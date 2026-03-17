"""
ESG Report Discovery Service
Automatically discovers ESG reports for any company using web search
Designed for Phase 2 of enterprise-grade ESG analysis pipeline
"""

import re
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import json
from pathlib import Path
from core.evidence_cache import evidence_cache
import time


class ReportDiscoveryService:
    """
    Discover ESG/sustainability reports for any company
    Uses web search to find official reports and PDFs
    Includes caching to avoid repeated searches
    """
    
    # Common domains for official ESG reports (prioritized)
    TRUSTED_REPORT_DOMAINS = [
        "investor.relations",
        "ir.com",
        "investor.com",
        "esg.report",
        "sustainability.report",
        "csr-report",
        "s3.amazonaws.com",
        "assets.ctfassets.net",
        "cdn",
        ".pdf",
    ]
    
    # Search query templates
    SEARCH_QUERIES = [
        "{company} sustainability report pdf",
        "{company} ESG report pdf",
        "{company} annual report sustainability pdf",
        "{company} corporate responsibility report",
        "{company} environmental report pdf",
        "{company} CSR report pdf",
        "{company} BRSR report",  # For Indian companies
        "{company} climate report pdf",
        "{company} net zero commitment report",
    ]
    
    def __init__(self):
        self.name = "ESG Report Discovery Service"
        self.cache_key_prefix = "esg_report_discovery"
        self.web_fetcher = self._initialize_web_fetcher()
    
    def _initialize_web_fetcher(self):
        """Initialize web search fetcher"""
        try:
            from utils.web_search import RealTimeDataFetcher
            return RealTimeDataFetcher()
        except ImportError:
            print("⚠️ RealTimeDataFetcher not available, using basic DuckDuckGo")
            return None
    
    def discover_reports(self, company_name: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Discover ESG reports for a company
        
        Args:
            company_name: Company name to search for
            max_results: Maximum number of results to return
            
        Returns:
            List of discovered reports with structure:
            [{
                "year": 2024,
                "url": "https://...",
                "title": "...",
                "source": "...",
                "confidence": 0.85,
                "report_type": "ESG" | "Sustainability" | "Annual" | "Other"
            }]
        """
        
        print(f"\n{'='*70}")
        print(f"🔍 REPORT DISCOVERY SERVICE")
        print(f"{'='*70}")
        print(f"Company: {company_name}")
        
        # ============================================================
        # STEP 1: CHECK CACHE
        # ============================================================
        cache_key = f"{self.cache_key_prefix}_{company_name.lower().replace(' ', '_')}"
        cached_results = evidence_cache.get_evidence(company_name, cache_key)
        
        if cached_results and cached_results.get("discovered_reports"):
            print(f"✅ Using cached discovery results - ZERO API calls")
            print(f"   Found {len(cached_results['discovered_reports'])} cached reports")
            return cached_results["discovered_reports"]
        
        # ============================================================
        # STEP 2: CACHE MISS - Perform web search
        # ============================================================
        print(f"🌐 Searching for ESG reports (LIVE)...")
        
        all_results = []
        
        canonical_company = self._resolve_company_search_name(company_name)

        # Execute multiple search queries for comprehensive discovery
        for query_template in self.SEARCH_QUERIES:
            query = query_template.format(company=canonical_company)
            print(f"\n   📍 Query: {query}")
            
            try:
                # Use DuckDuckGo for real-time search
                results = self._search_duckduckgo(query, max_per_query=3)
                
                # Filter PDF results
                pdf_results = [
                    r for r in results
                    if self._is_likely_pdf(r.get("url", ""))
                    and not self._is_competitor_contaminated(company_name, r)
                ]
                
                if pdf_results:
                    print(f"      ✅ Found {len(pdf_results)} PDF results")
                    all_results.extend(pdf_results)
                else:
                    print(f"      ⚠️ No PDF results for this query")
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"      ⚠️ Search error: {e}")
                continue
        
        # ============================================================
        # STEP 3: PROCESS AND DEDUPLICATE RESULTS
        # ============================================================
        print(f"\n📊 Processing {len(all_results)} search results...")
        
        # Deduplicate by URL
        unique_results = self._deduplicate_results(all_results)
        print(f"   ✅ Deduplicated to {len(unique_results)} unique results")
        
        # Extract year metadata from each result
        reports_with_metadata = []
        for result in unique_results:
            processed = self._extract_report_metadata(result, company_name)
            
            if processed:
                reports_with_metadata.append(processed)
        
        # ============================================================
        # STEP 4: RANK BY CONFIDENCE AND YEAR
        # ============================================================
        # Sort by year (newest first), then by confidence
        # Safe None handling: use (x.get("year") or 0) to avoid negating None
        ranked_reports = sorted(
            reports_with_metadata,
            key=lambda x: (
                -(x.get("year") or 0),
                -(x.get("confidence") or 0)
            )
        )
        
        # Return top N results
        final_results = ranked_reports[:max_results]
        
        print(f"\n📋 Final discovered reports:")
        for i, report in enumerate(final_results, 1):
            full_url = report.get('url', 'N/A')
            print(f"   {i}. {report.get('title', 'N/A')[:60]}")
            print(f"      Year: {report.get('year', 'Unknown')}, Confidence: {report.get('confidence', 0):.0%}")
            print(f"      URL length={len(full_url)}")
            print(f"      URL: {full_url}")
        
        # ============================================================
        # STEP 5: CACHE RESULTS
        # ============================================================
        cache_data = {
            "discovered_reports": final_results,
            "search_date": datetime.now().isoformat(),
            "company": company_name,
            "query_count": len(self.SEARCH_QUERIES)
        }
        
        evidence_cache.store_evidence(company_name, cache_data, cache_key)
        
        return final_results

    def _resolve_company_search_name(self, company_name: str) -> str:
        aliases_path = Path("config/company_aliases.json")
        if aliases_path.exists():
            try:
                with open(aliases_path, "r", encoding="utf-8") as f:
                    aliases = json.load(f)
                entry = aliases.get(company_name) or aliases.get(company_name.upper()) or aliases.get(company_name.title())
                if isinstance(entry, dict) and entry.get("full_name"):
                    return str(entry["full_name"])
            except Exception:
                pass
        return company_name

    def _is_competitor_contaminated(self, company_name: str, result: Dict[str, Any]) -> bool:
        text = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('url', '')}".lower()
        company_lower = company_name.lower()

        competitors = {
            "bp": ["bharat petroleum", "exxon", "chevron", "shell"],
            "shell": ["exxon", "chevron", "bp"],
            "exxon": ["shell", "bp", "chevron"],
            "chevron": ["shell", "bp", "exxon"],
        }

        if "bp" in company_lower:
            company_key = "bp"
        elif "shell" in company_lower:
            company_key = "shell"
        elif "exxon" in company_lower:
            company_key = "exxon"
        elif "chevron" in company_lower:
            company_key = "chevron"
        else:
            company_key = ""

        if not company_key:
            return False

        return any(name in text for name in competitors.get(company_key, []))
    
    def _search_duckduckgo(self, query: str, max_per_query: int = 5) -> List[Dict[str, Any]]:
        """Search using DuckDuckGo - no API key needed"""
        try:
            from ddgs import DDGS
            
            results = []
            with DDGS() as ddgs:
                for result in ddgs.text(query, max_results=max_per_query):
                    results.append({
                        "url": result.get("href", ""),
                        "title": result.get("title", ""),
                        "snippet": result.get("body", ""),
                        "source": "DuckDuckGo",
                        "search_date": datetime.now().isoformat()
                    })
            
            return results
            
        except ImportError:
            print("⚠️ ddgs library not installed. Run: pip install ddgs")
            return []
        except Exception as e:
            print(f"⚠️ DuckDuckGo search error: {e}")
            return []
    
    def _is_likely_pdf(self, url: str) -> bool:
        """
        Check if URL is likely to be a PDF
        Looks for .pdf extension or common PDF hosting patterns
        """
        url_lower = url.lower()
        
        # Direct PDF indicators
        if url_lower.endswith(".pdf"):
            return True
        
        # Common report patterns
        pdf_indicators = [
            "/download",
            "/pdf",
            "filetype:pdf",
            ".pdf?",
            "static/",
            "cdn-",
            "assets/",
            "investor",
            "esg-report",
            "sustainability-report",
        ]
        
        return any(indicator in url_lower for indicator in pdf_indicators)
    
    def _extract_report_metadata(self, result: Dict[str, Any], company_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract year and report type from search result
        Returns structured metadata or None if extraction fails
        """
        try:
            url = result.get("url", "")
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            
            # Extract year from title, URL, or snippet
            year = self._extract_year(title, url, snippet)
            
            # Determine report type
            report_type = self._determine_report_type(title, snippet)
            
            # Calculate confidence score
            confidence = self._calculate_confidence(url, title, snippet, company_name, year)
            
            return {
                "year": year,
                "url": url,
                "title": title,
                "snippet": snippet,
                "source": result.get("source", "Unknown"),
                "report_type": report_type,
                "confidence": confidence,
                "extracted_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"   ⚠️ Error extracting metadata: {e}")
            return None
    
    def _extract_year(self, title: str, url: str, snippet: str) -> Optional[int]:
        """
        Extract year from title, URL, or snippet
        Returns year as integer or None if not found
        """
        # Combine all text for searching
        combined_text = f"{title} {url} {snippet}".lower()
        
        # Look for 4-digit years between 2000 and 2030
        year_pattern = r'\b(20\d{2})\b'
        matches = re.findall(year_pattern, combined_text)
        
        if matches:
            # Get the most recent year found
            years = [int(y) for y in matches if 2000 <= int(y) <= 2030]
            if years:
                return max(years)  # Most recent year
        
        # Try other patterns like "FY2024", "2024-2025"
        fy_pattern = r'(?:fy|financial\s+year)?\s*(\d{4})'
        fy_matches = re.findall(fy_pattern, combined_text)
        if fy_matches:
            years = [int(y) for y in fy_matches if 2000 <= int(y) <= 2030]
            if years:
                return max(years)
        
        return None
    
    def _determine_report_type(self, title: str, snippet: str) -> str:
        """
        Determine type of report (ESG, Sustainability, Annual, etc.)
        """
        combined = f"{title} {snippet}".lower()
        
        if "esg" in combined or "environmental, social" in combined:
            return "ESG"
        elif "sustainability" in combined or "sustainable" in combined:
            return "Sustainability"
        elif "annual" in combined or "annual report" in combined:
            return "Annual"
        elif "csr" in combined or "corporate social responsibility" in combined:
            return "CSR"
        elif "brsr" in combined or "business responsibility" in combined:
            return "BRSR"
        elif "climate" in combined or "net zero" in combined:
            return "Climate"
        else:
            return "Unknown"
    
    def _calculate_confidence(self, url: str, title: str, snippet: str, 
                             company_name: str, year: Optional[int]) -> float:
        """
        Calculate confidence score (0.0 to 1.0) for a report result
        Higher confidence for official company sources and recent reports
        """
        confidence = 0.0
        
        # Domain trust score
        url_lower = url.lower()
        company_lower = company_name.lower().replace(" ", "")
        
        if company_lower in url_lower:
            confidence += 0.25  # Official company domain
        
        if any(domain in url_lower for domain in ["investor", "ir.", "esg.", "sustainability."]):
            confidence += 0.20  # Official report hosting
        
        # Title relevance
        title_lower = title.lower()
        if "sustainability" in title_lower or "esg" in title_lower:
            confidence += 0.20
        
        if "annual" in title_lower or "report" in title_lower:
            confidence += 0.10
        
        # Year recency
        if year and year >= 2023:
            confidence += 0.15
        elif year and year >= 2020:
            confidence += 0.05
        
        # Ensure clip to [0, 1]
        return min(confidence, 1.0)
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate URLs from results"""
        seen_urls = set()
        unique = []
        
        for result in results:
            url = result.get("url", "").lower()
            
            # Normalize URL for comparison
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(result)
        
        return unique


# Singleton instance
_discovery_service: Optional[ReportDiscoveryService] = None


def get_discovery_service() -> ReportDiscoveryService:
    """Get or create singleton instance"""
    global _discovery_service
    
    if _discovery_service is None:
        _discovery_service = ReportDiscoveryService()
    
    return _discovery_service


def discover_company_reports(company_name: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Convenience function to discover reports for a company
    
    Example:
        reports = discover_company_reports("Tesla", max_results=5)
        for report in reports:
            print(f"{report['year']}: {report['url']}")
    """
    service = get_discovery_service()
    return service.discover_reports(company_name, max_results)
