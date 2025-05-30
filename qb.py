"""
This module provides functions to interact with the qBittorrent Web API,
including removing torrents by hash and logging errors if removal fails.
"""

import sys
from requests import post
from log import log_error
from config import get_host


def remove_torrent(torrent_hash):
    """
    Removes a torrent from qBittorrent using its hash.

    Sends a POST request to the qBittorrent Web API to delete the torrent.
    If the request fails, logs an error and exits the script.

    Args:
        torrent_hash (str): The hash of the torrent to remove.

    Returns:
        None
    """
    response = post(
        f"{get_host()}/api/v2/torrents/delete",
        data={"hashes": torrent_hash, "deleteFiles": "false"},
        timeout=10,
    )

    if response.status_code != 200:
        log_error(f"Error deleting torrent '{torrent_hash}': {response.text}")
        sys.exit(1)
