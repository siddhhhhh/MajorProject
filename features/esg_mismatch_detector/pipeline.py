from typing import Dict
import json
import os
import sys
import time

# Ensure project root is accessible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from features.esg_mismatch_detector.company_resolver import resolve_company
from features.esg_mismatch_detector.report_collector import fetch_latest_esg_report
from features.esg_mismatch_detector.promise_extractor import extract_promises
from features.esg_mismatch_detector.evidence_collector import collect_external_evidence
from features.esg_mismatch_detector.comparison_engine import compare_promises_vs_actual

# ==============================
# Cache Configuration
# ==============================

CACHE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../cache/esg_analysis")
)

CACHE_TTL = 24 * 60 * 60  # 24 hours

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def _get_cache_path(company_name: str) -> str:
    normalized = company_name.lower().replace(" ", "_").strip()
    filename = f"{normalized}.json"
    return os.path.join(CACHE_DIR, filename)


def load_cached_result(company_name: str) -> Dict | None:
    cache_path = _get_cache_path(company_name)

    if not os.path.exists(cache_path):
        return None

    try:
        file_age = time.time() - os.path.getmtime(cache_path)

        if file_age > CACHE_TTL:
            print("🔄 Cache expired. Regenerating analysis...")
            return None

        with open(cache_path, "r", encoding="utf-8") as f:
            print("⚡ Using cached ESG analysis result.")
            return json.load(f)

    except Exception as e:
        print(f"⚠️ Cache read error: {e}")
        return None


def save_cached_result(company_name: str, result: Dict):
    cache_path = _get_cache_path(company_name)

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"💾 Cached result saved → {cache_path}")

    except Exception as e:
        print(f"⚠️ Could not save cache: {e}")


# ==============================
# Main Pipeline
# ==============================

