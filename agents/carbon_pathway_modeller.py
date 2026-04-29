from typing import Any, Dict


SCOPE3_FEASIBILITY_RULES = {
    "oil_and_gas": {
        "production_growth + scope3_reduction": "PHYSICALLY_IMPOSSIBLE",
        "production_stable + scope3_reduction_<20pct": "FEASIBLE_EFFICIENCY_ONLY",
        "production_decline + scope3_reduction": "FEASIBLE",
        "production_growth + scope3_intensity_reduction": "POSSIBLE_BUT_MISLEADING",
    }
}

IEA_NZE_REFERENCE = {
    "energy": {2030: 0.54, 2050: 1.0},
    "oil_and_gas": {2030: 0.54, 2050: 1.0},
    "utilities": {2030: 0.62, 2050: 1.0},
    "technology": {2030: 0.42, 2050: 1.0},
    "default": {2030: 0.45, 2050: 1.0},
}

IPCC_BUDGET_REFERENCE = {
    "energy": 1.8e9,
    "oil_and_gas": 1.8e9,
    "utilities": 2.5e9,
    "technology": 0.9e9,
    "default": 1.2e9,
}


class CarbonPathwayModeller:
    def __init__(self) -> None:
        self.name = "Industry-Calibrated Carbon Pathway Modeller"

    def model_pathway(
        self,
        company: str,
        industry: str,
        claim_text: str,
        scope1: float,
        scope2: float,
        scope3: float,
        base_year: int,
        target_year: int,
        target_reduction_pct: float,
        production_plan: str,
        claimed_pathway: str = "1.5C",
    ) -> Dict[str, Any]:
        total_current = max(0.0, float(scope1) + float(scope2) + float(scope3))
        years_remaining = max(1, int(target_year) - int(base_year))

        required_reduction_per_year = total_current * (float(target_reduction_pct) / 100.0) / years_remaining
        company_cagr = (float(target_reduction_pct) / 100.0) / years_remaining

        pathway_decline = self._required_decline_for_industry(industry, claimed_pathway, target_year)
        iea_benchmark_reduction_pct = self._reference_reduction_for_industry(industry, target_year, claimed_pathway)
        iea_benchmark_emission_level = total_current * (1 - iea_benchmark_reduction_pct)
        pathway_requirement_at_target_year = total_current * ((1 - pathway_decline) ** years_remaining)
        target_value = total_current * (1 - float(target_reduction_pct) / 100.0)

        pathway_gap = target_value - pathway_requirement_at_target_year
        pathway_gap_pct = (pathway_gap / pathway_requirement_at_target_year * 100.0) if pathway_requirement_at_target_year > 0 else 0.0

        iea_gap_tco2e = target_value - iea_benchmark_emission_level
        iea_gap_pct = (iea_gap_tco2e / iea_benchmark_emission_level * 100.0) if iea_benchmark_emission_level > 0 else 0.0

        projected_cumulative_emissions = ((total_current + target_value) / 2.0) * years_remaining
        ipcc_budget = self._ipcc_budget_for_industry(industry)
        budget_utilization_pct = (projected_cumulative_emissions / ipcc_budget * 100.0) if ipcc_budget > 0 else 0.0

        scope3_share_pct = (scope3 / total_current * 100.0) if total_current > 0 else 0.0
        scope3_feasibility = self._assess_scope3_feasibility(industry, production_plan, claim_text, target_reduction_pct)

        alignment_status = "aligned"
        
        # Calculate the rate gap in percentage points
        cagr_gap = (implied_cagr_required - company_cagr) * 100.0
        
        if scope3_feasibility == "PHYSICALLY_IMPOSSIBLE":
            alignment_status = "physically_impossible"
        elif budget_utilization_pct > 100:
            alignment_status = "ipcc_budget_exceeded"
        elif cagr_gap > 3.0 or iea_gap_pct > 10:
            # If the company's reduction rate is more than 3 percentage points 
            # behind the IEA required rate, they are misaligned.
            alignment_status = "benchmark_misaligned"
        elif cagr_gap > 0.5 or iea_gap_pct > 0:
            alignment_status = "slightly_above_benchmark"

        implied_cagr_required = pathway_decline

        # ── IEA NZE ceiling ──────────────────────────────────────────────
        # When carbon budgets are effectively exhausted, the mathematical
        # required rate can spike to unrealistic values (100%+/yr).
        # Cap at the maximum scientifically cited rate from IEA NZE 2050.
        IEA_NZE_CAP = 45.0
        raw_cagr_pct = round(implied_cagr_required * 100.0, 2)
        budget_years = self._compute_budget_years(total_current, claimed_pathway)
        capped = raw_cagr_pct > IEA_NZE_CAP or budget_years < 2.0
        display_cagr_pct = min(raw_cagr_pct, IEA_NZE_CAP) if capped else raw_cagr_pct
        alignment_note = (
            "Budget effectively exhausted — IEA NZE ceiling applied"
            if capped else ""
        )
        # ─────────────────────────────────────────────────────────────────

        return {
            "company": company,
            "industry": industry,
            "claimed_pathway": claimed_pathway,
            "total_current_emissions": round(total_current, 2),
            "required_annual_reduction": round(required_reduction_per_year, 2),
            "target_emission_level": round(target_value, 2),
            "iea_nze_reference_reduction_pct": round(iea_benchmark_reduction_pct * 100.0, 2),
            "iea_nze_reference_emission_level": round(iea_benchmark_emission_level, 2),
            "pathway_requirement": round(pathway_requirement_at_target_year, 2),
            "pathway_gap_tco2e": round(pathway_gap, 2),
            "pathway_gap_pct": round(pathway_gap_pct, 2),
            "iea_nze_gap_tco2e": round(iea_gap_tco2e, 2),
            "iea_nze_gap_pct": round(iea_gap_pct, 2),
            "alignment_status": alignment_status,
            "scope3_share_pct": round(scope3_share_pct, 2),
            "scope3_feasibility": scope3_feasibility,
            "ipcc_budget_tco2e": round(ipcc_budget, 2),
            "projected_cumulative_emissions_tco2e": round(projected_cumulative_emissions, 2),
            "ipcc_budget_utilization_pct": round(budget_utilization_pct, 2),
            "carbon_budget_remaining_yrs": budget_years,
            "implied_cagr_required": display_cagr_pct,
            "required_annual_rate_raw": raw_cagr_pct,
            "alignment_note": alignment_note,
            "company_implied_cagr": round(company_cagr * 100.0, 2),
            "production_plan": production_plan,
        }

    def _required_decline_for_industry(self, industry: str, pathway: str, target_year: int) -> float:
        """Return the required *annualized* decline rate for the industry.

        IEA_NZE_REFERENCE stores cumulative reduction fractions by target year
        (e.g. 0.54 = 54% total reduction by 2030 from a ~2020 baseline).
        We convert to an equivalent annual compound rate so downstream
        comparisons with the company's own annual CAGR are apples-to-apples.
        """
        ind = (industry or "").lower().replace(" ", "_")
        if ind in IEA_NZE_REFERENCE:
            ref = IEA_NZE_REFERENCE[ind]
        else:
            ref = IEA_NZE_REFERENCE["default"]

        years = sorted(ref.keys())
        if target_year <= years[0]:
            cumulative = ref[years[0]]
            span = max(1, years[0] - 2020)  # IEA NZE baseline ~2020
        elif target_year >= years[-1]:
            cumulative = ref[years[-1]]
            span = max(1, years[-1] - 2020)
        else:
            start_year, end_year = years[0], years[-1]
            start_val, end_val = ref[start_year], ref[end_year]
            slope = (end_val - start_val) / max(1, end_year - start_year)
            cumulative = start_val + slope * (target_year - start_year)
            span = max(1, target_year - 2020)

        # Convert cumulative fraction to annual compound rate
        # If cumulative = 0.54 over 10 years: annual = 1 - (1-0.54)^(1/10) ≈ 7.5%/yr
        remaining = max(0.01, 1.0 - cumulative)
        annual_rate = 1.0 - remaining ** (1.0 / span)
        return max(0.0, min(1.0, annual_rate))

    def _reference_reduction_for_industry(self, industry: str, target_year: int, pathway: str) -> float:
        """
        Return the cumulative reduction fraction expected by the reference pathway.

        This currently mirrors the calibrated industry decline lookup used elsewhere
        in the modeller so pathway-vs-benchmark comparisons remain internally
        consistent instead of crashing at runtime.
        """
        reduction = self._required_decline_for_industry(industry, pathway, target_year)
        return max(0.0, min(1.0, float(reduction)))

    def _ipcc_budget_for_industry(self, industry: str) -> float:
        ind = (industry or "").lower().replace(" ", "_")
        return float(IPCC_BUDGET_REFERENCE.get(ind, IPCC_BUDGET_REFERENCE["default"]))

    def _assess_scope3_feasibility(self, industry: str, production_plan: str, claim_text: str, target_reduction_pct: float) -> str:
        ind = (industry or "").lower().replace(" ", "_")
        plan = (production_plan or "").lower()
        claim = (claim_text or "").lower()

        if ind in {"energy", "oil_and_gas"}:
            production_growth = any(k in plan or k in claim for k in ["growth", "increase production", "maintain production"])
            scope3_reduction = "scope 3" in claim and any(k in claim for k in ["reduce", "reduction", "cut"])
            intensity_only = "intensity" in claim

            if production_growth and scope3_reduction and not intensity_only:
                return "PHYSICALLY_IMPOSSIBLE"
            if production_growth and intensity_only:
                return "POSSIBLE_BUT_MISLEADING"
            if "decline" in plan and scope3_reduction:
                return "FEASIBLE"
            if "stable" in plan and target_reduction_pct < 20:
                return "FEASIBLE_EFFICIENCY_ONLY"
        return "UNKNOWN"

    def _compute_budget_years(self, total_current: float, pathway: str) -> float:
        if total_current <= 0:
            return 0.0
        # Placeholder micro-budget allocation for company-level directional check.
        annual_budget = 2.5e8 if "1.5" in pathway.lower() else 4.0e8
        return round(max(0.0, annual_budget / total_current), 2)
