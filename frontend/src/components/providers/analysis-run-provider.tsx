"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

export type AppState = "input" | "processing" | "results";

export type LogEntry = {
  message: string;
  level: "info" | "warn" | "error" | "success";
  source: "stdout" | "stderr";
  ts: string;
};

export type AnalysisResult = {
  status: string;
  company_name: string;
  claim: string;
  industry: string;
  risk_level: string;
  confidence: number;
  summary: string;
  report_markdown: string;
  report_file_name: string;
  report_created_at: string;
  parsed_main_report?: {
    company: string;
    ticker: string;
    industry: string;
    claim: string;
    reportDate: string;
    reportConfidence: string;
    riskScore: string;
    esgRating: string;
    riskBand: string;
    confidence: string;
    keyDetails: Array<{ key: string; value: string }>;
    narrative: string[];
    // Pillar scores
    environmentalScore: string | null;
    socialScore: string | null;
    governanceScore: string | null;
    // Evidence
    evidenceCount: string | null;
    contradictionsFound: string | null;
    // Deception
    deceptionRisk: string | null;
    greenwishingScore: string | null;
    greenhushingScore: string | null;
    // Regulatory
    complianceScore: string | null;
    complianceGaps: string | null;
    // Carbon
    scope1: string | null;
    scope2: string | null;
    scope3: string | null;
    netZeroTarget: string | null;
    renewableEnergy: string | null;
    // Sections
    executiveSummary: string;
    keyRiskDrivers: string[];
    contradictions: string[];
  };
  json_report?: Record<string, unknown> | null;
  json_file_name?: string;
};

type AnalysisRunContextValue = {
  appState: AppState;
  logs: LogEntry[];
  results: AnalysisResult | null;
  runningCompany: string;
  progressPct: number;
  runStatusLabel: string;
  startAnalysis: (payload: { company: string; claim: string; industry: string }) => Promise<void>;
  resetRun: () => void;
};

const STORAGE_KEY = "esg-analysis-live-run";
const DUPLICATE_WINDOW_MS = 7000;
const MAX_LOGS = 120;
const MAX_PERSISTED_LOGS = 80;
const MAX_PERSISTED_LOG_MESSAGE_CHARS = 400;

type PersistedHistoryItem = {
  company_name: string;
  claim: string;
  industry: string;
  risk_level: string;
  confidence: number;
  report_created_at: string;
  report_file_name: string;
};

const AnalysisRunContext = createContext<AnalysisRunContextValue | null>(null);

function sanitizeDisplayMessage(message: string): string {
  return message;
}

function truncateText(value: string, maxChars: number): string {
  if (value.length <= maxChars) return value;
  return `${value.slice(0, maxChars)}...`;
}

function isQuotaExceededError(error: unknown): boolean {
  if (!(error instanceof DOMException)) return false;
  return (
    error.name === "QuotaExceededError" ||
    error.name === "NS_ERROR_DOM_QUOTA_REACHED" ||
    error.code === 22 ||
    error.code === 1014
  );
}

function setStorageItemSafely(key: string, value: string): boolean {
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch (error) {
    if (!isQuotaExceededError(error)) {
      throw error;
    }
    return false;
  }
}

function compactForHistory(result: AnalysisResult): PersistedHistoryItem {
  return {
    company_name: result.company_name,
    claim: truncateText(result.claim || "", 240),
    industry: result.industry,
    risk_level: result.risk_level,
    confidence: typeof result.confidence === "number" ? result.confidence : 0,
    report_created_at: result.report_created_at,
    report_file_name: result.report_file_name,
  };
}

function compactForPersistence(result: AnalysisResult | null): AnalysisResult | null {
  if (!result) return null;

  const compactNarrative = Array.isArray(result.parsed_main_report?.narrative)
    ? result.parsed_main_report?.narrative
        .slice(0, 5)
        .map((paragraph) => truncateText(String(paragraph), 600))
    : [];

  return {
    ...result,
    claim: truncateText(result.claim || "", 600),
    summary: truncateText(result.summary || "", 1800),
    report_markdown: "",
    json_report: null,
    parsed_main_report: result.parsed_main_report
      ? {
          ...result.parsed_main_report,
          keyDetails: result.parsed_main_report.keyDetails?.slice(0, 12) || [],
          narrative: compactNarrative,
        }
      : undefined,
  };
}

