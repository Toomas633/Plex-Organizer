# Copilot instructions (Plex-Organizer)

## Big picture

- All source modules live in the `plex_organizer/` package. Entry point is `plex_organizer/__main__.py` (invoked via `plex-organizer` CLI or `python -m plex_organizer`): requires root privileges, acquires a best-effort single-instance lock, then orchestrates:
  - (Optional) subtitle embedding into containers
  - (Optional) subtitle fetching from online providers
  - (Optional) subtitle-to-audio synchronization
  - (Optional) audio-language tagging
  - Aggressive cleanup (delete unwanted files/folders)
  - Rename + move into final TV/Movie layout
  - Per-library indexing so already-processed files can be skipped on future runs
  - Delete empty folders
  - (Optional) remove a completed torrent via qBittorrent
- Media-specific logic lives in `plex_organizer/tv.py` and `plex_organizer/movie.py`:
  - TV rename format: `Show Name SxxExx Quality.ext` (quality included only when `[Settings] include_quality = true`; when the filename lacks a quality tag, the video stream height is probed via `ffmpeg_utils.probe_video_quality()` as a fallback), then move into `tv/<Show>/Season <x>/`.
  - Movie rename format: `Name (Year) Quality.ext` (quality included only when `[Settings] include_quality = true`; when the filename lacks a quality tag, the video stream height is probed via `ffmpeg_utils.probe_video_quality()` as a fallback), then move into `movies/<Name (Year)>/`. The subfolder never includes quality.
- File/dir filtering and shared behaviors:
  - Constants in `plex_organizer/const.py` (`VIDEO_EXTENSIONS`, `EXT_FILTER`, `UNWANTED_FOLDERS`, subtitle extension lists, ISO 639 mappings).
  - Helpers in `plex_organizer/utils.py` (duplicate handling, capitalization rules, "Plex Versions" detection, start-dir mode detection).
  - Logging in `plex_organizer/log.py` (errors + duplicates) controlled by `config.ini`.
  - FFmpeg/FFprobe wrappers in `plex_organizer/ffmpeg_utils.py` (shared probing and remuxing helpers; binaries provided by `static-ffmpeg`). Includes `probe_video_quality()` which probes the first video stream height and maps it to a standard label (`2160p`, `1440p`, `1080p`, `720p`, `480p`).
  - Shared pipeline steps in `plex_organizer/pipeline.py` (cleanup, move/rename dispatch, audio tagging, indexing helpers).
  - Subtitle embedding in `plex_organizer/subs/embedding.py` (enabled by config).
  - Subtitle fetching in `plex_organizer/subs/fetching.py` (controlled by `fetch_subtitles` config).
  - Subtitle syncing in `plex_organizer/subs/syncing.py` (controlled by `sync_subtitles` config).
  - Audio language tagging in `plex_organizer/audio/tagging.py` and Whisper inference in `plex_organizer/audio/whisper.py`.
  - Indexing in `plex_organizer/indexing.py` via `.plex_organizer.index` files.

### Project structure

```
plex_organizer/
├── __init__.py
├── __main__.py          # CLI entrypoint (plex-organizer / python -m plex_organizer)
├── paths.py             # data-directory resolution (config, logs, lock file)
├── config.py            # config.ini access & auto-management
├── const.py             # shared constants (extensions, folders, ISO mappings)
├── dataclass.py         # shared data classes
├── ffmpeg_utils.py      # ffprobe/ffmpeg wrapper helpers
├── indexing.py          # per-library .plex_organizer.index files
├── log.py               # logging facade
├── manage.py            # interactive management menu, index generation, kill (--manage)
├── movie.py             # movie rename/move logic
├── organizer.py         # main orchestrator (lock, walk, dispatch pipeline steps)
├── pipeline.py          # shared pipeline steps (cleanup, move/rename, audio tagging)
├── qb.py                # qBittorrent Web API integration
├── tv.py                # TV show rename/move logic
├── utils.py             # shared utility functions
├── audio/
│   ├── __init__.py
│   ├── tagging.py       # audio stream language tagging
│   └── whisper.py       # faster-whisper language detection
└── subs/
    ├── __init__.py
    ├── embedding.py     # external subtitle embedding + metadata
    ├── fetching.py      # online subtitle downloading (subliminal)
    └── syncing.py       # subtitle-to-audio timing sync (ffsubsync)
```

### Test structure

Tests mirror the source package layout and live in the `tests/` directory:

