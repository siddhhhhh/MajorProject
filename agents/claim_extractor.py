import json
import re
from typing import Dict, Any, List, Optional
from core.llm_client import llm_client
from config.agent_prompts import CLAIM_EXTRACTION_PROMPT
from datetime import datetime, timedelta
from pathlib import Path


class ClaimExtractionCache:
    """
    Cache for ESG claim extraction results
    Prevents redundant LLM calls for the same company-year combinations
    Uses 7-day TTL to match report parser cache
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
        self.cache_dir = Path("cache/claim_extraction")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = 7
        self.cache_version = "v3"
        self._initialized = True
        
        print("✅ Claim Extraction Cache initialized (7-day TTL)")
    
    def _generate_cache_key(self, company: str, year: Any) -> str:
        """Generate cache key from company and year"""
        import hashlib
        key_str = f"{self.cache_version}_{company.lower()}_{year}".replace(" ", "_")
        return f"claims_{hashlib.md5(key_str.encode()).hexdigest()[:12]}"
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get file path for cached claims"""
        return self.cache_dir / f"{cache_key}.json"

    def _generate_chunk_cache_key(self, company: str, year: Any, chunk_text: str) -> str:
        """Generate deterministic cache key for chunk-level extraction."""
        import hashlib
        norm = " ".join(str(chunk_text).lower().split())[:2000]
        key_str = f"{self.cache_version}|{company.lower()}|{year}|{norm}"
        return f"chunk_claims_{hashlib.md5(key_str.encode()).hexdigest()[:16]}"

    def get_chunk_claims(self, company: str, year: Any, chunk_text: str) -> Any:
        """Get cached claims for a single chunk."""
        cache_key = self._generate_chunk_cache_key(company, year, chunk_text)

        if cache_key in self.session_cache:
            cached = self.session_cache[cache_key]
            return cached if cached else None

        cache_path = self._get_cache_path(cache_key)
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    claims = data.get('claims', [])
                if not claims:
                    return None
                self.session_cache[cache_key] = claims
                return claims
            except Exception:
                return None

        return None

    def store_chunk_claims(self, company: str, year: Any, chunk_text: str, claims: List[Dict[str, Any]]):
        """Store extracted claims for a single chunk."""
        cache_key = self._generate_chunk_cache_key(company, year, chunk_text)
        self.session_cache[cache_key] = claims

        cache_path = self._get_cache_path(cache_key)
        try:
            cache_data = {
                'company': company,
                'year': year,
                'cached_at': datetime.now().isoformat(),
                'scope': 'chunk',
                'claim_count': len(claims),
                'claims': claims
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"         ⚠️ Chunk cache write error: {e}")
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is within TTL"""
        if not cache_path.exists():
            return False
        
        modified_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - modified_time
        
        return age < timedelta(days=self.ttl_days)
    
    def get_claims(self, company: str, year: Any) -> Any:
        """Retrieve cached claims for a company/year combination"""
        cache_key = self._generate_cache_key(company, year)
        
        # Try in-memory cache first
        if cache_key in self.session_cache:
            print(f"         📦 Using cached claims from memory (7-day cache)")
            return self.session_cache[cache_key]
        
        # Try disk cache
        cache_path = self._get_cache_path(cache_key)
        
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    claims = data.get('claims', [])

                # Empty yearly cache should not suppress new extraction passes.
                if not claims:
                    return None
                
                # Load into session cache
                self.session_cache[cache_key] = claims
                
                # Calculate cache age
                age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
                age_hours = age.seconds // 3600
                
                print(f"         📦 Using cached claims from disk ({age_hours}h old)")
                return claims
                
            except Exception as e:
                print(f"         ⚠️ Cache read error: {e}")
                return None
        
        return None
    
    def store_claims(self, company: str, year: Any, claims: List[Dict[str, Any]]):
        """Store extracted claims in cache"""
        cache_key = self._generate_cache_key(company, year)
        
        # Store in memory
        self.session_cache[cache_key] = claims
        
        # Persist to disk
        cache_path = self._get_cache_path(cache_key)
        
        try:
            cache_data = {
                'company': company,
                'year': year,
                'cached_at': datetime.now().isoformat(),
                'claim_count': len(claims),
                'claims': claims
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            print(f"         ⚠️ Cache write error: {e}")


# Global singleton
claim_extraction_cache = ClaimExtractionCache()

class ClaimExtractor:
    def __init__(self):
        self.name = "Claim Extraction Specialist"
        self.llm = llm_client
    
    def extract_claims(self, company_name: str, content: str) -> Dict[str, Any]:
        """Extract structured ESG claims from content"""
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 1: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company_name}")
        print(f"Content length: {len(content)} chars")
        
        prompt = f"""{CLAIM_EXTRACTION_PROMPT}

