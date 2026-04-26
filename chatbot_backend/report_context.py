"""
report_context.py
-----------------
Single source-of-truth for loading and structuring ESG pipeline outputs.

Public API
----------
  find_latest_report(reports_dir, company, min_mtime) -> ReportArtifacts | None
  get_esg_context(reports_dir, company)               -> dict  (the ONE function the service calls)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ReportArtifacts:
    txt_file_name: str
    txt_content: str
    json_file_name: str | None
    json_payload: dict[str, Any] | None
    modified_at: datetime


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _company_slug(company: str) -> str:
    return "_".join(company.strip().split()).replace("/", "_")


def find_latest_report(
    reports_dir: Path,
    company: str | None = None,
    min_mtime: float | None = None,
) -> ReportArtifacts | None:
    if not reports_dir.exists():
        return None

    txt_files = sorted(
        reports_dir.glob("ESG_Report_*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if company:
        slug = _company_slug(company)
        filtered = [p for p in txt_files if slug.lower() in p.name.lower()]
        if filtered:
            txt_files = filtered

    if min_mtime is not None:
        fresher = [p for p in txt_files if p.stat().st_mtime >= min_mtime]
        if fresher:
            txt_files = fresher

    if not txt_files:
        return None

    txt_path = txt_files[0]
    txt_content = txt_path.read_text(encoding="utf-8", errors="ignore")
    json_path = txt_path.with_suffix(".json")
    json_payload = _read_json(json_path)

    return ReportArtifacts(
        txt_file_name=txt_path.name,
        txt_content=txt_content,
        json_file_name=json_path.name if json_payload is not None else None,
        json_payload=json_payload,
        modified_at=datetime.fromtimestamp(txt_path.stat().st_mtime),
    )


def _parse_txt_report(txt: str, json_payload: dict[str, Any] | None) -> dict[str, Any]:
    sections = []
    pattern = re.compile(r'^(SECTION\s+\d+):\s*(.*)', re.IGNORECASE | re.MULTILINE)
    parts = pattern.split(txt)
    for i in range(1, len(parts), 3):
        sec_id = parts[i].strip()
        title = parts[i+1].strip()
        content = parts[i+2].strip()
        
        # Extract semantic tags
        text_for_tags = (title + " " + content).lower()
        tags = []
        if "greenwash" in text_for_tags: tags.append("greenwashing")
        if "greenhush" in text_for_tags: tags.append("greenhushing")
        if "greenwish" in text_for_tags: tags.append("greenwishing")
        if "deception" in text_for_tags: tags.append("deception")
        if "score" in text_for_tags: tags.append("scores")
        if "carbon" in text_for_tags or "emission" in text_for_tags or "scope" in text_for_tags: tags.append("carbon")
        if "regulat" in text_for_tags or "compliance" in text_for_tags: tags.append("regulatory")
        if "contradict" in text_for_tags or "mismatch" in text_for_tags: tags.append("contradiction")
        if "evidence" in text_for_tags or "source" in text_for_tags: tags.append("evidence")
        if "peer" in text_for_tags or "industry" in text_for_tags: tags.append("peers")

        sections.append({
            "section_id": sec_id,
            "title": title,
            "content": content,
            "tags": list(set(tags))
        })
    
    metrics = {}
    
    # 1. Regex Extraction
    for m in re.finditer(r'(greenwashing\s+risk|esg)\s+score\s*:\s*(\d+(?:\.\d+)?)', txt, re.IGNORECASE):
        k = 'greenwashing' if 'greenwashing' in m.group(1).lower() else 'esg'
        metrics[k + '_score'] = float(m.group(2))

    for m in re.finditer(r'^\s*(greenwishing|greenhushing)\s+(?:LOW|MEDIUM|HIGH|CRITICAL|EXTREME|UNKNOWN|\?+)\s+(\d+(?:\.\d+)?)', txt, re.IGNORECASE | re.MULTILINE):
        metrics[m.group(1).lower() + '_score'] = float(m.group(2))
        
    # 2. Validation & Fallback
    validated_metrics = {}
    json_scores = (json_payload or {}).get("scores", {})
    json_agents = (json_payload or {}).get("agent_outputs", [])
    
    def get_fallback(key: str) -> float | None:
        if key == "greenwashing_score": return json_scores.get("greenwashing_score")
        if key == "esg_score": return json_scores.get("esg_score")
        if key in ("greenwishing_score", "greenhushing_score"):
            agent_key = key.replace("_score", "")
            for a in json_agents:
                if isinstance(a, dict) and a.get("agent") == "greenwishing_detection":
                    val = a.get(agent_key, {}).get("score")
                    if val is not None:
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            pass
        return None

    for key in ["greenwashing_score", "esg_score", "greenwishing_score", "greenhushing_score"]:
        val = metrics.get(key)
        fallback = get_fallback(key)
        
        # Check bounds and valid float
        if val is not None and 0 <= val <= 100:
            validated_metrics[key] = val
        elif fallback is not None and 0 <= float(fallback) <= 100:
            validated_metrics[key] = float(fallback)

    return {
        "sections": sections,
        "txt_metrics": validated_metrics
    }


# ---------------------------------------------------------------------------
# get_esg_context — THE single function the chat service uses
# ---------------------------------------------------------------------------

def get_esg_context(
    reports_dir: Path,
    company: str | None = None,
) -> dict[str, Any] | None:
    """
    Load the latest report JSON and return a structured context dict.

    Returns None if no report is found.

    Schema returned:
    {
      "company":          str,
      "industry":         str,
      "claim":            str,
      "verdict":          dict,   # final_verdict block
      "score":            dict,   # scores block (greenwashing, esg, pillar breakdown)
      "confidence":       float | str,
      "evidence":         list[dict],   # evidence_records (capped at 20)
      "contradictions":   list[dict],   # contradictions block
      "regulatory_gaps":  list[dict],
      "carbon_data":      dict | None,
      "agent_insights":   dict,   # keyed by agent name, from agent_outputs list
      "sections":         list[dict],
      "txt_metrics":      dict,
      "report_timestamp": str,
    }
    """
    artifacts = find_latest_report(reports_dir, company=company)
    if artifacts is None:
        return None

    data: dict[str, Any] = artifacts.json_payload or {}
    txt_parsed = _parse_txt_report(artifacts.txt_content, artifacts.json_payload)

    # ── Core identifiers ───────────────────────────────────────────────────
    company_name = data.get("company") or company or "Unknown"
    industry = data.get("industry") or "Unknown"
    claim = (
        data.get("claim_analyzed")
        or data.get("claim")
        or data.get("final_verdict", {}).get("claim")
        or "Not specified"
    )

    # ── Scores ─────────────────────────────────────────────────────────────
    scores: dict[str, Any] = data.get("scores", {})
    pillar_factors: dict[str, Any] = data.get("pillar_factors", {})

    score_summary = {
        "greenwashing_score":     scores.get("greenwashing_score"),
        "esg_score":              scores.get("esg_score"),
        "esg_rating":             scores.get("esg_rating"),
        "environmental":          scores.get("environmental") or pillar_factors.get("environmental", {}).get("score"),
        "social":                 scores.get("social") or pillar_factors.get("social", {}).get("score"),
        "governance":             scores.get("governance") or pillar_factors.get("governance", {}).get("score"),
        "confidence":             scores.get("confidence"),
        "report_tier":            scores.get("report_tier"),
        "compliance_risk_level":  scores.get("compliance", {}).get("risk_level"),
        "compliance_gap_count":   scores.get("compliance", {}).get("gap_count"),
    }

    confidence = (
        scores.get("confidence")
        or data.get("confidence")
        or data.get("confidence_score")
        or "UNKNOWN"
    )

    # ── Final verdict ───────────────────────────────────────────────────────
    final_verdict: dict[str, Any] = data.get("final_verdict", {})

    # ── Evidence ───────────────────────────────────────────────────────────
    # Use evidence_records (structured) first; fall back to evidence_sources
    raw_evidence = data.get("evidence_records") or data.get("evidence_sources") or []
    if not isinstance(raw_evidence, list):
        raw_evidence = []
    evidence = raw_evidence[:20]

    # ── Contradictions ─────────────────────────────────────────────────────
    raw_contradictions = data.get("contradictions", [])
    if not isinstance(raw_contradictions, list):
        raw_contradictions = []
    # Also pull from final_verdict if present
    if not raw_contradictions and isinstance(final_verdict, dict):
        vc = final_verdict.get("contradictions", [])
        if isinstance(vc, list):
            raw_contradictions = vc
    contradictions = raw_contradictions[:15]

    # ── Regulatory gaps ────────────────────────────────────────────────────
    regulatory_gaps = data.get("regulatory_gaps", [])
    if not isinstance(regulatory_gaps, list):
        regulatory_gaps = []

    # ── Carbon data ────────────────────────────────────────────────────────
    carbon_data = data.get("carbon_data") or data.get("carbon_extraction")

    # ── Agent insights — keyed dict for easy lookup by intent ──────────────
    raw_agent_outputs = data.get("agent_outputs", [])
    agent_insights: dict[str, Any] = {}
    if isinstance(raw_agent_outputs, list):
        for item in raw_agent_outputs:
            if isinstance(item, dict):
                agent_name = item.get("agent") or item.get("name", "unknown")
                agent_insights[agent_name] = item

    # Supplement with dedicated top-level agent blocks present in the JSON
    _DEDICATED_BLOCKS = [
        "greenwishing_analysis",
        "regulatory_compliance",
        "climatebert_analysis",
        "esg_mismatch_analysis",
        "social_analysis",
        "governance_analysis",
        "explainability_report",
        "claim_decomposition",
        "adversarial_triangulation",
        "carbon_pathway_analysis",
        "commitment_ledger",
        "adversarial_audit",
    ]
    for block in _DEDICATED_BLOCKS:
        if block in data and data[block]:
            agent_insights.setdefault(block, data[block])

    return {
        "company":          company_name,
        "industry":         industry,
        "claim":            claim,
        "verdict":          final_verdict,
        "score":            score_summary,
        "confidence":       confidence,
        "evidence":         evidence,
        "contradictions":   contradictions,
        "regulatory_gaps":  regulatory_gaps[:10],
        "carbon_data":      carbon_data,
        "agent_insights":   agent_insights,
        "sections":         txt_parsed["sections"],
        "txt_metrics":      txt_parsed["txt_metrics"],
        "report_timestamp": artifacts.modified_at.isoformat(),
    }
