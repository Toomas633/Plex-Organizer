---
description: Rules for working with config.ini and adding new configuration options
globs: plex_organizer/config.py, plex_organizer/**/*.py
---

# Configuration rules

- `config.ini` is auto-managed by `config.ensure_config_exists()`. On startup, missing sections/options are added and unknown options in known sections are removed.
- **Never invent new config keys** without updating the `default_config` dict in `plex_organizer/config.py`. Any key not in `default_config` will be silently deleted on the next run.
- When adding a new config option:
  1. Add the key + default value to `default_config` in `config.py`.
  2. Create a `get_<option>()` accessor function in `config.py`.
  3. Document the option in the relevant `[Section]` block in `README.md`.
  4. Add tests for the accessor in `tests/test_config.py`.
- Config access should always go through the accessor functions (e.g. `get_delete_duplicates()`, `get_include_quality()`), never by reading the INI file directly in other modules.
- The data directory (containing `config.ini`, logs, lock file) defaults to `/root/.config/plex-organizer/` and can be overridden with the `PLEX_ORGANIZER_DIR` environment variable.
