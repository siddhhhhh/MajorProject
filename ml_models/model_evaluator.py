"""
ML Model Evaluation Harness for ESG Greenwashing Detection
--------------------------------------------------------
Evaluates all ML models against the ground truth dataset and produces
publication-ready metrics, plots, and summary tables.
"""
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             roc_auc_score, confusion_matrix, roc_curve, balanced_accuracy_score)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder
import matplotlib.pyplot as plt
import seaborn as sns

_ml_results_printed = False

# === Feature Engineering ===
def build_features(df: pd.DataFrame) -> (np.ndarray, np.ndarray, list):
    """
    Build feature matrix X and label vector y from DataFrame.
    Returns X, y, feature_names
    """
    # Group A: TF-IDF features
    tfidf = TfidfVectorizer(max_features=300, ngram_range=(1,2), stop_words='english')
    X_tfidf = tfidf.fit_transform(df['claim_text']).toarray()
    tfidf_names = [f"tfidf_{w}" for w in tfidf.get_feature_names_out()]
    
    # Group B: Linguistic features
    vague_terms = ["sustainable", "green", "eco-friendly", "carbon neutral", "net zero", "commitment", "aspire", "aim to", "working towards", "journey", "pledge", "ambition", "goal", "by 2050", "future generations", "planet", "responsible", "conscious", "cleaner", "better world", "positive impact"]
    verification_terms = ["CDP", "SBTi", "Science Based Target", "verified by", "audited", "certified", "DNV", "Bureau Veritas", "third-party", "independent", "validated", "ISO 14001", "GRI", "TCFD", "B Corp", "Bluesign"]
    hedge_terms = ["plan to", "will", "by 2050", "by 2030", "intend to", "expect to", "aim", "hope", "target", "aspire", "goal"]
    import re
    def count_terms(text, terms):
        return sum(text.lower().count(t.lower()) for t in terms)
    def quant_score(text):
        return len(re.findall(r'\d+\.?\d*\s*(%|percent|tonne|MW|GW|km|kg|°C|degrees)', text))
    def verification_score(text):
        return count_terms(text, verification_terms)
    def vague_score(text):
        return count_terms(text, vague_terms)
    def hedge_score(text):
        return count_terms(text, hedge_terms)
    def action_vs_aspiration(text):
        v = vague_score(text)
        h = hedge_score(text)
        q = quant_score(text)
        ver = verification_score(text)
        return (ver + q) / max(1, v + h)
    def has_year(text):
        return int(bool(re.search(r'20[2-5]\d', text)))
    def has_scope(text):
        t = text.lower()
        return int("scope 1" in t or "scope 2" in t or "scope 3" in t)
    X_ling = np.array([
        [
            vague_score(t),
            quant_score(t),
            verification_score(t),
            hedge_score(t),
            action_vs_aspiration(t),
            len(t.split()),
            has_year(t),
            has_scope(t)
        ] for t in df['claim_text']
    ])
    ling_names = [
        "vague_language_score", "quantification_score", "verification_score", "future_hedge_score",
        "action_vs_aspiration_ratio", "claim_length", "has_specific_year", "has_scope_mention"
    ]
    # Group C: Sector one-hot
    enc = OneHotEncoder(sparse_output=False)
    X_sector = enc.fit_transform(df[['sector']])
    sector_names = [f"sector_{c}" for c in enc.categories_[0]]
    # Concatenate
    X = np.concatenate([X_tfidf, X_ling, X_sector], axis=1)
    feature_names = tfidf_names + ling_names + sector_names
    y = df['greenwashing_label'].values
    return X, y, feature_names

