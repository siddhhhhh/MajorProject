"""
Sentiment-ESG Correlation Model Training Script

Purpose: Train regression model to predict ESG score changes based on news sentiment
         Quantifies relationship between media coverage and future ESG performance

Model: Linear/Ridge/Lasso Regression
Dataset: Synthetic data simulating real-world sentiment-ESG patterns

Usage:
    python scripts/train_sentiment_esg_model.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import os
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class SentimentESGModelTrainer:
    """Train regression model for sentiment-to-ESG prediction"""
    
    def __init__(self, n_samples=2000):
        self.n_samples = n_samples
        self.df = None
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.feature_columns = None
        self.models = {}
        self.best_model = None
        self.best_model_name = None
        
        # Paths
        self.model_dir = 'ml_models/trained'
        self.reports_dir = 'reports'
        os.makedirs(self.model_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def generate_synthetic_data(self):
        """Generate synthetic training data simulating sentiment-ESG relationships"""
        
        print("="*70)
        print("📊 STEP 1: SYNTHETIC DATA GENERATION")
        print("="*70)
        
        print(f"\n🔧 Generating {self.n_samples} synthetic training samples...")
        print("   Based on real-world patterns:")
        print("   • Positive sentiment → ESG improvement")
        print("   • Controversies → ESG decline")
        print("   • High volume news → amplified effects")
        
        np.random.seed(42)
        
        # Base features
        news_sentiment = np.random.normal(0, 0.4, self.n_samples)  # Centered at 0
        news_sentiment = np.clip(news_sentiment, -1.0, 1.0)
        
        sentiment_volume = np.random.randint(1, 101, self.n_samples)
        controversy_level = np.random.choice([0, 1, 2, 3, 4, 5], 
                                            size=self.n_samples, 
                                            p=[0.4, 0.25, 0.15, 0.1, 0.07, 0.03])  # Most companies have low controversy
        
        current_esg_score = np.random.uniform(20, 90, self.n_samples)
        industry_volatility = np.random.uniform(0.5, 2.0, self.n_samples)
        
        # Target variable: ESG change over 6 months
        # Formula simulates real-world behavior
        esg_change = (
            news_sentiment * 15 +                    # Sentiment impact (±15 points max)
            sentiment_volume * 0.1 +                 # Volume amplification
            -controversy_level * 8 +                 # Controversy penalty
            current_esg_score * 0.05 +              # Baseline drift
            industry_volatility * news_sentiment * 5 + # Industry-specific sensitivity
            np.random.normal(0, 5, self.n_samples)  # Random noise
        )
        
        # Clip to realistic range
        esg_change = np.clip(esg_change, -30, 30)
        
        # Create DataFrame
        self.df = pd.DataFrame({
            'news_sentiment': news_sentiment,
            'sentiment_volume': sentiment_volume,
            'controversy_level': controversy_level,
            'current_esg_score': current_esg_score,
            'industry_volatility': industry_volatility,
            'esg_change_6months': esg_change
        })
        
        print(f"\n✅ Dataset created: {len(self.df)} samples")
        print(f"\n📋 Sample Data (first 10 rows):")
        print(self.df.head(10).to_string())
        
        print(f"\n📊 Dataset Statistics:")
        print(self.df.describe().round(2).to_string())
        
        print(f"\n🎯 Target Variable Distribution:")
        print(f"   ESG Change Range: [{self.df['esg_change_6months'].min():.1f}, {self.df['esg_change_6months'].max():.1f}]")
        print(f"   Mean Change: {self.df['esg_change_6months'].mean():.2f} points")
        print(f"   Std Dev: {self.df['esg_change_6months'].std():.2f} points")
    
    def engineer_features(self):
        """Create interaction features"""
        
        print("\n" + "="*70)
        print("🔧 STEP 2: FEATURE ENGINEERING")
        print("="*70)
        
        print("\n🔧 Creating interaction features...")
        
        # Interaction 1: Sentiment intensity (strong sentiment + high volume)
        self.df['sentiment_intensity'] = (
            self.df['news_sentiment'] * self.df['sentiment_volume']
        )
        
        # Interaction 2: Controversy-sentiment (scandal + negative news)
        self.df['controversy_sentiment'] = (
            self.df['controversy_level'] * self.df['news_sentiment']
        )
        
        # Interaction 3: Recovery potential (high ESG + positive news)
        self.df['recovery_potential'] = (
            self.df['current_esg_score'] * self.df['news_sentiment']
        )
        
        print("   ✅ sentiment_intensity (sentiment × volume)")
        print("   ✅ controversy_sentiment (controversy × sentiment)")
        print("   ✅ recovery_potential (ESG score × sentiment)")
        
        # Define feature columns
        self.feature_columns = [
            'news_sentiment',
            'sentiment_volume',
            'controversy_level',
            'current_esg_score',
            'industry_volatility',
            'sentiment_intensity',
            'controversy_sentiment',
            'recovery_potential'
        ]
        
        print(f"\n✅ Total features: {len(self.feature_columns)}")
        print(f"   Features: {', '.join(self.feature_columns)}")
    
    def split_data(self):
        """Split into train and test sets"""
        
        print("\n" + "="*70)
        print("✂️ STEP 3: TRAIN-TEST SPLIT")
        print("="*70)
        
        X = self.df[self.feature_columns]
        y = self.df['esg_change_6months']
        
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        print(f"\n✅ Data split:")
        print(f"   Training set:   {len(self.X_train)} samples ({len(self.X_train)/len(X)*100:.1f}%)")
        print(f"   Test set:       {len(self.X_test)} samples ({len(self.X_test)/len(X)*100:.1f}%)")
        print(f"\n   Training target - Mean: {self.y_train.mean():.2f}, Std: {self.y_train.std():.2f}")
        print(f"   Test target     - Mean: {self.y_test.mean():.2f}, Std: {self.y_test.std():.2f}")
    
    def train_models(self):
        """Train 3 regression models for comparison"""
        
        print("\n" + "="*70)
        print("🤖 STEP 4: MODEL TRAINING")
        print("="*70)
        
        print("\n🔧 Training 3 regression models...")
        
        # Model 1: Linear Regression (baseline)
        print("\n   1️⃣ Linear Regression (baseline)...")
        lr = LinearRegression()
        lr.fit(self.X_train, self.y_train)
        self.models['Linear'] = lr
        print("      ✅ Trained")
        
        # Model 2: Ridge Regression (L2 regularization)
        print("\n   2️⃣ Ridge Regression (alpha=1.0, L2 regularization)...")
        ridge = Ridge(alpha=1.0, random_state=42)
        ridge.fit(self.X_train, self.y_train)
        self.models['Ridge'] = ridge
        print("      ✅ Trained")
        
        # Model 3: Lasso Regression (L1 regularization)
        print("\n   3️⃣ Lasso Regression (alpha=0.1, L1 regularization)...")
        lasso = Lasso(alpha=0.1, random_state=42, max_iter=10000)
        lasso.fit(self.X_train, self.y_train)
        self.models['Lasso'] = lasso
        print("      ✅ Trained")
    
    def evaluate_models(self):
        """Evaluate and compare all models"""
        
        print("\n" + "="*70)
        print("📊 STEP 5: MODEL EVALUATION")
        print("="*70)
        
        results = []
        
        for name, model in self.models.items():
            # Predictions
            y_pred = model.predict(self.X_test)
            
            # Metrics
            mae = mean_absolute_error(self.y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(self.y_test, y_pred))
            r2 = r2_score(self.y_test, y_pred)
            
            # MAPE (avoid division by zero)
            mape = np.mean(np.abs((self.y_test - y_pred) / (self.y_test + 1e-10))) * 100
            
            results.append({
                'Model': name,
                'MAE': mae,
                'RMSE': rmse,
                'R²': r2,
                'MAPE': mape
            })
        
        # Create comparison DataFrame
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('MAE')
        
        print(f"\n📊 Model Comparison (Test Set):")
        print("="*70)
        print(f"{'Model':<15} {'MAE':<12} {'RMSE':<12} {'R²':<12} {'MAPE (%)':<12}")
        print("-"*70)
        for _, row in results_df.iterrows():
            print(f"{row['Model']:<15} {row['MAE']:<12.3f} {row['RMSE']:<12.3f} {row['R²']:<12.3f} {row['MAPE']:<12.2f}")
        print("="*70)
        
        # Select best model (lowest MAE)
        best_row = results_df.iloc[0]
        self.best_model_name = best_row['Model']
        self.best_model = self.models[self.best_model_name]
        
        print(f"\n🏆 Best Model: {self.best_model_name}")
        print(f"   MAE: {best_row['MAE']:.3f} points")
        print(f"   RMSE: {best_row['RMSE']:.3f} points")
        print(f"   R²: {best_row['R²']:.3f}")
        print(f"   MAPE: {best_row['MAPE']:.2f}%")
        
        return results_df
    
    def analyze_feature_importance(self):
        """Analyze feature importance from best model"""
        
        print("\n" + "="*70)
        print("🔍 STEP 6: FEATURE IMPORTANCE ANALYSIS")
        print("="*70)
        
        # Get coefficients
        coefficients = self.best_model.coef_
        
        # Create DataFrame
        importance_df = pd.DataFrame({
            'feature': self.feature_columns,
            'coefficient': coefficients,
            'abs_coefficient': np.abs(coefficients)
        })
        
        importance_df = importance_df.sort_values('abs_coefficient', ascending=False)
        
        print(f"\n📊 Feature Importance (Top 5 Most Influential):")
        print("="*70)
        print(f"{'Rank':<6} {'Feature':<30} {'Coefficient':<15} {'Impact':<10}")
        print("-"*70)
        for idx, (i, row) in enumerate(importance_df.head(5).iterrows(), 1):
            impact = "Positive" if row['coefficient'] > 0 else "Negative"
            print(f"{idx:<6} {row['feature']:<30} {row['coefficient']:<15.4f} {impact:<10}")
        
        print("\n💡 Interpretation:")
        top_feature = importance_df.iloc[0]
        if top_feature['coefficient'] > 0:
            print(f"   • {top_feature['feature']} has strongest positive effect")
            print(f"     → Each unit increase predicts +{top_feature['coefficient']:.2f} ESG point change")
        else:
            print(f"   • {top_feature['feature']} has strongest negative effect")
            print(f"     → Each unit increase predicts {top_feature['coefficient']:.2f} ESG point change")
        
        # Visualization
        plt.figure(figsize=(12, 6))
        colors = ['green' if x > 0 else 'red' for x in importance_df['coefficient']]
        plt.barh(importance_df['feature'], importance_df['coefficient'], color=colors, alpha=0.7)
        plt.xlabel('Coefficient (Impact on ESG Change)', fontsize=12)
        plt.ylabel('Feature', fontsize=12)
        plt.title(f'Feature Importance - {self.best_model_name} Model', fontsize=14, fontweight='bold')
        plt.axvline(x=0, color='black', linestyle='--', linewidth=1)
        plt.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        
        plot_path = os.path.join(self.reports_dir, 'sentiment_feature_importance.png')
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Feature importance plot saved: {plot_path}")
        plt.close()
        
        return importance_df
    
    def visualize_predictions(self):
        """Create prediction visualization"""
        
        print("\n" + "="*70)
        print("📈 STEP 7: PREDICTION VISUALIZATION")
        print("="*70)
        
        # Get predictions
        y_pred = self.best_model.predict(self.X_test)
        
        # Calculate R²
        r2 = r2_score(self.y_test, y_pred)
        
        # Get sentiment for coloring
        sentiment_colors = []
        for sentiment in self.X_test['news_sentiment']:
            if sentiment < -0.3:
                sentiment_colors.append('red')
            elif sentiment > 0.3:
                sentiment_colors.append('green')
            else:
                sentiment_colors.append('gray')
        
        # Create plot
        plt.figure(figsize=(12, 8))
        
        plt.scatter(self.y_test, y_pred, c=sentiment_colors, alpha=0.6, s=50, 
                   edgecolors='black', linewidth=0.5)
        
        # Perfect prediction line
        min_val = min(self.y_test.min(), y_pred.min())
        max_val = max(self.y_test.max(), y_pred.max())
        plt.plot([min_val, max_val], [min_val, max_val], 'b--', linewidth=2, 
                label='Perfect Prediction')
        
        plt.xlabel('Actual ESG Change (6 months)', fontsize=12)
        plt.ylabel('Predicted ESG Change (6 months)', fontsize=12)
        plt.title(f'Sentiment-to-ESG Predictions - {self.best_model_name} Model\nR² = {r2:.3f}', 
                 fontsize=14, fontweight='bold')
        
        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='green', alpha=0.6, label='Positive Sentiment'),
            Patch(facecolor='gray', alpha=0.6, label='Neutral Sentiment'),
            Patch(facecolor='red', alpha=0.6, label='Negative Sentiment'),
            plt.Line2D([0], [0], color='b', linestyle='--', linewidth=2, label='Perfect Prediction')
        ]
        plt.legend(handles=legend_elements, loc='upper left')
        
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        plot_path = os.path.join(self.reports_dir, 'sentiment_predictions_plot.png')
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        print(f"\n✅ Predictions plot saved: {plot_path}")
        plt.close()
    
    def save_artifacts(self):
        """Save model and metadata"""
        
        print("\n" + "="*70)
        print("💾 STEP 8: SAVING ARTIFACTS")
        print("="*70)
        
        # Save model
        model_path = os.path.join(self.model_dir, 'sentiment_esg_model.pkl')
        joblib.dump(self.best_model, model_path)
        print(f"\n✅ Model saved: {model_path}")
        
        # Save feature list
        features_path = os.path.join(self.model_dir, 'sentiment_features.pkl')
        joblib.dump(self.feature_columns, features_path)
        print(f"✅ Features saved: {features_path}")
        
        # Calculate metrics for metadata
        y_pred = self.best_model.predict(self.X_test)
        mae = mean_absolute_error(self.y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(self.y_test, y_pred))
        r2 = r2_score(self.y_test, y_pred)
        
        # Save metadata
        metadata = {
            'model_type': self.best_model_name,
            'training_date': datetime.now().isoformat(),
            'dataset_size': len(self.df),
            'train_size': len(self.X_train),
            'test_size': len(self.X_test),
            'features': self.feature_columns,
            'performance': {
                'mae': float(mae),
                'rmse': float(rmse),
                'r2': float(r2)
            },
            'interpretation': {
                'input': 'News sentiment, volume, controversy, current ESG, industry volatility',
                'output': 'Predicted ESG score change over 6 months (-30 to +30 points)',
                'use_case': 'Predict ESG impact of media coverage and controversies'
            }
        }
        
        metadata_path = os.path.join(self.model_dir, 'sentiment_model_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✅ Metadata saved: {metadata_path}")
    
    def test_prediction_function(self):
        """Test prediction function with example scenarios"""
        
        print("\n" + "="*70)
        print("🧪 STEP 9: TEST PREDICTION FUNCTION")
        print("="*70)
        
        # Calculate confidence interval (±2 RMSE)
        y_pred_test = self.best_model.predict(self.X_test)
        rmse = np.sqrt(mean_squared_error(self.y_test, y_pred_test))
        confidence_margin = 2 * rmse
        
        print(f"\n📊 Confidence Interval: ±{confidence_margin:.2f} points (95% confidence)")
        
        # Test scenarios
        scenarios = [
            {
                'name': "Scenario A: Major Scandal (Negative)",
                'data': {
                    'news_sentiment': -0.8,
                    'sentiment_volume': 85,
                    'controversy_level': 4,
                    'current_esg_score': 55,
                    'industry_volatility': 1.5
                },
                'expected': "Significant ESG decline expected"
            },
            {
                'name': "Scenario B: Positive Initiative Launch",
                'data': {
                    'news_sentiment': 0.7,
                    'sentiment_volume': 60,
                    'controversy_level': 0,
                    'current_esg_score': 70,
                    'industry_volatility': 1.0
                },
                'expected': "Moderate ESG improvement expected"
            },
            {
                'name': "Scenario C: Mixed Signals",
                'data': {
                    'news_sentiment': 0.2,
                    'sentiment_volume': 30,
                    'controversy_level': 2,
                    'current_esg_score': 50,
                    'industry_volatility': 1.2
                },
                'expected': "Minimal ESG change expected"
            }
        ]
        
        for scenario in scenarios:
            print(f"\n{'='*70}")
            print(f"📋 {scenario['name']}")
            print(f"{'='*70}")
            
            result = self._predict_esg_change(scenario['data'], confidence_margin)
            
            print(f"\n   Input Metrics:")
            for key, value in scenario['data'].items():
                print(f"      {key}: {value}")
            
            print(f"\n   📊 Prediction:")
            print(f"      ESG Change (6 months): {result['predicted_change']:+.2f} points")
            print(f"      Confidence Interval: ({result['confidence_interval'][0]:+.2f}, {result['confidence_interval'][1]:+.2f})")
            print(f"      Interpretation: {result['interpretation']}")
            print(f"\n   💡 Expected: {scenario['expected']}")
    
    def _predict_esg_change(self, input_data: dict, confidence_margin: float) -> dict:
        """Helper function to predict ESG change"""
        
        # Engineer interaction features
        input_data['sentiment_intensity'] = (
            input_data['news_sentiment'] * input_data['sentiment_volume']
        )
        input_data['controversy_sentiment'] = (
            input_data['controversy_level'] * input_data['news_sentiment']
        )
        input_data['recovery_potential'] = (
            input_data['current_esg_score'] * input_data['news_sentiment']
        )
        
        # Create DataFrame (preserve feature order)
        X_input = pd.DataFrame([[input_data[f] for f in self.feature_columns]], 
                              columns=self.feature_columns)
        
        # Predict
        prediction = self.best_model.predict(X_input)[0]
        
        # Confidence interval
        lower_bound = prediction - confidence_margin
        upper_bound = prediction + confidence_margin
        
        # Interpretation
        if prediction > 5:
            interpretation = f"Positive media coverage predicts +{prediction:.1f} point ESG improvement"
        elif prediction < -5:
            interpretation = f"Negative media coverage predicts {prediction:.1f} point ESG decline"
        else:
            interpretation = f"Mixed signals predict minimal ESG change ({prediction:+.1f} points)"
        
        return {
            'predicted_change': float(prediction),
            'confidence_interval': (float(lower_bound), float(upper_bound)),
            'interpretation': interpretation
        }
    
    def run_full_training(self):
        """Execute full training pipeline"""
        
        print("\n" + "="*70)
        print("🚀 SENTIMENT-ESG MODEL TRAINING")
        print("="*70)
        print(f"Training started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Step 1: Generate data
            self.generate_synthetic_data()
            
            # Step 2: Feature engineering
            self.engineer_features()
            
            # Step 3: Split data
            self.split_data()
            
            # Step 4: Train models
            self.train_models()
            
            # Step 5: Evaluate
            self.evaluate_models()
            
            # Step 6: Feature importance
            self.analyze_feature_importance()
            
            # Step 7: Visualize
            self.visualize_predictions()
            
            # Step 8: Save artifacts
            self.save_artifacts()
            
            # Step 9: Test
            self.test_prediction_function()
            
            print("\n" + "="*70)
            print("✅ TRAINING COMPLETE!")
            print("="*70)
            print("\n📦 Saved Artifacts:")
            print("   - ml_models/trained/sentiment_esg_model.pkl")
            print("   - ml_models/trained/sentiment_features.pkl")
            print("   - ml_models/trained/sentiment_model_metadata.json")
            print("   - reports/sentiment_feature_importance.png")
            print("   - reports/sentiment_predictions_plot.png")
            
            print("\n💡 Next Steps:")
            print("   1. Integrate into agents/sentiment_analyzer.py")
            print("   2. Use to predict ESG impact of news coverage")
            print("   3. Flag companies with high predicted ESG volatility")
            
        except Exception as e:
            print(f"\n❌ Error during training: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main entry point"""
    trainer = SentimentESGModelTrainer(n_samples=2000)
    trainer.run_full_training()


if __name__ == '__main__':
    main()
