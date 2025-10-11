import autogen
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from config.settings import settings

class AutoGenESGOrchestrator:
    """
    AutoGen-based multi-agent orchestration for ESG analysis
    Implements the original mega-prompt architecture
    """
    
    def __init__(self):
        self.name = "AutoGen ESG Orchestrator"
        
        # Configure LLMs for AutoGen
        self.llm_config_gemini = {
            "model": settings.GEMINI_MODEL,
            "api_key": settings.GEMINI_API_KEY,
            "api_type": "google"
        }
        
        self.llm_config_groq = {
            "model": settings.GROQ_MODEL,
            "api_key": settings.GROQ_API_KEY,
            "base_url": "https://api.groq.com/openai/v1",
            "api_type": "openai"
        }
        
        # Initialize AutoGen agents
        self._initialize_agents()
        
        print(f"✅ AutoGen Orchestrator initialized with {len(self.agents)} agents")
    
    def _initialize_agents(self):
        """Initialize all 7 AutoGen agents"""
        
        # Agent 1: Claim Extractor
        self.agent_1 = autogen.AssistantAgent(
            name="ClaimExtractor",
            system_message=self._get_agent_prompt(1),
            llm_config={
                "config_list": [self.llm_config_gemini],
                "temperature": 0.1,
                "timeout": 120
            }
        )
        
        # Agent 2: Evidence Retriever
        self.agent_2 = autogen.AssistantAgent(
            name="EvidenceRetriever",
            system_message=self._get_agent_prompt(2),
            llm_config={
                "config_list": [self.llm_config_groq],
                "temperature": 0.1,
                "timeout": 120
            },
            code_execution_config={
                "work_dir": "temp",
                "use_docker": False
            }
        )
        
        # Agent 3: Contradiction Analyzer
        self.agent_3 = autogen.AssistantAgent(
            name="ContradictionAnalyzer",
            system_message=self._get_agent_prompt(3),
            llm_config={
                "config_list": [self.llm_config_gemini],
                "temperature": 0.1,
                "timeout": 120
            }
        )
        
        # Agent 4: Credibility Analyst
        self.agent_4 = autogen.AssistantAgent(
            name="CredibilityAnalyst",
            system_message=self._get_agent_prompt(4),
            llm_config={
                "config_list": [self.llm_config_groq],
                "temperature": 0.1,
                "timeout": 120
            }
        )
        
        # Agent 5: Sentiment Analyzer
        self.agent_5 = autogen.AssistantAgent(
            name="SentimentAnalyzer",
            system_message=self._get_agent_prompt(5),
            llm_config={
                "config_list": [self.llm_config_groq],
                "temperature": 0.1,
                "timeout": 120
            }
        )
        
        # Agent 6: Historical Analyst
        self.agent_6 = autogen.AssistantAgent(
            name="HistoricalAnalyst",
            system_message=self._get_agent_prompt(6),
            llm_config={
                "config_list": [self.llm_config_groq],
                "temperature": 0.1,
                "timeout": 120
            }
        )
        
        # Agent 7: Risk Scorer
        self.agent_7 = autogen.AssistantAgent(
            name="RiskScorer",
            system_message=self._get_agent_prompt(7),
            llm_config={
                "config_list": [self.llm_config_gemini],
                "temperature": 0.1,
                "timeout": 120
            }
        )
        
        # User Proxy for coordination
        self.coordinator = autogen.UserProxyAgent(
            name="Coordinator",
            system_message="ESG Analysis Coordinator. Execute workflow and aggregate results.",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10,
            code_execution_config={
                "work_dir": "temp",
                "use_docker": False
            }
        )
        
        # Group chat for multi-agent collaboration
        self.agents = [
            self.agent_1, self.agent_2, self.agent_3, 
            self.agent_4, self.agent_5, self.agent_6, 
            self.agent_7
        ]
        
        self.group_chat = autogen.GroupChat(
            agents=self.agents + [self.coordinator],
            messages=[],
            max_round=20,
            speaker_selection_method="round_robin"
        )
        
        self.manager = autogen.GroupChatManager(
            groupchat=self.group_chat,
            llm_config={
                "config_list": [self.llm_config_gemini],
                "temperature": 0.1
            }
        )
    
    def _get_agent_prompt(self, agent_num: int) -> str:
        """Get system prompt for each agent"""
        
        prompts = {
            1: """You are the Claim Extraction Specialist.
ROLE: Extract structured, verifiable ESG claims from company content.
OUTPUT: Return ONLY valid JSON with claims array.
Format: {"company": "...", "claims": [{"claim_id": 1, "claim_text": "...", "category": "...", "specificity_score": X}]}
Be precise and extract ALL verifiable claims.""",
            
            2: """You are the Evidence Retrieval Specialist.
ROLE: Gather multi-source evidence for each claim.
TASK: Search web, databases, and documents for supporting/contradicting evidence.
OUTPUT: JSON with evidence array including source, url, snippet, credibility.
Use Python code to call search functions if needed.""",
            
            3: """You are the Contradiction Analyzer.
ROLE: Compare claims against evidence to detect contradictions.
OUTPUT: JSON with verification verdict (Verified/Contradicted/Partially True/Unverifiable), 
confidence level, and specific contradictions found.""",
            
            4: """You are the Credibility Analyst.
ROLE: Assess source credibility and detect bias.
OUTPUT: JSON with credibility scores (0-1.0) for each source and bias classification.""",
            
            5: """You are the Sentiment & Linguistic Analyst.
ROLE: Detect greenwashing language patterns and sentiment divergence.
OUTPUT: JSON with sentiment scores, buzzword count, and greenwashing flags.""",
            
            6: """You are the Historical Analyst.
ROLE: Research company's ESG track record and past controversies.
OUTPUT: JSON with violations, greenwashing history, and reputation score.""",
            
            7: """You are the Risk Scorer & ESG Rating Specialist.
ROLE: Synthesize all analyses into final ESG score and greenwashing risk rating.
OUTPUT: JSON with ESG score (0-100), risk level, rating grade (AAA-CCC), and top 3 reasons."""
        }
        
        return prompts.get(agent_num, "ESG Analysis Agent")
    
    def analyze_company_autogen(self, company: str, content: str) -> Dict[str, Any]:
        """
        Run complete ESG analysis using AutoGen multi-agent system
        """
        
        print(f"\n{'='*80}")
        print(f"🤖 AutoGen Multi-Agent Analysis: {company}")
        print(f"{'='*80}")
        
        # Create analysis task
        task = f"""
Analyze the following ESG claims for {company}:

CONTENT:
{content}

WORKFLOW:
1. Agent 1 (ClaimExtractor): Extract all ESG claims
2. Agent 2 (EvidenceRetriever): Gather evidence for each claim
3. Agent 3 (ContradictionAnalyzer): Analyze contradictions
4. Agent 4 (CredibilityAnalyst): Assess source credibility
5. Agent 5 (SentimentAnalyzer): Analyze language patterns
6. Agent 6 (HistoricalAnalyst): Research company history
7. Agent 7 (RiskScorer): Calculate final ESG score and risk rating

Each agent must output valid JSON and pass results to the next agent.
Final output should be a comprehensive ESG risk report.
"""
        
        # Initiate group chat
        self.coordinator.initiate_chat(
            self.manager,
            message=task
        )
        
        # Extract results from chat history
        results = self._extract_results_from_chat()
        
        return results
    
    def _extract_results_from_chat(self) -> Dict[str, Any]:
        """Extract structured results from AutoGen chat history"""
        
        # This would parse the conversation and extract JSON outputs
        # For now, return placeholder
        return {
            "company": "Company",
            "analysis_method": "AutoGen Multi-Agent",
            "status": "completed",
            "results": "See chat history for full analysis"
        }

# Global instance
autogen_orchestrator = AutoGenESGOrchestrator()
