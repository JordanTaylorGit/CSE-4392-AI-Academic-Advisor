"""Degree Planner + Verification Engine (Loc).

DETERMINISTIC — no LLM calls in this module. The planner topologically orders
the prerequisite DAG over the student's remaining requirement slots and packs
courses into semesters subject to credit caps and schedule feasibility.

The degree-plan JSON contract (consumed by the UI, compare.py, tools.py):

    DegreePlan.to_dict() == {
        "student_id": str,
        "program_id": str,
        "semesters": [{"term": "F2026",
                       "courses": [{"course_id": str, "title": str, "credits": int}],
                       "credits": int}, ...],
        "total_credits_planned": int,
        "warnings": [str, ...],          # e.g. unscheduled courses, cap hits
    }
"""

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field

from . import db

# Term ordering helpers. Terms: 'F2026', 'S2027', 'SU2027'.
TERM_SEASON_ORDER = {"S": 0, "SU": 1, "F": 2}


def term_key(term: str) -> tuple[int, int]:
    """Sort key for term strings like 'F2026'."""
    match = re.fullmatch(r"(SU|S|F)([0-9]{4})", term)
    if not match:
        raise ValueError(f"Invalid term {term!r}; expected S2027, SU2027, or F2027")
    return int(match[2]), TERM_SEASON_ORDER[match[1]]


def next_terms(start: str, n: int, include_summer: bool = False) -> list[str]:
    """Next n terms after `start` in chronological order (excl. start)."""
    year, order = term_key(start)
    out = []
    while len(out) < n:
        order += 1
        if order == 3:
            year, order = year + 1, 0
        if order != 1 or include_summer:
            out.append(f"{('S', 'SU', 'F')[order]}{year}")
    return out


@dataclass
class PlanSemester:
    term: str
    courses: list[dict] = field(default_factory=list)  # {course_id,title,credits}

    @property
    def credits(self) -> int:
        return sum(c["credits"] for c in self.courses)


@dataclass
class DegreePlan:
    student_id: str
    program_id: str
    semesters: list[PlanSemester] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "program_id": self.program_id,
            "semesters": [
                {"term": s.term, "courses": s.courses, "credits": s.credits}
                for s in self.semesters
            ],
            "total_credits_planned": sum(s.credits for s in self.semesters),
            "warnings": self.warnings,
        }


@dataclass
class CheckResult:
    """One of the six spec §4 verification checks."""

    name: str          # e.g. 'prerequisites_met'
    passed: bool
    detail: str = ""


CHECK_NAMES = [
    "prerequisites_met",            # (a) all prereqs satisfied
    "not_already_passed",           # (b) student hasn't passed the course
    "fulfills_degree_requirement",  # (c) counts toward the degree
    "no_schedule_conflict",         # (d) section times don't overlap
    "within_semester_credit_cap",   # (e) <= student's per-semester max
    "within_degree_credit_cap",     # (f) <= program total_credits
]


