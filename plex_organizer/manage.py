"""Interactive management menu for Plex Organizer.

Launched via ``plex-organizer --manage``.  Presents a
numbered menu with ``q`` to quit:

1. Show organizer folder (data dir with config, logs, lock file)
2. View the latest log
3. Migrate a pre-v6 config.ini to the current format
4. Run the index generator for a media folder
5. Kill running organizers
6. Custom run (pick individual pipeline steps)
7. Migrate old per-show TV indexes to TV root
8. Edit configuration
"""

from __future__ import annotations

from collections.abc import Callable
from configparser import ConfigParser
from contextlib import ExitStack
from datetime import datetime
from glob import glob
from json import JSONDecodeError, load
from os import (
    environ,
    getpid,
    kill,
    remove,
    unlink,
    walk,
)
from os.path import (
    abspath,
    basename,
    dirname,
    exists,
    expanduser,
    getmtime,
    getsize,
    isdir,
    isfile,
    join,
    normpath,
    relpath,
)
from re import compile as re_compile
from signal import SIGKILL
from subprocess import (
    CalledProcessError,
    DEVNULL,
    TimeoutExpired,
    call,
    check_output,
    run,
)
from sys import exit as sys_exit, modules as _modules
from tempfile import NamedTemporaryFile
from typing import Dict, Set
from unittest.mock import patch

from . import config as _config
from .paths import data_dir
from .audio.tagging import tag_audio_track_languages
from .config import ensure_config_exists
from .const import INDEX_FILENAME, VIDEO_EXTENSIONS
from .dataclass import IndexSummary
from .indexing import (
    index_root_for_path,
    mark_indexed,
    migrate_show_indexes_to_tv_root,
    prune_index,
    should_index_video,
)
from .subs.embedding import merge_subtitles_in_directory
from .subs.fetching import fetch_subtitles_in_directory
from .subs.syncing import sync_subtitles_in_directory
from .pipeline import (
    analyze_video_languages,
    delete_empty_directories,
    delete_unwanted_files,
    get_video_files_to_process,
    move_directories,
)
from .utils import is_main_folder, is_plex_folder, is_script_temp_file

__all__ = [
    "_expand_folder",
    "_run_full_pipeline",
    "_run_embed_subs",
    "_run_fetch_subs",
    "_run_sync_subs",
    "_run_tag_audio",
    "_run_cleanup",
    "_run_rename_move",
    "_run_delete_empty",
]

LOCK_FILENAME = ".plex_organizer.lock"


def _find_pids() -> list[int]:
    """Return PIDs of running plex-organizer processes (excluding ourselves)."""
    own_pid = getpid()
    try:
        output = check_output(
            ["pgrep", "-f", "plex.organizer"],
            text=True,
            stderr=DEVNULL,
        )
    except (CalledProcessError, FileNotFoundError):
        return []

    pids: list[int] = []
    for line in output.strip().splitlines():
        try:
            pid = int(line)
        except ValueError:
            continue
        if pid == own_pid:
            continue
        pids.append(pid)
    return pids


def _process_cmdline(pid: int) -> str:
    """Return the command line of *pid* for display purposes."""
    try:
        output = check_output(
            ["ps", "-p", str(pid), "-o", "args="],
            text=True,
            stderr=DEVNULL,
        )
        return output.strip()
    except (CalledProcessError, FileNotFoundError):
        return "unknown"


def kill_run() -> None:
    """Kill running plex-organizer processes and remove the lock file."""
    killed = 0

    for pid in _find_pids():
        cmdline = _process_cmdline(pid)
        try:
            kill(pid, SIGKILL)
            print(f"Killed process {pid} ({cmdline})")
            killed += 1
        except ProcessLookupError:
            pass
        except PermissionError:
            print(f"Permission denied killing process {pid} ({cmdline})")

    lock_path = join(data_dir(), LOCK_FILENAME)
    if exists(lock_path):
        try:
            remove(lock_path)
            print(f"Removed lock file: {lock_path}")
        except OSError as exc:
            print(f"Failed to remove lock file: {exc}")
    else:
        print(f"No lock file found at {lock_path}")

    if killed == 0:
        print("No running plex-organizer processes found.")
    else:
        print(f"Killed {killed} process(es).")


def _rel_key(index_root: str, file_path: str) -> str:
    """Return the index key for *file_path* relative to *index_root*."""
    rel = relpath(file_path, index_root)
    return normpath(rel)


def _read_index_keys(index_root: str) -> Set[str]:
    """Read existing index keys for *index_root*.

    Returns an empty set when the index does not exist or cannot be read.
    """
    idx_path = join(index_root, INDEX_FILENAME)
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            payload = load(f)
    except FileNotFoundError:
        return set()
    except (OSError, JSONDecodeError):
        return set()

    if not isinstance(payload, dict):
        return set()

    files = payload.get("files")
    if isinstance(files, dict):
        return set(files.keys())

    return set()


