# ESGLens — Project Documentation
*Last updated from codebase: June 2026 | Version 4.0*

---

## Project Summary

**ESGLens** is an AI-powered ESG (Environmental, Social, Governance) Greenwashing Detection Engine. It is not a traditional rating platform — it is an audit engine that combines 36 specialized AI agents, 28+ live external data sources, and a calibrated multi-factor scoring formula to produce research-grade, fully traceable greenwashing risk assessments in ~15 minutes per company.

**Core thesis**: ESG agency ratings have a 0.54 correlation (MIT Sloan study, Berg et al.) versus 0.92 for credit ratings. ESGLens fixes this with a glass-box, source-attributed, deterministic scoring system backed by live evidence retrieval.

---

## System Architecture

### Workflow Engine
- Built on **LangGraph** (directed acyclic graph state machine)
- Central state schema: `ESGState` (typed TypedDict) — passed between all nodes
- Three analysis tracks:
  - **Fast Track**: Supervisor → Claim Extraction → Risk Scoring → Verdict (3 agents, ~3 min)
  - **Standard Track**: Full 30+ agent pipeline with parallel fanout (~15 min)
  - **Deep Analysis Track**: Standard + Multi-Agent Debate Mechanism (~20 min)
- Supervisor Agent scores claim complexity 0–100 to route automatically
- Configurable `ESG_WORKFLOW_TIMEOUT` env var (default: 30 minutes)
- Graceful partial-result fallback on timeout or agent failure

### Execution Model
- The pipeline runs as an **isolated subprocess** launched by `api/analysis.py`
- FastAPI server (`server.py`) manages subprocess lifecycle, captures stdout/stderr
- Live pipeline logs streamed to frontend via WebSocket
- State is not shared across processes — final state is persisted to disk (`.json`)

### Parallel Analytics Fanout
- 10 agents run concurrently inside `parallel_analytics_node` using `ThreadPoolExecutor`
- Agents: GreenwishingDetector, RegulatoryScanner, ClimateBERT, SocialAgent, GovernanceAgent, ContradictionAnalyzer, TemporalConsistencyAgent, PeerComparison, SentimentAnalyzer, CredibilityAnalyst

---

## Agent System (36 Agents)

### Stage 1: Intake
| Agent | Class / Module | Key Output |
|-------|----------------|-----------|
| Supervisor | `core/workflow_phase2.py` | Complexity score; track selection |
| ClaimExtractor | `agents/claim_extractor.py` | Structured sub-claims with intensity/scope/timeframe/pillar |
| ClaimDecomposer | `core/claim_decomposer.py` | Atomic sub-claims; internal claim tensions |

### Stage 2: Evidence Collection
| Agent | Class / Module | Key Output |
|-------|----------------|-----------|
| EvidenceRetriever | `agents/evidence_retriever.py` | 28+ source evidence items with credibility weights |
| AdversarialValidator | `core/adversarial_validator.py` | Triangulated evidence; company-doc-only rejection |
| ReportDiscovery | `core/report_discoverer.py` | Company report URLs |
| ReportDownloader | `core/report_downloader.py` | Raw PDF bytes |
| ReportParser | `core/report_parser.py` | Text chunks + tables from PDF |
| ReportClaimExtractor | `core/report_claim_extractor.py` | Structured claims from PDF text |

### Stage 3: Carbon & Climate
| Agent | Class / Module | Key Output |
|-------|----------------|-----------|
| CarbonExtractor | `agents/carbon_extractor.py` | Scope 1/2/3 (tCO2e), Scope 3 category audit, boundary classification |
| CarbonPathwayModeller | `core/carbon_pathway_modeller.py` | Pathway gap %, alignment status, carbon budget years remaining |
| EmissionsVerifier | `core/emissions_verifier.py` | Climate TRACE cross-check result |
| SubsidiaryWalker | `core/subsidiary_footprint.py` | GLEIF subsidiary tree; coverage score; structural penalty |
| FinancedEmissions | `core/financed_emissions_calculator.py` | PCAF-aligned financed/portfolio emissions |

