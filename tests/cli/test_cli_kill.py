"""Tests for plex_organizer.cli.kill."""

from unittest.mock import patch
from pytest import mark

from plex_organizer.cli.kill import _find_pids, _process_cmdline, main


class TestFindPids:
    """Tests for _find_pids."""

    @patch("plex_organizer.cli.kill.os.getpid", return_value=100)
    @patch(
        "plex_organizer.cli.kill.subprocess.check_output",
        return_value="200\n300\n100\n",
    )
    def test_returns_pids_excluding_own(self, _mock_pgrep, _mock_getpid):
        """Own PID is excluded from the result list."""
        result = _find_pids()
        assert result == [200, 300]

    @patch("plex_organizer.cli.kill.os.getpid", return_value=1)
    @patch(
        "plex_organizer.cli.kill.subprocess.check_output",
        return_value="abc\n200\n\n",
    )
    def test_ignores_non_numeric_lines(self, _mock_pgrep, _mock_getpid):
        """Non-numeric lines in pgrep output are silently skipped."""
        result = _find_pids()
        assert result == [200]

    @patch("plex_organizer.cli.kill.os.getpid", return_value=1)
    @patch(
        "plex_organizer.cli.kill.subprocess.check_output",
        side_effect=FileNotFoundError,
    )
    def test_returns_empty_on_file_not_found(self, _mock_pgrep, _mock_getpid):
        """Returns empty list when pgrep is not installed."""
        assert not _find_pids()

    @patch("plex_organizer.cli.kill.os.getpid", return_value=1)
    @patch(
        "plex_organizer.cli.kill.subprocess.check_output",
        side_effect=__import__("subprocess").CalledProcessError(1, "pgrep"),
    )
    def test_returns_empty_on_called_process_error(self, _mock_pgrep, _mock_getpid):
        """Returns empty list when pgrep exits with a non-zero code."""
        assert not _find_pids()


class TestProcessCmdline:
    """Tests for _process_cmdline."""

    @patch(
        "plex_organizer.cli.kill.subprocess.check_output",
        return_value="python -m plex_organizer /media\n",
    )
    def test_returns_command_line(self, _mock_ps):
        """Returns the stripped command line string."""
        assert _process_cmdline(42) == "python -m plex_organizer /media"

    @patch(
        "plex_organizer.cli.kill.subprocess.check_output",
        side_effect=FileNotFoundError,
    )
    def test_returns_unknown_on_error(self, _mock_ps):
        """Returns 'unknown' when ps fails."""
        assert _process_cmdline(42) == "unknown"

    @patch(
        "plex_organizer.cli.kill.subprocess.check_output",
        side_effect=__import__("subprocess").CalledProcessError(1, "ps"),
    )
    def test_returns_unknown_on_called_process_error(self, _mock_ps):
        """Returns 'unknown' when ps exits non-zero."""
        assert _process_cmdline(42) == "unknown"


@mark.usefixtures("default_config")
class TestKillMain:
    """Tests for the main() entrypoint."""

    @patch("plex_organizer.cli.kill.sys.exit")
    @patch("plex_organizer.cli.kill.os.path.exists", return_value=False)
    @patch("plex_organizer.cli.kill._find_pids", return_value=[])
    def test_no_processes_no_lock(self, _pids, _exists, mock_exit, capsys):
        """Prints informational messages when nothing to do."""
        main()
        out = capsys.readouterr().out
        assert "No running plex-organizer processes found." in out
        assert "No lock file found" in out
        mock_exit.assert_called_once_with(0)

    @patch("plex_organizer.cli.kill.sys.exit")
    @patch("plex_organizer.cli.kill.os.remove")
    @patch("plex_organizer.cli.kill.os.path.exists", return_value=True)
    @patch("plex_organizer.cli.kill.os.kill")
    @patch("plex_organizer.cli.kill._process_cmdline", return_value="plex-organizer")
    @patch("plex_organizer.cli.kill._find_pids", return_value=[42, 99])
    def test_kills_processes_and_removes_lock(
        self, _pids, _cmd, mock_kill, _exists, mock_rm, _mock_exit, capsys
    ):
        """Kills found processes and removes the lock file."""
        main()
        assert mock_kill.call_count == 2
        mock_rm.assert_called_once()
        out = capsys.readouterr().out
        assert "Killed 2 process(es)." in out
        assert "Removed lock file" in out

    @patch("plex_organizer.cli.kill.sys.exit")
    @patch("plex_organizer.cli.kill.os.path.exists", return_value=False)
    @patch("plex_organizer.cli.kill.os.kill", side_effect=ProcessLookupError)
    @patch("plex_organizer.cli.kill._process_cmdline", return_value="cmd")
    @patch("plex_organizer.cli.kill._find_pids", return_value=[42])
    def test_process_lookup_error_silenced(
        self, _pids, _cmd, _kill, _exists, _mock_exit, capsys
    ):
        """ProcessLookupError (already dead) is silently ignored."""
        main()
        out = capsys.readouterr().out
        assert "No running plex-organizer processes found." in out

    @patch("plex_organizer.cli.kill.sys.exit")
    @patch("plex_organizer.cli.kill.os.path.exists", return_value=False)
    @patch("plex_organizer.cli.kill.os.kill", side_effect=PermissionError)
    @patch("plex_organizer.cli.kill._process_cmdline", return_value="cmd")
    @patch("plex_organizer.cli.kill._find_pids", return_value=[42])
    def test_permission_error_printed(
        self, _pids, _cmd, _kill, _exists, _mock_exit, capsys
    ):
        """PermissionError is reported to the user."""
        main()
        out = capsys.readouterr().out
        assert "Permission denied" in out

    @patch("plex_organizer.cli.kill.sys.exit")
    @patch("plex_organizer.cli.kill.os.remove", side_effect=OSError("device busy"))
    @patch("plex_organizer.cli.kill.os.path.exists", return_value=True)
    @patch("plex_organizer.cli.kill._find_pids", return_value=[])
    def test_lock_remove_oserror(self, _pids, _exists, _rm, _mock_exit, capsys):
        """OSError removing the lock file is reported."""
        main()
        out = capsys.readouterr().out
        assert "Failed to remove lock file" in out
        assert "device busy" in out
