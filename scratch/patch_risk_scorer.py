import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'c:\Users\Mahi\major\agents\risk_scorer.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Inject industry extraction and base_esg calculation
inject_old = """        # Calculate Environmental Score
        env_positive = sum(1 for kw in environmental_keywords if kw in combined_text)"""
inject_new = """        industry = all_analyses.get("industry", "unknown")
        base_risk = self.industry_baseline_risk.get(industry, {}).get("baseline", 50)
        base_esg = 100 - base_risk

        # Calculate Environmental Score
        env_positive = sum(1 for kw in environmental_keywords if kw in combined_text)"""
content = content.replace(inject_old, inject_new)

# 2. Modify Environmental Score fallback
env_old = """        env_penalty = min(env_negative * 15, 60)
        environmental_score = 50 + (env_positive * 10) - env_penalty
        environmental_score = max(0, min(100, environmental_score))"""
env_new = """        env_penalty = min(env_negative * 15, 60)
        environmental_score = base_esg + (env_positive * 10) - env_penalty
        if env_positive == 0 and env_negative == 0:
            environmental_score = float(base_esg - 5) if not sg_adequacy.get("overall_ready", False) else float(base_esg + 5)
        environmental_score = max(0, min(100, environmental_score))"""
content = content.replace(env_old, env_new)

# 3. Modify Social Score fallback
soc_old = """        if soc_positive == 0 and soc_negative == 0 and not social_lane.get("track_scores"):
            social_score = 35.0 if not sg_adequacy.get("social", {}).get("is_adequate", False) else 45.0"""
soc_new = """        if soc_positive == 0 and soc_negative == 0 and not social_lane.get("track_scores"):
            # Intelligent fallback scoring based on sector baseline
            social_score = float(base_esg - 5) if not sg_adequacy.get("social", {}).get("is_adequate", False) else float(base_esg + 5)"""
content = content.replace(soc_old, soc_new)

# 4. Modify Governance Score fallback
gov_old = """        if gov_positive == 0 and gov_negative == 0 and not governance_lane.get("track_scores"):
            governance_score = 38.0 if not sg_adequacy.get("governance", {}).get("is_adequate", False) else 48.0"""
gov_new = """        if gov_positive == 0 and gov_negative == 0 and not governance_lane.get("track_scores"):
            # Intelligent fallback scoring based on sector baseline
            governance_score = float(base_esg - 5) if not sg_adequacy.get("governance", {}).get("is_adequate", False) else float(base_esg + 5)"""
content = content.replace(gov_old, gov_new)

# 5. Sector-Aware proxy adjustments
# In RiskScorer._resolve_materiality_profile
mat_old = """        if social_hits >= 3 and industry in {"consumer_goods", "food_beverage", "banking"}:
            weights["S"] = weights.get("S", 0.30) + 0.03
            notes.append("Social topic density increased Social weight.")"""

mat_new = """        if social_hits >= 3 and industry in {"consumer_goods", "food_beverage", "banking"}:
            weights["S"] = weights.get("S", 0.30) + 0.03
            notes.append("Social topic density increased Social weight.")

        # Sector-Aware Proxy adjustments for low-disclosure/banks/tech
        if industry == "banking":
            if any(kw in combined_text for kw in ["financed emissions", "fossil fuel financing", "climate finance"]):
                weights["E"] = weights.get("E", 0.35) + 0.05
                notes.append("Bank's financed emissions proxy detected.")
        elif industry in {"technology", "software", "e-commerce"}:
            if any(kw in combined_text for kw in ["logistics", "supply chain", "data center", "renewable energy usage"]):
                weights["E"] = weights.get("E", 0.35) + 0.04
                notes.append("Tech/Logistics proxy emissions detected.")"""

content = content.replace(mat_old, mat_new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("risk_scorer.py patched successfully")
