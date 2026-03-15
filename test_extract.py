from features.esg_mismatch_detector.report_collector import fetch_latest_esg_report
from features.esg_mismatch_detector.company_resolver import resolve_company

company = resolve_company("Microsoft")
print(company)
report = fetch_latest_esg_report(company)
print("LENGTH:", len(report))
print(report[:1000])
