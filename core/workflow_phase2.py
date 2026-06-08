"""
Phase 2 Workflow - FIXED: Removed self-correction loop to prevent recursion
Self-correction will be added properly in Phase 3
"""
import os
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from core.state_schema import ESGState
from core.supervisor_agent import assess_complexity_node, classify_workflow
from core.agent_wrappers import (
    claim_extraction_node,
    claim_decomposition_node,
    evidence_retrieval_node,
    adversarial_triangulation_node,
    fact_graph_node,
    carbon_extraction_node,
    carbon_pathway_analysis_node,
    greenwishing_detection_node,
    regulatory_scanning_node,
    social_analysis_node,
    governance_analysis_node,
    climatebert_analysis_node,
    contradiction_analysis_node,
    temporal_analysis_node,
    peer_comparison_node,
    risk_scoring_node,
    adversarial_audit_node,
    sentiment_analysis_node,
    credibility_analysis_node,
    realtime_monitoring_node,
    confidence_scoring_node,
    verdict_generation_node,
    explainability_node,
    report_discovery_node,
    report_downloader_node,
    report_parser_node,
    report_claim_extraction_node,
    temporal_consistency_node,
    commitment_ledger_update_node,
    esg_mismatch_node
)
from core.professional_report_generator import professional_report_generation_node as report_generation_node
from core.debate_orchestrator import debate_node


def save_peer_to_database_node(state: ESGState) -> ESGState:
    """
    Save company ESG scores to peer database
    This builds the real peer comparison database over time
    """
    print(f"\n{'🔵 SAVING TO PEER DATABASE':=^70}")
    
    try:
        # IndustryComparator is deprecated.
        print("⚠️ Peer database saving disabled (IndustryComparator deprecated).")
        print(f"{'='*70}")
    
    except Exception as e:
        print(f"❌ Error saving to peer database: {e}")
        import traceback
        traceback.print_exc()
    
    return state

# ============================================================
# PARALLEL ANALYTICS FANOUT
# ============================================================
# Replaces 10 sequential analytical nodes with one node that runs them
# concurrently in a ThreadPoolExecutor. Proven independent (see dependency
# matrix in audit notes 2026-06-05): each agent reads
# evidence/claim/company/parsed-chunks and writes to its own unique state
# slot. Merging is union-by-agent for agent_outputs and append-new for
# scoremodifierledger + node_execution_order.
#
# EXCLUDED (kept sequential):
#   - realtime_monitoring_node: writes shared state["confidence"]
#   - esg_mismatch_node: post-refactor still mutates state["carbon_extraction"]
#
# Workers controlled by ESG_FANOUT_WORKERS (default 5). 1 = sequential
# behaviour (useful for correctness diff against baseline).

def _run_fanout_branch(name: str, fn, state_copy):
    """Execute a single branch; capture wall-clock duration."""
    import time as _t
    t0 = _t.time()
    out = fn(state_copy)
    return name, out, _t.time() - t0


