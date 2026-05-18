"""Versioned regulatory-framework registry loader.

Replaces the hardcoded FRAMEWORK_CREDIBILITY_WEIGHTS dict in
utils/regulatory_fetchers.py and centralises framework metadata
(jurisdiction applicability, weight, status, version, source URL)
into a single data file at data/regulatory_frameworks.json.

Design rules:
- Loader is read-only. Mutating frameworks at runtime is forbidden.
- `as_of` date filter: a framework is active iff
  effective_date <= as_of <= (sunset_date or infinity).
- `registry_version` from the JSON is stamped onto every report so
  historical reports stay reproducible after the registry is updated.
- Layered status logic (SBTi registry guard, net-zero check) stays in
  agents/regulatory_scanner.py — this loader provides the *data*, not
  the scoring rules.

Public API:
    load_registry(as_of=None) -> dict
    get_active_frameworks(as_of=None) -> list[dict]
    get_framework(framework_id, as_of=None) -> dict | None
    get_framework_by_scanner_id(scanner_reg_id, as_of=None) -> dict | None
    get_weight(name_or_id, as_of=None) -> float
    get_applicable_frameworks(country_code, company_name, industry, as_of=None) -> list[str]
    get_applicable_framework_objects(country_code, company_name, industry, as_of=None) -> list[dict]
    get_claim_validation_rules(scanner_reg_id, as_of=None) -> list[dict]
    registry_version(as_of=None) -> str
    volatility_share(framework_names, as_of=None) -> float
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REGISTRY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "regulatory_frameworks.json"
)

_lock = threading.Lock()
_cache: Dict[str, Any] = {"mtime": 0.0, "payload": None}

# Status keys considered "volatile" — used by Phase D confidence flag.
VOLATILE_STATUSES = {"under_consultation", "draft"}
# Status keys we still apply but with caution.
DEPRECATED_STATUSES = {"deprecated", "retired"}


# ── Date helpers ─────────────────────────────────────────────────────────────

def _parse_date(value: Any) -> Optional[date]:
    if value in (None, "", "null"):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _today() -> date:
    return date.today()


# ── Registry loader ─────────────────────────────────────────────────────────

def _load() -> Dict[str, Any]:
    """Read + cache the JSON. Returns empty payload on any failure so the
    pipeline degrades gracefully (no frameworks = no compliance scoring,
    but no crash)."""
    try:
        mtime = os.path.getmtime(_REGISTRY_PATH)
    except OSError:
        logger.warning("regulatory_frameworks.json missing at %s", _REGISTRY_PATH)
        return {"frameworks": [], "registry_version": "missing"}

    with _lock:
        if mtime == _cache["mtime"] and _cache["payload"] is not None:
            return _cache["payload"]
        try:
            with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f) or {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("regulatory_frameworks.json unreadable: %s", exc)
            payload = {"frameworks": [], "registry_version": "unreadable"}
        if not isinstance(payload.get("frameworks"), list):
            payload["frameworks"] = []
        _cache["mtime"] = mtime
        _cache["payload"] = payload
        return payload


def load_registry(as_of: Optional[date] = None) -> Dict[str, Any]:
    """Full registry payload, optionally filtered to active-at-date events.

    Caller-facing wrapper that always returns the same shape:
        {schema_version, registry_version, frameworks: [...active...]}
    """
    payload = _load()
    active = get_active_frameworks(as_of)
    return {
        "schema_version":      payload.get("schema_version", "unknown"),
        "registry_version":    payload.get("registry_version", "unknown"),
        "as_of":               (as_of or _today()).isoformat(),
        "frameworks":          active,
    }


def get_active_frameworks(as_of: Optional[date] = None) -> List[Dict[str, Any]]:
    """Frameworks whose [effective_date, sunset_date] window covers `as_of`."""
    when = as_of or _today()
    out: List[Dict[str, Any]] = []
    for fw in _load().get("frameworks", []):
        eff = _parse_date(fw.get("effective_date"))
        sun = _parse_date(fw.get("sunset_date"))
        if eff is None:
            continue
        if when < eff:
            continue
        if sun is not None and when > sun:
            continue
        out.append(fw)
    return out


def get_framework(framework_id: str, as_of: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """Look up a single framework by `framework_id` (active-at-date)."""
    target = (framework_id or "").lower().strip()
    if not target:
        return None
    for fw in get_active_frameworks(as_of):
        if (fw.get("framework_id") or "").lower() == target:
            return fw
    return None


def _by_name_or_id(needle: str, as_of: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """Find a framework whose `name`, `framework_id`, or any alias matches `needle`.

    Aliases are case-insensitive. Use this when the caller has a free-form
    framework string (e.g. legacy display names, scanner IDs).
    """
    if not needle:
        return None
    n = str(needle).strip()
    nlow = n.lower()
    for fw in get_active_frameworks(as_of):
        if (fw.get("framework_id") or "").lower() == nlow:
            return fw
        if (fw.get("name") or "") == n:
            return fw
        if (fw.get("name") or "").lower() == nlow:
            return fw
        for alias in fw.get("aliases") or []:
            if isinstance(alias, str) and alias.lower() == nlow:
                return fw
    return None


def get_framework_by_scanner_id(
    scanner_reg_id: str, as_of: Optional[date] = None
) -> Optional[Dict[str, Any]]:
    """Look up a framework by `scanner_reg_id` (the scanner's internal key)."""
    target = (scanner_reg_id or "").strip()
    if not target:
        return None
    for fw in get_active_frameworks(as_of):
        if (fw.get("scanner_reg_id") or "") == target:
            return fw
    return None


def get_claim_validation_rules(
    scanner_reg_id: str, as_of: Optional[date] = None
) -> List[Dict[str, Any]]:
    """Return the JSON-canonical claim_validation_rules for a scanner reg_id.

    Gap 2: scanner reads rules from here first; falls back to its in-memory
    dict only when the registry has no rules for this reg_id.
    """
    fw = get_framework_by_scanner_id(scanner_reg_id, as_of)
    if not fw:
        return []
    rules = fw.get("claim_validation_rules") or []
    return [r for r in rules if isinstance(r, dict) and r.get("pattern") and r.get("requirement")]


def get_weight(name_or_id: str, as_of: Optional[date] = None) -> float:
    """Return the credibility weight (default 0.5 for unknown frameworks).

    Drop-in replacement for utils.regulatory_fetchers.get_framework_weight.
    """
    fw = _by_name_or_id(name_or_id, as_of)
    if fw is None:
        return 0.5
    try:
        return float(fw.get("weight", 0.5))
    except (TypeError, ValueError):
        return 0.5


# ── Applicability routing ───────────────────────────────────────────────────

def _country_match(applicability: Dict[str, Any], country_code: str, company_name: str) -> bool:
    """Apply jurisdiction_applicability rules: country codes (with '*' wildcard)
    + free-form company-name hints (e.g. 'NSE', 'BSE', 'LONDON')."""
    if not isinstance(applicability, dict):
        return True  # No rules → global
    codes = applicability.get("country_codes") or []
    hints = applicability.get("company_name_hints") or []
    cu = (country_code or "").upper()
    nu = (company_name or "").upper()

    code_match = False
    if "*" in codes:
        code_match = True
    elif cu and any(cu == str(c).upper() for c in codes):
        code_match = True

    hint_match = False
    if nu and any(h and h.upper() in nu for h in hints):
        hint_match = True

    return code_match or hint_match


def get_applicable_framework_objects(
    country_code: str,
    company_name: str = "",
    industry: str = "",
    as_of: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Return full framework dicts applicable to (country_code, company_name, industry).

    Used by the scanner to grab `scanner_reg_id` directly, avoiding the
    fragile name → reg_id lookup that the legacy if/elif chain depended on.
    """
    out: List[Dict[str, Any]] = []
    ind = (industry or "").lower().strip()
    for fw in get_active_frameworks(as_of):
        if not _country_match(
            fw.get("jurisdiction_applicability") or {}, country_code, company_name
        ):
            continue
        ind_app = fw.get("industry_applicability") or {}
        include = [str(x).lower() for x in (ind_app.get("include") or [])]
        exclude = [str(x).lower() for x in (ind_app.get("exclude") or [])]
        if "all" not in include and include and ind and not any(i in ind for i in include):
            continue
        if ind and any(e in ind for e in exclude):
            continue
        out.append(fw)
    return out


def get_applicable_frameworks(
    country_code: str,
    company_name: str = "",
    industry: str = "",
    as_of: Optional[date] = None,
) -> List[str]:
    """Return framework names applicable to (country_code, company_name, industry).

    Drop-in replacement for the if/elif chain that used to live at
    agents/regulatory_scanner.py::get_applicable_frameworks. Reads from
    data/regulatory_frameworks.json — edit JSON to change applicability.
    """
    out: List[str] = []
    for fw in get_applicable_framework_objects(country_code, company_name, industry, as_of):
        name = fw.get("name")
        if name:
            out.append(name)
    return out


# ── Versioning + volatility ─────────────────────────────────────────────────

def registry_version(as_of: Optional[date] = None) -> str:
    """Returns the stamped version string for the registry. Use this on
    every report so historical reports stay reproducible after updates."""
    payload = _load()
    return str(payload.get("registry_version") or "unknown")


def volatility_share(framework_names: List[str], as_of: Optional[date] = None) -> Dict[str, Any]:
    """Compute the share of *weight* coming from frameworks tagged as
    `under_consultation` or `draft` among the given list of framework names.

    Phase D consumes this for the confidence flag.
    """
    volatile_w = 0.0
    total_w = 0.0
    volatile_ids: List[str] = []
    for nm in framework_names or []:
        fw = _by_name_or_id(nm, as_of)
        if fw is None:
            continue
        w = float(fw.get("weight", 0.5))
        total_w += w
        if (fw.get("status") or "").lower() in VOLATILE_STATUSES:
            volatile_w += w
            volatile_ids.append(fw.get("framework_id", nm))
    return {
        "total_weight":       round(total_w, 3),
        "volatile_weight":    round(volatile_w, 3),
        "volatile_share":     round(volatile_w / total_w, 3) if total_w > 0 else 0.0,
        "volatile_framework_ids": volatile_ids,
    }


def snapshot_for_report(as_of: Optional[date] = None) -> Dict[str, Any]:
    """Compact summary stamped onto every report — registry_version +
    a per-framework status digest so future re-derivation knows what
    ruleset was active."""
    payload = _load()
    active = get_active_frameworks(as_of)
    by_status: Dict[str, int] = {}
    digest: List[Dict[str, Any]] = []
    for fw in active:
        st = (fw.get("status") or "stable").lower()
        by_status[st] = by_status.get(st, 0) + 1
        digest.append({
            "framework_id":   fw.get("framework_id"),
            "name":           fw.get("name"),
            "version":        fw.get("version"),
            "status":         st,
            "weight":         fw.get("weight"),
        })
    return {
        "registry_version": payload.get("registry_version"),
        "schema_version":   payload.get("schema_version"),
        "as_of":            (as_of or _today()).isoformat(),
        "active_count":     len(active),
        "status_counts":    by_status,
        "frameworks":       digest,
    }
