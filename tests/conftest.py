"""Shared fixtures for Plex Organizer tests."""

from warnings import filterwarnings
from os.path import join
from pytest import fixture

from plex_organizer.paths import data_dir
from plex_organizer.config import ensure_config_exists


def pytest_configure():
    """Suppress third-party version mismatch warning fired at import time."""
    filterwarnings(
        "ignore", message=".*doesn't match a supported version", category=Warning
    )


@fixture
def tmp_media_tree(tmp_path):
    """Create a temporary media directory tree with tv/ and movies/ subfolders."""
    (tmp_path / "tv").mkdir()
    (tmp_path / "movies").mkdir()
    return tmp_path


@fixture
def tmp_tv_show(media_tree):
    """Create a TV show directory with season folders."""
    show_dir = media_tree / "tv" / "Breaking Bad"
    show_dir.mkdir(parents=True)
    (show_dir / "Season 01").mkdir()
    return show_dir


@fixture
def tmp_movies_dir(media_tree):
    """Return the movies directory inside a media tree."""
    return media_tree / "movies"


@fixture
def config_dir(tmp_path, monkeypatch):
    """Set up an isolated config directory so tests don't touch the real config."""
    config_path = tmp_path / "config"
    config_path.mkdir()
    monkeypatch.setenv("PLEX_ORGANIZER_DIR", str(config_path))

    data_dir.cache_clear()

    config_ini_path = join(str(config_path), "config.ini")
    monkeypatch.setattr("plex_organizer.config.CONFIG_PATH", config_ini_path)
    monkeypatch.setattr("plex_organizer.log.SCRIPT_DIR", str(config_path))

    yield config_path

    data_dir.cache_clear()


@fixture
def default_config(request):
    """Create a default config.ini in the isolated config directory."""
    cfg_dir = request.getfixturevalue("config_dir")
    ensure_config_exists()
    return cfg_dir
