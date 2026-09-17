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
    
    # Title and Description
    st.title("🤖 Multi-Agent AI Portfolio Advisor")
    
    # Custom CSS for better UI
    st.markdown("""
    <style>
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
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding-left: 20px;
            padding-right: 20px;
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
    
    # Configuration / Filters
    st.markdown("### ⚙️ Configuration & Filters")
    
    # 1st Row
    col1, col2, col3 = st.columns(3)
    with col1:
        analysis_mode = st.selectbox(
            "Analysis Mode",
            ["Full Advisory", "Portfolio Analysis Only", "Investment Suggestions Only"],
            help="Full Advisory runs all agents for comprehensive analysis"
        )
    with col2:
        portfolio_input = st.text_input(
            "Enter Stock Tickers",
            placeholder="e.g. RELIANCE, TCS, INFY",
            help="Enter tickers separated by commas, spaces, or anything else."
        )
    with col3:
        corpus = st.number_input(
            "Available corpus (₹)",
            min_value=0.0,
            value=100000.0,
            step=10000.0
        )
        
    # 2nd Row
    col4, col5, col6 = st.columns(3)
    with col4:
        risk_tolerance = st.select_slider(
            "Risk Tolerance",
            options=["Very Conservative", "Conservative", "Moderate", "Aggressive", "Very Aggressive"],
            value="Moderate"
        )
    with col5:
        investment_goals = st.multiselect(
            "Investment Goals",
            ["Wealth Creation", "Regular Income", "Retirement Planning", "Tax Saving", "Short-term Gains"],
            default=["Wealth Creation"]
        )
    with col6:
        market_cap_filter = st.multiselect(
            "Market Cap",
            ["Large Cap", "Mid Cap", "Small Cap", "Multi Cap"],
            default=["Large Cap", "Mid Cap", "Small Cap", "Multi Cap"],
            help="Filter suggestions based on market capitalization"
        )
        
    # 3rd Row
    col7, col8 = st.columns([2, 1])
    with col7:
        preferences = st.text_area(
            "Additional preferences",
            placeholder="e.g., Focus on IT sector, prefer dividend stocks, ESG investing",
            height=68
        )
    with col8:
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_button = st.button("🚀 Run Multi-Agent Analysis", type="primary", use_container_width=True)
        
    st.markdown("---")
    # Main content area
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
        st.info("🤖 Initializing multi-agent system...")
        
        with st.spinner("🔄 Agents are analyzing... This may take 30-60 seconds"):
            try:
                # Fetch comprehensive data
                with st.status("Fetching market data...") as status:
                    st.write("📡 Downloading data from Yahoo Finance...")
                    portfolio_data_list = FinancialDataProvider.get_portfolio_data(tickers)
                    status.update(label="✅ Data fetched successfully!", state="complete")
                
                # Prepare context for orchestrator
                context = {
                    "request_type": "full_advisory" if analysis_mode == "Full Advisory"
                                  else "portfolio_analysis" if analysis_mode == "Portfolio Analysis Only"
                                  else "investment_suggestion",
                    "portfolio_data": portfolio_data_list,  # full list, not just [0]
                    "tickers": tickers,
                    "current_holdings": tickers,
                    "corpus": corpus,
                    "user_profile": {
                        "risk_tolerance": risk_tolerance,
                        "goals": investment_goals,
                        "preferences": preferences,
                        "market_cap_preference": market_cap_filter,
                        "tax_bracket": "30%"  # Can be made configurable
                    },
                    "market_context": {
                        "general": "Indian equity markets, current conditions"
                    }
                }
                
                # Run orchestrator
                with st.status("🤖 Multi-agent system running...") as status:
                    st.write("🎭 Orchestrator coordinating agents...")
                    st.write("🔍 Fundamental Analysis Agent analyzing...")
                    st.write("📈 Technical Analysis Agent working...")
                    st.write("📰 Sentiment Analysis Agent processing news...")
                    st.write("⚠️ Risk Assessment Agent calculating...")
                    st.write("🎯 Optimizer Agent optimizing...")
                    
                    results = st.session_state.orchestrator.analyze(context)
                    st.session_state.analysis_results = results
                    st.session_state.execution_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "mode": analysis_mode,
                        "tickers": tickers
                    })
                    
                    status.update(label="✅ Analysis complete!", state="complete")
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
                <div class="agent-name">👨‍💼 Orchestrator Agent</div>
                Coordinates all agents and synthesizes insights
            </div>
            """, unsafe_allow_html=True)
        
        st.info("👈 Configure your portfolio in the sidebar and click 'Run Multi-Agent Analysis' to begin!")
        
        # Show execution history if available
        if st.session_state.execution_history:
            st.subheader("📜 Previous Analyses")
            for i, hist in enumerate(reversed(st.session_state.execution_history[-5:])):
                st.write(f"{i+1}. {hist['timestamp']} - {hist['mode']} - {', '.join(hist['tickers'][:3])}")


if __name__ == "__main__":
    main()
