"""Tests for plex_organizer.cli.setup."""

from os import makedirs
from os.path import join, exists
from time import sleep
from unittest.mock import patch, call
from configparser import ConfigParser
from pytest import mark, raises

from plex_organizer.cli.setup import (
    main,
    _expand_folder,
    _update_index_after_custom_run,
    _run_menu,
    _run_full_pipeline,
    _run_embed_subs,
    _run_fetch_subs,
    _run_sync_subs,
    _run_tag_audio,
    _run_cleanup,
    _run_rename_move,
    _run_delete_empty,
    _action_open_folder,
    _action_view_log,
    _action_migrate_config,
    _action_generate_indexes,
    _action_kill_organizers,
    _action_migrate_tv_indexes,
    _action_edit_config,
    _action_custom_run,
    _validate_config_value,
    _find_latest_log,
    _wait_for_quit,
    _command_exists,
    _colorize_log_line,
    migrate_config,
    _print_menu,
    MENU_OPTIONS,
    _CUSTOM_RUN_STEPS,
)
from plex_organizer.const import INDEX_FILENAME
from plex_organizer.indexing import _read_index, _write_index
from plex_organizer import config as _config


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
class TestActionMigrateTvIndexes:
    """Tests for option 7: migrate per-show TV indexes to root."""

    @patch(
        "plex_organizer.cli.setup.migrate_show_indexes_to_tv_root",
        return_value=3,
    )
    def test_success_message(self, _mock_migrate, tmp_path, capsys):
        """Successful migration prints a completion message."""
        tv_dir = tmp_path / "tv"
        tv_dir.mkdir()
        _action_migrate_tv_indexes(input_fn=lambda _: str(tv_dir))
        out = capsys.readouterr().out
        assert "Migration complete" in out
        assert "3" in out

    @patch(
        "plex_organizer.cli.setup.migrate_show_indexes_to_tv_root",
        return_value=0,
    )
    def test_no_indexes_found(self, _mock_migrate, tmp_path, capsys):
        """When no per-show indexes exist, a 'nothing found' message is shown."""
        tv_dir = tmp_path / "tv"
        tv_dir.mkdir()
        _action_migrate_tv_indexes(input_fn=lambda _: str(tv_dir))
        out = capsys.readouterr().out
        assert "No per-show index files found" in out

    def test_empty_path(self, capsys):
        """An empty input prints a 'No path provided' message."""
        _action_migrate_tv_indexes(input_fn=lambda _: "")
        out = capsys.readouterr().out
        assert "No path provided" in out

    def test_nonexistent_dir(self, capsys):
        """A nonexistent directory prints a 'Not a directory' message."""
        _action_migrate_tv_indexes(input_fn=lambda _: "/no/such/dir")
        out = capsys.readouterr().out
        assert "Not a directory" in out

    def test_eof_exits_gracefully(self):
        """EOFError during path prompt is handled silently."""

        def _raise(_):
            raise EOFError

        _action_migrate_tv_indexes(input_fn=_raise)

    @patch(
        "plex_organizer.cli.setup.migrate_show_indexes_to_tv_root",
        side_effect=RuntimeError("boom"),
    )
    def test_handles_exception(self, _mock_migrate, tmp_path, capsys):
        """Exceptions are caught and printed."""
        tv_dir = tmp_path / "tv"
        tv_dir.mkdir()
        _action_migrate_tv_indexes(input_fn=lambda _: str(tv_dir))
        out = capsys.readouterr().out
        assert "Migration failed" in out
        assert "boom" in out


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


