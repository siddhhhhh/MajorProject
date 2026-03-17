import json
import re
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging
from core.llm_client import llm_client
from utils.enterprise_data_sources import enterprise_fetcher
from config.agent_prompts import HISTORICAL_ANALYSIS_PROMPT
from core.evidence_cache import evidence_cache

try:
    from data.known_cases import get_known_contradictions
except Exception:
    def get_known_contradictions(company_name: str, claim_text: str) -> List[Dict[str, Any]]:
        return []

logger = logging.getLogger(__name__)

class HistoricalAnalyst:
    def __init__(self):
        self.name = "Historical ESG Pattern & Controversy Analyst"
        self.llm = llm_client
        self.fetcher = enterprise_fetcher
    
    def analyze_company_history(self, company: str) -> Dict[str, Any]:
        """
        Analyze company's historical ESG track record
        REUSES cached evidence to avoid redundant API calls
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 6: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        
        # ============================================================
        # STEP 1: TRY TO REUSE CACHED EVIDENCE
        # ============================================================
        cached_evidence = evidence_cache.get_evidence(company, "main_evidence")
        
        violations = []
        greenwashing = {}
        achievements = []
        
        if cached_evidence and cached_evidence.get("evidence"):
            print(f"📦 Reusing cached evidence for historical analysis - ZERO API calls")
            evidence_list = cached_evidence.get("evidence", [])
            
            # Extract violations, achievements from cached evidence
            violations = self._extract_violations_from_cache(evidence_list)
            achievements = self._extract_achievements_from_cache(evidence_list)
            greenwashing = self._extract_greenwashing_from_cache(evidence_list)
            
        else:
            # ============================================================
            # STEP 2: CACHE MISS - Fetch historical data
            # ============================================================
            print(f"⚠️ No cached evidence - fetching historical data...")
            
            # Search for violations and controversies
            print("\n🔍 Searching for ESG violations...")
            violations = self._search_violations(company)
            
            print(f"📊 Found {len(violations)} documented violations")
            
            # Search for greenwashing accusations
            print("\n🔍 Searching greenwashing history...")
            greenwashing = self._search_greenwashing_history(company)
            
            print(f"📊 Found {greenwashing.get('prior_accusations', 0)} prior accusations")
            
            # Search for positive achievements
            print("\n✅ Searching verified achievements...")
            achievements = self._search_achievements(company)
            
            print(f"📊 Found {len(achievements)} verified achievements")
        
        # ============================================================
        # STEP 3: ANALYZE PATTERNS (same regardless of cache)
        # ============================================================
        print("\n📈 Analyzing temporal patterns...")
        patterns = self._analyze_patterns(violations, greenwashing, achievements)

        if not violations:
            known = get_known_contradictions(company, "net zero sustainable climate") or []
            for case in known:
                violations.append({
                    "year": case.get("year"),
                    "type": "Known Contradiction",
                    "description": case.get("contradiction_text", "Known contradiction case"),
                    "source": case.get("source", "Known contradictions database"),
                    "url": case.get("source_url", ""),
                })
        
        # Calculate reputation score
        reputation = self._calculate_reputation_score(violations, greenwashing, achievements, patterns)

        trend_analysis = self._llm_trend_analysis(company, violations, achievements, patterns)
        claim_tone_trend = trend_analysis.get("claim_tone_trend") or "INSUFFICIENT_DATA"
        env_performance_trend = trend_analysis.get("env_performance_trend") or "INSUFFICIENT_DATA"

        years = [y for y in [v.get("year") for v in violations] if isinstance(y, int)]
        years_analyzed = len(set(years)) if years else 0
        year_range = f"{min(years)}-{max(years)}" if years else "N/A"
        
        result = {
            "company": company,
            "analysis_date": datetime.now().isoformat(),
            "past_violations": violations,
            "greenwashing_history": greenwashing,
            "positive_track_record": achievements,
            "temporal_patterns": patterns,
            "reputation_score": reputation,
            "claim_tone_trend": claim_tone_trend,
            "env_performance_trend": env_performance_trend,
            "violations": violations,
            "violations_count": len(violations),
            "years_analyzed": years_analyzed,
            "year_range": year_range,
            "confidence": 0.65 if years_analyzed > 0 else 0.5,
        }
        
        print(f"\n✅ Historical analysis complete:")
        print(f"   Reputation Score: {reputation}/100")
        print(f"   Violations: {len(violations)}")
        print(f"   Achievements: {len(achievements)}")
        
        return result

    def _llm_trend_analysis(
        self,
        company: str,
        violations: List[Dict[str, Any]],
        achievements: List[Dict[str, Any]],
        patterns: Dict[str, Any],
    ) -> Dict[str, Any]:
        """LLM-assisted trend summary with deterministic fallbacks."""
        prompt = HISTORICAL_ANALYSIS_PROMPT.format(
            company=company,
            violations=json.dumps(violations[:10], default=str),
            achievements=json.dumps(achievements[:10], default=str),
            patterns=json.dumps(patterns, default=str),
        )

        try:
            raw_response = self.llm.call_with_fallback(prompt, use_gemini_first=True)
            logger.debug("Historical LLM raw response: %s", raw_response)
        except Exception as exc:
            logger.warning("Historical LLM call failed: %s", exc)
            raw_response = None

        if not raw_response:
            return {
                "claim_tone_trend": "INSUFFICIENT_DATA",
                "env_performance_trend": "INSUFFICIENT_DATA",
            }

        try:
            cleaned = re.sub(r'```\s*json?\s*', '', raw_response)
            cleaned = re.sub(r'```\s*', '', cleaned)
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            payload = json.loads(cleaned[start:end]) if start != -1 and end > start else {}

            claim_tone_trend = (
                payload.get("claim_tone_trend")
                or payload.get("claim_trend")
                or payload.get("tone_trend")
                or "INSUFFICIENT_DATA"
            )
            env_performance_trend = (
                payload.get("env_performance_trend")
                or payload.get("environmental_trend")
                or payload.get("performance_trend")
                or "INSUFFICIENT_DATA"
            )

            return {
                "claim_tone_trend": claim_tone_trend,
                "env_performance_trend": env_performance_trend,
            }
        except Exception:
            return {
                "claim_tone_trend": "INSUFFICIENT_DATA",
                "env_performance_trend": "INSUFFICIENT_DATA",
            }
    
    def _extract_violations_from_cache(self, evidence_list: List[Dict]) -> List[Dict]:
        """Extract violations from cached evidence"""
        violations = []
        
        violation_keywords = ["fine", "penalty", "violation", "lawsuit", "settled", "sued", "enforcement"]
        
        for ev in evidence_list:
            text = (ev.get("relevant_text", "") + " " + ev.get("source_name", "")).lower()
            
            if any(kw in text for kw in violation_keywords):
                violations.append({
                    "year": self._extract_year(ev.get("date", "")),
                    "type": self._classify_violation(text),
                    "description": ev.get("relevant_text", "")[:200],
                    "source": ev.get("source_name", "Unknown"),
                    "url": ev.get("url", "")
                })
        
        return violations[:10]
    
    def _extract_achievements_from_cache(self, evidence_list: List[Dict]) -> List[Dict]:
        """Extract achievements from cached evidence"""
        achievements = []
        
        achievement_keywords = ["certified", "award", "recognized", "achieved", "verified", "compliance"]
        
        for ev in evidence_list:
            text = (ev.get("relevant_text", "") + " " + ev.get("source_name", "")).lower()
            
            if any(kw in text for kw in achievement_keywords):
                achievements.append({
                    "year": self._extract_year(ev.get("date", "")),
                    "achievement": ev.get("relevant_text", "")[:150],
                    "source": ev.get("source_name", ""),
                    "credibility": ev.get("source_type", "")
                })
        
        return achievements[:8]
    
    def _extract_greenwashing_from_cache(self, evidence_list: List[Dict]) -> Dict:
        """Extract greenwashing accusations from cached evidence"""
        accusations = []
        
        greenwashing_keywords = ["greenwashing", "misleading", "false claim", "exaggerated"]
        
        for ev in evidence_list:
            text = (ev.get("relevant_text", "") + " " + ev.get("source_name", "")).lower()
            
            if any(kw in text for kw in greenwashing_keywords):
                accusations.append({
                    "year": self._extract_year(ev.get("date", "")),
                    "description": ev.get("relevant_text", "")[:150],
                    "source": ev.get("source_name", "")
                })
        
        years = [acc["year"] for acc in accusations if acc["year"]]
        pattern_detected = len(set(years)) >= 2
        
        return {
            "prior_accusations": len(accusations),
            "examples": accusations[:5],
            "pattern_detected": pattern_detected
        }
    
    def _search_violations(self, company: str) -> List[Dict[str, Any]]:
        """Search for regulatory violations, fines, penalties"""
        
        violations = []
        
        # Search queries for violations
        queries = [
            f'"{company}" fine OR penalty OR lawsuit environmental',
            f'"{company}" EPA violation OR OSHA violation',
            f'"{company}" regulatory action ESG',
            f'"{company}" scandal OR controversy environmental social'
        ]
        
        for query in queries:
            source_dict = self.fetcher.fetch_all_sources(
                company=company,
                query=query,
                max_per_source=3
            )
            
            results = self.fetcher.aggregate_and_deduplicate(source_dict)
            
            for result in results[:5]:
                text = (result.get("title", "") + " " + result.get("snippet", "")).lower()
                
                # Check if it's actually a violation
                violation_indicators = ["fine", "penalty", "violation", "lawsuit", "settled", "sued"]
                if any(ind in text for ind in violation_indicators):
                    violations.append({
                        "year": self._extract_year(result.get("date", "")),
                        "type": self._classify_violation(text),
                        "description": result.get("snippet", "")[:200],
                        "source": result.get("source", "Unknown"),
                        "url": result.get("url", "")
                    })
        
        # Remove duplicates
        seen = set()
        unique_violations = []
        for v in violations:
            key = (v["year"], v["description"][:50])
            if key not in seen:
                seen.add(key)
                unique_violations.append(v)
        
        return unique_violations[:10]  # Top 10 most relevant
    
    def _search_greenwashing_history(self, company: str) -> Dict[str, Any]:
        """Search for past greenwashing accusations"""
        
        query = f'"{company}" greenwashing OR misleading OR false claims environmental'
        
        source_dict = self.fetcher.fetch_all_sources(
            company=company,
            query=query,
            max_per_source=5
        )
        
        results = self.fetcher.aggregate_and_deduplicate(source_dict)
        
        accusations = []
        for result in results[:10]:
            text = (result.get("title", "") + " " + result.get("snippet", "")).lower()
            
            if "greenwashing" in text or "misleading" in text or "false claim" in text:
                accusations.append({
                    "year": self._extract_year(result.get("date", "")),
                    "description": result.get("snippet", "")[:150],
                    "source": result.get("source", "")
                })
        
        # Detect pattern
        years = [acc["year"] for acc in accusations if acc["year"]]
        pattern_detected = len(set(years)) >= 2  # Multiple years = pattern
        
        return {
            "prior_accusations": len(accusations),
            "examples": accusations[:5],
            "pattern_detected": pattern_detected
        }
    
    def _search_achievements(self, company: str) -> List[Dict[str, Any]]:
        """Search for verified positive achievements"""
        
        query = f'"{company}" award OR certification ISO OR B-Corp verified achievement'
        
        source_dict = self.fetcher.fetch_all_sources(
            company=company,
            query=query,
            max_per_source=3
        )
        
        results = self.fetcher.aggregate_and_deduplicate(source_dict)
        
        achievements = []
        for result in results[:10]:
            text = (result.get("title", "") + " " + result.get("snippet", "")).lower()
            
            # Look for credible achievements
            achievement_indicators = ["certified", "award", "recognized", "achieved", "verified"]
            if any(ind in text for ind in achievement_indicators):
                # Check source credibility
                source_type = result.get("source_type", "")
                if source_type in ["Government/Regulatory", "Academic", "Tier-1 Financial Media"]:
                    achievements.append({
                        "year": self._extract_year(result.get("date", "")),
                        "achievement": result.get("snippet", "")[:150],
                        "source": result.get("source", ""),
                        "credibility": source_type
                    })
        
        return achievements[:8]
    
    def _analyze_patterns(self, violations: List, greenwashing: Dict, achievements: List) -> Dict[str, Any]:
        """Analyze temporal patterns in company behavior"""
        
        patterns = {
            "consistent_behavior": True,
            "improving_trend": False,
            "declining_trend": False,
            "reactive_claims": False
        }
        
        # Check for improvement
        violation_years = [v.get("year") for v in violations if v.get("year")]
        achievement_years = [a.get("year") for a in achievements if a.get("year")]
        
        if violation_years:
            recent_violations = [y for y in violation_years if y and y >= 2020]
            old_violations = [y for y in violation_years if y and y < 2020]
            
            if len(old_violations) > len(recent_violations):
                patterns["improving_trend"] = True
        
        # Check for declining trend
        if achievement_years:
            recent_achievements = [y for y in achievement_years if y and y >= 2020]
            if len(violations) > len(achievements) and len(recent_violations) > 0:
                patterns["declining_trend"] = True
        
        # Check for reactive claims (positive claims after negative news)
        if greenwashing.get("pattern_detected"):
            patterns["reactive_claims"] = True
        
        return patterns
    
    def _calculate_reputation_score(self, violations: List, greenwashing: Dict,
                                   achievements: List, patterns: Dict) -> int:
        """Calculate ESG reputation score (0-100)"""
        
        score = 50  # Start neutral
        
        # Penalties for violations
        score -= min(30, len(violations) * 5)
        
        # Penalties for greenwashing
        score -= min(20, greenwashing.get("prior_accusations", 0) * 10)
        
        # Bonus for achievements
        score += min(25, len(achievements) * 5)
        
        # Pattern adjustments
        if patterns.get("improving_trend"):
            score += 10
        if patterns.get("declining_trend"):
            score -= 15
        if patterns.get("reactive_claims"):
            score -= 10
        
        return max(0, min(100, score))
    
    def _extract_year(self, date_str: str) -> int:
        """Extract year from date string"""
        if not date_str:
            return None
        
        try:
            from dateutil import parser
            dt = parser.parse(date_str)
            return dt.year
        except:
            # Try to extract 4-digit year
            import re
            match = re.search(r'20\d{2}', date_str)
            if match:
                return int(match.group())
        
        return None
    
    def _classify_violation(self, text: str) -> str:
        """Classify type of violation"""
        if "environmental" in text or "epa" in text or "pollution" in text:
            return "Environmental"
        elif "labor" in text or "worker" in text or "osha" in text:
            return "Social/Labor"
        elif "governance" in text or "board" in text or "sec" in text:
            return "Governance"
        else:
            return "ESG-Related"
