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
    PeerEntry,
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

    # Pull agent-level findings — pathway + extraction live there, not at top level.
    pathway_kf: Dict = {}
    extraction_kf: Dict = {}
    for ar in (raw.get("agent_results") or []):
        if not isinstance(ar, dict):
            continue
        agent = ar.get("agent")
        kf = ar.get("key_findings") or {}
        if not isinstance(kf, dict):
            continue
        if agent == "carbon_pathway_analysis" and not pathway_kf:
            pathway_kf = kf
        elif agent == "carbon_extraction" and not extraction_kf:
            extraction_kf = kf

    # Net-zero target: prefer the carbon_extraction agent finding, then carbon_ext, then ledger.
    net_zero_target = "Unknown"
    if extraction_kf.get("net_zero_target"):
        net_zero_target = str(extraction_kf["net_zero_target"])
    elif carbon_ext.get("net_zero_target"):
        net_zero_target = str(carbon_ext["net_zero_target"])
    else:
        cl = raw.get("commitment_ledger") or {}
        if isinstance(cl, dict):
            commitments = cl.get("commitments", []) or cl.get("verified_commitments", [])
            for c in commitments:
                if not isinstance(c, dict):
                    continue
                desc = c.get("description", "") or c.get("commitment", "")
                if "net zero" in str(desc).lower() or "net-zero" in str(desc).lower() or "carbon negative" in str(desc).lower():
                    target_year = c.get("target_year", "") or c.get("year", "")
                    net_zero_target = f"Net zero by {target_year}" if target_year else str(desc)[:60]
                    break

    # Carbon pathway: read from the agent's key_findings (canonical field names).
    # Fall back to legacy top-level keys for older reports.
    cpa = raw.get("carbon_pathway_analysis") or {}
    if isinstance(cpa, dict) and "data" in cpa:
        cpa = cpa["data"]
    if not isinstance(cpa, dict):
        cpa = {}

    def _pick(*keys):
        for src in (pathway_kf, cpa):
            for k in keys:
                if k in src and src[k] is not None:
                    return src[k]
        return None

    budget_years = _safe_float(_pick("carbon_budget_remaining_yrs", "budget_years_remaining", "remaining_years"), None)
    required_rate = _safe_float(_pick("required_annual_rate_raw", "required_annual_rate", "required_rate", "implied_cagr_required"), None)
    implied_rate = _safe_float(_pick("company_implied_cagr", "company_implied_rate", "implied_rate"), None)
    alignment_status = str(_pick("alignment_status") or "")

    # IEA NZE annual-rate gap: the frontend Carbon tab caption shows "%/yr gap",
    # so prefer the rate-gap (implied - required) over the cumulative iea_nze_gap_pct.
    if required_rate is not None and implied_rate is not None:
        iea_gap = implied_rate - required_rate
    else:
        iea_gap = _safe_float(_pick("iea_nze_gap_pct", "iea_gap_pct", "gap_pct", "pathway_gap_pct", "pathway_gap"), None)

    # data quality
    adv = (raw.get("scores") or {}).get("adversarial_audit") or {}
    conf = _safe_float(adv.get("mean_agent_confidence", 0.7), 0.7)
    data_quality = _safe_int(carbon_data.get("data_quality")) if carbon_data.get("data_quality") else int(conf * 100)

    scope2_status = carbon_data.get("corrected_scope2_status") or (carbon_data.get("emissions") or {}).get("scope2_status") or "UNKNOWN"
    scope3_status = carbon_data.get("corrected_scope3_status") or (carbon_data.get("emissions") or {}).get("scope3_status") or "UNKNOWN"

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
        scope2_status=scope2_status,
        scope3_status=scope3_status,
    )


# ── Greenwashing mapping ──────────────────────────────────────────────────────

