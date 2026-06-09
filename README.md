# ESGLens — AI-Powered ESG Greenwashing Detection Engine

> **"Not a rating agency. Not a scoring platform. An AI-powered audit engine."**

ESGLens is a multi-agent AI system that analyzes corporate ESG (Environmental, Social, Governance) claims, detects greenwashing, and produces audit-grade reports with full evidence traceability. It runs 36 specialized AI agents against 28+ live data sources and returns a calibrated Greenwashing Risk Score in ~15 minutes per company.

---

## Table of Contents
- [What It Does](#what-it-does)
- [Key Features](#key-features)
- [Architecture Overview](#architecture-overview)
- [Agent Pipeline](#agent-pipeline)
- [Data Sources](#data-sources)
- [ML Models](#ml-models)
- [Output Formats](#output-formats)
- [Deployment Modes](#deployment-modes)
- [Quick Start](#quick-start)
- [Validated Companies](#validated-companies)

---

## What It Does

You provide one company name and one ESG claim. ESGLens:
1. Retrieves live evidence from 28+ external sources simultaneously
2. Runs 36 specialized AI agents to extract, analyze, and score
3. Returns a **Greenwashing Risk Score (0–100)** with a full, reproducible evidence chain
4. Generates three outputs: audit-ready text report, machine-readable JSON, and an AI chatbot interface

---

## Key Features

### 🔍 1. Multi-Agent Agentic Pipeline (LangGraph)
- Built on **LangGraph** with a state machine that dynamically routes each analysis through one of three tracks based on claim complexity:
  - **Fast Track** (3 agents) — simple, low-complexity claims
  - **Standard Track** (30+ agents) — full pipeline with parallel analytics fanout
  - **Deep Analysis Track** (30+ agents + Multi-Agent Debate) — high-complexity, contested claims
- A **Supervisor Agent** assesses claim complexity and routes automatically
- **Parallel Analytics Fanout**: 10 independent agents run concurrently in a ThreadPoolExecutor, cutting wallclock time dramatically
- Configurable timeout (`ESG_WORKFLOW_TIMEOUT`) with graceful partial-result fallback

### 📋 2. Claim Extraction & Decomposition
- **ClaimExtractor**: Parses the input ESG claim into structured, machine-readable sub-claims (intensity, scope, timeframe, pillar)
- **ClaimDecomposer**: Breaks compound claims into atomic sub-claims and surfaces internal tensions/contradictions within the claim itself
- Claim Intensity Scoring: quantifies how bold/specific a claim is (0–100), directly feeding the GW formula
- **SURE-RAG Abstention Layer**: Per-sub-claim evidence gating — if fewer than 2 independent sources or fewer than 1 Tier-1/2 source are found, the system abstains rather than guessing

### 🌐 3. Evidence Retrieval (28+ Live Sources)
- Simultaneously queries: NewsAPI, Reuters, Google News, Google Scholar, DuckDuckGo
- **SEC EDGAR** — XBRL filings, DEF 14A proxy statements, 10-K annual reports
- **CDP** (Carbon Disclosure Project) public data
- **SBTi** (Science-Based Targets initiative) registry — 14,900+ entries scanned
- **UN Global Compact** participants directory
- **GRI** (Global Reporting Initiative) database
- **OpenSanctions** — corruption and sanctions screening
- **InfluenceMap** — climate lobbying records
- **EPA ECHO** — US environmental violations database
- **CourtListener** — US litigation docket search
- **Indian Kanoon** — Indian court case search
- **GLEIF** — Legal Entity Identifier (LEI) registry for subsidiary mapping
- **Climate TRACE** — asset-level satellite-verified emissions
- **GDELT** — global news event database
- **UK Companies House**, **EU ESEF** XBRL filings API
- **WBA** (World Benchmarking Alliance) — SDG2000 benchmark scores
- **WRI Aqueduct 4.0** — physical/regulatory/reputational water risk (13 indicators)
- **PCAF** — financed emissions standards
- Adversarial search channel specifically hunting for lawsuits, rulings, NGO investigations

### ⚖️ 4. Adversarial Evidence Triangulation
- **AdversarialValidator**: Tests whether claims survive independent third-party scrutiny, or only appear in company-produced documents
- Evidence is tagged on entry with a **credibility weight**:
  - Government enforcement: 0.95
  - NGO/academic: 0.90
  - Tier-1 financial media: 0.85
  - Company-produced documents: significantly lower
- Company's own sustainability reports carry ~⅓ the weight of a government filing

### 🧮 5. Carbon Emissions Extraction & Validation
- **CarbonExtractor**: Extracts Scope 1, 2, and 3 emissions from PDF reports, evidence snippets, and CDP disclosures
  - Aligned with **GHG Protocol**, **CDP**, **TCFD**, and **SEBI BRSR** (India)
  - Per-category audit of all 15 GHG Protocol Scope 3 categories
  - Boundary classification: FULL / PARTIAL / PARTIAL_INFERRED
  - Unit normalization across scales (tCO2e → Gt CO2e)
  - Industry-specific magnitude floors and ceilings to reject parser artifacts
- **CarbonDataValidator**: Cross-validates extracted values against known industry ranges
- **Scope 3 Boundary Analysis**: Flags when companies exclude material categories (e.g., Cat 11 Use-of-Sold-Products for automakers)
- Curated 2024 public-disclosure fallback database for 20+ bellwether companies (Tesla, Shell, JPMorgan, Volkswagen, Microsoft, Apple, etc.)
- Backfill logic for Scope 1+2 combined disclosures

### 🌡️ 6. Carbon Pathway Modelling (1.5°C Alignment)
- **CarbonPathwayModeller**: Checks whether a company's claimed reduction trajectory is physically consistent with IEA Net Zero Emissions by 2050 (NZE) scenario
- Calculates: required annual reduction rate vs. company-implied rate
- IPCC carbon budget tracking — flags when a company's projected cumulative emissions exceed its allocated share
- Outputs: pathway gap %, alignment status (ON_TRACK / BELOW_PACE / IPCC_BUDGET_EXCEEDED), and carbon budget years remaining
- Structural penalty applied when pathway gap > 30% (adds directly to GW score)

### 🌿 7. Greenwashing / Greenwishing / Greenhushing Detection
- **GreenwishingDetector**: Identifies three distinct deception archetypes:
  - **Greenwashing** — actively misleading claims contradicted by evidence
  - **Greenwishing** — sincere but unfunded aspirational targets ("we aim to," "where feasible")
  - **Greenhushing** — selectively going quiet on areas of poor performance
- Detects: vague language patterns, absence of funded roadmaps, selective disclosure, carbon tunnel vision
- Produces a Deception Risk Score (0–100) with per-tactic breakdown

### 📡 8. Multi-Jurisdiction Regulatory Scanning
- **RegulatoryHorizonScanner** and **MultiJurisdictionRegulatoryScanner** simultaneously check:
  - **SEC** (US Securities and Exchange Commission)
  - **EU CSRD** (Corporate Sustainability Reporting Directive)
  - **UK FCA** Anti-Greenwashing Rule
  - **Indian SEBI BRSR** (Business Responsibility and Sustainability Report)
  - EU Taxonomy Regulation, EU ESEF
  - GHG Protocol Corporate Standard
  - TCFD-aligned Climate Disclosure
  - UN Global Compact, GRI Standards
  - CDP, SBTi registry
- Active enforcement / litigation detection with source URLs
- Known-cases registry with curated enforcement history (Shell Hague ruling, etc.)
- **LitigationResolver**: Resolves and updates known litigation outcomes (e.g., overturned rulings)

### 🕒 9. Temporal Consistency Analysis
- **TemporalConsistencyAgent**: Checks whether a company is moving goalposts year-over-year
- Detects: claims that strengthen while actual emissions stay flat; targets that weaken over time; past violations that contradict current pledges
- **HistoricalAnalyst**: Tracks historical ESG pattern analysis and past violations
- **PromiseLedger / CommitmentLedger**: Longitudinal ledger of all ESG commitments and revisions across time

### 🏭 10. Pillar-Based ESG Scoring (E / S / G)
- Weighted, industry-specific scoring across Environmental, Social, and Governance pillars
- SASB-inspired materiality weighting — different industries get different E/S/G weights
- **Materiality Profile Loader**: Maps industry to material topics and adjusts scoring weights
- Per-factor scoring with explicit source attribution and data quality labels
- Coverage-adjusted scores — missing indicators are treated as "Limited Disclosure," not zero
- GW score is computed **independently** from the ESG score using:
  ```
  GW = α·max(0,(C-P)/σ)·100 + β·R + γ·(1-D/100)·100 + δ·T
  ```
  Where: C=Claim Intensity, P=Performance Score, R=Controversy Risk, D=Disclosure Completeness, T=Temporal Escalation

### 🏢 11. Social Pillar Forensic Analysis
- **SocialAgent**: Dedicated social pillar analysis covering:
  - Employee health & safety
  - Labor rights & fair wages
  - Community impact & CSR spend
  - Supply chain labor standards
  - Diversity, equity & inclusion
- Pulls from WBA SDG2000 benchmark data and public filings (Form SD conflict minerals disclosures)

### 🏛️ 12. Governance Pillar Forensic Analysis
- **GovernanceAgent**: Dedicated governance pillar analysis covering:
  - Board independence
  - Board diversity
  - Executive pay ratio (CEO-to-median pay)
  - Anti-corruption policies
  - Whistleblower mechanisms
  - ESG disclosure quality
- Extracts DEF 14A proxy statement data from SEC EDGAR for US companies

### 🔁 13. Contradiction Analysis & Cross-Pillar Synthesis
- **ContradictionAnalyzer**: Identifies conflicts between ESG claims and retrieved evidence
- Three-tier contradiction classification:
  - 🔴 **Tier-1**: Court ruling / regulatory action verified against primary source
  - 🟡 **Tier-2**: Reported by Tier-1 media, not yet adjudicated
  - ⚪ **Tier-3**: LLM-inferred interpretation, treat as hypothesis
- **CrossPillarSynthesizer**: Detects contradictions that span multiple ESG pillars
- **ConflictResolver**: Multi-agent debate resolution for disputed findings

### 🤖 14. Multi-Agent Debate Mechanism (Deep Analysis Track)
- **DebateOrchestrator**: For high-complexity claims, a structured debate between agents is triggered before verdict
- Agents challenge each other's findings, surface opposing interpretations, and reach a consensus or escalate to human review
- Only activated on the Deep Analysis track

### 🏗️ 15. Company Knowledge Graph (KG)
- **CompanyKnowledgeGraph**: Persistent graph database tracking company ESG KPIs across multiple runs
- Year-over-year drift detection: flags when metrics improve/worsen by > 5% vs. prior run
- Fact Graph motif analysis: pillar coverage skew, contradiction density, graph density, decision-readiness
- **EvidenceGraph** and **FactGraphBuilder**: Builds structured graphs linking evidence items to claims
- Helps surface cross-run patterns that single-shot scores miss

### 🏢 16. Subsidiary Footprint Walk (GLEIF + Climate TRACE)
- **SubsidiaryWalker**: Traverses company subsidiary tree via GLEIF LEI registry
- Cross-references subsidiaries against Climate TRACE asset-level emissions database
- Calculates coverage score (% of subsidiaries with matched emissions data)
- Structural penalty applied when coverage is poor (indicating parent disclosure may under-represent group-wide reality)

### 📊 17. Peer & Industry Comparison
- **IndustryComparator**: Benchmarks a company against real sector peers
- Industry-specific sigma (σ) used in the GW formula — prevents cross-sector distortion
- Peer percentile rankings for each pillar
- Dynamic industry detection from company name

### 💡 18. NLP / ClimateBERT Analysis
- **ClimateBERTAnalyzer**: Classifies claim language using a fine-tuned climate NLP model
- Detects: high climate relevance, promotional vs. factual language divergence
- Signals when claim language is "notably more promotional than the supporting evidence"
- Supports sentence-level classification (climate vs. not-climate)

### 🎯 19. ML Risk Models
- **XGBoostRiskModel**: Ensemble gradient boosting model for greenwashing risk prediction
- **LightGBMESGPredictor**: LightGBM-based ESG score prediction
- **LSTMTrendPredictor**: LSTM neural network for time-series ESG trend forecasting
- **AnomalyDetector**: Statistical anomaly detection on ESG metrics
- **SentimentESGPredictor**: Sentiment-based ESG signal extraction
- **ScoreCalibrator**: Post-hoc calibration of raw model scores to improve accuracy
- **ModelEvaluator**: Benchmark evaluation framework for model comparison
- **ExplainabilityEngine**: SHAP/LIME-based feature importance and model explanations

### 🔍 20. Score Attribution & Explainability
- **ScoreAttribution / decompose()**: Decomposes the headline GW score into ranked contributors
- Every component traces back to a specific ledger entry — no synthetic deltas, no LLM rephrasing
- **Score Modifier Ledger**: Full audit trail of every adjustment, penalty, floor, and calibration applied
- **Counterfactual Scenarios**: Pre-baked "what if" scenarios (e.g., "if the carbon pathway gap closes, headline drops by 20 points")
- **Abstention Analysis**: Per-sub-claim abstention rate and thresholds logged in the report
- **LLM Variance Band**: Empirical confidence interval derived from inter-provider diagnostic (8 probes across providers)

### 📄 21. Company Report Discovery & Parsing
- **ReportDiscovery**: Automatically finds and fetches the company's latest sustainability/ESG/annual reports
- **ReportDownloader**: Downloads PDFs from company IR pages and sustainability portals
- **ReportParser**: Extracts text chunks from PDFs (PyMuPDF + Camelot for tables)
- **ReportClaimExtractor**: Extracts structured ESG claims from parsed report text
- Feeds parsed chunks back into Carbon Extractor and other agents for higher-accuracy extraction

### 💬 22. ESG Analyst Copilot (Chatbot)
- **ESGChatService**: Conversational chatbot for querying generated reports
- Intent detection: score lookup, score explanation, contradiction queries, regulatory queries, section extraction
- Session memory: conversation history maintained per-session
- Dual LLM routing: Gemini primary → Groq fallback
- ESG scope guard: blocks non-ESG questions
- Deterministic fast path for direct score/section lookups (no LLM needed)
- LLM fallback path for complex/open-ended questions with citation-backed answers

### 🌐 23. FastAPI REST Backend & WebSocket Streaming
- `server.py` / `api/` — FastAPI backend exposing:
  - `POST /api/analyse` — Start a new ESG analysis (async, returns `analysis_id` immediately)
  - `GET /api/analysis/{id}` — Poll status and retrieve results
  - `WebSocket /ws/pipeline/{analysis_id}` — Stream live pipeline logs to frontend
  - `GET /health` — Health check endpoint
  - `POST /api/reports/` — Report management endpoints
  - `POST /api/chatbot/` — Chatbot API
  - `POST /api/upload/` — PDF upload endpoint
- Subprocess execution model: pipeline runs as isolated process, stdout/stderr captured line-by-line
- Classified log streaming: `ok`, `warn`, `error`, `info` per log line

### 📑 24. Professional Report Generation
- **ProfessionalReportGenerator**: Generates research-grade, publication-ready reports from the full analysis state
- Report Sections:
  - **Header**: Company, ticker, industry, claim, report ID, date, confidence
  - **Verdict**: GW score with LLM variance band, ESG score, rating, risk band, data coverage, calibration status
  - **Section 3**: Executive Summary with caveats
  - **Section 3B**: Claim breakdown (sub-claims)
  - **Section 3C**: Abstention decisions (SURE-RAG)
  - **Section 4**: Evidence citations table (source, type, verified, evidence role)
  - **Section 5**: Score Derivation (E/S/G pillar factor tables with source attribution)
  - **Section 5A**: Materiality Profile (industry-specific weights and rationale)
  - **Section 5B**: External Benchmark Integration (WBA, WRI)
  - **Section 5C**: Score Component Breakdown (7-driver decomposition)
  - **Section 5D**: Score Contributors (Why This Score) — ledger-sourced, no LLM rephrasing
  - **Section 5E**: Counterfactual Scenarios
  - **Section 6**: Key Risk Drivers
  - **Section 7**: Contradictions & Regulatory Alerts (with tier classification)
  - **Section 7B**: Full Regulatory Framework Status
  - **Section 7C**: Public Coverage of Regulatory Issues
  - **Section 7D**: EPA ECHO + EDGAR XBRL (US companies)
  - **Section 7E**: Resolved Litigation Dockets
  - **Section 8**: Carbon Emissions & Climate Data (Scope 1/2/3 table, per-category audit)
  - **Section 8B**: Carbon Pathway Alignment Analysis (IEA NZE benchmarking)
  - **Section 8C**: Emissions Ground-Truth Verification (Climate TRACE)
  - **Section 8E**: Subsidiary Footprint (GLEIF + Climate TRACE)
  - **Section 9**: Deception Pattern Analysis (Greenwashing/Greenwishing/Greenhushing)
  - **Section 9B**: Recent News & Active Coverage (real-time monitoring)
  - **Section 10**: Social Pillar Analysis
  - **Section 11**: Governance Pillar Analysis
  - **Section 11C**: Knowledge Graph History (YoY drift, fact graph motifs)
  - **Section 12A**: ESG Mismatch Detector (future commitments vs. implementation gaps)
- **ReportQualityChecker**: Structural quality gate before rendering — verifies evidence coverage, traceability, peer data quality, agent success
- Report Confidence Level: HIGH / MEDIUM / LOW based on agent success rate, verified source count, peer count

### 📦 25. Investor Brief (One-Page Summary)
- `_build_investor_brief()`: Generates a compact, decision-grade JSON artifact for portfolio/diligence use cases
- Contains: headline scores, LLM variance bands, top 3 risks, enforcement status, carbon snapshot, 3 tailored due-diligence questions, abstention summary, counterfactual scenarios, score attribution, emissions verification

### 🔢 26. Calibration & Score Reliability
- Post-hoc score calibration using industry-peer calibration samples
- Calibration status labels: PROVISIONAL (n<10), LIMITED (n<30), STANDARD
- LLM variance band: inter-provider diagnostic across Gemini, Groq, Cerebras, OpenRouter
- Industry-specific sigma (σ) normalization — falls back to cross-sector sigma when peer count < 5
- Abstention system: system abstains (returns INSUFFICIENT_EVIDENCE) rather than guessing on sub-claims with weak evidence

### 🤖 27. Multi-Provider LLM Routing
- **LLMRouter**: Per-agent routing table maps each agent to a prioritized chain of LLM providers
- Providers: **Google Gemini**, **Groq**, **Cerebras**, **OpenRouter**
- Models used: Gemini 2.5 Pro (report generation), Gemini 2.0 Flash, LLaMA 3.3 70B, LLaMA 3.1 8B, Qwen 3 235B, LLaMA 4 Scout 17B, Mistral Small 3.1, Gemma 3 27B
- Automatic failover: primary → fallback_1 → fallback_2 on rate limit or error
- Temperature=0.0 by default for reproducibility (ESG analysis requires determinism)
- JSON mode enforced per agent where structured output is needed
- LLM audit log: every call records provider, model, latency for full traceability
- **LLMCache**: Response caching to avoid redundant API calls
- Retired model registry: known-dead endpoints are automatically skipped

### 💾 28. Caching & Performance
- **EvidenceCache**: Caches evidence retrieval results by company/claim
- **EmbedCache**: Caches vector embeddings for evidence chunks
- **DeadURLCache**: Remembers permanently-dead URLs to skip on future runs
- **LLMCache**: Caches LLM responses for repeated identical prompts
- **VectorStore** (ChromaDB): Semantic search over evidence and report chunks
- **KG-RAG** (`kg_rag.py`): Knowledge graph–augmented retrieval for company-specific context

### 📊 29. ESG Mismatch Detector
- **ESGMismatchDetector** (`features/esg_mismatch_detector/`): Specifically checks for mismatches between:
  - Future pledges and actual progress/trends
  - Past promises and implementation gaps
- Structured output: pledge → status trend → progress/trend → risk level → evidence source

### 📈 30. Real-Time Monitoring
- **RealTimeMonitor**: Continuously surfaces recent news and public discourse signals
- Aggregates ESG-relevant news articles published close to analysis date
- Source classification: Financial Platform, NGO, News, Regulatory
- Not scored contradictions — contextual market-participant signals

### 📐 31. Macro Context & Signals
- **MacroContext / MacroSignals**: Incorporates macro-level events into risk scoring
- Example: active geopolitical conflicts (Iran-US-Israel 2026) modeled as Scope 3 exogenous surcharge
- Counterfactual scenario shows impact of removing macro-attributable GW points

### 🔬 32. Forensic Trap & Observability
- **ForensicTrap**: Optional memory/crash trap that tracks RSS over time, top allocation sites, and thread stack traces at moment of crash
- Pipeline Diagnostics (DIAG mode): every node entry/exit logged with `agent_outputs` length and wall-clock duration
- Node timing registry (`_ESG_NODE_TIMINGS`) accessible for performance audits
- Unified pipeline log (`pipeline.log`) captures all stdout/stderr/logging across a run session

---

## Architecture Overview

```
User Request (company + ESG claim)
        │
        ▼
  [Supervisor Agent]  ──── assesses complexity ────►  Route to track
        │
   ┌────┴───────────────────────────────────────────────┐
   │                                                    │
Fast Track              Standard Track           Deep Analysis Track
(3 agents)           (30+ agents)              (30+ agents + Debate)
   │                      │                            │
   ▼                      ▼                            ▼
Claim Extraction   Claim Extraction + Decomposition    ...same + Debate
Risk Scoring       Evidence Retrieval (28+ sources)
Verdict            Adversarial Triangulation
                   Report Discovery / Download / Parse
                   Carbon Extraction → Pathway Modelling
                   ──── PARALLEL ANALYTICS FANOUT ────
                   [Greenwishing | Regulatory | ClimateBERT |
                    Social | Governance | Contradiction |
                    Temporal | Peer | Sentiment | Credibility]
                   ESG Mismatch Detector
                   Real-Time Monitoring
                   Temporal Consistency
                   Commitment Ledger
                   Fact Graph
                   Risk Scoring
                   Explainability (SHAP/LIME)
                   Adversarial Audit
                   Confidence Scoring
                   Verdict Generation
                   Professional Report Generation
                        │
                        ▼
              [3 Output Formats]
         Text Report | JSON Export | Investor Brief
```

---

## Agent Pipeline

| Agent | Role |
|-------|------|
| **Supervisor** | Complexity assessment, workflow routing |
| **ClaimExtractor** | Parse ESG claim into structured sub-claims |
| **ClaimDecomposer** | Decompose compound claims, surface tensions |
| **EvidenceRetriever** | Multi-source live evidence fetching (28+ sources) |
| **AdversarialValidator** | Evidence triangulation, adversarial source testing |
| **ReportDiscovery** | Find company's official ESG/sustainability reports |
| **ReportDownloader** | Download report PDFs |
| **ReportParser** | Extract text and tables from PDFs |
| **ReportClaimExtractor** | Extract structured claims from parsed reports |
| **CarbonExtractor** | Scope 1/2/3 emissions extraction (GHG Protocol aligned) |
| **CarbonPathwayModeller** | 1.5°C / IEA NZE pathway alignment analysis |
| **GreenwishingDetector** | Greenwashing / Greenwishing / Greenhushing detection |
| **RegulatoryHorizonScanner** | Multi-jurisdiction regulatory compliance scanning |
| **ClimateBERTAnalyzer** | NLP classification of climate language |
| **ContradictionAnalyzer** | Claim-evidence contradiction detection (3-tier) |
| **TemporalConsistencyAgent** | Year-over-year commitment tracking |
| **HistoricalAnalyst** | Historical ESG violation and pattern analysis |
| **SocialAgent** | Social pillar forensic scoring |
| **GovernanceAgent** | Governance pillar forensic scoring |
| **PeerComparison** | Industry peer benchmarking |
| **SentimentAnalyzer** | Sentiment and linguistic analysis |
| **CredibilityAnalyst** | Source credibility and reliability scoring |
| **RealTimeMonitor** | Live news & public discourse signals |
| **ESGMismatchDetector** | Future pledge vs. implementation gap analysis |
| **CommitmentLedger** | Longitudinal commitment tracking |
| **FactGraphBuilder** | Evidence-claim knowledge graph construction |
| **RiskScorer** | Greenwashing Risk Score computation |
| **ExplainabilityEngine** | SHAP/LIME score attribution |
| **AdversarialAudit** | Final adversarial quality audit of all findings |
| **ConfidenceScorer** | Confidence band calibration |
| **VerdictGenerator** | Final verdict synthesis |
| **DebateOrchestrator** | Multi-agent debate (Deep Track only) |
| **ProfessionalReportGenerator** | Research-grade report rendering |
| **FinancialAnalyst** | Financial-ESG correlation analysis |
| **SubsidiaryWalker** | Group subsidiary footprint (GLEIF + Climate TRACE) |

---

## Data Sources

| Source | Type | What We Get |
|--------|------|-------------|
| **SEC EDGAR** | Regulatory Filing | 10-K, DEF 14A, SD (conflict minerals) |
| **CDP** | ESG Registry | Carbon disclosure scores, A-list |
| **SBTi** | ESG Registry | Science-based targets validation (14,900+ entries) |
| **UN Global Compact** | ESG Registry | Participants directory |
| **GRI Database** | ESG Registry | Sustainability reporting standards compliance |
| **Climate TRACE** | Satellite/Asset Data | Asset-level verified emissions by country/sector |
| **GLEIF** | Corporate Registry | LEI, subsidiary/parent relationships |
| **WBA** | Benchmark | SDG2000 pillar scores (social, governance, environment) |
| **WRI Aqueduct 4.0** | Physical Risk | 13 water risk indicators (physical, regulatory, reputational) |
| **EPA ECHO** | Regulatory | US environmental violations |
| **CourtListener** | Legal | US court dockets |
| **Indian Kanoon** | Legal | Indian court cases |
| **OpenSanctions** | Sanctions | Corruption/sanctions screening |
| **EU ESEF** | Regulatory | EU XBRL filings, CSRD compliance |
| **PCAF** | Standard | Financed emissions (banking Scope 3 Cat 15) |
| **GDELT** | News | Global news event database |
| **NewsAPI / Reuters / Google News** | News | Real-time news coverage |
| **DuckDuckGo** | Web | Adversarial evidence search |

---

## ML Models

| Model | Purpose |
|-------|---------|
| **XGBoost** | Greenwashing risk prediction |
| **LightGBM** | ESG score prediction |
| **LSTM** | Time-series ESG trend forecasting |
| **ClimateBERT** | Climate language NLP classification |
| **Anomaly Detector** | ESG metric anomaly detection |
| **Score Calibrator** | Post-hoc calibration of raw scores |

---

## Output Formats

1. **Text Report** (`.txt`) — Human-readable, publication-style, ~60KB per company, 30+ sections
2. **JSON Export** (`.json`) — Machine-readable structured data, ~1MB per company, suitable for API/dashboard integration
3. **Investor Brief** (`_brief.json`) — One-page decision-grade summary: headline scores, top 3 risks, enforcement status, carbon snapshot, 3 due-diligence questions
4. **Chatbot Interface** — Query any generated report conversationally via the ESG Analyst Copilot

---

## Deployment Modes

- **SaaS**: Fully managed, API-first
- **Dedicated Cloud**: Customer-specific cloud instance
- **On-Premise**: Full self-hosted deployment for institutions with data sovereignty requirements

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run analysis
python main_langgraph.py --company "Shell" --claim "Net zero emissions by 2050"

# Start API server
uvicorn server:app --reload --port 8000
```

---

## Validated Companies

Validated across 51 companies, 8 sectors. Reports generated for:

| Company | Industry | GW Score | Risk Band |
|---------|----------|----------|-----------|
| Shell | Oil & Gas | 86.9/100 | HIGH |
| ExxonMobil | Oil & Gas | ~74/100 | HIGH |
| JPMorgan Chase | Financial Services | — | — |
| Volkswagen | Automotive | — | — |
| Reliance Industries | Conglomerate | — | — |

---

## Regulatory Coverage

| Jurisdiction | Framework |
|-------------|-----------|
| 🇺🇸 US | SEC Climate Disclosure Rule, EPA ECHO, EDGAR XBRL |
| 🇪🇺 EU | CSRD (Corporate Sustainability Reporting Directive), EU Taxonomy, ESEF |
| 🇬🇧 UK | FCA Anti-Greenwashing Rule |
| 🇮🇳 India | SEBI BRSR (Business Responsibility and Sustainability Report) |
| 🌍 Global | GHG Protocol, TCFD, CDP, SBTi, UN Global Compact, GRI, IPCC Consistency |

---

*ESGLens v4.0 — Multi-Agent ESG Analysis (Pillar-Primary, Calibrated)*
