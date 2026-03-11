"""Tests for plex_organizer.subs.embedding – operational / integration tests."""

from unittest.mock import MagicMock, patch
from pytest import mark

from plex_organizer.dataclass import SubtitleMergePlan
from plex_organizer.subs.embedding import (
    _build_subtitle_embed_cmd,
    _delete_paths_best_effort,
    _discover_plans,
    _embed_subtitles,
    _embeddable_subtitles_for_video,
    _tag_embedded_subtitle_languages,
    _tag_embedded_subtitle_languages_for_videos,
    merge_subtitles_in_directory,
)


@mark.usefixtures("default_config")
class TestTagEmbeddedSubtitleLanguages:
    """Tests for _tag_embedded_subtitle_languages."""

    def test_missing_file(self):
        """Returns early for non-existent file."""
        _tag_embedded_subtitle_languages("/nonexistent.mkv")

    @patch("plex_organizer.subs.embedding.probe_streams_json", return_value=[])
    @patch("plex_organizer.subs.embedding.get_ffmpeg", return_value="/ff")
    def test_no_streams(self, _ff, _probe, tmp_path):
        """Returns early when no subtitle streams found."""
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _tag_embedded_subtitle_languages(str(vid))

    @patch("plex_organizer.subs.embedding.remove")
    @patch("plex_organizer.subs.embedding.exists", return_value=False)
    @patch("plex_organizer.subs.embedding.replace_and_restore_timestamps")
    @patch("plex_organizer.subs.embedding.run_cmd")
    @patch(
        "plex_organizer.subs.embedding.build_ffmpeg_base_cmd", return_value=["ffmpeg"]
    )
    @patch(
        "plex_organizer.subs.embedding.create_temp_output", return_value="/tmp/o.mkv"
    )
    @patch(
        "plex_organizer.subs.embedding._get_overrides",
        return_value=(
            {0: "eng"},
            {0: "eng"},
        ),
    )
    @patch(
        "plex_organizer.subs.embedding.probe_streams_json",
        return_value=[{"tags": {"language": "und"}}],
    )
    @patch("plex_organizer.subs.embedding.get_ffmpeg", return_value="/ff")
    def test_applies_overrides(
        self,
        _ff,
        _probe,
        _overrides,
        _tmp,
        _build,
        mock_run,
        _rep,
        _exists,
        _rm,
        tmp_path,
    ):
        """Overrides are applied and file is replaced."""
        mock_run.return_value = MagicMock(returncode=0)
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _tag_embedded_subtitle_languages(str(vid))
        _rep.assert_called_once()

    @patch("plex_organizer.subs.embedding.remove")
    @patch("plex_organizer.subs.embedding.exists", return_value=False)
    @patch("plex_organizer.subs.embedding.log_error")
    @patch("plex_organizer.subs.embedding.run_cmd")
    @patch(
        "plex_organizer.subs.embedding.build_ffmpeg_base_cmd", return_value=["ffmpeg"]
    )
    @patch(
        "plex_organizer.subs.embedding.create_temp_output", return_value="/tmp/o.mkv"
    )
    @patch(
        "plex_organizer.subs.embedding._get_overrides",
        return_value=(
            {0: "eng"},
            {0: "eng"},
        ),
    )
    @patch(
        "plex_organizer.subs.embedding.probe_streams_json",
        return_value=[{"tags": {"language": "und"}}],
    )
    @patch("plex_organizer.subs.embedding.get_ffmpeg", return_value="/ff")
    def test_ffmpeg_failure_logged(
        self,
        _ff,
        _probe,
        _overrides,
        _tmp,
        _build,
        mock_run,
        mock_log,
        _exists,
        _rm,
        tmp_path,
    ):
        """ffmpeg failure during tagging logs error."""
        mock_run.return_value = MagicMock(returncode=1, stderr="tagging failed")
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _tag_embedded_subtitle_languages(str(vid))
        mock_log.assert_called()

    @patch("plex_organizer.subs.embedding.remove", side_effect=OSError("busy"))
    @patch("plex_organizer.subs.embedding.exists", return_value=True)
    @patch("plex_organizer.subs.embedding.replace_and_restore_timestamps")
    @patch("plex_organizer.subs.embedding.run_cmd")
    @patch(
        "plex_organizer.subs.embedding.build_ffmpeg_base_cmd", return_value=["ffmpeg"]
    )
    @patch(
        "plex_organizer.subs.embedding.create_temp_output", return_value="/tmp/o.mkv"
    )
    @patch(
        "plex_organizer.subs.embedding._get_overrides",
        return_value=(
            {0: "eng"},
            {0: "eng"},
        ),
    )
    @patch(
        "plex_organizer.subs.embedding.probe_streams_json",
        return_value=[{"tags": {"language": "und"}}],
    )
    @patch("plex_organizer.subs.embedding.get_ffmpeg", return_value="/ff")
    def test_finally_cleanup_oserror(
        self,
        _ff,
        _probe,
        _overrides,
        _tmp,
        _build,
        mock_run,
        _rep,
        _exists,
        _rm,
        tmp_path,
    ):
        """OSError in finally cleanup block is silently handled."""
        mock_run.return_value = MagicMock(returncode=0)
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _tag_embedded_subtitle_languages(str(vid))

    @patch(
        "plex_organizer.subs.embedding._get_overrides",
        return_value=({}, {}),
    )
    @patch(
        "plex_organizer.subs.embedding.probe_streams_json",
        return_value=[{"tags": {"language": "eng"}}],
    )
    @patch("plex_organizer.subs.embedding.get_ffmpeg", return_value="/ff")
    def test_no_overrides_skips(
        self,
        _ff,
        _probe,
        _overrides,
        tmp_path,
    ):
        """No overrides means no remux."""
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        _tag_embedded_subtitle_languages(str(vid))


