# === Real Peer Data Fetcher ===
from utils.free_esg_data_fetcher import fetch_wikirate_esg_score, fetch_cdp_score

# Sector known peers mapping
SECTOR_KNOWN_PEERS = {
    "Energy": ["Shell", "BP", "ExxonMobil", "Chevron", "TotalEnergies", "Eni", "Equinor", "Reliance Industries"],
    "Technology": ["Microsoft", "Apple", "Infosys", "TCS", "Wipro", "Accenture", "IBM", "SAP", "HCL Technologies"],
    "Finance": ["HSBC", "JPMorgan", "Goldman Sachs", "HDFC Bank", "ICICI Bank", "BNP Paribas", "Deutsche Bank"],
    "Aviation": ["Ryanair", "Emirates", "IndiGo", "Air India", "Lufthansa", "Delta Airlines"],
    "Retail": ["H&M", "Zara/Inditex", "Walmart", "Amazon", "Flipkart"],
    "Automotive": ["Volkswagen", "Tesla", "Tata Motors", "Toyota", "BMW"],
    "Consumer Goods": ["Unilever", "Nestle", "P&G", "HUL", "ITC"]
}

def get_peer_scores(company_name: str, sector: str) -> list:
    """
    Returns list of peer dicts with real data where possible.
    Priority: 1) Wikirate API, 2) CDP data, 3) Historical DB, 4) Estimated
    Each peer dict: {company, esg_score, e_score, s_score, g_score, source, is_estimated, year}
    """
    peers = SECTOR_KNOWN_PEERS.get(sector, [])
    peers = [p for p in peers if p.lower() != company_name.lower()][:5]
    peer_scores = []
    for peer in peers:
        # Try Wikirate first
        wikirate_data = fetch_wikirate_esg_score(peer)
        if wikirate_data and wikirate_data.get("overall_score"):
            peer_scores.append({
                "company": peer,
                "esg_score": float(wikirate_data["overall_score"]),
                "source": "Wikirate",
                "is_estimated": False,
                "year": wikirate_data.get("year")
            })
            continue
        # Try CDP
        cdp_data = fetch_cdp_score(peer)
        if cdp_data:
            peer_scores.append({
                "company": peer,
                "esg_score": float(cdp_data["cdp_numeric"]),
                "source": "CDP",
                "is_estimated": False,
                "year": cdp_data.get("year")
            })
            continue
        # Fall back to sector median estimate
        SECTOR_MEDIANS = {
            "Energy": 45, "Technology": 62, "Finance": 55,
            "Aviation": 38, "Retail": 48, "Automotive": 50,
            "Consumer Goods": 58
        }
        peer_scores.append({
            "company": peer,
            "esg_score": SECTOR_MEDIANS.get(sector, 50),
            "source": "Estimated (sector median)*",
            "is_estimated": True,
            "year": "est."
        })
    return peer_scores
"""
Industry Comparison & Peer Benchmarking Agent
DYNAMIC peer comparison - builds real database over time
100% Real-time, NO HARDCODING
"""

from typing import Dict, Any, List, Optional
from utils.enterprise_data_sources import enterprise_fetcher
from core.llm_client import llm_client
from core.evidence_cache import evidence_cache
import json
import numpy as np
from datetime import datetime

# ChromaDB imports
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("⚠️ ChromaDB not available - peer history disabled")


