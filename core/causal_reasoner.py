"""
core/causal_reasoner.py
------------------------
Fixes Problems #14 (No Causal Reasoning) and #6 (Black-Box Scoring)

Builds causal chains that explain WHY a score is what it is:
  Claim → Required condition → Evidence status → Risk implication

Also generates per-factor explanations for the GW formula components
(C, P, R, D, T) so the scoring model is no longer a black box.
"""
from __future__ import annotations
import re, logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Causal Chain Templates (claim-type → causal structure) ──
# These are reasoning templates, not hardcoded answers
CAUSAL_TEMPLATES = {
    "net_zero": [
        {"condition": "SBTi validated targets", "if_missing": "Net zero claim lacks independent scientific validation",
         "risk_implication": "HIGH — unverified net-zero targets are the most common greenwashing pattern"},
        {"condition": "Scope 3 disclosure", "if_missing": "Omitting value chain emissions understates true footprint",
         "risk_implication": "HIGH — Scope 3 typically represents 70-90% of total emissions"},
        {"condition": "No fossil fuel expansion", "if_missing": "New fossil investments contradict net-zero pathway",
         "risk_implication": "CRITICAL — production expansion is incompatible with 1.5°C alignment"},
    ],
    "renewable_energy": [
        {"condition": "Verified energy mix data", "if_missing": "Renewable claims without audited energy breakdown",
         "risk_implication": "MODERATE — self-reported energy mix is unreliable without third-party audit"},
        {"condition": "Location-based accounting", "if_missing": "Market-based only accounting can mask actual grid reliance",
         "risk_implication": "MODERATE — PPA certificates may not reflect actual consumption"},
    ],
    "emissions_reduction": [
        {"condition": "Fixed baseline year", "if_missing": "Baseline year changes can manufacture artificial reductions",
         "risk_implication": "HIGH — baseline manipulation is a known greenwashing technique"},
        {"condition": "Absolute reduction (not just intensity)", "if_missing": "Intensity reductions may hide absolute emission increases",
         "risk_implication": "MODERATE — growing companies can reduce intensity while increasing total emissions"},
    ],
}


def build_causal_chains(
    claim_text: str,
    claim_types: List[str],
    evidence_gaps: Dict[str, Any],
    contradiction_count: int = 0,
) -> List[Dict[str, Any]]:
    """
    Build causal reasoning chains explaining WHY the risk assessment
    reached its conclusion. Each chain is:
      Claim → Condition → Evidence Status → Because → Risk
    """
    chains = []

    for ct in claim_types:
        templates = CAUSAL_TEMPLATES.get(ct, [])
        type_analysis = evidence_gaps.get("per_type_analysis", {}).get(ct, {})
        missing = {m["type"] for m in type_analysis.get("missing_evidence", [])}
        found = {f["type"] for f in type_analysis.get("found_evidence", [])}
        red_flags = type_analysis.get("red_flags_detected", [])

        for tmpl in templates:
            condition = tmpl["condition"]
            # Determine if condition is met based on evidence gaps
            condition_tokens = set(re.findall(r"[a-z]{3,}", condition.lower()))
            # Check if evidence was found for this condition
            is_met = any(
                len(condition_tokens & set(re.findall(r"[a-z]{3,}", f.lower()))) >= 2
                for f in (type_analysis.get("found_evidence", []) or [])
                if isinstance(f, dict)
                for f_text in [f.get("description", "")]
            )

            if is_met:
                chains.append({
                    "claim_type": ct,
                    "condition": condition,
                    "status": "MET",
                    "reasoning": f"Evidence found supporting: {condition}",
                    "risk_implication": "LOW — condition satisfied",
                    "causal_direction": "mitigates_risk",
                })
            else:
                chains.append({
                    "claim_type": ct,
                    "condition": condition,
                    "status": "UNMET",
                    "reasoning": tmpl["if_missing"],
                    "risk_implication": tmpl["risk_implication"],
                    "causal_direction": "increases_risk",
                })

        # Red flag causal chains
        for rf in red_flags:
            chains.append({
                "claim_type": ct,
                "condition": f"Absence of: {rf['description']}",
                "status": "RED_FLAG",
                "reasoning": f"Evidence found that directly contradicts claim: {rf['description']}",
                "risk_implication": "HIGH — contradictory evidence detected",
                "causal_direction": "increases_risk",
            })

    # Contradiction-driven causal chain
    if contradiction_count >= 2:
        chains.append({
            "claim_type": "cross_cutting",
            "condition": "Internal consistency of claims",
            "status": "FAILED",
            "reasoning": f"{contradiction_count} contradictions found between stated claims and available evidence",
            "risk_implication": "HIGH — multiple contradictions indicate systemic credibility issues",
            "causal_direction": "increases_risk",
        })

    return chains


