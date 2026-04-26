from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class Provider(Enum):
    GEMINI     = "gemini"
    GROQ       = "groq"
    CEREBRAS   = "cerebras"
    OPENROUTER = "openrouter"

@dataclass
class ModelConfig:
    provider:     Provider
    model_id:     str
    json_mode:    bool  = False
    max_tokens:   int   = 1000
    temperature:  float = 0.1   # low temperature for ESG — determinism matters
    context_note: str   = ""    # why this model was chosen

# Helper constructors for readability
def Gemini(model, **kw):
    return ModelConfig(Provider.GEMINI, model, **kw)
def Groq(model, **kw):
    return ModelConfig(Provider.GROQ, model, **kw)
def Cerebras(model, **kw):
    return ModelConfig(Provider.CEREBRAS, model, **kw)
def OR(model, **kw):
    return ModelConfig(Provider.OPENROUTER, model, **kw)

# ═══════════════════════════════════════════════════════════
# ROUTING TABLE
# Format: "agent_name": [primary, fallback_1, fallback_2]
# First model tried = primary. On rate-limit/error → next.
# ═══════════════════════════════════════════════════════════
# Global OR fallback aliases — use these throughout
OR_REASONING = OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=2000)
OR_JSON      = OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=2000)
OR_GENERAL   = OR("google/gemma-3-27b-it:free", max_tokens=2000)

ROUTING_TABLE: dict[str, list[ModelConfig]] = {

    "supervisor": [
        Groq("llama-3.3-70b-versatile",
             max_tokens=100, temperature=0.0,
             context_note="complexity assessment routing"),
        OR_REASONING,
        Gemini("gemini-2.0-flash",
               max_tokens=100),
    ],

    # ── STAGE 2: EXTRACTION ──────────────────────────────────────

    "carbon_extraction": [
        Gemini("gemini-2.0-flash",          json_mode=True, max_tokens=1000),
        Groq("llama-3.3-70b-versatile",     json_mode=True, max_tokens=1000),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=1000),
    ],

    "claim_extraction": [
        Cerebras("llama3.1-8b",          json_mode=True, max_tokens=4096),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=4096),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=4096),
    ],

    "claim_extractor": [
        Cerebras("llama3.1-8b",          json_mode=True, max_tokens=4096),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=4096),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=4096),
    ],

    # ── STAGE 4: ANALYSIS ────────────────────────────────────────

    "contradiction_analysis": [
        Groq("llama-3.3-70b-versatile",     max_tokens=2000, temperature=0.1),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=2000),
        Gemini("gemini-2.0-flash",          max_tokens=2000),
    ],

    "sentiment_analysis": [
        # llama-4-scout is on Groq, not Cerebras — use Groq's version
        Groq("meta-llama/llama-4-scout-17b-16e-instruct", max_tokens=500),
        Cerebras("llama3.1-8b",          max_tokens=500),
        OR("meta-llama/llama-4-scout:free", max_tokens=500),
    ],

    "credibility_analysis": [
        # Called ~47 times per report — must be fastest available
        Cerebras("llama3.1-8b",          json_mode=True, max_tokens=200),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=200),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=200),
    ],

    "climatebert_analysis": [
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=300),
        Cerebras("llama3.1-8b",          json_mode=True, max_tokens=300),
        OR("microsoft/phi-4-reasoning:free", json_mode=True, max_tokens=300),
    ],

    "greenwishing_detection": [
        Groq("llama-3.3-70b-versatile",     json_mode=True, max_tokens=1500),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1500),
        Gemini("gemini-2.0-flash",          json_mode=True, max_tokens=1500),
    ],

    "esg_mismatch": [
        Groq("llama-3.3-70b-versatile",     json_mode=True, max_tokens=1500),
        Cerebras("qwen-3-235b-a22b-instruct-2507", json_mode=True, max_tokens=1500),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1500),
    ],

    "temporal_analysis": [
        # Qwen 235B on Cerebras replaces the missing llama3.1-70b
        Cerebras("qwen-3-235b-a22b-instruct-2507", json_mode=True, max_tokens=800),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=800),
        OR("meta-llama/llama-4-maverick:free", json_mode=True, max_tokens=800),
    ],

    "temporal_consistency": [
        # gemma2-9b-it decommissioned — replaced with qwen3-32b on Groq
        Groq("qwen/qwen3-32b",           json_mode=True, max_tokens=600),
        Cerebras("llama3.1-8b",          json_mode=True, max_tokens=600),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=600),
    ],

    # ── STAGE 5: SCORING ─────────────────────────────────────────

    "regulatory_scanning": [
        # gemma2-9b-it decommissioned — qwen3-32b is strong at rule-following
        Groq("qwen/qwen3-32b",           json_mode=True, max_tokens=2000),
        Groq("llama-3.3-70b-versatile",  json_mode=True, max_tokens=2000),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=2000),
    ],

    "risk_scoring": [
        Groq("llama-3.3-70b-versatile",     json_mode=True, max_tokens=2000, temperature=0.0),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=2000),
        Gemini("gemini-2.0-flash",          json_mode=True, max_tokens=2000),
    ],

    "peer_comparison": [
        Cerebras("qwen-3-235b-a22b-instruct-2507", json_mode=True, max_tokens=1000),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=1000),
        OR("meta-llama/llama-4-maverick:free", json_mode=True, max_tokens=1000),
    ],

    "confidence_scoring": [
        Cerebras("llama3.1-8b",          json_mode=True, max_tokens=300),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=300),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=300),
    ],

    "score_json": [
        Groq("llama-3.3-70b-versatile",  json_mode=True, max_tokens=2000),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=2000),
        Gemini("gemini-2.0-flash",       json_mode=True, max_tokens=2000),
    ],

    # ── STAGE 6: GENERATION ──────────────────────────────────────

    "explainability": [
        Groq("llama-3.3-70b-versatile",  max_tokens=600),
        OR("meta-llama/llama-4-maverick:free", max_tokens=600),
        Cerebras("qwen-3-235b-a22b-instruct-2507", max_tokens=600),
    ],

    "verdict_generation": [
        Groq("llama-3.3-70b-versatile",     max_tokens=500),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=500),
        Gemini("gemini-2.0-flash",          max_tokens=500),
    ],

    "professional_report_generation": [
        Gemini("gemini-2.5-pro-preview",    max_tokens=4000),
        # gemini-2.5-pro on OpenRouter is paid but cheap — best fallback
        OR("google/gemini-2.5-pro",         max_tokens=4000),
        Gemini("gemini-2.0-flash",          max_tokens=4000),
    ],

    # ── ADDITIONAL TASKS ─────────────────────────────────────────

    "rewrite": [
        Groq("meta-llama/llama-4-scout-17b-16e-instruct", max_tokens=300),
        Cerebras("llama3.1-8b",          max_tokens=300),
        OR("meta-llama/llama-4-maverick:free", max_tokens=300),
    ],

    "summarise": [
        # llama-4-scout on Groq has 16e (16 experts) — good for summarisation
        Groq("meta-llama/llama-4-scout-17b-16e-instruct", max_tokens=800),
        Cerebras("llama3.1-8b",          max_tokens=800),
        Gemini("gemini-2.0-flash",       max_tokens=800),
    ],

    "conflict_resolution": [
        Groq("llama-3.3-70b-versatile",     max_tokens=1000),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1000),
        Cerebras("qwen-3-235b-a22b-instruct-2507", max_tokens=1000),
    ],

    "financial_analysis": [
        Groq("llama-3.3-70b-versatile",     max_tokens=1500),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1500),
        Gemini("gemini-2.0-flash",          max_tokens=1500),
    ],

    "debate_orchestrator": [
        Groq("meta-llama/llama-4-scout-17b-16e-instruct", max_tokens=800),
        Cerebras("llama3.1-8b",          max_tokens=800),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", max_tokens=800),
    ],

    "promise_extraction": [
        Groq("llama-3.3-70b-versatile",     json_mode=True, max_tokens=1500),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1500),
        Cerebras("qwen-3-235b-a22b-instruct-2507", json_mode=True, max_tokens=1500),
    ],

    "kg_extraction": [
        Groq("llama-3.3-70b-versatile",     json_mode=True, max_tokens=2000, temperature=0.0),
        Gemini("gemini-2.0-flash",          json_mode=True, max_tokens=2000),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=2000),
    ],
}


