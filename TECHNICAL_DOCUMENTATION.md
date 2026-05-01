# ESGLens — Institutional-Grade ESG Intelligence Platform
## Technical Architecture & System Documentation
**Version 3.0 | May 2026 | Confidential**

---

## 1. Executive Overview

ESGLens is an **agentic AI platform** that deterministically verifies ESG (Environmental, Social, Governance) claims made by public and private companies. It ingests raw ESG disclosures — annual reports, sustainability reports, SEBI BRSR filings, SEC 10-Ks, and real-time news — runs them through a 30-node multi-agent LangGraph pipeline, and outputs audit-ready, source-cited risk scores with full explainability.

**Core value proposition:**
- Detect greenwashing, greenwishing, and greenhushing before capital is deployed
- Replace ESG analyst hours with a deterministic, traceable AI pipeline
- Produce institutional-grade reports that satisfy SEBI, CSRD, SEC Climate, and UK FCA requirements

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER-FACING LAYER                           │
│   React Frontend (Port 3001)  ←→  ESG Analyst Copilot Chatbot  │
└───────────────────────┬─────────────────────────────────────────┘
                        │ REST / WebSocket
┌───────────────────────▼─────────────────────────────────────────┐
│              FastAPI Backend  (server.py : Port 8000)           │
│   /api/analyse  │  /api/analysis/{id}  │  /ws/pipeline/{id}     │
└───────────────────────┬─────────────────────────────────────────┘
                        │ subprocess
┌───────────────────────▼─────────────────────────────────────────┐
│          LangGraph Orchestration Engine (main_langgraph.py)     │
│          ESGGreenwashingDetectorLangGraph v3.0                  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   Fast Track      Standard Track   Deep Analysis
   (3 agents)      (30 agents)      (30 + Debate)
