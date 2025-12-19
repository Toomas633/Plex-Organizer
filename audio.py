"""Audio language tagging utilities.

This module inspects audio streams in a video file via ffprobe/ffmpeg and, when
language metadata is missing/unknown, samples short audio segments and uses a
Whisper-based detector to infer the spoken language. Detected languages are
written back into the container as ISO 639-2 language tags.
"""

from __future__ import annotations
from json import loads
from os import path as os_path, stat, replace, utime
from shutil import which
from subprocess import run, CompletedProcess
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional, Tuple
from config import get_cpu_threads
from const import ISO639_1_TO_2
from dataclass import AudioStream
from log import log_error
from utils import is_plex_folder
from whisper_detector import WhisperDetector


def _which_or_raise(exe: str) -> str:
    """Resolve an executable on PATH or raise.

    Args:
        exe: Executable name to locate (e.g., "ffprobe", "ffmpeg").

    Returns:
        The resolved absolute path to the executable.

    Raises:
        RuntimeError: If the executable is not found on PATH.
    """
    resolved = which(exe)
    if not resolved:
        raise RuntimeError(
            f"Missing required tool '{exe}'. Install ffmpeg and ensure '{exe}' is on PATH."
        )
    return resolved


def _run(cmd: List[str]) -> CompletedProcess[str]:
    """Run a subprocess command and capture output.

    Args:
        cmd: Command argv list.

    Returns:
        CompletedProcess with stdout/stderr captured as text.

    Notes:
        This helper never raises on non-zero exit codes; callers must check
        returncode and handle stderr.
    """
    return run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def _audio_stream_from_ffprobe(audio_index: int, stream: Dict[str, Any]) -> AudioStream:
    """Convert an ffprobe stream payload into an AudioStream.

    Args:
        audio_index: Zero-based index within the probed audio stream list.
        stream: A single stream dict from ffprobe's JSON output.

    Returns:
        Parsed AudioStream with normalized types.
    """
    tags = stream.get("tags") or {}

    sample_rate = stream.get("sample_rate")
    try:
        sample_rate_int = int(sample_rate) if sample_rate is not None else None
    except ValueError:
        sample_rate_int = None

    ffprobe_idx_any = stream.get("index")
    ffprobe_idx = int(ffprobe_idx_any) if ffprobe_idx_any is not None else -1

    channels = stream.get("channels")

    return AudioStream(
        audio_index=audio_index,
        ffprobe_index=ffprobe_idx,
        codec_name=stream.get("codec_name"),
        channels=int(channels) if channels is not None else None,
        sample_rate=sample_rate_int,
        language=tags.get("language"),
        title=tags.get("title"),
    )


def _probe_audio_streams(video_path: str) -> List[AudioStream]:
    """Probe audio streams from a container using ffprobe.

    Args:
        video_path: Path to a local media file.

    Returns:
        A list of AudioStream objects in stream order (audio_index).

    Raises:
        FileNotFoundError: If video_path does not exist.
        RuntimeError: If ffprobe is missing or fails.
    """
    if not os_path.isfile(video_path):
        raise FileNotFoundError(video_path)

    _which_or_raise("ffprobe")
    proc = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-select_streams",
            "a",
            video_path,
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for '{video_path}':\n{proc.stderr.strip()}")

    payload: Dict[str, Any] = loads(proc.stdout or "{}")
    streams: List[Dict[str, Any]] = payload.get("streams", [])

    return [_audio_stream_from_ffprobe(i, s) for i, s in enumerate(streams)]


def _probe_duration_seconds(video_path: str) -> Optional[float]:
    """Probe container duration in seconds.

    Args:
        video_path: Path to a local media file.

    Returns:
        Duration in seconds, or None if unavailable/ffprobe fails.
    """
    if not os_path.isfile(video_path):
        raise FileNotFoundError(video_path)

    _which_or_raise("ffprobe")
    proc = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_entries",
            "format=duration",
            video_path,
        ]
    )
    if proc.returncode != 0:
        return None

    try:
        payload: Dict[str, Any] = loads(proc.stdout or "{}")
        fmt = payload.get("format") or {}
        dur = fmt.get("duration")
        if dur is None:
            return None
        return float(dur)
    except (ValueError, TypeError):
        return None


def _sampling_params_for_duration(dur_seconds: float) -> Tuple[int, List[float]]:
    """Return intro-skip seconds and sampling fractions based on total duration."""
    if dur_seconds < 2400:
        return (120, [0.25, 0.55, 0.80])
    if dur_seconds < 4800:
        return (300, [0.20, 0.50, 0.78])
    return (720, [0.18, 0.45, 0.72])


