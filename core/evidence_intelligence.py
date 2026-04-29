"""
core/evidence_intelligence.py
------------------------------
Fixes Problems #2 (Data Understanding), #3 (Signal/Noise), #12 (Attribution)

Replaces primitive keyword-matching with:
  - Semantic relevance scoring (claim ↔ evidence)
  - Tier-weighted evidence quality scoring
  - Evidence sufficiency checker with auto-escalation triggers
  - Conclusion-to-evidence linking for attribution
"""
from __future__ import annotations
import re, logging
from typing import Any, Dict, List, Tuple
from core.institutional_verifier import get_source_tier

logger = logging.getLogger(__name__)

# Tier multipliers: Tier 1 evidence is worth 4x Tier 4
TIER_WEIGHTS = {1: 4.0, 2: 3.0, 3: 1.5, 4: 1.0}

# Minimum weighted evidence score for decision-grade output
DECISION_GRADE_THRESHOLD = 12.0  # ~3 Tier-1 sources or 4 Tier-2 sources


def _tokenize(text: str) -> set:
    return {t for t in re.findall(r"[a-z]{3,}", text.lower()) if t not in {
        "the", "and", "for", "with", "that", "this", "from", "have", "are",
        "was", "were", "our", "their", "its", "into", "about", "more", "than",
        "will", "been", "being", "would", "could", "should", "also", "just",
    }}


def compute_relevance_score(claim: str, evidence_text: str) -> float:
    """Token-overlap relevance between claim and evidence. Returns 0.0-1.0."""
    claim_tokens = _tokenize(claim)
    ev_tokens = _tokenize(evidence_text)
    if not claim_tokens or not ev_tokens:
        return 0.0
    intersection = claim_tokens & ev_tokens
    # Jaccard-like but biased toward claim coverage
    claim_coverage = len(intersection) / max(1, len(claim_tokens))
    jaccard = len(intersection) / max(1, len(claim_tokens | ev_tokens))
    return round(0.6 * claim_coverage + 0.4 * jaccard, 3)


def score_evidence_quality(evidence_item: Dict[str, Any], claim: str = "") -> Dict[str, Any]:
    """
    Score a single evidence item on multiple quality dimensions.
    Returns enriched evidence with quality metadata.
    """
    tier = get_source_tier(evidence_item)
    tier_weight = TIER_WEIGHTS.get(tier, 1.0)

    text = str(
        evidence_item.get("relevant_text")
        or evidence_item.get("snippet")
        or evidence_item.get("title")
        or ""
    )

    # Relevance to claim
    relevance = compute_relevance_score(claim, text) if claim else 0.5

    # Recency signal
    date_str = str(evidence_item.get("date") or evidence_item.get("published_at") or "")
    has_recent_date = bool(re.search(r"202[3-9]|203\d", date_str))
    recency_score = 1.0 if has_recent_date else 0.5

    # Quantitative signal (numbers = more verifiable)
    has_numbers = bool(re.search(r"\d+\.?\d*\s*(%|tonne|MW|GW|million|billion|tCO2)", text, re.I))
    quant_score = 1.0 if has_numbers else 0.5

    # URL verifiability
    url = str(evidence_item.get("url") or "")
    has_url = bool(url and url.startswith("http"))
    url_score = 1.0 if has_url else 0.3

    # Composite quality score (0-10)
    quality = round(
        tier_weight * (0.35 * relevance + 0.25 * recency_score + 0.20 * quant_score + 0.20 * url_score),
        2
    )

    return {
        **evidence_item,
        "_quality_score": quality,
        "_tier": tier,
        "_tier_weight": tier_weight,
        "_relevance": relevance,
        "_recency": recency_score,
        "_quantitative": quant_score,
        "_has_url": has_url,
    }


def rank_evidence_by_quality(
    evidence: List[Dict[str, Any]], claim: str = ""
) -> List[Dict[str, Any]]:
    """Rank all evidence items by quality score, highest first."""
    scored = [score_evidence_quality(e, claim) for e in evidence if isinstance(e, dict)]
    scored.sort(key=lambda x: x.get("_quality_score", 0), reverse=True)
    return scored


