export type ReportData = {
  id: string;
  company: string;
  ticker: string;
  sector: string;
  jurisdiction: string;
  date: string;
  duration: string;
  agentsRun: string;
  esgScore: number;
  rating: string;
  riskLevel: "HIGH" | "MEDIUM" | "LOW";
  pillars: { e: number; s: number; g: number };
  greenwashing: number;
  confidence: number;
  scope1: number;
  scope2: number;
  scope3: number;
  netZeroTarget: string;
  carbonBudgetYears: number;
  ieaGapPct?: number;
  claim: string;
  verdict: "CONTRADICTED" | "SUPPORTED" | "UNVERIFIABLE" | "INCONCLUSIVE";
  summary: string;
  topFindings: { kind: "red" | "amber" | "green"; text: string }[];
  contradictions: { severity: string; claim: string; evidence: string; source: string; impact: string; kind: string }[];
  regulatory: { framework: string; score: number; status: string; gap: string }[];
  regulatoryOverall: number;
  peers: { name: string; ticker: string; esg: number; gw: number; rating: string; marketCap: number; isFocus?: boolean }[];
  evidence: { type: string; domain: string; url: string; year: number; credibility: number; stance: string; excerpt: string; archive: string }[];
  greenwashingData?: any;
  shapDrivers?: { f: string; v: number }[];
  // Real annual reduction rates from the carbon_pathway agent (when present);
  // the trajectory chart uses these to plot actual implied vs required pace.
  requiredAnnualRate?: number;
  companyImpliedRate?: number;
  alignmentStatus?: string;
};

export const SHELL_REPORT: ReportData = {
  id: "shel-2025",
  company: "Shell PLC",
  ticker: "SHEL",
  sector: "Energy",
  jurisdiction: "UK",
  date: "2025-04-18",
  duration: "5m 02s",
  agentsRun: "36 / 36",
  esgScore: 23.6,
  rating: "CCC",
  riskLevel: "HIGH",
  pillars: { e: 35.5, s: 16.1, g: 18.2 },
  greenwashing: 77.2,
  confidence: 65.87,
  scope1: 63_000_000,
  scope2: 6_500_000,
  scope3: 1_100_000_000,
  netZeroTarget: "Operational net zero by 2050",
  carbonBudgetYears: 0.34,
  claim: "Shell is transitioning to clean energy and aims to achieve net zero emissions by 2050",
  verdict: "CONTRADICTED",
  summary: "Strong contradictions between stated 2050 net zero ambition and 2023-2024 operational emissions trajectory. Dutch court ruling represents binding legal precedent.",
  topFindings: [
    { kind: "red", text: "Hague District Court ruling - binding 45% emissions cut by 2030" },
    { kind: "red", text: "Operational Scope 1+2 emissions rose 2.3% YoY in 2023-24" },
    { kind: "amber", text: "Renewables capex declined 12% while ambition restated" },
  ],
  contradictions: [
    {
      severity: "HIGH",
      claim: "Shell aims to achieve net zero emissions by 2050",
      evidence: "Hague District Court ruled (2021) that Shell must cut emissions 45% by 2030 vs 2019 - Shell's current pathway misses by 38pp.",
      source: "Hague District Court | May 2021",
      impact: "Legal precedent",
      kind: "legal",
    },
    {
      severity: "HIGH",
      claim: "Shell is transitioning to clean energy",
      evidence: "Operational Scope 1+2 emissions rose 2.3% YoY in 2023-2024 while renewables capex fell 12%.",
      source: "Shell Annual Report 2024 | p. 142",
      impact: "Material",
      kind: "data",
    },
  ],
  regulatory: [
    { framework: "TCFD", score: 62, status: "PARTIAL", gap: "Scope 3 scenario analysis incomplete" },
    { framework: "FCA Anti-Greenwashing", score: 31, status: "NON-COMPLIANT", gap: "Marketing claims not substantiated" },
    { framework: "SECR", score: 71, status: "COMPLIANT", gap: "Minor methodology inconsistencies" },
    { framework: "GHG Protocol", score: 58, status: "PARTIAL", gap: "Scope 3 category boundary unclear" },
    { framework: "SBTi", score: 22, status: "NON-COMPLIANT", gap: "Targets not 1.5 deg C aligned" },
    { framework: "SFDR", score: 41, status: "PARTIAL", gap: "PAI disclosures incomplete" },
  ],
  regulatoryOverall: 43,
  peers: [
    { name: "Shell PLC", ticker: "SHEL", esg: 23.6, gw: 77, rating: "CCC", marketCap: 200, isFocus: true },
    { name: "BP", ticker: "BP", esg: 28, gw: 72, rating: "CCC", marketCap: 95 },
    { name: "TotalEnergies", ticker: "TTE", esg: 31, gw: 68, rating: "B-", marketCap: 145 },
    { name: "Equinor", ticker: "EQNR", esg: 44, gw: 51, rating: "BB", marketCap: 80 },
    { name: "Repsol", ticker: "REP", esg: 38, gw: 58, rating: "B", marketCap: 18 },
    { name: "Eni", ticker: "ENI", esg: 35, gw: 64, rating: "B", marketCap: 50 },
  ],
  evidence: [
    { type: "Government", domain: "uitspraken.rechtspraak.nl", url: "https://uitspraken.rechtspraak.nl/details?id=ECLI:NL:RBDHA:2021:5337", year: 2021, credibility: 0.98, stance: "CONTRADICTING", excerpt: "Hague District Court orders 45% emissions reduction by 2030.", archive: "verified" },
    { type: "Financial", domain: "shell.com", url: "https://www.shell.com/sustainability/our-climate-target.html", year: 2024, credibility: 0.92, stance: "NEUTRAL", excerpt: "Annual Report 2024 - Energy Transition Strategy section.", archive: "verified" },
    { type: "Academic", domain: "nature.com", url: "https://www.nature.com/articles/s41558-023-01683-8", year: 2024, credibility: 0.95, stance: "CONTRADICTING", excerpt: "Major oil firms' net zero targets lack credible interim milestones.", archive: "verified" },
    { type: "NGO", domain: "carbontracker.org", url: "https://carbontracker.org/reports/", year: 2024, credibility: 0.88, stance: "CONTRADICTING", excerpt: "Shell capex misaligned with 1.5 deg C scenario by 78%.", archive: "verified" },
    { type: "News", domain: "ft.com", url: "https://www.ft.com/companies/energy", year: 2024, credibility: 0.74, stance: "CONTRADICTING", excerpt: "Shell quietly walks back 2035 emissions intensity target.", archive: "unverified" },
    { type: "Government", domain: "fca.org.uk", url: "https://www.fca.org.uk/firms/climate-change-sustainable-finance/anti-greenwashing-rule", year: 2024, credibility: 0.96, stance: "NEUTRAL", excerpt: "Anti-Greenwashing Rule guidance applies from May 2024.", archive: "verified" },
  ],
};

