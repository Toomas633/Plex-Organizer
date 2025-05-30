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
from utils import find_folders, is_plex_folder
from config import ensure_config_exists

START_DIR = sys.argv[1] if len(sys.argv) > 1 else None
TORRENT_HASH = sys.argv[2] if len(sys.argv) > 2 else None

TV_DIR = os.path.join(START_DIR, "tv")
MOVIES_DIR = os.path.join(START_DIR, "movies")


def delete_unwanted_files(directory: str):
    """
    Deletes files in the given directory (and subdirectories) that do not match allowed extensions,
    and removes unwanted folders.

    Args:
        directory (str): The directory to clean up.

    Returns:
        None
    """
    unwanted_folders = {
        "Plex Versions",
        "Extras",
        "Sample",
        "Samples",
        "Subs",
        "Subtitles",
        "Proof",
        "Screenshots",
        "Artwork",
        "Cover",
        "Covers",
        "Poster",
    }
    ext_filter = (".mkv", ".!qB", ".mp4")

    for root, _, files in os.walk(directory, topdown=False):
        for folder in find_folders(root):
            try:
                folder_parts = set(folder.split(os.sep))
                if unwanted_folders & folder_parts:
                    shutil.rmtree(folder)
            except OSError as e:
                log_error(f"Failed to delete folder {folder}: {e}")
        for file in files:
            if not file.endswith(ext_filter):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                except OSError as e:
                    log_error(f"Failed to delete file {file_path}: {e}")


def delete_empty_directories(directory: str):
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


def move_directories(directory: str):
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
                if directory == MOVIES_DIR:
                    movie.move(directory, root, file)
                else:
                    tv.move(directory, root, file)


def rename_files(directory: str):
    """
    Renames video files in the given directory using the appropriate handler.

    Args:
        directory (str): The directory to process (MOVIES_DIR or TV_DIR).

    Returns:
        None
    """
    inc_filter = (".mkv", ".mp4")
    for root, _, files in os.walk(directory, topdown=False):
        for file in files:
            if file.endswith(inc_filter) and not is_plex_folder(root):
                if directory == TV_DIR:
                    tv.rename(directory, root, file)
                else:
                    movie.rename(root, file)


def main():
    """
    Main entry point for the organizer script.
    Handles argument parsing, torrent removal, and file organization steps.

    Returns:
        None
    """
    try:
        if len(sys.argv) < 2:
            log_error("Error: No directory provided.")
            log_error("Usage: qb_delete.py <dir> <torrent_hash>")
            sys.exit(1)

        if TORRENT_HASH:
            remove_torrent(TORRENT_HASH)

        for directory in [MOVIES_DIR, TV_DIR]:
            delete_unwanted_files(directory)
            delete_empty_directories(directory)
            rename_files(directory)
            move_directories(directory)
            delete_empty_directories(directory)
    except (OSError, ValueError) as e:
        log_error(f"Error occured: {e}")


if __name__ == "__main__":
    ensure_config_exists()
    main()
