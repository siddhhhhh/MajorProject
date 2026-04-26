
  ┌─────┬──────────────────────────────────────┬──────────────────┬────────────────────────────┬──────────────────────────────────────────────────────┐
  │  #  │                Source                │       Auth       │           Status           │                       Returns                        │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 1   │ NewsAPI (newsapi.org)                │ API key          │ ✅ key valid, may return 0 │ Broad news articles                                  │
  │     │                                      │ (NEWSAPI_KEY)    │  for narrow queries        │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 2   │ NewsData.io                          │ API key          │ ✅ key valid, may return 0 │ ESG-tagged articles                                  │
  │     │                                      │ (NEWSDATA_KEY)   │  for narrow queries        │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 3   │ DuckDuckGo Web/News                  │ none             │ ✅ working                 │ Real-time web/news results                           │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 4   │ Reuters Sustainability (via Google   │ none             │ ✅ FIXED today (was 404    │ Reuters-sourced ESG articles                         │
  │     │ News site:reuters.com)               │                  │ endpoint)                  │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 5   │ Google News RSS                      │ none             │ ✅ working (always-on      │ News aggregator                                      │
  │     │                                      │                  │ fallback)                  │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 6   │ Google Scholar (via Semantic Scholar │ none             │ ⚠️ intermittent (rate      │ Peer-reviewed papers                                 │
  │     │  API)                                │                  │ limits)                    │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 7   │ CDP (Carbon Disclosure Project) —    │ none             │ ⚠️ silent (HTML parser     │ Company CDP responses                                │
  │     │ public scrape                        │                  │ stale)                     │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 8   │ SBTi Registry                        │ none             │ ⚠️ silent (HTML parser     │ Validated science-based targets                      │
  │     │ (sciencebasedtargets.org) — scrape   │                  │ stale)                     │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 9   │ Company Investor Relations           │ none             │ ✅ working                 │ IR / sustainability page URLs                        │
  │     │ (auto-discovery)                     │                  │                            │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 10  │ UK Companies House                   │ none             │ ✅ working                 │ UK filings, directors, status                        │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 11  │ OpenSanctions                        │ none             │ ✅ working                 │ Sanctions / PEP screening                            │
  │     │ (api.opensanctions.org)              │                  │                            │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 12  │ InfluenceMap (via DuckDuckGo site:   │ none             │ ⚠️ intermittent            │ Climate lobbying records                             │
  │     │ search)                              │                  │                            │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 13  │ GRI Database (via DuckDuckGo site:   │ none             │ ⚠️ intermittent            │ GRI sustainability reports                           │
  │     │ search)                              │                  │                            │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │     │ Adversarial channel (8               │                  │                            │ Lawsuits, NGO reports, court rulings (ClientEarth,   │
  │ 14  │ site:-targeted DDG queries)          │ none             │ ✅ working                 │ Reclaim Finance, AFM, rechtspraak.nl, EUR-Lex, SEC,  │
  │     │                                      │                  │                            │ InfluenceMap)                                        │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 15  │ SEC EDGAR full-text search           │ none             │ ✅ ADDED today (was        │ 10-K, 10-Q, 8-K, DEF 14A, SD, 20-F, 40-F, 6-K        │
  │     │ (efts.sec.gov)                       │                  │ governance-only)           │                                                      │
  ├─────┼──────────────────────────────────────┼──────────────────┼────────────────────────────┼──────────────────────────────────────────────────────┤
  │ 16  │ Internal vector store (ChromaDB)     │ local            │ ✅ working                 │ Historical context from past runs                    │
  └─────┴──────────────────────────────────────┴──────────────────┴────────────────────────────┴──────────────────────────────────────────────────────┘
  
  B. Pillar enrichment APIs (called from core/esg_data_apis.py)

  ┌───────────────────────────────────┬────────────────────────────────┬─────────────────────────────────────────────────────────────────────┐
  │              Source               │              Auth              │                                 Use                                 │
  ├───────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
  │ WBA (World Benchmarking Alliance) │ API key (WBA_API_KEY)          │ E/S/G pillar fill when IR sparse                                    │
  ├───────────────────────────────────┼────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
  │ WRI Aqueduct 4.0                  │ RESOURCE_WATCH_API_KEY + token │ 13 water-risk indicators (8 physical, 3 regulatory, 2 reputational) │
  └───────────────────────────────────┴────────────────────────────────┴─────────────────────────────────────────────────────────────────────┘

  C. Government / international (utils/enhanced_data_sources.py)

  These exist as modules but are NOT yet wired into the main retriever fan-out (see roadmap):

  ┌──────────────────────────────────────────┬──────┬────────────────────┐
  │                  Source                  │ Auth │       Status       │
  ├──────────────────────────────────────────┼──────┼────────────────────┤
  │ ILO NORMLEX (Labor standards violations) │ none │ ⚠️ HTTP 403 lately │
  ├──────────────────────────────────────────┼──────┼────────────────────┤
  │ UN Global Compact                        │ none │ scrape stub        │
  ├──────────────────────────────────────────┼──────┼────────────────────┤
  │ OECD Guidelines (NCP / OECDWATCH)        │ none │ scrape stub        │
  ├──────────────────────────────────────────┼──────┼────────────────────┤
  │ EU Taxonomy                              │ none │ placeholder        │
  ├──────────────────────────────────────────┼──────┼────────────────────┤
  │ UNFCCC Race to Zero                      │ none │ placeholder        │
  ├──────────────────────────────────────────┼──────┼────────────────────┤
  │ Open Apparel Registry                    │ none │ apparel-only       │
  ├──────────────────────────────────────────┼──────┼────────────────────┤
  │ OpenSanctions OFAC matching              │ none │ ✅ working         │
  ├──────────────────────────────────────────┼──────┼────────────────────┤
  │ World Bank Climate Data                  │ none │ ✅ working         │
  └──────────────────────────────────────────┴──────┴────────────────────┘

  D. Report discovery → download → parse (utils/)

  These are not "search" sources but they fetch and parse company-issued PDFs:

  - Report Discovery — 11 parallel DuckDuckGo queries for "<company> sustainability/ESG/annual/CSR/BRSR report pdf"
  - Report Downloader — direct PDF fetch (100MB cap, 30s timeout, 7-day cache)
  - PDF Parser — Camelot for tables, PyPDF2/pdfplumber for text

  E. Indian-market stack (utils/indian_data_sources.py, utils/indian_financial_data.py)

  ┌────────────────────────────────────────┬────────────────────────┐
  │                 Source                 │         Status         │
  ├────────────────────────────────────────┼────────────────────────┤
  │ Economic Times RSS                     │ ✅ working             │
  ├────────────────────────────────────────┼────────────────────────┤
  │ Business Standard RSS                  │ ✅ working             │
  ├────────────────────────────────────────┼────────────────────────┤
  │ LiveMint RSS                           │ ✅ working             │
  ├────────────────────────────────────────┼────────────────────────┤
  │ Moneycontrol RSS                       │ ✅ working             │
  ├────────────────────────────────────────┼────────────────────────┤
  │ NewsData.io (India filter)             │ uses NEWSDATA_KEY      │
  ├────────────────────────────────────────┼────────────────────────┤
  │ Google News India fallback             │ ✅ working             │
  ├────────────────────────────────────────┼────────────────────────┤
  │ Screener.in (financials scrape)        │ partial                │
  ├────────────────────────────────────────┼────────────────────────┤
  │ Yahoo Finance (Indian tickers)         │ partial                │
  ├────────────────────────────────────────┼────────────────────────┤
  │ SEBI (BRSR filings)                    │ stub — not implemented │
  ├────────────────────────────────────────┼────────────────────────┤
  │ MCA (Corporate Affairs registry)       │ stub                   │
  ├────────────────────────────────────────┼────────────────────────┤
  │ CPCB (Pollution Control Board)         │ stub                   │
  ├────────────────────────────────────────┼────────────────────────┤
  │ NGT (National Green Tribunal)          │ stub                   │
  ├────────────────────────────────────────┼────────────────────────┤
  │ CSE (Centre for Science & Environment) │ stub                   │
  ├────────────────────────────────────────┼────────────────────────┤
  │ WRI India                              │ stub                   │
  ├────────────────────────────────────────┼────────────────────────┤
  │ India Environment Portal               │ stub                   │
  └────────────────────────────────────────┴────────────────────────┘

  F. Knowledge graph + historical archive

  ┌─────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────┐
  │                     Source                      │                                  Use                                  │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ Neo4j (local Bolt)                              │ Company knowledge graph (with JSON fallback)                          │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ ChromaDB (peer_comparison_history)              │ Vector similarity over past analyses                                  │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ Wayback Machine (web.archive.org CDX)           │ ✅ working — historical snapshots                                     │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ Archive.today (archive.ph / archive.is)         │ ✅ working — historical snapshots                                     │
  ├─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
  │ Memento Time Travel (timetravel.mementoweb.org) │ ⚠️ DNS dead in this env — circuit breaker now skips after 1st failure │
  └─────────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────┘

  G. Financial-data sources (agents/financial_analyst.py)

  ┌─────────────────────────────────────────┬────────────────────────────┐
  │                 Source                  │            Auth            │
  ├─────────────────────────────────────────┼────────────────────────────┤
  │ yfinance (Yahoo Finance Python wrapper) │ none                       │
  ├─────────────────────────────────────────┼────────────────────────────┤
  │ Alpha Vantage                           │ API key (ALPHAVANTAGE_KEY) │
  ├─────────────────────────────────────────┼────────────────────────────┤
  │ Finnhub                                 │ API key (FINNHUB_KEY)      │
  ├─────────────────────────────────────────┼────────────────────────────┤
  │ Financial Modeling Prep                 │ API key (FMP_API_KEY)      │
  ├─────────────────────────────────────────┼────────────────────────────┤
  │ TheNewsAPI                              │ API key (THENEWSAPI_KEY)   │
  ├─────────────────────────────────────────┼────────────────────────────┤
  │ Mediastack                              │ API key (MEDIASTACK_KEY)   │
  └─────────────────────────────────────────┴────────────────────────────┘

  H. Static reference datasets (data/)

  These aren't fetched live but anchor the analysis:

  - known_cases.py — 20 verified greenwashing regulatory cases (BP, Shell, HSBC, VW, ExxonMobil, JPMorgan, etc.)
  - peer_database.json — sector-grouped peer ESG scores
  - sbti_company_cache.json — SBTi-validated targets (~70 KB)
  - emissions_floors.json — per-sector emissions baselines
  - ground_truth_dataset.csv — 51 labeled cases for calibration

  I. LLM providers (compute, not data — but worth listing)

  ┌─────────────────────────────────┬───────────────────────────────────────────────────────┐
  │            Provider             │                          Use                          │
  ├─────────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Groq (GROQ_API_KEY)             │ Primary — risk_scoring, supervisor, sentiment         │
  ├─────────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Google Gemini (GEMINI_API_KEY)  │ Carbon extraction, report generation, chatbot primary │
  ├─────────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Cerebras (CEREBRAS_API_KEY)     │ Credibility analysis (fastest — 47×/report)           │
  ├─────────────────────────────────┼───────────────────────────────────────────────────────┤
  │ OpenRouter (OPENROUTER_API_KEY) │ Fallback chain across providers                       │
  └─────────────────────────────────┴───────────────────────────────────────────────────────┘

  ---
  Headline count: 16 main retrievers + 2 pillar APIs + 8 government sources + 4 PDF/discovery + 14 India + 5 archive/KG + 6 financial + 4 LLM = ~55 distinct
   integrations, of which ~28 are actively contributing evidence per typical analysis run.