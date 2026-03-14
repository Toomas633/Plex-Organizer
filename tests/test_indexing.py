"""Tests for plex_organizer.indexing."""

from unittest.mock import patch
from pytest import mark

from plex_organizer.const import INDEX_FILENAME
from plex_organizer.indexing import (
    _is_indexed,
    _read_index,
    _write_index,
    collect_indexed_videos,
    index_root_for_path,
    mark_indexed,
    migrate_show_indexes_to_tv_root,
    prune_index,
    should_index_video,
)


class TestReadWriteIndex:
    """Tests for _read_index and _write_index round-trip."""

    def test_write_then_read(self, tmp_path):
        """Written index should be readable back identically."""
        idx_path = tmp_path / INDEX_FILENAME
        payload = {
            "files": {
                "Season 1/Show S01E01.mkv": {
                    "processed_at": "2025-01-01T00:00:00+00:00"
                }
            }
        }
        _write_index(str(idx_path), payload)
        result = _read_index(str(idx_path))
        assert result == payload

    def test_read_missing_file(self, tmp_path):
        """Reading a non-existent file returns empty index."""
        result = _read_index(str(tmp_path / "nonexistent.index"))
        assert result == {"files": {}}

    def test_read_invalid_json(self, tmp_path):
        """Invalid JSON returns empty index."""
        idx_path = tmp_path / INDEX_FILENAME
        idx_path.write_text("not json")
        result = _read_index(str(idx_path))
        assert result == {"files": {}}

    def test_read_non_dict(self, tmp_path):
        """Non-dict JSON returns empty index."""
        idx_path = tmp_path / INDEX_FILENAME
        idx_path.write_text('"just a string"')
        result = _read_index(str(idx_path))
        assert result == {"files": {}}

    def test_read_dict_without_files_key(self, tmp_path):
        """Dict without 'files' key wraps payload as files."""
        idx_path = tmp_path / INDEX_FILENAME
        idx_path.write_text('{"some_key": "val"}')
        result = _read_index(str(idx_path))
        assert result == {"files": {"some_key": "val"}}

    def test_read_files_key_is_not_dict(self, tmp_path):
        """Dict with non-dict 'files' value wraps payload as files."""
        idx_path = tmp_path / INDEX_FILENAME
        idx_path.write_text('{"files": "not_a_dict"}')
        result = _read_index(str(idx_path))
        assert result == {"files": {"files": "not_a_dict"}}

    def test_write_creates_missing_directory(self, tmp_path):
        """_write_index creates missing parent directories."""
        nested = tmp_path / "a" / "b" / INDEX_FILENAME
        _write_index(str(nested), {"files": {}})
        result = _read_index(str(nested))
        assert result == {"files": {}}


class TestMarkIndexed:
    """Tests for mark_indexed persistence."""

    def test_marks_file(self, tmp_path):
        """A marked file should be detected as indexed."""
        index_root = str(tmp_path)
        file_path = str(tmp_path / "Season 1" / "Show S01E01.mkv")
        mark_indexed(index_root, file_path)
        assert _is_indexed(index_root, file_path)

    def test_multiple_files(self, tmp_path):
        """Multiple files can be marked independently."""
        index_root = str(tmp_path)
        f1 = str(tmp_path / "Season 1" / "Show S01E01.mkv")
        f2 = str(tmp_path / "Season 1" / "Show S01E02.mkv")
        mark_indexed(index_root, f1)
        mark_indexed(index_root, f2)
        assert _is_indexed(index_root, f1)
        assert _is_indexed(index_root, f2)


class TestIsIndexed:  # pylint: disable=too-few-public-methods
    """Tests for _is_indexed checks."""

    def test_not_indexed_by_default(self, tmp_path):
        """Files are not indexed by default."""
        assert not _is_indexed(str(tmp_path), str(tmp_path / "file.mkv"))


