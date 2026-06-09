import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Download, RotateCw, GitCompare, ArrowRight, Search } from "lucide-react";
import { PageWrapper } from "@/components/layout/PageWrapper";
import { ArcGauge } from "@/components/charts/ArcGauge";
import { RiskBadge } from "@/components/cards/RiskBadge";
import type { ReportData } from "@/types/report";
import { getAllReports, HistoryEntry } from "@/lib/api";

function apiHistoryToReportData(api: HistoryEntry): ReportData {
  return {
    id: api.id,
    company: api.company,
    ticker: api.ticker,
    sector: api.sector,
    jurisdiction: "Global",
    date: api.analysis_date?.split("T")[0] || "",
    duration: `${Math.round(api.duration_seconds / 60)}m ${Math.round(api.duration_seconds % 60)}s`,
    agentsRun: `${api.agents_run}`,
    esgScore: api.esg_score,
    rating: api.rating_grade,
    riskLevel: api.risk_level as "HIGH" | "MEDIUM" | "LOW",
    pillars: { e: 0, s: 0, g: 0 },
    greenwashing: api.greenwashing_risk,
    confidence: api.confidence,
    scope1: 0, scope2: 0, scope3: 0,
    netZeroTarget: "",
    carbonBudgetYears: 0,
    claim: api.claim,
    verdict: api.risk_level === "HIGH" ? "CONTRADICTED" : "SUPPORTED",
    summary: api.ai_verdict_short,
    topFindings: [],
    contradictions: Array.from({ length: api.contradictions_count }).map(() => ({
      severity: "HIGH", claim: "", evidence: "See full report", source: "Backend", impact: "", kind: "data"
    })),
    regulatory: [],
    regulatoryOverall: 0,
    peers: [],
    evidence: [],
  };
}

function dotColor(level: string) {
  if (level === "HIGH") return "bg-risk-high";
  if (level === "MEDIUM") return "bg-amber-bright";
  return "bg-risk-low";
}
function borderColor(level: string) {
  if (level === "HIGH") return "border-l-risk-high";
  if (level === "MEDIUM") return "border-l-amber-bright";
  return "border-l-risk-low";
}
function findingIcon(kind: string) {
  if (kind === "red") return "RED";
  if (kind === "amber") return "AMBER";
  return "GREEN";
}

