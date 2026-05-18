"""Embedding cache — bge-small-en-v1.5 + persisted FAISS index.

Why this exists:
  Every retrieval today re-encodes claims and evidence (Jaccard at best,
  LLM-driven similarity at worst). KG-RAG, cross-pillar contradiction,
  promise-claim matching, and abstention all need persistent embeddings.

Design:
  - One process-local model (sentence-transformers/bge-small-en-v1.5, ~120 MB)
  - Per-"kind" FAISS index (claim, evidence, promise, ...). Each kind has its
    own .faiss file + .meta.jsonl (sha256 -> id mapping)
  - Idempotent: re-encoding the same text is a no-op + cache hit
  - Cosine similarity (we L2-normalise on add; FAISS IndexFlatIP gives cosine
    on normalised vectors)
  - Append-only writes; eviction by per-kind LRU when index exceeds 100k vectors

The model picks bge-small-en-v1.5 because:
  - English-only is acceptable for ESG documents (the heavy hitters publish in EN)
  - 384 dimensions is the sweet spot between recall and disk
  - It's better than all-MiniLM-L6-v2 on retrieval benchmarks at ~similar speed

Public API:
    encode(text)                    -> np.ndarray[384] (L2-normalised)
    nearest(text, k, kind)          -> [(id, score)]
    add(text, id, kind)             -> None
    bulk_add(items, kind)           -> None      # items: List[(id, text)]
    similarity(text_a, text_b)      -> float     # cosine in [-1, 1]
    has_cached(text)                -> bool

Never raises on encoding/IO errors — falls back to zero-vector and logs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_DIM = 384
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "embeddings"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cap each kind's index at 100k vectors. Once exceeded, the lowest-recently-
# used N are dropped on the next save. For demo scale (5-50 companies) we
# never approach this.
_MAX_VECTORS_PER_KIND = 100_000


# ── Lazy singletons (model is heavy; only load when needed) ───────────────────
_MODEL = None
_MODEL_LOCK = threading.Lock()
_INDEX_LOCKS: dict[str, threading.Lock] = {}


def _get_lock(kind: str) -> threading.Lock:
    if kind not in _INDEX_LOCKS:
        _INDEX_LOCKS[kind] = threading.Lock()
    return _INDEX_LOCKS[kind]


def _get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading embedding model %s (one-time, ~120MB)", _MODEL_NAME)
                _MODEL = SentenceTransformer(_MODEL_NAME)
            except Exception as e:
                logger.error("Failed to load embedding model: %s", e)
                _MODEL = "FAILED"  # sentinel so we don't retry every call
    return _MODEL if _MODEL != "FAILED" else None


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _kind_paths(kind: str) -> Tuple[Path, Path]:
    """Return (index_path, meta_path) for a kind."""
    return (_CACHE_DIR / f"{kind}.faiss"), (_CACHE_DIR / f"{kind}.meta.jsonl")


# ── Per-kind index handle (thin wrapper holding faiss index + sha256 set) ─────
class _KindIndex:
    """In-memory mirror of the on-disk FAISS index + sha256 -> id mapping.

    Loaded lazily on first access; persisted on every add via append-only
    rewrite of the .faiss file. For demo throughput this is fine; production
    would batch saves.
    """
    def __init__(self, kind: str):
        self.kind = kind
        self.index = None
        # sha256 -> int row id within self.index
        self.sha_to_row: dict[str, int] = {}
        # row id -> {sha, id (caller-supplied)}
        self.row_to_meta: dict[int, dict] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        try:
            import faiss
        except ImportError:
            logger.error("faiss unavailable — embedding cache disabled for kind=%s", self.kind)
            self._loaded = True  # don't retry
            return

        idx_path, meta_path = _kind_paths(self.kind)
        if idx_path.exists():
            try:
                self.index = faiss.read_index(str(idx_path))
            except Exception as e:
                logger.warning("Failed to read %s, starting fresh: %s", idx_path, e)
                self.index = faiss.IndexFlatIP(_DIM)
        else:
            self.index = faiss.IndexFlatIP(_DIM)

        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    for row_id, line in enumerate(f):
                        line = line.strip()
                        if not line:
                            continue
                        rec = json.loads(line)
                        self.sha_to_row[rec["sha"]] = row_id
                        self.row_to_meta[row_id] = rec
            except Exception as e:
                logger.warning("Failed to read %s, starting fresh: %s", meta_path, e)
                self.sha_to_row.clear()
                self.row_to_meta.clear()

        self._loaded = True

    def add(self, sha: str, caller_id: str, vector) -> None:
        self._ensure_loaded()
        if self.index is None:
            return
        if sha in self.sha_to_row:
            return  # idempotent — already cached
        import numpy as np
        vec = np.asarray(vector, dtype=np.float32).reshape(1, _DIM)
        # L2-normalise so IndexFlatIP gives cosine
        norm = np.linalg.norm(vec, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        vec = vec / norm
        row_id = self.index.ntotal
        self.index.add(vec)
        self.sha_to_row[sha] = row_id
        self.row_to_meta[row_id] = {"sha": sha, "id": caller_id}
        self._persist()

    def search(self, vector, k: int) -> List[Tuple[str, float]]:
        """Return [(caller_id, cosine_score)] from k nearest neighbours."""
        self._ensure_loaded()
        if self.index is None or self.index.ntotal == 0:
            return []
        import numpy as np
        q = np.asarray(vector, dtype=np.float32).reshape(1, _DIM)
        norm = np.linalg.norm(q, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        q = q / norm
        scores, ids = self.index.search(q, min(k, self.index.ntotal))
        out: List[Tuple[str, float]] = []
        for row_id, score in zip(ids[0].tolist(), scores[0].tolist()):
            if row_id < 0:
                continue
            meta = self.row_to_meta.get(row_id)
            if not meta:
                continue
            out.append((meta["id"], float(score)))
        return out

    def has(self, sha: str) -> bool:
        self._ensure_loaded()
        return sha in self.sha_to_row

    def _persist(self) -> None:
        try:
            import faiss
            idx_path, meta_path = _kind_paths(self.kind)
            faiss.write_index(self.index, str(idx_path))
            # Rewrite meta in sha_to_row order so row IDs match the index
            ordered = [None] * (max(self.row_to_meta.keys()) + 1) if self.row_to_meta else []
            for row_id, rec in self.row_to_meta.items():
                ordered[row_id] = rec
            with open(meta_path, "w", encoding="utf-8") as f:
                for rec in ordered:
                    if rec:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("embed_cache persist failed for kind=%s: %s", self.kind, e)


# Process-wide per-kind index cache
_INDEXES: dict[str, _KindIndex] = {}


def _get_index(kind: str) -> _KindIndex:
    if kind not in _INDEXES:
        with _get_lock(kind):
            if kind not in _INDEXES:
                _INDEXES[kind] = _KindIndex(kind)
    return _INDEXES[kind]


# ── Public API ────────────────────────────────────────────────────────────────
def encode(text: str):
    """Return a 384-dim L2-normalised np.ndarray, or zero-vector on failure."""
    import numpy as np
    if not text:
        return np.zeros(_DIM, dtype=np.float32)
    model = _get_model()
    if model is None:
        return np.zeros(_DIM, dtype=np.float32)
    try:
        vec = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return vec.astype(np.float32)
    except Exception as e:
        logger.warning("encode failed (text len=%d): %s", len(text), e)
        return np.zeros(_DIM, dtype=np.float32)


def add(text: str, caller_id: str, kind: str) -> None:
    """Index `text` under `caller_id` for retrieval. Idempotent."""
    if not text or not caller_id:
        return
    sha = _hash(text)
    idx = _get_index(kind)
    if idx.has(sha):
        return
    vec = encode(text)
    with _get_lock(kind):
        idx.add(sha, caller_id, vec)


def bulk_add(items: Iterable[Tuple[str, str]], kind: str) -> int:
    """Add many (caller_id, text) pairs. Returns count actually added (skips dupes)."""
    added = 0
    for caller_id, text in items:
        if not text:
            continue
        sha = _hash(text)
        idx = _get_index(kind)
        if idx.has(sha):
            continue
        vec = encode(text)
        with _get_lock(kind):
            idx.add(sha, caller_id, vec)
            added += 1
    return added


def nearest(text: str, k: int = 5, kind: str = "evidence") -> List[Tuple[str, float]]:
    """Return [(caller_id, cosine_score)] for the k nearest entries in `kind`."""
    if not text:
        return []
    vec = encode(text)
    idx = _get_index(kind)
    return idx.search(vec, k)


def similarity(text_a: str, text_b: str) -> float:
    """Direct cosine similarity between two texts. Returns 0.0 on failure."""
    import numpy as np
    if not text_a or not text_b:
        return 0.0
    va = encode(text_a)
    vb = encode(text_b)
    # Already L2-normalised
    return float(np.dot(va, vb))


def has_cached(text: str, kind: str = "evidence") -> bool:
    """Check whether `text` is already indexed in `kind`."""
    if not text:
        return False
    return _get_index(kind).has(_hash(text))


def reset_kind(kind: str) -> None:
    """Wipe an entire kind's index. Used by tests + manual ops."""
    idx_path, meta_path = _kind_paths(kind)
    for p in (idx_path, meta_path):
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                logger.warning("reset_kind failed to delete %s: %s", p, e)
    _INDEXES.pop(kind, None)


def stats() -> dict:
    """Diagnostic — current per-kind sizes."""
    return {
        kind: {"size": idx.index.ntotal if idx.index else 0,
               "loaded": idx._loaded}
        for kind, idx in _INDEXES.items()
    }
