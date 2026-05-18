import os
import json
import hashlib
import time

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache", "llm_responses")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_TTL_BY_AGENT = {
    "credibility_analysis": 30 * 24 * 60 * 60,  # 30 days
    "peer_comparison":      14 * 24 * 60 * 60,  # 14 days
    "temporal_analysis":     7 * 24 * 60 * 60,  # 7 days
    "default":               7 * 24 * 60 * 60,  # 7 days
}


def _hash_key(prompt: str, system: str | None = None, pdf_bytes: bytes | None = None) -> str:
    h = hashlib.sha256()
    h.update(prompt.encode("utf-8"))
    if system:
        h.update(b"\x00SYS\x00")
        h.update(system.encode("utf-8"))
    if pdf_bytes:
        h.update(b"\x00PDF\x00")
        h.update(hashlib.sha256(pdf_bytes).digest())
    return h.hexdigest()[:32]


def _get_cache_path(
    agent: str,
    prompt: str,
    system: str | None = None,
    pdf_bytes: bytes | None = None,
) -> str:
    h = _hash_key(prompt, system, pdf_bytes)
    agent_dir = os.path.join(CACHE_DIR, agent)
    os.makedirs(agent_dir, exist_ok=True)
    return os.path.join(agent_dir, f"{h}.json")


def _legacy_path(agent: str, prompt: str) -> str:
    """Old md5-on-prompt-only path. Used for one-shot read-fallback so we
    don't burn the free-tier quota rebuilding the cache after the schema
    change. Never written to."""
    h = hashlib.md5(prompt.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, agent, f"{h}.json")


def get(
    agent: str,
    prompt: str,
    system: str | None = None,
    pdf_bytes: bytes | None = None,
) -> str | None:
    # New-scheme lookup first.
    path = _get_cache_path(agent, prompt, system, pdf_bytes)
    if not os.path.exists(path):
        # Fall back to legacy md5(prompt-only) layout once, but only if
        # there's no PDF / system to disambiguate — otherwise the legacy
        # entry could mask a real divergence.
        if not system and not pdf_bytes:
            legacy = _legacy_path(agent, prompt)
            if os.path.exists(legacy):
                path = legacy
            else:
                return None
        else:
            return None

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return None

    timestamp = data.get("timestamp", 0)
    ttl = CACHE_TTL_BY_AGENT.get(agent, CACHE_TTL_BY_AGENT["default"])

    if time.time() - timestamp > ttl:
        return None

    return data.get("response")


def set(
    agent: str,
    prompt: str,
    response: str,
    system: str | None = None,
    pdf_bytes: bytes | None = None,
) -> None:
    path = _get_cache_path(agent, prompt, system, pdf_bytes)
    data = {
        "timestamp": time.time(),
        "response": response,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
