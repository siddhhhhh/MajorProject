"""
XGBoost Risk Model Wrapper
Loads trained XGBoost model for greenwashing risk prediction
"""

import os
import joblib
import numpy as np
from typing import Dict, Any, Optional, List


class XGBoostRiskModel:
    """
    Wrapper for trained XGBoost greenwashing risk classifier
    Loads model from ml_models/trained/xgboost_risk_model.pkl
    """
    
    def __init__(self, model_path: str = None):
        """
        Initialize XGBoost model wrapper
        
        Args:
            model_path: Path to trained model .pkl file
                       Default: ml_models/trained/xgboost_risk_model.pkl
        """
        if model_path is None:
            # Default path relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(project_root, "ml_models", "trained", "xgboost_risk_model.pkl")
        
        self.model_path = model_path
        self.model = None
        self.feature_names = None
        
        # Try to load model
        self._load_model()
    
    def _load_model(self):
        """Load trained XGBoost model from disk"""
        if not os.path.exists(self.model_path):
            print(f"ℹ️  XGBoost model not found at: {self.model_path}")
            print(f"   Run notebooks/train_xgboost_risk.ipynb to train the model")
            return
        
        try:
            import xgboost as xgb
            
            # Load model (might be dict or model object)
            loaded_data = joblib.load(self.model_path)
            
            # Handle different saved formats
            if isinstance(loaded_data, dict):
                # Model saved as {'model': model_obj, 'feature_names': [...], ...}
                self.model = loaded_data.get('model', loaded_data.get('xgb_model'))
                self.feature_names = loaded_data.get('feature_names', loaded_data.get('features'))
                
                if self.model is None:
                    print(f"⚠️  Model dict keys: {loaded_data.keys()}")
                    raise ValueError("Model not found in saved dictionary")
            else:
                # Model saved directly
                self.model = loaded_data
                # Use default feature names
                self.feature_names = None
            
            # Define expected features if not in saved file
            if self.feature_names is None:
                self.feature_names = [
                    'esg_score',
                    'revenue_log',
                    'profit_margin',
                    'carbon_intensity',
                    'water_efficiency',
                    'energy_efficiency',
                    'industry_encoded',
                    'esg_vs_industry',
                    'revenue_vs_industry',
                    'esg_disclosure_count'
                ]
            
            print(f"✅ XGBoost model loaded from {self.model_path}")
            print(f"   Features: {len(self.feature_names)}")
            print(f"   Model type: {type(self.model).__name__}")
            
        except Exception as e:
            print(f"⚠️  Failed to load XGBoost model: {e}")
            import traceback
            traceback.print_exc()
            self.model = None
    
    def predict(self, all_analyses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict greenwashing risk using XGBoost model
        
        Args:
            all_analyses: Dict with evidence, financial data, etc.
        
        Returns:
            Dict with prediction, confidence, probabilities
        """
        if self.model is None:
            return {
                "ml_available": False,
                "prediction": None,
                "confidence": 0.0,
                "probabilities": {},
                "error": "Model not loaded"
            }
        
        try:
            # Extract features from all_analyses
            features = self._extract_features(all_analyses)
            
            if features is None:
                return {
                    "ml_available": False,
                    "prediction": None,
                    "confidence": 0.0,
                    "probabilities": {},
                    "error": "Feature extraction failed"
                }
            
            # Make prediction
            import xgboost as xgb
            
            # Check model type - XGBClassifier (sklearn) or Booster (native XGBoost)
            model_type = type(self.model).__name__
            
            if hasattr(self.model, 'predict_proba'):
                # XGBClassifier or sklearn-compatible model - use numpy array directly
                proba = self.model.predict_proba(features)[0]  # Don't convert to DMatrix
                
                # Get class labels - check if model has classes_ attribute
                if hasattr(self.model, 'classes_'):
                    # Model has classes (e.g., [0, 1, 2])
                    numeric_classes = self.model.classes_
                    # Map numeric to risk levels: 0=HIGH, 1=LOW, 2=MODERATE
                    class_map = {0: 'HIGH', 1: 'LOW', 2: 'MODERATE'}
                    classes = [class_map.get(int(c), 'MODERATE') for c in numeric_classes]
                else:
                    # Default mapping
                    classes = ['HIGH', 'LOW', 'MODERATE']
                
                # Get prediction (class with highest probability)
                pred_idx = np.argmax(proba)
                prediction = classes[pred_idx]
                confidence = float(proba[pred_idx])
                
                # Build probability dict
                probabilities = {
                    classes[i]: float(proba[i])
                    for i in range(len(classes))
                }
                
            elif hasattr(self.model, 'predict'):
                # Native XGBoost or other model - try with DMatrix
                try:
                    dmatrix = xgb.DMatrix(features, feature_names=self.feature_names)
                    pred_proba = self.model.predict(dmatrix)
                except:
                    # Fallback to numpy array
                    pred_proba = self.model.predict(features)
                
                # Check if it returned probabilities or classes
                if len(pred_proba.shape) > 1 or pred_proba[0] < 1:
                    # It's probabilities
                    proba = pred_proba[0] if len(pred_proba.shape) > 1 else pred_proba
                    classes = ['HIGH', 'LOW', 'MODERATE']
                    pred_idx = np.argmax(proba)
                    prediction = classes[pred_idx]
                    confidence = float(proba[pred_idx])
                    probabilities = {classes[i]: float(proba[i]) for i in range(len(classes))}
                else:
                    # It's class labels (0, 1, 2)
                    class_map = {0: 'HIGH', 1: 'LOW', 2: 'MODERATE'}
                    prediction = class_map.get(int(pred_proba[0]), 'MODERATE')
                    confidence = 0.75  # Default confidence
                    probabilities = {prediction: 0.75, 'MODERATE': 0.15, 'LOW': 0.10}
            else:
                raise AttributeError(f"Model type {type(self.model)} has no predict method")
            
            return {
                "ml_available": True,
                "prediction": prediction,
                "confidence": confidence,
                "probabilities": probabilities,
                "features_used": self.feature_names,
                "feature_values": features.tolist()[0]
            }
            
        except Exception as e:
            print(f"⚠️  ML prediction error: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "ml_available": False,
                "prediction": None,
                "confidence": 0.0,
                "probabilities": {},
                "error": str(e)
            }
    
    def _extract_features(self, all_analyses: Dict[str, Any]) -> Optional[np.ndarray]:
        """
        Extract features matching training data
        Uses actual feature names from trained model (23 features)
        """
        try:
            # Get financial context
            financial_context = all_analyses.get('financial_context')
            fin_data = financial_context.get('financial_data', {}) if financial_context else {}
            
            # Extract basic financial metrics
            revenue = fin_data.get('revenue_usd', 100_000_000)
            revenue_log = np.log10(revenue + 1) if revenue > 0 else 8.0
            profit_margin = fin_data.get('profit_margin_pct', 5.0)
            debt_to_equity = fin_data.get('debt_to_equity', 1.0)
            
            # ESG metrics
            carbon_intensity = fin_data.get('carbon_intensity', 0.5)
            water_efficiency = fin_data.get('water_efficiency', 0.5)
            energy_efficiency = fin_data.get('energy_efficiency', 0.5)
            
            # Extract ESG score from credibility
            credibility = all_analyses.get('credibility_analysis', {})
            metrics = credibility.get('aggregate_metrics', {})
            avg_cred = metrics.get('average_credibility', 0.5)
            esg_score = avg_cred * 100
            
            # Contradiction data
            contradictions = all_analyses.get('contradiction_analysis', [])
            esg_disclosure_count = len(contradictions) if contradictions else 5
            
            # Industry encoding (simplified)
            industry_map = {
                'technology': 0, 'oil_and_gas': 1, 'automotive': 2,
                'fast_fashion': 3, 'food_beverage': 4, 'finance': 5,
                'manufacturing': 6, 'retail': 7, 'energy': 8, 'unknown': 9
            }
            peer_comp = all_analyses.get('peer_comparison', {})
            industry_name = peer_comp.get('industry', 'unknown')
            industry_encoded = industry_map.get(industry_name, 9)
            
            # Peer comparisons
            esg_vs_industry = peer_comp.get('esg_vs_industry', 0.0)
            revenue_vs_industry = peer_comp.get('revenue_vs_industry', 0.0)
            
            # ================================================================
            # NEW: Extract ESG PILLAR SCORES (0-100) - Normalized to 0-1
            # ================================================================
            pillar_scores = all_analyses.get('pillar_scores', {})
            environmental_score = pillar_scores.get('environmental_score', 50.0) / 100.0
            social_score = pillar_scores.get('social_score', 50.0) / 100.0
            governance_score = pillar_scores.get('governance_score', 50.0) / 100.0
            overall_esg_from_pillars = pillar_scores.get('overall_esg_score', 50.0) / 100.0
            
            print(f"   🔍 XGBoost Feature Extraction:")
            print(f"      ESG Score (old method): {esg_score:.1f}/100")
            print(f"      Environmental Pillar: {environmental_score*100:.1f}/100")
            print(f"      Social Pillar: {social_score*100:.1f}/100")
            print(f"      Governance Pillar: {governance_score*100:.1f}/100")
            print(f"      Overall ESG Pillar: {overall_esg_from_pillars*100:.1f}/100")
            
            # Create feature dict matching actual model (23 features from Colab + 4 pillar features = 27)
            # This matches the original dataset columns
            features_dict = {
                'ESG_Score': esg_score,
                'Revenue': revenue,
                'Profit_Margin': profit_margin,
                'Debt_to_Equity': debt_to_equity,
                'Carbon_Emissions': carbon_intensity * 1000,  # Scale up
                'Water_Usage': (1 - water_efficiency) * 100,  # Inverse
                'Energy_Consumption': (1 - energy_efficiency) * 100,  # Inverse
                'Waste_Production': 50.0,  # Default
                'Renewable_Energy_Pct': energy_efficiency * 100,
                'Board_Diversity_Pct': 30.0,  # Default
                'Female_Employees_Pct': 40.0,  # Default
                'Employee_Turnover_Rate': 10.0,  # Default
                'CEO_Pay_Ratio': 100.0,  # Default
                'Supplier_Audits': 5,  # Default
                'Product_Safety_Incidents': 0,  # Default
                'Data_Breaches': 0,  # Default
                'Regulatory_Fines': 0,  # Default
                'Sustainability_Report': 1,  # Default yes
                'Third_Party_Certifications': 1,  # Default yes
                'ESG_Controversies': 0,  # Default
                'Industry_Sector': industry_encoded,
                'Greenwashing_Risk': 2,  # Will be ignored (target variable)
                'ESG_Disclosure_Level': esg_disclosure_count,
                # NEW: Add pillar scores as features (normalized 0-100 scale)
                'Environmental_Score_Pillar': environmental_score * 100,
                'Social_Score_Pillar': social_score * 100,
                'Governance_Score_Pillar': governance_score * 100,
                'Overall_ESG_Pillar': overall_esg_from_pillars * 100
            }
            
            # If we have the actual feature names from the model, use those in order
            if self.feature_names:
                # Build array in exact order of feature names
                # Handle both old models (23 features) and new models (27 features)
                feature_array = np.array([[
                    features_dict.get(fname, 0.0) for fname in self.feature_names
                ]])
            else:
                # Fallback: use default order (include new pillar features)
                feature_array = np.array([[
                    features_dict[k] for k in sorted(features_dict.keys())
                ]])
            
            print(f"      Feature array shape: {feature_array.shape}")
            print(f"      Using {len(self.feature_names) if self.feature_names else 'default'} features")
            
            return feature_array
            
        except Exception as e:
            print(f"⚠️  Feature extraction error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def is_available(self) -> bool:
        """Check if model is loaded and ready"""
        return self.model is not None


# Singleton instance
_model_instance = None

def get_model() -> XGBoostRiskModel:
    """Get singleton XGBoost model instance"""
    global _model_instance
    if _model_instance is None:
        _model_instance = XGBoostRiskModel()
    return _model_instance
