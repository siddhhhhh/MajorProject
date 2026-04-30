"""
api/pipeline_ws.py
------------------
WebSocket /ws/pipeline/{analysis_id}
Streams real-time pipeline logs + status to the frontend.

Message types sent to the client:
  { "type": "log",       "t": "3.2s", "msg": "...", "kind": "ok|warn|error|info" }
  { "type": "progress",  "progress_pct": 0-100, "elapsed_seconds": float }
  { "type": "complete",  "analysis_id": "...", "report": {...} }
  { "type": "error",     "message": "..." }
  { "type": "heartbeat" }
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.analysis import _analysis_store

router = APIRouter()

_POLL_INTERVAL = 0.5        # check for new logs every 500ms
_HEARTBEAT_EVERY = 5.0


async def _send(ws: WebSocket, payload: Dict[str, Any]):
    try:
        await ws.send_text(json.dumps(payload, default=str))
    except Exception:
        pass


@router.websocket("/ws/pipeline/{analysis_id}")
async def pipeline_websocket(websocket: WebSocket, analysis_id: str):
    await websocket.accept()

    # Wait for the analysis to appear
    deadline = time.time() + 10
    while analysis_id not in _analysis_store and time.time() < deadline:
        await asyncio.sleep(0.3)

    if analysis_id not in _analysis_store:
        await _send(websocket, {"type": "error", "message": "Analysis not found"})
        await websocket.close()
        return

    start_time = time.time()
    last_heartbeat = start_time
    log_cursor = 0  # index into store["logs"] — send only new lines

    try:
        while True:
            now = time.time()
            elapsed = now - start_time
            entry = _analysis_store.get(analysis_id, {})
            status = entry.get("status", "running")
            logs = entry.get("logs", [])
            progress = entry.get("progress", 0)

            # ── Send any new log lines ────────────────────────────────
            if log_cursor < len(logs):
                new_logs = logs[log_cursor:]
                for log_entry in new_logs:
                    await _send(websocket, {
                        "type": "log",
                        "t": log_entry.get("t", ""),
                        "msg": log_entry.get("msg", ""),
                        "kind": log_entry.get("kind", "info"),
                    })
                log_cursor = len(logs)

            # ── Send progress update ──────────────────────────────────
            await _send(websocket, {
                "type": "progress",
                "progress_pct": progress,
                "elapsed_seconds": elapsed,
            })

            # ── Completed ─────────────────────────────────────────────
            if status == "completed":
                result = entry.get("result")
                # Safety check: ensure result is not None/empty before sending
                if result:
                    await _send(websocket, {
                        "type": "complete",
                        "analysis_id": analysis_id,
                        "report": result,
                    })
                    break

            # ── Error ─────────────────────────────────────────────────
            if status == "error":
                await _send(websocket, {
                    "type": "error",
                    "message": entry.get("error", "Pipeline failed"),
                })
                break

            # ── Heartbeat ─────────────────────────────────────────────
            if now - last_heartbeat >= _HEARTBEAT_EVERY:
                await _send(websocket, {"type": "heartbeat", "elapsed_seconds": elapsed})
                last_heartbeat = now

            await asyncio.sleep(_POLL_INTERVAL)

    except WebSocketDisconnect:
        pass
    except Exception:
        await _send(websocket, {"type": "error", "message": "Internal streaming error"})
