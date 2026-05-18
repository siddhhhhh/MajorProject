"""GDELT 2.0 — real-time news event stream for ESG controversy detection.

Why: paid news APIs (NewsAPI, Bloomberg) cost real money. GDELT is free,
no-auth, 100+ languages, 15-minute event resolution. For ESG: catches
"adverse event count by company × ESG theme over last N days" without
licensing fees.

We use GDELT 2.0 DOC API (REST). The BigQuery path is more powerful but
adds an auth dependency we don't need for v1.

Endpoint reference:
    api.gdeltproject.org/api/v2/doc/doc
        ?query=<query>
        &format=json
        &timespan=<90day|1mon|7day|...>
        &maxrecords=<n>
        &sort=hybridrel

Public API:
    fetch_events(company_aliases, esg_keywords, timespan='90day') -> List[Event]
    decay_weighted_intensity(events, half_life_days=30) -> float
    summarise(events) -> Dict   # counts by tone, top sources, etc.

ESG keyword bundle versioned in core (config/esg_event_keywords.json).
Tone column ∈ [-100, +100]; we map to severity via abs(tone)/100.
"""

from __future__ import annotations

import json
import logging
import math
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_DEFAULT_TIMEOUT = 15.0
_USER_AGENT = "esglens/1.0 (educational; +https://esglens.com)"

# GDELT is keyless but rate-limits aggressively. The 429s we saw on
# TotalEnergies came from bursty queries inside a single pipeline run.
# Retry with exponential backoff + jitter so transient 429s don't drop
# the whole event stream.
_RETRY_STATUSES: tuple[int, ...] = (429, 500, 502, 503, 504)
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 2.0

# Bundled keyword sets. Versioned here for now; future task to externalise.
_ESG_KEYWORDS: Dict[str, List[str]] = {
    "environmental_adverse": [
        "pollution", "spill", "leak", "contamination", "violation",
        "emissions fraud", "greenwashing", "deforestation",
        "biodiversity loss", "habitat destruction", "wildfire",
        "carbon offset scandal", "environmental fine",
    ],
    "social_adverse": [
        "labor abuse", "child labor", "modern slavery", "human rights violation",
        "wage theft", "worker death", "factory collapse", "strike",
        "discrimination lawsuit", "harassment", "boycott",
    ],
    "governance_adverse": [
        "fraud", "bribery", "corruption", "accounting scandal",
        "insider trading", "SEC investigation", "shareholder lawsuit",
        "data breach", "money laundering", "executive misconduct",
    ],
    "climate_litigation": [
        "climate lawsuit", "fossil fuel lawsuit", "climate liability",
        "stranded assets", "transition risk litigation", "nzba exit",
        "ca100 exit", "scope 3 lawsuit",
    ],
}

# Tone severity threshold — events with |tone| below this are considered
# routine coverage, not adverse signal.
_TONE_SEVERITY_THRESHOLD = 3.0


@dataclass
class GdeltEvent:
    date: str           # YYYYMMDDHHMMSS
    headline: str
    source_domain: str
    url: str
    tone: float
    severity: float     # 0..1, max(0, -tone)/10 — negative tone is bad ESG news
    language: str = "english"
    theme_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date":           self.date,
            "headline":       self.headline,
            "source_domain":  self.source_domain,
            "url":            self.url,
            "tone":           self.tone,
            "severity":       self.severity,
            "language":       self.language,
            "theme_tags":     self.theme_tags,
        }


