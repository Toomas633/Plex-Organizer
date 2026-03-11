"""
This module provides functions for renaming and moving TV episode files
to standardized formats and directories, including handling Plex folders
and logging errors or duplicates.
"""

from os import makedirs, sep
from os.path import join, splitext, exists
from re import compile as re_compile, IGNORECASE

from .ffmpeg_utils import probe_video_quality
from .utils import move_file, create_name, capitalize, find_corrected_directory


def _create_name(root: str, file: str) -> str:
    """
    Creates a standardized name for a TV episode file.

    The new name format is: "ShowName SxxExx Quality.Extension"
    (e.g., "Breaking Bad S01E01 1080p.mkv").
    If the season/episode or quality is missing, those parts are omitted.

    Args:
        root (str): The current directory containing the file.
        file (str): The name of the file to rename.

    Returns:
        str: The standardized file name.
    """
    show_name = capitalize(find_corrected_directory(root).split(sep)[-1])
    season_episode_pattern = re_compile(r"[. ]S(\d{2})[ .]?E(\d{2})", IGNORECASE)
    quality_pattern = re_compile(r"[. ](\d{3,4}p)", IGNORECASE)

    season_episode_match = season_episode_pattern.search(file)
    if season_episode_match:
        season_episode = (
            f"S{season_episode_match.group(1)}E{season_episode_match.group(2)}"
        )
    else:
        season_episode = None

    quality_match = quality_pattern.search(file)
    quality = quality_match.group(1) if quality_match else None

    if not quality:
        quality = probe_video_quality(join(root, file))

    return create_name(
        [show_name, season_episode],
        splitext(file)[1],
        quality,
    )


def move(root: str, file: str) -> str:
    """
    Renames and moves a TV episode file to its correct season folder.

    The file is moved to: "<directory>/<ShowName>/Season <x>/"
    If the season cannot be determined, the file remains in place.

    Args:
        root (str): The current directory containing the file.
        file (str): The name of the file to move.

    Returns:
        None
    """
    new_name = _create_name(root, file)

    season_match = re_compile(r"S(\d{2})", IGNORECASE).search(new_name)
    season = int(season_match.group(1)) if season_match else 0

    correct_path = join(find_corrected_directory(root), f"Season {season}")

    old_path = join(root, file)
    new_path = join(correct_path, new_name)

    if root == correct_path:
        return old_path

    if not exists(correct_path):
        makedirs(correct_path)

    move_file(old_path, new_path)
    return new_path
