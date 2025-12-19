"""Subtitle discovery and embedding.

When enabled by config, this module discovers external subtitle files next to (or
under common `Subs/`/`Subtitles/` folders for) video files and embeds them into
the container using ffmpeg.

Plex-managed folders are always skipped.
"""

from __future__ import annotations
from json import JSONDecodeError, loads
from hashlib import sha256
from os import listdir, path as os_path, remove, replace, stat, utime, walk
from re import sub as re_sub, MULTILINE, search, findall
from shutil import which
from subprocess import CompletedProcess, run
from tempfile import NamedTemporaryFile
from typing import Tuple, Any, Dict, List, Optional, Sequence
from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException
from config import get_enable_subtitle_embedding
from const import (
    ISO639_1_TO_2,
    TEXT_SUBTITLE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    SUBTITLE_EXTENSIONS,
)
from dataclass import SubtitleMergePlan
from log import log_error
from utils import is_plex_folder

DetectorFactory.seed = 0


def _iso639_1_to_2(code: Optional[str]) -> Optional[str]:
    """Convert ISO 639-1 code (e.g. 'en') to ISO 639-2 (e.g. 'eng')."""
    if not code:
        return None
    folded = code.strip().casefold()

    for sep in ("-", "_"):
        if sep in folded:
            folded = folded.split(sep, 1)[0]
            break
    if len(folded) == 3:
        return folded
    if len(folded) != 2:
        return None
    return ISO639_1_TO_2.get(folded)


def _read_text_best_effort(sub_path: str) -> str:
    """Read a text file best-effort, handling BOMs and odd encodings."""
    try:
        with open(sub_path, "rb") as f:
            data = f.read()
    except OSError:
        return ""

    try:
        return data.decode("utf-8-sig", errors="replace")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def _filename_suggests_sdh(sub_path: str) -> bool:
    """Return True when filename suggests SDH/HI subtitles.

    Note: We intentionally do not label "cc"; user requested no CC tag.
    """
    stem = os_path.splitext(os_path.basename(sub_path))[0].casefold()
    return bool(search(r"(^|[\W_])(sdh|hearing[\W_]*impaired)([\W_]|$)", stem))


def _text_suggests_sdh(raw_text: str) -> bool:
    """Heuristic SDH detector based on common non-dialogue cues."""
    if not raw_text:
        return False

    bracket_cues = len(findall(r"\[[^\]]{1,40}\]", raw_text))
    paren_cues = len(findall(r"\([^\)]{1,40}\)", raw_text))
    speaker_labels = len(findall(r"^[A-Z][A-Z ]{2,20}:\s", raw_text, flags=MULTILINE))

    return (bracket_cues + paren_cues) >= 3 or speaker_labels >= 2


def _detect_subtitle_language_and_sdh(sub_path: str) -> tuple[Optional[str], bool]:
    """Detect (language, SDH) for a text subtitle file best-effort."""
    if os_path.splitext(sub_path)[1].lower() not in TEXT_SUBTITLE_EXTENSIONS:
        return (None, False)

    raw = _read_text_best_effort(sub_path)
    is_sdh = _filename_suggests_sdh(sub_path) or _text_suggests_sdh(raw)

    cleaned = _clean_subtitle_text_for_langdetect(raw)
    if not cleaned:
        return (None, is_sdh)

    letter_count = sum(1 for ch in cleaned if ch.isalpha())
    if letter_count < 40:
        return (None, is_sdh)

    try:
        candidates = detect_langs(cleaned[:20_000])
    except (LangDetectException, ValueError):
        return (None, is_sdh)
    if not candidates:
        return (None, is_sdh)

    best = candidates[0]
    iso639_1 = getattr(best, "lang", None)
    return (_iso639_1_to_2(iso639_1), is_sdh)


