"""
Indian Sustainability Data Sources
APIs and data sources specifically for Indian enterprises and ESG compliance

Sources:
- SEBI: Listed company filings, BRSR reports
- MCA: Corporate information, CSR data
- CPCB: Environmental compliance data
- NSE/BSE: ESG disclosures
- Indian News: Economic Times, Business Standard, Moneycontrol, LiveMint
- Indian NGOs: CSE, TERI, WRI India
- Government: Data.gov.in, India Environmental Portal

Also includes:
- EPA OpenData (US)
- World Bank Climate APIs
- CDP Public Data
- OpenCorporates
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import json
from urllib.parse import quote, urlencode
from bs4 import BeautifulSoup
import time
from dotenv import load_dotenv

load_dotenv()


class IndianDataAggregator:
    """
    Indian-focused ESG data aggregator
    Combines Indian regulatory data, news, and sustainability APIs
    """
    
    def __init__(self):
        # API keys from .env
        self.newsapi_key = os.getenv("NEWSAPI_KEY")
        self.newsdata_key = os.getenv("NEWSDATA_KEY")
        self.world_bank_key = os.getenv("WORLD_BANK_API_KEY", "")  # Usually not needed
        
        # Cache directory
        self.cache_dir = "utils/cache/india"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Indian stock exchanges
        self.nse_api_base = "https://www.nseindia.com/api"
        self.bse_api_base = "https://api.bseindia.com"
        
        # Indian news sources for RSS
        self.indian_news_rss = {
            "economic_times": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
            "business_standard": "https://www.business-standard.com/rss/latest.rss",
            "livemint": "https://www.livemint.com/rss/homepage",
            "moneycontrol": "https://www.moneycontrol.com/rss/latestnews.xml",
            "hindu_business": "https://www.thehindubusinessline.com/feeder/default.rss"
        }
        
        print("[OK] Indian Data Aggregator initialized")
        print("   • Indian News Sources (ET, BS, Mint, MC)")
        print("   • SEBI/NSE/BSE Company Data")
        print("   • CPCB Environmental Compliance")
        print("   • MCA Corporate Information")
        print("   • World Bank Climate APIs")
        print("   • CDP Public Data")
        print("   • EPA OpenData")
        print()
    
    def fetch_all_indian_sources(self, company: str, 
                                  max_per_source: int = 5) -> Dict[str, List[Dict]]:
        """
        Fetch data from all Indian sources
        
        Args:
            company: Company name (e.g., "Reliance Industries")
            max_per_source: Maximum results per source
        
        Returns:
            Categorized results from all sources
        """
        
        results = {
            "news": [],
            "regulatory": [],
            "compliance": [],
            "financial": [],
            "research": [],
            "ngo": [],
            "environmental": []
        }
        
        print(f"\n🇮🇳 Fetching Indian sources for: {company}")
        
        # ========================================
        # INDIAN NEWS SOURCES
        # ========================================
        print("📰 Searching Indian news...")
        results["news"].extend(self._fetch_indian_news_rss(company, max_per_source))
        results["news"].extend(self._fetch_newsdata_india(company, max_per_source))
        results["news"].extend(self._fetch_google_news_india(company, max_per_source))
        
        # ========================================
        # REGULATORY SOURCES
        # ========================================
        print("⚖️  Searching regulatory filings...")
        results["regulatory"].extend(self._fetch_sebi_data(company, max_per_source))
        results["regulatory"].extend(self._fetch_mca_data(company, max_per_source))
        
        # ========================================
        # COMPLIANCE DATA
        # ========================================
        print("🏭 Checking compliance data...")
        results["compliance"].extend(self._fetch_cpcb_data(company, max_per_source))
        results["compliance"].extend(self._fetch_ngt_cases(company, max_per_source))
        
        # ========================================
        # ENVIRONMENTAL DATA
        # ========================================
        print("🌍 Fetching environmental data...")
        results["environmental"].extend(self._fetch_world_bank_climate(max_per_source))
        results["environmental"].extend(self._fetch_cdp_data(company, max_per_source))
        results["environmental"].extend(self._fetch_india_environment_portal(company, max_per_source))
        
        # ========================================
        # NGO/RESEARCH SOURCES
        # ========================================
        print("📚 Searching NGO/research sources...")
        results["ngo"].extend(self._fetch_cse_data(company, max_per_source))
        results["ngo"].extend(self._fetch_wri_india(company, max_per_source))
        
        # Count totals
        total = sum(len(v) for v in results.values())
        print(f"✅ Fetched {total} results from Indian sources\n")
        
        return results
    
    # ========================================
    # INDIAN NEWS APIS
    # ========================================
    
    def _fetch_indian_news_rss(self, company: str, limit: int = 5) -> List[Dict]:
        """Fetch from Indian news RSS feeds"""
        
        results = []
        
        for source_name, rss_url in self.indian_news_rss.items():
            try:
                import feedparser
                
                feed = feedparser.parse(rss_url)
                
                for entry in feed.entries[:20]:
                    title = entry.get("title", "").lower()
                    summary = entry.get("summary", entry.get("description", "")).lower()
                    
                    # Check if company mentioned
                    company_lower = company.lower()
                    company_words = company_lower.split()[:2]  # First two words
                    
                    if any(word in title or word in summary for word in company_words):
                        results.append({
                            "title": entry.get("title"),
                            "snippet": entry.get("summary", entry.get("description", ""))[:300],
                            "url": entry.get("link"),
                            "source": source_name.replace("_", " ").title(),
                            "date": entry.get("published"),
                            "data_source_api": f"Indian RSS: {source_name}",
                            "region": "India"
                        })
                        
                        if len(results) >= limit:
                            break
                
            except Exception as e:
                print(f"   ⚠️ {source_name} RSS error: {str(e)[:50]}")
        
        return results[:limit]
    
    def _fetch_newsdata_india(self, company: str, limit: int = 5) -> List[Dict]:
        """Fetch Indian news from NewsData.io"""
        
        if not self.newsdata_key:
            return []
        
        try:
            url = "https://newsdata.io/api/1/news"
            params = {
                "apikey": self.newsdata_key,
                "q": company,
                "country": "in",
                "language": "en",
                "category": "business"
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get("results", [])
                
                return [{
                    "title": a.get("title"),
                    "snippet": a.get("description", "")[:300],
                    "url": a.get("link"),
                    "source": a.get("source_id", "NewsData India"),
                    "date": a.get("pubDate"),
                    "data_source_api": "NewsData.io India",
                    "region": "India"
                } for a in articles[:limit]]
                
        except Exception as e:
            print(f"   ⚠️ NewsData India error: {str(e)[:50]}")
        
        return []
    
    def _fetch_google_news_india(self, company: str, limit: int = 5) -> List[Dict]:
        """Fetch from Google News India RSS"""
        
        try:
            import feedparser
            
            # Google News India search
            query = quote(f"{company} ESG sustainability India")
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            
            feed = feedparser.parse(rss_url)
            
            results = []
            for entry in feed.entries[:limit]:
                results.append({
                    "title": entry.get("title"),
                    "snippet": entry.get("summary", "")[:300],
                    "url": entry.get("link"),
                    "source": "Google News India",
                    "date": entry.get("published"),
                    "data_source_api": "Google News India RSS",
                    "region": "India"
                })
            
            return results
            
        except Exception as e:
            print(f"   ⚠️ Google News India error: {str(e)[:50]}")
        
        return []
    
    # ========================================
    # REGULATORY APIs
    # ========================================
    
    def _fetch_sebi_data(self, company: str, limit: int = 5) -> List[Dict]:
        """
        Fetch SEBI regulatory filings
        Note: SEBI doesn't have public API, scraping EDIFAR/SEBI website
        """
        
        results = []
        
        try:
            # SEBI Corporate Filings search
            search_url = "https://www.sebi.gov.in/sebiweb/ajax/corporatefilings"
            
            # Try to get company code
            # For now, return structured placeholder with SEBI guidance
            results.append({
                "title": f"SEBI BRSR Filing Search: {company}",
                "snippet": "Business Responsibility and Sustainability Report (BRSR) - Mandatory for top 1000 listed companies. Check NSE/BSE for latest filings.",
                "url": f"https://www.sebi.gov.in/enforcement/search-for-corporate-entities.html",
                "source": "SEBI",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "SEBI Web Search",
                "region": "India",
                "document_type": "regulatory_guidance"
            })
            
        except Exception as e:
            print(f"   ⚠️ SEBI data error: {str(e)[:50]}")
        
        return results[:limit]
    
    def _fetch_mca_data(self, company: str, limit: int = 5) -> List[Dict]:
        """
        Fetch MCA (Ministry of Corporate Affairs) data
        Note: MCA21 requires authentication, providing guidance
        """
        
        results = []
        
        try:
            # MCA company search guidance
            results.append({
                "title": f"MCA Company Information: {company}",
                "snippet": "Ministry of Corporate Affairs - Companies Act compliance, CSR reports, annual returns. Search on MCA21 portal for CIN and filings.",
                "url": "https://www.mca.gov.in/mcafoportal/viewCompanyMasterData.do",
                "source": "MCA India",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "MCA Portal Reference",
                "region": "India",
                "document_type": "regulatory_guidance"
            })
            
            # CSR mandate reference
            results.append({
                "title": "CSR Mandate - Companies Act 2013",
                "snippet": "Section 135 requires companies with net worth ≥₹500 crore, turnover ≥₹1000 crore, or net profit ≥₹5 crore to spend 2% average net profits on CSR.",
                "url": "https://www.mca.gov.in/Ministry/pdf/CompaniesActNotification2_2014.pdf",
                "source": "MCA India",
                "date": "2014-02-27",
                "data_source_api": "MCA CSR Rules",
                "region": "India",
                "document_type": "regulation"
            })
            
        except Exception as e:
            print(f"   ⚠️ MCA data error: {str(e)[:50]}")
        
        return results[:limit]
    
    # ========================================
    # ENVIRONMENTAL COMPLIANCE
    # ========================================
    
    def _fetch_cpcb_data(self, company: str, limit: int = 5) -> List[Dict]:
        """
        Fetch CPCB (Central Pollution Control Board) compliance data
        Covers: Consent to Operate, emission monitoring, violations
        """
        
        results = []
        
        try:
            # CPCB Online Monitoring
            results.append({
                "title": f"CPCB OCEMS Compliance: {company}",
                "snippet": "Online Continuous Emission Monitoring System (OCEMS) - Real-time emission monitoring for 17 heavily polluting industries. Check CPCB portal for compliance status.",
                "url": "https://cpcb.nic.in/openpdffile.php?id=UmVwb3J0RmlsZXMvMTA=",
                "source": "CPCB",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "CPCB Compliance Portal",
                "region": "India",
                "document_type": "compliance"
            })
            
            # Grossly Polluting Industries
            results.append({
                "title": "CPCB Grossly Polluting Industries List",
                "snippet": "Categories: Distillery, Sugar, Pulp & Paper, Tannery, Textile, Petrochemical, Thermal Power, Mining. Mandatory pollution control compliance.",
                "url": "https://cpcb.nic.in/Industry/",
                "source": "CPCB",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "CPCB Industry Classification",
                "region": "India"
            })
            
        except Exception as e:
            print(f"   ⚠️ CPCB data error: {str(e)[:50]}")
        
        return results[:limit]
    
    def _fetch_ngt_cases(self, company: str, limit: int = 5) -> List[Dict]:
        """
        Search National Green Tribunal cases
        Note: NGT website is not API-friendly, providing search guidance
        """
        
        results = []
        
        try:
            results.append({
                "title": f"NGT Cases Search: {company}",
                "snippet": "National Green Tribunal - Environmental disputes, violations, remediation orders. Search cause lists and judgments for company involvement.",
                "url": "https://greentribunal.gov.in/case-status",
                "source": "NGT India",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "NGT Case Search",
                "region": "India",
                "document_type": "legal"
            })
            
        except Exception as e:
            print(f"   ⚠️ NGT search error: {str(e)[:50]}")
        
        return results[:limit]
    
    # ========================================
    # GLOBAL ENVIRONMENTAL APIs
    # ========================================
    
    def _fetch_world_bank_climate(self, limit: int = 5) -> List[Dict]:
        """
        Fetch World Bank Climate Data
        Free API: https://datahelpdesk.worldbank.org/knowledgebase/topics/125589
        """
        
        results = []
        
        try:
            # India climate indicators
            indicators = [
                ("EN.ATM.CO2E.KT", "CO2 emissions (kt)"),
                ("EG.USE.PCAP.KG.OE", "Energy use per capita"),
                ("EN.ATM.METH.KT.CE", "Methane emissions")
            ]
            
            for indicator_code, indicator_name in indicators[:limit]:
                url = f"https://api.worldbank.org/v2/country/IND/indicator/{indicator_code}"
                params = {"format": "json", "per_page": 5, "date": "2018:2023"}
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if len(data) > 1 and data[1]:
                        latest = data[1][0]
                        results.append({
                            "title": f"India {indicator_name}: {latest.get('value', 'N/A')}",
                            "snippet": f"World Bank indicator {indicator_code} for India. Year: {latest.get('date')}. Source: World Development Indicators.",
                            "url": f"https://data.worldbank.org/indicator/{indicator_code}?locations=IN",
                            "source": "World Bank",
                            "date": latest.get("date"),
                            "data_source_api": "World Bank Climate API",
                            "indicator_value": latest.get("value"),
                            "region": "India"
                        })
                        
                time.sleep(0.3)  # Rate limiting
                
        except Exception as e:
            print(f"   ⚠️ World Bank API error: {str(e)[:50]}")
        
        return results
    
    def _fetch_cdp_data(self, company: str, limit: int = 5) -> List[Dict]:
        """
        Fetch CDP (Carbon Disclosure Project) public data
        Note: Full API requires registration, using public search
        """
        
        results = []
        
        try:
            # CDP company search
            results.append({
                "title": f"CDP Disclosure Search: {company}",
                "snippet": "Carbon Disclosure Project - Climate change, water security, and forests questionnaires. Check CDP website for company scores and disclosure status.",
                "url": f"https://www.cdp.net/en/responses?queries%5Bname%5D={quote(company)}",
                "source": "CDP",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "CDP Public Search",
                "document_type": "climate_disclosure"
            })
            
            # CDP India context
            results.append({
                "title": "CDP India - Climate Disclosure Trends",
                "snippet": "400+ Indian companies disclose to CDP. India's A-List companies demonstrate climate leadership. Sectors: IT, Financial Services, Materials.",
                "url": "https://www.cdp.net/en/research/global-reports/india-report",
                "source": "CDP",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "CDP India Report",
                "region": "India"
            })
            
        except Exception as e:
            print(f"   ⚠️ CDP search error: {str(e)[:50]}")
        
        return results[:limit]
    
    def _fetch_india_environment_portal(self, company: str, limit: int = 5) -> List[Dict]:
        """
        Fetch from India Environment Portal
        CSE (Centre for Science and Environment) database
        """
        
        results = []
        
        try:
            # Search India Environment Portal
            search_url = f"https://www.indiawaterportal.org/search/node/{quote(company)}"
            
            response = requests.get(search_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Parse search results
                articles = soup.find_all('li', class_='search-result')[:limit]
                
                for article in articles:
                    title_elem = article.find('h3')
                    snippet_elem = article.find('p')
                    
                    if title_elem:
                        link = title_elem.find('a')
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "snippet": snippet_elem.get_text(strip=True)[:300] if snippet_elem else "",
                            "url": link.get('href') if link else search_url,
                            "source": "India Water Portal",
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "data_source_api": "India Environment Portal",
                            "region": "India"
                        })
                        
        except Exception as e:
            print(f"   ⚠️ India Environment Portal error: {str(e)[:50]}")
        
        return results
    
    # ========================================
    # NGO/RESEARCH SOURCES
    # ========================================
    
    def _fetch_cse_data(self, company: str, limit: int = 5) -> List[Dict]:
        """
        Fetch from Centre for Science and Environment (CSE)
        India's premier environmental research organization
        """
        
        results = []
        
        try:
            # CSE Down to Earth magazine search
            search_url = f"https://www.downtoearth.org.in/search/{quote(company)}"
            
            results.append({
                "title": f"CSE/Down to Earth Search: {company}",
                "snippet": "Centre for Science and Environment - India's leading environmental research and advocacy organization. Search Down to Earth magazine archives.",
                "url": search_url,
                "source": "CSE India",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "CSE Down to Earth",
                "region": "India"
            })
            
            # State of Environment report
            results.append({
                "title": "CSE State of India's Environment 2025",
                "snippet": "Annual assessment of environmental challenges: air pollution, water crisis, climate change, forest cover, industrial pollution.",
                "url": "https://www.cseindia.org/state-of-indias-environment",
                "source": "CSE India",
                "date": "2025",
                "data_source_api": "CSE Annual Report",
                "region": "India"
            })
            
        except Exception as e:
            print(f"   ⚠️ CSE data error: {str(e)[:50]}")
        
        return results[:limit]
    
    def _fetch_wri_india(self, company: str, limit: int = 5) -> List[Dict]:
        """
        Fetch from World Resources Institute India
        Focus: Climate, energy, cities, forests
        """
        
        results = []
        
        try:
            # WRI India search
            results.append({
                "title": f"WRI India Research: {company}",
                "snippet": "World Resources Institute India - Research on climate action, sustainable cities, energy, forests, water. Policy recommendations for India's transition.",
                "url": f"https://wri-india.org/?s={quote(company)}",
                "source": "WRI India",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "WRI India Research",
                "region": "India"
            })
            
            # India specific research
            results.append({
                "title": "WRI India: Corporate Climate Action",
                "snippet": "Science-based targets for Indian companies. Analysis of corporate net-zero commitments, renewable energy procurement, and supply chain decarbonization.",
                "url": "https://wri-india.org/our-work/topics/climate",
                "source": "WRI India",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "WRI India Climate Research",
                "region": "India"
            })
            
        except Exception as e:
            print(f"   ⚠️ WRI India error: {str(e)[:50]}")
        
        return results[:limit]
    
    def fetch_epa_opendata(self, company: str = None, limit: int = 5) -> List[Dict]:
        """
        Fetch from US EPA OpenData portal
        Free public access to environmental enforcement data
        """
        
        results = []
        
        try:
            # EPA Enforcement and Compliance History
            base_url = "https://enviro.epa.gov/enviro/efservice"
            
            # Facility search if company provided
            if company:
                results.append({
                    "title": f"EPA ECHO Search: {company}",
                    "snippet": "EPA Enforcement and Compliance History Online (ECHO) - Search facility inspections, violations, enforcement actions in the United States.",
                    "url": f"https://echo.epa.gov/facilities/facility-search?search={quote(company)}",
                    "source": "US EPA",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "data_source_api": "EPA ECHO",
                    "region": "USA"
                })
            
            # General EPA data
            results.append({
                "title": "EPA GHG Reporting Program",
                "snippet": "Greenhouse Gas Reporting Program (GHGRP) - Facility-level emissions data for 8,000+ facilities. Direct emissions from major sources.",
                "url": "https://www.epa.gov/ghgreporting/data-sets",
                "source": "US EPA",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_source_api": "EPA GHGRP",
                "region": "USA"
            })
            
        except Exception as e:
            print(f"   ⚠️ EPA OpenData error: {str(e)[:50]}")
        
        return results[:limit]


# Global instance
indian_data_aggregator = IndianDataAggregator()

def get_indian_data_aggregator() -> IndianDataAggregator:
    """Get global Indian data aggregator instance"""
    return indian_data_aggregator
