/**
 * api.ts
 * -------
 * Unified API client for the ESGLens frontend.
 * All URLs come from import.meta.env — no hardcoded localhost:PORT in components.
 *
 * Backend API is served through the app's proxy or configured origin.
 * Chatbot uses the same proxy pattern.
 */

const BASE_URL = "/api"; // proxied by the app to the backend API
const CHATBOT_URL = "/chatbot"; // proxied by the app to the chatbot API
const WS_BASE = import.meta.env.VITE_WS_URL ?? "";

// ── Analysis ─────────────────────────────────────────────────────────────────

export async function startAnalysis(payload: {
  company: string;
  claim: string;
  industry?: string;
  focus_areas?: string[];
  uploaded_file_ids?: string[];
}): Promise<{ analysis_id: string; status: string }> {
  const res = await fetch(`${BASE_URL}/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Analysis failed: ${res.statusText}`);
  return res.json();
}

export async function getAnalysisStatus(id: string) {
  const res = await fetch(`${BASE_URL}/analysis/${id}`);
  if (!res.ok) throw new Error("Failed to fetch analysis status");
  return res.json();
}

// ── Reports ───────────────────────────────────────────────────────────────────

export async function getAllReports(): Promise<HistoryEntry[]> {
  const res = await fetch(`${BASE_URL}/reports`);
  if (!res.ok) throw new Error("Failed to fetch reports");
  return res.json();
}

export async function getReport(id: string): Promise<ESGReport> {
  const res = await fetch(`${BASE_URL}/reports/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch report ${id}`);
  return res.json();
}

export async function getReportArtifacts(id: string): Promise<ReportArtifacts> {
  const res = await fetch(`${BASE_URL}/reports/${id}/artifacts`);
  if (!res.ok) throw new Error(`Failed to fetch report artifacts ${id}`);
  return res.json();
}

// ── File Upload ───────────────────────────────────────────────────────────────

export async function uploadFile(file: File): Promise<{
  file_id: string;
  filename: string;
  size_bytes: number;
  status: string;
}> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

// ── WebSocket Pipeline Stream ──────────────────────────────────────────────────

export interface LogEntry {
  t: string;
  msg: string;
  kind: "ok" | "warn" | "error" | "info";
}

