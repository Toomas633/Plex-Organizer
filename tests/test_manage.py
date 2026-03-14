"""Tests for plex_organizer.manage."""

from json import dumps
from time import sleep
from unittest.mock import patch
from configparser import ConfigParser
from pytest import mark, raises

from plex_organizer.manage import (
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
    _find_pids,
    _process_cmdline,
    kill_run,
    _add_summary,
    _directories_to_scan,
    _is_video_candidate,
    _read_index_keys,
    _rel_key,
    _safe_mark_indexed,
    _safe_should_index_video,
    _get_or_load_index_keys,
    _scan_and_index_root,
    _scan_and_index_directory,
    generate_indexes,
)
from plex_organizer.const import INDEX_FILENAME
from plex_organizer.dataclass import IndexSummary
from plex_organizer.indexing import _read_index, _write_index
from plex_organizer import config


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

    @patch("plex_organizer.manage.run")
    def test_prints_folder_path(self, _mock_run, capsys):
        """The data directory path is printed to stdout."""
        _action_open_folder()
        out = capsys.readouterr().out
        assert "Organizer folder" in out

    @patch("plex_organizer.manage.run")
    def test_calls_xdg_open(self, mock_run):
        """xdg-open is invoked to open the data directory."""
        _action_open_folder()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "xdg-open"

    @patch(
        "plex_organizer.manage.run",
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

    @patch("plex_organizer.manage.call")
    @patch("plex_organizer.manage._command_exists", return_value=True)
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

    @patch("plex_organizer.manage.call", side_effect=OSError)
    @patch("plex_organizer.manage._command_exists", return_value=True)
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

    @patch("plex_organizer.manage._command_exists", return_value=False)
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

    @patch("plex_organizer.manage._command_exists", return_value=False)
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
        "plex_organizer.manage.check_output",
        side_effect=FileNotFoundError,
    )
    def test_missing_which(self, _mock):
        """FileNotFoundError from which causes False."""
        assert _command_exists("nonexistent_tool") is False

    @patch(
        "plex_organizer.manage.check_output",
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

    @patch("plex_organizer.manage.generate_indexes")
    def test_calls_generate_indexes(self, mock_gen, tmp_path):
        """generate_indexes is called with the provided media root."""
        media = tmp_path / "media"
        media.mkdir()
        (media / "tv").mkdir()
        (media / "movies").mkdir()

        _action_generate_indexes(input_fn=lambda _: str(media))
        mock_gen.assert_called_once_with(str(media))

    @patch(
        "plex_organizer.manage.generate_indexes",
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

    @patch("plex_organizer.manage.kill_run")
    def test_calls_kill_run(self, mock_kill):
        """The kill run function is invoked."""
        _action_kill_organizers()
        mock_kill.assert_called_once()

    @patch("plex_organizer.manage.kill_run")
    def test_prints_surrounding_newlines(self, _mock_kill, capsys):
        """Output is wrapped with blank lines."""
        _action_kill_organizers()
        assert capsys.readouterr().out == "\n\n"


@mark.usefixtures("default_config")
class TestActionMigrateTvIndexes:
    """Tests for option 7: migrate per-show TV indexes to root."""

    @patch(
        "plex_organizer.manage.migrate_show_indexes_to_tv_root",
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
        "plex_organizer.manage.migrate_show_indexes_to_tv_root",
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
        "plex_organizer.manage.migrate_show_indexes_to_tv_root",
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

    @patch("plex_organizer.manage.sys_exit")
    @patch("plex_organizer.manage._run_menu")
    def test_calls_run_menu(self, mock_menu, _mock_exit):
        """main() delegates to _run_menu."""
        main()
        mock_menu.assert_called_once()

    @patch("plex_organizer.manage.sys_exit")
    @patch("plex_organizer.manage._run_menu")
    def test_calls_sys_exit_zero(self, _mock_menu, mock_exit):
        """main() exits with code 0."""
        main()
        mock_exit.assert_called_once_with(0)

    @patch("plex_organizer.manage.sys_exit")
    @patch("plex_organizer.manage._run_menu")
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

    @patch("plex_organizer.manage._run_full_pipeline")
    def test_runs_full_pipeline(self, mock_fn, tmp_path, capsys):
        """Selecting step 1 then running executes the full pipeline."""
        d = tmp_path / "media"
        d.mkdir()
        inputs = iter([str(d), "1", "r"])
        _action_custom_run(input_fn=lambda _: next(inputs))
        args, _ = mock_fn.call_args
        assert args[0] == str(d)
        out = capsys.readouterr().out
        assert "Done" in out

    @patch("plex_organizer.manage._run_embed_subs")
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

    @patch("plex_organizer.manage._run_delete_empty")
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
        "plex_organizer.manage._run_full_pipeline",
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

    @patch("plex_organizer.manage.merge_subtitles_in_directory")
    @patch("plex_organizer.manage.fetch_subtitles_in_directory")
    @patch("plex_organizer.manage.sync_subtitles_in_directory")
    @patch("plex_organizer.manage.analyze_video_languages")
    @patch("plex_organizer.manage.delete_unwanted_files")
    @patch("plex_organizer.manage.move_directories")
    @patch("plex_organizer.manage.delete_empty_directories")
    def test_full_pipeline_expands_main_folder(
        self,
        _mock_del_empty,
        _mock_move,
        _mock_del_unwanted,
        _mock_analyze,
        _mock_sync,
        _mock_fetch,
        mock_embed,
        tmp_path,
    ):
        """Full pipeline processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        inputs = iter(["", "", "y", "y", "2", "y", "y", "n"])
        _run_full_pipeline(str(d), input_fn=lambda _: next(inputs))

        called_dirs = [c.args[0] for c in mock_embed.call_args_list]
        assert str(d / "tv") in called_dirs
        assert str(d / "movies") in called_dirs

    @patch("plex_organizer.manage.merge_subtitles_in_directory")
    def test_embed_subs_expands_main_folder(self, mock_embed, tmp_path):
        """Embed subs processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        inputs = iter(["y"])
        _run_embed_subs(str(d), input_fn=lambda _: next(inputs))

        called_dirs = [c.args[0] for c in mock_embed.call_args_list]
        assert str(d / "tv") in called_dirs
        assert str(d / "movies") in called_dirs

    @patch("plex_organizer.manage.fetch_subtitles_in_directory")
    def test_fetch_subs_expands_main_folder(self, mock_fetch, tmp_path):
        """Fetch subs processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        inputs = iter(["eng"])
        _run_fetch_subs(str(d), input_fn=lambda _: next(inputs))

        called_dirs = [c.args[0] for c in mock_fetch.call_args_list]
        assert str(d / "tv") in called_dirs
        assert str(d / "movies") in called_dirs

    @patch("plex_organizer.manage.sync_subtitles_in_directory")
    def test_sync_subs_expands_main_folder(self, mock_sync, tmp_path):
        """Sync subs processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        _run_sync_subs(str(d))

        called_dirs = [c.args[0] for c in mock_sync.call_args_list]
        assert str(d / "tv") in called_dirs
        assert str(d / "movies") in called_dirs

    @patch("plex_organizer.manage.tag_audio_track_languages")
    def test_tag_audio_expands_main_folder(self, mock_tag, tmp_path):
        """Tag audio processes videos under tv/ and movies/ separately."""
        d = self._make_main_folder(tmp_path)

        (d / "movies" / "Test (2020)").mkdir(parents=True)
        (d / "movies" / "Test (2020)" / "Test (2020).mkv").touch()
        (d / "tv" / "Show" / "Season 1").mkdir(parents=True)
        (d / "tv" / "Show" / "Season 1" / "Show S01E01.mkv").touch()

        inputs = iter(["2"])
        _run_tag_audio(str(d), input_fn=lambda _: next(inputs))

        assert mock_tag.call_count == 2

    @patch("plex_organizer.manage.delete_unwanted_files")
    def test_cleanup_expands_main_folder(self, mock_del, tmp_path):
        """Cleanup processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)
        _run_cleanup(str(d))

        called_roots = [c.args[0] for c in mock_del.call_args_list]
        tv_processed = any(str(d / "tv") in r for r in called_roots)
        movies_processed = any(str(d / "movies") in r for r in called_roots)
        assert tv_processed
        assert movies_processed

    @patch("plex_organizer.manage.move_directories")
    def test_rename_move_expands_main_folder(self, mock_move, tmp_path):
        """Rename & move processes tv and movies subdirectories separately."""
        d = self._make_main_folder(tmp_path)

        (d / "movies" / "Test (2020)").mkdir(parents=True)
        (d / "movies" / "Test (2020)" / "Test (2020).mkv").touch()

        inputs = iter(["y", "y", "n"])
        _run_rename_move(str(d), input_fn=lambda _: next(inputs))

        called_dirs = [c.args[0] for c in mock_move.call_args_list]
        assert all(str(d / "movies") in cd or str(d / "tv") in cd for cd in called_dirs)
        assert str(d) not in called_dirs or all(
            cd.startswith(str(d / "movies")) or cd.startswith(str(d / "tv"))
            for cd in called_dirs
        )

    @patch("plex_organizer.manage.delete_empty_directories")
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
        main_dir = tmp_path / "media"
        movies = main_dir / "movies"
        tv = main_dir / "tv"

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

        _update_index_after_custom_run(str(main_dir))

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
        """'true' is valid for bool type."""
        assert _validate_config_value("bool", "true") is None

    def test_bool_accepts_false(self):
        """'false' is valid for bool type."""
        assert _validate_config_value("bool", "false") is None

    def test_bool_rejects_invalid(self):
        """Non-boolean string is rejected."""
        assert _validate_config_value("bool", "yes") is not None

    def test_int_accepts_number(self):
        """Numeric string is valid for int type."""
        assert _validate_config_value("int", "4") is None

    def test_int_rejects_text(self):
        """Non-numeric string is rejected for int type."""
        assert _validate_config_value("int", "abc") is not None

    def test_str_accepts_anything(self):
        """Any string is valid for str type."""
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
        cfg_before = ConfigParser()
        cfg_before.read(config.CONFIG_PATH)
        old_val = cfg_before.get("Settings", "delete_duplicates")

        call_count = 0

        def _input(_prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "4"
            return "q"

        _action_edit_config(input_fn=_input)
        out = capsys.readouterr().out
        assert "Saved" in out

        cfg_after = ConfigParser()
        cfg_after.read(config.CONFIG_PATH)
        new_val = cfg_after.get("Settings", "delete_duplicates")
        expected = "false" if old_val.lower() == "true" else "true"
        assert new_val == expected

    def test_edit_string_value(self, capsys):
        """Editing a string option saves the new value."""
        call_count = 0

        def _input(_prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "1"
            if call_count == 2:
                return "http://newhost:9090"
            return "q"

        _action_edit_config(input_fn=_input)
        out = capsys.readouterr().out
        assert "Saved" in out

        cfg = ConfigParser()
        cfg.read(config.CONFIG_PATH)
        assert cfg.get("qBittorrent", "host") == "http://newhost:9090"

    def test_edit_int_value(self, capsys):
        """Editing an int option saves the new value."""
        call_count = 0

        def _input(_prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "7"
            if call_count == 2:
                return "16"
            return "q"

        _action_edit_config(input_fn=_input)
        out = capsys.readouterr().out
        assert "Saved" in out

        cfg = ConfigParser()
        cfg.read(config.CONFIG_PATH)
        assert cfg.get("Settings", "cpu_threads") == "16"

    def test_reject_invalid_int(self, capsys):
        """An invalid integer value is rejected with an error."""
        call_count = 0

        def _input(_prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "7"
            if call_count == 2:
                return "not_a_number"
            return "q"

        _action_edit_config(input_fn=_input)
        out = capsys.readouterr().out
        assert "integer" in out.lower()

    def test_empty_string_input_skips(self, capsys):
        """Pressing enter on a string option makes no change."""
        call_count = 0

        def _input(_prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "1"
            if call_count == 2:
                return ""
            return "q"

        _action_edit_config(input_fn=_input)
        capsys.readouterr()

        cfg = ConfigParser()
        cfg.read(config.CONFIG_PATH)
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


class TestFindPids:
    """Tests for _find_pids."""

    @patch("plex_organizer.manage.getpid", return_value=100)
    @patch(
        "plex_organizer.manage.check_output",
        return_value="200\n300\n100\n",
    )
    def test_returns_pids_excluding_own(self, _mock_pgrep, _mock_getpid):
        """Own PID is excluded from the result list."""
        result = _find_pids()
        assert result == [200, 300]

    @patch("plex_organizer.manage.getpid", return_value=1)
    @patch(
        "plex_organizer.manage.check_output",
        return_value="abc\n200\n\n",
    )
    def test_ignores_non_numeric_lines(self, _mock_pgrep, _mock_getpid):
        """Non-numeric lines in pgrep output are silently skipped."""
        result = _find_pids()
        assert result == [200]

    @patch("plex_organizer.manage.getpid", return_value=1)
    @patch(
        "plex_organizer.manage.check_output",
        side_effect=FileNotFoundError,
    )
    def test_returns_empty_on_file_not_found(self, _mock_pgrep, _mock_getpid):
        """Returns empty list when pgrep is not installed."""
        assert not _find_pids()

    @patch("plex_organizer.manage.getpid", return_value=1)
    @patch(
        "plex_organizer.manage.check_output",
        side_effect=__import__("subprocess").CalledProcessError(1, "pgrep"),
    )
    def test_returns_empty_on_called_process_error(self, _mock_pgrep, _mock_getpid):
        """Returns empty list when pgrep exits with a non-zero code."""
        assert not _find_pids()


class TestProcessCmdline:
    """Tests for _process_cmdline."""

    @patch(
        "plex_organizer.manage.check_output",
        return_value="python -m plex_organizer /media\n",
    )
    def test_returns_command_line(self, _mock_ps):
        """Returns the stripped command line string."""
        assert _process_cmdline(42) == "python -m plex_organizer /media"

    @patch(
        "plex_organizer.manage.check_output",
        side_effect=FileNotFoundError,
    )
    def test_returns_unknown_on_error(self, _mock_ps):
        """Returns 'unknown' when ps fails."""
        assert _process_cmdline(42) == "unknown"

    @patch(
        "plex_organizer.manage.check_output",
        side_effect=__import__("subprocess").CalledProcessError(1, "ps"),
    )
    def test_returns_unknown_on_called_process_error(self, _mock_ps):
        """Returns 'unknown' when ps exits non-zero."""
        assert _process_cmdline(42) == "unknown"


@mark.usefixtures("default_config")
class TestKillRun:
    """Tests for the kill_run() function."""

    @patch("plex_organizer.manage.exists", return_value=False)
    @patch("plex_organizer.manage._find_pids", return_value=[])
    def test_no_processes_no_lock(self, _pids, _exists, capsys):
        """Prints informational messages when nothing to do."""
        kill_run()
        out = capsys.readouterr().out
        assert "No running plex-organizer processes found." in out
        assert "No lock file found" in out

    @patch("plex_organizer.manage.remove")
    @patch("plex_organizer.manage.exists", return_value=True)
    @patch("plex_organizer.manage.kill")
    @patch("plex_organizer.manage._process_cmdline", return_value="plex-organizer")
    @patch("plex_organizer.manage._find_pids", return_value=[42, 99])
    def test_kills_processes_and_removes_lock(
        self, _pids, _cmd, mock_kill, _exists, mock_rm, capsys
    ):
        """Kills found processes and removes the lock file."""
        kill_run()
        assert mock_kill.call_count == 2
        mock_rm.assert_called_once()
        out = capsys.readouterr().out
        assert "Killed 2 process(es)." in out
        assert "Removed lock file" in out

    @patch("plex_organizer.manage.exists", return_value=False)
    @patch("plex_organizer.manage.kill", side_effect=ProcessLookupError)
    @patch("plex_organizer.manage._process_cmdline", return_value="cmd")
    @patch("plex_organizer.manage._find_pids", return_value=[42])
    def test_process_lookup_error_silenced(self, _pids, _cmd, _kill, _exists, capsys):
        """ProcessLookupError (already dead) is silently ignored."""
        kill_run()
        out = capsys.readouterr().out
        assert "No running plex-organizer processes found." in out

    @patch("plex_organizer.manage.exists", return_value=False)
    @patch("plex_organizer.manage.kill", side_effect=PermissionError)
    @patch("plex_organizer.manage._process_cmdline", return_value="cmd")
    @patch("plex_organizer.manage._find_pids", return_value=[42])
    def test_permission_error_printed(self, _pids, _cmd, _kill, _exists, capsys):
        """PermissionError is reported to the user."""
        kill_run()
        out = capsys.readouterr().out
        assert "Permission denied" in out

    @patch("plex_organizer.manage.remove", side_effect=OSError("device busy"))
    @patch("plex_organizer.manage.exists", return_value=True)
    @patch("plex_organizer.manage._find_pids", return_value=[])
    def test_lock_remove_oserror(self, _pids, _exists, _rm, capsys):
        """OSError removing the lock file is reported."""
        kill_run()
        out = capsys.readouterr().out
        assert "Failed to remove lock file" in out
        assert "device busy" in out


class TestRelKey:
    """Tests for _rel_key."""

    def test_relative_path(self):
        """Returns a normalised relative key."""
        result = _rel_key("/media/movies", "/media/movies/Film (2020)/Film (2020).mkv")
        assert result == "Film (2020)/Film (2020).mkv"

    def test_same_directory(self):
        """File in the index root itself."""
        result = _rel_key("/media/movies", "/media/movies/video.mkv")
        assert result == "video.mkv"


class TestReadIndexKeys:
    """Tests for _read_index_keys."""

    def test_returns_keys_from_valid_index(self, tmp_path):
        """Reads keys from a well-formed index file."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text(dumps({"files": {"a.mkv": True, "b.mkv": True}}))
        result = _read_index_keys(str(tmp_path))
        assert result == {"a.mkv", "b.mkv"}

    def test_returns_empty_when_no_file(self, tmp_path):
        """Returns empty set when the index does not exist."""
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_on_invalid_json(self, tmp_path):
        """Returns empty set on malformed JSON."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text("{bad json")
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_when_payload_not_dict(self, tmp_path):
        """Returns empty set when top-level JSON is not a dict."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text(dumps([1, 2, 3]))
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_when_files_not_dict(self, tmp_path):
        """Returns empty set when 'files' value is not a dict."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text(dumps({"files": "nope"}))
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_when_no_files_key(self, tmp_path):
        """Returns empty set when 'files' key is missing."""
        idx = tmp_path / ".plex_organizer.index"
        idx.write_text(dumps({"other": 1}))
        assert _read_index_keys(str(tmp_path)) == set()

    def test_returns_empty_on_oserror(self, tmp_path):
        """Returns empty set when reading triggers an OSError."""
        with patch("builtins.open", side_effect=OSError("fail")):
            assert _read_index_keys(str(tmp_path)) == set()


class TestDirectoriesToScan:
    """Tests for _directories_to_scan."""

    def test_main_root_with_tv_and_movies(self, tmp_path):
        """Returns tv/ and movies/ when both exist under start_dir."""
        (tmp_path / "tv").mkdir()
        (tmp_path / "movies").mkdir()
        result = _directories_to_scan(str(tmp_path))
        assert len(result) == 2
        assert any("tv" in d for d in result)
        assert any("movies" in d for d in result)

    def test_tv_folder_directly(self, tmp_path):
        """Accepts a folder named 'tv' directly."""
        tv = tmp_path / "tv"
        tv.mkdir()
        result = _directories_to_scan(str(tv))
        assert result == [str(tv)]

    def test_movies_folder_directly(self, tmp_path):
        """Accepts a folder named 'movies' directly."""
        movies = tmp_path / "movies"
        movies.mkdir()
        result = _directories_to_scan(str(movies))
        assert result == [str(movies)]

    def test_show_under_tv(self, tmp_path):
        """Accepts a tv/<Show> path (parent is 'tv')."""
        tv = tmp_path / "tv"
        show = tv / "MyShow"
        show.mkdir(parents=True)
        result = _directories_to_scan(str(show))
        assert result == [str(show)]

    def test_invalid_root_raises(self, tmp_path):
        """Raises ValueError for an unrecognised directory structure."""
        random = tmp_path / "random"
        random.mkdir()
        with raises(ValueError, match="Invalid root"):
            _directories_to_scan(str(random))


class TestAddSummary:  # pylint: disable=too-few-public-methods
    """Tests for _add_summary."""

    def test_adds_two_summaries(self):
        """Fields from both summaries are added."""
        a = IndexSummary(total_videos=2, eligible_videos=1, newly_indexed=1)
        b = IndexSummary(total_videos=3, eligible_videos=2, newly_indexed=0)
        result = _add_summary(a, b)
        assert result == IndexSummary(
            total_videos=5, eligible_videos=3, newly_indexed=1
        )


class TestIsVideoCandidate:
    """Tests for _is_video_candidate."""

    def test_video_extension_accepted(self):
        """MKV file is a video candidate."""
        assert _is_video_candidate("movie.mkv") is True

    def test_non_video_rejected(self):
        """SRT file is not a video candidate."""
        assert _is_video_candidate("sub.srt") is False

    def test_script_temp_file_rejected(self):
        """Organizer temp files are rejected even with video ext."""
        assert _is_video_candidate("video.langtag.mkv") is False


class TestSafeWrappers:
    """Tests for _safe_should_index_video and _safe_mark_indexed."""

    @patch(
        "plex_organizer.manage.should_index_video",
        return_value=True,
    )
    def test_safe_should_index_returns_result(self, _mock):
        """Delegates to should_index_video."""
        assert _safe_should_index_video("/root", "/root/v.mkv") is True

    @patch(
        "plex_organizer.manage.should_index_video",
        side_effect=OSError,
    )
    def test_safe_should_index_returns_false_on_error(self, _mock):
        """Returns False when should_index_video raises OSError."""
        assert _safe_should_index_video("/root", "/root/v.mkv") is False

    @patch("plex_organizer.manage.mark_indexed")
    def test_safe_mark_returns_true(self, _mock):
        """Returns True when mark_indexed succeeds."""
        assert _safe_mark_indexed("/root", "/root/v.mkv") is True

    @patch(
        "plex_organizer.manage.mark_indexed",
        side_effect=OSError,
    )
    def test_safe_mark_returns_false_on_error(self, _mock):
        """Returns False when mark_indexed raises OSError."""
        assert _safe_mark_indexed("/root", "/root/v.mkv") is False


class TestGetOrLoadIndexKeys:
    """Tests for _get_or_load_index_keys caching."""

    def test_uses_cache_on_hit(self):
        """Returns cached set without reading disk."""
        cache = {"/root": {"a.mkv"}}
        result = _get_or_load_index_keys(cache, "/root")
        assert result == {"a.mkv"}

    @patch(
        "plex_organizer.manage._read_index_keys",
        return_value={"b.mkv"},
    )
    def test_reads_and_caches_on_miss(self, mock_read):
        """Reads from disk on a cache miss and stores the result."""
        cache = {}
        result = _get_or_load_index_keys(cache, "/root")
        assert result == {"b.mkv"}
        assert cache["/root"] == {"b.mkv"}
        mock_read.assert_called_once_with("/root")


@mark.usefixtures("default_config")
class TestScanAndIndexRoot:
    """Tests for _scan_and_index_root."""

    @patch(
        "plex_organizer.manage._safe_mark_indexed",
        return_value=True,
    )
    @patch(
        "plex_organizer.manage._safe_should_index_video",
        return_value=True,
    )
    @patch(
        "plex_organizer.manage.index_root_for_path",
        return_value="/media/movies",
    )
    def test_indexes_eligible_video(self, _ir, _si, _mark):
        """Eligible video that is not yet cached gets indexed."""
        cache = {"/media/movies": set()}
        result = _scan_and_index_root(
            "/media/movies", "/media/movies", ["film.mkv", "readme.txt"], cache
        )
        assert result.total_videos == 1
        assert result.eligible_videos == 1
        assert result.newly_indexed == 1

    @patch(
        "plex_organizer.manage.index_root_for_path",
        return_value="/media/movies",
    )
    def test_skips_plex_folder(self, _ir):
        """Plex-managed folders return an empty summary."""
        result = _scan_and_index_root(
            "/media/movies",
            "/media/movies/Plex Versions",
            ["video.mkv"],
            {},
        )
        assert result == IndexSummary(0, 0, 0)

    @patch(
        "plex_organizer.manage._safe_should_index_video",
        return_value=False,
    )
    @patch(
        "plex_organizer.manage.index_root_for_path",
        return_value="/media/movies",
    )
    def test_not_eligible_skipped(self, _ir, _si):
        """Video that is not eligible is counted but not indexed."""
        cache = {"/media/movies": set()}
        result = _scan_and_index_root(
            "/media/movies", "/media/movies", ["film.mkv"], cache
        )
        assert result.total_videos == 1
        assert result.eligible_videos == 0
        assert result.newly_indexed == 0

    @patch(
        "plex_organizer.manage._safe_should_index_video",
        return_value=True,
    )
    @patch(
        "plex_organizer.manage.index_root_for_path",
        return_value="/media/movies",
    )
    def test_already_cached_key_not_reindexed(self, _ir, _si):
        """Video whose key is already in cache is not re-indexed."""
        cache = {"/media/movies": {"film.mkv"}}
        result = _scan_and_index_root(
            "/media/movies", "/media/movies", ["film.mkv"], cache
        )
        assert result.total_videos == 1
        assert result.eligible_videos == 1
        assert result.newly_indexed == 0

    @patch(
        "plex_organizer.manage._safe_mark_indexed",
        return_value=False,
    )
    @patch(
        "plex_organizer.manage._safe_should_index_video",
        return_value=True,
    )
    @patch(
        "plex_organizer.manage.index_root_for_path",
        return_value="/media/movies",
    )
    def test_mark_failure_not_counted(self, _ir, _si, _mark):
        """Failed mark_indexed does not increment newly_indexed."""
        cache = {"/media/movies": set()}
        result = _scan_and_index_root(
            "/media/movies", "/media/movies", ["film.mkv"], cache
        )
        assert result.total_videos == 1
        assert result.eligible_videos == 1
        assert result.newly_indexed == 0


@mark.usefixtures("default_config")
class TestScanAndIndexDirectory:  # pylint: disable=too-few-public-methods
    """Tests for _scan_and_index_directory."""

    @patch(
        "plex_organizer.manage._scan_and_index_root",
        return_value=IndexSummary(2, 1, 1),
    )
    @patch(
        "plex_organizer.manage.walk",
        return_value=[("/media/movies", [], ["a.mkv", "b.mkv"])],
    )
    def test_aggregates_walk_results(self, _walk, _scan):
        """Summary is accumulated from walk iterations."""
        result = _scan_and_index_directory("/media/movies", {})
        assert result.total_videos == 2


@mark.usefixtures("default_config")
class TestGenerateIndexes:
    """Tests for generate_indexes."""

    @patch("plex_organizer.manage._scan_and_index_directory")
    @patch("plex_organizer.manage._directories_to_scan")
    @patch("plex_organizer.manage.ensure_config_exists")
    def test_valid_directory(self, _cfg, mock_dirs, mock_scan, tmp_path, capsys):
        """Runs scan for each directory and prints summary."""
        mock_dirs.return_value = [str(tmp_path)]
        mock_scan.return_value = IndexSummary(5, 3, 2)
        result = generate_indexes(str(tmp_path))
        assert result.total_videos == 5
        assert result.newly_indexed == 2
        out = capsys.readouterr().out
        assert "Videos found: 5" in out
        assert "Newly indexed: 2" in out

    def test_not_a_directory_raises(self, tmp_path):
        """Raises ValueError when start_dir is not an existing directory."""
        with raises(ValueError, match="Not a directory"):
            generate_indexes(str(tmp_path / "nope"))

    @patch("plex_organizer.manage._scan_and_index_directory")
    @patch("plex_organizer.manage.ensure_config_exists")
    def test_multiple_directories(self, _cfg, mock_scan, tmp_path):
        """Processes both tv/ and movies/ for a main root."""
        (tmp_path / "tv").mkdir()
        (tmp_path / "movies").mkdir()
        mock_scan.return_value = IndexSummary(3, 2, 1)
        result = generate_indexes(str(tmp_path))
        assert mock_scan.call_count == 2
        assert result.total_videos == 6
        assert result.newly_indexed == 2
