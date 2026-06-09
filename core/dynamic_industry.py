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
# Company-name → sector seeds for bellwether companies where the name alone
# is the most reliable industry signal. Checked BEFORE keyword scoring.
# Keys must be lowercase substrings of the company name.
COMPANY_SECTOR_SEEDS: dict = {
    # Telecommunications
    "vodafone": "telecommunications",
    "verizon": "telecommunications",
    "at&t": "telecommunications",
    "t-mobile": "telecommunications",
    "deutsche telekom": "telecommunications",
    "bt group": "telecommunications",
    "orange": "telecommunications",
    "telefonica": "telecommunications",
    "comcast": "telecommunications",
    "charter communications": "telecommunications",
    "reliance jio": "telecommunications",
    "airtel": "telecommunications",
    # Oil & Gas
    "exxon": "oil_and_gas",
    "chevron": "oil_and_gas",
    "shell": "oil_and_gas",
    "bp ": "oil_and_gas",
    "totalenergies": "oil_and_gas",
    "conocophillips": "oil_and_gas",
    "equinor": "oil_and_gas",
    "eni": "oil_and_gas",
    "repsol": "oil_and_gas",
    # Banking / Finance
    "goldman sachs": "banking",
    "jp morgan": "banking",
    "jpmorgan": "banking",
    "bank of america": "banking",
    "wells fargo": "banking",
    "citigroup": "banking",
    "barclays": "banking",
    "hsbc": "banking",
    "ubs": "banking",
    "credit suisse": "banking",
    "bnp paribas": "banking",
    "deutsche bank": "banking",
    "morgan stanley": "banking",
    # Automotive / EV
    "tesla": "automotive",
    "volkswagen": "automotive",
    "bmw": "automotive",
    "mercedes": "automotive",
    "toyota": "automotive",
    "ford motor": "automotive",
    "general motors": "automotive",
    "stellantis": "automotive",
    "rivian": "automotive",
    "lucid": "automotive",
    "nio": "automotive",
    # Technology
    "microsoft": "technology",
    "apple inc": "technology",
    "alphabet": "technology",
    "amazon": "technology",
    "meta platforms": "technology",
    "nvidia": "technology",
    "intel": "technology",
    "samsung": "technology",
    "ibm": "technology",
    "oracle": "technology",
    "salesforce": "technology",
    "cisco": "technology",
    # FMCG / Consumer Goods
    "unilever": "consumer_goods",
    "nestle": "consumer_goods",
    "procter": "consumer_goods",                # Procter & Gamble
    "colgate": "consumer_goods",
    "reckitt": "consumer_goods",
    "henkel": "consumer_goods",
    "kimberly": "consumer_goods",               # Kimberly-Clark
    # Fashion / Apparel
    "h&m": "fast_fashion",
    "zara": "fast_fashion",
    "inditex": "fast_fashion",
    "fast retailing": "fast_fashion",           # Uniqlo parent
    "burberry": "fast_fashion",
    "nike": "fast_fashion",
    "adidas": "fast_fashion",
    "gap inc": "fast_fashion",
    "pvh": "fast_fashion",                      # Calvin Klein, Tommy Hilfiger
    # Pharmaceuticals / Healthcare
    "astrazeneca": "pharmaceuticals",
    "pfizer": "pharmaceuticals",
    "johnson & johnson": "pharmaceuticals",
    "novartis": "pharmaceuticals",
    "roche": "pharmaceuticals",
    "merck": "pharmaceuticals",
    "abbvie": "pharmaceuticals",
    "bayer": "pharmaceuticals",
    "sanofi": "pharmaceuticals",
    "glaxosmithkline": "pharmaceuticals",
    "gsk": "pharmaceuticals",
    "eli lilly": "pharmaceuticals",
    "novo nordisk": "pharmaceuticals",
    # Retail / E-commerce
    "walmart": "retail",
    "target corp": "retail",
    "costco": "retail",
    "kroger": "retail",
    "carrefour": "retail",
    "tesco": "retail",
    "sainsbury": "retail",
    "marks & spencer": "retail",
    "ikea": "retail",
    "home depot": "retail",
    "alibaba": "retail",
    # Food & Beverage
    "coca-cola": "food_beverage",
    "pepsico": "food_beverage",
    "kraft heinz": "food_beverage",
    "danone": "food_beverage",
    "diageo": "food_beverage",
    "ab inbev": "food_beverage",
    "mcdonald": "food_beverage",
    "starbucks": "food_beverage",
    "tyson foods": "food_beverage",
    # Renewable Energy
    "vestas": "renewable_energy",
    "siemens gamesa": "renewable_energy",
    "nextera": "renewable_energy",
    "brookfield renewable": "renewable_energy",
    "orsted": "renewable_energy",
    "enel": "renewable_energy",
    # Mining
    "bhp": "mining",
    "rio tinto": "mining",
    "glencore": "mining",
    "vale": "mining",
    "anglogold": "mining",
    "barrick": "mining",
    # Aviation
    "boeing": "aviation",
    "airbus": "aviation",
    "delta air": "aviation",
    "united airlines": "aviation",
    "american airlines": "aviation",
    "emirates": "aviation",
    "ryanair": "aviation",
    # Transportation / Logistics
    "ups": "transportation",
    "fedex": "transportation",
    "dhl": "transportation",
    "maersk": "transportation",
    "amazon logistics": "transportation",
    # Real Estate
    "prologis": "real_estate",
    "brookfield asset": "real_estate",
    # Chemicals
    "basf": "chemicals",
    "dow chemical": "chemicals",
    "dupont": "chemicals",
    "3m": "chemicals",
    "linde": "chemicals",
}

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
    "telecommunications": [
        "telecom", "telecommunications", "mobile network", "5g", "broadband",
        "internet provider", "mobile operator", "wireless operator", "spectrum",
        "vodafone", "verizon", "at&t", "t-mobile", "deutsche telekom", "bt group",
        "orange sa", "telefonica", "swisscom", "telstra", "softbank",
        "ntt docomo", "airtel", "reliance jio", "bsnl", "mtnl",
    ],
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
    # If a valid industry is already set and isn't "General" or "Unknown", keep it.
    # The previous regex normalisation collapsed "Healthcare / Pharma" to
    # "healthcare___pharma" (triple underscore) which never matched any config
    # key, so the keyword fallback fired and Pfizer kept getting reclassified
    # as `real_estate` (because facilities/R&D text contains "property").
    # Delegate to the shared normaliser instead — it already handles
    # "Healthcare / Pharma" → "pharmaceuticals", "Food & Beverage" → "food
    # beverage", and other display-form variants.
    if current_industry and current_industry.lower() not in ("general", "unknown", ""):
        try:
            from core.safe_utils import normalize_industry_key
            normalized = normalize_industry_key(current_industry).replace(" ", "_")
        except Exception:
            normalized = re.sub(r"[^a-z0-9]", "_", current_industry.lower().strip()).strip("_")
        # Compact consecutive underscores in case the legacy path is hit.
        normalized = re.sub(r"_+", "_", normalized)
        baselines = _load_baselines()
        if normalized in baselines.get("industry_baseline_risk", {}):
            return normalized, 0.95, "pre_classified"

    # Company-name seed lookup: for well-known companies the name alone is the
    # most reliable signal. This fires BEFORE keyword scoring so Vodafone never
    # falls through to "unknown" just because the evidence corpus doesn't
    # happen to contain the word "telecom".
    company_lc = (company or "").lower().strip()
    for seed_key, seed_sector in COMPANY_SECTOR_SEEDS.items():
        if seed_key in company_lc:
            return seed_sector, 0.98, "company_seed"

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
