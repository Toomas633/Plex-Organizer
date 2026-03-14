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


def main():
    """CLI entrypoint.

    Validates args, ensures config/logs exist, optionally removes a torrent from
    qBittorrent, then processes either a main folder or a single directory.
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

    if not args.start_dir:
        parser.error("start_dir is required when not using --manage")

    from .organizer import main as organize  # pylint: disable=import-outside-toplevel

    organize(args.start_dir, args.torrent_hash)


if __name__ == "__main__":
    main()
