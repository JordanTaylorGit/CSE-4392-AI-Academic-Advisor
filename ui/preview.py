"""Preview data for the UI (Person E) — used ONLY while the planner/compare
modules are stubs, and always shown with a "preview" banner in the UI.

This is NOT a degree planner: it orders courses by course number, ignores
prerequisites and schedules, and leaves most verification checks pending.
Person B's planner.py replaces all of it automatically once implemented.
"""

from advisor import db, planner

PENDING = "The planner runs this check once it is built."


def _terms(include_summer: bool) -> list[str]:
    """First scheduled term onward (next_terms() excludes its start term)."""
    rows = db.query("SELECT DISTINCT term FROM sections")
    first = min((r["term"] for r in rows), key=planner.term_key, default="F2026")
    return [first] + planner.next_terms(first, 20, include_summer)


def plan(student_id: str, program_id: str, include_summer: bool,
         courses_per_semester: int | None) -> dict:
    student = db.query("SELECT * FROM students WHERE student_id = :sid", {"sid": student_id})[0]
    total = db.query("SELECT total_credits FROM degree_programs WHERE program_id = :p",
                     {"p": program_id})[0]["total_credits"]
    done = db.query(
        "SELECT c.course_id, c.credits FROM completed_courses cc JOIN courses c USING (course_id)"
        " WHERE cc.student_id = :sid", {"sid": student_id})
    done_ids = {r["course_id"] for r in done}
    remaining_credits = total - sum(r["credits"] for r in done)

    pool = [c for c in db.query(
        "SELECT course_id, title, credits FROM courses ORDER BY number, dept")
        if c["course_id"] not in done_ids]

    cap = student["max_credits_per_semester"]
    per_sem = courses_per_semester or 5
    terms = iter(_terms(include_summer))
    semesters, current, planned = [], [], 0
    for c in pool:
        if planned + c["credits"] > remaining_credits:
            break
        if len(current) >= per_sem or sum(x["credits"] for x in current) + c["credits"] > cap:
            semesters.append({"term": next(terms), "courses": current})
            current = []
        current.append(dict(c))
        planned += c["credits"]
    if current:
        semesters.append({"term": next(terms), "courses": current})
    for s in semesters:
        s["credits"] = sum(c["credits"] for c in s["courses"])
    return {
        "student_id": student_id,
        "program_id": program_id,
        "semesters": semesters,
        "total_credits_planned": planned,
        "warnings": [],  # the UI's preview banner already says this is placeholder data
    }


def checks(student_id: str, course_id: str) -> list[dict]:
    passed = db.query(
        "SELECT grade, term FROM completed_courses WHERE student_id = :sid AND course_id = :cid",
        {"sid": student_id, "cid": course_id})
    out = []
    for name in planner.CHECK_NAMES:
        if name == "not_already_passed":
            out.append({"name": name, "passed": not passed,
                        "detail": (f"Completed {passed[0]['term']} with {passed[0]['grade']}"
                                   if passed else "Not on the student's transcript")})
        else:
            out.append({"name": name, "passed": None, "detail": PENDING})
    return out


def _recount(p: dict) -> dict:
    for s in p["semesters"]:
        s["credits"] = sum(c["credits"] for c in s["courses"])
    p["semesters"] = [s for s in p["semesters"] if s["courses"]]
    p["total_credits_planned"] = sum(s["credits"] for s in p["semesters"])
    return p


def add(p: dict, course_id: str, term: str) -> dict:
    c = db.query("SELECT course_id, title, credits FROM courses WHERE course_id = :cid",
                 {"cid": course_id})[0]
    new = {**p, "semesters": [{**s, "courses": list(s["courses"])} for s in p["semesters"]]}
    sem = next((s for s in new["semesters"] if s["term"] == term), None)
    if sem is None:
        sem = {"term": term, "courses": []}
        new["semesters"].append(sem)
        new["semesters"].sort(key=lambda s: planner.term_key(s["term"]))
    sem["courses"].append(dict(c))
    return _recount(new)


def drop(p: dict, course_id: str, term: str) -> dict:
    new = {**p, "semesters": [
        {**s, "courses": [c for c in s["courses"]
                          if not (s["term"] == term and c["course_id"] == course_id)]}
        for s in p["semesters"]]}
    return _recount(new)


def diff(old: dict, new: dict) -> dict:
    def where(p):
        return {c["course_id"]: s["term"] for s in p["semesters"] for c in s["courses"]}

    o, n = where(old), where(new)
    added = [{"term": n[c], "course_id": c} for c in n if c not in o]
    removed = [{"term": o[c], "course_id": c} for c in o if c not in n]
    moved = [{"course_id": c, "from": o[c], "to": n[c]} for c in o if c in n and o[c] != n[c]]
    sem_delta = len(new["semesters"]) - len(old["semesters"])
    cred_delta = new["total_credits_planned"] - old["total_credits_planned"]
    return {
        "added": added, "removed": removed, "moved": moved,
        "semesters_added": sem_delta, "credits_delta": cred_delta,
        "summary": (f"Preview diff: {len(added)} added, {len(removed)} removed, "
                    f"{len(moved)} moved; {sem_delta:+d} semesters, {cred_delta:+d} credits."),
    }


# ------------------------------------------------- requirement rings (mock)

