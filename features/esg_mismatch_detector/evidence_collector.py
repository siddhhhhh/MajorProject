from typing import List, Dict
import os
import re
import datetime
from urllib.parse import urlparse

from utils.web_search import RealTimeDataFetcher

CURRENT_YEAR = datetime.datetime.now().year

# ==============================
# TRUSTED SOURCE LIST
# ==============================

TRUSTED_DOMAINS = [
    # Regulatory / Government
    "sec.gov",
    "epa.gov",
    "europa.eu",
    "gov.uk",
    "sebi.gov.in",

    # Climate databases
    "cdp.net",
    "sbti.org",
    "climatetrace.org",
    "unfccc.int",
    "iea.org",
    "worldbank.org",
    "sciencebasedtargets.org",

    # Tier-1 investigative journalism
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com"
]

ESG_KEYWORDS = [
    "emissions", "carbon", "ghg", "renewable", "climate", "sustainability", 
    "net zero", "carbon neutral", "scope 1", "scope 2", "scope 3", 
    "energy consumption", "environmental impact"
]

INVALID_TERMS = [
    "guidance", "policy", "dataset", "methodology", "how to measure", 
    "reporting standard", "framework"
]

def is_trusted_source(url: str) -> bool:
    """Verify domain belongs to trusted ESG/legal sources."""
    try:
        domain = urlparse(url).netloc.lower()

        for trusted in TRUSTED_DOMAINS:
            if trusted in domain:
                return True

        return False

    except Exception:
        return False

def get_credibility_score(url: str) -> int:
    """Assign an evidence credibility score based on domain authority."""
    domain = urlparse(url).netloc.lower()
    if any(d in domain for d in ["sec.gov", "epa.gov", "europa.eu", "gov.uk", "sebi.gov.in", "unfccc.int", "worldbank.org", "iea.org"]):
        return 5
    if any(d in domain for d in ["cdp.net", "sbti.org", "climatetrace.org", "sciencebasedtargets.org"]):
        return 4
    if any(d in domain for d in ["ft.com", "bloomberg.com", "wsj.com", "reuters.com"]):
        return 4
    return 3

# ==============================
# METRIC DETECTION
# ==============================

def detect_metric_from_text(text: str) -> str:
    text = text.lower()

    if "renewable" in text or "carbon-free" in text:
        return "renewable_energy"

    if "scope 1" in text or "scope 2" in text or "scope 3" in text:
        return "carbon_emissions"

    if "emissions" in text or "co2" in text or "ghg" in text or "carbon" in text:
        return "carbon_emissions"

    if "water" in text:
        return "water_usage"

    if "waste" in text:
        return "waste_management"

    return "sustainability_goal"


# ==============================
# NUMERIC EXTRACTION
# ==============================

def extract_valid_change(text: str, metric: str) -> float | None:
    """
    Extract strictly metric-aligned numeric change (+/-) from text.
    Implements metric-number alignment and semantic validation.
    """
    text_lower = text.lower()
    
    # 1. Reject if no valid change keywords (Semantic Validation)
    change_keywords = ["increased", "reduced", "decreased", "rise", "fell", "cut", "jump", "rose", "higher", "lower", "down", "dropped", "slashed", "surge", "grew"]
    if not any(kw in text_lower for kw in change_keywords):
        return None
        
    # Valid Performance filter (Step 3 & 4: the value is not part of a future promise)
    if any(future in text_lower for future in ["aims to", "target to", "will reduce", "pledged to", "committed to"]):
        return None
        
    # 2. Extract percentage or raw numbers near the metric
    # Find all percentages
    matches = list(re.finditer(r'((?:[-+])?\d{1,3}(?:\.\d+)?)\s*%', text))
    if not matches:
        return None
        
    val = None
    best_dist = float('inf')
    
    # 3. Require metric-number alignment
    # Check distance between the metric keywords and the number. 
    # If "emissions" or "carbon" isn't within ~50 characters of the number, discard to avoid false mappings like "profit increased by 30%".
    metric_kws = ["emission", "carbon", "co2", "ghg", "renewable" ,"energy"]
    if metric == "water usage": metric_kws = ["water"]
    
    metric_positions = [m.start() for m in re.finditer("|".join(metric_kws), text_lower)]
    
    if not metric_positions:
        return None
        
    for match in matches:
        num_pos = match.start()
        # Find closest metric keyword
        dist = min((abs(num_pos - p) for p in metric_positions), default=float('inf'))
        if dist < 60: # Must be within ~60 characters to be safely associated
            try:
                candidate_val = float(match.group(1))
                val = candidate_val
                break
            except:
                pass
                
    if val is None:
        return None

    increase_keywords = ["increased", "rose", "higher", "jump", "up", "surge", "climbed", "grew", "rise"]
    decrease_keywords = ["decreased", "cut", "fell", "lower", "down", "dropped", "slashed", "reduced", "reduction"]
    
    is_increase = any(word in text_lower for word in increase_keywords)
    is_decrease = any(word in text_lower for word in decrease_keywords)
    
    if is_increase and not is_decrease:
         return abs(val) # Positive value = indicator of increase
    if is_decrease and not is_increase:
         return -abs(val) # Negative value = indicator of decrease
         
    return val

