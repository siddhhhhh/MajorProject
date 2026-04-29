"""
core/feature_engineering.py
----------------------------
Fixes Problems #5 (Feature Engineering) and #13 (Metric Overload)

Generates interaction/derived features that raw signals miss:
  - Claim-evidence gap features
  - Cross-pillar interaction features
  - Temporal delta features (YoY change)
  - Industry-relative percentile features
  - Dynamic metric selection (top-N most predictive)
"""
from __future__ import annotations
import json, os, re, logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BASELINES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "industry_baselines.json")
MATERIALITY_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "materiality_map.json")


def _load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _industry_key(industry: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", (industry or "general").lower().strip()).strip("_")


def compute_engineered_features(
    *,
    company: str,
    industry: str,
    claim: str = "",
    esg_score: float = 50.0,
    environmental_score: float = 50.0,
    social_score: float = 50.0,
    governance_score: float = 50.0,
    greenwashing_score: float = 50.0,
    claim_specificity: float = 5.0,
    evidence_count: int = 0,
    tier1_count: int = 0,
    tier2_count: int = 0,
    contradiction_count: int = 0,
    disclosure_completeness: float = 50.0,
    carbon_data_quality: float = 50.0,
    prior_esg_score: Optional[float] = None,
    prior_gw_score: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute interaction and derived features from raw pipeline signals.
    Returns a flat dict of engineered features with human-readable keys.
    """
    baselines = _load_json(BASELINES_PATH)
    materiality = _load_json(MATERIALITY_PATH)
    ind_key = _industry_key(industry)

    ind_baseline = baselines.get("industry_baseline_risk", {}).get(ind_key, {})
    baseline_esg = float(ind_baseline.get("baseline_esg", 50))
    baseline_risk = float(ind_baseline.get("baseline", 50))
    mat_weights = materiality.get(ind_key, materiality.get("general", {})).get("weights", {"E": 0.35, "S": 0.30, "G": 0.35})

    features = {}

    # ── 1. Claim-Evidence Gap Features ──
    features["claim_evidence_ratio"] = round(
        claim_specificity / max(1, evidence_count) * 10, 3
    )
    features["evidence_density"] = round(evidence_count / max(1, claim_specificity), 3)
    features["claim_vagueness_x_low_evidence"] = round(
        max(0, 7 - claim_specificity) * max(0, 10 - evidence_count) / 10, 3
    )

    # ── 2. Cross-Pillar Interaction Features ──
    pillar_spread = max(environmental_score, social_score, governance_score) - min(environmental_score, social_score, governance_score)
    features["pillar_spread"] = round(pillar_spread, 1)
    features["pillar_imbalance_flag"] = 1.0 if pillar_spread > 25 else 0.0
    features["env_gov_gap"] = round(abs(environmental_score - governance_score), 1)
    features["high_claim_low_gov"] = round(
        max(0, claim_specificity - 5) * max(0, 50 - governance_score) / 50, 3
    )

    # ── 3. Industry-Relative Features ──
    features["esg_vs_industry_baseline"] = round(esg_score - baseline_esg, 1)
    features["risk_vs_industry_baseline"] = round(greenwashing_score - baseline_risk, 1)
    features["above_industry_avg"] = 1.0 if esg_score > baseline_esg else 0.0

    # ── 4. Evidence Quality Features ──
    high_tier_ratio = (tier1_count + tier2_count) / max(1, evidence_count)
    features["high_tier_evidence_ratio"] = round(high_tier_ratio, 3)
    features["contradiction_density"] = round(
        contradiction_count / max(1, evidence_count), 3
    )
    features["contradiction_x_low_disclosure"] = round(
        contradiction_count * max(0, 100 - disclosure_completeness) / 100, 3
    )

    # ── 5. Disclosure-Performance Interaction ──
    features["disclosure_gap"] = round(100 - disclosure_completeness, 1)
    features["high_claim_low_disclosure"] = round(
        max(0, claim_specificity - 4) * max(0, 60 - disclosure_completeness) / 60, 3
    )
    features["carbon_data_adequacy"] = round(carbon_data_quality, 1)

    # ── 6. Temporal Delta Features (YoY) ──
    if prior_esg_score is not None:
        features["esg_yoy_delta"] = round(esg_score - prior_esg_score, 1)
        features["esg_improving"] = 1.0 if esg_score > prior_esg_score else 0.0
    else:
        features["esg_yoy_delta"] = 0.0
        features["esg_improving"] = 0.5  # unknown

    if prior_gw_score is not None:
        features["gw_yoy_delta"] = round(greenwashing_score - prior_gw_score, 1)
        features["gw_worsening"] = 1.0 if greenwashing_score > prior_gw_score else 0.0
    else:
        features["gw_yoy_delta"] = 0.0
        features["gw_worsening"] = 0.5

    # ── 7. Materiality-Weighted ESG ──
    mat_esg = (
        environmental_score * float(mat_weights.get("E", 0.35))
        + social_score * float(mat_weights.get("S", 0.30))
        + governance_score * float(mat_weights.get("G", 0.35))
    )
    features["materiality_weighted_esg"] = round(mat_esg, 1)
    features["materiality_vs_equal_weight"] = round(mat_esg - esg_score, 1)

    # ── 8. Composite Risk Signal ──
    features["composite_risk_signal"] = round(
        0.35 * greenwashing_score
        + 0.25 * (100 - esg_score)
        + 0.20 * (100 - disclosure_completeness)
        + 0.10 * min(100, contradiction_count * 20)
        + 0.10 * max(0, 100 - high_tier_ratio * 100),
        1
    )

    return features


def select_top_features(
    features: Dict[str, Any], top_n: int = 10
) -> List[Dict[str, Any]]:
    """
    Select top-N most informative features by deviation from neutral.
    Reduces metric overload (Problem #13) by surfacing only what matters.
    """
    ranked = []
    for key, val in features.items():
        if not isinstance(val, (int, float)):
            continue
        # Deviation from neutral (0 or 0.5 for flags)
        if key.endswith("_flag") or key.endswith("_improving") or key.endswith("_worsening"):
            deviation = abs(val - 0.5)
        else:
            deviation = abs(val)
        ranked.append({"feature": key, "value": round(val, 3), "deviation": round(deviation, 3)})

    ranked.sort(key=lambda x: x["deviation"], reverse=True)
    return ranked[:top_n]
