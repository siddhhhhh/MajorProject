"""
esg_data_apis.py
================
Structured API clients for WBA (World Benchmarking Alliance) and
WRI Aqueduct 4.0 to fill Social, Governance, and Water-Risk pillar
scores that IR page scraping fails to provide.

Dependencies
------------
    pip install httpx python-dotenv
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USER_AGENT = (
    "ESGLens/1.0 AdminContact@esglens.com"
)
_TIMEOUT = 20  # seconds
_WBA_RATE_LIMIT_SECONDS = 1.05
_WBA_MAX_RETRIES = 3

# WBA endpoints
_WBA_BASE = "https://data.worldbenchmarkingalliance.org/api/data/v1"

# WRI Aqueduct 4.0 endpoint
_WRI_BASE = "https://api.resourcewatch.org/v1/aqueduct"

# WRI indicator → risk category mapping (Aqueduct 4.0, all 13 indicators)
_WRI_PHYSICAL: list[str] = ["bws", "bwd", "iav", "sev", "gtd", "rfr", "cfr", "drr"]
_WRI_REGULATORY: list[str] = ["udw", "usa", "cep"]
_WRI_REPUTATIONAL: list[str] = ["rri", "eco"]


# ===================================================================
# WBA — World Benchmarking Alliance
# ===================================================================

def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_score_0_100(value: Any) -> float | None:
    parsed = _safe_float(value)
    if parsed is None:
        return None

    # WBA fields appear in mixed scales across datasets.
    # Normalize common ranges into a 0-100 score for internal scoring.
    if parsed <= 1.0:
        parsed = parsed * 100.0
    elif parsed <= 5.0:
        parsed = parsed * 20.0

    return max(0.0, min(100.0, float(parsed)))


def _normalize_name(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _extract_http_detail(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None

    if isinstance(payload, dict):
        detail = payload.get("detail")
        return str(detail) if detail else None
    return None


def _extract_company_coordinates(company_row: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not isinstance(company_row, dict):
        return None, None

    def _candidate_number(keys: tuple[str, ...]) -> float | None:
        for key, value in company_row.items():
            key_l = str(key).lower()
            if any(k in key_l for k in keys):
                parsed = _safe_float(value)
                if parsed is not None:
                    return parsed
        return None

    lat = _candidate_number(("lat", "latitude"))
    lon = _candidate_number(("lon", "lng", "longitude"))

    if lat is None or lon is None:
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None
    return lat, lon


def _wba_dataset_get(
    client: httpx.Client,
    dataset_name: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    url = f"{_WBA_BASE}/datasets/{dataset_name}"
    last_error: Exception | None = None

    for attempt in range(_WBA_MAX_RETRIES):
        try:
            response = client.get(url, params=params)
            if response.status_code == 429:
                retry_after_raw = response.headers.get("Retry-After")
                retry_after = _safe_float(retry_after_raw) or _WBA_RATE_LIMIT_SECONDS
                wait_seconds = max(_WBA_RATE_LIMIT_SECONDS, retry_after)
                logger.warning(
                    "WBA rate limit hit for dataset '%s' (attempt %d/%d); sleeping %.2fs",
                    dataset_name,
                    attempt + 1,
                    _WBA_MAX_RETRIES,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            if isinstance(payload, list):
                return {"data": payload, "meta": {}}
            return {"data": [], "meta": {}}
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt + 1 < _WBA_MAX_RETRIES:
                time.sleep(_WBA_RATE_LIMIT_SECONDS)
                continue
            raise
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if 500 <= status < 600 and attempt + 1 < _WBA_MAX_RETRIES:
                backoff = _WBA_RATE_LIMIT_SECONDS * (attempt + 1)
                time.sleep(backoff)
                continue
            raise
        except (TypeError, ValueError) as exc:
            last_error = exc
            break

    if last_error is not None:
        raise last_error
    return {"data": [], "meta": {}}


def _pick_best_company_match(rows: list[dict[str, Any]], company_name: str) -> dict[str, Any] | None:
    if not rows:
        return None

    target = _normalize_name(company_name)

    def _rank(row: dict[str, Any]) -> tuple[int, int, int]:
        candidate_name = row.get("company_name") or row.get("name") or ""
        normalized_candidate = _normalize_name(candidate_name)

        is_exact = 0 if normalized_candidate == target else 1
        contains_target = 0 if target and target in normalized_candidate else 1
        length_distance = abs(len(normalized_candidate) - len(target))
        return (is_exact, contains_target, length_distance)

    return sorted(rows, key=_rank)[0]


def _is_sdg2000_company(row: dict[str, Any]) -> bool:
    """Best-effort flag for WBA SDG2000 coverage."""
    if not isinstance(row, dict):
        return False

    for key, value in row.items():
        key_l = str(key).lower()
        value_l = str(value or "").lower()
        if "sdg2000" in key_l or "sdg2000" in value_l:
            return True
        if "list" in key_l or "universe" in key_l or "benchmark" in key_l:
            if "sdg" in value_l and "2000" in value_l:
                return True
    return False


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _extract_row_score(row: dict[str, Any]) -> float | None:
    preferred_keys = [
        "benchmark_score_numerical",
        "score_numerical",
        "indicator_score_numerical",
        "score",
        "value",
    ]
    for key in preferred_keys:
        if key in row:
            parsed = _normalize_score_0_100(row.get(key))
            if parsed is not None:
                return parsed

    for key, val in row.items():
        parsed = _normalize_score_0_100(val)
        if parsed is None:
            continue
        key_l = str(key).lower()
        if "score" in key_l or "value" in key_l:
            return parsed
    return None


def _collect_wba_scores(
    benchmark_rows: list[dict[str, Any]],
    indicator_rows: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, float]]:
    pillar_values: dict[str, list[float]] = {
        "social": [],
        "governance": [],
        "environment": [],
    }
    indicators: dict[str, float] = {}

    pillar_keywords: dict[str, tuple[str, ...]] = {
        "social": ("social", "worker", "human rights", "inclusion", "community"),
        "governance": ("governance", "board", "ethic", "transparency", "corruption"),
        "environment": ("environment", "climate", "carbon", "emission", "energy", "water", "nature"),
    }

    total_candidates: list[float] = []

    for row in benchmark_rows + indicator_rows:
        if not isinstance(row, dict):
            continue

        row_score = _extract_row_score(row)
        row_context = " ".join(
            str(row.get(k, ""))
            for k in (
                "benchmark_name",
                "measurement_area_name",
                "indicator_name",
                "element_name",
                "attribute_name",
                "name",
            )
        ).lower()

        if row_score is not None:
            if "benchmark_score_numerical" in row:
                total_candidates.append(row_score)

            indicator_name = (
                row.get("indicator_name")
                or row.get("measurement_area_name")
                or row.get("element_name")
                or row.get("benchmark_name")
                or row.get("name")
            )
            if indicator_name:
                indicators[str(indicator_name)] = row_score

            for pillar, keywords in pillar_keywords.items():
                if any(keyword in row_context for keyword in keywords):
                    pillar_values[pillar].append(row_score)

        # Also map explicit numeric columns such as social_score/governance_score fields.
        for key, value in row.items():
            key_lower = str(key).lower()
            parsed = _normalize_score_0_100(value)
            if parsed is None:
                continue

            if "social" in key_lower:
                pillar_values["social"].append(parsed)
            if "governance" in key_lower:
                pillar_values["governance"].append(parsed)
            if "environment" in key_lower or "climate" in key_lower:
                pillar_values["environment"].append(parsed)
            if key_lower in ("benchmark_score_numerical", "total", "overall_score"):
                total_candidates.append(parsed)

    scores: dict[str, float] = {}
    for pillar, values in pillar_values.items():
        if values:
            scores[pillar] = round(sum(values) / len(values), 3)

    if total_candidates:
        scores["total"] = round(sum(total_candidates) / len(total_candidates), 3)
    elif indicators:
        scores["total"] = round(sum(indicators.values()) / len(indicators), 3)

    return scores, indicators


def _extract_latest_methodology_year(rows: list[dict[str, Any]]) -> int | None:
    years: list[int] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for key in ("methodology_year", "year", "reporting_year"):
            value = row.get(key)
            if isinstance(value, (int, float)):
                y = int(value)
                if 1990 <= y <= 2100:
                    years.append(y)
            elif isinstance(value, str):
                m = re.search(r"\b(20\d{2})\b", value)
                if m:
                    years.append(int(m.group(1)))
    return max(years) if years else None


# ---------------------------------------------------------------------------
# Alias resolution — WBA records often use the company's pre-rebrand name or
# a shorter form. "TotalEnergies SE" misses; "Total" hits. Same for
# Meta/Facebook, Alphabet/Google, X/Twitter. We try a ranked list of
# candidates before giving up.
# ---------------------------------------------------------------------------
_CORPORATE_SUFFIXES: tuple[str, ...] = (
    " SE", " AG", " plc", " PLC", " Plc", " Ltd", " Ltd.", " Limited",
    " Inc", " Inc.", " Incorporated", " LLC", " L.L.C.", " NV", " N.V.",
    " SA", " S.A.", " S.p.A.", " SpA", " SAS", " S.A.S.", " GmbH", " AB",
    " ASA", " AS", " A/S", " Corp", " Corp.", " Corporation",
    " Holdings", " Holding", " Group", " & Co", " Co.", " Co",
    " Company", " Pty Ltd", " (Holdings)", " S.E.",
)

# Known major rebrands. Keep this small and well-justified — every entry is
# verified against the historical record (year of rename in comment).
_KNOWN_REBRANDS: dict[str, tuple[str, ...]] = {
    "totalenergies": ("Total", "TotalEnergies", "Total SA", "Total S.A."),  # 2021
    "meta": ("Facebook", "Meta", "Meta Platforms"),                          # 2021
    "alphabet": ("Google", "Alphabet"),                                      # 2015
    "x corp": ("Twitter", "X Corp", "X"),                                    # 2023
    "warner bros discovery": ("WarnerMedia", "Discovery", "Warner Bros"),    # 2022
    "kraft heinz": ("Kraft", "Heinz", "Kraft Heinz"),                        # 2015
    "international business machines": ("IBM", "International Business Machines"),
    "jpmorgan chase": ("JPMorgan", "JP Morgan", "Chase", "JPMorgan Chase"),
    "berkshire hathaway": ("Berkshire", "Berkshire Hathaway"),
    "exxonmobil": ("Exxon", "Mobil", "ExxonMobil", "Exxon Mobil"),
}


def _camelcase_split(name: str) -> list[str]:
    """Split a CamelCase name into space-separated tokens.

    ``TotalEnergies`` -> ``["Total", "Energies"]``
    ``IBM`` -> ``["IBM"]``
    """
    if not name:
        return []
    # Match either a Capital+lowercase run, or an all-caps run, or a lowercase run.
    return re.findall(r"[A-Z][a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|[a-z]+", name) or [name]


def generate_company_aliases(name: str) -> list[str]:
    """Return ranked candidate names to try against a registry, most-specific
    first. Pure function (no I/O). Exposed for unit testing."""
    raw = (name or "").strip()
    if not raw:
        return []

    seen: set[str] = set()
    ordered: list[str] = []

    def _add(c: str) -> None:
        c2 = re.sub(r"\s+", " ", (c or "")).strip(" ,.")
        if c2 and c2.lower() not in seen:
            seen.add(c2.lower())
            ordered.append(c2)

    _add(raw)

    # Strip corporate suffixes, possibly multiple (e.g. "X Corp Holdings").
    stripped = raw
    changed = True
    while changed:
        changed = False
        for sfx in _CORPORATE_SUFFIXES:
            if stripped.lower().endswith(sfx.lower()):
                stripped = stripped[: -len(sfx)].rstrip(" ,.")
                changed = True
                break
    if stripped and stripped.lower() != raw.lower():
        _add(stripped)

    # Known rebrands — match either by canonical key or any of its aliases.
    low = stripped.lower()
    for key, aliases in _KNOWN_REBRANDS.items():
        if key in low or any(a.lower() in low for a in aliases):
            for a in aliases:
                _add(a)

    # CamelCase split (e.g. "TotalEnergies" -> "Total Energies", "Total").
    parts = _camelcase_split(stripped)
    if len(parts) >= 2 and any(len(p) >= 3 for p in parts):
        _add(" ".join(parts))
        if len(parts[0]) >= 3:
            _add(parts[0])

    return ordered


def get_wba_company_assessment_with_aliases(
    company_name: str,
    api_key: str | None = None,
    *,
    max_aliases: int = 6,
) -> dict[str, Any]:
    """Wrapper around :func:`get_wba_company_assessment` that tries multiple
    alias candidates (corporate suffix stripped, known rebrands, CamelCase
    split) before giving up. Returns on the first successful match.

    The returned dict carries:
      - ``query_company_name`` — the original input
      - ``query_attempts`` — number of aliases tried (1-based)
      - ``aliases_tried`` — full ranked list, for diagnostics
    """
    aliases = generate_company_aliases(company_name)[:max_aliases]
    if not aliases:
        return {
            "found": False,
            "company_name": company_name,
            "error": "Empty company name — no aliases generated",
            "query_company_name": company_name,
            "query_attempts": 0,
            "aliases_tried": [],
        }

    last_result: dict[str, Any] | None = None
    for idx, alias in enumerate(aliases, start=1):
        result = get_wba_company_assessment(alias, api_key=api_key)
        result["query_company_name"] = company_name
        result["query_attempts"] = idx
        result["aliases_tried"] = aliases
        if result.get("found"):
            if alias != company_name:
                logger.info(
                    "WBA: matched '%s' via alias '%s' (attempt %d/%d)",
                    company_name, alias, idx, len(aliases),
                )
            return result
        last_result = result

    assert last_result is not None  # loop ran at least once
    last_result["error"] = (
        f"No WBA match for any alias of '{company_name}' "
        f"(tried {len(aliases)}: {aliases})"
    )
    return last_result


def get_wba_company_assessment(
    company_name: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch WBA company data via the WBA Data API datasets endpoints.

    Parameters
    ----------
    company_name : str
        Company name to search for (e.g. ``"Shell"``).
    api_key : str | None
        WBA API key.  Falls back to ``os.environ.get("WBA_API_KEY")``.

    Returns
    -------
    dict
        Keys: ``found``, ``company_name``, ``scores``, ``indicators``,
        ``raw``, ``error``.
    """
    result: dict[str, Any] = {
        "found": False,
        "company_name": company_name,
        "scores": {},
        "indicators": {},
        "hq_coordinates": {"lat": None, "lon": None},
        "raw": None,
        "error": None,
        "sdg2000": False,
    }

    api_key = (api_key or os.environ.get("WBA_API_KEY") or "").strip()
    if not api_key:
        result["error"] = "WBA_API_KEY not set"
        logger.warning("WBA: API key not available — skipping")
        return result

    headers = {
        "User-Agent": USER_AGENT,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=_TIMEOUT, headers=headers) as client:
            company_payload = _wba_dataset_get(
                client,
                "companies",
                {
                    "company_name__co": company_name,
                    "per_page": 50,
                    "page": 1,
                },
            )
            companies = company_payload.get("data") if isinstance(company_payload, dict) else []
            companies = [row for row in (companies or []) if isinstance(row, dict)]

            if not companies:
                result["error"] = f"No WBA company found for '{company_name}'"
                logger.info("WBA: no company rows found for '%s'", company_name)
                return result

            sdg2000_companies = [row for row in companies if _is_sdg2000_company(row)]
            company_pool = sdg2000_companies or companies
            company = _pick_best_company_match(company_pool, company_name) or company_pool[0]
            company_id = company.get("company_id") or company.get("id")
            result["company_name"] = str(company.get("company_name") or company.get("name") or company_name)
            result["sdg2000"] = _is_sdg2000_company(company)
            lat, lon = _extract_company_coordinates(company)
            result["hq_coordinates"] = {"lat": lat, "lon": lon}

            time.sleep(_WBA_RATE_LIMIT_SECONDS)

            benchmark_params: dict[str, Any] = {
                "per_page": 1000,
                "page": 1,
                "order_by": "methodology_year",
                "ascending": "false",
            }
            if company_id:
                benchmark_params["company_id"] = company_id
            else:
                benchmark_params["company_name__co"] = result["company_name"]

            benchmark_payload = _wba_dataset_get(client, "benchmarks", benchmark_params)
            benchmark_rows = benchmark_payload.get("data") if isinstance(benchmark_payload, dict) else []
            benchmark_rows = [row for row in (benchmark_rows or []) if isinstance(row, dict)]

            time.sleep(_WBA_RATE_LIMIT_SECONDS)

            indicator_params: dict[str, Any] = {
                "per_page": 1000,
                "page": 1,
            }
            if company_id:
                indicator_params["company_id"] = company_id
            else:
                indicator_params["company_name__co"] = result["company_name"]

            indicator_payload = _wba_dataset_get(client, "indicators", indicator_params)
            indicator_rows = indicator_payload.get("data") if isinstance(indicator_payload, dict) else []
            indicator_rows = [row for row in (indicator_rows or []) if isinstance(row, dict)]

            scores, indicators = _collect_wba_scores(benchmark_rows, indicator_rows)
            result["scores"].update(scores)
            result["indicators"].update(indicators)

            result["raw"] = {
                "company": company,
                "benchmarks_meta": benchmark_payload.get("meta", {}) if isinstance(benchmark_payload, dict) else {},
                "indicators_meta": indicator_payload.get("meta", {}) if isinstance(indicator_payload, dict) else {},
                "benchmarks_rows": benchmark_rows,
                "indicator_rows": indicator_rows,
            }
            result["data_year"] = _extract_latest_methodology_year(benchmark_rows + indicator_rows)

            result["found"] = bool(result["scores"] or result["indicators"])
            logger.info(
                "WBA: fetched data for '%s' — %d pillar scores, %d indicators",
                result["company_name"],
                len(result["scores"]),
                len(result["indicators"]),
            )

    except httpx.TimeoutException:
        result["error"] = f"WBA API timed out for '{company_name}'"
        logger.warning("WBA: request timed out for '%s'", company_name)
    except httpx.HTTPStatusError as exc:
        detail = _extract_http_detail(exc.response)
        status = exc.response.status_code
        if status == 401:
            result["error"] = "WBA API unauthorized (check WBA_API_KEY bearer token)"
        elif detail:
            result["error"] = f"WBA API HTTP {status}: {detail}"
        else:
            result["error"] = f"WBA API HTTP {status}"
        logger.warning("WBA: HTTP %d for '%s'", status, company_name)
    except httpx.HTTPError as exc:
        result["error"] = f"WBA API error: {exc}"
        logger.warning("WBA: request failed for '%s' — %s", company_name, exc)
    except (ValueError, KeyError, TypeError) as exc:
        result["error"] = f"WBA parse error: {exc}"
        logger.warning("WBA: failed to parse response for '%s' — %s", company_name, exc)

    return result


