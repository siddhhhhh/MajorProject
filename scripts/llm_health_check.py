"""Provider health check for the ESGLens LLM router.

Probes every distinct (provider, model_id) pair referenced in ROUTING_TABLE
with a minimal real call and reports which ones are alive. Run before a demo
or after any provider key/plan change to catch silent retirements before they
shrink fallback chains and concentrate load on a single provider.

Usage:
    venv/Scripts/python.exe scripts/llm_health_check.py
"""

from __future__ import annotations
import asyncio
import os
import sys
import time
from typing import Tuple

# Allow this script to run from repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_router import ROUTING_TABLE, ModelConfig, Provider  # noqa: E402
from core.llm_call import _dispatch  # noqa: E402


PROBE_PROMPT_PLAIN = "Reply with the single word OK and nothing else."
PROBE_PROMPT_JSON = (
    'Return exactly this JSON and nothing else: {"status": "ok"}'
)


def _unique_models() -> list[ModelConfig]:
    """Pick one ModelConfig per (provider, model_id). Prefer the non-json
    variant when both exist so the probe doesn't force JSON on models that
    are only configured for plain text in some chains.
    """
    best: dict[Tuple[Provider, str], ModelConfig] = {}
    for chain in ROUTING_TABLE.values():
        for cfg in chain:
            key = (cfg.provider, cfg.model_id)
            existing = best.get(key)
            if existing is None or (existing.json_mode and not cfg.json_mode):
                best[key] = cfg
    return list(best.values())


async def _probe_one(cfg: ModelConfig) -> dict:
    t0 = time.perf_counter()
    prompt = PROBE_PROMPT_JSON if cfg.json_mode else PROBE_PROMPT_PLAIN
    try:
        text = await _dispatch(cfg, prompt, system=None, pdf_bytes=None)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "provider": cfg.provider.value,
            "model_id": cfg.model_id,
            "status": "OK",
            "latency_ms": round(latency_ms, 1),
            "preview": (text or "")[:80].replace("\n", " "),
            "error": None,
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "provider": cfg.provider.value,
            "model_id": cfg.model_id,
            "status": "FAIL",
            "latency_ms": round(latency_ms, 1),
            "preview": None,
            "error": str(e)[:200],
        }


async def run() -> int:
    models = _unique_models()
    print(f"Probing {len(models)} distinct provider/model pairs...\n")

    # Serialize per-provider to avoid self-imposed rate limits during probe.
    results: list[dict] = []
    for cfg in models:
        r = await _probe_one(cfg)
        results.append(r)
        marker = "✓" if r["status"] == "OK" else "✗"
        print(f"  {marker} {r['provider']:11s} {r['model_id']:50s} "
              f"{r['status']:4s}  {r['latency_ms']:>7.1f}ms")
        if r["status"] == "FAIL":
            print(f"        └─ {r['error']}")

    # Chain-level summary: which agents have how many live fallbacks?
    # Keys use the enum's .value (string) since chain comparisons render the
    # same way; matching on the raw Provider enum would always miss.
    alive = {(r["provider"], r["model_id"]) for r in results if r["status"] == "OK"}
    def _is_alive(cfg: ModelConfig) -> bool:
        return (cfg.provider.value, cfg.model_id) in alive
    print("\nChain coverage (live providers per agent):")
    print(f"  {'agent':35s} {'live':>5s}/{'total':<5s}  {'status':10s}")
    print(f"  {'-'*35} {'-'*5} {'-'*5}  {'-'*10}")
    degraded = []
    for agent, chain in ROUTING_TABLE.items():
        n_total = len(chain)
        n_live = sum(1 for c in chain if _is_alive(c))
        status = "OK" if n_live == n_total else ("DEGRADED" if n_live > 0 else "DEAD")
        print(f"  {agent:35s} {n_live:>5d}/{n_total:<5d}  {status:10s}")
        if status != "OK":
            degraded.append((agent, n_live, n_total))

    print()
    n_ok = sum(1 for r in results if r["status"] == "OK")
    print(f"Provider summary: {n_ok}/{len(results)} live model endpoints")
    if degraded:
        print(f"Degraded chains: {len(degraded)}")
        for agent, n_live, n_total in degraded:
            print(f"  - {agent}: {n_live}/{n_total} live")
        # exit non-zero only if any chain is fully dead
        any_dead = any(n_live == 0 for _, n_live, _ in degraded)
        return 2 if any_dead else 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