def _clean_subtitle_text_for_langdetect(text: str) -> str:
    """Strip timestamps/markup to get mostly human language tokens."""
    if not text:
        return ""

    text = re_sub(r"^WEBVTT\s*\n", "", text, flags=0)

    text = re_sub(
        r"\b\d{1,2}:\d{2}:\d{2}[\.,]\d{1,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[\.,]\d{1,3}.*$",
        " ",
        text,
        flags=MULTILINE,
    )
    text = re_sub(r"^\s*\d+\s*$", " ", text, flags=MULTILINE)

    lines = []
    for ln in text.splitlines():
        ln = _ass_dialogue_to_payload(ln)
        ln = re_sub(r"\{[^}]*\}", " ", ln)
        ln = re_sub(r"<[^>]+>", " ", ln)
        lines.append(ln)
    text = "\n".join(lines)

    text = re_sub(r"[^\w\s]+", " ", text)
    text = re_sub(r"[_\d]+", " ", text)
    text = re_sub(r"\s+", " ", text).strip()
    return text


def _ass_dialogue_to_payload(line: str) -> str:
    if not line.lstrip().lower().startswith("dialogue:"):
        return line
    parts = line.split(",", 9)
    return parts[9] if len(parts) == 10 else line


def _which_or_log(exe: str) -> str | None:
    """Resolve an executable on PATH; log an error if missing."""
    resolved = which(exe)
    if not resolved:
        log_error(
            f"Missing required tool '{exe}'. Install ffmpeg and ensure '{exe}' is on PATH."
        )
    return resolved


def _run(cmd: List[str]) -> CompletedProcess[str]:
    """Run a subprocess command and capture stdout/stderr without raising."""
    return run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def _probe_embedded_subtitle_stream_count(video_path: str) -> int:
    """Return the number of subtitle streams already embedded in a container."""
    ffprobe = which("ffprobe")
    if not ffprobe:
        log_error(
            "Missing required tool 'ffprobe'. Install ffmpeg and ensure 'ffprobe' is on PATH."
        )
        raise RuntimeError("ffprobe is required for subtitle merging")

    proc = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "s",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            video_path,
        ]
    )
    if proc.returncode != 0:
        log_error(f"ffprobe failed for '{video_path}':\n{proc.stderr.strip()}")
        raise RuntimeError(f"ffprobe failed for '{video_path}'")

    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    return len(lines)


def _probe_subtitle_streams(video_path: str) -> List[Dict[str, Any]]:
    """Probe subtitle streams (order-preserving) from a container using ffprobe."""
    ffprobe = which("ffprobe")
    if not ffprobe:
        log_error(
            "Missing required tool 'ffprobe'. Install ffmpeg and ensure 'ffprobe' is on PATH."
        )
        return []

    proc = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-select_streams",
            "s",
            video_path,
        ]
    )
    if proc.returncode != 0:
        log_error(f"ffprobe failed for '{video_path}':\n{proc.stderr.strip()}")
        return []

    try:
        payload: Dict[str, Any] = loads(proc.stdout or "{}")
    except (JSONDecodeError, TypeError):
        return []

    streams = payload.get("streams") or []
    if not isinstance(streams, list):
        return []
    return [s for s in streams if isinstance(s, dict)]


def _subtitle_language_needs_tag(language: Optional[str]) -> bool:
    if not language:
        return True
    folded = language.strip().casefold()
    return folded in {"und", "unknown", "0"}


def _normalize_language_tag_to_iso639_2(language: Optional[str]) -> Optional[str]:
    if not language:
        return None
    folded = language.strip().casefold()
    if len(folded) == 3 and folded.isalpha():
        return folded
    return _iso639_1_to_2(folded)


def _lang2_from_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    token = title.strip().split()[0].casefold()
    if len(token) == 3 and token.isalpha() and token in ISO639_1_TO_2.values():
        return token
    return None


def _extract_embedded_subtitle_to_srt(
    ffmpeg: str,
    video_path: str,
    subtitle_stream_index: int,
) -> Optional[str]:
    """Extract a subtitle stream to an SRT file for language detection."""
    with NamedTemporaryFile(mode="wb", delete=False, suffix=".srt") as tmp:
        tmp_path = tmp.name

    proc = _run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            video_path,
            "-map",
            f"0:s:{subtitle_stream_index}",
            "-c:s",
            "srt",
            tmp_path,
        ]
    )
    if proc.returncode != 0:
        try:
            remove(tmp_path)
        except OSError:
            pass
        return None
    return tmp_path


