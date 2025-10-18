"""
Real-Time ESG News Monitoring Agent
Continuously scrapes and stores latest ESG news in Chroma
"""
import os
import requests
from newspaper import Article
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Dict, Any, List
import time
import json  # Add this
from core.vector_store import vector_store
from utils.enterprise_data_sources import enterprise_fetcher


class RealTimeMonitor:
    def __init__(self):
        self.name = "Real-Time ESG News Monitor"
        self.vector_store = vector_store
        self.fetcher = enterprise_fetcher
        
        # Load RSS feeds from config (NOT hardcoded)
        self.news_sources = self._load_news_sources()

    def _load_news_sources(self) -> List[str]:
        """Load RSS feeds from config file"""
        try:
            import json
            config_path = "config/data_sources.json"
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    feeds = config.get('rss_feeds', [])
                    return [feed['url'] for feed in feeds]
            else:
                print("⚠️ Config file not found, using default sources")
        except Exception as e:
            print(f"⚠️ Error loading config: {e}")
        
        # Fallback to minimal set (but log warning)
        print("⚠️ Using fallback RSS feeds - add config/data_sources.json for customization")
        return [
            "https://www.reuters.com/arc/outboundfeeds/v1/rss/?outputType=xml&size=25&feedName=sustainability"
        ]

        
    def scrape_and_store(self, company: str, hours_lookback: int = 24) -> Dict[str, Any]:
        """
        Scrape latest news and store in Chroma for real-time retrieval
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 8: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        print(f"Looking back: {hours_lookback} hours")
        
        cutoff_time = datetime.now() - timedelta(hours=hours_lookback)
        
        # 1. Fetch from all sources
        print("\n📰 Fetching real-time news...")
        all_articles = []
        
        # From our enterprise fetcher
        source_dict = self.fetcher.fetch_all_sources(
            company=company,
            query=f"ESG sustainability {company}",
            max_per_source=5
        )
        
        fetched = self.fetcher.aggregate_and_deduplicate(source_dict)
        all_articles.extend(fetched)
        
        # Scrape RSS feeds
        rss_articles = self._scrape_rss_feeds(company)
        all_articles.extend(rss_articles)
        
        # Extract full content using newspaper3k
        print(f"\n🔎 Extracting full article content...")
        enriched_articles = self._enrich_articles(all_articles[:10])  # Top 10
        
        # Filter by recency
        recent_articles = [
            a for a in enriched_articles 
            if self._is_recent(a.get('date', ''), cutoff_time)
        ]
        
        print(f"\n📊 Found {len(recent_articles)} recent articles")
        
        # Store in Chroma
        if recent_articles:
            self._store_in_chroma(recent_articles, company)
        
        return {
            "company": company,
            "articles_found": len(recent_articles),
            "articles": recent_articles,
            "timestamp": datetime.now().isoformat()
        }
    
    def _scrape_rss_feeds(self, company: str) -> List[Dict]:
        """Scrape RSS feeds - ROBUST XML parsing"""
        articles = []
        
        for feed_url in self.news_sources:
            try:
                response = requests.get(feed_url, timeout=10)
                if response.status_code == 200:
                    try:
                        from xml.etree import ElementTree as ET
                        
                        # Parse with error recovery
                        root = ET.fromstring(response.content)
                        
                        for item in root.findall('.//item')[:10]:
                            title = item.find('title')
                            description = item.find('description')
                            link = item.find('link')
                            pub_date = item.find('pubDate')
                            
                            if title is not None:
                                title_text = title.text or ""
                                desc_text = description.text if description is not None else ""
                                
                                # Check if company mentioned
                                if company.lower() in (title_text + desc_text).lower():
                                    articles.append({
                                        'title': title_text,
                                        'url': link.text if link is not None else '',
                                        'snippet': desc_text,
                                        'date': pub_date.text if pub_date is not None else '',
                                        'source': 'RSS Feed'
                                    })
                    
                    except ET.ParseError as e:
                        # Don't print error - just skip silently
                        continue
                        
            except Exception as e:
                # Skip quietly
                continue
        
        return articles


    
    def _enrich_articles(self, articles: List[Dict]) -> List[Dict]:
        """Extract full content - BLOCKS problematic domains"""
        enriched = []
        
        # Blocklist - sites that block scraping
        blocked_domains = [
            'yahoo.com', 'finance.yahoo', 
            'zhihu.com', 'baidu.com', 'weibo.com',  # Chinese sites
            'teslaaccessories.com',
            'mckinsey.com/~/med'  # Broken URLs
        ]
        
        for i, article in enumerate(articles):
            try:
                url = article.get('url', '')
                if not url:
                    enriched.append(article)
                    continue
                
                # Skip blocked domains
                if any(domain in url.lower() for domain in blocked_domains):
                    print(f"   ⏭️  Skipping blocked domain: {url[:50]}...")
                    article['extraction_skipped'] = True
                    article['skip_reason'] = 'Blocked domain'
                    enriched.append(article)
                    continue
            
            # Rest of your existing code...

                
                # Use newspaper3k with better headers
                news_article = Article(url)
                news_article.config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                news_article.config.request_timeout = 10
                
                news_article.download()
                news_article.parse()
                
                article['full_text'] = news_article.text[:5000]
                article['authors'] = news_article.authors
                article['publish_date'] = news_article.publish_date.isoformat() if news_article.publish_date else article.get('date')
                
                enriched.append(article)
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                # Don't crash - just log and continue
                error_msg = str(e)
                if '403' in error_msg or '503' in error_msg or 'Forbidden' in error_msg:
                    print(f"   ⚠️ Access blocked (article {i+1}): {error_msg[:100]}")
                else:
                    print(f"   ⚠️ Extraction error (article {i+1}): {error_msg[:100]}")
                
                article['extraction_failed'] = True
                article['extraction_error'] = error_msg[:200]
                enriched.append(article)
        
        return enriched

    
    def _is_recent(self, date_str: str, cutoff: datetime) -> bool:
        """Check if article is recent"""
        if not date_str:
            return False
        
        try:
            from dateutil import parser
            article_date = parser.parse(date_str)
            
            # Make timezone-naive for comparison
            if article_date.tzinfo:
                article_date = article_date.replace(tzinfo=None)
            if cutoff.tzinfo:
                cutoff = cutoff.replace(tzinfo=None)
            
            return article_date >= cutoff
        except:
            return False
    
    def _store_in_chroma(self, articles: List[Dict], company: str):
        """Store articles in Chroma vector DB"""
        
        print(f"💾 Storing {len(articles)} articles in Chroma...")
        
        documents = []
        metadatas = []
        ids = []
        
        for i, article in enumerate(articles):
            doc_id = f"{company}_{int(time.time())}_{i}"
            
            # Create document text
            text = f"{article.get('title', '')} {article.get('snippet', '')} {article.get('full_text', '')}"
            
            documents.append(text[:1000])  # Limit size
            metadatas.append({
                'company': company,
                'url': article.get('url', ''),
                'source': article.get('source', ''),
                'date': article.get('date', ''),
                'type': 'realtime_news',
                'scraped_at': datetime.now().isoformat()
            })
            ids.append(doc_id)
        
        self.vector_store.add_documents(documents, metadatas, ids)
        print(f"✅ Stored in Chroma")
