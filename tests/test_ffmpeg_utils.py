"""Tests for plex_organizer.ffmpeg_utils."""

from os import utime
from subprocess import CompletedProcess
from unittest.mock import patch
from pytest import approx, mark

from plex_organizer.ffmpeg_utils import (
    build_ffmpeg_base_cmd,
    cleanup_paths,
    create_temp_output,
    extract_wav,
    ffmpeg_input_cmd,
    get_ffmpeg,
    get_ffprobe,
    probe_duration_seconds,
    probe_json,
    probe_streams_json,
    probe_subtitle_languages,
    probe_subtitle_stream_count,
    probe_video_quality,
    replace_and_restore_timestamps,
    run_cmd,
)


@mark.usefixtures("default_config")
class TestBinaryResolution:
    """Tests for binary resolution helpers."""

    @patch(
        "plex_organizer.ffmpeg_utils._resolve_binaries",
        return_value=("/usr/bin/ffmpeg", "/usr/bin/ffprobe"),
    )
    def test_get_ffmpeg(self, _mock):
        """get_ffmpeg returns the first element of the resolved tuple."""
        assert get_ffmpeg() == "/usr/bin/ffmpeg"

    @patch(
        "plex_organizer.ffmpeg_utils._resolve_binaries",
        return_value=("/usr/bin/ffmpeg", "/usr/bin/ffprobe"),
    )
    def test_get_ffprobe(self, _mock):
        """get_ffprobe returns the second element of the resolved tuple."""
        assert get_ffprobe() == "/usr/bin/ffprobe"


class TestRunCmd:
    """Tests for run_cmd subprocess wrapper."""

    def test_captures_stdout(self):
        """Captures stdout from a simple command."""
        result = run_cmd(["echo", "hello"])
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_non_zero_exit_code(self):
        """Non-zero exit code is captured without raising."""
        result = run_cmd(["false"])
        assert result.returncode != 0


