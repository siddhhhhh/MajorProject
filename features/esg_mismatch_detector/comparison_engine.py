from typing import List, Dict
import datetime

def compare_promises_vs_actual(promises: List[Dict], actual_data: List[Dict]) -> List[Dict]:
    """
    Compare promised targets vs actual verified data.
    """
    comparisons = []
    
    # Deduplicate promises based on metric + deadline + target
    unique_promises = {}
    for p in promises:
        key = (p.get("metric"), p.get("deadline"), p.get("target"))
        if key not in unique_promises:
            unique_promises[key] = p
    promises_deduped = list(unique_promises.values())
    
    current_year = datetime.datetime.now().year
    
    METRIC_ALIASES = {
        "carbon_emissions": ["co2", "emissions", "ghg", "carbon", "carbon emissions change", "net zero emissions", "carbon negative", "carbon emissions progress", "scope 1", "scope 2", "scope 3"],
        "renewable_energy": ["renewable electricity", "clean energy", "renewable"],
        "water_usage": ["water", "water positive", "water consumption", "water neutrality"],
        "waste_management": ["waste", "zero waste", "waste reduction", "waste diversion", "circular economy"]
    }
    
    processed_events = set()
    
    for promise in promises_deduped:
        metric = promise.get("metric", "").lower()
        target = promise.get("target")
        deadline = promise.get("deadline")
        
        # Step 2: Check Promise Deadline before running mismatch analysis
        try:
            deadline_int = int(deadline) if deadline else None
        except:
            deadline_int = None
            
        category = "unknown"
        if deadline_int:
            if deadline_int <= current_year:
                category = "completed_promise"
            else:
                category = "future_promise"
        else:
             category = "completed_promise" # Assume completed if no deadline is specified to enforce strict checking

        # Determine base alias group for the promise metric
        search_terms = [metric]
        for base, aliases in METRIC_ALIASES.items():
            if metric in aliases or metric == base:
                search_terms.extend(aliases)
                search_terms.append(base)
                break
                
        actuals_for_metric = []
        for a in actual_data:
            a_metric = a.get("metric", "").lower()
            if any(term in a_metric for term in search_terms) or any(term in metric for term in [a_metric]):
                actuals_for_metric.append(a)
        
        actual = actuals_for_metric[0] if actuals_for_metric else None
        actual_value = actual.get("value") if actual else None
        
        gap = None
        progress = None
        risk_score = None
        status = None
        regulatory_violation = False
        mismatch_type = None
        mismatch_explanation = None
        trend = "unknown"

        if actual:
            actual_source = actual.get("source", "").lower()
            # Use explicit tag from evidence collector first, then fallback to quote checking
            if actual.get("is_regulatory_violation") == True:
                 regulatory_violation = True
            
            if any(reg in actual_source for reg in ["sec", "epa", "eu commission", "regulator", "government"]):
                actual_quote = actual.get("supporting_quote", "").lower()
                if any(crime in actual_quote for crime in ["violation", "fraud", "exceeding", "illegal", "investigation"]):
                    regulatory_violation = True
        
        event_category = actual.get("event_category", "Policy Gap / Performance Flag") if actual else None

        # Process Qualitative Regulatory Violations directly even without a numerical actual_value
        if regulatory_violation:
            if event_category == "Legal Dispute Overturned":
                 status = "Monitored (Overturned Dispute)"
                 mismatch_type = "Resolved Allegation"
                 risk_score = "Low"
                 mismatch_explanation = "A dispute occurred but ruling was overturned or appeal won."
                 regulatory_violation = False
            else:
                 status = "Violation Detected" if event_category in ["Confirmed Violation", "Policy Gap / Performance Flag"] else "Risk Flagged"
                 mismatch_type = "Regulatory/Legal Event"
                 
                 # Dynamically assign severity based on the tier
                 if event_category == "Confirmed Violation":
                     risk_score = "Severe"
                 elif event_category == "Allegation":
                     risk_score = "Moderate"
                 elif event_category == "Legal Dispute":
                     risk_score = "High"
                 else:
                     risk_score = "High" 
                 mismatch_explanation = f"Event recorded: {event_category}. Further investigation required."
                 
            # Set to valid placeholder so it successfully triggers mismatch logic lower down
            if actual_value is None:
                actual_value = event_category

        if actual_value is not None and not regulatory_violation:
            # Check string based absolute goals (like 'carbon negative') vs reality (+29.1% increase)
            if "reduction" in metric or "negative" in str(target).lower() or "change" in metric or "neutral" in metric or "zero" in metric or "progress" in metric or "emissions" in metric:
                try:
                    target_f = float(target) if target is not None else 100
                    actual_f = float(actual_value)
                    
                    # - values mean increase in actual logic, so + actual_f means emissions increased. we handle this in gap calculation.
                    # if actual_f > 0, emissions increased
                    if actual_f > 0:
                        trend = "worsening"
                    elif actual_f < 0:
                        trend = "improving"
                    elif actual_f == 0:
                        trend = "stable"
                        
                    if category == "completed_promise":
                        # For completed promises, we calculate strict gap and mismatch
                        if actual_f > 0: # emissions increased!
                            gap = target_f + actual_f # e.g. target 30% reduction, actual 5% increase -> missed by 35%
                            mismatch_type = "Missed Target"
                            mismatch_explanation = f"Target was {target_f}% reduction, but actual performance showed an increase of {actual_f}%."
                        else: # emissions decreased
                            gap = target_f - abs(actual_f) # e.g target 30% reduction, actual 20% reduction -> missed by 10%
                            if gap > 0:
                                mismatch_type = "Missed Target"
                                mismatch_explanation = f"Target was {target_f}% reduction, but actual reduction was {abs(actual_f)}%."

                        if gap is not None:
                            if gap <= 0:
                                risk_score = "Low"
                                status = "Achieved"
                                mismatch_type = None
                                mismatch_explanation = None
                            else:
                                risk_score = "Moderate" if gap <= 30 else ("High" if gap <= 70 else "Severe")
                                status = "Missed Minimum Targets"
                    elif category == "future_promise":
                        # Step 4: Monitoring for Future Promises
                        status = "In Progress"
                        if trend == "worsening":
                            risk_score = "Moderate"
                            mismatch_type = "Negative Trend"
                            mismatch_explanation = f"Company promised {metric} by {deadline}, but current trend is worsening (emissions increased by {actual_f}%)."
                        else:
                            risk_score = "Low"
                            
                    # Always elevate regulatory violations    
                    if regulatory_violation:
                        risk_score = "Severe"
                        mismatch_type = "Regulatory Violation"
                        mismatch_explanation = "Regulatory investigation or violation found contradicting sustainability claims."
                        
                except Exception as e:
                    pass
            elif "renewable" in metric or "energy" in metric:
                try:
                    target_f = float(target) if target is not None else 100
                    actual_f = float(actual_value)
                    
                    if actual_f > 0: # assuming actual_f is the % renewable energy achieved
                        trend = "improving"
                    elif actual_f < 0:
                        trend = "worsening"
                    elif actual_f == 0:
                        trend = "stable"
                        
                    if category == "completed_promise":
                        gap = target_f - actual_f
                        progress = actual_f
                        
                        if gap <= 0:
                            risk_score = "Low"
                            status = "Achieved"
                        else:
                            risk_score = "Moderate" if gap <= 30 else ("High" if gap <= 70 else "Severe")
                            status = "Missed Minimum Targets"
                            mismatch_type = "Missed Target"
                            mismatch_explanation = f"Target was {target_f}%, but actual achieved was {actual_f}%."
                    elif category == "future_promise":
                        status = "In Progress"
                        if trend == "worsening":
                             risk_score = "Moderate"
                             mismatch_type = "Negative Trend"
                             mismatch_explanation = f"Company promised {target}% renewable by {deadline}, but current trend is worsening."
                        else:
                             risk_score = "Low"
                        
                except Exception as e:
                    pass

        # Handle Timeline and Missing Data
        if category == "future_promise" and status is None:
             status = "In Progress"
             risk_score = "Low" 

        if actual_value is None and not regulatory_violation:
            if category == "completed_promise":
                status = "Unverified (Missing Data)"
            else:
                status = "Monitoring"
            risk_score = "Unknown"
            trend = "unknown"
            
        # Add Confidence metric loosely mapped from source severity / score
        eval_conf = "Medium"
        if actual:
             score = actual.get("confidence_score", 3)
             if score >= 5 and event_category == "Confirmed Violation":
                  eval_conf = "Very High (Regulatory Verdict)"
             elif score >= 5:
                  eval_conf = "High (Government Tier)"
             elif event_category == "Allegation":
                  eval_conf = "Low (Pending Investigation)"
             elif score == 4:
                  eval_conf = "Medium-High (Trusted Entity)"
            
        # Clean up output fields to be easily readable
        mismatch_source = actual.get("source") if actual and mismatch_type else None
        mismatch_quote = actual.get("supporting_quote") if actual and mismatch_type else None

        if mismatch_type and mismatch_source:
             event_key = f"{mismatch_source}_{mismatch_type}"
             if event_key in processed_events:
                 continue
             processed_events.add(event_key)
             
        comparisons.append({
            "metric": metric,
            "target": target,
            "unit": promise.get("unit"),
            "baseline": promise.get("baseline"),
            "scope": promise.get("scope"),
            "deadline": deadline,
            "category": category,
            "trend": trend,
            "gap": gap,
            "risk_score": risk_score,
            "status": status,
            "actual": actual_value,
            "measures_taking": promise.get("measures_taking"),
            "source": promise.get("source"),
            "mismatch_type": mismatch_type,
            "mismatch_explanation": mismatch_explanation,
            "mismatch_source": mismatch_source,
            "mismatch_quote": mismatch_quote,
            "confidence": eval_conf
        })

    return comparisons
