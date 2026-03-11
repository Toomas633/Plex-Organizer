"""Tests for plex_organizer.__main__ arg parsing and dispatch."""

from unittest.mock import patch, MagicMock

from plex_organizer.__main__ import main


class TestMain:
    """Tests for the main() CLI entrypoint dispatch."""

    @patch("plex_organizer.organizer.main")
    @patch(
        "plex_organizer.__main__.ArgumentParser.parse_args",
        return_value=MagicMock(manage=False, start_dir="/media", torrent_hash="abc123"),
    )
    def test_dispatches_to_organize(self, _args, mock_organize):
        """Calls organize() with start_dir and torrent_hash."""
        main()
        mock_organize.assert_called_once_with("/media", "abc123")

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
        "plex_organizer.__main__.ArgumentParser.parse_args",
        return_value=MagicMock(
            manage=False, start_dir="/media/tv/Show", torrent_hash=None
        ),
    )
    def test_no_torrent_hash(self, _args, mock_organize):
        """Passes None torrent_hash when not provided."""
        main()
        mock_organize.assert_called_once_with("/media/tv/Show", None)