```
tests/
├── __init__.py
├── conftest.py              # shared fixtures & pytest_configure hook
├── test_config.py           # config.py tests
├── test_const.py            # const.py tests
├── test_dataclass.py        # dataclass.py tests
├── test_ffmpeg_utils.py     # ffmpeg_utils.py tests
├── test_indexing.py         # indexing.py tests
├── test_log.py              # log.py tests
├── test_main.py             # __main__.py tests
├── test_manage.py           # manage.py tests
├── test_movie.py            # movie.py tests
├── test_organizer.py        # organizer.py tests
├── test_paths.py            # paths.py tests
├── test_qb.py               # qb.py tests
├── test_tv.py               # tv.py tests
├── test_utils.py            # utils.py tests
├── audio/
│   ├── __init__.py
│   ├── test_audio_tagging.py    # audio/tagging.py tests
│   └── test_audio_whisper.py    # audio/whisper.py tests
└── subs/
    ├── __init__.py
    ├── test_subs_embedding.py       # subs/embedding.py helper tests
    ├── test_subs_embedding_ops.py   # subs/embedding.py operation tests
    ├── test_subs_fetching.py        # subs/fetching.py tests
    └── test_subs_syncing.py         # subs/syncing.py tests
```

- Shared fixtures (`tmp_media_tree`, `config_dir`, `default_config`, etc.) live in `tests/conftest.py` and are available to all subfolders.
- The `PLEX_ORGANIZER_DIR` environment variable must point to a temporary directory when running tests to avoid touching the real config.

## Cleanup behavior (important)

- Cleanup is intentionally aggressive:
  - Files are kept only if they end with `EXT_FILTER` (currently video files, in-progress qBittorrent `.!qB`, and the organizer index file `*.index`). Anything else (e.g., `.srt`, `.nfo`, `.txt`) is deleted.
  - Any file with `sample` in its name is deleted.
  - Folders matching `UNWANTED_FOLDERS` are deleted recursively (includes `Subs`/`Subtitles`, `Extras`, `Sample(s)`, artwork/posters, and `Plex Versions`).
- Plex-managed content must not be modified: always skip paths where `utils.is_plex_folder()` is true.

## Indexing (skip already-processed files)

- Indexing is best-effort and stored as JSON in `.plex_organizer.index`.
- Index root rules (see `indexing.py`):
  - Movies: index is stored in the movies root.
  - TV: index is stored in the TV root (`tv/`). Per-show indexes from older versions are auto-migrated to the TV root on startup.
- Only videos that are already in the organizer's final layout are marked as indexed (prevents skipping raw/unprocessed names).

## How the organizer decides what to process

- `START_DIR` can be either:
  - A “main” folder containing `tv/` and/or `movies/` subfolders (detected by `utils.is_main_folder()`), or
  - A single torrent save path folder whose path includes `tv` or `movies` as a component (processed as-is).
- **Unrecognised directories** (path does not contain `tv` or `movies` and is not a main folder): the organizer removes the torrent (if a hash was provided) and exits immediately — no files are deleted, moved, or modified. This prevents accidental cleanup of generic download folders. Detection: `utils.is_media_directory()`.
- TV show name source differs by mode:
  - Main folder mode: show name is derived from `tv/<Show>/...` path.
  - Single-folder mode: show name is derived from the folder name passed in.

## Configuration & integration points

- `config.ini` is mandatory and auto-managed by `config.ensure_config_exists()`.
  - Missing required options are added.
  - Extra/unknown options in known sections are removed during startup config validation; don't invent new keys without updating `plex_organizer/config.py`.
- qBittorrent integration (`plex_organizer/qb.py`): calls `POST {host}/api/v2/torrents/delete` with `deleteFiles=false`.
  - Host comes from `[qBittorrent] host` (default `http://localhost:8081`).
  - Auth is implemented via `/api/v2/auth/login` using `[qBittorrent] username/password`.
  - Torrent removal is best-effort: failures are logged; processing continues.

## Audio language tagging

- Controlled by `[Audio] enable_audio_tagging` (default `true`).
- Implemented in `plex_organizer/audio/tagging.py` and `plex_organizer/audio/whisper.py`:
  - Uses `ffprobe` to enumerate audio streams.
  - For streams with missing/unknown `language` tags, extracts short WAV samples with `ffmpeg` and runs `faster-whisper` to infer spoken language.
  - Writes ISO 639-2 (`eng`, `spa`, etc.) back into the container via an `ffmpeg -c copy` remux (in-place replace).
- This runs after move/rename; it should still skip Plex folders and should log errors rather than raise.

## Subtitle embedding

- Controlled by `[Subtitles] enable_subtitle_embedding` (default `true`).
- Implemented in `plex_organizer/subs/embedding.py`:
  - Discovers external subtitles (including under `Subs/` / `Subtitles/`).
  - Detects subtitle language (ISO 639-2) and SDH best-effort.
  - Embeds into the container via `ffmpeg`.
- This runs before cleanup removes subtitle files/folders.
- `[Subtitles] analyze_embedded_subtitles` (default `true`):
  - When `true`, also probes already-embedded subtitle streams for missing/unknown language tags, extracts them to temp SRT, detects language + SDH via `langdetect`, and remuxes the tags back.
  - When `false`, only externally embedded subtitles receive language/SDH tagging during the embed step.

## Subtitle fetching

