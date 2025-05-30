import os
import configparser

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.ini")

config = configparser.ConfigParser()
config.read(CONFIG_PATH)


def get_host():
    return config.get("qBittorrent", "host")
