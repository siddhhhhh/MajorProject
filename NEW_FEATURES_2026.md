# ESG Greenwashing Detection System - New Features (2026 Enterprise Edition)

## Overview
This document covers the new enterprise-grade features added to the ESG Greenwashing Detection System, with special focus on Indian enterprise support.

---

## 🌍 1. Scope 1-3 Carbon Extractor Agent

**File:** `agents/carbon_extractor.py`

### Purpose
Extracts and validates carbon emissions data from evidence, aligned with GHG Protocol and SEBI BRSR requirements.

### Features
- **Scope 1 Extraction:** Direct emissions from owned/controlled sources
- **Scope 2 Extraction:** Indirect emissions from purchased energy (location-based & market-based)
- **Scope 3 Extraction:** All 15 GHG Protocol categories
- **Indian Grid Emission Factor:** Uses CEA 2025 factor (0.71 tCO2/MWh)
- **SEBI BRSR Compliance Check:** Validates against BRSR mandatory disclosures
- **Red Flag Detection:** Identifies carbon accounting inconsistencies

### Usage
```python
from agents.carbon_extractor import get_carbon_extractor

extractor = get_carbon_extractor()
result = extractor.extract_carbon_data(
    company="Reliance Industries",
    evidence=evidence_list,
    claim=claim_dict
)
```

### Output
```json
{
  "emissions": {
    "scope1": {"value": 10000, "unit": "tCO2e"},
    "scope2": {"value": 5000, "unit": "tCO2e", "methodology": "market-based"},
    "scope3": {"total": 50000, "categories": {...}}
  },
  "brsr_compliance": {...},
  "red_flags": [...]
}
```

---

## 🤖 2. ClimateBERT NLP Integration

**File:** `ml_models/climatebert_analyzer.py`

### Purpose
State-of-the-art transformer model fine-tuned on climate text for superior greenwashing detection.

### Models Used (HuggingFace)
- `climatebert/distilroberta-base-climate-detector` - Climate relevance
- `climatebert/environmental-claims` - Claim detection
- `climatebert/distilroberta-base-climate-f` - TCFD classification

### Features
- **Climate Relevance Scoring:** 0-100 scale
- **Environmental Claim Detection:** Identifies specific ESG claims
- **Greenwashing Pattern Detection:** Vague claims, hedge words, temporal vagueness
- **TCFD Coverage Analysis:** Governance, Strategy, Risk Management, Metrics

### Usage
```python
from ml_models.climatebert_analyzer import get_climatebert_analyzer

analyzer = get_climatebert_analyzer()
result = analyzer.analyze_claim_for_greenwashing(
    claim_text="We are committed to achieving net zero by 2050",
    evidence_texts=["Company reported 10% emission increase..."]
)
```

### Installation
```bash
pip install transformers torch
```

---

## 📊 3. SHAP/LIME Explainability Engine

**File:** `ml_models/explainability_engine.py`

### Purpose
Provides Explainable AI (XAI) for ESG ML model predictions, generating human-readable explanations for risk scores.

### Features
- **SHAP TreeExplainer:** For XGBoost and LightGBM models
- **LIME Explanations:** Model-agnostic explanations
- **Feature Impact Ranking:** Shows exactly why scores were assigned
- **Report-Ready Narratives:** Human-readable explanations for reports
- **Visualization Data:** Ready for plots (waterfall, bar charts)

### Usage
```python
from ml_models.explainability_engine import explain_esg_prediction

explanation = explain_esg_prediction(
    model=xgboost_model,
    model_type="xgboost",
    features=feature_array,
    feature_names=["esg_score", "carbon_intensity", ...],
    prediction={"risk_level": "HIGH"}
)
```

### Sample Output
```
**Key factors influencing this ESG risk assessment:**
1. **Carbon intensity per revenue** (value: 2.5M) - very high impact, increases risk
2. **ESG disclosure count** (value: 3) - high impact, increases risk
3. **Governance score** (value: 85) - moderate impact, decreases risk
```

---

## 🔍 4. Greenwishing/Greenhushing Detector Agent

**File:** `agents/greenwishing_detector.py`

### Purpose
Detects advanced ESG deception tactics beyond traditional greenwashing.

### Detection Capabilities

#### Greenwishing
- Unfunded aspirational targets
- Vague timelines ("eventually", "in the future")
- Dependency language ("subject to technology")
- No clear implementation pathway

#### Greenhushing
- Missing mandatory disclosures
- Suppression of negative ESG data
- Partial period reporting
- "Not material" claims for material topics

#### Selective Disclosure
- Cherry-picking favorable metrics
- Boundary manipulation (excluding JVs)
- Baseline gaming (restated figures)

### Usage
```python
from agents.greenwishing_detector import get_greenwishing_detector

detector = get_greenwishing_detector()
result = detector.detect_deception_tactics(
    company="Company Name",
    claim=claim_dict,
    evidence=evidence_list
)
```

---

## ⚖️ 5. Regulatory Horizon Scanner

**File:** `agents/regulatory_scanner.py`

### Purpose
Maps ESG claims against global and Indian regulations, identifying compliance gaps and regulatory risks.

### Supported Regulations

#### India 🇮🇳
- **SEBI BRSR:** Business Responsibility and Sustainability Report
- **MCA Companies Act:** Section 135 CSR mandate
- **CPCB EPA:** Environmental compliance (Consent to Operate)
- **RBI Green Finance:** Climate risk disclosure for banks
- **BEE PAT Scheme:** Energy efficiency for designated consumers

