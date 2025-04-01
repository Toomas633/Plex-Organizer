import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = "qb_organizer.log"


def log_message(level, message):
    with open(os.path.join(SCRIPT_DIR, LOG_PATH), "a") as log_file:
        log_file.write(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - [{level}] - {message}\n"
        )


def log_error(message):
    log_message("ERROR", message)


def log_duplicate(message):
    log_message("DUPLICATE", message)
