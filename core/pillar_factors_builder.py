"""
Pillar Factors Builder — Populates ESG sub-indicator breakdowns.

Produces a structured dict with per-pillar sub-indicators, weights,
data sources, and scores.  The weighted average of sub-indicator scores
is guaranteed to reproduce the given pillar score (via rescaling).

Industry-specific sub-indicators are added based on sector verticals.

Risk Mitigation #1 — Strict Factor Contract:
    Every factor MUST conform to the FactorResult schema.  If extraction
    fails the schema, the factor gracefully degrades to 'No Disclosure'
    rather than breaking the pipeline or hallucinating a score.
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
from core.safe_utils import safe_get, safe_number, parse_source_name, get_reliability_tier

# ============================================================
# FIX BUG2: Source-name → tier overrides for injected report
# chunks.  get_reliability_tier() operates on URL only; chunks
# from report_parser arrive with url="" so they default to
# tier 4.  This map corrects that for known authoritative
# source labels, pushing policy fallback 20 → 40.
# ============================================================
_SOURCENAME_TIER_OVERRIDES: Dict[str, int] = {
    # Report parser default labels
    "Primary ESG Report":    2,
    "Company Annual Report": 2,
    "Annual Report":         2,
    "Proxy Statement":       1,
    "ESG Report":            2,
    "Integrated Report":     2,
    "Sustainability Report": 2,
    "TCFD Report":           2,
    "Company Report (parsed)": 2,
    # SEC DEF14A variants
    "sec def14a":            1,
    "sec_def14a":            1,
    "def14a":                1,
    "sec proxy":             1,
    "sec filing":            1,
    "edgar":                 1,
    # CDP variants
    "cdp":                   1,
    "carbon disclosure project": 1,
    "cdp report":            1,
    "cdp climate change":    1,
    "cdp climate change questionnaire": 1,
    # GRI/SASB/TCFD
    "gri":                   2,
    "sasb":                  2,
    "tcfd":                  2,
}
# ============================================================


# =========================================================================
# Pydantic FactorResult Contract  (Risk Mitigation #1)
# =========================================================================

class FactorResult(BaseModel):
    """Strict contract for every scored factor.  Any extraction that cannot
    populate these fields falls back to data_quality='No Disclosure'."""
    name: str
    score: Optional[float] = Field(None, ge=0, le=100)
    weight: float = Field(..., ge=0, le=1)
    data_source: str = "Insufficient data"
    source_url: Optional[str] = None
    data_year: Optional[int] = None
    data_tier: int = Field(4, ge=1, le=4)
    data_quality: str = "No Disclosure"  # Verified / Estimated / Unverified / No Disclosure
    methodology: Optional[str] = None
    raw_value: Optional[str] = None
    unit: Optional[str] = None
    verified: bool = False
    primary_metric: Optional[str] = None
    metric_source_hint: Optional[str] = None
    gri_alignment: List[str] = Field(default_factory=list)
    sasb_alignment: List[str] = Field(default_factory=list)
    scoring_model: str = "keyword_heuristic_v1"
    contribution: Optional[float] = None  # score * weight, filled after scoring

    @validator("data_quality", always=True)
    def _infer_data_quality(cls, v, values):
        """If data_quality is not explicitly set, derive from data_tier."""
        if v and v != "No Disclosure":
            return v
        tier = values.get("data_tier", 4)
        return {1: "Verified", 2: "Estimated", 3: "Estimated", 4: "Unverified"}.get(tier, "No Disclosure")


def _to_factor_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a raw factor dict through the Pydantic contract.
    If validation fails, return a safe 'No Disclosure' fallback."""
    try:
        # Determine data_tier from the raw dict if not already set
        tier = raw.get("data_tier")
        if tier is None:
            # Infer from source reliability
            verified = raw.get("verified", False)
            scoring_model = raw.get("scoring_model", "")
            if verified and scoring_model == "structured_threshold_v1":
                tier = 1
            elif verified:
                tier = 2
            elif scoring_model == "structured_threshold_v1":
                tier = 2
            elif raw.get("score") is not None:
                tier = 3
            else:
                tier = 4
            raw["data_tier"] = tier

        # Determine data_quality
        if "data_quality" not in raw or raw["data_quality"] == "No Disclosure":
            if raw.get("score") is None:
                raw["data_quality"] = "No Disclosure"
            else:
                raw["data_quality"] = {1: "Verified", 2: "Estimated", 3: "Estimated", 4: "Unverified"}.get(tier, "Unverified")

        # Fill contribution
        if raw.get("score") is not None and raw.get("weight") is not None:
            raw["contribution"] = round(raw["score"] * raw["weight"], 2)

        result = FactorResult(**raw)
        return result.dict()
    except Exception:
        # Graceful degradation — Risk Mitigation #1
        return {
            "name": raw.get("name", "Unknown Factor"),
            "score": None,
            "weight": raw.get("weight", 0.0),
            "data_source": "Schema validation failed",
            "source_url": None,
            "data_year": None,
            "data_tier": 4,
            "data_quality": "No Disclosure",
            "methodology": None,
            "raw_value": None,
            "unit": None,
            "verified": False,
            "primary_metric": None,
            "metric_source_hint": None,
            "gri_alignment": [],
            "sasb_alignment": [],
            "scoring_model": "fallback",
            "contribution": None,
        }


# =========================================================================
# Sub-indicator definitions
# =========================================================================

# Default sub-indicators per pillar (used when no industry-specific set applies)

_DEFAULT_ENVIRONMENTAL = [
    {"name": "GHG Emissions Intensity",           "weight": 0.25, "keywords": ["emission", "ghg", "co2", "carbon", "scope 1", "scope 2", "tco2"]},
    {"name": "Scope 3 Coverage",                  "weight": 0.15, "keywords": ["scope 3", "value chain", "upstream", "downstream", "supply chain emission"]},
    {"name": "Renewable Energy Transition",        "weight": 0.20, "keywords": ["renewable", "solar", "wind", "clean energy", "green energy", "transition"]},
    {"name": "Water Usage & Stress",               "weight": 0.17, "keywords": ["water", "water stress", "water consumption", "effluent", "wastewater"]},
    {"name": "Biodiversity & Land Use",            "weight": 0.13, "keywords": ["biodiversity", "deforestation", "land use", "ecosystem", "habitat"]},
    {"name": "Waste & Circular Economy",           "weight": 0.10, "keywords": ["waste", "recycling", "circular economy", "landfill", "hazardous waste"]},
]

_DEFAULT_SOCIAL = [
    {"name": "Employee Health & Safety",           "weight": 0.25, "keywords": ["safety", "health", "occupational", "injury", "ltifr", "fatality"]},
    {"name": "Labor Rights & Fair Wages",          "weight": 0.25, "keywords": ["labor", "wage", "minimum wage", "fair wage", "working condition"]},
    {"name": "Community Impact & CSR Spend",       "weight": 0.20, "keywords": ["community", "csr", "social responsibility", "philanthropy", "donation"]},
    {"name": "Supply Chain Labor Standards",       "weight": 0.15, "keywords": ["supply chain", "child labor", "forced labor", "supplier audit", "vendor"]},
    {"name": "Diversity, Equity & Inclusion",      "weight": 0.15, "keywords": ["diversity", "inclusion", "equity", "gender", "women", "dei"]},
]