export const JPMC_REPORT: ReportData = {
  id: "jpm-2026",
  company: "JPMorgan Chase & Co.",
  ticker: "JPM",
  sector: "Banking & Financial Services",
  jurisdiction: "UK / US",
  date: "2026-04-20",
  duration: "4m 12s",
  agentsRun: "36 / 36",
  esgScore: 31.4,
  rating: "B-",
  riskLevel: "HIGH",
  pillars: { e: 28.5, s: 38.2, g: 34.1 },
  greenwashing: 68.9,
  confidence: 71.3,
  scope1: 430_000,
  scope2: 210_000,
  scope3: 780_000_000,
  netZeroTarget: "Operational net zero by 2030 / Portfolio net zero by 2050",
  carbonBudgetYears: 1.2,
  claim: "JPMorgan Chase is committed to financing a low-carbon economy and achieving operational net zero by 2030, with $2.5 trillion in sustainable development financing by 2030.",
  verdict: "CONTRADICTED",
  summary: "JPMorgan Chase presents a significant greenwashing risk profile. While the bank's green finance commitments are substantial in absolute dollar terms, its simultaneous position as the world's largest fossil fuel financier creates a material contradiction. The January 2025 withdrawal from the Net-Zero Banking Alliance represents a verifiable rollback of a public commitment. Financed emissions at 780M tCO2e represent 99.9% of total emissions and are declining at 0.8%/yr against an IEA-required 12%/yr - a 15x gap.",
  topFindings: [
    { kind: "red", text: "Withdrew from Net-Zero Banking Alliance - January 2025" },
    { kind: "red", text: "$40.8B fossil fuel financing in 2023 - largest among US banks" },
    { kind: "amber", text: "Financed emissions decline at 0.8%/yr vs 12%/yr required" },
  ],
  contradictions: [
    {
      severity: "HIGH",
      claim: "$2.5T in sustainable development financing by 2030",
      evidence: "JPMC simultaneously provided $40.8B in fossil fuel financing in 2023 - largest fossil fuel financier among US banks for the 7th consecutive year.",
      source: "Banking on Climate Chaos | 2024",
      impact: "Material",
      kind: "data",
    },
    {
      severity: "HIGH",
      claim: "Committed to Paris Agreement alignment",
      evidence: "JPMC withdrew from the Net-Zero Banking Alliance (NZBA) in January 2025, one of 6 major US banks to exit, citing 'legal uncertainty' - a verifiable promise degradation event.",
      source: "Reuters | January 2025 / NZBA records",
      impact: "Promise degradation",
      kind: "legal",
    },
  ],
  regulatory: [
    { framework: "TCFD", score: 51, status: "PARTIAL", gap: "Scope 3 financed emissions methodology inconsistent" },
    { framework: "FCA Anti-Greenwashing", score: 28, status: "NON-COMPLIANT", gap: "$2.5T sustainable figure includes non-green assets" },
    { framework: "SBTi", score: 19, status: "NON-COMPLIANT", gap: "No approved targets for financed emissions" },
    { framework: "GHG Protocol", score: 44, status: "PARTIAL", gap: "Scope 3 Cat 15 (investments) methodology disputed" },
    { framework: "PCAF", score: 58, status: "PARTIAL", gap: "Methodology aligned, scope coverage incomplete" },
    { framework: "SFDR", score: 39, status: "PARTIAL", gap: "PAI disclosures inconsistent across funds" },
  ],
  regulatoryOverall: 38,
  peers: [
    { name: "JPMorgan Chase", ticker: "JPM", esg: 31.4, gw: 69, rating: "B-", marketCap: 540, isFocus: true },
    { name: "HSBC", ticker: "HSBA", esg: 35, gw: 61, rating: "B", marketCap: 160 },
    { name: "Barclays", ticker: "BARC", esg: 29, gw: 71, rating: "CCC", marketCap: 48 },
    { name: "BNP Paribas", ticker: "BNP", esg: 44, gw: 42, rating: "BB", marketCap: 78 },
    { name: "Lloyds", ticker: "LLOY", esg: 51, gw: 31, rating: "BB+", marketCap: 38 },
    { name: "Citigroup", ticker: "C", esg: 33, gw: 64, rating: "B-", marketCap: 130 },
  ],
  evidence: [
    { type: "Financial", domain: "jpmorganchase.com", url: "https://www.jpmorganchase.com/ir/esg", year: 2025, credibility: 0.70, stance: "SUPPORTING", excerpt: "JPMC 2025 ESG Report - Sustainable financing progress narrative.", archive: "verified" },
    { type: "NGO", domain: "bankingonclimatechaos.org", url: "https://www.bankingonclimatechaos.org/", year: 2024, credibility: 0.88, stance: "CONTRADICTING", excerpt: "JPMC remains largest US fossil fuel financier - $40.8B in 2023.", archive: "verified" },
    { type: "News", domain: "reuters.com", url: "https://www.reuters.com/sustainability/jpmorgan-quits-net-zero-banking-alliance-2025-01-07/", year: 2025, credibility: 0.91, stance: "CONTRADICTING", excerpt: "JPMorgan withdraws from Net-Zero Banking Alliance - January 2025.", archive: "verified" },
    { type: "Academic", domain: "iea.org", url: "https://www.iea.org/reports/net-zero-by-2050", year: 2024, credibility: 0.95, stance: "NEUTRAL", excerpt: "IEA Net Zero by 2050 - financed emissions trajectory benchmark.", archive: "verified" },
    { type: "Financial", domain: "jpmorganchase.com", url: "https://www.jpmorganchase.com/ir/annual-report", year: 2024, credibility: 0.72, stance: "SUPPORTING", excerpt: "Annual Report 2024 - Climate strategy section.", archive: "verified" },
    { type: "NGO", domain: "shareaction.org", url: "https://shareaction.org/reports/voting-matters-2024", year: 2024, credibility: 0.82, stance: "CONTRADICTING", excerpt: "ShareAction Voting Matters - JPMC opposed key climate resolutions.", archive: "verified" },
    { type: "Government", domain: "cdp.net", url: "https://www.cdp.net/en/financial-services-disclosure", year: 2024, credibility: 0.87, stance: "NEUTRAL", excerpt: "CDP Financial Services Disclosure - partial alignment noted.", archive: "verified" },
    { type: "Academic", domain: "carbonaccountingfinancials.com", url: "https://carbonaccountingfinancials.com/standard", year: 2024, credibility: 0.90, stance: "NEUTRAL", excerpt: "PCAF Standard - financed emissions accounting methodology.", archive: "verified" },
  ],
};

