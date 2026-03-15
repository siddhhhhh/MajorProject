import json
import re
from typing import Dict, Any, List
from core.llm_client import llm_client
from config.agent_prompts import CLAIM_EXTRACTION_PROMPT

class ClaimExtractor:
    def __init__(self):
        self.name = "Claim Extraction Specialist"
        self.llm = llm_client
    
    def extract_claims(self, company_name: str, content: str) -> Dict[str, Any]:
        """Extract structured ESG claims from content"""
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 1: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company_name}")
        print(f"Content length: {len(content)} chars")
        
        prompt = f"""{CLAIM_EXTRACTION_PROMPT}

COMPANY: {company_name}

CONTENT TO ANALYZE:
{content[:4000]}

Return ONLY valid JSON in the exact format specified. No markdown, no explanations."""

        # Try with fallback - Gemini first, then Groq
        print("⏳ Calling LLM for claim extraction (with fallback)...")
        response = self.llm.call_with_fallback(prompt, use_gemini_first=True)
        
        if not response:
            print("❌ Failed to get response from both LLMs")
            return {
                "company": company_name,
                "error": "All LLMs failed",
                "claims": []
            }
        
        try:
            # Clean response - remove markdown if present
            cleaned_response = self._clean_json_response(response)
            
            # Parse JSON response
            claims_data = json.loads(cleaned_response)
            
            # Validate structure
            if "claims" in claims_data and isinstance(claims_data["claims"], list):
                num_claims = len(claims_data['claims'])
                print(f"✅ Successfully extracted {num_claims} claims")
                
                # Print summary
                for i, claim in enumerate(claims_data['claims'], 1):
                    print(f"  {i}. {claim.get('claim_text', 'N/A')[:80]}...")
                    print(f"     Category: {claim.get('category')}, Specificity: {claim.get('specificity_score')}/10")
                
                return claims_data
            else:
                print("⚠️ Invalid claims structure in response")
                return {"company": company_name, "claims": []}
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            print(f"Response preview: {response[:200]}...")
            # Attempt fallback parsing
            return self._fallback_parsing(response, company_name)
    
    def _clean_json_response(self, text: str) -> str:
        """Remove markdown code blocks and clean JSON"""
        # Remove markdown code blocks
        text = re.sub(r'```\s*', '', text)
        
        # Find JSON object
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start != -1 and end > start:
            return text[start:end]
        
        return text
    
    def _fallback_parsing(self, text: str, company_name: str) -> Dict[str, Any]:
        """Fallback parsing if JSON is malformed"""
        print("🔄 Attempting fallback parsing...")
        
        cleaned = self._clean_json_response(text)
        
        try:
            return json.loads(cleaned)
        except:
            print("❌ Fallback parsing also failed")
            return {
                "company": company_name, 
                "claims": [], 
                "error": "Parsing failed",
                "raw_response": text[:500]
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Return agent status"""
        return {
            "agent_name": self.name,
            "status": "ready",
            "capabilities": ["claim_extraction", "vague_language_detection"]
        }