export function connectPipelineStream(
  analysisId: string,
  onLog: (log: LogEntry) => void,
  onProgress: (pct: number, elapsed: number) => void,
  onComplete: (report: ESGReport) => void,
  onError: (msg: string) => void
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/pipeline/${analysisId}`);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "log") onLog({ t: msg.t, msg: msg.msg, kind: msg.kind });
      else if (msg.type === "progress") onProgress(msg.progress_pct, msg.elapsed_seconds);
      else if (msg.type === "complete") onComplete(msg.report as ESGReport);
      else if (msg.type === "error") onError(msg.message);
      // heartbeat: ignore silently
    } catch {
      // ignore parse errors
    }
  };

  ws.onerror = () => onError("WebSocket connection error");
  return ws;
}

// ── Chatbot ───────────────────────────────────────────────────────────────────

export async function sendChatMessage(payload: {
  session_id: string;
  question: string;
  provider?: string;
  report_id?: string;
  company?: string;
}): Promise<ChatbotResponse> {
  const res = await fetch(`${CHATBOT_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Chatbot request failed");
  return res.json();
}

export async function sendChatStream(payload: {
  session_id: string;
  question: string;
  provider?: string;
  report_id?: string;
  company?: string;
}): Promise<Response> {
  return fetch(`${CHATBOT_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ── TypeScript Types ──────────────────────────────────────────────────────────

export interface AgentUpdate {
  type: "agent_update";
  agent: string;
  status: "queued" | "running" | "completed" | "error";
  result_summary?: string;
  progress_pct: number;
  elapsed_seconds: number;
  partial_results?: Record<string, unknown>;
}

export interface PillarScore {
  score: number;
  coverage_adjusted_score?: number;
  weight: number;
  positive_signals: number;
  contradictions: number;
}

export interface CarbonData {
  scope1: number;
  scope2: number;
  scope3: number;
  total: number;
  net_zero_target: string;
  data_quality: number;
  iea_nze_gap_pct?: number;
  budget_years_remaining?: number;
  // Real reduction-rate fields from the carbon_pathway agent. When present,
  // the frontend trajectory chart renders the actual rates instead of a
  // hardcoded 12%/yr placeholder.
  required_annual_rate?: number;
  company_implied_rate?: number;
  alignment_status?: string;
  scope2_status?: string;
  scope3_status?: string;
  target_status?: string;
}

export interface GreenwashingData {
  overall_score: number;
  greenwishing_score: number;
  greenhushing_score: number;
  selective_disclosure: boolean;
  temporal_escalation: string;
  carbon_tunnel_vision: boolean;
  linguistic_risk: number;
  gsi_score: number;
  boilerplate_score: number;
  climatebert_relevance: number;
  climatebert_risk: string;
}

export interface Contradiction {
  id: string;
  severity: string;
  claim_text: string;
  evidence_text: string;
  source: string;
  source_url?: string;
  year?: number;
  impact: string;
}

export interface EvidenceItem {
  id: string;
  source_name: string;
  source_url?: string;
  credibility: number;
  stance: string;
  excerpt: string;
  year?: number;
  source_type: string;
  archive_verified: boolean;
}

export interface RegulatoryItem {
  framework: string;
  compliance_score: number;
  status: string;
  jurisdiction: string;
  key_gap: string;
}

export interface RiskDriver {
  name: string;
  impact: string;
  direction: "increases_risk" | "reduces_risk";
  shap_value?: number;
}

export interface ESGReport {
  id: string;
  company: string;
  ticker: string;
  sector: string;
  claim: string;
  analysis_date: string;
  esg_score: number;
  rating_grade: string;
  risk_level: string;
  confidence: number;
  environmental: PillarScore;
  social: PillarScore;
  governance: PillarScore;
  carbon: CarbonData;
  greenwashing: GreenwashingData;
  contradictions: Contradiction[];
  evidence: EvidenceItem[];
  regulatory: RegulatoryItem[];
  agents_total: number;
  agents_successful: number;
  pipeline_duration_seconds: number;
  ai_verdict: string;
  executive_summary: string;
  top_risk_drivers: RiskDriver[];
  temporal_score: number;
  temporal_risk: string;
  claim_trend: string;
  environmental_trend: string;
  contradiction_flag?: boolean;
  validation_notes?: string[];

  // ── New fields surfaced from the v4 pipeline ─────────────────────────
  // Honest quality warnings (calibration limitations, missing scope data, etc.).
  quality_warnings?: string[];
  // Per-agent model provenance, e.g. {"agent.supervisor": "groq:llama-3.3-70b-versatile"}.
  model_versions?: Record<string, unknown>;
  // Calibration block — includes pipeline_spearman_r (null until benchmarked)
  // and linguistic_stub_spearman_r (the actual measured correlation).
  calibration?: {
    spearman_r?: number;
    linguistic_stub_spearman_r?: number | null;
    pipeline_spearman_r?: number | null;
    calibration_methodology?: string;
    optimal_threshold?: number;
    dataset_size?: number;
    calibration_status?: string;
    [key: string]: unknown;
  };
  // KG year-over-year drift signals from prior runs.
  kg_drift?: {
    available?: boolean;
    signal_count?: number;
    signals?: Array<{
      metric_name: string;
      current_value: number;
      prior_value: number;
      prior_run_ts?: string;
      delta_abs?: number;
      delta_pct?: number;
      direction: "improved" | "worsened" | "stable" | "no_history";
      lower_is_better?: boolean;
    }>;
  };
  // Fact-graph motif diagnostics: pillar coverage skew, contradiction density.
  fact_graph_motifs?: {
    pillar_coverage?: Record<string, number>;
    pillar_coverage_skew?: number;
    contradiction_density?: number;
    graph_density?: number;
    is_decision_ready?: boolean;
  };
  // Per-retriever yield tally — names silent-failure retrievers.
  retriever_tally?: Record<string, number>;
}

export interface ReportArtifacts {
  txt?: string | null;
  brief?: Record<string, unknown> | null;
  full_json?: Record<string, unknown> | null;
  files?: {
    txt?: string | null;
    brief?: string | null;
    json?: string | null;
  };
}

export interface HistoryEntry {
  id: string;
  company: string;
  ticker: string;
  sector: string;
  risk_level: string;
  esg_score: number;
  rating_grade: string;
  greenwashing_risk: number;
  confidence: number;
  analysis_date: string;
  claim: string;
  ai_verdict_short: string;
  contradictions_count: number;
  agents_run: number;
  duration_seconds: number;
}

export interface ChatAnswer {
  answer: string;
  confidence_explanation: string;
  contradictions: string[];
  citations: string[];
  scope: string;
  intent?: string;
}

export interface ChatbotResponse {
  status: string;
  session_id: string;
  answer: ChatAnswer;
  provider_used: string;
}
