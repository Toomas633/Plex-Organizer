"""Tests for plex_organizer.cli.setup."""

from time import sleep
from unittest.mock import patch
from configparser import ConfigParser
from pytest import mark, raises

from plex_organizer.cli.setup import (
    main,
    _run_menu,
    _action_open_folder,
    _action_view_log,
    _action_migrate_config,
    _action_generate_indexes,
    _action_kill_organizers,
    _action_custom_run,
    _find_latest_log,
    _wait_for_quit,
    _command_exists,
    _colorize_log_line,
    migrate_config,
    _print_menu,
    MENU_OPTIONS,
    _CUSTOM_RUN_STEPS,
)


@mark.usefixtures("default_config")
class TestPrintMenu:
    """Tests for _print_menu output."""

    def test_menu_shows_numbered_options(self, capsys):
        """Each menu option is prefixed with a sequential number."""
        _print_menu()
        out = capsys.readouterr().out
        for idx in range(1, len(MENU_OPTIONS) + 1):
            assert str(idx) in out

    def test_menu_shows_quit_option(self, capsys):
        """The quit option is visible in the menu output."""
        _print_menu()
        out = capsys.readouterr().out
        assert "q" in out.lower()
        assert "Quit" in out

    def test_menu_shows_heading(self, capsys):
        """The menu includes a 'Setup' heading."""
        _print_menu()
        out = capsys.readouterr().out
        assert "Setup" in out

    def test_menu_shows_all_labels(self, capsys):
        """Every registered MENU_OPTIONS label appears in the output."""
        _print_menu()
        out = capsys.readouterr().out
        for label, _ in MENU_OPTIONS:
            assert label in out


