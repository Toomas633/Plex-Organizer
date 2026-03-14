"""Tests for plex_organizer.config."""

from pytest import mark

from plex_organizer.config import (
    ensure_config_exists,
    get_analyze_embedded_subtitles,
    get_capitalize,
    get_clear_log,
    get_cpu_threads,
    get_delete_duplicates,
    get_enable_audio_tagging,
    get_enable_logging,
    get_enable_subtitle_embedding,
    get_fetch_subtitles,
    get_host,
    get_include_quality,
    get_log_file,
    get_logging_level,
    get_qbittorrent_password,
    get_qbittorrent_username,
    get_radarr_api_key,
    get_radarr_enabled,
    get_radarr_host,
    get_sonarr_api_key,
    get_sonarr_enabled,
    get_sonarr_host,
    get_subtitle_providers,
    get_sync_subtitles,
    get_timestamped_log_files,
    get_whisper_model_size,
)


class TestEnsureConfigExists:
    """Tests for config creation, preservation, and validation."""

    def test_creates_config_when_missing(self, config_dir):
        """Verify config.ini is created when it does not exist."""
        config_file = config_dir / "config.ini"
        assert not config_file.exists()
        ensure_config_exists()
        assert config_file.exists()

    def test_preserves_existing_values(self, config_dir):
        """Verify user-edited values are preserved after config validation."""
        config_file = config_dir / "config.ini"
        config_file.write_text(
            "[Settings]\ndelete_duplicates = true\ninclude_quality = false\n"
            "capitalize = true\ncpu_threads = 4\n"
        )
        ensure_config_exists()
        content = config_file.read_text()
        assert "delete_duplicates = true" in content
        assert "include_quality = false" in content

    def test_adds_missing_sections(self, config_dir):
        """Verify missing sections are added to an existing config."""
        config_file = config_dir / "config.ini"
        config_file.write_text(
            "[Settings]\ndelete_duplicates = false\n"
            "include_quality = true\ncapitalize = true\ncpu_threads = 2\n"
        )
        ensure_config_exists()
        content = config_file.read_text()
        assert "[qBittorrent]" in content
        assert "[Logging]" in content
        assert "[Sonarr]" in content
        assert "[Radarr]" in content

    def test_removes_unknown_options(self, config_dir):
        """Verify unknown options are removed during config validation."""
        config_file = config_dir / "config.ini"
        config_file.write_text(
            "[Settings]\ndelete_duplicates = false\ninclude_quality = true\n"
            "capitalize = true\ncpu_threads = 2\nbogus_option = yes\n"
        )
        ensure_config_exists()
        content = config_file.read_text()
        assert "bogus_option" not in content