export const REPORTS: Record<string, ReportData> = {
  shel: SHELL_REPORT,
  jpm: JPMC_REPORT,
};

export const REPORT_LIST = [SHELL_REPORT, JPMC_REPORT];

export const RECENT_ANALYSES = [
  { name: "Shell PLC", ticker: "SHEL", esg: 23.6, e: 35, s: 16, g: 18, risk: "HIGH", summary: "Material contradictions vs net zero 2050 claim." },
  { name: "JPMorgan Chase", ticker: "JPM", esg: 31.4, e: 28, s: 38, g: 34, risk: "HIGH", summary: "NZBA exit Jan 2025; financed emissions trajectory misaligned by 15x." },
  { name: "BP", ticker: "BP", esg: 28, e: 38, s: 22, g: 24, risk: "HIGH", summary: "Net zero target weakened in 2023; capex misaligned." },
  { name: "Unilever", ticker: "ULVR", esg: 71, e: 68, s: 75, g: 70, risk: "LOW", summary: "Robust Scope 3 reporting; some greenhushing detected." },
  { name: "Tesco", ticker: "TSCO", esg: 58, e: 54, s: 62, g: 58, risk: "MEDIUM", summary: "Carbon neutral 2035 claim partially substantiated." },
  { name: "Barclays", ticker: "BARC", esg: 49, e: 41, s: 52, g: 54, risk: "MEDIUM", summary: "Sustainable finance pledge progressing slowly." },
];

