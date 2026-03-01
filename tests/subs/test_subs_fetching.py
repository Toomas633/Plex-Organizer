"""Tests for plex_organizer.subs.fetching."""

from unittest.mock import MagicMock, patch
from pytest import mark

from plex_organizer.subs.fetching import (
    _download_subtitles,
    _embed_srts,
    _fetch_subtitles_for_video,
    _missing_languages,
    fetch_subtitles_in_directory,
)


@mark.usefixtures("default_config")
class TestMissingLanguages:
    """Tests for _missing_languages."""

    @patch(
        "plex_organizer.subs.fetching.probe_subtitle_languages",
        return_value={"eng"},
    )
    def test_already_present(self, _probe):
        """Language already embedded is not missing."""
        assert _missing_languages("/v.mkv", ["eng"]) == []

    @patch(
        "plex_organizer.subs.fetching.probe_subtitle_languages",
        return_value={"eng"},
    )
    def test_some_missing(self, _probe):
        """Only languages not embedded are returned."""
        assert _missing_languages("/v.mkv", ["eng", "spa"]) == ["spa"]

    @patch(
        "plex_organizer.subs.fetching.probe_subtitle_languages",
        return_value=set(),
    )
    def test_all_missing(self, _probe):
        """All languages missing when nothing embedded."""
        assert _missing_languages("/v.mkv", ["eng", "spa"]) == ["eng", "spa"]


@mark.usefixtures("default_config")
class TestDownloadSubtitles:
    """Tests for _download_subtitles."""

    @patch("plex_organizer.subs.fetching.log_error")
    @patch(
        "plex_organizer.subs.fetching.scan_video",
        side_effect=ValueError("bad video"),
    )
    def test_scan_error_returns_empty(self, _scan, mock_log):
        """Returns empty list when scan_video fails."""
        result = _download_subtitles("/v.mkv", ["eng"])
        assert not result
        mock_log.assert_called_once()

    @patch("plex_organizer.subs.fetching.download_best_subtitles", return_value={})
    @patch("plex_organizer.subs.fetching.scan_video")
    def test_no_subtitles_found(self, _scan, _dl):
        """Returns empty list when no subtitles found."""
        result = _download_subtitles("/v.mkv", ["eng"])
        assert not result

    @patch("plex_organizer.subs.fetching.log_error")
    def test_invalid_language_code(self, _mock_log):
        """Invalid language code is logged and skipped."""
        with patch("plex_organizer.subs.fetching.scan_video") as mock_scan:
            mock_scan.return_value = MagicMock()
            with patch(
                "plex_organizer.subs.fetching.download_best_subtitles",
                return_value={},
            ):
                result = _download_subtitles("/v.mkv", ["zzz_bad"])
        assert isinstance(result, list)

    @patch("plex_organizer.subs.fetching.os_path.isfile", return_value=True)
    @patch("plex_organizer.subs.fetching.save_subtitles")
    @patch("plex_organizer.subs.fetching.download_best_subtitles")
    @patch("plex_organizer.subs.fetching.scan_video")
    def test_successful_download(self, mock_scan, mock_dl, mock_save, _isfile):
        """Returns (srt_path, lang) tuples on successful download."""
        video = MagicMock()
        mock_scan.return_value = video
        sub = MagicMock()
        sub.language = MagicMock()
        sub.language.__str__ = MagicMock(return_value="en")
        sub.language.alpha3 = "eng"
        mock_dl.return_value = {video: [sub]}
        mock_save.return_value = [sub]
        result = _download_subtitles("/video.mkv", ["eng"])
        assert len(result) == 1
        assert result[0][1] == "eng"

    @patch("plex_organizer.subs.fetching.save_subtitles", return_value=[])
    @patch("plex_organizer.subs.fetching.download_best_subtitles")
    @patch("plex_organizer.subs.fetching.scan_video")
    def test_save_returns_empty(self, mock_scan, mock_dl, _save):
        """Returns empty when save_subtitles returns nothing."""
        video = MagicMock()
        mock_scan.return_value = video
        sub = MagicMock()
        mock_dl.return_value = {video: [sub]}
        result = _download_subtitles("/video.mkv", ["eng"])
        assert not result


