"""Tests for plex_organizer.qb."""

from unittest.mock import MagicMock, patch
from pytest import mark

from plex_organizer.qb import remove_torrent


@mark.usefixtures("default_config")
class TestRemoveTorrent:
    """Tests for qBittorrent torrent removal."""

    def test_successful_removal(self):
        """Successful login and delete issues two POST calls."""
        mock_session = MagicMock()
        mock_login_response = MagicMock(status_code=200, text="Ok.")
        mock_delete_response = MagicMock(status_code=200)
        mock_session.post.side_effect = [mock_login_response, mock_delete_response]

        with patch("plex_organizer.qb.Session", return_value=mock_session):
            remove_torrent("abc123")

        assert mock_session.post.call_count == 2
        delete_call = mock_session.post.call_args_list[1]
        assert "torrents/delete" in delete_call[0][0]
        assert delete_call[1]["data"]["hashes"] == "abc123"
        assert delete_call[1]["data"]["deleteFiles"] == "false"

    def test_auth_failure_logs_error(self):
        """Authentication failure is logged as an error."""
        mock_session = MagicMock()
        mock_login_response = MagicMock(status_code=403, text="Forbidden")
        mock_session.post.return_value = mock_login_response

        with (
            patch("plex_organizer.qb.Session", return_value=mock_session),
            patch("plex_organizer.qb.log_error") as mock_log,
        ):
            remove_torrent("abc123")
            mock_log.assert_called()

    def test_delete_failure_logs_error(self):
        """Delete API failure is logged as an error."""
        mock_session = MagicMock()
        mock_login_response = MagicMock(status_code=200, text="Ok.")
        mock_delete_response = MagicMock(status_code=500, text="Internal Error")
        mock_session.post.side_effect = [mock_login_response, mock_delete_response]

        with (
            patch("plex_organizer.qb.Session", return_value=mock_session),
            patch("plex_organizer.qb.log_error") as mock_log,
        ):
            remove_torrent("abc123")
            mock_log.assert_called()

    def test_missing_credentials_logs_error(self):
        """Missing credentials are logged as an error."""
        with (
            patch("plex_organizer.qb.get_qbittorrent_username", return_value=""),
            patch("plex_organizer.qb.get_qbittorrent_password", return_value=""),
            patch("plex_organizer.qb.log_error") as mock_log,
        ):
            remove_torrent("abc123")
            mock_log.assert_called()