#### European Union 🇪🇺
- **CSRD:** Corporate Sustainability Reporting Directive
- **EU Taxonomy:** Sustainable activity classification
- **SFDR:** Sustainable Finance Disclosure Regulation

#### United States 🇺🇸
- **SEC Climate Rules:** Material climate risk disclosure
- **FTC Green Guides:** Marketing claim substantiation

#### United Kingdom 🇬🇧
- **FCA Anti-Greenwashing:** Must be fair, clear, not misleading
- **TCFD Mandatory:** Four pillars disclosure

#### Global 🌍
- **GHG Protocol:** Corporate carbon accounting standard
- **SBTi:** Science Based Targets validation
- **GRI Standards:** Sustainability reporting
- **CDP:** Climate disclosure questionnaire

### Usage
```python
from agents.regulatory_scanner import get_regulatory_scanner

scanner = get_regulatory_scanner()
result = scanner.scan_regulatory_compliance(
    company="Tata Steel",
    claim=claim_dict,
    evidence=evidence_list,
    jurisdiction="India"
)
```

---

## 🇮🇳 6. Indian Data Sources Integration

**File:** `utils/indian_data_sources.py`

### Purpose
Comprehensive Indian ESG data collection from regulatory, news, and research sources.

### Sources Covered

#### News
- Economic Times
- Business Standard
- LiveMint
- Moneycontrol
- The Hindu Business Line
- Google News India

#### Regulatory
- SEBI (Filings, BRSR)
- MCA (Company registration, CSR)
- NSE/BSE (Listed company data)

#### Environmental Compliance
- CPCB (Pollution control compliance)
- NGT (National Green Tribunal cases)
- MoEFCC (Environment ministry)

#### Research & NGO
- CSE (Centre for Science and Environment)
- WRI India
- India Water Portal

#### Global APIs
- World Bank Climate Data (India indicators)
- CDP India reports
- EPA OpenData (US comparison)

### Usage
```python
from utils.indian_data_sources import get_indian_data_aggregator

aggregator = get_indian_data_aggregator()
results = aggregator.fetch_all_indian_sources("Reliance Industries")
```

---

## 📦 Installation

### New Dependencies
```bash
pip install transformers torch shap lime nltk sentencepiece
```

Or install all requirements:
```bash
pip install -r requirements.txt
```

### Environment Variables
Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

Key settings for Indian enterprises:
```env
DEFAULT_JURISDICTION=India
CLIMATEBERT_ENABLED=true
SHAP_ENABLED=true
SEBI_BRSR_ENABLED=true
```

---

## 🚀 Quick Start

### Analyze Indian Company
```python
from main_langgraph import ESGGreenwashingDetectorLangGraph

detector = ESGGreenwashingDetectorLangGraph()

result = detector.analyze_company(
    company_name="Reliance Industries",
    claim="We are committed to achieving net carbon zero by 2035",
    industry="Oil & Gas"
)
```

### Use Individual Agents
```python
# Carbon Analysis
from agents.carbon_extractor import get_carbon_extractor
carbon = get_carbon_extractor().extract_carbon_data(...)

# Greenwishing Detection
from agents.greenwishing_detector import get_greenwishing_detector
deception = get_greenwishing_detector().detect_deception_tactics(...)

# Regulatory Scan
from agents.regulatory_scanner import get_regulatory_scanner
compliance = get_regulatory_scanner().scan_regulatory_compliance(...)

# Explainability
from ml_models.explainability_engine import explain_esg_prediction
explanation = explain_esg_prediction(...)
```

---

## 📋 API Keys Required

| API | Purpose | Free Tier |
|-----|---------|-----------|
| Groq | LLM inference | Yes |
| Gemini | LLM fallback | Yes |
| NewsAPI | News search | 100 req/day |
| NewsData | Indian news | 200 req/day |

---

## 🔧 Configuration

### Settings (`config/settings.py`)
```python
DEFAULT_JURISDICTION = "India"
INDIA_GRID_EMISSION_FACTOR = 0.71  # tCO2/MWh
CLIMATEBERT_ENABLED = True
SHAP_ENABLED = True
```

### Regulatory Frameworks
All frameworks are enabled by default. To customize:
```python
REGULATORY_FRAMEWORKS = [
    "SEBI_BRSR",
    "MCA_COMPANIES_ACT",
    "GHG_PROTOCOL",
    "SBTI"
]
```

---

## 📝 Notes for Indian Enterprises

1. **SEBI BRSR Compliance:** Mandatory for top 1000 listed companies. The system checks for Scope 1, 2 emissions, energy consumption, water usage, and waste disclosure.

2. **MCA CSR Mandate:** Section 135 requires 2% of average net profits for CSR. The system validates CSR claims against Schedule VII activities.

3. **CPCB Compliance:** For polluting industries, the system checks for Consent to Operate status and OCEMS compliance.

4. **Indian News Coverage:** Dedicated RSS feeds from major Indian business publications ensure comprehensive media monitoring.

5. **INR/Crore/Lakh Support:** Carbon extractors understand Indian numerical notation (lakh tonnes, crore rupees).

---

## 🤝 Contributing

To add new Indian regulations or data sources:
1. Add regulation to `agents/regulatory_scanner.py` in `_initialize_regulations()`
2. Add data source to `utils/indian_data_sources.py`
3. Update `config/settings.py` with new configuration options

---

## 📄 License

MIT License - See LICENSE file for details.
