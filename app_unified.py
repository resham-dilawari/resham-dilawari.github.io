"""
Unified AI Advisor Dashboard
Two Products: Portfolio Advisor (WealthTech) + Merchant Underwriting (B2B Fintech)
"""
import streamlit as st
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Page configuration - Mobile friendly with LIGHT THEME
st.set_page_config(
    page_title="AI Advisor Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Force light theme in Streamlit config
st.markdown("""
<script>
// Force light mode
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    location.reload();
});
</script>
""", unsafe_allow_html=True)

# Add viewport meta for mobile responsiveness
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
""", unsafe_allow_html=True)

# Custom CSS - Modern UI
st.markdown("""
<style>
    /* Reduce top padding */
    .block-container {
        padding-top: 1rem !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: #f8f9fa;
    }
    
    /* Sidebar divider */
    [data-testid="stSidebar"] hr {
        margin: 15px 0;
        border: none;
        height: 1px;
        background: #e0e0e0;
    }
    
    /* Main container styling - FORCE WHITE WITH BLACK TEXT */
    .stApp {
        background: #ffffff !important;
        color: #1a1a1a !important;
    }
    
    /* Force all text to be dark */
    .stApp *, .main *, p, span, div {
        color: #1a1a1a !important;
    }
    
    /* But keep colored elements colored */
    .product-title {
        color: #1a1a1a !important;
    }
    
    .product-desc {
        color: #666666 !important;
    }
    
    .product-stats {
        color: #555555 !important;
    }
    
    /* Product cards */
    .product-card {
        background: #ffffff;
        border: 2px solid #e8e8e8;
        border-radius: 20px;
        padding: 35px;
        margin: 10px;
        transition: all 0.3s ease;
        height: 100%;
        position: relative;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    .product-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .product-card:hover {
        transform: translateY(-8px);
        box-shadow: 0 12px 32px rgba(0,0,0,0.15);
        border: 2px solid #667eea;
    }
    
    .product-card:hover::before {
        opacity: 1;
    }
    
    .product-card-green:hover {
        border: 2px solid #11998e;
    }
    
    .product-card-green::before {
        background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
    }
    
    .product-icon {
        font-size: 48px;
        margin-bottom: 15px;
        display: block;
    }
    
    .product-title {
        font-size: 28px;
        font-weight: 700;
        margin-bottom: 12px;
        color: #1a1a1a;
        letter-spacing: -0.5px;
    }
    
    .product-desc {
        font-size: 15px;
        color: #666666;
        line-height: 1.6;
        margin-bottom: 20px;
    }
    
    .product-stats {
        margin-top: 20px;
        font-size: 13px;
        color: #555555;
        line-height: 1.8;
    }
    
    .product-stats div {
        padding: 4px 0;
        display: flex;
        align-items: center;
    }
    
    .product-stats div::before {
        content: '✓';
        color: #10b981;
        font-weight: bold;
        margin-right: 8px;
        font-size: 16px;
    }
    
    /* Button styling */
    .stButton button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 14px 24px;
        font-size: 16px;
        font-weight: 600;
        border-radius: 12px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 25px rgba(102, 126, 234, 0.6);
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
    
    /* Breadcrumb button styling */
    [data-testid="stSidebar"] button[kind="secondary"] {
        background: #ffffff !important;
        border: 2px solid #e8e8e8 !important;
        color: #555 !important;
        font-weight: 500 !important;
        padding: 12px 16px !important;
        border-radius: 10px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06) !important;
        text-transform: none !important;
        letter-spacing: 0 !important;
        font-size: 14px !important;
    }
    
    [data-testid="stSidebar"] button[kind="secondary"]:hover {
        background: #f8f9fa !important;
        border-color: #667eea !important;
        color: #667eea !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15) !important;
    }
    
    [data-testid="stSidebar"] button[kind="secondary"] p {
        font-size: 14px !important;
    }
    
    /* Hide breadcrumb navigation classes (not used) */
    .breadcrumb {
        display: none;
    }
    
    /* Title styling */
    h1 {
        color: #1a1a1a !important;
        font-weight: 800 !important;
        font-size: 48px !important;
        margin-top: 0px !important;
        margin-bottom: 10px !important;
        text-align: left !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #11998e 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block;
    }
    
    h2, h3 {
        color: #555555 !important;
        font-weight: 600 !important;
        text-align: left !important;
        margin-bottom: 30px !important;
    }
    
    /* Comparison table styling - FORCE WHITE */
    .stDataFrame, .stDataFrame > div, .stDataFrame table {
        background: #ffffff !important;
        background-color: #ffffff !important;
    }
    
    [data-testid="stDataFrame"] {
        background: #ffffff !important;
        background-color: #ffffff !important;
    }
    
    [data-testid="stDataFrame"] > div {
        background: #ffffff !important;
        background-color: #ffffff !important;
    }
    
    /* Table container */
    .stDataFrame {
        background: #ffffff !important;
        border-radius: 12px;
        padding: 10px;
        border: 1px solid #e8e8e8;
    }
    
    /* Table itself */
    table {
        background: #ffffff !important;
        background-color: #ffffff !important;
    }
    
    /* Table header */
    thead, thead tr, thead tr th {
        background: #f8f9fa !important;
        background-color: #f8f9fa !important;
        color: #1a1a1a !important;
        font-weight: 600 !important;
        border-bottom: 2px solid #e8e8e8 !important;
    }
    
    /* Table body */
    tbody, tbody tr, tbody tr td {
        background: #ffffff !important;
        background-color: #ffffff !important;
        color: #333333 !important;
        border-bottom: 1px solid #f0f0f0 !important;
    }
    
    tbody tr:hover, tbody tr:hover td {
        background: #f8f9fa !important;
        background-color: #f8f9fa !important;
    }
    
    /* Override any dark mode */
    .stDataFrame * {
        background-color: inherit !important;
    }
    
    /* Divider styling */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #e8e8e8, transparent);
        margin: 40px 0;
    }
    
    /* Mobile Responsive */
    @media only screen and (max-width: 768px) {
        h1 {
            font-size: 32px !important;
        }
        .product-card {
            padding: 25px;
            margin: 10px 0;
        }
        .product-icon {
            font-size: 36px;
        }
        .product-title {
            font-size: 22px;
        }
        .product-desc {
            font-size: 14px;
        }
        .stButton button {
            padding: 12px 20px;
            font-size: 14px;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'selected_product' not in st.session_state:
    st.session_state.selected_product = None

def main():
    """Main application with product selection."""
    
    # Check API key
    if not os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") == "your_api_key_here":
        st.error("⚠️ GEMINI_API_KEY is not set. Please add it to your .env file.")
        st.stop()
    
    # Check query parameters for routing
    if "page" in st.query_params:
        page_param = st.query_params["page"]
        if page_param == "aiportfolioadvisor":
            st.session_state.selected_product = "stocks"
        elif page_param == "merchantunderwriting":
            st.session_state.selected_product = "underwriting"
        elif page_param == "home":
            st.session_state.selected_product = None
    
    # Product Selection Screen
    if st.session_state.selected_product is None:
        st.query_params["page"] = "home"
        st.title("🤖 AI Advisor Platform")
        st.markdown("### Select Your Product")
        
        col1, col2 = st.columns(2, gap="medium")
        
        with col1:
            st.markdown("""
            <div class="product-card">
                <span class="product-icon">📈</span>
                <div class="product-title">Stock Advisor</div>
                <div class="product-desc">
                    AI-powered equity research and stock analysis for retail investors.
                    Get personalized stock recommendations, risk analysis, and market insights.
                </div>
                <div class="product-stats">
                    <div>Equity/Stock focus only</div>
                    <div>Multi-agent analysis</div>
                    <div>3 investor personas</div>
                    <div>Stock + Risk Analytics</div>
                    <div>Tax optimization (STCG/LTCG)</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🚀 Launch Stock Advisor", key="stock_btn", use_container_width=True):
                st.session_state.selected_product = "stocks"
                st.query_params["page"] = "aiportfolioadvisor"
                st.rerun()
        
        with col2:
            st.markdown("""
            <div class="product-card product-card-green">
                <span class="product-icon">🏪</span>
                <div class="product-title">Merchant Underwriting</div>
                <div class="product-desc">
                    Automated KYC/KYB risk assessment for B2B fintech platforms.
                    Screen merchants for fraud, AML, and credit risks in seconds.
                </div>
                <div class="product-stats">
                    <div>Red flag detection</div>
                    <div>Regulatory checks</div>
                    <div>Financial health analysis</div>
                    <div>Sanctions screening</div>
                    <div>80% time reduction</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🚀 Launch Merchant Underwriting", key="underwrite_btn", use_container_width=True):
                st.session_state.selected_product = "underwriting"
                st.query_params["page"] = "merchantunderwriting"
                st.rerun()
        
        # Feature Comparison
        st.divider()
        st.subheader("📋 Feature Comparison")
        
        comparison_data = {
            "Feature": [
                "Target User",
                "Industry",
                "Use Case",
                "Asset Coverage",
                "Analysis Time",
                "Key Output",
                "Agents",
                "Data Sources"
            ],
            "Stock Advisor": [
                "Retail Investors",
                "WealthTech",
                "Stock research & risk analytics",
                "Equities/Stocks only (NSE/BSE)",
                "<60 seconds",
                "BUY/HOLD/SELL recommendations",
                "8 specialized agents",
                "Stock data, news, financials"
            ],
            "Merchant Underwriting": [
                "Risk Analysts (Internal)",
                "B2B Fintech",
                "Merchant KYC/KYB screening",
                "Business entities",
                "<30 seconds",
                "Risk Assessment Brief",
                "5 specialized agents",
                "News, registries, watchlists"
            ]
        }
        
        # Render as HTML table with explicit inline styles
        html_table = """
        <table style="width: 100%; border-collapse: collapse; background: white;">
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e8e8e8; color: #1a1a1a; font-weight: 600;">Feature</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e8e8e8; color: #1a1a1a; font-weight: 600;">Stock Advisor</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e8e8e8; color: #1a1a1a; font-weight: 600;">Merchant Underwriting</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Target User</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Retail Investors</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Risk Analysts (Internal)</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Industry</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">WealthTech</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">B2B Fintech</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Use Case</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Stock research & risk analytics</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Merchant KYC/KYB screening</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Asset Coverage</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Equities/Stocks only (NSE/BSE)</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Business entities</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Analysis Time</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">&lt;60 seconds</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">&lt;30 seconds</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Key Output</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">BUY/HOLD/SELL recommendations</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Risk Assessment Brief</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Agents</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">8 specialized agents</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">5 specialized agents</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Data Sources</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">Stock data, news, financials</td>
                    <td style="padding: 10px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; background: white;">News, registries, watchlists</td>
                </tr>
            </tbody>
        </table>
        """
        
        st.markdown(html_table, unsafe_allow_html=True)
    
    # Route to selected product
    elif st.session_state.selected_product == "stocks":
        # Ensure query params reflect current page
        st.query_params["page"] = "aiportfolioadvisor"
        
        # Breadcrumb navigation at top of main page
        # Simple text breadcrumb
        st.markdown(
            '<div style="padding-bottom: 5px; font-size: 14px;"><a href="?page=home" style="text-decoration: none; color: #0066cc;">🏠 Home</a> &nbsp;/&nbsp; 📈 Stock Advisor</div>', 
            unsafe_allow_html=True
        )
        
        # Import the stock advisor app
        import app_multiagent
        app_multiagent.main()
        return  # Prevent home page content from rendering
    
    elif st.session_state.selected_product == "underwriting":
        # Ensure query params reflect current page
        st.query_params["page"] = "merchantunderwriting"
        
        # Breadcrumb navigation at top of main page  
        # Simple text breadcrumb
        st.markdown(
            '<div style="padding-bottom: 5px; font-size: 14px;"><a href="?page=home" style="text-decoration: none; color: #0066cc;">🏠 Home</a> &nbsp;/&nbsp; 🏢 Merchant Underwriting</div>', 
            unsafe_allow_html=True
        )
        
        # Import the underwriting app
        import app_underwriting
        app_underwriting.main()
        return  # Prevent home page content from rendering

if __name__ == "__main__":
    main()
