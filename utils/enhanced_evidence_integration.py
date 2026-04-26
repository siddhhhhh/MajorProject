"""
Integration wrapper to inject enhanced government/international ESG data into evidence pipeline
This module ensures enhanced data sources are called alongside traditional evidence retrieval
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from utils.enhanced_data_sources import fetch_enhanced_esg_data
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedEvidenceIntegration:
    """Wraps enhanced data sources into the standard evidence retrieval flow"""

    @staticmethod
    def _convert_enhanced_to_evidence_format(enhanced_data: Dict[str, Any], company: str) -> List[Dict[str, Any]]:
        """
        Convert enhanced source data into standard evidence item format
        for seamless integration with existing evidence pipeline
        """
        evidence_items = []

        # Map enhanced sources to evidence format
        if "enhanced_sources" in enhanced_data:
            for source_result in enhanced_data["enhanced_sources"]:
                if isinstance(source_result, dict):
                    # ILO Violations
                    if "violations" in source_result:
                        for violation in source_result.get("violations", []):
                            evidence_items.append({
                                "source_name": "ILO (International Labour Organization)",
                                "source_type": "Government/Regulatory",
                                "source": "ILO_NORMLEX",
                                "title": f"ILO Labor Standards - {violation.get('type', 'Violation')}",
                                "snippet": violation.get("severity", "MEDIUM") + " severity: " + str(violation),
                                "relevant_text": str(violation),
                                "url": "https://www.ilo.org/dyn/normlex",
                                "data_type": violation.get("data_type", "labor"),
                                "pillar": "social",
                                "stance": "contradicts" if violation.get("severity") == "HIGH" else "neutral",
                                "credibility_score": 0.95,  # Government source
                                "date": datetime.now().isoformat(),
                                "origin": "government_source"
                            })

                    # UN Global Compact Status
                    if "un_compact_status" in source_result:
                        status = source_result["un_compact_status"]
                        if status.get("is_signatory"):
                            evidence_items.append({
                                "source_name": "UN Global Compact (UNGC)",
                                "source_type": "NGO",
                                "source": "UN_GC",
                                "title": "UN Global Compact Signatory Status",
                                "snippet": f"Company is a UN Global Compact signatory endorsing: {', '.join(status.get('principles_endorsed', []))}",
                                "relevant_text": f"Endorsed principles: {status.get('principles_endorsed', [])}",
                                "url": "https://www.globalcompact.org",
                                "data_type": "governance_commitment",
                                "pillar": "governance",
                                "stance": "supports",
                                "credibility_score": 0.90,
                                "date": datetime.now().isoformat(),
                                "origin": "government_source"
                            })

                    # OECD Guidelines Cases
                    if "oecd_cases" in source_result:
                        for case in source_result.get("oecd_cases", []):
                            evidence_items.append({
                                "source_name": "OECD Guidelines / National Contact Points",
                                "source_type": "Regulatory Filing",
                                "source": "OECD_NCP",
                                "title": f"OECD Guidelines Complaint - {case.get('status', 'Active')}",
                                "snippet": case.get("case_type", "Complaint") + ": " + str(case),
                                "relevant_text": str(case),
                                "url": "https://www.oecdwatch.org",
                                "data_type": case.get("data_type", "regulatory"),
                                "pillar": "governance",
                                "stance": "contradicts" if case.get("status") == "Active" else "neutral",
                                "credibility_score": 0.95,  # Regulatory
                                "date": datetime.now().isoformat(),
                                "origin": "government_source"
                            })

                    # EU Taxonomy Alignment
                    if "eu_taxonomy" in source_result:
                        taxonomy = source_result["eu_taxonomy"]
                        if taxonomy.get("disclosure_status") != "NOT_FOUND":
                            evidence_items.append({
                                "source_name": "EU Taxonomy Regulation",
                                "source_type": "Government/Regulatory",
                                "source": "EU_TAXONOMY",
                                "title": "EU Taxonomy ESG Alignment",
                                "snippet": f"Taxonomy compliance score: {taxonomy.get('taxonomy_compliance_score', 'N/A')}",
                                "relevant_text": f"Aligned activities: {taxonomy.get('aligned_activities', [])}",
                                "url": "https://ec.europa.eu/sustainable-finance",
                                "data_type": "regulatory_compliance",
                                "pillar": "environmental",
                                "stance": "supports",
                                "credibility_score": 0.95,
                                "date": datetime.now().isoformat(),
                                "origin": "government_source"
                            })

                    # UNFCCC Net-Zero Pledges
                    if "net_zero_pledge" in source_result:
                        pledge = source_result["net_zero_pledge"]
                        if pledge.get("in_race_to_zero"):
                            evidence_items.append({
                                "source_name": "UNFCCC Race to Zero Campaign",
                                "source_type": "Government/Regulatory",
                                "source": "UNFCCC",
                                "title": f"UNFCCC Net-Zero Pledge ({pledge.get('target_year', 'TBD')})",
                                "snippet": f"Company pledged net-zero by {pledge.get('target_year')}, verified: {pledge.get('verified')}",
                                "relevant_text": f"Target year: {pledge.get('target_year')}, Pledge year: {pledge.get('pledge_year')}",
                                "url": "https://www.unfccc.int/climate-action/race-to-zero-campaign",
                                "data_type": "climate_commitment",
                                "pillar": "environmental",
                                "stance": "supports",
                                "credibility_score": 0.95,
                                "date": datetime.now().isoformat(),
                                "origin": "government_source"
                            })

                    # Supply Chain Transparency
                    if "supply_chain_data" in source_result:
                        supply_data = source_result["supply_chain_data"]
                        # Add for apparel/fashion companies
                        if supply_data.get("apparel_registry", {}).get("status") == "FOUND":
                            evidence_items.append({
                                "source_name": "Open Apparel Registry",
                                "source_type": "NGO",
                                "source": "OAR",
                                "title": "Supply Chain Transparency - Apparel",
                                "snippet": f"Registered facilities: {supply_data.get('apparel_registry', {}).get('facilities_count', 0)}",
                                "relevant_text": "Company facilities registered in Open Apparel Registry for supply chain transparency",
                                "url": "https://openapparelregistry.org",
                                "data_type": "supply_chain_labor",
                                "pillar": "social",
                                "stance": "supports",
                                "credibility_score": 0.85,
                                "date": datetime.now().isoformat(),
                                "origin": "government_source"
                            })

                    # Anti-Corruption Status
                    if "anti_corruption_status" in source_result:
                        corruption_status = source_result["anti_corruption_status"]
                        if corruption_status.get("ofac_sanctioned") or corruption_status.get("un_sanctioned"):
                            evidence_items.append({
                                "source_name": "OFAC / UN Sanctions Database",
                                "source_type": "Government/Regulatory",
                                "source": "OFAC",
                                "title": "Sanctions Designation",
                                "snippet": "Company or related entities found in international sanctions databases",
                                "relevant_text": str(corruption_status),
                                "url": "https://www.opensanctions.org",
                                "data_type": "governance_compliance",
                                "pillar": "governance",
                                "stance": "contradicts",
                                "credibility_score": 0.95,
                                "date": datetime.now().isoformat(),
                                "origin": "government_source"
                            })

        return evidence_items

    @staticmethod
    async def fetch_enhanced_evidence(company: str, industry: str = "", country: str = "") -> List[Dict[str, Any]]:
        """
        Fetch enhanced evidence from government/international sources
        (Async wrapper for integration into async evidence pipeline)
        """
        try:
            # Fetch enhanced data
            enhanced_data = fetch_enhanced_esg_data(
                company_name=company,
                industry=industry,
                country=country
            )

            # Convert to standard evidence format
            evidence_items = EnhancedEvidenceIntegration._convert_enhanced_to_evidence_format(
                enhanced_data,
                company
            )

            logger.info(f"✅ Fetched {len(evidence_items)} enhanced government evidence items for {company}")
            return evidence_items

        except Exception as e:
            logger.warning(f"Enhanced evidence fetch failed: {e}")
            return []


async def integrate_enhanced_sources_into_evidence(
    existing_evidence: List[Dict[str, Any]],
    company: str,
    industry: str = "",
    country: str = ""
) -> List[Dict[str, Any]]:
    """
    Wrapper function to be called by EvidenceRetriever.retrieve_evidence()
    Appends enhanced government/international sources to existing evidence
    """
    try:
        # Fetch enhanced evidence
        enhanced_evidence = await EnhancedEvidenceIntegration.fetch_enhanced_evidence(
            company=company,
            industry=industry,
            country=country
        )

        # Merge with existing evidence (enhanced sources are lower priority but add coverage)
        combined = list(existing_evidence) + enhanced_evidence

        # Deduplicate by source name + snippet
        seen = set()
        deduped = []
        for item in combined:
            key = (
                item.get("source_name", ""),
                item.get("snippet", "")[:100]
            )
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        logger.info(f"Combined evidence: {len(existing_evidence)} base + {len(enhanced_evidence)} enhanced = {len(deduped)} after dedup")
        return deduped

    except Exception as e:
        logger.warning(f"Enhanced evidence integration failed: {e} - returning base evidence")
        return existing_evidence