def clean_snippet(snippet: str) -> str:
    """Clean and truncate snippet for easy reading."""
    import re
    clean = re.sub(r'\s+', ' ', snippet).strip()
    return clean[:130] + "..." if len(clean) > 130 else clean

def deduct_legal_score(snippet: str) -> int:
    return 0

# ==============================
# QUALITATIVE VIOLATION EXTRACTION
# ==============================
def evaluate_legal_outcome(text: str) -> str:
    """
    Determine the category and severity of a legal or regulatory event.
    """
    t = text.lower()
    if any(w in t for w in ["won appeal", "overturned", "cleared", "dismissed", "dropped", "successful appeal"]):
        return "Legal Dispute Overturned"
    if any(w in t for w in ["fined", "penalized", "settled", "settlement", "convicted", "guilty", "ruling against", "ordered to", "court ordered"]):
        return "Confirmed Violation"
    if any(w in t for w in ["lawsuit", "sued", "dispute", "appeal", "appealing", "court case"]):
        return "Legal Dispute"
    if any(w in t for w in ["alleged", "accused", "investigation", "probe", "claims", "allegation", "scrutiny", "notice of violation"]):
        return "Allegation"
    return "Policy Gap / Performance Flag"

def detect_qualitative_violation(text: str) -> bool:
    """
    Look for explicit indicators of regulatory or ethical violations 
    that might lack numeric metrics but constitute an implementation gap (See STEP 3: TYPE 2).
    """
    text_lower = text.lower()
    violation_keywords = [
        "environmental scandal",
        "regulatory violation",
        "government investigation",
        "emissions cheating",
        "environmental fine",
        "lawsuit",
        "misleading environmental claims",
        "product misrepresentation",
        "defeat device",
        "cheating scandal",
        "fraud",
        "sec probe",
        "notice of violation",
        "nov"
    ]
    return any(kw in text_lower for kw in violation_keywords)

# ==============================
# MAIN EVIDENCE COLLECTION
# ==============================

