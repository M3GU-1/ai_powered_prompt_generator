"""FAISS vector index loading and similarity search."""

from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings


class VectorSearch:
    def __init__(self, index_path: str = "data/faiss_index"):
        self.index_path = index_path
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
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

    @property
    def is_loaded(self) -> bool:
        return self.vector_store is not None

    def search(self, query: str, k: int = 10) -> list[dict]:
        """Perform similarity search. Returns list of {tag, category, count, score}."""
        if not self.vector_store:
            return []

        results = self.vector_store.similarity_search_with_score(query, k=k)
        output = []
        for doc, distance in results:
            # FAISS returns L2 distance; convert to 0-1 similarity
            # L2 distance for normalized vectors: d = 2(1 - cos_sim)
            # cos_sim = 1 - d/2
            similarity = max(0.0, 1.0 - distance / 2.0)
            output.append({
                "tag": doc.metadata["tag"],
                "category": doc.metadata["category"],
                "count": doc.metadata["count"],
                "score": round(similarity, 4),
            })
        return output
