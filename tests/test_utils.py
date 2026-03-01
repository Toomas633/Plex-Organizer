"""Tests for plex_organizer.utils."""

import os
from unittest.mock import patch

from pytest import mark

from plex_organizer.utils import (
    capitalize,
    create_name,
    find_corrected_directory,
    find_folders,
    is_main_folder,
    is_media_directory,
    is_plex_folder,
    is_script_temp_file,
    is_tv_dir,
    move_file,
)


class TestIsPlexFolder:
    """Tests for is_plex_folder path detection."""

    def test_true_when_plex_versions_in_path(self):
        """Path containing 'Plex Versions' is detected."""
        assert is_plex_folder("/media/tv/Show/Plex Versions/file.mkv")

    def test_false_when_not_present(self):
        """Path without 'Plex Versions' is not detected."""
        assert not is_plex_folder("/media/tv/Show/Season 01/file.mkv")

    def test_false_for_substring_match(self):
        """Partial match of 'Plex Versions' is not detected."""
        assert not is_plex_folder("/media/tv/Plex Versionsx/file.mkv")


class TestFindFolders:
    """Tests for find_folders directory listing."""

    def test_returns_subdirectories(self, tmp_path):
        """Only subdirectories are returned, not files."""
        (tmp_path / "sub1").mkdir()
        (tmp_path / "sub2").mkdir()
        (tmp_path / "file.txt").write_text("x")
        result = find_folders(str(tmp_path))
        names = sorted(os.path.basename(p) for p in result)
        assert names == ["sub1", "sub2"]

    def test_returns_empty_for_nonexistent(self, tmp_path):
        """Non-existent directory returns empty list."""
        result = find_folders(str(tmp_path / "nonexistent"))
        assert result == []

    def test_returns_empty_for_empty_dir(self, tmp_path):
        """Empty directory returns empty list."""
        assert find_folders(str(tmp_path)) == []


@mark.usefixtures("default_config")
class TestMoveFile:
    """Tests for move_file rename and duplicate handling."""

    def test_move_renames_file(self, tmp_path):
        """File is renamed to the destination path."""
        src = tmp_path / "file.mkv"
        dst = tmp_path / "renamed.mkv"
        src.write_text("data")
        move_file(str(src), str(dst))
        assert dst.exists()
        assert not src.exists()

    def test_same_source_and_dest_is_noop(self, tmp_path):
        """Moving to same path is a no-op."""
        src = tmp_path / "file.mkv"
        src.write_text("data")
        move_file(str(src), str(src))
        assert src.exists()

    def test_source_not_found_logs_error(self, tmp_path):
        """Missing source file logs an error."""
        with patch("plex_organizer.utils.log_error") as mock_log:
            move_file(str(tmp_path / "missing.mkv"), str(tmp_path / "dest.mkv"))
            mock_log.assert_called_once()
            assert "not found" in mock_log.call_args[0][0].lower()

    def test_duplicate_skips_and_logs(self, tmp_path):
        """Duplicate file is skipped and logged."""
        src = tmp_path / "file.mkv"
        dst = tmp_path / "existing.mkv"
        src.write_text("source")
        dst.write_text("already-here")
        with patch("plex_organizer.utils.log_duplicate") as mock_dup:
            move_file(str(src), str(dst))
            mock_dup.assert_called_once()
        assert dst.read_text() == "already-here"

    def test_duplicate_deleted_when_configured(self, tmp_path):
        """Duplicate source is deleted when delete_duplicates is enabled."""
        src = tmp_path / "file.mkv"
        dst = tmp_path / "existing.mkv"
        src.write_text("source")
        dst.write_text("already-here")
        with patch("plex_organizer.utils.get_delete_duplicates", return_value=True):
            move_file(str(src), str(dst))
        assert not src.exists()

    def test_duplicate_delete_oserror_logs(self, tmp_path):
        """OSError when deleting a duplicate is logged."""
        src = tmp_path / "file.mkv"
        dst = tmp_path / "existing.mkv"
        src.write_text("source")
        dst.write_text("already-here")
        with (
            patch("plex_organizer.utils.get_delete_duplicates", return_value=True),
            patch("plex_organizer.utils.remove", side_effect=OSError("perm")),
            patch("plex_organizer.utils.log_error") as mock_log,
        ):
            move_file(str(src), str(dst))
            mock_log.assert_called_once()
            assert "duplicate" in mock_log.call_args[0][0].lower()

    def test_move_oserror_logs(self, tmp_path):
        """OSError during move is logged."""
        src = tmp_path / "file.mkv"
        dst = tmp_path / "renamed.mkv"
        src.write_text("data")
        with (
            patch("plex_organizer.utils.move", side_effect=OSError("disk full")),
            patch("plex_organizer.utils.log_error") as mock_log,
        ):
            move_file(str(src), str(dst))
            mock_log.assert_called_once()
            assert "failed to move" in mock_log.call_args[0][0].lower()


