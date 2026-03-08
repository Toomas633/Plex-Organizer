"""Shared ffmpeg / ffprobe helper utilities.

This module centralises subprocess wrappers, ffprobe queries, and ffmpeg
command-building helpers that are used by multiple modules (audio, subtitles).

Binary resolution is handled by the ``static_ffmpeg`` package which ships
pre-built static binaries for ffmpeg and ffprobe — no system install required.
"""

from __future__ import annotations

from functools import lru_cache
from json import JSONDecodeError, loads as json_loads
from os import remove, replace, stat, utime
from os.path import dirname, exists, splitext
from subprocess import run, CompletedProcess
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Sequence, Tuple
from static_ffmpeg import add_paths, run as ffmpeg_run

from .log import log_error

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


@lru_cache(maxsize=1)
def _resolve_binaries() -> Tuple[str, str]:
    """Return (ffmpeg_path, ffprobe_path) from the static-ffmpeg package.

    The result is cached so the download/check only happens once per process.
    """
    add_paths()
    ffmpeg_path, ffprobe_path = (
        ffmpeg_run.get_or_fetch_platform_executables_else_raise()
    )
    return ffmpeg_path, ffprobe_path


def get_ffmpeg() -> str:
    """Return the absolute path to the ffmpeg binary."""
    return _resolve_binaries()[0]


def get_ffprobe() -> str:
    """Return the absolute path to the ffprobe binary."""
    return _resolve_binaries()[1]


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


def probe_json(
    video_path: str,
    extra_args: Sequence[str] = (),
) -> Dict[str, Any]:
    """Run *ffprobe* with JSON output and return the parsed payload.

    ``ffprobe -v error -print_format json <extra_args> <video_path>``

    Returns an empty dict on failure.
    """
    ffprobe = get_ffprobe()
    proc = run_cmd(
        [ffprobe, "-v", "error", "-print_format", "json", *extra_args, video_path]
    )
    if proc.returncode != 0:
        return {}
    try:
        return json_loads(proc.stdout or "{}") or {}
    except (JSONDecodeError, TypeError):
        return {}


def probe_streams_json(
    video_path: str,
    stream_selector: str = "s",
) -> List[Dict[str, Any]]:
    """Probe streams (default: subtitle) from a container as parsed JSON dicts.

    Returns an empty list when ffprobe fails.
    """
    payload = probe_json(
        video_path, ["-show_streams", "-select_streams", stream_selector]
    )
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


def probe_duration_seconds(video_path: str) -> float | None:
    """Probe container duration in seconds.

    Returns ``None`` when ffprobe fails or the value is unavailable.
    """
    payload = probe_json(video_path, ["-show_entries", "format=duration"])
    fmt = payload.get("format") or {}
    dur = fmt.get("duration")
    if dur is None:
        return None
    try:
        return float(dur)
    except (ValueError, TypeError):
        return None


def probe_subtitle_stream_count(video_path: str) -> int:
    """Return the number of subtitle streams embedded in a container."""
    ffprobe = get_ffprobe()

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
    proc = run_cmd([*ffmpeg_input_cmd(ffmpeg, video_path), *WAV_OUTPUT_ARGS, wav_path])
    if proc.returncode != 0:
        log_error(
            f"ffmpeg failed extracting audio from '{video_path}':\n"
            f"{proc.stderr.strip()}"
        )
        return False
    return True


def ffmpeg_input_cmd(
    ffmpeg: str,
    video_path: str,
    pre_input: Sequence[str] = (),
) -> List[str]:
    """Return the standard ffmpeg invocation header for *video_path*.

    ``[ffmpeg, -y, -hide_banner, -loglevel, error, *pre_input, -i, video_path]``

    Use *pre_input* for flags that must precede ``-i`` (e.g. ``-ss``).
    """
    return [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *pre_input,
        "-i",
        video_path,
    ]


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
    out_dir = dirname(video_path)
    out_suffix = splitext(video_path)[1]

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
            if exists(path):
                remove(path)
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
