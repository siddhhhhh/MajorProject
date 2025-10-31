"""
Phase 2 Integration Test - UPDATED with recursion_limit config
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

load_dotenv()

def test_agent_imports():
    """Test that all your agents can be imported"""
    print("\n" + "="*70)
    print("TESTING AGENT IMPORTS")
    print("="*70)
    
    try:
        from core.agent_wrappers import (
            claim_extraction_node,
            evidence_retrieval_node,
            contradiction_analysis_node,
            temporal_analysis_node,
            peer_comparison_node,
            risk_scoring_node,
            sentiment_analysis_node,
            credibility_analysis_node,
            realtime_monitoring_node,
            confidence_scoring_node
        )
        print("\n✅ All agent wrappers imported successfully!")
        return True
    except Exception as e:
        print(f"\n❌ Agent import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_quick_workflow():
    """Quick test with your actual agents"""
    print("\n" + "="*70)
    print("QUICK WORKFLOW TEST")
    print("="*70)
    
    try:
        from core.workflow_phase2 import build_phase2_graph
        
        app = build_phase2_graph()
        
        initial_state = {
            "claim": "Microsoft reduced carbon emissions by 10% in 2024",
            "company": "Microsoft",
            "industry": "Technology",
            "complexity_score": 0.0,
            "workflow_path": "",
            "evidence": [],
            "confidence": 0.0,
            "risk_level": "",
            "agent_outputs": [],
            "iteration_count": 0,
            "needs_revision": False,
            "final_verdict": {},
            "report": ""
        }
        
        # FIXED: Add recursion_limit to config
        config = {
            "configurable": {
                "thread_id": "test_integration"
            },
            "recursion_limit": 50  # FIXED: Increase from default 25
        }
        
        print("\n🚀 Running workflow with your actual agents...")
        print("⏳ This may take 30-60 seconds for live API calls...")
        
        result = app.invoke(initial_state, config)
        
        print(f"\n{'='*70}")
        print("WORKFLOW RESULTS")
        print("="*70)
        print(f"✅ Workflow completed!")
        print(f"Risk Level: {result['risk_level']}")
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"Workflow Path: {result['workflow_path']}")
        
        # Show which agents actually executed
        executed_agents = [o.get('agent') for o in result['agent_outputs']]
        unique_agents = set(executed_agents)
        print(f"\n📊 Agents Executed ({len(unique_agents)}):")
        for agent in sorted(unique_agents):
            count = executed_agents.count(agent)
            print(f"  ✓ {agent} (executed {count}x)")
        
        # Show successful vs failed
        successful = len([o for o in result['agent_outputs'] if 'error' not in o])
        failed = len([o for o in result['agent_outputs'] if 'error' in o])
        print(f"\n✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        
        # Show report preview
        if result.get('report'):
            print(f"\n📄 REPORT PREVIEW:")
            print(result['report'][:500])
        
        return True
        
    except Exception as e:
        print(f"\n❌ Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*70)
    print("PHASE 2 INTEGRATION VERIFICATION")
    print("Testing with YOUR actual agents from agents/ directory")
    print("="*70)
    
    results = []
    results.append(("Agent Imports", test_agent_imports()))
    results.append(("Quick Workflow", test_quick_workflow()))
    
    print("\n" + "="*70)
    print("INTEGRATION TEST SUMMARY")
    print("="*70)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    if all(result[1] for result in results):
        print("\n🎉 Your agents are integrated! Now run full Phase 2 tests:")
        print("   python test_phase2.py")
    else:
        print("\n⚠️  Integration issues detected. Check error messages above.")

if __name__ == "__main__":
    main()
