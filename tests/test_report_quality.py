import os
from datetime import datetime

from agents.contradiction_analyzer import ContradictionAnalyzer
from agents.regulatory_scanner import RegulatoryHorizonScanner
from agents.sentiment_analyzer import SentimentAnalyzer
from core.professional_report_generator import ProfessionalReportGenerator


def _test_state(company: str, claim: str):
    evidence = [
        {
            "source_name": "Reuters",
            "url": "https://reuters.com/test",
            "reliability_tier": "Major News Outlet",
            "stance": "contradicts",
            "date_retrieved": datetime.utcnow().isoformat(),
            "title": "Test contradiction article",
            "snippet": "Company expanded fossil output while claiming net zero.",
            "relationship_to_claim": "Contradicts",
        }
    ]
    risk_results = {
        "greenwashing_risk_score": 64.2,
        "esg_score": 35.8,
        "rating_grade": "BB",
        "risk_level": "HIGH",
        "environmental_score": 30.0,
        "social_score": 42.0,
        "governance_score": 33.0,
        "pillar_factors": {
            "environmental": [
                {
                    "factor": "Carbon data quality",
                    "raw_signal": 0.0,
                    "source": "Carbon extractor",
                    "weight": 0.30,
                    "points_contributed": 0.0,
                    "confidence": "Low",
                }
            ],
            "social": [
                {
                    "factor": "Labor controversy count",
                    "raw_signal": 1,
                    "source": "Contradiction analyzer",
                    "weight": 0.30,
                    "points_contributed": 20.0,
                    "confidence": "Medium",
                }
            ],
            "governance": [
                {
                    "factor": "Board independence disclosure",
                    "raw_signal": "Absent",
                    "source": "Evidence retrieval",
                    "weight": 0.30,
                    "points_contributed": 0.0,
                    "confidence": "Low",
                }
            ],
        },
        "pillar_scores": {
            "environmental_score": 30.0,
            "social_score": 42.0,
            "governance_score": 33.0,
        },
    }
    return {
        "company": company,
        "industry": "Energy",
        "claim": claim,
        "evidence": evidence,
        "risk_level": "HIGH",
        "confidence": 0.72,
        "risk_results": risk_results,
        "contradiction_results": {
            "contradictions_found": 1,
            "contradiction_list": [
                {
                    "severity": "HIGH",
                    "description": "Known contradiction case",
                    "source": "ClientEarth",
                    "year": 2023,
                }
            ],
            "most_severe": {
                "severity": "HIGH",
                "description": "Known contradiction case",
                "source": "ClientEarth",
                "year": 2023,
            },
            "confidence": 0.8,
        },
        "sentiment_results": {
            "articles_analyzed": 3,
            "claim_sentiment": "positive",
            "evidence_sentiment": "negative",
            "sentiment_divergence": 0.4,
            "notable_signal": "Promotional overclaiming detected",
            "confidence": 0.7,
        },
        "historical_results": {
            "years_analyzed": 2,
            "year_range": "2022-2023",
            "claim_tone_trend": "ESCALATING",
            "env_performance_trend": "DECLINING",
            "violations_count": 1,
            "violations": [{"description": "Climate case", "year": 2023}],
            "reputation_score": 41,
            "confidence": 0.65,
        },
        "regulatory_results": {
            "jurisdiction": "Global",
            "applicable_regulations": ["SBTi", "CDP"],
            "compliance_score": {"score": 76, "risk_level": "Low", "gaps": 1},
            "compliance_results": [
                {"regulation_name": "SBTi", "gap_details": []},
                {"regulation_name": "CDP", "gap_details": ["Missing CDP disclosure"]},
            ],
            "regulatory_risks": [{"regulation": "CDP"}],
        },
        "credibility_results": {
            "total_sources": 4,
            "high_credibility_list": ["Reuters"],
            "low_credibility_count": 1,
            "unverifiable_count": 1,
            "overall_credibility": 74,
        },
        "climatebert_results": {
            "classification": "Likely green claim",
            "climate_relevance": 87,
            "greenwashing_risk": 68,
            "risk_level": "High",
            "claim_score": 81,
            "evidence_score": 49,
        },
        "explainability_results": {
            "method": "SHAP",
            "top_factors": [
                {"factor": "Carbon data quality", "impact": "High", "direction": "increases risk"},
                {"factor": "Regulatory gaps", "impact": "Moderate", "direction": "increases risk"},
            ],
            "explanation_text": "Primary risk driven by missing disclosed emissions.",
        },
        "node_execution_order": [
            "Claim Extraction",
            "Evidence Retrieval",
            "Carbon Extraction",
            "Greenwishing Detection",
            "Regulatory Scanning",
            "Contradiction Analysis",
            "Temporal Analysis",
            "Peer Comparison",
            "Risk Scoring",
            "Verdict Generation",
        ],
        "agent_outputs": [
            {"agent": "risk_scoring", "output": risk_results, "confidence": 0.72, "timestamp": datetime.utcnow().isoformat()},
            {"agent": "contradiction_analysis", "output": {"contradictions_found": 1}, "confidence": 0.8, "timestamp": datetime.utcnow().isoformat()},
            {"agent": "sentiment_analysis", "output": {"claim_sentiment": "positive"}, "confidence": 0.7, "timestamp": datetime.utcnow().isoformat()},
            {"agent": "temporal_analysis", "output": {"years_analyzed": 2}, "confidence": 0.65, "timestamp": datetime.utcnow().isoformat()},
            {"agent": "regulatory_scanning", "output": {"compliance_score": {"score": 76, "risk_level": "Low", "gaps": 1}}, "confidence": 0.75, "timestamp": datetime.utcnow().isoformat()},
        ],
    }


