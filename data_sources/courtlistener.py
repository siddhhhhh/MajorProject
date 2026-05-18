"""CourtListener — real US federal court docket lookups.

Replaces today's pattern-match "active enforcement" heuristic with actual
docket status. Free, anonymous REST. Rate-limited to ~5000/day per IP.

API base: https://www.courtlistener.com/api/rest/v3/
Endpoints used:
    /search/?q=<query>&type=r          # search RECAP (federal) dockets
    /opinions/<id>/                    # opinion text + metadata

The status classifier maps `date_terminated`, `nature_of_suit`, and recent
docket entries to one of:
    ACTIVE     — case is open, no terminating judgment
    SETTLED    — case terminated with settlement / consent decree
    DISMISSED  — case terminated by dismissal / summary judgment

Public API:
    search_cases(company_aliases, esg_keywords, since_year) -> List[Case]
    classify_status(case) -> str
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.courtlistener.com/api/rest/v3"
_DEFAULT_TIMEOUT = 20.0
_USER_AGENT = "esglens/1.0 (educational; +https://esglens.com)"

# CourtListener now serves 403 to fully-anonymous traffic for /search/.
# An API token (free, https://www.courtlistener.com/help/api/rest/) lifts
# the rate limit to ~5,000/hr. Set via env: ``COURTLISTENER_API_TOKEN``.
_RETRY_STATUSES: tuple[int, ...] = (429, 500, 502, 503, 504)
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.5

# Keywords expanded from ESG litigation common terms
_LITIGATION_KEYWORDS_ESG = (
    "climate", "emissions", "pollution", "environmental",
    "greenhouse gas", "carbon", "deforestation", "spill",
    "human rights", "child labor", "modern slavery",
    "fraud", "deceptive trade practices", "consumer fraud",
    "shareholder derivative", "securities fraud",
)


@dataclass
class CaseRecord:
    case_id: str
    court: str
    case_name: str
    filed_date: Optional[str]
    terminated_date: Optional[str]
    nature_of_suit: Optional[str]
    status: str = "ACTIVE"
    monetary_penalty_usd: Optional[float] = None
    summary: str = ""
    url: str = ""
    last_known_event: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id":              self.case_id,
            "court":                self.court,
            "case_name":            self.case_name,
            "filed_date":           self.filed_date,
            "terminated_date":      self.terminated_date,
            "nature_of_suit":       self.nature_of_suit,
            "status":               self.status,
            "monetary_penalty_usd": self.monetary_penalty_usd,
            "summary":              self.summary,
            "url":                  self.url,
            "last_known_event":     self.last_known_event,
        }


def _build_headers() -> Dict[str, str]:
    """Build request headers — adds ``Authorization: Token <key>`` when the
    ``COURTLISTENER_API_TOKEN`` env var is set."""
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    token = (os.environ.get("COURTLISTENER_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Token {token}"
    return headers


def _http_get_json(url: str, timeout: float = _DEFAULT_TIMEOUT) -> Optional[Any]:
    """GET JSON with retry-with-backoff on 429/5xx. Honors ``Retry-After``
    when the server sends it; otherwise uses exponential backoff with jitter."""
    headers = _build_headers()
    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            status = exc.code
            last_exc = exc
            if status == 403 and "Authorization" not in headers:
                logger.warning(
                    "CourtListener 403 (anonymous request denied). Set "
                    "COURTLISTENER_API_TOKEN env var — free signup at "
                    "https://www.courtlistener.com/help/api/rest/"
                )
                return None
            if status in _RETRY_STATUSES and attempt + 1 < _MAX_RETRIES:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    wait = float(retry_after) if retry_after else 0.0
                except (TypeError, ValueError):
                    wait = 0.0
                if wait <= 0:
                    wait = _BACKOFF_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.info(
                    "CourtListener HTTP %d on attempt %d/%d — sleeping %.1fs",
                    status, attempt + 1, _MAX_RETRIES, wait,
                )
                time.sleep(wait)
                continue
            logger.warning("CourtListener GET failed: %s | HTTP %d", url[:120], status)
            return None
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt + 1 < _MAX_RETRIES:
                wait = _BACKOFF_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(wait)
                continue
            logger.warning("CourtListener GET failed: %s | %s", url[:120], exc)
            return None
    if last_exc is not None:
        logger.warning("CourtListener exhausted retries: %s | %s", url[:120], last_exc)
    return None


_SETTLED_PATTERNS = (
    "settlement", "settled", "consent decree", "consent judgment",
    "stipulated dismissal", "voluntary dismissal with payment",
)
_DISMISSED_PATTERNS = (
    "dismissed", "dismissal", "summary judgment for defendant",
    "judgment as a matter of law", "denied",
)


def classify_status(case: CaseRecord) -> str:
    """Return ACTIVE | SETTLED | DISMISSED based on terminated_date + text cues."""
    if not case.terminated_date:
        return "ACTIVE"
    # Look at summary + last_known_event for cue patterns
    blob = " ".join(filter(None, [case.summary, case.last_known_event])).lower()
    for pat in _SETTLED_PATTERNS:
        if pat in blob:
            return "SETTLED"
    for pat in _DISMISSED_PATTERNS:
        if pat in blob:
            return "DISMISSED"
    # Has terminated_date but no clear cue — default SETTLED (more conservative
    # than DISMISSED for ESG scoring; analyst can override).
    return "SETTLED"


_USD_AMOUNT_RE = re.compile(
    r"\$\s*([0-9]{1,3}(?:[,.][0-9]{3})*(?:[.,][0-9]+)?)\s*"
    r"(?:million|billion|thousand|m|b|k)?",
    re.IGNORECASE,
)


def _extract_monetary_penalty(summary: str) -> Optional[float]:
    """Pull the largest $-amount from summary text (USD-equivalent)."""
    if not summary:
        return None
    amounts: List[float] = []
    for m in _USD_AMOUNT_RE.finditer(summary):
        raw = m.group(1).replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        tail = (summary[m.end():m.end() + 12] or "").lower()
        if "billion" in tail or tail.startswith("b"):
            val *= 1e9
        elif "million" in tail or tail.startswith("m"):
            val *= 1e6
        elif "thousand" in tail or tail.startswith("k"):
            val *= 1e3
        amounts.append(val)
    if not amounts:
        return None
    return max(amounts)


def search_cases(
    company_aliases: List[str],
    since_year: Optional[int] = None,
    max_results: int = 25,
) -> List[CaseRecord]:
    """Search RECAP for ESG-related cases naming any of `company_aliases`.

    Constrains by ESG-litigation keyword bundle to filter contractual /
    employment disputes outside scope.
    """
    if not company_aliases:
        return []
    # First alias as primary; OR-join supplemental
    primary_aliases = company_aliases[:3]
    alias_q = " OR ".join(f'"{a}"' for a in primary_aliases)
    esg_q = " OR ".join(_LITIGATION_KEYWORDS_ESG[:12])
    q = f"({alias_q}) AND ({esg_q})"
    params = {
        "q": q,
        "type": "r",        # RECAP federal dockets
        "order_by": "dateFiled desc",
    }
    if since_year:
        params["filed_after"] = f"{since_year}-01-01"
    url = f"{_BASE_URL}/search/?{urllib.parse.urlencode(params)}"
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return []
    results = data.get("results") or []
    cases: List[CaseRecord] = []
    for r in results[:max_results]:
        if not isinstance(r, dict):
            continue
        summary = " | ".join(filter(None, [
            r.get("snippet") or "",
            r.get("description") or "",
            r.get("caseName") or "",
        ]))[:1200]
        case_id = str(r.get("docket_id") or r.get("id") or r.get("absolute_url") or "")
        case = CaseRecord(
            case_id=case_id,
            court=str(r.get("court") or r.get("courtCitation") or "?"),
            case_name=str(r.get("caseName") or r.get("name") or "Unknown case"),
            filed_date=r.get("dateFiled") or r.get("filing_date"),
            terminated_date=r.get("dateTerminated") or r.get("terminationDate"),
            nature_of_suit=r.get("suitNature") or r.get("nature_of_suit"),
            summary=summary,
            url=("https://www.courtlistener.com" + str(r.get("absolute_url") or ""))
                if r.get("absolute_url") else "",
        )
        case.monetary_penalty_usd = _extract_monetary_penalty(case.summary)
        case.status = classify_status(case)
        cases.append(case)
    return cases
