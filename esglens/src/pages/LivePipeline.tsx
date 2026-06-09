import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { PageWrapper } from "@/components/layout/PageWrapper";
import { ArcGauge } from "@/components/charts/ArcGauge";
import { RiskBadge } from "@/components/cards/RiskBadge";
import { useAnalysisStore } from "@/stores/analysisStore";

export default function LivePipeline() {
  const nav = useNavigate();
  const logRef = useRef<HTMLDivElement>(null);

  const {
    currentAnalysisId,
    currentReport,
    isRunning,
    progress,
    elapsedSeconds,
    logs,
    error,
  } = useAnalysisStore();

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  // Navigate to report when complete
  useEffect(() => {
    if (currentReport && !isRunning) {
      const t = setTimeout(() => nav(`/report?id=${encodeURIComponent(currentReport.id)}`), 4000);
      return () => clearTimeout(t);
    }
  }, [currentReport, isRunning, nav]);

  const done = !!currentReport && !isRunning;

  // Count agents from logs (lines containing OK or [OK])
  const agentsDone = logs.filter(
    (l) => l.kind === "ok" && (l.msg.includes("OK") || l.msg.includes("[OK]") || l.msg.includes("completed"))
  ).length;

  // Format elapsed time
  const elapsed = elapsedSeconds > 0
    ? `${Math.floor(elapsedSeconds / 60)}m ${Math.round(elapsedSeconds % 60)}s`
    : "0s";

  return (
    <PageWrapper>
      {/* Top bar */}
      <div className="px-10 py-5 border-b border-bg-border flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-risk-high/15 text-risk-high flex items-center justify-center font-display text-lg">
            {currentReport ? currentReport.ticker.slice(0, 2) : "??"}
          </div>
          <div>
            <div className="font-display text-xl">
              {currentReport ? currentReport.company : "Running analysis..."}
              {currentReport && (
                <span className="text-text-secondary text-sm font-sans"> | {currentReport.ticker}</span>
              )}
            </div>
            <div className="font-mono text-[10px] text-text-secondary">
              {currentAnalysisId
                ? `ANALYSIS | ${currentAnalysisId.slice(0, 8).toUpperCase()}`
                : "WAITING FOR PIPELINE"}
            </div>
          </div>
        </div>
        <div className="flex-1 mx-10 max-w-xl">
          <div className="h-1.5 rounded-full bg-bg-elevated overflow-hidden">
            <motion.div
              animate={{ width: `${progress}%` }}
              className="h-full bg-gradient-to-r from-teal-mid to-teal-bright glow-teal"
            />
          </div>
          <div className="flex justify-between mt-1.5 text-[10px] font-mono">
            <span className="text-text-secondary">{agentsDone} AGENTS COMPLETED</span>
            <span className="text-teal-bright">{Math.round(progress)}%</span>
          </div>
        </div>
        <div className="font-mono text-[11px] text-text-secondary text-right">
          <div>{isRunning ? "RUNNING" : done ? "COMPLETE" : "IDLE"}</div>
          <div>ELAPSED {elapsed}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-px bg-bg-border min-h-[calc(100vh-90px)]">
        {/* Log terminal - full width, real pipeline output */}
        <div data-force-dark className="bg-[hsl(215_60%_8%)] p-6 text-text-primary">
          <div className="label-eyebrow mb-3">LIVE LOG STREAM</div>
          {error && (
            <div className="mb-3 text-risk-high text-xs font-mono bg-risk-high/10 border border-risk-high/20 rounded p-2">
              Warning: Error: {error}
            </div>
          )}
          <div
            ref={logRef}
            className="font-mono text-xs space-y-0.5 max-h-[calc(100vh-200px)] overflow-y-auto scrollbar-thin"
          >
            {logs.length === 0 && isRunning && (
              <div className="text-text-muted animate-pulse">Waiting for pipeline output...</div>
            )}
            {logs.length === 0 && !isRunning && !done && (
              <div className="text-text-muted">
                No analysis running.{" "}
                <button onClick={() => nav("/analyse")} className="text-teal-bright hover:underline">
                  Start one
                </button>
              </div>
            )}
            {logs.map((l, i) => (
              <div key={i} className="flex gap-3 leading-relaxed">
                <span className="text-text-muted shrink-0 w-14 text-right">[{l.t}]</span>
                <span
                  className={
                    l.kind === "ok"
                      ? "text-teal-bright"
                      : l.kind === "warn"
                      ? "text-amber-bright"
                      : l.kind === "error"
                      ? "text-risk-high"
                      : "text-text-secondary"
                  }
                >
                  {l.msg}
                </span>
              </div>
            ))}
            {done && (
              <div className="flex gap-3 mt-2 pt-2 border-t border-bg-border">
                <span className="text-text-muted w-14 text-right">[done]</span>
                <span className="text-teal-bright">OK Pipeline complete - report ready</span>
              </div>
            )}
          </div>
        </div>

        {/* Emerging results sidebar */}
        <div className="bg-bg-surface p-5 space-y-5">
          <div className="label-eyebrow">EMERGING RESULTS</div>

          {done && currentReport && (
            <>
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="text-center">
                <ArcGauge value={currentReport.esg_score} size={160} label="ESG SCORE" />
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex justify-center"
              >
                <RiskBadge level={currentReport.risk_level as "HIGH" | "MEDIUM" | "LOW"} />
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border border-bg-border p-3"
              >
                <div className="label-eyebrow mb-1">GREENWASHING</div>
                <div className="font-display text-2xl text-risk-high">
                  {currentReport.greenwashing.overall_score.toFixed(1)} / 100
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border border-bg-border p-3"
              >
                <div className="label-eyebrow mb-1">CONTRADICTIONS</div>
                <div className="font-display text-2xl text-risk-high">
                  {currentReport.contradictions.filter((c) => c.severity === "HIGH").length} HIGH
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border border-bg-border p-3"
              >
                <div className="label-eyebrow mb-1">CONFIDENCE</div>
                <div className="font-display text-2xl text-amber-bright">
                  {currentReport.confidence.toFixed(0)}%
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="text-center pt-4 border-t border-bg-border"
              >
                <div className="font-display text-2xl text-teal-bright mb-2">Analysis Complete</div>
                <div className="text-xs text-text-secondary mb-3">Routing to report in 4s...</div>
                <button
                  id="view-report-btn"
                  onClick={() => nav(`/report?id=${encodeURIComponent(currentReport.id)}`)}
                  className="px-4 py-2 rounded-md bg-teal-bright text-bg-void text-sm font-medium glow-teal"
                >
                  View Full Report
                </button>
              </motion.div>
            </>
          )}

          {isRunning && !done && (
            <div className="space-y-4">
              <div className="rounded-lg border border-bg-border p-3 text-center">
                <div className="label-eyebrow mb-1">PROGRESS</div>
                <div className="font-display text-4xl text-teal-bright">{Math.round(progress)}%</div>
              </div>
              <div className="rounded-lg border border-bg-border p-3 text-center">
                <div className="label-eyebrow mb-1">ELAPSED</div>
                <div className="font-display text-2xl text-amber-bright">{elapsed}</div>
              </div>
              <div className="rounded-lg border border-bg-border p-3 text-center">
                <div className="label-eyebrow mb-1">LOG LINES</div>
                <div className="font-display text-2xl text-text-primary">{logs.length}</div>
              </div>
              <div className="text-center text-[10px] font-mono text-text-muted animate-pulse">
                Pipeline running - streaming real-time output...
              </div>
            </div>
          )}

          {!isRunning && !done && !error && (
            <div className="text-center text-text-muted text-xs font-mono pt-4">
              No analysis running.
              <br />
              <button onClick={() => nav("/analyse")} className="text-teal-bright mt-1 hover:underline">
                Start a new analysis
              </button>
            </div>
          )}
        </div>
      </div>
    </PageWrapper>
  );
}
