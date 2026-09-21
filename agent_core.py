"""
agent_core.py — Agentic loop for the Portfolio Advisor.

Uses Gemini's function-calling API in a ReAct loop:
  Reason → call tool(s) → observe results → repeat → final answer

Now enhanced with:
  - Persistent memory: injects last N messages from MemoryStore into system prompt
  - Persona adaptation: adapts communication style based on portfolio size
  - User name awareness: addresses the user by name
  - Recommendation logging: embeds structured [RECOMMENDATION] blocks that are
    automatically extracted and written to recommendations/{session_id}.md
"""
import os
import logging
from typing import Generator, Optional
from google import genai
from google.genai import types
from tools import TOOL_DECLARATIONS, TOOL_FUNCTIONS

logger = logging.getLogger(__name__)


BASE_SYSTEM_PROMPT = """You are an expert AI financial advisor specializing in the Indian stock market (NSE/BSE).

You have access to real-time tools to fetch stock prices, company info, news, financial ratios,
and a semantic knowledge base of past analyses, tax rules, and risk frameworks.

Tool usage guidelines:
- Always fetch live data before making any price-based statements
- Call search_knowledge_base when you need historical context, past analyses of a stock,
  Indian capital gains tax rules, or portfolio risk guidelines
- When comparing stocks, use compare_stocks for efficiency
- Use get_recent_news to assess sentiment before making recommendations

Response guidelines:
- Clearly flag risks alongside any recommendation
- Use bullet points and markdown headings for clarity
- Be concise but thorough — don't pad with unnecessary caveats
- End every response with:
  "⚠️ This is AI-generated analysis for educational purposes only — not professional financial advice."
"""

# Appended to the system prompt — instructs the model to embed parseable
# recommendation blocks that RecommendationLogger will extract automatically.
RECOMMENDATION_FORMAT = """

## Recommendation Logging Protocol

Whenever you make an actionable investment recommendation (BUY, SELL, HOLD, INVEST,
DIVEST, ACCUMULATE, REDUCE, or AVOID) for any specific stock or asset, you MUST embed
a structured block in your response using EXACTLY this format:

[RECOMMENDATION]
TICKER: <ticker symbol, e.g. TCS.NS>
ACTION: <BUY | SELL | HOLD | INVEST | DIVEST | ACCUMULATE | REDUCE | AVOID>
CONVICTION: <HIGH | MEDIUM | LOW>
PRICE_NOTED: <current price from live data, e.g. ₹3,850>
RATIONALE: <1-3 sentences explaining the recommendation>
TARGET: <price target or time horizon, or N/A>
RISK: <key risks in one sentence>
[/RECOMMENDATION]

Rules:
- Include one block per stock recommended in the same response.
- Always fetch live price with get_stock_price BEFORE noting PRICE_NOTED.
- The block will be automatically extracted and saved to a file — the user will NOT
  see the raw tags. You may still explain the recommendation in natural language
  outside the block; the block is purely for structured logging.
- Only emit a block for ACTIONABLE recommendations — not for general commentary.
"""



def _build_system_prompt(
    user_name: Optional[str],
    persona_prompt: Optional[str],
    history_text: Optional[str],
    track_record_text: Optional[str] = None,
) -> str:
    """Assemble the full system prompt from base + persona + memory."""
    parts = [BASE_SYSTEM_PROMPT]

    if user_name:
        parts.append(
            f"\nThe user's name is {user_name}. Address them by first name occasionally "
            f"to make the conversation personal, but don't overdo it."
        )

    if track_record_text:
        parts.append(
            f"\n\n## Your Track Record with this User\n"
            f"Before you make any new recommendations, review your performance:\n"
            f"{track_record_text}\n"
            f"Use this self-analysis to calibrate your future recommendations. Be humble if your previous calls were incorrect."
        )

    if persona_prompt:
        parts.append(persona_prompt)

    if history_text:
        parts.append(
            f"\n\n## Previous Session Context\n"
            f"You have spoken with this user before. Use this history to provide continuity "
            f"— refer back to past topics when relevant, and avoid re-asking things they've "
            f"already told you.\n\n"
            f"{history_text}"
        )

    # Always append recommendation format instructions last so they're fresh in context
    parts.append(RECOMMENDATION_FORMAT)

    return "\n".join(parts)


def _format_history(history: list) -> str:
    """Format last-N messages into a compact readable string for the system prompt."""
    if not history:
        return ""
    lines = []
    for msg in history:
        role = "User" if msg["role"] == "user" else "Advisor"
        content = msg["content"]
        if len(content) > 400:
            content = content[:400] + "…"
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines)


def _detect_persona(corpus: float) -> tuple[str, str]:
    """
    Heuristic persona detection based on investable corpus.
    Returns (persona_key, persona_prompt).
    """
    try:
        from persona_detector import PersonaDetector
        detector = PersonaDetector()
        persona_key = detector.detect_persona(portfolio_size=corpus)
        persona_prompt = detector.get_response_adaptation_prompt(persona_key)
        return persona_key, persona_prompt
    except Exception as e:
        logger.warning(f"Persona detection failed: {e}")
        return "mid_career_mohit", ""