_DEFAULT_GOVERNANCE = [
    {"name": "Board Independence",                 "weight": 0.20, "keywords": ["board independence", "independent director", "non-executive"]},
    {"name": "Board Diversity",                    "weight": 0.20, "keywords": ["board diversity", "women directors", "female directors", "diverse directors"]},
    {"name": "Executive Pay Ratio",                "weight": 0.20, "keywords": ["executive pay", "ceo pay", "pay ratio", "compensation ratio", "remuneration"]},
    {"name": "Anti-Corruption Policies",           "weight": 0.20, "keywords": ["anti-corruption", "bribery", "corruption", "ethics", "compliance"]},
    {"name": "Whistleblower Mechanisms",           "weight": 0.10, "keywords": ["whistleblower", "grievance", "reporting mechanism", "speak up"]},
    {"name": "ESG Disclosure Quality",             "weight": 0.10, "keywords": ["disclosure", "transparency", "reporting", "brsr", "gri", "tcfd"]},
]

# Industry-specific ADDITIONAL sub-indicators
_INDUSTRY_EXTRA = {
    "energy": {
        "environmental": [
            {"name": "Methane Leakage Rate",           "weight": 0.15, "keywords": ["methane", "leakage", "flaring", "fugitive emission"]},
            {"name": "Stranded Asset Risk",             "weight": 0.15, "keywords": ["stranded asset", "fossil fuel reserve", "unburnable carbon"]},
            {"name": "Carbon Capture Investment",       "weight": 0.10, "keywords": ["carbon capture", "ccs", "ccus", "sequestration"]},
            {"name": "Just Transition Programs",        "weight": 0.10, "keywords": ["just transition", "worker retraining", "community transition"]},
        ],
    },
    "oil & gas": {
        "environmental": [
            {"name": "Methane Leakage Rate",           "weight": 0.15, "keywords": ["methane", "leakage", "flaring", "fugitive emission"]},
            {"name": "Stranded Asset Risk",             "weight": 0.15, "keywords": ["stranded asset", "fossil fuel reserve", "unburnable carbon"]},
            {"name": "Carbon Capture Investment",       "weight": 0.10, "keywords": ["carbon capture", "ccs", "ccus", "sequestration"]},
            {"name": "Just Transition Programs",        "weight": 0.10, "keywords": ["just transition", "worker retraining", "community transition"]},
        ],
    },
    "manufacturing": {
        "environmental": [
            {"name": "Supply Chain Emissions",          "weight": 0.15, "keywords": ["supply chain emission", "scope 3", "upstream", "downstream"]},
            {"name": "Product End-of-Life",             "weight": 0.10, "keywords": ["end of life", "product recycling", "take-back", "product disposal"]},
            {"name": "Chemical Hazard Management",      "weight": 0.10, "keywords": ["chemical", "hazardous", "toxic", "reach", "chemical management"]},
        ],
    },
    "banking": {
        "environmental": [
            {"name": "Green Lending Ratio",             "weight": 0.15, "keywords": ["green loan", "green lending", "sustainable finance", "green bond"]},
            {"name": "Climate Risk in Loan Book",       "weight": 0.15, "keywords": ["climate risk", "loan book", "credit risk", "transition risk"]},
        ],
        "social": [
            {"name": "Financial Inclusion",             "weight": 0.15, "keywords": ["financial inclusion", "unbanked", "microfinance", "rural banking"]},
        ],
    },
    "nbfc": {
        "environmental": [
            {"name": "Green Lending Ratio",             "weight": 0.15, "keywords": ["green loan", "green lending", "sustainable finance"]},
            {"name": "Climate Risk in Loan Book",       "weight": 0.15, "keywords": ["climate risk", "loan book", "credit risk"]},
        ],
        "social": [
            {"name": "Financial Inclusion",             "weight": 0.15, "keywords": ["financial inclusion", "unbanked", "microfinance"]},
        ],
    },
    "financial services": {
        "environmental": [
            {"name": "Green Lending Ratio",             "weight": 0.15, "keywords": ["green loan", "green lending", "sustainable finance", "green bond"]},
            {"name": "Climate Risk in Loan Book",       "weight": 0.15, "keywords": ["climate risk", "loan book", "credit risk", "transition risk"]},
        ],
        "social": [
            {"name": "Financial Inclusion",             "weight": 0.15, "keywords": ["financial inclusion", "unbanked", "microfinance"]},
        ],
    },
    "technology": {
        "environmental": [
            {"name": "Data Center PUE",                 "weight": 0.12, "keywords": ["data center", "pue", "power usage effectiveness", "server"]},
            {"name": "E-Waste Policy",                  "weight": 0.10, "keywords": ["e-waste", "electronic waste", "device recycling"]},
        ],
        "governance": [
            {"name": "Algorithm Fairness / AI Ethics",  "weight": 0.15, "keywords": ["ai ethics", "algorithm fairness", "bias", "responsible ai"]},
        ],
    },
    "it": {
        "environmental": [
            {"name": "Data Center PUE",                 "weight": 0.12, "keywords": ["data center", "pue", "power usage effectiveness", "server"]},
            {"name": "E-Waste Policy",                  "weight": 0.10, "keywords": ["e-waste", "electronic waste", "device recycling"]},
        ],
        "governance": [
            {"name": "Algorithm Fairness / AI Ethics",  "weight": 0.15, "keywords": ["ai ethics", "algorithm fairness", "bias", "responsible ai"]},
        ],
    },
    "consumer goods": {
        "environmental": [
            {"name": "Packaging Recyclability",         "weight": 0.12, "keywords": ["packaging", "recyclable", "single-use plastic", "sustainable packaging"]},
        ],
        "social": [
            {"name": "Living Wage in Supply Chain",     "weight": 0.12, "keywords": ["living wage", "supply chain wage", "fair trade"]},
        ],
    },
    "retail": {
        "environmental": [
            {"name": "Packaging Recyclability",         "weight": 0.12, "keywords": ["packaging", "recyclable", "single-use plastic"]},
        ],
        "social": [
            {"name": "Living Wage in Supply Chain",     "weight": 0.12, "keywords": ["living wage", "supply chain wage", "fair trade"]},
        ],
    },
}


