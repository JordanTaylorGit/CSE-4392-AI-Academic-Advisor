"""SQLite access layer (Person A owns the data; schema is a frozen contract).

Creates advisor.db from seed/schema.sql and loads seed datasets:
  - courses          <- catalog/course-desc.jsonl
  - degree_programs  <- hardcoded below (must match seed/degree_reqs/*.md IDs)
  - sections         <- seed/schedule.json
  - students         <- seed/students.json

TODO (Person A):
  - Parse prerequisite clauses out of the catalog PDF text into
    `prerequisites` (use advisor/ingest.py's course loader for the raw text).
  - Expand requirement_slots to cover BOTH programs fully (the .md docs are
    the source of truth; non-CSE courses like ENGL 1301/MATH/PHYS also need
    rows in `courses` so slots can reference them).
  - Enrich `courses` credits (JSONL lacks hours; catalog text has them).
"""

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .paths import COURSE_DESC_JSONL, DB_PATH, SCHEDULE_JSON, SCHEMA_SQL, SEED_DIR, STUDENTS_JSON

EXTRA_COURSES_JSON = SEED_DIR / "extra_courses.json"

_engine: Engine | None = None

# Must match the Program IDs in seed/degree_reqs/*.md.
PROGRAMS = [
    ("bs_cs_cyber", "BS in Computer Science — Cybersecurity", 120),
    ("bs_se_ai", "BS in Software Engineering — Artificial Intelligence", 120),
]


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
    for pid, name, total in PROGRAMS:
        conn.execute(
            text("INSERT INTO degree_programs VALUES (:pid, :name, :total)"),
            {"pid": pid, "name": name, "total": total},
        )
    _seed_sections(conn)
    _seed_students(conn)


def _seed_courses(conn) -> None:
    # TODO(Person A): augment credits from catalog text; add non-CSE courses
    # (MATH, ENGL, PHYS, ...) referenced by requirement slots.
    for line in COURSE_DESC_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        conn.execute(
            text(
                "INSERT OR IGNORE INTO courses"
                " (course_id, dept, number, title, credits, description)"
                " VALUES (:cid, 'CSE', :num, :title, 3, :descr)"
            ),
            {"cid": f"CSE {c['id']}", "num": c["id"], "title": c["title"], "descr": c["description"]},
        )


def _seed_extra_courses(conn) -> None:
    # Non-CSE courses referenced by seeds and requirement slots.
    # TODO(Person A): expand as requirement_slots coverage grows.
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
    for t in ("courses", "sections", "students", "degree_programs"):
        print(f"{t}: {_count(get_engine().connect(), t)}")
