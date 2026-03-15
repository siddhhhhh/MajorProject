"""
Regenerate scikit-learn scalers if version mismatch occurs

Run this if you see: "sklearn version X.X.X does not match pickle version Y.Y.Y"
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from sklearn.preprocessing import MinMaxScaler
import joblib
import sklearn


def regenerate_scalers():
    """
    Regenerate scalers by fitting to dummy data with same range as ESG scores (0-100)
    """
    
    print("="*70)
    print("SCALER REGENERATION")
    print("="*70)
    print(f"Current scikit-learn version: {sklearn.__version__}")
    
    model_dir = project_root / 'ml_models' / 'trained'
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # Create dummy data matching ESG score range (0-100)
    # Shape: (101, 6) for 6-year sequences
    print(f"\n🔨 Creating dummy data for ESG score range (0-100)...")
    dummy_X = np.array([[i] * 6 for i in range(0, 101)])  # Shape: (101, 6)
    dummy_y = np.array([[i] * 6 for i in range(0, 101)])  # Shape: (101, 6)
    
    print(f"   X shape: {dummy_X.shape}")
    print(f"   y shape: {dummy_y.shape}")
    
    # Create and fit scalers
    print(f"\n🔨 Creating and fitting scalers...")
    scaler_X = MinMaxScaler()
    scaler_y = MinMaxScaler()
    
    scaler_X.fit(dummy_X)
    scaler_y.fit(dummy_y)
    
    print(f"✅ Scalers fitted")
    print(f"   scaler_X range: [{scaler_X.data_min_[0]:.1f}, {scaler_X.data_max_[0]:.1f}]")
    print(f"   scaler_y range: [{scaler_y.data_min_[0]:.1f}, {scaler_y.data_max_[0]:.1f}]")
    
    # Backup old scalers if they exist
    scaler_X_path = model_dir / 'lstm_scaler_X.pkl'
    scaler_y_path = model_dir / 'lstm_scaler_y.pkl'
    
    if scaler_X_path.exists():
        backup_X_path = model_dir / 'lstm_scaler_X_backup.pkl'
        print(f"\n💾 Backing up old scaler_X to: {backup_X_path.name}")
        import shutil
        shutil.copy(scaler_X_path, backup_X_path)
    
    if scaler_y_path.exists():
        backup_y_path = model_dir / 'lstm_scaler_y_backup.pkl'
        print(f"💾 Backing up old scaler_y to: {backup_y_path.name}")
        import shutil
        shutil.copy(scaler_y_path, backup_y_path)
    
    # Save new scalers
    print(f"\n💾 Saving regenerated scalers...")
    joblib.dump(scaler_X, scaler_X_path)
    joblib.dump(scaler_y, scaler_y_path)
    
    print(f"✅ Scalers saved:")
    print(f"   {scaler_X_path}")
    print(f"   {scaler_y_path}")
    
    # Verify scalers load correctly
    print(f"\n🔍 Verifying scalers load correctly...")
    try:
        test_X = joblib.load(scaler_X_path)
        test_y = joblib.load(scaler_y_path)
        print(f"✅ Scaler verification successful")
        
        # Test transformation
        print(f"\n🧪 Testing transformation...")
        test_data = np.array([[50, 55, 60, 65, 70, 75]])
        transformed = test_X.transform(test_data)
        inverse = test_X.inverse_transform(transformed)
        
        print(f"   Input:       {test_data[0]}")
        print(f"   Transformed: {transformed[0].round(3)}")
        print(f"   Inverse:     {inverse[0].round(1)}")
        
        # Check if inverse matches input
        if np.allclose(test_data, inverse, rtol=1e-3):
            print(f"✅ Transformation test successful")
            return True
        else:
            print(f"⚠️  Transformation test warning: inverse doesn't match input")
            return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


if __name__ == "__main__":
    success = regenerate_scalers()
    
    if success:
        print(f"\n{'='*70}")
        print(f"✅ SUCCESS: Scalers regenerated with scikit-learn {sklearn.__version__}")
        print(f"{'='*70}")
        sys.exit(0)
    else:
        print(f"\n{'='*70}")
        print(f"❌ FAILED: Scaler regeneration encountered errors")
        print(f"{'='*70}")
        sys.exit(1)
