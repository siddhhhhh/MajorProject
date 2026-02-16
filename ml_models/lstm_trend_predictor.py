"""
LSTM-based ESG Trend Forecaster

Predicts 12-month ESG trajectory using historical time series data.
Model trained on 6 years of historical ESG scores to forecast next 6 years.
"""

import os
import numpy as np
import joblib
from typing import Dict, List, Optional, Any

# Lazy import for TensorFlow (heavy dependency)
try:
    from tensorflow import keras
    from tensorflow.keras.models import load_model
    from tensorflow.keras.losses import MeanSquaredError
    from tensorflow.keras.metrics import MeanAbsoluteError
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("⚠️  TensorFlow not installed - LSTM trend prediction disabled")


class LSTMTrendPredictor:
    """
    LSTM-based trend forecasting for ESG scores
    
    Input: Last 6 ESG scores (e.g., [60, 62, 65, 68, 70, 72])
    Output: Trend classification (IMPROVING/STABLE/DECLINING) + 6-year forecast
    """
    
    def __init__(self):
        self.model = None
        self.scaler_X = None
        self.scaler_y = None
        self.metadata = {}
        self.model_available = False
        self.load_error = None  # Track loading errors
        
        # Model paths
        self.model_dir = os.path.join(os.path.dirname(__file__), 'trained')
        self.model_path = os.path.join(self.model_dir, 'lstm_trend_forecaster.h5')
        self.scaler_X_path = os.path.join(self.model_dir, 'lstm_scaler_X.pkl')
        self.scaler_y_path = os.path.join(self.model_dir, 'lstm_scaler_y.pkl')
        self.metadata_path = os.path.join(self.model_dir, 'lstm_metadata.json')
        
        if TENSORFLOW_AVAILABLE:
            self._load_model()
        else:
            self.load_error = "TensorFlow not available"
            print("⚠️  TensorFlow not installed - LSTM prediction disabled")
    
    def _load_model(self):
        """
        Load trained LSTM model and scalers with proper custom_objects handling
        
        FIXED: Handles TensorFlow/Keras 2.15+ serialization changes
        - Explicitly registers 'mse' and 'mae' metrics
        - Uses compile=False to avoid metric deserialization issues
        - Manually recompiles model after loading
        """
        try:
            if not os.path.exists(self.model_path):
                self.load_error = f"Model file not found: {self.model_path}"
                print(f"⚠️  LSTM model not found at: {self.model_path}")
                print(f"   Train model using: notebooks/train_lstm_trend.ipynb")
                return
            
            # ============================================================
            # FIX: Load model with custom_objects for TF 2.15+
            # ============================================================
            print(f"🔄 Loading LSTM model from: {self.model_path}")
            
            try:
                # Attempt 1: Load with custom_objects (for TF 2.15+)
                self.model = load_model(
                    self.model_path,
                    custom_objects={
                        'mse': MeanSquaredError(),
                        'mae': MeanAbsoluteError(),
                        # Also handle legacy names
                        'mean_squared_error': MeanSquaredError(),
                        'mean_absolute_error': MeanAbsoluteError()
                    },
                    compile=False  # Skip compilation during load
                )
                print(f"✅ LSTM model loaded with custom_objects")
                
            except Exception as e1:
                print(f"⚠️  Custom objects loading failed: {e1}")
                print(f"🔄 Attempting legacy load method...")
                
                # Attempt 2: Load without compilation (fallback)
                try:
                    self.model = load_model(
                        self.model_path,
                        compile=False
                    )
                    print(f"✅ LSTM model loaded (legacy mode)")
                    
                except Exception as e2:
                    print(f"❌ All loading attempts failed")
                    print(f"   Error 1 (custom_objects): {e1}")
                    print(f"   Error 2 (legacy): {e2}")
                    self.load_error = f"Model loading failed: {str(e2)}"
                    return
            
            # ============================================================
            # Manually compile model with correct metrics
            # ============================================================
            try:
                self.model.compile(
                    optimizer='adam',
                    loss='mse',
                    metrics=['mae']
                )
                print(f"✅ Model recompiled successfully")
                
            except Exception as e:
                print(f"⚠️  Compilation warning (non-critical): {e}")
                # Model can still be used for prediction without compilation
            
            # ============================================================
            # Load scalers (with version compatibility handling)
            # ============================================================
            try:
                self.scaler_X = joblib.load(self.scaler_X_path)
                self.scaler_y = joblib.load(self.scaler_y_path)
                print(f"✅ Scalers loaded successfully")
                
            except Exception as e:
                print(f"❌ Scaler loading error: {e}")
                print(f"   This may indicate scikit-learn version mismatch")
                print(f"   Try: python scripts/regenerate_scalers.py")
                self.load_error = f"Scaler loading failed: {str(e)}"
                return
            
            # ============================================================
            # Load metadata
            # ============================================================
            if os.path.exists(self.metadata_path):
                import json
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)
                
                mae = self.metadata.get('mae', 'N/A')
                rmse = self.metadata.get('rmse', 'N/A')
                trend_acc = self.metadata.get('trend_accuracy', 'N/A')
                
                print(f"✅ Metadata loaded:")
                print(f"   MAE: {mae}")
                print(f"   RMSE: {rmse}")
                print(f"   Trend Accuracy: {trend_acc}%")
            
            self.model_available = True
            self.load_error = None
            print(f"✅ LSTM Trend Predictor ready")
            
        except Exception as e:
            self.load_error = f"Unexpected error: {str(e)}"
            print(f"❌ Error loading LSTM model: {e}")
            print(f"   Traceback:")
            import traceback
            traceback.print_exc()
            self.model_available = False
    
    def predict_trend(self, historical_esg_scores: List[float]) -> Optional[Dict[str, Any]]:
        """
        Predict ESG trend from historical scores
        
        Args:
            historical_esg_scores: List of 6 ESG scores (e.g., [60, 62, 65, 68, 70, 72])
        
        Returns:
            {
                'forecast': List of 6 future ESG scores,
                'trend': 'IMPROVING'/'STABLE'/'DECLINING',
                'change_pct': Percentage change,
                'confidence_mae': Model MAE,
                'trend_successful': True/False
            }
        """
        # Enhanced null checks
        if not TENSORFLOW_AVAILABLE:
            return {
                'trend_successful': False,
                'error': 'TensorFlow not installed',
                'trend': 'UNKNOWN'
            }
        
        if not self.model_available or self.model is None:
            return {
                'trend_successful': False,
                'error': self.load_error or 'LSTM model not available',
                'trend': 'UNKNOWN'
            }
        
        if self.scaler_X is None or self.scaler_y is None:
            return {
                'trend_successful': False,
                'error': 'Scalers not loaded',
                'trend': 'UNKNOWN'
            }
        
        try:
            # Validate input
            if len(historical_esg_scores) != 6:
                return {
                    'trend_successful': False,
                    'error': f'Expected 6 historical scores, got {len(historical_esg_scores)}',
                    'trend': 'UNKNOWN'
                }
            
            # Prepare input
            X_input = np.array(historical_esg_scores).reshape(1, -1)
            X_scaled = self.scaler_X.transform(X_input)
            X_scaled = X_scaled.reshape(1, 6, 1)  # (samples, timesteps, features)
            
            # Predict
            y_pred_scaled = self.model.predict(X_scaled, verbose=0)
            forecast = self.scaler_y.inverse_transform(y_pred_scaled)[0]
            
            # Detect trend
            trend, change_pct = self._detect_trend(forecast)
            
            return {
                'forecast': forecast.round(1).tolist(),
                'trend': trend,
                'change_pct': round(change_pct, 1),
                'confidence_mae': round(self.metadata.get('mae', 0), 2),
                'model_type': 'LSTM',
                'trend_successful': True
            }
            
        except Exception as e:
            return {
                'trend_successful': False,
                'error': str(e),
                'trend': 'UNKNOWN'
            }
    
    def _detect_trend(self, forecast: np.ndarray) -> tuple:
        """
        Classify trend as IMPROVING, STABLE, or DECLINING
        
        Args:
            forecast: Array of 6 future ESG scores
        
        Returns:
            (trend, change_pct)
        """
        start = forecast[:2].mean()  # Average of first 2 years
        end = forecast[-2:].mean()   # Average of last 2 years
        change_pct = ((end - start) / start) * 100
        
        if change_pct > 5:
            trend = "IMPROVING"
        elif change_pct < -5:
            trend = "DECLINING"
        else:
            trend = "STABLE"
        
        return trend, change_pct
    
    def predict_from_analysis(self, all_analyses: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract historical ESG scores from analyses and predict trend
        
        Args:
            all_analyses: Agent outputs containing temporal analysis
        
        Returns:
            Trend prediction result or None if data insufficient
        """
        try:
            # Extract historical ESG scores from temporal_analysis
            temporal = all_analyses.get('temporal_analysis', {})
            historical_scores = temporal.get('historical_esg_scores', [])
            
            if len(historical_scores) < 6:
                print(f"⚠️  Insufficient historical data ({len(historical_scores)}/6 years)")
                return None
            
            # Use last 6 scores
            recent_scores = historical_scores[-6:]
            
            return self.predict_trend(recent_scores)
            
        except Exception as e:
            print(f"❌ Error in predict_from_analysis: {e}")
            return None


# Singleton instance
_lstm_predictor = None

def get_lstm_predictor() -> LSTMTrendPredictor:
    """Get or create singleton LSTM predictor instance"""
    global _lstm_predictor
    if _lstm_predictor is None:
        _lstm_predictor = LSTMTrendPredictor()
    return _lstm_predictor
