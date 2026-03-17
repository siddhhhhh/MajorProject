"""
Evidence Retrieval & Cross-Verification Specialist
With intelligent relevance filtering to prevent cross-contamination
"""

import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.llm_client import llm_client
from core.vector_store import vector_store
from utils.enterprise_data_sources import enterprise_fetcher
from utils.web_search import classify_source
from config.agent_prompts import EVIDENCE_RETRIEVAL_PROMPT
from core.evidence_cache import evidence_cache
import time


class EvidenceRetriever:
    def __init__(self):
        self.name = "Evidence Retrieval & Cross-Verification Specialist"
        self.llm = llm_client
        self.vector_store = vector_store
        self.enterprise_fetcher = enterprise_fetcher
        from utils.free_data_sources import free_data_aggregator
        self.data_aggregator = free_data_aggregator
        
        # Try importing financial analyst
        try:
            from agents.financial_analyst import get_financial_context
            self.financial_analyst_available = True
            self.get_financial_context = get_financial_context
        except ImportError:
            self.financial_analyst_available = False
            print("⚠️ FinancialAnalyst not available")
        
        # Company report fetcher for PDF reports
        try:
            from utils.company_report_fetcher import get_report_fetcher
            self.report_fetcher = get_report_fetcher()
            self.report_fetcher_available = True
        except ImportError:
            self.report_fetcher_available = False
            print("⚠️ CompanyReportFetcher not available")
        
        # Indian financial data for revenue
        try:
            from utils.indian_financial_data import get_indian_financial_data
            self.indian_financial = get_indian_financial_data()
            self.indian_financial_available = True
        except ImportError:
            self.indian_financial_available = False
            print("⚠️ IndianFinancialData not available")

        self.source_weights = {
            "company_esg_report": 0.65,
            "sec_filing": 0.95,
            "cdp_disclosure": 0.98,
            "third_party_audit": 1.0,
            "ngo_report": 0.8,
            "major_news": 0.6,
            "aggregator": 0.3,
            "default": 0.5
        }
    
    def retrieve_evidence(self, claim: Dict[str, Any], company: str) -> Dict[str, Any]:
        """
        Gather LIVE multi-source evidence - ENTERPRISE GRADE
        With relevance filtering to prevent cross-contamination
        WITH INTELLIGENT CACHING to prevent redundant API calls
        """
        
        claim_id = claim.get("claim_id")
        claim_text = claim.get("claim_text", "")
        category = claim.get("category", "")
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 2: {self.name}")
        print(f"{'='*60}")
        print(f"Claim ID: {claim_id}")
        print(f"Claim: {claim_text[:100]}...")
        print(f"Category: {category}")
        
        # ============================================================
        # STEP 1: CHECK EVIDENCE CACHE
        # ============================================================
        cache_key = "main_evidence"
        cached_result = evidence_cache.get_evidence(company, cache_key)
        
        if cached_result:
            print(f"✅ Using cached evidence - ZERO API calls")
            return cached_result
        
        # ============================================================
        # STEP 2: CACHE MISS - Fetch from 14 sources (ONLY ONCE)
        # ============================================================
        print(f"🌐 CACHE MISS - Fetching from 15 sources for {company}...")
        
        # Generate targeted search query
        query = f'"{company}" {category} {claim_text[:50]}'
        
        # 1. Search vector store for historical context
        print(f"\n🗄️ Searching vector database...")
        vector_results = self.vector_store.search_similar(claim_text, n_results=5)
        vector_evidence = self._process_vector_results(vector_results)
        print(f"   Found: {len(vector_evidence)} stored documents")
        
        # 2. ENTERPRISE MULTI-SOURCE FETCH
        # REPLACE existing API calls with this:
        print(f"\n🌐 Fetching from 15 FREE sources...")
        all_sources = self.data_aggregator.fetch_all_sources(
            company=company,
            query=f"{company} {claim_text[:50]}",
            max_per_source=10
        )

        # Flatten all sources
        all_evidence = []
        for category, items in all_sources.items():
            all_evidence.extend(items)

        print(f"\n📊 RAW EVIDENCE COLLECTED: {len(all_evidence)} from 15 APIs")

        
        # 4. FILTER BY RELEVANCE (NEW - Prevents Apple for BP contamination)
        print(f"🔍 Filtering for relevance to {company}...")
        filtered_evidence = self._filter_relevant_evidence(all_evidence, company, claim_text)
        
        filtered_count = len(all_evidence) - len(filtered_evidence)
        if filtered_count > 0:
            print(f"   ⏭️  Filtered out {filtered_count} irrelevant sources")
        print(f"   ✅ Relevant sources: {len(filtered_evidence)}")
        
        # Count by source API
        source_breakdown = {}
        for ev in filtered_evidence:
            api_source = ev.get('data_source_api', 'Unknown')
            source_breakdown[api_source] = source_breakdown.get(api_source, 0) + 1
        
        print(f"\n   Source breakdown:")
        for api_source, count in sorted(source_breakdown.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {api_source}: {count}")
        
        # 5. Structure and classify evidence with AI
        print(f"\n📝 Analyzing evidence relationships...")
        structured_evidence = self._structure_evidence(filtered_evidence, claim_text)
        
        # 6. Store in vector DB
        self._store_evidence_in_vectordb(structured_evidence, company, claim_id)
        
        # 7. Calculate comprehensive quality metrics
        quality_metrics = self._calculate_quality_metrics(structured_evidence, source_breakdown)
        
        # NEW: Add financial context analysis
        financial_context = {}
        if self.financial_analyst_available:
            try:
                print(f"\n💰 Fetching financial context...")
                
                # Extract ESG data from claim or use defaults
                esg_data = {
                    "CarbonEmissions": claim.get("carbon_emissions", 0),
                    "WaterUsage": claim.get("water_usage", 0),
                    "EnergyConsumption": claim.get("energy_consumption", 0),
                    "ESG_Overall": claim.get("esg_score", 50)
                }
                
                financial_context = self.get_financial_context(company, claim_text, esg_data)
                
                if financial_context.get("financial_data_available"):
                    print(f"   ✅ Financial data retrieved")
                    print(f"   Greenwashing flags: {financial_context.get('greenwashing_flag_count', 0)}")
            except Exception as e:
                print(f"   ⚠️ Financial analysis error: {e}")
                financial_context = {"financial_data_available": False}
        
        # NEW: Fetch company reports (PDF) from official website
        company_reports = {}
        if self.report_fetcher_available:
            try:
                print(f"\n📄 Fetching official company reports...")
                company_reports = self.report_fetcher.fetch_company_reports(
                    company, 
                    report_types=["annual_report", "sustainability_report", "brsr_report"],
                    max_reports=3
                )
                
                if company_reports.get("reports_found"):
                    print(f"   ✅ Found {len(company_reports['reports_found'])} reports")
                    # Add extracted metrics to financial context
                    if company_reports.get("extracted_data"):
                        financial_context["report_metrics"] = company_reports["extracted_data"]
                        print(f"   📊 Extracted {len(company_reports['extracted_data'])} metrics from PDFs")
                else:
                    print(f"   ⚠️ No official reports found")
            except Exception as e:
                print(f"   ⚠️ Report fetcher error: {e}")
        
        # NEW: Fetch Indian financial data (revenue, profit)
        indian_financials = {}
        if self.indian_financial_available:
            try:
                # Check if likely Indian company
                indian_indicators = ['reliance', 'tata', 'infosys', 'wipro', 'hdfc', 'icici', 
                                     'bharti', 'airtel', 'adani', 'mahindra', 'bajaj', 'jsw',
                                     'vedanta', 'hindalco', 'ultratech', 'asian paints', 'titan',
                                     'nestle india', 'maruti', 'ntpc', 'ongc', 'coal india',
                                     'sbi', 'kotak', 'axis', 'itc', 'hindustan', 'larsen']
                
                company_lower = company.lower()
                is_indian = any(ind in company_lower for ind in indian_indicators)
                
                if is_indian:
                    print(f"\n🇮🇳 Fetching Indian financial data...")
                    indian_financials = self.indian_financial.get_company_financials(company)
                    
                    if indian_financials.get("financials"):
                        fin = indian_financials["financials"]
                        print(f"   ✅ Financial data retrieved")
                        if fin.get("revenue"):
                            print(f"   📈 Revenue: ₹{fin['revenue']:,.0f} Cr")
                        if fin.get("net_profit"):
                            print(f"   💰 Net Profit: ₹{fin['net_profit']:,.0f} Cr")
                        if fin.get("market_cap"):
                            print(f"   📊 Market Cap: ₹{fin['market_cap']:,.0f} Cr")
                        
                        # Add to financial context
                        financial_context["indian_financials"] = indian_financials
            except Exception as e:
                print(f"   ⚠️ Indian financial data error: {e}")
        
        print(f"\n✅ Evidence retrieval complete:")
        print(f"   Total sources: {len(structured_evidence)}")
        print(f"   Independent sources: {quality_metrics['independent_sources']}")
        print(f"   Premium sources: {quality_metrics['premium_sources']}")
        print(f"   Avg freshness: {quality_metrics['avg_freshness_days']:.1f} days")
        print(f"   Source diversity: {quality_metrics['source_diversity']} types")
        print(f"   Evidence gap: {'YES ⚠️' if quality_metrics['evidence_gap'] else 'NO ✓'}")
        if company_reports.get("reports_found"):
            print(f"   Official reports: {len(company_reports['reports_found'])} PDF(s)")
        if indian_financials.get("financials"):
            print(f"   Indian financials: Available")
        
        result = {
            "claim_id": claim_id,
            "evidence": structured_evidence,
            "contradicting_evidence": [
                e for e in structured_evidence
                if str(e.get("stance", "")).lower() == "contradicts"
            ],
            "evidence_gap": quality_metrics['evidence_gap'],
            "quality_metrics": quality_metrics,
            "source_breakdown": source_breakdown,
            "financial_context": financial_context,
            "company_reports": company_reports,
            "indian_financials": indian_financials,
            "retrieval_timestamp": datetime.now().isoformat()
        }
        
        # ============================================================
        # STEP 3: STORE IN CACHE for other agents to reuse
        # ============================================================
        evidence_cache.store_evidence(company, result, cache_key)
        
        return result
    
    def _filter_relevant_evidence(self, evidence: List[Dict], company: str, claim_text: str) -> List[Dict]:
        """
        Filter evidence to ensure relevance to company and claim
        Removes cached cross-contamination (e.g., Apple results for BP query)
        """
        
        filtered = []
        company_lower = company.lower()
        company_aliases = {
            company_lower,
            company_lower.replace(" plc", "").strip(),
            company_lower.replace(" ltd", "").strip(),
            company_lower.replace(" limited", "").strip(),
            company_lower.replace(" corporation", "").strip(),
            company_lower.replace(" corp", "").strip(),
            company_lower.replace(" inc", "").strip(),
            company_lower.replace(" group", "").strip(),
        }
        # Add meaningful tokens as aliases to capture headline shorthand.
        company_aliases.update(t for t in company_lower.replace("-", " ").replace("&", " ").split() if len(t) > 2)
        claim_keywords = set(claim_text.lower().split())
        
        # Common company names to detect wrong results
        company_indicators = {
            'apple', 'tesla', 'microsoft', 'google', 'amazon', 'meta', 'facebook',
            'shell', 'exxon', 'chevron', 'bp', 'totalenergies', 'conocophillips',
            'coca-cola', 'pepsi', 'nestle', 'unilever', 'nike', 'adidas', 'puma',
            'walmart', 'target', 'costco', 'ford', 'gm', 'volkswagen', 'toyota'
        }
        
        for item in evidence:
            # Check if company name appears in title or snippet
            title = item.get('title', '').lower()
            snippet = item.get('snippet', '').lower()
            url = item.get('url', '').lower()
            combined_text = f"{title} {snippet} {url}"
            
            # Prefer company mention via any alias/token
            mentions_company = any(alias and alias in combined_text for alias in company_aliases)
            
            # Or mentions key claim concepts (at least 2 keywords)
            claim_relevance_score = sum(
                1 for kw in claim_keywords 
                if kw in combined_text and len(kw) > 3
            )
            
            # Check if it's about a DIFFERENT company
            wrong_company = None
            for other_company in company_indicators:
                if other_company not in company_aliases and other_company in combined_text:
                    # If the other company is mentioned MORE than target company
                    other_count = combined_text.count(other_company)
                    target_count = max(combined_text.count(alias) for alias in company_aliases if alias)
                    
                    if other_count > target_count:
                        wrong_company = other_company
                        break
            
            # Include if:
            # 1. Mentions target company, OR
            # 2. Has high claim relevance (3+ keywords) AND no wrong company detected
            if mentions_company or (claim_relevance_score >= 3 and not wrong_company):
                filtered.append(item)
            elif wrong_company:
                print(f"      ⏭️  Filtered: '{item.get('title', 'Unknown')[:60]}...' (mentions {wrong_company.title()}, not {company})")

        # Controlled fallback: if strict filtering is too aggressive, recover top claim-relevant items.
        if len(filtered) < 10 and evidence:
            needed = 10 - len(filtered)
            candidates = []
            for item in evidence:
                if item in filtered:
                    continue
                title = item.get('title', '').lower()
                snippet = item.get('snippet', '').lower()
                url = item.get('url', '').lower()
                combined_text = f"{title} {snippet} {url}"
                score = sum(1 for kw in claim_keywords if len(kw) > 3 and kw in combined_text)
                if score >= 4:
                    candidates.append((score, item))

            candidates.sort(key=lambda x: x[0], reverse=True)
            recovered = [item for _, item in candidates[:needed]]
            if recovered:
                print(f"      ↩️ Recovered {len(recovered)} high-relevance items to maintain source robustness")
                filtered.extend(recovered)
        
        return filtered
    
    def _structure_evidence(self, raw_evidence: List[Dict], claim: str) -> List[Dict]:
        """Structure and classify evidence with AI relationship determination"""
        
        structured = []
        skipped_count = 0
        deduplicated_count = 0
        
        print(f"   Analyzing {len(raw_evidence)} sources with AI...", flush=True)
        
        # [FIX 2] Track (domain + source_type) pairs for proper deduplication
        # Counts valid evidence sources using domain + source_type instead of domain-only
        seen_sources = set()
        domain_extract = lambda url: url.split('/')[2] if url.count('/') >= 2 else url
        
        for i, ev in enumerate(raw_evidence):
            if i % 10 == 0 and i > 0:
                print(f"   Progress: {i}/{len(raw_evidence)}...", flush=True)
            
            # PHASE 5 FIX: Skip sources without URL (invalid sources)
            url = ev.get("url", "").strip()
            if not url:
                skipped_count += 1
                continue
            
            # Classify source type
            source_type = classify_source(url, ev.get("source", ""))
            
            # Override with explicit type if provided
            if ev.get("source_type"):
                source_type = ev.get("source_type")
            
            # [FIX 2] Create unique key using domain + source_type (not domain-only)
            domain = domain_extract(url)
            unique_key = f"{domain}|{source_type}"
            
            if unique_key in seen_sources:
                # Skip duplicate (same domain + source type combination)
                deduplicated_count += 1
                continue
            
            seen_sources.add(unique_key)
            
            # Determine relationship using LLM (fast Groq)
            relationship = self._determine_relationship(claim, ev.get("snippet", ""))
            weight = self._get_source_weight(ev, source_type)
            
            # Calculate freshness
            freshness = self._calculate_freshness(ev.get("date", ""))
            
            structured.append({
                "source_id": f"ev_{i:03d}",
                "source_name": ev.get("source", "Unknown"),
                "source_type": source_type,
                "url": url,  # Already validated above
                "domain": domain,  # NEW: Store domain for reference
                "date": ev.get("date", datetime.now().isoformat()),
                "relevant_text": ev.get("snippet", "")[:500],
                "relationship_to_claim": relationship,
                    "stance": relationship,
                "evidence_weight": weight,
                "data_freshness_days": freshness,
                "data_source_api": ev.get("data_source_api", "Unknown"),
                "retrieval_timestamp": datetime.now().isoformat()
            })
        
        if skipped_count > 0:
            print(f"   ⏭️  Skipped {skipped_count} sources without URLs (invalid)")
        if deduplicated_count > 0:
            print(f"   ⏭️  Deduplicated {deduplicated_count} sources (domain+type matches)")
        print(f"   ✓ Analysis complete ({len(structured)} valid unique sources)")
        
        # [FIX 3] Normalize evidence metadata - ensure all required fields are present
        print(f"   Normalizing evidence metadata...")
        normalized = [self._normalize_evidence(ev) for ev in structured]
        print(f"   [Fix] Evidence metadata normalized: {len(normalized)} items processed")
        
        # Rank evidence by source weight, then by freshness
        normalized.sort(
            key=lambda x: (
                x.get("evidence_weight", self.source_weights["default"]),
                -x.get("data_freshness_days", 999)
            ),
            reverse=True
        )

        return normalized

    def _get_source_weight(self, ev: Dict[str, Any], source_type: str) -> float:
        """Map evidence source to quality weight for downstream risk scoring."""
        url = str(ev.get("url", "")).lower()
        source_name = str(ev.get("source", "")).lower()
        title = str(ev.get("title", "")).lower()
        combined = f"{url} {source_name} {title}"

        if any(k in combined for k in ["sustainability-report", "esg-report", "annualreport", "brsr"]):
            return self.source_weights["company_esg_report"]
        if any(k in combined for k in ["tcfd", "assurance report", "limited assurance", "reasonable assurance", "isae 3000", "assurance statement"]):
            return self.source_weights["third_party_audit"]
        if any(k in combined for k in ["sec.gov", "10-k", "10k", "10-q", "20-f"]):
            return self.source_weights["sec_filing"]
        if "cdp" in combined:
            return self.source_weights["cdp_disclosure"]
        if any(k in combined for k in ["greenpeace", "wwf", "environmental defense", "ngo"]):
            return self.source_weights["ngo_report"]
        if any(k in combined for k in ["reuters", "bloomberg", "ft.com", "wsj", "economist"]):
            return self.source_weights["major_news"]
        if any(k in combined for k in ["duckduckgo", "news.google", "yahoo", "aggregator"]):
            return self.source_weights["aggregator"]
        if source_type in ["Government/Regulatory", "Academic"]:
            return 0.9

        return self.source_weights["default"]
    
    def _determine_relationship(self, claim: str, evidence: str) -> str:
        """Use FAST LLM (Groq) to determine relationship"""
        
        if not evidence or len(evidence) < 20:
            return "Neutral"
        
        prompt = EVIDENCE_RETRIEVAL_PROMPT.format(
            claim=claim[:200],
            evidence=evidence[:500]
        )
        
        # Use fast Groq model for speed
        response = self.llm.call_groq(
            [{"role": "user", "content": prompt}],
            temperature=0,
            use_fast=True
        )
        
        if response and any(word in response for word in ["Supports", "Contradicts", "Neutral", "Partial"]):
            for word in ["Supports", "Contradicts", "Partial", "Neutral"]:
                if word in response:
                    return word
        
        return "Neutral"
    
    def _normalize_evidence(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        [FIX 3] Normalize evidence metadata to ensure all required fields are present
        Every evidence item must include: title, source, url, date
        Prevents "Unknown" / "N/A" placeholders in final output
        """
        import uuid
        
        normalized = {
            "source_id": item.get("source_id", f"ev_{uuid.uuid4().hex[:8]}"),
            "title": item.get("source_name") or 
                    item.get("title") or 
                    "Unknown Source",
            "source": item.get("source_name") or 
                     item.get("source") or 
                     item.get("data_source_api") or 
                     "Unknown",
            "url": item.get("url", ""),
            "domain": item.get("domain", ""),
            "date": item.get("date") or datetime.now().isoformat(),
            "content": item.get("relevant_text", ""),
            "snippet": item.get("relevant_text", "")[:200],
            "source_type": item.get("source_type", "Unknown"),
            "relationship_to_claim": item.get("relationship_to_claim", "Neutral"),
            "evidence_weight": item.get("evidence_weight", self.source_weights["default"]),
            "data_freshness_days": item.get("data_freshness_days", 999),
            "data_source_api": item.get("data_source_api", "Unknown"),
            "retrieval_timestamp": item.get("retrieval_timestamp", datetime.now().isoformat()),
            "date_retrieved": datetime.now().date().isoformat(),
            "source_name": item.get("source_name") or item.get("source") or "Unknown",
            "reliability_tier": item.get("source_type", "Web")
        }
        
        # Validate critical fields
        if normalized["title"] == "Unknown Source" or normalized["title"] == "Unknown":
            normalized["title"] = f"Source: {normalized['source']}"
        
        if not normalized["url"] or normalized["url"] == "":
            normalized["url"] = ""
            normalized["evidence_weight"] = min(float(normalized["evidence_weight"]), 0.2)
            normalized["reliability_tier"] = "UNVERIFIABLE"
            print(f"   ⚠️ UNVERIFIABLE evidence downweighted: {normalized['title'][:60]}")
        
        return normalized
    
    def _calculate_freshness(self, date_str: str) -> int:
        """Calculate days since publication"""
        
        if not date_str:
            return 999
        
        try:
            from dateutil import parser
            date = parser.parse(date_str)
            now = datetime.now(date.tzinfo) if date.tzinfo else datetime.now()
            return max(0, (now - date).days)
        except:
            return 999
    
    def _process_vector_results(self, results: Dict) -> List[Dict]:
        """Process Chroma vector store results"""
        
        evidence = []
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        
        for i, (doc, meta) in enumerate(zip(docs, metadatas)):
            evidence.append({
                "source": meta.get("source", "Vector Store"),
                "url": meta.get("url", ""),
                "snippet": doc[:300],
                "date": meta.get("date", ""),
                "data_source_api": "Vector Database (Historical)",
                "source_type": meta.get("type", "Database")
            })
        
        return evidence
    
    def _store_evidence_in_vectordb(self, evidence: List[Dict], company: str, claim_id: int):
        """Store evidence in vector DB for future queries"""
        
        try:
            documents = []
            metadatas = []
            ids = []
            
            for i, ev in enumerate(evidence[:20]):  # Store top 20
                doc_id = f"{company}_{claim_id}_{i}_{int(time.time())}"
                
                documents.append(ev.get("relevant_text", ""))
                metadatas.append({
                    "company": company,
                    "claim_id": claim_id,
                    "source": ev.get("source_name", ""),
                    "url": ev.get("url", ""),
                    "date": ev.get("date", ""),
                    "type": ev.get("source_type", "")
                })
                ids.append(doc_id)
            
            if documents:
                self.vector_store.add_documents(documents, metadatas, ids)
        
        except Exception as e:
            print(f"   ⚠️ Vector store error: {e}")
    
    def _calculate_quality_metrics(self, evidence: List[Dict], source_dict: Dict) -> Dict[str, Any]:
        """
        Calculate comprehensive evidence quality metrics
        """
        
        if not evidence:
            return {
                "evidence_gap": True,
                "independent_sources": 0,
                "premium_sources": 0,
                "avg_freshness_days": 999,
                "source_diversity": 0,
                "total_sources": 0,
                "source_type_breakdown": {},
                "api_source_breakdown": {}
            }
        
        # Count independent sources
        independent = sum(1 for ev in evidence
                         if ev.get("source_type") not in ["Company-Controlled", "Sponsored Content"])
        
        # Count premium sources
        premium_types = ["Tier-1 Financial Media", "Government/Regulatory", "Academic", "NGO"]
        premium = sum(1 for ev in evidence
                     if ev.get("source_type") in premium_types)
        
        # Average freshness
        freshness_values = [ev.get("data_freshness_days", 999) for ev in evidence]
        avg_freshness = sum(freshness_values) / len(freshness_values) if freshness_values else 999
        
        # Source type diversity
        source_types = set(ev.get("source_type") for ev in evidence)

        weighted_quality = round(
            (sum(float(ev.get("evidence_weight", self.source_weights["default"])) for ev in evidence) / len(evidence)) * 100,
            1,
        ) if evidence else 0
        
        # Source type breakdown
        type_breakdown = {}
        for ev in evidence:
            stype = ev.get("source_type", "Unknown")
            type_breakdown[stype] = type_breakdown.get(stype, 0) + 1
        
        # API source breakdown
        api_breakdown = {}
        for ev in evidence:
            api_source = ev.get("data_source_api", "Unknown")
            api_breakdown[api_source] = api_breakdown.get(api_source, 0) + 1
        
        # Calculate diversity score
        diversity_score = min(100, len(source_types) * 20)
        
        # Evidence gap check
        evidence_gap = independent < 3
        
        # Coverage score
        total_api_sources = len([k for k in source_dict.keys() if source_dict[k]])
        coverage_score = (total_api_sources / 6) * 100  # 6 main source types
        
        return {
            "evidence_gap": evidence_gap,
            "independent_sources": independent,
            "premium_sources": premium,
            "avg_freshness_days": round(avg_freshness, 1),
            "source_diversity": len(source_types),
            "diversity_score": diversity_score,
            "weighted_quality_score": weighted_quality,
            "coverage_score": round(coverage_score, 1),
            "total_sources": len(evidence),
            "source_type_breakdown": type_breakdown,
            "api_source_breakdown": api_breakdown
        }
