---
description: Post-change validation checklist — run after every code change
globs: plex_organizer/**/*.py, tests/**/*.py
---

# Validation rules

After making any code change, always run these checks in order before considering the task complete:

1. **SonarQube analysis**: Run the SonarQube analysis tool on each changed file and resolve any flags (bugs, code smells, vulnerabilities, security hotspots).
2. **Pylint**: Run `pylint` on the changed files (or the relevant package) and fix any new errors or warnings.
   ```bash
   pylint plex_organizer/ tests/
   ```
3. **Tests**: Run the full test suite and ensure all tests pass.
   ```bash
   PLEX_ORGANIZER_DIR="$(mktemp -d)" python -m pytest
   ```

Do not skip any of these steps. If a check surfaces an issue introduced by the change, fix it before moving on.
