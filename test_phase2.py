"""
Phase 2 Verification: Test full agent integration and debate mechanism
UPDATED: Added recursion_limit to prevent infinite loops
"""
import os
from dotenv import load_dotenv
from core.workflow_phase2 import build_phase2_graph

load_dotenv()

def test_debate_mechanism():
    """Test deep analysis with debate for controversial claim"""
    print("\n" + "="*70)
    print("PHASE 2 TEST 1: Debate Mechanism (BP Net-Zero Claim)")
    print("="*70)
    
    app = build_phase2_graph()
    
    initial_state = {
        "claim": "BP is committed to becoming a net-zero company by 2050",
        "company": "BP",
        "industry": "Energy",
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
    
    config = {
        "configurable": {"thread_id": "test_debate_bp"},
        "recursion_limit": 50  # FIXED
    }
    
    try:
        print("⏳ Running deep analysis workflow (may take 60+ seconds)...")
        result = app.invoke(initial_state, config)
        
        print(f"\n✅ Phase 2 workflow completed!")
        print(f"Workflow Path: {result['workflow_path']}")
        print(f"Risk Level: {result['risk_level']}")
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"Iterations: {result['iteration_count']}")
        
        # Check if debate was triggered
        debate_outputs = [o for o in result['agent_outputs'] if o.get('agent') == 'debate_orchestrator']
        if debate_outputs:
            print(f"\n🗣️  DEBATE ACTIVATED:")
            for debate_output in debate_outputs:
                if debate_output.get('action') == 'conflict_detected':
                    print(f"  Conflicting agents: {debate_output.get('conflicting_agents', [])}")
                elif debate_output.get('action') == 'no_conflict_detected':
                    print(f"  {debate_output.get('message')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_standard_track():
    """Test standard track for moderate complexity"""
    print("\n" + "="*70)
    print("PHASE 2 TEST 2: Standard Track (Coca-Cola)")
    print("="*70)
    
    app = build_phase2_graph()
    
    initial_state = {
        "claim": "Coca-Cola committed to making all packaging recyclable by 2030",
        "company": "Coca-Cola",
        "industry": "Consumer Goods",
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
    
    config = {
        "configurable": {"thread_id": "test_standard_cocacola"},
        "recursion_limit": 50  # FIXED
    }
    
    try:
        print("⏳ Running standard track workflow...")
        result = app.invoke(initial_state, config)
        
        print(f"\n✅ Standard track completed!")
        print(f"Risk Level: {result['risk_level']}")
        print(f"Confidence: {result['confidence']:.2%}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fast_track():
    """Test fast track for simple claims"""
    print("\n" + "="*70)
    print("PHASE 2 TEST 3: Fast Track (Microsoft)")
    print("="*70)
    
    app = build_phase2_graph()
    
    initial_state = {
        "claim": "Microsoft reduced data center energy consumption by 12% in 2024",
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
    
    config = {
        "configurable": {"thread_id": "test_fast_microsoft"},
        "recursion_limit": 50  # FIXED
    }
    
    try:
        print("⏳ Running fast track workflow...")
        result = app.invoke(initial_state, config)
        
        print(f"\n✅ Fast track completed!")
        print(f"Risk Level: {result['risk_level']}")
        print(f"Confidence: {result['confidence']:.2%}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all Phase 2 tests"""
    print("\n" + "="*70)
    print("PHASE 2 VERIFICATION: Agent Collaboration & Debate")
    print("="*70)
    
    results = []
    results.append(("Fast Track", test_fast_track()))
    results.append(("Standard Track", test_standard_track()))
    results.append(("Deep Analysis + Debate", test_debate_mechanism()))
    
    # Summary
    print("\n" + "="*70)
    print("PHASE 2 TEST SUMMARY")
    print("="*70)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n🎉 Phase 2 verification complete! Ready for Phase 3.")
        print("\n📋 NEXT STEPS:")
        print("  1. Review agent outputs for quality")
        print("  2. Check live data fetching")
        print("  3. Proceed to Phase 3 for autonomous tool selection")
    else:
        print("\n⚠️  Some tests failed. Review error messages above.")

if __name__ == "__main__":
    main()
