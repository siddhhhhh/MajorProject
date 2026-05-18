"""SEC EDGAR XBRL — structured environmental capex / liability concepts.

EDGAR's XBRL API exposes per-company-per-concept time series. We pull the
environmental remediation expense + accrued contingency concepts so we can
cross-reference with EPA ECHO fines (P5).

API base: https://data.sec.gov/api/xbrl/companyconcept/CIK<cik>/us-gaap/<concept>.json

SEC policy: identify yourself in the User-Agent header (real contact OK).
Rate limits: 10 req/sec per IP. We make at most ~6 per company per run.

Public API:
    cik_for_ticker(ticker) -> str | None
    pull_concept(cik, concept) -> List[XBRLFact]
    environmental_capex_signal(cik) -> Dict   # roll-up of all env concepts
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BASE_URL = "https://data.sec.gov/api/xbrl"
_DEFAULT_TIMEOUT = 20.0
_USER_AGENT = "esglens/1.0 (tijo.thomas@lechlerindia.com)"  # SEC policy: real contact

_ENV_CONCEPTS = (
    # Empirically verified GAAP concepts (May-2026 audit across XOM/CVX/DUK/
    # PFE/JPM/DOW). The five "Environmental*" concepts in the original list
    # returned 404 for every CIK we tested — they're rarely used in SEC
    # filings. The R&D concept that previously rounded out the list was a
    # data-leak bug: R&D was being labeled as environmental capex,
    # producing a $23.7B "env capex" reading for Pfizer (actually 100%
    # R&D spending). Removed.
    #
    # The three remaining concepts ARE filed by extractive / utility
    # issuers (Exxon, Chevron, Duke), which are the issuers where env
    # capex is materially relevant. Tech / pharma / banks will return 0
    # filed concepts — that's the correct empty signal.
    "AssetRetirementObligation",
    "AssetRetirementObligationLiabilitiesIncurred",
    "AccrualForEnvironmentalLossContingencies",
)

# Per-CIK 404 cache. SEC's XBRL API has a 10 req/sec limit; without this
# cache a pipeline run that touches several agents pulling the same CIK
# would repeat the same dead-concept 404s, wasting our quota and the
# user's time. Keyed by (cik, concept) → True when 404 was previously
# observed in this process.
_CONCEPT_404_CACHE: Dict[tuple, bool] = {}


@dataclass
class XBRLFact:
    concept: str
    value: float
    units: str
    fiscal_year: Optional[int]
    end_date: Optional[str]
    form: Optional[str]


# Hardcoded ticker -> CIK for the v1 demo set. SEC supports company search
# but it returns multi-page JSON we don't want to parse. Extend as needed.
_TICKER_CIK_MAP = {
    "JPM":  "0000019617",
    "XOM":  "0000034088",
    "CVX":  "0000093410",
    "BP":   "0000313807",
    "MSFT": "0000789019",
    "TSLA": "0001318605",
    "AAPL": "0000320193",
    "GS":   "0000886982",
    "BAC":  "0000070858",
    "F":    "0000037996",
    "GM":   "0001467858",
    "PFE":  "0000078003",
    "AMZN": "0001018724",
    "GOOG": "0001652044",
    "GOOGL":"0001652044",
    "META": "0001326801",
}


def _http_get_json(url: str, timeout: float = _DEFAULT_TIMEOUT) -> Optional[Any]:
    import urllib.error
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": _USER_AGENT,
            "Accept":     "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 404 is a normal response — most companies don't file every GAAP
        # concept. Log at DEBUG so we don't fill production logs with
        # noise. The caller's cache shields us from repeat calls.
        if exc.code == 404:
            logger.debug("EDGAR concept not filed (404): %s", url[:120])
        else:
            logger.warning("EDGAR GET HTTP %d: %s", exc.code, url[:120])
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("EDGAR GET failed: %s | %s", url[:120], exc)
        return None


def cik_for_ticker(ticker: str) -> Optional[str]:
    if not ticker:
        return None
    return _TICKER_CIK_MAP.get(ticker.upper().strip())


def pull_concept(cik: str, concept: str) -> List[XBRLFact]:
    """Pull all reported facts for one US GAAP concept.

    Caches 404 responses per (cik, concept) so a single pipeline run
    doesn't repeat the same dead-concept call against SEC's 10 req/sec
    quota. Most companies don't file every GAAP concept in the env list —
    404 is the expected response shape and should not be retried within
    the same run.
    """
    if not cik:
        return []
    cik_padded = str(cik).zfill(10)
    cache_key = (cik_padded, concept)
    if _CONCEPT_404_CACHE.get(cache_key):
        return []
    url = f"{_BASE_URL}/companyconcept/CIK{cik_padded}/us-gaap/{concept}.json"
    data = _http_get_json(url)
    if not isinstance(data, dict):
        _CONCEPT_404_CACHE[cache_key] = True
        return []
    units = data.get("units") or {}
    facts: List[XBRLFact] = []
    for unit_name, rows in units.items():
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            val = r.get("val")
            if not isinstance(val, (int, float)):
                continue
            facts.append(XBRLFact(
                concept=concept,
                value=float(val),
                units=unit_name,
                fiscal_year=r.get("fy"),
                end_date=r.get("end"),
                form=r.get("form"),
            ))
    return facts


def environmental_capex_signal(cik: str, last_n_years: int = 3) -> Dict[str, Any]:
    """Aggregate environmental capex / liability concepts across last N FY."""
    if not cik:
        return {"available": False, "rationale": "missing CIK"}
    aggregated: Dict[str, Dict[str, float]] = {}
    for concept in _ENV_CONCEPTS:
        facts = pull_concept(cik, concept)
        for f in facts:
            if not f.fiscal_year:
                continue
            year_key = str(f.fiscal_year)
            aggregated.setdefault(concept, {})
            existing = aggregated[concept].get(year_key)
            # Take latest reported value per (concept, fiscal_year)
            if existing is None or (f.end_date and existing != f.value):
                aggregated[concept][year_key] = f.value
    if not aggregated:
        return {"available": False, "rationale": "no environmental concepts found in XBRL"}

    # Find the N most recent years across concepts
    all_years = sorted({y for v in aggregated.values() for y in v.keys()}, reverse=True)
    target_years = all_years[:last_n_years]
    rolled: Dict[str, float] = {y: 0.0 for y in target_years}
    rolled_by_concept: Dict[str, Dict[str, float]] = {}
    for concept, by_year in aggregated.items():
        rolled_by_concept[concept] = {}
        for y in target_years:
            v = by_year.get(y)
            if isinstance(v, (int, float)):
                rolled[y] += v
                rolled_by_concept[concept][y] = v

    return {
        "available":         True,
        "cik":               cik,
        "years":             target_years,
        "totals_by_year":    rolled,
        "by_concept_by_year": rolled_by_concept,
        "concepts_found":    sorted(aggregated.keys()),
        "rationale":         (
            f"Found {len(aggregated)} environmental US-GAAP concepts with "
            f"data across {len(target_years)} fiscal years."
        ),
    }