function persistLiveRunState(input: {
  appState: AppState;
  logs: LogEntry[];
  results: AnalysisResult | null;
  runningCompany: string;
}): void {
  const compactLogs = input.logs.slice(-MAX_PERSISTED_LOGS).map((entry) => ({
    ...entry,
    message: truncateText(entry.message || "", MAX_PERSISTED_LOG_MESSAGE_CHARS),
  }));

  const basePayload = {
    appState: input.appState,
    logs: compactLogs,
    results: compactForPersistence(input.results),
    runningCompany: truncateText(input.runningCompany || "", 120),
  };

  const fallbacks = [
    basePayload,
    { ...basePayload, logs: basePayload.logs.slice(-25) },
    { ...basePayload, logs: [], results: null, appState: input.appState === "results" ? "input" : input.appState },
  ];

  for (const payload of fallbacks) {
    if (setStorageItemSafely(STORAGE_KEY, JSON.stringify(payload))) {
      return;
    }
  }

  window.localStorage.removeItem(STORAGE_KEY);
}

function saveHistory(result: AnalysisResult): void {
  if (typeof window === "undefined") return;
  const key = "esg-analysis-history";

  let existingRaw = "";
  try {
    existingRaw = window.localStorage.getItem(key) || "";
  } catch {
    existingRaw = "";
  }

  let existing: PersistedHistoryItem[] = [];
  if (existingRaw) {
    try {
      const parsed = JSON.parse(existingRaw) as Array<Partial<PersistedHistoryItem>>;
      existing = parsed
        .filter((item) => item && typeof item.company_name === "string")
        .map((item) => ({
          company_name: String(item.company_name || ""),
          claim: truncateText(String(item.claim || ""), 240),
          industry: String(item.industry || ""),
          risk_level: String(item.risk_level || ""),
          confidence: typeof item.confidence === "number" ? item.confidence : 0,
          report_created_at: String(item.report_created_at || ""),
          report_file_name: String(item.report_file_name || ""),
        }));
    } catch {
      existing = [];
    }
  }

  const next = [compactForHistory(result), ...existing];
  for (const limit of [30, 15, 8, 3]) {
    if (setStorageItemSafely(key, JSON.stringify(next.slice(0, limit)))) {
      return;
    }
  }

  window.localStorage.removeItem(key);
}

function normalizeLogMessage(message: string): string {
  return message.replace(/\s+/g, " ").trim().toLowerCase();
}

