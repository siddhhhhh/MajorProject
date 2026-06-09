import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Search, Crosshair, ArrowUpRight, Activity, Paperclip } from "lucide-react";
import { Globe3D } from "@/components/three/Globe3D";
import { PageWrapper } from "@/components/layout/PageWrapper";
import { ArcGauge } from "@/components/charts/ArcGauge";
import { RiskBadge } from "@/components/cards/RiskBadge";
import { RECENT_ANALYSES, AGENTS } from "@/data/demo";
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer } from "recharts";

const PLACEHOLDERS = [
  "Analyse Shell's net zero claim...",
  "Score Unilever ESG 2025...",
  "Check BP greenwashing risk...",
  "Verify Tesco carbon neutral 2035...",
];

function TypewriterPlaceholder() {
  const [idx, setIdx] = useState(0);
  const [text, setText] = useState("");
  useEffect(() => {
    const target = PLACEHOLDERS[idx];
    let i = 0;
    const id = setInterval(() => {
      i++;
      setText(target.slice(0, i));
      if (i >= target.length) {
        clearInterval(id);
        setTimeout(() => setIdx((p) => (p + 1) % PLACEHOLDERS.length), 1800);
      }
    }, 45);
    return () => clearInterval(id);
  }, [idx]);
  return <span className="text-text-muted">{text}<span className="animate-blink">|</span></span>;
}

