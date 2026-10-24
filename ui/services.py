"""UI service layer (Person E): the only place app.py touches the backend.

Calls the planner / compare contracts, logs every UI action to the trace log,
and — while teammates' modules are still stubs — optionally falls back to
clearly-labelled preview data so the UI can be built and demoed early.

Every function returns (result, source) where source is "live" or "preview".
If a backend function isn't implemented and preview mode is off, NotReady is
raised and the UI shows a "not implemented yet" message instead.
"""

import json
from dataclasses import asdict

from advisor import compare, db, orchestrator, planner, tracing

from . import preview


class NotReady(Exception):
    """A teammate's module is still a stub."""


def _call(action: str, student_id: str, live, fallback, use_preview: bool,
          log: bool = True, **fields):
    """Run `live`, or `fallback` in preview mode when it isn't implemented.
    log=False for passive reads that run on every redraw (keeps the trace readable)."""
    try:
        result, source = live(), "live"
    except NotImplementedError as e:
        if not use_preview:
            if log:
                tracing.trace("ui_action", student_id=student_id, action=action,
                              source="not_ready", error=str(e), **fields)
            raise NotReady(str(e)) from e
        result, source = fallback(), "preview"
    if log:
        tracing.trace("ui_action", student_id=student_id, action=action, source=source, **fields)
    return result, source


# ---------------------------------------------------------------- lookups

def students() -> dict[str, dict]:
    return {s["student_id"]: s for s in db.query("SELECT * FROM students ORDER BY name")}


def programs() -> dict[str, dict]:
    return {p["program_id"]: p for p in db.query("SELECT * FROM degree_programs")}


def courses() -> dict[str, dict]:
    return {c["course_id"]: c for c in db.query(
        "SELECT course_id, title, credits FROM courses ORDER BY dept, number")}


def terms() -> list[str]:
    rows = db.query("SELECT DISTINCT term FROM sections")
    return sorted((r["term"] for r in rows), key=planner.term_key)


def completed_courses(student_id: str) -> list[dict]:
    return db.query(
        "SELECT cc.course_id, c.title, c.credits, cc.term, cc.grade"
        " FROM completed_courses cc JOIN courses c USING (course_id)"
        " WHERE cc.student_id = :sid ORDER BY cc.term, cc.course_id",
        {"sid": student_id},
    )


def sections(course_id: str, term: str) -> list[dict]:
    return db.query(
        "SELECT section_id, days, start_time, end_time, instructor, capacity"
        " FROM sections WHERE course_id = :cid AND term = :term ORDER BY section_id",
        {"cid": course_id, "term": term},
    )


# ---------------------------------------------------------- plan contracts

def plan_from_dict(d: dict) -> planner.DegreePlan:
    """Rebuild a DegreePlan from its to_dict() shape (session state keeps dicts)."""
    return planner.DegreePlan(
        student_id=d["student_id"],
        program_id=d["program_id"],
        semesters=[planner.PlanSemester(s["term"], list(s["courses"])) for s in d["semesters"]],
        warnings=list(d.get("warnings", [])),
    )


def generate_plan(student_id: str, program_id: str, include_summer: bool,
                  courses_per_semester: int | None, use_preview: bool):
    return _call(
        "generate_plan", student_id,
        live=lambda: planner.generate_plan(
            student_id, program_id, include_summer, courses_per_semester).to_dict(),
        fallback=lambda: preview.plan(student_id, program_id, include_summer, courses_per_semester),
        use_preview=use_preview,
        program_id=program_id, include_summer=include_summer,
        courses_per_semester=courses_per_semester,
    )


def verify_course(student_id: str, course_id: str, term: str, plan: dict | None,
                  use_preview: bool):
    def live():
        p = plan_from_dict(plan) if plan else None
        return [asdict(r) for r in planner.verify_course(student_id, course_id, term, p)]

    return _call(
        "verify_course", student_id, live,
        fallback=lambda: preview.checks(student_id, course_id),
        use_preview=use_preview, course_id=course_id, term=term,
    )