@mark.usefixtures("default_config")
class TestEmbedSrts:
    """Tests for _embed_srts."""

    def test_noop_on_empty_list(self):
        """Does nothing when srt_files is empty."""
        _embed_srts("/v.mkv", [])

    @patch("plex_organizer.subs.fetching.cleanup_paths")
    @patch("plex_organizer.subs.fetching.replace_and_restore_timestamps")
    @patch("plex_organizer.subs.fetching.run_cmd")
    @patch(
        "plex_organizer.subs.fetching.create_temp_output", return_value="/tmp/out.mkv"
    )
    @patch(
        "plex_organizer.subs.fetching.build_ffmpeg_base_cmd", return_value=["ffmpeg"]
    )
    @patch("plex_organizer.subs.fetching.probe_subtitle_stream_count", return_value=0)
    @patch("plex_organizer.subs.fetching.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_successful_embed(
        self, _ff, _count, _cmd, _tmp, mock_run, _replace, _cleanup
    ):
        """Embeds SRT files and restores timestamps."""
        mock_run.return_value = MagicMock(returncode=0)
        _embed_srts("/video.mkv", [("/sub.srt", "eng")])
        _replace.assert_called_once()

    @patch("plex_organizer.subs.fetching.cleanup_paths")
    @patch("plex_organizer.subs.fetching.log_error")
    @patch("plex_organizer.subs.fetching.run_cmd")
    @patch(
        "plex_organizer.subs.fetching.create_temp_output", return_value="/tmp/out.mkv"
    )
    @patch(
        "plex_organizer.subs.fetching.build_ffmpeg_base_cmd", return_value=["ffmpeg"]
    )
    @patch("plex_organizer.subs.fetching.probe_subtitle_stream_count", return_value=0)
    @patch("plex_organizer.subs.fetching.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_ffmpeg_failure_logs(
        self, _ff, _count, _cmd, _tmp, mock_run, mock_log, _cleanup
    ):
        """Logs error when ffmpeg fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="fail")
        _embed_srts("/video.mkv", [("/sub.srt", "eng")])
        mock_log.assert_called_once()

    @patch("plex_organizer.subs.fetching.cleanup_paths")
    @patch("plex_organizer.subs.fetching.replace_and_restore_timestamps")
    @patch("plex_organizer.subs.fetching.run_cmd")
    @patch(
        "plex_organizer.subs.fetching.create_temp_output", return_value="/tmp/out.mp4"
    )
    @patch(
        "plex_organizer.subs.fetching.build_ffmpeg_base_cmd", return_value=["ffmpeg"]
    )
    @patch("plex_organizer.subs.fetching.probe_subtitle_stream_count", return_value=1)
    @patch("plex_organizer.subs.fetching.get_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_mp4_adds_mov_text(
        self, _ff, _count, _base, _tmp, mock_run, _replace, _cleanup
    ):
        """MP4 files get mov_text codec for subtitle streams."""
        mock_run.return_value = MagicMock(returncode=0)
        _embed_srts("/video.mp4", [("/sub.srt", "eng")])
        cmd = mock_run.call_args[0][0]
        assert any("mov_text" in str(a) for a in cmd)


@mark.usefixtures("default_config")
class TestFetchSubtitlesForVideo:
    """Tests for _fetch_subtitles_for_video."""

    @patch("plex_organizer.subs.fetching.log_error")
    def test_file_not_found(self, mock_log):
        """Logs error when video doesn't exist."""
        _fetch_subtitles_for_video("/nonexistent.mkv", ["eng"])
        mock_log.assert_called_once()

    def test_skips_plex_folder(self, tmp_path):
        """Plex-managed folders are skipped."""
        _fetch_subtitles_for_video(str(tmp_path / "Plex Versions" / "v.mkv"), ["eng"])

    @patch("plex_organizer.subs.fetching._missing_languages", return_value=[])
    @patch("plex_organizer.subs.fetching.log_debug")
    def test_skips_when_all_present(self, mock_log, _missing, tmp_path):
        """Skips when all requested languages are already embedded."""
        video = tmp_path / "video.mkv"
        video.write_text("x")
        _fetch_subtitles_for_video(str(video), ["eng"])
        assert any("already embedded" in str(c) for c in mock_log.call_args_list)

    @patch("plex_organizer.subs.fetching._embed_srts")
    @patch(
        "plex_organizer.subs.fetching._download_subtitles",
        return_value=[("/sub.srt", "eng")],
    )
    @patch("plex_organizer.subs.fetching._missing_languages", return_value=["eng"])
    @patch("plex_organizer.subs.fetching.log_debug")
    def test_downloads_and_embeds(self, _log, _missing, _dl, mock_embed, tmp_path):
        """Downloads and embeds missing subtitles."""
        video = tmp_path / "video.mkv"
        video.write_text("x")
        _fetch_subtitles_for_video(str(video), ["eng"])
        mock_embed.assert_called_once()

    @patch(
        "plex_organizer.subs.fetching._download_subtitles",
        return_value=[],
    )
    @patch("plex_organizer.subs.fetching._missing_languages", return_value=["eng"])
    @patch("plex_organizer.subs.fetching.log_debug")
    def test_no_subtitles_found_online(self, mock_log, _missing, _dl, tmp_path):
        """Logs when no subtitles found online."""
        video = tmp_path / "video.mkv"
        video.write_text("x")
        _fetch_subtitles_for_video(str(video), ["eng"])
        assert any("No subtitles found" in str(c) for c in mock_log.call_args_list)


