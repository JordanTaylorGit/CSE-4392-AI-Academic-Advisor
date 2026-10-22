from copy import deepcopy

import pytest

from advisor import planner


def plan_with(*entries):
    return planner.DegreePlan("s1", "cs", [
        planner.PlanSemester(term, [{"course_id": cid, "title": cid, "credits": 3}
                                   for cid in courses])
        for term, courses in entries
    ])


def checks(course="CSE 1000", term="F2026", plan=None):
    return {c.name: c for c in planner.verify_course("s1", course, term, plan)}


def test_all_six_checks_are_returned_in_contract_order(catalog):
    result = planner.verify_course("s1", "CSE 1000", "F2026")
    assert [c.name for c in result] == planner.CHECK_NAMES
    assert all(c.passed and c.detail for c in result)


def test_prerequisites_require_earlier_terms_and_minimum_grade(catalog):
    p = plan_with(("F2026", ["CSE 1000"]))
    assert not checks("CSE 2000", plan=p)["prerequisites_met"].passed
    assert checks("CSE 2000", "S2027", p)["prerequisites_met"].passed
    catalog.execute("INSERT INTO completed_courses VALUES ('s1', 'CSE 1000', 'S2026', 'D')")
    assert not checks("CSE 2000")["prerequisites_met"].passed
    assert checks()["not_already_passed"].passed  # CSE requires C or better.
    catalog.execute("UPDATE completed_courses SET grade='B'")
    assert checks("CSE 2000")["prerequisites_met"].passed
    assert not checks()["not_already_passed"].passed


def test_prerequisite_groups_are_and_of_or_alternatives(catalog):
    catalog.execute("INSERT INTO prerequisites VALUES ('CSE 2000', 1, 'CSE 4100', 'C'),"
                    " ('CSE 2000', 2, 'CSE 4000', 'B')")
    catalog.execute("INSERT INTO completed_courses VALUES ('s1', 'CSE 4100', 'S2026', 'A'),"
                    " ('s1', 'CSE 4000', 'S2026', 'C')")
    assert not checks("CSE 2000")["prerequisites_met"].passed
    catalog.execute("UPDATE completed_courses SET grade='B' WHERE course_id='CSE 4000'")
    assert checks("CSE 2000")["prerequisites_met"].passed


def test_same_or_future_completed_term_does_not_satisfy_prerequisite(catalog):
    catalog.execute("INSERT INTO completed_courses VALUES ('s1', 'CSE 1000', 'F2026', 'A')")
    assert not checks("CSE 2000")["prerequisites_met"].passed


def test_requirement_check_rejects_unrelated_and_excess_electives(catalog):
    assert not checks("CSE 4300")["fulfills_degree_requirement"].passed
    p = plan_with(("F2026", ["CSE 4100"]))
    assert not checks("CSE 4200", "S2027", p)["fulfills_degree_requirement"].passed


def test_schedule_search_uses_alternative_section_and_boundary_times(catalog):
    catalog.execute("UPDATE sections SET start_time='09:30', end_time='10:30'"
                    " WHERE course_id='CSE 4000' AND term='F2026'")
    p = plan_with(("F2026", ["CSE 1000"]))
    assert not checks("CSE 4000", plan=p)["no_schedule_conflict"].passed
    catalog.execute("INSERT INTO sections VALUES ('alternate', 'CSE 4000', 'F2026',"
                    " 'MWF', '10:00', '11:00', '', 40)")
    assert checks("CSE 4000", plan=p)["no_schedule_conflict"].passed
    assert not checks(term="F2030")["no_schedule_conflict"].passed


def test_enrollments_lock_sections_and_count_once_against_caps(catalog):
    catalog.execute("INSERT INTO enrollments VALUES ('s1', '1000-F2026')")
    catalog.execute("UPDATE sections SET start_time='09:30', end_time='10:30'"
                    " WHERE course_id='CSE 4000' AND term='F2026'")
    assert not checks("CSE 4000")["no_schedule_conflict"].passed
    p = plan_with(("F2026", ["CSE 1000", "CSE 4100"]))
    assert not checks("CSE 4000", plan=p)["within_semester_credit_cap"].passed


def test_credit_caps_use_catalog_values_and_count_candidate_once(catalog):
    p = plan_with(("F2026", ["CSE 1000", "CSE 4000"]))
    p.semesters[0].courses[0]["credits"] = 0  # Caller cannot bypass the cap.
    assert not checks("CSE 4100", plan=p)["within_semester_credit_cap"].passed
    assert checks("CSE 4000", plan=p)["within_semester_credit_cap"].passed
    catalog.execute("UPDATE degree_programs SET total_credits=5 WHERE program_id='cs'")
    assert not checks("CSE 4000", plan=p)["within_degree_credit_cap"].passed


def test_unknown_course_returns_six_failures_and_wrong_student_is_rejected(catalog):
    assert not any(c.passed for c in planner.verify_course("s1", "BOGUS", "F2026"))
    with pytest.raises(ValueError, match="student"):
        planner.verify_course("missing", "CSE 1000", "F2026")
    p = plan_with()
    p.student_id = "someone_else"
    with pytest.raises(ValueError, match="student"):
        planner.verify_course("s1", "CSE 1000", "F2026", p)


def test_term_helpers_handle_summer_start_and_reject_bad_terms():
    assert planner.next_terms("SU2026", 2) == ["F2026", "S2027"]
    for invalid in ("F26", "X2026", "F2026junk", ""):
        with pytest.raises(ValueError):
            planner.term_key(invalid)


def test_verification_does_not_mutate_plan(catalog):
    p = plan_with(("F2026", ["CSE 1000"]))
    before = deepcopy(p)
    checks("CSE 4000", plan=p)
    assert p == before
