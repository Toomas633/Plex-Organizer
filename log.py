"""
Logging utilities for Plex Organizer.

Provides functions to log messages, errors, and duplicate file events to a log file.
"""

import os
from datetime import datetime
from config import (
    get_clear_log,
    get_log_file,
    get_enable_logging,
    get_timestamped_log_files,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


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

        if get_timestamped_log_files():
            base, ext = os.path.splitext(log_filename)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_filename = f"{base}.{timestamp}{ext}"

        log_path = os.path.join(SCRIPT_DIR, log_filename)
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


def check_clear_log():
    """
    Clears the log file if config value set to true by truncating it.

    Returns:
        None
    """
    if get_clear_log() and get_enable_logging() and not get_timestamped_log_files():
        with open(
            os.path.join(SCRIPT_DIR, get_log_file()), "w", encoding="utf-8"
        ) as log_file:
            log_file.truncate(0)
