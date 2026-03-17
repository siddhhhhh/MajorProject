"""
ESG Report Parser Service
Extracts text from PDFs, cleans content, and chunks for LLM processing
Designed for PHASE 4 of enterprise-grade ESG analysis pipeline
"""

import uuid
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class ReportParserCache:
    """
    Singleton cache for parsed report chunks
    Prevents re-parsing large PDFs with 7-day TTL
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
        self.cache_dir = Path("cache/parsed_reports")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = 7
        self._initialized = True
        
        print("✅ Report Parser Cache initialized (7-day TTL)")
    
    def _generate_cache_key(self, local_path: str) -> str:
        """Generate cache key from file path"""
        import hashlib
        path_hash = hashlib.md5(local_path.encode()).hexdigest()[:12]
        return f"parsed_{path_hash}"
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get file path for cached chunks"""
        return self.cache_dir / f"{cache_key}.json"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is within TTL"""
        if not cache_path.exists():
            return False
        
        modified_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - modified_time
        
        return age < timedelta(days=self.ttl_days)
    
    def get_chunks(self, local_path: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached chunks for a report"""
        cache_key = self._generate_cache_key(local_path)
        
        # Try in-memory cache first
        if cache_key in self.session_cache:
            chunks = self.session_cache[cache_key]
            print(f"      📦 Using cached chunks from memory (7-day cache)")
            return chunks
        
        # Try disk cache
        cache_path = self._get_cache_path(cache_key)
        
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    chunks = data.get('chunks', [])
                
                # Load into session cache
                self.session_cache[cache_key] = chunks
                
                # Calculate cache age
                age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
                age_hours = age.seconds // 3600
                
                print(f"      📦 Using cached chunks from disk ({age_hours}h old)")
                return chunks
                
            except Exception as e:
                print(f"      ⚠️ Cache read error: {e}")
                return None
        
        return None
    
    def store_chunks(self, local_path: str, chunks: List[Dict[str, Any]]):
        """Store parsed chunks in cache"""
        cache_key = self._generate_cache_key(local_path)
        
        # Store in memory
        self.session_cache[cache_key] = chunks
        
        # Persist to disk
        cache_path = self._get_cache_path(cache_key)
        
        try:
            cache_data = {
                'local_path': local_path,
                'cached_at': datetime.now().isoformat(),
                'chunk_count': len(chunks),
                'chunks': chunks
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            print(f"      ⚠️ Cache write error: {e}")


# Global singleton
report_parser_cache = ReportParserCache()


class ReportParserService:
    """
    Parse ESG reports and extract text chunks
    Handles PDF extraction, text cleaning, and chunking
    """
    
    # Parsing constraints
    MAX_PAGES = 500
    PAGE_LOG_INTERVAL = 20
    
    # Chunking parameters
    CHUNK_SIZE = 2000
    CHUNK_OVERLAP = 200
    
    # ========================================
    # OPTIMIZATION: ESG SECTION DETECTION
    # ========================================
    # Keywords for identifying ESG-relevant sections
    ESG_SECTION_KEYWORDS = [
        "sustainability", "sustainable", "climate", "net zero", "emissions",
        "renewable", "carbon", "environment", "environmental", "social",
        "governance", "esg", "csr", "corporate responsibility", "green",
        "energy transition", "scope 1", "scope 2", "scope 3",
        "decarbonization", "greenhouse gas", "climate strategy",
        "clean energy", "solar", "wind", "hydro", "fossil fuel",
        "circular economy", "waste", "water", "biodiversity",
        "diversity", "inclusion", "human rights", "labor", "workforce",
        "ethics", "compliance", "accountability", "stakeholder"
    ]
    
    # Keywords for sections to skip (reduce noise)
    IRRELEVANT_SECTIONS = [
        "board of directors", "executive compensation", "financial table",
        "risk management", "risk disclosure", "table of contents",
        "appendix", "glossary", "index", "contact", "about this report"
    ]
    
    # Rate limiting for claim extraction
    MAX_CHUNKS_FOR_CLAIM_EXTRACTION = 50  # Process max 50 chunks per report
    
    def __init__(self):
        self.name = "ESG Report Parser Service"
        self._init_pdf_libraries()
    
    def _init_pdf_libraries(self):
        """Initialize PDF extraction libraries"""
        self.pdfplumber_available = False
        self.pypdf_available = False
        
        try:
            import pdfplumber
            self.pdfplumber_available = True
            print("✅ pdfplumber loaded")
        except ImportError:
            print("⚠️ pdfplumber not available")
        
        try:
            from pypdf import PdfReader
            self.pypdf_available = True
            print("✅ pypdf loaded")
        except ImportError:
            print("⚠️ pypdf not available")
        
        # Initialize LangChain text splitter
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.CHUNK_SIZE,
                chunk_overlap=self.CHUNK_OVERLAP,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            print("✅ LangChain RecursiveCharacterTextSplitter loaded")
        except ImportError:
            print("⚠️ LangChain text splitter not available")
            self.text_splitter = None
    
    # [FIX 4] FINANCIAL METRIC VALIDATION
    # Revenue pattern matching and validation rules
    REVENUE_PATTERNS = {
        "revenue": r"(?:revenue|turnover|total revenue|consolidated revenue|sales)[\s:]*(?:of\s+)?[\s$₹¥€]*([0-9,]+(?:\.[0-9]+)?)\s*(crore|lakh|million|billion|thousand|cr|lk|mn|bn|k)?",
        "net_profit": r"(?:net profit|net income|net earnings|profit after tax|pat)[\s:]*(?:of\s+)?[\s$₹¥€]*([0-9,]+(?:\.[0-9]+)?)\s*(crore|lakh|million|billion|thousand|cr|lk|mn|bn|k)?",
        "ebitda": r"(?:ebitda|earnings before interest)[\s:]*(?:of\s+)?[\s$₹¥€]*([0-9,]+(?:\.[0-9]+)?)\s*(crore|lakh|million|billion|thousand|cr|lk|mn|bn|k)?"
    }
    
    # Validation rules: min/max realistic values (in crores for Indian companies)
    FINANCIAL_VALIDATION_RULES = {
        "revenue": {"min": 10, "max": 1000000},  # Min ₹10 Cr, Max ₹1M Cr (unrealistic above this)
        "net_profit": {"min": 0.1, "max": 500000},  # Min ₹0.1 Cr
        "ebitda": {"min": 1, "max": 700000}  # Min ₹1 Cr
    }
    
    # Unit conversion multipliers
    UNIT_MULTIPLIERS = {
        "crore": 1, "cr": 1,
        "lakh": 0.01, "lk": 0.01,
        "million": 0.1, "mn": 0.1,  # 1 million ≈ 0.1 crore
        "billion": 100, "bn": 100,  # 1 billion ≈ 100 crore
        "thousand": 0.001, "k": 0.001,
        "": 1  # Default if no unit specified
    }
    
    def _validate_financial_metric(self, metric_name: str, value: float, unit: str = "") -> Optional[float]:
        """
        [FIX 4] Validate financial metrics extracted from reports
        Ensures extracted values are realistic and discards invalid data
        
        Args:
            metric_name: "revenue", "net_profit", "ebitda"
            value: Extracted numeric value
            unit: Unit of value (crore, lakh, million, etc.)
        
        Returns:
            Validated value in crores, or None if invalid
        """
        if metric_name not in self.FINANCIAL_VALIDATION_RULES:
            return None
        
        # Convert to crores if necessary
        multiplier = self.UNIT_MULTIPLIERS.get(unit.lower(), 1)
        normalized_value = value * multiplier
        
        # Get validation rules
        rules = self.FINANCIAL_VALIDATION_RULES[metric_name]
        min_val, max_val = rules["min"], rules["max"]
        
        # Validate: value must be within realistic range
        if normalized_value < min_val or normalized_value > max_val:
            print(f"[Fix] Invalid {metric_name} value discarded: ₹{normalized_value:.2f} Cr (outside {min_val}-{max_val} range)")
            return None
        
        return normalized_value
    
    def _extract_and_validate_financial_metrics(self, text: str, company: str = "") -> Dict[str, float]:
        """
        [FIX 4] Extract and validate all financial metrics from report text
        Uses pattern matching and validation rules
        
        Args:
            text: Report text to extract from
            company: Company name for context
        
        Returns:
            Dictionary of validated financial metrics
        """
        metrics = {}
        
        for metric_type, pattern in self.REVENUE_PATTERNS.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            best_match = None
            for match in matches:
                try:
                    value_str = match.group(1).replace(",", "")
                    value = float(value_str)
                    unit = match.group(2) if len(match.groups()) > 1 else ""
                    
                    # Validate
                    validated = self._validate_financial_metric(metric_type, value, unit)
                    
                    if validated is not None:
                        # Keep largest valid value (usually the consolidated revenue)
                        if best_match is None or validated > best_match:
                            best_match = validated
                            
                except (ValueError, IndexError):
                    continue
            
            if best_match is not None:
                metrics[metric_type] = best_match
                print(f"[Fix] {metric_type.title()}: ₹{best_match:.2f} Cr (validated)")
        
        return metrics
    
    # [FIX 5] TEMPORAL ANALYSIS YEAR DETECTION
    # Extract year from multiple sources for reliable year detection
    YEAR_REGEX_PATTERNS = [
        r"FY\s*(20\d\d)",
        r"Year\s*ended\s*(20\d\d)",
        r"Report\s*(20\d\d)",
        r"(?:fiscal year|for the year|period ended)\s*(?:ended\s+)?(\b(?:19|20)\d{2}\b)",
        r"(\b(?:19|20)\d{2}\b)[-/]\s*(?:19|20)\d{2}",
        r"\b((?:19|20)\d{2})\b",
    ]
    
    def _extract_year_from_filename(self, filename: str) -> Optional[int]:
        """
        [FIX 5] Extract year from report filename
        Examples: "Tesla_2023_ESG.pdf", "Annual_Report_2023-2024.pdf"
        """
        import re
        
        # Pattern: looks for 4-digit number that looks like a year
        match = re.search(r"\b((?:19|20)\d{2})\b", filename)
        if match:
            year = int(match.group(1))
            if 1900 <= year <= 2099:
                return year
        
        return None
    
    def _extract_year_from_text(self, text: str) -> Optional[int]:
        """
        [FIX 5] Extract year from report heading/title text
        Looks for common patterns like "Annual Report 2023" or "Fiscal Year ended 2023"
        """
        import re
        
        # Search in heading/title area first
        search_text = text[:4000]
        
        for pattern in self.YEAR_REGEX_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                try:
                    year = int(re.search(r"\d{4}", match.group(1)).group())
                    if 1900 <= year <= 2099:
                        return year
                except (ValueError, IndexError, AttributeError):
                    continue
        
        return None
    
    def _detect_year_for_chunk(self, chunk_text: str, provided_year: Optional[int], filename: str = "", report_title: str = "") -> int:
        """
        [FIX 5] Detect year for a chunk using multiple strategies
        Priority:
        1. Provided year parameter (from caller)
        2. Year from filename
        3. Year from chunk text/headings
        4. Current year if all else fails
        """
        # Priority 1: Use provided year if available
        if provided_year and provided_year > 1900 and provided_year < 2100:
            return provided_year
        
        # Priority 2: Extract from filename
        if filename:
            filename_year = self._extract_year_from_filename(filename)
            if filename_year:
                return filename_year
        
        # Priority 3: Extract from report title/heading
        if report_title:
            title_year = self._extract_year_from_text(report_title)
            if title_year:
                return title_year

        # Priority 4: Extract from chunk text
        text_year = self._extract_year_from_text(chunk_text)
        if text_year:
            return text_year
        
        # Priority 5: Return current year as last resort
        return datetime.now().year
    
    def parse_reports(self, company_name: str, 
                     downloaded_reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse downloaded ESG reports and extract chunks
        Handles both PDF and HTML content
        
        Args:
            company_name: Name of company
            downloaded_reports: List from Phase 3 download
                [{url, local_path, year, report_type, file_size, content_type}, ...]
        
        Returns:
            List of chunks grouped by year:
            [{
                "text": "...",
                "year": 2024,
                "company": "tesla",
                "source": "esg_report" or "html_esg_page",
                "report_type": "sustainability",
                "chunk_id": "uuid"
            }]
        """
        
        print(f"\n{'='*70}")
        print(f"📄 REPORT PARSER SERVICE")
        print(f"{'='*70}")
        print(f"Company: {company_name}")
        print(f"Reports to parse: {len(downloaded_reports)}")
        
        all_chunks = []
        
        # Parse each downloaded report
        for i, report in enumerate(downloaded_reports, 1):
            print(f"\n   [{i}/{len(downloaded_reports)}] Parsing report...")
            
            local_path = report.get("local_path", "")
            year = report.get("year")
            report_type = report.get("report_type", "unknown")
            content_type = report.get("content_type", "pdf")  # Default to PDF
            report_title = report.get("title", "")
            filename = Path(local_path).name if local_path else ""
            
            if not local_path or not Path(local_path).exists():
                print(f"      ⚠️ File not found: {local_path}")
                continue
            
            # ============================================================
            # STEP 1: CHECK CACHE
            # ============================================================
            cached_chunks = report_parser_cache.get_chunks(local_path)
            
            if cached_chunks:
                all_chunks.extend(cached_chunks)
                print(f"      ✅ Added {len(cached_chunks)} chunks from cache")
                continue
            
            # ============================================================
            # STEP 2: PARSE CONTENT (PDF or HTML)
            # ============================================================
            if content_type == "html":
                print(f"      📄 Parsing HTML page...")
                text = self._extract_text_from_html(local_path)
                source = "html_esg_page"
            else:
                # Default PDF parsing
                print(f"      📥 Extracting text from PDF...")
                text = self._extract_text_from_pdf(local_path)
                source = "esg_report"
            
            if not text or len(text.strip()) == 0:
                print(f"      ⚠️ No text extracted, skipping")
                continue
            
            print(f"      ✅ Extracted {len(text)} characters")
            
            # ============================================================
            # STEP 3: CLEAN TEXT
            # ============================================================
            print(f"      🧹 Cleaning extracted text...")
            
            cleaned_text = self._clean_text(text)
            print(f"      ✅ Cleaned to {len(cleaned_text)} characters")
            
            # ============================================================
            # STEP 4: DETECT ESG SECTIONS (OPTIMIZATION)
            # ============================================================
            print(f"      🎯 Filtering ESG-relevant sections...")
            
            esg_text = self._detect_esg_sections(cleaned_text)
            
            # ============================================================
            # STEP 5: CHUNK TEXT
            # ============================================================
            print(f"      ✂️ Chunking text...")
            
            chunks = self._chunk_text(
                esg_text,
                company_name=company_name,
                year=year,
                report_type=report_type,
                source=source,  # Pass source type to chunk creation
                filename=filename,
                report_title=report_title
            )
            
            print(f"      ✅ Created {len(chunks)} chunks")
            
            # ============================================================
            # STEP 6: CACHE CHUNKS
            # ============================================================
            report_parser_cache.store_chunks(local_path, chunks)
            
            all_chunks.extend(chunks)
        
        # ============================================================
        # SUMMARY
        # ============================================================
        print(f"\n{'='*70}")
        print(f"📊 PARSING SUMMARY")
        print(f"{'='*70}")
        print(f"Total reports processed: {len(downloaded_reports)}")
        print(f"Total chunks generated: {len(all_chunks)}")
        
        if all_chunks:
            # Group chunks by year
            chunks_by_year = {}
            for chunk in all_chunks:
                year = chunk.get('year', 'unknown')
                if year not in chunks_by_year:
                    chunks_by_year[year] = 0
                chunks_by_year[year] += 1
            
            print(f"\n✅ Chunks by year:")
            for year in sorted([y for y in chunks_by_year.keys() if y != 'unknown'] + 
                              [y for y in chunks_by_year.keys() if y == 'unknown']):
                print(f"   {year}: {chunks_by_year[year]} chunks")
            
            # Count HTML vs PDF chunks
            html_chunks = sum(1 for c in all_chunks if c.get('source') == 'html_esg_page')
            pdf_chunks = sum(1 for c in all_chunks if c.get('source') == 'esg_report')
            
            if html_chunks > 0:
                print(f"\n📊 Source breakdown:")
                print(f"   PDF chunks: {pdf_chunks}")
                print(f"   HTML chunks: {html_chunks}")
        
        print(f"{'='*70}\n")
        
        return all_chunks
    
    def _extract_text_from_pdf(self, local_path: str) -> str:
        """
        Extract text from PDF file
        Tries pdfplumber first, then PyPDF2 as fallback
        """
        
        # Try pdfplumber first (better text extraction)
        if self.pdfplumber_available:
            try:
                import pdfplumber
                
                text_parts = []
                
                with pdfplumber.open(local_path) as pdf:
                    total_pages = len(pdf.pages)
                    
                    # Limit to MAX_PAGES
                    pages_to_process = min(total_pages, self.MAX_PAGES)
                    
                    if total_pages > self.MAX_PAGES:
                        print(f"         ⚠️ Report has {total_pages} pages, processing first {self.MAX_PAGES}")
                    
                    for page_num, page in enumerate(pdf.pages[:pages_to_process], 1):
                        # Log progress
                        if page_num % self.PAGE_LOG_INTERVAL == 0 or page_num == 1:
                            print(f"         📖 Processing page {page_num}/{pages_to_process}...")
                        
                        try:
                            page_text = page.extract_text()
                            
                            if page_text and len(page_text.strip()) > 0:
                                text_parts.append(page_text)
                            
                        except Exception as e:
                            print(f"         ⚠️ Error on page {page_num}: {e}, skipping...")
                            continue
                
                combined_text = "\n\n".join(text_parts)
                return combined_text
                
            except Exception as e:
                print(f"         ⚠️ pdfplumber extraction failed: {e}, trying PyPDF2...")
        
        # Fallback to PyPDF2
        if self.pypdf_available:
            try:
                from pypdf import PdfReader
                
                text_parts = []
                
                with open(local_path, 'rb') as f:
                    reader = PdfReader(f)
                    total_pages = len(reader.pages)
                    
                    # Limit to MAX_PAGES
                    pages_to_process = min(total_pages, self.MAX_PAGES)
                    
                    if total_pages > self.MAX_PAGES:
                        print(f"         ⚠️ Report has {total_pages} pages, processing first {self.MAX_PAGES}")
                    
                    for page_num in range(pages_to_process):
                        # Log progress
                        if (page_num + 1) % self.PAGE_LOG_INTERVAL == 0 or page_num == 0:
                            print(f"         📖 Processing page {page_num + 1}/{pages_to_process}...")
                        
                        try:
                            page = reader.pages[page_num]
                            page_text = page.extract_text()
                            
                            if page_text and len(page_text.strip()) > 0:
                                text_parts.append(page_text)
                            
                        except Exception as e:
                            print(f"         ⚠️ Error on page {page_num + 1}: {e}, skipping...")
                            continue
                
                combined_text = "\n\n".join(text_parts)
                return combined_text
                
            except Exception as e:
                print(f"         ❌ pypdf extraction also failed: {e}")
                return ""
        
        print(f"         ❌ No PDF library available")
        return ""
    
    def _extract_text_from_html(self, local_path: str) -> str:
        """
        Extract text from HTML file
        Removes scripts, styles, navigation, and extracts clean text
        """
        
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print(f"         ❌ BeautifulSoup not available for HTML parsing")
            return ""
        
        try:
            # Read HTML file
            with open(local_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(['script', 'style', 'nav', 'footer']):
                script.decompose()
            
            # Get text and clean it
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            print(f"         ❌ HTML extraction failed: {e}")
            return ""

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text
        Removes headers, footers, excessive whitespace, etc.
        """
        
        # Remove page numbers (common patterns)
        text = re.sub(r'\n\s*-?\s*\d+\s*-?\s*\n', '\n', text)
        text = re.sub(r'Page\s+\d+', '', text, flags=re.IGNORECASE)
        
        # Fix hyphenated words broken across lines
        text = re.sub(r'-\n\s*', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\n\n+', '\n\n', text)  # Multiple newlines → double newline
        text = re.sub(r'[ \t]{2,}', ' ', text)  # Multiple spaces/tabs → single space
        
        # Remove control characters (except newlines)
        text = ''.join(char if char.isprintable() or char in '\n\r\t' else '' for char in text)
        
        # Normalize unicode
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        
        # Remove long sequences of special characters (likely artifacts)
        text = re.sub(r'[_\-=]{10,}', '', text)
        
        # Remove lines that are only numbers or special chars (likely headers/footers)
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines and pure number/symbol lines
            if not stripped or re.match(r'^[\d\s\-\.\|]+$', stripped):
                continue
            
            cleaned_lines.append(line)
        
        text = '\n'.join(cleaned_lines)
        
        # Final strip
        text = text.strip()
        
        return text
    
    def _detect_esg_sections(self, text: str) -> str:
        """
        Filter text to only ESG-relevant sections
        Removes irrelevant content like finance tables, board info, etc.
        This typically reduces content volume by 80-90%
        
        Algorithm:
        1. Split text by likely section headers (major headings)
        2. Score each section based on ESG keyword density
        3. Keep only high-scoring sections
        4. Return filtered text
        """
        
        print(f"         🎯 ESG Section Detection: identifying relevant sections...")
        
        # Character count before filtering
        text_before = len(text)
        
        # Split by heading-style breaks and paragraph blocks
        sections = re.split(r"\n\n+|\n(?=[A-Z][A-Za-z\s]{6,80}:)", text)
        
        if len(sections) <= 1:
            # No clear sections, return as-is
            print(f"         ℹ️ No clear sections detected, processing full text")
            return text
        
        # Score each section
        relevant_sections = []
        keywords_lower = [kw.lower() for kw in self.ESG_SECTION_KEYWORDS]
        irrelevant_lower = [irr.lower() for irr in self.IRRELEVANT_SECTIONS]
        
        priority_section_terms = [
            "climate strategy",
            "emissions",
            "energy transition",
            "renewable energy",
            "net zero",
            "sustainability targets"
        ]

        for section in sections:
            if not section.strip():
                continue
            
            section_lower = section.lower()
            
            # Check if section contains irrelevant keywords (skip it)
            skip_section = any(irr in section_lower for irr in irrelevant_lower)
            if skip_section:
                continue
            
            # Count ESG keywords in section
            esg_keyword_count = sum(1 for kw in keywords_lower if kw in section_lower)
            priority_hits = sum(1 for term in priority_section_terms if term in section_lower)
            
            # Keep sections with target ESG sections first, then keyword-dense sections
            if priority_hits > 0 or esg_keyword_count >= 2:
                relevant_sections.append(section)
            elif len(relevant_sections) == 0:
                # If no sections found yet, keep first few sections as fallback
                # (may contain intro material before ESG section)
                if len(sections) - sections.index(section) > len(sections) // 2:
                    relevant_sections.append(section)
        
        # Fallback: if no sections selected, return full text
        if not relevant_sections:
            print(f"         ⚠️ No ESG sections detected, keeping full text")
            return text
        
        # Combine relevant sections
        filtered_text = '\n\n'.join(relevant_sections)
        text_after = len(filtered_text)
        reduction_pct = 100 * (1 - text_after / text_before) if text_before > 0 else 0
        
        print(f"         ✂️ Section filtering: {text_before:,} chars → {text_after:,} chars ({reduction_pct:.1f}% reduction)")
        
        return filtered_text
    
    
    def _chunk_text(self, text: str, company_name: str, year: Optional[int],
                    report_type: str, source: str = "esg_report",
                    filename: str = "", report_title: str = "") -> List[Dict[str, Any]]:
        """
        Split text into chunks with metadata
        Uses LangChain RecursiveCharacterTextSplitter
        [FIX 5] Improved year detection from text content
        """
        
        chunks_list = []
        
        # [FIX 5] Try to detect year from text if not provided
        detected_year = self._detect_year_for_chunk(text, year, filename=filename, report_title=report_title)
        if detected_year != year and detected_year != datetime.now().year:
            print(f"      [Fix] Year detected from text: {detected_year}")
        
        # Use LangChain splitter if available
        if self.text_splitter:
            try:
                chunk_texts = self.text_splitter.split_text(text)
                
                for chunk_text in chunk_texts:
                    if len(chunk_text.strip()) > 0:  # Skip empty chunks
                        # [FIX 5] Also try to detect year from individual chunk
                        chunk_year = self._detect_year_for_chunk(
                            chunk_text,
                            detected_year,
                            filename=filename,
                            report_title=report_title
                        )
                        
                        chunk = {
                            "text": chunk_text,
                            "year": chunk_year,  # Use detected/improved year
                            "report_year": detected_year,
                            "company": company_name.lower(),
                            "source": source,  # Use passed source type
                            "report_type": report_type.lower(),
                            "chunk_id": str(uuid.uuid4())
                        }
                        chunks_list.append(chunk)
                
                return chunks_list
                
            except Exception as e:
                print(f"         ⚠️ LangChain splitter failed: {e}, using fallback...")
        
        # Fallback: manual chunking with [FIX 5] year detection
        return self._fallback_chunking(
            text,
            company_name,
            detected_year,
            report_type,
            source,
            filename=filename,
            report_title=report_title
        )
    
    def _fallback_chunking(self, text: str, company_name: str, year: Optional[int],
                          report_type: str, source: str = "esg_report",
                          filename: str = "", report_title: str = "") -> List[Dict[str, Any]]:
        """
        Fallback chunking if LangChain not available
        Simple character-based splitting with overlap
        Uses guaranteed-progress algorithm to prevent infinite loops
        """
        
        # ========================================
        # INPUT VALIDATION
        # ========================================
        if not text or len(text) == 0:
            print(f"         ⚠️ No text to chunk (empty or None)")
            return []
        
        print(f"         [Parser] Text length: {len(text)}")
        print(f"         [Parser] Starting chunking with chunk_size={self.CHUNK_SIZE}, overlap={self.CHUNK_OVERLAP}...")
        
        chunks_list = []
        text_len = len(text)
        max_chunks = 10000  # Safety guard against runaway loops
        
        start = 0
        chunk_num = 0
        
        while start < text_len and chunk_num < max_chunks:
            # Calculate end position
            end = min(start + self.CHUNK_SIZE, text_len)
            
            # Try to break at sentence boundary if not at end
            if end < text_len:
                # Look for period, newline, or comma
                last_punct = max(
                    text.rfind('. ', start, end),
                    text.rfind('\n', start, end),
                    text.rfind('. \n', start, end)
                )
                
                if last_punct > start + self.CHUNK_SIZE * 0.5:  # At least 50% of chunk
                    end = last_punct + 1
            
            # Extract chunk
            chunk_text = text[start:end].strip()
            
            if len(chunk_text) > 0:
                # [FIX 5] Try to detect year from this chunk as well
                chunk_year = self._detect_year_for_chunk(
                    chunk_text,
                    year,
                    filename=filename,
                    report_title=report_title
                )
                
                chunk = {
                    "text": chunk_text,
                    "year": chunk_year,  # Use improved year detection
                    "report_year": year,
                    "company": company_name.lower(),
                    "source": source,  # Use passed source type
                    "report_type": report_type.lower(),
                    "chunk_id": str(uuid.uuid4())
                }
                chunks_list.append(chunk)
                chunk_num += 1
                
                # Diagnostic logging
                if chunk_num % 10 == 0 or chunk_num == 1:
                    print(f"         [Parser] Chunk {chunk_num}: start_index={start}, end_index={end}, size={len(chunk_text)}")
            
            # ========================================
            # GUARANTEED FORWARD PROGRESS
            # ========================================
            # Always move forward by (chunk_size - overlap)
            # This ensures pointer progression and prevents infinite loops
            start += self.CHUNK_SIZE - self.CHUNK_OVERLAP
        
        # Check if max chunks exceeded
        if chunk_num >= max_chunks:
            print(f"         ⚠️ Maximum chunks ({max_chunks}) reached, stopping chunking")
        
        print(f"         [Parser] Created {len(chunks_list)} chunks")
        
        return chunks_list


# Singleton instance
_parser_service: Optional[ReportParserService] = None


def get_parser_service() -> ReportParserService:
    """Get or create singleton instance"""
    global _parser_service
    
    if _parser_service is None:
        _parser_service = ReportParserService()
    
    return _parser_service


def parse_downloaded_reports(company_name: str,
                             downloaded_reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convenience function to parse downloaded reports
    
    Example:
        from utils.report_discovery import discover_company_reports
        from utils.report_downloader import download_company_reports
        from utils.report_parser import parse_downloaded_reports
        
        # Phase 2: Discover
        reports = discover_company_reports("Tesla")
        
        # Phase 3: Download
        downloaded = download_company_reports("Tesla", reports)
        
        # Phase 4: Parse
        chunks = parse_downloaded_reports("Tesla", downloaded)
        
        for chunk in chunks:
            print(f"Year {chunk['year']}: {chunk['text'][:100]}...")
    """
    service = get_parser_service()
    return service.parse_reports(company_name, downloaded_reports)
