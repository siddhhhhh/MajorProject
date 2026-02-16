"""
ESG Anomaly Detector

Detects companies with unusual ESG patterns using Isolation Forest.
Flags potential greenwashing indicators through statistical outliers.
"""

import os
import numpy as np
import joblib
from typing import Dict, Any, Optional, List


class ESGAnomalyDetector:
    """
    Anomaly detection for ESG greenwashing patterns
    
    Uses Isolation Forest to identify companies with suspicious metrics:
    - Extreme carbon/water/energy intensity
    - ESG-revenue mismatches
    - Inconsistent ESG scores over time
    - Imbalanced ESG pillars
    """
    
    def __init__(self, model_dir: str = None):
        """
        Initialize anomaly detector
        
        Args:
            model_dir: Directory containing trained model files
        """
        if model_dir is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_dir = os.path.join(project_root, "ml_models", "trained")
        
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.metadata = None
        self.model_available = False
        
        # Load model artifacts
        model_path = os.path.join(model_dir, "anomaly_detector.pkl")
        scaler_path = os.path.join(model_dir, "anomaly_scaler.pkl")
        features_path = os.path.join(model_dir, "anomaly_features.pkl")
        metadata_path = os.path.join(model_dir, "anomaly_metadata.json")
        
        try:
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                self.feature_names = joblib.load(features_path)
                
                if os.path.exists(metadata_path):
                    import json
                    with open(metadata_path, 'r') as f:
                        self.metadata = json.load(f)
                
                self.model_available = True
                contamination = self.metadata.get('contamination', 0.05) if self.metadata else 0.05
                print(f"✅ Anomaly detector loaded (contamination={contamination})")
            else:
                print(f"⚠️  Anomaly detector not found: {model_path}")
                print(f"   Train using: python scripts/train_anomaly_detector.py")
        except Exception as e:
            print(f"❌ Error loading anomaly detector: {e}")
    
    def detect_anomaly(self, company_metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Detect if company exhibits anomalous ESG patterns
        
        Args:
            company_metrics: Dictionary with engineered features:
                - carbon_intensity: CarbonEmissions / Revenue
                - water_intensity: WaterUsage / Revenue
                - energy_intensity: EnergyConsumption / Revenue
                - esg_revenue_gap: (ESG - 50) / log(Revenue)
                - growth_esg_correlation: GrowthRate * ESG
                - profit_esg_ratio: ProfitMargin / ESG
                - environmental_balance: Environmental / (Social + Governance)
                - volatility_score: Std dev of ESG across years
        
        Returns:
            {
                'is_anomaly': bool,
                'anomaly_score': float,
                'confidence': float,
                'severity': str,
                'anomalous_features': list,
                'detection_successful': bool
            }
        """
        
        if not self.model_available:
            return {
                'detection_successful': False,
                'error': 'Model not loaded'
            }
        
        try:
            # Validate required features
            missing = [f for f in self.feature_names if f not in company_metrics]
            if missing:
                return {
                    'detection_successful': False,
                    'error': f'Missing features: {", ".join(missing)}'
                }
            
            # Extract features in correct order
            X = np.array([[company_metrics[f] for f in self.feature_names]])
            
            # Replace inf/nan with 0
            X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)
            
            # Scale features
            X_scaled = self.scaler.transform(X)
            
            # Predict
            prediction = self.model.predict(X_scaled)[0]
            anomaly_score = float(self.model.score_samples(X_scaled)[0])
            
            # Calculate confidence (distance from threshold)
            threshold = -0.1  # Typical threshold for contamination=0.05
            confidence = min(abs(anomaly_score - threshold) / abs(threshold) * 100, 100)
            
            # Determine severity
            if anomaly_score > -0.05:
                severity = "Low"
            elif anomaly_score > -0.15:
                severity = "Moderate"
            else:
                severity = "High"
            
            # Identify which features are most anomalous
            # Calculate z-scores for each feature
            anomalous_features = []
            for i, feature in enumerate(self.feature_names):
                z_score = abs(X_scaled[0, i])
                if z_score > 2.5:  # More than 2.5 std devs
                    anomalous_features.append({
                        'feature': feature,
                        'value': float(X[0, i]),
                        'z_score': round(float(z_score), 2),
                        'severity': 'High' if z_score > 3 else 'Moderate'
                    })
            
            return {
                'is_anomaly': prediction == -1,
                'anomaly_score': round(anomaly_score, 4),
                'confidence': round(float(confidence), 2),
                'severity': severity,
                'anomalous_features': sorted(anomalous_features, 
                                           key=lambda x: x['z_score'], 
                                           reverse=True),
                'detection_successful': True
            }
            
        except Exception as e:
            print(f"❌ Anomaly detection error: {e}")
            return {
                'detection_successful': False,
                'error': str(e)
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata"""
        if not self.model_available:
            return {'model_available': False}
        
        return {
            'model_available': True,
            'model_type': 'Isolation Forest',
            'features': self.feature_names,
            'contamination': self.metadata.get('contamination', 0.05) if self.metadata else 0.05,
            'training_date': self.metadata.get('training_date', 'Unknown') if self.metadata else 'Unknown',
            'dataset_size': self.metadata.get('dataset_size', 'Unknown') if self.metadata else 'Unknown'
        }


# Singleton instance
_detector_instance = None

def get_anomaly_detector() -> ESGAnomalyDetector:
    """Get singleton anomaly detector instance"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ESGAnomalyDetector()
    return _detector_instance
