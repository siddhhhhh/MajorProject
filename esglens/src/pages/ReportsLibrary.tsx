import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageWrapper } from "@/components/layout/PageWrapper";
import { ArcGauge } from "@/components/charts/ArcGauge";
import { RiskBadge } from "@/components/cards/RiskBadge";
import { Download, Share2, RotateCw } from "lucide-react";
import { getAllReports, HistoryEntry } from "@/lib/api";

type ReportCard = {
  id: string;
  name: string;
  ticker: string;
  risk: string;
  esg: number;
  summary: string;
  date: string;
  sector: string;
};

export default function ReportsLibrary() {
  const nav = useNavigate();
  const [reports, setReports] = useState<ReportCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("All");

  useEffect(() => {
    setLoading(true);
    setError(null);
    getAllReports()
      .then((data) => {
        const mapped = data.map((r: HistoryEntry) => ({
          id: r.id,
          name: r.company,
          ticker: r.ticker,
          risk: r.risk_level,
          esg: r.esg_score,
          summary: r.ai_verdict_short,
          date: r.analysis_date?.split("T")[0] || "",
          sector: r.sector,
        }));
        setReports(mapped);
      })
      .catch((err) => {
        setError(err?.message || "Failed to load reports from API");
        setReports([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const filteredReports = reports.filter(r => {
    if (filter === "All") return true;
    if (["HIGH", "MEDIUM", "LOW"].includes(filter)) return r.risk === filter;
    return r.sector === filter;
  });
  return (
    <PageWrapper className="grid-bg">
      <div className="px-10 py-12">
        <div className="flex items-end justify-between mb-10">
          <div>
            <div className="label-eyebrow text-teal-bright mb-3">REPORTS LIBRARY</div>
            <h1 className="font-display text-5xl">All analyses</h1>
          </div>
          <button onClick={() => nav("/analyse")} className="px-4 py-2 rounded-md bg-teal-bright text-bg-void font-medium glow-teal">+ New Analysis</button>
        </div>

        {error && (
          <div className="mb-8 rounded-lg border border-risk-high/30 bg-risk-high/10 px-4 py-3 text-sm text-risk-high">
            {error}
          </div>
        )}

        {loading && (
          <div className="mb-8 text-sm font-mono text-text-secondary">Loading reports from backend…</div>
        )}

        <div className="flex flex-wrap gap-2 mb-8">
          {(["All", ...Array.from(new Set(reports.map((r) => r.sector))).sort(), "HIGH", "MEDIUM", "LOW"] as string[]).map((f) => (
            <button 
              key={f} 
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-full border text-xs font-mono transition ${filter === f ? "bg-teal-bright/15 text-teal-bright border-teal-bright/40" : "border-bg-border text-text-secondary hover:border-teal-dim hover:text-teal-bright"}`}
            >
              {f}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredReports.map((c, i) => (
            <div key={c.id || i} className="rounded-xl bg-bg-surface border border-bg-border p-5 hover:border-teal-dim transition">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="font-medium">{c.name}</div>
                  <div className="font-mono text-[10px] text-text-secondary">{c.ticker} · {c.date || `2025-04-${(i % 28) + 1}`}</div>
                </div>
                <RiskBadge level={c.risk as any} />
              </div>
              <div className="flex justify-center my-3"><ArcGauge value={c.esg} size={120} /></div>
              <p className="text-xs text-text-secondary line-clamp-2 mb-4">{c.summary}</p>
              <div className="flex items-center justify-between">
                <button onClick={() => nav(`/report?id=${c.id}`)} className="text-xs text-teal-bright hover:underline">View →</button>
                <div className="flex gap-1.5">
                  {[Download, Share2, RotateCw].map((Icon, j) => (
                    <button key={j} onClick={() => j === 0 ? window.print() : null} className="h-7 w-7 rounded-md bg-bg-elevated hover:bg-teal-bright/10 flex items-center justify-center transition">
                      <Icon className="h-3.5 w-3.5 text-text-secondary" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>

        {!loading && filteredReports.length === 0 && !error && (
          <div className="text-sm text-text-secondary">No reports found in the backend yet.</div>
        )}
      </div>
    </PageWrapper>
  );
}
