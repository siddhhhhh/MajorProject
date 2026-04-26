import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
import html
from bs4 import BeautifulSoup

from core.company_knowledge_graph import CompanyKnowledgeGraph
from core.archive_retriever import get_historical_snapshot
from core.llm_call import call_llm
from config.agent_prompts import CONTRADICTION_ANALYSIS_PROMPT
import asyncio
import requests

logger = logging.getLogger(__name__)


def clean_snippet_text(text: str) -> str:
    """Fix common encoding/scrape artifacts in snippet text."""
    if not text:
        return text

    # Decode HTML entities (&quot;, &amp;, etc.)
    text = html.unescape(str(text))
    # Strip HTML tags that leak from scraped snippets.
    text = BeautifulSoup(text, "html.parser").get_text(separator=" ")

    # Repair common mojibake sequences (e.g., "Â°C" -> "°C").
    try:
        text = text.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        pass

    # Fix camelCase splitting
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)

    # Fix spacing after punctuation
    text = re.sub(r"(?<=[,.;:])(?=[A-Za-z])", " ", text)

    # Fix common phrase spacing
    text = re.sub(r"(net)\s*-?\s*(zero)", r"\1-\2", text, flags=re.IGNORECASE)
    text = re.sub(r"(zero)\s*(by)", r"\1 \2", text, flags=re.IGNORECASE)
    text = re.sub(r"(climate)\s*(change)", r"\1 \2", text, flags=re.IGNORECASE)
    text = re.sub(r"(commitment)\s*(to)", r"\1 \2", text, flags=re.IGNORECASE)
    text = re.sub(r"(due)\s*(to)", r"\1 \2", text, flags=re.IGNORECASE)
    text = re.sub(r"(due)\s*(to)\s*(rising)", r"\1 \2 \3", text, flags=re.IGNORECASE)
    text = re.sub(r"(rising)\s*(emissions)", r"\1 \2", text, flags=re.IGNORECASE)
    text = re.sub(r"(across)\s*(its)", r"\1 \2", text, flags=re.IGNORECASE)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # If extraction starts mid-word, trim to the next likely sentence boundary.
    if text and re.match(r"^[a-z]\s", text):
        text = re.sub(r"^[a-z]\s+", "", text)

    return text

