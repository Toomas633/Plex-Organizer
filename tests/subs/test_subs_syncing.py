"""Tests for plex_organizer.subs.syncing."""

from os import path as os_path
from unittest.mock import MagicMock, patch
from pytest import mark

from plex_organizer.subs.syncing import (
    _build_remux_cmd,
    _extract_stream,
    _file_hash,
    _get_sub_stream_metadata,
    _make_temp,
    _remux_with_synced_subs,
    _run_ffsubsync,
    _sub_codec_for,
    _try_sync_stream,
    _sync_video_subtitles,
    sync_subtitles_in_directory,
)


class TestFileHash:  # pylint: disable=too-few-public-methods
    """Tests for _file_hash."""

    def test_returns_sha256(self, tmp_path):
        """SHA-256 hex digest is returned for a file."""
        p = tmp_path / "f.txt"
        p.write_bytes(b"hello")
        h = _file_hash(str(p))
        assert (
            len(h) == 64
            and h == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )


class TestMakeTemp:  # pylint: disable=too-few-public-methods
    """Tests for _make_temp."""

    def test_creates_temp_file(self, tmp_path):
        """Temp file is created with the requested suffix."""
        path = _make_temp(str(tmp_path), ".srt")
        assert path.endswith(".srt")
        assert os_path.isfile(path)


@mark.usefixtures("default_config")
class TestExtractStream:
    """Tests for _extract_stream."""

    @patch("plex_organizer.subs.syncing.run_cmd")
    def test_success(self, mock_run):
        """Returns True when ffmpeg exits with 0."""
        mock_run.return_value = MagicMock(returncode=0)
        assert _extract_stream("/usr/bin/ffmpeg", "/v.mkv", 0, "/out.srt", "srt")

    @patch("plex_organizer.subs.syncing.log_error")
    @patch("plex_organizer.subs.syncing.run_cmd")
    def test_failure(self, mock_run, mock_log):
        """Returns False and logs when ffmpeg fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        assert not _extract_stream("/usr/bin/ffmpeg", "/v.mkv", 0, "/out.srt", "srt")
        mock_log.assert_called_once()


@mark.usefixtures("default_config")
class TestRunFfsubsync:
    """Tests for _run_ffsubsync."""

    @patch("plex_organizer.subs.syncing.run_cmd")
    def test_success(self, mock_run):
        """Returns True when ffsubsync exits successfully."""
        mock_run.return_value = MagicMock(returncode=0)
        assert _run_ffsubsync("ffsubsync", "/v.mkv", "/in.srt", "/out.srt")

    @patch("plex_organizer.subs.syncing.log_error")
    @patch("plex_organizer.subs.syncing.run_cmd")
    def test_failure(self, mock_run, mock_log):
        """Returns False and logs when ffsubsync fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="err")
        assert not _run_ffsubsync("ffsubsync", "/v.mkv", "/in.srt", "/out.srt")
        mock_log.assert_called_once()


@mark.usefixtures("default_config")
class TestGetSubStreamMetadata:
    """Tests for _get_sub_stream_metadata."""

    @patch("plex_organizer.subs.syncing.probe_streams_json", return_value=[])
    def test_empty(self, _probe):
        """Returns empty list when no subtitle streams exist."""
        assert not _get_sub_stream_metadata("/v.mkv")

    @patch(
        "plex_organizer.subs.syncing.probe_streams_json",
        return_value=[
            {"codec_name": "subrip", "tags": {"language": "eng", "title": "English"}},
            {"codec_name": "hdmv_pgs_subtitle", "tags": {}},
        ],
    )
    def test_mixed_streams(self, _probe):
        """Correctly identifies text vs bitmap subtitle streams."""
        result = _get_sub_stream_metadata("/v.mkv")
        assert len(result) == 2
        assert result[0]["is_text"] is True
        assert result[0]["language"] == "eng"
        assert result[1]["is_text"] is False


class TestSubCodecFor:
    """Tests for _sub_codec_for."""

    def test_mp4_always_mov_text(self):
        """MP4 containers always use mov_text codec."""
        assert _sub_codec_for({"codec": "subrip"}, True) == "mov_text"

    def test_ass_codec(self):
        """ASS codec is preserved for non-MP4 containers."""
        assert _sub_codec_for({"codec": "ass"}, False) == "ass"

    def test_default_srt(self):
        """Non-ASS codecs default to SRT for non-MP4 containers."""
        assert _sub_codec_for({"codec": "subrip"}, False) == "srt"