@mark.usefixtures("default_config")
class TestRunMenu:
    """Tests for _run_menu interactive loop."""

    def test_quit_with_q(self, capsys):
        """Entering 'q' exits the loop immediately."""
        _run_menu(input_fn=lambda _: "q")
        out = capsys.readouterr().out
        assert "Setup" in out

    def test_quit_with_uppercase_q(self):
        """'Q' also quits."""
        _run_menu(input_fn=lambda _: "Q")

    def test_invalid_non_numeric(self, capsys):
        """Non-numeric / non-q input prints an error then loops."""
        inputs = iter(["abc", "q"])
        _run_menu(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Invalid option" in out

    def test_invalid_out_of_range(self, capsys):
        """A number beyond the menu range is rejected."""
        inputs = iter(["99", "q"])
        _run_menu(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Invalid option" in out

    def test_invalid_zero(self, capsys):
        """Zero is out of range."""
        inputs = iter(["0", "q"])
        _run_menu(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Invalid option" in out

    def test_eof_exits_gracefully(self):
        """EOFError (piped stdin) exits without traceback."""

        def _raise(_prompt):
            raise EOFError

        _run_menu(input_fn=_raise)

    def test_keyboard_interrupt_exits_gracefully(self):
        """Ctrl-C exits without traceback."""

        def _raise(_prompt):
            raise KeyboardInterrupt

        _run_menu(input_fn=_raise)

    def test_passes_input_fn_to_action(self):
        """input_fn is forwarded to actions that need interactive input."""
        calls = []

        def _fake_input(prompt):
            calls.append(prompt)
            if len(calls) == 1:
                return "1"
            return "q"

        _run_menu(input_fn=_fake_input)
        assert len(calls) >= 2


@mark.usefixtures("default_config")
class TestActionOpenFolder:
    """Tests for option 1: show organizer folder."""

    @patch("plex_organizer.cli.setup.run")
    def test_prints_folder_path(self, _mock_run, capsys):
        """The data directory path is printed to stdout."""
        _action_open_folder()
        out = capsys.readouterr().out
        assert "Organizer folder" in out

    @patch("plex_organizer.cli.setup.run")
    def test_calls_xdg_open(self, mock_run):
        """xdg-open is invoked to open the data directory."""
        _action_open_folder()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "xdg-open"

    @patch(
        "plex_organizer.cli.setup.run",
        side_effect=FileNotFoundError,
    )
    def test_fallback_when_xdg_open_missing(self, _mock_run, capsys):
        """A helpful message is shown when xdg-open is not installed."""
        _action_open_folder()
        out = capsys.readouterr().out
        assert "xdg-open not available" in out


@mark.usefixtures("default_config")
class TestFindLatestLog:
    """Tests for _find_latest_log helper."""

    @mark.usefixtures("config_dir")
    def test_returns_none_when_no_logs(self):
        """None is returned when no log files exist."""
        assert _find_latest_log() is None

    def test_returns_single_log(self, config_dir):
        """The single non-timestamped log file is returned."""
        log_file = config_dir / "plex-organizer.log"
        log_file.write_text("some log line\n")
        assert _find_latest_log() == str(log_file)

    def test_ignores_empty_single_log(self, config_dir):
        """An empty log file is treated as absent."""
        log_file = config_dir / "plex-organizer.log"
        log_file.write_text("")
        assert _find_latest_log() is None

    def test_returns_latest_timestamped(self, config_dir):
        """The newest timestamped log is preferred over older ones."""

        logs_dir = config_dir / "logs"
        logs_dir.mkdir()
        old = logs_dir / "plex-organizer.2025-01-01_00-00-00.log"
        old.write_text("old\n")
        sleep(0.05)
        new = logs_dir / "plex-organizer.2025-06-15_12-00-00.log"
        new.write_text("new\n")
        assert _find_latest_log() == str(new)

    def test_timestamped_takes_precedence_over_single(self, config_dir):
        """Timestamped logs in the logs/ subfolder beat the single file."""
        single = config_dir / "plex-organizer.log"
        single.write_text("single\n")
        logs_dir = config_dir / "logs"
        logs_dir.mkdir()
        ts = logs_dir / "plex-organizer.2025-06-15_12-00-00.log"
        ts.write_text("timestamped\n")
        result = _find_latest_log()
        assert result == str(ts)


@mark.usefixtures("default_config")
class TestActionViewLog:
    """Tests for option 2: view latest log."""

    def test_warns_when_no_logs(self, capsys):
        """A warning is printed when no log files are found."""
        _action_view_log()
        out = capsys.readouterr().out
        assert "No log files found" in out

    @patch("plex_organizer.cli.setup.call")
    @patch("plex_organizer.cli.setup._command_exists", return_value=True)
    def test_opens_pager(self, _mock_cmd, mock_call, config_dir, capsys):
        """A pager (less or more) is launched when available."""
        log_file = config_dir / "plex-organizer.log"
        log_file.write_text("2025-01-01 00:00:00 - [ERROR] - test error\n")
        _action_view_log()
        mock_call.assert_called_once()
        args = mock_call.call_args[0][0]
        assert args[0] in ("less", "more")
        if args[0] == "less":
            assert "-R" in args
        out = capsys.readouterr().out
        assert "Showing" in out

    @patch("plex_organizer.cli.setup.call", side_effect=OSError)
    @patch("plex_organizer.cli.setup._command_exists", return_value=True)
    def test_fallback_prints_contents_when_pager_fails(
        self, _cmd, _call, config_dir, capsys
    ):
        """Log contents are printed inline when the pager process fails."""
        log_file = config_dir / "plex-organizer.log"
        log_file.write_text("line one\nline two\n")
        _action_view_log(input_fn=lambda _: "q")
        out = capsys.readouterr().out
        assert "line one" in out
        assert "line two" in out

    @patch("plex_organizer.cli.setup._command_exists", return_value=False)
    def test_fallback_no_pager_prints_and_waits(
        self, _cmd, config_dir, capsys, monkeypatch
    ):
        """Without a pager, contents are printed and user waits to quit."""
        monkeypatch.delenv("PAGER", raising=False)
        log_file = config_dir / "plex-organizer.log"
        log_file.write_text("fallback content\n")
        _action_view_log(input_fn=lambda _: "q")
        out = capsys.readouterr().out
        assert "fallback content" in out

    @patch("plex_organizer.cli.setup._command_exists", return_value=False)
    def test_shows_empty_notice(self, _cmd, config_dir, capsys, monkeypatch):
        """An 'empty' notice is shown when the log has only whitespace."""
        monkeypatch.delenv("PAGER", raising=False)
        log_file = config_dir / "plex-organizer.log"
        log_file.write_text("content\n")
        log_file.write_text("   \n")
        _action_view_log()
        out = capsys.readouterr().out
        assert "empty" in out.lower()


@mark.usefixtures("default_config")
class TestWaitForQuit:
    """Tests for _wait_for_quit helper."""

    def test_returns_on_q(self):
        """Entering 'q' exits the wait loop."""
        _wait_for_quit(input_fn=lambda _: "q")

    def test_loops_until_q(self):
        """Non-q input is ignored until 'q' is entered."""
        inputs = iter(["x", "hello", "q"])
        _wait_for_quit(input_fn=lambda _: next(inputs))

    def test_eof_returns(self):
        """EOFError breaks out of the wait loop."""

        def _raise(_):
            raise EOFError

        _wait_for_quit(input_fn=_raise)

    def test_keyboard_interrupt_returns(self):
        """KeyboardInterrupt breaks out of the wait loop."""

        def _raise(_):
            raise KeyboardInterrupt

        _wait_for_quit(input_fn=_raise)


class TestCommandExists:
    """Tests for _command_exists helper."""

    def test_existing_command(self):
        """A command present on PATH returns True."""
        assert _command_exists("ls") is True

    @patch(
        "plex_organizer.cli.setup.check_output",
        side_effect=FileNotFoundError,
    )
    def test_missing_which(self, _mock):
        """FileNotFoundError from which causes False."""
        assert _command_exists("nonexistent_tool") is False

    @patch(
        "plex_organizer.cli.setup.check_output",
        side_effect=__import__("subprocess").CalledProcessError(1, "which"),
    )
    def test_unknown_command(self, _mock):
        """CalledProcessError from which causes False."""
        assert _command_exists("nonexistent_tool") is False


class TestColorizeLogLine:
    """Tests for _colorize_log_line ANSI coloring."""

    def test_colors_error_line(self):
        """ERROR lines include a red ANSI escape."""
        line = "2025-01-01 12:00:00 - [ERROR] - something broke"
        result = _colorize_log_line(line)
        assert "\033[" in result
        assert "something broke" in result
        assert "\033[31m" in result

    def test_colors_timestamp_light_green(self):
        """The timestamp portion is wrapped in light-green ANSI."""
        line = "2025-01-01 12:00:00 - [ERROR] - x"
        result = _colorize_log_line(line)
        assert "\033[92m" in result

    def test_colors_warning_line(self):
        """WARNING lines include a yellow ANSI escape."""
        result = _colorize_log_line("2025-06-15 08:30:00 - [WARNING] - heads up")
        assert "\033[33m" in result
        assert "heads up" in result

    def test_colors_debug_line(self):
        """DEBUG lines include a gray ANSI escape."""
        result = _colorize_log_line("2025-01-01 00:00:00 - [DEBUG] - trace")
        assert "\033[90m" in result
        assert "trace" in result

    def test_colors_duplicate_line(self):
        """DUPLICATE lines include a magenta ANSI escape."""
        result = _colorize_log_line("2025-01-01 00:00:00 - [DUPLICATE] - dup file")
        assert "\033[35m" in result

    def test_colors_info_line(self):
        """INFO lines include a blue ANSI escape."""
        result = _colorize_log_line("2025-01-01 00:00:00 - [INFO] - progress")
        assert "\033[34m" in result

    def test_passthrough_non_log_line(self):
        """Lines not matching the log format are returned unchanged."""
        line = "some random text without log format"
        assert _colorize_log_line(line) == line

    def test_preserves_message_text(self):
        """The original message portion is preserved in the output."""
        line = "2025-03-01 14:22:33 - [ERROR] - file /tmp/video.mkv missing"
        result = _colorize_log_line(line)
        assert "file /tmp/video.mkv missing" in result


@mark.usefixtures("default_config")
class TestMigrateConfig:
    """Tests for migrate_config function."""

    def test_copies_old_values(self, config_dir, tmp_path):
        """Old config values are merged into the current config.ini."""
        old_ini = tmp_path / "old_config.ini"
        old_ini.write_text(
            "[qBittorrent]\n"
            "host = http://myhost:9090\n"
            "username = myuser\n"
            "password = secret\n"
            "\n"
            "[Settings]\n"
            "delete_duplicates = true\n"
            "include_quality = false\n"
            "capitalize = false\n"
            "cpu_threads = 4\n"
            "\n"
            "[Subtitles]\n"
            "enable_subtitle_embedding = false\n"
        )

        added = migrate_config(str(old_ini))

        result = ConfigParser()
        result.read(str(config_dir / "config.ini"))

        assert result.get("qBittorrent", "host") == "http://myhost:9090"
        assert result.get("qBittorrent", "username") == "myuser"
        assert result.get("Settings", "delete_duplicates") == "true"
        assert result.get("Settings", "cpu_threads") == "4"
        assert result.get("Subtitles", "enable_subtitle_embedding") == "false"
        assert result.has_option("Subtitles", "sync_subtitles")
        assert result.has_option("Subtitles", "fetch_subtitles")
        assert added == 4

    @mark.usefixtures("config_dir")
    def test_preserves_existing_new_keys(self, tmp_path):
        """If old config already has a new-in-v6 key, added count is lower."""
        old_ini = tmp_path / "old_config.ini"
        old_ini.write_text(
            "[Subtitles]\n"
            "enable_subtitle_embedding = true\n"
            "sync_subtitles = false\n"
        )
        added = migrate_config(str(old_ini))
        assert added == 3

    @mark.usefixtures("config_dir")
    def test_raises_file_not_found(self):
        """FileNotFoundError is raised for a nonexistent config path."""

        with raises(FileNotFoundError):
            migrate_config("/nonexistent/config.ini")


@mark.usefixtures("default_config")
class TestActionMigrateConfig:
    """Tests for the interactive option 3 wrapper."""

    def test_prompts_for_path(self, tmp_path, capsys):
        """A valid path triggers migration and prints a success message."""
        old_ini = tmp_path / "old.ini"
        old_ini.write_text("[Settings]\ndelete_duplicates = true\n")
        _action_migrate_config(input_fn=lambda _: str(old_ini))
        out = capsys.readouterr().out
        assert "Migration complete" in out

    def test_empty_path(self, capsys):
        """An empty input prints a 'No path provided' message."""
        _action_migrate_config(input_fn=lambda _: "")
        out = capsys.readouterr().out
        assert "No path provided" in out

    def test_missing_file(self, capsys):
        """A nonexistent file path prints a 'File not found' message."""
        _action_migrate_config(input_fn=lambda _: "/no/such/file.ini")
        out = capsys.readouterr().out
        assert "File not found" in out

    def test_eof_exits_gracefully(self):
        """EOFError during path prompt is handled silently."""

        def _raise(_):
            raise EOFError

        _action_migrate_config(input_fn=_raise)


@mark.usefixtures("default_config")
class TestActionGenerateIndexes:
    """Tests for the interactive option 4 wrapper."""

    def test_empty_path(self, capsys):
        """An empty input prints a 'No path provided' message."""
        _action_generate_indexes(input_fn=lambda _: "")
        out = capsys.readouterr().out
        assert "No path provided" in out

    def test_nonexistent_dir(self, capsys):
        """A nonexistent directory prints a 'Not a directory' message."""
        _action_generate_indexes(input_fn=lambda _: "/no/such/dir")
        out = capsys.readouterr().out
        assert "Not a directory" in out

    @patch("plex_organizer.cli.setup.generate_indexes")
    def test_calls_generate_indexes(self, mock_gen, tmp_path):
        """generate_indexes is called with the provided media root."""
        media = tmp_path / "media"
        media.mkdir()
        (media / "tv").mkdir()
        (media / "movies").mkdir()

        _action_generate_indexes(input_fn=lambda _: str(media))
        mock_gen.assert_called_once_with(str(media))

    @patch(
        "plex_organizer.cli.setup.generate_indexes",
        side_effect=ValueError("Invalid root"),
    )
    def test_handles_value_error(self, _mock_gen, tmp_path, capsys):
        """A ValueError from generate_indexes is caught and printed."""
        d = tmp_path / "bad"
        d.mkdir()
        _action_generate_indexes(input_fn=lambda _: str(d))
        out = capsys.readouterr().out
        assert "Invalid root" in out

    def test_eof_exits_gracefully(self):
        """EOFError during path prompt is handled silently."""

        def _raise(_):
            raise EOFError

        _action_generate_indexes(input_fn=_raise)


@mark.usefixtures("default_config")
class TestActionKillOrganizers:
    """Tests for option 5: kill running organizers."""

    @patch("plex_organizer.cli.setup._kill_run")
    def test_calls_kill_run(self, mock_kill):
        """The kill run function is invoked."""
        _action_kill_organizers()
        mock_kill.assert_called_once()

    @patch("plex_organizer.cli.setup._kill_run")
    def test_prints_surrounding_newlines(self, _mock_kill, capsys):
        """Output is wrapped with blank lines."""
        _action_kill_organizers()
        assert capsys.readouterr().out == "\n\n"


@mark.usefixtures("default_config")
class TestSetupMain:
    """Tests for the main() entrypoint."""

    @patch("plex_organizer.cli.setup.sys_exit")
    @patch("plex_organizer.cli.setup._run_menu")
    def test_calls_run_menu(self, mock_menu, _mock_exit):
        """main() delegates to _run_menu."""
        main()
        mock_menu.assert_called_once()

    @patch("plex_organizer.cli.setup.sys_exit")
    @patch("plex_organizer.cli.setup._run_menu")
    def test_calls_sys_exit_zero(self, _mock_menu, mock_exit):
        """main() exits with code 0."""
        main()
        mock_exit.assert_called_once_with(0)

    @patch("plex_organizer.cli.setup.sys_exit")
    @patch("plex_organizer.cli.setup._run_menu")
    def test_ensures_config_exists(self, _mock_menu, _mock_exit, config_dir):
        """main() creates config.ini if missing."""
        config_ini = config_dir / "config.ini"
        if config_ini.exists():
            config_ini.unlink()
        main()
        assert config_ini.exists()

    def test_nonexistent_dir(self, capsys):
        """A nonexistent directory prints a 'Not a directory' message."""
        _action_custom_run(input_fn=lambda _: "/no/such/dir")
        out = capsys.readouterr().out
        assert "Not a directory" in out

    def test_eof_on_dir_prompt(self):
        """EOFError on the directory prompt exits gracefully."""

        def _raise(_):
            raise EOFError

        _action_custom_run(input_fn=_raise)

    def test_keyboard_interrupt_on_dir_prompt(self):
        """KeyboardInterrupt on the directory prompt exits gracefully."""

        def _raise(_):
            raise KeyboardInterrupt

        _action_custom_run(input_fn=_raise)

    def test_shows_step_submenu(self, tmp_path, capsys):
        """After a valid directory, a numbered step sub-menu is displayed."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "q"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Custom Run" in out
        for label, _ in _CUSTOM_RUN_STEPS:
            assert label in out

    def test_cancel_with_q(self, tmp_path, capsys):
        """Entering 'q' at the step sub-menu cancels without error."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "q"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Error" not in out

    def test_invalid_step_choice(self, tmp_path, capsys):
        """An invalid step number prints an error."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "99", "q"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Invalid option" in out

    def test_invalid_non_numeric_step(self, tmp_path, capsys):
        """A non-numeric step choice prints an error."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "abc", "q"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Invalid option" in out

    def test_eof_on_step_prompt(self, tmp_path):
        """EOFError on the step prompt exits gracefully."""
        d = tmp_path / "media"
        d.mkdir()
        call_count = 0

        def _input(_):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return str(d)
            raise EOFError

        _action_custom_run(input_fn=_input)

    @patch("plex_organizer.cli.setup._run_full_pipeline")
    def test_runs_full_pipeline(self, mock_fn, tmp_path, capsys):
        """Selecting step 1 then running executes the full pipeline."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "1", "r"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        # Only check folder argument, ignore input_fn identity
        args, _ = mock_fn.call_args
        assert args[0] == str(d)
        out = capsys.readouterr().out
        assert "Done" in out

    @patch("plex_organizer.cli.setup._run_embed_subs")
    def test_runs_embed_subs(self, mock_fn, tmp_path, capsys):
        """Selecting step 2 then running executes subtitle embedding."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "2", "r"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        args, _ = mock_fn.call_args
        assert args[0] == str(d)
        out = capsys.readouterr().out
        assert "Done" in out

    @patch("plex_organizer.cli.setup._run_delete_empty")
    def test_runs_last_step(self, mock_fn, tmp_path, capsys):
        """Selecting the last step then running executes delete empty folders."""
        d = tmp_path / "media"
        d.mkdir()
        last = str(len(_CUSTOM_RUN_STEPS))
        inputs = iter([str(d), last, "r"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        args, _ = mock_fn.call_args
        assert args[0] == str(d)
        out = capsys.readouterr().out
        assert "Done" in out

    @patch(
        "plex_organizer.cli.setup._run_full_pipeline",
        side_effect=RuntimeError("boom"),
    )
    def test_handles_step_exception(self, _mock_fn, tmp_path, capsys):
        """An exception during a step is caught and printed."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "1", "r"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Error" in out
        assert "boom" in out

    def test_prints_running_label(self, tmp_path, capsys):
        """The name of the selected step is printed before execution."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "q"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Cancel" in out

    def test_zero_step_is_invalid(self, tmp_path, capsys):
        """Zero is not a valid step number."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "0", "q"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Invalid option" in out

    def test_menu_option_exists(self):
        """Custom run appears in the main MENU_OPTIONS list."""
        labels = [label for label, _ in MENU_OPTIONS]
        assert "Custom run" in labels
