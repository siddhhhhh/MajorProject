"use client";

import React from "react";
import { motion } from "framer-motion";
import { 
  ArrowRight, 
  BrainCircuit, 
  Activity, 
  Database, 
  Globe,
  Terminal,
  Zap,
  LineChart,
  Lock,
  Workflow,
  Search,
  Settings,
  ShieldCheck,
  FileText,
  BarChart3
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";

// Animation Variants
const fadeInUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.6 }
};

const staggerContainer = {
  initial: {},
  whileInView: { transition: { staggerChildren: 0.1 } }
};

const agentSummaryItems = [
  {
    name: "Claim Extractor",
    purpose: "Extracts concrete ESG claims from long-form disclosures and report chunks.",
    icon: FileText,
    accent: "from-emerald-500 to-teal-500",
    lane: "left",
  },
  {
    name: "Evidence Retriever",
    purpose: "Pulls supporting or contradictory external evidence from trusted sources.",
    icon: Search,
    accent: "from-blue-500 to-cyan-500",
    lane: "right",
  },
  {
    name: "Credibility Analyst",
    purpose: "Checks source reliability and scores credibility before downstream reasoning.",
    icon: ShieldCheck,
    accent: "from-emerald-500 to-lime-500",
    lane: "left",
  },
  {
    name: "Contradiction Analyzer",
    purpose: "Detects mismatches between company statements and observed outcomes.",
    icon: Activity,
    accent: "from-orange-500 to-amber-500",
    lane: "right",
  },
  {
    name: "Temporal Consistency",
    purpose: "Tracks whether promises stay consistent across years and reporting cycles.",
    icon: Workflow,
    accent: "from-indigo-500 to-blue-500",
    lane: "left",
  },
  {
    name: "Greenwishing Detector",
    purpose: "Flags aspirational language that lacks measurable execution signals.",
    icon: BrainCircuit,
    accent: "from-rose-500 to-orange-500",
    lane: "right",
  },
  {
    name: "Financial Analyst",
    purpose: "Connects ESG claims with financial indicators and capital allocation behavior.",
    icon: LineChart,
    accent: "from-violet-500 to-fuchsia-500",
    lane: "left",
  },
  {
    name: "Regulatory Scanner",
    purpose: "Maps claims against policy frameworks and compliance red flags.",
    icon: Lock,
    accent: "from-sky-500 to-indigo-500",
    lane: "right",
  },
  {
    name: "Risk Scorer",
    purpose: "Combines multi-agent findings into a calibrated risk intensity estimate.",
    icon: BarChart3,
    accent: "from-red-500 to-orange-500",
    lane: "left",
  },
  {
    name: "Confidence Scorer",
    purpose: "Provides confidence weighting so each verdict remains explainable.",
    icon: Database,
    accent: "from-cyan-500 to-blue-500",
    lane: "right",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-slate-50 selection:bg-emerald-100 font-sans text-slate-900">
      <Navbar />

      {/* --- HERO SECTION --- */}
      <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 overflow-hidden bg-white">
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
          <div className="absolute top-[-10%] right-[-5%] w-[50%] h-[50%] rounded-full bg-emerald-50 blur-[120px]" />
          <div className="absolute bottom-[20%] left-[-10%] w-[40%] h-[60%] rounded-full bg-blue-50 blur-[150px]" />
        </div>

        <div className="container mx-auto px-4 text-center">
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8 }}
            className="max-w-4xl mx-auto space-y-8"
          >
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm font-semibold mb-4">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              Next-Gen Environmental Intelligence
            </div>
            
            <h1 className="text-6xl md:text-8xl font-bold tracking-tighter leading-[1.1] text-slate-950">
              Audit the <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-600 to-blue-700">
                Future of ESG
              </span>
            </h1>
            
            <p className="text-xl md:text-2xl text-slate-600 max-w-2xl mx-auto leading-relaxed font-light">
              We developed a multi-agent AI ecosystem to verify sustainability claims, uncover hidden risks, and bring radical transparency to corporate disclosures.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-8">
              <Button size="lg" className="h-14 px-10 text-lg bg-slate-900 hover:bg-slate-800 text-white group shadow-xl transition-all">
                Analyze ESG Claims <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Button>
              <Button variant="outline" size="lg" className="h-14 px-10 text-lg border-slate-200 hover:bg-slate-50">
                Explore Our Science
              </Button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* --- MISSION SECTION --- */}
      <section className="py-24 border-y border-slate-100 bg-slate-50/50">
        <div className="container mx-auto px-4">
          <div className="grid lg:grid-cols-2 gap-20 items-center">
            <motion.div {...fadeInUp} className="space-y-8">
              <div className="space-y-4">
                <h2 className="text-4xl font-bold text-slate-900 tracking-tight">
                  Our Mission: Bridging the <br />
                  <span className="text-emerald-600">Integrity Gap</span>
                </h2>
                <p className="text-lg text-slate-600 leading-relaxed">
                  We built this platform to transition ESG evaluation from marketing-led narratives to <strong>evidence-backed certainties</strong>. By leveraging distributed AI agents, we provide the granular verification that institutional stakeholders require.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {[
                  { title: "Verification", desc: "We cross-check disclosures against 15+ external news & regulatory data points." },
                  { title: "Risk Mitigation", desc: "We flag greenwashing and contradictory patterns using advanced LLM reasoning." }
                ].map((item, i) => (
                  <div key={i} className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm">
                    <h4 className="font-bold text-slate-900 mb-1">{item.title}</h4>
                    <p className="text-sm text-slate-500">{item.desc}</p>
                  </div>
                ))}
              </div>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0, x: 40 }}
              whileInView={{ opacity: 1, x: 0 }}
              className="relative bg-slate-900 rounded-[2.5rem] p-10 text-white shadow-2xl overflow-hidden"
            >
              <div className="absolute top-0 right-0 p-8 opacity-10"><Globe size={180} /></div>
              <h3 className="text-2xl font-bold mb-8 flex items-center gap-3 text-emerald-400">
                <Zap className="w-6 h-6" /> Why We Built This
              </h3>
              <ul className="space-y-8">
                {[
                  "To automate the analysis of complex, unstructured corporate reports.",
                  "To apply specialized AI agents that act as independent auditors.",
                  "To provide explainable SHAP-based scores for audit-ready compliance."
                ].map((text, i) => (
                  <li key={i} className="flex gap-4 items-start">
                    <div className="h-6 w-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 mt-1 font-mono text-xs">
                      {i + 1}
                    </div>
                    <p className="text-slate-300 text-lg leading-snug">{text}</p>
                  </li>
                ))}
              </ul>
            </motion.div>
          </div>
        </div>
      </section>

      {/* --- TECH STACK SECTION --- */}
      <section className="py-24 bg-white overflow-hidden">
        <div className="container mx-auto px-4 text-center mb-16">
          <motion.div {...fadeInUp}>
            <h2 className="text-4xl font-bold mb-4 tracking-tight text-slate-900">The Intelligence Architecture</h2>
            <p className="text-slate-500 max-w-2xl mx-auto">We designed a modular stack optimized for high-throughput ESG verification and transparency.</p>
          </motion.div>
        </div>

        <div className="container mx-auto px-4 max-w-6xl">
          <motion.div 
            variants={staggerContainer}
            initial="initial"
            whileInView="whileInView"
            className="grid md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            <TechCard 
              icon={<Workflow className="text-emerald-600" />} 
              title="Orchestration" 
              items={["Python Logic Layer", "LangGraph State Control", "Dynamic Agent Routing"]} 
            />
            <TechCard 
              icon={<BrainCircuit className="text-blue-600" />} 
              title="AI & NLP Engine" 
              items={["LLM Claims Extraction", "Sentiment Discrepancy", "Confidence Calibration"]} 
            />
            <TechCard 
              icon={<LineChart className="text-purple-600" />} 
              title="Predictive Models" 
              items={["XGBoost / LightGBM", "SHAP Explainability", "Temporal Risk Forecasting"]} 
            />
            <TechCard 
              icon={<Database className="text-orange-600" />} 
              title="Data Retrieval" 
              items={["Vector RAG Architecture", "Pinecone Evidence Storage", "High-Performance Caching"]} 
            />
            <TechCard 
              icon={<Terminal className="text-slate-600" />} 
              title="Interface" 
              items={["Next.js / TypeScript", "Tailwind + Framer Motion", "Real-time Visualization"]} 
            />
            <TechCard 
              icon={<Lock className="text-red-600" />} 
              title="Safety & Validation" 
              items={["Hallucination Detection", "Bias Mitigation", "Audit-Ready Logs"]} 
            />
          </motion.div>
        </div>
      </section>

      {/* --- AGENT SUMMARY SECTION --- */}
      <section className="py-24 bg-slate-950 text-white border-y border-slate-800 overflow-hidden relative">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute -top-16 left-1/2 -translate-x-1/2 w-[70%] h-56 rounded-full bg-emerald-500/10 blur-3xl" />
          <div className="absolute bottom-0 right-[-10%] w-[40%] h-64 rounded-full bg-cyan-500/10 blur-3xl" />
        </div>

        <div className="container mx-auto px-4 relative z-10">
          <motion.div {...fadeInUp} className="text-center max-w-3xl mx-auto mb-14">
            <h2 className="text-4xl font-bold mb-4 tracking-tight text-white">Agent Summary</h2>
            <p className="text-slate-300 text-lg">
              Each specialist agent contributes one focused responsibility to the full ESG verification workflow.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] gap-6 lg:gap-10 items-start max-w-6xl mx-auto">
            <motion.div variants={staggerContainer} initial="initial" whileInView="whileInView" viewport={{ once: true }} className="space-y-4">
              {agentSummaryItems.filter((agent) => agent.lane === "left").map((agent) => {
                const Icon = agent.icon;
                return (
                <motion.div
                  key={agent.name}
                  variants={fadeInUp}
                  whileHover={{ y: -6, scale: 1.01 }}
                  className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5 shadow-[0_20px_40px_rgba(2,6,23,0.45)] backdrop-blur"
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-11 h-11 rounded-2xl bg-gradient-to-br ${agent.accent} flex items-center justify-center shadow-lg`}>
                      <Icon size={20} className="text-white" />
                    </div>
                    <div>
                      <div className="text-[10px] font-mono tracking-[0.2em] text-emerald-300 uppercase">Agent Node</div>
                      <h3 className="mt-1 text-lg font-bold text-white">{agent.name}</h3>
                    </div>
                  </div>
                  <p className="mt-3 text-sm text-slate-300 leading-relaxed">{agent.purpose}</p>
                </motion.div>
                );
              })}
            </motion.div>

            <div className="hidden lg:flex h-full items-stretch justify-center px-2">
              <div className="relative w-px bg-slate-700 min-h-[640px]">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_16px_rgba(16,185,129,0.8)]" />
                <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-cyan-500 shadow-[0_0_16px_rgba(6,182,212,0.8)]" />
              </div>
            </div>

            <motion.div variants={staggerContainer} initial="initial" whileInView="whileInView" viewport={{ once: true }} className="space-y-4">
              {agentSummaryItems.filter((agent) => agent.lane === "right").map((agent) => {
                const Icon = agent.icon;
                return (
                <motion.div
                  key={agent.name}
                  variants={fadeInUp}
                  whileHover={{ y: -6, scale: 1.01 }}
                  className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5 shadow-[0_20px_40px_rgba(2,6,23,0.45)] backdrop-blur"
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-11 h-11 rounded-2xl bg-gradient-to-br ${agent.accent} flex items-center justify-center shadow-lg`}>
                      <Icon size={20} className="text-white" />
                    </div>
                    <div>
                      <div className="text-[10px] font-mono tracking-[0.2em] text-cyan-300 uppercase">Agent Node</div>
                      <h3 className="mt-1 text-lg font-bold text-white">{agent.name}</h3>
                    </div>
                  </div>
                  <p className="mt-3 text-sm text-slate-300 leading-relaxed">{agent.purpose}</p>
                </motion.div>
                );
              })}
            </motion.div>
          </div>
        </div>
      </section>

      {/* --- HOW IT WORKS SECTION --- */}
      <section className="py-24 bg-slate-900 text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 w-1/2 h-full bg-emerald-500/5 blur-[120px] pointer-events-none" />
        <div className="container mx-auto px-4 relative z-10">
          <div className="text-center mb-20">
            <h2 className="text-4xl font-bold mb-4">How the Pipeline Operates</h2>
            <p className="text-slate-400">We engineered a multi-stage flow to transform raw reports into verifiable intelligence.</p>
          </div>

          <div className="grid md:grid-cols-4 gap-4">
            {[
              { icon: <FileText />, step: "01", title: "Ingestion", desc: "We ingest raw PDF reports, URLs, and financial statements." },
              { icon: <Search />, step: "02", title: "Retrieval", desc: "Our RAG engine pulls contextual evidence from global data sources." },
              { icon: <Settings />, step: "03", title: "Reasoning", desc: "14 autonomous agents stress-test every sustainability claim." },
              { icon: <BarChart3 />, step: "04", title: "Synthesis", desc: "Ensemble models compute a final risk score with SHAP evidence." }
            ].map((item, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className="relative p-8 rounded-3xl bg-slate-800/40 border border-slate-700/50 backdrop-blur-sm group hover:border-emerald-500/50 transition-colors"
              >
                <div className="text-emerald-500 mb-4 group-hover:scale-110 transition-transform">{item.icon}</div>
                <div className="text-xs font-mono text-emerald-500/50 mb-2">STAGE {item.step}</div>
                <h4 className="text-xl font-bold mb-3">{item.title}</h4>
                <p className="text-slate-400 text-sm leading-relaxed">{item.desc}</p>
                {i < 3 && <ArrowRight className="hidden lg:block absolute -right-6 top-1/2 -translate-y-1/2 text-slate-700" />}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* --- DASHBOARD PREVIEW --- */}
      <section className="py-24 bg-slate-50">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4 tracking-tight">Enterprise Visibility</h2>
            <p className="text-slate-500">We provide real-time risk scoring and deep evidence mapping.</p>
          </div>

          <motion.div 
            initial={{ opacity: 0, scale: 0.98, y: 20 }}
            whileInView={{ opacity: 1, scale: 1, y: 0 }}
            className="max-w-5xl mx-auto bg-white rounded-[2.5rem] border border-slate-200 shadow-2xl overflow-hidden"
          >
            <div className="bg-slate-100 px-6 py-4 flex items-center gap-2 border-b">
               <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-amber-400" />
                <div className="w-3 h-3 rounded-full bg-emerald-400" />
               </div>
               <div className="mx-auto text-[10px] font-mono tracking-widest text-slate-400 uppercase">System Status: Active</div>
            </div>
            
            <div className="p-10 grid md:grid-cols-3 gap-10">
              <div className="space-y-6">
                <div className="p-6 rounded-[2rem] bg-red-50 border border-red-100 shadow-inner">
                  <div className="text-xs uppercase font-bold text-red-600 mb-2">Critical Anomaly</div>
                  <div className="text-4xl font-black text-red-700 tracking-tighter">89% RISK</div>
                  <div className="mt-4 h-2 w-full bg-red-200 rounded-full overflow-hidden">
                    <div className="h-full bg-red-600 w-[89%]" />
                  </div>
                  <p className="mt-4 text-xs text-red-800 font-medium leading-relaxed italic">&ldquo;Detection of misleading narrative regarding Scope 3 carbon neutrality targets.&rdquo;</p>
                </div>
              </div>

              <div className="md:col-span-2 p-8 rounded-[2rem] border border-slate-100 bg-slate-50/50">
                <h4 className="font-bold mb-8 flex items-center gap-2 text-slate-800">
                  <Activity size={18} className="text-emerald-500" /> Analytical Component Scoring
                </h4>
                <div className="space-y-10">
                  <ScoreBar label="Environmental Integrity" score={42} color="bg-amber-500" />
                  <ScoreBar label="Social & Ethical Disclosure" score={78} color="bg-emerald-500" />
                  <ScoreBar label="Governance Transparency" score={85} color="bg-blue-500" />
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* --- CALL TO ACTION --- */}
      <section className="py-24 bg-white px-4">
        <div className="container mx-auto">
          <Card className="bg-slate-950 border-0 rounded-[3.5rem] overflow-hidden relative p-12 md:p-24 text-center">
            <div className="absolute inset-0 opacity-20 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-emerald-500 via-transparent to-transparent"></div>
            <CardContent className="relative z-10 space-y-8">
              <h2 className="text-4xl md:text-6xl font-bold text-white tracking-tight leading-tight">
                Ready to transform <br /> ESG from <span className="text-emerald-400">Risk to Reality?</span>
              </h2>
              <p className="text-slate-400 text-lg max-w-xl mx-auto leading-relaxed">
                We empower teams with the evidence needed to make informed, sustainable decisions.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button size="lg" className="h-16 px-12 bg-emerald-500 hover:bg-emerald-600 text-slate-950 text-lg font-bold shadow-[0_0_20px_rgba(16,185,129,0.3)]">
                  Get Started
                </Button>
                <Button size="lg" variant="outline" className="h-16 px-12 border-slate-700 text-white hover:bg-slate-900 text-lg font-bold">
                  View Case Studies
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <Footer />
    </main>
  );
}