def parallel_analytics_node(state: ESGState) -> ESGState:
    """Run 10 proven-independent analytical agents concurrently."""
    import concurrent.futures, copy as _copy, time as _time

    fanout_funcs = [
        ("greenwishing",   greenwishing_detection_node),
        ("regulatory",     regulatory_scanning_node),
        ("climatebert",    climatebert_analysis_node),
        ("social",         social_analysis_node),
        ("governance",     governance_analysis_node),
        ("contradiction",  contradiction_analysis_node),
        ("temporal",       temporal_analysis_node),
        ("peer",           peer_comparison_node),
        ("sentiment",      sentiment_analysis_node),
        ("credibility",    credibility_analysis_node),
    ]

    max_workers = int(os.environ.get("ESG_FANOUT_WORKERS", "5"))
    if max_workers <= 1:
        # Sequential fallback — exercises the same code path but no parallelism
        print(f"\n{'⚡ FANOUT (SEQUENTIAL, workers=1)':=^70}")
        for name, fn in fanout_funcs:
            try:
                fn(state)
            except Exception as e:
                print(f"   ✗ {name} failed: {e}")
        return state

    print(f"\n{'⚡ PARALLEL ANALYTICS FANOUT (' + str(len(fanout_funcs)) + ' agents, workers=' + str(max_workers) + ')':=^70}")

    pre_keys = set(state.keys()) if isinstance(state, dict) else set()
    pre_agent_outputs = list(state.get("agent_outputs", []) or [])
    pre_ledger = list(state.get("scoremodifierledger", []) or [])
    pre_node_order = list(state.get("node_execution_order", []) or [])

    t0 = _time.time()
    branch_results = []  # (name, branch_state | None, duration, error | None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_fanout_branch, name, fn, _copy.deepcopy(state)): name
            for name, fn in fanout_funcs
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                bname, branch_state, duration = future.result()
                branch_results.append((bname, branch_state, duration, None))
                print(f"   ✓ {bname:15s} done in {duration:6.1f}s")
            except Exception as e:
                duration = _time.time() - t0
                branch_results.append((name, None, duration, e))
                print(f"   ✗ {name:15s} FAILED: {type(e).__name__}: {e}")

    total_dt = _time.time() - t0

    # ---- Merge branch outputs ----
    merged_agent_outputs = list(pre_agent_outputs)
    seen_agent_names = {ao.get("agent") for ao in merged_agent_outputs if isinstance(ao, dict)}
    merged_ledger = list(pre_ledger)
    merged_node_order = list(pre_node_order)

    # Known result-slot keys written by these 10 agents — adopt branch writes
    KNOWN_RESULT_SLOTS = {
        "greenwishing_analysis", "controversy_risk", "gdelt_events",
        "litigation_resolved", "regulatory_compliance", "regulatory_cross_ref",
        "regulatory_results", "climatebert_analysis", "climatebert_results",
        "social_analysis", "governance_analysis", "contradiction_results",
        "cross_pillar_contradictions", "historical_results", "peer_results",
        "sentiment_results", "credibility_results",
    }

    for name, branch_state, duration, error in branch_results:
        if branch_state is None or not isinstance(branch_state, dict):
            continue
        # agent_outputs: union by agent name
        for entry in (branch_state.get("agent_outputs") or []):
            if isinstance(entry, dict):
                agent_name = entry.get("agent")
                if agent_name and agent_name not in seen_agent_names:
                    seen_agent_names.add(agent_name)
                    merged_agent_outputs.append(entry)
        # scoremodifierledger: append entries beyond pre snapshot
        branch_ledger = branch_state.get("scoremodifierledger") or []
        if len(branch_ledger) > len(pre_ledger):
            merged_ledger.extend(branch_ledger[len(pre_ledger):])
        # node_execution_order: append new entries
        branch_order = branch_state.get("node_execution_order") or []
        if len(branch_order) > len(pre_node_order):
            merged_node_order.extend(branch_order[len(pre_node_order):])
        # New keys + known result slots
        for k, v in branch_state.items():
            if k in ("agent_outputs", "scoremodifierledger", "node_execution_order"):
                continue
            if k not in pre_keys:
                state[k] = v
            elif k in KNOWN_RESULT_SLOTS and v is not None and v != state.get(k):
                state[k] = v

    state["agent_outputs"] = merged_agent_outputs
    state["scoremodifierledger"] = merged_ledger
    state["node_execution_order"] = merged_node_order

    print(f"{'='*70}")
    print(f"⚡ Fanout complete: {total_dt:.1f}s wallclock")
    print(f"   agent_outputs: {len(pre_agent_outputs)} → {len(merged_agent_outputs)}")
    print(f"   ledger: {len(pre_ledger)} → {len(merged_ledger)}")
    return state


def inject_temporal_violations(state: ESGState) -> ESGState:
    agent_outputs = state.get("agent_outputs", [])
    temporal_result = next((o.get("output", {}) for o in agent_outputs if o.get("agent") == "temporal_analysis"), {})
    violations = temporal_result.get("past_violations", [])
    
    if not violations:
        return state
        
    company = state.get("company", "").lower()
    injected = []
    
    for v in violations:
        desc      = v.get("description", "").lower()
        url       = v.get("url", "").lower()
        tokens    = [t for t in company.split() if len(t) >= 4]
        name_match = any(t in desc or t in url for t in tokens)
        
        if not name_match:
            continue
        
        injected.append({
            "text":   v.get("description", ""),
            "source": v.get("source", ""),
            "url":    v.get("url", ""),
            "year":   v.get("year"),
            "type":   v.get("type", ""),
            "origin": "temporal_analysis"
        })
    
    if injected:
        existing = state.get("additional_evidence", []) or []
        state["additional_evidence"] = existing + injected
        state["evidence"] = state.get("evidence", []) + injected
    
    return state

