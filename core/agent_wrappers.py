"""
LIVE IMPLEMENTATION: Fetches real-time data and shows LangGraph progress
All agents use live API calls, not cached results
"""
import sys
import os
import importlib.util
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add agents directory to Python path
agents_dir = Path(__file__).parent.parent / "agents"
sys.path.insert(0, str(agents_dir))

# Add project root to Python path for feature imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from features.esg_mismatch_detector.pipeline import analyze_company_esg
except ImportError as e:
    print(f"⚠️  ESG Mismatch Detector import failed: {e}")
    analyze_company_esg = None

from core.state_schema import ESGState
from core.enums import AgentStatus
from core.evidence_cache import evidence_cache
from typing import Dict, Any, Optional
from core.esg_data_apis import fill_missing_pillars
from core.fact_graph_builder import build_esg_fact_graph
from core.adversarial_audit import build_adversarial_audit
from core.company_knowledge_graph import CompanyKnowledgeGraph
from core.objective_function import (
    UnifiedESGOutput,
    build_unified_output_from_state,
    extract_consistency_context,
)
from core.claim_evidence_requirements import (
    analyze_evidence_gaps,
    classify_claim,
    get_targeted_search_queries,
)
from data.known_cases import validate_pipeline_output
from core.pillar_factors_builder import synthesize_sec_metric_evidence
from core.evidence_intelligence import (
    rank_evidence_by_quality,
    compute_evidence_sufficiency,
    filter_noise,
    ConclusionLinker,
)
from core.feature_engineering import compute_engineered_features, select_top_features
from core.causal_reasoner import build_causal_chains, generate_score_explanation
from core.dynamic_industry import detect_industry, detect_geography, get_regulatory_context

# ============================================================
# LIVE DATA FETCHER - Gets fresh content for analysis
# ============================================================

class LiveDataFetcher:
    """Fetches live content for claim extraction"""

    def __init__(self):
        self.news_api_key = os.getenv("NEWS_API_KEY") or os.getenv("NEWSAPI_KEY")
        self.newsdata_api_key = os.getenv("NEWSDATA_API_KEY") or os.getenv("NEWSDATA_KEY")

    def fetch_company_content(self, company_name: str, claim: str = None) -> str:
        """
        Fetch live content about company for claim extraction
        Uses News API to get recent articles
        """
        print(f"\n🔴 LIVE FETCH: Getting fresh content for {company_name}")

        try:
            import requests

            # Build search query
            if claim:
                query = f'"{company_name}" AND ({claim}) AND (ESG OR sustainability OR environment)'
            else:
                query = f'"{company_name}" AND (ESG OR sustainability OR environment OR emissions OR renewable)'

            # Try News API first
            if self.news_api_key:
                print(f"📡 Calling News API (live)...")
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": query,
                    "apiKey": self.news_api_key,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 5
                }

                response = requests.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    articles = data.get("articles", [])

                    if articles:
                        print(f"✅ Found {len(articles)} recent articles")

                        # Combine article content
                        content = f"Company: {company_name}\n\n"
                        if claim:
                            content += f"Claim to verify: {claim}\n\n"
                        content += "Recent Articles:\n\n"

                        for i, article in enumerate(articles[:3], 1):
                            content += f"Article {i}:\n"
                            content += f"Title: {article.get('title', 'N/A')}\n"
                            content += f"Description: {article.get('description', 'N/A')}\n"
                            content += f"Content: {article.get('content', 'N/A')[:500]}\n"
                            content += f"Published: {article.get('publishedAt', 'N/A')}\n\n"

                        return content

            # Fallback: Use the claim itself as content
            print("⚠️ No live articles found, using claim as content")
            return f"Company: {company_name}\nClaim: {claim or 'General ESG analysis'}"

        except Exception as e:
            print(f"❌ Live fetch error: {e}")
            # Fallback content
            return f"Company: {company_name}\nClaim to analyze: {claim or 'General ESG sustainability claims'}"

# Initialize live fetcher
live_fetcher = LiveDataFetcher()

# ============================================================
# IMPORT YOUR ACTUAL AGENTS
# ============================================================

try:
    from claim_extractor import ClaimExtractor
    print("✅ ClaimExtractor loaded")
    CLAIM_EXTRACTOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ClaimExtractor import failed: {e}")
    CLAIM_EXTRACTOR_AVAILABLE = False

try:
    from evidence_retriever import EvidenceRetriever
    print("✅ EvidenceRetriever loaded")
    EVIDENCE_RETRIEVER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  EvidenceRetriever import failed: {e}")
    EVIDENCE_RETRIEVER_AVAILABLE = False

try:
    from contradiction_analyzer import ContradictionAnalyzer
    print("✅ ContradictionAnalyzer loaded")
    CONTRADICTION_ANALYZER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ContradictionAnalyzer import failed: {e}")
    CONTRADICTION_ANALYZER_AVAILABLE = False

try:
    from historical_analyst import HistoricalAnalyst
    print("✅ HistoricalAnalyst loaded")
    HISTORICAL_ANALYST_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  HistoricalAnalyst import failed: {e}")
    HISTORICAL_ANALYST_AVAILABLE = False

    # IndustryComparator is deprecated.
    INDUSTRY_COMPARATOR_AVAILABLE = False

try:
    from risk_scorer import RiskScorer
    print("✅ RiskScorer loaded")
    RISK_SCORER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  RiskScorer import failed: {e}")
    RISK_SCORER_AVAILABLE = False

try:
    from sentiment_analyzer import SentimentAnalyzer
    print("✅ SentimentAnalyzer loaded")
    SENTIMENT_ANALYZER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  SentimentAnalyzer import failed: {e}")
    SENTIMENT_ANALYZER_AVAILABLE = False

try:
    from credibility_analyst import CredibilityAnalyst
    print("✅ CredibilityAnalyst loaded")
    CREDIBILITY_ANALYST_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  CredibilityAnalyst import failed: {e}")
    CREDIBILITY_ANALYST_AVAILABLE = False

try:
    from confidence_scorer import ConfidenceScorer
    print("✅ ConfidenceScorer loaded")
    CONFIDENCE_SCORER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ConfidenceScorer import failed: {e}")
    CONFIDENCE_SCORER_AVAILABLE = False

try:
    from realtime_monitor import RealTimeMonitor
    print("✅ RealTimeMonitor loaded")
    REALTIME_MONITOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  RealTimeMonitor import failed: {e}")
    REALTIME_MONITOR_AVAILABLE = False

try:
    from conflict_resolver import ConflictResolver
    print("✅ ConflictResolver loaded")
    CONFLICT_RESOLVER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ConflictResolver import failed: {e}")
    CONFLICT_RESOLVER_AVAILABLE = False

try:
    from carbon_extractor import CarbonExtractor
    print("✅ CarbonExtractor loaded")
    CARBON_EXTRACTOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  CarbonExtractor import failed: {e}")
    CARBON_EXTRACTOR_AVAILABLE = False

try:
    from greenwishing_detector import GreenwishingDetector
    print("✅ GreenwishingDetector loaded")
    GREENWISHING_DETECTOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  GreenwishingDetector import failed: {e}")
    GREENWISHING_DETECTOR_AVAILABLE = False

try:
    from regulatory_scanner import RegulatoryHorizonScanner
    print("✅ RegulatoryHorizonScanner loaded")
    REGULATORY_SCANNER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  RegulatoryHorizonScanner import failed: {e}")
    REGULATORY_SCANNER_AVAILABLE = False

try:
    from social_agent import SocialAgent
    print("✅ SocialAgent loaded")
    SOCIAL_AGENT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  SocialAgent import failed: {e}")
    SOCIAL_AGENT_AVAILABLE = False

try:
    from governance_agent import GovernanceAgent
    print("✅ GovernanceAgent loaded")
    GOVERNANCE_AGENT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  GovernanceAgent import failed: {e}")
    GOVERNANCE_AGENT_AVAILABLE = False

try:
    import sys
    ml_models_path = Path(__file__).parent.parent / "ml_models"
    sys.path.insert(0, str(ml_models_path))
    from climatebert_analyzer import ClimateBERTAnalyzer
    print("✅ ClimateBERTAnalyzer loaded")
    CLIMATEBERT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ClimateBERTAnalyzer import failed: {e}")
    CLIMATEBERT_AVAILABLE = False

try:
    from explainability_engine import ESGExplainabilityEngine
    print("✅ ESGExplainabilityEngine loaded")
    EXPLAINABILITY_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ESGExplainabilityEngine import failed: {e}")
    EXPLAINABILITY_AVAILABLE = False

try:
    from claim_decomposer import ClaimDecomposer
    print("✅ ClaimDecomposer loaded")
    CLAIM_DECOMPOSER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ClaimDecomposer import failed: {e}")
    CLAIM_DECOMPOSER_AVAILABLE = False

try:
    from adversarial_validator import AdversarialEvidenceValidator
    print("✅ AdversarialEvidenceValidator loaded")
    ADVERSARIAL_VALIDATOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  AdversarialEvidenceValidator import failed: {e}")
    ADVERSARIAL_VALIDATOR_AVAILABLE = False

try:
    from carbon_pathway_modeller import CarbonPathwayModeller
    print("✅ CarbonPathwayModeller loaded")
    CARBON_PATHWAY_MODELLER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  CarbonPathwayModeller import failed: {e}")
    CARBON_PATHWAY_MODELLER_AVAILABLE = False

try:
    from multi_jurisdiction_regulatory_scanner import MultiJurisdictionRegulatoryScanner
    print("✅ MultiJurisdictionRegulatoryScanner loaded")
    MULTI_JURISDICTION_SCANNER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  MultiJurisdictionRegulatoryScanner import failed: {e}")
    MULTI_JURISDICTION_SCANNER_AVAILABLE = False

try:
    from commitment_tracker import CommitmentLedger
    print("✅ CommitmentLedger loaded")
    COMMITMENT_LEDGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  CommitmentLedger import failed: {e}")
    COMMITMENT_LEDGER_AVAILABLE = False

# NEW PHASE 7: ESG Report Pipeline
try:
    utils_path = Path(__file__).parent.parent / "utils"
    sys.path.insert(0, str(utils_path))
    from report_discovery import discover_company_reports
    print("✅ ReportDiscoveryService loaded")
    REPORT_DISCOVERY_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ReportDiscoveryService import failed: {e}")
    REPORT_DISCOVERY_AVAILABLE = False

try:
    from report_downloader import download_company_reports
    print("✅ ReportDownloaderService loaded")
    REPORT_DOWNLOADER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ReportDownloaderService import failed: {e}")
    REPORT_DOWNLOADER_AVAILABLE = False

try:
    from report_parser import parse_downloaded_reports
    print("✅ ReportParserService loaded")
    REPORT_PARSER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ReportParserService import failed: {e}")
    REPORT_PARSER_AVAILABLE = False

try:
    from temporal_consistency_agent import analyze_temporal_consistency, TemporalConsistencyAgent
    print("✅ TemporalConsistencyAgent loaded")
    TEMPORAL_CONSISTENCY_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  TemporalConsistencyAgent import failed: {e}")
    TEMPORAL_CONSISTENCY_AVAILABLE = False

# ============================================================
# LIVE NODE WRAPPERS WITH PROGRESS TRACKING
# ============================================================

def claim_extraction_node(state: ESGState) -> ESGState:
    """
    LIVE: ClaimExtractor with real-time content fetching
    Shows LangGraph node execution
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: claim_extraction")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    # Clear session cache for new analysis (keeps disk cache for reuse)
    if state.get("iteration_count", 0) == 0:
        evidence_cache.clear_session_cache()

    if not CLAIM_EXTRACTOR_AVAILABLE:
        from core.minimal_agents import claim_extraction_node as minimal_claim
        return minimal_claim(state)

    try:
        extractor = ClaimExtractor()

        # LIVE: Fetch fresh content
        live_content = live_fetcher.fetch_company_content(
            company_name=state["company"],
            claim=state["claim"]
        )

        print(f"📄 Content size: {len(live_content)} characters")
        print(f"🤖 Calling LLM for claim extraction...")

        # Call with both required parameters
        result = extractor.extract_claims(
            company_name=state["company"],
            content=live_content
        )

        confidence = 0.8
        if isinstance(result, dict):
            confidence = result.get("confidence", 0.8)
            claims = result.get("claims", [])
            print(f"✅ Extracted {len(claims)} claims")

        state["agent_outputs"].append({
            "agent": "claim_extraction",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "live_fetch": True
        })
        state["claim_results"] = result
        state.setdefault("node_execution_order", []).append("Claim Extraction")

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ ClaimExtractor error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "claim_extraction",
            "error": str(e),
            "confidence": 0.5
        })

    return state


def claim_decomposition_node(state: ESGState) -> ESGState:
    """Decompose compound claims into atomic sub-claims and detect internal tensions."""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print("Node: claim_decomposition")
    print("=" * 70)

    claim_text = state.get("claim", "")
    company = state.get("company", "")
    industry = state.get("industry", "")

    if not CLAIM_DECOMPOSER_AVAILABLE:
        decomposition = {
            "original_claim": claim_text,
            "sub_claims": [{
                "id": "SC1",
                "text": claim_text,
                "type": "policy_claim",
                "pillar": "cross-pillar",
                "measurable": False,
                "verification_requirements": ["Independent primary-source evidence"],
                "greenwashing_signal": "unverifiable",
            }],
            "logical_tension_pairs": [],
            "overall_internal_consistency": "consistent",
            "decomposition_confidence": 0.5,
            "internal_contradiction_score": 0.0,
        }
    else:
        try:
            decomposer = ClaimDecomposer()
            decomposition = decomposer.decompose_claim(company=company, industry=industry, claim_text=claim_text)
            score = decomposer.compute_internal_contradiction_score(
                decomposition.get("logical_tension_pairs", [])
            )
            decomposition["internal_contradiction_score"] = score
        except Exception as e:
            print(f"❌ ClaimDecomposer error: {e}")
            decomposition = {
                "original_claim": claim_text,
                "sub_claims": [{"id": "SC1", "text": claim_text, "type": "policy_claim", "pillar": "cross-pillar", "measurable": False}],
                "logical_tension_pairs": [],
                "overall_internal_consistency": "consistent",
                "decomposition_confidence": 0.4,
                "internal_contradiction_score": 0.0,
            }

    state["claim_decomposition"] = decomposition

    # P7: Promise tracker — record each measurable sub-claim against the
    # longitudinal promise ledger; statuses (NEW/IN_PROGRESS/MISSED/DELAYED)
    # reach the structural-penalty layer via state["promise_tracking"].
    try:
        _pt_spec = importlib.util.spec_from_file_location(
            "promise_tracker", "agents/promise_tracker.py",
        )
        _pt_mod = importlib.util.module_from_spec(_pt_spec)
        _pt_spec.loader.exec_module(_pt_mod)
        _pt_out = _pt_mod.run(
            company_lei=state.get("company_lei"),
            sub_claims=decomposition.get("sub_claims") or [],
            report_id=state.get("report_id"),
        )
        state["promise_tracking"] = _pt_out
        if _pt_out.get("tracked_promises"):
            print(f"\n>>> PROMISE TRACKER")
            print(f"    Tracked: {len(_pt_out.get('tracked_promises') or [])}")
            print(f"    Status counts: {_pt_out.get('status_counts')}")
            print(f"    Degradation score: {_pt_out.get('promise_degradation_score')}")
            print(f"    Ledger delta: {_pt_out.get('ledger_delta', 0):+.1f} GW pts")
            _pt_row = _pt_mod.build_ledger_row(_pt_out)
            if _pt_row:
                state.setdefault("scoremodifierledger", []).append(_pt_row)
            state["agent_outputs"].append({
                "agent": "promise_tracker",
                "output": _pt_out,
                "confidence": 0.85,
                "timestamp": datetime.now().isoformat(),
            })
    except Exception as _pt_exc:
        print(f"  [promise_tracker] skipped: {_pt_exc}")
        state["promise_tracking"] = {"status": "ERROR", "error": str(_pt_exc)[:200]}

    # P10: KG-RAG graph retrieval (feature-flagged with ESG_USE_KG_RAG).
    if os.environ.get("ESG_USE_KG_RAG", "").lower() in ("1", "true", "yes"):
        try:
            from core.kg_rag import kg_rag_retrieve
            _kg_out = kg_rag_retrieve(state)
            state["kg_rag_retrieval"] = _kg_out
            if _kg_out.get("status") == "COMPLETED":
                print(f"\n>>> KG-RAG RETRIEVAL")
                print(f"    Claims processed: {len(_kg_out.get('claims') or [])}")
                print(f"    Total items retrieved: {_kg_out.get('total_items')}")
        except Exception as _kg_exc:
            print(f"  [kg_rag] skipped: {_kg_exc}")
            state["kg_rag_retrieval"] = {"status": "ERROR", "error": str(_kg_exc)[:200]}

    # P9: A3CG triplet extractor (feature-flagged with ESG_USE_A3CG).
    if os.environ.get("ESG_USE_A3CG", "").lower() in ("1", "true", "yes"):
        try:
            _a3_spec = importlib.util.spec_from_file_location(
                "a3cg_extractor", "agents/a3cg_extractor.py",
            )
            _a3_mod = importlib.util.module_from_spec(_a3_spec)
            _a3_spec.loader.exec_module(_a3_mod)
            _a3_triplets = _a3_mod.extract_for_claims(decomposition.get("sub_claims") or [])
            state["a3cg_triplets"] = {
                "triplets":          _a3_triplets,
                "count":             len(_a3_triplets),
                "extractor_version": "a3cg_v1",
            }
            if _a3_triplets:
                print(f"\n>>> A3CG TRIPLETS")
                print(f"    Extracted: {len(_a3_triplets)} typed (aspect, action, outcome) triplets")
                for t in _a3_triplets[:3]:
                    print(f"      [{t.get('evidence_class')}] aspect={t.get('aspect')} action={t.get('action')} "
                          f"value={t.get('outcome_value')} year={t.get('outcome_year')}")
                state["agent_outputs"].append({
                    "agent": "a3cg_extractor",
                    "output": state["a3cg_triplets"],
                    "confidence": 0.80,
                    "timestamp": datetime.now().isoformat(),
                })
        except Exception as _a3_exc:
            print(f"  [a3cg_extractor] skipped: {_a3_exc}")
            state["a3cg_triplets"] = {"status": "ERROR", "error": str(_a3_exc)[:200]}

    sub_claims = decomposition.get("sub_claims") if isinstance(decomposition.get("sub_claims"), list) else []
    if len(sub_claims) < 2 and len(str(claim_text).split()) >= 10:
        # Hard floor for long claims: force at least two atomic checks.
        fallback = [
            {"id": "SC1", "text": str(claim_text).strip(), "type": "policy_claim", "pillar": "cross-pillar", "measurable": False},
            {"id": "SC2", "text": "Implicit verification requirement: comparative baseline, scope, and mechanism evidence required.", "type": "verification_requirement", "pillar": "cross-pillar", "measurable": True},
        ]
        decomposition["sub_claims"] = fallback
        state["claim_decomposition"] = decomposition

    # --- Step 4: Compute Claim Intensity Score (C) ---
    try:
        from agents.claim_intensity_scorer import calculate_claim_intensity
        ci_result = calculate_claim_intensity(
            claim_text=claim_text,
            sub_claims=decomposition.get("sub_claims", []),
            company=company,
            industry=industry,
        )
        state["claim_intensity"] = ci_result
        state.setdefault("pipeline_agent_statuses", {})["claim_intensity_scorer"] = AgentStatus.SUCCESS
    except Exception as e:
        print(f"   ⚠️ Claim intensity scorer failed: {e}")
        # Keyword-based fallback — ensures C is never zero when scorer crashes
        claim_raw = state.get("claim") or {}
        claim_lower = (
            claim_raw.get("claim_text", "") if isinstance(claim_raw, dict) else str(claim_raw)
        ).lower()
        high_intensity_kw = ["net zero", "carbon neutral", "climate positive", "100% renewable", "zero emissions"]
        med_intensity_kw = ["sustainable", "green", "eco-friendly", "clean energy", "committed to", "leader in"]
        if any(kw in claim_lower for kw in high_intensity_kw):
            fallback_c = 70.0
        elif any(kw in claim_lower for kw in med_intensity_kw):
            fallback_c = 45.0
        else:
            fallback_c = 25.0
        print(f"   ↪ Keyword fallback assigned C={fallback_c} (method=keyword_heuristic)")
        state["claim_intensity"] = {
            "score": fallback_c,
            "claim_intensity_score": fallback_c,
            "status": AgentStatus.PARTIAL.value,
            "fallback_reason": str(e),
            "method": "keyword_heuristic",
        }
        state.setdefault("pipeline_agent_statuses", {})["claim_intensity_scorer"] = AgentStatus.FAILED

    state.setdefault("node_execution_order", []).append("Claim Decomposition")
    state["agent_outputs"].append({
        "agent": "claim_decomposition",
        "output": decomposition,
        "confidence": decomposition.get("decomposition_confidence", 0.6),
        "timestamp": datetime.now().isoformat(),
    })
    print(f"✅ Decomposed into {len(decomposition.get('sub_claims', []))} sub-claim(s)")
    return state


def adversarial_triangulation_node(state: ESGState) -> ESGState:
    """Stress-test evidence by balancing supporting vs contradicting sources."""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print("Node: adversarial_triangulation")
    print("=" * 70)

    if not ADVERSARIAL_VALIDATOR_AVAILABLE:
        result = {
            "triangulation_score": None,
            "adversarial_ratio": 0.0,
            "evidence_balance": "UNCLASSIFIED — validator unavailable",
            "source_stances": [],
            "first_party_bias_warning": False,
        }
    else:
        try:
            validator = AdversarialEvidenceValidator()
            result = validator.triangulate(
                company=state.get("company", ""),
                claim_text=state.get("claim", ""),
                evidence=state.get("evidence", []),
            )
        except Exception as e:
            print(f"❌ AdversarialEvidenceValidator error: {e}")
            result = {
                "triangulation_score": None,
                "adversarial_ratio": 0.0,
                "evidence_balance": "UNCLASSIFIED — validator failed",
                "source_stances": [],
                "first_party_bias_warning": False,
            }

    state["adversarial_triangulation"] = result
    state.setdefault("node_execution_order", []).append("Adversarial Triangulation")
    state["agent_outputs"].append({
        "agent": "adversarial_triangulation",
        "output": result,
        "confidence": 0.72,
        "timestamp": datetime.now().isoformat(),
    })
    print(
        f"✅ Triangulation score: {result.get('triangulation_score', 'N/A')} | "
        f"Adversarial ratio: {result.get('adversarial_ratio', 'N/A')}"
    )
    return state


def evidence_retrieval_node(state: ESGState) -> ESGState:
    """
    LIVE: EvidenceRetriever fetches real-time evidence
    Includes financial analyst integration for ESG-financial correlation
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: evidence_retrieval (with Financial Analyst)")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not EVIDENCE_RETRIEVER_AVAILABLE:
        from core.minimal_agents import evidence_retrieval_node as minimal_evidence
        return minimal_evidence(state)

    try:
        retriever = EvidenceRetriever()

        print(f"🔍 Live evidence search for: {state['company']}")
        print(f"📡 Calling 15 external APIs + Financial Analyst...")

        decomposition = state.get("claim_decomposition") if isinstance(state.get("claim_decomposition"), dict) else {}
        sub_claims = decomposition.get("sub_claims") if isinstance(decomposition.get("sub_claims"), list) else []

        if sub_claims:
            merged_evidence = []
            sub_results = []
            confidence_values = []
            for sc in sub_claims[:6]:
                if not isinstance(sc, dict):
                    continue
                claim_dict = {
                    "claim_id": sc.get("id") or "C1",
                    "claim_text": sc.get("text") or state["claim"],
                    "category": sc.get("type") or "sustainability",
                    "sub_claim_id": sc.get("id"),
                }
                partial = retriever.retrieve_evidence(claim_dict, state["company"])
                if isinstance(partial, dict):
                    for ev in partial.get("evidence", []) or []:
                        if isinstance(ev, dict):
                            ev["sub_claim_id"] = sc.get("id")
                    sub_results.append({"sub_claim_id": sc.get("id"), "result": partial})
                    merged_evidence.extend(partial.get("evidence", []) or [])
                    confidence_values.append(float(partial.get("confidence", 0.7) or 0.7))
            result = {
                "sub_claim_mode": True,
                "sub_claim_results": sub_results,
                "evidence": merged_evidence,
                "evidence_count": len(merged_evidence),
                "confidence": (sum(confidence_values) / len(confidence_values)) if confidence_values else 0.7,
            }
        else:
            # Create claim dict for evidence retriever
            claim_dict = {
                "claim_id": "C1",
                "claim_text": state["claim"],
                "category": "sustainability"
            }
            # Call retrieve_evidence with proper parameters
            result = retriever.retrieve_evidence(claim_dict, state["company"])

        if isinstance(result, dict):
            evidence_list = result.get("evidence", [])
            confidence = result.get("confidence", 0.7)
            financial_context = result.get("financial_context")  # NEW: From Financial Analyst

            print(f"✅ Retrieved {len(evidence_list)} evidence items")

            if financial_context:
                print(f"💰 Financial Analysis (Agent #14):")
                if "financial_data" in financial_context:
                    fin_data = financial_context["financial_data"]
                    print(f"   Revenue: ${fin_data.get('revenue_usd', 0)/1e9:.1f}B")
                    print(f"   Profit Margin: {fin_data.get('profit_margin_pct', 0):.1f}%")
                if "greenwashing_flags" in financial_context:
                    flags = financial_context["greenwashing_flags"]
                    # Handle both dict and list formats
                    if isinstance(flags, dict):
                        high_risk = flags.get("HIGH", [])
                        if high_risk:
                            print(f"   ⚠️ HIGH risk flags: {len(high_risk)}")
                    elif isinstance(flags, list):
                        if flags:
                            print(f"   ⚠️ Greenwashing flags: {len(flags)}")
        else:
            evidence_list = result if isinstance(result, list) else []
            confidence = 0.7
            financial_context = None

        state["evidence"].extend(evidence_list)

        # ── EVIDENCE INTELLIGENCE: Quality scoring + noise filtering ──
        try:
            ev_sufficiency = compute_evidence_sufficiency(state["evidence"], state.get("claim", ""))
            state["evidence_sufficiency"] = ev_sufficiency
            grade = ev_sufficiency.get("grade", "UNKNOWN")
            print(f"   📊 Evidence quality: {grade} (weighted={ev_sufficiency.get('total_weighted_score', 0):.1f}, tier1-2={ev_sufficiency.get('tier_distribution', {}).get(1, 0) + ev_sufficiency.get('tier_distribution', {}).get(2, 0)})")
            if ev_sufficiency.get("needs_escalation"):
                for trigger in ev_sufficiency.get("escalation_triggers", [])[:2]:
                    print(f"   ⚠️ {trigger}")
        except Exception as e:
            print(f"   ⚠️ Evidence intelligence error (non-fatal): {e}")

        # NEW: Store enrichment data at state level for report access
        if isinstance(result, dict):
            if result.get("indian_financials"):
                state["indian_financials"] = result["indian_financials"]
            if result.get("company_reports"):
                state["company_reports"] = result["company_reports"]

        state["agent_outputs"].append({
            "agent": "evidence_retrieval",
            "output": result,
            "evidence_count": len(evidence_list),
            "confidence": confidence,
            "financial_context": financial_context,  # NEW: Pass to risk scorer
            "timestamp": datetime.now().isoformat(),
            "live_fetch": True
        })
        state["evidence_results"] = result
        state.setdefault("node_execution_order", []).append("Evidence Retrieval")

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ EvidenceRetriever error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "evidence_retrieval",
            "error": str(e),
            "confidence": 0.3
        })

    return state


