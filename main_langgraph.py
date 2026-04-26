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
from dotenv import load_dotenv
import json

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
    from agents.industry_comparator import initialize_peer_database
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

        initialize_peer_database()
        
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
        if save_full:
            print(f"   🔍 {full_file}")

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
    if args.company and args.claim:
        result = quick_analysis(args.company, args.claim, args.industry)
        if isinstance(result, dict) and result.get("error"):
            _force_exit_if_background_threads(1)
        _force_exit_if_background_threads(0)
    else:
        # Interactive mode if no arguments provided
        interactive_mode()

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

