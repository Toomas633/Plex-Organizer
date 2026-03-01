# Development

- [Prerequisites](#prerequisites)
- [Dev Container (VS Code)](#dev-container-vs-code)
- [Local Setup (without Dev Container)](#local-setup-without-dev-container)
- [Project Structure](#project-structure)
  - [Test Structure](#test-structure)
- [Pipeline Overview](#pipeline-overview)
- [Testing](#testing)
- [Tooling](#tooling)
- [Code Conventions](#code-conventions)
- [Configuration Notes](#configuration-notes)
- [Data Directory](#data-directory)
- [Contributing](#contributing)

## Prerequisites

- Python 3.10+
- Docker (only if using the Dev Container)
- **Root privileges** — the organizer must be run as root (`sudo`)

`ffmpeg`/`ffprobe` are bundled automatically via [`static-ffmpeg`](https://pypi.org/project/static-ffmpeg/) — no separate install needed.

Python dependencies are declared in `pyproject.toml`:

| Package          | Purpose                                  |
| ---------------- | ---------------------------------------- |
| `requests`       | qBittorrent Web API communication        |
| `chardet`        | Character encoding detection             |
| `faster-whisper` | Audio language detection via Whisper     |
| `langdetect`     | Subtitle language identification         |
| `subliminal`     | Online subtitle fetching                 |
| `ffsubsync`      | Subtitle-to-audio timing synchronization |
| `static-ffmpeg`  | Bundled ffmpeg/ffprobe binaries          |

Dev extras (`pip install -e ".[dev]"`):

| Package      | Purpose          |
| ------------ | ---------------- |
| `black`      | Code formatting  |
| `pylint`     | Linting          |
| `pytest`     | Test framework   |
| `pytest-cov` | Coverage reports |

## Dev Container (VS Code)

This repo ships a full Dev Container configuration (`.devcontainer/`).

1. Install **Docker** (or Docker Desktop) and **VS Code**.
2. In VS Code run: `Dev Containers: Reopen in Container`.

The container automatically:

- Installs system dependencies (`python3-dev`, etc.).
- Runs `pip install -e '.[dev]'` via `postCreateCommand`.
- Configures the Python interpreter, Black formatter, and recommended extensions.

> The container does **not** auto-run `test.sh` — run it manually when ready.

## Local Setup (without Dev Container)

```bash
git clone https://github.com/Toomas633/Plex-Organizer.git
cd Plex-Organizer
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

This installs the package in editable mode with three CLI commands on PATH:

| Command                | Purpose                                                               |
| ---------------------- | --------------------------------------------------------------------- |
| `plex-organizer`       | Main organizer pipeline                                               |
| `plex-organizer-index` | Generate index files for an already-organized library                 |
| `plex-organizer-kill`  | Kill running instances and release the lock file                      |
| `plex-organizer-setup` | Interactive post-install helper (logs, config migration, custom runs) |

## Project Structure

```
plex_organizer/
├── __init__.py
├── __main__.py          # CLI entrypoint (plex-organizer / python -m plex_organizer)
├── _paths.py            # data-directory resolution (config, logs, lock file)
├── config.py            # config.ini access & auto-management
├── const.py             # shared constants (extensions, folders, ISO mappings)
├── dataclass.py         # shared data classes
├── ffmpeg_utils.py      # ffprobe/ffmpeg wrapper helpers (uses static-ffmpeg)
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
├── cli/
│   ├── __init__.py
│   ├── generate_indexes.py  # plex-organizer-index CLI
│   ├── kill.py              # plex-organizer-kill CLI
│   └── setup.py             # plex-organizer-setup interactive menu
└── subs/
    ├── __init__.py
    ├── embedding.py     # external subtitle embedding + metadata
    ├── fetching.py      # online subtitle downloading (subliminal)
    └── syncing.py       # subtitle-to-audio timing sync (ffsubsync)
```

### Test Structure

Tests mirror the source package layout under `tests/`:

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
├── test_movie.py            # movie.py tests
├── test_paths.py            # _paths.py tests
├── test_qb.py               # qb.py tests
├── test_tv.py               # tv.py tests
├── test_utils.py            # utils.py tests
├── audio/
│   ├── __init__.py
│   ├── test_audio_tagging.py    # audio/tagging.py tests
│   └── test_audio_whisper.py    # audio/whisper.py tests
├── cli/
│   ├── __init__.py
│   ├── test_cli_generate_indexes.py  # cli/generate_indexes.py tests
│   ├── test_cli_kill.py             # cli/kill.py tests
│   └── test_cli_setup.py            # cli/setup.py tests
└── subs/
    ├── __init__.py
    ├── test_subs_embedding.py       # subs/embedding.py helper tests
    ├── test_subs_embedding_ops.py   # subs/embedding.py operation tests
    ├── test_subs_fetching.py        # subs/fetching.py tests
    └── test_subs_syncing.py         # subs/syncing.py tests
```

Shared fixtures (`tmp_media_tree`, `config_dir`, `default_config`, etc.) live in `tests/conftest.py` and are available to all subfolders.

## Pipeline Overview

`__main__.py` runs these steps in order for each directory:

1. **Subtitle embedding** — embed external subtitles into video containers.
2. **Subtitle fetching** — download and embed missing subtitles from online providers.
3. **Subtitle syncing** — synchronize embedded subtitle timing to the audio track.
4. **Audio language tagging** — detect and write missing audio language metadata.
5. **Cleanup** — delete unwanted files and folders (aggressive; see below).
6. **Rename & move** — place videos into the final TV/Movie layout + index them.
7. **Delete empty folders**.

Torrent removal (if a hash was provided) happens before the pipeline. If the start directory is not a recognised media folder, the organizer removes the torrent and exits immediately without modifying any files.

### Cleanup behavior

Cleanup is **intentionally aggressive**:

- Only files matching `EXT_FILTER` are kept (`.mkv`, `.mp4`, `.!qB`, `.plex_organizer.index`).
- Files with `sample` in the name are deleted.
- Folders in `UNWANTED_FOLDERS` are removed recursively (`Subs/`, `Subtitles/`, `Extras/`, `Sample/`, etc.).
- Plex-managed paths (`Plex Versions`) are always skipped via `utils.is_plex_folder()`.

## Testing

The test suite uses `pytest` + `pytest-cov`. The `PLEX_ORGANIZER_DIR` environment variable must point to a temporary directory so tests use an isolated config and don't touch the real one.

### Running tests

```bash
# Full suite
PLEX_ORGANIZER_DIR="$(mktemp -d)" python -m pytest

# With coverage report
PLEX_ORGANIZER_DIR="$(mktemp -d)" python -m pytest --cov=plex_organizer --cov-report=term-missing

# Single subpackage (e.g. subtitle tests)
PLEX_ORGANIZER_DIR="$(mktemp -d)" python -m pytest tests/subs/

# Single test file
PLEX_ORGANIZER_DIR="$(mktemp -d)" python -m pytest tests/test_tv.py
```

### Quick verification (integration)

```bash
bash ./test.sh
```

This script:

1. Copies `testData/` into `testEnv/`.
2. Creates/activates `venv/` and installs `pip install -e ".[dev]"`.
3. Runs `plex-organizer` against `testEnv/`.

### Manual run

```bash
sudo plex-organizer <start_dir> [torrent_hash]
# or
sudo python -m plex_organizer <start_dir> [torrent_hash]
```

### Test data

Place sample media structures under `testData/`. The directory is bind-mounted into the Dev Container. `testEnv/` is the disposable working copy and is `.gitignore`d.

## Tooling

| Tool           | Usage                        | Config                         |
| -------------- | ---------------------------- | ------------------------------ |
| **Black**      | Auto-formatter, runs on save | `.vscode/settings.json`        |
| **pylint**     | Linting (CI + local)         | `.github/workflows/pylint.yml` |
| **pytest**     | Unit / integration tests     | `pyproject.toml`               |
| **pytest-cov** | Coverage reporting           | `pyproject.toml`               |
| **SonarCloud** | Quality gate badge           | `sonar-project.properties`     |

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
# Lint the package
pylint plex_organizer/

# Lint with a minimum score threshold
pylint --fail-under=8.0 plex_organizer/
```

## Code Conventions

- **Moves & renames**: always use `utils.move_file()` so duplicate handling and `delete_duplicates` stay consistent.
- **Plex safety**: never modify paths where `utils.is_plex_folder()` returns `True`.
- **Filename parsing**: keep regex-driven and conservative (see `tv.py` and `movie.py` patterns).
- **Config keys**: don't add new keys to `config.ini` without updating the `default_config` dict in `config.py` — unknown options are removed on startup.
- **Error handling**: log errors rather than raising. Processing should continue for other files.
- **ffmpeg binaries**: always use `get_ffmpeg()` / `get_ffprobe()` from `ffmpeg_utils.py` — never shell out to bare `ffmpeg` / `ffprobe`.

## Configuration Notes

`config.ini` is auto-managed by `config.ensure_config_exists()`:

- Missing sections/options are added with defaults.
- Unknown options in known sections are removed.

When adding a new config option:

1. Add the key + default value to `default_config` in `config.py`.
2. Create a `get_<option>()` accessor function.
3. Document it in the `[Section]` block in `README.md`.

## Data Directory

By default, `config.ini`, log files, and the lock file are stored in `/root/.config/plex-organizer/`.

Resolution order (see `_paths.py`):

1. `PLEX_ORGANIZER_DIR` environment variable (if set).
2. Current working directory — if it already contains `config.ini`.
3. Parent of the `plex_organizer` package (editable install / repo clone).
4. `/root/.config/plex-organizer/` (default, created automatically).

## Contributing

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Commit your changes and push the branch.
4. Open a pull request.