function Counter({ to, prefix = "", suffix = "" }: { to: number; prefix?: string; suffix?: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const start = performance.now();
    const dur = 1200;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(to * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  const display = to >= 1000 ? Math.round(n).toLocaleString() : n < 100 ? n.toFixed(1) : Math.round(n);
  return <span>{prefix}{display}{suffix}</span>;
}

const RADAR_DATA = [
  { axis: "TCFD", co: 62, avg: 58 },
  { axis: "FCA", co: 31, avg: 64 },
  { axis: "SECR", co: 71, avg: 60 },
  { axis: "GHG", co: 58, avg: 62 },
  { axis: "SBTi", co: 22, avg: 55 },
  { axis: "SFDR", co: 41, avg: 52 },
];

export default function Dashboard() {
  const nav = useNavigate();
  const openFile = () => {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.multiple = true;
    inp.accept = ".pdf,.txt,.csv,.docx";
    inp.onchange = () => nav("/analyse");
    inp.click();
  };
  return (
    <PageWrapper>
      {/* HERO */}
      <section className="relative h-[88vh] hero-bloom grid-bg flex items-center justify-center overflow-hidden">
        <Globe3D />
        <div className="absolute inset-0 bg-gradient-to-b from-bg-deep/30 via-transparent to-bg-deep" />
        <div className="relative z-10 w-full max-w-4xl px-8 text-center">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
            <div className="label-eyebrow text-green-bright mb-6"> ESG INTELLIGENCE PLATFORM</div>
            <h1 className="font-display text-6xl md:text-7xl leading-[1.05] mb-6 text-navy-deep">
              ESG <span className="italic text-gradient-teal">Intelligence</span>
            </h1>
            <p className="text-text-secondary text-lg max-w-2xl mx-auto mb-10">
              36-agent analysis. Real-time contradictions. Carbon pathways. UK regulatory alignment.
            </p>
          </motion.div>

          <motion.form
            onSubmit={(e) => { e.preventDefault(); nav("/pipeline"); }}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.6 }}
            className="relative max-w-2xl mx-auto"
          >
            <div className="flex items-center gap-3 h-14 px-5 rounded-xl glass border-teal-dim/40 hover:border-teal-bright/60 focus-within:border-teal-bright focus-within:shadow-[0_0_0_3px_hsl(var(--teal-bright)/0.15)] transition">
              <Search className="h-5 w-5 text-teal-bright shrink-0" />
              <input
                className="flex-1 bg-transparent outline-none text-text-primary placeholder:text-transparent"
                placeholder="Analyse..."
              />
              {/* fake placeholder */}
              <div className="absolute left-[60px] pointer-events-none text-sm">
                <TypewriterPlaceholder />
              </div>
              <span className="hidden md:inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-mono bg-amber-bright/15 text-amber-bright border border-amber-bright/30">UK | FCA</span>
              <button type="button" onClick={(e) => { e.preventDefault(); openFile(); }} className="h-9 w-9 rounded-lg text-text-secondary hover:text-teal-bright hover:bg-teal-bright/10 flex items-center justify-center transition" aria-label="Attach files">
                <Paperclip className="h-4 w-4" />
              </button>
              <button type="submit" className="h-10 w-10 rounded-full bg-teal-bright text-bg-void flex items-center justify-center hover:scale-105 active:scale-95 transition glow-teal">
                <Crosshair className="h-4 w-4" />
              </button>
            </div>
          </motion.form>

          <div className="flex flex-wrap gap-2 justify-center mt-5">
            {["Shell | net zero 2050", "Barclays | sustainable finance", "Tesco | carbon neutral 2035"].map((s) => (
              <button key={s} onClick={() => nav("/pipeline")} className="text-xs px-3 py-1.5 rounded-full border border-bg-border text-text-secondary hover:text-teal-bright hover:border-teal-dim transition font-mono">
                {s}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* STATS */}
      <section className="px-10 py-16 border-y border-bg-border">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 max-w-6xl mx-auto">
          {[
            { v: 1847, label: "Companies Analysed" },
            { v: 94.2, label: "Pipeline Success", suffix: "%" },
            { v: 2.3, label: "AUM Using ESGLens", prefix: "GBP", suffix: "T" },
            { v: 36, label: "Agents Per Analysis" },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <div className="font-display text-5xl text-teal-bright mb-2">
                <Counter to={s.v} prefix={s.prefix} suffix={s.suffix} />
              </div>
              <div className="label-eyebrow">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* RECENT + LIVE */}
      <section className="px-10 py-16">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="label-eyebrow text-teal-bright mb-2">RECENT INTELLIGENCE</div>
            <h2 className="font-display text-4xl">Latest analyses</h2>
          </div>
          <button onClick={() => nav("/reports")} className="text-sm text-teal-bright hover:underline flex items-center gap-1">
            View all <ArrowUpRight className="h-4 w-4" />
          </button>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-8">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {RECENT_ANALYSES.map((c, i) => (
              <motion.button
                key={c.ticker}
                onClick={() => nav("/report")}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                whileHover={{ y: -4 }}
                className="group text-left rounded-xl bg-bg-surface border border-bg-border p-5 hover:border-teal-dim hover:glow-teal transition-all"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={`h-10 w-10 rounded-lg flex items-center justify-center font-display text-lg
                      ${c.risk === "HIGH" ? "bg-risk-high/15 text-risk-high" : c.risk === "MEDIUM" ? "bg-risk-medium/15 text-risk-medium" : "bg-risk-low/15 text-risk-low"}`}>
                      {c.ticker.slice(0, 2)}
                    </div>
                    <div>
                      <div className="font-medium text-text-primary">{c.name}</div>
                      <div className="font-mono text-[10px] text-text-secondary">{c.ticker}</div>
                    </div>
                  </div>
                  <RiskBadge level={c.risk as any} />
                </div>

                <div className="flex justify-center my-2">
                  <ArcGauge value={c.esg} size={140} label="ESG SCORE" />
                </div>

                <div className="flex gap-2 my-4 justify-center">
                  {[
                    { l: "E", v: c.e, color: "teal-bright" },
                    { l: "S", v: c.s, color: "amber-bright" },
                    { l: "G", v: c.g, color: "risk-low" },
                  ].map((p) => (
                    <span key={p.l} className="text-[11px] font-mono px-2 py-1 rounded-md bg-bg-elevated border border-bg-border">
                      <span className="text-text-secondary">{p.l} | </span><span className="text-text-primary">{p.v}</span>
                    </span>
                  ))}
                </div>

                <p className="text-xs text-text-secondary leading-relaxed line-clamp-2">{c.summary}</p>
              </motion.button>
            ))}
          </div>

          {/* Live pipeline panel */}
          <aside className="rounded-xl bg-bg-surface border border-bg-border p-5 h-fit lg:sticky lg:top-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="label-eyebrow">PIPELINE STATUS</div>
                <div className="font-display text-xl mt-1">Live activity</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-risk-minimal pulse-dot text-risk-minimal" />
                <span className="text-[10px] font-mono text-risk-minimal">LIVE</span>
              </div>
            </div>
            <div className="font-mono text-[11px] space-y-1.5 max-h-[420px] overflow-y-auto scrollbar-thin">
              {AGENTS.slice(0, 18).map((a, i) => {
                const status = i < 12 ? "OK" : i < 14 ? "RUN" : "WAIT";
                const color = i < 12 ? "text-risk-minimal" : i < 14 ? "text-amber-bright" : "text-text-muted";
                return (
                  <div key={a.id} className="flex items-center gap-2">
                    <span className="text-text-muted">{String(15 + i).padStart(2, "0")}:42</span>
                    <span className={color}>{status}</span>
                    <span className="text-text-secondary truncate">{a.name}</span>
                  </div>
                );
              })}
            </div>
          </aside>
        </div>
      </section>

      {/* IMPACT */}
      <section className="px-10 pb-20">
        <div className="label-eyebrow text-teal-bright mb-2">PORTFOLIO INTELLIGENCE</div>
        <h2 className="font-display text-4xl mb-8">Aggregate signals</h2>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Carbon heatmap (treemap-ish via flex) */}
          <div className="rounded-xl bg-bg-surface border border-bg-border p-6">
            <div className="label-eyebrow mb-4">CARBON EXPOSURE BY SECTOR</div>
            <div className="grid grid-cols-4 gap-1 h-48">
              {[
                { l: "Energy", v: 62, c: "bg-risk-critical/70" },
                { l: "Materials", v: 18, c: "bg-risk-high/60" },
                { l: "Utilities", v: 12, c: "bg-risk-medium/60" },
                { l: "Industrials", v: 9, c: "bg-amber-mid/50" },
                { l: "Transport", v: 8, c: "bg-amber-bright/40" },
                { l: "Tech", v: 4, c: "bg-teal-mid/40" },
                { l: "Finance", v: 3, c: "bg-teal-dim/60" },
                { l: "Other", v: 2, c: "bg-bg-border" },
              ].map((s) => (
                <div key={s.l} className={`${s.c} rounded p-2 flex flex-col justify-between`} style={{ gridColumn: `span ${Math.max(1, Math.round(s.v / 10))}` }}>
                  <div className="text-[10px] font-mono text-text-primary">{s.l}</div>
                  <div className="font-display text-lg text-text-primary">{s.v}%</div>
                </div>
              ))}
            </div>
          </div>

          {/* Greenwashing bubbles */}
          <div className="rounded-xl bg-bg-surface border border-bg-border p-6">
            <div className="label-eyebrow mb-4">GREENWASHING DISTRIBUTION</div>
            <div className="relative h-48">
              {RECENT_ANALYSES.map((c, i) => {
                const size = 30 + c.esg * 0.6;
                const left = 10 + i * 14;
                const top = 30 + ((100 - c.esg) % 50);
                const bg = c.risk === "HIGH" ? "bg-risk-high/40 border-risk-high" : c.risk === "MEDIUM" ? "bg-risk-medium/40 border-risk-medium" : "bg-risk-low/40 border-risk-low";
                return (
                  <div key={c.ticker} className={`absolute rounded-full border ${bg} flex items-center justify-center font-mono text-[10px] text-text-primary`}
                    style={{ width: size, height: size, left: `${left}%`, top }}>
                    {c.ticker}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Compliance radar */}
          <div className="rounded-xl bg-bg-surface border border-bg-border p-6">
            <div className="label-eyebrow mb-4">REGULATORY RADAR</div>
            <div className="h-48">
              <ResponsiveContainer>
                <RadarChart data={RADAR_DATA}>
                  <PolarGrid stroke="hsl(var(--bg-border))" />
                  <PolarAngleAxis dataKey="axis" tick={{ fill: "hsl(var(--text-secondary))", fontSize: 10 }} />
                  <PolarRadiusAxis stroke="hsl(var(--bg-border))" tick={false} />
                  <Radar dataKey="avg" stroke="hsl(var(--amber-bright))" fill="hsl(var(--amber-bright))" fillOpacity={0.2} />
                  <Radar dataKey="co" stroke="hsl(var(--teal-bright))" fill="hsl(var(--teal-bright))" fillOpacity={0.4} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </section>
    </PageWrapper>
  );
}
