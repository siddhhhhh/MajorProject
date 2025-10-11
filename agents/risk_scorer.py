import json
from typing import Dict, Any, List
from datetime import datetime
from core.llm_client import llm_client
from config.agent_prompts import RISK_SCORING_PROMPT

class RiskScorer:
    def __init__(self):
        self.name = "Greenwashing Risk Scoring & ESG Rating Specialist"
        self.llm = llm_client
        
        # MSCI-style weights
        self.weights = {
            "claim_verification": 0.25,
            "evidence_quality": 0.20,
            "source_credibility": 0.20,
            "sentiment_divergence": 0.15,
            "historical_pattern": 0.10,
            "contradiction_severity": 0.10
        }
    
    def calculate_final_score(self, company: str, all_analyses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate final greenwashing risk score and ESG rating
        Synthesize all agent outputs into MSCI/Sustainalytics-style report
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 7: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        print("\n📊 Synthesizing all analyses...")
        
        # Extract component scores
        component_scores = self._calculate_component_scores(all_analyses)
        
        # Calculate weighted greenwashing risk (0-100, higher = more risk)
        greenwashing_risk_score = self._calculate_weighted_risk(component_scores)
        
        # Calculate ESG score (0-100, higher = better)
        esg_score = 100 - greenwashing_risk_score
        
        # Determine risk level
        risk_level = self._determine_risk_level(greenwashing_risk_score)
        
        # Generate explainability
        top_reasons = self._generate_top_reasons(component_scores, all_analyses)
        
        # Industry benchmarking (if data available)
        industry_benchmark = self._get_industry_benchmark(company)
        
        # Generate actionable insights
        insights = self._generate_insights(greenwashing_risk_score, component_scores, all_analyses)
        
        result = {
            "company": company,
            "analysis_timestamp": datetime.now().isoformat(),
            "esg_score": round(esg_score, 1),
            "greenwashing_risk_score": round(greenwashing_risk_score, 1),
            "risk_level": risk_level,
            "component_scores": component_scores,
            "rating_grade": self._get_rating_grade(esg_score),
            "explainability_top_3_reasons": top_reasons,
            "actionable_insights": insights,
            "industry_benchmark": industry_benchmark,
            "confidence_level": self._calculate_confidence(all_analyses)
        }
        
        print(f"\n✅ Final scoring complete:")
        print(f"   ESG Score: {result['esg_score']}/100")
        print(f"   Greenwashing Risk: {result['greenwashing_risk_score']}/100")
        print(f"   Risk Level: {risk_level}")
        print(f"   Rating Grade: {result['rating_grade']}")
        
        return result
    
    def _calculate_component_scores(self, analyses: Dict) -> Dict[str, float]:
        """Calculate normalized component scores (0-100)"""
        
        scores = {}
        
        # 1. Claim Verification Score (0-100, higher = more risk)
        contradictions = analyses.get("contradiction_analysis", [])
        if contradictions:
            verified = sum(1 for c in contradictions if c.get("overall_verdict") == "Verified")
            contradicted = sum(1 for c in contradictions if c.get("overall_verdict") == "Contradicted")
            unverifiable = sum(1 for c in contradictions if c.get("overall_verdict") == "Unverifiable")
            partial = sum(1 for c in contradictions if c.get("overall_verdict") == "Partially True")
            total = len(contradictions)
            
            score = (contradicted * 100 + unverifiable * 60 + partial * 30) / total if total > 0 else 50
            scores["claim_verification"] = min(100, score)
        else:
            scores["claim_verification"] = 50
        
        # 2. Evidence Quality Score (0-100, higher = more risk)
        evidence_metrics = []
        for ev in analyses.get("evidence", []):
            metrics = ev.get("quality_metrics", {})
            evidence_metrics.append(metrics)
        
        if evidence_metrics:
            avg_gap = sum(1 for m in evidence_metrics if m.get("evidence_gap")) / len(evidence_metrics)
            avg_independent = sum(m.get("independent_sources", 0) for m in evidence_metrics) / len(evidence_metrics)
            
            # High risk if evidence gaps or few independent sources
            score = (avg_gap * 80) + max(0, (5 - avg_independent) * 4)
            scores["evidence_quality"] = min(100, score)
        else:
            scores["evidence_quality"] = 70
        
        # 3. Source Credibility Score (0-100, higher = more risk)
        credibility = analyses.get("credibility_analysis", {})
        if credibility:
            metrics = credibility.get("aggregate_metrics", {})
            avg_cred = metrics.get("average_credibility", 0.5)
            
            # Convert to risk score (low credibility = high risk)
            scores["source_credibility"] = int((1 - avg_cred) * 100)
        else:
            scores["source_credibility"] = 50
        
        # 4. Sentiment Divergence Score (already 0-100)
        sentiment_analyses = analyses.get("sentiment_analysis", [])
        if sentiment_analyses:
            avg_divergence = sum(s.get("divergence_score", 0) for s in sentiment_analyses) / len(sentiment_analyses)
            scores["sentiment_divergence"] = int(avg_divergence)
        else:
            scores["sentiment_divergence"] = 30
        
        # 5. Historical Pattern Score (0-100, higher = worse history)
        historical = analyses.get("historical_analysis", {})
        if historical:
            reputation = historical.get("reputation_score", 50)
            # Invert reputation to risk (low reputation = high risk)
            scores["historical_pattern"] = int(100 - reputation)
        else:
            scores["historical_pattern"] = 50
        
        # 6. Contradiction Severity Score (0-100)
        if contradictions:
            # Count major contradictions
            major_count = 0
            for c in contradictions:
                contras = c.get("specific_contradictions", [])
                major_count += sum(1 for con in contras if con.get("severity") == "Major")
            
            scores["contradiction_severity"] = min(100, major_count * 30)
        else:
            scores["contradiction_severity"] = 0
        
        return scores
    
    def _calculate_weighted_risk(self, component_scores: Dict[str, float]) -> float:
        """Calculate weighted risk score using MSCI-style methodology"""
        
        weighted_sum = 0
        for component, score in component_scores.items():
            weight = self.weights.get(component, 0)
            weighted_sum += score * weight
        
        return min(100, max(0, weighted_sum))
    
    def _determine_risk_level(self, risk_score: float) -> str:
        """Determine risk level category"""
        if risk_score >= 67:
            return "HIGH"
        elif risk_score >= 34:
            return "MODERATE"
        else:
            return "LOW"
    
    def _get_rating_grade(self, esg_score: float) -> str:
        """MSCI-style letter grade"""
        if esg_score >= 85:
            return "AAA"
        elif esg_score >= 75:
            return "AA"
        elif esg_score >= 65:
            return "A"
        elif esg_score >= 55:
            return "BBB"
        elif esg_score >= 45:
            return "BB"
        elif esg_score >= 35:
            return "B"
        else:
            return "CCC"
    
    def _generate_top_reasons(self, component_scores: Dict, analyses: Dict) -> List[str]:
        """Generate top 3 specific reasons for the score"""
        
        reasons = []
        
        # Sort components by score (highest risk first)
        sorted_components = sorted(component_scores.items(), key=lambda x: x[1], reverse=True)
        
        for component, score in sorted_components[:3]:
            if component == "claim_verification" and score > 50:
                contradicted = sum(1 for c in analyses.get("contradiction_analysis", []) 
                                 if c.get("overall_verdict") == "Contradicted")
                if contradicted > 0:
                    reasons.append(f"{contradicted} claim(s) contradicted by evidence with {int(score)}% verification risk")
            
            elif component == "source_credibility" and score > 40:
                cred_analysis = analyses.get("credibility_analysis", {})
                low_cred = cred_analysis.get("aggregate_metrics", {}).get("low_credibility_count", 0)
                reasons.append(f"Source credibility concerns: {low_cred} low-quality sources ({int(score)}% risk)")
            
            elif component == "historical_pattern" and score > 50:
                historical = analyses.get("historical_analysis", {})
                violations = len(historical.get("past_violations", []))
                if violations > 0:
                    reasons.append(f"Historical track record: {violations} documented violations (risk score: {int(score)})")
            
            elif component == "sentiment_divergence" and score > 40:
                reasons.append(f"Language analysis shows {int(score)}% sentiment divergence between claims and evidence")
            
            elif component == "evidence_quality" and score > 50:
                reasons.append(f"Evidence quality concerns with {int(score)}% risk (gaps or limited independent sources)")
        
        # Ensure we have 3 reasons
        if len(reasons) < 3:
            reasons.append("Comprehensive multi-source analysis across ESG dimensions")
        
        return reasons[:3]
    
    def _generate_insights(self, risk_score: float, component_scores: Dict, analyses: Dict) -> Dict[str, str]:
        """Generate actionable insights for different stakeholders"""
        
        insights = {}
        
        # For investors
        if risk_score >= 67:
            insights["for_investors"] = "High greenwashing risk detected. Recommend independent ESG due diligence before investment decisions. Consider ESG-focused funds with stricter verification."
        elif risk_score >= 34:
            insights["for_investors"] = "Moderate ESG claim reliability. Standard due diligence recommended. Monitor for material ESG developments."
        else:
            insights["for_investors"] = "Low greenwashing risk. ESG claims appear credible. Suitable for ESG-focused investment portfolios."
        
        # For regulators
        high_risk_areas = [k for k, v in component_scores.items() if v > 60]
        if high_risk_areas:
            insights["for_regulators"] = f"Areas requiring scrutiny: {', '.join(high_risk_areas)}. Recommend verification of specific claims and potential investigation."
        else:
            insights["for_regulators"] = "No major red flags requiring immediate regulatory action based on public information."
        
        # For consumers
        if risk_score >= 67:
            insights["for_consumers"] = "Exercise skepticism toward company's ESG claims. Seek independent certifications and third-party verification."
        elif risk_score >= 34:
            insights["for_consumers"] = "Company makes some credible ESG efforts but verify specific claims before making purchase decisions based on sustainability."
        else:
            insights["for_consumers"] = "Company's ESG claims appear trustworthy. Reasonable confidence in sustainability commitments."
        
        return insights
    
    def _get_industry_benchmark(self, company: str) -> Dict[str, Any]:
        """Get industry benchmark data (placeholder for future enhancement)"""
        
        # This would ideally fetch real industry data
        # For now, return placeholder
        return {
            "industry": "To be determined",
            "peer_average_esg_score": None,
            "company_percentile": None,
            "note": "Industry benchmarking requires proprietary database access"
        }
    
    def _calculate_confidence(self, analyses: Dict) -> int:
        """Calculate confidence level in the analysis (0-100)"""
        
        confidence = 100
        
        # Reduce confidence if limited evidence
        evidence_count = sum(len(ev.get("evidence", [])) for ev in analyses.get("evidence", []))
        if evidence_count < 10:
            confidence -= 20
        
        # Reduce if no historical data
        if not analyses.get("historical_analysis"):
            confidence -= 10
        
        # Reduce if limited source diversity
        credibility = analyses.get("credibility_analysis", {})
        if credibility:
            diversity = credibility.get("aggregate_metrics", {}).get("source_diversity", 0)
            if diversity < 3:
                confidence -= 15
        
        return max(50, confidence)  # Minimum 50% confidence

