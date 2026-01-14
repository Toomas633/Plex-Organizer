"""Generate Plex Organizer index files for an already-organized library.

This script scans a media root and creates/updates the `.plex_organizer.index`
files used by Plex Organizer to skip already-processed media.

Accepted inputs:
- A main root folder that contains BOTH `tv/` and `movies/`.
- A direct `tv/` folder.
- A direct `tv/<Show>/` folder.
- A direct `movies/` folder.

It only indexes videos that are already in their final layout and correctly
named (as defined by `indexing.should_index_video`).

Usage:
    python generate_indexes.py /path/to/media/root

Examples:
    python generate_indexes.py /mnt/media
    python generate_indexes.py /mnt/media/movies
    python generate_indexes.py /mnt/media/tv
"""

from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime
from json import JSONDecodeError, load
from os import walk
from os import path as os_path
from typing import Dict, Set

from config import ensure_config_exists
from const import INDEX_FILENAME, VIDEO_EXTENSIONS
from dataclass import IndexSummary
from indexing import index_root_for_path, mark_indexed, should_index_video
from utils import is_plex_folder, is_script_temp_file


def _rel_key(index_root: str, file_path: str) -> str:
    """Return the index key for *file_path* relative to *index_root*.

    The organizer stores file paths in index files as normalized relative paths.
    """
    rel = os_path.relpath(file_path, index_root)
    return os_path.normpath(rel)


def _read_index_keys(index_root: str) -> Set[str]:
    """Read existing index keys for *index_root*.

    Returns an empty set when the index does not exist or cannot be read.
    Only the current index format is supported: ``{"files": {<relpath>: {...}}}``.
    """
    idx_path = os_path.join(index_root, INDEX_FILENAME)
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            payload = load(f)
    except FileNotFoundError:
        return set()
    except (OSError, JSONDecodeError):
        return set()

    if not isinstance(payload, dict):
        return set()

    files = payload.get("files")
    if isinstance(files, dict):
        return set(files.keys())

    return set()


def _directories_to_scan(start_dir: str) -> list[str]:
    """Resolve *start_dir* into one or more directories to scan.

    Accepted inputs:
    - A main root containing BOTH ``tv/`` and ``movies/`` -> scan both.
    - The ``tv/`` folder -> scan it.
    - A ``tv/<Show>/`` folder -> scan that show only.
    - The ``movies/`` folder -> scan it.

    Raises:
        ValueError: when *start_dir* does not match any accepted shape.
    """
    tv_dir = os_path.join(start_dir, "tv")
    movies_dir = os_path.join(start_dir, "movies")

    if os_path.isdir(tv_dir) and os_path.isdir(movies_dir):
        return [tv_dir, movies_dir]

    base = os_path.basename(os_path.normpath(start_dir)).lower()
    if base == "tv":
        return [start_dir]
    if base == "movies":
        return [start_dir]

    parent = os_path.basename(os_path.dirname(os_path.normpath(start_dir))).lower()
    if parent == "tv":
        return [start_dir]

    raise ValueError(
        "Invalid root. Provide either a folder containing BOTH 'tv' and 'movies', or the 'tv' folder, or a 'tv/<Show>' folder, or the 'movies' folder."
    )


def _add_summary(a: IndexSummary, b: IndexSummary) -> IndexSummary:
    """Add two summaries together."""
    return IndexSummary(
        total_videos=a.total_videos + b.total_videos,
        eligible_videos=a.eligible_videos + b.eligible_videos,
        newly_indexed=a.newly_indexed + b.newly_indexed,
    )


def _is_video_candidate(file_name: str) -> bool:
    """Return True if *file_name* is a video file we should consider."""
    if is_script_temp_file(file_name):
        return False
    return file_name.lower().endswith(VIDEO_EXTENSIONS)


def _safe_should_index_video(index_root: str, video_path: str) -> bool:
    """Best-effort wrapper for ``should_index_video``.

    Returns False on any filesystem errors.
    """
    try:
        return should_index_video(index_root, video_path)
    except OSError:
        return False