@mark.usefixtures("default_config")
class TestFetchSubtitlesInDirectory:
    """Tests for fetch_subtitles_in_directory."""

    @patch("plex_organizer.subs.fetching.get_fetch_subtitles", return_value=[])
    def test_noop_when_disabled(self, _cfg):
        """Does nothing when no languages configured."""
        fetch_subtitles_in_directory("/media", ["/media/v.mkv"])

    @patch("plex_organizer.subs.fetching.get_fetch_subtitles", return_value=["eng"])
    def test_skips_plex_folder(self, _cfg):
        """Plex-managed directories are skipped."""
        fetch_subtitles_in_directory("/media/Plex Versions", [])

    @patch("plex_organizer.subs.fetching._fetch_subtitles_for_video")
    @patch("plex_organizer.subs.fetching.log_debug")
    @patch("plex_organizer.subs.fetching.get_fetch_subtitles", return_value=["eng"])
    def test_processes_video_paths(self, _cfg, _log, mock_fetch):
        """Processes each video path."""
        fetch_subtitles_in_directory("/media", ["/media/v.mkv"])
        mock_fetch.assert_called_once()

    @patch("plex_organizer.subs.fetching._fetch_subtitles_for_video")
    @patch("plex_organizer.subs.fetching.log_debug")
    @patch("plex_organizer.subs.fetching.get_fetch_subtitles", return_value=["eng"])
    def test_skips_non_video_paths(self, _cfg, _log, mock_fetch):
        """Non-video extension paths are skipped."""
        fetch_subtitles_in_directory("/media", ["/media/readme.txt"])
        mock_fetch.assert_not_called()

    @patch("plex_organizer.subs.fetching.log_error")
    @patch(
        "plex_organizer.subs.fetching._fetch_subtitles_for_video",
        side_effect=OSError("disk"),
    )
    @patch("plex_organizer.subs.fetching.log_debug")
    @patch("plex_organizer.subs.fetching.get_fetch_subtitles", return_value=["eng"])
    def test_exception_logged_and_continues(self, _cfg, _log, _fetch, mock_err):
        """Exceptions are caught and logged."""
        fetch_subtitles_in_directory("/media", ["/media/v.mkv"])
        mock_err.assert_called_once()
