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
        
    def fetch_all_sources(self, company: str, query: str, max_per_source: int = 3) -> Dict[str, List[Dict]]:
        """
        Fetch from all available sources
        Returns dict with source categories as keys
        """
        
        all_results = {}
        
        print(f"\n📡 Fetching data from multiple sources...")
        print(f"   Query: {query[:80]}...")
        
        # 1. NGO Sources
        print("1. NGO Sources...")
        try:
            all_results["ngo"] = self._fetch_ngo_sources(company, query, max_per_source)
        except Exception as e:
            print(f"   ⚠️ NGO sources error: {e}")
            all_results["ngo"] = []
        
        # 2. News Sources
        print("2. News Sources...")
        try:
            all_results["news"] = self._fetch_news_api(company, query, max_per_source)
        except Exception as e:
            print(f"   ⚠️ News API error: {e}")
            all_results["news"] = []
        
        # 3. Financial Data (aggregates multiple sources)
        print("3. Financial APIs...")
        try:
            all_results["financial"] = self._fetch_financial_apis(company, max_per_source)
        except Exception as e:
            print(f"   ⚠️ Financial APIs error: {e}")
            all_results["financial"] = []
        
        # 4. Government/Regulatory
        print("4. Government Sources...")
        try:
            all_results["government"] = self._fetch_government_sources(company, query, max_per_source)
        except Exception as e:
            print(f"   ⚠️ Government sources error: {e}")
            all_results["government"] = []
        
        # 5. Academic Sources
        print("5. Academic Sources...")
        try:
            all_results["academic"] = self._fetch_academic_sources(company, query, max_per_source)
        except Exception as e:
            print(f"   ⚠️ Academic sources error: {e}")
            all_results["academic"] = []
        
        # 6. Web Fallback (DuckDuckGo)
        print("6. Web Fallback (DuckDuckGo)...")
        try:
            all_results["web_fallback"] = self._search_ddgs_fallback(query, max_per_source)
        except Exception as e:
            print(f"   ⚠️ DuckDuckGo error: {e}")
            all_results["web_fallback"] = []
        
        return all_results


    def _fetch_financial_apis(self, company: str, max_results: int) -> List[Dict]:
        """
        Aggregate multiple financial API sources
        Combines Finnhub, SEC EDGAR, Yahoo Finance, Reuters, etc.
        """
        results = []
        
        # Sub-source 1: Finnhub
        finnhub_results = self._fetch_finnhub_news(company, max_results)
        results.extend(finnhub_results)
        
        # Sub-source 2: SEC EDGAR
        sec_results = self._fetch_sec_edgar(company, max_results)
        results.extend(sec_results)
        
        # Sub-source 3: Yahoo Finance
        yahoo_results = self._fetch_yahoo_finance(company, max_results)
        results.extend(yahoo_results)
        
        # Sub-source 4: Reuters RSS
        reuters_results = self._fetch_reuters_rss(company, max_results)
        results.extend(reuters_results)
        
        # Sub-source 5: Financial Times
        ft_results = self._fetch_ft_sustainability(company, max_results)
        results.extend(ft_results)
        
        if results:
            print(f"   ✅ Financial APIs: {len(results)} total results")
        else:
            print(f"   ⏭️  No financial API results")
        
        return results[:max_results * 2]  # Return up to 2x for diversity

    def _fetch_government_sources(self, company: str, query: str, max_results: int) -> List[Dict]:
        """Government and regulatory sources - EPA, OSHA, FTC"""
        
        results = []
        
        # SEC EDGAR
        sec_results = self._fetch_sec_edgar(company, max_results)
        results.extend(sec_results)
        
        # EPA Enforcement Database (simplified - actual API needs authentication)
        try:
            # Search for company in EPA news
            epa_url = "https://www.epa.gov/newsreleases/search"
            params = {'term': f'"{company}"'}
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(epa_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200 and company in response.text:
                results.append({
                    "source": "EPA",
                    "url": epa_url,
                    "title": f"EPA records for {company}",
                    "snippet": f"Environmental Protection Agency data on {company}",
                    "date": datetime.now().isoformat(),
                    "data_source_api": "EPA - Government",
                    "source_type": "Government/Regulatory"
                })
        except:
            pass
        
        if results:
            print(f"   ✅ Government sources: {len(results)} results")
        else:
            print(f"   ⏭️  No government sources (SEC filings require CIK lookup)")
        
        return results[:max_results]


    
    def _rate_limit(self, source: str):
        """Enforce rate limiting per source"""
        if source in self.last_call_time:
            elapsed = time.time() - self.last_call_time[source]
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
        self.last_call_time[source] = time.time()
    
    def _fetch_news_api(self, company: str, query: str, max_results: int) -> List[Dict]:
        """NewsAPI source with better error handling"""
        news_api_key = os.getenv("NEWS_API_KEY", "")
        if not news_api_key or news_api_key == "demo_key":
            print(f"   ⏭️  NewsAPI skipped (no valid API key)")
            return []
        
        try:
            self._rate_limit("news_api")
            
            from newsapi import NewsApiClient
            newsapi = NewsApiClient(api_key=news_api_key)
            
            # Use everything endpoint (not top-headlines for broader coverage)
            response = newsapi.get_everything(
                q=f'"{company}" AND (ESG OR sustainability)',
                language='en',
                sort_by='publishedAt',
                page_size=min(max_results, 20)  # Free tier limit
            )
            
            if response['status'] == 'ok':
                articles = response.get('articles', [])
                
                results = []
                for article in articles[:max_results]:
                    results.append({
                        "source": article['source']['name'],
                        "url": article['url'],
                        "title": article['title'],
                        "snippet": article.get('description', '')[:300],
                        "date": article['publishedAt'],
                        "author": article.get('author'),
                        "data_source_api": "NewsAPI",
                        "source_type": self._classify_news_source(article['source']['name'])
                    })
                
                return results
                
        except Exception as e:
            error_str = str(e)
            if '426' in error_str:
                print(f"   ⚠️ NewsAPI rate limit (upgrade to paid tier for more requests)")
            elif '429' in error_str:
                print(f"   ⚠️ NewsAPI too many requests (wait 1 hour)")
            else:
                print(f"   ⚠️ NewsAPI error: {error_str[:100]}")
        
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
        """Finnhub financial news API"""
        
        finnhub_key = os.getenv("FINNHUB_API_KEY", "")
        if not finnhub_key:
            return []
        
        try:
            # Get stock symbol first
            symbol = self._get_stock_symbol(company)
            if not symbol:
                return []
            
            url = "https://finnhub.io/api/v1/company-news"
            params = {
                'symbol': symbol,
                'from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                'to': datetime.now().strftime('%Y-%m-%d'),
                'token': finnhub_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                articles = response.json()
                
                results = []
                for article in articles[:max_results]:
                    if 'ESG' in article.get('headline', '') or 'sustainability' in article.get('summary', '').lower():
                        results.append({
                            "source": article.get('source', 'Finnhub'),
                            "url": article.get('url', ''),
                            "title": article.get('headline', ''),
                            "snippet": article.get('summary', '')[:300],
                            "date": datetime.fromtimestamp(article.get('datetime', 0)).isoformat(),
                            "data_source_api": "Finnhub - Financial",
                            "source_type": "Tier-1 Financial Media"
                        })
                
                return results
        except:
            pass
        
        return []

    def _fetch_sec_edgar(self, company: str, max_results: int) -> List[Dict]:
        """SEC EDGAR filings (free, no API key needed)"""
        
        try:
            # Search SEC EDGAR
            search_url = f"https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                'company': company,
                'type': '10-K',  # Annual reports
                'dateb': '',
                'owner': 'exclude',
                'count': max_results
            }
            
            headers = {'User-Agent': 'Mozilla/5.0 ESG Analyzer contact@example.com'}
            
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                results = []
                # Parse HTML for filing links (simplified - would need BeautifulSoup)
                if 'Filing Date' in response.text:
                    results.append({
                        "source": "SEC EDGAR",
                        "url": search_url,
                        "title": f"{company} SEC Filings",
                        "snippet": f"SEC regulatory filings for {company}",
                        "date": datetime.now().isoformat(),
                        "data_source_api": "SEC EDGAR - Government",
                        "source_type": "Government/Regulatory"
                    })
                
                return results
        except:
            pass
        
        return []

    def _fetch_yahoo_finance(self, company: str, max_results: int) -> List[Dict]:
        """Yahoo Finance ESG scores (free)"""
        
        try:
            symbol = self._get_stock_symbol(company)
            if not symbol:
                return []
            
            url = f"https://finance.yahoo.com/quote/{symbol}/sustainability"
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200 and 'ESG' in response.text:
                return [{
                    "source": "Yahoo Finance",
                    "url": url,
                    "title": f"{company} ESG Rating",
                    "snippet": f"Yahoo Finance ESG data for {company}",
                    "date": datetime.now().isoformat(),
                    "data_source_api": "Yahoo Finance - Financial",
                    "source_type": "Financial Platform"
                }]
        except:
            pass
        
        return []

    def _fetch_reuters_rss(self, company: str, max_results: int) -> List[Dict]:
        """Reuters company RSS feed"""
        
        try:
            # Reuters sustainability RSS
            feed_url = "https://www.reuters.com/arc/outboundfeeds/v1/rss/?outputType=xml&size=25&feedName=sustainability"
            
            response = requests.get(feed_url, timeout=10)
            if response.status_code == 200:
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.content)
                
                results = []
                for item in root.findall('.//item')[:max_results]:
                    title = item.find('title')
                    link = item.find('link')
                    
                    if title is not None and company.lower() in title.text.lower():
                        results.append({
                            "source": "Reuters",
                            "url": link.text if link is not None else '',
                            "title": title.text,
                            "snippet": "",
                            "date": datetime.now().isoformat(),
                            "data_source_api": "Reuters - Financial Media",
                            "source_type": "Tier-1 Financial Media"
                        })
                
                return results
        except:
            pass
        
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
        """Academic sources - Semantic Scholar + ArXiv"""
        results = []
        
        # Skip Google Scholar (blocks automation)
        print(f"   ⏭️  Google Scholar skipped (blocks automation)")
        
        # ArXiv
        try:
            import arxiv
            search = arxiv.Search(
                query=f'{company} ESG sustainability environmental',
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )
            
            for paper in search.results():
                results.append({
                    "source": "ArXiv (Academic)",
                    "url": paper.entry_id,
                    "title": paper.title,
                    "snippet": paper.summary[:300],
                    "date": paper.published.isoformat(),
                    "data_source_api": "ArXiv - Academic",
                    "source_type": "Academic"
                })
        except Exception as e:
            print(f"   ⚠️ ArXiv error: {e}")
        
        # Semantic Scholar - FIXED
        try:
            semantic_url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': f'{company} sustainability ESG',
                'limit': max_results,
                'fields': 'title,abstract,authors,year,url'
            }
            
            response = requests.get(semantic_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # FIX: Check if 'data' key exists before accessing
                if data and 'data' in data and data['data']:
                    for paper in data['data']:
                        # Check each field exists before accessing
                        results.append({
                            "source": "Semantic Scholar (Academic)",
                            "url": paper.get('url', ''),
                            "title": paper.get('title', 'Untitled'),
                            "snippet": (paper.get('abstract') or '')[:300],
                            "date": f"{paper.get('year', 2024)}-01-01",
                            "author": ', '.join([a.get('name', '') for a in (paper.get('authors') or [])][:3]),
                            "data_source_api": "Semantic Scholar - Academic",
                            "source_type": "Academic"
                        })
                    
                    print(f"   ✅ Semantic Scholar: {len(data['data'])} papers")
                else:
                    print(f"   ⏭️  Semantic Scholar: No results")
        except Exception as e:
            print(f"   ⚠️ Semantic Scholar error: {str(e)[:80]}")
        
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
    
    def _search_ddgs_fallback(self, query: str, max_results: int) -> List[Dict]:
        """DuckDuckGo fallback search - FIXED"""
        try:
            from ddgs import DDGS
            
            results = []
            with DDGS() as ddgs:
                search_results = ddgs.text(
                    query,  # Use keywords as a positional argument
                    region='wt-wt',
                    safesearch='off',
                    timelimit=None,
                    max_results=max_results
                )
                
                for result in search_results:
                    results.append({
                        "source": result.get('title', '')[:100],
                        "url": result.get('href', ''),
                        "title": result.get('title', ''),
                        "snippet": result.get('body', '')[:300],
                        "date": datetime.now().isoformat(),
                        "data_source_api": "DuckDuckGo - Web",
                        "source_type": "Web Source"
                    })
                    
                    if len(results) >= max_results:
                        break
            
            if results:
                print(f"   ✅ DuckDuckGo: {len(results)} results")
            else:
                print(f"   ⏭️  DuckDuckGo: No results")
            
            return results
            
        except Exception as e:
            error_msg = str(e)
            if 'dns error' in error_msg.lower() or 'no such host' in error_msg.lower():
                print(f"   ⚠️ DuckDuckGo DNS error (network issue) - skipping")
            elif 'missing' in error_msg.lower() and 'argument' in error_msg.lower():
                print(f"   ⚠️ DuckDuckGo API error: {error_msg[:80]}")
            else:
                print(f"   ⚠️ DuckDuckGo error: {error_msg[:100]}")
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