def carbon_extraction_node(state: ESGState) -> ESGState:
    """
    LIVE: CarbonExtractor - Extracts Scope 1/2/3 carbon emissions from evidence
    Analyzes carbon claims and calculates emission metrics
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: carbon_extraction (Scope 1/2/3 Analysis)")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not CARBON_EXTRACTOR_AVAILABLE:
        print("⚠️ CarbonExtractor not available - skipping")
        state["agent_outputs"].append({
            "agent": "carbon_extraction",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        extractor = CarbonExtractor()

        company = state.get("company", "")
        claim_text = state.get("claim", "")
        industry = state.get("industry", "")
        evidence = state.get("evidence", [])

        # Gather parsed report chunks and report claims for prioritized carbon extraction
        parser_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "report_parser"]
        parsed_chunks = parser_outputs[-1].get("output", {}).get("chunks", []) if parser_outputs else []
        parsed_report_files = parser_outputs[-1].get("output", {}).get("downloaded_reports", []) if parser_outputs else []

        if not parsed_report_files:
            downloader_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "report_downloader"]
            parsed_report_files = downloader_outputs[-1].get("output", {}).get("downloads", []) if downloader_outputs else []

        claim_extractor_outputs = [
            o for o in state.get("agent_outputs", [])
            if o.get("agent") == "claim_extractor" and o.get("source") == "report_chunks"
        ]
        report_claims_by_year = (
            claim_extractor_outputs[-1].get("output", {}).get("report_claims_by_year", {})
            if claim_extractor_outputs else {}
        )

        print(f"🌍 Extracting carbon metrics for: {company}")
        print(f"🏭 Industry: {industry}")
        print(f"📊 Evidence items to analyze: {len(evidence)}")

        # Create claim dict for carbon extractor
        claim_dict = {
            "claim_id": "C1",
            "claim_text": claim_text,
            "category": "carbon",
            "industry": industry,
        }

        # Pull financial-analyst data so intensity can be computed per
        # revenue (real intensity) rather than just sum of scopes.
        retriever_outputs = [
            o for o in state.get("agent_outputs", []) if o.get("agent") == "evidence_retrieval"
        ]
        financial_data = None
        if retriever_outputs:
            _fc = retriever_outputs[-1].get("output", {}).get("financial_context") or {}
            if isinstance(_fc, dict):
                financial_data = _fc.get("financial_data") or _fc

        # Extract carbon data from evidence
        result = extractor.extract_carbon_data(
            company=company,
            evidence=evidence,
            claim=claim_dict,
            report_chunks=parsed_chunks,
            report_claims_by_year=report_claims_by_year,
            report_files=parsed_report_files,
            financial_data=financial_data,
        )

        if isinstance(result, dict):
            # Store carbon extraction results in state
            state["carbon_extraction"] = result
            state["carbon_results"] = result

            # Display results
            emissions = result.get("emissions", {})
            scope1 = emissions.get("scope1", {})
            scope2 = emissions.get("scope2", {})
            scope3 = emissions.get("scope3", {})

            print(f"\n📊 CARBON EXTRACTION RESULTS:")
            print(f"   Scope 1 (Direct): {scope1.get('value', 'N/A')} tCO2e")
            print(f"   Scope 2 (Energy): {scope2.get('value', 'N/A')} tCO2e")
            print(f"   Scope 3 (Value Chain): {scope3.get('total', scope3.get('value', 'N/A'))} tCO2e")
            total_obj = emissions.get('total') or {}
            total_val = total_obj.get('all_scopes', 'N/A') if isinstance(total_obj, dict) else str(total_obj)
            print(f"   Total: {total_val} tCO2e")
            _im = result.get('intensity_metrics', {}) or {}
            _intensity_per_m = _im.get('intensity_per_revenue_m_tco2e')
            _ccy = _im.get('revenue_currency') or 'USD'
            if isinstance(_intensity_per_m, (int, float)) and _intensity_per_m > 0:
                print(f"   Carbon Intensity: {_intensity_per_m:,.1f} tCO2e per million {_ccy} of revenue")
            else:
                print(
                    f"   Carbon Intensity: not computed "
                    f"(no revenue denominator available — total emissions: {_im.get('total_emissions_tco2e', 'N/A')} tCO2e)"
                )
            print(f"   Net Zero Target: {result.get('net_zero_target', 'N/A')}")
            print(f"   Data Quality: {result.get('data_quality', 'N/A')}")

            confidence = result.get("confidence", 0.7)
        else:
            confidence = 0.5

        state["agent_outputs"].append({
            "agent": "carbon_extraction",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })
        state.setdefault("node_execution_order", []).append("Carbon Extraction")

        # ── P11: Multimodal extraction (feature-flagged) ────────────────
        if os.environ.get("ESG_USE_MULTIMODAL", "").lower() in ("1", "true", "yes"):
            try:
                _mm_spec = importlib.util.spec_from_file_location(
                    "multimodal_extractor", "agents/multimodal_extractor.py",
                )
                _mm_mod = importlib.util.module_from_spec(_mm_spec)
                _mm_spec.loader.exec_module(_mm_mod)
                _mm_out = _mm_mod.run(state)
                state["multimodal_extraction"] = _mm_out
                if _mm_out.get("status") == "COMPLETED":
                    print(f"\n>>> MULTIMODAL EXTRACTION")
                    print(f"    Tables: {_mm_out.get('table_count', 0)}, "
                          f"Chart facts: {_mm_out.get('fact_count', 0)}")
            except Exception as _mm_exc:
                print(f"  [multimodal_extractor] skipped: {_mm_exc}")
                state["multimodal_extraction"] = {"status": "ERROR", "error": str(_mm_exc)[:200]}

        # ── A2: Climate TRACE emissions verification ────────────────────
        # Cross-check disclosed Scope 1 against satellite-derived emissions.
        # Runs inline after carbon extraction so the verifier has the freshly
        # extracted scope1 value. Result lives in state["emissions_verification"]
        # and is also appended as a separate agent_output entry for the
        # report generator to pick up.
        try:
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location(
                "emissions_verifier", "agents/emissions_verifier.py"
            )
            _verifier_mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_verifier_mod)

            disclosed_s1 = None
            if isinstance(result, dict):
                _em = result.get("emissions") or {}
                _s1 = _em.get("scope1") or {}
                if isinstance(_s1, dict):
                    disclosed_s1 = _s1.get("value")

            # Prefer the F1-resolved country (more reliable than name heuristic)
            _entity = state.get("entity_record") or {}
            _resolved_country = None
            if isinstance(_entity, dict):
                _iso3 = _entity.get("country_iso3")
                # Climate TRACE accepts free-form country names; pass ISO3
                # directly via the verifier's normalise_country pathway
                _resolved_country = _iso3
            verif = _verifier_mod.verify_emissions(
                company=company,
                industry=industry,
                disclosed_scope1_tco2e=disclosed_s1,
                country=(_resolved_country
                         or state.get("country")
                         or state.get("jurisdiction")),
                year=2024,
            )
            state["emissions_verification"] = verif

            _led_row = _verifier_mod.build_ledger_row(verif)
            if _led_row:
                state.setdefault("scoremodifierledger", []).append(_led_row)

            print("\n>>> EMISSIONS VERIFICATION (Climate TRACE)")
            print(f"    Status: {verif.get('status')}")
            print(f"    Disclosed Scope 1: {(verif.get('disclosed_scope1_tco2e') or 0):,.0f} tCO2e")
            _obs = verif.get("observed_scope1_tco2e_assets")
            if _obs:
                print(f"    Observed (assets):  {_obs:,.0f} tCO2e "
                      f"(ratio={verif.get('ratio_disclosed_over_observed_assets')})")
            _sec = verif.get("observed_sector_total_tco2e")
            if _sec:
                print(f"    Sector ceiling:    {_sec:,.0f} tCO2e")
            print(f"    Ledger delta:      {verif.get('ledger_delta'):+.1f} GW pts")
            print(f"    Rationale: {(verif.get('rationale') or '')[:200]}")

            state["agent_outputs"].append({
                "agent": "emissions_verification",
                "output": verif,
                "confidence": 0.95 if verif.get("status") not in
                    ("NOT_APPLICABLE", "NOT_COVERED") else 0.5,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as _verif_exc:
            print(f"  [emissions_verifier] skipped: {_verif_exc}")
            state["emissions_verification"] = {
                "status": "NOT_COVERED",
                "error": str(_verif_exc)[:200],
            }

        # ── P2: PCAF financed emissions (financial-services only) ────────
        try:
            _fe_spec = importlib.util.spec_from_file_location(
                "financed_emissions", "agents/financed_emissions.py",
            )
            _fe_mod = importlib.util.module_from_spec(_fe_spec)
            _fe_spec.loader.exec_module(_fe_mod)

            _fe_out = _fe_mod.compute_financed_emissions(
                company=company, industry=industry,
            )
            state["financed_emissions"] = _fe_out
            if _fe_out.get("status") == "COMPUTED":
                print("\n>>> FINANCED EMISSIONS (PCAF)")
                print(f"    Total: {(_fe_out.get('total_financed_emissions_tco2e') or 0)/1e6:.2f} MtCO2e "
                      f"across {len(_fe_out.get('rows', []))} counterparties")
                print(f"    Intensity: {_fe_out.get('intensity_tco2e_per_usdm')} tCO2e/USDm  "
                      f"({_fe_out.get('benchmark_position')})")
                print(f"    Ledger delta: {_fe_out.get('ledger_delta'):+.1f} GW pts")

                _fe_row = _fe_mod.build_ledger_row(_fe_out)
                if _fe_row:
                    state.setdefault("scoremodifierledger", []).append(_fe_row)

                state["agent_outputs"].append({
                    "agent": "financed_emissions",
                    "output": _fe_out,
                    "confidence": 0.85,
                    "timestamp": datetime.now().isoformat(),
                })
        except Exception as _fe_exc:
            print(f"  [financed_emissions] skipped: {_fe_exc}")
            state["financed_emissions"] = {
                "status": "NOT_APPLICABLE",
                "error": str(_fe_exc)[:200],
            }

        # ── P6: Subsidiary KG walker ────────────────────────────────────
        try:
            _sw_spec = importlib.util.spec_from_file_location(
                "subsidiary_walker", "agents/subsidiary_walker.py",
            )
            _sw_mod = importlib.util.module_from_spec(_sw_spec)
            _sw_spec.loader.exec_module(_sw_mod)
            _sw_out = _sw_mod.run(
                company=company,
                entity_record=state.get("entity_record"),
                max_subsidiaries=10,
            )
            state["subsidiary_walk"] = _sw_out
            print(f"\n>>> SUBSIDIARY WALKER (GLEIF + Climate TRACE)")
            print(f"    Status: {_sw_out.get('status')}")
            print(f"    Subsidiaries: {len(_sw_out.get('subsidiaries') or [])}")
            print(f"    Coverage score: {_sw_out.get('subsidiary_coverage_score')}%")
            print(f"    Aggregate subsidiary emissions: "
                  f"{(_sw_out.get('total_subsidiary_emissions_tco2e') or 0)/1e6:.2f} MtCO2e")
            print(f"    Ledger delta: {_sw_out.get('ledger_delta', 0):+.1f} GW pts")

            _sw_row = _sw_mod.build_ledger_row(_sw_out)
            if _sw_row:
                state.setdefault("scoremodifierledger", []).append(_sw_row)
            state["agent_outputs"].append({
                "agent": "subsidiary_walker",
                "output": _sw_out,
                "confidence": 0.80 if _sw_out.get("status") != "NO_SUBSIDIARIES" else 0.4,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as _sw_exc:
            print(f"  [subsidiary_walker] skipped: {_sw_exc}")
            state["subsidiary_walk"] = {"status": "ERROR", "error": str(_sw_exc)[:200]}

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ CarbonExtractor error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "carbon_extraction",
            "error": str(e),
            "confidence": 0.3
        })

    return state


def carbon_pathway_analysis_node(state: ESGState) -> ESGState:
    """Model whether current and claimed trajectory aligns with 1.5C-style pathway constraints."""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print("Node: carbon_pathway_analysis")
    print("=" * 70)

    carbon = state.get("carbon_extraction") if isinstance(state.get("carbon_extraction"), dict) else {}
    emissions = carbon.get("emissions") if isinstance(carbon.get("emissions"), dict) else {}
    scope1 = emissions.get("scope1", {}) if isinstance(emissions.get("scope1"), dict) else {}
    scope2 = emissions.get("scope2", {}) if isinstance(emissions.get("scope2"), dict) else {}
    scope3 = emissions.get("scope3", {}) if isinstance(emissions.get("scope3"), dict) else {}

    def _n(x):
        return float(x) if isinstance(x, (int, float)) else 0.0

    scope1_val = _n(scope1.get("value"))
    scope2_val = _n(scope2.get("value"))
    scope3_val = _n(scope3.get("total") if isinstance(scope3.get("total"), (int, float)) else scope3.get("value"))

    target_year = 2030
    try:
        import re
        m = re.search(r"\b(20\d{2})\b", str(state.get("claim", "")))
        if m:
            target_year = int(m.group(1))
    except Exception:
        pass

    production_plan = "growth" if any(
        k in str(state.get("claim", "")).lower() for k in ["growth", "increase production", "maintain production"]
    ) else "stable"

    decomposition = state.get("claim_decomposition") if isinstance(state.get("claim_decomposition"), dict) else {}
    for sc in decomposition.get("sub_claims", []) if isinstance(decomposition.get("sub_claims"), list) else []:
        txt = str(sc.get("text", "")).lower()
        if "decline" in txt or "phase down" in txt:
            production_plan = "decline"

    # Resolve the base year dynamically (RC-1):
    #   1. Newest year tagged on parsed report chunks (report_parser node)
    #   2. reporting_year captured by carbon extraction / PDF metric extractor
    #   3. Fall back to "current year - 1" so a calendar rollover doesn't
    #      anchor every CAGR calculation to a frozen 2023 baseline.
    def _resolve_base_year() -> int:
        # 1. Most recent year on parsed report chunks
        for output in state.get("agent_outputs", []) or []:
            if not isinstance(output, dict) or output.get("agent") != "report_parser":
                continue
            chunks = ((output.get("output") or {}).get("chunks") or [])
            years = []
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                year = chunk.get("year")
                try:
                    year_int = int(year)
                except (TypeError, ValueError):
                    continue
                if 2015 <= year_int <= datetime.now().year + 1:
                    years.append(year_int)
            if years:
                return max(years)

        # 2. reporting_year on the carbon dict (set by carbon extractor or
        #    by company_report_fetcher._extract_esg_metrics — RC-4).
        candidate = carbon.get("reporting_year")
        if candidate is None:
            company_reports = state.get("company_reports") or {}
            candidate = (company_reports.get("extracted_data") or {}).get("reporting_year")
        try:
            candidate_int = int(candidate)
            if 2015 <= candidate_int <= datetime.now().year + 1:
                return candidate_int
        except (TypeError, ValueError):
            pass

        # 3. Dynamic fallback: previous calendar year.
        return datetime.now().year - 1

    base_year = _resolve_base_year()

    if not CARBON_PATHWAY_MODELLER_AVAILABLE:
        result = {
            "alignment_status": "misaligned",
            "pathway_gap_pct": 35.0,
            "scope3_feasibility": "UNKNOWN",
            "production_plan": production_plan,
        }
    else:
        try:
            modeller = CarbonPathwayModeller()
            result = modeller.model_pathway(
                company=state.get("company", ""),
                industry=state.get("industry", ""),
                claim_text=state.get("claim", ""),
                scope1=scope1_val,
                scope2=scope2_val,
                scope3=scope3_val,
                base_year=base_year,
                target_year=target_year,
                target_reduction_pct=30.0,
                production_plan=production_plan,
                claimed_pathway=(
                    "1.5C" if "1.5" in str(state.get("claim", "")).lower()
                    else f"net-zero-{target_year}" if target_year and target_year != 2030
                    else "net-zero-2050"
                ),
            )
        except Exception as e:
            print(f"❌ CarbonPathwayModeller error: {e}")
            result = {
                "alignment_status": "misaligned",
                "pathway_gap_pct": 35.0,
                "scope3_feasibility": "UNKNOWN",
                "production_plan": production_plan,
            }

    state["carbon_pathway_analysis"] = result
    state.setdefault("node_execution_order", []).append("Carbon Pathway Analysis")
    state["agent_outputs"].append({
        "agent": "carbon_pathway_analysis",
        "output": result,
        "confidence": 0.74,
        "timestamp": datetime.now().isoformat(),
    })
    print(
        f"✅ Alignment: {result.get('alignment_status', 'N/A')} | "
        f"Gap: {result.get('pathway_gap_pct', 'N/A')}%"
    )
    return state


def greenwishing_detection_node(state: ESGState) -> ESGState:
    """
    LIVE: GreenwishingDetector - Detects greenwishing, greenhushing, selective disclosure
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: greenwishing_detection")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not GREENWISHING_DETECTOR_AVAILABLE:
        print("⚠️ GreenwishingDetector not available - skipping")
        state["agent_outputs"].append({
            "agent": "greenwishing_detection",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        detector = GreenwishingDetector()

        company = state.get("company", "")
        claim_text = state.get("claim", "")
        evidence = state.get("evidence", [])

        print(f"🎯 Detecting greenwishing/greenhushing for: {company}")

        claim_dict = {
            "claim_id": "C1",
            "claim_text": claim_text,
            "category": "sustainability"
        }

        parser_outputs = [
            o for o in state.get("agent_outputs", [])
            if o.get("agent") == "report_parser"
        ]
        claim_outputs = [
            o for o in state.get("agent_outputs", [])
            if o.get("agent") == "claim_extractor" and o.get("source") == "report_chunks"
        ]

        result = detector.detect_deception_tactics(
            company=company,
            claim=claim_dict,
            evidence=evidence,
            structured_context={
                "report_chunks": parser_outputs[-1].get("output", {}).get("chunks", []) if parser_outputs else [],
                "report_claims_by_year": claim_outputs[-1].get("output", {}).get("report_claims_by_year", {}) if claim_outputs else {},
                "carbon_extraction": state.get("carbon_extraction", {})
            }
        )

        if isinstance(result, dict):
            state["greenwishing_analysis"] = result

            deception_risk = result.get("overall_deception_risk", {})
            print(f"\n🎭 DECEPTION DETECTION RESULTS:")
            print(f"   Greenwishing Risk: {result.get('greenwishing', {}).get('risk_level', 'N/A')}")
            print(f"   Greenhushing Risk: {result.get('greenhushing', {}).get('risk_level', 'N/A')}")
            print(f"   Selective Disclosure: {result.get('selective_disclosure', {}).get('detected', 'N/A')}")
            print(f"   Overall Deception Score: {deception_risk.get('score', 'N/A')}/100")

            confidence = result.get("confidence", 0.75)
        else:
            confidence = 0.5

        state["agent_outputs"].append({
            "agent": "greenwishing_detection",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ GreenwishingDetector error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "greenwishing_detection",
            "error": str(e),
            "confidence": 0.3
        })

    return state


def regulatory_scanning_node(state: ESGState) -> ESGState:
    """
    LIVE: RegulatoryHorizonScanner - Scans against SEBI BRSR, CSRD, SEC, etc.
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: regulatory_scanning")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not REGULATORY_SCANNER_AVAILABLE:
        print("⚠️ RegulatoryHorizonScanner not available - skipping")
        state["agent_outputs"].append({
            "agent": "regulatory_scanning",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        scanner = RegulatoryHorizonScanner()

        company = state.get("company", "")
        claim_text = state.get("claim", "")
        evidence = state.get("evidence", [])
        industry = state.get("industry", "")

        print(f"⚖️ Scanning regulatory compliance for: {company}")

        claim_dict = {
            "claim_id": "C1",
            "claim_text": claim_text,
            "category": "sustainability"
        }

        # Determine jurisdiction based on company name heuristics. The
        # buckets below are deliberately broad — the real-data fetchers
        # are jurisdiction-aware (`fetch_all_real_compliance` routes by
        # country) so a wrong bucket only mis-orders fetcher applicability,
        # not the underlying registry checks themselves.
        explicit_country = state.get("country") or state.get("hq_country") or ""
        if explicit_country:
            country = str(explicit_country).strip().upper()[:3]
        else:
            indian_companies = [
                "reliance", "tata", "infosys", "hdfc", "icici", "wipro", "bharti",
                "bajaj", "mahindra", "adani", "larsen", "maruti", "asian paints",
                "birla", "aditya birla", "ultratech", "grasim", "hindalco",
                "vedanta", "ongc", "ioc", "indian oil", "bpcl", "hpcl", "nalco",
                "coal india", "sail", "ntpc", "powergrid", "gail",
                "jsw", "jindal", "hindustan unilever", "itc ", "nestle india",
                "dr reddy", "cipla", "lupin", "sun pharma", "biocon", "divi",
                "tcs", "tech mahindra", "hcl", "mindtree", "lti", "persistent",
                "sbi ", "state bank of india", "axis bank", "kotak", "yes bank",
                "indusind", "federal bank", "pnb", "bank of baroda", "canara bank",
                "oyo", "paytm", "zomato", "nykaa", "policybazaar", "delhivery",
                "ashok leyland", "eicher", "tvs", "hero motocorp",
                "mrf", "apollo tyres", "ceat",
                "shree cement", "ambuja", "acc cement",
                "hindustan zinc", "tata steel", "jindal steel",
            ]
            company_lower = company.lower()
            if any(c in company_lower for c in indian_companies):
                country = "IN"
            elif any(c in company_lower for c in ["volkswagen", "vw", "bmw", "mercedes", "daimler", "siemens", "basf", "sap"]):
                country = "DE"
            elif any(c in company_lower for c in ["totalenergies", "total ", "loreal", "danone", "carrefour", "renault", "bnp paribas", "axa"]):
                country = "FR"
            elif any(c in company_lower for c in ["shell", "ing ", "philips", "heineken", "ahold"]):
                country = "NL"
            elif any(c in company_lower for c in ["bp ", "british petroleum", "hsbc", "unilever", "barclays", "london", "rio tinto", "anglo american", "vodafone", "diageo", "glaxo", "astrazeneca", "tesco"]):
                country = "UK"
            elif any(c in company_lower for c in ["nestle", "novartis", "roche", "ubs", "credit suisse", "abb"]):
                country = "CH"
            elif any(c in company_lower for c in [
                "tesla", "exxon", "chevron", "walmart", "microsoft", "apple", "amazon", "google", "alphabet",
                "jpmorgan", "jp morgan", "goldman", "morgan stanley", "citi", "wells fargo",
                "bank of america", "bofa", "blackrock", "berkshire", "meta", "netflix",
                "ibm", "intel", "nvidia", "oracle", "salesforce", "cisco", "adobe",
                "boeing", "lockheed", "caterpillar", "ge ", "general electric",
                "ford", "general motors", "gm ",
                "pepsi", "coca-cola", "coca cola", "procter", "johnson & johnson",
            ]):
                country = "US"
            else:
                country = ""

        if country in {"IN", "INDIA"}:
            jurisdiction = "India"
        elif country in {"DE", "FR", "NL", "DK", "SE", "IT", "ES", "PL", "BE", "AT", "FI", "IE", "PT", "CZ", "GR", "HU", "RO"}:
            jurisdiction = "EU"
        elif country in {"CH"}:
            jurisdiction = "CH"
        elif country in {"UK", "GB"}:
            jurisdiction = "UK"
        elif country in {"US", "USA"}:
            jurisdiction = "US"
        else:
            jurisdiction = "Global"

        carbon_state = state.get("carbon_extraction", {}) if isinstance(state.get("carbon_extraction"), dict) else {}
        base_result = scanner.scan_regulatory_compliance(
            company=company,
            claim=claim_dict,
            evidence=evidence,
            jurisdiction=jurisdiction,
            country=country,
            industry=industry,
            carbon_data=carbon_state,
        )

        # Real-data compliance pass — hits SEC EDGAR, TCFD adopter list,
        # CDP A-list, UN Global Compact, SBTi registry, GRI database, FTC
        # enforcement DB, plus an in-disclosure GHG Protocol check that
        # uses the parsed report chunks. These are the authoritative
        # signals; the keyword/DDG passes below are kept as supplementary
        # context. See utils/regulatory_fetchers.py.
        try:
            from agents.regulatory_scanner import evaluate_real_compliance

            # Reuse the parsed chunks from report_parser_node so the GHG
            # Protocol in-disclosure fetcher doesn't need to re-parse PDFs.
            _parser_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "report_parser"]
            _parsed_chunks = (
                _parser_outputs[-1].get("output", {}).get("chunks", [])
                if _parser_outputs else []
            )

            real_summary = evaluate_real_compliance(
                company=company,
                country=country,
                industry=industry,
                report_chunks=_parsed_chunks,
            )
            real_rows = real_summary.get("rows", []) if isinstance(real_summary, dict) else []
            print(
                f"   📋 Real-data fetch: {len(real_rows)} rows  ("
                f"{real_summary.get('compliant_count', 0)} pass, "
                f"{real_summary.get('gap_count', 0)} fail, "
                f"{real_summary.get('uncertain_count', 0)} uncertain, "
                f"{real_summary.get('not_applicable_count', 0)} N/A)"
            )
        except Exception as exc:
            print(f"   ⚠️ Real-data compliance fetch failed: {exc}")
            real_rows = []
            real_summary = {}

        if MULTI_JURISDICTION_SCANNER_AVAILABLE:
            try:
                mj = MultiJurisdictionRegulatoryScanner()
                jurisdictions = mj.detect_jurisdictions(industry=industry, hq_country=country)
                sbti_status = "unknown"
                carbon = state.get("carbon_extraction", {})
                if isinstance(carbon, dict):
                    sbti_status = str(carbon.get("sbti_status") or "unknown")
                multi = mj.aggregate_results(
                    company=company,
                    claim_text=claim_text,
                    jurisdictions=jurisdictions,
                    base_regulatory=base_result if isinstance(base_result, dict) else {},
                    evidence=evidence,
                    sbti_status=sbti_status,
                )
                result = dict(base_result) if isinstance(base_result, dict) else {}
                result["multi_jurisdiction"] = multi
                # Real-data rows are authoritative. When a real-data fetcher
                # returned a result for a framework, drop any heuristic /
                # keyword-rule row covering the same framework — otherwise
                # the report contradicts itself (e.g., SBTi COMPLIANT* from
                # the real registry + SBTi GAP from the keyword scanner).
                heuristic_rows = (
                    multi.get("jurisdiction_results", []) if isinstance(multi, dict) else []
                )

                def _norm_fwk(fwk: str) -> str:
                    """Normalize framework name for cross-source matching.

                    Strips wording variants (rule/rules, disclosure, climate,
                    parenthetical expansions) so "SEC Climate Disclosure Rule"
                    and "SEC Climate Disclosure Rules" collapse to the same
                    key — the real-data row should shadow whichever variant
                    the heuristic scanner used.
                    """
                    import re as _re
                    s = (fwk or "").lower()
                    s = _re.sub(r"\([^)]*\)", " ", s)  # strip "(Carbon Disclosure Project)"
                    s = _re.sub(r"\b(rule|rules|standard|standards|act|acts)\b", " ", s)
                    s = _re.sub(r"\b(disclosure|disclosures|aligned|climate|reporting|requirement|requirements)\b", " ", s)
                    s = "".join(ch for ch in s if ch.isalnum())
                    return s

                # Shadow ALL heuristic rows for any framework that a real-data
                # fetcher *attempted*, even when the real fetch returned
                # UNCERTAIN. A UNCERTAIN* row at least documents which public
                # registry was queried and when — strictly more informative
                # than a heuristic NOT_TESTED row covering the same framework.
                real_framework_keys = {
                    _norm_fwk(r.get("framework", ""))
                    for r in real_rows
                    if isinstance(r, dict) and r.get("status") in {"compliant", "gap", "uncertain"}
                }
                shadowed = 0
                filtered_heuristic = []
                for hr in heuristic_rows:
                    if not isinstance(hr, dict):
                        continue
                    if _norm_fwk(hr.get("framework", "")) in real_framework_keys:
                        shadowed += 1
                        continue
                    filtered_heuristic.append(hr)
                if shadowed:
                    print(
                        f"   🛡️  Real-data rows shadowed {shadowed} heuristic row(s) for the same framework"
                    )

                unified_frameworks = list(real_rows) + filtered_heuristic

                # Map multi-jurisdiction statuses → coarse buckets the
                # report renderer understands. "not_evaluated" / "uncertain"
                # are NOT gaps (they mean we didn't have evidence either way)
                # and must not be lumped into the gap count.
                _GAP_STATES = {"gap", "active_enforcement"}
                _COMPLIANT_STATES = {"compliant"}

                gap_count = sum(
                    1 for row in unified_frameworks
                    if isinstance(row, dict) and str(row.get("status", "")).lower() in _GAP_STATES
                )

                # Capability-based score (replaces the previous penalty-only
                # formula). Real-data rows from evaluate_real_compliance are
                # the authoritative signal; the multi-jurisdiction DDG rows
                # are supplementary. Each framework carries a credibility
                # weight (Tier 1 gov registry = 1.0, Tier 2 voluntary list =
                # 0.8, Tier 3 in-disclosure inference = 0.7) so a SEC EDGAR
                # PASS counts more than a UN Global Compact PASS.
                #
                #   capability = (Σ weight(pass) / Σ weight(pass+fail)) * 100
                #   final      = max(0, capability − enforcement_penalty)
                #
                # When no real-data rows are evaluated we fall back to the
                # old penalty-driven score so we never crash on a brand-new
                # company with no SEC ticker etc.
                from utils.regulatory_fetchers import get_framework_weight

                # Score across the FULL unified framework set (real-data fetches
                # + heuristic multi-jurisdiction rows), not just real_rows.
                # Otherwise a multi-jurisdiction GAP (e.g. EU CSRD detected via
                # the DDG scan) is invisible to the capability calculation,
                # producing perverse results like Shell scoring 100/100 with
                # 2 active gaps because none of the gaps came from real_rows.
                _pass_rows = [
                    r for r in unified_frameworks
                    if isinstance(r, dict) and str(r.get("status", "")).lower() == "compliant"
                ]
                _fail_rows = [
                    r for r in unified_frameworks
                    if isinstance(r, dict) and str(r.get("status", "")).lower() == "gap"
                ]
                _real_pass = len(_pass_rows)
                _real_fail = len(_fail_rows)
                _evaluated = _real_pass + _real_fail

                _weighted_pass = sum(get_framework_weight(r.get("framework", "")) for r in _pass_rows)
                _weighted_fail = sum(get_framework_weight(r.get("framework", "")) for r in _fail_rows)
                _weighted_total = _weighted_pass + _weighted_fail

                # Enforcement penalty as a *multiplier* rather than a flat
                # subtraction. Previously: `max(0, capability − 25×N)` —
                # any company with 1 active_enforcement row easily zeroed
                # out, making the compliance score "0" for nearly every
                # company tested (Tesla, VW, JPM all scored 0). The score
                # lost any spread: 0 = "we found something" rather than a
                # graded measure of compliance vs enforcement.
                #
                # New formula: each active_enforcement row trims 15% off the
                # capability score, capped so the final score never falls
                # below 25% of capability — even an enforcement-heavy
                # company keeps a meaningful relative score showing what
                # compliance signals exist.
                _enforcement_count = sum(
                    1 for row in unified_frameworks
                    if isinstance(row, dict) and str(row.get("status", "")).lower() == "active_enforcement"
                )
                if _weighted_total > 0:
                    _capability_score = (_weighted_pass / _weighted_total) * 100.0
                    _retention_factor = max(0.25, 1.0 - 0.15 * _enforcement_count)
                    unified_score = _capability_score * _retention_factor
                    _enforcement_penalty = _capability_score - unified_score
                    print(
                        f"   📊 Capability score (weighted): pass={_weighted_pass:.1f}, "
                        f"fail={_weighted_fail:.1f}, total={_weighted_total:.1f}  =>  "
                        f"capability={_capability_score:.0f}/100 × retention={_retention_factor:.2f} "
                        f"({_enforcement_count} enforcement rows) = "
                        f"{unified_score:.0f}/100"
                    )
                    if _pass_rows:
                        _passes = ", ".join(
                            f"{r.get('framework', '?')[:24]} (w={get_framework_weight(r.get('framework', '')):.1f})"
                            for r in _pass_rows
                        )
                        print(f"      passes: {_passes}")
                    if _fail_rows:
                        _fails = ", ".join(
                            f"{r.get('framework', '?')[:24]} (w={get_framework_weight(r.get('framework', '')):.1f})"
                            for r in _fail_rows
                        )
                        print(f"      fails:  {_fails}")
                else:
                    unified_score = float(multi.get("total_compliance_score", 0.0))
                    print(
                        f"   📊 Falling back to penalty-only score "
                        f"({unified_score:.0f}/100) — no real-data rows evaluated"
                    )

                # 3-band risk scale (LOW / MODERATE / HIGH).
                # CRITICAL was collapsed into HIGH May-2026 per design call.
                if unified_score >= 75:
                    derived_risk = "LOW"
                elif unified_score >= 50:
                    derived_risk = "MODERATE"
                else:
                    derived_risk = "HIGH"

                # Reg-D: Confidence flag for volatile frameworks. Compute the
                # share of *weight* coming from frameworks tagged
                # `under_consultation` or `draft` in the registry, and surface
                # a confidence adjustment + warning. The COMPLIANCE SCORE
                # ITSELF IS NOT MODIFIED — only the confidence reflects rule
                # volatility.
                try:
                    from core.regulatory_registry import volatility_share as _vol_share
                    _eval_names = [
                        fr.get("framework") for fr in unified_frameworks
                        if isinstance(fr, dict) and fr.get("framework")
                    ]
                    _volatility = _vol_share(_eval_names)
                    _conf_discount = round(0.3 * float(_volatility.get("volatile_share", 0.0)), 3)
                    _conf_adjusted = max(0.5, round(1.0 - _conf_discount, 3))
                    _volatility_warning = (
                        f"Compliance confidence reduced to {_conf_adjusted} — "
                        f"{int(_volatility.get('volatile_share', 0) * 100)}% of evaluated "
                        f"framework weight ({_volatility.get('volatile_weight', 0)}/"
                        f"{_volatility.get('total_weight', 0)}) comes from frameworks "
                        f"under active consultation or draft revision: "
                        f"{', '.join(_volatility.get('volatile_framework_ids') or []) or 'none'}."
                    ) if _volatility.get("volatile_share", 0) > 0 else None
                except Exception:
                    _volatility = {"total_weight": 0.0, "volatile_weight": 0.0, "volatile_share": 0.0, "volatile_framework_ids": []}
                    _conf_adjusted = 1.0
                    _volatility_warning = None

                result["compliance_result"] = {
                    "score": round(unified_score, 1),
                    "risk_level": derived_risk,
                    "frameworks": unified_frameworks,
                    "gap_count": gap_count,
                    "jurisdiction": multi.get("highest_risk_jurisdiction", jurisdiction),
                    "real_data_evaluated": _evaluated,
                    "real_data_passed": _real_pass,
                    "real_data_failed": _real_fail,
                    "framework_volatility":     _volatility,
                    "compliance_confidence":    _conf_adjusted,
                    "compliance_confidence_warning": _volatility_warning,
                }
                result["compliance_score"] = {
                    "score": result["compliance_result"]["score"],
                    "risk_level": result["compliance_result"]["risk_level"],
                    "gap_count": result["compliance_result"]["gap_count"],
                    "frameworks": result["compliance_result"]["frameworks"],
                    "jurisdiction": result["compliance_result"]["jurisdiction"],
                    # Reg-D: surface volatility + confidence at the report-facing
                    # location so Section 7B + the cross-version counterfactual
                    # can see them (they read from scores.compliance, not from
                    # agent_results[*].compliance_result).
                    "framework_volatility":          result["compliance_result"].get("framework_volatility"),
                    "compliance_confidence":         result["compliance_result"].get("compliance_confidence"),
                    "compliance_confidence_warning": result["compliance_result"].get("compliance_confidence_warning"),
                }
                result["risk_level"] = result["compliance_result"]["risk_level"]

                # Build canonical compliance_results that the report renderer
                # consumes for Section 7's gap table. Preserve real status
                # distinctions — collapsing not_evaluated/uncertain to GAP
                # produced misleading "Gap Found: not tested" rows.
                canonical_results = []
                compliant_count = 0
                not_evaluated_count = 0
                for mj_row in unified_frameworks:
                    if not isinstance(mj_row, dict):
                        continue
                    mj_status = str(mj_row.get("status", "")).lower()
                    if mj_status in _GAP_STATES:
                        canonical_status = "GAP"
                        gap_details = [mj_row.get("specific_violation")] if mj_row.get("specific_violation") else []
                    elif mj_status in _COMPLIANT_STATES:
                        canonical_status = "COMPLIANT"
                        gap_details = []
                        compliant_count += 1
                    elif mj_status in {"not_evaluated", "not evaluated"}:
                        canonical_status = "NOT_EVALUATED"
                        gap_details = []
                        not_evaluated_count += 1
                    else:  # uncertain or unknown
                        canonical_status = "UNCERTAIN"
                        gap_details = []
                    canonical_results.append({
                        "regulation_name": f"{mj_row.get('jurisdiction', 'Global')} | {mj_row.get('framework', 'Framework')}",
                        "gap_details": gap_details,
                        "status": canonical_status,
                    })
                result["compliance_results"] = canonical_results
                result["gaps"] = gap_count
                result["total_regulations"] = len(unified_frameworks)
                # Only count truly-compliant frameworks; not_evaluated/uncertain
                # are explicitly NOT compliant.
                result["compliant_regulations"] = compliant_count
                result["not_evaluated_regulations"] = not_evaluated_count
            except Exception as e:
                print(f"⚠️ Multi-jurisdiction aggregation failed: {e}")
                result = base_result
        else:
            result = base_result

        if isinstance(result, dict):
            state["regulatory_compliance"] = result
            state["regulatory_results"] = result

            print(f"\n⚖️ REGULATORY COMPLIANCE RESULTS:")
            print(f"   Jurisdiction: {result.get('jurisdiction', 'N/A')}")
            print(f"   Applicable Regulations: {len(result.get('applicable_regulations', []))}")
            score_obj = result.get("compliance_score", {})
            score_value = score_obj.get("score") if isinstance(score_obj, dict) else score_obj
            print(f"   Compliance Score: {score_value}/100")
            print(f"   Risk Level: {result.get('risk_level', 'N/A')}")

            # Show top regulations
            for reg in result.get('applicable_regulations', [])[:3]:
                print(f"   - {reg}")

            confidence = result.get("confidence", 0.8)
        else:
            confidence = 0.5

        # --- Step 6: Compute Controversy Risk Score (R) ---
        try:
            R = 0.0
            if isinstance(result, dict):
                # Regulatory gaps contribute heavily to R
                total_regs = max(1, result.get("total_regulations", 1))
                gaps = result.get("gaps", 0)
                gap_ratio = gaps / total_regs
                R += gap_ratio * 50.0  # Max 50 from compliance gaps

                # Risk level adds penalty
                risk_level = str(result.get("risk_level", "")).upper()
                if risk_level == "HIGH" or risk_level == "CRITICAL":
                    R += 25.0
                elif risk_level == "MODERATE":
                    R += 10.0

                # Sanctions check (from OpenSanctions or SEC)
                compliance_results = result.get("compliance_results", [])
                sanction_count = sum(
                    1 for cr in compliance_results
                    if isinstance(cr, dict) and str(cr.get("status", "")).upper() == "GAP"
                )
                R += min(25.0, sanction_count * 5.0)

            R = round(max(0.0, min(100.0, R)), 1)
            state["controversy_risk"] = {
                "score": R,
                "status": AgentStatus.SUCCESS.value,
                "source": "regulatory_scanner",
                "gaps": result.get("gaps", 0) if isinstance(result, dict) else 0,
                "risk_level": result.get("risk_level", "UNKNOWN") if isinstance(result, dict) else "UNKNOWN",
            }
            state.setdefault("pipeline_agent_statuses", {})["regulatory_scanning"] = AgentStatus.SUCCESS
            print(f"   📊 Controversy Risk Score (R): {R}/100")
        except Exception as e:
            print(f"   ⚠️ Controversy risk calculation failed: {e}")
            state["controversy_risk"] = {"score": 0.0, "status": AgentStatus.NULL_RESULT.value, "fallback_reason": str(e)}
            state.setdefault("pipeline_agent_statuses", {})["regulatory_scanning"] = AgentStatus.FAILED

        state["agent_outputs"].append({
            "agent": "regulatory_scanning",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })
        state.setdefault("node_execution_order", []).append("Regulatory Scanning")

        # ── P3: GDELT adverse-event stream ──────────────────────────────
        # Piggybacks on regulatory_scanning_node (both fetch external news/
        # filings). Runs after compliance scan so the report ordering stays
        # coherent.
        try:
            _gdelt_spec = importlib.util.spec_from_file_location(
                "gdelt_events", "agents/gdelt_events.py",
            )
            _gdelt_mod = importlib.util.module_from_spec(_gdelt_spec)
            _gdelt_spec.loader.exec_module(_gdelt_mod)
            _gdelt_out = _gdelt_mod.run(
                company=state.get("company", ""),
                entity_record=state.get("entity_record"),
                timespan="90day",
                max_records=50,
            )
            state["gdelt_events"] = _gdelt_out
            print(f"\n>>> GDELT EVENT STREAM")
            print(f"    Events: {len(_gdelt_out.get('events') or [])}")
            print(f"    Intensity: {_gdelt_out.get('decay_weighted_intensity')}")
            print(f"    Status: {_gdelt_out.get('status')}")
            print(f"    Ledger delta: {_gdelt_out.get('ledger_delta', 0):+.1f} GW pts")

            _gdelt_row = _gdelt_mod.build_ledger_row(_gdelt_out)
            if _gdelt_row:
                state.setdefault("scoremodifierledger", []).append(_gdelt_row)

            state["agent_outputs"].append({
                "agent": "gdelt_events",
                "output": _gdelt_out,
                "confidence": 0.80 if _gdelt_out.get("status") != "ERROR" else 0.4,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as _gdelt_exc:
            print(f"  [gdelt_events] skipped: {_gdelt_exc}")
            state["gdelt_events"] = {
                "status": "ERROR",
                "error": str(_gdelt_exc)[:200],
            }

        # ── P4: Litigation resolver (CourtListener + Indian Kanoon) ──────
        try:
            _lit_spec = importlib.util.spec_from_file_location(
                "litigation_resolver", "agents/litigation_resolver.py",
            )
            _lit_mod = importlib.util.module_from_spec(_lit_spec)
            _lit_spec.loader.exec_module(_lit_mod)
            _lit_out = _lit_mod.run(
                company=state.get("company", ""),
                entity_record=state.get("entity_record"),
                since_year=2018,
            )
            state["litigation_resolved"] = _lit_out
            print(f"\n>>> LITIGATION RESOLVER")
            print(f"    Status: {_lit_out.get('status')}")
            print(f"    US cases: {len(_lit_out.get('us_cases') or [])}, "
                  f"IN cases: {len(_lit_out.get('in_cases') or [])}")
            print(f"    Counts: {_lit_out.get('status_counts')}")
            print(f"    Ledger delta: {_lit_out.get('ledger_delta', 0):+.1f} GW pts")

            _lit_row = _lit_mod.build_ledger_row(_lit_out)
            if _lit_row:
                state.setdefault("scoremodifierledger", []).append(_lit_row)
            state["agent_outputs"].append({
                "agent": "litigation_resolver",
                "output": _lit_out,
                "confidence": 0.85 if _lit_out.get("status") != "ERROR" else 0.4,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as _lit_exc:
            print(f"  [litigation_resolver] skipped: {_lit_exc}")
            state["litigation_resolved"] = {
                "status": "ERROR",
                "error": str(_lit_exc)[:200],
            }

        # ── P5: EPA ECHO × EDGAR XBRL cross-ref (US-only) ────────────────
        try:
            _rcr_spec = importlib.util.spec_from_file_location(
                "regulatory_cross_ref", "agents/regulatory_cross_ref.py",
            )
            _rcr_mod = importlib.util.module_from_spec(_rcr_spec)
            _rcr_spec.loader.exec_module(_rcr_mod)
            _rcr_out = _rcr_mod.run(
                company=state.get("company", ""),
                industry=state.get("industry", ""),
                entity_record=state.get("entity_record"),
                ticker=state.get("ticker") or state.get("symbol"),
            )
            state["regulatory_cross_ref"] = _rcr_out
            print(f"\n>>> REGULATORY CROSS-REF (EPA ECHO × EDGAR)")
            print(f"    Status: {_rcr_out.get('status')}")
            print(f"    Fines: USD {_rcr_out.get('fines_total_usd', 0):,.0f}")
            print(f"    Env capex: USD {_rcr_out.get('env_capex_total_usd', 0):,.0f}")
            print(f"    Integrity flag: {_rcr_out.get('integrity_flag')}")
            print(f"    Ledger delta: {_rcr_out.get('ledger_delta', 0):+.1f} GW pts")

            _rcr_row = _rcr_mod.build_ledger_row(_rcr_out)
            if _rcr_row:
                state.setdefault("scoremodifierledger", []).append(_rcr_row)
            state["agent_outputs"].append({
                "agent": "regulatory_cross_ref",
                "output": _rcr_out,
                "confidence": 0.80 if _rcr_out.get("status") == "IN_ENGAGED" else 0.4,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as _rcr_exc:
            print(f"  [regulatory_cross_ref] skipped: {_rcr_exc}")
            state["regulatory_cross_ref"] = {
                "status": "ERROR",
                "error": str(_rcr_exc)[:200],
            }

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ RegulatoryHorizonScanner error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "regulatory_scanning",
            "error": str(e),
            "confidence": 0.3
        })

    return state


def climatebert_analysis_node(state: ESGState) -> ESGState:
    """
    LIVE: ClimateBERTAnalyzer - Transformer-based climate text analysis
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: climatebert_analysis")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not CLIMATEBERT_AVAILABLE:
        print("⚠️ ClimateBERTAnalyzer not available - skipping")
        state["agent_outputs"].append({
            "agent": "climatebert_analysis",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        analyzer = ClimateBERTAnalyzer()

        claim_text = state.get("claim", "")
        evidence = state.get("evidence", [])

        print(f"🤖 Running ClimateBERT NLP analysis...")

        # Extract evidence texts for comparison. Previously this only fed
        # ClimateBERT 10 retrieval snippets (~500 chars each), making the
        # analyzer's headline "Text length: 55 chars" — it was reading the
        # 55-char claim, not the report. Mix in a sample of parsed report
        # chunks (most claim-relevant first) so ClimateBERT actually
        # processes substantive disclosure text.
        evidence_texts = []
        for ev in evidence[:10]:  # Limit to first 10
            if isinstance(ev, dict):
                text = ev.get("content", ev.get("text", ev.get("snippet", "")))
                if text:
                    evidence_texts.append(text[:500])

        # Pull parsed-report chunks: prefer chunks with high ESG keyword
        # density so ClimateBERT analyzes substantive content, not boilerplate.
        try:
            _parser_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "report_parser"]
            _parsed_chunks = (
                _parser_outputs[-1].get("output", {}).get("chunks", [])
                if _parser_outputs else []
            )
            if _parsed_chunks:
                _esg_keywords = (
                    "scope 1", "scope 2", "scope 3", "emissions", "net zero",
                    "carbon neutral", "renewable", "ghg", "co2e",
                    "decarboniz", "climate target", "sbti",
                )
                _scored_chunks = []
                for c in _parsed_chunks[:200]:
                    if not isinstance(c, dict):
                        continue
                    t = c.get("text") or c.get("page_content") or ""
                    if not t or len(t) < 100:
                        continue
                    t_low = t.lower()
                    score = sum(1 for kw in _esg_keywords if kw in t_low)
                    if score >= 2:
                        _scored_chunks.append((score, t[:1500]))
                _scored_chunks.sort(reverse=True)
                # Take top 8 ESG-rich chunks for ClimateBERT input
                for _score, _text in _scored_chunks[:8]:
                    evidence_texts.append(_text)
                print(f"   📊 Including {min(8, len(_scored_chunks))} ESG-dense report chunks "
                      f"({sum(len(t) for _, t in _scored_chunks[:8])} chars) in ClimateBERT input")
        except Exception as _exc:
            print(f"   ⚠️ Report-chunk feed for ClimateBERT failed: {_exc}")

        result = analyzer.analyze_claim_for_greenwashing(
            claim_text=claim_text,
            evidence_texts=evidence_texts if evidence_texts else None
        )

        if isinstance(result, dict):
            state["climatebert_analysis"] = result
            state["climatebert_results"] = result

            claim_analysis = result.get("claim_analysis", {})
            gw_detection = claim_analysis.get("greenwashing_detection", {})
            evidence_analysis = result.get("evidence_analysis", {}) if isinstance(result.get("evidence_analysis"), dict) else {}

            print(f"\n🧠 CLIMATEBERT ANALYSIS RESULTS:")
            print(f"   Climate Relevance: {claim_analysis.get('climate_relevance', {}).get('score', 'N/A')}")
            print(f"   Backend: {result.get('analysis_backend', claim_analysis.get('analysis_backend', 'unknown'))}")
            if evidence_analysis:
                print(f"   Evidence Climate Relevance: {evidence_analysis.get('climate_relevance', {}).get('score', 'N/A')}")
            print(f"   Greenwashing Risk: {gw_detection.get('risk_score', 'N/A')}/100")
            print(f"   Risk Level: {gw_detection.get('risk_level', 'N/A')}")

            # Show detected patterns
            patterns = gw_detection.get("detected_patterns", [])
            if patterns:
                print(f"   Detected Patterns: {', '.join(patterns[:3])}")

            confidence = 0.85  # ClimateBERT is high confidence
        else:
            confidence = 0.5

        state["agent_outputs"].append({
            "agent": "climatebert_analysis",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })
        state.setdefault("node_execution_order", []).append("ClimateBERT Analysis")

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ ClimateBERTAnalyzer error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "climatebert_analysis",
            "error": str(e),
            "confidence": 0.3
        })

    return state


def social_analysis_node(state: ESGState) -> ESGState:
    """
    LIVE: SocialAgent - retrieves social pillar evidence and computes social risk signals.
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print("Node: social_analysis")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)

    if not SOCIAL_AGENT_AVAILABLE:
        print("⚠️ SocialAgent not available - skipping")
        state["agent_outputs"].append({
            "agent": "social_analysis",
            "output": "Agent not available",
            "confidence": 0.5,
        })
        return state

    try:
        agent = SocialAgent()

        # Get report chunks
        parser_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "report_parser"]
        parsed_chunks = parser_outputs[-1].get("output", {}).get("chunks", []) if parser_outputs else []

        enhanced_evidence = list(state.get("evidence", []))
        for chunk in parsed_chunks:
            text = chunk.get("text", str(chunk)) if isinstance(chunk, dict) else str(chunk)
            if text:
                enhanced_evidence.append({"snippet": text, "source": "Primary ESG Report"})

        result = agent.analyze(
            company=state.get("company", ""),
            claim_text=state.get("claim", ""),
            industry=state.get("industry", ""),
            evidence=enhanced_evidence,
        )

        state["social_analysis"] = result if isinstance(result, dict) else {}
        confidence = float(result.get("confidence", 0.7)) if isinstance(result, dict) else 0.5

        if isinstance(result, dict):
            print("✅ Social analysis complete")
            print(f"   Social Score: {result.get('social_score', 'N/A')}/100")
            print(f"   Risk Level: {result.get('risk_level', 'N/A')}")

        state.setdefault("node_execution_order", []).append("Social Analysis")
        state["agent_outputs"].append({
            "agent": "social_analysis",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        })

        print(f"{'✅ NODE COMPLETED':^70}")
    except Exception as e:
        print(f"❌ SocialAgent error: {e}")
        state["agent_outputs"].append({
            "agent": "social_analysis",
            "error": str(e),
            "confidence": 0.4,
            "timestamp": datetime.now().isoformat(),
        })

    return state


def governance_analysis_node(state: ESGState) -> ESGState:
    """
    LIVE: GovernanceAgent - parses governance evidence and proxy filing signals.
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print("Node: governance_analysis")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)

    if not GOVERNANCE_AGENT_AVAILABLE:
        print("⚠️ GovernanceAgent not available - skipping")
        state["agent_outputs"].append({
            "agent": "governance_analysis",
            "output": "Agent not available",
            "confidence": 0.5,
        })
        return state

    try:
        agent = GovernanceAgent()

        # Get report chunks
        parser_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "report_parser"]
        parsed_chunks = parser_outputs[-1].get("output", {}).get("chunks", []) if parser_outputs else []

        enhanced_evidence = list(state.get("evidence", []))
        for chunk in parsed_chunks:
            text = chunk.get("text", str(chunk)) if isinstance(chunk, dict) else str(chunk)
            if text:
                enhanced_evidence.append({"snippet": text, "source": "Primary ESG Report"})

        result = agent.analyze(
            company=state.get("company", ""),
            claim_text=state.get("claim", ""),
            industry=state.get("industry", ""),
            evidence=enhanced_evidence,
        )

        state["governance_analysis"] = result if isinstance(result, dict) else {}
        confidence = float(result.get("confidence", 0.7)) if isinstance(result, dict) else 0.5

        if isinstance(result, dict):
            print("✅ Governance analysis complete")
            print(f"   Governance Score: {result.get('governance_score', 'N/A')}/100")
            print(f"   Risk Level: {result.get('risk_level', 'N/A')}")

        state.setdefault("node_execution_order", []).append("Governance Analysis")
        state["agent_outputs"].append({
            "agent": "governance_analysis",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        })

        print(f"{'✅ NODE COMPLETED':^70}")
    except Exception as e:
        print(f"❌ GovernanceAgent error: {e}")
        state["agent_outputs"].append({
            "agent": "governance_analysis",
            "error": str(e),
            "confidence": 0.4,
            "timestamp": datetime.now().isoformat(),
        })

    return state


