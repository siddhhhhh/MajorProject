"""
Quick fix script to test AutoGen availability
"""

import sys
import os

print("\n" + "="*80)
print("🔧 AutoGen Diagnosis & Fix Script")
print("="*80)

# Test 1: Check if AutoGen is installed
print("\n1. Checking AutoGen installation...")
try:
    import autogen
    print(f"   ✅ AutoGen installed: version {autogen.__version__}")
except ImportError as e:
    print(f"   ❌ AutoGen NOT installed: {e}")
    print("\n   🔧 FIX: Run these commands:")
    print("      pip install pyautogen")
    print("      pip install openai")
    sys.exit(1)

# Test 2: Check OpenAI library
print("\n2. Checking OpenAI library...")
try:
    import openai
    print(f"   ✅ OpenAI installed: version {openai.__version__}")
except ImportError:
    print("   ❌ OpenAI NOT installed")
    print("\n   🔧 FIX: Run: pip install openai")
    sys.exit(1)

# Test 3: Check environment variables
print("\n3. Checking environment variables...")
from dotenv import load_dotenv
load_dotenv()

groq_key = os.getenv("GROQ_API_KEY")
if groq_key:
    print(f"   ✅ GROQ_API_KEY found: {groq_key[:10]}...")
else:
    print("   ❌ GROQ_API_KEY not found")

use_autogen = os.getenv("USE_AUTOGEN", "false")
print(f"   📝 USE_AUTOGEN = {use_autogen}")

# Test 4: Try to create AutoGen agent
print("\n4. Testing AutoGen agent creation...")
try:
    llm_config = {
        "config_list": [{
            "model": "llama-3.3-70b-versatile",
            "api_key": groq_key,
            "base_url": "https://api.groq.com/openai/v1",
            "api_type": "openai"
        }],
        "temperature": 0.1,
        "timeout": 60
    }
    
    test_agent = autogen.AssistantAgent(
        name="TestAgent",
        system_message="Test agent",
        llm_config=llm_config
    )
    
    print("   ✅ AutoGen agent created successfully")
    print(f"   Agent name: {test_agent.name}")
    
except Exception as e:
    print(f"   ❌ Failed to create AutoGen agent: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Try to import our orchestrator
print("\n5. Testing custom orchestrator import...")
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.hybrid_orchestrator import hybrid_orchestrator
    
    if hybrid_orchestrator is not None:
        print("   ✅ Hybrid orchestrator loaded successfully")
    else:
        print("   ⚠️ Orchestrator imported but is None")
        
except Exception as e:
    print(f"   ❌ Failed to import orchestrator: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("✅ DIAGNOSIS COMPLETE")
print("="*80)
print("\nIf all checks passed, AutoGen should work!")
print("If any failed, follow the fix instructions above.\n")
