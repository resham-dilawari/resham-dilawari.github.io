"""
Multi-Agent AI Portfolio Advisor - Streamlit Application
Showcases advanced agentic AI architecture with specialized agents
Now with Persona-Based Adaptation for personalized experiences
"""
import streamlit as st
from dotenv import load_dotenv
import os
import json
from datetime import datetime

from agents.orchestrator import OrchestratorAgent
from financial_data_enhanced import FinancialDataProvider
from persona_detector import PersonaDetector

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Multi-Agent AI Portfolio Advisor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    # Initialize session state
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = None
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'execution_history' not in st.session_state:
        st.session_state.execution_history = []
    if 'persona_detector' not in st.session_state:
        st.session_state.persona_detector = PersonaDetector()
    if 'user_persona' not in st.session_state:
        st.session_state.user_persona = None
    if 'persona_detected' not in st.session_state:
        st.session_state.persona_detected = False
    if 'questionnaire_answers' not in st.session_state:
        st.session_state.questionnaire_answers = {}
    if 'educational_mode' not in st.session_state:
        st.session_state.educational_mode = False
    if 'show_advanced_analytics' not in st.session_state:
        st.session_state.show_advanced_analytics = False
    if 'intent_key' not in st.session_state:
        st.session_state.intent_key = "both"

init_session_state()


@st.cache_resource
def get_orchestrator():
    """
    Initialize the OrchestratorAgent as a cached singleton.
    @st.cache_resource ensures all 9 genai.Client instances inside are
    created once and reused across reruns and sessions.
    """
    return OrchestratorAgent()


def initialize_orchestrator():
    """Load the cached orchestrator into session state."""
    if 'orchestrator' not in st.session_state or st.session_state.orchestrator is None:
        try:
            st.session_state.orchestrator = get_orchestrator()
            return True
        except Exception as e:
            st.error(f"Failed to initialize orchestrator: {e}")
            return False
    return True


