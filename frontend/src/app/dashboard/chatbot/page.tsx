"use client";

import { FormEvent, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, MessageSquareText, PlayCircle, ShieldAlert, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ESG_CHAT_API_BASE, apiJson } from "@/lib/esg-chat-api";

type ReportResponse = {
  status: string;
  company?: string;
  report_timestamp?: string;
  txt_file_name?: string;
  json_file_name?: string;
  txt_report: string;
  json_report: Record<string, unknown> | null;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
  contradictions?: string[];
  confidence?: string;
};

function randomSessionId() {
  return `esg-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`;
}

function toArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item)).filter(Boolean);
}

function guessScore(report: ReportResponse | null): string {
  const json = report?.json_report || {};
  const score = (json.esg_score || json.risk_level || "UNKNOWN") as string;
  return String(score);
}

function guessEvidence(report: ReportResponse | null): string[] {
  const json = report?.json_report || {};
  const evidence = json.evidence;
  if (Array.isArray(evidence)) {
    return evidence.slice(0, 6).map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const obj = item as Record<string, unknown>;
        return String(obj.snippet || obj.source || JSON.stringify(obj));
      }
      return String(item);
    });
  }
  return [];
}

function guessContradictions(report: ReportResponse | null): string[] {
  const json = report?.json_report || {};
  const contradictions = json.contradictions;
  if (!Array.isArray(contradictions)) return [];
  return contradictions.slice(0, 6).map((item) => String(item));
}

