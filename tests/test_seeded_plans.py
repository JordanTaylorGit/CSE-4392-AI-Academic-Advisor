"""Exercise the shipped student records through the live UI service boundary."""

import pytest

from advisor import db, tracing
from ui import services


@pytest.fixture
def seeded_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "advisor.db")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(tracing, "TRACE_LOG", tmp_path / "traces.jsonl")
    db.init_db()
    yield db
    db.get_engine().dispose()


@pytest.mark.parametrize("student_id", ["s_freshman", "s_sophomore", "s_senior", "s_switcher"])
def test_seeded_students_reach_every_requirement(seeded_catalog, student_id):
    student = services.students()[student_id]
    plan, source = services.generate_plan(student_id, student["program_id"], False, None, False)
    assert source == "live"
    assert all(w.startswith("[projection]") for w in plan["warnings"]), plan["warnings"]
    progress, source = services.requirement_progress(student_id, student["program_id"], plan, False)
    assert source == "live"
    assert all(r["completed"] + r["planned"] == r["required"] for r in progress), progress
    for semester in plan["semesters"]:
        for course in semester["courses"]:
            checks, _ = services.verify_course(student_id, course["course_id"], semester["term"], plan, False)
            assert all(c["passed"] for c in checks), checks


@pytest.mark.parametrize("student_id, course_id", [
    ("s_freshman", "CSE 1310"), ("s_senior", "CSE 4316"),
])
def test_seeded_concurrent_course_can_be_dropped_and_readded(seeded_catalog, student_id, course_id):
    student = services.students()[student_id]
    plan, _ = services.generate_plan(student_id, student["program_id"], False, None, False)
    dropped, _ = services.drop_course(plan, course_id, "F2026", False)
    restored, _ = services.add_course(dropped, course_id, "F2026", False)
    checks, _ = services.verify_course(student_id, course_id, "F2026", restored, False)
    assert all(c["passed"] for c in checks), checks
