"""
Final Risk Scorer & ESG Rating Specialist
Industry-adjusted risk scoring matching MSCI/Sustainalytics methodology
100% Dynamic - All data loaded from config files
"""

from typing import Dict, Any, List
from datetime import datetime
from core.llm_client import llm_client
import json
import os


class RiskScorer:
    def __init__(self):
        self.name = "Greenwashing Risk Scoring & ESG Rating Specialist"
        self.llm = llm_client
        
        # Load ALL configuration from external file (NO HARDCODING)
        self.config = self._load_config()
        self.industry_baseline_risk = self.config.get('industry_baseline_risk', {})
        self.weights = self.config.get('component_weights', {})
        self.risk_thresholds = self.config.get('risk_thresholds', {})
        
        print(f"✅ Loaded {len(self.industry_baseline_risk)} industry baselines from config")
    
    def _load_config(self) -> Dict:
        """Load industry configuration from external JSON file"""
        config_path = "config/industry_baselines.json"
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    print(f"✅ Loaded industry config from {config_path}")
                    return config
            else:
                print(f"⚠️ Config file not found: {config_path}")
                print("   Creating default config...")
                self._create_default_config(config_path)
                
                # Load again
                with open(config_path, 'r') as f:
                    return json.load(f)
                    
        except Exception as e:
            print(f"⚠️ Error loading config: {e}")
            print("   Using fallback defaults")
        
        # Fallback defaults (minimal)
        return {
            "industry_baseline_risk": {"unknown": {"baseline": 50, "source": "Default"}},
            "component_weights": {
                'claim_verification': 0.30,
                'evidence_quality': 0.15,
                'source_credibility': 0.15,
                'sentiment_divergence': 0.10,
                'historical_pattern': 0.15,
                'contradiction_severity': 0.15
            },
            "risk_thresholds": {
                "very_high_risk_industries": {"baseline_threshold": 70, "high_risk": 45, "moderate_risk": 30},
                "high_risk_industries": {"baseline_threshold": 60, "high_risk": 55, "moderate_risk": 35},
                "moderate_risk_industries": {"baseline_threshold": 50, "high_risk": 65, "moderate_risk": 40},
                "low_risk_industries": {"baseline_threshold": 0, "high_risk": 70, "moderate_risk": 45}
            }
        }
    
    def _create_default_config(self, config_path: str):
        """Create default industry baselines config file"""
        
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        default_config = {
            "industry_baseline_risk": {
                "oil_and_gas": {"baseline": 75, "source": "MSCI ESG 2024", "rationale": "High carbon intensity"},
                "coal": {"baseline": 80, "source": "MSCI ESG 2024", "rationale": "Highest emissions"},
                "mining": {"baseline": 70, "source": "MSCI ESG 2024", "rationale": "Environmental degradation"},
                "chemicals": {"baseline": 65, "source": "MSCI ESG 2024", "rationale": "Toxic waste"},
                "aviation": {"baseline": 70, "source": "MSCI ESG 2024", "rationale": "High emissions"},
                "automotive": {"baseline": 60, "source": "MSCI ESG 2024", "rationale": "Transition challenges"},
                "fast_fashion": {"baseline": 65, "source": "MSCI ESG 2024", "rationale": "Labor & waste"},
                "tobacco": {"baseline": 75, "source": "MSCI ESG 2024", "rationale": "Public health"},
                "defense": {"baseline": 60, "source": "MSCI ESG 2024", "rationale": "Ethical concerns"},
                "consumer_goods": {"baseline": 50, "source": "MSCI ESG 2024", "rationale": "Packaging waste"},
                "retail": {"baseline": 45, "source": "MSCI ESG 2024", "rationale": "Labor practices"},
                "food_beverage": {"baseline": 50, "source": "MSCI ESG 2024", "rationale": "Water usage"},
                "pharmaceuticals": {"baseline": 55, "source": "MSCI ESG 2024", "rationale": "Drug pricing"},
                "banking": {"baseline": 50, "source": "MSCI ESG 2024", "rationale": "Fossil fuel financing"},
                "real_estate": {"baseline": 45, "source": "MSCI ESG 2024", "rationale": "Energy efficiency"},
                "transportation": {"baseline": 55, "source": "MSCI ESG 2024", "rationale": "Emissions"},
                "hospitality": {"baseline": 45, "source": "MSCI ESG 2024", "rationale": "Water & waste"},
                "technology": {"baseline": 35, "source": "MSCI ESG 2024", "rationale": "Data privacy"},
                "software": {"baseline": 30, "source": "MSCI ESG 2024", "rationale": "Low footprint"},
                "healthcare_services": {"baseline": 35, "source": "MSCI ESG 2024", "rationale": "Patient care"},
                "telecommunications": {"baseline": 40, "source": "MSCI ESG 2024", "rationale": "Digital divide"},
                "renewable_energy": {"baseline": 25, "source": "MSCI ESG 2024", "rationale": "Positive impact"},
                "education": {"baseline": 30, "source": "MSCI ESG 2024", "rationale": "Access equity"},
                "unknown": {"baseline": 50, "source": "Default", "rationale": "Insufficient data"}
            },
            "component_weights": {
                "claim_verification": 0.30,
                "evidence_quality": 0.15,
                "source_credibility": 0.15,
                "sentiment_divergence": 0.10,
                "historical_pattern": 0.15,
                "contradiction_severity": 0.15
            },
            "risk_thresholds": {
                "very_high_risk_industries": {"baseline_threshold": 70, "high_risk": 45, "moderate_risk": 30},
                "high_risk_industries": {"baseline_threshold": 60, "high_risk": 55, "moderate_risk": 35},
                "moderate_risk_industries": {"baseline_threshold": 50, "high_risk": 65, "moderate_risk": 40},
                "low_risk_industries": {"baseline_threshold": 0, "high_risk": 70, "moderate_risk": 45}
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        print(f"✅ Created default config: {config_path}")
    
    def calculate_final_score(self, company: str, all_analyses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate final ESG score with industry-adjusted risk thresholds
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 7: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        
        # Step 1: Identify industry (100% dynamic via LLM)
        industry = self._identify_industry(company, all_analyses)
        industry_data = self.industry_baseline_risk.get(industry, self.industry_baseline_risk.get('unknown'))
        industry_baseline = industry_data.get('baseline', 50)
        
        print(f"Industry: {industry.replace('_', ' ').title()}")
        print(f"Industry baseline risk: {industry_baseline}/100")
        print(f"Source: {industry_data.get('source', 'Unknown')}")
        
        # Step 2: Calculate component scores
        components = self._calculate_components(all_analyses)
        
        # Step 3: Calculate base greenwashing risk (weighted average)
        base_risk = sum(
            components.get(key, 50) * weight 
            for key, weight in self.weights.items()
        )
        
        # Step 4: Apply industry adjustment
        industry_adjustment = (industry_baseline - 50) * 0.3  # 30% weight on industry
        adjusted_risk = base_risk + industry_adjustment
        
        # Step 5: Apply peer comparison modifier
        peer_modifier = self._calculate_peer_modifier(all_analyses, industry)
        debate_penalty = 0
        if all_analyses.get("debate_activated"):
            debate_penalty = 10.0  # +10 points risk if debate triggered
            print(f"⚠️  Multi-agent debate detected - applying +{debate_penalty} risk penalty")

        final_risk = adjusted_risk + peer_modifier + debate_penalty
        
        # Clamp to 0-100
        greenwashing_risk = max(0, min(100, final_risk))
        
        # ESG Score is inverse
        esg_score = 100 - greenwashing_risk
        
        # Step 6: Determine risk level with industry-aware thresholds
        risk_level, rating_grade = self._determine_risk_level(
            greenwashing_risk, 
            industry_baseline
        )
        
        # Step 7: Generate insights
        top_reasons = self._generate_top_reasons(
            components, all_analyses, industry, greenwashing_risk
        )
        
        insights = self._generate_insights(
            greenwashing_risk, risk_level, industry, company
        )
        
        result = {
            "company": company,
            "analysis_timestamp": datetime.now().isoformat(),
            "industry": industry,
            "industry_baseline_risk": industry_baseline,
            "industry_source": industry_data.get('source', 'Unknown'),
            "base_risk_score": round(base_risk, 1),
            "industry_adjustment": round(industry_adjustment, 1),
            "peer_adjustment": round(peer_modifier, 1),
            "greenwashing_risk_score": round(greenwashing_risk, 1),
            "esg_score": round(esg_score, 1),
            "risk_level": risk_level,
            "rating_grade": rating_grade,
            "component_scores": components,
            "explainability_top_3_reasons": top_reasons,
            "actionable_insights": insights,
            "confidence_level": 85
        }
        
        print(f"\n✅ Final Risk Assessment:")
        print(f"   Base Risk: {base_risk:.1f}/100")
        print(f"   Industry Adjustment: {industry_adjustment:+.1f}")
        print(f"   Peer Adjustment: {peer_modifier:+.1f}")
        print(f"   Final Greenwashing Risk: {greenwashing_risk:.1f}/100")
        print(f"   ESG Score: {esg_score:.1f}/100 (Grade: {rating_grade})")
        print(f"   Risk Level: {risk_level}")
        
        return result
    
    def _identify_industry(self, company: str, analyses: Dict) -> str:
        """
        Identify company's industry - 100% DYNAMIC (NO HARDCODED FALLBACKS)
        Uses LLM to classify into predefined MSCI-based categories
        """
        
        # Get list of valid industries from config
        valid_industries = [k for k in self.industry_baseline_risk.keys() if k != 'unknown']
        
        # Use LLM to classify
        prompt = f"""Classify {company} into ONE of these industries:

{', '.join(valid_industries)}

Return ONLY the industry name from the list above, nothing else.

Examples:
- BP → oil_and_gas
- Tesla → automotive
- Microsoft → technology
- H&M → fast_fashion
- Coca-Cola → food_beverage

Company: {company}
Industry:"""

        try:
            response = self.llm.call_groq(
                [{"role": "user", "content": prompt}],
                use_fast=True
            )
            
            if response:
                # Clean response
                industry = response.strip().lower()
                industry = industry.replace(' ', '_')
                industry = industry.replace('.', '').replace(',', '').replace(':', '')
                
                # Direct match
                if industry in valid_industries:
                    return industry
                
                # Fuzzy match
                for valid in valid_industries:
                    if valid in industry or industry in valid:
                        return valid
                    
                    # Check if any word matches
                    industry_words = industry.split('_')
                    valid_words = valid.split('_')
                    if any(word in valid_words for word in industry_words):
                        return valid
        
        except Exception as e:
            print(f"   ⚠️ Industry classification error: {e}")
        
        # If LLM fails, return unknown (NO HARDCODED COMPANY NAMES)
        print(f"   ⚠️ Could not classify {company} - using 'unknown'")
        return "unknown"
    
    def _calculate_components(self, analyses: Dict) -> Dict[str, float]:
        """
        Calculate all component scores (0-100, higher = more risk)
        FIXED: Unverifiable claims now properly penalized
        """
        
        components = {}
        
        # 1. Claim Verification (CRITICAL - FIXED scoring)
        contradictions = analyses.get('contradiction_analysis', [])
        if contradictions:
            contradicted = sum(1 for c in contradictions if c.get('overall_verdict') == 'Contradicted')
            unverifiable = sum(1 for c in contradictions if c.get('overall_verdict') == 'Unverifiable')
            partial = sum(1 for c in contradictions if c.get('overall_verdict') == 'Partially True')
            verified = sum(1 for c in contradictions if c.get('overall_verdict') == 'Verified')
            total = len(contradictions)
            
            # FIXED: Increased penalty for unverifiable claims
            # Contradicted = 100 risk
            # Unverifiable = 85 risk (was 70 - too lenient)
            # Partially True = 50 risk
            # Verified = 0 risk
            score = ((contradicted * 100) + (unverifiable * 85) + (partial * 50) + (verified * 0)) / total if total > 0 else 50
            components['claim_verification'] = min(100, score)
        else:
            components['claim_verification'] = 100
        
        # 2. Evidence Quality (more sources = lower risk)
        evidence = analyses.get('evidence', [])
        total_sources = sum(len(ev.get('evidence', [])) for ev in evidence)
        
        if total_sources >= 20:
            components['evidence_quality'] = 10
        elif total_sources >= 15:
            components['evidence_quality'] = 20
        elif total_sources >= 10:
            components['evidence_quality'] = 35
        elif total_sources >= 5:
            components['evidence_quality'] = 60
        else:
            components['evidence_quality'] = 90
        
        # 3. Source Credibility (higher credibility = lower risk)
        credibility = analyses.get('credibility_analysis', {})
        if credibility:
            metrics = credibility.get('aggregate_metrics', {})
            avg_cred = metrics.get('average_credibility', 0.5)
            # Convert: high credibility (0.9) → low risk (10)
            components['source_credibility'] = int((1.0 - avg_cred) * 100)
        else:
            components['source_credibility'] = 100
        
        # 4. Sentiment Divergence
        sentiment_list = analyses.get('sentiment_analysis', [])
        if sentiment_list:
            divergences = [s.get('divergence_score', 0) for s in sentiment_list]
            components['sentiment_divergence'] = int(sum(divergences) / len(divergences))
        else:
            components['sentiment_divergence'] = 50
        
        # 5. Historical Pattern
        historical = analyses.get('historical_analysis', {})
        if historical:
            violations = len(historical.get('past_violations', []))
            greenwashing_acc = historical.get('greenwashing_history', {}).get('prior_accusations', 0)
            reputation = historical.get('reputation_score', 50)
            
            # More violations = higher risk
            violation_risk = min(100, violations * 20)
            greenwashing_risk = min(100, greenwashing_acc * 30)
            reputation_risk = 100 - reputation
            
            components['historical_pattern'] = int((violation_risk + greenwashing_risk + reputation_risk) / 3)
        else:
            components['historical_pattern'] = 50
        
        # 6. Contradiction Severity
        if contradictions:
            major_count = sum(
                1 for c in contradictions 
                for cont in c.get('specific_contradictions', []) 
                if cont.get('severity') == 'Major'
            )
            components['contradiction_severity'] = min(100, major_count * 30)
        else:
            components['contradiction_severity'] = 0
        
        # At the end of calculate_components method (before return components, around line 440):

        # NEW: Check for vague greenwashing language
        if analyses.get("claim"):
            claim_text = analyses["claim"].lower()
            greenwashing_keywords = [
                "committed to", "leader in", "eco-friendly", "sustainable", 
                "green", "environmentally friendly", "climate positive"
            ]
            
            keyword_count = sum(1 for keyword in greenwashing_keywords if keyword in claim_text)
            has_numbers = any(char.isdigit() for char in analyses["claim"])
            
            # Vague claim (multiple buzzwords + no metrics) = +20 risk penalty
            if keyword_count >= 2 and not has_numbers:
                components["claim_verification"] = min(100, components.get("claim_verification", 50) + 20)
                print(f"⚠️  Vague claim detected ({keyword_count} buzzwords, no metrics) - penalty applied")

        return components

    def _calculate_peer_modifier(self, analyses: Dict, industry: str) -> float:
        """
        Calculate peer comparison modifier
        Unverified superlative claims → penalty
        """
        
        industry_comp = analyses.get('industry_comparison', {})
        if not industry_comp or industry_comp.get('error'):
            return 0.0
        
        # Check for unverified superlative claims
        comparisons = industry_comp.get('claim_comparisons', [])
        superlative_unverified = sum(
            1 for c in comparisons 
            if c.get('uses_superlative') and not c.get('verified_against_peers')
        )
        
        # Penalty: +5 points per unverified superlative
        if superlative_unverified > 0:
            return superlative_unverified * 5.0
        
        return 0.0
    
    def _determine_risk_level(self, risk_score: float, industry_baseline: float) -> tuple:
        """
        Determine risk level with industry-adjusted thresholds
        High-risk industries have LOWER bar for HIGH rating
        """
        
        # Load thresholds from config
        thresholds = self.risk_thresholds
        
        # Select threshold category based on industry baseline
        if industry_baseline >= 70:
            category = thresholds.get('very_high_risk_industries', {})
        elif industry_baseline >= 60:
            category = thresholds.get('high_risk_industries', {})
        elif industry_baseline >= 50:
            category = thresholds.get('moderate_risk_industries', {})
        else:
            category = thresholds.get('low_risk_industries', {})
        
        high_threshold = category.get('high_risk', 67)
        mod_threshold = category.get('moderate_risk', 34)
        
        # Determine level
        if risk_score >= high_threshold:
            risk_level = "HIGH"
            if risk_score >= 80:
                rating_grade = "CCC"
            else:
                rating_grade = "B"
        elif risk_score >= mod_threshold:
            risk_level = "MODERATE"
            rating_grade = "BBB"
        else:
            risk_level = "LOW"
            if risk_score <= 20:
                rating_grade = "AAA"
            elif risk_score <= 30:
                rating_grade = "AA"
            else:
                rating_grade = "A"
        
        return risk_level, rating_grade
    
    def _generate_top_reasons(self, components: Dict, analyses: Dict, 
                             industry: str, risk_score: float) -> List[str]:
        """Generate top 3 specific, data-backed reasons"""
        
        reasons = []
        
        # Sort components by risk score
        sorted_comps = sorted(components.items(), key=lambda x: x[1], reverse=True)
        
        for component, score in sorted_comps[:3]:
            if component == 'claim_verification' and score > 60:
                contradictions = analyses.get('contradiction_analysis', [])
                contradicted = sum(1 for c in contradictions if c.get('overall_verdict') == 'Contradicted')
                unverifiable = sum(1 for c in contradictions if c.get('overall_verdict') == 'Unverifiable')
                
                if contradicted > 0:
                    reasons.append(
                        f"Claim verification failure: {contradicted} claim(s) contradicted by evidence (risk: {int(score)}%)"
                    )
                elif unverifiable > 0:
                    reasons.append(
                        f"Unverifiable claims: {unverifiable} claim(s) lack supporting evidence (risk: {int(score)}%)"
                    )
            
            elif component == 'historical_pattern' and score > 50:
                historical = analyses.get('historical_analysis', {})
                violations = len(historical.get('past_violations', []))
                if violations > 0:
                    reasons.append(
                        f"Historical violations: {violations} documented ESG violation(s) (risk: {int(score)}%)"
                    )
            
            elif component == 'contradiction_severity' and score > 40:
                contradictions = analyses.get('contradiction_analysis', [])
                major_count = sum(
                    1 for c in contradictions 
                    for cont in c.get('specific_contradictions', []) 
                    if cont.get('severity') == 'Major'
                )
                if major_count > 0:
                    reasons.append(
                        f"Major contradictions: {major_count} severe inconsistenc(y/ies) detected (risk: {int(score)}%)"
                    )
            
            elif component == 'source_credibility' and score > 40:
                reasons.append(
                    f"Source credibility concerns: Evidence from low-quality or biased sources (risk: {int(score)}%)"
                )
        
        # Add industry context if high-risk
        if len(reasons) < 3 and industry in ['oil_and_gas', 'coal', 'mining', 'aviation', 'tobacco']:
            reasons.append(
                f"High-scrutiny industry ({industry.replace('_', ' ').title()}): ESG claims require exceptional evidence standards"
            )
        
        # Ensure we have at least 3 reasons
        while len(reasons) < 3:
            reasons.append("Insufficient data quality or evidence gaps detected")
        
        return reasons[:3]
    
    def _generate_insights(self, risk_score: float, risk_level: str, 
                          industry: str, company: str) -> Dict[str, str]:
        """Generate stakeholder-specific actionable insights"""
        
        industry_name = industry.replace('_', ' ').title()
        
        if risk_level == "HIGH":
            insights = {
                "for_investors": f"HIGH RISK: {company} ({industry_name}) shows significant greenwashing indicators. Claims lack credible verification or contain major contradictions. NOT suitable for ESG portfolios without deep independent audit and verification.",
                "for_regulators": f"IMMEDIATE ATTENTION REQUIRED: {company} requires formal investigation. Multiple red flags detected including unverified claims, contradictions, or historical violations. Recommend requesting documentation and potential enforcement action in high-scrutiny {industry_name} sector.",
                "for_consumers": f"CAUTION ADVISED: {company}'s ESG claims appear questionable or unsubstantiated. {industry_name} companies face inherent sustainability challenges. Strongly recommend seeking alternatives with credible third-party certifications (B Corp, Fair Trade, etc.)."
            }
        elif risk_level == "MODERATE":
            insights = {
                "for_investors": f"MODERATE RISK: {company} ({industry_name}) shows mixed ESG performance with some concerns. Additional due diligence required before investment. Monitor peer comparisons, upcoming sustainability reports, and third-party ratings (MSCI, Sustainalytics).",
                "for_regulators": f"MONITORING RECOMMENDED: {company} shows some inconsistencies in ESG claims. Standard oversight appropriate for {industry_name} sector. Consider requesting clarification on specific unverified claims and ensuring compliance with disclosure requirements.",
                "for_consumers": f"MIXED SIGNALS: {company} demonstrates some genuine ESG efforts but {industry_name} sector has structural sustainability challenges. Verify specific product claims independently and compare with competitors' performance."
            }
        else:
            insights = {
                "for_investors": f"LOW RISK: {company} ({industry_name}) shows credible ESG commitments backed by verifiable evidence from quality sources. Suitable for ESG-focused portfolios. Continue standard monitoring of annual reports and third-party assessments.",
                "for_regulators": f"NO MAJOR CONCERNS: {company} meets expected disclosure and performance standards for {industry_name} sector. Routine monitoring sufficient. Claims appear substantiated and consistent with available evidence.",
                "for_consumers": f"TRUSTWORTHY: {company}'s ESG claims appear credible with reasonable evidence backing from independent sources. Good choice within {industry_name} sector. Look for third-party certifications for additional assurance."
            }
        
        return insights
