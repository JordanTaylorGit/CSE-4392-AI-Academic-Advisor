"""Plan comparison (Person B) — spec req 5(c): comparing a new plan to the
existing plan (e.g. after a major switch or plan edit)."""

from .planner import DegreePlan


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

    TODO (Person B): implement.
    """
    raise NotImplementedError("TODO Person B: implement diff_plans")
