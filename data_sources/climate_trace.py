"""Climate TRACE — independent satellite-derived emissions ground truth.

The Climate TRACE coalition publishes facility-level emissions for ~745M assets,
updated monthly, free + no auth. We use it to cross-check disclosed Scope 1.

Two access paths are exposed:

  1. Asset-level lookup — when a company has a known facility list (e.g.
     "Lanjigarh Alumina Refinery" → Vedanta), we sum that facility's
     EmissionsDetails. The CURATED_OWNER_MAP keeps the demo set in one place;
     extending it is a 1-line change per company.

  2. Country-sector aggregate — when we don't have a facility list, we pull the
     entire country-level sector total. A company's disclosed Scope 1 that
     exceeds the full national sector ceiling is prima facie inflation.

All calls fail-soft: on error/network problem the helper returns None, never
raises. Latency is a few seconds per call uncached — well within the pipeline's
existing budget.

API base: https://api.climatetrace.org/v6/ (beta, "keep volume low" — we make
at most 1-3 calls per company per run, far below their limits).

Licensing: CC 4.0. Attribution string is exposed via attribution_string().
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.climatetrace.org/v6"
_DEFAULT_TIMEOUT = 15.0
_USER_AGENT = "esglens/1.0 (educational; +https://esglens.com)"


# ── Curated owner → asset map (extend per demo run) ───────────────────────────
# Each entry maps a normalised company key → list of (asset_name_substring,
# country_iso3). Match is case-insensitive substring against Asset.Name. The
# substring approach is robust to Climate TRACE renaming conventions
# (e.g. "Jharsuguda aluminium plant" vs "Jharsuguda Smelter").
CURATED_OWNER_MAP: Dict[str, List[Dict[str, str]]] = {
    "vedanta": [
        # Specific Vedanta-owned facilities (Climate TRACE asset names).
        # "Jharsuguda" alone is too broad — it's a town hosting multiple
        # operators (JSW BPSL, Action Ispat, etc.).
        {"name_contains": "Lanjigarh", "country": "IND"},
        {"name_contains": "Jharsuguda aluminium", "country": "IND"},
        {"name_contains": "Jharsuguda CPP", "country": "IND"},
        {"name_contains": "Jharsuguda Sterlite", "country": "IND"},
        {"name_contains": "BALCO Korba", "country": "IND"},
        {"name_contains": "Hindustan Zinc", "country": "IND"},
        {"name_contains": "Sterlite Industries", "country": "IND"},
    ],
    "reliance": [
        {"name_contains": "Jamnagar", "country": "IND"},
    ],
    "tata steel": [
        {"name_contains": "Tata Steel", "country": "IND"},
    ],
    "jsw steel": [
        {"name_contains": "JSW Steel", "country": "IND"},
    ],
    "coal india": [
        {"name_contains": "Coal Mine", "country": "IND"},
    ],
    "ntpc": [
        {"name_contains": "NTPC", "country": "IND"},
    ],
    "bp": [
        # BP's bulk Scope 1 footprint is in production/refining assets.
        {"name_contains": "BP ", "country": "GBR"},
    ],
    "shell": [
        {"name_contains": "Shell ", "country": "NLD"},
        {"name_contains": "Shell ", "country": "GBR"},
    ],
    "arcelormittal": [
        {"name_contains": "ArcelorMittal", "country": "IND"},
        {"name_contains": "ArcelorMittal", "country": "FRA"},
    ],
}


# ── Industry → Climate TRACE sectors map ──────────────────────────────────────
# Used by the country-sector aggregate fallback. Sectors come from /v6/sectors.
INDUSTRY_SECTOR_MAP: Dict[str, List[str]] = {
    "mining": ["coal-mining", "iron-and-steel", "aluminum"],
    "mining and metals": ["coal-mining", "iron-and-steel", "aluminum"],
    "metals": ["iron-and-steel", "aluminum"],
    "aluminum": ["aluminum"],
    "steel": ["iron-and-steel"],
    "oil and gas": ["oil-and-gas-production", "oil-and-gas-refining"],
    "oil_and_gas": ["oil-and-gas-production", "oil-and-gas-refining"],
    "petrochemicals": ["petrochemical-steam-cracking", "oil-and-gas-refining"],
    "cement": ["cement"],
    "chemicals": ["chemicals"],
    "power": ["electricity-generation"],
    "electricity": ["electricity-generation"],
    "utilities": ["electricity-generation"],
    "automotive": ["road-transportation"],
    "aviation": ["domestic-aviation", "international-aviation"],
    "shipping": ["international-shipping"],
}


# ── Country → ISO3 normalisation ──────────────────────────────────────────────
COUNTRY_ISO3: Dict[str, str] = {
    "india": "IND",
    "united states": "USA",
    "us": "USA",
    "usa": "USA",
    "united kingdom": "GBR",
    "uk": "GBR",
    "britain": "GBR",
    "germany": "DEU",
    "france": "FRA",
    "china": "CHN",
    "japan": "JPN",
    "netherlands": "NLD",
    "korea": "KOR",
    "south korea": "KOR",
    "russia": "RUS",
    "brazil": "BRA",
    "canada": "CAN",
    "australia": "AUS",
    "indonesia": "IDN",
    "saudi arabia": "SAU",
    "south africa": "ZAF",
    "mexico": "MEX",
}


@dataclass
class AssetEmissions:
    asset_id: int
    name: str
    country: str
    sector: str
    co2e_100yr_tco2e: Optional[float] = None
    year: Optional[int] = None


@dataclass
class CountryEmissions:
    country: str
    year: int
    co2e_100yr_tco2e: Optional[float]
    rank: Optional[int]
    raw: Dict[str, Any] = field(default_factory=dict)


# ── Internal HTTP ────────────────────────────────────────────────────────────
def _get(path: str, params: Optional[Dict[str, Any]] = None,
         timeout: float = _DEFAULT_TIMEOUT) -> Optional[Any]:
    """Single GET with no auth. Returns parsed JSON or None on error."""
    qs = ""
    if params:
        qs = "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )
    url = f"{_BASE_URL}/{path.lstrip('/')}{qs}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — fail-soft per module contract
        logger.warning("Climate TRACE GET failed: %s | %s", url, exc)
        return None


# ── Public surface ────────────────────────────────────────────────────────────
def attribution_string() -> str:
    """One-line attribution to include in report footers (CC 4.0 compliance)."""
    return ("Emissions verification: Climate TRACE coalition "
            "(https://climatetrace.org, CC 4.0).")


def normalise_country(name: Optional[str]) -> Optional[str]:
    """Map a free-form country/jurisdiction string to ISO-3."""
    if not name:
        return None
    s = str(name).strip().lower()
    return COUNTRY_ISO3.get(s)


def resolve_company_assets(
    company: str,
    country_iso3: Optional[str] = None,
    pull_limit: int = 1000,
) -> List[AssetEmissions]:
    """Look up Climate TRACE assets owned by `company` via the curated map.

    Returns an empty list when the company is not in CURATED_OWNER_MAP — the
    caller should fall back to the country-sector aggregate.
    """
    key = (company or "").strip().lower()
    # exact, then substring fall-back
    rules = CURATED_OWNER_MAP.get(key)
    if not rules:
        for k, v in CURATED_OWNER_MAP.items():
            if k in key or key in k:
                rules = v
                break
    if not rules:
        return []

    out: List[AssetEmissions] = []
    rule_countries = {r["country"] for r in rules}
    target_countries = (
        {country_iso3} if country_iso3 else rule_countries
    )

    for ctry in target_countries:
        d = _get("assets", {"countries": ctry, "limit": pull_limit, "year": 2024})
        if not isinstance(d, dict):
            continue
        assets = d.get("assets") or []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = (asset.get("Name") or "").strip()
            name_lc = name.lower()
            for r in rules:
                if r["country"] != ctry:
                    continue
                substr = (r.get("name_contains") or "").lower()
                if not substr or substr not in name_lc:
                    continue
                # Match!
                em_summary = asset.get("EmissionsSummary") or []
                co2e = None
                if isinstance(em_summary, list) and em_summary:
                    co2e = em_summary[0].get("EmissionsQuantity")
                out.append(AssetEmissions(
                    asset_id=int(asset.get("Id") or 0),
                    name=name,
                    country=asset.get("Country") or ctry,
                    sector=asset.get("Sector") or "",
                    co2e_100yr_tco2e=(float(co2e) if isinstance(co2e, (int, float)) else None),
                    year=2024,
                ))
                break
    return out


def country_sector_emissions(
    country_iso3: str,
    sectors: List[str],
    year: int = 2024,
    pull_limit: int = 1000,
) -> Dict[str, float]:
    """Aggregate total tCO2e per sector for a country by summing matching assets.

    Returns {sector: total_tco2e}. Sectors not found return 0.0.
    """
    out: Dict[str, float] = {s: 0.0 for s in sectors}
    d = _get("assets", {"countries": country_iso3, "limit": pull_limit, "year": year})
    if not isinstance(d, dict):
        return out
    for asset in d.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        sec = asset.get("Sector")
        if sec not in out:
            continue
        em_summary = asset.get("EmissionsSummary") or []
        if isinstance(em_summary, list) and em_summary:
            q = em_summary[0].get("EmissionsQuantity")
            if isinstance(q, (int, float)):
                out[sec] += float(q)
    return out


def country_total_emissions(
    country_iso3: str, year: int = 2024,
) -> Optional[CountryEmissions]:
    """Get the country-wide total CO2e (all sectors) for a year."""
    d = _get("country/emissions", {"countries": country_iso3, "years": year})
    if not isinstance(d, list) or not d:
        return None
    row = d[0]
    if not isinstance(row, dict):
        return None
    em = (row.get("emissions") or {}) if isinstance(row.get("emissions"), dict) else {}
    co2e = em.get("co2e_100yr")
    return CountryEmissions(
        country=row.get("country") or country_iso3,
        year=year,
        co2e_100yr_tco2e=(float(co2e) if isinstance(co2e, (int, float)) else None),
        rank=row.get("rank"),
        raw=row,
    )


# ── Convenience: full company snapshot ────────────────────────────────────────
def get_company_emissions_snapshot(
    company: str,
    industry: Optional[str] = None,
    country: Optional[str] = None,
    year: int = 2024,
) -> Dict[str, Any]:
    """Build a single decision-grade dict the verifier agent consumes.

    Output shape:
      {
        company: ...
        country_iso3: 'IND' | None
        sectors_targeted: [...]
        asset_level: { matched_assets: [...], total_tco2e: float | None }
        sector_aggregate: { sector: total_tco2e }
        country_total: { co2e_100yr_tco2e, rank, year } | None
        attribution: str
        source_url: str
        fetched_at_utc: ISO timestamp
      }
    """
    from datetime import datetime, timezone

    country_iso3 = normalise_country(country)
    industry_key = (industry or "").strip().lower()
    sectors = INDUSTRY_SECTOR_MAP.get(industry_key, [])

    assets = resolve_company_assets(company, country_iso3=country_iso3)
    asset_total = (
        sum((a.co2e_100yr_tco2e or 0.0) for a in assets) if assets else None
    )

    sector_aggregate: Dict[str, float] = {}
    if country_iso3 and sectors:
        sector_aggregate = country_sector_emissions(country_iso3, sectors, year=year)

    country_total = (
        country_total_emissions(country_iso3, year=year)
        if country_iso3 else None
    )

    return {
        "company": company,
        "country_iso3": country_iso3,
        "sectors_targeted": sectors,
        "asset_level": {
            "matched_assets": [
                {
                    "id": a.asset_id, "name": a.name,
                    "country": a.country, "sector": a.sector,
                    "tco2e": a.co2e_100yr_tco2e, "year": a.year,
                }
                for a in assets
            ],
            "total_tco2e": asset_total,
        },
        "sector_aggregate": sector_aggregate,
        "country_total": {
            "co2e_100yr_tco2e": country_total.co2e_100yr_tco2e,
            "rank": country_total.rank,
            "year": country_total.year,
        } if country_total else None,
        "attribution": attribution_string(),
        "source_url": "https://climatetrace.org",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
