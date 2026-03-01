"""Tests for plex_organizer.audio.tagging."""

from unittest.mock import MagicMock, patch

from pytest import mark, raises

from plex_organizer.audio.tagging import (
    _audio_stream_from_ffprobe,
    _choose_language_from_samples,
    _detect_languages_for_streams,
    _extract_audio_sample,
    _get_content_aware_offsets,
    _normalize_language_to_iso639_2,
    _pick_offsets,
    _probe_audio_streams,
    _sample_track_languages,
    _sampling_params_for_duration,
    _should_update_language,
    _apply_language_metadata,
    tag_audio_track_languages,
)
from plex_organizer.dataclass import AudioStream


class TestAudioStreamFromFfprobe:
    """Tests for converting ffprobe JSON to AudioStream."""

    def test_full_stream(self):
        """Parses a fully-populated stream dict."""
        stream = {
            "index": 1,
            "codec_name": "aac",
            "channels": 6,
            "sample_rate": "48000",
            "tags": {"language": "eng", "title": "Surround"},
        }
        result = _audio_stream_from_ffprobe(0, stream)
        assert result.audio_index == 0
        assert result.ffprobe_index == 1
        assert result.codec_name == "aac"
        assert result.channels == 6
        assert result.sample_rate == 48000
        assert result.language == "eng"
        assert result.title == "Surround"

    def test_minimal_stream(self):
        """Parses a stream dict with minimal fields."""
        result = _audio_stream_from_ffprobe(0, {})
        assert result.ffprobe_index == -1
        assert result.codec_name is None
        assert result.channels is None
        assert result.sample_rate is None
        assert result.language is None

    def test_invalid_sample_rate(self):
        """Non-numeric sample_rate yields None."""
        result = _audio_stream_from_ffprobe(0, {"sample_rate": "N/A"})
        assert result.sample_rate is None


@mark.usefixtures("default_config")
class TestProbeAudioStreams:
    """Tests for _probe_audio_streams."""

    def test_file_not_found_raises(self, tmp_path):
        """Raises FileNotFoundError if path doesn't exist."""
        with raises(FileNotFoundError):
            _probe_audio_streams(str(tmp_path / "nope.mkv"))

    @patch("plex_organizer.audio.tagging.probe_streams_json", return_value=[])
    @patch("plex_organizer.audio.tagging.get_ffprobe", return_value="/usr/bin/ffprobe")
    def test_returns_empty_on_no_streams(self, _ffp, _probe, tmp_path):
        """Returns empty list when no audio streams found."""
        video = tmp_path / "v.mkv"
        video.write_text("x")
        assert _probe_audio_streams(str(video)) == []

    @patch("plex_organizer.audio.tagging.probe_streams_json")
    def test_parses_streams(self, mock_probe, tmp_path):
        """Returns AudioStream objects for each stream dict."""
        mock_probe.return_value = [
            {"index": 1, "codec_name": "aac", "tags": {"language": "eng"}},
        ]
        video = tmp_path / "v.mkv"
        video.write_text("x")
        result = _probe_audio_streams(str(video))
        assert len(result) == 1
        assert result[0].codec_name == "aac"


class TestSamplingParamsForDuration:
    """Tests for _sampling_params_for_duration."""

    def test_short_duration(self):
        """Short videos use less intro skip."""
        skip, fracs = _sampling_params_for_duration(1800)
        assert skip == 120
        assert len(fracs) == 3

    def test_medium_duration(self):
        """Medium videos use moderate skip."""
        skip, fracs = _sampling_params_for_duration(3000)
        assert skip == 300
        assert len(fracs) == 3

    def test_long_duration(self):
        """Long videos use more intro skip."""
        skip, fracs = _sampling_params_for_duration(6000)
        assert skip == 720
        assert len(fracs) == 3


class TestPickOffsets:
    """Tests for _pick_offsets."""

    def test_returns_up_to_three(self):
        """Returns up to 3 de-duplicated offsets."""
        result = _pick_offsets(3600.0, 120, 3200, [0.25, 0.55, 0.80])
        assert len(result) <= 3

    def test_deduplication(self):
        """Duplicate offsets are removed and backfilled."""
        result = _pick_offsets(100.0, 0, 100, [0.5, 0.5, 0.5])
        assert len(set(result)) == len(result)


