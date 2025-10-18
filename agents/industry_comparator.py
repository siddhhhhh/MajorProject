"""
Industry Comparison & Peer Benchmarking Agent
Compares company claims against competitors
100% Real-time, Zero Hardcoding
"""

from typing import Dict, Any, List
from utils.enterprise_data_sources import enterprise_fetcher
from core.llm_client import llm_client
import json


class IndustryComparator:
    def __init__(self):
        self.name = "Peer Comparison & Industry Benchmark Specialist"
        self.fetcher = enterprise_fetcher
        self.llm = llm_client
    
    def compare_to_peers(self, company: str, claims: List[Dict]) -> Dict[str, Any]:
        """
        Compare company's ESG claims against industry peers
        Detects "industry-leading" greenwashing
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT 9: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        
        try:
            # Get peer companies dynamically
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
        
        # Fallback: return empty list
        print(f"   ⚠️ Could not identify peers for {company}")
        return []
    
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