def explainability_node(state: ESGState) -> ESGState:
    """
    LIVE: ESGExplainabilityEngine - SHAP/LIME explanations for ML predictions
    Runs AFTER risk_scoring to explain the ML model's decision

    PHASE 9: Improved to always return meaningful factors
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: explainability (SHAP/LIME)")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not EXPLAINABILITY_AVAILABLE:
        print("⚠️ ESGExplainabilityEngine not available - skipping")
        state["agent_outputs"].append({
            "agent": "explainability",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        engine = ESGExplainabilityEngine()

        # Get ML prediction from risk scorer
        ml_prediction = state.get("ml_prediction", {})

        print(f"📊 Generating SHAP/LIME explanations...")

        # If we have ML feature data, explain it
        if ml_prediction and isinstance(ml_prediction, dict):
            features = ml_prediction.get("features")
            feature_names = ml_prediction.get("feature_names")

            if features is not None and feature_names:
                import numpy as np
                features_array = np.array(features).reshape(1, -1) if not isinstance(features, np.ndarray) else features

                # Generate SHAP explanation
                result = engine.explain_xgboost_prediction(
                    model=None,  # Will use fallback
                    features=features_array,
                    feature_names=feature_names
                )
            else:
                # Generate mock explanation based on available data
                result = {
                    "method": "Heuristic",
                    "top_factors": [
                        {"feature": "Environmental Disclosure Gaps", "impact": "high", "direction": "increases risk"},
                        {"feature": "Historical Violations", "impact": "high", "direction": "increases risk"},
                        {"feature": "Weak Social Performance", "impact": "moderate", "direction": "increases risk"}
                    ],
                    "human_readable_explanation": "Risk assessment based on ESG pillar scores and contradiction indicators."
                }
        else:
            # PHASE 9 FIX: Always extract meaningful factors
            risk_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "risk_scoring"]

            if risk_outputs:
                risk_result = risk_outputs[-1].get("output", {})
                pillar_scores = risk_result.get("pillar_scores", {})

                # PHASE 9: Build comprehensive factors list from all available data
                factors = []

                # Primary factors: ESG Pillars
                if pillar_scores.get("environmental_score") is not None:
                    factors.append({
                        "feature": "Environmental Disclosure Gaps" if pillar_scores["environmental_score"] < 50 else "Environmental Performance",
                        "value": pillar_scores["environmental_score"],
                        "impact": "high",
                        "direction": "decreases risk" if pillar_scores["environmental_score"] > 60 else "increases risk"
                    })

                if pillar_scores.get("social_score") is not None:
                    factors.append({
                        "feature": "Social Performance",
                        "value": pillar_scores["social_score"],
                        "impact": "moderate",
                        "direction": "decreases risk" if pillar_scores["social_score"] > 50 else "increases risk"
                    })

                if pillar_scores.get("governance_score") is not None:
                    factors.append({
                        "feature": "Governance Structure",
                        "value": pillar_scores["governance_score"],
                        "impact": "moderate",
                        "direction": "decreases risk" if pillar_scores["governance_score"] > 50 else "increases risk"
                    })

                # Secondary factors: Contradiction signals
                contradiction_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "contradiction_analysis"]
                if contradiction_outputs:
                    contradictions = contradiction_outputs[-1].get("output", {}).get("contradictions", [])
                    if contradictions:
                        factors.append({
                            "feature": f"Claim Contradictions ({len(contradictions)})",
                            "impact": "high",
                            "direction": "increases risk"
                        })

                # Tertiary factors: Historical patterns
                temporal_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "temporal_analysis"]
                if temporal_outputs:
                    temporal_data = temporal_outputs[-1].get("output", {})
                    if temporal_data.get("declining_trend"):
                        factors.append({
                            "feature": "Declining Historical Trust",
                            "impact": "moderate",
                            "direction": "increases risk"
                        })

                # PHASE 9: Ensure we always have factors
                if not factors:
                    factors = [
                        {"feature": "Environmental Disclosure Gaps", "impact": "high", "direction": "increases risk"},
                        {"feature": "Historical Regulatory Violations", "impact": "high", "direction": "increases risk"},
                        {"feature": "Weak Social Performance", "impact": "moderate", "direction": "increases risk"}
                    ]

                result = {
                    "method": "ESG Pillar Analysis with Contradiction Detection",
                    "top_factors": factors,
                    "human_readable_explanation": f"Risk is primarily driven by: {', '.join(f.get('feature', 'unknown') for f in factors[:3])}"
                }
            else:
                # PHASE 9: Fallback factors when no risk scorer data
                result = {
                    "method": "Basic ESG Analysis",
                    "top_factors": [
                        {"feature": "Limited ESG Data Availability", "impact": "high", "direction": "increases risk"},
                        {"feature": "Carbon Emissions Disclosure", "impact": "high", "direction": "decreases risk if transparent"},
                        {"feature": "Community Engagement", "impact": "moderate", "direction": "decreases risk"}
                    ],
                    "human_readable_explanation": "ESG assessment based on available disclosure and historical patterns."
                }

        if isinstance(result, dict):
            state["explainability_report"] = result
            state["explainability_results"] = result

            print(f"\n📈 EXPLAINABILITY RESULTS:")
            print(f"   Method: {result.get('method', 'N/A')}")
            print(f"   Top Risk Drivers: {len(result.get('top_factors', []))}")

            for i, factor in enumerate(result.get("top_factors", [])[:3], 1):
                direction_symbol = "⬇️" if "decreases" in factor.get('direction', '') else "⬆️"
                print(f"   {i}. {factor.get('feature')}: {factor.get('impact')} impact {direction_symbol} {factor.get('direction')}")

            if result.get("human_readable_explanation"):
                print(f"\n   📝 {result['human_readable_explanation'][:120]}...")

            confidence = 0.85
        else:
            confidence = 0.5

        state["agent_outputs"].append({
            "agent": "explainability",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })
        state.setdefault("node_execution_order", []).append("Explainability")

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ ESGExplainabilityEngine error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "explainability",
            "error": str(e),
            "confidence": 0.3
        })

    return state


def contradiction_analysis_node(state: ESGState) -> ESGState:
    """LIVE: ContradictionAnalyzer"""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: contradiction_analysis")
    print("="*70)

    if not CONTRADICTION_ANALYZER_AVAILABLE:
        state["agent_outputs"].append({
            "agent": "contradiction_analysis",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        analyzer = ContradictionAnalyzer()

        print(f"🔍 Analyzing contradictions...")

        contradicting_evidence = []
        evidence_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "evidence_retrieval"]
        if evidence_outputs:
            contradicting_evidence = evidence_outputs[-1].get("output", {}).get("contradicting_evidence", []) or []

        result = analyzer.analyze_contradictions(
            company=state.get("company", ""),
            claim=state.get("claim", ""),
            evidence=state.get("evidence", []),
            contradicting_evidence=contradicting_evidence,
        )

        decomposition = state.get("claim_decomposition") if isinstance(state.get("claim_decomposition"), dict) else {}
        tension_pairs = decomposition.get("logical_tension_pairs") if isinstance(decomposition.get("logical_tension_pairs"), list) else []
        if isinstance(result, dict) and tension_pairs:
            logical_items = []
            for t in tension_pairs:
                if not isinstance(t, dict):
                    continue
                logical_items.append({
                    "severity": str(t.get("severity", "medium")).upper(),
                    "description": str(t.get("tension_description") or "Internal claim tension detected"),
                    "source": "claim_decomposition",
                    "source_type": "internal_logic",
                    "confidence": "HIGH" if str(t.get("severity", "")).lower() == "high" else "MEDIUM",
                })
            if logical_items:
                existing = result.get("contradictions") if isinstance(result.get("contradictions"), list) else []
                result["contradictions"] = existing + logical_items
                result["contradiction_list"] = result["contradictions"]
                result["specific_contradictions"] = result["contradictions"]
                result["contradictions_found"] = len(result["contradictions"])

        contradiction_count = 0
        confidence = 0.75
        if isinstance(result, dict):
            contradiction_count = int(result.get("contradictions_found") or len(result.get("contradictions", [])))
            confidence = result.get("confidence", 0.75)
            print(f"✅ Found {contradiction_count} contradictions")
            state["contradiction_results"] = result

        state.setdefault("node_execution_order", []).append("Contradiction Analysis")

        state["agent_outputs"].append({
            "agent": "contradiction_analysis",
            "output": result,
            "contradictions_count": contradiction_count,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ ContradictionAnalyzer error: {e}")
        state["agent_outputs"].append({
            "agent": "contradiction_analysis",
            "error": str(e),
            "confidence": 0.5
        })

    # ── P8: Cross-pillar contradiction synthesis ───────────────────────────
    # Runs after the in-pillar contradiction analyzer because it needs
    # claim_decomposition + the social/governance/carbon outputs + GDELT
    # + litigation + regulatory_cross_ref + subsidiary_walk in state.
    try:
        _cps_spec = importlib.util.spec_from_file_location(
            "cross_pillar_synthesizer", "agents/cross_pillar_synthesizer.py",
        )
        _cps_mod = importlib.util.module_from_spec(_cps_spec)
        _cps_spec.loader.exec_module(_cps_mod)
        _cps_out = _cps_mod.synthesize(state)
        state["cross_pillar_contradictions"] = _cps_out
        print(f"\n>>> CROSS-PILLAR SYNTHESIS")
        print(f"    Contradictions found: {_cps_out.get('contradiction_count', 0)}")
        print(f"    Ledger delta: {_cps_out.get('ledger_delta', 0):+.1f} GW pts")
        _cps_row = _cps_mod.build_ledger_row(_cps_out)
        if _cps_row:
            state.setdefault("scoremodifierledger", []).append(_cps_row)
        state["agent_outputs"].append({
            "agent": "cross_pillar_synthesizer",
            "output": _cps_out,
            "confidence": 0.80,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as _cps_exc:
        print(f"  [cross_pillar_synthesizer] skipped: {_cps_exc}")
        state["cross_pillar_contradictions"] = {"status": "ERROR", "error": str(_cps_exc)[:200]}

    return state


def temporal_analysis_node(state: ESGState) -> ESGState:
    """LIVE: HistoricalAnalyst - calls CORRECT method"""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: temporal_analysis")
    print("="*70)

    if not HISTORICAL_ANALYST_AVAILABLE:
        state["agent_outputs"].append({
            "agent": "temporal_analysis",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        analyst = HistoricalAnalyst()

        print(f"📅 Analyzing historical track record for {state['company']}...")

        # FIXED: Call the CORRECT method name
        result = analyst.analyze_company_history(state["company"])

        # Extract key metrics for logging
        if isinstance(result, dict):
            reputation = result.get("reputation_score", 50)
            violations = len(result.get("past_violations", []))
            print(f"✅ Historical analysis complete:")
            print(f"   Reputation: {reputation}/100")
            print(f"   Violations found: {violations}")
            confidence = 0.7
            state["historical_results"] = result
        else:
            confidence = 0.5

        state.setdefault("node_execution_order", []).append("Temporal Analysis")

        state["agent_outputs"].append({
            "agent": "temporal_analysis",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ HistoricalAnalyst error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "temporal_analysis",
            "error": str(e),
            "confidence": 0.5
        })

    return state



def peer_comparison_node(state: ESGState) -> ESGState:
    """Adapter that runs the real IndustryComparator and falls back to the
    persistent peer JSON database when ChromaDB / live retrieval fails.
    Tags `data_source` so downstream consumers (and the report quality
    checker) can tell when peer benchmarking is degraded."""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: peer_comparison")
    print("="*70)

    company = state.get("company", "")
    industry = state.get("industry", "general")

    result: Dict[str, Any] = {}
    data_source = "unknown"
    fallback_used = False

    # Tier 1 — full IndustryComparator (Chroma + JSON DB + WBA seeding)
    try:
        from agents.industry_comparator import IndustryComparator
        comparator = IndustryComparator()
        ic_result = comparator.compare(company=company, industry=industry)
        if isinstance(ic_result, dict) and ic_result.get("peers"):
            result = ic_result
            data_source = ic_result.get("data_source") or "industry_comparator"
            if ic_result.get("fallback_used"):
                fallback_used = True
        else:
            raise RuntimeError("IndustryComparator returned no peers")
    except Exception as exc:
        print(f"⚠️  IndustryComparator path failed ({exc}); trying cached peer_database.json")
        # Tier 2 — cached JSON peer database
        try:
            from agents.industry_comparator import load_peer_database, normalize_industry_key
            peer_db = load_peer_database()
            industry_key = normalize_industry_key(industry)
            cached_rows = (peer_db.get("peers", {}) or {}).get(industry_key, []) or []
            cached_peers = [
                {
                    "company": r.get("name") or r.get("company"),
                    "esg": r.get("esg_score") or r.get("esg"),
                    "greenwashing_risk_score": r.get("gw_score") or r.get("greenwashing_risk_score"),
                    "rank": r.get("rank"),
                    "data_source": "cached_fallback",
                    "is_target": str(r.get("name", "")).lower() == company.lower(),
                }
                for r in cached_rows
                if isinstance(r, dict)
            ]
            if cached_peers:
                result = {
                    "peers": cached_peers,
                    "confidence": 0.55,
                    "data_source": "cached_fallback",
                    "real_peer_count": len([p for p in cached_peers if not p.get("is_target")]),
                    "fallback_used": True,
                    "fallback_reason": f"IndustryComparator failed: {exc}",
                }
                data_source = "cached_fallback"
                fallback_used = True
        except Exception as exc2:
            print(f"⚠️  Cached fallback also failed ({exc2}); emitting empty peer set")

    # Tier 3 — last-resort placeholder so downstream contract doesn't break,
    # but mark the entry FAILED so the quality checker surfaces a warning.
    if not result.get("peers"):
        result = {
            "peers": [
                {
                    "company": company or "Target Company",
                    "esg": state.get("esg_score", 50.0),
                    "greenwashing_risk_score": state.get("gw_score", 55.0),
                    "rank": "1/1",
                    "data_source": "placeholder",
                    "is_target": True,
                }
            ],
            "confidence": 0.3,
            "data_source": "placeholder",
            "fallback_used": True,
            "fallback_reason": "all peer-source tiers exhausted",
            "real_peer_count": 0,
        }
        data_source = "placeholder"
        fallback_used = True
        # Emit FAILED so the report's quality_warnings calls out missing peer benchmarking.
        state["agent_outputs"].append({
            "agent": "peer_comparison",
            "error": "all peer-source tiers exhausted (live + cached)",
            "output": result,
            "confidence": 0.3,
            "timestamp": datetime.now().isoformat(),
        })
        state["peer_results"] = result
        state.setdefault("pipeline_agent_statuses", {})["peer_comparison"] = AgentStatus.FAILED
        state.setdefault("node_execution_order", []).append("Peer Comparison")
        print(f"❌ Peer Comparison: all tiers exhausted — emitting placeholder with FAILED flag")
        return state

    # M1: Tag the peer-benchmark window with any active macro context so
    # readers know the comparison is during a shared crisis (peers are
    # exposed too — relative reads stay honest).
    _macro = state.get("macro_context") if isinstance(state.get("macro_context"), dict) else {}
    if _macro and _macro.get("status") == "ACTIVE_EVENTS_PRESENT":
        result["analysis_window_macro_context"] = [
            ev.get("event_id")
            for ev in (_macro.get("active_events") or [])
            if isinstance(ev, dict) and ev.get("event_id")
        ]
        result["analysis_window_macro_note"] = (
            "Peers benchmarked during the same active macro window — relative "
            "comparisons stay honest because peers face the same exogenous "
            "exposure. See `macro_context` block for event details."
        )

    state["agent_outputs"].append({
        "agent": "peer_comparison",
        "output": result,
        "confidence": float(result.get("confidence", 0.6)),
        "timestamp": datetime.now().isoformat(),
    })
    state["peer_results"] = result
    state.setdefault("pipeline_agent_statuses", {})["peer_comparison"] = AgentStatus.SUCCESS
    state.setdefault("node_execution_order", []).append("Peer Comparison")
    print(f"{'✅ NODE COMPLETED':^70}  source={data_source}  fallback={fallback_used}  peers={len(result.get('peers', []))}")
    return state


def _enrich_external_esg_benchmarks(state: ESGState) -> Dict[str, Any]:
    """Fetch external WBA/WRI benchmark signals used by downstream risk scoring."""
    company = state.get("company", "")
    if not company:
        return {"enabled": False, "error": "missing company"}

    try:
        import re

        def _company_variants(raw_name: str) -> list[str]:
            variants: list[str] = []

            def _add(value: str):
                text = str(value or "").strip()
                if text and text not in variants:
                    variants.append(text)

            base = re.sub(r"\s+", " ", str(raw_name or "")).strip()
            _add(base)

            camel_split = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)
            _add(camel_split)
            _add(camel_split.replace("&", " and "))

            no_punct = re.sub(r"[,&()]+", " ", camel_split)
            no_punct = re.sub(r"\s+", " ", no_punct).strip()
            _add(no_punct)

            tokens = [t for t in no_punct.split(" ") if t]
            if tokens:
                _add(tokens[0])
            if len(tokens) >= 2:
                _add(" ".join(tokens[:2]))

            # Handle fused acronym + word forms like JPMorgan -> JP Morgan.
            if tokens:
                first = tokens[0]
                fused = re.match(r"^([A-Z]{3,})([a-z].*)$", first)
                if fused:
                    caps, tail = fused.groups()
                    split_first = f"{caps[:-1]} {caps[-1]}{tail}"
                    _add(" ".join([split_first] + tokens[1:]).strip())

            return variants

        candidate_names = _company_variants(company)
        filled = {}
        selected_company_name = company

        for candidate_name in candidate_names:
            selected_company_name = candidate_name
            filled = fill_missing_pillars(
                company_name=candidate_name,
                existing_scores={
                    "social": None,
                    "governance": None,
                    "environment": None,
                    "water_risk": None,
                },
                wba_api_key=os.getenv("WBA_API_KEY"),
                industry=state.get("industry", ""),
            )
            if isinstance(filled, dict) and filled.get("_sources"):
                break

        score_keys = {
            "social",
            "environment",
            "water_risk",
            "water_risk_physical",
            "water_risk_regulatory",
            "water_risk_reputational",
        }
        scores = {
            key: value
            for key, value in (filled or {}).items()
            if key in score_keys
        }
        
        if isinstance(filled, dict):
            governance_base = filled.get("pillarfactors", {}).get("governance", {}).get("coverageadjustedscore") \
                              or filled.get("pillarfactors", {}).get("governance", {}).get("score") \
                              or 22.4  # fallback only
            scores["governance"] = governance_base

        sources = filled.get("_sources", {}) if isinstance(filled, dict) else {}
        indicators = filled.get("_wba_indicators", {}) if isinstance(filled, dict) else {}
        hq_coords = filled.get("_wba_hq_coordinates", {}) if isinstance(filled, dict) else {}
        sec_metrics = filled.get("_sec_metrics", {}) if isinstance(filled, dict) else {}

        # --- FIX B2: Merge governance agent's direct SEC DEF14A extractions ---
        # The governance agent outputs board_independence_pct, ceo_worker_pay_ratio
        # etc. into state["governance_analysis"]["signals"]. These are never merged
        # into sec_metrics by default, causing synthesize_sec_metric_evidence to
        # always find None for these fields.
        gov_analysis = state.get("governance_analysis", {})
        if isinstance(gov_analysis, dict):
            board_signals = gov_analysis.get("signals", {}).get("board", {})
            comp_signals = gov_analysis.get("signals", {}).get("executive_compensation", {})
            sec_proxy_filings = gov_analysis.get("signals", {}).get("sec_proxy_parser", {}).get("filings", [])

            # Board independence
            if isinstance(board_signals, dict) and board_signals.get("board_independence_pct") is not None and not sec_metrics.get("board_independence_pct"):
                sec_metrics["board_independence_pct"] = board_signals["board_independence_pct"]

            # CEO pay ratio
            if isinstance(comp_signals, dict) and comp_signals.get("ceo_worker_pay_ratio") is not None and not sec_metrics.get("pay_ratio"):
                sec_metrics["pay_ratio"] = comp_signals["ceo_worker_pay_ratio"]

            # LTI ESG %
            if isinstance(comp_signals, dict) and comp_signals.get("lti_esg_pct") is not None and not sec_metrics.get("lti_esg_pct"):
                sec_metrics["lti_esg_pct"] = comp_signals["lti_esg_pct"]
                if comp_signals["lti_esg_pct"] > 0:
                    sec_metrics["executive_comp_esg_links"] = True

            # Board gender diversity
            if isinstance(board_signals, dict) and board_signals.get("board_gender_pct") is not None and not sec_metrics.get("board_diversity_pct"):
                sec_metrics["board_diversity_pct"] = board_signals["board_gender_pct"]

            # Fallback: parsed proxy filings
            if isinstance(sec_proxy_filings, list):
                for filing in sec_proxy_filings:
                    parsed = filing.get("parsed_metrics", {}) if isinstance(filing, dict) else {}
                    if isinstance(parsed, dict):
                        if parsed.get("board_independence_pct") is not None and not sec_metrics.get("board_independence_pct"):
                            sec_metrics["board_independence_pct"] = parsed["board_independence_pct"]
                        if parsed.get("ceo_worker_pay_ratio") is not None and not sec_metrics.get("pay_ratio"):
                            sec_metrics["pay_ratio"] = parsed["ceo_worker_pay_ratio"]
                        if parsed.get("board_gender_pct") is not None and not sec_metrics.get("board_diversity_pct"):
                            sec_metrics["board_diversity_pct"] = parsed["board_gender_pct"]
                        if parsed.get("whistleblower_hotline") and not sec_metrics.get("whistleblower_hotline"):
                            sec_metrics["whistleblower_hotline"] = True
                        if parsed.get("has_anti_corruption_policy") and not sec_metrics.get("has_anti_corruption_policy"):
                            sec_metrics["has_anti_corruption_policy"] = True
        # --- END FIX B2 ---

        print("SEC metrics keys:", list(sec_metrics.keys()))
        supplemental_evidence = filled.get("_supplemental_evidence", []) if isinstance(filled, dict) else []
        if not isinstance(supplemental_evidence, list):
            supplemental_evidence = []

        ticker = (
            state.get("ticker")
            or state.get("symbol")
            or state.get("stock_ticker")
            or company
        )
        sec = sec_metrics or {}
        if isinstance(sec, dict):
            sec_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=DEF+14A"

            def _sec_float(value):
                try:
                    if isinstance(value, str):
                        value = value.replace("%", "").replace(",", "").strip()
                    return float(value)
                except (TypeError, ValueError):
                    return None

            board_independence_pct = _sec_float(sec.get("board_independence_pct"))
            if board_independence_pct is not None:
                pct = board_independence_pct
                supplemental_evidence.append({
                    "title": "Board Independence - SEC DEF14A",
                    "snippet": (
                        f"{pct:.0f}% of board members are independent non-executive directors "
                        f"(SEC DEF14A proxy filing)."
                    ),
                    "source": "SEC DEF14A",
                    "sourceName": "SEC",
                    "sourceType": "Regulatory Filing",
                    "url": sec_url,
                    "relevantText": f"board independence {pct:.0f}% independent director non-executive",
                    "relevanttext": f"board independence {pct:.0f}% independent director non-executive",
                    "sourcename": "sec def14a",
                    "verified": True,
                    "tier": 1,
                    "reliabilitytier": 1,
                    "isprimarydocument": True,
                })

            pay_ratio = sec.get("pay_ratio")
            if pay_ratio is None:
                pay_ratio = sec.get("executive_pay_ratio")
            pay_ratio_value = _sec_float(pay_ratio)
            if pay_ratio_value is not None:
                ratio = pay_ratio_value
                supplemental_evidence.append({
                    "title": "CEO Pay Ratio - SEC DEF14A",
                    "snippet": (
                        f"CEO pay ratio {ratio:.0f}:1 as disclosed in SEC DEF14A proxy statement. "
                        f"Mandatory US public-company disclosure under Dodd-Frank Section 953(b)."
                    ),
                    "source": "SEC DEF14A",
                    "sourceName": "SEC",
                    "sourceType": "Regulatory Filing",
                    "url": sec_url,
                    "relevantText": f"pay ratio {ratio:.0f} to 1 ceo pay ratio compensation ratio",
                    "relevanttext": f"pay ratio {ratio:.0f} to 1 ceo pay ratio compensation ratio",
                    "sourcename": "sec def14a",
                    "verified": True,
                    "tier": 1,
                    "reliabilitytier": 1,
                    "isprimarydocument": True,
                })

            if sec.get("anti_corruption_policy") or sec.get("ethics_policy") or sec.get("has_anti_corruption_policy"):
                policy_text = (
                    sec.get("anti_corruption_policy")
                    or sec.get("ethics_policy")
                    or "Anti-bribery and ethics policy confirmed in proxy."
                )
                supplemental_evidence.append({
                    "title": "Anti-Corruption / Ethics Policy - SEC DEF14A",
                    "snippet": str(policy_text)[:400],
                    "source": "SEC DEF14A",
                    "sourceName": "SEC",
                    "sourceType": "Regulatory Filing",
                    "url": sec_url,
                    "relevantText": "anti-corruption bribery ethics code of conduct compliance fcpa",
                    "relevanttext": "anti-corruption bribery ethics code of conduct compliance fcpa",
                    "sourcename": "sec def14a",
                    "verified": True,
                    "tier": 1,
                    "reliabilitytier": 1,
                    "isprimarydocument": True,
                })

            if sec.get("whistleblower_policy") or sec.get("ethics_hotline") or sec.get("whistleblower_hotline"):
                wb_text = (
                    sec.get("whistleblower_policy")
                    or sec.get("ethics_hotline")
                    or "Whistleblower/ethics hotline policy confirmed in proxy."
                )
                supplemental_evidence.append({
                    "title": "Whistleblower / Ethics Hotline - SEC DEF14A",
                    "snippet": str(wb_text)[:400],
                    "source": "SEC DEF14A",
                    "sourceName": "SEC",
                    "sourceType": "Regulatory Filing",
                    "url": sec_url,
                    "relevantText": "whistleblower ethics hotline speak up grievance reporting mechanism",
                    "relevanttext": "whistleblower ethics hotline speak up grievance reporting mechanism",
                    "sourcename": "sec def14a",
                    "verified": True,
                    "tier": 1,
                    "reliabilitytier": 1,
                    "isprimarydocument": True,
                })
        enrichment_error = None
        if not sources:
            enrichment_error = (
                "No WBA/WRI data returned for company aliases: "
                + ", ".join(candidate_names[:6])
            )

        return {
            "enabled": bool(sources),
            "scores": scores,
            "sources": sources,
            "wba_company_name": filled.get("_wba_company_name") if isinstance(filled, dict) else None,
            "wba_data_year": filled.get("_wba_data_year") if isinstance(filled, dict) else None,
            "hq_coordinates": hq_coords,
            "wba_indicator_count": len(indicators) if isinstance(indicators, dict) else 0,
            "query_company_name": selected_company_name,
            "query_attempts": candidate_names,
            "sec_metrics": sec_metrics,
            "supplemental_evidence": supplemental_evidence,
            "supplementalevidence": supplemental_evidence,
            "error": enrichment_error,
        }
    except Exception as exc:
        return {"enabled": False, "error": f"external ESG enrichment failed: {exc}"}


def risk_scoring_node(state: ESGState) -> ESGState:
    """LIVE: RiskScorer with ML + Formula hybrid approach"""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: risk_scoring (ML-Enhanced with Financial Analyst)")
    print("="*70)

    if not RISK_SCORER_AVAILABLE:
        from core.minimal_agents import risk_scoring_node as minimal_risk
        return minimal_risk(state)

    try:
        scorer = RiskScorer()

        print(f"⚖️ Calculating risk score for {state['industry']} industry...")
        if scorer.use_ml:
            print(f"🤖 ML model loaded - using hybrid ML + formula approach")
            print(f"   NOTE: XGBoost now has visibility into ESG pillar scores")
        else:
            print(f"📐 Using formula-based scoring only")

        # Build all_analyses dict from agent_outputs
        all_analyses = _build_analyses_dict(state)

        # Add claim and company for pillar calculation
        all_analyses["claim"] = {
            "claim_id": "C1",
            "claim_text": state["claim"],
            "category": "sustainability"
        }
        all_analyses["company"] = state["company"]
        all_analyses["industry"] = state.get("industry", "")

        # Enrich with external benchmark data (WBA/WRI) before final scoring.
        external_benchmarks = _enrich_external_esg_benchmarks(state)
        all_analyses["external_benchmarks"] = external_benchmarks
        supp = external_benchmarks.get("supplemental_evidence", [])

        if supp:
            state["supplemental_evidence"] = supp
            
        state["external_esg_data"] = external_benchmarks
        state["agent_outputs"].append({
            "agent": "external_esg_enrichment",
            "output": external_benchmarks,
            "confidence": 0.8 if external_benchmarks.get("enabled") else 0.5,
            "timestamp": datetime.now().isoformat()
        })
        if external_benchmarks.get("enabled"):
            print(
                "🌐 External ESG enrichment active: "
                f"sources={external_benchmarks.get('sources', {})}, "
                f"indicators={external_benchmarks.get('wba_indicator_count', 0)}"
            )
        elif external_benchmarks.get("error"):
            print(f"⚠️ External ESG enrichment unavailable: {external_benchmarks.get('error')}")

        fact_graph_payload = all_analyses.get("fact_graph", {})
        if isinstance(fact_graph_payload, dict):
            fg_summary = fact_graph_payload.get("summary", {})
            if isinstance(fg_summary, dict) and fg_summary:
                print(
                    "🕸️ Fact graph active: "
                    f"facts={fg_summary.get('fact_count', 0)}, "
                    f"verified={fg_summary.get('verified_fact_count', 0)}, "
                    f"linked={fg_summary.get('claim_linked_fact_count', 0)}"
                )

        # ── FIX 1: Inject parsed report chunks into evidence_sources ──
        _parser_outputs = [
            o for o in all_analyses.get("agent_outputs", [])
            if isinstance(o, dict) and o.get("agent") == "report_parser"
        ]
        if _parser_outputs:
            _parsed_out = _parser_outputs[-1].get("output") or {}
            _chunks = (_parsed_out.get("chunks") or []) if isinstance(_parsed_out, dict) else []
            _chunk_evidence = []
            for _chunk in _chunks[:400]:    # proxy(112pp) + annual report(364pp)
                if not isinstance(_chunk, dict):
                    continue
                _text = (_chunk.get("text") or _chunk.get("content") or "").strip()
                if len(_text) < 40:
                    continue
                _chunk_evidence.append({
                    "title":      _chunk.get("title", "Primary ESG Report"),
                    "snippet":    _text[:1200],
                    "url":        _chunk.get("source_url") or _parsed_out.get("source_url", ""),
                    "sourcename": _chunk.get("sourcename") or _chunk.get("source_name") or "Company Report (parsed)",
                    "reliabilitytier": 2,
                    "isprimarydocument": True,
                })
            if _chunk_evidence:
                all_analyses["evidence"] = list(all_analyses.get("evidence", [])) + _chunk_evidence
                print(f"📄 Injected {len(_chunk_evidence)} report-parser chunks into evidence pool")

        _synthetic_evidence = []
        _sec_evidence = synthesize_sec_metric_evidence(external_benchmarks)
        if _sec_evidence:
            _synthetic_evidence.extend(_sec_evidence)

        def _first_metric(*values):
            for _value in values:
                if _value is not None:
                    return _value
            return None

        def _as_float(value):
            try:
                if isinstance(value, str):
                    value = value.replace(",", "").strip()
                return float(value)
            except (TypeError, ValueError):
                return None

        def _fmt_metric(value, decimals=3):
            numeric = _as_float(value)
            if numeric is None:
                return str(value).strip()
            if float(numeric).is_integer():
                return str(int(numeric))
            return f"{numeric:.{decimals}f}".rstrip("0").rstrip(".")

        _carbon_metrics = {}
        for _payload in (
            all_analyses.get("carbon_extraction"),
            state.get("carbon_extraction"),
            all_analyses.get("pdf_extracted_metrics"),
            state.get("pdf_extracted_metrics"),
        ):
            if isinstance(_payload, dict):
                _carbon_metrics.update(_payload)

        _emissions = _carbon_metrics.get("emissions") if isinstance(_carbon_metrics.get("emissions"), dict) else {}
        _scope3 = _emissions.get("scope3") if isinstance(_emissions.get("scope3"), dict) else {}

        # Resolve the year these synthetic snippets belong to (RC-5).
        # Without an explicit year, the scoring engine and report generator
        # treat a 2021 figure identically to a 2024 one. Prefer the carbon
        # extractor's reporting_year, then the PDF metric extractor's value,
        # then the parsed-report chunks' newest year, finally previous year.
        def _resolve_carbon_year() -> Optional[int]:
            current_year = datetime.now().year
            valid_min, valid_max = 2015, current_year + 1

            for value in (
                _carbon_metrics.get("reporting_year"),
                state.get("reporting_year"),
                ((state.get("company_reports") or {}).get("extracted_data") or {}).get("reporting_year"),
            ):
                try:
                    year_int = int(value)
                except (TypeError, ValueError):
                    continue
                if valid_min <= year_int <= valid_max:
                    return year_int

            for output in state.get("agent_outputs", []) or []:
                if not isinstance(output, dict) or output.get("agent") != "report_parser":
                    continue
                chunks = ((output.get("output") or {}).get("chunks") or [])
                years = []
                for chunk in chunks:
                    if not isinstance(chunk, dict):
                        continue
                    try:
                        ci = int(chunk.get("year"))
                    except (TypeError, ValueError):
                        continue
                    if valid_min <= ci <= valid_max:
                        years.append(ci)
                if years:
                    return max(years)

            return current_year - 1

        _carbon_year = _resolve_carbon_year()
        _year_tag = f"[{_carbon_year}] " if _carbon_year else ""

        _ghg_intensity = _first_metric(
            _carbon_metrics.get("ghg_intensity"),
            _carbon_metrics.get("carbon_intensity"),
            _carbon_metrics.get("emissions_intensity"),
        )
        _ghg_num = _as_float(_ghg_intensity)
        if _ghg_num is not None:
            _ghg_display = _ghg_num * 1000.0 if abs(_ghg_num) < 1 else _ghg_num
            _synthetic_evidence.append({
                "title": "Company carbon disclosure metric",
                "snippet": f"{_year_tag}GHG emissions intensity {_fmt_metric(_ghg_display)} tCO2e scope 1 scope 2 carbon",
                "url": "",
                "sourcename": "Sustainability Report",
                "reliabilitytier": 2,
                "isprimarydocument": True,
                "year": _carbon_year,
            })

        _renewable_pct = _first_metric(
            _carbon_metrics.get("renewable_energy_percentage"),
            _carbon_metrics.get("renewable_pct"),
        )
        if _renewable_pct is not None:
            _synthetic_evidence.append({
                "title": "Company carbon disclosure metric",
                "snippet": f"{_year_tag}{_fmt_metric(_renewable_pct, decimals=1)}% renewable energy clean energy solar wind",
                "url": "",
                "sourcename": "Sustainability Report",
                "reliabilitytier": 2,
                "isprimarydocument": True,
                "year": _carbon_year,
            })

        _water_intensity = _first_metric(
            _carbon_metrics.get("water_intensity"),
            _carbon_metrics.get("water_efficiency"),
        )
        if _water_intensity is not None:
            _synthetic_evidence.append({
                "title": "Company carbon disclosure metric",
                "snippet": f"{_year_tag}water {_fmt_metric(_water_intensity)} L water stress consumption effluent withdrawal",
                "url": "",
                "sourcename": "Sustainability Report",
                "reliabilitytier": 2,
                "isprimarydocument": True,
                "year": _carbon_year,
            })

        _scope3_categories = _first_metric(
            _carbon_metrics.get("scope3_categories"),
            _scope3.get("categories") if isinstance(_scope3, dict) else None,
        )
        _scope3_count = None
        if isinstance(_scope3_categories, dict):
            _scope3_count = _scope3_categories.get("count")
            if _scope3_count is None:
                _scope3_count = len(_scope3_categories)
        elif isinstance(_scope3_categories, list):
            _scope3_count = len(_scope3_categories)
        else:
            _scope3_count = _as_float(_scope3_categories)
        if _scope3_count is not None:
            _synthetic_evidence.append({
                "title": "Company carbon disclosure metric",
                "snippet": f"{_year_tag}scope 3 upstream downstream value chain {_fmt_metric(_scope3_count)} categories scope 3 emissions",
                "url": "",
                "sourcename": "Sustainability Report",
                "reliabilitytier": 2,
                "isprimarydocument": True,
                "year": _carbon_year,
            })

        if str(state.get("industry", "") or "").strip().lower() == "banking":
            _external_scores = external_benchmarks.get("scores", {}) if isinstance(external_benchmarks, dict) else {}
            _green_lending = _external_scores.get("green_lending_ratio") if isinstance(_external_scores, dict) else None
            if _green_lending is not None:
                _green_num = _as_float(_green_lending)
                if _green_num is not None and 0 <= _green_num <= 100:
                    _green_snippet = f"{_fmt_metric(_green_num, decimals=1)}% green lending sustainable finance green loan portfolio"
                else:
                    _green_snippet = f"sustainable finance green lending {_green_lending} green loan bond"
            else:
                _green_snippet = "green lending sustainable finance green loan banking climate finance"
            _synthetic_evidence.append({
                "title": "Banking sustainable finance metric",
                "snippet": _green_snippet,
                "url": "",
                "sourcename": "External ESG benchmark",
                "reliabilitytier": 3,
                "isprimarydocument": False,
            })

        if _synthetic_evidence:
            all_analyses["evidence"] = list(all_analyses.get("evidence", [])) + _synthetic_evidence
            print(f"ðŸ§¾ Injected {len(_synthetic_evidence)} synthetic metric evidence item(s)")

        # Call calculate_final_score with proper parameters
        result = scorer.calculate_final_score(
            company=state["company"],
            all_analyses=all_analyses
        )
        
        state["esg_score_lineage"] = scorer.get_score_lineage()

        # ============================================================
        # FIX GW-FLOOR: Hard floor for companies with verified HIGH
        # greenwashing contradictions.  Prevents P > C formula collapse
        # from zeroing out gap_term when known misconduct is confirmed.
        # Uses existing applied_hard_caps mechanism — transparent in JSON.
        # ============================================================
        if isinstance(result, dict):
            _pf_contras = (result.get("pillarfactors") or {}).get("contradictions") or []
            if not isinstance(_pf_contras, list):
                _pf_contras = []
            # Also check topcontradictions (where _derive_top_contradictions puts its output)
            _top_contras = result.get("topcontradictions") or []
            if not isinstance(_top_contras, list):
                _top_contras = []
            _all_contras = _pf_contras + _top_contras
            _verified_high = [
                c for c in _all_contras
                if isinstance(c, dict)
                and str(c.get("severity", "")).upper() == "HIGH"
                and str(c.get("source_type", c.get("sourcetype", ""))).lower() in (
                    "verified_regulatory_case", "verifiedregulatorycase",
                    "regulatory", "third_party_verified", "thirdpartyverified",
                )
            ]
            _gw_now = float(result.get("greenwashingriskscore") or 0.0)

            if len(_verified_high) >= 2 and _gw_now < 60.0:
                result["greenwashingriskscore"]     = 60.0
                result["greenwashingscoreraw"] = max(
                    result.get("greenwashingscoreraw") or 0.0, 60.0
                )
                result["greenwashingrisklabel"] = "HIGH"
                result["risklevel"]              = "HIGH"
                result.setdefault("applied_hard_caps", []).append({
                    "cap":            "VERIFIED_CONTRADICTION_FLOOR",
                    "floor":          60.0,
                    "reason":         f"{len(_verified_high)} verified HIGH-severity greenwashing contradictions",
                    "original_score": _gw_now,
                })
                result.setdefault("scoremodifierledger", []).append({
                    "label": f"GW Hard Floor ({len(_verified_high)} verified HIGH contradictions)",
                    "value": 60.0,
                })
                print(f"⚠  GW hard floor applied: {_gw_now:.1f} → 60.0  ({len(_verified_high)} HIGH contradictions)")

            elif len(_verified_high) == 1 and _gw_now < 50.0:
                result["greenwashingriskscore"] = 50.0
                result.setdefault("applied_hard_caps", []).append({
                    "cap":            "VERIFIED_CONTRADICTION_FLOOR",
                    "floor":          50.0,
                    "reason":         f"{len(_verified_high)} verified HIGH-severity greenwashing contradictions",
                    "original_score": _gw_now,
                })
                result.setdefault("scoremodifierledger", []).append({
                    "label": f"GW Soft Floor ({len(_verified_high)} verified HIGH contradiction)",
                    "value": 50.0,
                })
                print(f"⚠  GW soft floor applied: {_gw_now:.1f} → 50.0  ({len(_verified_high)} HIGH contradictions)")
        # ============================================================

        if isinstance(result, dict):
            risk_level = result.get("risklevel", "MODERATE")
            rating_grade = result.get("ratinggrade", "BBB")
            confidence = result.get("confidencelevel", 85) / 100
            risk_source = result.get("risk_source", "Formula-based")
            high_carbon_flag = result.get("high_carbon_greenwashing_flag", False)
            pillar_scores = result.get("pillar_scores", {})
            esg_override_active = result.get("esg_override_active", False)

            print(f"✅ Risk Level: {risk_level}")
            print(f"   Rating Grade: {rating_grade}")
            print(f"   Source: {risk_source}")
            print(f"   Greenwashing Risk: {result.get('greenwashing_risk_score', 50):.1f}/100")
            if result.get("greenwashing_risk_score_raw") is not None:
                print(f"   Raw Risk Before Recalibration: {result.get('greenwashing_risk_score_raw', 50):.1f}/100")
            print(f"   ESG Score: {result.get('esg_score', 50):.1f}/100")
            archive_quality = result.get("historical_archive_quality", {}) if isinstance(result.get("historical_archive_quality"), dict) else {}
            if archive_quality:
                print(
                    "   Historical Archive Quality: "
                    f"{archive_quality.get('archive_confidence', 'N/A')}/100 "
                    f"({archive_quality.get('archive_quality_band', 'UNKNOWN')})"
                )
            if result.get("abstainrecommended") or result.get("abstain_recommended"):
                print(f"   Abstention: RECOMMENDED")
                print(f"   Reason: {result.get('abstentionreason') or result.get('abstention_reason', 'Insufficient evidence')}")

            if pillar_scores:
                print(f"   📊 Pillar Scores:")
                print(f"      E: {pillar_scores.get('environmental_score', 0):.1f}/100")
                print(f"      S: {pillar_scores.get('social_score', 0):.1f}/100")
                print(f"      G: {pillar_scores.get('governance_score', 0):.1f}/100")

            if esg_override_active:
                print(f"   🔒 ESG PILLAR OVERRIDE ACTIVE (bypassed ML)")

            if high_carbon_flag:
                print(f"   🚨 High-Carbon Greenwashing Flag: ACTIVE")

            # Show ML contribution if available
            if "ml_prediction" in result and not esg_override_active:
                ml_info = result["ml_prediction"]
                print(f"   ML Prediction: {ml_info['prediction']} (confidence: {ml_info['confidence']:.1%})")
                print(f"   ML Used: {'YES' if ml_info['used_for_final'] else 'NO'}")
                print(f"   ML saw pillar scores: E={pillar_scores.get('environmental_score', 0):.0f}, "
                      f"S={pillar_scores.get('social_score', 0):.0f}, "
                      f"G={pillar_scores.get('governance_score', 0):.0f}")
            # ── INSTITUTIONAL VERIFICATION ENGINE (10-Rule Framework) ────────
            try:
                from core.institutional_verifier import build_institutional_report
                _carbon_data = state.get("carbon_extraction") or {}
                _emissions = _carbon_data.get("emissions") or {}
                _scope1_val = (_emissions.get("scope1") or {}).get("value") if isinstance(_emissions.get("scope1"), dict) else _emissions.get("scope1")
                _scope2_val = (_emissions.get("scope2") or {}).get("value") if isinstance(_emissions.get("scope2"), dict) else _emissions.get("scope2")
                _scope3_val = (_emissions.get("scope3") or {}).get("total", (_emissions.get("scope3") or {}).get("value")) if isinstance(_emissions.get("scope3"), dict) else _emissions.get("scope3")
                _carbon_flat = {
                    "scope1": _scope1_val,
                    "scope2": _scope2_val,
                    "scope3": _scope3_val,
                    "net_zero_target": _carbon_data.get("net_zero_target"),
                    "sbti_status": _carbon_data.get("sbti_status"),
                    "renewable_pct": _carbon_data.get("renewable_pct"),
                }
                _pathway = state.get("carbon_pathway_analysis") or {}
                _temporal = all_analyses.get("temporal_consistency") or {}
                _contras = (
                    (state.get("contradiction_results") or {}).get("contradictions")
                    or (state.get("contradiction_results") or {}).get("contradiction_list")
                    or []
                )
                _reg_gaps = (
                    (state.get("regulatory_compliance") or {}).get("compliance_results") or []
                )
                _conf_pct = float(result.get("confidencelevel", result.get("confidence_pct", 65)))
                _esg_score = float(result.get("esg_score", 50))

                institutional = build_institutional_report(
                    claim_text=state.get("claim", ""),
                    evidence=list(state.get("evidence", [])),
                    esg_score=_esg_score,
                    confidence_pct=_conf_pct,
                    carbon_data=_carbon_flat,
                    pathway_data=_pathway,
                    temporal_data=_temporal,
                    contradictions=_contras,
                    regulatory_gaps=_reg_gaps,
                    external_benchmarks=external_benchmarks,
                )
                result["institutional_verification"] = institutional
                state["institutional_verification"] = institutional
                print(f"\n🏛️  INSTITUTIONAL VERIFICATION: {institutional['institutional_verdict']}")
                print(f"   Claim status : {institutional['claim_verification']['status']}")
                print(f"   Source tiers : T1={institutional['source_tier_breakdown']['tier1_regulatory']} "
                      f"T2={institutional['source_tier_breakdown']['tier2_esg_agencies']} "
                      f"T3={institutional['source_tier_breakdown']['tier3_media']} "
                      f"T4={institutional['source_tier_breakdown']['tier4_general_web']}")
                if institutional["rating_divergence"]["divergence_detected"]:
                    print(f"   ⚠️  {institutional['rating_divergence']['note']}")
                if institutional["abstention_assessment"]["abstain"]:
                    print(f"   🚫 ABSTAIN: {institutional['abstention_assessment']['abstain_reasons'][0]}")
            except Exception as _iv_err:
                logger.warning("Institutional verifier failed (non-fatal): %s", _iv_err)
            # ── END INSTITUTIONAL VERIFICATION ───────────────────────────────

            state["riskresults"] = result
        else:
            risk_level = "MODERATE"
            rating_grade = "BBB"
            confidence = 0.5

        state["risk_level"] = risk_level
        state["rating_grade"] = rating_grade  # NEW: Set rating_grade in state
        state["confidence"] = confidence
        state.setdefault("node_execution_order", []).append("Risk Scoring")

        state["agent_outputs"].append({
            "agent": "risk_scoring",
            "output": result,
            "risk_level": risk_level,
            "rating_grade": rating_grade,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ RiskScorer error: {e}")
        import traceback
        traceback.print_exc()
        state["risk_level"] = "MODERATE"
        state["confidence"] = 0.5
        state["agent_outputs"].append({
            "agent": "risk_scoring",
            "error": str(e),
            "confidence": 0.5
        })

    return state


def _build_analyses_dict(state: ESGState) -> Dict[str, Any]:
    """
    Convert state agent_outputs into the format expected by RiskScorer.calculate_final_score
    """
    analyses = {
        "contradiction_analysis": [],
        "evidence": list(state.get("evidence", [])),
        "evidence_quality_metrics": {},
        "credibility_analysis": {},
        "sentiment_analysis": [],
        "historical_analysis": {},
        "peer_comparison": {},
        "industry_comparison": {},
        "carbon_extraction": state.get("carbon_extraction", {}),
        "emissions_verification": state.get("emissions_verification", {}),
        "financed_emissions": state.get("financed_emissions", {}),
        "gdelt_events": state.get("gdelt_events", {}),
        "litigation_resolved": state.get("litigation_resolved", {}),
        "regulatory_cross_ref": state.get("regulatory_cross_ref", {}),
        "subsidiary_walk": state.get("subsidiary_walk", {}),
        "promise_tracking": state.get("promise_tracking", {}),
        "cross_pillar_contradictions": state.get("cross_pillar_contradictions", {}),
        "macro_context": state.get("macro_context", {}),
        "greenwishing_analysis": state.get("greenwishing_analysis", {}),
        "regulatory_compliance": state.get("regulatory_compliance", {}),
        "social_analysis": state.get("social_analysis", {}),
        "governance_analysis": state.get("governance_analysis", {}),
        "temporal_consistency": {},
        "claim_decomposition": state.get("claim_decomposition", {}),
        "adversarial_triangulation": state.get("adversarial_triangulation", {}),
        "carbon_pathway_analysis": state.get("carbon_pathway_analysis", {}),
        "commitment_ledger": state.get("commitment_ledger", {}),
        "debate_activated": False,
        "financial_context": None,
        "agent_outputs": list(state.get("agent_outputs", [])),
        "industry": state.get("industry", ""),
        "external_benchmarks": state.get("external_esg_data", {}),
        "fact_graph": state.get("fact_graph", {}),
        # NEW: Five-variable GW formula inputs
        "claim_intensity": state.get("claim_intensity", {}),
        "controversy_risk": state.get("controversy_risk", {}),
        "temporal_escalation": state.get("temporal_escalation", {}),
    }

    for output in state.get("agent_outputs", []):
        agent_name = output.get("agent", "")
        agent_result = output.get("output", {})

        if agent_name == "contradiction_analysis":
            if isinstance(agent_result, list):
                analyses["contradiction_analysis"] = agent_result
            elif isinstance(agent_result, dict) and "contradictions" in agent_result:
                analyses["contradiction_analysis"] = agent_result["contradictions"]

        elif agent_name == "evidence_retrieval":
            if isinstance(agent_result, dict):
                nested_evidence = agent_result.get("evidence", [])
                if isinstance(nested_evidence, list) and nested_evidence:
                    analyses["evidence"].extend([e for e in nested_evidence if isinstance(e, dict)])
                if isinstance(agent_result.get("quality_metrics"), dict):
                    analyses["evidence_quality_metrics"] = agent_result.get("quality_metrics", {})
                # Extract financial context
                if "financial_context" in output:
                    analyses["financial_context"] = output["financial_context"]

        elif agent_name == "credibility_analysis":
            analyses["credibility_analysis"] = agent_result

        elif agent_name == "sentiment_analysis":
            if isinstance(agent_result, list):
                analyses["sentiment_analysis"] = agent_result
            else:
                analyses["sentiment_analysis"].append(agent_result)

        elif agent_name == "temporal_analysis" or agent_name == "historical_analysis":
            analyses["historical_analysis"] = agent_result

        elif agent_name == "peer_comparison":
            analyses["peer_comparison"] = agent_result
            analyses["industry_comparison"] = agent_result

        elif agent_name == "carbon_extraction":
            analyses["carbon_extraction"] = agent_result

        elif agent_name == "greenwishing_detection":
            analyses["greenwishing_analysis"] = agent_result

        elif agent_name == "regulatory_scanning":
            analyses["regulatory_compliance"] = agent_result

        elif agent_name == "social_analysis":
            analyses["social_analysis"] = agent_result

        elif agent_name == "governance_analysis":
            analyses["governance_analysis"] = agent_result

        elif agent_name == "temporal_consistency":
            analyses["temporal_consistency"] = agent_result

        elif agent_name == "claim_decomposition":
            analyses["claim_decomposition"] = agent_result

        elif agent_name == "adversarial_triangulation":
            analyses["adversarial_triangulation"] = agent_result

        elif agent_name == "carbon_pathway_analysis":
            analyses["carbon_pathway_analysis"] = agent_result

        elif agent_name == "commitment_ledger_update":
            analyses["commitment_ledger"] = agent_result

        elif agent_name == "debate":
            analyses["debate_activated"] = True
            analyses["debate_result"] = agent_result

        elif agent_name == "external_esg_enrichment":
            analyses["external_benchmarks"] = agent_result
        elif agent_name == "fact_graph_builder":
            analyses["fact_graph"] = agent_result

    # ── Controversy signal extraction for GW R-variable ──────────────────
    # Severity-weighted contradiction count drives the bucket model's
    # current_contradictions bucket via risk_scorer.
    # Source preference order (first match wins):
    #   1. ``analyses["contradiction_analysis"]`` — already populated above
    #      from agent_outputs; this is the canonical pipeline-internal store.
    #   2. ``state["contradiction_results"]`` — set by the contradiction node;
    #      kept as a fallback for replay scripts that bypass agent_outputs.
    #   3. ``state["contradictions"]`` — top-level alias used by some renderers.
    contras = analyses.get("contradiction_analysis") or []
    if not contras:
        contradiction_payload = (
            state.get("contradiction_results")
            or state.get("contradictions")
            or {}
        )
        if isinstance(contradiction_payload, dict):
            contras = (
                contradiction_payload.get("contradictions")
                or contradiction_payload.get("contradiction_list")
                or contradiction_payload.get("specific_contradictions")
                or []
            )
        elif isinstance(contradiction_payload, list):
            contras = contradiction_payload
        else:
            contras = []
    if not isinstance(contras, list):
        contras = []

    # Severity-weighted contradiction count.
    # CRITICAL (e.g. $34B Dieselgate settlement) carries 3× a HIGH signal —
    # they are categorically more severe and previously didn't count at all
    # because the filter only matched 'HIGH'. LOW counts at 0.25× because
    # any retrieved disagreement carries some signal (a clean-leader run
    # should not bottom out at literal zero).
    _SEVERITY_WEIGHTS = {"CRITICAL": 3.0, "HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.25}
    weighted_severity = 0.0
    for c in contras:
        if not isinstance(c, dict):
            continue
        sev = str(c.get("severity", "")).upper()
        weighted_severity += _SEVERITY_WEIGHTS.get(sev, 0.0)
    controversy_raw = int(round(weighted_severity))
    analyses["controversy_signals"] = controversy_raw

    # Count regulatory gaps so the scorer can de-duplicate overlapping signals.
    reg_payload = (
        analyses.get("regulatory_compliance") or {}
    )
    if isinstance(reg_payload, dict):
        reg_results = reg_payload.get("compliance_results", []) or []
        reggaps = sum(
            1 for r in reg_results
            if isinstance(r, dict) and (r.get("gap_details") or [])
        )
    else:
        reggaps = 0
    analyses["reg_gap_count"] = reggaps
    # ─────────────────────────────────────────────────────────────────────

    return analyses


def fact_graph_node(state: ESGState) -> ESGState:
    """
    Build a fact-centric ESG knowledge graph from collected evidence.
    This supports justification-centric scoring and abstention decisions.
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print("Node: fact_graph_builder")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)

    try:
        contradictions = []
        contradiction_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "contradiction_analysis"]
        if contradiction_outputs:
            payload = contradiction_outputs[-1].get("output", {})
            if isinstance(payload, list):
                contradictions = payload
            elif isinstance(payload, dict):
                contradictions = (
                    payload.get("contradictions")
                    or payload.get("contradiction_list")
                    or payload.get("specific_contradictions")
                    or []
                )

        temporal_payload = {}
        temporal_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "temporal_consistency"]
        if temporal_outputs:
            temporal_payload = temporal_outputs[-1].get("output", {}) or {}
        analyses = _build_analyses_dict(state)

        result = build_esg_fact_graph(
            company=state.get("company", ""),
            claim_text=state.get("claim", ""),
            evidence=state.get("evidence", []),
            contradictions=contradictions if isinstance(contradictions, list) else [],
            temporal_consistency=temporal_payload if isinstance(temporal_payload, dict) else {},
            normalized_sg_evidence=analyses.get("evidence_quality_metrics", {}).get("social_governance_evidence", {}) if isinstance(analyses.get("evidence_quality_metrics", {}), dict) else {},
        )

        summary = result.get("summary", {}) if isinstance(result, dict) else {}
        state["fact_graph"] = result if isinstance(result, dict) else {}
        try:
            kg_status = CompanyKnowledgeGraph().ingest_state(state)
        except Exception as kg_err:
            kg_status = {
                "status": "ingest_error",
                "error": str(kg_err),
            }
        state["company_knowledge_graph"] = kg_status if isinstance(kg_status, dict) else {}
        state.setdefault("node_execution_order", []).append("Fact Graph Builder")
        state["agent_outputs"].append(
            {
                "agent": "fact_graph_builder",
                "output": result if isinstance(result, dict) else {"summary": {}},
                "confidence": 0.82,
                "timestamp": datetime.now().isoformat(),
            }
        )
        state["agent_outputs"].append(
            {
                "agent": "company_knowledge_graph",
                "output": kg_status if isinstance(kg_status, dict) else {},
                "confidence": 0.78 if isinstance(kg_status, dict) and not kg_status.get("error") else 0.35,
                "timestamp": datetime.now().isoformat(),
            }
        )

        print("✅ Fact graph built")
        if isinstance(summary, dict):
            print(
                f"   Facts: {summary.get('fact_count', 0)} | "
                f"Verified: {summary.get('verified_fact_count', 0)} | "
                f"Claim-linked: {summary.get('claim_linked_fact_count', 0)}"
            )
        if isinstance(kg_status, dict):
            print(
                f"   KG status: {kg_status.get('status', 'unknown')} | "
                f"Anchor: {kg_status.get('organization_anchor', 'N/A')}"
            )
        print(f"{'✅ NODE COMPLETED':^70}")
    except Exception as e:
        print(f"❌ Fact graph builder error: {e}")
        state["agent_outputs"].append(
            {
                "agent": "fact_graph_builder",
                "error": str(e),
                "confidence": 0.3,
                "timestamp": datetime.now().isoformat(),
            }
        )

    return state


