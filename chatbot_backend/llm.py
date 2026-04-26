"""
llm.py
------
LLM clients for the ESG chatbot backend.

Provider chain: Gemini → Groq (GROQ_API_KEY).
No crash if one key is missing — that provider is skipped gracefully.
"""
from __future__ import annotations

import json
import os
from typing import Any

from chatbot_backend.config import Settings


class LLMProviderError(RuntimeError):
    pass


class BaseLLMClient:
    name: str

    def generate_response(self, *, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

class GeminiClient(BaseLLMClient):
    name = "gemini"

    def __init__(self, model: str) -> None:
        self.model = model
        self._genai = None

    def _ensure_client(self):
        if self._genai is not None:
            return self._genai
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise LLMProviderError("google-generativeai package is not installed") from exc

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise LLMProviderError("GEMINI_API_KEY is not set")

        genai.configure(api_key=api_key)
        self._genai = genai
        return self._genai

    def generate_response(self, *, system_prompt: str, user_prompt: str) -> str:
        genai = self._ensure_client()
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
        )
        response = model.generate_content(user_prompt)
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise LLMProviderError("Gemini returned an empty response")
        return text


# ---------------------------------------------------------------------------
# Groq  (uses GROQ_API_KEY from .env — OpenAI-compatible API)
# ---------------------------------------------------------------------------

class GroqClient(BaseLLMClient):
    name = "groq"

    def __init__(self, model: str) -> None:
        self.model = model
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMProviderError("openai package is not installed") from exc

        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise LLMProviderError("GROQ_API_KEY is not set")

        from openai import OpenAI
        self._client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        return self._client

    def generate_response(self, *, system_prompt: str, user_prompt: str) -> str:
        client = self._ensure_client()
        completion = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content or ""
        if not content.strip():
            raise LLMProviderError("Groq returned an empty response")
        return content


# ---------------------------------------------------------------------------
# Orchestrator — tries providers in order, never crashes on a missing key
# ---------------------------------------------------------------------------

class LLMOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.clients: dict[str, BaseLLMClient] = {
            "gemini": GeminiClient(settings.gemini_model),
            "groq":   GroqClient(settings.groq_model),
        }

    def generate_response(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        provider: str | None = None,
    ) -> tuple[str, str]:
        # Build deduplicated provider chain
        chain = [provider, self.settings.llm_provider, self.settings.llm_fallback_provider]
        ordered = list(dict.fromkeys(name for name in chain if name and name in self.clients))

        last_error: Exception | None = None
        for name in ordered:
            try:
                text = self.clients[name].generate_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                return text, name
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

        if last_error is None:
            raise LLMProviderError("No valid LLM provider configured")
        raise LLMProviderError(f"All LLM providers failed. Last error: {last_error}")


# ---------------------------------------------------------------------------
# JSON parser
# ---------------------------------------------------------------------------

def parse_llm_json(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        cleaned = "\n".join(
            line for line in cleaned.splitlines()
            if not line.strip().startswith("```")
        )
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Best-effort: return raw text in answer field
        return {"answer": cleaned, "citations": [], "contradictions": [], "scope": "ESG_ANALYSIS"}
