"""Time-decay and claim-relevance gating for ESG/greenwashing penalties.

This module implements two of the May-2026 audit recommendations:

  * **Time-decay** — old controversies should not dominate a current
    claim's evaluation. ``decay_weight(years_since, pillar)`` returns
    ``exp(-years_since / tau_pillar)`` with pillar-specific tau values.
    Active (still-litigated) enforcement bypasses decay entirely.

  * **Claim-relevance gating** — a governance scandal should weigh less
    against an environmental claim than against a governance claim. The
    matrix in ``config/penalty_relevance.json`` is the canonical source.

The module is intentionally lightweight — pure functions, single config
load, no global state. Risk-scoring callers compose them via
``weighted_penalty_contribution`` so each penalty contributes
``base × decay × relevance`` to the aggregator and the per-incident
metadata is recorded for the validator (V7).

Pillar values are normalised to ``"environmental" | "social" | "governance"``;
unknown values fall through to a configurable default weight.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


_CONFIG_PATH = os.environ.get(
    "ESG_PENALTY_RELEVANCE_PATH",
    os.path.join("config", "penalty_relevance.json"),
)

# Cached config; loaded on first use. Re-read at most once per process.
_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
            _CONFIG_CACHE = json.load(fh)
    except Exception:
        # Safe defaults if config disappears — system stays in safe pass-through mode.
        _CONFIG_CACHE = {
            "version": 0,
            "default_weight_when_unknown": 1.0,
            "matrix": {},
            "decay_tau_years_by_pillar": {
                "environmental": 8.0, "social": 6.0, "governance": 4.0,
            },
            "active_enforcement_decay_override": 1.0,
        }
    return _CONFIG_CACHE


_PILLAR_ALIASES = {
    "e": "environmental", "env": "environmental", "environment": "environmental",
    "environmental": "environmental",
    "s": "social", "soc": "social", "social": "social",
    "g": "governance", "gov": "governance", "governance": "governance",
}


def normalise_pillar(value: Any) -> Optional[str]:
    """Coerce loose pillar labels (E/S/G/env/...) to canonical names."""
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    if not key:
        return None
    return _PILLAR_ALIASES.get(key)


# ---------------------------------------------------------------------------
# Claim pillar classifier
# ---------------------------------------------------------------------------

# Keyword signals — kept conservative. The classifier returns None when no
# pillar dominates so the relevance matrix falls back to its default weight
# rather than misweighting an ambiguous claim.
_E_SIGNALS = re.compile(
    r"\b(carbon|climate|emission|emissions|net[\s-]?zero|ghg|greenhouse|"
    r"renewable|fossil|coal|oil|gas|deforest|biodivers|water|waste|"
    r"recycling|circular|scope[\s-]?[123]|sbti|paris|1\.5|1\.5°c|"
    r"environmental|pollution|methane|co2)\b",
    re.IGNORECASE,
)
_S_SIGNALS = re.compile(
    r"\b(diversity|inclusion|equity|gender|labor|labour|human\s+rights|"
    r"safety|community|stakeholder|customer|privacy|wage|union|"
    r"supplier|supply\s+chain|workforce|employee|workplace|d&i|dei|"
    r"social)\b",
    re.IGNORECASE,
)
_G_SIGNALS = re.compile(
    r"\b(board|director|executive\s+pay|compensation|audit|whistleblow|"
    r"corruption|bribery|tax|governance|disclosure|transparency|"
    r"oversight|fiduciary|shareholder|proxy|control|fraud|"
    r"non[\s-]?compliance)\b",
    re.IGNORECASE,
)


def classify_claim_pillar(claim_text: Any) -> Optional[str]:
    """Best-effort pillar classification of a free-text claim. None when ambiguous."""
    if not isinstance(claim_text, str) or not claim_text.strip():
        return None
    e = len(_E_SIGNALS.findall(claim_text))
    s = len(_S_SIGNALS.findall(claim_text))
    g = len(_G_SIGNALS.findall(claim_text))
    counts = {"environmental": e, "social": s, "governance": g}
    top_pillar, top_count = max(counts.items(), key=lambda kv: kv[1])
    if top_count == 0:
        return None
    # Require the top pillar to lead by at least 1 signal — otherwise treat as ambiguous.
    second = sorted(counts.values(), reverse=True)[1]
    if top_count - second < 1:
        return None
    return top_pillar


# ---------------------------------------------------------------------------
# Decay
# ---------------------------------------------------------------------------

def years_since(year: Any, *, today: Optional[datetime] = None) -> Optional[float]:
    """Approximate years between ``year`` (int or 4-digit string) and today.

    Returns None when the year cannot be parsed. Negative values (future
    years) are clamped to 0 so they don't accidentally amplify the penalty.
    """
    if isinstance(year, (int, float)):
        y = int(year)
    elif isinstance(year, str):
        m = re.search(r"\b(19|20)\d{2}\b", year)
        if not m:
            return None
        y = int(m.group(0))
    else:
        return None
    now = today or datetime.utcnow()
    delta = now.year + (now.month - 1) / 12.0 - float(y)
    return max(0.0, delta)


def decay_weight(
    incident_year: Any,
    incident_pillar: Optional[str],
    *,
    is_active: bool = False,
) -> Tuple[float, str]:
    """Return ``(weight, reason)`` for a dated incident.

    * ``is_active=True`` -> 1.0 (active enforcement override)
    * year unparseable -> 1.0 (safe pass-through; reason='no_date')
    * pillar unknown -> use the longest-memory tau (environmental=8) so
      we don't accidentally erase a recent governance event
    """
    cfg = _load_config()
    if is_active:
        return float(cfg.get("active_enforcement_decay_override", 1.0)), "active_enforcement"
    yrs = years_since(incident_year)
    if yrs is None:
        return 1.0, "no_date"
    tau_map = cfg.get("decay_tau_years_by_pillar", {}) or {}
    pillar_norm = normalise_pillar(incident_pillar) or "environmental"
    tau = float(tau_map.get(pillar_norm, 8.0))
    if tau <= 0:
        return 1.0, "tau_zero_passthrough"
    w = math.exp(-yrs / tau)
    return w, f"decay_tau_{pillar_norm}_{tau}_years_{yrs:.1f}"


# ---------------------------------------------------------------------------
# Relevance
# ---------------------------------------------------------------------------

def relevance_weight(
    claim_pillar: Optional[str],
    incident_pillar: Optional[str],
) -> Tuple[float, str]:
    """Return ``(weight, reason)`` for an incident vs the claim's pillar.

    Falls back to the configured default when either side is unknown.
    """
    cfg = _load_config()
    matrix = cfg.get("matrix") or {}
    default = float(cfg.get("default_weight_when_unknown", 1.0))
    cp = normalise_pillar(claim_pillar)
    ip = normalise_pillar(incident_pillar)
    if cp is None or ip is None:
        return default, f"unknown_pillar(claim={cp},incident={ip})"
    row = matrix.get(cp, {})
    if ip not in row:
        return default, f"missing_matrix_cell(claim={cp},incident={ip})"
    return float(row[ip]), f"matrix({cp}<-{ip})"


# ---------------------------------------------------------------------------
# Composite — what risk_scorer should call per incident
# ---------------------------------------------------------------------------

@dataclass
class WeightedPenalty:
    base: float
    weighted: float
    decay: float
    relevance: float
    incident_pillar: Optional[str]
    claim_pillar: Optional[str]
    incident_year: Optional[Any]
    is_active: bool
    decay_reason: str
    relevance_reason: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def weighted_penalty_contribution(
    base_penalty: float,
    *,
    incident_pillar: Optional[str],
    claim_pillar: Optional[str],
    incident_year: Optional[Any] = None,
    is_active: bool = False,
) -> WeightedPenalty:
    """Compose decay + relevance into a single weighted penalty record.

    The ``base_penalty`` is the original weight (e.g. 25 for an active
    enforcement, 20 per independent contradiction). The returned record
    carries ``weighted = base × decay × relevance`` plus full provenance
    so the report layer can show the math.
    """
    decay, decay_reason = decay_weight(incident_year, incident_pillar, is_active=is_active)
    rel, rel_reason = relevance_weight(claim_pillar, incident_pillar)
    weighted = float(base_penalty) * decay * rel
    return WeightedPenalty(
        base=float(base_penalty),
        weighted=round(weighted, 3),
        decay=round(decay, 3),
        relevance=round(rel, 3),
        incident_pillar=normalise_pillar(incident_pillar),
        claim_pillar=normalise_pillar(claim_pillar),
        incident_year=incident_year,
        is_active=is_active,
        decay_reason=decay_reason,
        relevance_reason=rel_reason,
    )
