import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.claim_extractor import ClaimExtractor
from agents.evidence_retriever import EvidenceRetriever
from dotenv import load_dotenv
import json

load_dotenv()

def test_full_pipeline_live():
    """
    Test LIVE data pipeline with real company
    """
    
    print("\n" + "="*80)
    print("🚀 TESTING FULL LIVE DATA PIPELINE")
    print("="*80)
    
    # Initialize agents
    claim_agent = ClaimExtractor()
    evidence_agent = EvidenceRetriever()
    
    # Test with recent Tesla sustainability claim
    company = "Tesla"
    content = """
    Tesla released its 2024 Impact Report in October 2025, claiming significant 
    environmental progress. The company states it has achieved a 45% reduction 
    in water usage at Gigafactory Texas compared to 2022 baseline. Tesla also 
    claims to be on track for net-zero carbon emissions by 2030 across all 
    manufacturing operations. The report highlights ISO 14001 certification 
    received in Q2 2025 for environmental management systems.
    """
    
    # Step 1: Extract claims
    print("\n" + "="*80)
    print("STEP 1: CLAIM EXTRACTION")
    print("="*80)
    claims_result = claim_agent.extract_claims(company, content)
    
    if not claims_result.get("claims"):
        print("❌ No claims extracted. Check Gemini/Groq connection.")
        return
    
    print(f"\n📊 Extracted {len(claims_result['claims'])} claims")
    
    # Step 2: Retrieve LIVE evidence for first claim
    print("\n" + "="*80)
    print("STEP 2: LIVE EVIDENCE RETRIEVAL")
    print("="*80)
    
    first_claim = claims_result["claims"][0]
    evidence_result = evidence_agent.retrieve_evidence(first_claim, company)
    
    # Display results
    print("\n" + "="*80)
    print("📋 EVIDENCE SUMMARY")
    print("="*80)
    
    print(f"\nClaim: {first_claim.get('claim_text')}")
    print(f"\nTotal Evidence Sources: {len(evidence_result['evidence'])}")
    print(f"Quality Metrics:")
    metrics = evidence_result.get('quality_metrics', {})
    print(f"  - Independent sources: {metrics.get('independent_sources')}")
    print(f"  - Avg age: {metrics.get('avg_freshness_days', 0):.1f} days")
    print(f"  - Source diversity: {metrics.get('source_diversity')} types")
    print(f"  - Evidence gap: {'YES ⚠️' if metrics.get('evidence_gap') else 'NO ✓'}")
    
    print(f"\n📰 Sample Evidence Sources:")
    for i, ev in enumerate(evidence_result['evidence'][:5], 1):
        print(f"\n  {i}. {ev.get('source_name')} ({ev.get('source_type')})")
        print(f"     Relationship: {ev.get('relationship_to_claim')}")
        print(f"     Age: {ev.get('data_freshness_days')} days")
        print(f"     URL: {ev.get('url')[:60]}...")
        print(f"     API Source: {ev.get('data_source_api')}")
    
    # Save full results
    output_file = "data/reports/live_test_results.json"
    os.makedirs("data/reports", exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump({
            "claims": claims_result,
            "evidence": evidence_result
        }, f, indent=2)
    
    print(f"\n💾 Full results saved to: {output_file}")
    
    print("\n" + "="*80)
    print("✅ LIVE DATA PIPELINE TEST COMPLETE")
    print("="*80)
    
    return claims_result, evidence_result

if __name__ == "__main__":
    test_full_pipeline_live()
