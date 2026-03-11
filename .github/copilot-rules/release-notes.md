---
description: Rules for generating release notes
globs: release/**/*.md
---

# Release notes rules

## When to create release notes

When asked to create or generate release notes, create a new file in `release/`.

## Version numbering

- Determine the next version by inspecting existing files in `release/` (e.g. `v6.0.md` → next major is `v7.0.md`, next minor is `v6.1.md`).
- If the user asks for a **minor** release, bump the minor component (e.g. `v6.0` → `v6.1`).
- Otherwise, bump the **major** component and reset minor to `0` (e.g. `v6.0` → `v7.0`).
- The filename is always `release/v<MAJOR>.<MINOR>.md`.

## Gathering changes

Follow these steps in order (this is how `v6.0.md` was created):

1. **Read previous release notes** in `release/` to match the existing tone and style.
2. **List tags** with `git --no-pager tag` to identify the last release.
3. **Get commits since the last tag**: `git --no-pager log <last_tag>..HEAD --oneline`.
4. **Check `pyproject.toml`** for the current version string.
5. **Cross-reference** with the source tree, README, config, and FAQ to ensure nothing is missed and descriptions are accurate.
6. **Group changes** by kind (see **Format** below) and create the file.

## Format

- The file starts with a single `##` heading: a short summary sentence of the release.
- For **minor releases** or releases with few changes, a flat bullet list under the heading is sufficient (like `v1.0.md` / `v1.1.md`):

  ```md
  ## Short summary of the release

  - **Feature/fix name**: Brief description.
  - **Another item**: Brief description.
  ```

- For **major releases** or releases with many changes, use `###` sub-sections to group items (like `v6.0.md`):

  ```md
  ## Short summary of the release

  ### Breaking changes

  - **Item**: Description.

  ### New features

  - **Item**: Description.

  ### Improvements

  - **Item**: Description.

  ### Bug fixes

  - **Item**: Description.
  ```

- Only include sub-sections that have content (e.g. skip "Bug fixes" if there are none).

## Style

- Each bullet starts with a **bold label** followed by a colon and a description.
- Descriptions are concise — one or two sentences max.
- Reference config keys in backticks (e.g. `[Subtitles] fetch_subtitles`).
- Link to other docs (e.g. FAQ) with relative paths where helpful.
- No emoji. No trailing whitespace.