# Structured scoring rules to replace keyword-only scoring for selected indicators.
_STRUCTURED_SCORING_RULES: Dict[str, Dict[str, Any]] = {
    "Water Usage & Stress": {
        "primary_metric": "Water withdrawal/intensity disclosure",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 90.0,
            "above_average": 70.0,
            "average": 50.0,
            "below_average": 30.0,
        },
        "metric_patterns": [
            r"water[^.\n]{0,80}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"water[^.\n]{0,80}?(\d[\d,\.]+)\s*(?:million\s*m3|m3|m\^3|cubic\s*met(?:er|re)s?)",
        ],
        "claim_keywords": ["water", "water stress", "water usage", "wastewater", "withdrawal"],
        "policy_keywords": ["water policy", "water stewardship", "cdp water", "grI 303", "aqueduct"],
        "source_hint": "CDP Water, sustainability report environmental tables",
        "gri_alignment": ["GRI 303-1", "GRI 303-3"],
        "sasb_alignment": ["SASB IF-EU-140a.1"],
    },
    "ESG Disclosure Quality": {
        "primary_metric": "Disclosure completeness across carbon and verification controls",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 90.0,
            "above_average": 70.0,
            "average": 50.0,
            "below_average": 30.0,
        },
        "metric_patterns": [],
        "claim_keywords": ["disclosure", "transparency", "reporting", "gri", "tcfd", "sbti", "scope 3"],
        "policy_keywords": ["assurance", "verified", "audited", "methodology", "third-party"],
        "source_hint": "Integrated report + carbon disclosure completeness",
        "gri_alignment": ["GRI 2-1", "GRI 2-3"],
        "sasb_alignment": ["SASB CG-MR-000.A"],
    },
    "Board Diversity": {
        "primary_metric": "Board gender/diversity representation (%)",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 45.0,
            "above_average": 35.0,
            "average": 25.0,
            "below_average": 15.0,
        },
        "metric_patterns": [
            r"board diversity[^.\n]{0,50}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,60}board diversity",
            r"(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,60}(?:women|female|diverse)[^.\n]{0,40}board",
            r"(\d{1,2})\s+of\s+(\d{1,2})\s+(?:directors|board members)[^.\n]{0,40}(?:women|female|diverse)",
        ],
        "claim_keywords": ["board diversity", "women directors", "female directors", "diverse directors"],
        "policy_keywords": ["nominating committee", "board composition", "director nominee", "proxy statement"],
        "source_hint": "Proxy statement / annual report board composition disclosure",
        "gri_alignment": ["GRI 405-1"],
        "sasb_alignment": ["SASB CG-AA-330a.1"],
    },
    "Executive Pay Ratio": {
        "primary_metric": "CEO pay ratio",
        "metric_unit": "ratio",
        "direction": "lower_better",
        "thresholds": {
            "top_decile": 100.0,
            "above_average": 150.0,
            "average": 250.0,
            "below_average": 400.0,
        },
        "metric_patterns": [
            r"pay ratio[^0-9]{0,30}(\d{1,4})\s*(?::|to)\s*1",
            r"ceo pay ratio[^0-9]{0,30}(\d{1,4})\s*(?::|to)\s*1",
            r"ratio of the annual total compensation[^0-9]{0,60}(\d{1,4})\s*(?::|to)\s*1",
        ],
        "claim_keywords": ["executive pay", "ceo pay", "pay ratio", "compensation ratio", "remuneration"],
        "policy_keywords": ["proxy statement", "compensation discussion", "def 14a", "executive compensation"],
        "source_hint": "SEC proxy statement / remuneration report",
        "gri_alignment": ["GRI 2-21"],
        "sasb_alignment": ["SASB CG-AA-330a.2"],
    },
    "Renewable Energy Transition": {
        "primary_metric": "Renewable energy share (% of total energy consumption)",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 80.0,
            "above_average": 50.0,
            "average": 30.0,
            "below_average": 10.0,
        },
        "metric_patterns": [
            r"renewable[^.\n]{0,70}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,70}?renewable",
            r"clean energy[^.\n]{0,70}?(\d{1,3}(?:\.\d+)?)\s*%",
        ],
        "claim_keywords": ["renewable", "clean energy", "solar", "wind", "transition"],
        "policy_keywords": ["target", "policy", "roadmap", "sourcing", "ppa", "commitment"],
        "source_hint": "Sustainability report, annual report energy table, CDP climate disclosure",
        "gri_alignment": ["GRI 302-1", "GRI 302-4"],
        "sasb_alignment": ["SASB IF-EU-000.B", "SASB SV-PS-130a.1"],
    },
    "Biodiversity & Land Use": {
        "primary_metric": "Share of operational sites with biodiversity management plans (%)",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 90.0,
            "above_average": 70.0,
            "average": 50.0,
            "below_average": 30.0,
        },
        "metric_patterns": [
            r"biodiversity[^.\n]{0,90}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"ecosystem[^.\n]{0,90}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"sites?[^.\n]{0,60}?biodiversity[^.\n]{0,60}?(\d{1,3}(?:\.\d+)?)\s*%",
        ],
        "claim_keywords": ["biodiversity", "ecosystem", "habitat", "deforestation", "land use"],
        "policy_keywords": ["tnfd", "no net loss", "restoration", "conservation", "plan"],
        "source_hint": "BRSR Principle 6 disclosures, biodiversity section in sustainability report",
        "gri_alignment": ["GRI 304-1", "GRI 304-3"],
        "sasb_alignment": ["SASB RR-FM-160a.1", "SASB CG-HP-430a.1"],
    },
    "Waste & Circular Economy": {
        "primary_metric": "Waste diversion rate (% waste diverted from landfill)",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 90.0,
            "above_average": 75.0,
            "average": 60.0,
            "below_average": 40.0,
        },
        "metric_patterns": [
            r"waste diversion[^.\n]{0,70}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"recycl(?:ed|ing)[^.\n]{0,70}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,70}?(?:diverted|recycled)",
        ],
        "claim_keywords": ["waste", "recycling", "circular economy", "landfill", "diversion"],
        "policy_keywords": ["zero waste", "circularity", "waste policy", "hazardous waste", "take-back"],
        "source_hint": "Annual sustainability waste KPIs, GRI waste tables, regulator filings",
        "gri_alignment": ["GRI 306-3", "GRI 306-4", "GRI 306-5"],
        "sasb_alignment": ["SASB CG-MR-150a.1", "SASB RT-CH-410a.1"],
    },
    "Employee Health & Safety": {
        "primary_metric": "Lost Time Injury Frequency Rate (LTIFR)",
        "metric_unit": "rate",
        "direction": "lower_better",
        "thresholds": {
            "top_decile": 0.10,
            "above_average": 0.25,
            "average": 0.50,
            "below_average": 1.00,
        },
        "metric_patterns": [
            r"ltifr[^\d]{0,25}(\d+(?:\.\d+)?)",
            r"lost time injury frequency rate[^\d]{0,25}(\d+(?:\.\d+)?)",
            r"trir[^\d]{0,25}(\d+(?:\.\d+)?)",
        ],
        "claim_keywords": ["health", "safety", "occupational", "injury", "fatality", "ltifr"],
        "policy_keywords": ["iso 45001", "ohs policy", "safety management", "certified", "assured"],
        "source_hint": "Safety tables in annual/sustainability report, assured OHS metrics",
        "gri_alignment": ["GRI 403-9", "GRI 403-10"],
        "sasb_alignment": ["SASB RT-IG-320a.1", "SASB SV-PS-320a.1"],
    },
    "Diversity, Equity & Inclusion": {
        "primary_metric": "Women in management or leadership roles (%)",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 45.0,
            "above_average": 35.0,
            "average": 25.0,
            "below_average": 15.0,
        },
        "metric_patterns": [
            r"women[^.\n]{0,70}?(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,40}?(?:management|leadership|board|workforce)",
            r"(?:management|leadership|board|workforce)[^.\n]{0,70}?women[^.\n]{0,40}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"gender diversity[^.\n]{0,70}?(\d{1,3}(?:\.\d+)?)\s*%",
        ],
        "claim_keywords": ["diversity", "inclusion", "equity", "gender", "women", "dei"],
        "policy_keywords": ["equal opportunity", "anti-discrimination", "inclusive hiring", "pay equity", "policy"],
        "source_hint": "Workforce diversity section, board composition, BRSR workforce disclosures",
        "gri_alignment": ["GRI 405-1", "GRI 406-1"],
        "sasb_alignment": ["SASB SV-PS-330a.1", "SASB TC-SI-330a.1"],
    },
    "Board Independence": {
        "primary_metric": "Percentage of independent directors on board (%)",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 85.0,
            "above_average": 70.0,
            "average": 50.0,
            "below_average": 33.0,
        },
        "metric_patterns": [
            r"(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,60}(?:independent|non-executive)\s*(?:director|board)",
            r"(?:independent|non-executive)\s*(?:director|board)[^.\n]{0,60}(\d{1,3}(?:\.\d+)?)\s*%",
            r"(\d{1,2})\s+of\s+(\d{1,2})\s+(?:directors|board members)\s+(?:are\s+)?independent",
            r"board independence[^.\n]{0,50}?(\d{1,3}(?:\.\d+)?)\s*%",
        ],
        "claim_keywords": ["board independence", "independent director", "non-executive", "outside director"],
        "policy_keywords": ["corporate governance guidelines", "board charter", "independence criteria", "nyse listing"],
        "source_hint": "Proxy statement / corporate governance guidelines / annual report",
        "gri_alignment": ["GRI 2-9", "GRI 2-10"],
        "sasb_alignment": ["SASB CG-AA-330a.1"],
    },
    "Anti-Corruption Policies": {
        "primary_metric": "Anti-corruption policy coverage and training completion (%)",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 95.0,
            "above_average": 80.0,
            "average": 60.0,
            "below_average": 40.0,
        },
        "metric_patterns": [
            r"anti[- ]?corruption[^.\n]{0,80}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"ethics training[^.\n]{0,80}?(\d{1,3}(?:\.\d+)?)\s*%",
            r"code of conduct[^.\n]{0,80}?(\d{1,3}(?:\.\d+)?)\s*%\s*(?:completion|compliance)",
            r"(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,60}(?:employees?\s+)?(?:completed|trained)[^.\n]{0,40}(?:anti[- ]?corruption|ethics|compliance)",
        ],
        "claim_keywords": ["anti-corruption", "bribery", "corruption", "ethics", "compliance", "fcpa", "uk bribery act"],
        "policy_keywords": ["anti-bribery", "code of conduct", "ethics policy", "zero tolerance", "compliance program"],
        "source_hint": "Annual report governance section, code of conduct, ESG report",
        "gri_alignment": ["GRI 205-1", "GRI 205-2", "GRI 205-3"],
        "sasb_alignment": ["SASB FN-CB-510a.1", "SASB FN-CB-510a.2"],
    },
    "Whistleblower Mechanisms": {
        "primary_metric": "Whistleblower/ethics hotline reports received per 1000 employees",
        "metric_unit": "rate",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 15.0,
            "above_average": 8.0,
            "average": 3.0,
            "below_average": 1.0,
        },
        "metric_patterns": [
            r"(?:whistleblower|ethics\s*hotline|speak\s*up)[^.\n]{0,80}?(\d{1,6}(?:,\d{3})*(?:\.\d+)?)\s*(?:reports?|cases?|complaints?)",
            r"(\d{1,6}(?:,\d{3})*(?:\.\d+)?)\s*(?:reports?|cases?|complaints?)[^.\n]{0,60}(?:whistleblower|ethics\s*hotline|speak\s*up)",
            r"(?:grievance|reporting)[^.\n]{0,80}?(\d{1,6}(?:,\d{3})*(?:\.\d+)?)\s*(?:incidents?|cases?|matters?)",
        ],
        "claim_keywords": ["whistleblower", "grievance", "reporting mechanism", "speak up", "ethics hotline"],
        "policy_keywords": ["whistleblower protection", "anonymous reporting", "non-retaliation", "ethics line", "hotline"],
        "source_hint": "Annual report governance section, ethics/compliance report",
        "gri_alignment": ["GRI 2-16", "GRI 2-26"],
        "sasb_alignment": ["SASB FN-CB-510a.2"],
    },
    "Green Lending Ratio": {
        "primary_metric": "Green/sustainable lending as share of total loan book (%)",
        "metric_unit": "%",
        "direction": "higher_better",
        "thresholds": {
            "top_decile": 25.0,
            "above_average": 15.0,
            "average": 8.0,
            "below_average": 3.0,
        },
        "metric_patterns": [
            r"(?:green|sustainable)\s*(?:loan|lending|finance|bond)[^.\n]{0,80}?[\$\u20ac\u00a3]?\s*(\d{1,4}(?:\.\d+)?)\s*(?:billion|bn|B)",
            r"[\$\u20ac\u00a3]\s*(\d{1,4}(?:\.\d+)?)\s*(?:billion|bn|B)[^.\n]{0,60}(?:green|sustainable)\s*(?:loan|lending|finance|bond)",
            r"(?:green|sustainable)\s*(?:loan|lending|finance)[^.\n]{0,60}?(\d{1,3}(?:\.\d+)?)\s*%",
        ],
        "claim_keywords": ["green loan", "green lending", "sustainable finance", "green bond", "sustainability bond"],
        "policy_keywords": ["green bond framework", "sustainable lending policy", "climate finance target", "tcfd"],
        "source_hint": "Annual report, sustainability report, TCFD disclosure, green bond framework",
        "gri_alignment": ["GRI 203-1"],
        "sasb_alignment": ["SASB FN-CB-410a.1", "SASB FN-CB-410a.2"],
        "currency_match_score": 75.0,
    },
    "Climate Risk in Loan Book": {
        "primary_metric": "Proportion of loan book exposed to climate-sensitive sectors (%)",
        "metric_unit": "%",
        "direction": "lower_better",
        "thresholds": {
            "top_decile": 5.0,
            "above_average": 10.0,
            "average": 20.0,
            "below_average": 35.0,
        },
        "metric_patterns": [
            r"(?:climate|transition)\s*risk[^.\n]{0,80}?(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,40}(?:loan|portfolio|exposure|book)",
            r"(?:loan|portfolio|exposure|book)[^.\n]{0,60}?(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,60}(?:climate|carbon|fossil)",
            r"(?:fossil fuel|oil and gas|coal)[^.\n]{0,60}?[\$\u20ac\u00a3]?\s*(\d{1,4}(?:\.\d+)?)\s*(?:billion|bn|B)[^.\n]{0,40}(?:exposure|financing|lending)",
        ],
        "claim_keywords": ["climate risk", "transition risk", "physical risk", "stranded asset", "loan book"],
        "policy_keywords": ["tcfd", "stress test", "climate scenario", "net zero banking", "nzba"],
        "source_hint": "TCFD report, annual report risk section, pillar 3 disclosure",
        "gri_alignment": ["GRI 201-2"],
        "sasb_alignment": ["SASB FN-CB-410a.2"],
        "currency_match_score": 75.0,
    },
}