def _pick_offsets(
    usable_end_seconds: float,
    min_start: int,
    max_start: int,
    fracs: List[float],
) -> List[int]:
    """Pick up to three clamped and de-duplicated offsets."""
    offsets = [
        max(min_start, min(int(usable_end_seconds * f), max_start)) for f in fracs[:3]
    ]
    dedup: List[int] = list(dict.fromkeys(offsets))

    while len(dedup) < 3:
        nxt = min(max_start, (dedup[-1] + 60) if dedup else min_start)
        if nxt in dedup:
            break
        dedup.append(nxt)

    return dedup[:3]


def _get_content_aware_offsets(
    duration_seconds: Optional[float],
) -> Optional[List[int]]:
    """Choose a small set of timestamps likely to contain dialogue.

    The goal is to avoid intros/outros and sample multiple points across the
    main content, improving language detection stability.

    Args:
        duration_seconds: Total duration of the media file.

    Returns:
        A list of up to 3 offsets (seconds), or None if duration is unusable.
    """
    if duration_seconds is None:
        return None

    try:
        dur = float(duration_seconds)
    except (TypeError, ValueError):
        return None

    if dur <= 0:
        return None

    end_padding = 300
    usable_end = max(0.0, dur - end_padding)
    if usable_end <= 0:
        return None

    intro_skip, fracs = _sampling_params_for_duration(dur)

    min_start = max(intro_skip, 30)
    max_start = int(max(0.0, usable_end - float(20)))
    if max_start <= min_start:
        return None

    offsets = _pick_offsets(usable_end, min_start, max_start, fracs)
    return offsets if offsets else None


def _sample_track_languages(
    video_path: str,
    stream: AudioStream,
    offsets: List[int],
    tmpdir: str,
) -> List[Tuple[Optional[str], float]]:
    """Extract and detect language for several samples from one audio stream.

    Args:
        video_path: Path to the media file.
        stream: Audio stream descriptor.
        offsets: Start offsets (seconds) for samples.
        tmpdir: Temporary directory to write WAV samples into.

    Returns:
        List of (iso639_2_language_or_none, confidence) tuples per sample.
    """
    samples: List[Tuple[Optional[str], float]] = []
    detector = WhisperDetector(cpu_threads=get_cpu_threads())
    wav_path = os_path.join(tmpdir, f"a{stream.audio_index}.wav")

    for offset in offsets:
        _extract_audio_sample(
            video_path,
            stream.audio_index,
            wav_path,
            start_seconds=offset,
        )
        lang_code, confidence = detector.detect_language(wav_path)
        samples.append((_normalize_language_to_iso639_2(lang_code), confidence))

    return samples


def _choose_language_from_samples(
    samples: List[Tuple[Optional[str], float]],
) -> Tuple[Optional[str], float]:
    """Pick a single language decision from multiple (lang, confidence) samples.

    Selection is based on a simple voting/aggregation scheme:
    - Prefer the language with the most sample hits; tie-break by confidence sum.
    - Require at least moderate confidence to emit a language.

    Args:
        samples: Per-sample language guesses and confidences.

    Returns:
        (chosen_language_or_none, best_observed_confidence).
    """
    by_lang: Dict[str, List[float]] = {}
    for lang, conf in samples:
        if not lang:
            continue
        by_lang.setdefault(lang, []).append(conf)

    if not by_lang:
        best_conf = max((conf for _l, conf in samples), default=0.0)
        return (None, best_conf)

    best_lang = ""
    best_count = -1
    best_sum = -1.0
    best_max = 0.0
    for lang, confs in by_lang.items():
        count = len(confs)
        total = float(sum(confs))
        m = float(max(confs))
        if (count > best_count) or (count == best_count and total > best_sum):
            best_lang = lang
            best_count = count
            best_sum = total
            best_max = m

    if best_count >= 2 and best_max >= 0.40:
        return (best_lang, best_max)
    if best_count == 1 and best_max >= 0.70:
        return (best_lang, best_max)
    return (None, best_max)