def _directories_to_scan(start_dir: str) -> list[str]:
    """Resolve *start_dir* into one or more directories to scan.

    Raises:
        ValueError: when *start_dir* does not match any accepted shape.
    """
    tv_dir = join(start_dir, "tv")
    movies_dir = join(start_dir, "movies")

    if isdir(tv_dir) and isdir(movies_dir):
        return [tv_dir, movies_dir]

    base = basename(normpath(start_dir)).lower()
    if base == "tv":
        return [start_dir]
    if base == "movies":
        return [start_dir]

    parent = basename(dirname(normpath(start_dir))).lower()
    if parent == "tv":
        return [start_dir]

    raise ValueError(
        "Invalid root. Provide either a folder containing BOTH"
        " 'tv' and 'movies', or the 'tv' folder,"
        " or a 'tv/<Show>' folder, or the 'movies' folder."
    )


def _add_summary(a: IndexSummary, b: IndexSummary) -> IndexSummary:
    """Add two summaries together."""
    return IndexSummary(
        total_videos=a.total_videos + b.total_videos,
        eligible_videos=a.eligible_videos + b.eligible_videos,
        newly_indexed=a.newly_indexed + b.newly_indexed,
    )


def _is_video_candidate(file_name: str) -> bool:
    """Return True if *file_name* is a video file we should consider."""
    if is_script_temp_file(file_name):
        return False
    return file_name.lower().endswith(VIDEO_EXTENSIONS)


def _safe_should_index_video(index_root: str, video_path: str) -> bool:
    """Best-effort wrapper for ``should_index_video``."""
    try:
        return should_index_video(index_root, video_path)
    except OSError:
        return False


def _safe_mark_indexed(index_root: str, video_path: str) -> bool:
    """Best-effort wrapper for ``mark_indexed``."""
    try:
        mark_indexed(index_root, video_path)
        return True
    except OSError:
        return False


def _get_or_load_index_keys(cache: Dict[str, Set[str]], index_root: str) -> Set[str]:
    """Return cached index keys for *index_root*, reading from disk if needed."""
    keys = cache.get(index_root)
    if keys is None:
        keys = _read_index_keys(index_root)
        cache[index_root] = keys
    return keys


def _scan_and_index_root(
    directory: str,
    root: str,
    files: list[str],
    cache: Dict[str, Set[str]],
) -> IndexSummary:
    """Scan a single filesystem *root* and update index files as needed."""
    total_videos = 0
    eligible_videos = 0
    newly_indexed = 0

    if is_plex_folder(root):
        return IndexSummary(0, 0, 0)

    index_root = index_root_for_path(directory, root)
    index_keys = _get_or_load_index_keys(cache, index_root)

    for file_name in files:
        if not _is_video_candidate(file_name):
            continue

        total_videos += 1
        video_path = join(root, file_name)
        if not _safe_should_index_video(index_root, video_path):
            continue

        eligible_videos += 1
        key = _rel_key(index_root, video_path)
        if key in index_keys:
            continue

        if not _safe_mark_indexed(index_root, video_path):
            continue

        index_keys.add(key)
        newly_indexed += 1

    return IndexSummary(
        total_videos=total_videos,
        eligible_videos=eligible_videos,
        newly_indexed=newly_indexed,
    )


def _scan_and_index_directory(
    directory: str, cache: Dict[str, Set[str]]
) -> IndexSummary:
    """Walk *directory* recursively and update index files (best-effort)."""
    summary = IndexSummary(0, 0, 0)
    for root, _, files in walk(directory):
        summary = _add_summary(
            summary, _scan_and_index_root(directory, root, files, cache)
        )
    return summary


def generate_indexes(start_dir: str) -> IndexSummary:
    """Generate/backfill organizer index files under *start_dir*.

    Only indexes videos already in the organizer's final layout.
    """
    start_dir = abspath(start_dir)
    if not isdir(start_dir):
        raise ValueError(f"Not a directory: {start_dir}")

    ensure_config_exists()

    dirs = _directories_to_scan(start_dir)
    cache: Dict[str, Set[str]] = {}

    total_videos = 0
    eligible_videos = 0
    newly_indexed = 0
    for directory in dirs:
        summary = _scan_and_index_directory(directory, cache)
        total_videos += summary.total_videos
        eligible_videos += summary.eligible_videos
        newly_indexed += summary.newly_indexed

    print(
        "\n".join(
            [
                f"Scanned: {start_dir}",
                f"Run at: {datetime.now().isoformat(timespec='seconds')}",
                f"Videos found: {total_videos}",
                f"Eligible (correct place/name): {eligible_videos}",
                f"Newly indexed: {newly_indexed}",
            ]
        )
    )

    return IndexSummary(
        total_videos=total_videos,
        eligible_videos=eligible_videos,
        newly_indexed=newly_indexed,
    )


def _config_path() -> str:
    """Return the current CONFIG_PATH (respects monkeypatching in tests)."""
    return _config.CONFIG_PATH


