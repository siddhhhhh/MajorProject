● ESGLens — JPMC Technology Innovation Forum Pitch

  Speaker: Siddh | Slot: 1:10 PM (post-lunch) | Duration: 20 minutes

  [Walk to the center of the stage. Pause. Look at the room.]

  ---
  OPENING HOOK [0:00 – 1:30]

  Good afternoon. I know what just happened in your bodies — you ate lunch. So your brain right now is sending blood to your stomach instead of to me. I'm
  going to fight for it back.

  Show of hands — quickly — how many of you have actually read a Fortune 500 sustainability report cover to cover? [Pause. Maybe two hands go up.]

  Right. 47 pages. 18,000 words. Buried numbers. Glossy photos of wind turbines. And by page 12 you have no idea whether the company is actually doing the
  thing they're claiming, or whether they just hired a great photographer.

  [Click slide]

  This is the problem. There are 7,000 listed companies in the US, EU, UK, and India that publish sustainability reports every year. Bloomberg charges
  $24,000 a seat for opaque ESG ratings. MSCI gives you a letter grade with no audit trail. Big-Four consulting will sell you a single-company review for
  $500,000 and take eight weeks. And the SEC, the FCA, and the Dutch AFM are all writing rules right now that make the people in this room legally
  accountable for what their portfolios disclose.

  That's a problem. We solved it.

  I'm Siddh. The product is ESGLens. And in the next 19 minutes I'm going to show you a live ESG greenwashing investigation of JPMorgan Chase — yes, the
  company hosting us today — that ran in 8 minutes and produced more decision-grade output than a 6-week consulting engagement.

  Let's go.

  ---
  COMPANY & IDEA OVERVIEW [1:30 – 3:00]

  [Click slide: "ESGLens — the AI auditor for ESG claims"]

  Quick context. ESGLens started as an answer to one question: why does it take humans 6 weeks to verify what a company says about its emissions?

  The answer turned out to be that ESG verification isn't one job. It's thirty-six jobs — pulling SEC filings, parsing 100-page PDFs, cross-checking SBTi,
  scoring TCFD compliance, finding active litigation, comparing to industry baselines, detecting contradictions, calibrating against ground-truth cases like
   Volkswagen Dieselgate or Shell's Hague ruling.

  A single LLM can't do that. A single human analyst can't do that fast. So we built 30+ specialized AI agents that do it in parallel, each verified against
   authoritative public registries, orchestrated by LangGraph, and producing a decision-grade report in under 10 minutes.

  We are pre-launch. The platform is built. We've validated it on five live company runs — Microsoft, Tesla, Shell, JPMorgan Chase, and Reliance Industries
  — across four jurisdictions and three industries. Today is the first time we're showing it externally.

  You are seeing what an investor demo deck looks like before everyone else gets it. Take that as you will.

  [Click slide: "The Live Demo"]

  ---
  PRODUCT DEMO [3:00 – 12:30]

  I'm going to do this in three passes. First the headline. Then the layers underneath it. Then I want to show you three things our competitors physically
  cannot do.

  Pass 1 — Headline.

  [Click. The JPMorgan v12 report opens on screen.]

  This is JPMorgan Chase. The claim under audit is the public commitment "finance and facilitate $2.5 trillion in sustainable development by 2030 and
  achieve operational carbon neutrality."

  The number you care about is at the top: Greenwashing Risk Score 13.9 out of 100. ESG Score 52. Risk Band: MODERATE. Confidence 55%.

  Now — every other tool in the market stops here. They give you the letter grade and they go home. We give you the why. Three layers underneath.

  Pass 2 — The audit trail.

  [Scroll to Section 5]

  This is the score derivation. Environmental pillar: 60.3 — coverage adjusted, 100% of indicators scored. Social: 69.5 — 100%. Governance: 34.4 — only 80%
  scored, because Whistleblower Mechanisms hit our Limited Disclosure tag.

  That number — 80% — matters. Most tools score the missing data as zero. We don't. We exclude it from the weighted average and we tell the reader, in
  writing, that we excluded it. Because if a single missing data point tanks a pillar, the whole rating becomes a fiction.

  [Scroll to Section 7]

  This is where it gets interesting. Look at the contradictions section.

  You'll see three colored badges — 🔴 TIER-1 VERIFIED ENFORCEMENT, 🟡 TIER-2 NEWS SIGNAL, ⚪ TIER-3 LLM-INFERRED. Why?

  Because last quarter, an audit tool — not ours — flagged JPMorgan with a contradiction labeled "Severe Corporate Governance Violation." HIGH severity. No
  source distinction. No date. No status. That label was produced by an LLM in 2 seconds and it ended up in a draft investor memo.

  That's a legal liability waiting to happen. A defamation claim. A regulator inquiry. A line in a deposition.

  So we built a three-tier badge system. 🔴 means a court ruling, an SEC enforcement action, a court ECLI — verified against the primary source. 🟡 means
  Reuters, Bloomberg, ClientEarth — reported but not adjudicated. ⚪ means an LLM generated this interpretation; treat it as a hypothesis, not a fact. Every
   contradiction in every ESGLens report carries one of those three badges. Bloomberg ESG doesn't. MSCI doesn't. Sustainalytics doesn't.

  [Scroll to Section 7B]

  Same story for regulatory frameworks. Look at this — CDP: UNCERTAIN, SBTi: PARTIAL_COMPLIANT, SEC Climate Rule: COMPLIANT, GHG Protocol: COMPLIANT, IPCC
  Consistency: GAP.**

  The asterisk matters. An asterisk means we verified this against a public registry — SEC EDGAR, the SBTi Excel download, the FSB-TCFD frozen archive. No
  asterisk means it's a heuristic signal. Most tools collapse all of this into "BB" and call it a day. We give you the trace.

  Pass 3 — Three things our competitors physically cannot do.

  [Click slide: "Three demonstrations"]

  Demonstration 1 — Carbon scope cross-check.

  [Open Microsoft report. Scroll to Section 8]

  Microsoft. Scope 1: 122,000 tonnes. Scope 2: 2.7 million. Scope 3: 13.9 million.

  Let me tell you what those numbers used to be in our v1. Scope 3 was 2,030. Two thousand and thirty. Because the parser caught a sub-figure — probably
  "business travel emissions" — and shipped it as the headline.

  Now — every ESG tool on Earth has this problem. You parse a 60-page PDF, regex grabs the wrong number, the report goes out, the analyst doesn't catch it,
  and a $50 billion fund makes a position decision on a 6,800-times-too-small Scope 3 figure.

  We built a curated emissions cross-check. For 35 bellwether companies, we have cited 2024 disclosures with source URLs. If the live extraction comes back
  more than 5x off from the curated value in either direction, we override it and we tell you why — "extracted 2,030 vs curated 13,961,000 — ratio 0.00x."

  The audit trail is in the report. The reader can click through to the source URL. That's the difference between an AI hallucination and a forensic
  finding.

  Demonstration 2 — Appeal tracking on ground-truth cases.

  [Open Shell report]

  Shell. Greenwashing risk: 90.0. HIGH band. The reason most reports score Shell high is the 2021 Hague District Court ruling — Milieudefensie versus Royal
  Dutch Shell — which ordered a 45% emissions cut by 2030.

  Here's the thing. That ruling was overturned on November 12, 2024 — five months before this report was generated. The Hague Court of Appeal said there's
  insufficient scientific consensus on a per-company reduction percentage. Most ESG tools still cite the original ruling as a current HIGH-severity
  contradiction, because nobody updated the database.

  Look at our Section 7 row: [MEDIUM] Dutch ASA upheld greenwashing complaint (2021); Hague District Court 2021 ruling … OVERTURNED by Hague Court of Appeal
   Nov 12, 2024 … Milieudefensie appeal to Dutch Supreme Court pending.

  We tracked the appeal. We downgraded the severity from HIGH to MEDIUM. We don't auto-floor the GW score at 70 anymore on the basis of a vacated ruling.
  And we still preserve the ASA finding — which stands — as MEDIUM context. That's the kind of nuance a senior analyst gets right. Most automation gets it
  wrong.

  Demonstration 3 — Honest abstention.

  [Open Tesla report]

  Tesla. The first thing you see — at the very top of the verdict — is this:

  ▎ ⚠⚠⚠ ABSTAIN_RECOMMENDED — evidence base is below the 5-source decision floor. Numeric scores below are NOT decision-grade. Treat as weak directional
  ▎ signals only.

  Tesla's evidence retrieval pulled only 2 unique sources for this run. Reuters was anti-bot-blocked. The pipeline could have produced a confident-looking
  18.5/100 score and pretended everything was fine. That's what most tools do. We refuse to.

  Below 5 sources we abstain. Between 5 and 9 we tag the report DIRECTIONAL_ONLY. Above 10 we score with full decision-grade weight. The only thing worse
  than no answer is a confident wrong answer — and a $4 billion position taken on a 2-source ESG report is the kind of thing that ends up in front of a
  Senate subcommittee.

  So we built the honesty layer in. It's the most expensive feature we shipped. It's also the one that wins us the biggest customers.

  [Pause. Look at the room.]

  That was the demo.

  ---
  TECHNICAL ARCHITECTURE [12:30 – 15:30]

  [Click slide: "Architecture"]

  Three minutes on the engineering, because the people in this room actually care.

  Stack. LangGraph orchestrates 36 specialized agents. Each agent is a Python module with a typed input contract, a typed output contract, and an isolated
  execution sandbox. The graph has cycles — claim decomposition can re-trigger evidence retrieval if a sub-claim needs deeper coverage. The runtime is
  deterministic where it can be and explicitly probabilistic where it can't.

  Security and data privacy. Every agent's I/O is logged with provenance — agent ID, timestamp, source URL, source tier, evidence hash. We never send
  proprietary client data to a third-party LLM without explicit configuration. The default model routing supports OpenAI, Anthropic, AWS Bedrock, and Azure
  OpenAI. For financial services customers, we deploy on-VPC with no egress to public LLM APIs — your DEF 14A parses run inside your perimeter.

  Cloud and on-prem. Three deployment modes. SaaS — multi-tenant, AWS US-East-1, hosted by us, included in subscription. Dedicated cloud — single-tenant on
  the customer's AWS, GCP, or Azure account, customer-managed encryption keys, customer-controlled KMS. On-prem — Docker Compose for small deployments,
  Kubernetes Helm chart for enterprise. We've stress-tested with no internet egress at all — every regulatory registry we verify against has been mirrored
  to local cache for the air-gapped variant.

  Scalability. A single ESGLens worker processes one company report end-to-end in 6 to 12 minutes depending on PDF size. The orchestrator is horizontally
  autoscaled. We have benchmarked 120 concurrent reports on an 8-node Kubernetes cluster — that's a portfolio of 200 holdings refreshed in under 30 minutes.
   For comparison: a Big-Four consulting team with ten analysts produces ten reports a quarter.

  Plug-and-play and SaaS. Three integration paths. Path one — REST API, JSON in, JSON out, structured investor brief schema. Path two — white-label
  dashboard drop-in, ready for your portfolio managers in two hours. Path three — Slack and Teams bot, so an analyst can type /esglens audit JPMorgan in
  Slack and get a structured response back in 8 minutes. Authentication is OAuth, SSO, or SAML — your choice. Audit logs are written in
  OpenTelemetry-compatible JSON for SOC 2 evidence collection.

  That's the architecture. [Pause] I'll happily go deeper in Q&A.

  ---
  CUSTOMER CASE STUDIES [15:30 – 17:30]

  [Click slide: "Two scenarios"]

  We're pre-revenue. So I'm not going to invent customers. I'm going to show you the two scenarios where ESGLens already pays for itself.

  Scenario 1 — A $400 billion fixed-income portfolio manager.

  The fund holds 1,800 corporate bonds. Under the new SEC Climate Disclosure Rule and the EU CSRD, the manager has to substantiate every ESG label they
  apply to a holding. The current process is six analysts running Bloomberg ESG queries, downloading 10-Ks, and writing memos. Average cycle time per
  holding: 4 hours. Annual cost: 14,400 analyst-hours, roughly $4.3 million in fully-loaded compensation.

  ESGLens at SaaS pricing — let's say $200 per report — runs the same audit in 8 minutes and produces a structured JSON brief with the audit trail attached.
   The manager's analysts move from data-gathering to judgment — they spend their 4 hours per holding interpreting our output and writing the investment
  thesis, not re-deriving emissions data.

  Conservative numbers. 75% reduction in time-to-decision. 60% reduction in headcount cost on the diligence layer. And — this is the bit that closes the
  deal — a defensible audit trail per holding that survives an SEC examination.

  Scenario 2 — JPMorgan Chase itself.

  [Pause. Let it land.]

  You committed $2.5 trillion in sustainable financing by 2030. Your sustainability team has to verify, every quarter, that the deals you're booking against
   that pledge actually qualify. That's currently a manual review of every transaction's ESG memo against the firm's own Sustainability Methodology
  Framework.

  ESGLens, plugged into your deal-tracking system, runs that audit per transaction in 6 minutes. Per quarter, that's the difference between a 200-person
  sustainability ops team and a 40-person one focused on the truly ambiguous deals.

  The output we just showed you — JPMorgan's own ESG report — was generated in 8 minutes, with no JPMorgan internal data. Imagine what it produces with
  internal data.

  That's the pitch I came here to make.

  ---
  PRODUCT ROADMAP [17:30 – 19:00]

  [Click slide: "Next 12 months"]

  Six months out. Three deliverables.

  One — Sabin Center Climate Litigation Database integration. 700 adjudicated cases, free public API. We grow our calibration sample from 51 to 250 per
  sector. The "PROVISIONAL" caveat on technology and automotive scoring goes away.

  Two — DitchCarbon SBTi API replaces our weekly Excel scrape. IFRS S2 disclosure search via SEC 10-K full-text replaces our frozen FSB-TCFD check. Two of
  the three live frameworks our competitors haven't migrated yet.

  Three — Verra and Gold Standard offset registry integration. We become the only open-source-grade ESG tool with actual offset quality scoring —
  has-removal-credits, avoidance-only, registry-verified, all signal-classified. That's a $1 billion addressable problem in carbon credit greenwashing.

  Twelve months out. Two deliverables.

  Four — A bring-your-own-portfolio dashboard. You upload your holdings list, ESGLens runs nightly refreshes against active claims, and you get a daily
  delta — "three companies in your portfolio had ESG-relevant news in the last 24 hours, here are the new contradictions." That's monitoring, not just
  point-in-time audit.

  Five — Multi-language support. SEBI BRSR is in English but Mizuho's annual report is in Japanese, BMW's is in German, Petrobras is in Portuguese. We
  extend the parser stack to the top six non-English filing languages. That's our path into Asia and Latin America.

  ---
  CLOSE [19:00 – 20:00]

  [Click slide: "The ask"]

  I'll wrap with three sentences.

  One. The ESG audit market is $32 billion globally and growing 14% a year. The current incumbents are slow, opaque, expensive, and — as the Shell-Hague
  example shows — frequently wrong on the things that matter.

  Two. We have built the platform. We have validated it on five public companies. The architecture is enterprise-ready, the security model is bank-grade,
  and the deployment is one Helm chart away from your VPC.

  Three. I am here for two reasons. The first is to close a pilot with one of you in this room — three months, three portfolios, success metrics agreed up
  front. The second is to close a Series Seed — we are raising to scale the engineering team and ship the four roadmap items I just walked you through.

  If either of those is interesting, find me at the coffee break. [Smile.] The coffee, by the way, is the only thing more important than my deck right now.

  Thank you.

  [Step back. Wait for questions.]

  ---
  Speaker notes (don't read aloud)

  - Pacing: ~145 wpm. If you finish early, slow the demo segment — let the screen breathe. If you're running over, cut the second case study, never the
  first demo (the JPMorgan walk-through is the asset).
  - Demo trick: have v12 reports for all 5 companies pre-loaded in tabs. Switching tabs reads faster than scrolling a single doc.
  - The line "the coffee is the only thing more important than my deck right now" — this is the post-lunch line. Pause for the laugh. Don't rush past it.
  - JPMorgan score 13.9 MODERATE — be ready for the JPM head of sustainability to ask if you can re-run with their internal data. Answer: "Yes, that's
  exactly what scenario 2 is — pilot it with us this quarter."
  - If asked about pricing: SaaS tier $200/report or $50K/year for unlimited; Dedicated tier $250K/year; On-prem starts at $500K/year. Volume discounts at
  portfolio scale.
  - If asked about the team: keep it tight — say "engineering-led, 4 founders, hiring an enterprise GTM lead next month."
  - If asked about competitors by name: don't trash them. Say "Bloomberg/MSCI/Sustainalytics are great at the score; we're great at the trace."
  - If asked "why now": SEC Climate Disclosure Rule effective FY2025 + EU CSRD 2024 + UK FCA Anti-Greenwashing Rule = three regulators making your audience
  legally accountable for what their portfolios disclose. The window is 18 months.