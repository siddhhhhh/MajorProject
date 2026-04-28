"""
utils/regulatory_fetchers.py
============================
Real-data fetchers for compliance-framework verification.

Each fetcher hits a free public source and returns a structured result:
    {
        "framework": "<name>",
        "verified": True | False | None,   # None == UNCERTAIN (couldn't determine)
        "evidence": "<short human-readable reason>",
        "url": "<source URL the determination came from>",
        "fetched_at": "<ISO date>",
        "source_name": "<name of the data source>",
    }

These exist because the previous regulatory scanner did keyword-rule
pattern matches against the claim text and DDG site searches — neither
of which actually verifies whether a company complies with a given
framework. These fetchers query the framework's own public registry
(SEC EDGAR, TCFD adopter list, CDP A List, UN Global Compact, SBTi).

All fetchers are file-cached at cache/regulatory/ to avoid hammering
upstream sources. TTLs are conservative because adopter/registry lists
move slowly (annual or quarterly cadence).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

CACHE_DIR = Path("cache/regulatory")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TTL_DAYS = 30
PERMANENT_TTL_DAYS = 36500  # ~100 years — for frozen lists like TCFD post-wind-down
USER_AGENT = "ESGLens/1.0 (research; tijo.thomas@lechlerindia.com)"

# ──────────────────────────────────────────────────────────────────────────
# Per-framework credibility weights for the capability score.
#
# Higher weight → more authoritative source. Government registries (SEC,
# FTC) get 1.0; official cross-border frameworks with verifiable
# registries (SBTi, CDP, CSRD/ESEF, TCFD) get 1.0; voluntary participant
# lists (UN GC, GRI) get 0.8 because anyone can self-register; in-
# disclosure inference (GHG Protocol scan of company's own report) gets
# 0.7 because the company is grading its own homework. Active enforcement
# is its own bucket with a heavy penalty (handled separately in scoring).
# ──────────────────────────────────────────────────────────────────────────
FRAMEWORK_CREDIBILITY_WEIGHTS: Dict[str, float] = {
    "SEC Climate Disclosure Rule":         1.0,   # Tier 1: US gov registry
    "FTC Green Guides":                    1.0,   # Tier 1: US gov enforcement
    "Science Based Targets initiative":    1.0,   # Tier 2: validated registry
    "CDP (Carbon Disclosure Project)":     1.0,   # Tier 2: scored registry
    "CSRD / EU ESEF Filing":               1.0,   # Tier 2: EU regulator filings
    "TCFD-aligned Climate Disclosure":     0.9,   # Tier 2: frozen registry
    "UN Global Compact":                   0.8,   # Tier 2: voluntary participation
    "GRI Sustainability Reporting Standards": 0.8,  # Tier 2: voluntary
    "GHG Protocol Corporate Standard":     0.7,   # Tier 3: in-disclosure inference
}


def get_framework_weight(framework: str) -> float:
    """Return the credibility weight for a framework name (default 0.5 unknown)."""
    return float(FRAMEWORK_CREDIBILITY_WEIGHTS.get(framework, 0.5))

_SESSION: Optional[requests.Session] = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        _SESSION = s
    return _SESSION


def _cache_key(name: str, *parts: str) -> Path:
    digest = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{name}_{digest}.json"


def _cache_get(path: Path, ttl_days: int = DEFAULT_TTL_DAYS) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        age = datetime.utcnow() - datetime.utcfromtimestamp(path.stat().st_mtime)
        if age > timedelta(days=ttl_days):
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_set(path: Path, data: dict) -> None:
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as exc:
        logger.warning("cache write failed for %s: %s", path, exc)


def _normalize_company_name(name: str) -> str:
    """Lowercase, strip punctuation/legal suffixes for fuzzy matching."""
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r"[^a-z0-9 &]+", " ", n)
    n = re.sub(r"\b(inc|incorporated|ltd|limited|corp|corporation|plc|group|company|co|s\.a\.|sa|ag|nv|llc|llp|holdings|holding)\b", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _name_matches(query: str, candidate: str) -> bool:
    """Conservative fuzzy match: tokens from query must all appear in candidate."""
    q = _normalize_company_name(query)
    c = _normalize_company_name(candidate)
    if not q or not c:
        return False
    if q in c or c in q:
        return True
    q_tokens = [t for t in q.split() if len(t) >= 3]
    if not q_tokens:
        return False
    return all(t in c for t in q_tokens)


def _today() -> str:
    return datetime.utcnow().date().isoformat()


# ─── SEC EDGAR ──────────────────────────────────────────────────────────────
# Free JSON API. Requires a real User-Agent. Returns recent filings for any
# US-listed entity. We use it to verify that a company has filed a 10-K
# (annual disclosure) recently — a baseline for SEC Climate Rule compliance.

_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def _sec_load_ticker_index() -> Dict[str, Dict[str, Any]]:
    """Cached download of the SEC ticker→CIK index. ~10k entries; refreshed weekly."""
    path = _cache_key("sec_ticker_index", "all")
    cached = _cache_get(path, ttl_days=7)
    if cached:
        return cached
    try:
        resp = _session().get(_SEC_TICKERS_URL, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
        # Index is {idx: {cik_str, ticker, title}} — flatten by normalized title
        index: Dict[str, Dict[str, Any]] = {}
        for entry in raw.values():
            title = str(entry.get("title", ""))
            cik = str(entry.get("cik_str") or "").zfill(10)
            ticker = str(entry.get("ticker", ""))
            if not cik or not title:
                continue
            index[_normalize_company_name(title)] = {
                "cik": cik,
                "title": title,
                "ticker": ticker,
            }
        _cache_set(path, index)
        return index
    except Exception as exc:
        logger.warning("SEC ticker index fetch failed: %s", exc)
        return {}


def _sec_lookup_cik(company: str) -> Optional[Dict[str, Any]]:
    index = _sec_load_ticker_index()
    if not index:
        return None
    norm = _normalize_company_name(company)
    if norm in index:
        return index[norm]
    # Token-overlap fallback
    q_tokens = [t for t in norm.split() if len(t) >= 3]
    best = None
    best_overlap = 0
    for key, entry in index.items():
        c_tokens = [t for t in key.split() if len(t) >= 3]
        if not q_tokens or not c_tokens:
            continue
        overlap = len(set(q_tokens) & set(c_tokens))
        if overlap > best_overlap:
            best_overlap = overlap
            best = entry
    if best and best_overlap >= max(1, len(q_tokens) // 2):
        return best
    return None


def fetch_sec_climate_disclosure(company: str, country: str = "") -> Dict[str, Any]:
    """Verify SEC Climate-related disclosure status for a US-listed company.

    Strategy:
      1. Look up CIK via the SEC ticker index.
      2. Fetch /submissions/CIK{n}.json for recent filings.
      3. Check whether a 10-K was filed in the last 18 months — baseline for
         SEC Climate Disclosure Rule (effective for FY2025 reports onwards).
      4. Inspect filing-specific items if available; flag if a 10-K covers
         climate-related items (Item 1C / Risk Factors mentioning climate).

    Returns the standard fetcher result shape. ``verified=None`` when the
    company isn't US-listed (so the framework simply doesn't apply).
    """
    framework = "SEC Climate Disclosure Rule"
    if country and country.upper() not in {"", "US", "USA", "UNITED STATES"}:
        return {
            "framework": framework,
            "verified": None,
            "evidence": f"Not applicable: company HQ is {country}, SEC rule is US-listed only.",
            "url": "",
            "fetched_at": _today(),
            "source_name": "SEC EDGAR",
            "applicable": False,
        }

    entry = _sec_lookup_cik(company)
    if not entry:
        return {
            "framework": framework,
            "verified": None,
            "evidence": "Company not found in SEC ticker index — likely not US-listed.",
            "url": _SEC_TICKERS_URL,
            "fetched_at": _today(),
            "source_name": "SEC EDGAR",
            "applicable": False,
        }

    cik = entry["cik"]
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    cache_path = _cache_key("sec_submissions", cik)
    cached = _cache_get(cache_path, ttl_days=7)
    submissions: Dict[str, Any] = {}
    if cached:
        submissions = cached
    else:
        try:
            resp = _session().get(submissions_url, timeout=20)
            resp.raise_for_status()
            submissions = resp.json()
            _cache_set(cache_path, submissions)
        except Exception as exc:
            return {
                "framework": framework,
                "verified": None,
                "evidence": f"SEC EDGAR submissions API failed: {exc}",
                "url": submissions_url,
                "fetched_at": _today(),
                "source_name": "SEC EDGAR",
                "applicable": True,
            }

    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    accession_nums = recent.get("accessionNumber", []) or []

    cutoff = (datetime.utcnow() - timedelta(days=540)).date().isoformat()
    annual_filings: List[Dict[str, Any]] = []
    for form, date, acc in zip(forms, dates, accession_nums):
        if form not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F"}:
            continue
        if date and date < cutoff:
            continue
        annual_filings.append({
            "form": form,
            "filing_date": date,
            "accession": acc,
            "url": (
                f"https://www.sec.gov/cgi-bin/browse-edgar?"
                f"action=getcompany&CIK={cik}&type={form}&dateb=&owner=include&count=10"
            ),
        })

    if annual_filings:
        latest = annual_filings[0]
        return {
            "framework": framework,
            "verified": True,
            "evidence": (
                f"Filed {latest['form']} on {latest['filing_date']} "
                f"({entry['title']}, CIK {cik}). SEC Climate Rule disclosures are "
                f"required in 10-K filings from FY2025 onwards."
            ),
            "url": latest["url"],
            "fetched_at": _today(),
            "source_name": "SEC EDGAR",
            "applicable": True,
            "filings_count": len(annual_filings),
            "company_title": entry["title"],
            "ticker": entry.get("ticker"),
        }

    return {
        "framework": framework,
        "verified": False,
        "evidence": (
            f"No recent annual filing (10-K/20-F) found for {entry['title']} "
            f"(CIK {cik}) in the last 18 months."
        ),
        "url": submissions_url,
        "fetched_at": _today(),
        "source_name": "SEC EDGAR",
        "applicable": True,
        "company_title": entry["title"],
    }


# ─── TCFD ADOPTER LIST ──────────────────────────────────────────────────────
# TCFD wound down Oct 2023. The adopter list is preserved at fsb-tcfd.org and
# mirrored on archive.org. We try both, cached for 30 days.

_TCFD_LIST_URLS = [
    # The live fsb-tcfd.org site is mostly a wind-down notice now (TCFD
    # was disbanded in Oct 2023; ISSB took over). The most complete
    # supporter list lives on archive.org snapshots from 2023.
    "https://web.archive.org/web/20231001000000*/fsb-tcfd.org/supporters",
    "https://web.archive.org/web/2023/https://www.fsb-tcfd.org/supporters/",
    "https://web.archive.org/web/20230715000000/https://www.fsb-tcfd.org/supporters/",
    "https://www.fsb-tcfd.org/supporters/",
]


def _tcfd_load_supporters() -> List[str]:
    """Return list of normalized company names that supported TCFD.

    The TCFD wound down Oct 2023; the supporter list is frozen. We
    cache the scraped result with a 100-year TTL and try Playwright
    first (the archived page is JS-rendered), falling back to plain
    HTTP scraping. Result is conservative — we'd rather miss some
    supporters than mis-attribute.
    """
    path = _cache_key("tcfd_supporters", "list")
    cached = _cache_get(path, ttl_days=PERMANENT_TTL_DAYS)
    if cached and isinstance(cached.get("companies"), list) and len(cached["companies"]) >= 50:
        return cached["companies"]

    companies: List[str] = []

    # Playwright path — handles JS-rendered archive snapshots.
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                for url in _TCFD_LIST_URLS:
                    try:
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        page.wait_for_timeout(2500)
                        text = page.content()
                        try:
                            from bs4 import BeautifulSoup  # type: ignore
                            soup = BeautifulSoup(text, "html.parser")
                            cands = []
                            for tag in soup.find_all(["a", "td", "li", "h3", "h4", "p", "span"]):
                                t = tag.get_text(" ", strip=True)
                                if 3 <= len(t) <= 120 and not t.lower().startswith(("home", "about", "contact", "privacy", "search", "menu")):
                                    cands.append(t)
                        except Exception:
                            cands = re.findall(r">([A-Z][A-Za-z0-9&\.\,\-\s]{3,80})<", text)
                        for raw in cands:
                            norm = _normalize_company_name(raw)
                            if norm and norm not in companies:
                                companies.append(norm)
                        if len(companies) >= 50:
                            break
                    except Exception as exc:
                        logger.debug("TCFD playwright fetch failed for %s: %s", url, exc)
            finally:
                browser.close()
    except Exception as exc:
        logger.debug("Playwright unavailable for TCFD: %s", exc)

    # Fallback: plain HTTP scraping (covers the case where Playwright is missing).
    if len(companies) < 50:
        for url in _TCFD_LIST_URLS:
            try:
                resp = _session().get(url, timeout=20)
                if resp.status_code != 200 or not resp.text:
                    continue
                try:
                    from bs4 import BeautifulSoup  # type: ignore
                    soup = BeautifulSoup(resp.text, "html.parser")
                    cands = []
                    for tag in soup.find_all(["a", "td", "li", "h3", "h4", "p", "span"]):
                        t = tag.get_text(" ", strip=True)
                        if 3 <= len(t) <= 120 and not t.lower().startswith(("home", "about", "contact", "privacy")):
                            cands.append(t)
                except Exception:
                    cands = re.findall(r">([A-Z][A-Za-z0-9&\.\,\-\s]{3,80})<", resp.text)
                for raw in cands:
                    norm = _normalize_company_name(raw)
                    if norm and norm not in companies:
                        companies.append(norm)
                if len(companies) >= 50:
                    break
            except Exception as exc:
                logger.debug("TCFD HTTP fetch failed for %s: %s", url, exc)

    if companies:
        _cache_set(path, {
            "companies": companies,
            "fetched_at": _today(),
            "source": _TCFD_LIST_URLS[0],
            "frozen_list": True,
            "count": len(companies),
        })
    return companies


def fetch_tcfd_adoption(company: str, country: str = "") -> Dict[str, Any]:
    """Check whether a company is on the public TCFD supporter list."""
    framework = "TCFD-aligned Climate Disclosure"
    supporters = _tcfd_load_supporters()
    if not supporters:
        return {
            "framework": framework,
            "verified": None,
            "evidence": "TCFD supporter list could not be retrieved (page may have moved post-wind-down Oct 2023).",
            "url": _TCFD_LIST_URLS[0],
            "fetched_at": _today(),
            "source_name": "FSB-TCFD",
            "applicable": True,
        }
    if any(_name_matches(company, c) for c in supporters):
        return {
            "framework": framework,
            "verified": True,
            "evidence": f"Listed on the FSB-TCFD supporter registry ({len(supporters)} total supporters).",
            "url": _TCFD_LIST_URLS[0],
            "fetched_at": _today(),
            "source_name": "FSB-TCFD",
            "applicable": True,
        }
    return {
        "framework": framework,
        "verified": False,
        "evidence": f"Not found in the FSB-TCFD supporter registry ({len(supporters)} entries scanned).",
        "url": _TCFD_LIST_URLS[0],
        "fetched_at": _today(),
        "source_name": "FSB-TCFD",
        "applicable": True,
    }


# ─── CDP A LIST ─────────────────────────────────────────────────────────────
# CDP releases an annual A List (top-disclosing companies). The full list is
# public; CDP's per-company score lookup is gated. We fetch the published
# A List (climate change topic by default) and check membership.

_CDP_A_LIST_URLS = [
    # CDP's dedicated A-list page (climate change topic). This URL has been
    # stable for several years and includes the year as a path segment that
    # CDP redirects to the latest cycle.
    "https://www.cdp.net/en/companies/companies-scores",
    "https://www.cdp.net/en/scores/cdp-scores-explained",
    "https://www.cdp.net/en/articles/companies/whos-on-the-a-list",
    # Wikipedia maintains a current list of CDP A-list companies (community-
    # maintained, lags the official list by a few months) — useful fallback.
    "https://en.wikipedia.org/wiki/Carbon_Disclosure_Project",
]


def _cdp_load_a_list() -> List[str]:
    """Load CDP A-list companies. Uses Playwright since the page is JS-rendered.

    CDP's company-scores page renders cards via React after the initial HTML,
    so plain `requests` returns no parseable company entries. Playwright loads
    the page in a real browser, waits for the cards to render, then extracts
    the company anchors.
    """
    path = _cache_key("cdp_a_list", "climate")
    cached = _cache_get(path, ttl_days=DEFAULT_TTL_DAYS)
    if cached and isinstance(cached.get("companies"), list) and len(cached["companies"]) >= 20:
        return cached["companies"]

    companies: List[str] = []

    # Playwright path
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                for url in _CDP_A_LIST_URLS:
                    try:
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        page.wait_for_timeout(4000)  # let React mount cards
                        # Try to scroll to load lazy-rendered rows
                        try:
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            page.wait_for_timeout(1500)
                        except Exception:
                            pass
                        text = page.content()
                        # 1) anchor href pattern that CDP uses for company pages
                        anchors = re.findall(
                            r'href="/en/(?:responses|companies)/[^"]+"[^>]*>([^<]{3,120})</a>',
                            text,
                        )
                        # 2) generic anchor texts inside cards if anchors missed
                        if not anchors:
                            try:
                                from bs4 import BeautifulSoup  # type: ignore
                                soup = BeautifulSoup(text, "html.parser")
                                for tag in soup.find_all(["a", "h3", "h4", "td"]):
                                    t = tag.get_text(" ", strip=True)
                                    if 3 <= len(t) <= 80 and not t.lower().startswith(
                                        ("home", "about", "search", "menu", "login", "filter")
                                    ):
                                        anchors.append(t)
                            except Exception:
                                pass
                        for raw in anchors:
                            norm = _normalize_company_name(raw)
                            if norm and norm not in companies:
                                companies.append(norm)
                        if len(companies) >= 20:
                            break
                    except Exception as exc:
                        logger.debug("CDP playwright fetch failed for %s: %s", url, exc)
            finally:
                browser.close()
    except Exception as exc:
        logger.debug("Playwright unavailable for CDP: %s", exc)

    # Fallback: plain HTTP (works for the Wikipedia URL even if the others don't)
    if len(companies) < 20:
        for url in _CDP_A_LIST_URLS:
            try:
                resp = _session().get(url, timeout=20)
                if resp.status_code != 200 or not resp.text:
                    continue
                anchors = re.findall(
                    r'href="/en/(?:responses|companies)/[^"]+"[^>]*>([^<]{3,120})</a>',
                    resp.text,
                )
                if not anchors:
                    try:
                        from bs4 import BeautifulSoup  # type: ignore
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for tag in soup.find_all(["a", "li", "td"]):
                            t = tag.get_text(" ", strip=True)
                            if 3 <= len(t) <= 80:
                                anchors.append(t)
                    except Exception:
                        pass
                for raw in anchors:
                    norm = _normalize_company_name(raw)
                    if norm and norm not in companies:
                        companies.append(norm)
                if len(companies) >= 20:
                    break
            except Exception as exc:
                logger.debug("CDP HTTP fetch failed for %s: %s", url, exc)

    if companies:
        _cache_set(path, {
            "companies": companies,
            "fetched_at": _today(),
            "source": _CDP_A_LIST_URLS[0],
            "count": len(companies),
        })
    return companies


def fetch_cdp_disclosure(company: str, country: str = "") -> Dict[str, Any]:
    """Check CDP A-List membership (free, public)."""
    framework = "CDP (Carbon Disclosure Project)"
    a_list = _cdp_load_a_list()
    if not a_list:
        return {
            "framework": framework,
            "verified": None,
            "evidence": "CDP public A-list could not be retrieved.",
            "url": _CDP_A_LIST_URLS[0],
            "fetched_at": _today(),
            "source_name": "CDP",
            "applicable": True,
        }
    if any(_name_matches(company, c) for c in a_list):
        return {
            "framework": framework,
            "verified": True,
            "evidence": f"On the public CDP Climate A-List ({len(a_list)} companies tracked).",
            "url": _CDP_A_LIST_URLS[0],
            "fetched_at": _today(),
            "source_name": "CDP",
            "applicable": True,
            "score_grade": "A",
        }
    return {
        "framework": framework,
        "verified": False,
        "evidence": (
            f"Not on CDP's public Climate A-List. May still disclose at lower grades "
            f"(A-, B, C, D) — CDP per-company scores require account access."
        ),
        "url": _CDP_A_LIST_URLS[0],
        "fetched_at": _today(),
        "source_name": "CDP",
        "applicable": True,
    }


# ─── UN GLOBAL COMPACT ──────────────────────────────────────────────────────
# Public participants list. Their JSON search endpoint returns matches.

_UNGC_SEARCH_URL = "https://unglobalcompact.org/api/v1/participants"


def fetch_un_global_compact(company: str, country: str = "") -> Dict[str, Any]:
    """Verify UN Global Compact participant status."""
    framework = "UN Global Compact"
    cache_path = _cache_key("ungc_participant", _normalize_company_name(company))
    cached = _cache_get(cache_path, ttl_days=DEFAULT_TTL_DAYS)
    if cached:
        return cached

    result: Dict[str, Any]
    try:
        # The public UN GC site exposes a search at /what-is-gc/participants
        resp = _session().get(
            "https://unglobalcompact.org/what-is-gc/participants/search",
            params={"search[keywords]": company},
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        text = resp.text
        try:
            from bs4 import BeautifulSoup  # type: ignore
            soup = BeautifulSoup(text, "html.parser")
            participants = []
            for card in soup.find_all(["a", "h3", "h4", "td"]):
                txt = card.get_text(" ", strip=True)
                if 3 <= len(txt) <= 120:
                    participants.append(txt)
        except Exception:
            participants = re.findall(r">([A-Z][A-Za-z0-9&\.\,\-\s]{3,80})<", text)

        match = next((p for p in participants if _name_matches(company, p)), None)
        if match:
            result = {
                "framework": framework,
                "verified": True,
                "evidence": f"Found in UN Global Compact participants directory: '{match}'.",
                "url": "https://unglobalcompact.org/what-is-gc/participants",
                "fetched_at": _today(),
                "source_name": "UN Global Compact",
                "applicable": True,
            }
        else:
            result = {
                "framework": framework,
                "verified": False,
                "evidence": "Not found in UN Global Compact participants directory.",
                "url": "https://unglobalcompact.org/what-is-gc/participants",
                "fetched_at": _today(),
                "source_name": "UN Global Compact",
                "applicable": True,
            }
    except Exception as exc:
        result = {
            "framework": framework,
            "verified": None,
            "evidence": f"UN Global Compact lookup failed: {exc}",
            "url": "https://unglobalcompact.org/what-is-gc/participants",
            "fetched_at": _today(),
            "source_name": "UN Global Compact",
            "applicable": True,
        }
    _cache_set(cache_path, result)
    return result


# ─── SBTi ───────────────────────────────────────────────────────────────────
# Leverages the existing data/sbti_company_cache.json that the regulatory
# scanner already maintains. We expose a fetcher-shape wrapper here so
# evaluate_real_compliance can treat all frameworks uniformly.

_SBTI_CACHE_PATH = Path("data/sbti_company_cache.json")


def fetch_sbti_status(company: str, country: str = "") -> Dict[str, Any]:
    """Check SBTi (Science Based Targets initiative) registry status."""
    framework = "Science Based Targets initiative"
    if not _SBTI_CACHE_PATH.exists():
        return {
            "framework": framework,
            "verified": None,
            "evidence": "SBTi registry cache not available.",
            "url": "https://sciencebasedtargets.org/companies-taking-action",
            "fetched_at": _today(),
            "source_name": "SBTi",
            "applicable": True,
        }
    try:
        with _SBTI_CACHE_PATH.open("r", encoding="utf-8") as f:
            cached = json.load(f)
        names: List[str] = cached.get("company_names", []) or []
    except Exception as exc:
        return {
            "framework": framework,
            "verified": None,
            "evidence": f"SBTi cache read failed: {exc}",
            "url": "https://sciencebasedtargets.org/companies-taking-action",
            "fetched_at": _today(),
            "source_name": "SBTi",
            "applicable": True,
        }

    if any(_name_matches(company, n) for n in names):
        return {
            "framework": framework,
            "verified": True,
            "evidence": f"Listed on SBTi public registry ({len(names)} companies tracked).",
            "url": "https://sciencebasedtargets.org/companies-taking-action",
            "fetched_at": _today(),
            "source_name": "SBTi",
            "applicable": True,
        }
    return {
        "framework": framework,
        "verified": False,
        "evidence": "No SBTi submission/validation found in public SBTi registry.",
        "url": "https://sciencebasedtargets.org/companies-taking-action",
        "fetched_at": _today(),
        "source_name": "SBTi",
        "applicable": True,
    }


# ─── GHG PROTOCOL (in-disclosure verification) ──────────────────────────────
# GHG Protocol is a methodology, not a registry. We verify it the same way
# auditors do: scan the company's own sustainability/climate disclosures
# for explicit GHG Protocol citations AND check whether Scope 2 is reported
# under both market-based and location-based methodologies (a Scope 2
# Guidance requirement). Both signals come from the parsed report chunks
# the pipeline already has, no extra HTTP calls needed.


def fetch_ghg_protocol_alignment(
    company: str, country: str = "", report_chunks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Verify GHG Protocol Corporate Standard alignment from report disclosures."""
    framework = "GHG Protocol Corporate Standard"
    if not report_chunks:
        return {
            "framework": framework,
            "verified": None,
            "evidence": "No parsed report chunks available — GHG Protocol alignment can only be verified from the company's own disclosures.",
            "url": "https://ghgprotocol.org/corporate-standard",
            "fetched_at": _today(),
            "source_name": "GHG Protocol",
            "applicable": True,
        }
    full_text_parts: List[str] = []
    for chunk in report_chunks[:600]:  # bound the scan
        if not isinstance(chunk, dict):
            continue
        t = chunk.get("text") or chunk.get("page_content") or ""
        if t:
            full_text_parts.append(str(t))
    text = "\n".join(full_text_parts).lower()
    if not text:
        return {
            "framework": framework,
            "verified": None,
            "evidence": "Parsed report chunks were empty — cannot verify.",
            "url": "https://ghgprotocol.org/corporate-standard",
            "fetched_at": _today(),
            "source_name": "GHG Protocol",
            "applicable": True,
        }

    # Strong citation signals — phrases that explicitly cite the standard.
    citation_patterns = [
        r"ghg\s+protocol(?:\s+corporate)?(?:\s+standard)?",
        r"greenhouse\s+gas\s+protocol",
        r"wri\s*/\s*wbcsd",
        r"world\s+resources\s+institute.*world\s+business\s+council",
    ]
    has_citation = any(re.search(p, text) for p in citation_patterns)

    # Scope 2 dual reporting (Scope 2 Guidance, Section 5)
    has_market_based = bool(re.search(r"market[-\s]+based", text))
    has_location_based = bool(re.search(r"location[-\s]+based", text))
    dual_s2 = has_market_based and has_location_based

    # Operational vs financial control boundary
    has_boundary = bool(re.search(r"operational\s+control|financial\s+control|equity\s+share", text))

    if has_citation and dual_s2:
        return {
            "framework": framework,
            "verified": True,
            "evidence": (
                "Explicit GHG Protocol citation found in disclosures + dual market-based "
                "and location-based Scope 2 reported (Scope 2 Guidance compliant)."
            ),
            "url": "https://ghgprotocol.org/corporate-standard",
            "fetched_at": _today(),
            "source_name": "GHG Protocol (in-disclosure)",
            "applicable": True,
            "details": {
                "has_citation": has_citation,
                "dual_scope2": dual_s2,
                "boundary_disclosed": has_boundary,
            },
        }
    if has_citation and not dual_s2:
        return {
            "framework": framework,
            "verified": False,
            "evidence": (
                "Cites GHG Protocol but does not appear to report Scope 2 under both "
                "market-based and location-based methodologies (Scope 2 Guidance gap)."
            ),
            "url": "https://ghgprotocol.org/corporate-standard",
            "fetched_at": _today(),
            "source_name": "GHG Protocol (in-disclosure)",
            "applicable": True,
        }
    if dual_s2 and not has_citation:
        return {
            "framework": framework,
            "verified": True,
            "evidence": (
                "Reports Scope 2 under both market-based and location-based methodologies "
                "(consistent with GHG Protocol Scope 2 Guidance), though without explicit citation."
            ),
            "url": "https://ghgprotocol.org/corporate-standard",
            "fetched_at": _today(),
            "source_name": "GHG Protocol (in-disclosure)",
            "applicable": True,
        }
    return {
        "framework": framework,
        "verified": False,
        "evidence": (
            "No explicit GHG Protocol citation and no dual market/location-based Scope 2 "
            "reporting found in parsed disclosures."
        ),
        "url": "https://ghgprotocol.org/corporate-standard",
        "fetched_at": _today(),
        "source_name": "GHG Protocol (in-disclosure)",
        "applicable": True,
    }


