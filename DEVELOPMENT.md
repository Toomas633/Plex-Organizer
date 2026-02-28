# Development

- [Prerequisites](#prerequisites)
- [Dev Container (VS Code)](#dev-container-vs-code)
- [Local Setup (without Dev Container)](#local-setup-without-dev-container)
- [Project Structure](#project-structure)
- [Pipeline Overview](#pipeline-overview)
- [Testing](#testing)
- [Tooling](#tooling)
- [Code Conventions](#code-conventions)
- [Configuration Notes](#configuration-notes)
- [Contributing](#contributing)

## Prerequisites

- Python 3.x
- `ffmpeg` / `ffprobe` on PATH (required for audio tagging, subtitle embedding, and subtitle generation)
- Docker (only if using the Dev Container)

Python dependencies (`requirements.txt`):

| Package          | Purpose                                        |
| ---------------- | ---------------------------------------------- |
| `faster-whisper` | Audio language detection & subtitle generation |
| `langdetect`     | Subtitle language identification               |
| `requests`       | qBittorrent Web API communication              |
| `black`          | Code formatting                                |
| `pylint`         | Linting                                        |

## Dev Container (VS Code)

This repo ships a full Dev Container configuration (`.devcontainer/`).

1. Install **Docker** (or Docker Desktop) and **VS Code**.
2. In VS Code run: `Dev Containers: Reopen in Container`.

The container automatically:

- Installs `ffmpeg` and system dependencies.
- Creates `venv/` and installs `requirements.txt` via `postCreateCommand`.
- Configures the Python interpreter, Black formatter, and recommended extensions.

> The container does **not** auto-run `test.sh` — run it manually when ready.

## Local Setup (without Dev Container)

```bash
git clone https://github.com/Toomas633/Plex-Organizer.git
cd Plex-Organizer
bash ./install.sh          # creates venv/ and installs dependencies
bash ./install.sh --upgrade  # or upgrade existing dependencies
```

## Project Structure

```
plex_organizer.py   – Entry point: lock, orchestrate, dispatch
config.py           – config.ini management & getters
const.py            – Constants (extensions, folder lists, ISO 639 maps)
utils.py            – Shared helpers (move, capitalize, Plex detection)
log.py              – Logging (errors, duplicates, debug)
tv.py               – TV show rename & move logic
movie.py            – Movie rename & move logic
subtitles.py        – External subtitle discovery & embedding
fetch_subs.py       – Fetch missing subtitles from online providers
audio.py            – Audio stream language tagging
whisper_detector.py – Whisper language detection wrapper
indexing.py         – Per-library index (.plex_organizer.index)
qb.py               – qBittorrent torrent removal
dataclass.py        – Shared data classes
```

## Pipeline Overview

`plex_organizer.py` runs these steps in order for each directory:

1. **Subtitle embedding** — embed external subtitles into video containers.
2. **Subtitle fetching** — download and embed subtitles from online providers for videos without any.
3. **Audio language tagging** — detect and write missing audio language metadata.
4. **Cleanup** — delete unwanted files and folders (aggressive; see below).
5. **Rename & move** — place videos into the final TV/Movie layout.
6. **Delete empty folders**.
7. **(Optional) Torrent removal** via qBittorrent API.

### Cleanup behavior

Cleanup is **intentionally aggressive**:

- Only files matching `EXT_FILTER` are kept (`.mkv`, `.mp4`, `.!qB`, `.plex_organizer.index`).
- Files with `sample` in the name are deleted.
- Folders in `UNWANTED_FOLDERS` are removed recursively (`Subs/`, `Subtitles/`, `Extras/`, `Sample/`, etc.).
- Plex-managed paths (`Plex Versions`) are always skipped via `utils.is_plex_folder()`.

## Testing

### Quick verification

```bash
bash ./test.sh
```

This script:

1. Copies `testData/` into `testEnv/`.
2. Creates/activates `venv/` and installs dependencies.
3. Runs `plex_organizer.py` against `testEnv/`.

### Manual run

```bash
# Via wrapper script (expects venv/ under repo root)
./run.sh <start_dir> [torrent_hash]

# Direct Python
python plex_organizer.py <start_dir> [torrent_hash]
```

### Test data

Place sample media structures under `testData/`. The directory is bind-mounted into the Dev Container. `testEnv/` is the disposable working copy and is `.gitignore`d.

## Tooling

| Tool           | Usage                        | Config                         |
| -------------- | ---------------------------- | ------------------------------ |
| **Black**      | Auto-formatter, runs on save | `.vscode/settings.json`        |
| **pylint**     | Linting (CI + local)         | `.github/workflows/pylint.yml` |
| **SonarCloud** | Quality gate badge           | `.sonarcloud.properties`       |

### Formatting with Black

Black runs automatically on save in VS Code. To format manually:

```bash
# Format a single file
black <file.py>

# Format the entire project
black .

# Check without modifying (dry run)
black --check .
```

### Linting with pylint

```bash
# Lint a single file
pylint <file.py>

# Lint all Python files
pylint *.py

# Lint with a minimum score threshold
pylint --fail-under=8.0 *.py
```

## Code Conventions

- **Moves & renames**: always use `utils.move_file()` so duplicate handling and `delete_duplicates` stay consistent.
- **Plex safety**: never modify paths where `utils.is_plex_folder()` returns `True`.
- **Filename parsing**: keep regex-driven and conservative (see `tv.py.rename()` and `movie.py.rename()`).
- **Config keys**: don't add new keys to `config.ini` without updating the `default_config` dict in `config.py` — unknown options are removed on startup.
- **Error handling**: log errors rather than raising. Processing should continue for other files.

## Configuration Notes

`config.ini` is auto-managed by `config.ensure_config_exists()`:

- Missing sections/options are added with defaults.
- Unknown options in known sections are removed.

When adding a new config option:

1. Add the key + default value to `default_config` in `config.py`.
2. Create a `get_<option>()` accessor function.
3. Document it in the `[Section]` block in `README.md`.

## Contributing

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Commit your changes and push the branch.
4. Open a pull request.