@mark.usefixtures("default_config")
class TestBuildRemuxCmd:
    """Tests for _build_remux_cmd."""

    @patch("plex_organizer.subs.syncing.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_basic_structure(self, _ff):
        """Command includes synced input, output path, and language metadata."""
        metadata = [
            {"index": 0, "codec": "subrip", "language": "eng", "title": "English"},
            {"index": 1, "codec": "ass", "language": "spa", "title": ""},
        ]
        synced = {0: "/synced0.srt"}
        cmd = _build_remux_cmd("/v.mkv", synced, metadata, "/tmp/out.mkv")
        assert "/synced0.srt" in cmd
        assert "/tmp/out.mkv" == cmd[-1]
        assert any("language=eng" in a for a in cmd)

    @patch("plex_organizer.subs.syncing.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_mp4_uses_mov_text(self, _ff):
        """MP4 output includes mov_text codec."""
        metadata = [
            {"index": 0, "codec": "mov_text", "language": "eng", "title": ""},
        ]
        synced = {0: "/synced.srt"}
        cmd = _build_remux_cmd("/v.mp4", synced, metadata, "/tmp/out.mp4")
        assert "mov_text" in cmd


@mark.usefixtures("default_config")
class TestRemuxWithSyncedSubs:
    """Tests for _remux_with_synced_subs."""

    @patch("plex_organizer.subs.syncing.cleanup_paths")
    @patch("plex_organizer.subs.syncing.replace_and_restore_timestamps")
    @patch("plex_organizer.subs.syncing.run_cmd")
    @patch("plex_organizer.subs.syncing.create_temp_output", return_value="/tmp/o.mkv")
    @patch("plex_organizer.subs.syncing.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_success(self, _ff, _tmp, mock_run, mock_rep, _cleanup):
        """Successful remux replaces original and restores timestamps."""
        mock_run.return_value = MagicMock(returncode=0)
        metadata = [{"index": 0, "codec": "subrip", "language": "eng", "title": ""}]
        assert _remux_with_synced_subs("/v.mkv", {0: "/s.srt"}, metadata)
        mock_rep.assert_called_once()

    @patch("plex_organizer.subs.syncing.cleanup_paths")
    @patch("plex_organizer.subs.syncing.log_error")
    @patch("plex_organizer.subs.syncing.run_cmd")
    @patch("plex_organizer.subs.syncing.create_temp_output", return_value="/tmp/o.mkv")
    @patch("plex_organizer.subs.syncing.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_failure(self, _ff, _tmp, mock_run, mock_log, _cleanup):
        """Failed remux logs error and returns False."""
        mock_run.return_value = MagicMock(returncode=1, stderr="err")
        metadata = [{"index": 0, "codec": "subrip", "language": "eng", "title": ""}]
        assert not _remux_with_synced_subs("/v.mkv", {0: "/s.srt"}, metadata)
        mock_log.assert_called_once()

    @patch("plex_organizer.subs.syncing.create_temp_output", return_value="/tmp/o.mkv")
    @patch("plex_organizer.subs.syncing._build_remux_cmd", return_value=[])
    def test_returns_false_when_cmd_empty(self, _build, _tmp):
        """Returns False immediately when _build_remux_cmd returns empty list."""
        assert not _remux_with_synced_subs("/v.mkv", {}, [])


@mark.usefixtures("default_config")
class TestTrySyncStream:
    """Tests for _try_sync_stream."""

    @patch("plex_organizer.subs.syncing._file_hash", side_effect=["aaa", "bbb"])
    @patch("plex_organizer.subs.syncing._run_ffsubsync", return_value=True)
    @patch("plex_organizer.subs.syncing._extract_stream", return_value=True)
    @patch(
        "plex_organizer.subs.syncing._make_temp", side_effect=["/ext.srt", "/syn.srt"]
    )
    def test_changed(self, _mk, _ext, _sync, _hash):
        """Returns synced path when hashes differ."""
        meta = {"index": 0, "codec": "subrip"}
        result, temps = _try_sync_stream("/ff", "/ffsub", "/v.mkv", meta, "/dir")
        assert result == "/syn.srt"
        assert len(temps) == 2

    @patch("plex_organizer.subs.syncing._file_hash", side_effect=["aaa", "aaa"])
    @patch("plex_organizer.subs.syncing._run_ffsubsync", return_value=True)
    @patch("plex_organizer.subs.syncing._extract_stream", return_value=True)
    @patch(
        "plex_organizer.subs.syncing._make_temp", side_effect=["/ext.srt", "/syn.srt"]
    )
    @patch("plex_organizer.subs.syncing.log_debug")
    def test_unchanged(self, _log, _mk, _ext, _sync, _hash):
        """Returns None when hashes match (already in sync)."""
        meta = {"index": 0, "codec": "subrip"}
        result, _ = _try_sync_stream("/ff", "/ffsub", "/v.mkv", meta, "/dir")
        assert result is None

    @patch("plex_organizer.subs.syncing._extract_stream", return_value=False)
    @patch(
        "plex_organizer.subs.syncing._make_temp", side_effect=["/ext.srt", "/syn.srt"]
    )
    def test_extract_fail(self, _mk, _ext):
        """Returns None when stream extraction fails."""
        meta = {"index": 0, "codec": "subrip"}
        result, _ = _try_sync_stream("/ff", "/ffsub", "/v.mkv", meta, "/dir")
        assert result is None

    @patch("plex_organizer.subs.syncing._run_ffsubsync", return_value=False)
    @patch("plex_organizer.subs.syncing._extract_stream", return_value=True)
    @patch(
        "plex_organizer.subs.syncing._make_temp", side_effect=["/ext.srt", "/syn.srt"]
    )
    def test_sync_fail(self, _mk, _ext, _sync):
        """Returns None when ffsubsync fails."""
        meta = {"index": 0, "codec": "subrip"}
        result, _ = _try_sync_stream("/ff", "/ffsub", "/v.mkv", meta, "/dir")
        assert result is None

    @patch("plex_organizer.subs.syncing._file_hash", side_effect=["x", "y"])
    @patch("plex_organizer.subs.syncing._run_ffsubsync", return_value=True)
    @patch("plex_organizer.subs.syncing._extract_stream", return_value=True)
    @patch(
        "plex_organizer.subs.syncing._make_temp", side_effect=["/ext.ass", "/syn.ass"]
    )
    def test_ass_codec(self, _mk, _ext, _sync, _hash):
        """ASS streams use .ass extension for temp files."""
        meta = {"index": 0, "codec": "ass"}
        result, _ = _try_sync_stream("/ff", "/ffsub", "/v.mkv", meta, "/dir")
        assert result == "/syn.ass"


@mark.usefixtures("default_config")
class TestSyncVideoSubtitles:
    """Tests for _sync_video_subtitles."""

    def test_nonexistent_file(self):
        """Returns early for non-existent file."""
        _sync_video_subtitles("/nonexistent.mkv")

    @patch("plex_organizer.subs.syncing.is_plex_folder", return_value=True)
    def test_plex_folder_skipped(self, _plex, tmp_path):
        """Plex-managed folders are skipped."""
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _sync_video_subtitles(str(vid))

    @patch("plex_organizer.subs.syncing.shutil_which", return_value=None)
    @patch("plex_organizer.subs.syncing.get_ffmpeg", return_value="/ff")
    def test_no_ffsubsync(self, _ff, _which, tmp_path):
        """Returns early when ffsubsync is not installed."""
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _sync_video_subtitles(str(vid))

    @patch("plex_organizer.subs.syncing.log_debug")
    @patch("plex_organizer.subs.syncing._get_sub_stream_metadata", return_value=[])
    @patch(
        "plex_organizer.subs.syncing.shutil_which", return_value="/usr/bin/ffsubsync"
    )
    @patch("plex_organizer.subs.syncing.get_ffmpeg", return_value="/ff")
    def test_no_text_streams(self, _ff, _which, _meta, mock_log, tmp_path):
        """Logs debug message when no text subtitle streams found."""
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _sync_video_subtitles(str(vid))
        assert any("No text subtitle" in str(c) for c in mock_log.call_args_list)

    @patch("plex_organizer.subs.syncing.cleanup_paths")
    @patch("plex_organizer.subs.syncing.log_debug")
    @patch(
        "plex_organizer.subs.syncing._try_sync_stream",
        return_value=(None, ["/tmp1"]),
    )
    @patch(
        "plex_organizer.subs.syncing._get_sub_stream_metadata",
        return_value=[
            {
                "index": 0,
                "codec": "subrip",
                "language": "eng",
                "title": "",
                "is_text": True,
            }
        ],
    )
    @patch(
        "plex_organizer.subs.syncing.shutil_which", return_value="/usr/bin/ffsubsync"
    )
    @patch("plex_organizer.subs.syncing.get_ffmpeg", return_value="/ff")
    def test_all_already_synced(
        self, _ff, _which, _meta, _try, mock_log, _cleanup, tmp_path
    ):
        """Logs when all subtitles are already in sync."""
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _sync_video_subtitles(str(vid))
        assert any("already in sync" in str(c) for c in mock_log.call_args_list)

    @patch("plex_organizer.subs.syncing.cleanup_paths")
    @patch("plex_organizer.subs.syncing._remux_with_synced_subs")
    @patch("plex_organizer.subs.syncing.log_debug")
    @patch(
        "plex_organizer.subs.syncing._try_sync_stream",
        return_value=("/synced.srt", ["/tmp1", "/tmp2"]),
    )
    @patch(
        "plex_organizer.subs.syncing._get_sub_stream_metadata",
        return_value=[
            {
                "index": 0,
                "codec": "subrip",
                "language": "eng",
                "title": "",
                "is_text": True,
            }
        ],
    )
    @patch(
        "plex_organizer.subs.syncing.shutil_which", return_value="/usr/bin/ffsubsync"
    )
    @patch("plex_organizer.subs.syncing.get_ffmpeg", return_value="/ff")
    def test_remuxes_synced(
        self, _ff, _which, _meta, _try, _log, mock_remux, _cleanup, tmp_path
    ):
        """Remuxes when synced streams differ from originals."""
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _sync_video_subtitles(str(vid))
        mock_remux.assert_called_once()


@mark.usefixtures("default_config")
class TestSyncSubtitlesInDirectory:
    """Tests for sync_subtitles_in_directory."""

    @patch("plex_organizer.subs.syncing.get_sync_subtitles", return_value=False)
    def test_noop_when_disabled(self, _cfg):
        """No-op when sync_subtitles is disabled."""
        sync_subtitles_in_directory("/media", ["/media/v.mkv"])

    @patch("plex_organizer.subs.syncing.get_sync_subtitles", return_value=True)
    def test_skips_plex_folder(self, _cfg):
        """Plex-managed directories are skipped."""
        sync_subtitles_in_directory("/media/Plex Versions", [])

    @patch("plex_organizer.subs.syncing._sync_video_subtitles")
    @patch("plex_organizer.subs.syncing.log_debug")
    @patch("plex_organizer.subs.syncing.get_sync_subtitles", return_value=True)
    def test_processes_videos(self, _cfg, _log, mock_sync):
        """Each video path is processed."""
        sync_subtitles_in_directory("/media", ["/media/v.mkv"])
        mock_sync.assert_called_once()

    @patch("plex_organizer.subs.syncing._sync_video_subtitles")
    @patch("plex_organizer.subs.syncing.log_debug")
    @patch("plex_organizer.subs.syncing.get_sync_subtitles", return_value=True)
    def test_skips_non_video(self, _cfg, _log, mock_sync):
        """Non-video extension paths are skipped."""
        sync_subtitles_in_directory("/media", ["/media/readme.txt"])
        mock_sync.assert_not_called()

    @patch("plex_organizer.subs.syncing.log_error")
    @patch(
        "plex_organizer.subs.syncing._sync_video_subtitles",
        side_effect=OSError("disk"),
    )
    @patch("plex_organizer.subs.syncing.log_debug")
    @patch("plex_organizer.subs.syncing.get_sync_subtitles", return_value=True)
    def test_exception_logged(self, _cfg, _log, _sync, mock_err):
        """Exceptions are caught and logged."""
        sync_subtitles_in_directory("/media", ["/media/v.mkv"])
        mock_err.assert_called_once()
