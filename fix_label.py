with open('core/pillar_factors_builder.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace(
    'if "unverified" in ds or "no relevant disclosure" in ds:\n            raw["data_quality"] = "Unverified"',
    'if "no relevant disclosure" in ds:\n            raw["data_quality"] = "Limited Disclosure"\n        elif "unverified" in ds:\n            raw["data_quality"] = "Unverified"'
)
with open('core/pillar_factors_builder.py', 'w', encoding='utf-8') as f:
    f.write(c)
