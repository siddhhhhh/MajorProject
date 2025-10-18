"""
AutoGen 0.10+ Compatible Hybrid Orchestrator
Uses new autogen-agentchat and autogen-core API
"""

import os
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from config.settings import settings

# Import custom agents
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

# Try new AutoGen 0.10+ imports
AUTOGEN_AVAILABLE = False
try:
    # AutoGen 0.10+ uses different imports
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.base import Response
    from autogen_agentchat.messages import TextMessage
    from autogen_core.models import ChatCompletionClient, UserMessage
    
    AUTOGEN_AVAILABLE = True
    print("✅ AutoGen 0.10+ detected")
except ImportError:
    try:
        # Try old AutoGen API as fallback
        import autogen
        AUTOGEN_AVAILABLE = True
        print("✅ AutoGen legacy version detected")
    except ImportError:
        AUTOGEN_AVAILABLE = False
        print("❌ AutoGen not available")


class HybridAutoGenOrchestrator:
    """
    AutoGen 0.10+ Compatible Orchestrator
    Simplified workflow coordination without complex agent conversations
    """
    
    def __init__(self):
        if not AUTOGEN_AVAILABLE:
            raise ImportError("AutoGen required but not properly installed")
        
        print("\n🤖 Initializing Hybrid Orchestrator (11 Agents)...")
        
        # Initialize all 11 custom agents (these work regardless of AutoGen)
        print("   📦 Loading 11 custom agents...")
        self.agents = {
            "agent_1": ClaimExtractor(),
            "agent_2": EvidenceRetriever(),
            "agent_3": ContradictionAnalyzer(),
            "agent_4": CredibilityAnalyst(),
            "agent_5": SentimentAnalyzer(),
            "agent_6": HistoricalAnalyst(),
            "agent_7": RiskScorer(),
            "agent_8": RealTimeMonitor(),
            "agent_9": IndustryComparator(),
            "agent_10": ConfidenceScorer(),
            "agent_11": ConflictResolver()
        }
        print("   ✅ All 11 agents loaded")
        
        # Simple workflow tracker (no complex AutoGen coordination needed)
        self.workflow_state = {
            "current_step": 0,
            "total_steps": 11,
            "notifications": []
        }
        
        print("   ✅ Orchestrator ready (Simplified Mode)")
        print("   🔗 Workflow: 11-Agent Sequential Pipeline\n")
    
    def analyze_with_autogen(self, company: str, content: str = None, 
                            enable_realtime: bool = True) -> Dict[str, Any]:
        """
        Execute 11-agent workflow with progress tracking
        AutoGen 0.10+ simplified - no complex agent conversations
        """
        
        print(f"\n{'='*80}")
        print(f"🤖 11-Agent ESG Analysis (AutoGen-Tracked)")
        print(f"{'='*80}")
        print(f"🏢 Company: {company}")
        print(f"📡 Real-time monitoring: {'Enabled' if enable_realtime else 'Disabled'}")
        print(f"⏰ Start: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*80}\n")
        
        results = {
            "company": company,
            "orchestration_method": "AutoGen 0.10+ Hybrid",
            "timestamp": datetime.now().isoformat(),
            "workflow_status": "in_progress"
        }
        
        try:
            # STEP 8: Real-time monitoring
            if enable_realtime:
                self._update_progress(8, 11, "Real-Time Data Collection")
                print(f"{'='*80}")
                print("🔄 AGENT 8: Real-Time News Monitoring")
                print(f"{'='*80}")
                
                realtime_data = self.agents["agent_8"].scrape_and_store(company, hours_lookback=48)
                results["realtime_monitoring"] = realtime_data
                self._notify(f"Agent 8: Scraped {realtime_data['articles_found']} articles")
            
            # Fetch content if not provided
            if not content:
                print(f"\n📄 Fetching recent ESG content...")
                content = self._fetch_esg_content(company)
                if not content:
                    results["workflow_status"] = "no_content"
                    return results
            
            # STEP 1: Claims
            self._update_progress(1, 11, "Claim Extraction")
            claims_result = self.agents["agent_1"].extract_claims(company, content)
            results["claims"] = claims_result.get("claims", [])
            
            if not results["claims"]:
                results["workflow_status"] = "no_claims"
                return results
            
            self._notify(f"Agent 1: {len(results['claims'])} claims extracted")
            
            # Initialize storage
            results["evidence"] = []
            results["contradiction_analysis"] = []
            results["sentiment_analysis"] = []
            results["conflict_resolutions"] = []
            
            # STEPS 2-5, 11: Per-claim analysis
            for i, claim in enumerate(results["claims"], 1):
                print(f"\n{'='*80}")
                print(f"🔍 Claim {i}/{len(results['claims'])}: {claim.get('claim_text')[:80]}...")
                print(f"{'='*80}")
                
                # Agent 2: Evidence
                self._update_progress(2, 11, f"Evidence (Claim {i})")
                evidence = self.agents["agent_2"].retrieve_evidence(claim, company)
                results["evidence"].append(evidence)
                self._notify(f"Claim {i}: {len(evidence.get('evidence', []))} sources")
                
                evidence_list = evidence.get("evidence", [])
                
                # Agent 3: Contradictions
                self._update_progress(3, 11, f"Contradictions (Claim {i})")
                contradiction = self.agents["agent_3"].analyze_claim(claim, evidence_list)
                results["contradiction_analysis"].append(contradiction)
                self._notify(f"Claim {i}: {contradiction.get('overall_verdict')}")
                
                # Agent 5: Sentiment
                self._update_progress(5, 11, f"Sentiment (Claim {i})")
                sentiment = self.agents["agent_5"].analyze_claim_language(claim, evidence_list)
                results["sentiment_analysis"].append(sentiment)
                
                # Agent 11: Conflicts
                self._update_progress(11, 11, f"Conflict Resolution (Claim {i})")
                conflict = self.agents["agent_11"].resolve_conflicts(claim, evidence_list)
                results["conflict_resolutions"].append(conflict)
                
                if conflict.get("requires_human_review"):
                    self._notify(f"⚠️ Claim {i}: Human review recommended")
            
            # Agent 4: Credibility
            self._update_progress(4, 11, "Credibility Analysis")
            all_evidence = []
            for ev in results["evidence"]:
                all_evidence.extend(ev.get("evidence", []))
            
            if all_evidence:
                results["credibility_analysis"] = self.agents["agent_4"].analyze_sources(all_evidence)
            
            # Agent 6: Historical
            self._update_progress(6, 11, "Historical Analysis")
            results["historical_analysis"] = self.agents["agent_6"].analyze_company_history(company)
            
            # Agent 9: Industry Comparison
            self._update_progress(9, 11, "Industry Comparison")
            try:
                results["industry_comparison"] = self.agents["agent_9"].compare_to_peers(
                    company, results["claims"]
                )
            except Exception as e:
                print(f"⚠️ Industry comparison skipped: {e}")
                results["industry_comparison"] = {"error": str(e)}
            
            # Agent 7: Risk Scoring
            self._update_progress(7, 11, "Risk Scoring")
            results["final_risk_assessment"] = self.agents["agent_7"].calculate_final_score(
                company, results
            )
            
            # Agent 10: Confidence
            self._update_progress(10, 11, "Confidence Scoring")
            results["confidence_assessment"] = self.agents["agent_10"].calculate_confidence(results)
            
            # Generate summary
            results["executive_summary"] = self._generate_simple_summary(results)
            
            results["workflow_status"] = "completed"
            
            print(f"\n{'='*80}")
            print(f"✅ 11-Agent Analysis Complete")
            print(f"⏰ End: {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'='*80}\n")
            
        except Exception as e:
            print(f"\n❌ Workflow error: {e}")
            results["workflow_status"] = "failed"
            results["error"] = str(e)
            import traceback
            results["traceback"] = traceback.format_exc()
        
        return results
    
    def _fetch_esg_content(self, company: str) -> Optional[str]:
        """Fetch recent ESG content"""
        try:
            from utils.enterprise_data_sources import enterprise_fetcher
            
            source_dict = enterprise_fetcher.fetch_all_sources(
                company=company,
                query="ESG sustainability report",
                max_per_source=3
            )
            
            results = enterprise_fetcher.aggregate_and_deduplicate(source_dict)
            
            if not results:
                return None
            
            content_parts = []
            for result in results[:5]:
                content_parts.append(result.get("title", ""))
                content_parts.append(result.get("snippet", ""))
            
            return " ".join(content_parts)
        except Exception as e:
            print(f"⚠️ Content fetch error: {e}")
            return None
    
    def _update_progress(self, step: int, total: int, description: str):
        """Update workflow progress"""
        self.workflow_state["current_step"] = step
        progress = (step / total) * 100
        print(f"\n📊 Progress: {progress:.0f}% (Step {step}/{total}: {description})")
    
    def _notify(self, message: str):
        """Log notification"""
        print(f"   💬 {message}")
        self.workflow_state["notifications"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
    
    def _generate_simple_summary(self, results: Dict) -> str:
        """Generate simple text summary"""
        assessment = results.get("final_risk_assessment", {})
        confidence = results.get("confidence_assessment", {})
        
        summary = f"""ESG Analysis Summary for {results.get('company')}

Overall ESG Score: {assessment.get('esg_score', 0)}/100 (Grade: {assessment.get('rating_grade', 'N/A')})
Greenwashing Risk: {assessment.get('risk_level', 'N/A')} ({assessment.get('greenwashing_risk_score', 0)}/100)
Analysis Confidence: {confidence.get('confidence_level', 'N/A')} ({confidence.get('overall_confidence', 0)}%)

Claims Analyzed: {len(results.get('claims', []))}
Evidence Sources: {sum(len(e.get('evidence', [])) for e in results.get('evidence', []))}

This analysis provides a comprehensive assessment of the company's ESG claims based on 
multi-source verification, historical track record, and industry benchmarking.
"""
        
        return summary


# Global instance
try:
    hybrid_orchestrator = HybridAutoGenOrchestrator()
    print("✅ Hybrid Orchestrator initialized\n")
except Exception as e:
    print(f"❌ Orchestrator initialization failed: {e}\n")
    import traceback
    traceback.print_exc()
    hybrid_orchestrator = None
