"""Kill all running plex-organizer processes and release the lock file.

Installed as the ``plex-organizer-kill`` console script.
"""

from __future__ import annotations

from os import kill, remove, getpid
from os.path import join, exists
from signal import SIGKILL
from subprocess import check_output, CalledProcessError, DEVNULL
from sys import exit as sys_exit

from .._paths import data_dir

LOCK_FILENAME = ".plex_organizer.lock"


def _find_pids() -> list[int]:
    """Return PIDs of running plex-organizer processes (excluding ourselves)."""
    own_pid = getpid()
    try:
        output = check_output(
            ["pgrep", "-f", "plex.organizer"],
            text=True,
            stderr=DEVNULL,
        )
    except (CalledProcessError, FileNotFoundError):
        return []

    pids: list[int] = []
    for line in output.strip().splitlines():
        try:
            pid = int(line)
        except ValueError:
            continue
        if pid == own_pid:
            continue
        pids.append(pid)
    return pids


def _process_cmdline(pid: int) -> str:
    """Return the command line of *pid* for display purposes."""
    try:
        output = check_output(
            ["ps", "-p", str(pid), "-o", "args="],
            text=True,
            stderr=DEVNULL,
        )
        return output.strip()
    except (CalledProcessError, FileNotFoundError):
        return "unknown"


def run() -> None:
    """Kill running plex-organizer processes and remove the lock file."""
    killed = 0

    for pid in _find_pids():
        cmdline = _process_cmdline(pid)
        try:
            kill(pid, SIGKILL)
            print(f"Killed process {pid} ({cmdline})")
            killed += 1
        except ProcessLookupError:
            pass
        except PermissionError:
            print(f"Permission denied killing process {pid} ({cmdline})")

    lock_path = join(data_dir(), LOCK_FILENAME)
    if exists(lock_path):
        try:
            remove(lock_path)
            print(f"Removed lock file: {lock_path}")
        except OSError as exc:
            print(f"Failed to remove lock file: {exc}")
    else:
        print(f"No lock file found at {lock_path}")

    if killed == 0:
        print("No running plex-organizer processes found.")
    else:
        print(f"Killed {killed} process(es).")


def main() -> None:
    """Entry point for ``plex-organizer-kill``."""
    run()
    sys_exit(0)


if __name__ == "__main__":
    main()
