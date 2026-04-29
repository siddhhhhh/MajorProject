"""
core/institutional_verifier.py
-------------------------------
Institutional-Grade ESG Verification Engine (v1.0)

Implements the 10-rule framework:
  1. Dual-source data priority
  2. Four-tier source hierarchy
  3. Per-claim verification engine (Verified / Partially Verified / Unverified)
  4. Multi-provider cross-check & rating divergence detection
  5. Missing-data handling (unknown, not zero)
  6. Confidence-driven abstention (<60% → ABSTAIN)
  7. Carbon / climate validation
  8. Temporal consistency
  9. Controversy integration
  10. Final output with evidence + confidence + source breakdown

This module is called from risk_scoring_node and verdict_generation_node
after the existing scoring pipeline has populated ESGState.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RULE 2 – Source Tier Definitions
# ---------------------------------------------------------------------------
TIER_1_DOMAINS = {
    "sec.gov", "sebi.gov.in", "gov.uk", "europa.eu", "companieshouse.gov.uk",
    "mca.gov.in", "bseindia.com", "nseindia.com", "greentribunal.gov.in",
    "eur-lex.europa.eu", "federalregister.gov",
}
TIER_2_DOMAINS = {
    "msci.com", "sustainalytics.com", "spglobal.com", "moodys.com",
    "cdp.net", "sbti.org", "sciencebasedtargets.org", "wba.earth",
    "bloomberg.com", "refinitiv.com", "iss-esg.com",
}
TIER_3_DOMAINS = {
    "reuters.com", "ft.com", "wsj.com", "nytimes.com", "theguardian.com",
    "cnbc.com", "bbc.com", "apnews.com", "bloomberg.com", "businesswire.com",
    "prnewswire.com", "wri.org", "influencemap.org", "clientearth.org",
}

def _domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(str(url or "")).netloc.replace("www.", "").lower()


def get_source_tier(evidence_item: Dict[str, Any]) -> int:
    """Return 1-4 tier for a single evidence record."""
    url = str(evidence_item.get("url") or evidence_item.get("source_url") or "")
    src_type = str(evidence_item.get("source_type") or "").lower()
    dom = _domain(url)

    # Explicit source_type hints
    if any(t in src_type for t in ("regulatory", "sec", "government", "legal")):
        return 1
    if any(t in src_type for t in ("esg rating", "cdp", "verified esg", "sustainalytics", "msci")):
        return 2
    if any(t in src_type for t in ("major news", "tier-1", "reuters", "bloomberg")):
        return 3

    # Domain matching
    if any(d in dom for d in TIER_1_DOMAINS):
        return 1
    if any(d in dom for d in TIER_2_DOMAINS):
        return 2
    if any(d in dom for d in TIER_3_DOMAINS):
        return 3
    return 4


# ---------------------------------------------------------------------------
# RULE 1 + 3 – Per-Claim Verification Status
# ---------------------------------------------------------------------------

def verify_claim(
    claim_text: str,
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    For a single claim, evaluate:
      - Supporting evidence count by tier
      - Contradicting evidence count
      - Verification status: Verified / Partially Verified / Unverified / Contradicted
    """
    supporting: List[Dict] = []
    contradicting: List[Dict] = []
    neutral: List[Dict] = []

    for e in evidence:
        stance = str(e.get("stance") or e.get("relationship_to_claim") or "").lower()
        if "contradict" in stance or "opposes" in stance:
            contradicting.append(e)
        elif "support" in stance or "confirms" in stance:
            supporting.append(e)
        else:
            neutral.append(e)

    # Count by tier for supporting evidence
    tier_counts: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    for e in supporting:
        t = get_source_tier(e)
        tier_counts[t] = tier_counts.get(t, 0) + 1

    strong_support = tier_counts[1] + tier_counts[2]  # Tier 1+2 = strong
    total_support = len(supporting)
    total_contradict = len(contradicting)

    # RULE 3 – Assign verification status
    if total_contradict > total_support:
        status = "CONTRADICTED"
    elif strong_support >= 2:
        status = "VERIFIED"
    elif strong_support >= 1 or total_support >= 2:
        status = "PARTIALLY_VERIFIED"
    elif total_support == 0 and total_contradict == 0:
        status = "UNVERIFIED"
    else:
        status = "PARTIALLY_VERIFIED"

    # RULE 2 – Reject Tier-4-only conclusions
    tier4_only = all(get_source_tier(e) == 4 for e in supporting) and strong_support == 0
    if tier4_only and total_support > 0:
        status = "UNVERIFIED"
        tier4_only_flag = True
    else:
        tier4_only_flag = False

    return {
        "status": status,
        "supporting_count": total_support,
        "contradicting_count": total_contradict,
        "neutral_count": len(neutral),
        "tier_breakdown": tier_counts,
        "strong_support_count": strong_support,
        "tier4_only": tier4_only_flag,
        "top_supporting_sources": [
            e.get("source_name") or _domain(e.get("url", ""))
            for e in supporting[:3]
        ],
        "top_contradicting_sources": [
            e.get("source_name") or _domain(e.get("url", ""))
            for e in contradicting[:3]
        ],
    }


