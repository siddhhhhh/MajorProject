"""
Regulatory Horizon Scanner Agent
Maps ESG claims against global and Indian regulations

Supported Regulations:
- INDIA: SEBI BRSR, MCA Companies Act, CPCB Environmental Compliance, RBI Green Finance
- EU: CSRD, EU Taxonomy, SFDR
- US: SEC Climate Rules, FTC Green Guides
- UK: FCA Anti-Greenwashing Rules, TCFD
- GLOBAL: GRI, SASB, ISSB, CDP, SBTi

Uses ChromaDB for regulation text storage and semantic search
"""

import json
import os
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from core.llm_call import call_llm
import asyncio
from core.vector_store import vector_store
from config.agent_prompts import REGULATORY_COMPLIANCE_PROMPT
import requests

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional runtime dependency
    pd = None


EU_COUNTRIES = {"DE", "FR", "NL", "DK", "SE", "IT", "ES", "PL", "BE", "AT", "CH"}
UK_COUNTRIES = {"GB", "UK"}
US_COUNTRIES = {"US", "USA"}
# Public SBTi target dashboard Excel — Google Sheets backed, served via the
# canonical /download/excel redirect. Replaces the older /resources/files/
# URL which now returns 404. Contains 14k+ rows (company_name column).
SBTI_PROGRESS_REPORT_URL = "https://sciencebasedtargets.org/download/excel"
SBTI_CACHE_FILE = os.path.join("data", "sbti_company_cache.json")
SBTI_CACHE_DAYS = 7


def get_applicable_frameworks(company: str, industry: str, country: str) -> list[str]:
    """Return framework display names based on company, industry, and country."""
    company_upper = (company or "").upper()
    country_code = (country or "").upper()

    frameworks = []

    is_indian = country_code in ("IN", "INDIA") or any(ex in company_upper for ex in ("NSE", "BSE"))
    if is_indian:
        frameworks.extend(
            [
                "SEBI BRSR (Business Responsibility and Sustainability Report)",
                "MCA Companies Act (CSR Rules)",
                "CPCB Environmental Compliance",
                "RBI Green Finance Framework",
                "India PAT Scheme (Perform, Achieve and Trade)",
            ]
        )

    if country_code in EU_COUNTRIES:
        frameworks.extend(
            [
                "EU Corporate Sustainability Reporting Directive",
                "EU Taxonomy Regulation",
                "EU Sustainable Finance Disclosure Regulation",
            ]
        )

    if country_code in UK_COUNTRIES or "LONDON" in company_upper:
        frameworks.extend(
            [
                "FCA Anti-Greenwashing Rule",
                "UK TCFD-Aligned Disclosure Requirements",
            ]
        )

    if country_code in US_COUNTRIES:
        frameworks.extend(
            [
                "SEC Climate Disclosure Rule",
                "FTC Green Guides",
            ]
        )

    frameworks.extend(
        [
            "GHG Protocol Corporate Standard",
            "GRI Sustainability Reporting Standards",
            "CDP (Carbon Disclosure Project)",
            "Science Based Targets initiative",
        ]
    )

    return list(dict.fromkeys(frameworks))


FRAMEWORK_NAME_ALIASES = {
    "MCA Companies Act (CSR Rules)": "MCA_COMPANIES_ACT",
    "SEC Climate Disclosure Rule": "SEC_CLIMATE",
    "UK TCFD-Aligned Disclosure Requirements": "UK_TCFD",
}


def calculate_compliance_score(compliance_results: list[dict]) -> dict:
    """
    Backward-compatible compliance score with per-regulation status details.

    Accepts both legacy detector rows (gap_count/gaps_found) and scanner rows
    (status/gap_details/requirements_unverified). The legacy score is:
    compliant-framework percentage minus 8 points per concrete gap.
    """
    if not compliance_results:
        return {
            "score": 0,
            "risk_level": "High",
            "per_regulation_status": [],
            "gaps": 0,
            "compliant_count": 0,
            "gap_count": 0,
            "total_count": 0,
            "total_regulations": 0,
            "compliant_regulations": 0,
            "score_breakdown": "No frameworks checked",
        }

    total = len(compliance_results)
    per_regulation_status = []
    compliant = 0
    concrete_gap_count = 0
    regulations_with_gaps = 0

    for idx, row in enumerate(compliance_results):
        if not isinstance(row, dict):
            row = {}

        gap_details = row.get("gap_details")
        if gap_details is None:
            gap_details = row.get("gaps_found")
        if gap_details is None and row.get("requirements_unverified"):
            gap_details = [
                req.get("requirement", str(req)) if isinstance(req, dict) else str(req)
                for req in row.get("requirements_unverified", [])
            ]
        if gap_details is None:
            gap_details = []
        if not isinstance(gap_details, list):
            gap_details = [str(gap_details)] if gap_details else []

        explicit_gap_count = row.get("gap_count")
        if isinstance(explicit_gap_count, int) and explicit_gap_count > len(gap_details):
            gap_details.extend(["Unspecified compliance gap"] * (explicit_gap_count - len(gap_details)))

        status_raw = str(row.get("status") or row.get("compliance_status") or "").upper()
        has_gap = bool(gap_details) or status_raw in {"GAP", "GAP FOUND", "NON-COMPLIANT", "PARTIALLY COMPLIANT"}
        # NOT_EVALUATED frameworks were never tested against the claim — they
        # must not be counted as compliant. Empty status with no gaps is also
        # treated as not-evaluated rather than auto-compliant.
        is_not_evaluated = status_raw in {"NOT_EVALUATED", "NOT EVALUATED"} or (
            not has_gap and status_raw in {"", "NOT APPLICABLE"}
        )
        is_compliant = not has_gap and not is_not_evaluated and status_raw == "COMPLIANT"

        if is_compliant:
            compliant += 1
        if has_gap and status_raw != "UNCERTAIN":
            regulations_with_gaps += 1
            concrete_gap_count += max(1, len(gap_details))

        if has_gap:
            display_status = "GAP FOUND"
        elif is_not_evaluated:
            display_status = "NOT EVALUATED"
        else:
            display_status = "COMPLIANT"
        per_regulation_status.append({
            "regulation": row.get("regulation_name") or row.get("regulation") or f"Regulation {idx + 1}",
            "status": display_status,
            "gap_count": len(gap_details),
            "gap_details": gap_details,
            "gaps": gap_details,
        })

    # Compute the base score against the number of frameworks the scanner
    # actually evaluated, not the full applicable list. Otherwise frameworks
    # that the claim never triggered (NOT_EVALUATED) drag the score down as
    # if they were gaps.
    evaluated_count = sum(
        1
        for row in per_regulation_status
        if row["status"] not in {"NOT EVALUATED", "NOT_EVALUATED"}
    )
    if evaluated_count == 0:
        base_score = 0
    else:
        base_score = (compliant / evaluated_count) * 100
    penalty = concrete_gap_count * 8
    final_score = max(0, round(base_score - penalty))

    if final_score >= 75:
        risk_level = "Low"
    elif final_score >= 45:
        risk_level = "Medium"
    else:
        risk_level = "High"

    breakdown = (
        f"{compliant}/{total} frameworks compliant "
        f"(+{round(base_score)}pts base) "
        f"minus {concrete_gap_count} gap penalties (-{penalty}pts) "
        f"= {final_score}/100"
    )

    return {
        "score": final_score,
        "risk_level": risk_level,
        "per_regulation_status": per_regulation_status,
        "gaps": concrete_gap_count,
        "compliant_count": compliant,
        "gap_count": concrete_gap_count,
        "total_count": total,
        "total_regulations": total,
        "compliant_regulations": compliant,
        "regulations_with_gaps": regulations_with_gaps,
        "score_breakdown": breakdown,
    }


