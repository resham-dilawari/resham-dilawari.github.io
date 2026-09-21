"""
performance_tracker.py — Automatically tracks recommendation performance
and generates self-analysis using Gemini.
"""
import logging
from datetime import datetime
import yfinance as yf
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def update_all_open_recommendations():
    """
    Fetches open recommendations, updates prices, and runs self-analysis.
    Intended to be called on app startup or before a new chat starts.
    """
    from memory_store import MemoryStore
    mem = MemoryStore()
    recs = mem.get_open_recommendations()
    if not recs:
        return

    # 1. Fetch live prices
    tickers = list(set([r["ticker"] for r in recs if r.get("ticker")]))
    prices = {}
    if tickers:
        try:
            # Batch fetch to save time
            data = yf.download(tickers, period="1d", progress=False)
            close_data = data['Close']
            
            # yfinance returns a DataFrame with MultiIndex if multiple tickers (or recent versions even for 1 in a list)
            # If it's a Series (older yfinance with 1 ticker), convert to frame
            import pandas as pd
            if isinstance(close_data, pd.Series):
                close_data = close_data.to_frame()
                
            last_row = close_data.iloc[-1]
            for t in tickers:
                try:
                    val = last_row[t]
                    if pd.notna(val):
                        prices[t] = float(val)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to fetch live prices: {e}")

    # 2. Evaluate performance and update
    for rec in recs:
        ticker = rec.get("ticker")
        if not ticker or ticker not in prices:
            continue
        
        current_price = prices[ticker]
        noted_price = rec.get("price_noted") or 0.0
        if noted_price == 0:
            continue
            
        change_pct = ((current_price - noted_price) / noted_price) * 100
        action = str(rec.get("action")).upper()
        
        # Determine performance status
        perf = "NEUTRAL"
        if action in ["BUY", "INVEST", "ACCUMULATE"]:
            if change_pct > 2.0: perf = "WINNING"
            elif change_pct < -2.0: perf = "LOSING"
        elif action in ["SELL", "DIVEST", "REDUCE", "AVOID"]:
            if change_pct < -2.0: perf = "WINNING"
            elif change_pct > 2.0: perf = "LOSING"
            
        # Check if EXPIRED (older than 90 days if no target date, or past target date)
        created_at = datetime.fromisoformat(rec["created_at"])
        target_date_str = rec.get("target_date")
        if target_date_str:
            target_date = datetime.fromisoformat(target_date_str)
            if datetime.now() > target_date:
                perf = "EXPIRED"
        else:
            if (datetime.now() - created_at).days > 90:
                perf = "EXPIRED"

        # Update DB with price & performance
        mem.update_recommendation_performance(rec["id"], current_price, change_pct, perf)
        
        # 3. Generate Agent Self-Analysis if needed
        # Condition: never analysed OR > 6 hours since last analysis
        needs_analysis = False
        last_analysed = rec.get("agent_analysed_at")
        if not last_analysed:
            needs_analysis = True
        else:
            hours_since = (datetime.now() - datetime.fromisoformat(last_analysed)).total_seconds() / 3600
            if hours_since > 6:
                needs_analysis = True
                
        if needs_analysis and os.environ.get("GEMINI_API_KEY"):
            try:
                analysis = _generate_self_analysis(rec, current_price, change_pct, perf)
                mem.update_recommendation_analysis(rec["id"], analysis)
            except Exception as e:
                logger.error(f"Self analysis failed for rec {rec['id']}: {e}")

def _generate_self_analysis(rec: dict, current_price: float, change_pct: float, perf: str) -> str:
    prompt = f"""
    You are an AI financial advisor evaluating your past recommendation.
    
    Past Recommendation:
    Ticker: {rec['ticker']}
    Action: {rec['action']}
    Conviction: {rec['conviction']}
    Price at the time: ₹{rec['price_noted']}
    Original Rationale: {rec['rationale']}
    
    Current State:
    Current Price: ₹{current_price:.2f}
    Price Change: {change_pct:+.2f}%
    Status: {perf}
    
    Provide a brief, honest self-critique (2-3 sentences max). 
    Did your rationale hold up? If it's LOSING, what might you have missed? If WINNING, what played out well?
    Be direct and humble.
    """
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.4)
    )
    return response.text.strip()
