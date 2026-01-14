"""Persistent per-library indexing for Plex Organizer.

The goal is to avoid re-processing media files that have already been handled by
Plex Organizer on prior runs.

Index location rules (per user request):
- Movies: store the index in the movies root.
- TV: store the index in the show root (tv/<Show>/).

We store paths relative to the index root plus file stat metadata so we can
invalidate entries if a file changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from json import JSONDecodeError, dump, load
from os import makedirs, path as os_path, replace, walk
from tempfile import NamedTemporaryFile
from typing import Any, Dict

from const import (
    INDEX_FILENAME,
    MOVIE_CORRECT_NAME_RE,
    TV_CORRECT_NAME_RE,
    TV_CORRECT_SEASON_RE,
    VIDEO_EXTENSIONS,
)
from dataclass import IndexEntry
from log import log_error
from utils import (
    capitalize,
    find_corrected_directory,
    is_plex_folder,
    is_script_temp_file,
    is_tv_dir,
)


def _index_file_path(index_root: str) -> str:
    return os_path.join(index_root, INDEX_FILENAME)


def _rel_key(index_root: str, file_path: str) -> str:
    rel = os_path.relpath(file_path, index_root)
    return os_path.normpath(rel)


def _read_index(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = load(f)
    except FileNotFoundError:
        log_error(f"Index file not found at path: {path}")
        return {"files": {}}
    except (OSError, JSONDecodeError):
        log_error(f"Error reading index file at path: {path}")
        return {"files": {}}

    if not isinstance(payload, dict):
        log_error(f"Invalid index format in file at path: {path}")
        return {"files": {}}

    files = payload.get("files")
    if isinstance(files, dict):
        return {"files": files}

    return {"files": payload}


def _write_index(path: str, payload: Dict[str, Any]) -> None:
    os_path_dir = os_path.dirname(path)
    if os_path_dir and not os_path.exists(os_path_dir):
        makedirs(os_path_dir, exist_ok=True)

    with NamedTemporaryFile("w", delete=False, dir=os_path_dir, encoding="utf-8") as f:
        dump(payload, f, indent=2, sort_keys=True)
        tmp_path = f.name

    replace(tmp_path, path)


def _is_indexed(index_root: str, file_path: str) -> bool:
    idx_path = _index_file_path(index_root)
    payload = _read_index(idx_path)
    files: Dict[str, Any] = payload.get("files", {})

    key = _rel_key(index_root, file_path)
    entry = files.get(key)

    return entry is not None


def mark_indexed(index_root: str, file_path: str) -> None:
    """Record *file_path* as processed under *index_root* (best-effort)."""
    idx_path = _index_file_path(index_root)
    payload = _read_index(idx_path)
    files: Dict[str, Any] = payload.get("files", {})
    payload = {"files": files}

    key = _rel_key(index_root, file_path)
    files[key] = IndexEntry(
        processed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    ).__dict__

    _write_index(idx_path, payload)


def should_index_video(index_root: str, file_path: str) -> bool:
    """Return True only when a video is already in the organizer's final layout.

    This prevents us from indexing raw/unprocessed filenames (which would cause
    future runs to skip files that still need renaming/moving).

    Rules:
    - Movies: file must be directly under index_root, and filename must match
      `Name (Year) [Quality].ext`.
    - TV: index_root is the show root (`tv/<Show>`). File must be directly under
      `Season XX/` and filename must start with the show title and contain `SxxEyy`.
    """
    if not file_path.lower().endswith(VIDEO_EXTENSIONS):
        return False

    if is_tv_dir(index_root):
        show_root = find_corrected_directory(index_root)
        if os_path.normpath(show_root) != os_path.normpath(index_root):
            return False

        if find_corrected_directory(os_path.dirname(file_path)) != show_root:
            return False

        season_dir = os_path.basename(os_path.dirname(file_path))
        season_match = TV_CORRECT_SEASON_RE.match(season_dir)
        if not season_match:
            return False
        season_folder = season_match.group(1)

        file_name = os_path.basename(file_path)
        show_title = capitalize(os_path.basename(show_root))
        prefix = f"{show_title} "
        if not file_name.startswith(prefix):
            return False

        name_match = TV_CORRECT_NAME_RE.match(file_name)
        if not name_match:
            return False

        season_in_name = name_match.group(1)
        return season_in_name == season_folder

    movies_root = find_corrected_directory(index_root)
    if os_path.normpath(movies_root) != os_path.normpath(index_root):
        return False
    if os_path.normpath(os_path.dirname(file_path)) != os_path.normpath(index_root):
        return False

    return bool(MOVIE_CORRECT_NAME_RE.match(os_path.basename(file_path)))


def _index_root_for_video_path(directory: str, video_path: str) -> str:
    return _index_root_for_path(directory, os_path.dirname(video_path))


def _index_root_for_path(directory: str, root: str) -> str:
    return (
        find_corrected_directory(root)
        if is_tv_dir(root)
        else find_corrected_directory(directory)
    )


def collect_indexed_videos(directory: str) -> dict[str, bool]:
    """Return a mapping of discovered video paths to "already indexed" status.

    Walks *directory* recursively (skipping Plex-managed folders) and checks each
    video file against the appropriate index root:
    - TV: show root (tv/<Show>/)
    - Movies: movies root

    Any index read errors are treated as "not indexed" (best-effort).
    """
    indexed_videos: dict[str, bool] = {}
    for root, _, files in walk(directory):
        if is_plex_folder(root):
            continue

        for file in files:
            if is_script_temp_file(file):
                continue
            if not file.lower().endswith(VIDEO_EXTENSIONS):
                continue

            video_path = os_path.join(root, file)
            index_root = _index_root_for_video_path(directory, video_path)
            try:
                indexed_videos[video_path] = _is_indexed(index_root, video_path)
            except OSError:
                indexed_videos[video_path] = False

    return indexed_videos


def index_root_for_path(directory: str, root: str) -> str:
    """Return the correct index root for a file in *root*.

    - TV: show root (tv/<Show>)
    - Movies: movies root
    """
    return (
        find_corrected_directory(root)
        if is_tv_dir(root)
        else find_corrected_directory(directory)
    )