class TestEmbeddableSubtitlesForVideo:
    """Tests for _embeddable_subtitles_for_video."""

    def test_no_existing_files(self, tmp_path):
        """Returns empty list when no subtitle files exist."""
        is_mp4, subs = _embeddable_subtitles_for_video(
            str(tmp_path / "v.mkv"), ["/nonexistent.srt"]
        )
        assert not subs
        assert not is_mp4

    def test_mp4_filters_incompatible(self, tmp_path):
        """Incompatible subtitle formats are filtered for MP4."""
        sub = tmp_path / "sub.ass"
        sub.write_text("x")
        is_mp4, subs = _embeddable_subtitles_for_video(
            str(tmp_path / "v.mp4"), [str(sub)]
        )
        assert is_mp4 is True
        assert not subs

    def test_mkv_returns_existing(self, tmp_path):
        """MKV returns all existing subtitle files."""
        sub = tmp_path / "sub.srt"
        sub.write_text("x")
        is_mp4, subs = _embeddable_subtitles_for_video(
            str(tmp_path / "v.mkv"), [str(sub)]
        )
        assert is_mp4 is False
        assert len(subs) == 1

    def test_mp4_dedupes_after_filter(self, tmp_path):
        """MP4 deduplicates after filtering to compatible."""
        s1 = tmp_path / "a.srt"
        s2 = tmp_path / "b.srt"
        s1.write_text("same")
        s2.write_text("same")
        is_mp4, subs = _embeddable_subtitles_for_video(
            str(tmp_path / "v.mp4"), [str(s1), str(s2)]
        )
        assert is_mp4 is True
        assert len(subs) == 1

    @patch("plex_organizer.subs.embedding._dedupe_subtitle_inputs", return_value=[])
    def test_first_dedup_returns_empty(self, _dedup, tmp_path):
        """Returns empty when first dedup yields nothing."""
        sub = tmp_path / "sub.srt"
        sub.write_text("x")
        _is_mp4, subs = _embeddable_subtitles_for_video(
            str(tmp_path / "v.mkv"), [str(sub)]
        )
        assert not subs


