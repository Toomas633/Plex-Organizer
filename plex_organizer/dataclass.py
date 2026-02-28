"""Shared dataclasses used across Plex Organizer modules.

These objects are intentionally lightweight containers for metadata extracted from
media files (via tools like ffprobe/ffmpeg) and for describing planned operations.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class AudioStream:
    """Represents a single audio stream in a media file.

    Attributes:
        audio_index: The organizer's 0-based index for the audio stream among audio
            streams (i.e., counting only audio streams).
        ffprobe_index: The stream index as reported by ffprobe (typically the global
            stream index in the container, e.g., 0=video, 1=audio, 2=subtitles).
        codec_name: Codec short name reported by ffprobe (e.g., ``aac``, ``eac3``).
        channels: Number of audio channels, if known.
        sample_rate: Audio sample rate in Hz, if known.
        language: ISO language tag (e.g., ``eng``), if present in metadata.
        title: Track title, if present in metadata.
    """

    audio_index: int
    ffprobe_index: int
    codec_name: Optional[str]
    channels: Optional[int]
    sample_rate: Optional[int]
    language: Optional[str]
    title: Optional[str]


@dataclass(frozen=True)
class SubtitleMergePlan:
    """A plan describing which subtitle files to embed into a single video.

    Attributes:
        video_path: Absolute or relative path to the target video file.
        subtitle_paths: Paths to subtitle files to be embedded (in input order).
    """

    video_path: str
    subtitle_paths: Tuple[str, ...]


@dataclass(frozen=True)
class IndexEntry:
    """Metadata recorded when a media file is marked as processed.

    Attributes:
        processed_at: UTC timestamp (ISO 8601) when the file was processed.
    """

    processed_at: str


@dataclass(frozen=True)
class IndexSummary:
    """Summary of an indexing run.

    Attributes:
        total_videos: Number of video files encountered.
        eligible_videos: Number of videos that were already in correct place/name.
        newly_indexed: Number of eligible videos newly written to index files.
    """

    total_videos: int
    eligible_videos: int
    newly_indexed: int
