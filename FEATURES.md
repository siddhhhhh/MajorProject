# ESGLens — Complete Feature List (Speech Reference)

> This document is the canonical reference for all features implemented in ESGLens.
> Written from the actual codebase — not from stale documentation.

---

## 🏗️ SYSTEM ARCHITECTURE

| Feature | Detail |
|---------|--------|
| **Orchestration Engine** | LangGraph state machine with directed acyclic graph (DAG) workflow |
| **Dynamic Routing** | Supervisor Agent classifies complexity → routes to Fast / Standard / Deep track |
| **Parallel Analytics** | 10 independent agents run concurrently via `ThreadPoolExecutor` (fanout mode) |
| **Agentic State** | Full typed state schema passed between nodes; every agent reads and writes its own slot |
| **Memory** | LangGraph MemorySaver checkpoint; company Knowledge Graph persists across runs |
| **Timeout Handling** | Configurable workflow timeout (default 30 min); partial-result fallback on timeout |
| **Observability** | DIAG mode: per-node entry/exit logging with agent_output length + wall-clock |
| **Forensic Crash Trap** | RSS tracking, allocation sites, thread stack traces logged on crash |
| **Pipeline Log** | Unified `pipeline.log` captures every run; multi-session with headers |

---

## 🤖 AGENT ROSTER (36 Agents)

### Stage 1 — Intake
| Agent | What It Does |
|-------|-------------|
| **Supervisor** | Assesses claim complexity score (0–100); routes to Fast/Standard/Deep track |
| **ClaimExtractor** | Parses ESG claim → structured sub-claims with intensity, scope, timeframe, pillar |
| **ClaimDecomposer** | Breaks compound claims into atomic components; surfaces internal claim tensions |

### Stage 2 — Evidence Collection
| Agent | What It Does |
|-------|-------------|
| **EvidenceRetriever** | Queries 28+ live sources simultaneously; tags credibility weight on entry |
| **AdversarialValidator** | Tests if claims survive independent scrutiny; rejects company-document-only claims |
| **ReportDiscovery** | Finds and fetches company's latest sustainability / annual reports |
| **ReportDownloader** | Downloads PDFs from company IR pages |
| **ReportParser** | Extracts text + tables from PDFs (PyMuPDF + Camelot) |
| **ReportClaimExtractor** | Extracts structured ESG claims from parsed PDF text |

### Stage 3 — Carbon & Climate
| Agent | What It Does |
|-------|-------------|
| **CarbonExtractor** | Extracts Scope 1, 2, 3 emissions from reports/evidence; GHG Protocol aligned |
| **CarbonPathwayModeller** | Checks if company's reduction trajectory is IEA NZE / 1.5°C consistent |
| **EmissionsVerifier** | Cross-verifies disclosed emissions against Climate TRACE satellite data |
| **SubsidiaryWalker** | Traverses subsidiary tree via GLEIF; checks Climate TRACE asset coverage |
| **FinancedEmissions** | Computes PCAF-aligned financed/portfolio emissions for financial institutions |

### Stage 4 — Parallel Analytics (run concurrently)
| Agent | What It Does |
|-------|-------------|
| **GreenwishingDetector** | Detects Greenwashing / Greenwishing / Greenhushing patterns |
| **RegulatoryHorizonScanner** | Multi-jurisdiction scan: SEC, EU CSRD, UK FCA, India SEBI BRSR |
| **ClimateBERTAnalyzer** | NLP: classifies climate language; detects promotional vs. factual tone divergence |
| **SocialAgent** | Scores Social pillar (health/safety, labor rights, CSR, D&I) |
| **GovernanceAgent** | Scores Governance pillar (board, pay ratio, anti-corruption, whistleblower) |
| **ContradictionAnalyzer** | Detects claim-evidence contradictions with 3-tier classification |
| **TemporalConsistencyAgent** | Year-over-year goalpost tracking; flags weakening commitments |
| **PeerComparison** | Industry peer benchmarking; provides sector-specific sigma (σ) |
| **SentimentAnalyzer** | Linguistic sentiment analysis; GSI (Greenwashing Sentiment Index) |
| **CredibilityAnalyst** | Scores source credibility and reliability |

### Stage 5 — Post-Processing
| Agent | What It Does |
|-------|-------------|
| **RealTimeMonitor** | Surfaces real-time news, NGO reports, regulatory signals |
| **ESGMismatchDetector** | Future pledges vs. implementation gaps; past promise failures |
| **TemporalAnalyst** | Historical ESG violations, pattern analysis |
| **CommitmentLedger** | Longitudinal commitment and revision ledger |
| **HistoricalAnalyst** | Historical ESG pattern and violation analysis |
| **FactGraphBuilder** | Builds evidence-claim knowledge graph |
| **CrossPillarSynthesizer** | Detects contradictions spanning multiple ESG pillars |

