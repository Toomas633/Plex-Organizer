import os
import configparser

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.ini")

config = configparser.ConfigParser()
config.read(CONFIG_PATH)


def get_host():
    return config.get("qBittorrent", "host")


def get_delete_duplicates():
    return config.getboolean("Settings", "delete_duplicates")


def get_include_quality():
    return config.getboolean("Settings", "include_quality")
