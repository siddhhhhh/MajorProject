"""Multimodal ESG extractor — Gemini-vision over PDF for table/chart facts.

MMESGBench (2025) shows text-only extraction misses ~30% of disclosure facts
that live in tables and charts. Asian disclosures are particularly heavy on
tabular content.

Uses our existing Gemini client (data is passed as PDF bytes via the
already-built `pdf_bytes` parameter of `call_llm`).

Output: list of structured table rows with provenance.

Feature-flagged behind ESG_USE_MULTIMODAL=1.

Public API:
    extract_tables_from_pdf(pdf_bytes, company) -> Dict
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_VISION_PROMPT = """You are extracting structured ESG data from this annual / sustainability report PDF.
Return a JSON object with this shape:

{
  "tables": [
    {
      "table_id": "T1",
      "page": <int>,
      "title": "<short>",
      "columns": ["col1", "col2", ...],
      "rows": [[<v1>, <v2>, ...], ...],
      "topic": "emissions|water|labor|governance|financial|other",
      "confidence": 0.0-1.0
    }
  ],
  "chart_facts": [
    {"fact": "<single sentence>", "value": <number|null>, "unit": "<str|null>",
     "year": <int|null>, "page": <int>, "topic": "<str>"}
  ]
}

Constraints:
- Only include tables/charts that contain numeric ESG-relevant data (emissions,
  energy, water, waste, diversity %, board composition, financials with
  environmental angle, regulatory penalties).
- For each table, include the column headers exactly as printed.
- Do NOT extract narrative text — that's done elsewhere.
- Return strictly valid JSON. No markdown, no commentary.
"""


def _is_enabled() -> bool:
    return os.environ.get("ESG_USE_MULTIMODAL", "").lower() in ("1", "true", "yes")


def _clean_response(raw: str) -> str:
    """Strip markdown fences if model returned them despite the prompt."""
    if not raw:
        return ""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"```$", "", text).strip()
    return text


def extract_tables_from_pdf(
    pdf_bytes: bytes,
    company: str = "",
    max_response_chars: int = 25000,
) -> Dict[str, Any]:
    """Single Gemini call against the PDF bytes; parse JSON response."""
    if not _is_enabled():
        return {"status": "DISABLED", "tables": [], "chart_facts": []}
    if not pdf_bytes:
        return {"status": "NO_PDF", "tables": [], "chart_facts": []}

    try:
        from core.llm_call import call_llm
    except Exception as e:
        return {"status": "LLM_UNAVAILABLE", "error": str(e), "tables": [], "chart_facts": []}

    prompt = _VISION_PROMPT
    if company:
        prompt += f"\n\nCompany: {company}"

    try:
        raw = asyncio.run(call_llm(
            agent="carbon_extraction",   # reuse the agent that already has gemini in chain
            prompt=prompt,
            pdf_bytes=pdf_bytes,
            use_cache=True,
        ))
    except Exception as e:
        return {"status": "LLM_ERROR", "error": str(e), "tables": [], "chart_facts": []}

    raw_clean = _clean_response(raw)[:max_response_chars]
    try:
        data = json.loads(raw_clean)
    except json.JSONDecodeError as e:
        return {
            "status":      "PARSE_ERROR",
            "error":       f"JSON parse failed: {e}",
            "raw_excerpt": raw_clean[:500],
            "tables":      [], "chart_facts": [],
        }
    return {
        "status":       "COMPLETED",
        "tables":       data.get("tables") or [],
        "chart_facts":  data.get("chart_facts") or [],
        "table_count":  len(data.get("tables") or []),
        "fact_count":   len(data.get("chart_facts") or []),
        "extractor":    "multimodal_v1_gemini_vision",
    }


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pipeline entry: pulls the freshest cached PDF and runs vision extraction."""
    out: Dict[str, Any] = {
        "agent":       "multimodal_extractor",
        "status":      "NO_PDF",
        "tables":      [],
        "chart_facts": [],
        "rationale":   "",
    }
    if not _is_enabled():
        out["status"] = "DISABLED"
        out["rationale"] = "Set ESG_USE_MULTIMODAL=1 to enable."
        return out

    # Find downloaded PDF bytes in agent_outputs
    pdf_bytes: Optional[bytes] = None
    for ao in state.get("agent_outputs") or []:
        if not isinstance(ao, dict):
            continue
        if ao.get("agent") not in ("report_parser", "report_downloader"):
            continue
        out_obj = ao.get("output") or {}
        if not isinstance(out_obj, dict):
            continue
        downloads = out_obj.get("downloads") or out_obj.get("downloaded_reports") or []
        for d in downloads:
            if not isinstance(d, dict):
                continue
            p = d.get("local_path") or d.get("path")
            if p and os.path.exists(p):
                try:
                    with open(p, "rb") as f:
                        pdf_bytes = f.read()
                    break
                except Exception as e:
                    logger.warning("Failed reading PDF %s: %s", p, e)
        if pdf_bytes:
            break

    if not pdf_bytes:
        out["rationale"] = "No downloaded PDF available in agent_outputs."
        return out

    result = extract_tables_from_pdf(pdf_bytes, company=state.get("company", ""))
    out.update(result)
    out["rationale"] = (
        f"Extracted {result.get('table_count', 0)} tables and "
        f"{result.get('fact_count', 0)} chart facts via multimodal vision."
    )
    return out