def generate_plan(
    student_id: str,
    program_id: str | None = None,
    include_summer: bool = False,
    courses_per_semester: int | None = None,
) -> DegreePlan:
    """Pack a prerequisite-ready frontier into the available schedule horizon.

    A course becomes ready only after its prerequisites occur in earlier terms.
    Alternative prerequisites/sections are considered without inventing future
    offerings. Incomplete data or an infeasible graph returns a partial plan
    with explicit warnings, never an unverified recommendation.
    """
    if courses_per_semester is not None and (isinstance(courses_per_semester, bool)
                                            or not isinstance(courses_per_semester, int)
                                            or courses_per_semester <= 0):
        raise ValueError("courses_per_semester must be a positive integer")
    context = _load_context(student_id, program_id)
    plan = DegreePlan(student_id, context.program["program_id"])
    if not context.slots:
        plan.warnings.append("No requirement slots are loaded for this program; seed the degree requirements first.")
        return plan
    start = context.student["start_term"]
    if context.completed:
        after_record = next_terms(max((r["term"] for r in context.completed), key=term_key), 1, include_summer)[0]
        start = max(start, after_record, key=term_key)
    if start.startswith("SU") and not include_summer:
        start = next_terms(start, 1)[0]
    available = sorted({s["term"] for s in context.sections if term_key(s["term"]) >= term_key(start)
                        and (include_summer or not s["term"].startswith("SU"))}, key=term_key)
    if not available:
        plan.warnings.append("No future class schedule is loaded; no courses can be verified.")
        return plan
    start = max(start, available[0], key=term_key)
    terms = [start]
    while term_key(terms[-1]) < term_key(available[-1]):
        terms.extend(next_terms(terms[-1], 1, include_summer))

    # Prioritize prerequisite courses that unlock more of the remaining DAG.
    children: dict[str, set[str]] = {}
    for row in context.prerequisites:
        children.setdefault(row["prereq_id"], set()).add(row["course_id"])

    def descendants(cid: str) -> int:
        seen, pending = {cid}, list(children.get(cid, ()))
        while pending:
            child = pending.pop()
            if child not in seen:
                seen.add(child)
                pending.extend(children.get(child, ()))
        return len(seen) - 1

    candidates = set().union(*(slot.options for slot in context.slots)) & context.courses.keys()
    order = sorted(candidates, key=lambda cid: (-descendants(cid), cid))
    for term in terms:
        semester = PlanSemester(term)
        plan.semesters.append(semester)
        for section in context.enrollments:
            if section["term"] == term and section["course_id"] not in _plan_ids(plan):
                semester.courses.append(_course_dict(context, section["course_id"]))
        for cid in order:
            if courses_per_semester is not None and len(semester.courses) >= courses_per_semester:
                break
            if cid in _plan_ids(plan) or cid in _passed(context):
                continue
            if all(c.passed for c in _verify(context, cid, term, plan)):
                semester.courses.append(_course_dict(context, cid))
        if _requirements_complete(context, _passed(context) | _plan_ids(plan)):
            break
    while plan.semesters and not plan.semesters[-1].courses:
        plan.semesters.pop()
    _audit(context, plan)
    if not _requirements_complete(context, _passed(context) | _plan_ids(plan)):
        plan.warnings.append(f"Schedule horizon ends at {available[-1]}; future offerings are not assumed.")
    return plan


def verify_course(student_id: str, course_id: str, term: str, plan: DegreePlan | None = None) -> list[CheckResult]:
    """Run all six checks against records, earlier plan terms, and real sections.

    Passing an existing plan course rechecks it without counting it twice.
    Planned prerequisites are conditional on passing those earlier courses.
    """
    term_key(term)
    if plan is not None and plan.student_id != student_id:
        raise ValueError("Plan belongs to a different student")
    context = _load_context(student_id, plan.program_id if plan else None)
    return _verify(context, course_id, term, plan or DegreePlan(student_id, context.program["program_id"]))


def add_course(plan: DegreePlan, course_id: str, term: str) -> DegreePlan:
    """Return an independent plan; reject additions that fail any check."""
    result = deepcopy(plan)
    context = _load_context(plan.student_id, plan.program_id)
    term_key(term)
    if course_id in _plan_ids(plan, term):
        return result
    failed = [c for c in _verify(context, course_id, term, plan) if not c.passed]
    if failed:
        result.warnings.extend(f"[verification] {course_id} {term}: {c.name}: {c.detail}" for c in failed)
        return result
    semester = next((s for s in result.semesters if s.term == term), None)
    if semester is None:
        semester = PlanSemester(term)
        result.semesters.append(semester)
        result.semesters.sort(key=lambda s: term_key(s.term))
    semester.courses.append(_course_dict(context, course_id))
    _audit(context, result)
    return result


def drop_course(plan: DegreePlan, course_id: str, term: str) -> DegreePlan:
    """Remove a course on a copy and flag dependents invalidated by the edit."""
    term_key(term)
    result = deepcopy(plan)
    for semester in result.semesters:
        if semester.term == term:
            semester.courses = [c for c in semester.courses if c["course_id"] != course_id]
    _audit(_load_context(plan.student_id, plan.program_id), result)
    return result


def _course_dict(context: "_Context", cid: str) -> dict:
    return {key: context.courses[cid][key] for key in ("course_id", "title", "credits")}


def _requirements_complete(context: "_Context", ids: set[str]) -> bool:
    return all(len(taken) >= slot.count for slot, taken in zip(context.slots, _allocation(context, ids)))


def _audit(context: "_Context", plan: DegreePlan) -> None:
    plan.warnings = [w for w in plan.warnings if not w.startswith(("[verification]", "[requirements]", "Schedule horizon"))]
    for semester in plan.semesters:
        for course in semester.courses:
            for check in _verify(context, course["course_id"], semester.term, plan):
                if not check.passed:
                    plan.warnings.append(f"[verification] {course['course_id']} {semester.term}: {check.name}: {check.detail}")
    allocation = _allocation(context, _passed(context) | _plan_ids(plan))
    for slot, taken in zip(context.slots, allocation):
        if len(taken) < slot.count:
            options = ", ".join(sorted(slot.options - taken)) or "no approved courses loaded"
            plan.warnings.append(f"[requirements] Unfilled {slot.label}: {options}. Check prerequisites, offerings, and credit caps.")


