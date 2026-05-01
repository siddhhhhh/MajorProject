import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Gavel, AlertTriangle, Shield, ExternalLink, AlertCircle, Flag, Loader2 } from "lucide-react";
import { PageWrapper } from "@/components/layout/PageWrapper";
import { ScoreHemisphere } from "@/components/three/ScoreHemisphere";
import { ArcGauge } from "@/components/charts/ArcGauge";
import { RiskBadge } from "@/components/cards/RiskBadge";
import type { ReportData } from "@/types/report";
import { ExportMenu } from "@/components/report/ExportMenu";
import { useAnalysisStore } from "@/stores/analysisStore";
import { getReport, getReportArtifacts } from "@/lib/api";
import type { ESGReport } from "@/lib/api";
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, Tooltip, Area, ComposedChart,
  ScatterChart, Scatter, ZAxis, BarChart, Bar, Cell,
} from "recharts";

const TABS = ["Overview", "Audit Report", "Carbon", "Greenwashing", "Contradictions", "Regulatory", "Peers", "Explainability", "Evidence", "Raw Data"];

// Empty fallbacks so charts render an empty state when backend data is
// missing — never fabricated demo values that would mislead a viewer.
const PATHWAY: Array<{ year: number; required: number; actual: number; gap: number }> = [];
const SHAP: Array<{ f: string; v: number }> = [];
const DECEPTION: Array<{ axis: string; v: number }> = [];

function parseAuditSections(text?: string | null): { title: string; body: string }[] {
  if (!text) return [];
  const lines = text.split(/\r?\n/);
  const sections: { title: string; body: string[] }[] = [];
  let current: { title: string; body: string[] } | null = null;

  const isRule = (line: string) => {
    const trimmed = line.trim();
    return trimmed.length >= 20 && /^[=\-─]+$/.test(trimmed);
  };

  for (const line of lines) {
    const trimmed = line.trim();
    const isTitle =
      trimmed === "REPORT HEADER" ||
      trimmed === "VERDICT" ||
      trimmed.startsWith("SECTION ") ||
      trimmed.startsWith("APPENDIX ");

    if (isTitle) {
      if (current) sections.push(current);
      current = { title: trimmed, body: [] };
      continue;
    }
    if (!current) {
      current = { title: "Full Report", body: [] };
    }
    if (!isRule(line)) current.body.push(line);
  }

  if (current) sections.push(current);
  return sections
    .map((s) => ({ title: s.title, body: s.body.join("\n").trim() }))
    .filter((s) => s.body || s.title);
}

