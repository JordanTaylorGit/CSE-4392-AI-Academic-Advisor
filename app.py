"""Streamlit web UI for the AI Advisor (Person E).

Run:  uv run streamlit run app.py

Spec coverage:
  req 1   web-based UI
  req 2   Plan section (generate multi-year plan, optional summer)
  req 3   Ask section (prompt-based queries) + Add/Drop dialog boxes
  req 4   Check a course section (six verification checks)
  req 5c  Switch major section (new plan + comparison with the existing plan)
  req 6   per-student conversation state across turns

The top bar selects the student (login is assumed per the spec). All backend
calls except chat go through ui/services.py; all styling is in ui/theme.py.
"""

import json
import time
import uuid

import streamlit as st

from advisor import db, planner, tracing
from ui import components as ui
from ui import services as svc
from ui import theme

st.set_page_config(page_title="Advisor", page_icon="🎓", layout="wide",
                   initial_sidebar_state="collapsed")
theme.apply()


@st.cache_resource
def _init():
    db.init_db()
    return True


_init()

STUDENTS = svc.students()
PROGRAMS = svc.programs()
COURSES = svc.courses()
TERMS = svc.terms()
SECTIONS = ["Plan", "Ask", "Check a course", "Switch major"]
SUGGESTIONS = [
    "Build my degree plan",
    "What are the prerequisites for CSE 3310?",
    "Which courses cover machine learning?",
    "Can I take CSE 4344 next semester?",
]

ss = st.session_state
ss.setdefault("messages", {})   # student_id -> chat messages
ss.setdefault("plans", {})      # student_id -> current plan dict
ss.setdefault("sources", {})    # student_id -> "live" | "preview"
ss.setdefault("undo", {})       # student_id -> (label, previous plan) for the last add/drop
ss.setdefault("trace_session", f"ui-{uuid.uuid4().hex[:8]}")
tracing.set_session(ss.trace_session)  # tag this run's trace records with the session

if not STUDENTS:
    ui.note("There are no students in the database. Run <code>uv run python -m advisor.db</code> "
            "to load the sample data, then reload this page.", kind="caution")
    st.stop()


def program_name(pid: str) -> str:
    return PROGRAMS.get(pid, {}).get("name", pid)


def course_label(cid: str) -> str:
    c = COURSES.get(cid)
    return f"{cid} — {ui.course_title(c['title'])}" if c else cid


# ------------------------------------------------------------------ top bar

with st.container(key="topbar"):
    c_brand, c_nav, c_student, c_more = st.columns([1.1, 3.4, 1.7, 0.75],
                                                   vertical_alignment="center")
    with c_brand:
        ui.wordmark()
    with c_nav:
        sections = SECTIONS + (["Traces"] if ss.get("show_traces") else [])
        if ss.get("section") not in sections:
            ss["section"] = "Plan"  # no default=: "Open in Plan" also sets it from code
        section = st.segmented_control("Section", sections, key="section",
                                       label_visibility="collapsed") or ss.get("last_section", "Plan")
        ss.last_section = section
    with c_student:
        student_id = st.selectbox("Student", list(STUDENTS), key="student",
                                  format_func=lambda sid: STUDENTS[sid]["name"],
                                  label_visibility="collapsed")
    student = STUDENTS[student_id]
    done = svc.completed_courses(student_id)
    with c_more:
        with st.popover("More", help="Transcript and options"):
            st.markdown(f"**{student['name']}**")
            st.caption(f"{program_name(student['program_id'])} · up to "
                       f"{student['max_credits_per_semester']} credits per semester")
            st.markdown("**Transcript**")
            ui.transcript(done)
            st.download_button(
                "Download transcript (.csv)", width="stretch",
                data=svc.transcript_csv(student_id),
                file_name=f"transcript_{student['name'].replace(' ', '_')}.csv",
                mime="text/csv",
                on_click=lambda: tracing.trace("ui_action", student_id=student_id,
                                               action="download_transcript", source="live"))
            if st.button("Clear the conversation", width="stretch"):
                ss.messages.pop(student_id, None)
                st.rerun()
            st.divider()
            st.caption("For the project team")
            st.toggle("Use preview data", key="use_preview",
                      help="While the planner is still a stub, show placeholder plans so the UI "
                           "can be tested. Real results replace it automatically once implemented.")
            st.toggle("Show execution traces", key="show_traces",
                      help="Adds a Traces section: every chat turn and action, step by step.")

