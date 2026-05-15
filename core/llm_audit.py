"""LLM call audit logger.

Every LLM call is logged with model identity + prompt/response hashes so that:
  - Two runs with different LLM keys can be diffed at the step level.
  - Auditors can verify which model produced which judgment.
  - The variance diagnostic harness has structured data to consume.

Writes JSONL to data/llm_audit/{YYYY-MM-DD}.jsonl. Append-only, never read by
the pipeline itself — purely an out-of-band record.
"""

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_AUDIT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "llm_audit"
)
os.makedirs(_AUDIT_DIR, exist_ok=True)

_LOCK = threading.Lock()
_DISABLED = os.getenv("ESG_LLM_AUDIT_DISABLED", "").lower() in ("1", "true", "yes")


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _today_path() -> str:
    return os.path.join(
        _AUDIT_DIR, datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl"
    )


def log_call(
    *,
    agent: str,
    provider: str,
    model_id: str,
    prompt: str,
    response: Optional[str],
    system: Optional[str] = None,
    latency_ms: Optional[float] = None,
    cache_hit: bool = False,
    error: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Append one record to today's audit JSONL.

    Never raises — audit failures must not break the pipeline.
    """
    if _DISABLED:
        return
    try:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "provider": provider,
            "model_id": model_id,
            "prompt_hash": _hash(prompt),
            "system_hash": _hash(system) if system else None,
            "response_hash": _hash(response) if response is not None else None,
            "response_len": len(response) if response else 0,
            "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
            "cache_hit": cache_hit,
            "error": error,
        }
        if extra:
            record.update(extra)
        with _LOCK, open(_today_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_audit_log(date_str: Optional[str] = None) -> list[Dict[str, Any]]:
    """Return all audit records for a given date (UTC). Default: today."""
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(_AUDIT_DIR, f"{date_str}.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def summarize_session(records: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate stats: call counts by (agent, provider, model_id)."""
    by_agent_provider: Dict[tuple, int] = {}
    by_model: Dict[str, int] = {}
    errors = 0
    cache_hits = 0
    total_latency = 0.0
    latency_samples = 0
    for r in records:
        k = (r.get("agent"), r.get("provider"), r.get("model_id"))
        by_agent_provider[k] = by_agent_provider.get(k, 0) + 1
        by_model[r.get("model_id") or "?"] = by_model.get(r.get("model_id") or "?", 0) + 1
        if r.get("error"):
            errors += 1
        if r.get("cache_hit"):
            cache_hits += 1
        lat = r.get("latency_ms")
        if isinstance(lat, (int, float)):
            total_latency += lat
            latency_samples += 1
    return {
        "total_calls": len(records),
        "unique_steps": len({(r.get("agent"), r.get("prompt_hash")) for r in records}),
        "errors": errors,
        "cache_hits": cache_hits,
        "avg_latency_ms": round(total_latency / latency_samples, 1) if latency_samples else None,
        "by_model": by_model,
        "by_agent_provider": {
            f"{a}|{p}|{m}": n for (a, p, m), n in by_agent_provider.items()
        },
    }