@mark.usefixtures("default_config")
class TestProbeJson:
    """Tests for probe_json."""

    @patch("plex_organizer.ffmpeg_utils.run_cmd")
    @patch("plex_organizer.ffmpeg_utils.get_ffprobe", return_value="/usr/bin/ffprobe")
    def test_returns_parsed_json(self, _ffprobe, mock_run):
        """Returns parsed JSON payload on success."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout='{"streams": []}', stderr=""
        )
        result = probe_json("/video.mkv")
        assert result == {"streams": []}

    @patch("plex_organizer.ffmpeg_utils.run_cmd")
    @patch("plex_organizer.ffmpeg_utils.get_ffprobe", return_value="/usr/bin/ffprobe")
    def test_returns_empty_dict_on_failure(self, _ffprobe, mock_run):
        """Returns empty dict when ffprobe exits non-zero."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        assert probe_json("/video.mkv") == {}

    @patch("plex_organizer.ffmpeg_utils.run_cmd")
    @patch("plex_organizer.ffmpeg_utils.get_ffprobe", return_value="/usr/bin/ffprobe")
    def test_returns_empty_dict_on_invalid_json(self, _ffprobe, mock_run):
        """Returns empty dict on malformed JSON."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="{bad json", stderr=""
        )
        assert probe_json("/video.mkv") == {}

    @patch("plex_organizer.ffmpeg_utils.run_cmd")
    @patch("plex_organizer.ffmpeg_utils.get_ffprobe", return_value="/usr/bin/ffprobe")
    def test_extra_args_passed_through(self, _ffprobe, mock_run):
        """Extra args are appended to the ffprobe command."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="{}", stderr=""
        )
        probe_json("/video.mkv", extra_args=["-show_streams"])
        cmd = mock_run.call_args[0][0]
        assert "-show_streams" in cmd

    @patch("plex_organizer.ffmpeg_utils.run_cmd")
    @patch("plex_organizer.ffmpeg_utils.get_ffprobe", return_value="/usr/bin/ffprobe")
    def test_returns_empty_dict_on_empty_stdout(self, _ffprobe, mock_run):
        """Returns empty dict when stdout is empty."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        assert probe_json("/video.mkv") == {}


@mark.usefixtures("default_config")
class TestProbeStreamsJson:
    """Tests for probe_streams_json."""

    @patch("plex_organizer.ffmpeg_utils.probe_json")
    def test_returns_stream_dicts(self, mock_probe):
        """Returns list of stream dicts from payload."""
        mock_probe.return_value = {"streams": [{"index": 0, "codec_name": "subrip"}]}
        result = probe_streams_json("/video.mkv")
        assert len(result) == 1
        assert result[0]["codec_name"] == "subrip"

    @patch("plex_organizer.ffmpeg_utils.probe_json", return_value={})
    def test_returns_empty_on_no_streams(self, _mock):
        """Returns empty list when no streams key."""
        assert probe_streams_json("/video.mkv") == []

    @patch("plex_organizer.ffmpeg_utils.probe_json")
    def test_filters_non_dict_streams(self, mock_probe):
        """Non-dict entries in streams are filtered out."""
        mock_probe.return_value = {"streams": ["bad", {"index": 0}]}
        result = probe_streams_json("/video.mkv")
        assert len(result) == 1

    @patch("plex_organizer.ffmpeg_utils.probe_json")
    def test_returns_empty_when_streams_not_list(self, mock_probe):
        """Returns empty list when streams value is not a list."""
        mock_probe.return_value = {"streams": "not-a-list"}
        assert probe_streams_json("/video.mkv") == []


@mark.usefixtures("default_config")
class TestProbeSubtitleLanguages:
    """Tests for probe_subtitle_languages."""

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_language_codes(self, mock_streams):
        """Returns set of language codes from subtitle streams."""
        mock_streams.return_value = [
            {"tags": {"language": "eng"}},
            {"tags": {"language": "spa"}},
        ]
        assert probe_subtitle_languages("/v.mkv") == {"eng", "spa"}

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_excludes_und_and_unknown(self, mock_streams):
        """Excludes und/unknown/0 language codes."""
        mock_streams.return_value = [
            {"tags": {"language": "und"}},
            {"tags": {"language": "unknown"}},
            {"tags": {"language": "0"}},
            {"tags": {"language": "eng"}},
        ]
        assert probe_subtitle_languages("/v.mkv") == {"eng"}

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_handles_missing_tags(self, mock_streams):
        """Streams without tags produce no language."""
        mock_streams.return_value = [{}]
        assert probe_subtitle_languages("/v.mkv") == set()


@mark.usefixtures("default_config")
class TestProbeDurationSeconds:
    """Tests for probe_duration_seconds."""

    @patch("plex_organizer.ffmpeg_utils.probe_json")
    def test_returns_float_duration(self, mock_probe):
        """Returns parsed float duration."""
        mock_probe.return_value = {"format": {"duration": "3600.5"}}
        assert probe_duration_seconds("/v.mkv") == approx(3600.5)

    @patch("plex_organizer.ffmpeg_utils.probe_json", return_value={})
    def test_returns_none_on_missing(self, _mock):
        """Returns None when format/duration is missing."""
        assert probe_duration_seconds("/v.mkv") is None

    @patch("plex_organizer.ffmpeg_utils.probe_json")
    def test_returns_none_on_invalid_value(self, mock_probe):
        """Returns None when duration is not numeric."""
        mock_probe.return_value = {"format": {"duration": "N/A"}}
        assert probe_duration_seconds("/v.mkv") is None

    @patch("plex_organizer.ffmpeg_utils.probe_json")
    def test_returns_none_when_duration_is_none(self, mock_probe):
        """Returns None when duration key value is None."""
        mock_probe.return_value = {"format": {"duration": None}}
        assert probe_duration_seconds("/v.mkv") is None


@mark.usefixtures("default_config")
class TestProbeSubtitleStreamCount:
    """Tests for probe_subtitle_stream_count."""

    @patch("plex_organizer.ffmpeg_utils.run_cmd")
    @patch("plex_organizer.ffmpeg_utils.get_ffprobe", return_value="/usr/bin/ffprobe")
    def test_counts_lines(self, _ffprobe, mock_run):
        """Returns number of non-empty lines from ffprobe."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="0\n1\n2\n", stderr=""
        )
        assert probe_subtitle_stream_count("/v.mkv") == 3

    @patch("plex_organizer.ffmpeg_utils.run_cmd")
    @patch("plex_organizer.ffmpeg_utils.get_ffprobe", return_value="/usr/bin/ffprobe")
    def test_returns_zero_on_failure(self, _ffprobe, mock_run):
        """Returns 0 when ffprobe fails."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )
        assert probe_subtitle_stream_count("/v.mkv") == 0


@mark.usefixtures("default_config")
class TestExtractWav:
    """Tests for extract_wav."""

    @patch("plex_organizer.ffmpeg_utils.run_cmd")
    def test_success(self, mock_run):
        """Returns True on successful extraction."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        assert extract_wav("/usr/bin/ffmpeg", "/v.mkv", "/out.wav") is True

    @patch("plex_organizer.ffmpeg_utils.log_error")
    @patch("plex_organizer.ffmpeg_utils.run_cmd")
    def test_failure_logs_error(self, mock_run, mock_log):
        """Returns False and logs error on failure."""
        mock_run.return_value = CompletedProcess(
            args=[], returncode=1, stdout="", stderr="conversion failed"
        )
        assert extract_wav("/usr/bin/ffmpeg", "/v.mkv", "/out.wav") is False
        mock_log.assert_called_once()


class TestFfmpegInputCmd:
    """Tests for ffmpeg_input_cmd."""

    def test_basic_command(self):
        """Returns standard ffmpeg header."""
        cmd = ffmpeg_input_cmd("/usr/bin/ffmpeg", "/video.mkv")
        assert cmd[0] == "/usr/bin/ffmpeg"
        assert "-i" in cmd
        assert "/video.mkv" in cmd

    def test_with_pre_input(self):
        """Pre-input args appear before -i."""
        cmd = ffmpeg_input_cmd("/usr/bin/ffmpeg", "/v.mkv", ["-ss", "30"])
        i_idx = cmd.index("-i")
        ss_idx = cmd.index("-ss")
        assert ss_idx < i_idx


