"""Tests for plex_organizer.subs.embedding – utility / helper tests."""

from unittest.mock import MagicMock, patch
from pytest import mark

from plex_organizer.subs.embedding import (
    _ass_dialogue_to_payload,
    _clean_subtitle_text_for_langdetect,
    _dedupe_subtitle_inputs,
    _detect_subtitle_language_and_sdh,
    _extract_embedded_subtitle_to_srt,
    _filename_suggests_sdh,
    _gather_subtitle_files_under,
    _get_overrides,
    _handle_existing_language_tag,
    _handle_title_lang2,
    _handle_tmp_srt,
    _index_subtitles_by_stem,
    _is_subtitle,
    _is_subtitles_dir_name,
    _is_video,
    _iso639_1_to_2,
    _lang2_from_title,
    _list_immediate_subtitle_dirs,
    _match_same_folder_subtitles,
    _mp4_compatible_subtitle_paths,
    _normalize_language_tag_to_iso639_2,
    _normalized_subtitle_bytes_for_hash,
    _read_text_best_effort,
    _scan_subtitle_dir,
    _stem_lower,
    _subtitle_language_needs_tag,
    _subtitle_matches_video,
    _text_suggests_sdh,
    _video_folder_name_matches,
)


class TestIso6391To2:
    """Tests for _iso639_1_to_2."""

    def test_valid_2letter(self):
        """Two-letter code is converted to three-letter code."""
        assert _iso639_1_to_2("en") == "eng"

    def test_valid_3letter_passthrough(self):
        """Three-letter code is returned unchanged."""
        assert _iso639_1_to_2("ger") == "ger"

    def test_none(self):
        """None input returns None."""
        assert _iso639_1_to_2(None) is None

    def test_empty(self):
        """Empty string returns None."""
        assert _iso639_1_to_2("") is None

    def test_single_char(self):
        """Single character returns None."""
        assert _iso639_1_to_2("e") is None

    def test_four_chars(self):
        """Four-character code returns None."""
        assert _iso639_1_to_2("abcd") is None

    def test_with_region(self):
        """Hyphenated region suffix is stripped before lookup."""
        assert _iso639_1_to_2("en-US") == "eng"

    def test_underscore_region(self):
        """Underscore region suffix is stripped before lookup."""
        assert _iso639_1_to_2("en_GB") == "eng"


class TestReadTextBestEffort:
    """Tests for _read_text_best_effort."""

    def test_reads_utf8(self, tmp_path):
        """Reads UTF-8 file content."""
        f = tmp_path / "sub.srt"
        f.write_text("hello", encoding="utf-8")
        assert _read_text_best_effort(str(f)) == "hello"

    def test_reads_bom(self, tmp_path):
        """UTF-8 BOM is stripped."""
        f = tmp_path / "sub.srt"
        f.write_bytes(b"\xef\xbb\xbfhello")
        assert _read_text_best_effort(str(f)) == "hello"

    def test_missing_file(self):
        """Missing file returns empty string."""
        assert _read_text_best_effort("/nonexistent.srt") == ""


class TestFilenameSuggestsSDH:
    """Tests for _filename_suggests_sdh."""

    def test_sdh_in_name(self):
        """Filename containing 'sdh' is detected."""
        assert _filename_suggests_sdh("Movie.sdh.srt")

    def test_hearing_impaired(self):
        """Filename containing 'hearing_impaired' is detected."""
        assert _filename_suggests_sdh("Movie.hearing_impaired.srt")

    def test_normal(self):
        """Normal filename is not flagged as SDH."""
        assert not _filename_suggests_sdh("Movie.en.srt")


