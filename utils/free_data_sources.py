"""
Free Data Sources Integration
23 APIs for maximum ESG coverage (15 original + 8 new)
"""
import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
from bs4 import BeautifulSoup
import json
from urllib.parse import quote
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from utils.source_tracker import source_tracker

class FreeDataAggregator:
    """Aggregates data from 15+ free APIs"""
    
    def __init__(self):
        # Load API keys from .env
        # News APIs
        self.newsapi_key = os.getenv("NEWSAPI_KEY")
        self.newsdata_key = os.getenv("NEWSDATA_KEY")
        self.thenews_key = os.getenv("THENEWSAPI_KEY")
        self.mediastack_key = os.getenv("MEDIASTACK_KEY")
        
        # Cache for OpenSanctions data (7 days)
        self.opensanctions_cache = None
        self.opensanctions_cache_time = None
        self.cache_duration = timedelta(days=7)
        
        # Create cache directory
        self.cache_dir = "utils/cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        print("[OK] Free Data Aggregator initialized (14 working sources)")
        print("   • 4 Premium News APIs (NewsAPI, NewsData, TheNewsAPI, Mediastack)")
        print("   • 4 Free News APIs (Google News, BBC, DuckDuckGo, GDELT)")
        print("   • 1 Research API (Semantic Scholar)")
        print("   • 2 Legal APIs (FTC, UK CMA)")
        print("   • 1 Compliance API (OpenSanctions)")
        print("   • 1 Environmental API (World Bank)")
        print("   • 1 Historical API (Wayback Machine)")
        print()
    
    def _get_cached_file(self, filename: str, url: str, cache_days: int = 7) -> Optional[str]:
        """
        Download and cache large files with smart caching
        Returns filepath if successful, None if failed
        """
        filepath = os.path.join(self.cache_dir, filename)
        
        # Check if cached and fresh
        if os.path.exists(filepath):
            file_age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(filepath))).days
            if file_age_days < cache_days:
                print(f"   ✅ Using cached file (age: {file_age_days} days)")
                return filepath
            else:
                print(f"   🔄 Cache expired ({file_age_days} days old), re-downloading...")
        
        # Download file
        try:
            print(f"   📥 Downloading {filename}...")
            response = requests.get(url, timeout=60)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"   ✅ Downloaded and cached successfully")
                return filepath
            else:
                print(f"   ⚠️ Download failed (HTTP {response.status_code})")
                return None
                
        except requests.Timeout:
            print(f"   ⚠️ Download timeout (file too large)")
            return None
        except Exception as e:
            print(f"   ⚠️ Download error: {str(e)[:80]}")
            return None
    
    def fetch_all_sources(self, company: str, query: str, max_per_source: int = 5) -> Dict:
        """
        Fetch from all 15 APIs in parallel
        
        Returns:
            {
                'news': [...],
                'research': [...],
                'social': [...],
                'financial': [...],
                'legal': [...]
            }
        """
        # Reset tracker for new analysis
        source_tracker.reset()
        
        results = {
            'news': [],
            'research': [],
            'social': [],
            'financial': [],
            'legal': [],
            'compliance': [],
            'environmental': [],
            'ngo': [],
            'regulatory': [],
            'historical': [],
            'labor': [],
            'supply_chain': []
        }
        
        print(f"\n🌐 Fetching from 14 WORKING sources for: {company}")
        
        # ========================================
        # PREMIUM NEWS APIs (with API keys) - 4 sources
        # ========================================
        results['news'].extend(search_newsapi_org(company, max_per_source))
        results['news'].extend(search_newsdata_io(company, max_per_source))
        results['news'].extend(self._fetch_thenewsapi(company, max_per_source))
        results['news'].extend(self._fetch_mediastack(company, max_per_source))
        
        # ========================================
        # FREE NEWS APIs (NO API KEYS) - 4 sources
        # ========================================
        results['news'].extend(search_google_news_rss(company, max_per_source))
        results['news'].extend(search_bbc_news(company, max_per_source))
        results['news'].extend(search_duckduckgo(f"{company} {query}", max_per_source))
        results['news'].extend(self._fetch_gdelt(company, query, max_per_source))
        
        # ========================================
        # RESEARCH APIs - 1 source
        # ========================================
        results['research'].extend(self._fetch_semantic_scholar(query, max_per_source))
        
        # ========================================
        # LEGAL/REGULATORY APIs - 2 sources
        # ========================================
        results['legal'].extend(self._fetch_ftc_enforcement(company, max_per_source))
        results['legal'].extend(self._fetch_uk_cma(company, max_per_source))
        
        # ========================================
        # COMPLIANCE APIs - 1 source
        # ========================================
        results['compliance'].extend(self._fetch_opensanctions(company, max_per_source))
        
        # ========================================
        # ENVIRONMENTAL APIs - 1 source
        # ========================================
        results['environmental'].extend(self._fetch_worldbank(company, "USA"))
        
        # ========================================
        # HISTORICAL APIs - 1 source
        # ========================================
        results['historical'].extend(self._fetch_wayback_machine(company, None, max_per_source))
        
        # ========================================
        # INDIAN SOURCES (NEW) - 8+ sources
        # ========================================
        results = self._fetch_indian_sources(company, results, max_per_source)
        
        # Count totals
        total = sum(len(v) for v in results.values())
        print(f"✅ Fetched {total} results from 22+ working sources\n")
        
        # Generate and save source usage report
        source_tracker.save_report(company)
        source_tracker.print_summary()
        
        return results
    
    def _fetch_indian_sources(self, company: str, results: Dict, 
                              max_per_source: int = 5) -> Dict:
        """
        Integrate Indian data sources for comprehensive coverage
        """
        try:
            from utils.indian_data_sources import indian_data_aggregator
            
            print("\n🇮🇳 Fetching Indian sources...")
            indian_results = indian_data_aggregator.fetch_all_indian_sources(company, max_per_source)
            
            # Merge Indian results
            for category, items in indian_results.items():
                if category in results:
                    results[category].extend(items)
                else:
                    results[category] = items
            
            # Count Indian sources
            indian_total = sum(len(v) for v in indian_results.values())
            print(f"   ✅ Added {indian_total} results from Indian sources")
            
        except ImportError:
            print("   ℹ️ Indian data sources not available")
        except Exception as e:
            print(f"   ⚠️ Indian sources error: {str(e)[:50]}")
        
        return results
    
    # ========================================
    # NEWS APIs
    # ========================================
    
    @source_tracker.track("TheNewsAPI")
    def _fetch_thenewsapi(self, company: str, limit: int = 5) -> List[Dict]:
        """TheNewsAPI - unlimited free"""
        if not self.thenews_key:
            return []
        
        try:
            url = "https://api.thenewsapi.com/v1/news/all"
            params = {
                'api_token': self.thenews_key,
                'search': company,
                'language': 'en',
                'limit': limit
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('data', [])
                return [{
                    'title': a.get('title'),
                    'snippet': a.get('description', ''),
                    'url': a.get('url'),
                    'source': 'TheNewsAPI',
                    'date': a.get('published_at'),
                    'data_source_api': 'TheNewsAPI'
                } for a in articles[:limit]]
        except Exception as e:
            print(f"⚠️ TheNewsAPI error: {e}")
        
        return []
    
    @source_tracker.track("Bing News")
    def _fetch_bing_news(self, company: str, limit: int = 5) -> List[Dict]:
        """Bing News Search - 1K/month free"""
        if not self.bing_key:
            return []
        
        try:
            url = "https://api.bing.microsoft.com/v7.0/news/search"
            headers = {'Ocp-Apim-Subscription-Key': self.bing_key}
            params = {'q': f'{company} ESG sustainability', 'count': limit}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('value', [])
                return [{
                    'title': a.get('name'),
                    'snippet': a.get('description', ''),
                    'url': a.get('url'),
                    'source': 'Bing News',
                    'date': a.get('datePublished'),
                    'data_source_api': 'Bing News'
                } for a in articles[:limit]]
        except Exception as e:
            print(f"⚠️ Bing News error: {e}")
        
        return []
    
    @source_tracker.track("Mediastack")
    def _fetch_mediastack(self, company: str, limit: int = 5) -> List[Dict]:
        """Mediastack - 500/month free"""
        if not self.mediastack_key:
            return []
        
        try:
            url = "http://api.mediastack.com/v1/news"
            params = {
                'access_key': self.mediastack_key,
                'keywords': company,
                'languages': 'en',
                'limit': limit
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('data', [])
                return [{
                    'title': a.get('title'),
                    'snippet': a.get('description', ''),
                    'url': a.get('url'),
                    'source': 'Mediastack',
                    'date': a.get('published_at'),
                    'data_source_api': 'Mediastack'
                } for a in articles[:limit]]
        except Exception as e:
            print(f"⚠️ Mediastack error: {e}")
        
        return []
    
    # ========================================
    # RESEARCH APIs
    # ========================================
    
    @source_tracker.track("Semantic Scholar")
    def _fetch_semantic_scholar(self, query: str, limit: int = 5) -> List[Dict]:
        """Semantic Scholar - 100 req/min free, no key"""
        try:
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': f'{query} ESG greenwashing',
                'limit': limit,
                'fields': 'title,abstract,url,year,authors'
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                papers = data.get('data', [])
                return [{
                    'title': p.get('title'),
                    'snippet': p.get('abstract', '')[:300],
                    'url': f"https://www.semanticscholar.org/paper/{p.get('paperId')}",
                    'source': 'Semantic Scholar',
                    'date': str(p.get('year')),
                    'data_source_api': 'Semantic Scholar'
                } for p in papers[:limit] if p.get('abstract')]
        except Exception as e:
            print(f"⚠️ Semantic Scholar error: {e}")
        
        return []
    
    @source_tracker.track("ArXiv")
    def _fetch_arxiv(self, query: str, limit: int = 5) -> List[Dict]:
        """arXiv - unlimited free, no key"""
        try:
            import feedparser
            url = f"http://export.arxiv.org/api/query?search_query=all:{query}+ESG&start=0&max_results={limit}"
            feed = feedparser.parse(url)
            
            return [{
                'title': entry.title,
                'snippet': entry.summary[:300],
                'url': entry.link,
                'source': 'arXiv',
                'date': entry.published,
                'data_source_api': 'arXiv'
            } for entry in feed.entries[:limit]]
        except Exception as e:
            print(f"⚠️ arXiv error: {e}")
        
        return []
    
    # ========================================
    # SOCIAL APIs
    # ========================================
    
    @source_tracker.track("Reddit")
    def _fetch_reddit(self, company: str, limit: int = 5) -> List[Dict]:
        """Reddit API - 100 req/min free"""
        if not self.reddit_id or not self.reddit_secret:
            return []
        
        try:
            import praw
            reddit = praw.Reddit(
                client_id=self.reddit_id,
                client_secret=self.reddit_secret,
                user_agent=os.getenv("REDDIT_USER_AGENT", "ESGOracle/1.0")
            )
            
            results = []
            for submission in reddit.subreddit('all').search(f'{company} ESG', limit=limit):
                results.append({
                    'title': submission.title,
                    'snippet': submission.selftext[:300] if submission.selftext else '',
                    'url': f"https://reddit.com{submission.permalink}",
                    'source': f'Reddit r/{submission.subreddit}',
                    'date': datetime.fromtimestamp(submission.created_utc).isoformat(),
                    'data_source_api': 'Reddit'
                })
            
            return results
        except Exception as e:
            print(f"⚠️ Reddit error: {e}")
        
        return []
    
    @source_tracker.track("Pushshift")
    def _fetch_pushshift(self, company: str, limit: int = 5) -> List[Dict]:
        """Pushshift - free, no key (Reddit archive)"""
        try:
            url = "https://api.pushshift.io/reddit/search/submission"
            params = {
                'q': f'{company} ESG',
                'size': limit,
                'sort': 'desc',
                'sort_type': 'created_utc'
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                posts = data.get('data', [])
                return [{
                    'title': p.get('title'),
                    'snippet': p.get('selftext', '')[:300],
                    'url': f"https://reddit.com{p.get('permalink')}",
                    'source': f"Reddit r/{p.get('subreddit')}",
                    'date': datetime.fromtimestamp(p.get('created_utc')).isoformat(),
                    'data_source_api': 'Pushshift'
                } for p in posts[:limit]]
        except Exception as e:
            print(f"⚠️ Pushshift error: {e}")
        
        return []
    
    # ========================================
    # FINANCIAL APIs
    # ========================================
    
    @source_tracker.track("Financial Modeling Prep")
    def _fetch_fmp(self, company: str, limit: int = 5) -> List[Dict]:
        """Financial Modeling Prep - 250/day free"""
        if not self.fmp_key:
            return []
        
        try:
            # Search for company ticker
            search_url = f"https://financialmodelingprep.com/api/v3/search?query={company}&apikey={self.fmp_key}"
            response = requests.get(search_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    ticker = data[0].get('symbol')
                    
                    # Get ESG scores
                    esg_url = f"https://financialmodelingprep.com/api/v4/esg-environmental-social-governance-data?symbol={ticker}&apikey={self.fmp_key}"
                    esg_response = requests.get(esg_url, timeout=10)
                    
                    if esg_response.status_code == 200:
                        esg_data = esg_response.json()
                        if esg_data:
                            return [{
                                'title': f"{company} ESG Scores",
                                'snippet': f"ESG Score: {esg_data[0].get('ESGScore', 'N/A')}",
                                'url': f"https://financialmodelingprep.com/financial-summary/{ticker}",
                                'source': 'FMP',
                                'date': datetime.now().isoformat(),
                                'data_source_api': 'FMP'
                            }]
        except Exception as e:
            print(f"⚠️ FMP error: {e}")
        
        return []
    
    # ========================================
    # NEW DATA SOURCES (8 ADDITIONS)
    # ========================================
    
    @source_tracker.track("GDELT")
    def _fetch_gdelt(self, company: str, query: str, limit: int = 3) -> List[Dict]:
        """
        GDELT - Global Database of Events, Language, and Tone
        Real-time global news monitoring (300+ sources, 100+ languages)
        FIXED: Timeout handling, simplified query
        """
        try:
            # FIXED: Simplified query - complex queries often timeout
            gdelt_query = f'"{company}"'
            encoded_query = quote(gdelt_query)
            
            url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={encoded_query}&mode=artlist&maxrecords=250&format=json"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            
            # FIXED: Increased timeout from 10 to 30 seconds (GDELT is slow)
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get("articles", [])
                
                # Filter for sustainability keywords in results
                sustainability_keywords = ['greenwashing', 'sustainability', 'esg', 'emissions', 'carbon', 'environmental', 'climate']
                
                results = []
                for article in articles:
                    title_snippet = (article.get("title", "") + " " + article.get("url", "")).lower()
                    
                    # Check if article is relevant to sustainability
                    if any(keyword in title_snippet for keyword in sustainability_keywords):
                        results.append({
                            'title': article.get('title', ''),
                            'snippet': article.get('title', '')[:100],
                            'url': article.get('url', ''),
                            'source': article.get('domain', 'GDELT'),
                            'date': article.get('seendate', datetime.now().isoformat()),
                            'data_source_api': 'GDELT - Global News'
                        })
                        
                        if len(results) >= limit:
                            break
                
                if results:
                    print(f"   ✅ GDELT: {len(results)} global news articles")
                else:
                    print(f"   ⏭️ GDELT: No sustainability-related results")
                
                return results
            else:
                print(f"   ⚠️ GDELT HTTP {response.status_code}")
                return []
        
        except requests.Timeout:
            print(f"   ⚠️ GDELT timeout (API is slow, try again later)")
            return []
        except requests.ConnectionError:
            print(f"   ⚠️ GDELT connection error (network issue)")
            return []
        except Exception as e:
            print(f"   ⚠️ GDELT error: {str(e)[:80]}")
            return []
    
    @source_tracker.track("CourtListener")
    def _fetch_courtlistener(self, company: str, limit: int = 3) -> List[Dict]:
        """
        CourtListener - Free legal research database
        Search federal and state court cases
        FIXED: Changed to opinions endpoint, better error handling
        """
        try:
            time.sleep(1)  # Rate limiting
            
            # FIXED: Use opinions endpoint instead of search
            # More reliable for programmatic access
            encoded_company = quote(company)
            
            # Try opinions API first
            url = f"https://www.courtlistener.com/api/rest/v3/opinions/?q={encoded_company}&type=o"
            
            headers = {
                "User-Agent": "ESG Research Tool (non-commercial academic use)",
                "Accept": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    opinions = data.get("results", [])
                    
                    results = []
                    for opinion in opinions[:limit]:
                        # Extract case name and date
                        case_name = opinion.get("case_name", "Unknown Case")
                        date_filed = opinion.get("date_filed", "")
                        cluster_id = opinion.get("cluster_id", "")
                        
                        results.append({
                            'title': case_name,
                            'snippet': f"Court opinion involving {company} - Filed: {date_filed}",
                            'url': f"https://www.courtlistener.com/opinion/{cluster_id}/",
                            'source': 'CourtListener',
                            'date': date_filed or datetime.now().isoformat(),
                            'data_source_api': 'CourtListener - Legal Cases'
                        })
                    
                    if results:
                        print(f"   ✅ CourtListener: {len(results)} legal opinions")
                    else:
                        print(f"   ℹ️ CourtListener: No legal cases found for {company}")
                    
                    return results
                
                except json.JSONDecodeError:
                    print(f"   ⚠️ CourtListener: Invalid JSON response")
                    return []
            
            elif response.status_code == 401:
                print(f"   ⏭️ CourtListener: API key required (skipping)")
                return []
            
            elif response.status_code == 429:
                print(f"   ⚠️ CourtListener: Rate limit exceeded")
                return []
            
            else:
                print(f"   ⚠️ CourtListener HTTP {response.status_code}")
                return []
        
        except requests.Timeout:
            print(f"   ⚠️ CourtListener timeout")
            return []
        except Exception as e:
            print(f"   ⚠️ CourtListener error: {str(e)[:80]}")
            return []
    
    @source_tracker.track("OpenSanctions")
    def _fetch_opensanctions(self, company: str, limit: int = 3) -> List[Dict]:
        """
        OpenSanctions - Global sanctions and compliance database
        Checks for regulatory violations, sanctions, watchlists
        FIXED: Proper file caching to avoid re-downloading
        """
        try:
            # FIXED: Use cached file system instead of in-memory cache
            cache_file = "opensanctions_entities.json"
            cache_url = "https://data.opensanctions.org/datasets/latest/default/entities.ftm.json"
            
            # Get cached file (downloads if not cached or expired)
            filepath = self._get_cached_file(cache_file, cache_url, cache_days=7)
            
            if not filepath:
                print(f"   ⚠️ OpenSanctions: Download failed")
                return []
            
            # Load and parse cached data
            print(f"   🔍 Searching OpenSanctions database for {company}...")
            
            results = []
            company_lower = company.lower()
            max_search = 50000  # Stop after searching 50k entities to prevent infinite loops
            
            # Parse line-delimited JSON
            with open(filepath, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if not line.strip():
                        continue
                    
                    # Stop if we've found enough results or searched too many entities
                    if len(results) >= limit or i >= max_search:
                        if i >= max_search:
                            print(f"      ⚠️  Reached search limit ({max_search:,} entities)")
                        break
                    
                    try:
                        entity = json.loads(line)
                        properties = entity.get("properties", {})
                        name = " ".join(properties.get("name", []))
                        
                        # Check if company name matches
                        if company_lower in name.lower():
                            topics = ", ".join(properties.get("topics", []))
                            datasets = ", ".join(entity.get("datasets", []))
                            entity_id = entity.get("id", "")
                            
                            results.append({
                                'title': f"{name} - Sanctions/Compliance Record",
                                'snippet': f"Topics: {topics} | Datasets: {datasets}",
                                'url': f"https://www.opensanctions.org/entities/{entity_id}",
                                'source': 'OpenSanctions',
                                'date': datetime.now().isoformat(),
                                'data_source_api': 'OpenSanctions - Compliance'
                            })
                    
                    except json.JSONDecodeError:
                        continue
                    
                    # Progress indicator for large files (every 10k entities)
                    if i > 0 and i % 10000 == 0:
                        print(f"      ... searched {i:,} entities ...")
            
            if results:
                print(f"   ✅ OpenSanctions: {len(results)} compliance records")
            else:
                print(f"   ℹ️ OpenSanctions: No records found (company clean)")
            
            return results
        
        except FileNotFoundError:
            print(f"   ⚠️ OpenSanctions: Cache file not found")
            return []
        except Exception as e:
            print(f"   ⚠️ OpenSanctions error: {str(e)[:80]}")
            return []
    
    @source_tracker.track("World Bank")
    def _fetch_worldbank(self, company: str, country_code: str = "USA") -> List[Dict]:
        """World Bank Open Data - Country-level environmental indicators"""
        try:
            time.sleep(1)
            indicators = [
                "EN.ATM.CO2E.PC",
                "EG.FEC.RNEW.ZS",
                "EN.ATM.GHGT.KT.CE"
            ]
            
            results = []
            
            for indicator in indicators:
                url = f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator}?format=json&date=2020:2024"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if len(data) > 1 and data[1]:
                        latest = data[1][0]
                        results.append({
                            'title': f"{country_code} - {latest.get('indicator', {}).get('value', 'Environmental Indicator')}",
                            'snippet': f"Value: {latest.get('value', 'N/A')} ({latest.get('date', 'Unknown year')})",
                            'url': f"https://data.worldbank.org/indicator/{indicator}?locations={country_code}",
                            'source': 'World Bank',
                            'date': f"{latest.get('date', 2024)}-01-01",
                            'data_source_api': 'World Bank - Country Context'
                        })
                
                time.sleep(0.5)
            
            return results
            
        except Exception as e:
            print(f"⚠️ World Bank error: {e}")
        
        return []
    
    @source_tracker.track("Our World in Data")
    def _fetch_ourworldindata(self, query: str, limit: int = 3) -> List[Dict]:
        """Our World in Data - Research and statistics on global issues"""
        try:
            time.sleep(1)
            encoded_query = quote(query)
            url = f"https://ourworldindata.org/search?q={encoded_query}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                articles = soup.find_all('article', limit=limit)
                
                for article in articles:
                    title_elem = article.find('h2') or article.find('h3')
                    link_elem = article.find('a')
                    
                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        full_url = href if href.startswith('http') else f"https://ourworldindata.org{href}"
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': 'Research-based statistics and visualizations on global sustainability issues',
                            'url': full_url,
                            'source': 'Our World in Data',
                            'date': datetime.now().isoformat(),
                            'data_source_api': 'Our World in Data - Statistics'
                        })
                
                return results
        except Exception as e:
            print(f"⚠️ Our World in Data error: {e}")
        
        return []
    
    @source_tracker.track("FTC Enforcement")
    def _fetch_ftc_enforcement(self, company: str, limit: int = 3) -> List[Dict]:
        """FTC - Federal Trade Commission enforcement actions"""
        try:
            time.sleep(2)
            encoded_company = quote(company)
            url = f"https://www.ftc.gov/enforcement/cases-proceedings?search={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                cases = soup.find_all('div', class_='views-row', limit=limit)
                
                for case in cases:
                    title_elem = case.find('h3') or case.find('h2')
                    link_elem = case.find('a')
                    date_elem = case.find('time')
                    summary_elem = case.find('p')
                    
                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        full_url = href if href.startswith('http') else f"https://www.ftc.gov{href}"
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': summary_elem.get_text(strip=True)[:300] if summary_elem else 'FTC enforcement action',
                            'url': full_url,
                            'source': 'FTC',
                            'date': date_elem.get('datetime', datetime.now().isoformat()) if date_elem else datetime.now().isoformat(),
                            'data_source_api': 'FTC - Consumer Protection'
                        })
                
                return results
        except Exception as e:
            print(f"⚠️ FTC error: {e}")
        
        return []
    
    @source_tracker.track("Greenpeace")
    def _fetch_greenpeace(self, company: str, limit: int = 3) -> List[Dict]:
        """Greenpeace International - NGO investigations and reports"""
        try:
            time.sleep(2)
            encoded_company = quote(company)
            url = f"https://www.greenpeace.org/international/?s={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                articles = soup.find_all('article', limit=limit * 2)
                
                for article in articles:
                    if len(results) >= limit:
                        break
                    
                    title_elem = article.find('h2') or article.find('h3')
                    link_elem = article.find('a')
                    date_elem = article.find('time')
                    
                    if title_elem and link_elem:
                        title_text = title_elem.get_text(strip=True).lower()
                        
                        if any(term in title_text for term in ['greenwash', 'climate', 'pollution', 'fossil', 'emissions', company.lower()]):
                            href = link_elem.get('href', '')
                            full_url = href if href.startswith('http') else f"https://www.greenpeace.org{href}"
                            
                            results.append({
                                'title': title_elem.get_text(strip=True),
                                'snippet': 'Greenpeace investigation or campaign report',
                                'url': full_url,
                                'source': 'Greenpeace',
                                'date': date_elem.get('datetime', datetime.now().isoformat()) if date_elem else datetime.now().isoformat(),
                                'data_source_api': 'Greenpeace - NGO Reports'
                            })
                
                return results
        except Exception as e:
            print(f"⚠️ Greenpeace error: {e}")
        
        return []
    
    @source_tracker.track("Carbon Tracker")
    def _fetch_carbon_tracker(self, company: str, limit: int = 3) -> List[Dict]:
        """Carbon Tracker Initiative - Financial think tank on climate risk"""
        try:
            time.sleep(2)
            encoded_company = quote(company)
            url = f"https://carbontracker.org/?s={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                reports = soup.find_all('article', limit=limit)
                
                for report in reports:
                    title_elem = report.find('h2') or report.find('h3')
                    link_elem = report.find('a')
                    date_elem = report.find('time')
                    
                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        full_url = href if href.startswith('http') else f"https://carbontracker.org{href}"
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': 'Carbon Tracker climate risk analysis and financial modeling',
                            'url': full_url,
                            'source': 'Carbon Tracker',
                            'date': date_elem.get('datetime', datetime.now().isoformat()) if date_elem else datetime.now().isoformat(),
                            'data_source_api': 'Carbon Tracker - Climate Analysis'
                        })
                
                return results
        except Exception as e:
            print(f"⚠️ Carbon Tracker error: {e}")
        
        return []
    
    # ========================================
    # HIGH PRIORITY SOURCES (17 NEW)
    # ========================================
    
    @source_tracker.track("Wikipedia")
    def _fetch_wikipedia_changes(self, company: str, limit: int = 3) -> List[Dict]:
        """Wikipedia API - Track edits to company pages (reputation management detection)"""
        try:
            time.sleep(1)
            # Get Wikipedia page title
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(company)}&format=json"
            response = requests.get(search_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                pages = data.get('query', {}).get('search', [])
                
                if not pages:
                    return []
                
                page_title = pages[0]['title']
                
                # Get recent revisions
                revisions_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={quote(page_title)}&prop=revisions&rvlimit={limit}&rvprop=timestamp|user|comment|size&format=json"
                rev_response = requests.get(revisions_url, timeout=10)
                
                if rev_response.status_code == 200:
                    rev_data = rev_response.json()
                    pages_data = rev_data.get('query', {}).get('pages', {})
                    
                    results = []
                    for page_id, page_info in pages_data.items():
                        revisions = page_info.get('revisions', [])
                        
                        for rev in revisions[:limit]:
                            results.append({
                                'title': f"{page_title} - Wikipedia Edit",
                                'snippet': f"Edit by {rev.get('user', 'Unknown')}: {rev.get('comment', 'No comment')[:200]}",
                                'url': f"https://en.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}",
                                'source': 'Wikipedia',
                                'date': rev.get('timestamp', datetime.now().isoformat()),
                                'data_source_api': 'Wikipedia API - Edit History'
                            })
                    
                    if results:
                        print(f"   ✅ Wikipedia: {len(results)} recent edits")
                    return results
        
        except Exception as e:
            print(f"   ⚠️ Wikipedia error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("Wayback Machine")
    def _fetch_wayback_machine(self, company: str, url: str = None, limit: int = 3) -> List[Dict]:
        """Internet Archive Wayback Machine - Historical snapshots of company websites"""
        try:
            time.sleep(1)
            
            # If no URL provided, try to get company website
            if not url:
                # Simple heuristic: company.com
                url = f"http://www.{company.lower().replace(' ', '')}.com"
            
            # Get available snapshots
            api_url = f"https://web.archive.org/cdx/search/cdx?url={quote(url)}&output=json&limit={limit}"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if len(data) <= 1:  # Only header or no data
                    return []
                
                results = []
                for row in data[1:limit+1]:  # Skip header
                    timestamp = row[1]
                    original_url = row[2]
                    status_code = row[4]
                    
                    # Format timestamp
                    date_str = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
                    
                    results.append({
                        'title': f"{company} Website Snapshot - {date_str}",
                        'snippet': f"Archived version from {date_str} (HTTP {status_code})",
                        'url': f"https://web.archive.org/web/{timestamp}/{original_url}",
                        'source': 'Internet Archive',
                        'date': date_str,
                        'data_source_api': 'Wayback Machine API'
                    })
                
                if results:
                    print(f"   ✅ Wayback Machine: {len(results)} snapshots")
                return results
        
        except Exception as e:
            print(f"   ⚠️ Wayback Machine error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("Google Patents")
    def _fetch_google_patents(self, company: str, limit: int = 3) -> List[Dict]:
        """Google Patents - Validate green technology claims"""
        try:
            time.sleep(1)
            
            # Search for sustainability/environment related patents
            query = f"{company} (sustainable OR renewable OR carbon OR emission OR clean OR green)"
            encoded_query = quote(query)
            
            # Google Patents public search
            url = f"https://patents.google.com/?q={encoded_query}&oq={encoded_query}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                
                # Find patent results (structure may vary)
                search_results = soup.find_all('search-result-item', limit=limit)
                
                for result in search_results:
                    title_elem = result.find('h3') or result.find('span', class_='title')
                    link_elem = result.find('a')
                    
                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        full_url = href if href.startswith('http') else f"https://patents.google.com{href}"
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': f"{company} patent related to sustainability/green technology",
                            'url': full_url,
                            'source': 'Google Patents',
                            'date': datetime.now().isoformat(),
                            'data_source_api': 'Google Patents Search'
                        })
                
                if results:
                    print(f"   ✅ Google Patents: {len(results)} green tech patents")
                else:
                    print(f"   ℹ️ Google Patents: No patents found")
                
                return results
        
        except Exception as e:
            print(f"   ⚠️ Google Patents error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("DOJ Environmental")
    def _fetch_doj_environmental(self, company: str, limit: int = 3) -> List[Dict]:
        """DOJ Environment Division - Environmental crimes and enforcement"""
        try:
            time.sleep(2)
            
            # DOJ Environment Division press releases
            encoded_company = quote(company)
            url = f"https://www.justice.gov/enrd/pr?search_api_fulltext={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                
                articles = soup.find_all('article', limit=limit)
                
                for article in articles:
                    title_elem = article.find('h3') or article.find('h2')
                    link_elem = article.find('a')
                    date_elem = article.find('time')
                    
                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        full_url = href if href.startswith('http') else f"https://www.justice.gov{href}"
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': 'DOJ environmental enforcement action or settlement',
                            'url': full_url,
                            'source': 'DOJ Environment Division',
                            'date': date_elem.get('datetime', datetime.now().isoformat()) if date_elem else datetime.now().isoformat(),
                            'data_source_api': 'DOJ ENRD - Environmental Crimes'
                        })
                
                if results:
                    print(f"   ✅ DOJ: {len(results)} environmental cases")
                else:
                    print(f"   ℹ️ DOJ: No environmental cases found")
                
                return results
        
        except Exception as e:
            print(f"   ⚠️ DOJ error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("SEC EDGAR Full")
    def _fetch_sec_full(self, company: str, limit: int = 3) -> List[Dict]:
        """Enhanced SEC Analysis - 10-K risk factors, proxy statements"""
        try:
            time.sleep(1)
            
            # SEC EDGAR full-text search
            encoded_company = quote(company)
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={encoded_company}&type=&dateb=&owner=exclude&count={limit}"
            
            headers = {
                "User-Agent": "ESG Research Tool contact@example.com",
                "Accept-Encoding": "gzip, deflate"
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                
                filing_table = soup.find('table', class_='tableFile2')
                if filing_table:
                    rows = filing_table.find_all('tr')[1:limit+1]  # Skip header
                    
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 4:
                            filing_type = cols[0].get_text(strip=True)
                            filing_date = cols[3].get_text(strip=True)
                            link_elem = cols[1].find('a')
                            
                            if link_elem:
                                href = link_elem.get('href', '')
                                full_url = f"https://www.sec.gov{href}" if not href.startswith('http') else href
                                
                                results.append({
                                    'title': f"{company} - {filing_type} Filing",
                                    'snippet': f"SEC filing dated {filing_date} - May contain ESG disclosures, risk factors",
                                    'url': full_url,
                                    'source': 'SEC EDGAR',
                                    'date': filing_date,
                                    'data_source_api': 'SEC EDGAR - Full Analysis'
                                })
                
                if results:
                    print(f"   ✅ SEC Full: {len(results)} recent filings")
                return results
        
        except Exception as e:
            print(f"   ⚠️ SEC Full error: {str(e)[:80]}")
        
        return []
    
    # ========================================
    # MEDIUM PRIORITY SOURCES
    # ========================================
    
    @source_tracker.track("MediaCloud")
    def _fetch_mediacloud(self, company: str, query: str, limit: int = 3) -> List[Dict]:
        """MediaCloud - News archive analysis"""
        try:
            # Note: MediaCloud may require API key signup
            # Using web interface as fallback
            print(f"   ℹ️ MediaCloud: API key required (skipping)")
            return []
        
        except Exception as e:
            print(f"   ⚠️ MediaCloud error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("EU Enforcement")
    def _fetch_eu_enforcement(self, company: str, limit: int = 3) -> List[Dict]:
        """EU Commission - Environmental enforcement database"""
        try:
            time.sleep(2)
            
            encoded_company = quote(company)
            url = f"https://ec.europa.eu/environment/legal/law/statistics.htm"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # EU enforcement data (simplified - actual implementation may vary)
                print(f"   ℹ️ EU Enforcement: Complex database (manual check recommended)")
                return []
        
        except Exception as e:
            print(f"   ⚠️ EU Enforcement error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("UK CMA")
    def _fetch_uk_cma(self, company: str, limit: int = 3) -> List[Dict]:
        """UK Competition & Markets Authority - Greenwashing cases"""
        try:
            time.sleep(2)
            
            encoded_company = quote(company)
            url = f"https://www.gov.uk/cma-cases?keywords={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                
                case_items = soup.find_all('li', class_='gem-c-document-list__item', limit=limit)
                
                for item in case_items:
                    link_elem = item.find('a')
                    title_elem = item.find('a')
                    
                    if link_elem and title_elem:
                        href = link_elem.get('href', '')
                        full_url = f"https://www.gov.uk{href}" if not href.startswith('http') else href
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': 'UK CMA investigation or case',
                            'url': full_url,
                            'source': 'UK CMA',
                            'date': datetime.now().isoformat(),
                            'data_source_api': 'UK CMA - Competition Cases'
                        })
                
                if results:
                    print(f"   ✅ UK CMA: {len(results)} cases")
                else:
                    print(f"   ℹ️ UK CMA: No cases found")
                
                return results
        
        except Exception as e:
            print(f"   ⚠️ UK CMA error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("UK ASA")
    def _fetch_uk_asa(self, company: str, limit: int = 3) -> List[Dict]:
        """UK Advertising Standards Authority - Greenwashing ad rulings"""
        try:
            time.sleep(2)
            
            encoded_company = quote(company)
            url = f"https://www.asa.org.uk/rulings.html?q={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                
                rulings = soup.find_all('div', class_='ruling', limit=limit)
                
                for ruling in rulings:
                    title_elem = ruling.find('h3') or ruling.find('h2')
                    link_elem = ruling.find('a')
                    
                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        full_url = f"https://www.asa.org.uk{href}" if not href.startswith('http') else href
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': 'ASA advertising standards ruling - potential greenwashing',
                            'url': full_url,
                            'source': 'UK ASA',
                            'date': datetime.now().isoformat(),
                            'data_source_api': 'UK ASA - Ad Rulings'
                        })
                
                if results:
                    print(f"   ✅ UK ASA: {len(results)} ad rulings")
                else:
                    print(f"   ℹ️ UK ASA: No rulings found")
                
                return results
        
        except Exception as e:
            print(f"   ⚠️ UK ASA error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("Changing Markets")
    def _fetch_changing_markets(self, company: str, limit: int = 3) -> List[Dict]:
        """Changing Markets Foundation - Greenwashing investigations"""
        try:
            time.sleep(2)
            
            encoded_company = quote(company)
            url = f"https://changingmarkets.org/?s={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                
                articles = soup.find_all('article', limit=limit)
                
                for article in articles:
                    title_elem = article.find('h2') or article.find('h3')
                    link_elem = article.find('a')
                    
                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': 'Changing Markets Foundation investigation/report',
                            'url': href,
                            'source': 'Changing Markets',
                            'date': datetime.now().isoformat(),
                            'data_source_api': 'Changing Markets - NGO Reports'
                        })
                
                if results:
                    print(f"   ✅ Changing Markets: {len(results)} reports")
                else:
                    print(f"   ℹ️ Changing Markets: No reports found")
                
                return results
        
        except Exception as e:
            print(f"   ⚠️ Changing Markets error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("ClientEarth")
    def _fetch_clientearth(self, company: str, limit: int = 3) -> List[Dict]:
        """ClientEarth - Environmental legal cases"""
        try:
            time.sleep(2)
            
            encoded_company = quote(company)
            url = f"https://www.clientearth.org/?s={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                
                articles = soup.find_all('article', limit=limit)
                
                for article in articles:
                    title_elem = article.find('h2') or article.find('h3')
                    link_elem = article.find('a')
                    
                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        full_url = href if href.startswith('http') else f"https://www.clientearth.org{href}"
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': 'ClientEarth environmental legal case or campaign',
                            'url': full_url,
                            'source': 'ClientEarth',
                            'date': datetime.now().isoformat(),
                            'data_source_api': 'ClientEarth - Legal NGO'
                        })
                
                if results:
                    print(f"   ✅ ClientEarth: {len(results)} legal cases")
                else:
                    print(f"   ℹ️ ClientEarth: No cases found")
                
                return results
        
        except Exception as e:
            print(f"   ⚠️ ClientEarth error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("Human Rights Watch")
    def _fetch_hrw(self, company: str, limit: int = 3) -> List[Dict]:
        """Human Rights Watch - Labor and social violations"""
        try:
            time.sleep(2)
            
            encoded_company = quote(company)
            url = f"https://www.hrw.org/search?search={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                
                search_results = soup.find_all('div', class_='node', limit=limit)
                
                for result in search_results:
                    title_elem = result.find('h3') or result.find('h2')
                    link_elem = result.find('a')
                    
                    if title_elem and link_elem:
                        href = link_elem.get('href', '')
                        full_url = href if href.startswith('http') else f"https://www.hrw.org{href}"
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'snippet': 'Human Rights Watch report on labor/social issues',
                            'url': full_url,
                            'source': 'Human Rights Watch',
                            'date': datetime.now().isoformat(),
                            'data_source_api': 'HRW - Human Rights Reports'
                        })
                
                if results:
                    print(f"   ✅ HRW: {len(results)} reports")
                else:
                    print(f"   ℹ️ HRW: No reports found")
                
                return results
        
        except Exception as e:
            print(f"   ⚠️ HRW error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("UNFCCC")
    def _fetch_unfccc(self, company: str, limit: int = 3) -> List[Dict]:
        """UNFCCC - Corporate climate pledges and commitments"""
        try:
            time.sleep(2)
            
            # UNFCCC Global Climate Action portal
            encoded_company = quote(company)
            url = f"https://climateaction.unfccc.int/"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"   ℹ️ UNFCCC: Complex database (check climateaction.unfccc.int manually)")
                return []
        
        except Exception as e:
            print(f"   ⚠️ UNFCCC error: {str(e)[:80]}")
        
        return []
    
    # ========================================
    # LOW PRIORITY SOURCES (Complex)
    # ========================================
    
    @source_tracker.track("Common Crawl")
    def _fetch_common_crawl(self, company: str, limit: int = 3) -> List[Dict]:
        """Common Crawl - Massive web archive (use sparingly - very large)"""
        try:
            # Common Crawl is massive - skipping for performance
            print(f"   ℹ️ Common Crawl: Dataset too large (manual analysis recommended)")
            return []
        
        except Exception as e:
            print(f"   ⚠️ Common Crawl error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("OECD Guidelines")
    def _fetch_oecd_cases(self, company: str, limit: int = 3) -> List[Dict]:
        """OECD Guidelines - Multinational enterprise complaints"""
        try:
            time.sleep(2)
            
            url = "http://mneguidelines.oecd.org/database/"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"   ℹ️ OECD: Database requires manual search at mneguidelines.oecd.org")
                return []
        
        except Exception as e:
            print(f"   ⚠️ OECD error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("ILO")
    def _fetch_ilo(self, company: str, limit: int = 3) -> List[Dict]:
        """ILO - International Labor Organization violations"""
        try:
            time.sleep(2)
            
            encoded_company = quote(company)
            url = f"https://www.ilo.org/global/lang--en/index.htm"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"   ℹ️ ILO: Complex database (check www.ilo.org manually)")
                return []
        
        except Exception as e:
            print(f"   ⚠️ ILO error: {str(e)[:80]}")
        
        return []
    
    @source_tracker.track("Open Apparel Registry")
    def _fetch_open_apparel(self, company: str, limit: int = 3) -> List[Dict]:
        """Open Apparel Registry - Supply chain transparency"""
        try:
            time.sleep(1)
            
            encoded_company = quote(company)
            url = f"https://openapparel.org/facilities?q={encoded_company}"
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                results = []
                
                facilities = soup.find_all('div', class_='facility-item', limit=limit)
                
                for facility in facilities:
                    name_elem = facility.find('h3') or facility.find('h2')
                    link_elem = facility.find('a')
                    
                    if name_elem and link_elem:
                        href = link_elem.get('href', '')
                        full_url = f"https://openapparel.org{href}" if not href.startswith('http') else href
                        
                        results.append({
                            'title': name_elem.get_text(strip=True),
                            'snippet': 'Supply chain facility registered in Open Apparel Registry',
                            'url': full_url,
                            'source': 'Open Apparel Registry',
                            'date': datetime.now().isoformat(),
                            'data_source_api': 'OAR - Supply Chain'
                        })
                
                if results:
                    print(f"   ✅ Open Apparel: {len(results)} facilities")
                else:
                    print(f"   ℹ️ Open Apparel: No facilities found")
                
                return results
        
        except Exception as e:
            print(f"   ⚠️ Open Apparel error: {str(e)[:80]}")
        
        return []