# ═══════════════════════════════════════════════════════════
# AGENTS THAT MUST NEVER CALL AN LLM
# If any of these appear in a routing call, raise an error.
# ═══════════════════════════════════════════════════════════
NO_LLM_AGENTS = {
    "report_discovery",
    "report_downloader",
    "report_parser",
    "evidence_retrieval",
    "realtime_monitoring",
}


def get_primary_model_config(agent_name: str) -> ModelConfig:
    chain = ROUTING_TABLE.get(agent_name)
    if not chain:
        raise ValueError(f"No routing chain configured for agent '{agent_name}'.")
    return chain[0]


def render_chat_messages_as_prompt(messages: List[Any]) -> tuple[str | None, str]:
    system_parts: List[str] = []
    user_parts: List[str] = []
    role_map = {
        "system": system_parts,
        "human": user_parts,
        "user": user_parts,
        "ai": user_parts,
        "assistant": user_parts,
    }
    for message in messages:
        role = getattr(message, "type", None) or getattr(message, "role", None) or "user"
        content = getattr(message, "content", "")
        bucket = role_map.get(str(role).lower(), user_parts)
        bucket.append(str(content))
    system = "\n\n".join(part for part in system_parts if part).strip() or None
    prompt = "\n\n".join(part for part in user_parts if part).strip()
    return system, prompt


def get_langchain_chat_model(
    agent_name: str,
    system_prompt: str | None = None,
    json_mode: bool = True,
):
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    import asyncio

    class RoutedLangChainChatModel(BaseChatModel):
        agent_name: str
        system_prompt: Optional[str] = None
        force_json_mode: bool = True

        @property
        def _llm_type(self) -> str:
            return "esglens_routed_chat_model"

        @property
        def _identifying_params(self) -> Dict[str, Any]:
            primary = get_primary_model_config(self.agent_name)
            return {
                "agent_name": self.agent_name,
                "provider": primary.provider.value,
                "model_id": primary.model_id,
                "json_mode": self.force_json_mode,
            }

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            from core.llm_call import call_llm

            system, prompt = render_chat_messages_as_prompt(messages)
            effective_system = self.system_prompt or system
            effective_prompt = prompt
            if self.force_json_mode:
                effective_prompt = (
                    f"{prompt}\n\n"
                    "Return valid JSON only. Use the allowed graph schema exactly."
                )
            text = asyncio.run(
                call_llm(
                    self.agent_name,
                    effective_prompt,
                    system=effective_system,
                    use_cache=False,
                )
            )
            generation = ChatGeneration(message=AIMessage(content=text))
            return ChatResult(generations=[generation])

    return RoutedLangChainChatModel(
        agent_name=agent_name,
        system_prompt=system_prompt,
        force_json_mode=json_mode,
    )