class TestGetContentAwareOffsets:
    """Tests for _get_content_aware_offsets."""

    def test_returns_offsets_for_normal_duration(self):
        """Returns a list of offsets for standard movie duration."""
        result = _get_content_aware_offsets(7200.0)
        assert result is not None
        assert len(result) <= 3

    def test_returns_none_for_none(self):
        """Returns None when duration is None."""
        assert _get_content_aware_offsets(None) is None

    def test_returns_none_for_zero(self):
        """Returns None when duration is zero."""
        assert _get_content_aware_offsets(0.0) is None

    def test_returns_none_for_negative(self):
        """Returns None when duration is negative."""
        assert _get_content_aware_offsets(-100.0) is None

    def test_returns_none_for_very_short(self):
        """Returns None when duration is too short for usable end."""
        assert _get_content_aware_offsets(200.0) is None

    def test_returns_none_for_non_numeric_string(self):
        """Returns None when duration is a non-numeric string (TypeError/ValueError)."""
        assert _get_content_aware_offsets("not_a_number") is None

    def test_returns_none_when_max_start_le_min_start(self):
        """Returns None when duration makes max_start <= min_start."""
        assert _get_content_aware_offsets(350.0) is None


class TestNormalizeLanguage:
    """Tests for _normalize_language_to_iso639_2."""

    def test_three_letter_code(self):
        """Three-letter code passes through."""
        assert _normalize_language_to_iso639_2("eng") == "eng"

    def test_two_letter_mapped(self):
        """Two-letter code is mapped to three-letter."""
        assert _normalize_language_to_iso639_2("en") == "eng"

    def test_none_returns_none(self):
        """None input returns None."""
        assert _normalize_language_to_iso639_2(None) is None

    def test_und_returns_none(self):
        """'und' returns None."""
        assert _normalize_language_to_iso639_2("und") is None

    def test_unknown_returns_none(self):
        """'unknown' returns None."""
        assert _normalize_language_to_iso639_2("unknown") is None

    def test_empty_returns_none(self):
        """Empty string returns None."""
        assert _normalize_language_to_iso639_2("") is None

    def test_unmapped_two_letter_returns_none(self):
        """Unmapped two-letter code returns None."""
        assert _normalize_language_to_iso639_2("zz") is None

    def test_single_letter_returns_none(self):
        """Single character returns None."""
        assert _normalize_language_to_iso639_2("e") is None


class TestShouldUpdateLanguage:
    """Tests for _should_update_language."""

    def test_none_needs_update(self):
        """None language needs update."""
        assert _should_update_language(None) is True

    def test_und_needs_update(self):
        """'und' language needs update."""
        assert _should_update_language("und") is True

    def test_valid_language_no_update(self):
        """Valid language code does not need update."""
        assert _should_update_language("eng") is False