function CompareTable({ a, b }: { a: ReportData; b: ReportData }) {
  const rows: { label: string; va: string; vb: string; better?: "a" | "b" | null; higherIsBetter: boolean }[] = [
    { label: "ESG Score", va: `${a.esgScore} / ${a.rating}`, vb: `${b.esgScore} / ${b.rating}`, higherIsBetter: true, better: a.esgScore > b.esgScore ? "a" : b.esgScore > a.esgScore ? "b" : null },
    { label: "Greenwashing Risk", va: `${a.greenwashing}% ${a.riskLevel}`, vb: `${b.greenwashing}% ${b.riskLevel}`, higherIsBetter: false, better: a.greenwashing < b.greenwashing ? "a" : b.greenwashing < a.greenwashing ? "b" : null },
    { label: "Environmental", va: String(a.pillars.e), vb: String(b.pillars.e), higherIsBetter: true, better: a.pillars.e > b.pillars.e ? "a" : "b" },
    { label: "Social", va: String(a.pillars.s), vb: String(b.pillars.s), higherIsBetter: true, better: a.pillars.s > b.pillars.s ? "a" : "b" },
    { label: "Governance", va: String(a.pillars.g), vb: String(b.pillars.g), higherIsBetter: true, better: a.pillars.g > b.pillars.g ? "a" : "b" },
    { label: "Scope 3 Emissions", va: a.scope3 >= 1e9 ? `${(a.scope3 / 1e9).toFixed(2)}B tCO2e` : `${(a.scope3 / 1e6).toFixed(0)}M tCO2e`, vb: b.scope3 >= 1e9 ? `${(b.scope3 / 1e9).toFixed(2)}B tCO2e` : `${(b.scope3 / 1e6).toFixed(0)}M tCO2e`, higherIsBetter: false, better: a.scope3 < b.scope3 ? "a" : "b" },
    { label: "Contradictions", va: `${a.contradictions.length} HIGH`, vb: `${b.contradictions.length} HIGH`, higherIsBetter: false, better: null },
    { label: "Regulatory Score", va: `${a.regulatoryOverall}/100`, vb: `${b.regulatoryOverall}/100`, higherIsBetter: true, better: a.regulatoryOverall > b.regulatoryOverall ? "a" : "b" },
    { label: "Confidence", va: `${a.confidence}%`, vb: `${b.confidence}%`, higherIsBetter: true, better: a.confidence > b.confidence ? "a" : "b" },
  ];

  const cellClass = (side: "a" | "b", better: "a" | "b" | null | undefined) => {
    if (!better) return "bg-bg-surface";
    if (better === side) return "bg-green-light text-green-bright";
    return "bg-red-light/60 text-risk-high";
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -8, height: 0 }}
      animate={{ opacity: 1, y: 0, height: "auto" }}
      exit={{ opacity: 0, y: -8, height: 0 }}
      className="overflow-hidden"
    >
      <div className="rounded-xl border border-bg-border bg-bg-surface shadow-card-lg p-6 my-4">
        <div className="flex items-center gap-2 mb-5">
          <GitCompare className="h-4 w-4 text-green-bright" />
          <span className="label-eyebrow text-green-bright">SIDE-BY-SIDE COMPARISON</span>
        </div>
        <div className="grid grid-cols-[1fr_1fr_1fr] gap-px bg-bg-border rounded-lg overflow-hidden text-sm">
          <div className="bg-bg-elevated px-4 py-3 font-mono text-[11px] text-text-secondary">METRIC</div>
          <div className="bg-bg-elevated px-4 py-3 font-display text-text-primary">{a.company}</div>
          <div className="bg-bg-elevated px-4 py-3 font-display text-text-primary">{b.company}</div>
          {rows.map((r) => (
            <>
              <div key={r.label + "-l"} className="bg-bg-surface px-4 py-3 text-text-secondary">{r.label}</div>
              <div className={`px-4 py-3 font-mono ${cellClass("a", r.better)}`}>{r.va}</div>
              <div className={`px-4 py-3 font-mono ${cellClass("b", r.better)}`}>{r.vb}</div>
            </>
          ))}
        </div>
        <p className="mt-5 text-sm text-text-secondary leading-relaxed border-l-2 border-green-bright pl-4">
          <span className="font-medium text-text-primary">{b.ticker} scores higher on Social ({b.pillars.s} vs {a.pillars.s}) and overall ESG ({b.esgScore} vs {a.esgScore}).</span>{" "}
          {a.ticker} has lower greenwashing risk ({a.greenwashing}% vs {b.greenwashing}%). Both rate HIGH risk with multiple verified contradictions.
        </p>
      </div>
    </motion.div>
  );
}

