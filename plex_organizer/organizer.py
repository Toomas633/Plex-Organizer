"""Plex media organizer entrypoint.

This script walks a target directory (either a single torrent save folder, or a “main”
folder containing ``tv/`` and/or ``movies/``), and performs these steps:

- Optionally embeds external subtitles into matching video files.
- Optionally fetches missing subtitles from online providers.
- Optionally synchronizes embedded subtitle timing to the audio track.
- Optionally tags missing/unknown audio stream language metadata.
- Deletes unwanted files and unwanted subfolders (aggressive cleanup).
- Renames and moves video files into their final TV/Movie layout.
- Indexes processed files so they can be skipped on future runs.
- Deletes empty folders.

It can also remove a completed torrent from qBittorrent when a torrent hash is provided.
"""

from errno import EAGAIN, EACCES, EWOULDBLOCK
from os import walk
from os.path import join
from fcntl import flock, LOCK_EX, LOCK_NB
from time import sleep

from .log import log_error, check_clear_log, log_debug
from .qb import remove_torrent
from .utils import (
    is_tv_dir,
    is_main_folder,
    is_media_directory,
)
from .config import ensure_config_exists
from .paths import data_dir
from .subs.embedding import merge_subtitles_in_directory
from .subs.fetching import fetch_subtitles_in_directory
from .subs.syncing import sync_subtitles_in_directory
from .indexing import (
    collect_indexed_videos,
    migrate_show_indexes_to_tv_root,
)
from .pipeline import (
    analyze_video_languages,
    delete_unwanted_files,
    delete_empty_directories,
    move_directories,
    get_video_files_to_process,
)

_lock_handle = None  # pylint: disable=invalid-name


def _get_lock():
    """Best-effort single-instance lock.

    Repeatedly attempts to acquire a non-blocking exclusive lock on a lock file.
    If another process holds the lock, the function sleeps and retries.

    The file handle is kept open (in the module-level ``_lock_handle``) for the
    lifetime of the process so the advisory lock is not released prematurely.

    Note: the lock is advisory (``flock``).
    """
    global _lock_handle  # pylint: disable=global-statement
    lock_file_path = join(data_dir(), ".plex_organizer.lock")
    while True:
        try:
            _lock_handle = open(  # pylint: disable=consider-using-with
                lock_file_path, "a", encoding="utf-8"
            )
            flock(_lock_handle, LOCK_EX | LOCK_NB)
            break
        except OSError as exc:
            if _lock_handle is not None:
                _lock_handle.close()
                _lock_handle = None
            if exc.errno in (EAGAIN, EACCES, EWOULDBLOCK):
                log_debug(
                    "Another instance of Plex Organizer is already running. "
                    "Waiting..."
                )
                sleep(10)
            else:
                raise


def _process_directory(directory: str):
    """Run the full organizer pipeline for a single directory tree."""
    if is_tv_dir(directory):
        migrated = migrate_show_indexes_to_tv_root(directory)
        if migrated:
            log_debug(
                f"Auto-migrated {migrated} per-show index(es) to TV root: {directory}"
            )

    indexed_videos = collect_indexed_videos(directory)
    videos_to_process = [p for p, is_done in indexed_videos.items() if not is_done]

    merge_subtitles_in_directory(directory, video_paths=videos_to_process)
    fetch_subtitles_in_directory(directory, video_paths=videos_to_process)
    sync_subtitles_in_directory(directory, video_paths=videos_to_process)

    for root, _, files in walk(directory, topdown=False):
        videos_to_process = get_video_files_to_process(root, files, indexed_videos)
        analyze_video_languages(root, videos_to_process)
        delete_unwanted_files(root, files)
        move_directories(directory, root, videos_to_process)

    delete_empty_directories(directory)


def main(start_dir: str, torrent_hash: str | None):
    """Organizer entrypoint.

    Ensures config/logs exist, optionally removes a torrent from
    qBittorrent, then processes either a main folder or a single directory.
    """
    ensure_config_exists()
    check_clear_log()
    _get_lock()
    log_debug(
        f"Starting Plex Organizer with directory: {start_dir} and torrent hash: {torrent_hash}"
    )

    try:
        if torrent_hash:
            remove_torrent(torrent_hash)

        if not is_media_directory(start_dir):
            log_debug(
                f"Directory '{start_dir}' is not a recognised media folder. "
                "Keeping files and exiting."
            )
            return

        directories = []
        if is_main_folder(start_dir):
            directories = [
                join(start_dir, "tv"),
                join(start_dir, "movies"),
            ]
        else:
            directories = [start_dir]
        log_debug(f"Processing directories: {directories}")
        for directory in directories:
            _process_directory(directory)
    except (OSError, ValueError) as e:
        log_error(f"Unhandled entrypoint error occurred: {e}")
