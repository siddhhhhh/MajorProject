"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Building2,
  AlertTriangle,
  Activity,
  FileCheck2,
  TrendingDown,
  TrendingUp,
  BarChart3,
  Shield,
  Leaf,
  Users,
  Clock
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  Cell
} from "recharts";

type HistoryItem = {
  company_name: string;
  claim: string;
  industry: string;
  risk_level: string;
  confidence: number;
  report_created_at: string;
  report_file_name: string;
};

const DEMO_ANALYSES = [
  { company: "Shell", risk: "HIGH", score: 99.5, industry: "Energy", greenwashing: true },
  { company: "Unilever", risk: "MODERATE", score: 55.2, industry: "Consumer Goods", greenwashing: false },
  { company: "JP Morgan", risk: "LOW", score: 28.4, industry: "Financial Services", greenwashing: false },
  { company: "Tesla", risk: "MODERATE", score: 62.1, industry: "Automotive", greenwashing: false },
  { company: "Reliance Industries", risk: "HIGH", score: 78.3, industry: "Energy", greenwashing: true },
];

const INDUSTRY_RADAR = [
  { pillar: "Environmental", Energy: 28, Finance: 45, Tech: 72, Consumer: 58 },
  { pillar: "Social", Energy: 42, Finance: 68, Tech: 65, Consumer: 72 },
  { pillar: "Governance", Energy: 51, Finance: 79, Tech: 63, Consumer: 61 },
  { pillar: "Carbon Mgmt", Energy: 22, Finance: 55, Tech: 68, Consumer: 51 },
  { pillar: "Disclosure", Energy: 48, Finance: 82, Tech: 74, Consumer: 66 },
];

const DEMO_REPORT_BASE_TIME = Date.parse("2026-04-22T12:00:00Z");

function getRiskColor(risk: string) {
  const upper = (risk || "").toUpperCase();
  if (upper === "HIGH") return { text: "text-red-700", bg: "bg-red-100", dot: "🔴" };
  if (upper === "MODERATE") return { text: "text-amber-700", bg: "bg-amber-100", dot: "🟡" };
  if (upper === "LOW") return { text: "text-emerald-700", bg: "bg-emerald-100", dot: "🟢" };
  return { text: "text-neutral-600", bg: "bg-neutral-100", dot: "⚪" };
}

function formatReportDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

