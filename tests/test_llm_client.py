import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.llm_client import llm_client
from dotenv import load_dotenv

load_dotenv()

def test_llm_clients():
    """Test both LLM clients"""
    
    print("\n" + "="*80)
    print("TESTING LLM CLIENTS")
    print("="*80)
    
    # Test prompt
    test_prompt = "List 3 ESG categories in JSON format: {categories: [...]}"
    
    # Test 1: Groq
    print("\n1. Testing Groq...")
    groq_response = llm_client.call_groq([{"role": "user", "content": test_prompt}])
    print(f"Groq Response: {groq_response}")
    
    # Test 2: Gemini
    print("\n2. Testing Gemini...")
    gemini_response = llm_client.call_gemini(test_prompt)
    print(f"Gemini Response: {gemini_response}")
    
    # Test 3: Fallback
    print("\n3. Testing Fallback (Gemini → Groq)...")
    fallback_response = llm_client.call_with_fallback(test_prompt, use_gemini_first=True)
    print(f"Fallback Response: {fallback_response}")
    
    print("\n" + "="*80)
    print("✅ LLM CLIENT TESTS COMPLETED")
    print("="*80)

if __name__ == "__main__":
    test_llm_clients()