COMPANY: {company_name}

CONTENT TO ANALYZE:
{content[:4000]}

Return ONLY valid JSON in the exact format specified. No markdown, no explanations."""

        # Try with fallback - Gemini first, then Groq
        print("⏳ Calling LLM for claim extraction (with fallback)...")
        response = self.llm.call_with_fallback(prompt, use_gemini_first=True)
        
        if not response:
            print("❌ Failed to get response from both LLMs")
            return {
                "company": company_name,
                "error": "All LLMs failed",
                "claims": []
            }
        
        claims_data = self._parse_claims_json_response(response, company_name=company_name)
        if "claims" in claims_data and isinstance(claims_data["claims"], list):
            num_claims = len(claims_data['claims'])
            print(f"✅ Successfully extracted {num_claims} claims")

            # Print summary
            for i, claim in enumerate(claims_data['claims'], 1):
                print(f"  {i}. {claim.get('claim_text', 'N/A')[:80]}...")
                print(f"     Category: {claim.get('category')}, Specificity: {claim.get('specificity_score')}/10")

            return claims_data

        print("⚠️ Invalid claims structure in response")
        return {"company": company_name, "claims": []}
    
    def _clean_json_response(self, text: str) -> str:
        """Remove markdown code blocks and clean JSON"""
        # Remove markdown code blocks
        text = re.sub(r'```\s*', '', text)
        
        # Find JSON object
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start != -1 and end > start:
            return text[start:end]
        
        return text
    
    def _fallback_parsing(self, text: str, company_name: str) -> Dict[str, Any]:
        """Fallback parsing if JSON is malformed"""
        print("🔄 Attempting fallback parsing...")
        
        cleaned = self._clean_json_response(text)
        
        try:
            return json.loads(cleaned)
        except:
            print("❌ Fallback parsing also failed")
            return {
                "company": company_name, 
                "claims": [], 
                "error": "Parsing failed",
                "raw_response": text[:500]
            }

    def _repair_json_common_issues(self, text: str) -> str:
        """Best-effort cleanup for common LLM JSON issues."""
        repaired = text

        # Normalize smart quotes and remove control chars.
        repaired = repaired.replace("\u201c", '"').replace("\u201d", '"')
        repaired = repaired.replace("\u2018", "'").replace("\u2019", "'")
        repaired = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", repaired)

        # Remove trailing commas before object/array close.
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

        # Fix missing commas between adjacent objects in arrays.
        repaired = re.sub(r"}\s*{", "},{", repaired)

        return repaired

    def _extract_claims_array(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Extract and parse only the claims array when full object parsing fails."""
        key_idx = text.find('"claims"')
        if key_idx == -1:
            return None

        bracket_start = text.find("[", key_idx)
        if bracket_start == -1:
            return None

        depth = 0
        bracket_end = -1
        for i in range(bracket_start, len(text)):
            ch = text[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    bracket_end = i
                    break

        if bracket_end == -1:
            return None

        arr_text = text[bracket_start: bracket_end + 1]
        arr_text = self._repair_json_common_issues(arr_text)

        try:
            parsed = json.loads(arr_text)
            if isinstance(parsed, list):
                return [c for c in parsed if isinstance(c, dict)]
        except Exception:
            return None

        return None

    def _parse_claims_json_response(self, response: str, company_name: str, year: Any = None) -> Dict[str, Any]:
        """Parse claims JSON robustly with repair and salvage fallbacks."""
        cleaned = self._clean_json_response(response)

        # Attempt 1: strict parse
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Attempt 2: repaired full JSON parse
        repaired = self._repair_json_common_issues(cleaned)
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as e:
            print(f"         ⚠️ JSON repair parse failed: {e}")

        # Attempt 3: salvage claims array only
        claims = self._extract_claims_array(repaired)
        if claims is None:
            claims = self._extract_claims_array(cleaned)

        if claims is not None:
            result = {
                "company": company_name,
                "claims": claims,
                "parsing_note": "claims array salvaged from malformed JSON"
            }
            if year is not None:
                for claim in result["claims"]:
                    if "year" not in claim:
                        claim["year"] = year
            print(f"         ✅ Recovered {len(result['claims'])} claim(s) from malformed JSON")
            return result

        # Final fallback
        print(f"         ❌ Unable to parse claims JSON. Response preview: {response[:220]}...")
        return {
            "company": company_name,
            "claims": [],
            "error": "Parsing failed",
            "raw_response": response[:500]
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Return agent status"""
        return {
            "agent_name": self.name,
            "status": "ready",
            "capabilities": ["claim_extraction", "vague_language_detection", "report_chunk_processing"]
        }
    
    # ============================================================
    # NEW: PHASE 5 - Report Chunk Processing (2026)
    # ============================================================
    
    # ESG keywords for filtering chunks (reduces unnecessary LLM calls)
    ESG_KEYWORDS = [
        "sustainability", "sustainable", "climate", "net zero", "emissions", 
        "renewable", "carbon", "environment", "environmental", "social",
        "governance", "esg", "csr", "corporate responsibility", "green",
        "sustainable development", "sdg", "paris agreement", "climate change",
        "circular economy", "waste reduction", "water", "biodiversity",
        "diversity", "inclusion", "human rights", "labor", "workforce",
        "board", "ethics", "transparency", "accountability", "risk",
        "compliance", "regulatory", "stakeholder", "community", "energy",
        "fossil fuel", "clean energy", "solar", "wind", "hydro",
        "esg score", "esg rating", "sustainability report", "annual report",
        "brsr", "sec filing", "10-k", "10-q"
    ]
    
    # Batch size for processing chunks (prevents huge LLM prompts)
    CHUNK_BATCH_SIZE = 3  # 3 chunks (~6000 chars) per LLM call
    
    # Rate limiting for API protection
    MAX_LLM_CALLS_PER_REPORT = 10  # Stop after 10 LLM calls per report
    
    def extract_claims_from_report_chunks(self, company_name: str,
                                         report_chunks: List[Dict[str, Any]],
                                         target_claim: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract ESG claims from ESG report chunks
        Processes chunks grouped by year to support temporal analysis
        
        Args:
            company_name: Name of company
            report_chunks: List from Phase 4 parser
                [{text, year, company, source, report_type, chunk_id}, ...]
        
        Returns:
            {
                "report_claims_by_year": {
                    2024: [claim_text1, claim_text2, ...],
                    2023: [claim_text1, ...],
                    ...
                },
                "claims_by_year_structured": {
                    2024: [{claim_id, claim_text, category, specificity_score, ...}, ...],
                    ...
                },
                "total_report_claims": <number>,
                "years_detected": [2024, 2023, 2022],
                "chunks_processed": <number>,
                "chunks_skipped": <number>,
                "cache_hits": <number>,
                "llm_calls_made": <number>
            }
        """
        
        print(f"\n{'='*70}")
        print(f"📊 CLAIM EXTRACTION FROM REPORT CHUNKS (PHASE 5)")
        print(f"{'='*70}")
        print(f"Company: {company_name}")
        print(f"Total chunks received: {len(report_chunks)}")
        
        # ============================================================
        # STEP 1: VALIDATE AND FILTER CHUNKS
        # ============================================================
        print(f"\n🔍 Step 1: Filtering chunks by ESG keywords...")
        
        filtered_chunks = self._filter_esg_chunks(report_chunks)
        
        print(f"   Chunks with ESG keywords: {len(filtered_chunks)}")
        print(f"   Chunks skipped: {len(report_chunks) - len(filtered_chunks)}")
        
        if not filtered_chunks:
            print(f"   ⚠️ No ESG-relevant chunks found, returning empty results")
            return {
                "report_claims_by_year": {},
                "claims_by_year_structured": {},
                "total_report_claims": 0,
                "years_detected": [],
                "chunks_processed": 0,
                "chunks_skipped": len(report_chunks),
                "cache_hits": 0,
                "llm_calls_made": 0
            }
        
        # ============================================================
        # STEP 2: GROUP CHUNKS BY YEAR
        # ============================================================
        print(f"\n📅 Step 2: Grouping chunks by year...")
        
        chunks_by_year = self._group_chunks_by_year(filtered_chunks)
        
        for year in sorted([y for y in chunks_by_year.keys() if y != 'unknown'] + 
                          [y for y in chunks_by_year.keys() if y == 'unknown']):
            print(f"   Year {year}: {len(chunks_by_year[year])} chunks")
        
        # ============================================================
        # STEP 3: PROCESS CHUNKS IN BATCHES BY YEAR (WITH CACHING)
        # ============================================================
        print(f"\n🧠 Step 3: Extracting claims from chunks (with caching)...")
        
        all_claims_by_year = {}
        all_structured_claims_by_year = {}
        total_claims = 0
        cache_hits = 0
        llm_calls = 0
        
        for year in sorted(chunks_by_year.keys(), 
                          key=lambda x: (x == 'unknown', x),
                          reverse=True):  # Process recent years first
            
            year_chunks = chunks_by_year[year]
            print(f"\n   Processing Year {year} ({len(year_chunks)} chunks)...")

            # Relevance filtering before LLM calls (top 10 chunks only)
            ranked_chunks = self._rank_chunks_by_relevance(
                year_chunks,
                query_text=target_claim or f"{company_name} esg climate emissions renewable net zero science-based targets"
            )
            year_chunks = ranked_chunks[:10]
            print(f"      🎯 Relevance filter: using top {len(year_chunks)} chunk(s)")
            
            # ========================================
            # CHECK CACHE FOR THIS YEAR'S CLAIMS
            # ========================================
            cached_claims = claim_extraction_cache.get_claims(company_name, year)
            
            if cached_claims:
                print(f"      ✅ Found {len(cached_claims)} cached claims for {company_name} ({year})")
                all_claims_by_year[year] = [c.get("claim_text", "") for c in cached_claims if c.get("claim_text")]
                all_structured_claims_by_year[year] = cached_claims
                cache_hits += 1
                continue
            
            claims_text = []
            structured_claims = []
            
            # Process chunks in batches
            for batch_start in range(0, len(year_chunks), self.CHUNK_BATCH_SIZE):
                # ========================================
                # RATE LIMIT PROTECTION
                # ========================================
                if llm_calls >= self.MAX_LLM_CALLS_PER_REPORT:
                    print(f"      ⚠️ Rate limit reached ({self.MAX_LLM_CALLS_PER_REPORT} LLM calls), stopping batch processing")
                    break
                
                batch_end = min(batch_start + self.CHUNK_BATCH_SIZE, len(year_chunks))
                batch = year_chunks[batch_start:batch_end]
                
                batch_num = batch_start // self.CHUNK_BATCH_SIZE + 1
                total_batches = (len(year_chunks) + self.CHUNK_BATCH_SIZE - 1) // self.CHUNK_BATCH_SIZE
                
                print(f"      Batch {batch_num}/{total_batches} ({len(batch)} chunks)...", end=" ")
                
                # Try chunk-level cache first to avoid redundant LLM calls
                batch_claims = {"claims": []}
                uncached_chunks = []
                for chunk in batch:
                    cached_chunk_claims = claim_extraction_cache.get_chunk_claims(
                        company=company_name,
                        year=year,
                        chunk_text=chunk.get("text", "")
                    )
                    if cached_chunk_claims is not None:
                        batch_claims["claims"].extend(cached_chunk_claims)
                        cache_hits += 1
                    else:
                        uncached_chunks.append(chunk)

                if uncached_chunks:
                    extracted_uncached = self._extract_claims_from_batch(company_name, uncached_chunks, year)
                    new_claims = extracted_uncached.get("claims", []) if isinstance(extracted_uncached, dict) else []
                    batch_claims["claims"].extend(new_claims)
                    # Do not cache batch claims against individual chunk keys,
                    # because one batch output may contain claims from multiple chunks.
                    # Year-level cache below remains the authoritative cache layer.
                    llm_calls += 1
                
                if batch_claims:
                    # Separate text claims and structured claims
                    for claim in batch_claims.get("claims", []):
                        claim_text = claim.get("claim_text", "")
                        if claim_text:
                            claims_text.append(claim_text)
                            structured_claims.append(claim)
                    
                    print(f"✅ {len(batch_claims.get('claims', []))} claims")
                else:
                    print(f"⚠️ No claims extracted")
            
            if claims_text:
                filtered_structured = self._filter_extracted_claims(structured_claims)
                dedup_structured = self._semantic_deduplicate_claims(filtered_structured)

                all_claims_by_year[year] = [c.get("claim_text", "") for c in dedup_structured if c.get("claim_text")]
                all_structured_claims_by_year[year] = dedup_structured
                # Cache the results
                claim_extraction_cache.store_claims(company_name, year, dedup_structured)
        
        # ============================================================
        # STEP 4: COMPILE RESULTS
        # ============================================================
        print(f"\n{'='*70}")
        print(f"📋 CLAIM EXTRACTION SUMMARY")
        print(f"{'='*70}")
        
        years_detected = sorted(
            [y for y in all_claims_by_year.keys() if y != 'unknown'] +
            [y for y in all_claims_by_year.keys() if y == 'unknown'],
            key=lambda x: (x == 'unknown', x),
            reverse=True
        )
        
        total_claims = sum(len(v) for v in all_structured_claims_by_year.values())
        print(f"Total claims extracted: {total_claims}")
        print(f"Years with claims: {years_detected}")
        print(f"📊 Cache hits: {cache_hits} | LLM calls: {llm_calls}")
        
        if all_claims_by_year:
            for year in years_detected:
                print(f"\n✅ Year {year}: {len(all_claims_by_year[year])} claims")
                for i, claim in enumerate(all_claims_by_year[year][:3], 1):
                    print(f"   {i}. {claim[:80]}...")
                if len(all_claims_by_year[year]) > 3:
                    print(f"   ... and {len(all_claims_by_year[year]) - 3} more")
        
        print(f"{'='*70}\n")
        
        return {
            "report_claims_by_year": all_claims_by_year,
            "claims_by_year_structured": all_structured_claims_by_year,
            "total_report_claims": sum(len(v) for v in all_structured_claims_by_year.values()),
            "years_detected": years_detected,
            "chunks_processed": len(filtered_chunks),
            "chunks_skipped": len(report_chunks) - len(filtered_chunks),
            "cache_hits": cache_hits,
            "llm_calls_made": llm_calls
        }

    def _rank_chunks_by_relevance(self, chunks: List[Dict[str, Any]], query_text: str) -> List[Dict[str, Any]]:
        """Deterministic token-overlap relevance scoring for claim-to-chunk filtering."""
        query_tokens = self._normalize_tokens(query_text)
        ranked = []

        for chunk in chunks:
            text = chunk.get("text", "")
            tokens = self._normalize_tokens(text)

            if not tokens:
                ranked.append((0.0, chunk))
                continue

            overlap = len(query_tokens & tokens) / max(1, len(query_tokens | tokens))
            has_numeric = 1.0 if re.search(r"\d", text) else 0.0
            has_target_terms = 1.0 if re.search(
                r"target|%|scope\s*[123]|emission|reduction|renewable|science[-\s]?based|net\s*zero",
                text,
                re.IGNORECASE,
            ) else 0.0

            score = (overlap * 0.6) + (has_numeric * 0.2) + (has_target_terms * 0.2)
            ranked.append((score, chunk))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in ranked]

    def _normalize_tokens(self, text: str) -> set:
        """Lowercase alphanumeric tokenization with short-word filtering."""
        tokens = re.findall(r"[a-zA-Z0-9\-]+", str(text).lower())
        stop = {
            "the", "and", "for", "with", "that", "this", "from", "have", "has", "are",
            "was", "were", "our", "their", "its", "into", "about", "more", "than"
        }
        return {t for t in tokens if len(t) > 2 and t not in stop}

    def _filter_extracted_claims(self, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep measurable ESG claims and reject generic aspirational statements."""
        generic_reject_patterns = [
            r"\bcommitted to\b",
            r"\baim to\b",
            r"\bcontinue to work\b",
            r"\bsustainability remains important\b",
        ]
        keep_patterns = [
            r"\btarget\b",
            r"\b\d+(?:\.\d+)?\s*%\b",
            r"\bemission(?:s)?\b",
            r"\breduction\b",
            r"\brenewable\b",
            r"\bscience[-\s]?based\b",
            r"\bnet\s*zero\b",
            r"\bscope\s*[123]\b",
        ]

        filtered = []
        for claim in claims:
            claim_text = str(claim.get("claim_text", "")).strip()
            if not claim_text:
                continue

            lower = claim_text.lower()
            has_keep_signal = any(re.search(p, lower, re.IGNORECASE) for p in keep_patterns)
            only_generic = any(re.search(p, lower, re.IGNORECASE) for p in generic_reject_patterns) and not has_keep_signal

            if only_generic:
                continue
            if not has_keep_signal:
                continue

            filtered.append(claim)

        return filtered

    def _semantic_deduplicate_claims(self, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate near-duplicate claims using token-set similarity."""
        unique = []
        seen_tokens = []

        for claim in claims:
            text = str(claim.get("claim_text", "")).strip()
            if not text:
                continue
            tokens = self._normalize_tokens(text)
            if not tokens:
                continue

            duplicate = False
            for prev in seen_tokens:
                sim = len(tokens & prev) / max(1, len(tokens | prev))
                if sim >= 0.75:
                    duplicate = True
                    break

            if not duplicate:
                unique.append(claim)
                seen_tokens.append(tokens)

        return unique
    
    def _filter_esg_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter chunks that contain ESG keywords
        Reduces unnecessary LLM calls by skipping irrelevant chunks
        """
        filtered = []
        keywords_lower = [kw.lower() for kw in self.ESG_KEYWORDS]
        
        for chunk in chunks:
            # Validate chunk has required fields
            if not chunk.get("text"):
                continue
            
            # Accept both parsed PDF and HTML ESG report chunks
            if chunk.get("source") not in ["esg_report", "html_esg_page"]:
                continue
            
            # Check for ESG keywords
            text_lower = chunk.get("text", "").lower()
            
            if any(keyword in text_lower for keyword in keywords_lower):
                filtered.append(chunk)
        
        return filtered
    
    def _group_chunks_by_year(self, chunks: List[Dict[str, Any]]) -> Dict[Any, List[Dict]]:
        """Group chunks by year for temporal analysis"""
        grouped = {}
        
        for chunk in chunks:
            year = chunk.get("year", "unknown")
            
            if year not in grouped:
                grouped[year] = []
            
            grouped[year].append(chunk)
        
        return grouped
    
    def _extract_claims_from_batch(self, company_name: str, 
                                  batch_chunks: List[Dict[str, Any]],
                                  year: Any) -> Dict[str, Any]:
        """
        Extract claims from a batch of chunks (3 chunks max per batch)
        Prevents oversized LLM prompts
        """
        
        # Combine batch chunks into single text
        combined_text = "\n\n---CHUNK BOUNDARY---\n\n".join(
            chunk.get("text", "") for chunk in batch_chunks
        )
        
        # Build prompt for batch
        prompt = f"""{CLAIM_EXTRACTION_PROMPT}

COMPANY: {company_name}
YEAR: {year}
SOURCE: ESG Report

CONTENT TO ANALYZE:
{combined_text[:4000]}

ADDITIONAL INSTRUCTION: Extract ESG-specific claims, focusing on sustainability commitments, environmental goals, and climate targets relevant to the year {year}.

Return ONLY valid JSON in the exact format specified. No markdown, no explanations."""

        try:
            # Call LLM
            response = self.llm.call_with_fallback(prompt, use_gemini_first=True)

            if not response:
                print(f"         ❌ LLM call failed")
                return {}

            claims_data = self._parse_claims_json_response(
                response,
                company_name=company_name,
                year=year
            )

            # Validate structure
            if "claims" not in claims_data or not isinstance(claims_data.get("claims"), list):
                return {}

            # Ensure each claim has year metadata
            for claim in claims_data["claims"]:
                if "year" not in claim:
                    claim["year"] = year

            return claims_data

        except Exception as e:
            print(f"         ⚠️ Error processing batch: {e}")
            return {}
    
    def _deduplicate_claims(self, claims: List[str]) -> List[str]:
        """
        Remove duplicate or near-duplicate claims
        Uses simple string similarity to detect duplicates
        """
        if not claims:
            return []
        
        unique_claims = []
        seen_claims = set()
        
        for claim in claims:
            claim_lower = claim.lower().strip()
            
            # Skip if we've seen an identical claim
            if claim_lower in seen_claims:
                continue
            
            # Skip if very similar to existing claim (naive similarity)
            is_duplicate = False
            for seen in seen_claims:
                # Simple check: if 80% of words match, consider it duplicate
                claim_words = set(claim_lower.split())
                seen_words = set(seen.split())
                
                if claim_words and seen_words:
                    overlap = len(claim_words & seen_words) / max(len(claim_words), len(seen_words))
                    
                    if overlap > 0.8:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_claims.append(claim)
                seen_claims.add(claim_lower)
        
        return unique_claims
