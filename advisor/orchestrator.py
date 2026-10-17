"""Orchestrator (Kyle): the LangChain glue.

handle_message() is the single entry point the UI calls per chat turn:
  1. persist + trace the user message (memory, tracing)
  2. route -> Intent (router)
  3. dispatch to a handler (chains / planner tools / advising dialog)
  4. persist + trace the assistant reply and return it

Handlers are thin over tools.py so the same operations are also exposed as
LangChain tools for a future agent executor. Handlers for other workstreams
call their tools — those raise NotImplementedError until owners land them,
which handle_message converts into a friendly "not implemented yet" reply.
"""

import re

from . import chains, db, memory, router, tools, tracing

_SYSTEM = (
    "You are an academic advising assistant for UTA CSE students. Be concise. "
    "You cannot look up records or generate degree plans in this mode — those "
    "requests are handled elsewhere. For general advising questions, answer "
    "briefly and suggest the student ask about their plan, a course's "
    "prerequisites, or a schedule."
)


def handle_message(student_id: str, message: str, history: list[dict] | None = None) -> str:
    """Process one chat turn and return the assistant's reply text."""
    tracing.trace("user_msg", student_id=student_id, message=message)
    memory.add_message(student_id, "user", message)

    intent = router.route(message, history)
    tracing.trace("intent", student_id=student_id, intent=intent.value)

    try:
        reply = _dispatch(student_id, message, intent, history)
    except NotImplementedError as e:
        reply = (f"That request routes to **{intent.value}**, which isn't "
                 f"implemented yet.\n\n`{e}`")
    return _finish(student_id, reply, intent.value)


def _dispatch(student_id: str, message: str, intent: router.Intent, history) -> str:
    if intent in (router.Intent.EXACT_QUERY, router.Intent.STATUS_QUERY):
        return chains.answer_exact(message, student_id)
    if intent == router.Intent.SEMANTIC_QUERY:
        return chains.answer_semantic(message, student_id)          # Miguel
    if intent == router.Intent.GENERATE_PLAN:
        plan = tools.generate_degree_plan.invoke({
            "student_id": student_id,
            "include_summer": _wants_summer(message),
        })                                                           # Loc
        return _format_plan(plan)
    if intent == router.Intent.MODIFY_PLAN:
        plan = tools.modify_plan.invoke({                           # Loc
            "student_id": student_id,
            **_extract_modify_args(message),
        })
        return _format_plan(plan)
    if intent == router.Intent.SWITCH_MAJOR:
        return _handle_switch_major(student_id, message)
    if intent == router.Intent.CHECK_ELIGIBILITY:
        return _handle_eligibility(student_id, message)
    return _general_answer(message, history)


_TERM_RE = re.compile(r"\b(SU?\d{4}|F\d{4})\b")


def _handle_eligibility(student_id: str, message: str) -> str:
    """"Can I take X next semester?" -> Loc's 6-check verifier."""
    m = _COURSE_ID_RE.search(message.upper())
    if not m:
        return "Which course did you want me to check? (e.g. \"can I take CSE 4344?\")"
    course_id = f"{m.group(1)} {m.group(2)}"
    term = _infer_term(student_id, message)
    results = tools.verify_course_eligibility.invoke({              # Loc
        "student_id": student_id, "course_id": course_id, "term": term})
    if not results:
        return f"The eligibility check for **{course_id}** in `{term}` returned no results."
    checks = [r if isinstance(r, dict)
              else {"name": r.name, "passed": r.passed, "detail": getattr(r, "detail", "")}
              for r in results]
    lines = [f"**Eligibility check: {course_id} in {term}**\n"]
    for r in checks:
        mark = "✅" if r["passed"] else "❌"
        detail = f" — {r['detail']}" if r.get("detail") else ""
        lines.append(f"{mark} {r['name']}{detail}")
    if all(r["passed"] for r in checks):
        lines.append("\nAll checks passed — this course can be recommended.")
    return "\n".join(lines)


_COURSE_ID_RE = re.compile(r"\b([A-Z]{2,4})\s*(\d{4})\b")


def _infer_term(student_id: str, message: str) -> str:
    """Pick a target term: explicit term in the message, else the term after
    the student's most recent completed course, else their start term."""
    from .planner import next_terms, term_key
    m = _TERM_RE.search(message.upper())
    if m:
        return m.group(1)
    done = db.query(
        "SELECT term FROM completed_courses WHERE student_id = :s",
        {"s": student_id})
    base = max((r["term"] for r in done), key=term_key) if done else None
    if base is None:
        rows = db.query("SELECT start_term FROM students WHERE student_id = :s",
                        {"s": student_id})
        base = rows[0]["start_term"] if rows else "F2026"
    return next_terms(base, 1, include_summer="summer" in message.lower())[0]