class TestTextSuggestsSDH:
    """Tests for _text_suggests_sdh."""

    def test_empty(self):
        """Empty text is not SDH."""
        assert not _text_suggests_sdh("")

    def test_bracket_cues(self):
        """Bracket cues indicate SDH."""
        assert _text_suggests_sdh("[music] [laughing] [door closes]")

    def test_speaker_labels(self):
        """Speaker labels indicate SDH."""
        assert _text_suggests_sdh("JOHN: Hello\nJANE: Hi there\n")

    def test_plain_dialogue(self):
        """Plain dialogue is not SDH."""
        assert not _text_suggests_sdh("Hello there, how are you?")


class TestCleanSubtitleText:
    """Tests for _clean_subtitle_text_for_langdetect."""

    def test_empty(self):
        """Empty input returns empty string."""
        assert _clean_subtitle_text_for_langdetect("") == ""

    def test_strips_timestamps(self):
        """Timestamp lines are removed."""
        text = "00:01:02,000 --> 00:01:05,000\nHello world"
        result = _clean_subtitle_text_for_langdetect(text)
        assert "Hello" in result
        assert "-->" not in result

    def test_strips_webvtt_header(self):
        """WEBVTT header is removed."""
        text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi"
        result = _clean_subtitle_text_for_langdetect(text)
        assert "WEBVTT" not in result


class TestAssDialogueToPayload:
    """Tests for _ass_dialogue_to_payload."""

    def test_non_dialogue(self):
        """Non-dialogue lines pass through unchanged."""
        assert _ass_dialogue_to_payload("some line") == "some line"

    def test_dialogue(self):
        """Dialogue payload is extracted from the 10th comma-separated field."""
        line = "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello world"
        assert _ass_dialogue_to_payload(line) == "Hello world"

    def test_too_few_parts(self):
        """Lines with too few fields are returned unchanged."""
        line = "Dialogue: a,b,c"
        assert _ass_dialogue_to_payload(line) == line


class TestSubtitleLanguageNeedsTag:
    """Tests for _subtitle_language_needs_tag."""

    def test_none(self):
        """None needs a tag."""
        assert _subtitle_language_needs_tag(None)

    def test_und(self):
        """'und' needs a tag."""
        assert _subtitle_language_needs_tag("und")

    def test_unknown(self):
        """'unknown' needs a tag."""
        assert _subtitle_language_needs_tag("unknown")

    def test_valid(self):
        """Valid language code does not need a tag."""
        assert not _subtitle_language_needs_tag("eng")


class TestNormalizeLanguageTag:
    """Tests for _normalize_language_tag_to_iso639_2."""

    def test_3letter(self):
        """Three-letter code passes through."""
        assert _normalize_language_tag_to_iso639_2("eng") == "eng"

    def test_2letter(self):
        """Two-letter code is converted."""
        assert _normalize_language_tag_to_iso639_2("en") == "eng"

    def test_none(self):
        """None returns None."""
        assert _normalize_language_tag_to_iso639_2(None) is None


class TestLang2FromTitle:
    """Tests for _lang2_from_title."""

    def test_valid(self):
        """Valid ISO 639-2 first token is returned."""
        assert _lang2_from_title("eng subtitle") == "eng"

    def test_none(self):
        """None input returns None."""
        assert _lang2_from_title(None) is None

    def test_not_iso(self):
        """Non-ISO token returns None."""
        assert _lang2_from_title("foo subtitle") is None

    def test_two_letter(self):
        """Two-letter token is not accepted."""
        assert _lang2_from_title("en subtitle") is None


class TestSimpleHelpers:
    """Tests for _stem_lower, _is_video, _is_subtitle, _is_subtitles_dir_name."""

    def test_stem_lower(self):
        """Returns lowercase stem without extension."""
        assert _stem_lower("Movie.mkv") == "movie"

    def test_is_video_true(self):
        """Video extension is recognized."""
        assert _is_video("file.mkv")

    def test_is_video_false(self):
        """Non-video extension is rejected."""
        assert not _is_video("file.txt")

    def test_is_subtitle_true(self):
        """Subtitle extension is recognized."""
        assert _is_subtitle("file.srt")

    def test_is_subtitle_false(self):
        """Non-subtitle extension is rejected."""
        assert not _is_subtitle("file.mkv")

    def test_is_subtitles_dir_true(self):
        """Known subtitle directory names are recognized."""
        assert _is_subtitles_dir_name("Subs")
        assert _is_subtitles_dir_name("Subtitles")

    def test_is_subtitles_dir_false(self):
        """Non-subtitle directory names are rejected."""
        assert not _is_subtitles_dir_name("Media")