### Stage 4: Parallel Analytics
| Agent | Class / Module | Key Output |
|-------|----------------|-----------|
| GreenwishingDetector | `agents/greenwishing_detector.py` | Deception risk score; pattern flags (GW/GWish/GH) |
| RegulatoryHorizonScanner | `agents/regulatory_scanner.py` | Per-framework compliance status; active enforcement |
| ClimateBERTAnalyzer | `core/climatebert_analyzer.py` | Climate relevance; promotional vs. factual divergence |
| SocialAgent | `agents/social_agent.py` | Social pillar factors scored; WBA integration |
| GovernanceAgent | `agents/governance_agent.py` | Governance pillar factors scored; DEF 14A extraction |
| ContradictionAnalyzer | `agents/contradiction_analyzer.py` | Tier-1/2/3 contradictions with source + confidence |
| TemporalConsistencyAgent | `core/temporal_consistency_agent.py` | YoY goalpost changes; weakening commitments |
| PeerComparison | `agents/financial_analyst.py` | Industry peer percentiles; sector sigma (σ) |
| SentimentAnalyzer | `agents/sentiment_analyzer.py` | Sentiment score; GSI (Greenwashing Sentiment Index) |
| CredibilityAnalyst | `agents/credibility_analyst.py` | Per-source credibility tier and weight |

### Stage 5: Post-Processing
| Agent | Class / Module | Key Output |
|-------|----------------|-----------|
| RealTimeMonitor | `agents/realtime_monitor.py` | Top 5 ESG news articles |
| ESGMismatchDetector | `features/esg_mismatch_detector/` | Future pledges; past implementation gaps |
| CommitmentLedger | `commitment_tracker/` | Longitudinal pledge + revision ledger |
| HistoricalAnalyst | `agents/historical_analyst.py` | Historical violation patterns |
| FactGraphBuilder | `core/company_knowledge_graph.py` | Evidence-claim KG; pillar coverage skew |

### Stage 6: Scoring & Output
| Agent | Class / Module | Key Output |
|-------|----------------|-----------|
| RiskScorer | `agents/risk_scorer.py` | GW score (0–100); ESG score; score modifier ledger |
| ExplainabilityEngine | `core/explainability_engine.py` | SHAP/LIME feature attribution |
| AdversarialAudit | `core/adversarial_validator.py` | Final quality audit of all findings |
| ConfidenceScorer | `agents/confidence_scorer.py` | Calibrated confidence band |
| VerdictGenerator | `core/verdict_generator.py` | Final plain-English verdict + key findings |
| DebateOrchestrator | `agents/conflict_resolver.py` | Multi-agent debate result (Deep Track only) |
| ProfessionalReportGenerator | `core/professional_report_generator.py` | 30-section text report; JSON export; investor brief |

---

## Scoring System

### Greenwashing Risk Formula
```
GW = α · max(0, (C - P) / σ) · 100   [Formula Gap bucket]
   + β · R                             [Historical Trust / Controversy bucket]
   + γ · (1 - D/100) · 100            [Disclosure Quality bucket]
   + δ · T                             [Current Contradictions bucket]
   + Σ (Structural Penalties)
   → Post-calibration adjustment
```

**Inputs:**
- **C (Claim Intensity, 0–100)**: Scored by ClaimExtractor. Net-zero floor = 60. Carbon-neutral = 40.
- **P (Performance Score, 0–100)**: Weighted ESG pillar score, adjusted by WBA/WRI external benchmarks
- **σ (Industry Sigma)**: Standard deviation from peer-group; cross-sector fallback (n=87) when peer count < 5
- **R (Controversy Risk, 0–100)**: From HistoricalAnalyst; uses known-cases registry + OpenSanctions
- **D (Disclosure Completeness, 0–100)**: Composite of CDP, GRI, TCFD, GHG Protocol, SBTi signals
- **T (Temporal Escalation)**: From TemporalConsistencyAgent; 0 if no goalpost changes
- **Weights**: α=0.35, β=0.40, γ=0.10, δ=0.15

**Structural Penalties:**
- Subsidiary poor coverage: +2.0 GW points
- Carbon pathway gap > 30%: +20.0 GW points
- Others configurable per run

