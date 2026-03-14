"""Sonarr API integration for triggering library rescans after processing."""

from requests import Session, RequestException

from .log import log_info, log_error, log_debug
from .config import get_sonarr_host, get_sonarr_api_key


def _get_headers() -> dict[str, str]:
    """Return request headers with the Sonarr API key."""
    return {"X-Api-Key": get_sonarr_api_key()}


def _find_series(session: Session, name: str) -> int | None:
    """Look up a series by title in Sonarr.

    Args:
        session: An active requests session.
        name: The series title to search for (case-insensitive).

    Returns:
        The Sonarr series ID, or ``None`` if not found.
    """
    url = f"{get_sonarr_host()}/api/v3/series"
    response = session.get(url, headers=_get_headers(), timeout=15)
    response.raise_for_status()

    name_lower = name.lower()
    for series in response.json():
        if series.get("title", "").lower() == name_lower:
            return series["id"]
    return None


def rescan_series(series_name: str):
    """Trigger a Sonarr rescan for a specific series.

    Falls back to a full library rescan when the series is not found.
    Best-effort: errors are logged, not raised.

    Args:
        series_name: The title of the series to rescan.
    """
    log_info(f"Requesting Sonarr rescan for series: {series_name}")

    session = Session()
    try:
        series_id = _find_series(session, series_name)
        body: dict = {"name": "RescanSeries"}
        if series_id is not None:
            body["seriesId"] = series_id
            log_debug(f"Found Sonarr series ID {series_id} for '{series_name}'")
        else:
            log_info(
                f"Series '{series_name}' not found in Sonarr — "
                "triggering full library rescan"
            )

        url = f"{get_sonarr_host()}/api/v3/command"
        response = session.post(url, json=body, headers=_get_headers(), timeout=15)
        response.raise_for_status()
        log_info(f"Sonarr rescan command accepted for '{series_name}'")
    except RequestException as exc:
        log_error(f"Sonarr rescan failed for '{series_name}': {exc}")
    finally:
        session.close()


def notify_series(show_names: set[str]):
    """Notify Sonarr to rescan each processed series.

    Args:
        show_names: Set of series titles that were processed.
    """
    for name in show_names:
        rescan_series(name)
