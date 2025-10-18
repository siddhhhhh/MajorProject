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
import time


class EvidenceRetriever:
    def __init__(self):
        self.name = "Evidence Retrieval & Cross-Verification Specialist"
        self.llm = llm_client
        self.vector_store = vector_store
        self.enterprise_fetcher = enterprise_fetcher
    
    def retrieve_evidence(self, claim: Dict[str, Any], company: str) -> Dict[str, Any]:
        """
        Gather LIVE multi-source evidence - ENTERPRISE GRADE
        With relevance filtering to prevent cross-contamination
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
        
        # Generate targeted search query
        query = f'"{company}" {category} {claim_text[:50]}'
        
        # 1. Search vector store for historical context
        print(f"\n🗄️ Searching vector database...")
        vector_results = self.vector_store.search_similar(claim_text, n_results=5)
        vector_evidence = self._process_vector_results(vector_results)
        print(f"   Found: {len(vector_evidence)} stored documents")
        
        # 2. ENTERPRISE MULTI-SOURCE FETCH
        print(f"\n🌐 Fetching from ENTERPRISE sources...")
        source_dict = self.enterprise_fetcher.fetch_all_sources(
            company=company,
            query=query,
            max_per_source=5
        )
        
        # 3. Aggregate all sources
        all_evidence = []
        for source_type, results in source_dict.items():
            for result in results:
                all_evidence.append(result)
        
        print(f"\n📊 RAW EVIDENCE COLLECTED: {len(all_evidence)} sources")
        
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
        quality_metrics = self._calculate_quality_metrics(structured_evidence, source_dict)
        
        print(f"\n✅ Evidence retrieval complete:")
        print(f"   Total sources: {len(structured_evidence)}")
        print(f"   Independent sources: {quality_metrics['independent_sources']}")
        print(f"   Premium sources: {quality_metrics['premium_sources']}")
        print(f"   Avg freshness: {quality_metrics['avg_freshness_days']:.1f} days")
        print(f"   Source diversity: {quality_metrics['source_diversity']} types")
        print(f"   Evidence gap: {'YES ⚠️' if quality_metrics['evidence_gap'] else 'NO ✓'}")
        
        return {
            "claim_id": claim_id,
            "evidence": structured_evidence,
            "evidence_gap": quality_metrics['evidence_gap'],
            "quality_metrics": quality_metrics,
            "source_breakdown": source_breakdown,
            "retrieval_timestamp": datetime.now().isoformat()
        }
    
    def _filter_relevant_evidence(self, evidence: List[Dict], company: str, claim_text: str) -> List[Dict]:
        """
        Filter evidence to ensure relevance to company and claim
        Removes cached cross-contamination (e.g., Apple results for BP query)
        """
        
        filtered = []
        company_lower = company.lower()
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
            
            # Must mention the company
            mentions_company = company_lower in combined_text
            
            # Or mentions key claim concepts (at least 2 keywords)
            claim_relevance_score = sum(
                1 for kw in claim_keywords 
                if kw in combined_text and len(kw) > 3
            )
            
            # Check if it's about a DIFFERENT company
            wrong_company = None
            for other_company in company_indicators:
                if other_company != company_lower and other_company in combined_text:
                    # If the other company is mentioned MORE than target company
                    other_count = combined_text.count(other_company)
                    target_count = combined_text.count(company_lower)
                    
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
        
        return filtered
    
    def _structure_evidence(self, raw_evidence: List[Dict], claim: str) -> List[Dict]:
        """Structure and classify evidence with AI relationship determination"""
        
        structured = []
        
        print(f"   Analyzing {len(raw_evidence)} sources with AI...", flush=True)
        
        for i, ev in enumerate(raw_evidence):
            if i % 10 == 0 and i > 0:
                print(f"   Progress: {i}/{len(raw_evidence)}...", flush=True)
            
            # Classify source type
            source_type = classify_source(ev.get("url", ""), ev.get("source", ""))
            
            # Override with explicit type if provided
            if ev.get("source_type"):
                source_type = ev.get("source_type")
            
            # Determine relationship using LLM (fast Groq)
            relationship = self._determine_relationship(claim, ev.get("snippet", ""))
            
            # Calculate freshness
            freshness = self._calculate_freshness(ev.get("date", ""))
            
            structured.append({
                "source_id": f"ev_{i:03d}",
                "source_name": ev.get("source", "Unknown"),
                "source_type": source_type,
                "url": ev.get("url", ""),
                "date": ev.get("date", datetime.now().isoformat()),
                "relevant_text": ev.get("snippet", "")[:500],
                "relationship_to_claim": relationship,
                "data_freshness_days": freshness,
                "data_source_api": ev.get("data_source_api", "Unknown"),
                "retrieval_timestamp": datetime.now().isoformat()
            })
        
        print(f"   ✓ Analysis complete")
        return structured
    
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
            "coverage_score": round(coverage_score, 1),
            "total_sources": len(evidence),
            "source_type_breakdown": type_breakdown,
            "api_source_breakdown": api_breakdown
        }
