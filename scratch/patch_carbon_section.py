import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'c:\Users\Mahi\major\core\professional_report_generator.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

scope3_old = """        else:
            _scope3_stmt = (
                "Scope 3 emissions are not disclosed. For most industries, value-chain emissions "
                "(Scope 3) constitute the largest share of the carbon footprint; "
                "omission significantly limits the credibility of any net-zero claim."
            )"""
scope3_new = """        else:
            if industry_label in {"banking", "financial services"}:
                _proxy_note = "As a financial institution, Scope 3 (Category 15: Financed Emissions) is the dominant risk factor. Missing this data indicates critical transition risk exposure."
            elif industry_label in {"technology", "software", "e-commerce", "retail"}:
                _proxy_note = "For tech/retail, Scope 3 (purchased goods, logistics, energy usage) is the dominant footprint. Using intensity proxies suggests high supply chain exposure."
            else:
                _proxy_note = "For most industries, value-chain emissions (Scope 3) constitute the largest share of the carbon footprint."

            _scope3_stmt = (
                f"Scope 3 emissions are not disclosed. {_proxy_note} "
                "Omission significantly limits the credibility of any net-zero claim."
            )"""
content = content.replace(scope3_old, scope3_new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("professional_report_generator.py carbon section patched successfully")