def generate_test_report(company: str, claim: str) -> str:
    generator = ProfessionalReportGenerator()
    return generator.generate_executive_report(_test_state(company, claim))


def test_section3_has_factor_rows():
    report = generate_test_report("BP", "BP net-zero by 2050")
    assert "No traceable factor rows" not in report


def test_section4_no_generic_fallback():
    report = generate_test_report("BP", "BP net-zero by 2050")
    assert "require direct inspection of the JSON export" not in report


def test_regulatory_score_consistency():
    scanner = RegulatoryHorizonScanner()
    claim = {"claim_id": "C1", "claim_text": "Net zero by 2050"}
    results = scanner.scan_regulatory_compliance("BP", claim, [], jurisdiction="Global")
    for data in results["compliance_results"]:
        has_gaps = len(data.get("gap_details", [])) > 0
        if data["status"] == "GAP FOUND":
            assert has_gaps, f"{data.get('regulation_name')}: GAP FOUND but 0 gap_details"
        if data["status"] == "COMPLIANT":
            assert not has_gaps, f"{data.get('regulation_name')}: COMPLIANT but has gap_details"


def test_contradiction_deterministic():
    analyzer = ContradictionAnalyzer()
    evidence = [{"stance": "Contradicts", "snippet": "Contradiction snippet", "source_name": "Reuters", "year": 2023}]
    counts = [
        analyzer.analyze_contradictions("BP", "BP net-zero by 2050", evidence)["contradictions_found"]
        for _ in range(3)
    ]
    assert len(set(counts)) == 1, f"Non-deterministic: {counts}"


def test_json_export_is_complete():
    state = _test_state("BP", "BP net-zero by 2050")
    state["evidence"] = state["evidence"] * 500
    generator = ProfessionalReportGenerator()
    metadata = {
        "report_id": f"TEST_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "analysis_date": datetime.utcnow().isoformat(),
        "report_confidence": "MEDIUM",
        "quality_warnings": [],
    }
    _, size = generator.generate_json_export(state, metadata)
    assert size > 10000, f"JSON export too small: {size} chars"


def test_source_name_not_agent_name():
    state = _test_state("BP", "BP net-zero by 2050")
    state["evidence"] += [
        {"source_name": "Reuters"},
        {"source_name": "Financial Times"},
    ]
    agent_names = ["realtime_news", "realtime_monitor", "evidence_retriever", "web_search"]
    for item in state["evidence"]:
        assert item.get("source_name") not in agent_names


def test_sentiment_not_none():
    analyzer = SentimentAnalyzer()
    results = analyzer.analyze_claim_language(
        {"claim_id": "C1", "claim_text": "We are a green company", "company": "BP"},
        [{"relevant_text": "The company faced criticism over fossil expansion."}],
    )
    assert results["claim_sentiment"] is not None
    assert results["evidence_sentiment"] is not None