def _handle_switch_major(student_id: str, message: str) -> str:
    """Spec req 5: engage the student about a major change, then regenerate
    the plan with a comparison. Minimal flow: if the target program isn't
    stated, ask which one (that IS the multi-turn engagement); if stated,
    run the switch + diff."""
    pid = _extract_program(message)
    if pid is None:
        programs = db.query("SELECT program_id, name FROM degree_programs")
        opts = "\n".join(f"- `{p['program_id']}` — {p['name']}" for p in programs)
        return ("A major change is worth thinking through. Which program are "
                "you considering switching to?\n\n" + opts +
                "\n\nOnce you pick, I'll generate the new plan and compare it "
                "against your current one — what you'd gain, lose, and how "
                "many semesters it adds.")
    res = tools.switch_major.invoke({                               # Loc
        "student_id": student_id, "new_program_id": pid})
    diff = res.get("diff", {})
    out = [_format_plan(res.get("new_plan", res))]
    if diff:
        out += [
            "\n**Compared to your current plan:**",
            f"- Courses added: {len(diff.get('added', []))}",
            f"- Courses removed: {len(diff.get('removed', []))}",
            f"- Courses moved: {len(diff.get('moved', []))}",
            f"- Credits delta: {diff.get('credits_delta', 0):+d} hrs",
            f"- Semesters added: {diff.get('semesters_added', 0):+d}",
        ]
        if diff.get("summary"):
            out.append(f"\n{diff['summary']}")
    return "\n".join(out)


def _extract_program(message: str) -> str | None:
    """Map free text to a program_id via program-name keywords."""
    q = message.lower()
    for p in db.query("SELECT program_id, name FROM degree_programs"):
        name = p["name"].lower()
        # 'software engineering' vs 'computer science' disambiguate the two programs
        if "software engineering" in q and "software engineering" in name:
            return p["program_id"]
        if ("computer science" in q or "cybersecurity" in q or "cyber security" in q) \
                and "computer science" in name:
            return p["program_id"]
    return None


def _extract_modify_args(message: str) -> dict:
    """Pull add/drop course ids and course-load numbers out of the message.
    Returns kwargs matching tools.modify_plan's signature."""
    upper = message.upper()
    adds = [f"{d} {n}" for d, n in
            re.findall(r"(?:ADD|TAKE|REGISTER FOR|ENROLL IN)\s+([A-Z]{2,4})\s*(\d{4})", upper)]
    drops = [f"{d} {n}" for d, n in
             re.findall(r"(?:DROP|REMOVE)\s+([A-Z]{2,4})\s*(\d{4})", upper)]
    m = re.search(r"(\d+)\s*(?:classes|courses)", message.lower())
    return {
        "add": adds or None,
        "drop": drops or None,
        "courses_per_semester": int(m.group(1)) if m else None,
    }


def _wants_summer(message: str) -> bool:
    return "summer" in message.lower()


def _format_plan(plan: dict) -> str:
    """Render a DegreePlan.to_dict() as markdown for chat."""
    sems = plan.get("semesters", [])
    if not sems:
        return "The planner returned an empty plan."
    lines = [f"**Degree plan** — `{plan.get('program_id', '?')}`\n"]
    for s in sems:
        courses = ", ".join(c["course_id"] for c in s["courses"]) or "(empty)"
        lines.append(f"- `{s['term']}` ({s['credits']} hrs): {courses}")
    lines.append(f"\n**Total planned:** {plan.get('total_credits_planned', 0)} hrs")
    for w in plan.get("warnings", []):
        lines.append(f"\n⚠️ {w}")
    return "\n".join(lines)


def _general_answer(message: str, history: list[dict] | None) -> str:
    """OTHER fallback: general advising chat via the configured LLM."""
    from .config import get_chat_model

    msgs = [{"role": "system", "content": _SYSTEM}]
    msgs += [{"role": m["role"], "content": m["content"]}
             for m in (history or [])[-6:]]
    msgs.append({"role": "user", "content": message})
    try:
        resp = get_chat_model(reasoning=False).invoke(msgs)
        text = resp.content if hasattr(resp, "content") else str(resp)
        return router._strip_think(text) or "I'm not sure how to help with that."
    except Exception as e:
        tracing.trace("llm_error", error=str(e))
        return ("I couldn't reach the LLM backend. If you're on Ollama, check "
                "that `ollama serve` is running and the model in `.env` is pulled.")


def _finish(student_id: str, reply: str, intent: str) -> str:
    memory.add_message(student_id, "assistant", reply)
    tracing.trace("assistant_msg", student_id=student_id, intent=intent, reply=reply[:2000])
    return reply
