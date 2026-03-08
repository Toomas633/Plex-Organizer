"""
Logging utilities for Plex Organizer.

Provides functions to log messages, errors, and duplicate file events to a log file.
"""

from os import makedirs
from os.path import join, splitext, exists
from datetime import datetime
from .config import (
    get_clear_log,
    get_log_file,
    get_enable_logging,
    get_logging_level,
    get_timestamped_log_files,
)
from ._paths import data_dir

SCRIPT_DIR = data_dir()


def _log_message(level: str, message: str):
    """
    Writes a log message with a specified level to the log file.

    Args:
        level (str): The log level (e.g., "ERROR", "DUPLICATE").
        message (str): The message to log.

    Returns:
        None
    """
    if get_enable_logging():
        log_filename = get_log_file()

        log_path = join(SCRIPT_DIR, log_filename)
        if get_timestamped_log_files():
            log_dir = join(SCRIPT_DIR, "logs")

            if not exists(log_dir):
                makedirs(log_dir, exist_ok=True)

            base, ext = splitext(log_filename)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_filename = f"{base}.{timestamp}{ext}"
            log_path = join(log_dir, log_filename)

        with open(log_path, "a", encoding="utf-8") as log_file_obj:
            log_file_obj.write(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - [{level}] - {message}\n"
            )


def log_error(message: str):
    """
    Logs an error message to the log file.

    Args:
        message (str): The error message to log.

    Returns:
        None
    """
    _log_message("ERROR", message)


def log_duplicate(message: str):
    """
    Logs a duplicate file message to the log file.

    Args:
        message (str): The duplicate file message to log.

    Returns:
        None
    """
    _log_message("DUPLICATE", message)


def log_debug(message: str):
    """
    Logs a debug message to the log file.

    Args:
        message (str): The debug message to log.

    Returns:
        None
    """
    if get_logging_level().upper() == "DEBUG":
        _log_message("DEBUG", message)


def check_clear_log():
    """
    Clears the log file if config value set to true by truncating it.

    Returns:
        None
    """
    if get_clear_log() and get_enable_logging() and not get_timestamped_log_files():
        with open(join(SCRIPT_DIR, get_log_file()), "w", encoding="utf-8") as log_file:
            log_file.truncate(0)
