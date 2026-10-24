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


def test_free_elective_does_not_bypass_professional_slot_admission(expanded):
    expanded.execute("DELETE FROM requirement_slots WHERE slot_id NOT IN (1, 5)")
    expanded.execute("UPDATE requirement_slots SET professional=1 WHERE slot_id=1")
    p = planner.generate_plan("s1")
    assert any("Requirement 1" in w for w in p.warnings)
    assert p.to_dict()["total_credits_planned"] == 3  # Only the free slot can be filled.


def test_matching_can_move_a_course_between_count_and_hour_slots(expanded):
    expanded.execute("DELETE FROM requirement_slots WHERE slot_id NOT IN (2, 4)")
    expanded.execute("DELETE FROM slot_courses")
    expanded.execute("INSERT INTO slot_courses VALUES (2, 'CSE 4000'), (2, 'CSE 4100'), (4, 'CSE 4000')")
    p = planner.generate_plan("s1")
    assert p.to_dict()["total_credits_planned"] == 6
    assert not p.warnings


def test_passing_completed_enrollment_retakes_are_preserved(expanded):
    expanded.execute("INSERT INTO completed_courses VALUES ('s1', 'CSE 1000', 'S2026', 'F')")
    expanded.execute("INSERT INTO enrollments VALUES ('s1', '1000-F2026', 'completed', 'A')")
    assert planner.verify_course("s1", "CSE 2000", "S2027")[0].passed
    p = planner.generate_plan("s1")
    assert p.semesters[0].term == "S2027"
    assert "CSE 1000" not in {c["course_id"] for s in p.semesters for c in s.courses}


def test_approved_four_credit_course_fills_three_hour_bucket(expanded):
    expanded.execute("DELETE FROM requirement_slots WHERE slot_id != 4")
    expanded.execute("UPDATE courses SET credits=4 WHERE course_id='CSE 4200'")
    p = planner.generate_plan("s1")
    assert p.to_dict()["total_credits_planned"] == 4
    assert not p.warnings


def test_json_plan_snapshots_round_trip(expanded):
    from advisor import plan_store, tools

    payload = tools.generate_degree_plan.invoke({"student_id": "s1", "include_summer": True})
    assert plan_store.latest("s1").to_dict() == payload
    assert expanded.query("SELECT plan_json FROM plans")[0]["plan_json"].startswith('{')


def test_mixed_credit_options_do_not_prevent_slot_reassignment(expanded):
    expanded.execute("DELETE FROM requirement_slots WHERE slot_id NOT IN (2, 4)")
    expanded.execute("DELETE FROM slot_courses")
    expanded.execute("INSERT INTO slot_courses VALUES (2, 'CSE 4000'), (2, 'CSE 4100'),"
                     " (4, 'CSE 4000'), (4, 'CSE 4200')")
    expanded.execute("UPDATE courses SET credits=4 WHERE course_id='CSE 4200'")
    expanded.execute("UPDATE degree_programs SET total_hours=6")
    p = planner.generate_plan("s1")
    assert p.to_dict()["total_credits_planned"] == 6
    assert not p.warnings


def test_modify_plan_adds_mutual_corequisites_together(expanded):
    from advisor import plan_store, tools

    expanded.execute("UPDATE prerequisites SET kind='coreq' WHERE course_id='CSE 2000'")
    expanded.execute("INSERT INTO prerequisites VALUES ('CSE 1000', 1, 'CSE 2000', 'C', 'coreq')")
    plan_store.save(planner.DegreePlan('s1', 'cs'))
    result = tools.modify_plan.invoke({'student_id': 's1', 'term': 'F2026', 'add': ['CSE 1000', 'CSE 2000']})
    assert result['total_credits_planned'] == 6
    assert not any('[verification]' in warning for warning in result['warnings'])
