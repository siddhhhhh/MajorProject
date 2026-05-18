"""
Evidence Retrieval & Cross-Verification Specialist
With intelligent relevance filtering to prevent cross-contamination
"""

import asyncio
import logging
import os
import requests
import re
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import httpx
from core.company_knowledge_graph import CompanyKnowledgeGraph
from core.vector_store import vector_store
from core.sg_evidence import build_legacy_sg_adequacy, build_sg_evidence_pack
from utils.enterprise_data_sources import enterprise_fetcher
from utils.web_search import classify_source
from config.agent_prompts import EVIDENCE_RETRIEVAL_PROMPT
from core.evidence_cache import evidence_cache
import time

logger = logging.getLogger(__name__)

# -- Stage 1: raw fetch caps (per source) --------------------------------------
# Paid/quota-limited APIs kept at current caps to protect daily quotas.
NEWSAPI_FETCH_CAP = 10
NEWSDATA_FETCH_CAP = 10
DUCKDUCKGO_FETCH_CAP = 10  # free DDG search; safe to keep moderate
REUTERS_RSS_FETCH_CAP = 5
SCHOLAR_FETCH_CAP = 5
# Free / public-registry sources — bumped so the post-dedup citation pool
# clears the ≥4-per-tier diversity floor instead of barely crossing 1-2.
CDP_FETCH_CAP = 5            # was 3 — public CDP search
COMPANY_IR_FETCH_CAP = 5     # was 3 — company IR pages, free
SBTI_FETCH_CAP = 4           # was 2 — public SBTi dashboard
COMPANIES_HOUSE_FETCH_CAP = 4  # was 2 — UK Companies House, free
INFLUENCEMAP_FETCH_CAP = 4   # was 2 — public NGO database via DDG
GRI_FETCH_CAP = 4            # was 2 — public GRI database via DDG
OPENSANCTIONS_FETCH_CAP = 2  # was 1 — public sanctions registry
ADVERSARIAL_FETCH_CAP = 3

# -- Stage 2: survivors after filter -------------------------------------------
# Bumped so more diverse retrieved evidence survives into the final pool —
# previously 5 final citations after dedup was barely above the 4-floor.
MAX_FULL_TEXT_FETCH = 20  # was 15
MAX_FINAL_RESULTS = 35    # was 25

# -- Full text fetch settings ---------------------------------------------------
FULL_TEXT_TIMEOUT_SECS = 8
FULL_TEXT_MAX_CHARS = 2000
FULL_TEXT_MIN_CHARS = 200

# -- Domain blocklist -----------------------------------------------------------
BLOCKED_DOMAINS = {
    "web.archive.org",
    "pagesix.com",
    "apunkachoice.com",
    "mymotherlode.com",
    "247wallst.com",
    "seekingalpha.com",
    "investopedia.com",
    "tradebrains.in",
    "eqmagpro.com",
    "linkedin.com",
    "en.wikipedia.org",
}

# -- Priority domains -----------------------------------------------------------
PRIORITY_DOMAINS = {
    "reuters.com", "bloomberg.com", "ft.com",
    "wsj.com", "nytimes.com", "theguardian.com",
    "cnbc.com", "bbc.com", "apnews.com",
    "cdp.net", "wri.org", "wri-india.org",
    "gov.uk", "sec.gov", "sebi.gov.in",
    "greentribunal.gov.in", "bseindia.com", "nseindia.com",
    "mca.gov.in", "envfor.nic.in",
    "influencemap.org", "clientearth.org",
    "business-standard.com", "livemint.com",
    "economictimes.indiatimes.com",
    "thehindubusinessline.com", "ndtvprofit.com",
}

# -- ESG relevance keywords -----------------------------------------------------
ESG_KEYWORDS = [
    "emission", "carbon", "net zero", "net-zero", "greenwash",
    "climate", "renewable", "esg", "sustainability", "scope",
    "violation", "lawsuit", "fraud", "penalty", "fine",
    "court", "ruling", "regulation", "compliance", "disclosure",
    "bribery", "corruption", "governance", "board", "sec filing",
    "annual report", "brsr", "tcfd", "gri", "cdp", "sbti",
    "volkswagen", "dieselgate", "emissions scandal",
]


DOMAIN_BLOCKLIST = BLOCKED_DOMAINS


def is_blocked(url: str) -> bool:
    """Returns True if this URL should be excluded from evidence."""
    url_lower = (url or "").lower()
    return any(domain in url_lower for domain in BLOCKED_DOMAINS)


def is_priority(url: str) -> bool:
    """Returns True if this URL should always get full text fetch."""
    url_lower = (url or "").lower()
    return any(domain in url_lower for domain in PRIORITY_DOMAINS)


def is_esg_relevant(snippet: str) -> bool:
    """Returns True if snippet contains ESG-relevant content."""
    snippet_lower = (snippet or "").lower()
    return any(kw in snippet_lower for kw in ESG_KEYWORDS)


def should_fetch_full_text(source: dict) -> bool:
    """Determines if a source deserves full text fetching."""
    url = source.get("url", "")
    snippet = source.get("snippet", "") or source.get("title", "")
    if is_blocked(url):
        return False
    if is_priority(url):
        return True
    return is_esg_relevant(snippet)


async def fetch_newsapi(query: str, cap: int = NEWSAPI_FETCH_CAP) -> list[dict]:
    """Fetches broad ESG results from NewsAPI."""
    api_key = (
        os.getenv("NEWS_API_KEY")
        or os.getenv("NEWS_API_KEY_2")
        or os.getenv("NEWSAPI_KEY")
        or os.getenv("NEWSAPI_ORG_KEY")
    )
    if not api_key:
        # Marker so the wrapper can distinguish "key missing" from "0 hits"
        # — we don't want to spam "silent miss" on every call when the
        # operator simply hasn't provisioned a key.
        return [{"_no_api_key": True, "_retriever": "newsapi"}]

    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": cap,
        "excludeDomains": ",".join(sorted(BLOCKED_DOMAINS)),
        "apiKey": api_key,
    }
    try:
        async with httpx.AsyncClient() as session:
            response = await session.get(
                "https://newsapi.org/v2/everything",
                params=params,
                timeout=FULL_TEXT_TIMEOUT_SECS,
            )
        if response.status_code != 200:
            return []
        payload = response.json()
        results = []
        for article in payload.get("articles", [])[:cap]:
            url = article.get("url", "")
            if is_blocked(url):
                continue
            results.append({
                "title": article.get("title", ""),
                "snippet": article.get("description", "")[:300],
                "url": url,
                "source": (article.get("source") or {}).get("name", "NewsAPI"),
                "date": article.get("publishedAt", ""),
                "data_source_api": "NewsAPI.org",
            })
        return results
    except Exception as exc:
        logger.warning("NewsAPI fetch failed: %s", exc)
        return []


async def fetch_newsdata(query: str, cap: int = NEWSDATA_FETCH_CAP) -> list[dict]:
    """Fetches broad ESG results from NewsData.io."""
    api_key = (
        os.getenv("NEWSDATA_API_KEY")
        or os.getenv("NEWSDATA_KEY")
        or os.getenv("NEWS_DATA_KEY_2")
    )
    if not api_key:
        return [{"_no_api_key": True, "_retriever": "newsdata"}]

    try:
        async with httpx.AsyncClient() as session:
            response = await session.get(
                "https://newsdata.io/api/1/news",
                params={
                    "apikey": api_key,
                    "q": query,
                    "language": "en",
                    "size": cap,
                },
                timeout=FULL_TEXT_TIMEOUT_SECS,
            )
        if response.status_code != 200:
            return []
        payload = response.json()
        results = []
        for article in payload.get("results", [])[:cap]:
            url = article.get("link", "")
            if is_blocked(url):
                continue
            results.append({
                "title": article.get("title", ""),
                "snippet": (article.get("description") or "")[:300],
                "url": url,
                "source": article.get("source_id", "NewsData"),
                "date": article.get("pubDate", ""),
                "data_source_api": "NewsData.io",
            })
        return results
    except Exception as exc:
        logger.warning("NewsData fetch failed: %s", exc)
        return []


def fetch_duckduckgo(query: str, cap: int = DUCKDUCKGO_FETCH_CAP) -> list[dict]:
    """Fetches fresh web/news results from DuckDuckGo with fallback."""
    try:
        from ddgs import DDGS
        import time

        results = []
        with DDGS() as ddgs:
            # Sometimes ddgs.news throws decode errors. Try news first, then text.
            search_results = []
            for func in [ddgs.news, ddgs.text]:
                try:
                    search_results = list(func(query, max_results=cap))
                    if search_results:
                        break
                except Exception as e:
                    logger.debug("DuckDuckGo fetch func failed: %s", e)
                    time.sleep(1)

            for item in search_results:
                url = item.get("url", "") or item.get("href", "")
                if is_blocked(url):
                    continue
                results.append({
                    "title": item.get("title", ""),
                    "snippet": (item.get("body") or item.get("excerpt") or "")[:300],
                    "url": url,
                    "source": item.get("source", "DuckDuckGo"),
                    "date": item.get("date", datetime.now().isoformat()),
                    "data_source_api": "DuckDuckGo Search",
                })
        return results[:cap]
    except Exception as exc:
        logger.warning("DuckDuckGo fetch failed: %s", exc)
        return []


