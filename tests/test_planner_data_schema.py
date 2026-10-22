"""Exercise the table/column contract on origin/Data without merging its WIP seeds."""

import pytest

from advisor import planner


@pytest.fixture
def expanded(catalog):
    catalog.execute("ALTER TABLE degree_programs RENAME COLUMN total_credits TO total_hours")
    catalog.execute("ALTER TABLE courses ADD COLUMN requires_professional INTEGER NOT NULL DEFAULT 0")
    catalog.execute("ALTER TABLE students ADD COLUMN professional_admitted INTEGER NOT NULL DEFAULT 0")
    catalog.execute("ALTER TABLE prerequisites ADD COLUMN kind TEXT NOT NULL DEFAULT 'prereq'")
    catalog.execute("ALTER TABLE enrollments ADD COLUMN status TEXT NOT NULL DEFAULT 'in_progress'")
    catalog.execute("ALTER TABLE enrollments ADD COLUMN grade TEXT")
    catalog.execute("ALTER TABLE plans ADD COLUMN plan_json TEXT NOT NULL DEFAULT '{}'")
    catalog.execute("DROP TABLE requirement_slots")
    catalog.execute("CREATE TABLE requirement_slots (slot_id INTEGER PRIMARY KEY, program_id TEXT,"
                    " slot_key TEXT, category TEXT, label TEXT, slot_type TEXT, hours INTEGER,"
                    " courses_needed INTEGER, professional INTEGER DEFAULT 0, open_list INTEGER DEFAULT 0)")
    catalog.execute("CREATE TABLE slot_courses (slot_id INTEGER, course_id TEXT)")
    for sid, kind, hours, count, options in [
        (1, 'fixed', 3, None, ['CSE 1000']),
        (2, 'one_of', 3, None, ['CSE 2000', 'CSE 4100']),
        (3, 'choose_n', 6, 2, ['CSE 3000', 'CSE 4000', 'CSE 4100']),
        (4, 'category', 3, None, ['CSE 4200']),
        (5, 'free', 3, None, []),
    ]:
        catalog.execute("INSERT INTO requirement_slots"
                        " (slot_id, program_id, slot_key, category, label, slot_type, hours, courses_needed)"
                        " VALUES (:sid, 'cs', :label, 'core', :label, :kind, :hours, :count)",
                        {"sid": sid, "label": f"Requirement {sid}", "kind": kind, "hours": hours, "count": count})
        for cid in options:
            catalog.execute("INSERT INTO slot_courses VALUES (:sid, :cid)", {"sid": sid, "cid": cid})
    return catalog


def test_expanded_slots_fill_counts_and_hours_without_double_counting(expanded):
    p = planner.generate_plan("s1", include_summer=True)
    ids = [c["course_id"] for s in p.semesters for c in s.courses]
    assert len(ids) == len(set(ids)) == 6
    assert p.to_dict()["total_credits_planned"] == 18
    assert not p.warnings
    assert all(c.passed for s in p.semesters for course in s.courses
               for c in planner.verify_course("s1", course["course_id"], s.term, p))


def test_corequisite_can_be_same_term_but_prerequisite_cannot(expanded):
    expanded.execute("UPDATE prerequisites SET kind='coreq' WHERE course_id='CSE 2000'")
    p = planner.DegreePlan("s1", "cs", [planner.PlanSemester("F2026", [
        {"course_id": "CSE 1000", "title": "Intro", "credits": 3}])])
    assert planner.verify_course("s1", "CSE 2000", "F2026", p)[0].passed
    assert not planner.verify_course("s1", "CSE 3000", "F2026", p)[0].passed


def test_generation_schedules_mutual_corequisites_as_a_bundle(expanded):
    expanded.execute("UPDATE prerequisites SET kind='coreq' WHERE course_id='CSE 2000'")
    expanded.execute("INSERT INTO prerequisites VALUES ('CSE 1000', 1, 'CSE 2000', 'C', 'coreq')")
    p = planner.generate_plan("s1", include_summer=True)
    assert {c['course_id'] for c in p.semesters[0].courses} == {"CSE 1000", "CSE 2000"}
    assert not p.warnings


def test_professional_admission_gates_courses_and_slots(expanded):
    expanded.execute("UPDATE courses SET requires_professional=1 WHERE course_id='CSE 1000'")
    assert not planner.verify_course("s1", "CSE 1000", "F2026")[0].passed
    expanded.execute("UPDATE students SET professional_admitted=1")
    assert planner.verify_course("s1", "CSE 1000", "F2026")[0].passed


def test_completed_enrollment_is_not_a_future_schedule_blocker(expanded):
    expanded.execute("INSERT INTO enrollments VALUES ('s1', '1000-F2026', 'completed', 'F')")
    assert planner.verify_course("s1", "CSE 1000", "S2027")[1].passed


def test_category_does_not_claim_unlisted_courses_are_approved(expanded):
    expanded.execute("DELETE FROM requirement_slots WHERE slot_type != 'category'")
    expanded.execute("UPDATE requirement_slots SET open_list=1")
    p = planner.generate_plan("s1")
    assert {c["course_id"] for s in p.semesters for c in s.courses} == {"CSE 4200"}


def test_bucket_credit_hours_can_be_filled_by_multiple_courses(expanded):
    expanded.execute("DELETE FROM requirement_slots WHERE slot_id != 4")
    expanded.execute("UPDATE requirement_slots SET hours=6")
    expanded.execute("INSERT INTO slot_courses VALUES (4, 'CSE 4300')")
    p = planner.generate_plan("s1")
    assert p.to_dict()["total_credits_planned"] == 6
    assert not p.warnings