- Controlled by `[Subtitles] fetch_subtitles` (default `eng`).
  - Value is a comma-separated list of ISO 639-2 language codes (e.g. `eng, est`). Empty disables fetching.
- Implemented in `plex_organizer/subs/fetching.py`:
  - Uses `subliminal` to search free online providers (OpenSubtitles, Podnapisi, Gestdown, TVsubtitles).
  - Only fetches languages that are **not** already present as embedded subtitle streams (runs after subtitle embedding).
  - Downloads best-matching SRT for each missing language, embeds via `ffmpeg`, then cleans up.
  - Best-effort: failures are logged; processing continues.

## Subtitle syncing

- Controlled by `[Subtitles] sync_subtitles` (default `true`).
- Implemented in `plex_organizer/subs/syncing.py`:
  - Runs after subtitle embedding and fetching.
  - For each video, probes embedded subtitle streams.
  - Extracts each text-based stream (SRT, ASS/SSA, `mov_text`, WebVTT) to a temp file.
  - Runs `ffsubsync` to align timing to the video's audio track.
  - Compares the synced output to the original via SHA-256; only remuxes if timing actually changed.
  - Bitmap subtitle formats (PGS, DVB, VobSub) are left unchanged.
  - Best-effort: failures are logged; processing continues.

## Developer workflows

- Install in editable mode (dev): `pip install -e ".[dev]"`.
- Install for production (as root): `sudo pipx install git+https://github.com/Toomas633/Plex-Organizer.git`.
- Run: `sudo plex-organizer <start_dir> [torrent_hash]` or `sudo python -m plex_organizer <start_dir> [torrent_hash]`.
- Index generation: via `plex-organizer --manage` → option 4.
- Interactive management menu: `plex-organizer --manage` (menu-driven post-install helper: view data dir, view logs, migrate old config, generate indexes, kill running instances, custom pipeline run, migrate TV indexes, edit configuration).
- The project is packaged via `pyproject.toml` — dependencies are declared there (not in `requirements.txt`).
- Update: `sudo pipx upgrade plex-organizer`.
- Data directory: defaults to `/root/.config/plex-organizer/` (config, logs, lock file). Override with `PLEX_ORGANIZER_DIR` env var.

### Testing

- Framework: `pytest` + `pytest-cov` (dev dependencies in `pyproject.toml`).
- Test layout mirrors `plex_organizer/` under `tests/` (see **Test structure** above).
- Run the full suite:
  ```bash
  PLEX_ORGANIZER_DIR="$(mktemp -d)" python -m pytest
  ```
- Run with coverage:
  ```bash
  PLEX_ORGANIZER_DIR="$(mktemp -d)" python -m pytest --cov=plex_organizer --cov-report=term-missing
  ```
- Run a single subpackage:
  ```bash
  PLEX_ORGANIZER_DIR="$(mktemp -d)" python -m pytest tests/subs/
  ```
- `PLEX_ORGANIZER_DIR` must be set to a temp directory so tests use an isolated config.

## Rules (`.github/copilot-rules/`)

Detailed, topic-specific rules live in `.github/copilot-rules/` and are auto-activated by glob pattern. Always follow these when working on matching files:

| Rule file             | Scope                                             | Key points                                                                                                            |
| --------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `imports.md`          | `plex_organizer/**`, `tests/**`                   | Import specific names; relative imports in source, absolute in tests; 3-group ordering (stdlib → third-party → local) |
| `code-conventions.md` | `plex_organizer/**`                               | Black formatting; use `utils.move_file()`; log errors don't raise; Google-style docstrings                            |
| `testing.md`          | `tests/**`, `plex_organizer/**`                   | pytest + pytest-cov; `config_dir`/`default_config` fixtures; `PLEX_ORGANIZER_DIR` isolation                           |
| `configuration.md`    | `plex_organizer/config.py`, `plex_organizer/**`   | `default_config` dict is source of truth; accessor pattern; unknown keys are auto-removed                             |
| `cleanup-safety.md`   | `plex_organizer/**`                               | Aggressive cleanup; `is_plex_folder()` guard; unrecognised dirs → exit without modifying                              |
| `ffmpeg-usage.md`     | `plex_organizer/**`                               | Use `get_ffmpeg()`/`get_ffprobe()` from `ffmpeg_utils.py`; remux to temp then replace; log failures                   |
| `indexing.md`         | `plex_organizer/indexing.py`, `plex_organizer/**` | Index only final-layout names; movies root vs show root; `.plex_organizer.index` protected from cleanup               |
| `release-notes.md`    | `release/**`                                      | Version numbering (major/minor); gather changes from git log; bold-label bullet style; sub-sections for major releases |

## Tooling

- Formatting: Black is the configured formatter (see `.vscode/settings.json`).
- CI: `pylint` + `pytest` + `pytest-cov` + SonarCloud run on push (see `.github/workflows/sonarcloud.yml`). Pylint report is informational; tests are discovered recursively from `tests/`.