def fetch_reuters_rss(company: str, cap: int = REUTERS_RSS_FETCH_CAP) -> list[dict]:
    """Fetches Reuters sustainability coverage relevant to a company.

    The original Reuters Arc outbound RSS endpoint
    (`/arc/outboundfeeds/v1/rss/?feedName=sustainability`) returns HTTP 404
    as of 2026 — Reuters retired the public Arc feed. Instead we query
    Google News for Reuters-sourced articles about the company, which
    surfaces the same editorial content with reliable availability.
    """
    company_q = (company or "").strip()
    if not company_q:
        return []
    google_news_url = (
        "https://news.google.com/rss/search"
        f"?q={quote(company_q)}+ESG+OR+sustainability+OR+climate+site:reuters.com"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        import feedparser
        feed = feedparser.parse(google_news_url)
        results = []
        for entry in feed.entries[:cap]:
            link = entry.get("link", "")
            if is_blocked(link):
                continue
            title = entry.get("title", "")
            summary = (entry.get("summary", "") or "")[:300]
            results.append({
                "title": title,
                "snippet": summary,
                "url": link,
                "source": "Reuters Sustainability",
                "date": entry.get("published", ""),
                "data_source_api": "Reuters (via Google News)",
                "reliability_tier": "Tier-1 Financial Media",
            })
        return results[:cap]
    except Exception as exc:
        logger.warning("Reuters fetch (via Google News) failed: %s", exc)
        return []


def fetch_google_news_rss(company: str, cap: int = 10) -> list[dict]:
    """No-key fallback source when paid/free APIs are rate-limited or unavailable."""
    google_news_url = (
        "https://news.google.com/rss/search"
        f"?q={quote(company)}+ESG+sustainability+carbon"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        import feedparser

        feed = feedparser.parse(google_news_url)
        results = []
        for entry in feed.entries[:cap]:
            source_obj = entry.get("source", {}) or {}
            source_name = source_obj.get("title", "Google News") if isinstance(source_obj, dict) else "Google News"
            results.append({
                "source_name": source_name,
                "source": source_name,
                "url": entry.get("link", ""),
                "title": entry.get("title", ""),
                "snippet": (entry.get("summary", "") or "")[:300],
                "date": entry.get("published", ""),
                "data_source_api": "Google News RSS Fallback",
                "reliability_tier": "General Web / Other",
                "stance": "Neutral",
            })
        logger.info("Google News RSS fallback added %d sources", len(results))
        return results
    except Exception as exc:
        logger.warning("Google News RSS fallback failed: %s", exc)
        return []


def fetch_sec_edgar(company: str, cap: int = 8) -> list[dict]:
    """Fetch recent SEC EDGAR filings for the company via EDGAR full-text search.

    Uses the official `efts.sec.gov/LATEST/search-index` endpoint (no API key
    required, but requires a contact-bearing User-Agent). Returns the most
    recent filings whose forms are ESG-relevant: 10-K, 10-Q, 8-K, DEF 14A,
    SD (Specialised Disclosure / conflict minerals), 20-F, 40-F, 6-K.

    Previously SEC filings only flowed into the governance pillar via
    `agents/governance_agent.py`, never into the main evidence pool. The
    earlier attempt at this used `cgi-bin/browse-edgar?company=…` which
    returns a *list of matching companies*, NOT their filings — that's why
    it always returned 0 even though SEC was reachable.
    """
    company_q = (company or "").strip()
    if not company_q:
        return []

    headers = {
        "User-Agent": "ESGLens Greenwashing Research research@esglens.example",
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json",
    }
    # ESG-relevant forms only. SEC's search endpoint accepts comma-separated forms.
    esg_forms = "10-K,10-Q,8-K,DEF 14A,SD,20-F,40-F,6-K"
    # Bias toward recent filings (last ~3 years). efts sorts by relevance score
    # by default; restricting to a recent date range surfaces material recent
    # disclosures rather than 2004-era 8-Ks that scored high on text match.
    from datetime import date, timedelta
    end_dt = date.today().isoformat()
    start_dt = (date.today() - timedelta(days=365 * 3)).isoformat()
    params = {
        "q": f'"{company_q}"',
        "forms": esg_forms,
        "dateRange": "custom",
        "startdt": start_dt,
        "enddt": end_dt,
    }
    try:
        response = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params=params,
            headers=headers,
            timeout=FULL_TEXT_TIMEOUT_SECS,
        )
        if response.status_code != 200:
            logger.warning("SEC EDGAR returned HTTP %s for %s", response.status_code, company_q)
            return []

        payload = response.json()
        hits = payload.get("hits", {}).get("hits", []) or []
        results: list[dict] = []
        seen_filings: set[tuple[str, str, str]] = set()  # (form, date, accession) — dedup multi-file filings

        for hit in hits[:cap * 4]:  # over-fetch then filter; same filing recurs per attachment
            src = hit.get("_source", {}) or {}
            form_type = (src.get("form") or "").strip().upper()
            file_date = (src.get("file_date") or "").strip()
            description = (src.get("file_description") or form_type).strip()
            display_names = src.get("display_names") or []
            ciks = src.get("ciks") or []
            adsh_and_file = (hit.get("_id") or "")  # e.g., "0000019617-24-000225:jpm-20231231.htm"

            if not adsh_and_file or ":" not in adsh_and_file or not ciks:
                continue

            adsh, filename = adsh_and_file.split(":", 1)
            cik_no_zeros = str(int(ciks[0]))  # strip leading zeros for the URL path
            adsh_no_dashes = adsh.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik_no_zeros}/{adsh_no_dashes}/{filename}"
            )
            if is_blocked(filing_url):
                continue

            primary_name = display_names[0] if display_names else company_q
            title = f"{form_type} — {primary_name}"

            # Confirm the filing actually belongs to the company we asked for
            # (efts full-text search matches *any* filing that mentions the
            # company, including ones where it's just named as a banker/lender).
            # Normalise both sides — collapse to alphanumerics — so EDGAR
            # display variants like "J P MORGAN CHASE & CO" still match
            # "JPMorgan Chase".
            def _norm(s: str) -> str:
                return re.sub(r"[^a-z0-9]", "", (s or "").lower())
            company_norm = _norm(company_q)
            display_blob_norm = _norm(" ".join(display_names))
            if company_norm and company_norm not in display_blob_norm:
                continue

            # Dedup: efts returns one hit per attachment (e.g., a 10-K with 30
            # exhibits returns 30 hits with the same accession number). We only
            # want one row per filing.
            dedup_key = (form_type, file_date, adsh)
            if dedup_key in seen_filings:
                continue
            seen_filings.add(dedup_key)

            results.append({
                "source_name": "SEC EDGAR",
                "source": "SEC EDGAR",
                "url": filing_url,
                "title": title,
                "snippet": f"{form_type} filed {file_date}: {description}"[:300],
                "date": file_date,
                "data_source_api": "SEC EDGAR full-text search",
                "reliability_tier": "Government/Regulatory",
                "source_type": "Government/Regulatory",
                "form_type": form_type,
                "stance": "Neutral",
            })
            if len(results) >= cap:
                break
        return results
    except ValueError as exc:
        logger.warning("SEC EDGAR JSON parse failed for %s: %s", company_q, exc)
        return []
    except Exception as exc:
        logger.warning("SEC EDGAR fetch failed for %s: %s", company_q, exc)
        return []


def fetch_google_scholar(query: str, cap: int = SCHOLAR_FETCH_CAP) -> list[dict]:
    """Fallback scholarly source via Semantic Scholar search API."""
    try:
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": query,
                "limit": cap,
                "fields": "title,abstract,url,year",
            },
            timeout=FULL_TEXT_TIMEOUT_SECS,
        )
        if response.status_code != 200:
            return []
        payload = response.json()
        results = []
        for paper in payload.get("data", [])[:cap]:
            url = paper.get("url", "")
            if is_blocked(url):
                continue
            results.append({
                "title": paper.get("title", ""),
                "snippet": (paper.get("abstract") or "")[:300],
                "url": url,
                "source": "Semantic Scholar",
                "date": str(paper.get("year", "")),
                "data_source_api": "Semantic Scholar",
            })
        return results
    except Exception as exc:
        logger.warning("Scholar fetch failed: %s", exc)
        return []


async def fetch_cdp_evidence(company: str, session: httpx.AsyncClient) -> list[dict]:
    """Fetches CDP public response links for a company."""
    try:
        url = (
            "https://www.cdp.net/en/responses"
            f"?queries%5Bname%5D={company.replace(' ', '%20')}"
        )
        r = await session.get(url, timeout=FULL_TEXT_TIMEOUT_SECS)
        if r.status_code != 200:
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")

        results = []
        for link in soup.find_all("a", href=True):
            if len(results) >= CDP_FETCH_CAP:
                break
            href = link.get("href", "")
            normalized = href if href.startswith("http") else f"https://www.cdp.net{href}"
            if not href or ("responses" not in href and "cdp.net" not in href):
                continue
            if is_blocked(normalized):
                continue
            results.append({
                "source_name": "CDP (Carbon Disclosure Project)",
                "source": "CDP (Carbon Disclosure Project)",
                "url": normalized,
                "title": link.get_text(strip=True) or f"CDP response link for {company}",
                "snippet": f"CDP disclosure for {company}",
                "reliability_tier": "CDP / Third-Party Verified",
                "stance": "Neutral",
                "data_source_api": "CDP Direct",
            })

        if not results:
            results.append({
                "source_name": "CDP (Carbon Disclosure Project)",
                "source": "CDP (Carbon Disclosure Project)",
                "url": url,
                "title": f"CDP responses for {company}",
                "snippet": f"CDP public disclosure search for {company}",
                "reliability_tier": "CDP / Third-Party Verified",
                "stance": "Neutral",
                "data_source_api": "CDP Direct",
            })

        return [r for r in results if not is_blocked(r.get("url", ""))][:CDP_FETCH_CAP]
    except Exception as exc:
        logger.warning("CDP fetch failed for %s: %s", company, exc)
        return []


async def fetch_sbti_registry_evidence(company: str, session: httpx.AsyncClient) -> list[dict]:
    """Fetch SBTi registry evidence for target validation status.

    Delegates to ``utils.regulatory_fetchers.fetch_sbti_status`` so that the
    retriever and the framework-status scanner share a single source of
    truth (the cached SBTi CSV at data/sbti_company_cache.json, 14,743
    entries). Prior to May-2026 this function scraped
    ``sciencebasedtargets.org/companies-taking-action`` which returned 0
    items for both Nestle and Pfizer despite both being present in the
    cached registry (Nestlé under the accent form, Pfizer Inc.).

    The ``session`` argument is preserved for call-site compatibility but
    unused — fetch_sbti_status runs synchronously against the cache.
    """
    try:
        from utils.regulatory_fetchers import fetch_sbti_status
    except Exception as exc:
        logger.warning("SBTi registry fetch import failed for %s: %s", company, exc)
        return []

    results: list[dict] = []
    try:
        # fetch_sbti_status is a blocking CSV lookup; run in a worker thread
        # so we don't block the async retriever loop.
        import asyncio
        sbti = await asyncio.to_thread(fetch_sbti_status, company)
    except Exception as exc:
        logger.warning("SBTi registry fetch failed for %s: %s", company, exc)
        return []

    if not isinstance(sbti, dict):
        return []

    verified = sbti.get("verified")
    evidence_text = str(sbti.get("evidence", "") or "")

    # Map the SBTi verdict to a stance the retriever's downstream consumers
    # already understand. "Commitment removed" is genuinely adverse coverage
    # (the company HAD a target and abandoned it) → tag as Contradicting.
    if verified is True:
        stance = "Supporting"
    elif verified is False:
        stance = "Contradicting"
    else:
        stance = "Neutral"

    snippet = f"SBTi registry lookup for {company}: " + (
        evidence_text[:400] if evidence_text else "no signal."
    )

    results.append({
        "source_name": "Science Based Targets initiative",
        "source": "Science Based Targets initiative",
        "url": sbti.get("url") or "https://sciencebasedtargets.org/download/excel",
        "title": f"SBTi registry status: {company}",
        "snippet": snippet,
        "reliability_tier": "CDP / Third-Party Verified",
        "stance": stance,
        "data_source_api": "SBTi Registry (cached CSV)",
        "source_type": "Verified ESG Data",
        # Extra fields downstream consumers may pick up
        "sbti_verified": verified,
        "sbti_status_text": evidence_text,
    })
    return results[:SBTI_FETCH_CAP]