**Rating Scale (ESG Score → Rating):**
| ESG Score | Rating |
|-----------|--------|
| ≥ 90 | AAA |
| ≥ 85 | AA |
| ≥ 75 | A |
| ≥ 60 | BBB |
| ≥ 50 | BB |
| ≥ 35 | B |
| < 35 | CCC |

**Risk Bands (GW Score):**
- ≥ 60: HIGH
- 40–59: MODERATE
- < 40: LOW

### ESG Pillar Scoring
- SASB-inspired industry-specific materiality weighting
- Industry profiles defined in `config/materiality_profiles.json`
- Per-factor scoring with explicit source attribution
- Coverage-adjusted scores: missing indicators → "Limited Disclosure" (not zero)
- External benchmark integration: WBA scores blend in via weighted average

### Calibration
- Post-hoc calibration using industry-peer calibration samples
- Sample size labels: PROVISIONAL (n<10), LIMITED (n<30), STANDARD (n≥30)
- LLM Variance Band: 8-probe inter-provider diagnostic; half-width = worst-case GW shift
- Industry sigma falls back to cross-sector (n=87) when peer count < 5

---

## Data Source Integrations

### `core/esg_data_apis.py`
Primary integration module for external ESG data APIs:
- **WBA (World Benchmarking Alliance)**: SDG2000 company API; 65+ indicators per company; natural_capital, human_rights, carbon_emissions, governance scores
- **WRI Aqueduct 4.0**: Physical, regulatory, and reputational water risk; 13 indicator dimensions
- **WRI CAIT**: CO2 country-level emissions (historical context)
- **SEC EDGAR**: XBRL financial data, DEF 14A proxy statements, Form SD filings
- **SBTi**: 14,900+ company registry (full download and scan)
- **CDP**: Public scores and A-list
- **UN Global Compact**: Participants directory
- **GRI Database**: Reporting standards compliance
- **InfluenceMap**: Climate lobbying records
- **OpenSanctions**: Corruption and sanctions
- **GLEIF**: Legal Entity Identifier registry
- **Climate TRACE**: Satellite-verified asset-level emissions
- **CourtListener**: US court dockets
- **Indian Kanoon**: Indian court cases
- **EPA ECHO**: US environmental violations
- **EU ESEF**: XBRL filing API (194+ entities sampled)
- **GDELT**: Global news events
- **NewsAPI / Reuters / Google News**: Real-time news

---

## LLM Infrastructure

### Multi-Provider Routing (`core/llm_router.py`)
- Providers: Google Gemini, Groq, Cerebras, OpenRouter
- Per-agent routing table: primary → fallback_1 → fallback_2
- Automatic failover on rate limit or error
- Temperature=0.0 default (reproducibility over diversity)
- JSON mode enforced where structured output is required
- Retired model registry: known-dead endpoints skipped automatically

### LLM Call Layer (`core/llm_call.py`)
- Rate limiting, retry with exponential backoff
- LLM audit log: every call records provider, model, latency
- `use_cache=False` option for real-time evidence analysis

### LangChain Integration
- `RoutedLangChainChatModel`: Custom BaseChatModel adapter that uses the routing table
- Used by KG-RAG and other LangChain-native components

---

## Caching & Storage

| Component | Implementation | Purpose |
|-----------|---------------|---------|
| `EvidenceCache` | File-based JSON | Cache evidence by company/claim hash |
| `EmbedCache` | Pickle/file | Cache vector embeddings for evidence chunks |
| `DeadURLCache` | File-based JSON | Skip permanently-dead URLs |
| `LLMCache` | SQLite | Cache LLM responses for identical prompts |
| `VectorStore` | ChromaDB | Semantic search over evidence and report chunks |
| `CompanyKnowledgeGraph` | JSON/graph file | Persistent KPI history across runs |
| `LitigationCache` | File | Cache court docket results |

---

## API Surface

### REST Endpoints (`server.py` + `api/`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyse` | Start ESG analysis; returns `analysis_id` |
| GET | `/api/analysis/{id}` | Poll status; retrieve results when complete |
| WebSocket | `/ws/pipeline/{id}` | Stream live pipeline logs |
| GET | `/health` | Health check |
| POST | `/api/reports/` | Report management |
| POST | `/api/chatbot/` | ESG Analyst Copilot chatbot |
| POST | `/api/upload/` | Upload PDF for analysis |

