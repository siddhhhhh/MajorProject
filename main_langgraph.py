"""
ESG Greenwashing Detection System - LangGraph Version
Maintains compatibility with existing main.py while adding agentic capabilities
"""
import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import sys
import argparse
import threading
import warnings
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import json

# ── Unified pipeline log (project_root/pipeline.log) ────────────────────────
# Every print() and stderr write, every Python `logging` record, every
# uncaught traceback is appended here. Multiple runs accumulate in one file
# with session headers so the user can hand me the WHOLE thing and I see
# exactly where each run died.
_PROJECT_ROOT = Path(__file__).resolve().parent
_PIPELINE_LOG_PATH = _PROJECT_ROOT / "pipeline.log"

# Opt-in: pipeline.log TeeStream wraps stdout/stderr with a per-line flush
# to disk. Useful for debugging slow/stuck runs but adds a small per-print
# disk sync that can slow import-heavy phases when packages emit thousands
# of stderr warnings. Default OFF so it doesn't slow normal runs.
# Set `ESG_PIPELINE_LOG=1` to enable for a debugging session.
_PIPELINE_LOG_FH = None
if os.environ.get("ESG_PIPELINE_LOG", "").lower() in ("1", "true", "yes"):
    try:
        _PIPELINE_LOG_FH = open(_PIPELINE_LOG_PATH, "a", encoding="utf-8", buffering=1)
        _PIPELINE_LOG_FH.write(f"\n{'='*80}\n")
        _PIPELINE_LOG_FH.write(
            f"PIPELINE RUN START  {datetime.now().isoformat(timespec='seconds')}\n"
        )
        _PIPELINE_LOG_FH.write(f"  pid : {os.getpid()}\n")
        _PIPELINE_LOG_FH.write(f"  argv: {sys.argv}\n")
        _PIPELINE_LOG_FH.write(f"  cwd : {os.getcwd()}\n")
        _PIPELINE_LOG_FH.write(f"{'='*80}\n")
        _PIPELINE_LOG_FH.flush()

        class _TeeStream:
            """Mirror writes to console AND to pipeline.log."""
            def __init__(self, console, logfile):
                self._console = console
                self._logfile = logfile
            def write(self, s):
                try:
                    self._console.write(s)
                    self._console.flush()
                except Exception:
                    pass
                try:
                    self._logfile.write(s)
                    self._logfile.flush()
                except Exception:
                    pass
            def flush(self):
                try: self._console.flush()
                except Exception: pass
                try: self._logfile.flush()
                except Exception: pass
            def isatty(self): return False
            def __getattr__(self, name):
                return getattr(self._console, name)

        sys.stdout = _TeeStream(sys.__stdout__, _PIPELINE_LOG_FH)
        sys.stderr = _TeeStream(sys.__stderr__, _PIPELINE_LOG_FH)

        import logging as _logging
        _root_logger = _logging.getLogger()
        if not any(getattr(h, "_pipeline_log_handler", False) for h in _root_logger.handlers):
            _h = _logging.StreamHandler(sys.stdout)
            _h.setLevel(_logging.INFO)
            _h.setFormatter(_logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            ))
            _h._pipeline_log_handler = True  # type: ignore[attr-defined]
            _root_logger.addHandler(_h)
            if _root_logger.level > _logging.INFO or _root_logger.level == _logging.NOTSET:
                _root_logger.setLevel(_logging.INFO)
    except Exception as _log_setup_exc:
        _PIPELINE_LOG_FH = None
        print(f"[pipeline.log setup failed: {_log_setup_exc}]", file=sys.__stderr__)

# Install forensic crash trap BEFORE heavy imports so allocations are tracked
# from process start. Silent crashes (OOM-kill, segfault) will leave evidence
# in logs/forensic_<pid>_<ts>.log — RSS over time, top allocation sites,
# stack tracebacks of every thread at the moment of death.
try:
    if os.getenv("ESG_FORENSIC_TRAP", "0").lower() in {"1", "true", "yes"}:
        from core.forensic_trap import install as _install_forensic_trap, report_exception as _report_forensic_exception
        _FORENSIC_LOG_PATH = _install_forensic_trap()
    else:
        _FORENSIC_LOG_PATH = None
        def _report_forensic_exception(exc):  # type: ignore
            pass
except Exception:  # never block startup on instrumentation failure
    _FORENSIC_LOG_PATH = None
    def _report_forensic_exception(exc):  # type: ignore
        pass

# ── Suppress known dependency warning flood ─────────────────────────────
# These are safe to ignore and pollute demo output.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="fitz")      # PyMuPDF
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pymupdf")
warnings.filterwarnings("ignore", message=".*RequestsDependencyWarning.*")          # requests/urllib3
warnings.filterwarnings("ignore", message=".*urllib3.*")
warnings.filterwarnings("ignore", message=".*chardet.*")
warnings.filterwarnings("ignore", category=FutureWarning, module="xgboost")
warnings.filterwarnings("ignore", category=UserWarning, module="tensorflow")
warnings.filterwarnings("ignore", category=UserWarning, module="keras")
# ────────────────────────────────────────────────────────────────────────