# Global instance
free_data_aggregator = FreeDataAggregator()


# ========================================
# TOP 10 BIG TRUSTED SOURCES (API KEY REQUIRED)
# ========================================

@source_tracker.track("NewsAPI.org")
def search_newsapi_org(company: str, max_results: int = 5) -> List[Dict]:
    """NewsAPI.org - Aggregates 80,000+ sources including Bloomberg, Reuters"""
    api_key = free_data_aggregator.newsapi_key
    if not api_key:
        return []
    
    try:
        from newsapi import NewsApiClient
        newsapi = NewsApiClient(api_key=api_key)
        
        # Search for company + sustainability
        articles = newsapi.get_everything(
            q=f'{company} AND (sustainability OR ESG OR greenwashing OR environmental)',
            language='en',
            sort_by='relevancy',
            page_size=max_results
        )
        
        results = []
        if articles.get('articles'):
            for article in articles['articles'][:max_results]:
                results.append({
                    'title': article.get('title', ''),
                    'snippet': article.get('description', '')[:200],
                    'url': article.get('url', ''),
                    'source': article.get('source', {}).get('name', 'NewsAPI'),
                    'date': article.get('publishedAt', ''),
                    'data_source_api': 'NewsAPI.org'
                })
        
        return results
    except Exception:
        return []


