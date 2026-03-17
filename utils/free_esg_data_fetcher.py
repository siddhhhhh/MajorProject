"""
Free ESG Data Fetcher Utilities
------------------------------
Fetches ESG and climate scores from Wikirate and CDP public APIs with caching.
All requests are free, public, and have a 7-day cache TTL.
"""
import os
import json
import time
import hashlib
from typing import Optional, Dict
import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
PEER_CACHE = os.path.join(CACHE_DIR, "peer_data")
CDP_CACHE = os.path.join(CACHE_DIR, "cdp_data")
SEARCH_CACHE = os.path.join(CACHE_DIR, "search")
CACHE_TTL = 7 * 24 * 3600  # 7 days in seconds
os.makedirs(PEER_CACHE, exist_ok=True)
os.makedirs(CDP_CACHE, exist_ok=True)
os.makedirs(SEARCH_CACHE, exist_ok=True)

def _cache_get(path: str) -> Optional[dict]:
    if os.path.exists(path):
        if time.time() - os.path.getmtime(path) < CACHE_TTL:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return None

def _cache_set(path: str, data: dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def fetch_wikirate_esg_score(company_name: str) -> Optional[Dict]:
    """
    Fetches ESG data from Wikirate public API.
    Returns dict with keys: e_score, s_score, g_score, overall_score, year, source
    Returns None if not found or error.
    """
    fname = os.path.join(PEER_CACHE, f"{company_name.replace(' ', '_')}.json")
    cached = _cache_get(fname)
    if cached:
        return cached
    endpoints = [
        f"https://wikirate.org/{company_name.replace(' ', '_')}+ESG_Score.json",
        f"https://wikirate.org/Company+ESG_Score.json?filter[company_name]={company_name}&limit=5",
    ]
    for url in endpoints:
        try:
            resp = requests.get(url, timeout=10, headers={"Accept": "application/json"})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    latest = sorted(data, key=lambda x: x.get('year', 0))[-1]
                    result = {
                        "overall_score": latest.get('value', None),
                        "year": latest.get('year', None),
                        "source": "Wikirate"
                    }
                    _cache_set(fname, result)
                    return result
                elif isinstance(data, dict) and "value" in data:
                    result = {
                        "overall_score": data["value"],
                        "year": data.get("year"),
                        "source": "Wikirate"
                    }
                    _cache_set(fname, result)
                    return result
        except Exception:
            continue
    return None

def fetch_cdp_score(company_name: str) -> Optional[Dict]:
    """
    Fetches CDP climate score from CDP open data.
    Returns dict with: cdp_score (letter), cdp_numeric (float), year, source
    Returns None if not found.
    """
    fname = os.path.join(CDP_CACHE, f"{company_name.replace(' ', '_')}.json")
    cached = _cache_get(fname)
    if cached:
        return cached
    CDP_SCORE_MAP = {
        "A": 95, "A-": 88, "B": 75, "B-": 65, "C": 50, "D": 30, "D-": 20, "F": 10
    }
    try:
        url = f"https://data.cdp.net/resource/scores.json?organization_name={company_name}&$limit=5"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                latest = sorted(data, key=lambda x: x.get('year', '0'))[-1]
                score_letter = latest.get('climate_change_score', latest.get('score', None))
                if score_letter:
                    result = {
                        "cdp_score": score_letter,
                        "cdp_numeric": CDP_SCORE_MAP.get(score_letter.upper(), 50),
                        "year": latest.get('year'),
                        "source": "CDP"
                    }
                    _cache_set(fname, result)
                    return result
    except Exception:
        pass
    # Fallback: DuckDuckGo search
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={company_name}+CDP+score+climate+rating&format=json&no_html=1"
        resp = requests.get(ddg_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            abstract = data.get("AbstractText", "") + " ".join(
                t.get("Text", "") for t in data.get("RelatedTopics", [])[:3])
            import re
            cdp_match = re.search(r'CDP\\s+(?:score|rating|grade)[:\\s]+([A-F][+-]?)', abstract, re.IGNORECASE)
            if cdp_match:
                score_letter = cdp_match.group(1)
                result = {
                    "cdp_score": score_letter,
                    "cdp_numeric": CDP_SCORE_MAP.get(score_letter.upper(), 50),
                    "year": "est.",
                    "source": "CDP (web)"
                }
                _cache_set(fname, result)
                return result
    except Exception:
        pass
    return None

def fetch_duckduckgo_search(query: str) -> Optional[Dict]:
    """
    Fetches DuckDuckGo search results and caches by query hash.
    Returns dict or None.
    """
    h = hashlib.sha256(query.encode("utf-8")).hexdigest()
    fname = os.path.join(SEARCH_CACHE, f"{h}.json")
    cached = _cache_get(fname)
    if cached:
        return cached
    try:
        url = f"https://api.duckduckgo.com/?q={requests.utils.quote(query)}&format=json&no_html=1&skip_disambig=1"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            _cache_set(fname, data)
            return data
    except Exception:
        pass
    return None

if __name__ == "__main__":
    print(fetch_wikirate_esg_score("BP"))
    print(fetch_cdp_score("Shell"))
    print(fetch_duckduckgo_search("Shell greenwashing ruling"))
