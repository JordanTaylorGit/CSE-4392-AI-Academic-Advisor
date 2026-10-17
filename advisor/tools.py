"""LangChain tool surface (Person D) — FROZEN CONTRACT.

These signatures are what the orchestrator (and any agent executor) calls.
Owners implement the bodies; signatures and docstrings may only change with
team sign-off.
"""

from langchain_core.tools import tool

from . import chains, compare, db, planner


@tool
def get_student_record(student_id: str) -> dict:
    """Look up a student's profile: program, completed courses, current
    enrollments. Exact-match SQL query."""
    raise NotImplementedError("TODO Person D/A")


@tool
def get_course_prerequisites(course_id: str) -> list[dict]:
    """Return the prerequisite groups for a course (e.g. 'CSE 3310')."""
    raise NotImplementedError("TODO Person A")


@tool
def get_class_schedule(course_id: str | None = None, term: str | None = None) -> list[dict]:
    """List scheduled sections, optionally filtered by course and/or term."""
    raise NotImplementedError("TODO Person A")


@tool
def generate_degree_plan(student_id: str, include_summer: bool = False) -> dict:
    """Generate a multi-year degree plan for the student. Returns
    DegreePlan.to_dict(). All six verification checks are applied inside the
    planner before any course is recommended."""
    raise NotImplementedError("TODO Person B")


@tool
def verify_course_eligibility(student_id: str, course_id: str, term: str) -> list[dict]:
    """Run the six recommendation checks for a course in a term and return
    per-check pass/fail details."""
    raise NotImplementedError("TODO Person B")


@tool
def modify_plan(student_id: str, add: list[str] | None = None, drop: list[str] | None = None,
                term: str | None = None, courses_per_semester: int | None = None) -> dict:
    """Modify the student's current plan: add/drop courses, or regenerate with
    a different semester course load. Returns the updated plan dict."""
    raise NotImplementedError("TODO Person B")


@tool
def switch_major(student_id: str, new_program_id: str) -> dict:
    """Switch the student's program, generate the new plan, and return
    {new_plan, diff} where diff comes from compare.diff_plans."""
    raise NotImplementedError("TODO Person B")


@tool
def search_advising_docs(query: str, k: int = 5) -> list[dict]:
    """Semantic search over the Chroma store (catalog descriptions, degree
    requirements, policies). Returns [{'id', 'text', 'score'}]."""
    raise NotImplementedError("TODO Person C")


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
