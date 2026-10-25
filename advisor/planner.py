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

    Prerequisites must occur earlier unless explicitly allowed concurrently.
    Terms beyond the published schedule use marked catalog projections.
    Incomplete requirements or an infeasible graph return a partial plan with
    explicit warnings.
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
    mandatory = set().union(*(slot.options for slot in context.slots
                              if slot.count and slot.count >= len(slot.options)))
    pending = list(mandatory)
    while pending:
        course = pending.pop()
        groups: dict[int, list[dict]] = {}
        for row in context.prerequisites:
            if row["course_id"] == course:
                groups.setdefault(row["group_id"], []).append(row)
        for alternatives in groups.values():
            if any(any(done["course_id"] == row["prereq_id"] and _grade_meets(done["grade"], row["min_grade"])
                       for done in context.completed) for row in alternatives):
                continue
            options = {row["prereq_id"] for row in alternatives}
            if len(options) == 1:
                for prerequisite in options - mandatory:
                    mandatory.add(prerequisite)
                    pending.append(prerequisite)
    order = sorted(candidates, key=lambda cid: (cid not in mandatory, -descendants(cid), cid))
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
            # Do not spend an elective slot needed by an unavoidable future prerequisite.
            reserved = _passed(context) | _plan_ids(plan) | mandatory
            if cid not in mandatory and _coverage(context, _allocation(context, reserved | {cid})) <= _coverage(context, _allocation(context, reserved)):
                continue
            for bundle in _corequisite_bundles(context, cid, term, plan):
                if courses_per_semester is not None and len(semester.courses) + len(bundle) > courses_per_semester:
                    continue
                trial = deepcopy(plan)
                trial.semesters[-1].courses.extend(_course_dict(context, c) for c in sorted(bundle))
                if all(check.passed for c in sorted(bundle) for check in _verify(context, c, term, trial)):
                    semester.courses.extend(_course_dict(context, c) for c in sorted(bundle))
                    break
        if _requirements_complete(context, _passed(context) | _plan_ids(plan)):
            break
    while plan.semesters and not plan.semesters[-1].courses:
        plan.semesters.pop()
    _audit(context, plan)
    if not _requirements_complete(context, _passed(context) | _plan_ids(plan)):
        plan.warnings.append(f"Planning window ends at {terms[-1]}"
                             + (f" (projected past {context.last_real_term});" if context.last_real_term else ";")
                             + " requirements remain unfilled.")
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
    return add_courses(plan, [course_id], term)


def add_courses(plan: DegreePlan, course_ids: list[str], term: str) -> DegreePlan:
    """Validate additions together so requested corequisites can share a term."""
    context = _load_context(plan.student_id, plan.program_id)
    term_key(term)
    result = deepcopy(plan)
    additions = sorted(set(course_ids) - _plan_ids(plan, term))
    if not additions:
        return result
    unknown = set(additions) - context.courses.keys()
    if unknown:
        result.warnings.append("[verification] Unknown courses: " + ", ".join(sorted(unknown)))
        return result
    semester = next((s for s in result.semesters if s.term == term), None)
    if semester is None:
        semester = PlanSemester(term)
        result.semesters.append(semester)
        result.semesters.sort(key=lambda s: term_key(s.term))
    semester.courses.extend(_course_dict(context, cid) for cid in additions)
    failures = [f"[verification] {cid} {term}: {check.name}: {check.detail}"
                for cid in additions for check in _verify(context, cid, term, result) if not check.passed]
    if failures:
        result = deepcopy(plan)
        result.warnings.extend(failures)
        return result
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


def revalidate_plan(plan: DegreePlan) -> DegreePlan:
    """Recompute warnings on a copy, including after loading a saved plan."""
    result = deepcopy(plan)
    _audit(_load_context(plan.student_id, plan.program_id), result)
    return result


def _course_dict(context: "_Context", cid: str) -> dict:
    return {key: context.courses[cid][key] for key in ("course_id", "title", "credits")}


def _requirements_complete(context: "_Context", ids: set[str]) -> bool:
    return all(_slot_complete(context, slot, taken)
               for slot, taken in zip(context.slots, _allocation(context, ids), strict=False))


def _slot_complete(context: "_Context", slot: "_Slot", taken: set[str]) -> bool:
    return len(taken) >= slot.count if slot.count else _credits(context, taken) >= slot.hours