def add_course(plan: dict, course_id: str, term: str, use_preview: bool):
    return _call(
        "add_course", plan["student_id"],
        live=lambda: planner.add_course(plan_from_dict(plan), course_id, term).to_dict(),
        fallback=lambda: preview.add(plan, course_id, term),
        use_preview=use_preview, course_id=course_id, term=term,
    )


def drop_course(plan: dict, course_id: str, term: str, use_preview: bool):
    return _call(
        "drop_course", plan["student_id"],
        live=lambda: planner.drop_course(plan_from_dict(plan), course_id, term).to_dict(),
        fallback=lambda: preview.drop(plan, course_id, term),
        use_preview=use_preview, course_id=course_id, term=term,
    )


def diff_plans(old: dict, new: dict, use_preview: bool):
    return _call(
        "diff_plans", old["student_id"],
        live=lambda: compare.diff_plans(plan_from_dict(old), plan_from_dict(new)),
        fallback=lambda: preview.diff(old, new),
        use_preview=use_preview,
        old_program=old["program_id"], new_program=new["program_id"],
    )


# ------------------------------------------------------- requirement progress

def _requirements_live(student_id: str, program_id: str, plan: dict | None) -> list[dict]:
    """Credits completed / planned per requirement category, from requirement_slots
    (schema.sql). Each course fills at most one slot; completed courses fill first."""
    slots = db.query("SELECT category, course_id, options, credits FROM requirement_slots"
                     " WHERE program_id = :p ORDER BY slot_id", {"p": program_id})
    if not slots:
        raise NotImplementedError("TODO Person A: seed requirement_slots for " + program_id)
    done = {r["course_id"] for r in db.query(
        "SELECT course_id FROM completed_courses WHERE student_id = :sid", {"sid": student_id})}
    planned = {c["course_id"] for s in (plan or {}).get("semesters", []) for c in s["courses"]}
    out: dict[str, dict] = {}
    used: set[str] = set()
    for slot in slots:
        row = out.setdefault(slot["category"], {"category": slot["category"], "required": 0,
                                                "completed": 0, "planned": 0})
        row["required"] += slot["credits"]
        options = [slot["course_id"]] if slot["course_id"] else json.loads(slot["options"] or "[]")
        for pool, key in ((done, "completed"), (planned, "planned")):
            match = next((c for c in options if c in pool and c not in used), None)
            if match:
                used.add(match)
                row[key] += slot["credits"]
                break
    return list(out.values())


def requirement_progress(student_id: str, program_id: str, plan: dict | None, use_preview: bool):
    return _call(
        "requirement_progress", student_id,
        live=lambda: _requirements_live(student_id, program_id, plan),
        fallback=lambda: preview.requirements(student_id, program_id, plan),
        use_preview=use_preview, log=False, program_id=program_id,
    )


# ----------------------------------------------------------------------- chat

def ask(student_id: str, prompt: str, messages: list[dict], plan: dict | None,
        use_preview: bool) -> tuple[dict, str]:
    """One chat turn. Returns ({"text", "cards"}, source).

    The orchestrator may return a plain string (today) or {"text": str, "cards": [...]}
    (see ui/README.md); both are normalized here. With preview on, keyword-routed
    placeholder answers stand in for the orchestrator.
    """
    if use_preview:
        # The orchestrator logs live turns itself; log preview turns the same way.
        tracing.trace("user_msg", student_id=student_id, message=prompt, source="preview")
        reply, source = preview.chat_reply(student_id, prompt, plan), "preview"
        tracing.trace("assistant_msg", student_id=student_id, intent="preview",
                      reply=reply["text"][:2000], cards=[c.get("type") for c in reply["cards"]],
                      source="preview")
    else:
        raw, source = orchestrator.handle_message(student_id, prompt, messages), "live"
        reply = raw if isinstance(raw, dict) else {"text": str(raw), "cards": []}
        if reply.get("cards"):
            tracing.trace("ui_action", student_id=student_id, action="show_cards", source="live",
                          cards=[c.get("type") for c in reply["cards"]])
    reply.setdefault("cards", [])
    return reply, source
