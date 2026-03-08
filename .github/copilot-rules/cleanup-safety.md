---
description: Rules around the aggressive cleanup behavior and Plex safety
globs: plex_organizer/**/*.py
---

# Cleanup & safety rules

- Cleanup is **intentionally aggressive**: only files matching `EXT_FILTER` from `const.py` are kept (`.mkv`, `.mp4`, `.!qB`, `.plex_organizer.index`). Everything else is deleted.
- Files with `sample` in the name are always deleted.
- Folders matching `UNWANTED_FOLDERS` (e.g. `Subs/`, `Subtitles/`, `Extras/`, `Sample/`) are removed recursively.
- **Plex-managed content must never be modified.** Always check `utils.is_plex_folder()` before deleting, renaming, or moving anything. Paths containing `Plex Versions` as a path component must be skipped.
- **Unrecognised directories** (path does not contain `tv` or `movies` and is not a main folder): the organizer must exit without modifying any files. This prevents accidental cleanup of generic download folders. Detection: `utils.is_media_directory()`.
- Subtitle embedding runs **before** cleanup so external subtitle files are still present when embedding happens. The cleanup step then removes the now-redundant subtitle files/folders.
- Temporary files created by the organizer (detected by `utils.is_script_temp_file()`) must be skipped during processing and cleaned up after use.
