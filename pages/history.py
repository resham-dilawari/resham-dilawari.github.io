import streamlit as st
import os
from memory_store import MemoryStore
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="History & Feedback", page_icon="📋", layout="wide")

if "user_name" not in st.session_state or not st.session_state.user_name:
    st.warning("Please log in from the main Chat page first.")
    st.stop()

user_id = st.session_state.session_id # session_id acts as user_id in our schema
mem = MemoryStore()

st.title(f"📋 {st.session_state.user_name}'s Portfolio History")

# Top stats
stats = mem.get_user_track_record(user_id)
acc = stats['accuracy']
cols = st.columns(4)
cols[0].metric("Accuracy", f"{acc}%")
cols[1].metric("Winning Calls", stats['stats']['WINNING'])
cols[2].metric("Losing Calls", stats['stats']['LOSING'])
cols[3].metric("Pending/Open", stats['stats']['PENDING'])

st.divider()

# Get all chat sessions
chats = mem.get_user_chat_sessions(user_id)
if not chats:
    st.info("No past chats found.")
    st.stop()

st.markdown("### Past Sessions")

for chat in chats:
    dt = datetime.fromisoformat(chat['started_at']).strftime("%d %b %Y, %I:%M %p")
    
    with st.expander(f"💬 Chat from {dt}", expanded=False):
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
                # Feedback form
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
