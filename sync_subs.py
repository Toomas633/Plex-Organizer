"""Synchronize embedded subtitles to audio using ffsubsync.

When enabled (``sync_subtitles = true``), this module extracts each text-based
embedded subtitle stream, runs ``ffsubsync`` to align timing with the audio, and
re-embeds the synced subtitles back into the container.

Bitmap subtitle formats (PGS, VobSub) are left unchanged.  Plex-managed folders
are always skipped.
"""

from __future__ import annotations

from hashlib import sha256
from os import path as os_path
from tempfile import NamedTemporaryFile
from typing import Dict, List

from config import get_sync_subtitles
from const import VIDEO_EXTENSIONS
from ffmpeg_utils import (
    COPY_STREAM_ARGS,
    cleanup_paths,
    create_temp_output,
    ffmpeg_input_cmd,
    probe_streams_json,
    replace_and_restore_timestamps,
    run_cmd,
    which_or_log,
)
from log import log_debug, log_error
from utils import is_plex_folder
from const import TEXT_SUB_CODECS, ASS_CODECS


def _file_hash(path: str) -> str:
    """Return the SHA-256 hex digest of *path*."""
    h = sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_temp(directory: str, suffix: str, prefix: str = ".sync.") -> str:
    """Create a named temp file in *directory* and return its path."""
    with NamedTemporaryFile(
        mode="wb", delete=False, dir=directory, prefix=prefix, suffix=suffix
    ) as tmp:
        return tmp.name


def _extract_stream(
    ffmpeg: str, video_path: str, stream_idx: int, out_path: str, fmt: str
) -> bool:
    """Extract subtitle stream *stream_idx* as *fmt* to *out_path*."""
    proc = run_cmd(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            video_path,
            "-map",
            f"0:s:{stream_idx}",
            "-f",
            fmt,
            out_path,
        ]
    )
    if proc.returncode != 0:
        log_error(
            f"ffmpeg failed extracting subtitle stream {stream_idx} "
            f"from '{video_path}':\n{proc.stderr.strip()}"
        )
        return False
    return True


def _run_ffsubsync(ffsubsync: str, video_path: str, sub_in: str, sub_out: str) -> bool:
    """Run ffsubsync to sync *sub_in* against audio of *video_path*."""
    proc = run_cmd([ffsubsync, video_path, "-i", sub_in, "-o", sub_out])
    if proc.returncode != 0:
        log_error(f"ffsubsync failed for '{video_path}':\n{proc.stderr.strip()}")
        return False
    return True


def _get_sub_stream_metadata(video_path: str) -> List[Dict]:
    """Return metadata for every embedded subtitle stream.

    Each dict contains: ``index``, ``codec``, ``language``, ``title``,
    ``is_text`` (whether it's a text-based codec we can sync).
    """
    streams = probe_streams_json(video_path, "s")
    result: List[Dict] = []
    for i, stream in enumerate(streams):
        codec = (stream.get("codec_name") or "").strip().lower()
        tags = stream.get("tags") or {}
        result.append(
            {
                "index": i,
                "codec": codec,
                "language": tags.get("language", "und"),
                "title": tags.get("title", ""),
                "is_text": codec in TEXT_SUB_CODECS,
            }
        )
    return result


def _sub_codec_for(meta: Dict, is_mp4: bool) -> str:
    """Return the ffmpeg subtitle codec name to use for *meta*."""
    if is_mp4:
        return "mov_text"
    if meta["codec"] in ASS_CODECS:
        return "ass"
    return "srt"


def _build_remux_cmd(
    video_path: str,
    synced: Dict[int, str],
    metadata: List[Dict],
    tmp_path: str,
) -> List[str]:
    """Build the ffmpeg command list for remuxing synced subtitle streams."""
    ffmpeg = which_or_log("ffmpeg")
    if not ffmpeg:
        return []

    is_mp4 = os_path.splitext(video_path)[1].lower() == ".mp4"
    cmd = ffmpeg_input_cmd(ffmpeg, video_path)

    input_map: Dict[int, int] = {}
    for ff_idx, (stream_idx, srt_path) in enumerate(sorted(synced.items()), start=1):
        cmd.extend(["-i", srt_path])
        input_map[stream_idx] = ff_idx

    cmd.extend(["-map", "0", "-map", "-0:s"])
    for meta in metadata:
        idx = meta["index"]
        if idx in input_map:
            cmd.extend(["-map", f"{input_map[idx]}:0"])
        else:
            cmd.extend(["-map", f"0:s:{idx}"])

    cmd.extend(COPY_STREAM_ARGS)

    for i, meta in enumerate(metadata):
        codec = _sub_codec_for(meta, is_mp4) if meta["index"] in synced else "copy"
        cmd.extend([f"-c:s:{i}", codec])
        cmd.extend([f"-metadata:s:s:{i}", f"language={meta['language']}"])
        if meta["title"]:
            cmd.extend([f"-metadata:s:s:{i}", f"title={meta['title']}"])

    cmd.append(tmp_path)
    return cmd


