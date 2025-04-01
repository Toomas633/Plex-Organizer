import os
import shutil
from log import log_error


def find_folders(dir):
    try:
        return [
            os.path.join(dir, folder)
            for folder in os.listdir(dir)
            if os.path.isdir(os.path.join(dir, folder))
        ]
    except Exception as e:
        log_error(f"Error finding folders in directory {dir}: {e}")
        return []


def is_plex_folder(path):
    folders = path.split(os.sep)
    return "Plex Versions" in folders


def has_plex_folder(dir):
    for folder in find_folders(dir):
        if is_plex_folder(folder):
            return True
    return False


def delete_plex_folder(dir):
    try:
        for folder in find_folders(dir):
            if is_plex_folder(folder):
                shutil.rmtree(folder)
    except Exception as e:
        log_error(f"Error finding folders in directory {dir}: {e}")
        return []
