"""
api/reports.py
--------------
GET /api/reports          → list of all completed reports (HistoryEntry)
GET /api/reports/{id}     → full ESGReport by id
GET /api/reports/{id}/pdf → audit-ready PDF download
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from api.mappers import map_report_to_history, map_report_to_schema, _short_id
from api.models import ESGReport, HistoryEntry

router = APIRouter(prefix="/api")

REPORTS_DIR = Path(os.getenv("ESG_REPORTS_DIR", "reports"))


def _parse_report_dt(raw: dict, path: Path) -> datetime:
    for key in ("analysis_date", "generated_at_utc", "generated_utc"):
        value = raw.get(key)
        if not value:
            continue
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def _report_preference(path: Path) -> tuple[int, float]:
    """Prefer canonical ESG_Report files because they have TXT/brief companions."""
    has_txt = path.with_suffix(".txt").exists()
    is_named_artifact = path.stem.startswith("ESG_Report_")
    return (1 if has_txt else 0) + (1 if is_named_artifact else 0), path.stat().st_mtime


def _dedupe_key(raw: dict, path: Path) -> tuple[str, str, str, int]:
    """Group duplicate writes from the same analysis run."""
    report_id = str(raw.get("report_id") or "").strip()
    if report_id:
        return ("report_id", report_id, "", 0)

    company = str(raw.get("company") or "").strip().lower()
    claim = str(raw.get("claim_analyzed") or raw.get("claim") or "").strip().lower()
    dt = _parse_report_dt(raw, path)
    # Same company/claim writes inside a two-second bucket are one run.
    return ("run_window", company, claim, int(dt.timestamp()) // 2)


def _iter_report_jsons():
    """Yield (report_id, parsed_dict) for every valid JSON report on disk."""
    if not REPORTS_DIR.exists():
        return
    chosen: dict[tuple[str, str, str, int], tuple[Path, dict]] = {}

    for p in sorted(REPORTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        # Skip lineage / debug files
        if "lineage" in p.stem or "FULL" in p.stem or "research_runs" in p.stem:
            continue
        if p.stem.lower().endswith("_brief"):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if not (isinstance(data, dict) and "scores" in data):
                continue

            key = _dedupe_key(data, p)
            existing = chosen.get(key)
            if existing is None or _report_preference(p) > _report_preference(existing[0]):
                chosen[key] = (p, data)
        except Exception:
            continue

    # A run may have been written once under report_id and again under the
    # display artifact name. Collapse those too by near-identical company,
    # claim, and analysis timestamp, keeping the richer companion artifact.
    by_window: list[tuple[Path, dict]] = []
    for p, data in chosen.values():
        dt = _parse_report_dt(data, p)
        company = str(data.get("company") or "").strip().lower()
        claim = str(data.get("claim_analyzed") or data.get("claim") or "").strip().lower()
        duplicate_index = None
        for idx, (existing_path, existing_data) in enumerate(by_window):
            existing_dt = _parse_report_dt(existing_data, existing_path)
            existing_company = str(existing_data.get("company") or "").strip().lower()
            existing_claim = str(existing_data.get("claim_analyzed") or existing_data.get("claim") or "").strip().lower()
            if company == existing_company and claim == existing_claim and abs((dt - existing_dt).total_seconds()) <= 5:
                duplicate_index = idx
                break

        if duplicate_index is None:
            by_window.append((p, data))
        elif _report_preference(p) > _report_preference(by_window[duplicate_index][0]):
            by_window[duplicate_index] = (p, data)

    for p, data in sorted(by_window, key=lambda item: item[0].stat().st_mtime, reverse=True):
        yield _short_id(str(p)), data


def _find_raw(report_id: str):
    """Return (raw_dict, path) for a given report_id, or raise 404."""
    if not REPORTS_DIR.exists():
        raise HTTPException(status_code=404, detail="No reports directory found")

    # Some legacy links/store entries may carry a `_brief` report id.
    # Resolve it to the full report first when both files exist.
    if report_id.endswith("_brief"):
        canonical_id = report_id[:-6]
    else:
        canonical_id = report_id

    candidates = sorted(
        REPORTS_DIR.glob("*.json"),
        key=lambda f: _report_preference(f),
        reverse=True,
    )
    for p in candidates:
        if "lineage" in p.stem or "FULL" in p.stem or "research_runs" in p.stem:
            continue
        if p.stem.lower().endswith("_brief"):
            continue
        if _short_id(str(p)) == canonical_id or p.stem == canonical_id:
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f), p
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to parse report: {e}")
    raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")


def _read_companion_artifacts(report_path: Path) -> dict:
    """Read TXT / brief JSON files produced next to the full report JSON.

    The pipeline writes JSON under two parallel naming conventions:
      - `ESG_Report_<Company>_<YYYYMMDD>_<HHMMSS>.json` (display format
        with `.txt` + `_brief.json` companions)
      - `<YYYYMMDD>-<HHMMSS>-<TICKER>.json` (internal/legacy format,
        JSON only, no `.txt` companion)
    When the user opens the internal-format entry from History, we fall
    back to the display-format `.txt` for the same company + day so the
    audit view never says "No TXT artifact".
    """
    stem = report_path.stem
    txt_path = report_path.with_suffix(".txt")
    brief_path = report_path.with_name(f"{stem}_brief.json")

    # ── Companion-TXT fallback for legacy / internal-format JSONs ────────
    fallback_txt: Optional[Path] = None
    if not txt_path.exists():
        # Try to find a sibling ESG_Report_<Company>_<YYYYMMDD>_*.txt
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            company = str(data.get("company") or "").strip()
        except Exception:
            company = ""
        if company:
            company_token = company.replace(" ", "_")
            # Match same-day display-format artifacts only (avoid grabbing
            # an unrelated company's report).
            mtime_day = datetime.fromtimestamp(
                report_path.stat().st_mtime
            ).strftime("%Y%m%d")
            for sibling in report_path.parent.glob(
                f"ESG_Report_{company_token}_{mtime_day}_*.txt"
            ):
                fallback_txt = sibling
                break
            if fallback_txt is None:
                # Looser fallback: any same-company TXT in the dir
                # (handles cross-day lookups when the display run landed
                # slightly later than the internal record).
                for sibling in report_path.parent.glob(
                    f"ESG_Report_{company_token}_*.txt"
                ):
                    fallback_txt = sibling
                    break

    effective_txt = txt_path if txt_path.exists() else fallback_txt

    artifacts: dict = {
        "txt": None,
        "brief": None,
        "full_json": None,
        "files": {
            "txt": effective_txt.name if effective_txt and effective_txt.exists() else None,
            "brief": brief_path.name if brief_path.exists() else None,
            "json": report_path.name,
        },
    }

    if effective_txt and effective_txt.exists():
        artifacts["txt"] = effective_txt.read_text(encoding="utf-8", errors="replace")

    if brief_path.exists():
        try:
            artifacts["brief"] = json.loads(brief_path.read_text(encoding="utf-8"))
        except Exception:
            artifacts["brief"] = None

    try:
        artifacts["full_json"] = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        artifacts["full_json"] = None

    return artifacts


@router.get("/reports", response_model=List[HistoryEntry])
def get_all_reports():
    """Return all completed analyses for the History page."""
    entries = []
    for report_id, raw in _iter_report_jsons():
        try:
            entries.append(map_report_to_history(raw, report_id))
        except Exception:
            continue
    return entries


@router.get("/reports/{report_id}", response_model=ESGReport)
def get_report(report_id: str):
    """Return the full report for a given ID."""
    raw, _ = _find_raw(report_id)
    return map_report_to_schema(raw, report_id)


@router.get("/reports/{report_id}/artifacts")
def get_report_artifacts(report_id: str):
    """Return the exact backend report artifacts used for audit display/export."""
    _, path = _find_raw(report_id)
    return _read_companion_artifacts(path)


@router.post("/reports/{report_id}/counterfactual")
def post_report_counterfactual(report_id: str, body: dict):
    """Recompute the headline GW under user-supplied ledger overrides.

    Body shape:
      {
        "overrides": [
          {"label": str, "drop": true} | {"label": str, "set_value": number}
        ]
      }

    Returns the RecomputeResult dict (see core/counterfactual.py).
    """
    raw, _ = _find_raw(report_id)
    try:
        from core.counterfactual import recompute_with_overrides
        overrides = (body or {}).get("overrides") or []
        if not isinstance(overrides, list):
            raise HTTPException(
                status_code=400,
                detail="`overrides` must be a list of {label, drop|set_value} entries",
            )
        result = recompute_with_overrides(raw, overrides)
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Counterfactual failed: {e}")


@router.get("/reports/{report_id}/leverage")
def get_report_leverage(report_id: str, top_k: int = 5):
    """Top-K leverage ranking — which ledger rows move the headline most.

    Convenience endpoint so the frontend can render a "challenge these
    rows first" list without iterating /counterfactual.
    """
    raw, _ = _find_raw(report_id)
    try:
        from core.counterfactual import leverage_ranking
        return {"top_leverage": leverage_ranking(raw, top_k=top_k)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Leverage ranking failed: {e}")


@router.get("/reports/{report_id}/attribution")
def get_report_attribution(report_id: str):
    """Score attribution / "why this score" decomposition.

    Reads the ranked-contributor view derived from the score modifier ledger.
    Falls back to live recomputation if the export didn't pre-compute it.
    """
    raw, _ = _find_raw(report_id)
    attr = raw.get("score_attribution")
    if not isinstance(attr, dict) or not attr or attr.get("error"):
        try:
            from core.score_attribution import decompose
            attr = decompose(raw)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Score attribution unavailable: {e}",
            )
    return attr


@router.get("/reports/{report_id}/pdf")
def get_report_pdf(report_id: str):
    """Generate and return an audit-ready PDF for the given report ID."""
    raw, path = _find_raw(report_id)
    artifacts = _read_companion_artifacts(path)
    try:
        report_schema = map_report_to_schema(raw, report_id)
        report_dict = report_schema.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build report model: {e}")

    try:
        from api.pdf_generator import build_pdf, build_pdf_from_text
        if artifacts.get("txt"):
            pdf_bytes = build_pdf_from_text(artifacts["txt"], report_dict)
        else:
            pdf_bytes = build_pdf(report_dict, raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    company = report_dict.get("company", "Report").replace(" ", "_").replace("&", "and")
    filename = f"ESGLens_{company}_{report_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
