"""
ESG Anomaly Detector Training Script

Purpose: Train Isolation Forest to detect companies with unusual ESG patterns
         that may indicate greenwashing or data inconsistencies.

Dataset: company_esg_financial_dataset.csv (11,000 rows)
Model: Isolation Forest (unsupervised anomaly detection)

Usage:
    python scripts/train_anomaly_detector.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class ESGAnomalyDetectorTrainer:
    """Train Isolation Forest for ESG anomaly detection"""
    
    def __init__(self, data_path='data/company_esg_financial_dataset.csv'):
        self.data_path = data_path
        self.df = None
        self.X_scaled = None
        self.feature_names = None
        self.scaler = None
        self.model = None
        self.results_df = None
        
        # Paths for saving
        self.model_dir = 'ml_models/trained'
        self.reports_dir = 'reports'
        os.makedirs(self.model_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def load_and_prepare_data(self):
        """Load dataset and engineer anomaly detection features"""
        
        print("="*70)
        print("📊 STEP 1: DATA LOADING & FEATURE ENGINEERING")
        print("="*70)
        
        # Load data
        self.df = pd.read_csv(self.data_path)
        print(f"\n✅ Dataset loaded: {len(self.df)} rows")
        print(f"   Columns: {list(self.df.columns)}")
        
        # Required base columns (rename if needed)
        column_mapping = {
            'Revenue': 'Revenue',
            'ProfitMargin': 'ProfitMargin', 
            'GrowthRate': 'GrowthRate',
            'CarbonEmissions': 'CarbonEmissions',
            'WaterUsage': 'WaterUsage',
            'EnergyConsumption': 'EnergyConsumption',
            'ESG_Overall': 'ESG_Overall',
            'ESG_Environmental': 'ESG_Environmental',
            'ESG_Social': 'ESG_Social',
            'ESG_Governance': 'ESG_Governance',
            'CompanyID': 'CompanyID',
            'CompanyName': 'CompanyName',
            'Industry': 'Industry',
            'Year': 'Year'
        }
        
        # Check which columns exist
        available_cols = {k: v for k, v in column_mapping.items() if k in self.df.columns}
        print(f"\n✅ Found {len(available_cols)} required columns")
        
        # Engineer anomaly detection features
        print("\n🔧 Engineering 8 anomaly detection features...")
        
        df_features = self.df.copy()
        
        # Feature 1: Carbon Intensity (emissions per dollar)
        df_features['carbon_intensity'] = df_features['CarbonEmissions'] / (df_features['Revenue'] + 1e-6)
        
        # Feature 2: Water Intensity (water per dollar)
        df_features['water_intensity'] = df_features['WaterUsage'] / (df_features['Revenue'] + 1e-6)
        
        # Feature 3: Energy Intensity (energy per dollar)
        df_features['energy_intensity'] = df_features['EnergyConsumption'] / (df_features['Revenue'] + 1e-6)
        
        # Feature 4: ESG-Revenue Gap (high ESG with low revenue = suspicious)
        df_features['esg_revenue_gap'] = (df_features['ESG_Overall'] - 50) / (np.log10(df_features['Revenue'] + 1) + 1e-6)
        
        # Feature 5: Growth-ESG Correlation (fast growth + high ESG = verify)
        df_features['growth_esg_correlation'] = df_features['GrowthRate'] * df_features['ESG_Overall'] / 100
        
        # Feature 6: Profit-ESG Ratio (low profit but high ESG = check)
        df_features['profit_esg_ratio'] = df_features['ProfitMargin'] / (df_features['ESG_Overall'] + 1e-6)
        
        # Feature 7: Environmental Balance (one pillar dominance = red flag)
        df_features['environmental_balance'] = df_features['ESG_Environmental'] / (
            df_features['ESG_Social'] + df_features['ESG_Governance'] + 1e-6
        )
        
        # Feature 8: Volatility Score (inconsistent scores = warning)
        # Calculate std dev of ESG_Overall per company across years
        esg_volatility = df_features.groupby('CompanyID')['ESG_Overall'].std().fillna(0)
        esg_volatility_dict = esg_volatility.to_dict()
        df_features['volatility_score'] = df_features['CompanyID'].map(esg_volatility_dict)
        
        print("   ✅ carbon_intensity")
        print("   ✅ water_intensity")
        print("   ✅ energy_intensity")
        print("   ✅ esg_revenue_gap")
        print("   ✅ growth_esg_correlation")
        print("   ✅ profit_esg_ratio")
        print("   ✅ environmental_balance")
        print("   ✅ volatility_score")
        
        # Group by company (take mean across years)
        print("\n🔄 Aggregating by CompanyID (mean across years)...")
        
        feature_cols = [
            'carbon_intensity', 'water_intensity', 'energy_intensity',
            'esg_revenue_gap', 'growth_esg_correlation', 'profit_esg_ratio',
            'environmental_balance', 'volatility_score'
        ]
        
        # Keep company info
        company_info = df_features.groupby('CompanyID').agg({
            'CompanyName': 'first',
            'Industry': 'first',
            'ESG_Overall': 'mean',
            'Revenue': 'mean',
            'ProfitMargin': 'mean'
        }).reset_index()
        
        # Aggregate features
        df_agg = df_features.groupby('CompanyID')[feature_cols].mean().reset_index()
        
        # Merge
        self.df = pd.merge(company_info, df_agg, on='CompanyID')
        
        # Remove rows with inf/nan
        initial_count = len(self.df)
        self.df = self.df.replace([np.inf, -np.inf], np.nan)
        self.df = self.df.dropna(subset=feature_cols)
        
        print(f"   Rows before cleaning: {initial_count}")
        print(f"   Rows after cleaning: {len(self.df)}")
        print(f"   Removed: {initial_count - len(self.df)} rows with missing/invalid values")
        
        # Extract features for training
        self.feature_names = feature_cols
        X = self.df[self.feature_names].values
        
        print(f"\n✅ Final dataset shape: {X.shape}")
        print(f"   Features: {len(self.feature_names)}")
        print(f"   Companies: {len(self.df)}")
        
        return X
    
    def train_model(self, X):
        """Train Isolation Forest model"""
        
        print("\n" + "="*70)
        print("🌲 STEP 2: MODEL TRAINING")
        print("="*70)
        
        # Standardize features
        print("\n🔧 Standardizing features (mean=0, std=1)...")
        self.scaler = StandardScaler()
        self.X_scaled = self.scaler.fit_transform(X)
        
        print("   Feature scaling applied:")
        for i, col in enumerate(self.feature_names):
            print(f"      {col}: mean={self.X_scaled[:, i].mean():.3f}, std={self.X_scaled[:, i].std():.3f}")
        
        # Train Isolation Forest
        print("\n🌲 Training Isolation Forest...")
        print("   Parameters:")
        print("      contamination: 0.05 (assume 5% anomalies)")
        print("      n_estimators: 100 (trees)")
        print("      max_samples: 256 (samples per tree)")
        print("      random_state: 42")
        
        self.model = IsolationForest(
            contamination=0.05,
            n_estimators=100,
            max_samples=256,
            random_state=42,
            n_jobs=-1,
            verbose=0
        )
        
        start_time = datetime.now()
        self.model.fit(self.X_scaled)
        training_time = (datetime.now() - start_time).total_seconds()
        
        print(f"\n✅ Training complete in {training_time:.2f} seconds!")
    
    def detect_anomalies(self):
        """Detect anomalies in the dataset"""
        
        print("\n" + "="*70)
        print("🔍 STEP 3: ANOMALY DETECTION")
        print("="*70)
        
        # Predict: 1 = normal, -1 = anomaly
        predictions = self.model.predict(self.X_scaled)
        
        # Anomaly scores (more negative = more anomalous)
        anomaly_scores = self.model.score_samples(self.X_scaled)
        
        # Create results DataFrame
        self.results_df = self.df.copy()
        self.results_df['anomaly_label'] = predictions
        self.results_df['anomaly_score'] = anomaly_scores
        self.results_df['is_anomaly'] = self.results_df['anomaly_label'] == -1
        
        # Statistics
        total_anomalies = (predictions == -1).sum()
        anomaly_pct = (total_anomalies / len(predictions)) * 100
        
        print(f"\n📊 Detection Results:")
        print(f"   Total companies analyzed: {len(predictions)}")
        print(f"   Anomalies detected: {total_anomalies} ({anomaly_pct:.2f}%)")
        print(f"   Normal companies: {(predictions == 1).sum()} ({100-anomaly_pct:.2f}%)")
        
        # Top 10 anomalies
        print("\n" + "="*70)
        print("🚨 TOP 10 MOST ANOMALOUS COMPANIES")
        print("="*70)
        
        top_anomalies = self.results_df.nsmallest(10, 'anomaly_score')
        
        print(f"\n{'Rank':<6} {'Company':<30} {'Industry':<20} {'Score':<12}")
        print("-" * 70)
        for idx, (i, row) in enumerate(top_anomalies.iterrows(), 1):
            company_name = row['CompanyName'][:28] if len(row['CompanyName']) > 28 else row['CompanyName']
            industry = row['Industry'][:18] if len(row['Industry']) > 18 else row['Industry']
            print(f"{idx:<6} {company_name:<30} {industry:<20} {row['anomaly_score']:<12.4f}")
        
        # Anomalies by industry
        print("\n" + "="*70)
        print("📊 ANOMALIES BY INDUSTRY")
        print("="*70)
        
        anomalies_by_industry = self.results_df[self.results_df['is_anomaly']].groupby('Industry').size().sort_values(ascending=False)
        
        print(f"\n{'Industry':<30} {'Anomaly Count':<15}")
        print("-" * 50)
        for industry, count in anomalies_by_industry.head(10).items():
            industry_short = industry[:28] if len(industry) > 28 else industry
            print(f"{industry_short:<30} {count:<15}")
    
    def visualize_results(self):
        """Create visualization of anomalies"""
        
        print("\n" + "="*70)
        print("📈 STEP 4: VISUALIZATION")
        print("="*70)
        
        # Create scatter plot
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        
        # Plot 1: Carbon Intensity vs ESG-Revenue Gap
        normal = self.results_df[self.results_df['anomaly_label'] == 1]
        anomalies = self.results_df[self.results_df['anomaly_label'] == -1]
        
        axes[0].scatter(normal['carbon_intensity'], normal['esg_revenue_gap'], 
                       alpha=0.5, s=50, c='blue', label=f'Normal ({len(normal)})')
        axes[0].scatter(anomalies['carbon_intensity'], anomalies['esg_revenue_gap'], 
                       alpha=0.7, s=80, c='red', marker='X', label=f'Anomaly ({len(anomalies)})')
        
        axes[0].set_xlabel('Carbon Intensity (emissions/$)', fontsize=12)
        axes[0].set_ylabel('ESG-Revenue Gap', fontsize=12)
        axes[0].set_title('Anomaly Detection: Carbon vs ESG-Revenue', fontsize=14, fontweight='bold')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Plot 2: Anomaly Score Distribution
        axes[1].hist(normal['anomaly_score'], bins=50, alpha=0.6, color='blue', label='Normal')
        axes[1].hist(anomalies['anomaly_score'], bins=30, alpha=0.8, color='red', label='Anomaly')
        axes[1].axvline(self.results_df['anomaly_score'].quantile(0.05), 
                       color='black', linestyle='--', linewidth=2, label='5% Threshold')
        
        axes[1].set_xlabel('Anomaly Score', fontsize=12)
        axes[1].set_ylabel('Frequency', fontsize=12)
        axes[1].set_title('Anomaly Score Distribution', fontsize=14, fontweight='bold')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save plot
        plot_path = os.path.join(self.reports_dir, 'anomaly_detection_plot.png')
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Visualization saved: {plot_path}")
        
        plt.close()
    
    def save_artifacts(self):
        """Save model, scaler, and results"""
        
        print("\n" + "="*70)
        print("💾 STEP 5: SAVING ARTIFACTS")
        print("="*70)
        
        # Save model
        model_path = os.path.join(self.model_dir, 'anomaly_detector.pkl')
        joblib.dump(self.model, model_path)
        print(f"\n✅ Model saved: {model_path}")
        
        # Save scaler
        scaler_path = os.path.join(self.model_dir, 'anomaly_scaler.pkl')
        joblib.dump(self.scaler, scaler_path)
        print(f"✅ Scaler saved: {scaler_path}")
        
        # Save feature names
        features_path = os.path.join(self.model_dir, 'anomaly_features.pkl')
        joblib.dump(self.feature_names, features_path)
        print(f"✅ Feature names saved: {features_path}")
        
        # Save results CSV
        results_path = os.path.join(self.reports_dir, 'detected_anomalies.csv')
        
        # Include only anomalies in CSV
        anomalies_df = self.results_df[self.results_df['is_anomaly']].copy()
        anomalies_df = anomalies_df.sort_values('anomaly_score')
        
        # Select relevant columns
        export_cols = [
            'CompanyID', 'CompanyName', 'Industry', 
            'ESG_Overall', 'Revenue', 'ProfitMargin',
            'anomaly_score'
        ] + self.feature_names
        
        anomalies_df[export_cols].to_csv(results_path, index=False)
        print(f"✅ Anomaly results saved: {results_path}")
        print(f"   ({len(anomalies_df)} anomalous companies exported)")
        
        # Save metadata
        metadata = {
            'training_date': datetime.now().isoformat(),
            'dataset_size': len(self.df),
            'features': self.feature_names,
            'contamination': 0.05,
            'n_estimators': 100,
            'anomalies_detected': int((self.results_df['is_anomaly']).sum()),
            'anomaly_percentage': float((self.results_df['is_anomaly'].sum() / len(self.results_df)) * 100)
        }
        
        metadata_path = os.path.join(self.model_dir, 'anomaly_metadata.json')
        import json
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✅ Metadata saved: {metadata_path}")
    
    def test_prediction(self):
        """Test the trained model with sample companies"""
        
        print("\n" + "="*70)
        print("🧪 STEP 6: TESTING PREDICTION FUNCTION")
        print("="*70)
        
        # Sample 1: Normal company
        print("\n📋 Test Case 1: Normal Company")
        normal_sample = {
            'carbon_intensity': 0.0001,
            'water_intensity': 0.002,
            'energy_intensity': 0.0015,
            'esg_revenue_gap': 0.5,
            'growth_esg_correlation': 3.0,
            'profit_esg_ratio': 0.3,
            'environmental_balance': 1.0,
            'volatility_score': 2.0
        }
        
        result1 = self._predict_sample(normal_sample)
        print(f"   Result: {result1}")
        
        # Sample 2: Anomalous company (extreme values)
        print("\n📋 Test Case 2: Anomalous Company")
        anomalous_sample = {
            'carbon_intensity': 0.01,      # Very high carbon
            'water_intensity': 0.05,       # Very high water usage
            'energy_intensity': 0.008,     # Very high energy
            'esg_revenue_gap': -5.0,       # Low ESG, high revenue (suspicious)
            'growth_esg_correlation': -2.0, # Negative correlation
            'profit_esg_ratio': 2.0,       # High profit but low ESG
            'environmental_balance': 3.0,  # Imbalanced pillars
            'volatility_score': 15.0       # Very volatile ESG scores
        }
        
        result2 = self._predict_sample(anomalous_sample)
        print(f"   Result: {result2}")
    
    def _predict_sample(self, company_data: dict) -> dict:
        """Helper function to predict on a single sample"""
        
        # Extract features in correct order
        X_sample = np.array([[company_data[f] for f in self.feature_names]])
        
        # Scale
        X_scaled = self.scaler.transform(X_sample)
        
        # Predict
        prediction = self.model.predict(X_scaled)[0]
        anomaly_score = self.model.score_samples(X_scaled)[0]
        
        # Calculate confidence (normalized distance from threshold)
        threshold = self.results_df['anomaly_score'].quantile(0.05)
        confidence = abs(anomaly_score - threshold) / abs(threshold) * 100
        confidence = min(confidence, 100)
        
        return {
            'is_anomaly': prediction == -1,
            'anomaly_score': round(float(anomaly_score), 4),
            'confidence': round(float(confidence), 2)
        }
    
    def run_full_training(self):
        """Execute full training pipeline"""
        
        print("\n" + "="*70)
        print("🚀 ESG ANOMALY DETECTOR TRAINING")
        print("="*70)
        print(f"Dataset: {self.data_path}")
        print(f"Training started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Step 1: Load and prepare data
            X = self.load_and_prepare_data()
            
            # Step 2: Train model
            self.train_model(X)
            
            # Step 3: Detect anomalies
            self.detect_anomalies()
            
            # Step 4: Visualize
            self.visualize_results()
            
            # Step 5: Save artifacts
            self.save_artifacts()
            
            # Step 6: Test
            self.test_prediction()
            
            print("\n" + "="*70)
            print("✅ TRAINING COMPLETE!")
            print("="*70)
            print("\n📦 Saved Artifacts:")
            print("   - ml_models/trained/anomaly_detector.pkl")
            print("   - ml_models/trained/anomaly_scaler.pkl")
            print("   - ml_models/trained/anomaly_features.pkl")
            print("   - ml_models/trained/anomaly_metadata.json")
            print("   - reports/detected_anomalies.csv")
            print("   - reports/anomaly_detection_plot.png")
            
        except Exception as e:
            print(f"\n❌ Error during training: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main entry point"""
    trainer = ESGAnomalyDetectorTrainer()
    trainer.run_full_training()


if __name__ == '__main__':
    main()
