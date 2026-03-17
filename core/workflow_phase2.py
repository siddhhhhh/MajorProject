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
    carbon_extraction_node,
    greenwishing_detection_node,
    regulatory_scanning_node,
    climatebert_analysis_node,
    contradiction_analysis_node,
    temporal_analysis_node,
    peer_comparison_node,
    risk_scoring_node,
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
    temporal_consistency_node
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
        from agents.industry_comparator import IndustryComparator
        
        # Extract company info
        company = state.get("company")
        industry = state.get("industry")
        
        if not company or not industry:
            print("⚠️ Missing company or industry - skipping database save")
            return state
        
        # Get risk scorer output for ESG scores
        agent_outputs = state.get("agent_outputs", [])
        risk_scorer_outputs = [o for o in agent_outputs if o.get("agent") == "risk_scoring"]
        
        if not risk_scorer_outputs:
            print("⚠️ No risk scorer output found - skipping database save")
            return state
        
        risk_scorer_result = risk_scorer_outputs[-1].get("output", {})
        pillar_scores = risk_scorer_result.get("pillar_scores", {})
        
        esg_score = pillar_scores.get("overall_esg_score")
        rating = risk_scorer_result.get("rating_grade", "BBB")
        
        if esg_score is None:
            print("⚠️ No ESG score available - skipping database save")
            return state
        
        # Import comparator and save
        comparator = IndustryComparator()
        
        success = comparator.save_company_to_peer_db(
            company=company,
            industry=industry,
            esg_score=esg_score,
            pillar_scores=pillar_scores,
            rating=rating
        )
        
        if success:
            print(f"✅ {company} saved to peer database")
            print(f"   ESG: {esg_score:.1f}, Rating: {rating}")
            print(f"   Industry: {industry}")
        else:
            print(f"⚠️ Failed to save {company} to peer database")
        
        print(f"{'='*70}")
    
    except Exception as e:
        print(f"❌ Error saving to peer database: {e}")
        import traceback
        traceback.print_exc()
    
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
    workflow.add_node("fast_save_peer", save_peer_to_database_node)  # NEW: Save to peer DB
    workflow.add_node("fast_report", report_generation_node)
    
    # ============================================================
    # STANDARD TRACK (15 agents - full pipeline with new features)
    # ============================================================
    workflow.add_node("std_claim", claim_extraction_node)
    workflow.add_node("std_evidence", evidence_retrieval_node)
    workflow.add_node("std_report_discovery", report_discovery_node)  # NEW: Report discovery
    workflow.add_node("std_report_downloader", report_downloader_node)  # NEW: Report download
    workflow.add_node("std_report_parser", report_parser_node)  # NEW: Report parsing
    workflow.add_node("std_report_claim_extractor", report_claim_extraction_node)  # NEW: Report claim extraction
    workflow.add_node("std_temporal_consistency", temporal_consistency_node)  # NEW: Temporal analysis
    workflow.add_node("std_carbon", carbon_extraction_node)  # Carbon extraction
    workflow.add_node("std_greenwishing", greenwishing_detection_node)  # NEW: Greenwishing detection
    workflow.add_node("std_regulatory", regulatory_scanning_node)  # NEW: Regulatory scanning
    workflow.add_node("std_climatebert", climatebert_analysis_node)  # NEW: ClimateBERT NLP
    workflow.add_node("std_contradiction", contradiction_analysis_node)
    workflow.add_node("std_temporal", temporal_analysis_node)
    workflow.add_node("std_peer", peer_comparison_node)
    workflow.add_node("std_credibility", credibility_analysis_node)
    workflow.add_node("std_sentiment", sentiment_analysis_node)
    workflow.add_node("std_realtime", realtime_monitoring_node)
    workflow.add_node("std_risk", risk_scoring_node)
    workflow.add_node("std_explainability", explainability_node)  # NEW: SHAP/LIME
    workflow.add_node("std_confidence", confidence_scoring_node)
    workflow.add_node("std_verdict", verdict_generation_node)
    workflow.add_node("std_save_peer", save_peer_to_database_node)
    workflow.add_node("std_report", report_generation_node)
    
    # ============================================================
    # DEEP ANALYSIS TRACK (Standard + Debate + All Features)
    # ============================================================
    workflow.add_node("deep_claim", claim_extraction_node)
    workflow.add_node("deep_evidence", evidence_retrieval_node)
    workflow.add_node("deep_report_discovery", report_discovery_node)  # NEW: Report discovery
    workflow.add_node("deep_report_downloader", report_downloader_node)  # NEW: Report download
    workflow.add_node("deep_report_parser", report_parser_node)  # NEW: Report parsing
    workflow.add_node("deep_report_claim_extractor", report_claim_extraction_node)  # NEW: Report claim extraction
    workflow.add_node("deep_temporal_consistency", temporal_consistency_node)  # NEW: Temporal analysis
    workflow.add_node("deep_carbon", carbon_extraction_node)  # Carbon extraction
    workflow.add_node("deep_greenwishing", greenwishing_detection_node)  # NEW: Greenwishing detection
    workflow.add_node("deep_regulatory", regulatory_scanning_node)  # NEW: Regulatory scanning
    workflow.add_node("deep_climatebert", climatebert_analysis_node)  # NEW: ClimateBERT NLP
    workflow.add_node("deep_contradiction", contradiction_analysis_node)
    workflow.add_node("deep_temporal", temporal_analysis_node)
    workflow.add_node("deep_peer", peer_comparison_node)
    workflow.add_node("deep_credibility", credibility_analysis_node)
    workflow.add_node("deep_sentiment", sentiment_analysis_node)
    workflow.add_node("deep_realtime", realtime_monitoring_node)
    workflow.add_node("deep_risk", risk_scoring_node)
    workflow.add_node("deep_explainability", explainability_node)  # NEW: SHAP/LIME
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
    workflow.add_edge("fast_risk", "fast_confidence")
    workflow.add_edge("fast_confidence", "fast_verdict")
    workflow.add_edge("fast_verdict", "fast_save_peer")  # NEW: Save peer data
    workflow.add_edge("fast_save_peer", "fast_report")
    workflow.add_edge("fast_report", END)  # FIXED: Direct to END
    
    # Standard track path (linear - no loops)
    workflow.add_edge("std_claim", "std_evidence")
    workflow.add_edge("std_evidence", "std_report_discovery")  # NEW: Enter report pipeline
    workflow.add_edge("std_report_discovery", "std_report_downloader")  # NEW: Download reports
    workflow.add_edge("std_report_downloader", "std_report_parser")  # NEW: Parse reports
    workflow.add_edge("std_report_parser", "std_report_claim_extractor")  # NEW: Extract claims from reports
    workflow.add_edge("std_report_claim_extractor", "std_carbon")  # Continue to carbon extraction
    workflow.add_edge("std_carbon", "std_greenwishing")  # NEW: Greenwishing
    workflow.add_edge("std_greenwishing", "std_regulatory")  # NEW: Regulatory
    workflow.add_edge("std_regulatory", "std_climatebert")  # NEW: ClimateBERT
    workflow.add_edge("std_climatebert", "std_contradiction")
    workflow.add_edge("std_contradiction", "std_temporal")
    workflow.add_edge("std_temporal", "std_peer")
    workflow.add_edge("std_peer", "std_credibility")
    workflow.add_edge("std_credibility", "std_sentiment")
    workflow.add_edge("std_sentiment", "std_realtime")
    workflow.add_edge("std_realtime", "std_temporal_consistency")  # Temporal analysis after broader evidence context
    workflow.add_edge("std_temporal_consistency", "std_risk")
    workflow.add_edge("std_risk", "std_explainability")  # NEW: SHAP/LIME after risk
    workflow.add_edge("std_explainability", "std_confidence")
    workflow.add_edge("std_confidence", "std_verdict")
    workflow.add_edge("std_verdict", "std_save_peer")
    workflow.add_edge("std_save_peer", "std_report")
    workflow.add_edge("std_report", END)
    
    # Deep analysis path (linear with debate - no loops)
    workflow.add_edge("deep_claim", "deep_evidence")
    workflow.add_edge("deep_evidence", "deep_report_discovery")  # NEW: Enter report pipeline
    workflow.add_edge("deep_report_discovery", "deep_report_downloader")  # NEW: Download reports
    workflow.add_edge("deep_report_downloader", "deep_report_parser")  # NEW: Parse reports
    workflow.add_edge("deep_report_parser", "deep_report_claim_extractor")  # NEW: Extract claims from reports
    workflow.add_edge("deep_report_claim_extractor", "deep_carbon")  # Continue to carbon extraction
    workflow.add_edge("deep_carbon", "deep_greenwishing")  # NEW: Greenwishing
    workflow.add_edge("deep_greenwishing", "deep_regulatory")  # NEW: Regulatory
    workflow.add_edge("deep_regulatory", "deep_climatebert")  # NEW: ClimateBERT
    workflow.add_edge("deep_climatebert", "deep_contradiction")
    workflow.add_edge("deep_contradiction", "deep_temporal")
    workflow.add_edge("deep_temporal", "deep_peer")
    workflow.add_edge("deep_peer", "deep_credibility")
    workflow.add_edge("deep_credibility", "deep_sentiment")
    workflow.add_edge("deep_sentiment", "deep_realtime")
    workflow.add_edge("deep_realtime", "deep_temporal_consistency")  # Temporal analysis after broader evidence context
    workflow.add_edge("deep_temporal_consistency", "deep_risk")
    workflow.add_edge("deep_risk", "deep_explainability")  # NEW: SHAP/LIME after risk
    workflow.add_edge("deep_explainability", "deep_confidence")
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
