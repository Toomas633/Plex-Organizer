"""Tests for plex_organizer.log."""

from unittest.mock import patch

from plex_organizer.log import check_clear_log, log_debug, log_duplicate, log_error


class TestLogFunctions:
    """Tests for individual log-level functions."""

    def test_log_error_writes_to_file(self, default_config):
        """log_error writes an ERROR entry to the log file."""
        log_error("test error message")
        log_file = default_config / "plex-organizer.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "[ERROR]" in content
        assert "test error message" in content

    def test_log_duplicate_writes_to_file(self, default_config):
        """log_duplicate writes a DUPLICATE entry to the log file."""
        log_duplicate("duplicate found")
        log_file = default_config / "plex-organizer.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "[DUPLICATE]" in content
        assert "duplicate found" in content

    def test_log_debug_respects_level(self, default_config):
        """log_debug does not write when logging level is above DEBUG."""
        log_debug("debug msg")
        log_file = default_config / "plex-organizer.log"
        if log_file.exists():
            content = log_file.read_text()
            assert "debug msg" not in content

    def test_log_debug_when_debug_enabled(self, default_config):
        """log_debug writes when logging level is DEBUG."""
        with patch("plex_organizer.log.get_logging_level", return_value="DEBUG"):
            log_debug("visible debug")
        log_file = default_config / "plex-organizer.log"
        content = log_file.read_text()
        assert "visible debug" in content

    def test_logging_disabled(self, default_config):
        """No log entry is written when logging is disabled."""
        with patch("plex_organizer.log.get_enable_logging", return_value=False):
            log_error("should not appear")
        log_file = default_config / "plex-organizer.log"
        if log_file.exists():
            content = log_file.read_text()
            assert "should not appear" not in content

    def test_timestamped_log_creates_log_dir(self, default_config):
        """Timestamped logging creates a logs/ subdirectory and writes there."""
        with patch("plex_organizer.log.get_timestamped_log_files", return_value=True):
            log_error("timestamped entry")
        logs_dir = default_config / "logs"
        assert logs_dir.exists()
        log_files = list(logs_dir.glob("plex-organizer.*.log"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "timestamped entry" in content


class TestCheckClearLog:
    """Tests for check_clear_log behaviour."""

    def test_clears_log_when_enabled(self, default_config):
        """Log file is emptied when clear_log is enabled."""
        log_error("old message")
        log_file = default_config / "plex-organizer.log"
        assert "old message" in log_file.read_text()

        with patch("plex_organizer.log.get_clear_log", return_value=True):
            check_clear_log()

        content = log_file.read_text()
        assert content == ""

    def test_preserves_log_when_disabled(self, default_config):
        """Log file is preserved when clear_log is disabled."""
        log_error("keep this")
        log_file = default_config / "plex-organizer.log"

        with patch("plex_organizer.log.get_clear_log", return_value=False):
            check_clear_log()

        assert "keep this" in log_file.read_text()