def main():
    """Main application."""
    init_session_state()

    # Title
    st.title("🤖 Multi-Agent AI Portfolio Advisor", anchor=False)

    # ── Custom CSS ──────────────────────────────────────────────
    st.markdown("""
    <style>
        /* Agent architecture cards */
        .agent-card {
            padding: 20px;
            border-radius: 10px;
            background-color: #f0f2f6;
            margin: 10px 0;
        }
        .agent-name {
            font-size: 18px;
            font-weight: bold;
            color: #1f77b4;
        }

        /* Results tabs */
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding-left: 20px;
            padding-right: 20px;
        }

        /* ── Intent tiles ── */
        .intent-tile {
            display: flex;
            align-items: flex-start;
            gap: 14px;
            padding: 16px 18px;
            border: 2px solid #e0e0e0;
            border-radius: 14px;
            background: #ffffff;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            margin-bottom: 6px;
            transition: all 0.2s ease;
        }
        .intent-tile.selected {
            border-color: #667eea;
            background: #f0f3ff;
            box-shadow: 0 4px 14px rgba(102,126,234,0.22);
        }
        .intent-icon {
            font-size: 26px;
            line-height: 1.2;
            flex-shrink: 0;
            margin-top: 2px;
        }
        .intent-text-block { display: flex; flex-direction: column; }
        .intent-title {
            font-size: 14px;
            font-weight: 700;
            color: #1a1a1a;
            line-height: 1.35;
        }
        .intent-desc {
            font-size: 12px;
            color: #666;
            margin-top: 3px;
            line-height: 1.4;
        }

        /* Broker badge */
        .broker-badge {
            display: inline-block;
            font-size: 11px;
            font-weight: 600;
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffc107;
            border-radius: 6px;
            padding: 2px 8px;
            margin-left: 8px;
            vertical-align: middle;
        }
    </style>
    """, unsafe_allow_html=True)

    # Check API key
    if not os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") == "your_api_key_here":
        st.error("⚠️ GEMINI_API_KEY is not set. Please add it to your .env file.")
        st.stop()

    # Initialize orchestrator
    if not initialize_orchestrator():
        st.stop()

    # ────────────────────────────────────────────────────────────
    # STEP 1 — What would you like to do?
    # ────────────────────────────────────────────────────────────
    st.markdown("### What would you like to do?")

    INTENT_OPTIONS = [
        {
            "key": "advise",
            "icon": "🔍",
            "title": "Advise on my current portfolio",
            "desc": "Review holdings and get BUY / HOLD / SELL recommendations for stocks you already own",
            "mode": "Portfolio Analysis Only",
        },
        {
            "key": "discover",
            "icon": "💡",
            "title": "Find new companies to invest in",
            "desc": "Discover fresh opportunities based on your goals and risk appetite — no existing portfolio needed",
            "mode": "Investment Suggestions Only",
        },
        {
            "key": "both",
            "icon": "✨",
            "title": "Both — advise my portfolio & find new investments",
            "desc": "Full advisory: analyse what you already hold and surface the best new opportunities in one go",
            "mode": "Full Advisory",
        },
    ]

    tile_cols = st.columns(3)
    for col, opt in zip(tile_cols, INTENT_OPTIONS):
        with col:
            is_selected = st.session_state.intent_key == opt["key"]
            tile_class = "intent-tile selected" if is_selected else "intent-tile"
            st.markdown(
                f"""<div class="{tile_class}">
                    <span class="intent-icon">{opt['icon']}</span>
                    <div class="intent-text-block">
                        <span class="intent-title">{opt['title']}</span>
                        <span class="intent-desc">{opt['desc']}</span>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
            btn_label = f"✔ Selected" if is_selected else "Select"
            if st.button(
                btn_label,
                key=f"intent_btn_{opt['key']}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state.intent_key = opt["key"]
                st.rerun()

    # Derive analysis_mode and whether we need a portfolio
    selected_intent = next(o for o in INTENT_OPTIONS if o["key"] == st.session_state.intent_key)
    analysis_mode = selected_intent["mode"]
    needs_portfolio = st.session_state.intent_key in ("advise", "both")

    st.markdown("---")

    # ────────────────────────────────────────────────────────────
    # STEP 2 — Current holdings (conditional)
    # ────────────────────────────────────────────────────────────
    portfolio_input = ""

    if needs_portfolio:
        st.markdown("### 💼 Your Current Holdings")
        st.markdown(
            "<p style='color:#555;font-size:14px;margin-top:-10px;margin-bottom:14px;'>"
            "How would you like to share your portfolio?</p>",
            unsafe_allow_html=True,
        )

        input_method = st.radio(
            "Input method",
            ["✍️ Type tickers", "📁 Upload file", "🔗 Connect broker"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if input_method == "✍️ Type tickers":
            portfolio_input = st.text_input(
                "Stock tickers",
                placeholder="e.g. RELIANCE, TCS, INFY, HDFCBANK",
                help="Separate tickers with commas or spaces.",
                label_visibility="collapsed",
            )

        elif input_method == "📁 Upload file":
            uploaded_file = st.file_uploader(
                "Upload Demat / Brokerage Statement",
                type=["csv", "xlsx"],
                label_visibility="collapsed",
            )
            if uploaded_file:
                st.success(f"✅ '{uploaded_file.name}' uploaded successfully!")
                st.info("📋 Extracting holdings from statement… (Mocked for demo)")
                portfolio_input = "RELIANCE, TCS, HDFCBANK, ICICIBANK, INFY"

        elif input_method == "🔗 Connect broker":
            st.markdown(
                "Securely import your holdings directly from your broker."
                '<span class="broker-badge">Demo placeholder</span>',
                unsafe_allow_html=True,
            )
            b_col1, b_col2, b_col3, b_col4 = st.columns(4)
            with b_col1:
                if st.button("🟠 Zerodha Kite", use_container_width=True):
                    st.toast("Connecting to Zerodha…")
                    portfolio_input = "RELIANCE, TCS, HDFCBANK, ICICIBANK, INFY"
            with b_col2:
                if st.button("🔵 Groww", use_container_width=True):
                    st.toast("Connecting to Groww…")
                    portfolio_input = "RELIANCE, TCS, HDFCBANK, ICICIBANK, INFY"
            with b_col3:
                if st.button("🟣 Upstox", use_container_width=True):
                    st.toast("Connecting to Upstox…")
                    portfolio_input = "RELIANCE, TCS, HDFCBANK, ICICIBANK, INFY"
            with b_col4:
                if st.button("⭐ Angel One", use_container_width=True):
                    st.toast("Connecting to Angel One…")
                    portfolio_input = "RELIANCE, TCS, HDFCBANK, ICICIBANK, INFY"
            st.caption("🔒 Secured via Account Aggregator framework.")

        st.markdown("---")

    # ────────────────────────────────────────────────────────────
    # STEP 3 — Preferences
    # ────────────────────────────────────────────────────────────
    st.markdown("### ⚙️ Your Preferences")

    col1, col2, col3 = st.columns(3)
    with col1:
        corpus = st.number_input(
            "Available corpus (₹)",
            min_value=0.0,
            value=100000.0,
            step=10000.0
        )
    with col2:
        risk_tolerance = st.select_slider(
            "Risk Tolerance",
            options=["Very Conservative", "Conservative", "Moderate", "Aggressive", "Very Aggressive"],
            value="Moderate"
        )
    with col3:
        investment_goals = st.multiselect(
            "Investment Goals",
            ["Wealth Creation", "Regular Income", "Retirement Planning", "Tax Saving", "Short-term Gains"],
            default=["Wealth Creation"]
        )

    col4, col5 = st.columns([1, 2])
    with col4:
        market_cap_filter = st.multiselect(
            "Market Cap",
            ["Large Cap", "Mid Cap", "Small Cap", "Multi Cap"],
            default=["Large Cap", "Mid Cap", "Small Cap", "Multi Cap"],
            help="Filter suggestions based on market capitalisation"
        )
    with col5:
        preferences = st.text_area(
            "Additional preferences",
            placeholder="e.g., Focus on IT sector, prefer dividend stocks, ESG investing",
            height=68
        )

    # Action Button
    st.markdown("<br>", unsafe_allow_html=True)
    col7, col8, col9 = st.columns([1, 2, 1])
    with col8:
        analyze_button = st.button("🚀 Run Multi-Agent Analysis", type="primary", use_container_width=True)

    st.markdown("---")

    # ────────────────────────────────────────────────────────────
    # Analysis execution
    # ────────────────────────────────────────────────────────────
    if analyze_button:
        st.session_state.is_running_analysis = True
        st.session_state.analysis_results = None

    if st.session_state.get("is_running_analysis"):
        # Parse portfolio tickers
        import re
        raw_tickers = [t.strip().upper() for t in re.split(r'[,\s\n]+', portfolio_input) if t.strip()]
        tickers = []
        for t in raw_tickers:
            if t.endswith('.NS') or t.endswith('.BO'):
                tickers.append(t)
            else:
                tickers.extend([f"{t}.NS", f"{t}.BO"])
        tickers = list(dict.fromkeys(tickers))

        if not tickers and analysis_mode != "Investment Suggestions Only":
            st.warning("⚠️ Please enter at least one ticker for portfolio analysis.")
            st.stop()

        # Show agent activation status
        try:
            with st.status("🤖 Analyzing Portfolio... This may take 30-60 seconds", expanded=True) as status:
                st.write("📊 Fetching market data from Yahoo Finance...")
                portfolio_data_list = FinancialDataProvider.get_portfolio_data(tickers)
                st.write("✅ Data fetched successfully!")

                # Prepare context for orchestrator
                context = {
                    "request_type": "full_advisory" if analysis_mode == "Full Advisory"
                                  else "portfolio_analysis" if analysis_mode == "Portfolio Analysis Only"
                                  else "investment_suggestion",
                    "portfolio_data": portfolio_data_list,
                    "tickers": tickers,
                    "current_holdings": tickers,
                    "corpus": corpus,
                    "user_profile": {
                        "risk_tolerance": risk_tolerance,
                        "goals": investment_goals,
                        "preferences": preferences,
                        "market_cap_preference": market_cap_filter,
                        "tax_bracket": "30%"
                    },
                    "market_context": {
                        "general": "Indian equity markets, current conditions"
                    }
                }

                st.write("👨‍💼 Orchestrator coordinating specialized agents...")
                st.write("📈 Fundamental Analysis Agent reviewing financials...")
                st.write("📉 Technical Analysis Agent analyzing charts...")
                st.write("📰 Sentiment Analysis Agent processing news...")
                st.write("⚠️ Risk Assessment Agent calculating exposure...")
                st.write("🎯 Optimizer Agent building recommendations...")

                results = st.session_state.orchestrator.analyze(context)
                st.session_state.analysis_results = results
                st.session_state.execution_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "mode": analysis_mode,
                    "tickers": tickers
                })

                status.update(label="✅ Multi-Agent Analysis Complete!", state="complete", expanded=False)
                st.session_state.is_running_analysis = False

        except Exception as e:
            st.error(f"❌ Error during analysis: {e}")
            st.exception(e)
            st.session_state.is_running_analysis = False
            st.stop()

    if st.session_state.get("analysis_results"):
        results = st.session_state.analysis_results
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Executive Summary",
            "🤖 Agent Insights",
            "📈 Detailed Analysis",
            "🔍 Execution Log"
        ])

        # Display results in tabs
        with tab1:
            st.header("📊 Executive Summary")
            if "synthesis" in results:
                st.markdown(results["synthesis"])
            elif "final_synthesis" in results:
                st.markdown(results["final_synthesis"])
            else:
                st.info("No synthesis available")

        with tab2:
            st.header("🤖 Individual Agent Insights")

            agent_results = results.get("agent_results", {})

            for agent_name, agent_result in agent_results.items():
                with st.expander(f"🔍 {agent_name.upper()} Agent", expanded=False):
                    if isinstance(agent_result, dict) and "analysis" in agent_result:
                        st.markdown(agent_result["analysis"])
                    else:
                        st.write(agent_result)

        with tab3:
            st.header("📈 Detailed Analysis")

            # Show raw agent results
            if analysis_mode == "Full Advisory":
                st.subheader("Portfolio Analysis")
                if "portfolio_analysis" in results:
                    st.json(results["portfolio_analysis"].get("agent_results", {}))

                st.subheader("Investment Suggestions")
                if "investment_suggestions" in results:
                    st.json(results["investment_suggestions"].get("agent_results", {}))
            else:
                st.json(results)

        with tab4:
            st.header("🔍 Execution Log & Transparency")
            st.write("**Orchestrator Execution Log:**")

            if st.session_state.orchestrator:
                logs = st.session_state.orchestrator.get_execution_log()
                for log in logs:
                    with st.expander(f"{log['action']} - {log['timestamp']}", expanded=False):
                        st.json(log)

            st.write("**Agent Health Status:**")
            health = st.session_state.orchestrator.get_agent_health_status()
            st.json(health)

        # Success message
        st.success("✅ Multi-agent analysis complete!")

        # Download report button
        if st.button("📥 Download Full Report"):
            report_json = json.dumps(results, indent=2, default=str)
            st.download_button(
                label="Download JSON Report",
                data=report_json,
                file_name=f"portfolio_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

    elif not st.session_state.get("analysis_results"):
        # Show agent architecture
        st.header("🏗️ Multi-Agent System Architecture")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">🔍 Fundamental Analysis Agent</div>
                Analyzes company financials, valuations, and business models
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">📈 Technical Analysis Agent</div>
                Identifies patterns, trends, and momentum signals
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">📰 Sentiment Analysis Agent</div>
                Processes news and gauges market psychology
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">⚠️ Risk Assessment Agent</div>
                Assesses portfolio risk and diversification
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">🎯 Portfolio Optimizer Agent</div>
                Optimizes asset allocation and rebalancing
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">🔬 Market Research Agent</div>
                Explores sectors and identifies opportunities
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">💰 Tax Optimization Agent</div>
                Provides tax-efficient strategies
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">🧠 RAG Knowledge Agent</div>
                Retrieves historical insights and past preferences
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">🪞 Self-Analysis Agent</div>
                Tracks recommendation performance and auto-calibrates
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="agent-card">
                <div class="agent-name">👨‍💼 Orchestrator Agent</div>
                Coordinates all agents and synthesizes insights
            </div>
            """, unsafe_allow_html=True)

        # Show execution history if available
        if st.session_state.execution_history:
            st.subheader("📜 Previous Analyses")
            for i, hist in enumerate(reversed(st.session_state.execution_history[-5:])):
                st.write(f"{i+1}. {hist['timestamp']} - {hist['mode']} - {', '.join(hist['tickers'][:3])}")


if __name__ == "__main__":
    main()