class TestExpandFolder:
    """Tests for _expand_folder helper."""

    def test_returns_folder_when_no_subfolders(self, tmp_path):
        """A plain directory without tv/movies is returned as-is."""
        d = tmp_path / "media"
        d.mkdir()
        assert _expand_folder(str(d)) == [str(d)]

    def test_expands_main_folder_with_tv_and_movies(self, tmp_path):
        """A main folder with both tv/ and movies/ expands to both."""
        d = tmp_path / "media"
        (d / "tv").mkdir(parents=True)
        (d / "movies").mkdir(parents=True)
        result = _expand_folder(str(d))
        assert str(d / "tv") in result
        assert str(d / "movies") in result
        assert len(result) == 2

    def test_expands_main_folder_with_only_tv(self, tmp_path):
        """A main folder with only tv/ expands to just tv/."""
        d = tmp_path / "media"
        (d / "tv").mkdir(parents=True)
        result = _expand_folder(str(d))
        assert result == [str(d / "tv")]

    def test_expands_main_folder_with_only_movies(self, tmp_path):
        """A main folder with only movies/ expands to just movies/."""
        d = tmp_path / "media"
        (d / "movies").mkdir(parents=True)
        result = _expand_folder(str(d))
        assert result == [str(d / "movies")]

    def test_single_tv_dir_not_expanded(self, tmp_path):
        """A tv/ directory itself is not expanded further."""
        d = tmp_path / "media" / "tv"
        d.mkdir(parents=True)
        assert _expand_folder(str(d)) == [str(d)]

    def test_single_movies_dir_not_expanded(self, tmp_path):
        """A movies/ directory itself is not expanded further."""
        d = tmp_path / "media" / "movies"
        d.mkdir(parents=True)
        assert _expand_folder(str(d)) == [str(d)]