def _extract_data_year(ev: Dict[str, Any]) -> Optional[int]:
    """Best-effort year extraction from evidence metadata."""
    for field in ("date", "publishedAt", "date_retrieved"):
        date_str = str(ev.get(field, ""))
        year_match = re.search(r"20[12]\d", date_str)
        if year_match:
            return int(year_match.group())
    return None


def _evidence_source_name(ev: Dict[str, Any], default: str = "") -> str:
    return str(ev.get("sourcename") or ev.get("source_name") or default)


def _evidence_text(ev: Dict[str, Any]) -> str:
    return " ".join(
        str(ev.get(k, ""))
        for k in ("title", "snippet", "content", "relevanttext", "relevant_text", "source", "sourcename", "source_name")
    )


def _evidence_tier(ev: Dict[str, Any]) -> int:
    url = str(ev.get("url", ""))
    tier = get_reliability_tier(url)
    explicit_tier = ev.get("reliabilitytier")
    if explicit_tier is None:
        explicit_tier = ev.get("reliability_tier")
    try:
        if explicit_tier is not None:
            tier = min(tier, int(explicit_tier))
    except (TypeError, ValueError):
        pass

    source_name = _evidence_source_name(ev).strip()
    sn_override = _SOURCENAME_TIER_OVERRIDES.get(source_name)
    if sn_override is None:
        sn_override = _SOURCENAME_TIER_OVERRIDES.get(source_name.lower())
    if sn_override is not None:
        tier = min(tier, sn_override)
    return max(1, min(4, tier))