export function AnalysisRunProvider({ children }: { children: React.ReactNode }) {
  const [appState, setAppState] = useState<AppState>("input");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [results, setResults] = useState<AnalysisResult | null>(null);
  const [runningCompany, setRunningCompany] = useState("");

  const duplicateGateRef = useRef<Map<string, number>>(new Map());
  const streamActiveRef = useRef(false);
  const activeRunTokenRef = useRef(0);
  const inFlightRunsRef = useRef(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (!saved) return;

    try {
      const parsed = JSON.parse(saved) as {
        appState?: AppState;
        logs?: LogEntry[];
        results?: AnalysisResult | null;
        runningCompany?: string;
      };

      // Only recover state if it was actively processing,
      // otherwise start completely fresh so we don't show truncated old results.
      if (parsed.appState === "processing") {
        setAppState(parsed.appState);
        if (Array.isArray(parsed.logs)) setLogs(parsed.logs.slice(-MAX_LOGS));
        if (parsed.results) setResults(parsed.results);
        if (parsed.runningCompany) setRunningCompany(parsed.runningCompany);
      } else {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    persistLiveRunState({ appState, logs, results, runningCompany });
  }, [appState, logs, results, runningCompany]);

  const appendLog = useCallback((incoming: LogEntry) => {
    const now = Date.now();
    const key = normalizeLogMessage(incoming.message);
    const previousAt = duplicateGateRef.current.get(key) || 0;

    if (now - previousAt < DUPLICATE_WINDOW_MS) {
      return;
    }

    duplicateGateRef.current.set(key, now);
    setLogs((prev) => [...prev, incoming].slice(-MAX_LOGS));
  }, []);

  const resetRun = useCallback(() => {
    setAppState("input");
    setLogs([]);
    setResults(null);
    setRunningCompany("");
  }, []);

  const startAnalysis = useCallback(async (payload: { company: string; claim: string; industry: string }) => {
    const hadActiveRun = inFlightRunsRef.current > 0;
    const runToken = Date.now();
    activeRunTokenRef.current = runToken;
    inFlightRunsRef.current += 1;

    if (hadActiveRun) {
      appendLog({
        message: "Starting a new backend run in parallel. Live view switched to the latest run.",
        level: "warn",
        source: "stdout",
        ts: new Date().toISOString(),
      });
    }

    streamActiveRef.current = true;
    duplicateGateRef.current.clear();
    setResults(null);
    setLogs([]);
    setRunningCompany(payload.company);
    setAppState("processing");

    try {
      const response = await fetch("/api/analyze-company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_name: payload.company, claim: payload.claim, industry: payload.industry }),
      });

      if (!response.ok || !response.body) {
        const bodyText = await response.text();
        throw new Error(bodyText || "Unable to start analysis.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let runResult: AnalysisResult | null = null;
      let runError = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";

        for (const chunk of chunks) {
          const lines = chunk.split("\n");
          const eventLine = lines.find((line) => line.startsWith("event:"));
          const dataLine = lines.find((line) => line.startsWith("data:"));
          if (!eventLine || !dataLine) continue;

          const event = eventLine.replace("event:", "").trim();
          const payloadData = JSON.parse(dataLine.replace("data:", "").trim()) as Record<string, unknown>;

          if (event === "log") {
            const incomingLevel = (payloadData.level as LogEntry["level"]) || "info";
            const safeLevel: LogEntry["level"] = incomingLevel === "error" ? "warn" : incomingLevel;
            if (activeRunTokenRef.current === runToken) {
              appendLog({
                message: sanitizeDisplayMessage(String(payloadData.message || "")),
                level: safeLevel,
                source: (payloadData.source as LogEntry["source"]) || "stdout",
                ts: String(payloadData.ts || new Date().toISOString()),
              });
            }
          }

          if (event === "status") {
            const state = String(payloadData.state || "info");
            const message = String(payloadData.message || "");
            if (message && activeRunTokenRef.current === runToken) {
              const level: LogEntry["level"] = state === "fallback" ? "warn" : state === "idle" ? "warn" : "info";
              appendLog({
                message,
                level,
                source: "stdout",
                ts: String(payloadData.ts || new Date().toISOString()),
              });
            }
          }

          if (event === "error") {
            runError = true;
          }

          if (event === "result") {
            const nextResult = payloadData as unknown as AnalysisResult;
            runResult = nextResult;
            if (activeRunTokenRef.current === runToken) {
              setResults(nextResult);
            }
            saveHistory(nextResult);
          }

          if (event === "end") {
            if (activeRunTokenRef.current === runToken) {
              if (payloadData.ok && runResult) {
                setAppState("results");
              } else if (!payloadData.ok) {
                setAppState("input");
              }
            }
          }
        }
      }

      if (!runError && runResult && activeRunTokenRef.current === runToken) {
        setAppState("results");
      }
      if (!runResult && !runError && activeRunTokenRef.current === runToken) {
        setAppState("input");
      }
    } catch (error) {
      const detail = error instanceof Error && error.message ? ` (${error.message})` : "";
      if (activeRunTokenRef.current === runToken) {
        appendLog({
          message: `Request finished without a new report${detail}. Previous fallback data is still available.`,
          level: "warn",
          source: "stderr",
          ts: new Date().toISOString(),
        });
        setAppState("input");
      }
    } finally {
      inFlightRunsRef.current = Math.max(0, inFlightRunsRef.current - 1);
      if (inFlightRunsRef.current === 0) {
        streamActiveRef.current = false;
      }
    }
  }, [appendLog]);

  const progressPct = useMemo(() => {
    if (appState === "results") return 100;
    if (appState !== "processing") return 0;
    return Math.min(92, 18 + logs.length * 2);
  }, [appState, logs.length]);

  const runStatusLabel = useMemo(() => {
    if (appState === "processing") return "Live run in progress";
    if (appState === "results") return "Run completed";
    return "Ready";
  }, [appState]);

  const value = useMemo<AnalysisRunContextValue>(
    () => ({
      appState,
      logs,
      results,
      runningCompany,
      progressPct,
      runStatusLabel,
      startAnalysis,
      resetRun,
    }),
    [appState, logs, results, runningCompany, progressPct, runStatusLabel, startAnalysis, resetRun],
  );

  return <AnalysisRunContext.Provider value={value}>{children}</AnalysisRunContext.Provider>;
}

export function useAnalysisRun(): AnalysisRunContextValue {
  const context = useContext(AnalysisRunContext);
  if (!context) {
    throw new Error("useAnalysisRun must be used within AnalysisRunProvider");
  }
  return context;
}