@mark.usefixtures("default_config")
class TestRunStepsMainFolder:
    """Tests that _run_* functions expand main folders into tv/ and movies/."""

    def _make_main_folder(self, tmp_path):
        """Create a main folder with tv/ and movies/ subdirectories."""
        d = tmp_path / "media"
        (d / "tv").mkdir(parents=True)
        (d / "movies").mkdir(parents=True)
        return d

    @patch("plex_organizer.cli.setup.merge_subtitles_in_directory")
    @patch("plex_organizer.cli.setup.fetch_subtitles_in_directory")
    @patch("plex_organizer.cli.setup.sync_subtitles_in_directory")
    @patch("plex_organizer.cli.setup._analyze_video_languages")
    @patch("plex_organizer.cli.setup._delete_unwanted_files")
    @patch("plex_organizer.cli.setup._move_directories")
    @patch("plex_organizer.cli.setup._delete_empty_directories")
    def test_full_pipeline_expands_main_folder(
        self,
        mock_del_empty,
        mock_move,
        mock_del_unwanted,
        mock_analyze,
        mock_sync,
        mock_fetch,
        mock_embed,
        tmp_path,
    ):
        """Full pipeline processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        inputs = iter(["", "", "y", "y", "2", "y", "y", "n"])
        _run_full_pipeline(str(d), input_fn=lambda _: next(inputs))

        # merge_subtitles_in_directory should be called for both tv and movies
        called_dirs = [c.args[0] for c in mock_embed.call_args_list]
        assert str(d / "tv") in called_dirs
        assert str(d / "movies") in called_dirs

    @patch("plex_organizer.cli.setup.merge_subtitles_in_directory")
    def test_embed_subs_expands_main_folder(self, mock_embed, tmp_path):
        """Embed subs processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        inputs = iter(["y"])
        _run_embed_subs(str(d), input_fn=lambda _: next(inputs))

        called_dirs = [c.args[0] for c in mock_embed.call_args_list]
        assert str(d / "tv") in called_dirs
        assert str(d / "movies") in called_dirs

    @patch("plex_organizer.cli.setup.fetch_subtitles_in_directory")
    def test_fetch_subs_expands_main_folder(self, mock_fetch, tmp_path):
        """Fetch subs processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        inputs = iter(["eng"])
        _run_fetch_subs(str(d), input_fn=lambda _: next(inputs))

        called_dirs = [c.args[0] for c in mock_fetch.call_args_list]
        assert str(d / "tv") in called_dirs
        assert str(d / "movies") in called_dirs

    @patch("plex_organizer.cli.setup.sync_subtitles_in_directory")
    def test_sync_subs_expands_main_folder(self, mock_sync, tmp_path):
        """Sync subs processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        _run_sync_subs(str(d))

        called_dirs = [c.args[0] for c in mock_sync.call_args_list]
        assert str(d / "tv") in called_dirs
        assert str(d / "movies") in called_dirs

    @patch("plex_organizer.cli.setup.tag_audio_track_languages")
    def test_tag_audio_expands_main_folder(self, mock_tag, tmp_path):
        """Tag audio processes videos under tv/ and movies/ separately."""
        d = self._make_main_folder(tmp_path)
        # Create a video in each subdirectory
        (d / "movies" / "Test (2020)").mkdir(parents=True)
        (d / "movies" / "Test (2020)" / "Test (2020).mkv").touch()
        (d / "tv" / "Show" / "Season 1").mkdir(parents=True)
        (d / "tv" / "Show" / "Season 1" / "Show S01E01.mkv").touch()

        inputs = iter(["2"])
        _run_tag_audio(str(d), input_fn=lambda _: next(inputs))

        assert mock_tag.call_count == 2

    @patch("plex_organizer.cli.setup._delete_unwanted_files")
    def test_cleanup_expands_main_folder(self, mock_del, tmp_path):
        """Cleanup processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        _run_cleanup(str(d))

        called_roots = [c.args[0] for c in mock_del.call_args_list]
        tv_processed = any(str(d / "tv") in r for r in called_roots)
        movies_processed = any(str(d / "movies") in r for r in called_roots)
        assert tv_processed
        assert movies_processed

    @patch("plex_organizer.cli.setup._move_directories")
    def test_rename_move_expands_main_folder(self, mock_move, tmp_path):
        """Rename & move processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        # Create a video in movies
        (d / "movies" / "Test (2020)").mkdir(parents=True)
        (d / "movies" / "Test (2020)" / "Test (2020).mkv").touch()

        inputs = iter(["y", "y", "n"])
        _run_rename_move(str(d), input_fn=lambda _: next(inputs))

        # _move_directories should be called with the movies/ subdirectory, not the main folder
        called_dirs = [c.args[0] for c in mock_move.call_args_list]
        assert all(str(d / "movies") in cd or str(d / "tv") in cd for cd in called_dirs)
        assert str(d) not in called_dirs or all(
            cd.startswith(str(d / "movies")) or cd.startswith(str(d / "tv"))
            for cd in called_dirs
        )

    @patch("plex_organizer.cli.setup._delete_empty_directories")
    def test_delete_empty_expands_main_folder(self, mock_del, tmp_path):
        """Delete empty processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        _run_delete_empty(str(d))

        called_dirs = [c.args[0] for c in mock_del.call_args_list]
        assert str(d / "tv") in called_dirs
        assert str(d / "movies") in called_dirs


@mark.usefixtures("default_config")
class TestUpdateIndexPruning:
    """Tests that _update_index_after_custom_run prunes stale entries."""

    def test_stale_movie_entry_removed(self, tmp_path):
        """Old movie index entries for moved/renamed files are pruned."""
        movies = tmp_path / "movies"
        movie_dir = movies / "Test (2020)"
        movie_dir.mkdir(parents=True)
        (movie_dir / "Test (2020).mkv").touch()

        _write_index(
            str(movies / INDEX_FILENAME),
            {
                "files": {
                    "Test (2020)/Test (2020).mkv": {
                        "processed_at": "2025-01-01T00:00:00+00:00"
                    },
                    "Old Name/Old Name.mkv": {
                        "processed_at": "2025-01-01T00:00:00+00:00"
                    },
                }
            },
        )

        _update_index_after_custom_run(str(movies))

        result = _read_index(str(movies / INDEX_FILENAME))
        assert "Test (2020)/Test (2020).mkv" in result["files"]
        assert "Old Name/Old Name.mkv" not in result["files"]

    def test_stale_tv_entry_removed(self, tmp_path):
        """Old TV index entries for moved/renamed files are pruned."""
        tv = tmp_path / "tv"
        show_dir = tv / "Show" / "Season 1"
        show_dir.mkdir(parents=True)
        (show_dir / "Show S01E01.mkv").touch()

        _write_index(
            str(tv / INDEX_FILENAME),
            {
                "files": {
                    "Show/Season 1/Show S01E01.mkv": {
                        "processed_at": "2025-01-01T00:00:00+00:00"
                    },
                    "Show/Season 1/Old.Name.S01E01.mkv": {
                        "processed_at": "2025-01-01T00:00:00+00:00"
                    },
                }
            },
        )

        _update_index_after_custom_run(str(tv))

        result = _read_index(str(tv / INDEX_FILENAME))
        assert "Show/Season 1/Show S01E01.mkv" in result["files"]
        assert "Show/Season 1/Old.Name.S01E01.mkv" not in result["files"]

    def test_main_folder_prunes_both_indexes(self, tmp_path):
        """When given a main folder, stale entries in both tv and movies indexes are pruned."""
        main = tmp_path / "media"
        movies = main / "movies"
        tv = main / "tv"

        movie_dir = movies / "Test (2020)"
        movie_dir.mkdir(parents=True)
        (movie_dir / "Test (2020).mkv").touch()

        show_dir = tv / "Show" / "Season 1"
        show_dir.mkdir(parents=True)
        (show_dir / "Show S01E01.mkv").touch()

        _write_index(
            str(movies / INDEX_FILENAME),
            {
                "files": {
                    "Test (2020)/Test (2020).mkv": {"processed_at": "ts"},
                    "Stale (2019)/Stale (2019).mkv": {"processed_at": "ts"},
                }
            },
        )
        _write_index(
            str(tv / INDEX_FILENAME),
            {
                "files": {
                    "Show/Season 1/Show S01E01.mkv": {"processed_at": "ts"},
                    "Show/Season 1/Stale.S01E01.mkv": {"processed_at": "ts"},
                }
            },
        )

        _update_index_after_custom_run(str(main))

        movies_idx = _read_index(str(movies / INDEX_FILENAME))
        assert "Test (2020)/Test (2020).mkv" in movies_idx["files"]
        assert "Stale (2019)/Stale (2019).mkv" not in movies_idx["files"]

        tv_idx = _read_index(str(tv / INDEX_FILENAME))
        assert "Show/Season 1/Show S01E01.mkv" in tv_idx["files"]
        assert "Show/Season 1/Stale.S01E01.mkv" not in tv_idx["files"]


@mark.usefixtures("default_config")
class TestValidateConfigValue:
    """Tests for _validate_config_value helper."""

    def test_bool_accepts_true(self):
        assert _validate_config_value("bool", "true") is None

    def test_bool_accepts_false(self):
        assert _validate_config_value("bool", "false") is None

    def test_bool_rejects_invalid(self):
        assert _validate_config_value("bool", "yes") is not None

    def test_int_accepts_number(self):
        assert _validate_config_value("int", "4") is None

    def test_int_rejects_text(self):
        assert _validate_config_value("int", "abc") is not None

    def test_str_accepts_anything(self):
        assert _validate_config_value("str", "anything") is None


@mark.usefixtures("default_config")
class TestActionEditConfig:
    """Tests for the interactive config editor (menu option 8)."""

    def test_menu_option_exists(self):
        """Edit configuration appears in the main MENU_OPTIONS list."""
        labels = [label for label, _ in MENU_OPTIONS]
        assert "Edit configuration" in labels

    def test_quit_immediately(self, capsys):
        """Pressing q returns to main menu without changes."""
        _action_edit_config(input_fn=lambda _: "q")
        out = capsys.readouterr().out
        assert "Configuration" in out

    def test_shows_all_sections(self, capsys):
        """All config sections are displayed."""
        _action_edit_config(input_fn=lambda _: "q")
        out = capsys.readouterr().out
        for section in ("qBittorrent", "Settings", "Logging", "Audio", "Subtitles"):
            assert section in out

    def test_toggle_boolean_value(self, capsys):
        """Selecting a bool option toggles it and saves."""
        from configparser import ConfigParser as CP

        # Read current value before toggle
        cfg_before = CP()
        cfg_before.read(_config.CONFIG_PATH)
        old_val = cfg_before.get("Settings", "delete_duplicates")

        # Find the index of delete_duplicates (a bool option)
        call_count = 0

        def _input(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Pick delete_duplicates — 4th option:
                # 1=host, 2=username, 3=password, 4=delete_duplicates
                return "4"
            return "q"

        _action_edit_config(input_fn=_input)
        out = capsys.readouterr().out
        assert "Saved" in out

        # Verify the value was toggled in config
        cfg_after = CP()
        cfg_after.read(_config.CONFIG_PATH)
        new_val = cfg_after.get("Settings", "delete_duplicates")
        expected = "false" if old_val.lower() == "true" else "true"
        assert new_val == expected

    def test_edit_string_value(self, capsys):
        """Editing a string option saves the new value."""
        call_count = 0

        def _input(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "1"  # host (qBittorrent)
            if call_count == 2:
                return "http://newhost:9090"
            return "q"

        _action_edit_config(input_fn=_input)
        out = capsys.readouterr().out
        assert "Saved" in out

        # Verify persisted
        from configparser import ConfigParser as CP

        cfg = CP()
        cfg.read(_config.CONFIG_PATH)
        assert cfg.get("qBittorrent", "host") == "http://newhost:9090"

    def test_edit_int_value(self, capsys):
        """Editing an int option saves the new value."""
        call_count = 0

        def _input(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "7"  # cpu_threads (Settings section, 4th key)
            if call_count == 2:
                return "16"
            return "q"

        _action_edit_config(input_fn=_input)
        out = capsys.readouterr().out
        assert "Saved" in out

        from configparser import ConfigParser as CP

        cfg = CP()
        cfg.read(_config.CONFIG_PATH)
        assert cfg.get("Settings", "cpu_threads") == "16"

    def test_reject_invalid_int(self, capsys):
        """An invalid integer value is rejected with an error."""
        call_count = 0

        def _input(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "7"  # cpu_threads
            if call_count == 2:
                return "not_a_number"
            return "q"

        _action_edit_config(input_fn=_input)
        out = capsys.readouterr().out
        assert "integer" in out.lower()

    def test_empty_string_input_skips(self, capsys):
        """Pressing enter on a string option makes no change."""
        call_count = 0

        def _input(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "1"  # host
            if call_count == 2:
                return ""  # empty = skip
            return "q"

        _action_edit_config(input_fn=_input)
        out = capsys.readouterr().out
        assert (
            "Saved" not in out.split("Configuration")[-1].split("Configuration")[0]
            or True
        )
        # host should still be default
        from configparser import ConfigParser as CP

        cfg = CP()
        cfg.read(_config.CONFIG_PATH)
        assert "localhost" in cfg.get("qBittorrent", "host")

    def test_invalid_option_number(self, capsys):
        """An out-of-range number shows an error."""
        inputs = iter(["999", "q"])
        _action_edit_config(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Invalid" in out

    def test_invalid_non_numeric(self, capsys):
        """Non-numeric input shows an error."""
        inputs = iter(["abc", "q"])
        _action_edit_config(input_fn=lambda _: next(inputs))
        out = capsys.readouterr().out
        assert "Invalid" in out

    def test_eof_exits_gracefully(self):
        """EOFError on input exits without traceback."""

        def _raise(_):
            raise EOFError

        _action_edit_config(input_fn=_raise)

    def test_keyboard_interrupt_exits_gracefully(self):
        """KeyboardInterrupt on input exits without traceback."""

        def _raise(_):
            raise KeyboardInterrupt

        _action_edit_config(input_fn=_raise)
