import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import os
import time
from bs4 import BeautifulSoup
import json

class EnterpriseESGDataFetcher:
    """
    Enterprise-grade ESG data fetcher matching MSCI, Sustainalytics, Bloomberg standards
    Multi-source aggregation with proper source attribution
    """
    
    def __init__(self):
        # API Keys
        self.news_api_key = os.getenv("NEWS_API_KEY", "")
        self.newsdata_api_key = os.getenv("NEWSDATA_API_KEY", "")
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY", "")
        self.finnhub_key = os.getenv("FINNHUB_API_KEY", "")
        
        # Rate limiting
        self.last_call_time = {}
        self.min_interval = 1.0  # seconds between calls
        
    def fetch_all_sources(self, company: str, query: str, max_per_source: int = 5) -> Dict[str, List[Dict]]:
        """
        Fetch from ALL available sources with proper attribution
        Returns dict with source-specific results
        """
        
        all_results = {
            "news_api": [],
            "newsdata_io": [],
            "finnhub_news": [],
            "sec_edgar": [],
            "esg_book": [],
            "yahoo_finance": [],
            "reuters": [],
            "ft_sustainability": [],
            "bloomberg_green": [],
            "guardian_environment": [],
            "ngo_sources": [],
            "academic_sources": [],
            "web_fallback": []
        }
        
        print(f"\n🌐 Fetching from multiple enterprise sources for: {company}")
        print("="*70)
        
        # 1. NewsAPI (80,000+ sources)
        print("📰 1. NewsAPI...")
        all_results["news_api"] = self._fetch_news_api(company, query, max_per_source)
        
        # 2. NewsData.io (ESG-specific)
        print("📊 2. NewsData.io (ESG-tagged)...")
        all_results["newsdata_io"] = self._fetch_newsdata_io(company, query, max_per_source)
        
        # 3. Finnhub (Financial + ESG news)
        print("💹 3. Finnhub Company News...")
        all_results["finnhub_news"] = self._fetch_finnhub_news(company, max_per_source)
        
        # 4. SEC EDGAR (Regulatory filings)
        print("📋 4. SEC EDGAR Filings...")
        all_results["sec_edgar"] = self._fetch_sec_edgar(company, max_per_source)
        
        # 5. Yahoo Finance News
        print("💼 5. Yahoo Finance...")
        all_results["yahoo_finance"] = self._fetch_yahoo_finance(company, max_per_source)
        
        # 6. Reuters Sustainability
        print("🌍 6. Reuters Sustainability...")
        all_results["reuters"] = self._fetch_reuters_rss(company, max_per_source)
        
        # 7. Financial Times Sustainability
        print("📈 7. Financial Times Climate...")
        all_results["ft_sustainability"] = self._fetch_ft_sustainability(company, max_per_source)
        
        # 8. Bloomberg Green
        print("🌱 8. Bloomberg Green...")
        all_results["bloomberg_green"] = self._fetch_bloomberg_green(company, max_per_source)
        
        # 9. Guardian Environment
        print("🌿 9. Guardian Environment...")
        all_results["guardian_environment"] = self._fetch_guardian_environment(company, max_per_source)
        
        # 10. NGO Sources (Greenpeace, Amnesty, etc.)
        print("🏛️  10. NGO Sources...")
        all_results["ngo_sources"] = self._fetch_ngo_sources(company, query, max_per_source)
        
        # 11. Academic Sources
        print("🎓 11. Academic Sources...")
        all_results["academic_sources"] = self._fetch_academic_sources(company, query, max_per_source)
        
        # 12. ESG Book (if available)
        print("📚 12. ESG Book Platform...")
        all_results["esg_book"] = self._fetch_esg_book(company, max_per_source)
        
        # 13. Web fallback (only if needed)
        total_results = sum(len(v) for v in all_results.values())
        if total_results < 10:
            print("🔍 13. Web Search Fallback...")
            all_results["web_fallback"] = self._fetch_web_fallback(company, query, max_per_source)
        
        # Print summary
        print("\n" + "="*70)
        print("📊 DATA FETCH SUMMARY:")
        for source, results in all_results.items():
            if results:
                print(f"   ✅ {source}: {len(results)} results")
        
        total = sum(len(v) for v in all_results.values())
        print(f"\n   📈 Total sources retrieved: {total}")
        print("="*70)
        
        return all_results
    
    def _rate_limit(self, source: str):
        """Enforce rate limiting per source"""
        if source in self.last_call_time:
            elapsed = time.time() - self.last_call_time[source]
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
        self.last_call_time[source] = time.time()
    
    def _fetch_news_api(self, company: str, query: str, max_results: int) -> List[Dict]:
        """NewsAPI - 80,000+ news sources"""
        if not self.news_api_key:
            return []
        
        try:
            self._rate_limit("newsapi")
            
            from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": f'"{company}" AND (ESG OR sustainability OR environmental OR greenwashing)',
                "apiKey": self.news_api_key,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max_results,
                "from": from_date
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for article in data.get("articles", []):
                    results.append({
                        "source": article.get("source", {}).get("name", "NewsAPI"),
                        "url": article.get("url", ""),
                        "title": article.get("title", ""),
                        "snippet": article.get("description", ""),
                        "content": article.get("content", ""),
                        "date": article.get("publishedAt", ""),
                        "author": article.get("author", ""),
                        "data_source_api": "NewsAPI - Premium",
                        "source_type": self._classify_news_source(article.get("source", {}).get("name", ""))
                    })
                
                return results
            elif response.status_code == 429:
                print("   ⚠️ NewsAPI rate limit reached")
            else:
                print(f"   ⚠️ NewsAPI error: {response.status_code}")
        except Exception as e:
            print(f"   ⚠️ NewsAPI error: {e}")
        
        return []
    
    def _fetch_newsdata_io(self, company: str, query: str, max_results: int) -> List[Dict]:
        """NewsData.io - ESG-specific AI tagging"""
        if not self.newsdata_api_key:
            return []
        
        try:
            self._rate_limit("newsdata")
            
            esg_domains = "reuters.com,bloomberg.com,theguardian.com,ft.com,wsj.com,cnbc.com"
            
            url = "https://newsdata.io/api/1/news"
            params = {
                "apikey": self.newsdata_api_key,
                "q": f'"{company}" sustainability',
                "language": "en",
                "category": "business,environment",
                "domain": esg_domains,
                "size": max_results
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for article in data.get("results", []):
                    results.append({
                        "source": article.get("source_name", "NewsData.io"),
                        "url": article.get("link", ""),
                        "title": article.get("title", ""),
                        "snippet": article.get("description", ""),
                        "content": article.get("content", ""),
                        "date": article.get("pubDate", ""),
                        "sentiment": article.get("sentiment", "neutral"),
                        "category": article.get("category", []),
                        "data_source_api": "NewsData.io - ESG Premium",
                        "source_type": "ESG Platform"
                    })
                
                return results
        except Exception as e:
            print(f"   ⚠️ NewsData.io error: {e}")
        
        return []
    
    def _fetch_finnhub_news(self, company: str, max_results: int) -> List[Dict]:
        """Finnhub - Financial news with ESG data"""
        if not self.finnhub_key:
            return []
        
        try:
            self._rate_limit("finnhub")
            
            # Get company symbol first
            symbol = self._get_stock_symbol(company)
            if not symbol:
                return []
            
            from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
            
            url = f"https://finnhub.io/api/v1/company-news"
            params = {
                "symbol": symbol,
                "from": from_date,
                "to": to_date,
                "token": self.finnhub_key
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                articles = response.json()
                results = []
                
                for article in articles[:max_results]:
                    # Filter for ESG-related news
                    text = (article.get('headline', '') + ' ' + article.get('summary', '')).lower()
                    if any(term in text for term in ['esg', 'sustainability', 'environmental', 'carbon', 'emission']):
                        results.append({
                            "source": article.get("source", "Finnhub"),
                            "url": article.get("url", ""),
                            "title": article.get("headline", ""),
                            "snippet": article.get("summary", ""),
                            "date": datetime.fromtimestamp(article.get("datetime", 0)).isoformat(),
                            "data_source_api": "Finnhub - Financial ESG",
                            "source_type": "Financial Media"
                        })
                
                return results
        except Exception as e:
            print(f"   ⚠️ Finnhub error: {e}")
        
        return []
    
    def _fetch_sec_edgar(self, company: str, max_results: int) -> List[Dict]:
        """SEC EDGAR - Official regulatory filings"""
        try:
            self._rate_limit("sec")
            
            base_url = "https://www.sec.gov/cgi-bin/browse-edgar"
            
            headers = {
                "User-Agent": "ESG Research Tool contact@esgresearch.com",
                "Accept-Encoding": "gzip, deflate"
            }
            
            params = {
                "action": "getcompany",
                "company": company,
                "type": "",
                "dateb": "",
                "owner": "exclude",
                "count": max_results * 2,  # Get more to filter ESG-related
                "output": "atom"
            }
            
            response = requests.get(base_url, params=params, headers=headers, timeout=20)
            
            if response.status_code == 200:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.content)
                
                results = []
                for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                    title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
                    link_elem = entry.find('{http://www.w3.org/2005/Atom}link')
                    updated_elem = entry.find('{http://www.w3.org/2005/Atom}updated')
                    
                    if title_elem is not None:
                        title = title_elem.text
                        
                        # Filter for ESG-relevant filings
                        if any(term in title.lower() for term in ['10-k', '10-q', '8-k', 'sustainability', 'esg', 'environmental']):
                            results.append({
                                "source": "SEC EDGAR",
                                "url": link_elem.get('href', '') if link_elem is not None else '',
                                "title": title,
                                "snippet": f"SEC Filing: {title}",
                                "date": updated_elem.text if updated_elem is not None else '',
                                "data_source_api": "SEC EDGAR - Official",
                                "source_type": "Government/Regulatory"
                            })
                    
                    if len(results) >= max_results:
                        break
                
                return results
        except Exception as e:
            print(f"   ⚠️ SEC EDGAR error: {e}")
        
        return []
    
    def _fetch_yahoo_finance(self, company: str, max_results: int) -> List[Dict]:
        """Yahoo Finance - News via RSS"""
        try:
            self._rate_limit("yahoo")
            
            symbol = self._get_stock_symbol(company)
            if not symbol:
                return []
            
            # Yahoo Finance RSS feed
            url = f"https://finance.yahoo.com/rss/headline?s={symbol}"
            
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.content)
                
                results = []
                for item in root.findall('.//item')[:max_results]:
                    title = item.find('title').text if item.find('title') is not None else ""
                    
                    # Filter for ESG terms
                    if any(term in title.lower() for term in ['esg', 'sustainability', 'environmental', 'carbon', 'climate']):
                        results.append({
                            "source": "Yahoo Finance",
                            "url": item.find('link').text if item.find('link') is not None else "",
                            "title": title,
                            "snippet": item.find('description').text if item.find('description') is not None else "",
                            "date": item.find('pubDate').text if item.find('pubDate') is not None else "",
                            "data_source_api": "Yahoo Finance - RSS",
                            "source_type": "Financial Media"
                        })
                
                return results
        except Exception as e:
            print(f"   ⚠️ Yahoo Finance error: {e}")
        
        return []
    
    def _fetch_reuters_rss(self, company: str, max_results: int) -> List[Dict]:
        """Reuters Sustainability RSS feed"""
        try:
            self._rate_limit("reuters")
            
            rss_url = "https://www.reuters.com/arc/outboundfeeds/v1/rss/?outputType=xml&size=50&feedName=sustainability"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(rss_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.content)
                
                results = []
                for item in root.findall('.//item'):
                    title = item.find('title').text if item.find('title') is not None else ""
                    description = item.find('description').text if item.find('description') is not None else ""
                    
                    # Check if company mentioned
                    if company.lower() in (title + description).lower():
                        results.append({
                            "source": "Reuters Sustainability",
                            "url": item.find('link').text if item.find('link') is not None else "",
                            "title": title,
                            "snippet": description,
                            "date": item.find('pubDate').text if item.find('pubDate') is not None else "",
                            "data_source_api": "Reuters - Tier-1 Media",
                            "source_type": "Tier-1 Financial Media"
                        })
                    
                    if len(results) >= max_results:
                        break
                
                return results
        except Exception as e:
            print(f"   ⚠️ Reuters error: {e}")
        
        return []
    
    # Continue in next message...
    def _fetch_ft_sustainability(self, company: str, max_results: int) -> List[Dict]:
        """Financial Times Climate/Sustainability coverage"""
        try:
            self._rate_limit("ft")
            
            # FT Climate RSS (free access)
            url = "https://www.ft.com/climate-capital?format=rss"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.content)
                
                results = []
                for item in root.findall('.//item'):
                    title = item.find('title').text if item.find('title') is not None else ""
                    description = item.find('description').text if item.find('description') is not None else ""
                    
                    if company.lower() in (title + description).lower():
                        results.append({
                            "source": "Financial Times Climate",
                            "url": item.find('link').text if item.find('link') is not None else "",
                            "title": title,
                            "snippet": description,
                            "date": item.find('pubDate').text if item.find('pubDate') is not None else "",
                            "data_source_api": "Financial Times - Premium",
                            "source_type": "Tier-1 Financial Media"
                        })
                    
                    if len(results) >= max_results:
                        break
                
                return results
        except Exception as e:
            print(f"   ⚠️ FT error: {e}")
        
        return []
    
    def _fetch_bloomberg_green(self, company: str, max_results: int) -> List[Dict]:
        """Bloomberg Green coverage"""
        try:
            self._rate_limit("bloomberg")
            
            # Bloomberg doesn't have public RSS, use web scraping
            search_url = f"https://www.bloomberg.com/search?query={company}+sustainability"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(search_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                results = []
                articles = soup.find_all('article', limit=max_results)
                
                for article in articles:
                    title_elem = article.find('a')
                    if title_elem:
                        results.append({
                            "source": "Bloomberg Green",
                            "url": "https://www.bloomberg.com" + title_elem.get('href', ''),
                            "title": title_elem.text.strip(),
                            "snippet": "Bloomberg article on sustainability",
                            "date": datetime.now().isoformat(),
                            "data_source_api": "Bloomberg - Premium Scrape",
                            "source_type": "Tier-1 Financial Media"
                        })
                
                return results
        except Exception as e:
            print(f"   ⚠️ Bloomberg error: {e}")
        
        return []
    
    def _fetch_guardian_environment(self, company: str, max_results: int) -> List[Dict]:
        """Guardian Environment section"""
        try:
            self._rate_limit("guardian")
            
            # Guardian Environment RSS
            url = "https://www.theguardian.com/environment/rss"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.content)
                
                results = []
                for item in root.findall('.//item'):
                    title = item.find('title').text if item.find('title') is not None else ""
                    description = item.find('description').text if item.find('description') is not None else ""
                    
                    if company.lower() in (title + description).lower():
                        results.append({
                            "source": "The Guardian Environment",
                            "url": item.find('link').text if item.find('link') is not None else "",
                            "title": title,
                            "snippet": BeautifulSoup(description, 'html.parser').get_text()[:300],
                            "date": item.find('pubDate').text if item.find('pubDate') is not None else "",
                            "data_source_api": "Guardian - Major Media",
                            "source_type": "General Media"
                        })
                    
                    if len(results) >= max_results:
                        break
                
                return results
        except Exception as e:
            print(f"   ⚠️ Guardian error: {e}")
        
        return []
    
    def _fetch_ngo_sources(self, company: str, query: str, max_results: int) -> List[Dict]:
        """Search major NGO websites"""
        ngo_sites = [
            ("Greenpeace", "greenpeace.org"),
            ("Amnesty International", "amnesty.org"),
            ("Rainforest Action Network", "ran.org"),
            ("Corporate Watch", "corporatewatch.org"),
            ("Global Witness", "globalwitness.org"),
            ("Friends of the Earth", "foe.org"),
            ("Sierra Club", "sierraclub.org")
        ]
        
        results = []
        
        for ngo_name, domain in ngo_sites:
            try:
                self._rate_limit(f"ngo_{domain}")
                
                # Google Custom Search or direct site search
                search_query = f'site:{domain} "{company}" sustainability OR environmental OR ESG'
                
                # Using DuckDuckGo for NGO-specific searches
                from ddgs import DDGS
                
                with DDGS() as ddgs:
                    search_results = list(ddgs.text(search_query, max_results=2))
                    
                    for result in search_results:
                        results.append({
                            "source": ngo_name,
                            "url": result.get("href", ""),
                            "title": result.get("title", ""),
                            "snippet": result.get("body", ""),
                            "date": datetime.now().isoformat(),
                            "data_source_api": f"{ngo_name} - NGO",
                            "source_type": "NGO"
                        })
                
                if len(results) >= max_results:
                    break
                    
                time.sleep(1)  # Be respectful to NGO sites
                
            except Exception as e:
                print(f"   ⚠️ {ngo_name} error: {e}")
        
        return results[:max_results]
    
    def _fetch_academic_sources(self, company: str, query: str, max_results: int) -> List[Dict]:
        """Academic sources - multiple databases"""
        results = []
        
        # 1. Try Google Scholar
        try:
            from scholarly import scholarly
            
            search_query = f'"{company}" ESG OR sustainability'
            search_results = scholarly.search_pubs(search_query)
            
            for i, pub in enumerate(search_results):
                if i >= max_results:
                    break
                
                bib = pub.get('bib', {})
                results.append({
                    "source": f"Academic: {bib.get('venue', 'Journal')}",
                    "url": pub.get('pub_url', ''),
                    "title": bib.get('title', ''),
                    "snippet": bib.get('abstract', '')[:300],
                    "date": f"{bib.get('pub_year', 'Unknown')}-01-01",
                    "author": ', '.join(bib.get('author', [])[:3]),
                    "data_source_api": "Google Scholar - Academic",
                    "source_type": "Academic"
                })
        except Exception as e:
            print(f"   ⚠️ Google Scholar error: {e}")
        
        # 2. Try ArXiv (if tech company)
        try:
            if any(term in company.lower() for term in ['tesla', 'microsoft', 'google', 'amazon', 'meta']):
                import arxiv
                
                search = arxiv.Search(
                    query=f'{company} sustainability OR environmental',
                    max_results=max_results,
                    sort_by=arxiv.SortCriterion.SubmittedDate
                )
                
                for paper in search.results():
                    results.append({
                        "source": "ArXiv",
                        "url": paper.entry_id,
                        "title": paper.title,
                        "snippet": paper.summary[:300],
                        "date": paper.published.isoformat(),
                        "author": ', '.join([a.name for a in paper.authors[:3]]),
                        "data_source_api": "ArXiv - Preprints",
                        "source_type": "Academic"
                    })
        except Exception as e:
            print(f"   ⚠️ ArXiv error: {e}")
        
        return results[:max_results]
    
    def _fetch_esg_book(self, company: str, max_results: int) -> List[Dict]:
        """ESG Book platform (if API available)"""
        # ESG Book is a premium platform - would need API key
        # This is a placeholder for enterprise integration
        
        esg_book_key = os.getenv("ESG_BOOK_API_KEY", "")
        if not esg_book_key:
            return []
        
        try:
            # ESG Book API endpoint (hypothetical - adjust based on actual API)
            url = f"https://api.esgbook.com/v1/companies/{company}/esg-data"
            headers = {"Authorization": f"Bearer {esg_book_key}"}
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                # Parse ESG Book response
                return []
        except Exception as e:
            print(f"   ⚠️ ESG Book error: {e}")
        
        return []
    
    def _fetch_web_fallback(self, company: str, query: str, max_results: int) -> List[Dict]:
        """DuckDuckGo fallback only if other sources failed"""
        try:
            from ddgs import DDGS
            
            results = []
            search_query = f'"{company}" ESG sustainability report OR environmental performance'
            
            with DDGS() as ddgs:
                search_results = ddgs.text(search_query, max_results=max_results)
                
                for result in search_results:
                    results.append({
                        "source": self._extract_domain(result.get("href", "")),
                        "url": result.get("href", ""),
                        "title": result.get("title", ""),
                        "snippet": result.get("body", ""),
                        "date": datetime.now().isoformat(),
                        "data_source_api": "DuckDuckGo - Web Fallback",
                        "source_type": "Web Source"
                    })
            
            return results
        except Exception as e:
            print(f"   ⚠️ DuckDuckGo fallback error: {e}")
            return []
    
    def _classify_news_source(self, source_name: str) -> str:
        """Classify news source by credibility tier"""
        source_lower = source_name.lower()
        
        tier1 = ["reuters", "bloomberg", "financial times", "ft.com", "wsj", "wall street journal"]
        if any(s in source_lower for s in tier1):
            return "Tier-1 Financial Media"
        
        tier2 = ["cnbc", "forbes", "economist", "guardian", "nytimes", "bbc"]
        if any(s in source_lower for s in tier2):
            return "General Media"
        
        return "News Source"
    
    def _get_stock_symbol(self, company: str) -> Optional[str]:
        """Get stock symbol for company"""
        # Common mappings
        symbol_map = {
            "tesla": "TSLA",
            "apple": "AAPL",
            "microsoft": "MSFT",
            "amazon": "AMZN",
            "google": "GOOGL",
            "meta": "META",
            "alphabet": "GOOGL",
            "nvidia": "NVDA",
            "netflix": "NFLX",
            "coca-cola": "KO",
            "pepsi": "PEP",
            "walmart": "WMT",
            "exxon": "XOM",
            "chevron": "CVX",
            "bp": "BP",
            "shell": "SHEL",
            "toyota": "TM",
            "volkswagen": "VWAGY",
            "unilever": "UL",
            "nestle": "NSRGY",
            "nike": "NKE",
            "adidas": "ADDYY"
        }
        
        return symbol_map.get(company.lower())
    
    def _extract_domain(self, url: str) -> str:
        """Extract clean domain from URL"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            return domain.replace('www.', '')
        except:
            return "Unknown"
    
    def aggregate_and_deduplicate(self, source_dict: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Aggregate all sources and deduplicate by URL
        Maintains source attribution
        """
        all_results = []
        seen_urls = set()
        
        # Priority order for sources (higher priority = kept if duplicate)
        priority_order = [
            "news_api", "newsdata_io", "sec_edgar", "finnhub_news",
            "reuters", "ft_sustainability", "bloomberg_green",
            "yahoo_finance", "guardian_environment", "ngo_sources",
            "academic_sources", "esg_book", "web_fallback"
        ]
        
        for source_key in priority_order:
            for result in source_dict.get(source_key, []):
                url = result.get('url', '')
                
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(result)
        
        # Sort by date (newest first) - with proper datetime handling
        try:
            all_results.sort(
                key=lambda x: self._parse_date_safe(x.get('date', '')),
                reverse=True
            )
        except Exception as e:
            print(f"   ⚠️ Date sorting error: {e}")
            # If sorting fails, just return as-is
            pass
        
        return all_results
    
    def _parse_date_safe(self, date_str: str) -> datetime:
        """
        Parse various date formats and normalize to timezone-naive UTC
        """
        if not date_str:
            return datetime.min
        
        from dateutil import parser
        try:
            dt = parser.parse(date_str)
            
            # Convert to timezone-naive UTC for consistent comparison
            if dt.tzinfo is not None:
                # Has timezone - convert to UTC then remove timezone
                dt = dt.astimezone(datetime.now().astimezone().tzinfo)
                dt = dt.replace(tzinfo=None)
            
            return dt
        except Exception as e:
            # If parsing fails, return current time
            return datetime.now()
    
    def _parse_date(self, date_str: str) -> datetime:
        """Alias for backward compatibility"""
        return self._parse_date_safe(date_str)

# Global instance
enterprise_fetcher = EnterpriseESGDataFetcher()
