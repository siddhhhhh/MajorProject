import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.claim_extractor import ClaimExtractor
from dotenv import load_dotenv

load_dotenv()

def test_claim_extraction():
    """Test Agent 1: Claim Extraction"""
    
    # Initialize agent
    agent = ClaimExtractor()
    
    # Test case 1: Clear quantified claims
    test_content_1 = """
    Tesla announces ambitious sustainability goals for 2024. The company claims to have achieved 
    a 40% reduction in water usage at its Gigafactory Nevada compared to 2020 levels. 
    CEO Elon Musk stated that Tesla will reach net-zero carbon emissions by 2030 across 
    all manufacturing facilities. The company also received ISO 14001 certification for 
    environmental management systems in Q1 2024.
    
    Additionally, Tesla claims to be the world's most sustainable automaker, using 100% 
    renewable energy in its European operations.
    """
    
    print("\n" + "="*80)
    print("TEST 1: Clear Quantified Claims (Tesla)")
    print("="*80)
    
    result1 = agent.extract_claims("Tesla", test_content_1)
    
    print(f"\nResult: {json.dumps(result1, indent=2)}")
    
    # Test case 2: Vague claims (greenwashing red flags)
    test_content_2 = """
    EcoFresh Products is committed to sustainability and environmental protection. 
    Our products are eco-friendly and made with green materials. We care deeply about 
    the planet and future generations. Our sustainable practices make us a leader in 
    the industry. We are continuously working towards a greener tomorrow.
    """
    
    print("\n" + "="*80)
    print("TEST 2: Vague Claims - Greenwashing Indicators")
    print("="*80)
    
    result2 = agent.extract_claims("EcoFresh Products", test_content_2)
    
    print(f"\nResult: {json.dumps(result2, indent=2)}")
    
    # Test case 3: Mixed claims
    test_content_3 = """
    Unilever published its 2024 sustainability report showing significant progress. 
    The company reduced plastic packaging by 25% since 2020 and aims to make all 
    packaging recyclable by 2025. However, Unilever also claims to be "nature positive" 
    and "the most sustainable consumer goods company" without providing specific metrics. 
    The company was awarded a B Corp certification in 2023.
    """
    
    print("\n" + "="*80)
    print("TEST 3: Mixed Claims (Specific + Vague)")
    print("="*80)
    
    result3 = agent.extract_claims("Unilever", test_content_3)
    
    print(f"\nResult: {json.dumps(result3, indent=2)}")
    
    return result1, result2, result3

if __name__ == "__main__":
    import json
    
    # Check environment variables
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ ERROR: GEMINI_API_KEY not found in environment!")
        print("Please add it to your .env file")
        sys.exit(1)
    
    print("\n🚀 Starting Claim Extraction Tests...")
    
    try:
        results = test_claim_extraction()
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED")
        print("="*80)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
