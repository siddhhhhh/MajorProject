"""Counterfactual recomputation — "what if this signal were different?"

Reads the scoremodifierledger (May-2026 invariant: ledger reconciles to headline)
and replays the headline arithmetic with one or more rows overridden.

Use cases:
  1. Live demo: reviewer says "but this lawsuit might be dismissed" -> answer in
     real time by zeroing the structural penalty row.
  2. Analyst tool: "what's the single highest-leverage row?" -> rank by
     |delta| of headline change when that row is zeroed.
  3. Calibration: replay an old score with a new structural rule applied.

We DO NOT re-run any LLM or agent. The recomputation is a deterministic walk:

    new_headline = bucket_sum + structural_sum + calibration_delta

Each is derived from the ledger directly. Overrides are applied per-row before
the sum. If an override changes a row, we update the contribution downstream;
the calibration_delta is preserved verbatim because we can't re-derive
calibration without re-running the pipeline.

Public API:
    recompute_with_overrides(report_raw, overrides) -> RecomputeResult
    leverage_ranking(report_raw, top_k=5) -> List[LeverageEntry]
    prebaked_scenarios(report_raw) -> List[Dict]   # used by Section 5E

Override grammar:
    {"label": str, "set_value": float | int}   # replace row's value
    {"label": str, "drop": True}               # remove row from sum

Labels are matched exactly against the ledger. Use `score_attribution.decompose`
output to discover available labels.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.score_attribution import _extract_ledger, _to_float

logger = logging.getLogger(__name__)


@dataclass
class RecomputeResult:
    original_headline: Optional[float]
    new_headline: Optional[float]
    delta: Optional[float]
    new_band: Optional[str]
    overrides_applied: List[Dict[str, Any]] = field(default_factory=list)
    breakdown: Dict[str, float] = field(default_factory=dict)
    reconciles: bool = True
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_headline_gw": self.original_headline,
            "new_headline_gw":      self.new_headline,
            "delta":                self.delta,
            "new_band":             self.new_band,
            "overrides_applied":    self.overrides_applied,
            "breakdown":            self.breakdown,
            "reconciles":           self.reconciles,
            "warnings":             self.warnings,
        }


@dataclass
class LeverageEntry:
    label: str
    original_value: Optional[float]
    headline_if_zeroed: Optional[float]
    headline_delta: Optional[float]   # negative = zeroing lowers GW score


# Re-implementing the totals walk here (rather than calling decompose()) so
# we have row-level control + don't lose info to the bucketed view.
_BUCKET_LABELS = {
    "Bucket: Formula Gap (weighted contribution)",
    "Bucket: Historical Trust (weighted contribution)",
    "Bucket: Current Contradictions (weighted contribution)",
    "Bucket: Disclosure Quality (weighted contribution)",
}

_HEADLINE_LABELS = (
    "GW Score (final, recalibrated)",
    "GW Score (recalibrated)",
    "GW Score (formula)",
)


def _walk_totals(ledger: List[Dict[str, Any]]) -> Tuple[float, float, Optional[float], Optional[float]]:
    """Return (bucket_sum, structural_sum, headline, calibration_delta).

    calibration_delta is headline - (bucket_sum + structural_sum); preserved
    verbatim because we can't re-derive it post-override.
    """
    bucket_sum = 0.0
    structural_sum = 0.0
    headline: Optional[float] = None
    for row in ledger:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "")
        v = _to_float(row.get("value"))
        if v is None:
            continue
        if label in _BUCKET_LABELS:
            bucket_sum += v
        elif label.startswith("Structural penalty: ") and label != "Structural penalty (total)":
            structural_sum += v
    # Headline = latest in priority order
    for hl in _HEADLINE_LABELS:
        for row in ledger:
            if row.get("label") == hl:
                hv = _to_float(row.get("value"))
                if hv is not None:
                    headline = hv
                    break
        if headline is not None:
            break
    calibration_delta = (
        round(headline - (bucket_sum + structural_sum), 2)
        if headline is not None else None
    )
    return bucket_sum, structural_sum, headline, calibration_delta


def _band_from_gw(gw: float) -> str:
    """Apply the canonical 3-band risk mapping.

    Source of truth is core/report_consistency_validator.py thresholds:
        < 33  -> LOW
        < 67  -> MODERATE
        >=    -> HIGH
    """
    if gw < 33:
        return "LOW"
    if gw < 67:
        return "MODERATE"
    return "HIGH"


def _apply_overrides(
    ledger: List[Dict[str, Any]],
    overrides: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """Apply overrides to a deep-copy of the ledger.

    Returns: (modified_ledger, warnings, overrides_actually_applied)
    """
    new_ledger = copy.deepcopy(ledger)
    warnings: List[str] = []
    applied: List[Dict[str, Any]] = []

    for ov in overrides:
        if not isinstance(ov, dict):
            warnings.append(f"override is not a dict: {ov!r}")
            continue
        label = ov.get("label")
        if not label:
            warnings.append(f"override missing 'label': {ov!r}")
            continue
        target_rows = [r for r in new_ledger
                       if isinstance(r, dict) and r.get("label") == label]
        if not target_rows:
            warnings.append(f"label not in ledger: {label!r}")
            continue
        if ov.get("drop"):
            # Remove all matching rows
            new_ledger = [r for r in new_ledger
                          if not (isinstance(r, dict) and r.get("label") == label)]
            applied.append({"label": label, "action": "dropped",
                            "previous_value": _to_float(target_rows[0].get("value"))})
        elif "set_value" in ov:
            new_val = ov["set_value"]
            prev = _to_float(target_rows[0].get("value"))
            for r in target_rows:
                r["value"] = new_val
            applied.append({"label": label, "action": "set_value",
                            "previous_value": prev, "new_value": new_val})
        else:
            warnings.append(f"override has neither 'drop' nor 'set_value': {ov!r}")
    return new_ledger, warnings, applied


# ── Public API ────────────────────────────────────────────────────────────────
def recompute_with_overrides(
    report_raw: Dict[str, Any],
    overrides: List[Dict[str, Any]],
) -> RecomputeResult:
    """Replay the headline arithmetic with one or more ledger rows overridden.

    `overrides` example:
      [
        {"label": "Structural penalty: climate_trace:INFLATION_FLAG:+12.0", "drop": True},
        {"label": "Bucket: Formula Gap (weighted contribution)", "set_value": 10.0},
      ]
    """
    ledger = _extract_ledger(report_raw)
    if not ledger:
        return RecomputeResult(
            original_headline=None, new_headline=None, delta=None, new_band=None,
            warnings=["no scoremodifierledger found in report"],
            reconciles=False,
        )

    # Original walk
    _, _, original_headline, calibration_delta = _walk_totals(ledger)

    # Applied walk
    new_ledger, warnings, applied = _apply_overrides(ledger, overrides)
    bucket_sum, structural_sum, _, _ = _walk_totals(new_ledger)

    # Calibration delta is preserved (it represents post-formula adjustments
    # that can't be re-derived without re-running the calibrator).
    cal = calibration_delta if calibration_delta is not None else 0.0
    new_headline = round(max(0.0, min(100.0, bucket_sum + structural_sum + cal)), 1)

    delta = (
        round(new_headline - original_headline, 1)
        if original_headline is not None else None
    )

    return RecomputeResult(
        original_headline=original_headline,
        new_headline=new_headline,
        delta=delta,
        new_band=_band_from_gw(new_headline),
        overrides_applied=applied,
        breakdown={
            "buckets":              round(bucket_sum, 2),
            "structural_penalties": round(structural_sum, 2),
            "calibration_delta":    round(cal, 2),
        },
        warnings=warnings,
        reconciles=(
            abs((bucket_sum + structural_sum + cal) - new_headline) <= 0.5
        ),
    )


def leverage_ranking(report_raw: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
    """Rank ledger rows by the absolute headline delta from zeroing each.

    Useful for "highest-leverage signal to challenge" diligence questions.
    """
    ledger = _extract_ledger(report_raw)
    if not ledger:
        return []
    _, _, original_headline, _ = _walk_totals(ledger)
    if original_headline is None:
        return []

    entries: List[Dict[str, Any]] = []
    seen_labels: set[str] = set()
    for row in ledger:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "")
        if not label or label in seen_labels:
            continue
        # Only consider contribution rows — buckets + structural
        is_bucket = label in _BUCKET_LABELS
        is_structural = (
            label.startswith("Structural penalty: ")
            and label != "Structural penalty (total)"
        )
        if not (is_bucket or is_structural):
            continue
        seen_labels.add(label)
        v = _to_float(row.get("value"))
        if v is None:
            continue
        result = recompute_with_overrides(report_raw, [{"label": label, "drop": True}])
        entries.append({
            "label": label,
            "original_value": v,
            "headline_if_zeroed": result.new_headline,
            "headline_delta": result.delta,
            "category": "bucket" if is_bucket else "structural",
        })

    entries.sort(key=lambda e: abs(e["headline_delta"] or 0.0), reverse=True)
    return entries[:top_k]


def prebaked_scenarios(report_raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate canned "what-if" scenarios for the demo Section 5E.

    Scenario shape:
        {name, description, overrides, result}
    """
    ledger = _extract_ledger(report_raw)
    if not ledger:
        return []

    scenarios: List[Dict[str, Any]] = []

    # Scenario 1: Climate TRACE inflation flag dismissed (if present)
    for r in ledger:
        if not isinstance(r, dict):
            continue
        lbl = r.get("label") or ""
        if lbl.startswith("Structural penalty: climate_trace:INFLATION_FLAG"):
            res = recompute_with_overrides(report_raw, [{"label": lbl, "drop": True}])
            scenarios.append({
                "name": "if_climate_trace_inflation_dismissed",
                "description": "If the Climate TRACE inflation flag is dismissed",
                "overrides": [{"label": lbl, "drop": True}],
                "result": res.to_dict(),
            })

    # Scenario 2: Carbon pathway gap closes to 10% (set the rule penalty to 0)
    for r in ledger:
        if not isinstance(r, dict):
            continue
        lbl = r.get("label") or ""
        if lbl.startswith("Structural penalty: pathway_gap_pct"):
            res = recompute_with_overrides(report_raw, [{"label": lbl, "drop": True}])
            scenarios.append({
                "name": "if_pathway_gap_closes",
                "description": "If the carbon pathway gap closes below the 30% threshold",
                "overrides": [{"label": lbl, "drop": True}],
                "result": res.to_dict(),
            })

    # Scenario 3: Halve Formula Gap bucket (proxy for "if controversy database
    # matches turn out to be misattributed")
    fg_label = "Bucket: Formula Gap (weighted contribution)"
    for r in ledger:
        if isinstance(r, dict) and r.get("label") == fg_label:
            v = _to_float(r.get("value"))
            if v is not None and v > 0:
                res = recompute_with_overrides(
                    report_raw, [{"label": fg_label, "set_value": round(v / 2, 2)}]
                )
                scenarios.append({
                    "name": "if_formula_gap_halved",
                    "description": "If the formula-gap signal is halved (e.g. controversy database matches reduced by half)",
                    "overrides": [{"label": fg_label, "set_value": round(v / 2, 2)}],
                    "result": res.to_dict(),
                })
            break

    # Scenario 5 (Reg-E): Cross-version regulatory framework counterfactual.
    # If the active registry_version were swapped for a "next version" with
    # different framework statuses or weights, what would the compliance
    # confidence look like? This DOES NOT mutate the compliance SCORE — it
    # surfaces the confidence band shift, which is the honest signal.
    #
    # Trigger: any framework in the report's volatility list (i.e. the
    # compliance_result already flagged something `under_consultation`).
    reg_snap = report_raw.get("regulatory_registry_snapshot") if isinstance(report_raw.get("regulatory_registry_snapshot"), dict) else {}
    compliance = (report_raw.get("scores") or {}).get("compliance") or {}
    if not compliance:
        compliance = report_raw.get("compliance_result") or {}
    if reg_snap and compliance:
        cur_volatility = compliance.get("framework_volatility") or {}
        cur_conf = compliance.get("compliance_confidence")
        cur_volatile_share = float(cur_volatility.get("volatile_share", 0.0) or 0.0)
        if cur_volatile_share > 0 and isinstance(cur_conf, (int, float)):
            # Hypothetical: all currently-volatile frameworks have stabilised
            # in a next version → volatile_share goes to 0, confidence
            # discount removed.
            volatile_ids = cur_volatility.get("volatile_framework_ids") or []
            scenarios.append({
                "name": "if_frameworks_v_next_stabilised",
                "description": (
                    "If the next registry version (stabilising "
                    f"{len(volatile_ids)} framework(s) currently under "
                    "consultation/draft) were applied"
                ),
                "overrides": [{
                    "label":  f"synthetic: stabilise {','.join(volatile_ids)}",
                    "set_value":  0.0,
                    "indicative": True,
                }],
                "result": {
                    "kind":                  "compliance_confidence_shift",
                    "compliance_score":      compliance.get("score"),
                    "current_confidence":    cur_conf,
                    "next_confidence":       1.0,
                    "delta_confidence":      round(1.0 - float(cur_conf), 3),
                    "stabilised_frameworks": volatile_ids,
                    "registry_version_now":  reg_snap.get("registry_version"),
                    "indicative":            True,
                    "reconciles":            True,
                    "rationale": (
                        "Compliance SCORE is unchanged. Only the CONFIDENCE "
                        f"in that score rises from {cur_conf} to 1.0 because "
                        "the volatile frameworks would no longer be tagged "
                        "under_consultation/draft. Indicative — does not "
                        "alter actual scoring."
                    ),
                },
            })

    # Scenario 4 (M1): Macro-attributable surcharge removed.
    # Indicative, not authoritative. We do NOT actually modify any ledger
    # row — instead we synthesise a hypothetical surcharge equal to
    # `aggregate_exposure × baseline_coef` GW pts and show what the
    # headline would be if it were subtracted. The macro_context block
    # itself is unaffected; the canonical score is unchanged.
    macro = report_raw.get("macro_context") if isinstance(report_raw.get("macro_context"), dict) else {}
    if macro and macro.get("status") == "ACTIVE_EVENTS_PRESENT":
        exposure = (macro.get("industry_exposure") or {}).get("aggregate_exposure")
        try:
            exp_f = float(exposure) if exposure is not None else 0.0
        except (TypeError, ValueError):
            exp_f = 0.0
        if exp_f > 0:
            baseline_coef = 8.0  # GW points per unit of exposure — conservative
            hypothetical_surcharge = round(exp_f * baseline_coef, 1)

            # Original headline (read straight from report, no recompute needed).
            scores = report_raw.get("scores") or {}
            orig_gw = _to_float(scores.get("greenwashingriskscore"))
            if orig_gw is None:
                orig_gw = _to_float(report_raw.get("greenwashingriskscore"))
            if orig_gw is not None:
                new_gw = max(0.0, min(100.0, orig_gw - hypothetical_surcharge))
                new_band = _band_from_gw(new_gw)
                event_ids = [e.get("event_id") for e in (macro.get("active_events") or [])]
                scenarios.append({
                    "name": "if_macro_surcharge_removed",
                    "description": (
                        "If a macro-attributable scope-3 / exogenous surcharge "
                        f"({hypothetical_surcharge:.1f} GW pts at exposure={exp_f:.2f}) "
                        "is removed (indicative — formula is NOT actually adjusted)"
                    ),
                    "overrides": [{
                        "label":  "synthetic: macro surcharge",
                        "set_value":  hypothetical_surcharge,
                        "indicative": True,
                    }],
                    "result": {
                        "original_headline_gw":   round(orig_gw, 1),
                        "new_headline_gw":        round(new_gw, 1),
                        "delta":                  round(new_gw - orig_gw, 1),
                        "new_band":               new_band,
                        "reconciles":             True,  # synthetic — no ledger to reconcile
                        "indicative":             True,
                        "macro_event_ids":        event_ids,
                        "exposure":               exp_f,
                        "baseline_coefficient":   baseline_coef,
                        "breakdown": {
                            "original_headline_gw": round(orig_gw, 1),
                            "hypothetical_surcharge": hypothetical_surcharge,
                            "new_headline_gw":      round(new_gw, 1),
                        },
                        "rationale": (
                            "Hypothetical: subtract aggregate macro exposure × "
                            "baseline_coef (8.0) from headline GW. Shows how "
                            "much of the score COULD be attributed to exogenous "
                            "macro conditions — does not alter actual scoring."
                        ),
                    },
                })

    return scenarios


