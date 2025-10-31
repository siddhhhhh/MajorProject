"""
ESG Greenwashing Detection System - LangGraph Version
Maintains compatibility with existing main.py while adding agentic capabilities
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import json

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
        
        # Execute workflow
        try:
            result = self.workflow.invoke(initial_state, config)
            
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
        
        # Save full results (for debugging)
        full_file = f"{base_name}_FULL.json"
        with open(full_file, 'w', encoding='utf-8') as f:
            # Remove non-serializable items
            clean_result = {k: v for k, v in result.items() 
                          if k not in ["professional_report", "json_export"]}
            json.dump(clean_result, f, indent=2, default=str)
        
        print(f"\n💾 Reports saved:")
        print(f"   📄 {txt_file}")
        print(f"   📊 {json_file}")
        print(f"   🔍 {full_file}")
    
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


if __name__ == "__main__":
    if len(sys.argv) > 2:
        # Command line mode: python main_langgraph.py "BP" "Net-zero by 2050"
        company_name = sys.argv[1]
        claim_text = sys.argv[2]
        industry_sector = sys.argv[3] if len(sys.argv) > 3 else None
        quick_analysis(company_name, claim_text, industry_sector)
    else:
        # Interactive mode
        interactive_mode()
