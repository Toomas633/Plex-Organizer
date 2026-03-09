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

from os import walk, remove, listdir, rmdir, sep, environ
from os.path import join, normcase
from fcntl import flock, LOCK_EX, LOCK_NB
from time import sleep
from shutil import rmtree
from warnings import filterwarnings
from logging import getLogger, ERROR
from argparse import ArgumentParser, RawDescriptionHelpFormatter

filterwarnings("ignore", message=".*doesn't match a supported version")
environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
getLogger("huggingface_hub").setLevel(ERROR)

# pylint: disable=wrong-import-position
from .log import log_error, check_clear_log, log_debug
from .qb import remove_torrent
from .tv import move as tv_move
from .movie import move as movie_move
from .const import UNWANTED_FOLDERS, VIDEO_EXTENSIONS, EXT_FILTER
from .utils import (
    find_folders,
    find_corrected_directory,
    is_plex_folder,
    is_script_temp_file,
    is_tv_dir,
    is_main_folder,
    is_media_directory,
)
from .config import (
    ensure_config_exists,
    get_enable_audio_tagging,
)
from ._paths import data_dir
from .audio.tagging import tag_audio_track_languages
from .subs.embedding import merge_subtitles_in_directory
from .subs.fetching import fetch_subtitles_in_directory
from .subs.syncing import sync_subtitles_in_directory
from .indexing import (
    mark_indexed,
    should_index_video,
    collect_indexed_videos,
    index_root_for_path,
    migrate_show_indexes_to_tv_root,
)

# pylint: enable=wrong-import-position


def _get_lock():
    """Best-effort single-instance lock.

    Repeatedly attempts to acquire a non-blocking exclusive lock on a lock file.
    If another process holds the lock, the function sleeps and retries.

    Note: the lock is advisory (``flock``).
    """
    lock_file_path = join(data_dir(), ".plex_organizer.lock")
    while True:
        try:
            with open(lock_file_path, "w", encoding="utf-8") as lock_file:
                flock(lock_file, LOCK_EX | LOCK_NB)
                break
        except OSError:
            log_debug(
                "Another instance of plex_organizer.py is already running. Waiting..."
            )
            sleep(10)


def _analyze_video_languages(root: str, video_files: list[str]):
    """Analyze and tag missing audio language metadata for video files.

    This step is enabled/disabled via config and skips Plex-managed folders and
    temporary files created by this script.

    Args:
        root: Current directory being walked.
        files: Filenames present in *root*.
    """
    if not get_enable_audio_tagging():
        return

    for file in video_files:
        if is_plex_folder(root) or is_script_temp_file(file):
            continue

        file_path = join(root, file)
        tag_audio_track_languages(file_path)


def _delete_unwanted_files(root: str, files: list[str]):
    """Delete unwanted files and unwanted subfolders under *root*.

    Files are removed when they do not match the allow-list extension filter or when
    they look like sample media. Temporary files created by this script are preserved.

    Args:
        root: Current directory being walked.
        files: Filenames present in *root*.
    """
    _delete_unwanted_directories(root)

    unwanted_files = [
        f for f in files if not f.endswith(EXT_FILTER) or "sample" in f.lower()
    ]

    for file in unwanted_files:
        if not is_script_temp_file(file):
            file_path = join(root, file)
            try:
                log_debug(f"Deleting unwanted file: {file_path}")
                remove(file_path)
            except OSError as e:
                log_error(f"Failed to delete file {file_path}: {e}")


def _delete_unwanted_directories(root: str):
    """Delete unwanted subdirectories under *root* (recursive)."""
    for folder in find_folders(root):
        folder_parts = {normcase(part) for part in folder.split(sep)}
        if any(normcase(unwanted) in folder_parts for unwanted in UNWANTED_FOLDERS):
            try:
                log_debug(f"Deleting unwanted folder: {folder}")
                rmtree(folder)
            except OSError as e:
                log_error(f"Failed to delete folder {folder}: {e}")


def _delete_empty_directories(directory: str):
    """Delete empty subdirectories under *directory* (post-order)."""
    for root, dirs, _ in walk(find_corrected_directory(directory), topdown=False):
        for dir_name in dirs:
            dir_path = join(root, dir_name)
            if not listdir(dir_path):
                rmdir(dir_path)


def _move_directories(directory: str, root: str, video_files: list[str]):
    """Move/rename video files found in *root*.

    Dispatches to the TV or Movie handler based on the current directory path.

    Args:
        directory: The base directory being processed (used as the movie destination root).
        root: Current directory being walked.
        files: Filenames present in *root*.
    """

    def _move_one(file_name: str) -> str:
        if is_tv_dir(root):
            return tv_move(root, file_name)
        return movie_move(directory, root, file_name)

    def _try_mark(index_root: str, final_path: str) -> None:
        try:
            if should_index_video(index_root, final_path):
                mark_indexed(index_root, final_path)
        except OSError:
            pass

    if is_plex_folder(root):
        return

    index_root = index_root_for_path(directory, root)
    for file in video_files:
        if is_script_temp_file(file):
            continue

        final_path = _move_one(file)
        _try_mark(index_root, final_path)


def _get_video_files_to_process(
    root: str,
    files: list[str],
    indexed_videos: dict[str, bool],
) -> list[str]:
    return [
        f
        for f in files
        if f.lower().endswith(VIDEO_EXTENSIONS)
        and not indexed_videos.get(join(root, f), False)
    ]


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
        videos_to_process = _get_video_files_to_process(root, files, indexed_videos)
        _analyze_video_languages(root, videos_to_process)
        _delete_unwanted_files(root, files)
        _move_directories(directory, root, videos_to_process)

    _delete_empty_directories(directory)


def main():
    """CLI entrypoint.

    Validates args, ensures config/logs exist, optionally removes a torrent from
    qBittorrent, then processes either a main folder or a single directory.
    """
    parser = ArgumentParser(
        prog="plex-organizer",
        description="Automated media file organizer for Plex.",
        epilog=(
            "companion commands:\n"
            "  plex-organizer-setup   Interactive post-install setup & configuration\n"
            "  plex-organizer-index   Generate index files for an already-organized library\n"
            "  plex-organizer-kill    Kill all running plex-organizer processes"
        ),
        formatter_class=RawDescriptionHelpFormatter,
    )
    parser.add_argument("start_dir", help="Directory to process")
    parser.add_argument(
        "torrent_hash",
        nargs="?",
        default=None,
        help="Optional torrent hash to remove from qBittorrent",
    )
    args = parser.parse_args()

    start_dir = args.start_dir
    torrent_hash = args.torrent_hash

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
        log_error(f"Unhandeled entrypoint error occured: {e}")


if __name__ == "__main__":
    main()