def build_phase2_graph():
    """
    Phase 2 LangGraph - SIMPLIFIED (no self-correction loop yet)
    - Dynamic routing based on complexity
    - Full 11-agent pipeline
    - Debate mechanism
    - NO self-correction (prevents recursion)
    """
    workflow = StateGraph(ESGState)

    # === DIAG: wrap every node — agent_outputs len + wall-clock per node ===
    if True:  # FORCED ON for this perf-audit session
        import functools, traceback as _tb, time as _time
        _PIPELINE_T0 = _time.time()
        _NODE_TIMINGS = {}  # name → [list of durations]
        _orig_add_node = workflow.add_node
        def _diag_add_node(name, fn, **kwargs):
            @functools.wraps(fn)
            def _wrapped(state, *a, **kw):
                ao = state.get("agent_outputs") if isinstance(state, dict) else None
                ao_in = len(ao) if isinstance(ao, list) else f"type={type(ao).__name__}"
                _t0 = _time.time()
                _wallclock = _t0 - _PIPELINE_T0
                print(f"[DIAG] >>> ENTRY {name:30s} ao_len={ao_in:>4} wallclock={_wallclock:7.1f}s", flush=True)
                try:
                    out = fn(state, *a, **kw)
                    ao2 = out.get("agent_outputs") if isinstance(out, dict) else None
                    ao_out = len(ao2) if isinstance(ao2, list) else f"type={type(ao2).__name__}"
                    _dt = _time.time() - _t0
                    _NODE_TIMINGS.setdefault(name, []).append(_dt)
                    _wallclock2 = _time.time() - _PIPELINE_T0
                    print(f"[DIAG] <<< EXIT  {name:30s} ao_len={ao_out:>4} duration={_dt:7.2f}s wallclock={_wallclock2:7.1f}s", flush=True)
                    return out
                except Exception as e:
                    _dt = _time.time() - _t0
                    print(f"[DIAG] !!! EXC   {name:30s} {type(e).__name__}: {e} (after {_dt:.2f}s)", flush=True)
                    _tb.print_exc()
                    raise
            return _orig_add_node(name, _wrapped, **kwargs)
        workflow.add_node = _diag_add_node
        # Make timings dict accessible for later inspection
        import builtins as _b
        _b._ESG_NODE_TIMINGS = _NODE_TIMINGS
        _b._ESG_PIPELINE_T0 = _PIPELINE_T0
        print(f"[DIAG] node tracing ENABLED (perf-audit mode; T0={_PIPELINE_T0:.0f})", flush=True)

    # ============================================================
    # SUPERVISOR & ROUTING
    # ============================================================
    workflow.add_node("assess_complexity", assess_complexity_node)
    
    # ============================================================
    # FAST TRACK (3 agents - for simple claims)
    # ============================================================
    workflow.add_node("fast_claim", claim_extraction_node)
    workflow.add_node("fast_risk", risk_scoring_node)
    workflow.add_node("fast_confidence", confidence_scoring_node)
    workflow.add_node("fast_audit", adversarial_audit_node)
    workflow.add_node("fast_verdict", verdict_generation_node)
    workflow.add_node("fast_save_peer", save_peer_to_database_node)  # NEW: Save to peer DB
    workflow.add_node("fast_report", report_generation_node)
    
    # ============================================================
    # STANDARD TRACK (15 agents - full pipeline with new features)
    # ============================================================
    workflow.add_node("std_claim", claim_extraction_node)
    workflow.add_node("std_claim_decomposition", claim_decomposition_node)
    workflow.add_node("std_evidence", evidence_retrieval_node)
    workflow.add_node("std_adversarial", adversarial_triangulation_node)
    workflow.add_node("std_report_discovery", report_discovery_node)  # NEW: Report discovery
    workflow.add_node("std_report_downloader", report_downloader_node)  # NEW: Report download
    workflow.add_node("std_report_parser", report_parser_node)  # NEW: Report parsing
    workflow.add_node("std_report_claim_extractor", report_claim_extraction_node)  # NEW: Report claim extraction
    workflow.add_node("std_temporal_consistency", temporal_consistency_node)  # NEW: Temporal analysis
    workflow.add_node("std_carbon", carbon_extraction_node)  # Carbon extraction
    workflow.add_node("std_pathway", carbon_pathway_analysis_node)  # NEW: Pathway modelling
    workflow.add_node("std_greenwishing", greenwishing_detection_node)  # NEW: Greenwishing detection
    workflow.add_node("std_regulatory", regulatory_scanning_node)  # NEW: Regulatory scanning
    workflow.add_node("std_climatebert", climatebert_analysis_node)  # NEW: ClimateBERT NLP
    workflow.add_node("std_contradiction", contradiction_analysis_node)
    workflow.add_node("std_mismatch", esg_mismatch_node)  # NEW: ESG Mismatch Detector
    workflow.add_node("std_temporal", temporal_analysis_node)
    workflow.add_node("std_inject_temporal", inject_temporal_violations)
    workflow.add_node("std_peer", peer_comparison_node)
    workflow.add_node("std_credibility", credibility_analysis_node)
    workflow.add_node("std_sentiment", sentiment_analysis_node)
    workflow.add_node("std_realtime", realtime_monitoring_node)
    workflow.add_node("std_social", social_analysis_node)
    workflow.add_node("std_governance", governance_analysis_node)
    workflow.add_node("std_commitment_ledger", commitment_ledger_update_node)  # NEW: Commitment ledger
    workflow.add_node("std_fact_graph", fact_graph_node)
    workflow.add_node("std_risk", risk_scoring_node)
    workflow.add_node("std_explainability", explainability_node)  # NEW: SHAP/LIME
    workflow.add_node("std_audit", adversarial_audit_node)
    workflow.add_node("std_confidence", confidence_scoring_node)
    workflow.add_node("std_verdict", verdict_generation_node)
    workflow.add_node("std_save_peer", save_peer_to_database_node)
    workflow.add_node("std_report", report_generation_node)
    
    # ============================================================
    # DEEP ANALYSIS TRACK (Standard + Debate + All Features)
    # ============================================================
    workflow.add_node("deep_claim", claim_extraction_node)
    workflow.add_node("deep_claim_decomposition", claim_decomposition_node)
    workflow.add_node("deep_evidence", evidence_retrieval_node)
    workflow.add_node("deep_adversarial", adversarial_triangulation_node)
    workflow.add_node("deep_report_discovery", report_discovery_node)  # NEW: Report discovery
    workflow.add_node("deep_report_downloader", report_downloader_node)  # NEW: Report download
    workflow.add_node("deep_report_parser", report_parser_node)  # NEW: Report parsing
    workflow.add_node("deep_report_claim_extractor", report_claim_extraction_node)  # NEW: Report claim extraction
    workflow.add_node("deep_temporal_consistency", temporal_consistency_node)  # NEW: Temporal analysis
    workflow.add_node("deep_carbon", carbon_extraction_node)  # Carbon extraction
    workflow.add_node("deep_pathway", carbon_pathway_analysis_node)  # NEW: Pathway modelling
    workflow.add_node("deep_greenwishing", greenwishing_detection_node)  # NEW: Greenwishing detection
    workflow.add_node("deep_regulatory", regulatory_scanning_node)  # NEW: Regulatory scanning
    workflow.add_node("deep_climatebert", climatebert_analysis_node)  # NEW: ClimateBERT NLP
    workflow.add_node("deep_contradiction", contradiction_analysis_node)
    workflow.add_node("deep_mismatch", esg_mismatch_node)  # NEW: ESG Mismatch Detector
    workflow.add_node("deep_temporal", temporal_analysis_node)
    workflow.add_node("deep_inject_temporal", inject_temporal_violations)
    workflow.add_node("deep_peer", peer_comparison_node)
    workflow.add_node("deep_credibility", credibility_analysis_node)
    workflow.add_node("deep_sentiment", sentiment_analysis_node)
    workflow.add_node("deep_realtime", realtime_monitoring_node)
    workflow.add_node("deep_social", social_analysis_node)
    workflow.add_node("deep_governance", governance_analysis_node)
    workflow.add_node("deep_commitment_ledger", commitment_ledger_update_node)  # NEW: Commitment ledger
    workflow.add_node("deep_fact_graph", fact_graph_node)
    workflow.add_node("deep_risk", risk_scoring_node)
    workflow.add_node("deep_explainability", explainability_node)  # NEW: SHAP/LIME
    workflow.add_node("deep_audit", adversarial_audit_node)
    workflow.add_node("deep_confidence", confidence_scoring_node)
    workflow.add_node("deep_verdict", verdict_generation_node)
    workflow.add_node("deep_debate", debate_node)
    workflow.add_node("deep_save_peer", save_peer_to_database_node)
    workflow.add_node("deep_report", report_generation_node)
    
    # ============================================================
    # EDGES: Connect the workflow (LINEAR - NO LOOPS)
    # ============================================================
    
    # Entry point
    workflow.add_edge(START, "assess_complexity")
    
    # Supervisor routes to tracks
    workflow.add_conditional_edges(
        "assess_complexity",
        classify_workflow,
        {
            "fast_track": "fast_claim",
            "standard_track": "std_claim",
            "deep_analysis": "deep_claim"
        }
    )
    
    # Fast track path (linear - no loops)
    workflow.add_edge("fast_claim", "fast_risk")
    workflow.add_edge("fast_risk", "fast_audit")
    workflow.add_edge("fast_audit", "fast_confidence")
    workflow.add_edge("fast_confidence", "fast_verdict")
    workflow.add_edge("fast_verdict", "fast_save_peer")  # NEW: Save peer data
    workflow.add_edge("fast_save_peer", "fast_report")
    workflow.add_edge("fast_report", END)  # FIXED: Direct to END
    
    # Standard track path
    # The path through the 10 analytical agents can be EITHER the original
    # sequential chain OR a single parallel fanout node. Default is fanout
    # (production setting); rollback via `ESG_ENABLE_FANOUT=0`.
    _FANOUT = os.environ.get("ESG_ENABLE_FANOUT", "1").lower() in ("1", "true", "yes")

    workflow.add_edge("std_claim", "std_claim_decomposition")
    workflow.add_edge("std_claim_decomposition", "std_evidence")
    workflow.add_edge("std_evidence", "std_adversarial")
    workflow.add_edge("std_adversarial", "std_report_discovery")
    workflow.add_edge("std_report_discovery", "std_report_downloader")
    workflow.add_edge("std_report_downloader", "std_report_parser")
    workflow.add_edge("std_report_parser", "std_report_claim_extractor")
    workflow.add_edge("std_report_claim_extractor", "std_carbon")
    workflow.add_edge("std_carbon", "std_pathway")

    if _FANOUT:
        # ⚡ PARALLEL: 10 independent analytical agents in a single ThreadPool stage
        workflow.add_node("std_parallel_analytics", parallel_analytics_node)
        workflow.add_edge("std_pathway", "std_parallel_analytics")
        workflow.add_edge("std_parallel_analytics", "std_inject_temporal")
        workflow.add_edge("std_inject_temporal", "std_mismatch")
        workflow.add_edge("std_mismatch", "std_realtime")
        workflow.add_edge("std_realtime", "std_temporal_consistency")
        print(f"[FANOUT] enabled — std_pathway → parallel_analytics → inject_temporal → mismatch → realtime → temporal_consistency", flush=True)
    else:
        # Original linear chain
        workflow.add_edge("std_pathway", "std_greenwishing")
        workflow.add_edge("std_greenwishing", "std_regulatory")
        workflow.add_edge("std_regulatory", "std_climatebert")
        workflow.add_edge("std_climatebert", "std_temporal")
        workflow.add_edge("std_temporal", "std_inject_temporal")
        workflow.add_edge("std_inject_temporal", "std_contradiction")
        workflow.add_edge("std_contradiction", "std_mismatch")
        workflow.add_edge("std_mismatch", "std_peer")
        workflow.add_edge("std_peer", "std_credibility")
        workflow.add_edge("std_credibility", "std_sentiment")
        workflow.add_edge("std_sentiment", "std_realtime")
        workflow.add_edge("std_realtime", "std_social")
        workflow.add_edge("std_social", "std_governance")
        workflow.add_edge("std_governance", "std_temporal_consistency")
    workflow.add_edge("std_temporal_consistency", "std_commitment_ledger")
    workflow.add_edge("std_commitment_ledger", "std_fact_graph")
    workflow.add_edge("std_fact_graph", "std_risk")
    workflow.add_edge("std_risk", "std_explainability")  # NEW: SHAP/LIME after risk
    workflow.add_edge("std_explainability", "std_audit")
    workflow.add_edge("std_audit", "std_confidence")
    workflow.add_edge("std_confidence", "std_verdict")
    workflow.add_edge("std_verdict", "std_save_peer")
    workflow.add_edge("std_save_peer", "std_report")
    workflow.add_edge("std_report", END)
    
    # Deep analysis path (linear with debate - no loops)
    workflow.add_edge("deep_claim", "deep_claim_decomposition")
    workflow.add_edge("deep_claim_decomposition", "deep_evidence")
    workflow.add_edge("deep_evidence", "deep_adversarial")
    workflow.add_edge("deep_adversarial", "deep_report_discovery")  # NEW: Enter report pipeline
    workflow.add_edge("deep_report_discovery", "deep_report_downloader")  # NEW: Download reports
    workflow.add_edge("deep_report_downloader", "deep_report_parser")  # NEW: Parse reports
    workflow.add_edge("deep_report_parser", "deep_report_claim_extractor")  # NEW: Extract claims from reports
    workflow.add_edge("deep_report_claim_extractor", "deep_carbon")  # Continue to carbon extraction
    workflow.add_edge("deep_carbon", "deep_pathway")  # NEW: Carbon pathway analysis
    workflow.add_edge("deep_pathway", "deep_greenwishing")  # NEW: Greenwishing
    workflow.add_edge("deep_greenwishing", "deep_regulatory")  # NEW: Regulatory
    workflow.add_edge("deep_regulatory", "deep_climatebert")  # NEW: ClimateBERT
    workflow.add_edge("deep_climatebert", "deep_temporal")
    workflow.add_edge("deep_temporal", "deep_inject_temporal")
    workflow.add_edge("deep_inject_temporal", "deep_contradiction")
    workflow.add_edge("deep_contradiction", "deep_mismatch")  # NEW: ESG Mismatch
    workflow.add_edge("deep_mismatch", "deep_peer")
    workflow.add_edge("deep_peer", "deep_credibility")
    workflow.add_edge("deep_credibility", "deep_sentiment")
    workflow.add_edge("deep_sentiment", "deep_realtime")
    workflow.add_edge("deep_realtime", "deep_social")
    workflow.add_edge("deep_social", "deep_governance")
    workflow.add_edge("deep_governance", "deep_temporal_consistency")  # Temporal analysis after broader evidence context
    workflow.add_edge("deep_temporal_consistency", "deep_commitment_ledger")
    workflow.add_edge("deep_commitment_ledger", "deep_fact_graph")
    workflow.add_edge("deep_fact_graph", "deep_risk")
    workflow.add_edge("deep_risk", "deep_explainability")  # NEW: SHAP/LIME after risk
    workflow.add_edge("deep_explainability", "deep_audit")
    workflow.add_edge("deep_audit", "deep_confidence")
    workflow.add_edge("deep_confidence", "deep_verdict")
    workflow.add_edge("deep_verdict", "deep_debate")
    workflow.add_edge("deep_debate", "deep_save_peer")
    workflow.add_edge("deep_save_peer", "deep_report")
    workflow.add_edge("deep_report", END)
    
    # Compile with memory checkpointer
    # Compile WITHOUT checkpointer (reduces duplicate state saves)
    app = workflow.compile()  # No checkpointer = faster, less memory
    
    return app


def get_chromadb_client():
    """
    Get ChromaDB client for peer comparison database
    Returns a ChromaDB client instance
    """
    import chromadb
    return chromadb.Client()
