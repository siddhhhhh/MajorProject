"""SURE-RAG style abstention — explicit "we couldn't verify this" decisions.

Inspired by SURE-RAG (2025): when the retrieved evidence has insufficient
coverage / source diversity / semantic relevance, the right answer is to
*abstain* rather than guess. Abstention is honest; hallucination is not.

Per-claim abstention rules:

  ABSTAIN_INSUFFICIENT_SOURCES   < 2 independent sources
  ABSTAIN_LOW_TIER               No Tier 1-2 source AND no quantitative target match
  ABSTAIN_LOW_RELEVANCE          No evidence with semantic overlap >= MIN_RELEVANCE
  PROCEED                        Coverage thresholds satisfied

The thresholds are conservative on purpose — for a demo it is better to
under-claim verification than to fabricate it.

This module is read-only and never calls an LLM.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Tunable thresholds — strict for demo. Lower MIN_RELEVANCE if abstention
# rate is too high in real-world runs.
# Note: relevance scale is bge-small cosine [0,1]. 0.30 ≈ weak topical match.
MIN_INDEPENDENT_SOURCES = 2
MIN_TIER12_SOURCES = 1
MIN_RELEVANCE = 0.30
QUANT_TARGET_RELAX_THRESHOLD = 0.20  # quantitative targets need slightly less semantic overlap


def _tokenise(text: str) -> set[str]:
    if not text:
        return set()
    return {
        t for t in re.findall(r"[a-z0-9]{3,}", text.lower())
        if t not in {
            "the", "and", "for", "with", "from", "that", "this",
            "have", "will", "are", "our", "its",
        }
    }


def _jaccard_relevance(claim_text: str, evidence_text: str) -> float:
    """Symmetric token-overlap fallback used when embeddings are unavailable.

    The original asymmetric `inter / len(claim)` form returned 0.0 for any
    paraphrase whose tokens didn't overlap with the claim — which is exactly
    why every sub-claim showed best_relevance=0.0 on Windows runs where
    sentence_transformers is disabled. The symmetric Jaccard + small lexical
    boost keeps the score positive whenever there's *any* shared vocabulary.
    """
    c = _tokenise(claim_text)
    e = _tokenise(evidence_text)
    if not c or not e:
        return 0.0
    inter = len(c & e)
    if inter == 0:
        return 0.0
    union = len(c | e)
    jaccard = inter / union if union else 0.0
    # Boost slightly toward the claim side so a paragraph that fully covers
    # the claim vocabulary scores closer to a real semantic match.
    coverage = inter / len(c)
    return min(1.0, 0.5 * jaccard + 0.5 * coverage)


def _relevance(claim_text: str, evidence_text: str) -> float:
    """Semantic similarity between claim and evidence.

    Strategy:
      1. Try the F2 embedding cache (bge-small cosine).
      2. If the embedding pipeline is degraded (model not loaded → zero
         vectors → cosine ≈ 0.0), fall back to the symmetric Jaccard
         relevance so abstention isn't triggered for every sub-claim.
    """
    try:
        from core.embed_cache import similarity as _emb_sim
        score = float(_emb_sim(claim_text, evidence_text))
    except Exception:
        score = 0.0
    # bge-small on real text rarely returns exactly 0.0 — that value almost
    # always means encode() returned a zero vector (model unavailable). Use
    # the lexical fallback so the abstention layer keeps working.
    if score <= 0.0:
        return _jaccard_relevance(claim_text, evidence_text)
    return min(1.0, max(0.0, score))


def _evidence_text(ev: Dict[str, Any]) -> str:
    if not isinstance(ev, dict):
        return ""
    return " ".join(str(ev.get(k) or "") for k in (
        "title", "snippet", "relevant_text", "text", "summary"
    ))


def _domain(ev: Dict[str, Any]) -> str:
    """Crude source key for independence counting."""
    if not isinstance(ev, dict):
        return ""
    src = ev.get("source_name") or ev.get("source") or ""
    if not src:
        url = str(ev.get("url") or "")
        m = re.match(r"https?://([^/]+)/?", url)
        src = m.group(1) if m else url[:40]
    return str(src).strip().lower()


def _tier(ev: Dict[str, Any]) -> int:
    """Best-effort tier read; default to 4 when unknown."""
    if not isinstance(ev, dict):
        return 4
    t = ev.get("reliability_tier") or ev.get("_tier") or ev.get("tier")
    if isinstance(t, int):
        return t
    if isinstance(t, str):
        tl = t.strip().lower()
        if "tier 1" in tl or tl == "1":
            return 1
        if "tier 2" in tl or tl == "2":
            return 2
        if "tier 3" in tl or tl == "3":
            return 3
    return 4


def evaluate_claim(
    claim_text: str,
    evidence: List[Dict[str, Any]],
    claim_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Decide ABSTAIN/PROCEED for a single claim.

    Returns dict with status + reasons + counts so the caller can both
    render the decision and surface diagnostic info.
    """
    if not isinstance(evidence, list):
        evidence = []

    # Tier counts — keyed by tier AND by unique domain so tier12 can never
    # exceed independent_sources (the bug that surfaced as
    # `sources=18 tier12=33` in the JPMorgan report came from counting raw
    # evidence rows instead of distinct Tier-1/2 domains).
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    tier_domains: Dict[int, set[str]] = {1: set(), 2: set(), 3: set(), 4: set()}
    domains: set[str] = set()
    best_relevance = 0.0
    relevance_per_ev: List[float] = []

    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        t = _tier(ev)
        tier_counts[t] = tier_counts.get(t, 0) + 1
        d = _domain(ev)
        if d:
            domains.add(d)
            tier_domains.setdefault(t, set()).add(d)
        r = _relevance(claim_text, _evidence_text(ev))
        relevance_per_ev.append(r)
        best_relevance = max(best_relevance, r)

    independent_sources = len(domains)
    tier12 = len(tier_domains[1] | tier_domains[2])
    if tier12 > independent_sources:
        raise ValueError(
            f"tier12 ({tier12}) exceeded independent_sources ({independent_sources}) "
            f"for claim {claim_text[:60]!r} — invariant violated"
        )
    is_quant = (claim_type or "").lower() in (
        "quantitative_target", "quantitative", "alignment_claim"
    )
    relevance_floor = (
        QUANT_TARGET_RELAX_THRESHOLD if is_quant else MIN_RELEVANCE
    )

    abstention_reasons: List[str] = []
    if independent_sources < MIN_INDEPENDENT_SOURCES:
        abstention_reasons.append(
            f"only_{independent_sources}_independent_sources"
            f"(need_{MIN_INDEPENDENT_SOURCES})"
        )
    if tier12 < MIN_TIER12_SOURCES:
        abstention_reasons.append(
            f"no_tier12_source(need_{MIN_TIER12_SOURCES})"
        )
    if best_relevance < relevance_floor:
        abstention_reasons.append(
            f"best_relevance_{best_relevance:.2f}_below_{relevance_floor:.2f}"
        )

    if abstention_reasons:
        status = "ABSTAIN_INSUFFICIENT_EVIDENCE"
    else:
        status = "PROCEED"

    return {
        "claim_text": claim_text[:200],
        "claim_type": claim_type,
        "status": status,
        "reasons": abstention_reasons,
        "independent_sources": independent_sources,
        "tier12_sources": tier12,
        "tier_counts": tier_counts,
        "best_relevance": round(best_relevance, 3),
        "evidence_count": len(evidence),
    }


