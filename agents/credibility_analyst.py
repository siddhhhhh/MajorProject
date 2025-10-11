import json
from typing import Dict, Any, List
from core.llm_client import llm_client
from config.agent_prompts import SOURCE_CREDIBILITY_PROMPT

class CredibilityAnalyst:
    def __init__(self):
        self.name = "Source Credibility & Bias Analyst"
        self.llm = llm_client
        
        # Base credibility scores by source type
        self.base_scores = {
            "Academic": 1.0,
            "Government/Regulatory": 0.95,
            "NGO": 0.90,
            "Tier-1 Financial Media": 0.85,
            "General Media": 0.70,
            "ESG Platform": 0.75,
            "Web Source": 0.50,
            "Company-Controlled": 0.35,
            "Sponsored Content": 0.20
        }
    
    def analyze_sources(self, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze credibility and bias of all evidence sources
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 4: {self.name}")
        print(f"{'='*60}")
        print(f"Analyzing {len(evidence)} sources...")
        
        source_analyses = []
        credibility_scores = []
        
        for i, ev in enumerate(evidence, 1):
            print(f"\r   Processing source {i}/{len(evidence)}...", end="", flush=True)
            
            analysis = self._analyze_single_source(ev)
            source_analyses.append(analysis)
            credibility_scores.append(analysis['final_credibility_score'])
        
        print(f"\n\n✅ Credibility analysis complete")
        
        # Calculate aggregate metrics
        avg_credibility = sum(credibility_scores) / len(credibility_scores) if credibility_scores else 0
        
        # Count by credibility tier
        high_credibility = sum(1 for s in credibility_scores if s >= 0.8)
        medium_credibility = sum(1 for s in credibility_scores if 0.5 <= s < 0.8)
        low_credibility = sum(1 for s in credibility_scores if s < 0.5)
        
        print(f"   Average credibility: {avg_credibility:.2f}")
        print(f"   High (≥0.8): {high_credibility} sources")
        print(f"   Medium (0.5-0.8): {medium_credibility} sources")
        print(f"   Low (<0.5): {low_credibility} sources")
        
        return {
            "source_credibility_analyses": source_analyses,
            "aggregate_metrics": {
                "average_credibility": avg_credibility,
                "high_credibility_count": high_credibility,
                "medium_credibility_count": medium_credibility,
                "low_credibility_count": low_credibility,
                "total_sources": len(evidence)
            }
        }
    
    def _analyze_single_source(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single source for credibility and bias"""
        
        source_type = evidence.get('source_type', 'Web Source')
        source_name = evidence.get('source_name', 'Unknown')
        url = evidence.get('url', '')
        content = evidence.get('relevant_text', '')
        
        # Get base credibility
        base_credibility = self.base_scores.get(source_type, 0.50)
        
        # Apply adjustments
        adjustments = []
        final_score = base_credibility
        
        # Freshness bonus
        freshness = evidence.get('data_freshness_days', 999)
        if freshness < 180:  # Less than 6 months
            adjustments.append("+0.05 (recent)")
            final_score += 0.05
        elif freshness > 1095:  # More than 3 years
            adjustments.append("-0.10 (outdated)")
            final_score -= 0.10
        
        # Detect paid content
        paid_content = self._detect_paid_content(content, source_name)
        if paid_content:
            adjustments.append("-0.20 (sponsored)")
            final_score -= 0.20
        
        # Company-controlled penalty
        if source_type == "Company-Controlled" or "tesla.com" in url.lower():
            adjustments.append("-0.15 (company source)")
            final_score -= 0.15
        
        # Regulatory/Academic bonus
        if source_type in ["Government/Regulatory", "Academic"]:
            if any(term in content.lower() for term in ["study", "research", "analysis", "data"]):
                adjustments.append("+0.05 (primary data)")
                final_score += 0.05
        
        # Cap between 0 and 1
        final_score = max(0.0, min(1.0, final_score))
        
        # Detect bias
        bias_direction = self._detect_bias(content, source_type)
        
        return {
            "source_id": evidence.get('source_id'),
            "source_name": source_name,
            "source_type": source_type,
            "base_credibility": base_credibility,
            "adjustments": adjustments,
            "final_credibility_score": round(final_score, 2),
            "paid_content_detected": paid_content,
            "bias_direction": bias_direction,
            "url": url
        }
    
    def _detect_paid_content(self, content: str, source_name: str) -> bool:
        """Detect if content is sponsored/paid"""
        indicators = [
            "sponsored", "advertorial", "paid promotion", "partner content",
            "in partnership with", "brought to you by"
        ]
        
        text = (content + " " + source_name).lower()
        return any(indicator in text for indicator in indicators)
    
    def _detect_bias(self, content: str, source_type: str) -> str:
        """Simple bias detection"""
        if not content:
            return "Neutral"
        
        content_lower = content.lower()
        
        # Pro-company indicators
        pro_indicators = ["revolutionary", "groundbreaking", "leader", "best", "innovative"]
        pro_count = sum(1 for ind in pro_indicators if ind in content_lower)
        
        # Critical indicators
        critical_indicators = ["violation", "accused", "greenwashing", "overstated", "failed"]
        critical_count = sum(1 for ind in critical_indicators if ind in content_lower)
        
        if pro_count > critical_count + 2:
            return "Pro-company"
        elif critical_count > pro_count + 2:
            return "Anti-company"
        else:
            return "Neutral"
