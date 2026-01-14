# Copilot instructions (Plex-Organizer)

## Big picture

- Entry point is `plex_organizer.py`: acquires a best-effort single-instance lock, then orchestrates:
  - (Optional) subtitle embedding into containers
  - (Optional) audio-language tagging
  - Aggressive cleanup (delete unwanted files/folders)
  - Rename + move into final TV/Movie layout
  - Per-library indexing so already-processed files can be skipped on future runs
  - Delete empty folders
  - (Optional) remove a completed torrent via qBittorrent
- Media-specific logic lives in `tv.py` and `movie.py`:
  - TV rename format: `Show Name SxxExx Quality.ext` (quality included only when `[Settings] include_quality = true`), then move into `tv/<Show>/Season <xx>/`.
  - Movie rename format: `Name (Year) Quality.ext` (quality included only when `[Settings] include_quality = true`), then move into the target movies folder.
- File/dir filtering and shared behaviors:
  - Constants in `const.py` (`VIDEO_EXTENSIONS`, `EXT_FILTER`, `UNWANTED_FOLDERS`, subtitle extension lists, ISO 639 mappings).
  - Helpers in `utils.py` (duplicate handling, capitalization rules, "Plex Versions" detection, start-dir mode detection).
  - Logging in `log.py` (errors + duplicates) controlled by `config.ini`.
  - Subtitle embedding in `subtitles.py` (enabled by config).
  - Indexing in `indexing.py` via `.plex_organizer.index` files.

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
  - A single torrent save path folder (processed as-is).
- TV show name source differs by mode:
  - Main folder mode: show name is derived from `tv/<Show>/...` path.
  - Single-folder mode: show name is derived from the folder name passed in.

## Configuration & integration points

- `config.ini` is mandatory and auto-managed by `config.ensure_config_exists()`.
  - Missing required options are added.
  - Extra/unknown options in known sections are removed during startup config validation; don’t invent new keys without updating `config.py`.
- qBittorrent integration (`qb.py`): calls `POST {host}/api/v2/torrents/delete` with `deleteFiles=false`.
  - Host comes from `[qBittorrent] host` (default `http://localhost:8081`).
  - Auth is implemented via `/api/v2/auth/login` using `[qBittorrent] username/password`.
  - Torrent removal is best-effort: failures are logged; processing continues.

## Audio language tagging

- Controlled by `[Audio] enable_audio_tagging` (default `true`).
- Implemented in `audio.py` and `whisper_detector.py`:
  - Uses `ffprobe` to enumerate audio streams.
  - For streams with missing/unknown `language` tags, extracts short WAV samples with `ffmpeg` and runs `faster-whisper` to infer spoken language.
  - Writes ISO 639-2 (`eng`, `spa`, etc.) back into the container via an `ffmpeg -c copy` remux (in-place replace).
- This runs after move/rename; it should still skip Plex folders and should log errors rather than raise.

## Subtitle embedding

- Controlled by `[Subtitles] enable_subtitle_embedding` (default `true`).
- Implemented in `subtitles.py`:
  - Discovers external subtitles (including under `Subs/` / `Subtitles/`).
  - Detects subtitle language (ISO 639-2) and SDH best-effort.
  - Embeds into the container via `ffmpeg`.
- This runs before cleanup removes subtitle files/folders.

## Developer workflows

- Fast local verification (Linux/macOS/Dev Container): `bash ./test.sh`.
  - It copies `testData/` into `testEnv/`, creates/activates `venv/`, installs `requirements.txt`, then runs `plex_organizer.py`.
- Manual run (direct Python): `python plex_organizer.py <start_dir> [torrent_hash]`.
- Linux/macOS wrapper script: `./run.sh <start_dir> [torrent_hash]` (expects `venv/` under repo root).

## Conventions to follow when changing code

- Prefer using `utils.move_file()` for any rename/move so duplicate handling + optional deletion (`Settings.delete_duplicates`) stays consistent.
- Don’t touch Plex-managed content: skip paths containing `Plex Versions` (`utils.is_plex_folder()`).
- Keep filename parsing regex-driven and conservative (see `tv.py.rename()` and `movie.py.rename()` patterns).

## Tooling

- Formatting: Black is the configured formatter (see `.vscode/settings.json`).
- Linting in CI: `pylint` runs on push (see `.github/workflows/pylint.yml`, report is informational).
