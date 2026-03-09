"""Persistent per-library indexing for Plex Organizer.

The goal is to avoid re-processing media files that have already been handled by
Plex Organizer on prior runs.

Index location rules (per user request):
- Movies: store the index in the movies root.
- TV: store the index in the TV root (tv/).

We store paths relative to the index root plus file stat metadata so we can
invalidate entries if a file changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from json import JSONDecodeError, dump, load
from os import makedirs, replace, walk
from os.path import basename, dirname, exists, normpath, relpath, join, splitext
from re import sub as re_sub
from tempfile import NamedTemporaryFile
from typing import Any, Dict

from .const import (
    INDEX_FILENAME,
    MOVIE_CORRECT_NAME_RE,
    TV_CORRECT_NAME_RE,
    TV_CORRECT_SEASON_RE,
    VIDEO_EXTENSIONS,
)
from .dataclass import IndexEntry
from .log import log_error
from .utils import (
    capitalize,
    find_corrected_directory,
    is_plex_folder,
    is_script_temp_file,
    is_tv_dir,
)


def _index_file_path(index_root: str) -> str:
    return join(index_root, INDEX_FILENAME)


def _rel_key(index_root: str, file_path: str) -> str:
    rel = relpath(file_path, index_root)
    return normpath(rel)


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
    os_path_dir = dirname(path)
    if os_path_dir and not exists(os_path_dir):
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


def _is_valid_tv_layout(index_root: str, file_path: str) -> bool:
    """Return True if *file_path* matches the expected TV layout under *index_root*.

    Expected structure: ``index_root/<Show>/Season <N>/<Show> SxxEyy[.ext]``.
    *index_root* is the TV library root (e.g. ``tv/``).
    """
    tv_root = find_corrected_directory(index_root)
    if normpath(tv_root) != normpath(index_root):
        return False

    # File must be exactly three levels deep: tv / Show / Season X / file
    season_dir = dirname(file_path)
    show_dir = dirname(season_dir)
    parent_of_show = dirname(show_dir)

    if normpath(parent_of_show) != normpath(index_root):
        return False

    # Verify the show root resolves correctly
    if normpath(find_corrected_directory(season_dir)) != normpath(show_dir):
        return False

    season_name = basename(season_dir)
    season_match = TV_CORRECT_SEASON_RE.match(season_name)
    if not season_match:
        return False
    season_folder = season_match.group(1)

    file_name = basename(file_path)
    show_title = capitalize(basename(show_dir))
    prefix = f"{show_title} "
    if not file_name.startswith(prefix):
        return False

    name_match = TV_CORRECT_NAME_RE.match(file_name)
    if not name_match:
        return False

    return int(name_match.group(1)) == int(season_folder)


def _is_valid_movie_layout(index_root: str, file_path: str) -> bool:
    """Return True if *file_path* matches the expected movie layout under *index_root*."""
    movies_root = find_corrected_directory(index_root)
    if normpath(movies_root) != normpath(index_root):
        return False

    file_name = basename(file_path)
    if not MOVIE_CORRECT_NAME_RE.match(file_name):
        return False

    movie_dir = basename(dirname(file_path))
    expected_folder = re_sub(r" \d{3,4}p$", "", splitext(file_name)[0])
    if movie_dir != expected_folder:
        return False

    if normpath(dirname(dirname(file_path))) != normpath(index_root):
        return False

    return True


def should_index_video(index_root: str, file_path: str) -> bool:
    """Return True only when a video is already in the organizer's final layout.

    This prevents us from indexing raw/unprocessed filenames (which would cause
    future runs to skip files that still need renaming/moving).

    Rules:
    - Movies: file must be under `index_root/<Name (Year)>/` and
      filename must match `Name (Year) [Quality].ext`. The subfolder never includes quality.
    - TV: index_root is the TV library root (`tv/`). File must be under
      `<Show>/Season X/` and filename must start with the show title and contain
      `SxxEyy`.
    """
    if not file_path.lower().endswith(VIDEO_EXTENSIONS):
        return False

    if is_tv_dir(index_root):
        return _is_valid_tv_layout(index_root, file_path)

    return _is_valid_movie_layout(index_root, file_path)


def _index_root_for_video_path(directory: str, video_path: str) -> str:
    return _index_root_for_path(directory, dirname(video_path))


def _index_root_for_path(directory: str, root: str) -> str:
    return find_corrected_directory(directory)


def collect_indexed_videos(directory: str) -> dict[str, bool]:
    """Return a mapping of discovered video paths to "already indexed" status.

    Walks *directory* recursively (skipping Plex-managed folders) and checks each
    video file against the library index root (TV root or movies root).

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

            video_path = join(root, file)
            index_root = _index_root_for_video_path(directory, video_path)
            try:
                indexed_videos[video_path] = _is_indexed(index_root, video_path)
            except OSError:
                indexed_videos[video_path] = False

    return indexed_videos


def prune_index(index_root: str) -> int:
    """Remove index entries whose files no longer exist on disk.

    Args:
        index_root: The library root whose index should be pruned.

    Returns:
        The number of stale entries that were removed.
    """
    idx_path = _index_file_path(index_root)
    payload = _read_index(idx_path)
    files: Dict[str, Any] = payload.get("files", {})

    if not files:
        return 0

    stale_keys = [key for key in files if not exists(join(index_root, key))]

    for key in stale_keys:
        del files[key]

    if stale_keys:
        _write_index(idx_path, {"files": files})

    return len(stale_keys)


def index_root_for_path(directory: str, root: str) -> str:
    """Return the correct index root for a file in *root*.

    Both TV and movies use the library root (*directory*) as the index root.
    """
    return find_corrected_directory(directory)


def migrate_show_indexes_to_tv_root(tv_root: str) -> int:
    """Merge per-show index files into a single TV-root index.

    Walks *tv_root* looking for ``INDEX_FILENAME`` files inside show
    sub-directories.  Each entry is re-keyed relative to *tv_root* and merged
    into the root-level index.  The old per-show index files are removed.

    Args:
        tv_root: Path to the TV library root (e.g. ``/media/tv``).

    Returns:
        The number of old per-show index files that were migrated and removed.
    """
    from os import remove

    tv_root = normpath(tv_root)
    root_idx_path = _index_file_path(tv_root)
    root_payload = _read_index(root_idx_path)
    root_files: Dict[str, Any] = root_payload.get("files", {})

    migrated = 0
    for dirpath, _dirnames, filenames in walk(tv_root):
        if INDEX_FILENAME not in filenames:
            continue
        show_idx_path = join(dirpath, INDEX_FILENAME)
        if normpath(show_idx_path) == normpath(root_idx_path):
            continue

        show_payload = _read_index(show_idx_path)
        show_files: Dict[str, Any] = show_payload.get("files", {})

        for old_key, value in show_files.items():
            show_dir = basename(normpath(dirpath))
            new_key = normpath(join(show_dir, old_key))
            if new_key not in root_files:
                root_files[new_key] = value

        try:
            remove(show_idx_path)
        except OSError:
            log_error(f"Failed to remove old index: {show_idx_path}")

        migrated += 1

    if migrated:
        _write_index(root_idx_path, {"files": root_files})

    return migrated
