import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  CircleAlert,
  FileSearch,
  Gauge,
  Layers,
  Loader2,
  Scale,
  ShieldAlert,
  Target,
} from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageWrapper } from "@/components/layout/PageWrapper";
import { RiskBadge } from "@/components/cards/RiskBadge";
import { ArcGauge } from "@/components/charts/ArcGauge";
import { getReport, getReportArtifacts, type ESGReport, type ReportArtifacts } from "@/lib/api";

type RiskLevel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "MINIMAL";

function riskLevel(score: number): RiskLevel {
  if (score >= 80) return "CRITICAL";
  if (score >= 60) return "HIGH";
  if (score >= 40) return "MEDIUM";
  if (score >= 20) return "LOW";
  return "MINIMAL";
}

function statusLevel(status?: string): RiskLevel {
  const normalized = (status || "").toUpperCase();
  if (normalized.includes("NON") || normalized.includes("FAIL") || normalized.includes("HIGH")) return "HIGH";
  if (normalized.includes("PARTIAL") || normalized.includes("MEDIUM")) return "MEDIUM";
  if (normalized.includes("COMPLIANT") || normalized.includes("LOW")) return "LOW";
  return "MINIMAL";
}

function formatNumber(n?: number | null) {
  if (typeof n !== "number" || Number.isNaN(n)) return "Unavailable";
  if (Math.abs(n) >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(0);
}

function asPct(n?: number | null) {
  if (typeof n !== "number" || Number.isNaN(n)) return "Unavailable";
  return `${n.toFixed(1)}%`;
}

function sourceHost(url?: string) {
  if (!url) return "Unlinked source";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.replace(/https?:\/\//, "").split("/")[0] || "Source";
  }
}

function countArtifacts(artifacts: ReportArtifacts | null) {
  if (!artifacts) return 0;
  return [artifacts.txt, artifacts.brief, artifacts.full_json].filter(Boolean).length;
}

function KpiCard({ label, value, detail, tone = "teal" }: { label: string; value: string | number; detail?: string; tone?: "teal" | "amber" | "red" | "blue" }) {
  const toneClass = {
    teal: "text-teal-bright",
    amber: "text-amber-bright",
    red: "text-risk-high",
    blue: "text-blue-bright",
  }[tone];
  return (
    <div className="rounded-lg border border-bg-border bg-bg-surface p-4 shadow-card">
      <div className="label-eyebrow mb-2">{label}</div>
      <div className={`font-display text-3xl leading-none ${toneClass}`}>{value}</div>
      {detail && <div className="mt-2 text-xs text-text-secondary">{detail}</div>}
    </div>
  );
}

function SectionHeader({ eyebrow, title, text }: { eyebrow: string; title: string; text?: string }) {
  return (
    <div className="mb-5 flex flex-col gap-1">
      <div className="label-eyebrow text-teal-bright">{eyebrow}</div>
      <h2 className="font-display text-3xl text-text-primary">{title}</h2>
      {text && <p className="max-w-2xl text-sm text-text-secondary">{text}</p>}
    </div>
  );
}

export default function ExecutiveKiosk() {
  const { reportId = "" } = useParams();
  const [report, setReport] = useState<ESGReport | null>(null);
  const [artifacts, setArtifacts] = useState<ReportArtifacts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    Promise.all([getReport(reportId), getReportArtifacts(reportId).catch(() => null)])
      .then(([data, artifactData]) => {
        if (!alive) return;
        setReport(data);
        setArtifacts(artifactData);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err?.message || "Failed to load executive dashboard");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [reportId]);

  const derived = useMemo(() => {
    if (!report) return null;

    const evidence = report.evidence || [];
    const contradictions = report.contradictions || [];
    const regulatory = report.regulatory || [];
    const riskDrivers = report.top_risk_drivers || [];
    const increasing = riskDrivers.filter((d) => d.direction === "increases_risk");
    const reducing = riskDrivers.filter((d) => d.direction === "reduces_risk");
    const shap = riskDrivers
      .map((d) => ({
        name: d.name,
        value: d.shap_value ?? (d.direction === "increases_risk" ? 1 : -1),
        direction: d.direction,
      }))
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
      .slice(0, 8);
    const supportCount = evidence.filter((e) => e.stance === "SUPPORTING").length;
    const contradictCount = evidence.filter((e) => e.stance === "CONTRADICTING").length;
    const neutralCount = evidence.length - supportCount - contradictCount;
    const avgCredibility = evidence.length
      ? evidence.reduce((sum, e) => sum + (e.credibility || 0), 0) / evidence.length
      : null;
    const regulatoryGaps = regulatory.filter((r) => r.status !== "COMPLIANT").length;
    const complianceAverage = regulatory.length
      ? regulatory.reduce((sum, r) => sum + r.compliance_score, 0) / regulatory.length
      : null;
    const sourceTypes = Object.entries(
      evidence.reduce<Record<string, number>>((acc, e) => {
        acc[e.source_type || "Unknown"] = (acc[e.source_type || "Unknown"] || 0) + 1;
        return acc;
      }, {}),
    ).map(([name, value]) => ({ name, value }));
    const sourceMix = [
      { name: "Supporting", value: supportCount },
      { name: "Contradicting", value: contradictCount },
      { name: "Neutral", value: Math.max(0, neutralCount) },
    ].filter((item) => item.value > 0);
    const evidenceQuality = [
      { name: "High", value: evidence.filter((e) => e.credibility >= 0.8).length },
      { name: "Medium", value: evidence.filter((e) => e.credibility < 0.8 && e.credibility >= 0.5).length },
      { name: "Low", value: evidence.filter((e) => e.credibility < 0.5).length },
    ].filter((item) => item.value > 0);
    const pipeline = [
      { label: "Claim extraction", complete: !!report.claim },
      { label: "Evidence retrieval", complete: evidence.length > 0 },
      { label: "Carbon analysis", complete: !!report.carbon },
      { label: "Regulatory analysis", complete: regulatory.length > 0 },
      { label: "Contradiction detection", complete: contradictions.length > 0 },
      { label: "Explainability", complete: riskDrivers.length > 0 },
      { label: "Risk scoring", complete: typeof report.greenwashing?.overall_score === "number" },
      { label: "Verdict generation", complete: !!report.ai_verdict || !!report.executive_summary },
    ];

    return {
      evidence,
      contradictions,
      regulatory,
      increasing,
      reducing,
      shap,
      supportCount,
      contradictCount,
      neutralCount,
      avgCredibility,
      regulatoryGaps,
      complianceAverage,
      sourceTypes,
      sourceMix,
      evidenceQuality,
      pipeline,
      artifactCount: countArtifacts(artifacts),
      dataCoverage: report.fact_graph_motifs?.is_decision_ready
        ? "Decision-ready"
        : report.fact_graph_motifs?.pillar_coverage
          ? `${Object.keys(report.fact_graph_motifs.pillar_coverage).length} pillars`
          : evidence.length > 0
            ? `${evidence.length} evidence items`
            : "Unavailable",
    };
  }, [artifacts, report]);

  if (loading) {
    return (
      <PageWrapper>
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-center">
            <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-teal-bright" />
            <div className="font-mono text-sm text-text-secondary">Loading executive intelligence...</div>
          </div>
        </div>
      </PageWrapper>
    );
  }

  if (error || !report || !derived) {
    return (
      <PageWrapper>
        <div className="flex min-h-screen items-center justify-center px-6">
          <div className="max-w-md rounded-lg border border-bg-border bg-bg-surface p-8 text-center">
            <CircleAlert className="mx-auto mb-4 h-9 w-9 text-risk-high" />
            <h1 className="font-display text-3xl">Executive dashboard unavailable</h1>
            <p className="mt-3 text-sm text-text-secondary">{error || `No report exists for ${reportId}.`}</p>
            <Link to="/reports" className="mt-5 inline-flex rounded-md bg-teal-bright px-4 py-2 text-sm font-medium text-bg-void">
              Open Reports Library
            </Link>
          </div>
        </div>
      </PageWrapper>
    );
  }

  const topContradictions = derived.contradictions.slice(0, 4);
  const carbonBreakdown = [
    { name: "Scope 1", value: report.carbon?.scope1 || 0 },
    { name: "Scope 2", value: report.carbon?.scope2 || 0 },
    { name: "Scope 3", value: report.carbon?.scope3 || 0 },
  ].filter((item) => item.value > 0);
  const carbonAlignment = typeof report.carbon?.required_annual_rate === "number" && typeof report.carbon?.company_implied_rate === "number"
    ? [
        { name: "Required", value: report.carbon.required_annual_rate },
        { name: "Implied", value: report.carbon.company_implied_rate },
      ]
    : [];

  return (
    <PageWrapper className="bg-bg-deep">
      <div className="min-h-screen px-8 py-8 lg:px-10">
        <section className="relative overflow-hidden rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card-lg">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-risk-high via-amber-bright to-teal-bright" />
          <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <div>
              <div className="label-eyebrow text-teal-bright">Executive intelligence kiosk</div>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <h1 className="font-display text-5xl leading-none text-text-primary">{report.company}</h1>
                <RiskBadge level={report.risk_level as RiskLevel} />
              </div>
              <div className="mt-2 font-mono text-xs text-text-secondary">
                {report.ticker || "No ticker"} | {report.sector || "Sector unavailable"} | {report.analysis_date?.split("T")[0] || "Date unavailable"}
              </div>
              <div className="mt-6 max-w-4xl rounded-lg border border-bg-border bg-bg-elevated p-5">
                <div className="label-eyebrow mb-2">Claim analyzed</div>
                <p className="font-display text-2xl italic leading-snug text-text-primary">"{report.claim}"</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <KpiCard label="Greenwashing risk" value={report.greenwashing.overall_score.toFixed(1)} detail="Backend score" tone="red" />
              <KpiCard label="ESG score" value={report.esg_score.toFixed(1)} detail={report.rating_grade} tone="teal" />
              <KpiCard label="Confidence" value={asPct(report.confidence)} detail="Model confidence" tone="amber" />
              <KpiCard label="Sources analyzed" value={derived.evidence.length} detail={`${derived.artifactCount} artifacts loaded`} tone="blue" />
              <KpiCard label="Contradictions" value={derived.contradictions.length} detail="Detected by backend" tone="red" />
              <KpiCard label="Regulatory gaps" value={derived.regulatoryGaps} detail={derived.complianceAverage == null ? "No frameworks" : `${derived.complianceAverage.toFixed(1)} avg compliance`} tone="amber" />
            </div>
          </div>
          <div className="mt-6 grid gap-4 lg:grid-cols-4">
            <KpiCard label="Risk band" value={report.risk_level} detail="Final backend classification" tone={report.risk_level === "HIGH" ? "red" : "teal"} />
            <KpiCard label="Data coverage" value={derived.dataCoverage} detail="Derived from report evidence" tone="blue" />
            <KpiCard label="Agents completed" value={`${report.agents_successful}/${report.agents_total}`} detail={`${Math.round(report.pipeline_duration_seconds)}s pipeline`} tone="teal" />
            <KpiCard label="Evidence quality" value={derived.avgCredibility == null ? "Unavailable" : asPct(derived.avgCredibility * 100)} detail="Average source credibility" tone="amber" />
          </div>
        </section>

        <section className="mt-8 grid gap-5 xl:grid-cols-[1fr_0.8fr]">
          <div className="rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card">
            <SectionHeader eyebrow="Why this score?" title="Risk contribution analysis" text="Top backend risk drivers, separated by direction and visualized by contribution weight." />
            {derived.shap.length > 0 ? (
              <div className="h-80">
                <ResponsiveContainer>
                  <BarChart data={derived.shap} layout="vertical" margin={{ left: 150, right: 20 }}>
                    <XAxis type="number" stroke="hsl(var(--text-muted))" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="name" type="category" width={150} stroke="hsl(var(--text-secondary))" tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: "hsl(var(--bg-elevated))", border: "1px solid hsl(var(--bg-border))" }} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {derived.shap.map((item) => (
                        <Cell key={item.name} fill={item.value >= 0 ? "hsl(var(--risk-high))" : "hsl(var(--teal-bright))"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="rounded-lg border border-bg-border bg-bg-elevated p-5 text-sm text-text-secondary">
                Explainability drivers were not included in this report.
              </div>
            )}
          </div>

          <div className="grid gap-5">
            <div className="rounded-lg border border-bg-border bg-bg-surface p-5 shadow-card">
              <div className="mb-3 flex items-center gap-2">
                <ArrowUpRight className="h-4 w-4 text-risk-high" />
                <div className="label-eyebrow text-risk-high">Factors increasing risk</div>
              </div>
              <div className="space-y-2">
                {derived.increasing.slice(0, 4).map((d) => (
                  <div key={d.name} className="rounded-md border border-risk-high/20 bg-risk-high/5 p-3">
                    <div className="text-sm font-medium text-text-primary">{d.name}</div>
                    {d.impact && <div className="mt-1 text-xs text-text-secondary">{d.impact}</div>}
                  </div>
                ))}
                {derived.increasing.length === 0 && <div className="text-sm text-text-secondary">No increasing-risk drivers reported.</div>}
              </div>
            </div>
            <div className="rounded-lg border border-bg-border bg-bg-surface p-5 shadow-card">
              <div className="mb-3 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-teal-bright" />
                <div className="label-eyebrow text-teal-bright">Factors reducing risk</div>
              </div>
              <div className="space-y-2">
                {derived.reducing.slice(0, 4).map((d) => (
                  <div key={d.name} className="rounded-md border border-teal-dim/40 bg-teal-bright/5 p-3">
                    <div className="text-sm font-medium text-text-primary">{d.name}</div>
                    {d.impact && <div className="mt-1 text-xs text-text-secondary">{d.impact}</div>}
                  </div>
                ))}
                {derived.reducing.length === 0 && <div className="text-sm text-text-secondary">No reducing-risk drivers reported.</div>}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8 rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card">
          <SectionHeader eyebrow="Agent investigation timeline" title="How the intelligence was assembled" />
          <div className="grid gap-3 md:grid-cols-4">
            {derived.pipeline.map((step, index) => (
              <motion.div
                key={step.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className={`rounded-lg border p-4 ${step.complete ? "border-teal-dim bg-teal-bright/5" : "border-bg-border bg-bg-elevated"}`}
              >
                <div className="mb-3 flex items-center justify-between">
                  <span className="font-mono text-[10px] text-text-muted">{String(index + 1).padStart(2, "0")}</span>
                  {step.complete ? <CheckCircle2 className="h-4 w-4 text-teal-bright" /> : <CircleAlert className="h-4 w-4 text-text-muted" />}
                </div>
                <div className="text-sm font-medium text-text-primary">{step.label}</div>
              </motion.div>
            ))}
          </div>
        </section>

        <section className="mt-8 rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card">
          <SectionHeader eyebrow="Claim vs reality" title="Corporate statement compared with evidence-backed findings" />
          <div className="grid gap-5 lg:grid-cols-2">
            <div className="rounded-lg border border-bg-border bg-bg-elevated p-5">
              <div className="label-eyebrow mb-3">Corporate claim</div>
              <p className="font-display text-3xl italic leading-tight text-text-primary">"{report.claim}"</p>
            </div>
            <div className="space-y-3">
              {derived.contradictions.slice(0, 3).map((c) => (
                <div key={`${c.source}-${c.claim_text}`} className="rounded-lg border border-risk-high/25 bg-risk-high/5 p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-risk-high" />
                    <RiskBadge level={c.severity as RiskLevel} />
                  </div>
                  <div className="text-sm font-medium text-text-primary">{c.evidence_text}</div>
                  <div className="mt-2 font-mono text-[11px] text-text-secondary">{c.source}</div>
                </div>
              ))}
              {derived.regulatory.slice(0, 2).map((r) => (
                <div key={r.framework} className="rounded-lg border border-amber-bright/25 bg-amber-bright/5 p-4">
                  <div className="mb-1 font-medium text-text-primary">{r.framework}: {r.status}</div>
                  <div className="text-sm text-text-secondary">{r.key_gap}</div>
                </div>
              ))}
              {derived.contradictions.length === 0 && derived.regulatory.length === 0 && (
                <div className="rounded-lg border border-bg-border bg-bg-elevated p-4 text-sm text-text-secondary">
                  No contradictions or regulatory findings were included in this report.
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-5 xl:grid-cols-[1fr_0.85fr]">
          <div className="rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card">
            <SectionHeader eyebrow="Contradiction explorer" title="Highest-signal contradictions" />
            <div className="space-y-3">
              {topContradictions.map((c, index) => {
                const evidenceMatch = derived.evidence.find((e) => e.source_name === c.source || e.source_url === c.source_url);
                return (
                  <details key={`${c.claim_text}-${index}`} className="rounded-lg border border-bg-border bg-bg-elevated p-4 open:border-risk-high/30">
                    <summary className="cursor-pointer list-none">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="label-eyebrow mb-1">Contradiction {index + 1}</div>
                          <div className="max-w-2xl text-sm font-medium text-text-primary">{c.claim_text}</div>
                        </div>
                        <RiskBadge level={c.severity as RiskLevel} />
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-text-secondary md:grid-cols-3">
                        <span>Confidence: {evidenceMatch ? asPct(evidenceMatch.credibility * 100) : asPct(report.confidence)}</span>
                        <span>Evidence tier: {evidenceMatch?.source_type || "Report evidence"}</span>
                        <span>Impact: {c.impact || "Reported by backend"}</span>
                      </div>
                    </summary>
                    <div className="mt-4 border-t border-bg-border pt-4 text-sm text-text-secondary">
                      {c.evidence_text}
                      <div className="mt-2 font-mono text-[11px] text-teal-bright">{c.source_url ? sourceHost(c.source_url) : c.source}</div>
                    </div>
                  </details>
                );
              })}
              {topContradictions.length === 0 && <div className="text-sm text-text-secondary">No contradictions were reported.</div>}
            </div>
          </div>

          <div className="rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card">
            <SectionHeader eyebrow="Regulatory intelligence" title="Framework risk map" />
            <div className="mb-5 flex justify-center">
              <ArcGauge value={derived.complianceAverage ?? 0} size={190} label="COMPLIANCE" />
            </div>
            <div className="grid gap-3">
              {derived.regulatory.map((r) => (
                <div key={r.framework} className="rounded-lg border border-bg-border bg-bg-elevated p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-text-primary">{r.framework}</div>
                    <RiskBadge level={statusLevel(r.status)} />
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-bg-border">
                    <div className="h-full rounded-full bg-teal-bright" style={{ width: `${Math.max(0, Math.min(100, r.compliance_score))}%` }} />
                  </div>
                  <div className="mt-2 text-xs text-text-secondary">{r.jurisdiction} | {r.key_gap}</div>
                </div>
              ))}
              {derived.regulatory.length === 0 && <div className="text-sm text-text-secondary">No regulatory findings were included.</div>}
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-5 xl:grid-cols-2">
          <div className="rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card">
            <SectionHeader eyebrow="Carbon intelligence" title="Emissions and pathway alignment" />
            <div className="grid gap-4 md:grid-cols-3">
              <KpiCard label="Scope 1" value={`${formatNumber(report.carbon?.scope1)} tCO2e`} tone="blue" />
              <KpiCard label="Scope 2" value={`${formatNumber(report.carbon?.scope2)} tCO2e`} tone="amber" />
              <KpiCard label="Scope 3" value={`${formatNumber(report.carbon?.scope3)} tCO2e`} tone="red" />
            </div>
            <div className="mt-5 grid gap-5 lg:grid-cols-2">
              <div className="h-64 rounded-lg border border-bg-border bg-bg-elevated p-4">
                {carbonBreakdown.length > 0 ? (
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={carbonBreakdown} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85}>
                        {carbonBreakdown.map((entry, index) => (
                          <Cell key={entry.name} fill={["hsl(var(--blue-bright))", "hsl(var(--amber-bright))", "hsl(var(--risk-high))"][index % 3]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value: number) => `${formatNumber(value)} tCO2e`} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-text-secondary">No emissions breakdown available.</div>
                )}
              </div>
              <div className="rounded-lg border border-bg-border bg-bg-elevated p-4">
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between"><span className="text-text-secondary">Net zero target</span><span className="font-medium text-text-primary">{report.carbon?.net_zero_target || "Unavailable"}</span></div>
                  <div className="flex items-center justify-between"><span className="text-text-secondary">Pathway status</span><span className="font-medium text-text-primary">{report.carbon?.alignment_status || "Unavailable"}</span></div>
                  <div className="flex items-center justify-between"><span className="text-text-secondary">Climate TRACE</span><span className="font-medium text-text-primary">{report.carbon?.data_quality ? asPct(report.carbon.data_quality * 100) : "Unavailable"}</span></div>
                  <div className="flex items-center justify-between"><span className="text-text-secondary">Budget remaining</span><span className="font-medium text-text-primary">{typeof report.carbon?.budget_years_remaining === "number" ? `${report.carbon.budget_years_remaining.toFixed(2)} years` : "Unavailable"}</span></div>
                </div>
                {carbonAlignment.length > 0 && (
                  <div className="mt-5 h-32">
                    <ResponsiveContainer>
                      <BarChart data={carbonAlignment}>
                        <XAxis dataKey="name" stroke="hsl(var(--text-muted))" tick={{ fontSize: 11 }} />
                        <YAxis stroke="hsl(var(--text-muted))" tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Bar dataKey="value" fill="hsl(var(--teal-bright))" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card">
            <SectionHeader eyebrow="Evidence intelligence" title="Source quality and stance distribution" />
            <div className="grid gap-4 md:grid-cols-3">
              <KpiCard label="Supporting" value={derived.supportCount} tone="teal" />
              <KpiCard label="Contradicting" value={derived.contradictCount} tone="red" />
              <KpiCard label="Neutral" value={Math.max(0, derived.neutralCount)} tone="blue" />
            </div>
            <div className="mt-5 grid gap-5 lg:grid-cols-2">
              <div className="h-56 rounded-lg border border-bg-border bg-bg-elevated p-4">
                {derived.sourceMix.length > 0 ? (
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={derived.sourceMix} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75}>
                        {derived.sourceMix.map((entry, index) => (
                          <Cell key={entry.name} fill={["hsl(var(--teal-bright))", "hsl(var(--risk-high))", "hsl(var(--blue-bright))"][index % 3]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-text-secondary">No evidence stance data.</div>
                )}
              </div>
              <div className="space-y-3">
                {derived.evidenceQuality.map((item) => (
                  <div key={item.name} className="rounded-md border border-bg-border bg-bg-elevated p-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-text-primary">{item.name} credibility</span>
                      <span className="font-mono text-teal-bright">{item.value}</span>
                    </div>
                  </div>
                ))}
                {derived.sourceTypes.slice(0, 5).map((item) => (
                  <div key={item.name} className="flex items-center justify-between text-xs text-text-secondary">
                    <span>{item.name}</span>
                    <span className="font-mono">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card">
            <SectionHeader eyebrow="ESG vs greenwashing" title="Strong ESG signals can still mask claim risk" />
            <div className="grid grid-cols-2 gap-5">
              <div className="rounded-lg border border-bg-border bg-bg-elevated p-4 text-center">
                <ArcGauge value={report.esg_score} size={190} label="ESG SCORE" />
                <div className="mt-2 font-display text-3xl text-teal-bright">{report.rating_grade}</div>
              </div>
              <div className="rounded-lg border border-risk-high/30 bg-risk-high/5 p-4 text-center">
                <ArcGauge value={report.greenwashing.overall_score} size={190} label="GW RISK" />
                <div className="mt-2">
                  <RiskBadge level={riskLevel(report.greenwashing.overall_score)} />
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-bg-border bg-bg-surface p-6 shadow-card">
            <SectionHeader eyebrow="Executive summary" title="Decision-ready interpretation" />
            <div className="rounded-lg border border-bg-border bg-bg-elevated p-5">
              <div className="label-eyebrow mb-2">One-line verdict</div>
              <p className="font-display text-3xl italic leading-tight text-text-primary">{report.ai_verdict || report.executive_summary}</p>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-bg-border bg-bg-elevated p-4">
                <FileSearch className="mb-2 h-5 w-5 text-teal-bright" />
                <div className="text-sm font-medium text-text-primary">Key findings</div>
                <div className="mt-1 text-xs text-text-secondary">{report.top_risk_drivers?.[0]?.name || report.executive_summary || "No findings provided."}</div>
              </div>
              <div className="rounded-lg border border-bg-border bg-bg-elevated p-4">
                <ShieldAlert className="mb-2 h-5 w-5 text-risk-high" />
                <div className="text-sm font-medium text-text-primary">Key concerns</div>
                <div className="mt-1 text-xs text-text-secondary">{derived.contradictions[0]?.impact || derived.regulatory[0]?.key_gap || "No concerns provided."}</div>
              </div>
              <div className="rounded-lg border border-bg-border bg-bg-elevated p-4">
                <Target className="mb-2 h-5 w-5 text-amber-bright" />
                <div className="text-sm font-medium text-text-primary">Investigate next</div>
                <div className="mt-1 text-xs text-text-secondary">{derived.regulatory[0]?.framework || derived.evidence[0]?.source_name || "Review full audit report."}</div>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <Link
                to={`/report?id=${encodeURIComponent(report.id)}`}
                className="inline-flex items-center gap-2 rounded-md bg-teal-bright px-5 py-3 text-sm font-medium text-bg-void shadow-card hover:opacity-90"
              >
                View Full Audit Report <ArrowUpRight className="h-4 w-4" />
              </Link>
              <Link
                to="/reports"
                className="inline-flex items-center gap-2 rounded-md border border-bg-border px-5 py-3 text-sm font-medium text-text-primary hover:border-teal-dim"
              >
                Reports Library
              </Link>
            </div>
          </div>
        </section>

        <div className="mt-8 grid gap-3 md:grid-cols-5">
          {[
            { icon: Gauge, label: "Scores", value: `${report.esg_score.toFixed(1)} / ${report.greenwashing.overall_score.toFixed(1)}` },
            { icon: Layers, label: "Artifacts", value: String(derived.artifactCount) },
            { icon: Scale, label: "Frameworks", value: String(derived.regulatory.length) },
            { icon: BarChart3, label: "Evidence", value: String(derived.evidence.length) },
            { icon: AlertTriangle, label: "Contradictions", value: String(derived.contradictions.length) },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-bg-border bg-bg-surface p-4">
              <item.icon className="mb-2 h-4 w-4 text-teal-bright" />
              <div className="label-eyebrow">{item.label}</div>
              <div className="mt-1 font-display text-2xl text-text-primary">{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </PageWrapper>
  );
}