def compute_evidence_sufficiency(
    evidence: List[Dict[str, Any]], claim: str = ""
) -> Dict[str, Any]:
    """
    Compute whether evidence is sufficient for decision-grade output.
    Returns sufficiency assessment with auto-escalation triggers.
    """
    scored = rank_evidence_by_quality(evidence, claim)
    total_weighted = sum(e.get("_quality_score", 0) for e in scored)
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for e in scored:
        t = e.get("_tier", 4)
        tier_counts[t] = tier_counts.get(t, 0) + 1

    high_relevance = sum(1 for e in scored if e.get("_relevance", 0) >= 0.3)

    # Decision logic
    is_sufficient = total_weighted >= DECISION_GRADE_THRESHOLD
    has_tier12 = (tier_counts[1] + tier_counts[2]) >= 2
    has_relevant = high_relevance >= 3

    escalation_triggers = []
    if not is_sufficient:
        escalation_triggers.append(f"Total weighted evidence ({total_weighted:.1f}) below threshold ({DECISION_GRADE_THRESHOLD})")
    if not has_tier12:
        escalation_triggers.append(f"Only {tier_counts[1]+tier_counts[2]} Tier 1-2 sources (need ≥2)")
    if not has_relevant:
        escalation_triggers.append(f"Only {high_relevance} claim-relevant items (need ≥3)")

    grade = "DECISION_GRADE" if (is_sufficient and has_tier12) else (
        "ADEQUATE" if is_sufficient else "INSUFFICIENT"
    )

    return {
        "grade": grade,
        "total_weighted_score": round(total_weighted, 2),
        "threshold": DECISION_GRADE_THRESHOLD,
        "tier_distribution": tier_counts,
        "high_relevance_count": high_relevance,
        "total_items": len(scored),
        "escalation_triggers": escalation_triggers,
        "needs_escalation": len(escalation_triggers) > 0,
        "top_3_sources": [
            {"source": e.get("source_name") or e.get("source", "Unknown"),
             "tier": e.get("_tier"), "quality": e.get("_quality_score")}
            for e in scored[:3]
        ],
    }


def filter_noise(
    evidence: List[Dict[str, Any]], claim: str, keep_top_n: int = 0
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Separate signal from noise. When sufficient Tier 1-2 evidence exists,
    deprioritize Tier 4 evidence to reduce dilution.
    Returns (signal, noise).
    """
    scored = rank_evidence_by_quality(evidence, claim)
    tier12_count = sum(1 for e in scored if e.get("_tier", 4) <= 2)

    if tier12_count >= 4:
        # Enough high-quality evidence — filter low-quality/irrelevant
        signal = [e for e in scored if e.get("_quality_score", 0) >= 1.5 or e.get("_tier", 4) <= 2]
        noise = [e for e in scored if e.get("_quality_score", 0) < 1.5 and e.get("_tier", 4) > 2]
    else:
        # Keep everything — we need all the evidence we can get
        signal = scored
        noise = []

    if keep_top_n > 0:
        signal = signal[:keep_top_n]

    return signal, noise


class ConclusionLinker:
    """Links each scoring conclusion to specific evidence items (Problem #12)."""

    def __init__(self):
        self.links: List[Dict[str, Any]] = []

    def link(self, conclusion: str, conclusion_type: str,
             evidence: List[Dict[str, Any]], claim: str = ""):
        """Find top evidence items that support a conclusion."""
        conclusion_tokens = _tokenize(conclusion)
        best = []
        for e in evidence:
            if not isinstance(e, dict):
                continue
            text = str(e.get("relevant_text") or e.get("snippet") or e.get("title") or "")
            ev_tokens = _tokenize(text)
            overlap = len(conclusion_tokens & ev_tokens)
            if overlap >= 2:
                best.append((overlap, e))
        best.sort(key=lambda x: x[0], reverse=True)
        top = best[:3]
        self.links.append({
            "conclusion": conclusion,
            "type": conclusion_type,
            "supporting_evidence": [
                {"source": e.get("source_name") or e.get("source", "?"),
                 "url": e.get("url", ""),
                 "text_preview": str(e.get("snippet") or e.get("relevant_text") or "")[:120],
                 "overlap_score": score}
                for score, e in top
            ],
            "evidence_count": len(top),
        })

    def to_dict(self) -> List[Dict[str, Any]]:
        return self.links
