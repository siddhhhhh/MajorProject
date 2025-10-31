"""
LangGraph Workflow Builder
Constructs the state graph with conditional routing
"""
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from core.state_schema import ESGState, InputState, OutputState
from core.supervisor_agent import assess_complexity_node, classify_workflow
from core.minimal_agents import (
    claim_extraction_node,
    evidence_retrieval_node,
    risk_scoring_node
)

def build_phase1_graph():
    """
    Build Phase 1 LangGraph with basic routing
    
    Workflow:
    START → Assess Complexity → Route by complexity:
        - Fast Track: Claim → Risk Score → END
        - Standard Track: Claim → Evidence → Risk Score → END
        - Deep Analysis: Claim → Evidence → Risk Score → END (same as standard in Phase 1)
    """
    # Create graph with state schema
    workflow = StateGraph(ESGState)
    
    # Add nodes
    workflow.add_node("assess_complexity", assess_complexity_node)
    workflow.add_node("fast_track_claim", claim_extraction_node)
    workflow.add_node("fast_track_risk", risk_scoring_node)
    workflow.add_node("standard_claim", claim_extraction_node)
    workflow.add_node("standard_evidence", evidence_retrieval_node)
    workflow.add_node("standard_risk", risk_scoring_node)
    
    # Set entry point
    workflow.add_edge(START, "assess_complexity")
    
    # Conditional routing from supervisor
    workflow.add_conditional_edges(
        "assess_complexity",
        classify_workflow,
        {
            "fast_track": "fast_track_claim",
            "standard_track": "standard_claim",
            "deep_analysis": "standard_claim"  # Same as standard in Phase 1
        }
    )
    
    # Fast track edges
    workflow.add_edge("fast_track_claim", "fast_track_risk")
    workflow.add_edge("fast_track_risk", END)
    
    # Standard track edges
    workflow.add_edge("standard_claim", "standard_evidence")
    workflow.add_edge("standard_evidence", "standard_risk")
    workflow.add_edge("standard_risk", END)
    
    # Compile with in-memory checkpointer for Phase 1
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    return app

def print_graph_structure(app):
    """Helper to visualize graph structure"""
    try:
        # Attempt to get mermaid diagram
        print(app.get_graph().draw_mermaid())
    except Exception:
        print("Graph compiled successfully (visualization requires graphviz)")