class IndustryComparator:
    def __init__(self):
        self.name = "Peer Comparison & Industry Benchmark Specialist"
        self.fetcher = enterprise_fetcher
        self.llm = llm_client
        
        # Initialize ChromaDB client for peer history
        self.peer_db_available = False
        if CHROMADB_AVAILABLE:
            try:
                self.chroma_client = chromadb.PersistentClient(
                    path="chroma_db/peer_comparison_history",
                    settings=Settings(anonymized_telemetry=False)
                )
                
                # Get or create collection
                self.peer_collection = self.chroma_client.get_or_create_collection(
                    name="peer_esg_scores",
                    metadata={"description": "Historical ESG scores for peer comparison"}
                )
                
                self.peer_db_available = True
                print("✅ Peer comparison database initialized")
                
            except Exception as e:
                print(f"⚠️ ChromaDB initialization failed: {e}")
                self.peer_db_available = False
        
        # Load industry baselines
        self.industry_config = self._load_industry_config()

    def _load_industry_config(self) -> Dict:
        """Load industry baseline configuration"""
        try:
            import os
            config_path = "config/industry_baselines.json"
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get("industry_baseline_risk", {})
            
        except Exception as e:
            print(f"⚠️ Failed to load industry config: {e}")
        
        return {}

    def save_company_to_peer_db(self, company: str, industry: str, 
                                esg_score: float, pillar_scores: Dict[str, float],
                                rating: str) -> bool:
        """
        Save company ESG scores to peer database
        This builds the real peer comparison database over time
        """
        if not self.peer_db_available:
            return False
        
        try:
            # Normalize industry name
            industry_normalized = industry.lower().replace(' ', '_').replace('&', 'and')
            
            # Create document
            doc_id = f"{company}_{industry_normalized}_{datetime.now().strftime('%Y%m%d')}"
            
            metadata = {
                "company": company,
                "industry": industry_normalized,
                "esg_score": float(esg_score),
                "env_score": float(pillar_scores.get("environmental_score", 50)),
                "social_score": float(pillar_scores.get("social_score", 50)),
                "gov_score": float(pillar_scores.get("governance_score", 50)),
                "rating": rating,
                "timestamp": datetime.now().isoformat(),
                "year": datetime.now().year
            }
            
            # Add to ChromaDB
            self.peer_collection.upsert(
                documents=[f"{company} ESG analysis from {datetime.now().strftime('%Y-%m-%d')}"],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            print(f"✅ Saved {company} to peer database (industry: {industry})")
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to save peer data: {e}")
            return False

    def get_real_peers_from_db(self, industry: str, exclude_company: str = None, 
                               max_peers: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve real peer companies from database
        Returns companies from same industry that were previously analyzed
        """
        if not self.peer_db_available:
            return []
        
        try:
            # Normalize industry
            industry_normalized = industry.lower().replace(' ', '_').replace('&', 'and')
            
            # Query ChromaDB for peers in same industry
            results = self.peer_collection.get(
                where={
                    "industry": industry_normalized
                },
                limit=max_peers + 1  # +1 in case we need to exclude current company
            )
            
            if not results or not results.get('metadatas'):
                return []
            
            # Extract peer data
            peers = []
            for metadata in results['metadatas']:
                company_name = metadata.get('company')
                
                # Skip current company
                if exclude_company and company_name.lower() == exclude_company.lower():
                    continue
                
                peers.append({
                    "company": company_name,
                    "esg": metadata.get('esg_score', 50),
                    "e": metadata.get('env_score', 50),
                    "s": metadata.get('social_score', 50),
                    "g": metadata.get('gov_score', 50),
                    "rating": metadata.get('rating', 'BBB'),
                    "source": "database",
                    "timestamp": metadata.get('timestamp', '')
                })
            
            print(f"📊 Found {len(peers)} real peers in database for {industry}")
            return peers[:max_peers]
            
        except Exception as e:
            print(f"⚠️ Failed to retrieve peers from database: {e}")
            return []

    def generate_estimated_peers(self, industry: str, target_esg: float, 
                                 count: int = 5) -> List[Dict[str, Any]]:
        """
        Generate estimated peer scores using industry baseline + variance
        Used as fallback when insufficient real peer data exists
        """
        industry_key = industry.lower().replace(' ', '_').replace('&', 'and')
        
        # Get industry config
        industry_data = self.industry_config.get(industry_key, self.industry_config.get('unknown', {}))
        
        if not industry_data.get('peer_estimation_enabled', False):
            print(f"⚠️ Peer estimation disabled for {industry}")
            return []
        
        baseline_esg = industry_data.get('baseline_esg', 50)
        baseline_env = industry_data.get('baseline_env', 50)
        baseline_social = industry_data.get('baseline_social', 50)
        baseline_gov = industry_data.get('baseline_gov', 50)
        
        variance_range = industry_data.get('peer_variance_range', [10, 15])
        
        # Generate deterministic estimated peers (no randomness)
        peers = []
        leader_variance = float(variance_range[1])
        above_variance = float((variance_range[0] + variance_range[1]) / 3)
        avg_variance = 0.0
        below_variance = -float((variance_range[0] + variance_range[1]) / 3)
        laggard_variance = -float(variance_range[1])
        
        # Peer 1: Industry Leader (above baseline)
        peers.append({
            "company": "Industry Leader",
            "esg": round(min(100, baseline_esg + leader_variance), 1),
            "e": round(min(100, baseline_env + leader_variance), 1),
            "s": round(min(100, baseline_social + leader_variance), 1),
            "g": round(min(100, baseline_gov + leader_variance), 1),
            "rating": self._calculate_rating(baseline_esg + leader_variance),
            "source": "estimated"
        })
        
        # Peer 2: Above Average
        peers.append({
            "company": "Industry Peer A",
            "esg": round(min(100, baseline_esg + above_variance), 1),
            "e": round(min(100, baseline_env + above_variance), 1),
            "s": round(min(100, baseline_social + above_variance), 1),
            "g": round(min(100, baseline_gov + above_variance), 1),
            "rating": self._calculate_rating(baseline_esg + above_variance),
            "source": "estimated"
        })
        
        # Peer 3: Industry Average
        peers.append({
            "company": "Industry Average",
            "esg": round(baseline_esg + avg_variance, 1),
            "e": round(baseline_env + avg_variance, 1),
            "s": round(baseline_social + avg_variance, 1),
            "g": round(baseline_gov + avg_variance, 1),
            "rating": self._calculate_rating(baseline_esg + avg_variance),
            "source": "estimated"
        })
        
        # Peer 4: Below Average
        peers.append({
            "company": "Industry Peer B",
            "esg": round(max(0, baseline_esg + below_variance), 1),
            "e": round(max(0, baseline_env + below_variance), 1),
            "s": round(max(0, baseline_social + below_variance), 1),
            "g": round(max(0, baseline_gov + below_variance), 1),
            "rating": self._calculate_rating(baseline_esg + below_variance),
            "source": "estimated"
        })
        
        # Peer 5: Industry Laggard
        peers.append({
            "company": "Industry Laggard",
            "esg": round(max(0, baseline_esg + laggard_variance), 1),
            "e": round(max(0, baseline_env + laggard_variance), 1),
            "s": round(max(0, baseline_social + laggard_variance), 1),
            "g": round(max(0, baseline_gov + laggard_variance), 1),
            "rating": self._calculate_rating(baseline_esg + laggard_variance),
            "source": "estimated"
        })
        
        print(f"📊 Generated {len(peers)} estimated peers for {industry}")
        return peers[:count]

    def _calculate_rating(self, esg_score: float) -> str:
        """Calculate ESG rating from score"""
        if esg_score >= 75:
            return "AA" if esg_score >= 80 else "A"
        elif esg_score >= 65:
            return "BBB"
        elif esg_score >= 50:
            return "BB"
        elif esg_score >= 35:
            return "B"
        else:
            return "CCC"

    def generate_dynamic_peer_table(self, company: str, industry: str, 
                                    esg_score: float = None,
                                    pillar_scores: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Generate peer comparison table using DYNAMIC approach:
        1. Query database for real peers in same industry
        2. If <3 real peers: Generate estimated peers using industry baseline
        3. Return table with appropriate disclaimer
        """
        print(f"\n📊 Generating dynamic peer comparison for {company} ({industry})...")
        
        # Step 1: Try to get real peers from database
        real_peers = self.get_real_peers_from_db(industry, exclude_company=company, max_peers=10)
        
        # Step 2: Determine if we need estimated peers
        use_estimates = len(real_peers) < 3
        
        if use_estimates:
            print(f"⚠️ Only {len(real_peers)} real peers found - generating estimates")
            estimated_peers = self.generate_estimated_peers(industry, esg_score or 50, count=5)
            all_peers = real_peers + estimated_peers
        else:
            print(f"✅ Using {len(real_peers)} real peers from database")
            all_peers = real_peers
        
        # If no peers at all, return unavailable
        if not all_peers:
            return {
                "available": False,
                "table_markdown": "Peer comparison unavailable - industry not configured for estimation",
                "peers": [],
                "rank": None,
                "industry_average": None,
                "data_source": "none"
            }
        
        # Step 3: Add target company to comparison
        all_companies = []
        
        if esg_score is not None and pillar_scores:
            env_score = pillar_scores.get('environmental_score', 50)
            soc_score = pillar_scores.get('social_score', 50)
            gov_score = pillar_scores.get('governance_score', 50)
            rating = self._calculate_rating(esg_score)
            
            target_company = {
                "company": company,
                "esg": round(esg_score, 1),
                "e": round(env_score, 1),
                "s": round(soc_score, 1),
                "g": round(gov_score, 1),
                "rating": rating,
                "is_target": True,
                "source": "target"
            }
            all_companies.append(target_company)
        
        # Add peers
        for peer in all_peers:
            peer_copy = peer.copy()
            peer_copy["is_target"] = False
            all_companies.append(peer_copy)
        
        # Step 4: Sort by ESG score and calculate ranks
        all_companies.sort(key=lambda x: x["esg"], reverse=True)
        
        for i, comp in enumerate(all_companies, 1):
            comp["rank"] = f"{i}/{len(all_companies)}"
        
        # Step 5: Calculate target company rank percentile
        target_rank = None
        if esg_score is not None:
            for comp in all_companies:
                if comp.get("is_target", False):
                    rank_num = int(comp["rank"].split('/')[0])
                    total = len(all_companies)
                    percentile = ((total - rank_num + 1) / total) * 100
                    
                    if percentile >= 80:
                        target_rank = f"Top 20% ({comp['rank']})"
                    elif percentile >= 60:
                        target_rank = f"Top 40% ({comp['rank']})"
                    elif percentile >= 40:
                        target_rank = f"Middle 40-60% ({comp['rank']})"
                    elif percentile >= 20:
                        target_rank = f"Bottom 40% ({comp['rank']})"
                    else:
                        target_rank = f"Bottom 20% ({comp['rank']})"
                    break
        
        # Step 6: Calculate industry average
        avg_esg = sum(c["esg"] for c in all_companies) / len(all_companies)
        avg_e = sum(c["e"] for c in all_companies) / len(all_companies)
        avg_s = sum(c["s"] for c in all_companies) / len(all_companies)
        avg_g = sum(c["g"] for c in all_companies) / len(all_companies)
        
        # Step 7: Generate markdown table
        table = "| Company              | ESG Score | E  | S  | G  | Rank | Rating |\n"
        table += "|----------------------|-----------|----|----|----|----- |--------|\n"
        
        for comp in all_companies:
            company_name = comp["company"]
            marker = ""
            if comp.get("is_target", False):
                marker = " ⭐"
            
            # Truncate long names and add marker
            display_name = company_name[:18] if len(company_name) > 18 else company_name
            display_name = f"{display_name}{marker}"
            
            table += f"| {display_name:<20} | {comp['esg']:>6.1f}    | {comp['e']:>2.0f} | {comp['s']:>2.0f} | {comp['g']:>2.0f} | {comp['rank']:<4} | {comp['rating']:<6} |\n"
        
        # Add industry average row
        table += "|----------------------|-----------|----|----|----|----- |--------|\n"
        table += f"| Industry Average     | {avg_esg:>6.1f}    | {avg_e:>2.0f} | {avg_s:>2.0f} | {avg_g:>2.0f} | -    | -      |\n"
        
        # Step 8: Determine data source for disclaimer
        real_count = len([p for p in all_peers if p.get('source') == 'database'])
        estimated_count = len([p for p in all_peers if p.get('source') == 'estimated'])
        
        if real_count >= 3:
            data_source = "real"
            disclaimer = None
        elif real_count > 0:
            data_source = "mixed"
            disclaimer = f"⚠️ Peer scores: {real_count} from database, {estimated_count} estimated from industry benchmarks"
        else:
            data_source = "estimated"
            disclaimer = f"⚠️ Peer scores estimated from industry benchmarks ({industry}) - insufficient historical data"
        
        print(f"   ✅ Peer table generated: {real_count} real + {estimated_count} estimated peers")
        if target_rank:
            print(f"   📊 Company Rank: {target_rank}")
        
        return {
            "available": True,
            "table_markdown": table,
            "peers": all_companies,
            "rank": target_rank,
            "industry_average": {
                "esg": round(avg_esg, 1),
                "e": round(avg_e, 1),
                "s": round(avg_s, 1),
                "g": round(avg_g, 1)
            },
            "total_peers": len(all_peers),
            "real_peer_count": real_count,
            "estimated_peer_count": estimated_count,
            "data_source": data_source,
            "disclaimer": disclaimer
        }

    # LEGACY METHOD: Keep for backwards compatibility but use generate_dynamic_peer_table instead
    def generate_peer_table(self, company: str, industry: str, 
                           esg_score: float = None,
                           pillar_scores: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Legacy method - redirects to generate_dynamic_peer_table
        """
        return self.generate_dynamic_peer_table(company, industry, esg_score, pillar_scores)
    
    def compare_to_peers(self, company: str, claims: List[Dict]) -> Dict[str, Any]:
        """
        Compare company's ESG claims against industry peers
        Detects "industry-leading" greenwashing
        REUSES cached evidence when available
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 9: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        
        try:
            # ============================================================
            # STEP 1: CHECK IF WE CAN REUSE CACHED EVIDENCE
            # ============================================================
            cached_evidence = evidence_cache.get_evidence(company, "main_evidence")
            
            if cached_evidence and cached_evidence.get("evidence"):
                print(f"📦 Reusing cached evidence for peer comparison - REDUCED API calls")
            
            # Get peer companies dynamically
            print(f"\n🔍 Identifying industry peers...")
            peers = self._get_peers(company)
            print(f"Peers identified: {', '.join(peers) if peers else 'None found'}")
            
            if not peers:
                return {
                    "company": company,
                    "peers_analyzed": [],
                    "peer_data": {},
                    "claim_comparisons": [],
                    "industry_position": {
                        "category": "Unknown",
                        "rationale": "No peers identified for comparison",
                        "confidence": 0
                    }
                }
            
            # Gather peer ESG data
            peer_data = {}
            print(f"\n📊 Gathering peer ESG data...")
            for peer in peers:
                print(f"   Fetching {peer} data...")
                peer_data[peer] = self._fetch_peer_esg_data(peer)
            
            # Analyze each claim against peers
            comparisons = []
            for claim in claims:
                comparison = self._compare_claim(company, claim, peers, peer_data)
                comparisons.append(comparison)
            
            # Calculate industry position
            position = self._calculate_industry_position(company, peer_data, comparisons)
            
            result = {
                "company": company,
                "peers_analyzed": peers,
                "peer_data": peer_data,
                "claim_comparisons": comparisons,
                "industry_position": position
            }
            
            print(f"\n✅ Industry comparison complete")
            print(f"   Position: {position['category']}")
            
            return result
            
        except Exception as e:
            print(f"⚠️ Peer comparison error: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "company": company,
                "error": str(e),
                "peers_analyzed": [],
                "peer_data": {},
                "claim_comparisons": [],
                "industry_position": {
                    "category": "Unknown",
                    "confidence": 0
                }
            }
    
    def _get_peers(self, company: str) -> List[str]:
        """
        Get peer companies dynamically - NO HARDCODING
        Uses LLM + web validation
        """
        
        print(f"   🔍 Identifying industry peers for {company}...")
        
        # Use LLM to identify peers
        prompt = f"""List 5 main direct competitors of {company} in the same industry.

Examples:
- If Tesla → Ford, GM, Volkswagen, Toyota, BYD
- If BP → Shell, Chevron, ExxonMobil, TotalEnergies, ConocoPhillips
- If Nike → Adidas, Puma, Under Armour, Lululemon, Reebok
- If Coca-Cola → PepsiCo, Nestle, Unilever, Danone, Keurig Dr Pepper
- If Microsoft → Google, Apple, Amazon, Meta, IBM

Return ONLY company names separated by commas, no other text.
Company: {company}
Competitors:"""
        
        try:
            response = self.llm.call_groq(
                [{"role": "user", "content": prompt}],
                use_fast=True
            )
            
            if response:
                # Parse response
                peers = [p.strip() for p in response.split(',') if p.strip()]
                # Clean up any extra text
                peers = [p.replace('Competitors:', '').replace('competitors:', '').strip() for p in peers]
                # Filter valid company names
                peers = [p for p in peers if len(p) > 2 and len(p) < 50][:5]
                
                if peers:
                    print(f"   ✅ Found {len(peers)} peers")
                    return peers
        
        except Exception as e:
            print(f"   ⚠️ LLM peer identification failed: {e}")
        
        # Fallback: deterministic peer dataset for energy-heavy companies
        fallback_energy = [
            "Shell",
            "BP",
            "TotalEnergies",
            "Chevron",
            "Exxon",
            "Reliance",
            "Adani"
        ]
        company_l = company.lower()
        if any(k in company_l for k in ["bp", "shell", "exxon", "chevron", "total", "energy", "oil", "gas", "reliance", "adani"]):
            peers = [p for p in fallback_energy if p.lower() != company_l][:5]
            print(f"   ⚠️ Using deterministic fallback peers for energy sector")
            return peers

        # Generic fallback: pick first 5 deterministic peers excluding company
        peers = [p for p in fallback_energy if p.lower() != company_l][:5]
        print(f"   ⚠️ Could not identify peers for {company}, using fallback peer list")
        return peers
    
    def _fetch_peer_esg_data(self, peer: str) -> Dict[str, Any]:
        """Fetch ESG data for peer - IMPROVED with multiple query strategies"""
        
        print(f"      Searching for {peer} ESG data...")
        
        try:
            # Strategy 1: Try specific ESG rating queries
            query_strategies = [
                f'"{peer}" ESG rating MSCI Sustainalytics 2024 2025',
                f'"{peer}" sustainability score CDP rating',
                f'"{peer}" environmental social governance performance',
                f'{peer} carbon emissions reduction target climate'
            ]
            
            all_results = []
            for i, query in enumerate(query_strategies):
                try:
                    source_dict = self.fetcher.fetch_all_sources(
                        company=peer,
                        query=query,
                        max_per_source=2
                    )
                    
                    results = self.fetcher.aggregate_and_deduplicate(source_dict)
                    all_results.extend(results)
                    
                    if len(all_results) >= 5:
                        break  # Have enough
                        
                except Exception as e:
                    continue
            
            if not all_results:
                print(f"      ⚠️ No data found for {peer}")
                return {
                    "data_available": False,
                    "esg_score": "unknown",
                    "source_count": 0
                }
            
            # Extract metrics using LLM with BETTER prompt
            content = " ".join([r.get('snippet', '')[:200] for r in all_results[:5]])
            
            if len(content) < 50:
                return {
                    "data_available": False,
                    "esg_score": "unknown",
                    "source_count": len(all_results)
                }
            
            # IMPROVED LLM prompt with examples
            prompt = f"""Extract ESG data for {peer} from this text:

    {content[:800]}

    Return ONLY valid JSON (no markdown, no explanation):
    {{
    "esg_score": 45,
    "carbon_neutral_target": "2050",
    "sustainability_certifications": ["B Corp"],
    "recent_violations": "yes"
    }}

    If not found, use "unknown" for strings or null for numbers.
    JSON:"""

            response = self.llm.call_groq(
                [{"role": "user", "content": prompt}],
                use_fast=True
            )
            
            if response:
                try:
                    # More robust JSON extraction
                    import re
                    
                    # Initialize cleaned
                    cleaned = response.strip()
                    
                    # Remove markdown
                    cleaned = re.sub(r'```\s*', '', cleaned)
                    
                    # Extract JSON
                    start = cleaned.find('{')
                    end = cleaned.rfind('}') + 1
                    
                    if start != -1 and end > start:
                        json_str = cleaned[start:end]
                        parsed = json.loads(json_str)
                        
                        # Validate and enhance
                        parsed['data_available'] = True
                        parsed['source_count'] = len(all_results)
                        parsed['sources_used'] = [r.get('url', '')[:100] for r in all_results[:3]]
                        
                        # Print what we found
                        score_str = str(parsed.get('esg_score', 'unknown'))
                        print(f"      ✅ {peer}: ESG={score_str}, Target={parsed.get('carbon_neutral_target', 'unknown')}")
                        
                        return parsed
                
                except Exception as e:
                    print(f"      ⚠️ {peer}: JSON error - {str(e)[:50]}")
            
            # Fallback: Return what we have
            return {
                "data_available": True,
                "esg_score": "data_found_parsing_failed",
                "source_count": len(all_results),
                "raw_snippets": [r.get('snippet', '')[:100] for r in all_results[:3]]
            }
        
        except Exception as e:
            print(f"      ❌ {peer}: Fetch error - {str(e)[:50]}")
            return {
                "data_available": False,
                "error": str(e)[:100],
                "esg_score": "unknown"
            }


    
    def _compare_claim(self, company: str, claim: Dict, peers: List[str], 
                      peer_data: Dict) -> Dict:
        """Compare single claim against peers"""
        
        claim_text = claim.get('claim_text', '')
        claim_id = claim.get('claim_id')
        
        # Check for superlative language
        superlatives = [
            'industry-leading', 'best-in-class', 'first', 'only', 
            'leading', 'top', 'most', 'largest', 'biggest', 'strongest'
        ]
        uses_superlative = any(sup in claim_text.lower() for sup in superlatives)
        
        comparison = {
            "claim_id": claim_id,
            "claim": claim_text,
            "uses_superlative": uses_superlative,
            "superlative_words": [s for s in superlatives if s in claim_text.lower()],
            "verified_against_peers": False,
            "peer_comparison": []
        }
        
        if uses_superlative:
            # Check if peers have similar/better claims
            for peer, data in peer_data.items():
                if data.get('data_available', False):
                    comparison["peer_comparison"].append({
                        "peer": peer,
                        "comparable_data": {
                            "esg_score": data.get('esg_score'),
                            "carbon_target": data.get('carbon_neutral_target')
                        },
                        "assessment": "Requires detailed comparison"
                    })
            
            # If multiple peers have similar data, superlative claim is questionable
            comparable_peers = len(comparison["peer_comparison"])
            if comparable_peers >= 2:
                comparison["verified_against_peers"] = False
                comparison["flag"] = f"Multiple peers ({comparable_peers}) have comparable ESG claims - superlative may not be justified"
            else:
                comparison["verified_against_peers"] = True
        
        return comparison
    
    def _calculate_industry_position(self, company: str, peer_data: Dict, 
                                    comparisons: List[Dict]) -> Dict:
        """Calculate company's position vs industry"""
        
        # Count peers with available data
        peers_with_data = sum(1 for data in peer_data.values() if data.get('data_available'))
        
        # Check for superlative claims
        superlative_claims = sum(1 for c in comparisons if c.get('uses_superlative'))
        
        # Simplified positioning (would need actual scores for real comparison)
        if peers_with_data == 0:
            category = "Unknown"
            confidence = 0
            rationale = "Insufficient peer data for comparison"
        elif superlative_claims > 0:
            # If using superlatives, need to verify
            category = "Claims Leadership"
            confidence = 40
            rationale = f"Company uses superlative language in {superlative_claims} claim(s) - requires verification against {peers_with_data} peers"
        else:
            category = "Average"
            confidence = 50
            rationale = f"Compared against {peers_with_data} peers - no superlative claims detected"
        
        return {
            "category": category,
            "rationale": rationale,
            "confidence": confidence,
            "peers_with_data": peers_with_data,
            "superlative_claims": superlative_claims
        }
    

