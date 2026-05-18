"""KG-RAG — graph-traversal retrieval over the evidence graph (F3).

EmeraldMind 2025 method. Replaces flat top-K vector retrieval with 2-hop
graph traversal that prioritises edge types meaningfully:
    CONTRADICTS > EVIDENCED_BY > CITES > RELATED_TO

For each claim node we walk the evidence_graph (F3) 2 hops out, collect the
visited evidence/source nodes, then render them as typed triplets in the
prompt rather than blobs of text.

Feature-flagged behind ESG_USE_KG_RAG=1.

Public API:
    retrieve_for_claim(graph, claim_node_id, max_hops=2) -> List[RetrievedItem]
    render_as_triplets(items) -> str    # prompt-ready string
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RetrievedItem:
    node_id: str
    node_type: str
    label: str
    path: List[str] = field(default_factory=list)
    depth: int = 0
    evidence_score: float = 0.0
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id":        self.node_id,
            "node_type":      self.node_type,
            "label":          self.label,
            "path":           self.path,
            "depth":          self.depth,
            "evidence_score": self.evidence_score,
        }


# Edge priority for KG-RAG traversal — CONTRADICTS surfaces strongest signal,
# then direct evidence, then weak related-to.
_EDGE_PRIORITY = [
    "CONTRADICTS", "EVIDENCED_BY", "SUPPORTS", "CITES", "OWNS",
    "AFFECTS", "BINDS", "OPERATES", "RELATED_TO",
]


def is_enabled() -> bool:
    return os.environ.get("ESG_USE_KG_RAG", "").lower() in ("1", "true", "yes")


def retrieve_for_claim(
    graph: Any,  # core.evidence_graph.EvidenceGraph
    claim_node_id: str,
    max_hops: int = 2,
) -> List[RetrievedItem]:
    """Walk the evidence graph from `claim_node_id` up to `max_hops`.

    Returns ranked items: contradictions first, then supporting evidence,
    then citations and other context.
    """
    if not graph or not claim_node_id:
        return []
    from core.evidence_graph import EvidenceGraph, EdgeType
    if not isinstance(graph, EvidenceGraph):
        return []

    edge_priorities = [
        EdgeType.CONTRADICTS, EdgeType.EVIDENCED_BY, EdgeType.SUPPORTS,
        EdgeType.CITES, EdgeType.OWNS, EdgeType.AFFECTS,
        EdgeType.BINDS, EdgeType.OPERATES, EdgeType.RELATED_TO,
    ]
    visited = graph.traverse(claim_node_id, max_hops=max_hops, edge_priority=edge_priorities)
    items: List[RetrievedItem] = []
    for node_id, depth, path in visited:
        node = graph.get_node(node_id)
        if not node:
            continue
        # Use the inbound edge weight as a rough score
        evidence_score = 0.5
        if len(path) >= 2:
            edata = graph.g.get_edge_data(path[-2], path[-1]) or {}
            evidence_score = float(edata.get("weight") or 0.5)
            etype = edata.get("edge_type", "")
            # Boost contradictions
            if etype == "CONTRADICTS":
                evidence_score *= 1.5
        items.append(RetrievedItem(
            node_id=node_id,
            node_type=node.get("node_type", "?"),
            label=node.get("label", ""),
            path=path,
            depth=depth,
            evidence_score=round(evidence_score, 3),
            payload=node.get("payload", {}),
        ))

    # Rank: contradictions first (we kept ordering via priority list above),
    # then by depth ascending, then by score descending.
    items.sort(key=lambda x: (x.depth, -x.evidence_score))
    return items


def render_as_triplets(items: List[RetrievedItem], max_lines: int = 20) -> str:
    """Render retrieval as `(Subject) -[EDGE]-> (Object "...")` lines for LLM prompts."""
    lines: List[str] = []
    for item in items[:max_lines]:
        if len(item.path) < 2:
            continue
        src, dst = item.path[-2], item.path[-1]
        line = (
            f"({src}) -[hop={item.depth}, score={item.evidence_score}]-> "
            f"({dst} \"{(item.label or '')[:80]}\")"
        )
        lines.append(line)
    return "\n".join(lines)


def kg_rag_retrieve(state: Dict[str, Any]) -> Dict[str, Any]:
    """High-level entry: build graph from state, retrieve per claim.

    Returns:
      {claims: [{claim_id, retrieved: [...]}], total_items: N, status}
    """
    out: Dict[str, Any] = {
        "agent":      "kg_rag",
        "status":     "DISABLED",
        "claims":     [],
        "total_items": 0,
    }
    if not is_enabled():
        out["status"] = "DISABLED"
        return out

    try:
        from core.evidence_graph import build_from_state, EvidenceGraph, NodeType
        graph = build_from_state(state)
        # Store graph snapshot back into state for downstream consumers
        # (cross-pillar synthesizer, counterfactual)
        state["evidence_graph"] = graph.to_dict()
    except Exception as exc:
        out["status"] = "ERROR"
        out["error"] = str(exc)[:200]
        return out

    claim_ids = graph.nodes_of_type(NodeType.CLAIM)
    if not claim_ids:
        out["status"] = "NO_CLAIMS"
        return out
    for cid in claim_ids[:5]:
        items = retrieve_for_claim(graph, cid, max_hops=2)
        out["claims"].append({
            "claim_id":    cid,
            "retrieved":   [i.to_dict() for i in items[:10]],
            "triplets_text": render_as_triplets(items, max_lines=8),
        })
        out["total_items"] += len(items)
    out["status"] = "COMPLETED"
    return out