def _score_governance_from_sec_metrics(metrics: dict[str, Any]) -> float | None:
    score = 0.0
    signals = 0

    if metrics.get("executive_comp_esg_links") is True:
        score += 35.0
        signals += 1
    elif metrics.get("executive_comp_esg_links") is False:
        score += 10.0
        signals += 1

    if metrics.get("board_diversity_pct") is not None:
        diversity = float(metrics["board_diversity_pct"])
        score += min(30.0, max(10.0, diversity * 0.75))
        signals += 1

    if metrics.get("executive_pay_ratio") is not None:
        ratio = float(metrics["executive_pay_ratio"])
        if ratio <= 100:
            score += 25.0
        elif ratio <= 200:
            score += 18.0
        else:
            score += 10.0
        signals += 1

    if signals == 0:
        return None
    return round(max(0.0, min(100.0, score)), 3)


def _score_social_from_form_sd(metrics: dict[str, Any]) -> float | None:
    if not metrics.get("conflict_minerals_human_rights"):
        return None

    score = 55.0
    if metrics.get("supplier_due_diligence"):
        score += 15.0
    if metrics.get("smelter_refiner_disclosure"):
        score += 10.0
    return round(min(100.0, score), 3)


def _find_filing_document_url(client: httpx.Client, filing_index_url: str, headers: dict[str, str]) -> str | None:
    try:
        resp = client.get(filing_index_url, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="tableFile")
        if not table:
            return None

        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            href = cols[2].find("a")
            doc_type = cols[3].get_text(" ", strip=True).upper()
            if not href:
                continue
            link = href.get("href", "")
            if not link:
                continue
            if doc_type in {"DEF 14A", "DEFA14A", "SD", "EX-1.01", "10-K"} or link.endswith((".htm", ".html", ".txt")):
                return f"https://www.sec.gov{link}" if link.startswith("/") else link
    except Exception:
        return None
    return None