export default function DashboardPage() {
  const [history] = useState<HistoryItem[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      const raw = window.localStorage.getItem("esg-analysis-history") || "[]";
      const parsed = JSON.parse(raw) as HistoryItem[];
      return Array.isArray(parsed) ? parsed.slice(0, 20) : [];
    } catch {
      return [];
    }
  });

  const stats = useMemo(() => {
    const all = [...history];
    const total = all.length;
    const highRisk = all.filter((h) => (h.risk_level || "").toUpperCase() === "HIGH").length;
    const avgConf = total > 0 ? Math.round(all.reduce((s, h) => s + (typeof h.confidence === "number" ? h.confidence * 100 : 0), 0) / total) : 71;
    const companies = new Set(all.map((h) => h.company_name)).size;
    return { total: total || 58, highRisk: highRisk || 12, avgConf: avgConf || 71, companies: companies || 15 };
  }, [history]);

  const riskDistribution = useMemo(() => {
    if (!history.length) return [
      { name: "Low Risk", value: 45, fill: "#4ade80" },
      { name: "Moderate", value: 35, fill: "#fbbf24" },
      { name: "High Risk", value: 20, fill: "#ef4444" },
    ];
    const low = history.filter((h) => (h.risk_level || "").toUpperCase() === "LOW").length;
    const mod = history.filter((h) => (h.risk_level || "").toUpperCase() === "MODERATE").length;
    const high = history.filter((h) => (h.risk_level || "").toUpperCase() === "HIGH").length;
    return [
      { name: "Low Risk", value: low, fill: "#4ade80" },
      { name: "Moderate", value: mod, fill: "#fbbf24" },
      { name: "High Risk", value: high, fill: "#ef4444" },
    ];
  }, [history]);

  const recentAnalyses = history.length > 0 ? history.slice(0, 5) : DEMO_ANALYSES.map((d, i) => ({
    company_name: d.company,
    claim: "ESG sustainability commitment analysis",
    industry: d.industry,
    risk_level: d.risk,
    confidence: (100 - d.score) / 100,
    report_created_at: new Date(DEMO_REPORT_BASE_TIME - i * 3600000).toISOString(),
    report_file_name: "",
  }));

  const widgets = [
    {
      title: "Total Analyses Run",
      value: String(stats.total),
      change: "+3 this week",
      positive: true,
      icon: <Activity className="w-4 h-4 text-primary-600" />,
    },
    {
      title: "Avg. Confidence",
      value: `${stats.avgConf}%`,
      change: "+2.1 pts",
      positive: true,
      icon: <FileCheck2 className="w-4 h-4 text-primary-600" />,
    },
    {
      title: "High Risk Alerts",
      value: String(stats.highRisk),
      change: "Requiring attention",
      positive: false,
      icon: <AlertTriangle className="w-4 h-4 text-red-500" />,
    },
    {
      title: "Companies Tracked",
      value: String(stats.companies),
      change: "Across all industries",
      positive: true,
      icon: <Building2 className="w-4 h-4 text-primary-600" />,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold font-heading text-neutral-900 tracking-tight">ESG Intelligence Dashboard</h2>
        <p className="text-neutral-500 text-sm mt-1">
          Real-time ESG risk monitoring, greenwashing detection, and sustainability analytics.
        </p>
      </div>

      {/* Stat Widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {widgets.map((widget, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: idx * 0.08 }}
          >
            <Card className="border-neutral-200/60 shadow-sm bg-white hover:shadow-md transition-shadow">
              <CardContent className="p-5">
                <div className="flex justify-between items-start mb-4">
                  <div className="w-8 h-8 rounded-md bg-neutral-100 flex items-center justify-center">
                    {widget.icon}
                  </div>
                  <div className={`flex items-center text-xs font-semibold ${widget.positive ? "text-green-600" : "text-red-600"}`}>
                    {widget.positive ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
                    {widget.change}
                  </div>
                </div>
                <div className="text-2xl font-bold text-neutral-900 mb-1">{widget.value}</div>
                <div className="text-sm font-medium text-neutral-500">{widget.title}</div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Distribution Bar */}
        <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, delay: 0.3 }}>
          <Card className="border-neutral-200/60 shadow-sm bg-white h-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-neutral-800 text-base flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-primary-600" /> ESG Risk Distribution
              </CardTitle>
              <CardDescription>Breakdown of analyses by risk level</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[240px] w-full mt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={riskDistribution} margin={{ top: 5, right: 5, bottom: 5, left: -20 }} barSize={48}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e5e5" />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#737373", fontSize: 12 }} dy={10} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "#737373", fontSize: 12 }} />
                    <Tooltip
                      cursor={{ fill: "#f5f5f5" }}
                      contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                    />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                      {riskDistribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* ESG Pillar Radar */}
        <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, delay: 0.4 }}>
          <Card className="border-neutral-200/60 shadow-sm bg-white h-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-neutral-800 text-base flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary-600" /> Industry ESG Pillar Comparison
              </CardTitle>
              <CardDescription>Average E/S/G scores by sector</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[240px] w-full mt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={INDUSTRY_RADAR}>
                    <PolarGrid stroke="#e5e5e5" />
                    <PolarAngleAxis dataKey="pillar" tick={{ fill: "#737373", fontSize: 11 }} />
                    <Radar name="Energy" dataKey="Energy" stroke="#ef4444" fill="#ef4444" fillOpacity={0.15} strokeWidth={2} />
                    <Radar name="Finance" dataKey="Finance" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={2} />
                    <Radar name="Tech" dataKey="Tech" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.15} strokeWidth={2} />
                    <Radar name="Consumer" dataKey="Consumer" stroke="#10b981" fill="#10b981" fillOpacity={0.15} strokeWidth={2} />
                    <Tooltip contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap gap-3 mt-2 justify-center text-xs">
                {[{ c: "#ef4444", l: "Energy" }, { c: "#3b82f6", l: "Finance" }, { c: "#8b5cf6", l: "Technology" }, { c: "#10b981", l: "Consumer" }].map(({ c, l }) => (
                  <span key={l} className="flex items-center gap-1.5 text-neutral-600">
                    <span className="w-3 h-3 rounded-full" style={{ background: c }} />
                    {l}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Greenwashing Risk Matrix & Recent Analyses */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Greenwashing Risk Matrix */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.5 }}>
          <Card className="border-neutral-200/60 shadow-sm bg-white h-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-neutral-800 text-base flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600" /> Greenwashing Indicators
              </CardTitle>
              <CardDescription>Pattern risk breakdown across analyses</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                { label: "Greenwishing", pct: 72, color: "bg-amber-400" },
                { label: "Greenhushing", pct: 48, color: "bg-orange-400" },
                { label: "Carbon Tunnel Vision", pct: 61, color: "bg-red-400" },
                { label: "Selective Disclosure", pct: 55, color: "bg-rose-400" },
                { label: "False Net-Zero Claims", pct: 38, color: "bg-yellow-400" },
              ].map((item) => (
                <div key={item.label}>
                  <div className="flex justify-between text-xs text-neutral-600 mb-1">
                    <span className="font-medium">{item.label}</span>
                    <span>{item.pct}%</span>
                  </div>
                  <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${item.color}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${item.pct}%` }}
                      transition={{ duration: 0.8, delay: 0.6 }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        {/* Recent Analyses */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6 }}
          className="lg:col-span-2"
        >
          <Card className="border-neutral-200/60 shadow-sm bg-white h-full">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-neutral-800 text-base flex items-center gap-2">
                    <Clock className="w-4 h-4 text-primary-600" /> Recent Analyses
                  </CardTitle>
                  <CardDescription>{history.length > 0 ? "From your analysis history" : "Demo data — run an analysis to populate"}</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {recentAnalyses.map((item, idx) => {
                  const colors = getRiskColor(item.risk_level);
                  const confPct = typeof item.confidence === "number" ? Math.round(item.confidence * 100) : 0;
                  return (
                    <div key={idx} className="flex items-center gap-3 p-3 rounded-lg border border-neutral-100 hover:bg-neutral-50 transition-colors">
                      <div className={`w-8 h-8 rounded-full ${colors.bg} flex items-center justify-center flex-shrink-0`}>
                        <span
                          className={`h-2.5 w-2.5 rounded-full ${
                            (item.risk_level || "").toUpperCase() === "HIGH"
                              ? "bg-red-500"
                              : (item.risk_level || "").toUpperCase() === "MODERATE"
                                ? "bg-amber-400"
                                : (item.risk_level || "").toUpperCase() === "LOW"
                                  ? "bg-emerald-500"
                                  : "bg-neutral-400"
                          }`}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-neutral-900 truncate">{item.company_name}</span>
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${colors.bg} ${colors.text}`}>
                            {item.risk_level || "N/A"}
                          </span>
                        </div>
                        <div className="text-xs text-neutral-500 truncate mt-0.5">{item.industry} · Conf. {confPct}%</div>
                      </div>
                      <div className="text-xs text-neutral-400 flex-shrink-0 text-right">
                        {item.report_created_at ? formatReportDate(item.report_created_at) : "Demo"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* ESG Pillar Quick Guide */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.7 }}>
        <Card className="border-neutral-200/60 shadow-sm bg-gradient-to-r from-green-50 via-blue-50 to-purple-50">
          <CardContent className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                {
                  icon: <Leaf className="w-5 h-5 text-emerald-600" />,
                  color: "text-emerald-700",
                  bg: "bg-emerald-100",
                  label: "Environmental",
                  desc: "GHG emissions, carbon intensity, renewable energy transition, water usage, biodiversity, and circular economy practices.",
                  weight: "35%",
                },
                {
                  icon: <Users className="w-5 h-5 text-blue-600" />,
                  color: "text-blue-700",
                  bg: "bg-blue-100",
                  label: "Social",
                  desc: "Employee health & safety, labor rights, community impact, supply chain standards, and diversity & inclusion metrics.",
                  weight: "30%",
                },
                {
                  icon: <Shield className="w-5 h-5 text-purple-600" />,
                  color: "text-purple-700",
                  bg: "bg-purple-100",
                  label: "Governance",
                  desc: "Board independence, executive pay, anti-corruption policies, whistleblower protections, and ESG disclosure quality.",
                  weight: "35%",
                },
              ].map(({ icon, color, bg, label, desc, weight }) => (
                <div key={label} className="flex gap-3">
                  <div className={`w-10 h-10 rounded-xl ${bg} flex items-center justify-center flex-shrink-0`}>{icon}</div>
                  <div>
                    <div className={`font-semibold text-sm ${color} flex items-center gap-2`}>
                      {label}
                      <span className="text-xs font-normal text-neutral-500">Weight: {weight}</span>
                    </div>
                    <p className="text-xs text-neutral-600 mt-1 leading-relaxed">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
