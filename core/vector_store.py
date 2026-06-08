from typing import List, Dict, Any, Optional
from config.settings import settings
import os

# NOTE: `chromadb` is intentionally NOT imported at module top.
# It transitively pulls in onnxruntime, hnswlib, sqlite, grpc, and
# pulsar SDK stubs — on Windows with Defender real-time scan this
# easily costs 5-15 min of cold-start time. We defer the import
# (and the heavy Client() / collection init) until the first method
# that actually needs the store is called. Three agents pull
# `vector_store` eagerly in their import chain (evidence_retriever,
# regulatory_scanner, realtime_monitor); none of them touch the
# collection at import time, so this is fully transparent.


class VectorStore:
    def __init__(self):
        self.client = None
        self.collection = None
        self.collection_name = "esg_evidence"
        self.reranker_model_name = os.getenv(
            "RAG_RERANKER_MODEL",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
        self.reranker_enabled = os.getenv("RAG_RERANK_ENABLED", "1").lower() in {"1", "true", "yes"}
        self._reranker = None
        self._reranker_failed = False
        self._chromadb_init_failed = False

    def _ensure_client(self) -> bool:
        """Lazy-init chromadb on first use. Returns True if collection is ready."""
        if self.collection is not None:
            return True
        if self._chromadb_init_failed:
            return False
        try:
            import chromadb  # heavy: deferred from module load to first use
            self.client = chromadb.Client()
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "ESG evidence and claims storage"}
            )
            return True
        except Exception as e:
            print(f"⚠️ ChromaDB initialization error: {e}")
            self._chromadb_init_failed = True
            self.collection = None
            return False

    def add_documents(self, documents: List[str], metadatas: List[Dict],
                     ids: List[str]) -> None:
        """Add documents to vector store"""
        if not self._ensure_client():
            return
        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added {len(documents)} documents to vector store")
        except Exception as e:
            print(f"Error adding documents: {e}")

    def search_similar(self, query: str, n_results: int = 5,
                      filter_dict: Optional[Dict] = None) -> Dict[str, Any]:
        """Search for similar documents"""
        if not self._ensure_client():
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        try:
            candidate_count = max(n_results * 3, n_results)
            results = self.collection.query(
                query_texts=[query],
                n_results=candidate_count,
                where=filter_dict
            )

            if self.reranker_enabled:
                docs = results.get("documents", [[]])[0]
                if docs:
                    results = self._rerank_results(query, results, n_results)
                else:
                    results = self._truncate_results(results, n_results)
            else:
                results = self._truncate_results(results, n_results)

            return results
        except Exception as e:
            print(f"Error searching documents: {e}")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    def _get_reranker(self):
        if self._reranker_failed:
            return None
        if self._reranker is not None:
            return self._reranker

        try:
            from sentence_transformers import CrossEncoder

            self._reranker = CrossEncoder(self.reranker_model_name)
            return self._reranker
        except Exception as e:
            self._reranker_failed = True
            print(f"⚠️ Reranker unavailable ({self.reranker_model_name}): {e}")
            return None

    def _truncate_results(self, results: Dict[str, Any], n_results: int) -> Dict[str, Any]:
        truncated: Dict[str, Any] = {}
        for key in ["ids", "documents", "metadatas", "distances"]:
            value = results.get(key, [[]])
            if isinstance(value, list) and value:
                truncated[key] = [value[0][:n_results]]
            else:
                truncated[key] = [[]]
        return truncated

    def _rerank_results(self, query: str, results: Dict[str, Any], n_results: int) -> Dict[str, Any]:
        reranker = self._get_reranker()
        if reranker is None:
            return self._truncate_results(results, n_results)

        docs = results.get("documents", [[]])[0]
        if not docs:
            return self._truncate_results(results, n_results)

        pairs = [(query, str(doc or "")) for doc in docs]
        try:
            scores = reranker.predict(pairs)
        except Exception as e:
            print(f"⚠️ Reranker scoring failed: {e}")
            return self._truncate_results(results, n_results)

        # Bound the index space by the smaller of (docs, scores) — defensive
        # against the rare case where the reranker returns a shorter score
        # array than the pairs we sent (partial batch / model bug).
        n_valid = min(len(docs), len(scores))
        if n_valid == 0:
            return self._truncate_results(results, n_results)
        ranked_indices = sorted(range(n_valid), key=lambda i: float(scores[i]), reverse=True)[:n_results]

        reranked: Dict[str, Any] = {}
        for key in ["ids", "documents", "metadatas", "distances"]:
            value = results.get(key, [[]])
            items = value[0] if isinstance(value, list) and value else []
            reranked[key] = [[items[i] for i in ranked_indices if i < len(items)]]

        if "distances" in reranked:
            reranked["distances"] = [[float(-scores[i]) for i in ranked_indices]]

        return reranked

    def get_collection_count(self) -> int:
        """Get total documents in collection"""
        if not self._ensure_client():
            return 0
        return self.collection.count()

    def delete_collection(self) -> None:
        """Delete the collection"""
        if not self._ensure_client():
            return
        self.client.delete_collection(name=settings.CHROMA_COLLECTION_NAME)

    def clear_collection(self):
        """Clear all cached data from vector DB"""
        if not self._ensure_client():
            return
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "ESG evidence storage"}
            )
            print(f"   ✅ Vector DB '{self.collection_name}' cleared and recreated")
        except Exception as e:
            print(f"   ⚠️ Vector DB clear error: {str(e)[:80]}")


# Global instance — lightweight now; chromadb only loads on first method call.
vector_store = VectorStore()
