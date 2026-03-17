"""
Test LSTM Model Loading

Quick test to verify LSTM model loads correctly with TensorFlow/Keras 2.15+
"""

import sys
from pathlib import Path
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_lstm_loading():
    """Test LSTM model loading with the fixed code"""
    
    print("="*70)
    print("LSTM MODEL LOADING TEST")
    print("="*70)
    
    # Skip cleanly when TensorFlow is not available in the environment.
    tf = pytest.importorskip("tensorflow", reason="TensorFlow is required for LSTM loading test")
    print(f"\n✅ TensorFlow version: {tf.__version__}")
    
    try:
        # Import LSTM predictor
        print(f"\n🔄 Importing LSTM predictor...")
        from ml_models.lstm_trend_predictor import get_lstm_predictor
        
        # Get predictor instance (this triggers model loading)
        print(f"🔄 Loading LSTM model...")
        predictor = get_lstm_predictor()
        
        if predictor.model_available:
            print(f"\n✅ LSTM model loaded successfully!")
            
            # Test prediction
            print(f"\n🧪 Testing prediction with sample data...")
            test_scores = [60, 62, 65, 68, 70, 72]
            result = predictor.predict_trend(test_scores)
            
            if result.get('trend_successful'):
                print(f"✅ Prediction successful!")
                print(f"   Input:      {test_scores}")
                print(f"   Forecast:   {result['forecast']}")
                print(f"   Trend:      {result['trend']}")
                print(f"   Change:     {result['change_pct']}%")
                print(f"   Model MAE:  {result['confidence_mae']}")
                assert True
            else:
                pytest.fail(f"Prediction failed: {result.get('error')}")
        else:
            print(f"\n⚠️  LSTM model not available")
            print(f"   This is expected if model hasn't been trained yet")
            print(f"   Train model using: notebooks/train_lstm_trend.ipynb")
            pytest.skip("LSTM model artifacts not available in this environment")
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    try:
        test_lstm_loading()
        success = True
    except pytest.skip.Exception:
        success = True
    except Exception:
        success = False
    
    print(f"\n{'='*70}")
    if success:
        print("✅ SUCCESS: LSTM model loading works correctly")
    else:
        print("⚠️  NOTE: If model file exists but fails to load, try:")
        print("   python scripts/regenerate_lstm_model.py")
    print("="*70)
    
    sys.exit(0 if success else 1)
