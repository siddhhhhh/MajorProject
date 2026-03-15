"""
Confidence Scoring System
Calculates confidence in analysis based on data quality
"""

from typing import Dict, Any, List
from datetime import datetime

class ConfidenceScorer:
    def __init__(self):
        self.name = "Analysis Confidence Scorer"
    
    def calculate_confidence(self, all_analyses: Dict[str, Any]) -> Dict[str, int]:
        """
        Calculate confidence score (0-100) for the entire analysis
        
        Factors:
        - Number of independent sources
        - Data recency
        - Source credibility
        - Historical data availability
        - Evidence gaps
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 10: {self.name}")
        print(f"{'='*60}")
        
        confidence_breakdown = {}
        
        # 1. Source Quantity Score (0-25 points)
        evidence = all_analyses.get('evidence', [])
        total_sources = sum(len(ev.get('evidence', [])) for ev in evidence)
        
        if total_sources >= 15:
            source_score = 25
        elif total_sources >= 10:
            source_score = 20
        elif total_sources >= 5:
            source_score = 15
        else:
            source_score = max(0, total_sources * 3)
        
        confidence_breakdown['source_quantity'] = source_score
        
        # 2. Source Quality Score (0-25 points)
        credibility = all_analyses.get('credibility_analysis', {})
        if credibility:
            metrics = credibility.get('aggregate_metrics', {})
            avg_cred = metrics.get('average_credibility', 0)
            high_quality = metrics.get('high_credibility_count', 0)
            
            quality_score = int(avg_cred * 15) + min(10, high_quality * 2)
        else:
            quality_score = 10
        
        confidence_breakdown['source_quality'] = quality_score
        
        # 3. Data Recency Score (0-20 points)
        if evidence:
            freshness_scores = []
            for ev in evidence:
                for item in ev.get('evidence', []):
                    days = item.get('data_freshness_days', 999)
                    freshness_scores.append(days)
            
            if freshness_scores:
                avg_freshness = sum(freshness_scores) / len(freshness_scores)
                
                if avg_freshness < 30:
                    recency_score = 20
                elif avg_freshness < 90:
                    recency_score = 15
                elif avg_freshness < 180:
                    recency_score = 10
                else:
                    recency_score = 5
            else:
                recency_score = 10
        else:
            recency_score = 5
        
        confidence_breakdown['data_recency'] = recency_score
        
        # 4. Historical Context Score (0-15 points)
        historical = all_analyses.get('historical_analysis', {})
        if historical:
            violations = len(historical.get('past_violations', []))
            achievements = len(historical.get('positive_track_record', []))
            
            if violations + achievements >= 5:
                history_score = 15
            elif violations + achievements >= 3:
                history_score = 10
            else:
                history_score = 5
        else:
            history_score = 0
        
        confidence_breakdown['historical_context'] = history_score
        
        # 5. Evidence Gap Penalty (0-15 points)
        gap_penalty = 0
        for ev in evidence:
            metrics = ev.get('quality_metrics', {})
            if metrics.get('evidence_gap', False):
                gap_penalty += 5
        
        gap_score = max(0, 15 - gap_penalty)
        confidence_breakdown['evidence_completeness'] = gap_score
        
        # Calculate total
        total_confidence = sum(confidence_breakdown.values())
        
        # Determine confidence level
        if total_confidence >= 80:
            level = "HIGH"
            color = "🟢"
        elif total_confidence >= 50:
            level = "MEDIUM"
            color = "🟡"
        else:
            level = "LOW"
            color = "🔴"
        
        print(f"\n{color} Overall Confidence: {total_confidence}/100 ({level})")
        print(f"\n📊 Confidence Breakdown:")
        for factor, score in confidence_breakdown.items():
            print(f"   {factor.replace('_', ' ').title()}: {score}")
        
        return {
            "overall_confidence": total_confidence,
            "confidence_level": level,
            "breakdown": confidence_breakdown,
            "interpretation": self._get_interpretation(total_confidence)
        }
    
    def _get_interpretation(self, score: int) -> str:
        """Get confidence interpretation"""
        if score >= 80:
            return "HIGH CONFIDENCE: Analysis backed by extensive, recent, credible sources. Suitable for regulatory/investment decisions."
        elif score >= 50:
            return "MEDIUM CONFIDENCE: Analysis has some limitations (source gaps, older data, or limited history). Use with additional due diligence."
        else:
            return "LOW CONFIDENCE: Significant data limitations. Analysis should be considered preliminary. Manual verification strongly recommended."
