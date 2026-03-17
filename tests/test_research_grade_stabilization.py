import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AGENTS_DIR = os.path.join(ROOT, "agents")
if AGENTS_DIR not in sys.path:
    sys.path.insert(0, AGENTS_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from carbon_extractor import CarbonExtractor
from claim_extractor import ClaimExtractor
from greenwishing_detector import GreenwishingDetector
from industry_comparator import IndustryComparator
from evidence_retriever import EvidenceRetriever
from regulatory_scanner import RegulatoryHorizonScanner
from risk_scorer import RiskScorer
from temporal_consistency_agent import TemporalConsistencyAgent
from core.agent_wrappers import _build_analyses_dict
from core.supervisor_agent import SupervisorAgent


def test_carbon_regex_extracts_scopes_and_converts_units():
    extractor = CarbonExtractor()
    text = (
        "Scope 1 emissions were 1.2 MtCO2e. "
        "Scope 2 emissions were 350 ktCO2e. "
        "Scope 3 emissions were 2,000 tCO2e. "
        "Total emissions were 1.55 MtCO2e."
    )

    out = extractor._regex_extract_carbon(text)

    assert out["scope1"]["value"] == 1_200_000
    assert out["scope2"]["value"] == 350_000
    assert out["scope3"]["total"] == 2_000
    assert out["total"]["value"] == 1_550_000


def test_offset_transparency_flags_avoidance_heavy_profile():
    extractor = CarbonExtractor()
    text = (
        "The company retires offset credits from cookstove programs and avoided emissions projects. "
        "Avoidance credits account for 80% of portfolio. "
        "Removal credits are 20%."
    )

    audit = extractor._audit_offset_transparency(text, {})

    assert audit["status"] in ["high_avoidance_reliance", "moderate_avoidance_reliance"]
    assert audit["avoidance_share_pct"] >= audit["removal_share_pct"]
    assert audit["risk_penalty_points"] >= 8


def test_greenhushing_score_zero_when_all_disclosures_present():
    detector = GreenwishingDetector()
    evidence_text = (
        "Scope 1 and Scope 2 and Scope 3 emissions disclosed. "
        "Renewable energy percentage is 78%. "
        "Net zero by 2050 with SBTi science based target validation. "
        "Climate capex investment disclosed in annual report."
    )

    out = detector._detect_greenhushing(evidence_text, "TestCo")

    assert out["score"] == 0
    assert out["missing_fields"] == 0
    assert out["disclosure_completeness"] == 1.0


def test_greenhushing_uses_structured_context_when_web_evidence_is_sparse():
    detector = GreenwishingDetector()
    out = detector._detect_greenhushing(
        evidence_text="",
        company="TestCo",
        structured_context={
            "carbon_extraction": {
                "emissions": {
                    "scope1": {"value": 1000},
                    "scope2": {"value": 2000},
                    "scope3": {"total": 3000},
                },
                "renewable_energy_percentage": "100%",
                "net_zero_target": "2050",
                "science_based_target": True,
            }
        },
    )

    assert out["missing_fields"] <= 1
    assert out["score"] <= 20


def test_claim_filter_rejects_generic_and_keeps_measurable():
    extractor = ClaimExtractor()
    claims = [
        {"claim_text": "We are committed to sustainability and continue to work on it."},
        {"claim_text": "We target 45% renewable energy by 2030."},
        {"claim_text": "Company aims to improve over time."},
        {"claim_text": "Scope 1 and Scope 2 emissions reduced by 18% from baseline."},
    ]

    out = extractor._filter_extracted_claims(claims)
    texts = [c["claim_text"] for c in out]

    assert "We target 45% renewable energy by 2030." in texts
    assert "Scope 1 and Scope 2 emissions reduced by 18% from baseline." in texts
    assert all("committed to" not in t.lower() for t in texts)


def test_regulatory_compliance_score_gap_formula_is_consistent():
    scanner = RegulatoryHorizonScanner()
    compliance_results = [
        {
            "compliance_status": "Partially Compliant",
            "requirements_unverified": [{"requirement": "A"}, {"requirement": "B"}],
        },
        {
            "compliance_status": "Compliant",
            "requirements_unverified": [],
        },
    ]

    out = scanner._calculate_compliance_score(compliance_results)

    assert out["gaps"] == 2
    assert out["score"] == 84


def test_temporal_analysis_single_year_uses_recent_snapshot_mode():
    agent = TemporalConsistencyAgent()
    out = agent.analyze_temporal_consistency(
        company_name="BP",
        report_claims_by_year={2024: ["Net zero by 2050"]},
        agent_outputs=[],
    )

    assert out["status"] == "recent_report_analysis"
    assert out["claim_trend"] == "recent_snapshot"
    assert out["temporal_mode"] == "snapshot"
    assert out["temporal_weight"] <= 0.05


def test_temporal_analysis_multiyear_has_nonzero_weight():
    agent = TemporalConsistencyAgent()
    claims = {
        2024: ["Scope 1 emissions reduced by 10%", "Net zero by 2050"],
        2023: ["Scope 1 emissions reduced by 7%", "Renewable energy 80%"],
        2022: ["Scope 1 emissions reduced by 5%", "Renewable energy 70%"],
    }

    out = agent.analyze_temporal_consistency(
        company_name="TestCo",
        report_claims_by_year=claims,
        agent_outputs=[{"agent": "carbon_extraction", "output": {"emissions": {"scope1": {"value": 1000}}}}],
    )

    assert out["status"] == "success"
    assert out["temporal_mode"] == "trend"
    assert out["temporal_weight"] >= 0.1


def test_dei_progress_signals_capture_target_gap_and_yoy():
    scorer = RiskScorer.__new__(RiskScorer)
    text = (
        "Diversity target of 40% women in leadership by 2030. "
        "Women in leadership is 31% this year and was 29% last year."
    )

    dei = scorer._extract_dei_progress_signals(text.lower())

    assert dei["has_target"] is True
    assert dei["has_actual"] is True
    assert dei["target_pct"] == 40.0
    assert dei["current_pct"] == 31.0
    assert dei["prior_pct"] == 29.0
    assert dei["yoy_change"] == 2.0
    assert dei["target_gap"] == 9.0


def test_peer_fallback_contains_energy_benchmark_set():
    comparator = IndustryComparator()

    class _DummyLLM:
        def call_groq(self, *args, **kwargs):
            return None

    comparator.llm = _DummyLLM()

    peers = comparator._get_peers("BP")

    assert len(peers) >= 5
    expected = {"Shell", "TotalEnergies", "Chevron", "Exxon", "Reliance", "Adani"}
    assert len(expected.intersection(set(peers))) >= 3


def test_build_analyses_dict_flattens_evidence_and_keeps_temporal_output():
    state = {
        "industry": "Technology",
        "evidence": [{"source": "A", "snippet": "s1"}],
        "carbon_extraction": {"emissions": {"scope1": {"value": 10}}},
        "agent_outputs": [
            {
                "agent": "evidence_retrieval",
                "output": {"evidence": [{"source": "B", "snippet": "s2"}]},
                "financial_context": {"financial_data_available": True},
            },
            {
                "agent": "temporal_consistency",
                "output": {"status": "success", "temporal_consistency_score": 55},
            },
        ],
    }

    analyses = _build_analyses_dict(state)

    snippets = [e.get("snippet") for e in analyses["evidence"] if isinstance(e, dict)]
    assert "s1" in snippets
    assert "s2" in snippets
    assert analyses["temporal_consistency"].get("status") == "success"
    assert analyses["industry"] == "Technology"


def test_supervisor_routes_quantitative_esg_claims_to_non_fast_track():
    supervisor = SupervisorAgent.__new__(SupervisorAgent)
    state = {
        "claim": "Company targets net zero by 2030 with 100% renewable electricity",
        "complexity_score": 0.1,
        "agent_outputs": [],
    }

    path = supervisor.route_workflow(state)

    assert path in ["standard_track", "deep_analysis"]


def test_evidence_weight_prioritizes_third_party_audits_over_company_reports():
    retriever = EvidenceRetriever.__new__(EvidenceRetriever)
    retriever.source_weights = {
        "company_esg_report": 0.65,
        "sec_filing": 0.95,
        "cdp_disclosure": 0.98,
        "third_party_audit": 1.0,
        "ngo_report": 0.8,
        "major_news": 0.6,
        "aggregator": 0.3,
        "default": 0.5,
    }

    company_weight = retriever._get_source_weight(
        {"url": "https://example.com/sustainability-report-2024", "source": "Company", "title": "ESG Report"},
        "Company/Corporate",
    )
    audit_weight = retriever._get_source_weight(
        {"url": "https://example.com/limited-assurance-statement", "source": "Independent Auditor", "title": "TCFD Assurance"},
        "ESG Platform",
    )

    assert audit_weight > company_weight