export default function ChatbotPage() {
  const [company, setCompany] = useState("Unilever");
  const [industry, setIndustry] = useState("Consumer Goods");
  const [claim, setClaim] = useState("Unilever aims to achieve net-zero emissions across its value chain by 2039.");

  const [sessionId, setSessionId] = useState(randomSessionId());
  const [question, setQuestion] = useState("");
  const [provider, setProvider] = useState("gemini");

  const [runningAnalysis, setRunningAnalysis] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);

  const [report, setReport] = useState<ReportResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState("");

  const score = useMemo(() => guessScore(report), [report]);
  const evidence = useMemo(() => guessEvidence(report), [report]);
  const contradictions = useMemo(() => guessContradictions(report), [report]);

  const runAnalysis = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setRunningAnalysis(true);
    try {
      const result = await apiJson<ReportResponse>("/run-analysis", {
        method: "POST",
        body: JSON.stringify({ company, industry, claim }),
      });
      setReport(result);
      setMessages([
        {
          role: "assistant",
          content: "Analysis complete. Ask me about contradictions, evidence quality, ESG risk, or confidence reasoning.",
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run analysis");
    } finally {
      setRunningAnalysis(false);
    }
  };

  const loadLatestReport = async () => {
    setError("");
    setLoadingReport(true);
    try {
      const result = await apiJson<ReportResponse>(`/report?company=${encodeURIComponent(company)}`);
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load latest report");
    } finally {
      setLoadingReport(false);
    }
  };

  const askQuestion = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;

    const currentQuestion = question.trim();
    setQuestion("");
    setError("");
    setChatLoading(true);

    setMessages((prev) => [...prev, { role: "user", content: currentQuestion }]);

    try {
      const response = await fetch(`${ESG_CHAT_API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          question: currentQuestion,
          provider,
          chunk_size: 45,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(await response.text());
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let pending = "";
      let assistantText = "";
      let citations: string[] = [];
      let contradictionNotes: string[] = [];
      let confidence = "";

      const flushAssistant = () => {
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last && last.role === "assistant") {
            copy[copy.length - 1] = {
              role: "assistant",
              content: assistantText,
              citations,
              contradictions: contradictionNotes,
              confidence,
            };
            return copy;
          }
          return [
            ...copy,
            {
              role: "assistant",
              content: assistantText,
              citations,
              contradictions: contradictionNotes,
              confidence,
            },
          ];
        });
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        pending += decoder.decode(value, { stream: true });
        const events = pending.split("\n\n");
        pending = events.pop() || "";

        for (const eventChunk of events) {
          const lines = eventChunk.split("\n");
          const eventName = lines.find((line) => line.startsWith("event:"))?.replace("event:", "").trim();
          const dataText = lines.find((line) => line.startsWith("data:"))?.replace("data:", "").trim() || "{}";

          if (!eventName) continue;

          if (eventName === "meta") {
            const meta = JSON.parse(dataText) as Record<string, unknown>;
            citations = toArray(meta.citations);
            contradictionNotes = toArray(meta.contradictions);
            confidence = String(meta.confidence_explanation || "");
            flushAssistant();
          }

          if (eventName === "message") {
            const payload = JSON.parse(dataText) as { delta?: string };
            assistantText += payload.delta || "";
            flushAssistant();
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed");
    } finally {
      setChatLoading(false);
    }
  };

  const resetSession = () => {
    setSessionId(randomSessionId());
    setMessages([]);
    setQuestion("");
    setError("");
  };

  return (
    <div className="space-y-6 pb-12">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-2xl font-bold text-neutral-900 tracking-tight">ESG Analyst Assistant</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Run ESG analysis, inspect report evidence, and ask grounded follow-up questions.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PlayCircle className="w-5 h-5" />
                Run Analysis
              </CardTitle>
              <CardDescription>Pipeline trigger for company claim analysis.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={runAnalysis} className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="company">Company</Label>
                  <Input id="company" value={company} onChange={(e) => setCompany(e.target.value)} required />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="industry">Industry</Label>
                  <Input id="industry" value={industry} onChange={(e) => setIndustry(e.target.value)} required />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="claim">Claim</Label>
                  <textarea
                    id="claim"
                    className="w-full min-h-24 border border-neutral-300 rounded-md px-3 py-2 text-sm"
                    value={claim}
                    onChange={(e) => setClaim(e.target.value)}
                    required
                  />
                </div>
                <Button className="w-full" type="submit" disabled={runningAnalysis}>
                  {runningAnalysis ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  Run Analysis
                </Button>
              </form>

              <div className="mt-3 flex gap-2">
                <Button variant="outline" onClick={loadLatestReport} disabled={loadingReport}>
                  {loadingReport ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  Load Report
                </Button>
                <Button variant="ghost" onClick={resetSession}>New Chat Session</Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Report Snapshot</CardTitle>
              <CardDescription>Auto-updates after each analysis run.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="rounded-md border border-neutral-200 p-3">
                <div className="text-xs text-neutral-500">ESG Score / Risk</div>
                <div className="text-lg font-semibold text-neutral-900">{score}</div>
              </div>
              <div>
                <div className="text-xs text-neutral-500 mb-1">Evidence Highlights</div>
                <ul className="space-y-1 text-neutral-700 list-disc pl-4">
                  {evidence.length ? evidence.map((item, idx) => <li key={`${item}-${idx}`}>{item}</li>) : <li>No evidence parsed yet.</li>}
                </ul>
              </div>
              <div>
                <div className="text-xs text-neutral-500 mb-1">Contradictions</div>
                <ul className="space-y-1 text-neutral-700 list-disc pl-4">
                  {contradictions.length ? contradictions.map((item, idx) => <li key={`${item}-${idx}`}>{item}</li>) : <li>No contradictions available in report.</li>}
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="xl:col-span-8">
          <Card className="h-full">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquareText className="w-5 h-5" />
                Chatbot Panel
              </CardTitle>
              <CardDescription>
                Grounded in generated report artifacts only. API base: {ESG_CHAT_API_BASE}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <div className="rounded-md border border-neutral-200 p-2 text-xs text-neutral-600">Session: {sessionId}</div>
                <div className="rounded-md border border-neutral-200 p-2 text-xs text-neutral-600">Provider: {provider}</div>
                <div className="rounded-md border border-neutral-200 p-2 text-xs text-neutral-600">Report: {report?.txt_file_name || "not loaded"}</div>
              </div>

              <div className="border border-neutral-200 rounded-lg p-3 min-h-[430px] max-h-[520px] overflow-y-auto bg-white space-y-3">
                {!messages.length ? (
                  <div className="text-sm text-neutral-500">No messages yet. Run analysis and ask a report-based ESG question.</div>
                ) : null}
                {messages.map((message, idx) => (
                  <div
                    key={`${message.role}-${idx}`}
                    className={`rounded-lg p-3 text-sm ${
                      message.role === "user" ? "bg-neutral-900 text-white ml-10" : "bg-neutral-100 text-neutral-800 mr-10"
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{message.content}</div>
                    {message.role === "assistant" && message.contradictions?.length ? (
                      <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-amber-800 text-xs">
                        <div className="font-semibold flex items-center gap-1">
                          <ShieldAlert className="w-3.5 h-3.5" />
                          Contradictions
                        </div>
                        <ul className="list-disc pl-4 mt-1 space-y-0.5">
                          {message.contradictions.map((item, contradictionIdx) => <li key={`${item}-${contradictionIdx}`}>{item}</li>)}
                        </ul>
                      </div>
                    ) : null}
                    {message.role === "assistant" && message.confidence ? (
                      <div className="mt-2 text-xs text-neutral-600 border-t border-neutral-300 pt-2">
                        <span className="font-semibold">Confidence explanation:</span> {message.confidence}
                      </div>
                    ) : null}
                    {message.role === "assistant" && message.citations?.length ? (
                      <div className="mt-2 text-[11px] text-neutral-600">
                        <span className="font-semibold">Citations:</span> {message.citations.join(", ")}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>

              <form onSubmit={askQuestion} className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                  <div className="md:col-span-3">
                    <Input
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      placeholder="Ask: Why is this claim misleading? Which evidence contradicts it?"
                      disabled={chatLoading}
                    />
                  </div>
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    className="border border-neutral-300 rounded-md px-2 text-sm"
                  >
                    <option value="gemini">Gemini</option>
                    <option value="grok">Grok</option>
                  </select>
                </div>
                <Button type="submit" disabled={chatLoading} className="w-full md:w-auto">
                  {chatLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                  Ask ESG Assistant
                </Button>
              </form>

              {error ? (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