@dataclass
class _Slot:
    label: str
    options: set[str]
    hours: int
    count: int = 1


@dataclass
class _Context:
    student: dict
    program: dict
    courses: dict[str, dict]
    slots: list[_Slot]
    prerequisites: list[dict]
    completed: list[dict]
    sections: list[dict]
    enrollments: list[dict]


def _load_context(student_id: str, program_id: str | None = None) -> _Context:
    students = db.query("SELECT * FROM students WHERE student_id=:sid", {"sid": student_id})
    if not students:
        raise ValueError(f"Unknown student: {student_id}")
    student = students[0]
    pid = program_id or student["program_id"]
    programs = db.query("SELECT * FROM degree_programs WHERE program_id=:pid", {"pid": pid})
    if not programs:
        raise ValueError(f"Unknown program: {pid}")
    courses = {c["course_id"]: c for c in db.query("SELECT * FROM courses ORDER BY course_id")}
    slots = []
    for row in db.query("SELECT * FROM requirement_slots WHERE program_id=:pid ORDER BY slot_id", {"pid": pid}):
        options = [row["course_id"]] if row["course_id"] else json.loads(row["options"])
        # A category tag is not an explicit list of approved courses.
        if not isinstance(options, list):
            options = []
        slots.append(_Slot(f"slot {row['slot_id']}", set(options), row["credits"]))
    sections = db.query("SELECT * FROM sections ORDER BY section_id")
    enrollments = db.query(
        "SELECT s.* FROM enrollments e JOIN sections s USING (section_id) WHERE e.student_id=:sid",
        {"sid": student_id},
    )
    return _Context(student, programs[0], courses, slots,
                    db.query("SELECT * FROM prerequisites ORDER BY course_id, group_id, prereq_id"),
                    db.query("SELECT * FROM completed_courses WHERE student_id=:sid", {"sid": student_id}),
                    sections, enrollments)


_GRADE_POINTS = {"A+": 4.3, "A": 4, "A-": 3.7, "B+": 3.3, "B": 3, "B-": 2.7,
                 "C+": 2.3, "C": 2, "C-": 1.7, "D+": 1.3, "D": 1, "D-": 0.7}


def _grade_meets(grade: str, minimum: str) -> bool:
    # Unrecognized / incomplete / failed grades do not establish eligibility.
    return grade in _GRADE_POINTS and minimum in _GRADE_POINTS and _GRADE_POINTS[grade] >= _GRADE_POINTS[minimum]


def _passed(context: _Context) -> set[str]:
    return {r["course_id"] for r in context.completed
            if _grade_meets(r["grade"], "C" if context.courses[r["course_id"]]["dept"] == "CSE" else "D")}


def _plan_ids(plan: DegreePlan, term: str | None = None) -> set[str]:
    return {c["course_id"] for s in plan.semesters if term is None or s.term == term for c in s.courses}


def _allocation(context: _Context, course_ids: set[str]) -> list[set[str]]:
    """Maximum matching for fixed/elective slots; one course earns credit once."""
    units = [i for i, slot in enumerate(context.slots) for _ in range(slot.count)]
    owners: dict[str, int] = {}

    def assign(unit: int, seen: set[str]) -> bool:
        for cid in sorted(context.slots[units[unit]].options & course_ids & context.courses.keys()):
            if cid in seen:
                continue
            seen.add(cid)
            if cid not in owners or assign(owners[cid], seen):
                owners[cid] = unit
                return True
        return False

    for unit in sorted(range(len(units)), key=lambda u: (len(context.slots[units[u]].options), u)):
        assign(unit, set())
    result = [set() for _ in context.slots]
    for cid, unit in owners.items():
        result[units[unit]].add(cid)
    return result


def _credits(context: _Context, course_ids: set[str]) -> int:
    return sum(context.courses[cid]["credits"] for cid in course_ids)


