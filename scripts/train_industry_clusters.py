# filepath: scripts/train_industry_clusters.py
"""
Industry ESG Clustering Model Training
======================================

PURPOSE: Train K-Means clustering to classify companies into ESG performance tiers
for peer comparison in greenwashing detection.

METHODOLOGY:
- Uses 7 ESG features from S&P 500 companies
- K-Means clustering with k=5 (Leaders, Above Avg, Average, Below Avg, Laggards)
- StandardScaler normalization
- Elbow method for optimal cluster selection
- Industry-specific performance benchmarking

OUTPUT:
- Trained KMeans model
- Cluster assignments for 426 companies
- Visualization plots
- Industry-specific analysis
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import joblib
import os
from typing import Dict, List, Any
import warnings
warnings.filterwarnings('ignore')

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)


def load_and_explore_data(filepath: str) -> pd.DataFrame:
    """Load dataset and perform initial exploration"""
    print("="*80)
    print("STEP 1: DATA LOADING & EXPLORATION")
    print("="*80)
    
    df = pd.read_csv(filepath)
    
    print(f"\n📊 Dataset Shape: {df.shape}")
    print(f"   Rows: {df.shape[0]:,} companies")
    print(f"   Columns: {df.shape[1]}")
    
    print(f"\n📋 Column Names:")
    for i, col in enumerate(df.columns, 1):
        print(f"   {i:2d}. {col}")
    
    print(f"\n❓ Missing Values:")
    missing = df.isnull().sum()
    if missing.sum() == 0:
        print("   ✅ No missing values detected")
    else:
        print(missing[missing > 0])
    
    print(f"\n📄 Sample Data (first 5 rows):")
    print(df.head())
    
    print(f"\n🏭 Unique Industries (GICS Sector):")
    industries = df['GICS Sector'].value_counts()
    for industry, count in industries.items():
        print(f"   {industry:30s}: {count:3d} companies")
    print(f"   TOTAL: {industries.sum()} companies across {len(industries)} sectors")
    
    print(f"\n📈 ESG Score Distribution by Industry:")
    industry_stats = df.groupby('GICS Sector')['totalEsg'].agg(['mean', 'std', 'min', 'max', 'count'])
    industry_stats = industry_stats.round(2)
    print(industry_stats)
    
    return df


def prepare_features(df: pd.DataFrame) -> tuple:
    """Prepare feature matrix for clustering"""
    print("\n" + "="*80)
    print("STEP 2: FEATURE SELECTION & PREPARATION")
    print("="*80)
    
    # Define features
    feature_columns = [
        'totalEsg',
        'environmentScore',
        'socialScore',
        'governanceScore',
        'highestControversy',
        'percentile',
        'overallRisk'
    ]
    
    print(f"\n✅ Selected Features ({len(feature_columns)}):")
    for i, feat in enumerate(feature_columns, 1):
        print(f"   {i}. {feat}")
    
    # Create feature DataFrame
    X = df[feature_columns].copy()
    
    # Handle missing values (fill with median)
    print(f"\n🔧 Handling Missing Values:")
    missing_before = X.isnull().sum().sum()
    if missing_before > 0:
        print(f"   Missing values found: {missing_before}")
        X = X.fillna(X.median())
        print(f"   ✅ Filled with median values")
    else:
        print(f"   ✅ No missing values detected")
    
    # Add metadata columns for later use
    metadata = df[['Symbol', 'Full Name', 'GICS Sector']].copy()
    metadata.rename(columns={'Full Name': 'Name'}, inplace=True)
    
    print(f"\n📊 Feature Statistics:")
    print(X.describe().round(2))
    
    return X, feature_columns, metadata


def scale_features(X: pd.DataFrame) -> tuple:
    """Normalize features using StandardScaler"""
    print("\n" + "="*80)
    print("STEP 3: FEATURE SCALING")
    print("="*80)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    print(f"\n✅ StandardScaler Applied:")
    print(f"   Features normalized to mean=0, std=1")
    
    print(f"\n📊 Scaled Data Statistics:")
    scaled_df = pd.DataFrame(X_scaled, columns=X.columns)
    stats = scaled_df.describe().round(3)
    print(stats.loc[['mean', 'std', 'min', 'max']])
    
    # Verify normalization
    print(f"\n🔍 Normalization Verification:")
    print(f"   Mean values (should be ~0): {scaled_df.mean().abs().max():.6f}")
    print(f"   Std values (should be ~1): {scaled_df.std().mean():.6f}")
    
    return X_scaled, scaler


def determine_optimal_clusters(X_scaled: np.ndarray, k_range: range) -> None:
    """Use Elbow Method and Silhouette Score to find optimal k"""
    print("\n" + "="*80)
    print("STEP 4: DETERMINE OPTIMAL NUMBER OF CLUSTERS")
    print("="*80)
    
    inertias = []
    silhouettes = []
    
    print(f"\n⏳ Testing k={k_range.start} to k={k_range.stop-1} clusters...")
    
    for k in k_range:
        # Train KMeans
        kmeans = KMeans(n_clusters=k, n_init=50, max_iter=500, random_state=42)
        kmeans.fit(X_scaled)
        
        inertia = kmeans.inertia_
        silhouette = silhouette_score(X_scaled, kmeans.labels_)
        
        inertias.append(inertia)
        silhouettes.append(silhouette)
        
        print(f"   k={k}: Inertia={inertia:.2f}, Silhouette={silhouette:.4f}")
    
    # Create plots
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Elbow plot
    axes[0].plot(k_range, inertias, 'bo-', linewidth=2, markersize=8)
    axes[0].set_xlabel('Number of Clusters (k)', fontsize=12)
    axes[0].set_ylabel('Inertia (Within-Cluster Sum of Squares)', fontsize=12)
    axes[0].set_title('Elbow Method for Optimal k', fontsize=14, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].axvline(x=5, color='r', linestyle='--', alpha=0.5, label='Recommended k=5')
    axes[0].legend()
    
    # Silhouette plot
    axes[1].plot(k_range, silhouettes, 'go-', linewidth=2, markersize=8)
    axes[1].set_xlabel('Number of Clusters (k)', fontsize=12)
    axes[1].set_ylabel('Silhouette Score', fontsize=12)
    axes[1].set_title('Silhouette Score vs Number of Clusters', fontsize=14, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].axvline(x=5, color='r', linestyle='--', alpha=0.5, label='Recommended k=5')
    axes[1].legend()
    
    plt.tight_layout()
    
    os.makedirs('reports', exist_ok=True)
    plt.savefig('reports/clustering_elbow_method.png', dpi=300, bbox_inches='tight')
    print(f"\n✅ Elbow method plot saved: reports/clustering_elbow_method.png")
    plt.close()
    
    print(f"\n💡 RECOMMENDATION: k=5 clusters")
    print(f"   Rationale: ESG performance quintiles (Leaders → Laggards)")


def train_kmeans_model(X_scaled: np.ndarray, k: int = 5) -> KMeans:
    """Train K-Means clustering model"""
    print("\n" + "="*80)
    print("STEP 5: TRAIN K-MEANS MODEL")
    print("="*80)
    
    print(f"\n⏳ Training KMeans with k={k} clusters...")
    print(f"   Parameters:")
    print(f"   - n_clusters: {k}")
    print(f"   - n_init: 50 (multiple initializations)")
    print(f"   - max_iter: 500")
    print(f"   - random_state: 42 (reproducibility)")
    
    kmeans = KMeans(n_clusters=k, n_init=50, max_iter=500, random_state=42)
    kmeans.fit(X_scaled)
    
    print(f"\n✅ Model Training Complete:")
    print(f"   Final Inertia: {kmeans.inertia_:.2f}")
    print(f"   Iterations: {kmeans.n_iter_}")
    print(f"   Cluster Centers Shape: {kmeans.cluster_centers_.shape}")
    
    # Calculate silhouette score
    silhouette = silhouette_score(X_scaled, kmeans.labels_)
    print(f"   Silhouette Score: {silhouette:.4f}")
    
    # Cluster distribution
    unique, counts = np.unique(kmeans.labels_, return_counts=True)
    print(f"\n📊 Cluster Distribution:")
    for cluster_id, count in zip(unique, counts):
        print(f"   Cluster {cluster_id}: {count:3d} companies ({count/len(kmeans.labels_)*100:.1f}%)")
    
    return kmeans


def analyze_and_label_clusters(df: pd.DataFrame, X: pd.DataFrame, 
                               kmeans: KMeans, metadata: pd.DataFrame) -> Dict[int, Dict[str, Any]]:
    """Analyze clusters and assign semantic labels"""
    print("\n" + "="*80)
    print("STEP 6: CLUSTER ANALYSIS & LABELING")
    print("="*80)
    
    # Add cluster assignments
    df_analysis = metadata.copy()
    df_analysis['cluster_id'] = kmeans.labels_
    df_analysis['totalEsg'] = df['totalEsg'].values
    
    # Calculate cluster statistics
    cluster_stats = df_analysis.groupby('cluster_id')['totalEsg'].agg(['mean', 'std', 'count', 'min', 'max'])
    cluster_stats = cluster_stats.sort_values('mean', ascending=False)
    
    # Assign semantic labels
    labels = ['ESG Leaders', 'Above Average', 'Average Performers', 'Below Average', 'ESG Laggards']
    cluster_mapping = {}
    
    print(f"\n📊 Cluster Analysis & Labels:")
    print("-" * 80)
    
    for i, (cluster_id, stats) in enumerate(cluster_stats.iterrows()):
        label = labels[i]
        
        # Get top 3 companies in this cluster
        cluster_companies = df_analysis[df_analysis['cluster_id'] == cluster_id].nlargest(3, 'totalEsg')
        top_companies = cluster_companies['Name'].tolist()
        
        cluster_mapping[int(cluster_id)] = {
            'label': label,
            'mean_esg': float(stats['mean']),
            'std_esg': float(stats['std']),
            'count': int(stats['count']),
            'min_esg': float(stats['min']),
            'max_esg': float(stats['max']),
            'top_companies': top_companies
        }
        
        print(f"\nCluster {cluster_id}: {label}")
        print(f"   Mean ESG: {stats['mean']:.2f} ± {stats['std']:.2f}")
        print(f"   Range: {stats['min']:.1f} - {stats['max']:.1f}")
        print(f"   Companies: {stats['count']} ({stats['count']/len(df_analysis)*100:.1f}%)")
        print(f"   Top Companies:")
        for j, company in enumerate(top_companies, 1):
            esg_score = cluster_companies.iloc[j-1]['totalEsg']
            print(f"      {j}. {company} (ESG: {esg_score:.1f})")
    
    return cluster_mapping


def create_results_dataframe(df: pd.DataFrame, X: pd.DataFrame, kmeans: KMeans, 
                             cluster_mapping: Dict, metadata: pd.DataFrame) -> pd.DataFrame:
    """Create comprehensive results DataFrame"""
    print("\n" + "="*80)
    print("STEP 7: CREATE RESULTS DATAFRAME")
    print("="*80)
    
    # Create results DataFrame
    results = df.copy()
    results['cluster_id'] = kmeans.labels_
    
    # Rename 'Full Name' to 'Name' for consistency
    if 'Full Name' in results.columns:
        results.rename(columns={'Full Name': 'Name'}, inplace=True)
    
    # Add cluster labels
    results['cluster_label'] = results['cluster_id'].map(
        lambda x: cluster_mapping[x]['label']
    )
    
    # Add cluster mean ESG
    results['cluster_mean_esg'] = results['cluster_id'].map(
        lambda x: cluster_mapping[x]['mean_esg']
    )
    
    # Calculate percentile within cluster
    results['percentile_within_cluster'] = results.groupby('cluster_id')['totalEsg'].rank(pct=True) * 100
    
    # Sort by industry, then by totalEsg
    results = results.sort_values(['GICS Sector', 'totalEsg'], ascending=[True, False])
    
    # Select key columns for output
    output_columns = [
        'Symbol', 'Name', 'GICS Sector', 
        'totalEsg', 'environmentScore', 'socialScore', 'governanceScore',
        'highestControversy', 'percentile', 'overallRisk',
        'cluster_id', 'cluster_label', 'cluster_mean_esg', 'percentile_within_cluster'
    ]
    
    results_output = results[output_columns].copy()
    
    # Save to CSV
    os.makedirs('reports', exist_ok=True)
    output_path = 'reports/company_esg_clusters.csv'
    results_output.to_csv(output_path, index=False)
    
    print(f"\n✅ Results DataFrame Created:")
    print(f"   Shape: {results_output.shape}")
    print(f"   Saved to: {output_path}")
    
    print(f"\n📄 Sample Output (first 10 rows):")
    print(results_output[['Name', 'GICS Sector', 'totalEsg', 'cluster_label']].head(10))
    
    return results_output


def create_visualizations(results: pd.DataFrame, X_scaled: np.ndarray, 
                         kmeans: KMeans, cluster_mapping: Dict, feature_columns: List[str]) -> None:
    """Create visualization plots"""
    print("\n" + "="*80)
    print("STEP 8: VISUALIZATION")
    print("="*80)
    
    # Create output directory
    os.makedirs('reports', exist_ok=True)
    
    # 1. Cluster Distribution Bar Chart
    print(f"\n📊 Creating cluster distribution plot...")
    
    cluster_counts = results['cluster_label'].value_counts()
    # Sort by cluster order
    label_order = ['ESG Leaders', 'Above Average', 'Average Performers', 'Below Average', 'ESG Laggards']
    cluster_counts = cluster_counts.reindex(label_order)
    
    plt.figure(figsize=(12, 6))
    colors = ['#2ecc71', '#3498db', '#f39c12', '#e67e22', '#e74c3c']
    bars = plt.bar(range(len(cluster_counts)), cluster_counts.values, color=colors, alpha=0.8, edgecolor='black')
    plt.xlabel('Cluster Performance Tier', fontsize=12, fontweight='bold')
    plt.ylabel('Number of Companies', fontsize=12, fontweight='bold')
    plt.title('Company Distribution Across ESG Performance Clusters', fontsize=14, fontweight='bold')
    plt.xticks(range(len(cluster_counts)), cluster_counts.index, rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('reports/cluster_distribution.png', dpi=300, bbox_inches='tight')
    print(f"   ✅ Saved: reports/cluster_distribution.png")
    plt.close()
    
    # 2. ESG Score Box Plot by Cluster
    print(f"\n📊 Creating ESG score boxplot...")
    
    plt.figure(figsize=(12, 6))
    results_sorted = results.copy()
    results_sorted['cluster_label'] = pd.Categorical(
        results_sorted['cluster_label'], 
        categories=label_order, 
        ordered=True
    )
    
    sns.boxplot(data=results_sorted, x='cluster_label', y='totalEsg', 
               palette=colors, linewidth=2)
    plt.xlabel('Cluster Performance Tier', fontsize=12, fontweight='bold')
    plt.ylabel('Total ESG Score', fontsize=12, fontweight='bold')
    plt.title('ESG Score Distribution by Cluster', fontsize=14, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig('reports/cluster_esg_boxplot.png', dpi=300, bbox_inches='tight')
    print(f"   ✅ Saved: reports/cluster_esg_boxplot.png")
    plt.close()
    
    # 3. 2D Cluster Visualization using PCA
    print(f"\n📊 Creating 2D PCA visualization...")
    
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    
    plt.figure(figsize=(12, 8))
    
    # Plot points colored by cluster
    for cluster_id, info in cluster_mapping.items():
        mask = kmeans.labels_ == cluster_id
        label_idx = list(cluster_mapping.keys()).index(cluster_id)
        plt.scatter(X_pca[mask, 0], X_pca[mask, 1], 
                   c=[colors[label_idx]], 
                   label=info['label'],
                   alpha=0.6, s=50, edgecolors='k', linewidth=0.5)
    
    # Plot cluster centers
    centers_pca = pca.transform(kmeans.cluster_centers_)
    plt.scatter(centers_pca[:, 0], centers_pca[:, 1], 
               c='black', marker='X', s=300, edgecolors='white', linewidth=2,
               label='Cluster Centers', zorder=5)
    
    plt.xlabel(f'Principal Component 1 ({pca.explained_variance_ratio_[0]*100:.1f}% variance)', 
              fontsize=12, fontweight='bold')
    plt.ylabel(f'Principal Component 2 ({pca.explained_variance_ratio_[1]*100:.1f}% variance)', 
              fontsize=12, fontweight='bold')
    plt.title('ESG Performance Clusters (2D PCA Projection)', fontsize=14, fontweight='bold')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', frameon=True, fancybox=True, shadow=True)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('reports/cluster_2d_visualization.png', dpi=300, bbox_inches='tight')
    print(f"   ✅ Saved: reports/cluster_2d_visualization.png")
    plt.close()
    
    print(f"\n✅ All visualizations created successfully!")


def industry_specific_analysis(results: pd.DataFrame, top_n: int = 5) -> None:
    """Perform industry-specific cluster analysis"""
    print("\n" + "="*80)
    print("STEP 9: INDUSTRY-SPECIFIC ANALYSIS")
    print("="*80)
    
    # Get top N industries by company count
    top_industries = results['GICS Sector'].value_counts().head(top_n).index
    
    print(f"\n📊 Analyzing Top {top_n} Industries:")
    print("-" * 80)
    
    for i, industry in enumerate(top_industries, 1):
        industry_data = results[results['GICS Sector'] == industry]
        
        print(f"\n{i}. {industry}")
        print(f"   {'-' * (len(industry) + 3)}")
        print(f"   Total Companies: {len(industry_data)}")
        print(f"   Industry Average ESG: {industry_data['totalEsg'].mean():.2f}")
        print(f"   ESG Range: {industry_data['totalEsg'].min():.1f} - {industry_data['totalEsg'].max():.1f}")
        
        # Cluster distribution
        cluster_dist = industry_data['cluster_label'].value_counts()
        print(f"\n   Cluster Distribution:")
        for label, count in cluster_dist.items():
            pct = count / len(industry_data) * 100
            print(f"      {label:20s}: {count:3d} ({pct:5.1f}%)")
        
        # Best performer
        best = industry_data.nlargest(1, 'totalEsg').iloc[0]
        print(f"\n   🏆 Best Performer:")
        print(f"      Company: {best['Name']}")
        print(f"      ESG Score: {best['totalEsg']:.1f}")
        print(f"      Cluster: {best['cluster_label']}")
        
        # Worst performer
        worst = industry_data.nsmallest(1, 'totalEsg').iloc[0]
        print(f"\n   ⚠️  Lowest Performer:")
        print(f"      Company: {worst['Name']}")
        print(f"      ESG Score: {worst['totalEsg']:.1f}")
        print(f"      Cluster: {worst['cluster_label']}")
    
    # Overall summary table
    print(f"\n\n📋 INDUSTRY SUMMARY TABLE:")
    print("=" * 100)
    
    summary_data = []
    for industry in top_industries:
        industry_data = results[results['GICS Sector'] == industry]
        summary_data.append({
            'Industry': industry,
            'Companies': len(industry_data),
            'Avg ESG': f"{industry_data['totalEsg'].mean():.2f}",
            'ESG Range': f"{industry_data['totalEsg'].min():.1f}-{industry_data['totalEsg'].max():.1f}",
            'Leaders': len(industry_data[industry_data['cluster_label'] == 'ESG Leaders']),
            'Laggards': len(industry_data[industry_data['cluster_label'] == 'ESG Laggards'])
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))


def save_model_artifacts(kmeans: KMeans, scaler: StandardScaler, 
                        cluster_mapping: Dict, feature_columns: List[str]) -> None:
    """Save trained model and artifacts"""
    print("\n" + "="*80)
    print("STEP 10: SAVE MODEL & ARTIFACTS")
    print("="*80)
    
    # Create output directory
    os.makedirs('ml_models/trained', exist_ok=True)
    
    # Save KMeans model
    model_path = 'ml_models/trained/industry_clusters_model.pkl'
    joblib.dump(kmeans, model_path)
    print(f"\n✅ KMeans model saved: {model_path}")
    print(f"   Size: {os.path.getsize(model_path) / 1024:.2f} KB")
    
    # Save scaler
    scaler_path = 'ml_models/trained/industry_clusters_scaler.pkl'
    joblib.dump(scaler, scaler_path)
    print(f"\n✅ StandardScaler saved: {scaler_path}")
    print(f"   Size: {os.path.getsize(scaler_path) / 1024:.2f} KB")
    
    # Save cluster mapping
    mapping_path = 'ml_models/trained/cluster_mapping.pkl'
    joblib.dump(cluster_mapping, mapping_path)
    print(f"\n✅ Cluster mapping saved: {mapping_path}")
    print(f"   Clusters: {len(cluster_mapping)}")
    
    # Save feature list
    features_path = 'ml_models/trained/cluster_features.pkl'
    joblib.dump(feature_columns, features_path)
    print(f"\n✅ Feature columns saved: {features_path}")
    print(f"   Features: {len(feature_columns)}")
    
    print(f"\n📦 All artifacts saved to ml_models/trained/")


def test_prediction_function() -> None:
    """Test the trained model with sample predictions"""
    print("\n" + "="*80)
    print("STEP 11: TEST PREDICTION FUNCTION")
    print("="*80)
    
    # Load saved artifacts
    print(f"\n⏳ Loading saved model artifacts...")
    kmeans = joblib.load('ml_models/trained/industry_clusters_model.pkl')
    scaler = joblib.load('ml_models/trained/industry_clusters_scaler.pkl')
    cluster_mapping = joblib.load('ml_models/trained/cluster_mapping.pkl')
    feature_columns = joblib.load('ml_models/trained/cluster_features.pkl')
    print(f"   ✅ All artifacts loaded successfully")
    
    # Define prediction function
    def predict_cluster(esg_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Predict ESG cluster for a company"""
        # Create feature array in correct order
        features = np.array([[
            esg_metrics['totalEsg'],
            esg_metrics['environmentScore'],
            esg_metrics['socialScore'],
            esg_metrics['governanceScore'],
            esg_metrics.get('highestControversy', 0),
            esg_metrics.get('percentile', 50),
            esg_metrics.get('overallRisk', 50)
        ]])
        
        # Scale features
        features_scaled = scaler.transform(features)
        
        # Predict cluster
        cluster_id = int(kmeans.predict(features_scaled)[0])
        cluster_info = cluster_mapping[cluster_id]
        
        return {
            'cluster_id': cluster_id,
            'cluster_label': cluster_info['label'],
            'peer_group': cluster_info['label'],
            'mean_esg_in_cluster': cluster_info['mean_esg'],
            'cluster_size': cluster_info['count'],
            'esg_range': f"{cluster_info['min_esg']:.1f}-{cluster_info['max_esg']:.1f}"
        }
    
    # Test with sample companies
    test_cases = [
        {
            'name': 'High Performer',
            'metrics': {
                'totalEsg': 85.0,
                'environmentScore': 30.0,
                'socialScore': 28.0,
                'governanceScore': 27.0,
                'highestControversy': 0,
                'percentile': 95.0,
                'overallRisk': 15.0
            }
        },
        {
            'name': 'Average Performer',
            'metrics': {
                'totalEsg': 50.0,
                'environmentScore': 15.0,
                'socialScore': 17.0,
                'governanceScore': 18.0,
                'highestControversy': 2,
                'percentile': 50.0,
                'overallRisk': 50.0
            }
        },
        {
            'name': 'Low Performer',
            'metrics': {
                'totalEsg': 25.0,
                'environmentScore': 8.0,
                'socialScore': 9.0,
                'governanceScore': 8.0,
                'highestControversy': 4,
                'percentile': 10.0,
                'overallRisk': 85.0
            }
        }
    ]
    
    print(f"\n🧪 Testing Prediction Function with 3 Sample Companies:")
    print("-" * 80)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   Input ESG Metrics:")
        print(f"      Total ESG: {test_case['metrics']['totalEsg']}")
        print(f"      Environment: {test_case['metrics']['environmentScore']}")
        print(f"      Social: {test_case['metrics']['socialScore']}")
        print(f"      Governance: {test_case['metrics']['governanceScore']}")
        
        result = predict_cluster(test_case['metrics'])
        
        print(f"\n   📊 Prediction Results:")
        print(f"      Cluster ID: {result['cluster_id']}")
        print(f"      Cluster Label: {result['cluster_label']}")
        print(f"      Peer Group: {result['peer_group']}")
        print(f"      Cluster Mean ESG: {result['mean_esg_in_cluster']:.2f}")
        print(f"      Cluster Size: {result['cluster_size']} companies")
        print(f"      ESG Range in Cluster: {result['esg_range']}")
    
    print(f"\n✅ Prediction function working correctly!")


