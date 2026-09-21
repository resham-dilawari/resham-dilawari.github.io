"""
recommendation_logger.py — Parses agent responses for investment recommendations
and writes them to a persistent markdown file.

One file per session: recommendations/{session_id}.md
The file is created on first recommendation and appended on every subsequent one.

The agent is instructed (via system prompt) to embed blocks like:

    [RECOMMENDATION]
    TICKER: TCS.NS
    ACTION: BUY
    CONVICTION: HIGH
    PRICE_NOTED: ₹3,850
    RATIONALE: Strong earnings growth, low debt, GenAI tailwinds...
    TARGET: ₹4,200 (6-month)
    RISK: USD/INR headwind, US tech spending slowdown
    [/RECOMMENDATION]

This module finds those blocks, strips them from the display text,
and appends a formatted entry to the session's log file.
"""
import os
import re
from datetime import datetime
from typing import List, Dict, Tuple

# ── Action → visual indicator ─────────────────────────────────────────────────
ACTION_EMOJI = {
    "BUY":        "🟢",
    "INVEST":     "🟢",
    "ACCUMULATE": "🟢",
    "HOLD":       "🟡",
    "REDUCE":     "🟠",
    "SELL":       "🔴",
    "DIVEST":     "🔴",
    "AVOID":      "⚫",
}

# Regex to extract [RECOMMENDATION]...[/RECOMMENDATION] blocks (case-insensitive)
_REC_PATTERN = re.compile(
    r"\[RECOMMENDATION\](.*?)\[/RECOMMENDATION\]",
    re.DOTALL | re.IGNORECASE,
)


class RecommendationLogger:
    """
    Parses and logs investment recommendations from agent responses.

    Usage:
        logger = RecommendationLogger("rahul", "Rahul", config)
        clean_text, recs = logger.process(response_text)
        # clean_text has [RECOMMENDATION] blocks removed — safe to display
        # recs is a list of parsed recommendation dicts
    """

    def __init__(
        self,
        chat_id: str,
        user_id: str,
        user_name: str,
        config: dict,
        output_dir: str = "recommendations",
    ):
        self.chat_id     = chat_id
        self.user_id     = user_id
        self.user_name   = user_name
        self.config      = config
        self.output_dir  = output_dir
        self.file_path   = os.path.join(output_dir, f"{user_id}_{chat_id}.md")
        self._rec_count  = 0          
        self._turn_count = 0          
        self._file_ready = False      

        os.makedirs(output_dir, exist_ok=True)

        if os.path.exists(self.file_path):
            with open(self.file_path, encoding="utf-8") as f:
                content = f.read()
            self._rec_count  = content.count("### ")
            self._turn_count = content.count("## ⏰")
            self._file_ready = True

    # ── Public API ────────────────────────────────────────────────────────────

    def process(self, response_text: str) -> Tuple[str, List[Dict]]:
        """
        Extract [RECOMMENDATION] blocks from the agent response.
        Saves them to DB and to the markdown file.
        """
        recs       = self._parse_blocks(response_text)
        clean_text = _REC_PATTERN.sub("", response_text).strip()

        if recs:
            self._turn_count += 1
            self._append_to_file(recs)
            self._save_to_db(recs)
            self._rec_count += len(recs)

        return clean_text, recs

    def _save_to_db(self, recs: List[Dict]):
        from memory_store import MemoryStore
        from datetime import datetime, timedelta
        mem = MemoryStore()
        for rec in recs:
            # simple attempt to parse target date
            target = str(rec.get("TARGET", "")).lower()
            parsed_date = None
            if "month" in target:
                nums = [int(s) for s in target.split() if s.isdigit()]
                m = nums[0] if nums else 6
                parsed_date = (datetime.now() + timedelta(days=30*m)).isoformat()
            elif "year" in target:
                nums = [int(s) for s in target.split() if s.isdigit()]
                y = nums[0] if nums else 1
                parsed_date = (datetime.now() + timedelta(days=365*y)).isoformat()

            mem.save_recommendation(self.chat_id, self.user_id, rec, parsed_date)

    @property
    def recommendation_count(self) -> int:
        return self._rec_count

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse_blocks(self, text: str) -> List[Dict]:
        """Find and parse all [RECOMMENDATION]...[/RECOMMENDATION] blocks."""
        recs = []
        for block in _REC_PATTERN.findall(text):
            rec = {}
            for line in block.strip().splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    rec[key.strip().upper()] = value.strip()
            # Only keep blocks that have at least ACTION or TICKER
            if rec.get("ACTION") or rec.get("TICKER"):
                recs.append(rec)
        return recs

    # ── File writing ──────────────────────────────────────────────────────────

    def _append_to_file(self, recs: List[Dict]):
        if not self._file_ready:
            self._write_header()
            self._file_ready = True

        timestamp = datetime.now().strftime("%I:%M %p")

        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n\n## ⏰ {timestamp} — Turn {self._turn_count}\n\n")
            for rec in recs:
                f.write(self._format_rec(rec))

    def _write_header(self):
        tickers = ", ".join(self.config.get("tickers", [])) or "—"
        corpus  = self.config.get("corpus", 0)
        date    = datetime.now().strftime("%d %B %Y")

        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write(
                f"# 📊 Portfolio Advisor — Recommendations Log\n\n"
                f"| Field | Value |\n"
                f"|-------|-------|\n"
                f"| **User** | {self.user_name} |\n"
                f"| **Chat ID** | `{self.chat_id}` |\n"
                f"| **Started** | {date} |\n"
                f"| **Holdings** | {tickers} |\n"
                f"| **Corpus** | ₹{corpus:,.0f} |\n\n"
                f"> ⚠️ Auto-generated by AI. For educational purposes only — "
                f"not professional financial advice.\n"
            )

    @staticmethod
    def _format_rec(rec: dict) -> str:
        ticker     = rec.get("TICKER", "N/A")
        action     = rec.get("ACTION", "N/A").upper()
        conviction = rec.get("CONVICTION", "")
        price      = rec.get("PRICE_NOTED", "")
        rationale  = rec.get("RATIONALE", "")
        target     = rec.get("TARGET", "")
        risk       = rec.get("RISK", "")
        emoji      = ACTION_EMOJI.get(action, "📌")

        parts = [f"### {emoji} {action} — `{ticker}`\n\n"]

        meta_parts = []
        if conviction:
            meta_parts.append(f"**Conviction:** {conviction}")
        if price:
            meta_parts.append(f"**Price Noted:** {price}")
        if meta_parts:
            parts.append(" &nbsp;|&nbsp; ".join(meta_parts) + "  \n\n")

        if rationale:
            parts.append(f"**Rationale:**  \n{rationale}  \n\n")
        if target:
            parts.append(f"**Target:** {target}  \n")
        if risk:
            parts.append(f"**Key Risks:** {risk}  \n")

        parts.append("\n")
        return "".join(parts)
