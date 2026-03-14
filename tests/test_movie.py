"""Tests for plex_organizer.movie."""

# pylint: disable=duplicate-code

from pathlib import Path
from unittest.mock import patch
from pytest import mark, param

from plex_organizer.movie import _create_name, move


@mark.usefixtures("default_config")
class TestCreateName:
    """Test movie name creation."""

    def test_standard_torrent_name(self):
        """Standard torrent name is parsed into Name (Year).ext format."""
        result = _create_name("Inception.2010.1080p.BluRay.x264-GROUP.mkv", "")
        assert "Inception" in result
        assert "(2010)" in result
        assert result.endswith(".mkv")

    def test_already_correct_name(self):
        """Already correct Name (Year).ext is re-parsed correctly."""
        result = _create_name("Inception (2010).mkv", "")
        assert result == "Inception (2010).mkv"

    def test_already_correct_with_quality(self):
        """Already correct name with quality tag is re-parsed correctly."""
        result = _create_name("Inception (2010) 1080p.mkv", "")
        assert result == "Inception (2010) 1080p.mkv"

    def test_already_correct_multi_year(self):
        """Already correct name with year in title is re-parsed correctly."""
        result = _create_name("Blade Runner 2049 (2017) 1080p.mkv", "")
        assert "Blade Runner 2049" in result
        assert "(2017)" in result
        assert "1080p" in result

    def test_already_correct_no_quality(self):
        """Already correct name without quality is re-parsed correctly."""
        result = _create_name("Blade Runner 2049 (2017).mkv", "")
        assert "Blade Runner 2049" in result
        assert "(2017)" in result

    def test_quality_included(self):
        """Quality tag is included when include_quality is enabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            result = _create_name("Inception.2010.1080p.BluRay.x264-GROUP.mkv", "")
            assert "1080p" in result

    def test_quality_excluded(self):
        """Quality tag is omitted when include_quality is disabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            result = _create_name("Inception.2010.1080p.BluRay.x264-GROUP.mkv", "")
            assert "1080p" not in result

    def test_unrecognized_filename_returns_original(self):
        """Unrecognized filename is returned as-is."""
        with patch("plex_organizer.movie.log_error"):
            result = _create_name("random_stuff.mkv", "")
            assert result == "random_stuff.mkv"

    def test_dots_replaced_with_spaces(self):
        """Dots in the title are replaced with spaces."""
        result = _create_name("The.Matrix.1999.720p.BRRip.mkv", "")
        assert "The Matrix" in result
        assert "(1999)" in result

    def test_mp4_extension_preserved(self):
        """MP4 extension is preserved in the output name."""
        result = _create_name("Inception.2010.1080p.mp4", "")
        assert result.endswith(".mp4")

    def test_multi_word_title(self):
        """Multi-word title is correctly parsed."""
        result = _create_name(
            "The.Lord.of.the.Rings.The.Fellowship.of.the.Ring.2001.1080p.mkv", ""
        )
        assert "(2001)" in result
        assert result.endswith(".mkv")

    def test_name_empty_group1_uses_group2(self):
        """When group(1) is empty, name is derived from group(2)."""
        result = _create_name("2010.1080p.BluRay.mkv", "")
        assert "2010" in result
        assert result.endswith(".mkv")

    def test_numeric_title_with_year(self):
        """Movie titled with a number (e.g. 1917) parses title and year."""
        result = _create_name("1917.2019.1080p.BluRay.mkv", "")
        assert "1917" in result
        assert "(2019)" in result
        assert "1080p" in result

    def test_numeric_title_already_correct(self):
        """Already-correct numeric title is re-parsed correctly."""
        result = _create_name("1917 (2019) 1080p.mkv", "")
        assert "1917" in result
        assert "(2019)" in result
        assert "1080p" in result

    def test_numeric_title_already_correct_no_quality(self):
        """Already-correct numeric title without quality is re-parsed correctly."""
        result = _create_name("1917 (2019).mkv", "")
        assert "1917" in result
        assert "(2019)" in result

    def test_multiple_years_in_name(self):
        """Film with extra year component includes it in the title."""
        result = _create_name("Blade.Runner.2049.2017.1080p.mkv", "")
        assert "(2017)" in result
        assert "2049" in result
        assert result.endswith(".mkv")

    def test_quality_from_video_properties(self):
        """Quality is probed from video when not in filename."""
        with patch("plex_organizer.movie.probe_video_quality", return_value="1080p"):
            result = _create_name(
                "Inception.2010.BluRay.x264-GROUP.mkv", root="/movies"
            )
            assert "1080p" in result

    def test_quality_from_video_properties_none(self):
        """No quality added when probe also returns None."""
        with patch("plex_organizer.movie.probe_video_quality", return_value=None):
            result = _create_name(
                "Inception.2010.BluRay.x264-GROUP.mkv", root="/movies"
            )
            assert "p" not in result.replace(".mkv", "").split()[-1]

    def test_quality_from_filename_preferred_over_probe(self):
        """Filename quality takes priority over probed quality."""
        with patch("plex_organizer.movie.probe_video_quality") as mock_probe:
            result = _create_name("Inception.2010.720p.BluRay.mkv", root="/movies")
            assert "720p" in result
            mock_probe.assert_not_called()

    def test_quality_not_probed_without_root(self):
        """Quality probe is skipped when root is not provided."""
        with patch("plex_organizer.movie.probe_video_quality") as mock_probe:
            result = _create_name("Inception.2010.BluRay.x264-GROUP.mkv", "")
            mock_probe.assert_not_called()
            assert result.endswith(".mkv")


