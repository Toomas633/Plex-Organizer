"""Constants for Plex Organizer.

This module defines file extensions and folder names used for filtering
and organizing media files.
"""

INC_FILTER = (".mkv", ".mp4")

EXT_FILTER = INC_FILTER + (".!qB",)

UNWANTED_FOLDERS = {
    "Plex Versions",
    "Extras",
    "Sample",
    "Samples",
    "Subs",
    "Subtitles",
    "Proof",
    "Screenshots",
    "Artwork",
    "Cover",
    "Covers",
    "Poster",
}