def _audit(context: "_Context", plan: DegreePlan) -> None:
    plan.warnings = [w for w in plan.warnings
                     if not w.startswith(("[verification]", "[requirements]", "Planning window", "[projection]"))]
    if not context.slots:
        plan.warnings.append("[requirements] No degree requirement slots are loaded.")
    for semester in plan.semesters:
        for course in semester.courses:
            for check in _verify(context, course["course_id"], semester.term, plan):
                if not check.passed:
                    plan.warnings.append(f"[verification] {course['course_id']} {semester.term}: {check.name}: {check.detail}")
    if context.last_real_term and any(
            s.courses and term_key(s.term) > term_key(context.last_real_term) for s in plan.semesters):
        plan.warnings.append(f"[projection] Terms after {context.last_real_term} assume catalog offering"
                             " patterns (1000/2000-level every term; 3000+ Fall/Spring);"
                             " meeting times are not published.")
    allocation = _allocation(context, _passed(context) | _plan_ids(plan))
    for slot, taken in zip(context.slots, allocation, strict=False):
        if not _slot_complete(context, slot, taken):
            options = ", ".join(sorted(slot.options - taken)) or "no approved courses loaded"
            plan.warnings.append(f"[requirements] Unfilled {slot.label}: {options}. Check prerequisites, offerings, and credit caps.")


@dataclass
class _Slot:
    label: str
    options: set[str]
    hours: int
    count: int = 1  # zero means a credit-hour bucket
    category: str = ""


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
    concurrent: set[tuple[str, str]] = field(default_factory=set)
    last_real_term: str | None = None


# The published schedule only covers a few terms. Beyond it, the catalog implies
# lower-division courses are offered every term and upper-division at least
# Fall/Spring, so the planner assumes offerings on that pattern (marked
# "projected": meeting days/times are unknown and never certify a conflict).
PROJECTED_TERMS = 18


def _course_level(course: dict) -> int:
    number = str(course["number"]).lstrip()
    return int(number[0]) if number[:1].isdigit() else 3


def _projected_sections(courses: dict[str, dict], last_term: str) -> list[dict]:
    out = []
    for term in next_terms(last_term, PROJECTED_TERMS, include_summer=True):
        summer = term.startswith("SU")
        for cid, course in courses.items():
            if _course_level(course) < 3 or not summer:
                out.append({"section_id": f"{cid}-{term}-projected", "course_id": cid,
                            "term": term, "days": "", "start_time": "", "end_time": "",
                            "instructor": "", "capacity": 1, "projected": True})
    return out


def _table_exists(name: str) -> bool:
    return bool(db.query("SELECT name FROM sqlite_master WHERE type='table' AND name=:t", {"t": name}))


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
    rows = db.query("SELECT * FROM requirement_slots WHERE program_id=:pid ORDER BY slot_id", {"pid": pid})
    for row in rows:
        options = [row["course_id"]] if row["course_id"] else json.loads(row["options"])
        # build_seed_data.expand_slots encodes an open elective as NULL + [].
        # Other empty categories and unresolved category tags stay unfilled.
        is_open = row["category"] == "elective" and not row["course_id"] and options == []
        if is_open:
            options = [cid for cid, course in courses.items() if course["credits"] > 0]
        elif not isinstance(options, list):
            options = []
        slots.append(_Slot(f"slot {row['slot_id']}", set(options), row["credits"],
                           count=0 if is_open else 1, category=row["category"]))
    sections = db.query("SELECT * FROM sections ORDER BY section_id")
    last_real_term = max((s["term"] for s in sections), key=term_key, default=None)
    if last_real_term is not None:
        sections = sections + _projected_sections(courses, last_real_term)
    enrollment_rows = db.query(
        "SELECT e.*, s.course_id, s.term AS section_term, s.days, s.start_time, s.end_time, s.capacity"
        " FROM enrollments e JOIN sections s USING (section_id) WHERE e.student_id=:sid",
        {"sid": student_id},
    )
    completed = db.query("SELECT * FROM completed_courses WHERE student_id=:sid", {"sid": student_id})
    enrollments = []
    for row in enrollment_rows:
        row["term"] = row["section_term"]  # Data branch also has a human-readable enrollment term.
        if row.get("status") == "completed":
            if not any((r["course_id"], r["term"], r["grade"]) ==
                       (row["course_id"], row["term"], row["grade"]) for r in completed):
                completed.append(row)
        else:
            enrollments.append(row)
    program = programs[0]
    if "total_hours" in program:
        program["total_credits"] = program["total_hours"]
    prerequisites = db.query("SELECT * FROM prerequisites ORDER BY course_id, group_id, prereq_id")
    # prereq_concurrent (Jordan's additive table) marks pairs that may be
    # satisfied by a course taken in the same term.
    concurrent = {(r["course_id"], r["prereq_id"])
                  for r in (db.query("SELECT * FROM prereq_concurrent")
                            if _table_exists("prereq_concurrent") else [])}
    return _Context(student, program, courses, slots, prerequisites,
                    completed, sections, enrollments, concurrent, last_real_term)


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
    """Match fixed/choice/hour requirements without counting a course twice.

    Equal-credit buckets participate in the same augmenting-path matching as
    fixed slots, so a scarce course can move between either kind of requirement.
    Mixed-credit buckets use a subset-sum pass after the count requirements.
    """
    units, mixed = [], []
    for i, slot in enumerate(context.slots):
        if slot.count:
            units.extend([i] * slot.count)
        else:
            credits = {context.courses[c]["credits"] for c in slot.options & course_ids & context.courses.keys()}
            if not credits:
                continue
            count = (slot.hours + min(credits) - 1) // min(credits)
            # If every combination of count courses fills the bucket and fewer
            # cannot, this is an ordinary matching problem even with mixed credits.
            if max(credits) * (count - 1) < slot.hours:
                units.extend([i] * count)
            else:
                mixed.append(i)
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
    used = set(owners)
    # Fill hour buckets after fixed/choose_n slots, reserving scarce options.
    buckets = sorted(mixed, key=lambda i: (len(context.slots[i].options), i))
    for i in buckets:
        slot = context.slots[i]
        choices = sorted((slot.options & course_ids & context.courses.keys()) - used,
                         key=lambda cid: (sum(cid in context.slots[j].options for j in buckets if j != i), cid))
        sums = {0: set()}
        for cid in choices:
            for total, selected in list(sums.items()):
                hours = total + context.courses[cid]["credits"]
                if total < slot.hours and hours not in sums:
                    sums[hours] = selected | {cid}
        enough = [hours for hours in sums if hours >= slot.hours]
        result[i] = sums[min(enough) if enough else max(sums)]
        used.update(result[i])
    return result


