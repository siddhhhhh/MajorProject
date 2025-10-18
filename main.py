"""
ESG Greenwashing Detection System - Production Version
11-Agent Multi-Agent System with AutoGen Orchestration
100% Real-time Data, Zero Hardcoding
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Import all 11 agents
from agents.claim_extractor import ClaimExtractor
from agents.evidence_retriever import EvidenceRetriever
from agents.contradiction_analyzer import ContradictionAnalyzer
from agents.credibility_analyst import CredibilityAnalyst
from agents.sentiment_analyzer import SentimentAnalyzer
from agents.historical_analyst import HistoricalAnalyst
from agents.risk_scorer import RiskScorer
from agents.realtime_monitor import RealTimeMonitor
from agents.industry_comparator import IndustryComparator
from agents.confidence_scorer import ConfidenceScorer
from agents.conflict_resolver import ConflictResolver

# AutoGen orchestration
USE_AUTOGEN = os.getenv("USE_AUTOGEN", "true").lower() == "true"

if USE_AUTOGEN:
    print("🤖 Using AutoGen Multi-Agent Orchestration")
    try:
        from core.hybrid_orchestrator import hybrid_orchestrator
    except ImportError:
        print("⚠️ AutoGen not available, falling back to direct orchestration")
        USE_AUTOGEN = False


class ESGGreenwashingDetector:
    """
    Enterprise-Grade ESG Greenwashing Detection System
    11-Agent Multi-Agent System with Real-Time Monitoring
    Matches MSCI/Sustainalytics/RepRisk Standards
    """
    
    def __init__(self):
        print("\n" + "="*80)
        print("🌱 ESG GREENWASHING DETECTION SYSTEM v2.0")
        print("Enterprise-Grade Multi-Agent Analysis (11 Agents)")
        print("Real-Time Monitoring | Zero Hardcoding | AutoGen Powered")
        print("="*80)
        
        self.use_autogen = False
        self.orchestrator = None
        
        if USE_AUTOGEN:
            print("\n🤖 Attempting AutoGen Multi-Agent Orchestration")
            try:
                from core.hybrid_orchestrator import hybrid_orchestrator
                
                if hybrid_orchestrator is not None:
                    self.orchestrator = hybrid_orchestrator
                    self.use_autogen = True
                    print("✅ AutoGen orchestrator loaded (11 agents)\n")
                else:
                    print("⚠️ AutoGen unavailable - using direct orchestration\n")
                    self.use_autogen = False
            except Exception as e:
                print(f"⚠️ AutoGen error: {e}")
                print("   Falling back to direct orchestration\n")
                self.use_autogen = False
        
        # Initialize agents (for direct orchestration)
        if not self.use_autogen:
            print("\n🔧 Using Direct Orchestration (11 Agents)")
            print("\n🤖 Initializing AI agents...")
            
            self.agent_1 = ClaimExtractor()
            print("   ✅ Agent 1: Claim Extraction Specialist")
            
            self.agent_2 = EvidenceRetriever()
            print("   ✅ Agent 2: Evidence Retrieval & Cross-Verification")
            
            self.agent_3 = ContradictionAnalyzer()
            print("   ✅ Agent 3: Contradiction & Verification Analyst")
            
            self.agent_4 = CredibilityAnalyst()
            print("   ✅ Agent 4: Source Credibility & Bias Analyst")
            
            self.agent_5 = SentimentAnalyzer()
            print("   ✅ Agent 5: Sentiment & Linguistic Analysis Expert")
            
            self.agent_6 = HistoricalAnalyst()
            print("   ✅ Agent 6: Historical Pattern & Controversy Analyst")
            
            self.agent_7 = RiskScorer()
            print("   ✅ Agent 7: Final Risk Scorer & ESG Rating Specialist")
            
            self.agent_8 = RealTimeMonitor()
            print("   ✅ Agent 8: Real-Time News Monitor & Scraper")
            
            self.agent_9 = IndustryComparator()
            print("   ✅ Agent 9: Industry Peer Comparison Specialist")
            
            self.agent_10 = ConfidenceScorer()
            print("   ✅ Agent 10: Analysis Confidence Scorer")
            
            self.agent_11 = ConflictResolver()
            print("   ✅ Agent 11: Evidence Conflict Resolver")
            
            print("\n✅ All 11 agents initialized successfully\n")
    
    def analyze_company(self, company_name: str, esg_content: str = None, 
                   enable_realtime: bool = True,
                   enable_peer_comparison: bool = True,
                   clear_cache: bool = True) -> dict:
        """
        Complete ESG analysis for any company using 11-agent system
        
        Args:
            company_name: Name of the company to analyze
            esg_content: Optional - specific ESG claims to analyze. 
                        If None, system will search for recent claims.
            enable_realtime: Enable real-time news monitoring (Agent 8)
            enable_peer_comparison: Enable industry comparison (Agent 9)
        
        Returns:
            Complete analysis results with ESG score, confidence, and risk rating
        """
        # Clear vector DB cache to prevent cross-contamination
        if clear_cache:
            try:
                from core.vector_store import vector_store
                print(f"\n🧹 Clearing vector DB cache for fresh analysis...")
                vector_store.clear_collection()
                print(f"   ✅ Cache cleared")
            except Exception as e:
                print(f"   ⚠️ Cache clear failed: {e}")
            if self.use_autogen and self.orchestrator is not None:
                # Use AutoGen orchestration
                print("🤖 Running analysis with AutoGen 11-Agent orchestration")
                try:
                    return self.orchestrator.analyze_with_autogen(
                        company_name, 
                        esg_content,
                        enable_realtime=enable_realtime
                    )
                except Exception as e:
                    print(f"❌ AutoGen analysis failed: {e}")
                    print("🔄 Falling back to direct orchestration...")
                    import traceback
                    traceback.print_exc()
                # Fall through to direct analysis
        
        # Direct orchestration (11 agents)
        return self._direct_analysis_11_agents(
            company_name, 
            esg_content,
            enable_realtime,
            enable_peer_comparison
        )
    
    def _direct_analysis_11_agents(self, company_name: str, esg_content: str = None,
                                   enable_realtime: bool = True,
                                   enable_peer_comparison: bool = True) -> dict:
        """Direct orchestration with all 11 agents"""
        
        print("\n" + "="*80)
        print(f"🔍 ANALYZING: {company_name}")
        print("="*80)
        print(f"⏰ Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📡 Real-time monitoring: {'Enabled' if enable_realtime else 'Disabled'}")
        print(f"📊 Peer comparison: {'Enabled' if enable_peer_comparison else 'Disabled'}")
        print("="*80)
        
        results = {
            "company": company_name,
            "analysis_timestamp": datetime.now().isoformat(),
            "orchestration_method": "Direct 11-Agent",
            "claims": [],
            "evidence": [],
            "contradiction_analysis": [],
            "credibility_analysis": None,
            "sentiment_analysis": [],
            "historical_analysis": None,
            "final_risk_assessment": None,
            "realtime_monitoring": None,
            "industry_comparison": None,
            "confidence_assessment": None,
            "conflict_resolutions": []
        }
        
        # ===================================================================
        # AGENT 8 (FIRST): REAL-TIME NEWS MONITORING & STORAGE
        # ===================================================================
        if enable_realtime:
            print("\n" + "="*80)
            print("AGENT 8: REAL-TIME NEWS MONITORING & SCRAPING")
            print("="*80)
            
            try:
                realtime_data = self.agent_8.scrape_and_store(company_name, hours_lookback=48)
                results["realtime_monitoring"] = realtime_data
            except Exception as e:
                print(f"⚠️ Real-time monitoring failed: {e}")
                results["realtime_monitoring"] = {"error": str(e)}
        
        # ===================================================================
        # AGENT 1: CLAIM EXTRACTION
        # ===================================================================
        if not esg_content:
            print(f"\n📄 Searching for recent ESG claims from {company_name}...")
            esg_content = self._fetch_recent_esg_content(company_name)
            
            if not esg_content:
                print(f"❌ No ESG content found for {company_name}")
                print("Please provide specific claims to analyze.")
                return results
        
        print("\n" + "="*80)
        print("AGENT 1: EXTRACTING ESG CLAIMS")
        print("="*80)
        
        claims_result = self.agent_1.extract_claims(company_name, esg_content)
        
        if not claims_result.get("claims"):
            print("❌ No verifiable claims extracted")
            return results
        
        results["claims"] = claims_result["claims"]
        print(f"\n✅ Extracted {len(results['claims'])} claims")
        
        # ===================================================================
        # AGENTS 2, 3, 5, 11: PER-CLAIM ANALYSIS
        # ===================================================================
        for i, claim in enumerate(results["claims"], 1):
            print(f"\n{'='*80}")
            print(f"ANALYZING CLAIM {i}/{len(results['claims'])}")
            print(f"{'='*80}")
            print(f"📋 {claim.get('claim_text')}")
            
            # AGENT 2: Retrieve Evidence
            evidence_result = self.agent_2.retrieve_evidence(claim, company_name)
            results["evidence"].append(evidence_result)
            evidence_list = evidence_result.get("evidence", [])
            
            # AGENT 3: Analyze Contradictions
            contradiction_result = self.agent_3.analyze_claim(claim, evidence_list)
            results["contradiction_analysis"].append(contradiction_result)
            
            verdict = contradiction_result.get("overall_verdict")
            confidence = contradiction_result.get("verification_confidence")
            print(f"\n   📊 Quick Verdict: {verdict} (Confidence: {confidence}%)")
            
            # AGENT 5: Sentiment & Linguistic Analysis
            sentiment_result = self.agent_5.analyze_claim_language(claim, evidence_list)
            results["sentiment_analysis"].append(sentiment_result)
            
            # AGENT 11: Conflict Resolution
            print(f"\n{'─'*80}")
            print("AGENT 11: RESOLVING EVIDENCE CONFLICTS")
            print(f"{'─'*80}")
            
            try:
                conflict_result = self.agent_11.resolve_conflicts(claim, evidence_list)
                results["conflict_resolutions"].append(conflict_result)
                
                if conflict_result.get("requires_human_review"):
                    print(f"   ⚠️ HUMAN REVIEW RECOMMENDED for this claim")
            except Exception as e:
                print(f"   ⚠️ Conflict resolution error: {e}")
                results["conflict_resolutions"].append({"error": str(e)})
        
        # ===================================================================
        # AGENT 4: OVERALL CREDIBILITY ANALYSIS
        # ===================================================================
        print(f"\n{'='*80}")
        print("AGENT 4: ANALYZING SOURCE CREDIBILITY")
        print(f"{'='*80}")
        
        all_evidence = []
        for ev_result in results["evidence"]:
            all_evidence.extend(ev_result.get("evidence", []))
        
        if all_evidence:
            credibility_result = self.agent_4.analyze_sources(all_evidence)
            results["credibility_analysis"] = credibility_result
        
        # ===================================================================
        # AGENT 6: HISTORICAL PATTERN ANALYSIS
        # ===================================================================
        print(f"\n{'='*80}")
        print("AGENT 6: ANALYZING HISTORICAL ESG TRACK RECORD")
        print(f"{'='*80}")
        
        historical_result = self.agent_6.analyze_company_history(company_name)
        results["historical_analysis"] = historical_result
        
        # ===================================================================
        # AGENT 9: INDUSTRY PEER COMPARISON
        # ===================================================================
        if enable_peer_comparison:
            print(f"\n{'='*80}")
            print("AGENT 9: INDUSTRY PEER COMPARISON")
            print(f"{'='*80}")
            
            try:
                industry_result = self.agent_9.compare_to_peers(company_name, results["claims"])
                results["industry_comparison"] = industry_result
            except Exception as e:
                print(f"⚠️ Peer comparison failed: {e}")
                results["industry_comparison"] = {"error": str(e)}
        
        # ===================================================================
        # AGENT 7: FINAL RISK SCORING & ESG RATING
        # ===================================================================
        print(f"\n{'='*80}")
        print("AGENT 7: CALCULATING FINAL ESG SCORE & RISK RATING")
        print(f"{'='*80}")
        
        final_assessment = self.agent_7.calculate_final_score(company_name, results)
        results["final_risk_assessment"] = final_assessment
        
        # ===================================================================
        # AGENT 10: CONFIDENCE SCORING
        # ===================================================================
        print(f"\n{'='*80}")
        print("AGENT 10: CALCULATING ANALYSIS CONFIDENCE")
        print(f"{'='*80}")
        
        confidence_result = self.agent_10.calculate_confidence(results)
        results["confidence_assessment"] = confidence_result
        
        # ===================================================================
        # DISPLAY FINAL COMPREHENSIVE REPORT
        # ===================================================================
        self._display_comprehensive_report(results)
        
        # Save results
        self._save_results(results, company_name)
        
        print(f"\n⏰ Completion time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return results
    
    def _fetch_recent_esg_content(self, company_name: str) -> str:
        """Fetch recent ESG claims/reports for company"""
        from utils.enterprise_data_sources import enterprise_fetcher
        
        source_dict = enterprise_fetcher.fetch_all_sources(
            company=company_name,
            query=f"ESG sustainability report announcement",
            max_per_source=3
        )
        
        all_results = enterprise_fetcher.aggregate_and_deduplicate(source_dict)
        
        if not all_results:
            return None
        
        content_parts = []
        for result in all_results[:5]:
            content_parts.append(result.get("title", ""))
            content_parts.append(result.get("snippet", ""))
        
        return " ".join(content_parts)
    
    def _display_comprehensive_report(self, results: dict):
        """Display enterprise-grade final report with all 11 agents"""
        
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE ESG GREENWASHING RISK REPORT")
        print("11-Agent Analysis | Real-Time Data | Industry Benchmarked")
        print("="*80)
        
        assessment = results.get("final_risk_assessment", {})
        confidence = results.get("confidence_assessment", {})
        
        # Header
        print(f"\n🏢 Company: {results['company']}")
        print(f"📅 Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔒 Analysis Confidence: {confidence.get('confidence_level', 'N/A')} ({confidence.get('overall_confidence', 0)}%)")
        
        # ESG Score (MSCI-style)
        esg_score = assessment.get("esg_score", 0)
        rating_grade = assessment.get("rating_grade", "N/A")
        risk_score = assessment.get("greenwashing_risk_score", 0)
        risk_level = assessment.get("risk_level", "N/A")
        
        print(f"\n{'─'*80}")
        print("🎯 ESG SCORE & RATING")
        print(f"{'─'*80}")
        print(f"   ESG Score: {esg_score}/100")
        print(f"   Rating Grade: {rating_grade} (MSCI-style)")
        print(f"   Greenwashing Risk: {risk_score}/100")
        print(f"   Risk Level: {risk_level}")
        
        # Risk bar visualization
        self._print_risk_bar(risk_score)
        
        # Real-time Monitoring Results
        realtime = results.get("realtime_monitoring")
        if realtime and not realtime.get("error"):
            print(f"\n{'─'*80}")
            print("📡 REAL-TIME MONITORING (48 Hours)")
            print(f"{'─'*80}")
            print(f"   Recent Articles Found: {realtime.get('articles_found', 0)}")
            print(f"   Stored in Vector DB: Yes")
            print(f"   Last Updated: {realtime.get('timestamp', 'N/A')}")
        
        # Component Breakdown
        print(f"\n{'─'*80}")
        print("📈 COMPONENT ANALYSIS (Weighted)")
        print(f"{'─'*80}")
        
        components = assessment.get("component_scores", {})
        for component, score in sorted(components.items(), key=lambda x: x[1], reverse=True):
            component_name = component.replace("_", " ").title()
            bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
            print(f"   {component_name:.<35} [{bar}] {score:.1f}/100")
        
        # Claim Summary with Conflicts
        print(f"\n{'─'*80}")
        print("📋 CLAIMS ANALYSIS SUMMARY")
        print(f"{'─'*80}")
        
        claims = results.get("claims", [])
        contradictions = results.get("contradiction_analysis", [])
        conflicts = results.get("conflict_resolutions", [])
        
        print(f"   Total Claims Analyzed: {len(claims)}")
        
        for i, contra in enumerate(contradictions):
            verdict = contra.get("overall_verdict")
            icon = "✅" if verdict == "Verified" else "❌" if verdict == "Contradicted" else "⚠️"
            
            # Check if conflict detected
            conflict_detected = ""
            if i < len(conflicts) and conflicts[i].get("conflicts_detected"):
                conflict_detected = " [⚠️ CONFLICT]"
            
            print(f"   {icon} Claim {contra.get('claim_id')}: {verdict} ({contra.get('verification_confidence')}% confidence){conflict_detected}")
        
        # Confidence Breakdown
        if confidence.get('breakdown'):
            print(f"\n{'─'*80}")
            print("🔒 CONFIDENCE BREAKDOWN")
            print(f"{'─'*80}")
            
            for factor, score in confidence['breakdown'].items():
                factor_name = factor.replace('_', ' ').title()
                print(f"   {factor_name:.<35} {score}/25")
            
            print(f"\n   {confidence.get('interpretation', 'N/A')}")
        
        # Industry Comparison
        industry = results.get("industry_comparison")
        if industry and not industry.get("error"):
            print(f"\n{'─'*80}")
            print("📊 INDUSTRY PEER COMPARISON")
            print(f"{'─'*80}")
            
            peers = industry.get("peers_analyzed", [])
            print(f"   Peers Analyzed: {', '.join(peers) if peers else 'N/A'}")
            
            position = industry.get("industry_position", {})
            print(f"   Industry Position: {position.get('category', 'N/A')} (Confidence: {position.get('confidence', 0)}%)")
        
        # Top 3 Reasons
        print(f"\n{'─'*80}")
        print("🔍 TOP 3 KEY FINDINGS")
        print(f"{'─'*80}")
        
        reasons = assessment.get("explainability_top_3_reasons", [])
        for i, reason in enumerate(reasons, 1):
            print(f"   {i}. {reason}")
        
        # Historical Context
        historical = results.get("historical_analysis", {})
        if historical:
            violations = len(historical.get("past_violations", []))
            greenwashing_acc = historical.get("greenwashing_history", {}).get("prior_accusations", 0)
            reputation = historical.get("reputation_score", 50)
            
            print(f"\n{'─'*80}")
            print("📜 HISTORICAL TRACK RECORD")
            print(f"{'─'*80}")
            print(f"   Past Violations: {violations}")
            print(f"   Prior Greenwashing Accusations: {greenwashing_acc}")
            print(f"   Reputation Score: {reputation}/100")
        
        # Source Quality
        credibility = results.get("credibility_analysis", {})
        if credibility:
            metrics = credibility.get("aggregate_metrics", {})
            print(f"\n{'─'*80}")
            print("📰 DATA SOURCE QUALITY")
            print(f"{'─'*80}")
            print(f"   Average Credibility: {metrics.get('average_credibility', 0):.2f}/1.0")
            print(f"   High Quality Sources: {metrics.get('high_credibility_count', 0)}")
            print(f"   Medium Quality Sources: {metrics.get('medium_credibility_count', 0)}")
            print(f"   Low Quality Sources: {metrics.get('low_credibility_count', 0)}")
        
        # Actionable Insights
        print(f"\n{'─'*80}")
        print("💡 ACTIONABLE INSIGHTS")
        print(f"{'─'*80}")
        
        insights = assessment.get("actionable_insights", {})
        
        print(f"\n   👔 For Investors:")
        print(f"      {insights.get('for_investors', 'N/A')}")
        
        print(f"\n   ⚖️  For Regulators:")
        print(f"      {insights.get('for_regulators', 'N/A')}")
        
        print(f"\n   🛒 For Consumers:")
        print(f"      {insights.get('for_consumers', 'N/A')}")
        
        print("\n" + "="*80)
    
    def _print_risk_bar(self, risk_score: float):
        """Print visual risk bar"""
        bar_length = 50
        filled = int((risk_score / 100) * bar_length)
        
        if risk_score >= 67:
            color_symbol = "🔴"
        elif risk_score >= 34:
            color_symbol = "🟡"
        else:
            color_symbol = "🟢"
        
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\n   {color_symbol} Risk Level: [{bar}] {risk_score:.1f}/100")
    
    def _save_results(self, results: dict, company_name: str):
        """Save results to JSON file"""
        os.makedirs("data/reports", exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/reports/{company_name.replace(' ', '_')}_{timestamp}_COMPLETE.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Complete 11-agent report saved to: {filename}")


def interactive_mode():
    """Interactive CLI mode"""
    detector = ESGGreenwashingDetector()
    
    while True:
        print("\n" + "="*80)
        print("🌱 ESG GREENWASHING DETECTOR v2.0 - Interactive Mode")
        print("="*80)
        
        company = input("\n🏢 Enter company name (or 'quit' to exit): ").strip()
        
        if company.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Thank you for using ESG Greenwashing Detector!")
            break
        
        if not company:
            print("❌ Company name cannot be empty")
            continue
        
        print("\n📄 Do you have specific ESG claims to analyze?")
        print("   1. Yes, I have claims to paste")
        print("   2. No, search for recent claims automatically")
        
        choice = input("\nChoice (1 or 2): ").strip()
        
        esg_content = None
        if choice == "1":
            print("\n📝 Paste ESG claims (press Enter twice when done):")
            lines = []
            while True:
                line = input()
                if line:
                    lines.append(line)
                else:
                    if lines:
                        break
            esg_content = " ".join(lines)
        
        # Advanced options
        print("\n⚙️  Advanced Options:")
        realtime = input("   Enable real-time monitoring? (Y/n): ").strip().lower() != 'n'
        peer_comp = input("   Enable peer comparison? (Y/n): ").strip().lower() != 'n'
        
        try:
            detector.analyze_company(company, esg_content, realtime, peer_comp)
        except Exception as e:
            print(f"\n❌ Analysis failed: {e}")
            import traceback
            traceback.print_exc()
        
        cont = input("\n\n🔄 Analyze another company? (y/n): ").strip().lower()
        if cont != 'y':
            print("\n👋 Thank you for using ESG Greenwashing Detector!")
            break


def quick_analysis(company: str, content: str = None, realtime: bool = True, peer_comp: bool = True):
    """Quick analysis function for API/programmatic use"""
    detector = ESGGreenwashingDetector()
    return detector.analyze_company(company, content, realtime, peer_comp)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Quick mode with command line args
        company_name = sys.argv[1]
        content = sys.argv[2] if len(sys.argv) > 2 else None
        
        quick_analysis(company_name, content)
    else:
        # Interactive mode
        interactive_mode()