// --- SUB-COMPONENTS ---

function TechCard({ icon, title, items }: { icon: React.ReactNode, title: string, items: string[] }) {
  const iconElement = icon as React.ReactElement<{ size?: number }>;

  return (
    <motion.div 
      variants={fadeInUp}
      whileHover={{ y: -8, boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.1)" }}
      className="p-8 rounded-[2rem] border border-slate-200 bg-white transition-all group"
    >
      <div className="w-12 h-12 rounded-2xl bg-slate-50 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform shadow-inner">
        {React.cloneElement(iconElement, { size: 24 })}
      </div>
      <h3 className="text-xl font-bold text-slate-900 mb-4 tracking-tight">{title}</h3>
      <ul className="space-y-3">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-slate-500 flex items-center gap-3">
            <ShieldCheck size={14} className="text-emerald-500 shrink-0" />
            {item}
          </li>
        ))}
      </ul>
    </motion.div>
  );
}

function ScoreBar({ label, score, color }: { label: string, score: number, color: string }) {
  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center text-sm">
        <span className="font-bold text-slate-700 tracking-tight">{label}</span>
        <span className="font-mono font-black text-slate-900">{score}/100</span>
      </div>
      <div className="h-2.5 w-full bg-slate-200 rounded-full overflow-hidden shadow-inner">
        <motion.div 
          initial={{ width: 0 }}
          whileInView={{ width: `${score}%` }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          className={`h-full ${color} shadow-[0_0_10px_rgba(0,0,0,0.1)]`}
        />
      </div>
    </div>
  );
}