def explain_gw_factor(
    factor_name: str,
    value: float,
    all_analyses: Dict[str, Any],
) -> str:
    """
    Generate natural language explanation for a single GW formula factor.
    Fixes Problem #6 — makes the scoring model explainable.
    """
    explanations = {
        "C": _explain_claim_intensity,
        "P": _explain_performance,
        "R": _explain_controversy,
        "D": _explain_disclosure,
        "T": _explain_temporal,
    }
    fn = explanations.get(factor_name)
    if fn:
        return fn(value, all_analyses)
    return f"{factor_name} = {value:.1f}"


def _explain_claim_intensity(value: float, ctx: Dict) -> str:
    if value >= 70:
        return f"Claim Intensity HIGH ({value:.0f}/100): Claims use strong/absolute language without proportionate evidence backing."
    if value >= 40:
        return f"Claim Intensity MODERATE ({value:.0f}/100): Claims contain measurable targets but some lack supporting evidence."
    return f"Claim Intensity LOW ({value:.0f}/100): Claims are measured, specific, and well-scoped."


def _explain_performance(value: float, ctx: Dict) -> str:
    if value >= 70:
        return f"Performance STRONG ({value:.0f}/100): Verified operational data supports claimed ESG performance."
    if value >= 40:
        return f"Performance AVERAGE ({value:.0f}/100): Some operational data available but gaps in disclosure reduce confidence."
    return f"Performance WEAK ({value:.0f}/100): Limited verifiable performance data; claims exceed demonstrable actions."


def _explain_controversy(value: float, ctx: Dict) -> str:
    if value >= 60:
        return f"Controversy Risk HIGH ({value:.0f}/100): Active regulatory actions, lawsuits, or credible investigative reports on record."
    if value >= 30:
        return f"Controversy Risk MODERATE ({value:.0f}/100): Some media/NGO concerns but no confirmed regulatory action."
    return f"Controversy Risk LOW ({value:.0f}/100): No significant controversies or regulatory flags identified."


def _explain_disclosure(value: float, ctx: Dict) -> str:
    if value >= 70:
        return f"Disclosure Completeness GOOD ({value:.0f}/100): Company reports across key ESG frameworks (CDP, GRI, BRSR, TCFD)."
    if value >= 40:
        return f"Disclosure Completeness PARTIAL ({value:.0f}/100): Some disclosures available but missing key areas like Scope 3 or social metrics."
    return f"Disclosure Completeness POOR ({value:.0f}/100): Minimal public ESG disclosure; transparency is insufficient for verification."


def _explain_temporal(value: float, ctx: Dict) -> str:
    if value >= 60:
        return f"Temporal Escalation HIGH ({value:.0f}/100): Commitment timeline shows weakening ambition or missed milestones over time."
    if value >= 30:
        return f"Temporal Escalation MODERATE ({value:.0f}/100): Some timeline shifts detected but overall trajectory maintained."
    return f"Temporal Escalation LOW ({value:.0f}/100): Commitments show stable or improving trajectory over time."


def generate_score_explanation(
    gw_components: Dict[str, Any],
    all_analyses: Dict[str, Any],
) -> Dict[str, str]:
    """Generate per-factor explanations for the entire GW formula."""
    fc = gw_components.get("formula_components", {})
    explanations = {}
    for factor in ["C", "P", "R", "D", "T"]:
        val = float(fc.get(factor, 50))
        explanations[factor] = explain_gw_factor(factor, val, all_analyses)
    return explanations
