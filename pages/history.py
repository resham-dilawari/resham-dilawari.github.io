import streamlit as st
import os
from memory_store import MemoryStore
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="History & Feedback", page_icon="📋", layout="wide")

st.title("📋 Platform History & Feedback")

tab_wealth, tab_lending = st.tabs(["📈 Wealth Advisor", "🏦 Lending Advisor"])

mem = MemoryStore()

# ──────────────────────────────────────────────────────────────────────────────
# WEALTH ADVISOR HISTORY
# ──────────────────────────────────────────────────────────────────────────────
with tab_wealth:
    if "user_name" not in st.session_state or not st.session_state.user_name:
        st.warning("Please log in from the main Chat page to view Wealth history.")
    else:
        user_id = st.session_state.session_id # session_id acts as user_id in our schema
        st.subheader(f"{st.session_state.user_name}'s Portfolio History")
        
        stats = mem.get_user_track_record(user_id)
        acc = stats['accuracy']
        cols = st.columns(4)
        cols[0].metric("Accuracy", f"{acc}%")
        cols[1].metric("Winning Calls", stats['stats']['WINNING'])
        cols[2].metric("Losing Calls", stats['stats']['LOSING'])
        cols[3].metric("Pending/Open", stats['stats']['PENDING'])

        st.divider()

        chats = mem.get_user_chat_sessions(user_id)
        if not chats:
            st.info("No past wealth sessions found.")
        else:
            for chat in chats:
                dt = datetime.fromisoformat(chat['started_at']).strftime("%d %b %Y, %I:%M %p")
                
                with st.expander(f"💬 Session from {dt}", expanded=False):
                    st.markdown(f"**Portfolio:** {chat['tickers']} | **Corpus:** ₹{chat['corpus']:,.0f}")
                    
                    recs = mem.get_chat_recommendations(chat['chat_id'])
                    if not recs:
                        st.write("_No recommendations made in this session._")
                        continue
                        
                    for rec in recs:
                        action = rec['action'].upper()
                        emoji = {"BUY": "🟢", "INVEST": "🟢", "ACCUMULATE": "🟢",
                                 "HOLD": "🟡", "SELL": "🔴", "DIVEST": "🔴",
                                 "REDUCE": "🟠", "AVOID": "⚫"}.get(action, "📌")
                        
                        perf = rec['performance']
                        perf_emoji = "✅" if perf == "WINNING" else "❌" if perf == "LOSING" else "⏳" if perf == "PENDING" else "➖"
                        
                        st.markdown(f"#### {emoji} {action} {rec['ticker']}")
                        c1, c2 = st.columns([2, 1])
                        with c1:
                            st.markdown(f"**Noted:** ₹{rec['price_noted']} ➔ **Current:** ₹{rec['current_price']} ({rec['price_change_pct']:+.2f}%) {perf_emoji} **{perf}**")
                            st.markdown(f"**Rationale:** {rec['rationale']}")
                            if rec.get('agent_analysis'):
                                st.info(f"**Agent Self-Analysis:**\n{rec['agent_analysis']}")
                        
                        with c2:
                            latest_fb = rec.get("latest_feedback")
                            st.markdown("**Your Feedback:**")
                            if latest_fb:
                                st.success(f"Rated: {latest_fb}")
                            
                            with st.form(key=f"fb_{rec['id']}"):
                                rating = st.radio("Rate this call:", ["GOOD", "BAD", "PARTIAL"], horizontal=True, label_visibility="collapsed")
                                note = st.text_input("Note (optional)")
                                if st.form_submit_button("Submit"):
                                    mem.add_feedback(rec['id'], user_id, rating, note)
                                    st.rerun()
                        st.markdown("---")

# ──────────────────────────────────────────────────────────────────────────────
# LENDING ADVISOR HISTORY
# ──────────────────────────────────────────────────────────────────────────────
with tab_lending:
    st.subheader("B2B Credit & Lending History")
    
    l_stats = mem.get_lending_track_record()
    l_acc = l_stats['accuracy']
    l_cols = st.columns(4)
    l_cols[0].metric("Accuracy", f"{l_acc}%")
    l_cols[1].metric("Success (Winning)", l_stats['stats']['WINNING'])
    l_cols[2].metric("Defaulted (Losing)", l_stats['stats']['LOSING'])
    l_cols[3].metric("Pending/Open", l_stats['stats']['PENDING'])
    
    st.divider()
    
    l_chats = mem.get_all_lending_sessions()
    if not l_chats:
        st.info("No past lending sessions found.")
    else:
        for chat in l_chats:
            dt = datetime.fromisoformat(chat['started_at']).strftime("%d %b %Y, %I:%M %p")
            
            with st.expander(f"🏦 {chat['merchant_name']} — {dt}", expanded=False):
                st.markdown(f"**Industry:** {chat['industry']} | **Revenue:** ₹{chat['revenue']:,.0f}")
                
                recs = mem.get_lending_recommendations(chat['chat_id'])
                if not recs:
                    st.write("_No credit decisions finalized._")
                    continue
                    
                for rec in recs:
                    decision = str(rec['decision']).upper()
                    emoji = "✅" if decision == "APPROVE" else "❌" if decision == "REJECT" else "⚠️"
                    perf = rec['performance']
                    perf_emoji = "🎉" if perf == "WINNING" else "💀" if perf == "LOSING" else "⏳" if perf == "PENDING" else "➖"
                    
                    st.markdown(f"#### {emoji} {decision} — {chat['merchant_name']}")
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.markdown(f"**Amount:** ₹{rec['rec_amount']:,.0f} @ {rec['interest_rate']}%")
                        st.markdown(f"**Orig Score:** {rec['credit_score']} ➔ **Current:** {rec['current_credit_score']} {perf_emoji} **{perf}**")
                        st.markdown(f"**Rationale:** {rec['rationale']}")
                        if rec.get('agent_analysis'):
                            st.info(f"**Agent Self-Analysis:**\n{rec['agent_analysis']}")
                    
                    with c2:
                        latest_fb = rec.get("latest_feedback")
                        st.markdown("**Manual Update / Feedback:**")
                        if latest_fb:
                            st.success(f"Rated: {latest_fb}")
                        
                        with st.form(key=f"lfb_{rec['id']}"):
                            rating = st.radio("Loan Status:", ["GOOD", "BAD", "PARTIAL"], horizontal=True, label_visibility="collapsed", help="GOOD=Repaid/Performing, BAD=Defaulted/NPA")
                            note = st.text_input("Note (optional)", key=f"lnote_{rec['id']}")
                            if st.form_submit_button("Submit Update"):
                                mem.add_lending_feedback(rec['id'], rating, note)
                                st.rerun()
                    st.markdown("---")
