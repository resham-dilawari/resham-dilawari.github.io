"""
vector_store.py — ChromaDB-backed semantic vector store.

Uses sentence-transformers (all-MiniLM-L6-v2, runs fully locally — no API key,
no quota, no cost) for embeddings. The model (~90 MB) is downloaded once and
cached automatically by the transformers library.

Why sentence-transformers instead of Gemini embeddings:
  The Gemini Embedding API (text-embedding-004 / gemini-embedding-001) requires
  a paid or billing-enabled API key. The existing GEMINI_API_KEY in this project
  is a free Gemini Studio key that doesn't cover the Embeddings API.
  sentence-transformers runs on-device and is a world-class embedding model that
  tops the MTEB benchmark for semantic similarity tasks.

Usage:
    vs = VectorStore()
    vs.seed_from_knowledge_base("simple_rag_db/knowledge_base.json")  # one-time
    results = vs.search("TCS valuation and earnings growth", top_k=3)
    vs.add_document({
        "content": "TCS Q3 2026: Revenue 62000 Cr...",
        "source":  "TCS Q3 FY26 Results",
        "ticker":  "TCS.NS",
        "doc_type": "quarterly_result",
    })
"""
import os
import uuid
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

logger = logging.getLogger(__name__)

# Best open-source model for semantic similarity — 90 MB, 384-dim, very fast
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class VectorStore:
    """
    Semantic vector store backed by ChromaDB with sentence-transformer embeddings.

    Data is persisted to a local directory (default: chroma_db/).
    ChromaDB runs in-process — no Docker, no server, no external API required.

    Collection layout
    -----------------
    Collection name : "financial_knowledge"
    Distance metric : cosine
    Metadata fields : source, ticker, doc_type, created_at
    """

    def __init__(self, db_path: str = "chroma_db"):
        self._embed_fn = SentenceTransformerEmbeddingFunction(
            model_name=_EMBEDDING_MODEL
        )
        self._client = chromadb.PersistentClient(path=db_path)
        self.collection = self._client.get_or_create_collection(
            name="financial_knowledge",
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_document(self, doc: Dict[str, Any]) -> str:
        """
        Embed and index one document.

        Required key : "content" (str)
        Optional keys: "id", "source", "ticker", "doc_type", "created_at"

        Returns the document ID.
        """
        doc_id = str(doc.get("id") or uuid.uuid4())
        metadata = {
            "source":     str(doc.get("source", "")),
            "ticker":     str(doc.get("ticker", "")),
            "doc_type":   str(doc.get("doc_type", "general")),
            "created_at": str(doc.get("created_at", datetime.now().isoformat())),
        }
        self.collection.add(
            documents=[doc["content"]],
            metadatas=[metadata],
            ids=[doc_id],
        )
        logger.info(f"VectorStore: indexed '{doc_id}' | source='{metadata['source']}'")
        return doc_id

    def seed_from_knowledge_base(self, kb_path: str) -> int:
        """
        One-time migration of simple_rag_db/knowledge_base.json into ChromaDB.
        Skips silently if the collection already has documents.
        Returns the number of new documents indexed.
        """
        if self.collection.count() > 0:
            logger.info("VectorStore already seeded — skipping migration.")
            return 0

        if not os.path.exists(kb_path):
            logger.warning(f"knowledge_base.json not found at '{kb_path}'. Skipping seed.")
            return 0

        with open(kb_path, encoding="utf-8") as f:
            kb = json.load(f)

        docs: List[Dict[str, Any]] = []

        for item in kb.get("stock_analyses", []):
            docs.append({
                "id":         f"stock_{item['ticker']}_{item['date']}",
                "content":    item["analysis"],
                "source":     f"{item['ticker']} Fundamental Analysis ({item['date']})",
                "ticker":     item["ticker"],
                "doc_type":   "stock_analysis",
                "created_at": item["date"],
            })

        for item in kb.get("tax_rules", []):
            safe_id = item["topic"].replace(" ", "_").lower()
            docs.append({
                "id":       f"tax_{safe_id}",
                "content":  item["content"],
                "source":   item["topic"],
                "ticker":   "",
                "doc_type": "tax_rule",
            })

        for item in kb.get("risk_frameworks", []):
            safe_id = item["topic"].replace(" ", "_").lower()
            docs.append({
                "id":       f"risk_{safe_id}",
                "content":  item["content"],
                "source":   item["topic"],
                "ticker":   "",
                "doc_type": "risk_framework",
            })

        for item in kb.get("sector_research", []):
            safe_id = item["sector"].replace(" ", "_").lower()
            docs.append({
                "id":         f"sector_{safe_id}_{item['date']}",
                "content":    item["content"],
                "source":     f"{item['sector']} Sector Research ({item['date']})",
                "ticker":     "",
                "doc_type":   "sector_research",
                "created_at": item["date"],
            })

        for doc in docs:
            self.add_document(doc)

        logger.info(f"VectorStore: seeded {len(docs)} documents from '{kb_path}'")
        return len(docs)

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 4,
        filter_ticker: str = "",
        filter_doc_type: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Semantic search.  Returns up to top_k results sorted by relevance.

        Each result dict:
            content, source, ticker, doc_type, relevance_score (0-1)

        Filtering is best-effort: automatically falls back to unfiltered
        search if the filtered set is empty or errors.
        """
        count = self.collection.count()
        if count == 0:
            return []

        n_results = min(top_k, count)

        # Build optional where-filter
        where: Optional[Dict] = None
        if filter_ticker and filter_doc_type:
            where = {"$and": [{"ticker": {"$eq": filter_ticker}},
                               {"doc_type": {"$eq": filter_doc_type}}]}
        elif filter_ticker:
            where = {"ticker": {"$eq": filter_ticker}}
        elif filter_doc_type:
            where = {"doc_type": {"$eq": filter_doc_type}}

        try:
            raw = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            # Fallback: drop filter if it returns nothing or errors
            try:
                raw = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception as e:
                logger.error(f"VectorStore.search failed: {e}")
                return []

        results = []
        for i, content in enumerate(raw["documents"][0]):
            distance = raw["distances"][0][i]
            meta = raw["metadatas"][0][i]
            results.append({
                "content":         content,
                "source":          meta.get("source", ""),
                "ticker":          meta.get("ticker", ""),
                "doc_type":        meta.get("doc_type", ""),
                "relevance_score": round(max(0.0, 1.0 - distance), 4),
            })

        return results

    def document_count(self) -> int:
        """Return total number of indexed documents."""
        return self.collection.count()
