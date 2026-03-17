"""
Financial Analyst Agent - ESG & Financial Performance Correlation
Uses yfinance (free) to correlate financial health with ESG claims
Detects financial-ESG mismatches (e.g., "green" claims + rising fossil fuel revenue)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path
from core.llm_client import llm_client

# Try importing yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️ yfinance not installed. Run: pip install yfinance")


class FinancialAnalyst:
    """
    Analyzes company financial health and ESG-financial correlations
    Detects greenwashing through financial-claim mismatches
    """
    
    def __init__(self):
        self.name = "ESG-Financial Correlation Analyst"
        self.llm = llm_client
        
        # Stock symbol mappings (extend as needed)
        self.symbol_map = {
            "tesla": "TSLA",
            "apple": "AAPL",
            "microsoft": "MSFT",
            "amazon": "AMZN",
            "google": "GOOGL",
            "alphabet": "GOOGL",
            "meta": "META",
            "facebook": "META",
            "nvidia": "NVDA",
            "netflix": "NFLX",
            "coca-cola": "KO",
            "pepsi": "PEP",
            "walmart": "WMT",
            "exxon": "XOM",
            "chevron": "CVX",
            "bp": "BP",
            "shell": "SHEL",
            "totalenergies": "TTE",
            "conocophillips": "COP",
            "toyota": "TM",
            "volkswagen": "VWAGY",
            "ford": "F",
            "gm": "GM",
            "unilever": "UL",
            "nestle": "NSRGY",
            "nike": "NKE",
            "adidas": "ADDYY",
            "starbucks": "SBUX",
            "mcdonalds": "MCD",
            "jpmorgan": "JPM",
            "bank of america": "BAC",
            "goldman sachs": "GS",
            "wells fargo": "WFC",
            "pfizer": "PFE",
            "johnson & johnson": "JNJ",
            "moderna": "MRNA",
            "boeing": "BA",
            "lockheed martin": "LMT",
            "general electric": "GE",
            "siemens": "SIEGY",
            "basf": "BASFY",
            "dupont": "DD",
            "dow": "DOW"
        }

        aliases_path = Path(__file__).parent.parent / "config" / "company_aliases.json"
        self.company_aliases = {}
        if aliases_path.exists():
            try:
                self.company_aliases = json.loads(aliases_path.read_text(encoding="utf-8"))
            except Exception:
                self.company_aliases = {}
    
    def analyze_financial_esg_correlation(self, company: str, claim: str, 
                                          esg_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main analysis: Correlate financial metrics with ESG claims
        
        Args:
            company: Company name
            claim: ESG claim to verify
            esg_data: ESG metrics (carbon emissions, water usage, etc.)
        
        Returns:
            Financial analysis with greenwashing flags
        """
        
        print(f"\n{'='*60}")
        print(f"💰 AGENT 14: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        print(f"Claim: {claim[:80]}...")
        
        if not YFINANCE_AVAILABLE:
            print(f"❌ yfinance not installed - install with: pip install yfinance")
            return {
                "financial_data_available": False,
                "error": "yfinance not installed",
                "greenwashing_flags": []
            }
        
        # TEST MODE: Override with Microsoft for testing
        original_company = company
        test_mode = False
        if company.lower() in ["test", "microsoft"]:
            print(f"\n🧪 TEST MODE: Testing with Microsoft first...")
            company = "Microsoft"
            test_mode = True
        
        # Step 1: Get stock ticker
        ticker_symbol = self._get_ticker(company)
        if not ticker_symbol:
            print(f"❌ Could not find stock ticker for {company}")
            print(f"   Try adding to symbol_map or using exact ticker (e.g., MSFT)")
            return {
                "financial_data_available": False,
                "error": "Ticker not found",
                "greenwashing_flags": []
            }
        
        print(f"📈 Found ticker: {ticker_symbol}")
        
        # Step 2: Fetch financial data (with extensive debug logging)
        print(f"⏳ Fetching financial data from Yahoo Finance...")
        financial_data = self._fetch_financial_data(ticker_symbol)
        
        if not financial_data.get("data_available"):
            print(f"\n❌ FINAL FAILURE: Both Yahoo Finance and Alpha Vantage failed")
            print(f"   Error: {financial_data.get('error', 'Unknown')}")
            return financial_data

        if not financial_data.get("revenue_ttm"):
            return {
                "financial_data_available": False,
                "error": "Financial data unavailable - financial ESG context excluded.",
                "revenue": None,
                "profit_margin": None,
                "greenwashing_flags": []
            }
        
        print(f"\n✅ Financial data fetch SUCCESSFUL")
        print(f"   Source: {financial_data.get('data_source', 'Yahoo Finance')}")
        
        # Restore original company name
        if test_mode:
            company = original_company
        
        # Step 3: Calculate ESG-financial metrics
        print(f"\n📊 Calculating ESG-financial metrics...")
        esg_financial_metrics = self._calculate_esg_financial_metrics(
            financial_data, esg_data
        )
        
        # Step 4: Detect greenwashing patterns
        print(f"\n🔍 Analyzing financial-ESG mismatches...")
        greenwashing_flags = self._detect_financial_greenwashing(
            company, claim, financial_data, esg_data, esg_financial_metrics
        )
        
        # Step 5: Financial health assessment
        print(f"\n💼 Assessing overall financial health...")
        financial_health = self._assess_financial_health(financial_data)
        
        # Step 6: LLM-based synthesis
        print(f"\n🤖 Running AI financial-ESG correlation analysis...")
        llm_analysis = self._llm_financial_analysis(
            company, claim, financial_data, esg_data, greenwashing_flags
        )
        
        result = {
            "company": company,
            "ticker_symbol": ticker_symbol,
            "analysis_date": datetime.now().isoformat(),
            "financial_data_available": True,
            "financial_data": financial_data,
            "esg_financial_metrics": esg_financial_metrics,
            "financial_health_score": financial_health["score"],
            "financial_health_rating": financial_health["rating"],
            "greenwashing_flags": greenwashing_flags,
            "greenwashing_flag_count": len(greenwashing_flags),
            "llm_analysis": llm_analysis,
            "risk_adjustment": self._calculate_risk_adjustment(greenwashing_flags)
        }
        
        print(f"\n✅ Financial analysis complete:")
        print(f"   Financial Health: {financial_health['rating']} ({financial_health['score']}/100)")
        print(f"   Greenwashing Flags: {len(greenwashing_flags)}")
        print(f"   Risk Adjustment: {result['risk_adjustment']:+.1f}%")
        
        return result
    
    def _get_ticker(self, company: str) -> Optional[str]:
        """Get stock ticker from company name"""
        company_lower = company.lower().strip()

        # Config alias map takes precedence for edge cases (e.g., BP vs BP.L)
        for canonical, alias_data in self.company_aliases.items():
            aliases = [canonical] + (alias_data.get("aliases") or []) + [alias_data.get("full_name", "")]
            if any(a and a.lower() in company_lower for a in aliases):
                ticker = alias_data.get("ticker")
                if ticker:
                    return ticker
        
        # Direct match
        if company_lower in self.symbol_map:
            return self.symbol_map[company_lower]
        
        # Partial match
        for key, symbol in self.symbol_map.items():
            if key in company_lower or company_lower in key:
                return symbol
        
        # Try searching with yfinance (limited functionality)
        try:
            # Common suffixes
            search_terms = [
                company_lower,
                company_lower.split()[0],  # First word
                company_lower.replace(" ", "")
            ]
            
            for term in search_terms:
                try:
                    ticker = yf.Ticker(term.upper())
                    info = ticker.info
                    if info and info.get('symbol'):
                        return info['symbol']
                except:
                    continue
        except:
            pass
        
        return None
    
    def _fetch_financial_data(self, ticker_symbol: str) -> Dict[str, Any]:
        """Fetch financial data from Yahoo Finance with debug logging"""
        
        print(f"\n{'='*60}")
        print(f"🔍 DEBUG: Financial Data Fetch")
        print(f"{'='*60}")
        print(f"📌 Ticker Symbol: {ticker_symbol}")
        
        try:
            # Step 1: Yahoo Finance (Primary)
            print(f"\n[1] Attempting Yahoo Finance API for {ticker_symbol}...")
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            
            print(f"✅ Yahoo Finance Response Status: SUCCESS")
            print(f"📊 Info Keys Available: {len(info)} keys")
            print(f"📊 Key Fields Present: {list(info.keys())[:10]}...")
            
            # Debug revenue extraction
            revenue_raw = info.get("totalRevenue", 0)
            market_cap_raw = info.get("marketCap", 0)
            
            print(f"\n💰 Raw Financial Data:")
            print(f"   Total Revenue (raw): {revenue_raw}")
            print(f"   Market Cap (raw): {market_cap_raw}")
            print(f"   Profit Margin (raw): {info.get('profitMargins', 'N/A')}")
            print(f"   Sector: {info.get('sector', 'Unknown')}")
            
            if revenue_raw == 0 or revenue_raw is None:
                print(f"\n⚠️ WARNING: Revenue is 0 or None")
                revenue_keys = [k for k in info.keys() if 'revenue' in k.lower()]
                print(f"   Available revenue keys: {revenue_keys}")
            
            # Get quarterly financials
            quarterly_financials = ticker.quarterly_financials
            quarterly_balance = ticker.quarterly_balance_sheet
            
            print(f"\n📈 Quarterly Data:")
            print(f"   Financials Shape: {quarterly_financials.shape if quarterly_financials is not None and hasattr(quarterly_financials, 'shape') else 'None'}")
            print(f"   Balance Sheet Shape: {quarterly_balance.shape if quarterly_balance is not None and hasattr(quarterly_balance, 'shape') else 'None'}")
            
            # Extract key metrics
            data = {
                "data_available": True,
                "ticker": ticker_symbol,
                "data_source": "Yahoo Finance",
                
                # Core financials
                "market_cap": info.get("marketCap", 0),
                "revenue_ttm": info.get("totalRevenue", 0),  # Trailing 12 months
                "profit_margin": info.get("profitMargins", 0) * 100 if info.get("profitMargins") else 0,
                "operating_margin": info.get("operatingMargins", 0) * 100 if info.get("operatingMargins") else 0,
                
                # Balance sheet
                "total_debt": info.get("totalDebt", 0),
                "total_equity": info.get("totalStockholderEquity", 0),
                "debt_to_equity": info.get("debtToEquity", 0),
                "current_ratio": info.get("currentRatio", 0),
                
                # Growth & performance
                "revenue_growth": info.get("revenueGrowth", 0) * 100 if info.get("revenueGrowth") else 0,
                "earnings_growth": info.get("earningsGrowth", 0) * 100 if info.get("earningsGrowth") else 0,
                "beta": info.get("beta", 1.0),  # Stock volatility
                
                # ESG-relevant
                "esg_scores": info.get("esgScores", {}),
                "environment_score": info.get("environmentScore", None),
                "social_score": info.get("socialScore", None),
                "governance_score": info.get("governanceScore", None),
                
                # Industry
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                
                # Quarterly trends (if available)
                "quarterly_revenue_trend": self._extract_quarterly_trend(quarterly_financials, "Total Revenue"),
                "quarterly_earnings_trend": self._extract_quarterly_trend(quarterly_financials, "Net Income")
            }
            
            # Calculate derived metrics
            if data["total_equity"] > 0:
                data["debt_to_equity"] = data["total_debt"] / data["total_equity"]
            
            print(f"\n✅ Yahoo Finance Data Extraction Summary:")
            print(f"   Revenue (TTM): ${data['revenue_ttm']:,.0f}")
            print(f"   Profit Margin: {data['profit_margin']:.1f}%")
            print(f"   Debt/Equity: {data['debt_to_equity']:.2f}")
            print(f"   Beta: {data['beta']:.2f}")
            
            # Check if data is valid
            if data['revenue_ttm'] == 0 or data['revenue_ttm'] is None:
                print(f"\n❌ Financial data extraction FAILED - Revenue is 0")
                print(f"   Reason: Yahoo Finance returned no revenue data")
                print(f"   Available info dump (revenue-related): {json.dumps({k: v for k, v in info.items() if 'revenue' in k.lower() or 'total' in k.lower()}, indent=2, default=str)}")
                
                # Try Alpha Vantage fallback
                print(f"\n[2] Falling back to Alpha Vantage API...")
                alpha_data = self._fetch_alpha_vantage_fallback(ticker_symbol)
                if alpha_data.get("data_available"):
                    return alpha_data
            
            return data
            
        except Exception as e:
            print(f"\n❌ Yahoo Finance Error: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            
            # Try Alpha Vantage fallback
            print(f"\n[2] Falling back to Alpha Vantage API...")
            return self._fetch_alpha_vantage_fallback(ticker_symbol)
    
    def _fetch_alpha_vantage_fallback(self, ticker_symbol: str) -> Dict[str, Any]:
        """
        Fallback to Alpha Vantage API if Yahoo Finance fails
        """
        import os
        import requests
        
        api_key = os.getenv("ALPHA_VANTAGE_KEY", "")
        
        print(f"\n{'='*60}")
        print(f"🔍 DEBUG: Alpha Vantage Fallback")
        print(f"{'='*60}")
        print(f"📌 Ticker Symbol: {ticker_symbol}")
        
        if not api_key:
            print(f"❌ Alpha Vantage Key: NOT SET")
            return {
                "data_available": False,
                "error": "Alpha Vantage API key not configured",
                "ticker": ticker_symbol
            }
        
        print(f"✅ Alpha Vantage Key: {api_key[:5]}... (length: {len(api_key)})")
        
        try:
            # Function 1: Company Overview (includes revenue, profit margin, etc.)
            print(f"\n[Alpha Vantage] Attempting Company Overview...")
            url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker_symbol}&apikey={api_key}"
            
            response = requests.get(url, timeout=15)
            print(f"✅ API Response Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ HTTP Error: {response.status_code}")
                return {"data_available": False, "error": f"HTTP {response.status_code}"}
            
            data_json = response.json()
            print(f"📊 API Response Body (first 500 chars):")
            print(f"   {json.dumps(data_json, indent=2)[:500]}...")
            
            # Check for API limit error
            if "Note" in data_json or "Error Message" in data_json:
                print(f"❌ API Error: {data_json}")
                return {"data_available": False, "error": "Alpha Vantage rate limit or error"}
            
            # Extract revenue
            revenue_str = data_json.get("RevenueTTM", "0")
            revenue_value = float(revenue_str) if revenue_str and revenue_str != "None" else 0
            
            print(f"\n💰 Extracted Financial Data:")
            print(f"   Revenue (TTM): ${revenue_value:,.0f}")
            print(f"   Profit Margin: {data_json.get('ProfitMargin', 'N/A')}")
            print(f"   Market Cap: {data_json.get('MarketCapitalization', 'N/A')}")
            print(f"   Sector: {data_json.get('Sector', 'Unknown')}")
            
            if revenue_value == 0 or revenue_value is None:
                print(f"\n❌ Financial data extraction FAILED - check API response format")
                print(f"   All available keys: {list(data_json.keys())}")
                return {"data_available": False, "error": "No revenue data in Alpha Vantage response"}
            
            # Build data structure
            profit_margin_str = data_json.get("ProfitMargin", "0")
            profit_margin = float(profit_margin_str) * 100 if profit_margin_str and profit_margin_str != "None" else 0
            
            operating_margin_str = data_json.get("OperatingMarginTTM", "0")
            operating_margin = float(operating_margin_str) * 100 if operating_margin_str and operating_margin_str != "None" else 0
            
            revenue_growth_str = data_json.get("QuarterlyRevenueGrowthYOY", "0")
            revenue_growth = float(revenue_growth_str) * 100 if revenue_growth_str and revenue_growth_str != "None" else 0
            
            earnings_growth_str = data_json.get("QuarterlyEarningsGrowthYOY", "0")
            earnings_growth = float(earnings_growth_str) * 100 if earnings_growth_str and earnings_growth_str != "None" else 0
            
            beta_str = data_json.get("Beta", "1.0")
            beta = float(beta_str) if beta_str and beta_str != "None" else 1.0
            
            market_cap_str = data_json.get("MarketCapitalization", "0")
            market_cap = float(market_cap_str) if market_cap_str and market_cap_str != "None" else 0
            
            data = {
                "data_available": True,
                "ticker": ticker_symbol,
                "data_source": "Alpha Vantage (fallback)",
                
                # Core financials
                "market_cap": market_cap,
                "revenue_ttm": revenue_value,
                "profit_margin": profit_margin,
                "operating_margin": operating_margin,
                
                # Balance sheet (not available in overview)
                "total_debt": 0,
                "total_equity": 0,
                "debt_to_equity": 0,
                "current_ratio": 0,
                
                # Growth
                "revenue_growth": revenue_growth,
                "earnings_growth": earnings_growth,
                "beta": beta,
                
                # ESG (not available in Alpha Vantage)
                "esg_scores": {},
                "environment_score": None,
                "social_score": None,
                "governance_score": None,
                
                # Industry
                "sector": data_json.get("Sector", "Unknown"),
                "industry": data_json.get("Industry", "Unknown"),
                
                "quarterly_revenue_trend": [],
                "quarterly_earnings_trend": []
            }
            
            print(f"\n✅ Alpha Vantage Data Extraction SUCCESS")
            return data
            
        except Exception as e:
            print(f"\n❌ Alpha Vantage Error: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            
            return {
                "data_available": False,
                "error": str(e),
                "ticker": ticker_symbol
            }
    
    def _extract_quarterly_trend(self, df, metric_name: str) -> List[float]:
        """Extract quarterly trend from pandas DataFrame"""
        try:
            if df is not None and metric_name in df.index:
                values = df.loc[metric_name].dropna().tolist()
                return [float(v) for v in values[:4]]  # Last 4 quarters
        except:
            pass
        return []
    
    def _calculate_esg_financial_metrics(self, financial_data: Dict, 
                                         esg_data: Dict) -> Dict[str, Any]:
        """Calculate ESG-financial correlation metrics"""
        
        metrics = {}
        
        revenue = financial_data.get("revenue_ttm", 0)
        
        # 1. Carbon Intensity (emissions per dollar of revenue)
        carbon_emissions = esg_data.get("CarbonEmissions", 0)
        if revenue > 0 and carbon_emissions > 0:
            metrics["carbon_intensity"] = carbon_emissions / revenue
            metrics["carbon_intensity_display"] = f"{metrics['carbon_intensity']:.6f} tons/$"
        else:
            metrics["carbon_intensity"] = None
        
        # 2. Water Efficiency
        water_usage = esg_data.get("WaterUsage", 0)
        if revenue > 0 and water_usage > 0:
            metrics["water_efficiency"] = water_usage / revenue
            metrics["water_efficiency_display"] = f"{metrics['water_efficiency']:.6f} liters/$"
        else:
            metrics["water_efficiency"] = None
        
        # 3. Energy Efficiency
        energy_consumption = esg_data.get("EnergyConsumption", 0)
        if revenue > 0 and energy_consumption > 0:
            metrics["energy_efficiency"] = energy_consumption / revenue
            metrics["energy_efficiency_display"] = f"{metrics['energy_efficiency']:.6f} kWh/$"
        else:
            metrics["energy_efficiency"] = None
        
        # 4. Green Investment Ratio (approximation)
        # Note: R&D not always available, use operating expenses as proxy
        operating_margin = financial_data.get("operating_margin", 0)
        if operating_margin > 0:
            metrics["green_investment_potential"] = operating_margin / 100
        else:
            metrics["green_investment_potential"] = None
        
        # 5. Financial Stability vs ESG Commitment
        profit_margin = financial_data.get("profit_margin", 0)
        esg_score = esg_data.get("ESG_Overall", 50)
        
        if profit_margin > 0:
            # Companies with high margins should have resources for ESG
            metrics["affordability_index"] = profit_margin / 10  # Scale to 0-10
            
            # Flag: High profit + low ESG = potential greenwashing
            if profit_margin > 20 and esg_score < 50:
                metrics["high_profit_low_esg_flag"] = True
            else:
                metrics["high_profit_low_esg_flag"] = False
        
        print(f"   ESG-Financial Metrics:")
        if metrics.get("carbon_intensity"):
            print(f"      Carbon Intensity: {metrics['carbon_intensity_display']}")
        if metrics.get("water_efficiency"):
            print(f"      Water Efficiency: {metrics['water_efficiency_display']}")
        
        return metrics
    
    def _detect_financial_greenwashing(self, company: str, claim: str,
                                       financial_data: Dict, esg_data: Dict,
                                       esg_financial_metrics: Dict) -> List[Dict[str, str]]:
        """Detect greenwashing through financial-ESG mismatches"""
        
        flags = []
        claim_lower = claim.lower()
        
        # Get metrics
        revenue = financial_data.get("revenue_ttm", 0)
        revenue_growth = financial_data.get("revenue_growth", 0)
        profit_margin = financial_data.get("profit_margin", 0)
        sector = financial_data.get("sector", "").lower()
        
        # FLAG 1: "Carbon neutral" claim in fossil fuel sector with growing revenue
        if any(term in claim_lower for term in ["carbon neutral", "net zero", "zero emissions"]):
            if "energy" in sector or "oil" in sector or "gas" in sector:
                if revenue_growth > 5:
                    flags.append({
                        "flag_type": "fossil_fuel_growth",
                        "severity": "High",
                        "description": f"Claims carbon neutrality but fossil fuel revenue grew {revenue_growth:.1f}%",
                        "risk_increase": 25
                    })
        
        # FLAG 2: "Sustainable" claim but high carbon intensity
        if any(term in claim_lower for term in ["sustainable", "green", "eco-friendly"]):
            carbon_intensity = esg_financial_metrics.get("carbon_intensity")
            if carbon_intensity and carbon_intensity > 0.01:  # Threshold
                flags.append({
                    "flag_type": "high_carbon_intensity",
                    "severity": "Moderate",
                    "description": f"Sustainability claims despite high carbon intensity ({carbon_intensity:.6f} tons/$)",
                    "risk_increase": 15
                })
        
        # FLAG 3: High profit margin (>25%) but low ESG score (<50)
        esg_score = esg_data.get("ESG_Overall", 50)
        if profit_margin > 25 and esg_score < 50:
            flags.append({
                "flag_type": "high_profit_low_esg",
                "severity": "Moderate",
                "description": f"High profitability ({profit_margin:.1f}%) but low ESG score ({esg_score})",
                "risk_increase": 10
            })
        
        # FLAG 4: "Investment in renewables" but debt-heavy balance sheet
        if any(term in claim_lower for term in ["invest", "commitment", "transition"]):
            debt_to_equity = financial_data.get("debt_to_equity", 0)
            if debt_to_equity > 2.0:  # High leverage
                flags.append({
                    "flag_type": "financial_constraints",
                    "severity": "Low",
                    "description": f"ESG investment claims despite high debt (D/E: {debt_to_equity:.2f})",
                    "risk_increase": 8
                })
        
        # FLAG 5: Declining revenue but increasing ESG claims
        if revenue_growth < -5:  # Revenue declining
            if any(term in claim_lower for term in ["leader", "pioneering", "committed"]):
                flags.append({
                    "flag_type": "defensive_esg_claims",
                    "severity": "Moderate",
                    "description": f"Aggressive ESG claims during revenue decline ({revenue_growth:.1f}%)",
                    "risk_increase": 12
                })
        
        # FLAG 6: "Renewable energy" claim but no capital expenditure growth
        if any(term in claim_lower for term in ["renewable", "solar", "wind", "clean energy"]):
            # Check if revenue is flat/declining (no growth in green investments)
            if -2 < revenue_growth < 2:
                flags.append({
                    "flag_type": "stagnant_green_investment",
                    "severity": "Low",
                    "description": f"Renewable energy claims but flat revenue growth ({revenue_growth:.1f}%)",
                    "risk_increase": 5
                })
        
        # FLAG 7: High volatility (beta > 1.5) + aggressive ESG claims
        beta = financial_data.get("beta", 1.0)
        if beta > 1.5:
            if any(term in claim_lower for term in ["guaranteed", "achieve", "will"]):
                flags.append({
                    "flag_type": "high_risk_company",
                    "severity": "Low",
                    "description": f"Definitive ESG claims despite high stock volatility (beta: {beta:.2f})",
                    "risk_increase": 5
                })
        
        if flags:
            print(f"\n   ⚠️ DETECTED {len(flags)} FINANCIAL GREENWASHING FLAGS:")
            for flag in flags:
                print(f"      • {flag['severity']}: {flag['description']}")
        else:
            print(f"   ✅ No financial greenwashing patterns detected")
        
        return flags
    
    def _assess_financial_health(self, financial_data: Dict) -> Dict[str, Any]:
        """Calculate overall financial health score"""
        
        score = 50  # Start neutral
        
        # Profit margin (max 25 points)
        profit_margin = financial_data.get("profit_margin", 0)
        if profit_margin > 20:
            score += 25
        elif profit_margin > 10:
            score += 15
        elif profit_margin > 5:
            score += 10
        elif profit_margin < 0:
            score -= 15
        
        # Debt-to-equity (max 25 points)
        debt_to_equity = financial_data.get("debt_to_equity", 0)
        if debt_to_equity < 0.5:
            score += 25
        elif debt_to_equity < 1.0:
            score += 15
        elif debt_to_equity < 2.0:
            score += 5
        else:
            score -= 10
        
        # Revenue growth (max 20 points)
        revenue_growth = financial_data.get("revenue_growth", 0)
        if revenue_growth > 20:
            score += 20
        elif revenue_growth > 10:
            score += 15
        elif revenue_growth > 5:
            score += 10
        elif revenue_growth < -10:
            score -= 15
        
        # Current ratio (max 10 points)
        current_ratio = financial_data.get("current_ratio", 0)
        if current_ratio > 2.0:
            score += 10
        elif current_ratio > 1.5:
            score += 8
        elif current_ratio > 1.0:
            score += 5
        elif current_ratio < 0.8:
            score -= 10
        
        # Market cap stability (max 10 points)
        beta = financial_data.get("beta", 1.0)
        if beta < 0.8:
            score += 10
        elif beta < 1.2:
            score += 5
        elif beta > 1.8:
            score -= 5
        
        # Cap score
        score = max(0, min(100, score))
        
        # Rating
        if score >= 80:
            rating = "Excellent"
        elif score >= 65:
            rating = "Good"
        elif score >= 50:
            rating = "Fair"
        elif score >= 35:
            rating = "Poor"
        else:
            rating = "Very Poor"
        
        return {
            "score": score,
            "rating": rating,
            "components": {
                "profitability": profit_margin,
                "leverage": debt_to_equity,
                "growth": revenue_growth,
                "liquidity": current_ratio,
                "stability": beta
            }
        }
    
    def _calculate_risk_adjustment(self, flags: List[Dict]) -> float:
        """Calculate risk adjustment from financial flags"""
        if not flags:
            return 0.0
        
        total_increase = sum(flag.get("risk_increase", 0) for flag in flags)
        return min(30.0, total_increase)  # Cap at 30% increase
    
    def _llm_financial_analysis(self, company: str, claim: str,
                                financial_data: Dict, esg_data: Dict,
                                flags: List[Dict]) -> Dict[str, Any]:
        """Use LLM to synthesize financial-ESG analysis"""
        
        prompt = f"""You are a financial analyst specializing in ESG-financial correlations.

COMPANY: {company}
ESG CLAIM: {claim}

FINANCIAL DATA:
- Revenue: ${financial_data.get('revenue_ttm', 0):,.0f}
- Profit Margin: {financial_data.get('profit_margin', 0):.1f}%
- Revenue Growth: {financial_data.get('revenue_growth', 0):.1f}%
- Debt/Equity: {financial_data.get('debt_to_equity', 0):.2f}
- Sector: {financial_data.get('sector', 'Unknown')}

ESG SCORE: {esg_data.get('ESG_Overall', 'N/A')}

DETECTED FLAGS: {len(flags)} financial greenwashing indicators

Analyze:
1. Does the financial profile support the ESG claim?
2. Are there red flags (e.g., fossil fuel revenue growth + carbon neutral claims)?
3. Financial affordability of ESG commitments
4. Overall credibility assessment

Return ONLY valid JSON:
{{
  "financial_esg_alignment": "High/Moderate/Low",
  "affordability_assessment": "[Can they afford ESG investments?]",
  "credibility_impact": "Positive/Neutral/Negative",
  "key_insight": "[One sentence summary]"
}}"""

        try:
            response = self.llm.call_with_fallback(prompt, use_gemini_first=False)
            
            if response:
                # Extract JSON
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            print(f"   ⚠️ LLM analysis failed: {e}")
        
        # Fallback
        return {
            "financial_esg_alignment": "Moderate",
            "affordability_assessment": "Unable to assess",
            "credibility_impact": "Neutral",
            "key_insight": "Financial data available but detailed analysis unavailable"
        }


# ============================================================================
# INTEGRATION FUNCTION FOR evidence_retriever.py
# ============================================================================

def get_financial_context(company: str, claim: str, esg_data: Dict) -> Dict[str, Any]:
    """
    Quick wrapper for evidence_retriever.py integration
    
    Usage in evidence_retriever.py:
        from agents.financial_analyst import get_financial_context
        financial_context = get_financial_context(company, claim, esg_data)
    """
    
    analyst = FinancialAnalyst()
    return analyst.analyze_financial_esg_correlation(company, claim, esg_data)
