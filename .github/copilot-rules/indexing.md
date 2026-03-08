---
description: Rules for the per-library indexing system
globs: plex_organizer/indexing.py, plex_organizer/**/*.py
---

# Indexing rules

- Indexes are stored as JSON in `.plex_organizer.index` files and are best-effort (never crash on index errors).
- Index root rules (see `indexing.py`):
  - **Movies**: index file lives in the movies root directory.
  - **TV**: index file lives in the show root directory (`tv/<Show>/`).
- Only videos already in the organizer's **final layout** (renamed and moved) should be marked as indexed. This prevents skipping raw/unprocessed filenames.
- Use `indexing.should_index_video()` to check whether a file needs indexing and `indexing.mark_indexed()` to write an entry.
- Use `indexing.index_root_for_path()` to determine the correct index root for a given file path.
- The index file extension (`.plex_organizer.index`) is included in `EXT_FILTER` so it is never deleted by cleanup.