def _lookup_sec_company_record(client: httpx.Client, company_name: str) -> dict[str, Any] | None:
    try:
        resp = client.get("https://www.sec.gov/files/company_tickers.json")
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return None

    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        rows = [value for value in payload.values() if isinstance(value, dict)]
    elif isinstance(payload, list):
        rows = [value for value in payload if isinstance(value, dict)]

    target = _normalize_name(company_name)
    if not rows:
        return None

    def _rank(row: dict[str, Any]) -> tuple[int, int]:
        title = _normalize_name(row.get("title"))
        exact = 0 if title == target else 1
        contains = 0 if target and target in title else 1
        return (exact, contains)

    ranked = sorted(rows, key=_rank)
    best = ranked[0]
    if _rank(best) == (1, 1):
        return None
    return best


def _get_sec_submission_filing(
    client: httpx.Client,
    company_name: str,
    form_type: str,
) -> dict[str, Any] | None:
    company_record = _lookup_sec_company_record(client, company_name)
    if not company_record:
        return None

    cik = str(company_record.get("cik_str") or "").strip()
    if not cik:
        return None

    cik_padded = cik.zfill(10)
    try:
        resp = client.get(f"https://data.sec.gov/submissions/CIK{cik_padded}.json")
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return None

    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    accession_numbers = recent.get("accessionNumber", []) or []
    filing_dates = recent.get("filingDate", []) or []
    primary_docs = recent.get("primaryDocument", []) or []

    for idx, form in enumerate(forms):
        if str(form).upper() != form_type.upper():
            continue
        accession = str(accession_numbers[idx]).replace("-", "")
        primary_doc = str(primary_docs[idx])
        filing_date = str(filing_dates[idx])
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession}/{primary_doc}"
        )
        return {
            "filing_url": filing_url,
            "filing_date": filing_date,
            "company_title": company_record.get("title"),
            "ticker": company_record.get("ticker"),
            "cik": cik,
        }

    return None


