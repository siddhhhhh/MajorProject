import json
from typing import Dict, Any, List
from core.llm_client import llm_client
from config.agent_prompts import CONTRADICTION_ANALYSIS_PROMPT

class ContradictionAnalyzer:
    def __init__(self):
        self.name = "Contradiction & Verification Analyst"
        self.llm = llm_client
    
    def analyze_claim(self, claim: Dict[str, Any], evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze claim against evidence to detect contradictions
        """
        
        claim_id = claim.get("claim_id")
        claim_text = claim.get("claim_text", "")
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 3: {self.name}")
        print(f"{'='*60}")
        print(f"Claim ID: {claim_id}")
        print(f"Claim: {claim_text[:100]}...")
        print(f"Evidence items: {len(evidence)}")
        
        # Categorize evidence by relationship
        supporting = [e for e in evidence if e.get('relationship_to_claim') == 'Supports']
        contradicting = [e for e in evidence if e.get('relationship_to_claim') == 'Contradicts']
        neutral = [e for e in evidence if e.get('relationship_to_claim') == 'Neutral']
        
        print(f"\n📊 Evidence breakdown:")
        print(f"   Supporting: {len(supporting)}")
        print(f"   Contradicting: {len(contradicting)}")
        print(f"   Neutral: {len(neutral)}")
        
        # Prepare evidence summary for LLM
        evidence_summary = self._prepare_evidence_summary(evidence)
        
        # Use Gemini for complex reasoning
        prompt = CONTRADICTION_ANALYSIS_PROMPT.format(
            claim=claim_text,
            evidence=evidence_summary,
            claim_id=claim_id
        )
        
        print(f"\n⏳ Running deep contradiction analysis...")
        response = self.llm.call_gemini(prompt, temperature=0.1, use_pro=True)
        
        if not response:
            print("❌ LLM analysis failed, using fallback")
            return self._fallback_analysis(claim, evidence, supporting, contradicting)
        
        try:
            # Clean and parse JSON
            cleaned = self._clean_json_response(response)
            analysis = json.loads(cleaned)
            
            # Add computed metrics
            analysis['evidence_counts'] = {
                'supporting': len(supporting),
                'contradicting': len(contradicting),
                'neutral': len(neutral)
            }
            
            print(f"\n✅ Analysis complete:")
            print(f"   Verdict: {analysis.get('overall_verdict')}")
            print(f"   Confidence: {analysis.get('verification_confidence')}%")
            print(f"   Contradictions found: {len(analysis.get('specific_contradictions', []))}")
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            return self._fallback_analysis(claim, evidence, supporting, contradicting)
    
    def _prepare_evidence_summary(self, evidence: List[Dict]) -> str:
        """Prepare concise evidence summary for LLM"""
        summary_parts = []
        
        # Group by source type for better analysis
        by_type = {}
        for ev in evidence[:20]:  # Limit to top 20
            source_type = ev.get('source_type', 'Unknown')
            if source_type not in by_type:
                by_type[source_type] = []
            by_type[source_type].append(ev)
        
        for source_type, items in by_type.items():
            summary_parts.append(f"\n{source_type} Sources:")
            for ev in items[:5]:  # Top 5 per type
                summary_parts.append(
                    f"- {ev.get('source_name')}: {ev.get('relevant_text')[:200]}"
                )
        
        return "\n".join(summary_parts)
    
    def _clean_json_response(self, text: str) -> str:
        """Remove markdown and extract JSON"""
        import re
        text = re.sub(r'```\s*', '', text)
        
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start != -1 and end > start:
            return text[start:end]
        return text
    
    def _fallback_analysis(self, claim: Dict, evidence: List[Dict], 
                          supporting: List, contradicting: List) -> Dict[str, Any]:
        """Simple rule-based analysis if LLM fails"""
        
        total = len(evidence)
        support_ratio = len(supporting) / total if total > 0 else 0
        contradict_ratio = len(contradicting) / total if total > 0 else 0
        
        if contradict_ratio > 0.3:
            verdict = "Contradicted"
            confidence = 70
        elif support_ratio > 0.5:
            verdict = "Verified"
            confidence = 60
        elif total < 3:
            verdict = "Unverifiable"
            confidence = 30
        else:
            verdict = "Partially True"
            confidence = 50
        
        return {
            "claim_id": claim.get("claim_id"),
            "overall_verdict": verdict,
            "verification_confidence": confidence,
            "specific_contradictions": [],
            "supportive_evidence": [e.get('source_name') for e in supporting[:3]],
            "key_issues": ["Automated fallback analysis - LLM unavailable"],
            "evidence_counts": {
                'supporting': len(supporting),
                'contradicting': len(contradicting),
                'neutral': len(evidence) - len(supporting) - len(contradicting)
            }
        }
