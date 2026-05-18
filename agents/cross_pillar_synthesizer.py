"""Cross-pillar contradiction synthesizer — catches E↔S, E↔G, S↔G mismatches.

Today contradiction detection runs inside each pillar agent and only catches
in-pillar inconsistencies. Real-world greenwashing often hides across pillars:
"Net-zero by 2030" (E) + "renewables division layoffs" (S, surfaced via GDELT).

This agent reads all three pillar agent outputs + GDELT events + claim
decomposition + litigation, then uses F2 embeddings to find claim/event pairs
that are topically similar but stance-opposed. Each found pair becomes a
cross-pillar contradiction entry.

Algorithm:
  1. Collect top-3 claims from each pillar (E/S/G) + claim_decomposition
  2. Collect "opposing-stance" signals: GDELT adverse events, litigation rows,
     regulatory_cross_ref fines, subsidiary high-emission entries
  3. For each (pillar_claim, opposing_signal) pair where cosine >= 0.55 AND
     stance-opposition flag fires -> create cross-pillar contradiction
  4. Rank by severity and emit top-N

State entry: state["cross_pillar_contradictions"]
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Cosine threshold below which we skip (avoid noise from bge-small's wide
# distribution).
_PAIR_THRESHOLD = 0.55
# Per-contradiction severity in GW points; capped total per run.
_PER_CONTRADICTION_PTS = 3.0
_TOTAL_CAP_PTS = 12.0


def _collect_pillar_claims(state: Dict[str, Any]) -> Dict[str, List[str]]:
    """Pull top claim text from each pillar's agent output."""
    pillars: Dict[str, List[str]] = {"E": [], "S": [], "G": []}
    # Environmental — carbon extraction net-zero claim, claim_decomposition
    decomp = state.get("claim_decomposition") or {}
    for sc in (decomp.get("sub_claims") or []):
        if not isinstance(sc, dict):
            continue
        pillar = (sc.get("pillar") or "E")[:1].upper()
        if pillar not in pillars:
            continue
        pillars[pillar].append(sc.get("text") or "")
    # Social analysis
    soc = state.get("social_analysis") or {}
    if isinstance(soc, dict):
        for k in ("summary", "narrative", "key_findings"):
            v = soc.get(k)
            if isinstance(v, str) and v:
                pillars["S"].append(v[:300])
                break
    # Governance analysis
    gov = state.get("governance_analysis") or {}
    if isinstance(gov, dict):
        for k in ("summary", "narrative", "key_findings"):
            v = gov.get(k)
            if isinstance(v, str) and v:
                pillars["G"].append(v[:300])
                break
    # Trim to top-3 per pillar
    return {k: [s for s in v if s][:3] for k, v in pillars.items()}