def _extract_def14a_metrics(text: str) -> dict[str, Any]:
    text_norm = re.sub(r"\s+", " ", text or " ")
    lower = text_norm.lower()

    executive_comp_esg_links = None
    comp_match = re.search(
        r"(executive compensation|annual incentive|cash incentive|bonus|compensation committee)[^.]{0,220}"
        r"(esg|environmental|sustainability|climate|human capital|diversity)",
        lower,
        flags=re.IGNORECASE,
    )
    if comp_match:
        executive_comp_esg_links = True

    pay_ratio = None
    for pattern in [
        r"pay ratio[^0-9]{0,30}(\d{1,4})\s*(?::|to)\s*1",
        r"ratio of the annual total compensation[^0-9]{0,60}(\d{1,4})\s*(?::|to)\s*1",
        r"ceo pay ratio[^0-9]{0,30}(\d{1,4})\s*(?::|to)\s*1",
        r"ceo to median employee pay ratio[^0-9]{0,30}(\d{1,4})\s*(?::|to)\s*1",
        r"pay ratio(?:.*?is)?\s*(\d{1,4})\s*(?::|to)\s*1",
    ]:
        match = re.search(pattern, lower, flags=re.IGNORECASE)
        if match:
            pay_ratio = _safe_int(match.group(1))
            break

    board_diversity_pct = None
    for pattern in [
        r"(\d{1,3}(?:\.\d+)?)\s*%\s+(?:of\s+)?(?:our\s+)?board[^.]{0,60}(?:women|female|diverse)",
        r"(?:women|female|diverse)[^.]{0,60}board[^.]{0,40}(\d{1,3}(?:\.\d+)?)\s*%",
        r"board diversity.*?(?:is|of|at)\s*(\d{1,3}(?:\.\d+)?)\s*%",
        r"(\d{1,3}(?:\.\d+)?)\s*%\s+board diversity",
    ]:
        match = re.search(pattern, lower, flags=re.IGNORECASE)
        if match:
            try:
                board_diversity_pct = float(match.group(1))
                break
            except ValueError:
                continue

    if board_diversity_pct is None:
        diversity_count_match = re.search(
            r"(\d{1,2})\s+of\s+(\d{1,2})\s+(?:director|board member)[^.]{0,40}(?:women|female|diverse)",
            lower,
            flags=re.IGNORECASE,
        )
        if diversity_count_match:
            numerator = _safe_int(diversity_count_match.group(1))
            denominator = _safe_int(diversity_count_match.group(2))
            if numerator is not None and denominator:
                board_diversity_pct = round((numerator / denominator) * 100.0, 1)

    metrics = {
        "executive_comp_esg_links": executive_comp_esg_links,
        "executive_pay_ratio": pay_ratio,
        "board_diversity_pct": board_diversity_pct,
    }
    return metrics


