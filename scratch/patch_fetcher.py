import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'c:\Users\Mahi\major\utils\company_report_fetcher.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

patterns_old = """        self.report_patterns = {
            "annual_report": [
                r"annual.?report", r"integrated.?report", r"ar.?\d{4}",
                r"\d{4}.?annual", r"yearly.?report"
            ],
            "sustainability_report": [
                r"sustainab", r"esg.?report", r"csr.?report", r"corporate.?social",
                r"environmental.?report", r"climate.?report", r"green.?report"
            ],
            "brsr_report": [
                r"brsr", r"business.?responsibility", r"sustainability.?reporting",
                r"sebi.?brsr"
            ],
            "financial_report": [
                r"financial.?statement", r"quarterly.?report", r"q\d.?\d{4}",
                r"earnings", r"10-k", r"10-q", r"20-f"
            ]
        }"""
patterns_new = """        self.report_patterns = {
            "annual_report": [
                r"annual.?report", r"integrated.?report", r"ar.?\d{4}",
                r"\d{4}.?annual", r"yearly.?report", r"10-k", r"filings", r"proxy", r"annual"
            ],
            "sustainability_report": [
                r"sustainab", r"esg", r"csr", r"corporate.?social",
                r"environmental", r"climate", r"green", r"impact", r"responsibility"
            ],
            "brsr_report": [
                r"brsr", r"business.?responsibility", r"sustainability.?reporting",
                r"sebi.?brsr"
            ],
            "financial_report": [
                r"financial", r"quarterly", r"q\d",
                r"earnings", r"10-k", r"10-q", r"20-f"
            ]
        }"""
content = content.replace(patterns_old, patterns_new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("company_report_fetcher.py patched successfully")
