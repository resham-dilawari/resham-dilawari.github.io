"""
tools.py — Gemini-callable tool definitions for the Portfolio Advisor Agent.

Each function is a real Python implementation AND declared as a Gemini
FunctionDeclaration so the model can call them autonomously during its
ReAct reasoning loop.

Tools:
  1. get_stock_price         — live price, change %
  2. get_stock_info          — company name, sector, summary
  3. get_recent_news         — latest 5 headlines
  4. get_financial_ratios    — P/E, EPS, market cap, 52-wk range, beta, ROE
  5. compare_stocks          — side-by-side price snapshot
  6. search_knowledge_base   — semantic search over internal ChromaDB corpus
"""
import yfinance as yf
from google.genai import types
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Tool Implementations
# ══════════════════════════════════════════════════════════════════════════════

def get_stock_price(ticker: str) -> dict:
    """Fetch live price, previous close, and % change for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        fi = stock.fast_info
        last = fi.last_price
        prev = fi.previous_close
        change = last - prev
        pct = (change / prev) * 100 if prev else 0
        return {
            "ticker":          ticker,
            "current_price":   round(last, 2),
            "previous_close":  round(prev, 2),
            "change":          round(change, 2),
            "change_pct":      round(pct, 2),
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def get_stock_info(ticker: str) -> dict:
    """Fetch company name, sector, industry and business summary."""
    try:
        info = yf.Ticker(ticker).info
        return {
            "ticker":   ticker,
            "name":     info.get("longName", "N/A"),
            "sector":   info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "summary":  (info.get("longBusinessSummary") or info.get("description", "N/A"))[:800],
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def get_recent_news(ticker: str) -> dict:
    """Fetch up to 5 recent news headlines for a ticker."""
    try:
        items = yf.Ticker(ticker).news or []
        headlines = [
            {"title": n.get("title", ""), "publisher": n.get("publisher", "")}
            for n in items[:5]
        ]
        return {"ticker": ticker, "headlines": headlines}
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def get_financial_ratios(ticker: str) -> dict:
    """Fetch key valuation and financial ratios."""
    try:
        info = yf.Ticker(ticker).info
        return {
            "ticker":              ticker,
            "pe_ratio":            info.get("trailingPE"),
            "forward_pe":          info.get("forwardPE"),
            "eps":                 info.get("trailingEps"),
            "market_cap":          info.get("marketCap"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low":  info.get("fiftyTwoWeekLow"),
            "dividend_yield":      info.get("dividendYield"),
            "beta":                info.get("beta"),
            "return_on_equity":    info.get("returnOnEquity"),
            "debt_to_equity":      info.get("debtToEquity"),
            "profit_margin":       info.get("profitMargins"),
            "revenue_growth":      info.get("revenueGrowth"),
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def compare_stocks(tickers: list[str]) -> dict:
    """Side-by-side price snapshot for a list of tickers."""
    results = {t: get_stock_price(t) for t in tickers}
    return {"comparison": results}


# ── Tool 6: Semantic Knowledge Base Search ────────────────────────────────────

_vector_store = None   # module-level singleton, lazy-initialised


def _get_vector_store():
    """Lazy-initialise VectorStore + seed once from knowledge_base.json."""
    global _vector_store
    if _vector_store is not None:
        return _vector_store
    try:
        from vector_store import VectorStore
        _vector_store = VectorStore(db_path="chroma_db")
        _vector_store.seed_from_knowledge_base("simple_rag_db/knowledge_base.json")
    except ImportError:
        logger.warning("search_knowledge_base: chromadb not installed. Tool disabled.")
        _vector_store = None
    except Exception as e:
        logger.error(f"search_knowledge_base: VectorStore init failed — {e}")
        _vector_store = None
    return _vector_store


def search_knowledge_base(query: str, ticker: str = "", doc_type: str = "") -> dict:
    """
    Search the internal financial knowledge base using semantic similarity.

    Returns the most relevant documents from historical analyses,
    tax rules, risk frameworks, and sector research.
    """
    vs = _get_vector_store()
    if vs is None:
        return {
            "error": "Knowledge base unavailable. Install chromadb: pip install chromadb",
            "query": query,
        }
    try:
        results = vs.search(query=query, top_k=3,
                             filter_ticker=ticker, filter_doc_type=doc_type)
        return {
            "query":            query,
            "results":          results,
            "count":            len(results),
            "total_documents":  vs.document_count(),
        }
    except Exception as e:
        return {"error": str(e), "query": query}


# ══════════════════════════════════════════════════════════════════════════════
# Gemini FunctionDeclaration Schema
# ══════════════════════════════════════════════════════════════════════════════

TOOL_DECLARATIONS = types.Tool(
    function_declarations=[

        types.FunctionDeclaration(
            name="get_stock_price",
            description=(
                "Get the current live price, previous close, and percentage change "
                "for a stock ticker (e.g. RELIANCE.NS, TCS.NS, INFY.BO). "
                "Always call this before making any price-based statements."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ticker": types.Schema(
                        type=types.Type.STRING,
                        description="Stock ticker symbol with exchange suffix (.NS for NSE, .BO for BSE)",
                    )
                },
                required=["ticker"],
            ),
        ),

        types.FunctionDeclaration(
            name="get_stock_info",
            description="Get the company name, sector, industry, and business description for a stock ticker.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ticker": types.Schema(
                        type=types.Type.STRING,
                        description="Stock ticker symbol with exchange suffix",
                    )
                },
                required=["ticker"],
            ),
        ),

        types.FunctionDeclaration(
            name="get_recent_news",
            description="Get the 5 most recent news headlines for a stock ticker to assess market sentiment and recent events.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ticker": types.Schema(
                        type=types.Type.STRING,
                        description="Stock ticker symbol with exchange suffix",
                    )
                },
                required=["ticker"],
            ),
        ),

        types.FunctionDeclaration(
            name="get_financial_ratios",
            description=(
                "Get key financial ratios for a ticker: P/E, forward P/E, EPS, market cap, "
                "52-week range, dividend yield, beta, ROE, debt-to-equity, profit margin, revenue growth."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ticker": types.Schema(
                        type=types.Type.STRING,
                        description="Stock ticker symbol with exchange suffix",
                    )
                },
                required=["ticker"],
            ),
        ),

        types.FunctionDeclaration(
            name="compare_stocks",
            description="Get a side-by-side live price comparison for multiple stock tickers at once.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "tickers": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="List of ticker symbols to compare (include exchange suffix)",
                    )
                },
                required=["tickers"],
            ),
        ),

        types.FunctionDeclaration(
            name="search_knowledge_base",
            description=(
                "Search the internal financial knowledge base for relevant past analyses, "
                "tax rules, risk frameworks, and sector research using semantic similarity. "
                "Call this when you need historical context, past recommendations for a stock, "
                "Indian tax rules on capital gains, or portfolio risk guidelines."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Natural language search query (e.g. 'TCS valuation history', 'LTCG tax rules India')",
                    ),
                    "ticker": types.Schema(
                        type=types.Type.STRING,
                        description="Optional: filter results to a specific stock ticker (e.g. 'TCS.NS')",
                    ),
                    "doc_type": types.Schema(
                        type=types.Type.STRING,
                        description=(
                            "Optional: filter by document type. One of: "
                            "'stock_analysis', 'tax_rule', 'risk_framework', 'sector_research'"
                        ),
                    ),
                },
                required=["query"],
            ),
        ),

    ]
)


# ── Dispatcher: maps function name → Python callable ──────────────────────────

TOOL_FUNCTIONS = {
    "get_stock_price":       get_stock_price,
    "get_stock_info":        get_stock_info,
    "get_recent_news":       get_recent_news,
    "get_financial_ratios":  get_financial_ratios,
    "compare_stocks":        compare_stocks,
    "search_knowledge_base": search_knowledge_base,
}
