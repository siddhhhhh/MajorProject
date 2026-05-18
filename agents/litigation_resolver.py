"""Litigation resolver — real docket status (ACTIVE/SETTLED/DISMISSED) from
CourtListener (US) + Indian Kanoon (IN). Replaces today's pattern-match.

Replaces the flat "active enforcement count" — which today over-penalises
companies whose enforcement matters have already settled — with a weighted
intensity that respects status + recency.

State entry: state["litigation_resolved"]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ACTIVE_WEIGHT = 1.0      # full weight
_SETTLED_WEIGHT_BASE = 0.5  # half weight, additional recency multiplier
_DISMISSED_WEIGHT = 0.0   # dismissed = zero (current flat counter penalises this)

# Per-case maximum GW points (cap on a single docket's contribution)
_MAX_PER_CASE = 10.0
# Cap on total ledger contribution from this source
_TOTAL_CAP = 25.0


def _years_since(date_str: Optional[str], ref: Optional[datetime] = None) -> Optional[float]:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(str(date_str)[:10])
        ref_dt = ref or datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (ref_dt - dt).total_seconds() / (86400 * 365.25)
    except Exception:
        return None


def _settled_recency_multiplier(years_old: Optional[float]) -> float:
    """SETTLED cases >2yr old fade rapidly; recent settlements still bite."""
    if years_old is None:
        return 0.5
    if years_old <= 1.0:
        return 1.0
    if years_old <= 2.0:
        return 0.7
    if years_old <= 4.0:
        return 0.4
    return 0.15


def run(
    company: str,
    entity_record: Optional[Dict[str, Any]] = None,
    since_year: Optional[int] = None,
) -> Dict[str, Any]:
    """Run both US + IN docket searches, classify status, compute intensity."""
    aliases: List[str] = [company]
    if entity_record:
        cn = entity_record.get("canonical_name")
        if cn and cn not in aliases:
            aliases.append(cn)
        aliases.extend(entity_record.get("aliases") or [])
    aliases = [a for a in aliases if a]

    country = (entity_record or {}).get("country_iso3") if entity_record else None

    out: Dict[str, Any] = {
        "agent":              "litigation_resolver",
        "company":            company,
        "aliases_queried":    aliases,
        "us_cases":           [],
        "in_cases":           [],
        "status_counts":      {"ACTIVE": 0, "SETTLED": 0, "DISMISSED": 0},
        "monetary_penalty_total_usd": 0.0,
        "weighted_intensity": 0.0,
        "ledger_delta":       0.0,
        "ledger_bucket":      "litigation_intensity",
        "status":             "NO_CASES",
        "source":             "courtlistener+indian_kanoon",
        "rationale":          "",
    }

    # US-side: skip for purely Indian companies (CourtListener is US-federal)
    if country != "IND":
        try:
            from data_sources.courtlistener import search_cases as _cl
            cases = _cl(aliases, since_year=since_year or 2018, max_results=20)
            out["us_cases"] = [c.to_dict() for c in cases]
        except Exception as exc:
            logger.warning("CourtListener call failed: %s", exc)

    # IN-side: run for IND, also for global companies as backup
    try:
        from data_sources.indian_kanoon import search_cases as _ik
        ik_cases = _ik(aliases, esg_terms=["pollution", "environment", "compliance", "violation"], max_results=15)
        out["in_cases"] = [c.to_dict() for c in ik_cases]
    except Exception as exc:
        logger.warning("Indian Kanoon call failed: %s", exc)

    all_cases = out["us_cases"] + out["in_cases"]
    if not all_cases:
        out["rationale"] = "No ESG-related dockets found in either CourtListener or Indian Kanoon."
        return out

    # Aggregate
    intensity = 0.0
    total_penalty = 0.0
    counts = out["status_counts"]
    for c in all_cases:
        s = c.get("status") or "ACTIVE"
        counts[s] = counts.get(s, 0) + 1
        # Per-case contribution
        if s == "ACTIVE":
            w = _ACTIVE_WEIGHT
        elif s == "SETTLED":
            yrs = _years_since(c.get("terminated_date") or c.get("decision_date"))
            w = _SETTLED_WEIGHT_BASE * _settled_recency_multiplier(yrs)
        else:  # DISMISSED
            w = _DISMISSED_WEIGHT
        # Each active case worth 6 pts cap; cumulative capped at _TOTAL_CAP
        per_case_pts = min(_MAX_PER_CASE, w * 6.0)
        intensity += per_case_pts
        mp = c.get("monetary_penalty_usd")
        if isinstance(mp, (int, float)):
            total_penalty += float(mp)

    intensity = min(_TOTAL_CAP, round(intensity, 1))
    out["weighted_intensity"] = intensity
    out["monetary_penalty_total_usd"] = total_penalty

    if intensity >= 15.0:
        out["status"] = "HEAVY_LITIGATION"
        out["ledger_delta"] = 12.0
    elif intensity >= 7.0:
        out["status"] = "MODERATE_LITIGATION"
        out["ledger_delta"] = 6.0
    elif intensity >= 1.0:
        out["status"] = "LIGHT_LITIGATION"
        out["ledger_delta"] = 2.0
    else:
        out["status"] = "ROUTINE"
        out["ledger_delta"] = 0.0

    out["rationale"] = (
        f"{counts.get('ACTIVE', 0)} active, "
        f"{counts.get('SETTLED', 0)} settled, "
        f"{counts.get('DISMISSED', 0)} dismissed cases; "
        f"weighted intensity {intensity:.1f}; "
        f"total monetary mentions ${total_penalty:,.0f}."
    )
    return out


def build_ledger_row(litigation_out: Dict[str, Any]) -> Dict[str, Any]:
    delta = float(litigation_out.get("ledger_delta") or 0.0)
    if abs(delta) < 0.01:
        return {}
    return {
        "bucket":          litigation_out.get("ledger_bucket", "litigation_intensity"),
        "source":          "litigation_resolver",
        "delta":           delta,
        "direction":       "increases_gw_risk",
        "rationale":       litigation_out.get("rationale", ""),
        "evidence_source": "CourtListener + Indian Kanoon",
        "evidence_url":    "https://www.courtlistener.com",
        "status":          litigation_out.get("status"),
        "active_count":    (litigation_out.get("status_counts") or {}).get("ACTIVE", 0),
        "settled_count":   (litigation_out.get("status_counts") or {}).get("SETTLED", 0),
        "dismissed_count": (litigation_out.get("status_counts") or {}).get("DISMISSED", 0),
    }
