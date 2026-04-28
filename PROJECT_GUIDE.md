# ESGLens — Comprehensive Project Guide

> **Generated**: 2026-04-26
> **Scope**: Every subsystem of this repository — pipeline, agents, scoring, knowledge graphs, caches, retrievers, reports, API, chatbot, ML models, mismatch detector, frontends, config, tests, environment.
> **Audience**: Anyone who needs to understand or extend this project end-to-end without reading every file first.
> **How to read this**: Sections 1–4 give you the mental model. Sections 5–11 are the reference for each subsystem. Sections 12–15 cover the surrounding plumbing. Section 16 is the known-issues backlog.

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [Repository Layout (Top-Down Map)](#2-repository-layout-top-down-map)
3. [The Mental Model — End-to-End in One Page](#3-the-mental-model--end-to-end-in-one-page)
4. [Entry Points — How a Run Starts](#4-entry-points--how-a-run-starts)
5. [The LangGraph Workflow](#5-the-langgraph-workflow)
6. [The 23 Agents](#6-the-23-agents)
7. [The Scoring Engine — Greenwashing Risk Formula](#7-the-scoring-engine--greenwashing-risk-formula)
8. [Knowledge Graph, Fact Graph, Pillar Factors, Commitment Ledger](#8-knowledge-graph-fact-graph-pillar-factors-commitment-ledger)
9. [Caching Subsystems](#9-caching-subsystems)
10. [Data Sources & Retrievers (28+ external feeds)](#10-data-sources--retrievers)
11. [Report Generation — TXT, JSON, PDF](#11-report-generation--txt-json-pdf)
12. [FastAPI Server & WebSocket Streaming](#12-fastapi-server--websocket-streaming)
13. [Chatbot Backend (ESG Analyst Copilot)](#13-chatbot-backend-esg-analyst-copilot)
14. [ML Models](#14-ml-models)
15. [ESG Mismatch Detector (Standalone Feature)](#15-esg-mismatch-detector-standalone-feature)
16. [Frontends — `esglens/` (active) and `frontend/` (legacy)](#16-frontends)
17. [Configuration, Tests, Environment](#17-configuration-tests-environment)
18. [Operational Runbook](#18-operational-runbook)
19. [Known Bugs & Future Work](#19-known-bugs--future-work)

---

## 1. What This Project Is

**ESGLens** is an enterprise-grade greenwashing-detection and ESG (Environmental / Social / Governance) intelligence platform. Its core question:

> **"Does a company's public sustainability claim hold up against the evidence in regulatory filings, NGO reports, news, official disclosures, financial data, and historical statements?"**

Concretely, the system takes three inputs:

- **Company name** (e.g., "JPMorgan Chase")
- **Claim** (e.g., "Net-zero emissions by 2050")
- **Industry** (auto-detected if omitted)

…runs a multi-agent LangGraph pipeline that fans out to 28+ external data sources, applies ~23 specialised analysis agents, blends rule-based + ML + LLM scoring, and produces:

1. A **TXT executive report** (12 sections + 3 appendices)
2. A **JSON machine-readable export** (consumed by the frontend)
3. A **PDF audit report** (mirrors the TXT layout, includes pillar bar chart)
4. A **Greenwashing Risk Score (GW)** 0–100 with full lineage
5. A **Risk verdict** (HIGH / MODERATE / LOW) with confidence
6. **Knowledge-graph payloads** (company KG + claim-centric fact graph)
7. A **commitment ledger** entry tracking promise revisions over time

The system is *not* "LLM in, score out". It mixes:

- Deterministic rule-based scoring (the GW master formula)
- Trained ML models (XGBoost risk, LightGBM ESG, LSTM trend, Isolation Forest anomalies, ClimateBERT NLP)
- LLM reasoning (Groq, Gemini, Cerebras, OpenRouter) with disk caching
- Hard-data retrieval (SEC EDGAR, Companies House, OpenSanctions, CDP, SBTi, WBA, WRI Aqueduct, etc.)
- Multi-agent debate (in deep-analysis mode)

---

## 2. Repository Layout (Top-Down Map)

```
ESG/
├── main_langgraph.py          ← CLI entry: builds graph, runs analysis, saves reports
├── server.py                  ← FastAPI app on :8000 — REST + WebSocket
├── validate_improvements.py   ← Smoke-test of the pipeline + ML stack
├── requirements.txt           ← Python deps (langgraph, fastapi, ml libs, scrapers)
├── pytest.ini                 ← Test config (root: tests/)
├── .env                       ← API keys, Neo4j creds, feature flags
├── README.md                  ← Marketing-grade overview (math & narrative)
├── PROJECT_DOCUMENTATION.md   ← Older end-to-end product doc (slightly stale)
├── IMPROVEMENTS_SUMMARY.md    ← Change log of fixes (Apr 2026)
├── PROJECT_GUIDE.md           ← THIS FILE
│
├── agents/                    ← 23 specialised analysis agents (see §6)
│
├── core/                      ← Workflow + state + LLM + KG + reports
│   ├── workflow_phase2.py        ← THE LangGraph DAG (fast / standard / deep tracks)
│   ├── state_schema.py           ← ESGState TypedDict (~107 fields)
│   ├── supervisor_agent.py       ← Complexity scoring + track routing
│   ├── debate_orchestrator.py    ← Multi-agent debate (deep track only)
│   ├── agent_wrappers.py         ← Per-node wrappers around raw agent classes (~2500 LOC)
│   ├── llm_call.py / llm_router.py / llm_clients.py / llm_cache.py
│   ├── company_knowledge_graph.py + kg_schema.py    ← Neo4j KG (with JSON fallback)
│   ├── fact_graph_builder.py + fact_graph_persistence.py  ← Claim-centric JSON graph
│   ├── pillar_factors_builder.py ← E/S/G sub-indicator decomposition
│   ├── evidence_cache.py         ← 24h disk+memory cache for retrieved evidence
│   ├── professional_report_generator.py ← TXT report (12 sections + 3 appendices)
│   ├── report_schema.py          ← Pydantic shape of the JSON export
│   ├── adversarial_audit.py      ← Coordination-risk audit
│   ├── archive_retriever.py      ← Wayback / Archive.today / Memento cascade
│   ├── carbon_retrieval.py + carbon_validator.py
│   ├── confidence_monitor.py     ← Iteration gate / revision trigger
│   ├── benchmark_evaluator.py    ← Ground-truth eval (AUC, Brier, ECE, bootstrap CIs)
│   ├── research_telemetry.py     ← JSONL run-metric logs
│   ├── materiality_profile_loader.py ← SASB-style E/S/G weights
│   ├── safe_utils.py             ← Null-safe getters, reliability tiers
│   ├── sg_evidence.py            ← Social/Governance evidence normalisation
│   ├── esg_data_apis.py          ← WBA + WRI Aqueduct enrichment
│   ├── vector_store.py           ← ChromaDB wrapper + reranker
│   ├── enums.py                  ← AgentStatus enum
│   └── extractors/pdf_table_extractor.py  ← Camelot-based PDF table parsing
│
├── api/                       ← FastAPI route handlers
│   ├── router.py                 ← Mounts all routes
│   ├── analysis.py               ← POST /api/analyse, GET /api/analysis/{id}
│   ├── reports.py                ← GET /api/reports, /api/reports/{id}, /pdf
│   ├── upload.py                 ← POST /api/upload (multipart, 50 MB cap)
│   ├── chatbot.py                ← /chatbot/* — proxies to chatbot_backend service
│   ├── pipeline_ws.py            ← WS /ws/pipeline/{analysis_id}
│   ├── mappers.py                ← Raw pipeline JSON → ESGReport Pydantic schema
│   ├── models.py                 ← Pydantic request/response models
│   ├── pdf_generator.py          ← ReportLab PDF (mirrors TXT structure)
│   ├── pdf_styles.py             ← Colours, fonts, table styles
│   └── validation_layer.py       ← Post-process integrity checks (non-destructive)
│
├── chatbot_backend/           ← Independent Q&A service over generated reports
│   ├── app.py                    ← Standalone FastAPI app (also mounted via /chatbot)
│   ├── service.py                ← ESGChatService — orchestrates intent/retrieval/LLM
│   ├── intent_router.py          ← Intent taxonomy + section matching
│   ├── llm.py                    ← LLMOrchestrator (Gemini → Groq fallback)
│   ├── memory.py                 ← SessionMemoryStore (in-memory turns, 6h TTL)
│   ├── prompts.py                ← System prompt + user prompt builder
│   ├── report_context.py         ← Loads latest report from reports/
│   ├── retriever.py              ← Pulls structured slices of report
│   ├── models.py                 ← Pydantic request/response
│   ├── config.py                 ← Settings loader
│   └── PROMPT_TEMPLATES.md       ← Prompt-design reference
│
├── features/esg_mismatch_detector/   ← Standalone promise-vs-actual pipeline
│   ├── pipeline.py               ← `python -m features.esg_mismatch_detector.pipeline "<co>"`
│   ├── company_resolver.py       ← Name normalisation + aliases
│   ├── report_collector.py       ← Fetch sustainability reports
│   ├── promise_extractor.py      ← Parse pledges from report text
│   ├── evidence_collector.py     ← External evidence + regulatory tags
│   ├── comparison_engine.py      ← Match promise → actual, score gap
│   └── mismatch_detector.py      ← Aggregate to overall risk
│
├── ml_models/                 ← Trained models + inference wrappers
│   ├── anomaly_detector.py       ← Isolation Forest (8 engineered features)
│   ├── climatebert_analyzer.py   ← 4 HuggingFace ClimateBERT models
│   ├── explainability_engine.py  ← SHAP TreeExplainer + LIME
│   ├── lightgbm_esg_predictor.py ← LightGBM (R² = 0.92 on 7-feature totalEsg)
│   ├── lstm_trend_predictor.py   ← LSTM (TF/Keras) — 6yr forecast from 6yr history
│   ├── model_evaluator.py        ← CV harness (Dummy/LogReg/XGB/LGBM)
│   ├── score_calibrator.py       ← Logistic recalibration of rule-based scores
│   ├── sentiment_esg_predictor.py ← Sentiment → 6-month ESG-change predictor
│   ├── xgboost_risk_model.py     ← Multi-class HIGH/MODERATE/LOW risk
│   └── trained/                  ← .pkl, .h5, .json artifacts (~2.2 MB total)
│
├── utils/                     ← Data fetching + parsing helpers
│   ├── enhanced_data_sources.py     ← ILO, UN GC, OECD, EU Tax, UNFCCC, OpenApparel, OpenSanctions
│   ├── enhanced_evidence_integration.py ← Bridge to EvidenceRetriever
│   ├── free_data_sources.py / free_esg_data_fetcher.py
│   ├── enterprise_data_sources.py
│   ├── indian_data_sources.py / indian_financial_data.py  ← BSE/NSE/SEBI/MCA/CPCB
│   ├── web_search.py                ← Wraps DuckDuckGo / Google News + SEC EDGAR
│   ├── report_discovery.py          ← Find ESG/sustainability PDFs
│   ├── report_downloader.py         ← Download with TTL cache (100 MB cap)
│   ├── report_parser.py             ← PDF → text chunks (PyPDF + Camelot)
│   ├── company_report_fetcher.py
│   └── source_tracker.py            ← @track decorator → per-source success report
│
├── commitment_tracker/
│   └── ledger.py                 ← SQLite ledger of commitments + revisions
│
├── config/                    ← Static configuration
│   ├── agent_prompts.py          ← Master ESG analyst system prompt + evidence hierarchy
│   ├── company_aliases.json      ← Ticker / aliases / full-name lookups
│   ├── data_sources.json         ← Per-source rate limits, cache TTLs, priorities
│   ├── industry_baselines.json   ← Sector baselines (oil/gas, coal, mining, tech, ...)
│   ├── materiality_map.json      ← SASB-style E/S/G weights per sector
│   └── settings.py               ← Pydantic settings loaded from .env
│
├── data/                      ← Static reference + sample reports
│   ├── known_cases.py            ← ~20 verified greenwashing regulatory cases
│   ├── peer_database.json        ← Sector-grouped peer ESG scores
│   ├── sbti_company_cache.json   ← SBTi-validated targets (~70 KB)
│   ├── emissions_floors.json     ← Per-sector emissions baselines
│   ├── esg_mismatch_results.json ← Historic mismatch outputs
│   └── reports/                  ← 20 sample company report folders (Adani, Apple, BP, ...)
│
├── esglens/                   ← ACTIVE FRONTEND (Vite + React 18 + TS)
│   ├── package.json              ← React Router, Zustand, Recharts, Three.js, Tanstack Query
│   ├── vite.config.ts            ← Dev server on :3001, proxy → :8000
│   └── src/
│       ├── pages/                ← Dashboard, NewAnalysis, LivePipeline, Report,
│       │                           History, Chatbot, ReportsLibrary, NotFound
│       ├── components/           ← cards, charts, layout, report, three (3D globe), ui (shadcn)
│       ├── stores/               ← analysisStore, chatStore, historyStore (Zustand)
│       ├── hooks/, lib/, data/, test/
│
├── frontend/                  ← LEGACY FRONTEND (Next.js 16) — file-backed auth, mostly scaffolding
│   ├── package.json              ← next, react 19, recharts 3, tailwind 4
│   └── src/
│       ├── app/                  ← App-router pages: /, /login, /signup, /dashboard, /api/*
│       ├── components/, lib/
│       └── data.json             ← Plain-text user store (NOT production-safe)
│
├── reports/                   ← Generated artifacts (gitignored)
│   ├── ESG_Report_<Co>_<TS>.txt  ← Human report
│   ├── ESG_Report_<Co>_<TS>.json ← Machine export
│   ├── ESG_Report_<Co>_<TS>_FULL.json   ← Optional debug dump
│   ├── debug_esg_lineage_<Co>.json      ← Score lineage trace
│   ├── company_kg/               ← Per-company KG payloads + KPI history JSONL
│   └── fact_graphs/              ← Per-run claim-centric fact graphs
│
├── cache/                     ← Disk caches (gitignored)
│   ├── evidence/                 ← 24h TTL retrieved-evidence dumps per company
│   ├── llm_responses/            ← Per-agent LLM output cache (7-30d TTL)
│   ├── claim_extraction/, contradiction_analysis/, credibility_analysis/, ...
│   ├── company_reports/, parsed_reports/, financial_data/, search/
│   ├── peer_data/, cdp_data/, esg_analysis/  ← mismatch-detector outputs
│   └── camelot_temp/             ← PDF table extractor scratch (auto-cleaned)
│
├── chroma_db/peer_comparison_history/   ← ChromaDB SQLite for peer benchmarking history
│
├── scripts/                   ← Dev/ops utility scripts (training, replay, KG verify, etc.)
├── scratch/                   ← One-off patches / dev fixes (carbon, scoring, sections)
├── tests/                     ← pytest — gw/esg independence, S/G evidence pipeline
└── venv/                      ← Local virtualenv (gitignored)
```

---

## 3. The Mental Model — End-to-End in One Page

```
                ┌─────────────────────────────────────────────────────────┐
                │  USER (CLI, frontend, or API client)                    │
                │  Inputs: company, claim, industry                       │
                └─────────────────────────────────────────────────────────┘
                                     │
                                     ▼
            ┌─────────────────────────────────────────────────────┐
            │  Frontend (esglens) ──► POST /api/analyse           │
            │  CLI ──────────────► python main_langgraph.py       │
            └─────────────────────────────────────────────────────┘
                                     │
                                     ▼
                ┌──────────────────────────────────────────────┐
                │  build_phase2_graph()  (core/workflow_phase2)│
                │   • assess_complexity ──► classify_workflow   │
                └──────────────────────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
        FAST TRACK            STANDARD TRACK           DEEP ANALYSIS
        (~7 nodes)           (~31 nodes)              (Standard + debate)
        complexity<0.2       0.2 ≤ c < 0.7            c ≥ 0.7 OR keyword
                                     │
                                     ▼
            ┌────────────────────────────────────────────────┐
            │  EvidenceRetriever fans out to 14+ retrievers:│
            │   newsapi · newsdata · duckduckgo · reuters    │
            │   google_news · scholar · cdp · sbti · ir      │
            │   companies_house · opensanctions · gri        │
            │   influencemap · adversarial · vector          │
            │   + WBA / SEC / WRI Aqueduct enrichment        │
            └────────────────────────────────────────────────┘
                                     │
                                     ▼
            ┌────────────────────────────────────────────────┐
            │  ~23 agents (E, S, G, carbon, regulatory,      │
            │  contradiction, credibility, sentiment,        │
            │  temporal, greenwishing, ClimateBERT, ML)      │
            │  — each appends to state["agent_outputs"]      │
            │    via custom dedupe reducer                    │
            └────────────────────────────────────────────────┘
                                     │
                                     ▼
            ┌────────────────────────────────────────────────┐
            │  RiskScorer applies the master GW formula:     │
            │    GW = α·Gap + β·R + γ·Deficit + δ·T          │
            │  + WBA/SEC injection + industry-tuned weights  │
            │  + ESG performance score (E/S/G blend)         │
            └────────────────────────────────────────────────┘
                                     │
                                     ▼
            ┌────────────────────────────────────────────────┐
            │  Explainability (SHAP/LIME) → adversarial      │
            │  audit → confidence scoring →                  │
            │  [debate_orchestrator if deep] →               │
            │  verdict_generation                            │
            └────────────────────────────────────────────────┘
                                     │
                                     ▼
            ┌────────────────────────────────────────────────┐
            │  Outputs written to disk:                       │
            │    • reports/ESG_Report_<co>_<ts>.txt           │
            │    • reports/ESG_Report_<co>_<ts>.json          │
            │    • reports/company_kg/<co>_payload.json       │
            │    • reports/fact_graphs/<co>_<ts>_*.json       │
            │    • commitment_tracker SQLite update           │
            └────────────────────────────────────────────────┘
                                     │
                                     ▼
            ┌────────────────────────────────────────────────┐
            │  Frontend reads JSON via /api/reports/{id}      │
            │  → renders dashboard, drives PDF export,        │
            │    feeds chatbot context                        │
            └────────────────────────────────────────────────┘
```

---

## 4. Entry Points — How a Run Starts

### 4.1 `main_langgraph.py` — CLI / programmatic

This is the canonical entry point. Three usage modes:

```bash
# Interactive (prompts for company + claim + industry)
python main_langgraph.py

# Argument-based
python main_langgraph.py --company "JPMorgan Chase" \
                        --claim "net-zero emissions by 2050" \
                        --industry "Banking"

# Programmatic
from main_langgraph import run_esg_analysis
result = run_esg_analysis(company, claim, industry)
```

Two top-level functions of interest:

- **`ESGGreenwashingDetectorLangGraph.analyze_company(...)`** — the rich path used by the CLI. Builds initial state with 26+ pre-declared fields, invokes `self.workflow.invoke(initial_state, config)` inside a `ThreadPoolExecutor` with a configurable timeout (`ESG_WORKFLOW_TIMEOUT`, default 1800s = 30 min). On timeout, if `ESG_ALLOW_PARTIAL_ON_TIMEOUT=1` (default), returns a partial result with `final_verdict.status = "TIMEOUT_PARTIAL"` rather than raising. On success, calls `ProfessionalReportGenerator` for the TXT + JSON exports, saves to `reports/`, and prints a deduplicated executive summary.
- **`run_esg_analysis(company, claim, industry)`** — slimmer wrapper used by tests/integration; streams nodes via `app.stream()` instead of `app.invoke()` and prints each node name as it executes.

Important flags / env vars consumed here:

| Env var | Default | Purpose |
|---|---|---|
| `USE_LANGGRAPH` | `true` | Master toggle (legacy `main.py` path lives behind a `false`) |
| `ESG_WORKFLOW_TIMEOUT` | `1800` | Hard wall-clock for graph invocation (seconds) |
| `ESG_ALLOW_PARTIAL_ON_TIMEOUT` | `1` | If true, return partial state instead of raising |
| `ESG_SAVE_FULL_RESULTS` | `0` | If true, also dump the raw state to `*_FULL.json` |
| `ESG_FORCE_EXIT` | `1` | Call `os._exit()` after CLI run if background threads remain |

### 4.2 FastAPI server (`server.py` → `api/`)

Started with:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Routes are mounted from `api/router.py`; full table in §12.

### 4.3 Frontend (`esglens/`)

```bash
cd esglens && npm install && npm run dev   # Vite on :3001, proxies to :8000
```

Calling `POST /api/analyse` causes the backend to spawn `main_langgraph.py` as a subprocess (in `api/pipeline_ws.py`) and stream stdout/stderr lines to the browser via the WebSocket at `/ws/pipeline/{analysis_id}`.

### 4.4 Mismatch detector (separate pipeline)

```bash
python -m features.esg_mismatch_detector.pipeline "BP"
```

Independent of LangGraph. Documented in §15.

### 4.5 Chatbot (`chatbot_backend/`)

The chatbot can run as its own service (`chatbot_backend/app.py`) but in normal use it is mounted into the main FastAPI app via `api/chatbot.py` under the `/chatbot/*` prefix.

---

## 5. The LangGraph Workflow

File: **`core/workflow_phase2.py`**, function: **`build_phase2_graph()`**.

The workflow is a directed graph with **three execution tracks** chosen at runtime by the supervisor.

### 5.1 Routing — `assess_complexity_node` → `classify_workflow`

`assess_complexity_node` (in `agent_wrappers.py`) clears the session evidence cache, instantiates `SupervisorAgent` (`core/supervisor_agent.py`), and asks the LLM to score the claim from 0.0 to 1.0 across five axes:

| Axis | Weight |
|---|---|
| Quantitative specificity (numbers, %, units) | 0.10 |
| Temporal clarity (year, deadline) | 0.20 |
| Verifiability (frameworks, scopes) | 0.30 |
| Ambiguity (hedging language) | 0.20 |
| Scope (single fact vs cross-pillar) | 0.20 |

If the LLM call fails, complexity defaults to **0.5**.

`classify_workflow` then picks a track:

- **fast_track** — `complexity < 0.2` **AND** the claim contains none of the keywords `["scope 1", "scope 2", "scope 3", "emission", "carbon", "net zero", "renewable", "sbti", "science based", "%", "by 20", "since 20"]`
- **deep_analysis** — `complexity >= 0.7` **OR** any of the above keywords appear
- **standard_track** — everything else

In practice, almost every meaningful claim ends up on standard or deep — fast_track is reserved for genuinely vague marketing statements.

### 5.2 Node execution order

#### Fast Track (~7 nodes)
```
claim_extraction → risk_scoring → adversarial_audit → confidence_scoring
  → verdict_generation → save_peer_to_database → report_generation → END
```

#### Standard Track (~31 nodes, in execution order)
```
claim_extraction
claim_decomposition
evidence_retrieval                ← also runs Financial Analyst (Agent #14)
adversarial_triangulation
report_discovery
report_downloader
report_parser
report_claim_extraction
carbon_extraction
carbon_pathway_analysis
greenwishing_detection
regulatory_scanning
climatebert_analysis
temporal_analysis
inject_temporal_violations
contradiction_analysis
esg_mismatch_analysis
peer_comparison
credibility_analysis
sentiment_analysis
realtime_monitoring
social_analysis
governance_analysis
temporal_consistency
commitment_ledger_update
fact_graph
risk_scoring
explainability
adversarial_audit
confidence_scoring
verdict_generation
save_peer_to_database
report_generation → END
```

#### Deep Analysis (~32 nodes)
Identical to standard, with `debate_node` inserted between `verdict_generation` and `save_peer_to_database`.

### 5.3 The state object — `ESGState`

File: **`core/state_schema.py`**. A `TypedDict` with ~107 fields. The most important groups:

| Group | Fields | Notes |
|---|---|---|
| **Inputs** | `claim`, `company`, `industry` | Set at run start |
| **Routing** | `complexity_score: float`, `workflow_path: str` | Filled by supervisor |
| **Evidence** | `evidence: List[Dict]`, `additional_evidence`, `external_esg_data` | Populated by retrievers |
| **Per-agent outputs** | `claim_decomposition`, `carbon_extraction`, `carbon_pathway_analysis`, `greenwishing_analysis`, `regulatory_compliance`, `climatebert_analysis`, `esg_mismatch_analysis`, `social_analysis`, `governance_analysis`, `commitment_ledger`, `adversarial_triangulation`, `adversarial_audit`, `explainability_report`, `fact_graph` | Each is `Optional[Dict]` |
| **Scoring intermediates** | `claim_intensity`, `controversy_risk`, `temporal_escalation`, `esg_score_lineage` | Mapped to GW formula vars C, R, T |
| **ML outputs** | `ml_prediction`, `financial_context`, `indian_financials` | XGBoost, FinancialAnalyst, IndianFinancialData |
| **Final** | `confidence: float`, `risk_level: str`, `rating_grade: Optional[str]`, `final_verdict: Dict`, `report: str` | Generated near end |
| **Bookkeeping** | `agent_outputs: Annotated[List[Dict], _dedupe_agent_outputs]`, `iteration_count`, `needs_revision`, `verdict_locked`, `pipeline_agent_statuses: Dict[str, AgentStatus]`, `research_telemetry` | The reducer keeps only the **latest** output per agent name to prevent unbounded growth across LangGraph merges |

`AgentStatus` (in `core/enums.py`): `SUCCESS`, `PARTIAL`, `NULL_RESULT`, `FAILED`.

### 5.4 Compilation note

The graph is compiled **without** a `MemorySaver`/SQLite checkpointer. This trades mid-execution recovery for speed and lower memory. State is fully recomputed per invocation.

### 5.5 Debate Orchestrator (deep track only)

File: **`core/debate_orchestrator.py`**. Fires only on the deep-analysis track, between `verdict_generation` and `save_peer_to_database`.

1. Walks `agent_outputs`, infers each agent's verdict (`HIGH` / `MODERATE` / `LOW`) from explicit `risk_level` fields or text patterns.
2. If two or more distinct verdicts exist → conflict detected.
3. Runs up to **3 debate rounds** (`max_rounds=3`) where conflicting agents defend their position via LLM.
4. **Weighted voting**: each agent's confidence × 10 = vote weight.
5. Winning verdict = most votes; final confidence = `winning_votes / total_votes`.
6. **Quality bonus**: +1% per debate argument, capped at +10%.
7. **Conflict penalty**: if `conflict_ratio ≥ 60%`, reduce confidence by `conflict_ratio × 30%`.
8. Output stored as a `debate_orchestrator` entry in `agent_outputs` with `vote_distribution`, `conflicting_agents`, `conflict_ratio`, `debate_summary[]`.

`confidence_monitor.py` may apply an additional penalty (up to 25%) downstream if conflicting agents remain.

### 5.6 Agent wrappers

File: **`core/agent_wrappers.py`** (~2500 LOC) — every node in the graph is a thin wrapper that:

1. Reads what it needs from state.
2. Imports and calls the live agent class (or its fallback if import fails).
3. Performs node-specific enrichment (e.g., `evidence_retrieval_node` also runs `FinancialAnalyst` and the `IndianFinancialData` fetcher).
4. Writes results back to state and appends an `agent_outputs` entry.

Two structural notes:

- **Financial Analyst is Agent #14, not a separate node.** It's invoked inside `evidence_retrieval_node`, and its output lands in `state.financial_context`.
- **WBA / SEC injection** happens via `core/esg_data_apis.py:fill_missing_pillars()`, called from the risk scorer when primary IR data is sparse.

---

## 6. The 23 Agents

The 23 agents in `agents/` are grouped here by role. For each, you'll find: **inputs from state → outputs to state → key methods → external deps → notable details.**

### 6.1 Quick index

| # | Agent | File | Role |
|---|---|---|---|
| 1 | AdversarialEvidenceValidator | `adversarial_validator.py` | Triangulates support/contradict balance |
| 2 | CarbonExtractor | `carbon_extractor.py` | Pulls Scope 1/2/3 emissions |
| 3 | CarbonPathwayModeller | `carbon_pathway_modeller.py` | IEA NZE / IPCC budget feasibility |
| 4 | ClaimDecomposer | `claim_decomposer.py` | Atomises compound claims, finds tensions |
| 5 | ClaimExtractor | `claim_extractor.py` | LLM extraction of claims from reports |
| 6 | ClaimIntensityScorer | `claim_intensity_scorer.py` | Computes `C` (boldness, 0–100) |
| 7 | ConfidenceScorer | `confidence_scorer.py` | Aggregates run-level confidence |
| 8 | ConflictResolver | `conflict_resolver.py` | Credibility-weighted vote on contradictions |
| 9 | ContradictionAnalyzer | `contradiction_analyzer.py` | KG + known-cases + LLM contradiction scan |
| 10 | CredibilityAnalyst | `credibility_analyst.py` | Per-source credibility & bias scoring |
| 11 | EvidenceRetriever ⭐ | `evidence_retriever.py` | Master fan-out to 14+ retrievers |
| 12 | FinancialAnalyst | `financial_analyst.py` | Revenue/margin/debt + greenwashing flags |
| 13 | GovernanceAgent | `governance_agent.py` | Board independence, pay equity, audit |
| 14 | GreenwishingDetector | `greenwishing_detector.py` | Greenwishing / greenhushing / cherry-picking |
| 15 | HistoricalAnalyst | `historical_analyst.py` | Past violations, trend, reputation |
| 16 | IndustryComparator | `industry_comparator.py` | Peer percentile (note: deprecated path in graph) |
| 17 | MultiJurisdictionRegulatoryScanner | `multi_jurisdiction_regulatory_scanner.py` | SEC / CSRD / FCA / BRSR / TCFD |
| 18 | RealtimeMonitor | `realtime_monitor.py` | Polling for breaking news |
| 19 | RegulatoryScanner | `regulatory_scanner.py` | Enforcement DBs (SEC EDGAR, FCA, MCA) |
| 20 | RiskScorer ⭐ | `risk_scorer.py` | Master GW + ESG performance scoring |
| 21 | SentimentAnalyzer | `sentiment_analyzer.py` | GSI + boilerplate score |
| 22 | SocialAgent | `social_agent.py` | Diversity, pay equity, H&S, grievance |
| 23 | TemporalConsistencyAgent | `temporal_consistency_agent.py` | Year-over-year claim drift |

### 6.2 The two heavyweights

#### Agent 11 — `EvidenceRetriever` (~900 LOC)

The single most complex agent. Public entry: `EvidenceRetriever.retrieve_evidence(claim, company)`.

**Pipeline (two stages):**

1. **Broad fetch** — fans out to 14 retrievers in parallel (mix of async & sync, gated by API keys / availability):

   - **Metered news**: `fetch_newsapi`, `fetch_newsdata` (capped at NEWSAPI_FETCH_CAP=50 / NEWSDATA_FETCH_CAP=50)
   - **Free web**: `fetch_duckduckgo`, `fetch_reuters_rss`, `fetch_google_news_rss`, `fetch_google_scholar` (Semantic Scholar)
   - **ESG registries**: `fetch_cdp_evidence`, `fetch_sbti_registry_evidence`, `fetch_gri_database_evidence`, `fetch_companies_house_evidence`
   - **Company-issued**: `fetch_company_ir` (HEAD-checks investor-relations URLs)
   - **Lobbying / sanctions**: `fetch_influencemap_evidence`, `fetch_opensanctions_evidence`
   - **Adversarial**: `fetch_adversarial_evidence` (8 site-specific DDG queries hitting ClientEarth, ReclaimFinance, AFM, rechtspraak.nl, EUR-Lex, SEC, etc.)
   - **Vector store**: `vector_store.search_similar(claim, n=5)` for historical context

   Each call is wrapped in `_try_async` / `_try_sync` which records the per-retriever result count in a `tally: Dict[str, int]`:
   - `tally[name] > 0` → contributed
   - `tally[name] == 0` → silent miss
   - `tally[name] == -1` → exception

   Printed summary line:
   ```
   📊 retrieval tally — contributed=8, silent=6, crashed=0
      silent (0 items): cdp, google_scholar, newsapi, newsdata, reuters_rss, sbti
   ```

2. **Filter & enrich**:
   - **Blocklist** removes URLs from `BLOCKED_DOMAINS` (linkedin.com, web.archive.org, wikipedia.org, etc.)
   - **Relevance filter** in `_filter_relevant_evidence()` — checks for ESG keywords OR a `PRIORITY_DOMAINS` host (reuters.com, bloomberg.com, sec.gov, sebi.gov.in, …)
   - **Company-name filter** drops items mentioning a *different* company more times than the target. ⚠️ **Known bug**: this uses naive substring matching, so common-word company names like `BP`, `GM`, `Target`, `Apple`, `Oxy` produce false positives. Real fix is word-boundary regex `\b{company_lower}\b` or proper tokenisation. Current symptom seen in JPMorgan run: ~15 valid items dropped because phrases like "net zero **target**" or "J**P Morgan**" were treated as references to companies named "Target" / "GM".
   - **URL-level dedup** by `seen_urls` set
   - **Tier-1 fallback** — if no Reuters/Bloomberg present, append a stub Reuters Sustainability link
   - **Full-text fetch** — async HTTP GET on up to 20 URLs, body capped at 2000 chars
   - **Final ranking** — return top 35 by source quality + full-text availability

The `retrieve_evidence` output schema:
```python
[
  {
    "source_name": "...", "source_type": "...", "url": "...",
    "title": "...", "snippet": "...", "full_text": "...",
    "data_source_api": "NewsAPI.org" | "Google News RSS Fallback" | ...,
    "reliability_tier": 1..4,
    "relationship_to_claim": "Supports" | "Contradicts" | "Neutral",
    "stance": "...", "date": "...", "credibility_weight": 0.30..1.0
  },
  ...
]
```

#### Agent 20 — `RiskScorer` (~2000 LOC)

The master scorer. Consumes everything upstream and produces:

- `greenwashing_score` (`GW`, 0–100) — the headline number
- `esg_performance_score` (0–100)
- `pillar_scores` (E, S, G — each 0–100)
- `final_score` — blended verdict signal
- `component_breakdown` — tracked in `state.esg_score_lineage`

**The Master GW Formula** (full math is in §7):

```
GW = α · gap_term + β · R + γ · (1 − D/100) · 100 + δ · T
```

with industry-tuned weights (oil-and-gas / banking / retail / tech / default profiles), a `T = 0` redistribution rule, and a Verified-vs-Probabilistic risk blend on top.

**WBA/SEC injection**: when primary IR data is missing, `fill_missing_pillars()` (in `core/esg_data_apis.py`) overlays World Benchmarking Alliance scores and SEC DEF 14A metrics. Pillar weights from `config/materiality_map.json` are applied in `pillar_factors_builder.py`.

### 6.3 The remaining 21 agents — one-paragraph each

**1. AdversarialEvidenceValidator** — Deterministic. Maps every evidence item to one of 8 credibility tiers (`government_regulatory=0.95` → `company_self_report=0.30`) and a stance (`supports` / `contradicts` / `neutral`) by keyword matching. Outputs `triangulation_score = (support_weight / total_weight) × 100`, penalised −10 if contradict outweighs support, plus an `evidence_balance` enum.

**2. CarbonExtractor** — Regex + unit-aware extraction of Scope 1/2/3 from evidence + parsed-report chunks. Multipliers: billion tonnes → 1e9, million tonnes → 1e6, tCO2e → 1. Validates against industry minimums (banking scope1 ≥ 10k, oil&gas scope1 ≥ 1M). Backfills scope1 from a combined scope1+2 figure when individual values are missing. Carries a built-in known-emissions DB for ~40 companies (Microsoft, Tata Steel, Shell, Infosys, …) cross-checked against CDP / BRSR.

**3. CarbonPathwayModeller** — Compares claimed targets to IEA NZE benchmarks and IPCC carbon budgets. Computes the implied CAGR of emissions reductions and, when the carbon budget is exhausted, caps it at `IEA_NZE_CAP = 45 %/yr` (the maximum scientifically cited rate). Flags `PHYSICALLY_IMPOSSIBLE` when production growth + Scope 3 *absolute* reduction (not intensity-only) collide in energy / oil-and-gas.

**4. ClaimDecomposer** — LLM-driven atomisation of compound claims. Output is an array of `sub_claims` with `id`, `text`, `pillar`, `measurable`, `verification_requirements`, `greenwashing_signal`. Detects `logical_tension_pairs` between sub-claims (physical_impossibility ×1.5, goal_conflict ×1.2, timeline_clash ×0.9) and computes `internal_contradiction_score` = `Σ weight × multiplier × 25`, capped at 100. Falls back to conjunction-splitting heuristics if the LLM fails.

**5. ClaimExtractor** — LLM-driven extraction of claims from arbitrary report chunks, with multi-stage JSON salvage (`strict → repair_json_common_issues → extract_claims_array → salvage_claims_objects`). Filters out non-ESG chunks, ranks by Jaccard overlap × 0.6 + numeric density × 0.2 + target-term hits × 0.2, dedups by token-set Jaccard ≥ 0.75. Cached for 7 days on disk.

**6. ClaimIntensityScorer** — Pure function `calculate_claim_intensity(claim_text, sub_claims)`. Five dimensions, max 100:
- Specificity (0–30): year ref +10, % or large number +10, baseline reference +10
- Verifiability (0–20): scope mention +8, framework ref (GRI/SASB/TCFD/CDP) +7, external body (SBTi) +5
- Ambiguity penalty (0–20): each hedging token (`aim to`, `may`, `could`) costs 7
- Scope clarity (0–15): scope [123] +5, supply chain +5, gas type (CO2/GHG/CH4) +5
- Third-party bonus (0 or 15)
Then weighted by claim type: `quantitative_target=1.00`, `alignment_claim=0.75`, `strategic=0.40`, `marketing=0.15`. Output is `C` in the master formula.

**7. ConfidenceScorer** — Aggregates data quality into a 0–100 score with a `HIGH` / `MEDIUM` / `LOW` label. Components: source quantity (0–25, max at ≥15), source quality (0–25, avg credibility × 15 + high-credibility count × 2), data recency (0–20, max if <30 days), historical context (0–15), evidence completeness (0–15, −5 per evidence_gap).

**8. ConflictResolver** — When evidence items contradict, weights them by source-type credibility (`Academic=1.0, Gov=0.95, NGO=0.90, Tier-1 Media=0.85, ESG Platform=0.75, General Media=0.70, Web=0.50, Company=0.30`). Verdict logic: `Likely True` if `support_weight > contradict_weight × 1.5`, `Likely False` if reversed, otherwise `Conflicting—Uncertain` with confidence floor 40. Adds an LLM scan over the top 3 supporting + 3 contradicting sources for arbitration.

**9. ContradictionAnalyzer** — Three-way contradiction detection: (a) match against curated `KNOWN_GREENWASHING_CASES` regulatory DB (~20 cases in `data/known_cases.py`); (b) Cypher query against the Neo4j knowledge graph for contradiction edges + reasoning paths; (c) LLM scan for temporal violations. Drops snippets <40 chars, mid-word truncations, archive snapshots >5y old (unless year ref present), non-archive items >8y old. Optional historical-snapshot retrieval via Wayback + Memento at the target year.

**10. CredibilityAnalyst** — Per-source credibility (0–1) and bias scoring. Base scores by source_type. Heuristic adjustments: HTTPS +0.03, missing URL −0.08, .gov/.edu/.sec +0.05, blog/Substack −0.10, fresh data (<30d) +0.03, ancient data (>10y) −0.03, paid content −0.25. Bias detection counts pro-company indicators ("revolutionary", "leader") vs critical indicators ("violation", "greenwashing"); if pro > critical+2 → "Pro-company". LLM-analyzes the first 6 sources (8s timeout) for nuance, heuristic for the rest. Cached 30 days (called ~47× per report — bottleneck if slow).

**11. EvidenceRetriever** — see §6.2.

**12. FinancialAnalyst** — Looks up ticker via 40+ symbol map, calls `yfinance.Ticker().info`, plus an Alpha Vantage fallback. Computes `financial_health_score` (0–100) from profit margin, debt/equity, revenue growth, current ratio, beta. Greenwashing flags:
- FLAG 1: net-zero claim in energy/oil/gas + revenue growth >5% → `severity=HIGH, risk +25%`
- FLAG 2: sustainable claim + carbon_intensity >0.01 → `MODERATE, +15%`
- FLAG 3: profit margin >25% + esg_score <50 → `MODERATE, +10%`
- FLAG 4: invest/commitment claim + debt/equity >2.0 → `LOW, +8%`

**13. GovernanceAgent** — Baseline 58.0. Hard-cap to 45 if board independence <40%; hard-cap to 35 if ESG claim with `LTI esg_pct=0`; hard-cap to 35 if ethical-culture claim with `regulatory_fines>0`. Penalties: CEO/worker pay ratio >300× → −8; tax_rate_delta >10% → −6; dual-class +6/poison pill +5/staggered board +5. Bonus +4 for independent audit committee. Pulls SEC DEF 14A via `web_search`.

**14. GreenwishingDetector** — Detects three deception patterns:
- *Greenwishing*: unfunded targets, vague timelines, no pathway, aspirational language
- *Greenhushing*: missing required disclosures (scope 1/2/3, renewable %, net-zero year, SBTi, climate capex)
- *Selective disclosure*: cherry-picking best metrics, boundary manipulation (operational vs financial control), baseline gaming (restated baselines)
Includes a BRSR mandatory-field audit. LLM-driven with `GREENWISHING_DETECTION_PROMPT`.

**15. HistoricalAnalyst** — Mines evidence + KG + known-cases for past violations and positive achievements. Computes `reputation_score` (0–100) and trend (`IMPROVING` / `STABLE` / `DECLINING`).

**16. IndustryComparator** — Was the peer-percentile engine; **the call-site `save_peer_to_database_node` is now deprecated** (prints a deprecated message and no-ops). The class still works in isolation if invoked.

**17. MultiJurisdictionRegulatoryScanner** — Maps the claim against rulebooks for SEC Climate Rules (US), CSRD (EU), FCA anti-greenwashing (UK), SEBI BRSR (India), TCFD. Output: `compliance_by_jurisdiction = {sec: {status, gaps, red_flags}, csrd: {...}, ...}`.

**18. RealtimeMonitor** — Designed to poll news APIs every N hours and emit alerts when new signals contradict the baseline assessment. In the standard pipeline call it runs once per analysis to capture recent signals; the polling daemon mode is not wired into the LangGraph runtime.

**19. RegulatoryScanner** — Searches enforcement databases for actual violations: SEC EDGAR (10-K legal proceedings, 10-Q, 8-K), EU REACH/EIA, UK FCA actions, ASIC continuous-disclosure breaches, India MCA & BRSR non-compliance.

**20. RiskScorer** — see §6.2 and §7.

**21. SentimentAnalyzer** — Uses Groq (`llama-4-scout-17b`) with a 500-token budget. Outputs `divergence_score` (0–100, how far the claim's tone diverges from the evidence's tone), `gsi_score` (Greenwashing Sentiment Index), and a sentiment breakdown. `risk_scorer` blends them as `(divergence × 0.65) + (gsi × 0.35)`.

**22. SocialAgent** — Pillar score (0–100) from diversity (gender %, ethnicity %, mgmt representation), pay equity (wage gap by gender/ethnicity), H&S (injury rate, fatalities → hard-cap 40), and grievance count. Penalties: gender <30% → −15; pay gap >15% → −20; >5 substantiated grievances → −15.

**23. TemporalConsistencyAgent** — Compares the current claim against archived versions of the same company's prior statements. Detects `missed_target` / `contradicts_past` / `reversed_commitment` violations. Uses Wayback Machine and the company KG. `consistency_score = 100 − (violations × 25)`, clamped 0–100.

---

## 7. The Scoring Engine — Greenwashing Risk Formula

File: **`agents/risk_scorer.py`** (~2000 LOC). The headline number every other layer of the system reports is **GW (Greenwashing Risk Score, 0–100)**.

### 7.1 The master formula

```
GW = α · gap_term + β · R + γ · (1 − D/100) · 100 + δ · T

where:

    gap_term = min(100, max(0, C − P) / σ_industry × 100)

    C            = Claim Intensity Score   (0–100, from ClaimIntensityScorer, §6.3 #6)
    P            = Performance Score       (0–100, from pillar analysis)
    σ_industry   = industry volatility constant (~25 for heavy industry, ~15 for tech)
    R            = Controversy Risk        (0–100, from contradiction + historical)
    D            = Disclosure Score        (0–100, from evidence quality + framework hits)
    T            = Temporal Consistency    (0–100, from temporal_consistency_agent)
```

Component intuition:

- **Gap term** — penalises claims that promise more than the company delivers. Normalised by σ to be fair across volatile sectors.
- **R** — captures *active* wrongdoing (regulatory findings, contradictions, controversies).
- **(1 − D/100) × 100** — turns disclosure into a deficit; companies that hide their data are penalised for *greenhushing*.
- **T** — companies that escalate claims while flatlining on emissions, or shift goalposts.

### 7.2 Industry weight profiles (from code)

| Industry bucket | α (Gap) | β (R) | γ (Deficit) | δ (T) |
|---|---|---|---|---|
| Oil & Gas, Energy, Coal, Mining, Aviation | 0.45 | 0.30 | 0.15 | 0.10 |
| Banking, Insurance, Asset Mgmt, Finance | 0.30 | 0.35 | 0.20 | 0.15 |
| Retail, Food, Consumer, Fast Fashion | 0.40 | 0.25 | 0.25 | 0.10 |
| Tech, Software, Healthcare | 0.35 | 0.20 | 0.30 | 0.15 |
| **Default** | **0.35** | **0.25** | **0.25** | **0.15** |

### 7.3 Risk Mitigation #2 — `T = 0` redistribution

When there is insufficient temporal data (`T == 0.0`), δ is redistributed:
- α += δ × 0.6
- γ += δ × 0.4
- δ = 0.0

This avoids zero-padding the score with the missing dimension; the weight is reallocated to the two best-supported terms.

### 7.4 Verified vs Probabilistic risk blend

Per the README's design and the code in `risk_scorer.py` (lines ~2467–2474), `R` is itself a 60/40 blend of **verified** regulatory gaps (hard data from SEC/WBA/government fines) and **probabilistic** contradictions (signals from `contradiction_analyzer`):

```
R = 0.6 · R_verified  +  0.4 · min(100, contradictions_count × 20)
```

There's also a **claim-verification risk** computed when the contradiction analyzer attaches a verdict to each claim:

```
verification_risk = (
    contradicted     × 100 +
    unverifiable     × 85  +     # raised from 70 in 2026
    partial          × 50  +
    verified         × 0
) / total
```

Falls back to 50 (neutral) if no verification data is available.

### 7.5 Pillar scores (E / S / G)

In `core/pillar_factors_builder.py`, each pillar is decomposed into ~5–6 sub-indicators (more for industry-specific extensions). Defaults:

| Pillar | Sub-indicators (weights) |
|---|---|
| **Environmental** | GHG Intensity 0.25, Scope 3 Coverage 0.15, Renewable Energy 0.20, Water 0.17, Biodiversity 0.13, Waste & Circular 0.10 |
| **Social** | H&S 0.25, Labor Rights 0.25, Community Impact 0.20, Supply Chain Labor 0.15, D&I 0.15 |
| **Governance** | Board Independence 0.20, Board Diversity 0.20, Exec Pay Ratio 0.20, Anti-Corruption 0.20, Whistleblower 0.10, ESG Disclosure Quality 0.10 |

Industry-specific additions:
- **Energy / Oil & Gas**: Methane Leakage, Stranded Asset Risk, Carbon Capture, Just Transition
- **Manufacturing**: Supply-Chain Emissions, Product End-of-Life, Chemical Hazard Mgmt
- **Banking / NBFC**: Green Lending Ratio, Climate Risk in Loan Book, Financial Inclusion
- **Tech**: Data Centre PUE, E-Waste Policy, Algorithm Fairness
- **Retail/Consumer**: Packaging Recyclability, Living Wage in Supply Chain

For 28 of these indicators, structured threshold rules map raw numbers to bucket scores (100 / 75 / 50 / 25 / 0). E.g., **Renewable Energy %**: ≥80 → 100, ≥50 → 75, ≥30 → 50, ≥10 → 25, else 0.

`coverageadjustedscore` is the weighted average over only the *available* (non-null) sub-indicators, preventing a single missing data point from dragging the pillar down.

### 7.6 Final blended score

```
final_score = (esg_performance × 0.65) − (greenwashing_score × 0.35)
```

Plus external benchmark adjustments — e.g., WRI Aqueduct water-risk delta = `(water_risk_external − 50) × 0.12`.

### 7.7 Score lineage

Everything that fed into the score is dumped into `state.esg_score_lineage` and (when `ESG_SAVE_FULL_RESULTS=1`) written to `reports/debug_esg_lineage_<Company>.json`. This is the audit trail that lets you reverse-engineer any number in the report.

### 7.8 Calibration

`ml_models/score_calibrator.py` performs logistic recalibration of the rule-based score against a small ground-truth corpus, with guardrails: 20–50 % blend with the raw score and absolute delta capped at 12–20 points. Sample-size warnings are exposed in the report:

| n | Status |
|---|---|
| n ≥ 30 | STABLE |
| 10 ≤ n < 30 | LIMITED |
| n < 10 | PROVISIONAL |

A previous bug *suppressed* the score altogether when n < 30; that has been removed (see `IMPROVEMENTS_SUMMARY.md`). Scores are now always shown with the calibration tier annotated.

---

## 8. Knowledge Graph, Fact Graph, Pillar Factors, Commitment Ledger

The system maintains **three parallel graph/ledger structures**, each with a different scope.

### 8.1 Company Knowledge Graph — `core/company_knowledge_graph.py` + `core/kg_schema.py`

**Backend**: Neo4j (Bolt driver, direct local connection to bypass routing). Falls back to **JSON payloads** at `reports/company_kg/<company_slug>_company_kg_payload.json` if Neo4j is unavailable, plus an append-only `<company_slug>_kpi_history.jsonl` for cross-run drift analysis.

**Schema** (`kg_schema.py`):

| Node type | Purpose |
|---|---|
| `Organization` | Anchor — the company itself |
| `Facility` | Physical sites (extracted from contradictions / regulatory mentions) |
| `KPI` | Numeric metrics (Scope 1/2/3, water, energy, …) |
| `RegulatoryVerdict` | Findings from contradiction analyzer / regulatory scanner |
| `SustainabilityGoal` | Net-zero / carbon-negative / renewable-target pledges |
| `EvidenceSource` | Every cited source, tagged with `source_tier` 1–4 |

| Edge type |
|---|
| `HAS_KPI`, `HAS_REGULATORY_VERDICT`, `HAS_SUSTAINABILITY_GOAL`, `HAS_FACILITY`, `SUPPORTED_BY` |

**Build flow** (`build_company_kg_package(state)`):
1. Normalise company anchor (`_normalize_company_anchor()`) — name + ticker
2. Mine `state.agent_outputs` for contradictions
3. Extract KPIs (`_extract_kpis()`) from `state.carbon_extraction.emissions`
4. Extract goals (`_extract_goals()`) — net-zero, carbon-negative, renewable
5. Build `RegulatoryVerdict` nodes from contradictions, attaching at facility level when a facility is mentioned
6. Link every evidence source as an `EvidenceSource` node
7. (Optional) If `KG_USE_LLM_GRAPH_TRANSFORMER=true`, run LangChain's `LLMGraphTransformer` to derive additional triples from claim/evidence text

**Querying**:
- `run_cypher(cypher, params)` — direct query
- `hybrid_retrieve(company, claim_text, ticker)` — returns up to 20 KPI/Verdict nodes with attached evidence + reasoning paths

### 8.2 Fact Graph — `core/fact_graph_builder.py` + `core/fact_graph_persistence.py`

**Different from the company KG**: claim-centric, lightweight, JSON-only, derived per run.

`build_esg_fact_graph(company, claim_text, evidence, contradictions, temporal_consistency, normalized_sg_evidence)`:

- Creates a claim root node
- Iterates evidence (cap 200) and adds `fact` nodes with `pillar` (E/S/G keyword detection), `polarity` (negative if violation/fine/lawsuit terms present), `verifiability_score` (URL presence + source type + numeric content + length)
- Adds `contradiction_fact` nodes (cap 60), `temporal_fact`, `normalized_fact`
- Edges: claim → fact (`supported_by` / `challenged_by` / `time_consistency_check`, weighted), fact → source (`sourced_from`)
- Returns a summary with `fact_count`, `verified_fact_count`, `claim_linked_fact_count`, `coverage_by_pillar`, and `is_decision_ready` (heuristic: ≥4 verified facts + ≥1 linked)

Persistence: `reports/fact_graphs/<company>_<report_id>_fact_graph.json` (default `report_id = timestamp`).

### 8.3 Pillar Factors — `core/pillar_factors_builder.py`

See §7.5 for the indicator list. Key implementation notes:

- `FactorResult` Pydantic model validates `score` (0–100), `weight` (0–1), `data_quality` ∈ {Verified, Estimated, Unverified, No Disclosure}, `data_tier` (1–4), GRI/SASB alignment lists.
- `_rescale_scores_to_target()` — when an externally provided pillar target exists, rescales the *flexible* indicators to match it while preserving locked structured-threshold indicators.
- `synthesize_sec_metric_evidence()` — extracts board independence %, pay ratio, anti-corruption policy, whistleblower hotline from SEC DEF 14A and injects them as high-reliability evidence rows.

### 8.4 Commitment Ledger — `commitment_tracker/ledger.py`

**Backend**: SQLite at `data/commitment_ledger.db`.

Two tables:

`commitments` — one row per pledge per run:
```
company, run_id, run_date, claim_text, sub_claim_id,
commitment_type, target_year, target_metric, target_value,
target_direction, baseline_year, baseline_value, current_value,
progress_pct, status, evidence_url, confidence
```

`commitment_revisions` — promise-degradation tracking:
```
company, original_commitment_id, revision_date,
original_text, revised_text, revision_type, severity_score, explanation
```

Where `revision_type` ∈ {`claim_dropped`, `target_weakened`, `deadline_extended`, `scope_narrowed`, `reframed`, `baseline_reset`}.

`update_from_subclaims()` matches new sub-claims to historical via 0.7 × semantic similarity (`sentence-transformers/all-MiniLM-L6-v2`) + 0.3 × lexical Jaccard, threshold 0.75. Computes a `promise_degradation_score` with weighted penalties (claim_dropped=30, target_weakened=20, …) × recency_weight × severity/100, capped at 100.

### 8.5 Static reference data — `data/`

| File | Purpose |
|---|---|
| `known_cases.py` | Curated DB of ~20 verified greenwashing cases (BP, Shell, HSBC, VW, Ryanair, H&M, ExxonMobil, Amazon, JPMorgan, Coca-Cola, Delta, Google, Goldman, DWS, …). Each: `claim_pattern` (regex), `contradiction_text`, `source`, `source_url`, `year`, `severity`, `regulatory_body`. Matched via `get_known_contradictions()` with `confidence=HIGH` + `source_type=verified_regulatory_case`. |
| `peer_database.json` | Sector-grouped peer ESG scores: `peers.{banking, energy, …} = [{name, ticker, esg_score, greenwashing_risk_score, environmental_score, social_score, governance_score, rating, source}]` |
| `sbti_company_cache.json` | SBTi-validated targets cache (~70 KB) — status, baseline/current/target values, alignment categories |
| `emissions_floors.json` | Per-sector emissions baselines for intensity normalisation |
| `esg_mismatch_results.json` | Historical outputs of the standalone mismatch detector |

### 8.6 ChromaDB

`chroma_db/peer_comparison_history/chroma.sqlite3` — vector store of past peer-comparison embeddings. Used by the peer-comparison node to retrieve semantically similar prior runs and detect drift over time.

---

## 9. Caching Subsystems

The system runs many expensive operations (LLM calls, scrapes, PDF downloads). Caching is layered:

### 9.1 Evidence cache — `core/evidence_cache.py`

- **Scope**: results of `EvidenceRetriever` per company
- **Key**: `<company_lower_with_underscores>` or `<company>_<md5(query_suffix)[:8]>`
- **TTL**: 24 hours
- **Storage**: in-memory singleton (volatile per session) + JSON files at `cache/evidence/{cache_key}.json`
- **Metadata**: each cache entry carries `_cache_metadata = {company, cached_at, cache_key}`
- **Session vs disk**: `clear_session_cache()` is called at the *start* of every run (in `assess_complexity_node`), but disk cache is preserved
- **APIs**: `has_evidence()`, `get_evidence()`, `store_evidence()`, `get_cache_stats()`

### 9.2 LLM response cache — `core/llm_cache.py`

- **Key**: `MD5(prompt)`
- **Layout**: `cache/llm_responses/{agent_name}/{md5_hash}.json`
- **File format**: `{"timestamp": <unix>, "response": "<string>"}`
- **Per-agent TTL**:

| Agent | TTL |
|---|---|
| `credibility_analysis` | **30 days** (called ~47× per report — heavily reused) |
| `peer_comparison` | 14 days |
| `temporal_analysis` | 7 days |
| **default** | 7 days |

- **Observed agent subdirs**: `claim_extraction/`, `claim_extractor/`, `contradiction_analysis/`, `credibility_analysis/`, `debate_orchestrator/`, `esg_mismatch/`, `financial_analysis/`, `greenwashing_detection/`, `regulatory_scanning/`, `risk_scoring/`, `sentiment_analysis/`, `supervisor/`

### 9.3 Per-source caches in `cache/`

| Subdir | What populates it |
|---|---|
| `evidence/` | EvidenceRetriever results (24h TTL) |
| `llm_responses/{agent}/` | LLM output (7–30d TTL) |
| `claim_extraction/` | Extracted claims from report chunks |
| `parsed_reports/` | Post-processed report structures |
| `company_reports/` | Parsed PDF extracts |
| `financial_data/` | Ticker / market-cap / yfinance lookups |
| `cdp_data/` | CDP questionnaire scrapes |
| `peer_data/` | Cached peer-company metrics |
| `search/` | DuckDuckGo / web search results |
| `esg_analysis/` | **Mismatch detector** outputs (24h TTL) |
| `camelot_temp/` | Scratch files for Camelot PDF table extraction (auto-cleaned) |

### 9.4 Source tracker — `utils/source_tracker.py`

Decorator pattern (`@source_tracker.track("NewsAPI")`) that records every retriever call's success/failure and item count, then writes a per-company report:

```json
{
  "summary": {
    "total_sources_called": 15,
    "sources_with_results": 9,
    "sources_failed": 6,
    "success_rate_percent": 60.0,
    "total_results_retrieved": 52
  },
  "detailed_stats": {
    "sources_called": [...],
    "sources_with_results": [...],
    "sources_failed": [...],
    "results_per_source": {...}
  }
}
```

This is the same data surfaced by the live "📊 retrieval tally" line in pipeline logs.

---

## 10. Data Sources & Retrievers

The pipeline draws on **28+ external feeds**. Below is the inventory grouped by status.

### 10.1 Currently working reliably

| Source | File / function | Auth | What it returns |
|---|---|---|---|
| DuckDuckGo Web | `agents/evidence_retriever.py:fetch_duckduckgo` | none | Real-time web/news results |
| Reuters RSS | `:fetch_reuters_rss` | none (RSS) | Sustainability feed entries |
| Google News RSS | `:fetch_google_news_rss` | none | Aggregated news (always-on fallback) |
| Company IR | `:fetch_company_ir` | none (HEAD checks) | Investor-relations / sustainability page links |
| UK Companies House | `:fetch_companies_house_evidence` | none | UK filings, directors, status pages |
| OpenSanctions | `:fetch_opensanctions_evidence` + `utils/enhanced_data_sources.py:get_anti_corruption_status` | none (api.opensanctions.org/v1/match) | Sanctions / PEP screening |
| Adversarial DuckDuckGo | `:fetch_adversarial_evidence` | none | 8 site:-targeted queries (ClientEarth, Reclaim Finance, AFM, rechtspraak.nl, EUR-Lex, SEC, …) |
| Vector store | `core/vector_store.py` via `:vector_store.search_similar` | none | Historical context from past runs |
| SEC EDGAR | `utils/web_search.py:get_sec_filings_realtime` | optional `SEC_API_KEY` (else free atom feed) | 10-K, 10-Q, 8-K |

### 10.2 Currently **silent** (returning 0 items in recent runs)

| Source | Likely reason |
|---|---|
| **NewsAPI** | `NEWS_API_KEY` env var missing or invalid |
| **NewsData.io** | `NEWSDATA_KEY` missing / expired |
| **Reuters RSS** | RSS feed is fine, but the in-process company-name filter rejects items that don't contain the exact match; no Reuters items mention "JPMorgan Chase" by exact phrase in the last 24h |
| **CDP** | BeautifulSoup parse fails or company isn't in CDP's public DB |
| **SBTi registry** | Page structure changed; HTML parser only returns a fallback entry |
| **Google Scholar** (via Semantic Scholar) | API timeout / rate limit |
| **InfluenceMap** | DuckDuckGo `site:` search returns 0 results for some companies |
| **GRI Database** | Site-specific search frequently empty |

**These are the silent retrievers identified in the most recent JPMorgan Chase run.** Fixing them is on the immediate backlog (§19).

### 10.3 Government / international (in `utils/enhanced_data_sources.py`)

| Source | Function | Notes |
|---|---|---|
| ILO (International Labour Org) | `get_ilo_violations` | NORMLEX public DB; HTML parse — frequently silent |
| UN Global Compact | `get_un_global_compact_status` | Web scrape for signatory status |
| OECD Guidelines | `get_oecd_guidelines_cases` | OECDWATCH + NCP DB; simplified extraction |
| EU Taxonomy | `get_eu_taxonomy_alignment` | EC portal; placeholder when NOT_FOUND |
| UNFCCC Race to Zero | `get_unfccc_net_zero_pledges` | Pledge year + target year |
| Open Apparel Registry | `get_supply_chain_transparency_data` | Apparel sector only |
| World Bank Climate | base URL | Country-level CO₂ / renewables % |
| WBA (World Benchmarking Alliance) | `core/esg_data_apis.py:query_wba` | Cross-industry pillar fill (`fill_missing_pillars`) |
| WRI Aqueduct 4.0 | `core/esg_data_apis.py:query_wri_aqueduct` | 13 water-risk indicators (8 physical, 3 regulatory, 2 reputational) |

### 10.4 India-specific stack

`utils/indian_data_sources.py` (`IndianDataAggregator`) and `utils/indian_financial_data.py`:

- Working: Indian News RSS (Economic Times, Business Standard, LiveMint, Moneycontrol), NewsData.io with `country=in`, Google News India fallback, World Bank country query
- Stub-only: SEBI BRSR filings, MCA registry (CSR data), CPCB compliance, NGT cases, India Environment Portal, CSE, WRI India
- Financial: Screener.in scrape, Yahoo Finance scrape; symbol map covers 50+ Nifty companies

### 10.5 Report Discovery → Download → Parse pipeline

This sub-pipeline (3 utility modules + Camelot extractor) finds and ingests official sustainability PDFs.

**`utils/report_discovery.py`** — `ReportDiscoveryService.discover_reports(company_name)`:
- Cache check (7-day TTL)
- 11 parallel DuckDuckGo queries: `"{company} sustainability report pdf"`, `"{company} ESG report pdf"`, `"{company} annual report sustainability pdf"`, `"{company} BRSR report"`, …
- Filter for `.pdf` extension + trusted hosts
- Extract year via regex `(20\d{2})`
- Classify report type (ESG, Sustainability, Annual, CSR, BRSR, Climate)
- Confidence score (0–1) from domain match (0.25), trusted hosts (0.20), title keywords (0.20), recency (0.05–0.15)
- Sort by year desc → confidence desc → return top N

**`utils/report_downloader.py`** — `ReportDownloaderService`:
- 7-day TTL cache (MD5 of URL → `cache/reports/report_<hash>.json`)
- MAX_FILE_SIZE = 100 MB, TIMEOUT = 30 s, MAX_RETRIES = 3
- HEAD then streamed GET; aborts if oversized
- Validates PDF magic bytes (`%PDF`)
- Pre-defined fallback URLs for major issuers (BP, Shell, Exxon, …)

**`utils/report_parser.py`** — `ReportParserService.parse_report(local_path)`:
- 7-day TTL cache by file hash
- Tries **Camelot** first when `TABLE_TRIGGER_KEYWORDS` are detected (e.g., "scope 1", "CO2e", "emissions") — table-aware extraction via `core/extractors/pdf_table_extractor.py`
- Falls back to **PyPDF2** / **pdfplumber**
- Chunks: 2000 chars, 200 overlap, preserves section headers, detects tables
- Output: `[{chunk_id, text, page_num, is_table, section}, ...]`

### 10.6 Adversarial retrieval

`fetch_adversarial_evidence(company, claim_text)` is the system's "dissenting voice" channel. Strategy is 8 site-specific DuckDuckGo queries:
```
"{company} climate lawsuit greenwashing ClientEarth Reclaim Finance"
"site:clientearth.org {company} climate"
"site:reclaimfinance.org {company} climate"
"site:influencemap.org {company} climate lobbying"
"site:afm.nl {company} greenwashing OR sustainability claim"      ← Dutch regulator
"site:rechtspraak.nl {company} climate ruling OR judgment"        ← Dutch courts
"site:eur-lex.europa.eu {company} sustainability disclosure"
"site:sec.gov {company} climate disclosure lawsuit"
```
+ a dynamic ninth query if the claim mentions "1.5", "net zero", "scope 3", or "production growth": `"{company} production growth scope 3 contradiction"`.

Items are tagged `stance=Contradicts` if the text contains lawsuit / greenwashing / misleading / court / ruling / enforcement / violation / investigation. Returns up to 72 items (6× cap) after async fan-out and dedup.

### 10.7 How retrievers compose into the final evidence pool

In `EvidenceRetriever.retrieve_evidence(claim, company)` (lines ~1005–1250):

1. **Stage 1 broad fetch** — async fan-out to all 14 retrievers (with per-source caps; e.g., NewsAPI 10, DuckDuckGo 10, Reuters RSS 5, scholar 5, adversarial 3-then-batched).
2. Per-retriever yield logged with `✓` (contributed), `⚠️ silent miss`, or `⚠️ raised`.
3. **Stage 2 filter & enrich**:
   - Blocklist domain filter
   - Relevance filter (ESG keywords OR priority host)
   - Company-name filter (⚠️ has substring bug — see §6.2 / §19)
   - URL dedup
   - Tier-1 fallback (synthetic Reuters Sustainability link if no Reuters/Bloomberg present)
   - Full-text fetch for up to 20 URLs (cap 2000 chars)
4. Final ranking by source quality + full-text availability → top 35 items.

---

## 11. Report Generation — TXT, JSON, PDF

Every successful run produces three artefacts (or four with `ESG_SAVE_FULL_RESULTS=1`).

### 11.1 TXT — `core/professional_report_generator.py`

Entry: `ProfessionalReportGenerator.generate_executive_report(state)`.

The report is rendered by `_render_v4_report` (lines ~1187–3320 of the generator) and is structured as **12 sections + 3 appendices**:

| # | Section | Content |
|---|---|---|
| 1 | (Preamble / metadata) | Run header, company, claim, industry, report ID |
| 3 | Executive Summary | Multi-sentence overview, evidence count, confidence |
| 3B | Claim Breakdown | Sub-claims from `state.claim_decomposition` |
| 4 | Evidence Citations Table | All sources with stance, credibility, verification status |
| 5 | Score Derivation (E / S / G) | Pillar scores, weights, contributions, sub-indicators, external benchmarks |
| 6 | Key Risk Drivers | Top SHAP-valued + inferred risk factors |
| 7 | Contradictions & Regulatory Alerts | High-severity contradictions; gaps by framework |
| 8 | Carbon Emissions & Climate Data | Scopes 1/2/3, net-zero target, data quality |
| 8B | Carbon Pathway Alignment | IEA NZE gap %, required vs implied CAGR |
| 9 | Deception Pattern Analysis | Greenwishing/greenhushing/selective disclosure/carbon tunnel vision/ClimateBERT |
| 10 | Calibration & Confidence | Spearman r, optimal threshold, agent success rate, duration |
| 11 | Limitations | Quality warnings, evidence gaps, synthetic peer usage, calibration n |
| **A** | Validation & Calibration Status | Sector coverage, contradiction DB, data sources |
| **B** | Temporal ESG Consistency | Temporal score, risk level, claim trend, env trend |
| **C** | Evidence & Offset Integrity | Realism confidence, source diversity, premium-source %, reliability tier |

#### `ReportQualityChecker` (lines 50–239)

Flags ~10 quality issues, including: <3 verifiable sources, unverifiable evidence excluded, pillar scores without traceable factors, synthetic peer usage, failed critical agents (`carbon_extraction`, `regulatory_scanning`, `risk_scoring`, `temporal_consistency`).

Confidence tiers:
- **HIGH** — n ≥ 10 verified sources, ≤ 2 failed agents
- **MEDIUM** — n ≥ 5, ≤ 2 failed
- **LOW** — otherwise

Calibration tiers:
- n < 10 → **PROVISIONAL**
- n < 30 → **LIMITED**
- else → **STABLE**

The `generate_executive_report` wrapper catches per-section errors and emits a structured fallback partial report with `stages_completed`, `stages_failed`, `warnings`. Max report size 500 KB (truncates if exceeded).

### 11.2 JSON — `core/report_schema.py` + `api/mappers.py`

The JSON written to disk (`reports/ESG_Report_<co>_<ts>.json`) is a richer machine-readable export. When read via the API (`GET /api/reports/{id}`), `api/mappers.py:map_report_to_schema()` normalises it into a Pydantic `ESGReport`, calling specialised sub-mappers:

- `_map_pillar` → `PillarScore` (score, coverage_adjusted_score, weight, positive_signals, contradictions)
- `_map_carbon` → scopes 1/2/3, net-zero target, IEA gap %, budget years, annual reduction rates, data quality, scope status
- `_map_greenwashing` → overall_score, greenwishing, greenhushing, selective_disclosure, temporal_escalation, carbon_tunnel_vision, linguistic_risk, GSI, boilerplate %, ClimateBERT relevance/risk
- `_map_contradictions` → severity, claim_text, evidence_text, source, year, impact
- `_map_evidence` → source_name, credibility, stance (SUPPORTING/CONTRADICTING/NEUTRAL), excerpt, archive_verified
- `_map_regulatory` → framework, compliance_score, status, jurisdiction, key_gap
- `_map_risk_drivers` → name, impact, direction (increases_risk/reduces_risk), shap_value (merges real SHAP drivers + inferred fallbacks)

Then `apply_final_validation()` (see §11.4) applies a non-destructive post-process pass and returns the final `ESGReport`.

Newer fields populated by mappers: `quality_warnings`, `model_versions`, `calibration`, `kg_drift`, `fact_graph_motifs`, `retriever_tally`.

### 11.3 PDF — `api/pdf_generator.py` + `api/pdf_styles.py`

**Library**: ReportLab (`platypus` + `charts`). Output is a `BytesIO` buffer, returned as `application/pdf` from `GET /api/reports/{id}/pdf`.

**Structure** (mirrors TXT — lines 137–435 of `build_pdf()`):

1. **Cover page** — title, company, ticker, industry, report ID, confidence, claim
2. **Verdict section** — 5-badge grid (GW Risk Score, ESG Score, Rating, Risk Band, Confidence) with colour coding
3. **Section 3** — Executive summary + top-5 key findings
4. **Section 3B** — Claim breakdown bullets
5. **Section 4** — Evidence citations table (max 15 rows: #, Source, Type, Verified, Role)
6. **Section 5** — Pillar bar chart (`HorizontalBarChart`, teal bars on white/light-grey alternating rows) + per-pillar factor tables
7. **Section 6** — Numbered key risk drivers
8. **Section 7** — Two tables: contradictions + regulatory
9. **Section 8** — Scopes table + KV pairs (data quality, net-zero target, scope status)
10. **Section 8B** — Carbon pathway KV pairs (alignment, required rate, company rate, gap, budget years, scope-3 share)
11. **Section 9** — Deception pattern table + ClimateBERT stats
12. **Section 10** — Calibration & confidence KV pairs
13. **Section 11** — Limitations bullet list
14. **Section 11B** — Commitment timeline (from commitment ledger)
15. **Section 12** — ESG Mismatch Detector summary
16. **Appendices A, B, C** — KV tables
17. **Footer** — "END OF REPORT" + report ID + date + "ESGLens v4.0"

**Page template**:
- Header (per page): company name (left), report title + ID (right), teal accent bar
- Footer (per page): "CONFIDENTIAL | ESGLens v4.0 | <date>" (left), page number (right)
- Page breaks before appendices
- Continuous flow within sections (recent change — was previously page-broken per section)

### 11.4 Validation layer — `api/validation_layer.py`

`apply_final_validation(report: ESGReport, raw: Dict) → ESGReport` performs **non-destructive** integrity checks. It only appends to `report.validation_notes`; it never silently suppresses findings.

Checks applied:

1. **Carbon scope status** — sets `scope2_status` to FULL / PARTIAL / DISCLOSED based on "market-based", "location-based", "purchased electricity" in evidence. Sets `scope3_status` based on "financed emissions", sector keywords, "total scope 3" claims. Sanity-warns if scope3 > 100× (scope1 + scope2) without an explicit total claim.
2. **Target claim status** — for quantitative claims, checks temporal_risk and claim_trend → sets `carbon.target_status` to OFF_TRACK / ABANDONED / VERIFIED.
3. **Contradiction correction** — flags off-track / abandoned targets and optionally appends a high-confidence (≥0.8) `Contradiction` record.
4. **Evidence quality safeguard** — if >80% of evidence is news/web/blog tier, reduces confidence by 5%.
5. **Abstention control** — for quantitative claims with evidence, prevents `unknown` target_status.

---

## 12. FastAPI Server & WebSocket Streaming

### 12.1 Server

**File**: `server.py`
- FastAPI app `ESGLens API v1.0.0`
- CORS allow list: `localhost:3000`, `:3001` (esglens dev), `:8080`, plus 127.0.0.1 variants
- Mounts `api_router` from `api/router.py`
- Health check: `GET /health` → `{"status": "ok", "service": "ESGLens API", "version": "1.0.0"}`
- Dev runner: `uvicorn server:app --host 0.0.0.0 --port 8000 --reload`

### 12.2 Routes

**Analysis**

| Route | Verb | Request | Response | Backend |
|---|---|---|---|---|
| `/api/analyse` | POST | `AnalysisRequest` (company, claim, industry, uploaded_file_ids) | `{analysis_id, status: "started"}` | Spawns subprocess thread, registers in `_analysis_store` |
| `/api/analysis/{analysis_id}` | GET | — | `{analysis_id, status, progress, company, result, error}` | Polls in-memory store |

**Reports**

| Route | Verb | Request | Response | Backend |
|---|---|---|---|---|
| `/api/reports` | GET | — | `List[HistoryEntry]` | Scans `reports/*.json` (excluding `lineage`/`FULL`/`research_runs`), maps to summaries |
| `/api/reports/{report_id}` | GET | — | `ESGReport` | `map_report_to_schema()` + `apply_final_validation()` |
| `/api/reports/{report_id}/pdf` | GET | — | PDF bytes (`application/pdf`, attachment) | `pdf_generator.build_pdf()` |

**Upload**

| Route | Verb | Request | Response |
|---|---|---|---|
| `/api/upload` | POST | multipart `file: UploadFile` (`.pdf .txt .docx .csv`, ≤50 MB) | `{file_id, filename, size_bytes, ext, status, path}` |

**WebSocket**

| Route | Protocol | Notes |
|---|---|---|
| `/ws/pipeline/{analysis_id}` | WebSocket | See §12.3 |

**Chatbot** (proxied to `chatbot_backend/` — see §13)

| Route | Verb | Request | Response |
|---|---|---|---|
| `/chatbot/health` | GET | — | `{"status": "ok", "service": "ESG Analyst Copilot"}` |
| `/chatbot/chat` | POST | `ChatRequest` (session_id, question, provider) | `ChatResponse` (status, session_id, answer, provider_used) |
| `/chatbot/chat/stream` | POST | `StreamChatRequest` | SSE stream with `meta` / `message` / `done` events |
| `/chatbot/run-analysis` | POST | `AnalysisRunRequest` (legacy) | `ReportResponse` |
| `/chatbot/report` | GET | `?company=` (optional) | `ReportResponse` |

**Auth**: none — there is no authentication or API-key validation gate on any of the above. (The legacy frontend has a file-backed user store but it's purely client-side cosmetic.)

### 12.3 Pipeline-WS streaming — `api/pipeline_ws.py`

Pattern: spawn-and-stream.

1. `POST /api/analyse` generates `analysis_id = uuid.uuid4()` and registers an entry in `_analysis_store[analysis_id]` with status="running".
2. A background thread runs `_run_pipeline_subprocess(analysis_id, ...)` (lines 106–228), which executes:
   ```
   venv/bin/python main_langgraph.py --company X --claim Y [--industry Z]
   ```
   — line-buffered, stderr merged into stdout. Each line is parsed and pushed into `_analysis_store[analysis_id]["logs"]` with `(timestamp, message, kind)` where `kind` ∈ {`ok`, `warn`, `error`, `info`}.
3. The browser opens `WebSocket /ws/pipeline/{analysis_id}`. The handler:
   - Waits up to 10s for the store entry to materialise.
   - Loops every 500 ms:
     - Sends new log lines: `{"type":"log","t":"3.2s","msg":"...","kind":"ok"}`
     - Sends progress: `{"type":"progress","progress_pct":...,"elapsed_seconds":...}`
     - On status="completed": `{"type":"complete","analysis_id":"...","report":{...}}`
     - On status="error": `{"type":"error","message":"..."}`
     - Every 5s: `{"type":"heartbeat","elapsed_seconds":...}`

Report ID is derived post-completion via `_short_id(json_filename)` — the filename stem if >6 chars, else MD5 hash first 12.

---

## 13. Chatbot Backend (ESG Analyst Copilot)

The chatbot is a Q&A service over generated reports. **It never runs a fresh pipeline analysis**; it answers questions about already-cached reports.

### 13.1 Architecture

```
HTTP /chatbot/chat
        │
        ▼
ESGChatService.answer(session_id, question, provider)
        │
        ├── 1. is_esg_scope(question)       ← scope guardrail
        ├── 2. get_esg_context(reports_dir) ← load latest report JSON
        ├── 3. detect_intents(question)     ← classify into 8 intents
        ├── 4. section regex match          ← if "section 7", extract directly
        ├── 5. select_relevant_context()    ← minimise context
        ├── 6. build_user_prompt()          ← inject context into template
        ├── 7. LLMOrchestrator.query()      ← Gemini → Groq fallback
        ├── 8. parse_llm_json()             ← extract answer + metadata
        └── 9. memory_store.append()        ← session-aware conversation
```

### 13.2 Intent taxonomy (`intent_router.py`)

8 intents — `SCORE`, `SCORE_EXPLANATION`, `EVIDENCE`, `CONTRADICTION`, `REGULATORY`, `CARBON`, `AGENT`, `SUMMARY`. Detection is keyword-based ("why is score" → SCORE_EXPLANATION).

For each intent, `select_relevant_context()` returns only the report fields needed:

| Intent | Selected fields |
|---|---|
| `SCORE_EXPLANATION` | `score`, `contradictions`, `regulatory_gaps`, sections tagged "driver"/"score" |
| `EVIDENCE` | `evidence` (top 10), `verdict` |
| `CONTRADICTION` | `contradictions`, agent insights on mismatch/greenwishing |
| `REGULATORY` | `regulatory_gaps`, compliance risk, agent insights on regulation |
| `CARBON` | `carbon_data`, pathway-related agent insights |
| `AGENT` | all `agent_insights` (greenwashing engines, adversarial audit) |
| `SUMMARY` | `score`, `verdict`, top 5 contradictions, top 5 regulatory gaps |

### 13.3 LLM (`chatbot_backend/llm.py`)

- **Primary**: Google Gemini (`google.generativeai`) — system instruction + user prompt → text
- **Fallback**: Groq (OpenAI-compatible at `https://api.groq.com/openai/v1`) — uses the `openai` client
- Graceful degradation: missing key → skip; both missing → raise

### 13.4 Memory (`chatbot_backend/memory.py`)

- `SessionMemoryStore` — in-memory dict per `session_id`
- `ChatTurn` schema: `role, content, timestamp`
- TTL 6 hours, max 10 turns (configurable via `max_chat_history`), oldest dropped when exceeded
- Lock-protected for thread safety

### 13.5 Mounting via `api/chatbot.py`

Initialised at import time:
```python
_settings = load_settings()
_memory_store = SessionMemoryStore(max_turns=_settings.max_chat_history)
_service = ESGChatService(settings=_settings, memory_store=_memory_store)
```

Routes are then registered under the `/chatbot` prefix (see §12.2).

---

## 14. ML Models

The `ml_models/` package contains 9 model wrappers + trained artifacts (~2.2 MB total in `ml_models/trained/`).

### 14.1 `xgboost_risk_model.py` — risk classifier

- **Library**: XGBoost
- **Output classes**: `HIGH` / `MODERATE` / `LOW`
- **Input**: 27-field dict — ESG scores, financial metrics (revenue, profit margin, debt/equity), carbon/water/energy efficiency, pillar scores, industry encoding, disclosure counts, internal contradiction / pathway gap scores
- **Inference**: returns `prediction`, `confidence` (probability), `probabilities` (per-class), `features_used`
- **Integration**: invoked from main pipeline; output → `state.ml_prediction` → consumed by RiskScorer

### 14.2 `lightgbm_esg_predictor.py`

- **Library**: LightGBM
- **Inputs (7)**: `environmentScore`, `socialScore`, `governanceScore`, `highestControversy`, `marketCap` (log-transformed), `beta`, `overallRisk`
- **Output**: `predicted_esg`, `confidence_r2 = 0.92`, `expected_error` (MAE), `prediction_range` (95% CI ±2×RMSE)
- **Validator**: `validate_esg_claim()` — flags claimed vs predicted gap >10 → "Moderate concern", >20 → "High concern"
- **Artifacts**: `lightgbm_esg_score_model.pkl` (178 KB) + feature names + metadata

### 14.3 `lstm_trend_predictor.py`

- **Library**: TensorFlow / Keras (LSTM)
- **Input**: last 6 years of ESG scores
- **Output**: 6-year forecast, `trend` ∈ {IMPROVING, STABLE, DECLINING}, `change_pct`, `confidence_mae` (~±5.0)
- **Trend rule**: if `avg(first_2_years) → avg(last_2_years)` increase >5% → IMPROVING
- **Artifacts**: `lstm_trend_forecaster.h5` (384 KB) + 2 scalers (joblib, TF 2.15+ compatible)

### 14.4 `anomaly_detector.py`

- **Library**: scikit-learn (Isolation Forest)
- **Features (8)**: `carbon_intensity`, `water_intensity`, `energy_intensity`, `esg_revenue_gap`, `growth_esg_correlation`, `profit_esg_ratio`, `environmental_balance`, `volatility_score`
- **Output**: `is_anomaly` (bool), `anomaly_score`, `confidence`, `severity` ∈ {Low, Moderate, High}, `anomalous_features` (z-scored outliers)

### 14.5 `climatebert_analyzer.py`

- **Library**: transformers + torch (lazy-loaded, GPU-aware)
- **Models** (4 from HuggingFace):
  - `climatebert/distilroberta-base-climate-detector` — climate relevance
  - `climatebert/environmental-claims` — claim detection
  - `climatebert/distilroberta-base-climate-f` — TCFD classification
  - `nlptown/bert-base-multilingual-uncased-sentiment` — sentiment
- **Output**: climate relevance (0–100), claim classification, greenwashing risk (pattern-based fallback), assessment credibility, recommendations
- **Greenwashing patterns**: vague ("sustainable"), unsubstantiated ("net zero"), hedge words ("aim to"), temporal vagueness ("by 2050")

### 14.6 `explainability_engine.py`

- **SHAP**: TreeExplainer on XGBoost/LightGBM
- **LIME**: model-agnostic local explanations
- **Output**:
  - SHAP — `top_factors` (5), `base_value`, `human_readable_explanation`, summary stats
  - LIME — `contributions`, `local_prediction`
  - Report-ready — `key_factors` with `impact` ∈ {very_high, high, moderate, low}, `direction` ∈ {increases risk, decreases risk}, narrative
- **Feature catalog**: 80+ human-friendly labels (e.g., "Carbon intensity per revenue", "Controversy level")

### 14.7 `score_calibrator.py`

Logistic recalibration of the rule-based score (see §7.8). Spearman correlation, point-biserial r, Mann-Whitney U, ROC-derived optimal threshold.

### 14.8 `sentiment_esg_predictor.py`

- **Inputs**: `news_sentiment` (-1..1), `sentiment_volume` (1..100), `controversy_level` (0..5), `current_esg_score`, `industry_volatility`
- **Engineered**: `sentiment_intensity` = sentiment × volume; `controversy_sentiment` = level × sentiment; `recovery_potential` = current_esg × sentiment
- **Output**: `predicted_change` (-30..+30 pts over 6 months), CI, `direction` {POSITIVE, NEGATIVE, NEUTRAL}, `magnitude` {MAJOR, MODERATE, MINOR}
- Amplifies impact when controversy_level ≥ 3

### 14.9 `model_evaluator.py`

CV harness for evaluating Dummy / LogReg / XGBoost / LightGBM on the ground-truth dataset:
- TF-IDF (300 features from claim text)
- Linguistic (8 features: vague_score, quantification_score, verification_score, hedge_score, action_vs_aspiration_ratio, length, has_year, has_scope)
- Sector (one-hot)
- 5-fold stratified CV + 20% holdout
- Metrics: accuracy, F1 (weighted & macro), AUC-ROC, precision, recall, balanced accuracy
- Outputs: `reports/ml_evaluation_results.json`, confusion matrices, ROC curve, feature importance plots

### 14.10 Trained artifacts (`ml_models/trained/`)

```
anomaly_detector.pkl (1.3 MB) + anomaly_scaler.pkl + anomaly_features.pkl + anomaly_metadata.json
lightgbm_esg_score_model.pkl (178 KB) + feature names + metadata
lstm_trend_forecaster.h5 (384 KB) + 2 scalers + lstm_metadata.json
xgboost_risk_model.pkl (349 KB)
sentiment_esg_model.pkl (1.1 KB) + features + sentiment_model_metadata.json
Industry clustering: cluster_mapping.pkl + scaler + features
```

---

## 15. ESG Mismatch Detector (Standalone Feature)

The mismatch detector is a **separate pipeline** from the LangGraph workflow. It does company-level promise-vs-reality auditing and caches results for 24 hours.

**Entry**: `python -m features.esg_mismatch_detector.pipeline "<company>"`
**Cache**: `cache/esg_analysis/<company>.json` (24h TTL, schema-version-checked, falls back to cached on live failure)

### 15.1 Pipeline stages

1. **`company_resolver.py`** — normalise name (CamelCase → spaces, strip `Inc.` / `Corp`), generate aliases (e.g., BP → BP, bp, "british petroleum"), detect industry, return `{company, aliases, search_terms, industry, high_signal_company}`
2. **`report_collector.py`** — fetch latest sustainability/ESG report
3. **`promise_extractor.py`** — extract pledges from report text (NLP); if none found, falls back to external public statements. Each promise carries `metric, target, unit, deadline, baseline, scope, measures_taking`
4. **`evidence_collector.py`** — fetch external evidence (news, SEC, EPA, regulatory DBs, research). Tags regulatory violations. Confidence 1–5 (5 = government/regulatory)
5. **`comparison_engine.py`** — match promises to evidence by metric alias (e.g., `carbon_emissions` ← `co2`, `ghg`, `scope 1`):
   - **Completed promises** (deadline ≤ current year): compute `gap = target − actual`; flag `Missed Target`; severity Low/Moderate/High/Severe
   - **Future promises** (deadline > current year): monitor trend; flag `Negative Trend` if worsening
   - **Regulatory violations**: elevate to Severe regardless
6. **`mismatch_detector.py`** — aggregate to overall risk: High / Moderate / Low / Inconclusive

### 15.2 Output schema

```json
{
  "Company Analyzed": "...",
  "Report Availability": "Available|Unavailable",
  "Overall Greenwashing Risk": "High|Moderate|Low|Inconclusive",
  "Executive Summary": "...",
  "Data Coverage": {
    "Total Sources Retrieved": int,
    "Sources Used In Final Reasoning": int,
    "Coverage Score": "HIGH|MEDIUM|LOW",
    "Evidence Threshold": int
  },
  "Confidence Score": "High|Medium|Low",
  "1. Future Commitments & Progress": [
    {
      "Pledge": "...",
      "Status Trend": "In Progress|Monitoring|Insufficient Evidence",
      "Progress/Trend": "...",
      "Measures Being Taken": "...",
      "Source of Measure": "Official ESG Report|..."
    }
  ],
  "2. Past Promise-Implementation Gaps": [
    {
      "Failed Pledge": "metric",
      "Expected Target": "value unit",
      "Flagged Status": "MISSED_TARGET: actual_value",
      "Risk Level": "Low|Moderate|High|Severe",
      "Confidence Score": "High|Medium|Low",
      "Evidence Source": "...",
      "Verified Quote": "..."
    }
  ]
}
```

### 15.3 How it differs from the in-pipeline contradiction analyzer

| Aspect | Main pipeline `ContradictionAnalyzer` | Mismatch Detector |
|---|---|---|
| Scope | One claim at a time | Whole company's pledge portfolio |
| Orchestration | LangGraph node | Standalone CLI / API |
| Caching | LLM cache only | Full result cache 24h |
| Data sources | Whatever `EvidenceRetriever` returns | Independent fetch + regulatory tagging |
| Use case | Score one claim | Company-wide audit / longitudinal monitoring |

---

## 16. Frontends

There are **two frontend trees** in the repo. The active one is `esglens/`.

### 16.1 `esglens/` — ACTIVE (Vite + React 18 + TypeScript)

**Stack**:
- Vite 5.4 + React SWC + React 18.3 + TypeScript 5.8
- React Router DOM 6.30
- **State**: Zustand 5
- **Server state**: TanStack React Query 5
- **UI**: Radix UI + shadcn/ui (`components.json` confirms)
- **Charts**: Recharts 2.12
- **3D**: Three.js + @react-three/fiber + drei (the dashboard globe)
- **Forms**: React Hook Form + Zod
- **Animation**: Framer Motion + Embla Carousel
- **Misc**: D3, Lucide icons, jsPDF, Sonner

**Scripts**:
```
dev          → vite --port 3001
build        → vite build
build:dev    → vite build --mode development
test / test:watch → vitest
```

**Routes** (`esglens/src/App.tsx`):

| Path | Page | Purpose |
|---|---|---|
| `/` | `Dashboard.tsx` | Landing — 3D globe, recent analyses, typewriter search, perf counters |
| `/analyse` | `NewAnalysis.tsx` | Submit company / claim / industry / focus areas / file upload |
| `/pipeline` | `LivePipeline.tsx` | Real-time pipeline logs + progress bar (WebSocket) |
| `/report` | `Report.tsx` | Full ESG report (pillars, carbon, greenwashing, contradictions, evidence, regulatory) |
| `/history` | `History.tsx` | Past analyses (tabular) |
| `/chat` | `Chatbot.tsx` | AI Q&A on the active report |
| `/reports` | `ReportsLibrary.tsx` | Searchable report library |
| `*` | `NotFound.tsx` | Fallback |

**Stores**:
- `analysisStore` — current analysis lifecycle (`startAnalysis`, `connectToStream`, `loadReport`, `clearCurrent`); holds `currentAnalysisId`, `currentReport`, `isRunning`, `progress`, `elapsedSeconds`, `logs[]`, `wsRef`
- `chatStore` — chatbot conversational state (`sendMessage`, `setContext`, `clearChat`); holds `messages[]`, `isTyping`, `sessionId`, `activeCompany`, `activeAnalysisId`
- `historyStore` — lighter weight history

**API client** (`esglens/src/lib/api.ts`):
- Base URL `/api` (Vite proxies to `http://localhost:8000/api`)
- Chatbot URL `/chatbot` (proxied to `:8000/chatbot`)
- WebSocket `ws://localhost:8000` (or env `VITE_WS_URL`)

Endpoints called: `POST /api/analyse`, `GET /api/analysis/{id}`, `GET /api/reports`, `GET /api/reports/{id}`, `POST /api/upload`, `WS /ws/pipeline/{id}`, `POST /chatbot/chat`, `POST /chatbot/chat/stream`.

**TypeScript types** mirror the Pydantic schemas: `ESGReport`, `LogEntry`, `PillarScore`, carbon data, greenwashing data, contradictions, evidence, regulatory.

### 16.2 `frontend/` — LEGACY (Next.js 16)

- Next.js 16.2.4 (App Router) + React 19.2 + Tailwind CSS 4
- Recharts 3.8, pdf-lib, react-markdown, Radix UI primitives
- File-backed user store at `frontend/src/data.json`:
```json
{"users":[{"id":"1","name":"Jane Doe","email":"jane@example.com","password":"password123","role":"user"}, ...]}
```
- Routes: `/`, `/login`, `/signup`, `/dashboard`, `/api/*`
- API client (`lib/esg-chat-api.ts`) hits the same backend on port 8000

**Verdict**: deprecated. Recent commits target `esglens/`. The `frontend/` tree is mostly auth scaffolding and demo widgets; for any new product work use `esglens/`. (The legacy frontend was the subject of the older `PROJECT_DOCUMENTATION.md`, which is why that doc references `/dashboard/analyze` and `/dashboard/mismatch` routes that no longer match the active UI.)

---

## 17. Configuration, Tests, Environment

### 17.1 `config/settings.py`

Pydantic settings loaded from `.env`. Key sections:

- **API keys** — Groq, Gemini, OpenRouter, NewsAPI, NewsData, SEC, ClimateBERT toggle
- **Models (Oct 2025 update)**: `GROQ_MODEL=llama-3.3-70b-versatile`, `GROQ_FAST_MODEL=llama-3.1-8b-instant`, `GEMINI_MODEL=gemini-2.5-flash`
- **ChromaDB**: `CHROMA_PERSIST_DIR=./data/chroma_db`, collection `esg_evidence`
- **Scoring weights** (overridden by industry profiles): claim verification 0.25, evidence quality 0.20, source credibility 0.20, sentiment divergence 0.15, historical 0.10, contradiction severity 0.10
- **India settings**: `DEFAULT_JURISDICTION=India`, `SEBI_BRSR_ENABLED`, `MCA_COMPLIANCE_ENABLED`, `CPCB_MONITORING_ENABLED`, `INDIA_GRID_EMISSION_FACTOR=0.71` (CEA 2025)
- **Carbon**: `CARBON_SCOPES_ENABLED=[scope1, scope2, scope3]`, `GHG_PROTOCOL_VERSION=2024`, `CDP_INTEGRATION_ENABLED`, `SBTI_VALIDATION_ENABLED`
- **Regulatory frameworks monitored** (16): SEBI_BRSR, MCA_COMPANIES_ACT, CPCB_EPA, RBI_GREEN_FINANCE, INDIA_BEE_PAT, GHG_PROTOCOL, SBTI, GRI_STANDARDS, CDP, EU_CSRD, EU_TAXONOMY, SEC_CLIMATE, UK_FCA_ANTIGREENWASHING, …
- **Explainability**: `SHAP_ENABLED`, `LIME_ENABLED`, `EXPLAINABILITY_TOP_FEATURES=5`

### 17.2 `config/agent_prompts.py`

Houses the master ESG analyst system prompt. Defines:

- **Pillar mandate** — E (Scope 1/2/3, CDP, TCFD, net-zero credibility, renewable %, ClimateBERT), S (ILO NORMLEX, UN Global Compact, Modern Slavery Act, supply-chain risk, diversity, employee sentiment, community impact), G (board composition, director interlocks, CEO/worker pay ratio, ESG pay linkage, audit quality, regulatory actions, shareholder rights, tax transparency, whistleblower hotline)
- **Evidence hierarchy** — Tier 1: regulatory filings + government DBs + academic/NGO audits; Tier 2: verified third-party certifications; Tier 3: company sustainability reports (cross-checked); Tier 4: news + analyst reports (signal only)
- **Contradiction rules** — E score > 70 + S score < 40 = SELECTIVE_DISCLOSURE; pillar with 0 evidence = EVIDENCE_VACUUM; target year shifted twice = HIGH_RISK; aspirational language without roadmap = GREENWISHING; unverified third-party = GREENWASHING

### 17.3 Other config files

| File | Purpose |
|---|---|
| `config/company_aliases.json` | Ticker / aliases / full-name lookups (BP → BP.L + "British Petroleum", …) |
| `config/data_sources.json` | Per-source rate limits + cache hours + priority (news_api: 100/d, newsdata_io: 200/d, reuters_sustainability: 60/d, sec_edgar: 10/d cache 24h, epa_enforcement, osha_violations, gdelt: 10/d cache 6h, courtlistener, opensanctions, worldbank: 10/d cache 720h, …) |
| `config/industry_baselines.json` | Per-sector baseline scores + greenwashing-sensitive language patterns. Examples: Oil & Gas (baseline_risk=75, baseline_esg=45, env=35, social=48, gov=52), Coal (80/38/28/42/45), Mining/Auto/Consumer/Tech/Finance |
| `config/materiality_map.json` | SASB-style E/S/G weights per sector. Examples: General `{E:0.35, S:0.30, G:0.35}`, Oil & Gas `{E:0.48, S:0.20, G:0.32}`, Coal `{E:0.52, S:0.18, G:0.30}`, Mining `{E:0.44, S:0.26, G:0.30}` |

### 17.4 LLM routing — `core/llm_router.py`

Each agent has a primary + fallback chain:

| Agent | Primary | Fallback chain |
|---|---|---|
| supervisor | Groq llama-3.3-70b (T=0.0, 100 tok) | OpenRouter reasoning → Gemini |
| carbon_extraction | Gemini 2.0-flash (JSON, 1000 tok) | Groq llama-3.3 → OpenRouter Mistral |
| claim_extraction | Cerebras llama3.1-8b (JSON, 4096) | Groq → OpenRouter |
| risk_scoring | Groq llama-3.3-70b (JSON, T=0.0, 2000 tok) | OpenRouter → Gemini |
| report_generation | Gemini 2.5-pro-preview (4000 tok) | OpenRouter 2.5-pro → Gemini 2.0-flash |
| credibility_analysis | Cerebras llama3.1-8b (JSON, 200 tok) — **fastest, called ~47×/report** | — |
| sentiment_analysis | Groq llama-4-scout-17b-16e (500 tok) | — |
| temporal_consistency | Groq qwen/qwen3-32b (JSON, 600 tok) | — |
| esg_mismatch | Groq llama-3.3-70b (JSON, 1500) | Cerebras qwen-3-235b → OpenRouter llama-3.3 |

`NO_LLM_AGENTS = {report_discovery, report_downloader, report_parser, evidence_retrieval, realtime_monitoring}` — these are pure Python/IO; the router raises if an LLM call is attempted.

### 17.5 Tests

| File | Validates |
|---|---|
| `tests/test_gw_esg_independence.py` | GW and ESG performance are NOT mathematical inverses (5 synthetic scenarios) |
| `tests/test_sg_pipeline.py` | S&G evidence pack builds tracks + adequacy gates; fact graph includes normalised S/G summary |
| `test_camelot.py` (root) | Camelot-py table extraction from sample sustainability PDFs (Shell, Apple, Microsoft) |
| `test_fixes.py` | Industry normalisation + RiskScorer key validation |
| `test_regulatory.py` | Regulatory infill (WBA, SEC) + Memento historical claim verification |
| `validate_improvements.py` | Smoke test of the full pipeline + ML stack |

`pytest.ini` — root `tests/`, excludes `cache`, `venv`, `.git`, `__pycache__`, `reports`, `node_modules`.

### 17.6 Environment variables (`.env`)

Names only — values are private. Every variable consumed by the system:

**LLM providers**
- `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `CEREBRAS_API_KEY`

**News & data**
- `NEWSAPI_KEY` / `NEWS_API_KEY`, `NEWSDATA_KEY` / `NEWSDATA_API_KEY`, `THENEWSAPI_KEY`, `MEDIASTACK_KEY`
- `SEC_API_KEY` (sec-api.io), `ALPHAVANTAGE_KEY`, `FINNHUB_KEY`, `FMP_API_KEY`
- `WBA_API_KEY` (World Benchmarking Alliance), `RESOURCE_WATCH_API_KEY` + `RESOURCE_WATCH_TOKEN` (WRI)

**Paths**
- `MATERIALITY_PROFILE_PATH=config/materiality_map.json`, `MATERIALITY_PROFILE_URL` (optional remote overlay)

**Neo4j (KG)**
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`

**Feature flags**
- `KG_ENABLED=true`
- `KG_USE_LLM_GRAPH_TRANSFORMER=false`
- `USE_LANGGRAPH=true`
- `TF_ENABLE_ONEDNN_OPTS=0`, `TF_CPP_MIN_LOG_LEVEL=2`

**Pipeline behaviour**
- `ESG_WORKFLOW_TIMEOUT=1800` (sec)
- `ESG_ALLOW_PARTIAL_ON_TIMEOUT=1`
- `ESG_SAVE_FULL_RESULTS=0`
- `ESG_FORCE_EXIT=1`

**Optional (per IMPROVEMENTS_SUMMARY.md)**
- `USE_ENHANCED_DATA_SOURCES=true`, `ENHANCED_DATA_TIMEOUT=15`, `ENHANCED_DATA_CACHE_HOURS=24`, `COMPANY_JURISDICTION=global`

### 17.7 Top-level housekeeping

- `logs_shell.txt` (~77 KB) — accumulated stdout/stderr from prior runs; useful for failed-pipeline diagnosis (do not commit; gitignored).
- `scripts/` — `train_anomaly_detector.py`, `check_orsted_report.py`, `run_sector_benchmark.py`, `summarize_research_runs.py`, `verify_company_kg.py`, `refresh_materiality_profiles.py`, `append_ground_truth_cases.py`, `debug_fetch_full_text.py`, `replay_report.py`, `view_fact_graph.py`
- `scratch/` — one-off patches: `fix_fstring.py`, `patch_carbon_section.py`, `patch_fetcher.py`, `patch_risk_scorer.py`, `patch_section9.py`, `patch_final_fixes.py`, `patch_report_gen.py`, `update_contradiction.py`, `update_reasons.py`, `update_scorer.py`, `test_claim_intensity.py`, `verify_sec_integration.py`, `patch_end_sections.py`

---

## 18. Operational Runbook

### 18.1 First-time setup

```bash
# Clone, then in repo root:
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy .env.example to .env and fill in API keys
cp .env.example .env
# At minimum, set: GROQ_API_KEY (or GEMINI_API_KEY), NEO4J_PASSWORD
# (Neo4j is optional — JSON fallback works without it)
```

### 18.2 Run the backend pipeline

```bash
# Direct CLI
python main_langgraph.py --company "JPMorgan Chase" \
                        --claim "net-zero emissions by 2050" \
                        --industry "Banking"

# Watch the live retriever tally
tail -f /tmp/jpm_*.log | grep -E "AGENT|tally|retriever"
```

Outputs:
- `reports/ESG_Report_<co>_<ts>.txt`
- `reports/ESG_Report_<co>_<ts>.json`
- `reports/company_kg/<co>_company_kg_payload.json`
- `reports/fact_graphs/<co>_<ts>_fact_graph.json`
- (if enabled) `reports/ESG_Report_<co>_<ts>_FULL.json` + `reports/debug_esg_lineage_<co>.json`

### 18.3 Run the API server

```bash
# Foreground
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Health check
curl http://localhost:8000/health
```

### 18.4 Run the active frontend

```bash
cd esglens
npm install
npm run dev          # http://localhost:3001 (proxies API to :8000)
```

### 18.5 Run the mismatch detector

```bash
python -m features.esg_mismatch_detector.pipeline "BP"
# Result cached at cache/esg_analysis/bp.json (24h TTL)
```

### 18.6 Cache management

| Want to … | Do this |
|---|---|
| Force a fresh evidence retrieval | `rm cache/evidence/<company_lower>_*.json` |
| Force a fresh LLM response for one agent | `rm -rf cache/llm_responses/<agent>/` |
| Clear all caches | `rm -rf cache/` (kept files: `cache/camelot_temp/` is auto-recreated) |
| Reset the commitment ledger | `rm data/commitment_ledger.db` |
| Reset the company KG payload | `rm reports/company_kg/<company>_company_kg_payload.json` |

⚠️ **Per project memory**: when iterating on analysis/report code, only purge generated reports/analysis — keep cached evidence so you don't burn API keys. Use targeted deletion, not `rm -rf cache/`.

### 18.7 Common issues

| Symptom | Cause / fix |
|---|---|
| Pipeline hangs >5 min | Check `WORKFLOW_TIMEOUT` (default 1800s); a slow retriever is usually to blame — inspect the retriever tally in stdout |
| All scores `[SUPPRESSED]` | Outdated code — already fixed; pull latest |
| `ILO API returned 403` warning | ILO rate-limits aggressively; safe to ignore |
| `NewsAPI returned 0 items (silent miss)` | `NEWS_API_KEY` invalid/missing |
| KG payload empty | Neo4j down; check `reports/company_kg/<co>_payload.json` for the JSON-fallback dump |
| PDF generation 500 error | Most often: report JSON is missing required fields. Re-run the analysis or check `api/pdf_generator.py:build_pdf` for the failing section |
| Frontend WS disconnects | Backend not running on `:8000`, or analysis_id never registered (subprocess crashed at startup) |

---

## 19. Known Bugs & Future Work

### 19.1 Active bugs

1. **Substring-match company-name filter in `EvidenceRetriever`** — `_filter_relevant_evidence()` uses `company_lower in combined_text`. This drops valid items whose text contains common-word company names. Observed in JPMorgan Chase run: ~15 valid items rejected because `"net zero target"` matched company "Target", `"JP Morgan"` was scanned for `"GM"`, etc.
   - **Fix**: replace with word-boundary regex `re.search(r'\b' + re.escape(company_lower) + r'\b', text)` or proper tokenisation. Keep a whitelist of multi-word company names that should be matched as phrases.

2. **6 silent retrievers** in current JPM run: `newsapi`, `newsdata`, `reuters_rss`, `cdp`, `sbti`, `google_scholar`.
   - NewsAPI / NewsData → check `NEWS_API_KEY` / `NEWSDATA_KEY` validity
   - Reuters RSS → company name not present in feed titles in last 24h (filter requires exact match) — consider relaxing to alias set
   - CDP / SBTi → HTML structure changed; both BeautifulSoup parsers need refresh
   - Google Scholar → Semantic Scholar API timeout; add retry + per-call timeout reduction

3. **`save_peer_to_database_node` is a no-op** — `IndustryComparator` is deprecated at the call site, so peer-database updates aren't happening. The class still works in isolation; needs re-wiring or removal from the graph.

4. **`PROJECT_DOCUMENTATION.md` is stale** — references `/dashboard/analyze` and `/dashboard/mismatch` routes that belong to the legacy `frontend/` tree, not the active `esglens/`. Either update or mark as legacy-only.

5. **Realtime monitoring polling daemon not wired** — `RealtimeMonitor` agent runs once per analysis but the periodic polling loop described in the README isn't scheduled.

### 19.2 Completed fixes (per `IMPROVEMENTS_SUMMARY.md`)

- Risk-score suppression removed (now always shown with calibration tier)
- HTML entities (`&quot;`, `&amp;`) decoded in contradiction snippets
- IndustryComparator hardened with try/except + structured fallback
- Enhanced government data sources added: ILO, UN GC, OECD, EU Taxonomy, UNFCCC, Open Apparel Registry, OpenSanctions
- PDF generator rewritten to mirror TXT (12 sections + 3 appendices); added pillar bar chart; white background; continuous flow

### 19.3 Future work backlog

- **Fix** the substring-match company filter (#1 above) — single highest-leverage fix
- **Refresh** the CDP and SBTi HTML parsers
- **Wire** `USE_ENHANCED_DATA_SOURCES=true` into `EvidenceRetriever` so the ILO/UN/OECD modules actually contribute
- **Implement** the SEBI BRSR / MCA / CPCB / NGT stubs in `utils/indian_data_sources.py`
- **Replace** plain-text password storage in legacy `frontend/src/data.json` (or formally retire that frontend)
- **Add** server-side auth gating to all `/api/*` routes
- **Build** a CI test that asserts every retriever returns ≥1 item for a known-good fixture (Microsoft + Apple)
- **Integrate** OECD Watch full scraping (currently keyword-based)
- **Add** CNINFO (China A-shares) and EDINET (Japan) sources
- **Real-time** sanctions screening webhooks
- **Schedule** the RealtimeMonitor polling loop and connect it to a re-analysis trigger

---

*End of guide. For day-to-day operational tweaks, edit this file alongside the change. For marketing/architecture overview, see `README.md`. For older product flow narrative (slightly stale on frontend), see `PROJECT_DOCUMENTATION.md`. For change-log of recent fixes, see `IMPROVEMENTS_SUMMARY.md`.*


