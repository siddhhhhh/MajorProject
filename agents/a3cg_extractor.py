"""A3CG triplet extractor — Aspect-Action-Outcome typed claim extraction.

NAACL 2025 method. Replaces brittle regex + free-form LLM prompts with a
structured `(aspect, action, outcome)` triplet per claim. Downstream consumers
(promise tracker, contradiction analyzer, counterfactual) get typed objects
instead of opaque text.

Output schema:
    {aspect: emissions|water|labor|governance|...,
     action: reduce|increase|maintain|achieve|disclose|...,
     outcome_value: number|null,
     outcome_unit: tCO2e|%|count|...,
     outcome_year: int|null,
     evidence_class: quantified|directional|aspirational}

Feature-flagged behind ESG_USE_A3CG=1. When off, falls back to today's
regex/LLM extraction path so existing tests stay green.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_VALID_ASPECTS = {
    "emissions", "scope1_emissions", "scope2_emissions", "scope3_emissions",
    "energy", "renewable_energy", "water", "waste", "biodiversity",
    "labor", "diversity", "safety", "human_rights", "supply_chain",
    "governance", "board", "compensation", "disclosure", "transparency",
}
_VALID_ACTIONS = {
    "reduce", "decrease", "cut", "lower",
    "increase", "raise", "grow", "expand",
    "maintain", "preserve",
    "achieve", "reach", "attain",
    "disclose", "report", "publish",
    "phase_out", "eliminate", "remove",
    "validate", "certify", "audit",
}

_YEAR_RE = re.compile(r"\b(20\d{2})\b")
# Quantitative value — must NOT be a 4-digit year. Pinning to followed-by-unit
# avoids picking the first 2-3 digits of a year like "2030" as a value.
_QUANT_RE = re.compile(
    r"\b(?P<val>\d{1,3}(?:\.\d+)?)\s*(?P<unit>%|x\b|tonnes|tco2e|gtco2e|mtco2e|mw|gw|twh|million|billion)",
    re.I,
)


def _is_enabled() -> bool:
    return os.environ.get("ESG_USE_A3CG", "").lower() in ("1", "true", "yes")


def _classify_aspect(text: str) -> str:
    t = text.lower()
    if "scope 1" in t or "scope1" in t:
        return "scope1_emissions"
    if "scope 2" in t or "scope2" in t:
        return "scope2_emissions"
    if "scope 3" in t or "scope3" in t:
        return "scope3_emissions"
    if "emission" in t or "carbon" in t or "ghg" in t or "co2" in t:
        return "emissions"
    if "coal" in t or "fossil" in t:
        return "emissions"  # phase-out of fossil fuel = emissions reduction
    if "renewable" in t or "solar" in t or "wind" in t:
        return "renewable_energy"
    if "water" in t:
        return "water"
    if "waste" in t or "recycl" in t:
        return "waste"
    if "biodivers" in t or "deforest" in t:
        return "biodiversity"
    if "labor" in t or "worker" in t or "safety" in t:
        return "labor"
    if "divers" in t or "inclus" in t:
        return "diversity"
    if "board" in t or "governance" in t or "audit" in t:
        return "governance"
    if "disclose" in t or "transparen" in t or "report" in t:
        return "disclosure"
    return "general"


def _classify_action(text: str) -> str:
    t = text.lower()
    for a in ("reduce", "decrease", "cut", "lower",
              "phase out", "eliminate", "remove",
              "achieve", "reach", "attain",
              "increase", "raise", "grow", "expand",
              "maintain", "preserve",
              "disclose", "report", "publish",
              "validate", "certify"):
        if a in t:
            return a.replace(" ", "_")
    if "net zero" in t or "carbon neutral" in t:
        return "achieve"
    return "commit"


def _classify_evidence_class(action: str, outcome_value, outcome_year) -> str:
    if outcome_value is not None and outcome_year:
        return "quantified"
    if outcome_year:
        return "directional"
    return "aspirational"


def extract_triplet(text: str) -> Optional[Dict[str, Any]]:
    """Pure-Python extractor (no LLM call). Returns triplet dict or None."""
    if not text or len(text.strip()) < 5:
        return None
    aspect = _classify_aspect(text)
    action = _classify_action(text)
    year_match = _YEAR_RE.search(text)
    year = int(year_match.group(1)) if year_match else None

    # Outcome value + unit
    value: Optional[float] = None
    unit: Optional[str] = None
    # Net-zero is a special case: outcome = 0 / target_year
    if "net zero" in text.lower() or "carbon neutral" in text.lower():
        value = 0.0
        unit = "tCO2e"
    else:
        m = _QUANT_RE.search(text)
        if m:
            try:
                value = float(m.group("val"))
                unit = (m.group("unit") or "").lower() or None
            except (TypeError, ValueError):
                value = None

    return {
        "aspect":          aspect if aspect in _VALID_ASPECTS else "general",
        "action":          action if action in _VALID_ACTIONS else "commit",
        "outcome_value":   value,
        "outcome_unit":    unit,
        "outcome_year":    year,
        "evidence_class":  _classify_evidence_class(action, value, year),
        "claim_text":      text[:300],
        "extractor":       "a3cg_v1",
    }


def extract_for_claims(sub_claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply A3CG to a list of sub-claims. Each input claim gets a triplet."""
    if not _is_enabled():
        return []
    out: List[Dict[str, Any]] = []
    for sc in sub_claims or []:
        if not isinstance(sc, dict):
            continue
        text = sc.get("text") or sc.get("claim") or ""
        triplet = extract_triplet(text)
        if not triplet:
            continue
        triplet["sub_claim_id"] = sc.get("id")
        out.append(triplet)
    return out
