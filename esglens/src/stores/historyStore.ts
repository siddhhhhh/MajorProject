/**
 * stores/historyStore.ts
 * -----------------------
 * Zustand store for the History page - fetches all completed analyses
 * from the backend API.
 */
import { create } from "zustand";
import * as api from "../lib/api";

interface HistoryStore {
  entries: api.HistoryEntry[];
  isLoading: boolean;
  error: string | null;
  fetchHistory: () => Promise<void>;
  clearHistory: () => void;
}

export const useHistoryStore = create<HistoryStore>((set) => ({
  entries: [],
  isLoading: false,
  error: null,

  fetchHistory: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await api.getAllReports();
      set({ entries: data, isLoading: false });
    } catch (e: unknown) {
      set({ error: String(e), isLoading: false });
    }
  },

  clearHistory: () => set({ entries: [], error: null }),
}));
