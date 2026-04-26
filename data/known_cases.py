"""
Known Greenwashing Regulatory Cases Database
------------------------------------------------
This module contains a curated database of verified greenwashing regulatory actions
and a function to match company claims against known contradiction cases.

All cases are sourced from public regulatory records, court rulings, and major
NGO investigations. Used for high-confidence contradiction detection in ESG
claim analysis.
"""
import re
from typing import List, Dict

# Main database: company key (lowercase) -> list of contradiction cases
doc_url = "https://www.clientearth.org/projects/the-greenwashing-files/bp/"
KNOWN_GREENWASHING_CASES: Dict[str, List[Dict]] = {
    "bp": [
        {
            "claim_pattern": r"net.?zero|carbon neutral|1\\.5|paris agreement|renewabl",
            "contradiction_text": "BP increased planned oil and gas investment by $8bn in 2023, contradicting net-zero direction. CEO Bernard Looney resigned amid governance failures.",
            "source": "Reuters / Guardian, February 2023",
            "source_url": "https://www.theguardian.com/business/2023/feb/07/bp-increases-fossil-fuel-investment-retreats-from-climate-targets",
            "year": 2023,
            "severity": "high",
            "regulatory_body": "ClientEarth (UK)"
        },
        {
            "claim_pattern": r"net.?zero|2050|sustainable",
            "contradiction_text": "ClientEarth filed historic lawsuit against BP board directors personally for mismanaging climate risk, arguing net-zero strategy was inadequate and misleading to investors.",
            "source": "ClientEarth vs BP Board, February 2023",
            "source_url": doc_url,
            "year": 2023,
            "severity": "high",
            "regulatory_body": "UK High Court"
        }
    ],
    "shell": [
        {
            "claim_pattern": r"net.?zero|carbon neutral|2050|emission",
            "contradiction_text": "Dutch court ruled Shell must reduce absolute emissions by 45% by 2030 vs 2019 levels, finding Shell's climate plan was insufficient and legally binding emission cuts required.",
            "source": "Milieudefensie v Shell, District Court The Hague, May 2021",
            "source_url": "https://uitspraken.rechtspraak.nl/inziendocument?id=ECLI:NL:RBDHA:2021:5339",
            "year": 2021,
            "severity": "high",
            "regulatory_body": "Dutch District Court, The Hague"
        },
        {
            "claim_pattern": r"renewable|clean energy|sustainable|net.?zero",
            "contradiction_text": "Shell's own annual report showed 95%+ of energy sales remained fossil fuels as of 2023. Shell lobbied against EU emissions regulations while claiming climate leadership.",
            "source": "Shell Annual Report 2023 / InfluenceMap Report",
            "source_url": "https://influencemap.org/report/Big-Oil-Reality-Check-2023",
            "year": 2023,
            "severity": "high",
            "regulatory_body": "InfluenceMap / ClientEarth"
        }
    ],
    "hsbc": [
        {
            "claim_pattern": r"green|sustain|carbon|climate|tree|net.?zero",
            "contradiction_text": "UK ASA banned HSBC adverts in October 2022 for misleading net-zero claims. Ads showing tree planting and clean energy failed to mention HSBC's continued financing of fossil fuel expansion.",
            "source": "UK ASA Ruling A22-1218011, October 2022",
            "source_url": "https://www.asa.org.uk/rulings/hsbc-uk-bank-plc-a22-1218011-hsbc-uk-bank-plc.html",
            "year": 2022,
            "severity": "high",
            "regulatory_body": "UK Advertising Standards Authority"
        }
    ],
    "ryanair": [
        {
            "claim_pattern": r"lowest emission|green|sustainable|eco|carbon",
            "contradiction_text": "UK ASA banned Ryanair's 'lowest emissions airline' claim in 2020, ruling that the comparator data was misleading and the claim could not be substantiated.",
            "source": "UK ASA Ruling G19-1040356, February 2020",
            "source_url": "https://www.asa.org.uk/rulings/ryanair-ltd-g19-1040356.html",
            "year": 2020,
            "severity": "high",
            "regulatory_body": "UK Advertising Standards Authority"
        }
    ],
    "volkswagen": [
        {
            "claim_pattern": r"clean|emission|diesel|sustainable|green",
            "contradiction_text": "US EPA found Volkswagen installed defeat devices in 11 million diesel vehicles worldwide to cheat emissions tests. VW paid over $33bn in fines and settlements globally.",
            "source": "US EPA Notice of Violation, September 2015",
            "source_url": "https://www.epa.gov/vw",
            "year": 2015,
            "severity": "high",
            "regulatory_body": "US EPA / DOJ"
        }
    ],
    "h&m": [
        {
            "claim_pattern": r"conscious|sustainable|recycl|eco|green|organic",
            "contradiction_text": "Norwegian Consumer Authority found H&M's Conscious Collection used misleading sustainability scores. The Higg Index data underpinning claims was suspended after independent review found methodological flaws.",
            "source": "Norwegian Consumer Authority, July 2022",
            "source_url": "https://www.forbrukerradet.no/undersokelse/no-undersokelsekategori/hm-greenwashing/",
            "year": 2022,
            "severity": "high",
            "regulatory_body": "Norwegian Consumer Authority"
        }
    ],
    "exxonmobil": [
        {
            "claim_pattern": r"carbon capture|net.?zero|climate|sustainable|renewable",
            "contradiction_text": "ExxonMobil sued by state of Massachusetts for decades of climate denial and investor deception. Internal documents showed company knew about climate risks since 1970s while publicly disputing science.",
            "source": "Massachusetts AG v ExxonMobil, 2019 / House Oversight Committee 2021",
            "source_url": "https://www.mass.gov/news/ag-healey-files-suit-against-exxonmobil",
            "year": 2021,
            "severity": "high",
            "regulatory_body": "Massachusetts AG / US House Oversight"
        }
    ],
    "amazon": [
        {
            "claim_pattern": r"carbon neutral|renewable|sustainable|green|climate pledge",
            "contradiction_text": "Amazon's own sustainability report showed absolute carbon emissions increased 18% from 2019 to 2021 despite Climate Pledge. FTC scrutinized carbon-neutral delivery claims.",
            "source": "Amazon Sustainability Report 2021 / FTC Green Guide Review 2022",
            "source_url": "https://sustainability.aboutamazon.com/",
            "year": 2022,
            "severity": "medium",
            "regulatory_body": "US FTC"
        }
    ],
    "totalenergies": [
        {
            "claim_pattern": r"net.?zero|renewable|sustainable|multi.?energy|green",
            "contradiction_text": "TotalEnergies planned to increase oil and gas production through 2030 while advertising net-zero 2050 goals. French court ruled TotalEnergies must update its plan in line with Paris Agreement.",
            "source": "Notre Affaire à Tous v TotalEnergies, Paris Court 2023",
            "source_url": "https://notreaffaireatous.org/en/",
            "year": 2023,
            "severity": "high",
            "regulatory_body": "Paris Civil Court"
        }
    ],
    "chevron": [
        {
            "claim_pattern": r"paris|carbon|renewable|sustainable|climate|net.?zero",
            "contradiction_text": "Chevron's own Paris Agreement alignment report scored only 15% aligned by InfluenceMap. Chevron spent millions lobbying against climate regulations while claiming Paris support.",
            "source": "InfluenceMap Corporate Climate Responsibility Monitor 2022",
            "source_url": "https://influencemap.org/report/Big-Oil-Reality-Check-2023",
            "year": 2022,
            "severity": "high",
            "regulatory_body": "InfluenceMap"
        }
    ],
    "jpmorgan chase": [
        {
            "claim_pattern": r"net.?zero|paris|alignment|sustainable|climate",
            "description": "Left the Net Zero Banking Alliance (NZBA) in January 2025",
            "contradiction_text": "Withdrew from net-zero banking coalition while publicly claiming Paris Agreement alignment",
            "source": "NZBA / Reuters",
            "source_url": "https://www.unepfi.org/net-zero-banking/members/",
            "year": 2025,
            "severity": "high",
            "regulatory_body": "NZBA (UNEP FI)"
        },
        {
            "claim_pattern": r"climate action|net.?zero|engagement|transition",
            "description": "Left Climate Action 100+ in February 2024",
            "contradiction_text": "Exited world's largest investor climate engagement initiative",
            "source": "Financial Times",
            "source_url": "https://www.climateaction100.org/whos-involved/investors/",
            "year": 2024,
            "severity": "high",
            "regulatory_body": "Climate Action 100+"
        },
        {
            "claim_pattern": r"2030|absolute|intensity|target|decarbon",
            "description": "Shifted 2030 targets from absolute cuts to cost-based intensity metrics",
            "contradiction_text": "Replaced absolute emission commitments with weaker intensity targets",
            "source": "Bloomberg / JPMC 2024 Climate Report",
            "source_url": "https://www.jpmorganchase.com/ir/news/2024/climate-report-2024",
            "year": 2024,
            "severity": "high",
            "regulatory_body": "Public disclosure"
        },
        {
            "claim_pattern": r"net.?zero|fossil|sustainable|paris|climate",
            "description": "$429B fossil fuel financing since Paris Agreement - ranked #1 globally",
            "contradiction_text": "World's largest fossil fuel financier while claiming sustainable low-carbon alignment",
            "source": "Banking on Climate Chaos 2023 - RAN/BankTrack/Sierra Club",
            "source_url": "https://www.bankingonclimatechaos.org/",
            "year": 2023,
            "severity": "high",
            "regulatory_body": "NGO investigation"
        },
        {
            "claim_pattern": r"expansion|fossil|transition|low.?carbon|financing",
            "description": "Financed $38.1B in fossil fuel expansion in 2022 alone",
            "contradiction_text": "Continued large-scale fossil fuel expansion financing",
            "source": "Banking on Climate Chaos 2023",
            "source_url": "https://www.bankingonclimatechaos.org/",
            "year": 2023,
            "severity": "high",
            "regulatory_body": "NGO investigation"
        }
    ],
    "coca-cola": [
        {
            "claim_pattern": r"100% recyclable|circular|sustainable packaging|plastic pollution",
            "contradiction_text": "Named world's top plastic polluter for 5 consecutive years. Lawsuit in US argued '100% recyclable' claims are misleading as most plastic ends up in landfill or ocean.",
            "source": "Break Free From Plastic / Earth Island Institute Lawsuit 2022",
            "source_url": "https://www.earthisland.org/index.php/news/entry/earth-island-institute-files-lawsuit-against-the-coca-cola-company",
            "year": 2022,
            "severity": "high",
            "regulatory_body": "Break Free From Plastic / US Courts"
        }
    ],
    "delta air lines": [
        {
            "claim_pattern": r"carbon neutral|greenest airline|sustainable|climate",
            "contradiction_text": "Class-action lawsuit filed in California in 2023 alleging 'carbon neutral' claims are false and misleading, predicated on low-quality offsets that do not actually remove carbon.",
            "source": "Delta Air Lines Carbon Neutral Class Action, 2023",
            "source_url": "https://www.theguardian.com/business/2023/may/30/delta-air-lines-lawsuit-carbon-neutral-claims",
            "year": 2023,
            "severity": "high",
            "regulatory_body": "US Federal Court"
        }
    ],
    "google": [
        {
            "claim_pattern": r"carbon neutral|sustainability|water stewardship|zero waste",
            "contradiction_text": "Google's 2024 Environment Report showed greenhouse gas emissions rose 48% over 5 years due to AI data center energy demand, contradicting their 2030 net-zero ambition.",
            "source": "Google Environmental Report 2024 / Bloomberg",
            "source_url": "https://www.bloomberg.com/news/articles/2024-07-02/google-s-emissions-shot-up-48-since-2019-during-ai-building-boom",
            "year": 2024,
            "severity": "medium",
            "regulatory_body": "Bloomberg / Public Reports"
        }
    ],
    "goldman sachs": [
        {
            "claim_pattern": r"esg fund|sustainable investment|ethical|green",
            "contradiction_text": "SEC fined Goldman Sachs $4 million in 2022 for failing to follow its own ESG investment policies and procedures in some of its mutual funds.",
            "source": "SEC Press Release 2022-209",
            "source_url": "https://www.sec.gov/news/press-release/2022-209",
            "year": 2022,
            "severity": "medium",
            "regulatory_body": "US Securities and Exchange Commission"
        }
    ],
    "dws": [
        {
            "claim_pattern": r"esg integration|sustainable investing|green assets",
            "contradiction_text": "DWS (Deutsche Bank) raided by German police and fined $25 million by SEC for greenwashing—specifically misleading investors about how it used ESG factors in research.",
            "source": "SEC / BaFin Investigation 2023",
            "source_url": "https://www.sec.gov/news/press-release/2023-194",
            "year": 2023,
            "severity": "high",
            "regulatory_body": "US SEC / German BaFin"
        }
    ]
}