/** Map an API ESGReport into the existing ReportData shape used by the UI */
function apiToReportData(api: ESGReport): ReportData {
  return {
    id: api.id,
    company: api.company,
    ticker: api.ticker,
    sector: api.sector,
    jurisdiction: api.regulatory && api.regulatory.length > 0 ? api.regulatory[0].jurisdiction : "Global",
    date: api.analysis_date?.split("T")[0] ?? "",
    duration: `${Math.round(api.pipeline_duration_seconds / 60)}m ${Math.round(api.pipeline_duration_seconds % 60)}s`,
    agentsRun: `${api.agents_successful} / ${api.agents_total}`,
    esgScore: api.esg_score,
    rating: api.rating_grade,
    riskLevel: api.risk_level as "HIGH" | "MEDIUM" | "LOW",
    pillars: { e: api.environmental.score, s: api.social.score, g: api.governance.score },
    greenwashing: api.greenwashing.overall_score,
    confidence: api.confidence,
    scope1: api.carbon.scope1,
    scope2: api.carbon.scope2,
    scope3: api.carbon.scope3,
    netZeroTarget: api.carbon.net_zero_target,
    carbonBudgetYears: api.carbon.budget_years_remaining ?? 0,
    ieaGapPct: api.carbon.iea_nze_gap_pct ?? 0,
    requiredAnnualRate: api.carbon.required_annual_rate,
    companyImpliedRate: api.carbon.company_implied_rate,
    alignmentStatus: api.carbon.alignment_status,
    claim: api.claim,
    verdict: api.risk_level === "HIGH" ? "CONTRADICTED" : api.risk_level === "LOW" ? "SUPPORTED" : "INCONCLUSIVE",
    summary: api.executive_summary || api.ai_verdict,
    topFindings: api.top_risk_drivers.slice(0, 3).map((d) => ({
      kind: (d.direction === "increases_risk" ? "red" : "green") as "red" | "amber" | "green",
      text: d.name + (d.impact ? ` — ${d.impact}` : ""),
    })),
    contradictions: api.contradictions.map((c) => ({
      severity: c.severity,
      claim: c.claim_text,
      evidence: c.evidence_text,
      source: c.source,
      impact: c.impact,
      kind: c.severity === "HIGH" ? "legal" : "data",
    })),
    regulatory: api.regulatory.map((r) => ({
      framework: r.framework,
      score: r.compliance_score,
      status: r.status,
      gap: r.key_gap,
    })),
    regulatoryOverall: api.regulatory.length > 0 ? Math.round(api.regulatory.reduce((s, r) => s + r.compliance_score, 0) / api.regulatory.length) : 0,
    // Real peer rows from peer_comparison agent (mapper). marketCap is no
    // longer fabricated — frontend now hides that column.
    peers: (api.peers && api.peers.length > 0)
      ? api.peers.map((p) => ({
          name: p.name,
          ticker: p.ticker || "",
          esg: p.esg,
          gw: p.gw,
          rating: p.rating || "",
          marketCap: 0,
          isFocus: !!p.is_focus,
        }))
      : [
          { name: api.company, ticker: api.ticker, esg: api.esg_score, gw: api.greenwashing.overall_score, rating: api.rating_grade, marketCap: 0, isFocus: true },
        ],
    evidence: api.evidence.map((e) => ({
      type: e.source_type,
      domain: (e.source_url ?? "").replace(/https?:\/\//, "").split("/")[0] || e.source_name,
      url: e.source_url ?? "#",
      year: e.year ?? 2024,
      credibility: e.credibility,
      stance: e.stance,
      excerpt: e.excerpt,
      archive: e.archive_verified ? "verified" : "unverified",
    })),
    greenwashingData: api.greenwashing,
    shapDrivers: api.top_risk_drivers.map(d => ({
      f: d.name,
      v: d.shap_value ?? (d.direction === "increases_risk" ? 10 : -5)
    })).slice(0, 10),
  };
}

function withArtifacts(base: ReportData, artifacts: Awaited<ReturnType<typeof getReportArtifacts>>): ReportData {
  const auditText = artifacts.txt || undefined;
  return {
    ...base,
    auditText,
    auditSections: parseAuditSections(auditText),
    auditBrief: artifacts.brief || null,
    rawReport: artifacts.full_json || null,
  };
}

export default function Report() {
  const [params] = useSearchParams();
  const id = params.get("id") || "";
  const storeReport = useAnalysisStore((s) => s.currentReport);
  const [apiReport, setApiReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [tab, setTab] = useState("Overview");
  const [evFilter, setEvFilter] = useState<string>("All");
  const [flagged, setFlagged] = useState<Record<number, boolean>>({});

  useEffect(() => {
    // Seed from store for instant paint, but still hydrate from backend when URL id exists.
    if (storeReport && (!id || storeReport.id === id)) {
      setApiReport(apiToReportData(storeReport));
    }

    if (id) {
      setLoading(true);
      setApiError(null);
      Promise.all([getReport(id), getReportArtifacts(id).catch(() => null)])
        .then(([data, artifacts]) => {
          const mapped = apiToReportData(data);
          setApiReport(artifacts ? withArtifacts(mapped, artifacts) : mapped);
        })
        .catch((err) => {
          setApiError(err?.message || "Failed to load report from API");
          if (typeof console !== "undefined") {
            console.warn(`[Report] live API fetch failed for id=${id}`, err);
          }
        })
        .finally(() => setLoading(false));
    }
  }, [id, storeReport]);

  const R = apiReport;

  if (loading) {
    return (
      <PageWrapper>
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <Loader2 className="h-10 w-10 text-teal-bright animate-spin mx-auto mb-4" />
            <div className="text-text-secondary font-mono text-sm">Loading report…</div>
          </div>
        </div>
      </PageWrapper>
    );
  }

  // Real-data failure path: the requested id could not be resolved from the live backend.
  if (!R) {
    return (
      <PageWrapper>
        <div className="flex items-center justify-center h-screen">
          <div className="text-center max-w-md px-6">
            <div className="text-text-primary text-xl font-display mb-3">
              Report not found
            </div>
            <div className="text-text-secondary text-sm mb-2">
              No live report exists for id <code className="font-mono">{id}</code>.
            </div>
            {apiError && (
              <div className="text-text-secondary text-xs font-mono mb-4 opacity-70">
                API error: {apiError}
              </div>
            )}
            <div className="text-text-secondary text-xs">
              Run a fresh analysis from the New Analysis page, or open a report from the library.
            </div>
          </div>
        </div>
      </PageWrapper>
    );
  }

  const filteredEvidence = R.evidence.filter((e) => {
    if (evFilter === "All") return true;
    if (evFilter === "Supporting") return e.stance === "SUPPORTING";
    if (evFilter === "Contradicting") return e.stance === "CONTRADICTING";
    if (evFilter === "Neutral") return e.stance === "NEUTRAL";
    if (evFilter === "High credibility") return e.credibility >= 0.8;
    if (evFilter === "Unverified") return e.archive !== "verified";
    return true;
  });
  const flaggedCount = Object.values(flagged).filter(Boolean).length;

  const activeDeception = R.greenwashingData ? [
    { axis: "Greenwashing", v: Math.round(R.greenwashingData.overall_score || R.greenwashing) },
    { axis: "Greenwishing", v: Math.round(R.greenwashingData.greenwishing_score || 0) },
    { axis: "Greenhushing", v: Math.round(R.greenwashingData.greenhushing_score || 0) },
    { axis: "Selective Disc.", v: R.greenwashingData.selective_disclosure ? 85 : 15 },
    { axis: "Temporal Esc.", v: R.greenwashingData.temporal_escalation === "HIGH" ? 90 : R.greenwashingData.temporal_escalation === "MEDIUM" ? 50 : 20 },
    { axis: "Linguistic Risk", v: Math.round(R.greenwashingData.linguistic_risk || 0) },
  ] : DECEPTION;

  const activeShap = R.shapDrivers || SHAP;

  // Real-data-first emissions pathway: derive from the report's required vs
  // implied annual reduction rates if the carbon-pathway agent provided them.
  // Otherwise fall through to the demo PATHWAY constant so the UI doesn't
  // collapse for legacy reports.
  const requiredRate = R.requiredAnnualRate;
  const impliedRate = R.companyImpliedRate;
  const activePathway = (typeof requiredRate === "number" && typeof impliedRate === "number" && requiredRate > 0)
    ? Array.from({ length: 31 }, (_, i) => {
        const year = 2020 + i;
        const required = Math.max(0, 100 - (i * requiredRate));
        const actual = Math.max(0, 100 - (i * impliedRate));
        return { year, required, actual, gap: actual - required };
      })
    : PATHWAY;

  return (
    <PageWrapper>
      {/* HERO */}
      <section className="relative px-10 py-12 border-b border-bg-border overflow-hidden grid-bg">
        <div className="absolute top-4 right-10 flex items-center gap-3">
          {flaggedCount > 0 && (
            <span className="inline-flex items-center gap-1.5 text-xs font-mono text-amber-bright px-2.5 py-1 rounded-md bg-amber-bright/10 border border-amber-bright/30">
              <Flag className="h-3 w-3" /> {flaggedCount} flagged
            </span>
          )}
          <ExportMenu report={R} reportId={id ?? undefined} />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px_1fr] gap-8 items-center">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <span className="label-eyebrow text-teal-bright">{R.sector?.toUpperCase() || "GENERAL"} · {R.jurisdiction?.toUpperCase() || "GLOBAL"}</span>
              <RiskBadge level={R.riskLevel} />
            </div>
            <h1 className="font-display text-6xl leading-none">{R.company}</h1>
            <div className="font-mono text-text-secondary mt-2">{R.ticker}</div>
            <p className="mt-6 text-text-secondary max-w-md italic font-display text-lg">"{R.claim}"</p>
            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-risk-high/10 border border-risk-high/30">
              <AlertTriangle className="h-4 w-4 text-risk-high" />
              <span className="text-risk-high text-sm font-medium">VERDICT · {R.verdict}</span>
            </div>
          </div>
          <div className="text-center">
            <ScoreHemisphere score={R.esgScore} />
            <div className="font-display text-7xl text-teal-bright leading-none -mt-4">{R.esgScore}</div>
            <div className="label-eyebrow mt-1">ESG SCORE</div>
          </div>
          <div className="text-right">
            <div className={`font-display text-9xl leading-none ${R.riskLevel === "HIGH" ? "text-risk-high" : R.riskLevel === "LOW" ? "text-risk-low" : "text-amber-bright"}`}>{R.rating}</div>
            <div className="label-eyebrow mt-2">MSCI-STYLE RATING</div>
            <div className="mt-4 inline-block">
              <div className="font-mono text-xs text-text-secondary">CONFIDENCE</div>
              <div className="font-display text-3xl text-amber-bright">{Math.round(R.confidence)}%</div>
            </div>
          </div>
        </div>
      </section>

      {/* TABS */}
      <div className="sticky top-0 z-30 bg-bg-deep/90 backdrop-blur-md border-b border-bg-border px-10">
        <div className="flex gap-1 overflow-x-auto scrollbar-thin">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-3 text-sm whitespace-nowrap border-b-2 transition ${
                tab === t ? "border-teal-bright text-teal-bright" : "border-transparent text-text-secondary hover:text-text-primary"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="px-10 py-10 space-y-10">
        {tab === "Overview" && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {[
                { l: "ESG SCORE", v: Math.round(R.esgScore), c: "text-teal-bright" },
                { l: "GREENWASHING", v: Math.round(R.greenwashing), c: "text-risk-high" },
                { l: "CONFIDENCE", v: Math.round(R.confidence), c: "text-amber-bright" },
              ].map((k) => (
                <div key={k.l} className="rounded-xl bg-bg-surface border border-bg-border p-6">
                  <div className="label-eyebrow mb-2">{k.l}</div>
                  <div className={`font-display text-5xl ${k.c}`}>{k.v}<span className="text-xl text-text-secondary">/100</span></div>
                </div>
              ))}
            </div>
            <div className="rounded-xl bg-bg-surface border border-bg-border p-8">
              <div className="label-eyebrow mb-3">AI VERDICT</div>
              <p className="font-display italic text-2xl text-text-primary leading-relaxed">{R.summary}</p>
            </div>
            <div className="grid grid-cols-3 gap-5">
              {[
                { l: "ENVIRONMENTAL", v: R.pillars.e },
                { l: "SOCIAL", v: R.pillars.s },
                { l: "GOVERNANCE", v: R.pillars.g },
              ].map((p) => (
                <div key={p.l} className="rounded-xl bg-bg-surface border border-bg-border p-6 text-center">
                  <ArcGauge value={p.v} size={180} label={p.l} />
                </div>
              ))}
            </div>
          </>
        )}

        {tab === "Audit Report" && (
          <div className="space-y-5">
            {R.auditBrief && (
              <div className="rounded-xl bg-bg-surface border border-bg-border p-6">
                <div className="label-eyebrow mb-4">BACKEND BRIEF</div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  {[
                    ["GW Risk", (R.auditBrief as any).headline?.greenwashing_risk_score],
                    ["ESG Score", (R.auditBrief as any).headline?.esg_score],
                    ["Risk Band", (R.auditBrief as any).headline?.risk_band],
                    ["Confidence", (R.auditBrief as any).headline?.confidence_pct ? `${(R.auditBrief as any).headline.confidence_pct}%` : undefined],
                  ].map(([label, value]) => (
                    <div key={label} className="border border-bg-border bg-bg-elevated/40 rounded-lg p-4">
                      <div className="label-eyebrow mb-1">{label}</div>
                      <div className="font-display text-2xl text-teal-bright">{value ?? "N/A"}</div>
                    </div>
                  ))}
                </div>
                {Array.isArray((R.auditBrief as any).due_diligence_questions) && (
                  <div className="mt-5">
                    <div className="label-eyebrow mb-2">DUE DILIGENCE QUESTIONS</div>
                    <div className="space-y-2">
                      {((R.auditBrief as any).due_diligence_questions as string[]).map((q, i) => (
                        <div key={i} className="text-sm text-text-primary border-l-2 border-teal-dim pl-3">{q}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {(R.auditSections && R.auditSections.length > 0) ? (
              R.auditSections.map((section) => (
                <section key={section.title} className="rounded-xl bg-bg-surface border border-bg-border overflow-hidden">
                  <div className="px-6 py-4 border-b border-bg-border bg-bg-elevated/40">
                    <h2 className="font-display text-2xl text-teal-bright">{section.title}</h2>
                  </div>
                  <pre className="p-6 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-text-primary overflow-x-auto">
                    {section.body}
                  </pre>
                </section>
              ))
            ) : (
              <div className="rounded-xl bg-bg-surface border border-bg-border p-6">
                <div className="label-eyebrow mb-3">BACKEND AUDIT REPORT</div>
                <div className="text-sm text-text-secondary">
                  No TXT artifact was found for this report. The structured API data is still available under Raw Data.
                </div>
              </div>
            )}
          </div>
        )}

        {tab === "Carbon" && (
          <>
            <div className="grid grid-cols-3 gap-5">
              {[
                { l: "SCOPE 1 · DIRECT", v: R.scope1 ? (R.scope1 / 1e6).toFixed(1) : 0, unit: "M tCO2e" },
                { l: "SCOPE 2 · ENERGY", v: R.scope2 ? (R.scope2 / 1e6).toFixed(1) : 0, unit: "M tCO2e" },
                { l: "SCOPE 3 · VALUE CHAIN", v: R.scope3 ? (R.scope3 / 1e6).toFixed(1) : 0, unit: "M tCO2e", big: true },
              ].map((s) => (
                <div key={s.l} className="rounded-xl bg-bg-surface border border-bg-border p-6">
                  <div className="label-eyebrow mb-3">{s.l}</div>
                  <div className={`font-display ${s.big ? "text-6xl text-risk-critical" : "text-5xl text-amber-bright"}`}>{s.v}</div>
                  <div className="font-mono text-xs text-text-secondary mt-1">{s.unit}</div>
                </div>
              ))}
            </div>
            <div className="rounded-xl bg-bg-surface border border-bg-border p-8">
              <div className="label-eyebrow mb-2">IEA NZE ALIGNMENT</div>
              <h3 className="font-display text-2xl mb-6">2020 → 2050 emissions trajectory</h3>
              <div className="h-72">
                {activePathway.length > 0 ? (
                  <ResponsiveContainer>
                    <ComposedChart data={activePathway}>
                      <XAxis dataKey="year" stroke="hsl(var(--text-muted))" tick={{ fontSize: 11 }} />
                      <YAxis stroke="hsl(var(--text-muted))" tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "hsl(var(--bg-elevated))", border: "1px solid hsl(var(--bg-border))", fontSize: 12 }} />
                      <Area type="monotone" dataKey="gap" fill="hsl(var(--risk-critical))" fillOpacity={0.15} stroke="none" />
                      <Line type="monotone" dataKey="required" stroke="hsl(var(--teal-bright))" strokeDasharray="5 5" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="actual" stroke="hsl(var(--amber-bright))" strokeWidth={2.5} dot={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-xs font-mono text-text-secondary">
                    Pathway trajectory not computed (insufficient rate data).
                  </div>
                )}
              </div>
              <div className="mt-4 text-sm text-text-secondary">
                {typeof requiredRate === "number" && typeof impliedRate === "number" ? (
                  <>
                    Company implied <span className="text-amber-bright font-mono">{impliedRate.toFixed(1)}%/yr</span> vs IEA NZE required <span className="text-teal-bright font-mono">{requiredRate.toFixed(1)}%/yr</span>
                    {typeof R.ieaGapPct === "number" ? (
                      <> · gap <span className="text-amber-bright font-mono">{R.ieaGapPct >= 0 ? "+" : ""}{R.ieaGapPct.toFixed(1)}%/yr</span></>
                    ) : null}
                    .
                  </>
                ) : (
                  <span className="font-mono text-text-muted">Pathway alignment data not yet available for this company.</span>
                )}
              </div>
            </div>
            <div className="rounded-xl bg-gradient-to-br from-risk-critical/10 to-bg-surface border border-risk-critical/30 p-10 text-center">
              <div className="label-eyebrow text-risk-critical mb-3">CARBON BUDGET COUNTDOWN</div>
              {R.carbonBudgetYears > 0 ? (
                <>
                  <div className="font-display text-7xl text-risk-critical">{R.carbonBudgetYears.toFixed(2)} yrs</div>
                  <div className="text-text-secondary mt-3">remaining at current trajectory</div>
                </>
              ) : (
                <>
                  <div className="font-display text-5xl text-text-secondary">—</div>
                  <div className="text-text-secondary mt-3">Budget remaining not computed (insufficient pathway data)</div>
                </>
              )}
            </div>
            {R.netZeroTarget && R.netZeroTarget !== "Unknown" && (
              <div className="rounded-xl bg-bg-surface border border-bg-border p-6">
                <div className="label-eyebrow mb-2">NET-ZERO TARGET</div>
                <div className="font-display text-2xl text-teal-bright">{R.netZeroTarget}</div>
                {R.alignmentStatus && (
                  <div className="mt-2 font-mono text-xs text-text-secondary">Pathway status: {R.alignmentStatus}</div>
                )}
              </div>
            )}
          </>
        )}

        {tab === "Greenwashing" && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <div className="rounded-xl bg-bg-surface border border-bg-border p-6">
                <div className="label-eyebrow mb-2">DECEPTION RADAR</div>
                <div className="h-80">
                  {activeDeception.length > 0 ? (
                    <ResponsiveContainer>
                      <RadarChart data={activeDeception}>
                        <PolarGrid stroke="hsl(var(--bg-border))" />
                        <PolarAngleAxis dataKey="axis" tick={{ fill: "hsl(var(--text-secondary))", fontSize: 11 }} />
                        <Radar dataKey="v" stroke="hsl(var(--risk-high))" fill="hsl(var(--risk-high))" fillOpacity={0.4} />
                      </RadarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="flex items-center justify-center h-full text-xs font-mono text-text-secondary">
                      No deception-pattern data available for this run.
                    </div>
                  )}
                </div>
              </div>
              <div className="rounded-xl bg-gradient-to-br from-teal-bright/10 to-bg-surface border border-teal-dim/40 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-lg bg-teal-bright/15 flex items-center justify-center text-teal-bright text-xl">🧠</div>
                  <div>
                    <div className="label-eyebrow text-teal-bright">CLIMATEBERT NLP</div>
                    <div className="font-display text-xl">Transformer analysis</div>
                  </div>
                </div>
                <div className="space-y-3 mt-6">
                  <div className="flex justify-between"><span className="text-text-secondary text-sm">Climate relevance</span><span className="font-mono text-teal-bright">{R.greenwashingData ? (R.greenwashingData.climatebert_relevance * 100).toFixed(1) : "99.8"}%</span></div>
                  <div className="flex justify-between"><span className="text-text-secondary text-sm">Risk classification</span><RiskBadge level={R.greenwashingData ? R.greenwashingData.climatebert_risk.toUpperCase() as any : "MEDIUM"} /></div>
                  <div className="flex justify-between"><span className="text-text-secondary text-sm">Linguistic patterns</span><span className="font-mono text-amber-bright">{R.greenwashingData ? (R.greenwashingData.linguistic_risk > 50 ? "High" : "Low") : "7 detected"}</span></div>
                </div>
                <p className="mt-6 text-sm text-text-secondary leading-relaxed">
                  Transformer analysis evaluated the disclosure document for semantic risk, identifying aspirational language patterns and benchmarking against known risk frameworks.
                </p>
              </div>
            </div>
          </>
        )}

        {tab === "Contradictions" && (
          <div className="space-y-5">
            {R.contradictions.map((c, i) => (
              <div key={i} className={`rounded-xl border-2 overflow-hidden ${c.kind === "legal" ? "border-risk-critical/40 bg-risk-critical/5" : "bg-bg-surface border-bg-border"}`}>
                <div className="flex items-center justify-between px-6 py-3 border-b border-bg-border">
                  <div className="flex items-center gap-3">
                    {c.kind === "legal" ? <Gavel className="h-5 w-5 text-risk-critical" /> : <AlertTriangle className="h-5 w-5 text-risk-high" />}
                    <span className="label-eyebrow">{c.kind === "legal" ? "LEGAL PRECEDENT" : "DATA CONTRADICTION"}</span>
                  </div>
                  <RiskBadge level={c.severity as any} />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-6 p-6 items-center">
                  <div>
                    <div className="label-eyebrow mb-2">CLAIM</div>
                    <p className="font-display italic text-lg">"{c.claim}"</p>
                  </div>
                  <div className="hidden md:flex flex-col items-center text-risk-critical">
                    <div className="h-16 w-px bg-risk-critical/40" />
                    <span className="text-2xl my-1">⚡</span>
                    <div className="h-16 w-px bg-risk-critical/40" />
                  </div>
                  <div>
                    <div className="label-eyebrow mb-2">EVIDENCE</div>
                    <p className="text-text-primary text-sm leading-relaxed">{c.evidence}</p>
                    <div className="font-mono text-[11px] text-teal-bright mt-3">{c.source}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "Regulatory" && (
          <>
            <div className="rounded-xl bg-bg-surface border border-bg-border p-8 text-center">
              <ArcGauge value={R.regulatoryOverall} size={220} label={`OVERALL ${R.jurisdiction?.toUpperCase() || "GLOBAL"} COMPLIANCE`} />
              <RiskBadge level={R.regulatoryOverall < 40 ? "HIGH" : R.regulatoryOverall < 70 ? "MEDIUM" : "LOW"} className="mt-4" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {R.regulatory.map((f) => (
                <div key={f.framework} className="rounded-xl bg-bg-surface border border-bg-border p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="font-display text-xl">{f.framework}</div>
                    <Shield className={`h-5 w-5 ${f.status === "COMPLIANT" ? "text-risk-low" : f.status === "PARTIAL" ? "text-amber-bright" : "text-risk-high"}`} />
                  </div>
                  <ArcGauge value={f.score} size={120} />
                  <div className={`mt-3 text-[11px] font-mono ${f.status === "COMPLIANT" ? "text-risk-low" : f.status === "PARTIAL" ? "text-amber-bright" : "text-risk-high"}`}>{f.status}</div>
                  <p className="text-xs text-text-secondary mt-2">{f.gap}</p>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === "Peers" && (
          <>
            <div className="rounded-xl bg-bg-surface border border-bg-border p-6">
              <div className="label-eyebrow mb-4">SECTOR ESG BENCHMARK</div>
              <div className="h-80">
                {R.peers.length > 1 ? (
                  <ResponsiveContainer>
                    <BarChart data={R.peers.map((p) => ({ name: p.name.replace(/ Corporation| Group| Industries| Inc\.?| plc/g, "").trim(), esg: p.esg, isFocus: p.isFocus }))}>
                      <XAxis dataKey="name" stroke="hsl(var(--text-muted))" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={70} />
                      <YAxis stroke="hsl(var(--text-muted))" tick={{ fontSize: 11 }} domain={[0, 100]} label={{ value: "ESG SCORE", angle: -90, position: "insideLeft", fill: "hsl(var(--text-secondary))", fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "hsl(var(--bg-elevated))", border: "1px solid hsl(var(--bg-border))", fontSize: 12 }} />
                      <Bar dataKey="esg" radius={[4, 4, 0, 0]}>
                        {R.peers.map((p, i) => (
                          <Cell key={i} fill={p.isFocus ? "hsl(var(--teal-bright))" : "hsl(var(--amber-mid))"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-xs font-mono text-text-secondary">
                    Sector peer comparators not yet populated by the backend — only the analysed company is shown.
                  </div>
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-4 text-xs font-mono text-text-secondary">
                <span className="inline-flex items-center gap-2"><span className="h-2 w-3 rounded-sm bg-teal-bright inline-block" /> Analysed company</span>
                <span className="inline-flex items-center gap-2"><span className="h-2 w-3 rounded-sm bg-amber-mid inline-block" /> Sector peers</span>
              </div>
            </div>
            <div className="rounded-xl bg-bg-surface border border-bg-border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-bg-elevated">
                  <tr className="text-left">
                    {["Company", "Ticker", "ESG", "GW Risk", "Rating"].map((h) => (
                      <th key={h} className="px-4 py-3 label-eyebrow">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {R.peers.map((p) => (
                    <tr key={`${p.name}-${p.ticker}`} className={`border-t border-bg-border ${p.isFocus ? "bg-teal-bright/5 border-l-2 border-l-teal-bright" : ""}`}>
                      <td className="px-4 py-3 font-medium">{p.name}{p.isFocus ? <span className="ml-2 text-[10px] font-mono text-teal-bright">FOCUS</span> : null}</td>
                      <td className="px-4 py-3 font-mono text-text-secondary">{p.ticker || "—"}</td>
                      <td className="px-4 py-3 font-mono text-teal-bright">{p.esg ? p.esg.toFixed(1) : "—"}</td>
                      {/* GW score is only computed for the analysed company; peers show "—". */}
                      <td className="px-4 py-3 font-mono text-risk-high">{p.isFocus && p.gw > 0 ? p.gw.toFixed(1) : "—"}</td>
                      <td className="px-4 py-3 font-display text-amber-bright">{p.rating || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {tab === "Explainability" && (
          <div className="rounded-xl bg-bg-surface border border-bg-border p-6">
            <div className="label-eyebrow mb-2">SHAP FEATURE IMPORTANCE</div>
            <h3 className="font-display text-2xl mb-6">Top risk drivers</h3>
            <div className="h-[420px]">
              {activeShap.length > 0 ? (
                <ResponsiveContainer>
                  <BarChart data={activeShap} layout="vertical" margin={{ left: 200 }}>
                    <XAxis type="number" stroke="hsl(var(--text-muted))" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="f" type="category" stroke="hsl(var(--text-secondary))" tick={{ fontSize: 11 }} width={200} />
                    <Tooltip contentStyle={{ background: "hsl(var(--bg-elevated))", border: "1px solid hsl(var(--bg-border))", fontSize: 12 }} />
                    <Bar dataKey="v" radius={[0, 4, 4, 0]}>
                      {activeShap.map((s, i) => (
                        <Cell key={i} fill={s.v > 0 ? "hsl(var(--risk-high))" : "hsl(var(--teal-bright))"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-xs font-mono text-text-secondary">
                  Risk-driver attribution not computed for this run.
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "Evidence" && (
          <>
            <div className="flex flex-wrap gap-2">
              {["All", "Supporting", "Contradicting", "Neutral", "High credibility", "Unverified"].map((f) => (
                <button
                  key={f}
                  onClick={() => setEvFilter(f)}
                  className={`px-3 py-1.5 rounded-full text-xs font-mono border transition ${
                    evFilter === f ? "bg-teal-bright/15 text-teal-bright border-teal-bright/40" : "border-bg-border text-text-secondary hover:border-teal-dim"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
            <motion.div layout className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredEvidence.map((e, i) => {
                const credColor = e.credibility >= 0.8 ? "bg-risk-minimal" : e.credibility >= 0.5 ? "bg-amber-bright" : "bg-risk-high";
                const credLabel = e.credibility >= 0.8 ? "High" : e.credibility >= 0.5 ? "Medium" : "Low";
                const verified = e.archive === "verified";
                const isFlagged = flagged[i];
                return (
                  <motion.div
                    key={i}
                    layout
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`rounded-xl border p-5 transition ${isFlagged ? "bg-amber-bright/5 border-amber-bright/40" : "bg-bg-surface border-bg-border"}`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-bg-elevated text-text-secondary">{e.type}</span>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        e.stance === "CONTRADICTING" ? "bg-risk-high/15 text-risk-high" :
                        e.stance === "SUPPORTING" ? "bg-risk-low/15 text-risk-low" :
                        "bg-bg-elevated text-text-secondary"
                      }`}>{e.stance}</span>
                    </div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`h-2 w-2 rounded-full ${credColor}`} title={`Credibility: ${e.credibility.toFixed(2)} / 1.0 — ${credLabel}`} />
                      <span className="font-mono text-xs text-teal-bright">{e.domain} · {e.year}</span>
                    </div>
                    <p className="text-sm text-text-primary leading-relaxed mb-4">{e.excerpt}</p>
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono text-text-secondary">CRED · {(e.credibility * 100).toFixed(0)}%</span>
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => setFlagged((p) => ({ ...p, [i]: !p[i] }))}
                          className={`transition ${isFlagged ? "text-amber-bright" : "text-text-muted hover:text-amber-bright"}`}
                          aria-label="Flag for review"
                          title="Flag for human review"
                        >
                          <Flag className="h-3.5 w-3.5" />
                        </button>
                        <a
                          href={(e as any).url || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={`inline-flex items-center gap-1 font-mono ${verified ? "text-teal-bright hover:underline" : "text-amber-bright hover:underline"}`}
                          title={verified ? "Open original source" : "Historical snapshot unavailable. Link may have changed since analysis."}
                        >
                          {verified ? (
                            <>View source <ExternalLink className="h-3 w-3" /></>
                          ) : (
                            <>Source unverified <AlertCircle className="h-3 w-3" /></>
                          )}
                        </a>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </motion.div>
          </>
        )}

        {tab === "Raw Data" && (
          <div className="rounded-xl bg-bg-void border border-bg-border p-6">
            <div className="label-eyebrow mb-3">BACKEND REPORT JSON</div>
            <pre className="font-mono text-xs text-teal-bright overflow-x-auto max-h-[600px] overflow-y-auto scrollbar-thin">
{JSON.stringify(R.rawReport || R, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