### Stage 6 — Scoring & Output
| Agent | What It Does |
|-------|-------------|
| **RiskScorer** | Computes Greenwashing Risk Score using calibrated 4-bucket formula |
| **ExplainabilityEngine** | SHAP/LIME feature importance; score attribution |
| **AdversarialAudit** | Final adversarial quality audit of all findings |
| **ConfidenceScorer** | Confidence band calibration |
| **VerdictGenerator** | Synthesizes final verdict |
| **DebateOrchestrator** | (Deep Track only) Multi-agent structured debate before verdict |
| **ProfessionalReportGenerator** | Renders research-grade text + JSON + investor brief |
| **FinancialAnalyst** | Financial-ESG correlation analysis |

---

## 🌐 28+ LIVE DATA SOURCES

### Regulatory / Government
- **SEC EDGAR** — 10-K, DEF 14A proxy, SD (conflict minerals), XBRL data
- **EPA ECHO** — US environmental violations database
- **EU ESEF** — EU XBRL filings (194+ entities sampled for CSRD)
- **Indian SEBI BRSR** — India mandatory ESG disclosure registry

### ESG Registries
- **CDP** — Carbon Disclosure Project (A-list scoring, Scope 3 data)
- **SBTi** — Science-Based Targets initiative (14,900+ company registry)
- **UN Global Compact** — Participants directory
- **GRI Database** — Global Reporting Initiative standards compliance
- **WBA** — World Benchmarking Alliance SDG2000 (social, governance, environment pillar scores)
- **WRI Aqueduct 4.0** — 13 water risk indicators (physical, regulatory, reputational)
- **PCAF** — Partnership for Carbon Accounting Financials (financed emissions)

### Legal / Litigation
- **CourtListener** — US federal and state court dockets
- **Indian Kanoon** — Indian court case search
- **OpenSanctions** — Corruption, sanctions, and PEP screening

### Corporate / Identity
- **GLEIF** — Global Legal Entity Identifier (subsidiary walk, corporate tree)
- **UK Companies House** — UK corporate filings

### Climate / Emissions
- **Climate TRACE** — Asset-level satellite-verified emissions (country × sector)
- **GDELT** — Global news and event database for ESG signals

### News / Media
- **NewsAPI** — Structured news from 80,000+ sources
- **Reuters** — Tier-1 financial and regulatory news
- **Google News** / **Google Scholar** — Public news and academic papers
- **DuckDuckGo** — Adversarial web search channel (hunts for lawsuits, NGO reports)
- **ESG News** — Dedicated ESG media monitoring

---

## 🧮 THE GREENWASHING RISK FORMULA

```
GW = α · max(0, (C - P) / σ) · 100
   + β · R
   + γ · (1 - D/100) · 100
   + δ · T
   + Σ (Structural Penalties)
   → Post-calibration adjustment
```

| Variable | Meaning |
|----------|---------|
| **C** | Claim Intensity (0–100): how bold/specific is the claim? |
| **P** | Performance Score (0–100): actual ESG pillar performance |
| **σ** | Industry sigma: peer-group standard deviation (cross-sector fallback if peers < 5) |
| **R** | Controversy/Historical Trust Risk (0–100) |
| **D** | Disclosure Completeness (0–100) |
| **T** | Temporal Escalation (flagged goalpost changes) |
| **α, β, γ, δ** | Weights: Gap=0.35, Controversy=0.40, Disclosure=0.10, Temporal=0.15 |
| **Structural Penalties** | Subsidiary poor coverage (+2), Carbon pathway gap >30% (+20), etc. |

**Key insight**: ESG Score and GW Score are **independent** — a company can have a high ESG score AND high greenwashing risk.

---

## 📊 ESG PILLAR SCORING

### Environmental Factors
- GHG Emissions Intensity (25% weight in oil & gas)
- Scope 3 Coverage (15%)
- Renewable Energy Transition (20%)
- Water Usage & Stress (17%)
- Biodiversity & Land Use (13%)
- Waste & Circular Economy (10%)

### Social Factors
- Employee Health & Safety (25%)
- Labor Rights & Fair Wages (25%)
- Community Impact & CSR Spend (20%)
- Supply Chain Labor Standards (15%)
- Diversity, Equity & Inclusion (15%)