def _extract_form_sd_metrics(text: str) -> dict[str, Any]:
    lower = re.sub(r"\s+", " ", text or " ").lower()
    return {
        "conflict_minerals_human_rights": (
            "conflict minerals" in lower and
            any(term in lower for term in ["human rights", "responsible sourcing", "due diligence", "drc", "cobalt", "tin", "tantalum", "tungsten", "gold"])
        ),
        "supplier_due_diligence": any(term in lower for term in ["due diligence", "supplier survey", "supplier engagement", "rmi", "oecd"]),
        "smelter_refiner_disclosure": any(term in lower for term in ["smelter", "refiner", "cmrt"]),
    }


def get_sec_governance_social_signals(company_name: str, industry: str | None = None) -> dict[str, Any]:
    """Pull governance/social disclosures from SEC DEF 14A and Form SD."""
    result: dict[str, Any] = {
        "found": False,
        "governance_score": None,
        "social_score": None,
        "evidence": [],
        "metrics": {},
        "filings": [],
        "error": None,
    }

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    encoded_company = company_name.strip()
    is_tech = "tech" in str(industry or "").lower() or any(
        token in company_name.lower() for token in ["apple", "microsoft", "google", "alphabet", "meta", "intel", "nvidia", "adobe", "cisco", "oracle"]
    )

    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=headers) as client:
            filing_types = ["DEF 14A"] + (["SD"] if is_tech else [])
            for filing_type in filing_types:
                submission_filing = _get_sec_submission_filing(client, encoded_company, filing_type)
                filing_date = None
                document_url = None

                if submission_filing:
                    filing_date = submission_filing.get("filing_date")
                    document_url = submission_filing.get("filing_url")

                if not document_url:
                    search_resp = client.get(
                        "https://www.sec.gov/cgi-bin/browse-edgar",
                        params={
                            "action": "getcompany",
                            "company": encoded_company,
                            "type": filing_type,
                            "owner": "exclude",
                            "count": 5,
                        },
                    )
                    search_resp.raise_for_status()
                    soup = BeautifulSoup(search_resp.text, "html.parser")
                    table = soup.find("table", class_="tableFile2")
                    if not table:
                        continue

                    first_row = table.find_all("tr")[1] if len(table.find_all("tr")) > 1 else None
                    if first_row is None:
                        continue

                    cols = first_row.find_all("td")
                    if len(cols) < 4:
                        continue

                    filing_date = cols[3].get_text(" ", strip=True)
                    filing_link = cols[1].find("a")
                    if not filing_link:
                        continue

                    filing_index_url = filing_link.get("href", "")
                    if filing_index_url.startswith("/"):
                        filing_index_url = f"https://www.sec.gov{filing_index_url}"

                    document_url = _find_filing_document_url(client, filing_index_url, headers) or filing_index_url

                if not document_url:
                    continue

                doc_resp = client.get(document_url)
                doc_resp.raise_for_status()
                filing_text = BeautifulSoup(doc_resp.text, "html.parser").get_text(" ", strip=True)

                filing_payload = {
                    "filing_type": filing_type,
                    "filing_date": filing_date,
                    "filing_url": document_url,
                }
                result["filings"].append(filing_payload)

                if filing_type == "DEF 14A":
                    metrics = _extract_def14a_metrics(filing_text)
                    result["metrics"].update(metrics)
                    governance_score = _score_governance_from_sec_metrics(metrics)
                    if governance_score is not None:
                        result["governance_score"] = governance_score

                    if metrics.get("executive_comp_esg_links") is not None:
                        snippet = "Proxy statement reviewed for executive compensation ESG links."
                        if metrics.get("executive_pay_ratio") is not None:
                            snippet += f" CEO pay ratio disclosed at approximately {metrics['executive_pay_ratio']}:1."
                        if metrics.get("board_diversity_pct") is not None:
                            snippet += f" Board diversity disclosed at {metrics['board_diversity_pct']}%."
                        result["evidence"].append({
                            "title": f"{company_name} DEF 14A governance disclosure",
                            "snippet": snippet,
                            "url": document_url,
                            "source": "SEC EDGAR",
                            "source_name": "SEC DEF 14A",
                            "source_type": "Government/Regulatory",
                            "date": filing_date or datetime.utcnow().date().isoformat(),
                        })

                if filing_type == "SD":
                    metrics = _extract_form_sd_metrics(filing_text)
                    result["metrics"].update(metrics)
                    social_score = _score_social_from_form_sd(metrics)
                    if social_score is not None:
                        result["social_score"] = social_score
                        result["evidence"].append({
                            "title": f"{company_name} Form SD supply-chain human rights disclosure",
                            "snippet": "Form SD indicates conflict minerals due diligence / responsible sourcing controls relevant to supply-chain human rights.",
                            "url": document_url,
                            "source": "SEC EDGAR",
                            "source_name": "SEC Form SD",
                            "source_type": "Government/Regulatory",
                            "date": filing_date or datetime.utcnow().date().isoformat(),
                        })

        result["found"] = bool(result["evidence"] or result["governance_score"] is not None or result["social_score"] is not None)
    except Exception as exc:
        result["error"] = f"SEC filing lookup failed: {exc}"

    return result


