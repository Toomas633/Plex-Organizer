"""Tests for plex_organizer.tv."""

# pylint: disable=duplicate-code

from os.path import join
from unittest.mock import patch
from pytest import mark, param

from plex_organizer.tv import _create_name, move


@mark.usefixtures("default_config")
class TestCreateName:
    """Test TV episode name creation."""

    def test_standard_episode(self):
        """Standard torrent episode name is parsed correctly."""
        root = join("/media", "tv", "Breaking Bad", "Season 1")
        file = "Breaking.Bad.S01E01.1080p.WEBRip.x265-RARBG.mkv"
        result = _create_name(root, file)
        assert "S01E01" in result
        assert result.endswith(".mkv")
        assert "Breaking Bad" in result

    def test_quality_included(self):
        """Quality tag is included when include_quality is enabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            root = join("/media", "tv", "The Office", "Season 3")
            file = "The.Office.S03E05.720p.WEBRip.mkv"
            result = _create_name(root, file)
            assert "720p" in result

    def test_quality_excluded(self):
        """Quality tag is omitted when include_quality is disabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            root = join("/media", "tv", "The Office", "Season 3")
            file = "The.Office.S03E05.720p.WEBRip.mkv"
            result = _create_name(root, file)
            assert "720p" not in result

    def test_no_season_episode(self):
        """File without SxxExx pattern uses show name from path."""
        root = join("/media", "tv", "Show Name", "Season 1")
        file = "random_video_file.mkv"
        result = _create_name(root, file)
        assert "Show Name" in result
        assert result.endswith(".mkv")

    def test_case_insensitive_episode_pattern(self):
        """Lowercase sXXeXX pattern is normalized to uppercase."""
        root = join("/media", "tv", "Show", "Season 1")
        file = "show.s01e05.720p.mkv"
        result = _create_name(root, file)
        assert "S01E05" in result

    def test_capitalization(self):
        """Show name is capitalized when capitalize setting is enabled."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            root = join("/media", "tv", "the flash", "Season 1")
            file = "the.flash.s01e01.mkv"
            result = _create_name(root, file)
            assert result.startswith("The Flash")

    def test_quality_from_video_properties(self):
        """Quality is probed from video when not in filename."""
        with patch("plex_organizer.tv.probe_video_quality", return_value="1080p"):
            root = join("/media", "tv", "The Office", "Season 3")
            file = "The.Office.S03E05.WEBRip.mkv"
            result = _create_name(root, file)
            assert "1080p" in result

    def test_quality_from_video_properties_none(self):
        """No quality added when probe also returns None."""
        with patch("plex_organizer.tv.probe_video_quality", return_value=None):
            root = join("/media", "tv", "The Office", "Season 3")
            file = "The.Office.S03E05.WEBRip.mkv"
            result = _create_name(root, file)
            assert "p" not in result.replace(".mkv", "").split()[-1]

    def test_quality_from_filename_preferred_over_probe(self):
        """Filename quality takes priority over probed quality."""
        with patch("plex_organizer.tv.probe_video_quality") as mock_probe:
            root = join("/media", "tv", "The Office", "Season 3")
            file = "The.Office.S03E05.720p.WEBRip.mkv"
            result = _create_name(root, file)
            assert "720p" in result
            mock_probe.assert_not_called()


@mark.usefixtures("default_config")
class TestCreateNameIdempotency:
    """Verify raw and already-renamed inputs produce identical output."""

    _cases = [
        param(
            "Breaking Bad",
            "Breaking.Bad.S01E01.1080p.WEBRip.x265-RARBG.mkv",
            "Breaking Bad S01E01 1080p.mkv",
            id="breaking-bad",
        ),
        param(
            "The Office",
            "The.Office.S03E05.720p.WEBRip.mkv",
            "The Office S03E05 720p.mkv",
            id="the-office",
        ),
        param(
            "New Amsterdam",
            "New.Amsterdam.2018.S02E01.1080p.WEBRip.x265-RARBG.mkv",
            "New Amsterdam S02E01 1080p.mkv",
            id="new-amsterdam",
        ),
    ]

    @mark.parametrize("show, raw, expected", _cases)
    def test_raw_name_quality_enabled(self, show, raw, expected):
        """Raw torrent name produces expected output with quality."""
        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            root = join("/media", "tv", show, "Season 1")
            assert _create_name(root, raw) == expected

    @mark.parametrize("show, _raw, expected", _cases)
    def test_already_renamed_quality_enabled(self, show, _raw, expected):
        """Already-renamed file produces same output with quality."""
        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            root = join("/media", "tv", show, "Season 1")
            assert _create_name(root, expected) == expected

    _cases_no_quality = [
        param(
            "Breaking Bad",
            "Breaking.Bad.S01E01.1080p.WEBRip.x265-RARBG.mkv",
            "Breaking Bad S01E01.mkv",
            id="breaking-bad",
        ),
        param(
            "The Office",
            "The.Office.S03E05.720p.WEBRip.mkv",
            "The Office S03E05.mkv",
            id="the-office",
        ),
        param(
            "New Amsterdam",
            "New.Amsterdam.2018.S02E01.1080p.WEBRip.x265-RARBG.mkv",
            "New Amsterdam S02E01.mkv",
            id="new-amsterdam",
        ),
    ]

    @mark.parametrize("show, raw, expected", _cases_no_quality)
    def test_raw_name_quality_disabled(self, show, raw, expected):
        """Raw torrent name produces expected output without quality."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            root = join("/media", "tv", show, "Season 1")
            assert _create_name(root, raw) == expected

    @mark.parametrize("show, _raw, expected", _cases_no_quality)
    def test_already_renamed_quality_disabled(self, show, _raw, expected):
        """Already-renamed file produces same output without quality."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            root = join("/media", "tv", show, "Season 1")
            assert _create_name(root, expected) == expected


@mark.usefixtures("default_config")
class TestCreateNameQualityToggle:
    """Verify quality is added or removed when toggling include_quality."""

    _cases = [
        param(
            "Breaking Bad",
            "Breaking.Bad.S01E01.1080p.WEBRip.x265-RARBG.mkv",
            "Breaking Bad S01E01 1080p.mkv",
            "Breaking Bad S01E01.mkv",
            "1080p",
            id="breaking-bad-raw",
        ),
        param(
            "The Office",
            "The.Office.S03E05.720p.WEBRip.mkv",
            "The Office S03E05 720p.mkv",
            "The Office S03E05.mkv",
            "720p",
            id="the-office-raw",
        ),
    ]

    @mark.parametrize("show, raw, _with_q, without_q, quality", _cases)
    def test_raw_quality_stripped_when_disabled(
        self, show, raw, _with_q, without_q, quality
    ):
        """Raw name with quality in filename loses it when disabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            root = join("/media", "tv", show, "Season 1")
            result = _create_name(root, raw)
            assert quality not in result
            assert result == without_q

    @mark.parametrize("show, _raw, _with_q, without_q, quality", _cases)
    def test_already_renamed_quality_stripped_when_disabled(
        self, show, _raw, _with_q, without_q, quality
    ):
        """Already-renamed name with quality loses it when disabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            root = join("/media", "tv", show, "Season 1")
            # Feed the with-quality name; expect quality to be stripped.
            result = _create_name(
                root, f"{without_q.removesuffix('.mkv')} {quality}.mkv"
            )
            assert quality not in result
            assert result == without_q

    @mark.parametrize("show, raw, with_q, _without_q, quality", _cases)
    def test_raw_quality_added_via_probe_when_enabled(
        self, show, raw, with_q, _without_q, quality
    ):
        """Raw name without quality gets it from probe when enabled."""
        no_quality_raw = raw.replace(f".{quality}", "")
        with (
            patch("plex_organizer.utils.get_include_quality", return_value=True),
            patch("plex_organizer.tv.probe_video_quality", return_value=quality),
        ):
            root = join("/media", "tv", show, "Season 1")
            result = _create_name(root, no_quality_raw)
            assert quality in result
            assert result == with_q

    @mark.parametrize("show, _raw, with_q, without_q, quality", _cases)
    def test_already_renamed_quality_added_via_probe_when_enabled(
        self, show, _raw, with_q, without_q, quality
    ):
        """Already-renamed name without quality gets it from probe when enabled."""
        with (
            patch("plex_organizer.utils.get_include_quality", return_value=True),
            patch("plex_organizer.tv.probe_video_quality", return_value=quality),
        ):
            root = join("/media", "tv", show, "Season 1")
            result = _create_name(root, without_q)
            assert quality in result
            assert result == with_q


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
        assert result == join(str(season_dir), "Show.S01E01.mkv")
