/**
 * stores/analysisStore.ts
 * -------------------------
 * Zustand store for the active ESG analysis lifecycle.
 * Now streams real pipeline logs from the backend subprocess.
 */
import { create } from "zustand";
import * as api from "../lib/api";
import type { LogEntry } from "../lib/api";

interface AnalysisStore {
  // State
  currentAnalysisId: string | null;
  currentReport: api.ESGReport | null;
  isRunning: boolean;
  progress: number;
  elapsedSeconds: number;
  logs: LogEntry[];
  error: string | null;
  wsRef: WebSocket | null;

  // Actions
  startAnalysis: (payload: {
    company: string;
    claim: string;
    industry?: string;
    focus_areas?: string[];
  }) => Promise<string>;
  connectToStream: (analysisId: string) => void;
  loadReport: (id: string) => Promise<void>;
  clearCurrent: () => void;
}

export const useAnalysisStore = create<AnalysisStore>((set, get) => ({
  currentAnalysisId: null,
  currentReport: null,
  isRunning: false,
  progress: 0,
  elapsedSeconds: 0,
  logs: [],
  error: null,
  wsRef: null,

  startAnalysis: async (payload) => {
    const existingWs = get().wsRef;
    if (existingWs) existingWs.close();

    set({
      isRunning: true,
      error: null,
      progress: 0,
      elapsedSeconds: 0,
      logs: [],
      currentReport: null,
    });

    const { analysis_id } = await api.startAnalysis(payload);
    set({ currentAnalysisId: analysis_id });
    get().connectToStream(analysis_id);
    return analysis_id;
  },

  connectToStream: (analysisId) => {
    const ws = api.connectPipelineStream(
      analysisId,
      // onLog - real pipeline log line
      (log) =>
        set((state) => ({
          logs: [...state.logs, log],
        })),
      // onProgress
      (pct, elapsed) =>
        set({ progress: pct, elapsedSeconds: elapsed }),
      // onComplete
      (report) =>
        set({ currentReport: report, isRunning: false, progress: 100 }),
      // onError
      (msg) => set({ error: msg, isRunning: false })
    );

    set({ wsRef: ws });
  },

  loadReport: async (id) => {
    try {
      const report = await api.getReport(id);
      set({ currentReport: report });
    } catch (e) {
      set({ error: String(e) });
    }
  },

  clearCurrent: () => {
    const existingWs = get().wsRef;
    if (existingWs) existingWs.close();
    set({
      currentAnalysisId: null,
      currentReport: null,
      isRunning: false,
      progress: 0,
      elapsedSeconds: 0,
      logs: [],
      error: null,
      wsRef: null,
    });
  },
}));