def _handle_existing_language_tag(out_s_index, language, title_overrides):
    lang2_existing = _normalize_language_tag_to_iso639_2(language)
    if lang2_existing:
        title_overrides[out_s_index] = lang2_existing


def _handle_title_lang2(out_s_index, title, lang_overrides):
    title_lang2 = _lang2_from_title(title)
    if title_lang2:
        lang_overrides[out_s_index] = title_lang2
        return True
    return False


def _handle_tmp_srt(out_s_index, ffmpeg, video_path, lang_overrides, title_overrides):
    tmp_srt = _extract_embedded_subtitle_to_srt(ffmpeg, video_path, out_s_index)
    if not tmp_srt:
        return
    try:
        detected, is_sdh = _detect_subtitle_language_and_sdh(tmp_srt)
    finally:
        try:
            remove(tmp_srt)
        except OSError:
            pass
    if detected:
        lang_overrides[out_s_index] = detected
        title_overrides[out_s_index] = f"{detected} SDH" if is_sdh else detected


def _get_overrides(
    streams: List[Dict[str, Any]], video_path: str, ffmpeg: str
) -> Tuple[Dict[int, str], Dict[int, str]]:
    lang_overrides: Dict[int, str] = {}
    title_overrides: Dict[int, str] = {}
    for out_s_index, stream in enumerate(streams):
        tags = stream.get("tags") or {}
        language = tags.get("language") if isinstance(tags, dict) else None
        title = tags.get("title") if isinstance(tags, dict) else None

        if not _subtitle_language_needs_tag(language) and not (title or ""):
            _handle_existing_language_tag(out_s_index, language, title_overrides)
            continue

        if _handle_title_lang2(out_s_index, title, lang_overrides):
            continue

        _handle_tmp_srt(
            out_s_index, ffmpeg, video_path, lang_overrides, title_overrides
        )

    return lang_overrides, title_overrides


def _tag_embedded_subtitle_languages(video_path: str) -> None:
    """Detect and tag missing language metadata for already-embedded subtitle streams."""
    if not os_path.isfile(video_path):
        return

    ffmpeg = _which_or_log("ffmpeg")
    if not ffmpeg:
        return

    streams = _probe_subtitle_streams(video_path)
    if not streams:
        return

    lang_overrides, title_overrides = _get_overrides(streams, video_path, ffmpeg)

    if not lang_overrides and not title_overrides:
        return

    st = stat(video_path)
    tmp_out = _create_temp_output_path(video_path)
    try:
        cmd: List[str] = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            video_path,
            "-map",
            "0",
            "-c",
            "copy",
            "-map_metadata",
            "0",
            "-map_chapters",
            "0",
        ]

        for out_s_index, lang2 in sorted(lang_overrides.items()):
            cmd.extend([f"-metadata:s:s:{out_s_index}", f"language={lang2}"])
        for out_s_index, title in sorted(title_overrides.items()):
            cmd.extend([f"-metadata:s:s:{out_s_index}", f"title={title}"])
        cmd.append(tmp_out)

        proc = _run(cmd)
        if proc.returncode != 0:
            log_error(
                (
                    f"ffmpeg failed tagging embedded subtitle languages in '{video_path}':\n"
                    f"{proc.stderr.strip()}"
                )
            )
            return

        replace(tmp_out, video_path)
        utime(video_path, ns=(st.st_atime_ns, st.st_mtime_ns))
    finally:
        try:
            if os_path.exists(tmp_out):
                remove(tmp_out)
        except OSError:
            pass


def _stem_lower(filename: str) -> str:
    """Return the lowercase filename stem (basename without extension)."""
    return os_path.splitext(filename)[0].casefold()


