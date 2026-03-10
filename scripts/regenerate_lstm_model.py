"""
Regenerate LSTM model with current TensorFlow/Keras version

Run this script if you encounter model loading errors after upgrading TensorFlow
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from tensorflow import keras
from tensorflow.keras.models import load_model, Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.losses import MeanSquaredError
from tensorflow.keras.metrics import MeanAbsoluteError
from sklearn.preprocessing import MinMaxScaler
import joblib
import json


def regenerate_lstm_model():
    """
    Regenerate LSTM model by loading old weights and resaving with current TF version
    """
    
    print("="*70)
    print("LSTM MODEL REGENERATION")
    print("="*70)
    
    model_dir = project_root / 'ml_models' / 'trained'
    old_model_path = model_dir / 'lstm_trend_forecaster.h5'
    
    if not old_model_path.exists():
        print(f"❌ Model not found at: {old_model_path}")
        print(f"   Please train model first using notebooks/train_lstm_trend.ipynb")
        return False
    
    try:
        # Load old model architecture
        print(f"\n🔄 Loading existing model...")
        
        old_model = load_model(
            str(old_model_path),
            custom_objects={
                'mse': MeanSquaredError(),
                'mae': MeanAbsoluteError()
            },
            compile=False
        )
        
        print(f"✅ Old model loaded")
        
        # Extract weights
        weights = old_model.get_weights()
        print(f"✅ Extracted {len(weights)} weight tensors")
        
        # Create new model with same architecture
        print(f"\n🔨 Creating new model with current TF version...")
        
        new_model = Sequential([
            LSTM(50, activation='relu', return_sequences=True, input_shape=(6, 1)),
            Dropout(0.2),
            LSTM(50, activation='relu'),
            Dropout(0.2),
            Dense(6)
        ])
        
        # Set weights from old model
        new_model.set_weights(weights)
        
        # Compile with current TF/Keras
        new_model.compile(
            optimizer='adam',
            loss='mse',
            metrics=['mae']
        )
        
        print(f"✅ New model created and compiled")
        
        # Save new model
        backup_path = model_dir / 'lstm_trend_forecaster_backup.h5'
        new_model_path = model_dir / 'lstm_trend_forecaster.h5'
        
        # Backup old model
        if old_model_path.exists():
            print(f"\n💾 Backing up old model to: {backup_path.name}")
            import shutil
            shutil.copy(old_model_path, backup_path)
        
        # Save new model
        print(f"💾 Saving regenerated model to: {new_model_path.name}")
        new_model.save(str(new_model_path))
        
        print(f"\n✅ Model regeneration complete!")
        print(f"   Old model backed up: {backup_path}")
        print(f"   New model saved: {new_model_path}")
        
        # Verify it loads correctly
        print(f"\n🔍 Verifying new model loads correctly...")
        test_model = load_model(
            str(new_model_path),
            custom_objects={
                'mse': MeanSquaredError(),
                'mae': MeanAbsoluteError()
            }
        )
        print(f"✅ New model verification successful")
        
        # Test prediction
        print(f"\n🧪 Testing prediction...")
        test_input = np.array([[60, 62, 65, 68, 70, 72]]).reshape(1, 6, 1)
        test_output = test_model.predict(test_input, verbose=0)
        print(f"✅ Prediction test successful (output shape: {test_output.shape})")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Regeneration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = regenerate_lstm_model()
    sys.exit(0 if success else 1)
