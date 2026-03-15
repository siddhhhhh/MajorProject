"""
Confidence Monitoring: Triggers iterative refinement
Implements self-correction loop when confidence < threshold
"""
from core.state_schema import ESGState

class ConfidenceMonitor:
    def __init__(self, threshold: float = 0.75, max_iterations: int = 2):
        self.threshold = threshold
        self.max_iterations = max_iterations
    
    def check_confidence(self, state: ESGState) -> ESGState:
        """Assess aggregate confidence - FIXED to account for debates"""
        
        # Calculate average confidence from successful agents only
        agent_confidences = [
            output.get("confidence", 0.0)
            for output in state["agent_outputs"]
            if "confidence" in output 
            and output.get("agent") not in ["supervisor", "debate_orchestrator", "debate_resolution"]
            and "error" not in output
        ]
        
        if not agent_confidences:
            avg_confidence = 0.5
        else:
            avg_confidence = sum(agent_confidences) / len(agent_confidences)
        
        # FIXED: Reduce confidence if debate was activated
        debate_outputs = [o for o in state["agent_outputs"] 
                        if o.get('agent') in ['debate_orchestrator', 'debate_resolution']]
        
        if debate_outputs:
            for debate in debate_outputs:
                conflicting = debate.get('conflicting_agents', [])
                if len(conflicting) > 0:
                    conflict_ratio = len(conflicting) / 13  # 13 analytical agents
                    # Reduce confidence by up to 25% based on conflict severity
                    confidence_penalty = min(0.25, conflict_ratio * 0.30)
                    avg_confidence *= (1 - confidence_penalty)
                    print(f"⚠️  Confidence reduced by {confidence_penalty:.0%} due to agent conflicts")
        
        state["confidence"] = avg_confidence
        
        # Decision: revise or finalize (existing logic)
        if avg_confidence < 0.5 and state["iteration_count"] < self.max_iterations:
            state["needs_revision"] = True
            state["iteration_count"] += 1
            
            state["agent_outputs"].append({
                "agent": "confidence_monitor",
                "action": "triggered_revision",
                "reason": f"Confidence {avg_confidence:.2%} critically low",
                "iteration": state["iteration_count"]
            })
        else:
            state["needs_revision"] = False
            
            state["agent_outputs"].append({
                "agent": "confidence_monitor",
                "action": "finalized",
                "reason": f"Confidence {avg_confidence:.2%}",
                "final_confidence": avg_confidence
            })
        
        return state

    
    def should_revise(self, state: ESGState) -> str:
        """Conditional edge function for LangGraph routing"""
        return "revise" if state["needs_revision"] else "end"

# Node and edge functions for LangGraph
def confidence_check_node(state: ESGState) -> ESGState:
    monitor = ConfidenceMonitor(threshold=0.75, max_iterations=2)
    return monitor.check_confidence(state)

def should_revise_edge(state: ESGState) -> str:
    monitor = ConfidenceMonitor()
    return monitor.should_revise(state)
