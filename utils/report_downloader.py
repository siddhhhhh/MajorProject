"""
ESG Report Downloader Service
Downloads and stores ESG reports discovered in Phase 2
Handles caching, validation, and error recovery
"""

import os
import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import hashlib


class ReportDownloadCache:
    """
    Singleton cache for downloaded report metadata
    Prevents redundant downloads with 7-day TTL
    Stores download history separately from evidence cache
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.session_cache: Dict[str, Any] = {}
        self.cache_dir = Path("cache/reports")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = 7  # Reports cached for 7 days
        self._initialized = True
        
        print("✅ Report Download Cache initialized (7-day TTL)")
    
    def _generate_cache_key(self, url: str) -> str:
        """Generate cache key from URL hash"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"report_{url_hash}"
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get file path for cached metadata"""
        return self.cache_dir / f"{cache_key}.json"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is within TTL"""
        if not cache_path.exists():
            return False
        
        modified_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - modified_time
        
        return age < timedelta(days=self.ttl_days)
    
    def get_download_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached download metadata for a URL"""
        cache_key = self._generate_cache_key(url)
        
        # Try in-memory cache first
        if cache_key in self.session_cache:
            return self.session_cache[cache_key]
        
        # Try disk cache
        cache_path = self._get_cache_path(cache_key)
        
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Load into session cache
                self.session_cache[cache_key] = data
                
                # Calculate cache age
                age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
                age_days = age.days
                age_str = f"{age_days}d {(age.seconds // 3600)}h" if age_days > 0 else f"{age.seconds // 3600}h"
                
                return data
                
            except Exception as e:
                print(f"⚠️ Cache read error: {e}")
                return None
        
        return None
    
    def store_download_info(self, url: str, download_info: Dict[str, Any]):
        """Store download metadata in both memory and disk cache"""
        cache_key = self._generate_cache_key(url)
        
        # Add metadata
        download_info['_cache_metadata'] = {
            'url': url,
            'cached_at': datetime.now().isoformat(),
            'cache_key': cache_key
        }
        
        # Store in memory
        self.session_cache[cache_key] = download_info
        
        # Persist to disk
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(download_info, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            print(f"⚠️ Cache write error: {e}")
    
    def clear_session_cache(self):
        """Clear in-memory cache"""
        self.session_cache.clear()


# Global singleton instance
report_download_cache = ReportDownloadCache()


class ReportDownloaderService:
    """
    Download and manage ESG report PDFs
    Handles validation, caching, and storage
    """
    
    # Download constraints. Cap raised from 100 MB → 300 MB because major
    # issuers (oil supermajors, large banks) publish unified annuals in the
    # 150-250 MB range; 100 MB caused TotalEnergies, Shell, JPMC primary PDFs
    # to be silently skipped, cascading to "all frameworks UNCERTAIN".
    MAX_FILE_SIZE = 300 * 1024 * 1024  # 300 MB
    TIMEOUT_SECONDS = 30
    MAX_RETRIES = 3
    REPORTS_DIR = "data/reports"
    
    # PDF validation
    PDF_CONTENT_TYPES = [
        "application/pdf",
        "application/x-pdf",
        "application/x-pdfdocument",
    ]

    # Direct fallback links for known issuers when discovery returns truncated/invalid URLs
    FALLBACK_REPORT_URLS = {
        "bp": "https://www.bp.com/content/dam/bp/business-sites/en/global/corporate/pdfs/sustainability/group-reports/bp-sustainability-report-2023.pdf",
        "shell": "https://reports.shell.com/sustainability-report/2023/_assets/downloads/shell-sustainability-report-2023.pdf",
        "tesla": "https://www.tesla.com/ns_videos/2023-tesla-impact-report.pdf",
        "microsoft": "https://query.prod.cms.rt.microsoft.com/cms/api/am/binary/RW1jvLz",
        "unilever": "https://www.unilever.com/investor-relations/annual-report-and-accounts/",
    }
    
    def __init__(self):
        self.name = "ESG Report Downloader Service"
        self.session: requests.Session = requests.Session()
        # Use a realistic browser User-Agent — many vendor sites (Tesla,
        # Apple, etc.) sit behind Cloudflare and reject default Python
        # requests UA with 403. A generic Chrome UA gets through their
        # anti-bot rules for static asset downloads (the actual PDF files).
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/pdf,text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

        # Create reports directory
        Path(self.REPORTS_DIR).mkdir(parents=True, exist_ok=True)
    
    def download_reports(self, company_name: str, 
                        discovered_reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Download discovered ESG reports to local storage
        
        Args:
            company_name: Name of company
            discovered_reports: List from Phase 2 discovery
                [{year, url, title, report_type, confidence}, ...]
        
        Returns:
            List of successfully downloaded reports:
            [{
                "url": "...",
                "local_path": "data/reports/tesla_2024_sustainability.pdf",
                "year": 2024,
                "report_type": "sustainability",
                "file_size": 5242880,
                "download_timestamp": "..."
            }]
        """
        
        print(f"\n{'='*70}")
        print(f"📥 REPORT DOWNLOADER SERVICE")
        print(f"{'='*70}")
        print(f"Company: {company_name}")
        print(f"Reports to download: {len(discovered_reports)}")

        # Add guaranteed fallback link when discovery returns nothing or invalid candidates.
        fallback_url = self.FALLBACK_REPORT_URLS.get(company_name.lower().strip())
        if fallback_url and not any((r.get("url") or "").strip() for r in discovered_reports):
            discovered_reports = list(discovered_reports) + [{
                "year": datetime.now().year - 1,
                "url": fallback_url,
                "title": f"{company_name} sustainability report (fallback)",
                "report_type": "sustainability",
                "confidence": 0.9,
            }]
            print(f"⚠️ Discovery returned no valid URLs, injecting fallback source for {company_name}")
        
        # Create company-specific report directory
        company_dir = Path(self.REPORTS_DIR) / self._sanitize_company_name(company_name)
        company_dir.mkdir(parents=True, exist_ok=True)

        print(f"📁 Storage directory: {company_dir}")

        successfully_downloaded = []

        # Pre-populate from existing local PDFs in the company directory
        # AND alternate sanitization variants (e.g. "Tesla, Inc." sanitizes
        # to `tesla_inc/` but a previous run named the dir `tesla/`). We
        # search both the canonical sanitized dir AND any sibling whose
        # name shares the company's distinctive tokens.
        try:
            search_dirs = {company_dir}
            try:
                reports_root = Path(self.REPORTS_DIR)
                # Distinctive tokens (≥4 chars, not generic suffixes)
                import re as _re_tok
                tokens = [
                    t for t in _re_tok.split(r"[^A-Za-z0-9]+", company_name.lower())
                    if len(t) >= 4 and t not in {"corp", "inc", "ltd", "plc", "group", "company", "limited"}
                ]
                if not tokens:  # short ticker
                    tokens = [(company_name or "").split()[0].lower()] if company_name else []
                if reports_root.is_dir() and tokens:
                    for sib in reports_root.iterdir():
                        if not sib.is_dir():
                            continue
                        sib_name = sib.name.lower()
                        # Match if any distinctive token is in the dir name
                        if any(tok in sib_name for tok in tokens):
                            search_dirs.add(sib)
            except Exception:
                pass

            local_pdfs: List[Path] = []
            for d in search_dirs:
                local_pdfs.extend(p for p in d.glob("*.pdf") if p.stat().st_size >= 200_000)
            local_pdfs = sorted(local_pdfs, key=lambda p: p.stat().st_mtime, reverse=True)
            if local_pdfs:
                # Take the largest 2 (most likely to be substantive ESG/Impact reports).
                local_pdfs.sort(key=lambda p: p.stat().st_size, reverse=True)
                _seen_paths: set = set()
                for pdf_path in local_pdfs[:2]:
                    if str(pdf_path) in _seen_paths:
                        continue
                    _seen_paths.add(str(pdf_path))
                    name = pdf_path.name.lower()
                    # Skip files we've already seen via the discovered URLs
                    already = any(
                        Path(r.get("local_path", "")).name == pdf_path.name
                        for r in successfully_downloaded
                    )
                    if already:
                        continue
                    # Year inference from filename
                    import re as _re_year
                    yr_match = _re_year.search(r"(20\d{2})", name)
                    inferred_year = int(yr_match.group(1)) if yr_match else None
                    rtype = (
                        "sustainability" if "sustain" in name or "impact" in name
                        else "annual" if "annual" in name or "10-k" in name
                        else "esg" if "esg" in name
                        else "unknown"
                    )
                    successfully_downloaded.append({
                        "url": f"local://{pdf_path}",
                        "local_path": str(pdf_path),
                        "year": inferred_year,
                        "report_type": rtype,
                        "file_size": pdf_path.stat().st_size,
                        "download_timestamp": datetime.fromtimestamp(pdf_path.stat().st_mtime).isoformat(),
                        "from_cache": True,
                        "source_origin": "pre_existing_local_pdf",
                    })
                    print(
                        f"      📂 Pre-existing local PDF added: {pdf_path.name} "
                        f"({pdf_path.stat().st_size/1e6:.1f}MB) — feeds parser even if discovery missed it"
                    )
        except Exception as _exc:
            print(f"      ⚠️ Could not enumerate pre-existing local PDFs: {_exc}")
        
        # Download each report
        for i, report in enumerate(discovered_reports, 1):
            print(f"\n   [{i}/{len(discovered_reports)}] Downloading report...")
            
            url = report.get("url", "")
            year = report.get("year")
            report_type = report.get("report_type", "unknown").lower()
            title = report.get("title", "")
            
            if not url:
                print(f"      ⚠️ Skipped: No URL provided")
                continue
            
            # ============================================================
            # STEP 1: CHECK CACHE
            # ============================================================
            cached_info = report_download_cache.get_download_info(url)
            
            if cached_info:
                cached_path = cached_info.get("local_path")
                
                # Verify cached file still exists
                if cached_path and Path(cached_path).exists():
                    print(f"      ✅ Using cached download (7-day cache)")
                    print(f"         File: {cached_path}")
                    
                    # Add to results
                    successfully_downloaded.append({
                        "url": url,
                        "local_path": cached_path,
                        "year": year,
                        "report_type": report_type,
                        "file_size": Path(cached_path).stat().st_size,
                        "download_timestamp": cached_info.get("download_timestamp"),
                        "from_cache": True
                    })
                    continue
                else:
                    print(f"      ⚠️ Cache entry invalid (file missing), re-downloading...")
            
            # ============================================================
            # STEP 2: DOWNLOAD WITH RETRIES
            # ============================================================
            result = self._download_with_retry(url, company_name, year, report_type, company_dir)
            
            if result:
                successfully_downloaded.append(result)
                
                # Cache the download info
                report_download_cache.store_download_info(url, {
                    "local_path": result["local_path"],
                    "file_size": result["file_size"],
                    "download_timestamp": result["download_timestamp"],
                    "url": url
                })
            else:
                print(f"      ❌ Failed to download after {self.MAX_RETRIES} retries")
        
        # ============================================================
        # SUMMARY
        # ============================================================
        print(f"\n{'='*70}")
        print(f"📊 DOWNLOAD SUMMARY")
        print(f"{'='*70}")
        print(f"Total requested:  {len(discovered_reports)}")
        print(f"Successfully downloaded: {len(successfully_downloaded)}")
        print(f"Success rate: {len(successfully_downloaded)/max(len(discovered_reports), 1)*100:.0f}%")
        
        if successfully_downloaded:
            print(f"\n✅ Downloaded reports:")
            for report in successfully_downloaded:
                year_str = f"{report.get('year', 'Unknown')}" if report.get('year') else "Unknown year"
                size_mb = report.get('file_size', 0) / (1024 * 1024)
                print(f"   • {year_str}: {Path(report.get('local_path', '')).name} ({size_mb:.1f} MB)")
        
        print(f"{'='*70}\n")
        
        return successfully_downloaded
    
    def _download_with_retry(self, url: str, company_name: str, year: Optional[int],
                            report_type: str, output_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Download file with retry logic
        Returns download info dict or None if failed
        """
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                print(f"      📡 Attempt {attempt}/{self.MAX_RETRIES}: URL length={len(url)}")
                print(f"         {url}")
                
                # ====== VALIDATE URL ======
                if not self._validate_url(url):
                    print(f"      ⚠️ URL validation failed, skipping")
                    return None
                
                # ====== SEND REQUEST ======
                response = self.session.get(
                    url,
                    timeout=self.TIMEOUT_SECONDS,
                    allow_redirects=True,
                    stream=True
                )
                
                # ====== CHECK RESPONSE STATUS ======
                if response.status_code != 200:
                    print(f"      ⚠️ HTTP {response.status_code}, skipping")
                    return None
                
                # ====== VALIDATE CONTENT TYPE ======
                content_type = response.headers.get('content-type', '').lower()
                
                # Check if PDF or HTML
                is_pdf = any(pdf_type in content_type for pdf_type in self.PDF_CONTENT_TYPES)
                is_html = 'text/html' in content_type or 'application/html' in content_type
                
                if is_pdf:
                    # Standard PDF download
                    return self._download_pdf_content(
                        response, company_name, year, report_type, output_dir, url
                    )
                elif is_html:
                    # HTML page detected - try to extract PDF links or save HTML
                    print(f"      📄 HTML page detected, attempting to extract content...")
                    return self._handle_html_page(response, url, company_name, year, report_type, output_dir)
                else:
                    print(f"      ⚠️ Unsupported content type ({content_type}), skipping")
                    return None
                

                
            except requests.Timeout:
                print(f"      ⏱️ Timeout on attempt {attempt}/{self.MAX_RETRIES}")
                if attempt < self.MAX_RETRIES:
                    print(f"      🔄 Retrying...")
                continue
            
            except requests.ConnectionError as e:
                print(f"      🌐 Connection error: {e}")
                if attempt < self.MAX_RETRIES:
                    print(f"      🔄 Retrying...")
                continue
            
            except Exception as e:
                print(f"      ❌ Unexpected error: {e}")
                if attempt < self.MAX_RETRIES:
                    print(f"      🔄 Retrying...")
                continue
        
        return None
    
    def _download_pdf_content(self, response, company_name: str, year: Optional[int],
                             report_type: str, output_dir: Path, url: str) -> Optional[Dict[str, Any]]:
        """
        Handle PDF content download
        Extracts into separate method for code clarity
        """
        # ====== CHECK FILE SIZE ======
        content_length = response.headers.get('content-length')
        
        if content_length:
            file_size = int(content_length)
            
            if file_size > self.MAX_FILE_SIZE:
                print(f"      ⚠️ File too large ({file_size / (1024*1024):.1f} MB > {self.MAX_FILE_SIZE // (1024*1024)} MB), skipping")
                return None
        
        # ====== GENERATE FILENAME ======
        filename = self._generate_filename(company_name, year, report_type)
        local_path = output_dir / filename
        
        # ====== DOWNLOAD FILE ======
        print(f"      ⏳ Downloading to {filename}...")
        
        total_size = 0
        chunks = []
        
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                chunks.append(chunk)
                total_size += len(chunk)
                
                # Periodic size check
                if total_size > self.MAX_FILE_SIZE:
                    print(f"      ⚠️ File exceeds {self.MAX_FILE_SIZE // (1024*1024)} MB limit during download, aborting")
                    return None
        
        # ====== WRITE TO DISK ======
        with open(local_path, 'wb') as f:
            for chunk in chunks:
                f.write(chunk)
        
        # ====== VERIFY FILE ======
        if not self._verify_pdf(local_path):
            print(f"      ⚠️ Downloaded file is not a valid PDF, deleting...")
            try:
                local_path.unlink()
            except:
                pass
            return None
        
        # ====== SUCCESS ======
        file_size = local_path.stat().st_size
        size_mb = file_size / (1024 * 1024)
        
        print(f"      ✅ Downloaded successfully ({size_mb:.1f} MB)")
        
        return {
            "url": url,
            "local_path": str(local_path),
            "year": year,
            "report_type": report_type,
            "file_size": file_size,
            "download_timestamp": datetime.now().isoformat(),
            "from_cache": False,
            "content_type": "pdf"
        }
    
    def _handle_html_page(self, response, url: str, company_name: str, year: Optional[int],
                         report_type: str, output_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Handle HTML page content
        Attempts to extract PDF links from HTML page
        Falls back to saving HTML content for parsing
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print(f"      ⚠️ BeautifulSoup not available, cannot parse HTML")
            return None
        
        try:
            # Parse HTML
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for PDF links in the page
            pdf_urls = self._extract_pdf_links_from_html(soup, url)
            
            if pdf_urls:
                print(f"      📎 Found {len(pdf_urls)} PDF link(s) in HTML page")
                # Try to download the first ESG-relevant PDF
                for pdf_url in pdf_urls[:3]:  # Try first 3 PDFs
                    print(f"      🔗 Attempting to download PDF from link: {pdf_url[:60]}...")
                    try:
                        pdf_response = self.session.get(
                            pdf_url,
                            timeout=self.TIMEOUT_SECONDS,
                            allow_redirects=True,
                            stream=True
                        )
                        
                        if pdf_response.status_code == 200:
                            content_type = pdf_response.headers.get('content-type', '').lower()
                            if any(pdf_type in content_type for pdf_type in self.PDF_CONTENT_TYPES):
                                # Successfully found a PDF link, download it
                                return self._download_pdf_content(
                                    pdf_response, company_name, year, report_type, output_dir, pdf_url
                                )
                    except Exception as e:
                        print(f"         ⚠️ Could not download PDF from link: {e}")
                        continue
            
            # No PDF links found, save HTML content for parsing
            print(f"      💾 Saving HTML content for parsing...")
            
            filename = self._generate_html_filename(company_name, year, report_type)
            local_path = output_dir / filename
            
            # Save HTML content
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            file_size = local_path.stat().st_size
            size_mb = file_size / (1024 * 1024)
            
            print(f"      ✅ Saved HTML content ({size_mb:.1f} MB)")
            
            return {
                "url": url,
                "local_path": str(local_path),
                "year": year,
                "report_type": report_type,
                "file_size": file_size,
                "download_timestamp": datetime.now().isoformat(),
                "from_cache": False,
                "content_type": "html"
            }
            
        except Exception as e:
            print(f"      ❌ Error processing HTML page: {e}")
            return None
    
    def _extract_pdf_links_from_html(self, soup, base_url: str) -> List[str]:
        """
        Extract PDF links from HTML page
        Scores links by ESG relevance
        """
        pdf_links = []
        esg_keywords = [
            'sustainability', 'esg', 'environmental', 'social', 'governance',
            'impact', 'csr', 'responsibility', 'climate', 'carbon', 'report',
            'esgreport', 'esg-report', 'sus-report'
        ]
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            link_text = link.get_text(strip=True).lower()
            
            # Check if it's a PDF link
            if href.endswith('.pdf'):
                # Score based on ESG keywords
                score = sum(1 for kw in esg_keywords if kw in href or kw in link_text)
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    from urllib.parse import urljoin
                    href = urljoin(base_url, href)
                elif not href.startswith('http'):
                    from urllib.parse import urljoin
                    href = urljoin(base_url, href)
                
                pdf_links.append((href, score))
        
        # Sort by relevance score (highest first)
        pdf_links.sort(key=lambda x: x[1], reverse=True)
        
        return [url for url, score in pdf_links]
    
    def _generate_html_filename(self, company_name: str, year: Optional[int],
                               report_type: str) -> str:
        """
        Generate filename for HTML content
        Format: <company>_<year>_<report_type>.html
        """
        company_clean = self._sanitize_company_name(company_name)
        year_str = str(year) if year else "unknown_year"
        report_type_clean = report_type.lower().replace(" ", "_")
        filename = f"{company_clean}_{year_str}_{report_type_clean}.html"
        return filename
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL format and accessibility.

        Tesla, Apple, and other vendors block HEAD requests via Cloudflare/
        anti-bot rules but happily serve GET. Previously the validator
        rejected on HEAD 403 and the actual report (63MB Tesla Impact
        Report) never got downloaded. We now treat HEAD 403/405/406/410
        as inconclusive (try the GET anyway) and only reject on hard 404.
        """
        try:
            # Basic URL validation
            if not url.startswith(('http://', 'https://')):
                return False

            # Common symptom of truncated logging/caching
            if "..." in url:
                return False

            parsed = urlparse(url)
            if not parsed.netloc:
                return False

            # Check HEAD request (quick validation without download)
            try:
                response = self.session.head(url, timeout=5, allow_redirects=True)
                # Hard reject only on 404. Many vendors return 403/405/406
                # for HEAD because their anti-bot rules don't whitelist it.
                if response.status_code == 404:
                    return False
                # 200/206 = explicit success; anything else (incl. 403, 405,
                # 410) = let the GET attempt make the final decision.
                return True
            except Exception:
                # HEAD might not work; allow proceeding to GET
                return True

        except Exception:
            return False
    
    # Stub PDFs slip through when a server returns a small redirect/404 page
    # with the .pdf extension and a %PDF prefix. Anything below these floors
    # cannot contain a real ESG/climate disclosure (a real one runs ≥10 pages
    # and ≥50 KB of compressed text). We treat such files as failed downloads
    # so they don't poison the chunk cache or carbon extraction.
    MIN_PDF_BYTES = 50 * 1024
    MIN_PDF_PAGES = 5

    def _verify_pdf(self, filepath: Path) -> bool:
        """
        Verify file is a valid, substantive PDF.

        Three layers of check:
          1. %PDF magic bytes
          2. File size ≥ MIN_PDF_BYTES (filters stub redirect pages)
          3. Page count ≥ MIN_PDF_PAGES when a parser is available
             (filters cover-only stubs that happen to compress to >50 KB)
        """
        try:
            size = filepath.stat().st_size
            if size < self.MIN_PDF_BYTES:
                print(
                    f"         ⚠️ PDF rejected: size {size} bytes < {self.MIN_PDF_BYTES} (likely stub/redirect page)"
                )
                return False

            with open(filepath, 'rb') as f:
                if not f.read(5).startswith(b'%PDF'):
                    return False

            # Page-count check — best effort; if neither parser is available
            # we accept based on size + magic bytes alone.
            try:
                from pypdf import PdfReader  # type: ignore
                reader = PdfReader(str(filepath))
                page_count = len(reader.pages)
            except Exception:
                try:
                    import pdfplumber  # type: ignore
                    with pdfplumber.open(str(filepath)) as pdf:
                        page_count = len(pdf.pages)
                except Exception:
                    return True  # parsers unavailable; rely on size+magic

            if page_count < self.MIN_PDF_PAGES:
                print(
                    f"         ⚠️ PDF rejected: only {page_count} page(s) < {self.MIN_PDF_PAGES} (likely cover-only stub)"
                )
                return False
            return True

        except Exception as e:
            print(f"         ⚠️ PDF verification error: {e}")
            return False
    
    def _generate_filename(self, company_name: str, year: Optional[int], 
                          report_type: str) -> str:
        """
        Generate filename from metadata
        Format: <company>_<year>_<report_type>.pdf
        """
        company_clean = self._sanitize_company_name(company_name)
        
        # Default year if unknown
        year_str = str(year) if year else "unknown_year"
        
        # Ensure report_type is clean
        report_type_clean = report_type.lower().replace(" ", "_")
        
        filename = f"{company_clean}_{year_str}_{report_type_clean}.pdf"
        
        return filename
    
    def _sanitize_company_name(self, company_name: str) -> str:
        """
        Clean company name for use in filenames
        Removes special characters, converts to lowercase
        """
        # Convert to lowercase
        clean = company_name.lower()
        
        # Keep only alphanumeric and underscores
        clean = ''.join(c if c.isalnum() or c in ('_', '-') else '_' for c in clean)
        
        # Remove multiple underscores
        while '__' in clean:
            clean = clean.replace('__', '_')
        
        # Remove leading/trailing underscores
        clean = clean.strip('_')
        
        return clean[:50]  # Limit to 50 characters


# Singleton instance
_downloader_service: Optional[ReportDownloaderService] = None


def get_downloader_service() -> ReportDownloaderService:
    """Get or create singleton instance"""
    global _downloader_service
    
    if _downloader_service is None:
        _downloader_service = ReportDownloaderService()
    
    return _downloader_service


def download_company_reports(company_name: str, 
                             discovered_reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convenience function to download reports for a company
    
    Example:
        from utils.report_discovery import discover_company_reports
        from utils.report_downloader import download_company_reports
        
        # Phase 2: Discover
        reports = discover_company_reports("Tesla")
        
        # Phase 3: Download
        downloaded = download_company_reports("Tesla", reports)
        
        for report in downloaded:
            print(f"{report['year']}: {report['local_path']}")
    """
    service = get_downloader_service()
    return service.download_reports(company_name, discovered_reports)