class TestListImmediateSubtitleDirs:
    """Tests for _list_immediate_subtitle_dirs."""

    def test_finds_subs(self, tmp_path):
        """Finds Subs directory but not unrelated directories."""
        (tmp_path / "Subs").mkdir()
        (tmp_path / "Other").mkdir()
        result = _list_immediate_subtitle_dirs(str(tmp_path))
        assert len(result) == 1
        assert "Subs" in result[0]

    def test_nonexistent(self):
        """Non-existent path returns empty list."""
        assert not _list_immediate_subtitle_dirs("/nonexistent")


class TestDedupeOSError:  # pylint: disable=too-few-public-methods
    """Tests for _dedupe_subtitle_inputs OSError branch."""

    def test_skips_unreadable_file(self, tmp_path):
        """Unreadable file is silently skipped during dedup."""
        f = tmp_path / "a.srt"
        f.write_text("x")
        with patch(
            "plex_organizer.subs.embedding._normalized_subtitle_bytes_for_hash",
            side_effect=OSError("nope"),
        ):
            result = _dedupe_subtitle_inputs([str(f)])
        assert not result


class TestMatching:
    """Tests for _subtitle_matches_video and _video_folder_name_matches."""

    def test_exact_match(self):
        """Exact stem match returns True."""
        assert _subtitle_matches_video("movie", "movie")

    def test_prefix_match(self):
        """Subtitle stem starting with video stem matches."""
        assert _subtitle_matches_video("movie", "movie.en")

    def test_no_match(self):
        """Unrelated stems do not match."""
        assert not _subtitle_matches_video("movie", "other")

    def test_folder_matches_stem(self):
        """Folder name matching video stem is accepted."""
        assert _video_folder_name_matches("movie.mkv", "movie", "Movie")

    def test_folder_matches_filename(self):
        """Folder name matching full video filename is accepted."""
        assert _video_folder_name_matches("movie.mkv", "movie", "movie.mkv")

    def test_folder_matches_prefix_separator(self):
        """Folder name matching via subtitle-matches prefix."""
        assert _video_folder_name_matches("movie.mkv", "movie", "movie.en")


class TestNormalizedSubtitleBytesForHash:
    """Tests for _normalized_subtitle_bytes_for_hash."""

    def test_text_normalizes_crlf(self, tmp_path):
        """CRLF line endings are normalized to LF."""
        f = tmp_path / "sub.srt"
        f.write_bytes(b"\r\nhello\r\n")
        result = _normalized_subtitle_bytes_for_hash(str(f))
        assert b"\r" not in result

    def test_text_strips_bom(self, tmp_path):
        """UTF-8 BOM is stripped from text subtitles."""
        f = tmp_path / "sub.srt"
        f.write_bytes(b"\xef\xbb\xbfhello")
        result = _normalized_subtitle_bytes_for_hash(str(f))
        assert not result.startswith(b"\xef\xbb\xbf")

    def test_binary_unchanged(self, tmp_path):
        """Binary subtitle bytes are returned unchanged."""
        f = tmp_path / "sub.sup"
        f.write_bytes(b"\x00\x01\x02")
        assert _normalized_subtitle_bytes_for_hash(str(f)) == b"\x00\x01\x02"


