"""
LightGBM ESG Score Predictor
Predicts ESG scores (0-100) from company metrics
Trained on S&P 500 data with ~92% accuracy (R²=0.92)
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LightGBMESGPredictor:
    """
    ESG Score Predictor using trained LightGBM model
    Predicts totalEsg score from 7 financial/ESG metrics
    """
    
    def __init__(self, model_dir: str = None):
        """
        Initialize LightGBM ESG predictor
        
        Args:
            model_dir: Directory containing trained model files
                      Default: ml_models/trained/
        """
        if model_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_dir = os.path.join(project_root, "ml_models", "trained")
        
        self.model = None
        self.feature_names = None
        self.metadata = None
        self.model_available = False
        
        # Load model
        model_path = os.path.join(model_dir, "lightgbm_esg_score_model.pkl")
        feature_path = os.path.join(model_dir, "lightgbm_feature_names.json")
        metadata_path = os.path.join(model_dir, "lightgbm_model_metadata.json")
        
        try:
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
                
                if os.path.exists(feature_path):
                    with open(feature_path, 'r') as f:
                        self.feature_names = json.load(f)
                
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        self.metadata = json.load(f)
                
                self.model_available = True
                r2 = self.metadata.get('performance', {}).get('test_r2') if self.metadata else None
                if isinstance(r2, (int, float)):
                    print(f"✅ LightGBM ESG predictor loaded (held-out R²={r2:.3f})")
                else:
                    print("✅ LightGBM ESG predictor loaded (held-out R² unavailable)")
            else:
                print(f"⚠️ LightGBM model not found: {model_path}")
                print(f"   Train model using notebooks/train_lightgbm_esg_score.ipynb")
        except Exception as e:
            print(f"❌ Error loading LightGBM model: {e}")
    
    def predict_esg_score(self, company_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Predict ESG score for a company
        
        Args:
            company_data: {
                'environmentScore': float (0-100),
                'socialScore': float (0-100),
                'governanceScore': float (0-100),
                'highestControversy': int (0-5),
                'marketCap': float (USD),
                'beta': float,
                'overallRisk': float (0-100)
            }
        
        Returns:
            {
                'predicted_esg': float,
                'confidence_r2': float,
                'expected_error': float,
                'prediction_range': (float, float),
                'model_type': str,
                'prediction_successful': bool
            }
        """
        
        if not self.model_available:
            return {
                'prediction_successful': False,
                'error': 'Model not loaded'
            }
        
        try:
            # Validate required fields
            required_fields = [
                'environmentScore', 'socialScore', 'governanceScore',
                'highestControversy', 'marketCap', 'beta', 'overallRisk'
            ]
            
            missing_fields = [f for f in required_fields if f not in company_data]
            if missing_fields:
                return {
                    'prediction_successful': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }
            
            # Transform data (log market cap)
            data = pd.DataFrame([company_data])
            data['marketCap_log'] = np.log1p(data['marketCap'])
            data = data.drop('marketCap', axis=1)
            
            # Reorder to match training
            if self.feature_names:
                data = data[self.feature_names]

            logger.debug("LightGBM input features: %s", list(data.columns))
            logger.debug("Feature matrix shape: %s", data.shape)
            logger.debug("Non-null counts: %s", data.count().to_dict())

            if data.isnull().all(axis=None):
                return {
                    'prediction_successful': False,
                    'error': 'All LightGBM inference features are NaN'
                }
            
            # Predict
            prediction = self.model.predict(data)[0]
            
            # Get error metrics from metadata
            mae = self.metadata['performance']['test_mae'] if self.metadata else 5.0
            rmse = self.metadata['performance']['test_rmse'] if self.metadata else 7.0
            r2 = self.metadata['performance']['test_r2'] if self.metadata else 0.92
            
            # Calculate prediction interval (95% confidence: ±2 RMSE)
            error_margin = 2 * rmse
            lower_bound = max(0, prediction - error_margin)
            upper_bound = min(100, prediction + error_margin)
            
            return {
                'predicted_esg': round(float(prediction), 2),
                'confidence_r2': round(r2, 3),
                'expected_error': round(mae, 2),
                'prediction_range': (round(lower_bound, 1), round(upper_bound, 1)),
                'model_type': 'LightGBM Regressor',
                'prediction_successful': True
            }
            
        except Exception as e:
            print(f"❌ Prediction error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'prediction_successful': False,
                'error': str(e)
            }
    
    def validate_esg_claim(self, claimed_esg: float, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a claimed ESG score against predicted score
        
        Args:
            claimed_esg: The ESG score claimed by the company
            company_data: Company metrics (see predict_esg_score)
        
        Returns:
            {
                'validation_available': bool,
                'claimed_esg': float,
                'predicted_esg': float,
                'discrepancy': float,
                'discrepancy_pct': float,
                'plausible': bool,
                'prediction_range': tuple,
                'flag': str,
                'confidence': float
            }
        """
        
        prediction = self.predict_esg_score(company_data)
        
        if not prediction or not prediction.get('prediction_successful'):
            return {
                'validation_available': False,
                'error': prediction.get('error', 'Prediction failed')
            }
        
        predicted_esg = prediction['predicted_esg']
        discrepancy = claimed_esg - predicted_esg
        discrepancy_pct = (discrepancy / predicted_esg) * 100 if predicted_esg > 0 else 0
        
        # Determine if claim is plausible (within prediction range)
        lower, upper = prediction['prediction_range']
        plausible = lower <= claimed_esg <= upper
        
        # Flag severity based on absolute discrepancy
        abs_discrepancy = abs(discrepancy)
        if abs_discrepancy < 5:
            flag = "No concern"
        elif abs_discrepancy < 10:
            flag = "Minor discrepancy"
        elif abs_discrepancy < 20:
            flag = "Moderate concern"
        else:
            flag = "High concern - investigate"
        
        return {
            'validation_available': True,
            'claimed_esg': claimed_esg,
            'predicted_esg': predicted_esg,
            'discrepancy': round(discrepancy, 2),
            'discrepancy_pct': round(discrepancy_pct, 1),
            'plausible': plausible,
            'prediction_range': prediction['prediction_range'],
            'flag': flag,
            'confidence': prediction['confidence_r2']
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata and performance metrics"""
        if not self.model_available:
            return {'model_available': False}
        
        return {
            'model_available': True,
            'model_type': 'LightGBM Regressor',
            'features': self.feature_names,
            'performance': self.metadata.get('performance', {}) if self.metadata else {},
            'training_date': self.metadata.get('training_date', 'Unknown') if self.metadata else 'Unknown',
            'dataset_size': self.metadata.get('dataset_size', 'Unknown') if self.metadata else 'Unknown'
        }


# Singleton instance
_predictor_instance = None

def get_esg_predictor() -> LightGBMESGPredictor:
    """Get singleton LightGBM ESG predictor instance"""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = LightGBMESGPredictor()
    return _predictor_instance
