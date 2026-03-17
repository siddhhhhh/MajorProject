#!/usr/bin/env python3
"""
ESG Greenwashing Detection System - Validation Runner
Usage: python run_validation.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime


def ensure_pytest_installed() -> None:
    try:
        import pytest  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest"], check=True)


def run_step(name, fn, *args, **kwargs):
    print(f"\n{'=' * 60}")
    print(f"RUNNING: {name}")
    print('=' * 60)
    try:
        result = fn(*args, **kwargs)
        print(f"[OK] {name} completed")
        return result
    except Exception as exc:
        print(f"[ERROR] {name} failed: {exc}")
        import traceback
        traceback.print_exc()
        return None


def main() -> int:
    ensure_pytest_installed()
    os.makedirs("reports", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    print("ESG GREENWASHING DETECTION - VALIDATION SUITE")
    print(f"Started: {datetime.now().isoformat()}")

    from data.ground_truth_builder import build_ground_truth_dataset
    run_step("Building Ground Truth Dataset", build_ground_truth_dataset)

    from ml_models.model_evaluator import run_full_evaluation
    eval_results = run_step("ML Model Evaluation", run_full_evaluation) or {}

    from ml_models.score_calibrator import run_calibration
    run_step("Score Calibration", run_calibration)

    run_step(
        "Running Test Suite",
        subprocess.run,
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        check=False,
    )

    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE - SUMMARY")
    print("=" * 60)

    best_model = eval_results.get("best_model")
    cv = (eval_results.get("cross_validation_results") or {}).get(best_model or "", {})
    if best_model and cv:
        print(f"Best ML Model (CV F1): {best_model} ({cv.get('f1_mean', 0):.3f})")

    caveat = eval_results.get("holdout_warning")
    if caveat:
        print(f"NOTE: {caveat}")

    print("\nAll reports saved to: reports/")
    print(f"Completed: {datetime.now().isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
