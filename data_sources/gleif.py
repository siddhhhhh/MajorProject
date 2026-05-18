"""GLEIF — Global Legal Entity Identifier Foundation.

GLEIF publishes free LEI + corporate-structure data covering ~2M entities.
For v1 we ship a *curated* subsidiary map for the demo set so we don't have
to bundle the 2GB GLEIF concatenated file. v2 will swap to the bulk parquet.

Public API:
    subsidiaries_of(parent_lei) -> List[SubsidiaryEntry]
    parent_of(subsidiary_lei) -> Optional[str]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubsidiaryEntry:
    parent_lei: str
    subsidiary_lei: Optional[str]
    subsidiary_name: str
    country_iso3: Optional[str]
    relationship: str = "direct"   # direct | intermediate
    sector_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parent_lei":      self.parent_lei,
            "subsidiary_lei":  self.subsidiary_lei,
            "subsidiary_name": self.subsidiary_name,
            "country_iso3":    self.country_iso3,
            "relationship":    self.relationship,
            "sector_hint":     self.sector_hint,
        }


# Curated subsidiary map keyed by parent LEI. Sourced from public corporate
# disclosures + GLEIF look-ups. v2 will pull these from the bulk file.
_PARENT_SUBSIDIARIES: Dict[str, List[SubsidiaryEntry]] = {
    # Vedanta — parent LEI 335800Q1AJZ7Y6V25S25
    "335800Q1AJZ7Y6V25S25": [
        SubsidiaryEntry("335800Q1AJZ7Y6V25S25", "335800B0K5FOIDA1KH26", "Hindustan Zinc Limited", "IND", "direct", "mining"),
        SubsidiaryEntry("335800Q1AJZ7Y6V25S25", None, "Bharat Aluminium Company (BALCO)", "IND", "direct", "aluminum"),
        SubsidiaryEntry("335800Q1AJZ7Y6V25S25", None, "Sterlite Copper", "IND", "direct", "metals"),
        SubsidiaryEntry("335800Q1AJZ7Y6V25S25", None, "Cairn India", "IND", "direct", "oil_and_gas"),
        SubsidiaryEntry("335800Q1AJZ7Y6V25S25", None, "Talwandi Sabo Power", "IND", "direct", "power"),
        SubsidiaryEntry("335800Q1AJZ7Y6V25S25", None, "Vedanta Aluminium", "IND", "direct", "aluminum"),
        SubsidiaryEntry("335800Q1AJZ7Y6V25S25", None, "Vedanta Iron Ore Goa", "IND", "direct", "mining"),
        SubsidiaryEntry("335800Q1AJZ7Y6V25S25", None, "Konkola Copper Mines", "ZMB", "direct", "metals"),
    ],
    # Reliance Industries
    "335800F2WCKW00BAUE36": [
        SubsidiaryEntry("335800F2WCKW00BAUE36", None, "Reliance Jio Infocomm", "IND", "direct", "telecommunications"),
        SubsidiaryEntry("335800F2WCKW00BAUE36", None, "Reliance Retail Ventures", "IND", "direct", "retail"),
        SubsidiaryEntry("335800F2WCKW00BAUE36", None, "Reliance Industrial Investments", "IND", "direct", "chemicals"),
        SubsidiaryEntry("335800F2WCKW00BAUE36", None, "Sibur Holding (JV)", "RUS", "direct", "petrochemicals"),
        SubsidiaryEntry("335800F2WCKW00BAUE36", None, "Reliance Brands", "IND", "direct", "retail"),
        SubsidiaryEntry("335800F2WCKW00BAUE36", None, "Reliance Power", "IND", "direct", "power"),
        SubsidiaryEntry("335800F2WCKW00BAUE36", None, "Reliance Petroleum Retail", "IND", "direct", "oil_and_gas_refining"),
    ],
    # JPMorgan Chase
    "8I5DZWZKVSZI1NUHU748": [
        SubsidiaryEntry("8I5DZWZKVSZI1NUHU748", None, "JPMorgan Chase Bank, N.A.", "USA", "direct", "financial_services"),
        SubsidiaryEntry("8I5DZWZKVSZI1NUHU748", None, "J.P. Morgan Securities LLC", "USA", "direct", "financial_services"),
        SubsidiaryEntry("8I5DZWZKVSZI1NUHU748", None, "Chase Bank USA, N.A.", "USA", "direct", "financial_services"),
        SubsidiaryEntry("8I5DZWZKVSZI1NUHU748", None, "JPMorgan Asset Management", "USA", "direct", "asset_management"),
        SubsidiaryEntry("8I5DZWZKVSZI1NUHU748", None, "JPMorgan Chase Commercial Mortgage Securities Corp.", "USA", "direct", "real_estate"),
    ],
    # BP plc
    "213800LBQA1Y9L22JB70": [
        SubsidiaryEntry("213800LBQA1Y9L22JB70", None, "BP America Inc.", "USA", "direct", "oil_and_gas_refining"),
        SubsidiaryEntry("213800LBQA1Y9L22JB70", None, "BP Exploration Operating Company", "GBR", "direct", "oil_and_gas_production"),
        SubsidiaryEntry("213800LBQA1Y9L22JB70", None, "BP Castrol", "GBR", "direct", "chemicals"),
        SubsidiaryEntry("213800LBQA1Y9L22JB70", None, "BP Pulse (EV charging)", "GBR", "direct", "automotive"),
    ],
    # Shell plc
    "21380068P1DRHMJ8KU70": [
        SubsidiaryEntry("21380068P1DRHMJ8KU70", None, "Shell USA Inc.", "USA", "direct", "oil_and_gas_refining"),
        SubsidiaryEntry("21380068P1DRHMJ8KU70", None, "Shell Energy Europe", "GBR", "direct", "oil_and_gas_refining"),
        SubsidiaryEntry("21380068P1DRHMJ8KU70", None, "Shell Pennzoil-Quaker State", "USA", "direct", "chemicals"),
    ],
    # Volkswagen AG
    "529900NNUPAGGOMPXZ31": [
        SubsidiaryEntry("529900NNUPAGGOMPXZ31", None, "Audi AG", "DEU", "direct", "automotive"),
        SubsidiaryEntry("529900NNUPAGGOMPXZ31", None, "Porsche AG", "DEU", "direct", "automotive"),
        SubsidiaryEntry("529900NNUPAGGOMPXZ31", None, "MAN Truck & Bus", "DEU", "direct", "automotive"),
        SubsidiaryEntry("529900NNUPAGGOMPXZ31", None, "Scania CV", "SWE", "direct", "automotive"),
        SubsidiaryEntry("529900NNUPAGGOMPXZ31", None, "Bentley Motors", "GBR", "direct", "automotive"),
        SubsidiaryEntry("529900NNUPAGGOMPXZ31", None, "Lamborghini", "ITA", "direct", "automotive"),
    ],
    # ExxonMobil
    "J3WHBG0MTS7O8ZVMDC91": [
        SubsidiaryEntry("J3WHBG0MTS7O8ZVMDC91", None, "ExxonMobil Refining & Supply", "USA", "direct", "oil_and_gas_refining"),
        SubsidiaryEntry("J3WHBG0MTS7O8ZVMDC91", None, "ExxonMobil Chemical Company", "USA", "direct", "petrochemicals"),
        SubsidiaryEntry("J3WHBG0MTS7O8ZVMDC91", None, "Esso UK", "GBR", "direct", "oil_and_gas_refining"),
        SubsidiaryEntry("J3WHBG0MTS7O8ZVMDC91", None, "Imperial Oil (subsidiary)", "CAN", "direct", "oil_and_gas_production"),
    ],
    # Tata Steel
    "3358003RHJBL6V8O7Y17": [
        SubsidiaryEntry("3358003RHJBL6V8O7Y17", None, "Tata Steel Europe", "GBR", "direct", "iron_and_steel"),
        SubsidiaryEntry("3358003RHJBL6V8O7Y17", None, "Tata Steel Netherlands", "NLD", "direct", "iron_and_steel"),
        SubsidiaryEntry("3358003RHJBL6V8O7Y17", None, "Tata Steel BSL (formerly Bhushan Steel)", "IND", "direct", "iron_and_steel"),
        SubsidiaryEntry("3358003RHJBL6V8O7Y17", None, "Tata Steel Long Products", "IND", "direct", "iron_and_steel"),
        SubsidiaryEntry("3358003RHJBL6V8O7Y17", None, "T S Global Holdings Pte", "SGP", "direct", "iron_and_steel"),
    ],
    # Adani Enterprises
    "335800F0YK0Y3HBKHV33": [
        SubsidiaryEntry("335800F0YK0Y3HBKHV33", None, "Adani Power Ltd", "IND", "direct", "power"),
        SubsidiaryEntry("335800F0YK0Y3HBKHV33", None, "Adani Green Energy", "IND", "direct", "power"),
        SubsidiaryEntry("335800F0YK0Y3HBKHV33", None, "Adani Ports and SEZ", "IND", "direct", "shipping"),
        SubsidiaryEntry("335800F0YK0Y3HBKHV33", None, "Adani Total Gas", "IND", "direct", "oil_and_gas"),
        SubsidiaryEntry("335800F0YK0Y3HBKHV33", None, "Adani Wilmar", "IND", "direct", "agriculture"),
    ],
    # ArcelorMittal SA
    "N7GHA2Y4QJ6Y7Y0PA240": [
        SubsidiaryEntry("N7GHA2Y4QJ6Y7Y0PA240", None, "ArcelorMittal Nippon Steel India", "IND", "direct", "iron_and_steel"),
        SubsidiaryEntry("N7GHA2Y4QJ6Y7Y0PA240", None, "ArcelorMittal Europe", "FRA", "direct", "iron_and_steel"),
        SubsidiaryEntry("N7GHA2Y4QJ6Y7Y0PA240", None, "ArcelorMittal Brazil", "BRA", "direct", "iron_and_steel"),
        SubsidiaryEntry("N7GHA2Y4QJ6Y7Y0PA240", None, "ArcelorMittal South Africa", "ZAF", "direct", "iron_and_steel"),
    ],
}


def subsidiaries_of(parent_lei: Optional[str]) -> List[SubsidiaryEntry]:
    """Return curated direct + intermediate subsidiaries for `parent_lei`."""
    if not parent_lei:
        return []
    return list(_PARENT_SUBSIDIARIES.get(parent_lei, []))


def parent_of(subsidiary_lei: str) -> Optional[str]:
    """Reverse lookup: parent LEI given a subsidiary LEI. None if not in map."""
    if not subsidiary_lei:
        return None
    for parent, subs in _PARENT_SUBSIDIARIES.items():
        for s in subs:
            if s.subsidiary_lei == subsidiary_lei:
                return parent
    return None


def known_parent_count() -> int:
    return len(_PARENT_SUBSIDIARIES)
