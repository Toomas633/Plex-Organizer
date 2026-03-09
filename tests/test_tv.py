"""Tests for plex_organizer.tv."""

from os.path import join as os_join
from unittest.mock import patch
from pytest import mark

from plex_organizer.tv import _create_name, move


@mark.usefixtures("default_config")
class TestCreateName:
    """Test TV episode name creation."""

    def test_standard_episode(self):
        """Standard torrent episode name is parsed correctly."""
        root = os_join("/media", "tv", "Breaking Bad", "Season 1")
        file = "Breaking.Bad.S01E01.1080p.WEBRip.x265-RARBG.mkv"
        result = _create_name(root, file)
        assert "S01E01" in result
        assert result.endswith(".mkv")
        assert "Breaking Bad" in result

    def test_quality_included(self):
        """Quality tag is included when include_quality is enabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            root = os_join("/media", "tv", "The Office", "Season 3")
            file = "The.Office.S03E05.720p.WEBRip.mkv"
            result = _create_name(root, file)
            assert "720p" in result

    def test_quality_excluded(self):
        """Quality tag is omitted when include_quality is disabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            root = os_join("/media", "tv", "The Office", "Season 3")
            file = "The.Office.S03E05.720p.WEBRip.mkv"
            result = _create_name(root, file)
            assert "720p" not in result

    def test_no_season_episode(self):
        """File without SxxExx pattern uses show name from path."""
        root = os_join("/media", "tv", "Show Name", "Season 1")
        file = "random_video_file.mkv"
        result = _create_name(root, file)
        assert "Show Name" in result
        assert result.endswith(".mkv")

    def test_case_insensitive_episode_pattern(self):
        """Lowercase sXXeXX pattern is normalized to uppercase."""
        root = os_join("/media", "tv", "Show", "Season 1")
        file = "show.s01e05.720p.mkv"
        result = _create_name(root, file)
        assert "S01E05" in result

    def test_capitalization(self):
        """Show name is capitalized when capitalize setting is enabled."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            root = os_join("/media", "tv", "the flash", "Season 1")
            file = "the.flash.s01e01.mkv"
            result = _create_name(root, file)
            assert result.startswith("The Flash")


@mark.usefixtures("default_config")
class TestMove:
    """Test TV episode move/rename."""

    def test_moves_file_to_season_dir(self, tmp_path):
        """Episode is moved into the correct Season folder."""
        show_dir = tmp_path / "tv" / "Some Show"
        download_dir = show_dir / "downloads"
        download_dir.mkdir(parents=True)
        src = download_dir / "Some.Show.S01E01.1080p.mkv"
        src.write_text("video")

        move(str(download_dir), "Some.Show.S01E01.1080p.mkv")
        season_dir = show_dir / "Season 1"
        assert season_dir.exists()

    def test_file_already_in_correct_place(self, tmp_path):
        """File already in correct location returns its current path."""
        show_dir = tmp_path / "tv" / "Show"
        season_dir = show_dir / "Season 1"
        season_dir.mkdir(parents=True)
        src = season_dir / "Show.S01E01.mkv"
        src.write_text("video")

        result = move(str(season_dir), "Show.S01E01.mkv")
        assert result == os_join(str(season_dir), "Show.S01E01.mkv")
