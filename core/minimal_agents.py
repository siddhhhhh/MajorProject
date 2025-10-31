"""
Minimal agent implementations for Phase 1 verification
These are simplified versions to test the LangGraph workflow
Full agents will be integrated in later phases
"""
import os
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from core.state_schema import ESGState

class MinimalClaimExtractor:
    """Simplified claim extraction for Phase 1"""
    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY")
        )
    
    def extract(self, state: ESGState) -> ESGState:
        """Extract and validate ESG claim"""
        prompt = f"""Extract the key ESG claim from this input:
Company: {state['company']}
Claim: {state['claim']}

Return a structured summary:
1. Main claim statement
2. Claim category (emissions, renewable energy, waste reduction, etc.)
3. Claimed impact/metric"""

        try:
            response = self.llm.invoke(prompt)
            
            state["agent_outputs"].append({
                "agent": "claim_extraction",
                "output": response.content,
                "confidence": 0.8
            })
        except Exception as e:
            state["agent_outputs"].append({
                "agent": "claim_extraction",
                "error": str(e),
                "confidence": 0.0
            })
        
        return state

class MinimalEvidenceRetriever:
    """Simplified evidence retrieval for Phase 1"""
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0,
            google_api_key=os.getenv("GEMINI_API_KEY")
        )
    
    def retrieve(self, state: ESGState) -> ESGState:
        """Simulate evidence gathering (Phase 1 uses LLM knowledge)"""
        prompt = f"""Based on your knowledge, provide evidence about this ESG claim:
Company: {state['company']}
Industry: {state['industry']}
Claim: {state['claim']}

Provide:
1. Known facts about this company's ESG track record
2. Any controversies or contradictions
3. Confidence level (0.0-1.0)"""

        try:
            response = self.llm.invoke(prompt)
            
            # Simulate evidence structure
            state["evidence"].append({
                "source": "llm_knowledge_base",
                "content": response.content,
                "relevance": 0.7
            })
            
            state["agent_outputs"].append({
                "agent": "evidence_retrieval",
                "evidence_count": len(state["evidence"]),
                "confidence": 0.7
            })
        except Exception as e:
            state["agent_outputs"].append({
                "agent": "evidence_retrieval",
                "error": str(e),
                "confidence": 0.0
            })
        
        return state

class MinimalRiskScorer:
    """Simplified risk scoring for Phase 1"""
    def __init__(self):
        # MSCI-based industry thresholds (from your existing system)
        self.INDUSTRY_THRESHOLDS = {
            "Energy": {"high": 0.7, "moderate": 0.4},
            "Consumer Goods": {"high": 0.6, "moderate": 0.3},
            "Automotive": {"high": 0.75, "moderate": 0.5},
            "Technology": {"high": 0.5, "moderate": 0.25},
            "Financial Services": {"high": 0.55, "moderate": 0.3},
            "Healthcare": {"high": 0.5, "moderate": 0.25},
            "default": {"high": 0.65, "moderate": 0.35}
        }
    
    def score(self, state: ESGState) -> ESGState:
        """Calculate risk score with industry adjustment"""
        # Simplified scoring based on complexity and evidence
        base_score = state["complexity_score"] * 0.6  # Higher complexity = higher risk
        
        # Adjust based on evidence quality
        if state["evidence"]:
            avg_relevance = sum(e.get("relevance", 0.5) for e in state["evidence"]) / len(state["evidence"])
            base_score += (1 - avg_relevance) * 0.4  # Low relevance = higher risk
        
        # Apply industry-specific thresholds
        industry = state["industry"]
        thresholds = self.INDUSTRY_THRESHOLDS.get(industry, self.INDUSTRY_THRESHOLDS["default"])
        
        if base_score >= thresholds["high"]:
            risk_level = "HIGH"
        elif base_score >= thresholds["moderate"]:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"
        
        state["risk_level"] = risk_level
        state["confidence"] = 0.75  # Fixed for Phase 1
        
        state["agent_outputs"].append({
            "agent": "risk_scoring",
            "base_score": round(base_score, 3),
            "industry": industry,
            "thresholds": thresholds,
            "risk_level": risk_level,
            "confidence": 0.75
        })
        
        return state

# LangGraph node wrappers
def claim_extraction_node(state: ESGState) -> ESGState:
    agent = MinimalClaimExtractor()
    return agent.extract(state)

def evidence_retrieval_node(state: ESGState) -> ESGState:
    agent = MinimalEvidenceRetriever()
    return agent.retrieve(state)

def risk_scoring_node(state: ESGState) -> ESGState:
    agent = MinimalRiskScorer()
    return agent.score(state)