@mark.usefixtures("default_config")
class TestCreateNameIdempotency:
    """Verify raw and already-renamed inputs produce identical output."""

    _cases = [
        param(
            "Inception.2010.1080p.BluRay.x264-GROUP.mkv",
            "Inception (2010) 1080p.mkv",
            id="inception",
        ),
        param(
            "The.Matrix.1999.720p.BRRip.mkv",
            "The Matrix (1999) 720p.mkv",
            id="the-matrix",
        ),
        param(
            "Blade.Runner.2049.2017.1080p.mkv",
            "Blade Runner 2049 (2017) 1080p.mkv",
            id="blade-runner-2049",
        ),
        param(
            "1917.2019.1080p.BluRay.mkv",
            "1917 (2019) 1080p.mkv",
            id="1917",
        ),
    ]

    @mark.parametrize("raw, expected", _cases)
    def test_raw_name_quality_enabled(self, raw, expected):
        """Raw torrent name produces expected output with quality."""
        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            assert _create_name(raw, "") == expected

    @mark.parametrize("_raw, expected", _cases)
    def test_already_renamed_quality_enabled(self, _raw, expected):
        """Already-renamed file produces same output with quality."""
        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            assert _create_name(expected, "") == expected

    _cases_no_quality = [
        param(
            "Inception.2010.1080p.BluRay.x264-GROUP.mkv",
            "Inception (2010).mkv",
            id="inception",
        ),
        param(
            "The.Matrix.1999.720p.BRRip.mkv",
            "The Matrix (1999).mkv",
            id="the-matrix",
        ),
        param(
            "Blade.Runner.2049.2017.1080p.mkv",
            "Blade Runner 2049 (2017).mkv",
            id="blade-runner-2049",
        ),
        param(
            "1917.2019.1080p.BluRay.mkv",
            "1917 (2019).mkv",
            id="1917",
        ),
    ]

    @mark.parametrize("raw, expected", _cases_no_quality)
    def test_raw_name_quality_disabled(self, raw, expected):
        """Raw torrent name produces expected output without quality."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            assert _create_name(raw, "") == expected

    @mark.parametrize("_raw, expected", _cases_no_quality)
    def test_already_renamed_quality_disabled(self, _raw, expected):
        """Already-renamed file produces same output without quality."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            assert _create_name(expected, "") == expected


