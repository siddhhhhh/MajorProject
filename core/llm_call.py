import asyncio, logging, os, json, time
from core.llm_clients import cerebras, groq_client, openrouter, gemini_client
from core.llm_router  import ROUTING_TABLE, NO_LLM_AGENTS, Provider, ModelConfig
from core.llm_router  import get_effective_chain
import core.llm_cache as cache
from core.llm_audit  import log_call as _audit_log

logger = logging.getLogger(__name__)
MAX_RETRIES  = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY  = float(os.getenv("RETRY_DELAY_SECONDS", "2"))

# Errors that mean "skip this model entirely, don't retry"
SKIP_ERRORS = ["402", "401", "403", "insufficient credits",
               "api key", "unauthorized", "not found"]

# Errors that mean "wait and retry same model"
RETRY_ERRORS = ["429", "rate limit", "timeout", "503", "502",
                "overloaded", "service unavailable"]


async def call_llm(
    agent:      str,
    prompt:     str,
    system:     str  = None,
    use_cache:  bool = True,
    pdf_bytes:  bytes = None,   # only for carbon_extraction
) -> str:
    """
    Single entry point for all LLM calls.
    
    Args:
        agent:      Agent name — must match a key in ROUTING_TABLE
        prompt:     User prompt
        system:     Optional system prompt
        use_cache:  Use disk cache (default True)
        pdf_bytes:  Raw PDF bytes — only needed for carbon_extraction
    
    Returns:
        str: Model response
    
    Raises:
        ValueError:   If agent is in NO_LLM_AGENTS or not in ROUTING_TABLE
        RuntimeError: If all providers in the chain fail
    """

    # Guard: never call LLM for pipeline/IO agents
    if agent in NO_LLM_AGENTS:
        raise ValueError(
            f"Agent '{agent}' should never call an LLM. "
            f"It is a pure Python/IO agent. Remove the LLM call."
        )

    # Guard: unknown agent
    if agent not in ROUTING_TABLE:
        raise ValueError(
            f"Agent '{agent}' has no routing entry. "
            f"Add it to ROUTING_TABLE in llm_router.py."
        )

    # Cache check — keyed on (agent, prompt, system, pdf_bytes). Model-agnostic
    # so the cache survives routing-override runs from the variance harness.
    # System is included so prompt revisions invalidate stale entries.
    if use_cache:
        hit = cache.get(agent, prompt, system=system, pdf_bytes=pdf_bytes)
        if hit:
            logger.debug("Cache hit: agent=%s", agent)
            _audit_log(
                agent=agent, provider="cache", model_id="cache",
                prompt=prompt, response=hit, system=system,
                latency_ms=0.0, cache_hit=True,
            )
            return hit

    # get_effective_chain consults ROUTING_OVERRIDE first (used by the
    # variance diagnostic harness to force a specific provider), then
    # falls back to ROUTING_TABLE[agent].
    model_chain = get_effective_chain(agent)
    last_error  = None

    for config in model_chain:
        for attempt in range(MAX_RETRIES):
            t0 = time.perf_counter()
            try:
                logger.info("Trying %s/%s for agent=%s (attempt %d)",
                            config.provider.value, config.model_id,
                            agent, attempt + 1)

                result = await _dispatch(config, prompt, system, pdf_bytes)

                latency_ms = (time.perf_counter() - t0) * 1000.0
                if use_cache:
                    cache.set(agent, prompt, result, system=system, pdf_bytes=pdf_bytes)

                logger.info("Success: %s/%s agent=%s",
                            config.provider.value, config.model_id, agent)
                _audit_log(
                    agent=agent, provider=config.provider.value,
                    model_id=config.model_id,
                    prompt=prompt, response=result, system=system,
                    latency_ms=latency_ms, cache_hit=False,
                    extra={"attempt": attempt + 1,
                           "temperature": config.temperature,
                           "json_mode": config.json_mode},
                )
                return result

            except Exception as e:
                last_error = e
                err = str(e).lower()
                latency_ms = (time.perf_counter() - t0) * 1000.0
                _audit_log(
                    agent=agent, provider=config.provider.value,
                    model_id=config.model_id,
                    prompt=prompt, response=None, system=system,
                    latency_ms=latency_ms, cache_hit=False,
                    error=str(e)[:200],
                    extra={"attempt": attempt + 1},
                )

                if any(x in err for x in SKIP_ERRORS):
                    logger.warning("Skip error on %s/%s: %s — next model",
                                   config.provider.value, config.model_id, e)
                    break  # don't retry, jump to next model

                if any(x in err for x in RETRY_ERRORS):
                    wait = RETRY_DELAY * (2 ** attempt)  # exponential backoff
                    logger.warning("Rate limit on %s/%s — waiting %.1fs",
                                   config.provider.value, config.model_id, wait)
                    await asyncio.sleep(wait)
                    continue

                logger.error("Unexpected error %s/%s: %s",
                             config.provider.value, config.model_id, e)
                break

    raise RuntimeError(
        f"All providers failed for agent='{agent}'. "
        f"Chain tried: {[c.model_id for c in model_chain]}. "
        f"Last error: {last_error}"
    )


