"""Probe Cerebras + Groq concurrent LLM throughput.

Measures: how does total wallclock change as we increase concurrent requests?
If wallclock(N) ≈ wallclock(1), provider parallelizes fully.
If wallclock(N) ≈ N * wallclock(1), provider serializes.
"""
import sys, os, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import concurrent.futures
import asyncio
from core.llm_call import call_llm

def one_call(agent_name, prompt):
    t0 = time.time()
    try:
        result = asyncio.run(call_llm(agent_name, prompt))
        return time.time() - t0, True, len(result)
    except Exception as e:
        return time.time() - t0, False, str(e)[:80]

PROMPT = "Reply with a one-sentence summary of ESG terminology. Max 30 words."

print(f"\n{'='*70}")
print("LLM provider concurrency probe")
print(f"{'='*70}\n")

# Use 'sentiment_analysis' agent which goes through llm_router
AGENT = "sentiment_analysis"

# Warm up cache
print("warmup...")
one_call(AGENT, PROMPT + " WARMUP")

for n in [1, 3, 5, 10]:
    print(f"\n--- Concurrent calls: N={n} ---")
    # Unique prompts to bypass cache
    prompts = [f"{PROMPT} variant_{n}_{i}_{int(time.time()*1000)}" for i in range(n)]
    
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        futures = [ex.submit(one_call, AGENT, p) for p in prompts]
        results = [f.result(timeout=120) for f in futures]
    total = time.time() - t0
    
    per_call_avg = sum(r[0] for r in results) / len(results)
    successes = sum(1 for r in results if r[1])
    
    print(f"  total wallclock: {total:.2f}s")
    print(f"  per-call avg:    {per_call_avg:.2f}s")
    print(f"  successes:       {successes}/{n}")
    print(f"  parallelism:     {n * per_call_avg / total:.2f}x")
    if not all(r[1] for r in results):
        for r in results:
            if not r[1]: print(f"   ERR: {r[2]}")
