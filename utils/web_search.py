import requests
from typing import List, Dict, Any, Optional
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import time
import json

class RealTimeDataFetcher:
    """
    Production-grade real-time data fetcher for ESG information
    Uses multiple live APIs and sources - NO hardcoded data
    """
    
    def __init__(self):
        self.news_api_key = os.getenv("NEWS_API_KEY", "")
        self.sec_api_key = os.getenv("SEC_API_KEY", "")
        self.newsdata_api_key = os.getenv("NEWSDATA_API_KEY", "")
        
    def search_all_sources(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Aggregate search from ALL live sources
        Returns deduplicated, timestamped results
        """
        all_results = []
        
        # 1. Real-time news via NewsAPI (last 30 days)
        news_results = self.search_news_api(query, max_results=5)
        all_results.extend(news_results)
        
        # 2. ESG-specific news via NewsData.io (with ESG tags)
        esg_news = self.search_newsdata_esg(query, max_results=5)
        all_results.extend(esg_news)
        
        # 3. DuckDuckGo real-time web search
        web_results = self.search_duckduckgo(query, max_results=5)
        all_results.extend(web_results)
        
        # 4. Reuters sustainability live feed
        reuters_results = self.search_reuters_sustainability(query, max_results=3)
        all_results.extend(reuters_results)
        
        # 5. Google Scholar for recent academic papers
        if "research" in query.lower() or "study" in query.lower():
            scholar_results = self.search_google_scholar(query, max_results=3)
            all_results.extend(scholar_results)
        
        # Deduplicate by URL and sort by date (newest first)
        unique_results = self._deduplicate_results(all_results)
        sorted_results = sorted(unique_results, 
                              key=lambda x: self._parse_date(x.get('date', '')), 
                              reverse=True)
        
        return sorted_results[:max_results]
    
    def search_news_api(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """NewsAPI - Real-time news from 80,000+ sources"""
        if not self.news_api_key:
            return []
        
        try:
            # Search last 30 days for relevance
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "apiKey": self.news_api_key,
                "language": "en",
                "sortBy": "publishedAt",  # Most recent first
                "pageSize": max_results,
                "from": from_date
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for article in data.get("articles", []):
                    results.append({
                        "source": article.get("source", {}).get("name", "NewsAPI"),
                        "url": article.get("url", ""),
                        "title": article.get("title", ""),
                        "snippet": article.get("description", ""),
                        "date": article.get("publishedAt", ""),
                        "content": article.get("content", ""),
                        "author": article.get("author", "Unknown"),
                        "data_source": "NewsAPI - Real-time"
                    })
                
                print(f"✅ NewsAPI: Found {len(results)} recent articles")
                return results
        except Exception as e:
            print(f"⚠️ NewsAPI error: {e}")
        
        return []
    
    def search_newsdata_esg(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        NewsData.io with ESG-specific AI tags
        Real-time + 7 years historical
        """
        if not self.newsdata_api_key:
            return []
        
        try:
            # ESG-specific AI tags
            esg_tags = "renewable_energy,climate_change,corporate_social_responsibility,pollution,work_life_balance"
            
            url = "https://newsdata.io/api/1/news"
            params = {
                "apikey": self.newsdata_api_key,
                "q": query,
                "language": "en",
                "ai_tag": esg_tags,
                "size": max_results
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for article in data.get("results", []):
                    results.append({
                        "source": article.get("source_name", "NewsData.io"),
                        "url": article.get("link", ""),
                        "title": article.get("title", ""),
                        "snippet": article.get("description", ""),
                        "date": article.get("pubDate", ""),
                        "content": article.get("content", ""),
                        "sentiment": article.get("sentiment", "neutral"),
                        "category": article.get("category", []),
                        "data_source": "NewsData.io - ESG Tagged"
                    })
                
                print(f"✅ NewsData.io: Found {len(results)} ESG-tagged articles")
                return results
        except Exception as e:
            print(f"⚠️ NewsData.io error: {e}")
        
        return []
    
    def search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """DuckDuckGo - No API key needed, real-time web search"""
        try:
            from ddgs import DDGS  # ✅ Updated from duckduckgo_search
            
            results = []
            with DDGS() as ddgs:
                search_results = ddgs.text(query, max_results=max_results)
                
                for result in search_results:
                    results.append({
                        "source": self._extract_domain(result.get("href", "")),
                        "url": result.get("href", ""),
                        "title": result.get("title", ""),
                        "snippet": result.get("body", ""),
                        "date": datetime.now().isoformat(),
                        "data_source": "DuckDuckGo - Real-time Web"
                    })
            
            print(f"✅ DuckDuckGo: Found {len(results)} web results")
            return results
        except ImportError:
            print("⚠️ ddgs not installed. Run: pip install ddgs")
            return []
        except Exception as e:
            print(f"⚠️ DuckDuckGo error: {e}")
            return []

    
    def search_reuters_sustainability(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Scrape Reuters Sustainability section - LIVE data"""
        try:
            # Reuters sustainability RSS feed
            rss_url = "https://www.reuters.com/arc/outboundfeeds/v1/rss/?outputType=xml&size=25&feedName=sustainability"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(rss_url, headers=headers, timeout=10)
            if response.status_code == 200:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.content)
                
                results = []
                for item in root.findall('.//item')[:max_results]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    
                    # Filter by query relevance
                    if query.lower() in title.lower():
                        results.append({
                            "source": "Reuters Sustainability",
                            "url": item.find('link').text if item.find('link') is not None else "",
                            "title": title,
                            "snippet": item.find('description').text if item.find('description') is not None else "",
                            "date": item.find('pubDate').text if item.find('pubDate') is not None else "",
                            "data_source": "Reuters - Live Feed"
                        })
                
                print(f"✅ Reuters: Found {len(results)} sustainability articles")
                return results
        except Exception as e:
            print(f"⚠️ Reuters scraping error: {e}")
        
        return []
    
    def search_google_scholar(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Google Scholar - Recent academic publications"""
        try:
            from scholarly import scholarly
            
            results = []
            search_query = scholarly.search_pubs(query)
            
            for i, pub in enumerate(search_query):
                if i >= max_results:
                    break
                
                bib = pub.get('bib', {})
                results.append({
                    "source": "Google Scholar",
                    "url": pub.get('pub_url', ''),
                    "title": bib.get('title', ''),
                    "snippet": bib.get('abstract', '')[:300],
                    "date": f"{bib.get('pub_year', 'Unknown')}-01-01",
                    "author": bib.get('author', 'Unknown'),
                    "data_source": "Google Scholar - Academic"
                })
            
            print(f"✅ Google Scholar: Found {len(results)} papers")
            return results
        except Exception as e:
            print(f"⚠️ Google Scholar error: {e}")
            return []
    
    def get_sec_filings_realtime(self, company_name: str, cik: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get LIVE SEC EDGAR filings - Real-time regulatory data
        """
        if not self.sec_api_key:
            return self._get_sec_filings_free(company_name, cik)
        
        try:
            # Using sec-api.io for real-time stream
            url = "https://api.sec-api.io"
            headers = {"Authorization": self.sec_api_key}
            
            query = {
                "query": f'companyName:"{company_name}" AND formType:"10-K" OR formType:"10-Q" OR formType:"8-K"',
                "from": "0",
                "size": "10",
                "sort": [{"filedAt": {"order": "desc"}}]
            }
            
            response = requests.post(f"{url}?token={self.sec_api_key}", 
                                   json=query, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                filings = data.get('filings', [])
                
                results = []
                for filing in filings:
                    results.append({
                        "source": "SEC EDGAR",
                        "url": filing.get('linkToFilingDetails', ''),
                        "title": f"{filing.get('companyName')} - {filing.get('formType')}",
                        "snippet": f"Filed: {filing.get('filedAt')} | Type: {filing.get('formType')}",
                        "date": filing.get('filedAt', ''),
                        "form_type": filing.get('formType', ''),
                        "data_source": "SEC EDGAR - Real-time"
                    })
                
                print(f"✅ SEC EDGAR: Found {len(results)} recent filings")
                return results
        except Exception as e:
            print(f"⚠️ SEC API error: {e}, trying free endpoint...")
            return self._get_sec_filings_free(company_name, cik)
        
        return []
    
    def _get_sec_filings_free(self, company_name: str, cik: Optional[str] = None) -> List[Dict[str, Any]]:
        """Free SEC EDGAR access - no API key needed"""
        try:
            # SEC's official free API
            base_url = "https://www.sec.gov/cgi-bin/browse-edgar"
            
            headers = {
                "User-Agent": "ESG Research Tool contact@example.com",
                "Accept-Encoding": "gzip, deflate"
            }
            
            params = {
                "action": "getcompany",
                "company": company_name,
                "type": "",
                "dateb": "",
                "owner": "exclude",
                "count": "10",
                "output": "atom"
            }
            
            if cik:
                params["CIK"] = cik
            
            response = requests.get(base_url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.content)
                
                results = []
                for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry')[:10]:
                    title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
                    link_elem = entry.find('{http://www.w3.org/2005/Atom}link')
                    updated_elem = entry.find('{http://www.w3.org/2005/Atom}updated')
                    
                    if title_elem is not None:
                        results.append({
                            "source": "SEC EDGAR (Free)",
                            "url": link_elem.get('href', '') if link_elem is not None else '',
                            "title": title_elem.text,
                            "snippet": title_elem.text,
                            "date": updated_elem.text if updated_elem is not None else '',
                            "data_source": "SEC EDGAR - Official Free API"
                        })
                
                print(f"✅ SEC EDGAR (Free): Found {len(results)} filings")
                return results
        except Exception as e:
            print(f"⚠️ SEC Free API error: {e}")
        
        return []
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate URLs"""
        seen_urls = set()
        unique = []
        
        for result in results:
            url = result.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(result)
        
        return unique
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse various date formats"""
        if not date_str:
            return datetime.min
        
        # Try common formats
        formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d',
            '%a, %d %b %Y %H:%M:%S %Z',
            '%a, %d %b %Y %H:%M:%S %z'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str[:25], fmt)
            except:
                continue
        
        return datetime.now()
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            return domain.replace('www.', '')
        except:
            return "Unknown"

def classify_source(url: str, source_name: str) -> str:
    """Classify source type with 2025 updates"""
    url_lower = url.lower()
    name_lower = source_name.lower()
    
    # Government/Regulatory
    gov_domains = [".gov", "sec.gov", "epa.gov", "europa.eu", "sebi.gov.in", 
                   "fca.org.uk", "asic.gov.au"]
    if any(domain in url_lower for domain in gov_domains):
        return "Government/Regulatory"
    
    # NGO - Updated 2025
    ngo_domains = ["greenpeace.org", "wwf.org", "amnesty.org", "ran.org", 
                   "corporatewatch.org", "globalwitness.org", "oxfam.org", 
                   "hrw.org", "earthjustice.org", "350.org", "climateaction.org"]
    if any(domain in url_lower for domain in ngo_domains):
        return "NGO"
    
    # Academic
    if any(domain in url_lower for domain in ["scholar.google", "researchgate", "arxiv.org", ".edu", "jstor", "nature.com"]):
        return "Academic"
    
    # Tier-1 Financial Media (highly credible)
    tier1_media = ["reuters.com", "bloomberg.com", "ft.com", "wsj.com", 
                   "economist.com", "financial-times.com"]
    if any(outlet in url_lower for outlet in tier1_media):
        return "Tier-1 Financial Media"
    
    # General Media
    media_outlets = ["guardian", "nytimes", "bbc", "cnn", "forbes", "theguardian",
                    "apnews", "npr.org", "aljazeera", "dw.com"]
    if any(outlet in name_lower or outlet in url_lower for outlet in media_outlets):
        return "General Media"
    
    # ESG-specific platforms
    esg_platforms = ["sustainability", "esg", "csrhub", "msci.com", "sustainalytics",
                    "cdp.net", "globalreporting.org", "sasb.org"]
    if any(platform in url_lower for platform in esg_platforms):
        return "ESG Platform"
    
    # Company sources
    if any(term in name_lower for term in ["press release", "investor relations", "corporate", "company announcement"]):
        return "Company-Controlled"
    
    # Sponsored
    if any(term in name_lower for term in ["sponsored", "advertorial", "paid", "partner content"]):
        return "Sponsored Content"
    
    return "Web Source"

# Global instance
data_fetcher = RealTimeDataFetcher()
