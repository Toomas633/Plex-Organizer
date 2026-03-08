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

from os import environ, makedirs, getcwd
from os.path import dirname, abspath, isfile, join
from functools import lru_cache

_PACKAGE_DIR = dirname(abspath(__file__))
_PACKAGE_PARENT = dirname(_PACKAGE_DIR)


@lru_cache(maxsize=1)
def data_dir() -> str:
    """Return the resolved data directory (cached after first call)."""

    env = environ.get("PLEX_ORGANIZER_DIR", "").strip()
    if env:
        path = abspath(env)
        makedirs(path, exist_ok=True)
        return path

    cwd = getcwd()
    if isfile(join(cwd, "config.ini")):
        return cwd

    if isfile(join(_PACKAGE_PARENT, "config.ini")):
        return _PACKAGE_PARENT

    default = "/root/.config/plex-organizer"
    makedirs(default, exist_ok=True)
    return default
