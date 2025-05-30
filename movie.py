"""
This module provides functions for renaming and moving movie files
to standardized formats and directories, including handling Plex folders
and logging errors or duplicates.
"""

import os
import re
from log import log_error, log_duplicate
from plex import has_plex_folder, delete_plex_folder


def rename(directory, file):
    """
    Renames a movie file in the specified directory to a standardized format.

    The new name format is: "Name (Year) Quality.Extension" (e.g., "Inception (2010) 1080p.mkv").
    If the year or quality is missing, those parts are omitted.

    Args:
        directory (str): The directory containing the file.
        file (str): The name of the file to rename.

    Returns:
        None
    """
    pattern = r"^(.*?)[.\s]?(\d{4})[.\s]?(?:.*?(\d{3,4}p))?.*"
    match = re.match(pattern, file)

    if not match.group(1):
        name = match.group(2)
        year = file.split(".")[1]
    else:
        name = match.group(1).replace(".", " ").strip() if match.group(1) else None
        year = match.group(2) if match.group(2) else None

    quality = match.group(3) if match.group(3) else None

    if not year:
        new_name_parts = [name, quality]
    else:
        new_name_parts = [name, f"({year})", quality]

    new_name = (
        " ".join(part for part in new_name_parts if part) + os.path.splitext(file)[1]
    )

    old_path = os.path.join(directory, file)
    new_path = os.path.join(directory, new_name)

    if not os.path.exists(old_path):
        log_error(f"File not found: {old_path}. Skipping rename.")
        return

    if os.path.exists(new_path):
        log_duplicate(
            f"File already exists: {new_path}. Skipping rename for {old_path}."
        )
        return

    try:
        os.rename(old_path, new_path)
    except OSError as e:
        log_error(f"Failed to rename {old_path} to {new_path}: {e}")


def move(destination_dir, source_dir, file_name):
    """
    Moves a movie file from the source directory to the destination directory.

    If the source directory contains a Plex folder, it deletes it before moving.
    Handles duplicate files and missing source files gracefully.

    Args:
        destination_dir (str): The directory to move the file to.
        source_dir (str): The directory to move the file from.
        file_name (str): The name of the file to move.

    Returns:
        None
    """
    source_path = os.path.join(source_dir, file_name)
    destination_path = os.path.join(destination_dir, file_name)

    if source_path == destination_path:
        return

    if has_plex_folder(source_dir):
        delete_plex_folder(source_dir)

    if not os.path.exists(source_path):
        log_error(f"File not found: {source_path}. Skipping rename.")
        return

    if os.path.exists(destination_path):
        log_duplicate(
            f"File already exists: {destination_path}. Skipping rename for {source_path}."
        )
        return

    try:
        os.rename(source_path, destination_path)
    except OSError as e:
        log_error(f"Failed to move {source_path} to {destination_path}: {e}")
