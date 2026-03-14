"""Tests for plex_organizer.__main__ arg parsing and dispatch."""

from unittest.mock import patch, MagicMock

from plex_organizer.__main__ import main, _detect_arr_env


class TestMain:
    """Tests for the main() CLI entrypoint dispatch."""

    @patch("plex_organizer.organizer.main")
    @patch(
        "plex_organizer.__main__._detect_arr_env",
        return_value=(None, None, None),
    )
    @patch(
        "plex_organizer.__main__.ArgumentParser.parse_args",
        return_value=MagicMock(manage=False, start_dir="/media", torrent_hash="abc123"),
    )
    def test_dispatches_to_organize(self, _args, _env, mock_organize):
        """Calls organize() with start_dir and torrent_hash."""
        main()
        mock_organize.assert_called_once_with("/media", "abc123", source=None)

    @patch("plex_organizer.manage.main")
    @patch(
        "plex_organizer.__main__.ArgumentParser.parse_args",
        return_value=MagicMock(manage=True),
    )
    def test_dispatches_to_manage(self, _args, mock_manage):
        """Calls manage() when --manage flag is set."""
        main()
        mock_manage.assert_called_once()

    @patch("plex_organizer.organizer.main")
    @patch(
        "plex_organizer.__main__._detect_arr_env",
        return_value=(None, None, None),
    )
    @patch(
        "plex_organizer.__main__.ArgumentParser.parse_args",
        return_value=MagicMock(
            manage=False, start_dir="/media/tv/Show", torrent_hash=None
        ),
    )
    def test_no_torrent_hash(self, _args, _env, mock_organize):
        """Passes None torrent_hash when not provided."""
        main()
        mock_organize.assert_called_once_with("/media/tv/Show", None, source=None)


class TestDetectArrEnv:
    """Tests for Sonarr/Radarr Custom Script env var detection."""

    def test_no_env_vars_returns_none(self):
        """Returns (None, None, None) when no arr env vars are set."""
        with patch.dict("os.environ", {}, clear=True):
            start_dir, torrent_hash, source = _detect_arr_env()
        assert start_dir is None
        assert torrent_hash is None
        assert source is None

    def test_sonarr_download_event(self):
        """Sonarr Download event extracts series path and download ID."""
        env = {
            "sonarr_eventtype": "Download",
            "sonarr_series_path": "/media/tv/Breaking Bad",
            "sonarr_download_id": "hash123",
        }
        with patch.dict("os.environ", env, clear=True):
            start_dir, torrent_hash, source = _detect_arr_env()
        assert start_dir == "/media/tv/Breaking Bad"
        assert torrent_hash == "hash123"
        assert source == "sonarr"

    def test_sonarr_test_event(self):
        """Sonarr Test event returns test source for clean exit."""
        env = {"sonarr_eventtype": "Test"}
        with patch.dict("os.environ", env, clear=True):
            start_dir, torrent_hash, source = _detect_arr_env()
        assert start_dir is None
        assert torrent_hash is None
        assert source == "sonarr_test"

    def test_radarr_download_event(self):
        """Radarr Download event extracts movie path and download ID."""
        env = {
            "radarr_eventtype": "Download",
            "radarr_movie_path": "/media/movies/Inception (2010)",
            "radarr_download_id": "movhash",
        }
        with patch.dict("os.environ", env, clear=True):
            start_dir, torrent_hash, source = _detect_arr_env()
        assert start_dir == "/media/movies/Inception (2010)"
        assert torrent_hash == "movhash"
        assert source == "radarr"

    def test_radarr_test_event(self):
        """Radarr Test event returns test source for clean exit."""
        env = {"radarr_eventtype": "Test"}
        with patch.dict("os.environ", env, clear=True):
            start_dir, torrent_hash, source = _detect_arr_env()
        assert start_dir is None
        assert torrent_hash is None
        assert source == "radarr_test"

    def test_sonarr_takes_priority_over_radarr(self):
        """Sonarr env vars take priority when both are present."""
        env = {
            "sonarr_eventtype": "Download",
            "sonarr_series_path": "/media/tv/Show",
            "radarr_eventtype": "Download",
            "radarr_movie_path": "/media/movies/Film",
        }
        with patch.dict("os.environ", env, clear=True):
            _, _, source = _detect_arr_env()
        assert source == "sonarr"

    def test_sonarr_missing_download_id(self):
        """Missing download_id is returned as None."""
        env = {
            "sonarr_eventtype": "Download",
            "sonarr_series_path": "/media/tv/Show",
        }
        with patch.dict("os.environ", env, clear=True):
            _, torrent_hash, _ = _detect_arr_env()
        assert torrent_hash is None


class TestMainArrIntegration:
    """Tests for CLI entrypoint with Sonarr/Radarr env vars."""

    @patch("plex_organizer.organizer.main")
    @patch(
        "plex_organizer.__main__._detect_arr_env",
        return_value=("/media/tv/Show", "hash123", "sonarr"),
    )
    @patch(
        "plex_organizer.__main__.ArgumentParser.parse_args",
        return_value=MagicMock(manage=False, start_dir=None, torrent_hash=None),
    )
    def test_sonarr_env_overrides_cli(self, _args, _env, mock_organize):
        """Sonarr env vars override missing CLI args."""
        main()
        mock_organize.assert_called_once_with(
            "/media/tv/Show", "hash123", source="sonarr"
        )

    @patch("plex_organizer.log.log_info")
    @patch(
        "plex_organizer.__main__._detect_arr_env",
        return_value=(None, None, "sonarr_test"),
    )
    @patch(
        "plex_organizer.__main__.ArgumentParser.parse_args",
        return_value=MagicMock(manage=False, start_dir=None, torrent_hash=None),
    )
    def test_sonarr_test_event_exits_cleanly(self, _args, _env, mock_log):
        """Sonarr Test event logs success and returns without processing."""
        main()
        assert any("test event" in str(c).lower() for c in mock_log.call_args_list)
