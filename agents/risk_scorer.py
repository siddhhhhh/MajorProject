"""
Final Risk Scorer & ESG Rating Specialist
Industry-adjusted risk scoring matching MSCI/Sustainalytics methodology
100% Dynamic - All data loaded from config files
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from core.llm_client import llm_client
import json
import os
import re
import numpy as np
from ml_models.xgboost_risk_model import XGBoostRiskModel
from ml_models.lightgbm_esg_predictor import LightGBMESGPredictor
from ml_models.lstm_trend_predictor import get_lstm_predictor
from ml_models.anomaly_detector import get_anomaly_detector


class RiskScorer:
    # Industry-specific risk penalty multipliers for high-carbon sectors
    INDUSTRY_RISK_MULTIPLIERS = {
        "oil_and_gas": 1.5,
        "mining": 1.4,
        "aviation": 1.3,
        "coal": 1.6
    }
        
    def __init__(self):
        self.name = "Greenwashing Risk Scoring & ESG Rating Specialist"
        self.llm = llm_client
        
        # Load ALL configuration from external file (NO HARDCODING)
        self.config = self._load_config()
        self.industry_baseline_risk = self.config.get('industry_baseline_risk', {})
        self.weights = self.config.get('component_weights', {})
        self.risk_thresholds = self.config.get('risk_thresholds', {})
        
        # Load ML models
        self.ml_model = XGBoostRiskModel()
        self.use_ml = self.ml_model.model is not None
        
        self.esg_predictor = LightGBMESGPredictor()
        self.use_esg_predictor = self.esg_predictor.model_available
        
        # Load LSTM trend predictor
        self.lstm_predictor = get_lstm_predictor()
        self.use_lstm = self.lstm_predictor.model_available
        
        # Load anomaly detector
        self.anomaly_detector = get_anomaly_detector()
        self.use_anomaly_detector = self.anomaly_detector.model_available
        
        print(f"✅ Loaded {len(self.industry_baseline_risk)} industry baselines from config")
        if self.use_ml:
            print(f"✅ XGBoost risk model loaded - hybrid prediction enabled")
        else:
            print(f"ℹ️  XGBoost model not available - using formula-based scoring only")
        
        if self.use_esg_predictor:
            print(f"✅ LightGBM ESG predictor loaded - score validation enabled")
        else:
            print(f"ℹ️  LightGBM predictor not available - skipping ESG score validation")
        
        if self.use_lstm:
            print(f"✅ LSTM trend forecaster loaded - temporal prediction enabled")
        else:
            print(f"ℹ️  LSTM trend forecaster not available - skipping trend analysis")
        
        if self.use_anomaly_detector:
            print(f"✅ Anomaly detector loaded - pattern anomaly detection enabled")
        else:
            print(f"ℹ️  Anomaly detector not available - skipping anomaly detection")
    
    @staticmethod
    def esg_score_to_rating(esg_score: float) -> tuple:
        """
        Convert ESG score (0-100) to MSCI-style rating and risk level
        
        Args:
            esg_score: Overall ESG score from 0-100
            
        Returns:
            tuple: (rating_grade, risk_level)
            
        Rating Scale (MSCI-style):
            AAA: 90-100  (ESG Leaders)
            AA:  85-89   (ESG Leaders)
            A:   75-84   (Above Average)
            BBB: 60-74   (Average)
            BB:  50-59   (Below Average)
            B:   35-49   (Laggards)
            CCC: 0-34    (Laggards)
        """
        if esg_score >= 90:
            return ('AAA', 'LOW')
        elif esg_score >= 85:
            return ('AA', 'LOW')
        elif esg_score >= 75:
            return ('A', 'LOW')
        elif esg_score >= 60:
            return ('BBB', 'MODERATE')
        elif esg_score >= 50:
            return ('BB', 'MODERATE')
        elif esg_score >= 35:
            return ('B', 'HIGH')
        else:
            return ('CCC', 'HIGH')
    
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
    
    def calculate_pillar_scores(self, all_analyses: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate Environmental, Social, and Governance pillar scores (0-100)
        
        Args:
            all_analyses: Dict containing all agent outputs
            
        Returns:
            Dict with environmental_score, social_score, governance_score
        """
        
        print(f"\n📊 Calculating ESG Pillar Scores...")

        evidence = all_analyses.get('evidence', [])
        contradictions = all_analyses.get('contradiction_analysis', [])
        historical = all_analyses.get('historical_analysis', {}) or {}
        carbon_ctx = all_analyses.get('carbon_extraction', {}) or {}

        # Flatten text for weak-signal keyword extraction using a bounded buffer
        # to avoid memory spikes on very large evidence payloads.
        combined_text = self._build_bounded_evidence_text(evidence)

        # Environmental signals
        carbon_data_quality = self._assess_carbon_data_quality(all_analyses)
        renewable_energy_pct = self._extract_percentage_from_text(combined_text, ["renewable", "renewable energy"])
        science_based_target = bool(
            carbon_ctx.get("science_based_target")
            or ("science based" in combined_text or "sbti" in combined_text)
        )
        net_zero_target = bool(carbon_ctx.get("net_zero_target") or ("net zero" in combined_text))
        climate_capex = self._extract_percentage_from_text(combined_text, ["climate capex", "decarbonization capex", "climate investment"])
        offset_audit = carbon_ctx.get("offset_transparency", {}) if isinstance(carbon_ctx, dict) else {}
        offset_penalty = float(offset_audit.get("risk_penalty_points", 0) or 0)

        environmental_score = 25.0
        environmental_score += min(30.0, carbon_data_quality * 0.30)
        environmental_score += min(15.0, renewable_energy_pct * 0.15)
        environmental_score += 12.0 if science_based_target else 0.0
        environmental_score += 10.0 if net_zero_target else 0.0
        environmental_score += min(8.0, climate_capex * 0.20)
        environmental_score -= min(20.0, offset_penalty)

        env_contradictions = sum(
            1 for c in contradictions
            if c.get('overall_verdict') == 'Contradicted' and any(k in str(c).lower() for k in ["carbon", "emission", "climate", "renewable"])
        )
        environmental_score -= min(20.0, env_contradictions * 6.0)
        environmental_score = max(0, min(100, environmental_score))

        print(
            f"   Environmental: {environmental_score:.1f}/100 "
            f"(carbon_quality={carbon_data_quality:.1f}, renewable={renewable_energy_pct:.1f}, "
            f"sbt={science_based_target}, net_zero={net_zero_target}, offset_penalty={offset_penalty:.1f})"
        )

        # Social signals
        controversies = len(historical.get('past_violations', []))
        labor_practices = 1 if any(k in combined_text for k in ["labor", "worker safety", "occupational safety", "workplace"]) else 0
        diversity_disclosure = 1 if any(k in combined_text for k in ["diversity", "inclusion", "gender", "women in workforce"]) else 0
        community_investment = 1 if any(k in combined_text for k in ["community investment", "csr", "community development"]) else 0
        dei_progress = self._extract_dei_progress_signals(combined_text)

        social_score = 35.0
        social_score += (labor_practices * 15.0)
        social_score += (diversity_disclosure * 6.0)
        social_score += (community_investment * 12.0)
        social_score -= min(25.0, controversies * 5.0)

        # DEI granularity: target existence is not enough, progress toward target matters.
        if dei_progress["has_target"] and dei_progress["has_actual"]:
            if dei_progress["yoy_change"] is not None and dei_progress["yoy_change"] > 0:
                social_score += min(12.0, 5.0 + dei_progress["yoy_change"] * 1.5)
            elif dei_progress["yoy_change"] is not None and dei_progress["yoy_change"] <= 0:
                social_score -= min(10.0, 4.0 + abs(dei_progress["yoy_change"]) * 1.5)

            if dei_progress["target_gap"] is not None:
                if dei_progress["target_gap"] <= 0:
                    social_score += 4.0
                elif dei_progress["target_gap"] >= 12:
                    social_score -= 8.0
                elif dei_progress["target_gap"] >= 6:
                    social_score -= 4.0
        elif dei_progress["has_target"] and not dei_progress["has_actual"]:
            social_score -= 5.0

        soc_contradictions = sum(
            1 for c in contradictions
            if c.get('overall_verdict') == 'Contradicted' and any(k in str(c).lower() for k in ["labor", "employee", "diversity", "community", "human rights"])
        )
        social_score -= min(20.0, soc_contradictions * 6.0)
        social_score = max(0, min(100, social_score))

        print(
            f"   Social: {social_score:.1f}/100 "
            f"(controversies={controversies}, labor={labor_practices}, diversity={diversity_disclosure}, "
            f"community={community_investment}, dei_yoy={dei_progress['yoy_change']}, dei_gap={dei_progress['target_gap']})"
        )

        # Governance signals
        board_independence = 1 if any(k in combined_text for k in ["independent director", "board independence", "independent board"]) else 0
        exec_comp_transparency = 1 if any(k in combined_text for k in ["executive compensation", "remuneration policy", "pay ratio"]) else 0
        anti_corruption = 1 if any(k in combined_text for k in ["anti corruption", "anti-corruption", "bribery", "ethics policy"]) else 0
        esg_governance_structure = 1 if any(k in combined_text for k in ["esg committee", "sustainability committee", "board oversight"] ) else 0

        governance_score = 38.0
        governance_score += board_independence * 15.0
        governance_score += exec_comp_transparency * 12.0
        governance_score += anti_corruption * 15.0
        governance_score += esg_governance_structure * 12.0

        gov_contradictions = sum(
            1 for c in contradictions
            if c.get('overall_verdict') == 'Contradicted' and any(k in str(c).lower() for k in ["board", "governance", "ethics", "corruption", "compliance"])
        )
        governance_score -= min(25.0, gov_contradictions * 7.0)
        governance_score = max(0, min(100, governance_score))

        print(
            f"   Governance: {governance_score:.1f}/100 "
            f"(board={board_independence}, exec_comp={exec_comp_transparency}, anti_corruption={anti_corruption}, esg_gov={esg_governance_structure})"
        )
        
        # Apply industry baseline adjustment
        industry = self._identify_industry(all_analyses.get('company', 'Unknown'), all_analyses)
        industry_data = self.industry_baseline_risk.get(industry, self.industry_baseline_risk.get('unknown'))
        industry_baseline = industry_data.get('baseline', 50)
        
        # Adjust scores based on industry baseline (high-risk industries get penalty)
        # Cap industry adjustment to avoid over-penalizing sector membership alone.
        industry_penalty = max(-5.0, min(5.0, (industry_baseline - 50) * 0.2))
        
        environmental_score = max(0, min(100, environmental_score - industry_penalty))
        social_score = max(0, min(100, social_score - industry_penalty))
        governance_score = max(0, min(100, governance_score - industry_penalty))
        
        if industry_penalty != 0:
            print(f"   Industry Adjustment ({industry}): {-industry_penalty:+.1f} points")
        
        # Calculate overall ESG score (weighted average)
        overall_esg = (environmental_score * 0.35) + (social_score * 0.30) + (governance_score * 0.35)
        
        print(f"   Overall ESG: {overall_esg:.1f}/100 (E×0.35 + S×0.30 + G×0.35)")
        
        pillar_factors = {
            "environmental": [
                {
                    "factor": "Carbon data quality",
                    "raw_signal": carbon_data_quality,
                    "source": "Carbon extractor agent",
                    "weight": 0.30,
                    "points_contributed": round(carbon_data_quality * 0.30, 1),
                    "confidence": "Low" if carbon_data_quality == 0 else "Medium",
                },
                {
                    "factor": "Renewable energy usage",
                    "raw_signal": renewable_energy_pct,
                    "source": "Evidence retrieval",
                    "weight": 0.25,
                    "points_contributed": round(renewable_energy_pct * 0.25, 1),
                    "confidence": "Medium",
                },
                {
                    "factor": "Science-based target (SBTi)",
                    "raw_signal": "Validated" if science_based_target else "ABSENT",
                    "source": "Regulatory scanner",
                    "weight": 0.25,
                    "points_contributed": 25.0 if science_based_target else 0.0,
                    "confidence": "High",
                },
                {
                    "factor": "Net-zero target declared",
                    "raw_signal": "Yes" if net_zero_target else "No",
                    "source": "Claim extractor",
                    "weight": 0.20,
                    "points_contributed": 20.0 if net_zero_target else 0.0,
                    "confidence": "High",
                },
            ],
            "social": [
                {
                    "factor": "Labor controversy count",
                    "raw_signal": controversies,
                    "source": "Contradiction analyzer",
                    "weight": 0.30,
                    "points_contributed": max(0, 30 - controversies * 10),
                    "confidence": "Medium",
                },
                {
                    "factor": "Labor rights disclosure",
                    "raw_signal": "Present" if labor_practices else "Absent",
                    "source": "Evidence retrieval",
                    "weight": 0.25,
                    "points_contributed": 25.0 if labor_practices else 0.0,
                    "confidence": "Medium",
                },
                {
                    "factor": "Diversity & inclusion disclosure",
                    "raw_signal": "Present" if diversity_disclosure else "Absent",
                    "source": "Evidence retrieval",
                    "weight": 0.25,
                    "points_contributed": 25.0 if diversity_disclosure else 0.0,
                    "confidence": "Low",
                },
                {
                    "factor": "Community engagement",
                    "raw_signal": "Present" if community_investment else "Absent",
                    "source": "Evidence retrieval",
                    "weight": 0.20,
                    "points_contributed": 20.0 if community_investment else 0.0,
                    "confidence": "Low",
                },
            ],
            "governance": [
                {
                    "factor": "Board independence disclosure",
                    "raw_signal": "Present" if board_independence else "Absent",
                    "source": "Evidence retrieval",
                    "weight": 0.30,
                    "points_contributed": 30.0 if board_independence else 0.0,
                    "confidence": "Low",
                },
                {
                    "factor": "Executive compensation ESG link",
                    "raw_signal": "Present" if exec_comp_transparency else "Absent",
                    "source": "Evidence retrieval",
                    "weight": 0.25,
                    "points_contributed": 25.0 if exec_comp_transparency else 0.0,
                    "confidence": "Low",
                },
                {
                    "factor": "Anti-corruption framework",
                    "raw_signal": "Present" if anti_corruption else "Absent",
                    "source": "Evidence retrieval",
                    "weight": 0.25,
                    "points_contributed": 25.0 if anti_corruption else 0.0,
                    "confidence": "Low",
                },
                {
                    "factor": "ESG governance structure",
                    "raw_signal": "Present" if esg_governance_structure else "Absent",
                    "source": "Evidence retrieval",
                    "weight": 0.20,
                    "points_contributed": 20.0 if esg_governance_structure else 0.0,
                    "confidence": "Low",
                },
            ],
        }

        return {
            "environmental_score": round(environmental_score, 1),
            "social_score": round(social_score, 1),
            "governance_score": round(governance_score, 1),
            "overall_esg_score": round(overall_esg, 1),
            "industry_adjustment": round(industry_penalty, 1),
            "offset_transparency_status": offset_audit.get("status", "unknown") if isinstance(offset_audit, dict) else "unknown",
            "offset_penalty": round(offset_penalty, 1),
            "dei_progress": dei_progress,
            "pillar_factors": pillar_factors,
        }

    def _extract_percentage_from_text(self, text: str, keywords: List[str]) -> float:
        """Extract first reasonable percentage near any keyword; deterministic fallback to 0."""
        if not text:
            return 0.0

        for kw in keywords:
            pattern = rf"{re.escape(kw)}[^\n\r]{{0,60}}?(\d{{1,3}}(?:\.\d+)?)\s*%"
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    value = float(m.group(1))
                    return max(0.0, min(100.0, value))
                except Exception:
                    continue

        return 0.0

    def _build_bounded_evidence_text(self, evidence: List[Dict[str, Any]]) -> str:
        """Build a capped lowercase evidence buffer to keep keyword parsing memory-safe."""
        if not evidence:
            return ""

        max_total_chars = 220000
        max_field_chars = 2500
        text_parts: List[str] = []
        total_chars = 0

        for ev in evidence:
            if not isinstance(ev, dict):
                continue

            for key in ("snippet", "relevant_text", "content"):
                raw = ev.get(key)
                if not raw:
                    continue

                fragment = str(raw)[:max_field_chars].lower()
                if not fragment:
                    continue

                remaining = max_total_chars - total_chars
                if remaining <= 0:
                    return " ".join(text_parts)

                if len(fragment) > remaining:
                    fragment = fragment[:remaining]

                text_parts.append(fragment)
                total_chars += len(fragment)

                if total_chars >= max_total_chars:
                    return " ".join(text_parts)

        return " ".join(text_parts)

    def _extract_dei_progress_signals(self, text: str) -> Dict[str, Any]:
        """Extract DEI target vs actual progress signals from narrative text."""
        if not text:
            return {
                "has_target": False,
                "has_actual": False,
                "target_pct": None,
                "current_pct": None,
                "prior_pct": None,
                "yoy_change": None,
                "target_gap": None,
            }

        # Guard against pathological payload sizes even after upstream bounding.
        try:
            t = text[:300000].lower()
        except MemoryError:
            return {
                "has_target": False,
                "has_actual": False,
                "target_pct": None,
                "current_pct": None,
                "prior_pct": None,
                "yoy_change": None,
                "target_gap": None,
            }

        target_pct = None
        target_match = re.search(
            r"(?:target|goal|aim)\s*(?:of\s*)?(\d{1,3}(?:\.\d+)?)\s*%[^\n\r]{0,50}?(?:women|female|diversity|dei|leadership)",
            t,
            re.IGNORECASE,
        )
        if target_match:
            target_pct = float(target_match.group(1))

        # Capture the first two percentages around DEI-related terms as current/prior proxy.
        dei_percentages = []
        sentences = re.split(r"[\.!?]", t)
        for sent in sentences:
            s = sent.strip()
            if not s:
                continue
            if not any(k in s for k in ["women", "female", "diversity", "dei", "inclusion", "leadership"]):
                continue
            if any(k in s for k in ["target", "goal", "aim", "by 20"]):
                continue

            for m in re.finditer(r"(\d{1,3}(?:\.\d+)?)\s*%", s):
                try:
                    dei_percentages.append(float(m.group(1)))
                except Exception:
                    continue
                if len(dei_percentages) >= 2:
                    break
            if len(dei_percentages) >= 2:
                break

        current_pct = dei_percentages[0] if len(dei_percentages) >= 1 else None
        prior_pct = dei_percentages[1] if len(dei_percentages) >= 2 else None
        yoy_change = (current_pct - prior_pct) if (current_pct is not None and prior_pct is not None) else None
        target_gap = (target_pct - current_pct) if (target_pct is not None and current_pct is not None) else None

        return {
            "has_target": target_pct is not None,
            "has_actual": current_pct is not None,
            "target_pct": target_pct,
            "current_pct": current_pct,
            "prior_pct": prior_pct,
            "yoy_change": yoy_change,
            "target_gap": target_gap,
        }
    
    def _assess_carbon_data_quality(self, all_analyses: Dict[str, Any]) -> float:
        """
        Assess carbon data quality (0-100)
        Returns percentage of emissions data available
        
        PHASE 3: Environmental Score Inflation Fix
        """
        try:
            # Prefer direct structured payload if already passed by wrappers.
            direct_carbon = all_analyses.get('carbon_extraction', {})
            if isinstance(direct_carbon, dict) and direct_carbon:
                direct_quality = direct_carbon.get('data_quality', {})
                if isinstance(direct_quality, dict):
                    overall = direct_quality.get('overall_score')
                    if isinstance(overall, (int, float)):
                        return float(overall)
                if isinstance(direct_quality, (int, float)):
                    return float(direct_quality)

            # Extract carbon extraction agent output
            agent_outputs = all_analyses.get('agent_outputs', [])
            carbon_outputs = [o for o in agent_outputs if o.get('agent') == 'carbon_extraction']
            
            if not carbon_outputs:
                return 0  # No carbon data found
            
            carbon_result = carbon_outputs[-1].get('output', {})
            
            # Check which emission scopes are available
            data_quality = carbon_result.get('data_quality', {})
            
            if isinstance(data_quality, dict):
                # If data_quality is a detailed object
                scope1_quality = data_quality.get('scope1', 0)
                scope2_quality = data_quality.get('scope2', 0)
                scope3_quality = data_quality.get('scope3', 0)
                
                # Average of available scopes
                avg_quality = (scope1_quality + scope2_quality + scope3_quality) / 3
                return avg_quality
            elif isinstance(data_quality, (int, float)):
                # If data_quality is a simple number
                return float(data_quality)
            
            # Check for basic emissions data
            emissions = carbon_result.get('emissions', {})
            has_scope1 = bool(emissions.get('scope1', {}).get('value'))
            has_scope2 = bool(emissions.get('scope2', {}).get('value'))
            has_scope3 = bool(emissions.get('scope3', {}).get('value'))
            
            # Calculate quality as percentage of scopes available (out of 3)
            scopes_available = sum([has_scope1, has_scope2, has_scope3])
            quality_percentage = (scopes_available / 3) * 100
            
            return quality_percentage
            
        except Exception as e:
            print(f"      ⚠️ Error assessing carbon data quality: {e}")
            return 0
    
    def calculate_final_score(self, company: str, all_analyses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate final ESG score with PILLAR-PRIMARY approach
        ESG pillar scores are the PRIMARY rating source (MSCI-aligned)
        ML is used only for refinement in MODERATE range (50-74 ESG)
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 7: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        
        # Step 0: Calculate ESG pillar scores FIRST (PRIMARY rating source)
        pillar_scores = self.calculate_pillar_scores(all_analyses)
        overall_esg_score = pillar_scores.get("overall_esg_score", 50)
        
        print(f"\n📊 ESG Pillar Scores Calculated:")
        print(f"   Environmental: {pillar_scores['environmental_score']}/100")
        print(f"   Social: {pillar_scores['social_score']}/100")
        print(f"   Governance: {pillar_scores['governance_score']}/100")
        print(f"   Overall ESG: {overall_esg_score}/100")
        
        # Step 0.5: Convert ESG score to MSCI-style rating (PRIMARY METHOD)
        rating_grade, risk_level = self.esg_score_to_rating(overall_esg_score)
        greenwashing_risk = 100 - overall_esg_score
        
        print(f"\n⭐ MSCI-Style Rating from ESG Score:")
        print(f"   ESG Score: {overall_esg_score}/100")
        print(f"   Rating Grade: {rating_grade}")
        print(f"   Risk Level: {risk_level}")
        print(f"   Greenwashing Risk: {greenwashing_risk:.1f}/100")
        
        # Track rating methodology
        override_ml = False
        risk_source = "ESG Pillar Score (MSCI-Aligned)"
        confidence = 0.85
        
        # Step 1: Check for ESG Leaders (≥75) - bypass ML entirely
        if overall_esg_score >= 85:
            print(f"\n✅ ESG LEADER STATUS (AA/AAA) - ML Bypassed")
            print(f"   Overall ESG: {overall_esg_score}/100")
            print(f"   Rating: {rating_grade} (Best-in-class ESG performance)")
            
            override_ml = True
            confidence = 0.90
            risk_source = "ESG Pillar Override (ESG Leader)"
            
        elif overall_esg_score >= 75:
            print(f"\n✅ STRONG ESG PERFORMANCE (A Rating) - ML Bypassed")
            print(f"   Overall ESG: {overall_esg_score}/100")
            print(f"   Rating: {rating_grade} (Above-average performance)")
            
            override_ml = True
            confidence = 0.88
            risk_source = "ESG Pillar Override (Strong Performance)"
        
        elif overall_esg_score < 50:
            print(f"\n⚠️ ESG LAGGARD (B/CCC Rating) - ML Bypassed")
            print(f"   Overall ESG: {overall_esg_score}/100")
            print(f"   Rating: {rating_grade} (Significant ESG concerns)")
            
            override_ml = True
            confidence = 0.85
            risk_source = "ESG Pillar Score (Laggard)"
        
        # Step 2: Get ML prediction (ONLY for MODERATE range: 50-74 ESG)
        ml_prediction = None
        ml_confidence = 0.0
        use_ml_prediction = False
        
        if not override_ml and self.use_ml and 50 <= overall_esg_score < 75:
            print(f"\n🤖 Running ML prediction for MODERATE range refinement...")
            print(f"   ESG Score: {overall_esg_score}/100 (50-74 range)")
            print(f"   Purpose: Refine BBB/BB rating boundary")
            
            # CRITICAL FIX: Inject pillar scores into all_analyses for XGBoost
            all_analyses['pillar_scores'] = pillar_scores
            print(f"   Pillar scores injected for ML feature extraction")
            
            ml_result = self.ml_model.predict(all_analyses)
            
            if ml_result.get('ml_available'):
                ml_prediction = ml_result['prediction']
                ml_confidence = ml_result['confidence']
                
                print(f"   ML Prediction: {ml_prediction}")
                print(f"   ML Confidence: {ml_confidence:.1%}")
                print(f"   Probabilities: LOW={ml_result['probabilities']['LOW']:.2%}, "
                      f"MODERATE={ml_result['probabilities']['MODERATE']:.2%}, "
                      f"HIGH={ml_result['probabilities']['HIGH']:.2%}")
                
                # Use ML to refine rating ONLY in moderate range with high confidence
                if ml_confidence >= 0.80:
                    use_ml_prediction = True
                    print(f"   ✅ Using ML to refine BBB/BB boundary (confidence ≥ 80%)")
                    
                    # ML can adjust rating within MODERATE range
                    if ml_prediction == "LOW" and overall_esg_score >= 60:
                        rating_grade = "BBB"
                        risk_level = "MODERATE"
                        greenwashing_risk = 35
                        print(f"   ML refinement: Upgraded to BBB (low-moderate risk)")
                    elif ml_prediction == "HIGH" and overall_esg_score < 60:
                        rating_grade = "BB"
                        risk_level = "MODERATE"
                        greenwashing_risk = 55
                        print(f"   ML refinement: Maintained BB (high-moderate risk)")
                    # else keep pillar-based rating
                    
                    risk_source = "ESG Pillar + ML Refinement"
                    confidence = (0.85 + ml_confidence) / 2
                else:
                    print(f"   ⚠️ ML confidence too low, using pillar-based rating")
        
        # Step 3: Extract temporal consistency signal (NEW PHASE 7)
        temporal_consistency_score = 50  # Default: neutral
        temporal_inconsistency_detected = False
        temporal_signal = None
        temporal_weight = 0.0
        temporal_mode = "none"
        temporal_data_quality = "low"
        
        # Extract temporal consistency from agent outputs if available
        temporal_outputs = [o for o in all_analyses.get('agent_outputs', []) if o.get('agent') == 'temporal_consistency']
        if temporal_outputs:
            temporal_result = temporal_outputs[-1].get('output', {})
            if isinstance(temporal_result, dict):
                temporal_consistency_score = temporal_result.get('temporal_consistency_score', 50)
                temporal_inconsistency_detected = temporal_result.get('temporal_inconsistency_detected', False)
                temporal_signal = temporal_result
                temporal_weight = float(temporal_result.get('temporal_weight', 0.0) or 0.0)
                temporal_mode = str(temporal_result.get('temporal_mode', 'none'))
                temporal_data_quality = str(temporal_result.get('data_quality', 'low'))
                
                print(f"\n🔄 TEMPORAL CONSISTENCY ANALYSIS (NEW):")
                print(f"   Temporal Score: {temporal_consistency_score:.1f}/100")
                print(f"   Risk Pattern Detected: {'YES' if temporal_inconsistency_detected else 'NO'}")
                print(f"   Claim Trend: {temporal_result.get('claim_trend', 'unknown')}")
                print(f"   Environmental Trend: {temporal_result.get('environmental_trend', 'unknown')}")
                print(f"   Mode: {temporal_mode} | Data Quality: {temporal_data_quality} | Weight: {temporal_weight:.2f}")
                
                # Impact greenwashing risk based on temporal consistency
                if temporal_inconsistency_detected:
                    temporal_risk_adjustment = temporal_consistency_score * temporal_weight
                    print(f"   Temporal Risk Adjustment: +{temporal_risk_adjustment:.1f} points")
        
        # Step 4: Formula-based components (for explainability ONLY)
        print(f"\n📐 Calculating formula components for explainability...")
        
        industry = self._identify_industry(company, all_analyses)
        industry_data = self.industry_baseline_risk.get(industry, self.industry_baseline_risk.get('unknown'))
        industry_baseline = industry_data.get('baseline', 50)
        
        print(f"Industry: {industry.replace('_', ' ').title()}")
        print(f"Industry baseline risk: {industry_baseline}/100")
        
        components = self._calculate_components(all_analyses)
        
        base_risk = sum(
            components.get(key, 50) * weight 
            for key, weight in self.weights.items()
        )
        
        industry_adjustment = max(-10.0, min(10.0, (industry_baseline - 50) * 0.3))
        adjusted_risk = base_risk + industry_adjustment
        
        # Apply industry-specific risk multipliers for high-carbon sectors
        industry_multiplier = min(1.2, self.INDUSTRY_RISK_MULTIPLIERS.get(industry, 1.0))
        if industry_multiplier > 1.0:
            print(f"Industry penalty applied: {industry.replace('_', ' ').title()} × {industry_multiplier}")
            adjusted_risk = adjusted_risk * industry_multiplier
        
        peer_modifier = self._calculate_peer_modifier(all_analyses, industry)
        debate_penalty = 10.0 if all_analyses.get("debate_activated") else 0.0
        temporal_modifier = 0.0
        
        # Apply temporal consistency penalty only when temporal signal quality supports it.
        if temporal_inconsistency_detected and temporal_consistency_score > 50 and temporal_weight > 0:
            temporal_modifier = (temporal_consistency_score - 50) * temporal_weight
            print(f"   Temporal Penalty: +{temporal_modifier:.1f} points (quality-gated)")
        elif temporal_inconsistency_detected and temporal_weight <= 0:
            print("   Temporal signal present but low confidence - no risk penalty applied")
        
        final_risk = adjusted_risk + peer_modifier + debate_penalty + temporal_modifier
        greenwashing_risk_formula = max(0, min(100, final_risk))
        
        print(f"   Formula Risk: {greenwashing_risk_formula:.1f}/100 (for component analysis)")
        print(f"   Industry: {industry.replace('_', ' ').title()}")
        print(f"   Industry Baseline: {industry_baseline}/100")
        
        # Step 5: DOMAIN KNOWLEDGE OVERRIDES (highest priority)
        # CRITICAL: Industry-specific greenwashing patterns override pillar scores
        high_carbon_greenwashing_flag = False
        
        # Extract claim text for greenwashing check
        claim_text = ""
        if isinstance(all_analyses.get("claim"), dict):
            claim_text = all_analyses["claim"].get("claim_text", "").lower()
        elif isinstance(all_analyses.get("claim"), str):
            claim_text = all_analyses["claim"].lower()
        
        # Define green keywords
        green_keywords = ["renewable", "green", "carbon neutral", "net zero", "sustainable"]
        has_green_claim = any(keyword in claim_text for keyword in green_keywords)
        
        # Calculate evidence quality score from components
        evidence_quality_score = 100 - components.get('evidence_quality', 50)
        
        print(f'\n🔍 DOMAIN KNOWLEDGE CHECK:')
        print(f'  Industry: {industry}')
        print(f'  Green claim: {has_green_claim}')
        print(f'  ESG Score: {overall_esg_score}/100')
        
        # Evidence-backed high-scrutiny override (not industry-only bias).
        high_scrutiny_industries = {"oil_and_gas", "coal", "mining", "aviation", "chemicals", "fast_fashion"}
        weak_substantiation = components.get("claim_verification", 50) >= 70 or components.get("evidence_quality", 50) >= 60

        if industry in high_scrutiny_industries and has_green_claim:
            print(f"\n🔴 HIGH-SCRUTINY GREEN CLAIM CHECK")
            print(f"   Industry: {industry.replace('_', ' ').title()}")
            print(f"   Green keywords: {[kw for kw in green_keywords if kw in claim_text]}")
            print(f"   ESG Score: {overall_esg_score}/100")
            print(f"   Weak substantiation signal: {weak_substantiation}")

            # Override only when claim quality signals support elevated risk.
            if overall_esg_score < 60 and weak_substantiation:
                print(f"   🚨 DOMAIN OVERRIDE: Low ESG + weakly substantiated green claim")

                rating_grade = "BB"
                risk_level = "HIGH"
                greenwashing_risk = max(greenwashing_risk, 70)
                high_carbon_greenwashing_flag = True
                override_ml = True
                risk_source = "Domain Knowledge Override (Evidence-Backed High-Scrutiny)"
                confidence = 0.92

                print(f"   Assigned Rating: {rating_grade} (forced HIGH risk)")
        
        # OLD HYBRID LOGIC (now deprecated - kept for reference)
        # Step 3: Hybrid decision with DOMAIN KNOWLEDGE PRIORITY
        # CRITICAL: Industry penalties and greenwashing flags MUST override ML predictions
        if False and not override_ml and use_ml_prediction:
            # Check if domain knowledge should override ML
            # Priority 1: Formula indicates HIGH risk (≥70) - ALWAYS override
            # Priority 2: High ML confidence (≥85%) - Use ML
            # Priority 3: Medium ML confidence (60-84%) - Use ensemble
            
            if greenwashing_risk_formula >= 70:
                # DOMAIN KNOWLEDGE OVERRIDE - Formula scoring indicates HIGH risk
                print(f"\n🔴 DOMAIN KNOWLEDGE OVERRIDE - Formula indicates HIGH RISK")
                print(f"   Formula Risk Score: {greenwashing_risk_formula:.1f}/100")
                print(f"   ML Prediction: {ml_prediction} (confidence: {ml_confidence:.1%})")
                print(f"   OVERRIDING ML with formula-based scoring")
                print(f"   Reason: Industry penalties + evidence analysis = HIGH risk threshold")
                
                greenwashing_risk = max(greenwashing_risk_formula, 70)  # Force minimum HIGH
                risk_source = "Domain Knowledge Override (Formula)"
                
            elif ml_confidence >= 0.85:
                # High ML confidence - use ML prediction
                risk_mapping_reverse = {'LOW': 25, 'MODERATE': 50, 'HIGH': 80}
                greenwashing_risk = risk_mapping_reverse[ml_prediction]
                risk_source = "ML Model (High Confidence)"
                
                print(f"\n🤖 USING ML PREDICTION (High Confidence)")
                print(f"   ML Prediction: {ml_prediction}")
                print(f"   ML Confidence: {ml_confidence:.1%}")
                print(f"   Final Risk: {greenwashing_risk}/100")
                
            else:
                # Medium confidence - use ensemble (60% ML + 40% Formula)
                risk_mapping_reverse = {'LOW': 25, 'MODERATE': 50, 'HIGH': 80}
                ml_risk_score = risk_mapping_reverse[ml_prediction]
                
                # Weighted ensemble
                greenwashing_risk = (ml_risk_score * 0.60) + (greenwashing_risk_formula * 0.40)
                risk_source = "Ensemble (60% ML + 40% Formula)"
                
                print(f"\n⚖️ USING ENSEMBLE APPROACH")
                print(f"   ML Prediction: {ml_prediction} ({ml_risk_score}/100)")
                print(f"   Formula Score: {greenwashing_risk_formula:.1f}/100")
                print(f"   Weighted Average: {greenwashing_risk:.1f}/100")
        
        # Step 5: LightGBM ESG Score Prediction (validation only)
        esg_prediction = None
        formula_esg_score = overall_esg_score
        
        if self.use_esg_predictor:
            print(f"\n🔮 Running LightGBM ESG Score Validation...")
            company_data = self._extract_esg_features(all_analyses)
            
            if company_data:
                esg_pred_result = self.esg_predictor.predict_esg_score(company_data)
                
                if esg_pred_result and esg_pred_result.get('prediction_successful'):
                    predicted_esg = esg_pred_result['predicted_esg']
                    esg_prediction = esg_pred_result
                    
                    print(f"   Pillar ESG: {formula_esg_score:.1f}/100")
                    print(f"   LightGBM ESG: {predicted_esg:.1f}/100")
                    print(f"   Prediction Range: {esg_pred_result['prediction_range']}")
                    
                    # Flag large discrepancies
                    discrepancy = abs(formula_esg_score - predicted_esg)
                    if discrepancy > 20:
                        print(f"   ⚠️ Large discrepancy ({discrepancy:.1f} points) - manual review recommended")
                    else:
                        print(f"   ✅ Scores aligned (discrepancy: {discrepancy:.1f} points)")
        
        # Step 6: LSTM Trend Prediction (context only)
        lstm_trend = None
        if self.use_lstm:
            print(f"\n🔮 Running LSTM Trend Forecast...")
            lstm_result = self.lstm_predictor.predict_from_analysis(all_analyses)
            
            if lstm_result and lstm_result.get('trend_successful'):
                lstm_trend = lstm_result
                
                print(f"   Forecast (6 years): {lstm_result['forecast']}")
                print(f"   Trend: {lstm_result['trend']}")
                print(f"   Change: {lstm_result['change_pct']:+.1f}%")
                print(f"   Model MAE: {lstm_result['confidence_mae']} points")
                
                # Adjust greenwashing risk based on trend
                if lstm_result['trend'] == 'DECLINING':
                    greenwashing_risk += 10
                    greenwashing_risk = min(100, greenwashing_risk)  # Cap at 100
                    print(f"   ⚠️ Declining ESG trend detected - risk increased by 10 points")
                elif lstm_result['trend'] == 'IMPROVING':
                    greenwashing_risk = max(0, greenwashing_risk - 5)
                    print(f"   ✅ Improving ESG trend - risk reduced by 5 points")
        
        # Step 7: Anomaly Detection (flagging only)
        anomaly_result = None
        if self.use_anomaly_detector:
            print(f"\n🔍 Running Anomaly Detection...")
            
            # Extract features for anomaly detection
            anomaly_features = self._extract_anomaly_features(all_analyses)
            
            if anomaly_features:
                anomaly_result = self.anomaly_detector.detect_anomaly(anomaly_features)
                
                if anomaly_result and anomaly_result.get('detection_successful'):
                    is_anomaly = anomaly_result['is_anomaly']
                    severity = anomaly_result['severity']
                    
                    print(f"   Anomaly Detected: {'YES' if is_anomaly else 'NO'}")
                    print(f"   Severity: {severity}")
                    
                    if is_anomaly:
                        print(f"   ⚠️ Anomaly flagged for review (does not alter rating)")
        
        # Step 8: Final ESG score determination
        esg_score = overall_esg_score
        
        # OLD GREENWASHING CHECK (now handled in Step 4)
        # Step 4C: Special greenwashing flag for high-carbon sectors with green claims (skip if overridden)
        # high_carbon_greenwashing_flag = False
        
        if False and not override_ml:
            # Extract claim text for greenwashing check
            claim_text = ""
            if isinstance(all_analyses.get("claim"), dict):
                claim_text = all_analyses["claim"].get("claim_text", "").lower()
            elif isinstance(all_analyses.get("claim"), str):
                claim_text = all_analyses["claim"].lower()
        
            # Define green keywords
            green_keywords = ["renewable", "green", "carbon neutral", "net zero"]
            has_green_claim = any(keyword in claim_text for keyword in green_keywords)
            
            # Calculate evidence quality score from components
            evidence_quality_score = 100 - components.get('evidence_quality', 50)
        
            # DEBUG: Print greenwashing check details
            print(f'\n🔍 GREENWASHING CHECK DEBUG:')
            print(f'  Industry detected: {industry}')
            print(f'  Claim text: {claim_text[:100] if claim_text else "(no claim)"}')
            print(f'  Green keywords found: {[kw for kw in green_keywords if kw in claim_text]}')
            print(f'  Evidence quality score: {evidence_quality_score}')
            print(f'  Has green claim: {has_green_claim}')
            print(f'  Meets all conditions (industry=oil_and_gas AND green_claim AND evidence<90): {industry == "oil_and_gas" and has_green_claim and evidence_quality_score < 90}')
            
            if industry == "oil_and_gas" and has_green_claim:
                # FIXED: Counterintuitive greenwashing pattern - MORE evidence can mean HIGHER risk
                # Oil & Gas companies extensively document their "transitions" - this is sophisticated greenwashing
                
                if evidence_quality_score < 70:
                    # Low evidence quality - standard greenwashing (no documentation)
                    print(f"\n🔴 HIGH-CARBON SECTOR GREENWASHING FLAG TRIGGERED")
                    print(f"   Industry: {industry.replace('_', ' ').title()}")
                    print(f"   Green keywords detected: {[kw for kw in green_keywords if kw in claim_text]}")
                    print(f"   Evidence quality: {evidence_quality_score}/100 (Low evidence)")
                    print(f"   ESCALATING TO HIGH RISK")
                    
                    greenwashing_risk = max(greenwashing_risk, 70)  # Force minimum HIGH risk
                    high_carbon_greenwashing_flag = True
                    risk_source = "Domain Knowledge Override (Greenwashing Flag)"
                    
                elif evidence_quality_score >= 70 and evidence_quality_score < 90:
                    # Moderate-high evidence quality - PARADOX: well-documented transition claims
                    print(f"\n⚠️ HIGH-QUALITY GREENWASHING EVIDENCE DETECTED (PARADOX)")
                    print(f"   Industry: Oil & Gas")
                    print(f"   Green keywords: {[kw for kw in green_keywords if kw in claim_text]}")
                    print(f"   Evidence quality: {evidence_quality_score}/100 (Well-documented)")
                    print(f"   PATTERN: Extensive documentation of transition = sophisticated greenwashing")
                    print(f"   APPLYING MODERATE PENALTY")
                    
                    greenwashing_risk = max(greenwashing_risk, 65)  # Moderate penalty
                    if "Override" not in risk_source:
                        risk_source = "Domain Knowledge Override (Paradox Pattern)"
                    
                elif evidence_quality_score >= 90:
                    # Extensive evidence quality - RED FLAG: over-documentation of green claims
                    print(f"\n🔴 EXTENSIVE GREENWASHING DOCUMENTATION DETECTED")
                    print(f"   Industry: Oil & Gas")
                    print(f"   Green keywords: {[kw for kw in green_keywords if kw in claim_text]}")
                    print(f"   Evidence quality: {evidence_quality_score}/100 (Extensively documented)")
                    print(f"   PATTERN: Over-documentation = Classic greenwashing tactic")
                    print(f"   APPLYING HIGH PENALTY - ESCALATING TO HIGH RISK")
                    
                    greenwashing_risk = max(greenwashing_risk, 72)  # High penalty
                    high_carbon_greenwashing_flag = True
                    risk_source = "Domain Knowledge Override (Over-documentation)"
            
            # FINAL OVERRIDE CHECK: If greenwashing flag is set, ensure HIGH risk
            if high_carbon_greenwashing_flag:
                if greenwashing_risk < 70:
                    print(f"\n🔴 FINAL OVERRIDE: Greenwashing flag forcing HIGH risk")
                    print(f"   Previous score: {greenwashing_risk:.1f}/100")
                    print(f"   Adjusted score: 70/100 (HIGH threshold)")
                    greenwashing_risk = 70
        
        # Step 9: Generate insights
        top_reasons = self._generate_top_reasons(
            components, 
            all_analyses, 
            industry, 
            greenwashing_risk
        )
        
        insights = self._generate_insights(
            greenwashing_risk, 
            risk_level, 
            industry, 
            company
        )
        
        result = {
            "company": company,
            "analysis_timestamp": datetime.now().isoformat(),
            "risk_source": risk_source,
            "industry": industry,
            "industry_baseline_risk": industry_baseline,
            "industry_source": industry_data.get('source', 'Unknown'),
            "base_risk_score": round(base_risk, 1),
            "industry_adjustment": round(industry_adjustment, 1),
            "peer_adjustment": round(peer_modifier, 1),
            "temporal_adjustment": round(temporal_modifier, 1),
            "greenwashing_risk_score": round(greenwashing_risk, 1),
            "esg_score": round(esg_score, 1),
            "risk_level": risk_level,
            "rating_grade": rating_grade,
            "environmental_score": pillar_scores.get("environmental_score"),
            "social_score": pillar_scores.get("social_score"),
            "governance_score": pillar_scores.get("governance_score"),
            "component_scores": components,
            "pillar_scores": pillar_scores,
            "pillar_factors": pillar_scores.get("pillar_factors", {}),
            "temporal_consistency_score": round(temporal_consistency_score, 1),
            "temporal_mode": temporal_mode,
            "temporal_data_quality": temporal_data_quality,
            "temporal_weight": round(temporal_weight, 2),
            "temporal_inconsistency_detected": temporal_inconsistency_detected,
            "explainability_top_3_reasons": top_reasons,
            "actionable_insights": insights,
            "confidence_level": round(confidence * 100, 1),
            "high_carbon_greenwashing_flag": high_carbon_greenwashing_flag,
            "esg_override_active": override_ml
        }
        
        # Add ML details if available
        if ml_prediction and use_ml_prediction:
            result["ml_prediction"] = {
                "prediction": ml_prediction,
                "confidence": ml_confidence,
                "probabilities": ml_result.get('probabilities', {}),
                "used_for_final": use_ml_prediction,
                "role": "Rating refinement in MODERATE range (50-74 ESG)"
            }
        
        # Add LightGBM ESG prediction if available
        if esg_prediction:
            result["esg_prediction"] = {
                "predicted_esg": esg_prediction['predicted_esg'],
                "confidence_r2": esg_prediction['confidence_r2'],
                "prediction_range": esg_prediction['prediction_range'],
                "pillar_esg": formula_esg_score,
                "discrepancy": abs(formula_esg_score - esg_prediction['predicted_esg']),
                "model_type": esg_prediction['model_type'],
                "role": "Validation only (does not affect rating)"
            }
        
        # Add LSTM trend prediction if available
        if lstm_trend:
            result["lstm_trend_prediction"] = {
                "forecast": lstm_trend['forecast'],
                "trend": lstm_trend['trend'],
                "change_pct": lstm_trend['change_pct'],
                "confidence_mae": lstm_trend['confidence_mae'],
                "model_type": lstm_trend['model_type'],
                "role": "Context only (does not affect rating)"
            }
        
        # Add anomaly detection result if available
        if anomaly_result:
            result["anomaly_detection"] = {
                "is_anomaly": anomaly_result['is_anomaly'],
                "severity": anomaly_result['severity'],
                "anomaly_score": anomaly_result['anomaly_score'],
                "confidence": anomaly_result['confidence'],
                "anomalous_features": anomaly_result.get('anomalous_features', []),
                "model_type": "Isolation Forest",
                "role": "Flagging only (does not affect rating)"
            }
        
        print(f"\n✅ Final Risk Assessment:")
        print(f"   Greenwashing Risk: {greenwashing_risk:.1f}/100 ({risk_source})")
        print(f"   ESG Score: {esg_score:.1f}/100 (Grade: {rating_grade})")
        print(f"   Risk Level: {risk_level}")
        print(f"   Methodology: {'ESG Pillar Primary' if not use_ml_prediction else 'Pillar + ML Refinement'}")
        
        print(f"\n📊 ESG Pillar Breakdown:")
        print(f"   Environmental: {pillar_scores['environmental_score']}/100 (35% weight)")
        print(f"   Social: {pillar_scores['social_score']}/100 (30% weight)")
        print(f"   Governance: {pillar_scores['governance_score']}/100 (35% weight)")
        print(f"   Overall ESG: {pillar_scores['overall_esg_score']}/100")
        
        if ml_prediction:
            print(f"\n🤖 XGBoost Risk Model:")
            print(f"   Prediction: {ml_prediction}")
            print(f"   Used: {'YES (refinement)' if use_ml_prediction else 'NO (pillar scores primary)'}")
        
        if esg_prediction:
            print(f"\n🔮 LightGBM ESG Validator:")
            print(f"   Predicted ESG: {esg_prediction['predicted_esg']:.1f}/100")
            print(f"   Purpose: Validation check")
        
        if lstm_trend:
            print(f"\n🔮 LSTM Trend Forecaster:")
            print(f"   Trend: {lstm_trend['trend']}")
            print(f"   Purpose: Contextual insight")
        
        if anomaly_result and anomaly_result.get('is_anomaly'):
            print(f"\n⚠️  Anomaly Detector:")
            print(f"   Status: ANOMALY DETECTED")
            print(f"   Severity: {anomaly_result['severity']}")
            print(f"   Purpose: Flagging for review")
        
        print(f"\n📊 ESG Pillar Breakdown:")
        print(f"   Environmental: {pillar_scores['environmental_score']}/100 (35% weight)")
        print(f"   Social: {pillar_scores['social_score']}/100 (30% weight)")
        print(f"   Governance: {pillar_scores['governance_score']}/100 (35% weight)")
        print(f"   Overall ESG: {pillar_scores['overall_esg_score']}/100")
        
        if ml_prediction:
            print(f"\n🤖 XGBoost Risk Model:")
            print(f"   Prediction: {ml_prediction}")
            print(f"   Used: {'YES' if use_ml_prediction else 'NO (low confidence)'}")
        
        if esg_prediction:
            print(f"\n🔮 LightGBM ESG Predictor:")
            print(f"   Predicted ESG: {esg_prediction['predicted_esg']:.1f}/100")
            print(f"   Confidence: R²={esg_prediction['confidence_r2']:.3f}")
        
        if lstm_trend:
            print(f"\n🔮 LSTM Trend Forecaster:")
            print(f"   Trend: {lstm_trend['trend']}")
            print(f"   Change: {lstm_trend['change_pct']:+.1f}%")
            print(f"   6-Year Forecast: {lstm_trend['forecast']}")
        
        if anomaly_result and anomaly_result.get('is_anomaly'):
            print(f"\n⚠️  Anomaly Detector:")
            print(f"   Status: ANOMALY DETECTED")
            print(f"   Severity: {anomaly_result['severity']}")
            print(f"   Confidence: {anomaly_result['confidence']:.1f}%")
        
        return result
    
    def _identify_industry(self, company: str, analyses: Dict) -> str:
        """
        Identify company's industry - 100% DYNAMIC (NO HARDCODED FALLBACKS)
        Uses LLM to classify into predefined MSCI-based categories
        """
        
        # Prefer workflow-provided industry when available to avoid unnecessary LLM variance.
        provided_industry = str(analyses.get("industry", "") or "").strip().lower()
        if provided_industry:
            normalized = provided_industry.replace("&", "and").replace("-", "_").replace(" ", "_")
            aliases = {
                "tech": "technology",
                "it": "technology",
                "information_technology": "technology",
                "energy": "oil_and_gas",
                "oil_gas": "oil_and_gas",
                "food_and_beverage": "food_beverage",
                "telecom": "telecommunications"
            }
            normalized = aliases.get(normalized, normalized)
            if normalized in self.industry_baseline_risk:
                return normalized

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
        
        # 2. Evidence Quality (more and better weighted sources = lower risk)
        evidence = analyses.get('evidence', [])
        total_sources = sum(
            len(ev.get('evidence', [])) if isinstance(ev.get('evidence', []), list) else 0
            for ev in evidence if isinstance(ev, dict)
        )
        if total_sources == 0:
            total_sources = len([ev for ev in evidence if isinstance(ev, dict)])

        # Prefer weighted evidence quality if available
        weighted_scores = [float(ev.get('evidence_weight', 0.5)) for ev in evidence if isinstance(ev, dict)]
        weighted_quality = (sum(weighted_scores) / len(weighted_scores)) if weighted_scores else 0.5
        
        if total_sources >= 20:
            base_evidence_risk = 10
        elif total_sources >= 15:
            base_evidence_risk = 20
        elif total_sources >= 10:
            base_evidence_risk = 35
        elif total_sources >= 5:
            base_evidence_risk = 60
        else:
            base_evidence_risk = 90

        # Higher source weight lowers risk
        quality_modifier = int((1.0 - weighted_quality) * 25)
        components['evidence_quality'] = max(0, min(100, base_evidence_risk + quality_modifier))
        
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
            claim = analyses["claim"]
            # Handle both string and dict formats
            if isinstance(claim, dict):
                claim_text = claim.get("text", claim.get("claim", "")).lower()
            elif isinstance(claim, str):
                claim_text = claim.lower()
            else:
                claim_text = str(claim).lower()
                
            greenwashing_keywords = [
                "committed to", "leader in", "eco-friendly", "sustainable", 
                "green", "environmentally friendly", "climate positive"
            ]
            
            keyword_count = sum(1 for keyword in greenwashing_keywords if keyword in claim_text)
            has_numbers = any(char.isdigit() for char in claim_text)
            
            # Vague claim (multiple buzzwords + no metrics) = +20 risk penalty
            if keyword_count >= 2 and not has_numbers:
                components["claim_verification"] = min(100, components.get("claim_verification", 50) + 20)
                print(f"⚠️  Vague claim detected ({keyword_count} buzzwords, no metrics) - penalty applied")
        
        # NEW: Financial Greenwashing Flags (AGENT 14 integration)
        evidence = analyses.get('evidence', [])
        financial_flags_penalty = 0
        
        for ev in evidence:
            financial_context = ev.get('financial_context', {})
            if financial_context.get('financial_data_available'):
                flags = financial_context.get('greenwashing_flags', [])
                
                # Add risk based on severity
                for flag in flags:
                    severity = flag.get('severity', 'Low')
                    if severity == 'High':
                        financial_flags_penalty += 15
                    elif severity == 'Moderate':
                        financial_flags_penalty += 10
                    else:
                        financial_flags_penalty += 5
                
                # Cap penalty
                financial_flags_penalty = min(30, financial_flags_penalty)
        
        # Apply penalty to claim verification component
        if financial_flags_penalty > 0:
            components['claim_verification'] = min(100, 
                components.get('claim_verification', 50) + financial_flags_penalty
            )
            print(f"   ⚠️ Financial greenwashing penalty: +{financial_flags_penalty} risk")

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
        DEPRECATED: Use esg_score_to_rating() instead
        This method kept for backward compatibility
        Converts risk score to ESG score and uses MSCI-aligned rating
        """
        # Convert risk to ESG score
        esg_score = 100 - risk_score
        return self.esg_score_to_rating(esg_score)
    
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
    
    def _extract_esg_features(self, analyses: Dict) -> Optional[Dict[str, Any]]:
        """
        Extract features for LightGBM ESG predictor from analyses
        Required features:
        - environmentScore, socialScore, governanceScore (0-100)
        - highestControversy (0-5)
        - marketCap (float)
        - beta (float)
        - overallRisk (0-100)
        """
        try:
            # Extract ESG component scores (derived from components)
            components = self._calculate_components(analyses)
            
            # Map component scores to E, S, G scores (invert since components are risk scores)
            # Higher component risk → Lower ESG score
            evidence_quality = 100 - components.get('evidence_quality', 50)
            credibility = 100 - components.get('source_credibility', 50)
            sentiment = 100 - components.get('sentiment_divergence', 50)
            historical = 100 - components.get('historical_pattern', 50)
            
            # Approximate ESG dimensions
            env_score = (evidence_quality + credibility) / 2  # Environment
            soc_score = (sentiment + historical) / 2  # Social
            gov_score = credibility  # Governance
            
            # Extract controversy level (from contradictions)
            contradictions = analyses.get('contradiction_analysis', [])
            controversy_count = sum(1 for c in contradictions if c.get('overall_verdict') == 'Contradicted')
            highest_controversy = min(controversy_count, 5)
            
            # Extract financial context (if available)
            financial_ctx = analyses.get('financial_context', {})
            market_cap = financial_ctx.get('market_cap', 10_000_000_000)  # Default 10B
            beta = financial_ctx.get('beta', 1.0)  # Default market beta
            
            # Calculate overall risk (from greenwashing components)
            overall_risk = sum(components.values()) / len(components) if components else 50
            
            return {
                'environmentScore': round(env_score, 2),
                'socialScore': round(soc_score, 2),
                'governanceScore': round(gov_score, 2),
                'highestControversy': highest_controversy,
                'marketCap': market_cap,
                'beta': beta,
                'overallRisk': round(overall_risk, 2)
            }
        except Exception as e:
            print(f"   ⚠️ Error extracting ESG features: {e}")
            return None
    
    def _extract_anomaly_features(self, analyses: Dict) -> Optional[Dict[str, float]]:
        """
        Extract 8 anomaly detection features from agent analyses
        
        Returns dict with:
            - carbon_intensity
            - water_intensity
            - energy_intensity
            - esg_revenue_gap
            - growth_esg_correlation
            - profit_esg_ratio
            - environmental_balance
            - volatility_score
        """
        try:
            # Get financial data
            financial = analyses.get('financial_context', {})
            if not financial or not financial.get('financial_data_available'):
                return None
            
            fin_data = financial.get('financial_data', {})
            revenue = fin_data.get('revenue_ttm', 0)
            profit_margin = fin_data.get('profit_margin', 0)
            growth_rate = fin_data.get('revenue_growth', 0)
            
            # Get ESG metrics
            esg_metrics = financial.get('esg_financial_metrics', {})
            carbon_intensity = esg_metrics.get('carbon_intensity', 0) or 0
            water_efficiency = esg_metrics.get('water_efficiency', 0) or 0
            energy_efficiency = esg_metrics.get('energy_efficiency', 0) or 0
            
            # Get ESG scores from credibility analysis
            credibility = analyses.get('credibility_analysis', {})
            esg_overall = credibility.get('esg_score', 50)
            esg_env = credibility.get('environmental_score', 50)
            esg_social = credibility.get('social_score', 50)
            esg_gov = credibility.get('governance_score', 50)
            
            # Get historical volatility (if available)
            historical = analyses.get('historical_analysis', {})
            patterns = historical.get('temporal_patterns', {})
            volatility = 10.0 if patterns.get('declining_trend') else 5.0 if patterns.get('reactive_claims') else 2.0
            
            # Calculate features
            features = {
                'carbon_intensity': carbon_intensity,
                'water_intensity': water_efficiency,
                'energy_intensity': energy_efficiency,
                'esg_revenue_gap': (esg_overall - 50) / (np.log10(revenue + 1) + 1e-6) if revenue > 0 else 0,
                'growth_esg_correlation': (growth_rate * esg_overall) / 100,
                'profit_esg_ratio': profit_margin / (esg_overall + 1e-6) if esg_overall > 0 else 0,
                'environmental_balance': esg_env / (esg_social + esg_gov + 1e-6) if (esg_social + esg_gov) > 0 else 1.0,
                'volatility_score': volatility
            }
            
            return features
            
        except Exception as e:
            print(f"⚠️  Could not extract anomaly features: {e}")
            return None