# ===================================================================
# WRI Aqueduct 4.0
# ===================================================================

def get_wri_water_risk(
    lat: float,
    lon: float,
    industry: str | None = None,
    api_key: str | None = None,
    bearer_token: str | None = None,
) -> dict[str, Any]:
    """Fetch water risk data from WRI Aqueduct via the Resource Watch API.

    Uses a two-step workflow:
        1. Register a GeoJSON geometry as a geostore on Resource Watch.
        2. Query the Aqueduct analysis endpoint using the geostore ID.

    Categorizes the 13 Aqueduct indicators into physical risk (bws, bwd,
    iav, sev, gtd, rfr, cfr, drr), regulatory risk (udw, usa, cep),
    and reputational risk (rri, eco).

    Parameters
    ----------
    lat : float
        Latitude of the location (e.g. company HQ).
    lon : float
        Longitude of the location.
    industry : str | None
        Optional industry filter for sector-weighted scoring.

    Returns
    -------
    dict
        Keys: ``found``, ``location``, ``overall_risk``,
        ``physical_risk``, ``regulatory_risk``, ``reputational_risk``,
        ``raw``, ``error``.
    """
    result: dict[str, Any] = {
        "found": False,
        "location": {"lat": lat, "lon": lon},
        "overall_risk": None,
        "physical_risk": {},
        "regulatory_risk": {},
        "reputational_risk": {},
        "raw": None,
        "error": None,
    }

    api_key = (
        api_key
        or os.environ.get("RESOURCE_WATCH_API_KEY")
        or os.environ.get("WRI_AQUEDUCT_API_KEY")
        or ""
    ).strip()
    bearer_token = (
        bearer_token
        or os.environ.get("RESOURCE_WATCH_TOKEN")
        or os.environ.get("WRI_AQUEDUCT_TOKEN")
        or ""
    ).strip()

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    # Create a small polygon buffer around the point (~1km) since
    # the Aqueduct raster may not intersect a bare Point geometry.
    BUFFER = 0.01  # ~1km in degrees
    geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [lon - BUFFER, lat - BUFFER],
                    [lon + BUFFER, lat - BUFFER],
                    [lon + BUFFER, lat + BUFFER],
                    [lon - BUFFER, lat + BUFFER],
                    [lon - BUFFER, lat - BUFFER],
                ]],
            },
            "properties": {},
        }],
    }

    if not api_key:
        result["error"] = (
            "Resource Watch API key not set "
            "(RESOURCE_WATCH_API_KEY or WRI_AQUEDUCT_API_KEY)"
        )
        logger.warning("WRI: API key not available - skipping Aqueduct lookup")
        return result

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            # --- Step 1: Create geostore ---
            gs_resp = client.post(
                "https://api.resourcewatch.org/v1/geostore",
                json={"geojson": geojson},
                headers=headers,
            )
            gs_resp.raise_for_status()
            geostore_id = gs_resp.json().get("data", {}).get("id")

            if not geostore_id:
                result["error"] = "Failed to create geostore (no ID returned)"
                logger.warning("WRI: geostore creation returned no ID")
                return result

            logger.info("WRI: geostore created — id=%s", geostore_id)

            # --- Step 2: Query Aqueduct analysis ---
            params: dict[str, str] = {
                "geostore": geostore_id,
                "wscheme": "aqueduct",
                "analysis_type": "annual",
                "year": "baseline",
            }
            if industry:
                params["industry"] = industry

            analysis_resp = client.get(
                "https://api.resourcewatch.org/v1/aqueduct/analysis",
                headers=headers,
                params=params,
            )
            analysis_resp.raise_for_status()
            data = analysis_resp.json()
            result["raw"] = data

            # Parse indicator values from response
            indicators: dict[str, Any] = {}

            # Handle various response shapes
            risk_data = (
                data.get("data")
                or data.get("rows")
                or data.get("indicators")
                or data
            )
            if isinstance(risk_data, list) and risk_data:
                risk_data = risk_data[0]
            if isinstance(risk_data, dict):
                attrs = risk_data.get("attributes") or risk_data
                for key, val in attrs.items():
                    indicators[key.lower()] = val

            # Categorize indicators into risk buckets
            for ind_key in _WRI_PHYSICAL:
                for full_key, val in indicators.items():
                    if ind_key in full_key and val is not None:
                        result["physical_risk"][ind_key] = val
                        break

            for ind_key in _WRI_REGULATORY:
                for full_key, val in indicators.items():
                    if ind_key in full_key and val is not None:
                        result["regulatory_risk"][ind_key] = val
                        break

            for ind_key in _WRI_REPUTATIONAL:
                for full_key, val in indicators.items():
                    if ind_key in full_key and val is not None:
                        result["reputational_risk"][ind_key] = val
                        break

            # Compute overall risk (average of available numeric values)
            all_numeric = [
                v for bucket in (
                    result["physical_risk"],
                    result["regulatory_risk"],
                    result["reputational_risk"],
                )
                for v in bucket.values()
                if isinstance(v, (int, float))
            ]
            if all_numeric:
                result["overall_risk"] = round(
                    sum(all_numeric) / len(all_numeric), 3,
                )

            result["found"] = bool(
                result["physical_risk"]
                or result["regulatory_risk"]
                or result["reputational_risk"]
            )
            logger.info(
                "WRI: water risk for (%.4f, %.4f) — overall=%s, "
                "physical=%d, regulatory=%d, reputational=%d indicators",
                lat, lon, result["overall_risk"],
                len(result["physical_risk"]),
                len(result["regulatory_risk"]),
                len(result["reputational_risk"]),
            )

    except httpx.TimeoutException:
        result["error"] = f"WRI API timed out for ({lat}, {lon})"
        logger.warning("WRI: request timed out for (%.4f, %.4f)", lat, lon)
    except httpx.HTTPStatusError as exc:
        result["error"] = f"WRI API HTTP {exc.response.status_code}"
        logger.warning(
            "WRI: HTTP %d for (%.4f, %.4f)", exc.response.status_code, lat, lon,
        )
    except httpx.HTTPError as exc:
        result["error"] = f"WRI API error: {exc}"
        logger.warning("WRI: request failed for (%.4f, %.4f) — %s", lat, lon, exc)
    except (ValueError, KeyError, TypeError) as exc:
        result["error"] = f"WRI parse error: {exc}"
        logger.warning(
            "WRI: failed to parse response for (%.4f, %.4f) — %s", lat, lon, exc,
        )

    return result


