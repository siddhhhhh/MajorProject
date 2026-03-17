"""
Company Report Fetcher
Automatically fetches company reports (Annual Reports, Sustainability Reports, BRSR) 
from official websites and extracts key ESG information.

Features:
- Auto-discovers company investor relations pages
- Downloads PDF reports (Annual, Sustainability, BRSR, CSR)
- Extracts text and tables from PDFs
- Caches reports locally for reuse
- Indian company focus with global support
"""

import os
import re
import json
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from urllib.parse import urljoin, urlparse
import time

# PDF parsing
try:
    import pdfplumber
    PDF_PLUMBER_AVAILABLE = True
except ImportError:
    PDF_PLUMBER_AVAILABLE = False
    print("⚠️  pdfplumber not installed. Install with: pip install pdfplumber")

try:
    from pypdf import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("⚠️  BeautifulSoup not installed. Install with: pip install beautifulsoup4")


class CompanyReportFetcher:
    """
    Fetches and parses company reports from official websites.
    Supports Indian and global companies.
    """
    
    def __init__(self):
        self.cache_dir = Path("cache/company_reports")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        
        # Known company investor relations URLs (expandable)
        self.known_ir_urls = {
            # Indian Companies
            "reliance industries": "https://www.ril.com/InvestorRelations/FinancialReporting.aspx",
            "tata steel": "https://www.tatasteel.com/investors/annual-report/",
            "tata consultancy": "https://www.tcs.com/investor-relations",
            "infosys": "https://www.infosys.com/investors/reports-filings.html",
            "wipro": "https://www.wipro.com/investors/annual-reports/",
            "hdfc bank": "https://www.hdfcbank.com/personal/about-us/investor-relations/annual-reports",
            "icici bank": "https://www.icicibank.com/aboutus/annual-reports",
            "state bank": "https://www.sbi.co.in/web/corporate-governance/annual-report",
            "bharti airtel": "https://www.airtel.in/about-bharti/investor-relations",
            "itc": "https://www.itcportal.com/about-itc/shareholder-value/annual-reports.aspx",
            "hindustan unilever": "https://www.hul.co.in/investor-relations/annual-reports/",
            "larsen & toubro": "https://investors.larsentoubro.com/AnnualReports.aspx",
            "adani": "https://www.adani.com/investors",
            "mahindra": "https://www.mahindra.com/investors/annual-reports",
            "bajaj": "https://www.bajajfinserv.in/investor-relations",
            "jsw steel": "https://www.jsw.in/investors/steel",
            "vedanta": "https://www.vedantalimited.com/investor-centre/results-reports",
            "coal india": "https://www.coalindia.in/investor-corner/annual-reports/",
            "ongc": "https://www.ongcindia.com/wps/wcm/connect/en/investors/annual-reports",
            "ntpc": "https://www.ntpc.co.in/en/investors/annual-reports",
            "power grid": "https://www.powergrid.in/investors/annual-reports",
            "gail": "https://www.gailonline.com/InvestorRelation.html",
            "indian oil": "https://iocl.com/pages/annual-reports",
            "bharat petroleum": "https://www.bharatpetroleum.in/investors/annual-reports.aspx",
            "hindalco": "https://www.hindalco.com/investors/annual-reports",
            "ultratech cement": "https://www.ultratechcement.com/investors/annual-reports",
            "asian paints": "https://www.asianpaints.com/more/investor/annual-reports.html",
            "titan": "https://www.titan.co.in/investor-relations",
            "nestle india": "https://www.nestle.in/investors/annual-reports",
            "maruti suzuki": "https://www.marutisuzuki.com/corporate/investors/company-reports",
            
            # Global Companies
            "microsoft": "https://www.microsoft.com/en-us/investor/annual-reports.aspx",
            "apple": "https://investor.apple.com/sec-filings/default.aspx",
            "google": "https://abc.xyz/investor/",
            "alphabet": "https://abc.xyz/investor/",
            "amazon": "https://ir.aboutamazon.com/annual-reports-proxies-and-shareholder-letters/default.aspx",
            "tesla": "https://ir.tesla.com/sec-filings",
            "meta": "https://investor.fb.com/financials/sec-filings/default.aspx",
            "exxonmobil": "https://corporate.exxonmobil.com/investors/investor-relations",
            "shell": "https://www.shell.com/investors/financial-reporting/annual-publications.html",
            "bp": "https://www.bp.com/en/global/corporate/investors/results-and-reporting.html",
            "chevron": "https://www.chevron.com/investors/financial-information/annual-reports",
            "coca-cola": "https://investors.coca-colacompany.com/filings-reports/annual-filings-10-k",
            "pepsi": "https://investor.pepsico.com/investors/financial-information/annual-reports",
            "unilever": "https://www.unilever.com/investors/annual-report-and-accounts/",
            "nestle": "https://www.nestle.com/investors/publications",
            "walmart": "https://stock.walmart.com/financials/annual-reports/default.aspx",
            "jpmorgan": "https://www.jpmorganchase.com/ir/annual-report",
            "bank of america": "https://investor.bankofamerica.com/financial-information/annual-reports",
        }
        
        # Report type patterns
        self.report_patterns = {
            "annual_report": [
                r"annual.?report", r"integrated.?report", r"ar.?\d{4}", 
                r"\d{4}.?annual", r"yearly.?report"
            ],
            "sustainability_report": [
                r"sustainab", r"esg.?report", r"csr.?report", r"corporate.?social",
                r"environmental.?report", r"climate.?report", r"green.?report"
            ],
            "brsr_report": [
                r"brsr", r"business.?responsibility", r"sustainability.?reporting",
                r"sebi.?brsr"
            ],
            "financial_report": [
                r"financial.?statement", r"quarterly.?report", r"q\d.?\d{4}",
                r"earnings", r"10-k", r"10-q", r"20-f"
            ]
        }
        
        print("✅ Company Report Fetcher initialized")
        print(f"   • {len(self.known_ir_urls)} companies in database")
        print(f"   • PDF parsing: {'pdfplumber' if PDF_PLUMBER_AVAILABLE else 'PyPDF2' if PYPDF2_AVAILABLE else 'Not available'}")
    
    def fetch_company_reports(self, company_name: str, report_types: List[str] = None,
                              max_reports: int = 5) -> Dict:
        """
        Fetch company reports from official website.
        
        Args:
            company_name: Company name to search for
            report_types: List of report types to fetch ['annual_report', 'sustainability_report', 'brsr_report']
            max_reports: Maximum number of reports to download
            
        Returns:
            Dictionary with report metadata and extracted content
        """
        if report_types is None:
            report_types = ["annual_report", "sustainability_report", "brsr_report"]
        
        print(f"\n📄 Fetching reports for: {company_name}")
        
        result = {
            "company": company_name,
            "timestamp": datetime.now().isoformat(),
            "reports_found": [],
            "extracted_data": {},
            "errors": []
        }
        
        # Step 1: Find investor relations page
        ir_url = self._find_investor_relations_page(company_name)
        if not ir_url:
            result["errors"].append("Could not find investor relations page")
            # Try alternative search
            ir_url = self._search_for_ir_page(company_name)
        
        if ir_url:
            print(f"   📍 Found IR page: {ir_url}")
            
            # Step 2: Scrape for PDF links
            pdf_links = self._scrape_pdf_links(ir_url, company_name)
            print(f"   📎 Found {len(pdf_links)} PDF links")
            
            # Step 3: Filter by report type
            categorized = self._categorize_pdfs(pdf_links, report_types)
            
            # Step 4: Download and parse reports
            reports_downloaded = 0
            for report_type, links in categorized.items():
                for link_info in links[:max_reports]:
                    if reports_downloaded >= max_reports:
                        break
                    
                    try:
                        report_data = self._download_and_parse_pdf(
                            link_info["url"], 
                            company_name, 
                            report_type
                        )
                        if report_data:
                            result["reports_found"].append({
                                "type": report_type,
                                "title": link_info.get("title", "Unknown"),
                                "url": link_info["url"],
                                "pages": report_data.get("pages", 0),
                                "extracted_metrics": report_data.get("metrics", {})
                            })
                            
                            # Merge extracted data
                            if "metrics" in report_data:
                                result["extracted_data"].update(report_data["metrics"])
                            
                            reports_downloaded += 1
                    except Exception as e:
                        result["errors"].append(f"Error processing {link_info['url']}: {str(e)}")
        
        # Step 5: Also try direct Google search for reports
        if len(result["reports_found"]) < 2:
            google_reports = self._search_google_for_reports(company_name)
            for report in google_reports[:max_reports - len(result["reports_found"])]:
                result["reports_found"].append(report)
        
        print(f"   ✅ Fetched {len(result['reports_found'])} reports")
        return result
    
    def _find_investor_relations_page(self, company_name: str) -> Optional[str]:
        """Find known IR page for company"""
        company_lower = company_name.lower()
        
        for key, url in self.known_ir_urls.items():
            if key in company_lower or company_lower in key:
                return url
        
        return None
    
    def _search_for_ir_page(self, company_name: str) -> Optional[str]:
        """Search for investor relations page using DuckDuckGo"""
        try:
            search_query = f"{company_name} investor relations annual report PDF"
            url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(search_query)}"
            
            response = self.session.get(url, timeout=10)
            if response.status_code == 200 and BS4_AVAILABLE:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find first result that looks like an IR page
                for link in soup.find_all('a', class_='result__url'):
                    href = link.get('href', '')
                    if any(x in href.lower() for x in ['investor', 'annual-report', 'ir.', 'investors']):
                        return href
        except Exception as e:
            print(f"   ⚠️ Search error: {e}")
        
        return None
    
    def _scrape_pdf_links(self, base_url: str, company_name: str) -> List[Dict]:
        """Scrape PDF links from investor relations page"""
        pdf_links = []
        
        if not BS4_AVAILABLE:
            return pdf_links
        
        try:
            response = self.session.get(base_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Check if it's a PDF link
                if '.pdf' in href.lower() or 'download' in href.lower():
                    # Make absolute URL
                    full_url = urljoin(base_url, href)
                    
                    pdf_links.append({
                        "url": full_url,
                        "title": text or self._extract_title_from_url(href),
                        "source": base_url
                    })
            
            # Also check for PDFs in iframes or embedded viewers
            for iframe in soup.find_all('iframe', src=True):
                src = iframe.get('src', '')
                if '.pdf' in src.lower():
                    pdf_links.append({
                        "url": urljoin(base_url, src),
                        "title": "Embedded PDF",
                        "source": base_url
                    })
                    
        except Exception as e:
            print(f"   ⚠️ Scraping error: {e}")
        
        return pdf_links
    
    def _categorize_pdfs(self, pdf_links: List[Dict], report_types: List[str]) -> Dict[str, List[Dict]]:
        """Categorize PDFs by report type"""
        categorized = {rt: [] for rt in report_types}
        
        for link in pdf_links:
            title_lower = link.get("title", "").lower()
            url_lower = link.get("url", "").lower()
            combined = f"{title_lower} {url_lower}"
            
            for report_type, patterns in self.report_patterns.items():
                if report_type in report_types:
                    for pattern in patterns:
                        if re.search(pattern, combined, re.IGNORECASE):
                            categorized[report_type].append(link)
                            break
        
        return categorized
    
    def _download_and_parse_pdf(self, url: str, company_name: str, 
                                report_type: str) -> Optional[Dict]:
        """Download PDF and extract text/metrics"""
        
        # Create cache key
        cache_key = hashlib.md5(f"{company_name}_{url}".encode()).hexdigest()[:16]
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        # Check cache (5 days)
        if cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age < timedelta(days=5):
                print(f"   📂 Using cached: {report_type}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        # Download PDF
        pdf_path = self.cache_dir / f"{cache_key}.pdf"
        
        try:
            print(f"   ⬇️ Downloading: {report_type}...")
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Check if it's actually a PDF
            content_type = response.headers.get('content-type', '')
            if 'pdf' not in content_type.lower() and not url.lower().endswith('.pdf'):
                return None
            
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Parse PDF
            result = self._parse_pdf(pdf_path, report_type)
            
            # Cache results
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            
            return result
            
        except Exception as e:
            print(f"   ⚠️ Download error: {e}")
            return None
    
    def _parse_pdf(self, pdf_path: Path, report_type: str) -> Dict:
        """Parse PDF and extract ESG-relevant metrics"""
        result = {
            "pages": 0,
            "text_preview": "",
            "metrics": {},
            "tables": []
        }
        
        text_content = ""
        
        # Try pdfplumber first (better table extraction)
        if PDF_PLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    result["pages"] = len(pdf.pages)
                    
                    # Extract text from first 50 pages (ESG info usually upfront)
                    for i, page in enumerate(pdf.pages[:50]):
                        page_text = page.extract_text() or ""
                        text_content += page_text + "\n"
                        
                        # Extract tables
                        tables = page.extract_tables()
                        for table in tables:
                            if table and len(table) > 1:
                                result["tables"].append({
                                    "page": i + 1,
                                    "data": table[:10]  # First 10 rows
                                })
            except Exception as e:
                print(f"   ⚠️ pdfplumber error: {e}")
        
        # Fallback to PyPDF2
        elif PYPDF2_AVAILABLE:
            try:
                reader = PdfReader(pdf_path)
                result["pages"] = len(reader.pages)
                
                for page in reader.pages[:50]:
                    text_content += page.extract_text() or ""
            except Exception as e:
                print(f"   ⚠️ PyPDF2 error: {e}")
        
        # Store preview
        result["text_preview"] = text_content[:5000]
        
        # Extract metrics
        result["metrics"] = self._extract_esg_metrics(text_content)
        
        return result
    
    def _extract_esg_metrics(self, text: str) -> Dict:
        """Extract ESG metrics from report text"""
        metrics = {}
        
        # Carbon emissions patterns
        carbon_patterns = [
            (r"scope\s*1[:\s]+(\d[\d,\.]*)\s*(million|mn|m)?\s*(tco2e?|tonnes?|mt)", "scope_1_emissions"),
            (r"scope\s*2[:\s]+(\d[\d,\.]*)\s*(million|mn|m)?\s*(tco2e?|tonnes?|mt)", "scope_2_emissions"),
            (r"scope\s*3[:\s]+(\d[\d,\.]*)\s*(million|mn|m)?\s*(tco2e?|tonnes?|mt)", "scope_3_emissions"),
            (r"total\s+emissions?[:\s]+(\d[\d,\.]*)\s*(million|mn|m)?\s*(tco2e?|tonnes?|mt)", "total_emissions"),
            (r"carbon\s+intensity[:\s]+(\d[\d,\.]*)", "carbon_intensity"),
            (r"ghg\s+emissions?[:\s]+(\d[\d,\.]*)\s*(million|mn|m)?", "ghg_emissions"),
        ]
        
        # Energy patterns
        energy_patterns = [
            (r"renewable\s+energy[:\s]+(\d[\d,\.]*)\s*%", "renewable_energy_pct"),
            (r"energy\s+consumption[:\s]+(\d[\d,\.]*)\s*(gwh|mwh|tj|pj)", "energy_consumption"),
            (r"electricity\s+consumption[:\s]+(\d[\d,\.]*)", "electricity_consumption"),
        ]
        
        # Water patterns
        water_patterns = [
            (r"water\s+consumption[:\s]+(\d[\d,\.]*)\s*(million|mn|m)?\s*(litres?|l|kl|ml|cubic)", "water_consumption"),
            (r"water\s+recycled?[:\s]+(\d[\d,\.]*)\s*%", "water_recycled_pct"),
            (r"water\s+intensity[:\s]+(\d[\d,\.]*)", "water_intensity"),
        ]
        
        # Waste patterns
        waste_patterns = [
            (r"waste\s+generated?[:\s]+(\d[\d,\.]*)\s*(tonnes?|mt|kg)", "waste_generated"),
            (r"waste\s+recycled?[:\s]+(\d[\d,\.]*)\s*%", "waste_recycled_pct"),
            (r"hazardous\s+waste[:\s]+(\d[\d,\.]*)", "hazardous_waste"),
        ]
        
        # Workforce patterns
        workforce_patterns = [
            (r"total\s+employees?[:\s]+(\d[\d,]*)", "total_employees"),
            (r"women\s+employees?[:\s]+(\d[\d,\.]*)\s*%", "women_employees_pct"),
            (r"women\s+in\s+(management|leadership)[:\s]+(\d[\d,\.]*)\s*%", "women_leadership_pct"),
            (r"employee\s+turnover[:\s]+(\d[\d,\.]*)\s*%", "employee_turnover"),
            (r"training\s+hours?[:\s]+(\d[\d,\.]*)", "training_hours"),
            (r"ltifr[:\s]+(\d[\d,\.]*)", "ltifr"),  # Lost Time Injury Frequency Rate
        ]
        
        # Financial patterns
        financial_patterns = [
            (r"revenue[:\s]+(?:rs\.?|inr|₹|\$|usd)?\s*(\d[\d,\.]*)\s*(crore|cr|billion|bn|million|mn)?", "revenue"),
            (r"net\s+profit[:\s]+(?:rs\.?|inr|₹|\$|usd)?\s*(\d[\d,\.]*)\s*(crore|cr|billion|bn|million|mn)?", "net_profit"),
            (r"ebitda[:\s]+(?:rs\.?|inr|₹|\$|usd)?\s*(\d[\d,\.]*)", "ebitda"),
            (r"csr\s+spend[:\s]+(?:rs\.?|inr|₹|\$|usd)?\s*(\d[\d,\.]*)\s*(crore|cr)?", "csr_spend"),
        ]
        
        # Governance patterns
        governance_patterns = [
            (r"board\s+independence?[:\s]+(\d[\d,\.]*)\s*%", "board_independence_pct"),
            (r"independent\s+directors?[:\s]+(\d+)", "independent_directors"),
            (r"women\s+(?:on\s+)?board[:\s]+(\d+)", "women_on_board"),
            (r"board\s+meetings?[:\s]+(\d+)", "board_meetings"),
        ]
        
        # Net Zero / Target patterns
        target_patterns = [
            (r"net\s*zero\s*(?:by|target)?\s*(\d{4})", "net_zero_target_year"),
            (r"carbon\s+neutral\s*(?:by)?\s*(\d{4})", "carbon_neutral_target"),
            (r"(\d+)\s*%\s*(?:emission)?\s*reduction\s*(?:by)?\s*(\d{4})", "emission_reduction_target"),
        ]
        
        all_patterns = (
            carbon_patterns + energy_patterns + water_patterns + 
            waste_patterns + workforce_patterns + financial_patterns +
            governance_patterns + target_patterns
        )
        
        text_lower = text.lower()
        
        for pattern, metric_name in all_patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = match.group(1)
                # Clean value
                value = value.replace(',', '')
                try:
                    metrics[metric_name] = float(value) if '.' in value else int(value)
                except:
                    metrics[metric_name] = value
                
                # Handle multipliers
                if len(match.groups()) > 1:
                    multiplier = match.group(2) if match.group(2) else ""
                    if multiplier.lower() in ['million', 'mn', 'm']:
                        metrics[metric_name] = metrics[metric_name] * 1000000
                    elif multiplier.lower() in ['billion', 'bn', 'b']:
                        metrics[metric_name] = metrics[metric_name] * 1000000000
                    elif multiplier.lower() in ['crore', 'cr']:
                        metrics[metric_name] = metrics[metric_name] * 10000000
        
        return metrics
    
    def _search_google_for_reports(self, company_name: str) -> List[Dict]:
        """Search for company reports via web search"""
        reports = []
        
        try:
            # Use DuckDuckGo as Google requires API key
            queries = [
                f"{company_name} annual report 2024 PDF filetype:pdf",
                f"{company_name} sustainability report PDF filetype:pdf",
                f"{company_name} BRSR report PDF filetype:pdf"
            ]
            
            for query in queries:
                url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200 and BS4_AVAILABLE:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for result in soup.find_all('a', class_='result__a')[:2]:
                        href = result.get('href', '')
                        title = result.get_text(strip=True)
                        
                        if '.pdf' in href.lower():
                            reports.append({
                                "type": "web_search",
                                "title": title,
                                "url": href,
                                "pages": "Unknown",
                                "extracted_metrics": {}
                            })
                
                time.sleep(1)  # Rate limiting
                
        except Exception as e:
            print(f"   ⚠️ Web search error: {e}")
        
        return reports
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract readable title from URL"""
        path = urlparse(url).path
        filename = path.split('/')[-1]
        # Remove extension and clean
        name = filename.rsplit('.', 1)[0]
        name = re.sub(r'[-_]', ' ', name)
        return name.title()
    
    def get_report_text(self, company_name: str) -> str:
        """Get combined text from all available company reports"""
        reports = self.fetch_company_reports(company_name)
        
        combined_text = []
        for report in reports.get("reports_found", []):
            if "text_preview" in report.get("extracted_metrics", {}):
                combined_text.append(report["extracted_metrics"]["text_preview"])
        
        if reports.get("extracted_data"):
            combined_text.append(f"\nExtracted Metrics:\n{json.dumps(reports['extracted_data'], indent=2)}")
        
        return "\n\n---\n\n".join(combined_text) if combined_text else ""


# Singleton instance
_report_fetcher = None

def get_report_fetcher() -> CompanyReportFetcher:
    """Get singleton instance of CompanyReportFetcher"""
    global _report_fetcher
    if _report_fetcher is None:
        _report_fetcher = CompanyReportFetcher()
    return _report_fetcher


if __name__ == "__main__":
    # Test the fetcher
    fetcher = CompanyReportFetcher()
    
    # Test with Reliance Industries
    result = fetcher.fetch_company_reports("Reliance Industries")
    print(f"\nResults: {json.dumps(result, indent=2, default=str)}")
