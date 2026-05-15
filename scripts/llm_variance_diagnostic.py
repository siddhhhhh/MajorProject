"""LLM variance diagnostic harness.

Quantifies how much the final ESG/GW score depends on which LLM provider is
used. The premise behind the system's design — that LLMs do extraction and
classification, and deterministic code does scoring — implies inter-LLM
variance should be small. This script measures that claim.

How it works
------------
1. Pick a small set of representative LLM-touched steps (claim classification,
   contradiction analysis, greenwashing detection, etc.).
2. For each step, run the SAME prompt three times — once forced through each
   primary provider in the routing table (Groq, Gemini, Cerebras / OpenRouter).
3. Hash every response. If providers produce byte-identical hashes -> variance
   is zero for that step. If they diverge -> record the divergence.
4. For numeric outputs (scores, counts) parse the JSON and compute pairwise
   numeric deltas.
5. Aggregate: report (a) hash-agreement rate, (b) numeric variance bounds,
   (c) projected impact on the final GW score using the bucket-model weights.

Usage
-----
    python scripts/llm_variance_diagnostic.py
    python scripts/llm_variance_diagnostic.py --suite minimal
    python scripts/llm_variance_diagnostic.py --output data/variance_reports/run1.json

Produces ./data/variance_reports/{timestamp}_variance.json and prints a
human-readable summary table.

Cost note: each suite is ~6-10 LLM calls x 3 providers = ~20-30 calls total.
Free-tier safe.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Make the project root importable when run as a script.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.llm_router import (
    ROUTING_TABLE,
    Provider,
    ModelConfig,
    set_routing_override,
)
from core.llm_call import call_llm
from core.llm_audit import read_audit_log, summarize_session


# -----------------------------------------------------------
# Test suite: representative LLM-touched prompts with realistic
# inputs drawn from the kinds of evidence the pipeline sees.
# -----------------------------------------------------------
@dataclass
class Probe:
    name: str           # human label
    agent: str          # routing-table key
    prompt: str
    system: Optional[str] = None
    parse_field: Optional[str] = None  # field to extract for numeric diff
    expected_kind: str = "categorical"  # "categorical" | "numeric" | "text"


# Probe selection note: routing chains differ per agent. Each probe's `agent`
# field must map to a chain that contains the providers being tested. We pick
# agents where Groq AND Cerebras are both present (most reliable 2-provider
# comparison; Gemini free-tier rate limits make Gemini probes brittle).

SUITE_MINIMAL: List[Probe] = [
    Probe(
        name="claim_classification_net_zero",
        agent="claim_extractor",  # Cerebras + Groq + OR
        prompt=(
            "Classify this corporate ESG claim. Return JSON only:\n"
            '{"claim_type": "NET_ZERO|REDUCTION|OFFSET|RENEWABLE|OTHER", '
            '"target_year": <int|null>, "is_quantified": <bool>}\n\n'
            "Claim: \"Vedanta has committed to achieving net-zero carbon "
            "emissions by 2050 or sooner across Scope 1 and Scope 2, with "
            "a USD 5 billion investment over the next 10 years.\""
        ),
        parse_field="target_year",
        expected_kind="categorical",
    ),
    Probe(
        name="sentiment_microsoft",
        agent="sentiment_analysis",  # Groq + Cerebras + OR
        prompt=(
            "Rate sentiment toward the company. Return JSON only: "
            '{"sentiment": "POSITIVE|NEUTRAL|NEGATIVE", "confidence": <0-1>}\n\n'
            "Text: \"Microsoft announced 100% renewable electricity by 2025 "
            "and reported a 6% drop in operational carbon, though Scope 3 "
            "emissions grew 30% year-over-year due to data-center expansion.\""
        ),
        parse_field="sentiment",
        expected_kind="categorical",
    ),
    Probe(
        name="credibility_evidence",
        agent="credibility_analysis",  # Cerebras + Groq + OR (called ~47x/report)
        prompt=(
            "Rate evidence credibility 1-5. Return JSON only: "
            '{"credibility": <1-5>, "reason": "..."}\n\n'
            "Evidence: \"Per the company's 2025 sustainability report (PwC "
            "assured), Scope 1 emissions decreased 12% YoY. Reuters reported "
            "the same figure based on the audited filing.\""
        ),
        parse_field="credibility",
        expected_kind="numeric",
    ),
    Probe(
        name="climatebert_classification",
        agent="climatebert_analysis",  # Groq + Cerebras + OR
        prompt=(
            "Classify the climate-disclosure type. Return JSON only: "
            '{"category": "TARGET|ACHIEVEMENT|RISK|OPPORTUNITY|GOVERNANCE", '
            '"specificity": "QUANTIFIED|QUALITATIVE"}\n\n'
            "Text: \"We aim to reduce absolute Scope 1+2 emissions by 50% by "
            "2030 from a 2019 baseline, validated by SBTi against a 1.5C "
            "pathway.\""
        ),
        parse_field="category",
        expected_kind="categorical",
    ),
    Probe(
        name="esg_mismatch_check",
        agent="esg_mismatch",  # Groq + Cerebras + OR
        prompt=(
            "Does the claim match the evidence? Return JSON only: "
            '{"match": <bool>, "mismatch_type": "NONE|EXAGGERATION|CONTRADICTION|MISSING"}\n\n'
            "Claim: \"We are a net-zero company today.\"\n"
            "Evidence: \"FY2024 Scope 1 emissions: 1.2M tCO2e (not offset). "
            "No removal contracts in place.\""
        ),
        parse_field="mismatch_type",
        expected_kind="categorical",
    ),
    Probe(
        name="temporal_consistency_target",
        agent="temporal_consistency",  # Groq + Cerebras + OR
        prompt=(
            "Are these two statements temporally consistent? Return JSON only: "
            '{"consistent": <bool>, "issue": "..."}\n\n'
            "2020 statement: \"We commit to a 50% Scope 1 reduction by 2030.\"\n"
            "2024 statement: \"We commit to a 30% Scope 1 reduction by 2030.\""
        ),
        parse_field="consistent",
        expected_kind="categorical",
    ),
    Probe(
        name="promise_extraction_jpm",
        agent="promise_extraction",  # Groq + OR + Cerebras
        prompt=(
            "Extract sustainability promises from this text. Return JSON only: "
            '{"promises": [{"text": "...", "target_year": <int|null>, '
            '"quantified": <bool>}]}\n\n'
            "Text: \"By 2030, we will achieve carbon-neutral operations, "
            "reduce financed-emissions intensity 25%, and align $1T in "
            "sustainable finance.\""
        ),
        parse_field="promises",
        expected_kind="categorical",  # list-equality
    ),
    Probe(
        name="confidence_score_basic",
        agent="confidence_scoring",  # Cerebras + Groq + OR
        prompt=(
            "Score confidence in this assessment 0-100. Return JSON only: "
            '{"confidence": <0-100>}\n\n'
            "Assessment: \"Greenwashing detected with 2 SBTi-validated "
            "targets, 1 audited disclosure, 3 corroborating news sources.\""
        ),
        parse_field="confidence",
        expected_kind="numeric",
    ),
]


# Gemini suite — smaller, paced, for users who want Gemini-vs-Groq variance
SUITE_GEMINI: List[Probe] = [
    Probe(
        name="contradiction_count_vw",
        agent="contradiction_analysis",  # Groq + OR + Gemini
        prompt=(
            "Two pieces of evidence about the same company:\n"
            "A: \"Volkswagen plans to be carbon-neutral by 2050.\"\n"
            "B: \"Volkswagen subsidiary Audi paid a $926M settlement related "
            "to Dieselgate emissions cheating in 2023.\"\n\n"
            "Return JSON only: "
            '{"contradiction": <bool>, "severity": "CRITICAL|HIGH|MEDIUM|LOW|NONE", '
            '"explanation": "..."}'
        ),
        parse_field="severity",
        expected_kind="categorical",
    ),
    Probe(
        name="greenwashing_score_jpm",
        agent="greenwishing_detection",  # Groq + OR + Gemini
        prompt=(
            "Assess greenwashing risk for this disclosure. Return JSON only:\n"
            '{"risk_score": <0-100>, "label": "LOW|MODERATE|HIGH", '
            '"top_signals": ["..."]}\n\n'
            "Disclosure: \"JPMorgan Chase committed to align its financing "
            "activities with net-zero by 2050. The bank is the largest "
            "fossil-fuel financier ($430B since 2016 per Banking on Climate "
            "Chaos). NZBA membership withdrawn in 2025.\""
        ),
        parse_field="risk_score",
        expected_kind="numeric",
    ),
    Probe(
        name="carbon_extraction_vedanta",
        agent="carbon_extraction",  # Gemini + Groq + OR
        prompt=(
            "Extract Scope 1, 2, 3 emissions in tCO2e from this text. "
            "Return JSON only: "
            '{"scope1": <int|null>, "scope2": <int|null>, "scope3": <int|null>, '
            '"year": <int>, "unit_in_source": "..."}\n\n'
            "Text: \"In FY2025, our total Scope 1 emissions were "
            "63,324 ktCO2e, Scope 2 (market-based) was 3,594 ktCO2e, and "
            "Scope 3 emissions stood at 45,802 ktCO2e.\""
        ),
        parse_field="scope1",
        expected_kind="numeric",
    ),
]


SUITES = {"minimal": SUITE_MINIMAL, "gemini": SUITE_GEMINI}


# -----------------------------------------------------------
# Run helpers
# -----------------------------------------------------------
@dataclass
class ProbeResult:
    probe_name: str
    provider: str
    model_id: str
    raw_response: str
    response_hash: str
    parsed_value: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0


def _hash16(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(
            l for l in cleaned.split("\n") if not l.strip().startswith("```")
        ).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to grab the first { ... } block.
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _extract_field(parsed: Any, field_path: str) -> Any:
    if not isinstance(parsed, dict) or not field_path:
        return None
    return parsed.get(field_path)


async def _run_probe_with_provider(
    probe: Probe, provider: Provider
) -> ProbeResult:
    """Force `probe` through the given provider, capture response."""
    # Find a ModelConfig in this agent's chain that matches the provider.
    chain = ROUTING_TABLE.get(probe.agent, [])
    forced_config = next((c for c in chain if c.provider == provider), None)
    if forced_config is None:
        return ProbeResult(
            probe_name=probe.name,
            provider=provider.value,
            model_id="(none in chain)",
            raw_response="",
            response_hash="",
            error=f"No {provider.value} entry in agent='{probe.agent}' chain",
        )

    # Install a per-agent override forcing this single config.
    set_routing_override({probe.agent: [forced_config]})
    t0 = time.perf_counter()
    try:
        response = await call_llm(
            agent=probe.agent,
            prompt=probe.prompt,
            system=probe.system,
            use_cache=False,  # always hit live so we measure real variance
        )
        elapsed = (time.perf_counter() - t0) * 1000.0
        parsed = _safe_parse_json(response)
        value = _extract_field(parsed, probe.parse_field) if probe.parse_field else None
        return ProbeResult(
            probe_name=probe.name,
            provider=provider.value,
            model_id=forced_config.model_id,
            raw_response=response,
            response_hash=_hash16(response),
            parsed_value=value,
            latency_ms=elapsed,
        )
    except Exception as e:
        return ProbeResult(
            probe_name=probe.name,
            provider=provider.value,
            model_id=forced_config.model_id,
            raw_response="",
            response_hash="",
            error=str(e)[:200],
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
    finally:
        set_routing_override(None)


# -----------------------------------------------------------
# Aggregation
# -----------------------------------------------------------
def _numeric(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.replace(",", ""))
        except ValueError:
            return None
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    return None


def aggregate(results: List[ProbeResult], probes: List[Probe]) -> Dict[str, Any]:
    """Compute per-probe agreement metrics and a top-line summary."""
    by_probe: Dict[str, List[ProbeResult]] = {}
    for r in results:
        by_probe.setdefault(r.probe_name, []).append(r)

    per_probe_rows = []
    hash_agreements = []
    categorical_agreements = []
    numeric_deltas = []

    for probe in probes:
        rs = [r for r in by_probe.get(probe.name, []) if not r.error]
        if len(rs) < 2:
            per_probe_rows.append({
                "probe": probe.name,
                "kind": probe.expected_kind,
                "status": "insufficient_responses",
                "n_providers": len(rs),
            })
            continue

        # Hash agreement
        hashes = [r.response_hash for r in rs]
        all_hash_match = len(set(hashes)) == 1
        hash_agreements.append(1.0 if all_hash_match else 0.0)

        # Parsed-value agreement
        values = [r.parsed_value for r in rs]
        unique_values = {json.dumps(v, sort_keys=True, default=str) for v in values}
        value_agreement = len(unique_values) == 1

        row: Dict[str, Any] = {
            "probe": probe.name,
            "kind": probe.expected_kind,
            "n_providers": len(rs),
            "hash_identical": all_hash_match,
            "parsed_values": {r.provider: r.parsed_value for r in rs},
            "value_agreement": value_agreement,
            "model_ids": {r.provider: r.model_id for r in rs},
        }

        if probe.expected_kind == "numeric":
            nums = [_numeric(v) for v in values]
            nums = [n for n in nums if n is not None]
            if len(nums) >= 2:
                lo, hi = min(nums), max(nums)
                spread = hi - lo
                mean = sum(nums) / len(nums)
                row.update({
                    "numeric_min": lo,
                    "numeric_max": hi,
                    "numeric_spread": spread,
                    "numeric_mean": mean,
                    "numeric_rel_spread_pct": (spread / mean * 100.0) if mean else None,
                })
                numeric_deltas.append(spread)
        else:
            categorical_agreements.append(1.0 if value_agreement else 0.0)

        per_probe_rows.append(row)

    summary = {
        "hash_agreement_rate": (
            round(sum(hash_agreements) / len(hash_agreements), 3)
            if hash_agreements else None
        ),
        "categorical_value_agreement_rate": (
            round(sum(categorical_agreements) / len(categorical_agreements), 3)
            if categorical_agreements else None
        ),
        "numeric_avg_spread": (
            round(sum(numeric_deltas) / len(numeric_deltas), 2)
            if numeric_deltas else None
        ),
        "numeric_max_spread": round(max(numeric_deltas), 2) if numeric_deltas else None,
        "n_probes": len(probes),
        "n_results": len(results),
    }
    return {"summary": summary, "per_probe": per_probe_rows}


# -----------------------------------------------------------
# Projected GW impact (rough upper bound)
# -----------------------------------------------------------
def project_gw_impact(per_probe: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rough upper bound on how much LLM disagreement could shift the final
    GW score. Maps each probe's variance to a score-weight component using
    the bucket-model multipliers (40/30/20/10) and per-contradiction weights.

    Counts a probe as "diverged" only when the *parsed value* differs across
    providers — byte-level hash differences in prose are ignored, since the
    scoring layer reads structured fields, not raw text.
    """
    # Per-probe contribution multipliers (rough; calibrated to bucket model).
    weights = {
        "claim_classification_net_zero": 5.0,          # affects formula gap_C
        "contradiction_count_vw": 20.0,                # 20 points per CRITICAL contradiction
        "greenwashing_score_jpm": 0.3,                 # 30% weight into current_contradictions
        "carbon_extraction_vedanta": 0.07,             # 7 points per material reggap
        "sentiment_microsoft": 2.0,                    # historical_trust bucket
        "regulatory_compliance_brsr": 7.0,             # one reggap = 7 GW points
        "credibility_evidence": 3.0,                   # credibility weights evidence in formula
        "climatebert_classification": 4.0,             # claim category drives gap_C
        "esg_mismatch_check": 8.0,                     # mismatch flips contradiction bucket
        "temporal_consistency_target": 6.0,            # target drift counts as contradiction
        "promise_extraction_jpm": 5.0,                 # promise set drives gap_R
        "confidence_score_basic": 0.2,                 # confidence is a multiplier
    }
    impact = 0.0
    contributions = []
    insufficient = []
    for row in per_probe:
        name = row.get("probe")
        # Skip probes that didn't get >=2 successful provider responses.
        if row.get("status") == "insufficient_responses" or row.get("n_providers", 0) < 2:
            insufficient.append(name)
            continue
        w = weights.get(name, 1.0)
        diverged = not row.get("value_agreement", True)
        if diverged:
            if row.get("kind") == "numeric":
                spread = row.get("numeric_spread") or 0.0
                contribution = spread * w
            else:
                contribution = w  # full per-step weight for categorical flip
            impact += contribution
            contributions.append({"probe": name, "contribution_gw_points": round(contribution, 2)})
    return {
        "projected_gw_upper_bound_points": round(impact, 2),
        "contributions": contributions,
        "insufficient_probes": insufficient,
        "method": (
            "Upper bound. Each diverging probe contributes its full GW weight; "
            "in practice the bucket model's averaging and capping reduces this. "
            "Probes with <2 successful provider responses are excluded as "
            "'insufficient data' rather than treated as agreement."
        ),
    }