class TestDedupeSubtitleInputs:
    """Tests for _dedupe_subtitle_inputs."""

    def test_removes_duplicates(self, tmp_path):
        """Files with identical content are deduplicated."""
        f1 = tmp_path / "a.srt"
        f2 = tmp_path / "b.srt"
        f1.write_text("same content")
        f2.write_text("same content")
        result = _dedupe_subtitle_inputs([str(f1), str(f2)])
        assert len(result) == 1

    def test_keeps_different(self, tmp_path):
        """Files with different content are kept."""
        f1 = tmp_path / "a.srt"
        f2 = tmp_path / "b.srt"
        f1.write_text("content a")
        f2.write_text("content b")
        result = _dedupe_subtitle_inputs([str(f1), str(f2)])
        assert len(result) == 2

    def test_skips_sub_with_idx(self, tmp_path):
        """.sub file is skipped when matching .idx exists."""
        idx = tmp_path / "movie.idx"
        sub = tmp_path / "movie.sub"
        idx.write_text("index")
        sub.write_text("subtitle")
        result = _dedupe_subtitle_inputs([str(idx), str(sub)])
        assert len(result) == 1
        assert result[0].endswith(".idx")


@mark.usefixtures("default_config")
class TestMp4Compatible:
    """Tests for _mp4_compatible_subtitle_paths."""

    def test_srt_allowed(self):
        """SRT files are MP4-compatible."""
        assert _mp4_compatible_subtitle_paths(["/a.srt"]) == ["/a.srt"]

    def test_ass_rejected(self):
        """ASS files are not MP4-compatible."""
        assert not _mp4_compatible_subtitle_paths(["/a.ass"])


class TestIndexSubtitlesByStem:  # pylint: disable=too-few-public-methods
    """Tests for _index_subtitles_by_stem."""

    def test_groups_by_stem(self):
        """Subtitle files are grouped by lowercase stem."""
        result = _index_subtitles_by_stem("/root", ["Movie.srt", "Movie.eng.srt"])
        assert "movie" in result
        assert "movie.eng" in result


class TestMatchSameFolderSubtitles:
    """Tests for _match_same_folder_subtitles."""

    def test_matches(self, tmp_path):
        """Subtitle with matching stem is matched to video."""
        result = _match_same_folder_subtitles(
            str(tmp_path), ["video.mkv"], ["video.srt"]
        )
        assert len(result) == 1

    def test_no_match(self, tmp_path):
        """Subtitle with non-matching stem is not matched."""
        result = _match_same_folder_subtitles(
            str(tmp_path), ["video.mkv"], ["other.srt"]
        )
        assert len(result) == 0


class TestDetectSubtitleLanguageAndSdh:
    """Tests for _detect_subtitle_language_and_sdh."""

    def test_non_text_subtitle(self, tmp_path):
        """Non-text subtitle returns (None, False)."""
        f = tmp_path / "sub.sup"
        f.write_bytes(b"\x00")
        lang, sdh = _detect_subtitle_language_and_sdh(str(f))
        assert lang is None
        assert sdh is False

    @patch("plex_organizer.subs.embedding.detect_langs")
    def test_detects_language(self, mock_detect, tmp_path):
        """Detects language from subtitle text."""
        f = tmp_path / "sub.srt"
        f.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\n"
            + "Hello world this is a test sentence for language detection. " * 5
        )
        mock_result = MagicMock()
        mock_result.lang = "en"
        mock_detect.return_value = [mock_result]
        lang, sdh = _detect_subtitle_language_and_sdh(str(f))
        assert lang == "eng"
        assert sdh is False

    def test_too_short(self, tmp_path):
        """Too-short text returns None language."""
        f = tmp_path / "sub.srt"
        f.write_text("Hi")
        lang, _sdh = _detect_subtitle_language_and_sdh(str(f))
        assert lang is None

    @patch(
        "plex_organizer.subs.embedding.detect_langs",
        side_effect=__import__("langdetect").lang_detect_exception.LangDetectException(
            0, ""
        ),
    )
    def test_langdetect_exception(self, _detect, tmp_path):
        """LangDetectException returns (None, sdh)."""
        f = tmp_path / "sub.srt"
        f.write_text(
            "Hello world this is a sentence with plenty of text for detection. " * 5
        )
        lang, _sdh = _detect_subtitle_language_and_sdh(str(f))
        assert lang is None

    @patch("plex_organizer.subs.embedding.detect_langs", return_value=[])
    def test_empty_candidates(self, _detect, tmp_path):
        """Empty detect_langs candidates returns (None, sdh)."""
        f = tmp_path / "sub.srt"
        f.write_text(
            "Hello world this is a sentence with plenty of text for detection. " * 5
        )
        lang, _sdh = _detect_subtitle_language_and_sdh(str(f))
        assert lang is None

    def test_cleaned_empty_returns_none(self, tmp_path):
        """Cleaned text with no alpha chars returns None."""
        f = tmp_path / "sub.srt"
        f.write_text("123 456 789 000 111 222 333 444 555 666 777 888 999")
        lang, _sdh = _detect_subtitle_language_and_sdh(str(f))
        assert lang is None