### Analysis Request Schema
```json
{
  "company": "Shell",
  "claim": "Net zero emissions by 2050",
  "industry": "oil_and_gas",
  "ticker": "SHEL",
  "deep_analysis": false
}
```

### Analysis Response Schema
```json
{
  "analysis_id": "20260608-101047-SHEL",
  "status": "completed",
  "greenwashing_score": 86.9,
  "esg_score": 40.1,
  "risk_band": "HIGH",
  "confidence": 65.0,
  "report_path": "reports/ESG_Report_Shell_20260608_101047.txt",
  "json_path": "reports/ESG_Report_Shell_20260608_101047.json"
}
```

---

## ESG Analyst Copilot (Chatbot)

**Module**: `chatbot_backend/service.py`

The conversational interface for querying generated reports.

### Capabilities
- Intent detection: score lookup, score explanation, contradiction queries, regulatory queries, section extraction
- Session memory: conversation history maintained per-session
- Dual LLM routing: Gemini primary → Groq fallback
- ESG scope guard: blocks non-ESG questions
- **Deterministic fast path**: Direct score/section lookups (no LLM required)
- **LLM fallback path**: Complex/open-ended questions with citation-backed answers

### Example Queries
- "Why is the governance score low?"
- "Which evidence is government-sourced?"
- "What were the three main contradictions?"
- "What's the Scope 3 coverage?"
- "What happens to the score if the carbon pathway gap closes?"

---

## Output Files

### Text Report (`ESG_Report_<company>_<ts>.txt`)
- ~60KB plain text
- 30+ named sections (see FEATURES.md for full section list)
- Human-readable, publication-style
- Max 500KB cap; truncated with `[TRUNCATED AT 500KB]` marker if exceeded

### JSON Export (`ESG_Report_<company>_<ts>.json`)
- ~1MB structured JSON
- Full state dump: all agent outputs, evidence, scores, calibration, quality warnings
- Machine-readable for API/dashboard integration
- Validated against `core/report_schema.py` (Pydantic models)
- Consistency check: `core/report_consistency_validator.py` — ESG rating, risk band, score range cross-validated

### Investor Brief (`ESG_Report_<company>_<ts>_brief.json`)
- ~5KB compact JSON
- Contents: headline scores, LLM variance bands, top 3 risks, enforcement status, carbon snapshot, 3 due-diligence questions, abstention summary, counterfactual scenarios, score attribution, emissions verification
- Designed for portfolio/diligence use cases

---

## Quality Assurance

### Report Quality Checker (`core/professional_report_generator.py: ReportQualityChecker`)
Before rendering, checks:
- Evidence coverage and verifiability (min 3 verified sources for MEDIUM confidence)
- Traceability of ESG pillar scores to factor rows
- Synthetic peer data usage flags
- Agent success flags vs. actual findings
- Carbon scope completeness (warns if Scope 2 or Scope 3 missing on net-zero claims)
- External benchmark mismatch detection
- Calibration sample size warnings (n<10 = PROVISIONAL, n<30 = LIMITED)

### Report Consistency Validator (`core/report_consistency_validator.py`)
Cross-validates:
- ESG score → rating consistency (canonical bin table)
- GW score → risk band consistency
- Score range validity (0–100)

### SURE-RAG Abstention Layer
Per-sub-claim verification gate:
- Minimum 2 independent sources
- Minimum 1 Tier-1 or Tier-2 source
- Semantic relevance > 0.3 threshold
- Returns `INSUFFICIENT_EVIDENCE` (abstains) rather than guessing when thresholds not met

---

## Known Data Limitations

