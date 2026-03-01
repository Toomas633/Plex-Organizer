"""Tests for plex_organizer.const."""

from plex_organizer.const import (
    ASS_CODECS,
    EXT_FILTER,
    INDEX_FILENAME,
    ISO639_1_TO_2,
    MOVIE_CORRECT_NAME_RE,
    SUBTITLE_EXTENSIONS,
    TEXT_SUB_CODECS,
    TEXT_SUBTITLE_EXTENSIONS,
    TV_CORRECT_NAME_RE,
    TV_CORRECT_SEASON_RE,
    UNWANTED_FOLDERS,
    VIDEO_EXTENSIONS,
)


class TestVideoExtensions:
    """Tests for VIDEO_EXTENSIONS constant."""

    def test_mkv_included(self):
        """Verify .mkv is a recognized video extension."""
        assert ".mkv" in VIDEO_EXTENSIONS

    def test_mp4_included(self):
        """Verify .mp4 is a recognized video extension."""
        assert ".mp4" in VIDEO_EXTENSIONS


class TestExtFilter:
    """Tests for EXT_FILTER constant."""

    def test_includes_video_extensions(self):
        """Verify all video extensions are in the filter."""
        for ext in VIDEO_EXTENSIONS:
            assert ext in EXT_FILTER

    def test_includes_qb_extension(self):
        """Verify qBittorrent in-progress extension is preserved."""
        assert ".!qB" in EXT_FILTER

    def test_includes_index_extension(self):
        """Verify organizer index extension is preserved."""
        assert ".index" in EXT_FILTER


class TestSubtitleExtensions:
    """Tests for subtitle extension constants."""

    def test_text_subtitles_are_subset(self):
        """Verify text subtitle extensions are a subset of all subtitles."""
        for ext in TEXT_SUBTITLE_EXTENSIONS:
            assert ext in SUBTITLE_EXTENSIONS

    def test_common_formats(self):
        """Verify common subtitle formats are present."""
        assert ".srt" in TEXT_SUBTITLE_EXTENSIONS
        assert ".ass" in TEXT_SUBTITLE_EXTENSIONS
        assert ".sub" in SUBTITLE_EXTENSIONS


class TestUnwantedFolders:
    """Tests for UNWANTED_FOLDERS constant."""

    def test_common_entries(self):
        """Verify well-known unwanted folder names are present."""
        assert "Subs" in UNWANTED_FOLDERS
        assert "Subtitles" in UNWANTED_FOLDERS
        assert "Extras" in UNWANTED_FOLDERS
        assert "Sample" in UNWANTED_FOLDERS
        assert "Plex Versions" in UNWANTED_FOLDERS

    def test_is_set(self):
        """Verify UNWANTED_FOLDERS is a set for O(1) lookup."""
        assert isinstance(UNWANTED_FOLDERS, set)


class TestISO639Mapping:
    """Tests for ISO 639-1 to 639-2 language code mapping."""

    def test_english(self):
        """Verify English maps to eng."""
        assert ISO639_1_TO_2["en"] == "eng"

    def test_spanish(self):
        """Verify Spanish maps to spa."""
        assert ISO639_1_TO_2["es"] == "spa"

    def test_french(self):
        """Verify French maps to fra."""
        assert ISO639_1_TO_2["fr"] == "fra"

    def test_german(self):
        """Verify German maps to deu."""
        assert ISO639_1_TO_2["de"] == "deu"


class TestMovieCorrectNameRegex:
    """Tests for MOVIE_CORRECT_NAME_RE pattern."""

    def test_matches_standard_movie(self):
        """Verify regex matches a correctly formatted movie name."""
        assert MOVIE_CORRECT_NAME_RE.match("Inception (2010).mkv")

    def test_matches_with_quality(self):
        """Verify regex matches a movie name with quality tag."""
        assert MOVIE_CORRECT_NAME_RE.match("Inception (2010) 1080p.mkv")

    def test_rejects_raw_torrent_name(self):
        """Verify regex rejects an unprocessed torrent filename."""
        assert not MOVIE_CORRECT_NAME_RE.match(
            "Inception.2010.1080p.BluRay.x264-GROUP.mkv"
        )

    def test_rejects_missing_year(self):
        """Verify regex rejects a filename without a year."""
        assert not MOVIE_CORRECT_NAME_RE.match("Inception.mkv")


class TestTVCorrectNameRegex:
    """Tests for TV_CORRECT_NAME_RE pattern."""

    def test_matches_standard_episode(self):
        """Verify regex matches a correctly formatted TV episode name."""
        m = TV_CORRECT_NAME_RE.match("Breaking Bad S01E01.mkv")
        assert m
        assert m.group(1) == "01"
        assert m.group(2) == "01"

    def test_matches_with_quality(self):
        """Verify regex matches a TV episode name with quality tag."""
        assert TV_CORRECT_NAME_RE.match("Breaking Bad S01E01 1080p.mkv")

    def test_rejects_raw_torrent_name(self):
        """Verify regex rejects an unprocessed TV torrent filename."""
        assert not TV_CORRECT_NAME_RE.match(
            "Breaking.Bad.S01E01.1080p.WEBRip.x265-RARBG.mkv"
        )


class TestTVCorrectSeasonRegex:
    """Tests for TV_CORRECT_SEASON_RE pattern."""

    def test_matches_season_folder(self):
        """Verify regex matches a correctly formatted season folder."""
        m = TV_CORRECT_SEASON_RE.match("Season 01")
        assert m
        assert m.group(1) == "01"

    def test_rejects_wrong_format(self):
        """Verify regex rejects incorrectly formatted season folders."""
        assert not TV_CORRECT_SEASON_RE.match("S01")
        assert not TV_CORRECT_SEASON_RE.match("Season1")


class TestTextSubCodecs:
    """Tests for TEXT_SUB_CODECS and ASS_CODECS constants."""

    def test_common_codecs(self):
        """Verify common text-based subtitle codecs are present."""
        assert "subrip" in TEXT_SUB_CODECS
        assert "srt" in TEXT_SUB_CODECS
        assert "ass" in TEXT_SUB_CODECS
        assert "mov_text" in TEXT_SUB_CODECS

    def test_ass_codecs(self):
        """Verify ASS/SSA codecs are present."""
        assert "ass" in ASS_CODECS
        assert "ssa" in ASS_CODECS


class TestIndexFilename:  # pylint: disable=too-few-public-methods
    """Tests for INDEX_FILENAME constant."""

    def test_value(self):
        """Verify the index filename value."""
        assert INDEX_FILENAME == ".plex_organizer.index"
