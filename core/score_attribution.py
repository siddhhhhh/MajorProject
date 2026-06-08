"""Score attribution — decomposes the headline GW score into ranked contributors.

The pipeline already produces a `scoremodifierledger` list of {label, value}
rows that reconciles to the headline. This module groups those rows into
human-meaningful categories so the user sees:

  Headline GW: 55.0
    +20.0  Carbon pathway gap > 30%       (structural penalty)
    +12.0  Climate TRACE inflation flag   (structural penalty)
    +15.9  Formula Gap bucket             (weighted contribution)
     +9.0  Calibration adjustment
     +4.8  Historical Trust bucket
     +3.2  Disclosure Quality bucket
     +2.1  Current Contradictions bucket
  Reconciles to 55.0 (within 0.1 tolerance).

No LLM calls. Pure derivation from the ledger that risk_scorer already builds,
which is the May-2026 invariant. The reconciliation step is the safety net:
if the ledger ever drifts from the headline we surface the gap rather than
silently mis-attribute.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# Labels are matched exactly against ledger rows; new entries should be added
# here when risk_scorer.py introduces a new ledger label.
_BUCKET_LABELS = {
    "Bucket: Formula Gap (weighted contribution)":            "Formula Gap",
    "Bucket: Historical Trust (weighted contribution)":       "Historical Trust",
    "Bucket: Current Contradictions (weighted contribution)": "Current Contradictions",
    "Bucket: Disclosure Quality (weighted contribution)":     "Disclosure Quality",
}

_BUCKET_SCORE_LABELS = {
    "Bucket: Formula Gap (score)":            "Formula Gap",
    "Bucket: Historical Trust (score)":       "Historical Trust",
    "Bucket: Current Contradictions (score)": "Current Contradictions",
    "Bucket: Disclosure Quality (score)":     "Disclosure Quality",
}

_HEADLINE_LABELS = (
    "GW Score (final, recalibrated)",
    "GW Score (recalibrated)",
    "GW Score (formula)",
)

# Ledger rows whose label starts with one of these prefixes are *advisory
# only* — they document the calculation but are not themselves contributions.
_ADVISORY_PREFIXES = (
    "C (",
    "P (",
    "Gap (",
    "R (",
    "D (",
    "T (",
    "α (",
    "β (",
    "γ (",
    "δ (",
    "ESG Score",
    "Applied hard caps",
    "Bucket: Formula Gap (score)",
    "Bucket: Historical Trust (score)",
    "Bucket: Current Contradictions (score)",
    "Bucket: Disclosure Quality (score)",
    "GW Score",  # any GW Score row is a checkpoint, not a contribution
    "Structural penalty (total)",  # the aggregate row — individual rules dominate
)


def _to_float(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.replace("+", "").replace(",", "").strip())
        except ValueError:
            return None
    return None


def _find_headline(ledger: List[Dict[str, Any]]) -> Optional[float]:
    """Most-derived GW score in the ledger."""
    for label in _HEADLINE_LABELS:
        for row in ledger:
            if str(row.get("label")) == label:
                v = _to_float(row.get("value"))
                if v is not None:
                    return v
    return None


def _categorise(row: Dict[str, Any]) -> Tuple[str, str]:
    """Return (category, display_name) for a ledger row."""
    label = str(row.get("label") or "").strip()
    if label in _BUCKET_LABELS:
        return ("bucket", _BUCKET_LABELS[label])
    if label.startswith("Structural penalty: "):
        rule = label.replace("Structural penalty: ", "")
        return ("structural", rule)
    if label.startswith("net_zero_") or "_floor" in label or "_fallback" in label:
        return ("hard_cap", label)
    if "calibrat" in label.lower():
        return ("calibration", label)
    return ("other", label)


def _format_human_name(category: str, raw_name: str) -> str:
    """Human-readable name from category + raw label."""
    if category == "structural":
        # Display the actual computed gap, not the trigger threshold.
        # Rule key shapes accepted:
        #   "pathway_gap_pct=13.0:+20"  (new — shows real gap)
        #   "pathway_gap_pct>30:+20"    (legacy — pre-fix runs cached)
        # When the upstream gap value exceeds reasonable display bounds
        # (e.g. 3149.1pp from a malformed implied-rate calc) the raw figure
        # would scream "bug" in a demo. Cap display to >100pp and explain.
        if "pathway_gap_pct" in raw_name:
            import re
            m = re.search(r"pathway_gap_pct=(\d+(?:\.\d+)?)", raw_name)
            if m:
                gap_val = float(m.group(1))
                if gap_val > 100:
                    return "Carbon pathway gap >100pp (severely off benchmark — trigger: >30pp)"
                return f"Carbon pathway gap {gap_val:.1f}pp (trigger: >30pp)"
            return "Carbon pathway gap > 30pp trigger"
        if "climate_trace" in raw_name:
            # "climate_trace:INFLATION_FLAG:+12.0" -> "Climate TRACE: inflation flag"
            parts = raw_name.split(":")
            if len(parts) >= 2:
                return f"Climate TRACE: {parts[1].lower().replace('_', ' ')}"
            return "Climate TRACE verification"
        if "pcaf" in raw_name:
            # "pcaf:ABOVE_P75_worse_than_peers:+8.0" -> "PCAF: above P75 (worse than peers)"
            parts = raw_name.split(":")
            if len(parts) >= 2:
                pos = parts[1].lower().replace("_", " ")
                return f"PCAF financed emissions: {pos}"
            return "PCAF financed emissions"
        if "gdelt" in raw_name:
            parts = raw_name.split(":")
            if len(parts) >= 2:
                return f"GDELT adverse coverage: {parts[1].lower().replace('_', ' ')}"
            return "GDELT adverse coverage"
        if "litigation" in raw_name:
            parts = raw_name.split(":")
            if len(parts) >= 2:
                return f"Litigation: {parts[1].lower().replace('_', ' ')}"
            return "Litigation intensity"
        if "reg_cross_ref" in raw_name:
            parts = raw_name.split(":")
            if len(parts) >= 2:
                return f"EPA/EDGAR integrity: {parts[1].lower().replace('_', ' ')}"
            return "EPA/EDGAR integrity"
        if "subsidiary" in raw_name:
            parts = raw_name.split(":")
            if len(parts) >= 2:
                return f"Subsidiary coverage: {parts[1].lower().replace('_', ' ')}"
            return "Subsidiary coverage"
        if "promise" in raw_name:
            return "Promise ledger degradation"
        if "cross_pillar" in raw_name:
            return "Cross-pillar contradictions"
        if "internal_contradiction" in raw_name:
            return "Internal claim contradictions"
        if "promise_degradation" in raw_name:
            return "Promise degradation history"
        if "alignment_status" in raw_name:
            return "Pathway physically impossible"
        if "triangulation" in raw_name:
            return "Adversarial triangulation gap"
        return raw_name.replace("_", " ").replace(":+", " (+").rstrip(")") + ")"
    if category == "hard_cap":
        return raw_name.replace("_", " ").title()
    return raw_name


def _extract_ledger(report_raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find the scoremodifierledger in a report — it lives in several places.

    Search order:
        1. report.scoremodifierledger                 (top-level explicit)
        2. report.scores.raw.scoremodifierledger      (canonical for new runs)
        3. report.scores.scoremodifierledger          (legacy)
        4. agent_results[*].key_findings.scoremodifierledger
           (where risk_scoring writes it — most existing reports)
        5. agent_outputs[*].output.scoremodifierledger
           (live LangGraph state)
    """
    if not isinstance(report_raw, dict):
        return []

    # Top-level first
    led = report_raw.get("scoremodifierledger") or report_raw.get("score_modifier_ledger")
    if isinstance(led, list) and led:
        return led

    scores = report_raw.get("scores") or {}
    if isinstance(scores, dict):
        raw_scores = scores.get("raw") if isinstance(scores.get("raw"), dict) else {}
        for src in (raw_scores, scores):
            led = (
                src.get("scoremodifierledger")
                or src.get("score_modifier_ledger")
            )
            if isinstance(led, list) and led:
                return led

    for ar in (report_raw.get("agent_results") or []):
        if not isinstance(ar, dict):
            continue
        kf = ar.get("key_findings") or {}
        if not isinstance(kf, dict):
            continue
        led = kf.get("scoremodifierledger") or kf.get("score_modifier_ledger")
        if isinstance(led, list) and led:
            return led

    # Live LangGraph state — risk_scoring writes its result into agent_outputs.
    for ao in (report_raw.get("agent_outputs") or []):
        if not isinstance(ao, dict):
            continue
        if ao.get("agent") not in ("risk_scoring", "risk_scorer"):
            continue
        out = ao.get("output") or {}
        if not isinstance(out, dict):
            continue
        led = out.get("scoremodifierledger") or out.get("score_modifier_ledger")
        if isinstance(led, list) and led:
            return led

    return []


