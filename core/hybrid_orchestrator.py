"""
AutoGen Hybrid Orchestrator for ESG Greenwashing Detection
Combines AutoGen's multi-agent framework with custom enterprise agents
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

# AutoGen imports
try:
    import autogen
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False
    print("⚠️ AutoGen not installed. Run: pip install pyautogen")


class HybridAutoGenOrchestrator:
    """
    Hybrid orchestrator combining:
    - AutoGen's multi-agent conversation framework
    - Our custom agents with real data sources
    - Enterprise-grade error handling and monitoring
    """
    
    def __init__(self):
        if not AUTOGEN_AVAILABLE:
            raise ImportError("AutoGen is required. Install with: pip install pyautogen")
        
        print("\n🤖 Initializing AutoGen Hybrid Orchestrator...")
        
        # Configure LLM for AutoGen (using Groq for OpenAI compatibility)
        self.llm_config = {
            "config_list": [{
                "model": settings.GROQ_MODEL,
                "api_key": settings.GROQ_API_KEY,
                "base_url": "https://api.groq.com/openai/v1",
                "api_type": "openai"
            }],
            "temperature": 0.1,
            "timeout": 120,
            "cache_seed": None  # Disable caching for fresh results
        }
        
        # Initialize custom agents (with real data sources)
        print("   📦 Loading custom agents...")
        self.custom_agents = {
            "agent_1": ClaimExtractor(),
            "agent_2": EvidenceRetriever(),
            "agent_3": ContradictionAnalyzer(),
            "agent_4": CredibilityAnalyst(),
            "agent_5": SentimentAnalyzer(),
            "agent_6": HistoricalAnalyst(),
            "agent_7": RiskScorer()
        }
        print("   ✅ Custom agents loaded")
        
        # Create AutoGen workflow coordinator
        print("   🤖 Creating AutoGen coordinator...")
        self.coordinator = autogen.AssistantAgent(
            name="ESG_Workflow_Coordinator",
            system_message=self._get_coordinator_prompt(),
            llm_config=self.llm_config
        )
        
        # Create user proxy for tool execution
        self.executor = autogen.UserProxyAgent(
            name="ESG_Analysis_Executor",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            code_execution_config=False  # Disable code execution for security
        )
        
        # Workflow state
        self.workflow_state = {
            "current_step": 0,
            "total_steps": 7,
            "results": {},
            "errors": []
        }
        
        print("   ✅ AutoGen orchestrator ready")
        print("   🔗 Workflow: 7-Agent ESG Analysis Pipeline\n")
    
    def _get_coordinator_prompt(self) -> str:
        """System prompt for AutoGen coordinator"""
        return """You are the ESG Analysis Workflow Coordinator.

Your role is to orchestrate a 7-agent ESG greenwashing detection workflow:

WORKFLOW STEPS:
1. Agent 1 (ClaimExtractor): Extract structured ESG claims from company content
2. Agent 2 (EvidenceRetriever): Gather multi-source evidence for each claim
3. Agent 3 (ContradictionAnalyzer): Detect contradictions between claims and evidence
4. Agent 4 (CredibilityAnalyst): Assess source credibility and bias
5. Agent 5 (SentimentAnalyzer): Analyze linguistic patterns and sentiment
6. Agent 6 (HistoricalAnalyst): Research company's ESG track record
7. Agent 7 (RiskScorer): Calculate final ESG score and greenwashing risk rating

RESPONSIBILITIES:
- Coordinate handoffs between agents
- Monitor workflow progress
- Report status updates
- Handle errors gracefully
- Ensure data quality

