import json
import re
from collections import deque
from pathlib import Path

report_candidates = sorted(Path("reports").glob("ESG_Report_Orsted_*.json"), key=lambda p: p.stat().st_mtime)
if not report_candidates:
    raise SystemExit("No Orsted report found under reports/")

report_path = report_candidates[-1]
with report_path.open(encoding="utf-8") as fh:
    data = json.load(fh)

blob = json.dumps(data)
urls = re.findall(r"https?://[^\"\s]+", blob)

has_web_archive = any("web.archive.org" in u for u in urls)
has_reuters_or_bloomberg = any(("reuters.com" in u or "bloomberg.com" in u) for u in urls)
has_cdp = any("cdp" in u.lower() for u in urls) or ("CDP" in blob)

queue = deque([data])
full_text_coverage_values = []
carbon_data_nodes = []

while queue:
    node = queue.popleft()
    if isinstance(node, dict):
        if "full_text_coverage" in node:
            full_text_coverage_values.append(node.get("full_text_coverage"))
        if "carbon_data" in node:
            carbon_data_nodes.append(node.get("carbon_data"))
        for value in node.values():
            queue.append(value)
    elif isinstance(node, list):
        queue.extend(node)

carbon_non_null = False
for item in carbon_data_nodes:
    if not isinstance(item, dict):
        continue
    for key in (
        "scope_1_emissions_tco2e",
        "scope_2_emissions_tco2e",
        "scope_3_emissions_tco2e",
        "scope1",
        "scope2",
        "scope3",
    ):
        value = item.get(key)
        if isinstance(value, (int, float)) and value != 0:
            carbon_non_null = True

print("report", report_path)
print("total_urls", len(urls))
print("has_web_archive", has_web_archive)
print("has_reuters_or_bloomberg", has_reuters_or_bloomberg)
print("has_cdp", has_cdp)
print("full_text_coverage_values", full_text_coverage_values[:10])
print("carbon_non_null", carbon_non_null)