# -----------------------------------------------------------
# Main
# -----------------------------------------------------------
async def run_suite(suite_name: str, providers: List[Provider]) -> Dict[str, Any]:
    probes = SUITES[suite_name]
    print(
        f"\nRunning suite='{suite_name}' "
        f"({len(probes)} probes x {len(providers)} providers = "
        f"{len(probes) * len(providers)} calls)\n"
    )
    results: List[ProbeResult] = []
    # Pace by-provider to dodge free-tier rate limits — Gemini in particular
    # caps free-tier RPM aggressively.
    pacing_secs = {Provider.GEMINI: 4.0, Provider.GROQ: 0.5, Provider.CEREBRAS: 0.5}
    for probe in probes:
        for provider in providers:
            print(f"  [{probe.name}] -> {provider.value} ...", end="", flush=True)
            r = await _run_probe_with_provider(probe, provider)
            results.append(r)
            tag = "ERR" if r.error else f"hash={r.response_hash[:8]}"
            print(f"  {tag}  ({r.latency_ms:.0f}ms)")
            await asyncio.sleep(pacing_secs.get(provider, 0.5))

    agg = aggregate(results, probes)
    impact = project_gw_impact(agg["per_probe"])
    return {
        "suite": suite_name,
        "providers": [p.value for p in providers],
        "results": [asdict(r) for r in results],
        "aggregate": agg,
        "projected_gw_impact": impact,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def print_report(report: Dict[str, Any]) -> None:
    agg = report["aggregate"]
    summ = agg["summary"]
    print("\n" + "=" * 70)
    print("LLM VARIANCE DIAGNOSTIC — SUMMARY")
    print("=" * 70)
    print(f"  Providers tested:           {', '.join(report['providers'])}")
    print(f"  Probes executed:            {summ['n_probes']}")
    print(f"  Total LLM calls:            {summ['n_results']}")
    print(
        f"  Byte-identical hash rate:   "
        f"{(summ.get('hash_agreement_rate') or 0) * 100:.1f}%   "
        "(any byte differs across providers -> counted as disagreement)"
    )
    print(
        f"  Categorical agreement rate: "
        f"{(summ.get('categorical_value_agreement_rate') or 0) * 100:.1f}%   "
        "(parsed enum/label match)"
    )
    if summ.get("numeric_avg_spread") is not None:
        print(
            f"  Numeric avg spread:         {summ['numeric_avg_spread']}   "
            f"(max {summ.get('numeric_max_spread')})"
        )
    print()
    print("  PROJECTED GW-SCORE VARIANCE (worst-case upper bound):")
    print(
        f"    +/-{report['projected_gw_impact']['projected_gw_upper_bound_points']:.2f} "
        "GW points across providers"
    )
    print("\n  Per-probe detail:")
    for row in agg["per_probe"]:
        kind = row.get("kind", "")
        n_ok = row.get("n_providers", 0)
        vals = row.get("parsed_values", {})
        if row.get("status") == "insufficient_responses" or n_ok < 2:
            flag = " NO-DATA"
        elif not row.get("value_agreement", True):
            flag = "DIVERGE "
        else:
            flag = "  AGREE "
        line = f"   {flag} [{kind:>11}] {row['probe']:<40} -> {vals}"
        print(line)
    insufficient = report.get("projected_gw_impact", {}).get("insufficient_probes", [])
    if insufficient:
        print(
            f"\n  NOTE: {len(insufficient)} probe(s) excluded from variance "
            f"calculation due to <2 successful provider responses (rate limits "
            f"or missing model in chain): {', '.join(insufficient)}"
        )
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="minimal", choices=list(SUITES.keys()))
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["groq", "gemini", "cerebras", "openrouter"],
        help="Which providers to compare. Defaults to all four.",
    )
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    name_to_provider = {p.value: p for p in Provider}
    providers = [name_to_provider[n] for n in args.providers if n in name_to_provider]
    if len(providers) < 2:
        print("Need at least 2 providers to measure variance.")
        sys.exit(1)

    report = asyncio.run(run_suite(args.suite, providers))
    print_report(report)

    out_dir = os.path.join(ROOT, "data", "variance_reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = args.output or os.path.join(
        out_dir,
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_variance.json",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report saved to: {out_path}")


if __name__ == "__main__":
    main()