@mark.usefixtures("default_config")
class TestExtractAudioSample:
    """Tests for _extract_audio_sample."""

    @patch("plex_organizer.audio.tagging.run_cmd")
    @patch("plex_organizer.audio.tagging.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_success(self, _ff, mock_run):
        """No exception raised on success."""
        mock_run.return_value = MagicMock(returncode=0)
        _extract_audio_sample("/v.mkv", 0, "/tmp/a.wav", start_seconds=30)

    @patch("plex_organizer.audio.tagging.run_cmd")
    @patch("plex_organizer.audio.tagging.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_failure_raises(self, _ff, mock_run):
        """RuntimeError raised on ffmpeg failure."""
        mock_run.return_value = MagicMock(returncode=1, stderr="fail")
        with raises(RuntimeError):
            _extract_audio_sample("/v.mkv", 0, "/tmp/a.wav")


class TestChooseLanguageFromSamples:
    """Tests for _choose_language_from_samples."""

    def test_majority_wins(self):
        """Language with most votes wins."""
        samples: list[tuple[str | None, float]] = [
            ("eng", 0.9),
            ("eng", 0.8),
            ("spa", 0.7),
        ]
        lang, _ = _choose_language_from_samples(samples)
        assert lang == "eng"

    def test_single_high_confidence(self):
        """Single sample with high confidence is accepted."""
        samples: list[tuple[str | None, float]] = [("eng", 0.85)]
        lang, _ = _choose_language_from_samples(samples)
        assert lang == "eng"

    def test_single_low_confidence_rejected(self):
        """Single sample with low confidence returns None."""
        samples: list[tuple[str | None, float]] = [("eng", 0.3)]
        lang, _ = _choose_language_from_samples(samples)
        assert lang is None

    def test_all_none_samples(self):
        """All None samples return None."""
        lang, _ = _choose_language_from_samples([(None, 0.1), (None, 0.2)])
        assert lang is None

    def test_tie_break_by_confidence_sum(self):
        """Tie-break resolved by highest sum of confidences."""
        samples: list[tuple[str | None, float]] = [("eng", 0.9), ("spa", 0.5)]
        lang, conf = _choose_language_from_samples(samples)
        assert lang is None or conf > 0


@mark.usefixtures("default_config")
class TestSampleTrackLanguages:  # pylint: disable=too-few-public-methods
    """Tests for _sample_track_languages."""

    @patch("plex_organizer.audio.tagging.WhisperDetector")
    @patch("plex_organizer.audio.tagging._extract_audio_sample")
    def test_returns_samples(self, _mock_extract, mock_whisper_cls, tmp_path):
        """Returns one detection per offset."""
        mock_detector = MagicMock()
        mock_detector.detect_language.return_value = ("en", 0.9)
        mock_whisper_cls.return_value = mock_detector

        stream = AudioStream(
            audio_index=0,
            ffprobe_index=1,
            codec_name="aac",
            channels=2,
            sample_rate=48000,
            language=None,
            title=None,
        )
        result = _sample_track_languages(
            "/v.mkv", stream, [30, 120, 240], str(tmp_path)
        )
        assert len(result) == 3
        assert result[0][0] == "eng"


@mark.usefixtures("default_config")
class TestDetectLanguagesForStreams:
    """Tests for _detect_languages_for_streams."""

    @patch("plex_organizer.audio.tagging._sample_track_languages")
    @patch("plex_organizer.audio.tagging.probe_duration_seconds", return_value=7200.0)
    def test_detects_missing_language(self, _dur, mock_samples):
        """Streams with missing language are sampled and detected."""
        mock_samples.return_value = [("eng", 0.9), ("eng", 0.85), ("eng", 0.8)]
        stream = AudioStream(0, 1, "aac", 2, 48000, None, None)
        result = _detect_languages_for_streams("/v.mkv", [stream])
        assert len(result) == 1
        assert result[0][1] == "eng"

    @patch("plex_organizer.audio.tagging._sample_track_languages")
    @patch("plex_organizer.audio.tagging.probe_duration_seconds", return_value=7200.0)
    def test_keeps_existing_language(self, _dur, mock_samples):
        """Streams with existing valid language are not re-detected."""
        stream = AudioStream(0, 1, "aac", 2, 48000, "spa", None)
        result = _detect_languages_for_streams("/v.mkv", [stream])
        assert result[0][1] == "spa"
        mock_samples.assert_not_called()

    @patch("plex_organizer.audio.tagging._sample_track_languages")
    @patch("plex_organizer.audio.tagging.probe_duration_seconds", return_value=None)
    def test_uses_default_offsets_when_duration_unavailable(self, _dur, mock_samples):
        """Falls back to default offsets when duration is None."""
        mock_samples.return_value = [("eng", 0.9), ("eng", 0.85), ("eng", 0.8)]
        stream = AudioStream(0, 1, "aac", 2, 48000, None, None)
        _detect_languages_for_streams("/v.mkv", [stream])
        offsets = mock_samples.call_args[0][2]
        assert offsets == [30, 150, 270]


@mark.usefixtures("default_config")
class TestApplyLanguageMetadata:
    """Tests for _apply_language_metadata."""

    @patch("plex_organizer.audio.tagging.replace_and_restore_timestamps")
    @patch("plex_organizer.audio.tagging.run_cmd")
    @patch(
        "plex_organizer.audio.tagging.build_ffmpeg_base_cmd", return_value=["ffmpeg"]
    )
    @patch("plex_organizer.audio.tagging.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_writes_language_tags(self, _ff, _base, mock_run, mock_replace):
        """Runs ffmpeg to write language metadata."""
        mock_run.return_value = MagicMock(returncode=0)
        stream = AudioStream(0, 1, "aac", 2, 48000, None, None)
        _apply_language_metadata("/v.mkv", [(stream, "eng", 0.9)])
        mock_run.assert_called_once()
        mock_replace.assert_called_once()

    @patch("plex_organizer.audio.tagging.run_cmd")
    @patch(
        "plex_organizer.audio.tagging.build_ffmpeg_base_cmd", return_value=["ffmpeg"]
    )
    @patch("plex_organizer.audio.tagging.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_raises_on_ffmpeg_failure(self, _ff, _base, mock_run):
        """Raises RuntimeError when ffmpeg fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        stream = AudioStream(0, 1, "aac", 2, 48000, None, None)
        with raises(RuntimeError):
            _apply_language_metadata("/v.mkv", [(stream, "eng", 0.9)])

    def test_noop_when_no_languages(self):
        """Does nothing when no language was detected."""
        stream = AudioStream(0, 1, "aac", 2, 48000, None, None)
        _apply_language_metadata("/v.mkv", [(stream, None, 0.0)])

    @patch("plex_organizer.audio.tagging.replace_and_restore_timestamps")
    @patch("plex_organizer.audio.tagging.run_cmd")
    @patch(
        "plex_organizer.audio.tagging.build_ffmpeg_base_cmd", return_value=["ffmpeg"]
    )
    @patch("plex_organizer.audio.tagging.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_skips_none_lang_in_loop(self, _ff, _base, mock_run, _mock_replace):
        """Detection with some None lang still writes only the non-None ones."""
        mock_run.return_value = MagicMock(returncode=0)
        s1 = AudioStream(0, 1, "aac", 2, 48000, None, None)
        s2 = AudioStream(1, 2, "aac", 2, 48000, None, None)
        _apply_language_metadata("/v.mkv", [(s1, "eng", 0.9), (s2, None, 0.0)])


@mark.usefixtures("default_config")
class TestTagAudioTrackLanguages:
    """Tests for the public tag_audio_track_languages."""

    def test_skips_plex_folder(self):
        """Plex-managed folders are skipped."""
        tag_audio_track_languages("/media/Plex Versions/v.mkv")

    @patch("plex_organizer.audio.tagging._apply_language_metadata")
    @patch("plex_organizer.audio.tagging._detect_languages_for_streams")
    @patch("plex_organizer.audio.tagging._probe_audio_streams", return_value=[])
    @patch("plex_organizer.audio.tagging.log_debug")
    def test_returns_when_no_streams(self, _log, _probe, _detect, _apply):
        """Returns early when no audio streams are found."""
        tag_audio_track_languages("/video.mkv")
        _detect.assert_not_called()

    @patch("plex_organizer.audio.tagging._apply_language_metadata")
    @patch("plex_organizer.audio.tagging._detect_languages_for_streams")
    @patch("plex_organizer.audio.tagging._probe_audio_streams")
    @patch("plex_organizer.audio.tagging.log_debug")
    def test_full_pipeline(self, _log, mock_probe, mock_detect, mock_apply):
        """Full pipeline: probe -> detect -> apply."""
        stream = AudioStream(0, 1, "aac", 2, 48000, None, None)
        mock_probe.return_value = [stream]
        mock_detect.return_value = [(stream, "eng", 0.9)]
        tag_audio_track_languages("/video.mkv")
        mock_apply.assert_called_once()

    @patch("plex_organizer.audio.tagging.log_error")
    @patch(
        "plex_organizer.audio.tagging._probe_audio_streams",
        side_effect=RuntimeError("fail"),
    )
    @patch("plex_organizer.audio.tagging.log_debug")
    def test_error_logged_not_raised(self, _log, _probe, mock_err):
        """Errors are caught and logged."""
        tag_audio_track_languages("/video.mkv")
        mock_err.assert_called_once()