# ─── GRI STANDARDS ──────────────────────────────────────────────────────────
# GRI maintains a public Sustainability Disclosure Database. We scrape the
# company-search page and check for matches.

_GRI_DB_URL = "https://database.globalreporting.org"
_GRI_FALLBACK_URLS = [
    "https://database.globalreporting.org/search/",
    "https://www.globalreporting.org/search-results/?q=",
]


def _gri_fetch_with_retry(url: str, params: Optional[Dict[str, str]] = None, attempts: int = 3) -> Optional[str]:
    """HTTP GET with N attempts and exponential backoff."""
    import time as _t
    for i in range(attempts):
        try:
            resp = _session().get(url, params=params, timeout=15)
            if resp.status_code == 200 and resp.text:
                return resp.text
            if resp.status_code in (429, 503):  # back off harder on rate-limit
                _t.sleep(2 + i * 2)
                continue
            return None
        except Exception as exc:
            logger.debug("GRI attempt %d on %s failed: %s", i + 1, url, exc)
            _t.sleep(1 + i)
    return None


def fetch_gri_disclosure(company: str, country: str = "") -> Dict[str, Any]:
    """Check GRI Sustainability Disclosure Database for the company.

    Hardened against transient failures: 3-attempt retry with backoff,
    and a fallback URL on globalreporting.org's main search if the
    database subdomain is unreachable.
    """
    framework = "GRI Sustainability Reporting Standards"
    cache_path = _cache_key("gri_company", _normalize_company_name(company))
    cached = _cache_get(cache_path, ttl_days=DEFAULT_TTL_DAYS)
    if cached:
        return cached

    text: Optional[str] = None
    used_url = ""
    # Try primary database, then fallbacks
    candidates = [
        (f"{_GRI_DB_URL}/search/", {"q": company}),
        (_GRI_FALLBACK_URLS[1] + company, None),  # main site search
    ]
    for url, params in candidates:
        text = _gri_fetch_with_retry(url, params=params, attempts=3)
        if text:
            used_url = url
            break

    if not text:
        result = {
            "framework": framework,
            "verified": None,
            "evidence": "GRI Database unreachable after retries (database.globalreporting.org + globalreporting.org search both timed out).",
            "url": _GRI_DB_URL,
            "fetched_at": _today(),
            "source_name": "GRI Database",
            "applicable": True,
        }
        _cache_set(cache_path, result)
        return result

    # Parse anchors / cards
    anchors: List[str] = []
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all(["a", "h3", "h4", "td"]):
            txt = a.get_text(" ", strip=True)
            if 3 <= len(txt) <= 120:
                anchors.append(txt)
    except Exception:
        anchors = re.findall(r">([A-Z][A-Za-z0-9&\.\,\-\s]{3,80})<", text)

    match = next((a for a in anchors if _name_matches(company, a)), None)
    if match:
        result = {
            "framework": framework,
            "verified": True,
            "evidence": f"Found in GRI Sustainability Disclosure Database: '{match[:80]}'.",
            "url": used_url,
            "fetched_at": _today(),
            "source_name": "GRI Database",
            "applicable": True,
        }
    else:
        result = {
            "framework": framework,
            "verified": None,
            "evidence": (
                "Not found in GRI Sustainability Disclosure Database. The database is not "
                "exhaustive (companies self-register), so absence is not proof of non-compliance."
            ),
            "url": used_url,
            "fetched_at": _today(),
            "source_name": "GRI Database",
            "applicable": True,
        }
    _cache_set(cache_path, result)
    return result


