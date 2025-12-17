"""
This module provides functions to access settings from the config.ini file.
"""

from os import path as os_path
from configparser import ConfigParser

CONFIG_PATH = os_path.join(os_path.dirname(__file__), "config.ini")


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
            "capitalize": "true",
            "cpu_threads": "2",
        },
        "Logging": {
            "enable_logging": "true",
            "log_file": "qbittorrent.log",
            "clear_log": "false",
            "timestamped_log_files": "false",
        },
        "Audio": {
            "enable_audio_tagging": "true",
            "whisper_model_size": "tiny",
        },
        "Subtitles": {
            "enable_subtitle_embedding": "true",
        },
    }

    if os_path.exists(CONFIG_PATH):
        _check_config(default_config)
    else:
        _create_config(default_config)


def _check_config(default_config: dict):
    """
    Check for missing sections/options in config.ini and add them if needed,
    preserving user edits.

    Args:
        default_config (dict): The default configuration with required sections and options.
    """
    config = _get_config()
    changed = False
    for section, options in default_config.items():
        if not config.has_section(section):
            config.add_section(section)
            changed = True
        existing_options = (
            set(config.options(section)) if config.has_section(section) else set()
        )
        default_options = set(options.keys())
        for opt in existing_options - default_options:
            config.remove_option(section, opt)
            changed = True
        for key, value in options.items():
            if not config.has_option(section, key):
                config.set(section, key, value)
                changed = True
    if changed:
        with open(CONFIG_PATH, "w", encoding="utf-8") as configfile:
            config.write(configfile)


def _create_config(default_config: dict):
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


def _get_config():
    """Return a ConfigParser object loaded with config.ini."""
    config = ConfigParser()
    config.read(CONFIG_PATH)
    return config


def get_host():
    """Return the qBittorrent host from the config file."""
    config = _get_config()
    return config.get("qBittorrent", "host")


def get_delete_duplicates():
    """Return True if duplicate deletion is enabled in settings."""
    config = _get_config()
    return config.getboolean("Settings", "delete_duplicates", fallback=False)


def get_include_quality():
    """Return True if quality should be included in settings."""
    config = _get_config()
    return config.getboolean("Settings", "include_quality", fallback=True)


def get_capitalize():
    """Return True if file names should be capitalized."""
    config = _get_config()
    return config.getboolean("Settings", "capitalize", fallback=True)


def get_enable_logging():
    """Return True if logging is enabled."""
    config = _get_config()
    return config.getboolean("Logging", "enable_logging", fallback=True)


def get_log_file():
    """Return the log file path."""
    config = _get_config()
    return config.get("Logging", "log_file", fallback="qbittorrent.log")


def get_clear_log():
    """Return True if the log should be cleared on startup."""
    config = _get_config()
    return config.getboolean("Logging", "clear_log", fallback=False)


def get_timestamped_log_files():
    """Return True if log files should be timestamped."""
    config = _get_config()
    return config.getboolean("Logging", "timestamped_log_files", fallback=False)


def get_whisper_model_size():
    """Return the Whisper model size from the config file."""
    config = _get_config()
    return config.get("Audio", "whisper_model_size", fallback="tiny")


def get_enable_audio_tagging():
    """Return True if audio tagging is enabled."""
    config = _get_config()
    return config.getboolean("Audio", "enable_audio_tagging", fallback=True)


def get_enable_subtitle_embedding():
    """Return True if subtitle embedding is enabled."""
    config = _get_config()
    return config.getboolean("Subtitles", "enable_subtitle_embedding", fallback=True)


def get_cpu_threads():
    """Return the number of CPU threads to use from settings."""
    config = _get_config()
    return config.getint("Settings", "cpu_threads", fallback=2)
