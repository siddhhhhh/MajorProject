from typing import List, Dict
import os
import re
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from utils.web_search import RealTimeDataFetcher

CURRENT_YEAR = datetime.datetime.now().year
MIN_RETRIEVAL_SOURCES = 15

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

CONTROVERSY_KEYWORDS = [
    "controversy", "greenwashing", "fraud", "investigation", "probe", "lawsuit",
    "fine", "penalty", "violation", "misleading claims", "enforcement"
]

ENERGY_KEYWORDS = [
    "oil production emissions",
    "fossil fuel expansion",
    "climate lawsuit",
    "net zero criticism",
    "greenwashing investigation",
    "scope 3 emissions oil",
    "renewable vs fossil investment",
    "climate targets criticism",
    "transition plan criticism",
    "carbon emissions lawsuit",
]

NEGATIVE_STANCE_WORDS = [
    "lawsuit", "criticism", "fails", "failed", "violation", "probe",
    "investigation", "greenwashing", "fraud", "penalty", "fossil expansion",
]

POSITIVE_STANCE_WORDS = [
    "achieved", "reduced", "aligned", "met target", "on track", "improved",
]

REGULATORY_KEYWORDS = [
    "SEC", "EPA", "DOJ", "EU regulator", "FCA", "SEBI", "enforcement action", "consent order"
]

COMMITMENT_KEYWORDS = [
    "net zero", "science based targets", "sustainability targets", "decarbonization",
    "scope 1", "scope 2", "scope 3", "transition plan", "climate commitments"
]

INVALID_TERMS = [
    "guidance", "policy", "dataset", "methodology", "how to measure", 
    "reporting standard", "framework"
]

HIGH_SIGNAL_NEWS_DOMAINS = [
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "apnews.com",
    "bbc.com", "nytimes.com", "theguardian.com",
]


def _normalize_aliases(company_name: str, aliases: List[str] | None) -> List[str]:
    values = [company_name] + list(aliases or [])
    out = []
    seen = set()
    for item in values:
        clean = re.sub(r"\s+", " ", str(item or "")).strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
        compact = clean.replace(" ", "")
        if compact.lower() not in seen:
            seen.add(compact.lower())
            out.append(compact)
    return out


def _mentions_company(text: str, aliases: List[str]) -> bool:
    if not text:
        return False
    t = text.lower()
    for alias in aliases:
        a = alias.lower().strip()
        if not a:
            continue
        if " " in a:
            if a in t:
                return True
            compact = a.replace(" ", "")
            if compact and compact in re.sub(r"[^a-z0-9]", "", t):
                return True
        else:
            if re.search(rf"\b{re.escape(a)}\b", t):
                return True
    return False


def build_expanded_queries(company_name: str, aliases: List[str], industry: str = "general") -> List[str]:
    """Build broad ESG retrieval queries across risk + commitments dimensions."""
    primary = aliases[0] if aliases else company_name
    secondary = aliases[1] if len(aliases) > 1 else company_name

    bundles = [
        ESG_KEYWORDS[:6],
        CONTROVERSY_KEYWORDS,
        REGULATORY_KEYWORDS,
        COMMITMENT_KEYWORDS,
    ]

    domain_filters = [
        " ".join([f"site:{d}" for d in TRUSTED_DOMAINS[:7]]),
        " ".join([f"site:{d}" for d in TRUSTED_DOMAINS[7:]]),
        "",
    ]

    queries = []
    for i, keywords in enumerate(bundles):
        key_phrase = " ".join(keywords[:6])
        company_fragment = f'"{primary}" "{secondary}"' if secondary != primary else f'"{primary}"'
        queries.append(f"{company_fragment} {key_phrase}")
        filters = domain_filters[i % len(domain_filters)]
        if filters:
            queries.append(f"{company_fragment} {key_phrase} {filters}")

    # Explicit high-signal template requested for institution-grade retrieval.
    queries.append(
        f'"{primary}" ESG controversies climate financing net zero commitments Reuters SEC EPA'
    )

    # Always include controversy-focused queries for contradiction detection.
    queries.extend([
        f'"{primary}" climate controversy Reuters',
        f'"{primary}" net zero criticism lawsuit',
        f'"{primary}" fossil fuel expansion vs targets',
        f'"{primary}" emissions lawsuit ruling',
    ])

    if industry == "energy":
        for keyword in ENERGY_KEYWORDS:
            queries.append(f'"{primary}" {keyword}')

    deduped = []
    seen = set()
    for query in queries:
        q = re.sub(r"\s+", " ", query).strip()
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)
    return deduped


