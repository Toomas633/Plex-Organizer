"""Tests for plex_organizer.dataclass."""

# pylint: disable=duplicate-code

from pytest import raises

from plex_organizer.dataclass import (
    AudioStream,
    IndexEntry,
    IndexSummary,
    SubtitleMergePlan,
)


class TestAudioStream:
    """Tests for the AudioStream dataclass."""

    def test_creation(self):
        """Verify all AudioStream fields are correctly assigned."""
        stream = AudioStream(
            audio_index=0,
            ffprobe_index=1,
            codec_name="aac",
            channels=2,
            sample_rate=48000,
            language="eng",
            title="English",
        )
        assert stream.audio_index == 0
        assert stream.ffprobe_index == 1
        assert stream.codec_name == "aac"
        assert stream.channels == 2
        assert stream.sample_rate == 48000
        assert stream.language == "eng"
        assert stream.title == "English"

    def test_frozen(self):
        """Verify AudioStream is immutable."""
        stream = AudioStream(0, 1, "aac", 2, 48000, "eng", "English")

        with raises(AttributeError):
            stream.language = "spa"  # type: ignore[misc]

    def test_optional_fields(self):
        """Verify optional fields accept None."""
        stream = AudioStream(0, 1, None, None, None, None, None)
        assert stream.codec_name is None
        assert stream.language is None


class TestSubtitleMergePlan:
    """Tests for the SubtitleMergePlan dataclass."""

    def test_creation(self):
        """Verify SubtitleMergePlan fields are correctly assigned."""
        plan = SubtitleMergePlan(
            video_path="/media/video.mkv",
            subtitle_paths=("/media/sub1.srt", "/media/sub2.srt"),
        )
        assert plan.video_path == "/media/video.mkv"
        assert len(plan.subtitle_paths) == 2

    def test_frozen(self):
        """Verify SubtitleMergePlan is immutable."""
        plan = SubtitleMergePlan("/video.mkv", ())

        with raises(AttributeError):
            plan.video_path = "/other.mkv"  # type: ignore[misc]


class TestIndexEntry:
    """Tests for the IndexEntry dataclass."""

    def test_creation(self):
        """Verify IndexEntry stores the processed timestamp."""
        entry = IndexEntry(processed_at="2025-01-01T00:00:00+00:00")
        assert entry.processed_at == "2025-01-01T00:00:00+00:00"

    def test_dict_conversion(self):
        """Verify IndexEntry converts to a dict correctly."""
        entry = IndexEntry(processed_at="2025-01-01T00:00:00+00:00")
        d = entry.__dict__
        assert d == {"processed_at": "2025-01-01T00:00:00+00:00"}


class TestIndexSummary:  # pylint: disable=too-few-public-methods
    """Tests for the IndexSummary dataclass."""

    def test_creation(self):
        """Verify IndexSummary fields are correctly assigned."""
        summary = IndexSummary(total_videos=10, eligible_videos=8, newly_indexed=5)
        assert summary.total_videos == 10
        assert summary.eligible_videos == 8
        assert summary.newly_indexed == 5
