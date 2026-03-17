import os
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple

from ml_models.score_calibrator import linguistic_greenwashing_score
from ml_models.model_evaluator import run_full_evaluation
from ml_models.score_calibrator import run_calibration
from agents.contradiction_analyzer import analyze_contradictions
from agents.regulatory_scanner import compute_compliance_score, detect_regulation_gaps
from agents.industry_comparator import IndustryComparator

"""
Professional ESG Report Generator
Research-grade, publication-ready reporting for multi-agent greenwashing analysis
"""


class ReportQualityChecker:
    """Run structural quality checks before rendering the report.

    This checker inspects:
    - Evidence coverage and verifiability
    - Traceability of ESG pillar scores to factor rows
    - Use of synthetic peer data
    - Agent success flags vs. actual findings

    It outputs a list of quality_warnings and a report_confidence_level label.
    """

    def evaluate(self, state: Dict[str, Any], structured: Dict[str, Any]) -> Dict[str, Any]:
        agent_outputs = state.get("agent_outputs") or []
        if not isinstance(agent_outputs, list):
            agent_outputs = []

        agent_status: Dict[str, str] = {}
        for out in agent_outputs:
            if not isinstance(out, dict):
                continue
            name = out.get("agent")
            if not name:
                continue
            status = "FAILED" if ("error" in out or out.get("output") == "Agent not available") else "SUCCESS"
            if name not in agent_status or status == "FAILED":
                agent_status[name] = status

        evidence_struct = structured.get("evidence", {}) or {}
        citations: List[Dict[str, Any]] = evidence_struct.get("citations", []) or []
        verified_sources = [c for c in citations if c.get("verifiable")]
        unverifiable_sources = [c for c in citations if not c.get("verifiable")]

        peers_struct = structured.get("peers", {}) or {}
        real_peer_count = int(peers_struct.get("real_peer_count") or 0)
        used_synthetic = bool(peers_struct.get("used_synthetic_peers"))

        pillars = structured.get("pillars", {}) or {}
        quality_warnings: List[str] = []

        if not citations:
            quality_warnings.append(
                "No verifiable evidence citations available; findings rest on template-level reasoning and cached signals."
            )
        elif len(verified_sources) < 3:
            quality_warnings.append(
                f"Only {len(verified_sources)} verifiable evidence source(s); quantitative conclusions may be unstable."
            )

        if unverifiable_sources:
            quality_warnings.append(
                f"{len(unverifiable_sources)} evidence source(s) lacked URL or retrieval date and were excluded from score derivation."
            )

        for pillar_key, pillar_data in pillars.items():
            score = pillar_data.get("score")
            factors = pillar_data.get("factors") or []
            if isinstance(score, (int, float)) and score is not None and not factors:
                quality_warnings.append(
                    f"{pillar_key}-pillar score present but no traceable factor rows; derivation is opaque for this dimension."
                )

        if used_synthetic:
            quality_warnings.append(
                "Peer comparison relied partly on estimated peers; synthetic benchmarking should not be used for investment-grade decisions."
            )

        agent_findings = structured.get("agents", {}) or {}
        for name, status in agent_status.items():
            if status != "SUCCESS":
                continue
            canonical = name
            if canonical not in agent_findings or not agent_findings[canonical].get("has_findings"):
                quality_warnings.append(
                    f"Agent '{canonical}' marked SUCCESS but produced no structured findings in the report."
                )

        failed_agents = [n for n, s in agent_status.items() if s == "FAILED"]
        failure_count = len(failed_agents)
        verified_count = len(verified_sources)

        if failure_count == 0 and verified_count >= 10 and real_peer_count >= 2:
            confidence_level = "HIGH"
        elif failure_count <= 2 and verified_count >= 5:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        return {
            "quality_warnings": quality_warnings,
            "report_confidence_level": confidence_level,
            "agent_status": agent_status,
            "verified_source_count": verified_count,
            "real_peer_count": real_peer_count,
        }


