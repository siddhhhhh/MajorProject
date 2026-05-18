"""
State schema for ESG Greenwashing Detection System
Defines the data structure passed between agents
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator
from core.enums import AgentStatus


def _dedupe_agent_outputs(left: List[Dict], right: List[Dict]) -> List[Dict]:
    """Custom LangGraph reducer for agent_outputs.

    Keeps ONLY the last output per agent name. This prevents the
    operator.add explosion (16M+ entries) that occurs when LangGraph
    concatenates the list on every state checkpoint merge across
    20+ pipeline nodes.

    The result is a bounded list (one entry per agent).
    """
    if not isinstance(left, list):
        left = []
    if not isinstance(right, list):
        right = []
    # Build ordered dict: later entries (from right) win per agent name
    merged: Dict[str, Dict] = {}
    for item in left:
        if isinstance(item, dict):
            key = item.get("agent", id(item))
            merged[key] = item
    for item in right:
        if isinstance(item, dict):
            key = item.get("agent", id(item))
            merged[key] = item
    return list(merged.values())

class ESGState(TypedDict):
    """
    Central state object for LangGraph workflow
    All agents read from and write to this state
    Enhanced with ML and financial analysis support
    """
    # Input fields
    claim: str
    company: str
    industry: str
    
    # Routing and workflow control
    complexity_score: float
    workflow_path: str  # "fast_track", "standard_track", "deep_analysis"
    
    # Evidence and analysis
    evidence: List[Dict[str, Any]]
    confidence: float
    risk_level: str  # "HIGH", "MODERATE", "LOW"
    rating_grade: Optional[str]  # "AAA", "AA", "A", "BBB", "BB", "B", "CCC"
    
    # Agent collaboration
    agent_outputs: Annotated[List[Dict], _dedupe_agent_outputs]  # Deduped per-agent outputs (bounded list)
    iteration_count: int
    needs_revision: bool
    verdict_locked: Optional[bool]  # Prevents verdict override when domain knowledge is applied
    
    # Financial analysis (from Agent #14)
    financial_context: Optional[Dict[str, Any]]  # From FinancialAnalyst
    
    # ML model metadata
    ml_prediction: Optional[Dict[str, Any]]  # From XGBoost risk model
    
    # NEW: Data Enrichment (2026 Features)
    indian_financials: Optional[Dict[str, Any]]  # Revenue, profit from Screener/Yahoo/NSE
    company_reports: Optional[Dict[str, Any]]  # PDF reports with extracted ESG metrics
    carbon_extraction: Optional[Dict[str, Any]]  # Scope 1/2/3 carbon analysis
    emissions_verification: Optional[Dict[str, Any]]  # Climate TRACE satellite-derived cross-check (A2)
    abstention_analysis: Optional[Dict[str, Any]]  # SURE-RAG per-sub-claim abstention decisions (A4)
    entity_record: Optional[Dict[str, Any]]  # Canonical entity (LEI, country_iso3, aliases) from F1
    company_lei: Optional[str]  # Convenience accessor; mirrors entity_record.lei
    evidence_graph: Optional[Dict[str, Any]]  # F3 typed evidence graph (JSON adjacency)
    financed_emissions: Optional[Dict[str, Any]]  # PCAF financed emissions for banks (P2)
    gdelt_events: Optional[Dict[str, Any]]  # GDELT adverse-event stream (P3)
    litigation_resolved: Optional[Dict[str, Any]]  # CourtListener + Indian Kanoon dockets (P4)
    regulatory_cross_ref: Optional[Dict[str, Any]]  # EPA ECHO × EDGAR XBRL integrity signal (P5)
    subsidiary_walk: Optional[Dict[str, Any]]  # Subsidiary footprint via GLEIF (P6)
    promise_tracking: Optional[Dict[str, Any]]  # Longitudinal promise ledger output (P7)
    cross_pillar_contradictions: Optional[Dict[str, Any]]  # Cross-pillar synthesis (P8)
    a3cg_triplets: Optional[Dict[str, Any]]  # A3CG aspect-action-outcome triplets (P9)
    kg_rag_retrieval: Optional[Dict[str, Any]]  # KG-RAG 2-hop graph retrieval per claim (P10)
    multimodal_extraction: Optional[Dict[str, Any]]  # Multimodal table/chart extraction (P11)
    macro_context: Optional[Dict[str, Any]]  # Geopolitical / macro events active during analysis (M1)
    regulatory_registry_snapshot: Optional[Dict[str, Any]]  # Active framework registry version + status digest (Reg-A)
    external_esg_data: Optional[Dict[str, Any]]  # WBA/WRI benchmark enrichment used in risk scoring
    fact_graph: Optional[Dict[str, Any]]  # Justification-centric ESG fact graph
    fact_graph_path: Optional[str]  # Persisted JSON artifact for the fact graph
    company_knowledge_graph: Optional[Dict[str, Any]]  # Persistent company-centric KG status/payload metadata
    
    # NEW: Advanced Detection (2026 Features)
    greenwishing_analysis: Optional[Dict[str, Any]]  # Greenwishing/greenhushing detection
    regulatory_compliance: Optional[Dict[str, Any]]  # Regulatory horizon scanning
    climatebert_analysis: Optional[Dict[str, Any]]  # ClimateBERT NLP analysis  
    esg_mismatch_analysis: Optional[Dict[str, Any]]  # Promise vs Actual gap detection
    social_analysis: Optional[Dict[str, Any]]  # Dedicated social pillar analysis
    governance_analysis: Optional[Dict[str, Any]]  # Dedicated governance pillar analysis
    explainability_report: Optional[Dict[str, Any]]  # SHAP/LIME explanations
    adversarial_audit: Optional[Dict[str, Any]]  # Multi-agent coordination risk diagnostics
    claim_decomposition: Optional[Dict[str, Any]]  # Decomposed sub-claims and internal tensions
    adversarial_triangulation: Optional[Dict[str, Any]]  # Supporting vs contradicting evidence balance
    carbon_pathway_analysis: Optional[Dict[str, Any]]  # Pathway alignment and feasibility output
    commitment_ledger: Optional[Dict[str, Any]]  # Longitudinal commitment/revision tracker summary
    additional_evidence: Optional[List[Dict[str, Any]]]
    research_telemetry: Optional[Dict[str, Any]]
    research_telemetry_path: Optional[str]
    
    # NEW: Risk Scoring Overhaul — Five-variable GW formula inputs
    claim_intensity: Optional[Dict[str, Any]]       # C: Claim Intensity Score from claim_intensity_scorer
    controversy_risk: Optional[Dict[str, Any]]      # R: Controversy Risk Score from regulatory scanner
    temporal_escalation: Optional[Dict[str, Any]]   # T: Temporal Escalation Score from temporal agent
    
    # Final output
    final_verdict: Dict[str, Any]
    report: str
    esg_score_lineage: Optional[Dict[str, Any]]  # Diagnostic breakdown of GW formula variables (C, P, R, D, T)
    riskresults: Optional[Dict[str, Any]]  # Canonical risk scorer output (pillar scores, GW score, rating)
    
    # Unified Dual-Objective Assessment (Problem #15 fix)
    unified_assessment: Optional[Dict[str, Any]]  # Co-primary ESG + GW output with consistency enforcement
    evidence_gap_analysis: Optional[Dict[str, Any]]  # Claim-evidence requirement gap tracking (Problem #4 fix)
    
    # Pipeline status
    pipeline_agent_statuses: Dict[str, AgentStatus]

# Input state for user-facing API
class InputState(TypedDict):
    claim: str
    company: str
    industry: str

# Output state for user-facing API
class OutputState(TypedDict):
    risk_level: str
    confidence: float
    evidence: List[Dict[str, Any]]
    agent_trace: List[Dict]
    report: str