def _is_video(filename: str) -> bool:
    """Return True if filename has a recognized video extension."""
    return filename.lower().endswith(VIDEO_EXTENSIONS)


def _is_subtitle(filename: str) -> bool:
    """Return True if filename has a recognized subtitle extension."""
    return filename.lower().endswith(SUBTITLE_EXTENSIONS)


def _is_subtitles_dir_name(name: str) -> bool:
    """Return True if directory name indicates a subtitles folder."""
    return name.casefold() in {"subs", "subtitles"}


def _list_immediate_subtitle_dirs(root: str) -> List[str]:
    """List immediate child directories of *root* named 'Subs' or 'Subtitles'."""
    try:
        entries = listdir(root)
    except OSError:
        return []

    result: List[str] = []
    for entry in entries:
        if not _is_subtitles_dir_name(entry):
            continue
        candidate = os_path.join(root, entry)
        if os_path.isdir(candidate):
            result.append(candidate)
    return result


def _gather_subtitle_files_under(directory: str) -> List[str]:
    """Recursively collect subtitle files under *directory*, skipping Plex folders."""
    found: List[str] = []
    for walk_root, _, files in walk(directory, topdown=True):
        if is_plex_folder(walk_root):
            continue
        for f in files:
            if _is_subtitle(f):
                found.append(os_path.join(walk_root, f))
    return found


def _is_text_subtitle_path(sub_path: str) -> bool:
    """Return True if subtitle path points to a text-based subtitle format."""
    return os_path.splitext(sub_path)[1].lower() in TEXT_SUBTITLE_EXTENSIONS


def _normalized_subtitle_bytes_for_hash(sub_path: str) -> bytes:
    """Read subtitle bytes normalized for robust de-duplication."""
    with open(sub_path, "rb") as f:
        data = f.read()

    if not _is_text_subtitle_path(sub_path):
        return data

    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]

    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def _dedupe_subtitle_inputs(subtitle_paths: Sequence[str]) -> List[str]:
    """De-duplicate subtitle inputs by path + content hash (text normalized)."""
    unique_paths = sorted({os_path.abspath(p) for p in subtitle_paths})

    idx_stems = {
        os_path.splitext(p)[0].casefold()
        for p in unique_paths
        if p.lower().endswith(".idx")
    }
    pruned: List[str] = []
    for p in unique_paths:
        if (
            p.lower().endswith(".sub")
            and os_path.splitext(p)[0].casefold() in idx_stems
        ):
            continue
        pruned.append(p)

    seen_hashes: set[str] = set()
    deduped: List[str] = []
    for p in pruned:
        try:
            payload = _normalized_subtitle_bytes_for_hash(p)
        except OSError:
            continue

        digest = sha256(payload).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        deduped.append(p)

    return deduped


def _video_folder_name_matches(
    video_filename: str, video_stem: str, folder_name: str
) -> bool:
    """Return True if a subtitle folder name appears to match a specific video."""
    folded = folder_name.casefold()
    if folded == video_stem:
        return True
    if folded == video_filename.casefold():
        return True
    return _subtitle_matches_video(video_stem, folded)


def _subtitle_matches_video(video_stem: str, subtitle_stem: str) -> bool:
    """Return True if a subtitle stem matches the video stem (common separators allowed)."""
    if subtitle_stem == video_stem:
        return True
    for sep in (".", "-", "_"):
        if subtitle_stem.startswith(video_stem + sep):
            return True
    return False


def _index_subtitles_by_stem(
    root: str, subtitle_files: Sequence[str]
) -> Dict[str, List[str]]:
    """Index subtitle files in *root* by lowercase stem."""
    subs_by_stem: Dict[str, List[str]] = {}
    for sub in subtitle_files:
        subs_by_stem.setdefault(_stem_lower(sub), []).append(os_path.join(root, sub))
    return subs_by_stem


def _extend_plan(
    plans: Dict[str, List[str]], video_path: str, subtitle_paths: Sequence[str]
) -> None:
    """Append subtitle paths into a plan map entry."""
    if subtitle_paths:
        plans.setdefault(video_path, []).extend(subtitle_paths)


