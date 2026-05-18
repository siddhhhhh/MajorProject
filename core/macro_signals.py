"""Macro live-signal calibration (Gap 3).

Each event in data/macro_events.json may declare `live_signals[]`:
  - baseline_value: editorial anchor (when the curated exposure weights were set)
  - current_value: latest poll (null if unfetched)
  - calibration_band: {high_threshold/multiplier, low_threshold/multiplier}

This module evaluates those signals and returns a calibration multiplier
that scales the curated exposure. The multiplier is applied in the
counterfactual scenario only — never to the headline ESG/GW score.

Design:
- A pluggable `SignalProvider` interface fetches real numbers (Brent
  crude, GDELT counts, Baltic Dry Index, etc.).
- Default `NullSignalProvider` returns no data; events fall back to
  curated exposure with status `not_configured`.
- Provider selection via env var `ESG_MACRO_SIGNAL_PROVIDER`. Lets users
  wire in a real source without touching this file.

Invariant: NEVER mutates headline scoring. Read-only data layer.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class SignalProvider(Protocol):
    """A pluggable provider that reads one live signal value."""

    def fetch(self, signal_id: str, signal_def: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return `{value: float|int, fetched_at: iso8601, source: str}` or None.

        None means "not available right now" — the calling code treats the
        signal as unfetched (status `not_configured` or `stale`).
        """
        ...


class NullSignalProvider:
    """Default provider. Returns nothing — preserves curated exposure."""

    def fetch(self, signal_id: str, signal_def: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None


# Registry: name → factory. Add real providers here.
_PROVIDERS: Dict[str, Any] = {
    "null": NullSignalProvider,
}


def _resolve_provider() -> SignalProvider:
    """Pick a provider based on ESG_MACRO_SIGNAL_PROVIDER, default null."""
    name = (os.environ.get("ESG_MACRO_SIGNAL_PROVIDER") or "null").strip().lower()
    factory = _PROVIDERS.get(name)
    if factory is None:
        logger.warning("Unknown ESG_MACRO_SIGNAL_PROVIDER=%r — using null provider", name)
        factory = NullSignalProvider
    try:
        return factory()
    except Exception as exc:
        logger.warning("Signal provider %s failed to init: %s — using null", name, exc)
        return NullSignalProvider()


# Cache the provider for one process. Tests can clear with `_PROVIDER_CACHE.clear()`.
_PROVIDER_CACHE: Dict[str, SignalProvider] = {}


def get_provider() -> SignalProvider:
    """Cached accessor for the active SignalProvider."""
    if "current" not in _PROVIDER_CACHE:
        _PROVIDER_CACHE["current"] = _resolve_provider()
    return _PROVIDER_CACHE["current"]


def _clamp(x: float, lo: float = 0.5, hi: float = 1.5) -> float:
    """Keep calibration multipliers in a sane band."""
    return max(lo, min(hi, x))


def _evaluate_band(value: float, band: Dict[str, Any]) -> float:
    """Compute a multiplier based on where `value` falls in the band.

    Above high_threshold → high_multiplier. Below low → low_multiplier.
    Between → 1.0 (curated weight is correct).
    """
    if not isinstance(band, dict):
        return 1.0
    try:
        hi = float(band.get("high_threshold")) if band.get("high_threshold") is not None else None
        hi_m = float(band.get("high_multiplier")) if band.get("high_multiplier") is not None else 1.0
        lo = float(band.get("low_threshold")) if band.get("low_threshold") is not None else None
        lo_m = float(band.get("low_multiplier")) if band.get("low_multiplier") is not None else 1.0
    except (TypeError, ValueError):
        return 1.0
    if hi is not None and value >= hi:
        return _clamp(hi_m)
    if lo is not None and value <= lo:
        return _clamp(lo_m)
    return 1.0


def evaluate_signals(event: Dict[str, Any]) -> Dict[str, Any]:
    """Read all live_signals for an event and return a calibration summary.

    Output shape:
        {
            "status":              "not_configured" | "calibrated" | "out_of_band",
            "readings":            [{signal_id, value, source, fetched_at, multiplier}],
            "effective_multiplier": float (product of clamped per-signal multipliers),
        }

    `status=not_configured` if no signals returned a value. The effective
    multiplier defaults to 1.0 in that case so curated exposures stay intact.
    """
    signals = event.get("live_signals") or []
    if not isinstance(signals, list) or not signals:
        return {"status": "no_signals_declared", "readings": [], "effective_multiplier": 1.0}

    provider = get_provider()
    readings: List[Dict[str, Any]] = []
    multipliers: List[float] = []

    for sig in signals:
        if not isinstance(sig, dict):
            continue
        sid = sig.get("signal_id") or "unknown"

        polled = provider.fetch(sid, sig)
        if polled is None:
            # Fall back to current_value in JSON (if a human pre-filled it).
            cur = sig.get("current_value")
            if cur is not None:
                polled = {
                    "value": cur,
                    "fetched_at": sig.get("current_as_of") or "",
                    "source": "json_baseline",
                }

        if polled is None or polled.get("value") is None:
            readings.append({
                "signal_id":   sid,
                "value":       None,
                "fetched_at":  None,
                "source":      "not_fetched",
                "multiplier":  1.0,
                "baseline":    sig.get("baseline_value"),
            })
            continue

        try:
            value = float(polled["value"])
        except (TypeError, ValueError):
            continue

        mult = _evaluate_band(value, sig.get("calibration_band") or {})
        multipliers.append(mult)
        readings.append({
            "signal_id":   sid,
            "value":       value,
            "fetched_at":  polled.get("fetched_at"),
            "source":      polled.get("source", "live"),
            "multiplier":  round(mult, 3),
            "baseline":    sig.get("baseline_value"),
        })

    if not multipliers:
        return {
            "status":               "not_configured",
            "readings":             readings,
            "effective_multiplier": 1.0,
        }

    eff = 1.0
    for m in multipliers:
        eff *= m
    eff = _clamp(eff, lo=0.5, hi=1.5)

    status = "calibrated"
    if eff > 1.001 or eff < 0.999:
        status = "out_of_band"

    return {
        "status":               status,
        "readings":             readings,
        "effective_multiplier": round(eff, 3),
        "evaluated_at":         datetime.now(timezone.utc).isoformat(),
    }


def calibrate_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply `evaluate_signals` to a list of events. Each output dict carries
    `event_id` + the calibration summary."""
    out: List[Dict[str, Any]] = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        summary = evaluate_signals(ev)
        out.append({
            "event_id": ev.get("event_id"),
            "name":     ev.get("name"),
            **summary,
        })
    return out