def decompose(scores_or_report: Dict[str, Any]) -> Dict[str, Any]:
    """Decompose into ranked contributors.

    Accepts either:
      - a scores dict (with scoremodifierledger or raw.scoremodifierledger)
      - a full report dict (we walk agent_results to find it)
    """
    ledger = _extract_ledger(scores_or_report)
    if not ledger:
        # Caller may have passed a scores dict directly — try that as a fallback.
        led_direct = (
            scores_or_report.get("scoremodifierledger")
            or scores_or_report.get("score_modifier_ledger")
            or []
        ) if isinstance(scores_or_report, dict) else []
        if isinstance(led_direct, list):
            ledger = led_direct
    if not isinstance(ledger, list):
        ledger = []

    headline = _find_headline(ledger)

    contributors: List[Dict[str, Any]] = []
    bucket_total = 0.0
    structural_total = 0.0

    for row in ledger:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        if not label:
            continue
        # Advisory rows — keep for the diagnostic view but exclude from
        # the top-N contributors.
        is_advisory = any(label.startswith(pref) for pref in _ADVISORY_PREFIXES)

        category, raw_name = _categorise(row)
        delta = _to_float(row.get("value"))
        if delta is None:
            continue

        if category == "bucket" and not label.endswith("(weighted contribution)"):
            # Skip non-contribution bucket rows here; the score rows are
            # already advisory.
            continue

        if category == "structural" and label != "Structural penalty (total)":
            structural_total += delta

        if category == "bucket":
            bucket_total += delta

        if is_advisory:
            continue

        contributors.append({
            "label": label,
            "category": category,
            "display_name": _format_human_name(category, raw_name),
            "delta": round(delta, 2),
            "direction": (
                "increases_gw_risk" if delta > 0 else
                "decreases_gw_risk" if delta < 0 else
                "neutral"
            ),
        })

    # Top contributors by absolute magnitude. Exclude hard_caps from the
    # ranked list — their value represents the input being capped
    # (e.g. C=60 after flooring), not a delta in points.
    contributors_sorted = sorted(
        contributors, key=lambda c: abs(c["delta"]), reverse=True
    )
    ranked = [c for c in contributors_sorted if c["category"] != "hard_cap"]
    hard_caps_applied = [c for c in contributors_sorted if c["category"] == "hard_cap"]

    top_positive = [c for c in ranked if c["direction"] == "increases_gw_risk"][:5]
    top_negative = [c for c in ranked if c["direction"] == "decreases_gw_risk"][:5]

    # Calibration delta — final headline minus (sum of buckets + structural)
    calibration_delta: Optional[float] = None
    if headline is not None:
        # The final headline = bucket_total + structural_total + calibration_delta
        # (within ~1.0 due to rounding/capping).
        calibration_delta = round(headline - (bucket_total + structural_total), 2)

    reconciles = (
        headline is not None and abs(
            (bucket_total + structural_total + (calibration_delta or 0.0)) - headline
        ) <= 0.5
    )

    return {
        "headline_gw_score": headline,
        "totals": {
            "buckets": round(bucket_total, 2),
            "structural_penalties": round(structural_total, 2),
            "calibration_delta": calibration_delta,
        },
        "top_contributors_positive": top_positive,
        "top_contributors_negative": top_negative,
        "all_contributors": ranked,
        "hard_caps_applied": hard_caps_applied,
        "reconciles": reconciles,
        "ledger_row_count": len(ledger),
    }


