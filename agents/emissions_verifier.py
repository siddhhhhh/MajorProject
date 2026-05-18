"""Emissions verifier — compares disclosed Scope 1 vs Climate TRACE ground truth.

Three-tier verdict, easiest to hardest:

  CONSISTENT       — disclosed and observed within 0.5x – 2.0x band
  INFLATION_FLAG   — disclosed > 2x observed AND > 2x sector ceiling
  UNDERREPORT_FLAG — disclosed < 0.5x observed
  PARTIAL_COVERAGE — Climate TRACE has only a subset of company assets;
                     comparison is informational, not flagged
  NOT_APPLICABLE   — disclosed missing, or industry is finance/services
                     (Climate TRACE has no coverage for Scope 1 there)
  NOT_COVERED      — country/industry combination not in Climate TRACE

The output is decision-grade JSON-safe and meant to flow straight into the
report's Section 8C plus the scoremodifierledger as a `emissions_verification`
bucket.

The agent runs purely on local data + one Climate TRACE HTTP call — no LLM.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from data_sources.climate_trace import (
    INDUSTRY_SECTOR_MAP,
    attribution_string,
    get_company_emissions_snapshot,
    normalise_country,
)

logger = logging.getLogger(__name__)


# Industries where Climate TRACE has no/poor Scope 1 coverage — companies in
# these sectors emit indirectly (financed emissions, purchased electricity).
_NO_COVERAGE_INDUSTRIES = {
    "financial services", "banking", "finance", "asset management",
    "insurance", "technology", "software", "internet", "e-commerce",
    "retail", "consumer services", "media", "healthcare services",
    "pharmaceuticals", "biotech", "real estate", "telecommunications",
}


# Default jurisdiction inference from common company-name patterns. This
# does NOT replace explicit country/jurisdiction state; it's only a fallback.
_DEFAULT_COUNTRY_BY_COMPANY: Dict[str, str] = {
    "vedanta": "India",
    "reliance": "India",
    "tata": "India",
    "infosys": "India",
    "wipro": "India",
    "adani": "India",
    "ntpc": "India",
    "ongc": "India",
    "coal india": "India",
    "hindustan zinc": "India",
    "jsw": "India",
    "bp": "United Kingdom",
    "shell": "Netherlands",
    "totalenergies": "France",
    "exxonmobil": "United States",
    "chevron": "United States",
    "arcelormittal": "France",
    "volkswagen": "Germany",
    "siemens": "Germany",
    "saudi aramco": "Saudi Arabia",
    "petrobras": "Brazil",
    "sinopec": "China",
}


def _infer_country(company: str, state_country: Optional[str]) -> Optional[str]:
    """Resolve country to a string `normalise_country` can map to ISO-3.

    Accepts ISO-3 directly (passes through) or free-form name (e.g. "India").
    """
    if state_country:
        s = str(state_country).strip()
        # ISO-3 codes are 3 uppercase letters
        if len(s) == 3 and s.isupper() and s.isalpha():
            # Reverse lookup: ISO-3 -> name so normalise_country() can map back
            from data_sources.climate_trace import COUNTRY_ISO3 as _C
            for name, iso in _C.items():
                if iso == s:
                    return name
            # Fall through to direct pass — verifier will treat as unresolved
            return s
        return s
    s = (company or "").lower()
    for key, ctry in _DEFAULT_COUNTRY_BY_COMPANY.items():
        if key in s:
            return ctry
    return None


def _normalise_industry(ind: Optional[str]) -> str:
    return (ind or "").strip().lower()


def verify_emissions(
    company: str,
    industry: Optional[str],
    disclosed_scope1_tco2e: Optional[float],
    country: Optional[str] = None,
    year: int = 2024,
) -> Dict[str, Any]:
    """Run the full verification.

    Returns a JSON-safe dict — see module docstring for status taxonomy.
    """
    industry_lc = _normalise_industry(industry)
    country_resolved = _infer_country(company, country)
    out: Dict[str, Any] = {
        "agent": "emissions_verifier",
        "company": company,
        "industry": industry,
        "country": country_resolved,
        "year": year,
        "disclosed_scope1_tco2e": disclosed_scope1_tco2e,
        "observed_scope1_tco2e_assets": None,
        "observed_sector_total_tco2e": None,
        "ratio_disclosed_over_observed_assets": None,
        "ratio_disclosed_over_sector_total": None,
        "status": "NOT_APPLICABLE",
        "rationale": "",
        "matched_assets": [],
        "sector_aggregate": {},
        "country_total": None,
        "ledger_delta": 0.0,
        "ledger_bucket": "emissions_verification",
        "source": "climate-trace",
        "attribution": attribution_string(),
    }

    # ── Early outs ──
    if industry_lc in _NO_COVERAGE_INDUSTRIES:
        out["status"] = "NOT_APPLICABLE"
        out["rationale"] = (
            f"Climate TRACE does not track Scope 1 for {industry_lc} — "
            "emissions are financed/purchased, not directly emitted. Scope 3 "
            "(financed emissions) requires PCAF methodology, not satellite data."
        )
        return out

    if disclosed_scope1_tco2e is None or not isinstance(disclosed_scope1_tco2e, (int, float)):
        out["status"] = "NOT_APPLICABLE"
        out["rationale"] = "Disclosed Scope 1 missing — cannot compare."
        return out

    disclosed = float(disclosed_scope1_tco2e)
    if disclosed <= 0:
        out["status"] = "NOT_APPLICABLE"
        out["rationale"] = "Disclosed Scope 1 is zero or negative — cannot compare."
        return out

    if not country_resolved or not normalise_country(country_resolved):
        out["status"] = "NOT_COVERED"
        out["rationale"] = (
            "Company jurisdiction not resolved to an ISO-3 country code — "
            "Climate TRACE lookup requires a country filter."
        )
        return out

    # ── Pull Climate TRACE snapshot ──
    try:
        snap = get_company_emissions_snapshot(
            company=company, industry=industry, country=country_resolved, year=year,
        )
    except Exception as exc:  # noqa: BLE001 — verification is advisory
        logger.warning("Climate TRACE snapshot failed for %s: %s", company, exc)
        out["status"] = "NOT_COVERED"
        out["rationale"] = f"Climate TRACE lookup failed: {str(exc)[:120]}"
        return out

    out["matched_assets"] = snap["asset_level"]["matched_assets"]
    out["observed_scope1_tco2e_assets"] = snap["asset_level"]["total_tco2e"]
    out["sector_aggregate"] = snap["sector_aggregate"]
    out["country_total"] = snap["country_total"]
    out["sectors_targeted"] = snap["sectors_targeted"]

    asset_total = snap["asset_level"]["total_tco2e"]
    sector_total = sum(snap["sector_aggregate"].values()) if snap["sector_aggregate"] else 0.0
    out["observed_sector_total_tco2e"] = sector_total

    # ── Decide status ──
    # We prefer the asset-level comparison when curated assets exist;
    # otherwise we use the sector ceiling. The two thresholds are:
    #   asset-level: disclosed / asset_total
    #   sector-level: disclosed / sector_total (cap, not equality)
    if isinstance(asset_total, (int, float)) and asset_total > 0:
        ratio = disclosed / asset_total
        out["ratio_disclosed_over_observed_assets"] = round(ratio, 2)
        if ratio > 2.0:
            out["status"] = "INFLATION_FLAG"
            out["rationale"] = (
                f"Disclosed Scope 1 ({disclosed:,.0f} tCO2e) is "
                f"{ratio:.1f}x higher than Climate TRACE's satellite-derived "
                f"total for matched assets ({asset_total:,.0f} tCO2e across "
                f"{len(out['matched_assets'])} facilities). "
                "This is consistent with either a unit/scale error or "
                "deliberate inflation."
            )
        elif ratio < 0.5:
            out["status"] = "UNDERREPORT_FLAG"
            out["rationale"] = (
                f"Disclosed Scope 1 ({disclosed:,.0f} tCO2e) is "
                f"{ratio:.2f}x of Climate TRACE's satellite-derived total "
                f"({asset_total:,.0f} tCO2e). Likely scope gap — verify "
                "facility coverage and Scope 1 boundary."
            )
        else:
            out["status"] = "CONSISTENT"
            out["rationale"] = (
                f"Disclosed Scope 1 ({disclosed:,.0f} tCO2e) is "
                f"{ratio:.2f}x of Climate TRACE's satellite-derived total "
                f"({asset_total:,.0f} tCO2e) — within the 0.5x–2.0x "
                "tolerance band."
            )
    elif sector_total > 0:
        # No curated assets — use country-sector ceiling as a sanity cap.
        ratio = disclosed / sector_total
        out["ratio_disclosed_over_sector_total"] = round(ratio, 2)
        if ratio > 1.0:
            out["status"] = "INFLATION_FLAG"
            out["rationale"] = (
                f"Disclosed Scope 1 ({disclosed:,.0f} tCO2e) exceeds the "
                f"entire {snap['country_iso3']} sector total for "
                f"{', '.join(snap['sectors_targeted'])} "
                f"({sector_total:,.0f} tCO2e, {ratio:.1f}x). "
                "No single operator can emit more than its entire national sector."
            )
        elif ratio > 0.25:
            out["status"] = "PARTIAL_COVERAGE"
            out["rationale"] = (
                f"Disclosed Scope 1 ({disclosed:,.0f} tCO2e) represents "
                f"{ratio*100:.0f}% of the entire {snap['country_iso3']} sector "
                f"total. Plausible only if the company is dominant. "
                "No curated asset list available for direct facility match."
            )
        else:
            out["status"] = "CONSISTENT"
            out["rationale"] = (
                f"Disclosed Scope 1 ({disclosed:,.0f} tCO2e) is "
                f"{ratio*100:.1f}% of the national sector total "
                f"({sector_total:,.0f} tCO2e). Plausible upper bound."
            )
    else:
        out["status"] = "NOT_COVERED"
        out["rationale"] = (
            f"Climate TRACE has no asset-level or sector-aggregate data for "
            f"{country_resolved} × {industry or 'unknown industry'}."
        )

    # ── Ledger delta: structural penalty/credit on the headline GW score ──
    # INFLATION_FLAG: +12 GW points (raises greenwashing risk significantly)
    # UNDERREPORT_FLAG: +6 GW points (still a disclosure quality issue, milder)
    # PARTIAL_COVERAGE: 0 (informational only)
    # CONSISTENT: -4 GW points (small credit for matching satellite data)
    delta_map = {
        "INFLATION_FLAG": 12.0,
        "UNDERREPORT_FLAG": 6.0,
        "CONSISTENT": -4.0,
        "PARTIAL_COVERAGE": 0.0,
        "NOT_APPLICABLE": 0.0,
        "NOT_COVERED": 0.0,
    }
    out["ledger_delta"] = delta_map.get(out["status"], 0.0)

    return out


def build_ledger_row(verifier_output: Dict[str, Any]) -> Dict[str, Any]:
    """Render the verifier dict into a scoremodifierledger row.

    Empty dict when no ledger impact — caller should skip appending.
    """
    delta = float(verifier_output.get("ledger_delta") or 0.0)
    if abs(delta) < 0.01:
        return {}
    return {
        "bucket": verifier_output.get("ledger_bucket", "emissions_verification"),
        "source": "climate_trace_verifier",
        "delta": delta,
        "direction": "increases_gw_risk" if delta > 0 else "decreases_gw_risk",
        "rationale": verifier_output.get("rationale", ""),
        "evidence_source": "Climate TRACE satellite-derived emissions",
        "evidence_url": "https://climatetrace.org",
        "status": verifier_output.get("status"),
        "disclosed_scope1_tco2e": verifier_output.get("disclosed_scope1_tco2e"),
        "observed_assets_tco2e": verifier_output.get("observed_scope1_tco2e_assets"),
        "observed_sector_tco2e": verifier_output.get("observed_sector_total_tco2e"),
    }
