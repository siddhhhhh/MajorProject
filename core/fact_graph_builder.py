"""
Fact-centric ESG graph builder.

Builds a lightweight, justification-centric graph from evidence and agent outputs
so downstream scoring can reason over structured facts instead of loose text only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re


HIGH_TRUST_SOURCE_TYPES = {
    "Government/Regulatory",
    "Government/International Data",
    "Legal/Court Documents",
    "Compliance/Sanctions Database",
    "UK/EU Regulatory",
    "NGO",
    "Climate NGO",
    "Supply Chain Database",
    "Tier-1 Financial Media",
}


def _safe_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and 1900 <= value <= 2100:
        return value
    text = str(value)
    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return None
    year = int(match.group(0))
    return year if 1900 <= year <= 2100 else None


def _pillar_from_text(text: str) -> str:
    """Classify a fact into E / S / G / O (Other) based on keyword density.

    Previously this function defaulted ties (and zero-hit text) to "E",
    which created reports where Social and Governance pillar coverage was
    artificially zero — every news headline / regulatory snippet got tagged
    Environmental even when it had no E content. The fix:
      - Expanded keyword lists per pillar.
      - "O" (Other) bucket when no pillar gets at least 1 hit.
      - Tie-break uses a small E-bias only when E has at least 1 hit (not
        when all are zero).
    """
    low = text.lower()
    env_kws = [
        "carbon", "emission", "co2", "ghg", "greenhouse",
        "water", "climate", "waste", "energy", "renewable",
        "pollution", "biodiversity", "deforestation", "circular",
        "recycl", "scope 1", "scope 2", "scope 3", "tCO2e", "tco2e",
        "net zero", "net-zero", "decarboniz",
    ]
    soc_kws = [
        "labor", "labour", "employee", "worker", "workforce",
        "human rights", "community", "safety", "diversity", "inclusion",
        "gender", "minority", "wage", "wages", "training", "engagement",
        "stakeholder", "supply chain", "supplier",
        "child labor", "modern slavery", "indigenous",
    ]
    gov_kws = [
        "board", "audit", "governance", "ethics", "corruption",
        "bribery", "compliance", "transparency", "disclosure",
        "executive pay", "ceo", "shareholder", "voting", "whistleblow",
        "fraud", "settlement", "lawsuit", "fine", "penalty",
        "regulatory", "enforcement", "tax", "lobbying",
    ]
    env_hits = sum(1 for kw in env_kws if kw in low)
    soc_hits = sum(1 for kw in soc_kws if kw in low)
    gov_hits = sum(1 for kw in gov_kws if kw in low)

    if env_hits == 0 and soc_hits == 0 and gov_hits == 0:
        return "O"  # Other / unclassified — don't pollute E
    # Strict argmax (no E-bias on ties when other pillars also have hits).
    if env_hits > soc_hits and env_hits > gov_hits:
        return "E"
    if soc_hits > env_hits and soc_hits > gov_hits:
        return "S"
    if gov_hits > env_hits and gov_hits > soc_hits:
        return "G"
    # Tie: choose the pillar with at least one hit, prefer S then G then E.
    # This rebalances away from the prior E-dominance default.
    if soc_hits >= 1:
        return "S"
    if gov_hits >= 1:
        return "G"
    return "E"


def _fact_polarity(text: str) -> str:
    low = text.lower()
    negative_markers = [
        "violation",
        "fine",
        "penalty",
        "lawsuit",
        "investigation",
        "non-compliance",
        "breach",
        "greenwashing",
        "controversy",
    ]
    if any(token in low for token in negative_markers):
        return "negative"
    return "neutral_or_positive"


def _verifiability_score(text: str, source_type: str, url: str) -> float:
    score = 0.25
    if url:
        score += 0.25
    if source_type in HIGH_TRUST_SOURCE_TYPES:
        score += 0.25
    if any(ch.isdigit() for ch in text):
        score += 0.15
    if len(text) >= 80:
        score += 0.10
    return round(min(1.0, score), 3)


def _token_set(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-zA-Z]{4,}", text.lower())}


def _extract_base_evidence(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for idx, ev in enumerate(evidence, start=1):
        if not isinstance(ev, dict):
            continue
        top_text = str(ev.get("relevant_text") or ev.get("snippet") or ev.get("content") or "").strip()
        if top_text:
            records.append(
                {
                    "source_id": ev.get("source_id") or ev.get("id") or f"ev_{idx}",
                    "text": top_text,
                    "url": str(ev.get("url") or ev.get("link") or "").strip(),
                    "source": str(ev.get("source_name") or ev.get("source") or "Unknown"),
                    "source_type": str(ev.get("source_type") or ""),
                    "year": _safe_year(ev.get("year") or ev.get("date")),
                }
            )

        nested = ev.get("evidence", [])
        if not isinstance(nested, list):
            continue
        for n_idx, item in enumerate(nested, start=1):
            if not isinstance(item, dict):
                continue
            text = str(item.get("relevant_text") or item.get("snippet") or "").strip()
            if not text:
                continue
            records.append(
                {
                    "source_id": item.get("source_id") or item.get("id") or f"ev_{idx}_{n_idx}",
                    "text": text,
                    "url": str(item.get("url") or ev.get("url") or "").strip(),
                    "source": str(item.get("source_name") or ev.get("source_name") or ev.get("source") or "Unknown"),
                    "source_type": str(item.get("source_type") or ev.get("source_type") or ""),
                    "year": _safe_year(item.get("year") or item.get("date") or ev.get("year") or ev.get("date")),
                }
            )
    return records


def build_esg_fact_graph(
    company: str,
    claim_text: str,
    evidence: List[Dict[str, Any]],
    contradictions: List[Dict[str, Any]] | None = None,
    temporal_consistency: Dict[str, Any] | None = None,
    normalized_sg_evidence: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    contradictions = contradictions or []
    temporal_consistency = temporal_consistency or {}
    normalized_sg_evidence = normalized_sg_evidence or {}

    records = _extract_base_evidence(evidence if isinstance(evidence, list) else [])
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    facts: List[Dict[str, Any]] = []

    claim_id = "claim_root"
    nodes.append(
        {
            "id": claim_id,
            "node_type": "claim",
            "text": claim_text or "",
            "company": company or "",
        }
    )

    claim_tokens = _token_set(claim_text or "")
    # "O" = Other (unclassified) — separates non-ESG general business
    # mentions from genuine Environmental hits, which previously bloated
    # the E pillar to 100% on text without any sustainability terms.
    pillar_counter = {"E": 0, "S": 0, "G": 0, "O": 0}
    linked_count = 0

    for idx, rec in enumerate(records[:200], start=1):
        text = rec.get("text", "")
        if not text:
            continue
        fact_id = f"fact_{idx}"
        source_id = f"source_{idx}"
        pillar = _pillar_from_text(text)
        pillar_counter[pillar] += 1
        score = _verifiability_score(text, rec.get("source_type", ""), rec.get("url", ""))
        polarity = _fact_polarity(text)

        fact_node = {
            "id": fact_id,
            "node_type": "fact",
            "text": text,
            "pillar": pillar,
            "polarity": polarity,
            "verifiability_score": score,
            "year": rec.get("year"),
        }
        source_node = {
            "id": source_id,
            "node_type": "source",
            "source_name": rec.get("source", "Unknown"),
            "source_type": rec.get("source_type", ""),
            "url": rec.get("url", ""),
        }

        nodes.append(fact_node)
        nodes.append(source_node)
        edges.append({"from": fact_id, "to": source_id, "relation": "sourced_from", "weight": score})

        overlap = len(claim_tokens.intersection(_token_set(text)))
        if overlap >= 2:
            linked_count += 1
            edges.append({"from": claim_id, "to": fact_id, "relation": "supported_by", "weight": min(1.0, overlap / 6.0)})

        facts.append(
            {
                "fact_id": fact_id,
                "text": text,
                "pillar": pillar,
                "polarity": polarity,
                "year": rec.get("year"),
                "source_id": source_id,
                "source_name": rec.get("source", "Unknown"),
                "source_type": rec.get("source_type", ""),
                "url": rec.get("url", ""),
                "verifiability_score": score,
            }
        )

    contradiction_count = 0
    for c_idx, row in enumerate(contradictions[:60], start=1):
        if not isinstance(row, dict):
            continue
        verdict = str(row.get("overall_verdict") or "").strip() or "Unknown"
        text = str(row.get("claim_text") or row.get("description") or row.get("reasoning") or "").strip()
        if not text:
            continue
        contradiction_count += 1
        fact_id = f"contradiction_{c_idx}"
        nodes.append(
            {
                "id": fact_id,
                "node_type": "contradiction_fact",
                "text": text,
                "verdict": verdict,
                "pillar": _pillar_from_text(text),
            }
        )
        edges.append({"from": claim_id, "to": fact_id, "relation": "challenged_by", "weight": 1.0})

    temporal_flags = 0
    temporal_evidence = temporal_consistency.get("evidence", []) if isinstance(temporal_consistency, dict) else []
    if isinstance(temporal_evidence, list):
        for t_idx, item in enumerate(temporal_evidence[:30], start=1):
            text = str(item).strip()
            if not text:
                continue
            temporal_flags += 1
            node_id = f"temporal_{t_idx}"
            nodes.append({"id": node_id, "node_type": "temporal_fact", "text": text, "pillar": _pillar_from_text(text)})
            edges.append({"from": claim_id, "to": node_id, "relation": "time_consistency_check", "weight": 0.8})

    verified_fact_count = sum(1 for f in facts if float(f.get("verifiability_score", 0)) >= 0.6)
    sg_facts = normalized_sg_evidence.get("normalized_facts", []) if isinstance(normalized_sg_evidence, dict) else []
    if isinstance(sg_facts, list):
        for s_idx, row in enumerate(sg_facts[:160], start=1):
            if not isinstance(row, dict):
                continue
            node_id = f"sg_fact_{s_idx}"
            verifiability = 0.85 if row.get("evidence_state") == "verified_evidence" else 0.45
            nodes.append(
                {
                    "id": node_id,
                    "node_type": "normalized_fact",
                    "pillar": "S" if row.get("pillar") == "social" else "G",
                    "indicator_name": row.get("indicator_name"),
                    "track": row.get("track"),
                    "evidence_state": row.get("evidence_state"),
                    "trust_level": row.get("trust_level"),
                    "text": row.get("text", ""),
                    "year": row.get("year"),
                }
            )
            edges.append({"from": claim_id, "to": node_id, "relation": "normalized_support", "weight": verifiability})
        verified_fact_count += sum(1 for row in sg_facts if isinstance(row, dict) and row.get("evidence_state") == "verified_evidence")
        linked_count += sum(1 for row in sg_facts if isinstance(row, dict) and row.get("claim_linked"))
    sg_summary = normalized_sg_evidence.get("summary", {}) if isinstance(normalized_sg_evidence.get("summary"), dict) else {}
    summary = {
        "fact_count": len(facts),
        "verified_fact_count": verified_fact_count,
        "claim_linked_fact_count": linked_count,
        "contradiction_fact_count": contradiction_count,
        "temporal_fact_count": temporal_flags,
        "coverage_by_pillar": pillar_counter,
        "normalized_sg_fact_count": int(sg_summary.get("normalized_fact_count", 0) or 0),
        "social_evidence_state": sg_summary.get("social_evidence_state", "insufficient_evidence"),
        "governance_evidence_state": sg_summary.get("governance_evidence_state", "insufficient_evidence"),
        "graph_density": round(len(edges) / max(1, len(nodes)), 3),
        "is_decision_ready": bool(sg_summary.get("overall_ready", False)) if sg_summary else bool(verified_fact_count >= 4 and linked_count >= 1),
    }

    return {
        "company": company,
        "claim_text": claim_text,
        "nodes": nodes,
        "edges": edges,
        "facts": facts,
        "summary": summary,
    }