```

### 2.1 Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React + Vite + TypeScript | Dashboard & Copilot UI |
| API Server | FastAPI + Uvicorn | REST endpoints + WebSocket streaming |
| Orchestration | LangGraph 0.2+ | Stateful multi-agent DAG |
| LLMs | Gemini 2.5 Flash/Pro, Llama-3.3-70B (Groq), OpenRouter free tier | NLP analysis, claim decomposition |
| ML Models | XGBoost, LightGBM, TensorFlow/Keras | Risk scoring, pattern detection |
| NLP | ClimateBERT (HuggingFace), SHAP, LIME | ESG text classification + explainability |
| PDF Parsing | pdfplumber, PyMuPDF, Camelot | Annual/sustainability report extraction |
| Web Scraping | Playwright, BeautifulSoup4 | IR page scraping |
| Vector DB | ChromaDB | Evidence caching |
| Knowledge Graph | Neo4j + LangChain Experimental | Company fact graph persistence |
| Data APIs | WBA, WRI Aqueduct 4.0, SEC EDGAR, NewsAPI | External benchmarks |

---

## 3. Data Ingestion — Where Data Comes From

### 3.1 Primary Source: Official Company Reports

**File:** `utils/company_report_fetcher.py` | `utils/report_discovery.py`

The system automatically fetches PDF reports from 50+ company investor relations pages:

```
IR Page Discovery → PDF Link Scraping → Download & Cache → Parse & Extract
```

**Extraction pipeline:**
1. **Playwright** renders JavaScript-heavy IR pages and extracts all PDF links
2. **BeautifulSoup** serves as fallback for static pages
3. PDFs are downloaded, MD5-hashed, and cached for 5 days
4. **pdfplumber** extracts text + tables from first 50 pages
5. **Camelot** extracts structured tables for precise emissions figures
6. Regex + LLM parse out: Scope 1/2/3 emissions, renewable energy %, board diversity, net zero targets, employee metrics, water/waste data

**Report types ingested:**
- Annual Reports / Integrated Reports (10-K, 20-F)
- Sustainability / ESG Reports
- BRSR (Business Responsibility & Sustainability Report — SEBI mandate)
- CSR Reports

### 3.2 Real-Time Evidence Layer

**File:** `agents/evidence_retriever.py` | `utils/free_data_sources.py`

- **NewsAPI** — sector-specific ESG events (NZBA withdrawals, regulatory actions)
- **DuckDuckGo Lite** — web search for ESG controversies and filings
- **RSS Feeds** — SEBI, SEC EDGAR, EU CSRD, UK FCA live alerts
- **arXiv** — academic research on greenwashing methodology
- **Google Scholar** — peer-reviewed ESG studies via `scholarly`

### 3.3 Regulatory Data Sources

**File:** `utils/regulatory_fetchers.py`

| Source | Data | Jurisdiction |
|---|---|---|
| SEC EDGAR | 10-K, DEF 14A, Form SD filings | USA |
| SEBI | BRSR filings, sustainability disclosures | India |
| BSE/NSE | Listed company disclosures | India |
| EU EUR-Lex | CSRD compliance data | EU |
| UK FCA | Anti-greenwashing rule enforcement | UK |
| CDP | Carbon Disclosure Project scores | Global |

### 3.4 External ESG Benchmarks

**File:** `core/esg_data_apis.py`

- **WBA (World Benchmarking Alliance)** — SDG2000 company scores; social, governance, environment pillars
- **WRI Aqueduct 4.0** — 13 water risk indicators (physical, regulatory, reputational)
- **SEC DEF 14A** — CEO pay ratio, board diversity %, executive ESG comp links
- **SEC Form SD** — conflict minerals and human rights due diligence

### 3.5 Indian-Specific Data

**File:** `utils/indian_data_sources.py` | `utils/indian_financial_data.py`

- **Screener.in** — revenue, EBITDA, net profit for NSE/BSE companies
- **Yahoo Finance India** — real-time financial metrics
- **NSE/BSE APIs** — price, market cap, institutional holdings
- **CPCB (Central Pollution Control Board)** — environmental compliance violations
- **Ministry of Corporate Affairs** — CSR spend compliance

---

## 4. The LangGraph Pipeline — How It Works

**File:** `core/workflow_phase2.py`

### 4.1 Complexity Router

Every analysis begins with a **Supervisor Agent** that assesses claim complexity and routes to one of three tracks:

```
assess_complexity → classify_workflow → [Fast | Standard | Deep]
```

| Track | Agents | Use Case |
|---|---|---|
| Fast Track | 5 nodes | Simple, verifiable claims |
| Standard Track | 30 nodes | Complex ESG claims |
| Deep Analysis | 30 nodes + Multi-Agent Debate | High-stakes, contested claims |

### 4.2 Standard/Deep Track — Full Pipeline (30 Nodes in Order)

```
1.  claim_extraction          → Parse and normalize the ESG claim
2.  claim_decomposition       → Break compound claims into sub-claims
3.  evidence_retrieval        → Multi-source evidence gathering
4.  adversarial_triangulation → Supporting vs. contradicting evidence balance
5.  report_discovery          → Find official company ESG reports
6.  report_downloader         → Download PDFs from IR pages
7.  report_parser             → Extract text, tables, metrics from PDFs
8.  report_claim_extractor    → Pull year-tagged claims from reports
9.  carbon_extraction         → Scope 1/2/3 with GHG Protocol validation
10. carbon_pathway_analysis   → IEA NZE 1.5°C pathway alignment
11. greenwishing_detection    → Greenwishing + Greenhushing + Tunnel Vision
12. regulatory_scanning       → Multi-jurisdiction compliance check
13. climatebert_analysis      → ClimateBERT ESG text classification
14. temporal_analysis         → Historical ESG trend analysis
15. inject_temporal_violations→ Inject past violations into evidence
16. contradiction_analysis    → Identify claim-evidence contradictions
17. esg_mismatch_detection    → Promise vs. actual gap scoring
18. peer_comparison           → Industry peer benchmarking
19. credibility_analysis      → Source credibility scoring
20. sentiment_analysis        → Media sentiment divergence
21. realtime_monitoring       → Live news and regulatory alerts
22. social_analysis           → Labour, human rights, community pillar
23. governance_analysis       → Board, ethics, exec comp pillar
24. temporal_consistency      → Year-over-year consistency check
25. commitment_ledger         → Longitudinal commitment revision tracking
26. fact_graph                → Neo4j ESG fact graph construction
27. risk_scoring              → XGBoost/LightGBM greenwashing risk score
28. explainability            → SHAP/LIME feature attribution
29. adversarial_audit         → Multi-agent coordination diagnostics
30. confidence_scoring        → Bayesian confidence with abstention logic
    verdict_generation        → Final institutional verdict
    [debate_node]             → (Deep track only) Multi-agent debate
    report_generation         → Professional report artifact