### Governance Factors
- Board Independence (20%)
- Board Diversity (20%)
- Executive Pay Ratio (20%)
- Anti-Corruption Policies (20%)
- Whistleblower Mechanisms (10%)
- ESG Disclosure Quality (10%)

**Industry weights (example — Oil & Gas):**
- Environmental: 45.7%
- Social: 19.1%
- Governance: 35.2%

---

## 📋 REGULATORY FRAMEWORKS CHECKED

| Jurisdiction | Framework | Check Type |
|-------------|-----------|-----------|
| 🇺🇸 US | SEC Climate Disclosure Rule | EDGAR XBRL mandatory filing |
| 🇺🇸 US | EPA ECHO | Environmental violations database |
| 🇪🇺 EU | CSRD | EU ESEF XBRL registry scan |
| 🇪🇺 EU | EU Taxonomy Regulation | Framework status |
| 🇬🇧 UK | FCA Anti-Greenwashing Rule | Heuristic + news scan |
| 🇮🇳 India | SEBI BRSR | NSE/BSE listing fact inference |
| 🌍 Global | GHG Protocol Corporate Standard | In-disclosure citation check |
| 🌍 Global | TCFD | FSB-TCFD archive + self-attestation |
| 🌍 Global | CDP | A-List public registry scan |
| 🌍 Global | SBTi | Registry scan (14,901 entries) |
| 🌍 Global | UN Global Compact | Participants directory scan |
| 🌍 Global | GRI Standards | GRI database check |
| 🌍 Global | IPCC Consistency | Carbon pathway alignment check |
| 🌍 Global | Active Enforcement | Litigation/enforcement scan |

---

## 🔍 DECEPTION PATTERN DETECTION

| Pattern | Definition | ESGLens Detection |
|---------|-----------|------------------|
| **Greenwashing** | Actively misleading — claims contradicted by evidence | Contradiction Analyzer + Regulatory Scanner + Adversarial Validator |
| **Greenwishing** | Sincere but unfunded — bold targets, no plan | Greenwishing Detector (vague language NLP + pathway gap check) |
| **Greenhushing** | Selectively quiet on poor performance areas | Greenwishing Detector (disclosure gap analysis) |
| **Carbon Tunnel Vision** | Obsessive focus on one scope while ignoring others | Carbon Extractor (Scope 3 category audit) |
| **Selective Disclosure** | Cherry-picking favorable metrics | Evidence pattern analysis |

---

## 🤖 LLM ROUTING TABLE

| Agent | Primary Model | Fallback 1 | Fallback 2 |
|-------|-------------|-----------|-----------|
| Report Generation | Gemini 2.5 Pro | Gemini 2.5 Pro (OpenRouter) | Gemini 2.0 Flash |
| Contradiction Analysis | LLaMA 3.3 70B (Groq) | LLaMA 3.3 70B (OpenRouter) | Gemini 2.0 Flash |
| Risk Scoring | LLaMA 3.3 70B (Groq) | Mistral Small 3.1 24B | Gemini 2.0 Flash |
| Regulatory Scanning | Qwen 3 32B (Groq) | LLaMA 3.3 70B | Mistral Small |
| Greenwishing | LLaMA 3.3 70B (Groq) | LLaMA 3.3 70B (OpenRouter) | Gemini 2.0 Flash |
| ESG Mismatch | LLaMA 3.3 70B (Groq) | Qwen 3 235B (Cerebras) | OpenRouter |
| Carbon Extraction | Gemini 2.0 Flash | LLaMA 3.3 70B | Mistral Small |
| Claim Extraction | LLaMA 3.1 8B (Cerebras) | LLaMA 3.1 8B (Groq) | Mistral Small |
| Temporal Analysis | Qwen 3 235B (Cerebras) | LLaMA 3.1 8B | LLaMA 4 Maverick |
| Sentiment Analysis | LLaMA 4 Scout 17B (Groq) | LLaMA 3.1 8B (Cerebras) | LLaMA 4 Scout (OR) |
| Debate | LLaMA 4 Scout 17B (Groq) | LLaMA 3.1 8B | Mistral Small |
| Supervisor | LLaMA 3.3 70B (Groq) | LLaMA 3.3 70B (OR) | Gemini 2.0 Flash |

**Policy**: Temperature=0.0 for all agents (determinism > diversity for ESG judgment work).

---

## 📑 REPORT SECTIONS (30+ sections)

