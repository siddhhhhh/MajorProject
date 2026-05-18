import json
import asyncio
import os
import re
from typing import Dict, Any, List
from core.evidence_cache import evidence_cache
from config.agent_prompts import SOURCE_CREDIBILITY_PROMPT, SOURCE_CREDIBILITY_BATCH_PROMPT
from core.llm_call import call_llm

class CredibilityAnalyst:
    def __init__(self):
        self.name = "Source Credibility & Bias Analyst"
        self.max_llm_sources = int(os.getenv("ESG_CREDIBILITY_LLM_MAX_SOURCES", "6"))
        self.llm_timeout_seconds = float(os.getenv("ESG_CREDIBILITY_LLM_TIMEOUT_SECONDS", "8"))
        
        # Base credibility scores by source type
        self.base_scores = {
            "Academic": 1.0,
            "Government/Regulatory": 0.95,
            "NGO": 0.90,
            "Tier-1 Financial Media": 0.85,
            "General Media": 0.70,
            "ESG Platform": 0.75,
            "Web Source": 0.50,
            "Company-Controlled": 0.35,
            "Sponsored Content": 0.20
        }
    
    def analyze_sources(self, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze credibility and bias of all evidence sources
        Works with evidence from cache (already fetched by EvidenceRetriever)
        """

        print(f"\n{'='*60}")
        print(f"🔍 AGENT 4: {self.name}")
        print(f"{'='*60}")
        print(f"Analyzing {len(evidence)} sources...")
        print(f"📦 Using evidence from cache (zero additional API calls)")

        # Split into LLM-eligible (first N) and heuristic-only. The same
        # cap (`max_llm_sources`) the per-source path enforces.
        llm_eligible = evidence[: self.max_llm_sources]
        heuristic_only = evidence[self.max_llm_sources :]

        # Single batched LLM call for the eligible slice — empty results
        # if the call fails, in which case we fall through to per-source.
        batched_results = self._batch_llm_credibility(llm_eligible)

        source_analyses: List[Dict[str, Any]] = []
        credibility_scores: List[float] = []

        for i, ev in enumerate(llm_eligible):
            llm_result = batched_results.get(i)
            if llm_result is None:
                # Batch produced no entry for this index — fall back to
                # per-source LLM (which will also try heuristic on its own).
                analysis = self._analyze_single_source(ev, use_llm=True)
            else:
                analysis = self._format_source_analysis(
                    evidence=ev,
                    source_name=ev.get("source_name", "Unknown"),
                    source_type=ev.get("source_type", "Web Source"),
                    url=ev.get("url", ""),
                    llm_result=llm_result,
                )
            source_analyses.append(analysis)
            credibility_scores.append(analysis["final_credibility_score"])

        for ev in heuristic_only:
            analysis = self._analyze_single_source(ev, use_llm=False)
            source_analyses.append(analysis)
            credibility_scores.append(analysis["final_credibility_score"])

        if batched_results:
            print(f"   Batched LLM call: 1 request covered {len(batched_results)} sources")
        print(f"\n✅ Credibility analysis complete")
        
        # Calculate aggregate metrics
        avg_credibility = sum(credibility_scores) / len(credibility_scores) if credibility_scores else 0
        
        # Count by credibility tier
        high_credibility = sum(1 for s in credibility_scores if s >= 0.8)
        medium_credibility = sum(1 for s in credibility_scores if 0.5 <= s < 0.8)
        low_credibility = sum(1 for s in credibility_scores if s < 0.5)
        
        print(f"   Average credibility: {avg_credibility:.2f}")
        print(f"   High (≥0.8): {high_credibility} sources")
        print(f"   Medium (0.5-0.8): {medium_credibility} sources")
        print(f"   Low (<0.5): {low_credibility} sources")
        
        return {
            "source_credibility_analyses": source_analyses,
            "aggregate_metrics": {
                "average_credibility": avg_credibility,
                "high_credibility_count": high_credibility,
                "medium_credibility_count": medium_credibility,
                "low_credibility_count": low_credibility,
                "total_sources": len(evidence)
            },
            "overall_credibility": int(round(avg_credibility * 100)),
            "high_credibility_sources": [
                s.get("source_name")
                for s in source_analyses
                if s.get("final_credibility_score", 0) >= 0.8
            ][:10],
            "low_credibility_sources": [
                s.get("source_name")
                for s in source_analyses
                if s.get("final_credibility_score", 0) < 0.5
            ][:10],
            "unverifiable_sources": sum(1 for s in source_analyses if not (s.get("url") or "").strip() or s.get("url") == "#"),
            "credibility_warning": f"{low_credibility} of {len(evidence)} sources scored low credibility"
        }
    
    def _batch_llm_credibility(
        self, sources: List[Dict[str, Any]]
    ) -> Dict[int, Dict[str, Any]]:
        """One LLM call for up to `max_llm_sources` sources. Returns a
        dict keyed by *list index* (0-based) so the caller can pair each
        result with the original evidence dict. Empty dict on any failure
        — the caller falls back to per-source LLM/heuristic.
        """
        if not sources:
            return {}

        # Render each source as a compact indexed block. Content cap of
        # 1200 chars (down from 2000 per-source) so the batch fits well
        # under typical 8k-input ceilings on the free Gemini tier.
        per_source_content_cap = 1200
        blocks = []
        for i, ev in enumerate(sources, 1):
            content = (
                ev.get("full_text")
                or ev.get("relevant_text")
                or ev.get("snippet")
                or ev.get("title")
                or ""
            )
            blocks.append(
                f"[{i}] SOURCE: {ev.get('source_name', 'Unknown')}\n"
                f"    TYPE: {ev.get('source_type', 'Web Source')}\n"
                f"    URL: {ev.get('url', '')}\n"
                f"    CONTENT: {str(content)[:per_source_content_cap]}"
            )
        prompt = (
            "Evaluate the following sources. Return one entry per source, "
            "in order, with matching `index`.\n\n" + "\n\n".join(blocks)
        )

        try:
            response = asyncio.run(
                asyncio.wait_for(
                    call_llm(
                        "credibility_analysis",
                        prompt,
                        system=SOURCE_CREDIBILITY_BATCH_PROMPT,
                    ),
                    timeout=self.llm_timeout_seconds * 2,  # batch is heavier
                )
            )
        except Exception as e:
            print(f"      ⚠️ Batched credibility call failed: {e}")
            return {}

        if not response:
            return {}

        # Strip ``` fences then extract the outer JSON object.
        cleaned = re.sub(r"```\s*json?\s*", "", response)
        cleaned = re.sub(r"```\s*", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start == -1 or end <= start:
            print("      ⚠️ Batched credibility response had no JSON object")
            return {}

        try:
            payload = json.loads(cleaned[start:end])
        except json.JSONDecodeError as e:
            print(f"      ⚠️ Batched credibility JSON parse failed: {e}")
            return {}

        evaluations = payload.get("evaluations") or []
        out: Dict[int, Dict[str, Any]] = {}
        for entry in evaluations:
            if not isinstance(entry, dict):
                continue
            idx = entry.get("index")
            if not isinstance(idx, int) or idx < 1 or idx > len(sources):
                continue
            entry["analysis_method"] = "llm_batched"
            out[idx - 1] = entry  # back to 0-based for caller pairing
        return out

    def _analyze_single_source(self, evidence: Dict[str, Any], use_llm: bool = True) -> Dict[str, Any]:
        """Analyze a single source for credibility and bias using LLM"""
        
        source_type = evidence.get('source_type', 'Web Source')
        source_name = evidence.get('source_name', 'Unknown')
        url = evidence.get('url', '')
        content = (
            evidence.get("full_text")
            or evidence.get("relevant_text")
            or evidence.get("snippet")
            or evidence.get("title")
            or ""
        )

        if not use_llm:
            llm_result = self._heuristic_credibility_fallback(
                evidence=evidence,
                source_type=source_type,
                source_name=source_name,
                url=url,
                content=content,
            )
            return self._format_source_analysis(evidence, source_name, source_type, url, llm_result)
        
        prompt = f"SOURCE: {source_name}\nTYPE: {source_type}\nURL: {url}\nCONTENT: {content[:2000]}"
        
        try:
            response = asyncio.run(
                asyncio.wait_for(
                    call_llm("credibility_analysis", prompt, system=SOURCE_CREDIBILITY_PROMPT),
                    timeout=self.llm_timeout_seconds,
                )
            )
            if response:
                import re
                cleaned = re.sub(r'```\s*json?\s*', '', response)
                cleaned = re.sub(r'```\s*', '', cleaned)
                start = cleaned.find('{')
                end = cleaned.rfind('}') + 1
                if start != -1 and end > start:
                    llm_result = json.loads(cleaned[start:end])
                else:
                    llm_result = json.loads(cleaned)
            else:
                llm_result = {}
        except Exception as e:
            print(f"      ⚠️ LLM credibility analysis failed: {e}")
            llm_result = self._heuristic_credibility_fallback(
                evidence=evidence,
                source_type=source_type,
                source_name=source_name,
                url=url,
                content=content,
            )
        
        return self._format_source_analysis(evidence, source_name, source_type, url, llm_result)

    def _format_source_analysis(
        self,
        evidence: Dict[str, Any],
        source_name: str,
        source_type: str,
        url: str,
        llm_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        base_cred = llm_result.get("base_credibility", self.base_scores.get(source_type, 0.50))
        final_score = llm_result.get("final_credibility_score", base_cred)
        paid = llm_result.get("paid_content_detected", False)
        bias = llm_result.get("bias_direction", "Neutral")
        adjustments = llm_result.get("adjustments", [])

        return {
            "source_id": evidence.get('source_id'),
            "source_name": source_name,
            "source_type": source_type,
            "base_credibility": base_cred,
            "adjustments": adjustments,
            "final_credibility_score": round(final_score, 2),
            "paid_content_detected": paid,
            "bias_direction": bias,
            "url": url,
            "analysis_method": llm_result.get("analysis_method", "llm")
        }

    def _heuristic_credibility_fallback(
        self,
        evidence: Dict[str, Any],
        source_type: str,
        source_name: str,
        url: str,
        content: str,
    ) -> Dict[str, Any]:
        """Deterministic fallback when remote LLM providers are unavailable."""
        base_cred = float(self.base_scores.get(source_type, 0.50))
        final_score = base_cred
        adjustments: List[str] = []
        url_lower = str(url or "").lower()
        source_name_lower = str(source_name or "").lower()
        freshness_days = evidence.get("data_freshness_days")

        paid = self._detect_paid_content(content, source_name)
        if paid:
            final_score -= 0.25
            adjustments.append("paid/sponsored indicators: -0.25")

        if url_lower.startswith("https://"):
            final_score += 0.03
            adjustments.append("https url present: +0.03")
        elif not url_lower or url_lower == "#":
            final_score -= 0.08
            adjustments.append("missing source url: -0.08")

        if any(token in url_lower for token in [".gov", ".edu", "sec.gov", "europa.eu", "reuters.com", "bloomberg.com", "ft.com"]):
            final_score += 0.05
            adjustments.append("high-trust domain signal: +0.05")

        if any(token in url_lower or token in source_name_lower for token in ["blog", "wordpress", "medium.com", "substack"]):
            final_score -= 0.10
            adjustments.append("self-published/blog signal: -0.10")

        if isinstance(freshness_days, (int, float)):
            if freshness_days <= 30:
                final_score += 0.03
                adjustments.append("fresh source data: +0.03")
            elif freshness_days > 3650:
                final_score -= 0.03
                adjustments.append("very old source data: -0.03")

        bias = self._detect_bias(content, source_type)
        if source_type == "Company-Controlled":
            bias = "Pro-company"

        final_score = max(0.0, min(1.0, final_score))
        return {
            "base_credibility": round(base_cred, 2),
            "adjustments": adjustments,
            "final_credibility_score": round(final_score, 2),
            "paid_content_detected": paid,
            "bias_direction": bias,
            "analysis_method": "heuristic_fallback",
        }
    
    def _detect_paid_content(self, content: str, source_name: str) -> bool:
        """Detect if content is sponsored/paid"""
        indicators = [
            "sponsored", "advertorial", "paid promotion", "partner content",
            "in partnership with", "brought to you by"
        ]
        
        text = (content + " " + source_name).lower()
        return any(indicator in text for indicator in indicators)
    
    def _detect_bias(self, content: str, source_type: str) -> str:
        """Simple bias detection"""
        if not content:
            return "Neutral"
        
        content_lower = content.lower()
        
        # Pro-company indicators
        pro_indicators = ["revolutionary", "groundbreaking", "leader", "best", "innovative"]
        pro_count = sum(1 for ind in pro_indicators if ind in content_lower)
        
        # Critical indicators
        critical_indicators = ["violation", "accused", "greenwashing", "overstated", "failed"]
        critical_count = sum(1 for ind in critical_indicators if ind in content_lower)
        
        if pro_count > critical_count + 2:
            return "Pro-company"
        elif critical_count > pro_count + 2:
            return "Anti-company"
        else:
            return "Neutral"