# ===================================================================
# Top-level pillar filler
# ===================================================================

def fill_missing_pillars(
    company_name: str,
    lat: float | None = None,
    lon: float | None = None,
    existing_scores: dict[str, Any] | None = None,
    wba_api_key: str | None = None,
    industry: str | None = None,
) -> dict[str, Any]:
    """Fill missing Social, Governance, and Water-Risk pillar scores.

    Called when either social or governance pillar is ``None`` in the
    existing scores.  Queries WBA for pillar scores and WRI Aqueduct
    for water risk data.

    Parameters
    ----------
    company_name : str
        Company name for WBA lookup.
    lat, lon : float | None
        HQ coordinates for WRI Aqueduct lookup.
    existing_scores : dict | None
        Current pillar scores dict.  Missing/``None`` values trigger
        API lookups.
    wba_api_key : str | None
        Optional WBA API key override.

    Returns
    -------
    dict
        Updated scores dict with ``_sources`` annotation showing
        which API filled each value.
    """
    scores = dict(existing_scores or {})
    sources: dict[str, str] = {}

    social_missing = scores.get("social") is None
    governance_missing = scores.get("governance") is None
    water_missing = scores.get("water_risk") is None

    # --- WBA: fill social & governance ---
    if social_missing or governance_missing:
        logger.info(
            "Filling missing pillars via WBA for '%s' "
            "(social=%s, governance=%s)",
            company_name,
            "missing" if social_missing else "present",
            "missing" if governance_missing else "present",
        )
        wba = get_wba_company_assessment_with_aliases(company_name, api_key=wba_api_key)

        if wba["found"]:
            if social_missing and "social" in wba["scores"]:
                scores["social"] = wba["scores"]["social"]
                sources["social"] = "WBA"

            if governance_missing and "governance" in wba["scores"]:
                scores["governance"] = wba["scores"]["governance"]
                sources["governance"] = "WBA"

            # Bonus: fill environment if also missing
            if scores.get("environment") is None and "environment" in wba["scores"]:
                scores["environment"] = wba["scores"]["environment"]
                sources["environment"] = "WBA"

            scores["_wba_indicators"] = wba["indicators"]
            scores["_wba_company_name"] = wba["company_name"]
            scores["_wba_data_year"] = wba.get("data_year")
            if isinstance(wba.get("hq_coordinates"), dict):
                scores["_wba_hq_coordinates"] = wba["hq_coordinates"]
        else:
            logger.warning(
                "WBA lookup failed for '%s': %s",
                company_name, wba.get("error"),
            )

    # --- SEC: fill governance/social from DEF 14A / Form SD when WBA is absent or incomplete ---
    if social_missing or governance_missing:
        sec = get_sec_governance_social_signals(company_name, industry=industry)
        if sec.get("found"):
            if governance_missing and sec.get("governance_score") is not None:
                scores["governance"] = sec["governance_score"]
                sources["governance"] = "SEC_DEF_14A"
            if social_missing and sec.get("social_score") is not None:
                scores["social"] = sec["social_score"]
                sources["social"] = "SEC_Form_SD"

            scores["_sec_metrics"] = sec.get("metrics", {})
            scores["_sec_filings"] = sec.get("filings", [])
            scores["_supplemental_evidence"] = sec.get("evidence", [])
        elif sec.get("error"):
            logger.warning("SEC governance/social lookup failed for '%s': %s", company_name, sec.get("error"))

    # --- WRI: fill water risk ---
    # Auto-derive HQ coordinates from WBA company data when caller doesn't provide them.
    if (lat is None or lon is None) and isinstance(scores.get("_wba_hq_coordinates"), dict):
        candidate = scores.get("_wba_hq_coordinates", {})
        lat = candidate.get("lat", lat)
        lon = candidate.get("lon", lon)

    if water_missing and lat is not None and lon is not None:
        logger.info(
            "Filling water_risk via WRI Aqueduct for (%.4f, %.4f)",
            lat, lon,
        )
        wri = get_wri_water_risk(lat, lon)

        if wri["found"]:
            scores["water_risk"] = wri["overall_risk"]
            scores["water_risk_physical"] = wri["physical_risk"]
            scores["water_risk_regulatory"] = wri["regulatory_risk"]
            scores["water_risk_reputational"] = wri["reputational_risk"]
            sources["water_risk"] = "WRI_Aqueduct_4.0"
        else:
            logger.warning(
                "WRI Aqueduct lookup failed for (%.4f, %.4f): %s",
                lat, lon, wri.get("error"),
            )

    scores["_sources"] = sources
    logger.info("fill_missing_pillars result sources: %s", sources)
    return scores