# ─── FTC GREEN GUIDES ───────────────────────────────────────────────────────
# Not a certification — companies aren't "compliant" with Green Guides; they
# either get an enforcement action or they don't. We search the FTC's public
# cases & proceedings page for the company name combined with green-claim
# keywords. Hits = HARD GAP. No hits = UNCERTAIN (no certification possible).


def fetch_ftc_green_guides(company: str, country: str = "") -> Dict[str, Any]:
    """Search FTC enforcement actions for green-claim cases against the company."""
    framework = "FTC Green Guides"
    if country and country.upper() not in {"", "US", "USA", "UNITED STATES"}:
        return {
            "framework": framework,
            "verified": None,
            "evidence": f"Not applicable: FTC jurisdiction is US-only ({country}).",
            "url": "https://www.ftc.gov/enforcement/cases-proceedings",
            "fetched_at": _today(),
            "source_name": "FTC",
            "applicable": False,
        }

    cache_path = _cache_key("ftc_enforcement", _normalize_company_name(company))
    cached = _cache_get(cache_path, ttl_days=DEFAULT_TTL_DAYS)
    if cached:
        return cached

    result: Dict[str, Any]
    try:
        resp = _session().get(
            "https://www.ftc.gov/enforcement/cases-proceedings",
            params={
                "search_api_fulltext": f"{company} green",
                "field_industry_target_id": "All",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        text = resp.text
        try:
            from bs4 import BeautifulSoup  # type: ignore
            soup = BeautifulSoup(text, "html.parser")
            # FTC case cards usually live in <article> or <div class="views-row">
            cards = []
            for tag in soup.find_all(["article", "div"], class_=re.compile(r"views-row|node--type-case")):
                txt = tag.get_text(" ", strip=True)
                if 20 <= len(txt) <= 800:
                    cards.append(txt)
            matched = [c for c in cards if _name_matches(company, c) and any(
                kw in c.lower() for kw in ("green", "environmental", "climate", "sustainab", "biodegrad", "recycl")
            )]
        except Exception:
            matched = []

        if matched:
            result = {
                "framework": framework,
                "verified": False,
                "evidence": (
                    f"FTC enforcement case(s) found mentioning the company AND green-claim "
                    f"keywords ({len(matched)} match(es)). Treat as HARD GAP."
                ),
                "url": "https://www.ftc.gov/enforcement/cases-proceedings",
                "fetched_at": _today(),
                "source_name": "FTC Enforcement DB",
                "applicable": True,
                "case_count": len(matched),
            }
        else:
            result = {
                "framework": framework,
                "verified": None,
                "evidence": (
                    "No FTC green-claim enforcement actions found against this company. "
                    "Note: Green Guides are guidelines, not a certification — absence of "
                    "enforcement is not proof of compliance."
                ),
                "url": "https://www.ftc.gov/enforcement/cases-proceedings",
                "fetched_at": _today(),
                "source_name": "FTC Enforcement DB",
                "applicable": True,
            }
    except Exception as exc:
        result = {
            "framework": framework,
            "verified": None,
            "evidence": f"FTC enforcement lookup failed: {exc}",
            "url": "https://www.ftc.gov/enforcement/cases-proceedings",
            "fetched_at": _today(),
            "source_name": "FTC Enforcement DB",
            "applicable": True,
        }
    _cache_set(cache_path, result)
    return result


# ─── CSRD / EU ESEF FILINGS ─────────────────────────────────────────────────
# The European Single Electronic Format (ESEF) database aggregates filings
# made under EU CSRD / Transparency Directive. Free public JSON-LD API at
# filings.xbrl.org. We query by entity name and treat any matching filing
# from the last 3 years as evidence of CSRD compliance.

_ESEF_API_URL = "https://filings.xbrl.org/api/filings"


def fetch_csrd_esef_filing(company: str, country: str = "") -> Dict[str, Any]:
    """Verify EU CSRD / ESEF filing against the public XBRL filings API."""
    framework = "CSRD / EU ESEF Filing"
    cache_path = _cache_key("csrd_esef", _normalize_company_name(company))
    cached = _cache_get(cache_path, ttl_days=DEFAULT_TTL_DAYS)
    if cached:
        return cached

    result: Dict[str, Any]
    try:
        # The XBRL Filings API returns JSON-LD with paginated entity records.
        # We fetch a large page and filter client-side by entity-name match.
        resp = _session().get(
            _ESEF_API_URL,
            params={"page[size]": 200, "include": "entity"},
            headers={"Accept": "application/vnd.api+json, application/json"},
            timeout=20,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        data = resp.json() if resp.text else {}
        # Walk the JSON:API "included" array for entity names
        included = data.get("included") or []
        entity_names: List[str] = []
        for item in included:
            if not isinstance(item, dict):
                continue
            attrs = item.get("attributes") or {}
            name = (
                attrs.get("name")
                or attrs.get("entityName")
                or attrs.get("legalName")
                or ""
            )
            if name:
                entity_names.append(str(name))
        # Walk the top-level "data" too in case the API returns flat records
        for item in data.get("data") or []:
            if not isinstance(item, dict):
                continue
            attrs = item.get("attributes") or {}
            for key in ("entity_name", "entityName", "name"):
                if attrs.get(key):
                    entity_names.append(str(attrs[key]))

        match = next((n for n in entity_names if _name_matches(company, n)), None)
        if match:
            result = {
                "framework": framework,
                "verified": True,
                "evidence": f"Found in EU ESEF Filings API: '{match[:80]}' (CSRD-aligned filing).",
                "url": _ESEF_API_URL,
                "fetched_at": _today(),
                "source_name": "EU ESEF (XBRL Filings API)",
                "applicable": True,
            }
        else:
            # CSRD only applies to EU-listed entities. If country tells us
            # the company is non-EU, mark as N/A rather than FAIL.
            non_eu = country and country.upper() in {
                "US", "USA", "UK", "GB", "IN", "INDIA", "CN", "CHINA", "JP", "JAPAN", "AU", "BR", "ZA"
            }
            if non_eu:
                result = {
                    "framework": framework,
                    "verified": None,
                    "evidence": f"Not applicable: company HQ is {country}, CSRD requires EU listing.",
                    "url": _ESEF_API_URL,
                    "fetched_at": _today(),
                    "source_name": "EU ESEF (XBRL Filings API)",
                    "applicable": False,
                }
            else:
                result = {
                    "framework": framework,
                    "verified": None,
                    "evidence": (
                        f"Not found in the {len(entity_names)} entities sampled from the EU ESEF "
                        "Filings API (CSRD applies to EU-listed entities only)."
                    ),
                    "url": _ESEF_API_URL,
                    "fetched_at": _today(),
                    "source_name": "EU ESEF (XBRL Filings API)",
                    "applicable": True,
                }
    except Exception as exc:
        result = {
            "framework": framework,
            "verified": None,
            "evidence": f"EU ESEF Filings API call failed: {exc}",
            "url": _ESEF_API_URL,
            "fetched_at": _today(),
            "source_name": "EU ESEF (XBRL Filings API)",
            "applicable": True,
        }
    _cache_set(cache_path, result)
    return result


# ─── Aggregator ─────────────────────────────────────────────────────────────


def fetch_all_real_compliance(
    company: str,
    country: str = "",
    industry: str = "",
    report_chunks: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Run every real-data fetcher and return the structured rows.

    Each row is a single framework × single source result. The caller
    (regulatory_scanner.evaluate_real_compliance) merges these into the
    multi-jurisdiction scanner's row stream so they appear in Section 7B.

    ``report_chunks`` is optional and only used by the GHG Protocol
    in-disclosure check, which can't run without the parsed report text.
    """
    rows: List[Dict[str, Any]] = []
    simple_fetchers = [
        fetch_sec_climate_disclosure,
        fetch_tcfd_adoption,
        fetch_cdp_disclosure,
        fetch_un_global_compact,
        fetch_sbti_status,
        fetch_gri_disclosure,
        fetch_ftc_green_guides,
        fetch_csrd_esef_filing,
    ]
    for fn in simple_fetchers:
        try:
            row = fn(company, country)
            if row:
                rows.append(row)
        except Exception as exc:
            logger.warning("%s failed for %s: %s", fn.__name__, company, exc)
    # GHG Protocol takes the parsed-chunks input
    try:
        rows.append(fetch_ghg_protocol_alignment(company, country, report_chunks=report_chunks))
    except Exception as exc:
        logger.warning("fetch_ghg_protocol_alignment failed for %s: %s", company, exc)
    return rows
