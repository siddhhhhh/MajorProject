import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.claim_extractor import ClaimExtractor
from agents.evidence_retriever import EvidenceRetriever
from dotenv import load_dotenv
import json

load_dotenv()

def test_enterprise_evidence_retrieval():
    """
    Test ENTERPRISE-GRADE multi-source evidence retrieval
    """
    
    print("\n" + "="*80)
    print("🚀 TESTING ENTERPRISE ESG DATA SOURCES")
    print("="*80)
    
    # Initialize agents
    claim_agent = ClaimExtractor()
    evidence_agent = EvidenceRetriever()
    
    # Test with Tesla
    company = "Tesla"
    content = """
    Tesla released its 2024 Impact Report claiming a 45% reduction in water usage 
    at Gigafactory Texas compared to 2022 baseline. The company states it is on track 
    for net-zero carbon emissions by 2030 across all manufacturing operations.
    """
    
    print("\n" + "="*80)
    print("STEP 1: CLAIM EXTRACTION")
    print("="*80)
    
    claims_result = claim_agent.extract_claims(company, content)
    
    if not claims_result.get("claims"):
        print("❌ No claims extracted")
        return
    
    first_claim = claims_result["claims"][0]
    print(f"\n✅ Testing claim: {first_claim.get('claim_text')}")
    
    print("\n" + "="*80)
    print("STEP 2: ENTERPRISE EVIDENCE RETRIEVAL")
    print("="*80)
    
    evidence_result = evidence_agent.retrieve_evidence(first_claim, company)
    
    # Display results
    print("\n" + "="*80)
    print("📊 ENTERPRISE DATA QUALITY REPORT")
    print("="*80)
    
    metrics = evidence_result.get('quality_metrics', {})
    
    print(f"\n🎯 OVERALL METRICS:")
    print(f"   Total Sources: {metrics.get('total_sources')}")
    print(f"   Independent Sources: {metrics.get('independent_sources')}")
    print(f"   Premium Sources: {metrics.get('premium_sources')}")
    print(f"   Source Diversity: {metrics.get('source_diversity')} types")
    print(f"   Diversity Score: {metrics.get('diversity_score')}/100")
    print(f"   Coverage Score: {metrics.get('coverage_score')}/100")
    print(f"   Avg Freshness: {metrics.get('avg_freshness_days')} days")
    print(f"   Evidence Gap: {'YES ⚠️' if metrics.get('evidence_gap') else 'NO ✓'}")
    
    print(f"\n📊 SOURCE TYPE BREAKDOWN:")
    type_breakdown = metrics.get('source_type_breakdown', {})
    for stype, count in sorted(type_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"   {stype}: {count}")
    
    print(f"\n🌐 API SOURCE BREAKDOWN:")
    api_breakdown = metrics.get('api_source_breakdown', {})
    for api, count in sorted(api_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"   {api}: {count}")
    
    print(f"\n📰 SAMPLE PREMIUM SOURCES:")
    evidence = evidence_result.get('evidence', [])
    premium_sources = [e for e in evidence if e.get('source_type') in [
        'Tier-1 Financial Media', 'Government/Regulatory', 'Academic', 'NGO'
    ]]
    
    for i, source in enumerate(premium_sources[:5], 1):
        print(f"\n   {i}. {source.get('source_name')} ({source.get('source_type')})")
        print(f"      API: {source.get('data_source_api')}")
        print(f"      Relationship: {source.get('relationship_to_claim')}")
        print(f"      Age: {source.get('data_freshness_days')} days")
        print(f"      URL: {source.get('url')[:60]}...")
    
    # Save results
    output_file = "data/reports/enterprise_test_results.json"
    os.makedirs("data/reports", exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump({
            "claim": first_claim,
            "evidence_result": evidence_result
        }, f, indent=2)
    
    print(f"\n💾 Full results saved to: {output_file}")
    
    # Quality assessment
    print("\n" + "="*80)
    print("📋 QUALITY ASSESSMENT")
    print("="*80)
    
    quality_grade = "A+"
    if metrics.get('evidence_gap'):
        quality_grade = "C"
    elif metrics.get('premium_sources', 0) < 3:
        quality_grade = "B"
    elif metrics.get('diversity_score', 0) < 60:
        quality_grade = "B+"
    
    print(f"\n   Overall Quality Grade: {quality_grade}")
    print(f"   Data Freshness: {'Excellent' if metrics.get('avg_freshness_days', 999) < 30 else 'Good' if metrics.get('avg_freshness_days', 999) < 90 else 'Fair'}")
    print(f"   Source Credibility: {'High' if metrics.get('premium_sources', 0) >= 5 else 'Medium' if metrics.get('premium_sources', 0) >= 3 else 'Low'}")
    print(f"   Coverage: {'Comprehensive' if metrics.get('coverage_score', 0) > 50 else 'Moderate' if metrics.get('coverage_score', 0) > 25 else 'Limited'}")
    
    print("\n" + "="*80)
    print("✅ ENTERPRISE TEST COMPLETE")
    print("="*80)
    
    return evidence_result

if __name__ == "__main__":
    # Check API keys
    required = ["GEMINI_API_KEY", "GROQ_API_KEY"]
    recommended = ["NEWS_API_KEY", "NEWSDATA_API_KEY", "FINNHUB_API_KEY"]
    
    print("\n🔑 Checking API Keys...")
    for key in required:
        if os.getenv(key):
            print(f"   ✅ {key}")
        else:
            print(f"   ❌ {key} - REQUIRED")
    
    for key in recommended:
        if os.getenv(key):
            print(f"   ✅ {key}")
        else:
            print(f"   ⚠️  {key} - Recommended for better coverage")
    
    print("\n")
    
    try:
        test_enterprise_evidence_retrieval()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
