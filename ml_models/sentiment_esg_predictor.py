"""
Sentiment-to-ESG Impact Predictor

Predicts ESG score changes based on news sentiment analysis.
Trained on synthetic data simulating real-world sentiment-ESG correlations.
"""

import os
import json
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


class SentimentESGPredictor:
    """
    Predict ESG score changes from news sentiment
    
    Input: News sentiment, volume, controversy level, current ESG, industry
    Output: Predicted ESG change over 6 months (-30 to +30 points)
    """
    
    def __init__(self, model_dir: str = None):
        """Initialize predictor"""
        if model_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_dir = os.path.join(project_root, "ml_models", "trained")
        
        self.model = None
        self.features = None
        self.metadata = None
        self.model_available = False
        
        # Load model artifacts
        model_path = os.path.join(model_dir, "sentiment_esg_model.pkl")
        features_path = os.path.join(model_dir, "sentiment_features.pkl")
        metadata_path = os.path.join(model_dir, "sentiment_model_metadata.json")
        
        try:
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
                self.features = joblib.load(features_path)
                
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        self.metadata = json.load(f)
                
                self.model_available = True
                model_type = self.metadata.get('model_type', 'Unknown') if self.metadata else 'Unknown'
                print(f"✅ Sentiment-ESG predictor loaded ({model_type})")
            else:
                print(f"⚠️  Sentiment-ESG model not found: {model_path}")
                print(f"   Train using: python scripts/train_sentiment_esg_model.py")
        except Exception as e:
            print(f"❌ Error loading sentiment-ESG model: {e}")
    
    def predict_esg_impact(self, sentiment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Predict ESG score change from sentiment analysis
        
        Args:
            sentiment_data: {
                'news_sentiment': float (-1 to 1),
                'sentiment_volume': int (1-100),
                'controversy_level': int (0-5),
                'current_esg_score': float (0-100),
                'industry_volatility': float (0.5-2.0)
            }
        
        Returns:
            {
                'predicted_change': float,
                'confidence_interval': (float, float),
                'direction': 'POSITIVE'/'NEGATIVE'/'NEUTRAL',
                'magnitude': 'MAJOR'/'MODERATE'/'MINOR',
                'interpretation': str,
                'prediction_successful': bool
            }
        """
        
        if not self.model_available:
            return {
                'prediction_successful': False,
                'error': 'Model not loaded'
            }
        
        try:
            # Validate inputs
            required = ['news_sentiment', 'sentiment_volume', 'controversy_level', 
                       'current_esg_score', 'industry_volatility']
            missing = [f for f in required if f not in sentiment_data]
            if missing:
                return {
                    'prediction_successful': False,
                    'error': f'Missing fields: {", ".join(missing)}'
                }
            
            # Engineer interaction features
            features = sentiment_data.copy()
            features['sentiment_intensity'] = (
                features['news_sentiment'] * features['sentiment_volume']
            )
            features['controversy_sentiment'] = (
                features['controversy_level'] * features['news_sentiment']
            )
            features['recovery_potential'] = (
                features['current_esg_score'] * features['news_sentiment']
            )
            
            # Create DataFrame in correct order
            X_input = pd.DataFrame([[features[f] for f in self.features]], 
                                  columns=self.features)
            
            # Predict
            prediction = float(self.model.predict(X_input)[0])
            
            # Calculate confidence interval
            rmse = self.metadata['performance']['rmse'] if self.metadata else 5.0
            confidence_margin = 2 * rmse
            lower_bound = prediction - confidence_margin
            upper_bound = prediction + confidence_margin
            
            # Classify direction
            if prediction > 5:
                direction = "POSITIVE"
            elif prediction < -5:
                direction = "NEGATIVE"
            else:
                direction = "NEUTRAL"
            
            # Classify magnitude
            abs_change = abs(prediction)
            if abs_change > 15:
                magnitude = "MAJOR"
            elif abs_change > 8:
                magnitude = "MODERATE"
            else:
                magnitude = "MINOR"
            
            # Generate interpretation
            if direction == "POSITIVE":
                interpretation = f"Positive sentiment predicts +{abs(prediction):.1f} point ESG improvement over 6 months"
            elif direction == "NEGATIVE":
                interpretation = f"Negative sentiment predicts -{abs(prediction):.1f} point ESG decline over 6 months"
            else:
                interpretation = f"Mixed signals predict minimal ESG change ({prediction:+.1f} points)"
            
            # Add context based on controversy
            if sentiment_data['controversy_level'] >= 3:
                interpretation += " (⚠️ High controversy amplifies impact)"
            
            return {
                'predicted_change': round(prediction, 2),
                'confidence_interval': (round(lower_bound, 2), round(upper_bound, 2)),
                'direction': direction,
                'magnitude': magnitude,
                'interpretation': interpretation,
                'prediction_successful': True,
                'model_type': self.metadata.get('model_type', 'Unknown') if self.metadata else 'Unknown'
            }
            
        except Exception as e:
            print(f"❌ Sentiment prediction error: {e}")
            return {
                'prediction_successful': False,
                'error': str(e)
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata"""
        if not self.model_available:
            return {'model_available': False}
        
        return {
            'model_available': True,
            'model_type': self.metadata.get('model_type', 'Unknown') if self.metadata else 'Unknown',
            'features': self.features,
            'mae': self.metadata['performance']['mae'] if self.metadata else None,
            'r2': self.metadata['performance']['r2'] if self.metadata else None,
            'training_date': self.metadata.get('training_date', 'Unknown') if self.metadata else 'Unknown',
            'use_case': 'Predict ESG impact of media sentiment and controversies'
        }


# Singleton instance
_predictor_instance = None

def get_sentiment_esg_predictor() -> SentimentESGPredictor:
    """Get singleton sentiment-ESG predictor instance"""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = SentimentESGPredictor()
    return _predictor_instance
