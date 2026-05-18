"""Regulatory cross-ref agent — joins EPA ECHO fines × SEC EDGAR env capex.

Integrity signal: when violations / fines exceed disclosed environmental
capex by a meaningful ratio, that's prima facie evidence of under-investment
in compliance / "pay to pollute" behaviour.

Decision-grade output schema:
  status         IN_ENGAGED | NOT_APPLICABLE | NO_DATA
  fines_total_usd, env_capex_total_usd, ratio (fines/capex)
  integrity_flag  WORSE_THAN_PEER | NORMAL | BETTER_THAN_PEER
  ledger_delta   {+5, 0, -2}
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def run(
    company: str,
    industry: Optional[str],
    entity_record: Optional[Dict[str, Any]] = None,
    ticker: Optional[str] = None,
) -> Dict[str, Any]:
    """Pull ECHO violations + EDGAR env capex, compute integrity signal."""
    out: Dict[str, Any] = {
        "agent":             "regulatory_cross_ref",
        "company":           company,
        "industry":          industry,
        "status":            "NOT_APPLICABLE",
        "rationale":         "",
        "epa_violations":    [],
        "epa_summary":       {},
        "edgar_env_signal":  {},
        "fines_total_usd":   0.0,
        "env_capex_total_usd": 0.0,
        "ratio_fines_over_capex": None,
        "integrity_flag":    "NORMAL",
        "ledger_delta":      0.0,
        "ledger_bucket":     "regulatory_cross_ref",
        "source":            "epa_echo+edgar_xbrl",
    }

    country = (entity_record or {}).get("country_iso3") if entity_record else None
    if country != "USA":
        out["rationale"] = (
            f"Company jurisdiction {country!r} is not USA — "
            "EPA ECHO + EDGAR XBRL are US-only sources."
        )
        return out

    # Pull EPA violations
    epa_unavailable = False
    try:
        from data_sources.epa_echo import (
            facility_search, facility_history, summarise_violations,
            EpaEchoUnavailable,
        )
        try:
            facilities = facility_search(company, max_results=10)
        except EpaEchoUnavailable as exc:
            epa_unavailable = True
            logger.info("EPA ECHO endpoint unavailable: %s", exc)
            facilities = []
        all_violations = []
        if not epa_unavailable:
            for f in facilities[:5]:
                try:
                    all_violations.extend(facility_history(f.registry_id))
                except EpaEchoUnavailable:
                    epa_unavailable = True
                    break
                except Exception as e:
                    logger.debug("ECHO history fail for %s: %s", f.registry_id, e)
        epa_summary = summarise_violations(all_violations)
        out["epa_violations"] = [v.to_dict() for v in all_violations[:50]]
        out["epa_summary"] = epa_summary
        if epa_unavailable:
            # Critical: do NOT default to 0.0 when the API is dead. Mark
            # as None so the downstream integrity classifier surfaces
            # UNAVAILABLE rather than awarding a false BETTER_THAN_PEER
            # credit on the basis of an unreachable endpoint.
            out["fines_total_usd"] = None
            out["epa_summary"] = {"status": "ENDPOINT_UNAVAILABLE",
                                  "note": "EPA ECHO REST API endpoint is deprecated/unreachable; fines count UNKNOWN."}
        else:
            out["fines_total_usd"] = epa_summary.get("total_fines_usd", 0.0)
    except Exception as exc:
        logger.warning("EPA ECHO call failed: %s", exc)
        out["epa_summary"] = {"error": str(exc)[:160]}
        out["fines_total_usd"] = None
        epa_unavailable = True

    # Pull EDGAR env capex (need ticker)
    try:
        from data_sources.edgar_xbrl import cik_for_ticker, environmental_capex_signal
        cik = cik_for_ticker(ticker) if ticker else None
        if not cik:
            # Try to infer ticker from company name via simple lookups
            from core.entity_resolver import resolve
            rec = resolve(company)
            if rec:
                # Try common aliases as tickers
                for a in (rec.aliases or ()):
                    cik = cik_for_ticker(a)
                    if cik:
                        break
        if cik:
            env_signal = environmental_capex_signal(cik, last_n_years=3)
            out["edgar_env_signal"] = env_signal
            if env_signal.get("available"):
                totals_by_year = env_signal.get("totals_by_year") or {}
                out["env_capex_total_usd"] = sum(totals_by_year.values()) or 0.0
    except Exception as exc:
        logger.warning("EDGAR call failed: %s", exc)
        out["edgar_env_signal"] = {"error": str(exc)[:160]}

    # Decide integrity signal. CRITICAL: when EPA fines are UNKNOWN
    # (endpoint unavailable), do NOT compute a ratio and do NOT award
    # the BETTER_THAN_PEER credit — the absence of evidence is not
    # evidence of absence.
    fines_raw = out["fines_total_usd"]
    capex = out["env_capex_total_usd"] or 0.0
    if epa_unavailable or fines_raw is None:
        out["integrity_flag"] = "UNKNOWN"
        out["ledger_delta"] = 0.0
        out["status"] = "EPA_UNAVAILABLE"
        out["rationale"] = (
            "EPA ECHO REST endpoint unavailable — fines count UNKNOWN. "
            "EDGAR environmental capex disclosed: "
            f"USD {capex:,.0f}. Integrity flag suppressed (no ledger credit "
            "applied without EPA verification)."
        )
        return out
    fines = fines_raw or 0.0
    if capex > 0:
        ratio = fines / capex
        out["ratio_fines_over_capex"] = round(ratio, 3)
        if ratio > 0.50:
            out["integrity_flag"] = "WORSE_THAN_PEER"
            out["ledger_delta"] = 5.0
        elif ratio > 0.15:
            out["integrity_flag"] = "NORMAL"
            out["ledger_delta"] = 0.0
        else:
            out["integrity_flag"] = "BETTER_THAN_PEER"
            out["ledger_delta"] = -2.0
    elif fines > 1e6:  # > $1M fines but no disclosed env capex
        out["integrity_flag"] = "WORSE_THAN_PEER"
        out["ledger_delta"] = 5.0
        out["rationale"] = (
            f"USD {fines:,.0f} EPA fines disclosed without corresponding "
            "environmental remediation expense in 10-K XBRL data."
        )
    elif fines == 0 and capex == 0:
        out["status"] = "NO_DATA"
        out["rationale"] = "No EPA violations and no EDGAR environmental capex disclosure found."
        return out

    if not out.get("rationale"):
        out["rationale"] = (
            f"EPA fines USD {fines:,.0f} vs disclosed environmental capex "
            f"USD {capex:,.0f}; ratio={out.get('ratio_fines_over_capex')}; "
            f"flag={out['integrity_flag']}."
        )
    out["status"] = "IN_ENGAGED"
    return out


def build_ledger_row(cr_out: Dict[str, Any]) -> Dict[str, Any]:
    delta = float(cr_out.get("ledger_delta") or 0.0)
    if abs(delta) < 0.01:
        return {}
    return {
        "bucket":          cr_out.get("ledger_bucket", "regulatory_cross_ref"),
        "source":          "epa_echo+edgar_xbrl",
        "delta":           delta,
        "direction":       "increases_gw_risk" if delta > 0 else "decreases_gw_risk",
        "rationale":       cr_out.get("rationale", ""),
        "evidence_source": "EPA ECHO (https://echo.epa.gov) + SEC EDGAR XBRL (data.sec.gov)",
        "evidence_url":    "https://echo.epa.gov",
        "fines_total_usd": cr_out.get("fines_total_usd"),
        "env_capex_total_usd": cr_out.get("env_capex_total_usd"),
        "ratio":           cr_out.get("ratio_fines_over_capex"),
        "integrity_flag":  cr_out.get("integrity_flag"),
    }
