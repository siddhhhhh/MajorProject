"""Report consistency validator — pre-export gate.

Runs against the structured-report dict produced by
``ProfessionalReportGenerator._build_structured_report``. Catches the integration-layer
contradictions surfaced by the May-2026 audit:

  V1  rating must be a pure function of the displayed ESG score
      (Volkswagen bug: BBB shown at ESG=35).
  V2  displayed band must agree with the headline risk number under
      the documented polarity (Infosys bug: GW=20.6 surfaced as HIGH).
  V3  display_esg must not be the ``100 - greenwashingriskscore`` fallback
      (silent invariant breaker in legacy code paths).
  V4  weighted pillar contributions must reconcile to the displayed ESG
      score within rounding tolerance.
  V5  greenwashing component sum must reconcile to the displayed GW score
      within tolerance, OR an ``applied_caps`` row must explain the delta.
  V6  when industry sigma falls back to cross-sector or hardcoded, the
      report must surface ``sigma_provenance`` so reviewers can flag the
      gap term as cross-sector-normalised (audit fix: small-peer-set
      industries getting global sigma).
  V7  when active enforcement penalties exist, each must carry the
      decay/relevance provenance fields so the Dieselgate-vs-climate-claim
      adjustment can be reproduced from the report.
  V8  confidence-language coupling: when displayed band is HIGH/CRITICAL
      AND confidence < 60%, the report must mark verdict_qualifier as
      "indicative" so the headline does not assert certainty on weak data.
  V9  ESG independence: displayed ESG must equal the weighted pillar
      average within tight tolerance. Historical-misconduct ceilings on
      ESG are forbidden (ESG = current pillar performance, period; trust
      penalties flow only into the GW historical_trust bucket).

Usage::

    from core.report_consistency_validator import validate_report
    result = validate_report(structured)
    if not result.ok and not os.environ.get("ALLOW_INCONSISTENT_EXPORT"):
        raise ReportConsistencyError(result)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1.0"

# Canonical ESG-score -> rating bins. Mirrors agents.risk_scorer.esg_score_to_rating
# so the two scales cannot drift apart silently.
_RATING_BINS = (
    (90.0, "AAA"),
    (85.0, "AA"),
    (75.0, "A"),
    (60.0, "BBB"),
    (50.0, "BB"),
    (35.0, "B"),
    (0.0,  "CCC"),
)

# Canonical headline-risk -> band bins. high_score_means_higher_risk.
# MSCI-style 3-band scale (LOW / MODERATE / HIGH). CRITICAL was dropped
# May-2026 per design call — sub-categorising HIGH adds confusion without
# adding decision value (a HIGH report is already an action trigger).
_RISK_BAND_BINS = (
    (60.0, "HIGH"),
    (40.0, "MODERATE"),
    (0.0,  "LOW"),
)

_BAND_ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2}

# Tolerances are deliberately a touch wider than rounding error so a single
# extra rounding step in the renderer never trips the gate.
_PILLAR_SUM_TOLERANCE = 0.6
_GW_SUM_TOLERANCE = 1.0
_FALLBACK_DELTA_TRIP = 0.5  # ESG vs (100-GW) closer than this trips V3


def canonical_rating(esg_score: float) -> str:
    """Bin ESG score (0-100) -> rating letter (AAA..CCC). Pure function."""
    if not isinstance(esg_score, (int, float)):
        return "BBB"
    v = float(esg_score)
    for threshold, label in _RATING_BINS:
        if v >= threshold:
            return label
    return "CCC"


def canonical_band(headline_risk: float) -> str:
    """Bin headline risk score (0-100, high=bad) -> band. Pure function."""
    if not isinstance(headline_risk, (int, float)):
        return "MODERATE"
    v = float(headline_risk)
    for threshold, label in _RISK_BAND_BINS:
        if v >= threshold:
            return label
    return "LOW"


@dataclass
class Violation:
    rule_id: str
    severity: str  # "CRITICAL" | "HIGH" | "WARNING"
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    ok: bool
    violations: List[Violation] = field(default_factory=list)
    warnings: List[Violation] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "CRITICAL")

    def summary(self) -> str:
        if self.ok:
            return "consistency OK"
        head = f"{len(self.violations)} violation(s) ({self.critical_count} CRITICAL)"
        rules = ", ".join(sorted({v.rule_id for v in self.violations}))
        return f"{head}: {rules}"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "schema_version": self.schema_version,
            "violations": [v.as_dict() for v in self.violations],
            "warnings": [w.as_dict() for w in self.warnings],
            "summary": self.summary(),
        }


class ReportConsistencyError(Exception):
    """Raised when an export is blocked because the structured report is inconsistent."""

    def __init__(self, result: ValidationResult):
        self.result = result
        super().__init__(result.summary())


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            return None
    return None


def _v1_rating_matches_esg(rc: Dict[str, Any]) -> Optional[Violation]:
    esg = _coerce_float(rc.get("final_esg_display"))
    rating = str(rc.get("final_rating") or "").strip().upper()
    if esg is None or not rating:
        return None
    expected = canonical_rating(esg)
    if rating != expected:
        return Violation(
            rule_id="V1",
            severity="CRITICAL",
            message=(
                f"Displayed rating '{rating}' does not match canonical rating "
                f"'{expected}' for ESG={esg:.1f}. Rating must be a pure function "
                f"of the displayed ESG score."
            ),
            evidence={
                "final_esg_display": esg,
                "final_rating": rating,
                "expected_rating": expected,
            },
        )
    return None


def _v2_band_matches_headline(rc: Dict[str, Any]) -> Optional[Violation]:
    gw = _coerce_float(rc.get("final_gw_calibrated"))
    band = str(rc.get("final_band") or "").strip().upper()
    if gw is None or not band:
        return None
    floor_band = canonical_band(gw)
    band_rank = _BAND_ORDER.get(band)
    floor_rank = _BAND_ORDER.get(floor_band)
    if band_rank is None or floor_rank is None:
        return Violation(
            rule_id="V2",
            severity="HIGH",
            message=f"Unknown band label(s): displayed='{band}', floor='{floor_band}'.",
            evidence={"final_band": band, "floor_band": floor_band, "gw": gw},
        )
    if band_rank < floor_rank:
        return Violation(
            rule_id="V2",
            severity="CRITICAL",
            message=(
                f"Displayed band '{band}' is below the canonical floor "
                f"'{floor_band}' implied by GW={gw:.1f} (high-score-means-higher-risk)."
            ),
            evidence={
                "final_band": band,
                "canonical_floor": floor_band,
                "final_gw_calibrated": gw,
            },
        )
    if band_rank > floor_rank:
        # Allowed only if an applied-caps row explains the escalation.
        caps = rc.get("applied_caps") or []
        explained = any(
            isinstance(c, dict)
            and (c.get("affects") in ("band", "rating", "both"))
            for c in caps
        )
        if not explained:
            return Violation(
                rule_id="V2",
                severity="HIGH",
                message=(
                    f"Displayed band '{band}' is more severe than the GW floor "
                    f"'{floor_band}' (GW={gw:.1f}) but no applied_caps row explains "
                    f"the escalation."
                ),
                evidence={
                    "final_band": band,
                    "canonical_floor": floor_band,
                    "final_gw_calibrated": gw,
                    "applied_caps": caps,
                },
            )
    return None


def _v3_no_inverse_fallback(rc: Dict[str, Any]) -> Optional[Violation]:
    esg = _coerce_float(rc.get("final_esg_display"))
    gw = _coerce_float(rc.get("final_gw_calibrated"))
    if esg is None or gw is None:
        return None
    if abs((100.0 - gw) - esg) <= _FALLBACK_DELTA_TRIP and esg not in (0.0, 100.0):
        # If the resolver stamped an explicit pillar-derived basis, the
        # near-equality with 100-GW is coincidental and we trust it. The
        # only basis that should trip V3 is the inverse-fallback path
        # (esg_basis missing, or esg_basis='inverse_fallback').
        basis = str(rc.get("esg_basis", "")).lower()
        if basis.startswith("pillar_") or basis in ("scores_esg_score", "risk_results_esg_score"):
            return None
        return Violation(
            rule_id="V3",
            severity="CRITICAL",
            message=(
                f"ESG ({esg:.1f}) appears derived from GW via the 100-GW inverse "
                f"fallback (delta={(100.0 - gw) - esg:.2f}). ESG must come from "
                f"the pillar pipeline; missing pillar data should mark "
                f"esg_basis='insufficient_data' instead."
            ),
            evidence={
                "final_esg_display": esg,
                "final_gw_calibrated": gw,
                "esg_basis": rc.get("esg_basis"),
            },
        )
    return None


def _v4_pillar_sum_reconciles(structured: Dict[str, Any]) -> Optional[Violation]:
    rc = structured.get("report_consistency") or {}
    if str(rc.get("esg_basis", "")).lower() == "insufficient_data":
        return None
    esg = _coerce_float(rc.get("final_esg_display"))
    if esg is None:
        return None
    pillars = structured.get("pillars") or {}
    if not isinstance(pillars, dict):
        return None

    # Accept either the canonical {environmental:{score, weight}} shape
    # or the flat {environmental_score, social_score, governance_score} shape.
    weights = pillars.get("weights") if isinstance(pillars.get("weights"), dict) else None
    e = _coerce_float(_pillar_value(pillars, "environmental"))
    s = _coerce_float(_pillar_value(pillars, "social"))
    g = _coerce_float(_pillar_value(pillars, "governance"))
    if e is None or s is None or g is None:
        return None
    if weights:
        we = _coerce_float(weights.get("E") or weights.get("environmental")) or 0.35
        ws = _coerce_float(weights.get("S") or weights.get("social")) or 0.30
        wg = _coerce_float(weights.get("G") or weights.get("governance")) or 0.35
    else:
        we, ws, wg = 0.35, 0.30, 0.35
    total_w = we + ws + wg
    if total_w <= 0:
        return None
    weighted = (e * we + s * ws + g * wg) / total_w
    delta = abs(weighted - esg)
    if delta > _PILLAR_SUM_TOLERANCE:
        return Violation(
            rule_id="V4",
            severity="HIGH",
            message=(
                f"Pillar weighted sum {weighted:.2f} disagrees with displayed ESG "
                f"{esg:.2f} by {delta:.2f} (tolerance {_PILLAR_SUM_TOLERANCE})."
            ),
            evidence={
                "environmental": e, "social": s, "governance": g,
                "weights": {"E": we, "S": ws, "G": wg},
                "weighted_sum": round(weighted, 3),
                "final_esg_display": esg,
                "delta": round(delta, 3),
            },
        )
    return None


def _pillar_value(pillars: Dict[str, Any], pillar_name: str) -> Any:
    """Read a pillar score from either nested or flat representation."""
    block = pillars.get(pillar_name)
    if isinstance(block, dict):
        for key in ("score", "displayed_score", "coverageadjustedscore", "value"):
            v = block.get(key)
            if isinstance(v, (int, float)):
                return v
    flat = pillars.get(f"{pillar_name}_score")
    if isinstance(flat, (int, float)):
        return flat
    return None


def _v5_gw_components_reconcile(structured: Dict[str, Any]) -> Optional[Violation]:
    rc = structured.get("report_consistency") or {}
    gw_displayed = _coerce_float(rc.get("final_gw_calibrated"))
    gw_raw = _coerce_float(rc.get("final_gw_raw"))
    if gw_displayed is None:
        return None

    # The calibration delta is always allowed if it's flagged as an applied cap.
    caps = rc.get("applied_caps") or []
    cap_delta = sum(
        _coerce_float(c.get("delta") or 0.0) or 0.0
        for c in caps
        if isinstance(c, dict)
    )

    components = (structured.get("scores") or {}).get("greenwashing_components")
    if not isinstance(components, dict) or not components:
        # No components disclosed — only enforce the raw->calibrated delta is
        # explained by an applied_caps row.
        if gw_raw is not None and abs(gw_displayed - gw_raw) > _GW_SUM_TOLERANCE and not caps:
            return Violation(
                rule_id="V5",
                severity="HIGH",
                message=(
                    f"Calibrated GW ({gw_displayed:.1f}) differs from raw GW "
                    f"({gw_raw:.1f}) by {gw_displayed - gw_raw:+.1f} but no "
                    f"applied_caps row documents the calibration delta."
                ),
                evidence={
                    "final_gw_calibrated": gw_displayed,
                    "final_gw_raw": gw_raw,
                    "applied_caps": caps,
                },
            )
        return None

    summed = 0.0
    for key in ("alpha_term", "beta_term", "gamma_term", "delta_term"):
        v = _coerce_float(components.get(key))
        if v is not None:
            summed += v

    # Caps that modify a FORMULA INPUT (e.g. net_zero_claim_intensity_floor
    # which raises C before the formula runs) cause the gap term to recompute
    # internally. The post-cap component ledger captures the result — there
    # is no clean output-side `delta` to record. Skip strict reconciliation
    # in that case; the cap's reason field is the audit trail. This was the
    # source of the May-2026 V5 false-positive on JPMorgan's net-zero claim.
    has_input_modifying_cap = any(
        isinstance(c, dict) and str(c.get("affects", "")).startswith("formula_input")
        for c in caps
    )
    if has_input_modifying_cap:
        return None

    expected = summed + cap_delta
    if abs(expected - gw_displayed) > _GW_SUM_TOLERANCE:
        return Violation(
            rule_id="V5",
            severity="HIGH",
            message=(
                f"GW components sum + caps ({expected:.2f}) does not reconcile to "
                f"displayed GW ({gw_displayed:.2f}). Reader cannot reproduce the "
                f"headline from the breakdown."
            ),
            evidence={
                "components_sum": round(summed, 3),
                "applied_caps_delta": round(cap_delta, 3),
                "expected_gw": round(expected, 3),
                "final_gw_calibrated": gw_displayed,
            },
        )
    return None


def _v6_sigma_provenance_disclosed(structured: Dict[str, Any]) -> Optional[Violation]:
    """When the gap-term sigma did not come from a real ≥5-peer industry
    sample, the report must surface the provenance and tag the score as
    provisional. Otherwise a JPM-style cross-sector sigma silently
    distorts the gap term."""
    components = (structured.get("scores") or {}).get("greenwashing_components") or {}
    if not isinstance(components, dict) or not components:
        return None
    provenance = str(components.get("sigma_provenance") or "").lower()
    if not provenance:
        return Violation(
            rule_id="V6", severity="WARNING",
            message="sigma_provenance is missing; reader cannot tell whether "
                    "industry_sigma came from real peers or fallback.",
            evidence={"greenwashing_components_keys": list(components.keys())},
        )
    if provenance in ("cross_sector_global", "hardcoded_fallback"):
        rc = structured.get("report_consistency") or {}
        applied_caps = rc.get("applied_caps") or []
        # An applied_caps row of cap='cross_sector_sigma' or a
        # confidence_band='provisional' tag both satisfy the rule.
        disclosed = any(
            isinstance(c, dict) and "sigma" in str(c.get("cap", "")).lower()
            for c in applied_caps
        ) or bool(rc.get("provisional"))
        if not disclosed:
            return Violation(
                rule_id="V6", severity="WARNING",
                message=(
                    f"sigma_provenance='{provenance}' (peer count "
                    f"{components.get('sigma_n_peers')}); gap term may be "
                    f"distorted but no applied_caps / provisional flag "
                    f"discloses the fallback to the reader."
                ),
                evidence={
                    "sigma_provenance": provenance,
                    "sigma_n_peers": components.get("sigma_n_peers"),
                    "industry_sigma": components.get("industry_sigma"),
                },
            )
    return None


def _v8_confidence_language_coupling(structured: Dict[str, Any]) -> Optional[Violation]:
    """When confidence is below 60% and the band is HIGH or CRITICAL, the
    report must hedge the language with verdict_qualifier='indicative'."""
    rc = structured.get("report_consistency") or {}
    band = str(rc.get("final_band") or "").strip().upper()
    conf = _coerce_float(rc.get("confidence_pct"))
    qualifier = str(rc.get("verdict_qualifier") or "").strip().lower()
    if conf is None or conf <= 0:
        return None
    if band not in {"HIGH", "CRITICAL"}:
        return None
    if conf < 60.0 and qualifier != "indicative":
        return Violation(
            rule_id="V8",
            severity="HIGH",
            message=(
                f"band={band} at confidence={conf:.1f}% asserts certainty "
                f"on weak data. Required: verdict_qualifier='indicative' "
                f"(found {qualifier or 'absent'!r})."
            ),
            evidence={
                "final_band": band,
                "confidence_pct": conf,
                "verdict_qualifier": qualifier or None,
                "verdict_label": rc.get("verdict_label"),
            },
        )
    return None


def _v9_esg_pillar_strict(structured: Dict[str, Any]) -> Optional[Violation]:
    """ESG must equal the weighted pillar average. The May-2026 audit
    fix removed the historical-misconduct ESG ceiling — any remaining
    gap means a path is still mutating ESG outside the pillar pipeline.

    Strictness depends on whether weights are surfaced:
      * weights present (pillars.weights) → ±0.5 strict, CRITICAL on miss
      * weights absent → try a small set of common materiality profiles;
        if NONE reconciles within ±1.5 the rule trips HIGH (not CRITICAL)
        because we can't be certain it's a mutation vs a weight mismatch.
    """
    rc = structured.get("report_consistency") or {}
    if str(rc.get("esg_basis", "")).lower() == "insufficient_data":
        return None
    esg = _coerce_float(rc.get("final_esg_display"))
    if esg is None:
        return None
    pillars = structured.get("pillars") or {}
    if not isinstance(pillars, dict):
        return None
    e = _coerce_float(_pillar_value(pillars, "environmental"))
    s = _coerce_float(_pillar_value(pillars, "social"))
    g = _coerce_float(_pillar_value(pillars, "governance"))
    if e is None or s is None or g is None:
        return None

    explicit_weights = pillars.get("weights") if isinstance(pillars.get("weights"), dict) else None
    if explicit_weights:
        we = _coerce_float(explicit_weights.get("E") or explicit_weights.get("environmental")) or 0.35
        ws = _coerce_float(explicit_weights.get("S") or explicit_weights.get("social")) or 0.30
        wg = _coerce_float(explicit_weights.get("G") or explicit_weights.get("governance")) or 0.35
        total_w = we + ws + wg
        if total_w <= 0:
            return None
        weighted = (e * we + s * ws + g * wg) / total_w
        delta = abs(weighted - esg)
        if delta > 0.5:
            return Violation(
                rule_id="V9", severity="CRITICAL",
                message=(
                    f"ESG {esg:.2f} does not match weighted pillar average "
                    f"{weighted:.2f} (delta {delta:.2f}, weights surfaced). "
                    f"Historical-misconduct ESG ceilings are forbidden — "
                    f"ESG must reflect current pillar performance only."
                ),
                evidence={
                    "final_esg_display": esg,
                    "weighted_pillar_average": round(weighted, 3),
                    "pillars": {"E": e, "S": s, "G": g},
                    "weights": {"E": we, "S": ws, "G": wg, "source": "pillars.weights"},
                    "delta": round(delta, 3),
                },
            )
        return None

    # No explicit weights — try common materiality profiles.
    profiles = [
        ("default",         0.35, 0.30, 0.35),
        ("default_alt",     0.35, 0.35, 0.30),
        ("oil_and_gas",     0.48, 0.20, 0.32),
        ("coal",            0.52, 0.18, 0.30),
        ("banking",         0.20, 0.40, 0.40),
        ("technology",      0.30, 0.35, 0.35),
    ]
    deltas = []
    for name, we, ws, wg in profiles:
        total_w = we + ws + wg
        if total_w <= 0:
            continue
        weighted = (e * we + s * ws + g * wg) / total_w
        deltas.append((abs(weighted - esg), name, weighted, (we, ws, wg)))
    if not deltas:
        return None
    deltas.sort()
    best_delta, best_profile, best_weighted, best_weights = deltas[0]
    if best_delta > 1.5:
        return Violation(
            rule_id="V9", severity="HIGH",
            message=(
                f"ESG {esg:.2f} does not match any common materiality "
                f"profile (closest: {best_profile} → {best_weighted:.2f}, "
                f"delta {best_delta:.2f}). Likely a non-pillar mutation; "
                f"surface pillars.weights or fix the override."
            ),
            evidence={
                "final_esg_display": esg,
                "closest_profile": best_profile,
                "closest_weighted_avg": round(best_weighted, 3),
                "pillars": {"E": e, "S": s, "G": g},
                "tried_weights": {"E": best_weights[0], "S": best_weights[1], "G": best_weights[2]},
                "delta": round(best_delta, 3),
            },
        )
    return None


def _v7_decay_metadata_present(structured: Dict[str, Any]) -> Optional[Violation]:
    """When active enforcement penalties are present, each component must
    carry decay + relevance provenance so the audit fix
    (Dieselgate-vs-climate-claim) can be reproduced."""
    components = (structured.get("scores") or {}).get("greenwashing_components") or {}
    if not isinstance(components, dict) or not components:
        return None
    r_components = components.get("r_components") or []
    if not isinstance(r_components, list) or not r_components:
        return None
    missing = []
    for i, rec in enumerate(r_components):
        if not isinstance(rec, dict):
            missing.append(i)
            continue
        for k in ("decay", "relevance", "weighted", "base"):
            if rec.get(k) is None:
                missing.append((i, k))
                break
    if missing:
        return Violation(
            rule_id="V7", severity="HIGH",
            message=(
                f"{len(missing)} active enforcement contribution(s) missing "
                f"decay/relevance provenance. Reader cannot reproduce the "
                f"R-after-decay adjustment."
            ),
            evidence={
                "missing_indices": missing[:8],
                "n_components": len(r_components),
            },
        )
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def validate_report(structured: Dict[str, Any]) -> ValidationResult:
    """Validate the structured report dict. Never raises; returns a result."""
    if not isinstance(structured, dict):
        return ValidationResult(
            ok=False,
            violations=[Violation(
                rule_id="V0", severity="CRITICAL",
                message="structured report is not a dict",
            )],
        )
    rc = structured.get("report_consistency")
    if not isinstance(rc, dict):
        return ValidationResult(
            ok=False,
            violations=[Violation(
                rule_id="V0", severity="CRITICAL",
                message="structured report missing 'report_consistency' block",
            )],
        )

    violations: List[Violation] = []
    warnings: List[Violation] = []

    for rule in (
        _v1_rating_matches_esg(rc),
        _v2_band_matches_headline(rc),
        _v3_no_inverse_fallback(rc),
        _v4_pillar_sum_reconciles(structured),
        _v5_gw_components_reconcile(structured),
        _v6_sigma_provenance_disclosed(structured),
        _v7_decay_metadata_present(structured),
        _v8_confidence_language_coupling(structured),
        _v9_esg_pillar_strict(structured),
    ):
        if rule is None:
            continue
        if rule.severity in ("CRITICAL", "HIGH"):
            violations.append(rule)
        else:
            warnings.append(rule)

    return ValidationResult(
        ok=not any(v.severity == "CRITICAL" for v in violations),
        violations=violations,
        warnings=warnings,
    )
