# Copilot instructions (Plex-Organizer)

## Big picture

- Entry point is `qb_organizer.py`: orchestrates cleanup → rename → move, and optionally removes a completed torrent via qBittorrent.
- Media-specific logic lives in `tv.py` and `movie.py`:
  - TV rename format: `Show Name SxxExx [Quality].ext`, then move into `tv/<Show>/Season <xx>/`.
  - Movie rename format: `Name (Year) [Quality].ext`, then move into the target movies folder.
- File/dir filtering and shared behaviors:
  - Constants in `const.py` (`INC_FILTER`, `EXT_FILTER`, `UNWANTED_FOLDERS`).
  - Helpers in `utils.py` (duplicate handling, capitalization rules, "Plex Versions" detection, start-dir mode detection).
  - Logging in `log.py` (errors + duplicates) controlled by `config.ini`.

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
  - Extra/unknown options in known sections are removed by `check_config()`; don’t invent new keys without updating `config.py`.
- qBittorrent integration (`qb.py`): calls `POST {host}/api/v2/torrents/delete` with `deleteFiles=false`.
  - Host comes from `[qBittorrent] host` (default `http://localhost:8081`).

## Developer workflows (Windows-first repo)

- Fast local verification uses the provided VS Code task `Run Batch Script` → `test.bat`.
  - It copies `testData/` into fresh `testEnv*` folders, creates/activates `venv/`, installs `requirements.txt`, then runs `qb_organizer.py` against multiple layouts.
- Manual run (direct Python): `python qb_organizer.py <start_dir> [torrent_hash]`.
- Linux/macOS wrapper script: `./run.sh <start_dir> [torrent_hash]` (expects `venv/` under repo root).

## Conventions to follow when changing code

- Prefer using `utils.move_file()` for any rename/move so duplicate handling + optional deletion (`Settings.delete_duplicates`) stays consistent.
- Don’t touch Plex-managed content: skip paths containing `Plex Versions` (`utils.is_plex_folder()`).
- Keep filename parsing regex-driven and conservative (see `tv.py.rename()` and `movie.py.rename()` patterns).

## Tooling

- Formatting: Black is the configured formatter (see `.vscode/settings.json`).
- Linting in CI: `pylint` runs on push (see `.github/workflows/pylint.yml`, report is informational).
