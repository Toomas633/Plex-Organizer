"""Shared pipeline steps used by both the main entrypoint and the manage CLI."""

from os import walk, remove, listdir, rmdir, sep
from os.path import join, normcase
from shutil import rmtree

from .audio.tagging import tag_audio_track_languages
from .config import get_enable_audio_tagging, get_sonarr_enabled, get_radarr_enabled
from .const import UNWANTED_FOLDERS, VIDEO_EXTENSIONS, EXT_FILTER
from .indexing import mark_indexed, should_index_video, index_root_for_path
from .log import log_error, log_info, log_debug
from .movie import move as movie_move
from .tv import move as tv_move
from .utils import (
    find_folders,
    find_corrected_directory,
    is_plex_folder,
    is_script_temp_file,
    is_tv_dir,
)


def analyze_video_languages(root: str, video_files: list[str]):
    """Analyze and tag missing audio language metadata for video files.

    This step is enabled/disabled via config and skips Plex-managed folders and
    temporary files created by this script.

    Args:
        root: Current directory being walked.
        video_files: Filenames present in *root*.
    """
    if not get_enable_audio_tagging():
        return

    log_info(f"Analyzing audio languages in '{root}'")
    for file in video_files:
        if is_plex_folder(root) or is_script_temp_file(file):
            continue

        file_path = join(root, file)
        tag_audio_track_languages(file_path)


def _delete_unwanted_directories(root: str):
    """Delete unwanted subdirectories under *root* (recursive)."""
    for folder in find_folders(root):
        folder_parts = {normcase(part) for part in folder.split(sep)}
        if any(normcase(unwanted) in folder_parts for unwanted in UNWANTED_FOLDERS):
            try:
                log_debug(f"Deleting unwanted folder: {folder}")
                rmtree(folder)
            except OSError as e:
                log_error(f"Failed to delete folder {folder}: {e}")


def delete_unwanted_files(root: str, files: list[str]):
    """Delete unwanted files and unwanted subfolders under *root*.

    Files are removed when they do not match the allow-list extension filter or when
    they look like sample media. Temporary files created by this script are preserved.

    Args:
        root: Current directory being walked.
        files: Filenames present in *root*.
    """
    _delete_unwanted_directories(root)

    unwanted_files = [
        f for f in files if not f.endswith(EXT_FILTER) or "sample" in f.lower()
    ]

    for file in unwanted_files:
        if not is_script_temp_file(file):
            file_path = join(root, file)
            try:
                log_debug(f"Deleting unwanted file: {file_path}")
                remove(file_path)
            except OSError as e:
                log_error(f"Failed to delete file {file_path}: {e}")


def delete_empty_directories(directory: str):
    """Delete empty subdirectories under *directory* (post-order)."""
    for root, dirs, _ in walk(find_corrected_directory(directory), topdown=False):
        for dir_name in dirs:
            dir_path = join(root, dir_name)
            if not listdir(dir_path):
                rmdir(dir_path)


def _is_arr_managed(root: str) -> bool:
    """Return True when Sonarr/Radarr manages rename/move for this path."""
    if is_tv_dir(root) and get_sonarr_enabled():
        return True
    if not is_tv_dir(root) and get_radarr_enabled():
        return True
    return False


def _try_mark(idx_root: str, final_path: str) -> None:
    """Best-effort index marking: swallows OSError."""
    try:
        if should_index_video(idx_root, final_path):
            mark_indexed(idx_root, final_path)
    except OSError:
        pass


def move_directories(directory: str, root: str, video_files: list[str]):
    """Move/rename video files found in *root*.

    Dispatches to the TV or Movie handler based on the current directory path.
    When Sonarr (TV) or Radarr (movies) integration is enabled, rename/move is
    skipped because the *arr application already placed files in their final
    layout. Indexing still runs for files that are already in the correct layout.

    Args:
        directory: The base directory being processed (used as the movie destination root).
        root: Current directory being walked.
        video_files: Filenames present in *root*.
    """
    if is_plex_folder(root):
        return

    arr_managed = _is_arr_managed(root)
    if arr_managed:
        log_info(
            f"Rename/move skipped for '{root}' — managed by "
            f"{'Sonarr' if is_tv_dir(root) else 'Radarr'}"
        )

    idx_root = index_root_for_path(directory, root)
    for file in video_files:
        if is_script_temp_file(file):
            continue

        if arr_managed:
            final_path = join(root, file)
        else:
            final_path = _move_file(directory, root, file)
        _try_mark(idx_root, final_path)


def _move_file(directory: str, root: str, file_name: str) -> str:
    """Dispatch a single file to the TV or Movie move handler."""
    if is_tv_dir(root):
        log_info(f"Moving TV file '{file_name}' from '{root}'")
        return tv_move(root, file_name)
    log_info(f"Moving movie file '{file_name}' from '{root}'")
    return movie_move(directory, root, file_name)


def get_video_files_to_process(
    root: str,
    files: list[str],
    indexed_videos: dict[str, bool],
) -> list[str]:
    """Return video filenames from *files* that have not yet been indexed."""
    return [
        f
        for f in files
        if f.lower().endswith(VIDEO_EXTENSIONS)
        and not indexed_videos.get(join(root, f), False)
    ]
