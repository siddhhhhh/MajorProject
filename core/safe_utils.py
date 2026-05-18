"""
Safe utility functions for ESG report generation.
Prevents NoneType crashes through defensive dict access and type coercion.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def safe_get(d: Any, *keys, default=None) -> Any:
    """Safely traverse nested dicts/objects.

    >>> safe_get({"a": {"b": 3}}, "a", "b")
    3
    >>> safe_get(None, "a", "b", default=0)
    0
    >>> safe_get({"a": None}, "a", "b", default="x")
    'x'
    """
    current = d
    for key in keys:
        if current is None:
            return default
        if isinstance(current, dict):
            current = current.get(key)
        elif hasattr(current, key):
            current = getattr(current, key, None)
        else:
            return default
    return current if current is not None else default


def safe_number(val: Any, default: float = 0.0) -> float:
    """Coerce a value to float, returning *default* on failure.

    >>> safe_number("42.5")
    42.5
    >>> safe_number(None)
    0.0
    >>> safe_number("N/A", default=-1.0)
    -1.0
    """
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    """Coerce a value to int, returning *default* on failure."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Source name extraction
# ---------------------------------------------------------------------------

DOMAIN_PUBLISHER_MAP = {
    "cnbc.com": "CNBC",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "ft.com": "Financial Times",
    "wsj.com": "Wall Street Journal",
    "nytimes.com": "New York Times",
    "economictimes.indiatimes.com": "Economic Times",
    "business-standard.com": "Business Standard",
    "livemint.com": "Livemint",
    "thehindubusinessline.com": "The Hindu BusinessLine",
    "moneycontrol.com": "Moneycontrol",
    "financialpost.com": "Financial Post",
    "cdp.net": "CDP (Carbon Disclosure Project)",
    "wri-india.org": "World Resources Institute India",
    "downtoearth.org.in": "Down To Earth",
    "sebi.gov.in": "SEBI",
    "mca.gov.in": "Ministry of Corporate Affairs",
    "rbi.org.in": "Reserve Bank of India",
    "envfor.nic.in": "Ministry of Environment",
    "msn.com": "MSN",
    "bbc.com": "BBC",
    "bbc.co.uk": "BBC",
    "theguardian.com": "The Guardian",
    "forbes.com": "Forbes",
    "fortune.com": "Fortune",
    "sciencebasedtargets.org": "SBTi",
    "unpri.org": "UN PRI",
    "globalreporting.org": "GRI",
    "sec.gov": "SEC",
    "epa.gov": "EPA",
    "europa.eu": "European Commission",
    "ec.europa.eu": "European Commission",
    "bseindia.com": "BSE India",
    "nseindia.com": "NSE India",
    "yahoo.com": "Yahoo Finance",
    "google.com": "Google News",
}

# Reliability tiers: domain -> (tier_number, tier_score)
_TIER1_DOMAINS = {
    "cdp.net", "globalreporting.org", "sebi.gov.in", "mca.gov.in",
    "envfor.nic.in", "sec.gov", "epa.gov", "europa.eu", "ec.europa.eu",
    "bseindia.com", "nseindia.com", "sciencebasedtargets.org", "rbi.org.in",
}
_TIER2_DOMAINS = {
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "nytimes.com",
    "economictimes.indiatimes.com", "business-standard.com", "livemint.com",
}
_TIER3_DOMAINS = {
    "cnbc.com", "thehindubusinessline.com", "moneycontrol.com",
    "bbc.com", "bbc.co.uk", "theguardian.com", "forbes.com", "fortune.com",
}
_EXCLUDED_DOMAINS = {
    "news.google.com",
}


def parse_source_name(url: str) -> str:
    """Extract human-readable publisher name from a URL.

    Falls back to 'Web source' — never returns 'Unknown'.

    >>> parse_source_name("https://reuters.com/article/xyz")
    'Reuters'
    >>> parse_source_name("https://unknown-site.org/page")
    'Web source'
    """
    if not url:
        return "Web source"

    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return "Web source"

    hostname = hostname.lower().lstrip("www.")

    # Direct match
    if hostname in DOMAIN_PUBLISHER_MAP:
        return DOMAIN_PUBLISHER_MAP[hostname]

    # Check subdomains (e.g. "in.reuters.com" -> reuters.com)
    for domain, name in DOMAIN_PUBLISHER_MAP.items():
        if hostname.endswith("." + domain) or hostname == domain:
            return name

    return "Web source"


