"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Search, 
  BrainCircuit, 
  CheckCircle2, 
  Loader2,
  ShieldAlert,
  Download,
  ChevronRight,
  TrendingDown,
  TrendingUp,
  FileText,
  AlertOctagon
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

type AppState = "input" | "processing" | "results";

export default function AnalyzePage() {
  const [appState, setAppState] = useState<AppState>("input");
  
  // Form State
  const [company, setCompany] = useState("Tesla");
  const [claim, setClaim] = useState("We are completely carbon neutral across all our operations.");
  const [industry, setIndustry] = useState("Automotive");

  // Processing State
  const [currentStep, setCurrentStep] = useState(0);
  const processingSteps = [
    "Collecting Evidence Context...",
    "Running Autonomous AI Agents...",
    "Performing Carbon Footprint Analysis...",
    "Evaluating Regulatory Compliance...",
    "Calculating Machine Learning Risk Score...",
    "Generating Final ESG Report..."
  ];

  // Results State
  const [results, setResults] = useState<any>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setAppState("processing");
    
    // Simulate pipeline steps animation
    const interval = setInterval(() => {
      setCurrentStep(prev => {
        if (prev < processingSteps.length - 1) return prev + 1;
        clearInterval(interval);
        return prev;
      });
    }, 1500);

    try {
      const res = await fetch("/api/analyze-company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_name: company, claim, industry })
      });
      const data = await res.json();
      
      if (res.ok) {
        setResults(data);
        setTimeout(() => setAppState("results"), 1000);
      }
    } catch (err) {
      console.error(err);
      setAppState("input");
    }
  };

  const InputView = () => (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-2xl mx-auto mt-8"
    >
      <div className="mb-8">
        <h2 className="text-2xl font-bold font-heading text-neutral-900 tracking-tight">Run ESG Analysis</h2>
        <p className="text-neutral-500 text-sm mt-1">Input corporate claims to detect greenwashing signatures using our multi-agent pipeline.</p>
      </div>

      <Card className="border-neutral-200 shadow-sm bg-white">
        <CardContent className="p-6 md:p-8">
          <form onSubmit={handleAnalyze} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="company">Company Name</Label>
              <Input 
                id="company" 
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="e.g., Apple, Tesla, BP" 
                required 
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="industry">Industry</Label>
              <select 
                id="industry"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="flex h-10 w-full rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                required
              >
                <option value="Automotive">Automotive</option>
                <option value="Energy">Energy</option>
                <option value="Technology">Technology</option>
                <option value="Finance">Finance</option>
                <option value="Fashion">Fashion & Retail</option>
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="claim">ESG Claim to Analyze</Label>
              <textarea 
                id="claim" 
                value={claim}
                onChange={(e) => setClaim(e.target.value)}
                placeholder="Paste the sustainability claim here..." 
                className="flex min-h-[120px] w-full rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                required 
              />
              <p className="text-xs text-neutral-500">Provide direct quotes from reports, marketing materials, or earnings calls for best results.</p>
            </div>

            <Button type="submit" className="w-full text-base py-6 group" size="lg">
              <BrainCircuit className="w-5 h-5 mr-2 group-hover:animate-pulse" />
              Run ESG Analysis Pipeline
            </Button>
          </form>
        </CardContent>
      </Card>
    </motion.div>
  );

  const ProcessingView = () => (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="max-w-2xl mx-auto mt-16 text-center"
    >
      <div className="w-24 h-24 bg-primary-50 rounded-full flex items-center justify-center mx-auto mb-8 relative">
        <div className="absolute inset-0 rounded-full border-4 border-primary-200 border-t-primary-600 animate-spin" />
        <BrainCircuit className="w-10 h-10 text-primary-600 animate-pulse" />
      </div>

      <h3 className="text-2xl font-bold font-heading text-neutral-900 mb-2">Analyzing Intelligence...</h3>
      <p className="text-neutral-500 mb-12">Please wait while our 14 autonomous agents process the data.</p>

      <div className="bg-white rounded-xl border border-neutral-200 p-6 text-left shadow-sm space-y-4">
        {processingSteps.map((step, idx) => (
          <div key={idx} className="flex items-center gap-4">
            {idx < currentStep ? (
              <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
              </div>
            ) : idx === currentStep ? (
              <div className="w-6 h-6 rounded-full bg-primary-100 flex items-center justify-center shrink-0">
                <Loader2 className="w-4 h-4 text-primary-600 animate-spin" />
              </div>
            ) : (
              <div className="w-6 h-6 rounded-full border border-neutral-300 flex items-center justify-center shrink-0" />
            )}
            <span className={`text-sm ${idx < currentStep ? 'text-neutral-900 font-medium' : idx === currentStep ? 'text-primary-700 font-semibold' : 'text-neutral-400'}`}>
              {step}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );

  const ResultsView = () => {
    if (!results) return null;

    return (
      <motion.div 
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-5xl mx-auto mt-4 space-y-6"
      >
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-semibold text-primary-700 uppercase tracking-wider bg-primary-50 px-2 py-1 rounded-md">
                Intelligence Report
              </span>
              <span className="text-sm text-neutral-500">{new Date().toLocaleDateString()}</span>
            </div>
            <h2 className="text-3xl font-bold font-heading text-neutral-900">{results.company_name}</h2>
            <p className="text-neutral-600 mt-1 max-w-2xl italic">"{results.claim}"</p>
          </div>
          
          <div className="flex gap-3 mt-4 sm:mt-0">
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" /> PDF
            </Button>
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" /> JSON
            </Button>
            <Button size="sm" onClick={() => setAppState("input")}>
              New Analysis
            </Button>
          </div>
        </div>

        {/* Top Highlight Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="md:col-span-2 border-red-200 bg-red-50/50 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-6 opacity-10">
              <AlertOctagon className="w-24 h-24 text-red-600" />
            </div>
            <CardContent className="p-6 relative z-10 flex flex-col justify-center h-full">
              <div className="text-sm font-semibold text-red-600 mb-1">Greenwashing Risk Level</div>
              <div className="text-4xl font-bold font-heading text-red-700 mb-2">{results.risk_level}</div>
              <div className="text-sm text-red-600/80">
                Confidence: {(results.confidence * 100).toFixed(0)}%
              </div>
            </CardContent>
          </Card>
          
          <Card className="border-neutral-200 shadow-sm bg-white">
            <CardContent className="p-6 flex flex-col justify-center h-full items-center text-center">
              <div className="text-sm font-semibold text-neutral-500 mb-2">Overall ESG Score</div>
              <div className="relative">
                {/* Custom Gauge placeholder */}
                <svg viewBox="0 0 36 36" className="w-20 h-20 circular-chart orange">
                  <path className="circle-bg" stroke="#f0f0f0" strokeWidth="3" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                  <path className="circle" stroke="#f59e0b" strokeWidth="3" strokeDasharray={`${results.esg_score}, 100`} fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                  <text x="18" y="22.5" className="text-sm font-bold font-heading" textAnchor="middle" fill="#171717">{results.esg_score}</text>
                </svg>
              </div>
            </CardContent>
          </Card>
          
          <Card className="border-neutral-200 shadow-sm bg-white text-center">
            <CardContent className="p-6 flex flex-col justify-center h-full items-center">
              <div className="text-sm font-semibold text-neutral-500 mb-2">Industry Percentile</div>
              <div className="text-3xl font-bold font-heading text-neutral-800 mb-1">24th</div>
              <div className="flex items-center text-xs text-red-600 font-medium">
                <TrendingDown className="w-3 h-3 mr-1" />
                Below avg
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column */}
          <div className="lg:col-span-2 space-y-6">
            
            <Card className="border-neutral-200 shadow-sm bg-white">
              <CardHeader className="pb-3 border-b border-neutral-100">
                <CardTitle className="text-lg">Executive Verdict</CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <p className="text-neutral-700 leading-relaxed">
                  {results.summary}
                </p>
              </CardContent>
            </Card>

            <Card className="border-neutral-200 shadow-sm bg-white">
              <CardHeader className="pb-3 border-b border-neutral-100 flex flex-row items-center justify-between">
                <CardTitle className="text-lg">Evidence Discovered</CardTitle>
                <span className="bg-neutral-100 text-neutral-600 px-2 py-1 rounded text-xs font-semibold">{results.evidence.length} sources</span>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-neutral-100">
                  {results.evidence.map((ev: any) => (
                    <div key={ev.id} className="p-4 hover:bg-neutral-50 transition-colors flex gap-4">
                      <div className="mt-1">
                        {ev.type === 'regulatory' ? <ShieldAlert className="w-5 h-5 text-red-500" /> :
                         ev.type === 'news' ? <FileText className="w-5 h-5 text-blue-500" /> :
                         <FileText className="w-5 h-5 text-neutral-500" />}
                      </div>
                      <div>
                        <a href={ev.link} className="font-medium text-neutral-900 hover:text-primary-600 hover:underline">
                          {ev.title}
                        </a>
                        <div className="flex items-center gap-3 text-xs text-neutral-500 mt-1.5">
                          <span className="font-semibold">{ev.source}</span>
                          <span className="w-1 h-1 rounded-full bg-neutral-300" />
                          <span>{ev.date}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="border-neutral-200 shadow-sm bg-white">
              <CardHeader className="pb-3 border-b border-neutral-100">
                <CardTitle className="text-lg">ML Explainability (SHAP Values)</CardTitle>
                <CardDescription>Factors influencing the greenwashing risk score.</CardDescription>
              </CardHeader>
              <CardContent className="p-6">
                <div className="space-y-4">
                  {results.shap_explanation.map((item: any, idx: number) => (
                    <div key={idx} className="flex items-center text-sm">
                      <div className="w-1/3 font-medium text-neutral-700">{item. фактор || item.factor}</div>
                      <div className="w-2/3 flex items-center">
                        {item.effect === 'increases' ? (
                          <div className="h-6 bg-red-100 rounded-r-md min-w-[20px] flex items-center justify-end pr-2" style={{ width: `${item.weight * 100}%` }}>
                            <span className="text-xs font-bold text-red-700">+{item.weight.toFixed(2)}</span>
                          </div>
                        ) : (
                          <div className="h-6 bg-green-100 rounded-l-md min-w-[20px] flex items-center justify-start pl-2" style={{ width: `${item.weight * 100}%`, marginLeft: 'auto' }}>
                            <span className="text-xs font-bold text-green-700">-{item.weight.toFixed(2)}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

          </div>

          {/* Right Column */}
          <div className="space-y-6">
            
            <Card className="border-neutral-200 shadow-sm bg-white">
              <CardHeader className="pb-3 border-b border-neutral-100">
                <CardTitle className="text-lg">ESG Pillar Scores</CardTitle>
              </CardHeader>
              <CardContent className="p-6 space-y-5">
                <div>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="font-medium text-neutral-700">Environmental</span>
                    <span className="text-amber-600 font-bold">{results.pillar_scores.environmental}</span>
                  </div>
                  <div className="w-full bg-neutral-100 rounded-full h-2">
                    <div className="bg-amber-400 h-2 rounded-full" style={{ width: `${results.pillar_scores.environmental}%` }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="font-medium text-neutral-700">Social</span>
                    <span className="text-primary-600 font-bold">{results.pillar_scores.social}</span>
                  </div>
                  <div className="w-full bg-neutral-100 rounded-full h-2">
                    <div className="bg-primary-500 h-2 rounded-full" style={{ width: `${results.pillar_scores.social}%` }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="font-medium text-neutral-700">Governance</span>
                    <span className="text-primary-600 font-bold">{results.pillar_scores.governance}</span>
                  </div>
                  <div className="w-full bg-neutral-100 rounded-full h-2">
                    <div className="bg-primary-500 h-2 rounded-full" style={{ width: `${results.pillar_scores.governance}%` }}></div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-neutral-200 shadow-sm bg-white">
              <CardHeader className="pb-3 border-b border-neutral-100">
                <CardTitle className="text-lg">Agent Execution Timeline</CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <div className="space-y-4">
                  {results.agent_outputs.map((agent: any, idx: number) => (
                    <div key={idx} className="flex gap-3">
                      <div className="flex flex-col items-center">
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center ${agent.alert ? 'bg-amber-100 text-amber-600' : 'bg-green-100 text-green-600'}`}>
                          {agent.alert ? <AlertOctagon className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                        </div>
                        {idx !== results.agent_outputs.length - 1 && (
                          <div className="w-px h-6 bg-neutral-200 my-1" />
                        )}
                      </div>
                      <div className="-mt-0.5">
                        <div className={`text-sm font-medium ${agent.alert ? 'text-amber-700' : 'text-neutral-700'}`}>{agent.name}</div>
                        <div className="text-xs text-neutral-400 capitalize">{agent.status}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

          </div>
        </div>
      </motion.div>
    );
  };

  return (
    <AnimatePresence mode="wait">
      {appState === "input" && <InputView key="input" />}
      {appState === "processing" && <ProcessingView key="processing" />}
      {appState === "results" && <ResultsView key="results" />}
    </AnimatePresence>
  );
}
