import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
"""
Score Calibrator for ESG Greenwashing Detection
----------------------------------------------
Performs calibration analysis of greenwashing scores against ground truth.
Computes correlation, calibration curve, and optimal threshold.
"""
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Callable, Dict, Any
from scipy.stats import spearmanr, pointbiserialr, mannwhitneyu
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_curve
import matplotlib.pyplot as plt

def linguistic_greenwashing_score(claim_text: str, company_name: str, sector: str) -> float:
    """
    Rule-based greenwashing score using only text analysis.
    Returns float 0-100. Higher = more likely greenwashing.
    """
    claim_lower = claim_text.lower()
    score = 50.0  # neutral start
    vague_terms = ["sustainable", "green", "eco-friendly", "responsible", "conscious", "planet", "future generations", "working towards", "journey", "ambition", "aspire", "better world"]
    vague_count = sum(1 for t in vague_terms if t in claim_lower)
    score += min(vague_count * 5, 25)
    verified_terms = ["cdp", "sbti", "science based target", "verified by", "audited", "certified", "dnv", "bureau veritas", "third-party", "independent audit", "validated", "b corp"]
    verified_count = sum(1 for t in verified_terms if t in claim_lower)
    score -= min(verified_count * 8, 30)
    import re
    quant_matches = re.findall(r'\d+\.?\d*\s*(%|percent|tonne|MW|GW|kg|°C)', claim_lower)
    score -= min(len(quant_matches) * 4, 20)
    future_only = sum(1 for t in ["by 2050", "by 2030", "will be", "aim to", "plan to", "intend to"] if t in claim_lower)
    present_action = sum(1 for t in ["have achieved", "is now", "since 2020", "currently", "already", "completed"] if t in claim_lower)
    if future_only > 0 and present_action == 0:
        score += min(future_only * 6, 20)
    high_risk_sectors = ["energy", "oil", "gas", "aviation", "fast fashion", "mining", "automotive"]
    if any(s in sector.lower() for s in high_risk_sectors):
        score += 5
    return max(0.0, min(100.0, score))

def run_calibration(score_fn: Callable[[str, str, str], float] = None) -> Dict[str, Any]:
    """
    Runs calibration analysis, saves plots and metrics, prints warnings if needed.
    """
    if score_fn is None:
        score_fn = linguistic_greenwashing_score
    df = pd.read_csv(os.path.join(os.path.dirname(__file__), '../data/ground_truth_dataset.csv'))
    scores = [score_fn(row['claim_text'], row['company_name'], row['sector']) for _, row in df.iterrows()]
    labels = df['greenwashing_label'].values
    # Correlation
    spearman = spearmanr(scores, labels)
    try:
        pointb = pointbiserialr(labels, scores)
    except Exception:
        pointb = (0, 1)
    try:
        mw = mannwhitneyu([s for s, l in zip(scores, labels) if l==1], [s for s, l in zip(scores, labels) if l==0], alternative='greater')
        mw_p = mw.pvalue
    except Exception:
        mw_p = 1.0
    # Calibration curve
    scores_norm = np.array(scores) / 100.0
    frac_pos, mean_pred = calibration_curve(labels, scores_norm, n_bins=5)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    plt.figure(figsize=(5,4))
    plt.plot(mean_pred, frac_pos, marker='o', label='Linguistic Scorer')
    plt.plot([0,1],[0,1],'k--',label='Perfectly Calibrated')
    plt.xlabel('Mean Predicted Value')
    plt.ylabel('Fraction of Positives')
    plt.title('Score Calibration  Predicted Greenwashing Probability vs Actual Rate')
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(REPORTS_DIR, 'calibration_curve.png'))
    plt.close()
    # Optimal threshold
    fpr, tpr, thresholds = roc_curve(labels, scores_norm)
    j_scores = tpr - fpr
    optimal_idx = np.argmax(j_scores)
    optimal_threshold = thresholds[optimal_idx] * 100
    # Update config/settings.py
    config_path = os.path.join(os.path.dirname(__file__), '../config/settings.py')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith('GREENWASHING_THRESHOLD'):
                lines[i] = f'GREENWASHING_THRESHOLD = {optimal_threshold:.1f}  # auto-computed\n'
                found = True
        if not found:
            lines.append(f'GREENWASHING_THRESHOLD = {optimal_threshold:.1f}  # auto-computed\n')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception:
        pass
    print(f"Optimal greenwashing threshold: {optimal_threshold:.1f}/100")
    # Save report
    mean_score_green = float(np.mean([s for s, l in zip(scores, labels) if l==1]))
    mean_score_legit = float(np.mean([s for s, l in zip(scores, labels) if l==0]))
    report = {
        "calibration_date": datetime.now().isoformat(),
        "dataset_size": int(len(df)),
        "linguistic_scorer": {
            "spearman_r": float(spearman.correlation),
            "spearman_p": float(spearman.pvalue),
            "point_biserial_r": float(pointb[0]),
            "mannwhitney_p": float(mw_p),
            "calibration_status": "CALIBRATED" if spearman.correlation > 0.4 and spearman.pvalue < 0.05 else "NEEDS_REVIEW",
            "optimal_threshold": float(optimal_threshold),
            "mean_score_greenwashing": mean_score_green,
            "mean_score_legitimate": mean_score_legit
        },
        "warnings": []
    }
    if spearman.correlation < 0.4:
        worst_sectors = df.groupby('sector').apply(lambda g: np.mean([score_fn(row['claim_text'], row['company_name'], row['sector']) for _, row in g.iterrows() if row['greenwashing_label']==1]) - np.mean([score_fn(row['claim_text'], row['company_name'], row['sector']) for _, row in g.iterrows() if row['greenwashing_label']==0])).sort_values().head(3).index.tolist()
        warn = f"CALIBRATION WARNING: Score correlation with ground truth is weak (r={spearman.correlation:.2f}). The linguistic scorer may need reweighting. Consider adding more training examples for sectors: {worst_sectors}."
        print(warn)
        report['warnings'].append(warn)
    with open(os.path.join(REPORTS_DIR, 'calibration_report.json'), 'w') as f:
        json.dump(report, f, indent=2)
    return report

if __name__ == "__main__":
    run_calibration()
