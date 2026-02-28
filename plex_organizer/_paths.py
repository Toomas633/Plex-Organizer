"""Centralized data-directory resolution for Plex Organizer.

The data directory is the folder that holds ``config.ini``, log files, and the
instance lock file.  It is resolved once per process and cached.

Resolution order:

1. ``PLEX_ORGANIZER_DIR`` environment variable (if set and non-empty).
2. Current working directory — if ``config.ini`` already exists there.
3. Parent of the ``plex_organizer`` package — covers editable installs and
   running directly from a repository clone.
4. ``/root/.config/plex-organizer/`` (default).  Created automatically when no
   higher-priority location matches.
"""

from __future__ import annotations

import os
from functools import lru_cache

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_PARENT = os.path.dirname(_PACKAGE_DIR)


@lru_cache(maxsize=1)
def data_dir() -> str:
    """Return the resolved data directory (cached after first call)."""

    env = os.environ.get("PLEX_ORGANIZER_DIR", "").strip()
    if env:
        path = os.path.abspath(env)
        os.makedirs(path, exist_ok=True)
        return path

    cwd = os.getcwd()
    if os.path.isfile(os.path.join(cwd, "config.ini")):
        return cwd

    if os.path.isfile(os.path.join(_PACKAGE_PARENT, "config.ini")):
        return _PACKAGE_PARENT

    default = "/root/.config/plex-organizer"
    os.makedirs(default, exist_ok=True)
    return default