@mark.usefixtures("default_config")
class TestConfigGetters:  # pylint: disable=too-many-public-methods
    """Tests for all config getter functions with default values."""

    def test_get_host(self):
        """Verify default qBittorrent host."""
        assert get_host() == "http://localhost:8081"

    def test_get_delete_duplicates_default(self):
        """Verify delete_duplicates defaults to False."""
        assert get_delete_duplicates() is False

    def test_get_include_quality_default(self):
        """Verify include_quality defaults to True."""
        assert get_include_quality() is True

    def test_get_capitalize_default(self):
        """Verify capitalize defaults to True."""
        assert get_capitalize() is True

    def test_get_cpu_threads_default(self):
        """Verify cpu_threads defaults to 2."""
        assert get_cpu_threads() == 2

    def test_get_enable_logging_default(self):
        """Verify enable_logging defaults to True."""
        assert get_enable_logging() is True

    def test_get_log_file_default(self):
        """Verify default log file name."""
        assert get_log_file() == "plex-organizer.log"

    def test_get_logging_level_default(self):
        """Verify logging level defaults to INFO."""
        assert get_logging_level() == "INFO"

    def test_get_whisper_model_size_default(self):
        """Verify whisper_model_size defaults to tiny."""
        assert get_whisper_model_size() == "tiny"

    def test_get_enable_audio_tagging_default(self):
        """Verify enable_audio_tagging defaults to True."""
        assert get_enable_audio_tagging() is True

    def test_get_enable_subtitle_embedding_default(self):
        """Verify enable_subtitle_embedding defaults to True."""
        assert get_enable_subtitle_embedding() is True

    def test_get_qbittorrent_username_default(self):
        """Verify default qBittorrent username."""
        assert get_qbittorrent_username() == "admin"

    def test_get_qbittorrent_password_default(self):
        """Verify default qBittorrent password."""
        assert get_qbittorrent_password() == "your_password_here"

    def test_get_fetch_subtitles_default(self):
        """Verify fetch_subtitles defaults to a list containing eng."""
        langs = get_fetch_subtitles()
        assert isinstance(langs, list)
        assert "eng" in langs

    def test_get_sync_subtitles_default(self):
        """Verify sync_subtitles defaults to True."""
        assert get_sync_subtitles() is True

    def test_get_subtitle_providers_default(self):
        """Verify subtitle_providers returns a non-empty list."""
        providers = get_subtitle_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_get_timestamped_log_files_default(self):
        """Verify timestamped_log_files defaults to False."""
        assert get_timestamped_log_files() is False

    def test_get_clear_log_default(self):
        """Verify clear_log defaults to False."""
        assert get_clear_log() is False

    def test_get_analyze_embedded_subtitles_default(self):
        """Verify analyze_embedded_subtitles defaults to True."""
        assert get_analyze_embedded_subtitles() is True

    def test_get_fetch_subtitles_empty(self, config_dir):
        """Empty fetch_subtitles value returns empty list."""
        config_file = config_dir / "config.ini"
        content = config_file.read_text()
        config_file.write_text(
            content.replace("fetch_subtitles = eng", "fetch_subtitles =")
        )
        assert get_fetch_subtitles() == []

    def test_get_subtitle_providers_empty_fallback(self, config_dir):
        """Empty subtitle_providers falls back to default list."""
        config_file = config_dir / "config.ini"
        content = config_file.read_text()
        config_file.write_text(
            content.replace(
                "subtitle_providers = opensubtitles, podnapisi, gestdown, tvsubtitles",
                "subtitle_providers =",
            )
        )
        providers = get_subtitle_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_get_sonarr_enabled_default(self):
        """Verify Sonarr is disabled by default."""
        assert get_sonarr_enabled() is False

    def test_get_sonarr_host_default(self):
        """Verify default Sonarr host."""
        assert get_sonarr_host() == "http://localhost:8989"

    def test_get_sonarr_api_key_default(self):
        """Verify Sonarr API key defaults to empty string."""
        assert get_sonarr_api_key() == ""

    def test_get_radarr_enabled_default(self):
        """Verify Radarr is disabled by default."""
        assert get_radarr_enabled() is False

    def test_get_radarr_host_default(self):
        """Verify default Radarr host."""
        assert get_radarr_host() == "http://localhost:7878"

    def test_get_radarr_api_key_default(self):
        """Verify Radarr API key defaults to empty string."""
        assert get_radarr_api_key() == ""

    def test_sonarr_enabled_when_set(self, config_dir):
        """Verify Sonarr reads as enabled when set to true."""
        config_file = config_dir / "config.ini"
        content = config_file.read_text()
        config_file.write_text(
            content.replace(
                "[Sonarr]\nenabled = false",
                "[Sonarr]\nenabled = true",
            )
        )
        assert get_sonarr_enabled() is True

    def test_radarr_enabled_when_set(self, config_dir):
        """Verify Radarr reads as enabled when set to true."""
        config_file = config_dir / "config.ini"
        content = config_file.read_text()
        config_file.write_text(
            content.replace(
                "[Radarr]\nenabled = false",
                "[Radarr]\nenabled = true",
            )
        )
        assert get_radarr_enabled() is True