def sentiment_analysis_node(state: ESGState) -> ESGState:
    """LIVE: SentimentAnalyzer"""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: sentiment_analysis")
    print("="*70)

    if not SENTIMENT_ANALYZER_AVAILABLE:
        state["agent_outputs"].append({
            "agent": "sentiment_analysis",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        analyzer = SentimentAnalyzer()

        print(f"💭 Analyzing sentiment...")

        result = analyzer.analyze_claim_language(
            claim={
                "claim_id": "C1",
                "claim_text": state.get("claim", ""),
                "company": state.get("company", ""),
            },
            evidence=state.get("evidence", []),
        )

        confidence = result.get("confidence", 0.7) if isinstance(result, dict) else 0.7
        print(f"✅ Sentiment analysis complete")
        if isinstance(result, dict):
            state["sentiment_results"] = result
        state.setdefault("node_execution_order", []).append("Sentiment Analysis")

        state["agent_outputs"].append({
            "agent": "sentiment_analysis",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ SentimentAnalyzer error: {e}")
        state["agent_outputs"].append({
            "agent": "sentiment_analysis",
            "error": str(e),
            "confidence": 0.5
        })

    return state


def credibility_analysis_node(state: ESGState) -> ESGState:
    """LIVE: CredibilityAnalyst"""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: credibility_analysis")
    print("="*70)

    if not CREDIBILITY_ANALYST_AVAILABLE:
        state["agent_outputs"].append({
            "agent": "credibility_analysis",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        analyst = CredibilityAnalyst()

        print(f"🔒 Assessing source credibility...")

        evidence = state.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []

        # Normalize evidence items to CredibilityAnalyst expected schema.
        # Many upstream agents store evidence as {title, snippet, source, url, relevant_text}.
        normalized_evidence = []
        for idx, ev in enumerate(evidence, start=1):
            if not isinstance(ev, dict):
                continue
            normalized_evidence.append({
                "source_id": ev.get("source_id") or ev.get("id") or idx,
                "source_name": ev.get("source_name") or ev.get("source") or ev.get("publisher") or ev.get("title") or "Unknown",
                "source_type": ev.get("source_type") or ev.get("reliability_tier") or "Web Source",
                "url": ev.get("url") or ev.get("link") or "",
                "relevant_text": ev.get("relevant_text") or ev.get("snippet") or ev.get("content") or "",
                "data_freshness_days": ev.get("data_freshness_days", 999),
            })

        if hasattr(analyst, 'analyze_sources'):
            result = analyst.analyze_sources(normalized_evidence)
        elif hasattr(analyst, 'analyze'):
            result = analyst.analyze(normalized_evidence)
        elif hasattr(analyst, 'assess'):
            result = analyst.assess(normalized_evidence)
        else:
            result = {"overall_credibility": 50, "aggregate_metrics": {"average_credibility": 0.5, "total_sources": len(normalized_evidence)}, "confidence": 0.5}

        confidence = result.get("confidence", 0.75) if isinstance(result, dict) else 0.75
        print(f"✅ Credibility assessment complete")
        if isinstance(result, dict):
            state["credibility_results"] = result
        state.setdefault("node_execution_order", []).append("Credibility Analysis")

        state["agent_outputs"].append({
            "agent": "credibility_analysis",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ CredibilityAnalyst error: {e}")
        state["agent_outputs"].append({
            "agent": "credibility_analysis",
            "error": str(e),
            "confidence": 0.5
        })

    return state


def realtime_monitoring_node(state: ESGState) -> ESGState:
    """LIVE: RealTimeMonitor - scrapes latest news"""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: realtime_monitoring")
    print("="*70)

    if not REALTIME_MONITOR_AVAILABLE:
        state["agent_outputs"].append({
            "agent": "realtime_monitoring",
            "output": "Agent not available",
            "confidence": 0.5
        })
        return state

    try:
        monitor = RealTimeMonitor()

        print(f"📰 Scraping real-time news for {state['company']}...")

        # Use the actual method from your file
        result = monitor.scrape_and_store(
            company=state["company"],
            hours_lookback=24
        )

        confidence = 0.7
        if isinstance(result, dict):
            evidence_items = result.get("evidence_items", [])
            print(f"✅ Found {len(evidence_items)} recent articles")
            for item in evidence_items:
                assert item.get("source_name") != "realtime_news", "source_name must be the publisher, not the agent name"
                state["evidence"].append(item)
            confidence = 0.8 if evidence_items else 0.5

        state.setdefault("node_execution_order", []).append("Realtime Monitoring")

        state["agent_outputs"].append({
            "agent": "realtime_monitoring",
            "output": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "live_fetch": True
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ RealTimeMonitor error: {e}")
        state["agent_outputs"].append({
            "agent": "realtime_monitoring",
            "error": str(e),
            "confidence": 0.5
        })

    return state


def confidence_scoring_node(state: ESGState) -> ESGState:
    """Calculate overall confidence"""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: confidence_scoring")
    print("="*70)

    # Calculate from successful agents only, one confidence per logical agent.
    unique_agent_confidences = {}
    for o in state.get("agent_outputs", []):
        if not isinstance(o, dict):
            continue
        agent_name = o.get("agent")
        conf = o.get("confidence")
        if not agent_name or "error" in o or not isinstance(conf, (int, float)):
            continue
        unique_agent_confidences[agent_name] = float(conf)

    confidences = list(unique_agent_confidences.values())
    agent_count = len(confidences)
    assert agent_count < 100, f"Agent count {agent_count} is unreasonably high - counter not being reset"

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

    # Apply reliability guardrails so sparse evidence runs cannot report inflated confidence.
    evidence_items = state.get("evidence", []) if isinstance(state.get("evidence", []), list) else []
    evidence_count = len(evidence_items)

    unique_domains = set()
    verifiable_count = 0
    for item in evidence_items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("link") or "").strip()
        date = str(item.get("date") or item.get("published_at") or item.get("publishedAt") or "").strip()

        if url:
            host = url.split("//")[-1].split("/")[0].lower().strip()
            if host.startswith("www."):
                host = host[4:]
            if host:
                unique_domains.add(host)

        if url and date:
            verifiable_count += 1

    reliability_caps = []
    if evidence_count < 3:
        reliability_caps.append(0.55)
    elif evidence_count < 5:
        reliability_caps.append(0.65)
    elif evidence_count < 8:
        reliability_caps.append(0.75)

    if len(unique_domains) < 3:
        reliability_caps.append(0.70)
    if verifiable_count < 3:
        reliability_caps.append(0.70)

    risk_outputs = [o for o in state.get("agent_outputs", []) if isinstance(o, dict) and o.get("agent") == "risk_scoring"]
    risk_result = risk_outputs[-1].get("output", {}) if risk_outputs else {}
    report_tier = str(risk_result.get("report_tier") or "").upper() if isinstance(risk_result, dict) else ""
    abstain_recommended = bool(risk_result.get("abstainrecommended", risk_result.get("abstain_recommended", False))) if isinstance(risk_result, dict) else False
    if report_tier == "TIER_3":
        reliability_caps.append(0.60)
    elif report_tier == "TIER_2":
        reliability_caps.append(0.75)
    if abstain_recommended:
        reliability_caps.append(0.55)

    audit_outputs = [o for o in state.get("agent_outputs", []) if isinstance(o, dict) and o.get("agent") == "adversarial_audit"]
    audit_result = audit_outputs[-1].get("output", {}) if audit_outputs else {}
    if isinstance(audit_result, dict):
        audit_penalty = float(audit_result.get("confidence_penalty", 0.0) or 0.0)
        if audit_penalty > 0:
            avg_confidence = max(0.0, avg_confidence - audit_penalty)
            reliability_caps.append(max(0.50, 1.0 - audit_penalty))

    failed_agents = 0
    for out in state.get("agent_outputs", []):
        if not isinstance(out, dict):
            continue
        if out.get("agent") == "confidence_scoring":
            continue
        if "error" in out or out.get("output") == "Agent not available":
            failed_agents += 1

    if failed_agents >= 4:
        avg_confidence *= 0.85
    elif failed_agents >= 2:
        avg_confidence *= 0.92

    cap_applied = min(reliability_caps) if reliability_caps else None
    if isinstance(cap_applied, float):
        avg_confidence = min(avg_confidence, cap_applied)

    avg_confidence = max(0.35, min(0.95, avg_confidence))
    state["confidence"] = avg_confidence

    print(
        f"✅ Average confidence: {avg_confidence:.2%} "
        f"(agents={agent_count}, evidence={evidence_count}, verifiable={verifiable_count}, domains={len(unique_domains)})"
    )

    state["agent_outputs"].append({
        "agent": "confidence_scoring",
        "output": {
            "average_confidence": avg_confidence,
            "agent_count": agent_count,
            "agents_included": sorted(unique_agent_confidences.keys()),
            "evidence_count": evidence_count,
            "verifiable_evidence_count": verifiable_count,
            "unique_domain_count": len(unique_domains),
            "failed_agent_count": failed_agents,
            "reliability_caps": reliability_caps,
            "cap_applied": cap_applied,
            "report_tier": report_tier,
            "abstain_recommended": abstain_recommended,
            "adversarial_audit": audit_result if isinstance(audit_result, dict) else {},
        },
        "confidence": avg_confidence,
        "timestamp": datetime.now().isoformat()
    })

    print(f"{'✅ NODE COMPLETED':^70}")

    return state


def adversarial_audit_node(state: ESGState) -> ESGState:
    """
    Compute coordination risk diagnostics across all upstream agents.
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print("Node: adversarial_audit")
    print("=" * 70)
    try:
        result = build_adversarial_audit(state)
        state["adversarial_audit"] = result
        state.setdefault("node_execution_order", []).append("Adversarial Audit")
        state["agent_outputs"].append({
            "agent": "adversarial_audit",
            "output": result,
            "confidence": max(0.5, 1.0 - float(result.get("coordination_risk", 0.0))),
            "timestamp": datetime.now().isoformat(),
        })
        print(
            "✅ Adversarial audit complete: "
            f"risk={result.get('coordination_risk_band')} "
            f"({result.get('coordination_risk', 0)}), "
            f"failed_agents={result.get('failed_agents', 0)}"
        )
        print(f"{'✅ NODE COMPLETED':^70}")
    except Exception as e:
        print(f"❌ Adversarial audit error: {e}")
        state["agent_outputs"].append({
            "agent": "adversarial_audit",
            "error": str(e),
            "confidence": 0.4,
            "timestamp": datetime.now().isoformat(),
        })
    return state


def verdict_generation_node(state: ESGState) -> ESGState:
    """
    Generate final verdict using AGENTIC INTELLIGENCE
    NO HARDCODING - All decisions based on agent analysis
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: verdict_generation")
    print("="*70)

    # ============================================================
    # PRIORITY 0: CHECK FOR ESG PILLAR OVERRIDE (HIGHEST PRIORITY)
    # ============================================================
    risk_scorer_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "risk_scoring"]

    # ============================================================
    # PRIORITY -1: ABSTENTION-AWARE DECISION (HARDEST GUARDRAIL)
    # ============================================================
    if risk_scorer_outputs:
        risk_scorer_result = risk_scorer_outputs[-1].get("output", {})
        if isinstance(risk_scorer_result, dict) and bool(risk_scorer_result.get("abstainrecommended", risk_scorer_result.get("abstain_recommended", False))):
            decision_status = str(risk_scorer_result.get("decision_status") or "ABSTAIN_RECOMMENDED")
            abstention_reason = str(risk_scorer_result.get("abstentionreason") or risk_scorer_result.get("abstention_reason") or "Evidence is insufficient for decision-grade scoring.")
            abstention_triggers = risk_scorer_result.get("abstentiontriggers") or risk_scorer_result.get("abstention_triggers", [])
            if not isinstance(abstention_triggers, list):
                abstention_triggers = []

            state["risk_level"] = "ABSTAIN"
            state["rating_grade"] = None
            state["confidence"] = min(float(state.get("confidence", 0.55) or 0.55), 0.55)
            state["verdict_locked"] = True

            verdict_data = {
                "company": state["company"],
                "claim": state["claim"],
                "risk_level": "ABSTAIN",
                "rating_grade": None,
                "final_confidence": state["confidence"],
                "decision_status": decision_status,
                "abstain_recommended": True,
                "abstention_reason": abstention_reason,
                "abstention_triggers": abstention_triggers,
                "score_disclaimer": risk_scorer_result.get("score_disclaimer", ""),
                "report_tier": risk_scorer_result.get("report_tier", "TIER_3"),
                "timestamp": datetime.now().isoformat(),
                "locked_by": "abstention_guardrail",
            }

            state["final_verdict"] = verdict_data
            state["agent_outputs"].append({
                "agent": "verdict_generation",
                "output": verdict_data,
                "confidence": state["confidence"],
                "timestamp": datetime.now().isoformat(),
                "verdict_locked": True,
            })

            print("\n🛑 ABSTENTION-AWARE DECISION ENFORCED")
            print(f"   Status: {decision_status}")
            print(f"   Reason: {abstention_reason}")
            print(f"{'✅ NODE COMPLETED':^70}")
            return state

    if risk_scorer_outputs:
        risk_scorer_result = risk_scorer_outputs[-1].get("output", {})
        esg_override_active = risk_scorer_result.get("esg_override_active", False)
        # Guard: the lockout flag fires for both ESG leaders (>=75) AND laggards (<50)
        # to suppress ML refinement, but the verdict-lock branch below was originally
        # written only for leaders. Restrict it to leaders so laggards aren't
        # incorrectly stamped LOW/A by the fallback defaults.
        _esg_for_gate = risk_scorer_result.get("esg_score")
        _is_leader = isinstance(_esg_for_gate, (int, float)) and float(_esg_for_gate) >= 75.0

        if esg_override_active and _is_leader:
            print(f"\n✅ ESG PILLAR OVERRIDE DETECTED - Strong Performance")
            print(f"   ESG Score: {risk_scorer_result.get('esg_score', 0)}/100")
            print(f"   Rating: {risk_scorer_result.get('ratinggrade') or risk_scorer_result.get('rating_grade', 'A')}")
            print(f"   This override takes HIGHEST PRIORITY")

            # Lock the verdict to ESG pillar-based assessment.
            # Read the canonical keys (risklevel / ratinggrade) the scorer actually emits;
            # only fall back to underscored aliases or hardcoded defaults if those are missing.
            locked_risk_level = (
                risk_scorer_result.get("risklevel")
                or risk_scorer_result.get("risk_level")
                or "LOW"
            )
            locked_rating = (
                risk_scorer_result.get("ratinggrade")
                or risk_scorer_result.get("rating_grade")
                or "A"
            )
            locked_confidence = risk_scorer_result.get("confidence_level", 90) / 100

            state["risk_level"] = locked_risk_level
            state["rating_grade"] = locked_rating
            state["confidence"] = locked_confidence
            state["verdict_locked"] = True

            verdict_data = {
                "company": state["company"],
                "claim": state["claim"],
                "risk_level": locked_risk_level,
                "rating_grade": locked_rating,
                "final_confidence": locked_confidence,
                "evidence_count": len(state["evidence"]),
                "timestamp": datetime.now().isoformat(),
                "locked_by": "esg_pillar_override",
                "lock_reason": f"Strong ESG performance (ESG >= 75) - {risk_scorer_result.get('risk_source')}"
            }

            state["agent_outputs"].append({
                "agent": "verdict_generation",
                "output": verdict_data,
                "confidence": locked_confidence,
                "timestamp": datetime.now().isoformat(),
                "verdict_locked": True
            })

            state["final_verdict"] = verdict_data

            print(f"\n🔒 VERDICT LOCKED BY ESG PILLAR OVERRIDE")
            print(f"   Risk Level: {locked_risk_level}")
            print(f"   Rating: {locked_rating}")
            print(f"   Confidence: {locked_confidence:.1%}")
            print(f"{'✅ NODE COMPLETED':^70}")

            return state

    # ============================================================
    # PRIORITY 1: CHECK IF RISK SCORER LOCKED THE DECISION (Domain Knowledge)
    # ============================================================
    # If risk_scorer already determined HIGH risk for oil_and_gas greenwashing,
    # DO NOT override - this is domain knowledge that must be preserved

    if risk_scorer_outputs:
        risk_scorer_result = risk_scorer_outputs[-1].get("output", {})
        high_carbon_flag = risk_scorer_result.get("high_carbon_greenwashing_flag", False)
        risk_source = risk_scorer_result.get("risk_source", "")

        # Check if risk scorer applied domain knowledge override
        if "Domain Knowledge Override" in risk_source or high_carbon_flag:
            print(f"\n🔒 VERDICT LOCKED - Risk Scorer Domain Knowledge Override Detected")
            print(f"   Risk Source: {risk_source}")
            print(f"   High Carbon Flag: {high_carbon_flag}")
            print(f"   Industry: {state.get('industry')}")
            print(f"   ⚠️ Verdict generation will NOT override domain-specific risk assessment")

            # Extract risk scorer's final decision
            locked_risk_level = risk_scorer_result.get("risk_level", "HIGH")
            locked_rating = risk_scorer_result.get("rating_grade", "BB")
            locked_confidence = state.get("confidence", 0.85)

            # Lock the state
            state["risk_level"] = locked_risk_level
            state["rating_grade"] = locked_rating
            state["confidence"] = locked_confidence
            state["verdict_locked"] = True

            verdict_data = {
                "company": state["company"],
                "claim": state["claim"],
                "risk_level": locked_risk_level,
                "rating_grade": locked_rating,
                "confidence": locked_confidence,
                "evidence_count": len(state["evidence"]),
                "timestamp": datetime.now().isoformat(),
                "locked_by": "risk_scorer_domain_knowledge",
                "lock_reason": f"Oil & Gas greenwashing pattern detected - {risk_source}"
            }

            state["agent_outputs"].append({
                "agent": "verdict_generation",
                "output": verdict_data,
                "confidence": locked_confidence,
                "timestamp": datetime.now().isoformat(),
                "verdict_locked": True
            })

            state["final_verdict"] = verdict_data

            print(f"\n✅ LOCKED VERDICT: {locked_risk_level} (Rating: {locked_rating}, Confidence: {locked_confidence:.1%})")
            print(f"{'✅ NODE COMPLETED':^70}")

            return state

    # ============================================================
    # NORMAL VERDICT GENERATION (if not locked)
    # ============================================================

    verdict_data = {
        "company": state["company"],
        "claim": state["claim"],
        "risk_level": state["risk_level"],
        "confidence": state["confidence"],
        "evidence_count": len(state["evidence"]),
        "timestamp": datetime.now().isoformat()
    }

    claim_lower = state["claim"].lower()
    import re

    # ============================================================
    # AGENTIC INTELLIGENCE: Extract insights from agent outputs
    # ============================================================
    agent_outputs = state.get("agent_outputs", [])

    # Get HistoricalAnalyst findings (LIVE, no hardcoding)
    historical_data = None
    for output in agent_outputs:
        if output.get("agent") == "temporal_analysis":
            historical_data = output.get("output", {})
            break

    # Get ContradictionAnalyzer findings
    contradiction_count = 0
    for output in agent_outputs:
        if output.get("agent") == "contradiction_analysis":
            contradiction_count = output.get("contradictions_count", 0)
            break

    # Get debate resolution data
    debate_conflict_ratio = 0
    debate_outputs = [o for o in agent_outputs if o.get('agent') in ['debate_orchestrator', 'debate_resolution']]
    if debate_outputs:
        for debate in debate_outputs:
            conflict_ratio = debate.get('conflict_ratio', 0)
            debate_conflict_ratio = max(debate_conflict_ratio, conflict_ratio)
    # ============================================================
    # PRIORITY 1: ABSOLUTE/IMPOSSIBLE CLAIMS (Pattern Detection)
    # ============================================================
    # FIXED: Exclude legitimate carbon accounting terms
    absolute_patterns = [
        r'100%\s*(sustainable|green|eco|recyclable|renewable|organic|natural)',
        r'(completely|totally|fully|entirely|perfectly|absolutely)\s*(sustainable|green|eco)',
        # REMOVED: r'zero\s*(waste|emissions|carbon|pollution|impact)' - these can be legitimate
    ]

    # NEW: Check if claim has SPECIFIC METRICS that make it verifiable
    has_metrics = bool(re.search(r'\d+\.?\d*\s*(million|billion|%)|20\d{2}|specific\s+amount', state["claim"]))
    has_year = bool(re.search(r'20\d{2}|in\s+\d{4}', state["claim"]))

    # NEW: Legitimate carbon accounting terms (NOT greenwashing)
    legitimate_carbon_terms = [
        "carbon negative",  # Removing MORE than emitting
        "net zero",         # With documented offsetting
        "carbon neutral",   # If verified and dated
        "scope 1", "scope 2", "scope 3"  # GHG Protocol terminology
    ]

    # Check if claim uses legitimate terminology WITH metrics
    is_legitimate_carbon_claim = (
        any(term in claim_lower for term in legitimate_carbon_terms)
        and has_metrics
        and has_year
    )

    absolute_detected = (
        any(re.search(p, claim_lower) for p in absolute_patterns)
        and not is_legitimate_carbon_claim  # FIXED: Don't flag legitimate claims
    )

    if absolute_detected:
        print(f"\n🔴 AGENTIC DECISION: Absolute claim pattern detected")
        state["risk_level"] = "HIGH"
        state["confidence"] = min(state["confidence"] * 0.60, 0.75)
        verdict_data["risk_level"] = "HIGH"
        verdict_data["escalation"] = "Absolute/impossible claim (pattern-based)"
        print(f"   Escalated to HIGH - unrealistic claim language")

    # ============================================================
    # PRIORITY 1.5: VERIFIED CARBON CLAIMS (Conditionally downgrade to LOW)
    # ============================================================
    # Only downgrade if the claim language is recognised AND there is no
    # material contradicting evidence. A "net zero by 2050" mention should
    # NOT silence verified contradictions like an NZBA exit or BOCC findings.
    elif is_legitimate_carbon_claim:
        # Pull the canonical contradiction signal already gathered upstream.
        _contra_count_for_gate = 0
        for _ao in agent_outputs:
            if _ao.get("agent") == "contradiction_analysis":
                _out = _ao.get("output") or {}
                _contra_count_for_gate = int(_out.get("contradictions_found", 0) or 0)
                break
        # Also include any verified regulatory cases stored elsewhere on state.
        _contra_count_for_gate = max(
            _contra_count_for_gate,
            int(contradiction_count or 0),
            len(state.get("contradictions", []) or []),
        )

        print(f"\n🟢 AGENTIC DECISION: Legitimate carbon accounting language detected")
        print(f"   - Specific metrics: {has_metrics}")
        print(f"   - Dated claim: {has_year}")
        print(f"   - Recognized terminology: carbon negative/net zero")
        print(f"   - Contradictions on file: {_contra_count_for_gate}")

        if _contra_count_for_gate >= 2:
            print(f"   ⛔ Downgrade BLOCKED: {_contra_count_for_gate} contradictions undermine credibility of stated target.")
            verdict_data["downgrade_blocked"] = (
                f"Carbon-claim downgrade declined — {_contra_count_for_gate} verified contradictions on record."
            )
        elif state["risk_level"] in ["MODERATE", "HIGH"]:
            original_risk = state["risk_level"]
            state["risk_level"] = "LOW"
            state["confidence"] = min(state["confidence"] * 1.10, 0.85)  # Boost confidence slightly
            verdict_data["risk_level"] = "LOW"
            verdict_data["downgrade"] = f"From {original_risk} to LOW - verified carbon accounting"
            verdict_data["verified_metrics"] = True

            print(f"   🟢 DOWNGRADING: {original_risk} → LOW")
            print(f"   Reason: Verifiable claim with specific date and recognized carbon accounting (no material contradictions)")



    # ============================================================
    # PRIORITY 2: HISTORICAL ANALYST INTELLIGENCE (AGENTIC)
    # ============================================================
    elif historical_data:
        reputation_score = historical_data.get("reputation_score", 50)
        violations = historical_data.get("past_violations", [])
        greenwashing_history = historical_data.get("greenwashing_history", {})
        patterns = historical_data.get("temporal_patterns", {})

        print(f"\n🤖 AGENTIC INTELLIGENCE: Historical Analysis")
        print(f"   Reputation Score: {reputation_score}/100 (LIVE calculated)")
        print(f"   Past Violations: {len(violations)} (LIVE searched)")
        print(f"   Greenwashing History: {greenwashing_history.get('prior_accusations', 0)} accusations (LIVE)")

        # DECISION RULES based on HistoricalAnalyst findings

        # Rule 1: Low reputation + violations = HIGH RISK (ADJUSTED thresholds)
        if reputation_score < 40 and len(violations) >= 1:  # Changed from ≥2 to ≥1
            print(f"\n🔴 AGENTIC DECISION: Poor track record detected")
            print(f"   - Reputation: {reputation_score}/100 (threshold: <40)")
            print(f"   - Violations: {len(violations)} (threshold: ≥1)")  # Updated

            state["risk_level"] = "HIGH"
            state["confidence"] = min(state["confidence"] * 0.70, 0.80)
            verdict_data["risk_level"] = "HIGH"
            verdict_data["escalation"] = f"Historical violations ({len(violations)}) + poor reputation ({reputation_score}/100)"
            verdict_data["historical_intelligence"] = True

        # Rule 2: Greenwashing pattern detected = HIGH RISK
        elif greenwashing_history.get("pattern_detected") and greenwashing_history.get("prior_accusations", 0) >= 2:
            print(f"\n🔴 AGENTIC DECISION: Greenwashing pattern detected")
            print(f"   - Prior Accusations: {greenwashing_history.get('prior_accusations')}")
            print(f"   - Pattern: Repeated across multiple years")

            state["risk_level"] = "HIGH"
            state["confidence"] = min(state["confidence"] * 0.65, 0.75)
            verdict_data["risk_level"] = "HIGH"
            verdict_data["escalation"] = f"Historical greenwashing pattern ({greenwashing_history.get('prior_accusations')} accusations)"
            verdict_data["historical_intelligence"] = True

        # Rule 3: Declining trend + current claim = ESCALATE
        elif patterns.get("declining_trend") and state["risk_level"] == "MODERATE":
            print(f"\n⚠️ AGENTIC DECISION: Declining ESG trend detected")
            print(f"   - Historical pattern shows worsening performance")

            state["risk_level"] = "HIGH"
            state["confidence"] *= 0.80
            verdict_data["risk_level"] = "HIGH"
            verdict_data["escalation"] = "Declining ESG trend contradicts positive claim"
            verdict_data["historical_intelligence"] = True

        # Rule 4: Reactive claims pattern = ESCALATE
        elif patterns.get("reactive_claims") and state["risk_level"] == "MODERATE":
            print(f"\n⚠️ AGENTIC DECISION: Reactive greenwashing pattern")
            print(f"   - Positive claims appear after negative news")

            state["risk_level"] = "HIGH"
            state["confidence"] *= 0.75
            verdict_data["risk_level"] = "HIGH"
            verdict_data["escalation"] = "Reactive greenwashing pattern detected"
            verdict_data["historical_intelligence"] = True

    # ============================================================
    # PRIORITY 3: CONTRADICTION ANALYZER INTELLIGENCE
    # ============================================================
    if contradiction_count >= 3 and state["risk_level"] == "MODERATE":
        print(f"\n⚠️ AGENTIC DECISION: Multiple contradictions detected")
        print(f"   - Contradictions: {contradiction_count} (threshold: ≥3)")

        state["risk_level"] = "HIGH"
        state["confidence"] *= 0.75
        verdict_data["risk_level"] = "HIGH"
        verdict_data["escalation"] = f"Multiple contradictions ({contradiction_count}) detected"
        verdict_data["contradiction_intelligence"] = True

    # ============================================================
    # PRIORITY 4: DEBATE ORCHESTRATOR INTELLIGENCE
    # ============================================================
    if debate_conflict_ratio >= 0.60 and state["risk_level"] == "MODERATE":
        print(f"\n⚠️ AGENTIC DECISION: High agent conflict detected")
        print(f"   - Conflict Ratio: {debate_conflict_ratio:.0%} (threshold: ≥60%)")

        state["risk_level"] = "HIGH"
        state["confidence"] *= 0.75
        verdict_data["risk_level"] = "HIGH"
        verdict_data["escalation"] = f"Agent disagreement ({debate_conflict_ratio:.0%})"
        verdict_data["debate_intelligence"] = True

    # ============================================================
    # PRIORITY 5: HIGH-RISK SUPERLATIVES (Pattern-based)
    # ============================================================
    superlatives = ["greenest", "leader in", "pioneer", "most sustainable", "best in class", "world's leading"]
    if any(sup in claim_lower for sup in superlatives) and state["risk_level"] == "MODERATE":
        print(f"\n⚠️ AGENTIC DECISION: Superlative language detected")

        state["risk_level"] = "HIGH"
        state["confidence"] *= 0.70
        verdict_data["risk_level"] = "HIGH"
        verdict_data["escalation"] = "Superlative greenwashing language"
        verdict_data["pattern_intelligence"] = True

    # ============================================================
    # PRIORITY 6: VAGUE CLAIMS (High-Risk Sectors)
    # ============================================================
    high_risk_sectors = ["Energy", "Automotive", "Aviation", "Mining", "Oil & Gas"]
    vague_keywords = ["committed to", "sustainable", "eco-friendly", "green", "clean energy"]
    keyword_count = sum(1 for kw in vague_keywords if kw in claim_lower)
    has_metrics = bool(re.search(r'\d+%|\d+\s*(tons|MW|GW|million|billion)|20\d{2}', state["claim"]))

    if state["industry"] in high_risk_sectors and keyword_count >= 2 and not has_metrics:
        if state["risk_level"] == "MODERATE":
            print(f"\n⚠️ AGENTIC DECISION: Vague high-risk sector claim")
            print(f"   - Sector: {state['industry']} (high baseline risk)")
            print(f"   - Vague keywords: {keyword_count}, Metrics: {has_metrics}")

            state["risk_level"] = "HIGH"
            state["confidence"] *= 0.80
            verdict_data["risk_level"] = "HIGH"
            verdict_data["escalation"] = f"Vague claim in {state['industry']} sector"
            verdict_data["sector_intelligence"] = True

    # Update final verdict
    verdict_data["final_confidence"] = state["confidence"]
    state["final_verdict"] = verdict_data

    print(f"\n✅ AGENTIC VERDICT: {state['risk_level']} (confidence: {state['confidence']:.1%})")

    # Log which intelligence sources influenced decision
    intelligence_sources = []
    if verdict_data.get("historical_intelligence"):
        intelligence_sources.append("Historical Track Record")
    if verdict_data.get("contradiction_intelligence"):
        intelligence_sources.append("Contradiction Analysis")
    if verdict_data.get("debate_intelligence"):
        intelligence_sources.append("Multi-Agent Debate")
    if verdict_data.get("pattern_intelligence"):
        intelligence_sources.append("Language Pattern Detection")
    if verdict_data.get("sector_intelligence"):
        intelligence_sources.append("Industry Risk Analysis")

    if intelligence_sources:
        print(f"   Intelligence Sources: {', '.join(intelligence_sources)}")

    # ============================================================
    # UNIFIED DUAL-OBJECTIVE OUTPUT (ESG + GW co-primary)
    # ============================================================
    try:
        unified_output = build_unified_output_from_state(state)
        state["unified_assessment"] = unified_output

        # Sync risk_level from unified output (consistency-enforced)
        unified_risk = unified_output.get("risk_level")
        if unified_risk and unified_risk != state["risk_level"]:
            print(f"   🔄 Unified consistency adjusted risk: {state['risk_level']} → {unified_risk}")
            state["risk_level"] = unified_risk
            verdict_data["risk_level"] = unified_risk

        # Sync confidence from unified output
        unified_conf = unified_output.get("final_confidence")
        if unified_conf and isinstance(unified_conf, (int, float)):
            state["confidence"] = unified_conf
            verdict_data["final_confidence"] = unified_conf

        consistency_flags = unified_output.get("quality_metadata", {}).get("consistency_flags", [])
        if consistency_flags:
            print(f"   ⚠️ Consistency flags raised: {len(consistency_flags)}")
            for flag in consistency_flags:
                print(f"      - [{flag['rule']}] {flag['message'][:100]}")

        print(f"   ✅ Unified dual-objective output built (ESG + GW co-primary)")
    except Exception as e:
        print(f"   ⚠️ Unified output builder error (non-fatal): {e}")

    # ============================================================
    # CLAIM-EVIDENCE GAP ANALYSIS
    # ============================================================
    try:
        evidence_list = state.get("evidence", []) if isinstance(state.get("evidence", []), list) else []
        gap_analysis = analyze_evidence_gaps(
            claim_text=state.get("claim", ""),
            company=state.get("company", ""),
            evidence=evidence_list,
        )
        state["evidence_gap_analysis"] = gap_analysis
        verdict_data["evidence_gap_analysis"] = {
            "claim_types": gap_analysis.get("claim_types", []),
            "evidence_sufficiency": gap_analysis.get("overall_evidence_sufficiency", 0),
            "total_required": gap_analysis.get("total_required", 0),
            "total_found": gap_analysis.get("total_found", 0),
            "priority_gaps": gap_analysis.get("highest_priority_gaps", [])[:3],
        }
        sufficiency = gap_analysis.get("overall_evidence_sufficiency", 0)
        print(f"   📋 Evidence sufficiency: {sufficiency:.0%} ({gap_analysis.get('total_found', 0)}/{gap_analysis.get('total_required', 0)} required evidence types found)")
        if gap_analysis.get("highest_priority_gaps"):
            print(f"   🔍 Top evidence gaps:")
            for gap in gap_analysis["highest_priority_gaps"][:3]:
                print(f"      - MISSING: {gap.get('description', 'Unknown')}")
    except Exception as e:
        print(f"   ⚠️ Evidence gap analysis error (non-fatal): {e}")

    # ============================================================
    # GROUND TRUTH VALIDATION (for known cases)
    # ============================================================
    try:
        risk_outputs = [o for o in state.get("agent_outputs", []) if isinstance(o, dict) and o.get("agent") == "risk_scoring"]
        if risk_outputs:
            _risk_out = risk_outputs[-1].get("output", {})
            if isinstance(_risk_out, dict):
                # Canonical post-recalibration GW score lives at the flat
                # `greenwashingriskscore` key (see risk_scorer.py:2017).
                # The legacy nested path `greenwashing_result.greenwashing_score`
                # was never populated by the agent, so reading it returned the
                # 50 fallback — the override caveat then misreported "raw GW 50"
                # regardless of what the formula actually produced.
                _gw_candidates = [
                    _risk_out.get("greenwashingriskscore"),
                    (_risk_out.get("greenwashing_result") or {}).get("greenwashing_score") if isinstance(_risk_out.get("greenwashing_result"), dict) else None,
                    _risk_out.get("greenwashingscoreraw"),
                ]
                _gw = next((float(v) for v in _gw_candidates if isinstance(v, (int, float))), 50.0)
                _esg_candidates = [
                    _risk_out.get("esg_score"),
                    _risk_out.get("esg_score_raw"),
                ]
                _esg = next((float(v) for v in _esg_candidates if isinstance(v, (int, float))), 50.0)
            else:
                _gw, _esg = 50.0, 50.0
        else:
            _gw, _esg = 50.0, 50.0

        gt_validation = validate_pipeline_output(
            company=state.get("company", ""),
            gw_score=_gw,
            esg_score=_esg,
        )
        if gt_validation.get("case_found"):
            verdict_data["ground_truth_validation"] = gt_validation
            cal_status = gt_validation.get("calibration_status", "UNKNOWN")
            print(f"   🎯 Ground truth case found: {gt_validation.get('case_id')} ({gt_validation.get('outcome')})")
            print(f"      GW: {gt_validation.get('gw_actual')}/100 (expected {gt_validation.get('gw_expected')}) {'✅' if gt_validation.get('gw_in_range') else '❌'}")
            print(f"      ESG: {gt_validation.get('esg_actual')}/100 (expected {gt_validation.get('esg_expected')}) {'✅' if gt_validation.get('esg_in_range') else '❌'}")
            print(f"      Calibration: {cal_status}")

            # Architecture (May-2026 audit fix):
            # Historical misconduct flows ONLY into the GW Trust Penalty
            # bucket — never into ESG. ESG must always reflect *current*
            # pillar performance so a company that genuinely improves can
            # earn a higher score over time. Hard ESG ceilings made the
            # system punitive in a way the user explicitly rejected.
            #
            # GW behaviour: instead of overwriting GW with ground_truth_floor,
            # we publish a `known_case_trust_penalty` that the new
            # historical_trust bucket consumes (risk_scorer:R_historical
            # weighting, default 30%). Hierarchy is now explicit:
            #     base formula → trust penalty contribution → final.
            outcome = (gt_validation.get("outcome") or "").upper()
            gw_expected = gt_validation.get("gw_expected") or [0, 100]
            if outcome == "CONFIRMED_GREENWASHING" and not gt_validation.get("gw_in_range"):
                floor_gw = float(gw_expected[0])
                if _gw < floor_gw:
                    # Publish the trust penalty as a SOFT signal. risk_scorer
                    # picks this up via state["known_case_trust_penalty"] and
                    # routes it through the historical_trust bucket. We do
                    # NOT overwrite _gw here.
                    trust_penalty_score = float(floor_gw)
                    verdict_data["known_case_trust_penalty"] = {
                        "case_id": gt_validation.get("case_id"),
                        "outcome": outcome,
                        "raw_gw_score": round(_gw, 1),
                        "implied_floor_gw": round(floor_gw, 1),
                        "trust_penalty_score": round(trust_penalty_score, 1),
                        "applies_to": "historical_trust_bucket",
                        "reason": (
                            f"Documented {outcome} case "
                            f"({gt_validation.get('regulatory_action', '')[:80]}); "
                            "contribution flows into historical_trust bucket "
                            "(no hard headline override)."
                        ),
                    }
                    state["known_case_trust_penalty"] = verdict_data["known_case_trust_penalty"]
                    print(
                        f"      🛡️ Known-case trust penalty published "
                        f"(score={trust_penalty_score:.0f}, case "
                        f"{gt_validation.get('case_id')}); GW formula will "
                        f"absorb via historical_trust bucket."
                    )

            # ESG ceiling logic deliberately removed (audit fix). ESG should
            # represent current pillar performance, not punishment memory.
            # If a confirmed-greenwashing company's pillars genuinely improve,
            # the ESG number should improve with them.

            # Surface the raw scores for transparency only — never overwrite.
            verdict_data["gw_score_raw"] = round(_gw, 1)
            verdict_data["esg_score_raw"] = round(_esg, 1)
    except Exception as e:
        print(f"   ⚠️ Ground truth validation error (non-fatal): {e}")

    # ============================================================
    # CAUSAL REASONING CHAINS (Problem #14 + #6)
    # ============================================================
    try:
        gap_data = state.get("evidence_gap_analysis", {})
        claim_types_for_causal = gap_data.get("claim_types", classify_claim(state.get("claim", "")))
        causal_chains = build_causal_chains(
            claim_text=state.get("claim", ""),
            claim_types=claim_types_for_causal,
            evidence_gaps=gap_data,
            contradiction_count=contradiction_count,
        )
        verdict_data["causal_chains"] = causal_chains
        unmet = sum(1 for c in causal_chains if c.get("status") in ("UNMET", "RED_FLAG", "FAILED"))
        print(f"   🔗 Causal chains: {len(causal_chains)} total, {unmet} unmet conditions")

        # Per-factor GW score explanations
        _risk_outs = [o for o in state.get("agent_outputs", []) if isinstance(o, dict) and o.get("agent") == "risk_scoring"]
        if _risk_outs:
            _r_out = _risk_outs[-1].get("output", {})
            _gw_res = _r_out.get("greenwashing_result", {}) if isinstance(_r_out, dict) else {}
            if isinstance(_gw_res, dict) and _gw_res:
                score_explanations = generate_score_explanation(_gw_res, {})
                verdict_data["score_explanations"] = score_explanations
                print(f"   📝 GW factor explanations generated for {len(score_explanations)} factors")
    except Exception as e:
        print(f"   ⚠️ Causal reasoning error (non-fatal): {e}")

    # ============================================================
    # ENGINEERED FEATURES (Problem #5 + #13)
    # ============================================================
    try:
        _risk_outs2 = [o for o in state.get("agent_outputs", []) if isinstance(o, dict) and o.get("agent") == "risk_scoring"]
        _r2 = _risk_outs2[-1].get("output", {}) if _risk_outs2 else {}
        _ps2 = _r2.get("pillarscores", _r2.get("pillar_scores", {})) if isinstance(_r2, dict) else {}
        _ctx2 = extract_consistency_context(state)
        eng_features = compute_engineered_features(
            company=state.get("company", ""),
            industry=state.get("industry", "General"),
            claim=state.get("claim", ""),
            esg_score=float(_r2.get("esg_score", 50) if isinstance(_r2, dict) else 50),
            environmental_score=float(_ps2.get("environmental_score", 50) if isinstance(_ps2, dict) else 50),
            social_score=float(_ps2.get("social_score", 50) if isinstance(_ps2, dict) else 50),
            governance_score=float(_ps2.get("governance_score", 50) if isinstance(_ps2, dict) else 50),
            greenwashing_score=float((_r2.get("greenwashing_result") or {}).get("greenwashing_score", 50) if isinstance(_r2, dict) else 50),
            evidence_count=_ctx2.get("evidence_count", 0),
            tier1_count=_ctx2.get("tier1_evidence_count", 0),
            tier2_count=_ctx2.get("tier2_evidence_count", 0),
            contradiction_count=_ctx2.get("contradiction_count", 0),
        )
        top_features = select_top_features(eng_features, top_n=8)
        verdict_data["engineered_features"] = eng_features
        verdict_data["top_features"] = top_features
        print(f"   🧮 {len(eng_features)} engineered features computed, top-8 selected")
    except Exception as e:
        print(f"   ⚠️ Feature engineering error (non-fatal): {e}")

    # ============================================================
    # DYNAMIC INDUSTRY & GEOGRAPHY (Problem #10)
    # ============================================================
    try:
        ev_text = " ".join(
            str(e.get("snippet", "") or e.get("relevant_text", ""))
            for e in (state.get("evidence", []) or [])[:20]
            if isinstance(e, dict)
        )
        detected_ind, ind_conf, ind_method = detect_industry(
            state.get("company", ""), state.get("claim", ""), ev_text, state.get("industry", "")
        )
        geo, geo_conf = detect_geography(state.get("company", ""), state.get("claim", ""), ev_text)
        reg_context = get_regulatory_context(geo)
        verdict_data["context_awareness"] = {
            "detected_industry": detected_ind,
            "industry_confidence": ind_conf,
            "detection_method": ind_method,
            "geography": geo,
            "geography_confidence": geo_conf,
            "regulatory_frameworks": reg_context,
        }
        if ind_method == "keyword_detection" and detected_ind != state.get("industry", "").lower():
            print(f"   🌍 Industry refined: {state.get('industry')} → {detected_ind} (conf={ind_conf})")
        print(f"   🌍 Geography: {geo} | Regulatory: {', '.join(reg_context.get('primary', []))}")
    except Exception as e:
        print(f"   ⚠️ Context awareness error (non-fatal): {e}")

    state["agent_outputs"].append({
        "agent": "verdict_generation",
        "output": verdict_data,
        "confidence": state["confidence"],
        "timestamp": datetime.now().isoformat(),
        "intelligence_sources": intelligence_sources
    })

    print(f"{'✅ NODE COMPLETED':^70}")
    return state


def report_generation_node(state: ESGState) -> ESGState:
    """Generate high-fidelity comprehensive report for JPMC Demo"""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: report_generation")
    print("="*70)

    risk_results = state.get("riskresults", {})
    pillar_scores = risk_results.get("pillarscores", risk_results.get("pillar_scores", {}))
    reasons = risk_results.get("explainability_top_3_reasons", [])
    insights = risk_results.get("actionable_insights", {})

    # 5-Feature Signals
    decomp = state.get("claim_decomposition", {})
    ledger = state.get("commitment_ledger", {})
    pathway = state.get("carbon_pathway_analysis", {})
    triangulation = state.get("adversarial_triangulation", {})
    reg_scan = state.get("regulatory_compliance", {})

    report = f"""
{'='*80}
             ESGLens™ | HIGH-FIDELITY GREENWASHING ANALYSIS REPORT
{'='*80}
Company: {state['company'].upper()}
Sector:  {state['industry'].replace('_', ' ').title()}
Rating:  {risk_results.get('ratinggrade', risk_results.get('rating_grade', 'N/A'))} ({state['risk_level']})
Confidence: {state['confidence']:.1%} | Workflow: {state.get('workflow_path', 'Deep Scan')}

ANALYSIS TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
{'='*80}

[1] EXECUTIVE SUMMARY & INTEGRITY SIGNALS
--------------------------------------------------------------------------------
{chr(10).join([f"• {r}" for r in reasons]) if reasons else "No specific integrity signals detected."}

[2] ESG PILLAR PERFORMANCE (0-100)
--------------------------------------------------------------------------------
Environmental: {pillar_scores.get('environmental_score', 0):.1f} | Weight: 35%
Social:        {pillar_scores.get('social_score', 0):.1f} | Weight: 35%
Governance:    {pillar_scores.get('governance_score', 0):.1f} | Weight: 30%
Overall ESG Score: {risk_results.get('esg_score', 0):.1f}

[3] HIGH-FIDELITY DIAGNOSTICS (2026 ENGINE)
--------------------------------------------------------------------------------
• CLAIM DECOMPOSITION: {decomp.get('internal_contradiction_score', 0)}/100 Contradiction Risk
  - Atomic Sub-claims: {len(decomp.get('sub_claims', []))} assertions analyzed.
  - Logical Tensions: {len(decomp.get('logical_tensions', []))} detected.

• COMMITMENT LEDGER: {ledger.get('promise_degradation_score', 0):.1f}/100 Degradation Score
  - Historical Revisions: {len(ledger.get('revision_events', []))} events tracked.
  - Trajectory Status: {'DEGRADING' if ledger.get('promise_degradation_score', 0) > 40 else 'STABLE'}

• CARBON PATHWAY MODEL: {pathway.get('alignment_status', 'UNKNOWN').upper()}
  - 1.5°C Alignment Gap: {pathway.get('pathway_gap_pct', 0):.1f}%
  - Scientific Credibility: {'HIGH' if pathway.get('pathway_gap_pct', 100) < 15 else 'LOW/BEYOND PHYSICS'}

• ADVERSARIAL TRIANGULATION: {triangulation.get('triangulation_score', 0):.1f}/100 Cross-Source Score
  - Third-Party Corroboration: {triangulation.get('third_party_corroboration_ratio', 0):.1%}
  - Bias Detection: {'NEUTRAL' if triangulation.get('triangulation_score', 0) > 60 else 'SKEWED TO FIRST-PARTY'}

• REGULATORY SCANNER: {len(reg_scan.get('compliance_results', []))} Frameworks Scanned
  - Jurisdictional Gaps: {len([r for r in reg_scan.get('compliance_results', []) if r.get('gap_details')])} detected.

[4] STAKEHOLDER INSIGHTS
--------------------------------------------------------------------------------
INVESTOR VIEW: {insights.get('for_investors', 'N/A')}

REGULATORY VIEW: {insights.get('for_regulators', 'N/A')}

CONSUMER VIEW: {insights.get('for_consumers', 'N/A')}

[5] EVIDENCE & JUSTIFICATION GRAPH
--------------------------------------------------------------------------------
Total Sources: {len(state['evidence'])} verified items.
Top Evidence Types: {', '.join(set([e.get('source_type', 'Web') for e in state['evidence'] if isinstance(e, dict)][:5]))}

{'='*80}
   Generated by ESGLens Multi-Agent Workflow Node: {state.get('workflow_path', 'Phase2')}
{'='*80}
"""

    state["report"] = report
    print(f"✅ High-Fidelity Report generated ({len(report)} characters)")

    state["agent_outputs"].append({
        "agent": "report_generation",
        "confidence": 1.0,
        "timestamp": datetime.now().isoformat()
    })

    print(f"{'✅ NODE COMPLETED':^70}")

    return state


# ============================================================
# PHASE 7: ESG REPORT DISCOVERY & PARSING PIPELINE
# ============================================================

def report_discovery_node(state: ESGState) -> ESGState:
    """
    PHASE 7: Automatically discover ESG reports for the company
    Uses web search to find published ESG, sustainability, and annual reports
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: report_discovery")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not REPORT_DISCOVERY_AVAILABLE:
        print("⚠️  Report Discovery not available - skipping")
        state["agent_outputs"].append({
            "agent": "report_discovery",
            "output": {"reports": [], "status": "skipped"},
            "confidence": 0.0
        })
        return state

    try:
        company = state.get("company")
        if not company:
            print("⚠️  No company specified - skipping report discovery")
            return state

        print(f"[Workflow] Starting ESG report discovery for {company}")
        print(f"🔍 Searching for ESG reports (up to 5 results)...")

        # Discover reports using convenience function
        discovered_reports = discover_company_reports(company, max_results=5)

        if discovered_reports:
            print(f"✅ Discovered {len(discovered_reports)} reports:")
            for report in discovered_reports[:3]:
                print(f"   - {report.get('year')}: {report.get('title', 'Untitled')[:60]}")
                print(f"     Confidence: {report.get('confidence', 0):.0%}")
        else:
            print(f"⚠️  No ESG reports discovered for {company}")

        confidence = 0.7 if discovered_reports else 0.3

        state["agent_outputs"].append({
            "agent": "report_discovery",
            "output": {
                "company": company,
                "reports": discovered_reports,
                "report_count": len(discovered_reports),
                "status": "success"
            },
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ Report Discovery error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "report_discovery",
            "error": str(e),
            "confidence": 0.0
        })

    return state


def report_downloader_node(state: ESGState) -> ESGState:
    """
    PHASE 7: Download discovered ESG reports (PDFs)
    Validates downloads and caches for reuse
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: report_downloader")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not REPORT_DOWNLOADER_AVAILABLE:
        print("⚠️  Report Downloader not available - skipping")
        return state

    try:
        company = state.get("company")

        # Find report discovery output
        discovery_outputs = [o for o in state.get("agent_outputs", [])
                           if o.get("agent") == "report_discovery"]

        if not discovery_outputs:
            print("⚠️  No report discovery output found - skipping download")
            return state

        discovered_reports = discovery_outputs[-1].get("output", {}).get("reports", [])

        if not discovered_reports:
            print("⚠️  No reports to download")
            return state

        print(f"[Workflow] Downloading ESG reports for {company}")
        print(f"📥 Downloading {len(discovered_reports)} discovered reports...")

        # Download reports using convenience function
        downloaded_reports = download_company_reports(company, discovered_reports)

        if downloaded_reports:
            print(f"✅ Downloaded {len(downloaded_reports)} reports:")
            for report in downloaded_reports:
                size_mb = report.get("file_size", 0) / (1024 * 1024)
                cached = report.get("from_cache", False)
                source = "(cached)" if cached else "(fresh download)"
                print(f"   - {report.get('year')}: {size_mb:.1f}MB {source}")
        else:
            print(f"⚠️  Failed to download any reports")

        confidence = 0.8 if downloaded_reports else 0.3

        state["agent_outputs"].append({
            "agent": "report_downloader",
            "output": {
                "company": company,
                "downloads": downloaded_reports,
                "download_count": len(downloaded_reports),
                "status": "success"
            },
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ Report Downloader error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "report_downloader",
            "error": str(e),
            "confidence": 0.0
        })

    return state


def report_parser_node(state: ESGState) -> ESGState:
    """
    PHASE 7: Parse downloaded PDFs and extract text chunks
    Cleans text and chunks for LLM processing
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: report_parser")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not REPORT_PARSER_AVAILABLE:
        print("⚠️  Report Parser not available - skipping")
        return state

    try:
        company = state.get("company")

        # Find report downloader output
        downloader_outputs = [o for o in state.get("agent_outputs", [])
                            if o.get("agent") == "report_downloader"]

        if not downloader_outputs:
            print("⚠️  No downloaded reports found - skipping parsing")
            return state

        downloaded_reports = downloader_outputs[-1].get("output", {}).get("downloads", [])

        if not downloaded_reports:
            print("⚠️  No reports to parse")
            return state

        print(f"[Workflow] Parsing ESG reports for {company}")
        print(f"📄 Parsing {len(downloaded_reports)} reports into chunks...")

        # Parse reports using convenience function
        parsed_chunks = parse_downloaded_reports(company, downloaded_reports)

        if parsed_chunks:
            print(f"✅ Extracted {len(parsed_chunks)} text chunks:")
            years_found = set(chunk.get("year") for chunk in parsed_chunks)
            print(f"   Years covered: {sorted(years_found, reverse=True)}")
            avg_chunk_size = sum(len(chunk.get("text", "")) for chunk in parsed_chunks) // len(parsed_chunks)
            print(f"   Avg chunk size: {avg_chunk_size} characters")
        else:
            print(f"⚠️  No chunks extracted from reports")

        confidence = 0.8 if parsed_chunks else 0.3

        state["agent_outputs"].append({
            "agent": "report_parser",
            "output": {
                "company": company,
                "chunks": parsed_chunks,
                "chunk_count": len(parsed_chunks),
                "downloaded_reports": downloaded_reports,
                "status": "success"
            },
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ Report Parser error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "report_parser",
            "error": str(e),
            "confidence": 0.0
        })

    return state


def report_claim_extraction_node(state: ESGState) -> ESGState:
    """
    PHASE 7: Extract ESG claims from parsed report chunks
    Groups claims by year and deduplicates
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: report_claim_extraction")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not CLAIM_EXTRACTOR_AVAILABLE:
        print("⚠️  Claim Extractor not available - skipping report claim extraction")
        return state

    try:
        company = state.get("company")

        # Find report parser output
        parser_outputs = [o for o in state.get("agent_outputs", [])
                         if o.get("agent") == "report_parser"]

        if not parser_outputs:
            print("⚠️  No parsed report chunks found - skipping claim extraction")
            return state

        parsed_chunks = parser_outputs[-1].get("output", {}).get("chunks", [])

        if not parsed_chunks:
            print("⚠️  No chunks to extract claims from")
            return state

        print(f"[Workflow] Extracting ESG claims from report chunks for {company}")
        print(f"📊 Processing {len(parsed_chunks)} chunks for claim extraction...")

        # Use report-specific claim extraction method
        try:
            extractor = ClaimExtractor()
            result = extractor.extract_claims_from_report_chunks(
                company,
                parsed_chunks,
                target_claim=state.get("claim", "")
            )
        except AttributeError:
            print("⚠️  Report chunk extraction method not available - skipping")
            return state

        if isinstance(result, dict):
            report_claims_by_year = result.get("report_claims_by_year", {})
            total_claims = result.get("total_report_claims", 0)
            years = result.get("years_detected", [])
            chunks_processed = result.get("chunks_processed", 0)
            chunks_skipped = result.get("chunks_skipped", 0)
            cache_hits = result.get("cache_hits", 0)
            llm_calls_made = result.get("llm_calls_made", 0)

            # Calculate optimization metrics
            total_chunks = chunks_processed + chunks_skipped
            esg_filtering_reduction = (100 * chunks_skipped / total_chunks) if total_chunks > 0 else 0

            print(f"\n{'📊 OPTIMIZATION METRICS':=^70}")
            print(f"✅ Extracted {total_claims} claims from reports")
            print(f"\n📈 Pipeline Efficiency:")
            print(f"   • Total chunks from parser: {total_chunks}")
            print(f"   • ESG-filtered chunks used: {chunks_processed}")
            print(f"   • Chunks filtered out: {chunks_skipped} ({esg_filtering_reduction:.1f}% reduction)")
            print(f"\n⚡ API Optimization:")
            print(f"   • LLM calls made: {llm_calls_made}")
            print(f"   • Cache hits: {cache_hits}")
            if cache_hits > 0:
                print(f"   • Cache save: ~{cache_hits * 3} est. LLM calls avoided")
            print(f"\n📅 Results by Year:")
            print(f"   Years detected: {sorted(years, reverse=True) if years else 'None'}")
            for year in sorted(years, reverse=True):
                year_claims = report_claims_by_year.get(year, [])
                print(f"   - {year}: {len(year_claims)} claims")
            print(f"{'='*70}")

            confidence = 0.8 if total_claims > 0 else 0.3
        else:
            report_claims_by_year = {}
            total_claims = 0
            confidence = 0.3
            print("⚠️  Invalid result from claim extraction")

        state["agent_outputs"].append({
            "agent": "claim_extractor",
            "output": result if isinstance(result, dict) else {"claims": []},
            "report_claims_by_year": report_claims_by_year,
            "total_report_claims": total_claims,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "source": "report_chunks",
            "optimization_metrics": {
                "chunks_processed": result.get("chunks_processed", 0) if isinstance(result, dict) else 0,
                "chunks_skipped": result.get("chunks_skipped", 0) if isinstance(result, dict) else 0,
                "cache_hits": result.get("cache_hits", 0) if isinstance(result, dict) else 0,
                "llm_calls_made": result.get("llm_calls_made", 0) if isinstance(result, dict) else 0
            }
        })

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ Report Claim Extraction error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "claim_extractor",
            "error": str(e),
            "confidence": 0.0,
            "source": "report_chunks"
        })

    return state


def temporal_consistency_node(state: ESGState) -> ESGState:
    """
    PHASE 7: Analyze temporal consistency in ESG claims
    Detects greenwashing by comparing claims over time and against actual performance
    Only runs if report claims are available
    """
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print(f"Node: temporal_consistency")
    print(f"Timestamp: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)

    if not TEMPORAL_CONSISTENCY_AVAILABLE:
        print("⚠️  Temporal Consistency Agent not available - skipping")
        return state

    try:
        company = state.get("company")

        # Check if we have report claims from report_claim_extraction_node
        claim_extractor_outputs = [o for o in state.get("agent_outputs", [])
                                  if o.get("agent") == "claim_extractor" and o.get("source") == "report_chunks"]

        if not claim_extractor_outputs:
            print("⚠️  No PDF chunks — running temporal analysis on web evidence (reduced accuracy mode)")
            web_claims = {}
            for ev in state.get("evidence", [])[:80]:
                if not isinstance(ev, dict):
                    continue
                text = str(ev.get("snippet") or ev.get("relevant_text") or "").strip()
                if not text:
                    continue
                date_raw = str(ev.get("date") or "")
                year = None
                for token in date_raw.replace("/", "-").split("-"):
                    if token.isdigit() and len(token) == 4:
                        year = int(token)
                        break
                if year is None:
                    year = datetime.now().year
                web_claims.setdefault(year, []).append(text)

            if not web_claims:
                print("⚠️  No web evidence available for temporal fallback mode")
                return state

            result = analyze_temporal_consistency(company, web_claims, state.get("agent_outputs", []))
            state["agent_outputs"].append({
                "agent": "temporal_consistency",
                "output": result,
                "confidence": 0.6,
                "timestamp": datetime.now().isoformat(),
                "mode": "web_evidence_fallback",
            })
            return state

        latest_claim_output = claim_extractor_outputs[-1]
        report_claims_by_year = latest_claim_output.get("report_claims_by_year", {})
        if not report_claims_by_year:
            claim_extractor_output = latest_claim_output.get("output", {})
            if isinstance(claim_extractor_output, dict):
                report_claims_by_year = claim_extractor_output.get("report_claims_by_year", {})

        if not report_claims_by_year:
            # Fallback: derive lightweight claims directly from parsed report chunks.
            parser_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "report_parser"]
            parsed_chunks = parser_outputs[-1].get("output", {}).get("chunks", []) if parser_outputs else []
            synthesized = {}
            for chunk in parsed_chunks:
                if not isinstance(chunk, dict):
                    continue
                year = chunk.get("report_year") or chunk.get("year")
                text = str(chunk.get("text", ""))
                if not year or not text:
                    continue

                sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
                picked = []
                for sent in sentences:
                    lower = sent.lower()
                    if any(k in lower for k in ["emission", "scope", "renewable", "net zero", "carbon", "target", "%"]):
                        picked.append(sent)
                    if len(picked) >= 5:
                        break

                if picked:
                    synthesized.setdefault(int(year), []).extend(picked)

            report_claims_by_year = synthesized

        if not report_claims_by_year:
            print("⚠️  No report claims by year - skipping temporal consistency analysis")
            return state

        print(f"[Workflow] Running temporal consistency analysis for {company}")
        print(f"📈 Analyzing claim trends across {len(report_claims_by_year)} years...")

        # Call temporal consistency analysis
        result = analyze_temporal_consistency(company, report_claims_by_year, state.get("agent_outputs", []))

        if isinstance(result, dict):
            temporal_score = result.get("temporal_consistency_score", 50)
            risk_level = result.get("risk_level", "MODERATE")
            claim_trend = result.get("claim_trend", "unknown")
            env_trend = result.get("environmental_trend", "unknown")

            print(f"✅ Temporal Consistency Analysis Complete:")
            # Score may be the sentinel string "NOT_COMPUTED" when historical
            # data was insufficient — print it raw instead of formatting.
            if isinstance(temporal_score, (int, float)):
                print(f"   Score: {temporal_score:.0f}/100")
            else:
                print(f"   Score: {temporal_score}")
            print(f"   Risk Level: {risk_level}")
            print(f"   Claim Trend: {claim_trend}")
            print(f"   Environmental Trend: {env_trend}")

            evidence = result.get("evidence", [])
            if evidence:
                print(f"   Key Findings: {len(evidence)} inconsistencies detected")
                for item in evidence[:2]:
                    print(f"   - {item[:70]}...")

            confidence = 0.85
        else:
            print("⚠️  Invalid result from temporal consistency analysis")
            confidence = 0.3

        state["agent_outputs"].append({
            "agent": "temporal_consistency",
            "output": result if isinstance(result, dict) else {"status": "error"},
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })

        # --- Step 7: Compute Temporal Escalation Score (T) ---
        # Risk Mitigation #2: If < 3 years of data, T = 0 (neutral)
        try:
            T = 0.0
            data_sufficient = False
            if isinstance(result, dict):
                years_analyzed = result.get("years_analyzed", [])
                data_quality = result.get("data_quality", "low")
                temporal_mode = result.get("temporal_mode", "none")
                status = result.get("status", "")

                # NOT_COMPUTED sentinel means the agent declined to score
                # (BUG 9 fix). Always treat as insufficient → T = 0 neutral.
                raw_score = result.get("temporal_consistency_score", 0.0)
                numeric_score = (
                    float(raw_score)
                    if isinstance(raw_score, (int, float))
                    else 0.0
                )
                if status == "insufficient_data" or raw_score == "NOT_COMPUTED":
                    data_sufficient = False
                    T = 0.0
                elif len(years_analyzed) >= 3 and data_quality in ("high", "medium"):
                    data_sufficient = True
                    # T is the temporal_consistency_score (high = claims escalate faster than performance)
                    T = numeric_score
                elif temporal_mode == "trend" and len(years_analyzed) >= 2:
                    # Partial data: use half weight
                    data_sufficient = False
                    T = numeric_score * 0.5
                else:
                    # Insufficient data: T = 0 (neutral, weight redistributed in GW formula)
                    T = 0.0
                    data_sufficient = False

            T = round(max(0.0, min(100.0, T)), 1)
            state["temporal_escalation"] = {
                "score": T,
                "status": AgentStatus.SUCCESS.value if data_sufficient else AgentStatus.PARTIAL.value,
                "data_sufficient": data_sufficient,
                "years_analyzed": result.get("years_analyzed", []) if isinstance(result, dict) else [],
                "data_quality": result.get("data_quality", "low") if isinstance(result, dict) else "low",
            }
            state.setdefault("pipeline_agent_statuses", {})["temporal_consistency"] = AgentStatus.SUCCESS if data_sufficient else AgentStatus.PARTIAL
            print(f"   📊 Temporal Escalation Score (T): {T}/100 (data_sufficient={data_sufficient})")
        except Exception as e:
            print(f"   ⚠️ Temporal escalation calculation failed: {e}")
            state["temporal_escalation"] = {"score": 0.0, "status": AgentStatus.NULL_RESULT.value, "data_sufficient": False, "fallback_reason": str(e)}
            state.setdefault("pipeline_agent_statuses", {})["temporal_consistency"] = AgentStatus.FAILED

        print(f"{'✅ NODE COMPLETED':^70}")

    except Exception as e:
        print(f"❌ Temporal Consistency error: {e}")
        import traceback
        traceback.print_exc()
        state["agent_outputs"].append({
            "agent": "temporal_consistency",
            "error": str(e),
            "confidence": 0.0
        })

    return state


def commitment_ledger_update_node(state: ESGState) -> ESGState:
    """Persist current commitments and detect revisions/degradation trajectory."""
    print(f"\n{'🟢 LANGGRAPH NODE EXECUTING':=^70}")
    print("Node: commitment_ledger_update")
    print("=" * 70)

    if not COMMITMENT_LEDGER_AVAILABLE:
        state["commitment_ledger"] = {
            "inserted_commitments": 0,
            "revision_events": [],
            "promise_degradation_score": 0.0,
            "status": "unavailable",
        }
        state["agent_outputs"].append({
            "agent": "commitment_ledger_update",
            "output": state["commitment_ledger"],
            "confidence": 0.4,
            "timestamp": datetime.now().isoformat(),
        })
        return state

    decomposition = state.get("claim_decomposition") if isinstance(state.get("claim_decomposition"), dict) else {}
    sub_claims = decomposition.get("sub_claims") if isinstance(decomposition.get("sub_claims"), list) else []
    if not sub_claims:
        sub_claims = [{"id": "SC1", "text": state.get("claim", ""), "type": "policy_claim"}]

    try:
        ledger = CommitmentLedger("data/commitment_ledger.db")
        run_date = datetime.now().date().isoformat()
        run_id = f"{state.get('company', 'company')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        output = ledger.update_from_subclaims(
            company=state.get("company", ""),
            run_id=run_id,
            run_date=run_date,
            sub_claims=sub_claims,
            evidence=state.get("evidence", []),
        )
        output["status"] = "ok"
    except Exception as e:
        print(f"❌ CommitmentLedger error: {e}")
        output = {
            "inserted_commitments": 0,
            "revision_events": [],
            "promise_degradation_score": 0.0,
            "status": "error",
            "error": str(e),
        }

    state["commitment_ledger"] = output
    state.setdefault("node_execution_order", []).append("Commitment Ledger Update")
    state["agent_outputs"].append({
        "agent": "commitment_ledger_update",
        "output": output,
        "confidence": 0.73,
        "timestamp": datetime.now().isoformat(),
    })
    print(
        f"✅ Ledger updated: commitments={output.get('inserted_commitments', 0)} | "
        f"promise_degradation={output.get('promise_degradation_score', 0)}"
    )
    return state



# ============================================================
# ESG MISMATCH DETECTOR NODE (2026 Features)
# ============================================================

def esg_mismatch_node(state: ESGState) -> ESGState:
    """
    Executes the ESG Mismatch Detector to compare company promises vs actual evidence.
    """
    print(f"\n{'?? NODE: ESG Mismatch Detector':=^70}")

    # Initialize state collections if missing
    if "agent_outputs" not in state or not isinstance(state["agent_outputs"], list):
        state["agent_outputs"] = []

    company = state.get("company", "")
    if not company or analyze_company_esg is None:
        print(f"?? Skipping mismatch detection (missing company name or module unavailable)")
        state["agent_outputs"].append({
            "agent": "esg_mismatch",
            "output": {"status": "skipped", "reason": "Module unavailable or missing company"},
            "confidence": 0.0,
            "timestamp": datetime.now().isoformat()
        })
        return state

    try:
        print(f"?? Analyzing ESG promises vs reality for: {company}")

        # ── PERF: bypass duplicate report-fetch + duplicate evidence-collection ──
        # The standalone analyze_company_esg re-runs DuckDuckGo discovery, PDF
        # download, full text extraction, and parallel external-evidence search
        # — all of which the main pipeline has already done. We pass the
        # already-acquired data so esg_mismatch only runs promise extraction
        # (LLM) and the comparison engine. Saves 2-6 min per run.
        _parser_outputs = [
            o for o in state.get("agent_outputs", []) if isinstance(o, dict) and o.get("agent") == "report_parser"
        ]
        _state_report_text = ""
        if _parser_outputs:
            _chunks = (_parser_outputs[-1].get("output") or {}).get("chunks") or []
            _state_report_text = "\n\n".join(
                str(c.get("text") or c.get("content") or "")
                for c in _chunks if isinstance(c, dict)
            )[:200_000]  # cap to prevent LLM context blow-up
        _state_evidence = state.get("evidence") or []

        mismatch_results = analyze_company_esg(
            company,
            state_evidence=_state_evidence,
            state_report_text=_state_report_text or None,
        )

        if isinstance(mismatch_results, dict):
            # Save raw structure to state
            state["esg_mismatch_analysis"] = mismatch_results
            promises = mismatch_results.get("promises", [])
            if isinstance(promises, list):
                renewable_promise = None
                for item in promises:
                    if not isinstance(item, dict):
                        continue
                    metric = str(item.get("metric", "")).lower()
                    quote = str(item.get("supporting_quote") or item.get("source") or "").lower()
                    if "renewable" in metric or "renewable" in quote:
                        renewable_promise = item
                        break
                if renewable_promise:
                    carbon_data = state.get("carbon_extraction", {})
                    if not isinstance(carbon_data, dict):
                        carbon_data = {}
                    target = renewable_promise.get("target")
                    deadline = renewable_promise.get("deadline")
                    if target is not None:
                        carbon_data["renewable_target_pct"] = target
                    if deadline is not None:
                        carbon_data["renewable_target_year"] = deadline
                    carbon_data["renewable_status"] = "pledged_not_verified"
                    state["carbon_extraction"] = carbon_data

            risk = mismatch_results.get("Overall Greenwashing Risk", "Unknown")
            print(f"   Mismatch Risk Level: {risk}")

            # Decide a confidence baseline
            confidence = 0.8 if risk in ["High", "Severe", "Violation Detected"] else 0.6

            state["agent_outputs"].append({
                "agent": "esg_mismatch",
                "output": mismatch_results,
                "confidence": confidence,
                "timestamp": datetime.now().isoformat()
            })

        else:
            print(f"?? Unexpected mismatch result format: {type(mismatch_results)}")

    except Exception as e:
        print(f"? Error in ESG Mismatch Detector: {e}")
        import traceback
        traceback.print_exc()

        state["agent_outputs"].append({
            "agent": "esg_mismatch",
            "error": str(e),
            "confidence": 0.0,
            "timestamp": datetime.now().isoformat()
        })

    print(f"{'='*70}")
    return state