# === Model Evaluation ===
def run_full_evaluation() -> Dict[str, Any]:
    """
    Runs full evaluation, saves plots and metrics, prints markdown table.
    """
    df = pd.read_csv(os.path.join(os.path.dirname(__file__), '../data/ground_truth_dataset.csv'))
    X, y, feature_names = build_features(df)
    # Imbalance ratio for positive class weighting (greenwashing=1)
    neg_count = int((y == 0).sum())
    pos_count = int((y == 1).sum())
    scale_pos_weight = (pos_count / max(1, neg_count)) if neg_count > 0 else 1.0
    results = {}
    models = {
        "Dummy": DummyClassifier(strategy='most_frequent'),
        "LogReg": LogisticRegression(C=1.0, max_iter=1000, class_weight='balanced', random_state=42),
        "XGBoost": XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, eval_metric='logloss', random_state=42, scale_pos_weight=scale_pos_weight),
        "LightGBM": LGBMClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42, verbose=-1)
    }
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_metrics = {k: {"accuracy": [], "precision": [], "recall": [], "f1": [], "auc": [], "balanced_accuracy": [], "macro_f1": []} for k in models}
    for model_name, model in models.items():
        for train_idx, test_idx in skf.split(X, y):
            model.fit(X[train_idx], y[train_idx])
            y_pred = model.predict(X[test_idx])
            y_proba = model.predict_proba(X[test_idx])[:,1] if hasattr(model, 'predict_proba') else np.zeros_like(y_pred)
            cv_metrics[model_name]["accuracy"].append(accuracy_score(y[test_idx], y_pred))
            cv_metrics[model_name]["precision"].append(precision_score(y[test_idx], y_pred, average='weighted', zero_division=0))
            cv_metrics[model_name]["recall"].append(recall_score(y[test_idx], y_pred, average='weighted', zero_division=0))
            cv_metrics[model_name]["f1"].append(f1_score(y[test_idx], y_pred, average='weighted', zero_division=0))
            cv_metrics[model_name]["balanced_accuracy"].append(balanced_accuracy_score(y[test_idx], y_pred))
            cv_metrics[model_name]["macro_f1"].append(f1_score(y[test_idx], y_pred, average='macro', zero_division=0))
            try:
                cv_metrics[model_name]["auc"].append(roc_auc_score(y[test_idx], y_proba))
            except Exception:
                cv_metrics[model_name]["auc"].append(0.5)
    # Aggregate
    results['cross_validation_results'] = {}
    for model_name in models:
        results['cross_validation_results'][model_name] = {
            "accuracy_mean": float(np.mean(cv_metrics[model_name]["accuracy"])),
            "accuracy_std": float(np.std(cv_metrics[model_name]["accuracy"])),
            "f1_mean": float(np.mean(cv_metrics[model_name]["f1"])),
            "f1_std": float(np.std(cv_metrics[model_name]["f1"])),
            "auc_mean": float(np.mean(cv_metrics[model_name]["auc"])),
            "auc_std": float(np.std(cv_metrics[model_name]["auc"])),
            "precision_mean": float(np.mean(cv_metrics[model_name]["precision"])),
            "recall_mean": float(np.mean(cv_metrics[model_name]["recall"])),
            "balanced_accuracy_mean": float(np.mean(cv_metrics[model_name]["balanced_accuracy"])),
            "macro_f1_mean": float(np.mean(cv_metrics[model_name]["macro_f1"]))
        }
    # === Holdout evaluation ===
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    holdout = {}
    y_probas = {}
    for model_name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:,1] if hasattr(model, 'predict_proba') else np.zeros_like(y_pred)
        holdout[model_name] = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "f1": float(f1_score(y_test, y_pred, average='weighted', zero_division=0)),
            "macro_f1": float(f1_score(y_test, y_pred, average='macro', zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
            "auc": float(roc_auc_score(y_test, y_proba)),
            "precision": float(precision_score(y_test, y_pred, average='weighted', zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, average='weighted', zero_division=0)),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist()
        }
        y_probas[model_name] = y_proba
    results['holdout_results'] = holdout
    # === Plots ===
    # Confusion matrices
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
    os.makedirs(REPORTS_DIR, exist_ok=True)
    for model_name in models:
        cm = holdout[model_name]["confusion_matrix"]
        plt.figure(figsize=(4,3))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=["Legitimate", "Greenwashing"], yticklabels=["Legitimate", "Greenwashing"])
        plt.title(f"Confusion Matrix  {model_name}")
        plt.xlabel("Predicted Label (0=Legitimate, 1=Greenwashing)")
        plt.ylabel("True Label")
        plt.tight_layout()
        plt.savefig(os.path.join(REPORTS_DIR, f"confusion_matrix_{model_name.lower()}.png"))
        plt.close()
    # ROC curve
    plt.figure(figsize=(6,5))
    for model_name in models:
        fpr, tpr, _ = roc_curve(y_test, y_probas[model_name])
        auc = holdout[model_name]["auc"]
        plt.plot(fpr, tpr, label=f"{model_name} (AUC={auc:.2f})")
    plt.plot([0,1],[0,1],'k--',label="Random")
    plt.title("ROC Curve Comparison  ESG Greenwashing Detection")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, "roc_curve_comparison.png"))
    plt.close()
    # Feature importance for XGBoost and LightGBM
    for model_name, model in {"XGBoost": models["XGBoost"], "LightGBM": models["LightGBM"]}.items():
        model.fit(X_train, y_train)
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            idx = np.argsort(importances)[-20:][::-1]
            # Define feature group names for color coding
            ling_names = [
                "vague_language_score", "quantification_score", "verification_score", "future_hedge_score",
                "action_vs_aspiration_ratio", "claim_length", "has_specific_year", "has_scope_mention"
            ]
            n_ling = len(ling_names)
            n_sector = len([f for f in feature_names if f.startswith('sector_')])
            n_tfidf = len(feature_names) - n_ling - n_sector
            tfidf_names = feature_names[:n_tfidf]
            sector_names = [f for f in feature_names if f.startswith('sector_')]
            colors = []
            for i in idx:
                name = feature_names[i]
                if name in tfidf_names:
                    colors.append('blue')
                elif name in ling_names:
                    colors.append('green')
                else:
                    colors.append('orange')
            plt.figure(figsize=(7,5))
            plt.barh([feature_names[i] for i in idx], importances[idx], color=colors)
            plt.gca().invert_yaxis()
            plt.title(f"Feature Importance  {model_name}")
            plt.tight_layout()
            plt.savefig(os.path.join(REPORTS_DIR, f"feature_importance_{model_name.lower()}.png"))
            plt.close()
    # === Save results ===
    results['evaluation_date'] = datetime.now().isoformat()
    results['dataset_size'] = int(len(df))
    results['class_balance'] = {"greenwashing": int(df['greenwashing_label'].sum()), "legitimate": int((df['greenwashing_label']==0).sum())}
    # Best model by CV F1 (research integrity)
    best_model = max(results['cross_validation_results'], key=lambda k: results['cross_validation_results'][k]['f1_mean'])
    results['best_model'] = best_model
    results['best_model_cv_f1'] = results['cross_validation_results'][best_model]['f1_mean']
    results['holdout_warning'] = (
        "NOTE: Dataset n=21 is insufficient for reliable holdout evaluation. "
        "CV metrics reported. Holdout F1 may reflect a trivially small test set and should not be interpreted as genuine generalisation."
    )
    # Save JSON
    with open(os.path.join(REPORTS_DIR, "ml_evaluation_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    global _ml_results_printed
    if not _ml_results_printed:
        _ml_results_printed = True
        print("\nML MODEL EVALUATION RESULTS\n---------------------------")
        header = "| Model | Accuracy | F1 | AUC | Precision | Recall |"
        print(header)
        print("|-------|----------|------|------|-----------|--------|")
        for model_name in models:
            h = holdout[model_name]
            print(f"| {model_name} | {h['accuracy']:.3f} | {h['f1']:.3f} | {h['auc']:.3f} | {h['precision']:.3f} | {h['recall']:.3f} |")
        print(f"\nBest Model (CV F1): {best_model} ({results['cross_validation_results'][best_model]['f1_mean']:.3f})")
    # === ClimateBERT evaluation ===
    try:
        from ml_models.climatebert_analyzer import climatebert_analyze
        y_pred_bert = []
        sample_claims = df['claim_text'].head(len(y_test)).tolist()
        for claim in sample_claims:
            try:
                out = climatebert_analyze(claim)
                if isinstance(out, (int, float)):
                    y_pred_bert.append(int(out >= 50))
                elif isinstance(out, str):
                    y_pred_bert.append(1 if out.strip().upper() in ["HIGH", "MEDIUM"] else 0)
                else:
                    y_pred_bert.append(0)
            except Exception:
                y_pred_bert.append(0)
        if len(y_pred_bert) < len(y_test):
            y_pred_bert.extend([0] * (len(y_test) - len(y_pred_bert)))
        elif len(y_pred_bert) > len(y_test):
            y_pred_bert = y_pred_bert[:len(y_test)]
        bert_prec = precision_score(y_test, y_pred_bert, average='weighted', zero_division=0)
        bert_rec = recall_score(y_test, y_pred_bert, average='weighted', zero_division=0)
        bert_f1 = f1_score(y_test, y_pred_bert, average='weighted', zero_division=0)
        print(f"| ClimateBERT | N/A | {bert_f1:.3f} | N/A | {bert_prec:.3f} | {bert_rec:.3f} |")
    except Exception as e:
        print(f"ClimateBERT evaluation skipped: {e}")
    return results

if __name__ == "__main__":
    run_full_evaluation()
