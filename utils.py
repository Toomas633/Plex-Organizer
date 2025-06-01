"""Utility functions for file operations in Plex Organizer."""

import os
from log import log_error, log_duplicate
from config import get_delete_duplicates, get_include_quality


def is_plex_folder(path: str):
    """
    Checks if the given path is a Plex Versions folder.

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path is a Plex Versions folder, False otherwise.
    """
    return "Plex Versions" in path.split(os.sep)


def find_folders(directory: str):
    """
    Finds all subdirectories in the given directory.

    Args:
        directory (str): The directory to search for subfolders.

    Returns:
        list: A list of full paths to subdirectories.
    """
    try:
        return [
            os.path.join(directory, folder)
            for folder in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, folder))
        ]
    except OSError as e:
        log_error(f"Error finding folders in directory {directory}: {e}")
        return []


def move_file(source_path: str, destination_path: str, move=True):
    """
    Move or rename a file, handling duplicates and errors.

    Args:
        source_path (str): The path to the source file.
        destination_path (str): The path to move or rename the file to.
        move (bool, optional): If True, move the file; if False, rename. Defaults to True.
    """
    if source_path == destination_path:
        return

    if not os.path.exists(source_path):
        log_error(f"File not found: {source_path}.")
        return

    if os.path.exists(destination_path):
        log_duplicate(
            f"File already exists: {destination_path}. "
            f"Skipping {'move' if move else 'rename'} for {source_path}."
        )

        if get_delete_duplicates():
            try:
                os.remove(source_path)
            except OSError as e:
                log_error(f"Failed to delete duplicate {source_path}: {e}")

        return

    try:
        os.rename(source_path, destination_path)
    except OSError as e:
        log_error(
            f"Failed to {'move' if move else 'rename'} {source_path} to {destination_path}: {e}"
        )


def create_name(parts: list[str], extension: str, quality: str | None = None):
    """
    Create a standardized file name from a list of parts.

    Args:
        parts (list): A list of parts to include in the file name.

    Returns:
        str: The standardized file name.
    """
    if get_include_quality() and quality:
        parts.append(quality)

    return " ".join(part for part in parts if part) + extension


def is_tv_dir(root: str):
    """
    Check if the directory is in a TV show directory.

    Args:
        root (str): The root directory to check.

    Returns:
        bool: True if the directory is in a TV show directory, False otherwise.
    """
    return "tv" in root.split(os.sep)