def _http_get_json(url: str, timeout: float = _DEFAULT_TIMEOUT) -> Optional[Any]:
    """GET JSON with retry-with-backoff on 429/5xx. GDELT honours
    ``Retry-After`` inconsistently; we fall back to exponential backoff
    with jitter when missing."""
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read().decode("utf-8", errors="replace")
                # GDELT sometimes returns 200 with an empty body or just
                # whitespace when it's silently rate-limited or the query
                # tripped a soft-throttle. json.loads on "" / "  " raises
                # "Expecting value" which used to be caught by the generic
                # Exception branch only at the LAST attempt — so the run
                # logged a JSON error instead of retrying. Treat any
                # body whose stripped length is zero as a 429-style
                # transient signal and retry with backoff.
                stripped = data.strip() if data else ""
                if not stripped:
                    if attempt + 1 < _MAX_RETRIES:
                        wait = _BACKOFF_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                        logger.info(
                            "GDELT empty-body 200 on attempt %d/%d — sleeping %.1fs",
                            attempt + 1, _MAX_RETRIES, wait,
                        )
                        time.sleep(wait)
                        continue
                    logger.warning(
                        "GDELT empty-body 200 — exhausted %d retries: %s",
                        _MAX_RETRIES, url[:120],
                    )
                    return None
                return json.loads(stripped)
        except urllib.error.HTTPError as exc:
            status = exc.code
            last_exc = exc
            if status in _RETRY_STATUSES and attempt + 1 < _MAX_RETRIES:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    wait = float(retry_after) if retry_after else 0.0
                except (TypeError, ValueError):
                    wait = 0.0
                if wait <= 0:
                    wait = _BACKOFF_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.info(
                    "GDELT HTTP %d on attempt %d/%d — sleeping %.1fs",
                    status, attempt + 1, _MAX_RETRIES, wait,
                )
                time.sleep(wait)
                continue
            logger.warning("GDELT GET failed: %s | HTTP %d", url[:120], status)
            return None
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt + 1 < _MAX_RETRIES:
                wait = _BACKOFF_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(wait)
                continue
            logger.warning("GDELT GET failed: %s | %s", url[:120], exc)
            return None
    if last_exc is not None:
        logger.warning("GDELT exhausted retries: %s | %s", url[:120], last_exc)
    return None


def _build_query(company_aliases: List[str], esg_keywords: List[str]) -> str:
    """Build a GDELT query string: <aliases> AND <esg terms>.

    GDELT syntax quirks:
      - Parens are ONLY allowed around OR groups with 2+ terms
      - Single-term clauses must be bare (no parens)
      - Multi-word phrases need double-quotes
      - Maximum query length around ~250 chars in practice
    """
    alias_clauses = [f'"{a}"' if " " in a else a for a in company_aliases if a]
    kw_clauses = [f'"{k}"' if " " in k else k for k in esg_keywords if k]
    if not alias_clauses or not kw_clauses:
        return ""

    def _group(clauses: List[str]) -> str:
        if len(clauses) == 1:
            return clauses[0]
        return "(" + " OR ".join(clauses) + ")"

    alias_part = _group(alias_clauses)
    kw_part = _group(kw_clauses)
    return f"{alias_part} AND {kw_part}"


def _parse_severity(tone: float) -> float:
    """Negative tone -> adverse signal. Map [-100, 0] to [0, 1] severity."""
    if tone is None or not isinstance(tone, (int, float)):
        return 0.0
    if tone >= 0:
        return 0.0  # neutral / positive = no adverse signal
    return min(1.0, abs(tone) / 10.0)


