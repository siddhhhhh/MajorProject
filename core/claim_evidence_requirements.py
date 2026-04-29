"""
core/claim_evidence_requirements.py
------------------------------------
Claim-Centric Evidence Requirement Engine

Instead of searching broadly and hoping to find relevant evidence,
this module defines WHAT evidence each type of ESG claim REQUIRES
for verification, then checks whether the pipeline actually found it.

This transforms the architecture from:
    Data → Scoring → Loosely mapped to claim
To:
    Claim → Required evidence → Search for it → Score per-claim

Used by:
    - evidence_retriever.py (to guide targeted searches)
    - risk_scorer.py (to compute claim-level verification status)
    - report_generator.py (to explain what evidence is missing)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Evidence Requirement Definitions
# ---------------------------------------------------------------------------
# Each claim type maps to:
#   - required_evidence: MUST have at least N of these for "VERIFIED"
#   - supporting_evidence: Nice-to-have, boosts confidence
#   - red_flags: If found, escalates greenwashing risk
#   - minimum_tier: Lowest acceptable source tier for verification

CLAIM_EVIDENCE_MAP: Dict[str, Dict[str, Any]] = {
    "net_zero": {
        "display_name": "Net Zero / Carbon Neutral Commitment",
        "match_patterns": [
            r"net[\s-]?zero",
            r"carbon[\s-]?neutral",
            r"climate[\s-]?neutral",
        ],
        "required_evidence": [
            {"type": "sbti_validation", "description": "Science Based Targets initiative validation status", "search_queries": ["{company} SBTi target validation status", "site:sciencebasedtargets.org {company}"]},
            {"type": "scope123_data", "description": "Scope 1, 2, and 3 emissions data", "search_queries": ["{company} scope 1 2 3 emissions disclosure", "{company} GHG emissions annual report"]},
            {"type": "pathway_alignment", "description": "1.5°C or 2°C pathway alignment assessment", "search_queries": ["{company} 1.5 degree pathway alignment", "{company} net zero pathway credibility"]},
        ],
        "supporting_evidence": [
            {"type": "interim_targets", "description": "Interim reduction targets (2025, 2030)", "search_queries": ["{company} emissions reduction target 2030"]},
            {"type": "cdp_disclosure", "description": "CDP climate change response", "search_queries": ["site:cdp.net {company} climate response"]},
            {"type": "offset_strategy", "description": "Carbon offset/removal strategy details", "search_queries": ["{company} carbon offset removal strategy"]},
        ],
        "red_flags": [
            {"pattern": r"production\s+(growth|expansion|increase)", "description": "Production expansion contradicts net zero"},
            {"pattern": r"new\s+(oil|gas|coal|fossil)", "description": "New fossil fuel investments"},
            {"pattern": r"offset[\s-]?(only|heavy|relian)", "description": "Over-reliance on offsets"},
        ],
        "minimum_tier": 2,
        "minimum_required_count": 2,
    },

    "renewable_energy": {
        "display_name": "Renewable Energy Claims",
        "match_patterns": [
            r"100%?\s*renewable",
            r"renewable\s+energy",
            r"clean\s+energy",
            r"RE100",
        ],
        "required_evidence": [
            {"type": "energy_mix", "description": "Current energy mix breakdown", "search_queries": ["{company} energy mix renewable percentage", "{company} electricity sources breakdown"]},
            {"type": "ppa_evidence", "description": "Power Purchase Agreements or RE certificates", "search_queries": ["{company} power purchase agreement renewable", "{company} IREC renewable energy certificate"]},
        ],
        "supporting_evidence": [
            {"type": "re100_membership", "description": "RE100 membership verification", "search_queries": ["site:there100.org {company}"]},
            {"type": "grid_mix", "description": "Regional grid emission factors", "search_queries": ["{company} grid emission factor location"]},
        ],
        "red_flags": [
            {"pattern": r"(diesel|backup)\s+generator", "description": "Backup fossil fuel generation"},
            {"pattern": r"scope\s*2.*market[\s-]?based\s+only", "description": "Market-based accounting without location-based disclosure"},
        ],
        "minimum_tier": 2,
        "minimum_required_count": 1,
    },

    "emissions_reduction": {
        "display_name": "Emissions Reduction Claims",
        "match_patterns": [
            r"\d+%?\s*(reduction|decrease|cut|lower)",
            r"reduc(e|ing|tion)\s+emission",
            r"emission.*\d+%",
        ],
        "required_evidence": [
            {"type": "baseline_year", "description": "Emissions baseline year and methodology", "search_queries": ["{company} emissions baseline year methodology"]},
            {"type": "verification", "description": "Third-party verification or assurance", "search_queries": ["{company} emissions verification assurance audit"]},
            {"type": "absolute_vs_intensity", "description": "Whether reduction is absolute or intensity-based", "search_queries": ["{company} absolute emissions intensity reduction"]},
        ],
        "supporting_evidence": [
            {"type": "scope_breakdown", "description": "Reduction by scope (1, 2, 3)", "search_queries": ["{company} scope 1 2 3 reduction breakdown"]},
        ],
        "red_flags": [
            {"pattern": r"intensity[\s-]?based\s+only", "description": "Intensity-only reduction while absolute emissions grow"},
            {"pattern": r"(acqui|divest|sold|restructur)", "description": "Reduction via portfolio changes, not operational improvement"},
            {"pattern": r"base\s*year\s*(chang|restat|adjust)", "description": "Baseline year manipulation"},
        ],
        "minimum_tier": 2,
        "minimum_required_count": 2,
    },

    "circular_economy": {
        "display_name": "Circular Economy / Zero Waste Claims",
        "match_patterns": [
            r"circular\s+economy",
            r"zero\s+waste",
            r"\d+%\s*recycl",
            r"100%\s*recyclable",
        ],
        "required_evidence": [
            {"type": "waste_data", "description": "Waste generation and diversion data", "search_queries": ["{company} waste data diversion rate recycling"]},
            {"type": "recyclability_proof", "description": "Actual recyclability vs theoretical", "search_queries": ["{company} recyclability rate actual vs theoretical"]},
        ],
        "supporting_evidence": [
            {"type": "lca", "description": "Life Cycle Assessment data", "search_queries": ["{company} life cycle assessment product"]},
        ],
        "red_flags": [
            {"pattern": r"(theoretical|potential)ly?\s+recycl", "description": "Theoretical vs actual recyclability"},
            {"pattern": r"downcycl", "description": "Downcycling marketed as recycling"},
        ],
        "minimum_tier": 3,
        "minimum_required_count": 1,
    },

    "social_impact": {
        "display_name": "Social / Labor / DEI Claims",
        "match_patterns": [
            r"divers(e|ity)",
            r"inclusion",
            r"equity",
            r"fair\s+(wage|pay|trade)",
            r"human\s+rights",
            r"living\s+wage",
            r"worker\s+(safety|welfare|rights)",
        ],
        "required_evidence": [
            {"type": "dei_metrics", "description": "Diversity metrics with year-over-year data", "search_queries": ["{company} diversity inclusion metrics workforce data"]},
            {"type": "audit_evidence", "description": "Supply chain or workplace audits", "search_queries": ["{company} supply chain audit labor rights"]},
        ],
        "supporting_evidence": [
            {"type": "pay_gap", "description": "Gender/racial pay gap disclosure", "search_queries": ["{company} gender pay gap disclosure"]},
            {"type": "certifications", "description": "Fair Trade, SA8000, or similar certifications", "search_queries": ["{company} fair trade certification labor"]},
        ],
        "red_flags": [
            {"pattern": r"(lawsuit|settlement|class\s+action).*labor", "description": "Labor-related lawsuits"},
            {"pattern": r"(sweatshop|child\s+labor|forced\s+labor)", "description": "Severe labor violations"},
        ],
        "minimum_tier": 3,
        "minimum_required_count": 1,
    },

    "governance": {
        "display_name": "Governance / Ethics / Transparency Claims",
        "match_patterns": [
            r"transparen(t|cy)",
            r"ethic(s|al)",
            r"good\s+governance",
            r"board\s+(divers|independen)",
            r"anti[\s-]?corrupt",
        ],
        "required_evidence": [
            {"type": "board_composition", "description": "Board independence and diversity data", "search_queries": ["{company} board composition independence diversity"]},
            {"type": "governance_filing", "description": "Proxy statement or governance charter", "search_queries": ["{company} proxy statement DEF 14A governance", "site:sec.gov {company} DEF 14A"]},
        ],
        "supporting_evidence": [
            {"type": "whistleblower", "description": "Whistleblower protection mechanisms", "search_queries": ["{company} whistleblower policy protection"]},
            {"type": "esg_committee", "description": "Board-level ESG oversight committee", "search_queries": ["{company} ESG committee board oversight"]},
        ],
        "red_flags": [
            {"pattern": r"(SEC|FCA|SEBI)\s*(fine|penalty|enforcement)", "description": "Regulatory enforcement actions"},
            {"pattern": r"(audit|accounting)\s*(scandal|restatement|fraud)", "description": "Financial integrity concerns"},
        ],
        "minimum_tier": 2,
        "minimum_required_count": 1,
    },

    "water_biodiversity": {
        "display_name": "Water / Biodiversity / Nature Claims",
        "match_patterns": [
            r"water[\s-]?(positive|neutral|steward)",
            r"biodiversity",
            r"nature[\s-]?positive",
            r"deforestation[\s-]?free",
            r"water\s+reduc",
        ],
        "required_evidence": [
            {"type": "water_data", "description": "Water withdrawal/consumption data by region", "search_queries": ["{company} water consumption withdrawal data"]},
            {"type": "biodiversity_assessment", "description": "Biodiversity impact assessment", "search_queries": ["{company} biodiversity assessment TNFD"]},
        ],
        "supporting_evidence": [
            {"type": "tnfd", "description": "TNFD alignment or nature-related disclosures", "search_queries": ["{company} TNFD nature disclosure"]},
        ],
        "red_flags": [
            {"pattern": r"(deforest|land\s+clear|habitat\s+destruct)", "description": "Deforestation or habitat destruction"},
        ],
        "minimum_tier": 3,
        "minimum_required_count": 1,
    },
}


# ---------------------------------------------------------------------------
# Claim Type Classifier
# ---------------------------------------------------------------------------

def classify_claim(claim_text: str) -> List[str]:
    """
    Classify a claim into one or more claim types.
    Returns list of matching claim type keys from CLAIM_EVIDENCE_MAP.
    """
    claim_lower = claim_text.lower()
    matched_types = []

    for claim_type, config in CLAIM_EVIDENCE_MAP.items():
        for pattern in config["match_patterns"]:
            if re.search(pattern, claim_lower, re.IGNORECASE):
                matched_types.append(claim_type)
                break

    # Default to most common if no match
    if not matched_types:
        # Check for generic ESG claim
        if any(kw in claim_lower for kw in ["sustain", "esg", "green", "climate", "environment"]):
            matched_types.append("emissions_reduction")  # Most common ESG claim type
        else:
            matched_types.append("governance")  # Fallback

    return matched_types


# ---------------------------------------------------------------------------
# Evidence Gap Analyzer
# ---------------------------------------------------------------------------

def analyze_evidence_gaps(
    claim_text: str,
    company: str,
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyze what evidence is available vs what is required for the claim.

    Returns:
        {
            "claim_types": ["net_zero", "emissions_reduction"],
            "per_type_analysis": {
                "net_zero": {
                    "required_total": 3,
                    "required_found": 1,
                    "missing_evidence": [...],
                    "found_evidence": [...],
                    "verification_status": "PARTIALLY_VERIFIED",
                    "search_queries_needed": [...],
                    "red_flags_detected": [...],
                }
            },
            "overall_evidence_sufficiency": 0.33,
            "highest_priority_gaps": [...],
        }
    """
    claim_types = classify_claim(claim_text)
    evidence_text_blob = " ".join(
        str(e.get("snippet", "") or e.get("relevant_text", "") or e.get("title", ""))
        for e in evidence
        if isinstance(e, dict)
    ).lower()

    per_type = {}
    all_gaps = []
    total_required = 0
    total_found = 0

    for ct in claim_types:
        config = CLAIM_EVIDENCE_MAP.get(ct)
        if not config:
            continue

        required = config["required_evidence"]
        found = []
        missing = []
        search_needed = []

        for req in required:
            # Check if evidence blob contains signals for this requirement
            req_keywords = req["description"].lower().split()
            # Count keyword matches
            match_score = sum(1 for kw in req_keywords if kw in evidence_text_blob)
            match_ratio = match_score / max(1, len(req_keywords))

            if match_ratio >= 0.3:  # At least 30% keyword overlap
                found.append({
                    "type": req["type"],
                    "description": req["description"],
                    "match_confidence": round(match_ratio, 2),
                })
            else:
                missing.append({
                    "type": req["type"],
                    "description": req["description"],
                    "priority": "HIGH",
                })
                # Generate targeted search queries for missing evidence
                for q in req.get("search_queries", []):
                    search_needed.append(q.replace("{company}", company))

        # Check red flags
        red_flags_found = []
        for rf in config.get("red_flags", []):
            if re.search(rf["pattern"], evidence_text_blob, re.IGNORECASE):
                red_flags_found.append({
                    "pattern": rf["pattern"],
                    "description": rf["description"],
                })

        # Determine verification status
        min_required = config.get("minimum_required_count", 1)
        if len(found) >= len(required):
            status = "VERIFIED"
        elif len(found) >= min_required:
            status = "PARTIALLY_VERIFIED"
        elif len(found) > 0:
            status = "WEAKLY_SUPPORTED"
        else:
            status = "UNVERIFIED"

        # Red flags can downgrade status
        if red_flags_found and status in ("VERIFIED", "PARTIALLY_VERIFIED"):
            status = "CONTRADICTED" if len(red_flags_found) >= 2 else "PARTIALLY_VERIFIED"

        per_type[ct] = {
            "display_name": config["display_name"],
            "required_total": len(required),
            "required_found": len(found),
            "missing_evidence": missing,
            "found_evidence": found,
            "verification_status": status,
            "search_queries_needed": search_needed[:6],  # Cap at 6
            "red_flags_detected": red_flags_found,
        }

        total_required += len(required)
        total_found += len(found)
        all_gaps.extend(missing)

    sufficiency = total_found / max(1, total_required)

    return {
        "claim_types": claim_types,
        "per_type_analysis": per_type,
        "overall_evidence_sufficiency": round(sufficiency, 3),
        "highest_priority_gaps": sorted(
            all_gaps, key=lambda x: x.get("priority", "LOW") == "HIGH", reverse=True
        )[:5],
        "total_required": total_required,
        "total_found": total_found,
    }


def get_targeted_search_queries(
    claim_text: str,
    company: str,
) -> List[str]:
    """
    Generate targeted search queries based on claim type.
    Used by evidence_retriever to supplement broad searches with claim-specific ones.
    """
    claim_types = classify_claim(claim_text)
    queries = []

    for ct in claim_types:
        config = CLAIM_EVIDENCE_MAP.get(ct)
        if not config:
            continue
        for req in config["required_evidence"]:
            for q in req.get("search_queries", []):
                queries.append(q.replace("{company}", company))
        # Add supporting evidence queries too (lower priority)
        for sup in config.get("supporting_evidence", []):
            for q in sup.get("search_queries", []):
                queries.append(q.replace("{company}", company))

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique[:12]  # Cap total queries
