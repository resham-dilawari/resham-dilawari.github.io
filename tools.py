"""
tools.py — Gemini-callable tool definitions for the Portfolio Advisor Agent.
Each function is a real Python function AND declared as a Gemini FunctionDeclaration
so the model can call them autonomously during its reasoning loop.
"""
import yfinance as yf
from google.genai import types

# ── Python implementations (called when the model invokes a tool) ─────────────

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
            "ticker": ticker,
            "current_price": round(last, 2),
            "previous_close": round(prev, 2),
            "change": round(change, 2),
            "change_pct": round(pct, 2),
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def get_stock_info(ticker: str) -> dict:
    """Fetch company name, sector, industry and business summary."""
    try:
        info = yf.Ticker(ticker).info
        return {
            "ticker": ticker,
            "name": info.get("longName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "summary": (info.get("longBusinessSummary") or info.get("description", "N/A"))[:800],
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
    """Fetch key valuation and financial ratios: P/E, EPS, market cap, 52-week range, dividend yield."""
    try:
        info = yf.Ticker(ticker).info
        return {
            "ticker": ticker,
            "pe_ratio": info.get("trailingPE"),
            "eps": info.get("trailingEps"),
            "market_cap": info.get("marketCap"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "return_on_equity": info.get("returnOnEquity"),
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


def compare_stocks(tickers: list[str]) -> dict:
    """Side-by-side price snapshot for a list of tickers."""
    results = {}
    for t in tickers:
        results[t] = get_stock_price(t)
    return {"comparison": results}


# ── Gemini FunctionDeclaration schema ─────────────────────────────────────────

TOOL_DECLARATIONS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_stock_price",
            description="Get the current live price, previous close, and percentage change for a stock ticker (e.g. RELIANCE.NS, TCS.NS, INFY.BO).",
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
            description="Get the 5 most recent news headlines for a stock ticker to assess market sentiment.",
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
            description="Get key financial ratios for a ticker: P/E ratio, EPS, market cap, 52-week range, dividend yield, beta, and return on equity.",
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
            description="Get a side-by-side price comparison for multiple stock tickers at once.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "tickers": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="List of ticker symbols to compare",
                    )
                },
                required=["tickers"],
            ),
        ),
    ]
)

# ── Dispatcher: maps function name → Python callable ──────────────────────────

TOOL_FUNCTIONS = {
    "get_stock_price": get_stock_price,
    "get_stock_info": get_stock_info,
    "get_recent_news": get_recent_news,
    "get_financial_ratios": get_financial_ratios,
    "compare_stocks": compare_stocks,
}
