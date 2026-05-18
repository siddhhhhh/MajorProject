"""Macro / geopolitical context layer.

Purpose: surface exogenous events (wars, energy shocks, pandemics) that
materially shift scope-3 emissions, energy mix, or supply chains during the
analysis window — WITHOUT altering the headline ESG/GW formula. Reports
display the context so readers can interpret year-over-year movement
honestly; the counterfactual module uses the same data to compute
what-if scenarios.

Design rule (load-bearing): nothing in this module mutates scores. It
only loads, filters, scores exposure, and exposes a structured payload.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LEDGER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "macro_events.json"
)

# Cached parsed ledger; invalidated on file mtime change.
_cache: Dict[str, Any] = {"mtime": 0.0, "events": []}


def _load_ledger() -> List[Dict[str, Any]]:
    """Read and cache the curated macro_events.json.

    Returns empty list if the file is missing or malformed — callers
    treat empty as "no macro context active" and proceed normally.
    """
    try:
        mtime = os.path.getmtime(_LEDGER_PATH)
    except OSError:
        return []
    if mtime == _cache["mtime"] and _cache["events"]:
        return _cache["events"]
    try:
        with open(_LEDGER_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f) or {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("macro_events.json unreadable: %s", exc)
        return []
    events = payload.get("events") or []
    if not isinstance(events, list):
        logger.warning("macro_events.json `events` is not a list — ignoring")
        return []
    _cache["mtime"] = mtime
    _cache["events"] = events
    return events


def _parse_date(value: Any) -> Optional[date]:
    if value in (None, "", "null"):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _today() -> date:
    return date.today()


def load_active_events(as_of: Optional[date] = None) -> List[Dict[str, Any]]:
    """Return ledger events whose [start_date, end_date] window contains `as_of`.

    `end_date` of null/missing means ongoing. `as_of` defaults to today.
    """
    when = as_of or _today()
    active: List[Dict[str, Any]] = []
    for ev in _load_ledger():
        start = _parse_date(ev.get("start_date"))
        end = _parse_date(ev.get("end_date"))
        if start is None:
            continue
        if when < start:
            continue
        if end is not None and when > end:
            continue
        active.append(ev)
    return active


def _normalise_industry(industry: str) -> str:
    """Lowercase + collapse whitespace/punctuation so 'Oil & Gas' matches
    'oil_and_gas' in the ledger."""
    s = str(industry or "").lower().strip()
    s = s.replace("&", "and")
    s = re.sub(r"[\s\-/]+", "_", s)
    s = re.sub(r"[^a-z0-9_]+", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _lookup_exposure(industry_map: Dict[str, float], industry: str) -> float:
    """Find the best industry match in the event's exposure map.

    Tries: exact normalised key → contains-match either direction → default.
    """
    if not isinstance(industry_map, dict) or not industry_map:
        return 0.0
    norm = _normalise_industry(industry)
    if norm and norm in industry_map:
        return float(industry_map[norm])
    # Soft match: key is substring of industry, or industry of key.
    for k, v in industry_map.items():
        if not isinstance(k, str):
            continue
        if k == "default":
            continue
        if k in norm or norm in k:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    try:
        return float(industry_map.get("default", 0.0))
    except (TypeError, ValueError):
        return 0.0


def compute_exposure(
    industry: str,
    events: Optional[List[Dict[str, Any]]] = None,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """Per-event and aggregate exposure for the given industry.

    Aggregate is the **maximum** exposure across events (not sum) — two
    parallel crises don't double-count, since both are upper-bounded by
    the larger of the two shocks for that industry. This is conservative
    and deliberately avoids over-claiming the counterfactual delta.
    """
    if events is None:
        events = load_active_events(as_of)

    per_event: List[Dict[str, Any]] = []
    aggregate = 0.0
    for ev in events:
        exposure = _lookup_exposure(ev.get("industry_exposure") or {}, industry)
        per_event.append({
            "event_id":          ev.get("event_id"),
            "name":              ev.get("name"),
            "exposure":          round(exposure, 3),
            "channels":          [c.get("channel") for c in (ev.get("channels") or [])],
            "geographic_scope":  ev.get("geographic_scope") or [],
        })
        if exposure > aggregate:
            aggregate = exposure

    return {
        "industry":             industry,
        "industry_normalised":  _normalise_industry(industry),
        "events_considered":    len(events),
        "per_event":            per_event,
        "aggregate_exposure":   round(aggregate, 3),
    }


def surface_for_report(state: Dict[str, Any]) -> Dict[str, Any]:
    """Build the macro_context dict stamped onto every report.

    Reads `industry` from state and the curated ledger; returns a fully
    populated structure even when nothing is active (so report templates
    can rely on the shape). NEVER touches scoring fields.
    """
    industry = state.get("industry") or ""
    as_of_raw = state.get("analysis_date") or state.get("timestamp")
    as_of = _parse_date(as_of_raw) if as_of_raw else None

    active = load_active_events(as_of)
    exposure = compute_exposure(industry, active, as_of)

    # Gap 3: evaluate live signals if any provider is configured.
    try:
        from core.macro_signals import calibrate_events
        live_signal_calibration = calibrate_events(active)
    except Exception as exc:
        logger.warning("macro_signals.calibrate_events failed: %s", exc)
        live_signal_calibration = []

    return {
        "agent":                    "macro_context",
        "status":                   "ACTIVE_EVENTS_PRESENT" if active else "NO_ACTIVE_EVENTS",
        "as_of":                    (as_of.isoformat() if as_of else _today().isoformat()),
        "active_events":            active,
        "industry_exposure":        exposure,
        "scoring_impact":           "NONE — display + counterfactual only, formula unchanged",
        "channels_affected":        sorted({
            c.get("channel")
            for ev in active
            for c in (ev.get("channels") or [])
            if isinstance(c, dict) and c.get("channel")
        }),
        "live_signal_calibration":  live_signal_calibration,
    }
