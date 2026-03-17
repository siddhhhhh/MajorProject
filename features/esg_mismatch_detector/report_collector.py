from typing import Dict, Optional
import requests
import os
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

def get_sustainability_page_url(company_name: str) -> Optional[str]:
    """Search for the official sustainability page of the company."""
    from utils.web_search import RealTimeDataFetcher
    fetcher = RealTimeDataFetcher()
    query = f"{company_name} official sustainability ESG investor relations page site:{company_name.lower().replace(' ', '')}.com"
    results = fetcher.search_duckduckgo(query, max_results=5)
    
    domain_part = company_name.lower().replace(" ", "")
    
    for res in results:
        url = res.get("url", "")
        # Look for typical path indicators
        if any(keyword in url.lower() for keyword in ["/sustainability", "/esg", "/responsibility", "/investors", "/climate", "/environment", "/corporate"]):
            # Also ideally belongs to the company domain
            if domain_part in url.lower():
                return url
                
    # If no strict match but we searched on their domain, fallback to general search for their domain
    query = f"{company_name} sustainability ESG"
    results = fetcher.search_duckduckgo(query, max_results=5)
    for res in results:
        url = res.get("url", "")
        if domain_part in url.lower() and ("sustainability" in url.lower() or "esg" in url.lower()):
            return url
            
    return None