class TestExtractEmbeddedSubtitleToSrt:
    """Tests for _extract_embedded_subtitle_to_srt."""

    @patch("plex_organizer.subs.embedding.run_cmd")
    @patch(
        "plex_organizer.subs.embedding.ffmpeg_input_cmd",
        return_value=["ffmpeg", "-i", "v.mkv"],
    )
    def test_success(self, _input_cmd, mock_run):
        """Returns temp path on success."""
        mock_run.return_value = MagicMock(returncode=0)
        result = _extract_embedded_subtitle_to_srt("/ff", "/v.mkv", 0)
        assert result is not None
        assert result.endswith(".srt")

    @patch("plex_organizer.subs.embedding.remove")
    @patch("plex_organizer.subs.embedding.run_cmd")
    @patch(
        "plex_organizer.subs.embedding.ffmpeg_input_cmd",
        return_value=["ffmpeg", "-i", "v.mkv"],
    )
    def test_failure_returns_none(self, _input_cmd, mock_run, mock_rm):
        """Returns None and cleans up on failure."""
        mock_run.return_value = MagicMock(returncode=1)
        result = _extract_embedded_subtitle_to_srt("/ff", "/v.mkv", 0)
        assert result is None
        mock_rm.assert_called_once()

    @patch("plex_organizer.subs.embedding.remove", side_effect=OSError("nope"))
    @patch("plex_organizer.subs.embedding.run_cmd")
    @patch(
        "plex_organizer.subs.embedding.ffmpeg_input_cmd",
        return_value=["ffmpeg", "-i", "v.mkv"],
    )
    def test_failure_cleanup_oserror(self, _input_cmd, mock_run, _rm):
        """OSError during cleanup is silently handled."""
        mock_run.return_value = MagicMock(returncode=1)
        result = _extract_embedded_subtitle_to_srt("/ff", "/v.mkv", 0)
        assert result is None


class TestGetOverrides:
    """Tests for _get_overrides."""

    @patch("plex_organizer.subs.embedding._handle_tmp_srt")
    def test_valid_language_no_title(self, _tmp_srt):
        """Stream with valid language and empty title gets title override."""
        streams = [{"tags": {"language": "eng", "title": ""}}]
        _lang_o, title_o = _get_overrides(streams, "/v.mkv", "/ff")
        assert 0 in title_o
        assert title_o[0] == "eng"

    @patch("plex_organizer.subs.embedding._handle_tmp_srt")
    def test_title_with_lang_code(self, _tmp_srt):
        """Stream with title containing lang code is resolved via title."""
        streams = [{"tags": {"language": "und", "title": "spa subtitle"}}]
        lang_o, _title_o = _get_overrides(streams, "/v.mkv", "/ff")
        assert lang_o.get(0) == "spa"

    @patch("plex_organizer.subs.embedding._handle_tmp_srt")
    def test_falls_through_to_tmp_srt(self, mock_tmp):
        """Stream with und language and no useful title falls through to tmp srt."""
        streams = [{"tags": {"language": "und", "title": ""}}]
        _get_overrides(streams, "/v.mkv", "/ff")
        mock_tmp.assert_called_once()

    def test_tags_none(self):
        """Stream with no tags at all is handled without error."""
        streams = [{"tags": None}]
        with patch("plex_organizer.subs.embedding._handle_tmp_srt"):
            lang_o, title_o = _get_overrides(streams, "/v.mkv", "/ff")
        assert isinstance(lang_o, dict)
        assert isinstance(title_o, dict)


