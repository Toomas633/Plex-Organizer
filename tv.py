"""
This module provides functions for renaming and moving TV episode files
to standardized formats and directories, including handling Plex folders
and logging errors or duplicates.
"""

import os
import re
from log import log_error, log_duplicate
from plex import has_plex_folder, delete_plex_folder


def rename(directory, root, file):
    """
    Renames a TV episode file to a standardized format.

    The new name format is: "ShowName SxxExx Quality.Extension" 
    (e.g., "Breaking Bad S01E01 1080p.mkv").
    If the season/episode or quality is missing, those parts are omitted.

    Args:
        directory (str): The base TV directory.
        root (str): The current directory containing the file.
        file (str): The name of the file to rename.

    Returns:
        None
    """
    show_name = os.path.relpath(root, directory).split(os.sep)[0]

    season_episode_pattern = re.compile(r"[. ]S(\d{2})E(\d{2})", re.IGNORECASE)
    quality_pattern = re.compile(r"[. ](\d{3,4}p)", re.IGNORECASE)

    season_episode_match = season_episode_pattern.search(file)
    season = f"S{season_episode_match.group(1)}" if season_episode_match else None
    episode = f"E{season_episode_match.group(2)}" if season_episode_match else None

    quality = quality_pattern.search(file).group(1) if quality_pattern.search(file) else None

    new_name_parts = [show_name, season + episode, quality]
    new_name = (
        " ".join(part for part in new_name_parts if part) + os.path.splitext(file)[1]
    )

    old_path = os.path.join(root, file)
    new_path = os.path.join(root, new_name)

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


def move(directory, root, file):
    """
    Moves a TV episode file to its correct season folder.

    The file is moved to: "<directory>/<ShowName>/Season <xx>/"
    If the season cannot be determined, the file remains in place.

    Args:
        directory (str): The base TV directory.
        root (str): The current directory containing the file.
        file (str): The name of the file to move.

    Returns:
        None
    """
    show_name = os.path.relpath(root, directory).split(os.sep)[0]
    season_pattern = re.compile(r"S(\d{2})", re.IGNORECASE)
    season_match = season_pattern.search(file)
    season = int(season_match.group(1)) if season_match else None

    correct_path = os.path.join(directory, show_name, f"Season {season}")

    old_path = os.path.join(root, file)
    new_path = os.path.join(correct_path, file)

    if root == correct_path:
        return

    if has_plex_folder(root):
        delete_plex_folder(root)

    if not os.path.exists(correct_path):
        os.makedirs(correct_path)

    if not os.path.exists(old_path):
        log_error(f"File not found: {old_path}. Skipping move.")
        return

    if os.path.exists(new_path):
        log_duplicate(f"File already exists: {new_path}. Skipping move for {old_path}.")
        return

    try:
        os.rename(old_path, new_path)
    except OSError as e:
        log_error(f"Failed to move {old_path} to {new_path}: {e}")
