"""
core/objective_function.py
--------------------------
Unified Dual-Objective ESG Intelligence Function

Ensures ESG Performance Score and Greenwashing Risk Score are co-primary
outputs that are always internally consistent and mutually reinforcing.

Design Principles:
    1. ESG Score measures ACTUAL performance (what the company IS doing)
    2. GW Score measures CLAIM CREDIBILITY (how honest the company IS about it)
    3. Both scores inform each other but are computed independently
    4. Evidence Attribution links every conclusion to specific evidence
    5. Consistency checks prevent contradictory outputs

Called from verdict_generation_node AFTER risk_scorer has produced raw scores.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Consistency Matrix: What combinations of ESG + GW are valid?
# ---------------------------------------------------------------------------
#
#  ESG Score  | GW Risk  | Interpretation                        | Valid?
#  ----------|----------|---------------------------------------|--------
#  HIGH (>75) | LOW (<35)  | Strong performer, honest claims      | ✅
#  HIGH (>75) | HIGH (>65) | Claims look good but evidence weak   | ✅ (greenhushing inverse)
#  LOW  (<50) | LOW (<35)  | Poor performer, but honest about it  | ✅
#  LOW  (<50) | HIGH (>65) | Poor performer AND deceptive claims  | ✅
#  MID        | MID        | Average performer, some concerns     | ✅
#  HIGH (>75) | HIGH (>65) + no contradictions | Inconsistent     | ⚠️ Needs review

CONSISTENCY_RULES = [
    {
        "name": "high_esg_high_gw_no_evidence",
        "condition": lambda esg, gw, ctx: esg >= 75 and gw >= 65 and ctx.get("contradiction_count", 0) == 0 and ctx.get("evidence_count", 0) < 5,
        "action": "flag",
        "message": "High ESG score with high GW risk but no contradictions found — likely insufficient evidence. GW score may be inflated by disclosure gaps rather than actual deception.",
        "adjustment": {"gw_cap": 60, "confidence_penalty": 0.10},
    },
    {
        "name": "low_esg_low_gw_with_vague_claims",
        "condition": lambda esg, gw, ctx: esg < 50 and gw < 35 and ctx.get("claim_specificity", 10) < 4,
        "action": "flag",
        "message": "Low ESG score with low GW risk despite vague claims — GW score may be understating risk. Vague claims from poor performers deserve scrutiny.",
        "adjustment": {"gw_floor": 40, "confidence_penalty": 0.05},
    },
    {
        "name": "extreme_divergence",
        "condition": lambda esg, gw, ctx: abs(esg - (100 - gw)) > 50,
        "action": "flag",
        "message": "ESG and GW scores are extremely divergent — review evidence quality and scoring inputs.",
        "adjustment": {"confidence_penalty": 0.15},
    },
]


# ---------------------------------------------------------------------------
# Evidence Chain: Links conclusions to specific evidence items
# ---------------------------------------------------------------------------

class EvidenceChain:
    """Tracks which evidence items support which conclusions."""

    def __init__(self):
        self.chains: List[Dict[str, Any]] = []

    def add_link(
        self,
        conclusion: str,
        conclusion_type: str,  # "esg_score", "gw_risk", "pillar_score", "claim_verdict"
        evidence_ids: List[str],
        evidence_summaries: List[str],
        confidence: float,
        reasoning: str,
    ):
        self.chains.append({
            "conclusion": conclusion,
            "conclusion_type": conclusion_type,
            "evidence_ids": evidence_ids,
            "evidence_summaries": evidence_summaries[:3],  # Top 3 for readability
            "confidence": round(confidence, 3),
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat(),
        })

    def get_chains_for_type(self, conclusion_type: str) -> List[Dict[str, Any]]:
        return [c for c in self.chains if c["conclusion_type"] == conclusion_type]

    def to_dict(self) -> List[Dict[str, Any]]:
        return self.chains


# ---------------------------------------------------------------------------
# Unified Output Builder
# ---------------------------------------------------------------------------

class UnifiedESGOutput:
    """
    Builds the final unified output ensuring ESG and GW scores are
    co-primary, internally consistent, and fully attributed.
    """

    def __init__(self):
        self.evidence_chain = EvidenceChain()
        self.consistency_flags: List[Dict[str, Any]] = []
        self.adjustments_log: List[Dict[str, Any]] = []

    def build_unified_verdict(
        self,
        *,
        company: str,
        claim: str,
        industry: str,
        # ESG Performance (co-primary)
        esg_score: float,
        environmental_score: float,
        social_score: float,
        governance_score: float,
        rating_grade: str,
        # Greenwashing Risk (co-primary)
        greenwashing_score: float,
        gw_components: Dict[str, Any],
        # Institutional Verification
        institutional_verdict: Optional[str] = None,
        claim_verification_status: Optional[str] = None,
        # Context for consistency checks
        evidence_count: int = 0,
        contradiction_count: int = 0,
        claim_specificity: float = 5.0,
        confidence: float = 0.5,
        tier1_evidence_count: int = 0,
        tier2_evidence_count: int = 0,
        # Score lineage
        esg_score_lineage: Optional[Dict[str, Any]] = None,
        # Abstention
        abstain_recommended: bool = False,
        abstention_reason: str = "",
    ) -> Dict[str, Any]:
        """
        Build the final unified verdict with consistency enforcement.

        Returns a single authoritative output dict that downstream consumers
        (report generator, API, frontend) should use as the source of truth.
        """

        # --- Step 1: Run consistency checks ---
        ctx = {
            "evidence_count": evidence_count,
            "contradiction_count": contradiction_count,
            "claim_specificity": claim_specificity,
            "tier1_count": tier1_evidence_count,
            "tier2_count": tier2_evidence_count,
        }

        adjusted_gw = greenwashing_score
        adjusted_confidence = confidence

        for rule in CONSISTENCY_RULES:
            try:
                if rule["condition"](esg_score, greenwashing_score, ctx):
                    self.consistency_flags.append({
                        "rule": rule["name"],
                        "message": rule["message"],
                        "action": rule["action"],
                    })
                    adj = rule.get("adjustment", {})
                    if "gw_cap" in adj:
                        old_gw = adjusted_gw
                        adjusted_gw = min(adjusted_gw, adj["gw_cap"])
                        if old_gw != adjusted_gw:
                            self.adjustments_log.append({
                                "type": "gw_cap",
                                "rule": rule["name"],
                                "before": round(old_gw, 1),
                                "after": round(adjusted_gw, 1),
                            })
                    if "gw_floor" in adj:
                        old_gw = adjusted_gw
                        adjusted_gw = max(adjusted_gw, adj["gw_floor"])
                        if old_gw != adjusted_gw:
                            self.adjustments_log.append({
                                "type": "gw_floor",
                                "rule": rule["name"],
                                "before": round(old_gw, 1),
                                "after": round(adjusted_gw, 1),
                            })
                    if "confidence_penalty" in adj:
                        adjusted_confidence = max(0.35, adjusted_confidence - adj["confidence_penalty"])
            except Exception as e:
                logger.warning("Consistency rule %s failed: %s", rule["name"], e)

        # --- Step 2: Derive unified risk level ---
        risk_level = self._derive_risk_level(esg_score, adjusted_gw, abstain_recommended)

        # --- Step 3: Build explanation strings ---
        esg_explanation = self._explain_esg_score(
            esg_score, environmental_score, social_score, governance_score, industry
        )
        gw_explanation = self._explain_gw_score(
            adjusted_gw, gw_components, claim, industry
        )

        # --- Step 4: Assemble unified output ---
        unified = {
            # Identity
            "company": company,
            "claim": claim,
            "industry": industry,
            "timestamp": datetime.now().isoformat(),

            # ═══════════════════════════════════════════════════════
            # CO-PRIMARY OUTPUT 1: ESG Performance Score
            # ═══════════════════════════════════════════════════════
            "esg_performance": {
                "overall_score": round(esg_score, 1),
                "environmental_score": round(environmental_score, 1),
                "social_score": round(social_score, 1),
                "governance_score": round(governance_score, 1),
                "rating_grade": rating_grade,
                "explanation": esg_explanation,
                "interpretation": self._interpret_esg(esg_score, rating_grade),
            },

            # ═══════════════════════════════════════════════════════
            # CO-PRIMARY OUTPUT 2: Greenwashing Risk Score
            # ═══════════════════════════════════════════════════════
            "greenwashing_risk": {
                "score": round(adjusted_gw, 1),
                "risk_band": self._gw_risk_band(adjusted_gw),
                "components": gw_components,
                "explanation": gw_explanation,
                "interpretation": self._interpret_gw(adjusted_gw),
                "pre_consistency_score": round(greenwashing_score, 1),
            },

            # ═══════════════════════════════════════════════════════
            # UNIFIED RISK ASSESSMENT
            # ═══════════════════════════════════════════════════════
            "risk_level": risk_level,
            "final_confidence": round(adjusted_confidence, 3),

            # ═══════════════════════════════════════════════════════
            # EVIDENCE ATTRIBUTION (Transparency)
            # ═══════════════════════════════════════════════════════
            "evidence_attribution": {
                "total_evidence_items": evidence_count,
                "tier1_regulatory": tier1_evidence_count,
                "tier2_esg_agencies": tier2_evidence_count,
                "contradiction_count": contradiction_count,
                "evidence_chains": self.evidence_chain.to_dict(),
            },

            # ═══════════════════════════════════════════════════════
            # INSTITUTIONAL VERIFICATION (If available)
            # ═══════════════════════════════════════════════════════
            "institutional_verification": {
                "verdict": institutional_verdict or "NOT_RUN",
                "claim_status": claim_verification_status or "PENDING",
            },

            # ═══════════════════════════════════════════════════════
            # QUALITY METADATA
            # ═══════════════════════════════════════════════════════
            "quality_metadata": {
                "consistency_flags": self.consistency_flags,
                "adjustments_applied": self.adjustments_log,
                "abstain_recommended": abstain_recommended,
                "abstention_reason": abstention_reason if abstain_recommended else "",
                "score_lineage": esg_score_lineage or {},
            },
        }

        # Log for transparency
        if self.consistency_flags:
            for flag in self.consistency_flags:
                logger.info(
                    "Consistency flag [%s]: %s", flag["rule"], flag["message"]
                )

        return unified

    # -------------------------------------------------------------------
    # Risk Level Derivation: Uses BOTH ESG and GW scores
    # -------------------------------------------------------------------

    @staticmethod
    def _derive_risk_level(
        esg_score: float,
        gw_score: float,
        abstain: bool,
    ) -> str:
        """
        Derive unified risk level from both ESG performance and GW risk.

        The risk level reflects the COMBINED assessment:
        - HIGH: Either GW risk is high OR ESG is very poor with concerns
        - MODERATE: Mixed signals, some concerns but not definitive
        - LOW: Good ESG performance AND low greenwashing indicators
        - ABSTAIN: Insufficient evidence for any conclusion
        """
        if abstain:
            return "ABSTAIN"

        # GW score is the primary risk driver (claim credibility)
        # ESG score provides context (actual performance)

        if gw_score >= 65:
            return "HIGH"
        if gw_score >= 50:
            # In the moderate GW zone, ESG score can push it either way
            if esg_score < 40:
                return "HIGH"  # Poor performer + moderate GW = HIGH
            return "MODERATE"
        if gw_score >= 35:
            if esg_score < 35:
                return "MODERATE"  # Low GW but very poor ESG = still concerning
            return "LOW" if esg_score >= 60 else "MODERATE"

        # GW < 35 = low greenwashing risk
        return "LOW"

    # -------------------------------------------------------------------
    # Explanation Generators
    # -------------------------------------------------------------------

    @staticmethod
    def _explain_esg_score(
        overall: float, env: float, soc: float, gov: float, industry: str
    ) -> str:
        parts = []
        # Identify strongest and weakest pillars
        pillars = {"Environmental": env, "Social": soc, "Governance": gov}
        strongest = max(pillars, key=pillars.get)
        weakest = min(pillars, key=pillars.get)

        if overall >= 75:
            parts.append(f"Strong ESG performance ({overall:.0f}/100).")
        elif overall >= 50:
            parts.append(f"Average ESG performance ({overall:.0f}/100).")
        else:
            parts.append(f"Below-average ESG performance ({overall:.0f}/100).")

        parts.append(
            f"Strongest pillar: {strongest} ({pillars[strongest]:.0f}). "
            f"Weakest: {weakest} ({pillars[weakest]:.0f})."
        )

        gap = pillars[strongest] - pillars[weakest]
        if gap > 25:
            parts.append(
                f"Significant pillar imbalance ({gap:.0f}-point spread) "
                f"suggests uneven ESG maturity."
            )

        return " ".join(parts)

    @staticmethod
    def _explain_gw_score(
        gw: float,
        components: Dict[str, Any],
        claim: str,
        industry: str,
    ) -> str:
        parts = []
        fc = components.get("formula_components", {})
        C = fc.get("C", 0)
        P = fc.get("P", 0)
        D = fc.get("D", 0)

        if gw >= 65:
            parts.append(f"High greenwashing risk ({gw:.0f}/100).")
        elif gw >= 40:
            parts.append(f"Moderate greenwashing risk ({gw:.0f}/100).")
        else:
            parts.append(f"Low greenwashing risk ({gw:.0f}/100).")

        # Explain the main driver
        gap = C - P
        if gap > 20:
            parts.append(
                f"Primary driver: large claim-performance gap "
                f"(Claim Intensity {C:.0f} vs Performance {P:.0f}, gap={gap:.0f})."
            )
        elif D < 40:
            parts.append(
                f"Primary driver: low disclosure completeness ({D:.0f}/100). "
                f"Insufficient transparency to verify claims."
            )
        elif fc.get("R", 0) > 50:
            parts.append(
                f"Primary driver: controversy/regulatory risk (R={fc.get('R', 0):.0f}/100)."
            )

        return " ".join(parts)

    @staticmethod
    def _interpret_esg(score: float, grade: str) -> str:
        if score >= 85:
            return f"ESG Leader ({grade}): Company demonstrates best-in-class ESG practices."
        if score >= 75:
            return f"Above Average ({grade}): Strong ESG fundamentals with room for improvement."
        if score >= 60:
            return f"Average ({grade}): Meeting basic ESG expectations for the sector."
        if score >= 50:
            return f"Below Average ({grade}): ESG practices lag sector peers."
        return f"ESG Laggard ({grade}): Significant ESG gaps requiring urgent attention."

    @staticmethod
    def _interpret_gw(score: float) -> str:
        if score >= 70:
            return "High Risk: ESG claims are substantially unsupported by evidence. Significant gap between stated commitments and verifiable actions."
        if score >= 50:
            return "Elevated Risk: Some ESG claims lack adequate evidence or contain material inconsistencies."
        if score >= 35:
            return "Moderate Risk: ESG claims are partially supported. Some disclosure gaps exist but no strong deception signals."
        return "Low Risk: ESG claims are well-supported by available evidence and consistent with observable performance."

    @staticmethod
    def _gw_risk_band(score: float) -> str:
        if score >= 70:
            return "HIGH"
        if score >= 50:
            return "ELEVATED"
        if score >= 35:
            return "MODERATE"
        return "LOW"


# ---------------------------------------------------------------------------
# Integration Helper: Extract context from ESGState for consistency checks
# ---------------------------------------------------------------------------

def extract_consistency_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract context needed for consistency checks from the pipeline state.
    Called by verdict_generation_node before building the unified output.
    """
    evidence = state.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    # Count evidence by tier
    from core.institutional_verifier import get_source_tier
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for e in evidence:
        if isinstance(e, dict):
            t = get_source_tier(e)
            tier_counts[t] = tier_counts.get(t, 0) + 1

    # Get contradiction count
    contradiction_count = 0
    for ao in state.get("agent_outputs", []):
        if not isinstance(ao, dict):
            continue
        if ao.get("agent") == "contradiction_analysis":
            out = ao.get("output", {})
            if isinstance(out, dict):
                contradiction_count = int(
                    out.get("contradictions_found", 0)
                    or out.get("total_contradictions", 0)
                    or 0
                )
            break

    # Get claim specificity from claim extraction
    claim_specificity = 5.0  # default mid
    for ao in state.get("agent_outputs", []):
        if not isinstance(ao, dict):
            continue
        if ao.get("agent") == "claim_extraction":
            out = ao.get("output", {})
            if isinstance(out, dict):
                claims = out.get("claims", [])
                if claims and isinstance(claims, list):
                    specs = [
                        c.get("specificity_score", 5)
                        for c in claims
                        if isinstance(c, dict)
                    ]
                    if specs:
                        claim_specificity = sum(specs) / len(specs)
            break

    return {
        "evidence_count": len(evidence),
        "contradiction_count": contradiction_count,
        "claim_specificity": claim_specificity,
        "tier1_evidence_count": tier_counts[1],
        "tier2_evidence_count": tier_counts[2],
        "tier3_evidence_count": tier_counts[3],
        "tier4_evidence_count": tier_counts[4],
    }


