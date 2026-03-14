"""Radarr API integration for triggering library rescans after processing."""

from requests import Session, RequestException

from .log import log_info, log_error, log_debug
from .config import get_radarr_host, get_radarr_api_key


def _get_headers() -> dict[str, str]:
    """Return request headers with the Radarr API key."""
    return {"X-Api-Key": get_radarr_api_key()}


def _find_movie(session: Session, name: str) -> int | None:
    """Look up a movie by title in Radarr.

    Args:
        session: An active requests session.
        name: The movie title to search for (case-insensitive).

    Returns:
        The Radarr movie ID, or ``None`` if not found.
    """
    url = f"{get_radarr_host()}/api/v3/movie"
    response = session.get(url, headers=_get_headers(), timeout=15)
    response.raise_for_status()

    name_lower = name.lower()
    for movie in response.json():
        if movie.get("title", "").lower() == name_lower:
            return movie["id"]
    return None


def rescan_movie(movie_name: str):
    """Trigger a Radarr rescan for a specific movie.

    Falls back to a full library rescan when the movie is not found.
    Best-effort: errors are logged, not raised.

    Args:
        movie_name: The title of the movie to rescan.
    """
    log_info(f"Requesting Radarr rescan for movie: {movie_name}")

    session = Session()
    try:
        movie_id = _find_movie(session, movie_name)
        body: dict = {"name": "RescanMovie"}
        if movie_id is not None:
            body["movieId"] = movie_id
            log_debug(f"Found Radarr movie ID {movie_id} for '{movie_name}'")
        else:
            log_info(
                f"Movie '{movie_name}' not found in Radarr — "
                "triggering full library rescan"
            )

        url = f"{get_radarr_host()}/api/v3/command"
        response = session.post(url, json=body, headers=_get_headers(), timeout=15)
        response.raise_for_status()
        log_info(f"Radarr rescan command accepted for '{movie_name}'")
    except RequestException as exc:
        log_error(f"Radarr rescan failed for '{movie_name}': {exc}")
    finally:
        session.close()


def notify_movies(movie_names: set[str]):
    """Notify Radarr to rescan each processed movie.

    Args:
        movie_names: Set of movie titles that were processed.
    """
    for name in movie_names:
        rescan_movie(name)