class AdvisorAgent:
    """
    Agentic advisor with a persistent chat session and tool-use loop.
    Now with persistent memory injection and persona-adaptive responses.
    """

    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set.")
        self.client = genai.Client(api_key=api_key)
        self.chat = None
        self.config = {}
        self.session_id: Optional[str] = None
        self.user_name:  Optional[str] = None
        self.persona_key: Optional[str] = None

    def initialize(
        self,
        tickers: list[str],
        corpus: float,
        preferences: str,
        session_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> Generator:
        """
        Start a new chat session pre-loaded with portfolio config, memory, and persona.
        Returns the agent's opening analysis as a streamed generator.
        """
        self.config     = {"tickers": tickers, "corpus": corpus, "preferences": preferences}
        self.session_id = session_id
        self.user_name  = user_name

        # ── Persona ───────────────────────────────────────────────────────────
        self.persona_key, persona_prompt = _detect_persona(corpus)

        # ── Memory: load previous session history ─────────────────────────────
        history_text = ""
        track_record_text = ""
        if session_id:
            try:
                from memory_store import MemoryStore
                mem = MemoryStore()
                
                # Fetch chat history
                history = mem.get_history(session_id, last_n=12)
                history_text = _format_history(history)
                
                # Fetch track record and self-analyses
                track_stats = mem.get_user_track_record(session_id)
                open_recs = mem.get_open_recommendations()
                # filter to this user
                user_open_recs = [r for r in open_recs if r["user_id"] == session_id and r.get("agent_analysis")]
                
                if track_stats["total_resolved"] > 0 or user_open_recs:
                    lines = [f"Overall Accuracy: {track_stats['accuracy']}% ({track_stats['stats']['WINNING']} WINNING, {track_stats['stats']['LOSING']} LOSING, {track_stats['stats']['NEUTRAL']} NEUTRAL)."]
                    if user_open_recs:
                        lines.append("\nRecent active recommendations and your self-analysis:")
                        # Take up to 3 most recent
                        user_open_recs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                        for r in user_open_recs[:3]:
                            lines.append(f"- {r['action']} {r['ticker']} @ {r['price_noted']} (Now {r['current_price']}, {r['performance']}): {r['agent_analysis']}")
                    track_record_text = "\n".join(lines)
            except Exception as e:
                logger.warning(f"Could not load memory/track record for session '{session_id}': {e}")

        # ── Build full system prompt ───────────────────────────────────────────
        system_prompt = _build_system_prompt(user_name, persona_prompt, history_text, track_record_text)

        # ── Create chat session ────────────────────────────────────────────────
        self.chat = self.client.chats.create(
            model="gemini-3.6-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[TOOL_DECLARATIONS],
                temperature=0.7,
            ),
        )

        # ── Opening message ────────────────────────────────────────────────────
        tickers_str = ", ".join(tickers) if tickers else "None"
        is_returning = bool(history_text)

        if is_returning:
            opening = (
                f"Welcome back{', ' + user_name if user_name else ''}! "
                f"Portfolio config:\n"
                f"- Holdings: {tickers_str}\n"
                f"- Corpus: ₹{corpus:,.2f}\n"
                f"- Preferences: {preferences}\n\n"
                f"The user is returning — briefly acknowledge the continuity from last session "
                f"(referencing specific topics if available in the previous session context), "
                f"then fetch live data for their holdings and give a fresh portfolio snapshot."
            )
        else:
            opening = (
                f"New user configuration:\n"
                f"- Holdings: {tickers_str}\n"
                f"- Corpus: ₹{corpus:,.2f}\n"
                f"- Preferences: {preferences}\n\n"
                f"Greet the user warmly, briefly acknowledge their config, "
                f"then immediately fetch live data for their holdings and give a "
                f"concise portfolio snapshot to kick off the conversation."
            )

        return self._run_loop(opening)

    def chat_turn(self, user_message: str) -> Generator:
        """
        Send a user message and run the agentic loop, yielding
        ('TOOL', fn_name, fn_args) events and a final ('TEXT', text) event.
        """
        if self.chat is None:
            yield ("TEXT", "⚠️ Please configure your portfolio first.")
            return
        yield from self._run_loop(user_message)

    # ── Core ReAct loop ───────────────────────────────────────────────────────

    def _run_loop(self, message: str) -> Generator:
        """
        Reason → Tool call(s) → Observe → Repeat → Final text.
        Yields:
            ("TOOL", fn_name, fn_args)  — for each tool call
            ("TEXT", text)              — final assistant response
        """
        current_message = message

        while True:
            response  = self.chat.send_message(current_message)
            candidate = response.candidates[0]
            parts     = candidate.content.parts

            function_calls = [p for p in parts if p.function_call]

            if not function_calls:
                text = "".join(p.text for p in parts if p.text)
                yield ("TEXT", text)
                return

            tool_results = []
            for part in function_calls:
                fc      = part.function_call
                fn_name = fc.name
                fn_args = dict(fc.args)

                yield ("TOOL", fn_name, fn_args)

                fn = TOOL_FUNCTIONS.get(fn_name)
                try:
                    result = fn(**fn_args) if fn else {"error": f"Unknown tool: {fn_name}"}
                except Exception as e:
                    result = {"error": str(e)}

                tool_results.append(
                    types.Part.from_function_response(
                        name=fn_name,
                        response=result,
                    )
                )

            current_message = tool_results
