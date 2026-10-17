"""Degree Planner + Verification Engine (Person B).

DETERMINISTIC — no LLM calls in this module. The planner topologically orders
the prerequisite DAG over the student's remaining requirement slots and packs
courses into semesters subject to credit caps and schedule feasibility.

The degree-plan JSON contract (consumed by app.py, compare.py, tools.py):

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

from dataclasses import dataclass, field

# Term ordering helpers. Terms: 'F2026', 'S2027', 'SU2027'.
TERM_SEASON_ORDER = {"S": 0, "SU": 1, "F": 2}


def term_key(term: str) -> tuple[int, int]:
    """Sort key for term strings like 'F2026'."""
    season = "SU" if term.startswith("SU") else term[0]
    year = int(term[len(season):])
    return (year, TERM_SEASON_ORDER[season])


def next_terms(start: str, n: int, include_summer: bool = False) -> list[str]:
    """Next n terms after `start` in chronological order (excl. start)."""
    seasons = ["S", "SU", "F"] if include_summer else ["S", "F"]
    year, order = term_key(start)
    si = seasons.index(("S", "SU", "F")[order])
    out, yy = [], year
    while len(out) < n:
        si += 1
        if si >= len(seasons):
            si, yy = 0, yy + 1
        out.append(f"{seasons[si]}{yy}")
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

    TODO (Person B): implement.
    """
    raise NotImplementedError("TODO Person B: implement generate_plan")


def verify_course(student_id: str, course_id: str, term: str, plan: DegreePlan | None = None) -> list[CheckResult]:
    """Run ALL six verification checks (spec req 4) before recommending
    `course_id` for `term`. Returns one CheckResult per check in CHECK_NAMES
    order — the UI renders these as a pass/fail table.

    TODO (Person B): implement.
    """
    raise NotImplementedError("TODO Person B: implement verify_course")


def add_course(plan: DegreePlan, course_id: str, term: str) -> DegreePlan:
    """Return a new plan with `course_id` added to `term` (spec req 3 add-class).
    Must re-run the six checks; failures land in plan.warnings.

    TODO (Person B): implement.
    """
    raise NotImplementedError("TODO Person B: implement add_course")


def drop_course(plan: DegreePlan, course_id: str, term: str) -> DegreePlan:
    """Return a new plan with `course_id` removed from `term`.

    TODO (Person B): implement.
    """
    raise NotImplementedError("TODO Person B: implement drop_course")