def evaluate_subclaims(
    sub_claims: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run evaluate_claim across a list of sub-claims and aggregate."""
    out_per_claim: List[Dict[str, Any]] = []
    for sc in sub_claims:
        if not isinstance(sc, dict):
            continue
        text = sc.get("text") or sc.get("claim") or ""
        ctype = sc.get("type") or sc.get("claim_type")
        decision = evaluate_claim(text, evidence, claim_type=ctype)
        decision["sub_claim_id"] = sc.get("id")
        decision["measurable"] = bool(sc.get("measurable"))
        out_per_claim.append(decision)

    total = len(out_per_claim)
    abstained = sum(1 for d in out_per_claim if d["status"].startswith("ABSTAIN"))
    return {
        "per_claim": out_per_claim,
        "total_subclaims": total,
        "abstained_count": abstained,
        "proceeded_count": total - abstained,
        "abstention_rate_pct": round(abstained / total * 100, 1) if total else 0.0,
        "thresholds": {
            "min_independent_sources": MIN_INDEPENDENT_SOURCES,
            "min_tier12_sources": MIN_TIER12_SOURCES,
            "min_relevance": MIN_RELEVANCE,
            "quant_target_relax_threshold": QUANT_TARGET_RELAX_THRESHOLD,
        },
    }


def _regulatory_tier1_credits(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Materialise synthetic Tier-1 evidence rows for verified regulatory
    filings already surfaced by ``regulatory_scanning``.

    A 10-K filed against SEC EDGAR is a definitional Tier-1 source. Without
    this credit, a US filer whose entire evidence pool is web/news (Tier 3)
    forces abstention even though the regulatory scanner has already
    confirmed an authoritative filing. Each credit row is tagged
    ``_origin=regulatory_credit`` so downstream consumers can distinguish
    it from a primary-retrieval evidence row.

    Recognised Tier-1 sources (government registries + mandatory filings):
      - SEC EDGAR (10-K, 20-F, DEF 14A)
      - SBTi (Science Based Targets) registry
      - CDP A-list
      - EU ESEF mandatory filings
      - SEBI BRSR (India)
      - FTC Enforcement Database
      - FSB-TCFD (when verified by registry, not self-attestation)
    """
    reg = state.get("regulatory_scanning") or {}
    # The agent's output shape varies between top-level and nested ``output``.
    if isinstance(reg, dict) and "frameworks" not in reg and isinstance(reg.get("output"), dict):
        reg = reg["output"]
    frameworks = (reg or {}).get("frameworks") or (reg or {}).get("compliance_result", {}).get("frameworks") or []
    if not isinstance(frameworks, list):
        return []

    tier1_sources = {
        "sec edgar",
        "sbti",
        "science based targets initiative",
        "cdp",
        "eu esef",
        "sebi brsr",
        "ftc enforcement db",
        "ftc",
    }
    credits: List[Dict[str, Any]] = []
    for row in frameworks:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").lower()
        if status != "compliant":
            continue
        if not row.get("real_data", True):  # heuristic-only rows are not Tier-1
            continue
        source_name = str(row.get("source_name") or "").lower()
        if not any(s in source_name for s in tier1_sources):
            continue
        credits.append({
            "title": f"{row.get('framework')} — verified by {row.get('source_name')}",
            "snippet": str(row.get("specific_violation") or row.get("evidence") or "")[:500],
            "url": row.get("evidence_url") or "",
            "source_name": row.get("source_name"),
            "reliability_tier": 1,
            "_tier": 1,
            "_origin": "regulatory_credit",
            "framework": row.get("framework"),
        })
    return credits


def evaluate_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Apply abstention checks to a pipeline state dict.

    Reads:
      - state['claim_decomposition']['sub_claims'] (list of dicts)
      - state['evidence']                          (list of dicts)
      - state['regulatory_scanning']               (for Tier-1 registry credits)
    """
    decomposition = state.get("claim_decomposition") or {}
    sub_claims = (
        decomposition.get("sub_claims") if isinstance(decomposition, dict) else []
    )
    if not isinstance(sub_claims, list) or not sub_claims:
        return {
            "per_claim": [],
            "total_subclaims": 0,
            "abstained_count": 0,
            "proceeded_count": 0,
            "abstention_rate_pct": 0.0,
            "note": "no sub_claims found in claim_decomposition",
        }

    evidence = list(state.get("evidence") or [])
    # Fix #13: credit verified regulatory filings (SEC 10-K, SBTi, CDP A-list,
    # ...) toward the Tier-1/2 counter. Without this, Chevron's 11 web
    # evidence rows + a verified SEC 10-K filing still abstained (tier12=0).
    regulatory_credits = _regulatory_tier1_credits(state)
    if regulatory_credits:
        evidence = evidence + regulatory_credits

    result = evaluate_subclaims(sub_claims, evidence)
    # Surface the credit derivation for the diagnostics appendix.
    if regulatory_credits:
        result["regulatory_credits_applied"] = [
            {"framework": c.get("framework"), "source": c.get("source_name")}
            for c in regulatory_credits
        ]
    return result


def format_abstention_text(result: Dict[str, Any], indent: str = "  ") -> List[str]:
    """Render a text block for the report's abstention section."""
    lines: List[str] = []
    total = result.get("total_subclaims", 0)
    abstained = result.get("abstained_count", 0)
    rate = result.get("abstention_rate_pct", 0.0)

    if total == 0:
        lines.append(f"{indent}No sub-claims were decomposed for this run.")
        return lines

    lines.append(
        f"{indent}Sub-claims evaluated: {total} | "
        f"abstained: {abstained} ({rate}%) | "
        f"proceeded: {result.get('proceeded_count', 0)}"
    )
    th = result.get("thresholds") or {}
    if th:
        lines.append(
            f"{indent}Thresholds: "
            f">={th.get('min_independent_sources')} independent sources, "
            f">={th.get('min_tier12_sources')} Tier 1-2 source, "
            f"relevance >= {th.get('min_relevance')}."
        )
    lines.append("")

    for d in result.get("per_claim", []) or []:
        sid = d.get("sub_claim_id", "?")
        st = d.get("status", "?")
        txt = (d.get("claim_text") or "")[:80].replace("\n", " ")
        prefix = "[ABSTAIN]" if st.startswith("ABSTAIN") else "[PROCEED]"
        lines.append(f"{indent}  {sid:<4} {prefix:<10} {txt}")
        if st.startswith("ABSTAIN"):
            for r in d.get("reasons", []):
                lines.append(f"{indent}         reason: {r}")
            lines.append(
                f"{indent}         sources={d.get('independent_sources')} "
                f"tier12={d.get('tier12_sources')} "
                f"best_rel={d.get('best_relevance')}"
            )
    return lines
