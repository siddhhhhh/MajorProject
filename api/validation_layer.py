import re
from typing import Dict, Any
from api.models import ESGReport, Contradiction

def apply_final_validation(report: ESGReport, raw: Dict[str, Any]) -> ESGReport:
    """
    FINAL ESG VALIDATION LAYER
    Applies strict ESG rules to ensure factual accuracy without degrading report quality.
    """
    modified = False

    # Collect all evidence text for easier searching
    all_evidence_text = ""
    for ev in report.evidence:
        all_evidence_text += (ev.excerpt + " " + ev.source_name + " ").lower()

    # ========================================
    # SECTION 1: CARBON DATA VALIDATION
    # ========================================
    if not hasattr(report, 'validation_notes') or report.validation_notes is None:
        report.validation_notes = []

    # --- Scope 2 ---
    has_market = "market-based" in all_evidence_text or "market" in all_evidence_text
    has_location = "location-based" in all_evidence_text or "location" in all_evidence_text
    
    if (has_market and not has_location) or (has_location and not has_market) or report.carbon.scope2_status == "PARTIAL":
        report.carbon.scope2_status = "PARTIAL"
        report.validation_notes.append("ERROR: Scope 2 improperly aggregated")
        modified = True
    elif has_market and has_location:
        report.carbon.scope2_status = "FULL"
        modified = True
    elif report.carbon.scope2 > 0:
        report.carbon.scope2_status = "PARTIAL"
        report.validation_notes.append("ERROR: Scope 2 improperly aggregated")
        modified = True
    elif report.carbon.scope2 == 0.0:
        report.validation_notes.append("WARNING: Scope 2 May exist elsewhere in report")
        modified = True

    # --- Scope 3 ---
    has_financed = "financed emissions" in all_evidence_text
    has_sector_data = any(x in all_evidence_text for x in ["oil", "gas", "power", "aviation", "auto", "selected categories"])
    is_explicitly_total = "total scope 3" in all_evidence_text or "aggregated across value chain" in all_evidence_text
    
    if has_financed or has_sector_data or report.carbon.scope3_status == "PARTIAL":
        report.carbon.scope3_status = "PARTIAL"
        report.validation_notes.append("ERROR: Scope 3 is partial, not total")
        modified = True
        
    if is_explicitly_total and report.carbon.scope3_status != "PARTIAL":
        report.carbon.scope3_status = "FULL"
        modified = True
        
    # Sanity Check (CRITICAL)
    s12 = report.carbon.scope1 + report.carbon.scope2
    if s12 > 0 and report.carbon.scope3 > (100 * s12) and not is_explicitly_total:
        report.carbon.scope3_status = "PARTIAL"
        report.validation_notes.append("WARNING: Disproportionate Scope 3 likely partial")
        modified = True

    # Invalid Total Emissions Calculation
    if report.carbon.scope3_status == "PARTIAL":
        report.carbon.total = 0.0
        report.validation_notes.append("ERROR: Invalid total due to incomplete Scope 3")
        modified = True

    # Missing Scope Check
    if report.carbon.scope1 == 0.0:
        report.validation_notes.append("WARNING: Scope 1 May exist elsewhere in report")
        modified = True

    # ========================================
    # SECTION 2: TARGET CLAIM VALIDATION
    # ========================================
    claim_lower = report.claim.lower()
    is_quant = bool(re.search(r'\d+%|\byear\b|\bbaseline\b|\b20\d\d\b', claim_lower))
    
    if is_quant:
        if report.temporal_risk == "HIGH" or report.claim_trend == "DEGRADING":
            report.carbon.target_status = "OFF_TRACK"
            modified = True
            
        if "replaced with" in all_evidence_text and "intensity" in all_evidence_text:
            report.carbon.target_status = "ABANDONED"
            modified = True
        elif "no longer" in all_evidence_text and "target" in all_evidence_text:
            report.carbon.target_status = "ABANDONED"
            modified = True

    # ========================================
    # SECTION 3: CONTRADICTION CORRECTION
    # ========================================
    contradiction_found = False
    
    if report.carbon.target_status in ["OFF_TRACK", "ABANDONED"]:
        contradiction_found = True
        
    if "reduction" in claim_lower and ("flat" in all_evidence_text or "increasing" in all_evidence_text):
        contradiction_found = True
        
    if "intensity" in all_evidence_text and "absolute" in claim_lower:
        contradiction_found = True
        
    if contradiction_found:
        report.contradiction_flag = True
        modified = True
        
        # ONLY override if high-confidence evidence exists
        has_high_conf = any(e.credibility >= 0.8 for e in report.evidence)
        if has_high_conf:
            existing_contra = any("validation" in c.source.lower() for c in report.contradictions)
            if not existing_contra:
                report.contradictions.append(Contradiction(
                    id=f"val_contra_{len(report.contradictions)+1}",
                    severity="HIGH",
                    claim_text=report.claim,
                    evidence_text="Validation layer identified a contradiction based on target status, flat/increasing emissions, or intensity vs absolute metrics.",
                    source="ESG Validation Layer",
                    impact="Increases greenwashing risk score"
                ))

    # ========================================
    # SECTION 4: EVIDENCE QUALITY SAFEGUARD
    # ========================================
    tier_45_count = sum(1 for ev in report.evidence if any(x in ev.source_type.lower() for x in ["news", "web", "article", "blog"]))
    total_ev = len(report.evidence)
    
    if total_ev > 0 and (tier_45_count / total_ev) > 0.8:
        report.confidence = max(0.0, report.confidence - 5.0)
        modified = True

    # ========================================
    # SECTION 5: ABSTENTION CONTROL
    # ========================================
    if is_quant and total_ev > 0:
        if report.carbon.target_status == "UNKNOWN":
            report.carbon.target_status = "VERIFIED" if report.temporal_risk == "LOW" else "PARTIAL"
            modified = True

    # ========================================
    # SECTION 6: NON-DESTRUCTIVE OUTPUT POLICY
    # ========================================
    if modified:
        if not report.validation_notes:
            report.validation_notes = []
        report.validation_notes.append("Data validation adjustment applied based on emissions classification rules.")

    return report