def collect_external_evidence(company_name: str) -> List[Dict]:
    """
    Collect real-world ESG evidence using only trusted legal/regulatory sources.
    """

    evidence = []
    seen_urls = set()
    company_lower = company_name.lower().split()[0]

    try:
        fetcher = RealTimeDataFetcher()

        print("🔍 Searching trusted legal / regulatory sources...")

        domain_filter = " OR ".join([f"site:{d}" for d in TRUSTED_DOMAINS])
        # Sometimes query gets too long for Duckduckgo, split filters or simplify query strings
        first_half_domains = " OR ".join([f"site:{d}" for d in TRUSTED_DOMAINS[:7]])
        second_half_domains = " OR ".join([f"site:{d}" for d in TRUSTED_DOMAINS[7:]])

        # Remove the OR from the base queries which breaks duckduckgo site searches when mixed with complex booleans
        queries = [
            f"{company_name} emissions violation fraud {first_half_domains}",
            f"{company_name} emissions violation fraud {second_half_domains}",
            f"{company_name} emissions scandal {first_half_domains}",
            f"{company_name} emissions scandal {second_half_domains}",
            f"{company_name} scope 1 scope 2 scope 3 emissions data {first_half_domains}",
            f"{company_name} scope 1 scope 2 scope 3 emissions data {second_half_domains}"
        ]

        for idx, search_query in enumerate(queries):
            results = fetcher.search_duckduckgo(search_query, max_results=8)

            for res in results:

                url = res.get("url", "")
                snippet = res.get("snippet", "")
                text = snippet.lower()

                if not url or url in seen_urls:
                    continue
                
                # --------------------------------
                # 1. Ensure Company is Mentioned
                # --------------------------------
                if company_lower not in text:
                    continue

                # --------------------------------
                # 2. Strict ESG Evidence Filtering
                # --------------------------------
                # Temporarily disabled strict keyword matching for qualitative legal findings (like "fraud") where it might just say "emissions scandal" without heavy ESG vernacular.
                # if not any(kw in text for kw in ESG_KEYWORDS):
                #     continue

                # --------------------------------
                # 3. Reject Generic Documents
                # --------------------------------
                if any(inv in text for inv in INVALID_TERMS):
                    continue
                
                # --------------------------------
                # 4. Filter ONLY trusted sources
                # --------------------------------
                if not is_trusted_source(url):
                    continue
                    
                score = get_credibility_score(url)
                if score < 3:
                    continue

                seen_urls.add(url)
                metric = detect_metric_from_text(text)
                
                domain = urlparse(url).netloc.replace("www.", "")
                credibility = f"Score {score} - Verified via {domain}"
                quote = clean_snippet(snippet)

                value = None

                # --------------------------------
                # Numeric Extraction with Polarity and Context Alignment
                # --------------------------------
                percent = extract_valid_change(text, metric)
                
                # STEP 3: TYPE 2 — Regulatory or Ethical Violations check
                is_violation = detect_qualitative_violation(text)
                
                # Expand violation detection strongly
                if not is_violation and any(word in text for word in ["investigation", "violation", "illegal", "fraud", "scandal", "dieselgate", "probe"]):
                    is_violation = True
                    
                event_category = evaluate_legal_outcome(text) if is_violation else "Performance Metric"
                
                if percent is not None:
                    value = percent
                elif is_violation:
                    value = event_category
                else:
                    # Still record evidence if it contains strong keywords but no valid math, just tag appropriately
                    if any(word in text for word in ["fail", "missed", "fraud", "violation"]):
                        value = "Qualitative Failure"
                        is_violation = True
                        event_category = evaluate_legal_outcome(text)
                        
                # --------------------------------
                # Evidence confidence weighting
                # --------------------------------
                if value is not None and score >= 3:
                    evidence.append({
                        "metric": metric,
                        "year": CURRENT_YEAR, # Future iterations will extract precise timeline data here
                        "value": value,
                        "unit": "change %" if isinstance(value, float) else "",
                        "is_regulatory_violation": is_violation, # Add flag for downstream engine
                        "event_category": event_category,
                        "source": url,
                        "confidence_score": score,
                        "source_credibility": credibility,
                        "supporting_quote": quote
                        # In the future: Add raw "2020_value", "2023_value" for Time-Series Analysis comparison
                    })
                
                # --------------------------------
                # Regulatory violation detection fallback
                # --------------------------------
                elif any(word in text for word in [
                    "investigation",
                    "violation",
                    "illegal",
                    "fraud",
                    "scandal",
                    "dieselgate"
                ]):
                    if not any(word in text for word in ["antitrust", "monopoly", "licensing", "competition"]):
                        evidence.append({
                            "metric": metric,
                            "year": CURRENT_YEAR,
                            "value": "Regulatory Violation",
                            "source": url,
                            "confidence_score": score,
                            "event_category": evaluate_legal_outcome(text),
                            "source_credibility": f"Regulatory ({domain})",
                            "supporting_quote": quote
                        })

    except Exception as e:
        print(f"Evidence search error: {e}")

    return evidence


# ==============================
# PROMISE-SPECIFIC VERIFICATION
# ==============================

def find_evidence_for_promise(metric: str, company: str, deadline: int) -> List[Dict]:
    """
    Search trusted sources for evidence verifying a specific promise metric.
    """

    evidence = []
    company_lower = company.lower().split()[0]

    try:

        fetcher = RealTimeDataFetcher()

        search_query = f"{company} {metric} progress climate sustainability"

        results = fetcher.search_duckduckgo(search_query, max_results=8)

        for res in results:

            url = res.get("url", "")
            snippet = res.get("snippet", "")
            text = snippet.lower()

            if not is_trusted_source(url):
                continue
                    
            if company_lower not in text or not any(kw in text for kw in ESG_KEYWORDS) or any(inv in text for inv in INVALID_TERMS):
                continue
            
            score = get_credibility_score(url)
            domain = urlparse(url).netloc.replace("www.", "")
            quote = clean_snippet(snippet)

            # We already matched ESG context, strictly check if we hit excluded topics
            invalid_reasons = []
            
            # Domain / Legal specific exclusion
            legal_exclusion = ["antitrust", "competition law", "corporate lawsuits", "financial disputes"]
            if any(l in snippet.lower() for l in legal_exclusion):
                continue
                
            invalid_terms = ["data center operations", "not emissions", "scaled back", "analysts criticized", "reduction in target"]
            for term in invalid_terms:
                if term in snippet.lower():
                    invalid_reasons.append(term)

            if len(invalid_reasons) > 0:
                continue

            evidence.append({
                "metric": metric,
                "year": CURRENT_YEAR,
                "value": "Reported",
                "source": url,
                "confidence_score": score,
                "source_credibility": f"Score {score} - Verified via {domain}",
                "supporting_quote": quote
            })

    except Exception as e:
        print(f"Promise verification error: {e}")

    return evidence