def get_reliability_tier(url: str) -> int:
    """Return reliability tier (1=highest, 4=lowest, 0=excluded).

    >>> get_reliability_tier("https://cdp.net/report")
    1
    >>> get_reliability_tier("https://reuters.com/article")
    2
    >>> get_reliability_tier("https://random-blog.com/post")
    4
    """
    if not url:
        return 4

    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return 4

    hostname = hostname.lower().lstrip("www.")

    # Check excluded
    for d in _EXCLUDED_DOMAINS:
        if hostname == d or hostname.endswith("." + d):
            return 0

    # Check tiers
    for d in _TIER1_DOMAINS:
        if hostname == d or hostname.endswith("." + d):
            return 1
    for d in _TIER2_DOMAINS:
        if hostname == d or hostname.endswith("." + d):
            return 2
    for d in _TIER3_DOMAINS:
        if hostname == d or hostname.endswith("." + d):
            return 3

    return 4


def get_reliability_score(tier: int) -> float:
    """Convert tier number to 0-1 reliability score."""
    return {1: 1.0, 2: 0.8, 3: 0.6, 4: 0.3, 0: 0.0}.get(tier, 0.3)


# ---------------------------------------------------------------------------
# Null-safe rendering helpers
# ---------------------------------------------------------------------------

def safe_render_indicator(indicator: dict) -> dict:
    """Render a sub-indicator safely with placeholders for missing fields.

    Rules:
    - If score is None -> display_score="N/A", data_missing=True
    - If raw_value is None -> display_value="Not disclosed"
    - If source_url is None -> source_label="No source"
    - Never raise AttributeError regardless of input shape
    - render_quality in {"full", "partial", "empty"}
    """
    row: Dict[str, Any] = dict(indicator) if isinstance(indicator, dict) else {}

    score = row.get("score")
    raw_value = row.get("raw_value")
    source_url = row.get("source_url")

    # Preserve row when complete; add display/accessory fields only when needed.
    has_score = score is not None
    has_raw_value = raw_value is not None
    has_source = source_url is not None and str(source_url).strip() != ""

    if not has_score:
        row["display_score"] = "N/A"
        row["data_missing"] = True

    if not has_raw_value:
        row["display_value"] = "Not disclosed"

    if not has_source:
        row["source_label"] = "No source"

    # Determine render quality from key field coverage.
    present_count = sum([has_score, has_raw_value, has_source])
    if present_count == 3:
        row["render_quality"] = "full"
    elif present_count == 0:
        row["render_quality"] = "empty"
    else:
        row["render_quality"] = "partial"

    return row


def safe_render_pillar(pillar: dict) -> dict:
    """Render a pillar safely by normalizing and scoring sub-indicators.

    - Applies safe_render_indicator to each sub-indicator
    - Computes pillar score from non-null indicator scores only
    - Adds coverage_pct and score_reliable flag (True when coverage >= 60%)
    """
    p: Dict[str, Any] = dict(pillar) if isinstance(pillar, dict) else {}

    raw_subs = p.get("sub_indicators")
    if not isinstance(raw_subs, list):
        raw_subs = []

    rendered: List[Dict[str, Any]] = [safe_render_indicator(ind) for ind in raw_subs]
    p["sub_indicators"] = rendered

    # Use only scored indicators for pillar score.
    scored_rows = [ind for ind in rendered if isinstance(ind.get("score"), (int, float))]
    scored_count = len(scored_rows)
    total_count = len(rendered)

    pillar_score: Any = None
    if scored_count > 0:
        weighted_rows = [
            ind
            for ind in scored_rows
            if isinstance(ind.get("weight"), (int, float)) and float(ind.get("weight")) > 0
        ]

        if weighted_rows:
            total_weight = sum(float(ind.get("weight")) for ind in weighted_rows)
            if total_weight > 0:
                weighted_sum = sum(float(ind.get("score")) * float(ind.get("weight")) for ind in weighted_rows)
                pillar_score = round(weighted_sum / total_weight, 2)
        if pillar_score is None:
            pillar_score = round(
                sum(float(ind.get("score")) for ind in scored_rows) / scored_count,
                2,
            )

    p["score"] = pillar_score if pillar_score is not None else "N/A"

    coverage_ratio = (scored_count / total_count) if total_count > 0 else 0.0
    p["coverage_pct"] = f"{scored_count}/{total_count} indicators scored ({coverage_ratio * 100:.1f}%)"
    p["score_reliable"] = coverage_ratio >= 0.60

    # Pillar-level quality summary.
    if total_count == 0:
        p["render_quality"] = "empty"
    elif scored_count == total_count:
        p["render_quality"] = "full"
    else:
        p["render_quality"] = "partial"

    return p


