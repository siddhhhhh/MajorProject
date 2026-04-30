import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Loader2 } from "lucide-react";
import { PageWrapper } from "@/components/layout/PageWrapper";
import { AGENTS } from "@/data/demo";
import { useAnalysisStore } from "@/stores/analysisStore";

const LAYERS = ["Input", "Data", "Analysis", "ML", "Output"];

const layerColors: Record<string, string> = {
  Input: "border-blue-400/40 bg-blue-400/5 text-blue-300",
  Data: "border-teal-mid/40 bg-teal-bright/5 text-teal-bright",
  Analysis: "border-purple-400/40 bg-purple-400/5 text-purple-300",
  ML: "border-amber-bright/40 bg-amber-bright/5 text-amber-bright",
  Output: "border-text-secondary/40 bg-text-secondary/5 text-text-primary",
};

export default function NewAnalysis() {
  const nav = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const companyRef = useRef<HTMLInputElement>(null);
  const industryRef = useRef<HTMLInputElement>(null);
  const claimRef = useRef<HTMLTextAreaElement>(null);

  const startAnalysis = useAnalysisStore((s) => s.startAnalysis);

  const handleSubmit = async () => {
    const company = companyRef.current?.value?.trim();
    const industry = industryRef.current?.value?.trim();
    const claim = claimRef.current?.value?.trim();

    if (!company || !claim) {
      setSubmitError("Company name and claim are required.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await startAnalysis({
        company,
        ...(industry ? { industry } : {}),
        claim,
      });
      nav("/pipeline");
    } catch (e) {
      setSubmitError(String(e));
      setIsSubmitting(false);
    }
  };

  return (
    <PageWrapper className="grid-bg">
      <div className="grid grid-cols-1 lg:grid-cols-[55%_45%] min-h-screen">
        {/* LEFT */}
        <div className="p-10 lg:p-14 max-w-2xl">
          <div className="label-eyebrow text-teal-bright mb-3">NEW ANALYSIS</div>
          <h1 className="font-display text-5xl mb-10">Configure analysis</h1>

          <div className="space-y-8">
            <div>
              <label className="label-eyebrow block mb-2">01 · COMPANY</label>
              <input
                ref={companyRef}
                id="company-input"
                defaultValue=""
                placeholder="Enter the company name"
                className="w-full h-12 px-4 rounded-lg bg-bg-elevated border border-bg-border focus:border-teal-bright focus:shadow-[0_0_0_3px_hsl(var(--teal-bright)/0.15)] outline-none transition"
              />
            </div>
            <div>
              <label className="label-eyebrow block mb-2">02 · INDUSTRY</label>
              <input
                ref={industryRef}
                id="industry-input"
                defaultValue=""
                placeholder="e.g. Energy, Financial Services, Automotive…"
                className="w-full h-12 px-4 rounded-lg bg-bg-elevated border border-bg-border focus:border-teal-bright focus:shadow-[0_0_0_3px_hsl(var(--teal-bright)/0.15)] outline-none transition"
              />
            </div>
            <div>
              <label className="label-eyebrow block mb-2">03 · CLAIM</label>
              <textarea
                ref={claimRef}
                id="claim-input"
                defaultValue=""
                placeholder="Enter the ESG claim to verify…"
                rows={3}
                className="w-full p-4 rounded-lg bg-bg-elevated border border-bg-border focus:border-teal-bright focus:shadow-[0_0_0_3px_hsl(var(--teal-bright)/0.15)] outline-none transition resize-none"
              />
            </div>

            {submitError && (
              <div className="text-risk-high text-sm font-mono bg-risk-high/10 border border-risk-high/20 rounded-lg px-4 py-2">
                ⚠ {submitError}
              </div>
            )}

            <button
              id="begin-analysis-btn"
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="w-full h-14 rounded-lg bg-gradient-to-r from-teal-mid to-teal-bright text-bg-void font-medium glow-teal hover:scale-[1.01] active:scale-[0.99] transition flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed disabled:scale-100"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Submitting…
                </>
              ) : (
                <>
                  Begin Analysis <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>

            <div className="font-mono text-[11px] text-text-muted pt-4 border-t border-bg-border">
              <span className="text-teal-bright">⌘K</span> Global search · <span className="text-teal-bright">⌘N</span> New analysis · <span className="text-teal-bright">⌘R</span> Latest report · <span className="text-teal-bright">⌘E</span> Export · <span className="text-teal-bright">?</span> All shortcuts
            </div>
          </div>
        </div>

        {/* RIGHT — topology */}
        <div className="relative border-l border-bg-border p-10 overflow-hidden bg-bg-deep/50">
          <div className="label-eyebrow text-teal-bright mb-2">PIPELINE TOPOLOGY</div>
          <h2 className="font-display text-3xl mb-8">36-agent system</h2>
          <div className="space-y-4">
            {LAYERS.map((layer) => {
              const agents = AGENTS.filter((agent) => agent.layer === layer);

              return (
                <div key={layer}>
                  <div className="label-eyebrow mb-2">{layer.toUpperCase()} LAYER · {agents.length}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {agents.map((agent, index) => (
                      <motion.span
                        key={agent.id}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: index * 0.03 }}
                        className={`text-[10px] font-mono px-2 py-1 rounded border ${layerColors[layer]}`}
                      >
                        {agent.name}
                      </motion.span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}
