"""
This script organizes downloaded media files by cleaning up, renaming, and moving them
to appropriate directories for TV and movies. It also handles unwanted files, empty folders,
and interacts with qBittorrent and Plex folder structures.
"""

import os
import sys
import shutil
from log import log_error, check_clear_log
from qb import remove_torrent
import tv
import movie
from const import UNWANTED_FOLDERS, INC_FILTER, EXT_FILTER
from utils import find_folders, is_plex_folder, is_tv_dir, is_main_folder
from config import ensure_config_exists, get_enable_audio_tagging
from audio import tag_audio_track_languages

START_DIR = sys.argv[1]
TORRENT_HASH = sys.argv[2] if len(sys.argv) > 2 else None


def _analyze_video_languages(directory: str):
    """
    Analyzes and tags audio track languages for video files in the given directory.

    Args:
        directory (str): The directory to process.

    Returns:
        None
    """
    if not get_enable_audio_tagging():
        return

    for root, _, files in os.walk(directory, topdown=False):
        for file in files:
            if file.endswith(INC_FILTER) and not is_plex_folder(root):
                file_path = os.path.join(root, file)
                tag_audio_track_languages(file_path)


def _delete_unwanted_files(directory: str):
    """
    Deletes files in the given directory (and subdirectories) that do not match allowed extensions,
    and removes unwanted folders.

    Args:
        directory (str): The directory to clean up.

    Returns:
        None
    """
    for root, _, files in os.walk(directory, topdown=False):
        for folder in find_folders(root):
            folder_parts = {os.path.normcase(part) for part in folder.split(os.sep)}
            if any(
                os.path.normcase(unwanted) in folder_parts
                for unwanted in UNWANTED_FOLDERS
            ):
                try:
                    shutil.rmtree(folder)
                except OSError as e:
                    log_error(f"Failed to delete folder {folder}: {e}")

        unwanted_files = [
            f for f in files if not f.endswith(EXT_FILTER) or "sample" in f.lower()
        ]

        for file in unwanted_files:
            file_path = os.path.join(root, file)
            try:
                os.remove(file_path)
            except OSError as e:
                log_error(f"Failed to delete file {file_path}: {e}")


def _delete_empty_directories(directory: str):
    """
    Deletes all empty subdirectories within the given directory.

    Args:
        directory (str): The directory to clean up.

    Returns:
        None
    """
    for root, dirs, _ in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if not os.listdir(dir_path):
                os.rmdir(dir_path)


def _move_directories(directory: str):
    """
    Moves video files from subdirectories to the main directory using the appropriate handler.

    Args:
        directory (str): The target directory (MOVIES_DIR or TV_DIR).

    Returns:
        None
    """
    inc_filter = (".mkv", ".mp4")
    for root, _, files in os.walk(directory, topdown=False):
        for file in files:
            if file.endswith(inc_filter) and not is_plex_folder(root):
                if is_tv_dir(root):
                    tv.move(directory, root, file, not is_main_folder(START_DIR))
                else:
                    movie.move(directory, root, file)


def _rename_files(directory: str):
    """
    Renames video files in the given directory using the appropriate handler.

    Args:
        directory (str): The directory to process (MOVIES_DIR or TV_DIR).

    Returns:
        None
    """
    for root, _, files in os.walk(directory, topdown=False):
        for file in files:
            if file.endswith(INC_FILTER) and not is_plex_folder(root):
                if is_tv_dir(root):
                    tv.rename(directory, root, file, not is_main_folder(START_DIR))
                else:
                    movie.rename(root, file)


def main():
    """
    Main entry point for the organizer script.
    Handles argument parsing, torrent removal, and file organization steps.

    Returns:
        None
    """

    ensure_config_exists()
    check_clear_log()
    if len(sys.argv) < 2:
        log_error("Error: No directory provided.")
        log_error("Usage: qb_delete.py <dir> <optional_torrent_hash>")
        sys.exit(1)

    try:
        if TORRENT_HASH:
            remove_torrent(TORRENT_HASH)

        directories = []
        if is_main_folder(START_DIR):
            directories = [
                os.path.join(START_DIR, "tv"),
                os.path.join(START_DIR, "movies"),
            ]
        else:
            directories = [START_DIR]

        for directory in directories:
            _delete_unwanted_files(directory)
            _delete_empty_directories(directory)
            _rename_files(directory)
            _move_directories(directory)
            _delete_empty_directories(directory)
            _analyze_video_languages(directory)
    except (OSError, ValueError) as e:
        log_error(f"Error occured: {e}")


if __name__ == "__main__":
    main()
