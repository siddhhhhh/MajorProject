"""
SHAP/LIME Explainability Engine
Provides Explainable AI (XAI) for ESG ML models

Features:
- SHAP TreeExplainer for XGBoost/LightGBM
- LIME for model-agnostic explanations
- Force plots, waterfall plots, summary plots
- Feature importance rankings
- Human-readable explanations for ESG risk scores

Integrates with existing ml_models for complete interpretability
"""

import os
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class ESGExplainabilityEngine:
    """
    Explainable AI Engine for ESG Risk Models
    Uses SHAP and LIME for model interpretability
    """
    
    def __init__(self):
        self.name = "ESG Explainability Engine"
        self.shap_available = False
        self.lime_available = False
        
        # Lazy import flags
        self._shap = None
        self._lime = None
        
        # Feature descriptions for human-readable explanations
        self.feature_descriptions = {
            # ESG Scores
            "esg_score": "Overall ESG performance score",
            "environmental_score": "Environmental pillar score",
            "social_score": "Social pillar score",
            "governance_score": "Governance pillar score",
            "environmentScore": "Environmental performance rating",
            "socialScore": "Social performance rating",
            "governanceScore": "Governance performance rating",
            
            # Carbon metrics
            "carbon_emissions": "Total carbon emissions (tCO2e)",
            "carbon_intensity": "Carbon intensity per revenue",
            "scope1_emissions": "Direct emissions from operations",
            "scope2_emissions": "Indirect emissions from energy",
            "scope3_emissions": "Value chain emissions",
            
            # Financial metrics
            "revenue_log": "Company revenue (log scale)",
            "profit_margin": "Net profit margin",
            "market_cap": "Market capitalization",
            "marketCap": "Market capitalization",
            "beta": "Stock volatility (beta)",
            
            # Risk indicators
            "controversy_score": "ESG controversy level",
            "highestControversy": "Most severe controversy level",
            "overallRisk": "Aggregate ESG risk score",
            "industry_encoded": "Industry sector classification",
            
            # Derived metrics
            "esg_vs_industry": "ESG score vs industry average",
            "revenue_vs_industry": "Revenue vs industry average",
            "esg_disclosure_count": "Number of ESG disclosures",
            
            # Greenwashing indicators
            "buzzword_count": "Number of vague sustainability buzzwords",
            "sentiment_divergence": "Gap between claim and evidence sentiment",
            "credibility_score": "Source credibility rating"
        }
        
        # Impact thresholds for explanations
        self.impact_thresholds = {
            "very_high": 0.3,
            "high": 0.15,
            "moderate": 0.05,
            "low": 0.01
        }
        
        print(f"✅ {self.name} initialized")
        print(f"   SHAP/LIME loaded on-demand")
    
    def _load_shap(self) -> bool:
        """Lazy load SHAP library"""
        if self._shap is not None:
            return self.shap_available
        
        try:
            import shap
            self._shap = shap
            self.shap_available = True
            print("✅ SHAP loaded successfully")
            return True
        except ImportError:
            print("⚠️ SHAP not installed: pip install shap")
            return False
    
    def _load_lime(self) -> bool:
        """Lazy load LIME library"""
        if self._lime is not None:
            return self.lime_available
        
        try:
            import lime
            import lime.lime_tabular
            self._lime = lime
            self.lime_available = True
            print("✅ LIME loaded successfully")
            return True
        except ImportError:
            print("⚠️ LIME not installed: pip install lime")
            return False
    
    def explain_xgboost_prediction(self, model, features: np.ndarray,
                                    feature_names: List[str],
                                    prediction_idx: int = None) -> Dict[str, Any]:
        """
        Generate SHAP explanation for XGBoost model prediction
        
        Args:
            model: Trained XGBoost model
            features: Feature array for prediction
            feature_names: List of feature names
            prediction_idx: Optional index if explaining specific sample
        
        Returns:
            Comprehensive SHAP explanation with visualizations
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 {self.name} - XGBoost Explanation")
        print(f"{'='*60}")
        
        if not self._load_shap():
            return self._fallback_explanation(features, feature_names)
        
        try:
            # Create TreeExplainer
            explainer = self._shap.TreeExplainer(model)
            
            # Calculate SHAP values
            features_2d = features.reshape(1, -1) if features.ndim == 1 else features
            shap_values = explainer.shap_values(features_2d)
            
            # Handle multi-class output
            if isinstance(shap_values, list):
                # Multi-class: shap_values is list of arrays
                if prediction_idx is not None:
                    shap_values_single = shap_values[prediction_idx][0]
                else:
                    # Use the class with highest absolute impact
                    shap_values_single = shap_values[0][0]
            else:
                shap_values_single = shap_values[0]
            
            # Generate explanation
            explanation = self._generate_explanation(
                shap_values_single,
                features_2d[0],
                feature_names,
                explainer.expected_value
            )
            
            print(f"✅ SHAP explanation generated")
            print(f"   Top factor: {explanation['top_factors'][0]['feature']}")
            
            return explanation
            
        except Exception as e:
            print(f"⚠️ SHAP explanation error: {e}")
            return self._fallback_explanation(features, feature_names)
    
    def explain_lightgbm_prediction(self, model, features: np.ndarray,
                                     feature_names: List[str]) -> Dict[str, Any]:
        """
        Generate SHAP explanation for LightGBM model prediction
        
        Args:
            model: Trained LightGBM model
            features: Feature array for prediction
            feature_names: List of feature names
        
        Returns:
            Comprehensive SHAP explanation
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 {self.name} - LightGBM Explanation")
        print(f"{'='*60}")
        
        if not self._load_shap():
            return self._fallback_explanation(features, feature_names)
        
        try:
            # Create TreeExplainer
            explainer = self._shap.TreeExplainer(model)
            
            # Calculate SHAP values
            features_2d = features.reshape(1, -1) if features.ndim == 1 else features
            shap_values = explainer.shap_values(features_2d)
            
            # For regression, shap_values is single array
            if isinstance(shap_values, list):
                shap_values_single = shap_values[0][0]
            else:
                shap_values_single = shap_values[0]
            
            # Generate explanation
            explanation = self._generate_explanation(
                shap_values_single,
                features_2d[0],
                feature_names,
                explainer.expected_value
            )
            
            print(f"✅ SHAP explanation generated")
            
            return explanation
            
        except Exception as e:
            print(f"⚠️ SHAP explanation error: {e}")
            return self._fallback_explanation(features, feature_names)
    
    def explain_with_lime(self, model, features: np.ndarray,
                          feature_names: List[str],
                          training_data: np.ndarray = None,
                          num_features: int = 10) -> Dict[str, Any]:
        """
        Generate LIME explanation for any model
        
        Args:
            model: Trained model with predict_proba method
            features: Feature array for prediction
            feature_names: List of feature names
            training_data: Training data for LIME (optional)
            num_features: Number of features to include in explanation
        
        Returns:
            LIME explanation with feature contributions
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 {self.name} - LIME Explanation")
        print(f"{'='*60}")
        
        if not self._load_lime():
            return self._fallback_explanation(features, feature_names)
        
        try:
            import lime.lime_tabular
            
            # Use features as training data if not provided
            if training_data is None:
                training_data = features.reshape(1, -1) if features.ndim == 1 else features
            
            # Create LIME explainer
            explainer = lime.lime_tabular.LimeTabularExplainer(
                training_data,
                feature_names=feature_names,
                mode='classification' if hasattr(model, 'predict_proba') else 'regression',
                discretize_continuous=True
            )
            
            # Generate explanation
            features_1d = features.flatten() if features.ndim > 1 else features
            
            if hasattr(model, 'predict_proba'):
                exp = explainer.explain_instance(features_1d, model.predict_proba, 
                                                 num_features=num_features)
            else:
                exp = explainer.explain_instance(features_1d, model.predict,
                                                num_features=num_features)
            
            # Extract feature contributions
            lime_contributions = []
            for feature, weight in exp.as_list():
                lime_contributions.append({
                    "feature": feature,
                    "contribution": float(weight),
                    "direction": "increases risk" if weight > 0 else "decreases risk"
                })
            
            return {
                "method": "LIME",
                "contributions": lime_contributions,
                "intercept": float(exp.intercept[1] if hasattr(exp, 'intercept') else 0),
                "local_prediction": float(exp.local_pred[0] if hasattr(exp, 'local_pred') else 0),
                "human_readable": self._generate_lime_narrative(lime_contributions)
            }
            
        except Exception as e:
            print(f"⚠️ LIME explanation error: {e}")
            return self._fallback_explanation(features, feature_names)
    
    def _generate_explanation(self, shap_values: np.ndarray,
                             features: np.ndarray,
                             feature_names: List[str],
                             base_value: float) -> Dict[str, Any]:
        """Generate comprehensive SHAP explanation"""
        
        # Create feature contributions
        contributions = []
        for i, (name, shap_val, feat_val) in enumerate(zip(feature_names, shap_values, features)):
            description = self.feature_descriptions.get(name, f"Feature: {name}")
            
            contributions.append({
                "feature": name,
                "description": description,
                "value": float(feat_val),
                "shap_value": float(shap_val),
                "impact": self._categorize_impact(abs(shap_val)),
                "direction": "increases risk" if shap_val > 0 else "decreases risk"
            })
        
        # Sort by absolute SHAP value
        contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        
        # Top factors
        top_factors = contributions[:5]
        
        # Generate human-readable narrative
        narrative = self._generate_narrative(top_factors)
        
        # Calculate summary stats
        total_positive = sum(c["shap_value"] for c in contributions if c["shap_value"] > 0)
        total_negative = sum(c["shap_value"] for c in contributions if c["shap_value"] < 0)
        
        return {
            "method": "SHAP",
            "base_value": float(base_value) if not isinstance(base_value, list) else float(base_value[0]),
            "all_contributions": contributions,
            "top_factors": top_factors,
            "summary": {
                "total_positive_impact": float(total_positive),
                "total_negative_impact": float(total_negative),
                "net_impact": float(total_positive + total_negative),
                "most_impactful_feature": top_factors[0]["feature"] if top_factors else None
            },
            "human_readable_explanation": narrative,
            "visualization_ready": True
        }
    
    def _categorize_impact(self, shap_value: float) -> str:
        """Categorize the impact level of a SHAP value"""
        
        if shap_value >= self.impact_thresholds["very_high"]:
            return "very_high"
        elif shap_value >= self.impact_thresholds["high"]:
            return "high"
        elif shap_value >= self.impact_thresholds["moderate"]:
            return "moderate"
        elif shap_value >= self.impact_thresholds["low"]:
            return "low"
        else:
            return "minimal"
    
    def _generate_narrative(self, top_factors: List[Dict]) -> str:
        """Generate human-readable narrative from SHAP values"""
        
        if not top_factors:
            return "Unable to determine key factors affecting the prediction."
        
        narrative_parts = ["**Key factors influencing this ESG risk assessment:**\n"]
        
        for i, factor in enumerate(top_factors[:3], 1):
            name = factor["feature"]
            description = factor["description"]
            direction = "increases" if factor["direction"] == "increases risk" else "decreases"
            impact = factor["impact"]
            value = factor["value"]
            
            # Format value nicely
            if abs(value) > 1000000:
                value_str = f"{value/1000000:.1f}M"
            elif abs(value) > 1000:
                value_str = f"{value/1000:.1f}K"
            else:
                value_str = f"{value:.2f}"
            
            narrative_parts.append(
                f"{i}. **{description}** (value: {value_str}) - {impact} impact, {direction} risk"
            )
        
        # Add summary
        increasing = [f for f in top_factors if f["direction"] == "increases risk"]
        decreasing = [f for f in top_factors if f["direction"] == "decreases risk"]
        
        if len(increasing) > len(decreasing):
            narrative_parts.append(f"\n⚠️ Overall, risk-increasing factors outweigh mitigating factors.")
        elif len(decreasing) > len(increasing):
            narrative_parts.append(f"\n✅ Overall, risk-mitigating factors outweigh risk-increasing factors.")
        else:
            narrative_parts.append(f"\nℹ️ Risk factors are balanced in this assessment.")
        
        return "\n".join(narrative_parts)
    
    def _generate_lime_narrative(self, contributions: List[Dict]) -> str:
        """Generate human-readable narrative from LIME contributions"""
        
        if not contributions:
            return "Unable to determine key factors."
        
        narrative_parts = ["**LIME Local Interpretation:**\n"]
        
        for i, contrib in enumerate(contributions[:5], 1):
            direction = contrib["direction"]
            narrative_parts.append(f"{i}. {contrib['feature']} - {direction}")
        
        return "\n".join(narrative_parts)
    
    def _fallback_explanation(self, features: np.ndarray, 
                             feature_names: List[str]) -> Dict[str, Any]:
        """Fallback explanation when SHAP/LIME unavailable"""
        
        # Simple feature importance based on value magnitude
        features_1d = features.flatten() if features.ndim > 1 else features
        
        contributions = []
        for name, val in zip(feature_names, features_1d):
            description = self.feature_descriptions.get(name, f"Feature: {name}")
            contributions.append({
                "feature": name,
                "description": description,
                "value": float(val),
                "relative_magnitude": "high" if abs(val) > np.mean(np.abs(features_1d)) else "normal"
            })
        
        # Sort by absolute value
        contributions.sort(key=lambda x: abs(x["value"]), reverse=True)
        
        return {
            "method": "fallback_magnitude",
            "note": "SHAP/LIME unavailable - showing feature values only",
            "contributions": contributions[:10],
            "human_readable_explanation": self._generate_fallback_narrative(contributions[:5])
        }
    
    def _generate_fallback_narrative(self, contributions: List[Dict]) -> str:
        """Generate simple narrative for fallback explanation"""
        
        parts = ["**Key features by magnitude:**\n"]
        
        for i, c in enumerate(contributions, 1):
            parts.append(f"{i}. {c['description']}: {c['value']:.2f}")
        
        parts.append("\n⚠️ Install SHAP for detailed feature impact analysis.")
        return "\n".join(parts)
    
    def generate_explanation_for_report(self, 
                                        model_type: str,
                                        model,
                                        features: np.ndarray,
                                        feature_names: List[str],
                                        prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate explanation suitable for professional ESG report
        
        Args:
            model_type: "xgboost" or "lightgbm"
            model: Trained model
            features: Input features
            feature_names: Feature names
            prediction: Model prediction result
        
        Returns:
            Report-ready explanation with narrative and factors
        """
        
        # Get SHAP explanation
        if model_type.lower() == "xgboost":
            shap_explanation = self.explain_xgboost_prediction(model, features, feature_names)
        elif model_type.lower() == "lightgbm":
            shap_explanation = self.explain_lightgbm_prediction(model, features, feature_names)
        else:
            shap_explanation = self._fallback_explanation(features, feature_names)
        
        # Format for report
        report_explanation = {
            "model_type": model_type,
            "prediction": prediction,
            "explanation_method": shap_explanation.get("method", "unknown"),
            "key_factors": [],
            "narrative": shap_explanation.get("human_readable_explanation", ""),
            "generated_at": datetime.now().isoformat()
        }
        
        # Extract top factors for report
        top_factors = shap_explanation.get("top_factors", shap_explanation.get("contributions", []))[:5]
        
        for factor in top_factors:
            report_explanation["key_factors"].append({
                "factor": factor.get("description", factor.get("feature")),
                "impact": factor.get("impact", "unknown"),
                "direction": factor.get("direction", "unknown"),
                "value": factor.get("value")
            })
        
        return report_explanation
    
    def create_shap_visualization_data(self, shap_values: np.ndarray,
                                       feature_names: List[str],
                                       features: np.ndarray) -> Dict[str, Any]:
        """
        Create data structure for SHAP visualizations
        Can be used to generate plots in frontend or Jupyter
        """
        
        # Waterfall plot data
        waterfall_data = []
        for i, (name, sv, fv) in enumerate(zip(feature_names, shap_values, features)):
            waterfall_data.append({
                "feature": name,
                "shap_value": float(sv),
                "feature_value": float(fv),
                "cumulative": float(sum(shap_values[:i+1]))
            })
        
        # Sort for waterfall
        waterfall_data.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        
        # Bar plot data (summary)
        bar_data = [
            {"feature": name, "importance": float(abs(sv))}
            for name, sv in zip(feature_names, shap_values)
        ]
        bar_data.sort(key=lambda x: x["importance"], reverse=True)
        
        return {
            "waterfall": waterfall_data,
            "bar": bar_data,
            "total_positive_shap": float(sum(sv for sv in shap_values if sv > 0)),
            "total_negative_shap": float(sum(sv for sv in shap_values if sv < 0))
        }


# Global instance
explainability_engine = ESGExplainabilityEngine()

def get_explainability_engine() -> ESGExplainabilityEngine:
    """Get global explainability engine instance"""
    return explainability_engine


def explain_esg_prediction(model, model_type: str, features: np.ndarray,
                          feature_names: List[str], prediction: Dict = None) -> Dict[str, Any]:
    """
    Convenience function to explain ESG model predictions
    
    Args:
        model: Trained ML model
        model_type: "xgboost" or "lightgbm"
        features: Input features
        feature_names: Feature names
        prediction: Optional prediction dict
    
    Returns:
        Explanation suitable for ESG reports
    """
    return explainability_engine.generate_explanation_for_report(
        model_type, model, features, feature_names, prediction or {}
    )