```

### 4.3 Shared State Object

All 30 agents read from and write to a single **ESGState** TypedDict (`core/state_schema.py`). Key fields:

```python
class ESGState(TypedDict):
    company: str
    claim: str
    industry: str
    evidence: List[Dict]           # All gathered evidence
    carbon_extraction: Dict        # Scope 1/2/3 + pathway
    greenwishing_analysis: Dict    # Greenwishing/hushing/tunnel vision
    regulatory_compliance: Dict    # Multi-jurisdiction compliance
    climatebert_analysis: Dict     # NLP climate claim classification
    commitment_ledger: Dict        # Historical commitment revisions
    risk_scoring: Dict             # Final GW risk score + ESG score
    explainability_report: Dict    # SHAP/LIME attributions
    final_verdict: Dict            # Institutional verdict
    esg_score_lineage: Dict        # Full scoring audit trail
```

A custom **deduplication reducer** (`_dedupe_agent_outputs`) prevents state explosion across 30 pipeline nodes.

---

## 5. Key Analytical Engines

### 5.1 Carbon Extraction Engine

**File:** `agents/carbon_extractor.py` (189 KB — most complex agent)

**Extraction priority chain:**
```
1. Camelot table extraction (PDF tables) — highest precision
2. Deterministic regex over report chunks — structured patterns
3. LLM extraction (Gemini/Llama) — free-text parsing
4. CDP public data fallback
5. Curated 2024 disclosure database (cited, labelled)
6. Industry baseline estimate (flagged as LOW confidence)
```

**Industry-aware validation:** The system maintains per-sector magnitude bounds (min/max tCO2e) for Scope 1, 2, and 3. Values outside bounds are rejected as parser artifacts.

**Scope 3 boundary awareness:** Distinguishes full-boundary vs. narrow-boundary disclosures. For example, an automotive company reporting only 1M–50M tCO2e for Scope 3 is flagged as likely missing **Category 11 (Use of sold products)** — typically 70–85% of automotive lifecycle emissions.

**Financed emissions detection:** For banking/financial sector, the system detects **Carbon Tunnel Vision** — when a bank reports only operational Scope 1/2 while omitting Category 15 (financed/portfolio emissions).

### 5.2 Greenwishing & Greenhushing Detector

**File:** `agents/greenwishing_detector.py`

Four detection modules with weighted scoring:

| Module | Weight | What It Detects |
|---|---|---|
| Greenwishing | 30% | Unfunded aspirational goals, vague timelines, no CAPEX |
| Greenhushing | 30% | Missing mandatory disclosures, suppression language |
| Selective Disclosure | 25% | Cherry-picking, boundary manipulation, baseline gaming |
| Carbon Tunnel Vision | 15% | Narrow ESG focus, missing financed emissions |

**BRSR compliance check:** For Indian companies, the system checks all 8 mandatory BRSR fields. >50% missing fields triggers a HIGH severity greenhushing finding.

### 5.3 Institutional Verification Engine (10-Rule Framework)

**File:** `core/institutional_verifier.py`

| Rule | Description |
|---|---|
| 1 | Dual-source data requirement — minimum 2 independent sources |
| 2 | Four-tier source hierarchy (Tier 1: Regulatory → Tier 4: General web) |
| 3 | Per-claim verification: VERIFIED / PARTIALLY_VERIFIED / UNVERIFIED / CONTRADICTED |
| 4 | Multi-provider rating divergence detection (>25 point spread = flag) |
| 5 | Missing data = UNKNOWN, never zero |
| 6 | Confidence-driven abstention: <60% confidence → NO DECISION |
| 7 | Carbon/climate validation — SBTi status, net-zero credibility |
| 8 | Temporal consistency — YoY changes >40% flagged |
| 9 | Controversy integration — regulatory fines, litigation |
| 10 | Final institutional output with full evidence + source breakdown |

**Source Tier Definitions:**
- **Tier 1:** `sec.gov`, `sebi.gov.in`, `europa.eu`, `mca.gov.in`, `nseindia.com`
- **Tier 2:** `msci.com`, `sustainalytics.com`, `cdp.net`, `sbti.org`, `spglobal.com`
- **Tier 3:** `reuters.com`, `ft.com`, `wsj.com`, `theguardian.com`, `wri.org`
- **Tier 4:** General web (conclusions based solely on Tier 4 are rejected)

### 5.4 Risk Scoring Engine

**File:** `agents/risk_scorer.py`

**Five-variable Greenwashing Risk Formula:**

```
GW_Score = f(C, P, R, D, T)

