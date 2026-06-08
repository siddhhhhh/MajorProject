"""Probe LLM provider concurrency limits.

Measures: how does total wallclock change as we increase concurrent calls?
If wallclock(N) ≈ wallclock(1), provider parallelizes fully.
If wallclock(N) ≈ N * wallclock(1), provider serializes.

Uses 'sentiment_analysis' agent (light prompt, fast model).
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import concurrent.futures
import asyncio
from core.llm_call import call_llm

def one_call(agent_name: str, prompt: str):
    t0 = time.time()
    try:
        result = asyncio.run(call_llm(agent_name, prompt))
        return time.time() - t0, True, len(result) if result else 0
    except Exception as e:
        return time.time() - t0, False, str(e)[:120]

PROMPT_BASE = "Reply with exactly 'OK' and nothing else."
AGENT = "sentiment_analysis"

print(f"\n{'='*70}")
print("LLM provider concurrency probe — agent =", AGENT)
print(f"{'='*70}")

# Warmup (populate any caches)
print("\nwarmup call...")
dt, ok, _ = one_call(AGENT, PROMPT_BASE + " warmup")
print(f"  warmup: {dt:.2f}s ok={ok}")

for n in [1, 3, 5, 10]:
    print(f"\n--- N={n} concurrent calls ---")
    prompts = [f"{PROMPT_BASE} unique_{n}_{i}_{int(time.time()*1000)}" for i in range(n)]
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        futures = [ex.submit(one_call, AGENT, p) for p in prompts]
        results = [f.result(timeout=60) for f in futures]
    total = time.time() - t0
    per_call_avg = sum(r[0] for r in results) / len(results)
    successes = sum(1 for r in results if r[1])
    print(f"  total wallclock: {total:.2f}s")
    print(f"  per-call avg:    {per_call_avg:.2f}s")
    print(f"  successes:       {successes}/{n}")
    parallelism = (n * per_call_avg) / total if total > 0 else 0
    print(f"  achieved parallelism: {parallelism:.2f}x  (1.0 = serial, N.0 = perfect)")
    for r in results:
        if not r[1]:
            print(f"   ERR: {r[2]}")