class RegulatoryHorizonScanner:
    """
    ESG Regulatory Compliance Scanner
    Verifies claims against global and Indian regulations
    """
    
    def __init__(self):
        self.name = "Regulatory Horizon & Policy Disclosure Scanner"
        self.vector_store = vector_store
        
        # Initialize regulation database
        self.regulations = self._initialize_regulations()
        
        print(f"✅ {self.name} initialized")
        print(f"   Loaded {len(self.regulations)} regulatory frameworks")
    
    def _initialize_regulations(self) -> Dict[str, Dict[str, Any]]:
        """Initialize comprehensive regulation database"""
        
        return {
            # =============================================
            # INDIAN REGULATIONS
            # =============================================
            "SEBI_BRSR": {
                "name": "SEBI BRSR (Business Responsibility and Sustainability Report)",
                "jurisdiction": "India",
                "authority": "Securities and Exchange Board of India",
                "effective_date": "2023-04-01",
                "applicability": "Top 1000 listed companies by market cap",
                "key_requirements": [
                    "Mandatory disclosure of Scope 1 and Scope 2 GHG emissions",
                    "Energy consumption from renewable and non-renewable sources",
                    "Water withdrawal, consumption, and discharge",
                    "Waste generated by type and disposal method",
                    "Employee well-being metrics and safety data",
                    "Value chain ESG assessment",
                    "BRSR Core assurance requirement from FY 2023-24"
                ],
                "penalties": {
                    "non_disclosure": "SEBI enforcement action, trading restrictions",
                    "false_disclosure": "Fraud investigation under SEBI Act"
                },
                "claim_validation_rules": [
                    {"pattern": "net zero|carbon neutral", "requirement": "Must disclose Scope 1, 2, 3 emissions with baseline"},
                    {"pattern": "renewable energy|clean energy", "requirement": "Must disclose % from renewable sources"},
                    {"pattern": "water positive|water neutral", "requirement": "Must disclose water withdrawal and recycling data"},
                    {"pattern": "zero waste|waste reduction", "requirement": "Must disclose waste by type and disposal method"}
                ]
            },
            
            "MCA_COMPANIES_ACT": {
                "name": "MCA Companies Act 2013 - ESG Provisions",
                "jurisdiction": "India",
                "authority": "Ministry of Corporate Affairs, India",
                "effective_date": "2013-08-29",
                "applicability": "All companies registered in India",
                "key_requirements": [
                    "Board Report must include CSR activities (Section 134)",
                    "CSR spending mandate - 2% of average net profits (Section 135)",
                    "Director responsibility for ESG oversight",
                    "Annual Return disclosure of energy conservation (Rule 8)",
                    "Secretarial Audit for listed companies"
                ],
                "penalties": {
                    "csr_non_compliance": "Transfer unspent amount to ESG fund, penalty up to ₹1 crore",
                    "false_disclosure": "Imprisonment up to 3 years, fine up to ₹25 lakh"
                },
                "claim_validation_rules": [
                    {"pattern": "csr|corporate social responsibility", "requirement": "Must have Board CSR committee, 2% spending mandate"},
                    {"pattern": "community investment|social impact", "requirement": "Must align with Schedule VII activities"}
                ]
            },
            
            "CPCB_EPA": {
                "name": "CPCB Environmental Compliance (EPA 1986)",
                "jurisdiction": "India",
                "authority": "Central Pollution Control Board / MoEFCC",
                "effective_date": "1986-11-19",
                "applicability": "All industrial units in India",
                "key_requirements": [
                    "Consent to Establish (CTE) and Consent to Operate (CTO)",
                    "Emission standards compliance for 17 categories",
                    "Effluent discharge standards",
                    "Hazardous waste management rules",
                    "Environmental audit and compliance reports",
                    "Real-time emission monitoring (OCEMS)"
                ],
                "penalties": {
                    "violation": "Imprisonment up to 5 years, fine up to ₹1 lakh per day",
                    "closure": "Production stoppage order"
                },
                "claim_validation_rules": [
                    {"pattern": "pollution free|zero discharge", "requirement": "Must have valid CTO and compliance certificates"},
                    {"pattern": "emission reduction|clean production", "requirement": "Must show CPCB compliance data"}
                ]
            },
            
            "RBI_GREEN_FINANCE": {
                "name": "RBI Green Finance Guidelines",
                "jurisdiction": "India",
                "authority": "Reserve Bank of India",
                "effective_date": "2023-01-01",
                "applicability": "All RBI regulated entities",
                "key_requirements": [
                    "Climate risk stress testing for banks",
                    "Green bond framework compliance",
                    "Disclosure of climate-related financial risks",
                    "Green taxonomy alignment for loans",
                    "Environmental and Social risk assessment in lending"
                ],
                "penalties": {
                    "non_compliance": "RBI regulatory action, restrictions on lending"
                },
                "claim_validation_rules": [
                    {"pattern": "green bond|sustainable finance", "requirement": "Must comply with RBI green bond framework"},
                    {"pattern": "climate risk|transition risk", "requirement": "Must disclose climate risk assessment"}
                ]
            },
            
            "INDIA_BEE_PAT": {
                "name": "BEE PAT Scheme (Perform, Achieve, Trade)",
                "jurisdiction": "India", 
                "authority": "Bureau of Energy Efficiency",
                "effective_date": "2012-04-01",
                "applicability": "Designated Consumers (high energy industries)",
                "key_requirements": [
                    "Specific Energy Consumption (SEC) targets",
                    "Energy audit by BEE accredited auditors",
                    "Energy Saving Certificates (ESCerts) trading",
                    "Mandatory reporting of energy consumption"
                ],
                "penalties": {
                    "non_achievement": "Purchase ESCerts from market, penalty"
                },
                "claim_validation_rules": [
                    {"pattern": "energy efficiency|energy saving", "requirement": "Must show PAT compliance if Designated Consumer"}
                ]
            },
            
            # =============================================
            # EU REGULATIONS
            # =============================================
            "EU_CSRD": {
                "name": "EU Corporate Sustainability Reporting Directive",
                "jurisdiction": "European Union",
                "authority": "European Commission",
                "effective_date": "2024-01-01",
                "applicability": "Large EU companies and listed SMEs, non-EU companies with EU revenue >€150M",
                "key_requirements": [
                    "Double materiality assessment (impact and financial)",
                    "ESRS (European Sustainability Reporting Standards) compliance",
                    "Scope 3 emissions disclosure",
                    "Biodiversity and ecosystem impact",
                    "Due diligence on value chain",
                    "Third-party limited assurance (moving to reasonable assurance)"
                ],
                "penalties": {
                    "non_compliance": "Member state penalties, market access restrictions",
                    "greenwashing": "Up to 4% of annual turnover"
                },
                "claim_validation_rules": [
                    {"pattern": "sustainable|sustainability", "requirement": "Must comply with ESRS double materiality"},
                    {"pattern": "value chain|supply chain esg", "requirement": "Must conduct value chain due diligence"},
                    {"pattern": "science based|sbti", "requirement": "Must show SBTi validation"}
                ]
            },
            
            "EU_TAXONOMY": {
                "name": "EU Taxonomy Regulation",
                "jurisdiction": "European Union",
                "authority": "European Commission",
                "effective_date": "2022-01-01",
                "applicability": "CSRD companies, financial market participants",
                "key_requirements": [
                    "Taxonomy alignment of economic activities",
                    "Substantial contribution to 1 of 6 environmental objectives",
                    "Do No Significant Harm (DNSH) criteria",
                    "Minimum social safeguards",
                    "Taxonomy-aligned revenue, CapEx, OpEx disclosure"
                ],
                "claim_validation_rules": [
                    {"pattern": "taxonomy aligned|eu taxonomy", "requirement": "Must meet substantial contribution and DNSH criteria"},
                    {"pattern": "green investment|sustainable investment", "requirement": "Must show taxonomy alignment percentage"}
                ]
            },
            
            "EU_SFDR": {
                "name": "EU Sustainable Finance Disclosure Regulation",
                "jurisdiction": "European Union",
                "authority": "European Commission",
                "effective_date": "2021-03-10",
                "applicability": "Financial market participants and advisers",
                "key_requirements": [
                    "ESG risk integration in investment process",
                    "Principal Adverse Impact (PAI) statements",
                    "Article 8 (promotes ESG) / Article 9 (sustainable objective) classification",
                    "Pre-contractual and periodic disclosures"
                ],
                "claim_validation_rules": [
                    {"pattern": "esg fund|sustainable fund", "requirement": "Must classify under SFDR Article 8 or 9"},
                    {"pattern": "impact investment", "requirement": "Must show Article 9 objective"}
                ]
            },
            
            # =============================================
            # US REGULATIONS  
            # =============================================
            "SEC_CLIMATE": {
                "name": "SEC Climate Disclosure Rules",
                "jurisdiction": "United States",
                "authority": "Securities and Exchange Commission",
                "effective_date": "2024-03-06",
                "applicability": "SEC registrants (public companies)",
                "key_requirements": [
                    "Material climate-related risks disclosure",
                    "GHG emissions (Scope 1, 2, material Scope 3)",
                    "Climate risk governance and management",
                    "Financial statement impact of climate risks",
                    "Climate targets and transition plans"
                ],
                "penalties": {
                    "non_disclosure": "SEC enforcement action",
                    "false_disclosure": "Securities fraud prosecution"
                },
                "claim_validation_rules": [
                    {"pattern": "climate risk|transition plan", "requirement": "Must file with SEC Form 10-K"},
                    {"pattern": "net zero|emission reduction", "requirement": "Must disclose in SEC filings with material assumptions"}
                ]
            },
            
            "FTC_GREEN_GUIDES": {
                "name": "FTC Green Guides",
                "jurisdiction": "United States",
                "authority": "Federal Trade Commission",
                "effective_date": "2012-10-01",
                "applicability": "All US businesses marketing green products",
                "key_requirements": [
                    "Environmental marketing claims must be truthful",
                    "Claims must be substantiated",
                    "Qualifications must be clear and prominent",
                    "Specific guidance on recyclable, biodegradable, carbon neutral claims"
                ],
                "penalties": {
                    "violation": "FTC enforcement action, consent orders, civil penalties"
                },
                "claim_validation_rules": [
                    {"pattern": "biodegradable|compostable", "requirement": "Must degrade within 1 year in customary disposal"},
                    {"pattern": "recyclable", "requirement": "Must be recyclable in substantial majority of communities"},
                    {"pattern": "carbon neutral|carbon offset", "requirement": "Must substantiate with reliable offsets"}
                ]
            },
            
            # =============================================
            # UK REGULATIONS
            # =============================================
            "UK_FCA_ANTIGREENWASHING": {
                "name": "FCA Anti-Greenwashing Rule",
                "jurisdiction": "United Kingdom",
                "authority": "Financial Conduct Authority",
                "effective_date": "2024-05-31",
                "applicability": "All FCA-authorised firms",
                "key_requirements": [
                    "Sustainability claims must be fair, clear, not misleading",
                    "Claims must be capable of substantiation",
                    "No cherry-picking or selective disclosure",
                    "Applies to ALL sustainability-related claims"
                ],
                "penalties": {
                    "violation": "FCA enforcement action, fines, restrictions"
                },
                "claim_validation_rules": [
                    {"pattern": "sustainable|green|ethical", "requirement": "Must be substantiated and not misleading"},
                    {"pattern": "esg|responsible investment", "requirement": "Must have clear methodology"}
                ]
            },
            
            "UK_TCFD": {
                "name": "UK TCFD Mandatory Disclosure",
                "jurisdiction": "United Kingdom",
                "authority": "HM Treasury / FCA",
                "effective_date": "2022-04-06",
                "applicability": "UK premium listed companies, large private companies",
                "key_requirements": [
                    "Governance of climate risks and opportunities",
                    "Strategy including scenario analysis",
                    "Risk management processes",
                    "Metrics and targets including GHG emissions"
                ],
                "claim_validation_rules": [
                    {"pattern": "climate strategy|tcfd", "requirement": "Must disclose 4 TCFD pillars"},
                    {"pattern": "scenario analysis|climate scenario", "requirement": "Must include 1.5°C and 2°C+ scenarios"}
                ]
            },
            
            # =============================================
            # GLOBAL FRAMEWORKS
            # =============================================
            "GHG_PROTOCOL": {
                "name": "GHG Protocol Corporate Standard",
                "jurisdiction": "Global",
                "authority": "WRI / WBCSD",
                "effective_date": "2001-01-01",
                "applicability": "Voluntary (de facto standard)",
                "key_requirements": [
                    "Scope 1, 2, 3 emissions inventory",
                    "Operational or financial control boundaries",
                    "Location-based and market-based Scope 2",
                    "15 Scope 3 categories",
                    "Base year recalculation policy"
                ],
                "claim_validation_rules": [
                    {"pattern": "scope 1|scope 2|scope 3", "requirement": "Must follow GHG Protocol methodology"},
                    {"pattern": "carbon footprint|ghg inventory", "requirement": "Must cover all material emission sources"}
                ]
            },
            
            "SBTI": {
                "name": "Science Based Targets initiative",
                "jurisdiction": "Global",
                "authority": "CDP, UNGC, WRI, WWF",
                "effective_date": "2015-01-01",
                "applicability": "Voluntary corporate targets",
                "key_requirements": [
                    "1.5°C or well-below 2°C pathway alignment",
                    "Scope 1, 2 mandatory, Scope 3 if >40% of emissions",
                    "5-10 year target timeframe",
                    "Annual progress reporting"
                ],
                "claim_validation_rules": [
                    {"pattern": "science based|sbti|1.5", "requirement": "Must have SBTi validated target"},
                    {"pattern": "paris aligned|paris agreement", "requirement": "Must show alignment pathway"}
                ]
            },
            
            "GRI_STANDARDS": {
                "name": "GRI Sustainability Reporting Standards",
                "jurisdiction": "Global",
                "authority": "Global Reporting Initiative",
                "effective_date": "2023-01-01",
                "applicability": "Voluntary (widely adopted)",
                "key_requirements": [
                    "Material topics disclosure",
                    "Sector-specific disclosures",
                    "Stakeholder engagement",
                    "Impact materiality assessment"
                ],
                "claim_validation_rules": [
                    {"pattern": "gri report|gri standards", "requirement": "Must follow GRI Universal Standards 2021"},
                    {"pattern": "materiality assessment", "requirement": "Must show stakeholder engagement process"}
                ]
            },
            
            "CDP": {
                "name": "CDP (Carbon Disclosure Project)",
                "jurisdiction": "Global",
                "authority": "CDP Non-profit",
                "effective_date": "2000-01-01",
                "applicability": "Investor/customer requested disclosure",
                "key_requirements": [
                    "Climate, Water, Forests questionnaires",
                    "GHG emissions disclosure",
                    "Climate risk and opportunity assessment",
                    "Supply chain engagement"
                ],
                "claim_validation_rules": [
                    {"pattern": "cdp score|cdp a list", "requirement": "Must submit annual CDP questionnaire"},
                    {"pattern": "supplier engagement", "requirement": "Must have supplier CDP program"}
                ]
            }
        }
    
    def scan_regulatory_compliance(self, company: str, claim: Dict[str, Any],
                                   evidence: List[Dict[str, Any]],
                                   jurisdiction: str = "India",
                                   country: Optional[str] = None,
                                   industry: str = "",
                                   carbon_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        carbon_data = carbon_data if isinstance(carbon_data, dict) else {}
        sbti_not_submitted = bool(carbon_data.get("flags", {}).get("sbti_not_submitted")) or (
            str(carbon_data.get("sbti_status", "")).strip().lower() == "not submitted"
        )
        """
        Scan claim against applicable regulations
        
        Args:
            company: Company name
            claim: ESG claim to verify
            evidence: Supporting evidence
            jurisdiction: Primary jurisdiction (India, EU, US, UK, Global)
        
        Returns:
            Comprehensive regulatory compliance assessment
        """
        
        print(f"\n{'='*60}")
        print(f"⚖️  AGENT: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        print(f"Jurisdiction: {jurisdiction}")
        print(f"Claim: {claim.get('claim_text', '')[:80]}...")
        
        claim_text = claim.get("claim_text", "").lower()
        evidence_text = self._combine_evidence(evidence)
        
        # 1. Identify applicable regulations
        print("🔍 Identifying applicable regulations...")
        applicable_regs = self._identify_applicable_regulations(
            claim_text,
            jurisdiction,
            company,
            industry,
            country,
        )
        
        # 2. Check compliance for each regulation
        print(f"⚖️ Checking compliance against {len(applicable_regs)} regulations...")
        compliance_results = []
        for reg_id in applicable_regs:
            result = self._check_regulation_compliance(
                reg_id,
                claim,
                evidence_text,
                company=company,
                sbti_not_submitted=sbti_not_submitted,
            )
            compliance_results.append(result)
        # Cross-validation guard: carbon and regulatory SBTi status must be consistent.
        if sbti_not_submitted:
            for row in compliance_results:
                if str(row.get("regulation_name", "")).lower().find("science based targets initiative") != -1:
                    if str(row.get("status", "")).upper() == "COMPLIANT":
                        row["status"] = "GAP"
                        row.setdefault("gap_details", []).append(
                            "Carbon agent confirms no SBTi submission despite compliance flag"
                        )
                        row["critical_gap"] = True
                        print("⚠️ SBTi contradiction detected and resolved")

        
        # 3. LLM deep compliance analysis
        print("🤖 Running AI compliance analysis...")
        llm_analysis = self._llm_compliance_analysis(company, claim_text, evidence_text, applicable_regs)
        
        # 4. Identify regulatory risks
        print("⚠️ Identifying regulatory risks...")
        regulatory_risks = self._identify_regulatory_risks(compliance_results)
        
        # 5. Generate compliance score
        score_result = calculate_compliance_score(compliance_results)
        
        result = {
            "company": company,
            "claim_id": claim.get("claim_id"),
            "jurisdiction": jurisdiction,
            "applicable_regulations": [self.regulations[r]["name"] for r in applicable_regs],
            "compliance_results": compliance_results,
            "llm_analysis": llm_analysis,
            "regulatory_risks": regulatory_risks,
            "compliance_score": score_result,
            "recommendations": self._generate_compliance_recommendations(compliance_results),
            "upcoming_regulations": self._get_upcoming_regulations(jurisdiction)
        }

        result["risk_level"] = score_result["risk_level"]
        result["gaps"] = score_result["gap_count"]
        result["total_regulations"] = score_result["total_count"]
        result["compliant_regulations"] = score_result["compliant_count"]
        result["score_breakdown"] = score_result["score_breakdown"]
        
        print(f"\n✅ Regulatory scan complete:")
        print(f"   Applicable regulations: {len(applicable_regs)}")
        print(f"   Compliance score: {score_result['score']}/100")
        print(f"   Risk level: {score_result['risk_level']}")
        
        return result
    
    def _combine_evidence(self, evidence: List[Dict[str, Any]]) -> str:
        """Combine evidence into searchable text"""
        texts = []
        for ev in evidence[:15]:
            title = ev.get("title", "")
            snippet = ev.get("snippet", ev.get("relevant_text", ""))
            texts.append(f"{title}: {snippet}")
        return "\n\n".join(texts)[:8000]
    
    def _identify_applicable_regulations(self, claim_text: str,
                                        jurisdiction: str,
                                        company: str,
                                        industry: str,
                                        country: Optional[str] = None) -> List[str]:
        """Identify regulations applicable to the claim"""
        
        applicable = []

        country_code = (country or "").upper()
        company_upper = (company or "").upper()
        if not country_code:
            if jurisdiction == "India":
                country_code = "IN"
            elif jurisdiction == "EU":
                country_code = "DE"
            elif jurisdiction == "UK":
                country_code = "UK"
            elif jurisdiction == "US":
                country_code = "US"

        framework_names = get_applicable_frameworks(company, industry, country_code)
        reg_ids_by_name = {
            reg.get("name"): reg_id
            for reg_id, reg in self.regulations.items()
        }

        for framework_name in framework_names:
            reg_id = reg_ids_by_name.get(framework_name)
            if not reg_id:
                reg_id = FRAMEWORK_NAME_ALIASES.get(framework_name)
            if reg_id:
                applicable.append(reg_id)

        allowed_jurisdictions = {"Global"}
        if country_code in ("IN", "INDIA") or any(ex in company_upper for ex in ("NSE", "BSE")):
            allowed_jurisdictions.add("India")
        if country_code in EU_COUNTRIES:
            allowed_jurisdictions.add("European Union")
        if country_code in UK_COUNTRIES or "LONDON" in company_upper:
            allowed_jurisdictions.add("United Kingdom")
        if country_code in US_COUNTRIES:
            allowed_jurisdictions.add("United States")
        
        # Check claim content for additional applicable regulations
        for reg_id, reg_data in self.regulations.items():
            if reg_id in applicable:
                continue
            if reg_data.get("jurisdiction") not in allowed_jurisdictions:
                continue
                
            for rule in reg_data.get("claim_validation_rules", []):
                if re.search(rule["pattern"], claim_text, re.IGNORECASE):
                    applicable.append(reg_id)
                    break
        
        return list(set(applicable))
    
    def _check_regulation_compliance(self, reg_id: str, claim: Dict[str, Any],
                                     evidence_text: str, company: str = "",
                                     sbti_not_submitted: bool = False) -> Dict[str, Any]:
        """Check compliance with a specific regulation"""
        
        reg = self.regulations.get(reg_id, {})
        claim_text = claim.get("claim_text", "").lower()
        evidence_lower = evidence_text.lower()
        
        violations = []
        requirements_met = []
        requirements_unverified = []
        
        # Check claim validation rules
        for rule in reg.get("claim_validation_rules", []):
            pattern = rule["pattern"]
            requirement = rule["requirement"]
            
            if re.search(pattern, claim_text, re.IGNORECASE):
                # Claim triggers this rule - check if requirement is met
                requirement_keywords = requirement.lower().split()
                key_terms = [w for w in requirement_keywords if len(w) > 4][:5]
                
                if any(term in evidence_lower for term in key_terms):
                    requirements_met.append({
                        "triggered_by": pattern,
                        "requirement": requirement,
                        "status": "Likely Compliant"
                    })
                else:
                    requirements_unverified.append({
                        "triggered_by": pattern,
                        "requirement": requirement,
                        "status": "Cannot Verify - Evidence Insufficient"
                    })
        
        # Calculate compliance status
        total_rules = len(requirements_met) + len(requirements_unverified)
        if total_rules == 0:
            compliance_status = "Not Applicable"
            compliance_percentage = 100
        elif len(requirements_unverified) == 0:
            compliance_status = "Compliant"
            compliance_percentage = 100
        elif len(requirements_met) == 0:
            compliance_status = "Non-Compliant"
            compliance_percentage = 0
        else:
            compliance_status = "Partially Compliant"
            compliance_percentage = (len(requirements_met) / total_rules) * 100

        gap_details = [r.get("requirement") for r in requirements_unverified if r.get("requirement")]

        net_zero_required_frameworks = [
            "science based targets initiative",
            "fca anti-greenwashing",
            "corporate sustainability reporting directive",
        ]
        net_zero_claim = any(
            kw in claim_text for kw in ["net zero", "net-zero", "carbon neutral", "carbon negative", "climate positive"]
        )
        framework_name = str(reg.get("name") or "").strip().lower()
        critical_gap = False
        # Hard SBTi gate: keyword hits are not enough without registry confirmation.
        if "science based targets initiative" in framework_name:
            in_registry = self._company_in_sbti_registry(company)
            if sbti_not_submitted or not in_registry:
                gap_message = "No SBTi submission/validation found in public SBTi list"
                if gap_message not in gap_details:
                    gap_details.append(gap_message)
                critical_gap = True
        sbti_evidence_present = any(
            token in evidence_lower
            for token in [
                "science based targets initiative",
                "science-based targets",
                "companies-taking-action",
                "sbti",
                "validated target",
                "targets set",
            ]
        )

        # For net-zero claims, explicit SBTi registry evidence should count as confirmation.
        if (
            "science based targets initiative" in framework_name
            and net_zero_claim
            and sbti_evidence_present
            and not requirements_met
        ):
            requirements_met.append({
                "triggered_by": "net-zero claim + SBTi evidence",
                "requirement": "Must have SBTi validated target",
                "status": "Likely Compliant",
            })

        evidence_confirms_compliance = len(requirements_met) > 0 and len(requirements_unverified) == 0

        is_required_framework = any(req in framework_name for req in net_zero_required_frameworks)
        if net_zero_claim and is_required_framework and not evidence_confirms_compliance:
            gap_message = f"Cannot confirm {reg.get('name')} compliance from available evidence"
            if gap_message not in gap_details:
                gap_details.append(gap_message)
            critical_gap = True

        has_gap = len(gap_details) > 0
        # Status taxonomy:
        #   GAP            – confirmed gap or critical-gap framework
        #   UNCERTAIN      – framework was triggered but evidence is missing
        #   COMPLIANT      – at least one requirement was triggered AND met,
        #                     and no gaps remain
        #   NOT_EVALUATED  – the claim never triggered any of this framework's
        #                     claim_validation_rules (i.e., the framework
        #                     wasn't actually tested). Previously this case
        #                     silently defaulted to COMPLIANT, producing
        #                     misleading "company X is compliant with GHG
        #                     Protocol" rows when the scanner never even
        #                     evaluated the framework against the claim.
        if has_gap and critical_gap:
            status = "GAP"
        elif has_gap and len(requirements_met) == 0 and not critical_gap:
            status = "UNCERTAIN"
        elif has_gap:
            status = "GAP"
        elif total_rules == 0:
            status = "NOT_EVALUATED"
        elif len(requirements_met) > 0:
            status = "COMPLIANT"
        else:
            status = "UNCERTAIN"
        
        return {
            "regulation_id": reg_id,
            "regulation_name": reg.get("name"),
            "jurisdiction": reg.get("jurisdiction"),
            "authority": reg.get("authority"),
            "status": status,
            "gap_details": gap_details,
            "compliance_status": compliance_status,
            "compliance_percentage": round(compliance_percentage, 1),
            "critical_gap": critical_gap,
            "requirements_met": requirements_met,
            "requirements_unverified": requirements_unverified,
            "violations": violations,
            "penalties": reg.get("penalties", {})
        }

    def _company_in_sbti_registry(self, company: str) -> bool:
        names = self._load_sbti_company_names()
        if not names:
            return False
        token = re.sub(r"[^a-z0-9 ]+", " ", (company or "").lower()).strip()
        if not token:
            return False
        token = re.sub(r"\b(inc|ltd|limited|corp|corporation|plc|group|co)\b", "", token).strip()
        return any(token and (token in name or name in token) for name in names)

    def _load_sbti_company_names(self) -> List[str]:
        """Load the SBTi company registry from the official Excel download.

        Source: https://sciencebasedtargets.org/download/excel — Google-Sheets
        backed XLSX with a `company_name` column (~14k rows). This is the
        authoritative public list. We refuse the brittle HTML-regex fallback
        that previously polluted the cache with CSS/HTML fragments — if the
        Excel fails, we keep the existing valid cache or return [] so the
        caller correctly reports UNCERTAIN rather than fabricating membership.
        """
        os.makedirs("data", exist_ok=True)
        now = datetime.utcnow()
        existing_valid: List[str] = []
        if os.path.exists(SBTI_CACHE_FILE):
            try:
                with open(SBTI_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                fetched_at = datetime.fromisoformat(str(cached.get("fetched_at")))
                cache_names = cached.get("company_names", []) or []
                # Detect poisoned caches: real SBTi data has 5k+ entries and
                # very few all-lowercase-no-space tokens. The bad regex
                # produced fragments like "a class", "html", etc.
                cache_is_clean = len(cache_names) >= 1000 and cached.get("source") == "sbti-excel"
                if cache_is_clean:
                    existing_valid = cache_names
                if cache_is_clean and now - fetched_at <= timedelta(days=SBTI_CACHE_DAYS):
                    return cache_names
            except Exception:
                pass

        company_names: List[str] = []
        if pd is not None:
            try:
                # SBTi serves a Google-Sheets-backed XLSX. requests handles
                # the redirect chain better than pandas's URL fetcher, then
                # we read from a temp buffer.
                import io
                resp = requests.get(SBTI_PROGRESS_REPORT_URL, timeout=60, allow_redirects=True)
                if resp.status_code == 200 and resp.content:
                    sheets = pd.read_excel(io.BytesIO(resp.content), sheet_name=None)
                    for sname, frame in sheets.items():
                        for col in frame.columns:
                            col_l = str(col).lower()
                            if col_l in {"company_name", "company"} or "company name" in col_l:
                                values = frame[col].dropna().astype(str).tolist()
                                company_names.extend(v.strip().lower() for v in values if v.strip() and len(v.strip()) >= 3)
                                break
                        if company_names:
                            break
            except Exception:
                company_names = []

        if not company_names and existing_valid:
            # Network failure but we have a clean cache from a previous run —
            # use it rather than poison the cache with garbage.
            return existing_valid

        if not company_names:
            # Refuse to write a poisoned cache. Return [] so the fetcher
            # reports UNCERTAIN cleanly.
            return []

        # Deduplicate and cache with a source marker so future runs can
        # detect/reject the legacy poisoned cache.
        deduped = sorted(set(company_names))
        try:
            with open(SBTI_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "fetched_at": now.isoformat(),
                    "company_names": deduped,
                    "source": "sbti-excel",
                    "source_url": SBTI_PROGRESS_REPORT_URL,
                    "count": len(deduped),
                }, f)
        except Exception:
            pass
        return deduped
    
    def _llm_compliance_analysis(self, company: str, claim_text: str,
                                 evidence_text: str, applicable_regs: List[str]) -> Dict[str, Any]:
        """Use LLM for deep compliance analysis"""
        
        reg_summaries = []
        for reg_id in applicable_regs[:5]:  # Top 5 regulations
            reg = self.regulations.get(reg_id, {})
            reg_summaries.append(f"- {reg.get('name')}: {reg.get('key_requirements', [])[:3]}")
        
        prompt = f"""{REGULATORY_COMPLIANCE_PROMPT}

COMPANY: {company}
CLAIM: {claim_text}

APPLICABLE REGULATIONS:
{chr(10).join(reg_summaries)}

EVIDENCE:
{evidence_text[:4000]}

Analyze regulatory compliance risks. Return JSON."""
        
        try:
            response = asyncio.run(call_llm("regulatory_scanning", prompt, system=REGULATORY_COMPLIANCE_PROMPT))
        except Exception as e:
            return {"analysis_performed": False, "error": f"LLM call failed: {e}"}
        
        try:
            cleaned = re.sub(r'```\s*json?\s*', '', response)
            cleaned = re.sub(r'```\s*', '', cleaned)
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(cleaned[start:end])
        except:
            pass
        
        return {"analysis_performed": True, "raw_analysis": response[:500]}
    
    def _identify_regulatory_risks(self, compliance_results: List[Dict]) -> List[Dict[str, Any]]:
        """Identify key regulatory risks"""
        
        risks = []
        
        for result in compliance_results:
            if result["compliance_status"] in ["Non-Compliant", "Partially Compliant"]:
                risk_level = "High" if result["compliance_status"] == "Non-Compliant" else "Medium"
                
                risks.append({
                    "regulation": result["regulation_name"],
                    "jurisdiction": result["jurisdiction"],
                    "risk_level": risk_level,
                    "unverified_requirements": [r["requirement"] for r in result["requirements_unverified"]],
                    "potential_penalties": result["penalties"]
                })
        
        # Sort by risk level
        risk_order = {"High": 0, "Medium": 1, "Low": 2}
        risks.sort(key=lambda x: risk_order.get(x["risk_level"], 2))
        
        return risks

    def _calculate_compliance_score(self, compliance_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Research-grade gap score: starts at 100 and subtracts per-gap penalties."""
        gaps = 0
        for row in compliance_results:
            if not isinstance(row, dict):
                continue
            unverified = row.get("requirements_unverified") or []
            gap_details = row.get("gap_details") or row.get("gaps_found") or []
            if isinstance(unverified, list):
                gaps += len(unverified)
            if isinstance(gap_details, list):
                gaps += len(gap_details)
            elif gap_details:
                gaps += 1

        score = max(0, round(100 - (gaps * 8)))
        risk_level = "Low" if score >= 75 else "Medium" if score >= 45 else "High"
        return {
            "score": score,
            "risk_level": risk_level,
            "gaps": gaps,
            "gap_count": gaps,
            "total_count": len(compliance_results),
            "total_regulations": len(compliance_results),
            "score_breakdown": f"100pts baseline minus {gaps} gap penalties (-{gaps * 8}pts) = {score}/100",
        }

    def _generate_compliance_recommendations(self, compliance_results: List[Dict]) -> List[str]:
        """Generate actionable compliance recommendations"""

        recommendations = []

        for result in compliance_results:
            if result["compliance_status"] == "Non-Compliant":
                recommendations.append(
                    f"[CRITICAL] {result['regulation_name']}: Address unverified requirements immediately"
                )
            elif result["compliance_status"] == "Partially Compliant":
                for req in result["requirements_unverified"][:2]:
                    recommendations.append(
                        f"[PARTIAL] {result['regulation_name']}: {req['requirement']}"
                    )

        if not recommendations:
            recommendations.append("[OK] Current disclosures appear compliant with applicable regulations")
            recommendations.append("[RECOMMEND] Consider voluntary third-party assurance for enhanced credibility")

        return recommendations[:10]

    def _get_upcoming_regulations(self, jurisdiction: str) -> List[Dict[str, Any]]:
        """Get upcoming regulatory changes"""

        upcoming = [
            {
                "regulation": "SEBI BRSR Core - Reasonable Assurance",
                "jurisdiction": "India",
                "effective": "FY 2024-25",
                "impact": "Mandatory external assurance of BRSR Core indicators"
            },
            {
                "regulation": "EU CSRD - Value Chain Due Diligence",
                "jurisdiction": "EU",
                "effective": "2025",
                "impact": "Extended due diligence requirements for large companies"
            },
            {
                "regulation": "ISSB S1/S2 Standards",
                "jurisdiction": "Global",
                "effective": "2024 (voluntary), 2025+ (adoption)",
                "impact": "Global baseline for sustainability disclosure"
            },
            {
                "regulation": "India Green Taxonomy",
                "jurisdiction": "India",
                "effective": "2025-26 (expected)",
                "impact": "Classification of sustainable activities for India"
            }
        ]

        if jurisdiction == "India":
            return [u for u in upcoming if u["jurisdiction"] in ["India", "Global"]]
        if jurisdiction == "EU":
            return [u for u in upcoming if u["jurisdiction"] in ["EU", "Global"]]
        return upcoming
    

# === NEW: End-to-end compliance scoring and gap detection ===
def compute_compliance_score(regulation_results: list) -> dict:
    """
    regulation_results: list of dicts with keys:
      regulation_name, gap_count (int), gaps_found (list of strings)
    Returns: dict with score (int 0-100), risk_level, per_regulation_status
    """
    if not regulation_results:
        return {
            "score": 0,
            "risk_level": "High",
            "per_regulation_status": [],
            "gaps": 0,
            "total_regulations": 0,
            "compliant_regulations": 0,
            "score_breakdown": "No frameworks checked",
        }

    total = len(regulation_results)
    per_regulation_status = []
    gaps = 0

    for r in regulation_results:
        gap_details = r.get("gap_details")
        if gap_details is None:
            gap_details = r.get("gaps_found", [])
        if not isinstance(gap_details, list):
            gap_details = [str(gap_details)] if gap_details else []

        gap_count = len(gap_details)
        has_gap = gap_count > 0
        status = "GAP FOUND" if has_gap else "COMPLIANT"

        if has_gap:
            gaps += 1

        per_regulation_status.append({
            "regulation": r["regulation_name"],
            "status": status,
            "gap_count": gap_count,
            "gap_details": gap_details,
            "gaps": gap_details,
        })

    # Build canonical list for the shared proportional scoring logic.
    canonical_results = []
    for r in regulation_results:
        gap_details = r.get("gap_details") if isinstance(r, dict) else []
        if gap_details is None:
            gap_details = r.get("gaps_found", []) if isinstance(r, dict) else []
        if not isinstance(gap_details, list):
            gap_details = [str(gap_details)] if gap_details else []

        status = "GAP" if gap_details else "COMPLIANT"
        materiality = "HIGH" if bool((r or {}).get("critical_gap")) else "MEDIUM"
        canonical_results.append({"status": status, "materiality": materiality})

    score_payload = calculate_compliance_score(canonical_results)
    compliant_count = score_payload["compliant_count"]
    score = score_payload["score"]
    if score >= 75:
        risk_level = "Low"
    elif score >= 45:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return {
        "score": score,
        "risk_level": risk_level,
        "per_regulation_status": per_regulation_status,
        "gaps": gaps,
        "total_regulations": total,
        "compliant_regulations": compliant_count,
        "score_breakdown": score_payload["score_breakdown"],
    }


def detect_regulation_gaps(company_name: str, claim_text: str, regulation_name: str, carbon_data: dict = None) -> dict:
    """
    Detects specific gaps between a claim and regulation requirements.
    Returns dict: {gap_count: int, gaps_found: list of str}
    All checks use only the text content — no paid APIs.
    """
    claim_lower = claim_text.lower()
    company_lower = company_name.lower()
    gaps = []
    if "science based target" in regulation_name.lower() or "sbti" in regulation_name.lower():
        has_sbti_mention = any(term in claim_lower for term in [
            "sbti", "science based target", "1.5°c", "1.5 degrees", "science-based"])
        has_net_zero_claim = any(term in claim_lower for term in [
            "net zero", "net-zero", "carbon neutral", "carbon negative"])
        if has_net_zero_claim and not has_sbti_mention:
            gaps.append("Net-zero/carbon neutral claim without SBTi validation mentioned")
        if "by 2050" in claim_lower and not has_sbti_mention:
            gaps.append("2050 target without Science Based Target validation")
    if "gri" in regulation_name.lower():
        has_scope_breakdown = any(term in claim_lower for term in [
            "scope 1", "scope 2", "scope 3"])
        if not has_scope_breakdown:
            gaps.append("No GRI-required Scope 1/2/3 emissions breakdown mentioned")
        if carbon_data and not carbon_data.get("scope_1"):
            gaps.append("Scope 1 emissions not disclosed (GRI 305-1 required)")
        if carbon_data and not carbon_data.get("scope_2"):
            gaps.append("Scope 2 emissions not disclosed (GRI 305-2 required)")
    if "cdp" in regulation_name.lower():
        has_cdp_mention = any(term in claim_lower for term in [
            "cdp", "carbon disclosure", "carbon disclosure project"])
        if not has_cdp_mention:
            gaps.append("No CDP disclosure score or submission referenced")
    if "ghg protocol" in regulation_name.lower():
        mentions_emissions = any(term in claim_lower for term in [
            "emissions", "carbon", "co2", "ghg", "greenhouse"])
        has_scope_boundary = any(term in claim_lower for term in [
            "scope 1", "scope 2", "operational", "market-based", "location-based"])
        if mentions_emissions and not has_scope_boundary:
            gaps.append("Emissions mentioned without GHG Protocol scope boundary definition")
    if "brsr" in regulation_name.lower() or "sebi" in regulation_name.lower():
        indian_companies = ["infosys", "tcs", "wipro", "hcl", "reliance", "tata", "mahindra", "hdfc", "icici", "bajaj", "asian paints"]
        is_indian = any(name in company_lower for name in indian_companies)
        if is_indian:
            has_brsr = any(term in claim_lower for term in ["brsr", "business responsibility", "sebi"])
            if not has_brsr:
                gaps.append("Indian company without BRSR compliance reference")
    if "tcfd" in regulation_name.lower():
        has_scenario = any(term in claim_lower for term in [
            "scenario", "physical risk", "transition risk", "climate risk"])
        if not has_scenario:
            gaps.append("No TCFD-required climate risk scenario analysis mentioned")
    return {"gap_count": len(gaps), "gaps_found": gaps}


# Global instance
regulatory_scanner = RegulatoryHorizonScanner()

def get_regulatory_scanner() -> RegulatoryHorizonScanner:
    """Get global regulatory scanner instance"""
    return regulatory_scanner


# ──────────────────────────────────────────────────────────────────────────
# Real-data compliance evaluation (added Apr 2026)
# ──────────────────────────────────────────────────────────────────────────


def evaluate_real_compliance(
    company: str,
    country: str = "",
    industry: str = "",
    report_chunks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run live fetchers against public regulatory registries.

    Returns rows shaped like the multi-jurisdiction scanner expects:
        {
            "jurisdiction": "...",
            "framework": "...",
            "status": "compliant" | "gap" | "uncertain" | "not_applicable",
            "specific_violation": "...",
            "evidence_url": "...",
            "source_name": "...",
            "fetched_at": "...",
            "penalty_score": int,
            "material_misstatement_risk": bool,
            "real_data": True,  # marker so the report renderer can show "verified"
        }

    Each row corresponds to one ACTUAL public registry / API check. This
    is the authoritative compliance signal — the keyword-rule and DDG-search
    rows are kept as supplementary, but real-data rows take precedence in
    scoring.

    ``report_chunks`` is forwarded to fetchers that verify against the
    company's own disclosures (currently only the GHG Protocol fetcher).
    """
    try:
        from utils.regulatory_fetchers import fetch_all_real_compliance
    except Exception as exc:
        return {"rows": [], "error": f"regulatory_fetchers import failed: {exc}"}

    rows: List[Dict[str, Any]] = []
    raw_results = fetch_all_real_compliance(
        company=company, country=country, industry=industry, report_chunks=report_chunks
    )

    # Map verified-flag → multi-jurisdiction status string
    jurisdiction_for_framework = {
        "SEC Climate Disclosure Rule": "US",
        "TCFD-aligned Climate Disclosure": "Global",
        "CDP (Carbon Disclosure Project)": "Global",
        "UN Global Compact": "Global",
        "Science Based Targets initiative": "Global",
        "GHG Protocol Corporate Standard": "Global",
        "GRI Sustainability Reporting Standards": "Global",
        "FTC Green Guides": "US",
        "CSRD / EU ESEF Filing": "EU",
        "SEBI BRSR (India)": "India",
        "NSE/BSE Listed Equity": "India",
    }

    for raw in raw_results:
        framework = raw.get("framework", "")
        verified = raw.get("verified")
        applicable = raw.get("applicable", True)

        if not applicable:
            status = "not_applicable"
            penalty = 0
            material = False
        elif verified is True:
            status = "compliant"
            penalty = 0
            material = False
        elif verified is False:
            status = "gap"
            penalty = 12
            material = True
        else:
            status = "uncertain"
            penalty = 4
            material = False

        rows.append({
            "jurisdiction": jurisdiction_for_framework.get(framework, "Global"),
            "framework": framework,
            "status": status,
            "specific_violation": raw.get("evidence", ""),
            "evidence_url": raw.get("url", ""),
            "source_name": raw.get("source_name", ""),
            "fetched_at": raw.get("fetched_at", ""),
            "penalty_score": penalty,
            "material_misstatement_risk": material,
            "real_data": True,
            "applicable": applicable,
        })

    summary = {
        "rows": rows,
        "evaluated_count": sum(1 for r in rows if r["status"] in {"compliant", "gap"}),
        "compliant_count": sum(1 for r in rows if r["status"] == "compliant"),
        "gap_count": sum(1 for r in rows if r["status"] == "gap"),
        "uncertain_count": sum(1 for r in rows if r["status"] == "uncertain"),
        "not_applicable_count": sum(1 for r in rows if r["status"] == "not_applicable"),
    }
    return summary