Where:
  C = Claim Intensity Score      (claim language strength)
  P = Pathway Credibility Score  (funded implementation evidence)
  R = Controversy Risk Score     (regulatory actions, media hits)
  D = Disclosure Quality Score   (completeness, consistency)
  T = Temporal Escalation Score  (YoY changes, sudden improvements)
```

**Scoring weights** (configurable in `config/settings.py`):
```
claim_verification:   25%
evidence_quality:     20%
source_credibility:   20%
sentiment_divergence: 15%
historical_pattern:   10%
contradiction_severity: 10%
```

**ML models used:**
- **XGBoost** — primary risk classification
- **LightGBM** — ensemble cross-check
- **TensorFlow/Keras** — deep pattern recognition

**SHAP/LIME explainability:** Every risk score ships with top-5 feature attributions so users understand *why* a score was assigned.

### 5.5 Carbon Pathway Modeller

**File:** `agents/carbon_pathway_modeller.py`

- Aligns company reduction trajectories against **IEA Net Zero Emissions (NZE) 2050** pathway
- Computes **CAGR of disclosed emissions** from multi-year extraction data
- Flags `PATHWAY_MISALIGNED` when gap vs. IEA NZE exceeds 20%
- Detects targets >30 years away as `NET_ZERO_TARGET_VERY_DISTANT`

### 5.6 Commitment Ledger

**File:** `agents/temporal_consistency_agent.py` | `core/agent_wrappers.py`

Tracks ESG commitments across years — detects:
- **Commitment downgrades** (e.g., "net zero by 2040" silently changed to "net zero by 2050")
- **Target rollbacks** after leadership changes
- **Inconsistent reporting boundaries** across fiscal years
- Uses normalized string comparison to detect substantive changes vs. minor wording shifts

### 5.7 Multi-Agent Debate (Deep Track)

**File:** `core/debate_orchestrator.py`

When the Deep Analysis track is selected, a **Debate Orchestrator** collects outputs from all agents, detects conflicting verdicts, and forces a structured resolution:

```
All agent outputs → Conflict detection → Debate round → Consensus verdict
```

---

## 6. How the System is Audit-Proof

### 6.1 Complete Evidence Provenance

Every piece of evidence in the final report carries:
- Source URL
- Source type (regulatory filing / ESG rating agency / news / general web)
- Source tier (1–4)
- Timestamp of retrieval
- Stance (supporting / contradicting / neutral)

### 6.2 Score Lineage

A dedicated `esg_score_lineage` object is saved alongside every report. It records:
- Raw input values for each of the 5 formula variables (C, P, R, D, T)
- Weights applied
- Pre- and post-calibration scores
- Which agents contributed which sub-scores

### 6.3 Deterministic Abstention

If evidence is insufficient (confidence <60%), the system outputs **"INSUFFICIENT EVIDENCE — NO DECISION"** rather than fabricating a verdict. This is a hard rule enforced in `core/institutional_verifier.py`.

### 6.4 Tier-4-Only Rejection

If all supporting evidence for a claim comes from Tier 4 sources (general web, unverified blogs), the system automatically downgrades the verdict to **UNVERIFIED** — preventing unverified web content from driving institutional decisions.

### 6.5 Multi-Provider Cross-Check

Scores from MSCI, Sustainalytics, S&P, and Bloomberg are cross-checked. A spread >25 points triggers a **RATING DIVERGENCE** flag in the report.

### 6.6 Output Artifacts (Per Analysis)

```
reports/
├── ESG_Report_{Company}_{timestamp}.txt       ← Full narrative report
├── ESG_Report_{Company}_{timestamp}.json      ← Structured JSON export
├── ESG_Report_{Company}_{timestamp}_brief.json ← Investor one-pager
└── debug_esg_lineage_{Company}.json           ← Score audit trail
```

---

## 7. API Reference

### 7.1 REST Endpoints (Port 8000)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/analyse` | Start analysis → returns `analysis_id` |
| GET | `/api/analysis/{id}` | Poll status + results |
| GET | `/api/reports` | List saved reports |
| POST | `/api/chatbot/answer` | ESG Analyst Copilot query |
| GET | `/health` | Service health check |
| WS | `/ws/pipeline/{id}` | Real-time log streaming |