def _match_same_folder_subtitles(
    root: str, video_files: Sequence[str], subtitle_files: Sequence[str]
) -> Dict[str, List[str]]:
    """Match subtitles found in *root* to videos in the same folder."""
    subs_by_stem = _index_subtitles_by_stem(root, subtitle_files)
    matches: Dict[str, List[str]] = {}

    for video in video_files:
        video_stem = _stem_lower(video)
        matched: List[str] = []
        for sub_stem, sub_paths in subs_by_stem.items():
            if _subtitle_matches_video(video_stem, sub_stem):
                matched.extend(sub_paths)
        if matched:
            matches[os_path.join(root, video)] = matched

    return matches


def _scan_subtitle_dir(subs_dir: str) -> tuple[List[str], Dict[str, List[str]]]:
    """Return (first_level_dirs, subs_dir_by_stem) for a subtitle directory."""
    try:
        first_level_dirs = [
            d for d in listdir(subs_dir) if os_path.isdir(os_path.join(subs_dir, d))
        ]
    except OSError:
        first_level_dirs = []

    try:
        subs_dir_files = [
            os_path.join(subs_dir, f)
            for f in listdir(subs_dir)
            if os_path.isfile(os_path.join(subs_dir, f)) and _is_subtitle(f)
        ]
    except OSError:
        subs_dir_files = []

    subs_dir_by_stem: Dict[str, List[str]] = {}
    for p in subs_dir_files:
        subs_dir_by_stem.setdefault(_stem_lower(os_path.basename(p)), []).append(p)

    return (first_level_dirs, subs_dir_by_stem)


def _match_subs_dir_for_video(
    subs_dir: str,
    video_filename: str,
    video_stem: str,
    first_level_dirs: Sequence[str],
    subs_dir_by_stem: Dict[str, List[str]],
) -> List[str]:
    """Find subtitle matches for a single video inside a Subs/Subtitles directory."""
    per_video_matches: List[str] = []

    for folder in first_level_dirs:
        if _video_folder_name_matches(video_filename, video_stem, folder):
            per_video_matches.extend(
                _gather_subtitle_files_under(os_path.join(subs_dir, folder))
            )

    if per_video_matches:
        return per_video_matches

    direct_matches: List[str] = []
    for sub_stem, sub_paths in subs_dir_by_stem.items():
        if _subtitle_matches_video(video_stem, sub_stem):
            direct_matches.extend(sub_paths)

    return direct_matches


def _add_matches_from_subtitle_dir(
    plans: Dict[str, List[str]], root: str, video_files: Sequence[str], subs_dir: str
) -> None:
    """Add matches found under a single immediate Subs/Subtitles directory."""
    first_level_dirs, subs_dir_by_stem = _scan_subtitle_dir(subs_dir)
    for video in video_files:
        video_path = os_path.join(root, video)
        matched = _match_subs_dir_for_video(
            subs_dir,
            video,
            _stem_lower(video),
            first_level_dirs,
            subs_dir_by_stem,
        )
        _extend_plan(plans, video_path, matched)

    if len(video_files) == 1:
        _add_single_video_remaining_under_subs_dir(
            plans, os_path.join(root, video_files[0]), subs_dir
        )


def _add_single_video_remaining_under_subs_dir(
    plans: Dict[str, List[str]], video_path: str, subs_dir: str
) -> None:
    """When a folder contains one video, embed all remaining subs under Subs/Subtitles."""
    already = set(plans.get(video_path, []))
    all_under_subs = _gather_subtitle_files_under(subs_dir)
    remaining = [p for p in all_under_subs if p not in already]
    _extend_plan(plans, video_path, remaining)


def _add_single_video_remaining_in_root(
    plans: Dict[str, List[str]],
    video_path: str,
    root: str,
    subtitle_files: Sequence[str],
) -> None:
    """When a folder contains one video, embed remaining subs in the same folder."""
    already = set(plans.get(video_path, []))
    remaining = [
        os_path.join(root, s)
        for s in subtitle_files
        if os_path.join(root, s) not in already
    ]
    _extend_plan(plans, video_path, remaining)