def format_scenarios_text(scenarios: List[Dict[str, Any]], indent: str = "  ") -> List[str]:
    """Render scenarios for Section 5E text block.

    Handles three result shapes:
      - Ledger override: orig/new headline GW + overrides_applied
      - Macro surcharge (indicative): orig/new headline GW + macro_event_ids
      - Compliance confidence shift (Reg-E indicative): compliance_score
        unchanged, only confidence moves
    """
    lines: List[str] = []
    if not scenarios:
        lines.append(f"{indent}No counterfactual scenarios available for this report.")
        lines.append(f"{indent}(Pre-baked scenarios trigger on Climate TRACE flag, pathway gap, formula gap.)")
        return lines
    for s in scenarios:
        res = s.get("result", {})

        # Shape C: compliance confidence shift (Reg-E)
        if res.get("kind") == "compliance_confidence_shift":
            comp = res.get("compliance_score")
            cur = res.get("current_confidence")
            nxt = res.get("next_confidence")
            delta_c = res.get("delta_confidence")
            stabilised = res.get("stabilised_frameworks") or []
            lines.append(f"{indent}- {s.get('description', '')}:")
            comp_disp = f"{comp:.1f}" if isinstance(comp, (int, float)) else str(comp)
            lines.append(
                f"{indent}     Compliance score: {comp_disp}/100 (unchanged — indicative)"
            )
            if isinstance(cur, (int, float)) and isinstance(nxt, (int, float)):
                lines.append(
                    f"{indent}     Confidence: {cur:.3f} -> {nxt:.3f} "
                    f"(delta=+{(delta_c or (nxt - cur)):.3f})"
                )
            if stabilised:
                lines.append(f"{indent}     Frameworks that stabilise: {', '.join(stabilised)}")
            continue

        # Shapes A and B both need orig/new headline GW
        orig = res.get("original_headline_gw")
        new = res.get("new_headline_gw")
        delta = res.get("delta")
        new_band = res.get("new_band")
        if orig is None or new is None:
            lines.append(f"{indent}- {s['description']}: insufficient ledger data")
            continue
        sign = "+" if (delta or 0) >= 0 else ""
        lines.append(f"{indent}- {s['description']}:")
        suffix = " (indicative)" if res.get("indicative") else ""
        lines.append(
            f"{indent}     Headline GW: {orig:.1f} -> {new:.1f} "
            f"(delta={sign}{delta:.1f}, new band={new_band}){suffix}"
        )
        # Macro scenario: surface the driving event(s)
        macro_ids = res.get("macro_event_ids") or []
        if macro_ids:
            exp = res.get("exposure")
            coef = res.get("baseline_coefficient")
            lines.append(
                f"{indent}     Driven by macro event(s): {', '.join(macro_ids)} "
                f"(exposure={exp}, coef={coef})"
            )
        # Ledger overrides (Shape A)
        for ov in res.get("overrides_applied", []):
            act = ov.get("action")
            if act == "dropped":
                lines.append(
                    f"{indent}     [drop] {ov.get('label')} "
                    f"(was {ov.get('previous_value')})"
                )
            elif act == "set_value":
                lines.append(
                    f"{indent}     [set] {ov.get('label')}: "
                    f"{ov.get('previous_value')} -> {ov.get('new_value')}"
                )
    return lines
