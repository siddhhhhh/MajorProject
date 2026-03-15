"""
Evidence Conflict Resolution Agent
Handles contradictory evidence from multiple sources
"""

from typing import Dict, Any, List
from core.llm_client import llm_client
import json

class ConflictResolver:
    def __init__(self):
        self.name = "Evidence Conflict Resolver"
        self.llm = llm_client
    
    def resolve_conflicts(self, claim: Dict, evidence: List[Dict]) -> Dict[str, Any]:
        """
        Identify and resolve conflicts in evidence
        Uses credibility weighting and temporal analysis
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 11: {self.name}")
        print(f"{'='*60}")
        print(f"Analyzing Claim {claim.get('claim_id')}")
        
        # Categorize evidence
        supporting = [e for e in evidence if e.get('relationship_to_claim') == 'Supports']
        contradicting = [e for e in evidence if e.get('relationship_to_claim') == 'Contradicts']
        neutral = [e for e in evidence if e.get('relationship_to_claim') in ['Neutral', 'Partial']]
        
        print(f"\n📊 Evidence Distribution:")
        print(f"   Supporting: {len(supporting)}")
        print(f"   Contradicting: {len(contradicting)}")
        print(f"   Neutral/Partial: {len(neutral)}")
        
        conflicts = []
        
        # Detect conflicts
        if supporting and contradicting:
            print(f"\n⚠️ CONFLICT DETECTED: Evidence disagrees")
            
            conflict = self._analyze_conflict(supporting, contradicting, claim)
            conflicts.append(conflict)
        
        # Resolve using ensemble voting
        resolution = self._ensemble_resolution(supporting, contradicting, neutral)
        
        result = {
            "claim_id": claim.get('claim_id'),
            "conflicts_detected": len(conflicts) > 0,
            "conflicts": conflicts,
            "resolution": resolution,
            "requires_human_review": len(conflicts) > 0 and resolution['confidence'] < 70
        }
        
        print(f"\n✅ Conflict analysis complete")
        if result['requires_human_review']:
            print(f"   ⚠️ HUMAN REVIEW RECOMMENDED")
        
        return result
    
    def _analyze_conflict(self, supporting: List, contradicting: List, claim: Dict) -> Dict:
        """Analyze specific conflict"""
        
        # Calculate weighted credibility
        support_credibility = self._calculate_weighted_credibility(supporting)
        contradict_credibility = self._calculate_weighted_credibility(contradicting)
        
        # Check temporal factors
        support_recency = self._calculate_avg_recency(supporting)
        contradict_recency = self._calculate_avg_recency(contradicting)
        
        # Use LLM for deep analysis
        prompt = f"""Analyze this evidence conflict for the claim:
CLAIM: {claim.get('claim_text')}

SUPPORTING EVIDENCE ({len(supporting)} sources, avg credibility: {support_credibility:.2f}):
{self._summarize_evidence(supporting[:3])}

CONTRADICTING EVIDENCE ({len(contradicting)} sources, avg credibility: {contradict_credibility:.2f}):
{self._summarize_evidence(contradicting[:3])}

Which evidence is more reliable? Consider:
1. Source credibility
2. Data recency (supporting: {support_recency:.0f} days old, contradicting: {contradict_recency:.0f} days old)
3. Specificity

