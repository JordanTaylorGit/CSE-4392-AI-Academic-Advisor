"""Planner snapshots in the existing plans/plan_semesters storage contract."""

from sqlalchemy import text

from . import db, planner


def save(plan: planner.DegreePlan) -> None:
    with db.get_engine().begin() as conn:
        write(conn, plan)


def write(conn, plan: planner.DegreePlan) -> None:
    """Write within the caller's transaction (also used for atomic major changes)."""
    result = conn.execute(
        text("INSERT INTO plans (student_id, program_id) VALUES (:student_id, :program_id)"),
        {"student_id": plan.student_id, "program_id": plan.program_id},
    )
    plan_id = result.lastrowid
    rows = [{"pid": plan_id, "term": s.term, "cid": c["course_id"]}
            for s in plan.semesters for c in s.courses]
    if rows:
        conn.execute(text("INSERT INTO plan_semesters (plan_id, term, course_id)"
                          " VALUES (:pid, :term, :cid)"), rows)


def latest(student_id: str) -> planner.DegreePlan | None:
    rows = db.query(
        "SELECT p.* FROM plans p JOIN students s ON s.student_id=p.student_id"
        " AND s.program_id=p.program_id WHERE p.student_id=:sid ORDER BY p.plan_id DESC LIMIT 1",
        {"sid": student_id},
    )
    if not rows:
        return None
    row = rows[0]
    assignments = db.query(
        "SELECT ps.term, c.course_id, c.title, c.credits FROM plan_semesters ps"
        " JOIN courses c USING (course_id) WHERE ps.plan_id=:pid",
        {"pid": row["plan_id"]},
    )
    by_term: dict[str, list[dict]] = {}
    for assignment in assignments:
        term = assignment.pop("term")
        by_term.setdefault(term, []).append(assignment)
    terms = sorted(by_term, key=planner.term_key)
    if terms:
        # Preserve intervening empty terms; the schema only stores courses.
        calendar = [terms[0]]
        summer = any(term.startswith("SU") for term in terms)
        while planner.term_key(calendar[-1]) < planner.term_key(terms[-1]):
            calendar.extend(planner.next_terms(calendar[-1], 1, summer))
        terms = calendar
    plan = planner.DegreePlan(student_id, row["program_id"], [
        planner.PlanSemester(term, sorted(by_term.get(term, []), key=lambda c: c["course_id"]))
        for term in terms
    ])
    return planner.revalidate_plan(plan)