export const AGENTS = [
  // Input
  { id: "company_kg", name: "Company KG", layer: "Input" },
  { id: "claim_decomp", name: "Claim Decomposition", layer: "Input" },
  { id: "report_disc", name: "Report Discovery", layer: "Input" },
  // Data
  { id: "downloader", name: "Report Downloader", layer: "Data" },
  { id: "parser", name: "Document Parser", layer: "Data" },
  { id: "carbon_extract", name: "Carbon Extraction", layer: "Data" },
  { id: "evidence_retr", name: "Evidence Retrieval", layer: "Data" },
  { id: "archive_retr", name: "Archive Retriever", layer: "Data" },
  { id: "fact_graph", name: "Fact Graph Builder", layer: "Data" },
  // Analysis
  { id: "climatebert", name: "ClimateBERT NLP", layer: "Analysis" },
  { id: "contradiction", name: "Contradiction Analysis", layer: "Analysis" },
  { id: "temporal", name: "Temporal Consistency", layer: "Analysis" },
  { id: "greenwash", name: "Greenwashing Detection", layer: "Analysis" },
  { id: "regulatory", name: "Regulatory Scanner", layer: "Analysis" },
  { id: "credibility", name: "Credibility Analysis", layer: "Analysis" },
  { id: "sentiment", name: "Sentiment Analysis", layer: "Analysis" },
  { id: "peer", name: "Peer Comparison", layer: "Analysis" },
  { id: "linguistic", name: "Linguistic Risk", layer: "Analysis" },
  { id: "selective", name: "Selective Disclosure", layer: "Analysis" },
  { id: "tunnel", name: "Carbon Tunnel Vision", layer: "Analysis" },
  { id: "greenhush", name: "Greenhushing", layer: "Analysis" },
  { id: "supply", name: "Supply Chain", layer: "Analysis" },
  // ML
  { id: "xgb", name: "XGBoost Risk Model", layer: "ML" },
  { id: "lgbm", name: "LightGBM Validator", layer: "ML" },
  { id: "lstm", name: "LSTM Forecaster", layer: "ML" },
  { id: "anomaly", name: "Anomaly Detector", layer: "ML" },
  { id: "iforest", name: "Isolation Forest", layer: "ML" },
  { id: "transformer", name: "Transformer Embeddings", layer: "ML" },
  // Output
  { id: "shap", name: "SHAP Explainability", layer: "Output" },
  { id: "adversarial", name: "Adversarial Audit", layer: "Output" },
  { id: "verdict", name: "Verdict Generation", layer: "Output" },
  { id: "report_build", name: "Report Builder", layer: "Output" },
  { id: "risk_score", name: "Risk Scoring", layer: "Output" },
  { id: "pillar_calc", name: "Pillar Calculation", layer: "Output" },
  { id: "rating_calc", name: "Rating Assignment", layer: "Output" },
  { id: "confidence", name: "Confidence Scoring", layer: "Output" },
];
