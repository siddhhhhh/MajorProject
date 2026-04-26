"""
service.py
----------
ESGChatService — the ESG Analyst Copilot service layer.

Architecture:
  1. get_esg_context()       → structured dict from pipeline JSON
  2. detect_intent()         → what is the user asking?
  3. select_relevant_context() → only the fields needed for that intent
  4. build_user_prompt()     → inject minimal context into LLM prompt
  5. LLMOrchestrator         → Gemini → Groq fallback

No RAG. No chunking. No TXT parsing.
"""
from __future__ import annotations

import subprocess
import time
from typing import Any

from chatbot_backend.config import Settings
from chatbot_backend.intent_router import Intent, detect_intents, match_sections, select_relevant_context
from chatbot_backend.llm import LLMOrchestrator, parse_llm_json
from chatbot_backend.memory import SessionMemoryStore
from chatbot_backend.prompts import SYSTEM_PROMPT, build_user_prompt, is_esg_scope
from chatbot_backend.report_context import find_latest_report, get_esg_context


class ESGChatService:
    def __init__(self, settings: Settings, memory_store: SessionMemoryStore) -> None:
        self.settings = settings
        self.memory_store = memory_store
        self.llm = LLMOrchestrator(settings)

    # ------------------------------------------------------------------
    # Pipeline runner (unchanged logic — just triggers the LangGraph run)
    # ------------------------------------------------------------------

    def run_analysis(self, company: str, claim: str, industry: str) -> dict[str, Any]:
        started_at = time.time()
        command = [
            self.settings.python_executable,
            str(self.settings.analysis_script_path),
            "--company", company,
            "--claim",   claim,
            "--industry", industry,
        ]
        result = subprocess.run(
            command,
            cwd=self.settings.project_root,
            text=True,
            capture_output=True,
            timeout=max(120, self.settings.request_timeout_seconds * 4),
            check=False,
        )
        report = find_latest_report(
            self.settings.reports_dir, company=company, min_mtime=started_at - 3
        )
        if report is None:
            report = find_latest_report(self.settings.reports_dir, company=company)

        if report is None:
            return {
                "status":      "error",
                "company":     company,
                "txt_report":  "",
                "json_report": None,
                "stdout":      result.stdout[-3500:],
                "stderr":      result.stderr[-3500:],
                "message":     "Pipeline finished but no report artifact was found.",
            }
        return {
            "status":           "success" if result.returncode == 0 else "fallback",
            "company":          company,
            "txt_report":       report.txt_content,
            "json_report":      report.json_payload,
            "txt_file_name":    report.txt_file_name,
            "json_file_name":   report.json_file_name,
            "report_timestamp": report.modified_at.isoformat(),
            "stdout":           result.stdout[-3500:],
            "stderr":           result.stderr[-3500:],
        }

    # ------------------------------------------------------------------
    # Report loader (for the /report endpoint)
    # ------------------------------------------------------------------

    def get_latest_report(self, company: str | None = None) -> dict[str, Any] | None:
        report = find_latest_report(self.settings.reports_dir, company=company)
        if report is None:
            return None
        return {
            "status":           "success",
            "company":          company,
            "txt_report":       report.txt_content,
            "json_report":      report.json_payload,
            "txt_file_name":    report.txt_file_name,
            "json_file_name":   report.json_file_name,
            "report_timestamp": report.modified_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # ESG Analyst Copilot answer
    # ------------------------------------------------------------------

    def answer(
        self,
        *,
        session_id: str,
        question: str,
        provider: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        # 1. Guard: out-of-scope
        if not is_esg_scope(question):
            return {
                "answer": "I can only answer ESG-report questions for the generated analysis report.",
                "confidence_explanation": "Out-of-scope question blocked by ESG guardrail.",
                "contradictions": [],
                "citations": [],
                "scope": "OUT_OF_SCOPE",
            }, "guardrail"

        # 2. Load structured context (ONE function, no duplication)
        ctx = get_esg_context(self.settings.reports_dir)
        if ctx is None:
            raise ValueError("No report found. Run /run-analysis first.")

        # 3. Detect intents
        intents = detect_intents(question)
        intent_str = ", ".join(intents)
        
        question_lower = question.lower()
        import re
        
        # Check for section extraction
        sec_match = re.search(r'section\s*(\d+)', question_lower)
        if sec_match:
            sec_num = sec_match.group(1)
            for sec in ctx.get("sections", []):
                if f"section {sec_num}" in sec["section_id"].lower():
                    answer = f"**{sec['section_id']}: {sec['title']}**\n\n{sec['content']}"
                    self.memory_store.append(session_id, "user", question)
                    self.memory_store.append(session_id, "assistant", answer)
                    return {
                        "answer": answer,
                        "confidence_explanation": "Extracted directly from the TXT report.",
                        "contradictions": [],
                        "citations": [],
                        "scope": "ESG_ANALYSIS",
                        "intent": "section_lookup",
                    }, "deterministic"
        
        # Check for score extraction (only if not asking for an explanation)
        if Intent.SCORE_EXPLANATION not in intents and (Intent.SCORE in intents or any(w in question_lower for w in ["hushing", "wishing"])):
            metrics = ctx.get("txt_metrics", {})
            found_scores = []
            
            def fmt_score(k: str, v: float) -> str:
                name = k.replace('_', ' ').title()
                if "washing" in k or "hushing" in k or "wishing" in k:
                    risk = "High" if v >= 60 else "Medium" if v >= 30 else "Low"
                    return f"**{name}: {v}** — Indicates {risk} Risk."
                else:
                    perf = "Strong" if v >= 60 else "Average" if v >= 40 else "Weak"
                    return f"**{name}: {v}** — Indicates {perf} Performance."
            
            if any(w in question_lower for w in ["greenwashing", "green washing"]):
                if "greenwashing_score" in metrics:
                    found_scores.append(fmt_score("greenwashing_score", metrics['greenwashing_score']))
            if any(w in question_lower for w in ["esg", "overall esg", "esg rating"]):
                if "esg_score" in metrics:
                    found_scores.append(fmt_score("esg_score", metrics['esg_score']))
            if any(w in question_lower for w in ["greenhushing", "hushing"]):
                if "greenhushing_score" in metrics:
                    found_scores.append(fmt_score("greenhushing_score", metrics['greenhushing_score']))
            if any(w in question_lower for w in ["greenwishing", "wishing"]):
                if "greenwishing_score" in metrics:
                    found_scores.append(fmt_score("greenwishing_score", metrics['greenwishing_score']))
            
            # If they asked for a score but didn't specify which one, give the primary scores
            if not found_scores and metrics and Intent.SCORE in intents:
                if "greenwashing_score" in metrics:
                    found_scores.append(fmt_score("greenwashing_score", metrics['greenwashing_score']))
                if "esg_score" in metrics:
                    found_scores.append(fmt_score("esg_score", metrics['esg_score']))

            if found_scores:
                answer = "\n".join(found_scores)
                self.memory_store.append(session_id, "user", question)
                self.memory_store.append(session_id, "assistant", answer)
                return {
                    "answer": answer,
                    "confidence_explanation": "Extracted deterministically from report metrics.",
                    "contradictions": [],
                    "citations": ["txt_metrics"],
                    "scope": "ESG_ANALYSIS",
                    "intent": "score_lookup",
                }, "deterministic"

        # 4. Match sections and select relevant context fields for LLM fallback
        matched_sections = match_sections(question, ctx.get("sections", []))
        relevant = select_relevant_context(intents, ctx, matched_sections=matched_sections)

        # 5. Build conversation history
        history = self.memory_store.get_history(session_id)

        # 6. Build prompt and call LLM
        user_prompt = build_user_prompt(
            question=question,
            intent=intent_str,
            relevant_context=relevant,
            history=history,
        )
        raw_response, provider_used = self.llm.generate_response(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            provider=provider,
        )
        parsed = parse_llm_json(raw_response)

        # 7. Build safe, typed response
        safe_answer: dict[str, Any] = {
            "answer": str(parsed.get("answer", "No grounded answer could be generated from the report.")),
            "confidence_explanation": str(
                parsed.get("confidence_explanation", "Based on structured pipeline outputs only.")
            ),
            "contradictions": [str(x) for x in (parsed.get("contradictions") or [])][:6],
            "citations": [str(x) for x in (parsed.get("citations") or [])][:8],
            "scope": "ESG_ANALYSIS" if parsed.get("scope") != "OUT_OF_SCOPE" else "OUT_OF_SCOPE",
            # Metadata surfaced to the frontend
            "intent": intent_str,
        }

        # 8. Update memory
        self.memory_store.append(session_id, "user", question)
        self.memory_store.append(session_id, "assistant", safe_answer["answer"])

        return safe_answer, provider_used