def analyze_company_esg(company_name: str) -> Dict:
    """
    Main ESG mismatch detection pipeline.
    """

    cache_key = company_name.lower().strip()

    # ------------------------------
    # Cache Check
    # ------------------------------
    cached_result = load_cached_result(cache_key)
    if cached_result:
        return cached_result

    print(f"🔍 Starting ESG analysis for: {company_name}")

    # ------------------------------
    # Resolve Company
    # ------------------------------
    company = resolve_company(company_name)

    # ------------------------------
    # Fetch ESG Report
    # ------------------------------
    print("📥 Fetching ESG report...")
    report_text = fetch_latest_esg_report(company)

    if not report_text:
        result = {
            "company": company["company"],
            "status": "report unavailable",
            "reason": "Could not retrieve ESG report"
        }

        save_cached_result(cache_key, result)
        return result

    # ------------------------------
    # Extract ESG Promises
    # ------------------------------
    print("🤖 Extracting promises...")
    promises = extract_promises(report_text, company_name)

    print(f"✅ Found {len(promises)} promises.")

    # ------------------------------
    # Collect Evidence
    # ------------------------------
    print("🌍 Collecting evidence...")
    actual_data = collect_external_evidence(company["company"])

    print(f"✅ Found {len(actual_data)} pieces of evidence.")

    # ------------------------------
    # Early Exit if No Data
    # ------------------------------
    if not actual_data and not promises:
        result = {
            "company": company["company"],
            "status": "data unavailable",
            "reason": "No verified ESG data retrieved"
        }

        save_cached_result(cache_key, result)
        return result

    # ------------------------------
    # Compare Promises vs Actuals
    # ------------------------------
    print("⚖️ Comparing promises vs actuals...")
    comparisons = compare_promises_vs_actual(promises, actual_data)

    print("🚩 Detecting mismatches...")

    mismatches = [c for c in comparisons if c.get("mismatch_type")]

    if len(mismatches) == 0:
        if not actual_data:
            print("🟡 Insufficient external verification. Relying only on company reports is unsafe.")
            overall_risk = "Unknown"
            summary = "Insufficient external verification. Requires verified data."
        else:
            print("🟢 No mismatch found for this company based on verified data.")
            overall_risk = "Low"
            summary = "No mismatch found for this company (verified against external sources)."
    else:
        print(f"🔴 Found {len(mismatches)} mismatches/red flags.")

        severe = any(
            m.get("risk_score") in ["High", "Severe", "Violation Detected"] for m in mismatches
        )

        overall_risk = "High" if severe else "Moderate"

        summary = f"Analysis completed. Detected {len(mismatches)} contradictions or risk flags."

    # ------------------------------
    # Final Result
    # ------------------------------
    # Sort evaluation into future vs completed promises
    future_promises = [c for c in comparisons if c.get("category") == "future_promise"]
    completed_promises = [c for c in comparisons if c.get("category") == "completed_promise" and c.get("mismatch_type") is not None]
    
    # User requested friendly formatting
    formatted_future = []
    for fp in future_promises:
         # Explicitly highlight failed future promises if a regulatory violation ruins their credibility
         if fp.get("status") == "Violation Detected":
              completed_promises.append(fp)
              continue
              
         # Create a clear, easily understood pledge string
         metric_name = fp.get('metric', '').replace('_', ' ').title()
         target = fp.get('target')
         unit = fp.get('unit', '')
         deadline = fp.get('deadline')
         baseline = fp.get('baseline')
         scope = fp.get('scope')

         parts = []
         if target is not None:
             parts.append(f"{target} {unit}")
         parts.append(f"of {metric_name}")
         if scope:
             parts.append(f"({scope})")
         if baseline:
             parts.append(f"from a {baseline} baseline")
         if deadline:
             parts.append(f"by {deadline}")

         pledge_str = " ".join(parts).strip()
         if pledge_str:
             pledge_str = "Commitment to reach " + pledge_str
         else:
             pledge_str = f"Commitment to improve {metric_name}"
             
         # Improve Status Trend and Progress logic
         trend = fp.get("trend", "unknown")
         status = fp.get("status", "Unknown")
         
         if not fp.get("mismatch_source") and not actual_data:
             status_display = "Insufficient Evidence"
             progress_display = "Awaiting verified external data"
         elif trend.lower() == "unknown":
             if fp.get("actual"):
                 status_display = "In Progress / Tracking"
                 progress_display = f"Monitoring metric: {fp.get('actual')}"
             else:
                 status_display = "Under Verification"
                 progress_display = "Evaluating credible sources"
         else:
             status_display = status
             progress_display = trend
             
         formatted_future.append({
             "Pledge": pledge_str,
             "Status Trend": status_display,
             "Progress/Trend": progress_display,
             "Measures Being Taken": fp.get("measures_taking") or "Not explicitly stated.",
             "Source of Measure": fp.get("mismatch_source") or "Official ESG Report"
         })
         
    formatted_mismatches = []
    for cp in completed_promises:
         metric_name = cp.get('metric', '').replace('_', ' ').title()
         
         actual_perf = str(cp.get('actual', 'N/A'))
         # Provide readable tier-labels instead of default NON-COMPLIANT
         verdict_label = cp.get('status', 'Unverified Issue').upper()
         
         formatted_mismatches.append({
             "Failed Pledge": metric_name,
             "Expected Target": f"{cp.get('target', 'N/A')} {cp.get('unit', '')}".strip() if cp.get('target') else "Categorical Goal",
             "Flagged Status": f"{verdict_label}: {actual_perf}",
             "Risk Level": cp.get("risk_score", "Unknown"),
             "Confidence Score": cp.get("confidence", "Medium"),
             "Evidence Source": cp.get("mismatch_source", "Unknown Source"),
             "Verified Quote": cp.get("mismatch_quote", "No quote available")
         })
    
    result = {
        "Company Analyzed": company["company"],
        "Overall Greenwashing Risk": overall_risk,
        "Executive Summary": summary,
        "1. Future Commitments & Progress": formatted_future,
        "2. Past Promise-Implementation Gaps (Mismatches)": formatted_mismatches if formatted_mismatches else ["No historical implementation gaps or regulatory mismatches detected."]
    }

    # ------------------------------
    # Save Cache
    # ------------------------------
    save_cached_result(cache_key, result)

    # ------------------------------
    # Save Log Output
    # ------------------------------
    os.makedirs("data", exist_ok=True)

    output_path = os.path.join("data", "esg_mismatch_results.json")

    try:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")

        print(f"💾 Results saved to {output_path}")

    except Exception as e:
        print(f"⚠️ Could not save results: {e}")

    return result


# ==============================
# CLI ENTRYPOINT
# ==============================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze ESG promise vs reality for any company"
    )

    parser.add_argument("company", help="Company name")

    args = parser.parse_args()

    result = analyze_company_esg(args.company)

    print("\n" + "=" * 50)
    print(json.dumps(result, indent=2))
    print("=" * 50)