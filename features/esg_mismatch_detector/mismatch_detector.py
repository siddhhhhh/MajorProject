from typing import List, Dict

def detect_mismatches(comparisons: List[Dict]) -> List[Dict]:
    """
    Detect mismatches and red flags in ESG promises vs actuals based on strict rules.
    """
    mismatches = []
    
    for comp in comparisons:
        metric = comp.get("metric", "Unknown metric")
        gap = comp.get("gap")
        target = comp.get("target")
        actual = comp.get("actual")
        unit = comp.get("unit", "")
        risk_score = comp.get("risk_score", "Unknown")
        mismatch_type = comp.get("mismatch_type")
        mismatch_explanation = comp.get("mismatch_explanation")
        
        # New format
        if mismatch_type:
            mismatches.append({
                "type": mismatch_type,
                "gap": gap,
                "explanation": mismatch_explanation
            })
            continue

        # Old format for backwards compatibility
        if actual == "Regulatory Violation":
            mismatches.append({
                "issue": f"{str(metric).title()} marketed under false pretenses or exceeded legal limits",
                "target": f"{target}{unit} (Compliance)",
                "actual": "Regulatory Violation (Investigation)",
                "gap": "Deceptive Practice / Violation",
                "risk_level": "High",
                "evidence": {
                    "promise_quote": comp.get("promise_source", ""),
                    "reality_source": comp.get("actual_source", ""),
                    "reality_quote": comp.get("actual_quote", "")
                }
            })
            continue

        if risk_score == "Low" and gap is not None and gap <= 0:
            # We matched or exceeded the target (e.g. 100% renewables achieved)
            continue
        
        # Determine mismatch
        if gap is not None and gap > 10:
             # handle floats cleanly
             target_str = f"{target}{unit}"
             actual_str = f"{gap:.1f}{unit}"
             mismatches.append({
                "issue": f"Massive gap in {str(metric).title()}: Target vs Reality diverging significantly.",
                "target": f"{target}{unit} (Reduction/Goal)",
                "actual": f"Moved backwards or missed by {gap:.1f}{unit} (e.g., 29.1% Increase vs 50% decrease target)",
                "gap": f"{gap:.1f}{unit}",
                "risk_level": risk_score,
                "evidence": {
                    "promise_quote": comp.get("promise_source"),
                    "reality_source": comp.get("actual_source"),
                    "reality_quote": comp.get("actual_quote")
                }
            })
        elif actual is None:
            # Missing actual data for a promise
            mismatches.append({
                "issue": f"No actual evidence found in primary docs to support {metric} promise",
                "target": f"{target}{unit}" if target else "Unknown",
                "actual": "None",
                "gap": "N/A",
                "risk_level": "Moderate",  # Missing data is moderate risk
                "evidence": {
                     "promise_quote": comp.get("promise_source")
                }
            })
            
    return mismatches
