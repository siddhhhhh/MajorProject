"""
State schema for ESG Greenwashing Detection System
Defines the data structure passed between agents
"""
from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator

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
    agent_outputs: Annotated[List[Dict], operator.add]  # Append-only list
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
    
    # NEW: Advanced Detection (2026 Features)
    greenwishing_analysis: Optional[Dict[str, Any]]  # Greenwishing/greenhushing detection
    regulatory_compliance: Optional[Dict[str, Any]]  # Regulatory horizon scanning
    climatebert_analysis: Optional[Dict[str, Any]]  # ClimateBERT NLP analysis  
    explainability_report: Optional[Dict[str, Any]]  # SHAP/LIME explanations
    
    # Final output
    final_verdict: Dict[str, Any]
    report: str

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
