"""
Temporal Consistency Agent - PHASE 6
Analyzes ESG claims across years to detect inconsistencies between claims and performance
Designed for enterprise-grade greenwashing detection
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json


class TemporalConsistencyAgent:
    """
    Detect temporal inconsistencies between ESG claims and performance
    
    Analyzes:
    1. Claim strength trends across years
    2. ESG performance trends (emissions, scores, etc.)
    3. Peer comparison alignment
    4. Financial alignment with sustainability investments
    
    Outputs a temporal consistency score (0-100):
    - 0-30: Consistent ESG progress
    - 31-60: Moderate inconsistency
    - 61-80: Significant inconsistency
    - 81-100: High greenwashing signal
    """
    
    # Claim strength keywords
    WEAK_CLAIM_KEYWORDS = [
        "commitment", "initiative", "exploring", "considering", "developing",
        "planning", "will", "aim", "goal", "intended", "target"
    ]
    
    MODERATE_CLAIM_KEYWORDS = [
        "transition", "improving", "progressing", "roadmap", "pathway",
        "increasing", "reducing", "advancing", "working", "engaged"
    ]
    
    STRONG_CLAIM_KEYWORDS = [
        "net zero", "carbon neutral", "climate leader", "sustainability leader",
        "industry leader", "best in class", "leading", "achieved", "accomplished",
        "certified", "verified", "committed to", "dedicated to"
    ]
    
    def __init__(self):
        self.name = "Temporal Consistency & Greenwashing Detector"
        
        # Scoring weights
        self.CLAIM_ESCALATION_WEIGHT = 0.35
        self.EMISSION_TREND_WEIGHT = 0.30
        self.PEER_COMPARISON_WEIGHT = 0.20
        self.FINANCIAL_ALIGNMENT_WEIGHT = 0.15
    
    def analyze_temporal_consistency(self, 
                                    company_name: str,
                                    report_claims_by_year: Dict[int, List[str]],
                                    agent_outputs: List[Dict[str, Any]],
                                    risk_level: str = "MODERATE") -> Dict[str, Any]:
        """
        Analyze temporal consistency of ESG claims and detect greenwashing patterns
        
        Args:
            company_name: Company being analyzed
            report_claims_by_year: Claims grouped by year from Phase 5
                {2024: [claim1, claim2], 2023: [claim1], ...}
            agent_outputs: List of all agent outputs from state
            risk_level: Current overall risk level
        
        Returns:
            {
                "temporal_consistency_score": <0-100>,
                "risk_level": "HIGH" | "MODERATE" | "LOW",
                "claim_trend": "increasing" | "stable" | "decreasing",
                "environmental_trend": "improving" | "stable" | "worsening",
                "temporal_inconsistency_detected": bool,
                "years_analyzed": [2024, 2023, 2022],
                "evidence": [...],
                "explanation": "...",
                "status": "success" | "insufficient_data"
            }
        """
        
        print(f"\n{'='*70}")
        print(f"⏳ TEMPORAL CONSISTENCY & GREENWASHING DETECTOR (PHASE 6)")
        print(f"{'='*70}")
        print(f"Company: {company_name}")
        print(f"Years with claims: {list(report_claims_by_year.keys())}")
        
        # ============================================================
        # VALIDATION
        # ============================================================
        if not report_claims_by_year:
            print(f"⚠️ No claims data available for temporal analysis")
            return {
                "temporal_consistency_score": None,
                "temporal_mode": "none",
                "data_quality": "low",
                "temporal_weight": 0.0,
                "status": "insufficient_data",
                "message": "No report claims by year available"
            }

        years_for_trend = [y for y in report_claims_by_year.keys() if y != "unknown"]
        has_multi_year_claims = len(years_for_trend) >= 2
        
        # ============================================================
        # STEP 1: ANALYZE CLAIM STRENGTH TRENDS
        # ============================================================
        print(f"\n📊 Step 1: Analyzing claim strength trends...")
        
        claim_strength_by_year = self._calculate_claim_strength(report_claims_by_year)
        
        claim_trend = self._determine_trend(claim_strength_by_year) if has_multi_year_claims else "unknown"
        claim_escalation_score = self._score_claim_escalation(claim_strength_by_year, claim_trend) if has_multi_year_claims else 45.0
        
        print(f"   Claim strength by year: {claim_strength_by_year}")
        print(f"   Trend: {claim_trend}")
        print(f"   Escalation score: {claim_escalation_score}")
        
        # ============================================================
        # STEP 2: ANALYZE ESG PERFORMANCE TRENDS
        # ============================================================
        print(f"\n📈 Step 2: Analyzing ESG performance trends...")
        
        emissions_trend, emissions_score = self._analyze_emissions_trend(
            company_name, agent_outputs
        )
        
        esg_score_trend, esg_score = self._analyze_esg_score_trend(
            company_name, agent_outputs
        )
        
        environmental_trend = emissions_trend or esg_score_trend or "unknown"

        temporal_quality = self._assess_temporal_data_quality(
            report_claims_by_year=report_claims_by_year,
            emissions_trend=emissions_trend,
            esg_score_trend=esg_score_trend,
            has_multi_year_claims=has_multi_year_claims
        )

        # Recent-report fallback mode: if claims are single-year, still produce temporal snapshot
        if not has_multi_year_claims:
            snapshot = self._recent_report_temporal_snapshot(
                company_name=company_name,
                report_claims_by_year=report_claims_by_year,
                agent_outputs=agent_outputs,
                emissions_trend=emissions_trend,
                esg_score_trend=esg_score_trend,
                temporal_quality=temporal_quality,
            )
            print(f"\n📌 Recent-report temporal snapshot mode active")
            return snapshot
        
        print(f"   Emissions trend: {emissions_trend}")
        print(f"   ESG score trend: {esg_score_trend}")
        print(f"   Environmental trend: {environmental_trend}")
        print(f"   Environmental score: {emissions_score}")
        
        # ============================================================
        # STEP 3: DETECT TEMPORAL INCONSISTENCIES
        # ============================================================
        print(f"\n🔍 Step 3: Detecting temporal inconsistencies...")
        
        inconsistencies = self._detect_inconsistencies(
            claim_trend=claim_trend,
            environmental_trend=environmental_trend,
            company_name=company_name,
            agent_outputs=agent_outputs
        )
        
        inconsistency_detected = len(inconsistencies) > 0
        inconsistency_score = self._score_inconsistencies(inconsistencies)
        
        print(f"   Inconsistencies detected: {len(inconsistencies)}")
        for i, inc in enumerate(inconsistencies, 1):
            print(f"   {i}. {inc}")
        print(f"   Inconsistency score: {inconsistency_score}")
        
        # ============================================================
        # STEP 4: EVALUATE PEER COMPARISON
        # ============================================================
        print(f"\n🏢 Step 4: Evaluating peer comparison...")
        
        peer_comparison_score = self._evaluate_peer_alignment(
            company_name, agent_outputs, claim_trend
        )
        
        print(f"   Peer comparison score: {peer_comparison_score}")
        
        # ============================================================
        # STEP 5: EVALUATE FINANCIAL ALIGNMENT
        # ============================================================
        print(f"\n💰 Step 5: Evaluating financial-ESG alignment...")
        
        financial_alignment_score = self._evaluate_financial_alignment(
            company_name, agent_outputs, claim_trend
        )
        
        print(f"   Financial alignment score: {financial_alignment_score}")
        
        # ============================================================
        # STEP 6: COMPUTE FINAL TEMPORAL CONSISTENCY SCORE
        # ============================================================
        print(f"\n⚖️ Step 6: Computing temporal consistency score...")
        
        # Weighted scoring
        scores = {
            "claim_escalation": claim_escalation_score,
            "environmental_misalignment": inconsistency_score,
            "peer_underperformance": peer_comparison_score,
            "financial_misalignment": financial_alignment_score
        }
        
        temporal_consistency_score = (
            scores["claim_escalation"] * self.CLAIM_ESCALATION_WEIGHT +
            scores["environmental_misalignment"] * self.EMISSION_TREND_WEIGHT +
            scores["peer_underperformance"] * self.PEER_COMPARISON_WEIGHT +
            scores["financial_misalignment"] * self.FINANCIAL_ALIGNMENT_WEIGHT
        )
        
        # Ensure score is 0-100
        temporal_consistency_score = max(0, min(100, temporal_consistency_score))
        
        print(f"   Component scores:")
        print(f"     Claim escalation: {scores['claim_escalation']:.0f}")
        print(f"     Environmental misalignment: {scores['environmental_misalignment']:.0f}")
        print(f"     Peer underperformance: {scores['peer_underperformance']:.0f}")
        print(f"     Financial misalignment: {scores['financial_misalignment']:.0f}")
        print(f"   Final temporal consistency score: {temporal_consistency_score:.0f}/100")
        
        # ============================================================
        # STEP 7: DETERMINE RISK LEVEL
        # ============================================================
        print(f"\n🚨 Step 7: Determining risk level...")
        
        risk_level_temporal = self._score_to_risk_level(temporal_consistency_score)
        
        print(f"   Risk level: {risk_level_temporal}")
        
        # ============================================================
        # COMPILE RESULTS
        # ============================================================
        evidence = inconsistencies.copy()
        
        if claim_trend == "increasing" and environmental_trend == "worsening":
            evidence.append("Claims escalated while environmental performance worsened")
        if claim_trend == "increasing" and emissions_trend == "worsening":
            evidence.append("Greenwashing flag: claims increasing while emissions are increasing")
        
        if claim_trend == "increasing" and peer_comparison_score > 60:
            evidence.append("Company makes increasingly strong claims despite below-average peer performance")
        
        if claim_trend == "increasing" and financial_alignment_score > 50:
            evidence.append("Sustainability claims intensified but financial investments don't support claims")
        
        explanation = self._generate_explanation(
            claim_trend, environmental_trend, temporal_consistency_score
        )
        
        print(f"\n{'='*70}")
        print(f"📋 TEMPORAL ANALYSIS SUMMARY")
        print(f"{'='*70}")
        print(f"Score: {temporal_consistency_score:.0f}/100")
        print(f"Risk: {risk_level_temporal}")
        print(f"Claim trend: {claim_trend}")
        print(f"Environmental trend: {environmental_trend}")
        print(f"Inconsistencies: {len(inconsistencies)}")
        print(f"{'='*70}\n")
        
        return {
            "temporal_consistency_score": temporal_consistency_score,
            "temporal_mode": "trend",
            "data_quality": temporal_quality["level"],
            "temporal_weight": temporal_quality["weight"],
            "risk_level": risk_level_temporal,
            "claim_trend": claim_trend,
            "environmental_trend": environmental_trend,
            "temporal_inconsistency_detected": inconsistency_detected,
            "claim_strength_by_year": claim_strength_by_year,
            "emissions_trend": emissions_trend or "unknown",
            "esg_score_trend": esg_score_trend or "unknown",
            "years_analyzed": sorted(
                [y for y in report_claims_by_year.keys() if y != "unknown"],
                reverse=True
            ),
            "evidence": evidence,
            "explanation": explanation,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "component_scores": scores
        }

    def _assess_temporal_data_quality(self,
                                     report_claims_by_year: Dict[int, List[str]],
                                     emissions_trend: Optional[str],
                                     esg_score_trend: Optional[str],
                                     has_multi_year_claims: bool) -> Dict[str, Any]:
        """Assess reliability of temporal signal and return recommended score weight."""
        years = [y for y in report_claims_by_year.keys() if y != "unknown"]
        claim_count = sum(len(v) for y, v in report_claims_by_year.items() if y != "unknown")

        quantified_claims = 0
        for y, claims in report_claims_by_year.items():
            if y == "unknown":
                continue
            for c in claims:
                text = str(c).lower()
                if any(k in text for k in ["%", "scope", "emission", "target", "tco2", "net zero", "carbon"]):
                    quantified_claims += 1

        has_performance_signal = (emissions_trend is not None) or (esg_score_trend is not None)

        if has_multi_year_claims and len(years) >= 3 and claim_count >= 6 and quantified_claims >= 4 and has_performance_signal:
            return {"level": "high", "weight": 0.20, "claim_count": claim_count, "years": len(years)}

        if has_multi_year_claims and len(years) >= 2 and claim_count >= 3 and quantified_claims >= 2:
            return {"level": "medium", "weight": 0.10, "claim_count": claim_count, "years": len(years)}

        if claim_count >= 2 and quantified_claims >= 1:
            return {"level": "low", "weight": 0.05, "claim_count": claim_count, "years": len(years)}

        return {"level": "low", "weight": 0.0, "claim_count": claim_count, "years": len(years)}
    
    def _calculate_claim_strength(self, claims_by_year: Dict[int, List[str]]) -> Dict[int, float]:
        """
        Calculate average claim strength for each year
        Strength scale: 1 (weak) to 5 (strong)
        """
        strength_by_year = {}
        
        for year in sorted(claims_by_year.keys(), reverse=True):
            claims = claims_by_year[year]
            
            if not claims:
                continue
            
            strengths = []
            
            for claim in claims:
                strength = self._score_claim_strength(claim)
                strengths.append(strength)
            
            # Calculate average strength
            avg_strength = sum(strengths) / len(strengths) if strengths else 0
            strength_by_year[year] = round(avg_strength, 1)
        
        return strength_by_year
    
    def _score_claim_strength(self, claim: str) -> float:
        """
        Score individual claim strength (1-5)
        1: weak commitment
        2: moderately weak
        3: moderate
        4: moderately strong
        5: strong leadership claim
        """
        claim_lower = claim.lower()
        
        # Strong claims
        for keyword in self.STRONG_CLAIM_KEYWORDS:
            if keyword in claim_lower:
                return 5.0
        
        # Moderate claims
        for keyword in self.MODERATE_CLAIM_KEYWORDS:
            if keyword in claim_lower:
                return 3.0
        
        # Weak claims
        for keyword in self.WEAK_CLAIM_KEYWORDS:
            if keyword in claim_lower:
                return 1.5
        
        # Default: moderate
        return 3.0
    
    def _determine_trend(self, values_by_year: Dict[int, float]) -> str:
        """
        Determine if trend is increasing, stable, or decreasing
        """
        if not values_by_year or len(values_by_year) < 2:
            return "unknown"
        
        # Sort by year (newest first)
        sorted_years = sorted(values_by_year.keys(), reverse=True)
        
        if len(sorted_years) < 2:
            return "stable"
        
        # Compare most recent to oldest
        recent_value = values_by_year[sorted_years[0]]
        old_value = values_by_year[sorted_years[-1]]
        
        # Calculate percentage change
        if old_value == 0:
            pct_change = 100 if recent_value > 0 else 0
        else:
            pct_change = ((recent_value - old_value) / old_value) * 100
        
        # Classify trend (threshold: 5% change)
        if pct_change > 5:
            return "increasing"
        elif pct_change < -5:
            return "decreasing"
        else:
            return "stable"
    
    def _score_claim_escalation(self, claim_strength: Dict[int, float], trend: str) -> float:
        """
        Score claim escalation (0-100)
        High scores indicate escalating claims
        """
        if trend == "increasing":
            return 80.0
        elif trend == "decreasing":
            return 20.0
        else:
            return 40.0
    
    def _analyze_emissions_trend(self, company: str, 
                                 agent_outputs: List[Dict]) -> Tuple[Optional[str], float]:
        """
        Extract emissions trend from agent outputs
        Returns: (trend: "improving"|"worsening"|"stable", score: 0-100)
        """
        # Look for carbon extraction or emissions data
        for output in agent_outputs:
            agent_name = output.get("agent", "")
            
            if "carbon" in agent_name.lower():
                output_data = output.get("output", {})
                
                # Try to infer trend from data
                if isinstance(output_data, dict):
                    annual_emissions = output_data.get("annual_emissions", {})
                    if isinstance(annual_emissions, dict) and len(annual_emissions) >= 2:
                        sorted_years = sorted(int(y) for y in annual_emissions.keys())
                        oldest = float(annual_emissions.get(sorted_years[0], 0))
                        latest = float(annual_emissions.get(sorted_years[-1], 0))
                        if oldest > 0:
                            delta_pct = ((latest - oldest) / oldest) * 100
                            if delta_pct > 5:
                                return "worsening", 85.0
                            if delta_pct < -5:
                                return "improving", 20.0
                            return "stable", 45.0

                    # Check for emission metrics
                    if "emissions_trend" in output_data:
                        trend_val = output_data["emissions_trend"].lower()
                        
                        if "increas" in trend_val or "worse" in trend_val:
                            return "worsening", 80.0
                        elif "decreas" in trend_val or "improv" in trend_val:
                            return "improving", 20.0
                        else:
                            return "stable", 40.0

                    emissions = output_data.get("emissions", {})
                    if isinstance(emissions, dict):
                        scope_values = []
                        for scope_key in ["scope1", "scope2", "scope3"]:
                            scope_obj = emissions.get(scope_key, {})
                            if isinstance(scope_obj, dict):
                                value = scope_obj.get("value") or scope_obj.get("emissions_tco2e") or scope_obj.get("total")
                                if isinstance(value, (int, float)) and value > 0:
                                    scope_values.append(value)

                        if scope_values:
                            # Single-year emissions snapshot exists even if trend series is absent.
                            return "stable", 45.0
        
        # No emissions data found
        return None, 50.0
    
    def _analyze_esg_score_trend(self, company: str,
                                agent_outputs: List[Dict]) -> Tuple[Optional[str], float]:
        """
        Extract ESG score trend from risk scorer or other sources
        Returns: (trend: "improving"|"worsening"|"stable", score: 0-100)
        """
        # Look for explicit trend signal first
        for output in agent_outputs:
            if output.get("agent") == "temporal_analysis":
                out = output.get("output", {})
                if isinstance(out, dict):
                    trend_hint = str(out.get("trend", "")).lower()
                    if "declin" in trend_hint:
                        return "worsening", 80.0
                    if "improv" in trend_hint:
                        return "improving", 20.0

        # Fallback to risk scorer signal
        for output in agent_outputs:
            agent_name = output.get("agent", "")
            
            if "risk_scor" in agent_name.lower():
                output_data = output.get("output", {})
                
                if isinstance(output_data, dict):
                    esg_score = output_data.get("esg_score")
                    if esg_score is None:
                        pillar_scores = output_data.get("pillar_scores", {})
                        esg_score = pillar_scores.get("overall_esg_score")
                    
                    # ESG score of 90+ indicates strong performance
                    if esg_score and esg_score > 75:
                        return "improving", 20.0
                    elif esg_score and esg_score < 50:
                        return "worsening", 80.0
                    else:
                        return "stable", 50.0
        
        return None, 50.0
    
    def _detect_inconsistencies(self, claim_trend: str, environmental_trend: str,
                               company_name: str, agent_outputs: List[Dict]) -> List[str]:
        """
        Detect temporal inconsistencies between claims and performance
        """
        inconsistencies = []
        
        # Pattern 1: Claims escalating but environment worsening
        if claim_trend == "increasing" and environmental_trend == "worsening":
            inconsistencies.append(
                "ESG claims escalated while environmental metrics deteriorated"
            )

        # Pattern 1b: Claims up and emissions up is explicit greenwashing pattern
        if claim_trend == "increasing":
            for output in agent_outputs:
                if output.get("agent") == "carbon_extraction":
                    carbon_data = output.get("output", {})
                    annual = carbon_data.get("annual_emissions", {}) if isinstance(carbon_data, dict) else {}
                    if isinstance(annual, dict) and len(annual) >= 2:
                        years = sorted(int(y) for y in annual.keys())
                        old_v = float(annual.get(years[0], 0))
                        new_v = float(annual.get(years[-1], 0))
                        if new_v > old_v and old_v > 0:
                            inconsistencies.append(
                                "Claims increased while annual emissions increased"
                            )
                            break
        
        # Pattern 2: Strong claims but weak actual performance
        if claim_trend == "increasing":
            # Check against risk outputs
            for output in agent_outputs:
                if output.get("agent") == "risk_scoring":
                    risk_data = output.get("output", {})
                    esg_score = risk_data.get("esg_score", 50)
                    
                    if esg_score < 50:
                        inconsistencies.append(
                            f"Strong ESG claims not supported by actual ESG performance (Score: {esg_score})"
                        )
        
        return inconsistencies
    
    def _score_inconsistencies(self, inconsistencies: List[str]) -> float:
        """
        Score inconsistencies (0-100)
        More inconsistencies = higher score
        """
        if not inconsistencies:
            return 20.0  # Baseline if no major inconsistencies
        
        # Each inconsistency adds to score
        score = min(100, 30 + (len(inconsistencies) * 15))
        
        return score
    
    def _evaluate_peer_alignment(self, company: str, 
                                agent_outputs: List[Dict],
                                claim_trend: str) -> float:
        """
        Evaluate if company's claims align with peer performance
        Returns score 0-100 (higher = worse alignment)
        """
        # Look for industry comparator data
        for output in agent_outputs:
            agent_name = output.get("agent", "")
            
            if "peer" in agent_name.lower() or "industry" in agent_name.lower():
                output_data = output.get("output", {})
                
                if isinstance(output_data, dict):
                    # Compare to peers
                    percentile = output_data.get("percentile", 50)
                    
                    # If claims escalating but below average performance
                    if claim_trend == "increasing" and percentile < 50:
                        # Strong claims but below-average performance = misalignment
                        return 70.0
                    elif percentile < 25:
                        return 80.0
                    elif percentile < 50:
                        return 60.0
        
        # No peer data found
        return 50.0
    
    def _evaluate_financial_alignment(self, company: str,
                                     agent_outputs: List[Dict],
                                     claim_trend: str) -> float:
        """
        Evaluate if financial investment aligns with sustainability claims
        Returns score 0-100 (higher = worse alignment)
        """
        # Look for financial analyst data
        for output in agent_outputs:
            agent_name = output.get("agent", "")
            
            if "financial" in agent_name.lower():
                output_data = output.get("output", {})
                
                if isinstance(output_data, dict):
                    # Check if financial data supports claims
                    financial_health = output_data.get("financial_health_score", 50)
                    
                    # If claims escalating but weak financial support
                    if claim_trend == "increasing" and financial_health < 50:
                        return 65.0
                    elif financial_health > 70:
                        return 20.0  # Good financial health supports claims
        
        # Default neutral alignment
        return 50.0
    
    def _score_to_risk_level(self, score: float) -> str:
        """
        Convert temporal consistency score to risk level
        0-30: Low risk (consistent)
        31-60: Moderate risk
        61-80: High risk
        81-100: Critical risk (greenwashing)
        """
        if score <= 30:
            return "LOW"
        elif score <= 60:
            return "MODERATE"
        elif score <= 80:
            return "HIGH"
        else:
            return "CRITICAL"
    
    def _generate_explanation(self, claim_trend: str, environmental_trend: str,
                             score: float) -> str:
        """Generate human-readable explanation of temporal analysis"""
        if claim_trend == "unknown" or environmental_trend == "unknown":
            return "Temporal signal is inconclusive because longitudinal claim/performance coverage is limited."

        if score <= 30:
            return "ESG claims align well with actual environmental performance over time. No significant greenwashing indicators detected."
        
        elif score <= 60:
            return f"Some misalignment between claims ({claim_trend}) and environmental performance ({environmental_trend}). Moderate inconsistency detected."
        
        elif score <= 80:
            return f"Significant temporal inconsistency: Claims {claim_trend} while environmental metrics {environmental_trend}. Strong greenwashing indicators."
        
        else:
            return f"Critical temporal inconsistency: Escalating claims ({claim_trend}) with deteriorating environmental performance ({environmental_trend}). High likelihood of greenwashing."

    def _recent_report_temporal_snapshot(self,
                                         company_name: str,
                                         report_claims_by_year: Dict[int, List[str]],
                                         agent_outputs: List[Dict[str, Any]],
                                         emissions_trend: Optional[str],
                                         esg_score_trend: Optional[str],
                                         temporal_quality: Dict[str, Any]) -> Dict[str, Any]:
        """Single-year fallback that still leverages available report signals."""
        years = sorted([y for y in report_claims_by_year.keys() if y != "unknown"], reverse=True)
        latest_year = years[0] if years else "unknown"
        latest_claims = report_claims_by_year.get(latest_year, []) if years else []

        strengths = [self._score_claim_strength(c) for c in latest_claims] if latest_claims else [3.0]
        avg_claim_strength = sum(strengths) / max(1, len(strengths))

        carbon_quality = 0.0
        for output in agent_outputs:
            if output.get("agent") == "carbon_extraction":
                data = output.get("output", {})
                if isinstance(data, dict):
                    carbon_quality = float(data.get("data_quality", {}).get("overall_score", 0.0))
                break

        risk_score = 40.0
        risk_evidence = []

        if avg_claim_strength >= 4.0 and carbon_quality < 40:
            risk_score += 30
            risk_evidence.append("Strong recent ESG claims with weak quantified emissions disclosure")
        elif avg_claim_strength >= 3.5 and carbon_quality < 60:
            risk_score += 15
            risk_evidence.append("Recent claims stronger than available quantified emissions support")

        if emissions_trend == "worsening":
            risk_score += 20
            risk_evidence.append("Recent report indicates worsening emissions trajectory")
        elif emissions_trend == "improving":
            risk_score -= 10
            risk_evidence.append("Recent report indicates improving emissions trajectory")

        if esg_score_trend == "worsening":
            risk_score += 10
            risk_evidence.append("Recent ESG score signal is weakening")
        elif esg_score_trend == "improving":
            risk_score -= 5

        risk_score = max(0.0, min(100.0, risk_score))
        detected = risk_score >= 60

        return {
            "temporal_consistency_score": round(risk_score, 1),
            "temporal_mode": "snapshot",
            "data_quality": temporal_quality.get("level", "low"),
            "temporal_weight": temporal_quality.get("weight", 0.0),
            "risk_level": self._score_to_risk_level(risk_score),
            "claim_trend": "recent_snapshot",
            "environmental_trend": emissions_trend or esg_score_trend or "unknown",
            "temporal_inconsistency_detected": detected,
            "years_analyzed": [latest_year] if latest_year != "unknown" else [],
            "evidence": risk_evidence,
            "explanation": "Recent-report temporal snapshot generated (single-year mode).",
            "status": "recent_report_analysis",
            "timestamp": datetime.now().isoformat(),
            "component_scores": {
                "claim_strength_latest_year": round(avg_claim_strength, 2),
                "carbon_data_quality": round(carbon_quality, 1),
                "emissions_signal": emissions_trend or "unknown",
                "esg_signal": esg_score_trend or "unknown"
            }
        }


# Singleton instance
_agent_instance = None


def get_temporal_consistency_agent() -> TemporalConsistencyAgent:
    """Get or create singleton instance"""
    global _agent_instance
    
    if _agent_instance is None:
        _agent_instance = TemporalConsistencyAgent()
    
    return _agent_instance


def analyze_temporal_consistency(company_name: str,
                                report_claims_by_year: Dict[int, List[str]],
                                agent_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convenience function for temporal consistency analysis
    
    Example:
        from agents.temporal_consistency_agent import analyze_temporal_consistency
        
        result = analyze_temporal_consistency(
            company_name="Tesla",
            report_claims_by_year={
                2024: ["We aim to achieve net zero by 2030", ...],
                2023: ["We are committed to sustainability", ...]
            },
            agent_outputs=[
                {"agent": "risk_scoring", "output": {...}},
                {"agent": "carbon_extraction", "output": {...}},
                ...
            ]
        )
        
        print(f"Score: {result['temporal_consistency_score']}")
        print(f"Risk: {result['risk_level']}")
    """
    agent = get_temporal_consistency_agent()
    return agent.analyze_temporal_consistency(
        company_name, report_claims_by_year, agent_outputs
    )
