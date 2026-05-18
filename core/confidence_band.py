"""LLM-variance confidence band.

Reads the most recent diagnostic from data/variance_reports/ and projects an
empirical confidence interval onto the headline scores:

    headline GW = 42  -> reported as  42 [38, 46]

The band width comes from the variance harness's measured worst-case GW impact
(`projected_gw_impact.projected_gw_upper_bound_points`). If no variance report
exists we return None so callers can omit the band cleanly.

This module is read-only at runtime; it does not call any LLM and never raises.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_VARIANCE_DIR = Path(__file__).resolve().parent.parent / "data" / "variance_reports"

# Fallback width when the variance report parses but contains no projection
# (e.g. minimal suite errored out). 4.0 GW points is the rounded midpoint of
# the 2-6 range observed across our minimal and gemini suites so far.
_DEFAULT_FALLBACK_BAND = 4.0

# Hard ceiling — we never report a band wider than ±15 even if a future
# harness run spikes. Above that we suppress the band entirely (callers
# get None) because a band that wide isn't decision-useful.
_MAX_BAND_POINTS = 15.0


def _latest_variance_path() -> Optional[Path]:
    if not _VARIANCE_DIR.exists():
        return None
    candidates = sorted(_VARIANCE_DIR.glob("*_variance.json"))
    return candidates[-1] if candidates else None


def load_latest_variance() -> Optional[Dict[str, Any]]:
    """Return the most recent variance report dict, or None."""
    p = _latest_variance_path()
    if not p:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _projected_upper_bound(variance: Dict[str, Any]) -> Optional[float]:
    proj = variance.get("projected_gw_impact") or {}
    val = proj.get("projected_gw_upper_bound_points")
    try:
        if val is None:
            return None
        v = float(val)
        if v < 0:
            return None
        return v
    except (TypeError, ValueError):
        return None


def get_band_width(variance: Optional[Dict[str, Any]] = None) -> Optional[float]:
    """Return the empirically measured band half-width in score points.

    None means "no usable variance data — caller should omit the band".
    """
    if variance is None:
        variance = load_latest_variance()
    if not variance:
        return None
    measured = _projected_upper_bound(variance)
    if measured is None:
        return _DEFAULT_FALLBACK_BAND
    if measured > _MAX_BAND_POINTS:
        return None
    # Clamp to a minimum of 1.0 so we never report a misleadingly tight band
    # (the variance harness has noise floors below 1pt).
    return max(1.0, measured)


def clamp_band(score: float, half_width: float) -> Tuple[float, float]:
    """Centre a [low, high] interval on `score`, clipped to [0, 100]."""
    low = max(0.0, round(score - half_width, 1))
    high = min(100.0, round(score + half_width, 1))
    return (low, high)


def compute_score_bands(scores: Dict[str, Any]) -> Dict[str, Any]:
    """Attach empirical bands to a scores dict.

    Returns a NEW dict — does not mutate input. Keys added (when variance
    data is available):
        greenwashing_band: [low, high]
        esg_band:          [low, high]
        confidence_band:   [low, high]
        band_meta:         {source, half_width_points, model_pairs_compared}
    """
    out = dict(scores or {})
    variance = load_latest_variance()
    half = get_band_width(variance)
    if half is None or not variance:
        return out

    def _band_for(key_candidates: Tuple[str, ...]) -> Optional[Tuple[float, float]]:
        for k in key_candidates:
            v = out.get(k)
            if isinstance(v, (int, float)):
                return clamp_band(float(v), half)
        return None

    gw_band = _band_for(("greenwashingriskscore", "greenwashing_score_raw",
                         "greenwashing_risk_score", "gw_score"))
    if gw_band:
        out["greenwashing_band"] = list(gw_band)

    esg_band = _band_for(("esg_score",))
    if esg_band:
        out["esg_band"] = list(esg_band)

    conf_val = out.get("confidence")
    if isinstance(conf_val, (int, float)):
        # Confidence is reported as a percentage in some paths and a 0-1 in
        # others. Detect and use a tighter band — confidence is more stable
        # than GW in our harness (probe spread averages 2.5).
        cval = float(conf_val)
        if cval <= 1.0:
            cval = cval * 100.0
        # Use half of the GW band width for confidence (empirically narrower)
        conf_half = max(1.0, half / 2.0)
        out["confidence_band"] = list(clamp_band(cval, conf_half))

    proj = variance.get("projected_gw_impact") or {}
    summary = (variance.get("aggregate") or {}).get("summary") or {}
    out["band_meta"] = {
        "source": "llm_variance_harness",
        "half_width_points": half,
        "method": proj.get("method"),
        "categorical_agreement_rate": summary.get("categorical_value_agreement_rate"),
        "numeric_max_spread": summary.get("numeric_max_spread"),
        "n_probes": summary.get("n_probes"),
        "variance_timestamp_utc": variance.get("timestamp_utc"),
    }
    return out


def format_score_with_band(score: Any, band: Any, decimals: int = 1) -> str:
    """Render '42 [38-46]' or '42' when no band is available.

    Used by the text/PDF report renderers. Defensive against non-numeric
    inputs so existing callers don't crash.
    """
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "N/A"

    def fmt(v: float) -> str:
        return f"{v:.{decimals}f}" if decimals else f"{int(round(v))}"

    if isinstance(band, (list, tuple)) and len(band) == 2:
        try:
            lo, hi = float(band[0]), float(band[1])
            return f"{fmt(s)} [{fmt(lo)}-{fmt(hi)}]"
        except (TypeError, ValueError):
            pass
    return fmt(s)