# Category credit totals per program, matching seed/requirement_slots.json
# (CS + Cybersecurity = 123, SE + AI = 127). "concentration" is the certificate.
CATEGORY_CREDITS = {
    "bs_cs_cyber": {"core": 28, "math_science": 19, "cse_core": 49, "concentration": 12, "elective": 15},
    "bs_se_ai": {"core": 28, "math_science": 23, "cse_core": 64, "concentration": 12},
}
# Fixed CSE courses and certificate courses from the same seed, used only to sort
# courses into categories here.
_CSE_SHARED = {"CSE 1106", "CSE 1310", "CSE 1320", "CSE 1325", "CSE 2312", "CSE 2315", "CSE 3302",
               "CSE 3310", "CSE 3314", "CSE 3315", "CSE 3318", "CSE 3320", "CSE 3330", "CSE 4316",
               "CSE 4317"}
PROGRAM_COURSES = {
    "bs_cs_cyber": {
        "cse_core": _CSE_SHARED,
        "concentration": {"CSE 4344", "CSE 4352", "CSE 4380", "CSE 4381", "CSE 4382"},
    },
    "bs_se_ai": {
        "cse_core": _CSE_SHARED | {"CSE 3311", "CSE 4321", "CSE 4322", "CSE 4361", "CSE 4380"},
        "concentration": {"CSE 4308", "CSE 4309", "CSE 4310", "CSE 4311"},
    },
}


def _category(program_id: str, course_id: str) -> str:
    lists = PROGRAM_COURSES.get(program_id, {})
    for cat in ("cse_core", "concentration"):
        if course_id in lists.get(cat, ()):
            return cat
    dept = course_id.split()[0]
    if dept in ("MATH", "PHYS"):
        return "math_science"
    if dept in ("ENGL", "HIST", "POLS"):
        return "core"
    return "elective"


def requirements(student_id: str, program_id: str, current: dict | None) -> list[dict]:
    """Per-category credits completed / planned, sorted by the degree docs' course lists."""
    credits = CATEGORY_CREDITS.get(program_id, CATEGORY_CREDITS["bs_cs_cyber"])
    out = {c: {"category": c, "required": n, "completed": 0, "planned": 0}
           for c, n in credits.items()}
    done = db.query("SELECT c.course_id, c.credits FROM completed_courses cc JOIN courses c "
                    "USING (course_id) WHERE cc.student_id = :sid", {"sid": student_id})
    def bucket(course_id: str) -> dict:  # SE has no elective area; those count as core
        return out.get(_category(program_id, course_id), out["core"])

    for r in done:
        bucket(r["course_id"])["completed"] += r["credits"]
    for s in (current or {}).get("semesters", []):
        for c in s["courses"]:
            bucket(c["course_id"])["planned"] += c["credits"]
    return list(out.values())


# --------------------------------------------------------- chat answers (mock)

STOP = {"which", "what", "courses", "course", "cover", "covers", "about", "that", "with", "there",
        "does", "have", "take", "teach", "classes", "class", "any", "are", "the", "for"}


def chat_reply(student_id: str, prompt: str, current: dict | None) -> dict:
    """Keyword-routed placeholder answers in the reply shape the UI accepts from the
    orchestrator: {"text": str, "cards": [...]} (see ui/README.md)."""
    import re

    student = db.query("SELECT * FROM students WHERE student_id = :sid", {"sid": student_id})[0]
    pid = (current or {}).get("program_id", student["program_id"])
    q = prompt.lower()
    code = re.search(r"\b([a-z]{3,4})\s?(\d{4})\b", q)
    cid = f"{code.group(1).upper()} {code.group(2)}" if code else None
    first_term = _terms(False)[0]

    if "switch" in q or "change my major" in q:
        others = [p["program_id"] for p in db.query("SELECT program_id FROM degree_programs")
                  if p["program_id"] != student["program_id"]]
        old = current or plan(student_id, student["program_id"], False, None)
        new = plan(student_id, others[0], False, None)
        return {"text": "Here is how your plan would change if you switched. Look at the extra "
                        "courses and whether your graduation date moves before deciding.",
                "cards": [{"type": "diff", "old": old, "new": new, "diff": diff(old, new)}]}
    if cid and ("take" in q or "eligib" in q or "can i" in q):
        return {"text": f"Here are the six checks for {cid} in your next semester.",
                "cards": [{"type": "checks", "course_id": cid, "term": first_term,
                           "checks": checks(student_id, cid)}]}
    if "plan" in q or "build" in q or "graduat" in q:
        p = current or plan(student_id, pid, False, None)
        return {"text": "I built a semester-by-semester plan to graduation. Open it to see "
                        "every course, or ask me to change the load or add summer terms.",
                "cards": [{"type": "plan", "plan": p}]}
    if cid:
        rows = db.query("SELECT course_id, title, credits, description FROM courses "
                        "WHERE course_id = :cid", {"cid": cid})
        if rows:
            return {"text": f"Here is what I have on {cid}. Prerequisite data isn't loaded yet, "
                            "so I can't list its prerequisites.",
                    "cards": [{"type": "courses", "courses": rows}]}
    words = [w for w in re.findall(r"[a-z]+", q) if len(w) > 3 and w not in STOP]
    if words:
        rows = db.query("SELECT course_id, title, credits, description FROM courses")
        hits = [r for r in rows
                if all(w in (r["title"] + " " + r["description"]).lower() for w in words)]
        if hits:
            return {"text": f"{len(hits)} course{'s' if len(hits) != 1 else ''} match "
                            f"\"{' '.join(words)}\":", "cards": [{"type": "courses", "courses": hits[:6]}]}
    return {"text": "I can build your degree plan, check whether you can take a course, find "
                    "courses on a topic, or compare switching majors. Try one of those.",
            "cards": []}
