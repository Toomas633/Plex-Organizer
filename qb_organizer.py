import os
import sys
from log import log_error
from qb import remove_torrent
import tv
import movie
from plex import is_plex_folder

TORRENT_HASH = sys.argv[1]
START_DIR = sys.argv[2]

TV_DIR = os.path.join(START_DIR, "tv")
MOVIES_DIR = os.path.join(START_DIR, "movies")


def delete_unwanted_files(directory):
    ext_filter = (".mkv", ".!qB", ".mp4")
    for root, _, files in os.walk(directory, topdown=False):
        for file in files:
            if not file.endswith(ext_filter):
                file_path = os.path.join(root, file)
                os.remove(file_path)


def delete_empty_directories(directory):
    for root, dirs, _ in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if not os.listdir(dir_path):
                os.rmdir(dir_path)


def move_directories(directory):
    inc_filter = (".mkv", ".mp4")
    for root, _, files in os.walk(directory, topdown=False):
        for file in files:
            if file.endswith(inc_filter) and not is_plex_folder(root):
                if directory == MOVIES_DIR:
                    movie.move(directory, root, file)
                else:
                    tv.move(directory, root, file)


def rename_files(directory):
    inc_filter = (".mkv", ".mp4")
    for root, _, files in os.walk(directory, topdown=False):
        for file in files:
            if file.endswith(inc_filter) and not is_plex_folder(root):
                if directory == TV_DIR:
                    tv.rename(directory, root, file)
                else:
                    movie.rename(root, file)


def main():
    try:
        if len(sys.argv) < 3:
            log_error("Error: No directory provided.")
            log_error("Usage: qb_delete.py <torrent_hash> <dir> [...]")
            sys.exit(1)

        if TORRENT_HASH != "test":
            remove_torrent(TORRENT_HASH)

        for directory in [MOVIES_DIR, TV_DIR]:
            delete_unwanted_files(directory)
            rename_files(directory)
            move_directories(directory)
            delete_empty_directories(directory)
    except Exception as e:
        log_error(f"Error occured: {e}")


if __name__ == "__main__":
    main()
