import os
import json
import re
import html
import time
import textwrap
import traceback as _tb
import asyncio
import logging
from urllib.parse import urlparse
from datetime import datetime, timezone
from core.carbon_validator import CarbonDataValidator
from typing import Dict, Any, List, Tuple, Set, Optional
from core.safe_utils import safe_get, safe_number, parse_source_name, normalize_industry_label, normalize_industry_key, get_reliability_tier
from core.report_schema import ReportPayload, EvidenceItem, EvidenceRoleCount, PeerEntry, CredibilityTierCount, FactGraphSummary, NewsItem
from pydantic import ValidationError

logger = logging.getLogger(__name__)

TICKER_SYMBOL_MAP = {
    "Tesla": "TSLA",
    "Microsoft": "MSFT",
    "ExxonMobil": "XOM",
    "JPMorgan": "JPM",
    "JPMorgan Chase": "JPM",
    "JPMC": "JPM",
    "Shell": "SHEL",
    "BP": "BP",
    "Unilever": "UL",
    "TotalEnergies": "TTE",
    "Nestle": "NESN",
}

AGENT_DISPLAY_NAMES = {
    "professional_report_generation": "report_generation",
    "greenwishing_detection": "greenwishing_detection",
}

# NOTE: Heavy ML/agent modules are intentionally NOT imported at module level here.
# They were previously triggering 80+ second re-initialization on every node call.
# If needed, import them lazily inside the specific functions that use them.


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
        ignored_agents = {
            "confidence_scoring",
            "professional_report_generation",
            "supervisor",
            "assess_complexity",
            "confidence_monitor",
        }

        scores = structured.get("scores", {}) or {}
        raw_scores = scores.get("raw", {}) if isinstance(scores.get("raw"), dict) else {}
        if not raw_scores:
            quality_warnings.append(
                "Risk scoring output missing; headline scores may reflect defaults rather than computed results."
            )

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
            if not isinstance(pillar_data, dict):
                quality_warnings.append(
                    f"{pillar_key}-pillar payload was null or malformed; using fallback defaults for this dimension."
                )
                continue
            score = pillar_data.get("score")
            factors = [f for f in (pillar_data.get("factors") or []) if isinstance(f, dict)]
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
            if name in ignored_agents:
                continue
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

        # Surface specific high-impact agent failures so consumers know which
        # dimensions of the analysis are degraded. Generic "FAILED" counts are
        # easy to skim past; named failures are actionable.
        critical_named = {
            "industry_comparator": "peer benchmarking",
            "peer_comparison": "peer benchmarking",
            "carbon_extraction": "scope-1/2/3 extraction",
            "carbon_pathway_analysis": "carbon pathway alignment",
            "regulatory_scanning": "regulatory framework scan",
            "contradiction_analysis": "contradiction detection",
            "risk_scoring": "headline risk score",
            "temporal_consistency": "temporal claim-vs-performance comparison",
            "company_knowledge_graph": "company knowledge graph context",
        }
        for agent_name, dim in critical_named.items():
            if agent_status.get(agent_name) == "FAILED":
                quality_warnings.append(
                    f"Critical agent '{agent_name}' FAILED — {dim} dimension is missing from the integrated score."
                )
        # Also warn when ANY non-critical agent failed, in aggregate.
        non_critical_failed = [n for n in failed_agents if n not in critical_named]
        if non_critical_failed:
            quality_warnings.append(
                f"{len(non_critical_failed)} non-critical agent(s) failed: {', '.join(sorted(non_critical_failed)[:5])}."
            )

        # Calibration sample size — n<10 means score is statistical guesswork
        # for this sector/claim-type cell. Surface it so the headline isn't
        # over-trusted. Read from `structured.calibration` (populated by
        # _build_structured_report → _compute_calibration_live), with state
        # as a fallback.
        cal = (structured.get("calibration") if isinstance(structured, dict) else None) or state.get("calibration") or {}
        if isinstance(cal, dict):
            n = cal.get("dataset_size") or cal.get("subset_n") or cal.get("n")
            if isinstance(n, (int, float)):
                if n < 10:
                    quality_warnings.append(
                        f"Calibration sample is very small (n={int(n)}); score is PROVISIONAL and should not anchor investment-grade decisions."
                    )
                elif n < 30:
                    quality_warnings.append(
                        f"Calibration sample is limited (n={int(n)}); score thresholds remain provisional for this sector/claim-type cell."
                    )

        # Carbon-scope completeness for net-zero / decarbonisation claims —
        # missing Scope 2 (or Scope 3 for financials) means the claim cannot
        # be quantitatively verified.
        carbon = state.get("carbon") or state.get("carbon_results") or {}
        emissions = carbon.get("emissions") if isinstance(carbon, dict) else {}
        if isinstance(emissions, dict):
            for scope_key, scope_label in [("scope1", "Scope 1"), ("scope2", "Scope 2"), ("scope3", "Scope 3")]:
                sd = emissions.get(scope_key)
                if isinstance(sd, dict):
                    val = sd.get("value") or sd.get("total")
                    if val in (None, "", 0, "N/A", "NOT DISCLOSED"):
                        quality_warnings.append(
                            f"{scope_label} emissions not disclosed; net-zero / decarbonisation claims cannot be quantitatively verified for this scope."
                        )

        # External benchmark status mismatch — "used_in_scoring=True" with 0
        # indicators is a contradictory signal. We deliberately do NOT treat
        # `enabled=True` alone as a problem (the layer is permitted to be on
        # standby); the warning only fires when the layer claims to have
        # influenced scoring without supplying any indicators.
        ext = state.get("external_esg_data") or state.get("external_benchmarks") or {}
        if isinstance(ext, dict):
            wba_count = ext.get("wba_indicator_count") or 0
            if ext.get("used_in_scoring") and (not wba_count or wba_count == 0):
                quality_warnings.append(
                    "External benchmark layer marked 'used_in_scoring' but 0 indicators returned; benchmark status is decorative, not load-bearing."
                )

        if not raw_scores:
            confidence_level = "LOW"
        elif failure_count == 0 and verified_count >= 10 and real_peer_count >= 2:
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

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime:
        """Safely coerce value to datetime.

        In the subprocess execution path (frontend → API → Python), the
        structured dict can be rebuilt from state that has already been
        serialised/deserialised (e.g. via JSON), so `timestamp_dt` may
        arrive as an ISO-8601 string instead of a datetime object.
        Calling .strftime() on a string raises AttributeError — this
        helper prevents that crash.
        """
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                # Handle both aware (Z / +00:00) and naive ISO strings
                cleaned = value.replace("Z", "+00:00")
                return datetime.fromisoformat(cleaned)
            except (ValueError, AttributeError):
                pass
        return datetime.utcnow()

    @staticmethod
    def _major_divider() -> str:
        return "=" * 80

    @staticmethod
    def _minor_divider() -> str:
        return "─" * 80

    @staticmethod
    def _wrap_paragraph(text: str, width: int = 80, indent: str = "") -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        return textwrap.fill(cleaned, width=width, subsequent_indent=indent) if cleaned else ""

    @staticmethod
    def _plain_textify(text: str) -> str:
        """Convert markdown-like artifacts to clean plain text for .txt output."""
        if not text:
            return ""
        lines = []
        for raw in str(text).splitlines():
            line = raw.replace("**", "")
            if line.lstrip().startswith("#"):
                line = line.lstrip("# ")
            if re.fullmatch(r"\s*\|?[-: ]+\|[-|: ]*\s*", line):
                continue
            if "|" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if parts:
                    line = "  ".join(parts)
            lines.append(line)
        return "\n".join(lines).strip()

    def generate_executive_report(self, state: Dict[str, Any]) -> str:
        """Generate a research-grade, publication-ready executive report.

        Reads the multi-agent analysis state, builds a structured internal
        representation, runs quality checks, then renders a human-readable
        report with explicit sections, citations, and score derivations.

        Wrapped in structured error handling so crashes never surface raw
        tracebacks to end users.
        """
        _start_time = time.time()
        stages_completed = []
        stages_failed = []
        warnings = []
        generation_status = "success"

        # ── GLOBAL STATE SANITIZER ───────────────────────────────────────────────
        # The subprocess execution path (frontend → API → Python) can deliver state
        # where keys exist but values are None, wrong-typed strings, or bare ints.
        # state.get("key", []) returns None when the key is present with value None
        # — so we normalise once here before any code touches state.
        _state_list_fields = [
            "agent_outputs", "evidence", "extracted_claims", "claims",
        ]
        for _slf in _state_list_fields:
            if not isinstance(state.get(_slf), list):
                state[_slf] = []
        _state_dict_fields = [
            "final_verdict", "carbon_extraction", "regulatory_compliance",
            "greenwishing_analysis", "climatebert_analysis", "claim_decomposition",
            "adversarial_triangulation", "carbon_pathway_analysis",
            "commitment_ledger", "social_analysis", "governance_analysis",
            "explainability_report", "esg_mismatch_analysis",
        ]
        for _sdf in _state_dict_fields:
            if not isinstance(state.get(_sdf), dict):
                state[_sdf] = {}
        # ── END GLOBAL STATE SANITIZER ───────────────────────────────────────────


        # Safety: define company/industry/ticker at method scope so sub-methods
        # that inadvertently reference them as free variables won't crash.
        company = str(state.get("company") or "Unknown").strip() or "Unknown"
        industry = str(state.get("industry") or "Unknown").strip() or "Unknown"
        ticker = str(state.get("ticker") or state.get("symbol") or "N/A").strip() or "N/A"
        if ticker == "N/A":
            company_l = company.lower()
            ticker_map = {
                "tesla": "TSLA",
                "shell": "SHEL",
                "microsoft": "MSFT",
                "bp": "BP",
                "totalenergies": "TTE",
                "exxonmobil": "XOM",
            }
            for key, value in ticker_map.items():
                if key in company_l.replace(" ", ""):
                    ticker = value
                    state["ticker"] = value
                    break

        try:
            stages_completed.append("structured_build")
            structured = self._build_structured_report(state)
            _scores = structured.get("scores", {}) if isinstance(structured, dict) else {}
            _company_block = structured.get("company", {}) if isinstance(structured, dict) else {}
            calibration = self._extract_calibration_info(
                _scores,
                company_industry=_company_block.get("industry", state.get("industry", "Unknown")),
                claim_text=_company_block.get("claim", state.get("claim", "")),
            )
            if isinstance(structured, dict):
                structured["calibration"] = calibration
            quality = ReportQualityChecker().evaluate(state, structured)
            structured.setdefault("metadata", {})["quality_warnings"] = quality.get("quality_warnings", [])
            structured["metadata"]["report_confidence_level"] = quality.get("report_confidence_level", "MEDIUM")

            stages_completed.append("report_assembly")
            payload = ReportPayload()
            payload.unified_evidence = self._parse_unified_evidence(state)
            payload.evidence_roles = self._count_evidence_roles(payload.unified_evidence)
            payload.esg_lineage = state.get("esg_score_lineage", {})
            
            report = self._render_v4_report(state, structured, quality, payload=payload)

        except Exception as exc:
            generation_status = "partial"
            stages_failed.append("report_assembly")
            warnings.append(str(exc))
            # Log structured error for debugging (not surfaced to end user)
            _err_log = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "report_id": safe_get(state, "report_id", default="unknown"),
                "stage": "generate_executive_report",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": _tb.format_exc(),
            }
            with open("reports/crash_traceback.log", "w", encoding="utf-8") as f:
                f.write(_tb.format_exc())
            print(f"[ERROR] Report generation failed. Full traceback written to reports/crash_traceback.log")
            report = (
                f"{'=' * 80}\n"
                f"ESG GREENWASHING RISK ASSESSMENT REPORT (PARTIAL)\n"
                f"{'=' * 80}\n\n"
                f"Report generation encountered an error.\n"
                f"Stages completed: {', '.join(stages_completed)}\n"
                f"Error: {type(exc).__name__}\n\n"
                f"Available data has been preserved in the JSON export.\n"
                f"{'=' * 80}\n"
            )

        # Store generation log on state for downstream consumers
        duration = round(time.time() - _start_time, 2)
        state["report_generation_log"] = {
            "status": generation_status,
            "stages_completed": stages_completed,
            "stages_failed": stages_failed,
            "warnings": warnings,
            "duration_seconds": duration,
        }

        if not isinstance(report, str) or not report.strip():
            return "[ERROR] Report generation failed: No content generated."

        # Safety cap — report should never exceed ~500KB
        MAX_REPORT_BYTES = 500_000
        encoded = report.encode("utf-8")
        if len(encoded) > MAX_REPORT_BYTES:
            report = encoded[:490_000].decode("utf-8", errors="ignore")
            report += "\n\n[TRUNCATED AT 500KB]"

        return report

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        return float(value) if isinstance(value, (int, float)) else default

    def _fmt_pct(self, value: Any) -> str:
        if isinstance(value, (int, float)):
            if value <= 1:
                value = value * 100
            return f"{int(round(value))}%"
        return "N/A"

    def _fmt_score1(self, value: Any, suffix: str = "") -> str:
        if isinstance(value, (int, float)):
            return f"{float(value):.1f}{suffix}"
        return f"N/A{suffix}" if suffix else "N/A"

    def _resolve_floor_label(self, carbon_validation: Any, industry_label: str) -> str:
        """Resolve a printable industry label for fallback carbon estimates."""
        floor_used = carbon_validation.get("floor_used") if isinstance(carbon_validation, dict) else None
        if floor_used is None:
            return str(industry_label or "Unknown").strip() or "Unknown"
        floor_label = str(floor_used).strip()
        return floor_label or (str(industry_label or "Unknown").strip() or "Unknown")

    def _build_kg_history_section(self, state: Dict[str, Any], major: str) -> List[str]:
        """Render Section 11C — Knowledge Graph History.

        Surfaces what the persistent KG knows about this company from prior
        runs: KPI history depth, year-over-year drift signals, and Fact
        Graph motif diagnostics. Empty (returns []) when nothing useful
        accumulated yet (e.g. first-ever run for a company)."""
        company = str(state.get("company") or "").strip()
        if not company:
            return []

        # Pull drift signals from the risk_scoring agent output (where we
        # populated `kg_drift` during this run).
        drift_signals: List[Dict[str, Any]] = []
        for ao in (state.get("agent_outputs") or []):
            if isinstance(ao, dict) and ao.get("agent") == "risk_scoring":
                out = ao.get("output") or {}
                if isinstance(out, dict):
                    kg = out.get("kg_drift") or {}
                    if isinstance(kg, dict):
                        drift_signals = kg.get("signals") or []
                break

        # Direct query of KPI history file for raw history depth.
        history_runs = 0
        history_metrics: List[str] = []
        try:
            from core.company_knowledge_graph import get_kpi_history
            history = get_kpi_history(company)
            history_runs = len({row.get("run_ts") for row in history if row.get("run_ts")})
            history_metrics = sorted({row.get("metric_name") for row in history if row.get("metric_name")})
        except Exception:
            history_runs = 0

        # Fact Graph motifs from the risk_scoring agent output.
        fg_motifs: Dict[str, Any] = {}
        for ao in (state.get("agent_outputs") or []):
            if isinstance(ao, dict) and ao.get("agent") == "risk_scoring":
                out = ao.get("output") or {}
                if isinstance(out, dict):
                    fg = out.get("fact_graph") or {}
                    if isinstance(fg, dict):
                        fg_motifs = fg.get("motifs") or {}
                break

        # If neither drift nor history nor motifs exist, skip the section.
        if not drift_signals and history_runs == 0 and not fg_motifs:
            return []

        section: List[str] = [major, "SECTION 11C: KNOWLEDGE GRAPH HISTORY", major]
        section.append(
            "This section surfaces what the persistent Company KG and Fact Graph"
        )
        section.append(
            "know about this company across all prior analyses — year-over-year"
        )
        section.append(
            "drift signals and graph-shape diagnostics that one-shot scores miss."
        )
        section.append("")

        section.append(f"KPI history depth (this company): {history_runs} prior run(s) recorded")
        if history_metrics:
            section.append(f"Tracked metrics in KG: {', '.join(history_metrics[:6])}")
        section.append("")

        if drift_signals:
            section.append(f"YEAR-OVER-YEAR DRIFT SIGNALS ({len(drift_signals)} detected)")
            section.append("-" * 70)
            for d in drift_signals[:8]:
                if not isinstance(d, dict):
                    continue
                arrow = {"improved": "↓ improved", "worsened": "↑ worsened", "stable": "→ stable"}.get(
                    d.get("direction", ""), d.get("direction", "?")
                )
                pct = d.get("delta_pct")
                pct_str = f"{pct:+.1f}%" if isinstance(pct, (int, float)) else "n/a"
                section.append(
                    f"  • {d.get('metric_name', '?'):<25} {arrow:<14} ({pct_str})  "
                    f"prior: {d.get('prior_value')}  current: {d.get('current_value')}"
                )
                _ts = d.get("prior_run_ts") or ""
                if _ts:
                    section.append(f"      compared to run on {_ts[:10]}")
            section.append("")
        else:
            section.append("YEAR-OVER-YEAR DRIFT SIGNALS")
            section.append("-" * 70)
            # Distinguish "this is the first run" from "prior run exists but
            # no comparable metrics yet drifted". Without this, the report
            # said "1 prior run recorded" two lines above and "no prior
            # recorded values" here — internally contradictory.
            try:
                _hr = int(history_runs or 0)
            except (TypeError, ValueError):
                _hr = 0
            if _hr == 0:
                section.append("  No prior recorded values for this company yet —")
                section.append("  drift signals will appear from the second run onward.")
            else:
                section.append(
                    f"  Prior runs recorded: {_hr}, but no metrics changed by enough to trigger"
                )
                section.append(
                    "  a drift signal this cycle (default threshold ±5% YoY)."
                )
            section.append("")

        if fg_motifs:
            section.append("FACT GRAPH MOTIFS (this run)")
            section.append("-" * 70)
            cov = fg_motifs.get("pillar_coverage") or {}
            if cov:
                cov_str = "  ".join(f"{k}={v}" for k, v in cov.items())
                section.append(f"  Pillar coverage:        {cov_str}")
            skew = fg_motifs.get("pillar_coverage_skew")
            if isinstance(skew, (int, float)):
                _interp = "balanced" if skew <= 2 else ("moderate skew" if skew <= 5 else "heavy skew — analysis is one-pillar-dominated")
                section.append(f"  Pillar coverage skew:   {skew}  ({_interp})")
            cd = fg_motifs.get("contradiction_density")
            if isinstance(cd, (int, float)):
                _interp = "low" if cd < 0.2 else ("moderate" if cd < 0.5 else "high — many evidence items oppose the claim")
                section.append(f"  Contradiction density:  {cd:.3f}  ({_interp})")
            gd = fg_motifs.get("graph_density")
            if isinstance(gd, (int, float)):
                section.append(f"  Graph density:          {gd:.3f}")
            ready = fg_motifs.get("is_decision_ready")
            if ready is not None:
                section.append(f"  Decision-ready graph:   {'Yes' if ready else 'No'}")
            section.append("")

        section.append(major)
        return section

    def _render_esg_mismatch_section(self, state: Dict[str, Any], major: str) -> List[str]:
        """Render a dedicated mismatch section so it is always visible in text reports."""
        section = [major, "SECTION 12: ESG MISMATCH DETECTOR", major]
        mismatch = state.get("esg_mismatch_analysis")

        if not isinstance(mismatch, dict) or not mismatch:
            section.append("No ESG mismatch analysis payload was provided for this run.")
            section.append(major)
            return section

        company = str(mismatch.get("Company Analyzed") or state.get("company") or "Unknown").strip() or "Unknown"
        overall = str(mismatch.get("Overall Greenwashing Risk") or mismatch.get("overall_risk_level") or "N/A").strip() or "N/A"
        summary = str(mismatch.get("Executive Summary") or mismatch.get("summary") or "No mismatch summary available.").strip()

        section.append(f"Company analyzed: {company}")
        section.append(f"Mismatch risk level: {overall}")
        section.append("")
        section.append("Summary:")
        section.append(self._wrap_paragraph(summary, width=80))
        section.append("")

        future = mismatch.get("1. Future Commitments & Progress") or mismatch.get("future_commitments") or []
        if not isinstance(future, list):
            future = []

        gaps = mismatch.get("2. Past Promise-Implementation Gaps (Mismatches)") or mismatch.get("past_gaps") or []
        if not isinstance(gaps, list):
            gaps = []

        if future:
            section.append("Future commitments and progress:")
            for idx, item in enumerate(future[:3], start=1):
                if not isinstance(item, dict):
                    continue
                pledge = str(item.get("Pledge") or item.get("pledge") or "Unspecified pledge").strip()
                status = str(item.get("Status Trend") or item.get("status") or "Under verification").strip()
                progress = str(item.get("Progress/Trend") or item.get("progress") or "No progress detail provided").strip()
                section.append(f"  {idx}. Pledge: {pledge}")
                section.append(f"     Status: {status} | Progress: {progress}")
            section.append("")

        # Filter out non-dict placeholders ("Inconclusive due to insufficient data."
        # is a string, not a structured gap) — only emit the subsection when
        # there is actual structured content.
        structured_gaps = [g for g in gaps if isinstance(g, dict)]
        if structured_gaps:
            section.append("Past promise-implementation gaps:")
            for idx, item in enumerate(structured_gaps[:3], start=1):
                failed = str(item.get("Failed Pledge") or item.get("failed_pledge") or "Unspecified pledge").strip()
                flagged = str(item.get("Flagged Status") or item.get("flagged_status") or "No flagged status").strip()
                risk = str(item.get("Risk Level") or item.get("risk_level") or "Unknown").strip()
                evidence = str(item.get("Evidence Source") or item.get("evidence_source") or "N/A").strip()
                if evidence.startswith("http"):
                    import urllib.parse
                    try:
                        domain = urllib.parse.urlparse(evidence).netloc.replace("www.", "")
                        evidence = f"Source: {domain}"
                    except Exception:
                        pass
                elif len(evidence) > 60:
                    evidence = evidence[:57] + "..."
                section.append(f"  {idx}. Failed pledge: {failed}")
                section.append(f"     Flag: {flagged} | Risk: {risk}")
                section.append(f"     Evidence: {evidence}")
            section.append("")

        if not future and not structured_gaps:
            section.append("No structured mismatch entries were provided by the mismatch detector.")

        section.append(major)
        return section

    def _confidence_label(self, pct: float, quality_label: Optional[str] = None) -> str:
        """Map percentage to a coarse confidence label.

        When ``quality_label`` is provided (from ReportQualityChecker), use
        the more conservative of the two — i.e. if the percentage suggests
        MEDIUM but the quality checker downgraded to LOW (due to coverage/
        evidence gaps), surface LOW. Without this rule, Section 3 said
        "59.0% (MEDIUM)" while the header/JSON said LOW for the same run.
        """
        pct_label = "HIGH" if pct >= 75 else "MEDIUM" if pct >= 50 else "LOW"
        if not quality_label:
            return pct_label
        # Pick the more conservative of (pct-derived, quality-derived).
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        q = quality_label.upper().strip()
        if q not in order:
            return pct_label
        return pct_label if order[pct_label] <= order[q] else q

    def _rating_from_esg_score(self, esg_score: Any) -> str:
        if not isinstance(esg_score, (int, float)):
            return "BBB"
        v = float(esg_score)
        if v >= 85:
            return "AAA"
        if v >= 75:
            return "AA"
        if v >= 65:
            return "A"
        if v >= 55:
            return "BBB"
        if v >= 45:
            return "BB"
        if v >= 35:
            return "B"
        if v >= 20:
            return "CCC"
        return "C"

    def _risk_band(self, score: float) -> str:
        if score >= 75:
            return "CRITICAL"
        if score >= 60:
            return "HIGH"
        if score >= 40:
            return "MODERATE"
        return "LOW"

    def _shorten_factor_name(self, name: str) -> str:
        cleaned = str(name or "Unknown factor").strip()
        replacements = {
            "Board independence disclosure": "Board independence discl.",
            "Executive compensation ESG link": "Exec comp ESG link",
            "Diversity & inclusion disclosure": "D&I disclosure",
            "Labor rights disclosure": "Labor rights discl.",
        }
        if cleaned in replacements:
            return replacements[cleaned]
        return cleaned.replace("disclosure", "discl.")

    def _collect_v4_values(self, state: Dict[str, Any], structured: Dict[str, Any], quality: Dict[str, Any]) -> Dict[str, Any]:
        metadata = structured.get("metadata", {}) or {}
        scores = structured.get("scores", {}) or {}
        evidence = structured.get("evidence", {}) or {}
        pillars = structured.get("pillars", {}) or {}
        peers = structured.get("peers", {}) or {}
        agents = structured.get("agents", {}) or {}
        calibration = structured.get("calibration", {}) or {}

        company = str(safe_get(structured, "company", "name", default="Unknown")).strip() or "Unknown"
        claim = str(safe_get(structured, "company", "claim", default="No claim provided")).strip() or "No claim provided"
        raw_industry = str(scores.get("industry") or safe_get(structured, "company", "industry", default=state.get("industry") or "Unknown")).strip() or "Unknown"
        industry = normalize_industry_label(raw_industry)
        industry_key = normalize_industry_key(raw_industry)
        ticker = str(
            state.get("ticker")
            or state.get("symbol")
            or state.get("stock_ticker")
            or TICKER_SYMBOL_MAP.get(company)
            or TICKER_SYMBOL_MAP.get(state.get("company", ""))
            or "N/A"
        ).strip() or "N/A"

        node_order = state.get("node_execution_order") or []
        workflow_steps: List[str] = []
        if isinstance(node_order, list):
            for n in node_order:
                n_txt = str(n).strip()
                if n_txt and n_txt not in workflow_steps:
                    workflow_steps.append(n_txt)
        if not workflow_steps:
            workflow_steps = [str(a.get("agent")) for a in (state.get("agent_outputs") or []) if isinstance(a, dict) and a.get("agent")]
            workflow_steps = list(dict.fromkeys(workflow_steps))
        if len(workflow_steps) > 15:
            workflow = " → ".join(workflow_steps[:15]) + " ..."
        else:
            workflow = " → ".join(workflow_steps) if workflow_steps else "workflow_unavailable"
        if len(workflow) > 300:
            workflow = workflow[:297] + "..."

        # ── Scores/ratings: trust report_consistency first ──────────────────
        _rc = structured.get("report_consistency", {}) if isinstance(structured.get("report_consistency"), dict) else {}
        if _rc:
            gw_score = float(_rc.get("final_gw_calibrated", 55.0))
            esg_score = float(_rc.get("final_esg_display", 50.0))
            rating = str(_rc.get("final_rating", "BBB"))
            band = str(_rc.get("final_band", "MODERATE")).upper()
        else:
            # Fallback: old derivation for backward compatibility
            gw_score = self._safe_float(scores.get("greenwashingriskscore"), 55.0)
            esg_score = scores.get("esg_score")
            if not isinstance(esg_score, (int, float)):
                esg_score = max(0.0, min(100.0, 100.0 - gw_score))
            rating = str(scores.get("ratinggrade") or scores.get("rating_grade") or scores.get("esg_rating") or self._rating_from_esg_score(esg_score))
            band = str(scores.get("risklevel") or scores.get("risk_level") or self._risk_band(gw_score)).upper()
            if rating.upper() in {"CCC", "C"} and band in {"LOW", "MODERATE"}:
                band = "HIGH"
        conf_raw = scores.get("confidence")
        conf_pct = float(conf_raw * 100) if isinstance(conf_raw, (int, float)) and conf_raw <= 1 else self._safe_float(conf_raw, 0.0)
        if conf_pct <= 0:
            conf_pct = 70.0 if quality.get("report_confidence_level") == "HIGH" else 60.0 if quality.get("report_confidence_level") == "MEDIUM" else 45.0
        conf_ceiling = calibration.get("confidence_ceiling_pct")
        if isinstance(conf_ceiling, (int, float)):
            conf_pct = min(conf_pct, float(conf_ceiling))
        report_confidence = str(quality.get("report_confidence_level", "MEDIUM") or "MEDIUM").upper()

        # Reliability guardrails: cap displayed confidence by evidence quality and report tier.
        confidence_caps: List[float] = []
        if report_confidence == "LOW":
            confidence_caps.append(59.0)
        elif report_confidence == "MEDIUM":
            confidence_caps.append(74.0)
        else:
            confidence_caps.append(90.0)

        evidence_citations = evidence.get("citations", []) if isinstance(evidence, dict) else []
        total_citations = len(evidence_citations) if isinstance(evidence_citations, list) else 0
        verified_sources = int(
            quality.get("verified_source_count")
            or evidence.get("verifiable_citations")
            or 0
        )
        real_peer_count = int(quality.get("real_peer_count") or 0)

        if total_citations < 3:
            confidence_caps.append(55.0)
        elif total_citations < 5:
            confidence_caps.append(65.0)

        if verified_sources < 3:
            confidence_caps.append(58.0)

        raw_report_tier = str(safe_get(scores, "raw", "report_tier", default="") or "").upper()
        if raw_report_tier == "TIER_3":
            confidence_caps.append(55.0)
        elif raw_report_tier == "TIER_2":
            confidence_caps.append(72.0)

        if real_peer_count <= 0:
            confidence_caps.append(85.0)

        if confidence_caps:
            capped_conf = min(confidence_caps)
            if conf_pct > capped_conf:
                conf_pct = capped_conf

        # Use ReportQualityChecker's label as a conservative override —
        # so a "59% (MEDIUM by pct)" run with a LOW quality label
        # consistently shows LOW everywhere, not MEDIUM in Section 3 and
        # LOW in the JSON.
        _quality_label = quality.get("report_confidence_level") if isinstance(quality, dict) else None
        conf_label = self._confidence_label(conf_pct, quality_label=_quality_label)

        _raw_threshold = calibration.get("optimal_threshold")
        threshold = float(_raw_threshold) if isinstance(_raw_threshold, (int, float)) else None
        if threshold is not None:
            delta = gw_score - threshold
            cal_status = f"Score is {abs(delta):.1f} pts {'above' if delta >= 0 else 'below'} the {threshold:.1f} threshold"
        else:
            cal_status = "Calibration not available — threshold not computed"

        # ── Contradictions: trust structured resolver first ─────────────────
        _resolved_items = evidence.get("contradiction_items_resolved")
        _resolved_count = evidence.get("contradictions_count_resolved")
        if isinstance(_resolved_items, list) and _resolved_items:
            # Canonical path: use pre-resolved, pre-deduped contradictions
            contradiction_items = _resolved_items
            contradiction_count = int(_resolved_count) if isinstance(_resolved_count, int) else len(_resolved_items)
            contradiction_output = agents.get("contradiction_analysis", {}).get("output", {}) if isinstance(agents.get("contradiction_analysis"), dict) else {}
        else:
            # Fallback: old derivation (backward compat when structured is missing)
            print("  [WARN] contradiction_items_resolved missing from structured — using fallback chain")
            contradiction_output = agents.get("contradiction_analysis", {}).get("output", {}) if isinstance(agents.get("contradiction_analysis"), dict) else {}
            contradiction_items = []
            if isinstance(contradiction_output, dict):
                contradiction_items = (
                    contradiction_output.get("contradictions")
                    or contradiction_output.get("specific_contradictions")
                    or []
                )
            if not isinstance(contradiction_items, list):
                contradiction_items = []
            # State-level fallback
            if not contradiction_items:
                state_contras = state.get("contradiction_results", {})
                if isinstance(state_contras, dict):
                    contradiction_items = (
                        state_contras.get("contradictions")
                        or state_contras.get("specific_contradictions")
                        or []
                    )
                if not isinstance(contradiction_items, list):
                    contradiction_items = []
            # Risk results fallback
            if not contradiction_items:
                risk_results = state.get("riskresults", {})
                if isinstance(risk_results, dict):
                    top_contra = safe_get(risk_results, "topcontradictions", default=[])
                    if not isinstance(top_contra, list):
                        top_contra = safe_get(risk_results, "raw", "topcontradictions", default=[])
                    if isinstance(top_contra, list):
                        contradiction_items = [
                            {"description": c.get("detail") or c.get("description", ""),
                             "severity": c.get("severity", "HIGH"),
                             "source": c.get("citation") or c.get("source", "risk_scoring")}
                            for c in top_contra if isinstance(c, dict)
                        ]
            # pillarfactors.contradictions fallback
            if not contradiction_items:
                _rr = state.get("riskresults") or {}
                _pf_contras = [
                    c for c in ((_rr.get("pillarfactors") or {}).get("contradictions") or [])
                    if isinstance(c, dict)
                    and str(c.get("severity", "")).upper() == "HIGH"
                ]
                if _pf_contras:
                    contradiction_items = [
                        {
                            "description": str(c.get("description") or c.get("detail") or c.get("text") or "").strip(),
                            "severity": str(c.get("severity", "HIGH")).upper(),
                            "source": str(c.get("source") or c.get("citation") or "Known verified case"),
                            "year": c.get("year", "N/A"),
                            "confidence": str(c.get("confidence") or "HIGH"),
                        }
                        for c in _pf_contras
                    ]
            # Dedup (only needed in fallback path — canonical path already deduped)
            seen_texts = set()
            deduped_items = []
            for item in contradiction_items:
                if not isinstance(item, dict):
                    continue
                text_key = str(item.get("description") or item.get("text") or item.get("contradiction_text") or "").strip().lower()[:120]
                if text_key and text_key not in seen_texts:
                    seen_texts.add(text_key)
                    deduped_items.append(item)
                elif not text_key:
                    deduped_items.append(item)
            contradiction_items = deduped_items
            contradiction_count = int(contradiction_output.get("contradictions_found", len(contradiction_items))) if isinstance(contradiction_output, dict) else len(contradiction_items)
            if contradiction_count < len(contradiction_items):
                contradiction_count = len(contradiction_items)

        print(f"  [Section 7] contradiction_items collected: {len(contradiction_items)} "
              f"(resolved={isinstance(_resolved_items, list) and bool(_resolved_items)})")

        regulatory = (
            state.get("regulatory_results")
            or state.get("regulatory_compliance")
            or agents.get("regulatory_scanning", {}).get("output", {})
            or {}
        )
        if not isinstance(regulatory, dict):
            regulatory = {}
        compliance_results = regulatory.get("compliance_results", []) or []
        if not isinstance(compliance_results, list):
            compliance_results = []
        reg_gaps = [
            r for r in compliance_results
            if isinstance(r, dict)
            and len(r.get("gap_details", []) or []) > 0
            and str(r.get("status", "")).upper() not in ("UNCERTAIN", "COMPLIANT")
        ]

        raw_carbon = state.get("carbon_results") or state.get("carbon_extraction") or agents.get("carbon_extraction", {}).get("output", {}) or {}
        if not isinstance(raw_carbon, dict):
            raw_carbon = {}
            
        validator = CarbonDataValidator()
        emissions_obj = raw_carbon.get("emissions") if isinstance(raw_carbon.get("emissions"), dict) else {}
        scope1_obj = emissions_obj.get("scope1") if isinstance(emissions_obj.get("scope1"), dict) else {}
        scope2_obj = emissions_obj.get("scope2") if isinstance(emissions_obj.get("scope2"), dict) else {}
        scope3_obj = emissions_obj.get("scope3") if isinstance(emissions_obj.get("scope3"), dict) else {}

        scope1_val = scope1_obj.get("value") if isinstance(scope1_obj, dict) else None
        scope2_val = scope2_obj.get("value") if isinstance(scope2_obj, dict) else None
        scope3_val = (scope3_obj.get("total") or scope3_obj.get("value")) if isinstance(scope3_obj, dict) else None

        total_dict = emissions_obj.get("total") if isinstance(emissions_obj.get("total"), dict) else {}
        combined_val = (
            total_dict.get("scope1_2")
            or total_dict.get("all_scopes")
        )
        if scope1_val is None and scope2_val is None and combined_val:
            scope1_val = combined_val

        dq = raw_carbon.get("data_quality")
        if isinstance(dq, dict):
            dq_score = dq.get("overall_score") or dq.get("score") or 0
        elif isinstance(dq, (int, float)):
            dq_score = dq
        else:
            dq_score = 0

        has_data = any(v is not None for v in [scope1_val, scope2_val, scope3_val])
        if has_data and dq_score == 0:
            dq_score = 55

        flat_carbon = {
            "scope1": scope1_val,
            "scope2": scope2_val,
            "scope3": scope3_val,
            "data_year": scope1_obj.get("year") if isinstance(scope1_obj, dict) else None,
            "data_quality": dq_score,
            "source": scope1_obj.get("source", "PDF extraction") if isinstance(scope1_obj, dict) else "PDF extraction",
            "emissions_detail": emissions_obj,
        }
        
        validated_carbon = validator.validate(flat_carbon, company, industry, report_year=datetime.now().year)
        # FIX: safe access — validate() should always return a dict with 'validation' but guard anyway
        _vc_validation = validated_carbon.get("validation", {}) if isinstance(validated_carbon, dict) else {}

        if not _vc_validation.get("passed", True):
            logger = logging.getLogger(__name__)
            logger.warning("Carbon data rejected for %s | reasons: %s", company, _vc_validation.get("rejection_reasons", []))
            try:
                from core.carbon_retrieval import fetch_carbon_with_fallback
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    import threading
                    _res = []
                    def _run():
                        _res.append(asyncio.run(
                            fetch_carbon_with_fallback(company, ticker, industry, "US", datetime.now().year)
                        ))
                    _t = threading.Thread(target=_run)
                    _t.start()
                    _t.join(timeout=30)  # FIX: never block indefinitely
                    fallback_carbon = _res[0] if _res else validated_carbon  # FIX: guard empty list
                else:
                    fallback_carbon = asyncio.run(
                        fetch_carbon_with_fallback(company, ticker, industry, "US", datetime.now().year)
                    )
                validated_carbon = fallback_carbon if isinstance(fallback_carbon, dict) else validated_carbon
            except Exception as e:
                logger.error(f"Fallback fetch failed: {e}")

        carbon = dict(raw_carbon)
        if "emissions" not in carbon:
            carbon["emissions"] = {}
        # Merge validated values into existing scope dicts so subkeys like
        # `boundary` (Scope 3 boundary classification) and other extractor-
        # supplied metadata aren't dropped by the validation step. Without
        # this merge, a flat assignment like {"value", "year", "source"}
        # silently strips fields the renderer needs.
        for _scope_key, _val_field, _val in (
            ("scope1", "value", validated_carbon.get("scope1")),
            ("scope2", "value", validated_carbon.get("scope2")),
            ("scope3", "total", validated_carbon.get("scope3")),
        ):
            existing = carbon["emissions"].get(_scope_key) or {}
            if not isinstance(existing, dict):
                existing = {}
            existing.update({
                _val_field: _val,
                "year": validated_carbon.get("data_year") or existing.get("year"),
                "source": validated_carbon.get("source") or existing.get("source"),
            })
            carbon["emissions"][_scope_key] = existing
        # Preserve top-level lifecycle_emissions if the extractor set it.
        if "lifecycle_emissions" not in carbon and isinstance(raw_carbon, dict):
            _le = raw_carbon.get("lifecycle_emissions")
            if _le:
                carbon["lifecycle_emissions"] = _le
        if "data_quality" not in carbon:
            carbon["data_quality"] = {}
        carbon["data_quality"]["overall_score"] = validated_carbon.get("data_quality", 0)
        carbon["validation"] = validated_carbon.get("validation", {})
        carbon["source_chain"] = validated_carbon.get("source_chain", [])

        citations = evidence.get("citations", []) or []
        premium = 0
        for c in citations:
            if not isinstance(c, dict):
                continue
            tier = str(c.get("reliability_tier", "")).lower()
            if "regulatory filing" in tier or "cdp / third-party verified" in tier:
                premium += 1

        peer_rows = peers.get("all_peers", []) or []
        if not peer_rows:
            peer_rows = (state.get("peer_comparison") or {}).get("peers", []) or []
        if not peer_rows:
            peer_rows = ((agents.get("peer_comparison") or {}).get("output", {}) or {}).get("peers", []) or []
        if not isinstance(peer_rows, list):
            peer_rows = []
        same_industry_peers: List[Dict[str, Any]] = []
        ind_norm = industry_key
        for p in peer_rows:
            if not isinstance(p, dict):
                continue
            p_ind_raw = p.get("industry") or p.get("sector")
            p_ind = normalize_industry_key(p_ind_raw) if p_ind_raw else ""
            if p_ind and ind_norm and p_ind != ind_norm:
                continue
            same_industry_peers.append(p)

        risk_raw = scores.get("raw", {}) if isinstance(scores.get("raw"), dict) else {}
        external_state = state.get("external_esg_data", {})
        if not isinstance(external_state, dict):
            external_state = {}
        external_from_risk = risk_raw.get("external_benchmarks", {})
        if not isinstance(external_from_risk, dict):
            external_from_risk = {}
        external_data = dict(external_state)
        if external_from_risk:
            external_data.update(external_from_risk)

        external_sources = external_data.get("sources", {}) if isinstance(external_data.get("sources"), dict) else {}
        external_scores = external_data.get("scores", {}) if isinstance(external_data.get("scores"), dict) else {}
        external_adjustments = safe_get(scores, "pillar_scores", "external_benchmark_adjustments", default=[])
        if not isinstance(external_adjustments, list):
            external_adjustments = []
        external_used = bool(safe_get(scores, "pillar_scores", "external_benchmarks_used", default=False))
        external_enabled = bool(external_data.get("enabled") or external_sources)

        # 2026 Engine High-Fidelity Diagnostics
        claim_decomposition = state.get("claim_decomposition") or safe_get(agents, "claim_decomposition", "output", default={})
        commitment_ledger = state.get("commitment_ledger") or safe_get(agents, "commitment_ledger", "output", default={})
        carbon_pathway = state.get("carbon_pathway_analysis") or safe_get(agents, "carbon_pathway", "output", default={})
        adversarial_triangulation = state.get("adversarial_triangulation") or safe_get(agents, "adversarial_triangulation", "output", default={})
        regulatory_scanning = state.get("regulatory_scanning") or safe_get(agents, "regulatory_scanning", "output", default={})

        v = {
            "metadata": metadata,
            "scores": scores,
            "evidence": evidence,
            "pillars": pillars,
            "agents": agents,
            "peers": peers,
            "calibration": calibration,
            "company": company,
            "ticker": ticker,
            "industry": industry,
            "claim": claim,
            "workflow": workflow,
            "gw_score": gw_score,
            "esg_score": float(esg_score),
            "rating": rating,
            "band": band,
            "confidence_pct": conf_pct,
            "confidence_label": conf_label,
            "threshold": threshold,
            "calibration_status": cal_status,
            "contradiction_output": contradiction_output,
            "contradiction_items": contradiction_items,
            "contradiction_count": contradiction_count,
            "regulatory": regulatory,
            "reg_gaps": reg_gaps,
            "carbon": carbon,
            "citations": citations,
            "premium_count": premium,
            "same_industry_peers": same_industry_peers,
            "quality_warnings": quality.get("quality_warnings", []),
            "report_confidence": report_confidence,
            "limitations": structured.get("limitations", []) or [],
            "external_benchmarks": structured.get("benchmarks") or {
                "enabled": external_enabled,
                "used": external_used,
                "sources": external_sources,
                "scores": external_scores,
                "adjustments": external_adjustments,
                "wba_company_name": external_data.get("wba_company_name"),
                "wba_indicator_count": external_data.get("wba_indicator_count", 0),
                "wba_data_year": external_data.get("wba_data_year"),
                "wba_adjustment_allowed": external_data.get("wba_indicator_count", 0) > 0,
                "error": external_data.get("error"),
            },
            # Decision state from canonical resolver
            "decision": structured.get("decision") or {},
            "abstain_recommended": (structured.get("decision") or {}).get("abstain_recommended", False),
            "decision_status": (structured.get("decision") or {}).get("decision_status", "SCORED"),
            "abstention_reason": (structured.get("decision") or {}).get("abstention_reason", ""),
            "score_disclaimer": (structured.get("decision") or {}).get("score_disclaimer", ""),
            # GW delta from canonical resolver
            "gw_raw": _rc.get("final_gw_raw", gw_score) if _rc else gw_score,
            "gw_delta": _rc.get("final_gw_delta", 0.0) if _rc else 0.0,
            # Calibration render status
            "calibration_render_status": calibration.get("render_status", "uncalibrated"),
            # 2026 Engine High-Fidelity Diagnostics
            "feature_signals": {
                "claim_decomposition": claim_decomposition,
                "commitment_ledger": commitment_ledger,
                "carbon_pathway": carbon_pathway,
                "adversarial_triangulation": adversarial_triangulation,
                "regulatory_scanning": regulatory_scanning,
            }
        }

        if not v["contradiction_items"]:
            verdict_findings = self._build_verdict_findings(agents, scores, v)
            for finding in verdict_findings:
                if not isinstance(finding, str):
                    continue
                # Skip findings that are verdict-warning artifacts ("[~]"
                # MEDIUM informational lines, "[i]" info lines, summary
                # statements about regulatory gaps already shown in Section
                # 7). These are NOT contradictions between claim and
                # evidence — promoting them creates the bizarre
                # "[MEDIUM] [~] MEDIUM - Regulatory gaps identified..." rows
                # the user spotted in Tesla's report.
                stripped = finding.strip()
                if stripped.startswith(("[~]", "[i]", "[~ ]", "[i ]")):
                    continue
                if "regulatory gaps identified" in stripped.lower():
                    continue
                if "sources analyzed" in stripped.lower():
                    continue
                upper = stripped.upper()
                if any(kw in upper for kw in ["HIGH", "CRITICAL", "!", "MISALIGN", "GAP"]):
                    v["contradiction_items"].append({
                        "description": stripped.strip("! "),
                        "severity": "HIGH" if "!" in stripped or "CRITICAL" in upper else "MEDIUM",
                        "source": "Integrated multi-agent verdict analysis",
                    })

            seen_texts = set()
            deduped_items = []
            for item in v["contradiction_items"]:
                if not isinstance(item, dict):
                    continue
                text_key = str(
                    item.get("description")
                    or item.get("text")
                    or item.get("contradiction_text")
                    or ""
                ).strip().lower()
                if text_key and text_key not in seen_texts:
                    seen_texts.add(text_key)
                    deduped_items.append(item)
                elif not text_key:
                    deduped_items.append(item)
            v["contradiction_items"] = deduped_items

        v["contradiction_count"] = max(
            int(v.get("contradiction_count", 0) or 0),
            len(v.get("contradiction_items", []) or []),
        )
        return v

    def _safe_section(self, section_name: str, fn, *args, **kwargs):
        """Execute fn(*args, **kwargs) isolated — any crash yields a placeholder section."""
        try:
            return fn(*args, **kwargs)
        except Exception as _sec_exc:
            import traceback as _tb2
            _tb2.print_exc()
            _m = "=" * 80
            return "\n".join([
                _m,
                f"{section_name} [SECTION UNAVAILABLE]",
                _m,
                f"  Error rendering section: {type(_sec_exc).__name__}: {_sec_exc}",
                "  All other sections and the JSON export are unaffected.",
                _m,
            ])

    def _render_v4_report(self, state: Dict[str, Any], structured: Dict[str, Any], quality: Dict[str, Any], payload: ReportPayload = None) -> str:
        if payload is None:
            payload = ReportPayload()
            payload.unified_evidence = self._parse_unified_evidence(state)
            payload.evidence_roles = self._count_evidence_roles(payload.unified_evidence)
            payload.esg_lineage = state.get("esg_score_lineage", {})
        major = self._major_divider()
        minor = self._minor_divider()
        v = self._collect_v4_values(state, structured, quality)

        # ── FIELD SANITIZER ──────────────────────────────────────────────────────
        # When triggered via the frontend subprocess path, fields in the collected
        # values dict may be wrong-typed (None, string, int) if state was partially
        # reconstructed.  Normalise every field that any render section reads so
        # that downstream code never encounters a type surprise.
        _list_fields = ["citations", "contradiction_items", "reg_gaps",
                        "same_industry_peers", "limitations", "quality_warnings"]
        for _f in _list_fields:
            if not isinstance(v.get(_f), list):
                v[_f] = []
        _dict_fields = ["evidence", "scores", "agents", "calibration",
                        "regulatory", "carbon", "contradiction_output",
                        "external_benchmarks", "metadata"]
        for _f in _dict_fields:
            if not isinstance(v.get(_f), dict):
                v[_f] = {}
        if not isinstance(v.get("gw_score"), (int, float)):
            v["gw_score"] = 55.0
        if not isinstance(v.get("esg_score"), (int, float)):
            v["esg_score"] = 50.0  # Default to neutral, not derived from GW
        if not isinstance(v.get("confidence_pct"), (int, float)):
            v["confidence_pct"] = 45.0
        if not isinstance(v.get("contradiction_count"), int):
            v["contradiction_count"] = len(v["contradiction_items"])
        for _sf in ["band", "rating", "company", "industry", "claim",
                    "ticker", "workflow", "report_confidence",
                    "calibration_status", "confidence_label"]:
            if not isinstance(v.get(_sf), str) or not v[_sf]:
                _defaults = {
                    "band": "MODERATE", "rating": "BBB",
                    "company": "Unknown", "industry": "Unknown",
                    "claim": "No claim provided", "ticker": "N/A",
                    "workflow": "workflow_unavailable",
                    "report_confidence": "MEDIUM",
                    "calibration_status": "Calibration not available",
                    "confidence_label": "MEDIUM",
                }
                v[_sf] = _defaults.get(_sf, "Unknown")
        # ── END SANITIZER ─────────────────────────────────────────────────────────

        industry_label = v.get("industry", "Unknown")
        ts = self._coerce_datetime(v["metadata"].get("timestamp_dt"))  # FIX: str→datetime safe
        report_id = str(v["metadata"].get("report_id") or f"{ts.strftime('%Y%m%d-%H%M%S')}-{v['company'][:4].upper()}")
        date_line = ts.strftime("%d %B %Y at %H:%M UTC")
        report_version = "4.0"

        claim_wrapped = textwrap.wrap(v["claim"], width=80)
        claim_line = f"Claim Analyzed:     {claim_wrapped[0] if claim_wrapped else 'No claim provided'}"
        claim_tail = [f"{'':20}{c}" for c in claim_wrapped[1:]]

        verdict_drivers = self._build_verdict_drivers(v)
        summary_sentence = self._build_verdict_summary(
            v["company"],
            v["band"],
            v["gw_score"],
            verdict_drivers,
        )

        verdict_findings = self._build_verdict_findings(v["agents"], v["scores"], v)
        if len(verdict_findings) < 2:
            verdict_findings.append("[i] INFO - Additional analysis completed without critical warning flags")
        if len(verdict_findings) < 2:
            verdict_findings.append("[i] INFO - Report contains multi-agent triangulation across evidence and scoring")
        verdict_findings = [f for f in verdict_findings if self._is_human_readable_text(f)][:5]

        section1_text = (
            f"This assessment evaluates {v['company']}'s claim using multi-agent evidence retrieval, contradiction checks, and calibrated ESG risk scoring. "
            f"The resulting greenwashing score is {v['gw_score']:.1f}/100, indicating {v['band'].lower()} risk under the current thresholding policy. "
            f"The evidence base includes {len(v['citations'])} total sources, with {v['evidence'].get('verifiable_citations', 0)} verifiable citations. "
            f"Overall confidence for this run is {v['confidence_pct']:.1f}% ({v['confidence_label']})."
        )

        decomposition = state.get("claim_decomposition") if isinstance(state.get("claim_decomposition"), dict) else {}
        sub_claims = decomposition.get("sub_claims") if isinstance(decomposition.get("sub_claims"), list) else []
        section_anatomy = [major, "SECTION 3B: CLAIM BREAKDOWN", major]
        if not sub_claims:
            section_anatomy.append("Claim breakdown was not available for this run.")
        else:
            section_anatomy.append("The claim is broken down into key components for evaluation:")
            section_anatomy.append("")
            for sc in sub_claims[:8]:
                if isinstance(sc, dict):
                    txt = self._clean_executive_text(sc.get("text") or sc.get("claim") or sc.get("description"), max_len=150)
                    claim_type = self._human_claim_type(sc.get("type") or sc.get("claim_type"))
                else:
                    txt = self._clean_executive_text(sc, max_len=150)
                    claim_type = ""
                if txt:
                    suffix = f" ({claim_type})" if claim_type else ""
                    section_anatomy.append(f"  • {txt}{suffix}")
        section_anatomy.append(major)

        triangulation = state.get("adversarial_triangulation") if isinstance(state.get("adversarial_triangulation"), dict) else {}
        tri_stance_map: Dict[str, str] = {}
        if triangulation and isinstance(triangulation.get("source_stances"), list):
            for row in triangulation.get("source_stances", []):
                if not isinstance(row, dict):
                    continue
                k = str(row.get("source_name") or "").strip().lower()
                stance_val = str(row.get("stance") or "").strip().upper()
                if k and stance_val:
                    tri_stance_map[k] = stance_val

        # Cross-reference Section 4 citations against the canonical contradictions list
        # so sources that produced HIGH-severity contradictions show "Contradicts" here
        # instead of defaulting to "Neutral" (Section 4 ↔ Section 7 consistency).
        # Build per-contradiction records keyed by canonical name + URL domain,
        # so we can both (a) override matching citation rows AND (b) append
        # phantom contradiction sources that were never in the evidence pool.
        contradiction_records: List[Dict[str, Any]] = []
        seen_contra_keys: Set[str] = set()
        # Pull from every reasonable source the live + replay paths might use.
        # Live pipeline writes to state["contradiction_results"]; replay also
        # sets state["contradictions"]; either way the contradiction_analysis
        # agent_output has the data — falling back through all three guarantees
        # we don't silently miss them.
        _contra_sources_to_check: List[Any] = [
            state.get("contradictions"),
            (state.get("contradiction_results") or {}).get("specific_contradictions"),
            (state.get("contradiction_results") or {}).get("contradictions"),
            (state.get("contradiction_results") or {}).get("contradiction_list"),
        ]
        # Last-resort fallback: dig into agent_outputs for the contradiction_analysis entry.
        for _ao_row in (state.get("agent_outputs") or []):
            if isinstance(_ao_row, dict) and _ao_row.get("agent") == "contradiction_analysis":
                _ao_out = _ao_row.get("output") or {}
                if isinstance(_ao_out, dict):
                    _contra_sources_to_check.extend([
                        _ao_out.get("contradictions"),
                        _ao_out.get("specific_contradictions"),
                        _ao_out.get("contradiction_list"),
                    ])
                break
        for _contra_src in _contra_sources_to_check:
            if not isinstance(_contra_src, list):
                continue
            for _row in _contra_src:
                if not isinstance(_row, dict):
                    continue
                _sn = str(_row.get("source") or _row.get("source_name") or "").strip()
                _url = str(_row.get("source_url") or _row.get("url") or "").strip()
                _dom = (urlparse(_url).netloc or "").replace("www.", "").lower() if _url else ""
                _key = (_sn.lower() + "|" + _dom).strip("|")
                if not _key or _key in seen_contra_keys:
                    continue
                seen_contra_keys.add(_key)
                contradiction_records.append({
                    "source_name": _sn,
                    "source_url": _url,
                    "domain": _dom,
                    "severity": str(_row.get("severity") or "").upper(),
                    # Tokens used for substring matching against citation source names
                    # (e.g. contradiction "NZBA / Reuters" should match citation "Reuters").
                    "tokens": [
                        t for t in re.findall(r"[a-z][a-z0-9]+", _sn.lower())
                        if len(t) >= 4 and t not in {
                            "report", "data", "press", "news", "scan", "evidence",
                            "https", "http", "from", "with", "this", "that"
                        }
                    ],
                })

        def _citation_matches_contradiction(src_lc: str, dom_lc: str) -> Dict[str, Any] | None:
            for rec in contradiction_records:
                if rec.get("domain") and dom_lc and rec["domain"] == dom_lc:
                    return rec
                if rec.get("source_name") and src_lc and rec["source_name"].lower() == src_lc:
                    return rec
                # Token substring match (e.g. "reuters" within "nzba / reuters").
                for tok in rec.get("tokens") or []:
                    if tok in src_lc:
                        return rec
            return None

        matched_contra_keys: Set[str] = set()

        source_tier_counts = {
            "t1": 0,
            "t2": 0,
            "t3": 0,
            "t4": 0,
            "other": 0,
        }
        company_tokens = [
            t for t in re.findall(r"[a-z0-9]+", str(v.get("company") or "").lower())
            if t not in {"inc", "plc", "ltd", "limited", "corp", "corporation", "co", "company", "group", "sa", "ag", "nv", "llc"}
        ]
        primary_company_token = company_tokens[0] if company_tokens else ""
        first_party_count = 0
        seen_sources: Set[str] = set()
        citation_rows: List[Dict[str, Any]] = []
        role_counts = {"Supports": 0, "Contradicts": 0, "Neutral": 0, "Mixed": 0}
        for i, c in enumerate(v["citations"], start=1):
            if not isinstance(c, dict):
                continue
            src = self._citation_source_name(c, i)
            source_domain = (urlparse(str(c.get("url") or "")).netloc or "").replace("www.", "").lower()
            source_label = src.lower()
            is_first_party = bool(primary_company_token and (primary_company_token in source_domain or primary_company_token in source_label))
            if is_first_party:
                first_party_count += 1

            source_type = self._business_source_type(c, is_first_party)
            if source_type == "Regulatory Filing":
                source_tier_counts["t1"] += 1
            elif source_type == "Verified ESG Data":
                source_tier_counts["t2"] += 1
            elif source_type == "Major News":
                source_tier_counts["t3"] += 1
            elif source_type in {"Company Disclosure", "Web Source"}:
                source_tier_counts["t4"] += 1
            else:
                source_tier_counts["other"] += 1

            tri_stance = tri_stance_map.get(src.lower())
            stance = self._business_evidence_role(c, tri_stance)
            # Override to Contradicts when this source matches the canonical
            # contradictions list — Section 4 must agree with Section 7.
            if stance != "Contradicts" and contradiction_records:
                _hit = _citation_matches_contradiction(src.lower(), source_domain)
                if _hit is not None:
                    stance = "Contradicts"
                    matched_contra_keys.add(
                        (_hit.get("source_name", "").lower() + "|" + _hit.get("domain", "")).strip("|")
                    )
            if stance in role_counts:
                role_counts[stance] += 1

            dedupe_key = self._citation_dedupe_key(c, src)
            if dedupe_key in seen_sources:
                continue
            seen_sources.add(dedupe_key)
            citation_rows.append({
                "source": src,
                "source_type": source_type,
                "verified": "Yes" if c.get("verifiable") else "No",
                "stance": stance,
            })

        # Append phantom contradiction sources — items flagged in Section 7 that
        # were not in the retrieved evidence pool. Without this Section 4 hides
        # the contradicting evidence the headline score relies on.
        for rec in contradiction_records:
            _key = (rec.get("source_name", "").lower() + "|" + rec.get("domain", "")).strip("|")
            if _key in matched_contra_keys:
                continue
            _name = rec.get("source_name") or rec.get("domain") or "Contradicting source"
            _dedupe = self._citation_dedupe_key(
                {"source": _name, "url": rec.get("source_url"), "source_name": _name},
                _name,
            )
            if _dedupe in seen_sources:
                continue
            seen_sources.add(_dedupe)
            citation_rows.append({
                "source": _name,
                "source_type": self._business_source_type(
                    {"source": _name, "url": rec.get("source_url"), "source_name": _name},
                    False,
                ),
                "verified": "Yes",
                "stance": "Contradicts",
            })
            role_counts["Contradicts"] += 1

        tri_score = triangulation.get("triangulation_score") if triangulation else None
        adv_ratio = triangulation.get("adversarial_ratio") if triangulation else None
        
        # FIX: The table header MUST match the actual citation_rows rendered below.
        # Do not use triangulation.get("corroborating_sources") if it contradicts the actual role_counts.
        supporting_count = role_counts["Supports"]
        contradicting_count = role_counts["Contradicts"]

        # Use canonical contradiction_count to ensure Section 4 matches Section 7.
        # Trust the canonical count whenever it exceeds what the local stance/triangulation
        # accounting picked up — those upstream sources were missing HIGH-severity items
        # (e.g. when adversarial_ratio is 0 but resolved contradictions list has 4 entries).
        canonical_contra = int(v.get("contradiction_count", 0) or 0)
        if canonical_contra > contradicting_count:
            contradicting_count = canonical_contra
        # When we have material verified contradictions, suppress any "Strong/Low" verdict
        # that would otherwise arise from a stale tri_score with no contradicting flag.
        if canonical_contra >= 3:
            tri_score_for_label = None  # force the label fn off the score>=75 fast path
            adv_ratio_for_label = max(self._safe_float(adv_ratio, 0.0), 0.5)
        else:
            tri_score_for_label = tri_score
            adv_ratio_for_label = adv_ratio
        strength_label, strength_reason = self._evidence_strength_label(tri_score_for_label, supporting_count, contradicting_count, len(v["citations"]))
        contradiction_label, contradiction_reason = self._contradiction_level_label(adv_ratio_for_label, supporting_count, contradicting_count)
        evidence_summary = self._evidence_summary_sentence(strength_label, contradiction_label, supporting_count, contradicting_count)
        unique_label = "source" if len(citation_rows) == 1 else "sources"
        retrieved_label = "source" if len(v["citations"]) == 1 else "sources"

        sec2_lines = [
            major,
            "SECTION 4: EVIDENCE CITATIONS TABLE",
            major,
            self._wrap_paragraph(evidence_summary, width=80),
            "",
            f"Evidence Strength: {strength_label} ({strength_reason})",
            f"Contradiction Level: {contradiction_label} ({contradiction_reason})",
            f"Coverage: {len(citation_rows)} unique {unique_label} shown from {len(v['citations'])} retrieved {retrieved_label}; {v['evidence'].get('verifiable_citations', 0)} verified.",
            "Duplicate citations are consolidated by URL/domain for readability.",
            "",
            f"{'#':<4} {'Source':<28} {'Source Type':<20} {'Verified':<9} {'Evidence Role':<15}",
            "-" * 80,
        ]
        for i, row in enumerate(citation_rows, start=1):
            sec2_lines.append(
                f"{i:<4} {row['source'][:28]:<28} {row['source_type'][:20]:<20} "
                f"{row['verified']:<9} {row['stance']:<15}"
            )
        sec2_lines.extend([
            "-" * 80,
            "Source types: Regulatory Filing; Major News; Company Disclosure;",
            "              Verified ESG Data; Web Source.",
        ])

        total_sources = len(v["citations"])
        if total_sources > 0 and (source_tier_counts["t1"] + source_tier_counts["t2"]) == 0:
            sec2_lines.extend([
                "",
                "EVIDENCE QUALITY NOTE",
                "-" * 28,
                "No regulatory filings or verified ESG datasets were included in this evidence set.",
                f"Sources reviewed: {total_sources}.",
                self._wrap_paragraph(
                    f"The current mix is concentrated in web/news and company-controlled disclosures "
                    f"(first-party sources detected: {first_party_count}/{total_sources}).",
                    width=80,
                ),
                "For decision-grade assurance, add CDP, SBTi, Bloomberg, or relevant regulatory filings.",
            ])
        sec2_lines.append(major)

        carbon = v["carbon"]
        emissions = carbon.get("emissions", {}) if isinstance(carbon.get("emissions"), dict) else {}
        scope1 = emissions.get("scope1") or carbon.get("scope_1") or {}
        scope2 = emissions.get("scope2") or carbon.get("scope_2") or {}
        scope3 = emissions.get("scope3") or carbon.get("scope_3") or {}
        scope_vals = {
            "Scope 1": scope1.get("value") if isinstance(scope1, dict) else None,
            "Scope 2": scope2.get("value") if isinstance(scope2, dict) else None,
            "Scope 3": (scope3.get("total") if isinstance(scope3, dict) else None) or (scope3.get("value") if isinstance(scope3, dict) else None),
        }

        pillar_factors = safe_get(v["scores"], "raw", "pillarfactors", default={})
        if not isinstance(pillar_factors, dict):
            pillar_factors = {}

        renewable_pct = (
            carbon.get("renewable_energy_percentage")
            or carbon.get("renewable_pct")
            or pillar_factors.get("renewable_energy_pct")
        )

        pillar_score_map = safe_get(v["scores"], "pillar_scores", default={})
        if not isinstance(pillar_score_map, dict):
            pillar_score_map = {}
        e_raw = pillar_score_map.get("environmental_score")
        s_raw = pillar_score_map.get("social_score")
        g_raw = pillar_score_map.get("governance_score")
        e_missing = not isinstance(e_raw, (int, float))
        s_missing = not isinstance(s_raw, (int, float))
        g_missing = not isinstance(g_raw, (int, float))
        e_score = self._safe_float(e_raw, 0.0)
        s_score = self._safe_float(s_raw, 0.0)
        g_score = self._safe_float(g_raw, 0.0)
        raw_gw_score = self._safe_float(v["scores"].get("greenwashingscoreraw"), v["gw_score"])
        calibrated_delta = v["gw_score"] - raw_gw_score
        pillar_snapshot = {
            "Environmental": {"score": e_score, "missing": e_missing, "expected": 6, "block": pillar_factors.get("environmental", {}) if isinstance(pillar_factors, dict) else {}},
            "Social": {"score": s_score, "missing": s_missing, "expected": 5, "block": pillar_factors.get("social", {}) if isinstance(pillar_factors, dict) else {}},
            "Governance": {"score": g_score, "missing": g_missing, "expected": 6, "block": pillar_factors.get("governance", {}) if isinstance(pillar_factors, dict) else {}},
        }
        esg_performance_label = self._score_band_label(v.get("esg_score", 0))
        strongest_pillar = max(pillar_snapshot.items(), key=lambda item: -1 if item[1].get("missing") else item[1]["score"])[0]
        weakest_pillar = min(pillar_snapshot.items(), key=lambda item: 101 if item[1].get("missing") else item[1]["score"])[0]
        section5_summary = self._build_score_derivation_summary(
            esg_performance_label,
            pillar_snapshot,
            strongest_pillar,
            weakest_pillar,
        )

        score_header = [
            major,
            "SECTION 5: SCORE DERIVATION (E / S / G)",
            major,
            f"Overall greenwashing risk score: {v['gw_score']:.1f}/100  ->  Rating: {v['rating']}  ->  Band: {v['band']}",
            "",
            "Score interpretation:",
            self._wrap_paragraph(section5_summary, width=80),
            f"Strongest pillar: {strongest_pillar}. Weakest pillar: {weakest_pillar}.",
            "Missing indicators are treated as Limited Disclosure and are not converted into zero-value factor rows.",
            "",
            "Composite formula:",
            "  ESG Performance Score = (Environmental × w_E) + (Social × w_S) + (Governance × w_G)",
            "  Greenwashing Risk Score = α·max(0,(C-P)/σ)·100 + β·R + γ·(1-D/100)·100 + δ·T",
            "  Where: C=Claim Intensity, P=Performance, R=Controversy, D=Disclosure, T=Temporal Escalation",
            "  Note: ESG and Greenwashing scores are INDEPENDENT — a company can have high ESG AND high GW risk.",
            f"  Raw risk score (pre-calibration) = {raw_gw_score:.1f}/100",
            f"  Final risk score (post-calibration) = {v['gw_score']:.1f}/100  (delta: {calibrated_delta:+.1f})",
            "",
        ]
        # ── Score Modifier Ledger + GW Formula Inputs ────────────────────
        # Render BEFORE the pillar tables so they don't break the
        # Environmental factor table flow. Look in both the canonical scores
        # dict AND its `raw` (risk_scorer_result) subkey.
        _scores_dict = v.get("scores") if isinstance(v.get("scores"), dict) else {}
        _raw_dict = _scores_dict.get("raw") if isinstance(_scores_dict.get("raw"), dict) else {}
        modifier_ledger = (
            _scores_dict.get("scoremodifierledger")
            or _scores_dict.get("score_modifier_ledger")
            or _raw_dict.get("scoremodifierledger")
            or _raw_dict.get("score_modifier_ledger")
            or []
        )
        if isinstance(modifier_ledger, list) and modifier_ledger:
            score_header.extend([
                "SCORE MODIFIER LEDGER",
                "─" * 56,
            ])
            for row in modifier_ledger:
                if not isinstance(row, dict):
                    continue
                label = str(row.get("label") or "Modifier")
                value = row.get("value")
                value_txt = f"{float(value):+.2f}" if isinstance(value, (int, float)) else str(value)
                score_header.append(f"  {label:<36} {value_txt:>10}")
            score_header.append("")

            # ── GW FORMULA INPUTS (audit table) ──────────────────────────
            ledger_map = {
                row.get("label"): row.get("value")
                for row in modifier_ledger
                if isinstance(row, dict)
            }
            raw_scores = v["scores"].get("raw") or {}
            gw_formula = raw_scores.get("greenwashingformula") or raw_scores.get("greenwashing_formula") or {}
            formula_comps = gw_formula.get("formula_components") or {}
            industry_sigma = formula_comps.get("industry_sigma", "N/A")

            gw_vars = [
                ("C (Claim Intensity)", ledger_map.get("C (Claim Intensity)")),
                ("P (Performance Score)", ledger_map.get("P (Performance Score)")),
                ("Gap (C - P)", ledger_map.get("Gap (C - P)")),
                ("R (Controversy Risk)", ledger_map.get("R (Controversy Risk)")),
                ("D (Disclosure Completeness)", ledger_map.get("D (Disclosure Completeness)")),
                ("T (Temporal Escalation)", ledger_map.get("T (Temporal Escalation)")),
                ("Industry sigma", industry_sigma),
                ("GW Score (formula)", ledger_map.get("GW Score (formula)")),
                ("GW Score (recalibrated)", ledger_map.get("GW Score (recalibrated)")),
            ]
            score_header.append("GW FORMULA INPUTS")
            score_header.append("─" * 56)
            score_header.append(f"  {'Variable':<36} {'Resolved Value':>10}")
            score_header.append("  " + "-" * 50)
            for var_label, var_val in gw_vars:
                val_txt = f"{float(var_val):.1f}" if isinstance(var_val, (int, float)) else str(var_val or "N/A")
                score_header.append(f"  {var_label:<36} {val_txt:>10}")
            score_header.append("  " + "-" * 50)
            score_header.append("  Formula: GW = α·max(0,(C-P)/σ)·100 + β·R + γ·(1-D/100)·100 + δ·T")
            score_header.append("  ESG and Greenwashing scores are INDEPENDENT — computed from separate inputs.")
            score_header.append("")
        # ── End modifier ledger / formula inputs ─────────────────────────

        score_header.extend([
            f"ENVIRONMENTAL PILLAR - {self._pillar_score_text(e_score, e_missing)}",
            self._pillar_insight_line("Environmental", None if e_missing else e_score, pillar_snapshot["Environmental"]["block"]),
            "-" * 78,
            f"  {'Factor':<34} {'Signal':<18} {'Source':<32} {'Weight':<7} {'Contribution to Score':<22} {'Data Quality':<18}",
            "  " + "-" * 135,
        ])

        def _append_pillar_rows(block: Dict[str, Any], fallback_score: float, expected_total: int, score_missing: bool = False) -> Tuple[int, int, float]:
            sub = self._pillar_sub_indicators(block)
            total_indicators = len(sub) if len(sub) > 0 else expected_total
            scored_indicators = 0
            original_weight_sum = 0.0
            available_weight_sum = 0.0
            contribution_sum = 0.0
            normalized_weighted_sum = 0.0

            if not sub:
                score_header.append(
                    f"  {'Factor evidence unavailable':<34} {'Limited Disclosure':<18} "
                    f"{'risk_scoring':<20} {'-':<7} {'Limited Disclosure':<22} {'Limited Disclosure':<18}"
                )
                score_header.append("  " + "-" * 135)
                score_header.append(f"  Reported pillar score: {self._pillar_score_text(fallback_score, score_missing)}")
                score_header.append(f"  Coverage: 0/{total_indicators} indicators scored - Limited Disclosure")
                score_header.append("  Coverage-adjusted score: Data Not Available")
                return 0, total_indicators, fallback_score

            for factor in sub:
                if not isinstance(factor, dict):
                    continue
                full_name = self._clean_executive_text(factor.get("factor") or factor.get("name") or "Factor", max_len=120) or "Factor"
                name = self._shorten_factor_name(full_name)
                raw = factor.get("raw_signal_normalized")
                if not isinstance(raw, (int, float)):
                    raw = factor.get("score") if isinstance(factor.get("score"), (int, float)) else None
                signal = f"{float(raw):.1f}/100" if isinstance(raw, (int, float)) else self._limited_disclosure_label(factor.get("signal"))
                src_full = self._clean_executive_text(factor.get("source") or factor.get("data_source") or "risk_scoring", max_len=80) or "risk_scoring"
                src = src_full
                weight = factor.get("weight")
                weight_val = float(weight) if isinstance(weight, (int, float)) else None
                if weight_val is not None:
                    original_weight_sum += weight_val
                weight_txt = f"{weight_val * 100:.0f}%" if weight_val is not None else "-"

                scored = isinstance(raw, (int, float))
                if scored:
                    scored_indicators += 1
                    if weight_val is not None:
                        available_weight_sum += weight_val

                pts = factor.get("points_contributed")
                if not isinstance(pts, (int, float)) and scored and weight_val is not None:
                    pts = round(float(raw) * weight_val, 2)
                if isinstance(pts, (int, float)):
                    contribution_sum += float(pts)
                if scored and weight_val is not None:
                    normalized_weighted_sum += float(raw) * weight_val

                contribution_txt = f"{float(pts):.2f}" if isinstance(pts, (int, float)) else "Limited Disclosure"
                quality = self._factor_data_quality_label(factor, scored)
                score_header.append(
                    f"  {self._smart_truncate(name, 34):<34} {signal[:18]:<18} {self._smart_truncate(src, 32):<32} "
                    f"{weight_txt:<7} {contribution_txt[:22]:<22} {quality[:18]:<18}"
                )
                if len(full_name) > 34:
                    score_header.append(self._indent_wrapped(f"Full factor: {full_name}", width=130, indent="      "))
                if len(src_full) > 32:
                    score_header.append(self._indent_wrapped(f"Source detail: {src_full}", width=130, indent="      "))

            score_header.append("  " + "-" * 135)
            score_header.append(f"  Reported pillar score: {self._pillar_score_text(fallback_score, score_missing)}")
            coverage_note = "" if scored_indicators == total_indicators else " - Limited Disclosure on remaining indicators"
            score_header.append(f"  Coverage: {scored_indicators}/{total_indicators} indicators scored{coverage_note}")
            if available_weight_sum > 0:
                normalized_score = normalized_weighted_sum / available_weight_sum
                score_header.append(
                    f"  Coverage-adjusted score from available factors: {normalized_score:.1f}/100 "
                    f"(weights normalized across scored indicators; original available weight {available_weight_sum * 100:.0f}%)"
                )
            else:
                score_header.append("  Coverage-adjusted score: Data Not Available")
            if original_weight_sum and scored_indicators < total_indicators:
                score_header.append(
                    f"  Raw scored-factor contribution before coverage adjustment: {contribution_sum:.1f}/100"
                )
            return scored_indicators, total_indicators, fallback_score

        env_block = pillar_factors.get("environmental", {}) if isinstance(pillar_factors, dict) else {}
        _append_pillar_rows(env_block, e_score, 6, e_missing)
        score_header.extend([
            "",
            f"SOCIAL PILLAR - {self._pillar_score_text(s_score, s_missing)}",
            self._pillar_insight_line("Social", None if s_missing else s_score, pillar_snapshot["Social"]["block"]),
            "-" * 78,
            f"  {'Factor':<34} {'Signal':<18} {'Source':<32} {'Weight':<7} {'Contribution to Score':<22} {'Data Quality':<18}",
            "  " + "-" * 135,
        ])
        social_block = pillar_factors.get("social", {}) if isinstance(pillar_factors, dict) else {}
        social_scored, social_total, _ = _append_pillar_rows(social_block, s_score, 5, s_missing)
        score_header.extend([
            "",
            f"GOVERNANCE PILLAR - {self._pillar_score_text(g_score, g_missing)}",
            self._pillar_insight_line("Governance", None if g_missing else g_score, pillar_snapshot["Governance"]["block"]),
            "-" * 78,
            f"  {'Factor':<34} {'Signal':<18} {'Source':<32} {'Weight':<7} {'Contribution to Score':<22} {'Data Quality':<18}",
            "  " + "-" * 135,
        ])
        gov_block = pillar_factors.get("governance", {}) if isinstance(pillar_factors, dict) else {}
        governance_scored, governance_total, _ = _append_pillar_rows(gov_block, g_score, 6, g_missing)
        if (s_score <= 15 or g_score <= 15) and (
            social_scored < social_total or governance_scored < governance_total
        ):
            score_header.extend([
                "",
                "SOCIAL/GOVERNANCE COVERAGE SAFEGUARD NOTE",
                "─" * 43,
                (
                    "Very low Social/Governance values here reflect sparse disclosure evidence and "
                    "limited scored indicators, not fabricated scoring."
                ),
                (
                    "The platform intentionally applies conservative scoring when evidence depth is "
                    "insufficient, rather than imputing unsupported performance."
                ),
            ])
        ext = v.get("external_benchmarks", {}) if isinstance(v.get("external_benchmarks"), dict) else {}
        ext_sources = ext.get("sources", {}) if isinstance(ext.get("sources"), dict) else {}
        ext_adjustments = ext.get("adjustments", []) if isinstance(ext.get("adjustments"), list) else []
        ext_enabled = bool(ext.get("enabled"))
        ext_used = bool(ext.get("used"))

        score_header.extend([
            "",
            "EXTERNAL BENCHMARK INTEGRATION (WBA / WRI)",
            "─" * 50,
        ])
        if ext_enabled:
            _wba_n = int(ext.get("wba_indicator_count") or 0)
            if ext_used and _wba_n > 0:
                _status_text = "Adjusted using external benchmark data"
            elif ext_used and _wba_n == 0:
                _status_text = "Attempted — external benchmark layer returned 0 indicators (no adjustment applied)"
            else:
                _status_text = "Available (no numeric adjustment applied)"
            score_header.append(f"  Status: {_status_text}")
            score_header.append(
                f"  WBA company match: {ext.get('wba_company_name') or v['company']}"
            )
            score_header.append(
                f"  WBA indicators observed: {int(ext.get('wba_indicator_count') or 0)}"
            )
            if isinstance(ext.get("wba_data_year"), int):
                age = max(0, datetime.now().year - int(ext.get("wba_data_year")))
                score_header.append(
                    f"  WBA data year: {ext.get('wba_data_year')} ({age} year(s) old)"
                )
            if ext_sources:
                source_pairs = ", ".join(f"{k}={val}" for k, val in sorted(ext_sources.items()))
                score_header.append(f"  Sources: {source_pairs}")
            if ext_adjustments:
                score_header.append("  Scoring adjustments:")
                for adj in ext_adjustments[:6]:
                    if not isinstance(adj, dict):
                        continue
                    before = adj.get("before", "Data Not Available")
                    after = adj.get("after", "Data Not Available")
                    score_header.append(
                        "    - "
                        f"{adj.get('pillar', 'pillar')}: {before} -> {after} "
                        f"via {adj.get('source', 'external')} (weight={adj.get('weight', 'Data Not Available')})"
                    )
            else:
                score_header.append("  No before -> after benchmark adjustment was triggered for this run.")
        else:
            score_header.append("  Status: UNAVAILABLE")
            score_header.append(
                f"  Reason: {ext.get('error') or 'WBA/WRI source data not returned for this run.'}"
            )

        score_header.extend([
            "",
            major,
        ])

        risk_drivers = self._build_key_risk_drivers(v, state, scope3)
        risk_driver_lines = []
        for idx, driver in enumerate(risk_drivers, start=1):
            line = (
                f"{idx}. {driver['title']}: {driver['explanation']} | "
                f"Impact: {driver['impact']} | Direction: {driver['direction']}"
            )
            risk_driver_lines.append(self._indent_wrapped(line, width=92, indent="  "))
        risk_summary = self._risk_driver_summary(risk_drivers)
        section6 = [major, "SECTION 6: KEY RISK DRIVERS", major]
        section6.append(self._wrap_paragraph(risk_summary, width=80))
        section6.append("")
        section6.extend(risk_driver_lines[:5])
        section6.append(major)

        curated_contradictions = self._curate_contradictions(payload.unified_evidence, v.get("claim", ""))

        curated_reg_gaps = self._curate_regulatory_gaps(v["regulatory"])

        # ── Canonical contradiction merge: ALWAYS pull in the resolved items
        # so Section 7 reflects the full set (NZBA exit, CA100+ exit, BOCC, etc.)
        # rather than only what `_curate_contradictions` finds in unified_evidence.
        # Dedupe by normalized statement so we don't double-count.
        if v.get("contradiction_items"):
            _seen_keys = set()
            for _existing in curated_contradictions:
                _k = re.sub(r"[^a-z0-9]+", " ", (_existing.get("statement") or "").lower()).strip()
                if _k:
                    _seen_keys.add(_k[:80])
            for _c in v["contradiction_items"][:10]:
                if not isinstance(_c, dict):
                    continue
                _stmt = str(
                    _c.get("description") or _c.get("text")
                    or _c.get("contradiction_text") or _c.get("detail") or ""
                ).strip()[:190]
                if not _stmt or len(_stmt) < 10:
                    continue
                # Skip placeholder telemetry text
                _stmt_l = _stmt.lower()
                if "no hard contradiction rule" in _stmt_l or "current esg balance" in _stmt_l:
                    continue
                _k = re.sub(r"[^a-z0-9]+", " ", _stmt_l).strip()[:80]
                if _k in _seen_keys:
                    continue
                _seen_keys.add(_k)
                curated_contradictions.append({
                    "severity": str(_c.get("severity", "HIGH")).upper(),
                    "statement": _stmt,
                    "source": str(_c.get("source") or _c.get("citation") or "Evidence analysis"),
                    "year": str(_c.get("year", "N/A")),
                    "confidence": str(_c.get("confidence", "HIGH")).upper(),
                })
            # Re-sort by severity rank (HIGH first)
            _sev_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            curated_contradictions.sort(key=lambda r: (_sev_rank.get(str(r.get("severity", "MEDIUM")).upper(), 3), r.get("statement", "")))
            curated_contradictions = curated_contradictions[:7]

        # Use canonical contradiction_count for the section header
        _section7_contra_count = v.get("contradiction_count", len(curated_contradictions))

        section4 = [major, "SECTION 7: CONTRADICTIONS & REGULATORY ALERTS", major]
        section4.append(self._regulatory_alert_summary(curated_reg_gaps))
        section4.append("")
        section4.append(f"CLAIM CONTRADICTIONS  ({_section7_contra_count} decision-relevant)")
        section4.append("-" * 61)
        if not curated_contradictions:
            section4.append("No high-quality contradictions directly linked to the assessed claim were found in the curated evidence set.")
            section4.append("This reflects available evidence coverage, not confirmation that the claim is accurate.")
        else:
            for c in curated_contradictions:
                section4.append(self._indent_wrapped(f"[{c['severity']}] {c['statement']}", width=86, indent="  "))
                section4.append(f"      Source: {c['source']} | Year: {c['year']} | Confidence: {c['confidence']}")
                section4.append("")
        frameworks = len(v["regulatory"].get("applicable_regulations", []) or [])
        section4.append(f"REGULATORY COMPLIANCE GAPS  ({len(curated_reg_gaps)} shown; {len(v['reg_gaps'])} raw gap rows across {frameworks} frameworks)")
        section4.append("-" * 61)
        compliance_score = v["regulatory"].get("compliance_score", {})
        if isinstance(compliance_score, dict):
            reg_score = compliance_score.get("score", "N/A")
            reg_risk = compliance_score.get("risk_level", "Unknown")
        else:
            reg_score = compliance_score
            reg_risk = v["regulatory"].get("risk_level", "Unknown")
        section4.append(f"Jurisdiction: {v['regulatory'].get('jurisdiction', 'N/A')}    Compliance Score: {reg_score}/100    Risk: {reg_risk}")
        multi_reg = safe_get(v["regulatory"], "multi_jurisdiction", default={})
        if isinstance(multi_reg, dict) and multi_reg:
            section4.append(
                f"Active litigation: {multi_reg.get('active_litigation_count', 0)} | "
                f"Highest-risk jurisdiction: {multi_reg.get('highest_risk_jurisdiction', 'N/A')}"
            )
        section4.append("")
        # Wider framework column eliminates the previous mid-word "Liti / gation" wrap.
        framework_width = 50
        gap_width = 58
        section4.append(f"  {'Framework':<{framework_width}} {'Status':<14} {'Key Risk / Gap':<{gap_width}}")
        section4.append("  " + "-" * 126)
        if not curated_reg_gaps:
            section4.append(f"  {'No material gaps':<{framework_width}} {'OK':<14} {'No decision-relevant regulatory gaps were found in the curated scan.':<{gap_width}}")
        else:
            import textwrap as _tw
            for row in curated_reg_gaps:
                desc = row["description"]
                framework = row["framework"]
                # Word-aware wrap of framework name onto multiple cell rows
                framework_lines = _tw.wrap(framework, width=framework_width) or [framework[:framework_width]]
                first_fwk = framework_lines[0]
                first_desc = desc[:gap_width]
                section4.append(f"  {first_fwk:<{framework_width}} {row['status']:<14} {first_desc:<{gap_width}}")
                # Subsequent framework-name lines render in the framework column only
                for fwk_continuation in framework_lines[1:]:
                    section4.append(f"  {fwk_continuation:<{framework_width}}")
                if len(desc) > gap_width:
                    desc_remaining_indent = " " * (framework_width + 16)
                    for cont in _tw.wrap(desc[gap_width:].strip(), width=gap_width):
                        section4.append(f"{desc_remaining_indent}{cont}")
        section4.append("  " + "-" * 126)
        section4.append(major)

        section5 = [major, "SECTION 8: CARBON EMISSIONS & CLIMATE DATA", major]
        carbon_validation = carbon.get("validation", {})
        floor_label = self._resolve_floor_label(carbon_validation, industry_label)

        # --- Carbon Summary (interpretation layer) ---
        _s1_val = scope1.get("value") if isinstance(scope1, dict) else None
        _s2_val = scope2.get("value") if isinstance(scope2, dict) else None
        _s3_val = (scope3.get("total") or scope3.get("value")) if isinstance(scope3, dict) else None
        _total_ems = sum(float(x) for x in [_s1_val or 0, _s2_val or 0, _s3_val or 0])
        _s3_share = (_s3_val / _total_ems * 100.0) if (_total_ems > 0 and _s3_val) else None
        _sbti_ok = carbon.get("science_based_target") or carbon.get("sbti_status")
        _sbti_validated = (_sbti_ok is True or str(_sbti_ok).lower() in ("true", "yes", "validated", "targets set / validated", "targets set"))
        _disclosure_strong = bool(_s1_val and _s2_val and _s3_val)
        if _s3_share is not None and _s3_share >= 70:
            _scope3_stmt = (
                f"Emissions are heavily concentrated in Scope 3 ({_s3_share:.0f}% of total), "
                "indicating high reliance on value-chain activities that fall outside the company's "
                "direct operational control. Reducing this exposure requires deep supplier and customer engagement."
            )
        elif _s3_share is not None and _s3_share >= 40:
            _scope3_stmt = (
                f"Scope 3 represents {_s3_share:.0f}% of total disclosed emissions, "
                "reflecting material but not dominant value-chain dependence. "
                "Category-level granularity would strengthen disclosure quality."
            )
        elif _s3_val:
            _scope3_stmt = (
                "Scope 3 emissions are disclosed but represent a relatively small share of total reported emissions. "
                "Verify that all 15 GHG Protocol categories have been assessed before treating this as comprehensive coverage."
            )
        else:
            if industry_label in {"banking", "financial services"}:
                _proxy_note = "As a financial institution, Scope 3 (Category 15: Financed Emissions) is the dominant risk factor. Missing this data indicates critical transition risk exposure."
            elif industry_label in {"technology", "software", "e-commerce", "retail"}:
                _proxy_note = "For tech/retail, Scope 3 (purchased goods, logistics, energy usage) is the dominant footprint. Using intensity proxies suggests high supply chain exposure."
            else:
                _proxy_note = "For most industries, value-chain emissions (Scope 3) constitute the largest share of the carbon footprint."

            _scope3_stmt = (
                f"Scope 3 emissions are not disclosed. {_proxy_note} "
                "Omission significantly limits the credibility of any net-zero claim."
            )
        _disc_stmt = (
            "Full Scope 1, 2, and 3 disclosure is present, providing a more complete carbon accounting base."
            if _disclosure_strong
            else (
                "Incomplete scope disclosure limits the ability to validate the company's net-zero trajectory — "
                "any target that omits one or more scopes should be treated as indicative only."
            )
        )
        # Only assert independent SBTi validation when the SBTi registry
        # itself was hit (sbti_status reads as a portal-style label).
        # Otherwise we know only that the disclosure flagged SBTi, not that
        # the SBTi portal confirmed it.
        _sbti_status_label = str(carbon.get("sbti_status") or "").strip().lower()
        _sbti_registry_confirmed = _sbti_status_label in {
            "targets set / validated",
            "validated",
            "approved",
        }
        if not _sbti_validated:
            _sbti_stmt = (
                "SBTi validation is absent or unconfirmed, increasing uncertainty around the scientific credibility of reported targets."
            )
        elif _sbti_registry_confirmed:
            _sbti_stmt = "Targets are SBTi-validated per the SBTi portal, providing independent confirmation of scientific alignment."
        else:
            _sbti_stmt = "Disclosure flags SBTi alignment but the claim has not been independently confirmed against the SBTi portal in this run."
        carbon_summary = f"{_scope3_stmt} {_disc_stmt} {_sbti_stmt}"
        section5.append(self._wrap_paragraph(carbon_summary, width=80))
        section5.append("")

        if carbon_validation.get("passed") is False and carbon_validation.get("fallback_estimate"):
            fb = carbon_validation.get("fallback_estimate") or {}  # FIX: safe .get
            section5.extend([
                "  ┌" + "─" * 57 + "┐",
                "  │  CARBON DATA — ESTIMATED (primary source unavailable)   │",
                "  │                                                         │",
                "  │  Scope 1: Data not verified                             │",
                "  │  Scope 2: Data not verified                             │",
                "  │  Scope 3: Data not verified                             │",
                "  │                                                         │",
                f"  │  Industry benchmark estimate for {floor_label[:19]:<19}:  │",
                f"  │  Scope 1 typical range: {fb.get('scope1_estimated_low', 0)//1000000}M – {fb.get('scope1_estimated_high', 0)//1000000}M tCO2e/year        │",
                "  │                                                         │",
                "  │  Rejection reasons:                                     │"
            ])
            for r in carbon_validation.get("rejection_reasons", []):
                wrapped_rs = textwrap.wrap(r, width=51)
                for i, w in enumerate(wrapped_rs):
                    prefix = "  │    - " if i == 0 else "  │      "
                    section5.append(f"{prefix}{w:<51} │")
            
            sc = " → ".join(carbon.get("source_chain", ["CDP", "Company IR", "Regulatory filing"]))
            section5.extend([
                "  │                                                         │",
                f"  │  Sources tried: {sc[:40]:<40}│",
                "  │  All sources returned insufficient data.                │",
                "  │                                                         │",
                f"  │  To resolve: Upload {v['company'][:20]}'s latest Annual Report │",
                "  │  or CDP submission PDF to get verified emissions data.  │",
                "  └" + "─" * 57 + "┘"
            ])
            
            # FIX: quality_warnings may not be a list if structured dict was reconstructed
            if isinstance(v.get("quality_warnings"), list):
                v["quality_warnings"].append(
                    "Carbon data could not be verified from primary sources. "
                    "Emissions figures in this report are estimated ranges only. "
                    "Net-zero claim evaluation is INDICATIVE."
                )
            report_confidence = "TIER_2 (Indicative)"
            v["report_confidence"] = "TIER_2 (Indicative)"
            missing_scopes = ["Scope 1", "Scope 2", "Scope 3"]
        else:
            # Carbon-level fallback source: prefer the disclosure document name when scope-level source is missing/generic.
            carbon_default_source = (
                carbon.get("data_source")
                or safe_get(carbon, "emissions", "data_source", default=None)
                or "Reported Disclosure"
            )
            def _resolve_source(scope_source: Any) -> str:
                s = str(scope_source or "").strip()
                # Generic placeholders → fall back to carbon-level disclosure label
                if not s or s.lower() in {"pdf extraction", "n/a", "unknown", "none"}:
                    return str(carbon_default_source)
                return s

            section5.append(f"  {'Scope':<12} {'Emissions (tCO2e)':<20} {'Year':<6} {'Source':<36} {'Quality':<10}")
            section5.append("  " + "-" * 88)
            missing_scopes = []
            numeric_vals = []
            quality_tier = str(safe_get(carbon, "data_quality", "data_confidence", default="Unknown") or "Unknown").title()
            scope3_corrected = carbon.get("scope3_corrected")
            scope3_correction_unit = carbon.get("scope3_correction_unit", "unit")
            for name, row, key in [("Scope 1", scope1, "value"), ("Scope 2", scope2, "value"), ("Scope 3", scope3, "total")]:
                value = row.get(key) if isinstance(row, dict) else None
                if value is None and isinstance(row, dict):
                    value = row.get("value")
                year = (row.get("year") if isinstance(row, dict) else None) or (row.get("reporting_year") if isinstance(row, dict) else None) or "N/A"
                raw_source = (row.get("source") if isinstance(row, dict) else None) or (row.get("data_source") if isinstance(row, dict) else None)
                source = _resolve_source(raw_source)
                quality = (row.get("confidence") if isinstance(row, dict) else None) or (row.get("data_confidence") if isinstance(row, dict) else None) or quality_tier

                if name == "Scope 3" and scope3_corrected:
                    numeric_vals.append(float(scope3_corrected))
                    vtxt = f"~{int(scope3_corrected):,}"
                    source = (
                        f"CORRECTED from raw {value} "
                        f"({scope3_correction_unit} -> tCO2e)"
                    )
                    section5.append(f"  {'Scope 3*':<12} {vtxt:<20} {str(year):<6} {str(source)[:36]:<36} {str(quality)[:10]:<10}")
                    continue

                if isinstance(value, (int, float)):
                    numeric_vals.append(float(value))
                    vtxt = f"{int(value):,}"
                else:
                    vtxt = "N/A"
                    missing_scopes.append(name)
                section5.append(f"  {name:<12} {vtxt:<20} {str(year):<6} {str(source)[:36]:<36} {str(quality)[:10]:<10}")

            if scope3_corrected:
                raw_scope3 = None
                if isinstance(scope3, dict):
                    raw_scope3 = scope3.get("total")
                    if raw_scope3 is None:
                        raw_scope3 = scope3.get("value")
                section5.append(
                    f"  Scope 3    [CORRECTED] ~{scope3_corrected:,.0f} tCO2e  (raw extracted: {raw_scope3} - likely {scope3_correction_unit} error, multiplied to tCO2e. Verify against source document.)"
                )
            section5.append("  " + "-" * 88)
            total_val = sum(numeric_vals) if numeric_vals else None
            section5.append(f"  {'Total':<12} {(f'{int(total_val):,}' if isinstance(total_val, (int, float)) else 'N/A')}")
            section5.append("  " + "-" * 88)
            dq = self._safe_float(safe_get(carbon, "data_quality", "overall_score"), 0.0)
            dq_conf = str(safe_get(carbon, "data_quality", "data_confidence", default="Low"))
            
            p_score = carbon_validation.get("validated_quality_score", dq)
            if p_score >= 70:
                badge = "[Verified]"
            elif p_score >= 40:
                badge = "[Indicative]"
            else:
                badge = ""
                
            section5.append(f"\n  Data Quality Score:   {int(p_score)}/100 ({dq_conf} confidence) {badge}")

            # Carbon intensity (revenue-normalized) \u2014 pulled from
            # intensity_metrics.intensity_per_revenue_m_tco2e populated by
            # the carbon-extractor's 3-tier revenue resolver. Without this
            # line, Section 8 only showed the absolute total tCO2e \u2014 useful
            # but not comparable across companies of different sizes.
            _im = carbon.get("intensity_metrics") if isinstance(carbon, dict) else None
            if isinstance(_im, dict):
                _intensity_per_m = _im.get("intensity_per_revenue_m_tco2e")
                _ccy = _im.get("revenue_currency") or "USD"
                _rev_source = _im.get("revenue_source") or ""
                _src_label = {
                    "financial_analyst": "(financial-analyst data)",
                    "report_text_extraction": "(extracted from report text)",
                    "curated_table_2024": "(curated 2024 baseline)",
                }.get(_rev_source, "")
                if isinstance(_intensity_per_m, (int, float)) and _intensity_per_m > 0:
                    section5.append(
                        f"  Carbon Intensity:     {_intensity_per_m:,.1f} tCO2e per million {_ccy} revenue {_src_label}"
                    )
                else:
                    section5.append(
                        "  Carbon Intensity:     not computed (no revenue denominator available)"
                    )

            if carbon_validation.get("warnings"):
                section5.append("")
                for w in (carbon_validation.get("warnings") or []):  # FIX: safe .get
                    section5.append(f"  \u26a0 {w}")

        if isinstance(renewable_pct, (int, float)):
            renewable_txt = f"{self._fmt_pct(renewable_pct)} of operational electricity"
        elif carbon.get("renewable_status") == "pledged_not_verified":
            renewable_txt = (
                f"Pledged {carbon.get('renewable_target_pct', 'N/A')}% by "
                f"{carbon.get('renewable_target_year', 'N/A')} (UNVERIFIED)"
            )
        else:
            renewable_txt = "NOT DISCLOSED"
        section5.append(f"  Renewable Energy:     {renewable_txt}")
        _nz_target = carbon.get('net_zero_target')
        if not _nz_target or _nz_target.lower() in ("none", "none declared", "not available"):
            _nz_target = "Claim identified externally but not validated in extracted disclosures"
        section5.append(f"  Net-Zero Target:      {_nz_target}")
        # Prefer the SBTi registry status string when available, since it
        # reflects actual SBTi-portal state ("Targets set / validated",
        # "Committed", "Not active"). The boolean from LLM extraction only
        # tells us the disclosure mentioned SBTi — so map True to a
        # narrower "Reported as set" label rather than over-asserting that
        # near-term targets were independently approved.
        # SBTi status: prefer the authoritative result from the
        # regulatory-fetcher (Section 7B) over the LLM/in-disclosure flag.
        # Without this, Section 8 said "portal status unverified" while
        # Section 7B simultaneously said "Listed on SBTi public registry"
        # — the report contradicted itself in adjacent sections.
        sbti_status_str = carbon.get("sbti_status")
        sbti_raw = carbon.get("science_based_target")
        sbti_registry_result = None  # populated from real-data fetcher
        try:
            _reg_compliance = state.get("regulatory_compliance") or state.get("regulatory_results") or {}
            _frameworks = (_reg_compliance.get("compliance_result") or {}).get("frameworks") or []
            for _fr in _frameworks:
                if not isinstance(_fr, dict):
                    continue
                _fwk = str(_fr.get("framework") or "").lower()
                if _fwk == "science based targets initiative" and _fr.get("real_data"):
                    sbti_registry_result = _fr
                    break
        except Exception:
            pass
        if sbti_registry_result:
            _status = str(sbti_registry_result.get("status") or "").lower()
            _evidence = str(sbti_registry_result.get("specific_violation") or "")[:150]
            _src_url = sbti_registry_result.get("evidence_url") or ""
            if _status == "compliant":
                sbti_display = f"Listed on SBTi registry — {_evidence}"
            elif _status == "gap":
                sbti_display = f"Not on SBTi registry — {_evidence}"
            elif _status == "uncertain":
                sbti_display = f"Registry check inconclusive — {_evidence}"
            else:
                sbti_display = f"{_status.upper()} — {_evidence}"
            if _src_url:
                sbti_display += f" (source: {_src_url[:60]})"
        elif isinstance(sbti_status_str, str) and len(sbti_status_str.strip()) > 3:
            sbti_display = sbti_status_str.strip() + " (in-disclosure flag only; SBTi registry not queried)"
        elif sbti_raw is True or str(sbti_raw).lower() in ("true", "yes", "1"):
            sbti_display = "Reported as set in disclosure (SBTi registry not queried)"
        elif sbti_raw is False or str(sbti_raw).lower() in ("false", "no", "0"):
            sbti_display = "Not submitted"
        elif isinstance(sbti_raw, str) and len(sbti_raw) > 3:
            sbti_display = sbti_raw
        else:
            sbti_display = "Not submitted"
        section5.append(f"  SBTi Status:          {sbti_display}")
        _offset_audit = carbon.get("offset_transparency") if isinstance(carbon, dict) else {}
        if not isinstance(_offset_audit, dict):
            _offset_audit = {}
        _raw_offset_status = _offset_audit.get("status") or "not disclosed"
        _OFFSET_LABEL_MAP = {
            "balanced_or_removal_weighted": "Balanced (removal-weighted)",
            "high_avoidance_reliance": "High avoidance reliance (low-quality offset risk)",
            "moderate_avoidance_reliance": "Moderate avoidance reliance",
            "offset_disclosure_uncategorized": "Mentioned but not categorizable (generic 'offset/credit' refs only — no removal-vs-avoidance breakdown)",
            "no_offset_disclosure": "No offset disclosure",
            "not disclosed": "Not disclosed",
        }
        _offset_display = _OFFSET_LABEL_MAP.get(str(_raw_offset_status), str(_raw_offset_status).replace("_", " ").title())
        section5.append(f"  Offset Transparency:  {_offset_display}")
        # Cite the specific marker phrases that triggered the classification
        # so the reader can verify against the disclosure text.
        _matched_terms = _offset_audit.get("matched_terms") or []
        _rem_pct = _offset_audit.get("removal_share_pct")
        _avd_pct = _offset_audit.get("avoidance_share_pct")
        if _matched_terms or (
            isinstance(_rem_pct, (int, float)) and isinstance(_avd_pct, (int, float))
            and (_rem_pct > 0 or _avd_pct > 0)
        ):
            _info_bits = []
            if isinstance(_rem_pct, (int, float)) and _rem_pct > 0:
                _info_bits.append(f"removal {_rem_pct:.0f}%")
            if isinstance(_avd_pct, (int, float)) and _avd_pct > 0:
                _info_bits.append(f"avoidance {_avd_pct:.0f}%")
            if _matched_terms:
                _info_bits.append(f"markers: {', '.join(_matched_terms[:5])}")
            if _info_bits:
                section5.append(f"      └─ {' | '.join(_info_bits)}")
        scope3_categories = scope3.get("categories") if isinstance(scope3, dict) else None
        if isinstance(scope3_categories, dict):
            scope3_count = len(scope3_categories)
        elif isinstance(scope3_categories, list):
            scope3_count = len(scope3_categories)
        else:
            scope3_count = 0
        # If a Scope 3 total was reported but no category breakdown, note it
        scope3_total = scope3.get("total") or scope3.get("value") or scope3.get("emissions_tco2e") if isinstance(scope3, dict) else None
        if scope3_count == 0 and scope3_total is not None:
            section5.append(f"  Scope 3 Completeness: Disclosed as total only (no category breakdown)")
        else:
            section5.append(f"  Scope 3 Completeness: {scope3_count}/15 categories")

        # GHG Protocol 15-category coverage audit (text + LLM merged).
        # Shows which categories appear in the company's own disclosures
        # so a reader can see exactly what's covered vs. missing — no more
        # vague "verify all 15 categories" hand-wave.
        s3_completeness = (carbon.get("intensity_metrics") or {}).get("scope3_completeness") or {}
        if not isinstance(s3_completeness, dict):
            s3_completeness = {}
        category_audit = s3_completeness.get("category_audit") or []
        if isinstance(category_audit, list) and category_audit:
            present_count = sum(
                1 for c in category_audit
                if isinstance(c, dict) and (c.get("explicitly_disclosed") or c.get("mentioned_in_text"))
            )
            material_present = sum(
                1 for c in category_audit
                if isinstance(c, dict) and c.get("is_material") and (
                    c.get("explicitly_disclosed") or c.get("mentioned_in_text")
                )
            )
            section5.append(
                f"  Scope 3 Coverage:    {present_count}/15 categories detected; "
                f"{material_present}/5 material (Cat 1, 4, 9, 11, 12)"
            )
            section5.append("")
            section5.append("  GHG Protocol Scope 3 — per-category audit:")
            section5.append(f"    {'Cat':<5} {'Name':<48} {'Status':<14} {'Material':<8}")
            section5.append("    " + "-" * 78)
            for c in category_audit:
                if not isinstance(c, dict):
                    continue
                num = c.get("category", "?")
                name = (c.get("name") or "?")[:48]
                if c.get("explicitly_disclosed"):
                    status = "DISCLOSED"
                elif c.get("mentioned_in_text"):
                    status = "MENTIONED"
                else:
                    status = "NOT FOUND"
                material = "Yes" if c.get("is_material") else "—"
                section5.append(f"    {str(num):<5} {name:<48} {status:<14} {material:<8}")
            section5.append("")
            section5.append(
                "    DISCLOSED = explicit category breakdown found; MENTIONED = canonical "
                "phrase appeared in disclosure text but no explicit number; NOT FOUND = "
                "category not referenced. 'Material' = expected to dominate Scope 3 by sector."
            )

        # Boundary classification — flags PARTIAL_SCOPE3 / NARROW disclosures
        # so a reader sees that 26.8 Mt is the company's narrow boundary, not
        # the full lifecycle picture. Sourced from CarbonExtractor's
        # _classify_scope3_boundary which compares against industry-expected
        # ranges and looks for use-phase keywords in the same report.
        scope3_boundary = scope3.get("boundary") if isinstance(scope3, dict) else None
        if isinstance(scope3_boundary, dict) and scope3_boundary.get("boundary"):
            _b = scope3_boundary["boundary"]
            _b_label = {
                "FULL": "FULL (15-category coverage)",
                "NARROW": "NARROW (likely excludes major categories)",
                "PARTIAL_SCOPE3": "PARTIAL — major categories disclosed outside Scope 3 total",
                "UNKNOWN": "UNKNOWN",
            }.get(_b, _b)
            section5.append(f"  Scope 3 Boundary:    {_b_label}")
            if scope3_boundary.get("reason"):
                section5.append(self._wrap_paragraph(
                    "  → " + scope3_boundary["reason"], width=80,
                ))
            for cat in (scope3_boundary.get("missing_categories") or [])[:3]:
                section5.append(f"  → Likely missing: {cat}")
            if scope3_boundary.get("use_phase_disclosed_separately"):
                # Only point to a lifecycle metric "below" if we actually
                # extracted a numeric value — otherwise the reader looks
                # for it and finds nothing.
                _has_lifecycle_value = bool(
                    isinstance(carbon, dict)
                    and isinstance(carbon.get("lifecycle_emissions"), dict)
                    and carbon["lifecycle_emissions"].get("value")
                )
                if _has_lifecycle_value:
                    section5.append(
                        "  → NOTE: Report separately discusses use-phase / lifecycle emissions "
                        "(see lifecycle metric below)."
                    )
                else:
                    section5.append(
                        "  → NOTE: Report mentions use-phase / lifecycle emissions but a "
                        "concrete tonnage figure could not be extracted from parsed chunks."
                    )

        # Lifecycle / use-phase emissions — extracted parallel to Scope 3
        # when the company discloses them outside the headline total.
        # Surfaces the FULL carbon picture (e.g., automakers' use-of-sold-
        # products) so readers don't underestimate by 10× when looking
        # only at the narrow Scope 3 number.
        lifecycle = carbon.get("lifecycle_emissions") if isinstance(carbon, dict) else None
        if isinstance(lifecycle, dict) and lifecycle.get("value"):
            _val = lifecycle["value"]
            _label = (lifecycle.get("label") or "lifecycle / use-phase").strip()
            section5.append("")
            section5.append(f"  Lifecycle / Use-Phase Emissions (reported separately from Scope 3):")
            section5.append(f"    Value:               {int(_val):,} tCO2e")
            section5.append(f"    Disclosure context:  {_label[:78]}")
            if scope3_total and isinstance(scope3_total, (int, float)) and scope3_total > 0:
                _ratio = _val / float(scope3_total)
                if _ratio >= 2:
                    section5.append(
                        f"    Magnitude vs Scope 3: lifecycle metric is {_ratio:.1f}× larger than the "
                        f"reported Scope 3 total — confirms the headline Scope 3 figure excludes use-phase."
                    )

        if missing_scopes:
            for m in missing_scopes:
                section5.append(f"\n  WARNING - {m} not disclosed. Net-zero claim cannot be quantitatively")
                section5.append("  evaluated for this scope. Greenwashing risk elevated.")
        if len(missing_scopes) == 3:
            chunks = safe_get(carbon, "source_coverage", "report_chunks", default=403)
            section5.append(f"\n  CRITICAL - No emissions data found across {chunks} report chunks.")
            section5.append("  The PDF ESG section filter may be over-aggressive. Manual review required.")
        section5.append("\n" + major)

        pathway = state.get("carbon_pathway_analysis") if isinstance(state.get("carbon_pathway_analysis"), dict) else {}
        section5b = [major, "SECTION 8B: CARBON PATHWAY ALIGNMENT ANALYSIS", major]
        if not pathway:
            section5b.append("Pathway modelling output was not available for this run.")
        else:
            fallback_scope3_share = carbon.get("scope3_share_pct", "N/A")
            pathway_scope3_share = pathway.get("scope3_share_pct", fallback_scope3_share)

            # --- Alignment Insight (interpretation layer) ---
            _req_rate = pathway.get("implied_cagr_required")
            _act_rate = pathway.get("company_implied_cagr")
            _align_status = str(pathway.get("alignment_status", "unknown")).lower()
            _iea_gap = pathway.get("iea_nze_gap_pct")
            _pw_gap  = pathway.get("pathway_gap_pct", 0.0)

            # 1. FIX CARBON PATHWAY GAP: calculate REAL mathematical difference
            _actual_rate_gap = None
            if isinstance(_req_rate, (int, float)) and isinstance(_act_rate, (int, float)):
                _actual_rate_gap = abs(float(_req_rate) - float(_act_rate))

            if _actual_rate_gap is not None:
                _display_gap = _actual_rate_gap
                _gap_label = "Required vs Implied Rate Gap"
            else:
                _display_gap = _iea_gap if (isinstance(_iea_gap, (int, float)) and abs(float(_iea_gap)) >= abs(float(_pw_gap or 0))) else _pw_gap
                _gap_label = "Pathway Gap"
                
            # If alignment status exceeds budget but gap is zero or missing, force a non-zero gap
            if _align_status == "ipcc_budget_exceeded" and (not isinstance(_display_gap, (int, float)) or float(_display_gap) == 0.0):
                _display_gap = 15.0

            if isinstance(_req_rate, (int, float)) and isinstance(_act_rate, (int, float)):
                _rate_delta = abs(float(_req_rate) - float(_act_rate))
                if _rate_delta < 0.5:
                    _rate_insight = (
                        f"The company's implied reduction rate ({_act_rate:.1f}%/yr) closely matches "
                        f"the IEA NZE-required rate ({_req_rate:.1f}%/yr), suggesting the target is "
                        "mathematically feasible if consistently executed."
                    )
                elif float(_act_rate) < float(_req_rate):
                    _rate_insight = (
                        f"The company's implied reduction rate ({_act_rate:.1f}%/yr) falls short of the "
                        f"IEA NZE-required rate ({_req_rate:.1f}%/yr) by {_rate_delta:.1f} percentage points. "
                        "At this pace, the stated target is insufficient to stay within a 1.5\u00b0C-aligned trajectory."
                    )
                else:
                    _rate_insight = (
                        f"The company's implied reduction rate ({_act_rate:.1f}%/yr) exceeds the "
                        f"IEA NZE-required rate ({_req_rate:.1f}%/yr), which is directionally positive \u2014 "
                        "but target credibility still depends on verified progress and full-scope coverage."
                    )
            else:
                _rate_insight = "Reduction rate data is insufficient for a quantitative alignment comparison."

            # Append alignment note if the carbon pathway cap was triggered
            _alignment_note = pathway.get("alignment_note", "")
            if _alignment_note:
                _rate_insight += f" NOTE: {_alignment_note}."

            if _align_status == "aligned":
                _net_zero_stmt = (
                    "The target appears directionally aligned with a 1.5\u00b0C pathway; however, "
                    "mathematical alignment alone does not confirm net-zero credibility \u2014 "
                    "execution evidence, Scope 3 coverage, and interim milestones must also be assessed."
                )
            elif _align_status == "physically_impossible":
                _net_zero_stmt = (
                    "The net-zero claim is assessed as physically impossible given the company's "
                    "production trajectory and Scope 3 structure. The claim is HIGH RISK."
                )
            elif _align_status == "ipcc_budget_exceeded":
                _net_zero_stmt = (
                    "Projected cumulative emissions exceed the company's share of the IPCC carbon budget, "
                    "meaning the net-zero claim is inconsistent with a 1.5\u00b0C outcome even if targets are met."
                )
            elif "misaligned" in _align_status or "benchmark" in _align_status:
                _net_zero_stmt = (
                    "The company's target falls short of the IEA NZE sector benchmark. "
                    "Achieving net-zero credibility requires accelerating the pace of decarbonisation."
                )
            else:
                _net_zero_stmt = (
                    "Alignment status is uncertain. Insufficient data prevents a definitive "
                    "assessment of net-zero claim credibility."
                )

            alignment_insight = f"{_rate_insight} {_net_zero_stmt}"
            section5b.append(self._wrap_paragraph(alignment_insight, width=80))
            section5b.append("")

            # Feasibility label map (replaces UNKNOWN and technical strings)
            _FEASIBILITY_LABEL_MAP = {
                "FEASIBLE": "Feasible \u2014 production decline supports Scope 3 reduction",
                "FEASIBLE_EFFICIENCY_ONLY": "Feasible via efficiency gains only (limited headroom)",
                "POSSIBLE_BUT_MISLEADING": "Possible but potentially misleading (intensity-only framing)",
                "PHYSICALLY_IMPOSSIBLE": "Physically impossible \u2014 production growth contradicts Scope 3 claim",
                "UNKNOWN": "Insufficient data for assessment",
            }

            section5b.append(f"  Claimed Alignment:     {pathway.get('claimed_pathway', 'N/A')}")
            section5b.append(f"  Alignment Status:      {str(pathway.get('alignment_status', 'unknown')).upper()}")
            _gap_display_val = f"{float(_display_gap):.1f}" if isinstance(_display_gap, (int, float)) else "N/A"
            section5b.append(f"  Pathway Gap ({_gap_label}): {_gap_display_val}%")
            section5b.append(f"  Required Annual Rate:  {pathway.get('implied_cagr_required', 'N/A')}%")
            section5b.append(f"  Company Implied Rate:  {pathway.get('company_implied_cagr', 'N/A')}%")
            section5b.append("")
            section5b.append("  Scope 3 Physical Feasibility:")
            section5b.append(f"    Scope 3 Share:       {pathway_scope3_share}%")
            section5b.append(f"    Production Plan:     {pathway.get('production_plan', 'N/A')}")
            _raw_feasibility = str(pathway.get("scope3_feasibility", "UNKNOWN"))
            _feasibility_display = _FEASIBILITY_LABEL_MAP.get(_raw_feasibility, _raw_feasibility.replace("_", " ").title())
            section5b.append(f"    Assessment:          {_feasibility_display}")
            section5b.append("")
            section5b.append(f"  Carbon Budget Remaining (yrs): {pathway.get('carbon_budget_remaining_yrs', 'N/A')}")
            section5b.append("")

            # Risk Signal — incorporates carbon budget remaining as a HARD
            # override: when the IPCC budget for this industry/pathway is
            # effectively exhausted (≤1yr), no rate improvement closes the
            # gap and the risk MUST be CRITICAL. Without this, the report
            # said "Carbon Budget Remaining: 0.1 yrs" yet "Risk: LOW",
            # which is logically inverted.
            _gap_num = float(_display_gap) if isinstance(_display_gap, (int, float)) else 0.0
            _s3_share_pw = (
                float(pathway_scope3_share)
                if isinstance(pathway_scope3_share, (int, float))
                else (float(_s3_share) if _s3_share is not None else 0.0)
            )
            _budget_yrs_raw = pathway.get('carbon_budget_remaining_yrs')
            try:
                _budget_yrs = float(_budget_yrs_raw) if _budget_yrs_raw is not None else None
            except (TypeError, ValueError):
                _budget_yrs = None

            if _budget_yrs is not None and _budget_yrs <= 1.0:
                _risk_signal = "CRITICAL"
                _risk_basis = (
                    f"carbon budget {_budget_yrs:.1f} yrs remaining at current trajectory — "
                    f"IPCC pathway exhausted before target year"
                )
            elif _budget_yrs is not None and _budget_yrs <= 5.0:
                _risk_signal = "HIGH"
                _risk_basis = (
                    f"carbon budget {_budget_yrs:.1f} yrs remaining — narrow window to align"
                )
            elif _align_status == "physically_impossible" or (_gap_num > 20 and _s3_share_pw >= 60):
                _risk_signal = "HIGH"
                _risk_basis = (
                    f"{_gap_label.lower()} {_gap_display_val}% with Scope 3 share {_s3_share_pw:.0f}%"
                )
            elif _gap_num > 10 or _s3_share_pw >= 70:
                _risk_signal = "MODERATE"
                _risk_basis = (
                    f"{_gap_label.lower()} {_gap_display_val}% / Scope 3 share {_s3_share_pw:.0f}%"
                )
            else:
                _risk_signal = "LOW"
                _risk_basis = (
                    f"{_gap_label.lower()} {_gap_display_val}% / Scope 3 share {_s3_share_pw:.0f}%"
                )
            section5b.append(
                f"  Carbon Alignment Risk: {_risk_signal} ({_risk_basis})"
            )
        section5b.append(major)

        green = state.get("greenwishing_analysis") or {}
        climate = state.get("climatebert_analysis") or v["agents"].get("climatebert_analysis", {}).get("output", {})
        overall_dec = safe_get(green, "overall_deception_risk", "score", default=0)
        overall_lvl = str(safe_get(green, "overall_deception_risk", "level", default="LOW")).upper()
        section7 = [major, "SECTION 9: DECEPTION PATTERN ANALYSIS", major]
        section7.append(f"  Overall Deception Risk:  {self._fmt_score1(overall_dec)}/100  ({overall_lvl})")
        if isinstance(overall_dec, (int, float)) and abs(float(overall_dec) - float(v["gw_score"])) > 30:
            section7.append(
                self._wrap_paragraph(
                    f"  NOTE: Deception Risk ({self._fmt_score1(overall_dec)}) and Greenwashing Score "
                    f"({v['gw_score']:.1f}) diverge materially. "
                    "Low deception + high greenwashing = disclosure gap, not intentional manipulation. "
                    "Risks are driven by omission and execution shortfalls rather than confirmed misrepresentation.",
                    width=80,
                )
            )
        section7.append("")

        # --- Tactic Table (consistent labels throughout) ---
        section7.append(f"  {'Tactic':<24} {'Status':<14} {'Score':<8} {'Evidence':<32}")
        section7.append("  " + "-" * 81)
        gw = green.get("greenwishing", {}) if isinstance(green, dict) else {}
        gh = green.get("greenhushing", {}) if isinstance(green, dict) else {}
        sd = green.get("selective_disclosure", {}) if isinstance(green, dict) else {}

        # Greenwishing row
        _gw_lvl = str(gw.get("risk_level", "LOW")).upper()
        _gw_status = "Risk: " + _gw_lvl.title()
        _gw_count = len(gw.get("findings", gw.get("indicators_found", [])) or [])
        section7.append(
            f"  {'Greenwishing':<24} {_gw_status:<14} {str(gw.get('score', '0')):<8} "
            f"{str(_gw_count) + ' indicator(s) detected':<32}"
        )
        # Greenhushing row
        _gh_lvl = str(gh.get("risk_level", "LOW")).upper()
        _gh_status = "Risk: " + _gh_lvl.title()
        _gh_missing = gh.get("missing_fields", 0)
        section7.append(
            f"  {'Greenhushing':<24} {_gh_status:<14} {str(gh.get('score', '0')):<8} "
            f"{str(_gh_missing) + ' missing field(s)':<32}"
        )
        # Selective disclosure row — no Yes/No, no N/A
        _sd_present = "Present" if sd.get("detected") else "Not Detected"
        _sd_count = len(sd.get("findings", sd.get("patterns", [])) or [])
        _sd_evidence = str(_sd_count) + " pattern(s) identified" if _sd_count > 0 else "No patterns identified"
        section7.append(
            f"  {'Selective disclosure':<24} {_sd_present:<14} " + "\u2014" + " " * 7 + f" {_sd_evidence:<32}"
        )
        # Carbon tunnel vision row — no Yes/No, no N/A
        _ctv_present = "Present" if len(missing_scopes) >= 2 else "Not Detected"
        _ctv_evidence = str(len(missing_scopes)) + " scope(s) undisclosed" if len(missing_scopes) >= 2 else "All scopes covered"
        section7.append(
            f"  {'Carbon tunnel vision':<24} {_ctv_present:<14} " + "\u2014" + " " * 7 + f" {_ctv_evidence:<32}"
        )
        section7.append("  " + "-" * 81)

        # --- Top Indicators (meaningful, deduplicated, max 3) ---
        indicators = (gw.get("findings") or gw.get("indicators_found") or []) if isinstance(gw, dict) else []
        _meaningful: list = []
        _seen: set = set()
        for item in indicators:
            if isinstance(item, dict):
                txt = str(item.get("description") or item.get("type") or "").replace("_", " ").strip()
            else:
                txt = str(item).replace("_", " ").strip()
            if not txt or txt.lower() in {"indicator detected", "n/a", "none", "unknown", ""}:
                continue
            txt_key = txt.lower()[:60]
            if txt_key in _seen:
                continue
            _seen.add(txt_key)
            _meaningful.append(txt)
            if len(_meaningful) == 3:
                break

        if _meaningful:
            section7.append("\n  Top indicators detected:")
            for m in _meaningful:
                section7.append(f"    - {m}")
        else:
            section7.append("\n  Top indicators: None \u2014 no high-confidence deception signals found in this run.")

        # --- Deception vs. Greenwashing Insight ---
        section7.append("")
        _dec = float(overall_dec) if isinstance(overall_dec, (int, float)) else 0.0
        _gw_score_val = float(v["gw_score"]) if isinstance(v.get("gw_score"), (int, float)) else 0.0
        if _dec < 30 and _gw_score_val >= 50:
            _interp_block = (
                "Interpretation: Low deception risk combined with elevated greenwashing risk signals that "
                "identified concerns are primarily driven by disclosure gaps and execution shortfalls rather than "
                "deliberate misrepresentation. The company does not appear to be intentionally misleading "
                "investors, but material omissions reduce transition credibility."
            )
        elif _dec >= 50:
            _interp_block = (
                "Interpretation: Elevated deception risk is driven by active rhetorical patterns \u2014 claims are "
                "framed in ways that go beyond what the underlying evidence supports. This warrants closer "
                "scrutiny of forward-looking commitments and target methodology."
            )
        else:
            _interp_block = (
                "Interpretation: Deception signals are within the low-to-moderate range. Residual risk is "
                "attributable to standard disclosure gaps rather than confirmed manipulative framing."
            )
        section7.append(self._wrap_paragraph(_interp_block, width=80))

        # --- ClimateBERT NLP Signal (optional supporting block) ---
        cb_score = safe_get(climate, "claim_analysis", "greenwashing_detection", "risk_score",
                            default=safe_get(climate, "greenwashing_risk", default=None))
        cb_level = str(safe_get(climate, "claim_analysis", "greenwashing_detection", "risk_level",
                                default=safe_get(climate, "risk_level", default=""))).upper()
        _clim_rel = safe_get(climate, "claim_analysis", "climate_relevance", "score",
                             default=safe_get(climate, "climate_relevance", default=None))
        c_claim = safe_get(climate, "comparison", "claim_greenwashing_score",
                           default=safe_get(climate, "claim_score", default=None))
        c_ev    = safe_get(climate, "comparison", "evidence_greenwashing_score",
                           default=safe_get(climate, "evidence_score", default=None))
        # Only display when the NLP block carries genuine signal variance
        _nlp_has_signal = (
            isinstance(cb_score, (int, float)) and cb_score > 0
            and isinstance(c_claim, (int, float)) and isinstance(c_ev, (int, float))
        )
        if _nlp_has_signal:
            section7.append("\n  NLP Supporting Signal (ClimateBERT):")
            # Suppress raw relevance score when it is constant / uninformative (> 95)
            if isinstance(_clim_rel, (int, float)) and _clim_rel > 95:
                section7.append("    Climate Relevance:    High climate relevance detected")
            elif isinstance(_clim_rel, (int, float)):
                section7.append(f"    Climate Relevance:    {self._fmt_score1(_clim_rel)} /100")
            # Claim vs evidence framing comparison \u2014 narrative, not raw scores
            _claim_gap = float(c_claim) - float(c_ev)
            if _claim_gap > 10:
                _lang_signal = "Claim language is notably more promotional than the supporting evidence."
            elif _claim_gap > 3:
                _lang_signal = "Claim language is slightly more optimistic than the supporting evidence."
            elif _claim_gap < -5:
                _lang_signal = "Evidence language is more promotional than the formal claim language."
            else:
                _lang_signal = "Claim language and evidence language are broadly consistent."
            section7.append(f"    NLP Signal:           {_lang_signal}")
            # Safe conflict handling \u2014 never surface contradicting verdict labels
            _sys_high = _dec >= 50 or overall_lvl in {"HIGH", "CRITICAL"}
            _nlp_high = cb_level in {"HIGH", "CRITICAL"} or (isinstance(cb_score, (int, float)) and cb_score >= 60)
            if _sys_high != _nlp_high:
                section7.append(
                    "    Note: NLP signal suggests more promotional language than evidence supports; "
                    "treat as a supplementary indicator alongside the structured deception scores above."
                )
            # ClimateBERT's own interpretation text (if non-generic)
            _cb_interp = safe_get(climate, "comparison", "interpretation", default="")
            if _cb_interp and len(str(_cb_interp)) > 20 and "reviewed for consistency" not in str(_cb_interp).lower():
                section7.append(f"    Supporting context:   {str(_cb_interp)[:120]}")

        # --- Concluding Risk Summary ---
        section7.append("")
        _top_tactics: list = []
        if _gw_lvl in {"HIGH", "CRITICAL", "MEDIUM", "MODERATE"}:
            _top_tactics.append("greenwishing")
        if _gh_lvl in {"HIGH", "CRITICAL", "MEDIUM", "MODERATE"}:
            _top_tactics.append("greenhushing")
        if sd.get("detected"):
            _top_tactics.append("selective disclosure")
        if len(missing_scopes) >= 2:
            _top_tactics.append("carbon tunnel vision")
        if not _top_tactics:
            _top_tactics.append("no dominant tactic detected")
        _tactic_str = ", ".join(_top_tactics)
        section7.append(
            self._wrap_paragraph(
                f"Overall, deception risk is assessed as {overall_lvl}, with primary concern(s) driven by: "
                f"{_tactic_str}. This should be interpreted alongside the greenwashing score "
                f"({v['gw_score']:.1f}/100) and any regulatory or contradiction signals raised in earlier sections.",
                width=80,
            )
        )
        section7.append("\n" + major)

        cal = v.get("calibration") or {}  # FIX: safe .get — never bare bracket
        section9 = [major, "SECTION 10: CALIBRATION & CONFIDENCE", major]
        section9.append(self._wrap_paragraph("This score is calibrated against a limited sample of verified cases. Results are indicative but should be interpreted with caution.", width=80))
        section9.append("")
        cal_state = cal.get("calibration_status", "NOT_AVAILABLE")
        dataset_size = cal.get("dataset_size")
        company_industry = v["industry"]

        if cal_state == "NOT_AVAILABLE":
            # Suppress calibration numbers entirely
            section9.extend([
                "Calibration not available \u2014 ground truth dataset not found or empty.",
                "Scores should be treated as indicative only.",
                "",
                "  The rating should be interpreted alongside qualitative context and sector",
                "  expertise. This is a probabilistic risk indicator, not a legal determination.",
                "",
                major,
            ])
        else:
            spearman_r = cal.get("spearman_r")
            spearman_p_reported = cal.get("p_value_reported")
            mean_gw = cal.get("mean_score_greenwashing")
            mean_leg = cal.get("mean_score_legitimate")
            subset_industry = cal.get("subset_industry") or company_industry
            subset_claim_type = cal.get("subset_claim_type") or "emissions"
            adjacent_used = bool(cal.get("adjacent_expansion_used"))
            adjacent_industries = cal.get("adjacent_industries") or []
            no_industry_match = bool(cal.get("no_industry_match"))
            fallback_used = bool(cal.get("fallback_used"))
            fallback_reason = cal.get("fallback_reason")
            low_sample = bool(cal.get("low_sample"))
            confidence_ceiling = cal.get("confidence_ceiling_pct")

            if v["threshold"] is not None:
                # Suppress threshold certainty language when calibration is not sector-matched
                _cal_render = v.get("calibration_render_status", "uncalibrated")
                if _cal_render == "calibrated":
                    if v["gw_score"] >= v["threshold"] + 10:
                        zone_text = (
                            f"Sits {v['gw_score'] - v['threshold']:.1f}pts above threshold - in the "
                            "calibration sample, scores this high are predominantly associated "
                            "with confirmed greenwashing cases."
                        )
                    elif v["gw_score"] <= v["threshold"] - 10:
                        zone_text = (
                            f"Sits {v['threshold'] - v['gw_score']:.1f}pts below threshold - in the "
                            "calibration sample, scores this low are more commonly associated "
                            "with legitimate ESG disclosures than with greenwashing."
                        )
                    else:
                        zone_text = (
                            f"Sits near the {v['threshold']:.1f} threshold in the grey zone - both legitimate "
                            "firms and greenwashers are observed at this score level. "
                            "Additional human review is recommended."
                        )
                elif _cal_render == "sector_mismatch":
                    zone_text = (
                        f"Threshold {v['threshold']:.1f} is derived from cross-sector fallback data, "
                        "not matched industry peers. Interpret with significant caution — "
                        "sector-specific calibration was not available."
                    )
                else:
                    zone_text = (
                        f"Threshold {v['threshold']:.1f} is available but the calibration dataset is "
                        "too small or absent for this sector. Treat as indicative only."
                    )
            else:
                zone_text = "Threshold not available \u2014 score interpretation requires manual review."

            status_label = f"{cal_state} (n={dataset_size} cases)"
            section9.append(f"Status:                 {status_label}")
            section9.append(f"Calibration subset:     {dataset_size} cases (industry: {subset_industry}, claim type: {subset_claim_type})")
            # IMPORTANT: the Spearman below is computed from the LINGUISTIC
            # STUB scorer (rule-based text matching) vs ground-truth labels —
            # NOT from the 30-agent pipeline. Label it clearly so readers don't
            # mistake it for pipeline-level validation.
            if isinstance(dataset_size, int) and dataset_size < 6:
                section9.append("Linguistic-stub Spearman r:  NOT REPORTED (subset n<6 — see system-level reference)")
            elif isinstance(spearman_r, (int, float)):
                if isinstance(dataset_size, int) and dataset_size < 10:
                    section9.append(f"Linguistic-stub Spearman r:  {spearman_r:.4f}  (small subset, interpret cautiously)")
                else:
                    section9.append(f"Linguistic-stub Spearman r:  {spearman_r:.4f}")
            else:
                section9.append("Linguistic-stub Spearman r:  unavailable")
            if isinstance(spearman_p_reported, (int, float)):
                section9.append(f"p-value:                     {spearman_p_reported:.4f}")
            else:
                section9.append(f"p-value:                     {spearman_p_reported}")
            section9.append(
                "Pipeline Spearman r:         NOT MEASURED (the 30-agent pipeline has not been"
            )
            section9.append(
                "                             benchmarked against the ground-truth dataset; the"
            )
            section9.append(
                "                             value above measures only the linguistic-stub scorer)"
            )
            if v["threshold"] is not None:
                section9.append(f"Optimal threshold:      {v['threshold']:.2f}")
            else:
                section9.append("Optimal threshold:      unavailable")
            if isinstance(mean_gw, (int, float)) and isinstance(mean_leg, (int, float)):
                section9.append(f"Mean greenwashing:      {mean_gw:.2f}")
                section9.append(f"Mean legitimate:        {mean_leg:.2f}")

            # ── System-level reference (whole dataset) ──────────────────
            sys_n = cal.get("system_dataset_size")
            sys_r = cal.get("system_spearman_r")
            sys_p = cal.get("system_spearman_p")
            sys_gw_m = cal.get("system_mean_greenwashing")
            sys_leg_m = cal.get("system_mean_legitimate")
            if isinstance(sys_n, int) and sys_n > 0 and (isinstance(sys_r, (int, float)) or isinstance(sys_gw_m, (int, float))):
                section9.append("")
                section9.append("System-level reference (full ground-truth dataset):")
                section9.append(f"  Cases (system):       {sys_n}")
                if isinstance(sys_r, (int, float)):
                    if isinstance(sys_p, (int, float)):
                        section9.append(f"  Linguistic-stub Spearman r (system):  {sys_r:.4f}  (p={sys_p:.4f})")
                    else:
                        section9.append(f"  Linguistic-stub Spearman r (system):  {sys_r:.4f}")
                if isinstance(sys_gw_m, (int, float)) and isinstance(sys_leg_m, (int, float)):
                    section9.append(f"  Mean greenwashing:    {sys_gw_m:.2f}    Mean legitimate:    {sys_leg_m:.2f}")

            if adjacent_used:
                if adjacent_industries:
                    section9.append(f"Note:                   Expanded to adjacent industries: {', '.join(adjacent_industries)}")
                else:
                    section9.append("Note:                   Expanded to adjacent industries")
            if low_sample:
                section9.append("WARNING:                LOW SAMPLE — treat with caution")
            if no_industry_match and fallback_used and fallback_reason == "NO_PEER_CASES":
                section9.append("WARNING:                NO PEER CASES — system-level stats used as fallback")
            if isinstance(confidence_ceiling, (int, float)):
                section9.append(f"Confidence ceiling:     {confidence_ceiling:.0f}%")

            section9.append("")
            if v["threshold"] is not None:
                section9.append("Score interpretation:")
                section9.append(f"  {v['gw_score']:.1f} / 100  ->  {'above' if v['gw_score'] >= v['threshold'] else 'below'} the {v['threshold']:.1f} threshold")
                section9.append("\n".join("  " + line for line in self._wrap_paragraph(zone_text, width=76).split("\n")))
            else:
                section9.append("Score interpretation:")
                section9.append(f"  {v['gw_score']:.1f} / 100  (no calibrated threshold available)")

            section9.append("")
            section9.append("  The rating should be interpreted alongside qualitative context and sector")
            section9.append("  expertise. This is a probabilistic risk indicator, not a legal determination.")

            section9.extend(["", major])

        section10_lines: List[str] = []
        section10_lines.append(f"Evidence coverage for this run is {len(v['citations'])} source(s), with {v['evidence'].get('verifiable_citations', 0)} verifiable citation(s).")
        if len(v["same_industry_peers"]) == 0:
            section10_lines.append("Peer comparison note: 0 same-industry peers were available, so peer benchmarking was not included.")
        if v["contradiction_count"] == 0:
            section10_lines.append("No legal contradiction was detected; this may indicate either true consistency or insufficient contrary evidence.")
        if v["confidence_pct"] < 60:
            section10_lines.append("Model confidence is below 60%, so borderline outcomes should be treated as preliminary and reviewed manually.")
        for lim in v["limitations"] if isinstance(v["limitations"], list) else []:
            txt = str(lim).strip()
            txt = txt.replace("agent failed or returned no output", "some analytical dimensions were not available for this run")
            txt = txt.replace("Agent failed or returned no output", "Some analytical dimensions were not available for this run")
            txt = txt.replace("failed or returned no output", "was not available for this run")
            if txt and txt not in section10_lines:
                section10_lines.append(txt)
        section10_lines = section10_lines[:5]
        while len(section10_lines) < 3:
            section10_lines.append("The score is probabilistic and does not constitute legal or regulatory determination.")

        section10 = [major, "SECTION 11: LIMITATIONS", major]
        for i, lim in enumerate(section10_lines, start=1):
            section10.append(f"  - {self._wrap_paragraph(str(lim), width=74)}")
        section10.append("\n" + major)

        # SECTION 11B - Commitment Timeline. Pull from state.commitment_ledger
        # OR from the commitment_ledger_update agent's output. If neither has
        # meaningful data, leave section10b empty so the renderer skips the block.
        commitment = state.get("commitment_ledger") if isinstance(state.get("commitment_ledger"), dict) else {}
        if not commitment:
            for _ao in (state.get("agent_outputs") or []):
                if isinstance(_ao, dict) and _ao.get("agent") == "commitment_ledger_update":
                    _out = _ao.get("output") or {}
                    if isinstance(_out, dict):
                        commitment = _out
                    break

        # Supplement the runtime snapshot with the FULL historical record from
        # the ledger DB so Section 11B reflects multi-year evolution, not just
        # the single new commitment from this run.
        try:
            from commitment_tracker.ledger import CommitmentLedger as _CL
            _company = state.get("company") or v.get("company")
            if _company:
                _ledger = _CL()
                _hist_score = _ledger.compute_promise_degradation_score(_company)
                with _ledger._connect() as _conn:
                    _hist_rev_rows = _conn.execute(
                        "SELECT revision_date, revision_type, severity_score, explanation, original_text, revised_text "
                        "FROM commitment_revisions WHERE company=? ORDER BY revision_date",
                        (_company,),
                    ).fetchall()
                    _hist_commit_count = _conn.execute(
                        "SELECT COUNT(DISTINCT run_date) FROM commitments WHERE company=?",
                        (_company,),
                    ).fetchone()[0]
                _hist_revisions = [
                    {
                        "revision_date": r["revision_date"],
                        "revision_type": r["revision_type"],
                        "severity": r["severity_score"],
                        "explanation": r["explanation"],
                        "original_text": r["original_text"],
                        "revised_text": r["revised_text"],
                    }
                    for r in _hist_rev_rows
                ]
                # Prefer historical figures whenever they exceed the runtime snapshot
                # (the snapshot only knows about this single run).
                if _hist_score > float(commitment.get("promise_degradation_score") or 0.0):
                    commitment = dict(commitment)
                    commitment["promise_degradation_score"] = _hist_score
                if _hist_revisions and not commitment.get("revision_events"):
                    commitment = dict(commitment)
                    commitment["revision_events"] = _hist_revisions
                if _hist_commit_count > int(commitment.get("inserted_commitments") or 0):
                    commitment = dict(commitment)
                    commitment.setdefault("historical_commitment_runs", _hist_commit_count)
        except Exception:
            pass

        _has_meaningful_commitment_data = (
            isinstance(commitment, dict)
            and (
                commitment.get("inserted_commitments") not in (None, 0)
                or (isinstance(commitment.get("revision_events"), list) and commitment.get("revision_events"))
                or commitment.get("promise_degradation_score") not in (None, 0, 0.0)
                or commitment.get("historical_commitment_runs") not in (None, 0)
            )
        )
        section10b: List[str] = []
        if _has_meaningful_commitment_data:
            section10b = [major, "SECTION 11B: COMMITMENT TIMELINE", major]
            section10b.append("This section tracks how company commitments evolve over time and whether accountability weakens.")
            section10b.append("")
            section10b.append(f"Promise Degradation Score: {commitment.get('promise_degradation_score', 'N/A')}/100 (Higher score indicates greater backsliding)")
            section10b.append(f"Commitments Recorded This Run: {commitment.get('inserted_commitments', 0)}")
            _hist_runs = commitment.get("historical_commitment_runs")
            if isinstance(_hist_runs, int) and _hist_runs > 0:
                section10b.append(f"Distinct historical commitment-tracking runs (this company): {_hist_runs}")
            revisions = commitment.get("revision_events", []) if isinstance(commitment.get("revision_events"), list) else []
            if revisions:
                section10b.append("")
                section10b.append(f"Revision events detected ({len(revisions)} total, showing most recent {min(len(revisions), 5)}):")
                for idx, rev in enumerate(revisions[-5:], start=1):
                    if not isinstance(rev, dict):
                        continue
                    _date = rev.get("revision_date") or ""
                    _date_str = f" [{_date}]" if _date else ""
                    section10b.append(
                        f"  {idx}.{_date_str} {rev.get('revision_type', 'reframed')} | Severity {rev.get('severity', 0)}/100"
                    )
                    if rev.get("original_text"):
                        section10b.append(f"     before: {self._smart_truncate(rev.get('original_text'), 100)}")
                    if rev.get("revised_text"):
                        section10b.append(f"     after:  {self._smart_truncate(rev.get('revised_text'), 100)}")
                    if rev.get("explanation"):
                        section10b.append(f"     why: {self._smart_truncate(rev.get('explanation'), 100)}")
            else:
                section10b.append("No substantive commitment weakening events were detected in this run.")
            section10b.append(major)
        # else: leave empty — block will be filtered out of ordered_keys

        # ── SECTION 11C: KNOWLEDGE GRAPH HISTORY ─────────────────────────
        # Surfaces what the persistent KG knows about this company across
        # all prior runs: KPI history count, year-over-year drift signals,
        # and Fact Graph motif diagnostics. Empty for first-ever runs.
        section11c: List[str] = []
        try:
            kg_block = self._build_kg_history_section(state, major)
            if kg_block:
                section11c = kg_block
        except Exception as exc:
            print(f"⚠️  KG history section render failed: {exc}")

        section11 = self._render_esg_mismatch_section(state, major)

        appendix_a = [major, "APPENDIX A: VALIDATION & CALIBRATION STATUS", major, self._plain_textify(self._generate_validation_metadata_section(v.get("calibration", {}), company_industry=v.get("industry", "Unknown"))), "", major]
        appendix_b = [major, "APPENDIX B: TEMPORAL ESG CONSISTENCY", major, self._plain_textify(self._generate_temporal_consistency_section(state)), "", major]
        appendix_c = [major, "APPENDIX C: EVIDENCE & OFFSET INTEGRITY", major, self._plain_textify(self._generate_realism_diagnostics_section(state)), "", major]

        # ── Decision state from canonical resolver (Phase 3: render from v) ──
        score_disclaimer = str(v.get("score_disclaimer", "")).strip()
        decision_status = str(v.get("decision_status", "SCORED")).strip()
        abstainrecommended = bool(v.get("abstain_recommended", False))
        abstentionreason = str(v.get("abstention_reason", "")).strip()

        gw_score_disp = f"{v['gw_score']:.1f} / 100"
        # ESG display: use canonical resolved score (already in v["esg_score"])
        # If a separate raw (un-adjusted) ESG score is available, show both side-by-side
        # so the audience can see industry-adjustment effects without flipping to JSON.
        _v_scores = v.get("scores", {}) if isinstance(v.get("scores"), dict) else {}
        _v_pillar = _v_scores.get("pillar_scores", {}) if isinstance(_v_scores.get("pillar_scores"), dict) else {}
        _esg_display_value = _v_pillar.get("displayesgscore")
        _esg_overall_value = _v_pillar.get("overall_esg_score")
        if (
            isinstance(_esg_display_value, (int, float))
            and isinstance(_esg_overall_value, (int, float))
            and abs(float(_esg_display_value) - float(_esg_overall_value)) >= 0.5
        ):
            # Show both — raw pillar-derived and industry-adjusted
            esg_score_disp = f"{float(_esg_overall_value):.1f} / 100  (raw pillar-derived)  |  {float(_esg_display_value):.1f} / 100  (industry-adjusted)"
        else:
            esg_score_disp = f"{v['esg_score']:.1f} / 100"

        # Industry baseline reference (MSCI ESG Industry Materiality Map etc.) for context.
        _baseline_risk = _v_scores.get("raw", {}).get("industry_baseline_risk") if isinstance(_v_scores.get("raw"), dict) else None
        _baseline_source = _v_scores.get("raw", {}).get("industry_source") if isinstance(_v_scores.get("raw"), dict) else None
        baseline_line = ""
        if isinstance(_baseline_risk, (int, float)) and _baseline_source:
            baseline_line = f"  Industry Baseline Risk:   {float(_baseline_risk):.1f} / 100  (source: {_baseline_source})"
        elif isinstance(_baseline_risk, (int, float)):
            baseline_line = f"  Industry Baseline Risk:   {float(_baseline_risk):.1f} / 100"
        n_size = cal.get("dataset_size")
        band_disp = str(v['band'])
        if n_size is None or n_size < 30:
            band_disp = f"{v['band']} (Provisional numeric score shown; calibration sample too small for this sector)"
        if n_size is None or n_size < 10:
            cal_status_disp = f"PROVISIONAL [{cal.get('calibration_status', 'N/A')} - VERY_LOW (n={n_size or 0})]"
        elif n_size < 30:
            cal_status_disp = f"PROVISIONAL [{cal.get('calibration_status', 'N/A')} - LOW (n={n_size or 0})]"
        else:
            cal_status_disp = f"{v['calibration_status']}  [{cal.get('calibration_status', 'N/A')} - n={n_size or 0}]"

        verdict_justification = []
        
        # Calculate DATA COVERAGE
        evidence_count = len(v.get('citations', []))
        carbon_output = v.get("agents", {}).get("carbon_extractor", {}).get("output", {})
        scope3_val = carbon_output.get("scope3_emissions", {}).get("value")
        if evidence_count >= 10 and scope3_val:
            data_coverage = "HIGH"
        elif evidence_count >= 5:
            data_coverage = "MODERATE"
        else:
            data_coverage = "LOW"
            
        data_coverage_str = f"  Data Coverage:            {data_coverage}"
        if data_coverage == "LOW":
            data_coverage_str += " (Results are based on limited disclosure and external signals)"

        if score_disclaimer:
            verdict_justification.append(score_disclaimer)
        # Only show abstention language when abstention is actually recommended
        if abstainrecommended and abstentionreason:
            verdict_justification.append(f"Decision status: {decision_status}. Justification: {abstentionreason}")

        # ──────────────────────────────────────────────────────────────────
        # NEW SECTIONS: surface JSON-rich content into the TXT report so the
        # presentation reflects the full depth of the analysis (materiality,
        # component drivers, compliance framework status, audit trail).
        # ──────────────────────────────────────────────────────────────────
        _scores_block = v.get("scores", {}) if isinstance(v.get("scores"), dict) else {}
        _raw_risk = _scores_block.get("raw", {}) if isinstance(_scores_block.get("raw"), dict) else {}
        _pillar_scores = _scores_block.get("pillar_scores", {}) if isinstance(_scores_block.get("pillar_scores"), dict) else {}
        _materiality = _pillar_scores.get("materiality_profile", {}) if isinstance(_pillar_scores.get("materiality_profile"), dict) else {}
        _pillar_weighting = _pillar_scores.get("pillar_weighting", {}) if isinstance(_pillar_scores.get("pillar_weighting"), dict) else {"E": 0.35, "S": 0.30, "G": 0.35}
        _component_scores = _scores_block.get("component_scores", {}) if isinstance(_scores_block.get("component_scores"), dict) else {}
        _adversarial_audit = (
            _raw_risk.get("adversarial_audit")
            or state.get("adversarial_audit")
            or {}
        )
        if not isinstance(_adversarial_audit, dict):
            _adversarial_audit = {}
        # Compliance frameworks: try multiple known locations
        # 1. risk_results.compliance (rare)
        # 2. regulatory_scanning agent output's compliance_result.frameworks (canonical)
        # 3. agent output's compliance_score.frameworks (alias)
        _compliance = _raw_risk.get("compliance") if isinstance(_raw_risk.get("compliance"), dict) else {}
        _compliance_frameworks = _compliance.get("frameworks") if isinstance(_compliance.get("frameworks"), list) else []
        if not _compliance_frameworks:
            for _ao in (state.get("agent_outputs") or []):
                if isinstance(_ao, dict) and _ao.get("agent") == "regulatory_scanning":
                    _out = _ao.get("output") or {}
                    if not isinstance(_out, dict):
                        continue
                    # canonical location
                    _cr = _out.get("compliance_result") or _out.get("compliance_score") or {}
                    if isinstance(_cr, dict) and isinstance(_cr.get("frameworks"), list):
                        _compliance_frameworks = _cr["frameworks"]
                        if not _compliance:
                            _compliance = _cr
                        break
                    # legacy fallbacks
                    _fr = _out.get("frameworks") or _out.get("compliance_frameworks")
                    if isinstance(_fr, list):
                        _compliance_frameworks = _fr
                        if not _compliance:
                            _compliance = _out
                        break

        # ── 5A: MATERIALITY PROFILE ──────────────────────────────────────
        materiality_lines = [major, "SECTION 5A: MATERIALITY PROFILE", major]
        e_w = float(_pillar_weighting.get("E", 0.35) or 0.35)
        s_w = float(_pillar_weighting.get("S", 0.30) or 0.30)
        g_w = float(_pillar_weighting.get("G", 0.35) or 0.35)
        # Some pipelines emit materiality.weights as the canonical source
        if isinstance(_materiality.get("weights"), dict):
            _mw = _materiality["weights"]
            try:
                e_w = float(_mw.get("E", e_w))
                s_w = float(_mw.get("S", s_w))
                g_w = float(_mw.get("G", g_w))
            except (TypeError, ValueError):
                pass
        materiality_industry = str(_materiality.get("industry") or v.get("industry") or "Unknown")
        rationale = str(_materiality.get("rationale") or "Default 35/30/35 weighting (no industry-specific materiality profile loaded).")
        topics = _materiality.get("material_topics") or []
        if not isinstance(topics, list):
            topics = []
        materiality_lines.append(self._wrap_paragraph(
            f"This assessment uses an industry-specific materiality profile to weight Environmental, "
            f"Social, and Governance pillars. For {materiality_industry}, the weighting reflects which "
            f"factors most influence long-term value creation and risk exposure.",
            width=80,
        ))
        materiality_lines.append("")
        materiality_lines.append(f"  Industry profile:        {materiality_industry}")
        materiality_lines.append(f"  Environmental weight:    {e_w*100:.1f}%")
        materiality_lines.append(f"  Social weight:           {s_w*100:.1f}%")
        materiality_lines.append(f"  Governance weight:       {g_w*100:.1f}%")
        materiality_lines.append("")
        if topics:
            materiality_lines.append("  Material topics for this industry:")
            for t in topics[:8]:
                materiality_lines.append(f"    • {str(t).strip()}")
            materiality_lines.append("")
        materiality_lines.append("  Weighting rationale:")
        materiality_lines.append(self._indent_wrapped(rationale, width=76, indent="    "))
        materiality_lines.append(major)

        # ── 5C: SCORE COMPONENT BREAKDOWN ────────────────────────────────
        component_lines = [major, "SECTION 5C: SCORE COMPONENT BREAKDOWN", major]
        component_lines.append(self._wrap_paragraph(
            "The greenwashing risk score is the weighted aggregation of seven underlying drivers. "
            "Each driver scores 0-100 (higher = more risk). This breakdown shows where the headline "
            "score originates so reviewers can challenge specific contributors.",
            width=80,
        ))
        component_lines.append("")
        if _component_scores:
            _label_map = {
                "claim_verification":      "Claim Verification Strength",
                "evidence_quality":        "Evidence Quality / Credibility",
                "source_credibility":      "Source Credibility Mix",
                "sentiment_divergence":    "Sentiment Divergence (claim vs reality)",
                "narrative_discrepancy_gsi": "Narrative Discrepancy (GSI)",
                "historical_pattern":      "Historical Pattern Risk",
                "contradiction_severity":  "Contradiction Severity",
            }
            component_lines.append(f"  {'Driver':<42} {'Score (0-100)':>14}   {'Reading':<14}")
            component_lines.append("  " + "-" * 78)
            for key, val in _component_scores.items():
                if not isinstance(val, (int, float)):
                    continue
                label = _label_map.get(key, str(key).replace("_", " ").title())
                v_num = float(val)
                if v_num >= 60:
                    reading = "Elevated risk"
                elif v_num >= 35:
                    reading = "Moderate"
                else:
                    reading = "Low"
                component_lines.append(f"  {label[:42]:<42} {v_num:>10.1f}     {reading:<14}")
            component_lines.append("  " + "-" * 78)
            component_lines.append("")
            component_lines.append(
                "  Read alongside Section 5: pillar scores describe what the company looks like;"
            )
            component_lines.append(
                "  component scores describe what's driving the greenwashing assessment."
            )
        else:
            component_lines.append("  Component-level decomposition was not produced for this run.")
        component_lines.append(major)

        # ── 7B: REGULATORY FRAMEWORK FULL STATUS ─────────────────────────
        compliance_lines = [major, "SECTION 7B: REGULATORY FRAMEWORK STATUS (FULL)", major]
        compliance_lines.append(self._wrap_paragraph(
            "Section 7 lists frameworks where gaps were detected. This section shows the full set of "
            "frameworks evaluated — including those where compliance signals were positive — so the "
            "regulatory picture is balanced rather than gap-only.",
            width=80,
        ))
        compliance_lines.append("")
        if _compliance_frameworks:
            comp_score = _compliance.get("score") if isinstance(_compliance, dict) else None
            comp_risk = _compliance.get("risk_level") if isinstance(_compliance, dict) else None
            if isinstance(comp_score, (int, float)) or comp_risk:
                _bits = []
                if isinstance(comp_score, (int, float)):
                    _bits.append(f"Compliance Score: {float(comp_score):.1f}/100")
                if comp_risk:
                    _bits.append(f"Risk Level: {comp_risk}")
                compliance_lines.append("  " + "    ".join(_bits))
                compliance_lines.append("")
            compliance_lines.append(f"  {'Jurisdiction':<10} {'Framework':<42} {'Status':<11} {'Weight':<6} {'Material':<8} {'Sources':<8}")
            compliance_lines.append("  " + "-" * 92)
            # Dedupe by (jurisdiction, framework, status). Multiple URL-level
            # rows for the same framework/status are aggregated into one row
            # with a count of sources reviewed.
            _grouped: Dict[tuple, Dict[str, Any]] = {}
            _order: List[tuple] = []
            for fr in _compliance_frameworks:
                if not isinstance(fr, dict):
                    continue
                juris = str(fr.get("jurisdiction", "—")).strip()
                fwk = str(fr.get("framework", "Unknown")).strip()
                status = str(fr.get("status", "uncertain")).upper().strip()
                key = (juris, fwk, status)
                if key not in _grouped:
                    _grouped[key] = {
                        "jurisdiction": juris,
                        "framework": fwk,
                        "status": status,
                        "material": bool(fr.get("material_misstatement_risk")),
                        "violation": str(fr.get("specific_violation") or "").strip(),
                        "source_count": 0,
                        "real_data": bool(fr.get("real_data")),
                        "evidence_url": str(fr.get("evidence_url") or "").strip(),
                        "source_name": str(fr.get("source_name") or "").strip(),
                        "fetched_at": str(fr.get("fetched_at") or "").strip(),
                    }
                    _order.append(key)
                _grouped[key]["source_count"] += 1
                # Promote material flag if any underlying row marks it
                if fr.get("material_misstatement_risk"):
                    _grouped[key]["material"] = True
                # Promote real_data marker / evidence URL when present
                if fr.get("real_data"):
                    _grouped[key]["real_data"] = True
                if not _grouped[key]["evidence_url"] and fr.get("evidence_url"):
                    _grouped[key]["evidence_url"] = str(fr.get("evidence_url"))
                if not _grouped[key]["source_name"] and fr.get("source_name"):
                    _grouped[key]["source_name"] = str(fr.get("source_name"))
                if not _grouped[key]["fetched_at"] and fr.get("fetched_at"):
                    _grouped[key]["fetched_at"] = str(fr.get("fetched_at"))
                # Keep the longest available violation text
                _v = str(fr.get("specific_violation") or "").strip()
                if len(_v) > len(_grouped[key]["violation"]):
                    _grouped[key]["violation"] = _v
            # Sort: GAP / ACTIVE_ENFORCEMENT first, then UNCERTAIN, then
            # COMPLIANT, then NOT_EVALUATED (least informative — pushed
            # to the bottom but still rendered for transparency).
            _status_rank = {
                "GAP": 0,
                "ACTIVE_ENFORCEMENT": 0,
                "UNCERTAIN": 1,
                "COMPLIANT": 2,
                "NOT_EVALUATED": 3,
                "NOT EVALUATED": 3,
            }
            _status_label = {
                "ACTIVE_ENFORCEMENT": "ACTIVE_ENF",
                "NOT_EVALUATED": "NOT_TESTED",
                "NOT EVALUATED": "NOT_TESTED",
            }
            _order.sort(key=lambda k: (_status_rank.get(k[2], 4), k[0], k[1]))
            for key in _order:
                row = _grouped[key]
                juris = row["jurisdiction"][:10]
                fwk = row["framework"]
                if len(fwk) > 42:
                    fwk = fwk[:39] + "..."
                status_raw = row["status"]
                status = _status_label.get(status_raw, status_raw)[:11]
                # Mark rows backed by a real public-registry fetch with a "*"
                # so readers can distinguish authoritative checks from
                # supplementary keyword/DDG signals.
                if row.get("real_data"):
                    status = (status[:10] + "*") if not status.endswith("*") else status
                material = "Yes" if row["material"] else "No"
                src_n = row["source_count"]
                src_label = f"{src_n}" if src_n > 1 else "1"
                # Source-credibility weight from the framework registry — only
                # meaningful for real-data rows (heuristic rows show "—").
                if row.get("real_data"):
                    try:
                        from utils.regulatory_fetchers import get_framework_weight
                        _w = get_framework_weight(row["framework"])
                        weight_label = f"{_w:.1f}"
                    except Exception:
                        weight_label = "—"
                else:
                    weight_label = "—"
                compliance_lines.append(f"  {juris:<10} {fwk:<42} {status:<11} {weight_label:<6} {material:<8} {src_label:<8}")
                # Violation / explanation
                if row["violation"] and row["status"] not in {"COMPLIANT", "NOT_EVALUATED", "NOT EVALUATED"}:
                    compliance_lines.append(f"      └─ {row['violation'][:120]}")
                elif row.get("real_data") and row["violation"]:
                    # COMPLIANT real-data rows still benefit from the evidence
                    # line (e.g. "Filed 10-K on 2026-02-13").
                    compliance_lines.append(f"      └─ {row['violation'][:120]}")
                # Source citation when real-data
                if row.get("real_data") and (row.get("source_name") or row.get("evidence_url")):
                    src_name = row.get("source_name") or "Public registry"
                    fetched = row.get("fetched_at") or ""
                    src_url = row.get("evidence_url") or ""
                    line = f"         Source: {src_name}"
                    if fetched:
                        line += f"  ({fetched})"
                    if src_url:
                        line += f"  {src_url[:90]}"
                    compliance_lines.append(line)
            compliance_lines.append("  " + "-" * 92)
            compliance_lines.append(
                "  Sources column = number of underlying URL-level evidence rows merged into the framework status."
            )
            compliance_lines.append(
                "  Weight column = source-credibility weight (0.0-1.0). 1.0 = government registry / mandatory"
            )
            compliance_lines.append(
                "  filing (SEC EDGAR, SEBI BRSR, FTC, CDP, SBTi, EU ESEF). 0.8 = voluntary registry (UN GC, GRI)."
            )
            compliance_lines.append(
                "  0.7 = in-disclosure inference (GHG Protocol, NSE/BSE listing fact). '—' = heuristic-only row."
            )
            compliance_lines.append(
                "  Status with '*' = verified against a public registry (SEC EDGAR, SBTi portal, FSB-TCFD,"
            )
            compliance_lines.append(
                "  CDP A-list, UN Global Compact, NSE/BSE, EU ESEF, SEBI BRSR). Others are heuristic signals."
            )
        else:
            compliance_lines.append("  Framework-level status not available for this run.")
        compliance_lines.append(major)

        # ── 10B: ADVERSARIAL AUDIT TRAIL ─────────────────────────────────
        audit_lines = [major, "SECTION 10B: ADVERSARIAL AUDIT TRAIL", major]
        audit_lines.append(self._wrap_paragraph(
            "Each agent in the pipeline produces an output and a confidence. The adversarial audit "
            "looks across agent outputs for coordination risk (agreement that may indicate echo bias) "
            "and confidence spread (disagreement that signals uncertainty). High coordination is not "
            "necessarily good — it can mask blind spots; high spread is not necessarily bad — it "
            "reflects honest uncertainty.",
            width=80,
        ))
        audit_lines.append("")
        if _adversarial_audit:
            def _fmt(val, suffix=""):
                if isinstance(val, (int, float)):
                    return f"{val:.2f}{suffix}" if not float(val).is_integer() else f"{int(val)}{suffix}"
                return str(val) if val is not None else "N/A"
            agents_seen = _adversarial_audit.get("agents_seen") or []
            agent_count = len(agents_seen) if isinstance(agents_seen, list) else 0
            successful = _adversarial_audit.get("successful_agents", agent_count)
            failed = _adversarial_audit.get("failed_agents", 0)
            audit_lines.append(f"  Agents executed:              {agent_count}")
            audit_lines.append(f"  Successful agents:            {successful}")
            audit_lines.append(f"  Failed agents:                {failed}")
            audit_lines.append(f"  Mean agent confidence:        {_fmt(_adversarial_audit.get('mean_agent_confidence'))}")
            audit_lines.append(f"  Confidence spread:            {_fmt(_adversarial_audit.get('confidence_spread'))}")
            audit_lines.append(f"  Coordination risk:            {_fmt(_adversarial_audit.get('coordination_risk'))} ({_adversarial_audit.get('coordination_risk_band','UNKNOWN')})")
            audit_lines.append(f"  Debate conflict ratio:        {_fmt(_adversarial_audit.get('debate_conflict_ratio'))}")
            audit_lines.append(f"  Contradictions observed:      {_fmt(_adversarial_audit.get('contradictions_count'))}")
            audit_lines.append(f"  Regulatory gaps observed:     {_fmt(_adversarial_audit.get('regulatory_gap_count'))}")
            cp = _adversarial_audit.get("confidence_penalty")
            if isinstance(cp, (int, float)):
                audit_lines.append(f"  Confidence penalty applied:   +{float(cp)*100:.1f}pp from coordination/disagreement")
            audit_lines.append("")
            audit_lines.append(
                "  Interpretation: a low confidence spread (<0.30) with high coordination (>0.70) "
                "indicates the pipeline is cohesive but may share a blind spot. A high confidence "
                "spread (>0.50) signals real disagreement among independent analyses — review the "
                "individual agent findings before relying on the headline score."
            )
        else:
            audit_lines.append("  Adversarial audit was not produced for this run.")
        audit_lines.append(major)

        # ── 7C: ENFORCEMENT & FINES HISTORY ──────────────────────────────
        # Pull from governance_analysis.signals.regulatory_legal — surfaces
        # the regulatory fine signals an audience would otherwise miss.
        enforcement_lines = [major, "SECTION 7C: ENFORCEMENT & FINES HISTORY", major]
        _gov_signals = {}
        for _ao in (state.get("agent_outputs") or []):
            if isinstance(_ao, dict) and _ao.get("agent") == "governance_analysis":
                _out = _ao.get("output") or {}
                if isinstance(_out, dict):
                    _gov_signals = _out.get("signals") or {}
                break
        # Also try state-level fallback (replay populates this)
        if not _gov_signals:
            _gov_state = state.get("governance_analysis") or {}
            if isinstance(_gov_state, dict):
                _gov_signals = _gov_state.get("signals") or {}
        _reg_legal = _gov_signals.get("regulatory_legal") if isinstance(_gov_signals.get("regulatory_legal"), dict) else {}
        _fine_count = _reg_legal.get("regulatory_fine_signals", 0)
        _fine_sources = _reg_legal.get("sources") or []
        if not isinstance(_fine_sources, list):
            _fine_sources = []

        # CROSS-SECTION RECONCILIATION: Pull enforcement signals from three
        # additional places so Section 7C is consistent with the rest of
        # the report. Without this, Section 7 could say "$34.7B Dieselgate
        # settlement (CRITICAL)" while Section 7C said "0 fines detected"
        # — the two sections drew from different agents and never crossed.
        #
        # Sources merged:
        #   1. Contradictions with severity CRITICAL/HIGH and a regulatory_action
        #      keyword (lawsuit/settlement/fine/enforcement/EPA/SEC/DOJ)
        #   2. regulatory_compliance.compliance_results rows with status =
        #      "active_enforcement" or framework = "Active Enforcement / Litigation"
        #   3. verdict_data.ground_truth_validation when outcome is
        #      CONFIRMED_GREENWASHING (the regulatory_action field carries the
        #      authoritative description: "$34.7B settlement (EPA, FTC, DOJ)")
        _enforce_keywords = (
            "lawsuit", "ruling", "settlement", "fine", "fines", "fined",
            "enforcement", "epa", "ftc", "doj", "sec ", "court", "consent decree",
        )
        # 1. Contradictions
        _contras = []
        for _ao in (state.get("agent_outputs") or []):
            if isinstance(_ao, dict) and _ao.get("agent") == "contradiction_analysis":
                _out = _ao.get("output") or {}
                _contras = (_out.get("contradictions") or []) if isinstance(_out, dict) else []
                break
        for c in _contras or []:
            if not isinstance(c, dict):
                continue
            sev = str(c.get("severity") or c.get("level") or "").upper()
            text = " ".join([
                str(c.get("title") or c.get("issue") or ""),
                str(c.get("description") or c.get("evidence") or ""),
                str(c.get("source") or ""),
            ]).lower()
            if sev in {"CRITICAL", "HIGH"} and any(k in text for k in _enforce_keywords):
                _fine_sources.append({
                    "title": str(c.get("title") or c.get("issue") or "Enforcement contradiction")[:200],
                    "url": c.get("url") or c.get("source_url"),
                    "_origin": "contradiction",
                    "severity": sev,
                })
        # 2. Active enforcement rows from regulatory scanner
        _reg_compliance = state.get("regulatory_compliance") or state.get("regulatory_results") or {}
        _frameworks = (_reg_compliance.get("compliance_result") or {}).get("frameworks") or []
        for fr in _frameworks or []:
            if not isinstance(fr, dict):
                continue
            status = str(fr.get("status") or "").lower()
            framework = str(fr.get("framework") or "").lower()
            if status == "active_enforcement" or "active enforcement" in framework or "litigation" in framework:
                _fine_sources.append({
                    "title": str(fr.get("specific_violation") or fr.get("framework") or "Active enforcement")[:200],
                    "url": fr.get("evidence_url"),
                    "_origin": "regulatory_scanner",
                })
        # 3. Ground-truth known cases (CONFIRMED_GREENWASHING)
        _verdict_ao = next(
            (o for o in (state.get("agent_outputs") or []) if o.get("agent") == "verdict_generation"),
            {},
        )
        _gt = ((_verdict_ao.get("output") or {}).get("ground_truth_validation") or {}) if isinstance(_verdict_ao, dict) else {}
        if not _gt:
            _gt = (state.get("final_verdict") or {}).get("ground_truth_validation") or {}
        if _gt.get("case_found") and (_gt.get("outcome") or "").upper() == "CONFIRMED_GREENWASHING":
            _ra = _gt.get("regulatory_action") or ""
            if _ra:
                # No "[GROUND TRUTH]" prefix here — the renderer below adds
                # the origin tag based on _origin, so prefixing here results
                # in "[GROUND TRUTH] [GROUND TRUTH] $34.7B settlement...".
                _fine_sources.insert(0, {
                    "title": str(_ra)[:200],
                    "url": None,
                    "_origin": "known_case",
                    "case_id": _gt.get("case_id"),
                })
        # Dedupe by title
        _seen_titles = set()
        _deduped = []
        for s in _fine_sources:
            t = str(s.get("title") or "").strip().lower()
            if not t or t in _seen_titles:
                continue
            _seen_titles.add(t)
            _deduped.append(s)
        _fine_sources = _deduped
        # Recompute count to match the merged set
        if _fine_sources and not _fine_count:
            _fine_count = len(_fine_sources)

        enforcement_lines.append(self._wrap_paragraph(
            "Historical regulatory penalties, enforcement actions, and litigation references "
            "from governance analysis, contradictions, the regulatory scanner, and the "
            "ground-truth known-cases registry. Cross-sourced so Section 7 (contradictions) "
            "and Section 7C (this section) cannot disagree on whether enforcement exists.",
            width=80,
        ))
        enforcement_lines.append("")
        if _fine_count or _fine_sources:
            enforcement_lines.append(f"  Regulatory fine / enforcement signals detected: {_fine_count}")
            enforcement_lines.append(f"  Source records reviewed:                      {len(_fine_sources)}")
            enforcement_lines.append("")
            if _fine_sources:
                enforcement_lines.append("  Source records:")
                for _src in _fine_sources[:10]:
                    if not isinstance(_src, dict):
                        continue
                    title = str(_src.get("title") or "(untitled)").strip()[:140]
                    url = str(_src.get("url") or "").strip()
                    origin = _src.get("_origin") or "governance_search"
                    origin_tag = {
                        "known_case": "[GROUND TRUTH]",
                        "contradiction": "[CONTRADICTION]",
                        "regulatory_scanner": "[REGULATORY]",
                        "governance_search": "[NEWS/SEARCH]",
                    }.get(origin, f"[{origin.upper()}]")
                    enforcement_lines.append(f"    • {origin_tag} {title}")
                    if url:
                        enforcement_lines.append(f"      {url}")
                enforcement_lines.append("")
                enforcement_lines.append(
                    "  Origin tags: [GROUND TRUTH] = matched against the curated known-cases "
                    "registry (data/known_cases.py); [CONTRADICTION] = surfaced by the "
                    "contradiction analyzer; [REGULATORY] = active_enforcement row from the "
                    "regulatory scanner; [NEWS/SEARCH] = aggregated from governance search."
                )
        else:
            enforcement_lines.append("  No regulatory fine or enforcement signals were detected in this run.")
        enforcement_lines.append(major)

        # ── 9B: RECENT NEWS & ACTIVE COVERAGE ────────────────────────────
        # Pull from realtime_monitoring agent's articles[] — surfaces
        # current public discourse around the company that may not yet be
        # codified into formal contradictions or regulatory filings.
        news_lines = [major, "SECTION 9B: RECENT NEWS & ACTIVE COVERAGE", major]
        _articles = []
        for _ao in (state.get("agent_outputs") or []):
            if isinstance(_ao, dict) and _ao.get("agent") == "realtime_monitoring":
                _out = _ao.get("output") or {}
                if isinstance(_out, dict):
                    _articles = _out.get("articles") or []
                break
        # State-level fallback
        if not _articles:
            _rt_state = state.get("realtime_monitoring") or {}
            if isinstance(_rt_state, dict):
                _articles = _rt_state.get("articles") or []
        if not isinstance(_articles, list):
            _articles = []
        news_lines.append(self._wrap_paragraph(
            "Current news coverage and public discourse signals captured by the real-time "
            "monitoring agent. These items reflect what would inform a market participant's "
            "view today; they are NOT graded contradictions.",
            width=80,
        ))
        news_lines.append("")
        if _articles:
            news_lines.append(f"  Articles surfaced: {len(_articles)}  (showing top {min(7, len(_articles))})")
            news_lines.append("")
            for i, _art in enumerate(_articles[:7], start=1):
                if not isinstance(_art, dict):
                    continue
                title = self._normalize_scraped_text((_art.get("title") or "(untitled)").strip())
                src = (_art.get("source_name") or _art.get("source_id") or "").strip()
                src_type = (_art.get("source_type") or "").strip()
                url = (_art.get("url") or "").strip()
                snippet = (_art.get("snippet") or _art.get("relevant_text") or "").strip()
                # Trim whitespace runs in snippet, then re-space joined camelCase
                # tokens left over from HTML scraping (e.g. "JPMorganChase&Co.").
                snippet = self._normalize_scraped_text(" ".join(snippet.split()))
                date_str = (_art.get("date") or "")[:10] if _art.get("date") else ""
                hdr_bits = [f"[{i}]"]
                if src or src_type:
                    label = src or src_type
                    if src and src_type and src_type not in src:
                        label = f"{src} ({src_type})"
                    hdr_bits.append(label)
                if date_str:
                    hdr_bits.append(date_str)
                news_lines.append("  " + " | ".join(hdr_bits))
                news_lines.append(self._indent_wrapped(title, width=88, indent="      "))
                if url:
                    news_lines.append(f"      {url}")
                if snippet:
                    news_lines.append(self._indent_wrapped(snippet[:280], width=88, indent="      "))
                news_lines.append("")
        else:
            news_lines.append("  No real-time news items were captured for this run.")
        news_lines.append(major)
        # ── END NEW SECTIONS ─────────────────────────────────────────────

        blocks = {
            "cover": "\n".join([
                major,
                "ESG GREENWASHING RISK ASSESSMENT REPORT",
                major,
                "REPORT HEADER",
                minor,
                f"Company:            {v['company']}",
                f"Ticker:             {v['ticker']}",
                f"Industry:           {v['industry']}",
                claim_line,
                *claim_tail,
                f"Report ID:          {report_id}",
                f"Date:               {date_line}",
                f"Confidence:         {v['confidence_pct']:.1f}% ({v['report_confidence']})",
                f"Version:            {report_version}",
                minor,
            ]),
            "verdict": "\n".join([
                major,
                "VERDICT",
                major,
                "",
                f"  Greenwashing Risk Score:  {gw_score_disp}",
                f"  ESG Score:                {esg_score_disp}",
                f"  ESG Rating:               {v['rating']}",
                f"  Risk Band:                {band_disp}",
                f"  Confidence:               {v['confidence_pct']:.1f}%",
                data_coverage_str,
                f"  Calibration Status:       {cal_status_disp}",
                *([baseline_line] if baseline_line else []),
                *([""] + ["  Score justification:", *[f"  - {line}" for line in verdict_justification]] if verdict_justification else []),
                "",
                "  One-sentence plain-English summary:",
                self._indent_wrapped(summary_sentence, width=76, indent="  "),
                "",
                "  Key findings at a glance:",
                *[self._format_verdict_finding(line) for line in verdict_findings],
                "",
                major,
            ]),
            "section1": "\n".join(self._build_section1_with_limitations(major, section1_text, v, structured)),
            "section_anatomy": "\n".join(section_anatomy),
            "section2": "\n".join(sec2_lines),
            "materiality_profile": "\n".join(materiality_lines),
            "section3": "\n".join(score_header),
            "component_breakdown": "\n".join(component_lines),
            "section6": "\n".join(section6),
            "section4": "\n".join(section4),
            "compliance_full": "\n".join(compliance_lines),
            "enforcement_history": "\n".join(enforcement_lines),
            "section5": "\n".join(section5),
            "section5b": "\n".join(section5b),
            "section7": "\n".join(section7),
            "recent_news": "\n".join(news_lines),
            "section9": "\n".join(section9),
            "section10": "\n".join(section10),
            "audit_metadata": "\n".join(audit_lines),
            "section10b": "\n".join(section10b),
            "section11c": "\n".join(section11c),
            "section11": "\n".join(section11),
            "appendix_a": "\n".join(appendix_a),
            "appendix_b": "\n".join(appendix_b),
            "appendix_c": "\n".join(appendix_c),
            "end": "\n".join([major, "END OF REPORT", major, f"Report ID: {report_id}   Generated: {date_line}   ESGLens v4.0", major]),
        }

        # Logical reading flow: 3 → 3B → 4 → 5A → 5 → 5C → 6 → 7 → 7B → 7C
        # → 8 → 8B → 9 → 9B → 10 → 10B → 11 → 11B → 12 → appendices
        ordered_keys = [
            "cover", "verdict", "section1", "section_anatomy", "section2",
            "materiality_profile", "section3", "component_breakdown",
            "section6", "section4", "compliance_full", "enforcement_history",
            "section5", "section5b", "section7", "recent_news",
            "section9", "audit_metadata", "section10", "section10b",
            "section11c", "section11", "appendix_a", "appendix_b", "appendix_c", "end",
        ]
        # Drop empty blocks so optional sections (e.g. SECTION 11B Commitment
        # Timeline when no ledger data exists) don't leave a hollow heading.
        ordered_keys = [k for k in ordered_keys if blocks.get(k, "").strip()]
        report = "\n\n".join(blocks[k] for k in ordered_keys)

        if len(report.encode("utf-8")) > 500_000:
            blocks["appendix_c"] = "\n".join([major, "APPENDIX C: EVIDENCE & OFFSET INTEGRITY", major, "[TRUNCATED DUE TO FILE-SIZE CAP]", major])
            report = "\n\n".join(blocks[k] for k in ordered_keys)

        if len(report.encode("utf-8")) > 500_000:
            for k in ["appendix_c", "appendix_b", "appendix_a"]:
                blocks[k] = "\n".join([major, blocks[k].split("\n")[1], major, "[TRUNCATED DUE TO FILE-SIZE CAP]", major])
                report = "\n\n".join(blocks[x] for x in ordered_keys)
                if len(report.encode("utf-8")) <= 500_000:
                    break

        if len(report.encode("utf-8")) > 500_000:
            report = report[:490_000] + "\n\n[TRUNCATED AT 500KB]"

        return report

    # ------------------------------------------------------------------
    # Canonical resolver helpers — called ONCE from _build_structured_report
    # ------------------------------------------------------------------

    def _resolve_contradictions(self, state, risk_results, agents):
        """Single arbitration point for contradiction items and count.
        Returns {"items": [...], "count": int} with deduplication applied.
        """
        items = []
        # Source 1: state["contradiction_results"] (primary)
        contra_state = state.get("contradiction_results", {})
        if isinstance(contra_state, dict):
            raw = contra_state.get("contradictions") or contra_state.get("specific_contradictions") or []
            if isinstance(raw, list):
                items.extend(c for c in raw if isinstance(c, dict))
        # Source 2: riskresults topcontradictions
        if not items:
            top_contra = risk_results.get("topcontradictions", [])
            if isinstance(top_contra, list):
                for c in top_contra:
                    if isinstance(c, dict):
                        items.append({
                            "description": c.get("detail") or c.get("description", ""),
                            "severity": c.get("severity", "HIGH"),
                            "source": c.get("citation") or c.get("source", "risk_scoring"),
                            "year": c.get("year", "N/A"),
                            "confidence": str(c.get("confidence") or "HIGH"),
                        })
        # Source 3: pillarfactors.contradictions (known-case DB entries)
        if not items:
            pf_contras = (risk_results.get("pillarfactors") or {}).get("contradictions", [])
            if isinstance(pf_contras, list):
                for c in pf_contras:
                    if isinstance(c, dict) and str(c.get("severity", "")).upper() in ("HIGH", "MEDIUM"):
                        items.append({
                            "description": str(c.get("description") or c.get("detail") or c.get("text") or "").strip(),
                            "severity": str(c.get("severity", "HIGH")).upper(),
                            "source": str(c.get("source") or c.get("citation") or "Known verified case"),
                            "year": c.get("year", "N/A"),
                            "confidence": str(c.get("confidence") or "HIGH"),
                        })
        # Source 4: agent_outputs contradiction_analysis
        if not items:
            contra_agent = agents.get("contradiction_analysis", {})
            contra_output = contra_agent.get("output", {}) if isinstance(contra_agent, dict) else {}
            if isinstance(contra_output, dict):
                raw = contra_output.get("contradictions") or contra_output.get("specific_contradictions") or []
                if isinstance(raw, list):
                    items.extend(c for c in raw if isinstance(c, dict))
        # Source 5: adversarial_audit key_findings fallback
        if not items:
            audit = risk_results.get("adversarial_audit") or state.get("adversarial_audit") or {}
            if isinstance(audit, dict):
                audit_count = int(audit.get("contradictions_count", 0) or 0)
                if audit_count > 0:
                    findings = (risk_results.get("key_findings")
                                or (risk_results.get("verdict") or {}).get("key_findings")
                                or state.get("key_findings") or [])
                    if isinstance(findings, list):
                        for f in findings:
                            if isinstance(f, dict) and str(f.get("level", "")).upper() == "HIGH":
                                items.append({
                                    "description": f.get("text") or f.get("finding") or str(f),
                                    "severity": "HIGH",
                                    "source": "adversarial_audit_fallback",
                                })
        # Deduplicate by normalized text (canonical — renderer must not re-dedup)
        seen = set()
        deduped = []
        for item in items:
            if not isinstance(item, dict):
                continue
            text_key = str(
                item.get("description") or item.get("text")
                or item.get("contradiction_text") or item.get("detail") or ""
            ).strip().lower()[:120]
            if text_key and text_key not in seen:
                seen.add(text_key)
                deduped.append(item)
            elif not text_key:
                deduped.append(item)
        # Enforce adversarial_audit count as floor
        audit = risk_results.get("adversarial_audit") or state.get("adversarial_audit") or {}
        audit_count = int(audit.get("contradictions_count", 0) or 0) if isinstance(audit, dict) else 0
        return {"items": deduped, "count": max(len(deduped), audit_count)}

    def _resolve_decision_state(self, risk_results):
        """Single arbitration point for abstention, decision status, and score disclaimer.
        Rule: abstention_reason is blanked when abstain_recommended is False.
        """
        abstain = bool(risk_results.get("abstainrecommended", risk_results.get("abstain_recommended", False)))
        decision_status = str(risk_results.get("decision_status", "SCORED") or "SCORED").strip()
        score_disclaimer = str(risk_results.get("score_disclaimer", "") or "").strip()
        if abstain:
            reason = str(
                risk_results.get("abstentionreason")
                or risk_results.get("abstention_reason")
                or "Evidence quality checks triggered an abstention recommendation."
            ).strip()
        else:
            reason = ""
        return {
            "abstain_recommended": abstain,
            "decision_status": decision_status,
            "abstention_reason": reason,
            "score_disclaimer": score_disclaimer,
        }

    def _resolve_score_basis(self, scores, risk_results):
        """Single arbitration point for ESG display score, rating basis, GW raw/calibrated, band."""
        pillar_scores = scores.get("pillar_scores", {}) if isinstance(scores.get("pillar_scores"), dict) else {}
        display_esg = pillar_scores.get("displayesgscore")
        if display_esg is None:
            display_esg = pillar_scores.get("overall_esg_score")
        if display_esg is None:
            display_esg = scores.get("esg_score")
        if display_esg is None:
            display_esg = risk_results.get("esg_score")
        display_esg = float(display_esg) if isinstance(display_esg, (int, float)) else 50.0
        rating = str(
            scores.get("esg_rating") or risk_results.get("ratinggrade")
            or risk_results.get("rating_grade") or self._rating_from_esg_score(display_esg)
        )
        gw_calibrated = float(scores.get("greenwashingriskscore", 55.0))
        gw_raw = float(
            risk_results.get("greenwashingscoreraw")
            or risk_results.get("greenwashing_score_raw")
            or gw_calibrated
        )
        band = str(
            scores.get("risk_level") or risk_results.get("risklevel")
            or risk_results.get("risk_level") or self._risk_band(gw_calibrated)
        ).upper()
        if rating.upper() in {"CCC", "C"} and band in {"LOW", "MODERATE"}:
            band = "HIGH"
        return {
            "display_esg_score": round(display_esg, 1),
            "rating_basis_score": round(display_esg, 1),
            "rating": rating,
            "band": band,
            "gw_raw": round(gw_raw, 1),
            "gw_calibrated": round(gw_calibrated, 1),
            "gw_delta": round(gw_calibrated - gw_raw, 1),
        }

    def _resolve_benchmark_provenance(self, risk_results, state):
        """Single arbitration point for WBA/WRI benchmark provenance.
        Rule: wba_adjustment_allowed is False when wba_indicator_count == 0.
        """
        ext_benchmarks = risk_results.get("external_benchmarks", {})
        if not isinstance(ext_benchmarks, dict):
            ext_benchmarks = {}
        ext_state = state.get("external_esg_data", {})
        if not isinstance(ext_state, dict):
            ext_state = {}
        merged = dict(ext_state)
        merged.update(ext_benchmarks)
        wba_indicator_count = int(merged.get("wba_indicator_count", 0) or 0)
        wba_adjustment_allowed = wba_indicator_count > 0
        sources = merged.get("sources", {}) if isinstance(merged.get("sources"), dict) else {}
        ext_scores = merged.get("scores", {}) if isinstance(merged.get("scores"), dict) else {}
        pillar_scores = risk_results.get("pillarscores") or risk_results.get("pillar_scores") or {}
        adjustments = pillar_scores.get("external_benchmark_adjustments", []) if isinstance(pillar_scores, dict) else []
        if not isinstance(adjustments, list):
            adjustments = []
        if not wba_adjustment_allowed:
            adjustments = [a for a in adjustments if isinstance(a, dict) and a.get("source") != "WBA"]
        return {
            "enabled": bool(merged.get("enabled") or sources),
            "used": bool(pillar_scores.get("external_benchmarks_used", False)) if isinstance(pillar_scores, dict) else False,
            "sources": sources,
            "scores": ext_scores,
            "adjustments": adjustments,
            "wba_company_name": merged.get("wba_company_name"),
            "wba_indicator_count": wba_indicator_count,
            "wba_data_year": merged.get("wba_data_year"),
            "wba_adjustment_allowed": wba_adjustment_allowed,
            "error": merged.get("error"),
        }

    def _build_section1_with_limitations(self, major: str, section1_text: str, v: Dict[str, Any], structured: Dict[str, Any]) -> List[str]:
        """Build Section 3 (Executive Summary) with critical caveats up front.

        Previously, limitations were buried in Section 11 — a reader skimming
        the executive summary couldn't tell that calibration was provisional,
        peer data was estimated, or Scope 3 boundary was partial. This
        surfaces the top 3-5 most material caveats into the headline section
        so trust gaps are visible immediately.
        """
        lines: List[str] = [major, "SECTION 3: EXECUTIVE SUMMARY", major]
        lines.append(self._wrap_paragraph(section1_text, width=80))
        lines.append("")

        caveats: List[str] = []

        # Calibration caveat
        cal = structured.get("calibration") or {}
        if isinstance(cal, dict):
            cal_status = str(cal.get("calibration_status", "")).upper()
            n_cases = cal.get("dataset_size") or cal.get("sample_size")
            if cal_status == "MISCALIBRATED":
                caveats.append(
                    "CALIBRATION: System score for this company falls outside the expected "
                    "range from the curated ground-truth registry. Headline numbers have been "
                    "adjusted via known-case floor; treat as provisional."
                )
            elif cal_status in {"PROVISIONAL", "VERY_LOW", "NEEDS_REVIEW"} or (
                isinstance(n_cases, int) and n_cases < 10
            ):
                caveats.append(
                    f"CALIBRATION: Provisional (n={n_cases or '<10'}) — calibration sample is small; "
                    f"score margins are wider than reported confidence suggests."
                )

        # Peer comparison caveat
        peers = structured.get("peers") or {}
        if isinstance(peers, dict):
            real_count = peers.get("real_peer_count")
            fallback_used = peers.get("fallback_used")
            if real_count == 0 or fallback_used or peers.get("data_source") in {"placeholder", "cached_fallback"}:
                caveats.append(
                    "PEER BENCHMARKING: No live peer data retrieved; comparison uses cached/"
                    "estimated peers. Industry-relative ranking is indicative only."
                )

        # Scope 3 boundary caveat
        carbon = v.get("carbon") or {}
        s3 = (carbon.get("emissions") or {}).get("scope3") if isinstance(carbon, dict) else {}
        if isinstance(s3, dict):
            boundary = s3.get("boundary") or {}
            if isinstance(boundary, dict):
                bcls = str(boundary.get("boundary") or "").upper()
                if bcls in {"PARTIAL_SCOPE3", "NARROW"}:
                    caveats.append(
                        f"CARBON BOUNDARY: Reported Scope 3 is classified {bcls} — major "
                        f"GHG Protocol categories likely disclosed outside the headline number. "
                        f"See Section 8 boundary breakdown."
                    )

        # Known-case override caveat — read from the verdict_generation
        # agent_output (carries `known_case_override` dict when applied).
        agents = structured.get("agents") or {}
        if isinstance(agents, dict):
            verdict_ao = agents.get("verdict_generation") or {}
            verdict_out = verdict_ao.get("output") if isinstance(verdict_ao, dict) else {}
            if isinstance(verdict_out, dict):
                kco = verdict_out.get("known_case_override") or {}
                if isinstance(kco, dict) and kco.get("applied"):
                    raw_gw = kco.get("raw_gw_score")
                    floor_gw = kco.get("floor_gw_score")
                    case_id = kco.get("case_id", "")
                    caveats.append(
                        f"GROUND TRUTH OVERRIDE: Headline scores adjusted (case {case_id}) — "
                        f"raw GW {raw_gw} → floor {floor_gw}/100. The system's pre-override "
                        f"verdict differed from the documented regulatory record; raw values "
                        f"in Section 10."
                    )

        # Confidence ceiling caveat
        conf_pct = v.get("confidence_pct") or 0
        if conf_pct < 70:
            caveats.append(
                f"CONFIDENCE: Headline confidence is {conf_pct:.0f}% — below the 70% threshold "
                f"for high-trust decisions. Treat findings as directional."
            )

        if caveats:
            lines.append("CRITICAL CAVEATS — read before relying on these numbers:")
            for i, cv in enumerate(caveats, 1):
                lines.append(self._wrap_paragraph(f"  {i}. {cv}", width=80))
            lines.append("")
        lines.append(major)
        return lines

    def _resolve_calibration_render_status(self, calibration):
        """Returns one of: 'calibrated', 'sector_mismatch', 'uncalibrated'"""
        if not isinstance(calibration, dict):
            return "uncalibrated"
        cal_status = calibration.get("calibration_status", "NOT_AVAILABLE")
        if cal_status == "NOT_AVAILABLE":
            return "uncalibrated"
        dataset_size = calibration.get("dataset_size")
        if not isinstance(dataset_size, int) or dataset_size < 5:
            return "uncalibrated"
        no_industry_match = bool(calibration.get("no_industry_match"))
        fallback_used = bool(calibration.get("fallback_used"))
        if no_industry_match or (fallback_used and calibration.get("fallback_reason") == "NO_PEER_CASES"):
            return "sector_mismatch"
        return "calibrated"


    # ------------------------------------------------------------------
    # Structured representation builders
    # ------------------------------------------------------------------

    def _build_structured_report(self, state: Dict[str, Any]) -> Dict[str, Any]:
        analysis_timestamp = datetime.now(timezone.utc)

        scores = self._extract_core_scoring(state)
        company = str(state.get("company") or "Unknown").strip() or "Unknown"
        raw_industry = str(scores.get("industry") or state.get("industry") or "Unknown").strip() or "Unknown"
        industry = normalize_industry_label(raw_industry)
        claim = str(state.get("claim") or "No claim provided").strip() or "No claim provided"

        evidence_struct = self._extract_evidence_citations(state)
        pillars = self._build_pillar_factor_breakdown(scores, evidence_struct, state)
        agents = self._extract_agent_findings(state)
        peers = self._extract_peer_context(state)
        calibration = self._extract_calibration_info(
            scores,
            company_industry=industry,
            claim_text=claim,
        )
        limitations = self._infer_limitations(state, evidence_struct, peers, calibration, agents)

        report_id = f"{analysis_timestamp.strftime('%Y%m%d-%H%M%S')}-{company.upper()[:4]}"

        # ── Canonical resolvers (single arbitration point) ────────────────
        risk_results = scores.get("raw", {}) if isinstance(scores.get("raw"), dict) else {}

        resolved_contradictions = self._resolve_contradictions(state, risk_results, agents)
        resolved_decision = self._resolve_decision_state(risk_results)
        resolved_scores = self._resolve_score_basis(scores, risk_results)
        resolved_benchmarks = self._resolve_benchmark_provenance(risk_results, state)
        calibration_render_status = self._resolve_calibration_render_status(calibration)

        # Store resolved contradictions in evidence for downstream consumption
        evidence_struct["contradiction_items_resolved"] = resolved_contradictions["items"]
        evidence_struct["contradictions_count_resolved"] = resolved_contradictions["count"]

        # Store calibration render status
        calibration["render_status"] = calibration_render_status
        # ── End canonical resolvers ───────────────────────────────────────

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
            "decision": resolved_decision,
            "benchmarks": resolved_benchmarks,
            "report_consistency": {
                "final_contradiction_count": resolved_contradictions["count"],
                "final_gw_raw": resolved_scores["gw_raw"],
                "final_gw_calibrated": resolved_scores["gw_calibrated"],
                "final_gw_delta": resolved_scores["gw_delta"],
                "final_esg_display": resolved_scores["display_esg_score"],
                "final_rating": resolved_scores["rating"],
                "final_rating_basis": resolved_scores["rating_basis_score"],
                "final_band": resolved_scores["band"],
                "final_decision_status": resolved_decision["decision_status"],
                "final_abstain_recommended": resolved_decision["abstain_recommended"],
                "final_calibration_label": calibration_render_status,
                "wba_adjustment_allowed": resolved_benchmarks["wba_adjustment_allowed"],
            },
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
        if isinstance(state.get("riskresults"), dict):
            risk_scorer_result = state.get("riskresults")

        pillar_scores = risk_scorer_result.get("pillarscores") or risk_scorer_result.get("pillar_scores") or {}
        if not isinstance(pillar_scores, dict):
            pillar_scores = {}

        esg_rating = (
            state.get("rating_grade")
            or risk_scorer_result.get("ratinggrade")
            or risk_scorer_result.get("rating_grade")
            or "BBB"
        )

        risk_level = (
            state.get("risk_level")
            or risk_scorer_result.get("risklevel")
            or risk_scorer_result.get("risk_level")
            or "MODERATE"
        )

        greenwashingriskscore = risk_scorer_result.get("greenwashingriskscore")
        if not isinstance(greenwashingriskscore, (int, float)):
            esg_score = risk_scorer_result.get("esg_score")
            if isinstance(esg_score, (int, float)):
                greenwashingriskscore = max(0.0, min(100.0, 100.0 - float(esg_score)))
            else:
                defaults = {"LOW": 25.0, "MODERATE": 55.0, "HIGH": 80.0}
                greenwashingriskscore = defaults.get(str(risk_level).upper(), 55.0)

        _raw_conf = state.get("confidence")
        state_confidence = float(_raw_conf) if isinstance(_raw_conf, (int, float)) else 0.0  # FIX: guard string confidence

        scorer_confidence_level = risk_scorer_result.get("confidence_level")
        scorer_confidence = (
            float(scorer_confidence_level) / 100.0
            if isinstance(scorer_confidence_level, (int, float))
            else 0.0
        )
        if state_confidence > 0 and scorer_confidence > 0:
            confidence = min(state_confidence, scorer_confidence)
        else:
            confidence = state_confidence or scorer_confidence

        component_scores = risk_scorer_result.get("component_scores") or {}
        if not isinstance(component_scores, dict):
            component_scores = {}

        # Preserve additional scorer outputs for explainability and report professionalism.
        esg_score = risk_scorer_result.get("esg_score")
        if esg_score is None and isinstance(pillar_scores, dict):
            esg_score = pillar_scores.get("overall_esg_score")

        explainability_top = risk_scorer_result.get("explainability_top_3_reasons") or []
        if not isinstance(explainability_top, list):
            explainability_top = []

        confidence_level = risk_scorer_result.get("confidence_level")
        industry = risk_scorer_result.get("industry") or state.get("industry")

        return {
            "esg_rating": esg_rating,
            "risk_level": risk_level,
            "greenwashingriskscore": float(greenwashingriskscore),
            "confidence": confidence,
            "confidence_level": confidence_level,
            "industry": industry,
            "esg_score": esg_score,
            "pillar_scores": pillar_scores,
            "component_scores": component_scores,
            "explainability_top_3_reasons": explainability_top,
            "esg_score_lineage": state.get("esg_score_lineage", {}),
            "raw": risk_scorer_result,
        }

    def _parse_unified_evidence(self, state: Dict[str, Any]) -> List[EvidenceItem]:
        # ── Key-name audit: detect novel upstream keys that we'd silently miss ──
        _KNOWN_EVIDENCE_KEYS = {
            "evidence", "contradiction_results", "contradictions",
            "unified_evidence", "evidence_items",
        }
        state_evidence_keys = {
            k for k in state.keys()
            if "evid" in k.lower() or "contra" in k.lower()
        }
        novel_keys = state_evidence_keys - _KNOWN_EVIDENCE_KEYS
        if novel_keys:
            logger.warning(
                f"Novel evidence-related state keys detected: {novel_keys}. "
                f"Check if they should be consolidated into unified_evidence."
            )

        unified: List[EvidenceItem] = []
        raw_evidence = state.get("evidence") or []
        if not isinstance(raw_evidence, list):
            raw_evidence = []

        company = str(state.get("company") or "").strip()
        claim = str(state.get("claim") or "").strip()
        filtered_ev = self._filter_evidence_items(raw_evidence, company, claim)

        for item in filtered_ev:
            if not isinstance(item, dict):
                continue

            text = item.get("text") or item.get("description") or item.get("content") or ""
            source = item.get("source") or item.get("domain") or "Unknown"
            url = item.get("url")
            year = item.get("year")
            origin = item.get("origin")

            rel = str(item.get("relationship_to_claim") or "Neutral").strip().lower()
            role = "Neutral"
            if "support" in rel: role = "Supports"
            elif "contradict" in rel: role = "Contradicts"
            elif "mixed" in rel: role = "Mixed"

            sev_str = str(item.get("severity") or "").upper()
            severity = sev_str if sev_str in ["HIGH", "MEDIUM", "LOW"] else None

            try:
                unified.append(EvidenceItem(
                    role=role, severity=severity, text=text,
                    source=source, url=url, year=str(year) if year is not None else None, origin=origin
                ))
            except ValidationError as e:
                logger.warning(
                    f"EvidenceItem validation failed for evidence item — dropped. "
                    f"Raw keys: {list(item.keys())}. Error: {e}"
                )

        # ── Parse contradiction lists specifically ──
        contradictions = []
        contra_out = state.get("contradiction_results") or {}
        if isinstance(contra_out, dict):
            contradictions = (
                contra_out.get("contradictions")
                or contra_out.get("specific_contradictions")
                or []
            )
        if not isinstance(contradictions, list):
            contradictions = []

        for item in contradictions:
            if not isinstance(item, dict):
                continue
            text = item.get("contradiction_text") or item.get("description") or item.get("text") or ""
            source = item.get("source") or "Contradiction Analyzer"
            url = item.get("url")
            year = item.get("year")
            origin = "contradiction_analysis"

            sev_str = str(item.get("severity") or "HIGH").upper()
            severity = sev_str if sev_str in ["HIGH", "MEDIUM", "LOW"] else "HIGH"

            try:
                unified.append(EvidenceItem(
                    role="Contradicts", severity=severity, text=text,
                    source=source, url=url, year=str(year) if year is not None else None, origin=origin
                ))
            except ValidationError as e:
                logger.warning(
                    f"EvidenceItem validation failed for contradiction item — dropped. "
                    f"Raw keys: {list(item.keys())}. Error: {e}"
                )

        return unified

    def _count_evidence_roles(self, unified_evidence: List[EvidenceItem]) -> EvidenceRoleCount:
        count = EvidenceRoleCount()
        for ev in unified_evidence:
            if ev.role == "Supports": count.supports += 1
            elif ev.role == "Contradicts": count.contradicts += 1
            elif ev.role == "Neutral": count.neutral += 1
            elif ev.role == "Mixed": count.mixed += 1
        return count

    def _extract_evidence_citations(self, state: Dict[str, Any]) -> Dict[str, Any]:
        evidence = state.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []

        company = str(state.get("company") or "").strip()
        claim = str(state.get("claim") or "").strip()
        evidence = self._filter_evidence_items(evidence, company, claim)

        by_url: Dict[str, Dict[str, Any]] = {}
        for idx, item in enumerate(evidence, start=1):
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            title = (item.get("title") or item.get("source") or "Unknown source").strip() or "Unknown source"
            date = (item.get("date") or "").strip()
            source_name = (item.get("source") or item.get("domain") or "").strip()
            if not source_name:
                source_name = parse_source_name(url) if url else "General Web / Other"
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

        # Inject known-case citations using explicit source names from matched records.
        contradiction_output: Dict[str, Any] = {}
        contradiction_state = state.get("contradiction_results")
        if isinstance(contradiction_state, dict):
            contradiction_output = contradiction_state
        else:
            for out in reversed(state.get("agent_outputs", []) or []):
                if not isinstance(out, dict) or out.get("agent") != "contradiction_analysis":
                    continue
                candidate = out.get("output")
                if isinstance(candidate, dict):
                    contradiction_output = candidate
                    break

        known_case_matches = contradiction_output.get("known_case_matches", []) if isinstance(contradiction_output, dict) else []
        if isinstance(known_case_matches, list):
            for known_case in known_case_matches:
                if not isinstance(known_case, dict):
                    continue
                source_name = known_case.get("source", "Known Cases Database")
                source_name = str(source_name).strip() or "Known Cases Database"
                source_url = str(known_case.get("source_url") or known_case.get("url") or "").strip()
                title = str(
                    known_case.get("description")
                    or known_case.get("contradiction_text")
                    or known_case.get("title")
                    or "Known greenwashing case"
                ).strip()
                if not title:
                    title = "Known greenwashing case"
                tier, verifiable = self._compute_reliability_tier(source_url, "regulatory")
                citations.append(
                    {
                        "id": len(citations) + 1,
                        "source_name": source_name,
                        "title": title,
                        "url": source_url or "[NO DIRECT URL]",
                        "date": str(known_case.get("year") or known_case.get("date") or "[DATE UNKNOWN]"),
                        "claim_support": "contradicts",
                        "reliability_tier": tier,
                        "verifiable": verifiable,
                        "avg_weight": 0.8,
                        "freshest_days": None,
                        "score_impact": "known-case contradiction",
                    }
                )

        citations.sort(key=lambda c: (not c["verifiable"], c["reliability_tier"], c["id"]))

        total = len(citations)
        verifiable_count = len([c for c in citations if c["verifiable"]])

        return {
            "citations": citations,
            "total_citations": total,
            "verifiable_citations": verifiable_count,
        }

    def _filter_evidence_items(
        self,
        evidence: List[Dict[str, Any]],
        company: str,
        claim: str,
    ) -> List[Dict[str, Any]]:
        """Drop clearly irrelevant evidence items before report rendering."""
        if not evidence or not company:
            return evidence

        company_lower = company.lower()
        aliases = {
            company_lower,
            company_lower.replace(" plc", "").strip(),
            company_lower.replace(" ltd", "").strip(),
            company_lower.replace(" limited", "").strip(),
            company_lower.replace(" corporation", "").strip(),
            company_lower.replace(" corp", "").strip(),
            company_lower.replace(" inc", "").strip(),
            company_lower.replace(" group", "").strip(),
        }
        aliases.update(
            t for t in company_lower.replace("-", " ").replace("&", " ").split() if len(t) > 2
        )

        claim_keywords = set(re.findall(r"[a-zA-Z][a-zA-Z0-9-]+", claim.lower()))

        filtered: List[Dict[str, Any]] = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            combined = " ".join(
                str(item.get(k, ""))
                for k in ("title", "snippet", "content", "url", "source", "source_name", "domain")
            ).lower()

            mentions_company = any(alias and alias in combined for alias in aliases)
            claim_hits = sum(1 for kw in claim_keywords if len(kw) > 3 and kw in combined)

            if mentions_company or claim_hits >= 3:
                filtered.append(item)

        return filtered or evidence

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
        risk_results = state.get("riskresults") or scores.get("raw") or {}
        pillar_factors = risk_results.get("pillarfactors") if isinstance(risk_results, dict) else {}
        if not isinstance(pillar_factors, dict):
            pillar_factors = {}

        if not pillar_factors:
            pillar_factors = self._extract_pillar_factors_from_logs(state)

        def _normalize_factor_rows(raw_pillar_obj: Any) -> List[Dict[str, Any]]:
            """Normalize old/new pillar formats into report factor rows.

            Supports:
            1) Legacy list of factor dicts
            2) Structured pillar dict with sub_indicators
            """
            normalized: List[Dict[str, Any]] = []

            # Legacy shape: pillar_factors[pillar] is already a list of factor dicts.
            if isinstance(raw_pillar_obj, list):
                for row in raw_pillar_obj:
                    if not isinstance(row, dict):
                        continue
                    factor_name = row.get("factor") or row.get("name") or "Unknown factor"
                    confidence = str(row.get("confidence") or ("High" if row.get("verified") else "Unknown"))
                    normalized.append(
                        {
                            "factor": factor_name,
                            "raw_signal": row.get("raw_signal", "N/A"),
                            "source": row.get("source") or row.get("data_source") or "Unknown",
                            "weight": row.get("weight"),
                            "points_contributed": row.get("points_contributed"),
                            "confidence": confidence,
                        }
                    )
                return normalized

            # New shape: pillar_factors[pillar] is a dict with sub_indicators.
            if not isinstance(raw_pillar_obj, dict):
                return normalized

            sub_indicators = raw_pillar_obj.get("sub_indicators") or []
            if not isinstance(sub_indicators, list):
                sub_indicators = []

            for sub in sub_indicators:
                if not isinstance(sub, dict):
                    continue

                sub_score = sub.get("score")
                weight = sub.get("weight")
                points_contributed = None
                if isinstance(sub_score, (int, float)) and isinstance(weight, (int, float)):
                    points_contributed = round(float(sub_score) * float(weight), 2)

                raw_signal = sub.get("raw_value")
                if raw_signal is None and isinstance(sub_score, (int, float)):
                    raw_signal = f"{float(sub_score):.1f}/100"
                if raw_signal is None:
                    raw_signal = "N/A"

                source = sub.get("data_source") or sub.get("source_url") or "Unknown"

                confidence = "Low"
                if sub.get("verified") is True:
                    confidence = "High"
                elif isinstance(sub_score, (int, float)):
                    confidence = "Medium"

                normalized.append(
                    {
                        "factor": sub.get("name") or sub.get("factor") or "Unknown factor",
                        "raw_signal": raw_signal,
                        "source": source,
                        "weight": weight,
                        "points_contributed": points_contributed,
                        "confidence": confidence,
                    }
                )

            return normalized

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
            raw_pillar_obj = pillar_factors.get(key_map.get(name, ""), {})
            state_factors = _normalize_factor_rows(raw_pillar_obj)
            if state_factors:
                for row in state_factors:
                    factor_name = row.get("factor") or "Unknown factor"
                    confidence = str(row.get("confidence") or "Unknown")
                    if confidence.lower() == "low":
                        factor_name = f"{factor_name} [LOW CONFIDENCE]"

                    raw_signal = row.get("raw_signal", "N/A")
                    points_contributed = row.get("points_contributed")
                    if "renewable" in str(factor_name).lower():
                        carbon_results = (
                            state.get("carbon_results")
                            or state.get("carbon_extraction")
                            or {}
                        )
                        renewable_pct = (
                            carbon_results.get("renewable_energy_percentage")
                            or carbon_results.get("renewable_pct")
                            or pillar_factors.get("renewable_energy_pct")
                        )
                        if renewable_pct is None:
                            raw_signal = "NOT DISCLOSED"
                            if not isinstance(points_contributed, (int, float)):
                                points_contributed = 0.0
                        else:
                            raw_signal = f"{renewable_pct}%"

                    factors.append({
                        "factor": factor_name,
                        "raw_signal": raw_signal,
                        "source": row.get("source", "Unknown"),
                        "weight": row.get("weight"),
                        "points_contributed": points_contributed,
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
            return " → ".join(dict.fromkeys(workflow_nodes))

        outputs = [o.get("agent", "") for o in state.get("agent_outputs", []) if isinstance(o, dict)]
        seen = dict.fromkeys(str(a).replace("_", " ").title() for a in outputs if a)
        return " → ".join(seen.keys()) if seen else "Workflow unavailable"

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
            "risk_scoring": "riskresults",
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
            trimmed = first_val[:600]
            suffix = "..." if len(first_val) > 600 else ""
            return f"{agent_name} [{first_key}]: {trimmed}{suffix}"

        return f"{agent_name}: Agent ran successfully. Key metrics: {list(agent_data.keys())}"

    def _score_band_label(self, score: Any) -> str:
        if not isinstance(score, (int, float)):
            return "Data Not Available"
        value = float(score)
        if value >= 70:
            return "High"
        if value >= 45:
            return "Moderate"
        return "Low"

    def _pillar_score_text(self, score: Any, missing: bool = False) -> str:
        if missing or not isinstance(score, (int, float)):
            return "Data Not Available (Limited Disclosure)"
        return f"{float(score):.1f}/100 ({self._score_band_label(score)})"

    def _pillar_sub_indicators(self, block: Any) -> List[Dict[str, Any]]:
        if isinstance(block, list):
            return [row for row in block if isinstance(row, dict)]
        if not isinstance(block, dict):
            return []
        sub = block.get("sub_indicators")
        if isinstance(sub, list):
            return [row for row in sub if isinstance(row, dict)]
        factors = block.get("factors")
        if isinstance(factors, list):
            return [row for row in factors if isinstance(row, dict)]
        return []

    def _limited_disclosure_label(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text or text.upper() in {"N/A", "NA", "NONE", "NULL", "0.0"}:
            return "Limited Disclosure"
        clean = self._clean_executive_text(text, max_len=40)
        return clean or "Limited Disclosure"

    def _factor_data_quality_label(self, factor: Dict[str, Any], scored: bool) -> str:
        if not scored:
            return "Limited Disclosure"
        text = " ".join(
            str(factor.get(key) or "")
            for key in ["data_quality", "quality", "confidence", "source", "data_source"]
        ).lower()
        if factor.get("estimated") or factor.get("low_confidence") or "estimated" in text:
            return "Estimated"
        if any(token in text for token in ["verified", "assured", "regulatory", "cdp", "audited"]):
            return "Verified"
        if "low" in text or "limited" in text:
            return "Limited Disclosure"
        return "Verified" if factor.get("verifiable") else "Estimated"

    def _pillar_driver_terms(self, pillar_name: str, block: Any, limit: int = 2) -> List[str]:
        factors = self._pillar_sub_indicators(block)
        scored: List[Tuple[float, str]] = []
        missing: List[str] = []
        for factor in factors:
            name = self._clean_executive_text(factor.get("factor") or factor.get("name"), max_len=50)
            if not name:
                continue
            raw = factor.get("raw_signal_normalized")
            if not isinstance(raw, (int, float)):
                raw = factor.get("score") if isinstance(factor.get("score"), (int, float)) else None
            if isinstance(raw, (int, float)):
                scored.append((float(raw), name.lower()))
            else:
                missing.append(name.lower())

        if missing:
            return [f"limited disclosure for {item}" for item in missing[:limit]]
        if scored:
            scored.sort(key=lambda item: item[0])
            return [item[1] for item in scored[:limit]]

        defaults = {
            "Environmental": ["carbon intensity", "transition progress"],
            "Social": ["labor and stakeholder disclosures"],
            "Governance": ["oversight and transparency"],
        }
        return defaults.get(pillar_name, ["available factor evidence"])[:limit]

    def _pillar_insight_line(self, pillar_name: str, score: Any, block: Any) -> str:
        drivers = self._join_business_list(self._pillar_driver_terms(pillar_name, block, limit=2))
        label = self._score_band_label(score).lower()
        if label == "data not available":
            return f"{pillar_name}: limited disclosure prevents a decision-grade pillar interpretation."
        return f"{pillar_name}: {label} score driven by {drivers}."

    def _build_score_derivation_summary(
        self,
        esg_performance_label: str,
        pillars: Dict[str, Dict[str, Any]],
        strongest_pillar: str,
        weakest_pillar: str,
    ) -> str:
        weakest = pillars.get(weakest_pillar, {})
        strongest = pillars.get(strongest_pillar, {})
        weakest_drivers = self._join_business_list(self._pillar_driver_terms(weakest_pillar, weakest.get("block"), limit=2))
        strongest_drivers = self._join_business_list(self._pillar_driver_terms(strongest_pillar, strongest.get("block"), limit=2))
        other_pillars = [name for name in ["Environmental", "Social", "Governance"] if name not in {strongest_pillar, weakest_pillar}]
        other_text = " and ".join(other_pillars) if other_pillars else "remaining pillars"
        performance = {"Low": "weak", "Moderate": "moderate", "High": "strong"}.get(
            str(esg_performance_label),
            str(esg_performance_label).lower(),
        )
        return (
            f"Overall ESG performance is {performance}, driven by {weakest_drivers}. "
            f"{strongest_pillar} is the strongest pillar due to {strongest_drivers}, while "
            f"{weakest_pillar} is weakest due to {weakest_drivers}. {other_text} scores reflect "
            "the available disclosure quality and factor-level evidence."
        )

    def _add_risk_driver(
        self,
        drivers: List[Dict[str, str]],
        title: str,
        explanation: str,
        impact: str,
        direction: str,
        priority: int,
    ) -> None:
        clean_title = self._clean_executive_text(title, max_len=60)
        clean_explanation = self._clean_executive_text(explanation, max_len=170)
        if not clean_title or not clean_explanation:
            return
        direction = direction if direction in {"increases risk", "decreases risk"} else "increases risk"
        impact = impact if impact in {"HIGH", "MEDIUM", "LOW"} else "MEDIUM"
        key = re.sub(r"[^a-z0-9]+", " ", clean_title.lower()).strip()
        if any(re.sub(r"[^a-z0-9]+", " ", d["title"].lower()).strip() == key for d in drivers):
            return
        drivers.append({
            "title": clean_title,
            "explanation": clean_explanation,
            "impact": impact,
            "direction": direction,
            "priority": priority,
        })

    def _scope3_category_count(self, scope3: Any) -> int:
        if not isinstance(scope3, dict):
            return 0
        categories = scope3.get("categories")
        if isinstance(categories, dict):
            return len(categories)
        if isinstance(categories, list):
            return len(categories)
        return 0

    def _build_key_risk_drivers(self, context: Dict[str, Any], state: Dict[str, Any], scope3: Any) -> List[Dict[str, str]]:
        drivers: List[Dict[str, str]] = []

        contradiction_count = int(self._safe_float(context.get("contradiction_count"), 0.0))
        if contradiction_count > 0:
            self._add_risk_driver(
                drivers,
                "Claim-Evidence Contradictions",
                f"{contradiction_count} contradiction signal(s) indicate that public claims and retrieved evidence may not be fully aligned.",
                "HIGH",
                "increases risk",
                10,
            )

        reg_gap_names = self._regulatory_gap_names(context.get("regulatory", {}) if isinstance(context.get("regulatory"), dict) else {})
        reg_gap_count = len(context.get("reg_gaps", []) if isinstance(context.get("reg_gaps"), list) else [])
        compliance_score = safe_get(context, "regulatory", "compliance_score", default={})
        if isinstance(compliance_score, dict):
            reg_gap_count = max(reg_gap_count, int(self._safe_float(compliance_score.get("gaps"), 0.0)))
        if reg_gap_count > 0 or reg_gap_names:
            frameworks = self._join_business_list(reg_gap_names[:3]) if reg_gap_names else f"{reg_gap_count} framework gap(s)"
            self._add_risk_driver(
                drivers,
                "Regulatory Alignment Gaps",
                f"Detected gaps across {frameworks} weaken assurance that the claim meets expected regulatory or voluntary standards.",
                "HIGH" if reg_gap_count >= 2 else "MEDIUM",
                "increases risk",
                20,
            )

        carbon = context.get("carbon", {}) if isinstance(context.get("carbon"), dict) else {}
        carbon_pathway = state.get("carbon_pathway_analysis") if isinstance(state.get("carbon_pathway_analysis"), dict) else {}
        if not carbon_pathway:
            carbon_pathway = safe_get(context, "feature_signals", "carbon_pathway", default={})
        pathway_text = " ".join(str(carbon_pathway.get(k) or "") for k in ["assessment", "scope3_feasibility", "pathway_status", "status"]).lower() if isinstance(carbon_pathway, dict) else ""
        pathway_negative = any(token in pathway_text for token in ["misalign", "not feasible", "insufficient", "behind", "off track", "unlikely"])
        if pathway_negative:
            self._add_risk_driver(
                drivers,
                "Carbon Pathway Misalignment",
                "Available pathway evidence suggests the emissions trajectory may not support the stated climate target.",
                "HIGH",
                "increases risk",
                30,
            )

        scope3_count = self._scope3_category_count(scope3)
        if self._carbon_has_scope3_gap(carbon, context.get("claim", "")) or scope3_count == 0:
            self._add_risk_driver(
                drivers,
                "Scope 3 Disclosure Gap",
                "Value-chain emissions coverage is incomplete, making it difficult to verify whether the target covers the company’s material footprint.",
                "MEDIUM",
                "increases risk",
                40,
            )

        sbti_status = str(carbon.get("science_based_target") or carbon.get("sbti_status") or "").lower()
        if sbti_status in {"false", "no", "0", "not submitted", "not validated", "none"}:
            self._add_risk_driver(
                drivers,
                "Target Validation Gap",
                "No validated science-based target was found, reducing external assurance over the transition claim.",
                "MEDIUM",
                "increases risk",
                45,
            )
        elif sbti_status in {"true", "yes", "1", "validated"}:
            self._add_risk_driver(
                drivers,
                "Science-Based Target Validation",
                "Validated target evidence provides external support for the company’s transition claim.",
                "MEDIUM",
                "decreases risk",
                80,
            )

        pillar_scores = safe_get(context, "scores", "pillar_scores", default={})
        governance_score = pillar_scores.get("governance_score") if isinstance(pillar_scores, dict) else None
        if isinstance(governance_score, (int, float)) and governance_score < 45:
            self._add_risk_driver(
                drivers,
                "Governance and Oversight Weakness",
                "Low governance scoring points to gaps in oversight, transparency, policies, or accountability mechanisms.",
                "MEDIUM",
                "increases risk",
                50,
            )

        citations = context.get("citations", []) if isinstance(context.get("citations"), list) else []
        premium_count = int(self._safe_float(context.get("premium_count"), 0.0))
        if len(citations) < 5 or premium_count == 0:
            self._add_risk_driver(
                drivers,
                "Limited Independent Evidence",
                "The evidence base lacks sufficient independent or high-assurance sources, so claim verification remains less reliable.",
                "MEDIUM",
                "increases risk",
                60,
            )

        if not drivers:
            self._add_risk_driver(
                drivers,
                "Evidence Alignment",
                "No material contradiction, regulatory gap, or carbon pathway concern was detected in the available evidence.",
                "LOW",
                "decreases risk",
                90,
            )

        impact_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        drivers.sort(key=lambda d: (impact_rank.get(d["impact"], 1), d["priority"]))
        return [{k: v for k, v in driver.items() if k != "priority"} for driver in drivers[:5]]

    def _risk_driver_summary(self, drivers: List[Dict[str, str]]) -> str:
        increasing = [d["title"].lower() for d in drivers if d.get("direction") == "increases risk"]
        if increasing:
            return f"Risk is primarily driven by {self._join_business_list(increasing[:3])}."
        decreasing = [d["title"].lower() for d in drivers if d.get("direction") == "decreases risk"]
        return f"Risk is moderated by {self._join_business_list(decreasing[:3])}."

    def _curate_contradictions(self, unified_evidence: List['EvidenceItem'], claim: str = "") -> List[Dict[str, str]]:
        if not unified_evidence:
            return []

        claim_terms = {
            token for token in re.findall(r"[a-z][a-z0-9-]{3,}", str(claim or "").lower())
            if token not in {"with", "from", "that", "this", "will", "into", "across", "company", "claim"}
        }
        curated: List[Dict[str, str]] = []
        seen: Set[str] = set()
        for item in unified_evidence:
            if item.role != "Contradicts":
                continue
            severity = str(item.severity or "MEDIUM").upper()
            if severity not in {"HIGH", "MEDIUM"}:
                continue

            statement = self._clean_executive_text(item.text, max_len=190)
            if not statement or not self._is_human_readable_text(statement):
                continue
            statement_l = statement.lower()
            weak_markers = [
                "generic", "not enough information", "unclear", "possibly",
                "may be unrelated", "official source located",
                "no hard contradiction rule",  # internal placeholder text — never decision-relevant
                "current esg balance",         # placeholder telemetry from rule scoring
            ]
            if any(marker in statement_l for marker in weak_markers):
                continue
            if claim_terms and not any(term in statement_l for term in claim_terms):
                evidence_text = f"{item.text} {item.source}".lower()
                if not any(term in evidence_text for term in claim_terms):
                    continue

            source = self._clean_executive_text(item.source, max_len=45) or "Evidence review"
            confidence_txt = "Not stated"  # EvidenceItem does not have confidence currently
            raw_year = str(item.year or "N/A").strip()
            year_match = re.search(r"(19|20)\d{2}", raw_year)
            year = year_match.group(0) if year_match else (raw_year if raw_year and raw_year != "None" else "N/A")
            key = re.sub(r"[^a-z0-9]+", " ", statement_l).strip()
            if key in seen:
                continue
            seen.add(key)
            curated.append({
                "severity": severity,
                "statement": statement,
                "source": source,
                "year": year,
                "confidence": confidence_txt,
            })

        severity_rank = {"HIGH": 0, "MEDIUM": 1}
        curated.sort(key=lambda row: (severity_rank.get(row["severity"], 2), row["statement"]))
        return curated[:5]

    def _regulatory_framework_priority(self, framework: str) -> int:
        text = str(framework or "").lower()
        priority_terms = [
            ("sbti", 1),
            ("science based", 1),
            ("fca", 2),
            ("anti-greenwashing", 2),
            ("sec", 3),
            ("tcfd", 4),
            ("cdp", 5),
            ("ghg protocol", 6),
            ("green claims", 7),
            ("csrd", 8),
            ("issb", 9),
        ]
        for term, priority in priority_terms:
            if term in text:
                return priority
        return 50

    def _normalize_regulatory_framework(self, raw_name: Any) -> str:
        name = self._clean_executive_text(raw_name, max_len=70) or "Unknown framework"
        replacements = {
            "UK Regulatory Evidence Scan": "UK regulatory evidence scan",
            "EU Regulatory Evidence Scan": "EU regulatory evidence scan",
        }
        name = replacements.get(name, name)
        lowered = name.lower()
        canonical = [
            ("sbti", "SBTi"),
            ("science based", "SBTi"),
            ("fca", "FCA Anti-Greenwashing Rule"),
            ("anti-greenwashing", "Anti-Greenwashing Rules"),
            ("sec", "SEC Climate Disclosure"),
            ("tcfd", "TCFD"),
            ("cdp", "CDP"),
            ("ghg protocol", "GHG Protocol"),
            ("green claims", "Green Claims Rules"),
            ("csrd", "CSRD"),
            ("issb", "ISSB"),
        ]
        for token, label in canonical:
            if token in lowered:
                return label
        return name

    def _clean_regulatory_gap_description(self, gap: Any, framework: str = "") -> str:
        raw = " ".join(str(x) for x in gap if x) if isinstance(gap, list) else str(gap or "")
        text = self._clean_executive_text(raw, max_len=150)
        lower = text.lower()
        framework_l = str(framework or "").lower()
        if not text or text in {"-", "N/A"}:
            return "Insufficient disclosure to confirm compliance."
        if "official source located" in lower or "no direct support" in lower:
            if "sbti" in framework_l or "science" in framework_l:
                return "No evidence of target validation."
            return "No verified disclosure supporting compliance."
        if "found in p" in lower or lower.endswith((" found in", " found in p", " page")):
            return "Insufficient disclosure to confirm compliance."
        if "not submitted" in lower or "not validated" in lower:
            return "No evidence of target validation."
        if "missing" in lower and ("disclosure" in lower or "evidence" in lower):
            return "Insufficient disclosure to confirm compliance."
        return text.rstrip(".") + "."

    def _curate_regulatory_gaps(self, regulatory: Any) -> List[Dict[str, str]]:
        if not isinstance(regulatory, dict):
            return []
        rows = regulatory.get("compliance_results", []) or []
        if not isinstance(rows, list):
            return []

        deduped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_name = row.get("regulation_name") or row.get("regulation") or row.get("framework") or row.get("standard")
            framework = self._normalize_regulatory_framework(raw_name)
            gaps = row.get("gap_details") or row.get("gaps") or []
            if isinstance(gaps, str):
                gaps = [gaps]
            if not isinstance(gaps, list):
                gaps = []
            status_raw = str(row.get("status") or "").lower()
            has_gap = bool(gaps) or "gap" in status_raw or "non" in status_raw or "missing" in status_raw
            if not has_gap:
                continue
            description = self._clean_regulatory_gap_description(gaps[0] if gaps else row.get("description"), framework)
            status = "Gap Found"
            priority = self._regulatory_framework_priority(framework)
            key = re.sub(r"[^a-z0-9]+", " ", framework.lower()).strip()
            existing = deduped.get(key)
            if existing is None or priority < existing["priority"]:
                deduped[key] = {
                    "framework": framework,
                    "status": status,
                    "description": description,
                    "priority": priority,
                }

        curated = list(deduped.values())
        curated.sort(key=lambda row: (row["priority"], row["framework"]))
        return [{k: str(v) for k, v in row.items() if k != "priority"} for row in curated[:8]]

    def _regulatory_alert_summary(self, gaps: List[Dict[str, str]]) -> str:
        if not gaps:
            return "Regulatory risk is not driven by material framework gaps in the curated evidence set."
        frameworks = [row["framework"] for row in gaps[:3]]
        return (
            "Regulatory risk is driven by gaps in key frameworks, particularly "
            f"{self._join_business_list(frameworks)}, indicating weak alignment with expected "
            "disclosure and validation standards."
        )

    def _human_claim_type(self, raw_type: Any) -> str:
        key = re.sub(r"[^a-z0-9]+", "_", str(raw_type or "").strip().lower()).strip("_")
        labels = {
            "policy_claim": "strategic claim",
            "strategy_claim": "strategic claim",
            "strategic_claim": "strategic claim",
            "target_claim": "long-term target",
            "future_target": "long-term target",
            "net_zero_target": "long-term target",
            "commitment_claim": "commitment",
            "alignment_claim": "alignment claim",
            "verification_requirement": "evidence requirement",
            "evidence_requirement": "evidence requirement",
            "quantitative_claim": "quantified claim",
            "performance_claim": "performance claim",
            "environmental_claim": "environmental claim",
            "social_claim": "social claim",
            "governance_claim": "governance claim",
        }
        return labels.get(key, "")

    def _citation_source_name(self, citation: Dict[str, Any], index: int) -> str:
        src = str(citation.get("source_name") or "").strip()
        if not src or src.lower() in {"unknown", "web source", "general web", "general web / other"}:
            src = parse_source_name(str(citation.get("url") or "")) or ""
            if not src or src.lower() == "web source":
                src = (urlparse(str(citation.get("url") or "")).netloc or "").replace("www.", "")
            if not src:
                src = str(citation.get("data_source_api") or "").strip()
            if not src:
                src = str(citation.get("title") or "Known source").split(" - ")[0][:36]
        src = self._clean_executive_text(src, max_len=42)
        if not src or src.lower() in {"unknown", "unknown source", "known source"}:
            src = f"Documented Source {index}"
        return src

    def _citation_dedupe_key(self, citation: Dict[str, Any], source_name: str) -> str:
        url = str(citation.get("url") or "").strip()
        parsed = urlparse(url)
        domain = (parsed.netloc or "").replace("www.", "").lower()
        if domain:
            return f"domain:{domain}"
        normalized_url = re.sub(r"[?#].*$", "", url).strip().lower()
        if normalized_url:
            return f"url:{normalized_url}"
        return f"source:{source_name.strip().lower()}"

    def _business_source_type(self, citation: Dict[str, Any], is_first_party: bool = False) -> str:
        tier = str(citation.get("reliability_tier") or "").lower()
        source = str(citation.get("source_name") or citation.get("title") or citation.get("url") or "").lower()
        combined = f"{tier} {source}"
        if "regulatory filing" in combined or "regulator" in combined or ".gov" in combined:
            return "Regulatory Filing"
        if "major news" in combined or "reuters" in combined or "financial times" in combined or "bloomberg" in combined:
            return "Major News"
        if "cdp" in combined or "third-party verified" in combined or "sbti" in combined:
            return "Verified ESG Data"
        if is_first_party or "annual report" in combined or "sustainability report" in combined or "company disclosure" in combined:
            return "Company Disclosure"
        return "Web Source"

    # Well-known ESG adversarial/watchdog domains whose content is almost
    # always critical of corporate climate claims.
    _ADVERSARIAL_DOMAINS = {
        "clientearth.org", "influencemap.org", "ca100.influencemap.org",
        "reclaimfinance.org", "globalwitness.org", "carbontracker.org",
        "follow-the-money.nl", "greenpeace.org", "sierraclub.org",
        "ran.org",  # Rainforest Action Network
    }

    def _business_evidence_role(self, citation: Dict[str, Any], tri_stance: Any = None) -> str:
        stance_raw = str(tri_stance or citation.get("claim_support") or citation.get("stance") or "Neutral").lower()
        if "contradict" in stance_raw or "oppose" in stance_raw or "adversarial" in stance_raw:
            return "Contradicts"
        if "support" in stance_raw or "corroborat" in stance_raw:
            return "Supports"
        if "mixed" in stance_raw:
            return "Mixed"

        # Domain-aware override: known adversarial watchdog sources
        url = str(citation.get("url") or "").lower()
        title = str(citation.get("title") or "").lower()
        snippet = str(citation.get("snippet") or citation.get("body") or "").lower()
        combined = f"{url} {title} {snippet}"
        for domain in self._ADVERSARIAL_DOMAINS:
            if domain in url:
                # Check if the content is actively critical
                critical_markers = [
                    "greenwash", "lawsuit", "court", "mislead", "fails",
                    "insufficient", "lobby", "block", "anti-climate",
                    "mismanag", "flawed", "legal action", "enforcement",
                ]
                if any(m in combined for m in critical_markers):
                    return "Contradicts"
                return "Mixed"

        return "Neutral"

    def _evidence_strength_label(
        self,
        tri_score: Any,
        supporting_count: int,
        contradicting_count: int,
        total_sources: int,
    ) -> Tuple[str, str]:
        score = self._safe_float(tri_score, -1.0)
        if total_sources <= 0:
            return "Limited", "no evidence sources available"
        if score >= 75 and contradicting_count == 0:
            return "Strong", "high agreement across sources"
        if score >= 75:
            return "Strong", "broad agreement with some opposing evidence"
        if score >= 50 or supporting_count >= contradicting_count:
            return "Moderate", "partial agreement with evidence limitations"
        return "Limited", "limited agreement across available sources"

    def _contradiction_level_label(
        self,
        adversarial_ratio: Any,
        supporting_count: int,
        contradicting_count: int,
    ) -> Tuple[str, str]:
        ratio = self._safe_float(adversarial_ratio, 0.0)
        if contradicting_count <= 0 and ratio < 0.2:
            return "Low", "no opposing evidence found"
        if ratio >= 0.5 or contradicting_count > supporting_count:
            return "High", "opposing evidence is material"
        return "Moderate", "some opposing evidence found"

    def _evidence_summary_sentence(
        self,
        strength_label: str,
        contradiction_label: str,
        supporting_count: int,
        contradicting_count: int,
    ) -> str:
        support_text = f"{supporting_count} supporting" if supporting_count else "no explicit supporting"
        contradict_text = f"{contradicting_count} contradicting" if contradicting_count else "no contradicting"
        return (
            f"The evidence base is {strength_label.lower()}, with {support_text} and "
            f"{contradict_text} sources, indicating {contradiction_label.lower()} contradiction pressure."
        )

    @staticmethod
    def _join_business_list(items: List[str]) -> str:
        clean_items = [str(item).strip() for item in items if str(item).strip()]
        if not clean_items:
            return "available evidence signals"
        if len(clean_items) == 1:
            return clean_items[0]
        if len(clean_items) == 2:
            return f"{clean_items[0]} and {clean_items[1]}"
        return f"{', '.join(clean_items[:-1])}, and {clean_items[-1]}"

    @staticmethod
    def _indent_wrapped(text: str, width: int = 76, indent: str = "  ") -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        if not cleaned:
            return ""
        return textwrap.fill(cleaned, width=width, initial_indent=indent, subsequent_indent=indent)

    @staticmethod
    def _slim_key_findings(kf: Dict[str, Any]) -> Dict[str, Any]:
        """Strip multi-MB payloads from agent_results before JSON export.

        Some agents (notably report_parser) carry parsed PDF chunks / raw
        full_text that bloat the export 14× without adding decision-relevant
        info — downstream agents already consumed it and the user can
        re-derive from cache/parsed_reports/. We replace large blobs with a
        compact stub so the audit trail still shows the agent ran.

        Set env var ESG_VERBOSE_JSON=1 (or pass `verbose=True` upstream) to
        retain the full payloads — required for audit/compliance review where
        users need to verify which parsed text produced each finding.
        """
        if not isinstance(kf, dict):
            return kf
        # Verbose mode — return everything untouched.
        if str(os.environ.get("ESG_VERBOSE_JSON", "")).lower() in ("1", "true", "yes", "on"):
            return kf
        # Keys that are always parsed text dumps; keep only a length stub.
        STRIP_KEYS = {"chunks", "raw_chunks", "pdf_chunks", "full_text", "raw_text", "page_text"}
        # Per-value byte cap for *any* string/list/dict value.
        MAX_VALUE_BYTES = 30_000
        out: Dict[str, Any] = {}
        # If report_parser provided downloaded_reports[], pass the local PDF
        # paths into the stub so users can jump straight to the source docs.
        _report_paths: List[str] = []
        try:
            _dr = kf.get("downloaded_reports")
            if isinstance(_dr, list):
                for _row in _dr:
                    if isinstance(_row, dict):
                        _p = _row.get("local_path") or _row.get("url")
                        if _p:
                            _report_paths.append(str(_p))
        except Exception:
            pass

        for k, v in kf.items():
            if k in STRIP_KEYS:
                _audit = {
                    "_stripped": True,
                    "_how_to_audit": (
                        "Set env var ESG_VERBOSE_JSON=1 and re-run to retain the full payload, "
                        "OR open the cached parsed PDFs at cache/parsed_reports/parsed_<hash>.json "
                        "(one per source document). The downloaded_reports[] field above lists the "
                        "originating PDF paths so you can map each finding back to its source."
                    ),
                    "_cache_dir": "cache/parsed_reports/",
                    "_source_documents": _report_paths or None,
                }
                if isinstance(v, list):
                    _audit.update({"_count": len(v), "_first_chunk_preview": (str(v[0])[:300] if v else None)})
                    out[k] = _audit
                elif isinstance(v, str):
                    _audit.update({"_chars": len(v), "_preview": v[:300]})
                    out[k] = _audit
                else:
                    out[k] = v
                continue
            try:
                size = len(json.dumps(v, default=str))
            except Exception:
                out[k] = v
                continue
            if size > MAX_VALUE_BYTES:
                # Keep a peek + summary so the audit trail records what was there.
                if isinstance(v, list):
                    out[k] = {
                        "_stripped": True,
                        "_count": len(v),
                        "_size_bytes": size,
                        "_sample": v[:3],
                        "_note": "Large list elided to keep JSON export under 500KB.",
                    }
                elif isinstance(v, dict):
                    out[k] = {
                        "_stripped": True,
                        "_keys": list(v.keys())[:20],
                        "_size_bytes": size,
                        "_note": "Large dict elided to keep JSON export under 500KB.",
                    }
                elif isinstance(v, str):
                    out[k] = {
                        "_stripped": True,
                        "_chars": len(v),
                        "_preview": v[:300],
                        "_note": "Large string truncated to keep JSON export under 500KB.",
                    }
                else:
                    out[k] = v
            else:
                out[k] = v
        return out

    @staticmethod
    def _smart_truncate(text: Any, width: int, ellipsis: str = "…") -> str:
        """Truncate at the last word boundary before `width`. Avoids mid-word cuts
        like "Web source / Company Report (par" that look like garbled output."""
        s = str(text or "")
        if len(s) <= width:
            return s
        cut = s[: max(1, width - len(ellipsis))]
        # Walk back to the last whitespace; if none found, fall back to a hard cut.
        last_ws = cut.rfind(" ")
        if last_ws >= max(8, width // 3):
            cut = cut[:last_ws].rstrip(" -/:,;")
        return cut + ellipsis

    @staticmethod
    def _normalize_scraped_text(text: Any) -> str:
        """Re-insert spaces into scraped text where HTML stripping concatenated tokens.

        Scraped news/profile text often comes back as e.g. "JPMorganChase& Co.",
        "ESGSustainability", "ESGEnvironmentalScore". Transformations applied:
          1. Acronym (3+ uppercase) → TitleCase split: "ESGSustainability" → "ESG Sustainability".
          2. Lowercase → uppercase split (camelCase): "JPMorganChase" → "JPMorgan Chase".
          3. Letter↔digit boundary split: "Scope3" → "Scope 3", "2030target" → "2030 target".
          4. Common-word boundary split for all-lowercase concatenated runs:
             "andenvironmentalgroupsare" → "and environmental groups are".
        """
        if text is None:
            return ""
        s = str(text)
        # Acronym (3+ uppers) followed by TitleCase word.
        s = re.sub(r"([A-Z]{3,})([A-Z][a-z])", r"\1 \2", s)
        # Standard camelCase boundary.
        s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
        # Letter↔digit boundaries.
        s = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", s)
        s = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", s)

        # All-lowercase concatenated runs from broken HTML extraction:
        # "andenvironmentalgroupsare" comes from "and environmental groups are"
        # losing its spaces. We split at common stop-words found inside long
        # lowercase runs. Pattern: a stop word preceded by a lowercase letter
        # (i.e. it's stuck to the previous word) gets a space before it.
        common_words = [
            "and", "the", "are", "was", "were", "for", "with", "from", "that",
            "this", "these", "have", "has", "been", "their", "they", "but",
            "not", "into", "about", "regulatory", "government", "groups",
            "environmental", "industrial", "company", "companies", "emission",
            "emissions", "climate", "report", "reports", "carbon", "scope",
        ]
        for w in common_words:
            # Only split when the stop-word is glued to a >=2-letter prefix
            # AND followed by another lowercase char (i.e. mid-run, not edge).
            s = re.sub(rf"([a-z]{{2,}})({w})(?=[a-z])", r"\1 \2 ", s, flags=re.IGNORECASE)
        # Collapse any double-space that may now exist.
        s = re.sub(r"  +", " ", s)
        return s

    def _format_verdict_finding(self, line: str) -> str:
        # Use a generous max_len so the source string isn't truncated mid-name
        # ("EU | EU" instead of "EU | EU Regulatory Evidence"). textwrap.fill
        # below handles the 78-char visual line wrapping cleanly.
        cleaned = self._clean_executive_text(line, max_len=220)
        if not cleaned:
            cleaned = "[i] INFO - Analysis completed without displayable raw extraction text"
        return textwrap.fill(cleaned, width=78, initial_indent="  - ", subsequent_indent="    ")

    def _is_human_readable_text(self, text: Any) -> bool:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        if not cleaned:
            return False

        lower = cleaned.lower()
        artifact_patterns = [
            r'["\']?[a-z_][\w -]{1,40}["\']?\s*:\s*(?:\[|\{|"|\d)',
            r"\b(?:loading|lqip|srcset|__typename|graphql|data-)\b",
            r"natural\s*dimensions",
            r"</?[a-z][^>]*>",
            r"&(?:quot|amp|lt|gt|nbsp);",
        ]
        if any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in artifact_patterns):
            json_punct = sum(1 for ch in cleaned if ch in "{}[]\":,")
            if json_punct >= 3 or cleaned[:1] in {";", ",", ":", "]", "}"}:
                return False

        if len(cleaned) < 8:
            allowed_label = all(ch.isalnum() or ch in " .&'/-" for ch in cleaned)
            return bool(allowed_label and any(ch.isalpha() for ch in cleaned))

        if cleaned[:1] in {";", ",", ":", "]", "}"}:
            return False

        letters = sum(1 for ch in cleaned if ch.isalpha())
        if letters < 5:
            return False

        structural = sum(1 for ch in cleaned if ch in "{}[]\":,")
        if structural / max(len(cleaned), 1) > 0.22:
            return False

        return bool(re.search(r"[^\W\d_][^\W\d_-]{2,}", cleaned, flags=re.UNICODE))

    def _clean_executive_text(self, raw: Any, max_len: int = 110) -> str:
        if raw is None:
            return ""

        text = html.unescape(str(raw))
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("\u2014", "-").replace("\u2013", "-")
        text = text.replace("\u2022", "-").replace("\xa0", " ")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = text.strip(" \t\r\n-;:,")

        if not self._is_human_readable_text(text):
            return ""

        if len(text) <= max_len:
            return text.rstrip(" ,;:")

        sentence_match = re.match(r"^(.{20,%d}?[.!?])(?:\s|$)" % max_len, text)
        if sentence_match:
            return sentence_match.group(1).strip()

        truncated = text[:max_len].rsplit(" ", 1)[0].strip(" ,;:-")
        return truncated if self._is_human_readable_text(truncated) else ""

    def _build_verdict_summary(self, company: str, band: str, score: Any, drivers: List[str]) -> str:
        company_clean = self._clean_executive_text(company, max_len=60) or "The company"
        band_clean = self._clean_executive_text(band, max_len=20) or "moderate"
        score_value = self._safe_float(score, 0.0)
        driver_text = self._join_business_list(drivers[:3])
        return (
            f"{company_clean} shows {band_clean.lower()} greenwashing risk "
            f"({score_value:.1f}/100) driven by {driver_text}."
        )

    def _carbon_has_scope3_gap(self, carbon: Dict[str, Any], claim: str = "") -> bool:
        claim_l = str(claim or "").lower()
        climate_claim = any(term in claim_l for term in ["net zero", "net-zero", "emission", "carbon", "value chain"])
        if not climate_claim:
            return False

        emissions = carbon.get("emissions", {}) if isinstance(carbon.get("emissions"), dict) else {}
        scope3 = emissions.get("scope3") or carbon.get("scope_3") or {}
        if not isinstance(scope3, dict):
            return True

        scope3_value = scope3.get("total") or scope3.get("value") or scope3.get("emissions_tco2e")
        categories = scope3.get("categories")
        if isinstance(categories, dict):
            category_count = len(categories)
        elif isinstance(categories, list):
            category_count = len(categories)
        else:
            category_count = 0

        return scope3_value in (None, "", "N/A") or category_count == 0

    def _carbon_quality_is_weak(self, carbon: Dict[str, Any]) -> bool:
        dq = carbon.get("data_quality") if isinstance(carbon, dict) else {}
        if isinstance(dq, dict):
            score = dq.get("overall_score") or dq.get("score")
            confidence = str(dq.get("data_confidence") or dq.get("confidence") or "").lower()
            return (isinstance(score, (int, float)) and float(score) < 50) or confidence == "low"
        return isinstance(dq, (int, float)) and float(dq) < 50

    def _regulatory_gap_names(self, regulatory: Dict[str, Any]) -> List[str]:
        rows = regulatory.get("compliance_results", []) if isinstance(regulatory, dict) else []
        if not isinstance(rows, list):
            rows = []

        names: List[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            details = row.get("gap_details") or row.get("gaps") or []
            status = str(row.get("status") or "").lower()
            has_gap = bool(details) or "gap" in status or "non" in status
            if not has_gap:
                continue
            name = (
                row.get("regulation_name")
                or row.get("regulation")
                or row.get("framework")
                or row.get("standard")
            )
            clean_name = self._clean_executive_text(name, max_len=28)
            if clean_name and clean_name not in names:
                names.append(clean_name)
        return names[:3]

    def _build_verdict_drivers(self, context: Dict[str, Any]) -> List[str]:
        drivers: List[str] = []

        contradiction_count = int(self._safe_float(context.get("contradiction_count"), 0.0))
        if contradiction_count > 0:
            drivers.append("contradiction signals")

        regulatory = context.get("regulatory", {}) if isinstance(context.get("regulatory"), dict) else {}
        reg_gaps = context.get("reg_gaps", []) if isinstance(context.get("reg_gaps"), list) else []
        reg_gap_names = self._regulatory_gap_names(regulatory)
        compliance_score = regulatory.get("compliance_score") if isinstance(regulatory, dict) else {}
        gap_count = compliance_score.get("gaps", 0) if isinstance(compliance_score, dict) else 0
        if reg_gaps or reg_gap_names or gap_count:
            drivers.append("regulatory gaps")

        carbon = context.get("carbon", {}) if isinstance(context.get("carbon"), dict) else {}
        if self._carbon_has_scope3_gap(carbon, context.get("claim", "")) or self._carbon_quality_is_weak(carbon):
            drivers.append("carbon misalignment")

        pillar_scores = safe_get(context, "scores", "pillar_scores", default={})
        governance_score = pillar_scores.get("governance_score") if isinstance(pillar_scores, dict) else None
        if isinstance(governance_score, (int, float)) and float(governance_score) < 45:
            drivers.append("weak governance signals")

        peers = context.get("same_industry_peers", []) if isinstance(context.get("same_industry_peers"), list) else []
        if len(peers) < 2:
            drivers.append("limited peer benchmarking")

        citations = context.get("citations", []) if isinstance(context.get("citations"), list) else []
        if len(citations) < 5:
            drivers.append("limited evidence coverage")

        if not drivers:
            drivers.extend(["claim substantiation", "evidence quality"])

        deduped = list(dict.fromkeys(drivers))
        return deduped[:3]

    def _build_verdict_findings(
        self,
        agents: Dict[str, Any],
        scores: Dict[str, Any],
        context: Any = None,
    ) -> List[str]:
        findings: List[str] = []
        context = context or {}

        contra_output = ((agents.get("contradiction_analysis", {}) or {}).get("output", {}) or {})
        contradictions = (
            contra_output.get("contradictions")
            or contra_output.get("specific_contradictions")
            or []
        )

        if isinstance(contradictions, list):
            for c in contradictions:
                if not isinstance(c, dict):
                    continue
                sev = str(c.get("severity", "")).upper()
                desc = self._clean_executive_text(
                    c.get("description") or c.get("contradiction_text") or c.get("summary") or c.get("title"),
                    max_len=86,
                )
                if sev == "HIGH" and desc:
                    findings.append(f"[!] HIGH - {desc}")

        if not any(f.startswith("[!]") for f in findings) and isinstance(contradictions, list):
            for c in contradictions[:2]:
                if isinstance(c, dict):
                    desc = self._clean_executive_text(
                        c.get("description") or c.get("contradiction_text") or c.get("summary") or c.get("title"),
                        max_len=86,
                    )
                    sev = str(c.get("severity", "MEDIUM")).upper()
                    if desc:
                        level = "HIGH" if sev == "HIGH" else "MEDIUM"
                        tag = "[!]" if level == "HIGH" else "[~]"
                        findings.append(f"{tag} {level} - {desc}")

        contradiction_count = int(self._safe_float(context.get("contradiction_count"), 0.0))
        if contradiction_count <= 0:
            contradiction_count = int(self._safe_float(contra_output.get("contradictions_found"), 0.0))
        if contradiction_count > 0 and not any("contradiction" in f.lower() for f in findings):
            findings.append("[!] HIGH - Contradiction signals detected in the evidence review")

        reg_output = context.get("regulatory") if isinstance(context.get("regulatory"), dict) else {}
        if not reg_output:
            reg_output = ((agents.get("regulatory_scanning", {}) or {}).get("output", {}) or {})
        gaps = 0
        if isinstance(reg_output, dict):
            cs = reg_output.get("compliance_score", {})
            gaps = cs.get("gaps", 0) if isinstance(cs, dict) else 0
        reg_gap_names = self._regulatory_gap_names(reg_output if isinstance(reg_output, dict) else {})
        reg_gap_rows = context.get("reg_gaps", []) if isinstance(context.get("reg_gaps"), list) else []
        if gaps or reg_gap_names or reg_gap_rows:
            if reg_gap_names:
                findings.append(f"[~] MEDIUM - Regulatory gaps identified in {self._join_business_list(reg_gap_names)}")
            else:
                gap_total = gaps or len(reg_gap_rows)
                findings.append(f"[~] MEDIUM - {gap_total} regulatory framework gap(s) identified")

        carbon = context.get("carbon", {}) if isinstance(context.get("carbon"), dict) else {}
        if self._carbon_has_scope3_gap(carbon, context.get("claim", "")):
            findings.append("[~] MEDIUM - Scope 3 evidence is incomplete for the stated climate claim")
        elif self._carbon_quality_is_weak(carbon):
            findings.append("[~] MEDIUM - Carbon data quality is weak for decision-grade assurance")

        pillar_scores = safe_get(context, "scores", "pillar_scores", default={})
        governance_score = pillar_scores.get("governance_score") if isinstance(pillar_scores, dict) else None
        if isinstance(governance_score, (int, float)) and float(governance_score) < 45:
            findings.append("[~] MEDIUM - Governance score indicates weak oversight or disclosure signals")

        evidence_out = ((agents.get("evidence_retrieval", {}) or {}).get("output", {}) or {})
        context_sources = context.get("citations", []) if isinstance(context.get("citations"), list) else []
        agent_sources = evidence_out.get("citations", []) or evidence_out.get("evidence", []) or []
        total_sources = len(context_sources) or len(agent_sources or [])
        findings.append(f"[i] INFO - {total_sources} sources analyzed")

        if not any("regulatory" in f.lower() for f in findings):
            findings.append("[i] INFO - Regulatory framework screening completed")

        if not any("contradiction" in f.lower() for f in findings):
            findings.append("[i] INFO - Contradiction screening completed")

        clean_findings: List[str] = []
        seen_messages: Set[str] = set()
        for finding in findings:
            # Generous max_len so framework names like "EU | EU Regulatory Evidence"
            # aren't truncated mid-name. textwrap downstream handles visual wrapping.
            cleaned = self._clean_executive_text(finding, max_len=220)
            if not cleaned:
                continue
            key = re.sub(r"^\[[!~i]\]\s+\w+\s+-\s+", "", cleaned.lower())
            if key in seen_messages:
                continue
            seen_messages.add(key)
            clean_findings.append(cleaned)

        return clean_findings[:5]

    def _extract_key_finding(self, agent_name: str, output: Dict[str, Any]) -> str:
        if not isinstance(output, dict):
            return "No output"
        o = output

        if agent_name in ("claim_extraction", "claim_extractor"):
            claims_by_year = o.get("claims_by_year", {})
            if isinstance(claims_by_year, dict):
                total_claims = sum(len(v) for v in claims_by_year.values() if isinstance(v, list))
                years = len([k for k, v in claims_by_year.items() if isinstance(v, list) and v])
                if total_claims > 0:
                    return f"{total_claims} claim(s) extracted across {years} year(s)"

        if agent_name == "carbon_extraction":
            emissions = o.get("emissions", {}) if isinstance(o.get("emissions"), dict) else o
            s1 = ((emissions.get("scope1", {}) or {}).get("value") if isinstance(emissions.get("scope1", {}), dict) else None) or "N/A"
            s2 = ((emissions.get("scope2", {}) or {}).get("value") if isinstance(emissions.get("scope2", {}), dict) else None) or "N/A"
            s3_dict = emissions.get("scope3", {}) if isinstance(emissions.get("scope3", {}), dict) else {}
            s3 = s3_dict.get("total") or s3_dict.get("value") or "N/A"
            return f"S1: {s1}  S2: {s2}  S3: {s3}"

        if agent_name == "contradiction_analysis":
            n = o.get("contradictions_found", 0)
            return f"{n} contradiction(s) found"

        if agent_name == "risk_scoring":
            score = o.get("greenwashingriskscore", "?")
            grade = o.get("rating_grade", "?")
            return f"Final: {score}/100  Grade: {grade}"

        if agent_name == "climatebert_analysis":
            claim_analysis = o.get("claim_analysis", {}) if isinstance(o.get("claim_analysis"), dict) else {}
            gwd = claim_analysis.get("greenwashing_detection", {}) if isinstance(claim_analysis.get("greenwashing_detection"), dict) else {}
            climate_rel = claim_analysis.get("climate_relevance", {}) if isinstance(claim_analysis.get("climate_relevance"), dict) else {}
            risk = gwd.get("risk_score")
            if not isinstance(risk, (int, float)):
                risk = o.get("greenwashing_risk", o.get("risk_score", 0))
            level = gwd.get("risk_level") or o.get("risk_level") or "LOW"
            rel = climate_rel.get("score")
            if not isinstance(rel, (int, float)):
                rel = o.get("climate_relevance", 0)
            return f"Risk {self._fmt_score1(risk)}/100 {str(level).upper()} - relevance {self._fmt_score1(rel)}%"

        if agent_name == "greenwishing_detection":
            gw = (o.get("greenwishing", {}) or {}).get("score", "?")
            level = (o.get("greenwishing", {}) or {}).get("risk_level", "?")
            return f"Greenwishing: {gw}/100 {level}"

        if agent_name == "regulatory_scanning":
            cs = o.get("compliance_score", {})
            score = cs.get("score", "?") if isinstance(cs, dict) else cs
            gaps = cs.get("gaps", 0) if isinstance(cs, dict) else 0
            return f"Compliance: {score}/100 - {gaps} gap(s)"

        if agent_name == "sentiment_analysis":
            sig = o.get("notable_signal", "")
            div = o.get("sentiment_divergence", "?")
            return f"Divergence: {div} - {sig or 'No dominant signal'}"

        if agent_name == "temporal_analysis":
            rep = o.get("reputation_score", "?")
            viol = o.get("violations_count", 0)
            return f"Reputation: {rep}/100 - {viol} violation(s)"

        if agent_name == "credibility_analysis":
            score = o.get("overall_credibility") or o.get("credibility_score", "?")
            total = o.get("total_sources") or o.get("sources_analyzed", 0)
            return f"Credibility: {score}/100 - {total} sources"

        if agent_name == "peer_comparison":
            peers = len(o.get("peers", []) or [])
            return f"{peers} peers in same industry set"

        if agent_name == "explainability":
            factors = o.get("top_factors", []) or []
            if factors and isinstance(factors[0], dict):
                top = factors[0].get("factor") or factors[0].get("feature", "?")
                return f"Top driver: {str(top)[:40]}"
            return "SHAP/LIME analysis complete"

        if agent_name == "temporal_consistency":
            score = o.get("temporal_consistency_score", "?")
            risk = o.get("risk_level", "?")
            return f"Score: {score}/100 - {risk}"

        if agent_name == "evidence_retrieval":
            evidence_count = len(o.get("evidence", []) or o.get("citations", []) or [])
            if evidence_count:
                return f"{evidence_count} evidence source(s) retrieved"
            ts = o.get("retrieval_timestamp", "")
            return f"Retrieved at {str(ts)[:16]}" if ts else "Evidence retrieved"

        if agent_name == "supervisor":
            return "Orchestration only"

        for k, v in o.items():
            if isinstance(v, str) and len(v) > 5 and k not in ("status", "agent"):
                return f"{k}: {v[:50]}"
        return "Completed"

    def _extract_peer_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        peer_analysis = state.get("peer_comparison") or {}
        if not isinstance(peer_analysis, dict):
            peer_analysis = {}

        if not peer_analysis.get("peers") and not peer_analysis.get("peer_table"):
            for out in reversed(state.get("agent_outputs", []) or []):
                if not isinstance(out, dict) or out.get("agent") not in {"peer_comparison", "industry_comparator"}:
                    continue
                candidate = out.get("output")
                if isinstance(candidate, dict) and (candidate.get("peers") or candidate.get("peer_table")):
                    peer_analysis = candidate
                    break

        peers = peer_analysis.get("peers") or peer_analysis.get("peer_table") or []
        if not isinstance(peers, list):
            peers = []

        real_peers = [
            p
            for p in peers
            if isinstance(p, dict) and (p.get("source") or "").lower() in {"database", "baseline", "wba_live"}
        ]
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

    @staticmethod
    def _normalize_sector_value(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _infer_claim_type(claim_text: str) -> str:
        text = str(claim_text or "").lower()
        if any(k in text for k in ["net zero", "net-zero", "carbon neutral", "carbon negative", "climate neutral"]):
            return "net-zero"
        if any(k in text for k in ["packaging", "plastic", "recycl", "biodegrad", "compostable", "single-use"]):
            return "packaging"
        if any(k in text for k in ["water", "water positive", "water neutral", "watershed", "freshwater"]):
            return "water"
        if any(k in text for k in ["board", "governance", "ethics", "compliance", "audit committee", "anti-corruption"]):
            return "governance"
        if any(k in text for k in ["labor", "human rights", "diversity", "inclusion", "community", "worker", "social"]):
            return "social"
        if any(k in text for k in ["emission", "scope 1", "scope 2", "scope 3", "co2", "ghg", "decarbon", "renewable"]):
            return "emissions"
        return "emissions"

    @staticmethod
    def _adjacent_industries(industry: str) -> Set[str]:
        # Lightweight adjacency graph for ESG comparability across closely related sectors.
        graph = {
            "energy": {"utilities", "manufacturing", "aviation", "automotive"},
            "technology": {"retail", "finance", "manufacturing"},
            "finance": {"technology", "retail"},
            "aviation": {"energy", "automotive", "manufacturing"},
            "automotive": {"manufacturing", "aviation", "energy"},
            "retail/fashion": {"retail", "consumer goods", "food & beverage"},
            "retail": {"retail/fashion", "consumer goods", "food & beverage", "technology"},
            "consumer goods": {"retail", "retail/fashion", "food & beverage", "manufacturing"},
            "food & beverage": {"consumer goods", "retail", "manufacturing"},
            "manufacturing": {"automotive", "energy", "consumer goods", "technology", "aviation"},
        }
        key = str(industry or "").strip().lower()
        return graph.get(key, set())

    def _extract_calibration_info(
        self,
        scores: Dict[str, Any],
        company_industry: str = "Unknown",
        claim_text: str = "",
    ) -> Dict[str, Any]:
        """Load ground truth CSV and compute calibration metrics live.

        Returns claim-specific calibration stats by filtering to same-industry +
        same-claim-type peers first, then expanding to adjacent industries.
        """
        import pandas as pd
        from scipy.stats import spearmanr

        gt_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ground_truth_dataset.csv')

        # ---- NOT_AVAILABLE: file missing or empty ----
        if not os.path.exists(gt_path):
            return self._empty_calibration(scores)
        try:
            df = pd.read_csv(gt_path)
        except Exception:
            return self._empty_calibration(scores)
        if df.empty or len(df) == 0:
            return self._empty_calibration(scores)

        # ---- Compute claim-specific calibration from filtered subset ----
        try:
            from ml_models.score_calibrator import linguistic_greenwashing_score

            df = df.copy()
            if 'claim_text' not in df.columns or 'greenwashing_label' not in df.columns:
                return self._empty_calibration(scores)

            df['sector_norm'] = df.get('sector', pd.Series([""] * len(df))).apply(self._normalize_sector_value)
            df['claim_type'] = df['claim_text'].apply(self._infer_claim_type)
            df['predicted_score'] = [
                linguistic_greenwashing_score(
                    str(row.get('claim_text', '')),
                    str(row.get('company_name', '')),
                    str(row.get('sector', '')),
                )
                for _, row in df.iterrows()
            ]

            target_industry = self._normalize_sector_value(company_industry)
            target_claim_type = self._infer_claim_type(claim_text)

            # Exact subset first (same industry + claim type).
            exact_subset = df[
                (df['sector_norm'] == target_industry) &
                (df['claim_type'] == target_claim_type)
            ]
            no_industry_match = len(exact_subset) == 0

            subset = exact_subset
            adjacent_used = False
            adjacent_list: List[str] = []

            # Expand to adjacent industries when fewer than 3 exact peers.
            if len(subset) < 3:
                adjacent_set = self._adjacent_industries(target_industry)
                adjacent_list = sorted(adjacent_set)
                if adjacent_set:
                    subset = df[
                        (df['claim_type'] == target_claim_type) &
                        (df['sector_norm'].isin({target_industry, *adjacent_set}))
                    ]
                    adjacent_used = True

            fallback_used = False
            fallback_reason = None
            if len(subset) == 0:
                # Zero matching cases: system-level fallback (computed, never hardcoded).
                subset = df
                fallback_used = True
                fallback_reason = "NO_PEER_CASES"

            labels = subset['greenwashing_label'].astype(float).values
            sc_scores = subset['predicted_score'].astype(float).values

            spearman_r = None
            spearman_p = None
            try:
                sp = spearmanr(sc_scores, labels)
                if sp is not None:
                    if sp.correlation == sp.correlation:
                        spearman_r = float(sp.correlation)
                    if sp.pvalue == sp.pvalue:
                        spearman_p = float(sp.pvalue)
            except Exception:
                pass

            gw_scores = subset.loc[subset['greenwashing_label'] == 1, 'predicted_score'].astype(float)
            legit_scores = subset.loc[subset['greenwashing_label'] == 0, 'predicted_score'].astype(float)

            mean_gw = float(gw_scores.mean()) if len(gw_scores) > 0 else None
            mean_leg = float(legit_scores.mean()) if len(legit_scores) > 0 else None

            if isinstance(mean_gw, float) and isinstance(mean_leg, float):
                optimal_threshold = float((mean_gw + mean_leg) / 2.0)
            else:
                # Class-imbalanced subset fallback to system-level class means.
                all_gw = df.loc[df['greenwashing_label'] == 1, 'predicted_score'].astype(float)
                all_leg = df.loc[df['greenwashing_label'] == 0, 'predicted_score'].astype(float)
                if len(all_gw) > 0 and len(all_leg) > 0:
                    optimal_threshold = float((float(all_gw.mean()) + float(all_leg.mean())) / 2.0)
                    if mean_gw is None:
                        mean_gw = float(all_gw.mean())
                    if mean_leg is None:
                        mean_leg = float(all_leg.mean())
                    fallback_used = True
                    if not fallback_reason:
                        fallback_reason = "CLASS_IMBALANCE"
                else:
                    optimal_threshold = None

            subset_n = int(len(subset))
            sector_counts = dict(subset['sector'].value_counts()) if 'sector' in subset.columns else {}
            industries = subset['sector'].dropna().unique().tolist() if 'sector' in subset.columns else []

            if subset_n >= 10:
                calibration_status = "CALIBRATED"
                confidence_ceiling = 85.0
            elif subset_n >= 5:
                calibration_status = "PROVISIONAL"
                confidence_ceiling = 75.0
            elif subset_n >= 3:
                calibration_status = "PROVISIONAL"
                confidence_ceiling = 65.0
            else:
                calibration_status = "LOW"
                confidence_ceiling = 55.0

            p_value_report: Any = "insufficient for significance"
            if subset_n >= 5 and isinstance(spearman_p, float):
                p_value_report = spearman_p

            # Confidence region
            gw_score = scores.get("greenwashingriskscore")
            confidence_region = "unknown"
            if isinstance(gw_score, (int, float)) and isinstance(optimal_threshold, (int, float)):
                if gw_score >= optimal_threshold + 10:
                    confidence_region = "high_suspicion_zone"
                elif gw_score <= optimal_threshold - 10:
                    confidence_region = "likely_legitimate_zone"
                else:
                    confidence_region = "grey_zone"

            # ── System-level (whole dataset) reference stats ──────────────
            # Useful when the sector-specific subset is small: the audience
            # can still see the overall correlation strength.
            system_spearman_r: Any = None
            system_spearman_p: Any = None
            try:
                sp_sys = spearmanr(df['predicted_score'].astype(float).values,
                                   df['greenwashing_label'].astype(float).values)
                if sp_sys is not None and sp_sys.correlation == sp_sys.correlation:
                    system_spearman_r = float(sp_sys.correlation)
                if sp_sys is not None and sp_sys.pvalue == sp_sys.pvalue:
                    system_spearman_p = float(sp_sys.pvalue)
            except Exception:
                pass
            sys_gw_mean = float(df.loc[df['greenwashing_label'] == 1, 'predicted_score'].mean()) if (df['greenwashing_label'] == 1).any() else None
            sys_leg_mean = float(df.loc[df['greenwashing_label'] == 0, 'predicted_score'].mean()) if (df['greenwashing_label'] == 0).any() else None

            return {
                # IMPORTANT: this Spearman correlates the LINGUISTIC STUB scorer
                # (ml_models/score_calibrator.linguistic_greenwashing_score, ~30 LOC of
                # rule-based text matching) against ground-truth labels. It does NOT
                # measure how well the 30-agent pipeline ranks greenwashers vs
                # legitimate companies. The pipeline has not been benchmarked
                # against the labelled dataset; until it is, `pipeline_spearman_r`
                # remains null and the headline calibration claim should not be
                # over-interpreted. See plan item #11 ("Make Spearman calibration
                # honest") for the validation script that would populate it.
                "spearman_r": spearman_r,  # deprecated alias of linguistic_stub_spearman_r
                "linguistic_stub_spearman_r": spearman_r,
                "spearman_p": spearman_p,
                "linguistic_stub_spearman_p": spearman_p,
                "pipeline_spearman_r": None,
                "pipeline_spearman_p": None,
                "calibration_methodology": (
                    "Sub-sample Spearman of linguistic_greenwashing_score (rule-based text scorer) "
                    "vs ground-truth labels. Pipeline correlation is unmeasured pending a "
                    "validate_pipeline.py run against the full labelled dataset."
                ),
                "p_value_reported": p_value_report,
                "point_biserial_r": None,
                "mannwhitney_p": None,
                "optimal_threshold": optimal_threshold,
                "mean_score_greenwashing": mean_gw,
                "mean_score_legitimate": mean_leg,
                "calibration_status": calibration_status,
                "confidence_region": confidence_region,
                "dataset_size": subset_n,
                "system_dataset_size": int(len(df)),
                "system_spearman_r": system_spearman_r,  # deprecated alias
                "system_linguistic_stub_spearman_r": system_spearman_r,
                "system_spearman_p": system_spearman_p,
                "system_linguistic_stub_spearman_p": system_spearman_p,
                "system_mean_greenwashing": sys_gw_mean,
                "system_mean_legitimate": sys_leg_mean,
                "industries_represented": industries,
                "sector_counts": sector_counts,
                "subset_industry": company_industry,
                "subset_claim_type": target_claim_type,
                "adjacent_expansion_used": adjacent_used,
                "adjacent_industries": adjacent_list,
                "no_industry_match": no_industry_match,
                "fallback_used": fallback_used,
                "fallback_reason": fallback_reason,
                "confidence_ceiling_pct": confidence_ceiling,
                "low_sample": subset_n < 5,
                "low_confidence_flag": subset_n < 3,
            }
        except Exception:
            return self._empty_calibration(scores)

    def _empty_calibration(self, scores: Dict[str, Any]) -> Dict[str, Any]:
        """Return a NOT_AVAILABLE calibration dict with all values as None."""
        gw_score = scores.get("greenwashingriskscore")
        return {
            "spearman_r": None,
            "spearman_p": None,
            "p_value_reported": "insufficient for significance",
            "point_biserial_r": None,
            "mannwhitney_p": None,
            "optimal_threshold": None,
            "mean_score_greenwashing": None,
            "mean_score_legitimate": None,
            "calibration_status": "NOT_AVAILABLE",
            "confidence_region": "unknown",
            "dataset_size": None,
            "industries_represented": [],
            "sector_counts": {},
            "subset_industry": None,
            "subset_claim_type": None,
            "adjacent_expansion_used": False,
            "adjacent_industries": [],
            "no_industry_match": False,
            "fallback_used": False,
            "fallback_reason": None,
            "confidence_ceiling_pct": None,
            "low_sample": True,
            "low_confidence_flag": True,
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
        gw_score = scores.get("greenwashingriskscore")
        esg_score = scores.get("esg_score")
        pillar_scores = scores.get("pillar_scores", {}) or {}
        top_reasons = scores.get("explainability_top_3_reasons", []) or []
        industry_ctx = scores.get("industry", industry)
        confidence_pct = scores.get("confidence_level", quality.get("report_confidence_level", "UNKNOWN"))
        citations = evidence.get("citations") or []
        verifiable = evidence.get("verifiable_citations", 0)
        real_peers = peers.get("real_peer_count", 0)
        report_conf = quality.get("report_confidence_level", "UNKNOWN")

        if isinstance(gw_score, (int, float)):
            score_text = f"{gw_score:.1f}/100"
        else:
            score_text = "not numerically calibrated"

        esg_text = f"{esg_score:.1f}/100" if isinstance(esg_score, (int, float)) else "N/A"
        e_p = pillar_scores.get("environmental_score")
        s_p = pillar_scores.get("social_score")
        g_p = pillar_scores.get("governance_score")

        # Top drivers: always show up to 3 concise bullets that mix positives and negatives.
        driver_lines: List[str] = []
        for reason in top_reasons[:3]:
            if not reason:
                continue
            driver_lines.append(f"  - {reason}")

        drivers_block = "\n".join(driver_lines) if driver_lines else "  - Drivers not available (insufficient structured explainability)."

        paragraph = (
            f"{company} ({industry_ctx}) is assessed at ESG rating {esg_rating} with {risk_level.lower()} greenwashing risk. "
            f"Overall ESG performance is {esg_text}, corresponding to an integrated greenwashing risk score of {score_text}. "
            f"E/S/G pillar scores are "
            f"{'E=' + str(e_p) if isinstance(e_p, (int, float)) else 'E=N/A'}, "
            f"{'S=' + str(s_p) if isinstance(s_p, (int, float)) else 'S=N/A'}, "
            f"{'G=' + str(g_p) if isinstance(g_p, (int, float)) else 'G=N/A'}. "
            f"Evidence coverage includes {len(citations)} sources ({verifiable} fully verifiable), with {real_peers} peer "
            f"comparators used for calibration. Overall confidence in this assessment is {confidence_pct}."
            f"\n\nTop drivers of this rating:\n{drivers_block}\n\n"
            f"Key claim analyzed: {claim}."
        )
        return self._wrap_paragraph(paragraph)

    def _render_section2_evidence_table(self, evidence: Dict[str, Any]) -> str:
        citations = evidence.get("citations") or []
        if not citations:
            return "No structured evidence citations were available for this run."

        lines: List[str] = []
        lines.append(f"{'#':<3} {'Source Name':<30} {'Reliability Tier':<28} {'Verifiable':<10} {'Claim Support':<15}")
        lines.append("-" * 91)
        for c in citations:
            idx = str(c.get("id", ""))
            src = str(c.get("source_name", "Unknown"))[:30]
            tier = str(c.get("reliability_tier", "General Web / Other"))[:28]
            ver = "YES" if c.get("verifiable") else "NO"
            claim_support = str(c.get("claim_support", "unspecified"))[:15]
            lines.append(f"{idx:<3} {src:<30} {tier:<28} {ver:<10} {claim_support:<15}")

        lines.append("")
        lines.append("Reliability tiers (strongest to weakest):")
        lines.append("  1. Regulatory Filing")
        lines.append("  2. CDP / Third-Party Verified")
        lines.append("  3. Major News Outlet")
        lines.append("  4. General Web / Other")
        lines.append("  5. Estimated / Synthetic")
        lines.append("  6. [UNVERIFIABLE]")
        return "\n".join(lines)

    def _render_metadata_table(
        self,
        metadata: Dict[str, Any],
        company: str,
        industry: str,
        claim: str,
        workflow_display: str,
        quality: Dict[str, Any],
    ) -> str:
        timestamp = self._coerce_datetime(metadata.get("timestamp_dt")) if metadata.get("timestamp_dt") else None  # FIX: str→datetime safe
        analysis_date = timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if timestamp else "Unknown"
        report_id = metadata.get("report_id", "Unknown")
        workflow_short = workflow_display if len(workflow_display) <= 300 else workflow_display[:297] + "..."
        lines = [
            "REPORT METADATA",
            self._minor_divider(),
            f"{'Report ID:':<24}{report_id}",
            f"{'Analysis Date:':<24}{analysis_date}",
            f"{'Report Version:':<24}{self.report_version}",
            f"{'Methodology:':<24}{self.methodology}",
            f"{'Company:':<24}{company}",
            f"{'Industry:':<24}{industry}",
            f"{'Claim:':<24}{claim}",
            f"{'Workflow:':<24}{workflow_short}",
            f"{'Report Confidence:':<24}{quality.get('report_confidence_level', 'UNKNOWN')}",
            f"{'Quality Warnings:':<24}{len(quality.get('quality_warnings', []))}",
            self._minor_divider(),
        ]
        return "\n".join(lines)

    def _render_evidence_quality_summary(self, evidence: Dict[str, Any]) -> str:
        citations = evidence.get("citations") or []
        total = evidence.get("total_citations", len(citations))
        verifiable = evidence.get("verifiable_citations", 0)

        tier_counts: Dict[str, int] = {}
        for c in citations:
            tier = c.get("reliability_tier", "Unknown")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        lines = [
            f"- Total sources: {total}",
            f"- Verifiable sources (URL + date): {verifiable}",
            "- Reliability tier breakdown:",
        ]

        for tier, count in sorted(tier_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  - {tier}: {count}")

        return "\n".join(lines)

    def _render_government_alignment_section(
        self,
        state: Dict[str, Any],
        evidence: Dict[str, Any],
        agents: Dict[str, Any],
    ) -> str:
        citations = evidence.get("citations") or []

        gov_domains = []
        gov_sources = []
        for c in citations:
            url = str(c.get("url") or "").lower()
            source = str(c.get("source_name") or "")
            if ".gov" in url or "regulatory" in str(c.get("reliability_tier", "")).lower():
                gov_domains.append(url)
                gov_sources.append(source)

        regulatory = agents.get("regulatory_scanning", {}).get("output", {})
        compliance = regulatory.get("compliance_score") if isinstance(regulatory, dict) else None
        gaps = 0
        if isinstance(compliance, dict):
            gaps = int(compliance.get("gaps", 0) or 0)

        gov_count = len(set(gov_sources))
        domain_count = len(set([d for d in gov_domains if d]))

        lines = [
            "**Government / Regulatory Alignment Checks**",
            f"- Regulatory sources referenced in evidence: {gov_count} (unique domains: {domain_count})",
        ]

        if isinstance(compliance, dict):
            lines.append(
                f"- Compliance score: {compliance.get('score', 'N/A')}/100 (gaps: {gaps})"
            )
        else:
            lines.append("- Compliance score: N/A (regulatory scan not available)")

        known_cases = 0
        contradictions = agents.get("contradiction_analysis", {}).get("output", {})
        if isinstance(contradictions, dict):
            known_cases = int(contradictions.get("known_case_matches", 0) or 0)

        if known_cases:
            lines.append(f"- Known-case matches from regulatory database: {known_cases}")
        else:
            lines.append("- Known-case matches from regulatory database: none reported")

        return "\n".join(lines)

    def _render_material_issues_section(self, pillars: Dict[str, Any]) -> str:
        drivers = []
        for key, pillar in pillars.items():
            if not isinstance(pillar, dict):
                continue
            label = pillar.get("label", key)
            factors = pillar.get("factors") or []
            for factor in factors:
                if not isinstance(factor, dict):
                    continue
                points = factor.get("points_contributed")
                if isinstance(points, (int, float)):
                    drivers.append(
                        {
                            "pillar": label,
                            "factor": factor.get("factor", "Unknown"),
                            "points": float(points),
                            "confidence": factor.get("confidence", "Unknown"),
                        }
                    )

        drivers.sort(key=lambda d: d["points"], reverse=True)
        top_drivers = drivers[:6]

        if not top_drivers:
            return "Insufficient factor-level data to rank material issues."

        lines = ["| Pillar | Factor | Points | Confidence |", "|---|---|---|---|"]
        for d in top_drivers:
            lines.append(
                f"| {d['pillar']} | {d['factor']} | {d['points']:.1f} | {d['confidence']} |"
            )

        return "\n".join(lines)

    def _render_section3_score_derivation(
        self,
        scores: Dict[str, Any],
        pillars: Dict[str, Any],
    ) -> str:
        lines: List[str] = []
        gw_score = scores.get("greenwashingriskscore")
        esg_rating = scores.get("esg_rating")
        risk_level = scores.get("risk_level")
        pillar_scores = scores.get("pillar_scores", {}) or {}

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

        # Robustness: if structured factor breakdown is missing, do not show misleading "fallback = 0.0" tables.
        # Instead, present the pillar scores and note the limitation.
        has_any_factors = False
        for p in (pillars or {}).values():
            if isinstance(p, dict) and (p.get("factors") or []):
                has_any_factors = True
                break

        if not has_any_factors and isinstance(pillar_scores, dict) and pillar_scores:
            e = pillar_scores.get("environmental_score")
            s = pillar_scores.get("social_score")
            g = pillar_scores.get("governance_score")
            o = pillar_scores.get("overall_esg_score")
            lines.append("PILLAR SUMMARY (MSCI-style pillar-primary scoring)")
            lines.append("-" * 55)
            lines.append(f"Environmental (E): {e if isinstance(e, (int, float)) else 'N/A'} / 100")
            lines.append(f"Social (S):        {s if isinstance(s, (int, float)) else 'N/A'} / 100")
            lines.append(f"Governance (G):    {g if isinstance(g, (int, float)) else 'N/A'} / 100")
            lines.append(f"Overall ESG:       {o if isinstance(o, (int, float)) else 'N/A'} / 100")
            lines.append("")
            lines.append("Note: Detailed factor-level pillar decomposition was not available for this run;")
            lines.append("the headline pillar scores above reflect the calibrated scoring used for the final rating.")
            return "\n".join(lines)

        for key, p in pillars.items():
            if not isinstance(p, dict):
                p = {}
            label = p.get("label", key)
            score = p.get("score")
            factors = [f for f in (p.get("factors") or []) if isinstance(f, dict)]
            lines.append(f"{label.upper()} PILLAR")
            lines.append("-" * max(20, len(label) + 7))
            if isinstance(score, (int, float)):
                lines.append(f"Pillar score: {score:.1f}/100")
            else:
                lines.append("Pillar score: not available (insufficient data)")

            if not factors:
                lines.append(f"  {'Factor':<36} {'Signal':<12} {'Source':<22} {'Weight':>6} {'Points':>7} {'Confidence':>11}")
                lines.append(f"  {'─' * 90}")
                lines.append(f"  {'Score reconstruction (fallback)':<36} {'N/A':<12} {'Log fallback parser':<22} {'100%':>6} {'0.0':>7} {'Low':>11}")
                lines.append("  Pillar total: 0.0/100")
                lines.append("")
                continue
            lines.append(f"  {'Factor':<36} {'Signal':<12} {'Source':<22} {'Weight':>6} {'Points':>7} {'Confidence':>11}")
            lines.append(f"  {'─' * 90}")
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

                factor = self._shorten_factor_name(factor)

                source_txt = str(f.get('source', 'Unknown'))[:22]
                lines.append(f"  {factor:<36} {raw[:12]:<12} {source_txt:<22} {w_str:>6} {c_str:>7} {confidence:>11}")
            lines.append(f"  {'─' * 90}")
            lines.append(f"  Pillar total: {pillar_total:.1f}/100")
            lines.append("")

        return "\n".join(lines)

    def _render_section4_agent_findings(self, agents: Dict[str, Any]) -> str:
        if not agents:
            return "No agent outputs were available to summarize."

        if not isinstance(agents, dict):
            return "Agent findings payload was malformed and could not be rendered."

        def _as_dict(value: Any) -> Dict[str, Any]:
            return value if isinstance(value, dict) else {}

        def _as_list(value: Any) -> List[Any]:
            return value if isinstance(value, list) else []

        lines: List[str] = []
        for name, info in sorted(agents.items()):
            if not isinstance(info, dict):
                lines.append(f"Agent: {name}")
                lines.append("-" * max(8, len(str(name)) + 7))
                lines.append("Status: MALFORMED OUTPUT | Error: Agent payload was not a structured object")
                lines.append(
                    "This dimension was excluded from the integrated narrative due to malformed agent payload."
                )
                lines.append("")
                continue

            output = info.get("output") or {}
            if not isinstance(output, dict):
                output = {"raw": output}
            error = info.get("error")
            conf = info.get("confidence")
            has_findings = bool(info.get("has_findings")) and not error

            header = f"Agent: {name}"
            lines.append(header)
            lines.append("-" * len(header))
            if error:
                lines.append(f"Status: FAILED | Error: {error}")
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
                contradictions = _as_list(output.get("contradictions"))
                most = _as_dict(output.get("most_severe"))
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
                carbon_data = output
                scope3_display = carbon_data.get("scope3", scope3)
                scope3_corrected = carbon_data.get("scope3_corrected")

                if scope3_corrected:
                    scope3_line = (
                        f"Scope 3    [CORRECTED] ~{scope3_corrected:,.0f} tCO2e  "
                        f"(raw extracted: {scope3_display} - likely "
                        f"{carbon_data.get('scope3_correction_unit','unit')} error, "
                        f"multiplied to tCO2e. Verify against source document.)"
                    )
                else:
                    scope3_line = f"Scope 3    {scope3_display}"
                quality = _as_dict(output.get("data_quality"))
                q_score = quality.get("overall_score") if isinstance(quality, dict) else quality
                q_conf = quality.get("data_confidence", "Unknown") if isinstance(quality, dict) else "Unknown"
                missing = output.get("missing_scopes") or [
                    s for s, v in {"Scope 1": scope1, "Scope 2": scope2, "Scope 3": scope3}.items() if v in (None, "N/A")
                ]
                lines.append(
                    f"The carbon extractor analyzed {output.get('articles_analyzed', 0)} evidence items and {_as_dict(output.get('source_coverage')).get('report_chunks', 0)} report chunks. "
                    f"Scope 1: {scope1 if scope1 is not None else 'NOT DISCLOSED'} tCO2e. Scope 2: {scope2 if scope2 is not None else 'NOT DISCLOSED'} tCO2e. "
                    f"{scope3_line}. Data quality: {q_score if q_score is not None else 'N/A'}/100 ({q_conf} confidence). "
                    f"Missing disclosures: {missing}."
                )
                if scope1 is None and scope2 is None and scope3 is None:
                    lines.append("WARNING — No emissions data found. Net-zero claim cannot be quantitatively evaluated. Greenwashing risk elevated.")
            elif name == "sentiment_analysis":
                claim_sent = output.get("claim_sentiment", "neutral")
                evidence_sent = output.get("evidence_sentiment", "neutral")
                divergence_score = float(output.get("sentiment_divergence", 0) or 0)
                gsi_score = float(output.get("gsi_score", 0) or 0)
                boilerplate = output.get("boilerplate_assessment", {}) if isinstance(output.get("boilerplate_assessment"), dict) else {}
                boilerplate_score = float(boilerplate.get("score", 0) or 0)
                if divergence_score >= 0.4:
                    divergence_label = "High"
                elif divergence_score >= 0.2:
                    divergence_label = "Moderate"
                else:
                    divergence_label = "Low"
                lines.append(
                    f"The sentiment analyzer processed {output.get('articles_analyzed', 0)} external sources. Corporate claim tone: {claim_sent}. "
                    f"External evidence tone: {evidence_sent}. Sentiment divergence: {divergence_label}. "
                    f"Boilerplate language score: {boilerplate_score:.1f}/100. "
                    f"Greenwashing Severity Index (GSI): {gsi_score:.1f}/100. "
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
                claim_a = _as_dict(output.get("claim_analysis"))
                gw = _as_dict(claim_a.get("greenwashing_detection"))
                relevance = _as_dict(claim_a.get("climate_relevance"))
                comp = _as_dict(output.get("comparison"))
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
                overall = _as_dict(output.get("overall_deception_risk"))
                overall_level = overall.get("risk_level")
                greenwishing = _as_dict(output.get("greenwishing")).get("risk_level")
                greenhushing = _as_dict(output.get("greenhushing")).get("risk_level")
                sel_disc = _as_dict(output.get("selective_disclosure")).get("risk_level")
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
                for row in _as_list(output.get("compliance_results")):
                    if not isinstance(row, dict):
                        continue
                    gap_details = row.get("gap_details")
                    if not isinstance(gap_details, list):
                        gap_details = []
                    has_gap = len(gap_details) > 0
                    if has_gap:
                        gap_list.append(f"{row.get('regulation_name')}: {', '.join(gap_details[:1])}")
                    else:
                        compliant.append(row.get("regulation_name"))
                lines.append(
                    f"Regulatory scanning covered {jurisdiction} across {len(_as_list(output.get('applicable_regulations')))} frameworks. "
                    f"Compliance score: {score}/100 (Risk: {risk_level}). Gaps identified: {gaps}. "
                    f"Compliant frameworks: {compliant}. Frameworks with gaps: {gap_list}."
                )
                if gaps:
                    alerts = [r.get("regulation") for r in _as_list(output.get("regulatory_risks")) if isinstance(r, dict)]
                    lines.append(f"Regulatory risk alerts: {alerts}.")
            elif name == "explainability":
                factors = _as_list(output.get("top_factors"))
                p = _as_dict(factors[0]) if len(factors) > 0 else {}
                s = _as_dict(factors[1]) if len(factors) > 1 else {}
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
        if not isinstance(peers, dict):
            peers = {}
        real_peers = peers.get("real_peers") or []
        if not isinstance(real_peers, list):
            real_peers = []
        if len(real_peers) < 2:
            return "Peer comparison unavailable due to insufficient peer data."

        lines: List[str] = []
        lines.append(
            f"The issuer is benchmarked against {len(real_peers)} real peers from the {industry} universe. Synthetic or estimated peers are excluded from this table."
        )
        header = f"{'Company':<28} {'ESG Score':<10} {'Greenwash Score':<16} {'Rating':<8} {'Source':<10}"
        lines.append(header)
        lines.append("-" * len(header))

        for p in real_peers:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name") or p.get("company") or "Peer").strip()[:28]
            esg = p.get("esg_score")
            gw = p.get("greenwashingriskscore")
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

        gw_score = scores.get("greenwashingriskscore")
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

        wrapped: List[str] = []
        for line in lines:
            if not line:
                wrapped.append("")
            else:
                wrapped.append(self._wrap_paragraph(line))

        return "\n".join(wrapped)

    def _render_section7_limitations(self, limitations: List[str]) -> str:
        if not limitations:
            return self._wrap_paragraph(
                "No specific methodological limitations were automatically detected for this run beyond general disclosure and model caveats."
            )

        lines = ["This assessment is subject to the following case-specific limitations:"]
        for idx, item in enumerate(limitations, start=1):
            lines.append(self._wrap_paragraph(f"{idx}. {item}"))
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

    def _generate_validation_metadata_section(self, calibration: Dict[str, Any] = None, company_industry: str = "Unknown") -> str:
        """Add validation & calibration status section."""
        if calibration is None:
            calibration = {}
        cal_state = calibration.get("calibration_status", "NOT_AVAILABLE")
        dataset_size = calibration.get("dataset_size")
        industries_repr = calibration.get("industries_represented") or []
        sector_counts = calibration.get("sector_counts") or {}

        lines = [
            "VALIDATION & CALIBRATION STATUS",
            "─" * 52,
            "This appendix summarizes validation coverage and calibration reliability.",
        ]

        # Ground Truth
        lines.append("")
        lines.append("Ground Truth Validation:")
        if cal_state == "NOT_AVAILABLE":
            lines.append("  Dataset:           Not available — ground truth dataset not found or empty")
            lines.append("  Status:            NOT_AVAILABLE — calibration numbers suppressed")
        else:
            lines.append("  Dataset:           Ground Truth ESG Dataset v1.0")
            lines.append(f"  Verified Cases:    {dataset_size} company-claim pairs with regulatory verdicts")
            lines.append(f"  Status:            {cal_state}")

        # ML Model Performance
        eval_path = os.path.join(os.path.dirname(__file__), '../reports/ml_evaluation_results.json')
        if os.path.exists(eval_path):
            lines.append("")
            lines.append("ML Model Performance (from latest evaluation):")
            with open(eval_path) as f:
                ml = json.load(f)
            best = ml.get('best_model', 'N/A')
            best_f1 = ml.get('best_model_cv_f1', ml.get('best_model_f1', 0))
            dummy_f1 = ml.get('cross_validation_results', {}).get('Dummy', {}).get('f1_mean', 'N/A')
            best_auc = ml.get('holdout_results', {}).get(best, {}).get('auc', 'N/A')
            lines.append(f"  Best Model:        {best} (F1: {best_f1:.3f}, AUC: {best_auc})")
            lines.append(f"  Baseline F1:       {dummy_f1} (majority class)")

        # Score Calibration
        lines.append("")
        lines.append("Score Calibration:")
        spearman_r = calibration.get("spearman_r")
        n_size = calibration.get("dataset_size")
        if cal_state == "NOT_AVAILABLE":
            lines.append("  Spearman r:        Not available — no ground truth data")
            lines.append("  Optimal Threshold: Not available")
        elif isinstance(n_size, int) and n_size < 6:
            lines.append("  Spearman r:        NOT REPORTED (subset n<6 — see system-level reference below)")
            optimal = calibration.get("optimal_threshold")
            if isinstance(optimal, (int, float)):
                lines.append(f"  Optimal Threshold: {optimal:.1f}/100")
            else:
                lines.append("  Optimal Threshold: Not available")
        elif isinstance(spearman_r, (int, float)):
            caveat = "  (small subset, interpret cautiously)" if isinstance(n_size, int) and n_size < 10 else ""
            lines.append(f"  Spearman r:        {spearman_r:.4f} ({cal_state}){caveat}")
            optimal = calibration.get("optimal_threshold")
            if isinstance(optimal, (int, float)):
                lines.append(f"  Optimal Threshold: {optimal:.1f}/100")
            else:
                lines.append("  Optimal Threshold: Not available")
        else:
            lines.append("  Spearman r:        Computation failed")

        # System-level reference for the whole ground-truth dataset.
        sys_n = calibration.get("system_dataset_size")
        sys_r = calibration.get("system_spearman_r")
        sys_p = calibration.get("system_spearman_p")
        if isinstance(sys_n, int) and sys_n > 0 and isinstance(sys_r, (int, float)):
            lines.append("")
            lines.append("System-level reference (whole ground-truth dataset):")
            lines.append(f"  Cases (system):    {sys_n}")
            if isinstance(sys_p, (int, float)):
                lines.append(f"  Spearman r:        {sys_r:.4f}  (p={sys_p:.4f})")
            else:
                lines.append(f"  Spearman r:        {sys_r:.4f}")

        # Company-specific sector note
        if cal_state != "NOT_AVAILABLE" and dataset_size and industries_repr:
            ind_key = company_industry.strip().lower()
            n_sector = 0
            for k, cnt in sector_counts.items():
                if k.strip().lower() == ind_key:
                    n_sector = cnt
                    break
            representativeness = "well-represented" if n_sector >= 3 else "underrepresented"
            industries_str = ", ".join(sorted(set(industries_repr)))
            lines.append("")
            lines.append(f"  Sector Coverage:   {company_industry} has {n_sector}/{dataset_size} cases — {representativeness}")
            lines.append(f"  Industries:        {industries_str}")

        # Contradiction DB
        lines.append("")
        lines.append("Contradiction Database:")
        try:
            from data.known_cases import KNOWN_GREENWASHING_CASES
            lines.append(f"  Known Cases:       {sum(len(v) for v in KNOWN_GREENWASHING_CASES.values())} verified regulatory actions")
        except Exception:
            lines.append("  Known Cases:       Not available")
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
            f"Score breakdown: {compliance.get('score_breakdown', 'N/A')}",
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
            peer_result = state.get("peer_results", {})

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

        # Read actual weights from the materiality profile (not hardcoded)
        dynamic_weights = pillar_scores.get("pillar_weighting", {"E": 0.35, "S": 0.30, "G": 0.35})
        w_e = float(dynamic_weights.get("E", 0.35) or 0.35)
        w_s = float(dynamic_weights.get("S", 0.30) or 0.30)
        w_g = float(dynamic_weights.get("G", 0.35) or 0.35)
        weighting_source = pillar_scores.get("weighting_source", "materiality_profile")

        env_contribution = env_score * w_e
        soc_contribution = soc_score * w_s
        gov_contribution = gov_score * w_g

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
  Weight:                 {w_e:.0%}
  Weighted Contribution:  {env_contribution:.1f} points

  Key Factors:
    • Carbon emissions and climate strategy
    • Energy efficiency and renewable usage
    • Water management and biodiversity impact
    • Waste reduction and circular economy

SOCIAL SCORE:             {soc_score:.1f}/100  ({soc_level})
  Weight:                 {w_s:.0%}
  Weighted Contribution:  {soc_contribution:.1f} points

  Key Factors:
    • Labor practices and employee welfare
    • Diversity, equity, and inclusion (DEI)
    • Community engagement and human rights
    • Product safety and stakeholder relations

GOVERNANCE SCORE:         {gov_score:.1f}/100  ({gov_level})
  Weight:                 {w_g:.0%}
  Weighted Contribution:  {gov_contribution:.1f} points

  Key Factors:
    • Board structure and independence
    • Ethics and compliance frameworks
    • Transparency and disclosure quality
    • Anti-corruption and accountability measures

{'─'*80}
OVERALL ESG SCORE:        {overall_esg:.1f}/100

Calculation:
  (Environmental × {w_e:.2f}) + (Social × {w_s:.2f}) + (Governance × {w_g:.2f})
  ({env_score:.1f} × {w_e:.2f}) + ({soc_score:.1f} × {w_s:.2f}) + ({gov_score:.1f} × {w_g:.2f}) = {overall_esg:.1f}

Weighting source: {weighting_source}
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

        independent_sources_raw = int(quality_metrics.get("independent_sources", 0) or 0)
        premium_sources_raw = int(quality_metrics.get("premium_sources", 0) or 0)
        if total_evidence_sources <= 0:
            total_evidence_sources = max(
                int(quality_metrics.get("total_sources", 0) or 0),
                len(state.get("evidence", []) if isinstance(state.get("evidence", []), list) else []),
                independent_sources_raw,
                premium_sources_raw,
                0,
            )

        independent_sources = min(independent_sources_raw, total_evidence_sources)
        premium_sources = min(premium_sources_raw, total_evidence_sources)
        source_diversity = int(quality_metrics.get("source_diversity", len(source_breakdown)) or 0)
        if independent_sources == 0 or premium_sources == 0 or source_diversity == 0:
            evidence_items = state.get("evidence", []) if isinstance(state.get("evidence"), list) else []
            independent_guess = 0
            premium_guess = 0
            source_types = set()
            company_token = str(state.get("company", "")).lower().split(" ")[0]
            for ev in evidence_items:
                if not isinstance(ev, dict):
                    continue
                src_type = str(ev.get("source_type", "")).strip() or "Unknown"
                source_types.add(src_type)
                url = str(ev.get("url", "")).lower()
                is_first_party = bool(company_token and company_token in url)
                if not is_first_party:
                    independent_guess += 1
                tier = get_reliability_tier(url)
                if tier <= 2:
                    premium_guess += 1
            if independent_sources == 0:
                independent_sources = min(independent_guess, total_evidence_sources)
            if premium_sources == 0:
                premium_sources = min(premium_guess, total_evidence_sources)
            if source_diversity == 0:
                source_diversity = len(source_types)
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
        """Generate a concise diagnostics panel for evidence and offset integrity."""
        diagnostics = self._collect_realism_diagnostics(state)

        evidence_diag = diagnostics.get("evidence_composition", {})
        temporal_diag = diagnostics.get("temporal_reliability", {})

        return f"""
EVIDENCE & OFFSET INTEGRITY
{'─'*80}

Overall Realism Confidence: {"Not available" if diagnostics.get('realism_score', 0) == 0 and diagnostics.get('realism_label', 'unknown') == 'unknown' else f"{diagnostics.get('realism_score', 0)}/100 ({str(diagnostics.get('realism_label', 'unknown')).upper()})"}

Offset Integrity:
  - Classification: {str(diagnostics.get('offset_integrity', 'unknown')).upper()} ({diagnostics.get('offset_status', 'unknown')})
  - Penalty Applied: {diagnostics.get('offset_penalty', 0)} point(s)

Evidence Composition:
  - Total Source Items: {evidence_diag.get('total_evidence_sources', 0)}
  - Independent Sources: {evidence_diag.get('independent_sources', 0)} ({evidence_diag.get('independent_share_pct', 0)}%)
  - Premium Sources: {evidence_diag.get('premium_sources', 0)} ({evidence_diag.get('premium_share_pct', 0)}%)
  - Source Diversity: {evidence_diag.get('source_diversity', 0)} type(s)
  - Evidence Gap Flag: {'YES' if evidence_diag.get('evidence_gap') else 'NO'}

Temporal Reliability:
  - Mode: {temporal_diag.get('mode', 'none')}
  - Weight in Final Scoring: {temporal_diag.get('weight', 0)}
  - Data Quality: {"Not available" if temporal_diag.get('quality_score', 0) == 0 and str(temporal_diag.get('quality_label', 'unknown')).lower() == 'unknown' else f"{temporal_diag.get('quality_score', 0)}/100 ({temporal_diag.get('quality_label', 'unknown')})"}
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

        agents_struct = self._extract_agent_findings(state)
        contradiction_output = agents_struct.get("contradiction_analysis", {}).get("output", {})
        controversy_count = int(contradiction_output.get("contradictions_found", 0))

        evidence_items = state.get("evidence", [])
        total_evidence = len(evidence_items)
        max_possible_sources = 14

        unique_sources = set()
        for ev in evidence_items:
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

            # Only surface missing scopes if they are material in context.
            if missing_scope_rows:
                status = str(carbon_data.get("data_quality", {}).get("status", "")).lower()
                used_baseline = bool(carbon_data.get("used_baseline_estimate", False))
                note_prefix = "Estimated from industry baselines; underlying disclosures are missing for: " if used_baseline else "Missing scope disclosures: "
                # If carbon is non-material to the sector, keep this note out of the main body.
                if v["industry"].lower().replace(" ", "_") in ["oil_and_gas", "coal", "mining", "aviation", "power", "cement", "steel", "energy", "utilities", "banking"]:
                    section += f"\nNote: {note_prefix}{', '.join(missing_scope_rows)}\n"
                else:
                    section += f"\nNote (non-material carbon context): {', '.join(missing_scope_rows)}\n"

            section += "\n"

            total_emissions = emissions.get("total") or carbon_data.get("total_emissions_tco2e")
            if isinstance(total_emissions, dict):
                total_emissions = (
                    total_emissions.get("all_scopes")
                    or total_emissions.get("scope1_2")
                    or total_emissions.get("value")
                )

            # New canonical intensity field is intensity_per_revenue_m_tco2e
            # (tCO2e per million of revenue). Fall back to the legacy
            # carbon_intensity field for back-compat with cached state.
            _im = carbon_data.get("intensity_metrics", {}) or {}
            intensity_per_revenue_m = _im.get("intensity_per_revenue_m_tco2e")
            revenue_currency = _im.get("revenue_currency") or "USD"
            carbon_intensity = (
                carbon_data.get("carbon_intensity")
                or _im.get("carbon_intensity")
            )
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
            # Prefer revenue-normalized intensity (tCO2e per million of
            # revenue) since "Carbon Intensity = total emissions" was
            # meaningless and previously misled readers.
            _rev_source = _im.get("revenue_source") or "unknown"
            _src_label = {
                "financial_analyst": "(financial-analyst data)",
                "report_text_extraction": "(extracted from report text)",
                "curated_table_2024": "(curated 2024 baseline)",
            }.get(_rev_source, "")
            if isinstance(intensity_per_revenue_m, (int, float)) and intensity_per_revenue_m > 0:
                section += (
                    f"Carbon Intensity: {intensity_per_revenue_m:,.1f} tCO2e per million {revenue_currency} "
                    f"of revenue {_src_label}\n"
                )
            elif carbon_intensity and isinstance(carbon_intensity, (int, float)):
                section += f"Carbon Intensity: {carbon_intensity} tCO2e/unit\n"
            elif carbon_intensity:
                section += f"Carbon Intensity: {carbon_intensity}\n"
            else:
                section += "Carbon Intensity: not computed (no revenue denominator available)\n"
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
                status = str(data_quality.get("status", "")).lower()
                if status == "estimated_baseline":
                    section += (
                        f"Data Quality Score: {quality_score}/100 ({confidence} confidence)\n"
                        f"Explanation: No disclosed Scope 1/2/3 values were found; emissions table above reflects "
                        f"industry baseline estimates for stability and should be treated as indicative only.\n"
                    )
                else:
                    section += f"Data Quality Score: {quality_score}/100 ({confidence} confidence)\n"
            else:
                # Only surface a generic 0/None if this is explicitly flagged upstream
                if data_quality not in (None, 0, "N/A"):
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
                    industry_key = v["industry"].lower().replace(" ", "_").replace("&", "and")
                    industry_avg = carbon_benchmarks.get(industry_key, 0.01)
                    status = "Above Avg" if carbon_intensity > industry_avg else "Below Avg"
                    section += f"| {'Carbon Intensity':<30} | {carbon_intensity:.6f} tCO2/${'':>8} | {status:<15} |\n"
                    section += f"| {'  Industry Average':<30} | {industry_avg:.6f} tCO2/${'':>8} | {'':>15} |\n"

                if water_efficiency is not None:
                    water_benchmarks = {
                        "oil_and_gas": 0.002, "energy": 0.0015, "automotive": 0.001,
                        "manufacturing": 0.0008, "food_beverage": 0.003,
                    }
                    industry_key = v["industry"].lower().replace(" ", "_").replace("&", "and")
                    industry_avg = water_benchmarks.get(industry_key, 0.001)
                    status = "Above Avg" if water_efficiency > industry_avg else "Below Avg"
                    section += f"| {'Water Intensity':<30} | {water_efficiency:.6f} L/${'':>10} | {status:<15} |\n"

                if energy_efficiency is not None:
                    energy_benchmarks = {
                        "oil_and_gas": 0.003, "energy": 0.0025, "manufacturing": 0.002,
                        "technology": 0.0008, "finance": 0.0005,
                    }
                    industry_key = v["industry"].lower().replace(" ", "_").replace("&", "and")
                    industry_avg = energy_benchmarks.get(industry_key, 0.0015)
                    status = "Above Avg" if energy_efficiency > industry_avg else "Below Avg"
                    section += f"| {'Energy Intensity':<30} | {energy_efficiency:.6f} kWh/${'':>8} | {status:<15} |\n"

                section += "\n"
                section += "Interpretation:\n"
                section += "  • Lower intensity = Better environmental efficiency\n"
                section += f"  • {v['company']} carbon footprint per revenue dollar\n"
                section += f"  • Benchmarked against {v['industry']} sector averages\n\n"

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

    def generate_json_export(
        self,
        analysis_state: Dict[str, Any],
        report_metadata: Dict[str, Any],
        structured: Dict[str, Any] = None,
        quality: Dict[str, Any] = None,
    ) -> Tuple[str, int]:
        if structured is None:
            structured = self._build_structured_report(analysis_state)
        if quality is None:
            quality = ReportQualityChecker().evaluate(analysis_state, structured)

        scores = structured.get("scores", {}) or {}
        raw_scores = scores.get("raw", {}) if isinstance(scores.get("raw"), dict) else {}
        pillar_scores = scores.get("pillar_scores", {}) if isinstance(scores.get("pillar_scores"), dict) else {}
        evidence_struct = structured.get("evidence", {}) or {}
        agents_struct = structured.get("agents", {}) or {}
        calibration = structured.get("calibration", {}) or {}

        esg_score = raw_scores.get("esg_score")
        if esg_score is None:
            esg_score = raw_scores.get("overall_esg_score") or pillar_scores.get("overall_esg_score")

        carbon_source = (
            analysis_state.get("carbon_results")
            or analysis_state.get("carbon_extraction")
            or {}
        )
        emissions = carbon_source.get("emissions", {}) if isinstance(carbon_source, dict) else {}
        scope1 = emissions.get("scope1", carbon_source.get("scope_1", {})) if isinstance(emissions, dict) else {}
        scope2 = emissions.get("scope2", carbon_source.get("scope_2", {})) if isinstance(emissions, dict) else {}
        scope3 = emissions.get("scope3", carbon_source.get("scope_3", {})) if isinstance(emissions, dict) else {}

        contradiction_output = agents_struct.get("contradiction_analysis", {}).get("output", {})
        contradictions = []
        if isinstance(contradiction_output, dict):
            contradictions = (
                contradiction_output.get("contradictions")
                or contradiction_output.get("specific_contradictions")
                or []
            )

        regulatory = (
            analysis_state.get("regulatory_results")
            or analysis_state.get("regulatory_compliance")
            or {}
        )

        # Canonicalize agent names so duplicates (e.g. claim_extractor / claim_extraction)
        # don't appear as two rows in agent_results.
        _AGENT_NAME_ALIASES = {
            "claim_extractor": "claim_extraction",
        }
        agent_results = []
        _seen_names = set()
        for name, info in sorted(agents_struct.items()):
            canonical_name = _AGENT_NAME_ALIASES.get(name, name)
            if canonical_name in _seen_names:
                continue
            _seen_names.add(canonical_name)
            output = info.get("output") if isinstance(info, dict) else {}
            if not isinstance(output, dict):
                output = {"raw": output}
            # Status enum: SUCCESS only when there is no embedded error in output.
            # An agent that ran but returned `key_findings.error` is operationally FAILED.
            _has_embedded_error = (
                isinstance(output, dict)
                and any(
                    isinstance(output.get(k), str) and str(output.get(k)).strip()
                    for k in ("error", "exception", "failure_reason")
                )
            )
            if info.get("error") or _has_embedded_error:
                status = "FAILED"
            elif info.get("has_findings"):
                status = "SUCCESS"
            else:
                status = "NO_DATA"
            key_findings = {
                k: v
                for k, v in output.items()
                if k not in {"raw_response", "prompt", "status", "confidence"}
                and not isinstance(v, (bytes, type(None)))
            }
            key_findings = self._slim_key_findings(key_findings)
            agent_results.append(
                {
                    "agent": canonical_name,
                    "status": status,
                    "confidence": info.get("confidence"),
                    "key_findings": key_findings,
                }
            )

        risk_scoring_output = (
            agents_struct.get("risk_scoring", {}).get("output", {})
            if isinstance(agents_struct.get("risk_scoring", {}), dict)
            else {}
        )
        if not isinstance(risk_scoring_output, dict):
            risk_scoring_output = {}

        external_meta = risk_scoring_output.get("external_benchmarks", {}) if isinstance(risk_scoring_output.get("external_benchmarks"), dict) else {}
        external_state = analysis_state.get("external_esg_data", {}) if isinstance(analysis_state.get("external_esg_data"), dict) else {}
        external_sources = external_meta.get("sources") if isinstance(external_meta.get("sources"), dict) else external_state.get("sources", {})
        if not isinstance(external_sources, dict):
            external_sources = {}
        external_scores = external_meta.get("scores") if isinstance(external_meta.get("scores"), dict) else external_state.get("scores", {})
        if not isinstance(external_scores, dict):
            external_scores = {}

        pillar_ext_adjustments = pillar_scores.get("external_benchmark_adjustments", []) if isinstance(pillar_scores, dict) else []
        if not isinstance(pillar_ext_adjustments, list):
            pillar_ext_adjustments = []
        pillar_ext_used = bool(pillar_scores.get("external_benchmarks_used", False)) if isinstance(pillar_scores, dict) else False

        # ── Canonical scores: trust report_consistency first ──
        _rc = structured.get("report_consistency", {}) if isinstance(structured.get("report_consistency"), dict) else {}
        if _rc:
            final_gw = float(_rc.get("final_gw_calibrated", 55.0))
            final_esg = float(_rc.get("final_esg_display", 50.0))
            final_rating = str(_rc.get("final_rating", "BBB"))
            final_band = str(_rc.get("final_band", "MODERATE"))
        else:
            final_gw = float(scores.get("greenwashingriskscore", 55.0))
            final_esg = float(esg_score if esg_score is not None else 50.0)
            final_rating = str(scores.get("esg_rating") or scores.get("rating") or "BBB")
            final_band = str(scores.get("risk_level") or "MODERATE")

        # ── Reproducibility metadata: makes the JSON audit-grade ────────────
        # Best-effort git SHA. Never crash the export if git is unavailable.
        _git_sha = None
        try:
            import subprocess as _sp
            _r = _sp.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=2,
            )
            if _r.returncode == 0:
                _git_sha = _r.stdout.strip() or None
        except Exception:
            _git_sha = None
        # Capture model provenance from env first; fall back to whatever the
        # llm_router has registered as defaults so the field is never empty
        # when LLMs were genuinely used.
        _model_versions: Dict[str, Any] = {
            "groq_model": os.environ.get("GROQ_MODEL"),
            "gemini_model": os.environ.get("GEMINI_MODEL"),
            "openrouter_default_model": os.environ.get("OPENROUTER_DEFAULT_MODEL"),
            "openai_model": os.environ.get("OPENAI_MODEL"),
            "anthropic_model": os.environ.get("ANTHROPIC_MODEL"),
        }
        try:
            from core.llm_router import ROUTING_TABLE as _RT  # type: ignore
            if isinstance(_RT, dict):
                for _agent, _chain in _RT.items():
                    if isinstance(_chain, list) and _chain:
                        _primary = _chain[0]
                        _provider = getattr(getattr(_primary, "provider", None), "value", None) or "unknown"
                        _mid = getattr(_primary, "model_id", None)
                        if _mid:
                            _model_versions.setdefault(f"agent.{_agent}", f"{_provider}:{_mid}")
        except Exception:
            pass
        _model_versions = {k: v for k, v in _model_versions.items() if v}
        if not _model_versions:
            # Even with all envs unset, record the fact that the router was
            # invoked so the audit trail isn't a silent {}.
            _model_versions = {"_note": "model identifiers not captured at runtime; check env vars / llm_router config"}
        # Add Python + scoring metadata for reproducibility.
        try:
            import sys as _sys
            _model_versions["python_version"] = _sys.version.split()[0]
        except Exception:
            pass

        export = {
            # Schema/version metadata (audit reproducibility)
            "schema_version": "esg_report_v1.1",
            "pipeline_version": "ESGLens v4.0",
            "git_sha": _git_sha,
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
            "model_versions": _model_versions,
            # Core report fields
            "report_id": report_metadata.get("report_id"),
            "analysis_date": report_metadata.get("analysis_date"),
            "company": analysis_state.get("company"),
            "industry": analysis_state.get("industry"),
            "claim_analyzed": analysis_state.get("claim"),
            "scores": {
                "greenwashingriskscore": final_gw,
                "greenwashing_score_raw": _rc.get("final_gw_raw", risk_scoring_output.get("greenwashingscoreraw")),
                "esg_score": final_esg,
                "esg_rating": final_rating,
                "risk_level": final_band,
                "environmental": pillar_scores.get("environmental_score"),
                "social": pillar_scores.get("social_score"),
                "governance": pillar_scores.get("governance_score"),
                "confidence": scores.get("confidence", analysis_state.get("confidence")),
                "confidence_penalty": risk_scoring_output.get("confidence_penalty"),
                "confidence_penalty_applied": risk_scoring_output.get("confidence_penalty_applied", 0),
                "report_tier": risk_scoring_output.get("report_tier"),
                "score_disclaimer": _rc.get("score_disclaimer", risk_scoring_output.get("score_disclaimer", "")),
                "decision_status": _rc.get("final_decision_status", risk_scoring_output.get("decision_status")),
                "abstain_recommended": _rc.get("final_abstain_recommended", risk_scoring_output.get("abstainrecommended", False)),
                # Mirror the arbitrated decision-block reason (already blanked when
                # abstain_recommended is False by _resolve_decision_state). Fall back
                # to the raw scorer text only if the structured decision is absent.
                "abstention_reason": (
                    (structured.get("decision") or {}).get("abstention_reason", "")
                    or (
                        ""
                        if not (_rc.get("final_abstain_recommended") or risk_scoring_output.get("abstainrecommended"))
                        else _rc.get("abstention_reason", risk_scoring_output.get("abstentionreason", ""))
                    )
                ),
                "historical_archive_quality": risk_scoring_output.get("historical_archive_quality", {}),
                "adversarial_audit": analysis_state.get("adversarial_audit", {}),
                "compliance": regulatory.get("compliance_score"),
            },
            "decision": structured.get("decision") or {},
            "report_consistency": _rc,
            "pillarfactors": raw_scores.get("pillarfactors") or {},
            "contradictions": contradictions,
            "regulatory_gaps": [
                {
                    "regulation": r.get("regulation_name"),
                    "gap_details": r.get("gap_details", []),
                }
                for r in (regulatory.get("compliance_results", []) or [])
                if len(r.get("gap_details", [])) > 0
            ],
            "carbon_data": {
                "scope1": scope1.get("value") if isinstance(scope1, dict) else None,
                "scope2": scope2.get("value") if isinstance(scope2, dict) else None,
                "scope3": scope3.get("total") if isinstance(scope3, dict) else None,
                "data_quality": (
                    safe_get(carbon_source, "data_quality", "overall_score")
                    if isinstance(carbon_source, dict)
                    else None
                ),
            },
            "evidence_sources": [
                {
                    "source_name": parse_source_name(e.get("url", "")) if e.get("source_name") in (None, "Unknown", "") else e.get("source_name"),
                    "url": e.get("url"),
                    "reliability_tier": e.get("reliability_tier"),
                    "stance": e.get("claim_support"),
                    "date_retrieved": e.get("date"),
                }
                for e in (evidence_struct.get("citations", []) or [])
                if isinstance(e, dict)
            ],
            "evidence_records": [
                {
                    "source_name": parse_source_name(e.get("url", "")) if e.get("source_name") in (None, "Unknown", "") else e.get("source_name"),
                    "source": e.get("source"),
                    "url": e.get("url"),
                    "title": e.get("title"),
                    "snippet": e.get("snippet") or e.get("relevant_text"),
                    "relationship_to_claim": e.get("relationship_to_claim") or e.get("claim_support") or e.get("stance"),
                    "reliability_tier": e.get("reliability_tier"),
                    "date": e.get("date") or e.get("date_retrieved"),
                }
                for e in (analysis_state.get("evidence", []) or [])[:1000]
                if isinstance(e, dict)
            ],
            "agent_results": agent_results,
            "calibration": {
                # Deprecated alias kept so older consumers don't break; the
                # honest name is `linguistic_stub_spearman_r`.
                "spearman_r": calibration.get("spearman_r"),
                "spearman_p": calibration.get("spearman_p"),
                "linguistic_stub_spearman_r": calibration.get("linguistic_stub_spearman_r", calibration.get("spearman_r")),
                "linguistic_stub_spearman_p": calibration.get("linguistic_stub_spearman_p", calibration.get("spearman_p")),
                "pipeline_spearman_r": calibration.get("pipeline_spearman_r"),
                "pipeline_spearman_p": calibration.get("pipeline_spearman_p"),
                "calibration_methodology": calibration.get("calibration_methodology",
                    "Sub-sample Spearman of linguistic_greenwashing_score vs ground-truth labels. "
                    "Pipeline correlation is unmeasured."
                ),
                "point_biserial_r": calibration.get("point_biserial_r"),
                "optimal_threshold": calibration.get("optimal_threshold"),
                "dataset_size": calibration.get("dataset_size"),
                "calibration_status": calibration.get("calibration_status"),
                "calibration_label": calibration.get("calibration_label"),
                "render_status": calibration.get("render_status"),
            },
            "external_benchmarks": {
                "enabled": bool(external_meta.get("enabled") or external_state.get("enabled") or external_sources),
                # Only claim "used_in_scoring" when at least one indicator was
                # actually returned AND a pillar adjustment was applied. Otherwise
                # the field is misleading: status reads "Adjusted" while the layer
                # contributed nothing to the headline number.
                "used_in_scoring": bool(
                    pillar_ext_used
                    and int(external_meta.get("wba_indicator_count", external_state.get("wba_indicator_count", 0)) or 0) > 0
                ),
                "sources": external_sources,
                "scores": external_scores,
                "adjustments": pillar_ext_adjustments,
                "wba_company_name": external_meta.get("wba_company_name") or external_state.get("wba_company_name"),
                "wba_indicator_count": external_meta.get("wba_indicator_count", external_state.get("wba_indicator_count", 0)),
                "wba_data_year": external_meta.get("wba_data_year", external_state.get("wba_data_year")),
                "error": external_meta.get("error") or external_state.get("error"),
            },
            "report_generation_log": analysis_state.get("report_generation_log", {
                "status": "success",
                "stages_completed": [],
                "stages_failed": [],
                "warnings": [],
                "duration_seconds": None,
            }),
            "esg_mismatch_analysis": analysis_state.get("esg_mismatch_analysis", {}),
            "report_confidence_level": report_metadata.get("report_confidence", "MEDIUM"),
            "quality_warnings": quality.get("quality_warnings", report_metadata.get("quality_warnings", [])),
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
                "analysis_date": self._coerce_datetime(meta.get("timestamp_dt")).isoformat(),  # FIX: str→datetime safe
                "report_confidence": quality.get("report_confidence_level", "MEDIUM"),
                "quality_warnings": quality.get("quality_warnings", []),
            }
            path, _ = self.generate_json_export(state, report_metadata, structured=structured, quality=quality)
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as exc:
            return json.dumps({"error": "JSON export failed", "detail": str(exc)}, indent=2)

    def _generate_mismatch_section(self, state: Dict[str, Any]) -> str:
        """
        Generate ESG Mismatch Detector analysis section.
        Highlights contradictions between company promises and actual evidence.
        """
        mismatch_data = state.get("esg_mismatch_analysis")
        if not mismatch_data or not isinstance(mismatch_data, dict):
            return "No ESG Promise vs Actual gap analysis was performed for this report."

        lines = [
            "ESG MISMATCH DETECTOR (PROMISE VS ACTUAL PERFORMANCE)",
            "─" * 60,
        ]

        overall_risk = mismatch_data.get("Overall Greenwashing Risk", "Unknown")
        summary = mismatch_data.get("Executive Summary", "No summary available.")
        
        lines.append(f"Overall Mismatch Risk: {overall_risk.upper()}")
        lines.append(f"Summary: {summary}")
        lines.append("")

        future = mismatch_data.get("1. Future Commitments & Progress", [])
        if future:
            lines.append("FUTURE COMMITMENTS & PROGRESS")
            lines.append("─" * 30)
            for idx, item in enumerate(future, start=1):
                lines.append(f"  {idx}. Pledge: {safe_get(item, 'Pledge', default='Unknown')}")
                lines.append(f"     Status:   {safe_get(item, 'Status Trend', default='N/A')}")
                lines.append(f"     Progress: {safe_get(item, 'Progress/Trend', default='N/A')}")
                lines.append(f"     Source:   {safe_get(item, 'Source of Measure', default='N/A')}")
                lines.append("")

        past = mismatch_data.get("2. Past Promise-Implementation Gaps (Mismatches)", [])
        if past and isinstance(past, list) and isinstance(past[0], dict):
            lines.append("PAST PROMISE-IMPLEMENTATION GAPS DETECTED")
            lines.append("─" * 40)
            for idx, item in enumerate(past, start=1):
                lines.append(f"  {idx}. Failed Pledge: {safe_get(item, 'Failed Pledge', default='Unknown')}")
                lines.append(f"     Target:        {safe_get(item, 'Expected Target', default='N/A')}")
                lines.append(f"     Actual Gap:    {safe_get(item, 'Flagged Status', default='N/A')}")
                lines.append(f"     Risk Level:    {safe_get(item, 'Risk Level', default='N/A')}")
                lines.append(f"     Evidence:      {safe_get(item, 'Evidence Source', default='N/A')}")
                lines.append("")
        elif past and isinstance(past, list) and isinstance(past[0], str):
            lines.append(past[0])
            lines.append("")

        # Wrap long lines cleanly
        wrapped_lines = []
        for line in lines:
            if line.startswith("─"):
                wrapped_lines.append(line)
            else:
                wrapped_lines.append("\n".join(textwrap.wrap(line, width=80, subsequent_indent="     " if line.startswith("     ") else "")))

        return "\n".join(wrapped_lines)

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
        
        # 5. FIX APPENDIX B INTERNAL INCONSISTENCY
        if not inconsistency_detected:
            risk_level = "LOW"
            if "moderate inconsistency" in explanation.lower():
                explanation = re.sub(r'(?i)moderate inconsistency', 'no material inconsistency', explanation)
        else:
            if risk_level.upper() in ["LOW", "NONE"]:
                risk_level = "MODERATE" 
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
            score_breakdown = (
                regulatory.get("score_breakdown")
                or (compliance_score.get("score_breakdown") if isinstance(compliance_score, dict) else None)
                or "N/A"
            )

            section += f"Jurisdiction: {jurisdiction}\n"
            section += f"Compliance Score: {compliance_score_value}/100\n"
            section += f"Score breakdown: {score_breakdown}\n"
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

        # === FACT-CENTRIC JUSTIFICATION GRAPH ===
        fact_graph = state.get("fact_graph", {})
        if not isinstance(fact_graph, dict) or not fact_graph:
            risk_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "risk_scoring"]
            if risk_outputs:
                risk_output = risk_outputs[-1].get("output", {})
                if isinstance(risk_output, dict):
                    fact_graph = risk_output.get("fact_graph", {})

        fg_summary = fact_graph.get("summary", {}) if isinstance(fact_graph, dict) else {}
        if isinstance(fg_summary, dict) and fg_summary:
            has_data = True
            section += f"""
FACT-CENTRIC JUSTIFICATION GRAPH
{'â”€'*80}

  â€¢ Total facts extracted: {fg_summary.get('fact_count', 0)}
  â€¢ Verified facts: {fg_summary.get('verified_fact_count', 0)}
  â€¢ Claim-linked facts: {fg_summary.get('claim_linked_fact_count', 0)}
  â€¢ Contradiction facts: {fg_summary.get('contradiction_fact_count', 0)}
  â€¢ Temporal facts: {fg_summary.get('temporal_fact_count', 0)}
  â€¢ Decision-ready graph: {fg_summary.get('is_decision_ready', False)}

"""

        company_kg = state.get("company_knowledge_graph", {})
        if isinstance(company_kg, dict) and company_kg:
            has_data = True
            section += f"""
SYSTEM-WIDE COMPANY KNOWLEDGE GRAPH
{'Ã¢â€â‚¬'*80}

  - Status: {company_kg.get('status', 'UNKNOWN')}
  - Neo4j configured: {company_kg.get('configured', False)}
  - Organization anchor: {company_kg.get('organization_anchor', 'N/A')}
  - Entity count: {company_kg.get('entity_count', 0)}
  - Relationship count: {company_kg.get('relationship_count', 0)}
  - Payload path: {company_kg.get('payload_path', 'N/A')}

"""
            reasoning_paths = company_kg.get("reasoning_paths", [])
            if isinstance(reasoning_paths, list) and reasoning_paths:
                section += "  - Justification paths:\n"
                for path in reasoning_paths[:5]:
                    section += f"    * {path}\n"
                section += "\n"

        # === HISTORICAL ARCHIVE QUALITY ===
        archive_quality = {}
        risk_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "risk_scoring"]
        if risk_outputs:
            risk_output = risk_outputs[-1].get("output", {})
            if isinstance(risk_output, dict):
                archive_quality = risk_output.get("historical_archive_quality", {})

        if isinstance(archive_quality, dict) and archive_quality:
            has_data = True
            section += f"""
HISTORICAL ARCHIVE QUALITY
{'â”€'*80}

  - Snapshot count: {archive_quality.get('snapshot_count', 0)}
  - Archive confidence: {archive_quality.get('archive_confidence', 'N/A')}/100
  - Quality band: {archive_quality.get('archive_quality_band', 'UNKNOWN')}
  - Confidence penalty from archive quality: +{archive_quality.get('archive_penalty_points', 0)} pts

"""

        # === ADVERSARIAL AUDIT FRAMEWORK ===
        adversarial_audit = state.get("adversarial_audit", {})
        if not isinstance(adversarial_audit, dict) or not adversarial_audit:
            audit_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "adversarial_audit"]
            if audit_outputs:
                candidate = audit_outputs[-1].get("output", {})
                if isinstance(candidate, dict):
                    adversarial_audit = candidate

        if isinstance(adversarial_audit, dict) and adversarial_audit:
            has_data = True
            section += f"""
ADVERSARIAL AUDIT FRAMEWORK
{'â”€'*80}

  - Coordination risk: {adversarial_audit.get('coordination_risk', 'N/A')} ({adversarial_audit.get('coordination_risk_band', 'UNKNOWN')})
  - Failed agents: {adversarial_audit.get('failed_agents', 0)}
  - Mean agent confidence: {adversarial_audit.get('mean_agent_confidence', 'N/A')}
  - Confidence spread: {adversarial_audit.get('confidence_spread', 'N/A')}
  - Debate conflict ratio: {adversarial_audit.get('debate_conflict_ratio', 'N/A')}
  - Contradictions observed: {adversarial_audit.get('contradictions_count', 0)}
  - Confidence penalty from coordination risk: +{adversarial_audit.get('confidence_penalty', 0)} pts

"""

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
    import time as _time
    _t0 = _time.time()
    print(f"\n{'== GENERATING PROFESSIONAL REPORT':=^70}")

    # === SAFETY TRIM: guard against operator.add accumulation ===
    raw_outputs = state.get("agent_outputs", [])
    if isinstance(raw_outputs, list) and len(raw_outputs) > 200:
        print(f"⚠️ [RPT] agent_outputs has {len(raw_outputs)} entries — trimming to last 200 (operator.add accumulation)")
        # Keep last unique-by-agent entries within the last 200
        seen, trimmed = set(), []
        for item in reversed(raw_outputs):
            name = item.get("agent", "") if isinstance(item, dict) else ""
            if name not in seen:
                seen.add(name)
                trimmed.append(item)
        state["agent_outputs"] = list(reversed(trimmed))
    print(f"[RPT] agent_outputs count: {len(state.get('agent_outputs', []))}", flush=True)

    print(f"[RPT] Step 1: generate_executive_report...", flush=True)
    generator = ProfessionalReportGenerator()
    professional_report = generator.generate_executive_report(state)
    print(f"[RPT] Step 1 done ({_time.time()-_t0:.1f}s) — {len(professional_report)} chars", flush=True)


    # Never write a bloated report to state — cap it
    if len(professional_report) > 500_000:
        professional_report = professional_report[:500_000] + "\n[TRUNCATED]"

    state["report"] = professional_report

    print(f"[RPT] Step 2: _build_structured_report...", flush=True)
    structured = generator._build_structured_report(state)
    print(f"[RPT] Step 2 done ({_time.time()-_t0:.1f}s)", flush=True)

    print(f"[RPT] Step 3: ReportQualityChecker...", flush=True)
    quality = ReportQualityChecker().evaluate(state, structured)
    print(f"[RPT] Step 3 done ({_time.time()-_t0:.1f}s)", flush=True)

    metadata = {
        "report_id": structured.get("metadata", {}).get("report_id"),
        "analysis_date": ProfessionalReportGenerator._coerce_datetime(  # FIX: str→datetime safe
            structured.get("metadata", {}).get("timestamp_dt")
        ).isoformat(),
        "report_confidence": quality.get("report_confidence_level", "MEDIUM"),
        "quality_warnings": quality.get("quality_warnings", []),
    }

    print(f"[RPT] Step 4: generate_json_export...", flush=True)
    json_path, json_size = generator.generate_json_export(state, metadata)
    print(f"[RPT] Step 4 done ({_time.time()-_t0:.1f}s) — {json_size} chars → {json_path}", flush=True)

    print(f"[RPT] Step 5: reading JSON file...", flush=True)
    with open(json_path, "r", encoding="utf-8") as f:
        state["json_export"] = f.read()
    state["json_export_path"] = json_path
    print(f"[RPT] Step 5 done ({_time.time()-_t0:.1f}s)", flush=True)

    print(f"[RPT] Step 6: fact-graph artifact export...", flush=True)
    try:
        from core.fact_graph_persistence import persist_fact_graph

        fact_graph_payload = state.get("fact_graph", {})
        if isinstance(fact_graph_payload, dict) and fact_graph_payload:
            fact_graph_path = persist_fact_graph(
                fact_graph=fact_graph_payload,
                company=state.get("company", ""),
                report_id=metadata.get("report_id"),
            )
            state["fact_graph_path"] = fact_graph_path
            state["agent_outputs"].append({
                "agent": "fact_graph_persistence",
                "confidence": 0.9,
                "timestamp": datetime.now().isoformat(),
                "output": {
                    "fact_graph_path": fact_graph_path,
                    "node_count": len(fact_graph_payload.get("nodes", []) if isinstance(fact_graph_payload.get("nodes"), list) else []),
                    "edge_count": len(fact_graph_payload.get("edges", []) if isinstance(fact_graph_payload.get("edges"), list) else []),
                },
            })
            print(f"[RPT] Step 6 done ({_time.time()-_t0:.1f}s) -> {fact_graph_path}", flush=True)
        else:
            print(f"[RPT] Step 6 skipped: no fact graph payload available", flush=True)
    except Exception as fact_graph_err:
        print(f"[RPT] Step 6 skipped: {fact_graph_err}", flush=True)

    print(f"[RPT] Step 7: research telemetry log...", flush=True)
    try:
        from core.research_telemetry import extract_run_metrics, append_run_metrics

        run_metrics = extract_run_metrics(
            state=state,
            structured=structured,
            quality=quality,
            json_export_path=json_path,
        )
        telemetry_path = append_run_metrics(run_metrics, log_path="reports/research_runs.jsonl")
        state["research_telemetry"] = run_metrics
        state["research_telemetry_path"] = telemetry_path
        state["agent_outputs"].append({
            "agent": "research_telemetry",
            "confidence": 0.9,
            "timestamp": datetime.now().isoformat(),
            "output": {
                "log_path": telemetry_path,
                "report_id": run_metrics.get("report_id"),
                "abstain_recommended": (run_metrics.get("abstention", {}) or {}).get("abstain_recommended", False),
                "fact_graph_path": state.get("fact_graph_path"),
            },
        })
        print(f"[RPT] Step 7 done ({_time.time()-_t0:.1f}s) -> {telemetry_path}", flush=True)
    except Exception as telemetry_err:
        print(f"[RPT] Step 7 skipped: {telemetry_err}", flush=True)

    print(f"[OK] Professional report generated ({len(professional_report)} characters)")
    print(f"[OK] JSON export generated ({json_size} characters)")

    state["agent_outputs"].append({
        "agent": "professional_report_generation",
        "confidence": 0.95,
        "timestamp": datetime.now().isoformat(),
        "output": {
            "report_id": metadata.get("report_id"),
            "report_confidence": metadata.get("report_confidence"),
            "quality_warnings": metadata.get("quality_warnings", []),
        },
    })

    print(f"[RPT] TOTAL report generation time: {_time.time()-_t0:.1f}s")
    return state