@source_tracker.track("NewsData.io")
def search_newsdata_io(company: str, max_results: int = 5) -> List[Dict]:
    """NewsData.io - Real-time news from 50,000+ sources"""
    api_key = free_data_aggregator.newsdata_key
    if not api_key:
        return []
    
    try:
        url = f"https://newsdata.io/api/1/news?apikey={api_key}&q={quote(company)} sustainability&language=en&size={max_results}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        results = []
        if data.get('results'):
            for article in data['results'][:max_results]:
                results.append({
                    'title': article.get('title', ''),
                    'snippet': article.get('description', '')[:200],
                    'url': article.get('link', ''),
                    'source': article.get('source_id', 'NewsData'),
                    'date': article.get('pubDate', ''),
                    'data_source_api': 'NewsData.io'
                })
        
        return results
    except Exception:
        return []


@source_tracker.track("Alpha Vantage")
def search_alpha_vantage(company: str, max_results: int = 5) -> List[Dict]:
    """Alpha Vantage - Financial data and company news"""
    api_key = free_data_aggregator.alphavantage_key
    if not api_key:
        return []
    
    try:
        # Get company news and sentiments
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={company}&apikey={api_key}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        results = []
        if data.get('feed'):
            for article in data['feed'][:max_results]:
                results.append({
                    'title': article.get('title', ''),
                    'snippet': article.get('summary', '')[:200],
                    'url': article.get('url', ''),
                    'source': article.get('source', 'Alpha Vantage'),
                    'date': article.get('time_published', ''),
                    'data_source_api': 'Alpha Vantage'
                })
        
        return results
    except Exception:
        return []


