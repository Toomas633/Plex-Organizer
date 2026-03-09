"""Tests for plex_organizer.movie."""

from pathlib import Path
from unittest.mock import patch
from pytest import mark

from plex_organizer.movie import _create_name, move


@mark.usefixtures("default_config")
class TestCreateName:
    """Test movie name creation."""

    def test_standard_torrent_name(self):
        """Standard torrent name is parsed into Name (Year).ext format."""
        result = _create_name("Inception.2010.1080p.BluRay.x264-GROUP.mkv")
        assert "Inception" in result
        assert "(2010)" in result
        assert result.endswith(".mkv")

    def test_already_correct_name(self):
        """Already correct Name (Year).ext is returned unchanged."""
        result = _create_name("Inception (2010).mkv")
        assert result == "Inception (2010).mkv"

    def test_already_correct_with_quality(self):
        """Already correct name with quality tag is returned unchanged."""
        result = _create_name("Inception (2010) 1080p.mkv")
        assert result == "Inception (2010) 1080p.mkv"

    def test_quality_included(self):
        """Quality tag is included when include_quality is enabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            result = _create_name("Inception.2010.1080p.BluRay.x264-GROUP.mkv")
            assert "1080p" in result

    def test_quality_excluded(self):
        """Quality tag is omitted when include_quality is disabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            result = _create_name("Inception.2010.1080p.BluRay.x264-GROUP.mkv")
            assert "1080p" not in result

    def test_unrecognized_filename_returns_original(self):
        """Unrecognized filename is returned as-is."""
        with patch("plex_organizer.movie.log_error"):
            result = _create_name("random_stuff.mkv")
            assert result == "random_stuff.mkv"

    def test_dots_replaced_with_spaces(self):
        """Dots in the title are replaced with spaces."""
        result = _create_name("The.Matrix.1999.720p.BRRip.mkv")
        assert "The Matrix" in result
        assert "(1999)" in result

    def test_mp4_extension_preserved(self):
        """MP4 extension is preserved in the output name."""
        result = _create_name("Inception.2010.1080p.mp4")
        assert result.endswith(".mp4")

    def test_multi_word_title(self):
        """Multi-word title is correctly parsed."""
        result = _create_name(
            "The.Lord.of.the.Rings.The.Fellowship.of.the.Ring.2001.1080p.mkv"
        )
        assert "(2001)" in result
        assert result.endswith(".mkv")

    def test_name_empty_group1_uses_group2(self):
        """When group(1) is empty, name is derived from group(2)."""
        result = _create_name("2010.1080p.BluRay.mkv")
        assert result.endswith(".mkv")

    def test_multiple_years_in_name(self):
        """Film with extra year component includes it in the title."""
        result = _create_name("Blade.Runner.2049.2017.1080p.mkv")
        assert "(2017)" in result
        assert "2049" in result
        assert result.endswith(".mkv")


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
