"""
Debate Orchestrator: Multi-agent collaboration for conflicting findings
Implements voting-based consensus mechanism
"""
import os
from typing import List, Dict, Tuple
from collections import Counter
from langchain_groq import ChatGroq
from core.state_schema import ESGState

class DebateOrchestrator:
    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.7,  # Higher for diverse reasoning
            api_key=os.getenv("GROQ_API_KEY")
        )
        self.max_rounds = 3
        self.conflict_threshold = 0.3  # Agents must differ by 30% to trigger debate
    
    def conduct_debate(self, state: ESGState) -> ESGState:
        """
        Multi-agent debate mechanism for conflicting findings
        Based on research showing 10.4% accuracy improvement with voting
        """
        # Step 1: Extract agent positions
        agent_positions = self.extract_positions(state)
        
        # Step 2: Detect conflicts
        conflicts = self.detect_conflicts(agent_positions)
        
        if not conflicts:
            state["agent_outputs"].append({
                "agent": "debate_orchestrator",
                "action": "no_conflict_detected",
                "message": "All agents in agreement, skipping debate"
            })
            return state
        
        state["agent_outputs"].append({
            "agent": "debate_orchestrator",
            "action": "conflict_detected",
            "conflicting_agents": list(conflicts.keys()),
            "initiating_debate": True
        })
        
        # Step 3: Run structured debate rounds
        debate_history = []
        for round_num in range(self.max_rounds):
            round_arguments = self.run_debate_round(
                state, 
                conflicts, 
                debate_history, 
                round_num
            )
            debate_history.extend(round_arguments)
        
        # Step 4: Voting-based resolution
        final_verdict = self.resolve_by_voting(agent_positions, debate_history, state)
        
        # Step 5: Update state with debate results
        state["confidence"] = final_verdict["confidence"]
        state["risk_level"] = final_verdict["verdict"]
        
        state["agent_outputs"].append({
            "agent": "debate_resolution",
            "debate_rounds": self.max_rounds,
            "total_arguments": len(debate_history),
            "final_verdict": final_verdict["verdict"],
            "confidence": final_verdict["confidence"],
            "vote_distribution": final_verdict["vote_distribution"],
            "debate_summary": debate_history
        })
        
        return state
    
    def extract_positions(self, state: ESGState) -> Dict[str, Dict]:
        """Extract each agent's position from outputs"""
        positions = {}
        
        for output in state["agent_outputs"]:
            agent_name = output.get("agent")
            
            # Skip non-analytical agents
            if agent_name in ["supervisor", "report_generation", "debate_orchestrator"]:
                continue
            
            # Extract position based on agent output
            if agent_name == "risk_scoring":
                positions[agent_name] = {
                    "verdict": output.get("risk_level", "MODERATE"),
                    "confidence": output.get("confidence", 0.5),
                    "reasoning": f"Risk score: {output.get('base_score', 'N/A')}"
                }
            elif agent_name == "contradiction_analysis":
                # Infer verdict from contradiction findings
                contradictions_found = output.get("contradictions_count", 0)
                verdict = "HIGH" if contradictions_found > 2 else "MODERATE" if contradictions_found > 0 else "LOW"
                positions[agent_name] = {
                    "verdict": verdict,
                    "confidence": output.get("confidence", 0.5),
                    "reasoning": output.get("output", "")
                }
            else:
                # Generic extraction
                positions[agent_name] = {
                    "verdict": self.infer_verdict_from_output(output),
                    "confidence": output.get("confidence", 0.5),
                    "reasoning": str(output.get("output", ""))[:200]
                }
        
        return positions
    
    def infer_verdict_from_output(self, output: Dict) -> str:
        """Infer risk verdict from agent output"""
        output_str = str(output.get("output", "")).lower()
        
        # Look for risk indicators in output
        if any(word in output_str for word in ["high risk", "severe", "critical", "major concern"]):
            return "HIGH"
        elif any(word in output_str for word in ["low risk", "minimal", "acceptable", "verified"]):
            return "LOW"
        else:
            return "MODERATE"
    
    def detect_conflicts(self, positions: Dict[str, Dict]) -> Dict[str, Dict]:
        """Identify agents with conflicting verdicts"""
        if len(positions) < 2:
            return {}
        
        verdicts = [p["verdict"] for p in positions.values()]
        unique_verdicts = set(verdicts)
        
        # No conflict if all agree
        if len(unique_verdicts) <= 1:
            return {}
        
        # Return all positions if there's disagreement
        return positions
    
    def run_debate_round(
        self, 
        state: ESGState, 
        conflicts: Dict, 
        debate_history: List[Dict],
        round_num: int
    ) -> List[Dict]:
        """Execute one round of structured debate"""
        round_arguments = []
        
        # Previous arguments for context
        previous_context = "\n".join([
            f"- {arg['agent']}: {arg['argument'][:150]}..."
            for arg in debate_history[-3:]  # Last 3 arguments
        ]) if debate_history else "No previous arguments"
        
        for agent_name, position in conflicts.items():
            prompt = f"""You are the {agent_name} in an ESG greenwashing analysis debate.

CLAIM BEING ANALYZED:
Company: {state['company']}
Industry: {state['industry']}
Claim: {state['claim']}

YOUR POSITION:
Verdict: {position['verdict']} risk
Confidence: {position['confidence']:.2%}
Initial Reasoning: {position['reasoning']}

OPPOSING POSITIONS:
{self.format_opposing_views(conflicts, agent_name)}

PREVIOUS DEBATE CONTEXT (Round {round_num + 1}/{self.max_rounds}):
{previous_context}

TASK:
Defend your {position['verdict']} risk verdict with specific evidence.
Address opposing arguments with concrete counterpoints.
Cite specific data points, timestamps, or regulatory violations if applicable.

Provide a concise argument (3-4 sentences)."""

            try:
                response = self.llm.invoke(prompt)
                argument = response.content
                
                round_arguments.append({
                    "round": round_num + 1,
                    "agent": agent_name,
                    "position": position["verdict"],
                    "argument": argument
                })
                
            except Exception as e:
                print(f"⚠️  Debate error for {agent_name}: {e}")
        
        return round_arguments
    
    def format_opposing_views(self, conflicts: Dict, current_agent: str) -> str:
        """Format other agents' positions for debate context"""
        opposing = []
        for agent_name, position in conflicts.items():
            if agent_name != current_agent:
                opposing.append(
                    f"- {agent_name}: {position['verdict']} risk "
                    f"({position['confidence']:.0%} confidence)"
                )
        return "\n".join(opposing) if opposing else "No opposing views"
    
    def resolve_by_voting(
        self, 
        positions: Dict[str, Dict], 
        debate_history: List[Dict],
        state: ESGState
    ) -> Dict:
        """
        Voting-based consensus with confidence weighting
        Research shows this improves accuracy by 10.4% over single agent
        ENHANCED: Now passes conflicting agents to verdict for escalation
        """
        weighted_votes = []
        
        for agent_name, position in positions.items():
            confidence = position["confidence"]
            verdict = position["verdict"]
            
            # Weight votes by confidence (0.9 confidence = 9 votes)
            vote_weight = int(confidence * 10)
            weighted_votes.extend([verdict] * vote_weight)
        
        # Count votes
        vote_counts = Counter(weighted_votes)
        
        if not vote_counts:
            # Fallback if no votes
            return {
                "verdict": "MODERATE",
                "confidence": 0.5,
                "vote_distribution": {},
                "conflicting_agents": []  # NEW
            }
        
        winning_verdict = vote_counts.most_common(1)[0][0]
        total_votes = sum(vote_counts.values())
        winning_votes = vote_counts[winning_verdict]
        
        # Consensus strength = % of votes for winner
        consensus_confidence = winning_votes / total_votes
        
        # Adjust confidence based on debate quality
        debate_quality_bonus = min(0.1, len(debate_history) * 0.01)  # Up to +10%
        final_confidence = min(0.95, consensus_confidence + debate_quality_bonus)
        
        # ============================================================
        # NEW: Identify conflicting agents (those who didn't vote for winner)
        # ============================================================
        conflicting_agents = []
        for agent_name, position in positions.items():
            if position["verdict"] != winning_verdict:
                conflicting_agents.append(agent_name)
        
        # ============================================================
        # NEW: Calculate conflict severity
        # ============================================================
        total_agents = len(positions)
        conflict_ratio = len(conflicting_agents) / max(total_agents, 1)
        
        # If high conflict (60%+ disagree), reduce confidence
        if conflict_ratio >= 0.60:
            final_confidence *= (1 - (conflict_ratio * 0.3))  # Reduce by up to 30%
            print(f"⚠️  High conflict detected: {len(conflicting_agents)}/{total_agents} agents disagree")
            print(f"   Reducing confidence by {conflict_ratio * 30:.0%}")
        
        # ============================================================
        # NEW: Return enhanced verdict with conflict information
        # ============================================================
        return {
            "verdict": winning_verdict,
            "confidence": final_confidence,
            "vote_distribution": dict(vote_counts),
            "consensus_strength": consensus_confidence,
            "conflicting_agents": conflicting_agents,  # NEW: For escalation
            "conflict_ratio": conflict_ratio,          # NEW: For escalation
            "total_agents": total_agents               # NEW: For logging
        }


# Node function for LangGraph
def debate_node(state: ESGState) -> ESGState:
    """LangGraph node wrapper for debate orchestrator"""
    orchestrator = DebateOrchestrator()
    return orchestrator.conduct_debate(state)
