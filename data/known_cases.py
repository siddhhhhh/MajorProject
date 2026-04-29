"""
data/known_cases.py
-------------------
Ground Truth: Known Greenwashing Cases

Verified greenwashing outcomes from regulatory enforcement actions,
court rulings, and settlements. Used by the pipeline to:
    1. Validate that our scoring engine correctly identifies known cases
    2. Calibrate confidence thresholds per industry
    3. Train/test the ML models on real outcomes

Each case includes:
    - Company and claim details
    - Regulatory outcome (fine, settlement, ruling)
    - Expected greenwashing score range
    - Source citations

Sources: SEC, FTC, EU Commission, Dutch ASA, Australian ACCC, UK ASA, SEBI
"""

from __future__ import annotations

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Expected output ranges for validation
# ---------------------------------------------------------------------------
# GW score should fall within [min, max] for the system to be "calibrated"
# ESG score gives a rough expected range for the company at that time

KNOWN_GREENWASHING_CASES: List[Dict[str, Any]] = [
    # ══════════════════════════════════════════════════════════════════
    # CONFIRMED GREENWASHING (Regulatory Actions / Court Rulings)
    # Expected GW Score: 65-100
    # ══════════════════════════════════════════════════════════════════
    {
        "case_id": "GW-001",
        "company": "DWS Group",
        "industry": "banking",
        "claim": "DWS claimed its ESG-integrated investment products applied rigorous sustainability criteria to all investments",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "SEC $19M fine (Sept 2023) for misleading ESG claims in investment products",
        "source": "SEC Enforcement Action, Release No. 34-98318",
        "year": 2023,
        "expected_gw_range": [65, 90],
        "expected_esg_range": [35, 55],
        "severity": "HIGH",
        "jurisdiction": "US",
    },
    {
        "case_id": "GW-002",
        "company": "Volkswagen",
        "industry": "automotive",
        "claim": "Volkswagen marketed 'Clean Diesel' vehicles as environmentally friendly with low emissions",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "~$33.3B cumulative cost of fines, settlements & buyback (per Reuters, June 2020); covers EPA, FTC, DOJ class actions and global remediation",
        "source": "EPA Enforcement, DOJ Settlement, Reuters reporting (Jun 2020)",
        "year": 2016,
        "expected_gw_range": [80, 100],
        "expected_esg_range": [15, 35],
        "severity": "CRITICAL",
        "jurisdiction": "US/EU",
    },
    {
        "case_id": "GW-003",
        "company": "Shell",
        "industry": "oil_and_gas",
        "claim": "Shell claimed to be investing heavily in renewable energy and transitioning to clean energy",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "Hague District Court ruling (May 2021) ordering 45% emissions cut by 2030; Dutch ASA upheld greenwashing complaint (2021)",
        "source": "Milieudefensie v. Royal Dutch Shell, ECLI:NL:RBDHA:2021:5339",
        "year": 2021,
        "expected_gw_range": [70, 95],
        "expected_esg_range": [25, 45],
        "severity": "HIGH",
        "jurisdiction": "Netherlands",
    },
    {
        "case_id": "GW-004",
        "company": "Keurig",
        "industry": "consumer_goods",
        "claim": "Keurig claimed K-Cup pods were recyclable",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "FTC investigation; $3M settlement with Competition Bureau Canada (2022); class action settlements in US",
        "source": "Competition Bureau Canada, FTC Green Guides",
        "year": 2022,
        "expected_gw_range": [60, 85],
        "expected_esg_range": [40, 55],
        "severity": "MODERATE",
        "jurisdiction": "US/Canada",
    },
    {
        "case_id": "GW-005",
        "company": "H&M",
        "industry": "fast_fashion",
        "claim": "H&M Conscious Collection marketed as sustainable fashion using recycled materials",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "Dutch ACM warning (2022); EU Consumer Organisation BEUC complaint; Class action in US District Court (2022)",
        "source": "Quartz investigation, BEUC complaint, Chelsea Commodore v. H&M",
        "year": 2022,
        "expected_gw_range": [60, 85],
        "expected_esg_range": [35, 55],
        "severity": "MODERATE",
        "jurisdiction": "EU/US",
    },
    {
        "case_id": "GW-006",
        "company": "TotalEnergies",
        "industry": "oil_and_gas",
        "claim": "TotalEnergies claimed net-zero ambition by 2050 while expanding oil and gas production",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "French court ruled misleading advertising (2023); Greenpeace France complaint upheld",
        "source": "Tribunal Judiciaire de Paris, Climate Action 100+",
        "year": 2023,
        "expected_gw_range": [70, 95],
        "expected_esg_range": [25, 45],
        "severity": "HIGH",
        "jurisdiction": "France",
    },
    {
        "case_id": "GW-007",
        "company": "HSBC",
        "industry": "banking",
        "claim": "HSBC advertised planting 2 million trees while financing fossil fuel expansion",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "UK ASA banned HSBC advertisements as misleading (Oct 2022)",
        "source": "UK Advertising Standards Authority ruling",
        "year": 2022,
        "expected_gw_range": [60, 80],
        "expected_esg_range": [40, 60],
        "severity": "MODERATE",
        "jurisdiction": "UK",
    },
    {
        "case_id": "GW-008",
        "company": "BNY Mellon",
        "industry": "banking",
        "claim": "BNY Mellon Investment Advisor falsely implied all investments in certain ESG funds had undergone ESG quality review",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "SEC $1.5M penalty (May 2022)",
        "source": "SEC Administrative Proceeding File No. 3-20867",
        "year": 2022,
        "expected_gw_range": [60, 80],
        "expected_esg_range": [45, 60],
        "severity": "MODERATE",
        "jurisdiction": "US",
    },
    {
        "case_id": "GW-009",
        "company": "Santos",
        "industry": "oil_and_gas",
        "claim": "Santos described natural gas as 'clean energy' in its 2020 annual report",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "Australian Federal Court ruled Santos' 'clean energy' claim misleading (Nov 2024)",
        "source": "Australasian Centre for Corporate Responsibility v Santos Ltd",
        "year": 2024,
        "expected_gw_range": [70, 90],
        "expected_esg_range": [25, 45],
        "severity": "HIGH",
        "jurisdiction": "Australia",
    },
    {
        "case_id": "GW-010",
        "company": "Vale",
        "industry": "mining",
        "claim": "Vale claimed commitment to safety and environmental protection while operating Brumadinho dam",
        "outcome": "CONFIRMED_GREENWASHING",
        "regulatory_action": "$7B settlement (Feb 2021); Criminal charges; Multiple regulatory sanctions",
        "source": "Brazilian Federal Police, Minas Gerais State Prosecution",
        "year": 2019,
        "expected_gw_range": [75, 100],
        "expected_esg_range": [10, 30],
        "severity": "CRITICAL",
        "jurisdiction": "Brazil",
    },

    # ══════════════════════════════════════════════════════════════════
    # LEGITIMATE ESG LEADERS (Verified Good Performers)
    # Expected GW Score: 10-35
    # ══════════════════════════════════════════════════════════════════
    {
        "case_id": "LEGIT-001",
        "company": "Ørsted",
        "industry": "renewable_energy",
        "claim": "Ørsted transformed from fossil fuel company DONG Energy to world's largest offshore wind developer",
        "outcome": "LEGITIMATE",
        "regulatory_action": "No enforcement; SBTi validated; CDP A-list; recognized by Corporate Knights, MSCI AAA",
        "source": "SBTi Target Dashboard, CDP Scores, MSCI ESG Ratings",
        "year": 2024,
        "expected_gw_range": [5, 30],
        "expected_esg_range": [75, 95],
        "severity": "NONE",
        "jurisdiction": "Denmark",
    },
    {
        "case_id": "LEGIT-002",
        "company": "Patagonia",
        "industry": "consumer_goods",
        "claim": "Patagonia claims to be in business to save our home planet with verified supply chain transparency",
        "outcome": "LEGITIMATE",
        "regulatory_action": "No enforcement; B Corp certified; 1% for the Planet member; Fair Trade certified",
        "source": "B Corp Directory, 1% for the Planet, Fair Trade USA",
        "year": 2024,
        "expected_gw_range": [5, 25],
        "expected_esg_range": [80, 95],
        "severity": "NONE",
        "jurisdiction": "US",
    },
    {
        "case_id": "LEGIT-003",
        "company": "Infosys",
        "industry": "technology",
        "claim": "Infosys achieved carbon neutral status across Scope 1, 2, and some Scope 3 categories",
        "outcome": "LEGITIMATE",
        "regulatory_action": "No enforcement; CDP A-list; DJSI member; verified by external auditors",
        "source": "Infosys ESG Data Center, CDP Climate, PAS 2060 certification",
        "year": 2024,
        "expected_gw_range": [10, 35],
        "expected_esg_range": [70, 90],
        "severity": "NONE",
        "jurisdiction": "India",
    },

    # ══════════════════════════════════════════════════════════════════
    # BORDERLINE / MIXED CASES
    # Expected GW Score: 35-65
    # ══════════════════════════════════════════════════════════════════
    {
        "case_id": "MIXED-001",
        "company": "Amazon",
        "industry": "technology",
        "claim": "Amazon's Climate Pledge: net-zero carbon by 2040 with 100,000 electric delivery vehicles",
        "outcome": "MIXED",
        "regulatory_action": "No formal greenwashing action; however, worker safety violations, union suppression concerns; Carbon footprint grew 40% (2019-2021) while pledging net zero",
        "source": "Amazon Sustainability Report, The Verge analysis, CDP disclosure",
        "year": 2023,
        "expected_gw_range": [35, 55],
        "expected_esg_range": [50, 70],
        "severity": "LOW",
        "jurisdiction": "US",
    },
    {
        "case_id": "MIXED-002",
        "company": "BP",
        "industry": "oil_and_gas",
        "claim": "BP rebranded as 'Beyond Petroleum' with stated commitment to energy transition",
        "outcome": "MIXED",
        "regulatory_action": "UK ASA investigation (2019-2020); No formal fine but required ad modifications; subsequently scaled back renewable targets in 2023",
        "source": "UK ASA, Financial Times analysis, Carbon Tracker",
        "year": 2023,
        "expected_gw_range": [55, 80],
        "expected_esg_range": [30, 50],
        "severity": "MODERATE",
        "jurisdiction": "UK",
    },
]