def requirement_progress(student_id: str, program_id: str, plan: DegreePlan | None = None) -> list[dict]:
    """Report category credits using the same allocation as plan verification.

    Passing records count as completed; plan courses and current enrollments
    count as planned. Each course contributes to at most one requirement.
    """
    context = _load_context(student_id, program_id)
    done = _passed(context)
    planned = (_plan_ids(plan) if plan else set()) | {r["course_id"] for r in context.enrollments}
    allocation = _allocation(context, done | planned)
    out: dict[str, dict] = {}
    for slot, taken in zip(context.slots, allocation, strict=True):
        row = out.setdefault(slot.category, {"category": slot.category, "required": 0,
                                            "completed": 0, "planned": 0})
        completed = min(slot.hours, _credits(context, taken & done))
        row["required"] += slot.hours
        row["completed"] += completed
        row["planned"] += min(slot.hours - completed, _credits(context, taken - done))
    return list(out.values())


def _coverage(context: _Context, allocation: list[set[str]]) -> int:
    return sum(len(taken) if slot.count else min(slot.hours, _credits(context, taken))
               for slot, taken in zip(context.slots, allocation, strict=False))


def _credits(context: _Context, course_ids: set[str]) -> int:
    return sum(context.courses[cid]["credits"] for cid in course_ids)


def _prerequisite_failures(context: _Context, cid: str, term: str, plan: DegreePlan) -> list[str]:
    groups: dict[int, list[dict]] = {}
    for row in context.prerequisites:
        if row["course_id"] == cid:
            groups.setdefault(row["group_id"], []).append(row)
    failures = []
    for alternatives in groups.values():
        if not any(_prereq_satisfied(context, r, term, plan) for r in alternatives):
            failures.append("prereq: " + " or ".join(
                f"{r['prereq_id']} (grade {r['min_grade']}+"
                f"{'; concurrent OK' if (r['course_id'], r['prereq_id']) in context.concurrent else ''})"
                for r in alternatives))
    return failures


def _prereq_satisfied(context: _Context, row: dict, term: str, plan: DegreePlan) -> bool:
    concurrent = (row["course_id"], row["prereq_id"]) in context.concurrent
    for semester in plan.semesters:
        eligible_term = term_key(semester.term) < term_key(term) or (concurrent and semester.term == term)
        if eligible_term and any(c["course_id"] == row["prereq_id"] for c in semester.courses):
            return True
    if concurrent and any(s["course_id"] == row["prereq_id"] and s["term"] == term for s in context.enrollments):
        return True
    return any(done["course_id"] == row["prereq_id"] and term_key(done["term"]) < term_key(term)
               and _grade_meets(done["grade"], row["min_grade"]) for done in context.completed)