# ---------------------------------------------------------------------------
# RULE 4 – Multi-Provider Cross-Check & Rating Divergence
# ---------------------------------------------------------------------------

_RATING_TO_SCORE = {
    "AAA": 95, "AA": 87, "A": 79, "BBB": 67, "BB": 54, "B": 42, "CCC": 20,
    "LEADER": 85, "AVERAGE": 50, "LAGGARD": 25,
    "LOW": 20, "MEDIUM": 50, "HIGH": 75, "SEVERE": 90,
}

def _normalise_rating(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        val = float(raw)
        # If it looks like 0-1 scale, convert
        return val * 100 if val <= 1.0 else min(100.0, val)
    upper = str(raw).strip().upper()
    return float(_RATING_TO_SCORE[upper]) if upper in _RATING_TO_SCORE else None


def check_rating_divergence(
    external_benchmarks: Dict[str, Any],
    internal_esg_score: float,
) -> Dict[str, Any]:
    """
    RULE 4: Compare scores across MSCI, Sustainalytics, S&P/Bloomberg.
    Flag divergence if spread > 25 points.
    """
    providers: Dict[str, float] = {}
    scores_block = external_benchmarks.get("scores", {}) if isinstance(external_benchmarks, dict) else {}

    # Map known keys
    for key, label in [
        ("msci_esg_score", "MSCI"),
        ("sustainalytics_score", "Sustainalytics"),
        ("sp_esg_score", "S&P"),
        ("bloomberg_esg_score", "Bloomberg"),
        ("esg_score", "External_Generic"),
    ]:
        raw = scores_block.get(key) or external_benchmarks.get(key)
        norm = _normalise_rating(raw)
        if norm is not None:
            providers[label] = norm

    # Also include internal score
    providers["ESGLens_Internal"] = round(float(internal_esg_score or 0), 1)

    if len(providers) < 2:
        return {
            "divergence_detected": False,
            "providers_available": list(providers.keys()),
            "provider_scores": providers,
            "note": "Insufficient external provider data for cross-check.",
        }

    score_values = list(providers.values())
    spread = max(score_values) - min(score_values)
    divergence_threshold = 25.0

    return {
        "divergence_detected": spread > divergence_threshold,
        "spread_points": round(spread, 1),
        "providers_available": list(providers.keys()),
        "provider_scores": providers,
        "divergence_threshold": divergence_threshold,
        "note": (
            f"RATING DIVERGENCE RISK: {spread:.1f}-point spread across providers."
            if spread > divergence_threshold
            else f"Provider scores within acceptable range ({spread:.1f} pts spread)."
        ),
    }


# ---------------------------------------------------------------------------
# RULE 5 – Missing Data Handler
# ---------------------------------------------------------------------------

def flag_missing_data(carbon_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    RULE 5: Missing fields = 'unknown', not 0. Returns a completeness report.
    """
    fields = {
        "scope1": "Scope 1 Direct Emissions",
        "scope2": "Scope 2 Energy Indirect",
        "scope3": "Scope 3 Value Chain",
        "net_zero_target": "Net-Zero Target Year",
        "sbti_status": "SBTi Validation Status",
        "renewable_pct": "Renewable Energy %",
    }
    missing = []
    present = []

    for key, label in fields.items():
        val = carbon_data.get(key)
        if val is None or val == "" or val == 0:
            missing.append({"field": key, "label": label, "value": "UNKNOWN"})
        else:
            present.append({"field": key, "label": label, "value": val})

    completeness_pct = round(len(present) / len(fields) * 100, 1)

    return {
        "completeness_pct": completeness_pct,
        "missing_fields": missing,
        "present_fields": present,
        "missing_count": len(missing),
        "confidence_penalty_pct": min(30, len(missing) * 5),  # up to -30% confidence
    }


# ---------------------------------------------------------------------------
# RULE 6 – Confidence-Driven Abstention
# ---------------------------------------------------------------------------

def should_abstain(
    confidence_pct: float,
    verification_result: Dict[str, Any],
    rating_divergence: Dict[str, Any],
    missing_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    RULE 6: If confidence < 60% → MUST abstain.
    If evidence conflicting → downgrade risk.
    """
    reasons: List[str] = []

    if confidence_pct < 60:
        reasons.append(f"Confidence {confidence_pct:.1f}% is below the 60% decision threshold.")

    if verification_result.get("status") == "UNVERIFIED":
        reasons.append("Claim is UNVERIFIED — insufficient strong-source evidence.")

    if verification_result.get("tier4_only"):
        reasons.append("All supporting evidence is Tier 4 only — conclusions rejected.")

    if rating_divergence.get("divergence_detected"):
        reasons.append(f"Rating divergence risk: {rating_divergence.get('note')}")

    if missing_data.get("completeness_pct", 100) < 40:
        reasons.append(f"Carbon data completeness only {missing_data['completeness_pct']}% — too many unknowns.")

    abstain = len(reasons) > 0 and confidence_pct < 60
    downgrade = (
        verification_result.get("contradicting_count", 0) > verification_result.get("supporting_count", 0)
    )

    return {
        "abstain": abstain,
        "abstain_reasons": reasons,
        "downgrade_risk_level": downgrade,
        "decision": "INSUFFICIENT EVIDENCE — NO DECISION" if abstain else "PROCEED",
    }


# ---------------------------------------------------------------------------
# RULE 7 – Carbon & Climate Validation
# ---------------------------------------------------------------------------

def validate_carbon_claims(
    carbon_data: Dict[str, Any],
    pathway_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    RULE 7: Validate Scope 1/2/3, SBTi status, net-zero pathway alignment.
    """
    findings: List[str] = []
    flags: List[str] = []

    scope1 = carbon_data.get("scope1")
    scope2 = carbon_data.get("scope2")
    scope3 = carbon_data.get("scope3")
    sbti = str(carbon_data.get("sbti_status") or "").lower()
    nzt = carbon_data.get("net_zero_target")
    alignment = str((pathway_data or {}).get("alignment_status") or "").lower()

    if scope1 is None:
        flags.append("MISSING_SCOPE1")
    if scope2 is None:
        flags.append("MISSING_SCOPE2")
    if scope3 is None:
        flags.append("MISSING_SCOPE3")
        findings.append("Scope 3 not disclosed — value chain emissions unknown.")

    if "committed" in sbti or "targets set" in sbti:
        findings.append(f"SBTi: {sbti} — targets set but not yet validated.")
    elif "validated" in sbti or "approved" in sbti:
        findings.append(f"SBTi: Validated targets in place.")
    elif sbti:
        findings.append(f"SBTi status: {sbti}.")
    else:
        flags.append("SBTI_UNKNOWN")
        findings.append("SBTi validation status not found.")

    if nzt:
        try:
            target_year = int(re.search(r"\d{4}", str(nzt)).group())
            gap = target_year - datetime.now().year
            if gap > 30:
                flags.append("NET_ZERO_TARGET_VERY_DISTANT")
                findings.append(f"Net-zero target is {gap} years away — credibility risk.")
        except Exception:
            pass

    gap_pct = (pathway_data or {}).get("iea_nze_gap_pct") or (pathway_data or {}).get("pathway_gap_pct")
    if gap_pct is not None:
        if float(gap_pct) > 20:
            flags.append("PATHWAY_MISALIGNED")
            findings.append(f"Carbon pathway gap: {gap_pct:.1f}% vs IEA NZE — misaligned.")
        else:
            findings.append(f"Carbon pathway within {gap_pct:.1f}% of IEA NZE target.")

    return {
        "scope_flags": flags,
        "findings": findings,
        "is_carbon_credible": len([f for f in flags if "MISSING" in f or "MISALIGNED" in f]) == 0,
    }


# ---------------------------------------------------------------------------
# RULE 8 – Temporal Consistency
# ---------------------------------------------------------------------------

def check_temporal_consistency(temporal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    RULE 8: Flag sudden improvements or inconsistent disclosures.
    """
    flags: List[str] = []
    findings: List[str] = []

    trend = str(temporal_data.get("claim_trend") or "").lower()
    env_trend = str(temporal_data.get("environmental_trend") or "").lower()
    consistency = float(temporal_data.get("consistency_score") or 50)

    if "sudden" in trend or "jump" in trend:
        flags.append("SUDDEN_IMPROVEMENT")
        findings.append("Sudden improvement detected — possible greenwashing signal.")

    if consistency < 50:
        flags.append("INCONSISTENT_DISCLOSURES")
        findings.append(f"Temporal consistency score {consistency}/100 — disclosures inconsistent across years.")

    yoy = temporal_data.get("year_over_year_changes") or []
    for change in yoy:
        if isinstance(change, dict):
            delta = change.get("delta_pct")
            metric = change.get("metric", "")
            if delta is not None and abs(float(delta)) > 40:
                flags.append(f"LARGE_YOY_SHIFT_{metric.upper()[:20]}")
                findings.append(f"{metric}: {delta:+.1f}% YoY change — warrants scrutiny.")

    return {
        "temporal_flags": flags,
        "findings": findings,
        "consistency_score": consistency,
        "is_temporally_consistent": len(flags) == 0,
    }


# ---------------------------------------------------------------------------
# RULE 9 – Controversy Integration
# ---------------------------------------------------------------------------

def integrate_controversies(
    contradictions: List[Dict[str, Any]],
    regulatory_gaps: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    RULE 9: Aggregate regulatory fines, litigation, ESG controversies.
    Cross-check with media + regulatory databases.
    """
    regulatory_actions = [
        c for c in contradictions
        if str(c.get("source_type") or "").lower() in ("verified_regulatory_case", "regulatory", "legal")
        or str(c.get("severity") or "").upper() in ("HIGH", "CRITICAL")
    ]

    media_hits = [
        e for e in evidence
        if get_source_tier(e) <= 3
        and any(kw in str(e.get("snippet") or e.get("text") or "").lower()
                for kw in ["fine", "penalty", "lawsuit", "fraud", "violation", "banned", "misleading"])
    ]

    non_compliant = [
        r for r in regulatory_gaps
        if str(r.get("status") or "").lower() in ("non-compliant", "gap", "missing", "pending")
    ]

    total_controversies = len(regulatory_actions) + len(media_hits)
    severity = "HIGH" if len(regulatory_actions) >= 2 else "MEDIUM" if total_controversies >= 2 else "LOW"

    return {
        "total_controversies": total_controversies,
        "regulatory_actions": len(regulatory_actions),
        "media_verified_controversies": len(media_hits),
        "non_compliant_frameworks": len(non_compliant),
        "controversy_severity": severity,
        "top_controversies": [
            {
                "description": c.get("description", "")[:150],
                "source": c.get("source", ""),
                "severity": c.get("severity", ""),
                "year": c.get("year"),
            }
            for c in (regulatory_actions + [
                {"description": e.get("snippet", e.get("text", ""))[:150],
                 "source": e.get("source_name", ""),
                 "severity": "MEDIUM", "year": e.get("year")}
                for e in media_hits
            ])[:5]
        ],
    }


# ---------------------------------------------------------------------------
# RULE 10 – Final Institutional Output Assembler
# ---------------------------------------------------------------------------

def build_institutional_report(
    claim_text: str,
    evidence: List[Dict[str, Any]],
    esg_score: float,
    confidence_pct: float,
    carbon_data: Dict[str, Any],
    pathway_data: Dict[str, Any],
    temporal_data: Dict[str, Any],
    contradictions: List[Dict[str, Any]],
    regulatory_gaps: List[Dict[str, Any]],
    external_benchmarks: Dict[str, Any],
) -> Dict[str, Any]:
    """
    RULE 10: Master assembler — runs all checks and returns a structured
    institutional-grade verification payload.
    Called from risk_scoring_node / verdict_generation_node.
    """

    # Run all sub-checks
    verification = verify_claim(claim_text, evidence)
    divergence = check_rating_divergence(external_benchmarks or {}, esg_score)
    missing = flag_missing_data(carbon_data or {})
    abstention = should_abstain(confidence_pct, verification, divergence, missing)
    carbon_validation = validate_carbon_claims(carbon_data or {}, pathway_data or {})
    temporal = check_temporal_consistency(temporal_data or {})
    controversy = integrate_controversies(contradictions or [], regulatory_gaps or [], evidence or [])

    # Source breakdown by tier
    tier_summary: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    for e in evidence:
        t = get_source_tier(e)
        tier_summary[t] = tier_summary.get(t, 0) + 1

    # Overall institutional verdict
    if abstention["abstain"]:
        overall = "INSUFFICIENT EVIDENCE — NO DECISION"
    elif verification["status"] == "CONTRADICTED":
        overall = "CLAIM CONTRADICTED"
    elif verification["status"] == "VERIFIED" and not carbon_validation["scope_flags"]:
        overall = "CLAIM VERIFIED"
    elif verification["status"] == "PARTIALLY_VERIFIED":
        overall = "CLAIM PARTIALLY VERIFIED"
    else:
        overall = "CLAIM UNVERIFIED"

    return {
        "institutional_verdict": overall,
        "claim_verification": verification,
        "rating_divergence": divergence,
        "carbon_data_completeness": missing,
        "abstention_assessment": abstention,
        "carbon_validation": carbon_validation,
        "temporal_consistency": temporal,
        "controversy_summary": controversy,
        "source_tier_breakdown": {
            "tier1_regulatory": tier_summary[1],
            "tier2_esg_agencies": tier_summary[2],
            "tier3_media": tier_summary[3],
            "tier4_general_web": tier_summary[4],
            "total": sum(tier_summary.values()),
        },
        "confidence_pct": round(confidence_pct, 1),
        "data_quality_flags": (
            carbon_validation["scope_flags"]
            + temporal["temporal_flags"]
            + (["RATING_DIVERGENCE"] if divergence["divergence_detected"] else [])
        ),
        "summary_for_report": (
            f"{overall} | Confidence: {confidence_pct:.0f}% | "
            f"Evidence: {tier_summary[1]+tier_summary[2]} Tier1-2, {tier_summary[3]} Tier3, {tier_summary[4]} Tier4 | "
            f"Controversies: {controversy['total_controversies']} | "
            f"Carbon completeness: {missing['completeness_pct']}%"
        ),
    }