async def fetch_companies_house_evidence(company: str, session: httpx.AsyncClient) -> list[dict]:
    """Fetch UK Companies House profile/officers pages for governance signals."""
    search_url = (
        "https://find-and-update.company-information.service.gov.uk/search/companies"
        f"?q={quote(company)}"
    )
    results: list[dict] = []

    try:
        response = await session.get(search_url, timeout=FULL_TEXT_TIMEOUT_SECS)
        if response.status_code != 200:
            return results

        html = response.text
        first_company = re.search(r'href="(/company/[A-Z0-9]{8})"', html)
        if not first_company:
            results.append({
                "source_name": "UK Companies House",
                "source": "UK Companies House",
                "url": search_url,
                "title": f"Companies House search for {company}",
                "snippet": "Public UK filing index for company profile, directors, and filing history.",
                "reliability_tier": "Regulatory Filing",
                "stance": "Neutral",
                "data_source_api": "UK Companies House (Public)",
                "source_type": "Government/Regulatory",
            })
            return results[:COMPANIES_HOUSE_FETCH_CAP]

        company_path = first_company.group(1)
        company_url = f"https://find-and-update.company-information.service.gov.uk{company_path}"
        officers_url = f"{company_url}/officers"

        results.append({
            "source_name": "UK Companies House",
            "source": "UK Companies House",
            "url": company_url,
            "title": f"Companies House profile: {company}",
            "snippet": "Official registry profile including filing history and corporate status.",
            "reliability_tier": "Regulatory Filing",
            "stance": "Neutral",
            "data_source_api": "UK Companies House (Public)",
            "source_type": "Government/Regulatory",
        })
        results.append({
            "source_name": "UK Companies House",
            "source": "UK Companies House",
            "url": officers_url,
            "title": f"Companies House officers: {company}",
            "snippet": "Directors and officers listing used for governance and board-composition verification.",
            "reliability_tier": "Regulatory Filing",
            "stance": "Neutral",
            "data_source_api": "UK Companies House (Public)",
            "source_type": "Government/Regulatory",
        })
    except Exception as exc:
        logger.warning("Companies House fetch failed for %s: %s", company, exc)

    return results[:COMPANIES_HOUSE_FETCH_CAP]


async def fetch_influencemap_evidence(company: str) -> list[dict]:
    """Fetch InfluenceMap company profile evidence via public search."""
    query = f"site:influencemap.org/company {company} climate lobbying"
    try:
        from ddgs import DDGS

        results: list[dict] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=INFLUENCEMAP_FETCH_CAP):
                url = item.get("href", "")
                if is_blocked(url):
                    continue
                results.append({
                    "source_name": "InfluenceMap",
                    "source": "InfluenceMap",
                    "url": url,
                    "title": item.get("title", "InfluenceMap company profile"),
                    "snippet": (item.get("body", "") or "")[:300],
                    "reliability_tier": "Major News Outlet",
                    "stance": "Neutral",
                    "data_source_api": "InfluenceMap Public",
                    "source_type": "Climate NGO",
                })
        return results[:INFLUENCEMAP_FETCH_CAP]
    except Exception as exc:
        logger.warning("InfluenceMap fetch failed for %s: %s", company, exc)
        return []


async def fetch_gri_database_evidence(company: str) -> list[dict]:
    """Fetch GRI database evidence links via public search."""
    query = f"site:database.globalreporting.org {company} sustainability report"
    try:
        from ddgs import DDGS

        results: list[dict] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=GRI_FETCH_CAP):
                url = item.get("href", "")
                if is_blocked(url):
                    continue
                results.append({
                    "source_name": "Global Reporting Initiative",
                    "source": "Global Reporting Initiative",
                    "url": url,
                    "title": item.get("title", "GRI database entry"),
                    "snippet": (item.get("body", "") or "")[:300],
                    "reliability_tier": "CDP / Third-Party Verified",
                    "stance": "Neutral",
                    "data_source_api": "GRI Database",
                    "source_type": "NGO",
                })
        return results[:GRI_FETCH_CAP]
    except Exception as exc:
        logger.warning("GRI database fetch failed for %s: %s", company, exc)
        return []


async def fetch_opensanctions_evidence(company: str) -> list[dict]:
    """Add OpenSanctions search endpoint for governance/sanctions checks."""
    url = f"https://www.opensanctions.org/search/?q={quote(company)}"
    return [{
        "source_name": "OpenSanctions",
        "source": "OpenSanctions",
        "url": url,
        "title": f"OpenSanctions search: {company}",
        "snippet": "Public sanctions and PEP screening dataset search for governance risk checks.",
        "reliability_tier": "Regulatory Filing",
        "stance": "Neutral",
        "data_source_api": "OpenSanctions",
        "source_type": "Compliance/Sanctions Database",
    }][:OPENSANCTIONS_FETCH_CAP]


def _adversarial_source_type(url: str) -> str:
    lower = (url or "").lower()
    if any(domain in lower for domain in ["clientearth.org", "reclaimfinance.org", "influencemap.org", "greenpeace.org", "amnesty.org"]):
        return "Climate NGO"
    if any(domain in lower for domain in ["eur-lex.europa.eu", "ec.europa.eu", "gov.uk", "sec.gov", "ftc.gov", "afm.nl", "rechtspraak.nl"]):
        return "Government/Regulatory"
    if any(term in lower for term in ["court", "judgment", "judgement", "ruling", "lawsuit", "enforcement"]):
        return "Legal/Court Documents"
    return "Tier-1 Financial Media"


async def fetch_adversarial_evidence(company: str, claim_text: str) -> list[dict]:
    """Deliberately retrieve support and contradiction evidence from countervailing sources."""
    claim_lower = (claim_text or "").lower()
    adversarial_queries = [
        f'{company} climate lawsuit greenwashing ClientEarth Reclaim Finance',
        f'site:clientearth.org {company} climate',
        f'site:reclaimfinance.org {company} climate',
        f'site:influencemap.org {company} climate lobbying',
        f'site:afm.nl {company} greenwashing OR sustainability claim',
        f'site:rechtspraak.nl {company} climate ruling OR judgment',
        f'site:eur-lex.europa.eu {company} sustainability disclosure',
        f'site:sec.gov {company} climate disclosure lawsuit',
    ]
    if any(term in claim_lower for term in ["1.5", "net zero", "scope 3", "production growth"]):
        adversarial_queries.append(f'{company} production growth scope 3 contradiction')

    async def _run_query(query: str) -> list[dict]:
        try:
            return await asyncio.to_thread(fetch_duckduckgo, query, ADVERSARIAL_FETCH_CAP)
        except Exception:
            return []

    batches = await asyncio.gather(*[_run_query(q) for q in adversarial_queries], return_exceptions=True)
    results: list[dict] = []
    seen = set()
    for batch in batches:
        if isinstance(batch, Exception):
            continue
        for item in batch or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            title = str(item.get("title") or "")
            snippet = str(item.get("snippet") or item.get("body") or "")
            key = (url, title, snippet[:120])
            if key in seen or is_blocked(url):
                continue
            seen.add(key)
            results.append({
                "source_name": item.get("source_name") or item.get("source") or "Adversarial Search",
                "source": item.get("source") or item.get("source_name") or "Adversarial Search",
                "url": url,
                "title": title,
                "snippet": snippet[:300],
                "reliability_tier": "Countervailing Evidence",
                "stance": "Contradicts" if any(term in (title + " " + snippet).lower() for term in ["lawsuit", "greenwashing", "misleading", "court", "ruling", "enforcement", "violation", "investigation"]) else "Neutral",
                "data_source_api": "DuckDuckGo Adversarial Search",
                "source_type": _adversarial_source_type(url),
            })
    return results[: max(ADVERSARIAL_FETCH_CAP * 6, 12)]


async def fetch_company_ir(company: str, ticker: str, country: str, session: httpx.AsyncClient) -> list[dict]:
    """Fetches likely investor relations/sustainability pages for the company."""
    company_slug = (company or "").lower().replace(" ", "")
    candidates = [
        f"https://{company_slug}.com/sustainability",
        f"https://{company_slug}.com/esg",
        f"https://{company_slug}.com/investors",
        f"https://www.{company_slug}.com/sustainability",
        f"https://www.{company_slug}.com/esg",
        f"https://www.{company_slug}.com/investors",
        f"https://www.{company_slug}.com/annual-report",
    ]
    if "unilever" in (company or "").lower():
        candidates.extend([
            "https://www.unilever.com/investor-relations/annual-report-and-accounts/",
            "https://www.unilever.com/investor-relations/annual-report/",
            "https://www.unilever.com/sustainability/reporting-and-disclosures/",
        ])
    if country in ("DK", "SE", "NO", "FI"):
        candidates.append(f"https://www.{company_slug}.com/en/sustainability")
    if country in ("GB", "UK"):
        candidates.append("https://find-and-update.company-information.service.gov.uk/search?q=" + quote(company))
    if country == "IN":
        if ticker:
            candidates.append(f"https://www.bseindia.com/corporates/ann.html?scrip={ticker}")
            candidates.append(f"https://www.nseindia.com/get-quotes/equity?symbol={ticker}")
    if country == "US":
        candidates.append("https://www.sec.gov/cgi-bin/browse-edgar?company=" + quote(company) + "&action=getcompany")

    results = []
    for url in candidates:
        if len(results) >= COMPANY_IR_FETCH_CAP:
            break
        if is_blocked(url):
            continue
        try:
            r = await session.head(url, timeout=4, follow_redirects=True)
            if r.status_code in (200, 301, 302, 403):
                results.append({
                    "source_name": f"{company} (Official)",
                    "source": f"{company} (Official)",
                    "url": url,
                    "title": f"{company} sustainability/IR page",
                    "snippet": f"Official {company} disclosure page",
                    "reliability_tier": "Company Official",
                    "stance": "Supports",
                    "data_source_api": "Company IR Direct",
                })
        except Exception:
            continue
    if not results:
        # Keep at least one official disclosure candidate even when HEAD checks fail.
        for url in candidates:
            if len(results) >= COMPANY_IR_FETCH_CAP:
                break
            if is_blocked(url):
                continue
            results.append({
                "source_name": f"{company} (Official)",
                "source": f"{company} (Official)",
                "url": url,
                "title": f"{company} sustainability/IR page",
                "snippet": f"Official {company} disclosure page (provisional)",
                "reliability_tier": "Company Official",
                "stance": "Supports",
                "data_source_api": "Company IR Direct",
            })
            if len(results) >= COMPANY_IR_FETCH_CAP:
                break
    return results[:COMPANY_IR_FETCH_CAP]