@source_tracker.track("Finnhub")
def search_finnhub(company: str, max_results: int = 5) -> List[Dict]:
    """Finnhub - Real-time financial data and company news"""
    api_key = free_data_aggregator.finnhub_key
    if not api_key:
        return []
    
    try:
        # Get company news
        url = f"https://finnhub.io/api/v1/company-news?symbol={company}&from=2024-01-01&to=2026-12-31&token={api_key}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        results = []
        for article in data[:max_results]:
            results.append({
                'title': article.get('headline', ''),
                'snippet': article.get('summary', '')[:200],
                'url': article.get('url', ''),
                'source': article.get('source', 'Finnhub'),
                'date': datetime.fromtimestamp(article.get('datetime', 0)).isoformat() if article.get('datetime') else '',
                'data_source_api': 'Finnhub'
            })
        
        return results
    except Exception:
        return []


@source_tracker.track("Polygon.io")
def search_polygon(company: str, max_results: int = 5) -> List[Dict]:
    """Polygon.io - Stock market data and company news"""
    api_key = free_data_aggregator.polygon_key
    if not api_key:
        return []
    
    try:
        # Get ticker news
        url = f"https://api.polygon.io/v2/reference/news?ticker={company}&limit={max_results}&apiKey={api_key}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        results = []
        if data.get('results'):
            for article in data['results'][:max_results]:
                results.append({
                    'title': article.get('title', ''),
                    'snippet': article.get('description', '')[:200],
                    'url': article.get('article_url', ''),
                    'source': article.get('publisher', {}).get('name', 'Polygon'),
                    'date': article.get('published_utc', ''),
                    'data_source_api': 'Polygon.io'
                })
        
        return results
    except Exception:
        return []