class TestBuildFfmpegBaseCmd:
    """Tests for build_ffmpeg_base_cmd."""

    def test_no_extra_inputs(self):
        """With no extra inputs, maps only input 0."""
        cmd = build_ffmpeg_base_cmd("/usr/bin/ffmpeg", "/v.mkv", [])
        assert "-map" in cmd
        assert cmd.count("-i") == 1

    def test_with_extra_inputs(self):
        """Extra inputs are added with -i and mapped."""
        cmd = build_ffmpeg_base_cmd(
            "/usr/bin/ffmpeg", "/v.mkv", ["/sub1.srt", "/sub2.srt"]
        )
        assert cmd.count("-i") == 3
        maps = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-map"]
        assert "0" in maps
        assert "1" in maps
        assert "2" in maps


class TestCreateTempOutput:  # pylint: disable=too-few-public-methods
    """Tests for create_temp_output."""

    def test_creates_file_with_correct_extension(self, tmp_path):
        """Created temp file has the same extension as the input."""
        video = tmp_path / "movie.mkv"
        video.write_text("x")
        result = create_temp_output(str(video), prefix=".test.")
        assert result.endswith(".mkv")
        assert ".test." in result


class TestCleanupPaths:
    """Tests for cleanup_paths."""

    def test_deletes_existing_files(self, tmp_path):
        """Removes existing files."""
        f = tmp_path / "a.txt"
        f.write_text("data")
        cleanup_paths([str(f)])
        assert not f.exists()

    def test_ignores_missing_files(self, tmp_path):
        """Does not raise on missing files."""
        cleanup_paths([str(tmp_path / "nonexistent.txt")])

    def test_handles_oserror(self, tmp_path):
        """Silently ignores OSError during removal."""
        f = tmp_path / "b.txt"
        f.write_text("data")
        with patch("plex_organizer.ffmpeg_utils.remove", side_effect=OSError):
            cleanup_paths([str(f)])


class TestProbeVideoQuality:
    """Tests for probe_video_quality."""

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_2160p_for_4k(self, mock_streams):
        """Returns 2160p for UHD resolution."""
        mock_streams.return_value = [{"height": 2160}]
        assert probe_video_quality("/v.mkv") == "2160p"

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_1080p(self, mock_streams):
        """Returns 1080p for Full HD resolution."""
        mock_streams.return_value = [{"height": 1080}]
        assert probe_video_quality("/v.mkv") == "1080p"

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_720p(self, mock_streams):
        """Returns 720p for HD resolution."""
        mock_streams.return_value = [{"height": 720}]
        assert probe_video_quality("/v.mkv") == "720p"

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_480p(self, mock_streams):
        """Returns 480p for SD resolution."""
        mock_streams.return_value = [{"height": 480}]
        assert probe_video_quality("/v.mkv") == "480p"

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_1440p(self, mock_streams):
        """Returns 1440p for QHD resolution."""
        mock_streams.return_value = [{"height": 1440}]
        assert probe_video_quality("/v.mkv") == "1440p"

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_raw_height_for_low_res(self, mock_streams):
        """Returns raw height with p suffix for resolutions below 480p."""
        mock_streams.return_value = [{"height": 360}]
        assert probe_video_quality("/v.mkv") == "360p"

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_none_on_no_streams(self, mock_streams):
        """Returns None when no video streams found."""
        mock_streams.return_value = []
        assert probe_video_quality("/v.mkv") is None

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_none_when_height_missing(self, mock_streams):
        """Returns None when height key is absent."""
        mock_streams.return_value = [{"width": 1920}]
        assert probe_video_quality("/v.mkv") is None

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_none_when_height_not_int(self, mock_streams):
        """Returns None when height is not an integer."""
        mock_streams.return_value = [{"height": "1080"}]
        assert probe_video_quality("/v.mkv") is None

    @patch("plex_organizer.ffmpeg_utils.probe_streams_json")
    def test_returns_none_when_height_zero(self, mock_streams):
        """Returns None when height is zero."""
        mock_streams.return_value = [{"height": 0}]
        assert probe_video_quality("/v.mkv") is None


class TestReplaceAndRestoreTimestamps:  # pylint: disable=too-few-public-methods
    """Tests for replace_and_restore_timestamps."""

    def test_replaces_file_and_restores_mtime(self, tmp_path):
        """Replaces file content and restores original timestamps."""
        orig = tmp_path / "video.mkv"
        orig.write_text("original")
        utime(str(orig), (1000000, 2000000))

        tmp_file = tmp_path / "tmp.mkv"
        tmp_file.write_text("replaced")

        replace_and_restore_timestamps(str(tmp_file), str(orig))

        assert orig.read_text() == "replaced"
        assert not tmp_file.exists()
        assert orig.stat().st_mtime == 2000000
