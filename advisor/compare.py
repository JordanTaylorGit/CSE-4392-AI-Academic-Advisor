"""Plan comparison (Loc) — spec req 5(c): comparing a new plan to the
existing plan (e.g. after a major switch or plan edit)."""

from .planner import DegreePlan, term_key


def diff_plans(old: DegreePlan, new: DegreePlan) -> dict:
    """Return a structured diff between two plans:

        {
          "added":   [{"term": str, "course_id": str}, ...],
          "removed": [{"term": str, "course_id": str}, ...],
          "moved":   [{"course_id": str, "from": str, "to": str}, ...],
          "semesters_added": int,        # new.plan - old.plan length delta
          "credits_delta": int,
          "summary": str,                # human-readable paragraph for the UI
        }

    """
    if old.student_id != new.student_id:
        raise ValueError("Cannot compare plans belonging to different students")

    def locations(plan):
        result = {}
        for semester in plan.semesters:
            for course in semester.courses:
                cid = course["course_id"]
                if cid in result:
                    raise ValueError(f"Duplicate planned course: {cid}")
                result[cid] = semester.term
        return result

    before, after = locations(old), locations(new)
    added = [{"term": after[cid], "course_id": cid} for cid in after.keys() - before.keys()]
    removed = [{"term": before[cid], "course_id": cid} for cid in before.keys() - after.keys()]
    moved = [{"course_id": cid, "from": before[cid], "to": after[cid]}
             for cid in sorted(before.keys() & after.keys()) if before[cid] != after[cid]]
    for changes in (added, removed):
        changes.sort(key=lambda r: (term_key(r["term"]), r["course_id"]))
    semesters_added = len(new.semesters) - len(old.semesters)
    credits_delta = sum(s.credits for s in new.semesters) - sum(s.credits for s in old.semesters)
    summary = []
    if old.program_id != new.program_id:
        summary.append(f"Program changes from {old.program_id} to {new.program_id}.")
    summary.append(f"{len(added)} courses added, {len(removed)} removed, {len(moved)} moved; "
                   f"{semesters_added:+d} semesters and {credits_delta:+d} planned credits.")
    if after:
        summary.append(f"Last planned term: {max(after.values(), key=term_key)}.")
    if new.warnings:
        summary.append(f"The new plan has {len(new.warnings)} warnings; review them before using it.")
    return {"added": added, "removed": removed, "moved": moved,
            "semesters_added": semesters_added, "credits_delta": credits_delta,
            "summary": " ".join(summary)}
