"""
Diagnostic script to inspect your actual agent methods
"""
import sys
from pathlib import Path
import inspect

# Add agents to path
agents_dir = Path(__file__).parent / "agents"
sys.path.insert(0, str(agents_dir))

def inspect_agent(module_name, class_name):
    """Inspect an agent class and show all its methods"""
    try:
        module = __import__(module_name)
        agent_class = getattr(module, class_name)
        
        print(f"\n{'='*70}")
        print(f"Agent: {class_name} (from {module_name}.py)")
        print(f"{'='*70}")
        
        # Get all methods
        methods = inspect.getmembers(agent_class, predicate=inspect.isfunction)
        
        for method_name, method_obj in methods:
            if not method_name.startswith('_'):  # Skip private methods
                sig = inspect.signature(method_obj)
                print(f"  ✓ {method_name}{sig}")
        
        return True
    except Exception as e:
        print(f"  ❌ Error inspecting {class_name}: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("INSPECTING YOUR ACTUAL AGENT METHODS")
    print("="*70)
    
    agents = [
        ("claim_extractor", "ClaimExtractor"),
        ("evidence_retriever", "EvidenceRetriever"),
        ("contradiction_analyzer", "ContradictionAnalyzer"),
        ("historical_analyst", "HistoricalAnalyst"),
        ("industry_comparator", "IndustryComparator"),
        ("risk_scorer", "RiskScorer"),
        ("sentiment_analyzer", "SentimentAnalyzer"),
        ("credibility_analyst", "CredibilityAnalyst"),
        ("confidence_scorer", "ConfidenceScorer"),
        ("realtime_monitor", "RealtimeMonitor"),
        ("conflict_resolver", "ConflictResolver"),
    ]
    
    for module_name, class_name in agents:
        inspect_agent(module_name, class_name)
    
    print("\n" + "="*70)
    print("Inspection complete! Use this info to fix agent_wrappers.py")
    print("="*70)

if __name__ == "__main__":
    main()