class TestGatherSubtitleFilesUnder:
    """Tests for _gather_subtitle_files_under."""

    def test_finds_subs(self, tmp_path):
        """Subtitle files are collected recursively."""
        (tmp_path / "sub.srt").write_text("x")
        (tmp_path / "nested").mkdir()
        (tmp_path / "nested" / "sub2.ass").write_text("x")
        result = _gather_subtitle_files_under(str(tmp_path))
        assert len(result) == 2

    def test_skips_plex_folder(self, tmp_path):
        """Plex Versions subdirectory is skipped."""
        plex = tmp_path / "Plex Versions"
        plex.mkdir()
        (plex / "sub.srt").write_text("x")
        result = _gather_subtitle_files_under(str(tmp_path))
        assert len(result) == 0


class TestScanSubtitleDir:
    """Tests for _scan_subtitle_dir."""

    def test_basic(self, tmp_path):
        """Finds dirs and subtitle files."""
        (tmp_path / "video").mkdir()
        (tmp_path / "sub.srt").write_text("x")
        dirs, by_stem = _scan_subtitle_dir(str(tmp_path))
        assert "video" in dirs
        assert "sub" in by_stem

    def test_oserror_on_dirs(self):
        """OSError on listdir returns empty dirs."""
        dirs, by_stem = _scan_subtitle_dir("/nonexistent")
        assert not dirs
        assert not by_stem


class TestOverrideHelpers:
    """Tests for _handle_existing_language_tag, _handle_title_lang2, _handle_tmp_srt."""

    def test_handle_existing_language_tag(self):
        """Existing language tag populates title overrides."""
        overrides = {}
        _handle_existing_language_tag(0, "eng", overrides)
        assert overrides[0] == "eng"

    def test_handle_title_lang2_found(self):
        """Title containing an ISO language code populates overrides."""
        overrides = {}
        assert _handle_title_lang2(0, "eng subtitle", overrides)
        assert overrides[0] == "eng"

    def test_handle_title_lang2_none(self):
        """None title yields no overrides."""
        overrides = {}
        assert not _handle_title_lang2(0, None, overrides)

    @patch(
        "plex_organizer.subs.embedding._extract_embedded_subtitle_to_srt",
        return_value=None,
    )
    def test_handle_tmp_srt_no_extraction(self, _extract):
        """No overrides when extraction returns None."""
        lang_o = {}
        title_o = {}
        _handle_tmp_srt(0, "/ff", "/v.mkv", lang_o, title_o)
        assert len(lang_o) == 0

    @patch("plex_organizer.subs.embedding.remove", side_effect=OSError("locked"))
    @patch(
        "plex_organizer.subs.embedding._detect_subtitle_language_and_sdh",
        return_value=("eng", True),
    )
    @patch(
        "plex_organizer.subs.embedding._extract_embedded_subtitle_to_srt",
        return_value="/tmp/tmp.srt",
    )
    def test_handle_tmp_srt_detected(self, _extract, _detect, _rm):
        """Detected language and SDH populate both override dicts."""
        lang_o = {}
        title_o = {}
        _handle_tmp_srt(0, "/ff", "/v.mkv", lang_o, title_o)
        assert lang_o[0] == "eng"
        assert title_o[0] == "eng SDH"
