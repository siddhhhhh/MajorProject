import { useState } from "react";
import { Download, FileText, FileJson, FileType2, Package, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { ReportData } from "@/types/report";

export function ExportMenu({ report: R, reportId }: { report: ReportData; reportId?: string }) {

function downloadBlob(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  // Some browsers (Firefox, certain Chromium builds) silently drop
  // a programmatic .click() if the anchor isn't attached to the document.
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

  function buildReportText() {
    if (R.auditText) return R.auditText;
    return [
      `ESGLENS REPORT - ${R.company} (${R.ticker})`,
      `Sector: ${R.sector} | Jurisdiction: ${R.jurisdiction}`,
      `Generated: ${new Date().toISOString()}`,
      "",
      `ESG SCORE: ${R.esgScore} / 100`,
      `Rating: ${R.rating} | Risk: ${R.riskLevel} | Confidence: ${R.confidence}%`,
      `Greenwashing risk: ${R.greenwashing} / 100`,
      "",
      `Pillars: E ${R.pillars.e} | S ${R.pillars.s} | G ${R.pillars.g}`,
      "",
      `CLAIM`,
      `"${R.claim}"`,
      `Verdict: ${R.verdict}`,
      "",
      `AI VERDICT`,
      R.summary,
      "",
      `CARBON`,
      `Scope 1: ${(R.scope1 / 1e6).toFixed(1)}M tCO2e`,
      `Scope 2: ${(R.scope2 / 1e6).toFixed(1)}M tCO2e`,
      `Scope 3: ${(R.scope3 / 1e9).toFixed(2)}B tCO2e`,
      "",
      `CONTRADICTIONS`,
      ...R.contradictions.map((c, i) => `${i + 1}. [${c.severity}] ${c.claim}\n   -> ${c.evidence}\n   Source: ${c.source}`),
      "",
      `REGULATORY (${R.regulatoryOverall}/100 overall)`,
      ...R.regulatory.map((r) => `| ${r.framework} - ${r.score}/100 ${r.status} - ${r.gap}`),
      "",
      `EVIDENCE (${R.evidence.length} sources)`,
      ...R.evidence.map((e) => `| [${e.stance}] ${e.domain} (${e.year}) cred ${(e.credibility * 100).toFixed(0)}% - ${e.excerpt}`),
    ].join("\n");
  }

  async function downloadAuditPDF() {
    if (!reportId) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/reports/${reportId}/pdf`);
      if (!res.ok) {
        const errText = await res.text().catch(() => res.statusText);
        throw new Error(`PDF endpoint ${res.status}: ${errText.slice(0, 200)}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ESGLens_${R.company.replace(/ /g, "_")}_${reportId}.pdf`;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (e) {
      console.error("PDF download failed", e);
      alert(`PDF download failed:\n${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const opts = [
    {
      icon: FileType2,
      label: "Audit-Ready Report (PDF)",
      size: "~150 KB",
      badge: "PROFESSIONAL",
      run: () => downloadAuditPDF(),
      disabled: !reportId,
    },
    { icon: FileText,  label: "Plain Text (TXT)",      size: R.auditText ? "~full" : "~20 KB",  badge: "", run: () => downloadBlob(buildReportText(), `ESGLens_${R.ticker}.txt`, "text/plain"), disabled: false },
    { icon: FileJson,  label: "Raw Data (JSON)",        size: R.rawReport ? "~full" : "~12 KB",  badge: "", run: () => downloadBlob(JSON.stringify(R.rawReport || R, null, 2), `ESGLens_${R.ticker}.json`, "application/json"), disabled: false },
    { icon: Package,   label: "Evidence Pack (JSON)",   size: "~6 KB",   badge: "", run: () => downloadBlob(JSON.stringify(R.evidence, null, 2), `ESGLens_${R.ticker}_evidence.json`, "application/json"), disabled: false },
  ];
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-teal-dim text-teal-bright hover:bg-teal-bright/10 transition text-sm"
      >
        <Download className="h-4 w-4" /> Export Report
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="absolute right-0 top-full mt-2 w-72 rounded-xl glass border border-bg-border shadow-2xl z-50 overflow-hidden"
          >
            {opts.map((o) => (
              <button
                key={o.label}
                disabled={o.disabled || loading}
                onMouseDown={(e) => { e.preventDefault(); o.run(); setOpen(false); }}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-teal-bright/10 transition border-b border-bg-border last:border-0 disabled:opacity-40"
              >
                {loading && o.label.includes("PDF") ? <Loader2 className="h-4 w-4 text-teal-bright animate-spin shrink-0" /> : <o.icon className="h-4 w-4 text-teal-bright shrink-0" />}
                <span className="flex-1 text-sm text-text-primary">{o.label}</span>
                {o.badge && <span className="font-mono text-[9px] bg-teal-bright/20 text-teal-bright px-1.5 py-0.5 rounded">{o.badge}</span>}
                <span className="font-mono text-[10px] text-text-muted">{o.size}</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
