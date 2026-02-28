"""Shared ffmpeg / ffprobe helper utilities.

This module centralises subprocess wrappers, ffprobe queries, and ffmpeg
command-building helpers that are used by multiple modules (audio, subtitles).
"""

from __future__ import annotations

from json import JSONDecodeError, loads as json_loads
from os import path as os_path, remove as os_remove, replace, stat, utime
from shutil import which
from subprocess import run, CompletedProcess
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional, Sequence

from log import log_error

COPY_STREAM_ARGS: List[str] = [
    "-c:v",
    "copy",
    "-c:a",
    "copy",
    "-map_metadata",
    "0",
    "-map_chapters",
    "0",
]

WAV_OUTPUT_ARGS: List[str] = [
    "-vn",
    "-sn",
    "-dn",
    "-ac",
    "1",
    "-ar",
    "16000",
    "-f",
    "wav",
]


def which_or_log(exe: str) -> Optional[str]:
    """Resolve an executable on PATH; log an error if missing."""
    resolved = which(exe)
    if not resolved:
        log_error(
            f"Missing required tool '{exe}'. "
            f"Install ffmpeg and ensure '{exe}' is on PATH."
        )
    return resolved


def which_or_raise(exe: str) -> str:
    """Resolve an executable on PATH or raise *RuntimeError*."""
    resolved = which(exe)
    if not resolved:
        raise RuntimeError(
            f"Missing required tool '{exe}'. "
            f"Install ffmpeg and ensure '{exe}' is on PATH."
        )
    return resolved


def run_cmd(cmd: List[str]) -> CompletedProcess[str]:
    """Run a subprocess command and capture stdout/stderr without raising."""
    return run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def probe_streams_json(
    video_path: str,
    stream_selector: str = "s",
) -> List[Dict[str, Any]]:
    """Probe streams (default: subtitle) from a container as parsed JSON dicts.

    Returns an empty list when ffprobe is missing or fails.
    """
    ffprobe = which("ffprobe")
    if not ffprobe:
        return []

    proc = run_cmd(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-select_streams",
            stream_selector,
            video_path,
        ]
    )
    if proc.returncode != 0:
        return []

    try:
        payload: Dict[str, Any] = json_loads(proc.stdout or "{}")
    except (JSONDecodeError, TypeError):
        return []

    streams = payload.get("streams") or []
    if not isinstance(streams, list):
        return []
    return [s for s in streams if isinstance(s, dict)]


def probe_subtitle_languages(video_path: str) -> set[str]:
    """Return ISO 639-2 language codes for subtitle streams already present."""
    streams = probe_streams_json(video_path, "s")
    languages: set[str] = set()
    for stream in streams:
        tags = stream.get("tags") or {}
        lang = tags.get("language", "").strip().casefold()
        if lang and lang not in {"und", "unknown", "0"}:
            languages.add(lang)
    return languages


def probe_subtitle_stream_count(video_path: str) -> int:
    """Return the number of subtitle streams embedded in a container."""
    ffprobe = which("ffprobe")
    if not ffprobe:
        return 0

    proc = run_cmd(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "s",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            video_path,
        ]
    )
    if proc.returncode != 0:
        return 0

    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    return len(lines)


def extract_wav(ffmpeg: str, video_path: str, wav_path: str) -> bool:
    """Extract full audio as 16 kHz mono WAV for Whisper.

    Returns True on success, False on failure.
    """
    proc = run_cmd(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            video_path,
            *WAV_OUTPUT_ARGS,
            wav_path,
        ]
    )
    if proc.returncode != 0:
        log_error(
            f"ffmpeg failed extracting audio from '{video_path}':\n"
            f"{proc.stderr.strip()}"
        )
        return False
    return True


def ffmpeg_input_cmd(ffmpeg: str, video_path: str) -> List[str]:
    """Return the standard ffmpeg invocation header for *video_path*.

    ``[ffmpeg, -y, -hide_banner, -loglevel, error, -i, video_path]``
    """
    return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", video_path]


def build_ffmpeg_base_cmd(
    ffmpeg: str,
    video_path: str,
    input_paths: Sequence[str],
) -> List[str]:
    """Build the common head of an ffmpeg embed command.

    Returns a command list containing:
    ``ffmpeg -y -hide_banner -loglevel error -i <video> [-i <path> ...]
      -map 0 [-map 1 ...] -c:v copy -c:a copy -map_metadata 0
      -map_chapters 0 -c:s copy``
    """
    cmd = ffmpeg_input_cmd(ffmpeg, video_path)

    for path in input_paths:
        cmd.extend(["-i", path])

    cmd.extend(["-map", "0"])
    for i in range(len(input_paths)):
        cmd.extend(["-map", str(i + 1)])

    cmd.extend(COPY_STREAM_ARGS)
    cmd.extend(["-c:s", "copy"])

    return cmd


def create_temp_output(video_path: str, prefix: str = ".ffutil.") -> str:
    """Create a temp output file next to *video_path* and return its path."""
    out_dir = os_path.dirname(video_path)
    out_suffix = os_path.splitext(video_path)[1]

    with NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=out_dir,
        prefix=prefix,
        suffix=out_suffix,
    ) as tmp:
        return tmp.name


def cleanup_paths(paths: Sequence[str]) -> None:
    """Best-effort delete of every path in *paths*."""
    for path in paths:
        try:
            if os_path.exists(path):
                os_remove(path)
        except OSError:
            pass


def replace_and_restore_timestamps(
    tmp_path: str,
    video_path: str,
) -> None:
    """Replace *video_path* with *tmp_path* and restore original timestamps."""
    st = stat(video_path)
    replace(tmp_path, video_path)
    utime(video_path, ns=(st.st_atime_ns, st.st_mtime_ns))