async def _dispatch(config: ModelConfig, prompt: str,
                    system: str, pdf_bytes: bytes) -> str:

    if config.provider == Provider.GEMINI:
        return await _call_gemini(config, prompt, system, pdf_bytes)
    elif config.provider == Provider.GROQ:
        return await _call_groq(config, prompt, system)
    elif config.provider == Provider.CEREBRAS:
        return await _call_cerebras(config, prompt, system)
    elif config.provider == Provider.OPENROUTER:
        return await _call_openrouter(config, prompt, system)
    else:
        raise ValueError(f"Unknown provider: {config.provider}")


async def _call_gemini(config, prompt, system, pdf_bytes) -> str:
    from core.llm_clients import gemini_client
    from google.genai import types

    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    if config.json_mode:
        full_prompt += "\n\nReturn valid JSON only. No markdown, no explanation."

    contents = []
    if pdf_bytes:
        contents.append(
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        )
    contents.append(full_prompt)

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: gemini_client.models.generate_content(
            model=config.model_id,
            contents=contents,
        )
    )

    text = response.text.strip()
    if config.json_mode and text.startswith("```"):
        text = "\n".join(
            l for l in text.split("\n")
            if not l.strip().startswith("```")
        ).strip()
    return text


async def _call_groq(config, prompt, system) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Groq requires the word "json" in messages when json_mode=True
    if config.json_mode:
        # Append to last user message — guaranteed to contain "json"
        messages[-1]["content"] += "\n\nRespond with valid JSON only."

    kwargs = dict(
        model=config.model_id,
        messages=messages,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )
    if config.json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await groq_client.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()


# Cerebras serves reasoning-tier models (gpt-oss-120b, zai-glm-4.7) that emit
# a chain-of-thought trace in `message.reasoning` before producing the actual
# reply in `message.content`. The reasoning tokens are billed against
# max_tokens, so a tight budget (e.g. 300) leaves the model no room for the
# reply and content comes back None. Boost the budget for known reasoning
# models so the configured max_tokens applies to the *output*, not the trace.
_CEREBRAS_REASONING_MODELS = {"gpt-oss-120b", "zai-glm-4.7"}
_CEREBRAS_REASONING_HEADROOM = 1200


async def _call_cerebras(config, prompt, system) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    effective_max_tokens = config.max_tokens
    if config.model_id in _CEREBRAS_REASONING_MODELS:
        effective_max_tokens = config.max_tokens + _CEREBRAS_REASONING_HEADROOM

    kwargs = dict(
        model=config.model_id,
        messages=messages,
        max_tokens=effective_max_tokens,
        temperature=config.temperature,
    )
    if config.json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await cerebras.chat.completions.create(**kwargs)
    message = response.choices[0].message
    content = getattr(message, "content", None)
    if content:
        return content.strip()

    # Reasoning model ran out of budget before it produced a reply — surface
    # this as a recoverable error so the chain falls through to the next
    # provider instead of returning empty string downstream.
    finish_reason = getattr(response.choices[0], "finish_reason", None)
    reasoning_preview = (getattr(message, "reasoning", "") or "")[:160]
    raise RuntimeError(
        f"Cerebras {config.model_id} returned empty content "
        f"(finish_reason={finish_reason}, reasoning_preview={reasoning_preview!r}). "
        f"Likely exhausted max_tokens={effective_max_tokens} on chain-of-thought."
    )


async def _call_openrouter(config, prompt, system) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = dict(
        model=config.model_id,
        messages=messages,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
    )
    if config.json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await openrouter.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()
