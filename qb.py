"""
This module provides functions to interact with the qBittorrent Web API,
including removing torrents by hash and logging errors if removal fails.
"""

from requests import Session
from log import log_debug, log_error
from config import get_host, get_qbittorrent_password, get_qbittorrent_username


def _authenticate_session(session: Session) -> bool:
    """
    Authenticates a session with the qBittorrent Web API.

    Args:
        session (Session): The requests Session object to authenticate.

    Returns:
        bool: True if authentication was successful, False otherwise.
    """
    username = get_qbittorrent_username()
    password = get_qbittorrent_password()

    log_debug(
        f"Authenticating with qBittorrent Web API. Username: {username} Password set: {password}"
    )

    if not password or not username:
        log_error("qBittorrent username or password not set in config.")
        return False

    login_url = f"{get_host()}/api/v2/auth/login"
    login_data = {"username": username, "password": password}
    login_response = session.post(login_url, data=login_data, timeout=10)

    log_debug(f"qBittorrent login response: {login_response}")

    if login_response.status_code != 200 or login_response.text != "Ok.":
        log_error(f"qBittorrent login failed: {login_response}")
        return False

    return True


def remove_torrent(torrent_hash: str):
    """
    Removes a torrent from qBittorrent using its hash.

    Sends a POST request to the qBittorrent Web API to delete the torrent.
    If the request fails, logs an error and exits the script.

    Args:
        torrent_hash (str): The hash of the torrent to remove.

    Returns:
        None
    """
    log_debug(f"Attempting to remove torrent with hash: {torrent_hash}")

    session = Session()
    try:
        if not _authenticate_session(session):
            return

        response = session.post(
            f"{get_host()}/api/v2/torrents/delete",
            data={"hashes": torrent_hash, "deleteFiles": "false"},
            timeout=10,
        )

        log_debug(f"qBittorrent response: {response}")

        if response.status_code != 200:
            log_error(f"Error deleting torrent '{torrent_hash}': {response.text}")
    finally:
        session.close()