### 7.2 Analysis Request Schema

```json
{
  "company": "Tesla",
  "claim": "Carbon neutral by 2030",
  "industry": "Automotive"
}
```

### 7.3 Analysis Response Schema (Abbreviated)

```json
{
  "company": "Tesla",
  "risk_level": "HIGH",
  "greenwashing_risk_score": 72,
  "esg_score": 48,
  "confidence_pct": 78.4,
  "institutional_verdict": "CLAIM PARTIALLY VERIFIED",
  "carbon_snapshot": {
    "scope1_tco2e": 302000,
    "scope2_tco2e": 677000,
    "scope3_tco2e": 54967000,
    "sbti_status": "Targets set",
    "pathway_alignment": "MISALIGNED"
  },
  "top_risks": [...],
  "enforcement": { "active_count": 0 },
  "source_tier_breakdown": {
    "tier1_regulatory": 4,
    "tier2_esg_agencies": 2,
    "tier3_media": 8,
    "tier4_general_web": 3
  }
}
```

---

## 8. ESG Analyst Copilot

**Files:** `chatbot_backend/`

An **ESG Analyst Copilot** is embedded in the platform — a deterministic query engine over generated reports.

**Architecture (no RAG, no vector search):**
```
Question → Intent Detection → Section/Metric Match → Context Selection → LLM → Answer
```

**Intent categories:**
- `SCORE` — direct score lookup (deterministic, no LLM)
- `RISK` — risk driver explanation
- `CARBON` — emissions data queries
- `REGULATORY` — compliance status
- `COMPARISON` — peer/industry comparison
- `SCORE_EXPLANATION` — why did the system score this way?

**LLM fallback chain:** Gemini 2.5 Flash → Groq Llama-3.3-70B

**Out-of-scope guardrail:** Non-ESG questions are blocked before reaching the LLM.

---

## 9. Regulatory Framework Coverage

| Framework | Jurisdiction | Coverage |
|---|---|---|
| SEBI BRSR | India | Mandatory fields, disclosure completeness |
| MCA Companies Act | India | CSR spend, board compliance |
| CPCB / EPA | India | Environmental violations |
| RBI Green Finance | India | Climate risk in lending |
| GHG Protocol | Global | Scope 1/2/3 accounting |
| Science Based Targets (SBTi) | Global | Net-zero pathway validation |
| GRI Standards | Global | Disclosure completeness |
| CDP | Global | Carbon disclosure scoring |
| EU CSRD | European Union | Double materiality, ESRS |
| EU Taxonomy | European Union | Green activity classification |
| SEC Climate Rules | USA | Climate risk disclosures |
| UK FCA Anti-Greenwashing | UK | Marketing claim validation |
| TCFD | Global | Climate financial disclosures |
| NZBA | Global | Net-Zero Banking Alliance commitments |

---

## 10. LLM Architecture & Cost Model

### 10.1 Task-Specific Model Routing

**File:** `core/llm_router.py` | `config/settings.py`

```
Task                        → Model
─────────────────────────────────────────────────────
Web search summarisation    → Llama-3.3-70B (free tier)
Contradiction detection     → Hermes-3-Llama-405B (free)
Sub-indicator scoring       → Mistral-Small-24B (free)
Carbon data parsing         → Mistral-Small-24B (free)
Full report narrative       → Hermes-3-Llama-405B (free)
High-stakes decisions       → Gemini 2.5 Pro (paid)
Fast operations             → Llama-3.1-8B-Instant (Groq)
```

All models operate through **OpenRouter** with automatic fallback chains — the system never blocks on a single provider failure.

### 10.2 Caching

- **LLM response cache** (`core/llm_cache.py`) — deduplicates identical prompts within a session
- **Evidence cache** (`core/evidence_cache.py`) — ChromaDB vector store for retrieved evidence
- **Report cache** — MD5-keyed PDF cache with 5-day TTL

---

## 11. Security & Data Integrity

