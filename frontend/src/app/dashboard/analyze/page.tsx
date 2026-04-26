"use client";

import { useMemo, useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BrainCircuit, CheckCircle2, Download, Loader2, RefreshCw, TerminalSquare,
  AlertTriangle, Shield, Leaf, Users, BarChart3, Zap, FileText, Activity,
  TrendingDown, TrendingUp, ChevronDown, ChevronUp, Info
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { type AnalysisResult, type LogEntry, useAnalysisRun } from "@/components/providers/analysis-run-provider";

type AgentResult = {
  agent: string;
  status?: string;
  confidence?: number | null;
  key_findings?: Record<string, unknown>;
};

type AgentContribution = {
  agent: string;
  status: string;
  confidence: number;
  contributionPct: number;
  keyFindingsCount: number;
};

function badgeClass(level: LogEntry["level"]): string {
  if (level === "error") return "bg-red-100 text-red-700";
  if (level === "warn") return "bg-amber-100 text-amber-700";
  if (level === "success") return "bg-emerald-100 text-emerald-700";
  return "bg-neutral-100 text-neutral-700";
}

function parsePercentText(value?: string): number {
  if (!value) return 0;
  const match = value.match(/(\d+(?:\.\d+)?)/);
  if (!match) return 0;
  return Number(match[1]) / 100;
}

function isUsefulText(value?: string | null): boolean {
  if (!value) return false;
  const normalized = value.trim();
  return !!normalized && !/^n\/?a$/i.test(normalized) && !/^unknown$/i.test(normalized);
}

function getDisplayRisk(results: AnalysisResult): string {
  const risk = results.risk_level;
  if (isUsefulText(risk)) return risk;
  const fallback = results.parsed_main_report?.riskBand;
  return isUsefulText(fallback) ? (fallback || "") : "";
}

function getDisplayConfidence(results: AnalysisResult): string {
  const numeric = (results.confidence > 0 ? results.confidence : parsePercentText(results.parsed_main_report?.confidence)) || 0;
  if (numeric > 0) {
    return `${Math.round(numeric * 100)}%`;
  }
  const textFallback = results.parsed_main_report?.reportConfidence;
  return isUsefulText(textFallback) ? (textFallback || "") : "";
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function toObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function titleCaseAgent(agent: string): string {
  return agent
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getRiskColor(risk: string): { bg: string; text: string; border: string; dot: string } {
  const upper = risk.toUpperCase();
  if (upper === "HIGH" || upper === "CCC" || upper === "B") {
    return { bg: "bg-red-50", text: "text-red-700", border: "border-red-200", dot: "bg-red-500" };
  }
  if (upper === "MODERATE" || upper === "LOW-MODERATE" || upper === "BB" || upper === "BBB") {
    return { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200", dot: "bg-amber-500" };
  }
  if (upper === "LOW" || upper === "AA" || upper === "AAA") {
    return { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200", dot: "bg-emerald-500" };
  }
  return { bg: "bg-neutral-50", text: "text-neutral-700", border: "border-neutral-200", dot: "bg-neutral-400" };
}

function PillarGauge({ label, score, icon, color }: { label: string; score: string | null | undefined; icon: React.ReactNode; color: string }) {
  const numScore = score ? parseFloat(score) : null;
  const pct = numScore !== null ? Math.min(100, Math.max(0, numScore)) : null;

  const getScoreColor = (s: number) => {
    if (s >= 60) return "text-emerald-600";
    if (s >= 30) return "text-amber-600";
    return "text-red-600";
  };

  const getBarColor = (s: number) => {
    if (s >= 60) return color || "bg-emerald-500";
    if (s >= 30) return "bg-amber-500";
    return "bg-red-500";
  };

  return (
    <div className="flex flex-col gap-2 p-4 rounded-xl border border-neutral-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${pct !== null && pct >= 60 ? "bg-emerald-100" : pct !== null && pct >= 30 ? "bg-amber-100" : "bg-red-100"}`}>
          {icon}
        </div>
        <span className="text-sm font-semibold text-neutral-700">{label}</span>
      </div>
      {pct !== null ? (
        <>
          <div className={`text-3xl font-bold tabular-nums ${getScoreColor(pct)}`}>
            {pct.toFixed(1)}<span className="text-lg font-normal text-neutral-400">/100</span>
          </div>
          <div className="h-2 w-full rounded-full bg-neutral-100 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 1, ease: "easeOut" }}
              className={`h-full rounded-full ${getBarColor(pct)}`}
            />
          </div>
          <div className="text-xs text-neutral-500">
            {pct >= 60 ? "Good" : pct >= 30 ? "Moderate" : "Needs Improvement"}
          </div>
        </>
      ) : (
        <div className="text-sm text-neutral-400 italic">Insufficient data</div>
      )}
    </div>
  );
}

function RiskBadge({ risk }: { risk: string }) {
  const colors = getRiskColor(risk);
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-bold ${colors.bg} ${colors.text} border ${colors.border}`}>
      <span className={`w-2 h-2 rounded-full ${colors.dot}`} />
      {risk} RISK
    </span>
  );
}

function MetricCard({ label, value, sub, icon }: { label: string; value: string; sub?: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs font-medium text-neutral-500 uppercase tracking-wide">{label}</div>
        {icon && <div className="text-neutral-400">{icon}</div>}
      </div>
      <div className="text-2xl font-bold text-neutral-900 mt-1 tabular-nums">{value}</div>
      {sub && <div className="text-xs text-neutral-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function getAgentResults(results: AnalysisResult | null): AgentResult[] {
  if (!results?.json_report) return [];
  const reportObj = toObject(results.json_report);
  const raw = reportObj.agent_results ?? reportObj.agent_outputs;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      const row = toObject(item);
      const agent = String(row.agent || "").trim();
      if (!agent) return null;
      return {
        agent,
        status: String(row.status || "UNKNOWN"),
        confidence: toNumber(row.confidence),
        key_findings: toObject(row.key_findings),
      } as AgentResult;
    })
    .filter((item): item is AgentResult => item !== null);
}

function toAgentContributions(agentResults: AgentResult[]): AgentContribution[] {
  const withConfidence = agentResults.map((item) => ({
    ...item,
    confidence: item.confidence ?? 0,
  }));
  const total = withConfidence.reduce((sum, item) => sum + Math.max(0, item.confidence || 0), 0);
  return withConfidence
    .map((item) => ({
      agent: item.agent,
      status: item.status || "UNKNOWN",
      confidence: Math.max(0, item.confidence || 0),
      contributionPct: total > 0 ? (Math.max(0, item.confidence || 0) / total) * 100 : 0,
      keyFindingsCount: Object.keys(item.key_findings || {}).length,
    }))
    .sort((a, b) => b.contributionPct - a.contributionPct);
}

export default function AnalyzePage() {
  const [company, setCompany] = useState("Unilever");
  const [claim, setClaim] = useState("Unilever aims to achieve net-zero emissions across its value chain by 2039.");
  const [industry, setIndustry] = useState(() => {
    if (typeof window === "undefined") return "Consumer Goods";
    return window.localStorage.getItem("esg-default-industry") || "Consumer Goods";
  });
  const [showAgents, setShowAgents] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const { appState, logs, results, runStatusLabel, startAnalysis, resetRun } = useAnalysisRun();

  const agentResults = useMemo(() => getAgentResults(results), [results]);
  const agentContributions = useMemo(() => toAgentContributions(agentResults), [agentResults]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const downloadFile = (name?: string) => {
    if (!name) return;
    window.open(`/api/reports/download?name=${encodeURIComponent(name)}`, "_blank");
  };

  const downloadPdf = (name?: string) => {
    if (!name) return;
    window.open(`/api/reports/pdf?name=${encodeURIComponent(name)}`, "_blank");
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    await startAnalysis({ company, claim, industry });
  };

  const riskDisplay = results ? getDisplayRisk(results) : "";
  const confidenceDisplay = results ? getDisplayConfidence(results) : "";
  const riskColors = riskDisplay ? getRiskColor(riskDisplay) : null;
  const report = results?.parsed_main_report;

  return (
    <div className="space-y-6 pb-12">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-2xl font-bold font-heading text-neutral-900 tracking-tight">ESG Claim Analysis</h2>
        <p className="text-neutral-500 text-sm mt-1">Submit a company and ESG claim to trigger the multi-agent LangGraph analysis pipeline.</p>
      </motion.div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Input Panel */}
        <div className="xl:col-span-4 space-y-4">
          <Card className="border-neutral-200 bg-white shadow-sm">
            <CardHeader>
              <CardTitle>Analysis Input</CardTitle>
              <CardDescription>Configure and launch the ESG analysis pipeline.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleAnalyze} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="company">Company Name</Label>
                  <Input id="company" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="e.g. Shell, Unilever, Microsoft" required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="industry">Industry</Label>
                  <Input id="industry" value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="e.g. Energy, Technology" required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="claim">ESG Claim</Label>
                  <textarea
                    id="claim"
                    value={claim}
                    onChange={(e) => setClaim(e.target.value)}
                    required
                    rows={5}
                    className="flex w-full rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all resize-none"
                    placeholder="Enter the ESG claim to verify..."
                  />
                </div>
                <Button type="submit" className="w-full" disabled={appState === "processing"}>
                  {appState === "processing" ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Running Pipeline...</>
                  ) : (
                    <><BrainCircuit className="w-4 h-4 mr-2" /> Run ESG Analysis</>
                  )}
                </Button>
                {appState === "results" && (
                  <Button type="button" variant="outline" className="w-full" onClick={resetRun}>
                    <RefreshCw className="w-4 h-4 mr-2" /> New Analysis
                  </Button>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Pipeline status */}
          {(appState === "processing" || logs.length > 0) && (
            <Card className="border-neutral-200 bg-white shadow-sm">
              <CardHeader className="pb-2 border-b border-neutral-100">
                <div className="flex items-center justify-between gap-3">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <TerminalSquare className="w-4 h-4 text-primary-700" /> Live Pipeline Log
                  </CardTitle>
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-md ${appState === "processing" ? "text-blue-700 bg-blue-50" : appState === "results" ? "text-emerald-700 bg-emerald-50" : "text-neutral-600 bg-neutral-100"}`}>
                    {runStatusLabel}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="p-3">
                <div className="h-[220px] overflow-auto rounded-lg border border-neutral-200 bg-neutral-950 text-neutral-100 p-3 space-y-1.5 font-mono text-[11px]">
                  {!logs.length && <div className="text-neutral-400">Waiting for pipeline events...</div>}
                  {logs.map((log, idx) => (
                    <div key={`${log.ts}-${idx}`} className="flex gap-2 items-start leading-relaxed">
                      <span className={`flex-shrink-0 px-1.5 py-0.5 rounded uppercase tracking-wide text-[9px] font-bold ${badgeClass(log.level)}`}>
                        {log.level}
                      </span>
                      <span className="text-neutral-300/70 flex-shrink-0">{new Date(log.ts).toLocaleTimeString()}</span>
                      <span className="break-words text-neutral-100">{log.message}</span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Results Panel */}
        <div className="xl:col-span-8 space-y-6">
          <AnimatePresence>
            {results && (
              <motion.div
                key="results"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                className="space-y-6"
              >
                {/* Header Card */}
                <Card className={`border-2 shadow-md ${riskColors ? riskColors.border : "border-neutral-200"}`}>
                  <CardContent className="p-6">
                    <div className="flex flex-col md:flex-row md:items-start gap-4 justify-between">
                      <div className="space-y-2">
                        <div className="flex items-center gap-3 flex-wrap">
                          <h3 className="text-xl font-bold text-neutral-900">{results.company_name}</h3>
                          {riskDisplay && <RiskBadge risk={riskDisplay} />}
                          {report?.esgRating && isUsefulText(report.esgRating) && (
                            <span className="text-sm font-bold text-neutral-700 bg-neutral-100 px-2.5 py-1 rounded-full">
                              ESG Rating: {report.esgRating}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-neutral-500 max-w-xl line-clamp-2">{results.claim}</p>
                        <div className="flex items-center gap-4 text-sm text-neutral-600 flex-wrap">
                          {results.industry && <span className="flex items-center gap-1"><Activity className="w-3.5 h-3.5" />{results.industry}</span>}
                          {confidenceDisplay && <span className="flex items-center gap-1"><Shield className="w-3.5 h-3.5" />Confidence: {confidenceDisplay}</span>}
                          {report?.riskScore && isUsefulText(report.riskScore) && (
                            <span className="flex items-center gap-1 font-semibold text-red-600"><AlertTriangle className="w-3.5 h-3.5" />Risk Score: {report.riskScore}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2 flex-wrap">
                        <Button variant="outline" size="sm" onClick={() => downloadFile(results.report_file_name)}>
                          <Download className="w-4 h-4 mr-1.5" /> TXT
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => downloadPdf(results.report_file_name)}>
                          <FileText className="w-4 h-4 mr-1.5" /> PDF
                        </Button>
                      </div>
                    </div>

                    {/* Executive Summary */}
                    {(report?.executiveSummary || results.summary) && (
                      <div className={`mt-4 p-4 rounded-lg border ${riskColors ? riskColors.bg + " " + riskColors.border : "bg-neutral-50 border-neutral-200"}`}>
                        <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500 mb-1">Executive Summary</div>
                        <p className="text-sm text-neutral-800 leading-relaxed">{report?.executiveSummary || results.summary}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* E/S/G Pillar Scores */}
                <div>
                  <h4 className="text-sm font-semibold text-neutral-700 uppercase tracking-wide mb-3 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4" /> ESG Pillar Scores
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <PillarGauge
                      label="Environmental"
                      score={report?.environmentalScore}
                      icon={<Leaf className="w-4 h-4 text-emerald-600" />}
                      color="bg-emerald-500"
                    />
                    <PillarGauge
                      label="Social"
                      score={report?.socialScore}
                      icon={<Users className="w-4 h-4 text-blue-600" />}
                      color="bg-blue-500"
                    />
                    <PillarGauge
                      label="Governance"
                      score={report?.governanceScore}
                      icon={<Shield className="w-4 h-4 text-purple-600" />}
                      color="bg-purple-500"
                    />
                  </div>
                  {!report?.environmentalScore && !report?.socialScore && !report?.governanceScore && (
                    <p className="text-xs text-neutral-400 mt-2 italic">Pillar scores will appear after the pipeline completes with scoring data.</p>
                  )}
                </div>

                {/* Key Metrics Row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <MetricCard
                    label="Evidence Sources"
                    value={report?.evidenceCount || String(results.json_report ? Object.keys(results.json_report).length : "—")}
                    sub="Total citations"
                    icon={<FileText className="w-4 h-4" />}
                  />
                  <MetricCard
                    label="Contradictions"
                    value={report?.contradictionsFound || "0"}
                    sub="Legal findings"
                    icon={<AlertTriangle className="w-4 h-4 text-red-500" />}
                  />
                  <MetricCard
                    label="Deception Risk"
                    value={report?.deceptionRisk || "—"}
                    sub="Overall score"
                    icon={<TrendingDown className="w-4 h-4 text-amber-500" />}
                  />
                  <MetricCard
                    label="Compliance Score"
                    value={report?.complianceScore ? `${report.complianceScore}/100` : "—"}
                    sub={report?.complianceGaps ? `${report.complianceGaps} gaps found` : "Regulatory"}
                    icon={<CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                  />
                </div>

                {/* Carbon & Climate Section */}
                {(report?.scope1 || report?.scope2 || report?.scope3 || report?.netZeroTarget) && (
                  <Card className="border-neutral-200 bg-white shadow-sm">
                    <CardHeader className="pb-3 border-b border-neutral-100">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Leaf className="w-4 h-4 text-emerald-600" /> Carbon & Climate Data
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-4">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {report?.scope1 && (
                          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3">
                            <div className="text-xs font-semibold text-emerald-700 uppercase tracking-wide">Scope 1 Emissions</div>
                            <div className="text-lg font-bold text-emerald-800 mt-1">{report.scope1}</div>
                            <div className="text-xs text-emerald-600">Direct GHG emissions</div>
                          </div>
                        )}
                        {report?.scope2 && (
                          <div className="rounded-lg bg-blue-50 border border-blue-200 p-3">
                            <div className="text-xs font-semibold text-blue-700 uppercase tracking-wide">Scope 2 Emissions</div>
                            <div className="text-lg font-bold text-blue-800 mt-1">{report.scope2}</div>
                            <div className="text-xs text-blue-600">Purchased energy emissions</div>
                          </div>
                        )}
                        {report?.scope3 && (
                          <div className="rounded-lg bg-purple-50 border border-purple-200 p-3">
                            <div className="text-xs font-semibold text-purple-700 uppercase tracking-wide">Scope 3 Emissions</div>
                            <div className="text-lg font-bold text-purple-800 mt-1">{report.scope3}</div>
                            <div className="text-xs text-purple-600">Value chain emissions</div>
                          </div>
                        )}
                      </div>
                      <div className="mt-4 flex flex-wrap gap-4 text-sm">
                        {report?.netZeroTarget && (
                          <div className="flex items-center gap-2 text-neutral-700">
                            <Zap className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                            <span><strong>Net-Zero Target:</strong> {report.netZeroTarget}</span>
                          </div>
                        )}
                        {report?.renewableEnergy && (
                          <div className="flex items-center gap-2 text-neutral-700">
                            <TrendingUp className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                            <span><strong>Renewable Energy:</strong> {report.renewableEnergy}</span>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Deception Analysis */}
                {(report?.greenwishingScore || report?.greenhushingScore) && (
                  <Card className="border-neutral-200 bg-white shadow-sm">
                    <CardHeader className="pb-3 border-b border-neutral-100">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <AlertTriangle className="w-4 h-4 text-amber-600" /> Deception Pattern Analysis
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                          <div className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">Greenwishing Score</div>
                          <div className="text-2xl font-bold text-amber-800">{report.greenwishingScore}/100</div>
                          <div className="text-xs text-amber-600 mt-1">Aspirational claims without execution backing</div>
                          <div className="mt-2 h-1.5 bg-amber-200 rounded-full overflow-hidden">
                            <div className="h-full bg-amber-500 rounded-full" style={{ width: `${report.greenwishingScore}%` }} />
                          </div>
                        </div>
                        <div className="rounded-lg border border-orange-200 bg-orange-50 p-4">
                          <div className="text-xs font-semibold text-orange-700 uppercase tracking-wide mb-2">Greenhushing Score</div>
                          <div className="text-2xl font-bold text-orange-800">{report.greenhushingScore}/100</div>
                          <div className="text-xs text-orange-600 mt-1">Material sustainability omissions</div>
                          <div className="mt-2 h-1.5 bg-orange-200 rounded-full overflow-hidden">
                            <div className="h-full bg-orange-500 rounded-full" style={{ width: `${report.greenhushingScore}%` }} />
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Key Risk Drivers */}
                {report?.keyRiskDrivers && report.keyRiskDrivers.length > 0 && (
                  <Card className="border-neutral-200 bg-white shadow-sm">
                    <CardHeader className="pb-3 border-b border-neutral-100">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <TrendingDown className="w-4 h-4 text-red-600" /> Key Risk Drivers
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-4 space-y-2">
                      {report.keyRiskDrivers.map((driver, i) => (
                        <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-red-50 border border-red-100">
                          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-red-200 text-red-800 text-xs font-bold flex items-center justify-center">{i + 1}</span>
                          <p className="text-sm text-neutral-800">{driver}</p>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Contradictions & Regulatory */}
                {report?.contradictions && report.contradictions.length > 0 && (
                  <Card className="border-red-200 bg-white shadow-sm">
                    <CardHeader className="pb-3 border-b border-red-100">
                      <CardTitle className="flex items-center gap-2 text-base text-red-700">
                        <AlertTriangle className="w-4 h-4" /> Legal Contradictions & Violations
                      </CardTitle>
                      <CardDescription>{report.contradictions.length} high-severity finding(s)</CardDescription>
                    </CardHeader>
                    <CardContent className="pt-4 space-y-3">
                      {report.contradictions.map((contra, i) => (
                        <div key={i} className="rounded-lg border border-red-200 bg-red-50 p-4">
                          <div className="flex items-start gap-2">
                            <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                            <p className="text-sm text-red-900 leading-relaxed">{contra}</p>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Narrative Section */}
                {report?.narrative && report.narrative.length > 0 && (
                  <Card className="border-neutral-200 bg-white shadow-sm">
                    <CardHeader className="pb-3 border-b border-neutral-100">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Info className="w-4 h-4 text-primary-600" /> Assessment Narrative
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-4 space-y-3">
                      {report.narrative.map((para, i) => (
                        <p key={i} className="text-sm text-neutral-700 leading-7">{para}</p>
                      ))}
                    </CardContent>
                  </Card>
                )}

                {/* Report Metadata */}
                <Card className="border-neutral-200 bg-white shadow-sm">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-semibold text-neutral-700">Report Metadata</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                      {[
                        { key: "Company", value: report?.company || results.company_name },
                        { key: "Ticker", value: report?.ticker },
                        { key: "Industry", value: report?.industry || results.industry },
                        { key: "Report Date", value: report?.reportDate },
                        { key: "Confidence", value: confidenceDisplay },
                        { key: "Report File", value: results.report_file_name },
                      ].filter(r => isUsefulText(r.value)).map(row => (
                        <div key={row.key} className="rounded-md border border-neutral-200 p-3">
                          <div className="text-xs text-neutral-500 mb-0.5">{row.key}</div>
                          <div className="font-medium text-neutral-900 text-xs break-all">{row.value}</div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Agent Breakdown (collapsible) */}
                <Card className="border-neutral-200 bg-white shadow-sm">
                  <button
                    className="w-full text-left p-4 flex items-center justify-between"
                    onClick={() => setShowAgents(!showAgents)}
                  >
                    <div className="flex items-center gap-2">
                      <BrainCircuit className="w-4 h-4 text-primary-600" />
                      <span className="font-semibold text-neutral-900 text-sm">Agent Execution Breakdown</span>
                      <span className="text-xs text-neutral-500">({agentContributions.length} agents)</span>
                    </div>
                    {showAgents ? <ChevronUp className="w-4 h-4 text-neutral-500" /> : <ChevronDown className="w-4 h-4 text-neutral-500" />}
                  </button>
                  <AnimatePresence>
                    {showAgents && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="px-4 pb-4 space-y-2 border-t border-neutral-100 pt-4">
                          {!agentContributions.length && (
                            <p className="text-sm text-neutral-500">No agent contribution data in report payload.</p>
                          )}
                          {agentContributions.map((agent) => (
                            <div key={agent.agent} className="rounded-md border border-neutral-200 p-3 bg-neutral-50">
                              <div className="flex items-center justify-between gap-3 text-sm">
                                <div className="font-medium text-neutral-900">{titleCaseAgent(agent.agent)}</div>
                                <div className="text-neutral-600 text-xs">
                                  {agent.contributionPct.toFixed(1)}% · conf {(agent.confidence * 100).toFixed(0)}%
                                </div>
                              </div>
                              <div className="mt-1.5 h-1.5 w-full rounded-full bg-neutral-200 overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-primary-500"
                                  style={{ width: `${Math.min(100, Math.max(0, agent.contributionPct))}%` }}
                                />
                              </div>
                              <div className="mt-1 text-xs text-neutral-500 flex items-center justify-between">
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${agent.status === "UNKNOWN" ? "bg-neutral-100 text-neutral-500" : "bg-emerald-100 text-emerald-700"}`}>
                                  {agent.status}
                                </span>
                                <span>{agent.keyFindingsCount} findings</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Empty state */}
          {appState === "input" && !results && (
            <div className="flex flex-col items-center justify-center h-64 text-center border-2 border-dashed border-neutral-200 rounded-2xl">
              <BrainCircuit className="w-12 h-12 text-neutral-300 mb-3" />
              <h3 className="text-neutral-700 font-semibold">Ready to Analyze</h3>
              <p className="text-neutral-400 text-sm mt-1 max-w-xs">Fill in the form and click &quot;Run ESG Analysis&quot; to start the multi-agent pipeline.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
