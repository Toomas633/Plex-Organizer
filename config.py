"""
This module provides functions to access settings from the config.ini file.
"""

import os
import configparser

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.ini")


def ensure_config_exists():
    """
    Create a default config.ini if it does not exist, or add missing sections/options,
    preserving user edits.
    """
    default_config = {
        "qBittorrent": {"host": "http://localhost:8081"},
        "Settings": {
            "delete_duplicates": "false",
            "include_quality": "true",
            "clear_log": "false",
        },
    }

    if os.path.exists(CONFIG_PATH):
        check_config(default_config)
    else:
        create_config(default_config)


def check_config(default_config: dict):
    """
    Check for missing sections/options in config.ini and add them if needed,
    preserving user edits.

    Args:
        default_config (dict): The default configuration with required sections and options.
    """
    config = get_config()
    changed = False
    for section, options in default_config.items():
        if not config.has_section(section):
            config.add_section(section)
            changed = True
        for key, value in options.items():
            if not config.has_option(section, key):
                config.set(section, key, value)
                changed = True
    if changed:
        with open(CONFIG_PATH, "w", encoding="utf-8") as configfile:
            config.write(configfile)


def create_config(default_config: dict):
    """
    Create a new config.ini file with all default sections and options.

    Args:
        default_config (dict): The default configuration to write.
    """
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        for section, options in default_config.items():
            f.write(f"[{section}]\n")
            for key, value in options.items():
                f.write(f"{key} = {value}\n")
            f.write("\n")


def get_config():
    """Return a ConfigParser object loaded with config.ini."""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config


def get_host():
    """Return the qBittorrent host from the config file."""
    config = get_config()
    return config.get("qBittorrent", "host")


def get_delete_duplicates():
    """Return True if duplicate deletion is enabled in settings."""
    config = get_config()
    return config.getboolean("Settings", "delete_duplicates")


def get_include_quality():
    """Return True if quality should be included in settings."""
    config = get_config()
    return config.getboolean("Settings", "include_quality")


def get_clear_log():
    """Return True if the log should be cleared on startup."""
    config = get_config()
    return config.getboolean("Settings", "clear_log")
