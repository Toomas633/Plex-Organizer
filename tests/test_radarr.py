"""Tests for plex_organizer.radarr Radarr API integration."""

from unittest.mock import patch, MagicMock

import pytest
from requests import RequestException

from plex_organizer.radarr import _find_movie, rescan_movie, notify_movies


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
def _mock_radarr_config():
    """Patch Radarr config accessors for all tests in this module."""
    with (
        patch(
            "plex_organizer.radarr.get_radarr_host",
            return_value="http://radarr:7878",
        ),
        patch(
            "plex_organizer.radarr.get_radarr_api_key",
            return_value="test-api-key",
        ),
    ):
        yield


@pytest.mark.usefixtures("_mock_radarr_config")
class TestFindMovie:
    """Tests for _find_movie() lookup."""

    def test_finds_matching_movie(self):
        """Returns the ID when title matches (case-insensitive)."""
        session = MagicMock()
        session.get.return_value.json.return_value = [
            {"title": "Inception", "id": 10},
            {"title": "Interstellar", "id": 20},
        ]
        session.get.return_value.raise_for_status = MagicMock()

        assert _find_movie(session, "inception") == 10

    def test_returns_none_when_not_found(self):
        """Returns None when no movie matches."""
        session = MagicMock()
        session.get.return_value.json.return_value = [
            {"title": "Inception", "id": 10},
        ]
        session.get.return_value.raise_for_status = MagicMock()

        assert _find_movie(session, "The Matrix") is None

    def test_empty_library(self):
        """Returns None when library is empty."""
        session = MagicMock()
        session.get.return_value.json.return_value = []
        session.get.return_value.raise_for_status = MagicMock()

        assert _find_movie(session, "Any Movie") is None


@pytest.mark.usefixtures("_mock_radarr_config")
class TestRescanMovie:
    """Tests for rescan_movie() command dispatch."""

    @patch("plex_organizer.radarr.Session")
    def test_targeted_rescan(self, mock_session_cls):
        """Sends targeted rescan when movie is found."""
        session = _session_with_library([{"title": "Inception", "id": 10}])
        mock_session_cls.return_value = session

        rescan_movie("Inception")

        post_call = session.post.call_args
        assert post_call[1]["json"]["name"] == "RescanMovie"
        assert post_call[1]["json"]["movieId"] == 10
        session.close.assert_called_once()

    @patch("plex_organizer.radarr.Session")
    def test_full_library_rescan_on_not_found(self, mock_session_cls):
        """Falls back to full rescan when movie not in Radarr."""
        session = _session_with_library([])
        mock_session_cls.return_value = session

        rescan_movie("Unknown Movie")

        post_call = session.post.call_args
        assert post_call[1]["json"]["name"] == "RescanMovie"
        assert "movieId" not in post_call[1]["json"]

    @patch("plex_organizer.radarr.Session")
    def test_request_error_is_logged(self, mock_session_cls):
        """RequestException is caught and logged, not raised."""
        session = _session_with_error(RequestException("connection refused"))
        mock_session_cls.return_value = session

        # Should not raise
        rescan_movie("Inception")
        session.close.assert_called_once()


@pytest.mark.usefixtures("_mock_radarr_config")
class TestNotifyMovies:
    """Tests for notify_movies() batch dispatch."""

    @patch("plex_organizer.radarr.rescan_movie")
    def test_calls_rescan_for_each_movie(self, mock_rescan):
        """Calls rescan_movie once per movie name."""
        notify_movies({"Film A", "Film B"})
        assert mock_rescan.call_count == 2
        called_names = {c[0][0] for c in mock_rescan.call_args_list}
        assert called_names == {"Film A", "Film B"}

    @patch("plex_organizer.radarr.rescan_movie")
    def test_empty_set_does_nothing(self, mock_rescan):
        """No calls when the set is empty."""
        notify_movies(set())
        mock_rescan.assert_not_called()