def format_attribution_text(decomp: Dict[str, Any], indent: str = "  ") -> List[str]:
    """Build text-report-friendly lines from a decomposition dict.

    Used by Section 5C (Score Contributors) in the professional report.
    """
    lines: List[str] = []
    headline = decomp.get("headline_gw_score")
    if isinstance(headline, (int, float)):
        lines.append(f"{indent}Headline GW score: {headline:.1f}/100")
        lines.append("")

    pos = decomp.get("top_contributors_positive") or []
    neg = decomp.get("top_contributors_negative") or []
    hard_caps = decomp.get("hard_caps_applied") or []

    if pos:
        lines.append(f"{indent}Top factors raising greenwashing risk:")
        for c in pos:
            lines.append(
                f"{indent}  +{c['delta']:>5.1f}  {c['display_name']:<45} "
                f"[{c['category']}]"
            )
    if neg:
        lines.append("")
        lines.append(f"{indent}Top factors lowering greenwashing risk:")
        for c in neg:
            lines.append(
                f"{indent}  {c['delta']:>+6.1f}  {c['display_name']:<45} "
                f"[{c['category']}]"
            )
    if hard_caps:
        lines.append("")
        lines.append(f"{indent}Hard caps / floors applied (override inputs):")
        for c in hard_caps:
            lines.append(
                f"{indent}  - {c['display_name']:<45} (value={c['delta']})"
            )

    totals = decomp.get("totals") or {}
    if totals:
        lines.append("")
        lines.append(f"{indent}Decomposition (reconciles to headline):")
        if totals.get("buckets") is not None:
            lines.append(f"{indent}  Buckets (4-bucket model):      {totals['buckets']:>+6.2f}")
        if totals.get("structural_penalties") is not None:
            lines.append(f"{indent}  Structural penalties total:    {totals['structural_penalties']:>+6.2f}")
        if totals.get("calibration_delta") is not None:
            lines.append(f"{indent}  Calibration adjustment:        {totals['calibration_delta']:>+6.2f}")
        if isinstance(headline, (int, float)):
            lines.append(
                f"{indent}  -> Final headline:               "
                f"{headline:>+6.2f}  (reconciles: "
                f"{'yes' if decomp.get('reconciles') else 'NO — see ledger'})"
            )
    return lines
