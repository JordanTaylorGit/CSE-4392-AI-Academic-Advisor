"""RAG chain + SQL tool chain (Miguel/Kyle).

- answer_semantic: retrieval over Chroma (catalog chunks, degree-req docs,
  policies) grounded answer generation.
- answer_exact: structured lookups against SQLite (prereqs, schedule, student
  record). Prefer deterministic SQL helpers here over letting the LLM write
  SQL — exact queries have known shapes.
"""

import re

from .paths import CHROMA_DIR

COLLECTION = "advisor"


def get_vectorstore():
    """Return the Chroma vectorstore for the configured embeddings backend."""
    from langchain_chroma import Chroma

    from .config import get_embeddings

    return Chroma(
        collection_name=COLLECTION,
        persist_directory=str(CHROMA_DIR),
        embedding_function=get_embeddings(),
    )


def answer_semantic(query: str, student_id: str | None = None, k: int = 5) -> str:
    """Answer a semantic/unstructured query via RAG.

    Retrieve top-k chunks from Chroma (trace the hits via tracing.trace
    'retrieval' with doc ids + scores), then answer with the chat model using
    ONLY retrieved context; say "I don't know" when context is insufficient.

    TODO (Miguel): implement. Reuse the retrieval pattern from the course's
    RAG prototype (same embeddings, same chunk format).
    """
    raise NotImplementedError("TODO Miguel: implement answer_semantic")


_COURSE_RE = re.compile(r"\b([A-Z]{2,4})\s*(\d{4})\b")


def _course_ids(text: str) -> list[str]:
    return [f"{d} {n}" for d, n in _COURSE_RE.findall(text.upper())]


def _prereq_answer(course_id: str) -> str:
    from . import db
    rows = db.query(
        "SELECT p.group_id, p.prereq_id, p.min_grade, c.title FROM prerequisites p"
        " LEFT JOIN courses c ON c.course_id = p.prereq_id"
        " WHERE p.course_id = :c ORDER BY p.group_id",
        {"c": course_id},
    )
    title = (db.query("SELECT title FROM courses WHERE course_id = :c", {"c": course_id})
             or [{}])[0].get("title", course_id)
    if not rows:
        return (f"**{course_id} — {title}** has no prerequisites on record. "
                f"(If this looks wrong, the prereq seed data may still be incomplete.)")
    groups: dict[int, list[str]] = {}
    for r in rows:
        groups.setdefault(r["group_id"], []).append(
            f"{r['prereq_id']} (min grade {r['min_grade']})")
    parts = [" or ".join(sorted(g)) if len(g) > 1 else g[0] for g in groups.values()]
    return f"**Prerequisites for {course_id} — {title}:**\n\n" + "\n".join(
        f"- {p}" for p in parts)


def _schedule_answer(course_id: str | None) -> str:
    from . import db
    from .planner import term_key
    if course_id:
        rows = db.query(
            "SELECT * FROM sections WHERE course_id = :c", {"c": course_id})
        heading = f"**Sections for {course_id}**"
    else:
        rows = db.query("SELECT * FROM sections")
        heading = "**All scheduled sections**"
    if not rows:
        return f"No sections found{f' for {course_id}' if course_id else ''} in the schedule data."
    rows.sort(key=lambda r: (term_key(r["term"]), r["course_id"], r["section_id"]))
    lines = [f"- `{r['term']}` {r['course_id']} {r['days']} "
             f"{r['start_time']}–{r['end_time']} ({r['instructor']}, cap {r['capacity']})"
             for r in rows]
    return f"{heading} ({len(rows)} section{'s' if len(rows) != 1 else ''}):\n\n" + "\n".join(lines)


def _record_answer(student_id: str) -> str:
    from . import db
    from .planner import term_key
    rows = db.query("SELECT * FROM students WHERE student_id = :s", {"s": student_id})
    if not rows:
        return f"I couldn't find a record for `{student_id}`."
    s = rows[0]
    done = db.query(
        "SELECT course_id, term, grade FROM completed_courses WHERE student_id = :s",
        {"s": student_id})
    done.sort(key=lambda r: term_key(r["term"]))
    enrolled = db.query(
        "SELECT e.section_id, sec.term, sec.days, sec.start_time, sec.end_time"
        " FROM enrollments e JOIN sections sec ON sec.section_id = e.section_id"
        " WHERE e.student_id = :s", {"s": student_id})
    credits = sum(c["credits"] for c in db.query(
        "SELECT c.credits FROM completed_courses cc JOIN courses c"
        " ON c.course_id = cc.course_id WHERE cc.student_id = :s", {"s": student_id}))
    out = [f"**{s['name']}** — `{s['program_id']}`, started {s['start_term']},"
           f" max {s['max_credits_per_semester']} hrs/semester",
           f"\nCompleted {len(done)} course(s), {credits} credit hours:"]
    out += [f"- `{c['term']}` {c['course_id']} — grade {c['grade']}" for c in done] or ["- (none yet)"]
    if enrolled:
        out.append("\nCurrently enrolled:")
        out += [f"- `{e['term']}` {e['section_id']} {e['days']} "
                f"{e['start_time']}–{e['end_time']}" for e in enrolled]
    return "\n".join(out)


def _course_info_answer(course_id: str) -> str:
    from . import db
    rows = db.query("SELECT * FROM courses WHERE course_id = :c", {"c": course_id})
    if not rows:
        return f"I don't have `{course_id}` in the course catalog."
    c = rows[0]
    return (f"**{c['course_id']} — {c['title']}** ({c['credits']} hrs)\n\n"
            f"{c['description']}")


def answer_exact(query: str, student_id: str | None = None) -> str:
    """Answer a conventional/exact-matching query against SQLite (Kyle).

    Supported shapes (deterministic, no LLM needed):
      - prerequisites for a course        ("prereqs for CSE 3310?")
      - sections/schedule for a course    ("when is CSE 3310 offered?")
      - the student's record              ("what have I completed?")
      - single course info fallback       ("CSE 3310")
    Anything else returns a honest "supported queries" message.
    """
    from .tracing import trace

    courses = _course_ids(query)
    q = query.lower()
    trace("tool_call", tool="answer_exact", courses=courses, student_id=student_id)

    if courses and any(w in q for w in ("prereq", "prerequisite", "before taking", "required for")):
        return _prereq_answer(courses[0])
    if any(w in q for w in ("schedule", "section", "offered", "when is", "what time", "times")):
        return _schedule_answer(courses[0] if courses else None)
    if student_id and any(w in q for w in ("record", "transcript", "completed", "have i taken",
                                           "my courses", "progress", "taken so far")):
        return _record_answer(student_id)
    if courses:
        return _course_info_answer(courses[0])
    return ("I couldn't match that to a structured lookup. I can answer exact "
            "queries like *\"prerequisites for CSE 3310\"*, *\"when is CSE 3320 "
            "offered\"*, or *\"show my record\"*. For anything else I'll need to "
            "search the catalog (semantic query).")
