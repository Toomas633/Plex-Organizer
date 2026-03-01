"""Tests for plex_organizer._paths."""

from os.path import isdir
from unittest.mock import patch

from plex_organizer._paths import data_dir


class TestDataDir:
    """Tests for data_dir resolution and caching."""

    def test_env_var_override(self, tmp_path, monkeypatch):
        """PLEX_ORGANIZER_DIR env var overrides the default data directory."""
        data_dir.cache_clear()
        custom_dir = tmp_path / "custom_config"
        monkeypatch.setenv("PLEX_ORGANIZER_DIR", str(custom_dir))
        result = data_dir()
        assert result == str(custom_dir)
        assert isdir(result)
        data_dir.cache_clear()

    def test_cwd_with_config(self, tmp_path, monkeypatch):
        """CWD is used when it contains a config.ini file."""
        data_dir.cache_clear()
        monkeypatch.delenv("PLEX_ORGANIZER_DIR", raising=False)
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.ini").write_text("[Settings]\n")
        result = data_dir()
        assert result == str(tmp_path)
        data_dir.cache_clear()

    def test_cache_works(self, tmp_path, monkeypatch):
        """Repeated calls return the same cached object."""
        data_dir.cache_clear()
        monkeypatch.setenv("PLEX_ORGANIZER_DIR", str(tmp_path))
        first = data_dir()
        second = data_dir()
        assert first is second
        data_dir.cache_clear()

    def test_package_parent_fallback(self, tmp_path, monkeypatch):
        """Falls back to package parent when it contains config.ini."""
        data_dir.cache_clear()
        monkeypatch.delenv("PLEX_ORGANIZER_DIR", raising=False)
        monkeypatch.chdir(tmp_path)
        parent = tmp_path / "parent"
        parent.mkdir()
        (parent / "config.ini").write_text("[Settings]\n")
        with patch("plex_organizer._paths._PACKAGE_PARENT", str(parent)):
            result = data_dir()
        assert result == str(parent)
        data_dir.cache_clear()

    def test_default_fallback(self, tmp_path, monkeypatch):
        """Falls back to default path when no other location matches."""
        data_dir.cache_clear()
        monkeypatch.delenv("PLEX_ORGANIZER_DIR", raising=False)
        monkeypatch.chdir(tmp_path)
        noconf = tmp_path / "noconf"
        noconf.mkdir()
        with (
            patch("plex_organizer._paths._PACKAGE_PARENT", str(noconf)),
            patch("plex_organizer._paths.os.makedirs") as mock_makedirs,
            patch("plex_organizer._paths.os.path.isfile", return_value=False),
        ):
            result = data_dir()
        assert result == "/root/.config/plex-organizer"
        mock_makedirs.assert_called_with("/root/.config/plex-organizer", exist_ok=True)
        data_dir.cache_clear()
