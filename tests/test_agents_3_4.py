import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.claim_extractor import ClaimExtractor
from agents.evidence_retriever import EvidenceRetriever
from agents.contradiction_analyzer import ContradictionAnalyzer
from agents.credibility_analyst import CredibilityAnalyst
from dotenv import load_dotenv
import json

load_dotenv()

def test_agents_3_and_4():
    """
    Test Agent 3 (Contradiction Analysis) and Agent 4 (Credibility Analysis)
    Using real Tesla data from previous test
    """
    
    print("\n" + "="*80)
    print("🚀 TESTING AGENTS 3 & 4: CONTRADICTION & CREDIBILITY ANALYSIS")
    print("="*80)
    
    # Initialize all agents
    claim_agent = ClaimExtractor()
    evidence_agent = EvidenceRetriever()
    contradiction_agent = ContradictionAnalyzer()
    credibility_agent = CredibilityAnalyst()
    
    # Test with Tesla water usage claim
    company = "Tesla"
    content = """
    Tesla released its 2024 Impact Report in October 2025, claiming significant 
    environmental progress. The company states it has achieved a 45% reduction 
    in water usage at Gigafactory Texas compared to 2022 baseline. Tesla also 
    claims to be on track for net-zero carbon emissions by 2030 across all 
    manufacturing operations.
    """
    
    # Step 1: Extract claims
    print("\n" + "="*80)
    print("STEP 1: CLAIM EXTRACTION (Agent 1)")
    print("="*80)
    claims_result = claim_agent.extract_claims(company, content)
    
    if not claims_result.get("claims"):
        print("❌ No claims extracted. Stopping test.")
        return
    
    print(f"\n✅ Extracted {len(claims_result['claims'])} claims")
    
    # Step 2: Retrieve evidence
    print("\n" + "="*80)
    print("STEP 2: EVIDENCE RETRIEVAL (Agent 2)")
    print("="*80)
    
    first_claim = claims_result["claims"][0]
    print(f"\nAnalyzing claim: {first_claim.get('claim_text')}")
    
    evidence_result = evidence_agent.retrieve_evidence(first_claim, company)
    evidence_list = evidence_result.get('evidence', [])
    
    print(f"\n✅ Retrieved {len(evidence_list)} evidence sources")
    
    # Step 3: Contradiction Analysis
    print("\n" + "="*80)
    print("STEP 3: CONTRADICTION ANALYSIS (Agent 3)")
    print("="*80)
    
    contradiction_result = contradiction_agent.analyze_claim(first_claim, evidence_list)
    
    print("\n📊 CONTRADICTION ANALYSIS RESULTS:")
    print("="*60)
    print(f"Overall Verdict: {contradiction_result.get('overall_verdict')}")
    print(f"Confidence Level: {contradiction_result.get('verification_confidence')}%")
    
    evidence_counts = contradiction_result.get('evidence_counts', {})
    print(f"\nEvidence Breakdown:")
    print(f"  ✅ Supporting: {evidence_counts.get('supporting')}")
    print(f"  ❌ Contradicting: {evidence_counts.get('contradicting')}")
    print(f"  ⚪ Neutral: {evidence_counts.get('neutral')}")
    
    contradictions = contradiction_result.get('specific_contradictions', [])
    if contradictions:
        print(f"\n⚠️ CONTRADICTIONS DETECTED ({len(contradictions)}):")
        for i, c in enumerate(contradictions[:3], 1):
            print(f"\n  {i}. {c.get('aspect', 'N/A')}")
            print(f"     Claim says: {c.get('claim_states', 'N/A')}")
            print(f"     Evidence shows: {c.get('evidence_shows', 'N/A')}")
            print(f"     Severity: {c.get('severity', 'N/A')}")
    
    supportive = contradiction_result.get('supportive_evidence', [])
    if supportive:
        print(f"\n✅ SUPPORTIVE EVIDENCE ({len(supportive)}):")
        for item in supportive[:3]:
            print(f"  - {item}")
    
    key_issues = contradiction_result.get('key_issues', [])
    if key_issues:
        print(f"\n🔍 KEY ISSUES IDENTIFIED:")
        for issue in key_issues:
            print(f"  - {issue}")
    
    # Step 4: Credibility Analysis
    print("\n" + "="*80)
    print("STEP 4: CREDIBILITY ANALYSIS (Agent 4)")
    print("="*80)
    
    credibility_result = credibility_agent.analyze_sources(evidence_list)
    
    print("\n📊 CREDIBILITY ANALYSIS RESULTS:")
    print("="*60)
    
    metrics = credibility_result.get('aggregate_metrics', {})
    print(f"Average Credibility Score: {metrics.get('average_credibility', 0):.2f}/1.0")
    print(f"\nSource Quality Distribution:")
    print(f"  🟢 High Credibility (≥0.8): {metrics.get('high_credibility_count')} sources")
    print(f"  🟡 Medium Credibility (0.5-0.8): {metrics.get('medium_credibility_count')} sources")
    print(f"  🔴 Low Credibility (<0.5): {metrics.get('low_credibility_count')} sources")
    
    # Show top credible sources
    source_analyses = credibility_result.get('source_credibility_analyses', [])
    sorted_sources = sorted(source_analyses, 
                           key=lambda x: x.get('final_credibility_score', 0), 
                           reverse=True)
    
    print(f"\n🏆 TOP 5 MOST CREDIBLE SOURCES:")
    for i, source in enumerate(sorted_sources[:5], 1):
        print(f"\n  {i}. {source.get('source_name')} ({source.get('source_type')})")
        print(f"     Credibility: {source.get('final_credibility_score'):.2f}/1.0")
        print(f"     Adjustments: {', '.join(source.get('adjustments', []))}")
        print(f"     Bias: {source.get('bias_direction')}")
        print(f"     Paid Content: {'Yes ⚠️' if source.get('paid_content_detected') else 'No ✓'}")
    
    print(f"\n⚠️ BOTTOM 3 LEAST CREDIBLE SOURCES:")
    for i, source in enumerate(sorted_sources[-3:], 1):
        print(f"\n  {i}. {source.get('source_name')} ({source.get('source_type')})")
        print(f"     Credibility: {source.get('final_credibility_score'):.2f}/1.0")
        print(f"     Adjustments: {', '.join(source.get('adjustments', []))}")
    
    # Detect bias patterns
    bias_counts = {}
    for source in source_analyses:
        bias = source.get('bias_direction', 'Neutral')
        bias_counts[bias] = bias_counts.get(bias, 0) + 1
    
    print(f"\n📊 BIAS DISTRIBUTION:")
    for bias_type, count in sorted(bias_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(source_analyses)) * 100
        print(f"  {bias_type}: {count} sources ({percentage:.1f}%)")
    
    # Save complete results
    output_file = "data/reports/agents_3_4_test_results.json"
    os.makedirs("data/reports", exist_ok=True)
    
    complete_results = {
        "claim": first_claim,
        "evidence_summary": {
            "total_sources": len(evidence_list),
            "quality_metrics": evidence_result.get('quality_metrics')
        },
        "contradiction_analysis": contradiction_result,
        "credibility_analysis": credibility_result
    }
    
    with open(output_file, 'w') as f:
        json.dump(complete_results, f, indent=2)
    
    print(f"\n💾 Complete results saved to: {output_file}")
    
    # Final Summary
    print("\n" + "="*80)
    print("📋 EXECUTIVE SUMMARY")
    print("="*80)
    
    verdict = contradiction_result.get('overall_verdict')
    confidence = contradiction_result.get('verification_confidence')
    avg_cred = metrics.get('average_credibility', 0)
    
    print(f"\nClaim: {first_claim.get('claim_text')[:80]}...")
    print(f"\nVerification Status: {verdict} (Confidence: {confidence}%)")
    print(f"Average Source Credibility: {avg_cred:.2f}/1.0")
    
    # Risk assessment
    risk_factors = []
    if contradiction_result.get('specific_contradictions'):
        risk_factors.append("⚠️ Contradictions detected in evidence")
    if evidence_counts.get('contradicting', 0) > evidence_counts.get('supporting', 0):
        risk_factors.append("⚠️ More contradicting than supporting evidence")
    if avg_cred < 0.6:
        risk_factors.append("⚠️ Low average source credibility")
    if metrics.get('low_credibility_count', 0) > metrics.get('high_credibility_count', 0):
        risk_factors.append("⚠️ More low-credibility than high-credibility sources")
    
    if risk_factors:
        print(f"\n🚨 RISK FACTORS IDENTIFIED:")
        for factor in risk_factors:
            print(f"  {factor}")
    else:
        print(f"\n✅ No major risk factors detected")
    
    print("\n" + "="*80)
    print("✅ AGENTS 3 & 4 TEST COMPLETE")
    print("="*80)
    
    return complete_results

if __name__ == "__main__":
    try:
        results = test_agents_3_and_4()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