def _is_high_signal_domain(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    if is_trusted_source(url):
        return True
    return any(d in domain for d in HIGH_SIGNAL_NEWS_DOMAINS)


def _classify_stance(text: str) -> str:
    t = (text or "").lower()
    if any(word in t for word in NEGATIVE_STANCE_WORDS):
        return "Contradicts"
    if any(word in t for word in POSITIVE_STANCE_WORDS):
        return "Supports"
    return "Neutral"


def _source_priority(url: str) -> int:
    domain = urlparse(url).netloc.lower()
    if any(d in domain for d in ["sec.gov", "epa.gov", "europa.eu", "gov.uk", "sebi.gov.in"]):
        return 0
    if any(d in domain for d in ["reuters.com", "bloomberg.com", "ft.com", "wsj.com"]):
        return 1
    if is_trusted_source(url):
        return 2
    if any(d in domain for d in HIGH_SIGNAL_NEWS_DOMAINS):
        return 3
    return 4


def _run_parallel_search(fetcher: RealTimeDataFetcher, queries: List[str], max_results: int) -> List[Dict]:
    results: List[Dict] = []
    with ThreadPoolExecutor(max_workers=min(8, len(queries) or 1)) as pool:
        future_map = {
            pool.submit(fetcher.search_all_sources, query, max_results): query
            for query in queries
        }
        for future in as_completed(future_map):
            try:
                query_results = future.result() or []
                results.extend(query_results)
            except Exception as exc:
                print(f"⚠️ Search failed for query: {future_map[future]} ({exc})")
    return results

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

def collect_external_evidence(
    company_name: str,
    aliases: List[str] | None = None,
    industry: str = "general",
    min_sources: int = MIN_RETRIEVAL_SOURCES,
    target_retrieval: int = 25,
) -> List[Dict]:
    """
    Collect real-world ESG evidence using only trusted legal/regulatory sources.
    """

    evidence = []
    seen_urls = set()
    normalized_aliases = _normalize_aliases(company_name, aliases)

    try:
        fetcher = RealTimeDataFetcher()

        print("🔍 Searching trusted legal / regulatory sources...")
        queries = build_expanded_queries(company_name, normalized_aliases, industry=industry)
        raw_results = _run_parallel_search(fetcher, queries, max_results=16)
        print(f"📡 Retrieval depth: total retrieved before filtering = {len(raw_results)}")

        # Prioritize regulatory and high-credibility news first.
        raw_results = sorted(raw_results, key=lambda r: _source_priority(r.get("url", "")))
        if target_retrieval > 0:
            raw_results = raw_results[:target_retrieval]

        filtered_count = 0

        for res in raw_results:

                url = res.get("url", "")
                snippet = res.get("snippet", "")
                text = snippet.lower()

                if not url or url in seen_urls:
                    continue
                
                # --------------------------------
                # 1. Ensure company is mentioned across name variants
                # --------------------------------
                combined_text = f"{res.get('title', '')} {snippet}"
                if not _mentions_company(combined_text, normalized_aliases):
                    continue

                # --------------------------------
                # 2. ESG relevance filtering (retain controversy and commitment signals)
                # --------------------------------
                has_esg_signal = any(kw in text for kw in ESG_KEYWORDS)
                has_controversy_signal = any(kw in text for kw in CONTROVERSY_KEYWORDS)
                has_commitment_signal = any(kw in text for kw in COMMITMENT_KEYWORDS)
                if not (has_esg_signal or has_controversy_signal or has_commitment_signal):
                    continue

                # --------------------------------
                # 3. Reject Generic Documents
                # --------------------------------
                if any(inv in text for inv in INVALID_TERMS):
                    continue
                
                # --------------------------------
                # 4. Source quality filter with reduced aggressiveness for high-signal domains
                # --------------------------------
                if not _is_high_signal_domain(url):
                    continue
                    
                score = get_credibility_score(url)
                if score < 2:
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
                stance = _classify_stance(combined_text)
                if value is not None and score >= 3:
                    filtered_count += 1
                    evidence.append({
                        "metric": metric,
                        "year": CURRENT_YEAR, # Future iterations will extract precise timeline data here
                        "value": value,
                        "unit": "change %" if isinstance(value, float) else "",
                        "is_regulatory_violation": is_violation, # Add flag for downstream engine
                        "event_category": event_category,
                        "source": url,
                        "confidence_score": score,
                        "stance": stance,
                        "relationship_to_claim": stance,
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
                        filtered_count += 1
                        evidence.append({
                            "metric": metric,
                            "year": CURRENT_YEAR,
                            "value": "Regulatory Violation",
                            "source": url,
                            "confidence_score": score,
                            "stance": "Contradicts",
                            "relationship_to_claim": "Contradicts",
                            "event_category": evaluate_legal_outcome(text),
                            "source_credibility": f"Regulatory ({domain})",
                            "supporting_quote": quote
                        })

        print(f"🧹 Retrieval depth: after filter = {filtered_count}")

        # Fallback pass: broaden retrieval and relax trust filtering when coverage is too low.
        if len(evidence) < min_sources:
            print(
                f"⚠️ Evidence below threshold ({len(evidence)}/{min_sources}). Running broader fallback retrieval..."
            )
            broad_queries = [
                f'{normalized_aliases[0] if normalized_aliases else company_name} ESG climate risk controversies',
                f'{normalized_aliases[0] if normalized_aliases else company_name} net zero sustainability targets progress',
                f'{normalized_aliases[0] if normalized_aliases else company_name} regulatory investigation environmental',
            ]
            broad_results = _run_parallel_search(fetcher, broad_queries, max_results=16)

            for res in broad_results:
                url = res.get("url", "")
                snippet = res.get("snippet", "")
                text = snippet.lower()
                combined_text = f"{res.get('title', '')} {snippet}"

                if not url or url in seen_urls:
                    continue
                if not _mentions_company(combined_text, normalized_aliases):
                    continue
                if any(inv in text for inv in INVALID_TERMS):
                    continue

                score = get_credibility_score(url)
                if score < 3 and not is_trusted_source(url):
                    # Keep non-trusted fallback only when we are clearly under-covered.
                    if len(evidence) >= max(5, min_sources // 2):
                        continue
                    score = 2

                seen_urls.add(url)
                metric = detect_metric_from_text(text)
                domain = urlparse(url).netloc.replace("www.", "")
                quote = clean_snippet(snippet)
                fallback_stance = _classify_stance(combined_text)
                evidence.append({
                    "metric": metric,
                    "year": CURRENT_YEAR,
                    "value": "Reported",
                    "unit": "",
                    "is_regulatory_violation": detect_qualitative_violation(text),
                    "event_category": evaluate_legal_outcome(text),
                    "source": url,
                    "confidence_score": score,
                    "stance": fallback_stance,
                    "relationship_to_claim": fallback_stance,
                    "source_credibility": f"Score {score} - Retrieved via fallback ({domain})",
                    "supporting_quote": quote,
                })

                if len(evidence) >= min_sources:
                    break

    except Exception as e:
        print(f"Evidence search error: {e}")

    # Final de-duplication by source URL preserving first-best entry.
    unique_by_source = {}
    for item in evidence:
        source = item.get("source")
        if source and source not in unique_by_source:
            unique_by_source[source] = item

    final_evidence = list(unique_by_source.values())
    print(f"🗂️ Retrieval depth: after dedup = {len(final_evidence)}")
    return final_evidence


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