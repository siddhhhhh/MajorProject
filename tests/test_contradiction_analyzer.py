"""
Unit tests for contradiction_analyzer.py and known_cases.py
"""
import pytest
from data.known_cases import get_known_contradictions
from agents.contradiction_analyzer import analyze_contradictions

def test_bp_net_zero_returns_contradiction():
    result = get_known_contradictions("BP", "We aim to be a net zero company by 2050")
    assert len(result) >= 1
    assert result[0]["severity"] == "high"
    assert result[0]["confidence"] == "HIGH"

def test_shell_net_zero_returns_contradiction():
    result = get_known_contradictions("Shell", "Shell aims to be net-zero emissions by 2050")
    assert len(result) >= 1

def test_infosys_returns_no_contradiction():
    result = get_known_contradictions("Infosys", "Infosys has been carbon neutral since 2020")
    assert len(result) == 0  # Infosys has no known greenwashing cases

def test_case_insensitive_matching():
    result = get_known_contradictions("SHELL", "net zero renewable energy")
    assert len(result) >= 1

def test_analyze_contradictions_returns_dict():
    result = analyze_contradictions(
        "We will be net zero by 2050", "BP", [])
    assert "contradictions" in result
    assert "controversy_count" in result
    assert result["controversy_count"] >= 1


def test_analyze_contradictions_is_deterministic_for_same_input():
    claim = "We will be net zero by 2050"
    company = "BP"
    evidence = []

    r1 = analyze_contradictions(claim, company, evidence)
    r2 = analyze_contradictions(claim, company, evidence)
    r3 = analyze_contradictions(claim, company, evidence)

    assert r1["controversy_count"] == r2["controversy_count"] == r3["controversy_count"]
    assert r1["assessment"] == r2["assessment"] == r3["assessment"]