When workflow completes, respond with "WORKFLOW_COMPLETE" followed by a summary.
If errors occur, report them clearly and attempt to continue if possible.
"""
    
    def analyze_with_autogen(self, company: str, content: str = None) -> Dict[str, Any]:
        """
        Execute complete 7-agent ESG analysis using AutoGen orchestration
        
        Args:
            company: Company name to analyze
            content: ESG claims content (optional, will be fetched if None)
        
        Returns:
            Complete analysis results with ESG score and risk assessment
        """
        
        print(f"\n{'='*80}")
        print(f"🤖 AutoGen Hybrid Multi-Agent Analysis")
        print(f"{'='*80}")
        print(f"🏢 Company: {company}")
        print(f"🔄 Orchestration: AutoGen + Custom Agents")
        print(f"⏰ Start: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*80}\n")
        
        # Initialize results
        results = {
            "company": company,
            "orchestration_method": "AutoGen Hybrid",
            "timestamp": datetime.now().isoformat(),
            "workflow_status": "in_progress"
        }
        
        try:
            # Fetch content if not provided
            if not content:
                print("📄 [AutoGen] Fetching recent ESG content...")
                content = self._fetch_esg_content(company)
                if not content:
                    results["workflow_status"] = "failed"
                    results["error"] = "No ESG content found"
                    return results
            
            # Execute 7-agent workflow
            results = self._execute_workflow(company, content)
            
            # Generate AutoGen summary
            self._generate_autogen_summary(results)
            
            results["workflow_status"] = "completed"
            
            print(f"\n{'='*80}")
            print(f"✅ AutoGen Analysis Complete")
            print(f"⏰ End: {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'='*80}\n")
            
        except Exception as e:
            print(f"\n❌ AutoGen workflow error: {e}")
            results["workflow_status"] = "failed"
            results["error"] = str(e)
            import traceback
            results["traceback"] = traceback.format_exc()
        
        return results
    
    def _execute_workflow(self, company: str, content: str) -> Dict[str, Any]:
        """Execute the 7-agent workflow with AutoGen coordination"""
        
        results = {
            "company": company,
            "claims": [],
            "evidence": [],
            "contradiction_analysis": [],
            "credibility_analysis": None,
            "sentiment_analysis": [],
            "historical_analysis": None,
            "final_risk_assessment": None
        }
        
        # ===================================================================
        # AGENT 1: CLAIM EXTRACTION
        # ===================================================================
        self._update_workflow_state(1, "Claim Extraction")
        print(f"\n{'─'*80}")
        print("🤖 [AutoGen Step 1/7] Claim Extraction")
        print(f"{'─'*80}")
        
        claims_result = self.custom_agents["agent_1"].extract_claims(company, content)
        results["claims"] = claims_result.get("claims", [])
        
        if not results["claims"]:
            print("❌ No claims extracted - stopping workflow")
            return results
        
        self._notify_coordinator(f"Step 1 complete: {len(results['claims'])} claims extracted")
        
        # ===================================================================
        # AGENTS 2-5: PER-CLAIM ANALYSIS (with AutoGen monitoring)
        # ===================================================================
        for i, claim in enumerate(results["claims"], 1):
            print(f"\n{'─'*80}")
            print(f"🤖 [AutoGen] Processing Claim {i}/{len(results['claims'])}")
            print(f"{'─'*80}")
            print(f"📋 {claim.get('claim_text')[:100]}...")
            
            # AGENT 2: Evidence Retrieval
            self._update_workflow_state(2, f"Evidence Retrieval (Claim {i})")
            evidence = self.custom_agents["agent_2"].retrieve_evidence(claim, company)
            results["evidence"].append(evidence)
            
            evidence_count = len(evidence.get("evidence", []))
            self._notify_coordinator(f"Claim {i}: Retrieved {evidence_count} evidence sources")
            
            # AGENT 3: Contradiction Analysis
            self._update_workflow_state(3, f"Contradiction Analysis (Claim {i})")
            contradiction = self.custom_agents["agent_3"].analyze_claim(
                claim, evidence.get("evidence", [])
            )
            results["contradiction_analysis"].append(contradiction)
            
            verdict = contradiction.get("overall_verdict")
            self._notify_coordinator(f"Claim {i}: Verdict = {verdict}")
            
            # AGENT 5: Sentiment Analysis
            self._update_workflow_state(5, f"Sentiment Analysis (Claim {i})")
            sentiment = self.custom_agents["agent_5"].analyze_claim_language(
                claim, evidence.get("evidence", [])
            )
            results["sentiment_analysis"].append(sentiment)
            
            linguistic_risk = sentiment.get("overall_linguistic_risk", 0)
            self._notify_coordinator(f"Claim {i}: Linguistic risk = {linguistic_risk}/100")
        
        # ===================================================================
        # AGENT 4: OVERALL CREDIBILITY ANALYSIS
        # ===================================================================
        self._update_workflow_state(4, "Overall Credibility Analysis")
        print(f"\n{'─'*80}")
        print("🤖 [AutoGen Step 4/7] Source Credibility Analysis")
        print(f"{'─'*80}")
        
        all_evidence = []
        for ev in results["evidence"]:
            all_evidence.extend(ev.get("evidence", []))
        
        if all_evidence:
            results["credibility_analysis"] = self.custom_agents["agent_4"].analyze_sources(all_evidence)
            avg_cred = results["credibility_analysis"].get("aggregate_metrics", {}).get("average_credibility", 0)
            self._notify_coordinator(f"Average source credibility: {avg_cred:.2f}/1.0")
        
        # ===================================================================
        # AGENT 6: HISTORICAL ANALYSIS
        # ===================================================================
        self._update_workflow_state(6, "Historical Pattern Analysis")
        print(f"\n{'─'*80}")
        print("🤖 [AutoGen Step 6/7] Historical Track Record Analysis")
        print(f"{'─'*80}")
        
        results["historical_analysis"] = self.custom_agents["agent_6"].analyze_company_history(company)
        reputation = results["historical_analysis"].get("reputation_score", 50)
        self._notify_coordinator(f"Historical reputation score: {reputation}/100")
        
        # ===================================================================
        # AGENT 7: FINAL RISK SCORING
        # ===================================================================
        self._update_workflow_state(7, "Final ESG Scoring")
        print(f"\n{'─'*80}")
        print("🤖 [AutoGen Step 7/7] Final ESG Score & Risk Rating")
        print(f"{'─'*80}")
        
        results["final_risk_assessment"] = self.custom_agents["agent_7"].calculate_final_score(
            company, results
        )
        
        esg_score = results["final_risk_assessment"].get("esg_score", 0)
        risk_level = results["final_risk_assessment"].get("risk_level", "N/A")
        self._notify_coordinator(f"FINAL: ESG Score = {esg_score}/100, Risk = {risk_level}")
        
        return results
    
    def _fetch_esg_content(self, company: str) -> Optional[str]:
        """Fetch recent ESG content for company"""
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
            print(f"⚠️ Content fetching error: {e}")
            return None
    
    def _update_workflow_state(self, step: int, description: str):
        """Update workflow state for monitoring"""
        self.workflow_state["current_step"] = step
        self.workflow_state["current_description"] = description
        
        # Progress indicator
        progress = (step / self.workflow_state["total_steps"]) * 100
        print(f"\n📊 Workflow Progress: {progress:.0f}% ({step}/{self.workflow_state['total_steps']})")
    
    def _notify_coordinator(self, message: str):
        """Send notification to AutoGen coordinator"""
        try:
            # Create a simple notification (non-blocking)
            notification = f"[Agent Update] {message}"
            print(f"   💬 {notification}")
            
            # Store in workflow state
            if "notifications" not in self.workflow_state:
                self.workflow_state["notifications"] = []
            self.workflow_state["notifications"].append({
                "timestamp": datetime.now().isoformat(),
                "message": message
            })
        except Exception as e:
            print(f"   ⚠️ Notification error: {e}")
    
    def _generate_autogen_summary(self, results: Dict):
        """Generate executive summary using AutoGen LLM"""
        
        print(f"\n{'─'*80}")
        print("🤖 [AutoGen] Generating Executive Summary...")
        print(f"{'─'*80}")
        
        try:
            assessment = results.get("final_risk_assessment", {})
            
            summary_prompt = f"""Based on the ESG analysis results, generate a concise 3-paragraph executive summary:

