/**
 * stores/chatStore.ts
 * --------------------
 * Zustand store for the ESGLens AI Chatbot.
 * Connects to the real chatbot backend (port 8001).
 */
import { create } from "zustand";
import * as api from "../lib/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  citations?: string[];
  intent?: string;
  timestamp: Date;
}

interface ChatStore {
  messages: ChatMessage[];
  isTyping: boolean;
  sessionId: string;
  activeCompany: string | null;
  activeAnalysisId: string | null;
  error: string | null;

  sendMessage: (text: string) => Promise<void>;
  setContext: (company: string, analysisId?: string) => void;
  clearChat: () => void;
}

function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function generateMsgId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  isTyping: false,
  sessionId: generateSessionId(),
  activeCompany: null,
  activeAnalysisId: null,
  error: null,

  sendMessage: async (text) => {
    const userMsg: ChatMessage = {
      id: generateMsgId(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    set((state) => ({
      messages: [...state.messages, userMsg],
      isTyping: true,
      error: null,
    }));

    try {
      const res = await api.sendChatMessage({
        session_id: get().sessionId,
        question: text,
        report_id: get().activeAnalysisId ?? undefined,
        company: get().activeCompany ?? undefined,
      });

      const answer = res.answer;
      const aiMsg: ChatMessage = {
        id: generateMsgId(),
        role: "assistant",
        content: typeof answer === "string" ? answer : answer.answer ?? "",
        sources: typeof answer === "object" ? answer.citations : [],
        citations: typeof answer === "object" ? answer.citations : [],
        intent: typeof answer === "object" ? answer.intent : undefined,
        timestamp: new Date(),
      };

      set((state) => ({
        messages: [...state.messages, aiMsg],
        isTyping: false,
      }));
    } catch (e) {
      const errorMsg: ChatMessage = {
        id: generateMsgId(),
        role: "assistant",
        content:
          "I couldn't connect to the ESG analysis service. Please ensure the chatbot backend is running on port 8001.",
        timestamp: new Date(),
      };
      set((state) => ({
        messages: [...state.messages, errorMsg],
        isTyping: false,
        error: String(e),
      }));
    }
  },

  setContext: (company, analysisId) =>
    set({ activeCompany: company, activeAnalysisId: analysisId ?? null }),

  clearChat: () =>
    set({
      messages: [],
      sessionId: generateSessionId(),
      error: null,
    }),
}));
