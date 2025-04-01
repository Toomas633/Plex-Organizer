from requests import post
from log import log_error
import sys

HOST = "http://localhost:8081"


def remove_torrent(torrent_hash):
    response = post(
        f"{HOST}/api/v2/torrents/delete",
        data={"hashes": torrent_hash, "deleteFiles": "false"},
    )

    if response.status_code != 200:
        log_error(f"Error deleting torrent '{torrent_hash}': {response.text}")
        sys.exit(1)