Company: {results.get('company')}
ESG Score: {assessment.get('esg_score')}/100
Rating: {assessment.get('rating_grade')}
Risk Level: {assessment.get('risk_level')}
Greenwashing Risk: {assessment.get('greenwashing_risk_score')}/100

Claims Analyzed: {len(results.get('claims', []))}
Verified: {sum(1 for c in results.get('contradiction_analysis', []) if c.get('overall_verdict') == 'Verified')}
Contradicted: {sum(1 for c in results.get('contradiction_analysis', []) if c.get('overall_verdict') == 'Contradicted')}

Generate a professional summary for C-level executives. Focus on:
1. Overall ESG performance assessment
2. Key risks or concerns identified
3. Recommendation for stakeholders

Keep it concise and actionable."""

            # Use AutoGen to generate summary
            self.executor.initiate_chat(
                self.coordinator,
                message=summary_prompt,
                max_turns=1
            )
            
            # Extract summary from chat
            chat_history = self.executor.chat_messages.get(self.coordinator, [])
            if chat_history:
                last_message = chat_history[-1]
                if last_message.get("role") == "assistant":
                    summary = last_message.get("content", "")
                    results["executive_summary"] = summary
                    
                    print(f"\n{'─'*80}")
                    print("📝 EXECUTIVE SUMMARY (AutoGen Generated)")
                    print(f"{'─'*80}")
                    print(summary)
                    print(f"{'─'*80}")
        
        except Exception as e:
            print(f"⚠️ Summary generation error: {e}")
            results["executive_summary"] = "Summary generation failed - see detailed report"


# Global singleton instance with proper error handling
hybrid_orchestrator = None

try:
    print("🔧 Attempting to initialize AutoGen Hybrid Orchestrator...")
    hybrid_orchestrator = HybridAutoGenOrchestrator()
    print("✅ AutoGen Hybrid Orchestrator initialized successfully\n")
except ImportError as e:
    print(f"❌ AutoGen import error: {e}")
    print("   Run: pip install pyautogen openai")
    print("   Falling back to direct orchestration\n")
    hybrid_orchestrator = None
except Exception as e:
    print(f"❌ Failed to initialize AutoGen orchestrator: {e}")
    print("   Falling back to direct orchestration\n")
    import traceback
    traceback.print_exc()
    hybrid_orchestrator = None