def find_pdf_links(page_url: str) -> list:
    """Scan a webpage for PDF links. Also check standard sub-pages containing reports."""
    try:
        pdf_links = []
        
        # Try finding PDFs on the exact given page
        response = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if ".pdf" in href.lower():
                    full_url = urljoin(page_url, href)
                    pdf_links.append(full_url)
                    
        # Many companies put the actual PDF on a "reports hub" page linked from the main page
        # If we didn't find any, we can try a direct google search prioritizing pdfs on their domain
        if not pdf_links:
            # Try appending common paths
            common_paths = ["/reports", "/downloads", "/esg-report", "/hub", ""]
            for path in common_paths:
                test_url = page_url.rstrip("/") + path
                try:
                    r = requests.get(test_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                    if r.status_code == 200:
                        s = BeautifulSoup(r.text, "html.parser")
                        for link in s.find_all("a", href=True):
                            href = link["href"]
                            if ".pdf" in href.lower():
                                full_url = urljoin(test_url, href)
                                pdf_links.append(full_url)
                except:
                    pass
                    
        return list(set(pdf_links))
    except Exception as e:
        print(f"Error crawling {page_url} for PDFs: {e}")
        return []

def duckduckgo_pdf_search(company_name: str) -> list:
    """If crawling fails, explicitly search DuckDuckGo for the PDF on the company's domain or broadly."""
    from utils.web_search import RealTimeDataFetcher
    fetcher = RealTimeDataFetcher()
    pdf_links = []
    
    # Try searching for a PDF explicitly
    query = f"{company_name} sustainability report filetype:pdf site:{company_name.lower().replace(' ', '')}.com"
    results = fetcher.search_duckduckgo(query, max_results=8)
    
    for res in results:
        url = res.get("url", "")
        if ".pdf" in url.lower():
            pdf_links.append(url)
            
    if not pdf_links:
        query = f"{company_name} sustainability report filetype:pdf"
        results = fetcher.search_duckduckgo(query, max_results=5)
        for res in results:
            url = res.get("url", "")
            if ".pdf" in url.lower():
                pdf_links.append(url)
            
    return pdf_links

ESG_KEYWORDS = [
    "sustainability",
    "esg",
    "climate",
    "environment",
    "responsibility",
    "impact",
    "report",
    "202" # Match 2023, 2024 etc.
]

def rank_esg_pdfs(pdf_links: list) -> list:
    """Rank PDFs based on ESG keywords to find the most relevant report."""
    ranked = []
    for url in pdf_links:
        score = 0
        url_lower = url.lower()
        for word in ESG_KEYWORDS:
            if word in url_lower:
                score += 1
        # Give extra weight to the most important words
        if "sustainability-report" in url_lower or "esg-report" in url_lower:
             score += 5
        ranked.append((score, url))
        
    ranked.sort(reverse=True, key=lambda x: x[0])
    return ranked

def download_pdf(url: str, output_path: str) -> Optional[str]:
    """Download a PDF file safely using requests."""
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return output_path
    except Exception as e:
        print(f"Error downloading PDF {url}: {e}")
    return None

def validate_pdf(file_path: str, company_name: str) -> bool:
    """Check if the downloaded PDF mentions the company name within the first few pages."""
    try:
        doc = fitz.open(file_path)
        text = ""
        # Just check first 5 pages to save time/memory for validation
        for i in range(min(5, doc.page_count)):
            text += doc[i].get_text()
            
        doc.close()
        return company_name.lower() in text.lower()
    except Exception as e:
        print(f"Error validating PDF {file_path}: {e}")
        return False

def extract_tables_from_pdf(pdf_path: str) -> str:
    """
    Use pdfplumber to extract Scope 1, 2, 3 emissions tables directly.
    Provides verified numerical metrics over regex guessing.
    """
    try:
        import pdfplumber
        extracted_data = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        extracted_data += " | ".join([str(cell) for cell in row if cell]) + "\n"
        return extracted_data
    except ImportError:
        print("⚠️ pdfplumber not installed. Falling back to text extraction.")
        return ""

def validate_company(text: str, company_name: str) -> bool:
    """
    Verify that the document actually belongs to the requested company.
    """
    if not text:
        return False
    return company_name.lower() in text.lower()

def extract_pdf_text_pymupdf(file_path: str) -> str:
    """Read a PDF fully into text using PyMuPDF."""
    try:
        text = ""
        doc = fitz.open(file_path)
        # Limit extraction to reasonable amount to avoid blowing up memory/context window later
        for i in range(min(50, doc.page_count)):
            text += doc[i].get_text() + "\n"
        doc.close()
        return text
    except Exception as e:
        print(f"PyMuPDF error: {e}")
        return ""

def fetch_latest_esg_report(company: Dict) -> Optional[str]:
    """
    Fetch the latest ESG report text using the improved discovery pipeline:
    Company -> Search Pages -> Crawl PDFs -> Rank -> Download -> Validate -> Extract
    """
    company_name = company['company']
    
    import tempfile
    
    print(f"🌍 Step 1: Locating official sustainability page for {company_name}...")
    page_url = get_sustainability_page_url(company_name)
    
    pdf_url = None
    if page_url:
        print(f"🔗 Found page: {page_url}")
        print("🕷️ Step 2: Crawling page for PDF links...")
        pdf_links = find_pdf_links(page_url)
        
        # Fallback to duckduckgo explicit PDF search
        if not pdf_links:
             print("⚠️ No PDFs found on page. Searching explicitly for PDFs...")
             pdf_links = duckduckgo_pdf_search(company_name)

        if pdf_links:
            print(f"📑 Found {len(pdf_links)} PDF links. Step 3: Ranking them...")
            ranked_pdfs = rank_esg_pdfs(pdf_links)
            
            # Try the top 3 ranked PDFs
            for score, url in ranked_pdfs[:3]:
                if score == 0 and len(ranked_pdfs) > 1:
                     continue # Skip completely un-scored files if we have options
                     
                print(f"⬇️ Step 4/5: Downloading candidate PDF (Score: {score}): {url}")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                     tmp_path = tmp_file.name
                     
                downloaded_path = download_pdf(url, tmp_path)
                if downloaded_path:
                    print(f"🔎 Step 6: Validating PDF belongs to {company_name}...")
                    if validate_pdf(downloaded_path, company_name):
                        print("✅ Validation successful!")
                        pdf_url = url
                        # Extract Text
                        print("📄 Step 7: Extracting text from valid PDF...")
                        extracted_text = extract_pdf_text_pymupdf(downloaded_path)
                        table_text = extract_tables_from_pdf(downloaded_path)
                        return extracted_text[:25000] + "\nTABLES:\n" + table_text[:5000]
                    else:
                        print("❌ Validation failed. Text does not match company.")
                        try:
                            os.remove(downloaded_path)
                        except:
                            pass
        else:
            print("⚠️ No PDF links found on the sustainability page.")
    else:
         print("⚠️ Could not definitively locate a sustainability page.")
    
    # Fallback to direct PDF search via DuckDuckGo if scraping failed
    if not pdf_url:
        print("⚠️ Direct PDF discovery failed. Falling back to search snippets...")
        
        try:
             # Fallback search if PDF fails to download or validate
             from utils.web_search import RealTimeDataFetcher
             fetcher = RealTimeDataFetcher()
             text_corpus = ""
             
             # Note: We now fetch snippets but immediately validate them against the company name before inclusion
             results = fetcher.search_duckduckgo(f"{company_name} ESG sustainability commitments targets goals", max_results=10)
             for res in results:
                 snippet = res.get("snippet", "")
                 content = res.get("content", "")
                 combined = snippet + " " + content
                 
                 if combined and validate_company(combined, company_name):
                      text_corpus += "\n" + snippet + "\n"
                      text_corpus += "\n" + content + "\n"
                 
             return text_corpus if text_corpus else ""
        except Exception as e:
             print(f"Error during fallback text prep: {e}")
             return ""
