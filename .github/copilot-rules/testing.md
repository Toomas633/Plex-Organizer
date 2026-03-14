---
description: Rules for writing and running tests in Plex Organizer
globs: tests/**/*.py, plex_organizer/**/*.py
---

# Testing rules

- Framework: `pytest` + `pytest-cov`.
- Test files mirror the source layout under `tests/` (e.g. `plex_organizer/tv.py` → `tests/test_tv.py`, `plex_organizer/subs/embedding.py` → `tests/subs/test_subs_embedding.py`).
- Always set `PLEX_ORGANIZER_DIR` to a temporary directory when running tests so the real config is never touched:
  ```bash
  PLEX_ORGANIZER_DIR="$(mktemp -d)" python -m pytest
  ```
- Use the `config_dir` and `default_config` fixtures from `tests/conftest.py` to get an isolated config directory in tests. Mark test classes with `@mark.usefixtures("default_config")` when config is needed.
- New test files must include an `__init__.py` in the test subdirectory.
- When testing functions that call config getters, use `unittest.mock.patch` to override the return value rather than writing a real config file.
- Tests should be deterministic and not depend on network or filesystem state outside the tmp directories.
- After adding or modifying source code, always run the relevant tests to verify the change.
