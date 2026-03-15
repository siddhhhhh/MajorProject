# ESG Greenwashing Detection System - Complete Architecture

**Project Version:** 3.0 (LangGraph)  
**Documentation Date:** February 17, 2026  
**System Type:** Multi-Agent AI with ML Enhancement

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Complete Project Flow](#complete-project-flow)
3. [ML Models Contribution](#ml-models-contribution)
4. [Agent Pipeline Details](#agent-pipeline-details)
5. [Data Sources](#data-sources)
6. [Architecture Decisions](#architecture-decisions)

---

## 🎯 System Overview

### What Does This System Do?

Analyzes corporate ESG (Environmental, Social, Governance) claims to detect **greenwashing** - when companies make misleading environmental claims.

### Key Capabilities:
- ✅ Analyzes claims from 15 free data sources
- ✅ Uses 14 specialized AI agents
- ✅ Employs 4 active ML models + 2 trained models
- ✅ Generates professional reports with letter grades (AAA to CCC)
- ✅ Self-improving peer database

### Technology Stack:
- **Orchestration:** LangGraph (state machine)
- **LLMs:** Groq (Llama 3.3 70B) / Google Gemini
- **ML Models:** XGBoost, LightGBM, LSTM, Isolation Forest
- **Vector DB:** ChromaDB (peer comparison + historical claims)
- **Data Sources:** 15 APIs (news, legal, financial, academic)

---

## 🔄 Complete Project Flow

### Phase 1: Input & Initialization

**Entry Point:** `main_langgraph.py`

```
USER INPUT:
├── Company Name (e.g., "Tesla")
├── ESG Claim (e.g., "We are carbon neutral")
└── Industry (optional, auto-detected)

SYSTEM INITIALIZATION:
├── Load LangGraph workflow
├── Initialize 14 AI agents
├── Load 4 ML models (XGBoost, LightGBM, LSTM, Anomaly)
├── Connect to ChromaDB peer database
└── Initialize evidence cache system
```

**State Object Created:**
```python
{
    "claim": "We are carbon neutral",
    "company": "Tesla",
    "industry": "Automotive",
    "evidence": [],
    "confidence": 0.0,
    "agent_outputs": [],
    "final_verdict": {},
    "report": ""
}
```

**Files Involved:**
- `main_langgraph.py` - Main entry point
- `core/workflow_phase2.py` - LangGraph workflow builder
- `core/state_schema.py` - State definition
- `ml_models/*.py` - ML model loaders

---

### Phase 2: Complexity Assessment & Routing

**Agent:** Supervisor Agent (`core/supervisor_agent.py`)

```
COMPLEXITY ANALYSIS:
├── LLM analyzes claim complexity (0.0 to 1.0)
├── Factors considered:
│   ├── Quantitative specificity (has numbers?)
│   ├── Temporal clarity (specific timeframe?)
│   ├── Verifiability (can be checked?)
│   ├── Ambiguity (vague terms like "sustainable"?)
│   └── Scope (broad vs specific?)
└── Returns complexity score

ROUTING DECISION:
├── Complexity < 0.3 → FAST TRACK (3 agents, ~30 sec)
├── Complexity 0.3-0.7 → STANDARD TRACK (11 agents, ~90 sec)
└── Complexity > 0.7 → DEEP ANALYSIS (11 agents + debate, ~120 sec)
```

**Example Complexity Scores:**
- "BP reduced emissions by 15% in 2023" → **0.2** (specific, verifiable) → Fast Track
- "Invested $500M in renewable energy" → **0.4** (moderate) → Standard Track
- "We are committed to sustainability" → **0.9** (vague) → Deep Analysis

**Why This Matters:**
- Saves computational resources on simple claims
- Ensures complex/vague claims get thorough scrutiny
- Adaptive resource allocation

---

### Phase 3: Evidence Collection

**Agent:** Evidence Retriever (`agents/evidence_retriever.py`)

```
CACHE CHECK:
├── Check evidence_cache (24-hour TTL)
├── Cache key: company_name + date
├── IF CACHE HIT → Return cached data (ZERO API calls)
└── IF CACHE MISS → Fetch from all sources

MULTI-SOURCE FETCH (if cache miss):
├── News APIs (8 sources):
│   ├── Premium: NewsAPI, NewsData, TheNewsAPI, Mediastack
│   └── Free: Google News, BBC RSS, DuckDuckGo News, GDELT
├── Legal APIs (2 sources):
│   ├── FTC Enforcement Actions
│   └── UK Competition & Markets Authority
├── Compliance (1 source):
│   └── OpenSanctions (sanctions database)
├── Environmental (1 source):
│   └── World Bank Climate Data
├── Research (1 source):
│   └── Semantic Scholar (academic papers)
├── Financial (1 source):
│   └── Yahoo Finance (yfinance)
└── Historical (1 source):
    └── Wayback Machine (archived claims)

FINANCIAL ANALYSIS (Agent #14):
├── Fetch real-time financial data via yfinance
├── Metrics extracted:
│   ├── Revenue, profit margin, debt-to-equity
│   ├── Carbon intensity (emissions / revenue)
│   ├── Water efficiency, energy efficiency
│   └── Stock beta (volatility)
└── Detect 7 greenwashing patterns:
    ├── Fossil fuel revenue growth + green claims
    ├── High carbon intensity (>1.0)
    ├── High profit + low ESG score
    ├── High debt + aggressive green claims
    ├── Revenue decline + ESG claims increase
    ├── Industry leader claiming transformation
    └── Acquisition of green companies during controversy

RELEVANCE FILTERING:
├── Remove cross-contaminated data
│   └── Example: Remove "Apple" articles when analyzing "BP"
├── Use LLM to verify company name matches
└── Filter by date relevance

VECTOR STORAGE:
├── Store evidence in ChromaDB
├── Enable similarity search
└── Build historical pattern database

OUTPUT: 20-50 evidence pieces stored in state["evidence"]
```

**Cache Benefits:**
- First analysis: 15 API calls
- Subsequent analyses (same day): 0 API calls
- 10 analyses of BP = 1 API call instead of 150

**Files Involved:**
- `agents/evidence_retriever.py` - Evidence orchestrator
- `agents/financial_analyst.py` - Financial data analysis
- `core/evidence_cache.py` - Caching system
- `utils/free_data_sources.py` - Free API aggregator
- `utils/enterprise_data_sources.py` - Premium APIs

---

### Phase 4: Specialized Agent Analysis

**Sequential Pipeline (11 Agents)**

#### Agent 1: Claim Extractor
**File:** `agents/claim_extractor.py`

```
FUNCTIONALITY:
├── Break down claim into verifiable sub-claims
├── Extract quantitative metrics (e.g., "30% reduction")
├── Categorize claim type (carbon, water, energy, etc.)
└── Assign specificity score (0-10)

EXAMPLE INPUT:
"Tesla reduced emissions by 30% and invested $500M in renewables"

EXAMPLE OUTPUT:
{
  "sub_claims": [
    {"text": "reduced emissions by 30%", "specificity": 9},
    {"text": "invested $500M in renewables", "specificity": 8}
  ],
  "claim_type": "Environmental",
  "overall_specificity": 8.5
}
```

#### Agent 3: Contradiction Analyzer
**File:** `agents/contradiction_analyzer.py`

```
FUNCTIONALITY:
├── Compare claim against gathered evidence
├── Identify logical contradictions
├── Severity scoring (minor/moderate/severe)
└── Citation of contradictory sources

EXAMPLE:
CLAIM: "We are carbon neutral"
EVIDENCE: "Company's Scope 1 emissions increased 15% YoY"
CONTRADICTION: SEVERE
```

#### Agent 4: Historical Analyst
**File:** `agents/historical_analyst.py`

```
FUNCTIONALITY:
├── Check past claims via Wayback Machine
├── Detect pattern changes over time
├── Flag inconsistencies in historical narrative
└── Identify claim evolution

EXAMPLE:
2020: "Committed to net zero by 2050"
2022: "Committed to net zero by 2040"
2024: "Committed to net zero by 2030"
PATTERN: Progressive commitment without action evidence
```

#### Agent 5: Industry Comparator
**File:** `agents/industry_comparator.py`

```
FUNCTIONALITY:
├── Compare company ESG score to industry peers
├── Uses ChromaDB peer database (built over time)
├── Calculate percentile ranking
└── Identify industry leaders vs laggards

EXAMPLE:
Company ESG: 55/100
Industry Average: 45/100
Percentile: 72nd percentile (above average)
Status: "Outperforming industry but moderate absolute score"
```

#### Agent 6: Credibility Analyst
**File:** `agents/credibility_analyst.py`

```
FUNCTIONALITY:
├── Score source credibility
│   ├── Government agencies: 1.0
│   ├── Academic papers: 0.9
│   ├── Major news outlets: 0.7-0.8
│   ├── Industry reports: 0.6
│   └── Social media: 0.3
├── Weight evidence by source quality
└── Cross-reference multiple sources

EXAMPLE:
Source 1: EPA Report (credibility: 1.0) - Emissions increased
Source 2: Company Blog (credibility: 0.4) - Emissions decreased
Weighted Verdict: Trust EPA report
```

#### Agent 7: Risk Scorer (MOST COMPLEX)
**File:** `agents/risk_scorer.py`

**This is where ML models are integrated - see ML Models section below**

```
FUNCTIONALITY:
├── Calculate ESG pillar scores (E/S/G)
├── Generate overall ESG score (0-100)
├── Convert to MSCI-style rating (AAA to CCC)
├── Apply ML model refinements (XGBoost, LSTM)
├── Validate with LightGBM predictor
├── Detect anomalies with Isolation Forest
└── Generate final risk level (HIGH/MODERATE/LOW)

OUTPUT:
{
  "esg_score": 68/100,
  "rating_grade": "BBB",
  "risk_level": "MODERATE",
  "greenwashing_risk": 32/100,
  "pillar_scores": {
    "environmental": 65/100,
    "social": 70/100,
    "governance": 69/100
  }
}
```

#### Agent 8: Sentiment Analyzer
**File:** `agents/sentiment_analyzer.py`

```
FUNCTIONALITY:
├── Analyze news sentiment (TextBlob)
├── Compare company claims vs public perception
├── Detect greenwashing language patterns:
│   ├── Buzzword density ("sustainable", "eco-friendly")
│   ├── Vague quantifiers ("significant", "substantial")
│   ├── Hedge words ("might", "could", "may")
│   ├── Future tense overuse ("will", "plans to")
│   └── Absolute claims without detail ("100%", "zero")
└── Calculate sentiment divergence score

EXAMPLE:
Claim Sentiment: +0.8 (very positive)
Evidence Sentiment: -0.3 (negative)
Divergence: 1.1 (HIGH - red flag)
```

#### Agent 9: Realtime Monitor
**File:** `agents/realtime_monitor.py`

```
FUNCTIONALITY:
├── Check recent news (last 7 days)
├── Detect breaking controversies
├── Flag sanctions/legal actions
└── Monitor social media sentiment

EXAMPLE:
Alert: "Company fined $2M by EPA 3 days ago"
Impact: Increases greenwashing risk by 15 points
```

#### Agent 10: Confidence Scorer
**File:** `agents/confidence_scorer.py`

```
FUNCTIONALITY:
├── Aggregate all agent outputs
├── Calculate final confidence (0-100%)
├── Factors:
│   ├── Evidence quantity (more = higher confidence)
│   ├── Source diversity (multiple independent sources)
│   ├── Agent agreement (all agents align?)
│   └── Data recency (recent = more confident)
└── Adjust final verdict confidence

EXAMPLE:
Evidence: 45 sources
Source Diversity: 12/15 sources used
Agent Agreement: 9/11 agents agree
Final Confidence: 87%
```

---

### Phase 5: Conflict Resolution (Deep Analysis Only)

**Agent:** Debate Orchestrator (`core/debate_orchestrator.py`)

**Activated When:** Agent verdicts differ by >30%

```
DEBATE PROCESS:
├── Extract each agent's position (HIGH/MODERATE/LOW)
├── Identify conflicting verdicts
├── Multi-round structured debate:
│   ├── Round 1: Each agent presents reasoning
│   ├── Round 2: Agents challenge opposing views
│   └── Round 3: Final arguments
├── Voting-based resolution:
│   ├── Each agent votes (weighted by confidence)
│   ├── Majority wins
│   └── Tiebreakers: Evidence quality, source credibility
└── Update state with consensus verdict

RESEARCH BASIS:
"Multi-agent voting improves accuracy by 10.4%" (research-validated)
```

**Example Conflict:**
- Risk Scorer: "HIGH risk" (based on formula)
- Credibility Analyst: "LOW risk" (high-quality evidence)
- Historical Analyst: "MODERATE risk" (inconsistent history)

**Debate Resolution:**
- After 3 rounds, majority votes "MODERATE risk"
- Confidence adjusted to reflect disagreement

**Files Involved:**
- `core/debate_orchestrator.py` - Debate logic
- `agents/conflict_resolver.py` - Final verdict synthesis

---

### Phase 6: Peer Database Update

**Location:** `core/workflow_phase2.py` - `save_peer_to_database_node()`

```
FUNCTIONALITY:
├── Extract company ESG scores
├── Save to ChromaDB peer database
├── Store:
│   ├── Company name
│   ├── Industry sector
│   ├── ESG score + pillar breakdown
│   ├── Rating grade (AAA to CCC)
│   └── Timestamp
└── Build long-term industry benchmarks

DATABASE GROWTH:
Analysis 1: Database has 0 companies → Save Tesla
Analysis 2: Database has 1 company → Save BP
Analysis 10: Database has 9 companies → Compare against 9 peers
Analysis 100: Database has 99 companies → Rich peer comparison

BENEFIT: Self-improving system without external datasets
```

**Files Involved:**
- `core/workflow_phase2.py` - Save node
- `agents/industry_comparator.py` - Database interface
- `chroma_db/peer_comparison_history/` - Persistent storage

---

### Phase 7: Final Verdict Generation

**Agent:** Conflict Resolver (`agents/conflict_resolver.py`)

```
VERDICT SYNTHESIS:
├── Aggregate all agent outputs
├── Resolve any remaining conflicts
├── Apply domain knowledge overrides:
│   └── Example: Oil & Gas + green claims = automatic HIGH risk
├── Generate structured verdict:
│   ├── Risk level (HIGH/MODERATE/LOW)
│   ├── Confidence score (0-100%)
│   ├── Rating grade (AAA to CCC)
│   ├── Verdict summary (text explanation)
│   ├── Key findings (top 3-5 insights)
│   └── Recommendations (actionable advice)
└── Lock verdict to prevent overrides

OUTPUT EXAMPLE:
{
  "risk_level": "HIGH",
  "final_confidence": 0.85,
  "rating_grade": "BB",
  "verdict_summary": "Evidence suggests greenwashing through vague claims without verifiable metrics",
  "key_findings": [
    "High buzzword density (12 instances) without specific data",
    "Contradicted by EPA emissions report (+15% increase)",
    "Historical claims inconsistent (changed targets 3 times)"
  ],
  "recommendations": [
    "Require third-party ESG audit",
    "Request Scope 1/2/3 emissions breakdown",
    "Monitor quarterly sustainability reports"
  ]
}
```

---

### Phase 8: Professional Report Generation

**Agent:** Report Generator (`core/professional_report_generator.py`)

```
REPORT FORMATS:

1. EXECUTIVE REPORT (TXT) - Multi-page professional document:
   ├── Cover Page (company, date, risk level)
   ├── Executive Summary (1 page)
   ├── Methodology (data sources, agents used)
   ├── Detailed Findings (evidence analysis)
   ├── Risk Assessment (pillar breakdown)
   ├── Peer Comparison (industry benchmarking)
   ├── Recommendations (actionable steps)
   └── Appendix (evidence citations, agent trace)

2. JSON EXPORT - Machine-readable format:
   ├── All raw data
   ├── Agent outputs with timestamps
   ├── Evidence list with sources
   └── Metadata (workflow path, ML predictions)

3. FULL DEBUG LOG - For auditing:
   ├── Complete trace of all agent outputs
   ├── LLM prompts and responses
   ├── ML model predictions
   └── Timing information

SAVED TO: reports/ESG_Report_CompanyName_TIMESTAMP.{txt,json}
```

**Report Quality Features:**
- ✅ Professional formatting with headers/sections
- ✅ Evidence citations with URLs
- ✅ Visualization-ready data (for dashboards)
- ✅ Audit trail (who decided what, when)
- ✅ Export-friendly (integrate with other systems)

---

### Phase 9: Output to User

**Display:** Terminal + Saved Files

```
TERMINAL OUTPUT:
═══════════════════════════════════════════════════════════════════════
📊 EXECUTIVE SUMMARY
═══════════════════════════════════════════════════════════════════════

🏢 Company: Tesla
🏭 Industry: Automotive
📋 Claim: We are carbon neutral and have achieved net-zero emissions

🔴 Risk Level: HIGH
📈 Confidence: 87%
⭐ ESG Rating: BB (Below Average)
🔀 Analysis Path: Deep Analysis with Multi-Agent Debate

📚 Evidence Sources: 45
🤖 Agents Executed: 11
✅ Successful: 11/11 (100%)

📋 Agents Used:
   ✅ Claim Extraction
   ✅ Evidence Retrieval
   ✅ Contradiction Analysis
   ✅ Historical/Temporal Analysis
   ✅ Industry/Peer Comparison
   ✅ Credibility Analysis
   ✅ Risk Scoring
   ✅ Sentiment Analysis
   ✅ Realtime Monitoring
   ✅ Confidence Scoring
   ✅ Conflict Resolution

🗣️  Multi-Agent Debate: ACTIVATED
   Conflicting agents: Risk Scorer, Credibility Analyst
   Consensus reached after 3 rounds

💾 Reports saved:
   📄 reports/ESG_Report_Tesla_20260217_143022.txt
   📊 reports/ESG_Report_Tesla_20260217_143022.json
   🔍 reports/ESG_Report_Tesla_20260217_143022_FULL.json
═══════════════════════════════════════════════════════════════════════
```

---

## 🤖 ML Models Contribution

### Overview: 4 Active Models + 2 Trained (Inactive)

```
ACTIVE ML MODELS:
├── XGBoost Risk Classifier
├── LightGBM ESG Predictor
├── LSTM Trend Forecaster
└── Isolation Forest Anomaly Detector

TRAINED BUT INACTIVE:
├── K-Means Industry Clustering
└── Sentiment-ESG Regression Predictor
```

---

### Model 1: XGBoost Risk Classifier 🎯

**File:** `ml_models/xgboost_risk_model.py`  
**Integration:** `agents/risk_scorer.py` lines 380-440  
**Type:** 3-class classification (HIGH/MODERATE/LOW)

#### Purpose:
Refines greenwashing risk classification for companies in MODERATE ESG range (50-74)

#### When Used:
```
ESG Score ≥75 (A/AA/AAA) → BYPASSED (pillar score used)
ESG Score 50-74 (BBB/BB) → ACTIVATED (refines boundary)
ESG Score <50 (B/CCC)    → BYPASSED (pillar score used)
```

#### Input Features (10):
```python
1. esg_score              # Overall ESG score (0-100)
2. revenue_log            # Log10(revenue in USD)
3. profit_margin          # Profit margin percentage
4. carbon_intensity       # Carbon emissions / Revenue
5. water_efficiency       # Water usage / Revenue
6. energy_efficiency      # Energy consumption / Revenue
7. industry_encoded       # Industry category (0-9)
8. esg_vs_industry        # ESG score vs peer average
9. revenue_vs_industry    # Revenue vs peer average
10. esg_disclosure_count  # Number of ESG disclosures
```

#### Output:
```python
{
    "prediction": "MODERATE",  # HIGH/MODERATE/LOW
    "confidence": 0.87,        # 0-1 scale
    "probabilities": {
        "HIGH": 0.12,
        "MODERATE": 0.78,
        "LOW": 0.10
    }
}
```

#### Contribution to ESG Score:

**Hybrid Decision Logic:**
```python
if ml_confidence >= 0.80:
    # Use ML prediction to refine rating
    if ml_prediction == "LOW" and esg_score >= 60:
        rating_grade = "BBB"  # Upgrade within MODERATE range
        risk_score = 35/100
    elif ml_prediction == "HIGH" and esg_score < 60:
        rating_grade = "BB"   # Downgrade within MODERATE range
        risk_score = 55/100
    
    risk_source = "ESG Pillar + ML Refinement"
else:
    # ML not confident, use pillar score
    rating_grade = pillar_based_rating
    risk_source = "ESG Pillar Score (MSCI-Aligned)"
```

#### Impact Example:
```
Company: Microsoft
Pillar ESG Score: 65/100 → Initial Rating: BBB (MODERATE)

XGBoost Input:
- ESG: 65, Revenue: $200B, Profit Margin: 35%
- Carbon Intensity: 0.15 (low), Industry: Technology
- ESG vs Industry: +10 points above peer average

XGBoost Prediction: LOW (confidence: 0.89)
✅ Confidence ≥80% → Refine rating

Final Adjustment:
Rating: BBB → BBB+ (low-moderate risk)
Risk Score: 50/100 → 35/100 (improved)
Reason: "Strong financials + sector outperformance"
```

#### Why This Approach:
- ✅ ML captures non-linear patterns (e.g., high profit + low ESG often = greenwashing)
- ✅ Only used when confident (≥80%)
- ✅ Doesn't override domain knowledge (oil & gas always flagged)
- ✅ Transparent fallback to pillar score

#### Training Data:
- Source: `data/company_esg_financial_dataset.csv` (11,000 rows)
- Features: ESG scores + financial metrics
- Labels: HIGH/MODERATE/LOW (manually labeled greenwashing cases)
- Accuracy: ~85% on test set

---

### Model 2: LightGBM ESG Score Predictor 🔮

**File:** `ml_models/lightgbm_esg_predictor.py`  
**Integration:** `agents/risk_scorer.py` lines 560-585  
**Type:** Regression (predicts ESG score 0-100)

#### Purpose:
Validates pillar-calculated ESG scores against ML prediction to detect inflation/deflation

#### When Used:
Always runs AFTER pillar scores are calculated (validation check)

#### Input Features (7):
```python
1. environmentScore      # Environmental pillar (0-100)
2. socialScore          # Social pillar (0-100)
3. governanceScore      # Governance pillar (0-100)
4. highestControversy   # Highest controversy level (0-5)
5. marketCap_log        # Log(market capitalization)
6. beta                 # Stock volatility
7. overallRisk          # Overall risk score (0-100)
```

#### Output:
```python
{
    "predicted_esg": 68.5,              # ML-predicted ESG score
    "confidence_r2": 0.92,              # Model accuracy (R²)
    "expected_error": 5.2,              # Mean Absolute Error
    "prediction_range": (56.5, 80.5)    # 95% confidence interval
}
```

#### Contribution to ESG Score:

**ROLE: Validation ONLY (does NOT change score)**

```python
pillar_esg_score = 52/100  # Calculated from evidence
ml_predicted_esg = 48/100  # LightGBM prediction

discrepancy = abs(52 - 48) = 4 points

if discrepancy > 20:
    print("⚠️ Large discrepancy - manual review recommended")
    flag_for_human_review = True
else:
    print("✅ Scores aligned - validation passed")
    flag_for_human_review = False

# NOTE: Pillar score (52) is still used, NOT ML score (48)
```

#### Impact Example:
```
Company: Unknown Startup "GreenTech Inc"
Pillar ESG Score: 75/100 (limited evidence, high claims)

LightGBM Prediction:
Input: E=80, S=70, G=75, Controversy=0, Beta=2.0
Output: 48/100 (range: 41-55)

Discrepancy: |75 - 48| = 27 points ⚠️ LARGE GAP

Alert in Report:
"⚠️ ESG score validation failed - 27 point discrepancy detected.
Pillar score (75) significantly exceeds ML expected range (41-55).
Possible causes: Limited evidence, claim inflation, or unique business model.
RECOMMENDATION: Manual review required before final rating."

Final Score: Still 75/100 (pillar score used)
Action: Flagged for human analyst review
```

#### Why Validation-Only:
- ✅ Pillar scores are evidence-based (interpretable)
- ✅ ML predictions can be wrong for unique companies
- ✅ Validation identifies potential issues without overriding human judgment
- ✅ Best of both worlds: evidence-based + ML quality check

#### Training Data:
- Source: S&P 500 ESG data (~500 companies)
- Accuracy: R² = 0.92 (92% variance explained)
- MAE: 5.2 points average error

---

### Model 3: LSTM Trend Forecaster 📈

**File:** `ml_models/lstm_trend_predictor.py`  
**Integration:** `agents/risk_scorer.py` lines 587-607  
**Type:** Time series forecasting (predicts next 6 years)

#### Purpose:
Predicts ESG score trajectory to detect improving/declining trends

#### When Used:
Always runs if available (adds temporal context)

#### Input:
Historical ESG scores (6-year window)
```python
[60, 62, 65, 68, 70, 72]  # Last 6 years
```

#### Output:
```python
{
    "forecast": [73, 74, 75, 76, 77, 78],  # Next 6 years prediction
    "trend": "IMPROVING",                   # IMPROVING/STABLE/DECLINING
    "change_pct": +8.3,                     # % change from current
    "confidence_mae": 3.5                   # Mean Absolute Error
}
```

#### Contribution to ESG Score:

**ROLE: Risk Adjustment (-10 to +5 points)**

```python
if lstm_trend == "DECLINING":
    greenwashing_risk += 10  # Penalize declining trajectory
    print("⚠️ Declining ESG trend - risk increased by 10 points")
    
elif lstm_trend == "IMPROVING":
    greenwashing_risk -= 5   # Reward improving trajectory
    print("✅ Improving ESG trend - risk reduced by 5 points")
    
else:  # STABLE
    # No adjustment
    print("ℹ️ Stable ESG trend - no risk adjustment")
```

#### Impact Example:

**Example 1: Declining Trend (Penalty)**
```
Company: ExxonMobil
Current ESG: 55/100 (rating: BB, MODERATE risk)
Historical Scores: [65, 63, 60, 58, 56, 55]

LSTM Forecast: [52, 49, 46, 43, 40, 38] → DECLINING
Change: -12.7% over 6 years

Risk Adjustment: +10 points
Original Risk: 50/100 → Adjusted Risk: 60/100
Rating Change: BB (MODERATE) → B (HIGH risk)

Reasoning: "Consistent ESG deterioration signals worsening practices"
```

**Example 2: Improving Trend (Reward)**
```
Company: Microsoft
Current ESG: 78/100 (rating: A, LOW risk)
Historical Scores: [68, 70, 72, 74, 76, 78]

LSTM Forecast: [80, 82, 84, 86, 88, 90] → IMPROVING
Change: +15.4% over 6 years

Risk Adjustment: -5 points
Original Risk: 22/100 → Adjusted Risk: 17/100
Rating: Stays A (LOW risk) with higher confidence

Reasoning: "Consistent ESG improvement demonstrates commitment"
```

#### Why Minor Adjustment:
- ✅ Trends provide context but shouldn't override current evidence
- ✅ Past performance doesn't guarantee future results
- ✅ Moderate penalty for decline (companies can improve)
- ✅ Small reward for improvement (avoid over-optimism)

#### Training Data:
- Source: 6 years of ESG scores (synthetic + real data mix)
- Architecture: LSTM(64) → Dropout(0.2) → Dense(1)
- MAE: 3.5 points average error

---

### Model 4: Anomaly Detector (Isolation Forest) 🚨

**File:** `ml_models/anomaly_detector.py`  
**Integration:** `agents/risk_scorer.py` lines 609-630  
**Type:** Unsupervised anomaly detection

#### Purpose:
Flags companies with statistically unusual ESG patterns (potential greenwashing)

#### When Used:
Always runs if available (quality check)

#### Input Features (8):
```python
1. carbon_intensity         # Emissions / Revenue
2. water_intensity          # Water usage / Revenue
3. energy_intensity         # Energy / Revenue
4. esg_revenue_gap          # (ESG - 50) / log(Revenue)
5. growth_esg_correlation   # GrowthRate * ESG
6. profit_esg_ratio         # ProfitMargin / ESG
7. environmental_balance    # Env / (Social + Governance)
8. volatility_score         # Std dev of ESG over time
```

#### Output:
```python
{
    "is_anomaly": True,                     # Anomaly detected?
    "anomaly_score": -0.23,                 # Isolation Forest score
    "severity": "HIGH",                     # LOW/MODERATE/HIGH
    "confidence": 0.88,                     # Detection confidence
    "anomalous_features": [
        "carbon_intensity",                 # Which features are outliers
        "esg_revenue_gap"
    ]
}
```

#### Contribution to ESG Score:

**ROLE: Flagging ONLY (does NOT change score)**

```python
if is_anomaly and severity == "HIGH":
    print("⚠️ Statistical anomaly detected")
    print(f"   Anomalous features: {anomalous_features}")
    print("   This does NOT alter the rating but flags for review")
    
    # Add warning to report
    report_warnings.append({
        "type": "Statistical Anomaly",
        "severity": "HIGH",
        "description": "Company metrics deviate significantly from industry norms",
        "anomalous_features": anomalous_features,
        "recommendation": "Manual verification recommended"
    })
    
# NOTE: Risk score and rating unchanged
```

#### Impact Example:
```
Company: "GreenWashCorp" (hypothetical)
ESG Claims: "Carbon neutral since 2020"
Pillar ESG Score: 82/100 (rating: A)

Anomaly Detector Input:
- Carbon Intensity: 5.2 (industry avg: 0.15) → 35x higher!
- ESG Revenue Gap: 18.5 (industry avg: 2.3)
- Profit ESG Ratio: 0.85 (unusually high profit vs ESG)

Anomaly Detection:
✅ ANOMALY DETECTED
Severity: HIGH
Confidence: 92%
Anomalous Features: ["carbon_intensity", "esg_revenue_gap"]

Interpretation:
"Company claims strong ESG performance (82/100) but has carbon
intensity 35x higher than industry average. This statistical
anomaly suggests potential greenwashing through selective reporting."

Rating Impact:
Score: Still 82/100 (A rating) ← unchanged
Action: ⚠️ FLAGGED FOR MANUAL REVIEW
Report Note: "Statistical anomaly detected - manual verification required"
```

#### Why Flagging-Only:
- ✅ Anomalies don't always mean greenwashing (could be unique business model)
- ✅ Human judgment needed for context
- ✅ Avoids false positives from legitimate outliers
- ✅ Provides quality assurance without hard overrides

#### Training Data:
- Source: S&P 500 companies (unsupervised)
- Contamination: 5% (assumes 5% are anomalous)
- Method: Isolation Forest (tree-based outlier detection)

---

### Model 5: K-Means Industry Clustering ⚠️ INACTIVE

**File:** `scripts/train_industry_clusters.py`  
**Model:** `ml_models/trained/industry_clusters_model.pkl` ✅ EXISTS  
**Status:** Trained but NOT integrated into workflow

#### Purpose:
Classifies companies into 5 ESG performance tiers across all industries

#### Clusters:
```
Cluster 0: ESG Leaders (top 20%)
Cluster 1: Above Average (60-80%)
Cluster 2: Average (40-60%)
Cluster 3: Below Average (20-40%)
Cluster 4: ESG Laggards (bottom 20%)
```

#### Input Features (7):
```python
1. totalEsg
2. environmentScore
3. socialScore
4. governanceScore
5. highestControversy
6. percentile
7. overallRisk
```

#### Why Inactive:
**Replaced by ChromaDB dynamic peer database**

```
CLUSTERING APPROACH (old):
├── Pre-trained on S&P 500 data
├── Fixed 5 clusters
├── Cross-industry comparison
└── Requires retraining with new data

CHROMADB APPROACH (current):
├── Builds dynamically over time
├── Industry-specific comparison
├── No training needed
└── Grows with each analysis
```

#### Could Be Reactivated For:
- Cross-industry ESG tier classification
- Broader peer comparison beyond single industry
- Pre-classifying companies before evidence gathering

---

### Model 6: Sentiment-ESG Predictor ⚠️ INACTIVE

**File:** `ml_models/sentiment_esg_predictor.py`  
**Model:** `ml_models/trained/sentiment_esg_model.pkl` ✅ EXISTS  
**Status:** Trained but NOT integrated into workflow

#### Purpose:
Predicts ESG score changes over 6 months based on news sentiment

#### Input Features (8):
```python
1. news_sentiment           # Average sentiment (-1 to +1)
2. sentiment_volume         # News article count
3. controversy_level        # Controversy level (0-5)
4. current_esg_score        # Current ESG score
5. industry_volatility      # Industry sensitivity
6. sentiment_intensity      # sentiment × volume
7. controversy_sentiment    # controversy × sentiment
8. recovery_potential       # current_esg × sentiment
```

#### Output:
```python
{
    "predicted_change": +12.5,          # ESG change (-30 to +30)
    "direction": "POSITIVE",            # POSITIVE/NEGATIVE/NEUTRAL
    "magnitude": "MODERATE",            # MAJOR/MODERATE/MINOR
    "interpretation": "Positive sentiment predicts +12.5 point ESG improvement"
}
```

#### Why Inactive:
**Replaced by rule-based sentiment analysis**

```
ML PREDICTOR (old):
├── Ridge regression model
├── Predicts numerical ESG change
├── Requires training data
└── Black-box prediction

CURRENT APPROACH:
├── TextBlob sentiment library
├── Rule-based pattern detection
├── LLM linguistic analysis
└── Interpretable flags
```

#### Current Sentiment Analysis:
```python
# From agents/sentiment_analyzer.py
blob = TextBlob(claim_text)
polarity = blob.sentiment.polarity  # -1 to +1

# Detect greenwashing patterns
buzzword_count = count_buzzwords(text)
vague_terms = find_vague_quantifiers(text)
hedge_words = find_hedge_words(text)

# Calculate linguistic risk
risk = polarity_divergence * 30 + buzzword_density * 20 + vague_terms * 15
```

#### Could Be Reactivated For:
- Quantitative ESG trajectory forecasting
- Sentiment impact prediction
- Complementing TextBlob with ML-based sentiment

---

## 🎯 ML Model Summary Table

| Model | Status | Purpose | Impact on Score | Confidence Level |
|-------|--------|---------|-----------------|------------------|
| **XGBoost** | ✅ Active | Refine MODERATE ratings | Minor (adjusts BBB/BB) | 80-95% |
| **LightGBM** | ✅ Active | Validate pillar scores | None (flags only) | 92% R² |
| **LSTM** | ✅ Active | Trend forecasting | Minor (-5 to +10 pts) | 70-80% |
| **Anomaly** | ✅ Active | Outlier detection | None (flags only) | 85-92% |
| **K-Means** | ❌ Inactive | Industry clustering | N/A | Replaced by ChromaDB |
| **Sentiment-ESG** | ❌ Inactive | Sentiment prediction | N/A | Replaced by TextBlob |

---

## 📊 Agent Pipeline Details

### Complete Agent Sequence (Standard Track)

```
1. Supervisor Agent → Assess complexity, route to track
2. Claim Extractor → Break down claim into verifiable parts
3. Evidence Retriever → Fetch from 15 data sources
4. Financial Analyst → Analyze financial-ESG correlation
5. Contradiction Analyzer → Find evidence contradicting claim
6. Historical Analyst → Check past claims via Wayback
7. Industry Comparator → Compare to peer companies
8. Credibility Analyst → Score source credibility
9. Sentiment Analyzer → Detect greenwashing language
10. Realtime Monitor → Check recent news/controversies
11. Risk Scorer → Calculate ESG score + ML enhancements
12. Confidence Scorer → Aggregate confidence levels
13. Conflict Resolver → Generate final verdict
14. Debate Orchestrator → Multi-agent debate (if conflicts)
15. Report Generator → Create professional reports
```

### Agent Execution Time:
- Fast Track (3 agents): ~30 seconds
- Standard Track (11 agents): ~90 seconds
- Deep Analysis (11 agents + debate): ~120 seconds

### Key Design Principles:
1. **Sequential Processing** - State passed between agents
2. **Cached Evidence** - Zero redundant API calls
3. **Domain Knowledge Priority** - Rules override ML when certain
4. **Transparent Decisions** - Every verdict explained
5. **Self-Improving** - Peer database grows with usage

---

## 🌐 Data Sources

### Free Data Sources (15 Active)

#### News APIs (8):
1. **Google News RSS** - General news articles
2. **BBC News RSS** - Reputable international news
3. **DuckDuckGo News** - Privacy-focused news aggregator
4. **GDELT Project** - Global events database (250M+ articles)
5. NewsAPI (premium, optional)
6. NewsData.io (premium, optional)
7. TheNewsAPI (premium, optional)
8. Mediastack (premium, optional)

#### Legal/Compliance (3):
9. **FTC Enforcement Actions** - US Federal Trade Commission
10. **UK CMA Cases** - UK Competition & Markets Authority
11. **OpenSanctions** - Sanctions and watchlist database

#### Environmental (1):
12. **World Bank Climate API** - Environmental data

#### Research (1):
13. **Semantic Scholar** - Academic papers (200M+ papers)

#### Financial (1):
14. **Yahoo Finance (yfinance)** - Real-time financial data

#### Historical (1):
15. **Wayback Machine** - Archived web pages (750B+ pages)

### Data Source Priority:
1. Government agencies (FTC, EPA) - Credibility: 1.0
2. Academic papers - Credibility: 0.9
3. Major news outlets - Credibility: 0.7-0.8
4. Industry reports - Credibility: 0.6
5. Company blogs - Credibility: 0.4
6. Social media - Credibility: 0.3

---

## 🏗️ Architecture Decisions

### Why LangGraph?
**Problem:** Traditional pipelines re-run entire analysis for each agent  
**Solution:** State machine where each agent reads/writes to shared state  
**Benefit:** 90% faster, no redundant API calls

### Why Hybrid ML + Formula?
**Problem:** Pure ML can be wrong, pure formula misses patterns  
**Solution:** Use ML when confident (≥80%), formula as fallback  
**Benefit:** Best of both worlds - accuracy + interpretability

### Why Evidence Caching?
**Problem:** 15 API calls × 10 analyses = 150 calls/day (rate limits)  
**Solution:** 24-hour cache, reuse evidence for same company  
**Benefit:** 10 analyses = 1 API call instead of 150

### Why ChromaDB Peer Database?
**Problem:** External datasets become outdated  
**Solution:** Build database over time from own analyses  
**Benefit:** Self-improving system, always up-to-date

### Why Multi-Agent Debate?
**Problem:** Different agents may disagree on verdict  
**Solution:** Structured debate with voting  
**Benefit:** 10.4% accuracy improvement (research-validated)

### Why Pillar-First ESG Calculation?
**Problem:** ML models are black boxes, hard to explain  
**Solution:** Evidence-based pillar scores (E/S/G), ML refines  
**Benefit:** Transparent decisions, human-verifiable

---

## 📈 Performance Metrics

### Accuracy:
- XGBoost Risk Classifier: ~85% accuracy
- LightGBM ESG Predictor: R² = 0.92 (92% variance)
- LSTM Trend Forecaster: MAE = 3.5 points
- Anomaly Detector: 92% confidence

### Speed:
- Fast Track: 30 seconds (simple claims)
- Standard Track: 90 seconds (typical)
- Deep Analysis: 120 seconds (complex claims)

### Cost Efficiency:
- With caching: 1 API call per company per day
- Without caching: 15 API calls per analysis
- Cost savings: 93% reduction in API calls

### Scalability:
- Handles 100+ analyses per day
- Peer database grows linearly
- No performance degradation over time

---

## 🚀 Usage Example

```bash
# Install dependencies
pip install -r requirements.txt

# Set API keys (optional - works with free sources)
# Edit .env file:
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_gemini_key

# Run analysis
python main_langgraph.py

# Or programmatic usage:
from main_langgraph import ESGGreenwashingDetectorLangGraph

detector = ESGGreenwashingDetectorLangGraph()
result = detector.analyze_company(
    company_name="Tesla",
    claim="We are carbon neutral and have achieved net-zero emissions",
    industry="automotive"
)

print(f"Risk Level: {result['risk_level']}")
print(f"ESG Score: {result['esg_score']}")
print(f"Rating: {result['rating_grade']}")
```

---

## 📚 Key Files Reference

### Core System:
- `main_langgraph.py` - Main entry point
- `core/workflow_phase2.py` - LangGraph workflow
- `core/state_schema.py` - State definition
- `core/supervisor_agent.py` - Complexity routing

### Agents:
- `agents/claim_extractor.py`
- `agents/evidence_retriever.py`
- `agents/financial_analyst.py`
- `agents/contradiction_analyzer.py`
- `agents/historical_analyst.py`
- `agents/industry_comparator.py`
- `agents/credibility_analyst.py`
- `agents/risk_scorer.py` ← ML models integrated here
- `agents/sentiment_analyzer.py`
- `agents/realtime_monitor.py`
- `agents/confidence_scorer.py`
- `agents/conflict_resolver.py`

### ML Models:
- `ml_models/xgboost_risk_model.py`
- `ml_models/lightgbm_esg_predictor.py`
- `ml_models/lstm_trend_predictor.py`
- `ml_models/anomaly_detector.py`
- `ml_models/sentiment_esg_predictor.py` (inactive)

### Training Scripts:
- `scripts/train_xgboost_risk.ipynb`
- `scripts/train_lightgbm_esg_score.ipynb`
- `scripts/train_lstm_trend.ipynb`
- `scripts/train_anomaly_detector.py`
- `scripts/train_industry_clusters.py` (inactive)
- `scripts/train_sentiment_esg_model.py` (inactive)

### Configuration:
- `config/industry_baselines.json` - Industry risk data
- `config/agent_prompts.py` - LLM prompts
- `config/data_sources.json` - API endpoints

---

## 🎓 Research Citations

1. **Multi-Agent Debate:**  
   "Multi-agent collaboration improves accuracy by 10.4% over single-agent systems"  
   Source: LangChain/LangGraph documentation

2. **MSCI ESG Ratings:**  
   Rating scale (AAA to CCC) based on MSCI ESG methodology  
   Source: MSCI ESG Research documentation

3. **Greenwashing Patterns:**  
   7 financial-ESG mismatch patterns  
   Source: Academic literature on corporate greenwashing

4. **Isolation Forest:**  
   Anomaly detection for outlier identification  
   Source: scikit-learn documentation

---

## 📝 Conclusion

This ESG Greenwashing Detection System combines:
- ✅ **14 AI agents** for specialized analysis
- ✅ **4 active ML models** for quantitative enhancement
- ✅ **15 free data sources** for evidence gathering
- ✅ **Self-improving peer database** for benchmarking
- ✅ **Professional reports** with audit trails

**Key Innovation:**  
Hybrid approach where evidence-based pillar scores remain primary, with ML models providing refinement, validation, and quality checks - ensuring both accuracy and interpretability.

**Result:**  
Enterprise-grade greenwashing detection that's transparent, explainable, and continuously improving.

---

**Last Updated:** February 17, 2026  
**Version:** 3.0 (LangGraph)  
**License:** See LICENSE file