def _prerequisite_failures(context: _Context, cid: str, term: str, plan: DegreePlan) -> list[str]:
    groups: dict[int, list[dict]] = {}
    for row in context.prerequisites:
        if row["course_id"] == cid:
            groups.setdefault(row["group_id"], []).append(row)
    earlier = {c["course_id"] for s in plan.semesters if term_key(s.term) < term_key(term) for c in s.courses}
    failures = []
    for alternatives in groups.values():
        satisfied = any(
            r["prereq_id"] in earlier or any(
                done["course_id"] == r["prereq_id"] and term_key(done["term"]) < term_key(term)
                and _grade_meets(done["grade"], r["min_grade"]) for done in context.completed)
            for r in alternatives
        )
        if not satisfied:
            failures.append(" or ".join(f"{r['prereq_id']} (grade {r['min_grade']}+)" for r in alternatives))
    return failures


def _overlap(a: dict, b: dict) -> bool:
    return bool(set(a["days"]) & set(b["days"])) and a["start_time"] < b["end_time"] and b["start_time"] < a["end_time"]


def _section_assignment(context: _Context, course_ids: set[str], term: str) -> dict[str, dict] | None:
    """Backtrack across section choices; current enrollments stay fixed."""
    fixed = {s["course_id"]: s for s in context.enrollments if s["term"] == term}
    choices = {}
    for cid in course_ids | fixed.keys():
        choices[cid] = [fixed[cid]] if cid in fixed else [
            s for s in context.sections if s["course_id"] == cid and s["term"] == term and s["capacity"] > 0]
    order = sorted(choices, key=lambda cid: (len(choices[cid]), cid))
    selected = {}

    def place(index: int) -> bool:
        if index == len(order):
            return True
        cid = order[index]
        for section in choices[cid]:
            if all(not _overlap(section, other) for other in selected.values()):
                selected[cid] = section
                if place(index + 1):
                    return True
                del selected[cid]
        return False

    return selected if place(0) else None


def _verify(context: _Context, cid: str, term: str, plan: DegreePlan) -> list[CheckResult]:
    if cid not in context.courses:
        return [CheckResult(name, False, f"Unknown course: {cid}") for name in CHECK_NAMES]
    planned = _plan_ids(plan)
    unknown = planned - context.courses.keys()
    if unknown:
        raise ValueError(f"Plan contains unknown courses: {', '.join(sorted(unknown))}")
    passed = _passed(context)
    enrolled = {s["course_id"] for s in context.enrollments}
    existing = (planned | passed | enrolled) - {cid}
    before = _allocation(context, existing)
    after = _allocation(context, existing | {cid})
    fulfills = sum(map(len, after)) > sum(map(len, before))
    prereqs = _prerequisite_failures(context, cid, term, plan)
    semester_ids = _plan_ids(plan, term) | {s["course_id"] for s in context.enrollments if s["term"] == term} | {cid}
    semester_credits = _credits(context, semester_ids)
    # Completed courses outside the target program do not consume its credit budget.
    applied_completed = set().union(*_allocation(context, passed)) if context.slots else set()
    degree_credits = _credits(context, applied_completed | planned | enrolled | {cid})
    semester_cap = context.student["max_credits_per_semester"]
    degree_cap = context.program["total_credits"]
    scheduled_elsewhere = any(s.term != term and any(c["course_id"] == cid for c in s.courses) for s in plan.semesters)
    scheduled_elsewhere |= any(s["course_id"] == cid and s["term"] != term for s in context.enrollments)
    schedule_ok = _section_assignment(context, semester_ids, term) is not None
    return [
        CheckResult(CHECK_NAMES[0], not prereqs, "Missing: " + "; ".join(prereqs) if prereqs else
                    "Prerequisites satisfied; earlier planned courses must be passed."),
        CheckResult(CHECK_NAMES[1], cid not in passed and not scheduled_elsewhere,
                    "Already passed or planned in another term." if cid in passed or scheduled_elsewhere else "Not already passed or planned elsewhere."),
        CheckResult(CHECK_NAMES[2], fulfills, "Fills an unfilled degree requirement." if fulfills else
                    "No unfilled requirement accepts this course; check requirement data."),
        CheckResult(CHECK_NAMES[3], schedule_ok, "A conflict-free section combination exists." if schedule_ok else
                    f"No conflict-free offered section combination in {term}; missing offerings also fail this check."),
        CheckResult(CHECK_NAMES[4], semester_credits <= semester_cap, f"{semester_credits}/{semester_cap} semester credits."),
        CheckResult(CHECK_NAMES[5], degree_credits <= degree_cap, f"{degree_credits}/{degree_cap} degree credits (applicable completed + planned/enrolled)."),
    ]