| Section | Content |
|---------|---------|
| **Header** | Company, ticker, industry, claim, report ID, date, confidence, version |
| **Verdict** | GW score with variance band, ESG score + rating, risk band, calibration status |
| **3: Executive Summary** | Plain-English summary + critical caveats |
| **3B: Claim Breakdown** | Sub-claim decomposition |
| **3C: Abstention Decisions** | SURE-RAG per-sub-claim gating; abstention rate |
| **4: Evidence Citations** | Source table: type, verified, evidence role (supports/contradicts/mixed) |
| **5: Score Derivation** | E/S/G factor tables with source attribution, data quality, weighted contribution |
| **5A: Materiality Profile** | Industry-specific weights + material topics |
| **5B: External Benchmarks** | WBA + WRI integration; score adjustments |
| **5C: Score Components** | 7-driver decomposition (claim verification, evidence quality, source mix, etc.) |
| **5D: Score Contributors** | Ranked ledger contributors (no LLM rephrasing) |
| **5E: Counterfactuals** | "What if" scenarios computed deterministically from ledger |
| **6: Key Risk Drivers** | Top 3 risk factors with impact and direction |
| **7: Contradictions** | Tiered contradictions (🔴 Tier-1 / 🟡 Tier-2 / ⚪ Tier-3) |
| **7B: Regulatory Status** | Full framework status table: compliant / gap / uncertain / active enforcement |
| **7C: Public Coverage** | News and search hits for regulatory issues |
| **7D: EPA + EDGAR** | US-only: environmental capex vs. violation history |
| **7E: Litigation Dockets** | CourtListener + Indian Kanoon resolved cases |
| **8: Carbon Emissions** | Scope 1/2/3 table; net-zero target; SBTi status; Scope 3 per-category audit |
| **8B: Pathway Alignment** | IEA NZE required rate vs. company implied rate; carbon budget remaining |
| **8C: Emissions Verification** | Climate TRACE satellite cross-check |
| **8E: Subsidiary Footprint** | GLEIF subsidiary walk; coverage score; structural penalty |
| **9: Deception Patterns** | Greenwashing/Greenwishing/Greenhushing scores; NLP signal |
| **9B: Recent News** | Top 5 real-time news articles |
| **10: Social Analysis** | Social pillar factor detail |
| **11: Governance Analysis** | Governance pillar factor detail |
| **11C: KG History** | YoY drift signals; fact graph motifs; decision-readiness |
| **12A: ESG Mismatch** | Future pledges vs. progress; past promise-implementation gaps |

---

## 💡 KEY DIFFERENTIATORS vs. MSCI / Sustainalytics / Refinitiv

| Problem | Incumbents | ESGLens |
|---------|-----------|---------|
| **Audit Trail** | Letter grade, no source | Every number traces to a specific URL, credibility weight, and agent |
| **Deception Types** | Lumped into one score | Greenwashing / Greenwishing / Greenhushing classified separately |
| **Data Freshness** | Quarterly/annual updates | Live — new 10-K, new court ruling picked up same day |
| **Regulatory Coverage** | Typically 1–2 jurisdictions | US + EU + UK + India + Global simultaneously |
| **Evidence Sources** | 2–4 vendor feeds | 28+ live sources |
| **Scoring Transparency** | Black box | Full score modifier ledger with counterfactuals |
| **Carbon Science** | Reported numbers accepted | 1.5°C pathway modelling; Scope 3 category audit; satellite verification |
| **Scalability** | Weeks per company | ~15 minutes per company; thousands/day |

---

## 📦 OUTPUT ARTIFACTS

| File | Format | Size | Purpose |
|------|--------|------|---------|
| `ESG_Report_<company>_<ts>.txt` | Plain Text | ~60KB | Human-readable audit report (30+ sections) |
| `ESG_Report_<company>_<ts>.json` | JSON | ~1MB | Machine-readable full structured data |
| `ESG_Report_<company>_<ts>_brief.json` | JSON | ~5KB | Investor one-pager (scores, risks, DD questions) |

---

## 🔢 KEY NUMBERS (for speech)

- **36** specialized AI agents
- **28+** live external data sources
- **~15 minutes** per company (vs. 4–6 weeks traditional)
- **51** companies validated across 8 sectors
- **14,900+** SBTi registry entries scanned per run
- **15** GHG Protocol Scope 3 categories audited per company
- **30+** report sections per analysis
- **4** regulatory jurisdictions simultaneously (US, EU, UK, India)
- **3** output formats per run (text, JSON, investor brief)
- **3** deployment modes (SaaS, dedicated cloud, on-premise)
- **4** LLM providers (Gemini, Groq, Cerebras, OpenRouter) with automatic failover
- **AAA → CCC** ESG rating scale (7 bands, aligned with institutional rating conventions)
- **0–100** Greenwashing Risk Score
- **LLM variance band**: inter-provider empirical confidence interval from 8 probes
