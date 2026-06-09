from dataclasses import dataclass, field
from enum import Enum
import os
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
    # Default temperature=0.0 for reproducibility. ESG analysis is judgment
    # work, not creative writing — determinism > diversity. Individual
    # entries can override if they truly need exploratory sampling.
    temperature:  float = 0.0
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
#
# PINNING POLICY (for inter-LLM reproducibility):
#   PINNED   — model_id contains a version tag that's stable across time.
#              Examples: "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
#              "qwen-3-235b-a22b-instruct-2507", "mistral-small-3.1-24b-...".
#   FLOATING — model_id is an alias the provider can re-point silently.
#              Examples: "gemini-2.0-flash" (Google rolls minor revisions),
#              ":free" tags on OpenRouter (latest snapshot of that tier),
#              "gemini-2.5-pro-preview" (preview channel).
#
# Floating IDs are kept because they're the only zero-cost path on
# OpenRouter / Google. The audit log records the exact model_id sent on
# every call so a divergence between two runs can be traced even when the
# alias resolves differently on each side. Production deployments that
# need stronger reproducibility should swap the FLOATING entries for the
# paid equivalent of the same version.
# ═══════════════════════════════════════════════════════════
# Global OR fallback aliases — use these throughout
OR_REASONING = OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=2000)  # FLOATING (:free)
OR_JSON      = OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=2000)  # PINNED (3.1-24b)
OR_GENERAL   = OR("google/gemma-3-27b-it:free", max_tokens=2000)  # FLOATING (:free)

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
        Cerebras("gpt-oss-120b",         json_mode=True, max_tokens=4096),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=4096),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=4096),
    ],

    "claim_extractor": [
        Cerebras("gpt-oss-120b",         json_mode=True, max_tokens=4096),
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
        Cerebras("gpt-oss-120b",         max_tokens=500),
        OR("meta-llama/llama-4-scout:free", max_tokens=500),
    ],

    "credibility_analysis": [
        # Batched: one call covers ~6 sources at ~150 tokens each → 1500 cap
        # leaves headroom for JSON wrapper without truncation mid-array.
        Cerebras("gpt-oss-120b",         json_mode=True, max_tokens=1500),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=1500),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", json_mode=True, max_tokens=1500),
    ],

    "climatebert_analysis": [
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=300),
        Cerebras("gpt-oss-120b",         json_mode=True, max_tokens=300),
        OR("microsoft/phi-4-reasoning:free", json_mode=True, max_tokens=300),
    ],

    "greenwishing_detection": [
        Groq("llama-3.3-70b-versatile",     json_mode=True, max_tokens=1500),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1500),
        Gemini("gemini-2.0-flash",          json_mode=True, max_tokens=1500),
    ],

    "esg_mismatch": [
        Groq("llama-3.3-70b-versatile",     json_mode=True, max_tokens=1500),
        Cerebras("zai-glm-4.7",          json_mode=True, max_tokens=1500),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1500),
    ],

    "temporal_analysis": [
        # GLM-4.7 (reasoning tier) replaces the retired Qwen-235B slot
        Cerebras("zai-glm-4.7",          json_mode=True, max_tokens=800),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=800),
        OR("meta-llama/llama-4-maverick:free", json_mode=True, max_tokens=800),
    ],

    "temporal_consistency": [
        # gemma2-9b-it decommissioned — replaced with qwen3-32b on Groq
        Groq("qwen/qwen3-32b",           json_mode=True, max_tokens=600),
        Cerebras("gpt-oss-120b",         json_mode=True, max_tokens=600),
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
        Cerebras("zai-glm-4.7",          json_mode=True, max_tokens=1000),
        Groq("llama-3.1-8b-instant",     json_mode=True, max_tokens=1000),
        OR("meta-llama/llama-4-maverick:free", json_mode=True, max_tokens=1000),
    ],

    "confidence_scoring": [
        Cerebras("gpt-oss-120b",         json_mode=True, max_tokens=300),
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
        Cerebras("zai-glm-4.7",          max_tokens=600),
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
        Cerebras("gpt-oss-120b",         max_tokens=300),
        OR("meta-llama/llama-4-maverick:free", max_tokens=300),
    ],

    "summarise": [
        # llama-4-scout on Groq has 16e (16 experts) — good for summarisation
        Groq("meta-llama/llama-4-scout-17b-16e-instruct", max_tokens=800),
        Cerebras("gpt-oss-120b",         max_tokens=800),
        Gemini("gemini-2.0-flash",       max_tokens=800),
    ],

    "conflict_resolution": [
        Groq("llama-3.3-70b-versatile",     max_tokens=1000),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1000),
        Cerebras("zai-glm-4.7",          max_tokens=1000),
    ],

    "financial_analysis": [
        Groq("llama-3.3-70b-versatile",     max_tokens=1500),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1500),
        Gemini("gemini-2.0-flash",          max_tokens=1500),
    ],

    "debate_orchestrator": [
        Groq("meta-llama/llama-4-scout-17b-16e-instruct", max_tokens=800),
        Cerebras("gpt-oss-120b",         max_tokens=800),
        OR("mistralai/mistral-small-3.1-24b-instruct:free", max_tokens=800),
    ],

    "promise_extraction": [
        Groq("llama-3.3-70b-versatile",     json_mode=True, max_tokens=1500),
        OR("meta-llama/llama-3.3-70b-instruct:free", max_tokens=1500),
        Cerebras("zai-glm-4.7",          json_mode=True, max_tokens=1500),
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

# Provider/model pairs that consistently return 404 ("not found") for the
# active API key. The Cerebras plan exposes only a subset of models at any
# given time; when an ID drops out of the catalog we list it here so the
# router skips it instead of paying the 404 latency on every fallback.
# Override with ESG_ALLOW_RETIRED_MODELS=1 for compatibility probes.
_RETIRED_MODELS = {
    (Provider.CEREBRAS, "llama3.1-8b"),
    (Provider.CEREBRAS, "qwen-3-235b-a22b-instruct-2507"),
}


def _sanitize_chain(chain: List[ModelConfig]) -> List[ModelConfig]:
    """Drop provider/model pairs known to be unavailable.

    The retired Cerebras llama3.1-8b endpoint returns a guaranteed 404, which
    adds latency before every fallback and increases pressure on downstream
    rate limits. Keep an env override for deliberate compatibility probes.
    """
    if os.getenv("ESG_ALLOW_RETIRED_MODELS", "0").lower() in {"1", "true", "yes"}:
        return chain
    filtered = [
        config for config in chain
        if (config.provider, config.model_id) not in _RETIRED_MODELS
    ]
    return filtered or chain


def get_primary_model_config(agent_name: str) -> ModelConfig:
    chain = ROUTING_TABLE.get(agent_name)
    if not chain:
        raise ValueError(f"No routing chain configured for agent '{agent_name}'.")
    return _sanitize_chain(chain)[0]


# ═══════════════════════════════════════════════════════════
# ROUTING OVERRIDE — used by the variance diagnostic harness
# ═══════════════════════════════════════════════════════════
# When non-None, every agent's effective chain is replaced by this map.
# Two shapes are supported:
#   {"_all_": Provider.GEMINI}        → force every call to the chain entry
#                                       whose provider matches; if none match
#                                       in the original chain, fall through.
#   {agent_name: [ModelConfig, ...]}  → per-agent explicit override.
# Set/reset by harness code. Production code should leave it None.
ROUTING_OVERRIDE: Optional[Dict[str, Any]] = None


def set_routing_override(override: Optional[Dict[str, Any]]) -> None:
    """Install or clear a routing override. Used by the variance harness."""
    global ROUTING_OVERRIDE
    ROUTING_OVERRIDE = override


def get_effective_chain(agent_name: str) -> List[ModelConfig]:
    """Return the model chain to use for this agent, honoring any active
    ROUTING_OVERRIDE. Falls back to ROUTING_TABLE when no override applies.
    """
    base_chain = ROUTING_TABLE.get(agent_name)
    if not base_chain:
        raise ValueError(f"No routing chain configured for agent '{agent_name}'.")
    base_chain = _sanitize_chain(base_chain)
    if ROUTING_OVERRIDE is None:
        return base_chain

    # Per-agent override wins.
    if agent_name in ROUTING_OVERRIDE:
        ov = ROUTING_OVERRIDE[agent_name]
        if isinstance(ov, list):
            return _sanitize_chain(ov)
        if isinstance(ov, ModelConfig):
            return _sanitize_chain([ov])

    # Provider-wide override: filter the base chain to only models from
    # the forced provider. If none match, append a Gemini-flash safety
    # net so the call still proceeds (and the audit log records the swap).
    forced = ROUTING_OVERRIDE.get("_all_")
    if isinstance(forced, Provider):
        filtered = [c for c in base_chain if c.provider == forced]
        if filtered:
            return filtered
        # No entry for forced provider in this chain; return the base
        # chain unchanged so the agent still works, and the audit log
        # will show the actual provider used.
        return base_chain

    return base_chain


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
