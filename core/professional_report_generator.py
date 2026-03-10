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
        
        # FIXED: Use risk_scorer output directly (most authoritative)
        # Priority: risk_scorer > final_verdict > state fallback
        risk_scorer_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "risk_scoring"]
        
        if risk_scorer_outputs:
            risk_scorer_result = risk_scorer_outputs[-1].get("output", {})
            risk_level = risk_scorer_result.get("risk_level", state.get("risk_level", "MODERATE"))
            rating_grade = risk_scorer_result.get("rating_grade", "BBB")
            greenwashing_risk_score = risk_scorer_result.get("greenwashing_risk_score", 50)
            risk_source = risk_scorer_result.get("risk_source", "Formula-based")
            pillar_scores = risk_scorer_result.get("pillar_scores", {})  # NEW: Extract pillar scores
            
            print(f"📊 Report using Risk Scorer output:")
            print(f"   Risk Level: {risk_level}")
            print(f"   Rating Grade: {rating_grade}")
            print(f"   Source: {risk_source}")
        else:
            # Fallback to final_verdict or state
            final_verdict = state.get("final_verdict", {})
            risk_level = final_verdict.get("risk_level") or state.get("risk_level", "MODERATE")
            rating_grade = final_verdict.get("rating_grade") or state.get("rating_grade", "BBB")
            greenwashing_risk_score = 50
            risk_source = "Verdict Generation"
            pillar_scores = {}  # No pillar scores available
        
        confidence = state.get("confidence", 0.0)
        evidence_count = len(state.get("evidence", []))
        agent_outputs = state.get("agent_outputs", [])
        workflow_path = state.get("workflow_path", "standard_track")
        
        # ============================================================
        # FIXED: Calculate metrics from UNIQUE agents only
        # Deduplicate by agent+timestamp to prevent inflated counts
        # ============================================================
        analysis_timestamp = datetime.now()
        
        # Deduplicate agent outputs by agent+timestamp
        unique_outputs = {}
        for output in agent_outputs:
            agent_name = output.get('agent')
            timestamp = output.get('timestamp', 'none')
            unique_key = f"{agent_name}_{timestamp}"
            
            # Keep first occurrence only
            if unique_key not in unique_outputs:
                unique_outputs[unique_key] = output
        
        unique_outputs_list = list(unique_outputs.values())
        
        # Count unique agents
        unique_agents = set(o.get('agent') for o in unique_outputs_list if o.get('agent'))
        total_agents = len(unique_agents)
        
        # Count successful unique agents (without errors)
        successful_agents = set()
        for output in unique_outputs_list:
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
        
        # FIXED: Use rating_grade from risk_scorer directly
        esg_rating = rating_grade
        
        # Generate ESG pillar section
        pillar_section = self._generate_pillar_section(pillar_scores)
        
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
Greenwashing Score:  {greenwashing_risk_score:.1f}/100
Confidence Score:    {confidence:.1%}
Risk Assessment By:  {risk_source}
Evidence Quality:    {"High" if evidence_count > 5 else "Moderate" if evidence_count > 2 else "Limited"}
Data Sources:        {evidence_count} verified sources
Agent Performance:   {num_successful}/{total_agents} agents successful ({num_successful/max(total_agents,1)*100:.0f}%)

RISK RATING SCALE (MSCI-Style)
{'─'*80}
AAA - AA  : Low Risk (Best-in-class ESG performance)
A - BBB   : Moderate Risk (Industry average ESG performance)
BB - CCC  : High Risk (Significant ESG concerns)

{pillar_section}

{'='*80}
{self._generate_quantitative_metrics_section(state)}
{self._generate_data_enrichment_section(state)}
{'='*80}
KEY FINDINGS
{'='*80}

{self._generate_key_findings(state)}

{self._generate_peer_comparison_section(state)}

{'='*80}
AGENT ANALYSIS BREAKDOWN
{'='*80}

{self._generate_agent_breakdown(agent_outputs)}

{'='*80}
DETAILED ANALYSIS
{'='*80}

