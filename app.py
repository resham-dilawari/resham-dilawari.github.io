"""
app.py — AI Portfolio Advisor (Agentic)

Three-phase flow:
  Phase 1 — Name screen  : user enters their name; previous session loaded from SQLite
  Phase 2 — Config screen : form pre-filled from memory, persona shown
  Phase 3 — Chat screen   : conversational chat + sidebar memory panel
"""
import streamlit as st
from dotenv import load_dotenv
import os
import json

load_dotenv()

st.set_page_config(
    page_title="AI Portfolio Advisor",
    page_icon="📈",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.config-card {
    background: #f0f4ff;
    border-left: 4px solid #4f6ef7;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 16px;
    font-size: 0.93rem;
}
.config-card b { color: #1a237e; }

.tool-call {
    background: #fff8e1;
    border-left: 3px solid #fbc02d;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 0.82rem;
    color: #5d4037;
    margin: 4px 0;
}

.memory-fact {
    background: #f3e5f5;
    border-left: 3px solid #8e24aa;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 0.80rem;
    color: #4a148c;
    margin: 3px 0;
}

.persona-badge {
    display: inline-block;
    background: #e8f5e9;
    border: 1px solid #43a047;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 0.78rem;
    color: #1b5e20;
    font-weight: 600;
}

.welcome-back {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 10px;
    padding: 16px 20px;
    color: white;
    margin-bottom: 16px;
}
.welcome-back h3 { margin: 0 0 6px 0; color: white; }
.welcome-back p  { margin: 0; opacity: 0.9; font-size: 0.9rem; }

.rec-saved {
    background: #e8f5e9;
    border-left: 3px solid #2e7d32;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 0.82rem;
    color: #1b5e20;
    margin: 4px 0;
}

.rec-preview {
    background: #f9fbe7;
    border-left: 3px solid #827717;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 0.80rem;
    color: #33691e;
    margin: 3px 0;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

PERSONA_LABELS = {
    "novice_nisha":        ("🌱 Beginner",     "#e8f5e9", "#2e7d32"),
    "mid_career_mohit":    ("📊 Intermediate", "#e3f2fd", "#1565c0"),
    "sophisticated_sanjay":("🎯 Expert",       "#fff3e0", "#e65100"),
}

def _tool_label(fn_name: str, fn_args: dict) -> str:
    labels = {
        "get_stock_price":       lambda a: f"Fetching live price for {a.get('ticker')}",
        "get_stock_info":        lambda a: f"Loading company info for {a.get('ticker')}",
        "get_recent_news":       lambda a: f"Reading latest news for {a.get('ticker')}",
        "get_financial_ratios":  lambda a: f"Fetching financial ratios for {a.get('ticker')}",
        "compare_stocks":        lambda a: f"Comparing {', '.join(a.get('tickers', []))}",
        "search_knowledge_base": lambda a: f"Searching knowledge base: \"{a.get('query', '')[:40]}\"",
    }
    return labels.get(fn_name, lambda a: fn_name)(fn_args)


def _session_id_from_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _get_memory():
    from memory_store import MemoryStore
    return MemoryStore()


def _extract_facts_from_preferences(prefs: str) -> dict:
    """Derive simple user facts from the free-text preferences field."""
    facts = {}
    prefs_lower = prefs.lower()
    sectors = []
    for s in ["it", "pharma", "banking", "fmcg", "auto", "infrastructure", "energy", "real estate"]:
        if s in prefs_lower:
            sectors.append(s.upper())
    if sectors:
        facts["preferred_sectors"] = ", ".join(sectors)

    risk_map = {
        "low risk": "conservative", "conservative": "conservative", "safe": "conservative",
        "moderate": "moderate",
        "high risk": "aggressive", "aggressive": "aggressive", "growth": "aggressive",
    }
    for kw, level in risk_map.items():
        if kw in prefs_lower:
            facts["risk_tolerance_stated"] = level
            break

    for kw in ["dividend", "dividends"]:
        if kw in prefs_lower:
            facts["prefers_dividends"] = "yes"

    return facts


# ── Session state defaults ────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "phase":       "name",      # "name" | "config" | "chat"
        "agent":       None,
        "messages":    [],
        "config":      {},
        "session_id":  None,
        "user_name":   None,
        "persona_key": None,
        "prev_session": None,       # loaded from MemoryStore on name entry
        "rec_logger":  None,        # RecommendationLogger instance
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Name Screen
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.phase == "name":
    st.title("📈 AI Portfolio Advisor")
    st.markdown("Your personal AI advisor for the Indian stock market.")
    st.divider()

    col_center, _, _ = st.columns([2, 1, 1])
    with col_center:
        st.subheader("👤 Who are you?")
        st.markdown(
            "Enter your name so the advisor can remember your portfolio and "
            "conversation history across sessions."
        )
        name_input = st.text_input(
            "Your name",
            placeholder="e.g. Rahul Sharma",
            label_visibility="collapsed",
        )

        if st.button("Continue →", type="primary", use_container_width=True,
                     disabled=not name_input.strip()):
            user_name  = name_input.strip()
            session_id = _session_id_from_name(user_name)

            # Load previous session from SQLite
            try:
                prev = _get_memory().load_session(session_id)
            except Exception:
                prev = None

            st.session_state.user_name   = user_name
            st.session_state.session_id  = session_id
            st.session_state.prev_session = prev
            st.session_state.phase        = "config"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Config Screen
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.phase == "config":
    user_name  = st.session_state.user_name
    prev       = st.session_state.prev_session

    st.title("📈 AI Portfolio Advisor")

    # ── Welcome back banner ───────────────────────────────────────────────────
    if prev:
        last_seen = prev.get("last_seen", "")[:10]
        prev_tickers = ", ".join(prev.get("tickers", [])) or "—"
        persona_label = PERSONA_LABELS.get(prev.get("persona", ""), ("", "", ""))[0]
        st.markdown(f"""
<div class="welcome-back">
  <h3>Welcome back, {user_name}! 🎉</h3>
  <p>Last session: {last_seen} &nbsp;|&nbsp; Previous holdings: {prev_tickers}
  &nbsp;|&nbsp; Investor type: {persona_label}</p>
</div>
""", unsafe_allow_html=True)
        default_tickers = ", ".join(prev.get("tickers", []))
        default_corpus  = float(prev.get("corpus", 50_000.0))
        default_prefs   = prev.get("preferences", "")
    else:
        st.markdown(f"Nice to meet you, **{user_name}**! Let's set up your portfolio.")
        default_tickers = ""
        default_corpus  = 50_000.0
        default_prefs   = ""
        
    col1, col2 = st.columns([1, 1])
    with col1:
        pass
    with col2:
        st.page_link("pages/history.py", label="📋 View Past Chats & Feedback", icon="📊")

    st.divider()

    with st.form("config_form"):
        st.subheader("🗂️ Your Portfolio")
        portfolio_input = st.text_input(
            "Current holdings — ticker symbols, comma separated",
            value=default_tickers,
            placeholder="e.g. RELIANCE.NS, TCS.NS, INFY.BO",
            help="Use .NS for NSE, .BO for BSE",
        )

        st.subheader("💰 Investment Corpus")
        corpus = st.number_input(
            "Amount available to invest (₹)",
            min_value=0.0,
            value=default_corpus,
            step=5_000.0,
        )

        st.subheader("🎯 Preferences & Risk Appetite")
        preferences = st.text_area(
            "Describe your investment style",
            value=default_prefs,
            placeholder="e.g. I prefer low-risk dividend-paying stocks in the IT and pharma sectors.",
            height=120,
        )

        submitted = st.form_submit_button("🚀 Start Chat", type="primary",
                                          use_container_width=True)

    if submitted:
        if not os.environ.get("GEMINI_API_KEY"):
            st.error("⚠️ GEMINI_API_KEY is not set. Add it to your .env file.")
            st.stop()

        tickers    = [t.strip().upper() for t in portfolio_input.split(",") if t.strip()]
        session_id = st.session_state.session_id
        user_name  = st.session_state.user_name

        # Detect persona for memory storage
        try:
            from persona_detector import PersonaDetector
            persona_key = PersonaDetector().detect_persona(portfolio_size=corpus)
        except Exception:
            persona_key = "mid_career_mohit"

        st.session_state.persona_key = persona_key

        # Persist config to memory
        try:
            mem = _get_memory()
            mem.save_session(session_id, user_name, tickers, corpus, preferences, persona_key)
            # Extract and store user facts from preferences text
            facts = _extract_facts_from_preferences(preferences)
            for k, v in facts.items():
                mem.upsert_fact(session_id, k, v)
        except Exception as e:
            st.warning(f"Memory save failed: {e}")

        st.session_state.config = {
            "tickers":     tickers,
            "corpus":      corpus,
            "preferences": preferences,
        }
        
        # ── Start new Chat Session ─────────────────────────────────────────────
        import uuid
        chat_id = str(uuid.uuid4())
        st.session_state.chat_id = chat_id
        
        try:
            mem = _get_memory()
            mem.create_chat_session(chat_id, session_id, tickers, corpus, preferences, persona_key)
            
            # Run performance tracker BEFORE agent starts so self-analysis is fresh
            with st.spinner("Analyzing past recommendations..."):
                from performance_tracker import update_all_open_recommendations
                update_all_open_recommendations()
        except Exception as e:
            st.warning(f"Chat setup failed: {e}")

        # Create agent and run opening analysis
        from agent_core import AdvisorAgent
        from recommendation_logger import RecommendationLogger
        agent = AdvisorAgent()
        st.session_state.agent = agent

        # Create the per-session recommendation logger
        rec_config = {"tickers": tickers, "corpus": corpus}
        st.session_state.rec_logger = RecommendationLogger(
            chat_id=chat_id,
            user_id=session_id,
            user_name=user_name,
            config=rec_config,
        )

        tool_steps   = []
        opening_text = ""
        with st.spinner("Your advisor is reviewing your portfolio…"):
            for event in agent.initialize(
                tickers, corpus, preferences,
                session_id=session_id,
                user_name=user_name,
            ):
                if event[0] == "TOOL":
                    _, fn_name, fn_args = event
                    tool_steps.append(_tool_label(fn_name, fn_args))
                elif event[0] == "TEXT":
                    opening_text = event[1]

        # Process opening text through recommendation logger (strips tags, extracts recs)
        clean_opening, opening_recs = st.session_state.rec_logger.process(opening_text)

        # Save opening assistant message to memory
        try:
            _get_memory().append_message(session_id, "assistant", clean_opening, tool_steps)
        except Exception:
            pass

        st.session_state.messages.append({
            "role":       "assistant",
            "content":    clean_opening,
            "tool_steps": tool_steps,
            "recs":       opening_recs,
        })

        st.session_state.phase = "chat"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Chat Screen
# ══════════════════════════════════════════════════════════════════════════════

else:
    cfg        = st.session_state.config
    tickers    = cfg.get("tickers", [])
    corpus     = cfg.get("corpus", 0)
    prefs      = cfg.get("preferences", "")
    user_name  = st.session_state.user_name or ""
    session_id = st.session_state.session_id
    persona_key = st.session_state.persona_key or "mid_career_mohit"

    # ── Sidebar — Memory Panel ─────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 🧠 Advisor Memory")

        # Persona badge
        p_label, p_bg, p_color = PERSONA_LABELS.get(persona_key, ("📊 Intermediate", "#e3f2fd", "#1565c0"))
        st.markdown(
            f'<span style="background:{p_bg};color:{p_color};border-radius:12px;'
            f'padding:4px 12px;font-size:0.82rem;font-weight:600;">{p_label}</span>',
            unsafe_allow_html=True,
        )
        st.markdown("")

        # Session info
        st.markdown(f"**User:** {user_name}")
        msg_count = len(st.session_state.messages)
        st.markdown(f"**Messages this session:** {msg_count}")

        # User facts
        if session_id:
            try:
                facts = _get_memory().get_user_facts(session_id)
                if facts:
                    st.markdown("**📌 What I know about you:**")
                    for k, v in facts.items():
                        label = k.replace("_", " ").title()
                        st.markdown(
                            f'<div class="memory-fact"><b>{label}:</b> {v}</div>',
                            unsafe_allow_html=True,
                        )
            except Exception:
                pass

        # Portfolio quick view
        st.divider()
        st.markdown("**💼 Portfolio:**")
        for t in tickers:
            st.markdown(f"• `{t}`")
        st.markdown(f"**💰 Corpus:** ₹{corpus:,.0f}")

        # ── Recommendations panel ─────────────────────────────────────────────
        rec_logger = st.session_state.rec_logger
        if rec_logger and rec_logger.recommendation_count > 0:
            st.divider()
            st.markdown("**📊 Recommendations this session:**")
            st.markdown(
                f'<div class="rec-saved">📄 {rec_logger.recommendation_count} recommendation(s) logged</div>',
                unsafe_allow_html=True,
            )
            rec_file = rec_logger.file_path
            abs_path = os.path.abspath(rec_file)
            st.markdown(f"📁 `{abs_path}`")
            if st.button("📂 Open recommendations folder", use_container_width=True):
                import subprocess
                subprocess.Popen(f'explorer /select,"{abs_path}"')

        st.divider()
        if st.button("⚙️ Reconfigure", use_container_width=True):
            for k in ["phase", "agent", "messages", "config", "persona_key", "prev_session", "rec_logger"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state.phase = "name"
            st.rerun()

    # ── Main chat area ─────────────────────────────────────────────────────────
    col_title, _ = st.columns([6, 1])
    with col_title:
        st.title(f"📈 Hi {user_name}!" if user_name else "📈 AI Portfolio Advisor")

    # Config summary card
    holdings_str = ", ".join(f"`{t}`" for t in tickers) if tickers else "_None_"
    st.markdown(f"""
<div class="config-card">
  <b>Holdings:</b> {holdings_str} &nbsp;|&nbsp;
  <b>Corpus:</b> ₹{corpus:,.0f} &nbsp;|&nbsp;
  <b>Preferences:</b> {prefs or "—"}
</div>
""", unsafe_allow_html=True)

    st.divider()

    # ── Conversation history ───────────────────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("tool_steps"):
                with st.expander("🔍 Agent reasoning", expanded=False):
                    for step in msg["tool_steps"]:
                        st.markdown(
                            f'<div class="tool-call">⚙️ {step}</div>',
                            unsafe_allow_html=True,
                        )
            st.markdown(msg["content"])

    # ── Chat input ─────────────────────────────────────────────────────────────
    user_input = st.chat_input("Ask your advisor anything…")

    if user_input:
        # Show user message immediately
        st.session_state.messages.append({
            "role": "user", "content": user_input, "tool_steps": []
        })
        with st.chat_message("user"):
            st.markdown(user_input)

        # Persist user message to memory
        if session_id:
            try:
                _get_memory().append_message(session_id, "user", user_input, [])
            except Exception:
                pass

        # Run agent turn
        agent      = st.session_state.agent
        tool_steps = []
        response_text = ""

        with st.chat_message("assistant"):
            status_placeholder = st.empty()

            for event in agent.chat_turn(user_input):
                if event[0] == "TOOL":
                    _, fn_name, fn_args = event
                    label = _tool_label(fn_name, fn_args)
                    tool_steps.append(label)
                    status_placeholder.markdown(
                        f'<div class="tool-call">⚙️ {label}</div>',
                        unsafe_allow_html=True,
                    )
                elif event[0] == "TEXT":
                    response_text = event[1]

            status_placeholder.empty()

            if tool_steps:
                with st.expander("🔍 Agent reasoning", expanded=False):
                    for step in tool_steps:
                        st.markdown(
                            f'<div class="tool-call">⚙️ {step}</div>',
                            unsafe_allow_html=True,
                        )

            # Process through recommendation logger: strips [RECOMMENDATION] tags,
            # extracts structured recs, and appends them to recommendations/{session_id}.md
            rec_logger = st.session_state.rec_logger
            if rec_logger:
                clean_text, new_recs = rec_logger.process(response_text)
            else:
                clean_text, new_recs = response_text, []

            st.markdown(clean_text)

            # Show "saved" indicator inline if any recommendations were logged
            if new_recs:
                rec_lines = []
                for r in new_recs:
                    action = r.get("ACTION", "?").upper()
                    ticker = r.get("TICKER", "?")
                    emoji  = {"BUY": "🟢", "INVEST": "🟢", "ACCUMULATE": "🟢",
                               "HOLD": "🟡", "SELL": "🔴", "DIVEST": "🔴",
                               "REDUCE": "🟠", "AVOID": "⚫"}.get(action, "📌")
                    rec_lines.append(f"{emoji} {action} {ticker}")
                summary = " &nbsp;|&nbsp; ".join(rec_lines)
                st.markdown(
                    f'<div class="rec-saved">📄 Recommendation logged: {summary}</div>',
                    unsafe_allow_html=True,
                )

        # Persist assistant message to memory
        if session_id:
            try:
                _get_memory().append_message(
                    session_id, "assistant", clean_text, tool_steps
                )
                _get_memory().touch_session(session_id)
            except Exception:
                pass

        st.session_state.messages.append({
            "role":       "assistant",
            "content":    clean_text,
            "tool_steps": tool_steps,
            "recs":       new_recs,
        })
