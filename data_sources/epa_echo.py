"""EPA ECHO — Enforcement & Compliance History Online (free, anonymous).

ECHO is the EPA's public data warehouse with five years of enforcement,
inspection, and violation history for ~1.5M regulated facilities.

We use the REST endpoints under echo.epa.gov/echo/.

Public API:
    facility_search(company_name) -> List[FacilityRecord]
    facility_history(registry_id) -> List[ViolationRecord]
    summarise_violations(violations) -> Dict   # counts + total penalty
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BASE_URL = "https://echo.epa.gov/efservice"
_DEFAULT_TIMEOUT = 20.0
_USER_AGENT = "esglens/1.0 (educational; +https://esglens.com)"

# EPA ECHO REST API status (as of 2026-05): the legacy efservice REST
# endpoints under echo.epa.gov return 404 for facility-search calls.
# Tested replacement candidates (enviro.epa.gov/efservice, data.epa.gov,
# echodata.epa.gov, ofmpub.epa.gov) all return 404 or generic EPA error
# HTML. Until EPA restores or migrates, treat search failure as
# "ENDPOINT_UNAVAILABLE" rather than silently inferring zero fines —
# zero-fines was being misread downstream as a BETTER_THAN_PEER credit
# that lowered the GW score on the basis of an unreachable API.
class EpaEchoUnavailable(RuntimeError):
    """Raised when the EPA ECHO REST endpoint returns a deprecation-style
    404. Callers should distinguish this from a legitimate "zero results"
    response."""


@dataclass
class FacilityRecord:
    registry_id: str
    name: str
    state: Optional[str]
    facility_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "registry_id":  self.registry_id,
            "name":         self.name,
            "state":        self.state,
            "facility_url": self.facility_url,
        }


@dataclass
class ViolationRecord:
    facility_registry_id: str
    facility_name: str
    program: str          # CAA / CWA / RCRA / etc.
    violation_type: str
    statute: Optional[str]
    fine_usd: Optional[float]
    inspection_date: Optional[str]
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facility_registry_id": self.facility_registry_id,
            "facility_name":        self.facility_name,
            "program":              self.program,
            "violation_type":       self.violation_type,
            "statute":              self.statute,
            "fine_usd":             self.fine_usd,
            "inspection_date":      self.inspection_date,
            "summary":              self.summary,
        }


def _http_get_json(url: str, timeout: float = _DEFAULT_TIMEOUT) -> Optional[Any]:
    """GET JSON. Raises EpaEchoUnavailable on the deprecated-endpoint 404
    pattern so the caller can surface UNAVAILABLE instead of treating it
    as "zero results"."""
    import urllib.error
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                # The legacy ECHO endpoint returns a ~65KB HTML 404 stub
                # with HTTP 200 in some configurations — detect this so we
                # don't silently degrade to "zero violations".
                if body[:50].lstrip().startswith((b"<!doctype", b"<html", b"<!DOCTYPE")):
                    raise EpaEchoUnavailable(
                        "EPA ECHO returned an HTML stub instead of JSON — "
                        "endpoint appears deprecated."
                    )
                return None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise EpaEchoUnavailable(
                f"EPA ECHO REST endpoint returned 404 — endpoint deprecated: {url[:120]}"
            )
        logger.warning("EPA ECHO GET HTTP %d: %s", exc.code, url[:120])
        return None
    except EpaEchoUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("EPA ECHO GET failed: %s | %s", url[:120], exc)
        return None


def facility_search(company_name: str, max_results: int = 20) -> List[FacilityRecord]:
    """Find ECHO facilities matching company name."""
    if not company_name:
        return []
    # ECHO facility search REST: /efservice/echo_rest_services.get_facilities/p_fn/<name>
    # JSON format requested by ?output=JSON
    encoded = urllib.parse.quote(company_name)
    url = (
        f"{_BASE_URL}/echo_rest_services.get_facilities/p_fn/{encoded}"
        f"/rows/1:{max_results}/output/JSON"
    )
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return []
    results = (
        (data.get("Results") or {}).get("Facilities")
        or (data.get("Results") or {}).get("FRSFacility")
        or []
    )
    out: List[FacilityRecord] = []
    for r in results[:max_results]:
        if not isinstance(r, dict):
            continue
        out.append(FacilityRecord(
            registry_id=str(r.get("RegistryID") or r.get("FacRegistryID") or ""),
            name=str(r.get("FacilityName") or r.get("FacName") or ""),
            state=r.get("FacState"),
            facility_url=str(r.get("FacURL") or ""),
        ))
    return out


def facility_history(registry_id: str) -> List[ViolationRecord]:
    """Return enforcement+violation history for a facility."""
    if not registry_id:
        return []
    url = (
        f"{_BASE_URL}/get_facility_info/p_id/{urllib.parse.quote(registry_id)}"
        f"/output/JSON"
    )
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return []
    fac = ((data.get("Results") or {}).get("FacilityInfo") or [{}])[0]
    if not isinstance(fac, dict):
        return []
    out: List[ViolationRecord] = []
    # ECHO surfaces a "CAAFormalActions", "CWAFormalActions", etc.
    for program in ("CAA", "CWA", "RCRA", "SDWA", "TSCA"):
        actions = fac.get(f"{program}FormalActions") or fac.get(f"{program}_3yr_compl_qtrs_history") or []
        if not isinstance(actions, list):
            continue
        for a in actions:
            if not isinstance(a, dict):
                continue
            out.append(ViolationRecord(
                facility_registry_id=registry_id,
                facility_name=str(fac.get("FacilityName") or ""),
                program=program,
                violation_type=str(a.get("ViolationType") or a.get("LawSection") or "?"),
                statute=a.get("Statute"),
                fine_usd=_parse_fine(a.get("FederalPenaltyAssessedAmt") or a.get("ActionAmount")),
                inspection_date=a.get("LeadAgencyCaseLodgedDate") or a.get("ActionDate"),
                summary=str(a.get("CaseName") or "")[:240],
            ))
    return out


def _parse_fine(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    if isinstance(v, str):
        s = v.replace("$", "").replace(",", "").strip()
        try:
            f = float(s)
            return f if f > 0 else None
        except ValueError:
            return None
    return None


def summarise_violations(violations: List[ViolationRecord]) -> Dict[str, Any]:
    if not violations:
        return {
            "total_count": 0,
            "by_program": {},
            "total_fines_usd": 0.0,
            "fines_by_program": {},
        }
    by_program: Dict[str, int] = {}
    fines_by_program: Dict[str, float] = {}
    total_fines = 0.0
    for v in violations:
        by_program[v.program] = by_program.get(v.program, 0) + 1
        if isinstance(v.fine_usd, (int, float)):
            total_fines += float(v.fine_usd)
            fines_by_program[v.program] = fines_by_program.get(v.program, 0.0) + float(v.fine_usd)
    return {
        "total_count": len(violations),
        "by_program":  by_program,
        "total_fines_usd": total_fines,
        "fines_by_program": fines_by_program,
    }