_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_BLUE = "\033[34m"
_CYAN = "\033[36m"
_GRAY = "\033[90m"
_GREEN = "\033[32m"
_LIGHT_GREEN = "\033[92m"
_MAGENTA = "\033[35m"
_RED = "\033[31m"
_WHITE = "\033[37m"
_YELLOW = "\033[33m"


def _heading(text: str) -> str:
    return f"{_BOLD}{_GREEN}{text}{_RESET}"


def _key(text: str) -> str:
    return f"{_CYAN}{text}{_RESET}"


def _warn(text: str) -> str:
    return f"{_YELLOW}{text}{_RESET}"


def _dim(text: str) -> str:
    return f"{_DIM}{text}{_RESET}"


def _err(text: str) -> str:
    return f"{_RED}{text}{_RESET}"


_LEVEL_COLORS: dict[str, str] = {
    "ERROR": _RED,
    "WARNING": _YELLOW,
    "DUPLICATE": _MAGENTA,
    "DEBUG": _GRAY,
    "INFO": _BLUE,
}

_LOG_LINE_RE = re_compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})( - )(\[[A-Z]+\])( - )(.*)",
)


def _colorize_log_line(line: str) -> str:
    """Return *line* with ANSI colors applied to date-time and level."""
    m = _LOG_LINE_RE.match(line)
    if not m:
        return line
    timestamp, sep1, level_tag, sep2, msg = m.groups()
    level_name = level_tag.strip("[]")
    lc = _LEVEL_COLORS.get(level_name, _WHITE)
    return (
        f"{_LIGHT_GREEN}{timestamp}{_RESET}"
        f"{sep1}"
        f"{_BOLD}{lc}{level_tag}{_RESET}"
        f"{sep2}"
        f"{msg}"
    )


def _find_latest_log() -> str | None:
    """Return the path to the latest log file, or *None* if none exist.

    Checks the timestamped ``logs/`` subdirectory first (sorted by mtime,
    newest first), then falls back to the single ``plex-organizer.log`` in the
    data directory.
    """
    base = data_dir()
    logs_dir = join(base, "logs")

    timestamped = (
        sorted(
            glob(join(logs_dir, "*.log")),
            key=getmtime,
            reverse=True,
        )
        if isdir(logs_dir)
        else []
    )

    if timestamped:
        return timestamped[0]

    single = join(base, "plex-organizer.log")
    if isfile(single) and getsize(single) > 0:
        return single

    return None


def _find_pager() -> str:
    """Return the name of an available pager, or empty string."""
    pager = environ.get("PAGER", "")
    if pager:
        return pager
    for candidate in ("less", "more"):
        if _command_exists(candidate):
            return candidate
    return ""


def _show_in_pager(pager: str, colored: str) -> bool:
    """Try to display *colored* text in *pager*. Return True on success."""
    tmp_path = None
    try:
        with NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(colored)
            tmp_path = tmp.name
        cmd = [pager]
        if pager == "less":
            cmd.append("-R")
        cmd.append(tmp_path)
        call(cmd)
        return True
    except OSError:
        return False
    finally:
        if tmp_path:
            try:
                unlink(tmp_path)
            except OSError:
                pass


def _command_exists(name: str) -> bool:
    """Return True if *name* is found on $PATH."""
    try:
        check_output(["which", name], stderr=DEVNULL)
        return True
    except (CalledProcessError, FileNotFoundError):
        return False


