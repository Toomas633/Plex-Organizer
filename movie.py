"""
This module provides functions for renaming and moving movie files
to standardized formats and directories, including handling Plex folders
and logging errors or duplicates.
"""

from os import path as os_path
from re import match as re_match
from log import log_error
from const import MOVIE_CORRECT_NAME_RE
from utils import move_file, create_name, capitalize, find_corrected_directory


def _create_name(file: str) -> str:
    """
    Creates a standardized movie file name based on its current name.

    The new name format is: "Name (Year) [Quality].Extension".
    Quality is only included when enabled via config and when it can be detected.

    Args:
        file (str): The movie filename.

    Returns:
        str: The standardized file name (or the original name if no rename is possible).
    """
    if MOVIE_CORRECT_NAME_RE.match(file):
        return file

    match = re_match(r"^(.*?)(?:[.\s])?((?:\d{4}[.\s])+)(?:.*?(\d{3,4}p))?.*", file)

    if not match:
        log_error(f"Filename does not match expected pattern: {file}. Skipping rename.")
        return file

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

    name_parts = [capitalize(name) if name else None]

    if year:
        name_parts.append(f"({year})")

    return create_name(
        name_parts,
        os_path.splitext(file)[1],
        match.group(3) if match.group(3) else None,
    )


def move(directory: str, root: str, file: str) -> str:
    """
    Renames and moves a movie file from the source directory to the destination directory.

    If the source directory contains a Plex folder, it deletes it before moving.
    Handles duplicate files and missing source files gracefully.

    Args:
        directory (str): The directory to move the file to.
        root (str): The directory to move the file from.
        file (str): The name of the file to move.

    Returns:
        None
    """
    source_path = os_path.join(root, file)
    destination_path = os_path.join(
        find_corrected_directory(directory), _create_name(file)
    )

    if source_path == destination_path:
        return destination_path

    move_file(source_path, destination_path)
    return destination_path
