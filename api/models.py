"""
api/models.py
-------------
Pydantic response models for the ESGLens REST API.
Mapped from the actual pipeline JSON output (ESG_Report_*.json).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ── Sub-models ────────────────────────────────────────────────────────────────

class PillarScore(BaseModel):
    score: float
    coverage_adjusted_score: Optional[float] = None
    weight: float
    positive_signals: int = 0
    contradictions: int = 0


class CarbonData(BaseModel):
    scope1: float = 0.0          # tCO2e
    scope2: float = 0.0
    scope3: float = 0.0
    total: float = 0.0
    net_zero_target: str = "Unknown"
    data_quality: int = 0        # 0-100
    iea_nze_gap_pct: Optional[float] = None
    budget_years_remaining: Optional[float] = None
    # Real annual reduction rates from carbon_pathway agent — None when the
    # agent didn't compute them (frontend then falls back to its placeholder).
    required_annual_rate: Optional[float] = None
    company_implied_rate: Optional[float] = None
    alignment_status: str = ""

    # Validation fields
    scope2_status: str = "UNKNOWN"
    scope3_status: str = "UNKNOWN"
    target_status: str = "UNKNOWN"


class Contradiction(BaseModel):
    id: str
    severity: str                 # HIGH / MEDIUM / LOW
    claim_text: str
    evidence_text: str
    source: str
    source_url: Optional[str] = None
    year: Optional[int] = None
    impact: str = ""


class EvidenceItem(BaseModel):
    id: str
    source_name: str
    source_url: Optional[str] = None
    credibility: float = 0.0     # 0-1
    stance: str                  # SUPPORTING / CONTRADICTING / NEUTRAL
    excerpt: str = ""
    year: Optional[int] = None
    source_type: str = "Unknown"
    archive_verified: bool = False


class RegulatoryItem(BaseModel):
    framework: str
    compliance_score: int = 0
    status: str                  # COMPLIANT / PARTIAL / NON-COMPLIANT
    jurisdiction: str = "Global"
    key_gap: str = ""


class GreenwashingData(BaseModel):
    overall_score: float = 0.0
    greenwishing_score: float = 0.0
    greenhushing_score: float = 0.0
    selective_disclosure: bool = False
    temporal_escalation: str = "LOW"
    carbon_tunnel_vision: bool = False
    linguistic_risk: float = 0.0
    gsi_score: float = 0.0
    boilerplate_score: float = 0.0
    climatebert_relevance: float = 0.0
    climatebert_risk: str = "LOW"


class RiskDriver(BaseModel):
    name: str
    impact: str
    direction: str = "increases_risk"
    shap_value: Optional[float] = None


class PeerEntry(BaseModel):
    name: str
    ticker: str = ""
    esg: float = 0.0
    gw: float = 0.0
    rating: str = ""
    is_focus: bool = False
    industry: str = ""
    e_score: Optional[float] = None
    s_score: Optional[float] = None
    g_score: Optional[float] = None
    rank: Optional[str] = None


class PipelineAgent(BaseModel):
    name: str
    status: str                  # queued / running / completed / error
    duration_ms: Optional[int] = None
    result_summary: Optional[str] = None
    error_message: Optional[str] = None


# ── Main report model ─────────────────────────────────────────────────────────

class ESGReport(BaseModel):
    # Identity
    id: str
    company: str
    ticker: str = ""
    sector: str = ""
    claim: str = ""
    analysis_date: str           # ISO string

    # Scores
    esg_score: float
    rating_grade: str = "B"
    risk_level: str              # HIGH / MODERATE / LOW
    confidence: float = 0.0     # 0-100

    # LLM-variance confidence bands [low, high]. Empty list when no
    # variance harness has been run yet — frontend should treat absence
    # the same as no band data.
    esg_score_band: List[float] = []
    greenwashing_band: List[float] = []
    confidence_band: List[float] = []
    band_meta: Dict[str, Any] = {}

    # Pillars
    environmental: PillarScore
    social: PillarScore
    governance: PillarScore

    # Sub-analyses
    carbon: CarbonData
    greenwashing: GreenwashingData
    contradictions: List[Contradiction] = []
    evidence: List[EvidenceItem] = []
    regulatory: List[RegulatoryItem] = []

    # Pipeline meta
    agents_total: int = 0
    agents_successful: int = 0
    pipeline_duration_seconds: float = 0.0

    # Text outputs
    ai_verdict: str = ""
    executive_summary: str = ""

    # Explainability
    top_risk_drivers: List[RiskDriver] = []

    # Peer comparison (real peers from peer_comparison agent, not hardcoded)
    peers: List[PeerEntry] = []
    peer_industry_average: Optional[Dict[str, float]] = None

    # Temporal
    temporal_score: int = 0
    temporal_risk: str = "LOW"
    claim_trend: str = ""
    environmental_trend: str = ""

    # Validation fields
    contradiction_flag: bool = False
    validation_notes: List[str] = []

    # ── New fields surfaced from session work (#2, #6, #12, #13) ──────────
    # Honest quality warnings populated by ReportQualityChecker.
    quality_warnings: List[str] = []
    # Per-agent model provenance (provider:model_id per agent_name).
    model_versions: Dict[str, Any] = {}
    # Spearman calibration honesty: linguistic-stub vs unmeasured pipeline.
    calibration: Dict[str, Any] = {}
    # KG year-over-year drift signals (signal_count + per-metric deltas).
    kg_drift: Dict[str, Any] = {}
    # Fact-graph motif diagnostics (pillar coverage, contradiction density).
    fact_graph_motifs: Dict[str, Any] = {}
    # Per-retriever yield tally so silent-failure sources are visible.
    retriever_tally: Dict[str, int] = {}
    # Climate TRACE emissions verification (Section 8C). Empty when the
    # verifier did not run for this report.
    emissions_verification: Dict[str, Any] = {}
    # SURE-RAG abstention analysis (Section 3C). Per-sub-claim
    # INSUFFICIENT_EVIDENCE / PROCEED decisions + aggregate counts.
    abstention_analysis: Dict[str, Any] = {}
    # Counterfactual (P1): pre-baked scenarios + leverage ranking.
    counterfactual: Dict[str, Any] = {}
    # F1: canonical entity record (LEI + country + aliases). Empty when
    # the resolver couldn't find a match.
    entity_record: Dict[str, Any] = {}
    company_lei: Optional[str] = None
    # P2: PCAF financed emissions (financial-services only).
    financed_emissions: Dict[str, Any] = {}
    # P3: GDELT real-time event stream (decay-weighted adverse coverage).
    gdelt_events: Dict[str, Any] = {}
    # P4: Litigation resolver (CourtListener + Indian Kanoon).
    litigation_resolved: Dict[str, Any] = {}
    # P5: Regulatory cross-ref (EPA ECHO × EDGAR XBRL).
    regulatory_cross_ref: Dict[str, Any] = {}
    # P6: Subsidiary footprint walk (GLEIF + Climate TRACE).
    subsidiary_walk: Dict[str, Any] = {}
    # P7: Longitudinal promise ledger output.
    promise_tracking: Dict[str, Any] = {}
    # P8: Cross-pillar contradiction synthesis.
    cross_pillar_contradictions: Dict[str, Any] = {}
    # P9: A3CG aspect-action-outcome triplets.
    a3cg_triplets: Dict[str, Any] = {}
    # P10: KG-RAG 2-hop retrieval per claim.
    kg_rag_retrieval: Dict[str, Any] = {}
    # P11: Multimodal vision extraction (tables/charts).
    multimodal_extraction: Dict[str, Any] = {}
    # M1: Macro / geopolitical context active during analysis. Display +
    # counterfactual layer only — never alters the headline score.
    macro_context: Dict[str, Any] = {}


# ── Request models ────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    company: str
    claim: str
    industry: Optional[str] = None
    focus_areas: Optional[List[str]] = []
    uploaded_file_ids: Optional[List[str]] = []


# ── History entry (lightweight) ───────────────────────────────────────────────

class HistoryEntry(BaseModel):
    id: str
    company: str
    ticker: str = ""
    sector: str = ""
    risk_level: str
    esg_score: float
    rating_grade: str = "B"
    greenwashing_risk: float = 0.0
    confidence: float = 0.0
    analysis_date: str           # ISO string
    claim: str = ""
    ai_verdict_short: str = ""   # first 120 chars of verdict
    contradictions_count: int = 0
    agents_run: int = 0
    duration_seconds: float = 0.0


# ── WebSocket pipeline update ─────────────────────────────────────────────────

class PipelineUpdate(BaseModel):
    analysis_id: str
    agent_name: str
    status: str                  # queued / running / completed / error
    result_summary: Optional[str] = None
    progress_pct: float = 0.0   # 0-100
    elapsed_seconds: float = 0.0
    partial_results: Optional[Dict[str, Any]] = None
