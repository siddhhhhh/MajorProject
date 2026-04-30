"""
api/analysis.py
---------------
POST /api/analyse          → start a new ESG analysis, returns analysis_id
GET  /api/analysis/{id}    → poll status + result

The pipeline is run as a **subprocess** (main_langgraph.py) so that:
  1. All rich stdout/stderr logs are captured line-by-line
  2. Those logs are stored in-memory and streamed via WebSocket
  3. The pipeline uses the venv Python with all dependencies
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.models import AnalysisRequest

router = APIRouter(prefix="/api")

# ── In-memory store ───────────────────────────────────────────────────────────
_analysis_store: Dict[str, Dict[str, Any]] = {}

# Detect venv python
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = _PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
if not _VENV_PYTHON.exists():
    _VENV_PYTHON = _PROJECT_ROOT / "venv" / "bin" / "python"  # Linux/Mac
if not _VENV_PYTHON.exists():
    _VENV_PYTHON = Path(sys.executable)  # fallback

_ANALYSIS_SCRIPT = _PROJECT_ROOT / "main_langgraph.py"


@router.post("/analyse")
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """Start a new ESG analysis. Returns analysis_id immediately."""
    analysis_id = str(uuid.uuid4())
    _analysis_store[analysis_id] = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "company": request.company,
        "claim": request.claim,
        "industry": request.industry,
        "result": None,
        "progress": 0,
        "error": None,
        "logs": [],           # list of {t, msg, kind}
        "log_cursor": 0,      # WebSocket reads from here
    }

    # Run in a background thread (not async — subprocess is blocking)
    t = threading.Thread(
        target=_run_pipeline_subprocess,
        args=(analysis_id, request.company, request.claim, request.industry),
        daemon=True,
    )
    t.start()

    return {"analysis_id": analysis_id, "status": "started"}


@router.get("/analysis/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """Poll for analysis status and result."""
    if analysis_id not in _analysis_store:
        raise HTTPException(status_code=404, detail="Analysis not found")
    entry = _analysis_store[analysis_id]
    return {
        "analysis_id": analysis_id,
        "status": entry["status"],
        "progress": entry.get("progress", 0),
        "company": entry.get("company"),
        "result": entry.get("result"),
        "error": entry.get("error"),
    }


# ── Log line classifier ──────────────────────────────────────────────────────

def _classify_log(line: str) -> str:
    """Return 'ok', 'warn', 'error', or 'info' based on log content."""
    lower = line.lower()
    if any(k in lower for k in ["✓", "[ok]", "success", "completed", "saved", "generated"]):
        return "ok"
    if any(k in lower for k in ["⚠", "warning", "warn", "fallback", "timeout", "retry"]):
        return "warn"
    if any(k in lower for k in ["error", "failed", "exception", "traceback", "critical"]):
        return "error"
    return "info"


# ── Subprocess runner ─────────────────────────────────────────────────────────

def _run_pipeline_subprocess(
    analysis_id: str,
    company: str,
    claim: str,
    industry: Optional[str],
):
    """
    Runs main_langgraph.py as a subprocess, capturing stdout/stderr
    line-by-line into _analysis_store[analysis_id]["logs"].
    """
    store = _analysis_store[analysis_id]
    start_time = time.time()

    def add_log(msg: str, kind: str = "info"):
        elapsed = time.time() - start_time
        store["logs"].append({
            "t": f"{elapsed:.1f}s",
            "msg": msg,
            "kind": kind,
        })

    add_log("Pipeline starting…", "info")

    command = [
        str(_VENV_PYTHON),
        str(_ANALYSIS_SCRIPT),
        "--company", company,
        "--claim", claim,
    ]
    if industry:
        command.extend(["--industry", industry])

    add_log(f"Command: {' '.join(command)}", "info")

    try:
        proc = subprocess.Popen(
            command,
            cwd=str(_PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge stderr into stdout
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # line-buffered
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )

        # Read stdout line-by-line
        agent_count = 0
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n\r")
            if not line:
                continue

            kind = _classify_log(line)
            add_log(line, kind)

            # Try to detect agent progress from log output
            if "✓" in line or "completed" in line.lower() or "[OK]" in line:
                agent_count += 1
                # Estimate progress (30 agents typical)
                store["progress"] = min(95, int((agent_count / 30) * 95))

        proc.wait()
        elapsed = time.time() - start_time

        if proc.returncode != 0:
            add_log(f"Pipeline exited with code {proc.returncode}", "error")
            store["status"] = "error"
            store["error"] = f"Pipeline exited with code {proc.returncode}"
            return

        add_log(f"Pipeline completed in {elapsed:.1f}s", "ok")

        # ── Load the generated report ─────────────────────────────────
        from api.mappers import map_report_to_schema, _short_id

        reports_dir = Path(os.getenv("ESG_REPORTS_DIR", str(_PROJECT_ROOT / "reports")))
        report_id = analysis_id
        raw_report = None

        if reports_dir.exists():
            # Find most recently modified JSON for this company
            company_key = company.lower().replace(" ", "_")
            candidates = sorted(
                [p for p in reports_dir.glob("*.json")
                 if company_key in p.stem.lower()
                 and "lineage" not in p.stem
                 and "FULL" not in p.stem
                 and "_brief" not in p.stem.lower()
                 and "research_runs" not in p.stem],
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                try:
                    with open(candidates[0], encoding="utf-8") as f:
                        raw_report = json.load(f)
                    report_id = _short_id(str(candidates[0]))
                    add_log(f"Loaded report: {candidates[0].name}", "ok")
                except Exception as e:
                    add_log(f"Failed to parse report JSON: {e}", "warn")

        if raw_report is None:
            store["status"] = "error"
            store["error"] = "Pipeline completed but no report JSON found"
            add_log("No report JSON found on disk", "error")
            return

        api_report = map_report_to_schema(raw_report, report_id)
        api_report.pipeline_duration_seconds = elapsed

        # CRITICAL: Set result BEFORE changing status to avoid race condition
        # where WebSocket reads "completed" status but result is still None
        store["result"] = api_report.model_dump()
        store["status"] = "completed"
        store["progress"] = 100
        add_log("Report mapped and ready", "ok")

    except Exception as e:
        add_log(f"Fatal error: {e}", "error")
        store["status"] = "error"
        store["error"] = str(e)
        import traceback
        store["traceback"] = traceback.format_exc()