def _remux_with_synced_subs(
    video_path: str,
    synced: Dict[int, str],
    metadata: List[Dict],
) -> bool:
    """Remux *video_path*, replacing synced subtitle streams.

    Streams not in *synced* are copied from the original.
    """
    tmp_path = create_temp_output(video_path, prefix=".syncsub.")
    cmd = _build_remux_cmd(video_path, synced, metadata, tmp_path)
    if not cmd:
        return False

    try:
        proc = run_cmd(cmd)
        if proc.returncode != 0:
            log_error(
                f"ffmpeg failed remuxing synced subs for '{video_path}':\n"
                f"{proc.stderr.strip()}"
            )
            return False
        replace_and_restore_timestamps(tmp_path, video_path)
        return True
    finally:
        cleanup_paths([tmp_path])


def _try_sync_stream(
    ffmpeg: str,
    ffsubsync_bin: str,
    video_path: str,
    meta: Dict,
    vid_dir: str,
) -> tuple[str | None, List[str]]:
    """Extract, sync, and return the synced path (or *None*) for one stream.

    Returns ``(synced_path_or_none, temp_files_created)``.
    """
    idx = meta["index"]
    is_ass = meta["codec"] in ASS_CODECS
    ext = ".ass" if is_ass else ".srt"
    fmt = "ass" if is_ass else "srt"

    extracted = _make_temp(vid_dir, suffix=ext, prefix=".syncin.")
    synced_path = _make_temp(vid_dir, suffix=ext, prefix=".syncout.")
    temps = [extracted, synced_path]

    if not _extract_stream(ffmpeg, video_path, idx, extracted, fmt):
        return None, temps

    if not _run_ffsubsync(ffsubsync_bin, video_path, extracted, synced_path):
        return None, temps

    if _file_hash(extracted) == _file_hash(synced_path):
        log_debug(
            f"Subtitle stream {idx} in '{video_path}' " "is already in sync, skipping"
        )
        return None, temps

    return synced_path, temps


def _sync_video_subtitles(video_path: str) -> None:
    """Sync all text-based subtitle streams in *video_path* to its audio."""
    if not os_path.isfile(video_path):
        return

    if is_plex_folder(video_path) or is_plex_folder(os_path.dirname(video_path)):
        return

    ffmpeg = which_or_log("ffmpeg")
    ffsubsync_bin = which_or_log("ffsubsync")
    if not ffmpeg or not ffsubsync_bin:
        return

    metadata = _get_sub_stream_metadata(video_path)
    text_streams = [m for m in metadata if m["is_text"]]
    if not text_streams:
        log_debug(f"No text subtitle streams to sync in '{video_path}'")
        return

    vid_dir = os_path.dirname(video_path)
    synced: Dict[int, str] = {}
    temp_files: List[str] = []

    try:
        for meta in text_streams:
            result, temps = _try_sync_stream(
                ffmpeg, ffsubsync_bin, video_path, meta, vid_dir
            )
            temp_files.extend(temps)
            if result:
                synced[meta["index"]] = result

        if not synced:
            log_debug(f"All subtitles already in sync for '{video_path}'")
            return

        langs = ", ".join(
            f"{metadata[idx]['language']}(s:{idx})" for idx in sorted(synced)
        )
        log_debug(f"Re-embedding synced subtitles ({langs}) into '{video_path}'")
        _remux_with_synced_subs(video_path, synced, metadata)
    finally:
        cleanup_paths(temp_files)


def sync_subtitles_in_directory(directory: str, video_paths: List[str]) -> None:
    """Sync embedded subtitles to audio for videos under *directory*.

    This is a best-effort operation: failures are logged and will not raise.
    It is a no-op when ``[Subtitles] sync_subtitles`` is ``false`` in config.

    Args:
        directory: Root directory being processed.
        video_paths: List of video file paths to check.
    """
    if not get_sync_subtitles():
        return

    if is_plex_folder(directory):
        return

    log_debug(f"Starting subtitle sync scan under '{directory}'")

    for video_path in video_paths:
        if not video_path.lower().endswith(VIDEO_EXTENSIONS):
            continue
        try:
            _sync_video_subtitles(video_path)
        except (OSError, RuntimeError, ValueError) as exc:
            log_error(f"Unexpected error syncing subtitles for '{video_path}': {exc}")
            continue
