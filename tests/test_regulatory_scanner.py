"""
Unit tests for regulatory_scanner.py
"""
import pytest
from agents.regulatory_scanner import detect_regulation_gaps, calculate_compliance_score

def test_net_zero_without_sbti_creates_gap():
    result = detect_regulation_gaps(
        "TechCorp", "We will be carbon neutral by 2050", "Science Based Targets initiative")
    assert result["gap_count"] >= 1
    assert any("SBTi" in g or "Science Based Target" in g for g in result["gaps_found"])

def test_sbti_mention_no_gap():
    result = detect_regulation_gaps(
        "TechCorp", "Our 1.5°C SBTi validated target confirmed by Science Based Target initiative",
        "Science Based Targets initiative")
    assert result["gap_count"] == 0

def test_compliance_score_calculation():
    regulation_results = [
        {"regulation_name": "GRI", "gap_count": 0, "gaps_found": []},
        {"regulation_name": "CDP", "gap_count": 1, "gaps_found": ["missing CDP score"]},
        {"regulation_name": "SBTi", "gap_count": 0, "gaps_found": []},
        {"regulation_name": "GHG Protocol", "gap_count": 2, "gaps_found": ["a", "b"]}
    ]
    result = calculate_compliance_score(regulation_results)
    assert result["score"] == 26
    assert result["risk_level"] == "High"

def test_compliant_status_label():
    regulation_results = [{"regulation_name": "GRI", "gap_count": 0, "gaps_found": []}]
    result = calculate_compliance_score(regulation_results)
    assert result["per_regulation_status"][0]["status"] == "COMPLIANT"

def test_gap_found_status_label():
    regulation_results = [{"regulation_name": "CDP", "gap_count": 2, "gaps_found": ["missing", "missing2"]}]
    result = calculate_compliance_score(regulation_results)
    assert "GAP FOUND" in result["per_regulation_status"][0]["status"]
