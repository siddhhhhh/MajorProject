"""GDELT events agent — adverse-event detection wrapper around data_sources/gdelt.

Runs as a parallel post-step to regulatory scanning. Output drops into state
under `gdelt_events` for the report generator and risk_scorer to consume.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from data_sources.gdelt import (
    fetch_events, decay_weighted_intensity, summarise,
)

logger = logging.getLogger(__name__)


def _build_aliases(company: str, entity_record: Optional[Dict[str, Any]]) -> List[str]:
    """Combine canonical name + curated aliases for the GDELT query."""
    aliases: List[str] = []
    if entity_record:
        cn = entity_record.get("canonical_name")
        if cn:
            aliases.append(cn)
        for a in entity_record.get("aliases") or []:
            aliases.append(str(a))
    if company and company not in aliases:
        aliases.insert(0, company)
    # Dedupe preserving order
    seen: set[str] = set()
    out: List[str] = []
    for a in aliases:
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def run(
    company: str,
    entity_record: Optional[Dict[str, Any]] = None,
    timespan: str = "90day",
    max_records: int = 50,
) -> Dict[str, Any]:
    """Fetch + score GDELT events. Returns decision-grade dict."""
    aliases = _build_aliases(company, entity_record)
    out: Dict[str, Any] = {
        "agent":              "gdelt_events",
        "company":             company,
        "timespan":            timespan,
        "aliases_queried":     aliases,
        "events":              [],
        "summary":             {},
        "decay_weighted_intensity": 0.0,
        "ledger_delta":        0.0,
        "ledger_bucket":       "gdelt_adverse_event_intensity",
        "status":              "NO_EVENTS",
        "rationale":           "",
        "source":              "gdelt-2.0-doc",
    }
    if not aliases:
        out["rationale"] = "No company aliases available — skipping GDELT query."
        return out

    try:
        events = fetch_events(aliases, timespan=timespan, max_records=max_records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("GDELT fetch_events failed for %s: %s", company, exc)
        out["status"] = "ERROR"
        out["rationale"] = f"GDELT API call failed: {str(exc)[:160]}"
        return out

    if not events:
        out["rationale"] = (
            "GDELT returned zero adverse events for this company × ESG theme "
            f"in the last {timespan}."
        )
        return out

    intensity = decay_weighted_intensity(events)
    out["events"] = [e.to_dict() for e in events]
    out["summary"] = summarise(events)
    out["decay_weighted_intensity"] = intensity

    # Map decay intensity to ledger delta. Empirical thresholds:
    #   intensity > 2.0 -> heavy adverse coverage (+6 GW pts)
    #   intensity > 1.0 -> moderate adverse coverage (+3 GW pts)
    #   intensity > 0.3 -> mild adverse coverage (+1 GW pts)
    #   else -> no penalty
    if intensity > 2.0:
        out["ledger_delta"] = 6.0
        out["status"] = "HEAVY_ADVERSE_COVERAGE"
    elif intensity > 1.0:
        out["ledger_delta"] = 3.0
        out["status"] = "MODERATE_ADVERSE_COVERAGE"
    elif intensity > 0.3:
        out["ledger_delta"] = 1.0
        out["status"] = "MILD_ADVERSE_COVERAGE"
    else:
        out["status"] = "ROUTINE"

    out["rationale"] = (
        f"{len(events)} adverse ESG events in last {timespan}; "
        f"decay-weighted intensity {intensity:.2f}; "
        f"top tone bands: {out['summary'].get('by_tone_band')}."
    )
    return out


def build_ledger_row(gdelt_output: Dict[str, Any]) -> Dict[str, Any]:
    """Render GDELT output into a scoremodifierledger row."""
    delta = float(gdelt_output.get("ledger_delta") or 0.0)
    if abs(delta) < 0.01:
        return {}
    return {
        "bucket":       gdelt_output.get("ledger_bucket", "gdelt_adverse_event_intensity"),
        "source":       "gdelt_event_stream",
        "delta":        delta,
        "direction":    "increases_gw_risk",
        "rationale":    gdelt_output.get("rationale", ""),
        "evidence_source": "GDELT Project 2.0 (https://gdeltproject.org)",
        "evidence_url":    "https://api.gdeltproject.org/api/v2/doc/doc",
        "event_count":     len(gdelt_output.get("events") or []),
        "decay_weighted_intensity": gdelt_output.get("decay_weighted_intensity"),
        "status":          gdelt_output.get("status"),
    }
