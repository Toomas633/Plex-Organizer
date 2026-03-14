"""
This module provides functions for renaming and moving movie files
to standardized formats and directories, including handling Plex folders
and logging errors or duplicates.
"""

from os import makedirs
from os.path import join, splitext, exists
from re import findall as re_findall, match as re_match, sub
from .log import log_error
from .ffmpeg_utils import probe_video_quality
from .utils import move_file, create_name, capitalize, find_corrected_directory


def _create_name(file: str, root: str) -> str:
    """
    Creates a standardized movie file name based on its current name.

    The new name format is: "Name (Year) [Quality].Extension".
    Quality is only included when enabled via config and when it can be detected.

    Args:
        file (str): The movie filename.
        root (str): The current directory containing *file*, used for probing
            video quality from the file when the filename lacks a quality tag.

    Returns:
        str: The standardized file name (or the original name if no rename is possible).
    """
    match = re_match(
        r"^(.*?)(?:[.\s])?((?:\(?\d{4}\)?[.\s)]+)+)(?:.*?(\d{3,4}p))?.*", file
    )

    if not match:
        log_error(f"Filename does not match expected pattern: {file}. Skipping rename.")
        return file

    years = re_findall(r"\d{4}", match.group(2))

    if not match.group(1):
        name = " ".join(years[:-1]) if len(years) >= 2 else years[0]
        year = years[-1]
    else:
        name = match.group(1).replace(".", " ").replace("(", "").strip()
        year = years[0] if years else None
        if len(years) >= 2:
            year = years[1]
            name = f"{name} {years[0]}"

    name_parts = [capitalize(name) if name else None]

    if year:
        name_parts.append(f"({year})")

    quality = match.group(3) if match.group(3) else None

    if not quality and root:
        quality = probe_video_quality(join(root, file))

    return create_name(
        name_parts,
        splitext(file)[1],
        quality,
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
    new_name = _create_name(file, root)
    movie_folder = sub(r" \d{3,4}p$", "", splitext(new_name)[0])
    movies_root = find_corrected_directory(directory)
    movie_dir = join(movies_root, movie_folder)

    source_path = join(root, file)
    destination_path = join(movie_dir, new_name)

    if source_path == destination_path:
        return destination_path

    if not exists(movie_dir):
        makedirs(movie_dir)

    move_file(source_path, destination_path)
    return destination_path
