"""Subsidiary walker — corporate-tree traversal + Climate TRACE per-subsidiary lookups.

Why: 70% of greenwashing hides at subsidiary level. The parent claims net-zero
while the subsidiary burns coal. This module produces a per-subsidiary
emissions footprint and computes a `subsidiary_coverage_score` indicating
whether the parent's disclosure plausibly reflects group-wide reality.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def run(
    company: str,
    entity_record: Optional[Dict[str, Any]] = None,
    max_subsidiaries: int = 10,
) -> Dict[str, Any]:
    """Walk subsidiaries and aggregate emissions footprint."""
    out: Dict[str, Any] = {
        "agent":                "subsidiary_walker",
        "company":              company,
        "parent_lei":           (entity_record or {}).get("lei"),
        "subsidiaries":         [],
        "total_subsidiary_emissions_tco2e": 0.0,
        "subsidiary_coverage_score": None,
        "status":               "NO_SUBSIDIARIES",
        "ledger_delta":         0.0,
        "ledger_bucket":        "subsidiary_coverage",
        "rationale":            "",
        "source":               "gleif+climate_trace",
    }

    lei = (entity_record or {}).get("lei")
    if not lei:
        out["rationale"] = "No parent LEI resolved — subsidiary walk skipped."
        return out

    from data_sources.gleif import subsidiaries_of
    subs = subsidiaries_of(lei)
    if not subs:
        out["rationale"] = (
            f"No curated subsidiaries for parent LEI {lei}. "
            "Extend data_sources/gleif._PARENT_SUBSIDIARIES to add coverage."
        )
        return out

    # Per-subsidiary Climate TRACE lookup
    from data_sources.climate_trace import get_company_emissions_snapshot

    rows: List[Dict[str, Any]] = []
    total_emissions = 0.0
    for sub in subs[:max_subsidiaries]:
        sub_d = sub.to_dict()
        # Map ISO3 -> country name for Climate TRACE lookup
        from data_sources.climate_trace import COUNTRY_ISO3
        country_name = None
        for name, iso in COUNTRY_ISO3.items():
            if iso == sub.country_iso3:
                country_name = name
                break
        try:
            snap = get_company_emissions_snapshot(
                company=sub.subsidiary_name,
                industry=sub.sector_hint,
                country=country_name,
                year=2024,
            )
            asset_total = (snap.get("asset_level") or {}).get("total_tco2e") or 0.0
            sector_aggregate = snap.get("sector_aggregate") or {}
            # When asset match fails, use sector total / N as a rough proxy
            estimate_basis = "asset_level"
            estimate = asset_total
            if not asset_total and sector_aggregate:
                # Conservative proxy: 5% of national sector total
                estimate = sum(sector_aggregate.values()) * 0.05
                estimate_basis = "sector_share_proxy"
            sub_d.update({
                "estimated_emissions_tco2e": round(estimate, 0) if estimate else 0,
                "estimate_basis":            estimate_basis,
                "matched_assets":            len(snap.get("asset_level", {}).get("matched_assets") or []),
            })
            total_emissions += estimate
        except Exception as exc:
            logger.warning("subsidiary lookup failed for %s: %s", sub.subsidiary_name, exc)
            sub_d.update({
                "estimated_emissions_tco2e": 0,
                "estimate_basis":            "lookup_failed",
                "error":                     str(exc)[:160],
            })
        rows.append(sub_d)

    out["subsidiaries"] = rows
    out["total_subsidiary_emissions_tco2e"] = round(total_emissions, 0)

    # Subsidiary coverage score: ratio of subsidiaries with asset-level
    # Climate TRACE matches to total subsidiaries. Higher = better disclosure
    # likely (parent's data covers more of the group).
    matched = sum(1 for r in rows if r.get("estimate_basis") == "asset_level"
                  and r.get("estimated_emissions_tco2e", 0) > 0)
    cov_score = round(matched / len(rows) * 100, 1) if rows else 0.0
    out["subsidiary_coverage_score"] = cov_score

    # Status + ledger delta
    if cov_score < 25.0 and total_emissions > 1e6:
        # Many unverified subsidiaries with material emissions exposure
        out["status"] = "POOR_COVERAGE_HIGH_EXPOSURE"
        out["ledger_delta"] = 5.0
    elif cov_score < 25.0:
        out["status"] = "POOR_COVERAGE"
        out["ledger_delta"] = 2.0
    elif cov_score < 60.0:
        out["status"] = "PARTIAL_COVERAGE"
        out["ledger_delta"] = 1.0
    else:
        out["status"] = "GOOD_COVERAGE"
        out["ledger_delta"] = -1.0

    out["rationale"] = (
        f"{len(rows)} subsidiaries walked; "
        f"coverage score {cov_score:.1f}%; "
        f"aggregate subsidiary emissions ~{total_emissions/1e6:.1f} MtCO2e."
    )
    return out


def build_ledger_row(walker_out: Dict[str, Any]) -> Dict[str, Any]:
    delta = float(walker_out.get("ledger_delta") or 0.0)
    if abs(delta) < 0.01:
        return {}
    return {
        "bucket":          walker_out.get("ledger_bucket", "subsidiary_coverage"),
        "source":          "subsidiary_walker",
        "delta":           delta,
        "direction":       "increases_gw_risk" if delta > 0 else "decreases_gw_risk",
        "rationale":       walker_out.get("rationale", ""),
        "evidence_source": "GLEIF + Climate TRACE",
        "evidence_url":    "https://www.gleif.org",
        "subsidiary_count": len(walker_out.get("subsidiaries") or []),
        "coverage_score":  walker_out.get("subsidiary_coverage_score"),
        "total_subsidiary_emissions_tco2e": walker_out.get("total_subsidiary_emissions_tco2e"),
        "status":          walker_out.get("status"),
    }
