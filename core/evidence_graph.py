"""Evidence Graph Store — typed graph layer over claims/evidence/companies.

Why this exists:
  Flat evidence lists can't express *who-said-what*, *contradicts-with*, or
  *evidenced-by*. KG-RAG (P10), cross-pillar contradiction (P8), counterfactual
  analysis (P1), and subsidiary walks (P6) all need graph semantics.

Design:
  - NetworkX DiGraph in-process (no DB)
  - Strongly-typed nodes + edges (enums)
  - JSON-serialisable adjacency so state passes through LangGraph cleanly
  - Methods are atomic and side-effect-free at the data layer

Node types:
    Company      — parent or subsidiary; keyed by LEI when available
    Claim        — extracted from text (links to ClaimDecomposition.sub_claim)
    Evidence     — retrieved document / chunk / API row
    Source       — domain / publisher (e.g. reuters.com, GLEIF, regulatory filings)
    Promise      — quantified target (subset of Claim with target_year/metric)
    Event        — GDELT / news event
    Case         — litigation docket
    Asset        — physical facility (Climate TRACE asset)

Edge types:
    OWNS              Company -> Subsidiary
    SAYS              Company -> Claim                (parent emits claim)
    EVIDENCED_BY      Claim   -> Evidence             (claim X has evidence Y)
    CITES             Evidence -> Source              (URL/domain back-ref)
    CONTRADICTS       Claim   -> Claim | Evidence     (mutual exclusion)
    SUPPORTS          Evidence -> Claim               (positive stance)
    PROMISES          Company -> Promise              (claim of intent)
    AFFECTS           Event   -> Company | Subsidiary
    BINDS             Case    -> Company              (litigation tied to entity)
    OPERATES          Company -> Asset                (facility ownership)

The graph is built per-run from already-resolved upstream artifacts; it's not
a global persistent KG (we have `company_knowledge_graph` for that). Think of
it as the *deduction substrate* the cross-pillar and KG-RAG passes traverse.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import networkx as nx

logger = logging.getLogger(__name__)


# ── Type system ───────────────────────────────────────────────────────────────
class NodeType(str, Enum):
    COMPANY = "Company"
    SUBSIDIARY = "Subsidiary"
    CLAIM = "Claim"
    EVIDENCE = "Evidence"
    SOURCE = "Source"
    PROMISE = "Promise"
    EVENT = "Event"
    CASE = "Case"
    ASSET = "Asset"


class EdgeType(str, Enum):
    OWNS = "OWNS"
    SAYS = "SAYS"
    EVIDENCED_BY = "EVIDENCED_BY"
    CITES = "CITES"
    CONTRADICTS = "CONTRADICTS"
    SUPPORTS = "SUPPORTS"
    PROMISES = "PROMISES"
    AFFECTS = "AFFECTS"
    BINDS = "BINDS"
    OPERATES = "OPERATES"
    RELATED_TO = "RELATED_TO"


# Allowed (source -> target) NodeType pairs per EdgeType. Enforced at add-edge
# time so callers can't quietly introduce nonsense like Claim-OWNS-Asset.
_ALLOWED_EDGE_SCHEMA: Dict[EdgeType, Tuple[Set[NodeType], Set[NodeType]]] = {
    EdgeType.OWNS:         ({NodeType.COMPANY}, {NodeType.SUBSIDIARY, NodeType.COMPANY}),
    EdgeType.SAYS:         ({NodeType.COMPANY, NodeType.SUBSIDIARY}, {NodeType.CLAIM, NodeType.PROMISE}),
    EdgeType.EVIDENCED_BY: ({NodeType.CLAIM, NodeType.PROMISE}, {NodeType.EVIDENCE}),
    EdgeType.CITES:        ({NodeType.EVIDENCE}, {NodeType.SOURCE}),
    EdgeType.CONTRADICTS:  ({NodeType.CLAIM, NodeType.EVIDENCE, NodeType.PROMISE},
                            {NodeType.CLAIM, NodeType.EVIDENCE, NodeType.PROMISE}),
    EdgeType.SUPPORTS:     ({NodeType.EVIDENCE}, {NodeType.CLAIM, NodeType.PROMISE}),
    EdgeType.PROMISES:     ({NodeType.COMPANY, NodeType.SUBSIDIARY}, {NodeType.PROMISE}),
    EdgeType.AFFECTS:      ({NodeType.EVENT}, {NodeType.COMPANY, NodeType.SUBSIDIARY}),
    EdgeType.BINDS:        ({NodeType.CASE}, {NodeType.COMPANY, NodeType.SUBSIDIARY}),
    EdgeType.OPERATES:     ({NodeType.COMPANY, NodeType.SUBSIDIARY}, {NodeType.ASSET}),
    EdgeType.RELATED_TO:   (set(NodeType), set(NodeType)),  # catch-all for weak links
}


# ── Public dataclasses (mostly for type hints + JSON shape) ───────────────────
@dataclass
class GraphNode:
    id: str
    node_type: NodeType
    label: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "label": self.label,
            "payload": self.payload,
        }


@dataclass
class GraphEdge:
    src: str
    dst: str
    edge_type: EdgeType
    weight: float = 1.0
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "src": self.src,
            "dst": self.dst,
            "edge_type": self.edge_type.value,
            "weight": self.weight,
            "payload": self.payload,
        }


# ── Main graph object ─────────────────────────────────────────────────────────
class EvidenceGraph:
    """In-process typed DiGraph for one pipeline run.

    Methods are deliberately small + composable so the LangGraph callers can
    snapshot state at any moment without touching the underlying NetworkX
    object directly.
    """

    def __init__(self):
        self.g = nx.DiGraph()

    # — Node ops —
    def add_node(self, node: GraphNode) -> None:
        if not node.id:
            raise ValueError("GraphNode.id is required")
        # If node exists, merge payload — never silently replace
        existing = self.g.nodes.get(node.id)
        if existing:
            existing.setdefault("payload", {}).update(node.payload or {})
            if node.label and not existing.get("label"):
                existing["label"] = node.label
            return
        self.g.add_node(
            node.id,
            node_type=node.node_type.value,
            label=node.label,
            payload=dict(node.payload),
        )

    def has_node(self, node_id: str) -> bool:
        return node_id in self.g.nodes

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if node_id not in self.g.nodes:
            return None
        nd = self.g.nodes[node_id]
        return {
            "id": node_id,
            "node_type": nd.get("node_type"),
            "label": nd.get("label", ""),
            "payload": nd.get("payload", {}),
        }

    # — Edge ops —
    def add_edge(self, edge: GraphEdge) -> None:
        if not (edge.src in self.g.nodes and edge.dst in self.g.nodes):
            raise ValueError(
                f"add_edge: missing endpoint(s) — src={edge.src!r} "
                f"({'present' if edge.src in self.g.nodes else 'MISSING'}), "
                f"dst={edge.dst!r} "
                f"({'present' if edge.dst in self.g.nodes else 'MISSING'})"
            )
        # Schema enforcement
        try:
            src_type = NodeType(self.g.nodes[edge.src]["node_type"])
            dst_type = NodeType(self.g.nodes[edge.dst]["node_type"])
        except (KeyError, ValueError) as e:
            raise ValueError(f"add_edge: node type lookup failed: {e}") from e

        allowed_src, allowed_dst = _ALLOWED_EDGE_SCHEMA[edge.edge_type]
        if src_type not in allowed_src or dst_type not in allowed_dst:
            raise ValueError(
                f"add_edge schema violation: ({src_type.value}) "
                f"-[{edge.edge_type.value}]-> ({dst_type.value}) "
                f"not allowed"
            )
        # Allow parallel edges of different types but not duplicates of the
        # same (src, dst, type); merge weights if duplicate.
        if self.g.has_edge(edge.src, edge.dst):
            existing = self.g.get_edge_data(edge.src, edge.dst)
            if existing.get("edge_type") == edge.edge_type.value:
                existing["weight"] = max(existing.get("weight", 1.0), edge.weight)
                existing.setdefault("payload", {}).update(edge.payload or {})
                return
        self.g.add_edge(
            edge.src, edge.dst,
            edge_type=edge.edge_type.value,
            weight=edge.weight,
            payload=dict(edge.payload),
        )

    # — Queries —
    def nodes_of_type(self, node_type: NodeType) -> List[str]:
        return [
            n for n, attrs in self.g.nodes(data=True)
            if attrs.get("node_type") == node_type.value
        ]

    def neighbours(self, node_id: str,
                   edge_types: Optional[Iterable[EdgeType]] = None,
                   direction: str = "out") -> List[Tuple[str, str]]:
        """Return [(neighbour_id, edge_type)] from `node_id`.

        direction: "out" | "in" | "both"
        edge_types: filter to these edge types (None = all)
        """
        if node_id not in self.g.nodes:
            return []
        et_set = (
            {e.value for e in edge_types}
            if edge_types is not None else None
        )
        out: List[Tuple[str, str]] = []
        if direction in ("out", "both"):
            for nbr in self.g.successors(node_id):
                et = self.g.get_edge_data(node_id, nbr).get("edge_type")
                if et_set is None or et in et_set:
                    out.append((nbr, et))
        if direction in ("in", "both"):
            for nbr in self.g.predecessors(node_id):
                et = self.g.get_edge_data(nbr, node_id).get("edge_type")
                if et_set is None or et in et_set:
                    out.append((nbr, et))
        return out

    def traverse(self, start: str, max_hops: int = 2,
                 edge_priority: Optional[List[EdgeType]] = None
                 ) -> List[Tuple[str, int, List[str]]]:
        """BFS from `start` up to `max_hops`. Returns [(node_id, depth, path)].

        edge_priority: traverse edges in this order at each hop. Used by KG-RAG
        to prioritise CONTRADICTS > EVIDENCED_BY > RELATED_TO.
        """
        if start not in self.g.nodes:
            return []
        priorities = (
            [e.value for e in edge_priority]
            if edge_priority is not None else None
        )
        visited: Set[str] = {start}
        frontier: List[Tuple[str, int, List[str]]] = [(start, 0, [start])]
        results: List[Tuple[str, int, List[str]]] = []
        while frontier:
            node, depth, path = frontier.pop(0)
            if depth > 0:
                results.append((node, depth, path))
            if depth >= max_hops:
                continue
            # Collect outgoing edges, sort by priority
            out_edges: List[Tuple[str, str]] = []
            for nbr in self.g.successors(node):
                et = self.g.get_edge_data(node, nbr).get("edge_type", "")
                out_edges.append((nbr, et))
            if priorities is not None:
                out_edges.sort(key=lambda x: (
                    priorities.index(x[1]) if x[1] in priorities else len(priorities)
                ))
            for nbr, et in out_edges:
                if nbr not in visited:
                    visited.add(nbr)
                    frontier.append((nbr, depth + 1, path + [nbr]))
        return results

    # — Serialisation —
    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe adjacency dict for state passing."""
        return {
            "nodes": [
                {
                    "id": n,
                    "node_type": attrs.get("node_type"),
                    "label": attrs.get("label", ""),
                    "payload": attrs.get("payload", {}),
                }
                for n, attrs in self.g.nodes(data=True)
            ],
            "edges": [
                {
                    "src": s, "dst": d,
                    "edge_type": attrs.get("edge_type"),
                    "weight": attrs.get("weight", 1.0),
                    "payload": attrs.get("payload", {}),
                }
                for s, d, attrs in self.g.edges(data=True)
            ],
            "stats": {
                "node_count": self.g.number_of_nodes(),
                "edge_count": self.g.number_of_edges(),
                "density": (
                    nx.density(self.g) if self.g.number_of_nodes() > 1 else 0.0
                ),
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceGraph":
        """Rebuild from a dict produced by `to_dict()`."""
        eg = cls()
        for node in data.get("nodes") or []:
            try:
                eg.add_node(GraphNode(
                    id=node["id"],
                    node_type=NodeType(node["node_type"]),
                    label=node.get("label", ""),
                    payload=node.get("payload") or {},
                ))
            except (ValueError, KeyError) as e:
                logger.warning("Skipping malformed node: %s", e)
        for edge in data.get("edges") or []:
            try:
                eg.add_edge(GraphEdge(
                    src=edge["src"], dst=edge["dst"],
                    edge_type=EdgeType(edge["edge_type"]),
                    weight=float(edge.get("weight", 1.0)),
                    payload=edge.get("payload") or {},
                ))
            except (ValueError, KeyError) as e:
                logger.warning("Skipping malformed edge: %s", e)
        return eg


# ── Builders that wire common pipeline shapes into a graph ───────────────────
def build_from_state(state: Dict[str, Any]) -> EvidenceGraph:
    """Construct an EvidenceGraph from a partial pipeline state.

    Wires up:
      - Company node (with LEI from F1)
      - Claim nodes (one per sub_claim in claim_decomposition)
      - Evidence nodes (from state['evidence'])
      - Source nodes (deduped by domain)
      - EVIDENCED_BY edges using F2 cosine similarity > threshold
    """
    g = EvidenceGraph()

    company_name = state.get("company") or "Unknown"
    entity = state.get("entity_record") or {}
    company_id = entity.get("lei") or f"name:{company_name.lower()}"
    g.add_node(GraphNode(
        id=company_id,
        node_type=NodeType.COMPANY,
        label=entity.get("canonical_name") or company_name,
        payload={
            "lei": entity.get("lei"),
            "country_iso3": entity.get("country_iso3"),
        },
    ))

    # Claim nodes
    decomposition = state.get("claim_decomposition") or {}
    sub_claims = (
        decomposition.get("sub_claims") if isinstance(decomposition, dict) else []
    ) or []
    claim_id_map: List[Tuple[str, str]] = []  # (claim_id, claim_text)
    for sc in sub_claims:
        if not isinstance(sc, dict):
            continue
        cid = f"claim:{sc.get('id') or len(claim_id_map)}"
        ctext = sc.get("text") or sc.get("claim") or ""
        g.add_node(GraphNode(
            id=cid,
            node_type=NodeType.CLAIM,
            label=ctext[:120],
            payload={
                "text": ctext,
                "claim_type": sc.get("type") or sc.get("claim_type"),
                "measurable": bool(sc.get("measurable")),
            },
        ))
        # SAYS edge
        g.add_edge(GraphEdge(src=company_id, dst=cid, edge_type=EdgeType.SAYS))
        claim_id_map.append((cid, ctext))

    # Evidence + Source nodes
    evidence_items = state.get("evidence") or []
    for i, ev in enumerate(evidence_items):
        if not isinstance(ev, dict):
            continue
        eid = f"ev:{i}"
        text = ev.get("title") or ev.get("snippet") or ev.get("relevant_text") or ""
        url = str(ev.get("url") or "")
        src_name = ev.get("source_name") or ev.get("source") or ""
        if not src_name and url:
            # Extract domain
            import re as _re
            m = _re.match(r"https?://([^/]+)/?", url)
            src_name = m.group(1) if m else ""
        src_name = (src_name or "unknown").lower()

        g.add_node(GraphNode(
            id=eid,
            node_type=NodeType.EVIDENCE,
            label=text[:120],
            payload={
                "text": text,
                "url": url,
                "tier": ev.get("reliability_tier") or ev.get("_tier") or 4,
            },
        ))
        # Source node
        sid = f"src:{src_name}"
        if not g.has_node(sid):
            g.add_node(GraphNode(
                id=sid, node_type=NodeType.SOURCE, label=src_name,
                payload={"domain": src_name},
            ))
        g.add_edge(GraphEdge(src=eid, dst=sid, edge_type=EdgeType.CITES))

    # EVIDENCED_BY edges via embedding similarity
    try:
        from core.embed_cache import similarity as _emb_sim
        for cid, ctext in claim_id_map:
            for i, ev in enumerate(evidence_items):
                if not isinstance(ev, dict):
                    continue
                etext = (
                    ev.get("title") or "") + " " + (
                    ev.get("snippet") or ev.get("relevant_text") or "")
                if not etext.strip():
                    continue
                score = _emb_sim(ctext, etext)
                # bge-small has a wide cosine distribution; 0.50 empirically
                # keeps legitimate paraphrases and drops topically unrelated
                # noise (cricket vs net-zero scores ~0.44).
                if score >= 0.50:
                    g.add_edge(GraphEdge(
                        src=cid, dst=f"ev:{i}",
                        edge_type=EdgeType.EVIDENCED_BY,
                        weight=score,
                        payload={"cosine": round(score, 3)},
                    ))
    except Exception as e:
        logger.warning("Evidence graph linking failed (embedding): %s", e)

    return g