COMPANY_ALIASES = {
    "JPMC": "JPMorgan Chase",
    "JPM": "JPMorgan Chase",
    "J.P. Morgan": "JPMorgan Chase",
    "JP Morgan": "JPMorgan Chase",
    "JPMorgan": "JPMorgan Chase",
    "Shell PLC": "Shell",
    "Shell plc": "Shell",
    "BP plc": "BP",
    "BP PLC": "BP",
    "Unilever PLC": "Unilever",
    "unilever": "Unilever",
}

def get_known_contradictions(company_name: str, claim_text: str) -> List[Dict]:
    """
    Checks a company name and claim against the known cases database.
    Returns list of matching contradiction dicts.
    Matching is case-insensitive on company name and regex on claim text.
    """
    alias_map = {k.lower(): v for k, v in COMPANY_ALIASES.items()}
    canonical = alias_map.get(str(company_name).lower(), company_name)
    company_key = canonical.lower().strip()
    # fuzzy match: check if any key is a substring of company name or vice versa
    matched_key = None
    for key in KNOWN_GREENWASHING_CASES:
        if key in company_key or company_key in key:
            matched_key = key
            break
    if not matched_key:
        return []
    cases = KNOWN_GREENWASHING_CASES[matched_key]
    matched = []
    for case in cases:
        if re.search(case["claim_pattern"], claim_text, re.IGNORECASE):
            matched.append({
                **case,
                "confidence": "HIGH",
                "source_type": "verified_regulatory_case"
            })
    return matched

if __name__ == "__main__":
    # Simple test/demo
    test = get_known_contradictions("BP", "We aim to be a net zero company by 2050")
    print(test)