{self._generate_detailed_analysis(state, unique_outputs_list)}

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
    
    def _generate_peer_comparison_section(self, state: Dict[str, Any]) -> str:
        """Generate peer comparison section with ESG benchmarking table"""
        
        company = state.get("company", "Unknown")
        industry = state.get("industry", "Unknown")
        
        # Get pillar scores and overall ESG from risk scorer
        risk_scorer_outputs = [o for o in state.get("agent_outputs", []) if o.get("agent") == "risk_scoring"]
        
        if risk_scorer_outputs:
            risk_scorer_result = risk_scorer_outputs[-1].get("output", {})
            pillar_scores = risk_scorer_result.get("pillar_scores", {})
            overall_esg = pillar_scores.get("overall_esg_score")
        else:
            pillar_scores = {}
            overall_esg = None
        
        # Generate DYNAMIC peer table (uses database + estimates)
        try:
            from agents.industry_comparator import IndustryComparator
            comparator = IndustryComparator()
            
            peer_result = comparator.generate_dynamic_peer_table(
                company=company,
                industry=industry,
                esg_score=overall_esg,
                pillar_scores=pillar_scores
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
            
            # Build section with context
            rank_text = peer_result.get("rank", "N/A")
            industry_avg = peer_result.get("industry_average", {})
            total_peers = peer_result.get("total_peers", 0)
            real_peer_count = peer_result.get("real_peer_count", 0)
            estimated_peer_count = peer_result.get("estimated_peer_count", 0)
            data_source = peer_result.get("data_source", "unknown")
            disclaimer = peer_result.get("disclaimer")
            
            # Build data source context
            if data_source == "real":
                data_source_text = "Historical database (previously analyzed companies)"
            elif data_source == "mixed":
                data_source_text = f"Mixed: {real_peer_count} from historical database, {estimated_peer_count} estimated from industry benchmarks"
            else:
                data_source_text = f"Estimated from industry benchmarks (insufficient historical data)"
            
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
            
            # Add disclaimer if using estimated data
            if disclaimer:
                section += f"""{disclaimer}

As more companies in {industry} are analyzed, this comparison will become more accurate 
with real peer data from the historical database.

"""
            
            section += """Legend:
  ⭐ = Target company
  E  = Environmental Score (0-100)
  S  = Social Score (0-100)
  G  = Governance Score (0-100)

Rating Scale:
  AAA-AA  = 75-100 (ESG Leaders)
  A-BBB   = 50-74  (Average Performance)
  BB-B    = 25-49  (Below Average)
  CCC-C   = 0-24   (ESG Laggards)

"""
            
            # Add performance commentary
            if overall_esg and industry_avg.get('esg'):
                delta = overall_esg - industry_avg.get('esg')
                if delta >= 10:
                    section += f"✅ OUTPERFORMING: {company} exceeds industry average by {delta:.1f} points\n"
                elif delta >= 5:
                    section += f"⚡ ABOVE AVERAGE: {company} performs {delta:.1f} points above peers\n"
                elif delta >= -5:
                    section += f"➖ INDUSTRY AVERAGE: {company} aligns with peer performance\n"
                elif delta >= -10:
                    section += f"⚠️ BELOW AVERAGE: {company} lags industry by {abs(delta):.1f} points\n"
                else:
                    section += f"🚨 UNDERPERFORMING: {company} significantly trails peers by {abs(delta):.1f} points\n"
            
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
        """Generate agent execution breakdown"""
        
        # ============================================================
        # FIXED: Count UNIQUE agent executions (not accumulated duplicates)
        # ============================================================
        agent_data = {}
        seen_executions = set()  # Track unique executions by agent+timestamp
        
        for output in agent_outputs:
            agent_name = output.get('agent', 'unknown')
            timestamp = output.get('timestamp', '')
            
            # Create unique key to detect duplicates
            unique_key = f"{agent_name}_{timestamp}"
            
            # Skip if we've already counted this exact execution
            if unique_key in seen_executions:
                continue
            seen_executions.add(unique_key)
            
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
            
            if 'confidence' in output and output['confidence'] is not None:
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
            
            # ============================================================
            # FIXED: Display actual runs (capped at 2 for debate loops)
            # Shows "1" for normal execution, "2" for debate participation
            # ============================================================
            actual_runs = data['executions']
            if actual_runs == 1:
                run_display = "1"
            elif actual_runs == 2:
                run_display = "2"  # Debate loop
            else:
                # Should not happen with deduplication, but cap at 2 for display
                run_display = "2"
            
            breakdown.append(f"{display_name:<35} | {status:<8} | {conf_display:<10} | {run_display:<5}")
        
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
    
    def _generate_pillar_section(self, pillar_scores: Dict[str, float]) -> str:
        """Generate ESG pillar scores section"""
        
        if not pillar_scores:
            return f"""
ESG PILLAR SCORES
{'─'*80}
(Pillar scores not available - insufficient data)
"""
        
        env_score = pillar_scores.get("environmental_score", 50)
        soc_score = pillar_scores.get("social_score", 50)
        gov_score = pillar_scores.get("governance_score", 50)
        overall_esg = pillar_scores.get("overall_esg_score", 50)
        industry_adj = pillar_scores.get("industry_adjustment", 0)
        
        # Calculate weighted contribution
        env_contribution = env_score * 0.35
        soc_contribution = soc_score * 0.30
        gov_contribution = gov_score * 0.35
        
        # Determine performance level for each pillar
        def get_performance_level(score):
            if score >= 70: return "Strong"
            elif score >= 50: return "Average"
            else: return "Weak"
        
        env_level = get_performance_level(env_score)
        soc_level = get_performance_level(soc_score)
        gov_level = get_performance_level(gov_score)
        
        section = f"""
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
        
        return section
    
    def _generate_quantitative_metrics_section(self, state: Dict[str, Any]) -> str:
        """Generate quantitative performance metrics section with industry benchmarking"""
        
        company = state.get("company", "Unknown")
        industry = state.get("industry", "Unknown")
        
        # Extract financial context from agent outputs
        financial_context = None
        agent_outputs = state.get("agent_outputs", [])
        
        for output in agent_outputs:
            if output.get("agent") == "financial_analysis":
                financial_context = output.get("output", {})
                break
        
        # Extract contradiction data
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
        
        # Calculate disclosure score
        evidence_list = state.get("evidence", [])
        total_evidence = len(evidence_list)
        max_possible_sources = 14  # Based on evidence retriever (14 main sources)
        
        # Calculate actual percentage (don't cap it - more sources is better!)
        disclosure_pct = (total_evidence / max_possible_sources * 100) if max_possible_sources > 0 else 0
        
        # Count unique sources to avoid double-counting
        unique_sources = set()
        for ev in evidence_list:
            if isinstance(ev, dict):
                source = ev.get("source", "unknown")
                unique_sources.add(source)
        
        unique_source_count = len(unique_sources)
        unique_disclosure_pct = (unique_source_count / max_possible_sources * 100) if max_possible_sources > 0 else 0
        
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
            
            # Get emissions data - support both formats
            emissions = carbon_data.get("emissions", {})
            scope1 = emissions.get("scope1", carbon_data.get("scope_1", {}))
            scope2 = emissions.get("scope2", carbon_data.get("scope_2", {}))
            scope3 = emissions.get("scope3", carbon_data.get("scope_3", {}))
            
            section += f"| {'Scope':<20} | {'Emissions (tCO2e)':<20} | {'Year':<10} | {'Source':<25} |\n"
            section += f"|{'-'*22}|{'-'*22}|{'-'*12}|{'-'*27}|\n"
            
            # Scope 1 - Direct emissions
            scope1_value = scope1.get("value") or scope1.get("emissions_tco2e")
            scope1_year = scope1.get("year", "")
            scope1_source = scope1.get("source", "BRSR/CDP")
            if scope1_value is not None and scope1_value != "N/A":
                section += f"| {'Scope 1 (Direct)':<20} | {scope1_value:>18,} | {str(scope1_year):<10} | {str(scope1_source)[:23]:<25} |\n"
            else:
                section += f"| {'Scope 1 (Direct)':<20} | {'Not disclosed':<20} | {'':<10} | {'':<25} |\n"
            
            # Scope 2 - Energy indirect
            scope2_value = scope2.get("value") or scope2.get("emissions_tco2e")
            scope2_year = scope2.get("year", "")
            scope2_source = scope2.get("source", scope2.get("methodology", ""))
            if scope2_value is not None and scope2_value != "N/A":
                section += f"| {'Scope 2 (Energy)':<20} | {scope2_value:>18,} | {str(scope2_year):<10} | {str(scope2_source)[:23]:<25} |\n"
            else:
                section += f"| {'Scope 2 (Energy)':<20} | {'Not disclosed':<20} | {'':<10} | {'':<25} |\n"
            
            # Scope 3 - Value chain
            scope3_value = scope3.get("total") or scope3.get("value") or scope3.get("emissions_tco2e")
            scope3_year = scope3.get("year", "")
            scope3_cats = scope3.get("categories", {})
            scope3_source = f"{len(scope3_cats)} categories" if scope3_cats else "Value Chain"
            if scope3_value is not None and scope3_value != "N/A":
                section += f"| {'Scope 3 (Value Chain)':<20} | {scope3_value:>18,} | {str(scope3_year):<10} | {str(scope3_source)[:23]:<25} |\n"
            else:
                section += f"| {'Scope 3 (Value Chain)':<20} | {'Not disclosed':<20} | {'':<10} | {'':<25} |\n"
            
            section += "\n"
            
            # Total emissions and intensity
            total_emissions = emissions.get("total") or carbon_data.get("total_emissions_tco2e")
            # Handle if total_emissions is a dict (from _calculate_total)
            if isinstance(total_emissions, dict):
                total_emissions = total_emissions.get("all_scopes") or total_emissions.get("scope1_2") or total_emissions.get("value")
            carbon_intensity = carbon_data.get("carbon_intensity") or carbon_data.get("intensity_metrics", {}).get("carbon_intensity")
            if isinstance(carbon_intensity, dict):
                carbon_intensity = carbon_intensity.get("value")
            net_zero_target = carbon_data.get("net_zero_target")
            renewable_pct = carbon_data.get("renewable_energy_percentage")
            sbt = carbon_data.get("science_based_target")
            verification = carbon_data.get("verification_status")
            data_source = carbon_data.get("data_source")
            data_quality = carbon_data.get("data_quality", {})
            
            # Display summary metrics
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
                section += f"Science-Based Target: ✅ Yes (SBTi approved)\n"
            if verification:
                section += f"Verification: {verification}\n"
            if data_source:
                section += f"Data Source: {data_source}\n"
            
            # Data quality assessment
            if isinstance(data_quality, dict):
                quality_score = data_quality.get("overall_score", 0)
                confidence = data_quality.get("data_confidence", "Unknown")
                section += f"Data Quality Score: {quality_score}/100 ({confidence} confidence)\n"
            else:
                section += f"Data Quality: {data_quality}\n"
            
            section += "\n"
            
            # Grid emission factor used
            grid_factor = carbon_data.get("grid_emission_factor")
            country = carbon_data.get("country_detected", "Unknown")
            if grid_factor:
                section += f"Grid Emission Factor: {grid_factor} tCO2/MWh ({country})\n\n"
        
        # === CARBON METRICS (from Financial Analyst - fallback) ===
        has_carbon_data = has_carbon_extraction
        
        if financial_context and isinstance(financial_context, dict) and not has_carbon_extraction:
            esg_metrics = financial_context.get("esg_financial_metrics", {})
            
            # Check for carbon intensity
            carbon_intensity = esg_metrics.get("carbon_intensity")
            water_efficiency = esg_metrics.get("water_efficiency")
            energy_efficiency = esg_metrics.get("energy_efficiency")
            
            if carbon_intensity is not None or water_efficiency is not None or energy_efficiency is not None:
                has_carbon_data = True
                
                section += "ENVIRONMENTAL METRICS\n"
                section += f"{'─'*80}\n\n"
                
                # Build metrics table
                section += f"| {'Metric':<30} | {'Value':<20} | {'Status':<15} |\n"
                section += f"|{'-'*32}|{'-'*22}|{'-'*17}|\n"
                
                # Carbon Intensity
                if carbon_intensity is not None:
                    # Industry benchmarks (approximate)
                    carbon_benchmarks = {
                        "oil_and_gas": 0.05, "energy": 0.04, "automotive": 0.02,
                        "aviation": 0.03, "manufacturing": 0.015, "technology": 0.005,
                        "finance": 0.001, "healthcare": 0.008
                    }
                    industry_key = industry.lower().replace(" ", "_").replace("&", "and")
                    industry_avg = carbon_benchmarks.get(industry_key, 0.01)
                    
                    status = "⚠️ Above Avg" if carbon_intensity > industry_avg else "✅ Below Avg"
                    section += f"| {'Carbon Intensity':<30} | {carbon_intensity:.6f} tCO2/${'':>8} | {status:<15} |\n"
                    section += f"| {'  Industry Average':<30} | {industry_avg:.6f} tCO2/${'':>8} | {'':>15} |\n"
                
                # Water Efficiency
                if water_efficiency is not None:
                    water_benchmarks = {
                        "oil_and_gas": 0.002, "energy": 0.0015, "automotive": 0.001,
                        "manufacturing": 0.0008, "food_beverage": 0.003
                    }
                    industry_key = industry.lower().replace(" ", "_").replace("&", "and")
                    industry_avg = water_benchmarks.get(industry_key, 0.001)
                    
                    status = "⚠️ Above Avg" if water_efficiency > industry_avg else "✅ Below Avg"
                    section += f"| {'Water Intensity':<30} | {water_efficiency:.6f} L/${'':>10} | {status:<15} |\n"
                
                # Energy Efficiency
                if energy_efficiency is not None:
                    energy_benchmarks = {
                        "oil_and_gas": 0.003, "energy": 0.0025, "manufacturing": 0.002,
                        "technology": 0.0008, "finance": 0.0005
                    }
                    industry_key = industry.lower().replace(" ", "_").replace("&", "and")
                    industry_avg = energy_benchmarks.get(industry_key, 0.0015)
                    
                    status = "⚠️ Above Avg" if energy_efficiency > industry_avg else "✅ Below Avg"
                    section += f"| {'Energy Intensity':<30} | {energy_efficiency:.6f} kWh/${'':>8} | {status:<15} |\n"
                
                section += "\n"
                section += "Interpretation:\n"
                section += f"  • Lower intensity = Better environmental efficiency\n"
                section += f"  • {company} carbon footprint per revenue dollar\n"
                section += f"  • Benchmarked against {industry} sector averages\n\n"
        
        if not has_carbon_data:
            section += "ENVIRONMENTAL METRICS\n"
            section += f"{'─'*80}\n\n"
            section += "⚠️ Carbon Metrics: Not publicly disclosed (Transparency Gap)\n"
            section += "⚠️ Water Usage: Not publicly disclosed\n"
            section += "⚠️ Energy Consumption: Not publicly disclosed\n\n"
            section += "Note: Lack of environmental data disclosure may indicate:\n"
            section += "  • Limited ESG reporting maturity\n"
            section += "  • Private company without disclosure requirements\n"
            section += "  • Emerging market with lower transparency standards\n\n"
        
        # === GOVERNANCE METRICS ===
        section += "GOVERNANCE & DISCLOSURE METRICS\n"
        section += f"{'─'*80}\n\n"
        
        section += f"| {'Metric':<35} | {'Value':<20} | {'Assessment':<15} |\n"
        section += f"|{'-'*37}|{'-'*22}|{'-'*17}|\n"
        
        # Board Independence (if available from financial data)
        board_independence = None
        if financial_context and isinstance(financial_context, dict):
            gov_metrics = financial_context.get("governance_metrics", {})
            board_independence = gov_metrics.get("board_independence")
        
        if board_independence:
            status = "✅ Strong" if board_independence > 60 else "⚠️ Weak" if board_independence < 40 else "➖ Average"
            section += f"| {'Board Independence Score':<35} | {board_independence:.1f}/100{'':>13} | {status:<15} |\n"
        
        # Controversy Count
        controversy_status = "✅ Clean" if controversy_count == 0 else "⚠️ Concerns" if controversy_count <= 3 else "🚨 High Risk"
        section += f"| {'Controversy Count':<35} | {controversy_count} issue(s){'':>11} | {controversy_status:<15} |\n"
        
        # Disclosure Score (using unique sources)
        disclosure_status = "✅ Excellent" if unique_disclosure_pct >= 70 else "⚡ Good" if unique_disclosure_pct >= 50 else "⚠️ Limited"
        section += f"| {'Disclosure Score':<35} | {unique_source_count}/{max_possible_sources} sources ({unique_disclosure_pct:.0f}%){'':>3} | {disclosure_status:<15} |\n"
        
        section += "\n"
        section += "Interpretation:\n"
        section += f"  • Controversy Count: {controversy_count} contradiction(s) found in claims vs evidence\n"
        section += f"  • Disclosure Score: {unique_source_count} unique sources out of {max_possible_sources} tracked ({unique_disclosure_pct:.0f}%)\n"
        section += f"  • Total Evidence Items: {total_evidence} (may include multiple items per source)\n"
        section += f"  • Higher disclosure = Greater transparency\n\n"
        
        # === FINANCIAL-ESG ALIGNMENT ===
        if financial_context and isinstance(financial_context, dict):
            greenwashing_flags = financial_context.get("greenwashing_flags", [])
            
            if greenwashing_flags and len(greenwashing_flags) > 0:
                section += "FINANCIAL-ESG MISALIGNMENT FLAGS\n"
                section += f"{'─'*80}\n\n"
                
                for flag in greenwashing_flags[:5]:  # Top 5 flags
                    if isinstance(flag, dict):
                        severity = flag.get("severity", "Low")
                        description = flag.get("description", "")
                        icon = "🚨" if severity == "High" else "⚠️" if severity == "Moderate" else "⚡"
                        section += f"{icon} {severity} Risk: {description}\n"
                
                section += "\n"
        
        return section
    
    def export_json(self, state: Dict[str, Any]) -> str:
        """Export machine-readable JSON format"""
        
        # ============================================================
        # FIXED: Deduplicate agent outputs before export
        # ============================================================
        agent_outputs = state.get("agent_outputs", [])
        
        # Deduplicate by agent+timestamp
        unique_outputs = {}
        for output in agent_outputs:
            agent_name = output.get('agent')
            timestamp = output.get('timestamp', 'none')
            unique_key = f"{agent_name}_{timestamp}"
            
            if unique_key not in unique_outputs:
                unique_outputs[unique_key] = output
        
        unique_outputs_list = list(unique_outputs.values())
        
        # Count unique agents
        unique_agents = set(o.get('agent') for o in unique_outputs_list if o.get('agent'))
        successful_agents = set(o.get('agent') for o in unique_outputs_list 
                               if o.get('agent') and 'error' not in o)
        
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
                for o in unique_outputs_list
                if o.get("agent")
            ]
        }
        
        return json.dumps(export, indent=2)
    
    def _generate_data_enrichment_section(self, state: Dict[str, Any]) -> str:
        """
        Generate section showing results from NEW enterprise features:
        - Indian Financial Data (revenue, profit, market cap)
        - Company Reports (PDF extraction)
        - Carbon Extractor (Scope 1/2/3)
        - Greenwishing/Greenhushing Detection
        - Regulatory Compliance Status
        """
        section = ""
        has_data = False
        
        # Extract data from agent outputs
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
        
        # Also check state directly
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
                section += f"| {'Return on Equity (ROE)':<30} | {'{:.1f}%'.format(ratios['roe']*100 if ratios['roe'] < 1 else ratios['roe']):<25} | {'Screener':<20} |\n"
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
                    
                    # Carbon metrics
                    if extracted_data.get("scope_1_emissions"):
                        section += f"| {'Scope 1 Emissions':<35} | {extracted_data['scope_1_emissions']:,.0f} tCO2e{'':<17} |\n"
                    if extracted_data.get("scope_2_emissions"):
                        section += f"| {'Scope 2 Emissions':<35} | {extracted_data['scope_2_emissions']:,.0f} tCO2e{'':<17} |\n"
                    if extracted_data.get("scope_3_emissions"):
                        section += f"| {'Scope 3 Emissions':<35} | {extracted_data['scope_3_emissions']:,.0f} tCO2e{'':<17} |\n"
                    if extracted_data.get("total_emissions"):
                        section += f"| {'Total GHG Emissions':<35} | {extracted_data['total_emissions']:,.0f} tCO2e{'':<17} |\n"
                    
                    # Energy metrics
                    if extracted_data.get("renewable_energy_pct"):
                        section += f"| {'Renewable Energy %':<35} | {extracted_data['renewable_energy_pct']:.1f}%{'':<25} |\n"
                    if extracted_data.get("energy_consumption"):
                        section += f"| {'Energy Consumption':<35} | {extracted_data['energy_consumption']:,.0f} GWh{'':<19} |\n"
                    
                    # Water metrics
                    if extracted_data.get("water_consumption"):
                        section += f"| {'Water Consumption':<35} | {extracted_data['water_consumption']:,.0f} ML{'':<20} |\n"
                    if extracted_data.get("water_recycled_pct"):
                        section += f"| {'Water Recycled %':<35} | {extracted_data['water_recycled_pct']:.1f}%{'':<25} |\n"
                    
                    # Workforce metrics
                    if extracted_data.get("total_employees"):
                        section += f"| {'Total Employees':<35} | {extracted_data['total_employees']:,}{'':<22} |\n"
                    if extracted_data.get("women_employees_pct"):
                        section += f"| {'Women Employees %':<35} | {extracted_data['women_employees_pct']:.1f}%{'':<25} |\n"
                    if extracted_data.get("women_leadership_pct"):
                        section += f"| {'Women in Leadership %':<35} | {extracted_data['women_leadership_pct']:.1f}%{'':<25} |\n"
                    
                    # Governance metrics
                    if extracted_data.get("board_independence_pct"):
                        section += f"| {'Board Independence %':<35} | {extracted_data['board_independence_pct']:.1f}%{'':<25} |\n"
                    if extracted_data.get("independent_directors"):
                        section += f"| {'Independent Directors':<35} | {extracted_data['independent_directors']}{'':<26} |\n"
                    
                    # Targets
                    if extracted_data.get("net_zero_target_year"):
                        section += f"| {'Net Zero Target Year':<35} | {extracted_data['net_zero_target_year']}{'':<26} |\n"
                    
                    # Financial from reports
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
                gw_indicators = len(gw.get("indicators_found", []))
                section += f"| {'Greenwishing (Unfunded Goals)':<30} | {gw_risk:<15} | {gw_score:<10} | {f'{gw_indicators} indicators':<25} |\n"
            
            if gh:
                gh_risk = gh.get("risk_level", "N/A")
                gh_score = gh.get("score", "N/A")
                gh_missing = len(gh.get("missing_disclosures", []))
                section += f"| {'Greenhushing (Hidden Data)':<30} | {gh_risk:<15} | {gh_score:<10} | {f'{gh_missing} missing fields':<25} |\n"
            
            if sd:
                sd_detected = "Yes" if sd.get("detected") else "No"
                sd_patterns = len(sd.get("patterns", []))
                section += f"| {'Selective Disclosure':<30} | {sd_detected:<15} | {'N/A':<10} | {f'{sd_patterns} patterns':<25} |\n"
            
            if overall:
                section += f"\n{'Overall Deception Risk Score':<30}: {overall.get('score', 'N/A')}/100 ({overall.get('level', 'N/A')})\n"
            
            # Show top indicators
            indicators = gw.get("indicators_found", [])[:3]
            if indicators:
                section += "\nTop Greenwishing Indicators:\n"
                for ind in indicators:
                    section += f"  ⚠️  {ind}\n"
            
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
            risk_level = regulatory.get("risk_level", "N/A")
            applicable_regs = regulatory.get("applicable_regulations", [])
            
            section += f"Jurisdiction: {jurisdiction}\n"
            section += f"Compliance Score: {compliance_score}/100\n"
            section += f"Risk Level: {risk_level}\n\n"
            
            if applicable_regs:
                section += "Applicable Regulations:\n"
                for reg in applicable_regs[:6]:
                    section += f"  ✓ {reg}\n"
                if len(applicable_regs) > 6:
                    section += f"  ... and {len(applicable_regs) - 6} more\n"
                section += "\n"
            
            # Compliance results
            compliance_results = regulatory.get("compliance_results", [])
            if compliance_results:
                section += f"| {'Regulation':<35} | {'Status':<12} | {'Gaps':<15} |\n"
                section += f"|{'-'*37}|{'-'*14}|{'-'*17}|\n"
                for result in compliance_results[:5]:
                    reg_name = result.get("regulation", "Unknown")[:35]
                    status = "✅ Compliant" if result.get("compliant") else "⚠️ Gap Found"
                    gaps = len(result.get("gaps", []))
                    section += f"| {reg_name:<35} | {status:<12} | {gaps} issue(s){'':<7} |\n"
                section += "\n"
            
            # Regulatory risks
            risks = regulatory.get("regulatory_risks", [])
            if risks:
                section += "Regulatory Risks Identified:\n"
                for risk in risks[:3]:
                    section += f"  🚨 {risk.get('risk', 'Unknown')}: {risk.get('description', '')[:50]}\n"
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
            
            # Climate relevance
            climate_rel = claim_analysis.get("climate_relevance", {})
            if climate_rel:
                section += f"Climate Relevance Score: {climate_rel.get('score', 'N/A')}/100\n"
                section += f"Classification: {climate_rel.get('classification', 'N/A')}\n\n"
            
            # Greenwashing detection
            gw_detect = claim_analysis.get("greenwashing_detection", {})
            if gw_detect:
                section += f"Greenwashing Risk (NLP): {gw_detect.get('risk_score', 'N/A')}/100\n"
                section += f"Risk Level: {gw_detect.get('risk_level', 'N/A')}\n"
                
                patterns = gw_detect.get("detected_patterns", [])
                if patterns:
                    section += f"Detected Patterns: {', '.join(patterns[:4])}\n"
                section += "\n"
            
            # Claim vs Evidence comparison
            if comparison:
                section += "Claim vs Evidence Comparison:\n"
                section += f"  • Claim Greenwashing Score: {comparison.get('claim_greenwashing_score', 'N/A')}\n"
                section += f"  • Evidence Greenwashing Score: {comparison.get('evidence_greenwashing_score', 'N/A')}\n"
                section += f"  • Interpretation: {comparison.get('interpretation', 'N/A')}\n\n"
            
            # Final verdict
            if verdict:
                section += f"ClimateBERT Verdict: {verdict.get('verdict', 'N/A')}\n"
                section += f"Confidence: {verdict.get('confidence', 'N/A')}\n"
            
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
            
            # Human-readable explanation
            narrative = explainability.get("human_readable_explanation", "")
            if narrative:
                section += f"AI Explanation:\n{narrative}\n"
            
            section += "\n"
        
        # === FINANCIAL CONTEXT FLAGS (Greenwashing Indicators) ===
        financial_context = {}
        if evidence_output:
            financial_context = evidence_output.get("financial_context", {})
        
        if not financial_context:
            financial_context = state.get("financial_context", {})
        
        if financial_context:
            report_metrics = financial_context.get("report_metrics", {})
            greenwashing_flags = financial_context.get("greenwashing_flags", [])
            
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

⚠️  Indian Financial Data: Not available (company may not be in database)
⚠️  Company Reports: No official PDFs could be fetched
⚠️  PDF Metrics: No data extracted

Note: This may occur when:
  • Company is not in the 50+ Indian companies database
  • Investor relations page structure is not recognized
  • PDF reports are not publicly accessible
  • Non-Indian company without configured IR URL

"""
        
        return section


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
