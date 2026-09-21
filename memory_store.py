"""
memory_store.py — SQLite-backed persistent memory for the Portfolio Advisor.

Stores three types of data across sessions:
  - sessions   : user profile, portfolio config, persona, timestamps
  - messages   : full chat history (role, content, tool_steps)
  - user_facts : extracted preferences and observed behaviours

The DB file (memory_store.db) is created automatically on first use.
Uses the Python standard-library sqlite3 — zero new dependencies.
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional


class MemoryStore:
    """
    Thread-safe SQLite memory store.

    Quick start:
        mem = MemoryStore()                              # creates DB if needed
        mem.save_session("rahul", "Rahul", ["TCS.NS"], 50000, "conservative", "mid_career_mohit")
        mem.append_message("rahul", "user", "What is TCS P/E?", [])
        mem.append_message("rahul", "assistant", "TCS P/E is 28x...", ["Fetched financial ratios"])
        prev = mem.load_session("rahul")                 # → dict or None
        hist = mem.get_history("rahul", last_n=10)       # → list of message dicts
    """

    _DDL = """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id  TEXT PRIMARY KEY,
        user_name   TEXT NOT NULL,
        tickers     TEXT,           -- JSON array e.g. '["TCS.NS","INFY.NS"]'
        corpus      REAL,
        preferences TEXT,
        persona     TEXT,
        created_at  TEXT,
        last_seen   TEXT
    );

    CREATE TABLE IF NOT EXISTS messages (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  TEXT    NOT NULL,
        role        TEXT    NOT NULL,   -- 'user' | 'assistant'
        content     TEXT,
        tool_steps  TEXT,               -- JSON array of label strings
        created_at  TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );

    CREATE TABLE IF NOT EXISTS user_facts (
        session_id  TEXT NOT NULL,
        fact_key    TEXT NOT NULL,
        fact_value  TEXT,
        updated_at  TEXT,
        PRIMARY KEY (session_id, fact_key),
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    );

    CREATE TABLE IF NOT EXISTS chat_sessions (
        chat_id     TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL,
        started_at  TEXT,
        tickers     TEXT,
        corpus      REAL,
        preferences TEXT,
        persona     TEXT,
        FOREIGN KEY (user_id) REFERENCES sessions(session_id)
    );

    CREATE TABLE IF NOT EXISTS recommendations (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id           TEXT NOT NULL,
        user_id           TEXT NOT NULL,
        ticker            TEXT,
        action            TEXT,
        conviction        TEXT,
        price_noted       REAL,
        rationale         TEXT,
        target            TEXT,
        target_date       TEXT,
        risk_note         TEXT,
        created_at        TEXT,
        last_checked_at   TEXT,
        current_price     REAL,
        price_change_pct  REAL,
        performance       TEXT,
        agent_analysis    TEXT,
        agent_analysed_at TEXT,
        FOREIGN KEY (chat_id) REFERENCES chat_sessions(chat_id),
        FOREIGN KEY (user_id) REFERENCES sessions(session_id)
    );

    CREATE TABLE IF NOT EXISTS rec_feedback (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        rec_id      INTEGER NOT NULL,
        user_id     TEXT NOT NULL,
        rating      TEXT, -- GOOD / BAD / PARTIAL
        note        TEXT,
        created_at  TEXT,
        FOREIGN KEY (rec_id) REFERENCES recommendations(id),
        FOREIGN KEY (user_id) REFERENCES sessions(session_id)
    );
    """

    def __init__(self, db_path: str = "memory_store.db"):
        self.db_path = db_path
        self._init_db()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # safe for concurrent reads
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(self._DDL)

    # ── Sessions ──────────────────────────────────────────────────────────────

    def save_session(
        self,
        session_id: str,
        user_name: str,
        tickers: List[str],
        corpus: float,
        preferences: str,
        persona: str,
    ):
        """
        Create or update a session record.
        On conflict (same session_id) updates all mutable fields and last_seen.
        """
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO sessions
                    (session_id, user_name, tickers, corpus, preferences, persona, created_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    tickers     = excluded.tickers,
                    corpus      = excluded.corpus,
                    preferences = excluded.preferences,
                    persona     = excluded.persona,
                    last_seen   = excluded.last_seen
                """,
                (
                    session_id,
                    user_name,
                    json.dumps(tickers),
                    corpus,
                    preferences,
                    persona,
                    now,
                    now,
                ),
            )

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return session as a dict (tickers already decoded from JSON), or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["tickers"] = json.loads(d.get("tickers") or "[]")
            return d

    def touch_session(self, session_id: str):
        """Refresh the last_seen timestamp without changing any other field."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET last_seen = ? WHERE session_id = ?",
                (datetime.now().isoformat(), session_id),
            )

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Return a summary of all sessions, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT session_id, user_name, persona, last_seen,
                       (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count
                FROM sessions s
                ORDER BY last_seen DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Messages ──────────────────────────────────────────────────────────────

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_steps: List[str] = None,
    ):
        """
        Append one message to the session's chat history.
        role must be 'user' or 'assistant'.
        """
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, tool_steps, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    role,
                    content,
                    json.dumps(tool_steps or []),
                    datetime.now().isoformat(),
                ),
            )

    def get_history(
        self,
        session_id: str,
        last_n: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Return the last N messages in chronological order (oldest first).
        Each dict: role, content, tool_steps (list), created_at (ISO string).
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT role, content, tool_steps, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, last_n),
            ).fetchall()
        # Reverse so oldest message is first
        return [
            {
                "role":       r["role"],
                "content":    r["content"],
                "tool_steps": json.loads(r["tool_steps"] or "[]"),
                "created_at": r["created_at"],
            }
            for r in reversed(rows)
        ]

    def message_count(self, session_id: str) -> int:
        """Return total number of messages stored for a session."""
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]

    # ── User Facts ────────────────────────────────────────────────────────────

    def upsert_fact(self, session_id: str, key: str, value: str):
        """
        Store or update a structured user fact.

        Examples:
            upsert_fact(sid, "preferred_sectors", "IT, Pharma")
            upsert_fact(sid, "risk_tolerance_observed", "conservative")
            upsert_fact(sid, "recurring_concern", "inflation impact on tech stocks")
        """
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO user_facts (session_id, fact_key, fact_value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, fact_key) DO UPDATE SET
                    fact_value = excluded.fact_value,
                    updated_at = excluded.updated_at
                """,
                (session_id, key, value, datetime.now().isoformat()),
            )

    def get_user_facts(self, session_id: str) -> Dict[str, str]:
        """Return all stored facts for a session as {key: value}."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT fact_key, fact_value FROM user_facts WHERE session_id = ?",
                (session_id,),
            ).fetchall()
            return {r["fact_key"]: r["fact_value"] for r in rows}

    # ── Chat Sessions & Recommendations ───────────────────────────────────────

    def create_chat_session(self, chat_id: str, user_id: str, tickers: List[str], corpus: float, preferences: str, persona: str):
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (chat_id, user_id, started_at, tickers, corpus, preferences, persona)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, datetime.now().isoformat(), json.dumps(tickers), corpus, preferences, persona)
            )

    def save_recommendation(self, chat_id: str, user_id: str, rec: dict, parsed_target_date: str = None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO recommendations (
                    chat_id, user_id, ticker, action, conviction, price_noted, rationale, target, target_date, risk_note, created_at, performance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
                """,
                (
                    chat_id, user_id, rec.get("TICKER"), rec.get("ACTION"), rec.get("CONVICTION"),
                    self._parse_price(rec.get("PRICE_NOTED")), rec.get("RATIONALE"), rec.get("TARGET"),
                    parsed_target_date, rec.get("RISK"), datetime.now().isoformat()
                )
            )
            return cur.lastrowid

    def _parse_price(self, price_str) -> float:
        if not price_str:
            return 0.0
        try:
            return float(str(price_str).replace("₹", "").replace(",", "").strip())
        except ValueError:
            return 0.0

    def get_open_recommendations(self) -> List[Dict]:
        """Fetch all recommendations that need performance updates (not EXPIRED)."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM recommendations WHERE performance != 'EXPIRED'").fetchall()
            return [dict(r) for r in rows]

    def update_recommendation_performance(self, rec_id: int, current_price: float, price_change_pct: float, performance: str):
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE recommendations 
                SET current_price = ?, price_change_pct = ?, performance = ?, last_checked_at = ?
                WHERE id = ?
                """,
                (current_price, price_change_pct, performance, datetime.now().isoformat(), rec_id)
            )

    def update_recommendation_analysis(self, rec_id: int, agent_analysis: str):
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE recommendations 
                SET agent_analysis = ?, agent_analysed_at = ?
                WHERE id = ?
                """,
                (agent_analysis, datetime.now().isoformat(), rec_id)
            )

    def add_feedback(self, rec_id: int, user_id: str, rating: str, note: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO rec_feedback (rec_id, user_id, rating, note, created_at) VALUES (?, ?, ?, ?, ?)",
                (rec_id, user_id, rating, note, datetime.now().isoformat())
            )

    def get_user_chat_sessions(self, user_id: str) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY started_at DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_chat_recommendations(self, chat_id: str) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT r.*, 
                       (SELECT rating FROM rec_feedback f WHERE f.rec_id = r.id ORDER BY created_at DESC LIMIT 1) as latest_feedback
                FROM recommendations r 
                WHERE chat_id = ? ORDER BY created_at ASC
                """, (chat_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_user_track_record(self, user_id: str) -> Dict[str, Any]:
        with self._conn() as conn:
            rows = conn.execute("SELECT performance, COUNT(*) as cnt FROM recommendations WHERE user_id = ? GROUP BY performance", (user_id,)).fetchall()
            stats = {"WINNING": 0, "LOSING": 0, "NEUTRAL": 0, "PENDING": 0, "EXPIRED": 0}
            total_resolved = 0
            for r in rows:
                p = r["performance"]
                c = r["cnt"]
                if p in stats:
                    stats[p] = c
                if p in ["WINNING", "LOSING", "NEUTRAL"]:
                    total_resolved += c
            
            accuracy = 0
            if total_resolved > 0:
                accuracy = round((stats["WINNING"] / total_resolved) * 100)
            
            return {
                "stats": stats,
                "total_resolved": total_resolved,
                "accuracy": accuracy
            }