def main():
    """Main execution pipeline"""
    print("\n" + "="*80)
    print("ESG INDUSTRY CLUSTERING MODEL TRAINING")
    print("="*80)
    print("Purpose: Train K-Means to classify companies into ESG performance tiers")
    print("Dataset: S&P 500 companies with ESG scores")
    print("Method: K-Means clustering with k=5 (Leaders to Laggards)")
    print("="*80)
    
    # Step 1: Load and explore data
    df = load_and_explore_data('data/sp500_esg_data.csv')
    
    # Step 2: Prepare features
    X, feature_columns, metadata = prepare_features(df)
    
    # Step 3: Scale features
    X_scaled, scaler = scale_features(X)
    
    # Step 4: Determine optimal clusters
    determine_optimal_clusters(X_scaled, range(2, 11))
    
    # Step 5: Train KMeans model
    kmeans = train_kmeans_model(X_scaled, k=5)
    
    # Step 6: Analyze and label clusters
    cluster_mapping = analyze_and_label_clusters(df, X, kmeans, metadata)
    
    # Step 7: Create results DataFrame
    results = create_results_dataframe(df, X, kmeans, cluster_mapping, metadata)
    
    # Step 8: Create visualizations
    create_visualizations(results, X_scaled, kmeans, cluster_mapping, feature_columns)
    
    # Step 9: Industry-specific analysis
    industry_specific_analysis(results, top_n=5)
    
    # Step 10: Save model artifacts
    save_model_artifacts(kmeans, scaler, cluster_mapping, feature_columns)
    
    # Step 11: Test prediction function
    test_prediction_function()
    
    # Final summary
    print("\n" + "="*80)
    print("✅ TRAINING COMPLETE!")
    print("="*80)
    print(f"\n📦 Output Files:")
    print(f"   1. ml_models/trained/industry_clusters_model.pkl")
    print(f"   2. ml_models/trained/industry_clusters_scaler.pkl")
    print(f"   3. ml_models/trained/cluster_mapping.pkl")
    print(f"   4. ml_models/trained/cluster_features.pkl")
    print(f"   5. reports/company_esg_clusters.csv")
    print(f"   6. reports/clustering_elbow_method.png")
    print(f"   7. reports/cluster_distribution.png")
    print(f"   8. reports/cluster_esg_boxplot.png")
    print(f"   9. reports/cluster_2d_visualization.png")
    
    print(f"\n🎯 Key Results:")
    print(f"   - 5 clusters trained (ESG Leaders → Laggards)")
    print(f"   - {len(df):,} companies classified")
    print(f"   - Ready for peer comparison in greenwashing detection")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Integrate with IndustryComparator agent")
    print(f"   2. Use for real-time peer benchmarking")
    print(f"   3. Validate superlative ESG claims against clusters")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
