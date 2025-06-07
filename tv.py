"""
This module provides functions for renaming and moving TV episode files
to standardized formats and directories, including handling Plex folders
and logging errors or duplicates.
"""

import os
import re
from utils import move_file, create_name, capitalize


def rename(directory: str, root: str, file: str, take_name_from_root=False):
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
    if not take_name_from_root:
        show_name = capitalize(os.path.relpath(root, directory).split(os.sep)[0])
    else:
        show_name = capitalize(directory.split(os.sep)[-1])

    season_episode_pattern = re.compile(r"[. ]S(\d{2})[ .]?E(\d{2})", re.IGNORECASE)
    quality_pattern = re.compile(r"[. ](\d{3,4}p)", re.IGNORECASE)

    season_episode_match = season_episode_pattern.search(file)
    if season_episode_match:
        season_episode = (
            f"S{season_episode_match.group(1)}E{season_episode_match.group(2)}"
        )
    else:
        season_episode = None

    quality_match = quality_pattern.search(file)

    new_name = create_name(
        [show_name, season_episode],
        os.path.splitext(file)[1],
        quality_match.group(1) if quality_match else None,
    )

    old_path = os.path.join(root, file)
    new_path = os.path.join(root, new_name)

    move_file(old_path, new_path, False)


def move(directory: str, root: str, file: str, move_to_root=False):
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
    season_pattern = re.compile(r"S(\d{2})", re.IGNORECASE)
    season_match = season_pattern.search(file)
    season = int(season_match.group(1)) if season_match else 0

    if not move_to_root:
        show_name = os.path.relpath(root, directory).split(os.sep)[0]
        correct_path = os.path.join(directory, show_name, f"Season {season:02d}")
    else:
        correct_path = os.path.join(directory, f"Season {season:02d}")

    old_path = os.path.join(root, file)
    new_path = os.path.join(correct_path, file)

    if root == correct_path:
        return

    if not os.path.exists(correct_path):
        os.makedirs(correct_path)

    move_file(old_path, new_path)
