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
  - TV rename format: `Show Name SxxExx Quality.ext` (quality included only when `[Settings] include_quality = true`), then move into `tv/<Show>/Season <xx>/`.
  - Movie rename format: `Name (Year) Quality.ext` (quality included only when `[Settings] include_quality = true`), then move into the target movies folder.
- File/dir filtering and shared behaviors:
  - Constants in `plex_organizer/const.py` (`VIDEO_EXTENSIONS`, `EXT_FILTER`, `UNWANTED_FOLDERS`, subtitle extension lists, ISO 639 mappings).
  - Helpers in `plex_organizer/utils.py` (duplicate handling, capitalization rules, "Plex Versions" detection, start-dir mode detection).
  - Logging in `plex_organizer/log.py` (errors + duplicates) controlled by `config.ini`.
  - FFmpeg/FFprobe wrappers in `plex_organizer/ffmpeg_utils.py` (shared probing and remuxing helpers; binaries provided by `static-ffmpeg`).
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
├── _paths.py            # data-directory resolution (config, logs, lock file)
├── cli_generate_indexes.py  # plex-organizer-index CLI
├── config.py            # config.ini access & auto-management
├── const.py             # shared constants (extensions, folders, ISO mappings)
├── dataclass.py         # shared data classes
├── ffmpeg_utils.py      # ffprobe/ffmpeg wrapper helpers
├── indexing.py          # per-library .plex_organizer.index files
├── log.py               # logging facade
├── movie.py             # movie rename/move logic
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
  - TV: index is stored in the show root (`tv/<Show>/`).
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

- Install in editable mode: `pip install -e ".[dev]"`.
- Run: `sudo plex-organizer <start_dir> [torrent_hash]` or `sudo python -m plex_organizer <start_dir> [torrent_hash]`.
- Index generation: `plex-organizer-index <media_root>`.
- The project is packaged via `pyproject.toml` — dependencies are declared there (not in `requirements.txt`).
- `update.sh` pulls the latest code and reinstalls the package.
- Data directory: defaults to `/root/.config/plex-organizer/` (config, logs, lock file). Override with `PLEX_ORGANIZER_DIR` env var.

## Conventions to follow when changing code

- Prefer using `utils.move_file()` for any rename/move so duplicate handling + optional deletion (`Settings.delete_duplicates`) stays consistent.
- Don’t touch Plex-managed content: skip paths containing `Plex Versions` (`utils.is_plex_folder()`).
- Keep filename parsing regex-driven and conservative (see `plex_organizer/tv.py` and `plex_organizer/movie.py` patterns).

## Tooling

- Formatting: Black is the configured formatter (see `.vscode/settings.json`).
- Linting in CI: `pylint` runs on push (see `.github/workflows/pylint.yml`, report is informational).