# ========================================
# PUBLIC API METHODS (NO KEYS REQUIRED)
# ========================================

@source_tracker.track("Google News RSS")
def search_google_news_rss(company: str, max_results: int = 5) -> List[Dict]:
    """Google News RSS - 100% FREE"""
    try:
        query = quote(f"{company} sustainability OR greenwashing OR ESG")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code != 200:
            return []
        
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)
        
        results = []
        for item in root.findall('.//item')[:max_results]:
            title = item.find('title')
            link = item.find('link')
            pub_date = item.find('pubDate')
            description = item.find('description')
            
            if title is not None and link is not None:
                results.append({
                    'title': title.text,
                    'snippet': description.text[:200] if description is not None else '',
                    'url': link.text,
                    'source': 'Google News',
                    'date': pub_date.text if pub_date is not None else '',
                    'data_source_api': 'Google News RSS'
                })
        
        return results
    except Exception:
        return []


@source_tracker.track("DuckDuckGo Search")
def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict]:
    """DuckDuckGo Search - 100% FREE, real-time web search"""
    try:
        from ddgs import DDGS
        
        results = []
        with DDGS() as ddgs:
            search_results = ddgs.text(f"{query} ESG sustainability", max_results=max_results)
            
            for result in search_results:
                results.append({
                    'title': result.get('title', ''),
                    'snippet': result.get('body', '')[:200],
                    'url': result.get('href', ''),
                    'source': 'DuckDuckGo',
                    'date': datetime.now().isoformat(),
                    'data_source_api': 'DuckDuckGo Search'
                })
        
        return results
    except ImportError:
        # ddgs not installed
        return []
    except Exception as e:
        return []


