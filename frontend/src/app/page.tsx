"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { 
  ArrowRight, 
  BrainCircuit, 
  Leaf, 
  ShieldAlert, 
  Activity, 
  Database, 
  FileSearch,
  CheckCircle2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-background selection:bg-primary-200">
      <Navbar />

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 overflow-hidden">
        {/* Background Gradients */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
          <div className="absolute top-[-10%] right-[-5%] w-[50%] h-[50%] rounded-full bg-primary-100/50 blur-[120px]" />
          <div className="absolute bottom-[20%] left-[-10%] w-[40%] h-[60%] rounded-full bg-primary-200/30 blur-[150px]" />
        </div>

        <div className="container mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="max-w-4xl mx-auto space-y-8"
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-50 border border-primary-200 text-primary-700 text-sm font-medium mb-4">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary-500"></span>
              </span>
              Enterprise ESG Grade Intelligence
            </div>
            
            <h1 className="text-5xl md:text-7xl font-heading font-bold text-neutral-900 tracking-tight leading-tight">
              AI-Powered <br className="hidden md:block" />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-primary-800">
                ESG Intelligence
              </span>
            </h1>
            
            <p className="text-lg md:text-xl text-neutral-600 max-w-2xl mx-auto leading-relaxed">
              Detect greenwashing, analyze sustainability claims, and uncover ESG risks using multi-agent AI, machine learning, and regulatory intelligence.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
              <Link href="/signup">
                <Button size="lg" className="h-12 px-8 w-full sm:w-auto text-base group">
                  Analyze ESG Claims
                  <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
              <Link href="#platform">
                <Button size="lg" variant="outline" className="h-12 px-8 w-full sm:w-auto text-base bg-white/50 backdrop-blur-sm">
                  Learn More
                </Button>
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Platform Features Grid */}
      <section id="platform" className="py-24 bg-white relative">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl md:text-4xl font-heading font-semibold text-neutral-900 mb-4">Platform Capabilities</h2>
            <p className="text-neutral-600">Comprehensive tools for rigorous sustainability intelligence and audit-ready ESG analysis.</p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: <BrainCircuit className="w-6 h-6 text-primary-600" />,
                title: "Multi-Agent ESG Analysis",
                description: "14 autonomous AI agents critically evaluate corporate claims against unstructured data."
              },
              {
                icon: <Leaf className="w-6 h-6 text-primary-600" />,
                title: "Carbon Accounting Intel",
                description: "Validates Scope 1, 2, and 3 emission data using contextual industry baselines."
              },
              {
                icon: <FileSearch className="w-6 h-6 text-primary-600" />,
                title: "Regulatory Compliance",
                description: "Automated scanning against SEBI, CSRD, SEC, and global ESG frameworks."
              },
              {
                icon: <Activity className="w-6 h-6 text-primary-600" />,
                title: "Machine Learning Risk",
                description: "Powered by XGBoost and LightGBM models with anomaly detection capabilities."
              },
              {
                icon: <ShieldAlert className="w-6 h-6 text-primary-600" />,
                title: "Greenwashing Detection",
                description: "Identify greenhushing, greenwishing, and misleading narrative tactics instantly."
              },
              {
                icon: <Database className="w-6 h-6 text-primary-600" />,
                title: "Explainable AI Reports",
                description: "Transparent SHAP explanations for every ESG risk decision and generated score."
              }
            ].map((feature, idx) => (
              <motion.div
                key={idx}
                whileHover={{ y: -5 }}
                transition={{ duration: 0.2 }}
              >
                <Card className="h-full border border-neutral-100 bg-white hover:border-primary-200 transition-colors shadow-sm cursor-default group">
                  <CardContent className="p-6">
                    <div className="w-12 h-12 rounded-lg bg-primary-50 flex items-center justify-center mb-4 group-hover:bg-primary-100 transition-colors">
                      {feature.icon}
                    </div>
                    <h3 className="text-xl font-semibold font-heading text-neutral-900 mb-2">{feature.title}</h3>
                    <p className="text-neutral-600 leading-relaxed text-sm">
                      {feature.description}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it Works Pipeline */}
      <section id="technology" className="py-24 bg-primary-900 text-white overflow-hidden relative">
        {/* Background elements */}
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary-800 rounded-full blur-[100px] opacity-50 pointer-events-none" />
        
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="text-center max-w-3xl mx-auto mb-20">
            <h2 className="text-3xl md:text-4xl font-heading font-semibold mb-4">How the Platform Works</h2>
            <p className="text-primary-100">An intelligent multi-stage pipeline designed to process unstructured ESG claims with unparalleled accuracy.</p>
          </div>

          <div className="max-w-4xl mx-auto relative">
            {/* Connecting Line */}
            <div className="hidden md:block absolute left-1/2 top-0 bottom-0 w-px bg-primary-700 -translate-x-1/2" />
            
            {[
              { title: "Corporate ESG Claim", desc: "Input physical reports, URLs, or specific claims from a company." },
              { title: "Evidence Collection", desc: "Agents retrieve millions of data points from regulatory filings and news." },
              { title: "AI Agent Analysis", desc: "Specialized models analyze sentiment, contradictions, and sentiment." },
              { title: "Machine Learning Risk Scoring", desc: "Ensemble models compute a precise risk metric using historical correlations." },
              { title: "Greenwashing Detection Report", desc: "Final generation of an audit-ready, comprehensible ESG intelligence report." }
            ].map((step, idx) => (
              <motion.div 
                key={idx} 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                className={`relative flex items-center justify-between mb-8 md:mb-12 ${idx % 2 === 0 ? 'md:flex-row' : 'md:flex-row-reverse'}`}
              >
                {/* Node */}
                <div className="absolute left-4 md:left-1/2 w-4 h-4 rounded-full bg-primary-400 border-4 border-primary-900 md:-translate-x-1/2 z-10 shadow-[0_0_15px_rgba(102,187,106,0.5)]" />
                
                {/* Content */}
                <div className={`ml-12 md:ml-0 md:w-[45%] ${idx % 2 === 0 ? 'md:text-right' : 'md:text-left'} bg-primary-800/50 backdrop-blur-sm p-6 rounded-xl border border-primary-700/50`}>
                  <div className="text-sm font-bold text-primary-400 mb-1">STEP 0{idx + 1}</div>
                  <h4 className="text-xl font-heading font-semibold mb-2">{step.title}</h4>
                  <p className="text-primary-100/80 text-sm leading-relaxed">{step.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Dashboard Preview */}
      <section className="py-24 bg-primary-50 relative overflow-hidden">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl md:text-4xl font-heading font-semibold text-neutral-900 mb-4">Intelligent Dashboard Preview</h2>
            <p className="text-neutral-600">Enterprise-grade interface built for sustainability analysts and institutional investors.</p>
          </div>

          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="rounded-2xl border border-neutral-200/60 bg-white shadow-2xl overflow-hidden relative max-w-5xl mx-auto"
          >
             {/* Mac style header */}
            <div className="h-10 bg-neutral-100 border-b border-neutral-200 flex items-center px-4 gap-2">
              <div className="w-3 h-3 rounded-full bg-red-400" />
              <div className="w-3 h-3 rounded-full bg-amber-400" />
              <div className="w-3 h-3 rounded-full bg-green-400" />
            </div>
            
            <div className="p-8 pb-12 bg-neutral-50/50">
              <div className="grid md:grid-cols-3 gap-6">
                <div className="md:col-span-1 space-y-6">
                  <div className="bg-white p-5 rounded-xl border border-neutral-100 shadow-sm">
                    <div className="text-sm text-neutral-500 font-medium mb-1">Greenwashing Risk</div>
                    <div className="text-3xl font-bold font-heading text-red-600 mb-2">High</div>
                    <div className="w-full bg-neutral-100 rounded-full h-2 mb-1">
                      <div className="bg-red-500 h-2 rounded-full w-[85%]"></div>
                    </div>
                    <div className="text-xs text-neutral-400 text-right">85% certainty</div>
                  </div>
                  
                  <div className="bg-white p-5 rounded-xl border border-neutral-100 shadow-sm space-y-3">
                    <div className="text-sm text-neutral-500 font-medium">Contradictory Evidence</div>
                    <div className="flex gap-3 text-sm">
                      <ShieldAlert className="w-5 h-5 text-amber-500 shrink-0" />
                      <span className="text-neutral-700">Scope 3 emissions omit supply chain logistics as per EU directive.</span>
                    </div>
                  </div>
                </div>
                
                <div className="md:col-span-2">
                  <div className="bg-white p-6 rounded-xl border border-neutral-100 shadow-sm h-full flex flex-col">
                    <div className="flex justify-between items-center mb-6">
                      <div className="font-semibold font-heading text-neutral-800">ESG Component Scores</div>
                    </div>
                    <div className="flex-1 space-y-6 flex flex-col justify-center">
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="font-medium">Environmental</span>
                          <span className="text-amber-600 font-bold">42/100</span>
                        </div>
                        <div className="w-full bg-neutral-100 rounded-full h-3">
                          <div className="bg-amber-400 h-3 rounded-full w-[42%]"></div>
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="font-medium">Social</span>
                          <span className="text-primary-600 font-bold">78/100</span>
                        </div>
                        <div className="w-full bg-neutral-100 rounded-full h-3">
                          <div className="bg-primary-500 h-3 rounded-full w-[78%]"></div>
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="font-medium">Governance</span>
                          <span className="text-primary-600 font-bold">85/100</span>
                        </div>
                        <div className="w-full bg-neutral-100 rounded-full h-3">
                          <div className="bg-primary-500 h-3 rounded-full w-[85%]"></div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 bg-white relative">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <Card className="bg-gradient-to-br from-primary-800 to-primary-900 border-0 shadow-2xl relative overflow-hidden">
            <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10"></div>
            <CardContent className="p-12 md:p-20 text-center relative z-10">
              <h2 className="text-3xl md:text-5xl font-heading font-bold text-white mb-6">
                Start Detecting ESG Greenwashing Today
              </h2>
              <p className="text-primary-100 text-lg md:text-xl max-w-2xl mx-auto mb-10">
                Join leading enterprises and investors utilizing AI for precise, transparent, and rigorous sustainability analytics.
              </p>
              <div className="flex flex-col sm:flex-row justify-center gap-4">
                <Link href="/signup">
                  <Button size="lg" className="h-14 px-8 text-base text-primary-900 bg-white hover:bg-neutral-100 shadow-xl">
                    Create Account
                  </Button>
                </Link>
                <Link href="/login">
                  <Button size="lg" variant="outline" className="h-14 px-8 text-base text-white border-white/30 hover:bg-white/10">
                    Analyze a Company
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <Footer />
    </main>
  );
}
