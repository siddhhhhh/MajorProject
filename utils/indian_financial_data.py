"""
Indian Financial Data Sources
Fetches revenue, profit, and financial metrics for Indian companies.

Sources:
- Screener.in (free, no API key needed)
- MoneyControl (web scraping)
- BSE/NSE Official APIs
- Yahoo Finance India
- Google Finance
- Financial Express
"""

import os
import re
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import hashlib
import time

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


class IndianFinancialData:
    """
    Fetches financial data (revenue, profit, ratios) for Indian companies.
    Uses free publicly available sources.
    """
    
    def __init__(self):
        self.cache_dir = Path("cache/financial_data")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/html, */*',
        })
        
        # Company name to BSE/NSE code mapping (expandable)
        self.company_codes = {
            # Nifty 50 companies
            "reliance industries": {"bse": "500325", "nse": "RELIANCE", "screener": "reliance-industries"},
            "tata consultancy": {"bse": "532540", "nse": "TCS", "screener": "tcs"},
            "infosys": {"bse": "500209", "nse": "INFY", "screener": "infosys"},
            "hdfc bank": {"bse": "500180", "nse": "HDFCBANK", "screener": "hdfc-bank"},
            "icici bank": {"bse": "532174", "nse": "ICICIBANK", "screener": "icici-bank"},
            "hindustan unilever": {"bse": "500696", "nse": "HINDUNILVR", "screener": "hindustan-unilever"},
            "itc": {"bse": "500875", "nse": "ITC", "screener": "itc"},
            "state bank": {"bse": "500112", "nse": "SBIN", "screener": "state-bank-of-india"},
            "bharti airtel": {"bse": "532454", "nse": "BHARTIARTL", "screener": "bharti-airtel"},
            "kotak bank": {"bse": "500247", "nse": "KOTAKBANK", "screener": "kotak-mahindra-bank"},
            "larsen toubro": {"bse": "500510", "nse": "LT", "screener": "larsen-and-toubro"},
            "asian paints": {"bse": "500820", "nse": "ASIANPAINT", "screener": "asian-paints"},
            "axis bank": {"bse": "532215", "nse": "AXISBANK", "screener": "axis-bank"},
            "maruti suzuki": {"bse": "532500", "nse": "MARUTI", "screener": "maruti-suzuki-india"},
            "wipro": {"bse": "507685", "nse": "WIPRO", "screener": "wipro"},
            "hcl tech": {"bse": "532281", "nse": "HCLTECH", "screener": "hcl-technologies"},
            "tata motors": {"bse": "500570", "nse": "TATAMOTORS", "screener": "tata-motors-ltd"},
            "tata steel": {"bse": "500470", "nse": "TATASTEEL", "screener": "tata-steel"},
            "sun pharma": {"bse": "524715", "nse": "SUNPHARMA", "screener": "sun-pharma"},
            "bajaj finance": {"bse": "500034", "nse": "BAJFINANCE", "screener": "bajaj-finance"},
            "titan": {"bse": "500114", "nse": "TITAN", "screener": "titan-company"},
            "nestle india": {"bse": "500790", "nse": "NESTLEIND", "screener": "nestle-india"},
            "ultratech cement": {"bse": "532538", "nse": "ULTRACEMCO", "screener": "ultratech-cement"},
            "power grid": {"bse": "532898", "nse": "POWERGRID", "screener": "power-grid-corp"},
            "ntpc": {"bse": "532555", "nse": "NTPC", "screener": "ntpc"},
            "ongc": {"bse": "500312", "nse": "ONGC", "screener": "oil-and-natural-gas-corp"},
            "coal india": {"bse": "533278", "nse": "COALINDIA", "screener": "coal-india"},
            "adani enterprises": {"bse": "512599", "nse": "ADANIENT", "screener": "adani-enterprises"},
            "adani ports": {"bse": "532921", "nse": "ADANIPORTS", "screener": "adani-ports-special-eco"},
            "adani green": {"bse": "541450", "nse": "ADANIGREEN", "screener": "adani-green-energy"},
            "jsw steel": {"bse": "500228", "nse": "JSWSTEEL", "screener": "jsw-steel"},
            "vedanta": {"bse": "500295", "nse": "VEDL", "screener": "vedanta"},
            "hindalco": {"bse": "500440", "nse": "HINDALCO", "screener": "hindalco-industries"},
            "grasim": {"bse": "500300", "nse": "GRASIM", "screener": "grasim-industries"},
            "tech mahindra": {"bse": "532755", "nse": "TECHM", "screener": "tech-mahindra"},
            "mahindra mahindra": {"bse": "500520", "nse": "M&M", "screener": "mahindra-mahindra"},
            "bajaj auto": {"bse": "532977", "nse": "BAJAJ-AUTO", "screener": "bajaj-auto"},
            "hero motocorp": {"bse": "500182", "nse": "HEROMOTOCO", "screener": "hero-motocorp"},
            "eicher motors": {"bse": "505200", "nse": "EICHERMOT", "screener": "eicher-motors"},
            "dr reddy": {"bse": "500124", "nse": "DRREDDY", "screener": "dr-reddys-laboratories"},
            "cipla": {"bse": "500087", "nse": "CIPLA", "screener": "cipla"},
            "divis lab": {"bse": "532488", "nse": "DIVISLAB", "screener": "divis-laboratories"},
            "britannia": {"bse": "500825", "nse": "BRITANNIA", "screener": "britannia-industries"},
            "indusind bank": {"bse": "532187", "nse": "INDUSINDBK", "screener": "indusind-bank"},
            "sbi life": {"bse": "540719", "nse": "SBILIFE", "screener": "sbi-life-insurance-company"},
            "hdfc life": {"bse": "540777", "nse": "HDFCLIFE", "screener": "hdfc-life-insurance-company"},
            "bajaj finserv": {"bse": "532978", "nse": "BAJAJFINSV", "screener": "bajaj-finserv"},
            "indian oil": {"bse": "530965", "nse": "IOC", "screener": "indian-oil-corp"},
            "bharat petroleum": {"bse": "500547", "nse": "BPCL", "screener": "bharat-petroleum-corp"},
            "gail": {"bse": "532155", "nse": "GAIL", "screener": "gail-india"},
        }
        
        print("✅ Indian Financial Data initialized")
        print(f"   • {len(self.company_codes)} companies in database")
        print("   • Sources: Screener.in, Yahoo Finance, MoneyControl")
    
    def get_company_financials(self, company_name: str) -> Dict:
        """
        Get comprehensive financial data for an Indian company.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Dictionary with revenue, profit, ratios, and growth metrics
        """
        print(f"\n💰 Fetching financials for: {company_name}")
        
        result = {
            "company": company_name,
            "timestamp": datetime.now().isoformat(),
            "currency": "INR",
            "unit": "Crore",
            "financials": {},
            "ratios": {},
            "growth": {},
            "sources": [],
            "errors": []
        }
        
        # Get company codes
        codes = self._get_company_codes(company_name)
        
        # Try multiple sources
        # 1. Screener.in (best for Indian companies)
        screener_data = self._fetch_screener(company_name, codes)
        if screener_data:
            result["financials"].update(screener_data.get("financials", {}))
            result["ratios"].update(screener_data.get("ratios", {}))
            result["growth"].update(screener_data.get("growth", {}))
            result["sources"].append("Screener.in")
        
        # 2. Yahoo Finance
        yahoo_data = self._fetch_yahoo_finance(company_name, codes)
        if yahoo_data:
            # Merge without overwriting
            for key, value in yahoo_data.get("financials", {}).items():
                if key not in result["financials"]:
                    result["financials"][key] = value
            result["sources"].append("Yahoo Finance")
        
        # 3. MoneyControl
        mc_data = self._fetch_moneycontrol(company_name, codes)
        if mc_data:
            for key, value in mc_data.get("financials", {}).items():
                if key not in result["financials"]:
                    result["financials"][key] = value
            result["sources"].append("MoneyControl")
        
        # 4. NSE/BSE Official
        nse_data = self._fetch_nse_data(company_name, codes)
        if nse_data:
            result["financials"].update(nse_data)
            result["sources"].append("NSE India")
        
        # Calculate derived metrics
        result = self._calculate_derived_metrics(result)
        
        # Cache the result
        self._cache_result(company_name, result)
        
        print(f"   ✅ Fetched from {len(result['sources'])} sources")
        return result
    
    def _get_company_codes(self, company_name: str) -> Dict:
        """Get BSE/NSE codes for company"""
        company_lower = company_name.lower()
        
        for key, codes in self.company_codes.items():
            if key in company_lower or company_lower in key:
                return codes
        
        # Try to find partial match
        for key, codes in self.company_codes.items():
            key_words = key.split()
            if any(word in company_lower for word in key_words if len(word) > 3):
                return codes
        
        return {}
    
    def _fetch_screener(self, company_name: str, codes: Dict) -> Optional[Dict]:
        """Fetch data from Screener.in (free, no API key)"""
        
        if not BS4_AVAILABLE:
            return None
        
        screener_slug = codes.get("screener", "")
        if not screener_slug:
            # Try to construct slug from name
            screener_slug = company_name.lower().replace(" ", "-").replace(".", "")
        
        try:
            url = f"https://www.screener.in/company/{screener_slug}/"
            
            # Check cache first
            cache_key = hashlib.md5(url.encode()).hexdigest()[:16]
            cache_file = self.cache_dir / f"screener_{cache_key}.json"
            
            if cache_file.exists():
                cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                if cache_age < timedelta(hours=24):
                    with open(cache_file, 'r') as f:
                        return json.load(f)
            
            print(f"   📊 Fetching from Screener.in...")
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            result = {
                "financials": {},
                "ratios": {},
                "growth": {}
            }
            
            # Extract key ratios from the top section
            ratio_list = soup.find('ul', {'id': 'top-ratios'})
            if ratio_list:
                for li in ratio_list.find_all('li'):
                    name = li.find('span', class_='name')
                    value = li.find('span', class_='value')
                    if name and value:
                        name_text = name.get_text(strip=True)
                        value_text = value.get_text(strip=True)
                        
                        # Parse value
                        parsed_value = self._parse_value(value_text)
                        
                        if 'Market Cap' in name_text:
                            result["financials"]["market_cap"] = parsed_value
                        elif 'Current Price' in name_text:
                            result["financials"]["current_price"] = parsed_value
                        elif 'Stock P/E' in name_text:
                            result["ratios"]["pe_ratio"] = parsed_value
                        elif 'Book Value' in name_text:
                            result["ratios"]["book_value"] = parsed_value
                        elif 'ROCE' in name_text:
                            result["ratios"]["roce"] = parsed_value
                        elif 'ROE' in name_text:
                            result["ratios"]["roe"] = parsed_value
                        elif 'Face Value' in name_text:
                            result["financials"]["face_value"] = parsed_value
                        elif 'Dividend Yield' in name_text:
                            result["ratios"]["dividend_yield"] = parsed_value
            
            # Extract quarterly results table
            quarters_section = soup.find('section', {'id': 'quarters'})
            if quarters_section:
                table = quarters_section.find('table')
                if table:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['th', 'td'])
                        if len(cells) >= 2:
                            metric = cells[0].get_text(strip=True)
                            latest_value = cells[-1].get_text(strip=True) if len(cells) > 1 else ""
                            
                            parsed = self._parse_value(latest_value)
                            
                            if 'Sales' in metric or 'Revenue' in metric:
                                result["financials"]["revenue_quarterly"] = parsed
                            elif 'Net Profit' in metric:
                                result["financials"]["net_profit_quarterly"] = parsed
                            elif 'OPM' in metric:
                                result["ratios"]["operating_margin"] = parsed
            
            # Extract annual P&L
            profit_loss = soup.find('section', {'id': 'profit-loss'})
            if profit_loss:
                table = profit_loss.find('table')
                if table:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['th', 'td'])
                        if len(cells) >= 2:
                            metric = cells[0].get_text(strip=True)
                            latest_value = cells[-1].get_text(strip=True) if len(cells) > 1 else ""
                            
                            parsed = self._parse_value(latest_value)
                            
                            if 'Sales' in metric:
                                result["financials"]["revenue_annual"] = parsed
                            elif 'Net Profit' in metric and 'OPM' not in metric:
                                result["financials"]["net_profit_annual"] = parsed
                            elif 'Operating Profit' in metric:
                                result["financials"]["operating_profit"] = parsed
                            elif 'EPS' in metric:
                                result["financials"]["eps"] = parsed
            
            # Extract growth percentages
            for section in soup.find_all('section'):
                text = section.get_text()
                
                # Look for compounded growth rates
                cagr_match = re.search(r'Sales\s+growth.*?(\d+(?:\.\d+)?)\s*%', text, re.IGNORECASE)
                if cagr_match:
                    result["growth"]["revenue_cagr"] = float(cagr_match.group(1))
                
                profit_growth = re.search(r'Profit\s+growth.*?(\d+(?:\.\d+)?)\s*%', text, re.IGNORECASE)
                if profit_growth:
                    result["growth"]["profit_cagr"] = float(profit_growth.group(1))
            
            # Cache result
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            return result
            
        except Exception as e:
            print(f"   ⚠️ Screener.in error: {e}")
            return None
    
    def _fetch_yahoo_finance(self, company_name: str, codes: Dict) -> Optional[Dict]:
        """Fetch data from Yahoo Finance"""
        
        nse_code = codes.get("nse", "")
        if not nse_code:
            return None
        
        try:
            # Yahoo Finance uses .NS suffix for NSE stocks
            symbol = f"{nse_code}.NS"
            
            # Try Yahoo Finance API
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
            params = {
                "modules": "financialData,defaultKeyStatistics,summaryDetail"
            }
            
            print(f"   📈 Fetching from Yahoo Finance...")
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            result = {
                "financials": {},
                "ratios": {}
            }
            
            quote_summary = data.get("quoteSummary", {}).get("result", [{}])[0]
            
            # Financial data
            financial_data = quote_summary.get("financialData", {})
            if financial_data:
                result["financials"]["total_revenue"] = financial_data.get("totalRevenue", {}).get("raw")
                result["financials"]["revenue_growth"] = financial_data.get("revenueGrowth", {}).get("raw")
                result["financials"]["gross_profit"] = financial_data.get("grossProfits", {}).get("raw")
                result["financials"]["ebitda"] = financial_data.get("ebitda", {}).get("raw")
                result["financials"]["operating_margin"] = financial_data.get("operatingMargins", {}).get("raw")
                result["ratios"]["profit_margin"] = financial_data.get("profitMargins", {}).get("raw")
                result["ratios"]["roe"] = financial_data.get("returnOnEquity", {}).get("raw")
                result["ratios"]["roa"] = financial_data.get("returnOnAssets", {}).get("raw")
            
            # Key statistics
            key_stats = quote_summary.get("defaultKeyStatistics", {})
            if key_stats:
                result["financials"]["enterprise_value"] = key_stats.get("enterpriseValue", {}).get("raw")
                result["ratios"]["pe_forward"] = key_stats.get("forwardPE", {}).get("raw")
                result["ratios"]["pe_trailing"] = key_stats.get("trailingPE", {}).get("raw")
                result["ratios"]["peg_ratio"] = key_stats.get("pegRatio", {}).get("raw")
                result["ratios"]["price_to_book"] = key_stats.get("priceToBook", {}).get("raw")
            
            # Summary detail
            summary = quote_summary.get("summaryDetail", {})
            if summary:
                result["financials"]["market_cap"] = summary.get("marketCap", {}).get("raw")
                result["ratios"]["dividend_yield"] = summary.get("dividendYield", {}).get("raw")
                result["ratios"]["beta"] = summary.get("beta", {}).get("raw")
            
            # Clean None values
            result["financials"] = {k: v for k, v in result["financials"].items() if v is not None}
            result["ratios"] = {k: v for k, v in result["ratios"].items() if v is not None}
            
            return result
            
        except Exception as e:
            print(f"   ⚠️ Yahoo Finance error: {e}")
            return None
    
    def _fetch_moneycontrol(self, company_name: str, codes: Dict) -> Optional[Dict]:
        """Fetch data from MoneyControl"""
        
        if not BS4_AVAILABLE:
            return None
        
        bse_code = codes.get("bse", "")
        if not bse_code:
            return None
        
        try:
            # MoneyControl search
            search_url = f"https://www.moneycontrol.com/stocks/cptmarket/compsearchnew.php?search_data={bse_code}"
            
            print(f"   💹 Fetching from MoneyControl...")
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            result = {
                "financials": {}
            }
            
            # Look for financial tables
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[-1].get_text(strip=True)
                        
                        parsed = self._parse_value(value)
                        
                        if 'revenue' in label or 'sales' in label:
                            result["financials"]["revenue"] = parsed
                        elif 'net profit' in label:
                            result["financials"]["net_profit"] = parsed
                        elif 'total assets' in label:
                            result["financials"]["total_assets"] = parsed
            
            return result if result["financials"] else None
            
        except Exception as e:
            print(f"   ⚠️ MoneyControl error: {e}")
            return None
    
    def _fetch_nse_data(self, company_name: str, codes: Dict) -> Optional[Dict]:
        """Fetch data from NSE India official API"""
        
        nse_code = codes.get("nse", "")
        if not nse_code:
            return None
        
        try:
            # NSE requires specific headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.nseindia.com/'
            }
            
            # First get cookies
            self.session.get("https://www.nseindia.com/", headers=headers, timeout=10)
            
            # Then fetch quote
            url = f"https://www.nseindia.com/api/quote-equity?symbol={nse_code}"
            
            print(f"   🏛️ Fetching from NSE India...")
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            result = {}
            
            price_info = data.get("priceInfo", {})
            if price_info:
                result["current_price"] = price_info.get("lastPrice")
                result["change_percent"] = price_info.get("pChange")
                result["52w_high"] = price_info.get("weekHighLow", {}).get("max")
                result["52w_low"] = price_info.get("weekHighLow", {}).get("min")
            
            security_info = data.get("securityInfo", {})
            if security_info:
                result["face_value"] = security_info.get("faceValue")
                result["issued_size"] = security_info.get("issuedSize")
            
            return result if result else None
            
        except Exception as e:
            print(f"   ⚠️ NSE error: {e}")
            return None
    
    def _parse_value(self, value_str: str) -> Optional[float]:
        """Parse financial value string to number"""
        if not value_str:
            return None
        
        # Remove currency symbols and clean
        value_str = re.sub(r'[₹$€£,]', '', value_str.strip())
        
        # Handle Cr, Lakh, etc.
        multiplier = 1
        value_lower = value_str.lower()
        
        if 'cr' in value_lower:
            multiplier = 1  # Already in crores
            value_str = re.sub(r'cr\.?', '', value_str, flags=re.IGNORECASE)
        elif 'lakh' in value_lower or 'lac' in value_lower:
            multiplier = 0.01  # Convert to crores
            value_str = re.sub(r'lakh|lac', '', value_str, flags=re.IGNORECASE)
        elif 'billion' in value_lower or 'bn' in value_lower:
            multiplier = 8300  # Approx USD billion to INR crore
            value_str = re.sub(r'billion|bn', '', value_str, flags=re.IGNORECASE)
        elif 'million' in value_lower or 'mn' in value_lower:
            multiplier = 8.3  # Approx USD million to INR crore
            value_str = re.sub(r'million|mn', '', value_str, flags=re.IGNORECASE)
        
        # Handle percentages
        is_percentage = '%' in value_str
        value_str = value_str.replace('%', '').strip()
        
        try:
            value = float(value_str)
            if not is_percentage:
                value *= multiplier
            return value
        except:
            return None
    
    def _calculate_derived_metrics(self, result: Dict) -> Dict:
        """Calculate additional metrics from available data"""
        
        financials = result.get("financials", {})
        ratios = result.get("ratios", {})
        
        # Calculate PE if we have price and EPS
        if financials.get("current_price") and financials.get("eps"):
            if "pe_ratio" not in ratios:
                ratios["pe_ratio"] = financials["current_price"] / financials["eps"]
        
        # Calculate market cap from price and shares
        if financials.get("current_price") and financials.get("issued_size"):
            if "market_cap" not in financials:
                financials["market_cap"] = financials["current_price"] * financials["issued_size"] / 10000000  # In crores
        
        # Identify primary revenue figure
        if "revenue_annual" in financials:
            financials["revenue"] = financials["revenue_annual"]
        elif "total_revenue" in financials:
            # Convert from raw (likely in actual currency) to crores
            financials["revenue"] = financials["total_revenue"] / 10000000
        
        # Primary profit figure
        if "net_profit_annual" in financials:
            financials["net_profit"] = financials["net_profit_annual"]
        
        result["financials"] = financials
        result["ratios"] = ratios
        
        return result
    
    def _cache_result(self, company_name: str, result: Dict):
        """Cache financial data"""
        cache_key = hashlib.md5(company_name.lower().encode()).hexdigest()[:16]
        cache_file = self.cache_dir / f"financial_{cache_key}.json"
        
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
    
    def get_revenue(self, company_name: str) -> Optional[float]:
        """Quick method to get just the revenue in Crores"""
        data = self.get_company_financials(company_name)
        return data.get("financials", {}).get("revenue")
    
    def get_profit(self, company_name: str) -> Optional[float]:
        """Quick method to get just the net profit in Crores"""
        data = self.get_company_financials(company_name)
        return data.get("financials", {}).get("net_profit")
    
    def get_market_cap(self, company_name: str) -> Optional[float]:
        """Quick method to get market cap in Crores"""
        data = self.get_company_financials(company_name)
        return data.get("financials", {}).get("market_cap")


# Singleton instance
_financial_data = None

def get_indian_financial_data() -> IndianFinancialData:
    """Get singleton instance of IndianFinancialData"""
    global _financial_data
    if _financial_data is None:
        _financial_data = IndianFinancialData()
    return _financial_data


if __name__ == "__main__":
    # Test
    fin = IndianFinancialData()
    
    # Test with Reliance
    data = fin.get_company_financials("Reliance Industries")
    print(f"\nReliance Industries Financials:")
    print(json.dumps(data, indent=2, default=str))
    
    # Quick revenue
    revenue = fin.get_revenue("TCS")
    print(f"\nTCS Revenue: ₹{revenue:,.0f} Crore" if revenue else "TCS Revenue: Not found")
