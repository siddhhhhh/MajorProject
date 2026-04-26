"""
Replay-only report regeneration.

Reads a previously generated JSON report (and the cached evidence file) and
re-runs ONLY the report generator with the latest code. Avoids every LLM
call, web search, and external API hit so the API quotas aren't burned.

Usage:
    python scripts/replay_report.py reports/ESG_Report_JPMorgan_Chase_20260426_133328.json

The script:
  1. Loads the previous JSON output
  2. Reconstructs a minimal `state` dict with agent_outputs, evidence,
     contradictions, regulatory data, carbon, etc.
  3. Optionally pulls in the cached evidence file from cache/evidence/
  4. Calls professional_report_generation_node(state) to render fresh
     TXT + JSON using the current (fixed) report generator code.
  5. Writes the new report to reports/ with a fresh timestamp.

Notes:
  - Risk level / rating are restored from the risk_scoring agent's canonical
    `risklevel` / `ratinggrade` keys, bypassing any prior post-override that
    may have flipped HIGH→LOW. (The verdict_generation override has been
    fixed in agent_wrappers.py but doesn't run on replay; this script
    reconstructs the correct upstream value.)
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Force UTF-8 stdout/stderr on Windows so unicode arrows in print statements
# don't crash the run mid-flight.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load env so settings.py/LLM_router (imported transitively) doesn't fail.
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass


def _slugify_company(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in (name or "").lower()).strip("_")


def _find_evidence_cache(company: str) -> dict | None:
    """Best-effort: return the largest cached evidence file for this company."""
    slug = _slugify_company(company)
    cache_dir = REPO_ROOT / "cache" / "evidence"
    if not cache_dir.exists():
        return None
    candidates = sorted(
        [p for p in cache_dir.glob(f"{slug}_*.json") if p.is_file()],
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not candidates:
        return None
    try:
        with candidates[0].open(encoding="utf-8") as f:
            data = json.load(f)
        print(f"[replay] Loaded evidence cache: {candidates[0].name} ({candidates[0].stat().st_size:,} bytes)")
        if isinstance(data, dict) and isinstance(data.get("evidence"), list):
            return data
        if isinstance(data, list):
            return {"evidence": data}
        return {"evidence": []}
    except Exception as exc:
        print(f"[replay] WARN: could not load evidence cache: {exc}")
        return None


def reconstruct_state_from_json(prev_json_path: Path) -> dict:
    with prev_json_path.open() as f:
        prev = json.load(f)

    company = prev.get("company") or "Unknown"
    industry = prev.get("industry") or "Unknown"
    claim = prev.get("claim_analyzed") or "No claim provided"

    # ── Reconstruct agent_outputs from agent_results ─────────────────────
    # The prev JSON's agent_results have:
    #   {"agent": ..., "status": "SUCCESS"/"FAILED"/"NO_DATA",
    #    "confidence": float, "key_findings": {...}}
    # The runtime state expects agent_outputs[] entries with:
    #   {"agent": ..., "output": {...}, "confidence": float, "timestamp": ...}
    agent_outputs = []
    for ar in prev.get("agent_results", []) or []:
        if not isinstance(ar, dict):
            continue
        agent_outputs.append({
            "agent": ar.get("agent"),
            "output": ar.get("key_findings") or {},
            "confidence": ar.get("confidence"),
            "status": ar.get("status"),
            "timestamp": prev.get("analysis_date"),
        })

    # ── Pull risklevel/ratinggrade from the risk_scoring agent KF ────────
    # This bypasses the legacy verdict_generation override that flipped
    # values; we use the canonical scorer output as the truth.
    risk_scoring_kf = {}
    for ar in prev.get("agent_results", []) or []:
        if isinstance(ar, dict) and ar.get("agent") == "risk_scoring":
            risk_scoring_kf = ar.get("key_findings") or {}
            break

    canonical_risk_level = (
        risk_scoring_kf.get("risklevel")
        or risk_scoring_kf.get("risk_level")
        or prev.get("scores", {}).get("risk_level")
        or "MODERATE"
    )
    canonical_rating = (
        risk_scoring_kf.get("ratinggrade")
        or risk_scoring_kf.get("rating_grade")
        or prev.get("scores", {}).get("esg_rating")
        or "BBB"
    )

    # ── Evidence: prefer cached evidence, fall back to evidence_records ──
    evidence_cache = _find_evidence_cache(company) or {}
    evidence = evidence_cache.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        # Build evidence list from the previous JSON's evidence_records
        evidence = []
        for er in prev.get("evidence_records", []) or []:
            if isinstance(er, dict):
                evidence.append({
                    "source_name": er.get("source_name"),
                    "source": er.get("source") or er.get("source_name"),
                    "url": er.get("url"),
                    "title": er.get("title"),
                    "snippet": er.get("snippet"),
                    "text": er.get("snippet"),
                    "relationship_to_claim": er.get("relationship_to_claim"),
                    "claim_support": er.get("relationship_to_claim"),
                    "reliability_tier": er.get("reliability_tier"),
                    "date": er.get("date"),
                    "verifiable": True,
                })

    # ── Build contradiction_results from prev contradictions ─────────────
    contradiction_results = {
        "contradictions_found": len(prev.get("contradictions", []) or []),
        "specific_contradictions": prev.get("contradictions", []) or [],
        "contradictions": prev.get("contradictions", []) or [],
        "confidence": 0.85,
    }

    # ── Build regulatory_compliance ──────────────────────────────────────
    regulatory_compliance = {}
    for ar in prev.get("agent_results", []) or []:
        if isinstance(ar, dict) and ar.get("agent") == "regulatory_scanning":
            regulatory_compliance = ar.get("key_findings") or {}
            break

    # ── Build carbon block ───────────────────────────────────────────────
    carbon_kf = {}
    for ar in prev.get("agent_results", []) or []:
        if isinstance(ar, dict) and ar.get("agent") == "carbon_extraction":
            carbon_kf = ar.get("key_findings") or {}
            break
    carbon = carbon_kf or {
        "emissions": {
            "scope1": {"value": prev.get("carbon_data", {}).get("scope1")},
            "scope2": {"value": prev.get("carbon_data", {}).get("scope2")},
            "scope3": {"total": prev.get("carbon_data", {}).get("scope3")},
        },
        "data_quality": {"overall_score": prev.get("carbon_data", {}).get("data_quality")},
    }

    # ── Pull adversarial_audit ──────────────────────────────────────────
    adversarial_audit = prev.get("scores", {}).get("adversarial_audit") or {}

    # ── Riskresults (some report code reads this) ───────────────────────
    riskresults = dict(risk_scoring_kf) if risk_scoring_kf else {}

    # ── Build a name→key_findings map so we can populate state-level
    #    fields that the renderer reads directly (not via agent_outputs)
    _kf_by_agent = {}
    for ar in prev.get("agent_results", []) or []:
        if isinstance(ar, dict) and ar.get("agent"):
            _kf_by_agent[ar["agent"]] = ar.get("key_findings") or {}

    claim_decomposition = _kf_by_agent.get("claim_decomposition", {})
    carbon_pathway = (
        _kf_by_agent.get("carbon_pathway_analysis")
        or _kf_by_agent.get("carbon_pathway")
        or {}
    )
    greenwishing_analysis = (
        _kf_by_agent.get("greenwishing_detection")
        or _kf_by_agent.get("greenwishing_analysis")
        or {}
    )
    climatebert_analysis = _kf_by_agent.get("climatebert_analysis", {})
    sentiment_analysis = _kf_by_agent.get("sentiment_analysis", {})
    temporal_analysis = _kf_by_agent.get("temporal_analysis", {}) or _kf_by_agent.get("temporal_consistency", {})
    historical_analysis = _kf_by_agent.get("historical_analysis", {}) or temporal_analysis
    credibility_analysis = _kf_by_agent.get("credibility_analysis", {})

    # ── Final state assembly ─────────────────────────────────────────────
    state = {
        "company": company,
        "industry": industry,
        "claim": claim,
        "evidence": evidence,
        "agent_outputs": agent_outputs,
        "contradictions": prev.get("contradictions", []) or [],
        "contradiction_results": contradiction_results,
        "regulatory_compliance": regulatory_compliance,
        "carbon": carbon,
        "carbon_results": carbon,
        "adversarial_audit": adversarial_audit,
        "esg_mismatch_analysis": prev.get("esg_mismatch_analysis", {}),
        "external_esg_data": prev.get("external_benchmarks", {}),
        "riskresults": riskresults,
        "risk_level": canonical_risk_level,
        "rating_grade": canonical_rating,
        "confidence": prev.get("scores", {}).get("confidence", 0.7),
        "verdict_locked": False,
        "node_execution_order": [
            ar.get("agent") for ar in (prev.get("agent_results", []) or []) if isinstance(ar, dict)
        ],
        "fact_graph": {},
        "ticker": "JPM" if company == "JPMorgan Chase" else None,
        "report_generation_log": prev.get("report_generation_log", {}),
        # State-level fields the renderer reads directly (not via agent_outputs)
        "claim_decomposition": claim_decomposition,
        "carbon_pathway_analysis": carbon_pathway,
        "greenwishing_analysis": greenwishing_analysis,
        "climatebert_analysis": climatebert_analysis,
        "sentiment_analysis": sentiment_analysis,
        "temporal_analysis": temporal_analysis,
        "temporal_consistency": temporal_analysis,
        "historical_analysis": historical_analysis,
        "credibility_analysis": credibility_analysis,
    }

    print(f"[replay] State reconstructed:")
    print(f"  company={company}  industry={industry}")
    print(f"  agent_outputs={len(agent_outputs)}  evidence={len(evidence)}")
    print(f"  contradictions={len(state['contradictions'])}")
    print(f"  canonical risk_level={canonical_risk_level}  rating={canonical_rating}")
    return state


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    prev_json = Path(sys.argv[1]).resolve()
    if not prev_json.exists():
        print(f"ERROR: file not found: {prev_json}")
        sys.exit(1)

    print(f"[replay] Loading: {prev_json}")
    state = reconstruct_state_from_json(prev_json)

    print(f"[replay] Importing report node ...")
    from core.professional_report_generator import professional_report_generation_node

    print(f"[replay] Running report node (no LLM/web calls) ...")
    state = professional_report_generation_node(state)

    txt_report = state.get("report") or ""
    json_export_path = state.get("json_export_path")

    # Save TXT report under reports/ with fresh timestamp
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    company_slug = (state.get("company") or "company").replace(" ", "_")
    txt_path = REPO_ROOT / "reports" / f"ESG_Report_{company_slug}_{ts}_REPLAY.txt"
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(txt_report, encoding="utf-8")

    print()
    print(f"[replay] DONE.")
    print(f"  TXT report   : {txt_path}  ({txt_path.stat().st_size:,} bytes)")
    if json_export_path:
        print(f"  JSON report  : {json_export_path}")
    print(f"  Replay used 0 LLM calls and 0 web searches.")


if __name__ == "__main__":
    main()