def _map_greenwashing(raw: Dict) -> GreenwashingData:
    # Deception data lives in the greenwishing_detection agent's key_findings,
    # and ClimateBERT NLP output lives in climatebert_analysis. Top-level keys
    # are not populated in current pipeline runs.
    gw: Dict = {}
    cb: Dict = {}
    for ar in (raw.get("agent_results") or []):
        if not isinstance(ar, dict):
            continue
        agent = ar.get("agent")
        kf = ar.get("key_findings") or {}
        if not isinstance(kf, dict):
            continue
        if agent == "greenwishing_detection" and not gw:
            gw = kf
        elif agent == "climatebert_analysis" and not cb:
            cb = kf

    # Fall back to top-level keys for legacy reports.
    if not gw:
        gw = raw.get("greenwishing_analysis") or raw.get("greenwashing_analysis") or {}
        if isinstance(gw, dict) and "data" in gw:
            gw = gw["data"]
    if not cb:
        cb = raw.get("climatebert_analysis") or {}
        if isinstance(cb, dict) and "data" in cb:
            cb = cb["data"]

    scores = raw.get("scores") or {}
    gw_score = _safe_float(scores.get("greenwashingriskscore") or scores.get("greenwashing_score_raw"), 0)

    def _score_or(d: Any, key_main: str, key_alt: str = "") -> float:
        if isinstance(d, dict):
            sub = d.get(key_main)
            if isinstance(sub, dict) and sub.get("score") is not None:
                return _safe_float(sub.get("score"), 0.0)
            if key_alt and d.get(key_alt) is not None:
                return _safe_float(d.get(key_alt), 0.0)
        return 0.0

    def _detected(d: Any, key: str) -> bool:
        if isinstance(d, dict):
            sub = d.get(key)
            if isinstance(sub, dict):
                return bool(sub.get("detected", False))
            return bool(sub)
        return False

    # ClimateBERT: real fields live under claim_analysis.climate_relevance.score
    # (0–100) and claim_analysis.greenwashing_detection.risk_level.
    cb_claim = (cb.get("claim_analysis") or {}) if isinstance(cb, dict) else {}
    cb_relevance_pct = _safe_float(
        (cb_claim.get("climate_relevance") or {}).get("score") if isinstance(cb_claim.get("climate_relevance"), dict)
        else cb.get("climate_relevance") or cb.get("relevance_score"),
        0.0,
    )
    # The frontend expects relevance as a 0–1 fraction (it multiplies by 100 for display).
    if cb_relevance_pct > 1.0:
        cb_relevance_frac = cb_relevance_pct / 100.0
    else:
        cb_relevance_frac = cb_relevance_pct

    cb_risk_level = ""
    cb_gw_detection = (cb_claim.get("greenwashing_detection") or {}) if isinstance(cb_claim, dict) else {}
    if isinstance(cb_gw_detection, dict):
        cb_risk_level = str(cb_gw_detection.get("risk_level") or "")
    if not cb_risk_level:
        cb_risk_level = str(cb.get("risk_level") or cb.get("climate_risk") or "LOW")

    # Linguistic risk proxy: greenwashing_risk_score from ClimateBERT's overall
    # assessment (0–100), or the greenwishing detector's overall_deception_risk.
    overall_dr = gw.get("overall_deception_risk") if isinstance(gw, dict) else None
    if isinstance(overall_dr, dict) and overall_dr.get("score") is not None:
        linguistic_risk = _safe_float(overall_dr.get("score"), 0.0)
    else:
        cb_overall = (cb_claim.get("overall_assessment") or {}) if isinstance(cb_claim, dict) else {}
        linguistic_risk = _safe_float(
            cb_overall.get("greenwashing_risk_score") if isinstance(cb_overall, dict) else None,
            0.0,
        )

    # Temporal escalation: classify from greenwishing.score (which represents
    # severity of aspirational language). LOW/MEDIUM/HIGH bands.
    gw_aspirational = _score_or(gw, "greenwishing", "greenwishing_score")
    if gw_aspirational >= 60:
        temporal_band = "HIGH"
    elif gw_aspirational >= 30:
        temporal_band = "MEDIUM"
    else:
        temporal_band = "LOW"
    if isinstance(gw, dict) and gw.get("temporal_escalation"):
        temporal_band = str(gw["temporal_escalation"])

    return GreenwashingData(
        overall_score=gw_score,
        greenwishing_score=gw_aspirational,
        greenhushing_score=_score_or(gw, "greenhushing", "greenhushing_score"),
        selective_disclosure=_detected(gw, "selective_disclosure"),
        temporal_escalation=temporal_band,
        carbon_tunnel_vision=_detected(gw, "carbon_tunnel_vision"),
        linguistic_risk=linguistic_risk,
        gsi_score=_safe_float(raw.get("gsi_score") or (gw.get("gsi_score") if isinstance(gw, dict) else None), 0.0),
        boilerplate_score=_safe_float(raw.get("boilerplate_pct") or (gw.get("boilerplate_score") if isinstance(gw, dict) else None), 0.0),
        climatebert_relevance=cb_relevance_frac,
        climatebert_risk=cb_risk_level or "LOW",
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

    # Backstop: pull from the contradiction_analysis agent's key_findings
    # when neither top-level list nor contradiction_analysis dict was present.
    if not items:
        for ar in (raw.get("agent_results") or []):
            if not isinstance(ar, dict):
                continue
            if ar.get("agent") != "contradiction_analysis":
                continue
            kf = ar.get("key_findings") or {}
            if isinstance(kf, dict):
                items = kf.get("contradiction_list") or kf.get("contradictions") or []
            break

    company_claim = str(raw.get("claim_analyzed") or raw.get("claim") or "").strip()

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        # Contradiction items typically have only `description` — the contradicting
        # evidence summary. Surface the company's analysed claim on the CLAIM side
        # of the UI card and the description on the EVIDENCE side, so the two
        # columns aren't echoes of each other.
        description = str(item.get("description") or "").strip()
        explicit_claim = str(item.get("claim") or item.get("claim_text") or "").strip()
        explicit_evidence = str(item.get("evidence") or item.get("evidence_text") or "").strip()

        claim_text = explicit_claim or company_claim or description
        evidence_text = explicit_evidence or description or claim_text

        impact = str(item.get("impact") or "")
        if not impact:
            severity = str(item.get("severity", "MEDIUM")).upper()
            confidence = str(item.get("confidence") or "").upper()
            stype = str(item.get("source_type") or "").lower()
            if severity == "HIGH":
                impact = "Materially undermines the headline claim."
            elif "regulatory" in stype or "verified" in stype:
                impact = "Verified counter-evidence — weighted into the headline score."
            elif "llm" in stype or confidence == "LOW":
                impact = "LLM-inferred signal — directional only, not used as a ground-truth floor."
            else:
                impact = "Counter-evidence considered in the score."

        result.append(Contradiction(
            id=str(item.get("id", f"c{i}")),
            severity=str(item.get("severity", "MEDIUM")).upper(),
            claim_text=claim_text,
            evidence_text=evidence_text,
            source=str(item.get("source", "")),
            source_url=item.get("url") or item.get("source_url"),
            year=_safe_int(item.get("year"), 0) or None,
            impact=impact,
        ))

    return result


# ── Evidence mapping ──────────────────────────────────────────────────────────

def _classify_source_type(url: str, source_name: str, reliability_tier: str) -> str:
    """Mirror professional_report_generator's source-type bucketing for the UI."""
    u = (url or "").lower()
    name = (source_name or "").lower()
    tier = (reliability_tier or "").lower()
    if "regulator" in tier or "filing" in tier:
        return "Regulatory Filing"
    if "news" in tier or "media" in tier:
        return "Major News"
    if "company" in tier or "disclos" in tier:
        return "Company Disclosure"
    if "esg" in tier or "data" in tier:
        return "Verified ESG Data"
    if any(k in u for k in ["sec.gov", "europa.eu", "epa.gov", "ec.europa.eu", "company-information.service.gov.uk"]):
        return "Regulatory Filing"
    if any(k in u for k in ["reuters.com", "ft.com", "bloomberg.com", "wsj.com", "newsweek.com", "guardian", "nytimes"]):
        return "Major News"
    if any(k in name for k in ["companies house", "sec edgar", "ofgem", "fca"]) or "filing" in name:
        return "Regulatory Filing"
    if any(k in name for k in ["reuters", "bloomberg", "guardian", "newsweek", "ft", "nytimes", "wsj"]):
        return "Major News"
    if u:
        return "Web Source"
    return "Unknown"


def _parse_year(value: Any) -> Optional[int]:
    if value is None:
        return None
    s = str(value)
    m = re.search(r"(19|20|21)\d{2}", s)
    if m:
        try:
            return int(m.group(0))
        except ValueError:
            return None
    return None


def _map_evidence(raw: Dict) -> List[EvidenceItem]:
    result = []

    # Prefer evidence_records (richest shape: snippet, url, relationship_to_claim,
    # reliability_tier, date) — that's what the audit TXT renders. Fall through
    # to other keys only if records is empty.
    ev_list = (
        raw.get("evidence_records")
        or raw.get("unified_evidence")
        or raw.get("evidence")
        or []
    )
    if isinstance(ev_list, dict):
        ev_list = ev_list.get("items", []) or []

    # Build a stance lookup from evidence_sources (keyed by URL) — sometimes
    # records say "Neutral" but the source registry has the real stance.
    stance_by_url: Dict[str, str] = {}
    for src in (raw.get("evidence_sources") or []):
        if not isinstance(src, dict):
            continue
        url = src.get("url") or ""
        stance = src.get("stance") or src.get("role") or ""
        if url and stance:
            stance_by_url[url] = str(stance)

    stance_map = {
        "SUPPORTS": "SUPPORTING",
        "SUPPORTIVE": "SUPPORTING",
        "CONTRADICTS": "CONTRADICTING",
        "MIXED": "NEUTRAL",
    }

    seen_urls: set = set()
    for i, item in enumerate(ev_list):
        if not isinstance(item, dict):
            continue

        # Skip internal LLM-synthesis "sources" — these are the system's own
        # inferences and must not be listed alongside external citations.
        _src_type_l = str(item.get("source_type") or item.get("origin") or "").lower()
        _src_name_l = str(item.get("source_name") or item.get("source") or "").lower()
        if (
            "llm_scan" in _src_type_l
            or "llm evidence synthesis" in _src_name_l
            or "claim_decomposition" in _src_name_l
            or "internal llm" in _src_name_l
        ):
            continue

        url = str(item.get("url") or item.get("source_url") or "").strip()
        # De-dupe by URL so the Evidence tab shows one row per unique source.
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        # Stance: prefer item.relationship_to_claim, then evidence_sources lookup.
        stance_raw = str(
            item.get("role")
            or item.get("stance")
            or item.get("relationship_to_claim")
            or stance_by_url.get(url, "")
            or "NEUTRAL"
        ).upper().split(",")[0].strip()
        stance = stance_map.get(stance_raw, stance_raw)
        if stance not in ("SUPPORTING", "CONTRADICTING", "NEUTRAL"):
            stance = "NEUTRAL"

        source_name = str(item.get("source_name") or item.get("source") or "Unknown")
        reliability_tier = str(item.get("reliability_tier") or "")
        source_type = _classify_source_type(url, source_name, reliability_tier)

        # Verified if the source has a real URL (mirrors the TXT report's
        # _compute_reliability_tier rule: "no URL → unverifiable").
        archive_verified = bool(url) and not item.get("archive_verified", True) is False
        if "archive_verified" in item:
            archive_verified = bool(item.get("archive_verified"))
        else:
            archive_verified = bool(url)

        # Credibility: derive from reliability_tier when not explicit.
        cred = _safe_float(item.get("credibility"), None)
        if cred is None:
            tier_l = reliability_tier.lower()
            if "regulator" in tier_l or "filing" in tier_l or source_type == "Regulatory Filing":
                cred = 0.95
            elif "news" in tier_l or source_type == "Major News":
                cred = 0.8
            elif "company" in tier_l or "disclos" in tier_l:
                cred = 0.75
            elif "esg" in tier_l:
                cred = 0.85
            elif url:
                cred = 0.6
            else:
                cred = 0.4

        # Year: parse from item.year, else from item.date.
        year = _safe_int(item.get("year"), 0) or None
        if year is None:
            year = _parse_year(item.get("date") or item.get("date_retrieved"))

        excerpt = str(item.get("text") or item.get("excerpt") or item.get("snippet") or item.get("title") or "")

        result.append(EvidenceItem(
            id=str(item.get("id", f"e{i}")),
            source_name=source_name,
            source_url=url or None,
            credibility=cred,
            stance=stance,
            excerpt=excerpt,
            year=year,
            source_type=source_type,
            archive_verified=archive_verified,
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

    # Map impact tier to a default magnitude when no real SHAP value exists.
    # The Explainability bar chart uses these as relative weights — keep them
    # spread out (HIGH > MODERATE > LOW) so bars don't all render identically.
    impact_to_magnitude = {
        "CRITICAL": 18.0,
        "HIGH": 14.0,
        "MEDIUM": 9.0,
        "MODERATE": 9.0,
        "LOW": 5.0,
    }

    for idx, d in enumerate(drivers):
        if not isinstance(d, dict):
            continue
        raw_dir = str(d.get("direction", "increases_risk")).lower()
        if "increase" in raw_dir or "high" in raw_dir:
            direction = "increases_risk"
        else:
            direction = "reduces_risk"

        impact = str(d.get("impact", "")).upper()
        shap_value = _safe_float(d.get("shap_value") or d.get("value"), None)
        if shap_value is None or shap_value == 0:
            magnitude = impact_to_magnitude.get(impact, 8.0)
            # Stagger drivers slightly by rank so bars don't render at exactly
            # the same height when multiple share the same impact tier.
            magnitude = max(2.0, magnitude - (idx * 0.5))
            shap_value = magnitude if direction == "increases_risk" else -magnitude

        result.append(RiskDriver(
            name=str(d.get("name", d.get("feature", ""))),
            impact=impact or "MEDIUM",
            direction=direction,
            shap_value=shap_value,
        ))
    return result


# ── Peer mapping ──────────────────────────────────────────────────────────────

def _map_peers(raw: Dict, focus_company: str, focus_ticker: str, focus_esg: float, focus_gw: float, focus_rating: str, focus_industry: str) -> tuple[List[PeerEntry], Optional[Dict[str, float]]]:
    """Map peer_comparison agent output to a list of PeerEntry objects.

    The focus company is always inserted as the first row with is_focus=True.
    Real peers come from agent_results[peer_comparison].key_findings.peers.
    Returns (peers_list, industry_average_dict_or_None).
    """
    peers: List[PeerEntry] = []
    industry_avg: Optional[Dict[str, float]] = None

    raw_peers: List[Dict[str, Any]] = []
    for ar in (raw.get("agent_results") or []):
        if not isinstance(ar, dict):
            continue
        if ar.get("agent") not in ("peer_comparison", "industry_comparator"):
            continue
        kf = ar.get("key_findings") or {}
        if not isinstance(kf, dict):
            continue
        candidate = kf.get("peers")
        if isinstance(candidate, list) and candidate:
            raw_peers = candidate
            ia = kf.get("industry_average")
            if isinstance(ia, dict):
                industry_avg = {
                    "esg": _safe_float(ia.get("esg"), 0.0),
                    "e": _safe_float(ia.get("e"), 0.0),
                    "s": _safe_float(ia.get("s"), 0.0),
                    "g": _safe_float(ia.get("g"), 0.0),
                }
            break

    # Always place the focus company first.
    peers.append(PeerEntry(
        name=focus_company,
        ticker=focus_ticker,
        esg=focus_esg,
        gw=focus_gw,
        rating=focus_rating,
        is_focus=True,
        industry=focus_industry,
    ))

    # De-dup against the focus company by stem-match (so "Microsoft" matches
    # "Microsoft Corporation"). Build a comparison key using a normalised stem
    # of the focus name so common-suffix peers don't double up.
    def _stem(s: str) -> str:
        s = s.lower().strip()
        for suffix in (
            " corporation", " corp", " inc.", " inc", " plc", " ltd",
            " limited", " group", ", inc.", ", inc", ", ltd", " ag", " s.a.",
            " sa", " co.", " co", " holdings", " industries",
        ):
            if s.endswith(suffix):
                s = s[: -len(suffix)].strip()
                break
        return s.replace(",", "").strip()

    focus_stem = _stem(focus_company)
    seen_stems = {focus_stem}
    for p in raw_peers:
        if not isinstance(p, dict):
            continue
        name = str(p.get("company") or p.get("name") or "").strip()
        if not name:
            continue
        peer_stem = _stem(name)
        if peer_stem in seen_stems:
            continue
        seen_stems.add(peer_stem)
        peers.append(PeerEntry(
            name=name,
            ticker=str(p.get("ticker") or ""),
            esg=_safe_float(p.get("esg") or p.get("esg_score"), 0.0),
            gw=_safe_float(p.get("gw") or p.get("greenwashing_risk_score") or p.get("gw_score"), 0.0),
            rating=str(p.get("rating") or ""),
            is_focus=bool(p.get("is_target", False)),
            industry=str(p.get("industry") or focus_industry),
            e_score=_safe_float(p.get("e"), None),
            s_score=_safe_float(p.get("s"), None),
            g_score=_safe_float(p.get("g"), None),
            rank=str(p.get("rank")) if p.get("rank") is not None else None,
        ))

    return peers, industry_avg


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
    gw_score_for_band = _safe_float(scores.get("greenwashingriskscore") or scores.get("greenwashing_score_raw"), 0.0)
    risk_level_raw = str(raw.get("risk_level", scores.get("risk_level", "")) or "").upper()
    if risk_level_raw not in ("HIGH", "MODERATE", "LOW"):
        risk_level_raw = ""
    # Floor the band against the headline GW score so a missing/stale risk_level
    # never underrepresents risk. The 4-tier _risk_band scheme (LOW/MODERATE/
    # HIGH/CRITICAL) collapses to 3 here because the API surface is 3-band.
    if gw_score_for_band >= 60:
        floor_band = "HIGH"
    elif gw_score_for_band >= 40:
        floor_band = "MODERATE"
    else:
        floor_band = "LOW"
    order = {"LOW": 0, "MODERATE": 1, "HIGH": 2}
    if not risk_level_raw or order[floor_band] > order.get(risk_level_raw, 0):
        risk_level_raw = floor_band
        
    conf_val = _safe_float(scores.get("confidence"), 0.0)
    confidence = conf_val * 100 if conf_val <= 1.0 else conf_val
    # Apply the same confidence-ceiling cap that the TXT report applies, so the
    # headline confidence on the frontend matches the printed audit (e.g. 65%
    # not 75.7%). The ceiling lives under raw.calibration when present.
    cal_block = raw.get("calibration") or {}
    if isinstance(cal_block, dict):
        ceiling = cal_block.get("confidence_ceiling_pct")
        if isinstance(ceiling, (int, float)):
            confidence = min(confidence, float(ceiling))
    # Confidence caps stored on scores (e.g. evidence-thinness or coverage caps).
    for cap_key in ("confidence_cap_pct", "confidence_ceiling_pct"):
        cap_val = scores.get(cap_key)
        if isinstance(cap_val, (int, float)):
            confidence = min(confidence, float(cap_val))

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

    # Real peer comparison data — replaces the hardcoded sector-peer rows.
    _gw_overall = _safe_float(scores.get("greenwashingriskscore") or scores.get("greenwashing_score_raw"), 0.0)
    peers_list, peer_industry_avg = _map_peers(
        raw,
        focus_company=company,
        focus_ticker=ticker,
        focus_esg=esg_score,
        focus_gw=_gw_overall,
        focus_rating=rating_grade,
        focus_industry=industry or sector,
    )

    # LLM-variance bands attached to the canonical scores dict in
    # professional_report_generator. Surfaced through to the API so the
    # frontend can render "55 [49-61]" on the headline.
    _gw_band_raw = scores.get("greenwashing_band") or []
    _esg_band_raw = scores.get("esg_band") or []
    _conf_band_raw = scores.get("confidence_band") or []
    _band_meta = scores.get("band_meta") or {}
    def _coerce_band(b: Any) -> List[float]:
        if isinstance(b, (list, tuple)) and len(b) == 2:
            try:
                return [float(b[0]), float(b[1])]
            except (TypeError, ValueError):
                return []
        return []

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
        esg_score_band=_coerce_band(_esg_band_raw),
        greenwashing_band=_coerce_band(_gw_band_raw),
        confidence_band=_coerce_band(_conf_band_raw),
        band_meta=_band_meta if isinstance(_band_meta, dict) else {},
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
        peers=peers_list,
        peer_industry_average=peer_industry_avg,
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
        emissions_verification=(
            raw.get("emissions_verification")
            if isinstance(raw.get("emissions_verification"), dict)
            else {}
        ),
        abstention_analysis=(
            raw.get("abstention_analysis")
            if isinstance(raw.get("abstention_analysis"), dict)
            else {}
        ),
        counterfactual=(
            raw.get("counterfactual")
            if isinstance(raw.get("counterfactual"), dict)
            else {}
        ),
        entity_record=(
            raw.get("entity_record")
            if isinstance(raw.get("entity_record"), dict)
            else {}
        ),
        company_lei=raw.get("company_lei"),
        financed_emissions=(
            raw.get("financed_emissions")
            if isinstance(raw.get("financed_emissions"), dict)
            else {}
        ),
        gdelt_events=(
            raw.get("gdelt_events")
            if isinstance(raw.get("gdelt_events"), dict)
            else {}
        ),
        litigation_resolved=(
            raw.get("litigation_resolved")
            if isinstance(raw.get("litigation_resolved"), dict)
            else {}
        ),
        regulatory_cross_ref=(
            raw.get("regulatory_cross_ref")
            if isinstance(raw.get("regulatory_cross_ref"), dict)
            else {}
        ),
        subsidiary_walk=(
            raw.get("subsidiary_walk")
            if isinstance(raw.get("subsidiary_walk"), dict)
            else {}
        ),
        promise_tracking=(
            raw.get("promise_tracking")
            if isinstance(raw.get("promise_tracking"), dict)
            else {}
        ),
        cross_pillar_contradictions=(
            raw.get("cross_pillar_contradictions")
            if isinstance(raw.get("cross_pillar_contradictions"), dict)
            else {}
        ),
        a3cg_triplets=(
            raw.get("a3cg_triplets")
            if isinstance(raw.get("a3cg_triplets"), dict)
            else {}
        ),
        kg_rag_retrieval=(
            raw.get("kg_rag_retrieval")
            if isinstance(raw.get("kg_rag_retrieval"), dict)
            else {}
        ),
        multimodal_extraction=(
            raw.get("multimodal_extraction")
            if isinstance(raw.get("multimodal_extraction"), dict)
            else {}
        ),
        macro_context=(
            raw.get("macro_context")
            if isinstance(raw.get("macro_context"), dict)
            else {}
        ),
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