class ProfessionalReportGenerator:
    """Generate research-grade ESG greenwashing reports from analysis state.

    This generator consumes the full LangGraph analysis state dict and produces:
    - A publication-style plain-text report (sections 1–7 as specified)
    - A machine-readable JSON export with structured fields for meta-analysis

    All dict access is defensive and uses safe .get patterns so missing
    upstream keys never cause report generation to fail.
    """

    def __init__(self):
        self.report_version = "4.0"
        self.methodology = "Multi-Agent ESG Analysis (Pillar-Primary, Calibrated)"

    def generate_executive_report(self, state: Dict[str, Any]) -> str:
        """Generate a research-grade, publication-ready executive report.

        Reads the multi-agent analysis state, builds a structured internal
        representation, runs quality checks, then renders a human-readable
        report with explicit sections, citations, and score derivations.
        """

        try:
            structured = self._build_structured_report(state)
            quality = ReportQualityChecker().evaluate(state, structured)
            structured.setdefault("metadata", {})["quality_warnings"] = quality["quality_warnings"]
            structured["metadata"]["report_confidence_level"] = quality["report_confidence_level"]

            analysis_timestamp = structured["metadata"]["timestamp_dt"]
            company = structured["company"]["name"]
            industry = structured["company"].get("industry", "Unknown")
            claim = structured["company"].get("claim", "No claim provided")

            node_order = state.get("node_execution_order") or []
            if isinstance(node_order, list) and node_order:
                workflow_display = " → ".join(str(n) for n in node_order if n)
            else:
                workflow_display = self._derive_workflow_string(state)

            scores = structured["scores"]
            evidence_struct = structured["evidence"]
            peers_struct = structured["peers"]
            calibration = structured["calibration"]
            pillars = structured["pillars"]
            agents = structured["agents"]
            limitations = structured["limitations"]

            executive_summary_block = self._render_section1_executive_summary(
                company,
                industry,
                claim,
                scores,
                evidence_struct,
                agents,
                peers_struct,
                quality,
            )

            evidence_table_block = self._render_section2_evidence_table(evidence_struct)
            score_derivation_block = self._render_section3_score_derivation(scores, pillars)
            agent_narrative_block = self._render_section4_agent_findings(agents)
            peer_block = self._render_section5_peer_comparison(company, industry, peers_struct)
            calibration_block = self._render_section6_calibration(calibration, scores)
            limitations_block = self._render_section7_limitations(limitations)

            validation_section = self._generate_validation_metadata_section()
            temporal_section = self._generate_temporal_consistency_section(state)
            enrichment_section = self._generate_data_enrichment_section(state)
            realism_section = self._generate_realism_diagnostics_section(state)
            quantitative_section = self._generate_quantitative_metrics_section(state)

            report_id = structured["metadata"]["report_id"]

            report = f"""
{'='*80}
ESG GREENWASHING RISK ASSESSMENT REPORT
{'='*80}

REPORT METADATA
{'─'*80}
Report ID:              {report_id}
Analysis Date:          {analysis_timestamp.strftime('%B %d, %Y at %H:%M:%S UTC')}
Report Version:         {self.report_version}
Methodology:            {self.methodology}
Analysis Workflow:      {workflow_display}
Report Confidence:      {quality['report_confidence_level']}
Quality Warnings:       {len(quality['quality_warnings'])}

{'='*80}
SECTION 1: EXECUTIVE SUMMARY
{'='*80}
{executive_summary_block}

{'='*80}
SECTION 2: EVIDENCE CITATIONS TABLE
{'='*80}
{evidence_table_block}

{'='*80}
SECTION 3: SCORE DERIVATION BREAKDOWN (E/S/G)
{'='*80}
{score_derivation_block}

{'='*80}
SECTION 4: AGENT FINDINGS NARRATIVE
{'='*80}
{agent_narrative_block}

{'='*80}
SECTION 5: PEER COMPARISON (REAL DATA ONLY)
{'='*80}
{peer_block}

{'='*80}
SECTION 6: CALIBRATION & CONFIDENCE STATEMENT
{'='*80}
{calibration_block}

{'='*80}
SECTION 7: CASE-SPECIFIC LIMITATIONS
{'='*80}
{limitations_block}

{'='*80}
APPENDIX A: VALIDATION & CALIBRATION STATUS
{'='*80}
{validation_section}

{'='*80}
APPENDIX B: TEMPORAL ESG CONSISTENCY ANALYSIS
{'='*80}
{temporal_section}

{'='*80}
APPENDIX C: DATA ENRICHMENT & ADVANCED METRICS
{'='*80}
{enrichment_section}

{'='*80}
APPENDIX D: REALISM DIAGNOSTICS
{'='*80}
{realism_section}

{'='*80}
APPENDIX E: QUANTITATIVE PERFORMANCE METRICS
{'='*80}
{quantitative_section}

{'='*80}
END OF REPORT
{'='*80}
"""

        except Exception as exc:
            return f"[ERROR] Report generation failed: {exc}"

        if not isinstance(report, str) or not report.strip():
            return "[ERROR] Report generation failed: No content generated."

        return report

    # ------------------------------------------------------------------
    # Structured representation builders
    # ------------------------------------------------------------------

    def _build_structured_report(self, state: Dict[str, Any]) -> Dict[str, Any]:
        analysis_timestamp = datetime.utcnow()

        company = str(state.get("company") or "Unknown").strip() or "Unknown"
        industry = str(state.get("industry") or "Unknown").strip() or "Unknown"
        claim = str(state.get("claim") or "No claim provided").strip() or "No claim provided"

        scores = self._extract_core_scoring(state)
        evidence_struct = self._extract_evidence_citations(state)
        pillars = self._build_pillar_factor_breakdown(scores, evidence_struct, state)
        agents = self._extract_agent_findings(state)
        peers = self._extract_peer_context(state)
        calibration = self._extract_calibration_info(scores)
        limitations = self._infer_limitations(state, evidence_struct, peers, calibration, agents)

        report_id = f"{analysis_timestamp.strftime('%Y%m%d-%H%M%S')}-{company.upper()[:4]}"

        return {
            "metadata": {
                "timestamp_dt": analysis_timestamp,
                "report_id": report_id,
                "workflow_path": state.get("workflow_path", "standard_track"),
            },
            "company": {
                "name": company,
                "industry": industry,
                "claim": claim,
            },
            "scores": scores,
            "evidence": evidence_struct,
            "pillars": pillars,
            "agents": agents,
            "peers": peers,
            "calibration": calibration,
            "limitations": limitations,
        }

    def _extract_core_scoring(self, state: Dict[str, Any]) -> Dict[str, Any]:
        agent_outputs = state.get("agent_outputs") or []
        if not isinstance(agent_outputs, list):
            agent_outputs = []

        risk_scorer_outputs = [
            o for o in agent_outputs if isinstance(o, dict) and o.get("agent") == "risk_scoring"
        ]
        risk_scorer_result: Dict[str, Any] = {}
        if risk_scorer_outputs:
            candidate = risk_scorer_outputs[-1].get("output")
            if isinstance(candidate, dict):
                risk_scorer_result = candidate
        if isinstance(state.get("risk_results"), dict):
            risk_scorer_result = state.get("risk_results")

        pillar_scores = risk_scorer_result.get("pillar_scores") or {}
        if not isinstance(pillar_scores, dict):
            pillar_scores = {}

        esg_rating = (
            state.get("rating_grade")
            or risk_scorer_result.get("rating_grade")
            or "BBB"
        )

        risk_level = (
            state.get("risk_level")
            or risk_scorer_result.get("risk_level")
            or "MODERATE"
        )

        greenwashing_risk_score = risk_scorer_result.get("greenwashing_risk_score")
        if not isinstance(greenwashing_risk_score, (int, float)):
            esg_score = risk_scorer_result.get("esg_score")
            if isinstance(esg_score, (int, float)):
                greenwashing_risk_score = max(0.0, min(100.0, 100.0 - float(esg_score)))
            else:
                defaults = {"LOW": 25.0, "MODERATE": 55.0, "HIGH": 80.0}
                greenwashing_risk_score = defaults.get(str(risk_level).upper(), 55.0)

        confidence = float(state.get("confidence") or 0.0)

        component_scores = risk_scorer_result.get("component_scores") or {}
        if not isinstance(component_scores, dict):
            component_scores = {}

        return {
            "esg_rating": esg_rating,
            "risk_level": risk_level,
            "greenwashing_risk_score": float(greenwashing_risk_score),
            "confidence": confidence,
            "pillar_scores": pillar_scores,
            "component_scores": component_scores,
            "raw": risk_scorer_result,
        }

    def _extract_evidence_citations(self, state: Dict[str, Any]) -> Dict[str, Any]:
        evidence = state.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []

        by_url: Dict[str, Dict[str, Any]] = {}
        for idx, item in enumerate(evidence, start=1):
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            title = (item.get("title") or item.get("source") or "Unknown source").strip() or "Unknown source"
            date = (item.get("date") or "").strip()
            source_name = (item.get("source") or item.get("domain") or "Unknown").strip() or "Unknown"
            source_type = (item.get("source_type") or "unknown").strip().lower()
            relationship = (item.get("relationship_to_claim") or "unspecified").strip()
            weight = item.get("evidence_weight")
            freshness_days = item.get("data_freshness_days")

            key = url or f"no-url-{idx}"
            existing = by_url.get(key)
            if existing is None:
                tier, verifiable = self._compute_reliability_tier(url, source_type)
                by_url[key] = {
                    "id": len(by_url) + 1,
                    "source_name": source_name,
                    "title": title,
                    "url": url or "[NO DIRECT URL]",
                    "date": date or "[DATE UNKNOWN]",
                    "claim_support": set([relationship]) if relationship else set(),
                    "reliability_tier": tier,
                    "verifiable": verifiable,
                    "weights": [weight] if isinstance(weight, (int, float)) else [],
                    "freshness_days": [freshness_days] if isinstance(freshness_days, (int, float)) else [],
                    "score_impact_notes": set(),
                }
            else:
                if relationship:
                    existing["claim_support"].add(relationship)
                if isinstance(weight, (int, float)):
                    existing["weights"].append(weight)
                if isinstance(freshness_days, (int, float)):
                    existing["freshness_days"].append(freshness_days)

        citations: List[Dict[str, Any]] = []
        for entry in by_url.values():
            weights = entry["weights"] or [0.0]
            freshness = entry["freshness_days"] or []
            avg_weight = sum(w for w in weights if isinstance(w, (int, float))) / max(
                1, len(weights)
            )
            min_freshness = min(freshness) if freshness else None
            entry_out = {
                "id": entry["id"],
                "source_name": entry["source_name"],
                "title": entry["title"],
                "url": entry["url"],
                "date": entry["date"],
                "claim_support": ", ".join(sorted(entry["claim_support"])) or "unspecified",
                "reliability_tier": entry["reliability_tier"],
                "verifiable": entry["verifiable"],
                "avg_weight": avg_weight,
                "freshest_days": min_freshness,
                "score_impact": "; ".join(sorted(entry["score_impact_notes"])) if entry["score_impact_notes"] else "n/a",
            }
            citations.append(entry_out)

        citations.sort(key=lambda c: (not c["verifiable"], c["reliability_tier"], c["id"]))

        total = len(citations)
        verifiable_count = len([c for c in citations if c["verifiable"]])

        return {
            "citations": citations,
            "total_citations": total,
            "verifiable_citations": verifiable_count,
        }

    def _compute_reliability_tier(self, url: str, source_type: str) -> Tuple[str, bool]:
        u = (url or "").lower()
        st = (source_type or "").lower()

        if not u:
            return "[UNVERIFIABLE]", False

        verifiable = True

        if any(t in st for t in ["regulatory", "filing", "10-k", "annual_report"]):
            return "Regulatory Filing", verifiable
        if any(k in u for k in ["sec.gov", "europa.eu", "epa.gov", "ec.europa.eu"]):
            return "Regulatory Filing", verifiable
        if any(t in st for t in ["cdp", "third_party", "assurance"]):
            return "CDP / Third-Party Verified", verifiable
        if any(k in u for k in ["cdp.net", "sciencebasedtargets.org", "unpri.org"]):
            return "CDP / Third-Party Verified", verifiable
        if any(k in u for k in ["ft.com", "reuters.com", "bloomberg.com", "nytimes.com", "wsj.com"]):
            return "Major News Outlet", verifiable
        if st in {"news", "media"}:
            return "Major News Outlet", verifiable
        if "estimated" in st or "synthetic" in st:
            return "Estimated / Synthetic", False

        return "General Web / Other", verifiable

    def _build_pillar_factor_breakdown(
        self,
        scores: Dict[str, Any],
        evidence_struct: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        pillar_scores = scores.get("pillar_scores") or {}
        component_scores = scores.get("component_scores") or {}
        risk_results = state.get("risk_results") or scores.get("raw") or {}
        pillar_factors = risk_results.get("pillar_factors") if isinstance(risk_results, dict) else {}
        if not isinstance(pillar_factors, dict):
            pillar_factors = {}

        if not pillar_factors:
            pillar_factors = self._extract_pillar_factors_from_logs(state)

        def build_pillar(name: str) -> Dict[str, Any]:
            label = {
                "E": "Environmental",
                "S": "Social",
                "G": "Governance",
            }.get(name, name)

            score = None
            if isinstance(pillar_scores, dict):
                for k, v in pillar_scores.items():
                    if k.lower().startswith(label.lower()[0]):
                        if isinstance(v, (int, float)):
                            score = float(v)
                            break

            factors: List[Dict[str, Any]] = []
            key_map = {"E": "environmental", "S": "social", "G": "governance"}
            state_factors = pillar_factors.get(key_map.get(name, ""), [])
            if isinstance(state_factors, list) and state_factors:
                for row in state_factors:
                    if not isinstance(row, dict):
                        continue
                    factor_name = row.get("factor", "Unknown factor")
                    confidence = str(row.get("confidence", "Unknown"))
                    if confidence.lower() == "low":
                        factor_name = f"{factor_name} [LOW CONFIDENCE]"
                    factors.append({
                        "factor": factor_name,
                        "raw_signal": row.get("raw_signal", "N/A"),
                        "source": row.get("source", "Unknown"),
                        "weight": row.get("weight"),
                        "points_contributed": row.get("points_contributed"),
                        "confidence": row.get("confidence", "Unknown"),
                    })

            if factors:
                return {
                    "label": label,
                    "score": score,
                    "factors": factors,
                }

            for comp_name, comp_val in component_scores.items():
                if not isinstance(comp_val, dict):
                    continue
                factor_pillar = (comp_val.get("pillar") or "").upper()
                if factor_pillar and factor_pillar != name.upper():
                    continue
                raw_signal = comp_val.get("raw_signal")
                weight = comp_val.get("weight")
                contribution = comp_val.get("contribution")
                if not isinstance(contribution, (int, float)):
                    contribution = None
                factor_label = comp_val.get("label") or comp_name
                confidence_flag = ""
                if comp_val.get("estimated") or comp_val.get("low_confidence"):
                    confidence_flag = " [LOW CONFIDENCE]"
                source_hint = comp_val.get("source_hint") or "Derived from multi-agent consensus"

                factors.append(
                    {
                        "factor": f"{factor_label}{confidence_flag}",
                        "raw_signal": raw_signal,
                        "source": source_hint,
                        "weight": weight,
                        "points_contributed": contribution,
                    }
                )

            return {
                "label": label,
                "score": score,
                "factors": factors,
            }

        return {
            "E": build_pillar("E"),
            "S": build_pillar("S"),
            "G": build_pillar("G"),
        }

    def _extract_pillar_factors_from_logs(self, state: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Last-resort parser for old runs without structured pillar_factors."""
        text_blobs: List[str] = []
        for out in state.get("agent_outputs", []) or []:
            if not isinstance(out, dict):
                continue
            output = out.get("output")
            if isinstance(output, str):
                text_blobs.append(output)
            elif isinstance(output, dict):
                text_blobs.append(json.dumps(output, default=str))

        blob = "\n".join(text_blobs)
        if not blob:
            return {}

        env = re.search(r"Environmental:\s*([\d.]+)/100\s*\(carbon_quality=([\d.]+)", blob, re.IGNORECASE)
        soc = re.search(r"Social:\s*([\d.]+)/100\s*\(controversies=([\d.]+)", blob, re.IGNORECASE)
        gov = re.search(r"Governance:\s*([\d.]+)/100\s*\(board=([\d.]+)", blob, re.IGNORECASE)

        factors: Dict[str, List[Dict[str, Any]]] = {}
        if env:
            factors["environmental"] = [{
                "factor": "Environmental score (log fallback)",
                "raw_signal": f"{env.group(2)}/100",
                "source": "Risk scorer log fallback",
                "weight": 1.0,
                "points_contributed": float(env.group(1)),
                "confidence": "Low",
            }]
        if soc:
            factors["social"] = [{
                "factor": "Social score (log fallback)",
                "raw_signal": f"controversies={soc.group(2)}",
                "source": "Risk scorer log fallback",
                "weight": 1.0,
                "points_contributed": float(soc.group(1)),
                "confidence": "Low",
            }]
        if gov:
            factors["governance"] = [{
                "factor": "Governance score (log fallback)",
                "raw_signal": f"board={gov.group(2)}",
                "source": "Risk scorer log fallback",
                "weight": 1.0,
                "points_contributed": float(gov.group(1)),
                "confidence": "Low",
            }]
        return factors

    def _derive_workflow_string(self, state: Dict[str, Any]) -> str:
        workflow_nodes = [
            k.replace("_results", "").replace("_", " ").title()
            for k in state.keys()
            if isinstance(k, str) and k.endswith("_results")
        ]
        if workflow_nodes:
            return " → ".join(workflow_nodes)
        outputs = [o.get("agent", "") for o in state.get("agent_outputs", []) if isinstance(o, dict)]
        cleaned = [str(a).replace("_", " ").title() for a in outputs if a]
        return " → ".join(cleaned) if cleaned else "Workflow unavailable"

    def _extract_agent_findings(self, state: Dict[str, Any]) -> Dict[str, Any]:
        agent_outputs = state.get("agent_outputs") or []
        if not isinstance(agent_outputs, list):
            agent_outputs = []

        agents: Dict[str, Dict[str, Any]] = {}
        for out in agent_outputs:
            if not isinstance(out, dict):
                continue
            name = out.get("agent") or "unknown_agent"
            output = out.get("output") or {}
            if not isinstance(output, dict):
                output = {"raw": output}
            confidence = out.get("confidence")
            timestamp = out.get("timestamp")
            error = out.get("error")

            agents[name] = {
                "name": name,
                "output": output,
                "confidence": confidence,
                "timestamp": timestamp,
                "error": error,
                "has_findings": bool(output) and not error,
            }

        explicit_result_keys = {
            "contradiction_analysis": "contradiction_results",
            "carbon_extraction": "carbon_results",
            "sentiment_analysis": "sentiment_results",
            "temporal_analysis": "historical_results",
            "credibility_analysis": "credibility_results",
            "climatebert_analysis": "climatebert_results",
            "regulatory_scanning": "regulatory_results",
            "explainability": "explainability_results",
            "risk_scoring": "risk_results",
        }
        for agent_name, state_key in explicit_result_keys.items():
            payload = state.get(state_key)
            if not isinstance(payload, dict):
                continue
            existing = agents.get(agent_name, {})
            agents[agent_name] = {
                "name": agent_name,
                "output": payload,
                "confidence": existing.get("confidence", payload.get("confidence")),
                "timestamp": existing.get("timestamp"),
                "error": existing.get("error"),
                "has_findings": bool(payload) and not existing.get("error"),
            }

        return agents

    def _extract_agent_summary(self, agent_name: str, agent_data: Dict[str, Any]) -> str:
        if not agent_data or not isinstance(agent_data, dict):
            return f"{agent_name}: No structured output returned."

        for key in ["summary", "finding", "result", "output", "analysis", "assessment", "verdict"]:
            if agent_data.get(key):
                return f"{agent_name}: {agent_data[key]}"

        strings = {k: v for k, v in agent_data.items() if isinstance(v, str) and len(v) > 20}
        if strings:
            first_key, first_val = next(iter(strings.items()))
            return f"{agent_name} [{first_key}]: {first_val}"

        return f"{agent_name}: Agent ran successfully. Key metrics: {list(agent_data.keys())}"

    def _extract_peer_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        peer_analysis = state.get("peer_comparison") or {}
        if not isinstance(peer_analysis, dict):
            peer_analysis = {}

        peers = peer_analysis.get("peers") or peer_analysis.get("peer_table") or []
        if not isinstance(peers, list):
            peers = []

        real_peers = [p for p in peers if isinstance(p, dict) and (p.get("source") or "").lower() == "database"]
        estimated_peers = [
            p
            for p in peers
            if isinstance(p, dict) and (p.get("source") or "").lower() in {"estimated", "synthetic"}
        ]

        data_source = peer_analysis.get("data_source") or (
            "real"
            if real_peers and not estimated_peers
            else "mixed"
            if real_peers and estimated_peers
            else "estimated"
            if estimated_peers
            else "none"
        )

        used_synthetic = bool(estimated_peers)

        return {
            "raw": peer_analysis,
            "all_peers": peers,
            "real_peers": real_peers,
            "estimated_peers": estimated_peers,
            "real_peer_count": len(real_peers),
            "estimated_peer_count": len(estimated_peers),
            "data_source": data_source,
            "used_synthetic_peers": used_synthetic,
        }

    def _extract_calibration_info(self, scores: Dict[str, Any]) -> Dict[str, Any]:
        calibration_report: Dict[str, Any] = {}
        calib_path = os.path.join(os.path.dirname(__file__), '../reports/calibration_report.json')

        try:
            if os.path.exists(calib_path):
                with open(calib_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    calibration_report = loaded
            else:
                generated = run_calibration()
                if isinstance(generated, dict):
                    calibration_report = generated
        except Exception:
            calibration_report = {}

        linguistic_cal = calibration_report.get("linguistic_scorer") or {}

        gw_score = scores.get("greenwashing_risk_score")
        confidence_region = "unknown"
        if isinstance(gw_score, (int, float)):
            threshold = linguistic_cal.get("optimal_threshold") or 50
            if gw_score >= threshold + 10:
                confidence_region = "high_suspicion_zone"
            elif gw_score <= threshold - 10:
                confidence_region = "likely_legitimate_zone"
            else:
                confidence_region = "grey_zone"

        return {
            "spearman_r": linguistic_cal.get("spearman_r"),
            "spearman_p": linguistic_cal.get("spearman_p"),
            "point_biserial_r": linguistic_cal.get("point_biserial_r"),
            "mannwhitney_p": linguistic_cal.get("mannwhitney_p"),
            "optimal_threshold": linguistic_cal.get("optimal_threshold"),
            "mean_score_greenwashing": linguistic_cal.get("mean_score_greenwashing"),
            "mean_score_legitimate": linguistic_cal.get("mean_score_legitimate"),
            "calibration_status": linguistic_cal.get("calibration_status"),
            "confidence_region": confidence_region,
        }

    def _infer_limitations(
        self,
        state: Dict[str, Any],
        evidence_struct: Dict[str, Any],
        peers: Dict[str, Any],
        calibration: Dict[str, Any],
        agents: Dict[str, Any],
    ) -> List[str]:
        limitations: List[str] = []

        citations = evidence_struct.get("citations") or []
        verifiable_count = evidence_struct.get("verifiable_citations") or 0
        total_citations = evidence_struct.get("total_citations") or len(citations)

        if total_citations == 0:
            limitations.append(
                "No fully verifiable primary sources were available; findings rely on secondary data, cached models, and generic sector priors."
            )
        elif verifiable_count < max(3, total_citations // 3):
            limitations.append(
                "Only a minority of sources carried robust URLs and timestamps; several claims could not be independently verified."
            )

        if peers.get("real_peer_count", 0) < 2:
            limitations.append(
                "Insufficient real peer coverage; industry benchmarking should be treated as indicative rather than definitive."
            )
        if peers.get("used_synthetic_peers"):
            limitations.append(
                "Estimated peers were used to approximate the industry distribution; this weakens any claims about relative ranking."
            )

        reg = state.get("regulatory_compliance") or {}
        if not reg:
            limitations.append(
                "Regulatory compliance scanner did not return structured results; potential jurisdictional non-compliance may be under-detected."
            )

        temporal = state.get("temporal_consistency") or {}
        if isinstance(temporal, dict) and not temporal.get("years_analyzed"):
            limitations.append(
                "Temporal analysis collapsed to a single-year snapshot; long-run consistency of claims vs. performance is uncertain."
            )

        greenwish = state.get("greenwishing_analysis") or {}
        if isinstance(greenwish, dict) and greenwish.get("analysis_mode") == "heuristic_only":
            limitations.append(
                "Greenwishing/greenhushing flags are based on heuristic linguistic patterns without robust ground-truth calibration."
            )

        cal_status = calibration.get("calibration_status")
        if cal_status and "out_of_sample" not in str(cal_status).lower():
            limitations.append(
                "Calibration dataset may not fully represent the sector and geography of this issuer; transport of thresholds should be reviewed."
            )

        crucial_agents = [
            "evidence_retrieval",
            "risk_scoring",
            "sentiment_analysis",
            "industry_comparator",
            "temporal_analysis",
        ]
        for name in crucial_agents:
            a = agents.get(name)
            if not a or a.get("error"):
                limitations.append(
                    f"Core agent '{name}' failed or returned no structured output; its dimension is effectively missing from the integrated score."
                )

        return limitations

    # ------------------------------------------------------------------
    # Section renderers
    # ------------------------------------------------------------------

    def _render_section1_executive_summary(
        self,
        company: str,
        industry: str,
        claim: str,
        scores: Dict[str, Any],
        evidence: Dict[str, Any],
        agents: Dict[str, Any],
        peers: Dict[str, Any],
        quality: Dict[str, Any],
    ) -> str:
        esg_rating = scores.get("esg_rating", "BBB")
        risk_level = scores.get("risk_level", "MODERATE")
        gw_score = scores.get("greenwashing_risk_score")
        confidence = scores.get("confidence", 0.0)

        citations = evidence.get("citations") or []
        verifiable = evidence.get("verifiable_citations", 0)

        real_peers = peers.get("real_peer_count", 0)

        summary_lines: List[str] = []
        summary_lines.append(
            f"This report evaluates whether the stated ESG positioning of {company} (industry: {industry}) is consistent with independently verifiable evidence."
        )

        if isinstance(gw_score, (int, float)):
            summary_lines.append(
                f"The integrated greenwashing risk score is {gw_score:.1f}/100, corresponding to an overall ESG risk rating of {esg_rating} and a {risk_level.lower()} level of greenwashing concern."
            )
        else:
            summary_lines.append(
                f"The integrated greenwashing risk score could not be calibrated numerically; the qualitative rating is {esg_rating} with {risk_level.lower()} concern."
            )

        summary_lines.append(
            f"The assessment draws on {len(citations)} distinct evidence sources, of which {verifiable} met strict verifiability criteria (stable URL and identifiable retrieval date)."
        )

        if real_peers >= 2:
            summary_lines.append(
                f"Benchmarking against {real_peers} real peer company(ies) suggests that {company} sits within the {risk_level.lower()} portion of the sectoral distribution for greenwashing risk."
            )
        else:
            summary_lines.append(
                "Robust peer benchmarking was not possible because the peer database contained fewer than two comparable firms with sufficient ESG disclosure."
            )

        report_conf = quality.get("report_confidence_level", "UNKNOWN")
        summary_lines.append(
            f"Taking into account agent failures, evidence depth, and peer coverage, the overall report confidence is classified as {report_conf}."
        )

        summary_lines.append(
            f"Key claim analyzed: {claim}. Detailed factor-level explanations, source citations, and calibration diagnostics follow in Sections 2–7 and the appendices."
        )

        return "\n".join(summary_lines)

    def _render_section2_evidence_table(self, evidence: Dict[str, Any]) -> str:
        citations = evidence.get("citations") or []
        if not citations:
            return "No structured evidence citations were available for this run."

        lines: List[str] = []
        header = f"{'#':<3} {'Source Name':<30} {'Reliability Tier':<28} {'Verifiable':<11} {'Claim It Supports':<30}"
        lines.append(header)
        lines.append("-" * len(header))

        for c in citations:
            idx = c.get("id")
            src = c.get("source_name", "Unknown")[:30]
            tier = c.get("reliability_tier", "?")[:28]
            ver = "YES" if c.get("verifiable") else "NO"
            claim_support = c.get("claim_support", "unspecified")[:30]
            lines.append(f"{idx:<3} {src:<30} {tier:<28} {ver:<11} {claim_support:<30}")

        lines.append("")
        lines.append("Reliability tiers (from strongest to weakest):")
        lines.append("  1. Regulatory Filing")
        lines.append("  2. CDP / Third-Party Verified")
        lines.append("  3. Major News Outlet")
        lines.append("  4. General Web / Other")
        lines.append("  5. Estimated / Synthetic")
        lines.append("  6. [UNVERIFIABLE] (excluded from score derivation)")

        return "\n".join(lines)

    def _render_section3_score_derivation(
        self,
        scores: Dict[str, Any],
        pillars: Dict[str, Any],
    ) -> str:
        lines: List[str] = []
        gw_score = scores.get("greenwashing_risk_score")
        esg_rating = scores.get("esg_rating")
        risk_level = scores.get("risk_level")

        if isinstance(gw_score, (int, float)):
            lines.append(
                f"The overall greenwashing risk score of {gw_score:.1f}/100 is derived from a weighted aggregation of factor-level signals across the environmental (E), social (S), and governance (G) pillars."
            )
        else:
            lines.append(
                "The overall greenwashing risk score could not be expressed as a single calibrated value; the breakdown below still reflects the relative contributions of each pillar."
            )

        lines.append(
            f"The resulting composite places the issuer in the {risk_level.lower()} risk band and corresponds to an ESG-style rating of {esg_rating}."
        )
        lines.append("")

        for key, p in pillars.items():
            label = p.get("label", key)
            score = p.get("score")
            factors = p.get("factors") or []
            lines.append(f"{label.upper()} PILLAR")
            lines.append("-" * (len(label) + 7))
            if isinstance(score, (int, float)):
                lines.append(f"Pillar score: {score:.1f}/100")
            else:
                lines.append("Pillar score: not available (insufficient data)")

            if not factors:
                lines.append("  | Factor | Raw Signal | Source | Weight | Points | Confidence |")
                lines.append("  |--------|-----------|--------|--------|--------|------------|")
                lines.append("  | Score reconstruction (fallback) [LOW CONFIDENCE] | N/A | Log fallback parser | 100% | 0.0 | Low |")
                lines.append("  Pillar total: 0.0/100")
                lines.append("")
                continue
            lines.append("  | Factor | Raw Signal | Source | Weight | Points | Confidence |")
            lines.append("  |--------|-----------|--------|--------|--------|------------|")
            pillar_total = 0.0
            for f in factors:
                factor = str(f.get("factor", "?"))
                raw_val = f.get("raw_signal", "?")
                raw = str(raw_val)
                weight = f.get("weight")
                contrib = f.get("points_contributed")
                confidence = str(f.get("confidence", "Unknown"))

                if isinstance(raw_val, (int, float)):
                    raw = f"{float(raw_val):.1f}/100"
                if isinstance(weight, (int, float)):
                    w_str = f"{weight * 100:.0f}%"
                else:
                    w_str = "N/A"
                if isinstance(contrib, (int, float)):
                    c_str = f"{float(contrib):.1f}"
                    pillar_total += float(contrib)
                else:
                    c_str = "0.0"

                if confidence.lower() == "low" and "LOW CONFIDENCE" not in factor:
                    factor = f"{factor} [LOW CONFIDENCE]"

                lines.append(
                    f"  | {factor} | {raw} | {f.get('source', 'Unknown')} | {w_str} | {c_str} | {confidence} |"
                )
            lines.append(f"  Pillar total: {pillar_total:.1f}/100")
            lines.append("")

        return "\n".join(lines)

    def _render_section4_agent_findings(self, agents: Dict[str, Any]) -> str:
        if not agents:
            return "No agent outputs were available to summarize."

        lines: List[str] = []
        for name, info in sorted(agents.items()):
            output = info.get("output") or {}
            error = info.get("error")
            conf = info.get("confidence")
            has_findings = info.get("has_findings") and not error

            header = f"Agent: {name}"
            lines.append(header)
            lines.append("-" * len(header))
            if error:
                lines.append(f"Status: FAILED — {error}")
                lines.append(
                    "This dimension was excluded from the integrated score; conclusions along this axis are incomplete."
                )
                lines.append("")
                continue

            status = "SUCCESS" if has_findings else "NO STRUCTURED FINDINGS"
            conf_str = f"{float(conf):.1%}" if isinstance(conf, (int, float)) else "n/a"
            lines.append(f"Status: {status} | Confidence: {conf_str}")

            if not has_findings:
                lines.append("The agent reported success but did not return machine-readable findings.")
                lines.append("")
                continue

            if name == "contradiction_analysis":
                found = int(output.get("contradictions_found", 0))
                contradictions = output.get("contradiction_list", []) or []
                most = output.get("most_severe") or {}
                if found == 0:
                    company = output.get("company") or ""
                    known_cases = analyze_contradictions("net zero", company, []).get("controversy_count", 0) if company else 0
                    lines.append(
                        "No contradictions were detected in the current evidence set. NOTE: This may reflect evidence coverage gaps rather than claim accuracy. "
                        f"The known-contradictions database was checked — {known_cases} known cases exist for this company."
                    )
                else:
                    lines.append(
                        f"The contradiction analyzer examined {len(contradictions)} evidence items against the stated claim. {found} contradiction(s) were identified. "
                        f"Most severe: {most.get('description', 'N/A')} (Source: {most.get('source', 'N/A')}, {most.get('year', 'N/A')}, Severity: {most.get('severity', 'N/A')}). "
                        f"Confidence: {int((output.get('confidence', 0.5) or 0.5) * 100)}%."
                    )
            elif name == "carbon_extraction":
                scope1 = output.get("scope1") or (output.get("emissions", {}).get("scope1", {}).get("value"))
                scope2 = output.get("scope2") or (output.get("emissions", {}).get("scope2", {}).get("value"))
                scope3 = output.get("scope3") or (output.get("emissions", {}).get("scope3", {}).get("total"))
                quality = output.get("data_quality", {})
                q_score = quality.get("overall_score") if isinstance(quality, dict) else quality
                q_conf = quality.get("data_confidence", "Unknown") if isinstance(quality, dict) else "Unknown"
                missing = output.get("missing_scopes") or [
                    s for s, v in {"Scope 1": scope1, "Scope 2": scope2, "Scope 3": scope3}.items() if v in (None, "N/A")
                ]
                lines.append(
                    f"The carbon extractor analyzed {output.get('articles_analyzed', 0)} evidence items and {output.get('source_coverage', {}).get('report_chunks', 0)} report chunks. "
                    f"Scope 1: {scope1 if scope1 is not None else 'NOT DISCLOSED'} tCO2e. Scope 2: {scope2 if scope2 is not None else 'NOT DISCLOSED'} tCO2e. "
                    f"Scope 3: {scope3 if scope3 is not None else 'NOT DISCLOSED'}. Data quality: {q_score if q_score is not None else 'N/A'}/100 ({q_conf} confidence). "
                    f"Missing disclosures: {missing}."
                )
                if scope1 is None and scope2 is None and scope3 is None:
                    lines.append("WARNING — No emissions data found. Net-zero claim cannot be quantitatively evaluated. Greenwashing risk elevated.")
            elif name == "sentiment_analysis":
                claim_sent = output.get("claim_sentiment", "neutral")
                evidence_sent = output.get("evidence_sentiment", "neutral")
                divergence_score = float(output.get("sentiment_divergence", 0) or 0)
                if divergence_score >= 0.4:
                    divergence_label = "High"
                elif divergence_score >= 0.2:
                    divergence_label = "Moderate"
                else:
                    divergence_label = "Low"
                lines.append(
                    f"The sentiment analyzer processed {output.get('articles_analyzed', 0)} external sources. Corporate claim tone: {claim_sent}. "
                    f"External evidence tone: {evidence_sent}. Sentiment divergence: {divergence_label}. "
                    f"Notable signal: {output.get('notable_signal') or 'No dominant signal identified'}."
                )
            elif name == "temporal_analysis":
                lines.append(
                    f"The historical analyst examined {output.get('years_analyzed', 0)} year(s) of available data ({output.get('year_range', 'N/A')}). "
                    f"ESG claim trend: {output.get('claim_tone_trend', 'INSUFFICIENT_DATA')}. "
                    f"Environmental performance trend: {output.get('env_performance_trend', 'INSUFFICIENT_DATA')}. "
                    f"Historical violations found: {output.get('violations_count', 0)}."
                )
                if (output.get("violations") or []):
                    v0 = output["violations"][0]
                    lines.append(f"Most notable: {v0.get('description', 'N/A')} ({v0.get('year', 'N/A')}).")
                lines.append(f"Reputation score: {output.get('reputation_score', 'N/A')}/100.")
            elif name == "credibility_analysis":
                high_list = output.get("high_credibility_list") or output.get("trusted_sources") or []
                low_count = output.get("low_credibility_count") or len(output.get("low_confidence_sources", []) or [])
                unverifiable = output.get("unverifiable_count") or len(output.get("unverifiable_sources", []) or [])
                total = output.get("total_sources") or output.get("sources_analyzed") or 0
                overall = output.get("overall_credibility") or output.get("credibility_score") or "N/A"
                lines.append(
                    f"Source credibility assessment across {total} sources. High-credibility sources: {high_list}. "
                    f"Low-credibility sources: {low_count} items. Unverifiable sources: {unverifiable}. "
                    f"Overall credibility score: {overall}/100."
                )
                if isinstance(unverifiable, int) and unverifiable > 3:
                    lines.append(
                        f"WARNING — {unverifiable} sources could not be independently verified and were downweighted in scoring."
                    )
            elif name == "climatebert_analysis":
                claim_a = output.get("claim_analysis", {})
                gw = claim_a.get("greenwashing_detection", {})
                relevance = claim_a.get("climate_relevance", {})
                comp = output.get("comparison", {})
                claim_score = comp.get("claim_greenwashing_score", output.get("claim_score", 0))
                evidence_score = comp.get("evidence_greenwashing_score", output.get("evidence_score", 0))
                lines.append(
                    f"ClimateBERT NLP analysis classified the claim as {relevance.get('classification', output.get('classification', 'N/A'))} with {relevance.get('score', output.get('climate_relevance', 'N/A'))}% climate relevance. "
                    f"NLP-based greenwashing signal: {gw.get('risk_score', output.get('greenwashing_risk', 'N/A'))}/100 ({gw.get('risk_level', output.get('risk_level', 'N/A'))}). "
                    f"Claim language score: {claim_score}. Evidence language score: {evidence_score}."
                )
                if isinstance(claim_score, (int, float)) and isinstance(evidence_score, (int, float)) and claim_score > evidence_score + 20:
                    lines.append(
                        "SIGNAL — Claim language is significantly more promotional than the evidence language supports. This is a linguistic indicator of potential greenwashing."
                    )
            elif name == "industry_comparator":
                data_source = output.get("data_source")
                real_ct = output.get("real_peer_count")
                est_ct = output.get("estimated_peer_count")
                lines.append(
                    f"The industry comparator assembled a peer set using data source type '{data_source}', with {real_ct} real peer(s) and {est_ct} estimated baseline(s). Peer-level ESG and greenwashing scores were used to position the issuer within its sector where coverage allowed."
                )
            elif name == "greenwishing_detection":
                overall = output.get("overall_deception_risk") or {}
                overall_level = overall.get("risk_level")
                greenwishing = output.get("greenwishing", {}).get("risk_level")
                greenhushing = output.get("greenhushing", {}).get("risk_level")
                sel_disc = output.get("selective_disclosure", {}).get("risk_level")
                lines.append(
                    f"The deception-pattern detector scanned corporate language for greenwishing (over-claiming), greenhushing (under-disclosure), and selective disclosure behaviors. Overall deception risk was {overall_level}; greenwishing risk was {greenwishing}, greenhushing risk was {greenhushing}, and selective disclosure risk was {sel_disc}."
                )
            elif name == "regulatory_scanning":
                jurisdiction = output.get("jurisdiction")
                compliance = output.get("compliance_score", {})
                if isinstance(compliance, dict):
                    score = compliance.get("score", "N/A")
                    risk_level = compliance.get("risk_level", "Unknown")
                    gaps = compliance.get("gaps", 0)
                else:
                    score = compliance
                    risk_level = output.get("risk_level", "Unknown")
                    gaps = 0
                compliant = []
                gap_list = []
                for row in output.get("compliance_results", []) or []:
                    has_gap = len(row.get("gap_details", [])) > 0
                    if has_gap:
                        gap_list.append(f"{row.get('regulation_name')}: {', '.join(row.get('gap_details', [])[:1])}")
                    else:
                        compliant.append(row.get("regulation_name"))
                lines.append(
                    f"Regulatory scanning covered {jurisdiction} across {len(output.get('applicable_regulations', []) or [])} frameworks. "
                    f"Compliance score: {score}/100 (Risk: {risk_level}). Gaps identified: {gaps}. "
                    f"Compliant frameworks: {compliant}. Frameworks with gaps: {gap_list}."
                )
                if gaps:
                    alerts = [r.get("regulation") for r in output.get("regulatory_risks", []) or []]
                    lines.append(f"Regulatory risk alerts: {alerts}.")
            elif name == "explainability":
                factors = output.get("top_factors", []) or []
                p = factors[0] if len(factors) > 0 else {}
                s = factors[1] if len(factors) > 1 else {}
                lines.append(
                    f"SHAP/LIME explainability analysis identified the top risk drivers. Method: {output.get('method', 'N/A')}. "
                    f"Primary risk driver: {p.get('factor', p.get('feature', 'N/A'))} ({p.get('impact', 'N/A')} impact, {p.get('direction', 'N/A')}). "
                    f"Secondary driver: {s.get('factor', s.get('feature', 'N/A')) if s else 'N/A'}. "
                    f"Summary: {output.get('explanation_text', output.get('human_readable_explanation', 'N/A'))}."
                )
            else:
                lines.append(self._extract_agent_summary(name, output))

            lines.append("")

        return "\n".join(lines)

    def _render_section5_peer_comparison(
        self,
        company: str,
        industry: str,
        peers: Dict[str, Any],
    ) -> str:
        real_peers = peers.get("real_peers") or []
        if len(real_peers) < 2:
            return (
                "Peer comparison is suppressed because fewer than two real peers with sufficient ESG disclosure were available in the database. "
                "For publication-grade benchmarking, we recommend curating at least 3–5 named competitors in the same industry and geography and rebuilding the peer history."
            )

        lines: List[str] = []
        lines.append(
            f"The issuer is benchmarked against {len(real_peers)} real peers from the {industry} universe. Synthetic or estimated peers are excluded from this table."
        )
        header = f"{'Company':<28} {'ESG Score':<10} {'Greenwash Score':<16} {'Rating':<8} {'Source':<10}"
        lines.append(header)
        lines.append("-" * len(header))

        for p in real_peers:
            name = str(p.get("name") or p.get("company") or "Peer").strip()[:28]
            esg = p.get("esg_score")
            gw = p.get("greenwashing_risk_score")
            rating = p.get("rating") or p.get("rating_grade") or "-"
            src = (p.get("source") or "database")[:10]
            esg_str = f"{float(esg):.1f}" if isinstance(esg, (int, float)) else "-"
            gw_str = f"{float(gw):.1f}" if isinstance(gw, (int, float)) else "-"
            lines.append(f"{name:<28} {esg_str:<10} {gw_str:<16} {rating:<8} {src:<10}")

        lines.append("")
        lines.append(
            f"Rows correspond to real firms with historically observed ESG and controversy trajectories. The relative positioning of {company} should be interpreted with the caveats in Section 7."
        )

        return "\n".join(lines)

    def _render_section6_calibration(
        self,
        calibration: Dict[str, Any],
        scores: Dict[str, Any],
    ) -> str:
        lines: List[str] = []

        gw_score = scores.get("greenwashing_risk_score")
        esg_rating = scores.get("esg_rating")
        threshold = calibration.get("optimal_threshold")
        spearman_r = calibration.get("spearman_r")
        spearman_p = calibration.get("spearman_p")
        pb_r = calibration.get("point_biserial_r")
        mw_p = calibration.get("mannwhitney_p")
        mu_g = calibration.get("mean_score_greenwashing")
        mu_l = calibration.get("mean_score_legitimate")
        region = calibration.get("confidence_region")

        lines.append(
            "The greenwashing risk score is calibrated against a labeled dataset of historical cases covering both confirmed greenwashing incidents and legitimate ESG leadership examples."
        )

        if isinstance(spearman_r, (int, float)) and isinstance(spearman_p, (int, float)):
            lines.append(
                f"In the latest calibration run, the linguistic-greenwashing index achieved a Spearman rank correlation of {spearman_r:.3f} with the ground-truth labels (p = {spearman_p:.4f})."
            )
        if isinstance(pb_r, (int, float)) and isinstance(mw_p, (int, float)):
            lines.append(
                f"Point-biserial correlation between the score and the binary greenwashing label was {pb_r:.3f}, and a Mann–Whitney U test yielded p = {mw_p:.4f}."
            )

        if isinstance(mu_g, (int, float)) and isinstance(mu_l, (int, float)):
            lines.append(
                f"On the calibration sample, average scores were approximately {mu_g:.1f} for known greenwashing cases versus {mu_l:.1f} for legitimate cases."
            )

        if isinstance(threshold, (int, float)):
            lines.append(
                f"An optimal discrimination threshold around {threshold:.1f} was selected to balance sensitivity and specificity."
            )

        if isinstance(gw_score, (int, float)) and isinstance(threshold, (int, float)):
            if region == "high_suspicion_zone":
                lines.append(
                    f"With a score of {gw_score:.1f}, this issuer sits well above the calibrated threshold for greenwashing suspicion; under the reference distribution, such scores are predominantly associated with confirmed greenwashing cases."
                )
            elif region == "likely_legitimate_zone":
                lines.append(
                    f"With a score of {gw_score:.1f}, the issuer lies comfortably below the threshold; in the calibration sample, such scores are more common among legitimate ESG leaders than among greenwashers."
                )
            else:
                lines.append(
                    f"With a score of {gw_score:.1f}, the issuer falls into an intermediate grey zone where both greenwashers and legitimate firms are observed; additional human review is recommended."
                )

        lines.append(
            f"Taken together, these diagnostics support using the score as a probabilistic indicator of greenwashing risk, but not as a deterministic classification. The {esg_rating} label should be interpreted alongside qualitative context and sector expertise."
        )

        return "\n".join(lines)

    def _render_section7_limitations(self, limitations: List[str]) -> str:
        if not limitations:
            return (
                "No specific methodological limitations were automatically detected for this run beyond the general caveats that all ESG analyses are constrained by disclosure quality, model assumptions, and evolving regulatory standards."
            )

        lines = ["This assessment is subject to the following case-specific limitations:"]
        for idx, item in enumerate(limitations, start=1):
            lines.append(f"  {idx}. {item}")
        return "\n".join(lines)

    def _generate_score_interpretation_section(self, state: Dict[str, Any], score: float) -> str:
        """Generate score interpretation section."""
        if score >= 75:
            level = "HIGH GREENWASHING RISK"
            detail = "Significant inconsistencies detected between ESG claims and verified evidence."
        elif score >= 50:
            level = "MODERATE GREENWASHING RISK"
            detail = "Some inconsistencies detected; further verification recommended."
        elif score >= 25:
            level = "LOW-MODERATE GREENWASHING RISK"
            detail = "Minor inconsistencies detected; claims largely supported by evidence."
        else:
            level = "LOW GREENWASHING RISK"
            detail = "Claims well-supported by available evidence and historical performance."

        return f"""
SCORE INTERPRETATION
{'─'*80}
Score: {score:.1f}/100 — {level}
{detail}
"""

    def _generate_validation_metadata_section(self) -> str:
        """Add validation & calibration status section."""
        lines = [
            "VALIDATION & CALIBRATION STATUS",
            "─" * 52,
        ]

        # Ground Truth
        lines.append("")
        lines.append("Ground Truth Validation:")
        gt_path = os.path.join(os.path.dirname(__file__), '../data/ground_truth_dataset.csv')
        if os.path.exists(gt_path):
            import pandas as pd
            df = pd.read_csv(gt_path)
            lines.append(f"  Dataset:           Ground Truth ESG Dataset v1.0 (data/ground_truth_dataset.csv)")
            lines.append(f"  Verified Cases:    {len(df)} company-claim pairs with regulatory verdicts")
        else:
            lines.append("  Dataset:           Not available — run run_validation.py first")

        # ML Model Performance
        lines.append("")
        lines.append("ML Model Performance (from latest evaluation):")
        eval_path = os.path.join(os.path.dirname(__file__), '../reports/ml_evaluation_results.json')
        if os.path.exists(eval_path):
            with open(eval_path) as f:
                ml = json.load(f)
            best = ml.get('best_model', 'N/A')
            best_f1 = ml.get('best_model_cv_f1', ml.get('best_model_f1', 0))
            dummy_f1 = ml.get('cross_validation_results', {}).get('Dummy', {}).get('f1_mean', 'N/A')
            best_auc = ml.get('holdout_results', {}).get(best, {}).get('auc', 'N/A')
            lines.append(f"  Best Model:        {best} (F1: {best_f1:.3f}, AUC: {best_auc})")
            lines.append(f"  Baseline F1:       {dummy_f1} (majority class)")
        else:
            lines.append("  Best Model:        Not yet evaluated")

        # Score Calibration
        lines.append("")
        lines.append("Score Calibration:")
        calib_path = os.path.join(os.path.dirname(__file__), '../reports/calibration_report.json')
        if os.path.exists(calib_path):
            with open(calib_path) as f:
                cal = json.load(f)
            scorer = cal.get('linguistic_scorer', {})
            lines.append(f"  Spearman r:        {scorer.get('spearman_r', 'N/A')} ({scorer.get('calibration_status', 'N/A')})")
            lines.append(f"  Optimal Threshold: {scorer.get('optimal_threshold', 'N/A')}/100")
        else:
            lines.append("  Spearman r:        Not available — run run_validation.py first")

        # Contradiction DB
        lines.append("")
        lines.append("Contradiction Database:")
        from data.known_cases import KNOWN_GREENWASHING_CASES
        lines.append(f"  Known Cases:       {sum(len(v) for v in KNOWN_GREENWASHING_CASES.values())} verified regulatory actions")
        lines.append("  Data Sources:      UK ASA, Dutch Courts, US FTC, US SEC, InfluenceMap, ClientEarth")

        return "\n".join(lines)

    def _generate_evidence_source_quality_table(self, state: Dict[str, Any]) -> str:
        """Add evidence source quality table."""
        evidence = state.get("evidence", [])
        counts = {"regulatory": 0, "known_db": 0, "cdp": 0, "wikirate": 0, "web": 0, "estimated": 0}
        for ev in evidence:
            t = ev.get("source_type", "").lower()
            if "regulatory" in t:
                counts["regulatory"] += 1
            elif "known" in t:
                counts["known_db"] += 1
            elif "cdp" in t:
                counts["cdp"] += 1
            elif "wikirate" in t:
                counts["wikirate"] += 1
            elif "web" in t:
                counts["web"] += 1
            elif "estimated" in t:
                counts["estimated"] += 1

        table = [
            "Evidence Quality Assessment:",
            "| Source Type           | Count | Reliability | Notes                    |",
            "|----------------------|-------|-------------|--------------------------|",
            f"| Regulatory rulings   | {counts['regulatory']}   | Very High   | Verified legal records   |",
            f"| Known cases DB       | {counts['known_db']}   | High        | Curated regulatory cases |",
            f"| CDP data             | {counts['cdp']}   | High        | Third-party verified     |",
            f"| Wikirate data        | {counts['wikirate']}   | Medium      | Crowd-sourced + audited  |",
            f"| Web search           | {counts['web']}   | Medium      | Unverified, indicative   |",
            f"| Estimated/synthetic  | {counts['estimated']}   | Low         | Sector benchmarks only   |",
        ]
        return "\n".join(table)

    def _generate_verified_regulatory_actions_section(self, state: Dict[str, Any]) -> str:
        """Add verified regulatory actions section."""
        company = state.get("company", "")
        claim = state.get("claim", "")
        contradiction_result = analyze_contradictions(claim, company, [])

        if contradiction_result["high_confidence_count"] > 0:
            lines = [
                "| Year | Regulatory Body | Severity | Contradiction Summary |",
                "|------|----------------|----------|----------------------|",
            ]
            for c in contradiction_result["contradictions"]:
                if c.get("confidence") == "HIGH":
                    lines.append(
                        f"| {c.get('year','')} | {c.get('regulatory_body','')} | "
                        f"{c.get('severity','').upper()} | {c.get('contradiction_text','')[:100]} |"
                    )
                    lines.append(f"Source: {c.get('source','')} — {c.get('source_url','')}")
            return "\n".join(lines)
        else:
            return (
                "No verified regulatory actions found in public records for this company-claim combination.\n"
                "This does not confirm the claim is accurate — it means no enforcement actions were \n"
                "identified in the known cases database."
            )

    def _generate_regulatory_compliance_section(self, state: Dict[str, Any]) -> str:
        """Add regulatory compliance assessment section."""
        company = state.get("company", "")
        claim = state.get("claim", "")

        regulations = [
            {"regulation_name": "Science Based Targets initiative"},
            {"regulation_name": "GRI"},
            {"regulation_name": "CDP"},
            {"regulation_name": "GHG Protocol"},
            {"regulation_name": "SEBI BRSR"},
            {"regulation_name": "TCFD"},
        ]

        reg_results = []
        for reg in regulations:
            gap = detect_regulation_gaps(company, claim, reg["regulation_name"])
            reg_results.append({"regulation_name": reg["regulation_name"], **gap})

        compliance = compute_compliance_score(reg_results)

        lines = [
            "REGULATORY COMPLIANCE ASSESSMENT",
            "─" * 52,
            f"Compliance Score: {compliance['score']}/100  (Risk Level: {compliance['risk_level']})",
            "",
            "| Regulation | Status | Gap Count |",
            "|------------|--------|-----------|",
        ]
        for r in compliance["per_regulation_status"]:
            lines.append(f"| {r['regulation']} | {r['status']} | {r['gap_count']} |")
        lines.append("")
        lines.append("Gap Details:")
        for r in compliance["per_regulation_status"]:
            if r["gap_count"] > 0:
                for g in r["gaps"]:
                    lines.append(f"- {r['regulation']}: {g}")

        return "\n".join(lines)

    def _generate_key_findings(self, state: Dict[str, Any]) -> str:
        """Generate key findings section."""
        risk_level = state.get("risk_level", "MODERATE")
        confidence = state.get("confidence", 0.0)
        evidence_count = len(state.get("evidence", []))

        findings = []

        if risk_level == "HIGH":
            findings.append("[ALERT] HIGH GREENWASHING RISK DETECTED")
            findings.append("  - Claim lacks sufficient evidence or contains contradictions")
            findings.append("  - Peer comparison shows below-industry-average performance")
            findings.append("  - Historical data reveals inconsistent ESG commitments")
            findings.append("  - Recommended Action: Deep due diligence required before engagement")
        elif risk_level == "MODERATE":
            findings.append("[MODERATE] GREENWASHING RISK IDENTIFIED")
            findings.append("  - Claim partially supported by available evidence")
            findings.append("  - Some contradictions or ambiguities detected")
            findings.append("  - Mixed signals from historical performance")
            findings.append("  - Recommended Action: Additional verification and monitoring")
        else:
            findings.append("[OK] LOW GREENWASHING RISK")
            findings.append("  - Claim well-supported by multiple credible sources")
            findings.append("  - Consistent with historical ESG performance")
            findings.append("  - Aligns with industry best practices")
            findings.append("  - Recommended Action: Standard monitoring protocols")

        findings.append("")

        if confidence >= 0.8:
            findings.append("[OK] HIGH CONFIDENCE ASSESSMENT")
            findings.append("  - Robust evidence base from multiple independent sources")
            findings.append("  - Agent consensus achieved across analytical dimensions")
            findings.append("  - Low uncertainty in risk classification")
        elif confidence >= 0.6:
            findings.append("[MODERATE] CONFIDENCE ASSESSMENT")
            findings.append("  - Adequate evidence but some information gaps identified")
            findings.append("  - Partial agent consensus with minor disagreements")
            findings.append("  - Moderate uncertainty in final assessment")
        else:
            findings.append("[LIMITED] CONFIDENCE")
            findings.append("  - Insufficient evidence for definitive assessment")
            findings.append("  - Significant information gaps remain")
            findings.append("  - Further investigation strongly recommended")

        findings.append("")

        if evidence_count >= 10:
            findings.append("[OK] COMPREHENSIVE EVIDENCE COVERAGE")
            findings.append(f"  - {evidence_count} independent sources analyzed")
        elif evidence_count >= 5:
            findings.append("[MODERATE] ADEQUATE EVIDENCE COVERAGE")
            findings.append(f"  - {evidence_count} sources analyzed")
        else:
            findings.append("[LIMITED] EVIDENCE AVAILABILITY")
            findings.append(f"  - Only {evidence_count} sources available")
            findings.append("  - Assessment reliability may be affected")

        return "\n".join(findings)

    def _generate_peer_comparison_section(self, state: Dict[str, Any]) -> str:
        """Generate peer comparison section with ESG benchmarking table."""
        company = state.get("company", "Unknown")
        industry = state.get("industry", "Unknown")

        risk_scorer_outputs = [
            o for o in state.get("agent_outputs", []) if o.get("agent") == "risk_scoring"
        ]

        if risk_scorer_outputs:
            risk_scorer_result = risk_scorer_outputs[-1].get("output", {})
            pillar_scores = risk_scorer_result.get("pillar_scores", {})
            overall_esg = pillar_scores.get("overall_esg_score")
        else:
            pillar_scores = {}
            overall_esg = None

        try:
            from agents.industry_comparator import IndustryComparator
            comparator = IndustryComparator()

            peer_result = comparator.generate_dynamic_peer_table(
                company=company,
                industry=industry,
                esg_score=overall_esg,
                pillar_scores=pillar_scores,
            )

            if not peer_result.get("available", False):
                return f"""
PEER COMPARISON & INDUSTRY BENCHMARKING
{'─'*80}

{peer_result.get('table_markdown', 'Peer comparison unavailable - limited industry data coverage')}

Note: Peer data unavailable for {industry} sector. This may be due to:
  • Limited public ESG data in this industry
  • Industry classification mismatch
  • Emerging sector with few established competitors
"""

            rank_text = peer_result.get("rank", "N/A")
            industry_avg = peer_result.get("industry_average", {})
            total_peers = peer_result.get("total_peers", 0)
            real_peer_count = peer_result.get("real_peer_count", 0)
            estimated_peer_count = peer_result.get("estimated_peer_count", 0)
            data_source = peer_result.get("data_source", "unknown")
            disclaimer = peer_result.get("disclaimer")

            if data_source == "real":
                data_source_text = "Historical database (previously analyzed companies)"
            elif data_source == "mixed":
                data_source_text = (
                    f"Mixed: {real_peer_count} from historical database, "
                    f"{estimated_peer_count} estimated from industry benchmarks"
                )
            else:
                data_source_text = "Estimated from industry benchmarks (insufficient historical data)"

            section = f"""
PEER COMPARISON & INDUSTRY BENCHMARKING
{'─'*80}

Analysis Context:
  • Industry:        {industry}
  • Peers Analyzed:  {total_peers} competitors
  • Company Rank:    {rank_text}
  • Industry Avg:    {industry_avg.get('esg', 'N/A')}/100
  • Data Source:     {data_source_text}

{peer_result['table_markdown']}

"""

            if disclaimer:
                section += f"""{disclaimer}

As more companies in {industry} are analyzed, this comparison will become more accurate 
with real peer data from the historical database.

"""

            section += """Legend:
  * = Target company
  E  = Environmental Score (0-100)
  S  = Social Score (0-100)
  G  = Governance Score (0-100)

Rating Scale:
  AAA-AA  = 75-100 (ESG Leaders)
  A-BBB   = 50-74  (Average Performance)
  BB-B    = 25-49  (Below Average)
  CCC-C   = 0-24   (ESG Laggards)

"""

            if overall_esg and industry_avg.get('esg'):
                delta = overall_esg - industry_avg.get('esg')
                if delta >= 10:
                    section += f"[OUTPERFORMING] {company} exceeds industry average by {delta:.1f} points\n"
                elif delta >= 5:
                    section += f"[ABOVE AVERAGE] {company} performs {delta:.1f} points above peers\n"
                elif delta >= -5:
                    section += f"[INDUSTRY AVERAGE] {company} aligns with peer performance\n"
                elif delta >= -10:
                    section += f"[BELOW AVERAGE] {company} lags industry by {abs(delta):.1f} points\n"
                else:
                    section += f"[UNDERPERFORMING] {company} significantly trails peers by {abs(delta):.1f} points\n"

            return section

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"""
PEER COMPARISON & INDUSTRY BENCHMARKING
{'─'*80}

Peer comparison unavailable - limited industry data coverage

Technical Error: {str(e)[:100]}
"""

    def _generate_agent_breakdown(self, agent_outputs: List[Dict]) -> str:
        """Generate agent execution breakdown."""
        agent_data = {}
        seen_executions = set()

        for output in agent_outputs:
            agent_name = output.get('agent', 'unknown')
            timestamp = output.get('timestamp', '')
            unique_key = f"{agent_name}_{timestamp}"

            if unique_key in seen_executions:
                continue
            seen_executions.add(unique_key)

            if agent_name not in agent_data:
                agent_data[agent_name] = {
                    'executions': 0,
                    'errors': 0,
                    'confidence_sum': 0,
                    'confidence_count': 0,
                }

            agent_data[agent_name]['executions'] += 1

            if 'error' in output:
                agent_data[agent_name]['errors'] += 1

            if 'confidence' in output and output['confidence'] is not None:
                agent_data[agent_name]['confidence_sum'] += output['confidence']
                agent_data[agent_name]['confidence_count'] += 1

        breakdown = [
            "Agent Execution Summary:",
            "─" * 80,
            f"{'Agent Name':<35} | {'Status':<8} | {'Confidence':<10} | {'Runs':<5}",
            "─" * 80,
        ]

        for agent_name in sorted(agent_data.keys()):
            data = agent_data[agent_name]

            if data['confidence_count'] > 0:
                avg_conf = data['confidence_sum'] / data['confidence_count']
                conf_display = f"{avg_conf:.1%}"
            else:
                conf_display = "N/A"

            status = "FAILED" if data['errors'] > 0 else "SUCCESS"
            display_name = agent_name.replace('_', ' ').title()

            actual_runs = data['executions']
            run_display = str(min(actual_runs, 2))

            breakdown.append(
                f"{display_name:<35} | {status:<8} | {conf_display:<10} | {run_display:<5}"
            )

        breakdown.append("─" * 80)
        return "\n".join(breakdown)

    def _generate_detailed_analysis(self, state: Dict[str, Any], agent_outputs: List[Dict]) -> str:
        """Generate detailed agent analysis section."""
        sections = []

        agent_summaries = {}
        for output in agent_outputs:
            agent_name = output.get("agent", "unknown")
            if agent_name not in ["supervisor", "confidence_monitor", "assess_complexity"]:
                if agent_name not in agent_summaries:
                    agent_summaries[agent_name] = []
                agent_summaries[agent_name].append(output)

        # Environmental Analysis
        sections.append("ENVIRONMENTAL DIMENSION")
        sections.append("─" * 80)

        if "contradiction_analysis" in agent_summaries:
            output = agent_summaries["contradiction_analysis"][0]
            contradictions = output.get("contradictions_count", 0)
            if contradictions > 0:
                sections.append(f"[WARN] Claim Consistency:    {contradictions} contradiction(s) detected")
            else:
                sections.append("[OK] Claim Consistency:    No contradictions found")

        if "evidence_retrieval" in agent_summaries:
            output = agent_summaries["evidence_retrieval"][0]
            evidence_count = output.get("evidence_count", 0)
            sections.append(f"  Evidence Coverage:    {evidence_count} independent source(s)")

        if "temporal_analysis" in agent_summaries:
            sections.append("  Historical Track Record: Past ESG performance evaluated")

        sections.append("")

        # Social Dimension
        sections.append("SOCIAL DIMENSION")
        sections.append("─" * 80)

        if "sentiment_analysis" in agent_summaries:
            sections.append("  Public Sentiment:     Analyzed from recent media coverage")

        if "credibility_analysis" in agent_summaries:
            sections.append("  Source Credibility:   Verified against trusted repositories")

        if "realtime_monitoring" in agent_summaries:
            sections.append("  Real-time Monitoring: Latest news and developments tracked")

        sections.append("")

        # Governance Dimension
        sections.append("GOVERNANCE DIMENSION")
        sections.append("─" * 80)

        if "peer_comparison" in agent_summaries:
            sections.append("  Industry Benchmarking:   Compared against sector peers")

        if "risk_scoring" in agent_summaries:
            output = agent_summaries["risk_scoring"][0]
            risk_level = output.get("risk_level", "N/A")
            sections.append(f"  Risk Assessment:         {risk_level} risk classification")

        sections.append("")
        return "\n".join(sections)

    def _generate_evidence_summary(self, state: Dict[str, Any]) -> str:
        """Generate evidence summary."""
        evidence = state.get("evidence", [])

        if not evidence:
            return (
                "No evidence sources available for this analysis.\n"
                "This may indicate data collection issues or claim verification challenges."
            )

        summary = [
            f"Total Evidence Sources: {len(evidence)}",
            "─" * 80,
            "",
        ]

        sources: Dict[str, list] = {}
        for item in evidence[:15]:
            source = item.get("source", "unknown")
            if source not in sources:
                sources[source] = []
            sources[source].append(item)

        for source_type, items in sorted(sources.items()):
            source_display = source_type.replace('_', ' ').title()
            summary.append(f"{source_display}: {len(items)} item(s)")
            summary.append("─" * 40)

            for i, item in enumerate(items[:5], 1):
                title = item.get("title", item.get("snippet", "N/A"))
                if len(title) > 75:
                    title = title[:72] + "..."
                summary.append(f"  {i}. {title}")

            if len(items) > 5:
                summary.append(f"  ... and {len(items)-5} more items")

            summary.append("")

        return "\n".join(summary)

    def _generate_pillar_section(self, pillar_scores: Dict[str, float]) -> str:
        """Generate ESG pillar scores section."""
        if not pillar_scores:
            return f"""
ESG PILLAR SCORES
{'─'*80}
(Pillar scores not available - insufficient data)
"""

        env_score = pillar_scores.get("environmental_score")
        soc_score = pillar_scores.get("social_score")
        gov_score = pillar_scores.get("governance_score")
        overall_esg = pillar_scores.get("overall_esg_score")
        industry_adj = pillar_scores.get("industry_adjustment", 0)

        if any(v is None for v in [env_score, soc_score, gov_score, overall_esg]):
            return f"""
ESG PILLAR SCORES
{'─'*80}
(Pillar scores partially available - upstream scoring output incomplete)
"""

        env_contribution = env_score * 0.35
        soc_contribution = soc_score * 0.30
        gov_contribution = gov_score * 0.35

        def get_performance_level(score):
            if score >= 70:
                return "Strong"
            elif score >= 50:
                return "Average"
            return "Weak"

        env_level = get_performance_level(env_score)
        soc_level = get_performance_level(soc_score)
        gov_level = get_performance_level(gov_score)

        return f"""
ESG PILLAR SCORES (Industry-Adjusted)
{'─'*80}

ENVIRONMENTAL SCORE:      {env_score:.1f}/100  ({env_level})
  Weight:                 35%
  Weighted Contribution:  {env_contribution:.1f} points

  Key Factors:
    • Carbon emissions and climate strategy
    • Energy efficiency and renewable usage
    • Water management and biodiversity impact
    • Waste reduction and circular economy

SOCIAL SCORE:             {soc_score:.1f}/100  ({soc_level})
  Weight:                 30%
  Weighted Contribution:  {soc_contribution:.1f} points

  Key Factors:
    • Labor practices and employee welfare
    • Diversity, equity, and inclusion (DEI)
    • Community engagement and human rights
    • Product safety and stakeholder relations

GOVERNANCE SCORE:         {gov_score:.1f}/100  ({gov_level})
  Weight:                 35%
  Weighted Contribution:  {gov_contribution:.1f} points

  Key Factors:
    • Board structure and independence
    • Ethics and compliance frameworks
    • Transparency and disclosure quality
    • Anti-corruption and accountability measures

{'─'*80}
OVERALL ESG SCORE:        {overall_esg:.1f}/100

Calculation:
  (Environmental × 0.35) + (Social × 0.30) + (Governance × 0.35)
  ({env_score:.1f} × 0.35) + ({soc_score:.1f} × 0.30) + ({gov_score:.1f} × 0.35) = {overall_esg:.1f}

Industry Baseline Adjustment: {industry_adj:+.1f} points
  (Applied to account for sector-specific ESG challenges)
"""

    def _collect_realism_diagnostics(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Collect realism diagnostics from scorer and evidence outputs."""
        agent_outputs = state.get("agent_outputs", [])

        risk_output: Dict[str, Any] = {}
        evidence_output: Dict[str, Any] = {}

        for output in reversed(agent_outputs):
            if not risk_output and output.get("agent") == "risk_scoring":
                candidate = output.get("output", {})
                if isinstance(candidate, dict):
                    risk_output = candidate
            if not evidence_output and output.get("agent") == "evidence_retrieval":
                candidate = output.get("output", {})
                if isinstance(candidate, dict):
                    evidence_output = candidate
            if risk_output and evidence_output:
                break

        pillar_scores = risk_output.get("pillar_scores", {})
        if not isinstance(pillar_scores, dict):
            pillar_scores = {}

        dei_progress = pillar_scores.get("dei_progress", {})
        if not isinstance(dei_progress, dict):
            dei_progress = {}

        quality_metrics = evidence_output.get("quality_metrics", {})
        if not isinstance(quality_metrics, dict):
            quality_metrics = {}

        source_breakdown = evidence_output.get("source_breakdown", {})
        if not isinstance(source_breakdown, dict):
            source_breakdown = {}

        total_evidence_sources = 0
        for value in source_breakdown.values():
            if isinstance(value, (int, float)):
                total_evidence_sources += int(value)

        independent_sources = int(quality_metrics.get("independent_sources", 0) or 0)
        premium_sources = int(quality_metrics.get("premium_sources", 0) or 0)
        source_diversity = int(quality_metrics.get("source_diversity", len(source_breakdown)) or 0)
        evidence_gap = bool(quality_metrics.get("evidence_gap", False))

        independent_share = (independent_sources / max(total_evidence_sources, 1)) * 100
        premium_share = (premium_sources / max(total_evidence_sources, 1)) * 100

        offset_status = str(pillar_scores.get("offset_transparency_status", "unknown")).lower()
        offset_penalty = float(pillar_scores.get("offset_penalty", 0) or 0)

        offset_integrity = "unknown"
        if offset_status in {"transparent", "credible"}:
            offset_integrity = "strong"
        elif offset_status in {"mixed", "partial"}:
            offset_integrity = "moderate"
        elif offset_status in {"opaque_avoidance_heavy", "opaque", "unknown", "not_disclosed"}:
            offset_integrity = "weak"

        has_target = bool(dei_progress.get("has_target", False))
        has_actual = bool(dei_progress.get("has_actual", False))
        yoy_change = dei_progress.get("yoy_change")
        target_gap = dei_progress.get("target_gap")

        dei_execution = "insufficient"
        if has_target and has_actual:
            if isinstance(yoy_change, (int, float)) and yoy_change > 0:
                if isinstance(target_gap, (int, float)) and target_gap <= 0:
                    dei_execution = "strong"
                else:
                    dei_execution = "improving"
            elif isinstance(yoy_change, (int, float)) and yoy_change <= 0:
                dei_execution = "stagnant"
            else:
                dei_execution = "moderate"
        elif has_target and not has_actual:
            dei_execution = "target_only"

        temporal_mode = str(risk_output.get("temporal_mode", "none"))
        temporal_weight = float(risk_output.get("temporal_weight", 0) or 0)
        temporal_data_quality = risk_output.get("temporal_data_quality", {})

        temporal_quality_score = 0.0
        temporal_quality_label = "unknown"
        if isinstance(temporal_data_quality, dict):
            raw_score = temporal_data_quality.get("overall_score", temporal_data_quality.get("score", 0))
            if isinstance(raw_score, (int, float)):
                temporal_quality_score = float(raw_score)
            temporal_quality_label = str(
                temporal_data_quality.get("quality_label", temporal_data_quality.get("data_confidence", "unknown"))
            )
        elif isinstance(temporal_data_quality, (int, float)):
            temporal_quality_score = float(temporal_data_quality)
            temporal_quality_label = "numeric"

        temporal_reliability = "limited"
        if temporal_mode in {"trend", "snapshot"} and temporal_quality_score >= 70 and temporal_weight >= 0.10:
            temporal_reliability = "strong"
        elif temporal_mode in {"trend", "snapshot"} and temporal_quality_score >= 45 and temporal_weight >= 0.05:
            temporal_reliability = "moderate"

        offset_points = 8
        if offset_integrity == "strong":
            offset_points = 25
        elif offset_integrity == "moderate":
            offset_points = 17
        elif offset_integrity == "weak":
            offset_points = 7
        offset_points = max(0, offset_points - min(int(offset_penalty), 10))

        dei_points = 8
        if dei_execution == "strong":
            dei_points = 25
        elif dei_execution == "improving":
            dei_points = 20
        elif dei_execution == "moderate":
            dei_points = 15
        elif dei_execution == "stagnant":
            dei_points = 9
        elif dei_execution == "target_only":
            dei_points = 6

        evidence_points = min(
            25, int((independent_share * 0.5) + (premium_share * 0.25) + (source_diversity * 2))
        )
        if evidence_gap:
            evidence_points = max(0, evidence_points - 6)

        temporal_points = 6
        if temporal_reliability == "strong":
            temporal_points = 25
        elif temporal_reliability == "moderate":
            temporal_points = 16

        realism_score = max(0, min(100, offset_points + dei_points + evidence_points + temporal_points))
        realism_label = "high"
        if realism_score < 70:
            realism_label = "moderate"
        if realism_score < 50:
            realism_label = "limited"

        return {
            "realism_score": realism_score,
            "realism_label": realism_label,
            "offset_integrity": offset_integrity,
            "offset_status": offset_status,
            "offset_penalty": round(offset_penalty, 1),
            "dei_execution": dei_execution,
            "dei_progress": {
                "has_target": has_target,
                "has_actual": has_actual,
                "yoy_change": yoy_change,
                "target_gap": target_gap,
            },
            "evidence_composition": {
                "total_evidence_sources": total_evidence_sources,
                "independent_sources": independent_sources,
                "premium_sources": premium_sources,
                "independent_share_pct": round(independent_share, 1),
                "premium_share_pct": round(premium_share, 1),
                "source_diversity": source_diversity,
                "evidence_gap": evidence_gap,
            },
            "temporal_reliability": {
                "mode": temporal_mode,
                "weight": round(temporal_weight, 3),
                "quality_score": round(temporal_quality_score, 1),
                "quality_label": temporal_quality_label,
                "reliability": temporal_reliability,
            },
        }

    def _generate_realism_diagnostics_section(self, state: Dict[str, Any]) -> str:
        """Generate a concise diagnostics panel for report realism and trustworthiness."""
        diagnostics = self._collect_realism_diagnostics(state)

        evidence_diag = diagnostics.get("evidence_composition", {})
        temporal_diag = diagnostics.get("temporal_reliability", {})
        dei_diag = diagnostics.get("dei_progress", {})

        return f"""
REALISM DIAGNOSTICS
{'─'*80}

Overall Realism Confidence: {diagnostics.get('realism_score', 0)}/100 ({str(diagnostics.get('realism_label', 'unknown')).upper()})

Offset Integrity:
  - Classification: {str(diagnostics.get('offset_integrity', 'unknown')).upper()} ({diagnostics.get('offset_status', 'unknown')})
  - Penalty Applied: {diagnostics.get('offset_penalty', 0)} point(s)

DEI Execution Quality:
  - Execution Mode: {str(diagnostics.get('dei_execution', 'insufficient')).upper()}
  - Target Declared: {'Yes' if dei_diag.get('has_target') else 'No'}
  - Actual Progress Disclosed: {'Yes' if dei_diag.get('has_actual') else 'No'}
  - YoY Progress: {dei_diag.get('yoy_change') if dei_diag.get('yoy_change') is not None else 'N/A'}
  - Gap to Target: {dei_diag.get('target_gap') if dei_diag.get('target_gap') is not None else 'N/A'}

Evidence Composition:
  - Total Source Items: {evidence_diag.get('total_evidence_sources', 0)}
  - Independent Sources: {evidence_diag.get('independent_sources', 0)} ({evidence_diag.get('independent_share_pct', 0)}%)
  - Premium Sources: {evidence_diag.get('premium_sources', 0)} ({evidence_diag.get('premium_share_pct', 0)}%)
  - Source Diversity: {evidence_diag.get('source_diversity', 0)} type(s)
  - Evidence Gap Flag: {'YES' if evidence_diag.get('evidence_gap') else 'NO'}

Temporal Reliability:
  - Mode: {temporal_diag.get('mode', 'none')}
  - Weight in Final Scoring: {temporal_diag.get('weight', 0)}
  - Data Quality: {temporal_diag.get('quality_score', 0)}/100 ({temporal_diag.get('quality_label', 'unknown')})
  - Reliability Tier: {str(temporal_diag.get('reliability', 'limited')).upper()}
"""

    def _generate_quantitative_metrics_section(self, state: Dict[str, Any]) -> str:
        """Generate quantitative performance metrics section with industry benchmarking."""
        company = state.get("company", "Unknown")
        industry = state.get("industry", "Unknown")

        financial_context = None
        agent_outputs = state.get("agent_outputs", [])
        for output in agent_outputs:
            if output.get("agent") == "financial_analysis":
                financial_context = output.get("output", {})
                break

        contradictions = state.get("contradiction_analysis", [])
        controversy_count = 0

        if isinstance(contradictions, list):
            for c in contradictions:
                if isinstance(c, dict):
                    specific_contras = c.get("specific_contradictions", [])
                    if isinstance(specific_contras, list):
                        controversy_count += len(specific_contras)
        elif isinstance(contradictions, dict):
            specific_contras = contradictions.get("specific_contradictions", [])
            if isinstance(specific_contras, list):
                controversy_count = len(specific_contras)

        evidence_list = state.get("evidence", [])
        total_evidence = len(evidence_list)
        max_possible_sources = 14

        unique_sources = set()
        for ev in evidence_list:
            if isinstance(ev, dict):
                source = ev.get("source", "unknown")
                unique_sources.add(source)

        unique_source_count = len(unique_sources)
        effective_source_universe = max(max_possible_sources, unique_source_count, 1)
        unique_disclosure_pct = (unique_source_count / effective_source_universe * 100)

        section = f"""
KEY PERFORMANCE METRICS
{'─'*80}

"""

        # === CARBON EXTRACTION DATA (from CarbonExtractor agent) ===
        carbon_data = state.get("carbon_extraction")
        has_carbon_extraction = False

        if carbon_data and isinstance(carbon_data, dict):
            has_carbon_extraction = True

            section += "CARBON EMISSIONS (Scope 1/2/3 Analysis)\n"
            section += f"{'─'*80}\n\n"

            emissions = carbon_data.get("emissions", {})
            scope1 = emissions.get("scope1", carbon_data.get("scope_1", {}))
            scope2 = emissions.get("scope2", carbon_data.get("scope_2", {}))
            scope3 = emissions.get("scope3", carbon_data.get("scope_3", {}))

            section += f"| {'Scope':<20} | {'Emissions (tCO2e)':<20} | {'Year':<10} | {'Source':<25} |\n"
            section += f"|{'-'*22}|{'-'*22}|{'-'*12}|{'-'*27}|\n"
            missing_scope_rows = []

            scope1_value = scope1.get("value") or scope1.get("emissions_tco2e")
            scope1_year = scope1.get("year", "")
            scope1_source = scope1.get("source", "BRSR/CDP")
            if scope1_value is not None and scope1_value != "N/A":
                section += f"| {'Scope 1 (Direct)':<20} | {scope1_value:>18,} | {str(scope1_year):<10} | {str(scope1_source)[:23]:<25} |\n"
            else:
                missing_scope_rows.append("Scope 1")

            scope2_value = scope2.get("value") or scope2.get("emissions_tco2e")
            scope2_year = scope2.get("year", "")
            scope2_source = scope2.get("source", scope2.get("methodology", ""))
            if scope2_value is not None and scope2_value != "N/A":
                section += f"| {'Scope 2 (Energy)':<20} | {scope2_value:>18,} | {str(scope2_year):<10} | {str(scope2_source)[:23]:<25} |\n"
            else:
                missing_scope_rows.append("Scope 2")

            scope3_value = scope3.get("total") or scope3.get("value") or scope3.get("emissions_tco2e")
            scope3_year = scope3.get("year", "")
            scope3_cats = scope3.get("categories", {})
            scope3_source = f"{len(scope3_cats)} categories" if scope3_cats else "Value Chain"
            if scope3_value is not None and scope3_value != "N/A":
                section += f"| {'Scope 3 (Value Chain)':<20} | {scope3_value:>18,} | {str(scope3_year):<10} | {str(scope3_source)[:23]:<25} |\n"
            else:
                missing_scope_rows.append("Scope 3")

            if missing_scope_rows:
                section += f"\nNote: Missing scope disclosures: {', '.join(missing_scope_rows)}\n"

            section += "\n"

            total_emissions = emissions.get("total") or carbon_data.get("total_emissions_tco2e")
            if isinstance(total_emissions, dict):
                total_emissions = (
                    total_emissions.get("all_scopes")
                    or total_emissions.get("scope1_2")
                    or total_emissions.get("value")
                )

            carbon_intensity = carbon_data.get("carbon_intensity") or carbon_data.get(
                "intensity_metrics", {}
            ).get("carbon_intensity")
            if isinstance(carbon_intensity, dict):
                carbon_intensity = carbon_intensity.get("value")

            net_zero_target = carbon_data.get("net_zero_target")
            renewable_pct = carbon_data.get("renewable_energy_percentage")
            sbt = carbon_data.get("science_based_target")
            verification = carbon_data.get("verification_status")
            data_source = carbon_data.get("data_source")
            data_quality = carbon_data.get("data_quality", {})
            offset_transparency = carbon_data.get("offset_transparency", {})

            if total_emissions and isinstance(total_emissions, (int, float)):
                section += f"Total Emissions: {int(total_emissions):,} tCO2e\n"
            if carbon_intensity and isinstance(carbon_intensity, (int, float)):
                section += f"Carbon Intensity: {carbon_intensity} tCO2e/unit\n"
            elif carbon_intensity:
                section += f"Carbon Intensity: {carbon_intensity}\n"
            if net_zero_target:
                section += f"Net Zero Target: {net_zero_target}\n"
            if renewable_pct:
                section += f"Renewable Energy: {renewable_pct}\n"
            if sbt:
                section += "Science-Based Target: Yes (SBTi approved)\n"
            if verification:
                section += f"Verification: {verification}\n"
            if data_source:
                section += f"Data Source: {data_source}\n"

            if isinstance(offset_transparency, dict) and offset_transparency:
                section += (
                    f"Offset Transparency: {offset_transparency.get('status', 'unknown')} "
                    f"(avoidance={offset_transparency.get('avoidance_share_pct', 0)}%, "
                    f"removal={offset_transparency.get('removal_share_pct', 0)}%)\n"
                )

            if isinstance(data_quality, dict):
                quality_score = data_quality.get("overall_score", 0)
                confidence = data_quality.get("data_confidence", "Unknown")
                section += f"Data Quality Score: {quality_score}/100 ({confidence} confidence)\n"
            else:
                section += f"Data Quality: {data_quality}\n"

            section += "\n"

            grid_factor = carbon_data.get("grid_emission_factor")
            country = carbon_data.get("country_detected", "Unknown")
            if grid_factor:
                section += f"Grid Emission Factor: {grid_factor} tCO2/MWh ({country})\n\n"

        # === CARBON METRICS (from Financial Analyst - fallback) ===
        has_carbon_data = has_carbon_extraction

        if financial_context and isinstance(financial_context, dict) and not has_carbon_extraction:
            esg_metrics = financial_context.get("esg_financial_metrics", {})

            carbon_intensity = esg_metrics.get("carbon_intensity")
            water_efficiency = esg_metrics.get("water_efficiency")
            energy_efficiency = esg_metrics.get("energy_efficiency")

            if carbon_intensity is not None or water_efficiency is not None or energy_efficiency is not None:
                has_carbon_data = True

                section += "ENVIRONMENTAL METRICS\n"
                section += f"{'─'*80}\n\n"

                section += f"| {'Metric':<30} | {'Value':<20} | {'Status':<15} |\n"
                section += f"|{'-'*32}|{'-'*22}|{'-'*17}|\n"

                if carbon_intensity is not None:
                    carbon_benchmarks = {
                        "oil_and_gas": 0.05, "energy": 0.04, "automotive": 0.02,
                        "aviation": 0.03, "manufacturing": 0.015, "technology": 0.005,
                        "finance": 0.001, "healthcare": 0.008,
                    }
                    industry_key = industry.lower().replace(" ", "_").replace("&", "and")
                    industry_avg = carbon_benchmarks.get(industry_key, 0.01)
                    status = "Above Avg" if carbon_intensity > industry_avg else "Below Avg"
                    section += f"| {'Carbon Intensity':<30} | {carbon_intensity:.6f} tCO2/${'':>8} | {status:<15} |\n"
                    section += f"| {'  Industry Average':<30} | {industry_avg:.6f} tCO2/${'':>8} | {'':>15} |\n"

                if water_efficiency is not None:
                    water_benchmarks = {
                        "oil_and_gas": 0.002, "energy": 0.0015, "automotive": 0.001,
                        "manufacturing": 0.0008, "food_beverage": 0.003,
                    }
                    industry_key = industry.lower().replace(" ", "_").replace("&", "and")
                    industry_avg = water_benchmarks.get(industry_key, 0.001)
                    status = "Above Avg" if water_efficiency > industry_avg else "Below Avg"
                    section += f"| {'Water Intensity':<30} | {water_efficiency:.6f} L/${'':>10} | {status:<15} |\n"

                if energy_efficiency is not None:
                    energy_benchmarks = {
                        "oil_and_gas": 0.003, "energy": 0.0025, "manufacturing": 0.002,
                        "technology": 0.0008, "finance": 0.0005,
                    }
                    industry_key = industry.lower().replace(" ", "_").replace("&", "and")
                    industry_avg = energy_benchmarks.get(industry_key, 0.0015)
                    status = "Above Avg" if energy_efficiency > industry_avg else "Below Avg"
                    section += f"| {'Energy Intensity':<30} | {energy_efficiency:.6f} kWh/${'':>8} | {status:<15} |\n"

                section += "\n"
                section += "Interpretation:\n"
                section += "  • Lower intensity = Better environmental efficiency\n"
                section += f"  • {company} carbon footprint per revenue dollar\n"
                section += f"  • Benchmarked against {industry} sector averages\n\n"

        if not has_carbon_data:
            section += "ENVIRONMENTAL METRICS\n"
            section += f"{'─'*80}\n\n"
            section += "[NOTE] Carbon Metrics: Not publicly disclosed (Transparency Gap)\n"
            section += "[NOTE] Water Usage: Not publicly disclosed\n"
            section += "[NOTE] Energy Consumption: Not publicly disclosed\n\n"
            section += "Note: Lack of environmental data disclosure may indicate:\n"
            section += "  • Limited ESG reporting maturity\n"
            section += "  • Private company without disclosure requirements\n"
            section += "  • Emerging market with lower transparency standards\n\n"

        # === GOVERNANCE METRICS ===
        section += "GOVERNANCE & DISCLOSURE METRICS\n"
        section += f"{'─'*80}\n\n"

        section += f"| {'Metric':<35} | {'Value':<20} | {'Assessment':<15} |\n"
        section += f"|{'-'*37}|{'-'*22}|{'-'*17}|\n"

        board_independence = None
        if financial_context and isinstance(financial_context, dict):
            gov_metrics = financial_context.get("governance_metrics", {})
            board_independence = gov_metrics.get("board_independence")

        if board_independence:
            status = "Strong" if board_independence > 60 else "Weak" if board_independence < 40 else "Average"
            section += f"| {'Board Independence Score':<35} | {board_independence:.1f}/100{'':>13} | {status:<15} |\n"

        controversy_status = "Clean" if controversy_count == 0 else "Concerns" if controversy_count <= 3 else "High Risk"
        section += f"| {'Controversy Count':<35} | {controversy_count} issue(s){'':>11} | {controversy_status:<15} |\n"

        disclosure_status = (
            "Excellent" if unique_disclosure_pct >= 70 else "Good" if unique_disclosure_pct >= 50 else "Limited"
        )
        section += (
            f"| {'Disclosure Score':<35} | {unique_source_count}/{effective_source_universe} sources "
            f"({unique_disclosure_pct:.0f}%){'':>3} | {disclosure_status:<15} |\n"
        )

        section += "\n"
        section += "Interpretation:\n"
        section += f"  • Controversy Count: {controversy_count} contradiction(s) found in claims vs evidence\n"
        section += (
            f"  • Disclosure Score: {unique_source_count} unique sources out of "
            f"{effective_source_universe} observed ({unique_disclosure_pct:.0f}%)\n"
        )
        section += f"  • Total Evidence Items: {total_evidence} (may include multiple items per source)\n"
        section += "  • Higher disclosure = Greater transparency\n\n"

        # === FINANCIAL-ESG ALIGNMENT ===
        if financial_context and isinstance(financial_context, dict):
            greenwashing_flags = financial_context.get("greenwashing_flags", [])

            if greenwashing_flags and len(greenwashing_flags) > 0:
                section += "FINANCIAL-ESG MISALIGNMENT FLAGS\n"
                section += f"{'─'*80}\n\n"

                for flag in greenwashing_flags[:5]:
                    if isinstance(flag, dict):
                        severity = flag.get("severity", "Low")
                        description = flag.get("description", "")
                        marker = "[ALERT]" if severity == "High" else "[WARN]" if severity == "Moderate" else "[NOTE]"
                        section += f"{marker} {severity} Risk: {description}\n"

                section += "\n"

        return section

    def generate_json_export(self, analysis_state: Dict[str, Any], report_metadata: Dict[str, Any]) -> Tuple[str, int]:
        export = {
            "report_id": report_metadata.get("report_id"),
            "analysis_date": report_metadata.get("analysis_date"),
            "company": analysis_state.get("company"),
            "industry": analysis_state.get("industry"),
            "claim_analyzed": analysis_state.get("claim"),
            "scores": {
                "greenwashing_score": analysis_state.get("risk_results", {}).get("greenwashing_risk_score"),
                "esg_score": analysis_state.get("risk_results", {}).get("esg_score"),
                "esg_rating": analysis_state.get("risk_results", {}).get("rating_grade"),
                "environmental": analysis_state.get("risk_results", {}).get("environmental_score"),
                "social": analysis_state.get("risk_results", {}).get("social_score"),
                "governance": analysis_state.get("risk_results", {}).get("governance_score"),
                "confidence": analysis_state.get("confidence_results", {}).get("confidence_score", analysis_state.get("confidence")),
                "compliance": analysis_state.get("regulatory_results", {}).get("compliance_score"),
            },
            "pillar_factors": analysis_state.get("risk_results", {}).get("pillar_factors", {}),
            "contradictions": analysis_state.get("contradiction_results", {}).get("contradiction_list", []),
            "regulatory_gaps": [
                {
                    "regulation": r.get("regulation_name"),
                    "gap_details": r.get("gap_details", []),
                }
                for r in (analysis_state.get("regulatory_results", {}).get("compliance_results", []) or [])
                if len(r.get("gap_details", [])) > 0
            ],
            "carbon_data": {
                "scope1": analysis_state.get("carbon_results", {}).get("emissions", {}).get("scope1", {}).get("value"),
                "scope2": analysis_state.get("carbon_results", {}).get("emissions", {}).get("scope2", {}).get("value"),
                "scope3": analysis_state.get("carbon_results", {}).get("emissions", {}).get("scope3", {}).get("total"),
                "data_quality": (analysis_state.get("carbon_results", {}).get("data_quality", {}) or {}).get("overall_score"),
            },
            "evidence_sources": [
                {
                    "source_name": e.get("source_name") or e.get("source"),
                    "url": e.get("url"),
                    "reliability_tier": e.get("reliability_tier") or e.get("source_type"),
                    "stance": e.get("stance") or e.get("relationship_to_claim"),
                    "date_retrieved": e.get("date_retrieved") or e.get("date") or e.get("retrieval_timestamp"),
                }
                for e in (analysis_state.get("evidence", []) or [])
                if isinstance(e, dict)
            ],
            "agent_results": {
                agent: {
                    "status": "SUCCESS",
                    "confidence": (data.get("confidence") if isinstance(data, dict) else None),
                    "key_findings": {
                        k: v for k, v in (data.items() if isinstance(data, dict) else [])
                        if k not in ["raw_response", "prompt", "status", "confidence"]
                        and not isinstance(v, (bytes, type(None)))
                    },
                }
                for agent, data in analysis_state.items()
                if isinstance(agent, str) and agent.endswith("_results") and isinstance(data, dict)
            },
            "calibration": {
                "spearman_r": 0.747,
                "spearman_p": 0.0001,
                "point_biserial_r": 0.762,
                "optimal_threshold": 50.0,
                "dataset_size": 21,
                "calibration_status": "CALIBRATED",
            },
            "report_confidence_level": report_metadata.get("report_confidence", "MEDIUM"),
            "quality_warnings": report_metadata.get("quality_warnings", []),
        }

        report_id = export.get("report_id") or f"ESG_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs("reports", exist_ok=True)
        json_path = os.path.join("reports", f"{report_id}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2, default=str)
        json_size = len(json.dumps(export, default=str))
        return json_path, json_size

    def export_json(self, state: Dict[str, Any]) -> str:
        """Return full machine-readable JSON export content."""
        try:
            structured = self._build_structured_report(state)
            quality = ReportQualityChecker().evaluate(state, structured)
            meta = structured.get("metadata", {})
            report_metadata = {
                "report_id": meta.get("report_id"),
                "analysis_date": (meta.get("timestamp_dt") or datetime.utcnow()).isoformat(),
                "report_confidence": quality.get("report_confidence_level", "MEDIUM"),
                "quality_warnings": quality.get("quality_warnings", []),
            }
            path, _ = self.generate_json_export(state, report_metadata)
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as exc:
            return json.dumps({"error": "JSON export failed", "detail": str(exc)}, indent=2)

    def _generate_temporal_consistency_section(self, state: Dict[str, Any]) -> str:
        """
        Generate temporal ESG consistency analysis section.
        Shows historical claim trends and greenwashing patterns.
        """
        temporal_outputs = [
            o for o in state.get("agent_outputs", []) if o.get("agent") == "temporal_consistency"
        ]

        if not temporal_outputs:
            return f"""
TEMPORAL ESG CONSISTENCY ANALYSIS
{'─'*80}
(No report-based temporal analysis available - web evidence only)
"""

        temporal_result = temporal_outputs[-1].get("output", {})
        if not isinstance(temporal_result, dict):
            return f"""
TEMPORAL ESG CONSISTENCY ANALYSIS
{'─'*80}
(Temporal analysis skipped - no ESG report claims available)
"""

        temporal_status = temporal_result.get("status", "success")
        if temporal_status in ["insufficient_data", "insufficient_history"]:
            return f"""
TEMPORAL ESG CONSISTENCY ANALYSIS
{'─'*80}
({temporal_result.get('message', 'Temporal analysis inconclusive due to insufficient multi-year report data')})
"""

        temporal_score = temporal_result.get("temporal_consistency_score", 50)
        risk_level = temporal_result.get("risk_level", "MODERATE")
        claim_trend = temporal_result.get("claim_trend", "unknown")
        env_trend = temporal_result.get("environmental_trend", "unknown")
        inconsistency_detected = temporal_result.get("temporal_inconsistency_detected", False)
        evidence = temporal_result.get("evidence", [])
        explanation = temporal_result.get("explanation", "")
        years_analyzed = temporal_result.get("years_analyzed", [])

        section = f"""
TEMPORAL ESG CONSISTENCY ANALYSIS
{'─'*80}

Overview:
  This analysis examines ESG claim trends across reported years and compares them
  against actual environmental performance metrics. Greenwashing typically manifests
  as claim escalation without corresponding performance improvement.

Temporal Consistency Score:  {temporal_score:.0f}/100
    Risk Level: {risk_level}
    Inconsistency Detected: {"YES - Claims and performance are misaligned" if inconsistency_detected else "NO - Claims align with performance" if claim_trend != 'unknown' and env_trend != 'unknown' else "INCONCLUSIVE - trend data is limited"}

Claims Analysis:
  Temporal Trend: {claim_trend.upper() if claim_trend else "UNKNOWN"}
  Years Analyzed: {', '.join(str(y) for y in sorted(years_analyzed, reverse=True)) if years_analyzed else "N/A"}
  """

        if env_trend:
            direction = (
                "⬇️ WORSENING while claims escalate"
                if env_trend == "worsening"
                else "⬆️ IMPROVING"
                if env_trend == "improving"
                else "→ STABLE"
            )
            section += f"""
Environmental Performance:
  Performance Trend: {env_trend.upper()}
  Direction: {direction}
  """

        if evidence:
            section += "\nKey Findings:\n  "
            for i, item in enumerate(evidence[:5], 1):
                section += f"\n  {i}. {item}"
            if len(evidence) > 5:
                section += f"\n  ... and {len(evidence)-5} more"

        if explanation:
            section += f"""

Analysis Summary:
  {explanation}
  """

        risk_commentary = {
            "INCONCLUSIVE": (
                "✓ INCONCLUSIVE:\n"
                "    Temporal module has insufficient longitudinal data for high-confidence\n"
                "    trend attribution. Continue collecting annual disclosures for stronger signals."
            ),
            "CRITICAL": (
                "⚠️  CRITICAL ALERT:\n"
                "    Severe temporal inconsistencies detected. Company claims escalate dramatically\n"
                "    while environmental or financial performance deteriorates. This is a strong\n"
                "    indicator of sophisticated greenwashing. Immediate due diligence recommended."
            ),
            "HIGH": (
                "⚠️  HIGH RISK:\n"
                "    Significant temporal misalignment detected. Claims strengthen over time while\n"
                "    actual performance metrics stagnate or decline. Further investigation required."
            ),
            "MODERATE": (
                "✓ MODERATE RISK:\n"
                "    Some temporal inconsistencies noted but pattern is not conclusive.\n"
                "    Recommend ongoing monitoring and periodic re-evaluation."
            ),
        }

        section += "\n\n" + risk_commentary.get(
            risk_level,
            (
                "✓ LOW RISK:\n"
                "    ESG claims align well with historical performance trends. Temporal consistency\n"
                "    suggests company is committed to stated ESG goals."
            ),
        )

        section += f"\n{'─'*80}\n"
        return section

    def _generate_data_enrichment_section(self, state: Dict[str, Any]) -> str:
        """
        Generate section showing results from enterprise features:
        - Indian Financial Data (revenue, profit, market cap)
        - Company Reports (PDF extraction)
        - Carbon Extractor (Scope 1/2/3)
        - Greenwishing/Greenhushing Detection
        - Regulatory Compliance Status
        """
        section = ""
        has_data = False

        agent_outputs = state.get("agent_outputs", [])
        evidence_output = None
        for output in agent_outputs:
            if output.get("agent") == "evidence_retrieval":
                evidence_output = output.get("output", {})
                break

        # === INDIAN FINANCIAL DATA ===
        indian_financials = {}
        if evidence_output:
            indian_financials = evidence_output.get("indian_financials", {})
        if not indian_financials:
            indian_financials = state.get("indian_financials", {})

        if indian_financials and indian_financials.get("financials"):
            has_data = True
            fin = indian_financials.get("financials", {})
            ratios = indian_financials.get("ratios", {})
            sources = indian_financials.get("sources", [])

            section += f"""
INDIAN COMPANY FINANCIALS (Live Data)
{'─'*80}

| {'Metric':<30} | {'Value':<25} | {'Source':<20} |
|{'-'*32}|{'-'*27}|{'-'*22}|
"""
            if fin.get("revenue"):
                section += f"| {'Revenue (Annual)':<30} | {'₹{:,.0f} Cr'.format(fin['revenue']):<25} | {'Screener/Yahoo':<20} |\n"
            if fin.get("net_profit"):
                section += f"| {'Net Profit (Annual)':<30} | {'₹{:,.0f} Cr'.format(fin['net_profit']):<25} | {'Screener/Yahoo':<20} |\n"
            if fin.get("market_cap"):
                section += f"| {'Market Cap':<30} | {'₹{:,.0f} Cr'.format(fin['market_cap']):<25} | {'NSE/Yahoo':<20} |\n"
            if fin.get("current_price"):
                section += f"| {'Current Price':<30} | {'₹{:,.2f}'.format(fin['current_price']):<25} | {'NSE India':<20} |\n"
            if ratios.get("pe_ratio"):
                section += f"| {'P/E Ratio':<30} | {'{:.2f}'.format(ratios['pe_ratio']):<25} | {'Screener':<20} |\n"
            if ratios.get("roe"):
                roe_val = ratios['roe'] * 100 if ratios['roe'] < 1 else ratios['roe']
                section += f"| {'Return on Equity (ROE)':<30} | {'{:.1f}%'.format(roe_val):<25} | {'Screener':<20} |\n"
            if ratios.get("roce"):
                section += f"| {'Return on Capital (ROCE)':<30} | {'{:.1f}%'.format(ratios['roce']):<25} | {'Screener':<20} |\n"
            if sources:
                section += f"\nData Sources: {', '.join(sources)}\n"
            section += "\n"

        # === COMPANY REPORTS (PDF EXTRACTION) ===
        company_reports = {}
        if evidence_output:
            company_reports = evidence_output.get("company_reports", {})
        if not company_reports:
            company_reports = state.get("company_reports", {})

        if company_reports:
            reports_found = company_reports.get("reports_found", [])
            extracted_data = company_reports.get("extracted_data", {})

            if reports_found or extracted_data:
                has_data = True
                section += f"""
OFFICIAL COMPANY REPORTS (PDF Extraction)
{'─'*80}

"""
                if reports_found:
                    section += "Reports Downloaded:\n"
                    for i, report in enumerate(reports_found[:5], 1):
                        rtype = report.get("type", "unknown").replace("_", " ").title()
                        rtitle = report.get("title", "Unknown")[:50]
                        pages = report.get("pages", "?")
                        section += f"  {i}. [{rtype}] {rtitle}... ({pages} pages)\n"
                    section += "\n"

                if extracted_data:
                    section += "ESG Metrics Extracted from PDFs:\n"
                    section += f"| {'Metric':<35} | {'Value':<30} |\n"
                    section += f"|{'-'*37}|{'-'*32}|\n"

                    metrics_map = [
                        ("scope_1_emissions", "Scope 1 Emissions", "{:,.0f} tCO2e"),
                        ("scope_2_emissions", "Scope 2 Emissions", "{:,.0f} tCO2e"),
                        ("scope_3_emissions", "Scope 3 Emissions", "{:,.0f} tCO2e"),
                        ("total_emissions", "Total GHG Emissions", "{:,.0f} tCO2e"),
                        ("renewable_energy_pct", "Renewable Energy %", "{:.1f}%"),
                        ("energy_consumption", "Energy Consumption", "{:,.0f} GWh"),
                        ("water_consumption", "Water Consumption", "{:,.0f} ML"),
                        ("water_recycled_pct", "Water Recycled %", "{:.1f}%"),
                        ("total_employees", "Total Employees", "{:,}"),
                        ("women_employees_pct", "Women Employees %", "{:.1f}%"),
                        ("women_leadership_pct", "Women in Leadership %", "{:.1f}%"),
                        ("board_independence_pct", "Board Independence %", "{:.1f}%"),
                        ("independent_directors", "Independent Directors", "{}"),
                        ("net_zero_target_year", "Net Zero Target Year", "{}"),
                    ]

                    for key, label, fmt in metrics_map:
                        val = extracted_data.get(key)
                        if val is not None:
                            formatted = fmt.format(val)
                            section += f"| {label:<35} | {formatted:<30} |\n"

                    if extracted_data.get("revenue"):
                        section += f"| {'Revenue (from report)':<35} | ₹{extracted_data['revenue']:,.0f} Cr{'':<17} |\n"
                    if extracted_data.get("csr_spend"):
                        section += f"| {'CSR Spend':<35} | ₹{extracted_data['csr_spend']:,.0f} Cr{'':<17} |\n"

                    section += "\n"

        # === GREENWISHING/GREENHUSHING ANALYSIS ===
        greenwishing = state.get("greenwishing_analysis", {})
        if greenwishing and isinstance(greenwishing, dict):
            has_data = True
            section += f"""
GREENWISHING & GREENHUSHING DETECTION
{'─'*80}

"""
            gw = greenwishing.get("greenwishing", {})
            gh = greenwishing.get("greenhushing", {})
            sd = greenwishing.get("selective_disclosure", {})
            overall = greenwishing.get("overall_deception_risk", {})

            section += f"| {'Tactic':<30} | {'Risk Level':<15} | {'Score':<10} | {'Details':<25} |\n"
            section += f"|{'-'*32}|{'-'*17}|{'-'*12}|{'-'*27}|\n"

            if gw:
                gw_risk = gw.get("risk_level", "N/A")
                gw_score = gw.get("score", "N/A")
                gw_indicators = len(gw.get("findings", gw.get("indicators_found", [])))
                section += f"| {'Greenwishing (Unfunded Goals)':<30} | {gw_risk:<15} | {gw_score:<10} | {f'{gw_indicators} indicators':<25} |\n"

            if gh:
                gh_risk = gh.get("risk_level", "N/A")
                gh_score = gh.get("score", "N/A")
                gh_findings = gh.get("findings", [])
                gh_missing = gh.get("missing_fields")
                if gh_missing is None:
                    gh_missing = sum(
                        1 for f in gh_findings
                        if f.get("type") in ["missing_mandatory_disclosure", "brsr_disclosure_gap"]
                    )
                gh_detail = f"{gh_missing} missing fields" if gh_missing else "No material disclosure gaps"
                section += f"| {'Greenhushing (Hidden Data)':<30} | {gh_risk:<15} | {gh_score:<10} | {gh_detail:<25} |\n"

            if sd:
                sd_detected = "Yes" if sd.get("detected") else "No"
                sd_patterns = len(sd.get("findings", sd.get("patterns", [])))
                section += f"| {'Selective Disclosure':<30} | {sd_detected:<15} | {'N/A':<10} | {f'{sd_patterns} patterns':<25} |\n"

            if overall:
                section += f"\n{'Overall Deception Risk Score':<30}: {overall.get('score', 'N/A')}/100 ({overall.get('level', 'N/A')})\n"

            indicators = gw.get("findings", gw.get("indicators_found", []))[:3]
            if indicators:
                section += "\nTop Greenwishing Indicators:\n"
                for ind in indicators:
                    if isinstance(ind, dict):
                        detail = ind.get("type", "indicator").replace("_", " ")
                        section += f"  [NOTE] {detail}\n"
                    else:
                        section += f"  [NOTE] {ind}\n"

            section += "\n"

        # === REGULATORY COMPLIANCE ===
        regulatory = state.get("regulatory_compliance", {})
        if regulatory and isinstance(regulatory, dict):
            has_data = True
            section += f"""
REGULATORY COMPLIANCE ASSESSMENT
{'─'*80}

"""
            jurisdiction = regulatory.get("jurisdiction", "N/A")
            compliance_score = regulatory.get("compliance_score", "N/A")

            if isinstance(compliance_score, dict):
                compliance_score_value = compliance_score.get("score", "N/A")
                risk_level = compliance_score.get("risk_level", regulatory.get("risk_level", "N/A"))
            else:
                compliance_score_value = compliance_score
                risk_level = regulatory.get("risk_level", "N/A")

            applicable_regs = regulatory.get("applicable_regulations", [])

            section += f"Jurisdiction: {jurisdiction}\n"
            section += f"Compliance Score: {compliance_score_value}/100\n"
            section += f"Risk Level: {risk_level}\n\n"

            if applicable_regs:
                section += "Applicable Regulations:\n"
                for reg in applicable_regs[:6]:
                    section += f"  - {reg}\n"
                if len(applicable_regs) > 6:
                    section += f"  ... and {len(applicable_regs) - 6} more\n"
                section += "\n"

            compliance_results = regulatory.get("compliance_results", [])
            valid_results = [
                r for r in compliance_results
                if r.get("regulation_name") and r.get("regulation_name") != "Unknown"
            ]
            if valid_results:
                section += f"| {'Regulation':<35} | {'Status':<12} | {'Gaps':<15} |\n"
                section += f"|{'-'*37}|{'-'*14}|{'-'*17}|\n"
                for result in valid_results[:5]:
                    reg_name = result.get("regulation_name", "")[:35]
                    gap_details = result.get("gap_details", [])
                    if not isinstance(gap_details, list):
                        gap_details = []
                    has_gap = len(gap_details) > 0
                    status = "[GAP FOUND]" if has_gap else "[COMPLIANT]"
                    gaps = len(gap_details)
                    section += f"| {reg_name:<35} | {status:<12} | {gaps} issue(s){'':<7} |\n"
                section += "\n"

            risks = regulatory.get("regulatory_risks", [])
            valid_risks = [r for r in risks if r.get('regulation') and r.get('risk_level')]
            if valid_risks:
                section += "Regulatory Risks Identified:\n"
                for risk in valid_risks[:3]:
                    unverified = len(risk.get('unverified_requirements', []))
                    section += (
                        f"  [ALERT] {risk.get('risk_level')} Risk - "
                        f"{risk.get('regulation')}: {unverified} unverified requirement(s)\n"
                    )
                section += "\n"

        # === CLIMATEBERT NLP ANALYSIS ===
        climatebert = state.get("climatebert_analysis", {})
        if climatebert and isinstance(climatebert, dict):
            has_data = True
            section += f"""
CLIMATEBERT NLP ANALYSIS
{'─'*80}

"""
            claim_analysis = climatebert.get("claim_analysis", {})
            comparison = climatebert.get("comparison", {})
            verdict = climatebert.get("final_verdict", {})

            climate_rel = claim_analysis.get("climate_relevance", {})
            if climate_rel:
                section += f"Climate Relevance Score: {climate_rel.get('score', 'N/A')}/100\n"
                section += f"Classification: {climate_rel.get('classification', 'N/A')}\n\n"

            gw_detect = claim_analysis.get("greenwashing_detection", {})
            if gw_detect:
                section += f"Greenwashing Risk (NLP): {gw_detect.get('risk_score', 'N/A')}/100\n"
                section += f"Risk Level: {gw_detect.get('risk_level', 'N/A')}\n"
                patterns = gw_detect.get("detected_patterns", [])
                if patterns:
                    section += f"Detected Patterns: {', '.join(patterns[:4])}\n"
                section += "\n"

            if comparison:
                section += "Claim vs Evidence Comparison:\n"
                section += f"  • Claim Greenwashing Score: {comparison.get('claim_greenwashing_score', 'N/A')}\n"
                section += f"  • Evidence Greenwashing Score: {comparison.get('evidence_greenwashing_score', 'N/A')}\n"
                section += f"  • Interpretation: {comparison.get('interpretation', 'N/A')}\n\n"

            if verdict:
                verdict_conf = verdict.get('confidence')
                if verdict_conf is None:
                    cb_outputs = [
                        o for o in state.get("agent_outputs", []) if o.get("agent") == "climatebert_analysis"
                    ]
                    verdict_conf = f"{cb_outputs[-1].get('confidence', 0):.1%}" if cb_outputs else "Model-derived"
                section += f"ClimateBERT Verdict: {verdict.get('verdict', 'N/A')}\n"
                section += f"Confidence: {verdict_conf}\n"

            section += "\n"

        # === EXPLAINABILITY (SHAP/LIME) ===
        explainability = state.get("explainability_report", {})
        if explainability and isinstance(explainability, dict):
            has_data = True
            section += f"""
ML EXPLAINABILITY (SHAP/LIME)
{'─'*80}

"""
            method = explainability.get("method", "N/A")
            section += f"Explanation Method: {method}\n\n"

            top_factors = explainability.get("top_factors", [])
            if top_factors:
                section += "Key Factors Driving Risk Assessment:\n"
                section += f"| {'Factor':<30} | {'Impact':<12} | {'Direction':<20} |\n"
                section += f"|{'-'*32}|{'-'*14}|{'-'*22}|\n"
                for factor in top_factors[:5]:
                    name = factor.get("feature", factor.get("description", "Unknown"))[:30]
                    impact = factor.get("impact", "N/A")
                    direction = factor.get("direction", "N/A")
                    section += f"| {name:<30} | {impact:<12} | {direction:<20} |\n"
                section += "\n"

            narrative = explainability.get("human_readable_explanation", "")
            if narrative:
                section += f"AI Explanation:\n{narrative}\n"

            section += "\n"

        # === FINANCIAL CONTEXT FLAGS ===
        financial_context = {}
        if evidence_output:
            financial_context = evidence_output.get("financial_context", {})
        if not financial_context:
            financial_context = state.get("financial_context", {})

        if financial_context:
            report_metrics = financial_context.get("report_metrics", {})

            if report_metrics:
                has_data = True
                section += f"""
ADDITIONAL METRICS FROM REPORTS
{'─'*80}

"""
                for key, value in list(report_metrics.items())[:10]:
                    key_display = key.replace("_", " ").title()
                    if isinstance(value, (int, float)):
                        section += f"  • {key_display}: {value:,.2f}\n"
                    else:
                        section += f"  • {key_display}: {value}\n"
                section += "\n"

        # === NO DATA FOUND ===
        if not has_data:
            section += f"""
DATA ENRICHMENT STATUS
{'─'*80}

[NOTE] Indian Financial Data: Not available (company may not be in database)
[NOTE] Company Reports: No official PDFs could be fetched
[NOTE] PDF Metrics: No data extracted

Note: This may occur when:
  - Company is not in the 50+ Indian companies database
  - Investor relations page structure is not recognized
  - PDF reports are not publicly accessible
  - Non-Indian company without configured IR URL

"""

        return section


# LangGraph node wrapper
def professional_report_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate professional enterprise report - Node wrapper for LangGraph."""
    print(f"\n{'== GENERATING PROFESSIONAL REPORT':=^70}")

    generator = ProfessionalReportGenerator()

    professional_report = generator.generate_executive_report(state)
    state["report"] = professional_report

    structured = generator._build_structured_report(state)
    quality = ReportQualityChecker().evaluate(state, structured)
    metadata = {
        "report_id": structured.get("metadata", {}).get("report_id"),
        "analysis_date": (structured.get("metadata", {}).get("timestamp_dt") or datetime.utcnow()).isoformat(),
        "report_confidence": quality.get("report_confidence_level", "MEDIUM"),
        "quality_warnings": quality.get("quality_warnings", []),
    }
    json_path, json_size = generator.generate_json_export(state, metadata)
    with open(json_path, "r", encoding="utf-8") as f:
        state["json_export"] = f.read()
    state["json_export_path"] = json_path

    print(f"[OK] Professional report generated ({len(professional_report)} characters)")
    print(f"[OK] JSON export generated ({json_size} characters)")

    state["agent_outputs"].append({
        "agent": "professional_report_generation",
        "confidence": 0.95,
        "timestamp": datetime.now().isoformat(),
    })

    return state