class ContradictionAnalyzer:
    def __init__(self):
        self.name = "Contradiction & Verification Analyst"
        try:
            total_cases = sum(len(v) for v in KNOWN_GREENWASHING_CASES.values())
            print(f"[ContradictionDB] Loaded {total_cases} known cases for {len(KNOWN_GREENWASHING_CASES)} companies")
        except Exception:
            pass

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
        try:
            graph_context = CompanyKnowledgeGraph().hybrid_retrieve(company=company, claim_text=claim)
        except Exception as exc:
            logger.error("Neo4j / Knowledge Graph unavailable (%s). Falling back to local offline DB.", exc)
            graph_context = {}

        graph_evidence = graph_context.get("graph_evidence", []) if isinstance(graph_context, dict) else []
        reasoning_paths = graph_context.get("reasoning_paths", []) if isinstance(graph_context, dict) else []
        historical_archive = self._retrieve_historical_claim_evidence(company=company, claim=claim, evidence=evidence)
        historical_evidence = historical_archive.get("evidence", []) if isinstance(historical_archive, dict) else []

        prioritized = list(contradicting_evidence or [])
        if not prioritized:
            prioritized = [
                e for e in (evidence or [])
                if str(e.get("stance", e.get("relationship_to_claim", ""))).lower() == "contradicts"
            ]
        prioritized.extend(historical_evidence)
        prioritized.extend(
            ev for ev in graph_evidence
            if str(ev.get("relationship_to_claim", "")).lower() == "contradicts"
        )

        evidence_contradictions = self._extract_contradictions_from_evidence(prioritized)

        # Combine standard and historical evidence for LLM scan to detect temporal violations
        combined_evidence = list(evidence or []) + historical_evidence
        
        try:
            llm_found = self._run_llm_contradiction_scan(claim=claim, evidence=combined_evidence, temperature=0)
        except Exception as exc:
            logger.warning("LLM contradiction scan failed: %s", exc)
            llm_found = []

        merged = self._merge_contradictions(known, evidence_contradictions, llm_found)
        for item in merged:
            if isinstance(item, dict) and reasoning_paths and not item.get("reasoning_path"):
                item["reasoning_path"] = reasoning_paths[0]

        text_signal_count = len(prioritized) + len(known) + len(llm_found)
        abstain = bool((graph_context or {}).get("abstain_recommended", False)) and len(merged) == 0 and text_signal_count == 0

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
            "graph_reasoning_paths": reasoning_paths,
            "graph_evidence_count": len(graph_evidence),
            "historical_archive_lookup": historical_archive,
            "abstain_recommended": abstain,
            "abstention_reason": "ABSTAIN: Insufficient verifiable evidence in Knowledge Graph" if abstain else None,
        }

    def _extract_target_claim_year(self, claim: str, evidence: List[Dict[str, Any]]) -> int:
        years = [int(y) for y in re.findall(r"\b(20[0-2]\d)\b", str(claim or ""))]
        if years:
            return min(years)

        for item in evidence or []:
            date_text = str(item.get("date") or item.get("publishedAt") or item.get("published_at") or "")
            match = re.search(r"\b(20[0-2]\d)\b", date_text)
            if match:
                return int(match.group(1))

        return max(2000, datetime.now().year - 2)

    def _candidate_archive_urls(self, company: str, evidence: List[Dict[str, Any]]) -> List[str]:
        urls: List[str] = []

        def _add(url: str):
            candidate = str(url or "").strip()
            if candidate and candidate not in urls and candidate.startswith("http"):
                urls.append(candidate)

        for item in evidence or []:
            url = item.get("url") if isinstance(item, dict) else ""
            source_type = str(item.get("source_type", "")) if isinstance(item, dict) else ""
            if "Company-Controlled" in source_type or company.lower() in str(url).lower():
                _add(str(url))

        slug = re.sub(r"[^a-z0-9]+", "", company.lower())
        if slug:
            _add(f"https://www.{slug}.com")
            _add(f"https://www.{slug}.com/sustainability")
            _add(f"https://www.{slug}.com/environment")

        known_urls = {
            "microsoft": [
                "https://www.microsoft.com/en-us/corporate-responsibility/sustainability",
                "https://blogs.microsoft.com/blog/tag/sustainability/",
            ],
            "apple": [
                "https://www.apple.com/environment/",
                "https://www.apple.com/newsroom/",
            ],
        }
        for key, candidates in known_urls.items():
            if key in company.lower():
                for url in candidates:
                    _add(url)

        return urls[:6]

    def _choose_archive_candidate(self, archive_result: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        if not isinstance(archive_result, dict):
            return None, None

        all_results = archive_result.get("all_results", {})
        if not isinstance(all_results, dict):
            return archive_result.get("snapshot_url"), archive_result.get("source")

        for source_name in ("memento", "archive_today", "wayback"):
            candidate = all_results.get(source_name)
            if candidate:
                return candidate, source_name

        return archive_result.get("snapshot_url"), archive_result.get("source")

    def _fetch_snapshot_text(self, snapshot_url: str) -> str:
        try:
            resp = requests.get(snapshot_url, timeout=15, headers={"User-Agent": "ESGLens historical retrieval"})
            resp.raise_for_status()
            text = re.sub(r"\s+", " ", resp.text)
            return text
        except Exception:
            return ""

    def _retrieve_historical_claim_evidence(self, company: str, claim: str, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        target_year = self._extract_target_claim_year(claim, evidence)
        urls = self._candidate_archive_urls(company, evidence)
        snapshots: List[Dict[str, Any]] = []
        historical_evidence: List[Dict[str, Any]] = []

        claim_keywords = [
            kw for kw in ["carbon", "net zero", "emission", "renewable", "climate", "pledge", "target"]
            if kw in str(claim or "").lower()
        ] or ["carbon", "net zero", "emission", "climate"]

        for url in urls:
            archive_result = get_historical_snapshot(url=url, target_year=target_year, strategy="all")
            snapshot_url, source_name = self._choose_archive_candidate(archive_result)
            snapshots.append({
                "url": url,
                "target_year": target_year,
                "snapshot_url": snapshot_url,
                "source": source_name,
                "all_results": archive_result.get("all_results", {}) if isinstance(archive_result, dict) else {},
            })
            if not snapshot_url:
                continue

            snapshot_text = self._fetch_snapshot_text(snapshot_url)
            if not snapshot_text:
                continue

            lower = snapshot_text.lower()
            if not any(keyword in lower for keyword in claim_keywords):
                continue

            snippet = ""
            for keyword in claim_keywords:
                idx = lower.find(keyword)
                if idx != -1:
                    start = max(0, idx - 180)
                    end = min(len(snapshot_text), idx + 320)
                    snippet = clean_snippet_text(snapshot_text[start:end])
                    break

            if snippet:
                historical_evidence.append({
                    "title": f"{company} historical archive snapshot ({target_year})",
                    "snippet": snippet,
                    "relevant_text": snippet,
                    "url": snapshot_url,
                    "source": source_name or "memento",
                    "source_name": f"{(source_name or 'archive').title()} snapshot",
                    "source_type": "Historical Archive",
                    "date": f"{target_year}-01-01",
                    "origin": "historical_archive",
                    "relationship_to_claim": "supports",
                })

        return {
            "claim_year": target_year,
            "candidate_urls": urls,
            "snapshots": snapshots,
            "evidence": historical_evidence,
            "snapshot_count": sum(1 for item in snapshots if item.get("snapshot_url")),
            "memento_available": any(item.get("source") == "memento" for item in snapshots),
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
        if merged.get("abstain_recommended"):
            merged["overall_verdict"] = "ABSTAIN"
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
        desc = clean_snippet_text(desc)
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
        from datetime import datetime as _dt
        current_year = _dt.now().year
        contradictions = []
        for item in evidence or []:
            description = (
                item.get("full_text")
                or item.get("relevant_text")
                or item.get("snippet")
                or item.get("title")
                or ""
            )
            if not description:
                continue
            cleaned = clean_snippet_text(description)[:300]
            # ── Quality gates: drop snippets that aren't presentation-grade ──
            # 1. Drop if cleaned text is too short to be a real signal
            if len(cleaned.strip()) < 40:
                continue
            # 2. Drop if first character is lowercase (likely truncated mid-word)
            first_char = cleaned.lstrip()[:1]
            if first_char and first_char.isalpha() and first_char.islower():
                continue
            # 3. Drop ancient Wayback / archive snippets — old archive content is
            #    almost never a decision-relevant contradiction for a current claim.
            url_lower = str(item.get("url") or "").lower()
            source_lower = str(item.get("source_name") or item.get("source") or "").lower()
            is_archive = (
                "web.archive.org" in url_lower
                or "wayback" in source_lower
                or "wayback" in url_lower
            )
            year = item.get("year")
            if is_archive:
                # Without a year, archives are unverifiable; with an old year, stale.
                if not isinstance(year, int) or year < (current_year - 5):
                    continue
            # 4. Drop generic non-archive items that are simply too old
            if isinstance(year, int) and year < (current_year - 8):
                continue
            contradictions.append({
                "severity": "MEDIUM",
                "description": cleaned,
                "source": item.get("source_name") or item.get("source") or "Evidence retrieval",
                "source_url": item.get("url", ""),
                "year": year,
                "confidence": "MEDIUM",
                "source_type": "retrieved_evidence",
            })
        return contradictions

    def _run_llm_contradiction_scan(
        self, claim: str, evidence: List[Dict[str, Any]], temperature: float = 0
    ) -> List[Dict[str, Any]]:
        evidence_summary = self._prepare_evidence_summary(evidence)
        
        temporal_violations = [
            e for e in evidence
            if e.get("origin") == "temporal_analysis"
        ]
        
        if temporal_violations:
            violations_text = "\n".join([
                f"[{e.get('type','Violation')} - "
                f"Year: {e.get('year','Unknown')} - "
                f"Source: {e.get('source','')}]: {e.get('text','')}"
                for e in temporal_violations
            ])
            evidence_summary = (
                evidence_summary
                + "\n\nADDITIONAL VERIFIED VIOLATIONS FROM REGULATORY DATABASES:\n"
                + violations_text
            )
            
        print("CONTRADICTION EVIDENCE SENT:", evidence_summary[:800])
        
        prompt = CONTRADICTION_ANALYSIS_PROMPT.format(
            claim=claim,
            evidence=evidence_summary,
            claim_id="C1",
        )
        try:
            response = asyncio.run(call_llm("contradiction_analysis", prompt))
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return []
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
            severity = str(c.get("severity", "LOW")).upper()
            description = clean_snippet_text(c.get("description") or c.get("contradiction_text") or c.get("aspect") or c.get("evidence_shows") or "Potential contradiction")
            source = c.get("source", "LLM evidence synthesis")

            if description in ("Potential contradiction", ""):
                continue
            if source == "LLM evidence synthesis" and severity not in ("HIGH", "MEDIUM"):
                continue

            normalized.append({
                "severity": severity,
                "description": description,
                "source": source,
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
                text = (
                    ev.get("full_text")
                    or ev.get("relevant_text")
                    or ev.get("snippet")
                    or ev.get("title")
                    or ""
                )
                summary_parts.append(
                    f"- {ev.get('source_name')}: {text[:200]}"
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
    from data.known_cases import get_known_contradictions, KNOWN_GREENWASHING_CASES
except ImportError:
    def _fallback_get_known_contradictions(company_name: str, claim_text: str) -> list:
        return []
    get_known_contradictions = _fallback_get_known_contradictions
    KNOWN_GREENWASHING_CASES = {}

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