@mark.usefixtures("default_config")
class TestShouldIndexVideo:
    """Tests for should_index_video layout validation."""

    def test_correct_movie_layout(self):
        """Movie in correct Name (Year).ext layout is accepted."""
        index_root = "/media/movies"
        file_path = "/media/movies/Inception (2010)/Inception (2010).mkv"
        assert should_index_video(index_root, file_path)

    def test_correct_movie_with_quality(self):
        """Movie with quality tag in correct layout is accepted (folder has no quality)."""
        index_root = "/media/movies"
        file_path = "/media/movies/Inception (2010)/Inception (2010) 1080p.mkv"
        assert should_index_video(index_root, file_path)

    def test_movie_quality_in_folder_rejected(self):
        """Movie folder that includes quality is rejected."""
        index_root = "/media/movies"
        file_path = "/media/movies/Inception (2010) 1080p/Inception (2010) 1080p.mkv"
        assert not should_index_video(index_root, file_path)

    def test_raw_movie_name_rejected(self):
        """Raw torrent-style movie name is rejected."""
        index_root = "/media/movies"
        file_path = (
            "/media/movies/Inception.2010.1080p.BluRay/Inception.2010.1080p.BluRay.mkv"
        )
        assert not should_index_video(index_root, file_path)

    def test_correct_tv_layout(self):
        """TV episode in correct Show SxxExx layout is accepted."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            index_root = "/media/tv"
            file_path = "/media/tv/Breaking Bad/Season 1/Breaking Bad S01E01.mkv"
            assert should_index_video(index_root, file_path)

    def test_raw_tv_name_rejected(self):
        """Raw torrent-style TV name is rejected."""
        index_root = "/media/tv"
        file_path = "/media/tv/Breaking Bad/Season 1/Breaking.Bad.S01E01.1080p.mkv"
        assert not should_index_video(index_root, file_path)

    def test_non_video_extension_rejected(self):
        """Non-video file extensions are rejected."""
        index_root = "/media/movies"
        file_path = "/media/movies/Inception (2010)/Inception (2010).srt"
        assert not should_index_video(index_root, file_path)

    def test_tv_wrong_season_folder(self):
        """Episode in wrong season folder is rejected."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            index_root = "/media/tv"
            file_path = "/media/tv/Show/Season 2/Show S01E01.mkv"
            assert not should_index_video(index_root, file_path)

    def test_tv_index_root_not_tv_root(self):
        """TV index_root deeper than TV root is rejected."""
        index_root = "/media/tv/Show"
        file_path = "/media/tv/Show/Season 1/Show S01E01.mkv"
        assert not should_index_video(index_root, file_path)

    def test_tv_bad_season_dir_name(self):
        """TV file under a non-Season folder is rejected."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            index_root = "/media/tv"
            file_path = "/media/tv/Show/Specials/Show S01E01.mkv"
            assert not should_index_video(index_root, file_path)

    def test_tv_wrong_show_prefix(self):
        """TV file not starting with show title is rejected."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            index_root = "/media/tv"
            file_path = "/media/tv/Show/Season 1/Other S01E01.mkv"
            assert not should_index_video(index_root, file_path)

    def test_tv_file_not_matching_name_regex(self):
        """TV file with show prefix but no SxxExx is rejected."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            index_root = "/media/tv"
            file_path = "/media/tv/Show/Season 1/Show random.mkv"
            assert not should_index_video(index_root, file_path)

    def test_tv_file_under_different_show(self):
        """TV file whose corrected dir differs from index_root is rejected."""
        with patch("plex_organizer.utils.get_capitalize", return_value=True):
            index_root = "/media/tv"
            file_path = "/media/tv/Other/Season 1/Show S01E01.mkv"
            assert not should_index_video(index_root, file_path)

    def test_movie_index_root_too_deep(self):
        """Movie index_root deeper than movies root is rejected."""
        index_root = "/media/movies/subfolder"
        file_path = "/media/movies/subfolder/Inception (2010)/Inception (2010).mkv"
        assert not should_index_video(index_root, file_path)

    def test_movie_file_in_wrong_subfolder(self):
        """Movie file in a mismatched subfolder of index_root is rejected."""
        index_root = "/media/movies"
        file_path = "/media/movies/Wrong Folder/Inception (2010).mkv"
        assert not should_index_video(index_root, file_path)

    def test_movie_file_directly_in_root(self):
        """Movie file directly in index_root (no subfolder) is rejected."""
        index_root = "/media/movies"
        file_path = "/media/movies/Inception (2010).mkv"
        assert not should_index_video(index_root, file_path)


class TestCollectIndexedVideos:
    """Tests for collect_indexed_videos discovery."""

    def test_empty_directory(self, tmp_path):
        """Empty directory yields empty result."""
        result = collect_indexed_videos(str(tmp_path))
        assert not result

    def test_unindexed_videos_are_false(self, tmp_path):
        """Videos not in the index are mapped to False."""
        movies_dir = tmp_path / "movies"
        movie_folder = movies_dir / "Inception (2010)"
        movie_folder.mkdir(parents=True)
        (movie_folder / "Inception (2010).mkv").write_text("video")
        result = collect_indexed_videos(str(movies_dir))
        for val in result.values():
            assert val is False

    @mark.usefixtures("default_config")
    def test_indexed_videos_are_true(self, tmp_path):
        """Videos in the index are mapped to True."""
        movies_dir = tmp_path / "movies"
        movie_folder = movies_dir / "Inception (2010)"
        movie_folder.mkdir(parents=True)
        video = movie_folder / "Inception (2010).mkv"
        video.write_text("video")
        mark_indexed(str(movies_dir), str(video))
        result = collect_indexed_videos(str(movies_dir))
        assert result.get(str(video)) is True

    def test_skips_plex_folders(self, tmp_path):
        """Plex Versions folders are excluded from collection."""
        plex_dir = tmp_path / "Plex Versions"
        plex_dir.mkdir()
        (plex_dir / "video.mkv").write_text("video")
        result = collect_indexed_videos(str(tmp_path))
        assert all("Plex Versions" not in k for k in result)

    def test_skips_script_temp_files(self, tmp_path):
        """Script temp files are excluded from collection."""
        (tmp_path / "video.langtag.mkv").write_text("temp")
        (tmp_path / "real.mkv").write_text("video")
        result = collect_indexed_videos(str(tmp_path))
        assert all("langtag" not in k for k in result)

    def test_oserror_marks_as_not_indexed(self, tmp_path):
        """OSError during index read marks the video as not indexed."""
        (tmp_path / "video.mkv").write_text("video")
        with patch("plex_organizer.indexing._is_indexed", side_effect=OSError("fail")):
            result = collect_indexed_videos(str(tmp_path))
        for val in result.values():
            assert val is False


class TestIndexRootForPath:
    """Tests for index_root_for_path resolution."""

    def test_tv_returns_tv_root(self):
        """TV path resolves to the TV root directory."""
        directory = "/media/tv"
        root = "/media/tv/Show/Season 1"
        result = index_root_for_path(directory, root)
        assert result == "/media/tv"

    def test_movies_returns_movies_root(self):
        """Movie path resolves to the movies root directory."""
        directory = "/media/movies"
        root = "/media/movies/subfolder"
        result = index_root_for_path(directory, root)
        assert result == "/media/movies"


class TestMigrateShowIndexesToTvRoot:
    """Tests for migrate_show_indexes_to_tv_root."""

    def test_merges_show_indexes(self, tmp_path):
        """Per-show index entries are merged into a single TV-root index."""
        tv_root = tmp_path / "tv"
        show_a = tv_root / "Show A"
        show_a.mkdir(parents=True)
        show_b = tv_root / "Show B"
        show_b.mkdir(parents=True)

        _write_index(
            str(show_a / INDEX_FILENAME),
            {"files": {"Season 1/Show A S01E01.mkv": {"processed_at": "2025-01-01"}}},
        )
        _write_index(
            str(show_b / INDEX_FILENAME),
            {"files": {"Season 1/Show B S01E01.mkv": {"processed_at": "2025-02-01"}}},
        )

        count = migrate_show_indexes_to_tv_root(str(tv_root))

        assert count == 2
        assert not (show_a / INDEX_FILENAME).exists()
        assert not (show_b / INDEX_FILENAME).exists()

        root_idx = _read_index(str(tv_root / INDEX_FILENAME))
        files = root_idx["files"]
        assert "Show A/Season 1/Show A S01E01.mkv" in files
        assert "Show B/Season 1/Show B S01E01.mkv" in files

    def test_no_show_indexes_returns_zero(self, tmp_path):
        """If no per-show index files exist, returns 0 and writes nothing."""
        tv_root = tmp_path / "tv"
        tv_root.mkdir()

        count = migrate_show_indexes_to_tv_root(str(tv_root))

        assert count == 0
        assert not (tv_root / INDEX_FILENAME).exists()

    def test_skips_root_index(self, tmp_path):
        """An existing TV-root index is not treated as a per-show index."""
        tv_root = tmp_path / "tv"
        tv_root.mkdir()

        _write_index(
            str(tv_root / INDEX_FILENAME),
            {
                "files": {
                    "Show/Season 1/Show S01E01.mkv": {"processed_at": "2025-01-01"}
                }
            },
        )

        count = migrate_show_indexes_to_tv_root(str(tv_root))
        assert count == 0

    def test_does_not_overwrite_existing_keys(self, tmp_path):
        """If the TV-root index already has a key, the per-show value is skipped."""
        tv_root = tmp_path / "tv"
        show = tv_root / "Show"
        show.mkdir(parents=True)

        _write_index(
            str(tv_root / INDEX_FILENAME),
            {"files": {"Show/Season 1/Show S01E01.mkv": {"processed_at": "root-ts"}}},
        )
        _write_index(
            str(show / INDEX_FILENAME),
            {"files": {"Season 1/Show S01E01.mkv": {"processed_at": "show-ts"}}},
        )

        migrate_show_indexes_to_tv_root(str(tv_root))

        root_idx = _read_index(str(tv_root / INDEX_FILENAME))
        assert (
            root_idx["files"]["Show/Season 1/Show S01E01.mkv"]["processed_at"]
            == "root-ts"
        )


class TestPruneIndex:
    """Tests for prune_index stale-entry removal."""

    def test_removes_stale_entries(self, tmp_path):
        """Entries for files that no longer exist are removed."""
        index_root = tmp_path / "movies"
        index_root.mkdir()
        movie_dir = index_root / "Test (2020)"
        movie_dir.mkdir()
        (movie_dir / "Test (2020).mkv").touch()

        _write_index(
            str(index_root / INDEX_FILENAME),
            {
                "files": {
                    "Test (2020)/Test (2020).mkv": {
                        "processed_at": "2025-01-01T00:00:00+00:00"
                    },
                    "Old Movie (2019)/Old Movie (2019).mkv": {
                        "processed_at": "2025-01-01T00:00:00+00:00"
                    },
                }
            },
        )

        removed = prune_index(str(index_root))
        assert removed == 1

        result = _read_index(str(index_root / INDEX_FILENAME))
        assert "Test (2020)/Test (2020).mkv" in result["files"]
        assert "Old Movie (2019)/Old Movie (2019).mkv" not in result["files"]

    def test_no_stale_entries(self, tmp_path):
        """When all entries are valid, nothing is removed."""
        index_root = tmp_path / "movies"
        index_root.mkdir()
        movie_dir = index_root / "Test (2020)"
        movie_dir.mkdir()
        (movie_dir / "Test (2020).mkv").touch()

        _write_index(
            str(index_root / INDEX_FILENAME),
            {
                "files": {
                    "Test (2020)/Test (2020).mkv": {
                        "processed_at": "2025-01-01T00:00:00+00:00"
                    },
                }
            },
        )

        removed = prune_index(str(index_root))
        assert removed == 0

    def test_empty_index(self, tmp_path):
        """Pruning an empty index returns zero."""
        index_root = tmp_path / "movies"
        index_root.mkdir()

        _write_index(str(index_root / INDEX_FILENAME), {"files": {}})
        removed = prune_index(str(index_root))
        assert removed == 0

    def test_missing_index_file(self, tmp_path):
        """Pruning when no index file exists returns zero."""
        index_root = tmp_path / "movies"
        index_root.mkdir()

        removed = prune_index(str(index_root))
        assert removed == 0

    def test_all_entries_stale(self, tmp_path):
        """When all entries are stale, all are removed."""
        index_root = tmp_path / "movies"
        index_root.mkdir()

        _write_index(
            str(index_root / INDEX_FILENAME),
            {
                "files": {
                    "Gone (2020)/Gone (2020).mkv": {
                        "processed_at": "2025-01-01T00:00:00+00:00"
                    },
                    "Also Gone (2021)/Also Gone (2021).mkv": {
                        "processed_at": "2025-01-01T00:00:00+00:00"
                    },
                }
            },
        )

        removed = prune_index(str(index_root))
        assert removed == 2

        result = _read_index(str(index_root / INDEX_FILENAME))
        assert result["files"] == {}
