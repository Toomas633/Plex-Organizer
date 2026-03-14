"""Tests for plex_organizer.sonarr Sonarr API integration."""

from unittest.mock import patch, MagicMock

import pytest
from requests import RequestException

from plex_organizer.sonarr import _find_series, rescan_series, notify_series


def _session_with_library(library: list[dict]) -> MagicMock:
    """Return a mock Session whose GET returns *library* and POST succeeds."""
    session = MagicMock()
    get_resp = MagicMock()
    get_resp.json.return_value = library
    session.get.return_value = get_resp
    session.post.return_value = MagicMock()
    return session


def _session_with_error(error: Exception) -> MagicMock:
    """Return a mock Session whose GET raises *error*."""
    session = MagicMock()
    session.get.side_effect = error
    return session


@pytest.fixture()
def _mock_sonarr_config():
    """Patch Sonarr config accessors for all tests in this module."""
    with (
        patch(
            "plex_organizer.sonarr.get_sonarr_host",
            return_value="http://sonarr:8989",
        ),
        patch(
            "plex_organizer.sonarr.get_sonarr_api_key",
            return_value="test-api-key",
        ),
    ):
        yield


@pytest.mark.usefixtures("_mock_sonarr_config")
class TestFindSeries:
    """Tests for _find_series() lookup."""

    def test_finds_matching_series(self):
        """Returns the ID when title matches (case-insensitive)."""
        session = MagicMock()
        session.get.return_value.json.return_value = [
            {"title": "Breaking Bad", "id": 42},
            {"title": "Better Call Saul", "id": 7},
        ]
        session.get.return_value.raise_for_status = MagicMock()

        assert _find_series(session, "breaking bad") == 42

    def test_returns_none_when_not_found(self):
        """Returns None when no series matches."""
        session = MagicMock()
        session.get.return_value.json.return_value = [
            {"title": "Breaking Bad", "id": 42},
        ]
        session.get.return_value.raise_for_status = MagicMock()

        assert _find_series(session, "The Wire") is None

    def test_empty_library(self):
        """Returns None when library is empty."""
        session = MagicMock()
        session.get.return_value.json.return_value = []
        session.get.return_value.raise_for_status = MagicMock()

        assert _find_series(session, "Any Show") is None


@pytest.mark.usefixtures("_mock_sonarr_config")
class TestRescanSeries:
    """Tests for rescan_series() command dispatch."""

    @patch("plex_organizer.sonarr.Session")
    def test_targeted_rescan(self, mock_session_cls):
        """Sends targeted rescan when series is found."""
        session = _session_with_library([{"title": "Breaking Bad", "id": 42}])
        mock_session_cls.return_value = session

        rescan_series("Breaking Bad")

        post_call = session.post.call_args
        assert post_call[1]["json"]["name"] == "RescanSeries"
        assert post_call[1]["json"]["seriesId"] == 42
        session.close.assert_called_once()

    @patch("plex_organizer.sonarr.Session")
    def test_full_library_rescan_on_not_found(self, mock_session_cls):
        """Falls back to full rescan when series not in Sonarr."""
        session = _session_with_library([])
        mock_session_cls.return_value = session

        rescan_series("Unknown Show")

        post_call = session.post.call_args
        assert post_call[1]["json"]["name"] == "RescanSeries"
        assert "seriesId" not in post_call[1]["json"]

    @patch("plex_organizer.sonarr.Session")
    def test_request_error_is_logged(self, mock_session_cls):
        """RequestException is caught and logged, not raised."""
        session = _session_with_error(RequestException("connection refused"))
        mock_session_cls.return_value = session

        # Should not raise
        rescan_series("Breaking Bad")
        session.close.assert_called_once()


@pytest.mark.usefixtures("_mock_sonarr_config")
class TestNotifySeries:
    """Tests for notify_series() batch dispatch."""

    @patch("plex_organizer.sonarr.rescan_series")
    def test_calls_rescan_for_each_show(self, mock_rescan):
        """Calls rescan_series once per show name."""
        notify_series({"Show A", "Show B"})
        assert mock_rescan.call_count == 2
        called_names = {c[0][0] for c in mock_rescan.call_args_list}
        assert called_names == {"Show A", "Show B"}

    @patch("plex_organizer.sonarr.rescan_series")
    def test_empty_set_does_nothing(self, mock_rescan):
        """No calls when the set is empty."""
        notify_series(set())
        mock_rescan.assert_not_called()
