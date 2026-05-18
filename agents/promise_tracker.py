"""Promise tracker — wraps the promise ledger; runs per pipeline.

For each measurable sub-claim, extract (metric, target_year, target_value)
and lookup against the ledger to label the promise. New promises are
inserted; repeated promises get `seen_count++` + status updated.

Status determination:
  NEW          — not previously seen
  IN_PROGRESS  — seen ≥ 2 times, target_year > current_year, unchanged target_value
  KEPT         — target_year ≤ current_year AND latest_value satisfies target
                 (we don't have latest_value yet — flagged as `KEPT_TENTATIVE`)
  MISSED       — target_year ≤ current_year AND latest_value falls short
  RETRACTED    — previously seen, target_year matches, but absent in current run
                 (handled by ledger reconciliation; not detected here)
  DELAYED      — target_year > previously-recorded target_year for same metric
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _decide_status(
    existing: Optional[Dict[str, Any]],
    extracted: Dict[str, Any],
    current_year: int,
) -> str:
    target_year = int(extracted.get("target_year") or 0)
    target_value = extracted.get("target_value")
    if existing is None:
        if target_year <= current_year:
            return "MISSED" if (target_value is not None and target_value > 0) else "KEPT_TENTATIVE"
        return "NEW"
    # Existing — compare target_year for DELAYED detection
    prior_year = existing.get("target_year")
    if isinstance(prior_year, int) and target_year > prior_year:
        return "DELAYED"
    if target_year <= current_year:
        return "MISSED" if (target_value is not None and target_value > 0) else "KEPT_TENTATIVE"
    return "IN_PROGRESS"


def run(
    company_lei: Optional[str],
    sub_claims: List[Dict[str, Any]],
    report_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract + persist promises. Returns aggregate summary."""
    out: Dict[str, Any] = {
        "agent":         "promise_tracker",
        "company_lei":   company_lei,
        "tracked_promises": [],
        "status_counts":   {"NEW": 0, "IN_PROGRESS": 0, "KEPT_TENTATIVE": 0,
                             "MISSED": 0, "DELAYED": 0},
        "promise_degradation_score": 0.0,
        "ledger_delta":  0.0,
        "ledger_bucket": "promise_tracking",
        "source":        "promise_ledger",
        "rationale":     "",
    }
    if not company_lei:
        out["rationale"] = "No company_lei — cannot key the promise ledger."
        return out

    from core.promise_ledger import (
        PromiseLedger, extract_promises_from_subclaims,
    )
    ledger = PromiseLedger()
    extracted_rows = extract_promises_from_subclaims(sub_claims or [])
    if not extracted_rows:
        out["rationale"] = "No quantified promises found in sub_claims."
        return out

    current_year = datetime.now(timezone.utc).year
    counts = out["status_counts"]
    tracked: List[Dict[str, Any]] = []

    for er in extracted_rows:
        metric = er["metric"]
        target_year = int(er["target_year"])
        # Find by exact (lei, metric, target_year) first; if absent, fall back
        # to "latest for this metric" so we catch DELAYED-when-target-year-shifts.
        existing = ledger.find(company_lei, metric, target_year)
        if not existing:
            existing = ledger.find_latest_for_metric(company_lei, metric)
        existing_d = existing.to_dict() if existing else None
        status = _decide_status(existing_d, er, current_year)
        rec = ledger.record(
            company_lei=company_lei,
            metric=metric,
            target_year=target_year,
            target_value=er.get("target_value"),
            target_unit=er.get("target_unit"),
            claim_text=er.get("claim_text") or "",
            report_id=report_id,
            status_label=status,
        )
        counts[status] = counts.get(status, 0) + 1
        tracked.append({
            **rec.to_dict(),
            "prior_target_year": (existing_d or {}).get("target_year"),
            "prior_target_value": (existing_d or {}).get("target_value"),
            "prior_status": (existing_d or {}).get("status_label"),
        })

    out["tracked_promises"] = tracked

    # Degradation score: weighted by status severity
    weights = {"MISSED": 10.0, "DELAYED": 6.0, "IN_PROGRESS": 0.0,
               "KEPT_TENTATIVE": -3.0, "NEW": 0.0}
    score = sum(weights.get(s, 0.0) * counts.get(s, 0) for s in counts)
    out["promise_degradation_score"] = round(min(40.0, max(-15.0, score)), 1)

    # Ledger delta: scale degradation -> GW pts (with cap)
    if score >= 20:
        out["ledger_delta"] = 8.0
    elif score >= 10:
        out["ledger_delta"] = 4.0
    elif score >= 5:
        out["ledger_delta"] = 2.0
    elif score <= -5:
        out["ledger_delta"] = -2.0

    out["rationale"] = (
        f"Tracked {len(tracked)} promises: "
        f"{counts.get('NEW', 0)} NEW, "
        f"{counts.get('IN_PROGRESS', 0)} IN_PROGRESS, "
        f"{counts.get('KEPT_TENTATIVE', 0)} KEPT, "
        f"{counts.get('MISSED', 0)} MISSED, "
        f"{counts.get('DELAYED', 0)} DELAYED. "
        f"Degradation score {out['promise_degradation_score']}."
    )
    return out


def build_ledger_row(tracker_out: Dict[str, Any]) -> Dict[str, Any]:
    delta = float(tracker_out.get("ledger_delta") or 0.0)
    if abs(delta) < 0.01:
        return {}
    return {
        "bucket":          tracker_out.get("ledger_bucket", "promise_tracking"),
        "source":          "promise_tracker",
        "delta":           delta,
        "direction":       "increases_gw_risk" if delta > 0 else "decreases_gw_risk",
        "rationale":       tracker_out.get("rationale", ""),
        "evidence_source": "Promise Ledger (data/promise_ledger.db)",
        "evidence_url":    None,
        "promise_count":   len(tracker_out.get("tracked_promises") or []),
        "degradation_score": tracker_out.get("promise_degradation_score"),
        "status_counts":   tracker_out.get("status_counts"),
    }
