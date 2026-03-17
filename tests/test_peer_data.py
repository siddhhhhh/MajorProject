"""
Unit tests for free_esg_data_fetcher and peer data logic
"""
import pytest
from utils.free_esg_data_fetcher import fetch_wikirate_esg_score, fetch_cdp_score
from agents.industry_comparator import get_peer_scores

def test_fetch_wikirate_esg_score():
    result = fetch_wikirate_esg_score("BP")
    assert result is None or "overall_score" in result

def test_fetch_cdp_score():
    result = fetch_cdp_score("Shell")
    assert result is None or "cdp_score" in result

def test_get_peer_scores_real_and_estimated():
    peers = get_peer_scores("BP", "Energy")
    assert isinstance(peers, list)
    assert len(peers) > 0
    for peer in peers:
        assert "company" in peer
        assert "esg_score" in peer
        assert "source" in peer
        assert "is_estimated" in peer
