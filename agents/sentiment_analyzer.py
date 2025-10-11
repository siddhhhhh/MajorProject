import json
from typing import Dict, Any, List
from textblob import TextBlob
import re
from core.llm_client import llm_client
from config.agent_prompts import SENTIMENT_ANALYSIS_PROMPT

class SentimentAnalyzer:
    def __init__(self):
        self.name = "Sentiment & Linguistic Analysis Expert"
        self.llm = llm_client
        
        # Greenwashing buzzwords
        self.buzzwords = [
            "sustainable", "green", "eco-friendly", "carbon neutral", "net zero",
            "climate positive", "100% renewable", "zero waste", "planet-friendly",
            "environmentally friendly", "clean energy", "carbon negative"
        ]
        
        self.vague_quantifiers = [
            "significant", "substantial", "considerable", "major", "leading",
            "groundbreaking", "revolutionary", "world-class", "best-in-class"
        ]
        
        self.hedge_words = [
            "might", "could", "may", "possibly", "potentially", "approximately",
            "around", "roughly", "about", "nearly", "almost", "up to"
        ]
    
    def analyze_claim_language(self, claim: Dict[str, Any], evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze linguistic patterns in claim vs evidence
        Detect greenwashing language tactics
        """
        
        claim_text = claim.get("claim_text", "")
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 5: {self.name}")
        print(f"{'='*60}")
        print(f"Analyzing claim {claim.get('claim_id')}: {claim_text[:80]}...")
        
        # Analyze claim sentiment
        print("\n📊 Analyzing claim language...")
        claim_analysis = self._analyze_text(claim_text, "claim")
        
        # Analyze evidence sentiment
        print("📊 Analyzing evidence sentiment...")
        evidence_texts = [ev.get("relevant_text", "") for ev in evidence[:10]]
        combined_evidence = " ".join(evidence_texts)
        evidence_analysis = self._analyze_text(combined_evidence, "evidence")
        
        # Calculate divergence
        sentiment_divergence = abs(
            claim_analysis["polarity_score"] - evidence_analysis["polarity_score"]
        )
        
        # Detect greenwashing patterns
        print("🔍 Detecting greenwashing patterns...")
        greenwashing_flags = self._detect_greenwashing_patterns(claim_text, claim)
        
        # LLM-based deep analysis
        print("🤖 Running AI linguistic analysis...")
        llm_analysis = self._llm_sentiment_analysis(claim_text)
        
        result = {
            "claim_id": claim.get("claim_id"),
            "claim_sentiment": claim_analysis,
            "evidence_sentiment": evidence_analysis,
            "sentiment_divergence": round(sentiment_divergence, 3),
            "divergence_score": min(100, int(sentiment_divergence * 100)),
            "greenwashing_flags": greenwashing_flags,
            "llm_linguistic_analysis": llm_analysis,
            "overall_linguistic_risk": self._calculate_linguistic_risk(
                claim_analysis, evidence_analysis, sentiment_divergence, greenwashing_flags
            )
        }
        
        print(f"\n✅ Linguistic analysis complete:")
        print(f"   Sentiment divergence: {sentiment_divergence:.3f}")
        print(f"   Greenwashing flags: {len(greenwashing_flags)}")
        print(f"   Linguistic risk: {result['overall_linguistic_risk']}/100")
        
        return result
    
    def _analyze_text(self, text: str, text_type: str) -> Dict[str, Any]:
        """Analyze text using TextBlob + custom metrics"""
        
        if not text:
            return {
                "polarity_score": 0.0,
                "subjectivity_score": 0.0,
                "buzzword_count": 0,
                "vague_terms": [],
                "hedge_words": []
            }
        
        # TextBlob analysis
        blob = TextBlob(text)
        
        # Count patterns
        text_lower = text.lower()
        buzzword_count = sum(1 for word in self.buzzwords if word in text_lower)
        vague_found = [term for term in self.vague_quantifiers if term in text_lower]
        hedge_found = [word for word in self.hedge_words if word in text_lower]
        
        return {
            "polarity_score": round(blob.sentiment.polarity, 3),  # -1 to +1
            "subjectivity_score": round(blob.sentiment.subjectivity, 3),  # 0 to 1
            "buzzword_count": buzzword_count,
            "vague_terms": vague_found,
            "hedge_words": hedge_found,
            "specificity_deficit": buzzword_count > 3 and len(vague_found) > 2
        }
    
    def _detect_greenwashing_patterns(self, claim_text: str, claim: Dict) -> List[Dict[str, str]]:
        """Detect specific greenwashing tactics"""
        
        flags = []
        claim_lower = claim_text.lower()
        
        # Pattern 1: High buzzword density without metrics
        buzzword_count = sum(1 for word in self.buzzwords if word in claim_lower)
        specificity = claim.get("specificity_score", 0)
        
        if buzzword_count >= 2 and specificity < 6:
            flags.append({
                "type": "Vague Buzzwords",
                "severity": "High",
                "description": f"{buzzword_count} buzzwords without specific metrics"
            })
        
        # Pattern 2: Future tense overuse (promises vs. achievements)
        future_words = ["will", "plans to", "aims to", "targets", "committed to", "by 20"]
        future_count = sum(1 for word in future_words if word in claim_lower)
        
        if future_count >= 2 and claim.get("claim_type") == "Target":
            flags.append({
                "type": "Future Promise Heavy",
                "severity": "Moderate",
                "description": "Focus on future targets rather than current achievements"
            })
        
        # Pattern 3: Absolute claims without qualifiers
        absolutes = ["100%", "completely", "entirely", "always", "never", "zero", "all"]
        absolute_count = sum(1 for word in absolutes if word in claim_lower)
        
        if absolute_count >= 1 and specificity < 8:
            flags.append({
                "type": "Absolute Claims",
                "severity": "High",
                "description": "Absolute statements without sufficient detail"
            })
        
        # Pattern 4: Passive voice (avoiding responsibility)
        passive_indicators = ["is achieved", "was reduced", "has been", "were implemented"]
        if any(indicator in claim_lower for indicator in passive_indicators):
            flags.append({
                "type": "Passive Voice",
                "severity": "Low",
                "description": "Passive construction may obscure responsibility"
            })
        
        # Pattern 5: Qualifier overload
        qualifiers = ["leading", "revolutionary", "groundbreaking", "world-class", "best"]
        qualifier_count = sum(1 for word in qualifiers if word in claim_lower)
        
        if qualifier_count >= 2:
            flags.append({
                "type": "Excessive Qualifiers",
                "severity": "Moderate",
                "description": f"{qualifier_count} promotional qualifiers detected"
            })
        
        return flags
    
    def _llm_sentiment_analysis(self, claim_text: str) -> Dict[str, Any]:
        """Use LLM for deep linguistic analysis"""
        
        prompt = SENTIMENT_ANALYSIS_PROMPT.format(text=claim_text)
        
        # Use fast Groq model
        response = self.llm.call_groq(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            use_fast=True
        )
        
        if not response:
            return {"analysis_failed": True}
        
        try:
            # Try to parse JSON
            cleaned = re.sub(r'```\s*', '', cleaned)
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(cleaned[start:end])
        except:
            pass
        
        # Fallback: extract key info from text
        return {
            "raw_analysis": response[:300],
            "parsed": False
        }
    
    def _calculate_linguistic_risk(self, claim_analysis: Dict, evidence_analysis: Dict,
                                   divergence: float, flags: List) -> int:
        """Calculate overall linguistic risk score (0-100)"""
        
        risk_score = 0
        
        # Sentiment divergence (0-30 points)
        risk_score += min(30, int(divergence * 30))
        
        # Buzzword density (0-20 points)
        buzzword_risk = min(20, claim_analysis.get("buzzword_count", 0) * 5)
        risk_score += buzzword_risk
        
        # Vague terms (0-15 points)
        vague_risk = min(15, len(claim_analysis.get("vague_terms", [])) * 5)
        risk_score += vague_risk
        
        # Greenwashing flags (0-35 points)
        flag_severity_scores = {"High": 12, "Moderate": 7, "Low": 3}
        flag_risk = sum(flag_severity_scores.get(flag.get("severity"), 5) for flag in flags)
        risk_score += min(35, flag_risk)
        
        # Subjectivity (0-10 points)
        if claim_analysis.get("subjectivity_score", 0) > 0.7:
            risk_score += 10
        
        return min(100, risk_score)