def _configure_utf8_console() -> None:
    """Avoid Windows cp1252 crashes when logs include non-ASCII characters."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Logging setup should never block startup.
        pass


_configure_utf8_console()

if sys.version_info < (3, 11):
    print("WARNING: Python 3.11+ recommended. Current:", sys.version)

load_dotenv()

# Check which orchestration to use
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "true").lower() == "true"

if USE_LANGGRAPH:
    from core.workflow_phase2 import build_phase2_graph
    from core.professional_report_generator import ProfessionalReportGenerator

class ESGGreenwashingDetectorLangGraph:
    """
    LangGraph-Powered ESG Analysis
    Enterprise-grade with dynamic routing, debate mechanism, and professional reports
    """
    
    def __init__(self):
        print("\n" + "="*80)
        print("🌱 ESG GREENWASHING DETECTION SYSTEM v3.0 (LangGraph)")
        print("Agentic AI | Dynamic Routing | Multi-Agent Debate | Professional Reports")
        print("="*80)

        if os.getenv("ESG_INIT_PEER_DB", "0").lower() in {"1", "true", "yes"}:
            try:
                from agents.industry_comparator import initialize_peer_database
                initialize_peer_database()
            except Exception as exc:
                print(f"[PeerDB] Initialization skipped: {exc}")
        
        if not USE_LANGGRAPH:
            print("⚠️  LangGraph disabled. Use main.py instead.")
            return
        
        print("\n✅ Building LangGraph workflow with 11 agents...")
        self.workflow = build_phase2_graph()
        self.report_generator = ProfessionalReportGenerator()
        print("✅ LangGraph system ready\n")
    
    def analyze_company(self, company_name: str, claim: str, 
                       industry: str = None,
                       save_reports: bool = True) -> dict:
        """
        Analyze company ESG claim using LangGraph agentic system
        
        Args:
            company_name: Company to analyze
            claim: ESG claim to verify
            industry: Industry sector (auto-detected if None)
            save_reports: Save professional reports to disk
        
        Returns:
            Complete analysis results with professional report
        """
        
        # Auto-detect industry
        if not industry:
            industry = self._detect_industry(company_name)
        
        print("\n" + "="*80)
        print(f"🔍 ANALYZING: {company_name}")
        print("="*80)
        print(f"📋 Claim: {claim}")
        print(f"🏢 Industry: {industry}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Initialize state
        initial_state = {
            "claim": claim,
            "company": company_name,
            "industry": industry,
            "complexity_score": 0.0,
            "workflow_path": "",
            "evidence": [],
            "confidence": 0.0,
            "risk_level": "",
            "agent_outputs": [],
            "iteration_count": 0,
            "needs_revision": False,
            "financial_context": None,  # From Financial Analyst (Agent #14)
            "ml_prediction": None,  # From XGBoost risk model
            "indian_financials": None,  # From IndianFinancialData
            "company_reports": None,  # From CompanyReportFetcher
            "carbon_extraction": None,  # Scope 1/2/3 carbon analysis
            "greenwishing_analysis": None,  # NEW: Greenwishing/greenhushing detection
            "regulatory_compliance": None,  # NEW: Regulatory horizon scanning
            "climatebert_analysis": None,  # NEW: ClimateBERT NLP analysis
            "claim_decomposition": None,  # NEW: Compound claim decomposition + tensions
            "adversarial_triangulation": None,  # NEW: Evidence triangulation output
            "carbon_pathway_analysis": None,  # NEW: 1.5C/Net-zero pathway modelling
            "commitment_ledger": None,  # NEW: Longitudinal commitments and revisions
            "social_analysis": None,  # NEW: dedicated social pillar analysis
            "governance_analysis": None,  # NEW: dedicated governance pillar analysis
            "explainability_report": None,  # NEW: SHAP/LIME explanations
            "final_verdict": {},
            "report": ""
        }
        
        config = {
            "configurable": {"thread_id": f"analysis-{company_name}-{int(__import__('time').time())}"},
            "recursion_limit": 50
        }
        
        print("\n🚀 Running LangGraph workflow...")
        print("⏳ Estimated time: 60-120 seconds (live API calls)")
        print("─" * 80)
        
        # Execute workflow with configurable timeout and graceful fallback.
        import concurrent.futures
        WORKFLOW_TIMEOUT = int(os.getenv("ESG_WORKFLOW_TIMEOUT", "1800"))  # default 30 min
        ALLOW_PARTIAL_ON_TIMEOUT = os.getenv("ESG_ALLOW_PARTIAL_ON_TIMEOUT", "1").lower() in {"1", "true", "yes"}
        try:
            _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            _future = _executor.submit(self.workflow.invoke, initial_state, config)
            try:
                timeout_arg = WORKFLOW_TIMEOUT if WORKFLOW_TIMEOUT > 0 else None
                result = _future.result(timeout=timeout_arg)
                _executor.shutdown(wait=True)
            except concurrent.futures.TimeoutError:
                print(f"\n⚠️  Workflow timed out after {WORKFLOW_TIMEOUT}s. Cancelling background task...")
                _future.cancel()
                _executor.shutdown(wait=False, cancel_futures=True)

                if not ALLOW_PARTIAL_ON_TIMEOUT:
                    raise TimeoutError(f"Analysis timed out after {max(1, WORKFLOW_TIMEOUT // 60)} minutes")

                # Return a bounded partial result so callers still receive a report artifact.
                result = dict(initial_state)
                result["workflow_timeout"] = True
                result["timeout_seconds"] = WORKFLOW_TIMEOUT
                result["final_verdict"] = {
                    "status": "TIMEOUT_PARTIAL",
                    "message": f"Workflow exceeded timeout ({WORKFLOW_TIMEOUT}s); generated partial output.",
                }
            
            print("\n" + "="*80)
            print("✅ LANGGRAPH ANALYSIS COMPLETE")
            print("="*80)
            
            # Generate professional report
            professional_report = self.report_generator.generate_executive_report(result)
            result["professional_report"] = professional_report
            
            # Generate JSON export
            json_export = self.report_generator.export_json(result)
            result["json_export"] = json_export
            
            # Save reports
            if save_reports:
                self._save_reports(result, company_name)
            
            # Display summary
            self._display_summary(result)
            
            print(f"\n⏰ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            return result
            
        except Exception as e:
            print(f"\n❌ Analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
    
    def _detect_industry(self, company_name: str) -> str:
        """Auto-detect industry from company name"""
        industry_map = {
            # Energy
            "bp": "Energy", "shell": "Energy", "exxon": "Energy", 
            "chevron": "Energy", "conocophillips": "Energy",
            
            # Technology
            "microsoft": "Technology", "apple": "Technology", "google": "Technology",
            "amazon": "Technology", "meta": "Technology", "facebook": "Technology",
            
            # Consumer Goods
            "coca-cola": "Consumer Goods", "pepsi": "Consumer Goods",
            "unilever": "Consumer Goods", "procter": "Consumer Goods",
            "nike": "Consumer Goods", "adidas": "Consumer Goods",
            
            # Automotive
            "tesla": "Automotive", "volkswagen": "Automotive", "ford": "Automotive",
            "gm": "Automotive", "toyota": "Automotive",
            
            # Financial
            "jpmorgan": "Financial Services", "goldman": "Financial Services",
            "bank of america": "Financial Services", "wells fargo": "Financial Services",
            
            # Healthcare
            "pfizer": "Healthcare", "johnson": "Healthcare", "moderna": "Healthcare"
        }
        
        company_lower = company_name.lower()
        for key, industry in industry_map.items():
            if key in company_lower:
                return industry
        
        return "General"
    
    def _save_reports(self, result: dict, company_name: str):
        """Save professional reports to disk"""
        os.makedirs("reports", exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"reports/ESG_Report_{company_name.replace(' ', '_')}_{timestamp}"
        
        # Save text report
        txt_file = f"{base_name}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(result["professional_report"])
        
        # Save JSON export
        json_file = f"{base_name}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(result["json_export"])

        # One-page investor brief: structured JSON for portfolio/diligence
        # use cases. Investors won't read 47KB TXT reports — they need a
        # decision-grade summary they can paste into a model or an IC memo.
        brief_file = f"{base_name}_brief.json"
        try:
            brief = self._build_investor_brief(result, company_name)
            with open(brief_file, 'w', encoding='utf-8') as f:
                json.dump(brief, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"⚠️ Investor brief generation failed: {exc}")
            brief_file = None

        # Save full results only when explicitly enabled to avoid large blocking writes.
        full_file = f"{base_name}_FULL.json"
        save_full = os.getenv("ESG_SAVE_FULL_RESULTS", "0").lower() in {"1", "true", "yes"}
        if save_full:
            try:
                with open(full_file, 'w', encoding='utf-8') as f:
                    clean_result = {
                        k: self._to_json_safe(v)
                        for k, v in result.items()
                        if k not in ["professional_report", "json_export"]
                    }
                    json.dump(clean_result, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"⚠️ Skipped full debug JSON export: {e}")
        
        # ── Lineage diagnostic dump (Step 4) ──────────────────────────────────
        lineage = result.get("esg_score_lineage")
        if lineage and isinstance(lineage, dict):
            lineage_file = f"reports/debug_esg_lineage_{company_name.replace(' ', '_')}.json"
            try:
                with open(lineage_file, 'w', encoding='utf-8') as f:
                    json.dump(lineage, f, indent=2, default=str)
                print(f"\n🔬 Lineage saved → {lineage_file}")
            except Exception as e:
                print(f"⚠️ Lineage dump failed: {e}")

        print(f"\n💾 Reports saved:")
        print(f"   📄 {txt_file}")
        print(f"   📊 {json_file}")
        if brief_file:
            print(f"   📋 {brief_file}")
        if save_full:
            print(f"   🔍 {full_file}")

    def _build_investor_brief(self, result: dict, company_name: str) -> dict:
        """Build a one-page investor brief from the full result.

        Decision-grade snapshot — six sections an analyst can scan in
        under a minute: header, headline scores, top 3 risks,
        enforcement Y/N, carbon pathway status, three due-diligence
        questions to ask management.

        Pulls from json_export first (canonical, post-render values)
        then falls back to runtime state. Without this the brief showed
        null scores because the runtime keys differ from the rendered
        JSON keys.
        """
        # Parse the rendered JSON for canonical scores
        rendered: dict = {}
        try:
            if result.get("json_export"):
                rendered = json.loads(result["json_export"])
        except Exception:
            rendered = {}
        rendered_scores = rendered.get("scores") or {}

        verdict = result.get("verdict") or result.get("final_verdict") or {}
        carbon = (
            result.get("carbon_extraction")
            or rendered.get("carbon_data")
            or {}
        )
        if not carbon:
            for ao in (result.get("agent_outputs") or []):
                if isinstance(ao, dict) and ao.get("agent") in ("carbon_extraction", "Carbon Extraction"):
                    _co = ao.get("output") or {}
                    if isinstance(_co, dict):
                        carbon = _co
                        break
        emissions = (carbon.get("emissions") or {}) if isinstance(carbon, dict) else {}

        # Headline scores: prefer rendered JSON values (post-calibration,
        # post-cap) over raw runtime state.
        gw_score = (
            rendered_scores.get("greenwashingriskscore")
            or rendered_scores.get("greenwashing_score_raw")
            or verdict.get("greenwashing_risk_score")
            or verdict.get("gw_score")
            or (result.get("risk_scoring") or {}).get("greenwashing_risk_score")
        )
        esg_score = (
            rendered_scores.get("esg_score")
            or verdict.get("esg_score")
            or (result.get("risk_scoring") or {}).get("esg_score")
        )
        risk_band = (
            rendered_scores.get("risk_level")
            or verdict.get("risk_band")
            or verdict.get("risk_level")
            or "UNKNOWN"
        )
        confidence_pct = (
            rendered_scores.get("confidence")
            or verdict.get("confidence_pct")
            or verdict.get("confidence")
        )
        if isinstance(confidence_pct, float) and confidence_pct < 1.0:
            # 0.65 → 65.0 — render as percentage
            confidence_pct = round(confidence_pct * 100, 1)

        # Top 3 risks from key_risk_drivers / findings / decision summary
        risk_drivers: list = []
        for source in (
            verdict.get("key_risk_drivers"),
            verdict.get("risk_drivers"),
            (rendered.get("decision") or {}).get("key_risk_drivers"),
            rendered.get("key_risk_drivers"),
        ):
            if isinstance(source, list):
                for d in source[:3]:
                    if isinstance(d, dict):
                        risk_drivers.append({
                            "title": d.get("title") or d.get("name") or d.get("driver") or "Risk driver",
                            "impact": d.get("impact"),
                            "direction": d.get("direction"),
                        })
                    elif isinstance(d, str):
                        risk_drivers.append({"title": d})
                if risk_drivers:
                    break

        # Last-resort: pull from contradictions
        if not risk_drivers:
            contras = rendered.get("contradictions") or []
            if isinstance(contras, list):
                for c in contras[:3]:
                    if isinstance(c, dict):
                        risk_drivers.append({
                            "title": str(c.get("statement") or c.get("description") or "Contradiction")[:140],
                            "impact": str(c.get("severity") or "MEDIUM"),
                        })

        # Enforcement detection
        regulatory = result.get("regulatory_compliance") or {}
        compliance = regulatory.get("compliance_result") or {}
        active_litigation_count = 0
        enforcement_summary = []
        for fr in (compliance.get("frameworks") or []):
            if not isinstance(fr, dict):
                continue
            if (
                fr.get("status") == "active_enforcement"
                or "active enforcement" in str(fr.get("framework", "")).lower()
            ):
                active_litigation_count += 1
                enforcement_summary.append({
                    "framework": fr.get("framework"),
                    "violation": (fr.get("specific_violation") or "")[:160],
                    "url": fr.get("evidence_url"),
                })

        # Carbon pathway
        pathway = result.get("carbon_pathway") or {}
        if not pathway:
            for ao in (result.get("agent_outputs") or []):
                if isinstance(ao, dict) and ao.get("agent") in ("carbon_pathway_analysis", "Carbon Pathway Analysis"):
                    _po = ao.get("output") or {}
                    if isinstance(_po, dict):
                        pathway = _po
                        break

        # Three due-diligence questions tailored to detected gaps
        dd_questions: list[str] = []
        if (carbon.get("net_zero_target") or "").lower().startswith(("not declared", "carbon negative")):
            dd_questions.append(
                "Has management published interim milestones (5-year + 10-year) tied to "
                "the headline climate commitment, with binding capital-allocation triggers?"
            )
        if active_litigation_count > 0:
            dd_questions.append(
                f"What is the current status of the {active_litigation_count} active "
                f"climate-related enforcement matter(s) and what is the worst-case provision?"
            )
        if isinstance(emissions.get("scope3"), dict) and not (emissions["scope3"].get("total") or emissions["scope3"].get("value")):
            dd_questions.append(
                "Why is Scope 3 not disclosed at the GHG Protocol 15-category level? "
                "When will the company close this disclosure gap?"
            )
        # Pad to three with generic critical questions
        generic_dd = [
            "Has the SBTi-validated near-term target been independently re-verified within the last 18 months?",
            "What proportion of executive long-term incentive compensation is tied to ESG metrics, and which metrics specifically?",
            "Which independent third-party assurance provider audits Scope 1, 2, and 3 disclosures?",
        ]
        for q in generic_dd:
            if len(dd_questions) >= 3:
                break
            if q not in dd_questions:
                dd_questions.append(q)

        # LLM-variance bands from the canonical scores dict (Section 5).
        gw_band = rendered_scores.get("greenwashing_band")
        esg_band = rendered_scores.get("esg_band")
        confidence_band = rendered_scores.get("confidence_band")
        band_meta = rendered_scores.get("band_meta")

        headline_block = {
            "greenwashing_risk_score": gw_score,
            "esg_score": esg_score,
            "risk_band": risk_band,
            "confidence_pct": confidence_pct,
        }
        # Fix #18: When ABSTAIN_RECOMMENDED, surface an explicit display
        # string so machine consumers (dashboards, downstream pipelines)
        # see the demotion without re-deriving it from abstention_summary.
        # Numeric stays in greenwashing_risk_score for backward compat.
        abstain_flag = (
            (rendered.get("decision") or {}).get("abstain_recommended")
            or rendered_scores.get("abstain_recommended")
            or (verdict.get("decision_status") == "ABSTAIN_RECOMMENDED")
        )
        if abstain_flag:
            headline_block["abstain_recommended"] = True
            headline_block["greenwashing_risk_score_display"] = (
                f"ABSTAINED (indicative only: {gw_score:.1f})"
                if isinstance(gw_score, (int, float))
                else "ABSTAINED"
            )
        if gw_band:
            headline_block["greenwashing_risk_score_band"] = gw_band
        if esg_band:
            headline_block["esg_score_band"] = esg_band
        if confidence_band:
            headline_block["confidence_pct_band"] = confidence_band
        if band_meta:
            headline_block["band_meta"] = band_meta

        # Emissions verification (Climate TRACE) — surfaced on the brief so
        # diligence readers see the inflation/underreport flag without
        # opening the full report.
        emissions_verif_raw = result.get("emissions_verification") or {}
        if not isinstance(emissions_verif_raw, dict):
            emissions_verif_raw = {}
        emissions_verif_brief = {
            "status": emissions_verif_raw.get("status"),
            "disclosed_scope1_tco2e": emissions_verif_raw.get("disclosed_scope1_tco2e"),
            "observed_scope1_tco2e_assets": emissions_verif_raw.get("observed_scope1_tco2e_assets"),
            "ratio_disclosed_over_observed_assets": emissions_verif_raw.get(
                "ratio_disclosed_over_observed_assets"
            ),
            "matched_asset_count": len(emissions_verif_raw.get("matched_assets") or []),
            "rationale": emissions_verif_raw.get("rationale"),
            "source": "climate-trace",
        } if emissions_verif_raw.get("status") else None

        # Score attribution top-N for the brief — diligence "why this score"
        # in one glance. Falls back to live decompose() if export didn't
        # pre-compute it.
        attribution_brief = None
        try:
            attr = rendered.get("score_attribution")
            if not isinstance(attr, dict) or not attr or attr.get("error"):
                from core.score_attribution import decompose
                attr = decompose(rendered if rendered else result)
            attribution_brief = {
                "top_positive": [
                    {"name": c.get("display_name"),
                     "delta": c.get("delta"),
                     "category": c.get("category")}
                    for c in (attr.get("top_contributors_positive") or [])[:5]
                ],
                "top_negative": [
                    {"name": c.get("display_name"),
                     "delta": c.get("delta"),
                     "category": c.get("category")}
                    for c in (attr.get("top_contributors_negative") or [])[:3]
                ],
                "totals": attr.get("totals"),
                "reconciles": attr.get("reconciles"),
            }
        except Exception as _att_exc:
            attribution_brief = {"error": str(_att_exc)[:160]}

        return {
            "schema_version": "1.0",
            "company": company_name,
            "report_id": rendered.get("report_id") or verdict.get("report_id"),
            "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "headline": headline_block,
            "emissions_verification": emissions_verif_brief,
            "score_attribution": attribution_brief,
            "abstention_summary": (
                {
                    "total_subclaims": (rendered.get("abstention_analysis") or {}).get("total_subclaims"),
                    "abstained_count": (rendered.get("abstention_analysis") or {}).get("abstained_count"),
                    "abstention_rate_pct": (rendered.get("abstention_analysis") or {}).get("abstention_rate_pct"),
                }
                if isinstance(rendered.get("abstention_analysis"), dict) else None
            ),
            "counterfactual_scenarios": (
                [
                    {
                        "name": s.get("name"),
                        "description": s.get("description"),
                        "new_headline_gw": (s.get("result") or {}).get("new_headline_gw"),
                        "delta": (s.get("result") or {}).get("delta"),
                        "new_band": (s.get("result") or {}).get("new_band"),
                    }
                    for s in (rendered.get("counterfactual") or {}).get("prebaked_scenarios") or []
                ]
                if isinstance(rendered.get("counterfactual"), dict) else []
            ),
            "entity_record": rendered_scores.get("entity_record") or rendered.get("entity_record"),
            "carbon_snapshot": {
                "scope1_tco2e": (emissions.get("scope1") or {}).get("value") if isinstance(emissions.get("scope1"), dict) else None,
                "scope2_tco2e": (emissions.get("scope2") or {}).get("value") if isinstance(emissions.get("scope2"), dict) else None,
                "scope3_tco2e": (emissions.get("scope3") or {}).get("total") if isinstance(emissions.get("scope3"), dict) else None,
                "renewable_energy_pct": carbon.get("renewable_energy_percentage"),
                "net_zero_target": carbon.get("net_zero_target"),
                "sbti_status": carbon.get("sbti_status"),
                "pathway_alignment": (pathway or {}).get("alignment_status") or (pathway or {}).get("status"),
            },
            "top_risks": risk_drivers[:3],
            "enforcement": {
                "active_count": active_litigation_count,
                "items": enforcement_summary[:5],
            },
            "due_diligence_questions": dd_questions[:3],
            "report_files": {
                "txt": f"{result.get('_report_basename', 'see_disk')}.txt",
                "json": f"{result.get('_report_basename', 'see_disk')}.json",
            },
        }

    def _to_json_safe(self, value, depth: int = 0, max_depth: int = 5, max_items: int = 200):
        """Convert nested runtime objects into bounded JSON-safe structures."""
        if depth >= max_depth:
            return "<truncated>"

        if isinstance(value, (str, int, float, bool)) or value is None:
            return value

        if isinstance(value, dict):
            items = list(value.items())[:max_items]
            out = {str(k): self._to_json_safe(v, depth + 1, max_depth, max_items) for k, v in items}
            if len(value) > max_items:
                out["_truncated_keys"] = len(value) - max_items
            return out

        if isinstance(value, (list, tuple, set)):
            items = list(value)[:max_items]
            out = [self._to_json_safe(v, depth + 1, max_depth, max_items) for v in items]
            if len(value) > max_items:
                out.append({"_truncated_items": len(value) - max_items})
            return out

        return str(value)
    
    def _display_summary(self, result: dict):
        """Display executive summary - FIXED deduplication"""
        print("\n" + "="*80)
        print("📊 EXECUTIVE SUMMARY")
        print("="*80)
        
        # Basic info
        print(f"\n🏢 Company: {result['company']}")
        print(f"🏭 Industry: {result['industry']}")
        print(f"📋 Claim: {result['claim'][:100]}{'...' if len(result['claim']) > 100 else ''}")
        
        # Risk assessment
        # AFTER: Read from final_verdict (most authoritative source)
        final_verdict = result.get('final_verdict', {})

        # Use final_verdict values if present, fall back to state values
        risk_level = final_verdict.get('risk_level') or result.get('risk_level', 'N/A')
        confidence = final_verdict.get('final_confidence') or result.get('confidence', 0.0)

        
        risk_colors = {
            "HIGH": "🔴",
            "MODERATE": "🟡",
            "LOW": "🟢"
        }
        color = risk_colors.get(risk_level, "⚪")
        
        print(f"\n{color} Risk Level: {risk_level}")
        print(f"📈 Confidence: {confidence:.1%}")
        
        # Workflow details
        workflow_path = result.get('workflow_path', '')
        if workflow_path:
            workflow_names = {
                "fast_track": "Fast Track (Low Complexity)",
                "standard_track": "Standard Analysis (Moderate Complexity)", 
                "deep_analysis": "Deep Analysis with Multi-Agent Debate (High Complexity)"
            }
            workflow_display = workflow_names.get(workflow_path, workflow_path.replace('_', ' ').title())
            print(f"🔀 Analysis Path: {workflow_display}")
        
        # Evidence summary
        evidence_count = len(result.get('evidence', []))
        print(f"📚 Evidence Sources: {evidence_count}")
        
        # FIXED: Deduplicate agent outputs for display
        agent_outputs = result.get('agent_outputs', [])
        
        # Remove duplicates by creating unique key from agent+timestamp
        unique_outputs = {}
        for output in agent_outputs:
            agent_name = output.get('agent')
            timestamp = output.get('timestamp', 'none')
            unique_key = f"{agent_name}_{timestamp}"
            
            # Keep only first occurrence
            if unique_key not in unique_outputs:
                unique_outputs[unique_key] = output
        
        unique_outputs_list = list(unique_outputs.values())
        
        # Count unique agents
        unique_agents = set(o.get('agent') for o in unique_outputs_list if o.get('agent'))
        total_agents = len(unique_agents)
        
        # Count successful agents (without errors)
        successful_agents = set()
        for output in unique_outputs_list:
            agent_name = output.get('agent')
            if agent_name and 'error' not in output:
                successful_agents.add(agent_name)
        
        num_successful = len(successful_agents)
        
        print(f"\n🤖 Agents Executed: {total_agents}")
        print(f"✅ Successful: {num_successful}/{total_agents} ({num_successful/max(total_agents,1)*100:.0f}%)")
        
        # Show agent list with status
        if unique_agents:
            print(f"\n📋 Agents Used:")
            for agent in sorted(unique_agents):
                # Check if agent had any errors
                had_error = any('error' in o for o in unique_outputs_list if o.get('agent') == agent)
                status = "❌" if had_error else "✅"
                print(f"   {status} {agent.replace('_', ' ').title()}")
        
        # Check for debate
        debate_outputs = [o for o in unique_outputs_list if o.get('agent') == 'debate_orchestrator']
        if debate_outputs:
            print(f"\n🗣️  Multi-Agent Debate: ACTIVATED")
            for debate in debate_outputs:
                if debate.get('action') == 'conflict_detected':
                    conflicting = debate.get('conflicting_agents', [])
                    print(f"   Conflicting agents: {', '.join(conflicting)}")
                elif debate.get('action') == 'no_conflict_detected':
                    print(f"   All agents in agreement - debate skipped")
        
        # FIXED: Show actual processing steps (deduplicated)
        print(f"\n⏱️  Total Processing Steps: {len(unique_outputs_list)}")
        
        print("\n" + "="*80)




def interactive_mode():
    """Interactive CLI with LangGraph"""
    detector = ESGGreenwashingDetectorLangGraph()
    
    while True:
        print("\n" + "="*80)
        print("🌱 ESG GREENWASHING DETECTOR v3.0 - LangGraph Mode")
        print("="*80)
        
        company = input("\n🏢 Enter company name (or 'quit' to exit): ").strip()
        
        if company.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Thank you for using ESG Greenwashing Detector!")
            break
        
        if not company:
            print("❌ Company name cannot be empty")
            continue
        
        claim = input("📋 Enter ESG claim to verify: ").strip()
        
        if not claim:
            print("❌ Claim cannot be empty")
            continue
        
        industry = input("🏭 Enter industry (or press Enter to auto-detect): ").strip() or None
        
        try:
            detector.analyze_company(company, claim, industry)
        except Exception as e:
            print(f"\n❌ Analysis failed: {e}")
            import traceback
            traceback.print_exc()
        
        cont = input("\n\n🔄 Analyze another company? (y/n): ").strip().lower()
        if cont != 'y':
            print("\n👋 Thank you!")
            break


def quick_analysis(company: str, claim: str, industry: str = None):
    """Quick analysis for programmatic use"""
    detector = ESGGreenwashingDetectorLangGraph()
    return detector.analyze_company(company, claim, industry)


def _force_exit_if_background_threads(exit_code: int = 0):
    """Force process termination for CLI runs if background threads keep interpreter alive."""
    if os.getenv("ESG_FORCE_EXIT", "1").lower() not in {"1", "true", "yes"}:
        return

    live_threads = [
        t for t in threading.enumerate()
        if t is not threading.main_thread() and t.is_alive()
    ]

    if live_threads:
        print("\n⚠️ Background threads detected after completion; forcing clean process exit for CLI run.")

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(exit_code))


if __name__ == "__main__":
    # Setup argument parser for named arguments
    parser = argparse.ArgumentParser(
        description='ESG Greenwashing Detection System v3.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main_langgraph.py --company "ExxonMobil" --claim "carbon neutral by 2050" --industry "Oil & Gas"
  python main_langgraph.py --company "Tesla" --claim "100%% renewable energy" --industry "Automotive"
  python main_langgraph.py  (interactive mode)
        """
    )
    
    parser.add_argument('--company', type=str, help='Company name to analyze')
    parser.add_argument('--claim', type=str, help='ESG claim to verify')
    parser.add_argument('--industry', type=str, help='Industry sector (optional, auto-detected if not provided)')
    
    args = parser.parse_args()
    
    # If company and claim are provided, run analysis
    try:
        if args.company and args.claim:
            result = quick_analysis(args.company, args.claim, args.industry)
            if isinstance(result, dict) and result.get("error"):
                _force_exit_if_background_threads(1)
            _force_exit_if_background_threads(0)
        else:
            # Interactive mode if no arguments provided
            interactive_mode()
    except BaseException as _exc:
        _report_forensic_exception(_exc)
        raise

