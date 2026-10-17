"""Streamlit chat UI for the AI Advisor (Person E).

Run:  uv run streamlit run app.py

Spec req 1 (UI) + req 6 (conversation state across turns). The sidebar selects
the demo student persona (login is assumed per the spec's assumptions).
"""

import streamlit as st

from advisor import db, orchestrator

st.set_page_config(page_title="AI Academic Advisor", page_icon="🎓")
st.title("AI Academic Advisor")


@st.cache_resource
def _init():
    db.init_db()
    return True


_init()

students = {s["student_id"]: s for s in db.query("SELECT * FROM students")}

with st.sidebar:
    st.header("Student")
    student_id = st.selectbox(
        "Logged in as",
        options=list(students) or ["(no students — run seed)"],
        format_func=lambda sid: students.get(sid, {}).get("name", sid),
    )
    program = students.get(student_id, {}).get("program_id", "?")
    st.caption(f"Program: `{program}`")
    if st.button("Clear conversation"):
        st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant",
         "content": "Hi! I can generate degree plans, answer questions about "
                    "courses and requirements, and help with plan changes. "
                    "What can I do for you?"}
    ]

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask your advisor..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = orchestrator.handle_message(student_id, prompt, st.session_state.messages)
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