def _discover_plans(directory: str) -> List[SubtitleMergePlan]:
    """Return subtitle-embedding plans discovered under a directory.

    The discovery logic looks for:
    - subtitles in the same folder as a video, and
    - subtitles under immediate `Subs/` or `Subtitles/` folders.

    It attempts to match subtitles to videos by filename stem, and falls back to
    embedding remaining subtitles when a folder contains only a single video.
    """
    plans: Dict[str, List[str]] = {}

    for root, files in ((r, f) for r, _, f in walk(directory, topdown=True)):
        if is_plex_folder(root):
            continue

        video_files = [f for f in files if _is_video(f)]
        if not video_files:
            continue

        subtitle_files = [f for f in files if _is_subtitle(f)]
        subtitle_dirs = _list_immediate_subtitle_dirs(root)
        if not subtitle_files and not subtitle_dirs:
            continue

        for video_path, subs in _match_same_folder_subtitles(
            root, video_files, subtitle_files
        ).items():
            _extend_plan(plans, video_path, subs)

        for subs_dir in subtitle_dirs:
            _add_matches_from_subtitle_dir(plans, root, video_files, subs_dir)

        if len(video_files) == 1:
            _add_single_video_remaining_in_root(
                plans, os_path.join(root, video_files[0]), root, subtitle_files
            )

    result = [
        SubtitleMergePlan(
            video_path=os_path.abspath(video_path),
            subtitle_paths=tuple(sorted({os_path.abspath(p) for p in subs})),
        )
        for video_path, subs in plans.items()
        if subs
    ]
    result.sort(key=lambda p: p.video_path)
    return result


def _mp4_compatible_subtitle_paths(paths: Sequence[str]) -> List[str]:
    """Filter subtitle paths to formats compatible with MP4 mov_text."""
    ok_ext = (".srt", ".vtt")
    compatible: List[str] = []
    for p in paths:
        if os_path.splitext(p)[1].lower() in ok_ext:
            compatible.append(p)
        else:
            log_error(f"Skipping subtitle not compatible with MP4 mov_text: {p}")
    return compatible


def _embeddable_subtitles_for_video(
    video_path: str, subtitle_paths: Sequence[str]
) -> tuple[bool, List[str]]:
    """Return (is_mp4, subtitle_paths) after filtering to existing/compatible inputs."""
    is_mp4 = os_path.splitext(video_path)[1].lower() == ".mp4"

    existing_subs = [p for p in subtitle_paths if os_path.isfile(p)]
    if not existing_subs:
        return (is_mp4, [])

    existing_subs = _dedupe_subtitle_inputs(existing_subs)
    if not existing_subs:
        return (is_mp4, [])

    if is_mp4:
        existing_subs = _mp4_compatible_subtitle_paths(existing_subs)
        if not existing_subs:
            return (is_mp4, [])
        existing_subs = _dedupe_subtitle_inputs(existing_subs)
        if not existing_subs:
            return (is_mp4, [])

    return (is_mp4, existing_subs)


def _create_temp_output_path(video_path: str) -> str:
    """Create a temp output file path next to *video_path* and return it."""
    out_dir = os_path.dirname(video_path)
    out_suffix = os_path.splitext(video_path)[1]

    with NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=out_dir,
        prefix=".submerge.",
        suffix=out_suffix,
    ) as tmp:
        return tmp.name