@mark.usefixtures("default_config")
class TestBuildSubtitleEmbedCmd:
    """Tests for _build_subtitle_embed_cmd."""

    @patch(
        "plex_organizer.subs.embedding._detect_subtitle_language_and_sdh",
        return_value=("eng", False),
    )
    @patch("plex_organizer.subs.embedding.probe_subtitle_stream_count", return_value=0)
    def test_basic(self, _count, _detect):
        """Command includes output path and language metadata."""
        cmd = _build_subtitle_embed_cmd(
            "/ff", "/v.mkv", ["/sub.srt"], "/tmp/out.mkv", False
        )
        assert "/tmp/out.mkv" == cmd[-1]
        assert any("language=eng" in a for a in cmd)

    @patch(
        "plex_organizer.subs.embedding._detect_subtitle_language_and_sdh",
        return_value=("eng", True),
    )
    @patch("plex_organizer.subs.embedding.probe_subtitle_stream_count", return_value=0)
    def test_sdh_title(self, _count, _detect):
        """SDH subtitle gets 'eng SDH' title."""
        cmd = _build_subtitle_embed_cmd(
            "/ff", "/v.mkv", ["/sub.srt"], "/tmp/out.mkv", False
        )
        assert any("title=eng SDH" in a for a in cmd)

    @patch(
        "plex_organizer.subs.embedding._detect_subtitle_language_and_sdh",
        return_value=("eng", False),
    )
    @patch("plex_organizer.subs.embedding.probe_subtitle_stream_count", return_value=0)
    def test_mp4_mov_text(self, _count, _detect):
        """MP4 output uses mov_text codec."""
        cmd = _build_subtitle_embed_cmd(
            "/ff", "/v.mp4", ["/sub.srt"], "/tmp/out.mp4", True
        )
        assert "mov_text" in cmd

    @patch(
        "plex_organizer.subs.embedding._detect_subtitle_language_and_sdh",
        return_value=(None, False),
    )
    @patch("plex_organizer.subs.embedding.probe_subtitle_stream_count", return_value=0)
    def test_skips_no_lang(self, _count, _detect):
        """Subtitle with undetected language gets no metadata."""
        cmd = _build_subtitle_embed_cmd(
            "/ff", "/v.mkv", ["/sub.srt"], "/tmp/out.mkv", False
        )
        assert not any("language=" in a for a in cmd)


@mark.usefixtures("default_config")
class TestDeletePathsBestEffort:
    """Tests for _delete_paths_best_effort."""

    def test_deletes(self, tmp_path):
        """Existing file is deleted."""
        f = tmp_path / "f.txt"
        f.write_text("x")
        _delete_paths_best_effort([str(f)])
        assert not f.exists()

    @patch("plex_organizer.subs.embedding.log_error")
    def test_logs_oserror(self, mock_log):
        """OSError during deletion is logged."""
        _delete_paths_best_effort(["/nonexistent_file_xyz"])
        mock_log.assert_called_once()


