"""Small, real SQLite catalogs keep planner tests independent of team seed work."""

import sqlite3

import pytest
from sqlalchemy import create_engine

from advisor import db


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    path = tmp_path / "advisor.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(db.SCHEMA_SQL.read_text())
        # Jordan's additive table (created IF NOT EXISTS on the Data branch).
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS prereq_concurrent ("
            " course_id TEXT NOT NULL REFERENCES courses(course_id),"
            " prereq_id TEXT NOT NULL REFERENCES courses(course_id),"
            " PRIMARY KEY (course_id, prereq_id))")
    engine = create_engine(f"sqlite:///{path}")
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(db, "_engine", engine)
    db.execute("INSERT INTO degree_programs VALUES ('cs', 'Computer Science', 18),"
               " ('se', 'Software Engineering', 18)")
    db.execute("INSERT INTO students VALUES ('s1', 'Student', 'cs', 'F2026', 6)")
    for number in (1000, 2000, 3000, 4000, 4100, 4200, 4300):
        cid = f"CSE {number}"
        db.execute("INSERT INTO courses VALUES (:cid, 'CSE', :n, :cid, 3, '')",
                   {"cid": cid, "n": str(number)})
    for cid in ("CSE 1000", "CSE 2000", "CSE 3000", "CSE 4000"):
        db.execute("INSERT INTO requirement_slots (program_id, category, course_id, credits)"
                   " VALUES ('cs', 'core', :cid, 3)", {"cid": cid})
    db.execute("INSERT INTO requirement_slots (program_id, category, options, credits)"
               " VALUES ('cs', 'elective', '[\"CSE 4100\", \"CSE 4200\"]', 3)")
    db.execute("INSERT INTO requirement_slots (program_id, category, course_id, credits)"
               " VALUES ('se', 'core', 'CSE 4300', 3)")
    db.execute("INSERT INTO prerequisites VALUES ('CSE 2000', 1, 'CSE 1000', 'C'),"
               " ('CSE 3000', 1, 'CSE 2000', 'C')")
    for term in ("F2026", "S2027", "SU2027", "F2027", "S2028"):
        for i, number in enumerate((1000, 2000, 3000, 4000, 4100, 4200, 4300)):
            db.execute("INSERT INTO sections VALUES (:sid, :cid, :term, 'MWF', :start, :end, '', 40)",
                       {"sid": f"{number}-{term}", "cid": f"CSE {number}", "term": term,
                        "start": f"{9+i:02}:00", "end": f"{10+i:02}:00"})
    yield db
    engine.dispose()