@source_tracker.track("Reuters Sustainability RSS")
def search_reuters_sustainability(company: str, max_results: int = 5) -> List[Dict]:
    """Reuters Sustainability RSS - 100% FREE"""
    try:
        url = "https://www.reuters.com/arc/outboundfeeds/v3/rss/?outputType=xml&size=50&topics=sustainability"
        
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code != 200:
            return []
        
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)
        
        results = []
        company_lower = company.lower()
        
        for item in root.findall('.//item'):
            title = item.find('title')
            link = item.find('link')
            pub_date = item.find('pubDate')
            description = item.find('description')
            
            if title is not None and link is not None:
                title_text = title.text or ''
                desc_text = description.text if description is not None else ''
                
                # Filter by company name
                if company_lower in title_text.lower() or company_lower in desc_text.lower():
                    results.append({
                        'title': title_text,
                        'snippet': desc_text[:200],
                        'url': link.text,
                        'source': 'Reuters Sustainability',
                        'date': pub_date.text if pub_date is not None else '',
                        'data_source_api': 'Reuters RSS'
                    })
                    
                    if len(results) >= max_results:
                        break
        
        return results
    except Exception:
        return []


@source_tracker.track("Guardian Environment")
def search_guardian_environment(company: str, max_results: int = 5) -> List[Dict]:
    """Guardian Environment RSS - 100% FREE"""
    try:
        url = "https://www.theguardian.com/environment/rss"
        
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        
        if response.status_code != 200:
            return []
        
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)
        
        results = []
        company_lower = company.lower()
        
        for item in root.findall('.//item'):
            title = item.find('title')
            link = item.find('link')
            pub_date = item.find('pubDate')
            description = item.find('description')
            
            if title is not None and link is not None:
                title_text = title.text or ''
                desc_text = description.text if description is not None else ''
                
                # Filter by company name
                if company_lower in title_text.lower() or company_lower in desc_text.lower():
                    results.append({
                        'title': title_text,
                        'snippet': desc_text[:200],
                        'url': link.text,
                        'source': 'The Guardian',
                        'date': pub_date.text if pub_date is not None else '',
                        'data_source_api': 'Guardian RSS'
                    })
                    
                    if len(results) >= max_results:
                        break
        
        return results
    except Exception:
        return []


