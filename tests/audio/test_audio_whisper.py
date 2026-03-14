"""Tests for plex_organizer.audio.whisper."""

from unittest.mock import MagicMock, patch
from pytest import approx, mark, raises

from plex_organizer.audio.whisper import WhisperDetector


@mark.usefixtures("default_config")
class TestWhisperDetectorInit:
    """Tests for WhisperDetector initialization."""

    @patch("plex_organizer.audio.whisper.WhisperModel")
    @patch("plex_organizer.audio.whisper.get_whisper_model_size", return_value="tiny")
    def test_successful_init(self, _model_size, _wm):
        """Backend is set on successful initialization."""
        detector = WhisperDetector()
        assert detector.is_available() is True

    @patch(
        "plex_organizer.audio.whisper.WhisperModel",
        side_effect=OSError("no model"),
    )
    @patch("plex_organizer.audio.whisper.get_whisper_model_size", return_value="tiny")
    def test_oserror_disables_backend(self, _ms, _wm):
        """OSError during init disables the backend."""
        detector = WhisperDetector()
        assert detector.is_available() is False

    @patch(
        "plex_organizer.audio.whisper.WhisperModel",
        side_effect=RuntimeError("fail"),
    )
    @patch("plex_organizer.audio.whisper.get_whisper_model_size", return_value="tiny")
    def test_runtime_error_disables_backend(self, _ms, _wm):
        """RuntimeError during init disables the backend."""
        detector = WhisperDetector()
        assert detector.is_available() is False

    @patch(
        "plex_organizer.audio.whisper.WhisperModel",
        side_effect=ValueError("bad"),
    )
    @patch("plex_organizer.audio.whisper.get_whisper_model_size", return_value="tiny")
    def test_value_error_disables_backend(self, _ms, _wm):
        """ValueError during init disables the backend."""
        detector = WhisperDetector()
        assert detector.is_available() is False

    @patch("plex_organizer.audio.whisper.WhisperModel")
    @patch("plex_organizer.audio.whisper.get_whisper_model_size", return_value="tiny")
    def test_cpu_threads_passed(self, _ms, mock_wm):
        """cpu_threads kwarg is passed to WhisperModel."""
        WhisperDetector(cpu_threads=4)
        kwargs = mock_wm.call_args[1]
        assert kwargs["cpu_threads"] == 4


@mark.usefixtures("default_config")
class TestWhisperDetectorDetectLanguage:
    """Tests for WhisperDetector.detect_language."""

    @patch("plex_organizer.audio.whisper.WhisperModel")
    @patch("plex_organizer.audio.whisper.get_whisper_model_size", return_value="tiny")
    def test_detect_language_returns_result(self, _ms, mock_wm):
        """Returns language and probability from model."""
        mock_model = MagicMock()
        info = MagicMock()
        info.language = "en"
        info.language_probability = 0.95
        mock_model.transcribe.return_value = (iter([MagicMock()]), info)
        mock_wm.return_value = mock_model

        detector = WhisperDetector()
        lang, prob = detector.detect_language("/audio.wav")
        assert lang == "en"
        assert prob == approx(0.95)

    @patch("plex_organizer.audio.whisper.WhisperModel")
    @patch("plex_organizer.audio.whisper.get_whisper_model_size", return_value="tiny")
    def test_detect_handles_empty_segments(self, _ms, mock_wm):
        """Handles empty segment iterator gracefully."""
        mock_model = MagicMock()
        info = MagicMock()
        info.language = "es"
        info.language_probability = 0.8
        mock_model.transcribe.return_value = (iter([]), info)
        mock_wm.return_value = mock_model

        detector = WhisperDetector()
        lang, prob = detector.detect_language("/audio.wav")
        assert lang == "es"
        assert prob == approx(0.8)

    def test_detect_raises_when_unavailable(self):
        """Raises RuntimeError when backend is unavailable."""
        with (
            patch(
                "plex_organizer.audio.whisper.WhisperModel",
                side_effect=OSError,
            ),
            patch(
                "plex_organizer.audio.whisper.get_whisper_model_size",
                return_value="tiny",
            ),
        ):
            detector = WhisperDetector()
        with raises(RuntimeError, match="unavailable"):
            detector.detect_language("/audio.wav")

    @patch("plex_organizer.audio.whisper.WhisperModel")
    @patch("plex_organizer.audio.whisper.get_whisper_model_size", return_value="tiny")
    def test_detect_handles_none_probability(self, _ms, mock_wm):
        """Handles None probability gracefully."""
        mock_model = MagicMock()
        info = MagicMock()
        info.language = "fr"
        info.language_probability = None
        mock_model.transcribe.return_value = (iter([]), info)
        mock_wm.return_value = mock_model

        detector = WhisperDetector()
        lang, prob = detector.detect_language("/audio.wav")
        assert lang == "fr"
        assert prob == approx(0.0)
