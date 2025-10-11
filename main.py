import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Import agents
from agents.claim_extractor import ClaimExtractor
from agents.evidence_retriever import EvidenceRetriever
from agents.contradiction_analyzer import ContradictionAnalyzer
from agents.credibility_analyst import CredibilityAnalyst
from agents.sentiment_analyzer import SentimentAnalyzer
from agents.historical_analyst import HistoricalAnalyst
from agents.risk_scorer import RiskScorer

# Choose orchestration method
USE_AUTOGEN = os.getenv("USE_AUTOGEN", "false").lower() == "true"

if USE_AUTOGEN:
    print("🤖 Using AutoGen Multi-Agent Orchestration")
    try:
        from core.hybrid_orchestrator import hybrid_orchestrator
    except ImportError:
        print("⚠️ AutoGen orchestrator not found, falling back to direct orchestration")
        USE_AUTOGEN = False

class ESGGreenwashingDetector:
    """
    Enterprise-grade ESG Greenwashing Detection System
    7-Agent Multi-Agent System matching MSCI/Sustainalytics/RepRisk standards
    """
    
    def __init__(self):
        print("\n" + "="*80)
        print("🌱 ESG GREENWASHING DETECTION SYSTEM")
        print("Enterprise-Grade Multi-Agent Analysis (7 Agents)")
        print("="*80)
        
        self.use_autogen = False
        self.orchestrator = None
        
        if USE_AUTOGEN:
            print("\n🤖 Attempting to use AutoGen Multi-Agent Orchestration")
            try:
                from core.hybrid_orchestrator import hybrid_orchestrator
                
                if hybrid_orchestrator is not None:
                    self.orchestrator = hybrid_orchestrator
                    self.use_autogen = True
                    print("✅ AutoGen orchestrator loaded successfully\n")
                else:
                    print("⚠️ AutoGen orchestrator is None - using direct orchestration\n")
                    self.use_autogen = False
            except ImportError as e:
                print(f"⚠️ AutoGen not available: {e}")
                print("   Falling back to direct orchestration\n")
                self.use_autogen = False
            except Exception as e:
                print(f"⚠️ Error loading AutoGen: {e}")
                print("   Falling back to direct orchestration\n")
                self.use_autogen = False
        
        # If not using AutoGen or it failed, initialize direct agents
        if not self.use_autogen:
            print("\n🔧 Using Direct Orchestration")
            print("\n🤖 Initializing AI agents...")
            self.agent_1_claim = ClaimExtractor()
            print("   ✅ Agent 1: Claim Extraction Specialist")
            
            self.agent_2_evidence = EvidenceRetriever()
            print("   ✅ Agent 2: Evidence Retrieval & Cross-Verification")
            
            self.agent_3_contradiction = ContradictionAnalyzer()
            print("   ✅ Agent 3: Contradiction & Verification Analyst")
            
            self.agent_4_credibility = CredibilityAnalyst()
            print("   ✅ Agent 4: Source Credibility & Bias Analyst")
            
            self.agent_5_sentiment = SentimentAnalyzer()
            print("   ✅ Agent 5: Sentiment & Linguistic Analysis Expert")
            
            self.agent_6_historical = HistoricalAnalyst()
            print("   ✅ Agent 6: Historical Pattern & Controversy Analyst")
            
            self.agent_7_risk = RiskScorer()
            print("   ✅ Agent 7: Final Risk Scorer & ESG Rating Specialist")
            
            print("\n✅ All 7 agents initialized successfully\n")
    
    def analyze_company(self, company_name: str, esg_content: str = None) -> dict:
        """
        Complete ESG analysis for any company using 7-agent system
        
        Args:
            company_name: Name of the company to analyze
            esg_content: Optional - specific ESG claims to analyze. 
                        If None, system will search for recent claims.
        
        Returns:
            Complete analysis results with ESG score and risk rating
        """
        
        if self.use_autogen and self.orchestrator is not None:
            # Use AutoGen orchestration
            print("🤖 Running analysis with AutoGen orchestration")
            try:
                return self.orchestrator.analyze_with_autogen(company_name, esg_content)
            except Exception as e:
                print(f"❌ AutoGen analysis failed: {e}")
                print("🔄 Falling back to direct orchestration...")
                import traceback
                traceback.print_exc()
                # Fall through to direct analysis
        
        # Direct orchestration (fallback or default)
        return self._direct_analysis(company_name, esg_content)
    
    def _direct_analysis(self, company_name: str, esg_content: str = None) -> dict:
        """Direct orchestration without AutoGen"""
        
        print("\n" + "="*80)
        print(f"🔍 ANALYZING: {company_name}")
        print("="*80)
        print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        results = {
            "company": company_name,
            "analysis_timestamp": datetime.now().isoformat(),
            "claims": [],
            "evidence": [],
            "contradiction_analysis": [],
            "credibility_analysis": None,
            "sentiment_analysis": [],
            "historical_analysis": None,
            "final_risk_assessment": None
        }
        
        # ===================================================================
        # STEP 0: Get ESG Content (if not provided)
        # ===================================================================
        if not esg_content:
            print(f"\n📄 Searching for recent ESG claims from {company_name}...")
            esg_content = self._fetch_recent_esg_content(company_name)
            
            if not esg_content:
                print(f"❌ No ESG content found for {company_name}")
                print("Please provide specific claims to analyze.")
                return results
        
        # ===================================================================
        # AGENT 1: CLAIM EXTRACTION
        # ===================================================================
        print("\n" + "="*80)
        print("AGENT 1: EXTRACTING ESG CLAIMS")
        print("="*80)
        
        claims_result = self.agent_1_claim.extract_claims(company_name, esg_content)
        
        if not claims_result.get("claims"):
            print("❌ No verifiable claims extracted")
            return results
        
        results["claims"] = claims_result["claims"]
        print(f"\n✅ Extracted {len(results['claims'])} claims")
        
        # ===================================================================
        # AGENTS 2-5: ANALYZE EACH CLAIM
        # ===================================================================
        for i, claim in enumerate(results["claims"], 1):
            print(f"\n{'='*80}")
            print(f"ANALYZING CLAIM {i}/{len(results['claims'])}")
            print(f"{'='*80}")
            print(f"📋 {claim.get('claim_text')}")
            
            # AGENT 2: Retrieve Evidence
            evidence_result = self.agent_2_evidence.retrieve_evidence(claim, company_name)
            results["evidence"].append(evidence_result)
            evidence_list = evidence_result.get("evidence", [])
            
            # AGENT 3: Analyze Contradictions
            contradiction_result = self.agent_3_contradiction.analyze_claim(claim, evidence_list)
            results["contradiction_analysis"].append(contradiction_result)
            
            # Quick verdict display
            verdict = contradiction_result.get("overall_verdict")
            confidence = contradiction_result.get("verification_confidence")
            print(f"\n   📊 Quick Verdict: {verdict} (Confidence: {confidence}%)")
            
            # AGENT 5: Sentiment & Linguistic Analysis (per claim)
            sentiment_result = self.agent_5_sentiment.analyze_claim_language(claim, evidence_list)
            results["sentiment_analysis"].append(sentiment_result)
        
        # ===================================================================
        # AGENT 4: OVERALL CREDIBILITY ANALYSIS
        # ===================================================================
        print(f"\n{'='*80}")
        print("AGENT 4: ANALYZING SOURCE CREDIBILITY")
        print(f"{'='*80}")
        
        # Combine all evidence
        all_evidence = []
        for ev_result in results["evidence"]:
            all_evidence.extend(ev_result.get("evidence", []))
        
        if all_evidence:
            credibility_result = self.agent_4_credibility.analyze_sources(all_evidence)
            results["credibility_analysis"] = credibility_result
        
        # ===================================================================
        # AGENT 6: HISTORICAL PATTERN ANALYSIS
        # ===================================================================
        print(f"\n{'='*80}")
        print("AGENT 6: ANALYZING HISTORICAL ESG TRACK RECORD")
        print(f"{'='*80}")
        
        historical_result = self.agent_6_historical.analyze_company_history(company_name)
        results["historical_analysis"] = historical_result
        
        # ===================================================================
        # AGENT 7: FINAL RISK SCORING & ESG RATING
        # ===================================================================
        print(f"\n{'='*80}")
        print("AGENT 7: CALCULATING FINAL ESG SCORE & RISK RATING")
        print(f"{'='*80}")
        
        final_assessment = self.agent_7_risk.calculate_final_score(company_name, results)
        results["final_risk_assessment"] = final_assessment
        
        # ===================================================================
        # DISPLAY FINAL REPORT
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
        """Display enterprise-grade final report"""
        
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE ESG GREENWASHING RISK REPORT")
        print("="*80)
        
        assessment = results.get("final_risk_assessment", {})
        
        # Header
        print(f"\n🏢 Company: {results['company']}")
        print(f"📅 Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔒 Confidence Level: {assessment.get('confidence_level', 0)}%")
        
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
        
        # Component Breakdown
        print(f"\n{'─'*80}")
        print("📈 COMPONENT ANALYSIS")
        print(f"{'─'*80}")
        
        components = assessment.get("component_scores", {})
        for component, score in sorted(components.items(), key=lambda x: x[1], reverse=True):
            component_name = component.replace("_", " ").title()
            bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
            print(f"   {component_name:.<35} [{bar}] {score:.1f}/100")
        
        # Claim Summary
        print(f"\n{'─'*80}")
        print("📋 CLAIMS ANALYSIS SUMMARY")
        print(f"{'─'*80}")
        
        claims = results.get("claims", [])
        contradictions = results.get("contradiction_analysis", [])
        
        print(f"   Total Claims Analyzed: {len(claims)}")
        
        for contra in contradictions:
            verdict = contra.get("overall_verdict")
            icon = "✅" if verdict == "Verified" else "❌" if verdict == "Contradicted" else "⚠️"
            print(f"   {icon} Claim {contra.get('claim_id')}: {verdict} ({contra.get('verification_confidence')}% confidence)")
        
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
        filename = f"data/reports/{company_name.replace(' ', '_')}_{timestamp}_FULL.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Complete report saved to: {filename}")


def interactive_mode():
    """Interactive CLI mode"""
    detector = ESGGreenwashingDetector()
    
    while True:
        print("\n" + "="*80)
        print("🌱 ESG GREENWASHING DETECTOR - Interactive Mode")
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
        
        try:
            detector.analyze_company(company, esg_content)
        except Exception as e:
            print(f"\n❌ Analysis failed: {e}")
            import traceback
            traceback.print_exc()
        
        cont = input("\n\n🔄 Analyze another company? (y/n): ").strip().lower()
        if cont != 'y':
            print("\n👋 Thank you for using ESG Greenwashing Detector!")
            break


def quick_analysis(company: str, content: str = None):
    """Quick analysis function for API/programmatic use"""
    detector = ESGGreenwashingDetector()
    return detector.analyze_company(company, content)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Quick mode with command line args
        company_name = sys.argv[1]
        content = sys.argv[2] if len(sys.argv) > 2 else None
        
        quick_analysis(company_name, content)
    else:
        # Interactive mode
        interactive_mode()
