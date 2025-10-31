"""
Supervisor Agent: Routes claims to appropriate workflow paths
Implements dynamic routing based on claim complexity
"""
import os
from typing import Literal
from langchain_groq import ChatGroq
from core.state_schema import ESGState

class SupervisorAgent:
    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY")
        )
    
    def assess_complexity(self, state: ESGState) -> ESGState:
        """
        Analyze claim complexity to determine routing path
        Returns updated state with complexity_score
        """
        claim = state["claim"]
        company = state["company"]
        
        prompt = f"""Analyze the complexity of this ESG claim on a scale of 0.0 to 1.0:

Claim: {claim}
Company: {company}

Complexity factors:
- Quantitative specificity (0.1): Has specific numbers/percentages? (e.g., "reduced emissions by 30%")
- Temporal clarity (0.2): Specific timeframe? (e.g., "in 2024" vs "committed to")
- Verifiability (0.3): Can be verified with public data? (emissions data, financial reports)
- Ambiguity (0.2): Vague terms like "sustainable", "eco-friendly", "green"
- Scope (0.2): Broad claims vs specific initiatives

Examples:
- "BP reduced carbon emissions by 15% in 2023" → 0.2 (specific, verifiable)
- "We are committed to sustainability" → 0.9 (vague, unverifiable)
- "Invested $500M in renewable energy projects" → 0.4 (specific amount, moderate complexity)

Return ONLY a single float between 0.0 and 1.0, nothing else."""

        try:
            response = self.llm.invoke(prompt)
            complexity = float(response.content.strip())
            
            # Clamp between 0 and 1
            complexity = max(0.0, min(1.0, complexity))
            
        except Exception as e:
            print(f"Error in complexity assessment: {e}")
            complexity = 0.5  # Default to standard track on error
        
        state["complexity_score"] = complexity
        state["agent_outputs"].append({
            "agent": "supervisor",
            "action": "complexity_assessment",
            "complexity_score": complexity,
            "reasoning": f"Assessed claim complexity: {complexity:.2f}"
        })
        
        return state
    
    def route_workflow(self, state: ESGState) -> Literal["fast_track", "standard_track", "deep_analysis"]:
        """
        Determine which workflow path to take based on complexity
        """
        complexity = state["complexity_score"]
        
        if complexity < 0.3:
            path = "fast_track"
        elif complexity < 0.7:
            path = "standard_track"
        else:
            path = "deep_analysis"
        
        state["workflow_path"] = path
        state["agent_outputs"].append({
            "agent": "supervisor",
            "action": "workflow_routing",
            "selected_path": path,
            "reason": f"Complexity {complexity:.2f} → {path}"
        })
        
        return path

# Node functions for LangGraph
def assess_complexity_node(state: ESGState) -> ESGState:
    """Wrapper function for LangGraph node"""
    supervisor = SupervisorAgent()
    return supervisor.assess_complexity(state)

def classify_workflow(state: ESGState) -> str:
    """Conditional edge function for routing"""
    supervisor = SupervisorAgent()
    return supervisor.route_workflow(state)
