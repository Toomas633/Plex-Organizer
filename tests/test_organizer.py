"""Tests for plex_organizer.organizer helper functions."""

from sys import modules
from unittest.mock import patch
from pytest import mark

from plex_organizer.organizer import (
    _get_lock,
    _process_directory,
    main,
)
from plex_organizer.pipeline import (
    analyze_video_languages,
    _delete_unwanted_directories,
    delete_empty_directories,
    delete_unwanted_files,
    get_video_files_to_process,
    move_directories,
)


@mark.usefixtures("default_config")
class TestDeleteUnwantedFiles:
    """Test _delete_unwanted_files from organizer."""

    def test_deletes_non_video_files(self, tmp_path):
        """Non-video files are deleted while videos are preserved."""
        (tmp_path / "video.mkv").write_text("video")
        (tmp_path / "readme.txt").write_text("text")
        (tmp_path / "info.nfo").write_text("nfo")

        delete_unwanted_files(str(tmp_path), ["video.mkv", "readme.txt", "info.nfo"])

        assert (tmp_path / "video.mkv").exists()
        assert not (tmp_path / "readme.txt").exists()
        assert not (tmp_path / "info.nfo").exists()

    def test_deletes_sample_files(self, tmp_path):
        """Files with 'sample' in the name are deleted."""
        (tmp_path / "sample.mkv").write_text("video")
        (tmp_path / "real.mkv").write_text("video")

        delete_unwanted_files(str(tmp_path), ["sample.mkv", "real.mkv"])

        assert not (tmp_path / "sample.mkv").exists()
        assert (tmp_path / "real.mkv").exists()

    def test_preserves_index_files(self, tmp_path):
        """Index files are preserved during cleanup."""
        (tmp_path / "data.index").write_text("index")
        delete_unwanted_files(str(tmp_path), ["data.index"])
        assert (tmp_path / "data.index").exists()

    def test_preserves_qb_temp_files(self, tmp_path):
        """qBittorrent in-progress files are preserved."""
        (tmp_path / "file.mkv.!qB").write_text("downloading")
        delete_unwanted_files(str(tmp_path), ["file.mkv.!qB"])
        assert (tmp_path / "file.mkv.!qB").exists()

    def test_preserves_script_temp_files(self, tmp_path):
        """Organizer temporary langtag files are preserved."""
        (tmp_path / "video.langtag.mkv").write_text("temp")
        delete_unwanted_files(str(tmp_path), ["video.langtag.mkv"])
        assert (tmp_path / "video.langtag.mkv").exists()


@mark.usefixtures("default_config")
class TestDeleteUnwantedDirectories:
    """Test _delete_unwanted_directories from organizer."""

    def test_deletes_subs_folder(self, tmp_path):
        """Subs folder is deleted recursively."""
        subs = tmp_path / "Subs"
        subs.mkdir()
        (subs / "subtitle.srt").write_text("sub")

        _delete_unwanted_directories(str(tmp_path))
        assert not subs.exists()

    def test_deletes_extras_folder(self, tmp_path):
        """Extras folder is deleted."""
        extras = tmp_path / "Extras"
        extras.mkdir()

        _delete_unwanted_directories(str(tmp_path))
        assert not extras.exists()

    def test_preserves_normal_folders(self, tmp_path):
        """Non-unwanted folders are preserved."""
        season = tmp_path / "Season 1"
        season.mkdir()

        _delete_unwanted_directories(str(tmp_path))
        assert season.exists()


@mark.usefixtures("default_config")
class TestDeleteEmptyDirectories:
    """Test _delete_empty_directories from organizer."""

    def test_deletes_empty_subdirs(self, tmp_path):
        """Empty subdirectories are removed."""
        movies_dir = tmp_path / "movies"
        movies_dir.mkdir()
        empty = movies_dir / "Empty Folder"
        empty.mkdir()

        delete_empty_directories(str(movies_dir))
        assert not empty.exists()

    def test_keeps_non_empty_dirs(self, tmp_path):
        """Directories with files are kept."""
        movies_dir = tmp_path / "movies"
        movies_dir.mkdir()
        non_empty = movies_dir / "Has Files"
        non_empty.mkdir()
        (non_empty / "video.mkv").write_text("video")

        delete_empty_directories(str(movies_dir))
        assert non_empty.exists()


@mark.usefixtures("default_config")
class TestGetVideoFilesToProcess:
    """Tests for _get_video_files_to_process filtering."""

    def test_returns_only_video_files(self):
        """Only files with video extensions are returned."""
        files = ["video.mkv", "video.mp4", "readme.txt", "sub.srt"]
        result = get_video_files_to_process("/media/movies", files, {})
        assert sorted(result) == ["video.mkv", "video.mp4"]

    def test_excludes_indexed_files(self):
        """Already-indexed files are excluded."""
        files = ["video1.mkv", "video2.mkv"]
        indexed = {"/media/movies/video1.mkv": True}
        result = get_video_files_to_process("/media/movies", files, indexed)
        assert result == ["video2.mkv"]

    def test_includes_non_indexed_files(self):
        """Files marked as not indexed are included."""
        files = ["video.mkv"]
        indexed = {"/media/movies/video.mkv": False}
        result = get_video_files_to_process("/media/movies", files, indexed)
        assert result == ["video.mkv"]


