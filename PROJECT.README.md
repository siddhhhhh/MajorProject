# ESG Greenwashing Detection System - Master Project README

This document is the complete, up-to-date reference for this project: what it does, which features are implemented, and what each major folder/file contains.

## 1) Project Purpose

The system analyzes ESG claims made by companies and detects potential greenwashing by combining:
- multi-agent reasoning,
- multi-source evidence collection,
- ML-enhanced risk scoring,
- regulatory and carbon-accounting checks,
- explainability outputs,
- enterprise-style report generation.

Primary runtime entry point:
- `main_langgraph.py`

## 2) Current Implemented Feature Set

## 2.1 Multi-Agent Analysis

Implemented agent modules in `agents/`:

1. `claim_extractor.py` - extracts structured ESG claims from report/news text.
2. `evidence_retriever.py` - gathers evidence from APIs, web, legal/compliance, and financial sources.
3. `contradiction_analyzer.py` - checks claim-vs-evidence contradictions.
4. `historical_analyst.py` - compares historical narratives and previous commitments.
5. `temporal_consistency_agent.py` - validates timeline consistency and year-over-year coherence.
6. `industry_comparator.py` - compares company against peer/industry patterns.
7. `credibility_analyst.py` - evaluates source quality and claim reliability.
8. `risk_scorer.py` - computes final risk using formula/ML-informed scoring.
9. `sentiment_analyzer.py` - detects sentiment and language style signals.
10. `confidence_scorer.py` - estimates confidence for verdict reliability.
11. `conflict_resolver.py` - resolves conflicting agent outputs into coherent signals.
12. `financial_analyst.py` - integrates financial metrics (revenue, margin, debt, etc.) with ESG context.
13. `carbon_extractor.py` - Scope 1/2/3 extraction and carbon-quality checks.
14. `greenwishing_detector.py` - detects greenwishing, greenhushing, and selective disclosure patterns.
15. `regulatory_scanner.py` - maps findings to India/global compliance frameworks.
16. `realtime_monitor.py` - supports live/continuous monitoring style evidence updates.

## 2.2 Workflow and Orchestration

Implemented in `core/`:

- `workflow_phase2.py` builds LangGraph flow.
- `supervisor_agent.py` routes analysis based on claim complexity.
- `agent_wrappers.py` executes and coordinates nodes.
- `debate_orchestrator.py` supports deeper analysis/revision loops.
- `state_schema.py` defines analysis state fields.
- `professional_report_generator.py` creates executive report outputs.
- `confidence_monitor.py` tracks confidence behavior.
- `evidence_cache.py` provides evidence caching.
- `llm_client.py` manages model/provider calls.
- `vector_store.py` connects vector retrieval storage.

## 2.3 Data and Evidence Layer

Implemented data-source and ingestion utilities in `utils/`:

- `free_data_sources.py` and `enterprise_data_sources.py` for global source aggregation.
- `indian_data_sources.py` and `indian_financial_data.py` for India-focused intelligence.
- `report_discovery.py`, `report_downloader.py`, `report_parser.py` for sustainability report pipeline.
- `company_report_fetcher.py` for company report acquisition.
- `web_search.py` for web-level retrieval.
- `source_tracker.py` for source tracking metadata.
- `cache/` subfolder for utility-specific caching helpers.

Implemented pipeline enhancements (documented in project reports):

- HTML fallback parsing when direct PDF retrieval fails.
- safer chunking fallback logic.
- ESG section detection before chunking.
- ESG keyword filtering for chunk relevance.
- batch chunk processing to reduce LLM API calls.
- claim extraction cache and call-rate protection.
- stronger diagnostics and integration validation.

## 2.4 ML and Explainability

Implemented in `ml_models/`:

- `xgboost_risk_model.py` - risk classification support.
- `lightgbm_esg_predictor.py` - ESG score/risk prediction utilities.
- `lstm_trend_predictor.py` - trend modeling.
- `anomaly_detector.py` - outlier/anomaly signals.
- `sentiment_esg_predictor.py` - sentiment-driven ESG prediction support.
- `climatebert_analyzer.py` - climate-language NLP (transformer-based).
- `explainability_engine.py` - SHAP/LIME explanation generation.
- `trained/` - storage location for serialized models/artifacts.

## 2.5 Configuration and Baselines

Implemented in `config/`:

- `settings.py` - runtime flags, feature toggles, defaults.
- `agent_prompts.py` - prompt definitions/templates.
- `data_sources.json` - source configuration map.
- `industry_baselines.json` - baseline metrics for peer comparison.

## 2.6 Reporting and Outputs

Generated output folders:

