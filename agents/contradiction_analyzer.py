import json
import logging
from typing import Dict, Any, List, Optional

from core.llm_client import llm_client
from config.agent_prompts import CONTRADICTION_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)

class ContradictionAnalyzer:
    def __init__(self):
        self.name = "Contradiction & Verification Analyst"
        self.llm = llm_client

    def analyze(self, claim_text: str, evidence: List[Dict[str, Any]], company: str = "") -> Dict[str, Any]:
        """Compatibility entrypoint used by wrappers."""
        return self.analyze_contradictions(company=company, claim=claim_text, evidence=evidence)

    def analyze_contradictions(
        self,
        company: str,
        claim: str,
        evidence: List[Dict[str, Any]],
        contradicting_evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Deterministic contradiction analysis merging known DB + evidence + LLM signals."""
        known = self._check_known_contradictions(company=company, claim_text=claim)

        prioritized = list(contradicting_evidence or [])
        if not prioritized:
            prioritized = [
                e for e in (evidence or [])
                if str(e.get("stance", e.get("relationship_to_claim", ""))).lower() == "contradicts"
            ]

        evidence_contradictions = self._extract_contradictions_from_evidence(prioritized)

        try:
            llm_found = self._run_llm_contradiction_scan(claim=claim, evidence=evidence, temperature=0)
        except Exception as exc:
            logger.warning("LLM contradiction scan failed: %s", exc)
            llm_found = []

        merged = self._merge_contradictions(known, evidence_contradictions, llm_found)

        return {
            "contradictions_found": len(merged),
            "contradiction_list": merged,
            "most_severe": self._most_severe(merged),
            "db_matches": len(known),
            "llm_matches": len(llm_found),
            "evidence_matches": len(evidence_contradictions),
            "contradictions": merged,
            "controversy_count": len(merged),
            "assessment": "Clean" if not merged else f"{len(merged)} confirmed case(s)",
            "confidence": 0.5 if not merged else 0.8,
        }

    def analyze_claim(self, claim: Dict[str, Any], evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze claim against evidence to detect contradictions
        """
        claim_id = claim.get("claim_id")
        claim_text = claim.get("claim_text", "")

        print(f"\n{'='*60}")
        print(f"🔍 AGENT 3: {self.name}")
        print(f"{'='*60}")
        print(f"Claim ID: {claim_id}")
        print(f"Claim: {claim_text[:100]}...")
        print(f"Evidence items: {len(evidence)}")

        contradicting = [
            e for e in evidence
            if str(e.get("stance", e.get("relationship_to_claim", ""))).lower() == "contradicts"
        ]

        merged = self.analyze_contradictions(
            company=claim.get("company", ""),
            claim=claim_text,
            evidence=evidence,
            contradicting_evidence=contradicting,
        )

        supporting = [e for e in evidence if str(e.get("relationship_to_claim", "")).lower() == "supports"]
        neutral = [e for e in evidence if str(e.get("relationship_to_claim", "")).lower() == "neutral"]
        merged["claim_id"] = claim_id
        merged["overall_verdict"] = "Contradicted" if merged["contradictions_found"] > 0 else "Unverifiable"
        merged["verification_confidence"] = int((merged.get("confidence") or 0.5) * 100)
        merged["specific_contradictions"] = merged.get("contradiction_list", [])
        merged["supportive_evidence"] = [e.get("source_name") for e in supporting[:3]]
        merged["evidence_counts"] = {
            "supporting": len(supporting),
            "contradicting": len(contradicting),
            "neutral": len(neutral),
        }
        return merged

    def _normalize_known_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        desc = case.get("contradiction_text") or case.get("description") or "Known contradiction case"
        sev = str(case.get("severity", "LOW")).upper()
        return {
            "severity": sev,
            "description": desc,
            "source": case.get("source", "Known contradictions database"),
            "source_url": case.get("source_url", ""),
            "year": case.get("year"),
            "confidence": case.get("confidence", "HIGH"),
            "source_type": case.get("source_type", "verified_regulatory_case"),
        }

    def _extract_contradictions_from_evidence(self, evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        contradictions = []
        for item in evidence or []:
            description = item.get("snippet") or item.get("relevant_text") or item.get("title") or ""
            if not description:
                continue
            contradictions.append({
                "severity": "MEDIUM",
                "description": description[:300],
                "source": item.get("source_name") or item.get("source") or "Evidence retrieval",
                "source_url": item.get("url", ""),
                "year": item.get("year"),
                "confidence": "MEDIUM",
                "source_type": "retrieved_evidence",
            })
        return contradictions

    def _run_llm_contradiction_scan(
        self, claim: str, evidence: List[Dict[str, Any]], temperature: float = 0
    ) -> List[Dict[str, Any]]:
        evidence_summary = self._prepare_evidence_summary(evidence)
        prompt = CONTRADICTION_ANALYSIS_PROMPT.format(
            claim=claim,
            evidence=evidence_summary,
            claim_id="C1",
        )
        response = self.llm.call_gemini(prompt, temperature=0, use_pro=True)
        if not response:
            return []

        cleaned = self._clean_json_response(response)
        payload = json.loads(cleaned)
        found = payload.get("specific_contradictions") or payload.get("contradictions") or []
        if not isinstance(found, list):
            return []

        normalized = []
        for c in found:
            if not isinstance(c, dict):
                continue
            normalized.append({
                "severity": str(c.get("severity", "LOW")).upper(),
                "description": c.get("description") or c.get("contradiction_text") or "Potential contradiction",
                "source": c.get("source", "LLM evidence synthesis"),
                "source_url": c.get("source_url", ""),
                "year": c.get("year"),
                "confidence": c.get("confidence", "LOW"),
                "source_type": "llm_scan",
            })
        return normalized

    def _merge_contradictions(self, known: List[Dict[str, Any]], evidence_found: List[Dict[str, Any]], llm_found: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized_known = [self._normalize_known_case(k) for k in (known or [])]
        merged = list(normalized_known)

        def seen_key(item: Dict[str, Any]) -> str:
            source = str(item.get("source") or "").strip().lower()
            year = str(item.get("year") or "").strip()
            if source or year:
                return f"{source}|{year}"
            return str(item.get("description") or "").strip().lower()[:120]

        seen = {seen_key(i) for i in merged}

        for bucket in ((evidence_found or []) + (llm_found or [])):
            if not isinstance(bucket, dict):
                continue
            key = seen_key(bucket)
            if key in seen:
                continue
            seen.add(key)
            merged.append(bucket)

        return merged

    def _most_severe(self, contradictions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not contradictions:
            return None
        rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        return max(contradictions, key=lambda x: rank.get(str(x.get("severity", "LOW")).upper(), 0))

    def _prepare_evidence_summary(self, evidence: List[Dict]) -> str:
        """Prepare concise evidence summary for LLM"""
        summary_parts = []
        # Group by source type for better analysis
        by_type = {}
        for ev in evidence[:20]:  # Limit to top 20
            source_type = ev.get('source_type', 'Unknown')
            if source_type not in by_type:
                by_type[source_type] = []
            by_type[source_type].append(ev)
        for source_type, items in by_type.items():
            summary_parts.append(f"\n{source_type} Sources:")
            for ev in items[:5]:  # Top 5 per type
                summary_parts.append(
                    f"- {ev.get('source_name')}: {ev.get('relevant_text')[:200]}"
                )
        return "\n".join(summary_parts)

    def _clean_json_response(self, text: str) -> str:
        """Remove markdown and extract JSON"""
        import re
        text = re.sub(r'```\s*', '', text)
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            return text[start:end]
        return text

    def _fallback_analysis(self, claim: Dict, evidence: List[Dict], 
                          supporting: List, contradicting: List) -> Dict[str, Any]:
        """Simple rule-based analysis if LLM fails"""
        total = len(evidence)
        support_ratio = len(supporting) / total if total > 0 else 0
        contradict_ratio = len(contradicting) / total if total > 0 else 0
        if contradict_ratio > 0.3:
            verdict = "Contradicted"
            confidence = 70
        elif support_ratio > 0.5:
            verdict = "Verified"
            confidence = 60
        elif total < 3:
            verdict = "Unverifiable"
            confidence = 30
        else:
            verdict = "Partially True"
            confidence = 50
        return {
            "claim_id": claim.get("claim_id"),
            "overall_verdict": verdict,
            "verification_confidence": confidence,
            "specific_contradictions": self._check_known_contradictions(claim.get("company", ""), claim.get("claim_text", "")),
            "supportive_evidence": [e.get('source_name') for e in supporting[:3]],
            "key_issues": ["Automated fallback analysis - LLM unavailable"],
            "evidence_counts": {
                'supporting': len(supporting),
                'contradicting': len(contradicting),
                'neutral': len(evidence) - len(supporting) - len(contradicting)
            }
        }

    def _check_known_contradictions(self, company: str, claim_text: str) -> List[Dict[str, Any]]:
        if not company:
            return []
        try:
            return get_known_contradictions(company, claim_text) or []
        except Exception:
            return []

# === Enhanced Contradiction Analysis ===
try:
    from data.known_cases import get_known_contradictions
except ImportError:
    def _fallback_get_known_contradictions(company_name: str, claim_text: str) -> list:
        return []
    get_known_contradictions = _fallback_get_known_contradictions

import requests
import hashlib

def search_greenwashing_evidence(company_name: str) -> list:
    """
    Searches DuckDuckGo for greenwashing regulatory actions.
    Uses free DuckDuckGo API — no key required.
    Returns list of evidence dicts.
    """
    evidence = []
    queries = [
        f"{company_name} greenwashing ruling banned fined",
        f"{company_name} ASA ruling environmental claim",
        f"{company_name} FTC SEC climate misleading"
    ]
    for query in queries:
        try:
            url = f"https://api.duckduckgo.com/?q={requests.utils.quote(query)}&format=json&no_html=1&skip_disambig=1"
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                # Extract Abstract
                if data.get("AbstractText"):
                    evidence.append({
                        "text": data["AbstractText"],
                        "source": data.get("AbstractSource", "DuckDuckGo"),
                        "url": data.get("AbstractURL", ""),
                        "confidence": "MEDIUM",
                        "source_type": "web_search"
                    })
                # Extract RelatedTopics
                for topic in data.get("RelatedTopics", [])[:3]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        evidence.append({
                            "text": topic["Text"],
                            "source": "DuckDuckGo Related",
                            "url": topic.get("FirstURL", ""),
                            "confidence": "LOW",
                            "source_type": "web_search"
                        })
        except Exception:
            continue
    return evidence

def analyze_contradictions(claim_text: str, company_name: str, evidence_items: list) -> dict:
    """
    Enhanced contradiction analyzer combining:
    1. Known regulatory case database (HIGH confidence)
    2. Existing LLM-based analysis on evidence_items
    3. DuckDuckGo web search (MEDIUM confidence)
    """
    analyzer = ContradictionAnalyzer()
    merged = analyzer.analyze_contradictions(
        company=company_name,
        claim=claim_text,
        evidence=evidence_items or [],
        contradicting_evidence=[
            e for e in (evidence_items or [])
            if str(e.get("stance", e.get("relationship_to_claim", ""))).lower() == "contradicts"
        ],
    )

    web_evidence = search_greenwashing_evidence(company_name)
    contradiction_signals = [
        "banned", "misleading", "ruled", "fined", "penalised",
        "greenwashing", "deceptive", "false claim", "withdrawn",
    ]
    web_hits = []
    for ev in web_evidence:
        text = ev.get("text", "")
        if any(sig in text.lower() for sig in contradiction_signals):
            web_hits.append({
                "severity": "MEDIUM",
                "description": text,
                "source": ev.get("source", "DuckDuckGo"),
                "source_url": ev.get("url", ""),
                "year": None,
                "confidence": ev.get("confidence", "LOW"),
                "source_type": ev.get("source_type", "web_search"),
            })

    all_contradictions = analyzer._merge_contradictions(
        known=merged.get("contradiction_list", []),
        evidence_found=[],
        llm_found=web_hits,
    )
    controversy_count = len(all_contradictions)

    return {
        "contradictions": all_contradictions,
        "contradictions_found": controversy_count,
        "contradiction_list": all_contradictions,
        "most_severe": analyzer._most_severe(all_contradictions),
        "controversy_count": controversy_count,
        "assessment": "Clean" if controversy_count == 0 else f"{controversy_count} confirmed case(s)",
        "high_confidence_count": sum(
            1 for c in all_contradictions if str(c.get("confidence", "")).upper() == "HIGH"
        ),
        "db_matches": merged.get("db_matches", 0),
        "llm_matches": merged.get("llm_matches", 0),
        "sources_searched": ["known_regulatory_database", "evidence_scan", "web_search"],
    }
