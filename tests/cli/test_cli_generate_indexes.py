"""Tests for plex_organizer.cli.generate_indexes."""

from json import dumps
from unittest.mock import patch

from pytest import mark, raises

from plex_organizer.cli.generate_indexes import (
    _add_summary,
    _directories_to_scan,
    _is_video_candidate,
    _read_index_keys,
    _rel_key,
    _safe_mark_indexed,
    _safe_should_index_video,
    _get_or_load_index_keys,
    _scan_and_index_root,
    _scan_and_index_directory,
    generate_indexes,
    main,
)
from plex_organizer.dataclass import IndexSummary


class TestRelKey:
    """Tests for _rel_key."""

    def test_relative_path(self):
        """Returns a normalised relative key."""
        result = _rel_key("/media/movies", "/media/movies/Film (2020)/Film (2020).mkv")
        assert result == "Film (2020)/Film (2020).mkv"

    def test_same_directory(self):
        """File in the index root itself."""
        result = _rel_key("/media/movies", "/media/movies/video.mkv")
        assert result == "video.mkv"


class TestReadIndexKeys:
    """Tests for _read_index_keys."""

    def test_returns_keys_from_valid_index(self, tmp_path):
        """Reads keys from a well-formed index file."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text(dumps({"files": {"a.mkv": True, "b.mkv": True}}))
        result = _read_index_keys(str(tmp_path))
        assert result == {"a.mkv", "b.mkv"}

    def test_returns_empty_when_no_file(self, tmp_path):
        """Returns empty set when the index does not exist."""
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_on_invalid_json(self, tmp_path):
        """Returns empty set on malformed JSON."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text("{bad json")
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_when_payload_not_dict(self, tmp_path):
        """Returns empty set when top-level JSON is not a dict."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text(dumps([1, 2, 3]))
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_when_files_not_dict(self, tmp_path):
        """Returns empty set when 'files' value is not a dict."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text(dumps({"files": "nope"}))
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_when_no_files_key(self, tmp_path):
        """Returns empty set when 'files' key is missing."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text(dumps({"other": 1}))
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_on_oserror(self, tmp_path):
        """Returns empty set when reading triggers an OSError."""
        with patch("builtins.open", side_effect=OSError("fail")):
            assert _read_index_keys(str(tmp_path)) == set()


class TestDirectoriesToScan:
    """Tests for _directories_to_scan."""

    def test_main_root_with_tv_and_movies(self, tmp_path):
        """Returns tv/ and movies/ when both exist under start_dir."""
        (tmp_path / "tv").mkdir()
        (tmp_path / "movies").mkdir()
        result = _directories_to_scan(str(tmp_path))
        assert len(result) == 2
        assert any("tv" in d for d in result)
        assert any("movies" in d for d in result)

    def test_tv_folder_directly(self, tmp_path):
        """Accepts a folder named 'tv' directly."""
        tv = tmp_path / "tv"
        tv.mkdir()
        result = _directories_to_scan(str(tv))
        assert result == [str(tv)]

    def test_movies_folder_directly(self, tmp_path):
        """Accepts a folder named 'movies' directly."""
        movies = tmp_path / "movies"
        movies.mkdir()
        result = _directories_to_scan(str(movies))
        assert result == [str(movies)]

    def test_show_under_tv(self, tmp_path):
        """Accepts a tv/<Show> path (parent is 'tv')."""
        tv = tmp_path / "tv"
        show = tv / "MyShow"
        show.mkdir(parents=True)
        result = _directories_to_scan(str(show))
        assert result == [str(show)]

    def test_invalid_root_raises(self, tmp_path):
        """Raises ValueError for an unrecognised directory structure."""
        random = tmp_path / "random"
        random.mkdir()
        with raises(ValueError, match="Invalid root"):
            _directories_to_scan(str(random))


class TestAddSummary:  # pylint: disable=too-few-public-methods
    """Tests for _add_summary."""

    def test_adds_two_summaries(self):
        """Fields from both summaries are added."""
        a = IndexSummary(total_videos=2, eligible_videos=1, newly_indexed=1)
        b = IndexSummary(total_videos=3, eligible_videos=2, newly_indexed=0)
        result = _add_summary(a, b)
        assert result == IndexSummary(
            total_videos=5, eligible_videos=3, newly_indexed=1
        )


class TestIsVideoCandidate:
    """Tests for _is_video_candidate."""

    def test_video_extension_accepted(self):
        """MKV file is a video candidate."""
        assert _is_video_candidate("movie.mkv") is True

    def test_non_video_rejected(self):
        """SRT file is not a video candidate."""
        assert _is_video_candidate("sub.srt") is False

    def test_script_temp_file_rejected(self):
        """Organizer temp files are rejected even with video ext."""
        assert _is_video_candidate("video.langtag.mkv") is False


class TestSafeWrappers:
    """Tests for _safe_should_index_video and _safe_mark_indexed."""

    @patch(
        "plex_organizer.cli.generate_indexes.should_index_video",
        return_value=True,
    )
    def test_safe_should_index_returns_result(self, _mock):
        """Delegates to should_index_video."""
        assert _safe_should_index_video("/root", "/root/v.mkv") is True

    @patch(
        "plex_organizer.cli.generate_indexes.should_index_video",
        side_effect=OSError,
    )
    def test_safe_should_index_returns_false_on_error(self, _mock):
        """Returns False when should_index_video raises OSError."""
        assert _safe_should_index_video("/root", "/root/v.mkv") is False

    @patch("plex_organizer.cli.generate_indexes.mark_indexed")
    def test_safe_mark_returns_true(self, _mock):
        """Returns True when mark_indexed succeeds."""
        assert _safe_mark_indexed("/root", "/root/v.mkv") is True

    @patch(
        "plex_organizer.cli.generate_indexes.mark_indexed",
        side_effect=OSError,
    )
    def test_safe_mark_returns_false_on_error(self, _mock):
        """Returns False when mark_indexed raises OSError."""
        assert _safe_mark_indexed("/root", "/root/v.mkv") is False


class TestGetOrLoadIndexKeys:
    """Tests for _get_or_load_index_keys caching."""

    def test_uses_cache_on_hit(self):
        """Returns cached set without reading disk."""
        cache = {"/root": {"a.mkv"}}
        result = _get_or_load_index_keys(cache, "/root")
        assert result == {"a.mkv"}

    @patch(
        "plex_organizer.cli.generate_indexes._read_index_keys",
        return_value={"b.mkv"},
    )
    def test_reads_and_caches_on_miss(self, mock_read):
        """Reads from disk on a cache miss and stores the result."""
        cache = {}
        result = _get_or_load_index_keys(cache, "/root")
        assert result == {"b.mkv"}
        assert cache["/root"] == {"b.mkv"}
        mock_read.assert_called_once_with("/root")


@mark.usefixtures("default_config")
class TestScanAndIndexRoot:
    """Tests for _scan_and_index_root."""

    @patch(
        "plex_organizer.cli.generate_indexes._safe_mark_indexed",
        return_value=True,
    )
    @patch(
        "plex_organizer.cli.generate_indexes._safe_should_index_video",
        return_value=True,
    )
    @patch(
        "plex_organizer.cli.generate_indexes.index_root_for_path",
        return_value="/media/movies",
    )
    def test_indexes_eligible_video(self, _ir, _si, _mark):
        """Eligible video that is not yet cached gets indexed."""
        cache = {"/media/movies": set()}
        result = _scan_and_index_root(
            "/media/movies", "/media/movies", ["film.mkv", "readme.txt"], cache
        )
        assert result.total_videos == 1
        assert result.eligible_videos == 1
        assert result.newly_indexed == 1

    @patch(
        "plex_organizer.cli.generate_indexes.index_root_for_path",
        return_value="/media/movies",
    )
    def test_skips_plex_folder(self, _ir):
        """Plex-managed folders return an empty summary."""
        result = _scan_and_index_root(
            "/media/movies",
            "/media/movies/Plex Versions",
            ["video.mkv"],
            {},
        )
        assert result == IndexSummary(0, 0, 0)

    @patch(
        "plex_organizer.cli.generate_indexes._safe_should_index_video",
        return_value=False,
    )
    @patch(
        "plex_organizer.cli.generate_indexes.index_root_for_path",
        return_value="/media/movies",
    )
    def test_not_eligible_skipped(self, _ir, _si):
        """Video that is not eligible is counted but not indexed."""
        cache = {"/media/movies": set()}
        result = _scan_and_index_root(
            "/media/movies", "/media/movies", ["film.mkv"], cache
        )
        assert result.total_videos == 1
        assert result.eligible_videos == 0
        assert result.newly_indexed == 0

    @patch(
        "plex_organizer.cli.generate_indexes._safe_should_index_video",
        return_value=True,
    )
    @patch(
        "plex_organizer.cli.generate_indexes.index_root_for_path",
        return_value="/media/movies",
    )
    def test_already_cached_key_not_reindexed(self, _ir, _si):
        """Video whose key is already in cache is not re-indexed."""
        cache = {"/media/movies": {"film.mkv"}}
        result = _scan_and_index_root(
            "/media/movies", "/media/movies", ["film.mkv"], cache
        )
        assert result.total_videos == 1
        assert result.eligible_videos == 1
        assert result.newly_indexed == 0

    @patch(
        "plex_organizer.cli.generate_indexes._safe_mark_indexed",
        return_value=False,
    )
    @patch(
        "plex_organizer.cli.generate_indexes._safe_should_index_video",
        return_value=True,
    )
    @patch(
        "plex_organizer.cli.generate_indexes.index_root_for_path",
        return_value="/media/movies",
    )
    def test_mark_failure_not_counted(self, _ir, _si, _mark):
        """Failed mark_indexed does not increment newly_indexed."""
        cache = {"/media/movies": set()}
        result = _scan_and_index_root(
            "/media/movies", "/media/movies", ["film.mkv"], cache
        )
        assert result.total_videos == 1
        assert result.eligible_videos == 1
        assert result.newly_indexed == 0


@mark.usefixtures("default_config")
class TestScanAndIndexDirectory:  # pylint: disable=too-few-public-methods
    """Tests for _scan_and_index_directory."""

    @patch(
        "plex_organizer.cli.generate_indexes._scan_and_index_root",
        return_value=IndexSummary(2, 1, 1),
    )
    @patch(
        "plex_organizer.cli.generate_indexes.walk",
        return_value=[("/media/movies", [], ["a.mkv", "b.mkv"])],
    )
    def test_aggregates_walk_results(self, _walk, _scan):
        """Summary is accumulated from walk iterations."""
        result = _scan_and_index_directory("/media/movies", {})
        assert result.total_videos == 2


@mark.usefixtures("default_config")
class TestGenerateIndexes:
    """Tests for generate_indexes."""

    @patch("plex_organizer.cli.generate_indexes._scan_and_index_directory")
    @patch("plex_organizer.cli.generate_indexes._directories_to_scan")
    @patch("plex_organizer.cli.generate_indexes.ensure_config_exists")
    def test_valid_directory(self, _cfg, mock_dirs, mock_scan, tmp_path, capsys):
        """Runs scan for each directory and prints summary."""
        mock_dirs.return_value = [str(tmp_path)]
        mock_scan.return_value = IndexSummary(5, 3, 2)
        result = generate_indexes(str(tmp_path))
        assert result.total_videos == 5
        assert result.newly_indexed == 2
        out = capsys.readouterr().out
        assert "Videos found: 5" in out
        assert "Newly indexed: 2" in out

    def test_not_a_directory_raises(self, tmp_path):
        """Raises ValueError when start_dir is not an existing directory."""
        with raises(ValueError, match="Not a directory"):
            generate_indexes(str(tmp_path / "nope"))

    @patch("plex_organizer.cli.generate_indexes._scan_and_index_directory")
    @patch("plex_organizer.cli.generate_indexes.ensure_config_exists")
    def test_multiple_directories(self, _cfg, mock_scan, tmp_path):
        """Processes both tv/ and movies/ for a main root."""
        (tmp_path / "tv").mkdir()
        (tmp_path / "movies").mkdir()
        mock_scan.return_value = IndexSummary(3, 2, 1)
        result = generate_indexes(str(tmp_path))
        assert mock_scan.call_count == 2
        assert result.total_videos == 6
        assert result.newly_indexed == 2


@mark.usefixtures("default_config")
class TestCLIMain:
    """Tests for the main() CLI entrypoint."""

    @patch(
        "plex_organizer.cli.generate_indexes.generate_indexes",
        return_value=IndexSummary(5, 3, 2),
    )
    @patch(
        "plex_organizer.cli.generate_indexes.ArgumentParser.parse_args",
    )
    def test_success_returns_zero(self, mock_args, mock_gen):
        """Returns 0 on success."""
        mock_args.return_value = type("Args", (), {"root": "/media"})()
        assert main() == 0
        mock_gen.assert_called_once_with("/media")

    @patch(
        "plex_organizer.cli.generate_indexes.generate_indexes",
        side_effect=ValueError("Invalid root"),
    )
    @patch(
        "plex_organizer.cli.generate_indexes.ArgumentParser.parse_args",
    )
    def test_value_error_returns_two(self, mock_args, _gen, capsys):
        """Returns 2 and prints message on ValueError."""
        mock_args.return_value = type("Args", (), {"root": "/bad"})()
        assert main() == 2
        out = capsys.readouterr().out
        assert "Invalid root" in out
