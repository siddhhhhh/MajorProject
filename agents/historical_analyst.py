import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
from core.llm_client import llm_client
from utils.enterprise_data_sources import enterprise_fetcher
from config.agent_prompts import HISTORICAL_ANALYSIS_PROMPT

class HistoricalAnalyst:
    def __init__(self):
        self.name = "Historical ESG Pattern & Controversy Analyst"
        self.llm = llm_client
        self.fetcher = enterprise_fetcher
    
    def analyze_company_history(self, company: str) -> Dict[str, Any]:
        """
        Analyze company's historical ESG track record
        Search for violations, controversies, patterns
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 6: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        
        result = {
            "company": company,
            "analysis_date": datetime.now().isoformat(),
            "past_violations": [],
            "greenwashing_history": {},
            "positive_track_record": [],
            "temporal_patterns": {},
            "reputation_score": 50  # Default: neutral
        }
        
        # Search for violations and controversies
        print("\n🔍 Searching for ESG violations...")
        violations = self._search_violations(company)
        result["past_violations"] = violations
        
        print(f"📊 Found {len(violations)} documented violations")
        
        # Search for greenwashing accusations
        print("\n🔍 Searching greenwashing history...")
        greenwashing = self._search_greenwashing_history(company)
        result["greenwashing_history"] = greenwashing
        
        print(f"📊 Found {greenwashing.get('prior_accusations', 0)} prior accusations")
        
        # Search for positive achievements
        print("\n✅ Searching verified achievements...")
        achievements = self._search_achievements(company)
        result["positive_track_record"] = achievements
        
        print(f"📊 Found {len(achievements)} verified achievements")
        
        # Analyze temporal patterns
        print("\n📈 Analyzing temporal patterns...")
        patterns = self._analyze_patterns(violations, greenwashing, achievements)
        result["temporal_patterns"] = patterns
        
        # Calculate reputation score
        reputation = self._calculate_reputation_score(violations, greenwashing, achievements, patterns)
        result["reputation_score"] = reputation
        
        print(f"\n✅ Historical analysis complete:")
        print(f"   Violations: {len(violations)}")
        print(f"   Greenwashing accusations: {greenwashing.get('prior_accusations', 0)}")
        print(f"   Positive achievements: {len(achievements)}")
        print(f"   Reputation score: {reputation}/100")
        
        return result
    
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