@mark.usefixtures("default_config")
class TestEmbedSubtitles:
    """Tests for _embed_subtitles."""

    def test_plex_folder_skipped(self):
        """Plex-managed folders are skipped."""
        plan = SubtitleMergePlan(
            video_path="/Plex Versions/v.mkv", subtitle_paths=("/sub.srt",)
        )
        _embed_subtitles(plan)

    @patch("plex_organizer.subs.embedding.log_error")
    def test_missing_video(self, mock_log):
        """Missing video logs error."""
        plan = SubtitleMergePlan(
            video_path="/nonexistent.mkv", subtitle_paths=("/sub.srt",)
        )
        _embed_subtitles(plan)
        mock_log.assert_called_once()

    @patch("plex_organizer.subs.embedding.remove")
    @patch("plex_organizer.subs.embedding.exists", return_value=False)
    @patch("plex_organizer.subs.embedding._delete_paths_best_effort")
    @patch("plex_organizer.subs.embedding.replace_and_restore_timestamps")
    @patch("plex_organizer.subs.embedding.run_cmd")
    @patch(
        "plex_organizer.subs.embedding._build_subtitle_embed_cmd",
        return_value=["ffmpeg"],
    )
    @patch(
        "plex_organizer.subs.embedding.create_temp_output", return_value="/tmp/o.mkv"
    )
    @patch("plex_organizer.subs.embedding.get_ffmpeg", return_value="/ff")
    @patch(
        "plex_organizer.subs.embedding._embeddable_subtitles_for_video",
        return_value=(False, ["/sub.srt"]),
    )
    def test_success(
        self, _emb, _ff, _tmp, _build, mock_run, _rep, _del, _exists, _rm, tmp_path
    ):
        """Successful embed replaces file and deletes subtitle sources."""
        mock_run.return_value = MagicMock(returncode=0)
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        plan = SubtitleMergePlan(video_path=str(vid), subtitle_paths=("/sub.srt",))
        _embed_subtitles(plan)
        _rep.assert_called_once()
        _del.assert_called_once()

    @patch("plex_organizer.subs.embedding.remove")
    @patch("plex_organizer.subs.embedding.exists", return_value=False)
    @patch("plex_organizer.subs.embedding.log_error")
    @patch("plex_organizer.subs.embedding.run_cmd")
    @patch(
        "plex_organizer.subs.embedding._build_subtitle_embed_cmd",
        return_value=["ffmpeg"],
    )
    @patch(
        "plex_organizer.subs.embedding.create_temp_output", return_value="/tmp/o.mkv"
    )
    @patch("plex_organizer.subs.embedding.get_ffmpeg", return_value="/ff")
    @patch(
        "plex_organizer.subs.embedding._embeddable_subtitles_for_video",
        return_value=(False, ["/sub.srt"]),
    )
    def test_ffmpeg_failure(
        self, _emb, _ff, _tmp, _build, mock_run, mock_log, _exists, _rm, tmp_path
    ):
        """Failed ffmpeg logs error."""
        mock_run.return_value = MagicMock(returncode=1, stderr="fail")
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        plan = SubtitleMergePlan(video_path=str(vid), subtitle_paths=("/sub.srt",))
        _embed_subtitles(plan)
        mock_log.assert_called()

    @patch(
        "plex_organizer.subs.embedding._embeddable_subtitles_for_video",
        return_value=(False, []),
    )
    def test_no_embeddable_subs(self, _emb, tmp_path):
        """Returns early when no embeddable subs remain."""
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        plan = SubtitleMergePlan(video_path=str(vid), subtitle_paths=("/sub.srt",))
        _embed_subtitles(plan)

    @patch("plex_organizer.subs.embedding.remove")
    @patch("plex_organizer.subs.embedding.exists", return_value=True)
    @patch("plex_organizer.subs.embedding.log_error")
    @patch(
        "plex_organizer.subs.embedding._build_subtitle_embed_cmd",
        side_effect=RuntimeError("ffprobe failed"),
    )
    @patch(
        "plex_organizer.subs.embedding.create_temp_output", return_value="/tmp/o.mkv"
    )
    @patch("plex_organizer.subs.embedding.get_ffmpeg", return_value="/ff")
    @patch(
        "plex_organizer.subs.embedding._embeddable_subtitles_for_video",
        return_value=(False, ["/sub.srt"]),
    )
    def test_runtime_error_logged(
        self, _emb, _ff, _tmp, _build, mock_log, _exists, _rm, tmp_path
    ):
        """RuntimeError during embed is logged."""
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        plan = SubtitleMergePlan(video_path=str(vid), subtitle_paths=("/sub.srt",))
        _embed_subtitles(plan)
        mock_log.assert_called()

    @patch("plex_organizer.subs.embedding.remove", side_effect=OSError("locked"))
    @patch("plex_organizer.subs.embedding.exists", return_value=True)
    @patch("plex_organizer.subs.embedding.log_error")
    @patch("plex_organizer.subs.embedding.run_cmd")
    @patch(
        "plex_organizer.subs.embedding._build_subtitle_embed_cmd",
        return_value=["ffmpeg"],
    )
    @patch(
        "plex_organizer.subs.embedding.create_temp_output", return_value="/tmp/o.mkv"
    )
    @patch("plex_organizer.subs.embedding.get_ffmpeg", return_value="/ff")
    @patch(
        "plex_organizer.subs.embedding._embeddable_subtitles_for_video",
        return_value=(False, ["/sub.srt"]),
    )
    def test_tmp_cleanup_oserror(
        self, _emb, _ff, _tmp, _build, mock_run, mock_log, _exists, _rm, tmp_path
    ):
        """OSError cleaning up tmp is logged."""
        mock_run.return_value = MagicMock(returncode=1, stderr="fail")
        vid = tmp_path / "v.mkv"
        vid.write_text("x")
        plan = SubtitleMergePlan(video_path=str(vid), subtitle_paths=("/sub.srt",))
        _embed_subtitles(plan)
        assert mock_log.call_count >= 1