def fetch_events(
    company_aliases: List[str],
    keyword_themes: Optional[List[str]] = None,
    timespan: str = "90day",
    max_records: int = 75,
) -> List[GdeltEvent]:
    """Query GDELT for ESG-adverse coverage of `company` in `timespan`.

    keyword_themes: which of _ESG_KEYWORDS keys to include. None = all.
    Returns events sorted by severity descending.
    """
    if not company_aliases:
        return []
    themes = keyword_themes or list(_ESG_KEYWORDS.keys())
    keywords: List[str] = []
    for t in themes:
        keywords.extend(_ESG_KEYWORDS.get(t, []))
    if not keywords:
        return []

    # GDELT has a ~250 char query length cap in practice. Trim to top-N
    # of each side so the query fits.
    aliases_trimmed = company_aliases[:4]
    keywords_trimmed = keywords[:18]

    query = _build_query(aliases_trimmed, keywords_trimmed)
    if not query:
        return []

    params = {
        "query":      query,
        "format":     "json",
        "timespan":   timespan,
        "maxrecords": min(max_records, 250),
        "sort":       "hybridrel",
        "mode":       "ArtList",
    }
    url = _BASE_URL + "?" + urllib.parse.urlencode(params)
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return []
    articles = data.get("articles") or []
    out: List[GdeltEvent] = []
    seen_urls: set[str] = set()
    for a in articles:
        if not isinstance(a, dict):
            continue
        u = a.get("url") or ""
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        tone = float(a.get("tone") or 0.0)
        sev = _parse_severity(tone)
        if abs(tone) < _TONE_SEVERITY_THRESHOLD:
            continue  # Drop routine coverage
        out.append(GdeltEvent(
            date=str(a.get("seendate") or ""),
            headline=str(a.get("title") or "")[:240],
            source_domain=str(a.get("domain") or "").lower(),
            url=u,
            tone=tone,
            severity=sev,
            language=str(a.get("language") or "english").lower(),
            theme_tags=themes,
        ))
    out.sort(key=lambda e: e.severity, reverse=True)
    return out


def _days_since(date_str: str, now: Optional[datetime] = None) -> Optional[float]:
    """Parse GDELT YYYYMMDDHHMMSS and return days since."""
    if not date_str or len(date_str) < 8:
        return None
    try:
        # GDELT seendate is sometimes 'YYYYMMDDTHHMMSSZ' (ISO-ish); strip non-digits
        ds = re.sub(r"[^0-9]", "", date_str)[:14]
        if len(ds) < 8:
            return None
        # YYYYMMDDHHMMSS — pad shorter strings
        ds_full = ds + "000000"[: 14 - len(ds)] if len(ds) < 14 else ds[:14]
        dt = datetime.strptime(ds_full, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        ref = now or datetime.now(timezone.utc)
        return (ref - dt).total_seconds() / 86400.0
    except Exception:
        return None


def decay_weighted_intensity(events: List[GdeltEvent],
                             half_life_days: float = 30.0,
                             now: Optional[datetime] = None) -> float:
    """Sum (severity × exp(-age_days × ln(2)/half_life)) across events.

    Captures both recency and severity. Result is in arbitrary units; the
    ledger consumer maps to a GW point delta.
    """
    if not events:
        return 0.0
    decay_k = math.log(2.0) / max(1.0, half_life_days)
    total = 0.0
    for e in events:
        age = _days_since(e.date, now=now)
        if age is None or age < 0:
            continue
        total += e.severity * math.exp(-decay_k * age)
    return round(total, 3)


def summarise(events: List[GdeltEvent]) -> Dict[str, Any]:
    """Aggregate counts: by tone band, top domains, by theme."""
    if not events:
        return {
            "total_count":  0,
            "by_tone_band": {},
            "top_domains":  [],
            "by_theme":     {},
        }
    by_tone = {"very_negative": 0, "negative": 0, "mild_negative": 0}
    domain_counts: Dict[str, int] = {}
    theme_counts: Dict[str, int] = {}
    for e in events:
        if e.tone <= -7.0:
            by_tone["very_negative"] += 1
        elif e.tone <= -4.0:
            by_tone["negative"] += 1
        else:
            by_tone["mild_negative"] += 1
        domain_counts[e.source_domain] = domain_counts.get(e.source_domain, 0) + 1
        for t in e.theme_tags:
            theme_counts[t] = theme_counts.get(t, 0) + 1
    top_domains = sorted(
        domain_counts.items(), key=lambda x: x[1], reverse=True
    )[:10]
    return {
        "total_count":  len(events),
        "by_tone_band": by_tone,
        "top_domains":  [{"domain": d, "count": c} for d, c in top_domains],
        "by_theme":     theme_counts,
    }


def list_available_themes() -> List[str]:
    return sorted(_ESG_KEYWORDS.keys())
