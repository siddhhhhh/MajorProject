"""
Supervisor Agent: Routes claims to appropriate workflow paths
Implements dynamic routing based on claim complexity
"""
import os
from typing import Literal
from core.state_schema import ESGState
from core.llm_call import call_llm
import asyncio
from core.evidence_cache import evidence_cache

class SupervisorAgent:
    def __init__(self):
        pass
    
    def assess_complexity(self, state: ESGState) -> ESGState:
        """
        Analyze claim complexity to determine routing path
        Returns updated state with complexity_score
        """
        claim = state["claim"]
        company = state["company"]
        
        prompt = f"""Analyze the complexity of this ESG claim on a scale of 0.0 to 1.0:

Claim: {claim}
Company: {company}

Complexity factors:
- Quantitative specificity (0.1): Has specific numbers/percentages? (e.g., "reduced emissions by 30%")
- Temporal clarity (0.2): Specific timeframe? (e.g., "in 2024" vs "committed to")
- Verifiability (0.3): Can be verified with public data? (emissions data, financial reports)
- Ambiguity (0.2): Vague terms like "sustainable", "eco-friendly", "green"
- Scope (0.2): Broad claims vs specific initiatives

Examples:
- "BP reduced carbon emissions by 15% in 2023" → 0.2 (specific, verifiable)
- "We are committed to sustainability" → 0.9 (vague, unverifiable)
- "Invested $500M in renewable energy projects" → 0.4 (specific amount, moderate complexity)

Return ONLY a single float between 0.0 and 1.0, nothing else."""

        try:
            response = asyncio.run(call_llm("supervisor", prompt))
            complexity = float(response.strip())
            
            # Clamp between 0 and 1
            complexity = max(0.0, min(1.0, complexity))
            
        except Exception as e:
            print(f"Error in complexity assessment: {e}")
            complexity = 0.5  # Default to standard track on error
        
        state["complexity_score"] = complexity
        state["agent_outputs"].append({
            "agent": "supervisor",
            "action": "complexity_assessment",
            "complexity_score": complexity,
            "reasoning": f"Assessed claim complexity: {complexity:.2f}"
        })
        
        return state
    
    def route_workflow(self, state: ESGState) -> Literal["fast_track", "standard_track", "deep_analysis"]:
        """
        Determine which workflow path to take based on complexity
        """
        complexity = state["complexity_score"]

        claim_text = str(state.get("claim", "") or "").lower()
        requires_full_pipeline = any(
            kw in claim_text for kw in [
                "scope 1", "scope 2", "scope 3", "emission", "carbon", "net zero",
                "renewable", "sbti", "science based", "%", "by 20", "since 20"
            ]
        )

        # Only allow fast track for genuinely simple, non-quantitative claims.
        if complexity < 0.2 and not requires_full_pipeline:
            path = "fast_track"
        elif complexity < 0.7:
            path = "standard_track"
        else:
            path = "deep_analysis"
        
        state["workflow_path"] = path
        state["agent_outputs"].append({
            "agent": "supervisor",
            "action": "workflow_routing",
            "selected_path": path,
            "reason": f"Complexity {complexity:.2f} → {path}"
        })
        
        return path

# Node functions for LangGraph
def assess_complexity_node(state: ESGState) -> ESGState:
    """
    Wrapper function for LangGraph node
    CLEARS session cache at start of new analysis
    """
    company = state.get("company", "Unknown")

    # CLEAR SESSION CACHE for new analysis (keeps disk cache for reuse)
    evidence_cache.clear_session_cache()
    print(f"\n🔄 Starting analysis for {company} - session cache cleared\n")

    # F1: Resolve canonical entity (LEI + country + aliases) at pipeline entry
    # so every downstream consumer (Climate TRACE, GDELT, CourtListener, etc.)
    # has a stable join key. Failure is non-fatal — state["entity_record"]
    # stays None and consumers fall back to name-string lookups.
    try:
        from core.entity_resolver import resolve as _resolve_entity, record_to_dict
        _rec = _resolve_entity(company)
        if _rec is not None:
            state["entity_record"] = record_to_dict(_rec)
            state["company_lei"] = _rec.lei
            print(f"   🔗 Resolved entity: {_rec.canonical_name} "
                  f"(LEI={_rec.lei or 'unknown'}, country={_rec.country_iso3 or 'unknown'})")
        else:
            state["entity_record"] = None
            state["company_lei"] = None
            print(f"   ⚠️  Entity not in resolver index — falling back to name-string lookups")
    except Exception as _ent_exc:
        print(f"   ⚠️  Entity resolver failed: {_ent_exc}")
        state["entity_record"] = None
        state["company_lei"] = None

    # M1: Stamp the curated macro / geopolitical context onto state. Read-only
    # — does NOT change scoring; downstream report Section 12 + counterfactual
    # consume it for display / what-if scenarios.
    try:
        from core.macro_context import surface_for_report as _macro_surface
        state["macro_context"] = _macro_surface(state)
        _mc = state["macro_context"]
        if _mc.get("status") == "ACTIVE_EVENTS_PRESENT":
            _names = [e.get("name") for e in (_mc.get("active_events") or [])]
            _exp = (_mc.get("industry_exposure") or {}).get("aggregate_exposure", 0.0)
            print(f"   🌐 Macro context: {len(_names)} active event(s) — "
                  f"{', '.join(_names)} | industry exposure={_exp:.2f}")
        else:
            print(f"   🌐 Macro context: no active events for this date")
    except Exception as _mc_exc:
        print(f"   ⚠️  Macro context surface failed: {_mc_exc}")
        state["macro_context"] = {"status": "ERROR", "error": str(_mc_exc)[:200]}

    # Reg-A: Stamp the active regulatory-framework registry snapshot onto
    # state. Reports become reproducible: future re-derivation can pin
    # against `registry_version` even after the rules change.
    try:
        from core.regulatory_registry import snapshot_for_report as _reg_snap
        state["regulatory_registry_snapshot"] = _reg_snap()
        _rs = state["regulatory_registry_snapshot"]
        print(f"   ⚖️  Regulatory registry: v={_rs.get('registry_version')} "
              f"| {_rs.get('active_count')} active frameworks "
              f"| status={_rs.get('status_counts')}")
    except Exception as _rs_exc:
        print(f"   ⚠️  Regulatory registry snapshot failed: {_rs_exc}")
        state["regulatory_registry_snapshot"] = {
            "status": "ERROR", "error": str(_rs_exc)[:200]
        }

    supervisor = SupervisorAgent()
    return supervisor.assess_complexity(state)

def classify_workflow(state: ESGState) -> str:
    """Conditional edge function for routing"""
    supervisor = SupervisorAgent()
    return supervisor.route_workflow(state)