def normalize_industry_label(raw: Any) -> str:
    """Convert internal industry key to a user-facing display label."""
    text = str(raw or "general").strip()
    key = text.lower().replace("_", " ").replace("&", " and ")
    key = " ".join(key.split())

    display_labels = {
        "oil and gas": "Oil & Gas",
        "energy": "Energy",
        "banking": "Banking",
        "financial services": "Financial Services",
        "consumer goods": "Consumer Goods",
        "fmcg": "Consumer Goods",
        "technology": "Technology",
        "healthcare": "Healthcare",
        "manufacturing": "Manufacturing",
        "automotive": "Automotive",
        "retail": "Retail",
        "utilities": "Utilities",
        "general": "General",
    }
    return display_labels.get(key, text.replace("_", " ").title())


def normalize_industry_key(raw: Any) -> str:
    """Convert display/internal industry values to a canonical persistence key.

    Returned form is space-separated, all-lowercase, no "&" / "_" / slashes.
    Downstream `industry_comparator.py` does ``.replace(' ', '_')`` on this
    value to derive the snake_case key it uses against industry_baselines.json
    (e.g. ``food_beverage``, ``pharmaceuticals``). Keep aliases in sync with
    BOTH ``data/peer_database.json`` keys (space-form) and
    ``config/industry_baselines.json`` keys (underscore-form).
    """
    key = str(raw or "general").strip().lower().replace("_", " ").replace("&", " and ")
    # Strip slashes (so "Healthcare / Pharma" -> "healthcare   pharma" -> "healthcare pharma")
    key = key.replace("/", " ").replace("\\", " ")
    key = " ".join(key.split())

    aliases = {
        "oil and gas": "oil & gas",
        "energy": "oil & gas",
        "banking": "banking",
        "financial services": "banking",
        "consumer goods": "consumer goods",
        "fmcg": "consumer goods",
        "technology": "technology",
        "healthcare": "healthcare",
        "manufacturing": "manufacturing",
        "automotive": "automotive",
        "retail": "retail",
        "utilities": "utilities",
        "general": "general",
        # Food & Beverage variants (Nestle case)
        "food and beverage": "food beverage",
        "food beverage": "food beverage",
        "f and b": "food beverage",
        "beverage": "food beverage",
        "food": "food beverage",
        # Pharma variants (Pfizer case). Map "Healthcare / Pharma" and
        # "Pharmaceuticals" to the same key so peer_database.json
        # "pharmaceuticals" cohort + industry_baselines.json
        # "pharmaceuticals" config both resolve.
        "pharma": "pharmaceuticals",
        "pharmaceuticals": "pharmaceuticals",
        "pharmaceutical": "pharmaceuticals",
        "healthcare pharma": "pharmaceuticals",
        "healthcare and pharma": "pharmaceuticals",
        "pharma and biotech": "pharmaceuticals",
        "biotech": "pharmaceuticals",
        # Telecom / IT services normalisation
        "telecom": "telecom",
        "telecommunications": "telecom",
        "it services": "it services",
        "it": "it services",
    }
    return aliases.get(key, key)
