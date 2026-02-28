"""Fetch missing subtitles from the web using subliminal.

When configured with one or more ISO 639-2 language codes
(e.g. ``fetch_subtitles = eng, est``), this module searches online subtitle
providers and embeds the best match for each requested language into the
video container via ffmpeg.

Only languages that are **not** already present as embedded subtitle streams
are fetched.  Plex-managed folders are always skipped.
"""

from __future__ import annotations

from os import path as os_path, remove
from typing import List

from babelfish import Language
from subliminal import (
    download_best_subtitles,
    region,
    save_subtitles,
    scan_video,
)

from config import get_fetch_subtitles, get_subtitle_providers
from const import VIDEO_EXTENSIONS
from ffmpeg_utils import (
    build_ffmpeg_base_cmd,
    create_temp_output,
    probe_subtitle_languages,
    probe_subtitle_stream_count,
    replace_and_restore_timestamps,
    run_cmd,
    which_or_log,
)
from log import log_debug, log_error
from utils import is_plex_folder

# One-time in-memory cache so subliminal doesn't re-query within the same run.
region.configure("dogpile.cache.memory", replace_existing_backend=True)


def _missing_languages(video_path: str, lang_codes: list[str]) -> list[str]:
    """Return the subset of *lang_codes* not already embedded in the video."""
    existing = probe_subtitle_languages(video_path)
    return [code for code in lang_codes if code not in existing]


def _download_subtitles(
    video_path: str, lang_codes: list[str]
) -> list[tuple[str, str]]:
    """Search online providers for subtitles in the requested languages.

    Args:
        video_path: Path to the video file.
        lang_codes: ISO 639-2 language codes (e.g. ``["eng", "est"]``).

    Returns:
        A list of ``(srt_path, iso639_2_lang)`` tuples for each successfully
        downloaded subtitle, or an empty list when nothing was found.
    """
    try:
        video = scan_video(video_path)
    except ValueError as exc:
        log_error(f"subliminal could not scan '{video_path}': {exc}")
        return []

    languages = set()
    for code in lang_codes:
        try:
            languages.add(Language(code))
        except (ValueError, KeyError):
            log_error(f"Invalid language code '{code}' in fetch_subtitles config")

    if not languages:
        return []

    subtitles = download_best_subtitles(
        {video},
        languages,
        only_one=False,
        providers=get_subtitle_providers(),
    )

    if not subtitles.get(video):
        return []

    saved = save_subtitles(video, subtitles[video], single=False)
    if not saved:
        return []

    results: list[tuple[str, str]] = []
    for sub in saved:
        lang_iso = str(sub.language)
        srt_path = os_path.splitext(video_path)[0] + f".{lang_iso}.srt"
        if os_path.isfile(srt_path):
            iso3 = sub.language.alpha3
            results.append((srt_path, iso3))
    return results


def _embed_srts(video_path: str, srt_files: list[tuple[str, str]]) -> None:
    """Embed downloaded SRT files into the video container and clean up.

    Args:
        video_path: Path to the video file.
        srt_files: List of ``(srt_path, iso639_2_lang)`` tuples.
    """
    if not srt_files:
        return

    ffmpeg = which_or_log("ffmpeg")
    if not ffmpeg:
        return

    is_mp4 = os_path.splitext(video_path)[1].lower() == ".mp4"
    existing_sub_count = probe_subtitle_stream_count(video_path)
    input_paths = [p for p, _ in srt_files]
    tmp_path = create_temp_output(video_path, prefix=".fetchsub.")

    try:
        cmd = build_ffmpeg_base_cmd(ffmpeg, video_path, input_paths)

        for i, (_, lang) in enumerate(srt_files):
            idx = existing_sub_count + i
            if is_mp4:
                cmd.extend([f"-c:s:{idx}", "mov_text"])
            cmd.extend([f"-metadata:s:s:{idx}", f"language={lang}"])
            cmd.extend([f"-metadata:s:s:{idx}", f"title={lang}"])

        cmd.append(tmp_path)

        proc = run_cmd(cmd)
        if proc.returncode != 0:
            log_error(
                f"ffmpeg failed embedding fetched subtitles into '{video_path}':\n"
                f"{proc.stderr.strip()}"
            )
            return

        replace_and_restore_timestamps(tmp_path, video_path)
    finally:
        cleanup = [tmp_path] + input_paths
        for path in cleanup:
            try:
                if os_path.exists(path):
                    remove(path)
            except OSError:
                pass


def _fetch_subtitles_for_video(video_path: str, lang_codes: list[str]) -> None:
    """Fetch and embed subtitles for languages not yet embedded in the video."""
    if not os_path.isfile(video_path):
        log_error(f"Video file not found: {video_path}")
        return

    if is_plex_folder(video_path) or is_plex_folder(os_path.dirname(video_path)):
        return

    missing = _missing_languages(video_path, lang_codes)
    if not missing:
        log_debug(
            f"Skipping subtitle fetch for '{video_path}': "
            "all requested languages already embedded"
        )
        return

    log_debug(
        f"Searching online providers for subtitles ({', '.join(missing)}): "
        f"'{video_path}'"
    )
    srt_files = _download_subtitles(video_path, missing)

    if not srt_files:
        log_debug(f"No subtitles found online for '{video_path}'")
        return

    langs = ", ".join(lang for _, lang in srt_files)
    log_debug(f"Embedding fetched subtitles ({langs}) into '{video_path}'")
    _embed_srts(video_path, srt_files)


def fetch_subtitles_in_directory(directory: str, video_paths: List[str]) -> None:
    """Fetch and embed missing subtitles for videos under *directory*.

    This is a best-effort operation: failures are logged and will not raise.
    It is a no-op when ``[Subtitles] fetch_subtitles`` is empty in config.

    Args:
        directory: Root directory being processed.
        video_paths: List of video file paths to check.
    """
    lang_codes = get_fetch_subtitles()
    if not lang_codes:
        return

    if is_plex_folder(directory):
        return

    log_debug(f"Starting subtitle fetch scan under '{directory}'")

    for video_path in video_paths:
        if not video_path.lower().endswith(VIDEO_EXTENSIONS):
            continue
        try:
            _fetch_subtitles_for_video(video_path, lang_codes)
        except (OSError, RuntimeError, ValueError) as exc:
            log_error(f"Unexpected error fetching subtitles for '{video_path}': {exc}")
            continue