def synthesize_sec_metric_evidence(external_benchmarks: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create scannable SEC evidence snippets from parsed DEF 14A metrics."""
    if not isinstance(external_benchmarks, dict):
        return []

    sec_metrics = external_benchmarks.get("sec_metrics", {})
    if not isinstance(sec_metrics, dict) or not sec_metrics:
        return []

    snippets: List[str] = []
    board_independence = sec_metrics.get("board_independence_pct")
    if board_independence is not None:
        snippets.append(f"{board_independence}% independent directors on board (DEF 14A)")

    pay_ratio = sec_metrics.get("pay_ratio")
    if pay_ratio is None:
        pay_ratio = sec_metrics.get("executive_pay_ratio")
    if pay_ratio is not None:
        snippets.append(f"pay ratio {pay_ratio} to 1 CEO DEF 14A proxy statement")

    if sec_metrics.get("has_anti_corruption_policy") is True:
        snippets.append("anti-corruption policy code of conduct ethics training employees (DEF 14A)")

    if sec_metrics.get("whistleblower_hotline") is True:
        snippets.append("whistleblower ethics hotline speak up anonymous reporting mechanism")

    return [
        {
            "title": "SEC DEF 14A governance metric",
            "snippet": snippet,
            "url": "https://www.sec.gov/cgi-bin/browse-edgar",
            "sourcename": "sec def14a",
            "reliabilitytier": 1,
            "isprimarydocument": True,
        }
        for snippet in snippets
    ]


def _extract_best_metric_value(
    rule: Dict[str, Any],
    evidence_sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract the best quantitative metric value for a structured-scoring indicator."""
    metric_patterns = rule.get("metric_patterns", [])
    metric_unit = rule.get("metric_unit")
    best_match: Optional[Dict[str, Any]] = None

    for ev in evidence_sources:
        if not isinstance(ev, dict):
            continue

        url = str(ev.get("url", ""))
        tier = _evidence_tier(ev)
        source_name = (parse_source_name(url) if url else None) or _evidence_source_name(ev, "Web evidence")
        data_year = _extract_data_year(ev)
        ev_text = _evidence_text(ev)

        for pattern in metric_patterns:
            for match in re.finditer(pattern, ev_text, flags=re.IGNORECASE):
                try:
                    if match.lastindex and match.lastindex >= 2 and "of" in match.group(0).lower():
                        numerator = float(match.group(1))
                        denominator = float(match.group(2))
                        if denominator == 0:
                            continue
                        value = (numerator / denominator) * 100.0
                    else:
                        value = float(match.group(1))
                except (TypeError, ValueError, IndexError, ZeroDivisionError):
                    continue

                if metric_unit == "%" and (value < 0 or value > 100):
                    continue
                if metric_unit == "rate" and (value < 0 or value > 1000):
                    continue

                candidate = {
                    "value": value,
                    "url": url or None,
                    "source_name": source_name,
                    "tier": tier,
                    "year": data_year,
                    "matched_text": match.group(0),
                }

                if best_match is None:
                    best_match = candidate
                    continue

                # Prefer higher-reliability sources first, then newer year.
                best_year = best_match.get("year") or 0
                cand_year = candidate.get("year") or 0
                if candidate["tier"] < best_match["tier"] or (
                    candidate["tier"] == best_match["tier"] and cand_year > best_year
                ):
                    best_match = candidate

    return best_match or {}


def _score_from_thresholds(value: float, rule: Dict[str, Any]) -> int:
    """Map a quantitative value into the fixed score buckets: 100/75/50/25/0."""
    thresholds = rule.get("thresholds", {})
    direction = rule.get("direction", "higher_better")

    if direction == "lower_better":
        if value <= thresholds.get("top_decile", float("inf")):
            return 100
        if value <= thresholds.get("above_average", float("inf")):
            return 75
        if value <= thresholds.get("average", float("inf")):
            return 50
        if value <= thresholds.get("below_average", float("inf")):
            return 25
        return 0

    if value >= thresholds.get("top_decile", float("inf")):
        return 100
    if value >= thresholds.get("above_average", float("inf")):
        return 75
    if value >= thresholds.get("average", float("inf")):
        return 50
    if value >= thresholds.get("below_average", float("inf")):
        return 25
    return 0


def _score_structured_indicator(
    indicator: Dict[str, Any],
    rule: Dict[str, Any],
    evidence_sources: List[Dict[str, Any]],
    carbon_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Structured indicator scoring with quantitative thresholds and explicit fallback."""
    name = indicator["name"]
    if name == "ESG Disclosure Quality" and isinstance(carbon_data, dict):
        emissions = carbon_data.get("emissions", {}) if isinstance(carbon_data.get("emissions"), dict) else {}
        scope1 = safe_get(emissions, "scope1", "value")
        scope2 = safe_get(emissions, "scope2", "value")
        scope3 = safe_get(emissions, "scope3", "total")
        if scope3 is None:
            scope3 = safe_get(emissions, "scope3", "value")
        scope3_categories = safe_get(emissions, "scope3", "categories", default={})
        if isinstance(scope3_categories, dict):
            scope3_cat_count = len(scope3_categories)
        elif isinstance(scope3_categories, list):
            scope3_cat_count = len(scope3_categories)
        else:
            scope3_cat_count = 0
        sbti_status = str(carbon_data.get("sbti_status") or "").lower()
        renewable_disclosed = (
            carbon_data.get("renewable_energy_percentage") is not None
            or carbon_data.get("renewable_pct") is not None
            or carbon_data.get("renewable_status") is not None
        )
        offset_status = str(safe_get(carbon_data, "offset_transparency", "status", default="")).lower()
        third_party_verified = bool(
            str(carbon_data.get("verification_status", "")).strip()
            and "unverified" not in str(carbon_data.get("verification_status", "")).lower()
        )
        checks = [
            (scope1 is not None, 15),
            (scope2 is not None, 15),
            (scope3 is not None, 10),
            (scope3_cat_count >= 5, 10),
            (sbti_status not in {"", "not submitted", "unverified"}, 15),
            (renewable_disclosed, 10),
            (offset_status not in {"", "not disclosed", "no_offset_disclosure", "unknown"}, 10),
            (third_party_verified, 10),
            (bool(carbon_data.get("net_zero_target")), 5),
        ]
        earned = sum(weight for passed, weight in checks if passed)
        score = round(float(earned), 1)
        return {
            "name": name,
            "score": score,
            "weight": indicator["weight"],
            "data_source": "Computed disclosure completeness checklist",
            "source_url": None,
            "data_year": 2024,
            "methodology": "Weighted completeness checklist across core disclosure controls.",
            "raw_value": f"{earned}/100 checklist points",
            "unit": "%",
            "verified": third_party_verified,
            "primary_metric": rule.get("primary_metric"),
            "metric_source_hint": rule.get("source_hint"),
            "gri_alignment": rule.get("gri_alignment", []),
            "sasb_alignment": rule.get("sasb_alignment", []),
            "fallback_rule": "computed score (no hardcoded 100 defaults)",
            "scoring_model": "structured_threshold_v1",
        }

    metric_match = _extract_best_metric_value(rule, evidence_sources)

    # ── Currency guard: $ commitments → flat score for banking indicators ──
    _currency_flat = rule.get("currency_match_score")
    if _currency_flat and not metric_match:
        _currency_re = re.compile(
            r"[\$€£]\s*\d[\d,.]*\s*(?:billion|bn|million|mn|B|M|trillion|tn|T)",
            re.IGNORECASE,
        )
        for _ev in evidence_sources:
            if not isinstance(_ev, dict):
                continue
            _blob = _evidence_text(_ev)
            if _currency_re.search(_blob):
                _claim_kws = [str(k).lower() for k in rule.get("claim_keywords", [])]
                if any(kw in _blob.lower() for kw in _claim_kws):
                    return {
                        "name": name,
                        "score": float(_currency_flat),
                        "weight": indicator["weight"],
                        "data_source": (parse_source_name(str(_ev.get("url", ""))) if _ev.get("url") else None) or _evidence_source_name(_ev, "Company disclosure"),
                        "source_url": _ev.get("url"),
                        "data_year": _extract_data_year(_ev) or 2024,
                        "methodology": (
                            f"Currency commitment detected for {rule.get('primary_metric')}. "
                            f"Flat score {_currency_flat} assigned (quantitative % metric not extracted)."
                        ),
                        "raw_value": _blob[:120].strip(),
                        "unit": rule.get("metric_unit", "%"),
                        "data_tier": _evidence_tier(_ev),
                        "verified": bool(_evidence_tier(_ev) <= 2),
                        "primary_metric": rule.get("primary_metric"),
                        "metric_source_hint": rule.get("source_hint"),
                        "gri_alignment": rule.get("gri_alignment", []),
                        "sasb_alignment": rule.get("sasb_alignment", []),
                        "fallback_rule": "currency_commitment_guard",
                        "scoring_model": "structured_threshold_v1",
                    }

    thresholds = rule.get("thresholds", {})
    threshold_text = (
        f"100 if metric is top decile ({thresholds.get('top_decile')}), "
        f"75 above average ({thresholds.get('above_average')}), "
        f"50 average ({thresholds.get('average')}), "
        f"25 below average ({thresholds.get('below_average')}), else 0"
    )

    if metric_match:
        metric_value = float(metric_match["value"])
        score = _score_from_thresholds(metric_value, rule)
        metric_unit = rule.get("metric_unit")
        if metric_unit == "%":
            raw_value = f"{metric_value:.1f}%"
        else:
            raw_value = f"{metric_value:.3f}"

        return {
            "name": name,
            "score": float(score),
            "weight": indicator["weight"],
            "data_source": metric_match.get("source_name") or "Structured quantitative disclosure",
            "source_url": metric_match.get("url"),
            "data_year": metric_match.get("year") or 2024,
            "data_tier": metric_match.get("tier", 4),
            "methodology": (
                f"Structured threshold scoring using {rule.get('primary_metric')}. "
                f"Buckets: {threshold_text}."
            ),
            "raw_value": raw_value,
            "unit": metric_unit,
            "verified": bool(metric_match.get("tier", 5) <= 2),
            "primary_metric": rule.get("primary_metric"),
            "metric_source_hint": rule.get("source_hint"),
            "gri_alignment": rule.get("gri_alignment", []),
            "sasb_alignment": rule.get("sasb_alignment", []),
            "fallback_rule": "verified policy=40, unverified claim=20, no mention=0",
            "scoring_model": "structured_threshold_v1",
        }

    claim_keywords = [str(k).lower() for k in rule.get("claim_keywords", [])]
    policy_keywords = [str(k).lower() for k in rule.get("policy_keywords", [])]

    best_policy_url = None
    best_policy_source = None
    best_policy_tier = 5
    best_policy_year = None
    has_policy_mention = False
    has_any_claim = False

    for ev in evidence_sources:
        if not isinstance(ev, dict):
            continue
        url = str(ev.get("url", ""))
        tier = _evidence_tier(ev)
        source_name = (parse_source_name(url) if url else None) or _evidence_source_name(ev, "Web evidence")
        ev_text = _evidence_text(ev).lower()

        claim_hit = any(kw in ev_text for kw in claim_keywords)
        policy_hit = any(kw in ev_text for kw in policy_keywords)
        if claim_hit:
            has_any_claim = True
        if claim_hit and policy_hit:
            has_policy_mention = True
            if tier < best_policy_tier:
                best_policy_tier = tier
                best_policy_url = url or None
                best_policy_source = source_name
                best_policy_year = _extract_data_year(ev)

    if has_policy_mention and best_policy_tier <= 2:
        fallback_score = 40.0
        fallback_source = best_policy_source or "Verified policy disclosure"
        verified = True
    elif has_any_claim:
        fallback_score = 20.0
        fallback_source = best_policy_source or "Unverified narrative claim"
        verified = False
    else:
        fallback_score = 0.0
        fallback_source = "No relevant disclosure"
        verified = False

    megabank_structured_factors = {
        "Board Independence",
        "Executive Pay Ratio",
        "Whistleblower Mechanisms",
    }
    if name in megabank_structured_factors and best_policy_tier == 1 and fallback_score == 40.0:
        bank_evidence_text = " ".join(
            _evidence_text(ev).lower()
            for ev in evidence_sources
            if isinstance(ev, dict)
        )
        has_us_bank_mandatory_evidence = any(
            marker in bank_evidence_text
            for marker in (
                "confirmed us bank",
                "us large-cap bank",
                "nyse listing standards",
                "dodd-frank",
                "section 953",
                "sarbanes-oxley",
                "sox",
            )
        )
        if has_us_bank_mandatory_evidence:
            fallback_score = 65.0
            fallback_source = best_policy_source or "SEC mandatory structured disclosure"
            verified = True

    # === Banking factor stubs: limited_disclosure exclusion ===
    _BANKING_FACTORS_REQUIRING_STUB = {
        "Green Lending Ratio",
        "Climate Risk in Loan Book",
    }
    if name in _BANKING_FACTORS_REQUIRING_STUB and not has_any_claim:
        return {
            "name": name,
            "score": 0.0 if name == "Climate Risk in Loan Book" else None,
            "weight": indicator["weight"],
            "data_source": "No data source available",
            "source_url": None,
            "data_year": None,
            "data_tier": 4,
            "data_quality": "No Disclosure",
            "methodology": None,
            "raw_value": None,
            "unit": rule.get("metric_unit"),
            "verified": False,
            "primary_metric": rule.get("primary_metric"),
            "metric_source_hint": rule.get("source_hint"),
            "gri_alignment": rule.get("gri_alignment", []),
            "sasb_alignment": rule.get("sasb_alignment", []),
            "limited_disclosure": True,
            "quality_flag": "MISSING_BANKING_DATA",
            "fallback_rule": "banking_factor_stub_limited_disclosure",
            "scoring_model": "structured_threshold_v1",
        }
    # === END Banking factor stubs ===

    return {
        "name": name,
        "score": fallback_score,
        "weight": indicator["weight"],
        "data_source": fallback_source,
        "source_url": best_policy_url,
        "data_year": best_policy_year or 2024,
        "data_tier": best_policy_tier if best_policy_tier <= 4 else 4,
        "methodology": (
            f"Structured threshold scoring with fallback. Primary metric: {rule.get('primary_metric')}. "
            f"Fallback applied: verified policy=40, unverified claim=20, no mention=0."
        ),
        "raw_value": None,
        "unit": rule.get("metric_unit"),
        "verified": verified,
        "primary_metric": rule.get("primary_metric"),
        "metric_source_hint": rule.get("source_hint"),
        "gri_alignment": rule.get("gri_alignment", []),
        "sasb_alignment": rule.get("sasb_alignment", []),
        "fallback_rule": "verified policy=40, unverified claim=20, no mention=0",
        "scoring_model": "structured_threshold_v1",
    }


def _normalize_industry(industry: str) -> str:
    """Normalize industry name for lookup."""
    if not industry:
        return "general"
    return industry.strip().lower().replace("_", " ")


def _build_indicators_for_pillar(
    pillar_key: str,
    industry: str,
    default_indicators: List[Dict],
) -> List[Dict]:
    """Combine default + industry-specific indicators, then renormalize weights to sum to 1.0."""
    indicators = [dict(ind) for ind in default_indicators]  # deep copy

    norm_industry = _normalize_industry(industry)
    extra = safe_get(_INDUSTRY_EXTRA, norm_industry, pillar_key, default=[])

    if extra:
        indicators.extend([dict(e) for e in extra])

    # Renormalize weights to sum to 1.0
    total_weight = sum(ind["weight"] for ind in indicators)
    if total_weight > 0:
        for ind in indicators:
            ind["weight"] = round(ind["weight"] / total_weight, 4)

    return indicators


def _score_indicator(
    indicator: Dict,
    evidence_texts: List[str],
    evidence_sources: List[Dict],
    carbon_data: Optional[Dict],
) -> Dict[str, Any]:
    """Score a single sub-indicator based on evidence keyword matching.

    Returns a dict with score, data_source, raw_value, verified, etc.
    If evidence is insufficient, score is set to None.
    """
    name = indicator["name"]

    structured_rule = _STRUCTURED_SCORING_RULES.get(name)
    if structured_rule:
        return _score_structured_indicator(indicator, structured_rule, evidence_sources, carbon_data=carbon_data)

    keywords = indicator.get("keywords", [])

    # Collect matching evidence
    matching_sources = []
    matching_texts = []
    best_url = None
    best_tier = 5
    data_year = None
    verified = False

    for ev in evidence_sources:
        if not isinstance(ev, dict):
            continue
        ev_text = _evidence_text(ev).lower()

        hit_count = sum(1 for kw in keywords if kw in ev_text)
        if hit_count >= 1:
            matching_texts.append(ev_text[:300])
            url = ev.get("url", "")
            tier = _evidence_tier(ev)
            source_name = (parse_source_name(url) if url else None) or _evidence_source_name(ev)
            matching_sources.append(source_name)

            if tier < best_tier:
                best_tier = tier
                best_url = url

            # Try to extract year from evidence
            for field in ("date", "publishedAt", "date_retrieved"):
                date_str = str(ev.get(field, ""))
                year_match = re.search(r"20[12]\d", date_str)
                if year_match:
                    data_year = int(year_match.group())
                    break

            # Check if from primary disclosure or high-quality company disclosure.
            if tier <= 2:
                verified = True

    # Special handling for GHG-related indicators using carbon_data
    raw_value = None
    unit = None
    methodology = None

    if isinstance(carbon_data, dict) and ("ghg" in name.lower() or "emission" in name.lower()):
        emissions = safe_get(carbon_data, "emissions", default={})
        if isinstance(emissions, dict):
            scope1_val = safe_get(emissions, "scope1", "value")
            scope2_val = safe_get(emissions, "scope2", "value")
            if scope1_val is not None or scope2_val is not None:
                parts = []
                if scope1_val is not None:
                    parts.append(f"Scope 1: {scope1_val}")
                if scope2_val is not None:
                    parts.append(f"Scope 2: {scope2_val}")
                raw_value = ", ".join(parts) + " tCO2e"
                unit = "tCO2e"
                methodology = "Scope 1+2 tCO2e per unit revenue, normalized to industry peers"
                if not matching_sources:
                    matching_sources.append("Company carbon disclosure")

    # Determine score
    if not matching_sources and raw_value is None:
        # Insufficient data — do NOT hallucinate a score
        return {
            "name": name,
            "score": None,
            "weight": indicator["weight"],
            "data_source": "Insufficient data",
            "source_url": None,
            "data_year": data_year,
            "methodology": None,
            "raw_value": None,
            "unit": unit,
            "verified": False,
        }

    # Compute a heuristic score based on evidence density and quality
    evidence_density = min(len(matching_sources), 5)  # cap at 5
    tier_bonus = {1: 20, 2: 10, 3: 5, 4: 0, 5: 0}.get(best_tier, 0)

    # Base score: 40 + evidence hits * 8 + tier bonus, capped at 95
    raw_score = min(95.0, max(20.0, 40.0 + evidence_density * 8.0 + tier_bonus))

    # Build data_source string
    unique_sources = list(dict.fromkeys(matching_sources))[:3]
    data_source = " / ".join(unique_sources) if unique_sources else "Web evidence"

    return {
        "name": name,
        "score": round(raw_score, 1),
        "weight": indicator["weight"],
        "data_source": data_source,
        "source_url": best_url,
        "data_year": data_year or 2024,
        "data_tier": best_tier if best_tier <= 4 else 4,
        "methodology": methodology or f"Keyword-matched evidence scoring for {name.lower()}",
        "raw_value": raw_value,
        "unit": unit,
        "verified": verified,
    }


def _rescale_scores_to_target(
    sub_indicators: List[Dict], target_score: float
) -> List[Dict]:
    """Rescale non-null sub-indicator scores so their weighted average equals target_score.

    This ensures mathematical consistency: weighted_avg(sub_scores) == pillar_score.
    """
    scored = [(i, ind) for i, ind in enumerate(sub_indicators) if ind.get("score") is not None]
    if not scored:
        return sub_indicators

    # Keep structured-threshold indicators fixed; only rescale flexible indicators.
    locked = [
        (i, ind)
        for i, ind in scored
        if ind.get("scoring_model") == "structured_threshold_v1"
    ]
    flexible = [
        (i, ind)
        for i, ind in scored
        if ind.get("scoring_model") != "structured_threshold_v1"
    ]

    if not flexible:
        return sub_indicators

    total_weight = sum(ind["weight"] for _, ind in scored)
    flex_weight = sum(ind["weight"] for _, ind in flexible)
    if total_weight <= 0 or flex_weight <= 0:
        return sub_indicators

    locked_total = sum(ind["score"] * ind["weight"] for _, ind in locked)
    target_total = target_score * total_weight
    target_flex_avg = (target_total - locked_total) / flex_weight
    target_flex_avg = max(0.0, min(100.0, target_flex_avg))

    current_flex_avg = sum(ind["score"] * ind["weight"] for _, ind in flexible) / flex_weight

    if current_flex_avg <= 0:
        # Can't rescale from zero, just set all to target
        for idx, ind in flexible:
            sub_indicators[idx] = {**ind, "score": round(target_flex_avg, 1)}
        return sub_indicators

    scale_factor = target_flex_avg / current_flex_avg

    for idx, ind in flexible:
        new_score = max(0.0, min(100.0, ind["score"] * scale_factor))
        sub_indicators[idx] = {**ind, "score": round(new_score, 1)}

    return sub_indicators


def build_pillar_factors(
    company: str,
    industry: str,
    evidence_sources: List[Dict],
    carbon_data: Optional[Dict],
    pillar_scores: Optional[Dict] = None,
    external_benchmarks: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Build structured pillar_factors with full sub-indicator breakdown.

    Args:
        company: Company name
        industry: Industry sector (e.g. "Energy", "Banking")
        evidence_sources: List of evidence dicts from evidence retrieval
        carbon_data: Carbon extraction results dict
        pillar_scores: Dict with pillar scores (environmental_score, social_score, governance_score)
        external_benchmarks: External ESG data containing SEC/WBA/WRI enrichment

    Returns:
        Dict with 'environmental', 'social', 'governance' keys, each containing
        score, weight, and sub_indicators list.
    """
    if not isinstance(pillar_scores, dict):
        pillar_scores = {}
    if not isinstance(evidence_sources, list):
        evidence_sources = []
    if not isinstance(carbon_data, dict):
        carbon_data = {}

    sec_evidence = synthesize_sec_metric_evidence(external_benchmarks)
    if sec_evidence:
        existing_snippets = {
            str(ev.get("snippet", "")).strip()
            for ev in evidence_sources
            if isinstance(ev, dict) and ev.get("snippet")
        }
        evidence_sources = list(evidence_sources) + [
            ev for ev in sec_evidence
            if str(ev.get("snippet", "")).strip() not in existing_snippets
        ]

    # Extract pillar target scores or compute them if not provided
    has_target = bool(pillar_scores)
    env_score = safe_number(pillar_scores.get("environmental_score"), default=50.0) if has_target else None
    soc_score = safe_number(pillar_scores.get("social_score"), default=50.0) if has_target else None
    gov_score = safe_number(pillar_scores.get("governance_score"), default=50.0) if has_target else None

    # Gather all evidence text for scoring
    evidence_texts = []
    for ev in evidence_sources:
        if isinstance(ev, dict):
            for k in ("snippet", "content", "relevanttext", "relevant_text", "title"):
                txt = ev.get(k, "")
                if txt:
                    evidence_texts.append(str(txt).lower())

    # Build indicators per pillar
    env_indicators = _build_indicators_for_pillar("environmental", industry, _DEFAULT_ENVIRONMENTAL)
    soc_indicators = _build_indicators_for_pillar("social", industry, _DEFAULT_SOCIAL)
    gov_indicators = _build_indicators_for_pillar("governance", industry, _DEFAULT_GOVERNANCE)

    # Score each sub-indicator and validate through Pydantic contract
    env_scored = [
        _to_factor_result(_score_indicator(ind, evidence_texts, evidence_sources, carbon_data))
        for ind in env_indicators
    ]
    soc_scored = [
        _to_factor_result(_score_indicator(ind, evidence_texts, evidence_sources, carbon_data))
        for ind in soc_indicators
    ]
    gov_scored = [
        _to_factor_result(_score_indicator(ind, evidence_texts, evidence_sources, carbon_data))
        for ind in gov_indicators
    ]

    def _compute_coverage_adjusted(scored_indicators) -> float:
        total_weight = 0.0
        total_score = 0.0
        for ind in scored_indicators:
            if ind.get("score") is not None:
                total_weight += ind["weight"]
                total_score += ind["score"] * ind["weight"]
        if total_weight > 0:
            return total_score / total_weight
        return 0.0

    def _count_tier1(scored_indicators) -> int:
        return sum(1 for ind in scored_indicators if ind.get("data_tier") == 1)

    def _total_factors(scored_indicators) -> int:
        return len(scored_indicators)

    env_adj = _compute_coverage_adjusted(env_scored)
    soc_adj = _compute_coverage_adjusted(soc_scored)
    gov_adj = _compute_coverage_adjusted(gov_scored)

    if not has_target:
        env_score = env_adj
        soc_score = soc_adj
        gov_score = gov_adj
    else:
        # Rescale to match target pillar scores
        env_scored = _rescale_scores_to_target(env_scored, env_score)
        soc_scored = _rescale_scores_to_target(soc_scored, soc_score)
        gov_scored = _rescale_scores_to_target(gov_scored, gov_score)

    # Compute aggregate Performance Score (P) for the GW formula
    # P is the materiality-weighted average across all three pillars
    all_factors = env_scored + soc_scored + gov_scored
    performance_score = _compute_coverage_adjusted(all_factors)

    # Compute factor coverage stats for Disclosure Score (D)
    tier1_count = _count_tier1(env_scored) + _count_tier1(soc_scored) + _count_tier1(gov_scored)
    total_factor_count = _total_factors(env_scored) + _total_factors(soc_scored) + _total_factors(gov_scored)

    return {
        "environmental": {
            "score": round(env_score, 1),
            "coverageadjustedscore": round(env_adj, 1),
            "weight": 0.40,
            "sub_indicators": env_scored,
        },
        "social": {
            "score": round(soc_score, 1),
            "coverageadjustedscore": round(soc_adj, 1),
            "weight": 0.30,
            "sub_indicators": soc_scored,
        },
        "governance": {
            "score": round(gov_score, 1),
            "coverageadjustedscore": round(gov_adj, 1),
            "weight": 0.30,
            "sub_indicators": gov_scored,
        },
        "performance_score": round(performance_score, 1),
        "factor_coverage": {
            "tier1_factors": tier1_count,
            "total_factors": total_factor_count,
        },
    }