def _collect_opposing_signals(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a list of adverse / opposing-stance signals from across the state."""
    signals: List[Dict[str, Any]] = []

    # GDELT adverse events
    gdelt = state.get("gdelt_events") or {}
    if isinstance(gdelt, dict):
        for e in (gdelt.get("events") or [])[:15]:
            signals.append({
                "text":   e.get("headline") or "",
                "source": "gdelt",
                "stance": "adverse",
                "severity": float(e.get("severity") or 0.5),
                "url":    e.get("url"),
            })

    # Litigation rows
    lit = state.get("litigation_resolved") or {}
    if isinstance(lit, dict):
        for c in (lit.get("us_cases") or [])[:5]:
            if c.get("status") in ("ACTIVE", "SETTLED"):
                signals.append({
                    "text":   c.get("case_name") or "",
                    "source": "courtlistener",
                    "stance": "adverse",
                    "severity": 0.6 if c["status"] == "ACTIVE" else 0.3,
                    "url":    c.get("url"),
                })
        for c in (lit.get("in_cases") or [])[:5]:
            if c.get("status") in ("ACTIVE", "SETTLED"):
                signals.append({
                    "text":   c.get("case_name") or "",
                    "source": "indian_kanoon",
                    "stance": "adverse",
                    "severity": 0.4,
                    "url":    c.get("url"),
                })

    # Regulatory cross-ref EPA violations
    rcr = state.get("regulatory_cross_ref") or {}
    if isinstance(rcr, dict):
        for v in (rcr.get("epa_violations") or [])[:8]:
            signals.append({
                "text":   f"EPA {v.get('program')} violation: {v.get('summary') or v.get('violation_type')}",
                "source": "epa_echo",
                "stance": "adverse",
                "severity": 0.55,
                "url":    None,
            })

    # Subsidiary high-emission rows (treat as opposing signal to parent
    # net-zero claims)
    sw = state.get("subsidiary_walk") or {}
    if isinstance(sw, dict):
        for s in (sw.get("subsidiaries") or []):
            if (s.get("estimated_emissions_tco2e") or 0) > 5e6:
                signals.append({
                    "text":   f"Subsidiary {s.get('subsidiary_name')} emits "
                              f"{s.get('estimated_emissions_tco2e')/1e6:.1f} MtCO2e "
                              f"(sector: {s.get('sector_hint')})",
                    "source": "subsidiary_walker",
                    "stance": "adverse",
                    "severity": 0.5,
                    "url":    None,
                })

    return signals


def _embedding_pair_score(a: str, b: str) -> float:
    try:
        from core.embed_cache import similarity
        return max(0.0, float(similarity(a, b)))
    except Exception:
        # Jaccard fallback
        import re as _re
        ta = set(_re.findall(r"[a-z0-9]{3,}", (a or "").lower()))
        tb = set(_re.findall(r"[a-z0-9]{3,}", (b or "").lower()))
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / max(1, len(ta))


def synthesize(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the cross-pillar synthesis. Returns decision-grade dict."""
    out: Dict[str, Any] = {
        "agent":               "cross_pillar_synthesizer",
        "contradictions":      [],
        "contradiction_count": 0,
        "ledger_delta":        0.0,
        "ledger_bucket":       "cross_pillar_contradiction",
        "rationale":           "",
        "source":              "cross_pillar_synthesis_v1",
    }

    pillar_claims = _collect_pillar_claims(state)
    opposing = _collect_opposing_signals(state)
    if not opposing:
        out["rationale"] = "No opposing-stance signals collected (GDELT / litigation / EPA / subsidiary)."
        return out

    contradictions: List[Dict[str, Any]] = []
    for pillar, claims in pillar_claims.items():
        for claim in claims:
            for opp in opposing:
                score = _embedding_pair_score(claim, opp.get("text") or "")
                if score < _PAIR_THRESHOLD:
                    continue
                contradictions.append({
                    "pillar":         pillar,
                    "claim":          claim[:200],
                    "opposing_text":  (opp.get("text") or "")[:200],
                    "opposing_source": opp.get("source"),
                    "opposing_url":   opp.get("url"),
                    "cosine":         round(score, 3),
                    "severity":       round(score * (opp.get("severity") or 0.5), 3),
                })

    # Dedupe by (pillar, opposing_text)
    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for c in sorted(contradictions, key=lambda x: x["severity"], reverse=True):
        key = (c["pillar"], (c["opposing_text"] or "")[:120])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    out["contradictions"] = deduped[:10]
    out["contradiction_count"] = len(deduped)

    # Ledger delta — capped
    pts = min(_TOTAL_CAP_PTS, _PER_CONTRADICTION_PTS * out["contradiction_count"])
    out["ledger_delta"] = round(pts, 1)

    out["rationale"] = (
        f"Found {out['contradiction_count']} cross-pillar contradiction pair(s) "
        f"with cosine >= {_PAIR_THRESHOLD}. Top-10 retained."
    )
    return out


def build_ledger_row(syn_out: Dict[str, Any]) -> Dict[str, Any]:
    delta = float(syn_out.get("ledger_delta") or 0.0)
    if abs(delta) < 0.01:
        return {}
    return {
        "bucket":          syn_out.get("ledger_bucket", "cross_pillar_contradiction"),
        "source":          "cross_pillar_synthesizer",
        "delta":           delta,
        "direction":       "increases_gw_risk",
        "rationale":       syn_out.get("rationale", ""),
        "evidence_source": "Cross-pillar synthesis (embedding cosine pairs)",
        "evidence_url":    None,
        "contradiction_count": syn_out.get("contradiction_count"),
    }
