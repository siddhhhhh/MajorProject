import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'c:\Users\Mahi\major\core\professional_report_generator.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Claim Recognition Fix
claim_old = "section5.append(f\"  Net-Zero Target:      {carbon.get('net_zero_target') or 'None declared'}\")"
claim_new = """_nz_target = carbon.get('net_zero_target')
        if not _nz_target or _nz_target.lower() in ("none", "none declared", "not available"):
            _nz_target = "Claim identified externally but not validated in extracted disclosures"
        section5.append(f"  Net-Zero Target:      {_nz_target}")"""
content = content.replace(claim_old, claim_new)

# 2. Data Availability Layer
# Add data coverage block
coverage_calc_old = "verdict_justification = []"
coverage_calc_new = """verdict_justification = []
        
        # Calculate DATA COVERAGE
        evidence_count = len(v.get('citations', []))
        carbon_output = v.get("agents", {}).get("carbon_extractor", {}).get("output", {})
        scope3_val = carbon_output.get("scope3_emissions", {}).get("value")
        if evidence_count >= 10 and scope3_val:
            data_coverage = "HIGH"
        elif evidence_count >= 5:
            data_coverage = "MODERATE"
        else:
            data_coverage = "LOW"
            
        data_coverage_str = f"  Data Coverage:            {data_coverage}"
        if data_coverage == "LOW":
            data_coverage_str += " (Results are based on limited disclosure and external signals)"
"""
content = content.replace(coverage_calc_old, coverage_calc_new)

# Insert it into the verdict block
cover_old = """f"  Confidence:               {v['confidence_pct']:.1f}%","""
cover_new = """f"  Confidence:               {v['confidence_pct']:.1f}%",
                data_coverage_str,"""
content = content.replace(cover_old, cover_new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("professional_report_generator.py patched successfully")
