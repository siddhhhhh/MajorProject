import json
import os

class CarbonDataValidator:
    """
    Validates extracted carbon emissions data against industry-specific
    plausibility floors. Rejects bad data and triggers fallback retrieval.
    """

    MAX_ACCEPTABLE_DATA_AGE_YEARS = 3  # reject data older than this

    def _resolve_floor_key(self, industry: str, floors: dict) -> str:
        """Resolve the best floor key for an industry with safe matching."""
        industry = str(industry or "").strip()
        if not industry:
            return "Default"

        # Exact match first
        if industry in floors:
            return industry

        industry_lower = industry.lower()

        # Case-insensitive exact
        for key in floors:
            if key.lower() == industry_lower:
                return key

        # Normalize separators for loose matching
        normalized = industry_lower.replace("_", " ").replace("&", "and")
        for key in floors:
            key_norm = key.lower().replace("_", " ").replace("&", "and")
            if normalized == key_norm:
                return key

        # Partial match (Technology -> IT / Technology)
        for key in floors:
            key_norm = key.lower()
            if industry_lower in key_norm or key_norm in industry_lower:
                return key

        return "Default"

    def validate(self, carbon_data: dict, company: str, 
                 industry: str, report_year: int) -> dict:
        """
        Main entry point. Returns a validated carbon_data dict with:
        - rejection flags
        - fallback estimates if rejected
        - quality score
        - data_age_years
        
        Input carbon_data format:
        {
          "scope1": float | None,
          "scope2": float | None,  
          "scope3": float | None,
          "data_year": int | None,
          "data_quality": int,          # 0-100
          "source": str
        }
        """
        
        result = carbon_data.copy()
        result["validation"] = {
            "passed": False,
            "rejection_reasons": [],
            "warnings": [],
            "data_age_years": None,
            "floor_used": None,
            "fallback_triggered": False,
            "fallback_estimate": None,
            "validated_quality_score": 0
        }

        # Debug trace for pipeline validation handoff.
        print(f"[DEBUG] validate called: company={company} industry={industry}")

        scope1 = carbon_data.get("scope1")
        scope2 = carbon_data.get("scope2")
        scope3 = carbon_data.get("scope3")

        # Treat combined Scope 1+2 totals as real extracted data signals.
        emissions_detail = carbon_data.get("emissions_detail", {})
        total_combined = (
            (emissions_detail.get("total") or {}).get("scope1_2")
            or (emissions_detail.get("total") or {}).get("all_scopes")
        )

        truly_null = (
            scope1 is None
            and scope2 is None
            and scope3 is None
            and total_combined is None
        )

        if truly_null:
            result["validation"]["rejection_reasons"].append(
                "All carbon scope values are null and no combined total was found. "
                "PDF chunks may not contain emissions data, or the ESG section filter "
                "excluded the relevant pages."
            )
            result["validation"]["fallback_triggered"] = True
            floors = self._get_floors(industry)
            floor_key = self._resolve_floor_key(industry, self._load_all_floors())
            result["validation"]["floor_used"] = floor_key
            result["validation"]["fallback_estimate"] = self._build_fallback(
                company, industry, floors
            )
            return result
        
        floors = self._get_floors(industry)
        floor_key = self._resolve_floor_key(industry, self._load_all_floors())
        result["validation"]["floor_used"] = floor_key

        # STEP 1: Unit detection and auto-correction (before floor checks)
        def detect_and_correct_units(value, label):
            """Detects ktCO2e/MtCO2e values and returns corrected tCO2e."""
            if value is None:
                return value, None
            try:
                value_num = float(value)
            except (TypeError, ValueError):
                return value, None
            if value_num <= 0:
                return value_num, None

            floor_min = float(floors.get("scope1_min", 100))

            # ktCO2e -> tCO2e
            if value_num < floor_min and value_num * 1_000 >= floor_min * 0.1:
                corrected = value_num * 1_000
                note = (
                    f"{label} auto-corrected: {value_num} appears to be in "
                    f"ktCO2e. Corrected to {corrected:,.0f} tCO2e."
                )
                result["validation"]["warnings"].append(note)
                return corrected, note

            # MtCO2e -> tCO2e
            if value_num < floor_min and value_num * 1_000_000 >= floor_min * 0.1:
                corrected = value_num * 1_000_000
                note = (
                    f"{label} auto-corrected: {value_num} appears to be in "
                    f"MtCO2e. Corrected to {corrected:,.0f} tCO2e."
                )
                result["validation"]["warnings"].append(note)
                return corrected, note

            return value_num, None

        scope1, scope1_note = detect_and_correct_units(scope1, "Scope 1")
        scope2, scope2_note = detect_and_correct_units(scope2, "Scope 2")
        scope3, scope3_note = detect_and_correct_units(scope3, "Scope 3")

        if scope1_note:
            result["scope1_corrected"] = scope1
        if scope2_note:
            result["scope2_corrected"] = scope2
        if scope3_note:
            result["scope3_corrected"] = scope3

        # Keep corrected values in result for downstream consumers.
        result["scope1"] = scope1
        result["scope2"] = scope2
        result["scope3"] = scope3
        
        # STEP 2: Data age check
        if carbon_data.get("data_year"):
            age = report_year - carbon_data["data_year"]
            result["validation"]["data_age_years"] = age
            if age > self.MAX_ACCEPTABLE_DATA_AGE_YEARS:
                result["validation"]["rejection_reasons"].append(
                    f"Data is {age} years old (from {carbon_data['data_year']}). "
                    f"Maximum acceptable age is {self.MAX_ACCEPTABLE_DATA_AGE_YEARS} years."
                )
        else:
            result["validation"]["warnings"].append(
                "No data_year provided — cannot assess data age."
            )

        # STEP 3: Scope 1 floor check (uses corrected values)
        if scope1 is None or scope1 == 0:
            result["validation"]["rejection_reasons"].append(
                f"Scope 1 is missing or zero. Cannot evaluate net-zero claim "
                f"without direct operational emissions."
            )
        elif scope1 < floors["scope1_min"]:
            result["validation"]["rejection_reasons"].append(
                f"Scope 1 = {scope1:,.0f} tCO2e is below the minimum plausible "
                f"floor of {floors['scope1_min']:,.0f} tCO2e for {industry} companies. "
                f"Likely a data extraction error or unit mismatch (check if value "
                f"is in MtCO2e instead of tCO2e)."
            )

        # STEP 4: Scope 3 completeness (for net-zero claims)
        if scope1 and scope3 is not None and scope3 > 0:
            ratio = scope3 / scope1
            is_finance = industry in ("Banking / Finance", "Insurance")

            if ratio < 0.0001 and not is_finance:
                # Physically impossible - almost certainly unit error
                corrected_kt = scope3 * 1_000
                corrected_mt = scope3 * 1_000_000

                if corrected_kt / scope1 > 0.0001:
                    hint = (
                        f"Likely ktCO2e unit error. "
                        f"Corrected: {corrected_kt:,.0f} tCO2e "
                        f"({corrected_kt/scope1:.1%} of Scope 1)."
                    )
                    result["scope3_corrected"] = corrected_kt
                    result["scope3_correction_unit"] = "ktCO2e"
                elif corrected_mt / scope1 > 0.01:
                    hint = (
                        f"Likely MtCO2e unit error. "
                        f"Corrected: {corrected_mt:,.0f} tCO2e."
                    )
                    result["scope3_corrected"] = corrected_mt
                    result["scope3_correction_unit"] = "MtCO2e"
                else:
                    hint = "Cannot auto-correct - manual review required."
                    result["scope3_corrected"] = None

                result["validation"]["rejection_reasons"].append(
                    f"Scope 3 ({scope3:,.2f} tCO2e) is {ratio:.6%} of "
                    f"Scope 1 ({scope1:,.0f} tCO2e). "
                    f"Physically implausible for {industry}. {hint}"
                )

            elif ratio < 1.0 and not is_finance:
                # Smaller than Scope 1 but not impossibly so - warn only
                result["validation"]["warnings"].append(
                    f"Scope 3 ({scope3:,.0f}) is less than "
                    f"Scope 1 ({scope1:,.0f}). "
                    f"For most industries Scope 3 is 5-20x larger. "
                    f"Possible incomplete calculation (check category coverage)."
                )

        # STEP 5: Data quality score threshold
        if carbon_data.get("data_quality", 0) < 40:
            result["validation"]["rejection_reasons"].append(
                f"Data quality score is {carbon_data.get('data_quality', 0)}/100, "
                f"below the 40/100 minimum threshold for inclusion."
            )

        # DECISION: pass or reject
        if not result["validation"]["rejection_reasons"]:
            result["validation"]["passed"] = True
            result["validation"]["validated_quality_score"] = carbon_data.get(
                "data_quality", 50
            )
        else:
            result["validation"]["passed"] = False
            result["validation"]["fallback_triggered"] = True
            result["validation"]["fallback_estimate"] = self._build_fallback(
                company, industry, floors
            )
            result["validation"]["validated_quality_score"] = 0

        return result

    def _load_all_floors(self) -> dict:
        floors_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "emissions_floors.json"
        )
        with open(floors_path) as f:
            data = json.load(f)
        return data["emissions_floors"]

    def _get_floors(self, industry: str) -> dict:
        floors = self._load_all_floors()
        floor_key = self._resolve_floor_key(industry, floors)
        return floors.get(
            floor_key,
            floors.get(
                "Default",
                {
                    "scope1_min": 100,
                    "scope1_typical_low": 10000,
                    "scope1_typical_high": 1000000,
                    "notes": "Default floors - industry not found",
                },
            ),
        )

    def _build_fallback(self, company: str, industry: str, floors: dict) -> dict:
        """
        Returns a clearly labelled estimated range when real data is rejected.
        This is shown in the report instead of the bad extracted value.
        """
        return {
            "type": "industry_estimate",
            "scope1_estimated_low": floors["scope1_typical_low"],
            "scope1_estimated_high": floors["scope1_typical_high"],
            "display_string": (
                f"Scope 1 data could not be verified from available sources. "
                f"Based on industry benchmarks for {industry} companies of "
                f"similar scale, estimated Scope 1 emissions range: "
                f"{floors['scope1_typical_low'] / 1_000_000:.0f}M – "
                f"{floors['scope1_typical_high'] / 1_000_000:.0f}M tCO2e/year. "
                f"Upload the company's latest annual report or CDP submission "
                f"to obtain verified figures."
            ),
            "confidence": "LOW",
            "source": "Industry benchmark estimate — not company-verified"
        }