| Control | Implementation |
|---|---|
| No data storage of sensitive inputs | All analysis runs in memory; only artifacts are persisted |
| API key isolation | Keys loaded from `.env`; never logged |
| Timeout protection | Configurable `ESG_WORKFLOW_TIMEOUT` (default 30 min) with graceful partial-result fallback |
| UTF-8 enforcement | All I/O explicitly reconfigured on startup to prevent encoding corruption |
| Structured output validation | Pydantic models validate all API inputs/outputs |
| Partial result on timeout | `ESG_ALLOW_PARTIAL_ON_TIMEOUT=true` returns bounded result rather than failing silently |

---

## 12. Deployment Architecture

```
┌──────────────────────┐     ┌──────────────────────┐
│  React Frontend      │     │  ESGLens API         │
│  Vite Dev Server     │────▶│  FastAPI + Uvicorn   │
│  Port: 3001          │     │  Port: 8000          │
└──────────────────────┘     └──────────┬───────────┘
                                        │ subprocess
                             ┌──────────▼───────────┐
                             │  LangGraph Pipeline  │
                             │  main_langgraph.py   │
                             │  30-agent DAG        │
                             └──────────┬───────────┘
                                        │
                   ┌────────────────────┼──────────────────────┐
                   ▼                    ▼                       ▼
          ┌──────────────┐   ┌──────────────────┐   ┌─────────────────┐
          │  ChromaDB    │   │  Neo4j           │   │  Reports/       │
          │  Evidence    │   │  Knowledge Graph │   │  Cache (disk)   │
          │  Cache       │   │  (fact graph)    │   │                 │
          └──────────────┘   └──────────────────┘   └─────────────────┘
```

### Environment Variables

```bash
GROQ_API_KEY=...           # Groq Llama inference
GEMINI_API_KEY=...         # Google Gemini
OPENROUTER_API_KEY=...     # Multi-model routing
NEWS_API_KEY=...           # NewsAPI
WBA_API_KEY=...            # World Benchmarking Alliance
ESG_WORKFLOW_TIMEOUT=1800  # 30-minute analysis window
ESG_ALLOW_PARTIAL_ON_TIMEOUT=1
USE_LANGGRAPH=true
CLIMATEBERT_ENABLED=true
SHAP_ENABLED=true
DEFAULT_JURISDICTION=India
```

---

## 13. Competitive Differentiation

| Capability | ESGLens | Traditional ESG Tools |
|---|---|---|
| Real-time claim verification | ✅ Live multi-source | ❌ Periodic updates |
| Greenwishing detection | ✅ 4-module detector | ❌ Not available |
| Source tier hierarchy | ✅ 4-tier, rejection logic | ❌ Flat weighting |
| Confidence-driven abstention | ✅ <60% → NO DECISION | ❌ Always outputs score |
| Multi-agent debate | ✅ Conflict resolution | ❌ Single model |
| BRSR / Indian compliance | ✅ Native support | ❌ Minimal |
| Carbon pathway alignment | ✅ IEA NZE 1.5°C | ❌ Not available |
| Financed emissions detection | ✅ Category 15 explicit | ❌ Not available |
| SHAP explainability | ✅ Per-feature attribution | ❌ Black box |
| Investor one-pager | ✅ Auto-generated brief | ❌ Manual |
| Open architecture | ✅ OSS stack | ❌ Proprietary |

---

## 14. Performance Benchmarks

| Metric | Value |
|---|---|
| Average analysis time | 3–8 minutes (Standard Track) |
| Evidence sources per analysis | 15–40 documents |
| Agents executed | 30 (Standard/Deep) |
| PDF pages parsed per run | Up to 50 pages per report |
| LLM calls per analysis | 12–25 (task-routed) |
| Report artifacts generated | 3–4 files (TXT, JSON, Brief, Lineage) |
| Cache hit rate (repeat companies) | ~70% (5-day TTL) |

---

## 15. Roadmap

| Phase | Feature | Status |
|---|---|---|
| v3.0 | 30-agent LangGraph pipeline | ✅ Live |
| v3.0 | Institutional 10-rule verifier | ✅ Live |
| v3.0 | ClimateBERT + SHAP explainability | ✅ Live |
| v3.1 | Neo4j persistent knowledge graph | 🔄 In progress |
| v3.1 | SFDR / Article 9 fund screening | 📋 Planned |
| v3.2 | Portfolio-level ESG aggregation | 📋 Planned |
| v3.2 | API-first SaaS deployment | 📋 Planned |
| v4.0 | Agentic self-correction loop | 📋 Planned |

---

*Document generated: May 2026 | ESGLens v3.0 | Confidential*