def _detect_languages_for_streams(
    video_path: str,
    streams: List[AudioStream],
) -> List[Tuple[AudioStream, Optional[str], float]]:
    """Detect (or reuse) language tags for each audio stream.

    Args:
        video_path: Path to the media file.
        streams: Probed audio streams.

    Returns:
        A list of (stream, language_or_none, confidence) for each stream.
    """
    detections: List[Tuple[AudioStream, Optional[str], float]] = []

    with TemporaryDirectory(prefix="plex_audio_lang_") as tmpdir:
        for stream in streams:
            if not _should_update_language(stream.language):
                detections.append(
                    (stream, _normalize_language_to_iso639_2(stream.language), 1.0)
                )
                continue

            offsets = _get_content_aware_offsets(_probe_duration_seconds(video_path))
            if offsets is None:
                offsets = [30 + (120 * i) for i in range(3)]

            samples = _sample_track_languages(
                video_path,
                stream,
                offsets,
                tmpdir,
            )
            chosen_lang, chosen_conf = _choose_language_from_samples(samples)
            detections.append((stream, chosen_lang, chosen_conf))
    return detections


def _apply_language_metadata(
    video_path: str, detections: List[Tuple[AudioStream, Optional[str], float]]
) -> None:
    """Write language metadata to the container (stream-level) using ffmpeg.

    Args:
        video_path: Path to the media file (modified in-place).
        detections: Per-stream detection results.

    Raises:
        RuntimeError: If ffmpeg fails to rewrite the file.
    """
    updates = [(s, lang) for (s, lang, _conf) in detections if lang]
    if not updates:
        return

    _which_or_raise("ffmpeg")
    in_stat = stat(video_path)
    base, ext = os_path.splitext(video_path)
    tmp_out = f"{base}.langtag.tmp{ext}"

    cmd: List[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        video_path,
        "-map",
        "0",
        "-c",
        "copy",
    ]

    for stream, lang, _conf in detections:
        if not lang:
            continue
        cmd.extend(["-metadata:s:a:" + str(stream.audio_index), "language=" + lang])

    cmd.append(tmp_out)

    proc = _run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed while writing language tags to '{video_path}':\n{proc.stderr.strip()}"
        )

    replace(tmp_out, video_path)

    try:
        utime(video_path, (in_stat.st_atime, in_stat.st_mtime))
    except OSError:
        pass


def _normalize_language_to_iso639_2(code: Optional[str]) -> Optional[str]:
    """Normalize a language code to ISO 639-2 (three-letter) when possible.

    Args:
        code: Two-letter (ISO 639-1), three-letter (ISO 639-2), or unknown tag.

    Returns:
        ISO 639-2 three-letter code, or None if unknown/unmappable.
    """
    if not code:
        return None
    code = code.strip().lower()
    if not code or code in {"und", "unknown"}:
        return None
    if len(code) == 3:
        return code
    if len(code) == 2:
        return ISO639_1_TO_2.get(code)
    return None


def _extract_audio_sample(
    video_path: str,
    audio_index: int,
    wav_path: str,
    start_seconds: int = 0,
) -> None:
    """Extract a short mono 16kHz WAV sample from an audio stream.

    Args:
        video_path: Path to the media file.
        audio_index: Zero-based audio stream index as used by ffmpeg (0:a:N).
        wav_path: Output WAV path.
        start_seconds: Start offset in seconds for the sample.

    Raises:
        RuntimeError: If ffmpeg fails to extract the sample.
    """
    _which_or_raise("ffmpeg")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(start_seconds),
        "-i",
        video_path,
        "-map",
        f"0:a:{audio_index}",
        "-t",
        "20",
        "-vn",
        "-sn",
        "-dn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        wav_path,
    ]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(
            (
                f"ffmpeg failed extracting audio stream 0:a:{audio_index} "
                f"from '{video_path}':\n{proc.stderr.strip()}"
            )
        )


def _should_update_language(existing: Optional[str]) -> bool:
    """Return True when a stream language tag is missing/unknown."""
    normalized = _normalize_language_to_iso639_2(existing)
    return normalized is None


def tag_audio_track_languages(video_path: str) -> None:
    """Detect and tag missing audio track language metadata for a video.

    This is the public entrypoint for this module.

    Args:
        video_path: Path to a local media file.

    Notes:
        Errors are logged via log_error() and do not raise.
    """
    if is_plex_folder(video_path) or is_plex_folder(os_path.dirname(video_path)):
        return

    try:
        streams = _probe_audio_streams(video_path)
        if not streams:
            return

        detections = _detect_languages_for_streams(video_path, streams)

        _apply_language_metadata(video_path, detections)
    except (RuntimeError, OSError, ValueError) as e:
        log_error(str(e))
        return
