"""Cache of permanently-failing URLs so we don't re-attempt them every run.

Two-tier in-memory + on-disk JSON store keyed by sha256(url). Different
TTLs for different failure modes so transient hiccups eventually re-test
while hard 404s stay buried.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
_CACHE_PATH = os.path.join(_CACHE_DIR, "dead_urls.json")

# TTLs per failure mode (seconds)
_TTL = {
    "404":        30 * 24 * 60 * 60,  # 30 days — page genuinely gone
    "403":         7 * 24 * 60 * 60,  # 7  days — may be temporary block
    "410":        30 * 24 * 60 * 60,  # 30 days — gone permanently
    "5xx":         3 * 24 * 60 * 60,  # 3  days — server flake
    "timeout":     1 * 24 * 60 * 60,  # 1  day  — retry sooner
    "dns":         7 * 24 * 60 * 60,  # 7  days — domain may come back
    "non_html":   30 * 24 * 60 * 60,  # 30 days — content type won't change
    "too_short":   7 * 24 * 60 * 60,  # 7  days — page may grow
    "default":     7 * 24 * 60 * 60,
}

_lock = threading.Lock()
_mem: Optional[dict] = None


def _hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _load() -> dict:
    global _mem
    if _mem is not None:
        return _mem
    if not os.path.exists(_CACHE_PATH):
        _mem = {}
        return _mem
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            _mem = json.load(f) or {}
    except (json.JSONDecodeError, OSError):
        _mem = {}
    return _mem


def _save(data: dict) -> None:
    tmp = _CACHE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, _CACHE_PATH)
    except OSError as exc:
        logger.debug("dead_url_cache save failed: %s", exc)


def is_dead(url: str) -> bool:
    """Return True if the URL is in the cache and still within its TTL.

    Stale entries are pruned lazily on read.
    """
    if not url:
        return False
    with _lock:
        data = _load()
        entry = data.get(_hash(url))
        if not entry:
            return False
        reason = entry.get("reason", "default")
        ttl = _TTL.get(reason, _TTL["default"])
        if time.time() - entry.get("ts", 0) > ttl:
            data.pop(_hash(url), None)
            _save(data)
            return False
        return True


def mark_dead(url: str, reason: str = "default", detail: str = "") -> None:
    """Record a URL as dead. `reason` keys into _TTL.

    Safe to call repeatedly; just refreshes the timestamp.
    """
    if not url:
        return
    if reason not in _TTL:
        # Normalise free-form status codes (e.g., '500') to bucketed reasons.
        try:
            code = int(reason)
            if 500 <= code < 600:
                reason = "5xx"
            elif code == 404:
                reason = "404"
            elif code == 403:
                reason = "403"
            elif code == 410:
                reason = "410"
            else:
                reason = "default"
        except (TypeError, ValueError):
            reason = "default"
    with _lock:
        data = _load()
        data[_hash(url)] = {
            "url":    url[:300],
            "reason": reason,
            "detail": (detail or "")[:200],
            "ts":     time.time(),
        }
        _save(data)


def stats() -> dict:
    """Return a summary of cached dead-URL counts by reason."""
    with _lock:
        data = _load()
        out = {"total": len(data)}
        for entry in data.values():
            r = entry.get("reason", "default")
            out[r] = out.get(r, 0) + 1
        return out


def clear() -> None:
    """Wipe the cache. Test-only."""
    global _mem
    with _lock:
        _mem = {}
        if os.path.exists(_CACHE_PATH):
            os.remove(_CACHE_PATH)
