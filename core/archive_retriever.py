"""
archive_retriever.py
====================
Multi-archive cascade strategy for retrieving historical web snapshots.

Queries three independent web archives — Wayback Machine, Archive.today,
and the Memento Time Travel aggregator — to find the closest snapshot of a
URL for a given year.  This replaces the previous inconsistent single-source
Wayback Machine retrieval.

Dependencies
------------
    pip install requests requests-cache aiohttp
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Literal
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USER_AGENT = (
    "ESGLens/1.0 (greenwashing-verification-platform; "
    "https://github.com/mahig1705/esg; research-use)"
)
_HEADERS = {"User-Agent": USER_AGENT}
_REQUEST_TIMEOUT = 15  # seconds
_RATE_LIMIT_SLEEP = 0.5  # seconds between archive calls


# ===================================================================
# Individual archive fetchers
# ===================================================================

def fetch_wayback(url: str, target_year: int) -> str | None:
    """Query the Wayback Machine CDX API for the closest snapshot.

    Searches for the snapshot closest to January 1 of *target_year*
    with HTTP status 200.

    Parameters
    ----------
    url : str
        The original URL to look up.
    target_year : int
        The year to find a snapshot for.

    Returns
    -------
    str | None
        Full Wayback Machine replay URL, or ``None`` if nothing found.
    """
    timestamp = f"{target_year}0101000000"  # YYYYMMDDhhmmss
    cdx_url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={quote(url, safe='')}"
        f"&closest={timestamp}"
        "&sort=closest"
        "&limit=1"
        "&output=json"
        "&filter=statuscode:200"
    )
    try:
        resp = requests.get(cdx_url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        rows = resp.json()
        if len(rows) < 2:
            logger.info("Wayback: no snapshots found for %s near %d", url, target_year)
            return None

        # rows[0] = header, rows[1] = first result
        # CDX columns: urlkey, timestamp, original, mimetype, statuscode, digest, length
        ts = rows[1][1]
        original = rows[1][2]
        snapshot_url = f"https://web.archive.org/web/{ts}/{original}"
        logger.info("Wayback: found snapshot %s", snapshot_url)
        return snapshot_url
    except requests.exceptions.Timeout:
        logger.warning("Wayback: request timed out for %s", url)
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning("Wayback: request failed for %s — %s", url, exc)
        return None
    except (ValueError, KeyError, IndexError) as exc:
        logger.warning("Wayback: failed to parse response for %s — %s", url, exc)
        return None


def _parse_http_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        # Example: "Mon, 20 Apr 2020 10:00:00 GMT"
        return datetime.strptime(value.strip(), "%a, %d %b %Y %H:%M:%S GMT")
    except ValueError:
        return None


def fetch_archive_today(url: str, target_year: int | None = None) -> str | None:
    """Query Archive.today (archive.ph / archive.is) for a saved snapshot.

    Archive.today has no public JSON API.  We query the search page and
    follow the redirect to find the most recent snapshot.

    Parameters
    ----------
    url : str
        The original URL to look up.

    Returns
    -------
    str | None
        Archive.today snapshot URL, or ``None`` if not found.
    """
    # Prefer timemap lookup when target_year is provided so we can choose
    # a closer snapshot than just "newest".
    if target_year is not None:
        timemap_endpoints = [
            f"https://archive.ph/timemap/{url}",
            f"https://archive.is/timemap/{url}",
        ]
        best_url = None
        best_distance = 10_000
        for tm_url in timemap_endpoints:
            try:
                tm_resp = requests.get(tm_url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
                if tm_resp.status_code != 200:
                    continue
                body = tm_resp.text or ""
                # Timemap lines often contain:
                # <https://archive.ph/xxxx>; rel="memento"; datetime="Mon, 20 Apr 2020 10:00:00 GMT"
                for line in body.splitlines():
                    if 'rel="memento"' not in line:
                        continue
                    parts = [p.strip() for p in line.split(";")]
                    if not parts:
                        continue
                    uri_part = parts[0]
                    if not (uri_part.startswith("<") and uri_part.endswith(">")):
                        continue
                    snapshot_url = uri_part[1:-1].strip()
                    datetime_part = next((p for p in parts if p.startswith('datetime=')), "")
                    dt_raw = datetime_part.replace('datetime=', "").strip().strip('"')
                    dt = _parse_http_datetime(dt_raw)
                    if dt is None:
                        continue
                    distance = abs(dt.year - int(target_year))
                    if distance < best_distance:
                        best_distance = distance
                        best_url = snapshot_url
                if best_url:
                    logger.info(
                        "Archive.today timemap: selected closest snapshot %s (target_year=%s, delta=%s)",
                        best_url, target_year, best_distance,
                    )
                    return best_url
            except requests.exceptions.Timeout:
                logger.warning("Archive.today timemap: request timed out for %s", tm_url)
            except requests.exceptions.RequestException as exc:
                logger.warning("Archive.today timemap: request failed for %s — %s", tm_url, exc)

    # archive.ph and archive.is search endpoints use redirect-based lookup.
    search_endpoints = [
        f"https://archive.ph/newest/{url}",
        f"https://archive.is/newest/{url}",
    ]
    for search_url in search_endpoints:
        try:
            resp = requests.get(
                search_url,
                headers=_HEADERS,
                timeout=_REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            # A successful lookup redirects to the snapshot page.
            # If no snapshot exists, it typically returns a search page
            # or a 404-like page without a valid archive path.
            final_url = resp.url
            if resp.status_code == 200 and (
                "archive.ph/" in final_url or "archive.is/" in final_url
            ):
                # Verify it's an actual snapshot URL (contains a timestamp path)
                if "/newest/" not in final_url:
                    logger.info("Archive.today: found snapshot %s", final_url)
                    return final_url
            logger.debug(
                "Archive.today: no snapshot via %s (status=%d, final=%s)",
                search_url, resp.status_code, final_url,
            )
        except requests.exceptions.Timeout:
            logger.warning("Archive.today: request timed out for %s", search_url)
        except requests.exceptions.RequestException as exc:
            logger.warning("Archive.today: request failed — %s", exc)

    logger.info("Archive.today: no snapshots found for %s", url)
    return None


# Module-level circuit breaker for Memento. The aggregator endpoint
# (timetravel.mementoweb.org) frequently fails to resolve from constrained
# environments; once we've seen it fail we skip subsequent calls for the rest
# of the process to avoid burning ~15s per invocation across many URLs.
_MEMENTO_DISABLED = False
_MEMENTO_DISABLED_REASON: str | None = None


def fetch_memento(url: str, target_year: int) -> str | None:
    """Query the Memento Time Travel aggregator API.

    The `Memento Time Travel API <https://timetravel.mementoweb.org/>`_
    aggregates results from the Internet Archive, Archive-It, UK Web
    Archive, Library of Congress, and dozens of other archives.

    A process-level circuit breaker disables further calls after the first
    DNS / connection failure to avoid repeated 15s timeouts.

    Parameters
    ----------
    url : str
        The original URL to look up.
    target_year : int
        The year to find the closest memento for.

    Returns
    -------
    str | None
        URI of the closest memento, or ``None`` if nothing found.
    """
    global _MEMENTO_DISABLED, _MEMENTO_DISABLED_REASON

    if _MEMENTO_DISABLED:
        # Skip silently after first failure — Wayback + Archive.today still cover
        # the same use case via the cascade in `get_historical_snapshot`.
        return None

    # Memento API expects datetime in YYYYMMDDhhmmss format
    datetime_str = f"{target_year}0101000000"
    api_url = (
        f"https://timetravel.mementoweb.org/api/json/{datetime_str}/"
        f"{url}"
    )
    try:
        resp = requests.get(api_url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        # The API returns { "mementos": { "closest": { "uri": [...] , "datetime": ... } } }
        closest = data.get("mementos", {}).get("closest", {})
        uri = closest.get("uri", [None])
        # uri can be a list or a single string
        if isinstance(uri, list):
            memento_url = uri[0] if uri else None
        else:
            memento_url = uri

        if memento_url:
            logger.info("Memento: found closest memento %s", memento_url)
            return memento_url

        logger.info("Memento: no mementos found for %s near %d", url, target_year)
        return None
    except requests.exceptions.Timeout:
        _MEMENTO_DISABLED = True
        _MEMENTO_DISABLED_REASON = "timeout"
        logger.warning("Memento: request timed out for %s — disabling for rest of process", url)
        return None
    except requests.exceptions.ConnectionError as exc:
        _MEMENTO_DISABLED = True
        _MEMENTO_DISABLED_REASON = f"connection_error: {exc}"
        logger.warning(
            "Memento: connection error for %s — disabling for rest of process (%s)",
            url, exc,
        )
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning("Memento: request failed for %s — %s", url, exc)
        return None
    except (ValueError, KeyError, IndexError) as exc:
        logger.warning("Memento: failed to parse response for %s — %s", url, exc)
        return None


# ===================================================================
# Master cascade function
# ===================================================================

def get_historical_snapshot(
    url: str,
    target_year: int,
    strategy: Literal["cascade", "all"] = "cascade",
) -> dict[str, Any]:
    """Retrieve a historical web snapshot using a multi-archive strategy.

    Parameters
    ----------
    url : str
        The original URL to retrieve a historical snapshot for.
    target_year : int
        The year to find the closest snapshot for.
    strategy : ``"cascade"`` | ``"all"``
        - ``"cascade"``: return on the **first** successful archive hit.
        - ``"all"``: try all three archives and return every result.

    Returns
    -------
    dict
        Keys:
        - ``snapshot_url`` : str | None — best snapshot URL found
        - ``source``       : str | None — which archive provided it
        - ``all_results``  : dict — results from each archive tried
        - ``success``      : bool — whether any snapshot was found
    """
    result: dict[str, Any] = {
        "snapshot_url": None,
        "source": None,
        "all_results": {},
        "success": False,
    }

    archive_functions = [
        ("wayback", lambda: fetch_wayback(url, target_year)),
        ("archive_today", lambda: fetch_archive_today(url, target_year=target_year)),
        ("memento", lambda: fetch_memento(url, target_year)),
    ]

    for i, (name, fetch_fn) in enumerate(archive_functions):
        if i > 0:
            time.sleep(_RATE_LIMIT_SLEEP)

        logger.info("Trying archive: %s for %s (year=%d)", name, url, target_year)
        snapshot = fetch_fn()
        result["all_results"][name] = snapshot

        if snapshot and not result["success"]:
            result["snapshot_url"] = snapshot
            result["source"] = name
            result["success"] = True

            if strategy == "cascade":
                logger.info(
                    "Cascade hit: %s returned snapshot, skipping remaining archives.",
                    name,
                )
                return result

    if result["success"]:
        logger.info(
            "Historical snapshot found via %s: %s",
            result["source"], result["snapshot_url"],
        )
    else:
        logger.warning(
            "No historical snapshot found for %s (year=%d) across all archives.",
            url, target_year,
        )

    return result
