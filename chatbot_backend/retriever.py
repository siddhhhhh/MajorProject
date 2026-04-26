from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")


@dataclass(slots=True)
class ContextChunk:
    chunk_id: str
    source: str
    text: str



def _tokenize(text: str) -> set[str]:
    return {match.group(0).lower() for match in _WORD_RE.finditer(text)}



def _normalize_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(_normalize_value(item) for item in value if item is not None)
    if isinstance(value, dict):
        return "\n".join(f"{k}: {_normalize_value(v)}" for k, v in value.items())
    return ""



def build_chunks(structured_context: dict[str, Any], txt_content: str, min_chars: int = 220, max_chars: int = 1000) -> list[ContextChunk]:
    chunks: list[ContextChunk] = []

    for idx, (key, value) in enumerate(structured_context.items(), start=1):
        normalized = _normalize_value(value).strip()
        if not normalized:
            continue
        chunks.append(ContextChunk(chunk_id=f"json-{idx}", source=f"json.{key}", text=normalized[:max_chars]))

    paragraph_idx = 1
    for paragraph in [p.strip() for p in txt_content.split("\n\n") if p.strip()]:
        if len(paragraph) < min_chars:
            continue

        start = 0
        while start < len(paragraph):
            part = paragraph[start : start + max_chars]
            part = part.strip()
            if part:
                chunks.append(ContextChunk(chunk_id=f"txt-{paragraph_idx}", source="txt_report", text=part))
                paragraph_idx += 1
            start += max_chars

    return chunks



def rank_chunks(query: str, chunks: list[ContextChunk], limit: int = 8) -> list[ContextChunk]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return chunks[:limit]

    scored: list[tuple[float, ContextChunk]] = []
    for chunk in chunks:
        chunk_tokens = _tokenize(chunk.text)
        overlap = len(query_tokens & chunk_tokens)
        if overlap == 0:
            continue
        score = overlap / max(1, len(query_tokens))
        if "contradict" in query.lower() and "contradict" in chunk.text.lower():
            score += 0.4
        if "evidence" in query.lower() and "evidence" in chunk.source.lower():
            score += 0.2
        scored.append((score, chunk))

    if not scored:
        return chunks[:limit]

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:limit]]