# ---------------------------------------------------------------------------
# Validation Functions
# ---------------------------------------------------------------------------

def validate_pipeline_output(
    company: str,
    gw_score: float,
    esg_score: float,
) -> Dict[str, Any]:
    """
    Check if pipeline output falls within expected ranges for known cases.

    Returns:
        {
            "case_found": True/False,
            "case_id": "GW-001",
            "gw_in_range": True/False,
            "esg_in_range": True/False,
            "gw_expected": [65, 90],
            "gw_actual": 72.5,
            "calibration_status": "CALIBRATED" | "NEEDS_REVIEW" | "MISCALIBRATED"
        }
    """
    company_lower = company.lower().strip()

    for case in KNOWN_GREENWASHING_CASES:
        case_company = case["company"].lower().strip()
        # Fuzzy match: check if either contains the other
        if case_company in company_lower or company_lower in case_company:
            gw_range = case["expected_gw_range"]
            esg_range = case["expected_esg_range"]

            gw_in_range = gw_range[0] <= gw_score <= gw_range[1]
            esg_in_range = esg_range[0] <= esg_score <= esg_range[1]

            # Calibration status
            if gw_in_range and esg_in_range:
                status = "CALIBRATED"
            elif gw_in_range or esg_in_range:
                status = "NEEDS_REVIEW"
            else:
                status = "MISCALIBRATED"

            return {
                "case_found": True,
                "case_id": case["case_id"],
                "company": case["company"],
                "outcome": case["outcome"],
                "gw_in_range": gw_in_range,
                "esg_in_range": esg_in_range,
                "gw_expected": gw_range,
                "gw_actual": round(gw_score, 1),
                "esg_expected": esg_range,
                "esg_actual": round(esg_score, 1),
                "calibration_status": status,
                "regulatory_action": case["regulatory_action"],
            }

    return {
        "case_found": False,
        "calibration_status": "NO_GROUND_TRUTH",
    }