- `reports/` - final executive report outputs.
- `cache/` - extracted claims/evidence/report parsing caches.
- `chroma_db/` - vector data, historical/peer retrieval state.

Runtime output behavior from `main_langgraph.py`:

- text and JSON report export under `reports/`.
- optional full-state JSON export (toggle via environment variable).

## 2.7 Testing and Validation

Top-level test/verification scripts:

- `test_api_optimization.py`
- `test_chunking_fix.py`
- `test_html_parsing.py`
- `test_validation_pass.py`
- `verify_integration.py`

Additional tests under `tests/`:

- `tests/test_phase7_integration.py`
- `tests/test_research_grade_stabilization.py`

Guidance file:

- `TEST_GUIDE.md`

## 2.8 Major Improvement Milestones Already Included

Project-level milestone docs show completed hardening and optimization work:

- `OPTIMIZATION_COMPLETE.md`
- `API_OPTIMIZATION_REPORT.md`
- `CHUNKING_FIX_REPORT.md`
- `HTML_FALLBACK_ENHANCEMENT.md`
- `HTML_ENHANCEMENT_ANALYSIS.md`
- `DEBUGGING_STABILIZATION_REPORT.md`
- `PHASE7_COMPLETION_REPORT.md`
- `NEW_FEATURES_2026.md`

These reflect improvements already integrated in the codebase, including API reduction, chunk safety, HTML fallback coverage, debugging stabilization, and enterprise feature expansion.

## 3) Folder-by-Folder Guide (What Has What)

## 3.1 Root Folder (`MajorProject/`)

Contains:

- execution entry point: `main_langgraph.py`
- dependency list: `requirements.txt`
- primary docs and phase reports: all `*.md` and `IMPLEMENTATION_SUMMARY.txt`
- top-level test scripts: `test_*.py` and `verify_integration.py`

## 3.2 `agents/`

Contains specialized analysis agents. This is where domain logic for claim analysis, contradiction detection, carbon extraction, greenwishing detection, regulatory checks, financial context, sentiment, confidence, and risk synthesis lives.

## 3.3 `core/`

Contains system orchestration code: LangGraph workflow construction, agent wrappers, state schema, supervisor routing, debate handling, confidence control, vector/evidence integration, and professional report generation.

## 3.4 `utils/`

Contains ingestion and data plumbing: report discovery/download/parsing, web search, source APIs (global + Indian), source tracking, and utility cache helpers.

## 3.5 `ml_models/`

Contains ML model wrappers and explainability modules (XGBoost, LightGBM, LSTM, anomaly detection, ClimateBERT, SHAP/LIME engine) plus model artifact storage.

## 3.6 `config/`

Contains all central settings and baseline config assets (source lists, prompts, industry baselines).

## 3.7 `data/`

Contains curated datasets used for ESG training/testing/benchmarking, including company-level and market datasets plus a data README.

## 3.8 `notebooks/`

Contains training notebooks for model workflows:

- `train_xgboost_risk.ipynb`
- `train_lightgbm_esg_score.ipynb`
- `train_lstm_trend.ipynb`

## 3.9 `scripts/`

Contains operational/model maintenance scripts such as model regeneration, dataset exploration, cache management, and targeted model training helpers.

## 3.10 `tests/`

Contains focused integration/research-grade stabilization tests complementing top-level test scripts.

## 3.11 `cache/`

Contains runtime cache folders:

- `claim_extraction/`
- `company_reports/`
- `evidence/`
- `financial_data/`
- `parsed_reports/`
- `reports/`

## 3.12 `chroma_db/`

Contains vector database persistence (for example, peer comparison history and retrieval context).

## 3.13 `reports/`

Contains generated analysis reports and exports from workflow runs.

## 4) End-to-End Flow (Current)

1. User provides company + claim.
2. Supervisor evaluates complexity and selects route.
3. Evidence retriever gathers multi-source evidence (news, legal, financial, report content).
4. Specialized agents analyze contradictions, temporal consistency, credibility, peer context, regulatory risks, and deception patterns.
5. Risk scorer synthesizes findings with confidence signals and ML support.
6. Professional report generator exports executive output files.

## 5) Project Status Snapshot (As of March 2026)

This repository already includes:

- enterprise-level multi-agent architecture,
- global + India-specific ESG intelligence features,
- climate NLP and XAI modules,
- report pipeline hardening with HTML/PDF fallback handling,
- API optimization and caching improvements,
- integration/test utilities for validation.

In short: this is not an MVP-only codebase anymore; it is an expanded, optimization-focused, enterprise-style ESG analysis platform with documented phase-wise improvements.
