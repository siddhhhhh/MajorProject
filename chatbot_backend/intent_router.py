"""
intent_router.py
----------------
Intent detection and field extraction for the ESG Analyst Copilot.

No RAG. No chunking. Pure field routing over get_esg_context() output.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Intent taxonomy
# ---------------------------------------------------------------------------

class Intent:
    SCORE       = "score"
    SCORE_EXPLANATION = "score_explanation"
    EVIDENCE    = "evidence"
    CONTRADICTION = "contradiction"
    REGULATORY  = "regulatory"
    CARBON      = "carbon"
    AGENT       = "agent"
    SUMMARY     = "summary"
    UNKNOWN     = "unknown"


_INTENT_KEYWORDS: dict[str, list[str]] = {
    Intent.SCORE_EXPLANATION: [
        "why is score", "explain score", "explain risk", "reason for score", 
        "driver", "what makes the score", "why high", "why low", "why bad",
    ],
    Intent.SCORE: [
        "score", "rating", "esg score", "greenwashing score", "tier",
        "grade", "environmental", "social", "governance", "pillar",
        "how bad", "how good", "performance",
    ],
    Intent.EVIDENCE: [
        "evidence", "source", "proof", "support", "document", "substantiat",
        "referenced", "cited", "url", "report", "disclosure",
    ],
    Intent.CONTRADICTION: [
        "contradict", "inconsist", "conflict", "discrepan", "mismatch",
        "greenwash", "mislead", "false claim", "dispute",
    ],
    Intent.REGULATORY: [
        "regulat", "compliance", "framework", "gap", "violation", "sbti",
        "fca", "ghg protocol", "gri", "csrd", "sebi", "brsr", "sec",
        "enforcement", "litigation", "penalty", "ipcc",
    ],
    Intent.CARBON: [
        "carbon", "scope 1", "scope 2", "scope 3", "emission", "co2",
        "ghg", "net zero", "net-zero", "pathway", "tco2", "tonne",
    ],
    Intent.AGENT: [
        "agent", "greenwishing", "climatebert", "adversarial", "explainab",
        "commitment ledger", "carbon pathway", "claim decompos", "social agent",
        "governance agent", "regulatory agent", "temporal",
    ],
    Intent.SUMMARY: [
        "summary", "summar", "overview", "verdict", "conclusion", "bottom line",
        "tldr", "tl;dr", "overall", "assess", "result", "finding",
    ],
}


import re

def detect_intents(question: str) -> list[str]:
    """Return all detected intents for the given question."""
    lowered = question.lower()
    detected = []
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            detected.append(intent)
    if not detected:
        return [Intent.UNKNOWN]
    return detected


def match_sections(query: str, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Smart match user query to TXT sections using keywords and tags."""
    lowered = query.lower()
    query_words = set(re.findall(r'\w+', lowered))
    
    scored_sections = []
    for sec in sections:
        score = 0
        
        title_lower = sec["title"].lower()
        title_words = set(re.findall(r'\w+', title_lower))
        
        # Word overlap with title
        overlap = query_words.intersection(title_words)
        score += len(overlap) * 5
        
        # Tags match
        for tag in sec.get("tags", []):
            if tag in query_words:
                score += 10
                
        if score > 0:
            scored_sections.append((score, sec))
            
    # Sort and take top 2
    scored_sections.sort(key=lambda x: x[0], reverse=True)
    return [sec for _, sec in scored_sections[:2]]


# ---------------------------------------------------------------------------
# Field selector — returns only the context fields relevant to the intent
# ---------------------------------------------------------------------------

def select_relevant_context(
    intents: list[str],
    ctx: dict[str, Any],
    matched_sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Return a MINIMAL dict of only the fields needed for the given intents,
    along with any smartly matched sections.
    """
    # Fields always included (lightweight header)
    header = {
        "company":    ctx.get("company"),
        "industry":   ctx.get("industry"),
        "claim":      ctx.get("claim"),
        "confidence": ctx.get("confidence"),
    }
    
    merged = {**header}
    if matched_sections:
        merged["matched_sections"] = matched_sections

    for intent in intents:
        if intent == Intent.SCORE_EXPLANATION:
            merged["score"] = ctx.get("score")
            merged["contradictions"] = ctx.get("contradictions", [])
            merged["regulatory_gaps"] = ctx.get("regulatory_gaps", [])
            # Try to grab Key Drivers (Section 6 typically) or sections tagged 'scores'
            if "matched_sections" not in merged:
                merged["matched_sections"] = []
            for sec in ctx.get("sections", []):
                sec_lower = (sec["title"] + " " + sec["section_id"]).lower()
                if "driver" in sec_lower or "section 6" in sec_lower or "score" in sec_lower:
                    if sec not in merged["matched_sections"]:
                        merged["matched_sections"].append(sec)
        
        if intent == Intent.SCORE:
            merged["score"] = ctx.get("score")
            merged["verdict"] = ctx.get("verdict")

        if intent == Intent.EVIDENCE:
            merged["evidence"] = ctx.get("evidence", [])[:10]
            merged["verdict"] = ctx.get("verdict")

        if intent == Intent.CONTRADICTION:
            merged["contradictions"] = ctx.get("contradictions", [])
            merged["verdict"] = ctx.get("verdict")
            merged.setdefault("agent_insights", {})
            for k, v in (ctx.get("agent_insights") or {}).items():
                if any(x in k.lower() for x in ["contradict", "mismatch", "greenwish", "adversarial"]):
                    merged["agent_insights"][k] = v

        if intent == Intent.REGULATORY:
            merged["regulatory_gaps"] = ctx.get("regulatory_gaps", [])
            merged["compliance"] = (ctx.get("score") or {}).get("compliance_risk_level")
            merged["compliance_gap_count"] = (ctx.get("score") or {}).get("compliance_gap_count")
            merged.setdefault("agent_insights", {})
            for k, v in (ctx.get("agent_insights") or {}).items():
                if "regulat" in k.lower() or "compliance" in k.lower():
                    merged["agent_insights"][k] = v

        if intent == Intent.CARBON:
            merged["carbon_data"] = ctx.get("carbon_data")
            merged.setdefault("agent_insights", {})
            for k, v in (ctx.get("agent_insights") or {}).items():
                if "carbon" in k.lower() or "pathway" in k.lower():
                    merged["agent_insights"][k] = v

        if intent == Intent.AGENT:
            if "agent_insights" not in merged:
                merged["agent_insights"] = ctx.get("agent_insights", {})

        if intent == Intent.SUMMARY:
            merged["score"] = ctx.get("score")
            merged["verdict"] = ctx.get("verdict")
            merged["contradictions"] = ctx.get("contradictions", [])[:5]
            merged["regulatory_gaps"] = ctx.get("regulatory_gaps", [])[:5]

    if Intent.UNKNOWN in intents and len(intents) == 1:
        merged["score"] = ctx.get("score")
        merged["verdict"] = ctx.get("verdict")

    return merged