Return JSON: {{"more_reliable": "supporting|contradicting", "reason": "brief explanation", "confidence": 0-100}}"""

        response = self.llm.call_groq([{"role": "user", "content": prompt}], use_fast=True)
        
        llm_analysis = self._parse_llm_response(response)
        
        return {
            "type": "Evidence Disagreement",
            "supporting_sources": len(supporting),
            "contradicting_sources": len(contradicting),
            "support_credibility": support_credibility,
            "contradict_credibility": contradict_credibility,
            "support_recency_days": support_recency,
            "contradict_recency_days": contradict_recency,
            "llm_resolution": llm_analysis
        }
    
    def _ensemble_resolution(self, supporting: List, contradicting: List, neutral: List) -> Dict:
        """Ensemble voting resolution"""
        
        total = len(supporting) + len(contradicting) + len(neutral)
        
        if total == 0:
            return {"verdict": "Insufficient Evidence", "confidence": 0}
        
        # Weight by credibility
        support_weight = sum(self._get_credibility_score(e.get('source_type', '')) for e in supporting)
        contradict_weight = sum(self._get_credibility_score(e.get('source_type', '')) for e in contradicting)
        
        if support_weight > contradict_weight * 1.5:
            verdict = "Likely True"
            confidence = min(95, int((support_weight / (support_weight + contradict_weight)) * 100))
        elif contradict_weight > support_weight * 1.5:
            verdict = "Likely False"
            confidence = min(95, int((contradict_weight / (support_weight + contradict_weight)) * 100))
        else:
            verdict = "Conflicting Evidence - Uncertain"
            confidence = 40
        
        return {
            "verdict": verdict,
            "confidence": confidence,
            "method": "Credibility-Weighted Ensemble Voting"
        }
    
    def _calculate_weighted_credibility(self, evidence: List) -> float:
        """Calculate average weighted credibility"""
        if not evidence:
            return 0.0
        
        scores = [self._get_credibility_score(e.get('source_type', '')) for e in evidence]
        return sum(scores) / len(scores) if scores else 0.0
    
    def _calculate_avg_recency(self, evidence: List) -> float:
        """Calculate average age of evidence"""
        ages = [e.get('data_freshness_days', 365) for e in evidence]
        return sum(ages) / len(ages) if ages else 365
    
    def _get_credibility_score(self, source_type: str) -> float:
        """Get credibility score for source type"""
        scores = {
            "Academic": 1.0,
            "Government/Regulatory": 0.95,
            "NGO": 0.90,
            "Tier-1 Financial Media": 0.85,
            "General Media": 0.70,
            "ESG Platform": 0.75,
            "Web Source": 0.50,
            "Company-Controlled": 0.30
        }
        return scores.get(source_type, 0.50)
    
    def _summarize_evidence(self, evidence: List) -> str:
        """Create brief summary of evidence"""
        summaries = []
        for e in evidence:
            summaries.append(f"- {e.get('source_name')}: {e.get('relevant_text', '')[:100]}...")
        return "\n".join(summaries)
    def _parse_llm_response(self, response: str) -> Dict:
        """Parse LLM JSON response - ROBUST parsing"""
        
        if not response:
            return {"more_reliable": "unknown", "reason": "No response", "confidence": 0}
        
        try:
            # Try 1: Direct JSON parse
            try:
                return json.loads(response)
            except:
                pass
            
            # Try 2: Remove markdown code blocks
            import re
            cleaned = response
            cleaned = re.sub(r'```\s*', '', cleaned)
            
            # Try 3: Extract JSON object
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = cleaned[start:end]
                return json.loads(json_str)
            
            # Try 4: Extract from explanation text using regex
            more_reliable_match = re.search(r'"more_reliable":\s*"(supporting|contradicting)"', response)
            confidence_match = re.search(r'"confidence":\s*(\d+)', response)
            reason_match = re.search(r'"reason":\s*"([^"]+)"', response)
            
            if more_reliable_match:
                return {
                    "more_reliable": more_reliable_match.group(1),
                    "reason": reason_match.group(1) if reason_match else "Extracted from text",
                    "confidence": int(confidence_match.group(1)) if confidence_match else 50
                }
        
        except Exception as e:
            print(f"      ⚠️ LLM parse error: {str(e)[:50]}")
        
        # Fallback: Use ensemble voting only
        return {
            "more_reliable": "ensemble_voting_used", 
            "reason": "LLM parsing failed - using credibility-weighted voting", 
            "confidence": 75
        }