def _build_subtitle_embed_cmd(
    *,
    ffmpeg: str,
    video_path: str,
    subtitle_paths: Sequence[str],
    tmp_path: str,
    is_mp4: bool,
    existing_embedded_sub_count: int,
) -> List[str]:
    """Build an ffmpeg command to embed subtitle inputs into a container."""
    cmd: List[str] = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        video_path,
    ]

    for sub in subtitle_paths:
        cmd.extend(["-i", sub])

    cmd.extend(["-map", "0"])
    for i in range(len(subtitle_paths)):
        cmd.extend(["-map", str(i + 1)])

    cmd.extend(
        [
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-map_metadata",
            "0",
            "-map_chapters",
            "0",
            "-c:s",
            "copy",
        ]
    )

    if is_mp4:
        start = existing_embedded_sub_count
        end = existing_embedded_sub_count + len(subtitle_paths)
        for out_s_index in range(start, end):
            cmd.extend([f"-c:s:{out_s_index}", "mov_text"])

    for i, sub_path in enumerate(subtitle_paths):
        out_s_index = existing_embedded_sub_count + i
        lang2, is_sdh = _detect_subtitle_language_and_sdh(sub_path)
        if not lang2:
            continue
        cmd.extend([f"-metadata:s:s:{out_s_index}", f"language={lang2}"])
        title = f"{lang2} SDH" if is_sdh else lang2
        cmd.extend([f"-metadata:s:s:{out_s_index}", f"title={title}"])

    cmd.append(tmp_path)
    return cmd


def _delete_paths_best_effort(paths: Sequence[str]) -> None:
    """Delete a sequence of paths best-effort, logging failures."""
    for p in paths:
        try:
            remove(p)
        except OSError as e:
            log_error(f"Failed to delete file '{p}': {e}")


def _embed_subtitles(plan: SubtitleMergePlan) -> None:
    """Embed subtitles described by *plan* into the target video.

    This is a best-effort operation. Failures are logged and do not raise.
    """
    if is_plex_folder(plan.video_path) or is_plex_folder(
        os_path.dirname(plan.video_path)
    ):
        return

    if not os_path.isfile(plan.video_path):
        log_error(f"Video file not found: {plan.video_path}")
        return

    is_mp4, existing_subs = _embeddable_subtitles_for_video(
        plan.video_path, plan.subtitle_paths
    )
    if not existing_subs:
        return

    ffmpeg = _which_or_log("ffmpeg")
    if not ffmpeg:
        return

    try:
        existing_embedded_sub_count = _probe_embedded_subtitle_stream_count(
            plan.video_path
        )
    except RuntimeError:
        return

    st = stat(plan.video_path)
    tmp_path = _create_temp_output_path(plan.video_path)

    try:
        cmd = _build_subtitle_embed_cmd(
            ffmpeg=ffmpeg,
            video_path=plan.video_path,
            subtitle_paths=existing_subs,
            tmp_path=tmp_path,
            is_mp4=is_mp4,
            existing_embedded_sub_count=existing_embedded_sub_count,
        )
        proc = _run(cmd)
        if proc.returncode != 0:
            log_error(
                (
                    f"ffmpeg failed embedding subtitles into '{plan.video_path}':\n"
                    f"{proc.stderr.strip()}"
                )
            )
            return

        replace(tmp_path, plan.video_path)
        utime(plan.video_path, ns=(st.st_atime_ns, st.st_mtime_ns))

        _delete_paths_best_effort(existing_subs)
    finally:
        try:
            if os_path.exists(tmp_path):
                remove(tmp_path)
        except OSError as e:
            log_error(f"Failed to clean up temporary file '{tmp_path}': {e}")


def merge_subtitles_in_directory(directory: str):
    """Discover and embed subtitles for videos under *directory*.

    This is a best-effort operation: failures are logged and will not raise.
    It is a no-op when `[Subtitles] enable_subtitle_embedding` is disabled.
    """
    if not get_enable_subtitle_embedding():
        return

    for root, _, files in walk(directory, topdown=True):
        if is_plex_folder(root):
            continue
        video_files = [f for f in files if f.lower().endswith(VIDEO_EXTENSIONS)]
        for f in video_files:
            try:
                _tag_embedded_subtitle_languages(os_path.join(root, f))
            except OSError:
                continue

    plans = _discover_plans(directory)
    try:
        for plan in plans:
            _embed_subtitles(plan)
    except (OSError, RuntimeError, ValueError) as e:
        log_error(f"Unexpected error during subtitle merging: {e}")
        return
