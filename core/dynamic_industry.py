"""
core/dynamic_industry.py
--------------------------
Fixes Problem #10 (No Context Awareness)

Replaces hardcoded 25-company industry lookup with dynamic classification:
  - Keyword-based sector signals from claim/evidence text
  - Fallback to industry_baselines.json sector list
  - Geographic context detection for regulatory mapping
"""
from __future__ import annotations
import json, os, re, logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASELINES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "industry_baselines.json")

# Sector signal keywords (no company names — fully dynamic)
SECTOR_SIGNALS = {
    "oil_and_gas": ["petroleum", "crude oil", "natural gas", "drilling", "refinery", "upstream", "downstream", "lng", "pipeline", "fossil fuel"],
    "coal": ["coal mining", "coal power", "thermal coal", "metallurgical coal"],
    "mining": ["mining", "mineral", "ore", "tailings", "smelting", "copper", "gold mine", "lithium", "nickel"],
    "automotive": ["automobile", "automotive", "vehicle", "ev manufacturer", "car maker", "electric vehicle", "auto parts"],
    "aviation": ["airline", "aviation", "aircraft", "aerospace", "flight", "airport"],
    "banking": ["bank", "banking", "financial services", "lending", "mortgage", "credit", "deposits", "fintech"],
    "technology": ["technology", "tech company", "semiconductor", "hardware", "data center", "cloud computing", "ai company"],
    "software": ["software", "saas", "platform", "app developer", "digital services"],
    "consumer_goods": ["consumer goods", "fmcg", "household products", "personal care", "cosmetics"],
    "food_beverage": ["food", "beverage", "restaurant", "agriculture", "dairy", "meat", "packaged food"],
    "fast_fashion": ["fashion", "apparel", "clothing", "textile", "garment", "retail fashion"],
    "retail": ["retail", "e-commerce", "marketplace", "online store", "supermarket", "grocery"],
    "pharmaceuticals": ["pharmaceutical", "pharma", "drug", "biotech", "clinical trial", "medicine"],
    "chemicals": ["chemical", "petrochemical", "agrochemical", "fertilizer", "polymer"],
    "real_estate": ["real estate", "property", "reit", "construction", "building", "housing"],
    "telecommunications": ["telecom", "telecommunications", "mobile network", "5g", "broadband", "internet provider"],
    "renewable_energy": ["solar", "wind energy", "renewable", "clean energy", "green energy", "wind farm", "solar farm"],
    "healthcare_services": ["healthcare", "hospital", "medical", "health services", "clinic"],
    "tobacco": ["tobacco", "cigarette", "nicotine", "vaping"],
    "defense": ["defense", "defence", "military", "weapons", "arms manufacturer"],
    "transportation": ["shipping", "logistics", "freight", "railway", "transport", "trucking"],
    "hospitality": ["hotel", "hospitality", "tourism", "resort", "travel"],
    "education": ["education", "university", "school", "e-learning", "edtech"],
}

# Geographic signal keywords for regulatory context
GEO_SIGNALS = {
    "india": ["india", "indian", "bse", "nse", "sebi", "mca", "brsr", "nifty", "sensex", "mumbai", "delhi", "rupee"],
    "us": ["united states", "sec", "nyse", "nasdaq", "ftc", "epa", "dollar", "wall street", "10-k", "10-q"],
    "eu": ["european", "eu", "gdpr", "csrd", "sfdr", "taxonomy regulation", "euro", "brussels"],
    "uk": ["united kingdom", "fca", "companies house", "london stock exchange", "ftse", "pound", "sterling"],
    "australia": ["australia", "asx", "asic", "accc", "australian"],
    "china": ["china", "chinese", "shanghai", "shenzhen", "hong kong", "hkex"],
}


def detect_industry(
    company: str,
    claim: str = "",
    evidence_text: str = "",
    current_industry: str = "",
) -> Tuple[str, float, str]:
    """
    Dynamically detect industry from available text signals.
    
    Returns (industry_key, confidence, method)
    """
    # If a valid industry is already set and isn't "General" or "Unknown", keep it
    if current_industry and current_industry.lower() not in ("general", "unknown", ""):
        normalized = re.sub(r"[^a-z0-9]", "_", current_industry.lower().strip()).strip("_")
        # Verify it's a known sector
        baselines = _load_baselines()
        if normalized in baselines.get("industry_baseline_risk", {}):
            return normalized, 0.95, "pre_classified"

    # Build text corpus for matching
    corpus = f"{company} {claim} {evidence_text}".lower()

    # Score each sector
    scores = {}
    for sector, keywords in SECTOR_SIGNALS.items():
        score = sum(1 for kw in keywords if kw in corpus)
        if score > 0:
            scores[sector] = score

    if not scores:
        return "unknown", 0.3, "no_signals"

    # Best match
    best_sector = max(scores, key=scores.get)
    best_score = scores[best_sector]
    confidence = min(0.95, 0.5 + best_score * 0.1)

    return best_sector, round(confidence, 2), "keyword_detection"


def detect_geography(
    company: str,
    claim: str = "",
    evidence_text: str = "",
) -> Tuple[str, float]:
    """Detect primary geographic context for regulatory mapping."""
    corpus = f"{company} {claim} {evidence_text}".lower()

    scores = {}
    for geo, keywords in GEO_SIGNALS.items():
        score = sum(1 for kw in keywords if kw in corpus)
        if score > 0:
            scores[geo] = score

    if not scores:
        return "global", 0.3

    best = max(scores, key=scores.get)
    confidence = min(0.9, 0.4 + scores[best] * 0.1)
    return best, round(confidence, 2)


def get_regulatory_context(geography: str) -> Dict[str, Any]:
    """Get applicable regulatory frameworks for a geography."""
    frameworks = {
        "india": {"primary": ["BRSR", "SEBI ESG"], "secondary": ["Companies Act 2013", "CPCB", "NGT"], "esg_standard": "BRSR"},
        "us": {"primary": ["SEC Climate Disclosure", "FTC Green Guides"], "secondary": ["EPA", "DOJ Environmental"], "esg_standard": "SEC"},
        "eu": {"primary": ["CSRD", "SFDR", "EU Taxonomy"], "secondary": ["NFRD", "Green Claims Directive"], "esg_standard": "CSRD"},
        "uk": {"primary": ["TCFD (mandatory)", "SDR", "FCA ESG"], "secondary": ["Companies House", "UK Green Taxonomy"], "esg_standard": "TCFD"},
        "australia": {"primary": ["ASIC Greenwashing", "ACCC"], "secondary": ["ASX Corporate Governance"], "esg_standard": "ASIC"},
        "china": {"primary": ["CSRC ESG Guidelines"], "secondary": ["CBIRC Green Finance"], "esg_standard": "CSRC"},
        "global": {"primary": ["GRI", "CDP", "TCFD", "SBTi"], "secondary": ["ISSB/IFRS S1/S2", "TNFD"], "esg_standard": "GRI/ISSB"},
    }
    return frameworks.get(geography, frameworks["global"])


def _load_baselines() -> dict:
    try:
        with open(BASELINES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
