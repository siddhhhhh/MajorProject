"""
core/feedback_collector.py
---------------------------
Fixes Problems #11 (Feedback Loop) and #8 (Calibration)

Provides:
  - Report accuracy feedback collection
  - Outcome tracking over time
  - Calibration drift detection
  - Auto-recalibration triggers
"""
from __future__ import annotations
import json, os, logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FEEDBACK_DIR = Path(os.path.dirname(__file__)).parent / "data" / "feedback"
FEEDBACK_FILE = FEEDBACK_DIR / "feedback_log.jsonl"
OUTCOMES_FILE = FEEDBACK_DIR / "outcome_log.jsonl"


def _ensure_dir():
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def submit_feedback(
    company: str,
    report_id: str,
    *,
    accuracy_rating: int,  # 1-5
    gw_score_accurate: Optional[bool] = None,
    esg_score_accurate: Optional[bool] = None,
    user_comment: str = "",
    analyst_id: str = "anonymous",
) -> Dict[str, Any]:
    """
    Record user/analyst feedback on a generated report.
    Used to track prediction quality over time.
    """
    _ensure_dir()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "company": company,
        "report_id": report_id,
        "accuracy_rating": max(1, min(5, accuracy_rating)),
        "gw_score_accurate": gw_score_accurate,
        "esg_score_accurate": esg_score_accurate,
        "user_comment": user_comment,
        "analyst_id": analyst_id,
    }
    try:
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("Feedback recorded for %s (report %s)", company, report_id)
    except Exception as e:
        logger.warning("Failed to write feedback: %s", e)
    return entry


def record_outcome(
    company: str,
    report_id: str,
    *,
    predicted_gw_score: float,
    predicted_esg_score: float,
    predicted_risk_level: str,
    actual_outcome: str,  # "CONFIRMED_GREENWASHING", "LEGITIMATE", "MIXED", "UNKNOWN"
    outcome_source: str = "",  # e.g., "SEC enforcement", "court ruling"
    outcome_date: str = "",
) -> Dict[str, Any]:
    """
    Record a real-world outcome for a previously scored company.
    Used to compute precision/recall and calibration drift.
    """
    _ensure_dir()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "company": company,
        "report_id": report_id,
        "predicted_gw_score": round(predicted_gw_score, 1),
        "predicted_esg_score": round(predicted_esg_score, 1),
        "predicted_risk_level": predicted_risk_level,
        "actual_outcome": actual_outcome,
        "outcome_source": outcome_source,
        "outcome_date": outcome_date,
    }
    try:
        with open(OUTCOMES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("Outcome recorded for %s: %s", company, actual_outcome)
    except Exception as e:
        logger.warning("Failed to write outcome: %s", e)
    return entry


def compute_calibration_drift() -> Dict[str, Any]:
    """
    Analyze recorded outcomes vs predictions to detect calibration drift.
    Returns metrics on prediction accuracy.
    """
    if not OUTCOMES_FILE.exists():
        return {"status": "NO_DATA", "total_outcomes": 0}

    outcomes = []
    try:
        with open(OUTCOMES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    outcomes.append(json.loads(line))
    except Exception as e:
        return {"status": "READ_ERROR", "error": str(e)}

    if len(outcomes) < 5:
        return {"status": "INSUFFICIENT_DATA", "total_outcomes": len(outcomes)}

    # Compute accuracy metrics
    correct_direction = 0
    total_with_outcome = 0
    gw_errors = []

    for o in outcomes:
        actual = o.get("actual_outcome", "UNKNOWN")
        if actual == "UNKNOWN":
            continue
        total_with_outcome += 1
        predicted_gw = o.get("predicted_gw_score", 50)
        predicted_risk = o.get("predicted_risk_level", "MODERATE")

        if actual == "CONFIRMED_GREENWASHING":
            expected_high = predicted_risk == "HIGH" or predicted_gw >= 60
            if expected_high:
                correct_direction += 1
            gw_errors.append(max(0, 65 - predicted_gw))  # Should be >=65
        elif actual == "LEGITIMATE":
            expected_low = predicted_risk == "LOW" or predicted_gw <= 40
            if expected_low:
                correct_direction += 1
            gw_errors.append(max(0, predicted_gw - 35))  # Should be <=35

    accuracy = correct_direction / max(1, total_with_outcome)
    avg_gw_error = sum(gw_errors) / max(1, len(gw_errors))

    needs_recalibration = accuracy < 0.70 or avg_gw_error > 15

    return {
        "status": "COMPUTED",
        "total_outcomes": len(outcomes),
        "outcomes_with_verdict": total_with_outcome,
        "directional_accuracy": round(accuracy, 3),
        "avg_gw_score_error": round(avg_gw_error, 1),
        "needs_recalibration": needs_recalibration,
        "recommendation": (
            "Recalibration recommended — accuracy below 70% or GW error above 15 points"
            if needs_recalibration
            else "Calibration within acceptable range"
        ),
    }


def get_feedback_summary() -> Dict[str, Any]:
    """Get summary statistics from collected feedback."""
    if not FEEDBACK_FILE.exists():
        return {"status": "NO_FEEDBACK", "total_entries": 0}

    entries = []
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception:
        return {"status": "READ_ERROR"}

    if not entries:
        return {"status": "NO_FEEDBACK", "total_entries": 0}

    ratings = [e.get("accuracy_rating", 3) for e in entries]
    gw_accurate = [e for e in entries if e.get("gw_score_accurate") is not None]
    esg_accurate = [e for e in entries if e.get("esg_score_accurate") is not None]

    return {
        "status": "OK",
        "total_entries": len(entries),
        "avg_accuracy_rating": round(sum(ratings) / len(ratings), 2),
        "gw_accuracy_rate": round(
            sum(1 for e in gw_accurate if e["gw_score_accurate"]) / max(1, len(gw_accurate)), 3
        ) if gw_accurate else None,
        "esg_accuracy_rate": round(
            sum(1 for e in esg_accurate if e["esg_score_accurate"]) / max(1, len(esg_accurate)), 3
        ) if esg_accurate else None,
        "latest_feedback_date": entries[-1].get("timestamp", ""),
    }
