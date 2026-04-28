"""
Carbon Extractor Agent - Scope 1, 2, 3 Emissions Analysis
Enterprise-grade carbon accounting aligned with GHG Protocol and SEBI BRSR

Extracts and validates:
- Scope 1: Direct emissions (owned/controlled sources)
- Scope 2: Indirect emissions from purchased energy
- Scope 3: Value chain emissions (15 categories)

Supports: Global companies + Indian enterprises (SEBI BRSR, MCA compliance)
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from core.llm_call import call_llm
from config.agent_prompts import CARBON_EXTRACTION_PROMPT
import asyncio


UNIT_MULTIPLIERS = {
    "billion tonnes": 1_000_000_000,
    "billion tons": 1_000_000_000,
    "billion tco2e": 1_000_000_000,
    "bn tco2e": 1_000_000_000,
    "gt co2e": 1_000_000_000,
    "million tonnes": 1_000_000,
    "million tons": 1_000_000,
    "million metric tons": 1_000_000,
    "million tco2e": 1_000_000,
    "mtco2e": 1_000_000,
    "mt co2e": 1_000_000,
    "mmt": 1_000_000,
    "thousand tonnes": 1_000,
    "thousand metric tons": 1_000,
    "ktco2e": 1_000,
    "kt co2e": 1_000,
    "000 tonnes": 1_000,
    "000 tco2e": 1_000,
    "tonnes co2e": 1,
    "tco2e": 1,
    "t co2e": 1,
    "metric tons co2e": 1,
}

SCOPE3_INDUSTRY_MINIMUMS = {
    "banking": 1_000_000,
    "financial services": 1_000_000,
    "energy": 100_000_000,
    "oil and gas": 100_000_000,
    "consumer goods": 10_000_000,
    "fmcg": 10_000_000,
    "retail": 10_000_000,
    "automotive": 1_000_000,
    "technology": 1_000_000,
    "healthcare": 1_000_000,
    "manufacturing": 10_000_000,
    "utilities": 50_000_000,
    "general": 100_000,
}

SCOPE1_INDUSTRY_MINIMUMS = {
    "banking": 10_000,
    "financial services": 10_000,
    "energy": 1_000_000,
    "oil and gas": 1_000_000,
    "consumer goods": 100_000,
    "fmcg": 100_000,
    "technology": 10_000,
    "general": 1_000,
}

SCOPE1_ALIASES = [
    "operations emissions",
    "operational emissions",
    "direct operations",
    "factory emissions",
    "manufacturing emissions",
]

SCOPE3_ALIASES = [
    "value chain",
    "brand footprint",
    "consumer use",
    "raw materials",
    "ingredients",
    "packaging emissions",
    "end of life",
    "upstream emissions",
    "downstream emissions",
]


def backfill_from_total(emissions: dict) -> dict:
    """
    When scope1/scope2 individual values are null but a combined
    scope1+2 total exists, backfill scope1 with the combined figure.

    This preserves found data rather than discarding it.
    Scope2 is left null to avoid double-counting.
    The combined flag tells downstream readers what happened.
    """
    if not isinstance(emissions, dict):
        return emissions

    scope1_val = (emissions.get("scope1") or {}).get("value")
    scope2_val = (emissions.get("scope2") or {}).get("value")
    total_dict = emissions.get("total") or {}
    combined = (
        total_dict.get("scope1_2")
        or total_dict.get("all_scopes")
        or total_dict.get("scope1_scope2")
    )

    # Only backfill when: combined exists AND both scope1/2 are null
    if combined and scope1_val is None and scope2_val is None:

        # Ensure scope1/scope2 dicts exist before writing to them
        if not isinstance(emissions.get("scope1"), dict):
            emissions["scope1"] = {}
        if not isinstance(emissions.get("scope2"), dict):
            emissions["scope2"] = {}

        emissions["scope1"]["value"] = combined
        emissions["scope1"]["source"] = (
            f"Scope 1+2 combined figure ({combined:,.0f} tCO2e). "
            "Could not separate individual scopes from source."
        )
        emissions["scope1"]["combined_scope1_2"] = True
        emissions["scope1"]["year"] = (
            (emissions.get("scope1") or {}).get("year")
            or total_dict.get("year")
        )

        # Scope 2 marked as included to avoid double-counting
        emissions["scope2"]["value"] = None
        emissions["scope2"]["source"] = (
            "Included in Scope 1 combined figure. "
            "See scope1 for combined Scope 1+2 total."
        )
        emissions["scope2"]["combined_with_scope1"] = True

    return emissions


class CarbonExtractor:
    """
    Scope 1-3 Carbon Emissions Extractor
    Aligned with GHG Protocol, CDP, TCFD, SEBI BRSR (India)
    """

    def __init__(self):
        self.name = "Carbon Emissions Extraction Specialist"

        # Industry-level emissions baselines (order-of-magnitude only) used when disclosures are missing.
        # Purpose: prevent downstream "score collapse" due to missing data while clearly flagging low confidence.
        # Units: tCO2e (annual, indicative typical large-cap ranges).
        self.industry_emissions_baselines = {
            "oil_and_gas": {"scope1": 25_000_000, "scope2": 3_000_000, "scope3": 250_000_000},
            "coal": {"scope1": 60_000_000, "scope2": 5_000_000, "scope3": 300_000_000},
            "mining": {"scope1": 10_000_000, "scope2": 2_000_000, "scope3": 30_000_000},
            "aviation": {"scope1": 8_000_000, "scope2": 200_000, "scope3": 0},
            "chemicals": {"scope1": 5_000_000, "scope2": 1_000_000, "scope3": 15_000_000},
            "cement": {"scope1": 20_000_000, "scope2": 2_000_000, "scope3": 6_000_000},
            "steel": {"scope1": 30_000_000, "scope2": 6_000_000, "scope3": 12_000_000},
            "banking": {"scope1": 12_000, "scope2": 180_000, "scope3": 35_000_000},  # financed emissions dominated
            "consumer_goods": {"scope1": 60_000, "scope2": 120_000, "scope3": 10_000_000},
            "technology": {"scope1": 25_000, "scope2": 250_000, "scope3": 2_500_000},
            "unknown": {"scope1": 100_000, "scope2": 300_000, "scope3": 5_000_000},
        }

        # ────────────────────────────────────────────────────────────────
        # The previous in-memory "known emissions" database — a hardcoded
        # dict of scope 1/2/3 figures keyed by company name — has been
        # removed. It silently overrode real extraction with stale 2023/2024
        # values stamped "BRSR Filing / CDP Disclosure", producing reports
        # that looked verified but were not. Carbon figures must now come
        # from parsed disclosures, deterministic regex passes, the LLM
        # extractor, or the explicit industry-baseline fallback (which is
        # transparently labelled "Estimated industry baseline").
        # ────────────────────────────────────────────────────────────────
        self.known_emissions: Dict[str, Dict[str, Any]] = {}
        # GHG Protocol Scope 3 Categories
        self.scope3_categories = {
            1: "Purchased goods and services",
            2: "Capital goods",
            3: "Fuel and energy-related activities",
            4: "Upstream transportation and distribution",
            5: "Waste generated in operations",
            6: "Business travel",
            7: "Employee commuting",
            8: "Upstream leased assets",
            9: "Downstream transportation and distribution",
            10: "Processing of sold products",
            11: "Use of sold products",
            12: "End-of-life treatment of sold products",
            13: "Downstream leased assets",
            14: "Franchises",
            15: "Investments"
        }

        self.scope3_keywords = {
            1: ["purchased goods", "supply chain", "vendor emissions", "procurement emissions"],
            2: ["capital goods", "machinery", "equipment", "construction", "capital assets"],
            3: ["fuel-and-energy", "transmission and distribution", "t&d losses", "well-to-tank"],
            4: ["upstream transport", "inbound logistics", "tier 1 transport", "upstream distribution"],
            5: ["waste generated", "landfill", "composting", "incineration", "recycling disposal"],
            6: ["business travel", "air travel", "hotel stays", "employee travel", "corporate flights"],
            7: ["employee commuting", "commuting", "teleworking", "work-from-home", "wfh emissions"],
            8: ["upstream leased", "leased office", "leased building", "leased asset"],
            9: ["downstream transport", "outbound logistics", "last mile", "downstream distribution"],
            10: ["processing of sold", "intermediate products", "processing emissions"],
            11: ["use of sold products", "electricity during use", "fuel during use", "product energy consumption"],
            12: ["end-of-life", "product disposal", "recycling of products", "product end of life"],
            13: ["downstream leased", "assets leased to others", "lessor emissions"],
            14: ["franchise", "operation of franchises"],
            15: ["investment", "financed emissions", "portfolio emissions", "mortgages and loans"]
        }

        # Emission factors for validation (tCO2e)
        self.emission_benchmarks = {
            "energy": {"coal_power": 0.91, "natural_gas": 0.41, "solar": 0.041, "wind": 0.011},
            "transport": {"diesel_truck": 0.089, "electric_vehicle": 0.020, "aviation": 0.255},
            "industry": {"steel": 1.85, "cement": 0.62, "aluminum": 11.5, "chemicals": 2.5}
        }

        # Global grid emission factors by country (tCO2/MWh - IEA 2024)
        self.grid_emission_factors = {
            # Asia
            "india": 0.71, "china": 0.58, "japan": 0.47, "south_korea": 0.42,
            "indonesia": 0.72, "vietnam": 0.52, "thailand": 0.49, "malaysia": 0.61,
            # Europe
            "germany": 0.35, "uk": 0.21, "france": 0.06, "spain": 0.22,
            "italy": 0.33, "poland": 0.74, "netherlands": 0.37, "sweden": 0.01,
            # Americas
            "usa": 0.37, "canada": 0.13, "brazil": 0.08, "mexico": 0.43,
            # Others
            "australia": 0.66, "south_africa": 0.90, "uae": 0.42, "russia": 0.35,
            # Default
            "global_average": 0.44
        }

        # Indian-specific emission factors (CEA Grid Emission Factor)
        self.india_grid_emission_factor = 0.71  # tCO2/MWh (India 2025)
        self.india_brsr_categories = [
            "Scope 1 emissions",
            "Scope 2 emissions",
            "Total energy consumed from renewable sources",
            "Total energy consumed from non-renewable sources",
            "Water withdrawn",
            "Water recycled",
            "Waste generated"
        ]

    def extract_carbon_data(self, company: str, evidence: List[Dict[str, Any]],
                           claim: Dict[str, Any] = None,
                           report_chunks: Optional[List[Dict[str, Any]]] = None,
                           report_claims_by_year: Optional[Dict[Any, List[str]]] = None,
                           report_files: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Extract comprehensive carbon emissions data from evidence

        Args:
            company: Company name
            evidence: List of evidence documents from EvidenceRetriever
            claim: Optional ESG claim being analyzed
            report_chunks: Parsed ESG report chunks
            report_claims_by_year: Extracted report claims grouped by year

        Returns:
            Structured carbon data with Scope 1, 2, 3 breakdown
        """

        print(f"\n{'='*60}")
        print(f"♻️  AGENT: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        print(f"Evidence documents: {len(evidence)}")
        print(f"Report chunks: {len(report_chunks or [])}")
        print(f"Report files: {len(report_files or [])}")
        print(f"Report claim years: {len((report_claims_by_year or {}).keys())}")

        if not report_chunks and isinstance(claim, dict):
            report_chunks = claim.get("parsed_report_chunks") or claim.get("report_chunks") or []

        # Build prioritized extraction corpus (reports -> report claims -> evidence)
        extraction_text, source_meta = self._build_extraction_corpus(
            evidence=evidence,
            report_chunks=report_chunks or [],
            report_claims_by_year=report_claims_by_year or {}
        )

        industry_hint = self._derive_industry_hint(company, extraction_text, claim)
        chunk_texts = []
        for chunk in report_chunks or []:
            if isinstance(chunk, dict):
                chunk_text = chunk.get("page_content") or chunk.get("text")
                if chunk_text:
                    chunk_texts.append(str(chunk_text))
        for ev in evidence or []:
            if isinstance(ev, dict):
                snippet = ev.get("snippet") or ev.get("relevant_text") or ev.get("content")
                if snippet:
                    chunk_texts.append(str(snippet))

        deterministic_scope1 = self._extract_scope_emissions_from_chunks(chunk_texts, 1, industry_hint)
        deterministic_scope2 = self._extract_scope_emissions_from_chunks(chunk_texts, 2, industry_hint)
        deterministic_scope3 = self._extract_scope_emissions_from_chunks(chunk_texts, 3, industry_hint)
        deterministic_scope12 = self._extract_scope12_combined(chunk_texts, industry_hint)
        table_extracted = self._extract_from_report_files(report_files or [])

        # Camelot picks the FIRST scope match in a table, which is often a
        # sub-total row (e.g., "Scope 1 stationary combustion = 979" instead
        # of the consolidated "Scope 1 GHG Emissions = 115,294" further down).
        # Only let camelot OVERRIDE the chunk-regex extractor when its value
        # is at least as large as what we already found (or when the regex
        # extractor returned nothing). This prevents a small sub-total from
        # silently shadowing the real consolidated number.
        industry_threshold_key = self._normalize_industry_for_threshold(industry_hint)

        def _camelot_should_override(scope_num: int, camelot_val, current_val) -> bool:
            if camelot_val is None:
                return False
            # Always reject camelot values that fail the industry magnitude floor —
            # otherwise a 979 sub-total wins by virtue of being non-None.
            validated = self._validate_emission_magnitude(
                camelot_val, scope_num, industry_threshold_key, "company"
            )
            if validated is None:
                return False
            # Override when we have nothing yet, or when camelot is bigger
            # (more likely to be the consolidated/total figure).
            if current_val is None:
                return True
            try:
                return float(camelot_val) >= float(current_val)
            except (TypeError, ValueError):
                return False

        if _camelot_should_override(1, table_extracted.get("scope1"), deterministic_scope1.get("value")):
            deterministic_scope1 = {
                "value": table_extracted.get("scope1"),
                "year": table_extracted.get("year"),
                "source": table_extracted.get("source"),
                "confidence": "high",
                "candidates_found": table_extracted.get("tables_found", 0),
            }
        if _camelot_should_override(2, table_extracted.get("scope2"), deterministic_scope2.get("value")):
            deterministic_scope2 = {
                "value": table_extracted.get("scope2"),
                "year": table_extracted.get("year"),
                "source": table_extracted.get("source"),
                "confidence": "high",
                "candidates_found": table_extracted.get("tables_found", 0),
            }
        if _camelot_should_override(3, table_extracted.get("scope3"), deterministic_scope3.get("value")):
            deterministic_scope3 = {
                "value": table_extracted.get("scope3"),
                "year": table_extracted.get("year"),
                "source": table_extracted.get("source"),
                "confidence": "high",
                "candidates_found": table_extracted.get("tables_found", 0),
            }

        if deterministic_scope1.get("value") is None and deterministic_scope12.get("scope1") is not None:
            deterministic_scope1 = {
                "value": deterministic_scope12.get("scope1"),
                "year": deterministic_scope12.get("year"),
                "source": deterministic_scope12.get("source"),
                "confidence": deterministic_scope12.get("confidence", "medium"),
                "candidates_found": deterministic_scope12.get("candidates_found", 0),
            }
        if deterministic_scope2.get("value") is None and deterministic_scope12.get("scope2") is not None:
            deterministic_scope2 = {
                "value": deterministic_scope12.get("scope2"),
                "year": deterministic_scope12.get("year"),
                "source": deterministic_scope12.get("source"),
                "confidence": deterministic_scope12.get("confidence", "medium"),
                "candidates_found": deterministic_scope12.get("candidates_found", 0),
            }

        # The hardcoded "known emissions" lookup has been removed; carbon
        # figures must come from extracted disclosures every run.
        known_data = None

        extracted_data = {}

        # Extract via LLM / regex over the assembled disclosure corpus.
        print("📊 Extracting carbon emissions data via LLM/Regex...")
        extracted_data = self._llm_extract_carbon(company, extraction_text, claim)
        if not extracted_data:
            extracted_data = self._regex_extract_carbon(extraction_text)

        # Deterministic scope extraction has priority when available.
        if deterministic_scope1.get("value") is not None:
            extracted_data["scope1"] = {
                "value": deterministic_scope1.get("value"),
                "unit": "tCO2e",
                "year": deterministic_scope1.get("year"),
                "source": deterministic_scope1.get("source") or "PDF extraction",
                "confidence": deterministic_scope1.get("confidence", "medium"),
            }
        if deterministic_scope2.get("value") is not None:
            extracted_data["scope2"] = {
                "value": deterministic_scope2.get("value"),
                "unit": "tCO2e",
                "year": deterministic_scope2.get("year"),
                "source": deterministic_scope2.get("source") or "PDF extraction",
                "confidence": deterministic_scope2.get("confidence", "medium"),
            }
        if deterministic_scope3.get("value") is not None:
            extracted_data["scope3"] = {
                "total": deterministic_scope3.get("value"),
                "unit": "tCO2e",
                "year": deterministic_scope3.get("year"),
                "source": deterministic_scope3.get("source") or "PDF extraction",
                "confidence": deterministic_scope3.get("confidence", "medium"),
            }

        # Extract Scope 3 category presence from report/evidence text.
        scope3_categories = self._extract_scope3_category_presence(extraction_text)
        if scope3_categories:
            extracted_data.setdefault("scope3", {})
            existing_categories = extracted_data["scope3"].get("categories")
            if not isinstance(existing_categories, dict):
                existing_categories = {}
            existing_categories.update(scope3_categories)
            extracted_data["scope3"]["categories"] = existing_categories

        # If CDP disclosure is present and Scope 3 is disclosed, assume category coverage is available.
        if (
            isinstance(extracted_data.get("scope3"), dict)
            and not extracted_data["scope3"].get("categories")
            and extracted_data["scope3"].get("total") is not None
            and "cdp" in extraction_text.lower()
            and ("scope 3" in extraction_text.lower() or "value chain" in extraction_text.lower())
        ):
            extracted_data["scope3"]["categories"] = {
                str(k): "reported_via_cdp_disclosure" for k in self.scope3_categories.keys()
            }

        # Pull water and waste disclosures so BRSR/ESG environmental checks have structured inputs.
        ww = self._extract_water_waste_disclosures(extraction_text)
        if ww.get("water_usage"):
            extracted_data["water_usage"] = ww["water_usage"]
        if ww.get("waste_data"):
            extracted_data["waste_data"] = ww["waste_data"]

        # Helper to check if scope has actual data
        def has_emission_value(scope_data):
            if not scope_data or not isinstance(scope_data, dict):
                return False
            return scope_data.get("value") is not None or scope_data.get("total") is not None

        # Step 1.5: If still no data, try CDP public fallback
        llm_has_data = has_emission_value(extracted_data.get("scope1")) or has_emission_value(extracted_data.get("scope2"))

        if not llm_has_data and not known_data:
            cdp_fallback = self._fetch_cdp_carbon_data(company)
            if cdp_fallback:
                print("📊 Using CDP public-data fallback...")
                extracted_data.update(cdp_fallback)

        # Step 1.9: Confidence-aware fallback when emissions are missing
        # If we still have no usable scope values, estimate an industry baseline rather than returning an empty/zero set.
        llm_has_data = has_emission_value(extracted_data.get("scope1")) or has_emission_value(extracted_data.get("scope2")) or has_emission_value(extracted_data.get("scope3"))
        used_baseline_estimate = False
        baseline_industry = "unknown"
        if not llm_has_data:
            baseline_industry = self._derive_industry_hint(company, extraction_text, claim)
            baseline = self.industry_emissions_baselines.get(baseline_industry, self.industry_emissions_baselines["unknown"])
            extracted_data = {
                "scope1": {"value": baseline["scope1"], "unit": "tCO2e", "year": None, "source": f"Industry baseline estimate ({baseline_industry})"},
                "scope2": {"value": baseline["scope2"], "unit": "tCO2e", "year": None, "source": f"Industry baseline estimate ({baseline_industry})"},
                "scope3": {"total": baseline["scope3"], "unit": "tCO2e", "year": None, "source": f"Industry baseline estimate ({baseline_industry})"},
                "data_source": "Estimated industry baseline (no disclosed scope data in sources)"
            }
            used_baseline_estimate = True

        # Per-scope fallback — when only some scopes are missing (e.g. JPM
        # discloses scope1+scope3 but omits scope2), fill the gap from
        # industry baselines so carbon-pathway analysis can run cleanly.
        # Each filled scope is tagged "Estimated — disclosure gap" so the
        # report flags it as inferred, not disclosed.
        if not used_baseline_estimate:
            _baseline_industry = self._derive_industry_hint(company, extraction_text, claim)
            _baseline = self.industry_emissions_baselines.get(
                _baseline_industry, self.industry_emissions_baselines["unknown"]
            )
            for _scope_key, _value_field in (("scope1", "value"), ("scope2", "value"), ("scope3", "total")):
                _scope_data = extracted_data.get(_scope_key)
                if (
                    _scope_data is None
                    or not isinstance(_scope_data, dict)
                    or _scope_data.get(_value_field) in (None, "", 0)
                ) and not (
                    isinstance(_scope_data, dict) and _scope_data.get("combined_with_scope1")
                ):
                    extracted_data[_scope_key] = {
                        _value_field: _baseline.get(_scope_key),
                        "unit": "tCO2e",
                        "year": None,
                        "source": f"Estimated — disclosure gap (industry baseline: {_baseline_industry})",
                        "confidence": "low",
                        "estimated_from_baseline": True,
                    }

        # Step 2: Validate and normalize units
        print("🔍 Validating emission figures...")
        validated_data = self._validate_emissions(extracted_data, company)
        if extracted_data.get("water_usage"):
            validated_data["water_usage"] = extracted_data.get("water_usage")
        if extracted_data.get("waste_data"):
            validated_data["waste_data"] = extracted_data.get("waste_data")

        # Magnitude validation to reject parser artifacts (return None, never zero).
        industry_state = self._normalize_industry_for_threshold(industry_hint)
        scope1_value = self._validate_emission_magnitude(
            (validated_data.get("scope1") or {}).get("value"), 1, industry_state, company
        )
        scope2_value = self._validate_emission_magnitude(
            (validated_data.get("scope2") or {}).get("value"), 2, industry_state, company
        )
        scope3_value = self._validate_emission_magnitude(
            (validated_data.get("scope3") or {}).get("total") or (validated_data.get("scope3") or {}).get("value"),
            3,
            industry_state,
            company,
        )
        if "scope1" not in validated_data:
            validated_data["scope1"] = {}
        if "scope2" not in validated_data:
            validated_data["scope2"] = {}
        if "scope3" not in validated_data:
            validated_data["scope3"] = {}
        validated_data["scope1"]["value"] = scope1_value
        validated_data["scope2"]["value"] = scope2_value
        validated_data["scope3"]["total"] = scope3_value
        scope3_categories = (
            extracted_data.get("scope3", {}).get("categories")
            if isinstance(extracted_data.get("scope3"), dict)
            else None
        )
        if isinstance(scope3_categories, dict) and scope3_categories:
            validated_data["scope3"]["categories"] = scope3_categories

        # Step 3: Calculate carbon intensity metrics
        print("📈 Calculating carbon intensity...")
        intensity_metrics = self._calculate_intensity(validated_data, company)

        # Step 4: Check GHG Protocol compliance
        print("✅ Checking GHG Protocol compliance...")
        compliance_check = self._check_ghg_compliance(validated_data)

        # Step 5: Indian BRSR compliance (if applicable)
        print("🇮🇳 Checking SEBI BRSR compliance...")
        brsr_compliance = self._check_brsr_compliance(validated_data, company)

        # Step 6: Offset transparency audit (avoidance vs removal)
        print("🧾 Auditing carbon offset transparency...")
        offset_transparency = self._audit_offset_transparency(extraction_text, validated_data)

        # Pull additional metadata from whatever extraction surfaced in the
        # current run — net-zero target, renewables %, SBTi flag, verification
        # status, and the actual disclosure source. Nothing here is allowed to
        # come from a hardcoded company table; only fields that real
        # extraction populated will appear in the final report.
        additional_info: Dict[str, Any] = {}
        for key, source_keys in (
            ("net_zero_target", ("net_zero_target", "reduction_target")),
            ("renewable_energy_percentage", ("renewable_energy",)),
            ("science_based_target", ("science_based_target",)),
            ("verification_status", ("verification_status", "verification")),
            ("data_source", ("data_source",)),
        ):
            for sk in source_keys:
                value = extracted_data.get(sk)
                if value not in (None, "", []):
                    additional_info[key] = value
                    break

        # SBTi registry fallback for target-validation confirmation.
        if additional_info.get("science_based_target") is None:
            sbti_registry = self._fetch_sbti_registry_status(company)
            if isinstance(sbti_registry, dict):
                if sbti_registry.get("science_based_target") is not None:
                    additional_info["science_based_target"] = sbti_registry.get("science_based_target")
                if sbti_registry.get("sbti_status"):
                    additional_info["sbti_status"] = sbti_registry.get("sbti_status")
                if sbti_registry.get("sbti_source"):
                    additional_info["sbti_source"] = sbti_registry.get("sbti_source")

        claim_text = ""
        if isinstance(claim, dict):
            claim_text = claim.get("claim_text", "")
        elif isinstance(claim, str):
            claim_text = claim

        inferred_net_zero = self.extract_net_zero_year_from_claim(claim_text)

        emissions_dict = {
            "scope1": validated_data.get("scope1", {}),
            "scope2": validated_data.get("scope2", {}),
            "scope3": validated_data.get("scope3", {}),
            "total": self._calculate_total(validated_data)
        }

        # Backfill scope1/2 from combined total if individual values are null.
        emissions_dict = backfill_from_total(emissions_dict)

        # If backfill populated scope1, treat extraction as successful.
        scope1_after = (emissions_dict.get("scope1") or {}).get("value")
        scope3_after = (emissions_dict.get("scope3") or {}).get("total")
        extraction_successful = (
            not used_baseline_estimate and
            (scope1_after is not None or scope3_after is not None)
        )

        result = {
            "company": company,
            # Baseline estimates are useful for stability but are not treated as a successful extraction.
            "extraction_successful": extraction_successful,
            "used_baseline_estimate": used_baseline_estimate,
            "baseline_industry": baseline_industry if used_baseline_estimate else None,
            "emissions": emissions_dict,
            "intensity_metrics": intensity_metrics,
            "ghg_compliance": compliance_check,
            "brsr_compliance": brsr_compliance,
            "offset_transparency": offset_transparency,
            "data_quality": self._assess_data_quality(validated_data),
            "carbon_claims_analysis": self._analyze_carbon_claims(claim, validated_data),
            "red_flags": self._detect_carbon_red_flags(validated_data, extraction_text),
            "annual_emissions": self._extract_annual_emissions(extraction_text),
            "source_coverage": source_meta,
            "table_extraction": table_extracted,
            "water_usage": extracted_data.get("water_usage"),
            "waste_data": extracted_data.get("waste_data"),
            **additional_info  # Include net zero target, renewable %, etc.
        }

        scope1_val = (result.get("emissions", {}).get("scope1", {}) or {}).get("value")
        scope2_val = (result.get("emissions", {}).get("scope2", {}) or {}).get("value")
        scope3_val = (
            (result.get("emissions", {}).get("scope3", {}) or {}).get("total")
            or (result.get("emissions", {}).get("scope3", {}) or {}).get("value")
        )
        try:
            s1 = float(scope1_val or 0)
            s2 = float(scope2_val or 0)
            s3 = float(scope3_val or 0)
            total = s1 + s2 + s3
            result["scope3_share_pct"] = round((s3 / total) * 100, 1) if total > 0 else None
        except Exception:
            result["scope3_share_pct"] = None

        sbti_status_txt = str(result.get("sbti_status") or additional_info.get("sbti_status") or "").strip().lower()
        result.setdefault("flags", {})
        result["flags"]["sbti_not_submitted"] = sbti_status_txt == "not submitted"

        result["net_zero_target"] = (
            result.get("net_zero_target")
            or extracted_data.get("net_zero_target")
            or inferred_net_zero
            or "Not declared in available evidence"
        )

        result = self._audit_emissions_data(result)

        print(f"\n✅ Carbon extraction complete:")
        print(f"   Scope 1: {result['emissions']['scope1'].get('value', 'N/A')} tCO2e")
        print(f"   Scope 2: {result['emissions']['scope2'].get('value', 'N/A')} tCO2e")
        print(f"   Scope 3: {result['emissions']['scope3'].get('total', 'N/A')} tCO2e")
        print(f"   Data quality: {result['data_quality']['overall_score']}/100")
        if additional_info.get("net_zero_target"):
            print(f"   Net Zero Target: {additional_info['net_zero_target']}")
            print(f"   Data Source: {additional_info.get('data_source', 'Unknown')}")

        return result

    def extract_net_zero_year_from_claim(self, claim: str) -> Optional[str]:
        """Extract net-zero target year directly from the analyzed claim text."""
        if not claim:
            return None
        claim_lower = claim.lower()
        if "net-zero" in claim_lower or "net zero" in claim_lower:
            year_match = re.search(r"20[3-9][0-9]", claim)
            if year_match:
                return f"Net zero by {year_match.group(0)} (from claim)"
        return None

        return result

    def _audit_emissions_data(self, result: dict) -> dict:
        """Audits carbon emissions data for common interpretation errors based on GHG Protocol rules."""
        emissions = result.get("emissions", {})
        scope1 = emissions.get("scope1", {})
        scope2 = emissions.get("scope2", {})
        scope3 = emissions.get("scope3", {})
        
        flags = []
        notes = []
        
        s1_val = float(scope1.get("value") or 0)
        s2_val = float(scope2.get("value") or 0)
        s3_val = float(scope3.get("total") or scope3.get("value") or 0)
        
        # 1. Scope 2 Misclassification
        scope2_status = "FULL"
        s2_method = str(scope2.get("methodology", "")).lower()
        if not s2_method or ("market" in s2_method and "location" not in s2_method) or ("location" in s2_method and "market" not in s2_method):
            if s2_val > 0 or scope2.get("value") is not None:
                flags.append("Scope 2 improperly aggregated")
                notes.append("Scope 2 only reports one methodology (market or location), lacking the dual-reporting required by GHG Protocol.")
                scope2_status = "PARTIAL"
            elif scope2.get("value") is None:
                flags.append("May exist elsewhere in report")
                scope2_status = "ERROR"

        # 2. Scope 3 Misinterpretation
        scope3_status = "FULL"
        s3_cats = scope3.get("categories", {})
        if s3_val > 0:
            if isinstance(s3_cats, dict) and len(s3_cats) > 0 and len(s3_cats) < 5:
                if "15" in str(list(s3_cats.keys())):
                    flags.append("Scope 3 is partial, not total")
                    notes.append("Scope 3 relies heavily on financed emissions or selected categories.")
                    scope3_status = "PARTIAL"
        elif scope3.get("total") is None and scope3.get("value") is None:
            flags.append("May exist elsewhere in report")
            scope3_status = "ERROR"
            
        # 4. Missing Scope Check
        if scope1.get("value") is None:
            flags.append("May exist elsewhere in report")
            
        # 5. Sanity Check
        if s3_val > 0 and (s1_val + s2_val) > 0:
            if s3_val > (s1_val + s2_val) * 100:
                flags.append("Disproportionate Scope 3 likely partial")
                notes.append("Scope 3 is >100x larger than Scope 1+2; likely represents partial financed/use-phase emissions.")
                scope3_status = "PARTIAL"
                
        # 3. Invalid Total Emissions Calculation
        if scope3_status == "PARTIAL":
            flags.append("Invalid total due to incomplete Scope 3")
            emissions["total"] = None  # MUST NOT be calculated
            
        result["corrected_scope2_status"] = scope2_status
        result["corrected_scope3_status"] = scope3_status
        result["audit_error_flags"] = list(set(flags))
        result["audit_notes"] = " ".join(set(notes))
        
        emissions["scope2_status"] = scope2_status
        emissions["scope3_status"] = scope3_status
        
        return result

    def _extract_from_report_files(self, report_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run the Camelot table extractor over downloaded PDF reports when available."""
        result = {
            "scope1": None,
            "scope2": None,
            "scope3": None,
            "unit": None,
            "year": None,
            "tables_found": 0,
            "source": None,
            "report_path": None,
        }
        if not report_files:
            return result
        try:
            from core.extractors.pdf_table_extractor import extract_emissions_values
        except Exception:
            return result

        def _coverage_score(payload: Dict[str, Any]) -> Tuple[int, int]:
            scope_count = sum(1 for key in ("scope1", "scope2", "scope3") if payload.get(key) is not None)
            tables_found = int(payload.get("tables_found") or 0)
            return (scope_count, tables_found)

        best_payload: Optional[Dict[str, Any]] = None

        for report in report_files:
            local_path = str((report or {}).get("local_path") or "").strip()
            if not local_path or Path(local_path).suffix.lower() != ".pdf":
                continue
            try:
                payload = extract_emissions_values(local_path)
            except Exception:
                continue

            if _coverage_score(payload) > _coverage_score(best_payload or {}):
                best_payload = payload
                result["report_path"] = local_path

        if not best_payload:
            return result

        result.update({
            "scope1": best_payload.get("scope1"),
            "scope2": best_payload.get("scope2"),
            "scope3": best_payload.get("scope3"),
            "unit": best_payload.get("unit"),
            "year": best_payload.get("year"),
            "tables_found": best_payload.get("tables_found", 0),
            "source": best_payload.get("source"),
        })
        return result

    def _extract_emission_value_with_unit(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract emission values and normalize to tCO2e using unit multipliers."""
        text_lower = (text or "").lower()
        number_pattern = r"([\d,]+\.?\d*|\d*\.\d+)"

        for unit_str, multiplier in sorted(UNIT_MULTIPLIERS.items(), key=lambda x: x[1], reverse=True):
            pattern = number_pattern + r"\s*" + re.escape(unit_str)
            match = re.search(pattern, text_lower)
            if match:
                raw_num_str = match.group(1).replace(",", "")
                try:
                    raw_num = float(raw_num_str)
                    return raw_num * multiplier, match.group(0)
                except ValueError:
                    continue

        # Base fallback where only tCO2e-like token appears.
        match = re.search(number_pattern + r"\s*(tco2e|co2e)", text_lower)
        if match:
            try:
                return float(match.group(1).replace(",", "")), match.group(0)
            except ValueError:
                return None, None

        return None, None

    @staticmethod
    def _detect_chunk_unit_multiplier(chunk_text: str) -> float:
        """Return the dominant unit multiplier hinted at in the chunk header.

        Real ESG tables often write the unit once (in the column header or
        a footnote) and leave the row values bare. Without a chunk-level
        hint, the local-context unit detector misses every row in the table.

        Case sensitivity matters: JPMorgan and most US-listed banks write
        "mtCO2e" to mean "metric tonnes CO2e" (multiplier = 1), while
        oil & gas companies write "MtCO2e" to mean "megatonnes" (1e6).
        Lowercasing the chunk before unit lookup conflates the two and
        produces 1,000,000× errors. We therefore restrict the auto-multiplier
        to phrases that are unambiguous in either case ("million tonnes",
        "billion tonnes", "kilotonnes"/"thousand tonnes", "GtCO2e",
        "megatonnes") plus the case-preserving capital-M variants.
        """
        if not chunk_text:
            return 1.0

        unambiguous_lower = {
            "billion tonnes": 1_000_000_000,
            "billion tons": 1_000_000_000,
            "billion metric tons": 1_000_000_000,
            "gigatonnes": 1_000_000_000,
            "million tonnes": 1_000_000,
            "million tons": 1_000_000,
            "million metric tons": 1_000_000,
            "megatonnes": 1_000_000,
            "thousand tonnes": 1_000,
            "thousand metric tons": 1_000,
            "kilotonnes": 1_000,
        }
        chunk_lower = chunk_text.lower()
        for token, multiplier in sorted(unambiguous_lower.items(), key=lambda x: -x[1]):
            if token in chunk_lower:
                return float(multiplier)

        # Case-sensitive checks for ambiguous abbreviations: only treat as
        # multipliers when the capital letter is preserved.
        if re.search(r"\bGt\s*CO2?e?\b", chunk_text):
            return 1_000_000_000.0
        if re.search(r"\bMt\s*CO2?e?\b", chunk_text):
            return 1_000_000.0
        if re.search(r"\bkt\s*CO2?e?\b", chunk_text, re.IGNORECASE):
            # "ktCO2e" = kilotonnes; standard regardless of case.
            return 1_000.0
        return 1.0

    def _extract_scope_emissions_from_chunks(self, chunks: List[str], scope_number: int, industry_hint: str) -> Dict[str, Any]:
        """Extract Scope 1/2/3 emissions from chunk corpus with unit-aware parsing."""
        number_pattern = r"([\d,]+\.?\d*|\d*\.\d+)"
        high_precision_patterns = {
            1: [
                r"total\s+scope\s+1\s+emissions[^0-9]{0,20}([\d,]+(?:\.\d+)?)",
                r"\|\s*total\s+scope\s+1\s+emissions\s*\|[^|]*\|\s*([\d,]+(?:\.\d+)?)",
                # Common table-row form: "Scope 1   65,500   72,300" — pick
                # the first numeric column after the label. The intervening
                # `[^0-9\n]{0,40}` (no digits, no newlines) keeps us inside
                # one row and prevents capturing a totally unrelated number.
                r"\bscope\s*1\b(?:\s*\([^)]*\))?[^0-9\n]{0,40}([\d,]+(?:\.\d+)?)",
                # Prose form: "Scope 1 emissions in 2024 were 65,500"
                r"\bscope\s*1\b[\s\S]{0,80}?\bwere\s+([\d,]+(?:\.\d+)?)",
                r"\bscope\s*1\b[\s\S]{0,80}?\b(?:was|were|reached|stood at|totalled|totaled)\s+([\d,]+(?:\.\d+)?)",
            ],
            2: [
                r"\|\s*market\s+based\s*\|[^|]*\|\s*([\d,]+(?:\.\d+)?)",
                r"\|\s*location\s+based\s*\|[^|]*\|\s*([\d,]+(?:\.\d+)?)",
                r"scope\s+2[\s\S]{0,120}?market\s+based[^0-9]{0,20}([\d,]+(?:\.\d+)?)",
                r"scope\s+2[\s\S]{0,160}?location\s+based[^0-9]{0,20}([\d,]+(?:\.\d+)?)",
                r"\bscope\s*2\b(?:\s*\([^)]*\))?[^0-9\n]{0,40}([\d,]+(?:\.\d+)?)",
                r"\bscope\s*2\b[\s\S]{0,80}?\b(?:was|were|reached|stood at|totalled|totaled)\s+([\d,]+(?:\.\d+)?)",
            ],
            3: [
                r"total\s+scope\s+3\s+emission[s]?[^0-9]{0,20}([\d,]+(?:\.\d+)?)",
                r"\|\s*total\s+scope\s+3\s+emission[s]?\s*\|[^|]*\|\s*([\d,]+(?:\.\d+)?)",
                r"\bscope\s*3\b(?:\s*\([^)]*\))?[^0-9\n]{0,40}([\d,]+(?:\.\d+)?)",
                r"\bscope\s*3\b[\s\S]{0,80}?\b(?:was|were|reached|stood at|totalled|totaled)\s+([\d,]+(?:\.\d+)?)",
            ],
        }
        scope_patterns = {
            1: [
                rf"scope\s*1\s*(?:direct\s*)?(?:emissions?\s*)?[:\-]?\s*{number_pattern}",
                rf"direct\s*(?:ghg\s*)?emissions?\s*[:\-]?\s*{number_pattern}",
                rf"scope\s*1\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"combustion\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"operated\s*assets?\s*[:\-]?\s*{number_pattern}",
                rf"equity\s*share\s*[:\-]?\s*{number_pattern}",
                rf"operated\s*basis\s*[:\-]?\s*{number_pattern}",
                rf"own\s*operations\s*[:\-]?\s*{number_pattern}",
                rf"operations\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"operational\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"direct\s*operations\s*[:\-]?\s*{number_pattern}",
                rf"factory\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"manufacturing\s*emissions?\s*[:\-]?\s*{number_pattern}",
            ],
            2: [
                rf"scope\s*2\s*(?:indirect\s*)?(?:energy\s*)?(?:emissions?\s*)?[:\-]?\s*{number_pattern}",
                rf"(?:market.based|location.based)\s*[:\-]?\s*{number_pattern}",
                rf"scope\s*2\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"purchased\s*electricity\s*[:\-]?\s*{number_pattern}",
                rf"energy\s*indirect\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"market\s*based\s*[:\-]?\s*{number_pattern}",
                rf"location\s*based\s*[:\-]?\s*{number_pattern}",
                rf"electricity\s*consumption\s*[:\-]?\s*{number_pattern}",
            ],
            3: [
                rf"(?:total\s*)?financed\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"facilitated\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"portfolio\s*(?:ghg\s*)?emissions?\s*[:\-]?\s*{number_pattern}",
                rf"absolute\s*financed\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"scope\s*3\s*(?:value\s*chain\s*)?(?:emissions?\s*)?[:\-]?\s*{number_pattern}",
                rf"value\s*chain\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"brand\s*footprint\s*[:\-]?\s*{number_pattern}",
                rf"consumer\s*use\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"raw\s*materials?\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"ingredients\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"packaging\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"end\s*of\s*life\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"upstream\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"downstream\s*emissions?\s*[:\-]?\s*{number_pattern}",
                rf"(?:total\s*)?indirect\s*(?:ghg\s*)?emissions?\s*[:\-]?\s*{number_pattern}",
            ],
        }

        candidates: List[Dict[str, Any]] = []
        precision_candidates: List[Dict[str, Any]] = []
        for chunk in chunks or []:
            chunk_raw = chunk or ""
            chunk_lower = chunk_raw.lower()

            # Detect a chunk-level unit hint (e.g., the column header on a
            # table reads "(million tonnes CO2e)" while the row entries are
            # bare numbers). When the local 220-char window around a match
            # has no unit token, this lets us still apply the right multiplier.
            # Pass the case-preserved text so "MtCO2e" (megatonnes) and
            # "mtCO2e" (metric tonnes) are not conflated.
            chunk_unit_multiplier = self._detect_chunk_unit_multiplier(chunk_raw)

            for pattern in high_precision_patterns.get(scope_number, []):
                for match in re.finditer(pattern, chunk_lower):
                    try:
                        value = float(match.group(1).replace(",", ""))
                    except ValueError:
                        continue

                    year_match = re.search(r"20(1[5-9]|2[0-9])", chunk_lower)
                    year = int(year_match.group(0)) if year_match else None
                    precision_candidates.append(
                        {
                            "value": value * chunk_unit_multiplier,
                            "year": year,
                            "source_text": match.group(0),
                            "context": chunk_lower[max(0, match.start() - 60):min(len(chunk_lower), match.end() + 120)],
                            "confidence": "high",
                        }
                    )

            for pattern in scope_patterns.get(scope_number, []):
                for match in re.finditer(pattern, chunk_lower):
                    start = max(0, match.start() - 80)
                    end = min(len(chunk_lower), match.end() + 140)
                    context = chunk_lower[start:end]
                    value, source_text = self._extract_emission_value_with_unit(context)

                    # Fallback: when the local context lacks a unit token but
                    # the chunk header had one, use the regex-captured number
                    # times the chunk-level multiplier. Without this branch,
                    # typical table rows like "Scope 1   65,500" get dropped
                    # because tCO2e lives 200+ chars up in the column header.
                    if value is None:
                        try:
                            raw = float(match.group(1).replace(",", ""))
                        except (IndexError, ValueError):
                            continue
                        # Only trust the bare number when:
                        #   - the chunk supplies a unit hint, OR
                        #   - the matched scope phrase itself is unambiguous
                        #     (e.g., "scope 1 emissions: 65,500" — value
                        #     pattern matched right after the keyword)
                        if chunk_unit_multiplier == 1 and not re.search(
                            r"(emissions?|tco2e|co2e|tonnes?|metric tons?)",
                            context,
                        ):
                            continue
                        value = raw * chunk_unit_multiplier
                        source_text = match.group(0)

                    year_match = re.search(r"20(1[5-9]|2[0-9])", context)
                    year = int(year_match.group(0)) if year_match else None
                    candidates.append(
                        {
                            "value": value,
                            "year": year,
                            "source_text": source_text,
                            "context": context[:220],
                            "confidence": "high" if year else "medium",
                        }
                    )

        if precision_candidates:
            candidates = precision_candidates + candidates

        if not candidates:
            return {"value": None, "year": None, "source": None, "confidence": "none", "candidates_found": 0}

        # Filter candidates BEFORE choosing the best, otherwise a sub-total
        # number from a single facility line ("Scope 1 stationary combustion
        # = 979") shadows the consolidated figure ("Scope 1 = 65,500") and
        # the whole result collapses to None when 979 fails the magnitude
        # floor. Keep only candidates that pass the industry floor.
        industry_threshold_key = self._normalize_industry_for_threshold(industry_hint)
        valid_candidates = []
        for c in candidates:
            if self._validate_emission_magnitude(
                c.get("value"), scope_number, industry_threshold_key, "company"
            ) is not None:
                valid_candidates.append(c)

        # If the floor wiped out everything, retain the largest raw candidate
        # so the report still shows what extraction actually saw rather than
        # silently going None — the magnitude warning will already have
        # printed and the per-scope baseline fallback runs after this.
        pool_for_pick = valid_candidates if valid_candidates else candidates

        # "Total"-prefixed matches outrank bare matches; later years outrank
        # older ones; larger values outrank smaller within the same year.
        def _candidate_rank(c):
            text = (c.get("source_text") or "").lower()
            total_bonus = 1 if "total" in text else 0
            return (total_bonus, c.get("year") or 0, c.get("value") or 0)

        best = max(pool_for_pick, key=_candidate_rank)

        if not valid_candidates:
            # Best survived only because we relaxed; flag confidence accordingly.
            return {
                "value": None,
                "year": best.get("year"),
                "source": None,
                "confidence": "none",
                "candidates_found": len(candidates),
            }

        return {
            "value": best.get("value"),
            "year": best.get("year"),
            "source": f"PDF extraction - {(best.get('source_text') or '')[:50]}",
            "confidence": best.get("confidence", "medium"),
            "candidates_found": len(candidates),
        }

    def _extract_scope12_combined(self, chunks: List[str], industry_hint: str) -> Dict[str, Any]:
        """Extract combined Scope 1+2 figure and split into Scope 1/2 fallback values."""
        patterns = [
            r"scope\s*1\s*(?:and|&|\+)\s*2\s*[:\-]?\s*([\d,\.]+)\s*(million|billion|mt|kt)?",
            r"scope\s*1\s*(?:and|&|\+)\s*2\s*emissions?\s*[:\-]?\s*([\d,\.]+)\s*(million|billion|mt|kt)?",
            r"combined\s*scope\s*1\s*(?:and|&)\s*2\s*[:\-]?\s*([\d,\.]+)\s*(million|billion|mt|kt)?",
        ]

        candidates: List[Dict[str, Any]] = []
        for chunk in chunks or []:
            chunk_lower = (chunk or "").lower()
            for pattern in patterns:
                for match in re.finditer(pattern, chunk_lower):
                    start = max(0, match.start() - 60)
                    end = min(len(chunk_lower), match.end() + 120)
                    context = chunk_lower[start:end]
                    value, source_text = self._extract_emission_value_with_unit(context)
                    if value is None:
                        try:
                            raw = float(match.group(1).replace(",", ""))
                        except Exception:
                            continue
                        unit = (match.group(2) or "").lower()
                        if unit == "billion":
                            value = raw * 1_000_000_000
                        elif unit in {"million", "mt"}:
                            value = raw * 1_000_000
                        elif unit == "kt":
                            value = raw * 1_000
                        else:
                            value = raw

                    year_match = re.search(r"20(1[5-9]|2[0-9])", context)
                    year = int(year_match.group(0)) if year_match else None
                    candidates.append({
                        "value": value,
                        "year": year,
                        "source": source_text or match.group(0),
                    })

        if not candidates:
            return {"scope1": None, "scope2": None, "year": None, "source": None, "confidence": "none", "candidates_found": 0}

        best = max(candidates, key=lambda c: ((c.get("year") or 0), (c.get("value") or 0)))
        total_scope12 = best.get("value")
        if not isinstance(total_scope12, (int, float)):
            return {"scope1": None, "scope2": None, "year": None, "source": None, "confidence": "none", "candidates_found": len(candidates)}

        industry_key = self._normalize_industry_for_threshold(industry_hint)
        scope1_ratio = 0.85 if industry_key in {"oil and gas", "energy"} else 0.70
        scope2_ratio = 1.0 - scope1_ratio

        return {
            "scope1": round(float(total_scope12) * scope1_ratio, 2),
            "scope2": round(float(total_scope12) * scope2_ratio, 2),
            "year": best.get("year"),
            "source": f"PDF extraction - combined scope1+2 ({str(best.get('source') or '')[:40]})",
            "confidence": "medium",
            "candidates_found": len(candidates),
        }

    def _normalize_industry_for_threshold(self, industry: str) -> str:
        industry_key = str(industry or "general").lower().strip().replace("_", " ")
        aliases = {
            "oil_and_gas": "oil and gas",
            "financial services": "financial services",
            "bank": "banking",
            "banks": "banking",
            "consumer_goods": "consumer goods",
        }
        return aliases.get(industry_key, industry_key)

    def _validate_emission_magnitude(self, value: Optional[float], scope: int, industry: str, company: str) -> Optional[float]:
        """Reject implausibly small emissions for the industry; return None when rejected."""
        if value is None:
            return None

        industry_key = str(industry or "general").lower().strip()
        key_variants = [
            industry_key,
            industry_key.replace(" & ", "_and_"),
            industry_key.replace(" ", "_"),
            industry_key.replace("oil & gas", "energy"),
        ]

        minimum = None
        for key in key_variants:
            if scope == 3:
                minimum = SCOPE3_INDUSTRY_MINIMUMS.get(key)
            else:
                minimum = SCOPE1_INDUSTRY_MINIMUMS.get(key)
            if minimum is not None:
                break
        if minimum is None:
            minimum = 1_000

        if float(value) < minimum:
            print(
                f"[CarbonValidator] REJECTED Scope {scope}={value} "
                f"for {company} ({industry}) - below {minimum:,}"
            )
            return None
        return float(value)

    def _estimate_industry_for_baseline(self, company: str, text: str) -> str:
        """
        Best-effort industry estimation purely for baseline emissions fallback.
        Kept intentionally simple and deterministic (no external calls).
        """
        hay = f"{company} {text}".lower()
        # Avoid false positives from generic "greenhouse gas" language.
        oil_gas_markers = [
            "oil and gas",
            "oil & gas",
            "petroleum",
            "refinery",
            "upstream oil",
            "downstream oil",
            "lng",
            "exploration and production",
            "hydrocarbon",
        ]
        if any(k in hay for k in oil_gas_markers):
            return "oil_and_gas"
        if any(k in hay for k in ["coal", "thermal power", "mining coal"]):
            return "coal"
        if any(k in hay for k in ["mining", "ore", "tailings", "extraction site"]):
            return "mining"
        if any(k in hay for k in ["airline", "aviation", "jet fuel", "fleet emissions"]):
            return "aviation"
        if any(k in hay for k in ["cement", "clinker"]):
            return "cement"
        if any(k in hay for k in ["steel", "blast furnace"]):
            return "steel"
        if any(k in hay for k in ["chemical", "petrochemical", "polymer", "fertiliser", "fertilizer"]):
            return "chemicals"
        if any(k in hay for k in ["bank", "banking", "financial services", "lending", "financed emissions"]):
            return "banking"
        if any(k in hay for k in ["fmcg", "consumer goods", "home care", "personal care", "packaging"]):
            return "consumer_goods"
        if any(k in hay for k in ["software", "cloud", "data center", "datacenter", "saas"]):
            return "technology"
        return "unknown"

    def _derive_industry_hint(self, company: str, text: str, claim: Dict[str, Any] = None) -> str:
        """Prefer workflow-provided industry over heuristic baseline inference."""
        if isinstance(claim, dict):
            explicit = (
                claim.get("industry")
                or claim.get("sector")
                or (claim.get("metadata") or {}).get("industry")
            )
            if isinstance(explicit, str) and explicit.strip():
                normalized = explicit.strip().lower().replace("/", " ").replace("-", " ")
                if "tech" in normalized or "it" in normalized:
                    return "technology"
                if "oil" in normalized or "gas" in normalized or "energy" in normalized:
                    return "oil_and_gas"
                return self._normalize_industry_for_threshold(normalized)

        company_lower = str(company or "").lower()
        company_to_industry = {
            "microsoft": "technology",
            "apple": "technology",
            "google": "technology",
            "alphabet": "technology",
            "amazon": "technology",
            "meta": "technology",
        }
        for key, industry in company_to_industry.items():
            if key in company_lower:
                return industry

        return self._estimate_industry_for_baseline(company, text)

    def _fetch_cdp_carbon_data(self, company_name: str) -> Dict[str, Any]:
        """Best-effort CDP public web fallback for scope values."""
        query = f"{company_name} CDP scope 1 2 3 emissions tCO2e site:cdp.net"
        try:
            from ddgs import DDGS
            text_hits = []
            with DDGS() as ddgs:
                for result in ddgs.text(query, max_results=5):
                    title = result.get("title", "")
                    body = result.get("body", "")
                    text_hits.append(f"{title} {body}")
        except Exception:
            text_hits = []

        parsed = self._parse_cdp_results(text_hits)
        return parsed

    def _fetch_sbti_registry_status(self, company_name: str) -> Dict[str, Any]:
        """Best-effort SBTi registry signal extraction from public search results."""
        query = f"site:sciencebasedtargets.org/companies-taking-action {company_name}"
        try:
            from ddgs import DDGS

            text_hits: List[str] = []
            source_url = ""
            with DDGS() as ddgs:
                for result in ddgs.text(query, max_results=5):
                    title = result.get("title", "")
                    body = result.get("body", "")
                    href = result.get("href", "")
                    if not source_url and href:
                        source_url = href
                    text_hits.append(f"{title} {body}")

            blob = " ".join(text_hits).lower()
            if not blob:
                return {}

            if any(tok in blob for tok in ["targets set", "target set", "validated", "approved"]):
                status = "Targets set / validated"
                sbti_bool = True
            elif any(tok in blob for tok in ["committed", "commitment"]):
                status = "Committed"
                sbti_bool = True
            elif "removed" in blob or "inactive" in blob:
                status = "Not active"
                sbti_bool = False
            else:
                status = "Unverified"
                sbti_bool = None

            out: Dict[str, Any] = {
                "sbti_status": status,
                "sbti_source": source_url or "sciencebasedtargets.org/companies-taking-action",
            }
            out["science_based_target"] = sbti_bool
            return out
        except Exception:
            return {}

    def _extract_scope3_category_presence(self, text: str) -> Dict[str, Any]:
        """Extract Scope 3 category presence from report/evidence text (GHG 15-category taxonomy)."""
        lower = (text or "").lower()
        if not lower:
            return {}

        categories: Dict[str, Any] = {}

        # Direct mention of full category coverage.
        if re.search(r"scope\s*3[^\n\r]{0,80}(15\s*categories|categories\s*1\s*[-to]{1,3}\s*15)", lower):
            return {str(idx): "reported" for idx in self.scope3_categories.keys()}

        for idx, label in self.scope3_categories.items():
            label_lower = label.lower()
            # 1. Check numeric category markers
            number_hit = re.search(rf"(?:category|cat\.?|scope\s*3\s*category)\s*{idx}\b", lower)
            # 2. Check full label
            name_hit = label_lower in lower
            # 3. Check specific keywords
            keywords = self.scope3_keywords.get(idx, [])
            keyword_hit = any(kw in lower for kw in keywords)

            if number_hit or name_hit or keyword_hit:
                categories[str(idx)] = "reported"

        return categories

    def _extract_water_waste_disclosures(self, text: str) -> Dict[str, Any]:
        """Extract water and waste disclosure snippets for downstream compliance checks."""
        lower = (text or "").lower()
        out: Dict[str, Any] = {}
        if not lower:
            return out

        water_match = re.search(
            r"(?:water\s*(?:withdrawn|consumption|used|usage)|freshwater)[^\n\r]{0,80}?(\d[\d,\.]+)\s*(million\s*m3|m3|m\^3|cubic\s*met(?:er|re)s?)",
            lower,
            re.IGNORECASE,
        )
        if water_match:
            out["water_usage"] = {
                "value": water_match.group(1).replace(",", ""),
                "unit": water_match.group(2),
                "source": "Report/Evidence extraction",
            }
        elif "water" in lower and any(k in lower for k in ["withdraw", "consumption", "stress", "wastewater"]):
            out["water_usage"] = {
                "status": "disclosed",
                "source": "Report/Evidence extraction",
            }

        waste_match = re.search(
            r"(?:waste\s*(?:generated|disposed|recycled)|hazardous\s*waste)[^\n\r]{0,80}?(\d[\d,\.]+)\s*(tonnes|tons|t)",
            lower,
            re.IGNORECASE,
        )
        if waste_match:
            out["waste_data"] = {
                "value": waste_match.group(1).replace(",", ""),
                "unit": waste_match.group(2),
                "source": "Report/Evidence extraction",
            }
        elif "waste" in lower and any(k in lower for k in ["recycled", "landfill", "hazardous", "circular"]):
            out["waste_data"] = {
                "status": "disclosed",
                "source": "Report/Evidence extraction",
            }

        return out

    def _parse_cdp_results(self, results: List[str]) -> Dict[str, Any]:
        text = "\n".join(results or [])
        if not text:
            return {}

        def _extract_scope(patterns: List[str]) -> Optional[float]:
            for p in patterns:
                m = re.search(p, text, re.IGNORECASE)
                if m:
                    try:
                        return float(m.group(1).replace(",", ""))
                    except Exception:
                        continue
            return None

        scope1 = _extract_scope([r"scope\s*1[^\d]{0,20}(\d[\d,\.]*)"])
        scope2 = _extract_scope([r"scope\s*2[^\d]{0,20}(\d[\d,\.]*)"])
        scope3 = _extract_scope([r"scope\s*3[^\d]{0,20}(\d[\d,\.]*)"])

        if scope1 is None and scope2 is None and scope3 is None:
            return {}

        out: Dict[str, Any] = {
            "data_source": "CDP public web fallback",
        }
        if scope1 is not None:
            out["scope1"] = {"value": scope1, "unit": "tCO2e", "source": "CDP"}
        if scope2 is not None:
            out["scope2"] = {"value": scope2, "unit": "tCO2e", "source": "CDP"}
        if scope3 is not None:
            out["scope3"] = {"total": scope3, "unit": "tCO2e", "source": "CDP"}
        return out

    def _combine_evidence(self, evidence: List[Dict[str, Any]]) -> str:
        """Combine evidence documents into searchable text"""
        texts = []
        for ev in evidence[:15]:  # Limit to prevent token overflow
            title = ev.get("title", "")
            snippet = ev.get("snippet", ev.get("relevant_text", ""))
            texts.append(f"{title}: {snippet}")

        return "\n\n".join(texts)[:8000]  # Limit to ~2K tokens

    def _combine_report_chunks(self, report_chunks: List[Dict[str, Any]]) -> str:
        """Combine parsed report chunks with year hints.

        Sustainability reports run 200–900 chunks and the emissions tables
        often sit deep in the document. A fixed N=60 slice silently drops
        90%+ of the corpus before extraction even runs. Instead we:
          1. Surface chunks whose text mentions emission keywords first,
             then fall through to the rest in original order.
          2. Stop at a token budget (~32k chars after joining), which is
             what `_build_extraction_corpus` truncates to anyway.
        This way the LLM/regex passes see the parts of the document that
        actually contain numbers, even when those chunks aren't on the
        first few pages.
        """
        if not report_chunks:
            return ""

        emission_keywords = (
            "scope 1", "scope 2", "scope 3",
            "tco2e", "co2e", "tonnes co2", "ghg emissions", "ghg intensity",
            "carbon emissions", "emissions intensity", "operational emissions",
            "financed emissions", "value chain emissions", "tco2", "mtco2",
        )

        priority: List[str] = []
        rest: List[str] = []
        for chunk in report_chunks:
            chunk_text = str(chunk.get("page_content") or chunk.get("text", ""))
            if not chunk_text:
                continue
            year = chunk.get("year", "unknown")
            report_year = chunk.get("report_year", year)
            tagged = f"[REPORT YEAR {report_year}] {chunk_text[:2000]}"
            if any(kw in chunk_text.lower() for kw in emission_keywords):
                priority.append(tagged)
            else:
                rest.append(tagged)

        ordered = priority + rest
        # 32k char budget (matches _build_extraction_corpus truncation).
        out: List[str] = []
        used = 0
        for piece in ordered:
            if used + len(piece) + 2 > 32000:
                break
            out.append(piece)
            used += len(piece) + 2
        return "\n\n".join(out)

    def _combine_report_claims(self, report_claims_by_year: Dict[Any, List[str]]) -> str:
        """Combine report claims grouped by year."""
        texts = []
        for year in sorted(report_claims_by_year.keys(), reverse=True):
            claims = report_claims_by_year.get(year, [])
            if not claims:
                continue
            joined = "\n".join(f"- {c}" for c in claims[:80])
            texts.append(f"[REPORT CLAIMS {year}]\n{joined}")
        return "\n\n".join(texts)

    def _build_extraction_corpus(self,
                                 evidence: List[Dict[str, Any]],
                                 report_chunks: List[Dict[str, Any]],
                                 report_claims_by_year: Dict[Any, List[str]]) -> Tuple[str, Dict[str, int]]:
        """Build prioritized corpus: report chunks, then report claims, then evidence."""
        report_text = self._combine_report_chunks(report_chunks)
        report_claim_text = self._combine_report_claims(report_claims_by_year)
        evidence_text = self._combine_evidence(evidence)

        corpus_parts = []
        if report_text:
            corpus_parts.append("=== PRIORITY 1: ESG REPORT CHUNKS ===\n" + report_text)
        if report_claim_text:
            corpus_parts.append("=== PRIORITY 2: REPORT CLAIMS BY YEAR ===\n" + report_claim_text)
        if evidence_text:
            corpus_parts.append("=== PRIORITY 3: EXTERNAL EVIDENCE ===\n" + evidence_text)

        combined = "\n\n".join(corpus_parts)[:32000]
        meta = {
            "report_chunks": len(report_chunks),
            "report_claim_years": len(report_claims_by_year.keys()),
            "evidence_documents": len(evidence)
        }
        return combined, meta

    def _get_known_emissions(self, company: str) -> Optional[Dict[str, Any]]:
        """Deprecated lookup retained for API compatibility.

        The hardcoded "known emissions" database has been removed because it
        silently overrode real extraction with stale per-company figures
        stamped "BRSR Filing / CDP Disclosure". Always returns None — every
        run must derive scope 1/2/3 from disclosures, regex passes, the LLM
        extractor, or the explicit industry-baseline fallback.
        """
        return None

    def _llm_extract_carbon(self, company: str, evidence_text: str,
                           claim: Dict[str, Any] = None) -> Dict[str, Any]:
        """Use LLM to extract carbon figures from evidence"""

        claim_text = claim.get("claim_text", "") if claim else ""

        user_prompt = f"""COMPANY: {company}
CLAIM BEING VERIFIED: {claim_text}

EVIDENCE TO ANALYZE:
{evidence_text}

Extract ALL carbon emission data. Return ONLY valid JSON."""

        try:
            response = asyncio.run(call_llm("carbon_extraction", user_prompt, system=CARBON_EXTRACTION_PROMPT))
        except Exception as e:
            print(f"❌ LLM extraction failed: {e}")
            return {}

        if not response:
            print("❌ LLM extraction failed")
            return {}

        try:
            cleaned = self._clean_json_response(response)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parsing error: {e}")
            # Attempt regex extraction
            return self._regex_extract_carbon(evidence_text)

    def _regex_extract_carbon(self, text: str) -> Dict[str, Any]:
        """Fallback regex extraction for carbon figures"""

        result = {"scope1": {}, "scope2": {}, "scope3": {}, "total": {}}

        # Stronger extraction patterns aligned to report wording
        patterns = [
            (r'Scope\s*1[^\n\r]{0,120}?(\d[\d,\.]+)\s*(MtCO2e|ktCO2e|tCO2e|tons?|tonnes?)?', "scope1"),
            (r'Scope\s*2[^\n\r]{0,120}?(\d[\d,\.]+)\s*(MtCO2e|ktCO2e|tCO2e|tons?|tonnes?)?', "scope2"),
            (r'Scope\s*3[^\n\r]{0,120}?(\d[\d,\.]+)\s*(MtCO2e|ktCO2e|tCO2e|tons?|tonnes?)?', "scope3"),
            (r'Total\s+emissions[^\n\r]{0,120}?(\d[\d,\.]+)\s*(MtCO2e|ktCO2e|tCO2e|tons?|tonnes?)?', "total"),
            (r'carbon\s+footprint[:\s]+(\d+(?:,\d+)*(?:\.\d+)?)\s*(MtCO2e|ktCO2e|tCO2e|MT|tonnes?)', "total"),
        ]

        for pattern, scope in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1).replace(",", ""))
                unit = match.group(2) if len(match.groups()) > 1 and match.group(2) else "tCO2e"
                normalized_value = self._normalize_units(value, unit)
                if scope == "scope3":
                    result[scope] = {"total": normalized_value, "unit": "tCO2e", "source": "regex_extraction"}
                elif scope == "total":
                    result[scope] = {"value": normalized_value, "unit": "tCO2e", "source": "regex_extraction"}
                else:
                    result[scope] = {"value": normalized_value, "unit": "tCO2e", "source": "regex_extraction"}

        return result

    def _validate_emissions(self, data: Dict[str, Any], company: str) -> Dict[str, Any]:
        """Validate emission figures for reasonableness"""

        validated = {"scope1": {}, "scope2": {}, "scope3": {}}

        for scope in ["scope1", "scope2", "scope3"]:
            scope_data = data.get(scope, {})

            if isinstance(scope_data, dict):
                value = scope_data.get("value")
                if value is None and scope == "scope3":
                    value = scope_data.get("total")

                if value is not None:
                    # Normalize to tCO2e
                    normalized_value = self._normalize_units(value, scope_data.get("unit", "tCO2e"))

                    # Flag suspicious values
                    validation_flags = []
                    if normalized_value > 1_000_000_000:  # > 1 billion tCO2e
                        validation_flags.append("exceptionally_high_value")
                    if normalized_value < 0:
                        validation_flags.append("negative_value_invalid")

                    validated_scope = {
                        "value": normalized_value,
                        "unit": "tCO2e",
                        "original_value": value,
                        "original_unit": scope_data.get("unit"),
                        "year": scope_data.get("year"),
                        "validation_flags": validation_flags,
                        "verified": len(validation_flags) == 0
                    }
                    if scope == "scope3":
                        validated_scope["total"] = normalized_value
                    validated[scope] = validated_scope
            elif isinstance(scope_data, (int, float)):
                validated[scope] = {
                    "value": float(scope_data),
                    "unit": "tCO2e",
                    "verified": True
                }

        return validated

    def _normalize_units(self, value: float, unit: str) -> float:
        """Normalize emission values to tCO2e"""

        unit_lower = (unit or "tco2e").lower().strip()
        unit_lower = unit_lower.replace(" ", "")

        conversions = {
            "tco2e": 1.0,
            "tco2": 1.0,
            "mtco2e": 1_000_000,  # Megatonnes
            "mtco2": 1_000_000,
            "ktco2e": 1_000,  # Kilotonnes
            "ktco2": 1_000,
            "mmtco2e": 1_000_000,
            "milliontonnes": 1_000_000,
            "kgco2e": 0.001,  # Kilograms
            "kgco2": 0.001,
            "mt": 1.0,  # Metric tonnes
            "tonne": 1.0,
            "tonnes": 1.0,
            "tons": 0.907,  # US short tons
            "ton": 0.907,
            "lakh tonnes": 100_000,  # Indian lakh
            "crore tonnes": 10_000_000  # Indian crore
        }

        conversion_factor = conversions.get(unit_lower, 1.0)
        return float(value) * conversion_factor

    def _extract_annual_emissions(self, text: str) -> Dict[int, float]:
        """Extract coarse annual total emissions series for temporal analysis."""
        annual = {}
        if not text:
            return annual

        for match in re.finditer(
            r"((?:19|20)\d{2})[^\n\r]{0,120}?(?:total\s+emissions|scope\s*1\s*\+\s*scope\s*2|ghg\s+emissions)[^\n\r]{0,120}?(\d[\d,\.]+)\s*(MtCO2e|ktCO2e|tCO2e|tons?|tonnes?)",
            text,
            re.IGNORECASE,
        ):
            year = int(match.group(1))
            value = float(match.group(2).replace(",", ""))
            unit = match.group(3) or "tCO2e"
            annual[year] = self._normalize_units(value, unit)

        return dict(sorted(annual.items()))

    def _calculate_intensity(self, data: Dict[str, Any], company: str) -> Dict[str, Any]:
        """Calculate carbon intensity metrics"""

        total_scope1 = data.get("scope1", {}).get("value", 0) or 0
        total_scope2 = data.get("scope2", {}).get("value", 0) or 0
        total_scope3 = data.get("scope3", {}).get("total", data.get("scope3", {}).get("value", 0)) or 0

        total_emissions = total_scope1 + total_scope2 + total_scope3

        return {
            "total_emissions_tco2e": total_emissions,
            "scope1_percentage": (total_scope1 / max(total_emissions, 1)) * 100,
            "scope2_percentage": (total_scope2 / max(total_emissions, 1)) * 100,
            "scope3_percentage": (total_scope3 / max(total_emissions, 1)) * 100,
            "scope3_completeness": self._assess_scope3_completeness(data.get("scope3", {})),
            "market_vs_location_scope2": data.get("scope2", {}).get("methodology", "Unknown")
        }

    def _calculate_total(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate total emissions across all scopes"""

        scope1 = data.get("scope1", {}).get("value", 0) or 0
        scope2 = data.get("scope2", {}).get("value", 0) or 0
        scope3_data = data.get("scope3", {})
        scope3 = scope3_data.get("total", scope3_data.get("value", 0)) or 0

        return {
            "scope1_2": scope1 + scope2,
            "all_scopes": scope1 + scope2 + scope3,
            "scope1_2_3_available": all([scope1, scope2, scope3])
        }

    def _assess_scope3_completeness(self, scope3_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess Scope 3 reporting completeness (GHG Protocol)"""

        if not scope3_data:
            return {
                "categories_reported": 0,
                "total_categories": 15,
                "completeness_percentage": 0,
                "material_categories_covered": False
            }

        categories = scope3_data.get("categories", {})
        categories_reported = len([c for c in categories.values() if c])

        # Material categories (usually account for >90% of Scope 3)
        material_categories = [1, 4, 9, 11, 12]  # Purchased goods, transport, use of products
        material_covered = sum(1 for c in material_categories if str(c) in categories or c in categories)

        return {
            "categories_reported": categories_reported,
            "total_categories": 15,
            "completeness_percentage": (categories_reported / 15) * 100,
            "material_categories_covered": material_covered >= 3,
            "missing_material_categories": [self.scope3_categories[c] for c in material_categories
                                           if str(c) not in categories and c not in categories]
        }

    def _check_ghg_compliance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check GHG Protocol Corporate Standard compliance"""

        checks = {
            "scope1_reported": bool(data.get("scope1", {}).get("value")),
            "scope2_reported": bool(data.get("scope2", {}).get("value")),
            "scope3_reported": bool(data.get("scope3", {}).get("value") or
                                   data.get("scope3", {}).get("total")),
            "boundaries_defined": data.get("organizational_boundary") is not None,
            "base_year_stated": data.get("base_year") is not None,
            "methodology_disclosed": data.get("methodology") is not None
        }

        compliance_score = sum(checks.values()) / len(checks) * 100

        return {
            "checks": checks,
            "compliance_score": compliance_score,
            "compliant": compliance_score >= 50,  # Minimum Scope 1+2
            "standard": "GHG Protocol Corporate Standard",
            "missing_requirements": [k for k, v in checks.items() if not v]
        }

    def _check_brsr_compliance(self, data: Dict[str, Any], company: str) -> Dict[str, Any]:
        """
        Check SEBI BRSR (Business Responsibility & Sustainability Report) compliance
        Applicable to top 1000 listed Indian companies
        """

        brsr_checks = {
            "scope1_emissions_disclosed": bool(data.get("scope1", {}).get("value")),
            "scope2_emissions_disclosed": bool(data.get("scope2", {}).get("value")),
            "total_energy_consumption": bool(data.get("energy_consumption")),
            "renewable_energy_percentage": bool(data.get("renewable_percentage")),
            "ghg_reduction_targets": bool(data.get("reduction_targets")),
            "water_usage_disclosed": bool(data.get("water_usage")),
            "waste_management_disclosed": bool(data.get("waste_data"))
        }

        compliance_score = sum(brsr_checks.values()) / len(brsr_checks) * 100

        return {
            "applicable": True,  # Assume applicable for listed companies
            "checks": brsr_checks,
            "compliance_score": compliance_score,
            "regulation": "SEBI BRSR (India)",
            "effective_from": "FY 2022-23",
            "top_1000_mandate": True,
            "missing_disclosures": [k for k, v in brsr_checks.items() if not v],
            "grid_emission_factor_used": self.india_grid_emission_factor
        }

    def _assess_data_quality(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess quality of carbon data"""

        # PHASE 7 FIX: Check if any emissions data exists
        has_scope1 = bool(data.get("scope1", {}).get("value"))
        has_scope2 = bool(data.get("scope2", {}).get("value"))
        has_scope3 = bool(data.get("scope3", {}).get("value") or data.get("scope3", {}).get("total"))

        # If NO disclosed emissions data exists, keep score non-zero to avoid downstream collapse.
        # This reflects "estimated baseline available" rather than "no signal at all".
        if not (has_scope1 or has_scope2 or has_scope3):
            return {
                "factors": {
                    "scope1_present": 0,
                    "scope2_present": 0,
                    "scope3_present": 0,
                    "year_specified": 0,
                    "methodology_stated": 0,
                    "third_party_verified": 0,
                    "baseline_estimated": 25
                },
                "overall_score": 25,
                "data_confidence": "Low",
                "status": "estimated_baseline",
                "message": "No disclosed Scope 1/2/3 values found; using industry baseline estimate with low confidence."
            }

        quality_factors = {
            "scope1_present": 25 if has_scope1 else 0,
            "scope2_present": 25 if has_scope2 else 0,
            "scope3_present": 20 if has_scope3 else 0,
            "year_specified": 10 if any(d.get("year") for d in [data.get("scope1", {}),
                                                                 data.get("scope2", {})]) else 0,
            "methodology_stated": 10 if data.get("methodology") else 0,
            "third_party_verified": 10 if data.get("verified") else 0
        }

        overall_score = sum(quality_factors.values())

        return {
            "factors": quality_factors,
            "overall_score": overall_score,
            "data_confidence": "High" if overall_score >= 70 else
                              "Medium" if overall_score >= 40 else "Low",
            "status": "sufficient_data" if overall_score > 0 else "insufficient_data",
            "message": "Emissions data not available in retrieved sources." if overall_score == 0 else None
        }

    def _analyze_carbon_claims(self, claim: Dict[str, Any],
                               carbon_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze carbon-related claims against extracted data"""

        if not claim:
            return {"analysis_performed": False}

        claim_text = claim.get("claim_text", "").lower()

        # Detect carbon-related claims
        carbon_keywords = ["carbon neutral", "net zero", "carbon negative", "scope 1",
                          "scope 2", "scope 3", "emissions", "ghg", "carbon footprint",
                          "decarbonization", "decarbonisation"]

        is_carbon_claim = any(kw in claim_text for kw in carbon_keywords)

        if not is_carbon_claim:
            return {"analysis_performed": False, "reason": "Not a carbon-related claim"}

        # Analyze claim veracity
        analysis = {
            "analysis_performed": True,
            "claim_type": self._classify_carbon_claim(claim_text),
            "data_available_to_verify": bool(carbon_data.get("scope1", {}).get("value") or
                                            carbon_data.get("scope2", {}).get("value")),
            "red_flags": []
        }

        # Check for unsubstantiated claims
        if "carbon neutral" in claim_text or "net zero" in claim_text:
            if not carbon_data.get("scope3"):
                analysis["red_flags"].append("Carbon neutral/net zero claim without Scope 3 disclosure")

            offset_audit = carbon_data.get("offset_transparency", {}) if isinstance(carbon_data, dict) else {}
            if offset_audit and offset_audit.get("status") == "high_avoidance_reliance":
                analysis["red_flags"].append("Carbon neutral claim relies heavily on avoidance offsets")
            elif not offset_audit or offset_audit.get("total_offset_mentions", 0) == 0:
                analysis["red_flags"].append("Carbon neutral claim without offset disclosure")

        if "100%" in claim_text and "renewable" in claim_text:
            if not carbon_data.get("renewable_percentage"):
                analysis["red_flags"].append("100% renewable claim without supporting data")

        return analysis

    def _classify_carbon_claim(self, claim_text: str) -> str:
        """Classify the type of carbon claim"""

        if "net zero" in claim_text:
            return "net_zero_commitment"
        elif "carbon neutral" in claim_text:
            return "carbon_neutral_claim"
        elif "carbon negative" in claim_text:
            return "carbon_negative_claim"
        elif "reduction" in claim_text or "reduce" in claim_text:
            return "emission_reduction_target"
        elif "scope 3" in claim_text:
            return "value_chain_emission_claim"
        elif "renewable" in claim_text:
            return "renewable_energy_claim"
        else:
            return "general_carbon_claim"

    def _detect_carbon_red_flags(self, data: Dict[str, Any],
                                 evidence_text: str) -> List[Dict[str, Any]]:
        """Detect carbon accounting red flags"""

        red_flags = []

        # 1. Scope 3 significantly smaller than Scope 1+2 (rare for most companies)
        scope1 = data.get("scope1", {}).get("value", 0) or 0
        scope2 = data.get("scope2", {}).get("value", 0) or 0
        scope3 = data.get("scope3", {}).get("value", 0) or 0

        if scope3 and scope3 < (scope1 + scope2) * 0.5:
            if not any(ind in evidence_text.lower() for ind in ["service", "software", "consulting"]):
                red_flags.append({
                    "flag": "Scope 3 unusually low",
                    "severity": "Medium",
                    "detail": "Scope 3 < 50% of Scope 1+2, unusual for most industries"
                })

        # 2. No year-over-year comparison
        if not data.get("previous_year"):
            red_flags.append({
                "flag": "No historical comparison",
                "severity": "Low",
                "detail": "Single year data without trend analysis"
            })

        # 3. Net zero claims without Scope 3
        if any(phrase in evidence_text.lower() for phrase in ["net zero", "carbon neutral"]):
            if not data.get("scope3", {}).get("value"):
                red_flags.append({
                    "flag": "Net zero without Scope 3",
                    "severity": "High",
                    "detail": "Net zero/carbon neutral claim without Scope 3 disclosure"
                })

        # 4. Heavy reliance on offsets (avoidance-focused)
        offset_audit = self._audit_offset_transparency(evidence_text, data)
        if offset_audit.get("status") == "high_avoidance_reliance":
            red_flags.append({
                "flag": "Offset-heavy strategy (avoidance-dominant)",
                "severity": "High",
                "detail": "Offset mix is dominated by avoidance credits over removals"
            })

        # 5. Missing intensity metrics
        if (scope1 or scope2) and not any(
            term in evidence_text.lower()
            for term in ["per revenue", "per employee", "intensity", "per unit"]
        ):
            red_flags.append({
                "flag": "No intensity metrics",
                "severity": "Low",
                "detail": "Absolute emissions without intensity normalization"
            })

        return red_flags

    def _audit_offset_transparency(self, text: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Audit offset disclosures and classify avoidance vs removal reliance."""
        lower = (text or "").lower()

        removal_terms = [
            "direct air capture", "dac", "biochar", "mineralization", "carbon removal",
            "reforestation", "afforestation", "soil carbon", "enhanced weathering", "beccs"
        ]
        avoidance_terms = [
            "avoided emissions", "cookstove", "clean cookstove", "renewable project credits",
            "landfill gas", "methane avoidance", "energy efficiency credits", "prevented deforestation"
        ]

        removal_mentions = sum(lower.count(t) for t in removal_terms)
        avoidance_mentions = sum(lower.count(t) for t in avoidance_terms)
        generic_offset_mentions = lower.count("offset") + lower.count("credit") + lower.count("vcu") + lower.count("verra")
        total_mentions = removal_mentions + avoidance_mentions + generic_offset_mentions

        rem_pct = self._extract_nearby_percentage(lower, ["removal", "carbon removal", "removals"])
        avd_pct = self._extract_nearby_percentage(lower, ["avoidance", "avoided emissions", "avoidance credits"])

        if rem_pct is not None or avd_pct is not None:
            rem = max(0.0, min(100.0, rem_pct if rem_pct is not None else 100.0 - float(avd_pct or 0.0)))
            avd = max(0.0, min(100.0, avd_pct if avd_pct is not None else 100.0 - rem))
        elif (removal_mentions + avoidance_mentions) > 0:
            rem = (removal_mentions / max(1, removal_mentions + avoidance_mentions)) * 100.0
            avd = (avoidance_mentions / max(1, removal_mentions + avoidance_mentions)) * 100.0
        else:
            rem = 0.0
            avd = 0.0

        if total_mentions == 0:
            status = "no_offset_disclosure"
            risk_penalty = 0
        elif avd >= 70 and avd > rem:
            status = "high_avoidance_reliance"
            risk_penalty = 15
        elif avd >= 55 and avd > rem:
            status = "moderate_avoidance_reliance"
            risk_penalty = 8
        else:
            status = "balanced_or_removal_weighted"
            risk_penalty = 0

        return {
            "status": status,
            "avoidance_share_pct": round(avd, 1),
            "removal_share_pct": round(rem, 1),
            "avoidance_mentions": avoidance_mentions,
            "removal_mentions": removal_mentions,
            "total_offset_mentions": total_mentions,
            "risk_penalty_points": risk_penalty
        }

    def _extract_nearby_percentage(self, text: str, keywords: List[str]) -> Optional[float]:
        """Extract first percentage near any keyword from a text blob."""
        for kw in keywords:
            m = re.search(rf"{re.escape(kw)}[^\n\r]{{0,60}}?(\d{{1,3}}(?:\.\d+)?)\s*%", text, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1))
                except Exception:
                    continue
        return None

    def _clean_json_response(self, text: str) -> str:
        """Clean JSON from LLM response"""

        text = re.sub(r'```\s*json?\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        start = text.find('{')
        end = text.rfind('}') + 1

        if start != -1 and end > start:
            return text[start:end]

        return text


# Global instance
carbon_extractor = CarbonExtractor()

def get_carbon_extractor() -> CarbonExtractor:
    """Get global carbon extractor instance"""
    return carbon_extractor
