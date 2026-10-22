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
    """Generate a multi-year degree plan for `student_id`.

    Steps (spec req 2):
      1. Load the student's program requirement slots and completed courses.
      2. Compute remaining required courses.
      3. Topologically sort by prerequisites (a course is schedulable once all
         its prereq groups are satisfied by completed/earlier-planned courses).
      4. Pack into chronological terms, respecting each student's
         max_credits_per_semester, offered sections (sections.term), and the
         program total-credit cap. Honor courses_per_semester / include_summer.
      5. Record warnings for anything that couldn't be placed.

    TODO (Loc): implement.
    """
    raise NotImplementedError("TODO Loc: implement generate_plan")


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
    """Return a new plan with `course_id` added to `term` (spec req 3 add-class).
    Must re-run the six checks; failures land in plan.warnings.

    TODO (Loc): implement.
    """
    raise NotImplementedError("TODO Loc: implement add_course")


def drop_course(plan: DegreePlan, course_id: str, term: str) -> DegreePlan:
    """Return a new plan with `course_id` removed from `term`.

    TODO (Loc): implement.
    """
    raise NotImplementedError("TODO Loc: implement drop_course")


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
