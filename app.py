"""
app.py — AI Portfolio Advisor (Agentic)

Flow:
  Phase 1 — Config screen: user enters tickers, corpus, preferences
  Phase 2 — Chat screen:   config shown as a retained read-only summary
                            + full conversational chat powered by the agent loop
"""
import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(
    page_title="AI Portfolio Advisor",
    page_icon="📈",
    layout="wide",
)

# ── Inject minimal CSS ─────────────────────────────────────────────────────────
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
</style>
""", unsafe_allow_html=True)


# ── Helper ────────────────────────────────────────────────────────────────────
def _tool_label(fn_name: str, fn_args: dict) -> str:
    """Human-readable label for a tool call."""
    labels = {
        "get_stock_price":      lambda a: f"Fetching live price for {a.get('ticker')}",
        "get_stock_info":       lambda a: f"Loading company info for {a.get('ticker')}",
        "get_recent_news":      lambda a: f"Reading latest news for {a.get('ticker')}",
        "get_financial_ratios": lambda a: f"Fetching financial ratios for {a.get('ticker')}",
        "compare_stocks":       lambda a: f"Comparing {', '.join(a.get('tickers', []))}",
    }
    return labels.get(fn_name, lambda a: fn_name)(fn_args)


# ── Session state defaults ─────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "phase": "config",          # "config" | "chat"
        "agent": None,
        "messages": [],             # [{role, content, tool_steps}]
        "config": {},               # retained config dict
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Config Screen
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.phase == "config":

    st.title("📈 AI Portfolio Advisor")
    st.markdown("Set up your profile once, then chat freely with your AI advisor.")
    st.divider()

    with st.form("config_form"):
        st.subheader("🗂️ Your Portfolio")
        portfolio_input = st.text_input(
            "Current holdings — ticker symbols, comma separated",
            placeholder="e.g. RELIANCE.NS, TCS.NS, INFY.BO",
            help="Use .NS for NSE, .BO for BSE",
        )

        st.subheader("💰 Investment Corpus")
        corpus = st.number_input(
            "Amount available to invest (₹)",
            min_value=0.0,
            value=50_000.0,
            step=5_000.0,
        )

        st.subheader("🎯 Preferences & Risk Appetite")
        preferences = st.text_area(
            "Describe your investment style",
            placeholder="e.g. I prefer low-risk dividend-paying stocks in the IT and pharma sectors.",
            height=120,
        )

        submitted = st.form_submit_button("🚀 Start Chat", type="primary", use_container_width=True)

    if submitted:
        # Validate API key
        if not os.environ.get("GEMINI_API_KEY"):
            st.error("⚠️ GEMINI_API_KEY is not set. Add it to your .env file.")
            st.stop()

        tickers = [t.strip().upper() for t in portfolio_input.split(",") if t.strip()]

        # Persist config
        st.session_state.config = {
            "tickers": tickers,
            "corpus": corpus,
            "preferences": preferences,
        }

        # Create agent and run opening analysis
        from agent_core import AdvisorAgent
        agent = AdvisorAgent()
        st.session_state.agent = agent

        # Run opening message, collect events
        tool_steps = []
        opening_text = ""
        with st.spinner("Your advisor is reviewing your portfolio…"):
            for event in agent.initialize(tickers, corpus, preferences):
                if event[0] == "TOOL":
                    _, fn_name, fn_args = event
                    label = _tool_label(fn_name, fn_args)
                    tool_steps.append(label)
                elif event[0] == "TEXT":
                    opening_text = event[1]

        # Store as first assistant message
        st.session_state.messages.append({
            "role": "assistant",
            "content": opening_text,
            "tool_steps": tool_steps,
        })

        st.session_state.phase = "chat"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Chat Screen
# ══════════════════════════════════════════════════════════════════════════════
else:
    cfg = st.session_state.config
    tickers = cfg.get("tickers", [])
    corpus  = cfg.get("corpus", 0)
    prefs   = cfg.get("preferences", "")

    # ── Header ────────────────────────────────────────────────────────────────
    col_title, col_reset = st.columns([5, 1])
    with col_title:
        st.title("📈 AI Portfolio Advisor")
    with col_reset:
        if st.button("⚙️ Reconfigure", use_container_width=True):
            # Reset everything, go back to config
            for k in ["phase", "agent", "messages", "config"]:
                del st.session_state[k]
            st.rerun()

    # ── Retained config summary card ──────────────────────────────────────────
    holdings_str = ", ".join(f"`{t}`" for t in tickers) if tickers else "_None_"
    st.markdown(f"""
<div class="config-card">
  <b>Holdings:</b> {holdings_str} &nbsp;|&nbsp;
  <b>Corpus:</b> ₹{corpus:,.0f} &nbsp;|&nbsp;
  <b>Preferences:</b> {prefs or "—"}
</div>
""", unsafe_allow_html=True)

    st.divider()

    # ── Render conversation history ────────────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            # Show tool steps (agent thinking) if any
            if msg.get("tool_steps"):
                with st.expander("🔍 Agent reasoning", expanded=False):
                    for step in msg["tool_steps"]:
                        st.markdown(f'<div class="tool-call">⚙️ {step}</div>',
                                    unsafe_allow_html=True)
            st.markdown(msg["content"])

    # ── Chat input ────────────────────────────────────────────────────────────
    user_input = st.chat_input("Ask your advisor anything…")

    if user_input:
        # Show user message immediately
        st.session_state.messages.append({"role": "user", "content": user_input, "tool_steps": []})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Run agent turn
        agent = st.session_state.agent
        tool_steps = []
        response_text = ""

        with st.chat_message("assistant"):
            status_placeholder = st.empty()

            for event in agent.chat_turn(user_input):
                if event[0] == "TOOL":
                    _, fn_name, fn_args = event
                    label = _tool_label(fn_name, fn_args)
                    tool_steps.append(label)
                    # Show live tool-call status while running
                    status_placeholder.markdown(
                        f'<div class="tool-call">⚙️ {label}</div>',
                        unsafe_allow_html=True,
                    )
                elif event[0] == "TEXT":
                    response_text = event[1]

            status_placeholder.empty()

            # Render tool steps as collapsible expander
            if tool_steps:
                with st.expander("🔍 Agent reasoning", expanded=False):
                    for step in tool_steps:
                        st.markdown(f'<div class="tool-call">⚙️ {step}</div>',
                                    unsafe_allow_html=True)

            st.markdown(response_text)

        st.session_state.messages.append({
            "role": "assistant",
            "content": response_text,
            "tool_steps": tool_steps,
        })