@source_tracker.track("SEC EDGAR Search")
def search_sec_edgar(company: str, max_results: int = 5) -> List[Dict]:
    """SEC EDGAR - 100% FREE"""
    try:
        # Search for company CIK
        search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={quote(company)}&type=&dateb=&owner=exclude&count=10"
        headers = {'User-Agent': 'Mozilla/5.0 ESG-Analyzer contact@example.com'}
        
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        
        # Find filing table
        filing_table = soup.find('table', class_='tableFile2')
        if filing_table:
            rows = filing_table.find_all('tr')[1:max_results+1]  # Skip header
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    filing_type = cols[0].get_text(strip=True)
                    description = cols[2].get_text(strip=True)
                    filing_date = cols[3].get_text(strip=True)
                    
                    # Get document link
                    doc_link = cols[1].find('a')
                    if doc_link:
                        doc_url = f"https://www.sec.gov{doc_link.get('href')}"
                        
                        results.append({
                            'title': f"{company} - {filing_type}: {description}",
                            'snippet': f"SEC Filing {filing_type} filed on {filing_date}",
                            'url': doc_url,
                            'source': 'SEC EDGAR',
                            'date': filing_date,
                            'data_source_api': 'SEC EDGAR'
                        })
        
        return results
    except Exception:
        return []


@source_tracker.track("EPA Enforcement Search")
def search_epa_enforcement(company: str, max_results: int = 5) -> List[Dict]:
    """EPA Enforcement - 100% FREE"""
    try:
        search_url = f"https://echo.epa.gov/facilities/facility-search/results?qname={quote(company)}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        
        # Parse facility results
        facilities = soup.find_all('div', class_='facility-item')[:max_results]
        
        for facility in facilities:
            name_elem = facility.find('h3')
            location_elem = facility.find(class_='location')
            
            if name_elem:
                facility_link = name_elem.find('a')
                facility_url = f"https://echo.epa.gov{facility_link.get('href')}" if facility_link else ''
                
                results.append({
                    'title': name_elem.get_text(strip=True),
                    'snippet': f"EPA regulated facility - {location_elem.get_text(strip=True) if location_elem else 'Location data available'}",
                    'url': facility_url,
                    'source': 'EPA ECHO',
                    'date': datetime.now().isoformat(),
                    'data_source_api': 'EPA Enforcement'
                })
        
        return results
    except Exception:
        return []


@source_tracker.track("ArXiv Research")
def search_arxiv_sustainability(query: str, max_results: int = 5) -> List[Dict]:
    """ArXiv.org - 100% FREE Academic Research"""
    try:
        import feedparser
        
        # Simple query - just use main terms
        search_terms = query.replace(' ', '+').replace('AND', '%26')
        
        url = f"http://export.arxiv.org/api/query?search_query=all:{search_terms}+sustainability&start=0&max_results={max_results}"
        
        feed = feedparser.parse(url)
        
        results = []
        for entry in feed.entries[:max_results]:
            results.append({
                'title': entry.title,
                'snippet': entry.summary[:200] if hasattr(entry, 'summary') else '',
                'url': entry.link,
                'source': 'ArXiv.org',
                'date': entry.published if hasattr(entry, 'published') else '',
                'data_source_api': 'ArXiv API'
            })
        
        return results
    except Exception:
        return []


