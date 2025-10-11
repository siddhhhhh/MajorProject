import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.contradiction_analyzer import ContradictionAnalyzer
from agents.credibility_analyst import CredibilityAnalyst
import json

def test_with_existing_data():
    """
    Test Agents 3 & 4 using already retrieved data
    Much faster for testing
    """
    
    print("\n" + "="*80)
    print("🚀 QUICK TEST: AGENTS 3 & 4 WITH EXISTING DATA")
    print("="*80)
    
    # Load previously retrieved data
    data_file = "data/reports/live_test_results.json"
    
    if not os.path.exists(data_file):
        print(f"❌ Data file not found: {data_file}")
        print("Run test_live_data.py first to generate data")
        return
    
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    first_claim = data['claims']['claims'][0]
    evidence_list = data['evidence']['evidence']
    
    print(f"\n📋 Loaded existing data:")
    print(f"   Claim: {first_claim.get('claim_text')[:80]}...")
    print(f"   Evidence sources: {len(evidence_list)}")
    
    # Initialize agents
    contradiction_agent = ContradictionAnalyzer()
    credibility_agent = CredibilityAnalyst()
    
    # Test Agent 3
    print("\n" + "="*80)
    print("TESTING AGENT 3: CONTRADICTION ANALYSIS")
    print("="*80)
    
    contradiction_result = contradiction_agent.analyze_claim(first_claim, evidence_list)
    
    print("\n📊 RESULTS:")
    print(f"   Verdict: {contradiction_result.get('overall_verdict')}")
    print(f"   Confidence: {contradiction_result.get('verification_confidence')}%")
    
    contradictions = contradiction_result.get('specific_contradictions', [])
    print(f"   Contradictions found: {len(contradictions)}")
    
    # Test Agent 4
    print("\n" + "="*80)
    print("TESTING AGENT 4: CREDIBILITY ANALYSIS")
    print("="*80)
    
    credibility_result = credibility_agent.analyze_sources(evidence_list)
    
    metrics = credibility_result.get('aggregate_metrics', {})
    print("\n📊 RESULTS:")
    print(f"   Average credibility: {metrics.get('average_credibility', 0):.2f}/1.0")
    print(f"   High credibility sources: {metrics.get('high_credibility_count')}")
    print(f"   Low credibility sources: {metrics.get('low_credibility_count')}")
    
    # Save results
    output_file = "data/reports/quick_test_agents_3_4.json"
    with open(output_file, 'w') as f:
        json.dump({
            "contradiction_analysis": contradiction_result,
            "credibility_analysis": credibility_result
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    print("\n" + "="*80)
    print("✅ QUICK TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    test_with_existing_data()