@mark.usefixtures("default_config")
class TestTagEmbeddedSubtitleLanguagesForVideos:
    """Tests for _tag_embedded_subtitle_languages_for_videos."""

    @patch("plex_organizer.subs.embedding._tag_embedded_subtitle_languages")
    def test_processes_non_plex(self, mock_tag):
        """Non-Plex videos are processed."""
        _tag_embedded_subtitle_languages_for_videos(["/media/v.mkv"])
        mock_tag.assert_called_once()

    @patch("plex_organizer.subs.embedding._tag_embedded_subtitle_languages")
    def test_skips_plex(self, mock_tag):
        """Plex-managed videos are skipped."""
        _tag_embedded_subtitle_languages_for_videos(["/media/Plex Versions/v.mkv"])
        mock_tag.assert_not_called()

    @patch(
        "plex_organizer.subs.embedding._tag_embedded_subtitle_languages",
        side_effect=OSError("x"),
    )
    def test_oserror_continues(self, _tag):
        """OSError is caught and processing continues."""
        _tag_embedded_subtitle_languages_for_videos(["/media/v.mkv"])


class TestDiscoverPlans:
    """Tests for _discover_plans."""

    def test_discovers_video_and_sub(self, tmp_path):
        """Video with matching subtitle produces a plan."""
        vid = tmp_path / "video.mkv"
        sub = tmp_path / "video.srt"
        vid.write_text("x")
        sub.write_text("x")
        plans = _discover_plans(str(tmp_path))
        assert len(plans) == 1
        assert plans[0].video_path.endswith("video.mkv")

    def test_empty_dir(self, tmp_path):
        """Empty directory yields no plans."""
        assert _discover_plans(str(tmp_path)) == []

    def test_skips_plex_folder(self, tmp_path):
        """Plex Versions folders are skipped."""
        plex = tmp_path / "Plex Versions"
        plex.mkdir()
        (plex / "v.mkv").write_text("x")
        (plex / "v.srt").write_text("x")
        assert _discover_plans(str(tmp_path)) == []

    def test_subs_dir(self, tmp_path):
        """Subtitles under Subs directory are discovered."""
        vid = tmp_path / "video.mkv"
        vid.write_text("x")
        subs_dir = tmp_path / "Subs"
        subs_dir.mkdir()
        (subs_dir / "video.srt").write_text("x")
        plans = _discover_plans(str(tmp_path))
        assert len(plans) == 1

    def test_subs_subdir(self, tmp_path):
        """Subtitles in video-named subdirectory of Subs are discovered."""
        vid = tmp_path / "video.mkv"
        vid.write_text("x")
        subs_dir = tmp_path / "Subs" / "video"
        subs_dir.mkdir(parents=True)
        (subs_dir / "2_English.srt").write_text("x")
        plans = _discover_plans(str(tmp_path))
        assert len(plans) == 1

    def test_single_video_remaining_in_root(self, tmp_path):
        """Single video picks up unmatched subs in same folder."""
        vid = tmp_path / "video.mkv"
        vid.write_text("x")
        (tmp_path / "other_name.srt").write_text("x")
        plans = _discover_plans(str(tmp_path))
        assert len(plans) == 1
        assert any("other_name.srt" in p for p in plans[0].subtitle_paths)

    def test_no_subs_no_plans(self, tmp_path):
        """Directory with only video and no subtitles yields no plans."""
        (tmp_path / "video.mkv").write_text("x")
        assert _discover_plans(str(tmp_path)) == []


