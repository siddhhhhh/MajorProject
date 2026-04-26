"""
Social Pillar Agent
Focused retrieval and scoring for labor, workforce, and community evidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
import re

import requests

from utils.free_data_sources import search_duckduckgo
from core.sg_evidence import build_sg_evidence_pack


class SocialAgent:
    def __init__(self) -> None:
        self.name = "Social Pillar Forensic Agent"
        self.user_agent = "ESGLens/1.0 (research@esglens.local)"

    def analyze(
        self,
        company: str,
        claim_text: str,
        industry: str,
        evidence: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        claim_text = str(claim_text or "")
        evidence_text = self._collect_text(evidence)
        combined_text = f"{claim_text}\n{evidence_text}".lower()

        ilo = self._query_ilo_normlex(company)
        ungc = self._query_un_global_compact(company)
        slavery = self._check_modern_slavery_statements(company)
        supply_chain = self._check_supply_chain_risk(company, combined_text)
        workforce = self._check_workforce_diversity(combined_text)
        sentiment = self._check_employee_sentiment(company, combined_text)
        community = self._check_community_impact(combined_text)
        safety = self._check_health_and_safety(company, combined_text)

        score = 60.0
        findings: List[str] = []
        red_flags: List[str] = []

        if ungc.get("status") in {"non_communicating", "delisted"}:
            score -= 12
            red_flags.append("UN Global Compact status indicates possible social-governance weakness.")

        if ilo.get("possible_hits", 0) > 0:
            score -= 10
            findings.append("Potential ILO/NORMLEX labor signal identified and requires legal verification.")

        if slavery.get("vague_statement_detected"):
            score -= 8
            red_flags.append("Modern Slavery statement language appears generic without concrete audit actions.")

        if safety.get("citation_signals", 0) > 0:
            score -= 8
            findings.append("Health and safety citation signals detected in OSHA/HSE context.")

        if not supply_chain.get("labor_disclosures_present"):
            score = min(score, 35.0)
            red_flags.append("0 supply-chain labor disclosures detected: automatic Social HIGH RISK flag.")

        diversity_claim_detected = "divers" in combined_text or "inclusion" in combined_text
        if diversity_claim_detected and not workforce.get("pay_gap_disclosed"):
            score = min(score, 45.0)
            red_flags.append("Diversity claim without pay-gap disclosure: GREENWISHING indicator.")

        if sentiment.get("award_claim_detected") and not sentiment.get("award_verified"):
            score -= 6
            findings.append("Award-winning employer claim lacks third-party verification.")

        if workforce.get("women_leadership_pct") is not None and workforce["women_leadership_pct"] >= 30:
            score += 4
        if community.get("community_investment_pct_pre_tax_profit") is not None:
            score += 4
        if sentiment.get("rating") is not None and sentiment["rating"] >= 3.8:
            score += 3

        score = round(max(0.0, min(100.0, score)), 1)
        risk_level = self._risk_level(score)

        coverage_indicators = sum([
            1 if ungc.get("status") != "unknown" else 0,
            1 if slavery.get("statement_sources", 0) > 0 else 0,
            1 if supply_chain.get("labor_disclosures_present") else 0,
            1 if (workforce.get("women_leadership_pct") is not None or workforce.get("pay_gap_disclosed")) else 0,
            1 if sentiment.get("rating") is not None else 0,
            1 if (community.get("community_investment_pct_pre_tax_profit") is not None or community.get("local_procurement_pct") is not None) else 0,
            1 if safety.get("citation_signals", 0) > 0 else 0,
        ])

        if coverage_indicators < 3:
            score = None
            risk_level = "UNKNOWN"
            status = "insufficient_data"
            findings.insert(0, f"Insufficient data: only {coverage_indicators}/7 social themes detected. Pillar excluded from composite scoring.")
        else:
            status = "success"

        sources: List[Dict[str, Any]] = []
        sources.extend(ilo.get("sources", []))
        sources.extend(ungc.get("sources", []))
        sources.extend(slavery.get("sources", []))
        sources.extend(supply_chain.get("sources", []))
        sources.extend(sentiment.get("sources", []))
        sources.extend(safety.get("sources", []))

        confidence = 0.65 + min(0.25, len(sources) * 0.02)
        if status == "insufficient_data":
            confidence = 0.1
        social_lane = build_sg_evidence_pack(evidence=evidence, claim_text=claim_text).get("pillars", {}).get("social", {})

        return {
            "company": company,
            "industry": industry,
            "social_score": score,
            "status": status,
            "risk_level": risk_level,
            "confidence": round(min(0.9, confidence), 2),
            "signals": {
                "ilo_normlex": ilo,
                "un_global_compact": ungc,
                "modern_slavery": slavery,
                "supply_chain": supply_chain,
                "workforce_diversity": workforce,
                "employee_sentiment": sentiment,
                "community_impact": community,
                "health_safety": safety,
            },
            "rule_flags": {
                "supply_chain_disclosure_missing": not supply_chain.get("labor_disclosures_present"),
                "diversity_without_pay_gap": bool(diversity_claim_detected and not workforce.get("pay_gap_disclosed")),
                "award_claim_weak_evidence": bool(sentiment.get("award_claim_detected") and not sentiment.get("award_verified")),
            },
            "red_flags": red_flags,
            "key_findings": findings,
            "evidence_sources": sources[:15],
            "extraction_tracks": social_lane.get("tracks", []),
            "evidence_lane": social_lane,
            "timestamp": datetime.now().isoformat(),
        }

    def _collect_text(self, evidence: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for ev in evidence or []:
            if not isinstance(ev, dict):
                continue
            parts.append(str(ev.get("title", "")))
            parts.append(str(ev.get("snippet", "")))
            parts.append(str(ev.get("relevant_text", "")))
            parts.append(str(ev.get("source", "")))
            parts.append(str(ev.get("source_type", "")))
        return " ".join(parts)

    def _query_ilo_normlex(self, company: str) -> Dict[str, Any]:
        sources: List[Dict[str, Any]] = []
        possible_hits = 0

        normlex_url = "https://normlex.ilo.org"
        try:
            resp = requests.get(
                normlex_url,
                timeout=10,
                headers={"User-Agent": self.user_agent},
            )
            if resp.status_code == 200:
                sources.append(
                    {
                        "title": "ILO NORMLEX portal",
                        "url": normlex_url,
                        "source": "ILO NORMLEX",
                    }
                )
        except Exception:
            pass

        query = f'site:normlex.ilo.org "{company}" labor OR forced labor OR child labor'
        for item in search_duckduckgo(query, max_results=4):
            title = str(item.get("title", ""))
            snippet = str(item.get("snippet", ""))
            hay = f"{title} {snippet}".lower()
            if any(term in hay for term in ["forced labor", "child labor", "violation", "complaint"]):
                possible_hits += 1
            sources.append(
                {
                    "title": title,
                    "url": item.get("url", ""),
                    "source": "ILO NORMLEX search",
                }
            )

        return {
            "possible_hits": possible_hits,
            "sources": sources,
            "note": "Programmatic ILO company matching is limited; flagged hits should be manually verified.",
        }

    def _query_un_global_compact(self, company: str) -> Dict[str, Any]:
        sources: List[Dict[str, Any]] = []
        status = "unknown"

        search_url = f"https://www.unglobalcompact.org/what-is-gc/participants/search?query={company}"
        try:
            resp = requests.get(
                search_url,
                timeout=10,
                headers={"User-Agent": self.user_agent},
            )
            if resp.status_code == 200:
                body = resp.text.lower()
                if "non-communicating" in body:
                    status = "non_communicating"
                elif "delisted" in body:
                    status = "delisted"
                elif "active" in body or "participant" in body:
                    status = "active"
                sources.append(
                    {
                        "title": "UN Global Compact participant search",
                        "url": search_url,
                        "source": "UN Global Compact",
                    }
                )
        except Exception:
            pass

        if status == "unknown":
            for item in search_duckduckgo(f'site:unglobalcompact.org "{company}" participant'):
                text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
                if "non-communicating" in text:
                    status = "non_communicating"
                elif "delisted" in text:
                    status = "delisted"
                elif "participant" in text:
                    status = "active"
                sources.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "source": "UNGC web search",
                    }
                )

        return {"status": status, "sources": sources[:5]}

    def _check_modern_slavery_statements(self, company: str) -> Dict[str, Any]:
        sources: List[Dict[str, Any]] = []
        vague_hits = 0

        query = (
            f'"{company}" "modern slavery statement" UK OR Australia supplier audit'
        )
        results = search_duckduckgo(query, max_results=6)
        vague_patterns = [
            "we take this seriously",
            "committed to human rights",
            "zero tolerance",
        ]

        for item in results:
            snippet = str(item.get("snippet", "")).lower()
            if any(pattern in snippet for pattern in vague_patterns):
                vague_hits += 1
            sources.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": "Modern Slavery search",
                }
            )

        return {
            "statement_sources": len(results),
            "vague_statement_detected": vague_hits > 0,
            "sources": sources,
        }

    def _check_supply_chain_risk(self, company: str, combined_text: str) -> Dict[str, Any]:
        sources: List[Dict[str, Any]] = []
        benchmark_hits = 0

        keywords = ["knowthechain", "sedex", "fair labor association", "supplier audit"]
        labor_disclosures_present = any(term in combined_text for term in keywords)

        for keyword in ["KnowTheChain", "Sedex", "Fair Labor Association"]:
            query = f'"{company}" "{keyword}"'
            items = search_duckduckgo(query, max_results=2)
            if items:
                benchmark_hits += 1
            for item in items:
                sources.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "source": f"{keyword} search",
                    }
                )

        return {
            "labor_disclosures_present": labor_disclosures_present or benchmark_hits > 0,
            "benchmark_hits": benchmark_hits,
            "sources": sources,
        }

    def _check_workforce_diversity(self, combined_text: str) -> Dict[str, Any]:
        women_match = re.search(
            r"women[^\n\r]{0,60}?(?:leadership|management|board)[^\d]{0,20}(\d{1,3}(?:\.\d+)?)\s*%",
            combined_text,
        )
        pay_gap_match = re.search(r"pay gap[^\d]{0,20}(\d{1,2}(?:\.\d+)?)\s*%", combined_text)
        ethnic_match = re.search(r"ethnic(?:ity)?\s+diversity[^\d]{0,20}(\d{1,3}(?:\.\d+)?)\s*%", combined_text)

        women_pct = float(women_match.group(1)) if women_match else None
        pay_gap_pct = float(pay_gap_match.group(1)) if pay_gap_match else None

        return {
            "women_leadership_pct": women_pct,
            "pay_gap_disclosed": pay_gap_match is not None,
            "pay_gap_pct": pay_gap_pct,
            "ethnic_diversity_pct": float(ethnic_match.group(1)) if ethnic_match else None,
        }

    def _check_employee_sentiment(self, company: str, combined_text: str) -> Dict[str, Any]:
        sources: List[Dict[str, Any]] = []
        rating = None
        ratings = []

        for query in [f'"{company}" Glassdoor rating', f'"{company}" Indeed rating']:
            items = search_duckduckgo(query, max_results=3)
            for item in items:
                snippet = str(item.get("snippet", ""))
                sources.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "source": "Employee sentiment search",
                    }
                )
                for match in re.findall(r"([1-4](?:\.\d)?)\s*/\s*5", snippet):
                    try:
                        ratings.append(float(match))
                    except ValueError:
                        continue

        if ratings:
            rating = round(sum(ratings) / len(ratings), 2)

        award_claim_detected = "award-winning employer" in combined_text or "best employer" in combined_text
        award_verified = any(
            "forbes" in str(src.get("url", "")).lower() or "greatplacetowork" in str(src.get("url", "")).lower()
            for src in sources
        )

        return {
            "rating": rating,
            "award_claim_detected": award_claim_detected,
            "award_verified": award_verified,
            "sources": sources,
        }

    def _check_community_impact(self, combined_text: str) -> Dict[str, Any]:
        local_proc = re.search(r"local procurement[^\d]{0,30}(\d{1,3}(?:\.\d+)?)\s*%", combined_text)
        community_pct = re.search(
            r"community (?:investment|spend)[^\d]{0,35}(\d{1,2}(?:\.\d+)?)\s*%[^\n\r]{0,20}pre[- ]tax profit",
            combined_text,
        )

        return {
            "local_procurement_pct": float(local_proc.group(1)) if local_proc else None,
            "community_investment_pct_pre_tax_profit": float(community_pct.group(1)) if community_pct else None,
        }

    def _check_health_and_safety(self, company: str, combined_text: str) -> Dict[str, Any]:
        sources: List[Dict[str, Any]] = []
        citation_signals = 0

        query = f'"{company}" OSHA citation OR HSE notice OR workplace fatality'
        for item in search_duckduckgo(query, max_results=5):
            text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
            if any(token in text for token in ["citation", "notice", "fatality", "penalty"]):
                citation_signals += 1
            sources.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": "OSHA/HSE search",
                }
            )

        if any(token in combined_text for token in ["osha", "hse", "fatality", "ltifr"]):
            citation_signals += 1

        return {
            "citation_signals": citation_signals,
            "sources": sources,
        }

    def _risk_level(self, score: float) -> str:
        if score >= 70:
            return "LOW"
        if score >= 45:
            return "MODERATE"
        return "HIGH"
