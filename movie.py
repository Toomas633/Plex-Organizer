"""
This module provides functions for renaming and moving movie files
to standardized formats and directories, including handling Plex folders
and logging errors or duplicates.
"""

import os
import re
from log import log_error
from utils import move_file, create_name


def rename(root: str, file: str):
    """
    Renames a movie file in the specified directory to a standardized format.

    The new name format is: "Name (Year) Quality.Extension" (e.g., "Inception (2010) 1080p.mkv").
    If the year or quality is missing, those parts are omitted.

    Args:
        root (str): The directory containing the file.
        file (str): The name of the file to rename.

    Returns:
        None
    """
    pattern = r"^(.*?)(?:[.\s])?((?:\d{4}[.\s])+)(?:.*?(\d{3,4}p))?.*"
    match = re.match(pattern, file)

    if not match:
        log_error(f"Filename does not match expected pattern: {file}. Skipping rename.")
        return

    if not match.group(1):
        name = match.group(2)
        year = file.split(".")[1]
    else:
        name = (
            match.group(1).replace(".", " ").replace("(", "").strip()
            if match.group(1)
            else None
        )
        years = match.group(2).split(".") if match.group(2) else []
        year = None
        if len(years) > 1:
            year = years[0]
        if len(years) > 2:
            year = years[1]
            name = f"{name} {years[0]}"

    name_parts = [name]

    if year:
        name_parts.append(f"({year})")

    new_name = create_name(
        name_parts,
        os.path.splitext(file)[1],
        match.group(3) if match.group(3) else None,
    )

    old_path = os.path.join(root, file)
    new_path = os.path.join(root, new_name)

    move_file(old_path, new_path, False)


def move(directory: str, root: str, file: str):
    """
    Moves a movie file from the source directory to the destination directory.

    If the source directory contains a Plex folder, it deletes it before moving.
    Handles duplicate files and missing source files gracefully.

    Args:
        directory (str): The directory to move the file to.
        root (str): The directory to move the file from.
        file (str): The name of the file to move.

    Returns:
        None
    """
    source_path = os.path.join(root, file)
    destination_path = os.path.join(directory, file)

    move_file(source_path, destination_path)