def build_unified_output_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function: Build unified output directly from pipeline state.
    Extracts all needed values from risk_scoring agent output and state fields.
    """
    # Get risk scorer output
    risk_output = {}
    for ao in state.get("agent_outputs", []):
        if isinstance(ao, dict) and ao.get("agent") == "risk_scoring":
            risk_output = ao.get("output", {})
            if isinstance(risk_output, dict):
                break

    pillar_scores = risk_output.get("pillarscores", risk_output.get("pillar_scores", {}))
    if not isinstance(pillar_scores, dict):
        pillar_scores = {}

    gw_result = risk_output.get("greenwashing_result", {})
    if not isinstance(gw_result, dict):
        gw_result = {}

    ctx = extract_consistency_context(state)

    builder = UnifiedESGOutput()
    return builder.build_unified_verdict(
        company=state.get("company", "Unknown"),
        claim=state.get("claim", ""),
        industry=state.get("industry", "General"),
        # ESG Performance
        esg_score=float(risk_output.get("esg_score", 50)),
        environmental_score=float(pillar_scores.get("environmental_score", 50)),
        social_score=float(pillar_scores.get("social_score", 50)),
        governance_score=float(pillar_scores.get("governance_score", 50)),
        rating_grade=str(
            risk_output.get("ratinggrade")
            or risk_output.get("rating_grade")
            or "BBB"
        ),
        # Greenwashing Risk
        greenwashing_score=float(gw_result.get("greenwashing_score", 50)),
        gw_components=gw_result,
        # Institutional
        institutional_verdict=risk_output.get("institutional_verdict"),
        claim_verification_status=risk_output.get("claim_verification_status"),
        # Context
        evidence_count=ctx["evidence_count"],
        contradiction_count=ctx["contradiction_count"],
        claim_specificity=ctx["claim_specificity"],
        confidence=float(state.get("confidence", 0.5)),
        tier1_evidence_count=ctx["tier1_evidence_count"],
        tier2_evidence_count=ctx["tier2_evidence_count"],
        # Lineage
        esg_score_lineage=state.get("esg_score_lineage"),
        # Abstention
        abstain_recommended=bool(risk_output.get("abstainrecommended", risk_output.get("abstain_recommended", False))),
        abstention_reason=str(risk_output.get("abstentionreason", risk_output.get("abstention_reason", ""))),
    )