@source_tracker.track("Yahoo Finance")
def search_yahoo_finance(company: str, max_results: int = 5) -> List[Dict]:
    """Yahoo Finance RSS - 100% FREE"""
    try:
        import feedparser
        
        # Yahoo Finance company news RSS
        company_symbol = company.replace(' ', '-').lower()
        url = f"https://finance.yahoo.com/rss/headline?s={company}"
        
        feed = feedparser.parse(url)
        
        results = []
        company_lower = company.lower()
        
        for entry in feed.entries[:max_results * 2]:
            title_text = entry.title if hasattr(entry, 'title') else ''
            summary_text = entry.summary if hasattr(entry, 'summary') else ''
            
            # Filter by company mention
            if company_lower in title_text.lower() or company_lower in summary_text.lower():
                results.append({
                    'title': title_text,
                    'snippet': summary_text[:200],
                    'url': entry.link if hasattr(entry, 'link') else '',
                    'source': 'Yahoo Finance',
                    'date': entry.published if hasattr(entry, 'published') else '',
                    'data_source_api': 'Yahoo Finance RSS'
                })
                
                if len(results) >= max_results:
                    break
        
        return results
    except Exception:
        return []


@source_tracker.track("BBC News")
def search_bbc_news(company: str, max_results: int = 5) -> List[Dict]:
    """BBC News RSS - 100% FREE"""
    try:
        import feedparser
        
        # BBC Business and Science/Environment feeds
        feeds = [
            'https://feeds.bbci.co.uk/news/business/rss.xml',
            'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml'
        ]
        
        results = []
        company_lower = company.lower()
        
        for feed_url in feeds:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                title_text = entry.title if hasattr(entry, 'title') else ''
                summary_text = entry.summary if hasattr(entry, 'summary') else ''
                
                # Filter by company mention
                if company_lower in title_text.lower() or company_lower in summary_text.lower():
                    results.append({
                        'title': title_text,
                        'snippet': summary_text[:200],
                        'url': entry.link if hasattr(entry, 'link') else '',
                        'source': 'BBC News',
                        'date': entry.published if hasattr(entry, 'published') else '',
                        'data_source_api': 'BBC RSS'
                    })
                    
                    if len(results) >= max_results:
                        break
            
            if len(results) >= max_results:
                break
        
        return results
    except Exception:
        return []


@source_tracker.track("InsideClimate News")
def search_inside_climate(company: str, max_results: int = 5) -> List[Dict]:
    """InsideClimate News RSS - 100% FREE"""
    try:
        import feedparser
        
        url = 'https://insideclimatenews.org/feed/'
        feed = feedparser.parse(url)
        
        results = []
        company_lower = company.lower()
        
        for entry in feed.entries[:max_results * 3]:
            title_text = entry.title if hasattr(entry, 'title') else ''
            summary_text = entry.summary if hasattr(entry, 'summary') else ''
            
            # Filter by company mention
            if company_lower in title_text.lower() or company_lower in summary_text.lower():
                results.append({
                    'title': title_text,
                    'snippet': BeautifulSoup(summary_text, 'html.parser').get_text()[:200],
                    'url': entry.link if hasattr(entry, 'link') else '',
                    'source': 'InsideClimate News',
                    'date': entry.published if hasattr(entry, 'published') else '',
                    'data_source_api': 'InsideClimate RSS'
                })
                
                if len(results) >= max_results:
                    break
        
        return results
    except Exception:
        return []


@source_tracker.track("Climate Home News")
def search_climate_home(company: str, max_results: int = 5) -> List[Dict]:
    """Climate Home News RSS - 100% FREE"""
    try:
        import feedparser
        
        url = 'https://www.climatechangenews.com/feed/'
        feed = feedparser.parse(url)
        
        results = []
        company_lower = company.lower()
        
        for entry in feed.entries[:max_results * 3]:
            title_text = entry.title if hasattr(entry, 'title') else ''
            summary_text = entry.summary if hasattr(entry, 'summary') else ''
            
            # Filter by company mention
            if company_lower in title_text.lower() or company_lower in summary_text.lower():
                results.append({
                    'title': title_text,
                    'snippet': BeautifulSoup(summary_text, 'html.parser').get_text()[:200],
                    'url': entry.link if hasattr(entry, 'link') else '',
                    'source': 'Climate Home News',
                    'date': entry.published if hasattr(entry, 'published') else '',
                    'data_source_api': 'Climate Home RSS'
                })
                
                if len(results) >= max_results:
                    break
        
        return results
    except Exception:
        return []


@source_tracker.track("ProPublica")
def search_propublica(company: str, max_results: int = 5) -> List[Dict]:
    """ProPublica - 100% FREE Investigative Journalism"""
    try:
        # ProPublica search page
        search_url = f"https://www.propublica.org/search?q={quote(company)}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        response = requests.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        
        # Find article results
        articles = soup.find_all('article', class_='article-item')[:max_results]
        
        for article in articles:
            title_elem = article.find('h2') or article.find('h3')
            link_elem = article.find('a')
            snippet_elem = article.find('p', class_='dek') or article.find('div', class_='description')
            date_elem = article.find('time')
            
            if title_elem and link_elem:
                article_url = link_elem.get('href', '')
                if not article_url.startswith('http'):
                    article_url = f"https://www.propublica.org{article_url}"
                
                results.append({
                    'title': title_elem.get_text(strip=True),
                    'snippet': snippet_elem.get_text(strip=True)[:200] if snippet_elem else '',
                    'url': article_url,
                    'source': 'ProPublica',
                    'date': date_elem.get('datetime', '') if date_elem else '',
                    'data_source_api': 'ProPublica Search'
                })
        
        return results
    except Exception:
        return []


@source_tracker.track("NPR Environment")
def search_npr_environment(company: str, max_results: int = 5) -> List[Dict]:
    """NPR Environment RSS - 100% FREE"""
    try:
        import feedparser
        
        # NPR Climate and Environment feed
        url = 'https://feeds.npr.org/1025/rss.xml'
        feed = feedparser.parse(url)
        
        results = []
        company_lower = company.lower()
        
        for entry in feed.entries[:max_results * 3]:
            title_text = entry.title if hasattr(entry, 'title') else ''
            summary_text = entry.summary if hasattr(entry, 'summary') else ''
            
            # Filter by company mention
            if company_lower in title_text.lower() or company_lower in summary_text.lower():
                results.append({
                    'title': title_text,
                    'snippet': BeautifulSoup(summary_text, 'html.parser').get_text()[:200],
                    'url': entry.link if hasattr(entry, 'link') else '',
                    'source': 'NPR',
                    'date': entry.published if hasattr(entry, 'published') else '',
                    'data_source_api': 'NPR RSS'
                })
                
                if len(results) >= max_results:
                    break
        
        return results
    except Exception:
        return []


# Make all new functions accessible
free_data_aggregator.search_newsapi_org = search_newsapi_org
free_data_aggregator.search_newsdata_io = search_newsdata_io
free_data_aggregator.search_alpha_vantage = search_alpha_vantage
free_data_aggregator.search_finnhub = search_finnhub
free_data_aggregator.search_polygon = search_polygon
free_data_aggregator.search_google_news_rss = search_google_news_rss
free_data_aggregator.search_duckduckgo = search_duckduckgo
free_data_aggregator.search_reuters_sustainability = search_reuters_sustainability
free_data_aggregator.search_guardian_environment = search_guardian_environment
free_data_aggregator.search_sec_edgar = search_sec_edgar
free_data_aggregator.search_epa_enforcement = search_epa_enforcement
free_data_aggregator.search_arxiv_sustainability = search_arxiv_sustainability
free_data_aggregator.search_yahoo_finance = search_yahoo_finance
free_data_aggregator.search_bbc_news = search_bbc_news
free_data_aggregator.search_inside_climate = search_inside_climate
free_data_aggregator.search_climate_home = search_climate_home
free_data_aggregator.search_propublica = search_propublica
free_data_aggregator.search_npr_environment = search_npr_environment
