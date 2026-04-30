  Two slides. Designed to be left behind after the coffee break.

  ---
  SLIDE 1 — THE OPPORTUNITY

  ESGLens

  The AI auditor for ESG claims. 30+ specialist agents. 8 minutes per company. Audit-grade traceability.

  ---
  The problem we solve

  ESG verification today is broken three ways:
  - Slow — Big-Four reviews take 6 weeks per company, $500K per engagement
  - Opaque — Bloomberg ESG and MSCI give you a letter grade with no audit trail
  - Wrong — competitors still cite Shell's 2021 Hague ruling as active enforcement, five months after it was overturned on appeal

  Meanwhile the SEC Climate Disclosure Rule, EU CSRD, and UK FCA Anti-Greenwashing Rule are making asset managers, banks, and corporates legally accountable
   for what their portfolios disclose. The compliance window is 18 months.

  ---
  What we built

  A multi-agent AI platform that produces a forensic ESG / greenwashing audit in 8 minutes with full source-cited traceability per finding.

  ┌──────────────────────────┬───────────────────────────────────┬─────────────────────┬────────────────────────────────────────────────────┐
  │                          │ Bloomberg / MSCI / Sustainalytics │ Big-Four Consulting │                      ESGLens                       │
  ├──────────────────────────┼───────────────────────────────────┼─────────────────────┼────────────────────────────────────────────────────┤
  │ Time per company         │ Real-time score, no audit         │ 6 weeks             │ 8 minutes                                          │
  ├──────────────────────────┼───────────────────────────────────┼─────────────────────┼────────────────────────────────────────────────────┤
  │ Cost per company         │ $24K/seat/year                    │ $500K               │ $200 — $50K all-you-can-eat                        │
  ├──────────────────────────┼───────────────────────────────────┼─────────────────────┼────────────────────────────────────────────────────┤
  │ Audit trail              │ None                              │ Manual memo         │ Per-agent provenance, source URLs, evidence hashes │
  ├──────────────────────────┼───────────────────────────────────┼─────────────────────┼────────────────────────────────────────────────────┤
  │ Multi-jurisdiction       │ US-centric                        │ Manual per region   │ US + EU + UK + India + Netherlands, 11 frameworks  │
  ├──────────────────────────┼───────────────────────────────────┼─────────────────────┼────────────────────────────────────────────────────┤
  │ Three-tier source labels │ No                                │ No                  │ Yes — registry / news / LLM-inferred badges        │
  ├──────────────────────────┼───────────────────────────────────┼─────────────────────┼────────────────────────────────────────────────────┤
  │ Honest abstention        │ No                                │ N/A                 │ Refuses to score below 5 sources                   │
  ├──────────────────────────┼───────────────────────────────────┼─────────────────────┼────────────────────────────────────────────────────┤
  │ Self-hosting             │ No                                │ N/A                 │ Air-gapped on-prem available                       │
  └──────────────────────────┴───────────────────────────────────┴─────────────────────┴────────────────────────────────────────────────────┘

  ---
  Validation (pre-launch)

  5 production reports generated across 4 jurisdictions and 3 industries. Real findings:
  - Microsoft — GW 10.1, ESG 65.3 — caught SBTi net-zero commitment removal (March 2024) flagged as PARTIAL_COMPLIANT, not clean COMPLIANT
  - Tesla — ABSTAIN_RECOMMENDED banner fired automatically when evidence retrieval returned only 2 sources
  - Shell — GW 90.0 HIGH — Hague Court of Appeal Nov 2024 reversal correctly tracked, severity downgraded HIGH→MEDIUM
  - JPMorgan Chase — GW 13.9 MODERATE — proxy statement parsed via SEC EDGAR DEF 14A, structured pay ratio + board diversity surfaced
  - Reliance Industries — India BRSR routing landed correctly, Camelot 100-page guard prevented OOM crash on 146-page sustainability PDF

  ---
  SLIDE 2 — THE ASK

  Market

  $32B global ESG audit market, 14% CAGR. Three regulatory tailwinds (SEC, CSRD, FCA) compress the buyer decision cycle from "should we" to "we have 18
  months." Initial wedge: $8B fixed-income and equity asset-management ESG-diligence segment.

  ---
  Traction & roadmap (next 12 months)

  Engineering — shipped:
  - 36-agent LangGraph orchestrator
  - SEC EDGAR DEF 14A live parser (board independence, pay ratio, diversity, anti-corruption)
  - Curated emissions cross-check (35 bellwether companies with cited 2024 disclosures)
  - Three-tier contradiction badges (verified / news / LLM-inferred)
  - Geography-aware jurisdiction routing (US/EU/UK/IN/NL)
  - Min-source floor with ABSTAIN / DIRECTIONAL_ONLY tiers
  - Investor-brief JSON output schema
  - Appeal-aware ground-truth registry

  Next 6 months:
  - Sabin Center Climate Litigation DB integration (700 adjudicated cases) → calibration sample 51 → 250 per sector
  - DitchCarbon SBTi API + IFRS S2 disclosure search (replaces frozen FSB-TCFD check)
  - Verra + Gold Standard offset registry integration → first open ESG tool with offset-quality scoring

  6–12 months:
  - Bring-your-own-portfolio nightly delta dashboard
  - Multi-language parser stack (DE, JA, PT, FR, ES, ZH)
  - SOC 2 Type II
  - Two paid enterprise pilots → $2M ARR target

  ---
  Why we win

  1. Architectural moat: 36 specialist agents with isolated I/O contracts beat a single LLM black box on traceability — and traceability is what regulators
  audit.
  2. Trust moat: the abstention layer and three-tier badges make us the only platform that refuses to produce a confident wrong answer. That's the feature
  that wins financial-services contracts.
  3. Speed-to-deploy: REST API, white-label dashboard, or Slack/Teams bot — three integration paths, two-hour onboarding.
  4. Deployment optionality: SaaS, dedicated cloud, on-prem air-gapped. Bank-grade.

  ---
  The round

  ┌────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │            │                                                                                                                                        │
  ├────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Stage      │ Seed                                                                                                                                   │
  ├────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Raise      │ $2.5M                                                                                                                                  │
  ├────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Use of     │ 60% engineering (4 hires: 2 ML, 1 platform, 1 GTM enterprise lead) · 25% data partnerships (Sabin, Verra, Gold Standard, DitchCarbon)  │
  │ funds      │ · 15% SOC 2 + customer pilots                                                                                                          │
  ├────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Runway     │ 18 months to $2M ARR                                                                                                                   │
  ├────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Lead check │ $1M, allocations from $100K                                                                                                            │
  └────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  The ask

  Pilot — three months, three portfolios, success metrics agreed up front. We co-design the success metric: cycle time, accuracy vs your in-house diligence,
   regulator-defensibility of the audit trail. Convert to annual contract on hit.

  Investment — Seed round closing this quarter. Looking for one strategic from financial services, one institutional ESG-tech specialist, one technical-AI
  lead.

  ---
  Contact
  Siddh — Founder, ESGLens
  Pitch deck, sample reports, sandbox access available on request.

  ---
  Footer footnote (small print, bottom of slide 2)

  ▎ Sample reports for Microsoft, Tesla, Shell, JPMorgan Chase, and Reliance Industries available under NDA. All findings traceable to public sources; no
  ▎ client data used in pre-launch validation. ESGLens is not a regulated rating agency; outputs are decision-support, not a substitute for fiduciary
  ▎ judgment.

  ---
  Layout notes for the deck designer:
  - Slide 1 is the table-driven competitive comparison + the 5-company validation strip. Heavy on numbers, light on words. The table is the centerpiece.
  - Slide 2 is the round + the roadmap + the ask. Use the green-yellow-grey roadmap timeline visual.
  - Both slides on JPMC-event-appropriate stationery — don't over-design. The product is the deck; the deck is just paper.
  - Bring 50 printed copies. Hand them out personally at the coffee break — it forces a 30-second conversation per copy.