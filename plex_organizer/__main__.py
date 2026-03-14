"""Plex media organizer entrypoint.

This script walks a target directory (either a single torrent save folder, or a “main”
folder containing ``tv/`` and/or ``movies/``), and performs these steps:

- Optionally embeds external subtitles into matching video files.
- Optionally fetches missing subtitles from online providers.
- Optionally synchronizes embedded subtitle timing to the audio track.
- Optionally tags missing/unknown audio stream language metadata.
- Deletes unwanted files and unwanted subfolders (aggressive cleanup).
- Renames and moves video files into their final TV/Movie layout.
- Indexes processed files so they can be skipped on future runs.
- Deletes empty folders.

It can also remove a completed torrent from qBittorrent when a torrent hash is provided.
"""

from os import environ
from warnings import filterwarnings
from logging import getLogger, ERROR
from argparse import ArgumentParser, RawDescriptionHelpFormatter

filterwarnings("ignore", message=".*doesn't match a supported version")
environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
getLogger("huggingface_hub").setLevel(ERROR)


def _detect_arr_env():
    """Detect Sonarr/Radarr Custom Script environment variables.

    Returns:
        tuple: (start_dir, torrent_hash, source) where source is
        ``"sonarr"``, ``"radarr"``, or ``None`` when no env vars found.
    """
    sonarr_event = environ.get("sonarr_eventtype")
    radarr_event = environ.get("radarr_eventtype")

    if sonarr_event:
        if sonarr_event == "Test":
            return None, None, "sonarr_test"
        start_dir = environ.get("sonarr_series_path", "")
        torrent_hash = environ.get("sonarr_download_id")
        return start_dir, torrent_hash, "sonarr"

    if radarr_event:
        if radarr_event == "Test":
            return None, None, "radarr_test"
        start_dir = environ.get("radarr_movie_path", "")
        torrent_hash = environ.get("radarr_download_id")
        return start_dir, torrent_hash, "radarr"

    return None, None, None


def main():
    """CLI entrypoint.

    Validates args, ensures config/logs exist, optionally removes a torrent from
    qBittorrent, then processes either a main folder or a single directory.

    When invoked as a Sonarr/Radarr Custom Script, environment variables are
    detected automatically and take priority over CLI arguments.
    """
    parser = ArgumentParser(
        prog="plex-organizer",
        description="Automated media file organizer for Plex.",
        formatter_class=RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--manage",
        action="store_true",
        help="Launch the interactive management menu (logs, config migration, custom runs)",
    )
    parser.add_argument("start_dir", nargs="?", help="Directory to process")
    parser.add_argument(
        "torrent_hash",
        nargs="?",
        default=None,
        help="Optional torrent hash to remove from qBittorrent",
    )
    args = parser.parse_args()

    if args.manage:
        from .manage import main as manage  # pylint: disable=import-outside-toplevel

        manage()
        return

    arr_dir, arr_hash, source = _detect_arr_env()

    if source in ("sonarr_test", "radarr_test"):
        from .log import log_info  # pylint: disable=import-outside-toplevel

        log_info(f"Received {source.replace('_test', '')} test event — OK")
        return

    start_dir = arr_dir or args.start_dir
    torrent_hash = arr_hash or args.torrent_hash

    if not start_dir:
        parser.error("start_dir is required when not using --manage")

    from .organizer import main as organize  # pylint: disable=import-outside-toplevel

    organize(start_dir, torrent_hash, source=source)


if __name__ == "__main__":
    main()