@mark.usefixtures("default_config")
class TestGetLock:
    """Tests for _get_lock advisory locking."""

    def teardown_method(self):
        """Close and reset the module-level lock handle after each test."""
        _mod = modules["plex_organizer.organizer"]
        handle = getattr(_mod, "_lock_handle", None)
        if handle is not None:
            handle.close()
            setattr(_mod, "_lock_handle", None)

    @patch("plex_organizer.organizer.flock")
    @patch("plex_organizer.organizer.data_dir", return_value="/tmp/po")
    def test_acquires_lock_immediately(self, _mock_dd, mock_flock, tmp_path):
        """Lock acquired on the first try with no waiting."""
        with patch("plex_organizer.organizer.data_dir", return_value=str(tmp_path)):
            _get_lock()
        assert mock_flock.call_count >= 0

    @patch("plex_organizer.organizer.sleep")
    @patch("plex_organizer.organizer.log_debug")
    def test_retries_on_lock_contention(self, mock_debug, mock_sleep, tmp_path):
        """Retries and logs when the lock is held by another process."""
        call_count = 0

        def flock_side_effect(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("Resource temporarily unavailable")

        with (
            patch("plex_organizer.organizer.data_dir", return_value=str(tmp_path)),
            patch("plex_organizer.organizer.flock", side_effect=flock_side_effect),
        ):
            _get_lock()

        assert mock_sleep.call_count == 2
        assert mock_debug.call_count == 2


@mark.usefixtures("default_config")
class TestAnalyzeVideoLanguages:
    """Tests for _analyze_video_languages."""

    @patch("plex_organizer.pipeline.tag_audio_track_languages")
    @patch("plex_organizer.pipeline.get_enable_audio_tagging", return_value=False)
    def test_skips_when_disabled(self, _mock_cfg, mock_tag):
        """No tagging occurs when audio tagging is disabled."""
        analyze_video_languages("/media/movies", ["video.mkv"])
        mock_tag.assert_not_called()

    @patch("plex_organizer.pipeline.tag_audio_track_languages")
    @patch("plex_organizer.pipeline.get_enable_audio_tagging", return_value=True)
    def test_tags_normal_video(self, _mock_cfg, mock_tag):
        """Tags audio languages for normal video files."""
        analyze_video_languages("/media/movies", ["video.mkv"])
        mock_tag.assert_called_once_with("/media/movies/video.mkv")

    @patch("plex_organizer.pipeline.tag_audio_track_languages")
    @patch("plex_organizer.pipeline.get_enable_audio_tagging", return_value=True)
    def test_skips_plex_folder(self, _mock_cfg, mock_tag):
        """Plex-managed folders are skipped."""
        analyze_video_languages("/media/movies/Plex Versions", ["video.mkv"])
        mock_tag.assert_not_called()

    @patch("plex_organizer.pipeline.tag_audio_track_languages")
    @patch("plex_organizer.pipeline.get_enable_audio_tagging", return_value=True)
    def test_skips_script_temp_files(self, _mock_cfg, mock_tag):
        """Organizer temp files are skipped."""
        analyze_video_languages("/media/movies", ["video.langtag.mkv"])
        mock_tag.assert_not_called()


@mark.usefixtures("default_config")
class TestDeleteUnwantedFilesErrors:  # pylint: disable=too-few-public-methods
    """Tests for _delete_unwanted_files OSError handling."""

    @patch("plex_organizer.pipeline.log_error")
    def test_logs_oserror_on_remove(self, mock_log_error, tmp_path):
        """OSError during file removal is logged, not raised."""
        bad_file = tmp_path / "readme.txt"
        bad_file.write_text("text")
        with patch(
            "plex_organizer.pipeline.remove", side_effect=OSError("perm denied")
        ):
            delete_unwanted_files(str(tmp_path), ["readme.txt"])
        mock_log_error.assert_called_once()
        assert "perm denied" in mock_log_error.call_args[0][0]


@mark.usefixtures("default_config")
class TestDeleteUnwantedDirErrors:  # pylint: disable=too-few-public-methods
    """Tests for _delete_unwanted_directories OSError handling."""

    @patch("plex_organizer.pipeline.log_error")
    @patch("plex_organizer.pipeline.rmtree", side_effect=OSError("busy"))
    def test_logs_oserror_on_rmtree(self, _mock_rm, mock_log_error, tmp_path):
        """OSError during directory removal is logged, not raised."""
        subs = tmp_path / "Subs"
        subs.mkdir()
        _delete_unwanted_directories(str(tmp_path))
        mock_log_error.assert_called_once()
        assert "busy" in mock_log_error.call_args[0][0]


@mark.usefixtures("default_config")
class TestMoveDirectories:
    """Tests for _move_directories."""

    @patch("plex_organizer.pipeline.mark_indexed")
    @patch("plex_organizer.pipeline.should_index_video", return_value=True)
    @patch("plex_organizer.pipeline.index_root_for_path", return_value="/media/movies")
    @patch(
        "plex_organizer.pipeline.movie_move",
        return_value="/media/movies/Film (2020).mkv",
    )
    def test_moves_movie_and_indexes(self, mock_move, _ir, _si, mock_mark):
        """Movie file is moved and marked indexed."""
        move_directories("/media/movies", "/media/movies/raw", ["film.mkv"])
        mock_move.assert_called_once_with(
            "/media/movies", "/media/movies/raw", "film.mkv"
        )
        mock_mark.assert_called_once_with(
            "/media/movies", "/media/movies/Film (2020).mkv"
        )

    @patch("plex_organizer.pipeline.mark_indexed")
    @patch("plex_organizer.pipeline.should_index_video", return_value=False)
    @patch("plex_organizer.pipeline.index_root_for_path", return_value="/media/movies")
    @patch("plex_organizer.pipeline.movie_move", return_value="/media/movies/Film.mkv")
    def test_does_not_mark_when_should_index_false(self, _mv, _ir, _si, mock_mark):
        """File not marked when should_index_video returns False."""
        move_directories("/media/movies", "/media/movies/raw", ["film.mkv"])
        mock_mark.assert_not_called()

    @patch("plex_organizer.pipeline.mark_indexed")
    @patch("plex_organizer.pipeline.should_index_video", side_effect=OSError("fail"))
    @patch("plex_organizer.pipeline.index_root_for_path", return_value="/media/movies")
    @patch("plex_organizer.pipeline.movie_move", return_value="/media/movies/Film.mkv")
    def test_oserror_in_try_mark_swallowed(self, _mv, _ir, _si, mock_mark):
        """OSError in _try_mark is silently swallowed."""
        move_directories("/media/movies", "/media/movies/raw", ["film.mkv"])
        mock_mark.assert_not_called()

    @patch("plex_organizer.pipeline.index_root_for_path")
    @patch("plex_organizer.pipeline.movie_move")
    def test_skips_plex_folder(self, mock_move, mock_ir):
        """Plex-managed folders are skipped entirely."""
        move_directories("/media/movies", "/media/movies/Plex Versions", ["video.mkv"])
        mock_move.assert_not_called()
        mock_ir.assert_not_called()

    @patch("plex_organizer.pipeline.mark_indexed")
    @patch("plex_organizer.pipeline.should_index_video", return_value=True)
    @patch("plex_organizer.pipeline.index_root_for_path", return_value="/media/tv")
    @patch("plex_organizer.pipeline.tv_move", return_value="/media/tv/Show/S01E01.mkv")
    def test_moves_tv_file(self, mock_tv, _ir, _si, _mock_mark):
        """TV file is dispatched to tv_move."""
        move_directories("/media/tv", "/media/tv/Show/Season 01", ["ep.mkv"])
        mock_tv.assert_called_once_with("/media/tv/Show/Season 01", "ep.mkv")

    @patch("plex_organizer.pipeline.mark_indexed")
    @patch("plex_organizer.pipeline.should_index_video", return_value=True)
    @patch("plex_organizer.pipeline.index_root_for_path", return_value="/media/movies")
    @patch("plex_organizer.pipeline.movie_move", return_value="/media/movies/Film.mkv")
    def test_skips_script_temp_files(self, mock_move, _ir, _si, _mark):
        """Temp files created by the script are skipped."""
        move_directories("/media/movies", "/media/movies/raw", ["video.langtag.mkv"])
        mock_move.assert_not_called()


@mark.usefixtures("default_config")
class TestProcessDirectory:  # pylint: disable=too-few-public-methods
    """Tests for _process_directory orchestration."""

    @patch("plex_organizer.organizer.delete_empty_directories")
    @patch("plex_organizer.organizer.move_directories")
    @patch("plex_organizer.organizer.delete_unwanted_files")
    @patch("plex_organizer.organizer.analyze_video_languages")
    @patch("plex_organizer.organizer.get_video_files_to_process", return_value=[])
    @patch(
        "plex_organizer.organizer.walk", return_value=[("/media/movies", [], ["v.mkv"])]
    )
    @patch("plex_organizer.organizer.sync_subtitles_in_directory")
    @patch("plex_organizer.organizer.fetch_subtitles_in_directory")
    @patch("plex_organizer.organizer.merge_subtitles_in_directory")
    @patch(
        "plex_organizer.organizer.collect_indexed_videos",
        return_value={"/media/movies/v.mkv": False},
    )
    def test_calls_pipeline_in_order(
        self,
        mock_collect,
        mock_merge,
        mock_fetch,
        mock_sync,
        _mock_walk,
        _mock_vids,
        _mock_analyze,
        _mock_del_files,
        _mock_move,
        mock_del_empty,
    ):  # pylint: disable=too-many-arguments,too-many-positional-arguments
        """All pipeline steps are invoked for a directory."""
        _process_directory("/media/movies")
        mock_collect.assert_called_once()
        mock_merge.assert_called_once()
        mock_fetch.assert_called_once()
        mock_sync.assert_called_once()
        mock_del_empty.assert_called_once()


@mark.usefixtures("default_config")
class TestMain:
    """Tests for the main() CLI entrypoint."""

    @patch("plex_organizer.organizer._process_directory")
    @patch("plex_organizer.organizer._get_lock")
    @patch("plex_organizer.organizer.check_clear_log")
    @patch("plex_organizer.organizer.ensure_config_exists")
    @patch("plex_organizer.organizer.is_media_directory", return_value=True)
    @patch("plex_organizer.organizer.is_main_folder", return_value=True)
    @patch("plex_organizer.organizer.remove_torrent")
    @patch("plex_organizer.organizer.log_debug")
    def test_main_folder_mode(
        self,
        _log,
        mock_rm,
        _mf,
        _md,
        _cfg,
        _clr,
        _lock,
        mock_proc,
    ):
        """Main processes tv/ and movies/ when start_dir is a main folder."""
        main("/media", "abc123")
        mock_rm.assert_called_once_with("abc123")
        assert mock_proc.call_count == 2
        mock_proc.assert_any_call("/media/tv")
        mock_proc.assert_any_call("/media/movies")

    @patch("plex_organizer.organizer._process_directory")
    @patch("plex_organizer.organizer._get_lock")
    @patch("plex_organizer.organizer.check_clear_log")
    @patch("plex_organizer.organizer.ensure_config_exists")
    @patch("plex_organizer.organizer.is_media_directory", return_value=True)
    @patch("plex_organizer.organizer.is_main_folder", return_value=False)
    @patch("plex_organizer.organizer.log_debug")
    def test_single_directory_mode(
        self,
        _log,
        _mf,
        _md,
        _cfg,
        _clr,
        _lock,
        mock_proc,
    ):
        """Single directory processed when not a main folder."""
        main("/media/tv/Show", None)
        mock_proc.assert_called_once_with("/media/tv/Show")

    @patch("plex_organizer.organizer._process_directory")
    @patch("plex_organizer.organizer._get_lock")
    @patch("plex_organizer.organizer.check_clear_log")
    @patch("plex_organizer.organizer.ensure_config_exists")
    @patch("plex_organizer.organizer.is_media_directory", return_value=False)
    @patch("plex_organizer.organizer.log_debug")
    def test_non_media_directory_exits(
        self,
        mock_log,
        _md,
        _cfg,
        _clr,
        _lock,
        mock_proc,
    ):
        """Non-media directories cause early return without processing."""
        main("/tmp/random", None)
        mock_proc.assert_not_called()
        assert any("not a recognised" in str(c) for c in mock_log.call_args_list)

    @patch("plex_organizer.organizer.log_error")
    @patch("plex_organizer.organizer._get_lock")
    @patch("plex_organizer.organizer.check_clear_log")
    @patch("plex_organizer.organizer.ensure_config_exists")
    @patch("plex_organizer.organizer.is_media_directory", side_effect=OSError("disk"))
    @patch("plex_organizer.organizer.log_debug")
    def test_oserror_caught_and_logged(
        self,
        _log,
        _md,
        _cfg,
        _clr,
        _lock,
        mock_err,
    ):
        """Top-level OSError is caught and logged."""
        main("/media", None)
        mock_err.assert_called_once()
        assert "disk" in mock_err.call_args[0][0]

    @patch("plex_organizer.organizer._process_directory")
    @patch("plex_organizer.organizer._get_lock")
    @patch("plex_organizer.organizer.check_clear_log")
    @patch("plex_organizer.organizer.ensure_config_exists")
    @patch("plex_organizer.organizer.is_media_directory", return_value=True)
    @patch("plex_organizer.organizer.is_main_folder", return_value=False)
    @patch("plex_organizer.organizer.log_debug")
    def test_no_torrent_hash(self, _log, _mf, _md, _cfg, _clr, _lock, mock_proc):
        """Processing runs without torrent removal when hash is None."""
        main("/media/tv/Show", None)
        mock_proc.assert_called_once_with("/media/tv/Show")