| Limitation | Impact | Mitigated By |
|-----------|--------|-------------|
| Calibration sample small (n<10) for some sectors | Score labeled PROVISIONAL | Cross-sector sigma fallback |
| GRI database can time out | GRI check = UNCERTAIN | Multi-source evidence |
| SBTi registry legal name mismatch | Company may appear not found | Known-alias lookup |
| Climate TRACE: limited non-US/EU coverage | Ground-truth verification not available | Flagged in report |
| Scope 3 boundary: FULL vs. PARTIAL ambiguous | Boundary treated as PARTIAL_INFERRED | Per-category audit |
| CDP A-list is top 61 only | Non-disclosure ≠ bad score | Explained in report |
| TCFD: FSB registry frozen post Oct 2023 | Self-attestation fallback | Noted in footnote |

---

## Development & Testing

### Running Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Set API keys in .env (see .env.example)
cp .env.example .env

# Run single company analysis
python main_langgraph.py --company "Shell" --claim "Net zero emissions by 2050"

# Start API server
uvicorn server:app --reload --port 8000

# Run tests
pytest tests/ -v
```

### Environment Variables
```
GOOGLE_API_KEY=          # Gemini API key
GROQ_API_KEY=            # Groq API key
CEREBRAS_API_KEY=        # Cerebras API key
OPENROUTER_API_KEY=      # OpenRouter API key
ESG_WORKFLOW_TIMEOUT=    # Seconds (default: 1800)
ESG_ALLOW_RETIRED_MODELS=# 0 (default) or 1 to enable
```

### Demo Logs
Pre-generated demo logs for key companies:
- `_jpmc_demo_dryrun_20260605.log` — JPMorgan Chase
- `exxonmobil_demo.log` — ExxonMobil
- `microsoft_demo.log` — Microsoft
- Report: `reports/ESG_Report_Shell_20260608_154049.txt`

---

## File Structure

```
ESGLens/
├── main_langgraph.py          # CLI entry point; full pipeline
├── server.py                  # FastAPI server definition
├── api/
│   └── analysis.py            # Subprocess management + log capture
├── agents/                    # All 36 agent classes
│   ├── claim_extractor.py
│   ├── evidence_retriever.py
│   ├── carbon_extractor.py
│   ├── greenwishing_detector.py
│   ├── regulatory_scanner.py
│   ├── social_agent.py
│   ├── governance_agent.py
│   ├── contradiction_analyzer.py
│   ├── risk_scorer.py
│   └── ...
├── core/
│   ├── workflow_phase2.py     # LangGraph graph definition
│   ├── state_schema.py        # ESGState TypedDict
│   ├── llm_router.py          # Per-agent LLM routing table
│   ├── llm_call.py            # LLM call layer (rate limit, retry, cache)
│   ├── esg_data_apis.py       # External data integrations (WBA, SEC, etc.)
│   ├── carbon_pathway_modeller.py
│   ├── professional_report_generator.py
│   ├── report_schema.py       # Pydantic schema for report validation
│   ├── company_knowledge_graph.py
│   ├── adversarial_validator.py
│   ├── climatebert_analyzer.py
│   └── ...
├── chatbot_backend/
│   └── service.py             # ESG Analyst Copilot service
├── features/
│   └── esg_mismatch_detector/ # ESG mismatch detection feature
├── data/
│   ├── known_cases.py         # Curated enforcement history
│   └── materiality_profiles/  # Industry ESG weight profiles
├── config/                    # Configuration files
├── ml_models/                 # ML model definitions and weights
├── reports/                   # Generated reports (gitignored)
├── cache/                     # Evidence/LLM cache (gitignored)
├── logs/                      # Pipeline logs
├── chroma_db/                 # ChromaDB vector store
└── tests/                     # Pytest test suite
```

---

## Roadmap (Next 12 Months)

| Timeline | Feature |
|----------|---------|
| Q3 2026 | **Litigation Database**: Sabin Center for Climate Change Law (700+ cases); grows calibration from 51 → 250 companies per sector |
| Q3 2026 | **Continuous Portfolio Monitoring Dashboard**: Nightly delta reports; daily ESG alerts for portfolio companies |
| Q4 2026 | **Carbon Credit Quality Scoring**: Verra and Gold Standard offset registry; removal vs. avoidance classification |
| Q1 2027 | **Multi-Language Parser Stack**: Japanese, German, Portuguese, French, Korean, Hindi; covers BRSR mandate (India's top 1,000 listed companies) |
