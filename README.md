# ESG Greenwashing Detection System

**Enterprise-grade AI-powered greenwashing detection** with 14 specialized agents, 15 data sources, and ML-enhanced risk scoring.

## 🚀 Quick Start

### **1. Install Dependencies**
```21
6pip install -r requirements.txt
`5``

### **2. Set API Keys** (Optional - works with free sources)
Create `.env` file:
```env
# Premium (Optional)
NEWS_API_KEY=your_newsapi_key
NEWSDATA_API_KEY=your_newsdata_key

# LLMs (Choose one)
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_gemini_key
```

### **3. Run Analysis**
```bash
python main_langgraph.py
```

## 📊 What's Integrated

### ✅ **14 AI Agents**
1. Claim Extractor
2. **Evidence Retriever** (includes Financial Analyst #14)
3. Contradiction Analyzer
4. Historical/Temporal Analyst
5. Industry/Peer Comparator
6. Credibility Analyst
7. **Risk Scorer** (ML + Formula hybrid)
8. Sentiment Analyzer
9. Realtime Monitor
10. Confidence Scorer
11. Conflict Resolver
12. Supervisor
13. Report Generator
14. **Financial Analyst** (NEW - yfinance integration)

### ✅ **15 Free Data Sources**
- **4 Premium News APIs**: NewsAPI, NewsData, TheNewsAPI, Mediastack
- **4 Free News APIs**: Google News, BBC RSS, DuckDuckGo, GDELT
- **2 Legal APIs**: FTC Enforcement, UK CMA
- **1 Compliance**: OpenSanctions
- **1 Environmental**: World Bank
- **1 Research**: Semantic Scholar
- **1 Historical**: Wayback Machine
- **1 Financial**: Yahoo Finance (yfinance)

### ✅ **ML-Enhanced Risk Scoring**
- **XGBoost Classifier**: 3-class (HIGH/MODERATE/LOW) risk prediction
- **Hybrid Approach**: 
  - High confidence (≥80%): Pure ML
  - Medium (60-79%): 70% ML + 30% Formula
  - Low (<60%): Pure Formula
- **10 Features**: ESG score, revenue, profit margin, carbon intensity, water/energy efficiency, industry, peer comparison, disclosure count

### ✅ **Financial Analysis Integration**
- **Real-time Financial Data**: Revenue, profit margin, debt-to-equity, beta
- **ESG-Financial Metrics**: Carbon intensity, water efficiency, energy efficiency
- **7 Greenwashing Patterns**:
  1. Fossil fuel revenue growth with green claims
  2. High carbon intensity (>1.0)
  3. High profit + low ESG
  4. High debt + aggressive green claims
  5. Revenue decline + ESG claims increase
  6. Industry leader claiming transformation
  7. Acquisition of green companies during controversy

## 🎯 Usage Examples

### **Basic Analysis**
```python
from main_langgraph import ESGGreenwashingDetectorLangGraph

detector = ESGGreenwashingDetectorLangGraph()
result = detector.analyze_company(
    company_name="Tesla",
    claim="We are carbon neutral and have achieved net-zero emissions",
    industry="automotive"
)

print(f"Risk Level: {result['risk_level']}")
print(f"ESG Score: {result['esg_score']}")
print(f"Confidence: {result['confidence']}")
```

### **With ML Model**
1. Train model in Google Colab:
   - Open `notebooks/train_xgboost_risk.ipynb`
   - Upload `data/company_esg_financial_dataset.csv` (11K rows)
   - Run all cells (~5-7 minutes)
   - Download `xgboost_risk_model.pkl`

2. Place model:
   ```
   ml_models/trained/xgboost_risk_model.pkl
   ```

3. Run analysis (automatically uses ML):
   ```bash
   python main_langgraph.py
   ```

## 📁 Project Structure

```
ESG/
├── agents/                    # 14 specialized AI agents
│   ├── financial_analyst.py    # NEW: Agent #14 (yfinance)
│   ├── evidence_retriever.py   # Calls financial_analyst
│   ├── risk_scorer.py          # ML + Formula hybrid
│   └── [11 other agents]
├── core/                      # LangGraph orchestration
│   ├── workflow_phase2.py      # Main workflow
│   ├── agent_wrappers.py       # Node wrappers
│   └── state_schema.py         # State management
├── ml_models/                 # XGBoost model
│   ├── xgboost_risk_model.py   # Model wrapper
│   └── trained/                # Trained models
├── utils/                     # Data sources
│   ├── enterprise_data_sources.py
│   ├── free_data_sources.py    # 15 APIs
│   └── web_search.py
├── data/                      # Datasets
│   └── company_esg_financial_dataset.csv  # 11K rows
├── notebooks/                 # Training
│   └── train_xgboost_risk.ipynb  # Colab notebook
└── main_langgraph.py          # Entry point
```

## 🧪 Testing

```bash
# Full integration test
python test_full_integration.py

# Financial analyst test
python test_financial_analyst.py

# End-to-end workflow
python test_e2e.py
```

## 📊 Output Format

```json
{
  "risk_level": "HIGH",
  "greenwashing_risk_score": 78.5,
  "esg_score": 21.5,
  "risk_source": "ML-Enhanced (70% XGBoost + 30% Formula)",
  "confidence": 0.85,
  
  "ml_prediction": {
    "prediction": "HIGH",
    "confidence": 0.92,
    "probabilities": {
      "HIGH": 0.92,
      "MODERATE": 0.06,
      "LOW": 0.02
    }
  },
  
  "financial_analysis": {
    "revenue_usd": 94800000000,
    "profit_margin_pct": 4.5,
    "carbon_intensity": 0.42,
    "greenwashing_flags": ["..."]
  },
  
  "evidence_count": 47,
  "report": "reports/Tesla_20260205_180430.pdf"
}
```

## 📚 Documentation

- **[FULL_INTEGRATION_GUIDE.md](FULL_INTEGRATION_GUIDE.md)** - Complete integration details
- **[FINANCIAL_ANALYST_INTEGRATION.md](FINANCIAL_ANALYST_INTEGRATION.md)** - Financial analyst docs
- **`notebooks/train_xgboost_risk.ipynb`** - ML model training

## 🔧 Key Features

### **Dynamic Workflow Routing**
- **Fast Track** (3 agents): Simple claims, low complexity
- **Standard Track** (11 agents): Normal analysis
- **Deep Analysis** (11 agents + Debate): High complexity, controversial claims

### **Hybrid ML Scoring**
- **Confidence-based ensemble**: Combines ML and formula strengths
- **Graceful degradation**: Works without trained model
- **Feature extraction**: Automatic from agent outputs

### **Financial Integration**
- **Automatic**: Called during evidence retrieval
- **Real-time**: Yahoo Finance API
- **Comprehensive**: 7 greenwashing pattern detectors

## 🆘 Troubleshooting

**"XGBoost model not found"**
- ✅ Normal - system uses formula-based scoring
- ⚠️ To enable ML: Train model in Colab (see above)

**"yfinance not installed"**
```bash
pip install yfinance>=0.2.40
```

**Test all integrations:**
```bash
python test_full_integration.py
```

## 📝 Requirements

**Minimum:**
- Python 3.10+
- 4GB RAM
- Internet connection

**Recommended:**
- Python 3.10+
- 8GB RAM
- GPU (for faster ML training in Colab)

## 🎓 System Architecture

```
User Input
    ↓
[Supervisor] → Assess Complexity → Route
    ↓
[Evidence Retriever] → 15 APIs + Financial Analyst
    ↓
[Agents] → Contradiction, Temporal, Peer, Credibility, Sentiment
    ↓
[Risk Scorer] → XGBoost ML + Formula + Financial Penalties
    ↓
[Report] → Professional PDF
```

## 🌟 What Makes This Special

1. **Fully Integrated**: All 14 agents, 15 data sources, ML model work seamlessly
2. **Production Ready**: Error handling, fallbacks, graceful degradation
3. **Free to Use**: Works without any paid APIs
4. **ML-Enhanced**: Optional XGBoost model for better accuracy
5. **Financial Analysis**: Unique yfinance integration for ESG-financial correlation
6. **Comprehensive**: Multi-source evidence, peer comparison, historical analysis
7. **Transparent**: Explainable scoring, detailed reports

## 📜 Status

**✅ FULLY INTEGRATED**
- All agents connected
- Financial analyst operational
- ML model wrapper ready
- State management enhanced
- LangGraph workflow optimized
- Testing suite complete

**Ready for production use!**

## 🚀 Get Started

```bash
# 1. Clone/download project
# 2. Install dependencies
pip install -r requirements.txt

# 3. Run first analysis
python main_langgraph.py

# 4. (Optional) Train ML model
# Open notebooks/train_xgboost_risk.ipynb in Colab
```

---

**Built with**: LangGraph, XGBoost, yfinance, Groq, Gemini
**Version**: 3.0 (Fully Integrated)
**Updated**: February 2026

For detailed integration documentation, see **[FULL_INTEGRATION_GUIDE.md](FULL_INTEGRATION_GUIDE.md)**