def _wait_for_quit(input_fn=input) -> None:
    """Block until the user types ``q``."""
    while True:
        try:
            key = input_fn("  Press q to return to menu: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if key == "q":
            return


def _action_open_folder(**_kwargs) -> None:
    """Open the organizer data directory in the system file manager."""
    folder = data_dir()
    print(f"\n  Organizer folder: {_key(folder)}")
    try:
        run(
            ["xdg-open", folder],
            stdout=DEVNULL,
            stderr=DEVNULL,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, TimeoutExpired):
        print(f"  {_dim('(xdg-open not available — open the path above manually)')}")
    print()


def _action_view_log(input_fn=input) -> None:
    """Display the latest log file in a pager (less/more) so the user can scroll."""
    log_path = _find_latest_log()
    if log_path is None:
        print(f"\n  {_warn('No log files found.')}\n")
        return

    print(f"\n  Showing: {_key(log_path)}")
    print(f"  {_dim('(press q to return to menu)')}\n")

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as exc:
        print(f"  {_err(f'Failed to read log: {exc}')}\n")
        return

    if not raw.strip():
        print(f"  {_dim('(log file is empty)')}\n")
        return

    colored = "\n".join(_colorize_log_line(l) for l in raw.splitlines()) + "\n"

    pager = _find_pager()
    if pager and _show_in_pager(pager, colored):
        return

    for line in colored.splitlines():
        print(f"  {line}")
    print()
    _wait_for_quit(input_fn)


_NEW_SUBTITLE_DEFAULTS: dict[str, str] = {
    "analyze_embedded_subtitles": "true",
    "fetch_subtitles": "eng",
    "subtitle_providers": "opensubtitles, podnapisi, gestdown, tvsubtitles",
    "sync_subtitles": "true",
}


def migrate_config(old_path: str) -> int:
    """Read a pre-v6 config.ini and merge its values into the current config.

    Existing user values from the old file are preserved.  Any keys present in
    the current default config but missing from the old file are filled with
    their defaults.

    Args:
        old_path: Absolute or relative path to the old ``config.ini``.

    Returns:
        The number of new keys that were added during migration.
    """
    if not isfile(old_path):
        raise FileNotFoundError(f"File not found: {old_path}")

    old = ConfigParser()
    old.read(old_path)

    _config.ensure_config_exists()

    current = ConfigParser()
    current.read(_config_path())

    for section in old.sections():
        if not current.has_section(section):
            continue
        for key in old.options(section):
            if current.has_option(section, key):
                current.set(section, key, old.get(section, key))

    added = 0
    if current.has_section("Subtitles"):
        for key, default in _NEW_SUBTITLE_DEFAULTS.items():
            if not old.has_option("Subtitles", key):
                current.set("Subtitles", key, default)
                added += 1

    with open(_config_path(), "w", encoding="utf-8") as f:
        current.write(f)

    return added


def _action_migrate_config(input_fn=input) -> None:
    """Prompt for an old config path and migrate it."""
    print()
    try:
        old_path = input_fn("  Path to old config.ini: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not old_path:
        print(f"\n  {_warn('No path provided.')}\n")
        return

    old_path = expanduser(old_path)
    try:
        added = migrate_config(old_path)
        print(
            f"\n  {_key('Migration complete.')} "
            f"{added} new key(s) added to {_dim(_config_path())}\n"
        )
    except FileNotFoundError:
        print(f"\n  {_err('File not found:')} {old_path}\n")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n  {_err(f'Migration failed: {exc}')}\n")


def _action_generate_indexes(input_fn=input) -> None:
    """Prompt for a media folder and run the index generator."""
    print()
    try:
        folder = input_fn("  Media folder to index: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not folder:
        print(f"\n  {_warn('No path provided.')}\n")
        return

    folder = abspath(expanduser(folder))
    if not isdir(folder):
        print(f"\n  {_err('Not a directory:')} {folder}\n")
        return

    print()
    try:
        generate_indexes(folder)
    except ValueError as exc:
        print(f"\n  {_err(str(exc))}\n")
    print()


def _action_kill_organizers(**_kwargs) -> None:
    """Kill all running plex-organizer processes."""
    print()
    kill_run()
    print()


def _action_migrate_tv_indexes(input_fn=input) -> None:
    """Migrate old per-show TV index files into a single TV-root index."""
    print()
    try:
        folder = input_fn("  TV root folder (e.g. /media/tv): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not folder:
        print(f"\n  {_warn('No path provided.')}\n")
        return

    folder = abspath(expanduser(folder))
    if not isdir(folder):
        print(f"\n  {_err('Not a directory:')} {folder}\n")
        return

    try:
        count = migrate_show_indexes_to_tv_root(folder)
        if count:
            print(
                f"\n  {_key('Migration complete.')} "
                f"Merged {count} per-show index(es) into {_dim(folder)}\n"
            )
        else:
            print(f"\n  {_dim('No per-show index files found to migrate.')}\n")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n  {_err(f'Migration failed: {exc}')}\n")


def _expand_folder(folder: str) -> list[str]:
    """Expand *folder* into per-library directories when it is a main folder.

    When *folder* is a main folder (contains ``tv/`` and/or ``movies/``
    subfolders) the returned list contains the existing subdirectory paths.
    Otherwise the original *folder* is returned as-is so single-library
    directories keep working.
    """
    if is_main_folder(folder):
        dirs = []
        for sub in ("tv", "movies"):
            candidate = join(folder, sub)
            if isdir(candidate):
                dirs.append(candidate)
        return dirs if dirs else [folder]
    return [folder]


def _index_root_videos(index_root: str, root: str, files: list[str]) -> None:
    """Mark un-indexed video files in a single *root* directory."""
    for f in files:
        if not _is_video_candidate(f):
            continue
        video_path = join(root, f)
        if should_index_video(index_root, video_path):
            mark_indexed(index_root, video_path)


def _index_directory_videos(directory: str) -> None:
    """Walk *directory* and mark un-indexed video files, then prune stale entries."""
    index_root = index_root_for_path(directory, directory)
    prune_index(index_root)

    for root, _, files in walk(directory):
        if is_plex_folder(root):
            continue
        _index_root_videos(index_root, root, files)


def _update_index_after_custom_run(folder: str) -> None:
    """Walk *folder* and mark any un-indexed video files as indexed.

    Also prunes stale entries whose files no longer exist on disk (e.g.
    after a rename/move operation).
    """
    for directory in _expand_folder(folder):
        _index_directory_videos(directory)


def _find_all_videos(folder: str) -> list[str]:
    """Return paths for every video file under *folder*, ignoring the index."""
    videos: list[str] = []
    for root, _, files in walk(folder):
        if is_plex_folder(root):
            continue
        for f in files:
            if is_script_temp_file(f):
                continue
            if f.lower().endswith(VIDEO_EXTENSIONS):
                videos.append(join(root, f))
    return videos


def _prompt_yes_no(input_fn, prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question. Return *default* on empty input."""
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        answer = input_fn(f"    {prompt} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not answer:
        return default
    return answer.startswith("y")


def _prompt_string(input_fn, prompt: str, default: str = "") -> str:
    """Ask for a free-text value. Return *default* on empty input."""
    hint = f" [{default}]" if default else ""
    try:
        answer = input_fn(f"    {prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return answer if answer else default


def _prompt_int(input_fn, prompt: str, default: int) -> int:
    """Ask for an integer value. Return *default* on empty input."""
    try:
        answer = input_fn(f"    {prompt} [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not answer:
        return default
    try:
        return int(answer)
    except ValueError:
        return default


def _no_index_video_map(folder: str) -> dict[str, bool]:
    """Return a video map where nothing is marked as indexed."""
    return dict.fromkeys(_find_all_videos(folder), False)


def _collect_pipeline_settings(input_fn) -> dict:
    """Prompt the user for all pipeline toggles and return them as a dict."""
    print(f"\n  {_heading('Configure pipeline settings:')}\n")
    fetch_langs_str = _prompt_string(
        input_fn, "Fetch subtitle languages (e.g. eng,spa; empty to skip)", ""
    )
    return {
        "analyze_embedded": _prompt_yes_no(
            input_fn, "Analyze already-embedded subtitles?"
        ),
        "fetch_langs": (
            [c.strip().lower() for c in fetch_langs_str.split(",") if c.strip()]
            if fetch_langs_str
            else []
        ),
        "do_sync": _prompt_yes_no(input_fn, "Sync subtitles to audio?"),
        "do_tag": _prompt_yes_no(input_fn, "Tag audio languages?"),
        "cpu": _prompt_int(input_fn, "CPU threads for Whisper", 2),
        "inc_quality": _prompt_yes_no(input_fn, "Include quality in filename?"),
        "do_capitalize": _prompt_yes_no(input_fn, "Capitalize file names?"),
        "del_dups": _prompt_yes_no(input_fn, "Delete duplicates?", default=False),
    }


def _pipeline_patches(settings: dict):
    """Return a combined context manager patching all config getters."""
    stack = ExitStack()
    targets = [
        ("plex_organizer.subs.embedding.get_enable_subtitle_embedding", True),
        (
            "plex_organizer.subs.embedding.get_analyze_embedded_subtitles",
            settings["analyze_embedded"],
        ),
        ("plex_organizer.subs.fetching.get_fetch_subtitles", settings["fetch_langs"]),
        ("plex_organizer.subs.syncing.get_sync_subtitles", settings["do_sync"]),
        ("plex_organizer.config.get_enable_audio_tagging", settings["do_tag"]),
        ("plex_organizer.pipeline.get_enable_audio_tagging", settings["do_tag"]),
        ("plex_organizer.audio.tagging.get_cpu_threads", settings["cpu"]),
        ("plex_organizer.utils.get_include_quality", settings["inc_quality"]),
        ("plex_organizer.utils.get_capitalize", settings["do_capitalize"]),
        ("plex_organizer.utils.get_delete_duplicates", settings["del_dups"]),
    ]
    for target, value in targets:
        stack.enter_context(patch(target, return_value=value))
    return stack


def _run_full_pipeline(folder: str, input_fn=input) -> None:
    settings = _collect_pipeline_settings(input_fn)
    print()

    for directory in _expand_folder(folder):
        print(f"  {_dim('Processing directory:')} {directory}")
        all_videos = _find_all_videos(directory)
        no_index = _no_index_video_map(directory)

        with _pipeline_patches(settings):
            print(f"    {_dim('Embedding subtitles...')}")
            for vp in all_videos:
                print(f"      {_dim(basename(vp))}")
            merge_subtitles_in_directory(directory, video_paths=all_videos)
            print(f"    {_dim('Fetching subtitles...')}")
            for vp in all_videos:
                print(f"      {_dim(basename(vp))}")
            fetch_subtitles_in_directory(directory, video_paths=all_videos)
            print(f"    {_dim('Syncing subtitles...')}")
            for vp in all_videos:
                print(f"      {_dim(basename(vp))}")
            sync_subtitles_in_directory(directory, video_paths=all_videos)

            print(f"    {_dim('Tagging audio, cleaning up & moving files...')}")
            for root, _, files in walk(directory, topdown=False):
                videos = get_video_files_to_process(root, files, no_index)
                for v in videos:
                    print(f"      {_dim(v)}")
                analyze_video_languages(root, videos)
                delete_unwanted_files(root, files)
                move_directories(directory, root, videos)

            print(f"    {_dim('Deleting empty folders...')}")
            delete_empty_directories(directory)

    print(f"  {_dim('Updating index...')}")
    _update_index_after_custom_run(folder)


def _run_embed_subs(folder: str, input_fn=input) -> None:
    print()
    analyze = _prompt_yes_no(input_fn, "Analyze already-embedded subtitles?")
    print()

    for directory in _expand_folder(folder):
        print(f"  {_dim('Embedding subtitles in:')} {directory}")
        vids = _find_all_videos(directory)
        for vp in vids:
            print(f"    {_dim(basename(vp))}")
        with (
            patch(
                "plex_organizer.subs.embedding.get_enable_subtitle_embedding",
                return_value=True,
            ),
            patch(
                "plex_organizer.subs.embedding.get_analyze_embedded_subtitles",
                return_value=analyze,
            ),
        ):
            merge_subtitles_in_directory(directory, video_paths=vids)

    print(f"  {_dim('Updating index...')}")
    _update_index_after_custom_run(folder)


def _run_fetch_subs(folder: str, input_fn=input) -> None:
    print()
    langs_str = _prompt_string(input_fn, "Languages to fetch (e.g. eng,spa)", "eng")
    langs = [c.strip().lower() for c in langs_str.split(",") if c.strip()]
    print()

    if not langs:
        print(f"  {_warn('No languages specified, skipping.')}\n")
        return

    for directory in _expand_folder(folder):
        print(f"  {_dim('Fetching subtitles in:')} {directory}")
        vids = _find_all_videos(directory)
        for vp in vids:
            print(f"    {_dim(basename(vp))}")
        with patch(
            "plex_organizer.subs.fetching.get_fetch_subtitles",
            return_value=langs,
        ):
            fetch_subtitles_in_directory(directory, video_paths=vids)

    print(f"  {_dim('Updating index...')}")
    _update_index_after_custom_run(folder)


def _run_sync_subs(folder: str, **_kwargs) -> None:
    for directory in _expand_folder(folder):
        print(f"  {_dim('Syncing subtitles in:')} {directory}")
        vids = _find_all_videos(directory)
        for vp in vids:
            print(f"    {_dim(basename(vp))}")
        with patch(
            "plex_organizer.subs.syncing.get_sync_subtitles",
            return_value=True,
        ):
            sync_subtitles_in_directory(directory, video_paths=vids)

    print(f"  {_dim('Updating index...')}")
    _update_index_after_custom_run(folder)


def _run_tag_audio(folder: str, input_fn=input) -> None:
    print()
    cpu = _prompt_int(input_fn, "CPU threads for Whisper", 2)
    print()

    for directory in _expand_folder(folder):
        print(f"  {_dim('Tagging audio in:')} {directory}")
        with patch(
            "plex_organizer.audio.tagging.get_cpu_threads",
            return_value=cpu,
        ):
            for video_path in _find_all_videos(directory):
                print(f"    {_dim(basename(video_path))}")
                tag_audio_track_languages(video_path)

    print(f"  {_dim('Updating index...')}")
    _update_index_after_custom_run(folder)


def _run_cleanup(folder: str, **_kwargs) -> None:
    for directory in _expand_folder(folder):
        print(f"  {_dim('Cleaning up:')} {directory}")
        for root, _, files in walk(directory, topdown=False):
            for f in files:
                print(f"    {_dim(f)}")
            delete_unwanted_files(root, files)

    print(f"  {_dim('Updating index...')}")
    _update_index_after_custom_run(folder)


def _run_rename_move(folder: str, input_fn=input) -> None:
    print()
    inc_quality = _prompt_yes_no(input_fn, "Include quality in filename?")
    do_capitalize = _prompt_yes_no(input_fn, "Capitalize file names?")
    del_dups = _prompt_yes_no(input_fn, "Delete duplicates?", default=False)
    print()

    for directory in _expand_folder(folder):
        print(f"  {_dim('Renaming & moving in:')} {directory}")
        no_index = _no_index_video_map(directory)
        with (
            patch(
                "plex_organizer.utils.get_include_quality",
                return_value=inc_quality,
            ),
            patch(
                "plex_organizer.utils.get_capitalize",
                return_value=do_capitalize,
            ),
            patch(
                "plex_organizer.utils.get_delete_duplicates",
                return_value=del_dups,
            ),
        ):
            for root, _, files in walk(directory, topdown=False):
                videos = [
                    f
                    for f in files
                    if f.lower().endswith(VIDEO_EXTENSIONS)
                    and not no_index.get(join(root, f), False)
                ]
                for v in videos:
                    print(f"    {_dim(v)}")
                move_directories(directory, root, videos)

    print(f"  {_dim('Updating index...')}")
    _update_index_after_custom_run(folder)


def _run_delete_empty(folder: str, **_kwargs) -> None:
    for directory in _expand_folder(folder):
        print(f"  {_dim('Deleting empty folders in:')} {directory}")
        delete_empty_directories(directory)

    print(f"  {_dim('Updating index...')}")
    _update_index_after_custom_run(folder)


_CUSTOM_RUN_STEPS: list[tuple[str, str]] = [
    ("Full pipeline (all steps)", "_run_full_pipeline"),
    ("Embed subtitles", "_run_embed_subs"),
    ("Fetch subtitles", "_run_fetch_subs"),
    ("Sync subtitles", "_run_sync_subs"),
    ("Tag audio languages", "_run_tag_audio"),
    ("Cleanup (delete unwanted files/folders)", "_run_cleanup"),
    ("Rename & move", "_run_rename_move"),
    ("Delete empty folders", "_run_delete_empty"),
]


def _print_step_menu(selected_steps: list[int]) -> None:
    """Print the step selection menu for custom run."""
    print()
    print(f"  {_heading('Custom Run — Step Selection')}")
    if selected_steps:
        sel_labels = [_CUSTOM_RUN_STEPS[i - 1][0] for i in selected_steps]
        print(f"  Selected steps: {_key(', '.join(sel_labels))}")
    else:
        print(f"  {_dim('No steps selected yet.')}")
    print()
    for idx, (label, _) in enumerate(_CUSTOM_RUN_STEPS, start=1):
        sel_mark = _GREEN + "*" + _RESET if idx in selected_steps else " "
        print(f"    {sel_mark} {_key(str(idx))}. {label}")
    print()
    print(f"      {_key('r')}. Run selected steps")
    print(f"      {_key('q')}. Cancel")
    print()


def _run_selected_steps(selected_steps: list[int], folder: str, input_fn) -> None:
    """Execute already-selected custom-run steps in order."""
    _mod = _modules[__name__]
    for step_num in selected_steps:
        label, fn_name = _CUSTOM_RUN_STEPS[step_num - 1]
        step_fn = getattr(_mod, fn_name)
        print(f"  Running: {_key(label)} on {_dim(folder)} ...")
        try:
            step_fn(folder, input_fn=input_fn)
            print(f"\n  {_key('Done.')}")
        except Exception as exc:  # pylint: disable=broad-except
            print(f"\n  {_err(f'Error: {exc}')}")


def _toggle_steps(choice: str, selected_steps: list[int]) -> None:
    """Parse *choice* as comma-separated step numbers and toggle them."""
    for sn in (c.strip() for c in choice.split(",") if c.strip()):
        try:
            idx = int(sn)
        except ValueError:
            print(f"\n  {_err(f'Invalid option: {sn}')}")
            continue
        if not 1 <= idx <= len(_CUSTOM_RUN_STEPS):
            print(f"\n  {_err(f'Invalid option: {sn}')}")
            continue
        if idx in selected_steps:
            selected_steps.remove(idx)
        else:
            selected_steps.append(idx)


def _action_custom_run(input_fn=input) -> None:
    """Run specific parts of the organizer pipeline on a chosen directory.

    Presents a toggle menu where the user selects/deselects steps by number,
    then types ``r`` to run all selected steps or ``q`` to cancel.
    """
    print()
    try:
        folder = input_fn("  Directory to process: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not folder:
        print(f"\n  {_warn('No path provided.')}\n")
        return

    folder = abspath(expanduser(folder))
    if not isdir(folder):
        print(f"\n  {_err('Not a directory:')} {folder}\n")
        return

    selected_steps: list[int] = []
    while True:
        _print_step_menu(selected_steps)
        try:
            choice = (
                input_fn(
                    "    Add/remove step(s) (numbers, comma-separated),"
                    " r to run, q to cancel: "
                )
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if choice == "q":
            return
        if choice == "r":
            if not selected_steps:
                print(f"\n  {_err('No steps selected.')}")
                continue
            _run_selected_steps(selected_steps, folder, input_fn)
            return
        _toggle_steps(choice, selected_steps)


_CONFIG_KEY_TYPES: dict[tuple[str, str], str] = {
    ("qBittorrent", "host"): "str",
    ("qBittorrent", "username"): "str",
    ("qBittorrent", "password"): "str",
    ("Settings", "delete_duplicates"): "bool",
    ("Settings", "include_quality"): "bool",
    ("Settings", "capitalize"): "bool",
    ("Settings", "cpu_threads"): "int",
    ("Logging", "enable_logging"): "bool",
    ("Logging", "log_file"): "str",
    ("Logging", "clear_log"): "bool",
    ("Logging", "timestamped_log_files"): "bool",
    ("Logging", "level"): "str",
    ("Audio", "enable_audio_tagging"): "bool",
    ("Audio", "whisper_model_size"): "str",
    ("Subtitles", "enable_subtitle_embedding"): "bool",
    ("Subtitles", "analyze_embedded_subtitles"): "bool",
    ("Subtitles", "fetch_subtitles"): "str",
    ("Subtitles", "subtitle_providers"): "str",
    ("Subtitles", "sync_subtitles"): "bool",
}


def _print_config(config: ConfigParser) -> list[tuple[str, str]]:
    """Print the current config and return a flat list of (section, key) pairs.

    Each option is printed with a sequential number so the user can pick one.
    Returns the ordered list for index look-up.
    """
    entries: list[tuple[str, str]] = []
    for section in config.sections():
        print(f"\n    {_heading(f'[{section}]')}")
        for key in config.options(section):
            idx = len(entries) + 1
            value = config.get(section, key)
            type_hint = _CONFIG_KEY_TYPES.get((section, key), "str")
            hint = f" {_dim(f'({type_hint})')}" if type_hint != "str" else ""
            print(f"      {_key(str(idx)):>8s}. {key} = {_CYAN}{value}{_RESET}{hint}")
            entries.append((section, key))
    return entries


def _validate_config_value(type_hint: str, value: str) -> str | None:
    """Return an error message if *value* is invalid for *type_hint*, else None."""
    if type_hint == "bool" and value.lower() not in ("true", "false"):
        return "Value must be 'true' or 'false'."
    if type_hint == "int":
        try:
            int(value)
        except ValueError:
            return "Value must be an integer."
    return None


def _prompt_new_config_value(
    input_fn, key: str, current: str, type_hint: str
) -> str | None:
    """Prompt for a new config value. Return *None* to skip the edit."""
    if type_hint == "bool":
        new_value = "false" if current.lower() == "true" else "true"
        print(f"\n    {key}: {_DIM}{current}{_RESET} → {_CYAN}{new_value}{_RESET}")
        return new_value

    try:
        new_value = input_fn(f"    New value for {key} [{current}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return new_value or None


def _action_edit_config(input_fn=input) -> None:
    """Interactive config editor.

    Shows all config sections and options with sequential numbers.  The user
    picks a number to edit, enters a new value, and the change is written to
    disk immediately.  ``q`` returns to the main menu.
    """
    _config.ensure_config_exists()
    config = ConfigParser()
    config.read(_config_path())

    while True:
        print(f"\n  {_heading('Configuration')}  {_dim(_config_path())}")
        entries = _print_config(config)
        print(f"\n      {_key('q')}. Back to menu\n")

        try:
            choice = input_fn("    Select option to edit: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if choice == "q":
            return

        try:
            idx = int(choice)
        except ValueError:
            print(f"\n  {_err('Invalid option.')}")
            continue

        if not 1 <= idx <= len(entries):
            print(f"\n  {_err('Invalid option.')}")
            continue

        section, key = entries[idx - 1]
        current = config.get(section, key)
        type_hint = _CONFIG_KEY_TYPES.get((section, key), "str")

        new_value = _prompt_new_config_value(input_fn, key, current, type_hint)
        if new_value is None:
            continue

        error = _validate_config_value(type_hint, new_value)
        if error:
            print(f"\n  {_err(error)}")
            continue

        config.set(section, key, new_value)
        with open(_config_path(), "w", encoding="utf-8") as f:
            config.write(f)
        print(f"    {_key('Saved.')}")


MENU_OPTIONS: list[tuple[str, Callable[..., None]]] = [
    ("Show organizer folder", _action_open_folder),
    ("View latest log", _action_view_log),
    ("Migrate old config (pre-v6)", _action_migrate_config),
    ("Generate indexes", _action_generate_indexes),
    ("Kill running organizers", _action_kill_organizers),
    ("Custom run", _action_custom_run),
    ("Migrate TV indexes to root", _action_migrate_tv_indexes),
    ("Edit configuration", _action_edit_config),
]


def _print_menu() -> None:
    """Print the numbered menu."""
    print()
    print(f"  {_heading('Plex Organizer — Setup')}")
    print()
    for idx, (label, _) in enumerate(MENU_OPTIONS, start=1):
        print(f"    {_key(str(idx))}. {label}")
    print(f"    {_key('q')}. Quit")
    print()


def _run_menu(*, input_fn=input) -> None:
    """Display the menu in a loop until the user quits."""
    while True:
        _print_menu()
        try:
            choice = input_fn("  Select an option: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice == "q":
            break

        try:
            idx = int(choice)
        except ValueError:
            print(f"\n  {_err('Invalid option.')}")
            continue

        if 1 <= idx <= len(MENU_OPTIONS):
            _, action = MENU_OPTIONS[idx - 1]
            action(input_fn=input_fn)
        else:
            print(f"\n  {_err('Invalid option.')}")


def main() -> None:
    """Entry-point for ``plex-organizer --manage``."""
    _config.ensure_config_exists()
    _run_menu()
    sys_exit(0)


if __name__ == "__main__":
    main()
