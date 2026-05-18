"""Indian Kanoon — Indian case-law search (HTML scrape, no API).

Indian Kanoon (indiankanoon.org) is the canonical free Indian case-law search.
No public REST API; we scrape the search results page conservatively.

Usage notes:
  - Rate-limited via 1s sleep between calls (server-side anti-abuse threshold)
  - Returns coarse-grained metadata only (full opinion text would require a
    second per-doc fetch — out of scope for v1)
  - Status classifier mirrors CourtListener's taxonomy
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BASE_URL = "https://indiankanoon.org"
_DEFAULT_TIMEOUT = 20.0
_USER_AGENT = "esglens/1.0 (educational; +https://esglens.com)"


@dataclass
class IndianCase:
    case_id: str
    court: str
    case_name: str
    decision_date: Optional[str]
    status: str = "ACTIVE"
    summary: str = ""
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id":       self.case_id,
            "court":         self.court,
            "case_name":     self.case_name,
            "decision_date": self.decision_date,
            "status":        self.status,
            "summary":       self.summary,
            "url":           self.url,
        }


_TERMINATED_TOKENS = ("decided", "dismissed", "allowed", "disposed of", "decree")


def _http_get_text(url: str, timeout: float = _DEFAULT_TIMEOUT) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Indian Kanoon GET failed: %s | %s", url[:120], exc)
        return None


# Search results are rendered as <div class="result"> blocks with anchor +
# snippet. We extract conservatively; layout has been stable since ~2017.
_RESULT_RE = re.compile(
    r'<div class="result"[^>]*>\s*'
    r'<div class="result_title">\s*<a href="(?P<href>[^"]+)"[^>]*>(?P<title>[^<]+)</a>',
    re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'<div class="result_snippet">\s*(?P<snippet>.+?)</div>',
    re.DOTALL,
)


def search_cases(
    company_aliases: List[str],
    esg_terms: Optional[List[str]] = None,
    max_results: int = 15,
) -> List[IndianCase]:
    """Search Indian Kanoon for ESG-related cases. Single-page scrape."""
    if not company_aliases:
        return []
    alias = company_aliases[0]
    terms = esg_terms or ["pollution", "environment", "compliance"]
    q_alias = f'"{alias}"' if " " in alias else alias
    q_terms = " OR ".join(terms)
    full_q = f"{q_alias} AND ({q_terms})"
    url = f"{_BASE_URL}/search/?{urllib.parse.urlencode({'formInput': full_q, 'pagenum': 0})}"
    html = _http_get_text(url)
    time.sleep(1)  # rate-limit politeness
    if not html:
        return []
    cases: List[IndianCase] = []
    # Pair title matches with snippets in sequence
    title_matches = list(_RESULT_RE.finditer(html))
    snippet_matches = list(_SNIPPET_RE.finditer(html))
    for i, tm in enumerate(title_matches[:max_results]):
        href = tm.group("href")
        title = re.sub(r"\s+", " ", tm.group("title")).strip()
        snippet = ""
        if i < len(snippet_matches):
            snippet = re.sub(r"<[^>]+>", " ", snippet_matches[i].group("snippet"))
            snippet = re.sub(r"\s+", " ", snippet).strip()[:600]
        full_url = href if href.startswith("http") else f"{_BASE_URL}{href}"
        # Court from URL prefix: /doc/<id>/ doesn't carry court; pull from title
        # if pattern present, else mark unknown.
        court_match = re.search(
            r"\b(Supreme Court|High Court|NCLT|NGT|CESTAT|ITAT|Tribunal)\b",
            title + " " + snippet, re.IGNORECASE,
        )
        court = court_match.group(1).title() if court_match else "Unknown"
        # Decision date is the trailing year in title parens, sometimes
        date_match = re.search(r"\b(19|20)\d{2}\b", title)
        date = date_match.group(0) if date_match else None
        status = "ACTIVE"
        joined = (title + " " + snippet).lower()
        if any(tok in joined for tok in _TERMINATED_TOKENS):
            status = "SETTLED" if "settle" in joined else "DISMISSED" if "dismiss" in joined else "SETTLED"
        cases.append(IndianCase(
            case_id=full_url.rsplit("/", 2)[-2] if "/doc/" in full_url else full_url[:50],
            court=court,
            case_name=title,
            decision_date=date,
            status=status,
            summary=snippet,
            url=full_url,
        ))
    return cases
