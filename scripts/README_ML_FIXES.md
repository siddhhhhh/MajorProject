# ML Model Compatibility Utilities

This directory contains utility scripts to fix ML model compatibility issues after library upgrades.

## 🚨 Common Issues & Solutions

### Issue 1: LSTM Model Loading Error

**Error Message:**
```
Could not deserialize 'keras.metrics.mse' because it is not a KerasSaveable subclass
```

**Root Cause:**
- TensorFlow/Keras 2.15+ changed how metrics are serialized
- Old models saved with TF 2.14 or earlier may fail to load

**Solution:**
```bash
python scripts/test_lstm_loading.py
```

If loading fails, regenerate the model:
```bash
python scripts/regenerate_lstm_model.py
```

---

### Issue 2: Scaler Version Mismatch

**Error Message:**
```
sklearn version X.X.X does not match pickle version Y.Y.Y
```

**Root Cause:**
- scikit-learn changed pickle format between versions
- Old scalers may not load in newer sklearn versions

**Solution:**
```bash
python scripts/regenerate_scalers.py
```

---

## 📁 Script Descriptions

### `test_lstm_loading.py`
**Purpose:** Test if LSTM model loads correctly with current TensorFlow version

**Usage:**
```bash
python scripts/test_lstm_loading.py
```

**Expected Output (Success):**
```
✅ TensorFlow version: 2.15.0
✅ LSTM model loaded successfully!
✅ Prediction successful!
   Input:      [60, 62, 65, 68, 70, 72]
   Forecast:   [73.2, 74.5, 75.8, 77.1, 78.4, 79.7]
   Trend:      IMPROVING
   Change:     8.6%
   Model MAE:  2.34
```

---

### `regenerate_lstm_model.py`
**Purpose:** Regenerate LSTM model file with current TensorFlow version

**When to Use:**
- After upgrading TensorFlow
- When model fails to load with deserialization errors
- After changing Keras configuration

**Usage:**
```bash
python scripts/regenerate_lstm_model.py
```

**What It Does:**
1. Loads old model architecture and weights
2. Creates new model with same architecture
3. Transfers weights to new model
4. Saves with current TensorFlow version
5. Backs up old model to `lstm_trend_forecaster_backup.h5`

**Requirements:**
- Original model file must exist: `ml_models/trained/lstm_trend_forecaster.h5`
- TensorFlow must be installed

---

### `regenerate_scalers.py`
**Purpose:** Regenerate scikit-learn scalers with current version

**When to Use:**
- After upgrading scikit-learn
- When scalers fail to load with version mismatch errors
- When encountering pickle compatibility issues

**Usage:**
```bash
python scripts/regenerate_scalers.py
```

**What It Does:**
1. Creates dummy data matching ESG score range (0-100)
2. Fits new scalers to dummy data
3. Saves scalers with current scikit-learn version
4. Backs up old scalers

**Note:**
- Scalers fitted to dummy data maintain same transformation properties
- ESG score range is always 0-100, so dummy data is representative

---

## 🔧 Manual Fixes

### Fix 1: Check Library Versions

```bash
# Check current versions
python -c "import tensorflow as tf; print(f'TensorFlow: {tf.__version__}')"
python -c "import sklearn; print(f'scikit-learn: {sklearn.__version__}')"
```

### Fix 2: Upgrade Libraries

```bash
# Upgrade to latest compatible versions
pip install tensorflow>=2.15.0 --upgrade
pip install scikit-learn>=1.3.0 --upgrade
```

### Fix 3: Retrain Models (Last Resort)

If regeneration scripts fail, retrain models from scratch:

**LSTM Model:**
```bash
jupyter notebook notebooks/train_lstm_trend.ipynb
```

**Other Models:**
```bash
python scripts/train_xgboost_risk.py
python scripts/train_lightgbm_esg.py
python scripts/train_anomaly_detector.py
```

---

## 📊 Compatibility Matrix

| TensorFlow | Keras | scikit-learn | Status |
|------------|-------|--------------|--------|
| 2.15.x     | 2.15.x| 1.3.x-1.5.x  | ✅ Compatible |
| 2.14.x     | 2.14.x| 1.3.x-1.5.x  | ⚠️ May need regeneration |
| 2.13.x     | 2.13.x| 1.2.x-1.5.x  | ❌ Regenerate required |

---

## 🐛 Troubleshooting

### Model Still Fails to Load

1. **Check file exists:**
   ```bash
   ls ml_models/trained/lstm_trend_forecaster.h5
   ```

2. **Check file permissions:**
   ```bash
   # On Windows
   icacls ml_models/trained/lstm_trend_forecaster.h5
   ```

3. **Try manual verification:**
   ```python
   from tensorflow.keras.models import load_model
   model = load_model('ml_models/trained/lstm_trend_forecaster.h5', compile=False)
   print(model.summary())
   ```

### Scaler Regeneration Doesn't Work

1. **Check scikit-learn version:**
   ```bash
   pip show scikit-learn
   ```

2. **Reinstall scikit-learn:**
   ```bash
   pip uninstall scikit-learn -y
   pip install scikit-learn==1.7.2
   ```

3. **Clear Python cache:**
   ```bash
   find . -type d -name __pycache__ -exec rm -rf {} +
   ```

---

## 📝 Additional Notes

### Why These Issues Occur

**TensorFlow/Keras:**
- Breaking changes in serialization format between major versions
- Metric/loss function registration changed in 2.15+
- Custom objects handling was redesigned

**scikit-learn:**
- Pickle format changes between versions
- Security improvements affect deserialization
- Internal API changes for transformer objects

### Prevention

To avoid these issues in the future:

1. **Pin library versions in requirements.txt:**
   ```
   tensorflow==2.15.0
   scikit-learn==1.7.2
   ```

2. **Test after upgrades:**
   ```bash
   python scripts/test_lstm_loading.py
   ```

3. **Keep backups:**
   - Model files are automatically backed up during regeneration
   - Store original training notebooks in version control

---

## 🆘 Getting Help

If issues persist:

1. Check error logs in script output
2. Verify TensorFlow GPU support (if using GPU)
3. Check for conflicting package versions
4. Retrain models as last resort

For persistent issues, file a bug report with:
- TensorFlow version
- scikit-learn version
- Full error traceback
- Output from `test_lstm_loading.py`