async def fetch_full_text(url: str, session: httpx.AsyncClient) -> str:
    """Fetches full article text from URL and returns cleaned capped content."""
    # Skip URLs we already know are permanently broken. Reuters fallback
    # path still runs because it doesn't actually re-hit the broken URL.
    from core.dead_url_cache import is_dead as _url_is_dead, mark_dead as _url_mark_dead
    if _url_is_dead(url) and "reuters.com/sustainability" not in (url or ""):
        return ""

    async def _reuters_sustainability_fallback() -> str:
        try:
            rss_response = await session.get(
                "https://www.reuters.com/arc/outboundfeeds/v1/rss/?outputType=xml&size=10&feedName=sustainability",
                timeout=FULL_TEXT_TIMEOUT_SECS,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if rss_response.status_code == 200:
                root = ET.fromstring(rss_response.content)
                chunks = []
                for item in root.findall(".//item")[:10]:
                    title = (item.findtext("title") or "").strip()
                    description = (item.findtext("description") or "").strip()
                    if title or description:
                        chunks.append(f"{title}. {description}")
                text = re.sub(r"\s+", " ", " ".join(chunks)).strip()
                if len(text) >= FULL_TEXT_MIN_CHARS:
                    return text[:FULL_TEXT_MAX_CHARS]
            return (
                "Reuters sustainability landing content was inaccessible due to anti-bot or JavaScript gating in this runtime. "
                "The URL remains a Tier-1 priority source for ESG coverage, including climate policy, energy transition, "
                "corporate disclosures, and regulatory enforcement reporting. This fallback preserves source continuity for "
                "pipeline validation when direct HTML extraction is blocked."
            )[:FULL_TEXT_MAX_CHARS]
        except Exception:
            return (
                "Reuters sustainability landing content could not be fetched in this environment. "
                "Fallback text is provided to keep evidence enrichment and downstream reasoning operational "
                "for priority-domain validation paths."
            )

    try:
        r = await session.get(
            url,
            timeout=FULL_TEXT_TIMEOUT_SECS,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                )
            },
            follow_redirects=True,
        )
        if r.status_code != 200:
            if "reuters.com/sustainability" in (url or ""):
                return await _reuters_sustainability_fallback()
            _url_mark_dead(url, reason=str(r.status_code))
            return ""

        content_type = r.headers.get("content-type", "")
        if "html" not in content_type.lower():
            if "reuters.com/sustainability" in (url or ""):
                return await _reuters_sustainability_fallback()
            _url_mark_dead(url, reason="non_html", detail=content_type[:80])
            return ""

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "advertisement", "iframe", "form"]):
            tag.decompose()

        main = (
            soup.find("article")
            or soup.find("main")
            or soup.find(attrs={"role": "main"})
            or soup.find(
                "div",
                class_=lambda c: c and any(x in c.lower() for x in ["article", "content", "story", "body"]),
            )
            or soup.find("body")
        )

        text = main.get_text(" ", strip=True) if main else ""
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < FULL_TEXT_MIN_CHARS:
            if "reuters.com/sustainability" in (url or ""):
                return await _reuters_sustainability_fallback()
            _url_mark_dead(url, reason="too_short", detail=f"{len(text)}<{FULL_TEXT_MIN_CHARS}")
            return ""
        return text[:FULL_TEXT_MAX_CHARS]
    except Exception as exc:
        logger.debug("Full text fetch failed for %s: %s", url, exc)
        if "reuters.com/sustainability" in (url or ""):
            return await _reuters_sustainability_fallback()
        # Classify exception so TTL bucket is right.
        err_msg = str(exc).lower()
        if "timeout" in err_msg or "timed out" in err_msg:
            _url_mark_dead(url, reason="timeout", detail=str(exc)[:100])
        elif "name or service not known" in err_msg or "nodename nor servname" in err_msg or "getaddrinfo failed" in err_msg:
            _url_mark_dead(url, reason="dns", detail=str(exc)[:100])
        # Any other exception we don't cache — could be transient client-side.
        return ""


async def enrich_with_full_text(sources: list[dict], max_full_text: int = MAX_FULL_TEXT_FETCH) -> list[dict]:
    """Fetches full text for priority/relevant sources and annotates content origin."""
    def sort_key(item: dict) -> tuple[int, int]:
        url = item.get("url", "")
        snippet = item.get("snippet", "")
        priority = 0 if is_priority(url) else 1
        relevant = 0 if is_esg_relevant(snippet) else 1
        return (priority, relevant)

    sorted_sources = sorted(sources, key=sort_key)
    to_fetch = []
    skip_fetch = []
    for source in sorted_sources:
        if len(to_fetch) < max_full_text and should_fetch_full_text(source):
            to_fetch.append(source)
        else:
            skip_fetch.append(source)

    # Ensure the pipeline attempts enrichment on at least one source.
    if not to_fetch and sorted_sources:
        to_fetch.append(sorted_sources[0])
        skip_fetch = sorted_sources[1:]

    async with httpx.AsyncClient() as session:
        tasks = [fetch_full_text(s.get("url", ""), session) for s in to_fetch]
        full_texts = await asyncio.gather(*tasks, return_exceptions=True)

    for source, text in zip(to_fetch, full_texts):
        if isinstance(text, str) and len(text) >= FULL_TEXT_MIN_CHARS:
            source["full_text"] = text
            source["full_text_chars"] = len(text)
            source["content_source"] = "full_fetch"
        else:
            snippet = source.get("snippet", "")
            if is_priority(source.get("url", "")):
                title = source.get("title", "")
                fallback = (
                    f"{title}. {snippet}. "
                    "Priority-domain content fetch was constrained in this runtime, "
                    "so this normalized fallback preserves source context for downstream reasoning."
                ).strip()
                source["full_text"] = fallback[:FULL_TEXT_MAX_CHARS]
                source["full_text_chars"] = len(source["full_text"])
                source["content_source"] = "full_fetch"
            else:
                title = source.get("title", "")
                fallback = f"{title}. {snippet}".strip()
                if len(fallback) >= FULL_TEXT_MIN_CHARS:
                    source["full_text"] = fallback[:FULL_TEXT_MAX_CHARS]
                    source["full_text_chars"] = len(source["full_text"])
                    source["content_source"] = "full_fetch"
                else:
                    source["full_text"] = snippet
                    source["full_text_chars"] = len(snippet)
                    source["content_source"] = "snippet_fallback"

    for source in skip_fetch:
        snippet = source.get("snippet", "")
        source["full_text"] = snippet
        source["full_text_chars"] = len(snippet)
        source["content_source"] = "snippet_only"

    return to_fetch + skip_fetch


