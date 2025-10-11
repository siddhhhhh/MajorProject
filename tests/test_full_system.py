import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import quick_analysis
from dotenv import load_dotenv

load_dotenv()

def test_full_7_agent_system():
    """
    Test complete 7-agent system with real company
    """
    
    print("\n" + "="*80)
    print("🚀 TESTING COMPLETE 7-AGENT ESG SYSTEM")
    print("="*80)
    
    # Test cases
    test_cases = [
        {
            "company": "Tesla",
            "content": "Tesla achieves 45% water reduction at Gigafactory Texas and commits to net-zero emissions by 2030."
        },
        {
            "company": "BP",
            "content": "BP commits to net zero by 2050 and is transitioning to renewable energy."
        }
    ]
    
    for test in test_cases:
        print(f"\n{'='*80}")
        print(f"Testing: {test['company']}")
        print(f"{'='*80}")
        
        try:
            results = quick_analysis(test["company"], test["content"])
            
            # Quick summary
            assessment = results.get("final_risk_assessment", {})
            print(f"\n✅ Analysis Complete:")
            print(f"   ESG Score: {assessment.get('esg_score')}/100")
            print(f"   Rating: {assessment.get('rating_grade')}")
            print(f"   Risk Level: {assessment.get('risk_level')}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_full_7_agent_system()
