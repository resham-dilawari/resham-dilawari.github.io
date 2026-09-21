"""
rag_agent.py — RAG (Retrieval-Augmented Generation) Agent

Retrieves semantically relevant financial documents from ChromaDB and
augments analysis prompts with them.  Replaces the previous mock
implementation that returned hard-coded strings pretending to be
real retrieved documents.

Knowledge sources (stored in chroma_db/):
  - Historical stock analyses (seeded from simple_rag_db/knowledge_base.json)
  - Quarterly earnings summaries (indexed after each analysis run)
  - Tax rules and SEBI guidelines
  - Risk management frameworks
  - Sector research reports
"""
from typing import Dict, Any, List
from .base_agent import BaseAgent
from datetime import datetime
import json
import logging
import sys
import os

logger = logging.getLogger(__name__)


class RAGAgent(BaseAgent):
    """
    Agent that uses real ChromaDB-backed RAG to retrieve relevant
    financial knowledge and augment analysis prompts.
    """

    def __init__(self, use_real_db: bool = True):
        super().__init__(
            agent_name="RAG Knowledge Agent",
            specialization=(
                "retrieval and integration of relevant financial knowledge "
                "from a semantically-indexed document corpus"
            ),
        )
        self._vs = None          # lazy-init to avoid import cost at startup
        self._use_real_db = use_real_db

    # ── VectorStore (lazy) ────────────────────────────────────────────────────

    def _get_vs(self):
        """Lazy-initialise VectorStore and seed from knowledge_base.json."""
        if self._vs is not None:
            return self._vs

        if not self._use_real_db:
            return None

        try:
            # Adjust path relative to the project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, project_root)
            from vector_store import VectorStore

            chroma_path = os.path.join(project_root, "chroma_db")
            kb_path = os.path.join(project_root, "simple_rag_db", "knowledge_base.json")

            self._vs = VectorStore(db_path=chroma_path)
            seeded = self._vs.seed_from_knowledge_base(kb_path)
            if seeded:
                logger.info(f"RAGAgent: seeded {seeded} documents into ChromaDB")
        except Exception as e:
            logger.error(f"RAGAgent: failed to initialise VectorStore ({e}). RAG disabled.")
            self._vs = None

        return self._vs

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve relevant documents and augment analysis with retrieved knowledge.

        Expected context keys:
            query         : str  — the user's question or analysis request
            ticker        : str  — stock ticker for context-aware filtering
            analysis_type : str  — "stock_analysis" | "tax_rule" | "risk_framework" |
                                    "sector_research" | "general"
        """
        self.log_action("start_rag_retrieval", {"query": context.get("query")})

        query         = context.get("query", "")
        ticker        = context.get("ticker", "")
        analysis_type = context.get("analysis_type", "general")

        # 1. Retrieve
        retrieved_docs = self._retrieve_documents(query, ticker, analysis_type)

        # 2. Build augmented prompt
        augmented_prompt = self._create_augmented_prompt(
            query=query,
            ticker=ticker,
            retrieved_docs=retrieved_docs,
            context=context,
        )

        # 3. Generate response
        analysis_text = self.generate_response(augmented_prompt, temperature=0.4)

        result = {
            "agent":          self.agent_name,
            "ticker":         ticker,
            "analysis":       analysis_text,
            "retrieved_docs": len(retrieved_docs),
            "sources":        [doc.get("source", "") for doc in retrieved_docs],
            "avg_relevance":  (
                round(sum(d.get("relevance_score", 0) for d in retrieved_docs) /
                      len(retrieved_docs), 3)
                if retrieved_docs else 0
            ),
            "timestamp":      datetime.now().isoformat(),
            "type":           "rag_analysis",
        }

        self.log_action("complete_rag_analysis", {
            "docs_retrieved": len(retrieved_docs),
            "avg_relevance":  result["avg_relevance"],
        })

        return result

    def index_document(self, document: Dict[str, Any]) -> bool:
        """Index a new document into ChromaDB for future retrieval."""
        vs = self._get_vs()
        if vs is None:
            logger.warning("RAGAgent.index_document: VectorStore unavailable.")
            return False
        try:
            vs.add_document(document)
            self.log_action("index_document", {
                "source": document.get("source"),
                "ticker": document.get("ticker"),
            })
            return True
        except Exception as e:
            logger.error(f"RAGAgent.index_document failed: {e}")
            return False

    def update_knowledge_base(self, analysis_result: Dict[str, Any]) -> bool:
        """
        Store a fresh analysis result back into the knowledge base.
        This creates the self-learning loop: past analyses inform future retrieval.
        """
        vs = self._get_vs()
        if vs is None:
            return False
        try:
            doc = {
                "content":  analysis_result.get("analysis", ""),
                "source":   f"{analysis_result.get('ticker', 'Unknown')} "
                            f"Analysis ({datetime.now().strftime('%Y-%m-%d')})",
                "ticker":   analysis_result.get("ticker", ""),
                "doc_type": "stock_analysis",
            }
            vs.add_document(doc)
            self.log_action("update_knowledge_base", {
                "ticker": doc["ticker"],
                "source": doc["source"],
            })
            return True
        except Exception as e:
            logger.error(f"RAGAgent.update_knowledge_base failed: {e}")
            return False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _retrieve_documents(
        self,
        query: str,
        ticker: str,
        analysis_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve semantically relevant documents from ChromaDB.
        Falls back to an empty list if the vector store is unavailable.
        """
        vs = self._get_vs()
        if vs is None or vs.document_count() == 0:
            logger.warning("RAGAgent: VectorStore empty or unavailable — returning no documents.")
            return []

        # Map analysis_type to a doc_type filter for ChromaDB
        doc_type_map = {
            "fundamental": "stock_analysis",
            "risk":        "risk_framework",
            "tax":         "tax_rule",
            "sector":      "sector_research",
        }
        filter_doc_type = doc_type_map.get(analysis_type, "")

        # Primary search: filter by ticker + doc_type
        docs = vs.search(
            query=query,
            top_k=4,
            filter_ticker=ticker,
            filter_doc_type=filter_doc_type,
        )

        # Secondary search: global (no ticker filter) if primary returned < 2 results
        if len(docs) < 2:
            global_docs = vs.search(
                query=query,
                top_k=4,
                filter_doc_type=filter_doc_type,
            )
            # Merge, deduplicate by source
            seen_sources = {d["source"] for d in docs}
            for d in global_docs:
                if d["source"] not in seen_sources:
                    docs.append(d)
                    seen_sources.add(d["source"])

        self.log_action("documents_retrieved", {
            "count":           len(docs),
            "avg_relevance":   round(sum(d.get("relevance_score", 0) for d in docs) /
                                     len(docs), 3) if docs else 0,
        })

        return docs[:4]   # cap at 4 to keep prompts concise

    def _create_augmented_prompt(
        self,
        query: str,
        ticker: str,
        retrieved_docs: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """Build a prompt that injects the retrieved documents as grounding context."""

        if retrieved_docs:
            docs_text = "\n\n".join([
                f"[Source: {d['source']} | Relevance: {d.get('relevance_score', 0):.2f}]\n"
                f"{d['content']}"
                for d in retrieved_docs
            ])
            retrieval_block = f"""
You have access to the following documents retrieved from the financial knowledge base:

--- RETRIEVED KNOWLEDGE ---
{docs_text}
--- END RETRIEVED KNOWLEDGE ---

Use this retrieved knowledge to ground your analysis:
- Cite sources when you use retrieved information (e.g. "[Source: TCS Analysis 2025]")
- If retrieved data conflicts with current market data, note the discrepancy
- Do not fabricate data that was not in the retrieved documents or current context
"""
        else:
            retrieval_block = (
                "\nNote: No matching documents were retrieved from the knowledge base. "
                "Base your analysis on the current data provided and your training knowledge.\n"
            )

        return f"""{self.get_system_prompt()}
{retrieval_block}
User Query: {query}
Ticker: {ticker or 'N/A'}
Additional Context: {json.dumps(context.get('additional_data', {}), indent=2, default=str)}

Provide a thorough analysis that:
1. Integrates retrieved knowledge with current data
2. Cites sources for retrieved facts
3. Flags any conflicts between past analyses and current market data
4. Gives clear, actionable insights
"""
