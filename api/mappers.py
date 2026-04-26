"""
api/mappers.py
--------------
Maps the raw pipeline JSON output (ESG_Report_*.json) to the
API Pydantic models.  The pipeline output is never modified —
all translation happens here.
"""
from __future__ import annotations

import hashlib
import re
import os
from typing import Any, Dict, List, Optional

from api.models import (
    CarbonData,
    Contradiction,
    ESGReport,
    EvidenceItem,
    GreenwashingData,
    HistoryEntry,
    PillarScore,
    RegulatoryItem,
    RiskDriver,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(v: Any, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _short_id(path: str) -> str:
    """Derive a stable report ID from the filename (e.g. 20260425-171609-SHEL)."""
    basename = os.path.splitext(os.path.basename(path))[0]
    # If the basename already looks like a usable ID, use it; else hash it.
    if len(basename) > 6:
        return basename
    return hashlib.md5(path.encode()).hexdigest()[:12]


# ── Pillar mapping ────────────────────────────────────────────────────────────

def _map_pillar(pillar_data: Optional[Dict]) -> PillarScore:
    if not pillar_data or not isinstance(pillar_data, dict):
        return PillarScore(score=0.0, weight=0.33)
    
    score = _safe_float(pillar_data.get("score", 0))
    weight = _safe_float(pillar_data.get("weight", 0.33))
    cov_adj = _safe_float(pillar_data.get("coverageadjustedscore") or pillar_data.get("coverage_adjusted_score"), score)

    # Count positive/negative sub-indicators
    sub_indicators = pillar_data.get("sub_indicators", [])
    positive = sum(1 for s in sub_indicators if _safe_float(s.get("score", 0)) >= 50)
    contradictions = sum(1 for s in sub_indicators if _safe_float(s.get("score", 0)) < 30)

    return PillarScore(
        score=score,
        coverage_adjusted_score=cov_adj,
        weight=weight,
        positive_signals=positive,
        contradictions=contradictions,
    )


# ── Carbon mapping ────────────────────────────────────────────────────────────

def _map_carbon(raw: Dict) -> CarbonData:
    carbon_ext = raw.get("carbon_extraction") or {}
    if isinstance(carbon_ext, dict) and "data" in carbon_ext:
        carbon_ext = carbon_ext["data"]

    # Also try to read from pillar sub-indicators (scope 1/2/3 are in env pillar)
    pillar_env = (raw.get("pillarfactors") or {}).get("environmental") or {}
    sub_indicators = pillar_env.get("sub_indicators", [])

    # Check new 'carbon_data' key
    carbon_data = raw.get("carbon_data") or {}

    scope1 = _safe_float(carbon_ext.get("scope_1") or carbon_ext.get("scope1") or carbon_data.get("scope1"), 0.0)
    scope2 = _safe_float(carbon_ext.get("scope_2") or carbon_ext.get("scope2") or carbon_data.get("scope2"), 0.0)
    scope3 = _safe_float(carbon_ext.get("scope_3") or carbon_ext.get("scope3") or carbon_data.get("scope3"), 0.0)

    # Fallback: parse from the GHG Intensity sub-indicator raw_value
    if scope1 == 0.0 and scope2 == 0.0:
        for si in sub_indicators:
            if "ghg" in si.get("name", "").lower() or "emission" in si.get("name", "").lower():
                raw_val = si.get("raw_value", "")
                if raw_val and "Scope 1:" in str(raw_val):
                    try:
                        parts = str(raw_val).split(",")
                        for p in parts:
                            p = p.strip()
                            if p.startswith("Scope 1:"):
                                scope1 = float(p.replace("Scope 1:", "").strip().split()[0].replace(",", ""))
                            elif p.startswith("Scope 2:"):
                                scope2 = float(p.replace("Scope 2:", "").strip().split()[0].replace(",", ""))
                            elif p.startswith("Scope 3:"):
                                scope3 = float(p.replace("Scope 3:", "").strip().split()[0].replace(",", ""))
                    except Exception:
                        pass

    total = scope1 + scope2 + scope3

    # Net-zero target from commitment_ledger or raw fields
    cl = raw.get("commitment_ledger") or {}
    if isinstance(cl, dict):
        commitments = cl.get("commitments", []) or cl.get("verified_commitments", [])
        net_zero_target = "Unknown"
        for c in commitments:
            if isinstance(c, dict):
                desc = c.get("description", "") or c.get("commitment", "")
                if "net zero" in str(desc).lower() or "net-zero" in str(desc).lower():
                    target_year = c.get("target_year", "") or c.get("year", "")
                    net_zero_target = f"Net zero by {target_year}" if target_year else str(desc)[:60]
                    break
    else:
        net_zero_target = str(carbon_ext.get("net_zero_target", "Unknown"))

    # IEA gap from carbon_pathway_analysis (real values, not hardcoded)
    cpa = raw.get("carbon_pathway_analysis") or {}
    if isinstance(cpa, dict) and "data" in cpa:
        cpa = cpa["data"]
    iea_gap = _safe_float(cpa.get("iea_gap_pct") or cpa.get("gap_pct") or cpa.get("pathway_gap"), None) if isinstance(cpa, dict) else None
    budget_years = _safe_float(cpa.get("budget_years_remaining") or cpa.get("remaining_years"), None) if isinstance(cpa, dict) else None
    # Annual reduction rates — needed by the frontend trajectory chart so it
    # plots the company's actual implied rate vs the IEA-required rate instead
    # of a hardcoded 12%/yr placeholder line.
    required_rate = _safe_float(cpa.get("required_annual_rate") or cpa.get("required_rate"), None) if isinstance(cpa, dict) else None
    implied_rate = _safe_float(cpa.get("company_implied_rate") or cpa.get("implied_rate"), None) if isinstance(cpa, dict) else None
    alignment_status = str(cpa.get("alignment_status") or "") if isinstance(cpa, dict) else ""

    # data quality
    adv = (raw.get("scores") or {}).get("adversarial_audit") or {}
    conf = _safe_float(adv.get("mean_agent_confidence", 0.7), 0.7)
    data_quality = _safe_int(carbon_data.get("data_quality")) if carbon_data.get("data_quality") else int(conf * 100)

    return CarbonData(
        scope1=scope1,
        scope2=scope2,
        scope3=scope3,
        total=total,
        net_zero_target=net_zero_target,
        data_quality=data_quality,
        iea_nze_gap_pct=iea_gap,
        budget_years_remaining=budget_years,
        required_annual_rate=required_rate,
        company_implied_rate=implied_rate,
        alignment_status=alignment_status,
    )


# ── Greenwashing mapping ──────────────────────────────────────────────────────

def _map_greenwashing(raw: Dict) -> GreenwashingData:
    gw = raw.get("greenwishing_analysis") or raw.get("greenwashing_analysis") or {}
    if isinstance(gw, dict) and "data" in gw:
        gw = gw["data"]

    scores = raw.get("scores") or {}
    gw_score = _safe_float(scores.get("greenwashingriskscore") or scores.get("greenwashing_score_raw"), 0)

    # ClimateBERT
    cb = raw.get("climatebert_analysis") or {}
    if isinstance(cb, dict) and "data" in cb:
        cb = cb["data"]
    if not isinstance(cb, dict):
        cb = {}

    return GreenwashingData(
        overall_score=gw_score,
        greenwishing_score=_safe_float(
            (gw.get("greenwishing") or {}).get("score") if isinstance(gw.get("greenwishing"), dict)
            else gw.get("greenwishing_score"),
            0.0
        ),
        greenhushing_score=_safe_float(
            (gw.get("greenhushing") or {}).get("score") if isinstance(gw.get("greenhushing"), dict)
            else gw.get("greenhushing_score"),
            0.0
        ),
        selective_disclosure=bool(gw.get("selective_disclosure", False)),
        temporal_escalation=str(gw.get("temporal_escalation", "LOW")),
        carbon_tunnel_vision=bool(gw.get("carbon_tunnel_vision", False)),
        linguistic_risk=_safe_float(raw.get("linguistic_risk") or gw.get("linguistic_risk"), 0.0),
        gsi_score=_safe_float(raw.get("gsi_score") or gw.get("gsi_score"), 0.0),
        boilerplate_score=_safe_float(raw.get("boilerplate_pct") or gw.get("boilerplate_score"), 0.0),
        climatebert_relevance=_safe_float(cb.get("climate_relevance") or cb.get("relevance_score"), 0.0),
        climatebert_risk=str(cb.get("risk_level") or cb.get("climate_risk", "LOW")),
    )


# ── Contradictions mapping ────────────────────────────────────────────────────

def _map_contradictions(raw: Dict) -> List[Contradiction]:
    result = []
    
    # From contradiction_analysis or top-level contradictions
    ca = raw.get("contradiction_analysis") or raw.get("contradictions") or {}
    if isinstance(ca, dict) and "data" in ca:
        ca = ca["data"]
    
    items = []
    if isinstance(ca, dict):
        items = ca.get("contradictions", []) or ca.get("items", []) or []
    elif isinstance(ca, list):
        items = ca

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        result.append(Contradiction(
            id=str(item.get("id", f"c{i}")),
            severity=str(item.get("severity", "MEDIUM")).upper(),
            claim_text=str(item.get("claim") or item.get("claim_text") or item.get("description", "")),
            evidence_text=str(item.get("evidence") or item.get("evidence_text") or item.get("description", "")),
            source=str(item.get("source", "")),
            source_url=item.get("url") or item.get("source_url"),
            year=_safe_int(item.get("year"), 0) or None,
            impact=str(item.get("impact", "")),
        ))

    return result


# ── Evidence mapping ──────────────────────────────────────────────────────────

def _map_evidence(raw: Dict) -> List[EvidenceItem]:
    result = []

    # Try multiple keys
    ev_list = (
        raw.get("unified_evidence")
        or raw.get("evidence")
        or raw.get("evidence_records")
        or []
    )
    if isinstance(ev_list, dict):
        ev_list = ev_list.get("items", []) or []

    for i, item in enumerate(ev_list):
        if not isinstance(item, dict):
            continue

        stance_raw = str(item.get("role") or item.get("stance") or item.get("relationship_to_claim") or "NEUTRAL").upper()
        stance_map = {
            "SUPPORTS": "SUPPORTING",
            "SUPPORTIVE": "SUPPORTING",
            "CONTRADICTS": "CONTRADICTING",
            "MIXED": "NEUTRAL",
        }
        stance = stance_map.get(stance_raw, stance_raw)

        result.append(EvidenceItem(
            id=str(item.get("id", f"e{i}")),
            source_name=str(item.get("source") or item.get("source_name") or "Unknown"),
            source_url=item.get("url") or item.get("source_url"),
            credibility=_safe_float(item.get("credibility"), 0.5),
            stance=stance,
            excerpt=str(item.get("text") or item.get("excerpt") or item.get("snippet") or ""),
            year=_safe_int(item.get("year"), 0) or None,
            source_type=str(item.get("origin", item.get("source_type", "Unknown"))),
            archive_verified=bool(item.get("archive_verified", False)),
        ))

    return result[:50]  # cap for safety


# ── Regulatory mapping ────────────────────────────────────────────────────────

def _map_regulatory(raw: Dict) -> List[RegulatoryItem]:
    result = []
    compliance = (raw.get("scores") or {}).get("compliance") or {}
    frameworks = compliance.get("frameworks", [])

    seen = set()
    for fw in frameworks:
        if not isinstance(fw, dict):
            continue
        framework = str(fw.get("framework", ""))
        if not framework or framework in seen:
            continue
        seen.add(framework)

        status_raw = str(fw.get("status", "uncertain")).lower()
        status_map = {
            "compliant": "COMPLIANT",
            "gap": "NON-COMPLIANT",
            "uncertain": "PARTIAL",
            "active_enforcement": "NON-COMPLIANT",
        }
        status = status_map.get(status_raw, "PARTIAL")

        penalty = _safe_int(fw.get("penalty_score", 0))
        compliance_score = max(0, 100 - penalty * 2)

        result.append(RegulatoryItem(
            framework=framework,
            compliance_score=compliance_score,
            status=status,
            jurisdiction=str(fw.get("jurisdiction", "Global")),
            key_gap=str(fw.get("specific_violation") or fw.get("remediation_required") or ""),
        ))

    # Also handle regulatory_gaps if present
    reg_gaps = raw.get("regulatory_gaps") or []
    for rg in reg_gaps:
        if not isinstance(rg, dict):
            continue
        framework = str(rg.get("regulation", ""))
        if not framework or framework in seen:
            continue
        seen.add(framework)
        result.append(RegulatoryItem(
            framework=framework,
            compliance_score=50,
            status="NON-COMPLIANT",
            jurisdiction="Global",
            key_gap="; ".join(rg.get("gap_details", [])),
        ))

    return result


# ── Risk drivers mapping ──────────────────────────────────────────────────────

def _map_risk_drivers(raw: Dict) -> List[RiskDriver]:
    result = []
    expl = raw.get("explainability_report") or {}
    if isinstance(expl, dict) and "data" in expl:
        expl = expl["data"]
    if not isinstance(expl, dict):
        expl = {}

    # Step 1: collect REAL drivers (top-level + explainability agent output)
    drivers = list(expl.get("top_risk_drivers") or expl.get("shap_values") or [])
    agent_results = raw.get("agent_results") or []
    for ar in agent_results:
        if isinstance(ar, dict) and ar.get("agent") == "explainability":
            kf = ar.get("key_findings") or {}
            if isinstance(kf, dict):
                # Normalize agent's `top_factors` shape ({feature, impact, direction})
                # into the driver shape used downstream ({name, impact, direction, shap_value}).
                for factor in (kf.get("top_factors") or []):
                    if not isinstance(factor, dict):
                        continue
                    drivers.append({
                        "name": str(factor.get("feature") or factor.get("name") or "Unnamed driver"),
                        "impact": str(factor.get("impact") or "MEDIUM").upper(),
                        "direction": str(factor.get("direction") or "increases_risk").lower().replace(" ", "_"),
                        # Real SHAP value if the explainability agent produced one;
                        # otherwise leave None so we can flag it as un-quantified.
                        "shap_value": _safe_float(factor.get("shap_value"), None),
                    })
            break

    # Track which driver names came from real data so fallback inference
    # doesn't double-add the same risk dimension.
    seen_names = {str(d.get("name", "")).lower().strip() for d in drivers if isinstance(d, dict)}

    def _add_fallback(name: str, impact: str, direction: str, shap_value: float):
        """Add an inferred driver only if no real driver already covers this dimension."""
        if name.lower() in seen_names:
            return
        # Fuzzy collision check: if any real driver mentions a substantive token
        # from this fallback name, treat as already-covered.
        tokens = {t for t in re.findall(r"[a-z]{4,}", name.lower())}
        for sn in seen_names:
            if any(t in sn for t in tokens):
                return
        drivers.append({
            "name": name,
            "impact": impact,
            "direction": direction,
            "shap_value": shap_value,
            "_inferred": True,  # mark as heuristic-derived, not from explainability agent
        })
        seen_names.add(name.lower())

    # Step 2: fill gaps with inferred drivers — these are HEURISTIC fallbacks
    # used only when the explainability agent didn't surface this dimension.
    # The hardcoded SHAP magnitudes are illustrative weights, not real SHAP values.
    contras = _map_contradictions(raw)
    if contras:
        _add_fallback("Claim-Evidence Contradictions", "HIGH", "increases_risk", 15.0)

    regs = _map_regulatory(raw)
    if any(r.status == "NON-COMPLIANT" for r in regs):
        _add_fallback("Regulatory Alignment Gaps", "HIGH", "increases_risk", 12.0)

    carb = _map_carbon(raw)
    if carb.scope3 == 0 and carb.total > 0:
        _add_fallback("Scope 3 Disclosure Gap", "MEDIUM", "increases_risk", 8.0)

    pillars = raw.get("pillarfactors") or {}
    gov = pillars.get("governance", {})
    if isinstance(gov, dict) and _safe_float(gov.get("score"), 100) < 40:
        _add_fallback("Governance and Oversight Weakness", "MEDIUM", "increases_risk", 7.0)

    if "validated" in carb.net_zero_target.lower() or "sbti" in carb.net_zero_target.lower():
        _add_fallback("Science-Based Target Validation", "MEDIUM", "reduces_risk", -5.0)

    gw = _map_greenwashing(raw)
    if gw.overall_score > 60:
        _add_fallback("Elevated Greenwashing Signals", "HIGH", "increases_risk", 10.0)

    for d in drivers:
        if not isinstance(d, dict):
            continue
        raw_dir = str(d.get("direction", "increases_risk")).lower()
        if "increase" in raw_dir or "high" in raw_dir:
            direction = "increases_risk"
        else:
            direction = "reduces_risk"

        result.append(RiskDriver(
            name=str(d.get("name", d.get("feature", ""))),
            impact=str(d.get("impact", "")),
            direction=direction,
            shap_value=_safe_float(d.get("shap_value") or d.get("value"), None) or None,
        ))
    return result


# ── Ticker / sector from company name ────────────────────────────────────────

_TICKER_MAP = {
    "shell": ("SHEL", "Energy"),
    "bp": ("BP", "Energy"),
    "exxon": ("XOM", "Energy"),
    "jpmorgan": ("JPM", "Financial Services"),
    "jpmc": ("JPM", "Financial Services"),
    "microsoft": ("MSFT", "Technology"),
    "tesla": ("TSLA", "Automotive"),
    "apple": ("AAPL", "Technology"),
    "amazon": ("AMZN", "Technology"),
    "google": ("GOOGL", "Technology"),
    "unilever": ("ULVR", "Consumer Goods"),
    "barclays": ("BARC", "Financial Services"),
    "hsbc": ("HSBA", "Financial Services"),
    "tesco": ("TSCO", "Consumer Goods"),
}


def _get_ticker_sector(company: str, industry: Optional[str]) -> tuple[str, str]:
    company_lower = company.lower()
    for key, (ticker, sector) in _TICKER_MAP.items():
        if key in company_lower:
            return ticker, (industry or sector)
    # Derive a pseudo-ticker
    words = company.upper().split()
    ticker = "".join(w[0] for w in words if w.isalpha())[:4]
    return ticker, (industry or "General")


# ── Verdict ───────────────────────────────────────────────────────────────────

def _map_verdict(raw: Dict) -> str:
    fv = raw.get("final_verdict") or {}
    if isinstance(fv, dict):
        if fv:
            return str(fv.get("verdict") or fv.get("summary") or fv.get("message") or "")
    elif isinstance(fv, str):
        return fv
    
    # Generate a fallback summary based on risk and drivers
    company = str(raw.get("company", "The company"))
    scores = raw.get("scores") or {}
    gw_score = _safe_float(scores.get("greenwashingriskscore") or scores.get("greenwashing_score_raw"), 0)
    risk_level = str(raw.get("risk_level", scores.get("risk_level", "MODERATE"))).lower()
    
    drivers = _map_risk_drivers(raw)
    drivers_text = ""
    if drivers:
        names = [d.name for d in drivers[:3]]
        if len(names) > 1:
            names[-1] = "and " + names[-1]
        drivers_text = f" driven by {', '.join(names)}" if len(names) > 2 else f" driven by {' '.join(names)}"
        
    generated_verdict = f"{company} shows {risk_level} greenwashing risk ({gw_score}/100){drivers_text}."
    
    # Fallback to esg_mismatch_analysis only if we don't have enough data
    if gw_score == 0 and not drivers:
        esm = raw.get("esg_mismatch_analysis") or {}
        if isinstance(esm, dict):
            return str(esm.get("Executive Summary") or "")
    
    return generated_verdict


# ── Main mapper ───────────────────────────────────────────────────────────────

def map_report_to_schema(raw: Dict, report_id: str) -> ESGReport:
    """
    Translates raw pipeline JSON (from ESG_Report_*.json) into
    the ESGReport Pydantic model.  All key mapping lives here.
    """
    scores = raw.get("scores") or {}
    pillars = raw.get("pillarfactors") or {}

    company = str(raw.get("company", "Unknown"))
    industry = str(raw.get("industry", ""))
    ticker, sector = _get_ticker_sector(company, industry or None)

    esg_score = _safe_float(scores.get("esg_score"), 0.0)
    rating_grade = str(scores.get("esg_rating", "B"))
    risk_level_raw = str(raw.get("risk_level", scores.get("risk_level", "MODERATE"))).upper()
    if risk_level_raw not in ("HIGH", "MODERATE", "LOW"):
        risk_level_raw = "MODERATE"
        
    conf_val = _safe_float(scores.get("confidence"), 0.0)
    confidence = conf_val * 100 if conf_val <= 1.0 else conf_val

    # Agents
    adv = scores.get("adversarial_audit") or {}
    agents_total = _safe_int(
        adv.get("successful_agents", 0) + adv.get("failed_agents", 0), 0
    ) or len(adv.get("agents_seen", []))
    agents_successful = _safe_int(adv.get("successful_agents", agents_total))

    # Duration: not stored in report; leave as 0 (pipeline fills it)
    duration = _safe_float(raw.get("pipeline_duration_seconds"), 0.0)

    # Temporal
    temporal = raw.get("temporal_consistency") or raw.get("temporal_analysis") or {}
    if isinstance(temporal, dict) and "data" in temporal:
        temporal = temporal["data"]
    if not isinstance(temporal, dict):
        temporal = {}

    temporal_score = _safe_int(temporal.get("consistency_score") or temporal.get("temporal_score"), 0)
    temporal_risk = str(temporal.get("temporal_risk") or temporal.get("risk_level", "LOW")).upper()
    claim_trend = str(temporal.get("claim_trend") or temporal.get("trend", ""))
    env_trend = str(temporal.get("environmental_trend") or temporal.get("env_trend", ""))

    # Verdict / summary
    ai_verdict = _map_verdict(raw)
    exec_summary = str(raw.get("executive_summary") or raw.get("summary") or ai_verdict[:500])

    # ── New fields surfaced from session work (#2, #6, #12, #13) ──────────
    # Pull the risk_scoring agent's output for kg_drift and fact_graph motifs.
    _risk_scoring_kf = {}
    _evidence_retrieval_kf = {}
    for ar in (raw.get("agent_results") or []):
        if not isinstance(ar, dict):
            continue
        if ar.get("agent") == "risk_scoring":
            _risk_scoring_kf = ar.get("key_findings") or {}
        elif ar.get("agent") == "evidence_retrieval":
            _evidence_retrieval_kf = ar.get("key_findings") or {}

    kg_drift_block = _risk_scoring_kf.get("kg_drift") if isinstance(_risk_scoring_kf, dict) else {}
    if not isinstance(kg_drift_block, dict):
        kg_drift_block = {}

    fact_graph_block = _risk_scoring_kf.get("fact_graph") if isinstance(_risk_scoring_kf, dict) else {}
    fact_graph_motifs_block = (fact_graph_block or {}).get("motifs", {}) if isinstance(fact_graph_block, dict) else {}
    if not isinstance(fact_graph_motifs_block, dict):
        fact_graph_motifs_block = {}

    retriever_tally_block = _evidence_retrieval_kf.get("retriever_tally") if isinstance(_evidence_retrieval_kf, dict) else {}
    if not isinstance(retriever_tally_block, dict):
        retriever_tally_block = {}

    report = ESGReport(
        id=report_id,
        company=company,
        ticker=ticker,
        sector=sector,
        claim=str(raw.get("claim_analyzed") or raw.get("claim", "")),
        analysis_date=str(raw.get("analysis_date", "")),
        esg_score=esg_score,
        rating_grade=rating_grade,
        risk_level=risk_level_raw,
        confidence=confidence,
        environmental=_map_pillar(pillars.get("environmental")),
        social=_map_pillar(pillars.get("social")),
        governance=_map_pillar(pillars.get("governance")),
        carbon=_map_carbon(raw),
        greenwashing=_map_greenwashing(raw),
        contradictions=_map_contradictions(raw),
        evidence=_map_evidence(raw),
        regulatory=_map_regulatory(raw),
        agents_total=agents_total,
        agents_successful=agents_successful,
        pipeline_duration_seconds=duration,
        ai_verdict=ai_verdict,
        executive_summary=exec_summary,
        top_risk_drivers=_map_risk_drivers(raw),
        temporal_score=temporal_score,
        temporal_risk=temporal_risk,
        claim_trend=claim_trend,
        environmental_trend=env_trend,
        # New fields ─────────────────────────────────────────────────────
        quality_warnings=raw.get("quality_warnings") or [],
        model_versions=raw.get("model_versions") or {},
        calibration=raw.get("calibration") or {},
        kg_drift=kg_drift_block,
        fact_graph_motifs=fact_graph_motifs_block,
        retriever_tally=retriever_tally_block,
    )
    
    from api.validation_layer import apply_final_validation
    return apply_final_validation(report, raw)


def map_report_to_history(raw: Dict, report_id: str) -> HistoryEntry:
    """Lightweight summary of a report for the History / list endpoints."""
    full = map_report_to_schema(raw, report_id)
    return HistoryEntry(
        id=full.id,
        company=full.company,
        ticker=full.ticker,
        sector=full.sector,
        risk_level=full.risk_level,
        esg_score=full.esg_score,
        rating_grade=full.rating_grade,
        greenwashing_risk=full.greenwashing.overall_score,
        confidence=full.confidence,
        analysis_date=full.analysis_date,
        claim=full.claim,
        ai_verdict_short=full.ai_verdict[:120],
        contradictions_count=len(full.contradictions),
        agents_run=full.agents_total,
        duration_seconds=full.pipeline_duration_seconds,
    )
