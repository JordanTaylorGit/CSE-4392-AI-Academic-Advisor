"""SQLite access layer (Jordan owns the data; schema is a frozen contract).

Creates advisor.db from seed/schema.sql and loads seed datasets:
  - courses            <- catalog/course-desc.jsonl (+ seed/course_credits.json for real credit hours)
                          + seed/extra_courses.json (non-CSE courses)
  - degree_programs    <- seed/programs.json
  - prerequisites,
    prereq_concurrent,
    professional_courses <- seed/prerequisites.json
  - requirement_slots  <- seed/requirement_slots.json
  - sections           <- seed/schedule.json
  - students (+ completed_courses, current-term enrollments) <- seed/students.json

All the generated JSON above comes from `python advisor/seed/build_seed_data.py`
(catalog PDF + seed/degree_source.py). Re-run it instead of hand-editing the JSON.
If advisor.db already exists, delete it and re-run `python -m advisor.db` to reseed.
"""

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .paths import COURSE_DESC_JSONL, DB_PATH, SCHEDULE_JSON, SCHEMA_SQL, SEED_DIR, STUDENTS_JSON

EXTRA_COURSES_JSON = SEED_DIR / "extra_courses.json"
CREDITS_JSON = SEED_DIR / "course_credits.json"
PROGRAMS_JSON = SEED_DIR / "programs.json"
PREREQS_JSON = SEED_DIR / "prerequisites.json"
SLOTS_JSON = SEED_DIR / "requirement_slots.json"

_engine: Engine | None = None

def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{DB_PATH}")
    return _engine


def init_db() -> None:
    """Create tables (idempotent) and load seed data if empty."""
    sqlite3.connect(DB_PATH).executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        if _count(conn, "courses") == 0:
            _seed(conn)


def _count(conn, table: str) -> int:
    return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def _seed(conn) -> None:
    _seed_courses(conn)
    _seed_extra_courses(conn)
    for p in _load(PROGRAMS_JSON):
        conn.execute(
            text("INSERT INTO degree_programs (program_id, name, total_credits)"
                 " VALUES (:program_id, :name, :total_credits)"), p)
    _seed_prereqs(conn)
    _seed_slots(conn)
    _seed_sections(conn)
    _seed_students(conn)


def _seed_courses(conn) -> None:
    # CSE courses: titles/descriptions from the JSONL, real credit hours parsed from the catalog PDF.
    credits = _load(CREDITS_JSON) if CREDITS_JSON.exists() else {}
    for line in COURSE_DESC_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        cid = f"CSE {c['id']}"
        conn.execute(
            text(
                "INSERT OR IGNORE INTO courses"
                " (course_id, dept, number, title, credits, description)"
                " VALUES (:cid, 'CSE', :num, :title, :credits, :descr)"
            ),
            {"cid": cid, "num": c["id"], "title": c["title"],
             "credits": credits.get(cid, 3), "descr": c["description"]},
        )


def _seed_extra_courses(conn) -> None:
    # Non-CSE courses referenced by seeds and requirement slots.
    # TODO(Jordan): expand as requirement_slots coverage grows.
    if not EXTRA_COURSES_JSON.exists():
        return
    for c in json.loads(EXTRA_COURSES_JSON.read_text(encoding="utf-8")):
        conn.execute(
            text(
                "INSERT OR IGNORE INTO courses"
                " (course_id, dept, number, title, credits, description)"
                " VALUES (:cid, :dept, :num, :title, :credits, :descr)"
            ),
            {"cid": c["course_id"], "dept": c["dept"], "num": c["number"],
             "title": c["title"], "credits": c["credits"], "descr": c["description"]},
        )


def _seed_prereqs(conn) -> None:
    data = _load(PREREQS_JSON)
    for r in data["prerequisites"]:
        conn.execute(
            text("INSERT OR IGNORE INTO prerequisites (course_id, group_id, prereq_id, min_grade)"
                 " VALUES (:course_id, :group_id, :prereq_id, :min_grade)"), r)
        if r["concurrent_ok"]:
            conn.execute(
                text("INSERT OR IGNORE INTO prereq_concurrent (course_id, prereq_id)"
                     " VALUES (:course_id, :prereq_id)"), r)
    for cid in data["professional_courses"]:
        conn.execute(text("INSERT OR IGNORE INTO professional_courses (course_id) VALUES (:c)"), {"c": cid})


def _seed_slots(conn) -> None:
    for r in _load(SLOTS_JSON):
        conn.execute(
            text("INSERT INTO requirement_slots (program_id, category, course_id, options, credits)"
                 " VALUES (:program_id, :category, :course_id, :options, :credits)"),
            {**r, "options": json.dumps(r["options"])},
        )


def _seed_sections(conn) -> None:
    for s in json.loads(SCHEDULE_JSON.read_text(encoding="utf-8")):
        conn.execute(
            text(
                "INSERT OR IGNORE INTO sections"
                " (section_id, course_id, term, days, start_time, end_time, instructor, capacity)"
                " VALUES (:sid, :cid, :term, :days, :st, :et, :instr, :cap)"
            ),
            {
                "sid": s["section_id"], "cid": s["course_id"], "term": s["term"],
                "days": s["days"], "st": s["start_time"], "et": s["end_time"],
                "instr": s["instructor"], "cap": s.get("capacity", 40),
            },
        )


def _seed_students(conn) -> None:
    for s in json.loads(STUDENTS_JSON.read_text(encoding="utf-8")):
        conn.execute(
            text(
                "INSERT OR IGNORE INTO students"
                " (student_id, name, program_id, start_term, max_credits_per_semester)"
                " VALUES (:sid, :name, :pid, :start, :maxc)"
            ),
            {
                "sid": s["student_id"], "name": s["name"], "pid": s["program_id"],
                "start": s["start_term"], "maxc": s["max_credits_per_semester"],
            },
        )
        for sec_id in s.get("current_enrollments", []):
            conn.execute(
                text("INSERT OR IGNORE INTO enrollments (student_id, section_id) VALUES (:sid, :sec)"),
                {"sid": s["student_id"], "sec": sec_id},
            )
        for cc in s.get("completed_courses", []):
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO completed_courses"
                    " (student_id, course_id, term, grade) VALUES (:sid, :cid, :term, :g)"
                ),
                {"sid": s["student_id"], "cid": cc["course_id"], "term": cc["term"], "g": cc["grade"]},
            )


def query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a read query, return rows as dicts. Used by tools/chains."""
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
    return [dict(r) for r in rows]


def execute(sql: str, params: dict | Iterable[dict] | None = None) -> None:
    """Run a write statement."""
    eng = get_engine()
    with eng.begin() as conn:
        if isinstance(params, Iterable) and not isinstance(params, (dict, str)):
            conn.execute(text(sql), list(params))
        else:
            conn.execute(text(sql), params or {})


if __name__ == "__main__":
    init_db()
    for t in ("courses", "prerequisites", "prereq_concurrent", "professional_courses", "requirement_slots",
              "sections", "students", "completed_courses", "enrollments", "degree_programs"):
        print(f"{t}: {_count(get_engine().connect(), t)}")
