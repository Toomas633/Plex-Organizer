"""
This module provides utilities for detecting and deleting Plex Versions folders,
as well as general folder operations for media organization.
"""

import os
import shutil
from log import log_error


def find_folders(directory):
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


def is_plex_folder(path):
    """
    Checks if the given path is a Plex Versions folder.

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path is a Plex Versions folder, False otherwise.
    """
    return "Plex Versions" in path.split(os.sep)


def has_plex_folder(directory):
    """
    Determines if the specified directory contains a Plex Versions folder.

    Args:
        directory (str): The directory to check.

    Returns:
        bool: True if a Plex Versions folder exists, False otherwise.
    """
    for folder in find_folders(directory):
        if is_plex_folder(folder):
            return True
    return False


def delete_plex_folder(directory):
    """
    Deletes all Plex Versions folders in the specified directory.

    Args:
        directory (str): The directory to search for Plex Versions folders.

    Returns:
        None
    """
    try:
        for folder in find_folders(directory):
            if is_plex_folder(folder):
                shutil.rmtree(folder)
    except OSError as e:
        log_error(f"Error finding folders in directory {directory}: {e}")
