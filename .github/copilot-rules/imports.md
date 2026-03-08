---
description: Import style and ordering rules for Plex Organizer source and test code
globs: plex_organizer/**/*.py, tests/**/*.py
---

# Import rules

## Style

- **Import specific names**, not entire modules. Use `from os.path import join, exists` instead of `import os.path`. Use `from re import compile as re_compile` instead of `import re`.
- **Relative imports** within the `plex_organizer` package. Use `from .config import get_host` or `from ..log import log_error` — never `from plex_organizer.config import ...` in source modules.
- **Absolute imports** in test files. Use `from plex_organizer.config import get_host` — tests are outside the package and should not use relative imports.
- **Alias when shadowing builtins** or to avoid name collisions: `from os import walk as _walk`, `from re import compile as re_compile`, `from re import match as re_match`.

## Ordering (3 groups, separated by blank lines)

1. **Standard library** — `os`, `os.path`, `re`, `json`, `subprocess`, `tempfile`, `functools`, `configparser`, `shutil`, etc.
2. **Third-party** — `requests`, `chardet`, `faster_whisper`, `langdetect`, `subliminal`, `ffsubsync`, `static_ffmpeg`, etc.
3. **Local / project** — relative imports from `. ` / `.. ` within source; absolute `from plex_organizer.*` in tests.

Within each group, sort alphabetically by module name.

## Test imports

- Import the public API being tested at the top of the file:
  ```python
  from plex_organizer.cli.setup import main, _run_menu, MENU_OPTIONS
  ```
- Import test helpers (`pytest.mark`, `pytest.raises`, `unittest.mock.patch`) in the standard-library group.
- Use `from unittest.mock import patch` (not `from unittest import mock`) when you only need `patch`.