def get_all_cases_for_industry(industry: str) -> List[Dict[str, Any]]:
    """Get all known cases for an industry for sector-specific calibration."""
    return [
        c for c in KNOWN_GREENWASHING_CASES
        if c["industry"].lower() == industry.lower()
    ]


def get_calibration_summary() -> Dict[str, Any]:
    """
    Get overall calibration statistics for the ground truth dataset.
    Used by the calibration pipeline to track accuracy over time.
    """
    total = len(KNOWN_GREENWASHING_CASES)
    by_outcome = {}
    by_industry = {}
    by_severity = {}

    for case in KNOWN_GREENWASHING_CASES:
        outcome = case["outcome"]
        industry = case["industry"]
        severity = case["severity"]

        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        by_industry[industry] = by_industry.get(industry, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1

    return {
        "total_cases": total,
        "by_outcome": by_outcome,
        "by_industry": by_industry,
        "by_severity": by_severity,
        "coverage_note": (
            "Ground truth covers regulatory enforcement (SEC, FTC, EU, UK ASA, ACCC) "
            "and court rulings. Does NOT cover undetected greenwashing. "
            "Dataset should be expanded continuously as new enforcement actions occur."
        ),
    }


def get_known_contradictions(company_name: str, claim_text: str) -> List[Dict[str, Any]]:
    """Return known greenwashing cases that match a given company and claim.

    Performs fuzzy company name matching and optional claim keyword overlap
    to surface high-confidence ground-truth contradictions from the regulatory
    database.
    """
    if not company_name:
        return []

    company_lower = company_name.lower().strip()
    claim_lower = (claim_text or "").lower()
    matches: List[Dict[str, Any]] = []

    for case in KNOWN_GREENWASHING_CASES:
        case_company = case.get("company", "").lower().strip()
        # Fuzzy match: either name contains the other
        if not (case_company in company_lower or company_lower in case_company):
            continue

        # Only return cases that are CONFIRMED or MIXED greenwashing
        outcome = str(case.get("outcome", "")).upper()
        if outcome not in {"CONFIRMED_GREENWASHING", "MIXED"}:
            continue

        # Build a contradiction record
        matches.append({
            "case_id": case.get("case_id"),
            "severity": case.get("severity", "MEDIUM"),
            "description": case.get("regulatory_action", "Known regulatory case"),
            "contradiction_text": case.get("regulatory_action", ""),
            "source": case.get("source", "Known contradictions database"),
            "source_url": "",
            "year": case.get("year"),
            "confidence": "HIGH",
            "source_type": "verified_regulatory_case",
            "outcome": outcome,
        })

    return matches