def _corequisite_bundles(context: _Context, cid: str, term: str, plan: DegreePlan):
    """Enumerate bundles that fill the candidate's unsatisfied prerequisites.

    Only prereq_concurrent pairs can be pulled into the bundle; other missing
    prereqs leave the candidate for a later term.
    """
    seen: set[frozenset[str]] = set()

    def expand(bundle: set[str]):
        key = frozenset(bundle)
        if key in seen:
            return
        seen.add(key)
        trial = deepcopy(plan)
        semester = next(s for s in trial.semesters if s.term == term)
        semester.courses.extend(_course_dict(context, c) for c in sorted(bundle))
        for course in sorted(bundle):
            groups: dict[int, list[dict]] = {}
            for row in context.prerequisites:
                if row["course_id"] == course:
                    groups.setdefault(row["group_id"], []).append(row)
            for alternatives in groups.values():
                if not any(_prereq_satisfied(context, row, term, trial) for row in alternatives):
                    for row in alternatives:
                        prerequisite = row["prereq_id"]
                        if ((row["course_id"], prerequisite) in context.concurrent
                                and prerequisite in context.courses and prerequisite not in bundle):
                            yield from expand(bundle | {prerequisite})
                    return
        yield bundle

    yield from expand({cid})


def _overlap(a: dict, b: dict) -> bool:
    return bool(set(a["days"]) & set(b["days"])) and a["start_time"] < b["end_time"] and b["start_time"] < a["end_time"]


def _known_meeting(section: dict) -> bool:
    time_pattern = r"(?:[01][0-9]|2[0-3]):[0-5][0-9]"
    return (bool(section["days"]) and set(section["days"]) <= set("MTWRFSU")
            and re.fullmatch(time_pattern, section["start_time"]) is not None
            and re.fullmatch(time_pattern, section["end_time"]) is not None
            and section["start_time"] < section["end_time"])


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
            # Projected offerings have unknown meeting times; they cannot be
            # certified conflict-free, but they must not block a term either.
            if section.get("projected") or (_known_meeting(section)
                                            and all(not _overlap(section, other) for other in selected.values())):
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
    # An added elective must not strand an already-counted plan course or
    # overfill its hour bucket and spend credits needed by the rest of the degree.
    allocated_before = set().union(*before)
    allocated_after = set().union(*after)
    preserves_plan = ((planned | enrolled) & allocated_before) <= allocated_after
    overfills = any(not slot.count and cid in taken and _credits(context, taken) > slot.hours
                    for slot, taken in zip(context.slots, after, strict=True))
    fulfills = _coverage(context, after) > _coverage(context, before) and preserves_plan and not overfills
    prereqs = _prerequisite_failures(context, cid, term, plan)
    semester_ids = _plan_ids(plan, term) | {s["course_id"] for s in context.enrollments if s["term"] == term} | {cid}
    semester_credits = _credits(context, semester_ids)
    # Completed courses outside the target program do not consume its credit budget.
    applied_completed = allocated_after & passed
    degree_credits = _credits(context, applied_completed | planned | enrolled | {cid})
    semester_cap = context.student["max_credits_per_semester"]
    degree_cap = context.program["total_credits"]
    scheduled_elsewhere = any(s.term != term and any(c["course_id"] == cid for c in s.courses) for s in plan.semesters)
    scheduled_elsewhere |= any(s["course_id"] == cid and s["term"] != term for s in context.enrollments)
    scheduled_elsewhere |= sum(c["course_id"] == cid for s in plan.semesters for c in s.courses) > 1
    assignment = _section_assignment(context, semester_ids, term)
    schedule_ok = assignment is not None
    if schedule_ok:
        schedule_detail = ("Assumed offered beyond the published schedule; meeting times are not yet available."
                           if assignment[cid].get("projected") else
                           "A conflict-free section combination exists.")
    else:
        schedule_detail = f"No conflict-free offered section combination in {term}; missing offerings also fail this check."
    return [
        CheckResult(CHECK_NAMES[0], not prereqs, "Missing: " + "; ".join(prereqs) if prereqs else
                    "Prerequisites satisfied; earlier planned courses must be passed."),
        CheckResult(CHECK_NAMES[1], cid not in passed and not scheduled_elsewhere,
                    "Already passed or planned in another term." if cid in passed or scheduled_elsewhere else "Not already passed or planned elsewhere."),
        CheckResult(CHECK_NAMES[2], fulfills, "Fills an unfilled degree requirement." if fulfills else
                    "No unfilled requirement accepts this course; check requirement data."),
        CheckResult(CHECK_NAMES[3], schedule_ok, schedule_detail),
        CheckResult(CHECK_NAMES[4], semester_credits <= semester_cap, f"{semester_credits}/{semester_cap} semester credits."),
        CheckResult(CHECK_NAMES[5], degree_credits <= degree_cap, f"{degree_credits}/{degree_cap} degree credits (applicable completed + planned/enrolled)."),
    ]
