"""Constants for Plex Organizer.

This module defines file extensions and folder names used for filtering
and organizing media files.
"""

from typing import Dict
from re import compile as re_compile

VIDEO_EXTENSIONS = (".mkv", ".mp4")

TEXT_SUBTITLE_EXTENSIONS = (".srt", ".vtt", ".ass", ".ssa")

SUBTITLE_EXTENSIONS = TEXT_SUBTITLE_EXTENSIONS + (
    ".sub",
    ".idx",
)

EXT_FILTER = VIDEO_EXTENSIONS + (".!qB", ".index")

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

ISO639_1_TO_2: Dict[str, str] = {
    "aa": "aar",
    "ab": "abk",
    "af": "afr",
    "ar": "ara",
    "az": "aze",
    "be": "bel",
    "bg": "bul",
    "bn": "ben",
    "bs": "bos",
    "ca": "cat",
    "cs": "ces",
    "cy": "cym",
    "da": "dan",
    "de": "deu",
    "el": "ell",
    "en": "eng",
    "es": "spa",
    "et": "est",
    "eu": "eus",
    "fa": "fas",
    "fi": "fin",
    "fr": "fra",
    "ga": "gle",
    "gl": "glg",
    "gu": "guj",
    "he": "heb",
    "hi": "hin",
    "hr": "hrv",
    "hu": "hun",
    "hy": "hye",
    "id": "ind",
    "is": "isl",
    "it": "ita",
    "ja": "jpn",
    "jv": "jav",
    "ka": "kat",
    "kk": "kaz",
    "km": "khm",
    "kn": "kan",
    "ko": "kor",
    "lt": "lit",
    "lv": "lav",
    "mk": "mkd",
    "ml": "mal",
    "mr": "mar",
    "ms": "msa",
    "my": "mya",
    "ne": "nep",
    "nl": "nld",
    "no": "nor",
    "pa": "pan",
    "pl": "pol",
    "pt": "por",
    "ro": "ron",
    "ru": "rus",
    "sk": "slk",
    "sl": "slv",
    "sq": "sqi",
    "sr": "srp",
    "sv": "swe",
    "sw": "swa",
    "ta": "tam",
    "te": "tel",
    "th": "tha",
    "tl": "tgl",
    "tr": "tur",
    "uk": "ukr",
    "ur": "urd",
    "vi": "vie",
    "zh": "zho",
}

INDEX_FILENAME = ".plex_organizer.index"

MOVIE_CORRECT_NAME_RE = re_compile(r"^.+ \(\d{4}\)(?: \d{3,4}p)?\.[\w]+$", flags=0)
TV_CORRECT_NAME_RE = re_compile(r"^.+ S(\d{2})E(\d{2})(?: \d{3,4}p)?\.[\w]+$", flags=0)
TV_CORRECT_SEASON_RE = re_compile(r"^Season (\d{2})$", flags=0)
