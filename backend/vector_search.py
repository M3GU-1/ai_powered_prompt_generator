"""FAISS vector index loading and similarity search."""

from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings


class VectorSearch:
    _shared_embeddings: Optional[HuggingFaceEmbeddings] = None

    @classmethod
    def _get_embeddings(cls) -> HuggingFaceEmbeddings:
        """Get or create shared embedding model (avoids ~10s reload on hot-swap)."""
        if cls._shared_embeddings is None:
            cls._shared_embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
            )
        return cls._shared_embeddings

    def __init__(self, index_path: str = "data/faiss_index"):
        self.index_path = index_path
        self.embeddings = self._get_embeddings()
        self.vector_store: Optional[FAISS] = None
        self._load_index()

    def _load_index(self):
        path = Path(self.index_path)
        if not path.exists():
            print(f"Warning: FAISS index not found at {self.index_path}")
            print("Run: python scripts/build_embeddings.py")
            return

        self.vector_store = FAISS.load_local(
            self.index_path,
            self.embeddings,
            allow_dangerous_deserialization=True,
        )

    def reload(self, index_path: str):
        """Reload with a different FAISS index. Reuses embedding model."""
        self.index_path = index_path
        self.vector_store = None
        self._load_index()

    @property
    def is_loaded(self) -> bool:
        return self.vector_store is not None

    def search(self, query: str, k: int = 10, min_score: float = 0.0) -> list[dict]:
        """Perform similarity search. Returns list of {tag, category, count, score}.

        Fetches extra candidates internally so that an exact-name match
        (query == tag name) is virtually guaranteed to appear even when
        alias-diluted embeddings push it down the ranking.
        """
        if not self.vector_store:
            return []

        # Normalize query to match indexing format (build_embedding_text):
        # underscores → spaces so the embedding model sees the same surface form.
        search_query = query.strip().replace("_", " ")

        normalized_query = search_query.lower().replace(" ", "_").replace("-", "_")

        # Fetch more candidates to increase chance of finding exact matches
        fetch_k = max(k * 3, 30)
        results = self.vector_store.similarity_search_with_score(search_query, k=fetch_k)

        output = []
        for doc, distance in results:
            # FAISS returns squared L2 distance; convert to 0-1 similarity
            # For unit vectors: ||a-b||² = 2(1 - cos_sim)  →  cos_sim = 1 - d/2
            similarity = max(0.0, 1.0 - distance / 2.0)
            if similarity < min_score:
                continue
            tag_name = doc.metadata["tag"]

            # Boost score when the query closely matches the tag name itself.
            # This compensates for embeddings that were diluted by alias text.
            norm_tag = tag_name.lower()
            if norm_tag == normalized_query:
                # Exact name match → treat as near-perfect similarity
                similarity = max(similarity, 0.99)
            elif normalized_query in norm_tag or norm_tag in normalized_query:
                # Substring containment → moderate boost
                similarity = max(similarity, similarity + 0.10)
                similarity = min(similarity, 0.98)

            output.append({
                "tag": tag_name,
                "category": doc.metadata["category"],
                "count": doc.metadata["count"],
                "score": round(similarity, 4),
            })

        # Re-sort by boosted score and return top-k
        output.sort(key=lambda x: x["score"], reverse=True)
        return output[:k]
