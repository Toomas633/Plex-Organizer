"""
Logging utilities for Plex Organizer.

Provides functions to log messages, errors, and duplicate file events to a log file.
"""

import os
from datetime import datetime
from config import get_clear_log

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = "log.log"


def log_message(level: str, message: str):
    """
    Writes a log message with a specified level to the log file.

    Args:
        level (str): The log level (e.g., "ERROR", "DUPLICATE").
        message (str): The message to log.

    Returns:
        None
    """
    with open(os.path.join(SCRIPT_DIR, LOG_PATH), "a", encoding="utf-8") as log_file:
        log_file.write(
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
    log_message("ERROR", message)


def log_duplicate(message: str):
    """
    Logs a duplicate file message to the log file.

    Args:
        message (str): The duplicate file message to log.

    Returns:
        None
    """
    log_message("DUPLICATE", message)


def check_clear_log():
    """
    Clears the log file if config value set to true by truncating it.

    Returns:
        None
    """
    if get_clear_log():
        with open(
            os.path.join(SCRIPT_DIR, LOG_PATH), "w", encoding="utf-8"
        ) as log_file:
            log_file.truncate(0)
