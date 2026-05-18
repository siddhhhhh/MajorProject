"""Entity Resolver — canonical company-name → LEI mapping.

Why this exists:
  Today "JPM", "JPMorgan Chase & Co.", "JPMORGAN CHASE BANK NA" are three
  different keys across the codebase. Without a stable canonical ID:
    - We can't dedupe subsidiaries across runs
    - We can't join Climate TRACE assets to disclosure data
    - We can't track promises longitudinally
    - Cross-source joins (CourtListener case search, EPA ECHO, etc.) lose precision

LEI (Legal Entity Identifier, ISO 17442) is the chosen canonical ID — free,
globally unique, government-backed, covers ~2M legal entities via GLEIF.

This module ships as a "simpler-first" v1:
  - Curated alias map for the ~50 companies we expect in our demo + audit set
  - rapidfuzz string-similarity fallback (>= 90 score against curated keys)
  - Manual overrides at data/entity_alias_overrides.json (caller-extensible)

v2 will swap the in-memory map for a slimmed GLEIF parquet (~50k LEIs covering
all corporate parents). The public API stays the same so nothing downstream has
to change.

Public API:
    resolve(name) -> EntityRecord | None
    record_to_dict(record) -> dict          # JSON-safe for state passing
    register_override(name, lei, country)   # runtime extension

EntityRecord is intentionally minimal — only fields downstream consumers need.
The "more metadata" path is to fetch the LEI from GLEIF directly when the
caller wants the full record.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Threshold for rapidfuzz fallback. Picked empirically against the curated
# alias set — 90 catches "JP Morgan" -> "JPMorgan Chase & Co." but rejects
# "JP Mortgage" -> "JPMorgan" which is a different entity.
_FUZZY_THRESHOLD = 90

_OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "data" / "entity_alias_overrides.json"


@dataclass(frozen=True)
class EntityRecord:
    """Canonical record for a resolved entity.

    `lei` may be None when the curated map provides an alias group without
    a confirmed LEI — callers should treat None LEI as "use canonical_name
    as the join key, accept the precision loss".
    """
    canonical_name: str
    lei: Optional[str]
    country_iso3: Optional[str]
    aliases: tuple[str, ...]


# ── Curated alias map ─────────────────────────────────────────────────────────
# Keys here are the *normalised* form (lowercase, stripped, punctuation removed).
# Values carry the canonical name + LEI + country. LEIs are pulled from the
# GLEIF public registry (https://search.gleif.org) — verify before adding new
# entries; a bad LEI silently mis-attributes Climate TRACE assets etc.
#
# Coverage rationale: every company in our 5-company audit set, every demo
# lead candidate, and the top portfolio holdings expected in PCAF flows.

_CURATED: Dict[str, EntityRecord] = {
    # Financial services (US / global) — primary JPMC-forum demo set.
    "jpmorgan chase": EntityRecord(
        canonical_name="JPMorgan Chase & Co.",
        lei="8I5DZWZKVSZI1NUHU748",
        country_iso3="USA",
        aliases=("JPMorgan Chase", "JPM", "JPMorgan Chase & Co",
                 "JPMORGAN CHASE BANK NA", "JP Morgan", "JPMC"),
    ),
    "goldman sachs": EntityRecord(
        canonical_name="The Goldman Sachs Group, Inc.",
        lei="784F5XWPLTWKTBV3E584",
        country_iso3="USA",
        aliases=("Goldman Sachs Group", "Goldman Sachs", "GS"),
    ),
    "bank of america": EntityRecord(
        canonical_name="Bank of America Corporation",
        lei="B4TYDEB6GKMZO031MB27",
        country_iso3="USA",
        aliases=("Bank of America", "BofA", "BAC"),
    ),
    "morgan stanley": EntityRecord(
        canonical_name="Morgan Stanley",
        lei="IGJSJL3JD5P30I6NJZ34",
        country_iso3="USA",
        aliases=("Morgan Stanley & Co", "MS"),
    ),
    "wells fargo": EntityRecord(
        canonical_name="Wells Fargo & Company",
        lei="PBLD0EJDB5FWOLXP3B76",
        country_iso3="USA",
        aliases=("Wells Fargo Bank", "WFC"),
    ),
    "hdfc bank": EntityRecord(
        canonical_name="HDFC Bank Limited",
        lei="335800XNS3IK9SDJ4R36",
        country_iso3="IND",
        aliases=("HDFC Bank Ltd", "HDFC"),
    ),

    # Mining / Metals — Vedanta inflation-flag demo
    "vedanta": EntityRecord(
        canonical_name="Vedanta Limited",
        lei="335800Q1AJZ7Y6V25S25",
        country_iso3="IND",
        aliases=("Vedanta Ltd", "Vedanta Limited", "Vedanta Resources"),
    ),
    "tata steel": EntityRecord(
        canonical_name="Tata Steel Limited",
        lei="3358003RHJBL6V8O7Y17",
        country_iso3="IND",
        aliases=("Tata Steel", "Tata Steel Ltd"),
    ),
    "jsw steel": EntityRecord(
        canonical_name="JSW Steel Limited",
        lei="335800GTUUFMNDXMBR42",
        country_iso3="IND",
        aliases=("JSW Steel", "JSW Steel Ltd"),
    ),
    "arcelormittal": EntityRecord(
        canonical_name="ArcelorMittal SA",
        lei="N7GHA2Y4QJ6Y7Y0PA240",
        country_iso3="LUX",
        aliases=("Arcelor Mittal", "ArcelorMittal Group", "ArcelorMittal Nippon Steel"),
    ),
    "hindustan zinc": EntityRecord(
        canonical_name="Hindustan Zinc Limited",
        lei="335800B0K5FOIDA1KH26",
        country_iso3="IND",
        aliases=("Hindustan Zinc", "HZL"),
    ),

    # Oil & Gas — refining/petrochem demo + PCAF portfolio targets
    "reliance industries": EntityRecord(
        canonical_name="Reliance Industries Limited",
        lei="335800F2WCKW00BAUE36",
        country_iso3="IND",
        aliases=("Reliance Industries", "Reliance", "Reliance Industries Ltd", "RIL"),
    ),
    "exxonmobil": EntityRecord(
        canonical_name="Exxon Mobil Corporation",
        lei="J3WHBG0MTS7O8ZVMDC91",
        country_iso3="USA",
        aliases=("ExxonMobil", "Exxon Mobil", "Exxon", "XOM"),
    ),
    "chevron": EntityRecord(
        canonical_name="Chevron Corporation",
        lei="MVR3RKAHWVQOC67V1H35",
        country_iso3="USA",
        aliases=("Chevron Corp", "CVX"),
    ),
    "bp": EntityRecord(
        canonical_name="BP p.l.c.",
        lei="213800LBQA1Y9L22JB70",
        country_iso3="GBR",
        aliases=("BP plc", "BP PLC", "British Petroleum"),
    ),
    "shell": EntityRecord(
        canonical_name="Shell plc",
        lei="21380068P1DRHMJ8KU70",
        country_iso3="GBR",
        aliases=("Royal Dutch Shell", "Shell plc", "Shell Oil"),
    ),
    "totalenergies": EntityRecord(
        canonical_name="TotalEnergies SE",
        lei="529900S21EQ1BO4ESM68",
        country_iso3="FRA",
        aliases=("Total", "Total SE", "TotalEnergies", "TTE"),
    ),
    "saudi aramco": EntityRecord(
        canonical_name="Saudi Arabian Oil Company",
        lei="5586007WI53R3CVOFY28",
        country_iso3="SAU",
        aliases=("Aramco", "Saudi Aramco"),
    ),

    # Power / Utilities — Climate TRACE coverage strong
    "ntpc": EntityRecord(
        canonical_name="NTPC Limited",
        lei="335800BBONTQGJUTPN59",
        country_iso3="IND",
        aliases=("NTPC", "NTPC Ltd", "National Thermal Power Corporation"),
    ),
    "coal india": EntityRecord(
        canonical_name="Coal India Limited",
        lei="335800GBJ3BBL8U02B23",
        country_iso3="IND",
        aliases=("Coal India", "Coal India Ltd", "CIL"),
    ),

    # Tech — Scope 2 dominant, used to demonstrate "not financial but coverage limited"
    "microsoft": EntityRecord(
        canonical_name="Microsoft Corporation",
        lei="INR2EJN1ERAN0W5ZP974",
        country_iso3="USA",
        aliases=("Microsoft", "MSFT", "Microsoft Corp"),
    ),
    "apple": EntityRecord(
        canonical_name="Apple Inc.",
        lei="HWUPKR0MPOU8FGXBT394",
        country_iso3="USA",
        aliases=("Apple", "Apple Inc", "AAPL"),
    ),
    "alphabet": EntityRecord(
        canonical_name="Alphabet Inc.",
        lei="5493006MHB84DD0ZWV18",
        country_iso3="USA",
        aliases=("Alphabet", "Google", "Google LLC", "GOOG", "GOOGL"),
    ),
    "meta platforms": EntityRecord(
        canonical_name="Meta Platforms, Inc.",
        lei="BQ4BKCS1HXDV9HN80Z93",
        country_iso3="USA",
        aliases=("Meta", "Facebook", "Meta Platforms", "META", "FB"),
    ),
    "amazon": EntityRecord(
        canonical_name="Amazon.com, Inc.",
        lei="ZXTILKJKG63JELOEG630",
        country_iso3="USA",
        aliases=("Amazon", "Amazon.com", "AMZN"),
    ),
    "tesla": EntityRecord(
        canonical_name="Tesla, Inc.",
        lei="54930043XZGB27CTOV49",
        country_iso3="USA",
        aliases=("Tesla", "Tesla Motors", "TSLA"),
    ),
    "infosys": EntityRecord(
        canonical_name="Infosys Limited",
        lei="213800WD2PE2VBPWA471",
        country_iso3="IND",
        aliases=("Infosys", "Infosys Ltd", "INFY"),
    ),
    "wipro": EntityRecord(
        canonical_name="Wipro Limited",
        lei="335800XX3ZQHF66BV390",
        country_iso3="IND",
        aliases=("Wipro", "Wipro Ltd"),
    ),

    # Automotive — Volkswagen Dieselgate is a known-promise-missed demo
    "volkswagen": EntityRecord(
        canonical_name="Volkswagen AG",
        lei="529900NNUPAGGOMPXZ31",
        country_iso3="DEU",
        aliases=("VW", "Volkswagen Group", "Volkswagen AG"),
    ),
    "toyota": EntityRecord(
        canonical_name="Toyota Motor Corporation",
        lei="5493006W3QUS5LMH6R37",
        country_iso3="JPN",
        aliases=("Toyota", "Toyota Motor", "TM"),
    ),
    "ford motor": EntityRecord(
        canonical_name="Ford Motor Company",
        lei="20S5DUSU8J3SDF1WZH33",
        country_iso3="USA",
        aliases=("Ford", "Ford Motor", "F"),
    ),
    "general motors": EntityRecord(
        canonical_name="General Motors Company",
        lei="54930070NSV60J38I987",
        country_iso3="USA",
        aliases=("GM", "General Motors", "Chevrolet parent"),
    ),

    # Consumer/Pharma — for breadth across pillars
    "unilever": EntityRecord(
        canonical_name="Unilever PLC",
        lei="549300MKFYEKVRWML317",
        country_iso3="GBR",
        aliases=("Unilever", "Unilever Plc", "UL"),
    ),
    "nestle": EntityRecord(
        canonical_name="Nestlé S.A.",
        lei="529900SGCDPHLAJYQ307",
        country_iso3="CHE",
        aliases=("Nestle", "Nestlé"),
    ),
    "pfizer": EntityRecord(
        canonical_name="Pfizer Inc.",
        lei="765400R22UTQ1WHW5036",
        country_iso3="USA",
        aliases=("Pfizer", "PFE"),
    ),

    # Adani (India, controversial — used for cross-pillar contradiction demo)
    "adani": EntityRecord(
        canonical_name="Adani Enterprises Limited",
        lei="335800F0YK0Y3HBKHV33",
        country_iso3="IND",
        aliases=("Adani", "Adani Group", "Adani Enterprises"),
    ),

    # Petrobras / Sinopec — non-US/India oil for coverage
    "petrobras": EntityRecord(
        canonical_name="Petróleo Brasileiro S.A. - Petrobras",
        lei="529900TMOZHTBFLBQ112",
        country_iso3="BRA",
        aliases=("Petrobras", "Petroleo Brasileiro"),
    ),
    "sinopec": EntityRecord(
        canonical_name="China Petroleum & Chemical Corporation",
        lei="3003001BS3YSMTNTYP55",
        country_iso3="CHN",
        aliases=("Sinopec", "China Petroleum & Chemical", "SNP"),
    ),
}


def _normalise(name: str) -> str:
    """Lowercase, strip, drop common suffixes + punctuation."""
    if not name:
        return ""
    s = name.lower().strip()
    # Strip common suffixes (one pass is enough — order matters)
    suffixes = (
        " corporation", " incorporated", " limited", " plc", " p.l.c.",
        " plc.", " ltd.", " ltd", " inc.", " inc", " co.", " company",
        " corp.", " corp", " s.a.", " sa", " s.e.", " se", " ag", " group",
        " holdings", " holding",
    )
    for suf in suffixes:
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
            break
    # Drop punctuation we don't care about; keep word characters and spaces
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── Index built from the curated map ──────────────────────────────────────────
# Per-entry alias keys (normalised) -> EntityRecord. Computed once at module
# import. Reverse direction: normalised name from `_CURATED` keys + aliases.
_ALIAS_INDEX: Dict[str, EntityRecord] = {}


def _build_index() -> None:
    _ALIAS_INDEX.clear()
    for primary_key, rec in _CURATED.items():
        _ALIAS_INDEX[primary_key] = rec
        _ALIAS_INDEX[_normalise(rec.canonical_name)] = rec
        for alias in rec.aliases:
            _ALIAS_INDEX[_normalise(alias)] = rec
    # Load runtime overrides (callers can extend via register_override or by
    # editing data/entity_alias_overrides.json).
    if _OVERRIDES_PATH.exists():
        try:
            with open(_OVERRIDES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data if isinstance(data, list) else []:
                rec = EntityRecord(
                    canonical_name=str(entry.get("canonical_name", "")),
                    lei=entry.get("lei"),
                    country_iso3=entry.get("country_iso3"),
                    aliases=tuple(entry.get("aliases") or ()),
                )
                if not rec.canonical_name:
                    continue
                _ALIAS_INDEX[_normalise(rec.canonical_name)] = rec
                for alias in rec.aliases:
                    _ALIAS_INDEX[_normalise(alias)] = rec
        except Exception as e:
            logger.warning("entity_alias_overrides.json failed to load: %s", e)


_build_index()


# ── Public API ───────────────────────────────────────────────────────────────
def resolve(name: str) -> Optional[EntityRecord]:
    """Return the canonical EntityRecord for `name`, or None if unresolved.

    Strategy:
      1. Direct lookup against normalised aliases (O(1))
      2. rapidfuzz fallback against the alias key list, threshold 90+
    """
    if not name:
        return None
    norm = _normalise(name)
    if norm in _ALIAS_INDEX:
        return _ALIAS_INDEX[norm]

    # Fuzzy fallback — only used when direct lookup misses. We import here
    # because rapidfuzz adds ~30ms to module load and most callers hit the
    # fast path.
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        logger.debug("rapidfuzz not available; entity resolver running in exact-match mode")
        return None

    candidates = list(_ALIAS_INDEX.keys())
    if not candidates:
        return None
    best = process.extractOne(norm, candidates, scorer=fuzz.WRatio)
    if best and best[1] >= _FUZZY_THRESHOLD:
        matched_key, score, _idx = best
        logger.debug("entity_resolver fuzzy match: %r -> %r (score=%.1f)", name, matched_key, score)
        return _ALIAS_INDEX[matched_key]
    return None


def record_to_dict(rec: Optional[EntityRecord]) -> Optional[Dict[str, object]]:
    """JSON-safe representation for state passing + report embedding."""
    if rec is None:
        return None
    d = asdict(rec)
    # Convert tuple to list for JSON serialisation
    d["aliases"] = list(rec.aliases)
    return d


def register_override(canonical_name: str, lei: Optional[str],
                      country_iso3: Optional[str],
                      aliases: Optional[List[str]] = None) -> None:
    """Add a new entity at runtime. Persists to entity_alias_overrides.json."""
    rec = EntityRecord(
        canonical_name=canonical_name,
        lei=lei,
        country_iso3=country_iso3,
        aliases=tuple(aliases or ()),
    )
    _ALIAS_INDEX[_normalise(canonical_name)] = rec
    for a in rec.aliases:
        _ALIAS_INDEX[_normalise(a)] = rec

    # Persist
    existing: List[Dict[str, object]] = []
    if _OVERRIDES_PATH.exists():
        try:
            with open(_OVERRIDES_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f) or []
        except Exception:
            existing = []
    existing.append(record_to_dict(rec))
    os.makedirs(_OVERRIDES_PATH.parent, exist_ok=True)
    with open(_OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def all_known_companies() -> List[str]:
    """Diagnostic — list canonical names currently in the index."""
    return sorted({rec.canonical_name for rec in _ALIAS_INDEX.values()})
