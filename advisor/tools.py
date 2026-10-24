"""LangChain tool surface (Kyle) — FROZEN CONTRACT.

These signatures are what the orchestrator (and any agent executor) calls.
Owners implement the bodies; signatures and docstrings may only change with
team sign-off.
"""

from dataclasses import asdict

from langchain_core.tools import tool
from sqlalchemy import text

from . import chains, compare, db, planner, plan_store


@tool
def get_student_record(student_id: str) -> dict:
    """Look up a student's profile: program, completed courses, current
    enrollments. Exact-match SQL query."""
    rows = db.query("SELECT * FROM students WHERE student_id = :s", {"s": student_id})
    if not rows:
        return {"error": f"unknown student_id '{student_id}'"}
    student = rows[0]
    student["completed_courses"] = db.query(
        "SELECT course_id, term, grade FROM completed_courses"
        " WHERE student_id = :s ORDER BY term", {"s": student_id})
    student["enrollments"] = [
        r["section_id"] for r in db.query(
            "SELECT section_id FROM enrollments WHERE student_id = :s", {"s": student_id})
    ]
    return student


@tool
def get_course_prerequisites(course_id: str) -> list[dict]:
    """Return the prerequisite groups for a course (e.g. 'CSE 3310')."""
    raise NotImplementedError("TODO Jordan")


@tool
def get_class_schedule(course_id: str | None = None, term: str | None = None) -> list[dict]:
    """List scheduled sections, optionally filtered by course and/or term."""
    raise NotImplementedError("TODO Jordan")


@tool
def generate_degree_plan(student_id: str, include_summer: bool = False) -> dict:
    """Generate a multi-year degree plan for the student. Returns
    DegreePlan.to_dict(). All six verification checks are applied inside the
    planner before any course is recommended."""
    plan = planner.generate_plan(student_id, include_summer=include_summer)
    plan_store.save(plan)
    return plan.to_dict()


@tool
def verify_course_eligibility(student_id: str, course_id: str, term: str) -> list[dict]:
    """Run the six recommendation checks for a course in a term and return
    per-check pass/fail details."""
    plan = plan_store.latest(student_id)
    return [asdict(c) for c in planner.verify_course(student_id, course_id, term, plan)]


@tool
def modify_plan(student_id: str, add: list[str] | None = None, drop: list[str] | None = None,
                term: str | None = None, courses_per_semester: int | None = None) -> dict:
    """Modify the student's current plan: add/drop courses, or regenerate with
    a different semester course load. Returns the updated plan dict."""
    if (add or drop) and term is None:
        raise ValueError("An explicit term is required when adding or dropping courses")
    plan = plan_store.latest(student_id) or planner.generate_plan(student_id)
    if courses_per_semester is not None:
        plan = planner.generate_plan(student_id, program_id=plan.program_id,
                                     include_summer=any(s.term.startswith("SU") for s in plan.semesters),
                                     courses_per_semester=courses_per_semester)
    for cid in drop or []:
        plan = planner.drop_course(plan, cid, term)
    if add:
        plan = planner.add_courses(plan, add, term)
    plan_store.save(plan)
    return plan.to_dict()


@tool
def switch_major(student_id: str, new_program_id: str) -> dict:
    """Switch the student's program, generate the new plan, and return
    {new_plan, diff} where diff comes from compare.diff_plans."""
    old = plan_store.latest(student_id) or planner.generate_plan(student_id)
    new = planner.generate_plan(student_id, program_id=new_program_id,
                                include_summer=any(s.term.startswith("SU") for s in old.semesters))
    difference = compare.diff_plans(old, new)
    with db.get_engine().begin() as conn:
        conn.execute(text("UPDATE students SET program_id=:pid WHERE student_id=:sid"),
                     {"pid": new_program_id, "sid": student_id})
        plan_store.write(conn, new)
    return {"new_plan": new.to_dict(), "diff": difference}


@tool
def search_advising_docs(query: str, k: int = 5) -> list[dict]:
    """Semantic search over the Chroma store (catalog descriptions, degree
    requirements, policies). Returns [{'id', 'text', 'score'}]."""
    raise NotImplementedError("TODO Miguel")


ALL_TOOLS = [
    get_student_record,
    get_course_prerequisites,
    get_class_schedule,
    generate_degree_plan,
    verify_course_eligibility,
    modify_plan,
    switch_major,
    search_advising_docs,
]
