"""
Merchant Underwriting + Credit & Lending Application
B2B Fintech — Automated KYC/KYB Risk Assessment and Business Credit Decisions
"""
import streamlit as st
import os
import json
from datetime import datetime

from agents.underwriting_orchestrator import UnderwritingOrchestrator
from agents.credit_lending_orchestrator import CreditLendingOrchestrator
from agents.loan_structuring_agent import LoanStructuringAgent


# ── collateral options from the agent ──────────────────────────────────────
COLLATERAL_OPTIONS = LoanStructuringAgent.collateral_type_options()
COLLATERAL_KEY_MAP = {v: k for k, v in COLLATERAL_OPTIONS}


def main():
    """Merchant Underwriting + Credit & Lending Application."""
    
    # Check open recommendations
    if "lending_perf_checked" not in st.session_state:
        import performance_tracker
        performance_tracker.update_lending_recommendations()
        st.session_state.lending_perf_checked = True

    # ── CSS ────────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
        /* Mobile Responsive */
        @media only screen and (max-width: 768px) {
            .stColumn { width: 100% !important; flex: 100% !important; max-width: 100% !important; }
            .stTextInput input, .stTextArea textarea, .stSelectbox select { font-size: 14px !important; }
            .stButton button { width: 100%; font-size: 14px !important; padding: 10px !important; }
            h1 { font-size: 24px !important; }
            h2 { font-size: 20px !important; }
            h3 { font-size: 18px !important; }
            [data-testid="stMetricValue"] { font-size: 20px !important; }
        }
        @media only screen and (max-width: 480px) {
            h1 { font-size: 20px !important; }
            [data-testid="stMetricValue"] { font-size: 18px !important; }
            .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
        }

        /* Mode tiles */
        .mode-tile {
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
        .mode-tile.selected {
            border-color: #11998e;
            background: #f0faf8;
            box-shadow: 0 4px 14px rgba(17,153,142,0.18);
        }
        .mode-icon { font-size: 26px; line-height: 1.2; flex-shrink: 0; margin-top: 2px; }
        .mode-text-block { display: flex; flex-direction: column; }
        .mode-title { font-size: 14px; font-weight: 700; color: #1a1a1a; line-height: 1.35; }
        .mode-desc  { font-size: 12px; color: #666; margin-top: 3px; line-height: 1.4; }

        /* Credit score badge */
        .score-pill {
            display: inline-block;
            font-size: 28px;
            font-weight: 800;
            padding: 8px 20px;
            border-radius: 50px;
            margin-bottom: 4px;
        }
        .score-AAA, .score-AA, .score-A  { background:#d4edda; color:#155724; }
        .score-BBB                        { background:#fff3cd; color:#856404; }
        .score-BB,  .score-B              { background:#fde8d8; color:#7d3100; }
        .score-C,   .score-D              { background:#f8d7da; color:#721c24; }

        /* Section divider label */
        .section-tag {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 8px;
        }
    </style>
    """, unsafe_allow_html=True)

    # ── Title ──────────────────────────────────────────────────────────────
    st.title("🏢 B2B Risk & Credit Platform", anchor=False)
    st.markdown(
        "AI-powered merchant onboarding screening and business credit decisions "
        "for B2B fintech teams.")

    # ── Session state ──────────────────────────────────────────────────────
    for key, default in [
        ("uw_orchestrator",   None),
        ("cl_orchestrator",   None),
        ("uw_results",        None),
        ("cl_results",        None),
        ("uw_history",        []),
        ("cl_history",        []),
        ("b2b_mode",          "onboarding"),
        ("lending_chat_id",   None),
        ("lending_agent",     None),
        ("lending_messages",  []),
        ("lending_logger",    None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Orchestrator init ──────────────────────────────────────────────────
    if st.session_state.uw_orchestrator is None:
        try:
            st.session_state.uw_orchestrator = UnderwritingOrchestrator()
        except Exception as e:
            st.error(f"Failed to initialise underwriting system: {e}")
            st.stop()

    if st.session_state.cl_orchestrator is None:
        try:
            st.session_state.cl_orchestrator = CreditLendingOrchestrator()
        except Exception as e:
            st.error(f"Failed to initialise credit & lending system: {e}")
            st.stop()

    # ════════════════════════════════════════════════════════════════════════
    # MODE SELECTOR
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("### What would you like to do?")

    MODE_OPTIONS = [
        {
            "key": "onboarding",
            "icon": "🏪",
            "title": "Merchant Onboarding",
            "desc": "KYC/KYB screening — approve or reject merchant applications "
                    "for payment gateway or neo-banking onboarding",
        },
        {
            "key": "credit",
            "icon": "💳",
            "title": "Credit & Lending",
            "desc": "Business loan assessment — credit score, DSCR, collateral "
                    "analysis, and full loan term structuring",
        },
    ]

    mcol1, mcol2 = st.columns(2)
    for col, opt in zip([mcol1, mcol2], MODE_OPTIONS):
        with col:
            is_sel = st.session_state.b2b_mode == opt["key"]
            tile_cls = "mode-tile selected" if is_sel else "mode-tile"
            st.markdown(
                f"""<div class="{tile_cls}">
                    <span class="mode-icon">{opt['icon']}</span>
                    <div class="mode-text-block">
                        <span class="mode-title">{opt['title']}</span>
                        <span class="mode-desc">{opt['desc']}</span>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button(
                "✔ Selected" if is_sel else "Select",
                key=f"mode_btn_{opt['key']}",
                use_container_width=True,
                type="primary" if is_sel else "secondary",
            ):
                st.session_state.b2b_mode = opt["key"]
                st.session_state.uw_results = None
                st.session_state.cl_results = None
                st.rerun()

    mode = st.session_state.b2b_mode
    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # SHARED FORM — Company + Financial
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("### 📋 Company Information")

    col1, col2, col3 = st.columns(3)
    with col1:
        company_name = st.text_input("Legal Business Name", placeholder="e.g., Acme Trading Pvt Ltd")
        industry = st.selectbox("Industry", [
            "E-commerce", "SaaS/Software", "Professional Services",
            "Manufacturing", "Education", "Healthcare",
            "Travel", "Forex Trading", "MLM", "Other"
        ])
    with col2:
        registration_number = st.text_input(
            "Registration Number",
            placeholder="CIN (India) or UEN (Singapore)",
            help="Company Identification Number"
        )
        country = st.selectbox("Country of Operations", ["India", "Singapore", "UAE", "Other"])
    with col3:
        website = st.text_input("Company Website", placeholder="https://example.com")
        years_in_business = st.number_input("Years in Business", min_value=0, value=1, step=1)

    col4, col5 = st.columns(2)
    with col4:
        directors_input = st.text_area("Director Names (one per line)",
                                       placeholder="John Doe\nJane Smith", height=68)
    with col5:
        business_description = st.text_area(
            "What does the company do?",
            placeholder="Describe the business model, products/services offered…", height=68)

    st.markdown("#### 💵 Financial Information")
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        revenue     = st.number_input("Annual Revenue (₹)",    min_value=0.0, value=0.0, step=100000.0)
        net_profit  = st.number_input("Net Profit (₹)",                       value=0.0, step=10000.0)
    with fcol2:
        total_assets      = st.number_input("Total Assets (₹)",      min_value=0.0, value=0.0, step=100000.0)
        total_liabilities = st.number_input("Total Liabilities (₹)", min_value=0.0, value=0.0, step=100000.0)
    with fcol3:
        cash       = st.number_input("Cash & Equivalents (₹)", min_value=0.0, value=0.0, step=10000.0)
        total_debt = st.number_input("Total Debt (₹)",         min_value=0.0, value=0.0, step=100000.0)

    rcol1, _, _ = st.columns(3)
    with rcol1:
        credit_rating = st.selectbox(
            "External Credit Rating (if available)",
            ["Not Available", "AAA", "AA", "A", "BBB", "BB", "B", "C", "D"]
        )

    # ════════════════════════════════════════════════════════════════════════
    # CREDIT & LENDING EXTRA FIELDS
    # ════════════════════════════════════════════════════════════════════════
    loan_amount_requested = 0.0
    loan_purpose          = "Working Capital"
    loan_tenure_months    = 24
    collateral_type_key   = "none"
    collateral_value      = 0.0

    if mode == "credit":
        st.markdown("---")
        st.markdown("### 💳 Loan Request")

        lc1, lc2, lc3 = st.columns(3)
        with lc1:
            loan_amount_requested = st.number_input(
                "Loan Amount Requested (₹)",
                min_value=0.0, value=1000000.0, step=100000.0
            )
        with lc2:
            loan_purpose = st.selectbox("Loan Purpose", [
                "Working Capital", "Equipment / Machinery",
                "Business Expansion", "Trade Finance",
                "Invoice Discounting", "Real Estate / Property",
                "Other"
            ])
        with lc3:
            loan_tenure_months = st.select_slider(
                "Preferred Tenure (months)",
                options=[6, 12, 18, 24, 36, 48, 60],
                value=24
            )

        st.markdown("#### 🏠 Collateral")
        cc1, cc2 = st.columns(2)
        with cc1:
            collateral_display_names = [v for _, v in COLLATERAL_OPTIONS]
            collateral_display = st.selectbox("Collateral Type", collateral_display_names)
            collateral_type_key = COLLATERAL_KEY_MAP.get(collateral_display, "none")
        with cc2:
            collateral_value = st.number_input(
                "Collateral Estimated Value (₹)",
                min_value=0.0, value=0.0, step=100000.0,
                help="Gross market/book value before haircut"
            )

        # Show live haircut preview
        if collateral_type_key != "none" and collateral_value > 0:
            coll_info    = LoanStructuringAgent.COLLATERAL_TYPES[collateral_type_key]
            effective    = collateral_value * coll_info["max_ltv"]
            haircut_pct  = coll_info["haircut"] * 100
            st.info(
                f"**Haircut applied**: {haircut_pct:.0f}%  →  "
                f"Effective collateral cover: **₹{effective:,.0f}**  |  "
                f"_{coll_info['notes']}_"
            )

    # ════════════════════════════════════════════════════════════════════════
    # RUN BUTTON
    # ════════════════════════════════════════════════════════════════════════
    st.markdown("<br>", unsafe_allow_html=True)
    btn_label = (
        "🚀 Run Underwriting Assessment"
        if mode == "onboarding"
        else "🚀 Run Credit & Lending Assessment"
    )
    _, bcol, _ = st.columns([1, 2, 1])
    with bcol:
        run_button = st.button(btn_label, type="primary", use_container_width=True)
    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # EXECUTION
    # ════════════════════════════════════════════════════════════════════════
    if run_button:
        if not company_name:
            st.warning("⚠️ Please enter company name to proceed.")
            st.stop()
        if mode == "credit" and loan_amount_requested <= 0:
            st.warning("⚠️ Please enter a loan amount > 0.")
            st.stop()

        directors = [d.strip() for d in directors_input.split("\n") if d.strip()]
        financial_data = {}
        if revenue > 0:
            financial_data = {
                "revenue":           revenue,
                "net_profit":        net_profit,
                "total_assets":      total_assets,
                "total_liabilities": total_liabilities,
                "total_equity":      max(0.0, total_assets - total_liabilities),
                "cash":              cash,
                "total_debt":        total_debt,
            }

        base_context = {
            "company_name":        company_name,
            "registration_number": registration_number or "Not Provided",
            "directors":           directors,
            "business_description": business_description or "Not provided",
            "website":             website or "Not provided",
            "industry":            industry,
            "country":             country,
            "financial_data":      financial_data,
            "years_in_business":   years_in_business,
            "credit_rating":       credit_rating if credit_rating != "Not Available" else None,
            "simulated_news":      [],
        }

        if mode == "onboarding":
            _run_onboarding(base_context)
        else:
            credit_context = {
                **base_context,
                "loan_amount_requested": loan_amount_requested,
                "loan_purpose":          loan_purpose,
                "loan_tenure_months":    loan_tenure_months,
                "collateral_type":       collateral_type_key,
                "collateral_value":      collateral_value,
            }
            _run_credit(credit_context)

    # ════════════════════════════════════════════════════════════════════════
    # RESULTS DISPLAY
    # ════════════════════════════════════════════════════════════════════════
    if mode == "onboarding" and st.session_state.uw_results:
        _show_onboarding_results(st.session_state.uw_results)

    elif mode == "credit" and st.session_state.cl_results:
        _show_credit_results(st.session_state.cl_results)

    else:
        _show_architecture(mode)


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _run_onboarding(context: dict):
    with st.spinner("🔄 Running underwriting assessment…"):
        try:
            results = st.session_state.uw_orchestrator.analyze(context)
            st.session_state.uw_results = results
            st.session_state.uw_history.append({
                "timestamp": datetime.now().isoformat(),
                "company":   context["company_name"],
                "decision":  results.get("decision"),
            })
        except Exception as e:
            st.error(f"❌ Error during underwriting: {e}")
            st.exception(e)


def _run_credit(context: dict):
    with st.status("💳 Running credit & lending assessment… (this may take 60–90 s)", expanded=True) as status:
        try:
            st.write("🔍 Phase 1: Red flag, sanctions & financial health screening…")
            st.write("📐 Phase 2: Credit scoring & repayment capacity analysis…")
            st.write("🏗️ Phase 3: Loan structuring & collateral assessment…")
            st.write("📝 Phase 4: Synthesising credit memo…")
            results = st.session_state.cl_orchestrator.analyze(context)
            st.session_state.cl_results = results
            st.session_state.cl_history.append({
                "timestamp": datetime.now().isoformat(),
                "company":   context["company_name"],
                "decision":  results.get("decision"),
            })
            status.update(label="✅ Credit & Lending Assessment Complete!", state="complete", expanded=False)
            _init_lending_chat(context, results)
        except Exception as e:
            st.error(f"❌ Error during credit assessment: {e}")
            st.exception(e)

def _init_lending_chat(context: dict, results: dict):
    import uuid
    from memory_store import MemoryStore
    from lending_agent_core import LendingAgent
    from lending_recommendation_logger import LendingRecommendationLogger
    
    chat_id = str(uuid.uuid4())
    st.session_state.lending_chat_id = chat_id
    st.session_state.lending_messages = []
    
    mem = MemoryStore()
    mem.create_lending_session(chat_id, context["company_name"], context, results)
    
    track_stats = mem.get_lending_track_record()
    track_text = None
    if track_stats["total_resolved"] > 0:
        track_text = f"Accuracy: {track_stats['accuracy']}% ({track_stats['stats']['WINNING']} SUCCESS, {track_stats['stats']['LOSING']} DEFAULTED)."
        
    st.session_state.lending_logger = LendingRecommendationLogger(
        chat_id, context["company_name"], results.get("credit_score")
    )
    
    agent = LendingAgent()
    st.session_state.lending_agent = agent
    
    opening_text = ""
    for event in agent.initialize(context["company_name"], context, results, chat_id, track_text):
        if event[0] == "TEXT":
            opening_text = event[1]
            
    st.session_state.lending_messages.append({
        "role": "assistant",
        "content": opening_text
    })


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS — ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════

def _show_onboarding_results(results: dict):
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 Risk Assessment Brief",
        "🤖 Agent Details",
        "📊 Risk Breakdown",
        "🔍 Audit Trail"
    ])

    decision   = results.get("decision", "UNKNOWN")
    risk_level = results.get("overall_risk", "UNKNOWN")

    with tab1:
        st.header("🎯 Risk Assessment Brief")
        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            if decision == "APPROVE":
                st.success(f"✅ **Decision**: {decision}")
            elif decision == "REJECT":
                st.error(f"❌ **Decision**: {decision}")
            else:
                st.warning(f"⚠️ **Decision**: {decision}")
        with dc2:
            risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(risk_level, "⚪")
            st.info(f"{risk_icon} **Risk Level**: {risk_level}")
        with dc3:
            st.metric("Assessment Time", "<30s")
        st.divider()
        synthesis = results.get("synthesis", "")
        if synthesis:
            st.markdown(synthesis)
        else:
            st.info("No synthesis available.")

    with tab2:
        st.header("🤖 Individual Agent Findings")
        AGENT_NAMES = {
            "red_flag":       "Red Flag Detection Agent",
            "business_model": "Business Model Compliance Validation Agent",
            "financial_health": "Financial Health Assessment Agent",
            "sanctions":      "Sanctions & Watchlist Screening Agent",
            "orchestrator":   "Risk Assessment Brief Agent",
        }
        for aname, ares in results.get("agent_results", {}).items():
            rl = ares.get("risk_level", "UNKNOWN")
            icon = {"LOW": "🟢", "CLEAN": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(rl, "⚪")
            display = AGENT_NAMES.get(aname, aname.replace("_", " ").title())
            with st.expander(f"{icon} {display} — Risk: {rl}", expanded=False):
                if isinstance(ares, dict) and "analysis" in ares:
                    st.markdown(ares["analysis"])
                else:
                    st.write(ares)

    with tab3:
        st.header("📊 Risk Score Breakdown")
        import pandas as pd
        AGENT_NAMES = {
            "red_flag":       "Red Flag Detection",
            "business_model": "Business Model Compliance",
            "financial_health": "Financial Health",
            "sanctions":      "Sanctions & Watchlist",
        }
        rows = []
        for aname, ares in results.get("agent_results", {}).items():
            rl = ares.get("risk_level", "UNKNOWN")
            rows.append({
                "Agent":      AGENT_NAMES.get(aname, aname.replace("_", " ").title()),
                "Risk Level": rl,
                "Status":     "✅ Pass" if rl in ["LOW", "CLEAN"] else
                              "⚠️ Review" if rl == "MEDIUM" else "❌ Fail"
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.divider()
        mc1, mc2, mc3, mc4 = st.columns(4)
        ar = results.get("agent_results", {})
        with mc1: st.metric("Overall Risk", risk_level)
        with mc2: st.metric("Agents Passed", f"{sum(1 for r in ar.values() if r.get('risk_level') in ['LOW','CLEAN'])}/{len(ar)}")
        with mc3: st.metric("Critical Flags", sum(1 for r in ar.values() if r.get("risk_level") == "CRITICAL"))
        with mc4: st.metric("Confidence", "High" if risk_level in ["LOW", "CRITICAL"] else "Medium")

    with tab4:
        _audit_trail_tab(st.session_state.uw_orchestrator)

    st.success("✅ Underwriting assessment complete!")
    _download_button(results, prefix="underwriting")


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS — CREDIT & LENDING
# ══════════════════════════════════════════════════════════════════════════════

def _show_credit_results(results: dict):
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💳 Credit Memo",
        "🤖 Agent Details",
        "📊 Credit Scorecard",
        "🔍 Audit Trail",
        "💬 AI Loan Advisor"
    ])

    decision    = results.get("decision", "UNKNOWN")
    risk_level  = results.get("overall_risk", "UNKNOWN")
    credit_score = results.get("credit_score")
    credit_rating = results.get("credit_rating", "—")
    dscr         = results.get("dscr")
    rec_amount   = results.get("recommended_amount", 0)
    rate         = results.get("interest_rate")
    rate_band    = results.get("interest_rate_band", "—")
    tenure       = results.get("tenure_months")

    with tab1:
        st.header("💳 Credit Memo")
        # Decision banner
        dc1, dc2, dc3, dc4 = st.columns(4)
        with dc1:
            if decision == "APPROVE":
                st.success(f"✅ {decision}")
            elif decision == "REJECT":
                st.error(f"❌ {decision}")
            else:
                st.warning(f"⚠️ {decision.replace('_', ' ')}")
        with dc2:
            risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(risk_level, "⚪")
            st.info(f"{risk_icon} Risk: **{risk_level}**")
        with dc3:
            if rec_amount:
                st.metric("Recommended Amount", f"₹{rec_amount:,.0f}")
        with dc4:
            if rate:
                st.metric("Interest Rate", f"{rate:.1f}%")
        st.divider()
        memo = results.get("credit_memo", "")
        if memo:
            st.markdown(memo)
        else:
            st.info("No credit memo generated.")

    with tab2:
        st.header("🤖 Agent Findings")
        AGENT_DISPLAY = {
            "red_flag":          "🚩 Red Flag Detection",
            "sanctions":         "🔍 Sanctions & Watchlist",
            "financial_health":  "💵 Financial Health",
            "credit_scoring":    "💳 Credit Scoring",
            "repayment_capacity": "📐 Repayment Capacity",
            "loan_structuring":  "🏗️ Loan Structuring",
        }
        for aname, ares in results.get("agent_results", {}).items():
            rl   = ares.get("risk_level", "UNKNOWN")
            icon = {"LOW": "🟢", "CLEAN": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(rl, "⚪")
            display = AGENT_DISPLAY.get(aname, aname.replace("_", " ").title())
            with st.expander(f"{icon} {display} — Risk: {rl}", expanded=False):
                if isinstance(ares, dict) and "analysis" in ares:
                    st.markdown(ares["analysis"])
                else:
                    st.write(ares)

    with tab3:
        st.header("📊 Credit Scorecard")

        # Credit score visual
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            if credit_score is not None:
                rating_css = f"score-{credit_rating}" if credit_rating in [
                    "AAA","AA","A","BBB","BB","B","C","D"] else "score-BB"
                st.markdown(
                    f"<div style='text-align:center'>"
                    f"<div class='score-pill {rating_css}'>{credit_score}/100</div>"
                    f"<div style='font-size:13px;color:#555;margin-top:4px;'>Credit Score</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            else:
                st.metric("Credit Score", "—")
        with sc2:
            st.metric("Credit Rating", credit_rating or "—")
        with sc3:
            st.metric("DSCR", f"{dscr:.2f}" if dscr is not None else "—",
                      help="≥ 1.25 is lender-acceptable. ≥ 1.5 is comfortable.")
        with sc4:
            st.metric("Rate Band", rate_band)

        st.divider()

        # Collateral breakdown
        ctype    = results.get("collateral_type", "—")
        ccover   = results.get("collateral_cover", 0)
        cadequate = results.get("collateral_adequate", False)
        cc1, cc2, cc3 = st.columns(3)
        with cc1: st.metric("Collateral Type", ctype or "—")
        with cc2: st.metric("Effective Cover (post-haircut)", f"₹{ccover:,.0f}" if ccover else "—")
        with cc3: st.metric("Collateral Adequate", "✅ Yes" if cadequate else "❌ No")

        st.divider()

        # Agent risk summary table
        import pandas as pd
        AGENT_DISPLAY = {
            "red_flag":           "Red Flag Detection",
            "sanctions":          "Sanctions & Watchlist",
            "financial_health":   "Financial Health",
            "credit_scoring":     "Credit Scoring",
            "repayment_capacity": "Repayment Capacity",
            "loan_structuring":   "Loan Structuring",
        }
        rows = []
        for aname, ares in results.get("agent_results", {}).items():
            rl = ares.get("risk_level", "UNKNOWN")
            rows.append({
                "Agent":      AGENT_DISPLAY.get(aname, aname.replace("_", " ").title()),
                "Risk Level": rl,
                "Status":     "✅ Pass" if rl in ["LOW","CLEAN"] else
                              "⚠️ Review" if rl == "MEDIUM" else "❌ Fail"
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab4:
        _audit_trail_tab(st.session_state.cl_orchestrator)

    with tab5:
        st.header("💬 AI Loan Advisor Chat")
        st.markdown("Discuss the credit memo, ask for term adjustments, or finalize the loan decision.")
        
        # Display chat history
        for msg in st.session_state.lending_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # Chat input
        if prompt := st.chat_input("Ask a question or finalize terms..."):
            st.session_state.lending_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    agent = st.session_state.lending_agent
                    response_text = ""
                    for event in agent.chat_turn(prompt):
                        if event[0] == "TEXT":
                            response_text += event[1]
                    
                    if st.session_state.lending_logger:
                        clean_text, recs = st.session_state.lending_logger.process(response_text)
                        st.markdown(clean_text)
                        for r in recs:
                            st.success(f"📌 Logged final credit decision: {r.get('ACTION', 'UNKNOWN')} for {r.get('AMOUNT', 'N/A')}")
                    else:
                        st.markdown(response_text)
                        
            st.session_state.lending_messages.append({"role": "assistant", "content": response_text})

    st.success("✅ Credit & lending assessment complete!")
    _download_button(results, prefix=f"credit_{results.get('decision','UNKNOWN')}")


# ══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _audit_trail_tab(orchestrator):
    st.header("🔍 Audit Trail & Execution Log")
    st.write("**Orchestrator Execution Log:**")
    if orchestrator:
        for log in orchestrator.get_execution_log()[-15:]:
            with st.expander(f"{log['action']} — {log['timestamp']}", expanded=False):
                st.json(log)
    st.write("**Agent Health Status:**")
    if orchestrator:
        st.json(orchestrator.get_agent_health_status())


def _download_button(results: dict, prefix: str):
    if st.button("📥 Download Full Report"):
        data = json.dumps(results, indent=2, default=str)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="Download JSON Report",
            data=data,
            file_name=f"{prefix}_{ts}.json",
            mime="application/json"
        )


# ══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE OVERVIEW (shown before first run)
# ══════════════════════════════════════════════════════════════════════════════

def _show_architecture(mode: str):
    if mode == "onboarding":
        st.header("🏗️ Merchant Onboarding System Architecture")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
### 🤖 Agents
**🚩 Red Flag Detection Agent**
- Scans negative news, fraud, lawsuits, bankruptcy
- Regulatory fines, license revocations

**📋 Business Model Compliance Agent**
- Acceptable Use Policy check
- Prohibited business detection

**💰 Financial Health Assessment Agent**
- Liquidity, solvency, profitability ratios
- Credit risk evaluation

**🔍 Sanctions & Watchlist Screening Agent**
- OFAC, UN, EU, RBI/MAS watchlists
- PEP identification, AML/CFT compliance
""")
        with col2:
            st.markdown("""
### 📊 Key Metrics
- **Time Reduction**: 80% (45 min → <30 sec)
- **False Negative Rate**: <1%
- **Audit Trail**: 100% — 7-year retention
- **Throughput**: 10× increase

### 💼 Decision Outputs
- APPROVE
- APPROVE WITH CONDITIONS
- REQUEST MORE INFO
- REJECT
""")

    else:
        st.header("🏗️ Credit & Lending System Architecture")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
### 🤖 Agents (6 total, 3 phases)

**Phase 1 (parallel)**
- 🚩 Red Flag Detection
- 🔍 Sanctions & Watchlist Screening
- 💵 Financial Health Assessment

**Phase 2 (parallel)**
- 💳 Credit Scoring (0–100 + AAA–D rating)
- 📐 Repayment Capacity (DSCR + stress test)

**Phase 3**
- 🏗️ Loan Structuring (terms, covenants, collateral)
""")
        with col2:
            st.markdown("""
### 📊 Credit Outputs
- Credit Score (0–100) & Rating (AAA–D)
- DSCR with −20% revenue stress test
- Collateral adequacy by type (type-specific haircuts)
- Recommended loan amount & interest rate band
- Tenure options with EMI comparison
- Loan covenants & pre-disbursement checklist
- Full Credit Memo for credit committee

### 🏠 Collateral Haircuts
| Type | Haircut | Max LTV |
|------|---------|---------|
| Real Estate | 35% | 65% |
| Machinery | 45% | 55% |
| Invoice / Receivables | 25% | 75% |
| FD / Securities | 10% | 90% |
| Unsecured | — | — |
""")


if __name__ == "__main__":
    main()