@mark.usefixtures("default_config")
class TestCreateNameQualityToggle:
    """Verify quality is added or removed when toggling include_quality."""

    _cases = [
        param(
            "Inception.2010.1080p.BluRay.x264-GROUP.mkv",
            "Inception (2010) 1080p.mkv",
            "Inception (2010).mkv",
            "1080p",
            id="inception",
        ),
        param(
            "Blade.Runner.2049.2017.1080p.mkv",
            "Blade Runner 2049 (2017) 1080p.mkv",
            "Blade Runner 2049 (2017).mkv",
            "1080p",
            id="blade-runner-2049",
        ),
        param(
            "1917.2019.1080p.BluRay.mkv",
            "1917 (2019) 1080p.mkv",
            "1917 (2019).mkv",
            "1080p",
            id="1917",
        ),
    ]

    @mark.parametrize("raw, _with_q, without_q, quality", _cases)
    def test_raw_quality_stripped_when_disabled(self, raw, _with_q, without_q, quality):
        """Raw name with quality in filename loses it when disabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            result = _create_name(raw, "")
            assert quality not in result
            assert result == without_q

    @mark.parametrize("_raw, with_q, without_q, quality", _cases)
    def test_already_renamed_quality_stripped_when_disabled(
        self, _raw, with_q, without_q, quality
    ):
        """Already-renamed name with quality loses it when disabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            result = _create_name(with_q, "")
            assert quality not in result
            assert result == without_q

    @mark.parametrize("raw, with_q, _without_q, quality", _cases)
    def test_raw_quality_added_via_probe_when_enabled(
        self, raw, with_q, _without_q, quality
    ):
        """Raw name without quality gets it from probe when enabled."""
        no_quality_raw = raw.replace(f".{quality}", "")
        with (
            patch("plex_organizer.utils.get_include_quality", return_value=True),
            patch("plex_organizer.movie.probe_video_quality", return_value=quality),
        ):
            result = _create_name(no_quality_raw, "/movies")
            assert quality in result
            assert result == with_q

    @mark.parametrize("_raw, with_q, without_q, quality", _cases)
    def test_already_renamed_quality_added_via_probe_when_enabled(
        self, _raw, with_q, without_q, quality
    ):
        """Already-renamed name without quality gets it from probe when enabled."""
        with (
            patch("plex_organizer.utils.get_include_quality", return_value=True),
            patch("plex_organizer.movie.probe_video_quality", return_value=quality),
        ):
            result = _create_name(without_q, "/movies")
            assert quality in result
            assert result == with_q


@mark.usefixtures("default_config")
class TestMove:
    """Test movie move/rename."""

    def test_moves_file_to_movie_subfolder(self, tmp_path):
        """Movie file is moved into a movie-name subfolder under movies root."""
        movies_dir = tmp_path / "movies"
        sub_dir = movies_dir / "Inception.2010.1080p.BluRay"
        sub_dir.mkdir(parents=True)
        src = sub_dir / "Inception.2010.1080p.BluRay.x264-GROUP.mkv"
        src.write_text("video")

        result = move(str(movies_dir), str(sub_dir), src.name)
        assert str(movies_dir) in result

        result_path = Path(result)
        assert result_path.parent.parent == movies_dir

    def test_folder_excludes_quality(self, tmp_path):
        """Movie subfolder never includes the quality tag."""
        movies_dir = tmp_path / "movies"
        sub_dir = movies_dir / "Inception.2010.1080p.BluRay"
        sub_dir.mkdir(parents=True)
        src = sub_dir / "Inception.2010.1080p.BluRay.x264-GROUP.mkv"
        src.write_text("video")

        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            result = move(str(movies_dir), str(sub_dir), src.name)

        result_path = Path(result)
        assert "1080p" in result_path.name
        assert "1080p" not in result_path.parent.name
        assert result_path.parent.name == "Inception (2010)"

    def test_same_source_and_dest_returns_path(self, tmp_path):
        """When source and dest match, the existing path is returned."""
        movies_dir = tmp_path / "movies"
        movie_folder = movies_dir / "Inception (2010)"
        movie_folder.mkdir(parents=True)
        src = movie_folder / "Inception (2010).mkv"
        src.write_text("video")

        result = move(str(movies_dir), str(movie_folder), src.name)
        assert result == str(src)