@mark.usefixtures("default_config")
class TestCreateName:
    """Tests for create_name assembly."""

    def test_basic_name(self):
        """Parts are joined with spaces and extension appended."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            result = create_name(["Breaking Bad", "S01E01"], ".mkv")
            assert result == "Breaking Bad S01E01.mkv"

    def test_with_quality_enabled(self):
        """Quality tag is appended when enabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=True):
            result = create_name(["Breaking Bad", "S01E01"], ".mkv", "1080p")
            assert result == "Breaking Bad S01E01 1080p.mkv"

    def test_quality_excluded_when_disabled(self):
        """Quality tag is omitted when disabled."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            result = create_name(["Breaking Bad", "S01E01"], ".mkv", "1080p")
            assert result == "Breaking Bad S01E01.mkv"

    def test_none_parts_skipped(self):
        """None values in parts list are filtered out."""
        with patch("plex_organizer.utils.get_include_quality", return_value=False):
            result = create_name(["Show", None, "S01E01"], ".mkv")
            assert result == "Show S01E01.mkv"


class TestIsTvDir:
    """Tests for is_tv_dir path detection."""

    def test_true_for_tv_in_path(self):
        """Path with 'tv' component is detected."""
        assert is_tv_dir("/media/tv/Show/Season 01")

    def test_false_for_movies(self):
        """Movie path is not detected as TV."""
        assert not is_tv_dir("/media/movies/SomeMovie")

    def test_false_when_tv_is_substring_only(self):
        """Substring 'tv' in a folder name is not detected."""
        assert not is_tv_dir("/media/tvshows/Show")


class TestIsMainFolder:
    """Tests for is_main_folder detection."""

    def test_true_when_has_tv_and_movies(self, tmp_media_tree):
        """Folder with both tv/ and movies/ is a main folder."""
        assert is_main_folder(str(tmp_media_tree))

    def test_true_when_has_only_tv(self, tmp_path):
        """Folder with only tv/ is a main folder."""
        (tmp_path / "tv").mkdir()
        assert is_main_folder(str(tmp_path))

    def test_true_when_has_only_movies(self, tmp_path):
        """Folder with only movies/ is a main folder."""
        (tmp_path / "movies").mkdir()
        assert is_main_folder(str(tmp_path))

    def test_false_for_empty(self, tmp_path):
        """Empty folder is not a main folder."""
        assert not is_main_folder(str(tmp_path))


class TestIsMediaDirectory:
    """Tests for is_media_directory detection."""

    def test_main_folder_recognized(self, tmp_media_tree):
        """Main folder is recognized as a media directory."""
        assert is_media_directory(str(tmp_media_tree))

    def test_tv_in_path_recognized(self, tmp_path):
        """Path containing 'tv' component is recognized."""
        d = tmp_path / "tv" / "SomeShow"
        d.mkdir(parents=True)
        assert is_media_directory(str(d))

    def test_movies_in_path_recognized(self, tmp_path):
        """Path containing 'movies' component is recognized."""
        d = tmp_path / "movies" / "SomeMovie"
        d.mkdir(parents=True)
        assert is_media_directory(str(d))

    def test_unrelated_path_rejected(self, tmp_path):
        """Path without media components is rejected."""
        d = tmp_path / "downloads"
        d.mkdir()
        assert not is_media_directory(str(d))


class TestIsScriptTempFile:
    """Tests for is_script_temp_file detection."""

    def test_langtag_file(self):
        """Langtag temp file is detected."""
        assert is_script_temp_file("video.langtag.mkv")

    def test_submerge_file(self):
        """Submerge temp file is detected."""
        assert is_script_temp_file("video.submerge.mkv")

    def test_regular_file(self):
        """Regular file is not detected as temp."""
        assert not is_script_temp_file("video.mkv")


@mark.usefixtures("default_config")
class TestCapitalize:
    """Tests for capitalize title-casing."""

    def test_title_case(self):
        """Basic title case is applied correctly."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            assert capitalize("the lord of the rings") == "The Lord of the Rings"

    def test_disabled(self):
        """Capitalization is skipped when disabled."""
        with patch("plex_organizer.utils.get_capitalize", return_value=False):
            assert capitalize("the lord of the rings") == "the lord of the rings"

    def test_minor_words_lowercase_except_first_and_last(self):
        """Minor words stay lowercase except at start and end."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            assert capitalize("a tale of two cities") == "A Tale of Two Cities"

    def test_empty_string(self):
        """Empty string returns empty string."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            assert capitalize("") == ""

    def test_single_word(self):
        """Single word is capitalized."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            assert capitalize("hello") == "Hello"


class TestFindCorrectedDirectory:
    """Tests for find_corrected_directory path truncation."""

    def test_movies_path_truncated(self):
        """Movie path is truncated to the movies root."""
        result = find_corrected_directory("/media/data/movies/SomeMovie/subfolder")
        assert result == "/media/data/movies"

    def test_tv_show_path_truncated(self):
        """TV path is truncated to the show root."""
        result = find_corrected_directory("/media/data/tv/Breaking Bad/Season 01")
        assert result == "/media/data/tv/Breaking Bad"

    def test_relative_movies(self):
        """Relative movie path is truncated correctly."""
        result = find_corrected_directory("data/movies/Film")
        assert result == os.path.join("data", "movies")

    def test_relative_tv(self):
        """Relative TV path is truncated correctly."""
        result = find_corrected_directory("data/tv/Show/Season 01")
        assert result == os.path.join("data", "tv", "Show")
