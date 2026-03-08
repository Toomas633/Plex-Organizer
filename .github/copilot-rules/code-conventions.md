---
description: Code style and conventions for the Plex Organizer project
globs: plex_organizer/**/*.py
---

# Code conventions

- **Formatter**: Black. Do not fight Black's style choices — let it handle all formatting.
- **Linter**: pylint (CI). Address warnings where practical; use `# pylint: disable=` sparingly with a reason.
- **Moves & renames**: always use `utils.move_file()` so duplicate handling and the `delete_duplicates` setting stay consistent.
- **Plex safety**: never modify paths where `utils.is_plex_folder()` returns `True`. Check before any delete or rename.
- **Filename parsing**: keep regex-driven and conservative (see `tv.py` and `movie.py` patterns). Prefer not matching over a wrong match.
- **Error handling**: log errors via `log.log_error()` rather than raising exceptions. Processing should continue for other files.
- **ffmpeg binaries**: always use `get_ffmpeg()` / `get_ffprobe()` from `ffmpeg_utils.py` — never shell out to bare `ffmpeg` / `ffprobe`.
- **Imports**: use relative imports within the `plex_organizer` package (e.g. `from .config import ...`).
- **Type hints**: use standard library generics (`list`, `dict`, `tuple`) on Python 3.10+; avoid `typing.List` etc. in new code.
- **Docstrings**: use Google-style docstrings with `Args:` and `Returns:` sections.