@mark.usefixtures("default_config")
class TestMergeSubtitlesInDirectory:
    """Tests for merge_subtitles_in_directory."""

    @patch(
        "plex_organizer.subs.embedding.get_enable_subtitle_embedding",
        return_value=False,
    )
    def test_noop_when_disabled(self, _cfg):
        """No-op when subtitle embedding is disabled."""
        merge_subtitles_in_directory("/media", [])

    @patch(
        "plex_organizer.subs.embedding.get_enable_subtitle_embedding",
        return_value=True,
    )
    def test_skips_plex_folder(self, _cfg):
        """Plex-managed directories are skipped."""
        merge_subtitles_in_directory("/media/Plex Versions", [])

    @patch("plex_organizer.subs.embedding._embed_subtitles")
    @patch(
        "plex_organizer.subs.embedding._discover_plans",
        return_value=[
            SubtitleMergePlan(
                video_path="/media/v.mkv", subtitle_paths=("/media/v.srt",)
            )
        ],
    )
    @patch(
        "plex_organizer.subs.embedding.get_analyze_embedded_subtitles",
        return_value=False,
    )
    @patch("plex_organizer.subs.embedding.log_debug")
    @patch(
        "plex_organizer.subs.embedding.get_enable_subtitle_embedding",
        return_value=True,
    )
    def test_embeds_plans(self, _cfg, _log, _analyze, _plans, mock_embed):
        """Discovered plans are embedded."""
        merge_subtitles_in_directory("/media", ["/media/v.mkv"])
        mock_embed.assert_called_once()

    @patch("plex_organizer.subs.embedding._tag_embedded_subtitle_languages_for_videos")
    @patch("plex_organizer.subs.embedding._discover_plans", return_value=[])
    @patch(
        "plex_organizer.subs.embedding.get_analyze_embedded_subtitles",
        return_value=True,
    )
    @patch("plex_organizer.subs.embedding.log_debug")
    @patch(
        "plex_organizer.subs.embedding.get_enable_subtitle_embedding",
        return_value=True,
    )
    def test_analyzes_when_enabled(self, _cfg, _log, _analyze, _plans, mock_tag):
        """Embedded subtitle analysis runs when enabled."""
        merge_subtitles_in_directory("/media", ["/media/v.mkv"])
        mock_tag.assert_called_once()

    @patch("plex_organizer.subs.embedding.log_error")
    @patch(
        "plex_organizer.subs.embedding._embed_subtitles",
        side_effect=OSError("disk"),
    )
    @patch(
        "plex_organizer.subs.embedding._discover_plans",
        return_value=[
            SubtitleMergePlan(
                video_path="/media/v.mkv", subtitle_paths=("/media/v.srt",)
            )
        ],
    )
    @patch(
        "plex_organizer.subs.embedding.get_analyze_embedded_subtitles",
        return_value=False,
    )
    @patch("plex_organizer.subs.embedding.log_debug")
    @patch(
        "plex_organizer.subs.embedding.get_enable_subtitle_embedding",
        return_value=True,
    )
    def test_exception_logged(self, _cfg, _log, _analyze, _plans, _embed, mock_err):
        """Exceptions during embedding are caught and logged."""
        merge_subtitles_in_directory("/media", ["/media/v.mkv"])
        mock_err.assert_called_once()