use_preview = ss.get("use_preview", False)
plan = ss.plans.get(student_id)


def set_plan(new_plan: dict, source: str, done_msg: str | None = None) -> None:
    """Store the student's plan. With done_msg, confirm the change and allow undo."""
    if done_msg:
        ss.undo[student_id] = (done_msg, ss.plans.get(student_id))
        ss["toast"] = done_msg
    else:
        ss.undo.pop(student_id, None)
    ss.plans[student_id] = new_plan
    ss.sources[student_id] = source


if msg := ss.pop("toast", None):
    st.toast(msg)


def type_out(text: str):
    """Yield a reply word by word so it types out like a live answer, finishing in
    about a second however long it is (HIG motion.md: brief, never make people wait)."""
    words = text.split(" ")
    step = max(1, len(words) // 60)
    for i in range(0, len(words), step):
        yield " ".join(words[i:i + step]) + " "
        time.sleep(0.016)


def not_ready(e: Exception) -> None:
    ui.note(f"This part of the advisor isn't built yet: <code>{e}</code><br>"
            "To test this screen, open <b>More</b> and turn on <b>Use preview data</b>.")


# ------------------------------------------------------------ add/drop dialogs

@st.dialog("Add a course", width="large")
def add_dialog():
    in_plan = {c["course_id"] for s in plan["semesters"] for c in s["courses"]}
    taken = {r["course_id"] for r in done}
    options = [c for c in COURSES if c not in in_plan and c not in taken]
    c1, c2 = st.columns([3, 1.3])
    cid = c1.selectbox("Course", options, format_func=course_label)
    terms = sorted({s["term"] for s in plan["semesters"]} | set(TERMS), key=planner.term_key)
    term = c2.selectbox("Semester", terms, format_func=ui.term_label)
    try:
        checks, source = svc.verify_course(student_id, cid, term, plan, use_preview)
    except svc.NotReady as e:
        not_ready(e)
        return
    ui.preview_banner(source)
    ui.checks_table(checks)
    if st.button("Add course", type="primary",
                 disabled=any(c["passed"] is False for c in checks)):
        try:
            new, source = svc.add_course(plan, cid, term, use_preview)
        except svc.NotReady as e:
            not_ready(e)
            return
        set_plan(new, source, f"Added {cid} to {ui.term_label(term)}")
        st.rerun()


@st.dialog("Drop a course")
def drop_dialog():
    entries = [(s["term"], c["course_id"]) for s in plan["semesters"] for c in s["courses"]]
    term, cid = st.selectbox(
        "Course", entries, format_func=lambda e: f"{ui.term_label(e[0])}: {course_label(e[1])}")
    if st.button("Drop course", type="primary"):
        try:
            new, source = svc.drop_course(plan, cid, term, use_preview)
        except svc.NotReady as e:
            not_ready(e)
            return
        set_plan(new, source, f"Dropped {cid} from {ui.term_label(term)}")
        st.rerun()


# --------------------------------------------------------------------- hero

shown_program = plan["program_id"] if plan else student["program_id"]
program_line = program_name(shown_program)
if shown_program != student["program_id"]:
    program_line += f" (exploring a switch from {program_name(student['program_id'])})"
ui.hero(student, program_line, done, plan,
        PROGRAMS.get(shown_program, {}).get("total_credits", 120))

# ----------------------------------------------------------------- sections

if section == "Plan":
    with st.container(key="card_plan"):
        st.markdown("### Degree plan")
        st.caption("Every semester from now until graduation, checked against your degree "
                   "requirements.")
        c1, c2, c3 = st.columns([2.2, 2, 1.1], vertical_alignment="bottom")
        program_id = c1.selectbox("Program", list(PROGRAMS), format_func=program_name,
                                  index=list(PROGRAMS).index(student["program_id"]))
        load = c2.segmented_control("Courses per semester", ["Auto", 3, 4, 5, 6],
                                    default="Auto", key="load")
        summer = c3.toggle("Summer terms", value=False)
        a1, a2, a3, a4, _ = st.columns([1.1, 1.15, 1.15, 1.5, 1.6])
        if a1.button("Build plan", type="primary", width="stretch"):
            try:
                new, source = svc.generate_plan(student_id, program_id, summer,
                                                None if load in (None, "Auto") else load,
                                                use_preview)
                set_plan(new, source)
                ss["animate_route"] = True  # lay the new route out once, on the next run
                st.rerun()  # so the hero's progress bar reflects the new plan
            except svc.NotReady as e:
                not_ready(e)
        if plan:
            if a2.button("Add a course", width="stretch"):
                add_dialog()
            if a3.button("Drop a course", width="stretch", disabled=not plan["semesters"]):
                drop_dialog()
            if undo := ss.undo.get(student_id):
                label, previous = undo
                if a4.button("Undo last change", width="stretch", help=f"Undo: {label}"):
                    ss.undo.pop(student_id)
                    ss.plans[student_id] = previous
                    ss["toast"] = f"Undid: {label}"
                    st.rerun()
    if plan:
        ui.preview_banner(ss.sources.get(student_id, "live"))
        ui.plan_warnings(plan)

    if plan or done:
        with st.container(key="card_rings"):
            st.markdown("### Degree requirements")
            st.caption("Green is completed, blue is in progress or planned. Each ring is one requirement area "
                       "of your degree.")
            try:
                progress, source = svc.requirement_progress(student_id, shown_program, plan,
                                                            use_preview)
                ui.rings(progress)
                if source == "preview":
                    st.caption("Preview: courses are sorted into areas using the course lists in "
                               "the degree documents, not the real degree audit.")
            except svc.NotReady as e:
                not_ready(e)

        view = st.segmented_control("View", ["Timeline", "Years"], default="Timeline",
                                    key="plan_view", label_visibility="collapsed") or "Timeline"
        if view == "Years":
            ui.year_view(plan, done)
        else:
            ui.route(plan, done, animate=ss.pop("animate_route", False))
    else:
        st.caption("Build a plan to see every semester laid out here.")

elif section == "Ask":
    messages = ss.messages.setdefault(student_id, [
        {"role": "assistant",
         "content": f"Hi {student['name'].split()[0]}. I can build your degree plan, answer "
                    "questions about courses, requirements, and the class schedule, and help "
                    "you add or drop classes or switch majors."}
    ])
    def open_plan(p: dict, source: str) -> None:  # "Open in Plan" on a plan card
        set_plan(p, source)
        ss["section"] = "Plan"
        ss["animate_route"] = True

    def render_cards(m: dict, idx: int) -> None:
        for j, card in enumerate(m.get("cards", [])):
            ui.chat_card(card)
            if card.get("type") == "plan":
                st.button("Open in Plan", key=f"open_{idx}_{j}", on_click=open_plan,
                          args=(card["plan"], m.get("source", "live")))

    for idx, m in enumerate(messages):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("source") == "preview":
                st.caption("Preview answer")
            render_cards(m, idx)
    if len(messages) == 1:
        with st.container(key="suggestions"):
            cols = st.columns(2)
            for i, text in enumerate(SUGGESTIONS):
                if cols[i % 2].button(text, key=f"suggest_{i}", width="stretch"):
                    ss["pending_prompt"] = text
                    st.rerun()
    prompt = st.chat_input("Ask about courses, requirements, or the schedule") \
        or ss.pop("pending_prompt", None)
    if prompt:
        messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Thinking…"):
                    reply, source = svc.ask(student_id, prompt, messages, plan, use_preview)
            except svc.NotReady as e:
                messages.pop()  # let them ask again once the chat backend lands
                not_ready(e)
                st.stop()
            st.write_stream(type_out(reply["text"]))
        messages.append({"role": "assistant", "content": reply["text"],
                         "cards": reply["cards"], "source": source})
        st.rerun()  # redraw with the reply's cards

elif section == "Check a course":
    with st.container(key="card_check"):
        st.markdown("### Can I take this course?")
        st.caption("The advisor runs these six checks before it recommends any course.")
        c1, c2, c3 = st.columns([3, 1.3, 1.1], vertical_alignment="bottom")
        cid = c1.selectbox("Course", list(COURSES), format_func=course_label, key="check_course")
        term = c2.selectbox("Semester", TERMS, format_func=ui.term_label, key="check_term")
        run = c3.button("Run checks", type="primary", width="stretch")
        if run:
            try:
                checks, source = svc.verify_course(student_id, cid, term, plan, use_preview)
                ui.preview_banner(source)
                ui.checks_table(checks)
            except svc.NotReady as e:
                not_ready(e)
    secs = svc.sections(cid, term)
    with st.expander(f"Sections of {cid} in {ui.term_label(term)}: {len(secs)}"):
        if secs:
            st.dataframe(secs, hide_index=True, width="stretch")
        else:
            st.caption("No sections are scheduled for this semester.")

elif section == "Switch major":
    with st.container(key="card_switch"):
        st.markdown("### Explore switching major")
        st.caption("See a plan in another program next to your current one. To talk through "
                   "the pros and cons, ask the advisor.")
        others = [p for p in PROGRAMS if p != student["program_id"]]
        c1, c2 = st.columns([3, 1.1], vertical_alignment="bottom")
        target = c1.selectbox("Switch to", others, format_func=program_name)
        if c2.button("Compare plans", type="primary", width="stretch", disabled=not others):
            try:
                if not plan or plan["program_id"] != student["program_id"]:
                    plan, source = svc.generate_plan(student_id, student["program_id"],
                                                     False, None, use_preview)
                    set_plan(plan, source)
                new, new_src = svc.generate_plan(student_id, target, False, None, use_preview)
                diff, diff_src = svc.diff_plans(plan, new, use_preview)
                ss["switch"] = {"student_id": student_id, "old": plan, "new": new, "diff": diff,
                                "source": "preview" if "preview" in (new_src, diff_src) else "live"}
                st.rerun()
            except svc.NotReady as e:
                not_ready(e)

    result = ss.get("switch")
    if result and result["student_id"] == student_id:
        ui.preview_banner(result["source"])
        with st.container(key="card_compare"):
            ui.compare(result["old"], f"Now: {program_name(result['old']['program_id'])}",
                       result["new"], f"After switching: {program_name(result['new']['program_id'])}")
        with st.container(key="card_diff"):
            st.markdown("### What changes")
            ui.diff_view(result["diff"])
            if st.button("Use this plan", type="primary"):
                set_plan(result["new"], result["source"])
                ss.pop("switch")
                st.rerun()

elif section == "Traces":
    with st.container(key="card_traces"):
        st.markdown("### Execution trace")
        st.caption("Every chat turn and action, step by step, as written to logs/traces.jsonl "
                   "(the trace log submitted with the project).")
        c1, c2, c3 = st.columns([1.35, 1.6, 2.2], vertical_alignment="bottom")
        scope = c1.segmented_control("Sessions", ["This session", "All"],
                                     default="This session", key="trace_scope") or "This session"
        who = c2.segmented_control("Students", ["This student", "All students"],
                                   default="All students", key="trace_who") or "All students"
        query = c3.text_input("Search", placeholder="Search messages, intents, courses…",
                              key="trace_query").strip().lower()
        records = tracing.read(session=ss.trace_session if scope == "This session" else None,
                               student_id=student_id if who == "This student" else None)
        groups = tracing.group_turns(records)
        if query:
            groups = [g for g in groups
                      if query in json.dumps(g["events"], ensure_ascii=False).lower()]
        ui.trace_summary(groups, tracing.duration_ms)
        shown = [r for g in groups for r in g["events"]]
        st.download_button("Download these events (.jsonl)", width="content",
                           data="".join(json.dumps(r, ensure_ascii=False) + "\n" for r in shown),
                           file_name="traces.jsonl", mime="application/json",
                           disabled=not shown)
    if groups:
        names = {sid: s_["name"] for sid, s_ in STUDENTS.items()}
        ui.trace_list(groups[-100:], names, tracing.duration_ms)
        if len(groups) > 100:
            st.caption(f"Showing the newest 100 of {len(groups)}. Download for the full log.")
    else:
        st.caption("Nothing logged here yet. Use the advisor in another section, then come back.")
