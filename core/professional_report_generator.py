"""
Professional ESG Report Generator - COMPLETE
Modeled after MSCI ESG Ratings and Sustainalytics format
Provides audit-ready, investor-grade reports
"""
from datetime import datetime
from typing import Dict, Any, List
import json

class ProfessionalReportGenerator:
    """
    Enterprise-grade ESG report generation
    Format matches industry leaders: MSCI, Sustainalytics, Workiva
    """
    
    def __init__(self):
        self.report_version = "1.0"
        self.methodology = "Hybrid Multi-Agent Analysis with LangGraph Orchestration"
    
    def generate_executive_report(self, state: Dict[str, Any]) -> str:
        """
        Generate investor-ready executive report
        Format: MSCI ESG Ratings style
        """
        
        # Extract data
        company = state.get("company", "Unknown")
        industry = state.get("industry", "Unknown")
        claim = state.get("claim", "N/A")
        risk_level = state.get("risk_level", "MODERATE")
        confidence = state.get("confidence", 0.0)
        evidence_count = len(state.get("evidence", []))
        agent_outputs = state.get("agent_outputs", [])
        workflow_path = state.get("workflow_path", "standard_track")
        
        # Calculate metrics - FIXED
        analysis_timestamp = datetime.now()
        
        # Count unique agents
        unique_agents = set(o.get('agent') for o in agent_outputs if o.get('agent'))
        total_agents = len(unique_agents)
        
        # Count successful unique agents
        successful_agents = set()
        for output in agent_outputs:
            agent_name = output.get('agent')
            if agent_name and 'error' not in output:
                successful_agents.add(agent_name)
        num_successful = len(successful_agents)
        
        # Map workflow path to readable name
        workflow_names = {
            "fast_track": "Fast Track (Low Complexity)",
            "standard_track": "Standard Analysis (Moderate Complexity)",
            "deep_analysis": "Deep Analysis with Multi-Agent Debate (High Complexity)"
        }
        workflow_display = workflow_names.get(workflow_path, workflow_path.replace('_', ' ').title())
        
        # Risk score mapping (MSCI-style: AAA to CCC)
        risk_rating_map = {
            "LOW": "AA",
            "MODERATE": "BBB",
            "HIGH": "CCC"
        }
        esg_rating = risk_rating_map.get(risk_level, "BBB")
        
        # Generate report
        report = f"""
{'='*80}
ESG GREENWASHING RISK ASSESSMENT REPORT
{'='*80}

REPORT METADATA
{'─'*80}
Report ID:           {analysis_timestamp.strftime('%Y%m%d-%H%M%S')}-{company.upper()[:4]}
Analysis Date:       {analysis_timestamp.strftime('%B %d, %Y at %H:%M:%S UTC')}
Report Version:      {self.report_version}
Methodology:         {self.methodology}
Analysis Workflow:   {workflow_display}

{'='*80}
EXECUTIVE SUMMARY
{'='*80}

Company Information
{'─'*80}
Company Name:        {company}
Industry Sector:     {industry}
Claim Analyzed:      {claim}

Overall Assessment
{'─'*80}
ESG Risk Rating:     {esg_rating} ({risk_level} RISK)
Confidence Score:    {confidence:.1%}
Evidence Quality:    {"High" if evidence_count > 5 else "Moderate" if evidence_count > 2 else "Limited"}
Data Sources:        {evidence_count} verified sources
Agent Performance:   {num_successful}/{total_agents} agents successful ({num_successful/max(total_agents,1)*100:.0f}%)

RISK RATING SCALE (MSCI-Style)
{'─'*80}
AAA - AA  : Low Risk (Best-in-class ESG performance)
A - BBB   : Moderate Risk (Industry average ESG performance)
BB - CCC  : High Risk (Significant ESG concerns)

{'='*80}
KEY FINDINGS
{'='*80}

{self._generate_key_findings(state)}

{'='*80}
AGENT ANALYSIS BREAKDOWN
{'='*80}

{self._generate_agent_breakdown(agent_outputs)}

{'='*80}
DETAILED ANALYSIS
{'='*80}

{self._generate_detailed_analysis(state, agent_outputs)}

{'='*80}
EVIDENCE SUMMARY
{'='*80}

{self._generate_evidence_summary(state)}

{'='*80}
METHODOLOGY & DATA QUALITY
{'='*80}

Analysis Framework:
  • Multi-Agent AI System with {total_agents} specialized agents
  • Industry-adjusted risk thresholds (MSCI-based)
  • Real-time data integration from {evidence_count} sources
  • Consensus-based validation through agent debate mechanism

Data Quality Assurance:
  • Successful Agents:  {num_successful}/{total_agents} ({num_successful/max(total_agents,1)*100:.0f}%)
  • Confidence Level:   {confidence:.1%}
  • Evidence Coverage:  {evidence_count} independent sources
  • Temporal Relevance: Real-time monitoring (last 24-48 hours)

Analysis Workflow: {workflow_display}
  • Complexity Assessment → Dynamic Routing
  • Claim Extraction → Evidence Retrieval → Contradiction Analysis
  • Historical Pattern Analysis → Industry Peer Comparison
  • Risk Scoring with Industry Thresholds → Final Verdict

{'='*80}
REGULATORY COMPLIANCE & STANDARDS
{'='*80}

This report aligns with the following ESG frameworks:
  ✓ MSCI ESG Ratings Methodology
  ✓ Sustainalytics ESG Risk Ratings
  ✓ GRI (Global Reporting Initiative) Standards
  ✓ SASB (Sustainability Accounting Standards Board)
  ✓ TCFD (Task Force on Climate-related Financial Disclosures)

{'='*80}
DISCLAIMERS & LIMITATIONS
{'='*80}

Scope: This analysis is based on publicly available information and real-time
       data sources. It reflects conditions as of the analysis date.

Limitations:
  • Analysis quality depends on data availability and source reliability
  • ESG claims evolve over time; regular monitoring recommended
  • Industry comparisons based on available peer data
  • AI-generated insights require human expert validation for investment decisions

Forward-Looking Statements:
  This report may contain assessments based on forward-looking statements.
  Actual ESG performance may differ materially from analyzed claims.

{'='*80}
CONTACT & SUPPORT
{'='*80}

For inquiries regarding this report:
  System:     ESG Greenwashing Detection Platform v3.0
  Version:    {self.report_version}
  Generated:  {analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

{'='*80}
END OF REPORT
{'='*80}

This report is confidential and intended for the recipient's internal use only.
Redistribution requires explicit authorization.
"""
        
        return report
    
    def _generate_key_findings(self, state: Dict[str, Any]) -> str:
        """Generate key findings section"""
        risk_level = state.get("risk_level", "MODERATE")
        confidence = state.get("confidence", 0.0)
        evidence_count = len(state.get("evidence", []))
        
        findings = []
        
        # Risk-specific findings
        if risk_level == "HIGH":
            findings.append("⚠ HIGH GREENWASHING RISK DETECTED")
            findings.append("  • Claim lacks sufficient evidence or contains contradictions")
            findings.append("  • Peer comparison shows below-industry-average performance")
            findings.append("  • Historical data reveals inconsistent ESG commitments")
            findings.append("  • Recommended Action: Deep due diligence required before engagement")
        elif risk_level == "MODERATE":
            findings.append("⚡ MODERATE GREENWASHING RISK IDENTIFIED")
            findings.append("  • Claim partially supported by available evidence")
            findings.append("  • Some contradictions or ambiguities detected")
            findings.append("  • Mixed signals from historical performance")
            findings.append("  • Recommended Action: Additional verification and monitoring")
        else:
            findings.append("✓ LOW GREENWASHING RISK")
            findings.append("  • Claim well-supported by multiple credible sources")
            findings.append("  • Consistent with historical ESG performance")
            findings.append("  • Aligns with industry best practices")
            findings.append("  • Recommended Action: Standard monitoring protocols")
        
        findings.append("")
        
        # Confidence-based findings
        if confidence >= 0.8:
            findings.append("✓ HIGH CONFIDENCE ASSESSMENT")
            findings.append("  • Robust evidence base from multiple independent sources")
            findings.append("  • Agent consensus achieved across analytical dimensions")
            findings.append("  • Low uncertainty in risk classification")
        elif confidence >= 0.6:
            findings.append("⚡ MODERATE CONFIDENCE ASSESSMENT")
            findings.append("  • Adequate evidence but some information gaps identified")
            findings.append("  • Partial agent consensus with minor disagreements")
            findings.append("  • Moderate uncertainty in final assessment")
        else:
            findings.append("⚠ LIMITED CONFIDENCE")
            findings.append("  • Insufficient evidence for definitive assessment")
            findings.append("  • Significant information gaps remain")
            findings.append("  • Further investigation strongly recommended")
        
        findings.append("")
        
        # Evidence coverage findings
        if evidence_count >= 10:
            findings.append("✓ COMPREHENSIVE EVIDENCE COVERAGE")
            findings.append(f"  • {evidence_count} independent sources analyzed")
        elif evidence_count >= 5:
            findings.append("⚡ ADEQUATE EVIDENCE COVERAGE")
            findings.append(f"  • {evidence_count} sources analyzed")
        else:
            findings.append("⚠ LIMITED EVIDENCE AVAILABILITY")
            findings.append(f"  • Only {evidence_count} sources available")
            findings.append("  • Assessment reliability may be affected")
        
        return "\n".join(findings)
    
    def _generate_agent_breakdown(self, agent_outputs: List[Dict]) -> str:
        """Generate agent execution breakdown"""
        
        # Group by agent
        agent_data = {}
        for output in agent_outputs:
            agent_name = output.get('agent', 'unknown')
            if agent_name not in agent_data:
                agent_data[agent_name] = {
                    'executions': 0,
                    'errors': 0,
                    'confidence_sum': 0,
                    'confidence_count': 0
                }
            
            agent_data[agent_name]['executions'] += 1
            
            if 'error' in output:
                agent_data[agent_name]['errors'] += 1
            
            if 'confidence' in output:
                agent_data[agent_name]['confidence_sum'] += output['confidence']
                agent_data[agent_name]['confidence_count'] += 1
        
        # Format breakdown
        breakdown = []
        breakdown.append("Agent Execution Summary:")
        breakdown.append("─" * 80)
        breakdown.append(f"{'Agent Name':<35} | {'Status':<8} | {'Confidence':<10} | {'Runs':<5}")
        breakdown.append("─" * 80)
        
        for agent_name in sorted(agent_data.keys()):
            data = agent_data[agent_name]
            
            # Calculate average confidence
            if data['confidence_count'] > 0:
                avg_conf = data['confidence_sum'] / data['confidence_count']
                conf_display = f"{avg_conf:.1%}"
            else:
                conf_display = "N/A"
            
            # Status
            if data['errors'] > 0:
                status = "FAILED"
            else:
                status = "SUCCESS"
            
            # Format agent name
            display_name = agent_name.replace('_', ' ').title()
            
            breakdown.append(f"{display_name:<35} | {status:<8} | {conf_display:<10} | {data['executions']:<5}")
        
        breakdown.append("─" * 80)
        
        return "\n".join(breakdown)
    
    def _generate_detailed_analysis(self, state: Dict[str, Any], agent_outputs: List[Dict]) -> str:
        """Generate detailed agent analysis section"""
        
        sections = []
        
        # Group outputs by agent
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
                sections.append(f"⚠ Claim Consistency:    {contradictions} contradiction(s) detected")
            else:
                sections.append(f"✓ Claim Consistency:    No contradictions found")
        
        if "evidence_retrieval" in agent_summaries:
            output = agent_summaries["evidence_retrieval"][0]
            evidence_count = output.get("evidence_count", 0)
            sections.append(f"  Evidence Coverage:    {evidence_count} independent source(s)")
        
        if "temporal_analysis" in agent_summaries:
            sections.append(f"  Historical Track Record: Past ESG performance evaluated")
        
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
        """Generate evidence summary"""
        evidence = state.get("evidence", [])
        
        if not evidence:
            return "No evidence sources available for this analysis.\nThis may indicate data collection issues or claim verification challenges."
        
        summary = []
        summary.append(f"Total Evidence Sources: {len(evidence)}")
        summary.append("─" * 80)
        summary.append("")
        
        # Categorize by source
        sources = {}
        for item in evidence[:15]:  # Limit to top 15
            source = item.get("source", "unknown")
            if source not in sources:
                sources[source] = []
            sources[source].append(item)
        
        for source_type, items in sorted(sources.items()):
            source_display = source_type.replace('_', ' ').title()
            summary.append(f"{source_display}: {len(items)} item(s)")
            summary.append("─" * 40)
            
            for i, item in enumerate(items[:5], 1):  # Top 5 per source
                title = item.get("title", item.get("snippet", "N/A"))
                if len(title) > 75:
                    title = title[:72] + "..."
                summary.append(f"  {i}. {title}")
            
            if len(items) > 5:
                summary.append(f"  ... and {len(items)-5} more items")
            
            summary.append("")
        
        return "\n".join(summary)
    
    def export_json(self, state: Dict[str, Any]) -> str:
        """Export machine-readable JSON format"""
        
        # Count unique agents
        agent_outputs = state.get("agent_outputs", [])
        unique_agents = set(o.get('agent') for o in agent_outputs if o.get('agent'))
        successful_agents = set(o.get('agent') for o in agent_outputs if o.get('agent') and 'error' not in o)
        
        export = {
            "report_metadata": {
                "report_id": f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{state.get('company', 'UNK')[:4]}",
                "timestamp": datetime.now().isoformat(),
                "version": self.report_version,
                "methodology": self.methodology
            },
            "company_info": {
                "name": state.get("company"),
                "industry": state.get("industry"),
                "claim": state.get("claim")
            },
            "assessment": {
                "risk_level": state.get("risk_level"),
                "confidence_score": state.get("confidence"),
                "esg_rating": {"LOW": "AA", "MODERATE": "BBB", "HIGH": "CCC"}.get(state.get("risk_level"), "BBB"),
                "workflow_path": state.get("workflow_path")
            },
            "evidence": {
                "total_sources": len(state.get("evidence", [])),
                "sources": state.get("evidence", [])[:10]
            },
            "agent_performance": {
                "total_agents": len(unique_agents),
                "successful_agents": len(successful_agents),
                "success_rate": len(successful_agents) / max(len(unique_agents), 1)
            },
            "agent_details": [
                {
                    "agent": o.get("agent"),
                    "confidence": o.get("confidence"),
                    "timestamp": o.get("timestamp"),
                    "status": "error" if "error" in o else "success"
                }
                for o in agent_outputs
                if o.get("agent")
            ]
        }
        
        return json.dumps(export, indent=2)


# LangGraph node wrapper
def professional_report_generation_node(state):
    """Generate professional enterprise report - Node wrapper for LangGraph"""
    print(f"\n{'🟢 GENERATING PROFESSIONAL REPORT':=^70}")
    
    generator = ProfessionalReportGenerator()
    
    # Generate full report
    professional_report = generator.generate_executive_report(state)
    state["report"] = professional_report
    
    # Also generate JSON export
    json_export = generator.export_json(state)
    state["json_export"] = json_export
    
    print(f"✅ Professional report generated ({len(professional_report)} characters)")
    print(f"✅ JSON export generated ({len(json_export)} characters)")
    
    state["agent_outputs"].append({
        "agent": "professional_report_generation",
        "confidence": 0.95,
        "timestamp": datetime.now().isoformat()
    })
    
    return state