function HistoryCard({ r, others, onCompare, comparingWith, onCloseCompare }: {
  r: ReportData;
  others: ReportData[];
  onCompare: (id: string) => void;
  comparingWith: ReportData | null;
  onCloseCompare: () => void;
}) {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="relative pl-12">
      {/* node + connector */}
      <div className={`absolute left-0 top-7 h-3 w-3 rounded-full ring-4 ring-bg-deep ${dotColor(r.riskLevel)}`} />
      <div className="absolute left-3 top-8 h-px w-9 bg-border" />

      <div className={`absolute -left-12 top-7 -translate-x-2 text-right font-mono text-[10px] text-text-muted w-24 hidden md:block`}>
        {r.date}
      </div>

      <div className={`rounded-xl bg-bg-surface border border-bg-border border-l-4 ${borderColor(r.riskLevel)} shadow-card hover:shadow-card-hover transition`}>
        <button onClick={() => setOpen((o) => !o)} className="w-full text-left px-5 py-4 grid grid-cols-1 md:grid-cols-[1.4fr_auto_auto] gap-4 items-center">
          <div className="flex items-center gap-3">
            <div className={`h-11 w-11 rounded-lg flex items-center justify-center font-display text-lg
              ${r.riskLevel === "HIGH" ? "bg-risk-high/15 text-risk-high" : r.riskLevel === "MEDIUM" ? "bg-amber-bright/15 text-amber-bright" : "bg-risk-low/15 text-risk-low"}`}>
              {r.ticker.slice(0, 2)}
            </div>
            <div>
              <div className="font-display text-lg text-text-primary leading-tight">{r.company}</div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="font-mono text-[10px] text-text-secondary">{r.ticker}</span>
                <span className="text-text-muted">|</span>
                <span className="text-[10px] uppercase tracking-wider text-text-secondary">{r.sector}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-center">
            <ArcGauge value={r.esgScore} size={100} />
          </div>

          <div className="flex items-center gap-3 justify-end">
            <div className="text-right">
              <RiskBadge level={r.riskLevel as any} />
              <div className="font-display text-xl text-text-primary mt-1">{r.rating}</div>
              <div className="font-mono text-[10px] text-text-secondary">GW {r.greenwashing}%</div>
            </div>
            <ChevronDown className={`h-4 w-4 text-text-muted transition ${open ? "rotate-180" : ""}`} />
          </div>
        </button>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden border-t border-bg-border"
            >
              <div className="grid grid-cols-1 lg:grid-cols-[55%_45%] gap-6 p-6">
                {/* LEFT */}
                <div className="space-y-4">
                  <div>
                    <div className="label-eyebrow mb-1.5">CLAIM ANALYSED</div>
                    <p className="italic text-text-secondary text-sm leading-relaxed">"{r.claim}"</p>
                  </div>
                  <div>
                    <div className="label-eyebrow mb-1.5">AI VERDICT</div>
                    <p className="text-sm text-text-primary leading-relaxed">{r.summary}</p>
                  </div>
                  <div>
                    <div className="label-eyebrow mb-2">TOP FINDINGS</div>
                    <ul className="space-y-1.5">
                      {r.topFindings.map((f, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-text-primary">
                          <span className="mt-0.5">{findingIcon(f.kind)}</span>
                          <span className="leading-relaxed">{f.text}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="font-mono text-[11px] text-text-muted pt-2 border-t border-bg-border">
                    {r.agentsRun} AGENTS | {r.duration} | CONFIDENCE {r.confidence}%
                  </div>
                </div>

                {/* RIGHT */}
                <div className="space-y-4">
                  <div>
                    <div className="label-eyebrow mb-3">ESG PILLARS</div>
                    <div className="space-y-2">
                      {[
                        { l: "Environmental", v: r.pillars.e, c: "bg-green-bright" },
                        { l: "Social", v: r.pillars.s, c: "bg-blue-bright" },
                        { l: "Governance", v: r.pillars.g, c: "bg-navy-mid" },
                      ].map((p) => (
                        <div key={p.l}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-text-secondary">{p.l}</span>
                            <span className="font-mono text-text-primary">{p.v}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                            <div className={`h-full ${p.c}`} style={{ width: `${p.v}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-bg-elevated p-3 text-center">
                      <div className="label-eyebrow mb-1">GREENWASHING</div>
                      <ArcGauge value={r.greenwashing} size={90} />
                    </div>
                    <div className="rounded-lg bg-risk-high/8 border border-risk-high/30 p-3 text-center flex flex-col justify-center">
                      <div className="label-eyebrow text-risk-high mb-1">CONTRADICTIONS</div>
                      <div className="font-display text-4xl text-risk-high leading-none">{r.contradictions.length}</div>
                      <div className="font-mono text-[10px] text-risk-high mt-1">HIGH SEVERITY</div>
                    </div>
                  </div>

                  <div className="rounded-lg bg-bg-elevated p-3">
                    <div className="label-eyebrow mb-1.5">KEY CONTRADICTION</div>
                    <p className="text-xs text-text-primary leading-relaxed">{r.contradictions[0]?.evidence}</p>
                    <p className="font-mono text-[10px] text-text-secondary mt-2">{r.contradictions[0]?.source}</p>
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="flex flex-wrap items-center gap-2 px-6 pb-5">
                <button onClick={() => nav(`/report?id=${encodeURIComponent(r.id)}`)} className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-green-bright text-white text-sm font-medium hover:bg-green-mid transition">
                  View Full Report <ArrowRight className="h-3.5 w-3.5" />
                </button>
                <button onClick={() => nav("/pipeline")} className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-green-dim text-green-bright text-sm hover:bg-green-light transition">
                  <RotateCw className="h-3.5 w-3.5" /> Re-run
                </button>
                <button className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-bg-border text-text-secondary text-sm hover:border-border-strong transition">
                  <Download className="h-3.5 w-3.5" /> Export PDF
                </button>
                <div className="relative ml-auto">
                  <button onClick={() => setShowMenu((s) => !s)} className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-bg-border text-text-secondary text-sm hover:border-border-strong transition">
                    <GitCompare className="h-3.5 w-3.5" /> Compare with... <ChevronDown className="h-3 w-3" />
                  </button>
                  {showMenu && (
                    <div className="absolute right-0 mt-1 w-56 rounded-lg bg-bg-surface border border-bg-border shadow-card-lg z-10 overflow-hidden">
                      {others.length === 0 ? (
                        <div className="px-4 py-3 text-xs text-text-muted">No other analyses yet</div>
                      ) : (
                        others.map((o) => (
                          <button
                            key={o.id}
                            onClick={() => { onCompare(o.id); setShowMenu(false); }}
                            className="w-full text-left px-4 py-2.5 text-sm hover:bg-bg-subtle flex items-center justify-between"
                          >
                            <span className="text-text-primary">{o.company}</span>
                            <span className="font-mono text-[10px] text-text-secondary">{o.ticker}</span>
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {comparingWith && (
          <div className="relative">
            <CompareTable a={r} b={comparingWith} />
            <button onClick={onCloseCompare} className="absolute top-2 right-2 text-xs text-text-muted hover:text-text-primary">Close x</button>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function History() {
  const nav = useNavigate();
  const [query, setQuery] = useState("");
  const [risk, setRisk] = useState("All");
  const [sector, setSector] = useState("All");
  const [view, setView] = useState<"list" | "grid">("list");
  const [compareMap, setCompareMap] = useState<Record<string, string | null>>({});
  const [historyList, setHistoryList] = useState<ReportData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getAllReports()
      .then((data) => {
        setHistoryList(data.map(apiHistoryToReportData));
      })
      .catch((err) => {
        setError(err?.message || "Failed to load history from API");
        setHistoryList([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const sectors = useMemo(() => ["All", ...Array.from(new Set(historyList.map((r) => r.sector)))], [historyList]);

  const filtered = historyList.filter((r) => {
    if (query && !`${r.company} ${r.ticker}`.toLowerCase().includes(query.toLowerCase())) return false;
    if (risk !== "All" && r.riskLevel !== risk) return false;
    if (sector !== "All" && r.sector !== sector) return false;
    return true;
  });

  const avgGw = historyList.length ? (historyList.reduce((s, r) => s + r.greenwashing, 0) / historyList.length).toFixed(1) : "0";
  const highCount = historyList.filter((r) => r.riskLevel === "HIGH").length;

  const stats = [
    { label: "Total analyses run", v: historyList.length },
    { label: "Companies analysed", v: historyList.length },
    { label: "High risk findings", v: `${highCount} / ${historyList.length}` },
    { label: "Avg greenwashing", v: `${avgGw}%` },
  ];

  return (
    <PageWrapper className="grid-bg">
      <div className="px-10 py-12 max-w-6xl mx-auto">
        <div className="mb-10">
          <div className="label-eyebrow text-green-bright mb-3">ANALYSIS HISTORY</div>
          <h1 className="font-display text-5xl text-navy-deep leading-tight">Analysis History</h1>
          <p className="text-text-secondary mt-3 max-w-xl">All previous pipeline runs - click any entry to view the full report.</p>
        </div>

        {error && (
          <div className="mb-8 rounded-lg border border-risk-high/30 bg-risk-high/10 px-4 py-3 text-sm text-risk-high">
            {error}
          </div>
        )}

        {loading && (
          <div className="mb-8 text-sm font-mono text-text-secondary">Loading history from backend...</div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {stats.map((s) => (
            <div key={s.label} className="rounded-xl bg-bg-surface border border-bg-border shadow-card p-5">
              <div className="font-display text-3xl text-green-bright">{s.v}</div>
              <div className="label-eyebrow mt-1">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="rounded-xl bg-bg-surface border border-bg-border shadow-card p-4 mb-10 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-[200px] px-3 h-10 rounded-md border border-bg-border focus-within:border-green-bright transition">
            <Search className="h-4 w-4 text-text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search companies..."
              className="flex-1 bg-transparent outline-none text-sm text-text-primary placeholder:text-text-muted"
            />
          </div>
          <select value={risk} onChange={(e) => setRisk(e.target.value)} className="h-10 px-3 rounded-md border border-bg-border bg-bg-surface text-sm text-text-primary">
            {["All", "HIGH", "MEDIUM", "LOW"].map((r) => <option key={r}>{r}</option>)}
          </select>
          <select value={sector} onChange={(e) => setSector(e.target.value)} className="h-10 px-3 rounded-md border border-bg-border bg-bg-surface text-sm text-text-primary">
            {sectors.map((s) => <option key={s}>{s}</option>)}
          </select>
          <div className="flex items-center rounded-md border border-bg-border overflow-hidden text-xs">
            {(["list", "grid"] as const).map((v) => (
              <button key={v} onClick={() => setView(v)} className={`px-3 h-10 capitalize ${view === v ? "bg-green-light text-green-bright" : "text-text-secondary hover:bg-bg-subtle"}`}>
                {v}
              </button>
            ))}
          </div>
        </div>

        {/* Empty state */}
        {filtered.length === 0 && (
          <div className="rounded-xl border border-dashed border-bg-border p-16 text-center">
            <div className="text-5xl mb-3">WAIT</div>
            <p className="text-text-secondary mb-4">No analyses match your filters.</p>
            <button onClick={() => nav("/analyse")} className="px-4 py-2 rounded-md bg-green-bright text-white font-medium">Start New Analysis</button>
          </div>
        )}

        {/* Timeline */}
        {view === "list" && filtered.length > 0 && (
          <div className="relative space-y-6 before:content-[''] before:absolute before:left-1.5 before:top-0 before:bottom-0 before:w-px before:bg-border">
            {filtered.map((r) => {
              const cmpId = compareMap[r.id];
              const cmp = cmpId ? historyList.find((x) => x.id === cmpId) || null : null;
              return (
                <HistoryCard
                  key={r.id}
                  r={r}
                  others={historyList.filter((x) => x.id !== r.id)}
                  onCompare={(id) => setCompareMap((m) => ({ ...m, [r.id]: id }))}
                  comparingWith={cmp}
                  onCloseCompare={() => setCompareMap((m) => ({ ...m, [r.id]: null }))}
                />
              );
            })}
          </div>
        )}

        {view === "grid" && filtered.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {filtered.map((r) => (
              <button
                key={r.id}
                onClick={() => nav(`/report?id=${encodeURIComponent(r.id)}`)}
                className={`text-left rounded-xl bg-bg-surface border border-bg-border border-l-4 ${borderColor(r.riskLevel)} shadow-card hover:shadow-card-hover p-5 transition`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="font-display text-lg">{r.company}</div>
                    <div className="font-mono text-[10px] text-text-secondary">{r.ticker} | {r.date}</div>
                  </div>
                  <RiskBadge level={r.riskLevel as any} />
                </div>
                <div className="flex justify-center my-3"><ArcGauge value={r.esgScore} size={120} /></div>
                <p className="text-xs text-text-secondary line-clamp-2">{r.summary}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