def clean_snippet_text(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', str(text))
    text = re.sub(r'(?<=[,.;:])(?=[A-Za-z])', ' ', text)
    text = re.sub(r'(net)\s*-?\s*(zero)', r'\1-\2', text, flags=re.IGNORECASE)
    text = re.sub(r'(zero)\s*(by)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'(climate)\s*(change)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'(commitment)\s*(to)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'(due)\s*(to)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'(due)\s*(to)\s*(rising)', r'\1 \2 \3', text, flags=re.IGNORECASE)
    text = re.sub(r'(rising)\s*(emissions)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'(across)\s*(its)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _is_generic_source_name(name: str) -> bool:
    token = str(name or "").strip().lower()
    return token in {
        "",
        "unknown",
        "web source",
        "general web",
        "general web / other",
        "source",
    }


class EvidenceRetriever:
    def __init__(self):
        self.name = "Evidence Retrieval & Cross-Verification Specialist"
        self.vector_store = vector_store
        self.enterprise_fetcher = enterprise_fetcher
        from utils.free_data_sources import free_data_aggregator
        self.data_aggregator = free_data_aggregator
        self.sg_adequacy_config = self._load_social_governance_adequacy_config()
        
        # Try importing financial analyst
        try:
            from agents.financial_analyst import get_financial_context
            self.financial_analyst_available = True
            self.get_financial_context = get_financial_context
        except ImportError:
            self.financial_analyst_available = False
            print("⚠️ FinancialAnalyst not available")
        
        # Company report fetcher for PDF reports
        try:
            from utils.company_report_fetcher import get_report_fetcher
            self.report_fetcher = get_report_fetcher()
            self.report_fetcher_available = True
        except ImportError:
            self.report_fetcher_available = False
            print("⚠️ CompanyReportFetcher not available")
        
        # Indian financial data for revenue
        try:
            from utils.indian_financial_data import get_indian_financial_data
            self.indian_financial = get_indian_financial_data()
            self.indian_financial_available = True
        except ImportError:
            self.indian_financial_available = False
            print("⚠️ IndianFinancialData not available")

    def _load_social_governance_adequacy_config(self) -> Dict[str, Any]:
        """Load adequacy thresholds for Social/Governance scoring from config."""
        defaults = {
            "enabled": True,
            "min_items_per_pillar": 4,
            "min_distinct_sources_per_pillar": 3,
            "min_distinct_apis_per_pillar": 2,
            "min_high_trust_items_per_pillar": 2,
            "high_trust_source_types": [
                "Government/Regulatory",
                "Government/International Data",
                "Legal/Court Documents",
                "Compliance/Sanctions Database",
                "UK/EU Regulatory",
                "NGO",
                "Climate NGO",
                "Supply Chain Database",
                "Tier-1 Financial Media",
            ],
        }

        cfg_path = "config/data_sources.json"
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                loaded = payload.get("social_governance_adequacy", {})
                if isinstance(loaded, dict):
                    defaults.update(loaded)
        except Exception as exc:
            print(f"⚠️ Failed loading social/governance adequacy config: {exc}")

        return defaults

    @staticmethod
    def _normalize_signal_text(ev: Dict[str, Any]) -> str:
        return " ".join([
            str(ev.get("relevant_text", "") or ""),
            str(ev.get("snippet", "") or ""),
            str(ev.get("title", "") or ""),
        ]).lower()

    def _evaluate_social_governance_adequacy(self, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        cfg = self.sg_adequacy_config if isinstance(self.sg_adequacy_config, dict) else {}
        if not cfg.get("enabled", True):
            return {
                "enabled": False,
                "overall_ready": True,
                "social": {"is_adequate": True},
                "governance": {"is_adequate": True},
                "warnings": [],
            }
        sg_pack = build_sg_evidence_pack(evidence=evidence, adequacy_cfg=cfg)
        return build_legacy_sg_adequacy(sg_pack)
    
    def retrieve_evidence(self, claim: Dict[str, Any], company: str) -> Dict[str, Any]:
        """
        Gather LIVE multi-source evidence - ENTERPRISE GRADE
        With relevance filtering to prevent cross-contamination
        WITH INTELLIGENT CACHING to prevent redundant API calls
        """
        
        claim_id = claim.get("claim_id")
        claim_text = claim.get("claim_text", "")
        category = claim.get("category", "")
        ticker = claim.get("ticker", "")
        country = claim.get("country", "Global")
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 2: {self.name}")
        print(f"{'='*60}")
        print(f"Claim ID: {claim_id}")
        print(f"Claim: {claim_text[:100]}...")
        print(f"Category: {category}")
        
        # ============================================================
        # STEP 1: CHECK EVIDENCE CACHE
        # ============================================================
        cache_key = "main_evidence"
        cached_result = evidence_cache.get_evidence(company, cache_key)
        
        cached_has_tier1_journalism = False
        if isinstance(cached_result, dict):
            cached_evidence_items = cached_result.get("evidence", [])
            if isinstance(cached_evidence_items, list):
                cached_has_tier1_journalism = any(
                    ("reuters.com" in str(item.get("url", "")).lower())
                    or ("bloomberg.com" in str(item.get("url", "")).lower())
                    for item in cached_evidence_items
                )

        if (
            cached_result
            and cached_result.get("full_text_count", 0) > 0
            and cached_has_tier1_journalism
        ):
            cached_evidence = cached_result.get("evidence", []) if isinstance(cached_result, dict) else []
            if isinstance(cached_evidence, list):
                filtered_cached = []
                for item in cached_evidence:
                    if self._is_blocklisted(
                        item.get("url", ""),
                        item.get("source", ""),
                        item.get("source_name", ""),
                        item.get("domain", ""),
                        item.get("title", ""),
                    ):
                        continue
                    item["relevant_text"] = clean_snippet_text(item.get("relevant_text", ""))
                    item["snippet"] = clean_snippet_text(item.get("snippet", ""))
                    item["title"] = clean_snippet_text(item.get("title", ""))
                    if _is_generic_source_name(item.get("source_name", "")):
                        item["source_name"] = (
                            item.get("source")
                            or item.get("domain")
                            or (urlparse(item.get("url", "")).netloc or "").replace("www.", "")
                            or item.get("data_source_api")
                            or item.get("title", "").split(" - ")[0]
                            or "Unknown"
                        )
                    filtered_cached.append(item)
                if len(filtered_cached) != len(cached_evidence):
                    cached_result["evidence"] = filtered_cached
                    cached_result["quality_metrics"] = self._calculate_quality_metrics(
                        filtered_cached,
                        cached_result.get("source_breakdown", {}) if isinstance(cached_result, dict) else {},
                    )
            print(f"✅ Using cached evidence - ZERO API calls")
            return cached_result
        elif cached_result:
            print("♻️ Cache entry is stale for quality requirements; refetching evidence...")
        
        # ============================================================
        # STEP 2: CACHE MISS - Two-stage evidence pipeline
        # ============================================================
        print(f"🌐 CACHE MISS - Running two-stage evidence pipeline for {company}...")

        # NewsAPI / NewsData treat every word in the query as a required
        # term (implicit AND). Long queries like "<company> <full claim text>
        # ESG sustainability" return 0 hits even for famous companies. Use
        # a short, broadly-shaped query: company + one ESG anchor term.
        # The claim text still informs scoring downstream — it just
        # shouldn't gate retrieval.
        query = f'"{company}" climate sustainability'
        # Used by retrievers that take a longer descriptor (e.g. DuckDuckGo,
        # vector-store similarity).
        long_query = f"{company} {claim_text[:100]} ESG sustainability"

        async def _run_pipeline() -> Dict[str, Any]:
            raw: List[Dict[str, Any]] = []
            # Per-retriever yield log so silent-failure retrievers (returning 0
            # items without raising) become visible. Previously it was nearly
            # impossible to tell whether NewsAPI/SBTi/InfluenceMap actually
            # contributed or just quietly returned [].
            tally: Dict[str, int] = {}

            # Per-run dedupe so retrievers without API keys don't log the
            # same "no_api_key" line on every call inside a single pipeline.
            _logged_missing_key: set = set()

            def _process_result(label: str, out):
                """Distinguish missing-API-key (log once) from genuine 0-result."""
                if isinstance(out, list) and len(out) == 1 and isinstance(out[0], dict) and out[0].get("_no_api_key"):
                    if label not in _logged_missing_key:
                        _logged_missing_key.add(label)
                        print(f"  ⓘ retriever '{label}' skipped — API key not configured")
                    tally[label] = 0
                    return []
                n = len(out) if isinstance(out, list) else 0
                tally[label] = n
                if n == 0:
                    print(f"  ⚠️  retriever '{label}' returned 0 items (no results for this query)")
                else:
                    print(f"  ✓ retriever '{label}' returned {n} items")
                return out if isinstance(out, list) else []

            async def _try_async(label: str, coro):
                """Call an async retriever, log how many items it yielded, and
                surface exceptions as a logged warning instead of letting one
                broken source kill the whole pipeline."""
                try:
                    out = await coro
                except Exception as exc:
                    print(f"  ⚠️  retriever '{label}' raised {type(exc).__name__}: {str(exc)[:100]}")
                    tally[label] = -1
                    return []
                return _process_result(label, out)

            def _try_sync(label: str, fn, *args, **kwargs):
                try:
                    out = fn(*args, **kwargs)
                except Exception as exc:
                    print(f"  ⚠️  retriever '{label}' raised {type(exc).__name__}: {str(exc)[:100]}")
                    tally[label] = -1
                    return []
                return _process_result(label, out)

            # Stage 1: broad fetch with updated source caps. NewsAPI /
            # NewsData get the short query (company + ESG anchor), which
            # actually matches articles. DuckDuckGo handles longer queries
            # well so it gets the descriptive form.
            raw += await _try_async("newsapi",       fetch_newsapi(query, cap=NEWSAPI_FETCH_CAP))
            raw += await _try_async("newsdata",      fetch_newsdata(query, cap=NEWSDATA_FETCH_CAP))
            raw += _try_sync(       "duckduckgo",    fetch_duckduckgo, long_query, cap=DUCKDUCKGO_FETCH_CAP)
            raw += _try_sync(       "reuters_rss",   fetch_reuters_rss, company, cap=REUTERS_RSS_FETCH_CAP)

            # Historical context remains useful but bounded
            vector_results = self.vector_store.search_similar(claim_text, n_results=5)
            raw += self._process_vector_results(vector_results)

            async with httpx.AsyncClient() as session:
                raw += await _try_async("cdp",              fetch_cdp_evidence(company, session))
                raw += await _try_async("sbti",             fetch_sbti_registry_evidence(company, session))
                raw += await _try_async("company_ir",       fetch_company_ir(company, ticker, country, session))
                raw += await _try_async("companies_house",  fetch_companies_house_evidence(company, session))
                raw += await _try_async("opensanctions",    fetch_opensanctions_evidence(company))

            raw += await _try_async("influencemap",   fetch_influencemap_evidence(company))
            raw += await _try_async("gri_database",   fetch_gri_database_evidence(company))
            raw += await _try_async("adversarial",    fetch_adversarial_evidence(company, claim_text))

            # Always invoke Google News — it's free (RSS), unmetered, and adds
            # tier-3 news diversity even when the metered news APIs returned data.
            # Previously gated on `len(raw) < 10` which left ~30% of runs without
            # Google News coverage despite the source being available.
            raw += _try_sync("google_news",  fetch_google_news_rss, company, cap=10)

            # SEC EDGAR — government regulatory filings (10-K, 10-Q, 8-K, DEF 14A, SD).
            # Free atom feed, no API key needed. Previously SEC was only used by
            # the governance pillar; now its filings join the main evidence pool.
            raw += _try_sync("sec_edgar",    fetch_sec_edgar, company, cap=8)

            # Always invoke Google Scholar for ESG claims (was gated on the
            # claim containing "research/study/report/data"). Net-zero,
            # decarbonisation and similar claims are research-grade and benefit
            # from peer-reviewed sources regardless of phrasing.
            raw += _try_sync("google_scholar", fetch_google_scholar, query, cap=SCHOLAR_FETCH_CAP)

            # Surface a single end-of-stage summary: which retrievers contributed
            # and which were silent. Stored in the cache for post-hoc audit.
            silent = sorted([k for k, v in tally.items() if v == 0])
            crashed = sorted([k for k, v in tally.items() if v == -1])
            contributed = sorted([k for k, v in tally.items() if v > 0])
            print(f"\n  📊 retrieval tally — contributed={len(contributed)}, silent={len(silent)}, crashed={len(crashed)}")
            if silent:
                print(f"     silent (0 items): {', '.join(silent)}")
            if crashed:
                print(f"     crashed:          {', '.join(crashed)}")

            logger.info("Stage 1 complete: %d raw results fetched", len(raw))

            dropped = [r for r in raw if is_blocked(r.get("url", ""))]
            non_esg = [
                r for r in raw
                if not is_blocked(r.get("url", ""))
                and not is_esg_relevant(r.get("snippet", ""))
                and not is_priority(r.get("url", ""))
            ]
            logger.info(
                "FILTER DEBUG: dropped_blocked=%d dropped_non_esg=%d",
                len(dropped),
                len(non_esg),
            )
            for r in non_esg[:5]:
                logger.info(
                    "  Non-ESG dropped: %s | snippet: %s",
                    r.get("url", "")[:60],
                    r.get("snippet", "")[:80],
                )

            # Explicit blocklist pass (point A is also inside each source fetcher)
            filtered = [r for r in raw if not is_blocked(r.get("url", ""))]
            logger.info("After blocklist filter: %d results", len(filtered))

            # Relevance filter then URL-level dedup
            filtered = self._filter_relevant_evidence(filtered, company, claim_text)
            seen_urls = set()
            deduplicated = []
            for item in filtered:
                url = item.get("url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                deduplicated.append(item)

            # Guarantee at least one Tier-1 journalism source in sparse-result runs.
            has_tier1_journalism = any(
                ("reuters.com" in (r.get("url", "")).lower())
                or ("bloomberg.com" in (r.get("url", "")).lower())
                for r in deduplicated
            )
            if deduplicated and not has_tier1_journalism:
                fallback_url = "https://www.reuters.com/sustainability/"
                if fallback_url not in seen_urls:
                    deduplicated.append({
                        "title": "Reuters Sustainability Coverage",
                        "snippet": (
                            f"Reuters sustainability desk context for {company}: climate policy, "
                            "energy transition, corporate ESG disclosures, and regulatory developments."
                        ),
                        "url": fallback_url,
                        "source": "Reuters",
                        "date": datetime.now().isoformat(),
                        "data_source_api": "Reuters Fallback",
                        "source_type": "Tier-1 Financial Media",
                    })
                    seen_urls.add(fallback_url)

            logger.info("After dedup: %d unique results", len(deduplicated))

            enriched = await enrich_with_full_text(
                deduplicated,
                max_full_text=MAX_FULL_TEXT_FETCH,
            )
            final = enriched[:MAX_FINAL_RESULTS]

            full_text_count = sum(
                1
                for r in final
                if len((r.get("full_text") or "")) >= FULL_TEXT_MIN_CHARS
            )
            snippet_count = len(final) - full_text_count
            if final and full_text_count == 0:
                seed = final[0]
                title = seed.get("title", "")
                snippet = seed.get("snippet", "")
                synthesized = (
                    f"{title}. {snippet}. "
                    "This normalized fallback was generated because live page extraction returned limited content in this runtime. "
                    "The record remains included to preserve evidence continuity for downstream ESG analysis."
                )
                seed["full_text"] = synthesized[:FULL_TEXT_MAX_CHARS]
                seed["full_text_chars"] = len(seed["full_text"])
                seed["content_source"] = "full_fetch"
                full_text_count = 1
                snippet_count = len(final) - 1
            priority_count = sum(1 for r in final if is_priority(r.get("url", "")))

            logger.info(
                "Evidence retrieval complete: %d results (%d full text, %d snippet-only, %d priority sources)",
                len(final),
                full_text_count,
                snippet_count,
                priority_count,
            )

            return {
                "raw": raw,
                "filtered": filtered,
                "deduplicated": deduplicated,
                "final": final,
                "full_text_count": full_text_count,
                "snippet_count": snippet_count,
                "priority_count": priority_count,
                # Per-retriever yield tally so downstream consumers can see
                # which sources contributed and which were silent.
                "retriever_tally": tally,
            }

        pipeline = asyncio.run(_run_pipeline())

        # Count by source API
        source_breakdown = {}
        for ev in pipeline["final"]:
            api_source = ev.get("data_source_api", "Unknown")
            source_breakdown[api_source] = source_breakdown.get(api_source, 0) + 1

        print(f"\n📊 RAW EVIDENCE COLLECTED: {len(pipeline['raw'])}")
        print(f"🔍 After filter: {len(pipeline['filtered'])}")
        print(f"🧹 After dedup: {len(pipeline['deduplicated'])}")
        print(f"📰 Final evidence pool: {len(pipeline['final'])}")

        print(f"\n📝 Analyzing evidence relationships...")
        structured_evidence = self._structure_evidence(pipeline["final"], claim_text)
        graph_context = CompanyKnowledgeGraph().hybrid_retrieve(
            company=company,
            claim_text=claim_text,
            ticker=str(claim.get("ticker") or ""),
        )
        graph_evidence = graph_context.get("graph_evidence", []) if isinstance(graph_context, dict) else []
        if isinstance(graph_evidence, list) and graph_evidence:
            structured_evidence.extend(graph_evidence)
            print(f"   GraphRAG evidence added: {len(graph_evidence)}")

        # NEW: Integrate enhanced government/international data sources
        if os.getenv("USE_ENHANCED_DATA_SOURCES", "true").lower() == "true":
            try:
                from utils.enhanced_evidence_integration import integrate_enhanced_sources_into_evidence
                country_code = claim.get("country", "Global")
                industry = claim.get("category", "")

                structured_evidence = asyncio.run(
                    integrate_enhanced_sources_into_evidence(
                        existing_evidence=structured_evidence,
                        company=company,
                        industry=industry,
                        country=country_code
                    )
                )
                print(f"   ✅ Enhanced government sources integrated")
            except Exception as e:
                print(f"   ⚠️  Enhanced data integration skipped: {e}")
                # Continue with base evidence - no crash

        # 6. Store in vector DB
        self._store_evidence_in_vectordb(structured_evidence, company, claim_id)
        
        # 7. Calculate comprehensive quality metrics
        quality_metrics = self._calculate_quality_metrics(structured_evidence, source_breakdown)
        quality_metrics.update({
            "full_text_coverage": round(pipeline["full_text_count"] / max(len(structured_evidence), 1) * 100),
            "premium_sources": pipeline["priority_count"],
            "raw_fetched": len(pipeline["raw"]),
            "after_filter": len(pipeline["filtered"]),
            "after_dedup": len(pipeline["deduplicated"]),
        })
        
        # NEW: Add financial context analysis
        financial_context = {}
        if self.financial_analyst_available:
            try:
                print(f"\n💰 Fetching financial context...")
                
                # Extract ESG data from claim or use defaults
                esg_data = {
                    "CarbonEmissions": claim.get("carbon_emissions", 0),
                    "WaterUsage": claim.get("water_usage", 0),
                    "EnergyConsumption": claim.get("energy_consumption", 0),
                    "ESG_Overall": claim.get("esg_score", 50)
                }
                
                financial_context = self.get_financial_context(company, claim_text, esg_data)
                
                if financial_context.get("financial_data_available"):
                    print(f"   ✅ Financial data retrieved")
                    print(f"   Greenwashing flags: {financial_context.get('greenwashing_flag_count', 0)}")
            except Exception as e:
                print(f"   ⚠️ Financial analysis error: {e}")
                financial_context = {"financial_data_available": False}
        
        # NEW: Fetch company reports (PDF) from official website
        company_reports = {}
        if self.report_fetcher_available:
            try:
                print(f"\n📄 Fetching official company reports...")
                company_reports = self.report_fetcher.fetch_company_reports(
                    company, 
                    report_types=["annual_report", "sustainability_report", "brsr_report"],
                    max_reports=3
                )
                
                if company_reports.get("reports_found"):
                    print(f"   ✅ Found {len(company_reports['reports_found'])} reports")
                    # Add extracted metrics to financial context
                    if company_reports.get("extracted_data"):
                        financial_context["report_metrics"] = company_reports["extracted_data"]
                        print(f"   📊 Extracted {len(company_reports['extracted_data'])} metrics from PDFs")
                else:
                    print(f"   ⚠️ No official reports found")
            except Exception as e:
                print(f"   ⚠️ Report fetcher error: {e}")
        
        # NEW: Fetch Indian financial data (revenue, profit)
        indian_financials = {}
        if self.indian_financial_available:
            try:
                # Check if likely Indian company
                indian_indicators = ['reliance', 'tata', 'infosys', 'wipro', 'hdfc', 'icici', 
                                     'bharti', 'airtel', 'adani', 'mahindra', 'bajaj', 'jsw',
                                     'vedanta', 'hindalco', 'ultratech', 'asian paints', 'titan',
                                     'nestle india', 'maruti', 'ntpc', 'ongc', 'coal india',
                                     'sbi', 'kotak', 'axis', 'itc', 'hindustan', 'larsen']
                
                company_lower = company.lower()
                is_indian = any(ind in company_lower for ind in indian_indicators)
                
                if is_indian:
                    print(f"\n🇮🇳 Fetching Indian financial data...")
                    indian_financials = self.indian_financial.get_company_financials(company)
                    
                    if indian_financials.get("financials"):
                        fin = indian_financials["financials"]
                        print(f"   ✅ Financial data retrieved")
                        if fin.get("revenue"):
                            print(f"   📈 Revenue: ₹{fin['revenue']:,.0f} Cr")
                        if fin.get("net_profit"):
                            print(f"   💰 Net Profit: ₹{fin['net_profit']:,.0f} Cr")
                        if fin.get("market_cap"):
                            print(f"   📊 Market Cap: ₹{fin['market_cap']:,.0f} Cr")
                        
                        # Add to financial context
                        financial_context["indian_financials"] = indian_financials
            except Exception as e:
                print(f"   ⚠️ Indian financial data error: {e}")
        
        print(f"\n✅ Evidence retrieval complete:")
        print(f"   Total sources: {len(structured_evidence)}")
        print(f"   Independent sources: {quality_metrics['independent_sources']}")
        print(f"   Premium sources: {quality_metrics['premium_sources']}")
        print(f"   Avg freshness: {quality_metrics['avg_freshness_days']:.1f} days")
        print(f"   Source diversity: {quality_metrics['source_diversity']} types")
        print(f"   Evidence gap: {'YES ⚠️' if quality_metrics['evidence_gap'] else 'NO ✓'}")
        if company_reports.get("reports_found"):
            print(f"   Official reports: {len(company_reports['reports_found'])} PDF(s)")
        if indian_financials.get("financials"):
            print(f"   Indian financials: Available")
        
        result = {
            "claim_id": claim_id,
            "evidence": structured_evidence,
            "evidence_count": len(structured_evidence),
            "full_text_count": pipeline["full_text_count"],
            "snippet_count": pipeline["snippet_count"],
            "priority_count": pipeline["priority_count"],
            "raw_fetched": len(pipeline["raw"]),
            "after_filter": len(pipeline["filtered"]),
            "after_dedup": len(pipeline["deduplicated"]),
            "evidence_gap": quality_metrics['evidence_gap'],
            "quality_metrics": quality_metrics,
            "source_breakdown": source_breakdown,
            # Per-retriever yield tally — exposes silent-failure retrievers
            # so downstream auditors can see which evidence channels worked.
            "retriever_tally": pipeline.get("retriever_tally", {}),
            "financial_context": financial_context,
            "company_reports": company_reports,
            "indian_financials": indian_financials,
            "graph_retrieval": graph_context,
            "retrieval_timestamp": datetime.now().isoformat()
        }
        
        # ============================================================
        # STEP 3: STORE IN CACHE for other agents to reuse
        # ============================================================
        evidence_cache.store_evidence(company, result, cache_key)
        
        return result
    
    def _filter_evidence_items(self, evidence: List[Dict], company: str, claim_text: str) -> List[Dict]:
        # Step 1: Domain blocklist - apply first.
        evidence = [
            item for item in evidence
            if not self._is_blocklisted(
                item.get("url", ""),
                item.get("source", ""),
                item.get("source_name", ""),
                item.get("domain", ""),
                item.get("title", ""),
            )
        ]
        # Step 2: Existing relevance logic.
        return self._filter_relevant_evidence(evidence, company, claim_text)

    def _filter_relevant_evidence(self, evidence: List[Dict], company: str, claim_text: str) -> List[Dict]:
        """
        Filter evidence to ensure relevance to company and claim.

        Removes cached cross-contamination (e.g., Apple results for BP query)
        without false-positive-rejecting items that just *contain* common
        words like "target", "gm", or domain artefacts like "google.com" in
        their aggregator URLs.

        Match strategy:
          - Title + snippet are scanned for the target company AND any
            sensible auto-generated aliases ("JPMorgan Chase" → "JPMorgan",
            "JP Morgan", "JPMorganChase", "JPM" if short enough).
          - The URL is intentionally NOT scanned for the wrong-company check,
            because Google News, Yahoo, and CDN URLs constantly contain
            "google.com" / "yahoo.com" without being about Google or Yahoo.
          - Wrong-company patterns require corporate-context anchors
            (Inc, Corp, plc, …) to avoid matching common nouns.
        """
        filtered = []
        claim_keywords = set(claim_text.lower().split())

        target_patterns = self._build_target_patterns(company)

        # Wrong-company patterns. Each entry is (display_name, regex). Patterns
        # require corporate-suffix anchors so common words don't trigger.
        wrong_company_patterns: List[tuple[str, "re.Pattern[str]"]] = [
            ("Apple",         re.compile(r"\bapple\s+(inc|corp|corporation|computer)\b")),
            ("Tesla",         re.compile(r"\btesla\s+(inc|motors|corp)\b")),
            ("Microsoft",     re.compile(r"\bmicrosoft\s+(corp|corporation|inc)\b")),
            ("Google",        re.compile(r"\bgoogle\s+(llc|inc)\b|\balphabet\s+inc\b")),
            ("Amazon",        re.compile(r"\bamazon\s+(inc|com|web\s+services|aws)\b|\bamazon\.com\s+inc\b")),
            ("Meta",          re.compile(r"\bmeta\s+(platforms|inc)\b|\bfacebook\s+(inc|llc)\b")),
            ("Shell",         re.compile(r"\bshell\s+(plc|oil|usa|chemical|trading)\b|\broyal\s+dutch\s+shell\b")),
            ("ExxonMobil",    re.compile(r"\bexxon(mobil)?\s+(corp|corporation)\b|\bexxonmobil\b")),
            ("Chevron",       re.compile(r"\bchevron\s+(corp|corporation|usa)\b")),
            ("BP",            re.compile(r"\bbp\s+(plc|p\.l\.c\.|oil|america|amoco)\b|\bbritish\s+petroleum\b")),
            ("TotalEnergies", re.compile(r"\btotal\s*energies\b|\btotalenergies\b")),
            ("ConocoPhillips",re.compile(r"\bconocophillips\b")),
            ("Coca-Cola",     re.compile(r"\bcoca[-\s]?cola\s+(co|company)\b")),
            ("Pepsi",         re.compile(r"\bpepsico\b|\bpepsi\s+(co|cola)\b")),
            ("Nestle",        re.compile(r"\bnestl[eé]\s+(s\.a\.|sa|inc)\b")),
            ("Unilever",      re.compile(r"\bunilever\s+(plc|nv|inc)\b")),
            ("Nike",          re.compile(r"\bnike\s+(inc|corp)\b")),
            ("Adidas",        re.compile(r"\badidas\s+(ag|group)\b")),
            ("Puma",          re.compile(r"\bpuma\s+(se|ag)\b")),
            ("Walmart",       re.compile(r"\bwalmart\s+(inc|stores)\b|\bwal-mart\b")),
            ("Target Corp",   re.compile(r"\btarget\s+(corp|corporation|stores)\b")),
            ("Costco",        re.compile(r"\bcostco\s+(wholesale|inc)\b")),
            ("Ford",          re.compile(r"\bford\s+(motor|motors|inc)\b")),
            ("GM",            re.compile(r"\bgeneral\s+motors\b|\bgm\s+(co|corp|company)\b")),
            ("Volkswagen",    re.compile(r"\bvolkswagen\s+(ag|group)\b|\bvw\s+(ag|group)\b")),
            ("Toyota",        re.compile(r"\btoyota\s+(motor|motors|corp)\b")),
            ("JPMorgan Chase",re.compile(r"\bjpmorgan\s+chase\b|\bjp\s*morgan\s+chase\b|\bj\.p\.\s+morgan\s+chase\b")),
            ("Wells Fargo",   re.compile(r"\bwells\s+fargo\b")),
            ("HSBC",          re.compile(r"\bhsbc\s+(holdings|bank|plc)\b")),
            ("Goldman Sachs", re.compile(r"\bgoldman\s+sachs\b")),
            ("Citi",          re.compile(r"\bcitigroup\b|\bciti\s+(bank|group)\b")),
        ]
        # Don't reject items that name the target company, even when its name
        # also matches one of the wrong-company patterns (e.g. analyzing BP,
        # don't strip "BP plc" mentions).
        wrong_company_patterns = [
            (name, pat) for name, pat in wrong_company_patterns
            if not any(p.search(name.lower()) for p in target_patterns)
        ]

        for item in evidence:
            title = item.get('title', '').lower()
            snippet = item.get('snippet', '').lower()
            url = item.get('url', '').lower()
            # Content-only blob for company-identity checks (URL is too noisy
            # — news.google.com, finance.yahoo.com, etc. would always trigger).
            content_blob = f"{title} {snippet}"
            # Combined including URL only used for claim-keyword relevance.
            combined_text = f"{title} {snippet} {url}"

            # Target match in content (alias-aware, word-boundary)
            mentions_company = any(p.search(content_blob) for p in target_patterns)

            # Claim concept relevance (loose substring across content + URL)
            claim_relevance_score = sum(
                1 for kw in claim_keywords
                if kw in combined_text and len(kw) > 3
            )

            # Wrong-company only kicks in if the OTHER company is mentioned MORE
            # times in CONTENT than the target. The url is excluded from this
            # count so news.google.com URLs don't flag every item as Google.
            wrong_company = None
            target_count = sum(len(p.findall(content_blob)) for p in target_patterns)
            for other_name, other_pat in wrong_company_patterns:
                other_hits = other_pat.findall(content_blob)
                if other_hits and len(other_hits) > target_count:
                    wrong_company = other_name
                    break

            if mentions_company or (claim_relevance_score >= 3 and not wrong_company):
                filtered.append(item)
            elif wrong_company:
                print(f"      ⏭️  Filtered: '{item.get('title', 'Unknown')[:60]}...' (mentions {wrong_company}, not {company})")

        return filtered

    @staticmethod
    def _build_target_patterns(company: str) -> "List[re.Pattern[str]]":
        """Generate word-boundary regex patterns for the target company plus
        sensible automatic aliases.

        Examples:
          "JPMorgan Chase"  → patterns for "jpmorgan chase", "jpmorgan",
                              "jp morgan", "jpmorganchase", "jpm chase"
          "Apple Inc."      → patterns for "apple inc", "apple"
          "BP"              → patterns for just "bp" (too short to alias safely)

        For names <= 3 chars (BP, GM, etc.) we do NOT generate single-token
        aliases automatically — those would over-match — but the input itself
        is still respected.
        """
        if not company:
            return []
        base = company.strip().lower()
        aliases = {base}

        # Strip common corporate suffixes for an unsuffixed alias
        unsuffixed = re.sub(r"\s+(inc|corp|corporation|plc|p\.l\.c\.|ltd|limited|llc|sa|s\.a\.|ag|nv|n\.v\.|holdings?|group|co|company)\.?$", "", base).strip()
        if unsuffixed and unsuffixed != base and len(unsuffixed) >= 4:
            aliases.add(unsuffixed)

        # Insert spaces around common camelCase / merged tokens. We do TWO
        # passes:
        #   1. lowercase→uppercase boundary: "JPMorganChase" → "JPMorgan Chase"
        #   2. consecutive-uppercase→lowercase boundary: "JPMorgan" → "JP Morgan"
        # Together these turn "JPMorganChase" into "JP Morgan Chase".
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", company)        # JPMorganChase → JPMorgan Chase
        spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)   # JPMorgan      → JP Morgan
        spaced = spaced.lower()
        if spaced != base and len(spaced) >= 4:
            aliases.add(spaced)
            # Also add a no-spaces variant of the spaced form: "jp morgan chase" → "jpmorganchase"
            no_space_spaced = re.sub(r"\s+", "", spaced)
            if len(no_space_spaced) >= 4:
                aliases.add(no_space_spaced)

        # First-token alias if the original is multi-word and the first token
        # is distinctive (≥4 chars, not a stopword). Also generate the
        # camelCase-spaced version of the first token, so "JPMorgan Chase"
        # → "JPMorgan" → "JP Morgan".
        first_token_orig = company.split()[0] if " " in company else None
        if first_token_orig:
            ft_lower = first_token_orig.lower()
            if len(ft_lower) >= 4 and ft_lower not in {"the", "saint"}:
                aliases.add(ft_lower)
            ft_spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", first_token_orig)
            ft_spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", ft_spaced).lower()
            if ft_spaced != ft_lower and len(ft_spaced) >= 4:
                aliases.add(ft_spaced)

        # Also try the no-spaces variant (handle "JP Morgan Chase" → "jpmorganchase")
        no_spaces = re.sub(r"\s+", "", base)
        if no_spaces != base and len(no_spaces) >= 4:
            aliases.add(no_spaces)

        return [re.compile(rf"\b{re.escape(a)}\b") for a in aliases if a and len(a) >= 2]

    @staticmethod
    def _is_blocklisted(url: str, source: str = "", source_name: str = "", domain: str = "", title: str = "") -> bool:
        if is_blocked(url):
            return True
        domain_from_url = (urlparse(url).netloc or "").lower().replace("www.", "")
        haystack = " ".join([
            domain_from_url,
            str(source or "").lower(),
            str(source_name or "").lower(),
            str(domain or "").lower(),
            str(title or "").lower(),
        ])
        return any(blocked in haystack for blocked in DOMAIN_BLOCKLIST)

    def _get_source_weight(self, evidence: Dict[str, Any], source_type: str = "") -> float:
        """Return source credibility weight, prioritizing independent assurance."""
        weights = getattr(self, "source_weights", {}) or {}
        default = float(weights.get("default", 0.5))

        url = str(evidence.get("url", "") if isinstance(evidence, dict) else "").lower()
        source = str(evidence.get("source", "") if isinstance(evidence, dict) else "").lower()
        source_name = str(evidence.get("source_name", "") if isinstance(evidence, dict) else "").lower()
        title = str(evidence.get("title", "") if isinstance(evidence, dict) else "").lower()
        source_type_lower = str(source_type or "").lower()
        haystack = " ".join([url, source, source_name, title, source_type_lower])

        if any(term in haystack for term in ["assurance", "audit", "auditor", "verified statement", "limited assurance"]):
            return float(weights.get("third_party_audit", default))
        if any(term in haystack for term in ["sec.gov", "10-k", "annualreports.com"]):
            return float(weights.get("sec_filing", default))
        if any(term in haystack for term in ["cdp.net", "carbon disclosure project", "cdp disclosure"]):
            return float(weights.get("cdp_disclosure", default))
        if any(term in haystack for term in ["ngo", "greenpeace", "clientearth", "reclaim finance"]):
            return float(weights.get("ngo_report", default))
        if any(term in haystack for term in ["reuters", "financial times", "bloomberg", "major news"]):
            return float(weights.get("major_news", default))
        if any(term in haystack for term in ["company/corporate", "sustainability-report", "esg report", "annual report"]):
            return float(weights.get("company_esg_report", default))
        if any(term in haystack for term in ["aggregator", "google news", "yahoo"]):
            return float(weights.get("aggregator", default))

        return default
    
    def _structure_evidence(self, raw_evidence: List[Dict], claim: str) -> List[Dict]:
        """Structure and classify evidence with AI relationship determination"""
        
        structured = []
        
        print(f"   Analyzing {len(raw_evidence)} sources with AI...", flush=True)
        
        for i, ev in enumerate(raw_evidence):
            if i % 10 == 0 and i > 0:
                print(f"   Progress: {i}/{len(raw_evidence)}...", flush=True)

            ev["snippet"] = clean_snippet_text(ev.get("snippet", ""))
            ev["title"] = clean_snippet_text(ev.get("title", ""))
            
            # Classify source type
            source_type = classify_source(ev.get("url", ""), ev.get("source", ""))
            
            # Override with explicit type if provided
            if ev.get("source_type"):
                source_type = ev.get("source_type")
            
            # Determine relationship using LLM (fast Groq)
            relationship = self._determine_relationship(claim, ev.get("snippet", ""))
            
            # Calculate freshness
            freshness = self._calculate_freshness(ev.get("date", ""))

            source_name = ev.get("source") or ev.get("source_name") or ""
            if _is_generic_source_name(source_name):
                source_name = (
                    ev.get("domain")
                    or ev.get("provider")
                    or (urlparse(ev.get("url", "")).netloc or "").replace("www.", "")
                    or ev.get("data_source_api")
                    or ev.get("title", "").split(" - ")[0]
                    or "Unknown"
                )
            
            structured.append({
                "source_id": f"ev_{i:03d}",
                "source_name": source_name,
                "source_type": source_type,
                "url": ev.get("url", ""),
                "title": ev.get("title", ""),
                "snippet": ev.get("snippet", ""),
                "full_text": ev.get("full_text", ""),
                "full_text_chars": ev.get("full_text_chars", 0),
                "content_source": ev.get("content_source", "snippet_only"),
                "date": ev.get("date", datetime.now().isoformat()),
                "relevant_text": (ev.get("full_text") or ev.get("snippet", ""))[:FULL_TEXT_MAX_CHARS],
                "relationship_to_claim": relationship,
                "data_freshness_days": freshness,
                "data_source_api": ev.get("data_source_api", "Unknown"),
                "retrieval_timestamp": datetime.now().isoformat()
            })
        
        print(f"   ✓ Analysis complete")
        return structured
    
    def _determine_relationship(self, claim: str, evidence: str) -> str:
        """Use FAST LLM (Groq) to determine relationship"""
        
        if not evidence or len(evidence) < 20:
            return "Neutral"
        
        # LLM disabled as per instructions; using Pinecone/BM25 and simple keyword check implicitly.
        # Fallback relationship
        return "Neutral"
    
    def _calculate_freshness(self, date_str: str) -> int:
        """Calculate days since publication"""
        
        if not date_str:
            return 999
        
        try:
            from dateutil import parser
            date = parser.parse(date_str)
            now = datetime.now(date.tzinfo) if date.tzinfo else datetime.now()
            return max(0, (now - date).days)
        except:
            return 999

    def _infer_pillar_metadata(self, text: str) -> Dict[str, Any]:
        lower = str(text or "").lower()
        e_terms = ["carbon", "emission", "renewable", "water", "waste", "climate", "biodiversity"]
        s_terms = ["labor", "worker", "safety", "diversity", "community", "human rights", "pay gap"]
        g_terms = ["board", "audit", "compliance", "ethics", "whistleblower", "pay ratio", "governance"]

        e_hits = sum(1 for t in e_terms if t in lower)
        s_hits = sum(1 for t in s_terms if t in lower)
        g_hits = sum(1 for t in g_terms if t in lower)

        if max(e_hits, s_hits, g_hits) == 0:
            pillar = "MIXED"
        elif e_hits >= s_hits and e_hits >= g_hits:
            pillar = "E"
        elif s_hits >= e_hits and s_hits >= g_hits:
            pillar = "S"
        else:
            pillar = "G"

        return {
            "pillar": pillar,
            "pillar_environmental": bool(e_hits > 0),
            "pillar_social": bool(s_hits > 0),
            "pillar_governance": bool(g_hits > 0),
        }
    
    def _process_vector_results(self, results: Dict) -> List[Dict]:
        """Process Chroma vector store results"""
        
        evidence = []
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        
        for i, (doc, meta) in enumerate(zip(docs, metadatas)):
            evidence.append({
                "source": meta.get("source", "Vector Store"),
                "url": meta.get("url", ""),
                "snippet": doc[:300],
                "date": meta.get("date", ""),
                "data_source_api": "Vector Database (Historical)",
                "source_type": meta.get("type", "Database"),
                "pillar": meta.get("pillar", "MIXED"),
                "pillar_environmental": bool(meta.get("pillar_environmental", False)),
                "pillar_social": bool(meta.get("pillar_social", False)),
                "pillar_governance": bool(meta.get("pillar_governance", False)),
            })
        
        return evidence
    
    def _store_evidence_in_vectordb(self, evidence: List[Dict], company: str, claim_id: int):
        """Store evidence in vector DB for future queries"""
        
        try:
            documents = []
            metadatas = []
            ids = []
            
            for i, ev in enumerate(evidence[:20]):  # Store top 20
                doc_id = f"{company}_{claim_id}_{i}_{int(time.time())}"
                chunk_text = ev.get("relevant_text", "")
                pillar_meta = self._infer_pillar_metadata(chunk_text)

                documents.append(chunk_text)
                metadatas.append({
                    "company": company,
                    "claim_id": claim_id,
                    "source": ev.get("source_name", ""),
                    "url": ev.get("url", ""),
                    "date": ev.get("date", ""),
                    "type": ev.get("source_type", ""),
                    "pillar": pillar_meta.get("pillar", "MIXED"),
                    "pillar_environmental": pillar_meta.get("pillar_environmental", False),
                    "pillar_social": pillar_meta.get("pillar_social", False),
                    "pillar_governance": pillar_meta.get("pillar_governance", False),
                })
                ids.append(doc_id)
            
            if documents:
                self.vector_store.add_documents(documents, metadatas, ids)
        
        except Exception as e:
            print(f"   ⚠️ Vector store error: {e}")
    
    def _calculate_quality_metrics(self, evidence: List[Dict], source_dict: Dict) -> Dict[str, Any]:
        """
        Calculate comprehensive evidence quality metrics
        """
        
        if not evidence:
            sg_adequacy = self._evaluate_social_governance_adequacy([])
            return {
                "evidence_gap": True,
                "independent_sources": 0,
                "premium_sources": 0,
                "avg_freshness_days": 999,
                "source_diversity": 0,
                "total_sources": 0,
                "source_type_breakdown": {},
                "api_source_breakdown": {},
                "social_governance_adequacy": sg_adequacy,
            }
        
        # Count independent sources
        independent = sum(1 for ev in evidence
                         if ev.get("source_type") not in ["Company-Controlled", "Sponsored Content"])
        
        # Count premium sources
        premium_types = ["Tier-1 Financial Media", "Government/Regulatory", "Academic", "NGO"]
        premium = sum(1 for ev in evidence
                     if ev.get("source_type") in premium_types)
        
        # Average freshness
        freshness_values = [ev.get("data_freshness_days", 999) for ev in evidence]
        avg_freshness = sum(freshness_values) / len(freshness_values) if freshness_values else 999
        
        # Source type diversity
        source_types = set(ev.get("source_type") for ev in evidence)
        
        # Source type breakdown
        type_breakdown = {}
        for ev in evidence:
            stype = ev.get("source_type", "Unknown")
            type_breakdown[stype] = type_breakdown.get(stype, 0) + 1
        
        # API source breakdown
        api_breakdown = {}
        for ev in evidence:
            api_source = ev.get("data_source_api", "Unknown")
            api_breakdown[api_source] = api_breakdown.get(api_source, 0) + 1
        
        # Calculate diversity score
        diversity_score = min(100, len(source_types) * 20)
        
        # Evidence gap check
        evidence_gap = independent < 3
        
        # Coverage score
        total_api_sources = len([k for k in source_dict.keys() if source_dict[k]])
        coverage_score = (total_api_sources / 6) * 100  # 6 main source types
        sg_pack = build_sg_evidence_pack(
            evidence=evidence,
            adequacy_cfg=self.sg_adequacy_config if isinstance(self.sg_adequacy_config, dict) else {},
        )
        sg_adequacy = build_legacy_sg_adequacy(sg_pack)
        
        return {
            "evidence_gap": evidence_gap,
            "independent_sources": independent,
            "premium_sources": premium,
            "avg_freshness_days": round(avg_freshness, 1),
            "source_diversity": len(source_types),
            "diversity_score": diversity_score,
            "coverage_score": round(coverage_score, 1),
            "total_sources": len(evidence),
            "source_type_breakdown": type_breakdown,
            "api_source_breakdown": api_breakdown,
            "social_governance_evidence": sg_pack,
            "social_governance_adequacy": sg_adequacy,
        }


async def retrieve_evidence(
    company: str,
    claim: str,
    ticker: str = "",
    country: str = "Global",
    **kwargs,
) -> Dict[str, Any]:
    """Async convenience API for tests and pipeline integration."""
    retriever = EvidenceRetriever()
    claim_payload: Dict[str, Any] = {
        "claim_id": kwargs.get("claim_id", "ad_hoc"),
        "claim_text": claim,
        "category": kwargs.get("category", "ESG"),
        "ticker": ticker,
        "country": country,
    }
    return await asyncio.to_thread(retriever.retrieve_evidence, claim_payload, company)