# ============================================================================
# API WRAPPER FUNCTION FOR TESTING & INTEGRATION
# ============================================================================

def run_esg_analysis(company: str, claim: str, industry: str) -> dict:
    """
    Wrapper function to run ESG analysis programmatically
    
    Args:
        company: Company name (e.g., "Tesla")
        claim: ESG claim to analyze (e.g., "Carbon neutral by 2030")
        industry: Industry sector (e.g., "Automotive")
    
    Returns:
        dict with keys:
            - company: str
            - claim: str
            - industry: str
            - risk_level: str (HIGH/MODERATE/LOW)
            - confidence: float (0-100)
            - evidence_count: int
            - agent_outputs: list
            - final_verdict: dict
            - report_path: str (if generated)
    """
    import sys
    from datetime import datetime
    
    print(f"\n{'='*80}")
    print(f"🏢 COMPANY: {company}")
    print(f"📋 CLAIM: {claim}")
    print(f"🏭 INDUSTRY: {industry}")
    print(f"{'='*80}\n")
    
    # Initialize state
    initial_state = {
        "company": company,
        "claim": claim,
        "industry": industry,
        "claims": [],
        "evidence": [],
        "agent_outputs": [],
        "risk_level": "UNKNOWN",
        "confidence": 0.0,
        "complexity_score": 0.0,
        "workflow_path": "standard_track",
        "needs_revision": False,
        "iteration_count": 0,
        "financial_context": None,
        "ml_prediction": None,
        "indian_financials": None,  # NEW: From IndianFinancialData
        "company_reports": None,  # NEW: From CompanyReportFetcher
        "final_verdict": {},
        "report": ""
    }
    
    try:
        # Build and compile graph
        # Build graph (already compiled)
        print("🔧 Building LangGraph workflow...")
        app = build_phase2_graph()
        print("✅ Workflow ready\n")
        
        # Run the graph with configurable timeout and graceful fallback.
        import concurrent.futures
        WORKFLOW_TIMEOUT = int(os.getenv("ESG_WORKFLOW_TIMEOUT", "1800"))
        ALLOW_PARTIAL_ON_TIMEOUT = os.getenv("ESG_ALLOW_PARTIAL_ON_TIMEOUT", "1").lower() in {"1", "true", "yes"}
        print("🚀 Starting agent execution...\n")
        final_state = None

        def _run_stream():
            _final = None
            for step_output in app.stream(initial_state):
                if isinstance(step_output, dict):
                    for node_name, node_output in step_output.items():
                        if node_name != "__end__":
                            print(f"   ⚙️  {node_name}")
                    _final = node_output
            return _final

        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        _future = _executor.submit(_run_stream)
        try:
            timeout_arg = WORKFLOW_TIMEOUT if WORKFLOW_TIMEOUT > 0 else None
            final_state = _future.result(timeout=timeout_arg)
            _executor.shutdown(wait=True)
        except concurrent.futures.TimeoutError:
            print(f"\n⚠️  Workflow timed out after {WORKFLOW_TIMEOUT}s. Cancelling background task...")
            _future.cancel()
            _executor.shutdown(wait=False, cancel_futures=True)

            if not ALLOW_PARTIAL_ON_TIMEOUT:
                raise TimeoutError(f"Analysis timed out after {max(1, WORKFLOW_TIMEOUT // 60)} minutes")

            final_state = dict(initial_state)
            final_state["workflow_timeout"] = True
            final_state["timeout_seconds"] = WORKFLOW_TIMEOUT
            final_state["final_verdict"] = {
                "status": "TIMEOUT_PARTIAL",
                "message": f"Workflow exceeded timeout ({WORKFLOW_TIMEOUT}s); generated partial output.",
            }

        if final_state is None:
            final_state = initial_state

        
        print("\n✅ All agents completed!\n")
        
        # Generate report
        print("📄 Generating report...")
        report_gen = ProfessionalReportGenerator()
        
        # Generate professional report
        professional_report = report_gen.generate_executive_report(final_state)
        
        # Save report to file
        os.makedirs("reports", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"reports/ESG_Report_{company.replace(' ', '_')}_{timestamp}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(professional_report)
        
        print(f"✅ Report saved: {report_path}\n")
        
        # Extract results
        result = {
            "company": final_state.get("company", company),
            "claim": final_state.get("claim", claim),
            "industry": final_state.get("industry", industry),
            "risk_level": final_state.get("risk_level", "UNKNOWN"),
            "confidence": final_state.get("confidence", 0.0) * 100,  # Convert to percentage
            "evidence_count": len(final_state.get("evidence", [])),
            "agent_outputs": final_state.get("agent_outputs", []),
            "final_verdict": final_state.get("final_verdict", {}),
            "report_path": report_path,
            "workflow_path": final_state.get("workflow_path", "unknown"),
            "complexity_score": final_state.get("complexity_score", 0.0)
        }
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "company": company,
            "claim": claim,
            "industry": industry,
            "risk_level": "ERROR",
            "confidence": 0.0,
            "evidence_count": 0,
            "agent_outputs": [],
            "final_verdict": {"error": str(e)},
            "report_path": None
        }

