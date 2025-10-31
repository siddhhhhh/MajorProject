"""
Phase 2 Workflow - FIXED: Removed self-correction loop to prevent recursion
Self-correction will be added properly in Phase 3
"""
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from core.state_schema import ESGState
from core.supervisor_agent import assess_complexity_node, classify_workflow
from core.agent_wrappers import (
    claim_extraction_node,
    evidence_retrieval_node,
    contradiction_analysis_node,
    temporal_analysis_node,
    peer_comparison_node,
    risk_scoring_node,
    sentiment_analysis_node,
    credibility_analysis_node,
    realtime_monitoring_node,
    confidence_scoring_node,
    verdict_generation_node
)
from core.professional_report_generator import professional_report_generation_node as report_generation_node
from core.debate_orchestrator import debate_node

def build_phase2_graph():
    """
    Phase 2 LangGraph - SIMPLIFIED (no self-correction loop yet)
    - Dynamic routing based on complexity
    - Full 11-agent pipeline
    - Debate mechanism
    - NO self-correction (prevents recursion)
    """
    workflow = StateGraph(ESGState)
    
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
    workflow.add_node("fast_verdict", verdict_generation_node)
    workflow.add_node("fast_report", report_generation_node)
    
    # ============================================================
    # STANDARD TRACK (11 agents - full pipeline)
    # ============================================================
    workflow.add_node("std_claim", claim_extraction_node)
    workflow.add_node("std_evidence", evidence_retrieval_node)
    workflow.add_node("std_contradiction", contradiction_analysis_node)
    workflow.add_node("std_temporal", temporal_analysis_node)
    workflow.add_node("std_peer", peer_comparison_node)
    workflow.add_node("std_credibility", credibility_analysis_node)
    workflow.add_node("std_sentiment", sentiment_analysis_node)
    workflow.add_node("std_realtime", realtime_monitoring_node)
    workflow.add_node("std_risk", risk_scoring_node)
    workflow.add_node("std_confidence", confidence_scoring_node)
    workflow.add_node("std_verdict", verdict_generation_node)
    workflow.add_node("std_report", report_generation_node)
    
    # ============================================================
    # DEEP ANALYSIS TRACK (Standard + Debate)
    # ============================================================
    workflow.add_node("deep_claim", claim_extraction_node)
    workflow.add_node("deep_evidence", evidence_retrieval_node)
    workflow.add_node("deep_contradiction", contradiction_analysis_node)
    workflow.add_node("deep_temporal", temporal_analysis_node)
    workflow.add_node("deep_peer", peer_comparison_node)
    workflow.add_node("deep_credibility", credibility_analysis_node)
    workflow.add_node("deep_sentiment", sentiment_analysis_node)
    workflow.add_node("deep_realtime", realtime_monitoring_node)
    workflow.add_node("deep_risk", risk_scoring_node)
    workflow.add_node("deep_confidence", confidence_scoring_node)
    workflow.add_node("deep_verdict", verdict_generation_node)
    workflow.add_node("deep_debate", debate_node)
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
    workflow.add_edge("fast_risk", "fast_confidence")
    workflow.add_edge("fast_confidence", "fast_verdict")
    workflow.add_edge("fast_verdict", "fast_report")
    workflow.add_edge("fast_report", END)  # FIXED: Direct to END
    
    # Standard track path (linear - no loops)
    workflow.add_edge("std_claim", "std_evidence")
    workflow.add_edge("std_evidence", "std_contradiction")
    workflow.add_edge("std_contradiction", "std_temporal")
    workflow.add_edge("std_temporal", "std_peer")
    workflow.add_edge("std_peer", "std_credibility")
    workflow.add_edge("std_credibility", "std_sentiment")
    workflow.add_edge("std_sentiment", "std_realtime")
    workflow.add_edge("std_realtime", "std_risk")
    workflow.add_edge("std_risk", "std_confidence")
    workflow.add_edge("std_confidence", "std_verdict")
    workflow.add_edge("std_verdict", "std_report")
    workflow.add_edge("std_report", END)  # FIXED: Direct to END
    
    # Deep analysis path (linear with debate - no loops)
    workflow.add_edge("deep_claim", "deep_evidence")
    workflow.add_edge("deep_evidence", "deep_contradiction")
    workflow.add_edge("deep_contradiction", "deep_temporal")
    workflow.add_edge("deep_temporal", "deep_peer")
    workflow.add_edge("deep_peer", "deep_credibility")
    workflow.add_edge("deep_credibility", "deep_sentiment")
    workflow.add_edge("deep_sentiment", "deep_realtime")
    workflow.add_edge("deep_realtime", "deep_risk")
    workflow.add_edge("deep_risk", "deep_confidence")
    workflow.add_edge("deep_confidence", "deep_verdict")
    workflow.add_edge("deep_verdict", "deep_debate")
    workflow.add_edge("deep_debate", "deep_report")
    workflow.add_edge("deep_report", END)  # FIXED: Direct to END
    
    # Compile with memory checkpointer
    # Compile WITHOUT checkpointer (reduces duplicate state saves)
    app = workflow.compile()  # No checkpointer = faster, less memory
    
    return app