def _safe_mark_indexed(index_root: str, video_path: str) -> bool:
    """Best-effort wrapper for ``mark_indexed``.

    Returns True if the file was recorded into the index, else False.
    """
    try:
        mark_indexed(index_root, video_path)
        return True
    except OSError:
        return False


def _get_or_load_index_keys(cache: Dict[str, Set[str]], index_root: str) -> Set[str]:
    """Return cached index keys for *index_root*, reading from disk if needed."""
    keys = cache.get(index_root)
    if keys is None:
        keys = _read_index_keys(index_root)
        cache[index_root] = keys
    return keys


def _scan_and_index_root(
    directory: str,
    root: str,
    files: list[str],
    cache: Dict[str, Set[str]],
) -> IndexSummary:
    """Scan a single filesystem *root* and update index files as needed.

    Args:
        directory: The scan base passed to ``index_root_for_path``.
        root: The current directory from ``os.walk``.
        files: Filenames present in *root*.
        cache: Mapping of index_root -> set of existing index keys.

    Returns:
        IndexSummary: counts for this single *root*.
    """
    total_videos = 0
    eligible_videos = 0
    newly_indexed = 0

    if is_plex_folder(root):
        return IndexSummary(0, 0, 0)

    index_root = index_root_for_path(directory, root)
    index_keys = _get_or_load_index_keys(cache, index_root)

    for file_name in files:
        if not _is_video_candidate(file_name):
            continue

        total_videos += 1
        video_path = os_path.join(root, file_name)
        if not _safe_should_index_video(index_root, video_path):
            continue

        eligible_videos += 1
        key = _rel_key(index_root, video_path)
        if key in index_keys:
            continue

        if not _safe_mark_indexed(index_root, video_path):
            continue

        index_keys.add(key)
        newly_indexed += 1

    return IndexSummary(
        total_videos=total_videos,
        eligible_videos=eligible_videos,
        newly_indexed=newly_indexed,
    )


def _scan_and_index_directory(
    directory: str, cache: Dict[str, Set[str]]
) -> IndexSummary:
    """Walk *directory* recursively and update index files (best-effort)."""
    summary = IndexSummary(0, 0, 0)
    for root, _, files in walk(directory):
        summary = _add_summary(
            summary, _scan_and_index_root(directory, root, files, cache)
        )
    return summary


def generate_indexes(start_dir: str) -> IndexSummary:
    """Generate/backfill organizer index files under *start_dir*.

    The script only indexes videos that are already in the organizer's final
    layout and correctly named.
    """
    start_dir = os_path.abspath(start_dir)
    if not os_path.isdir(start_dir):
        raise ValueError(f"Not a directory: {start_dir}")

    ensure_config_exists()

    dirs = _directories_to_scan(start_dir)

    cache: Dict[str, Set[str]] = {}

    total_videos = 0
    eligible_videos = 0
    newly_indexed = 0
    for directory in dirs:
        summary = _scan_and_index_directory(directory, cache)
        total_videos += summary.total_videos
        eligible_videos += summary.eligible_videos
        newly_indexed += summary.newly_indexed

    print(
        "\n".join(
            [
                f"Scanned: {start_dir}",
                f"Run at: {datetime.now().isoformat(timespec='seconds')}",
                f"Videos found: {total_videos}",
                f"Eligible (correct place/name): {eligible_videos}",
                f"Newly indexed: {newly_indexed}",
            ]
        )
    )

    return IndexSummary(
        total_videos=total_videos,
        eligible_videos=eligible_videos,
        newly_indexed=newly_indexed,
    )


def main() -> int:
    """CLI entrypoint."""
    parser = ArgumentParser(
        prog="generate_indexes.py",
        description=(
            "Generate/backfill .plex_organizer.index files for an already-organized library."
        ),
    )
    parser.add_argument(
        "root",
        help="Folder containing BOTH tv+movies, or the tv folder, or tv/<Show>, or the movies folder",
    )

    args = parser.parse_args()
    try:
        generate_indexes(args.root)
        return 0
    except ValueError as e:
        print(str(e))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
