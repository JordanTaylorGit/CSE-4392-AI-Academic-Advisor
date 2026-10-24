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
    projected = checks(term="F2030")["no_schedule_conflict"]
    assert projected.passed and "Assumed offered" in projected.detail
    assert not checks(term="F2045")["no_schedule_conflict"].passed  # Beyond the projection window.


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


def test_generate_plan_packs_prerequisites_before_dependents(catalog):
    p = planner.generate_plan("s1")
    terms = {c["course_id"]: s.term for s in p.semesters for c in s.courses}
    assert terms["CSE 1000"] == "F2026"
    assert planner.term_key(terms["CSE 1000"]) < planner.term_key(terms["CSE 2000"])
    assert planner.term_key(terms["CSE 2000"]) < planner.term_key(terms["CSE 3000"])
    assert len(terms) == 5
    assert not p.warnings
    assert all(s.credits <= 6 for s in p.semesters)
    for semester in p.semesters:
        for course in semester.courses:
            assert all(c.passed for c in planner.verify_course("s1", course["course_id"], semester.term, p))
    assert p.to_dict() == planner.generate_plan("s1").to_dict()


def test_course_limit_and_optional_summer(catalog):
    p = planner.generate_plan("s1", include_summer=True, courses_per_semester=1)
    assert len(p.semesters) == 5
    assert p.semesters[2].term == "SU2027"
    assert all(len(s.courses) <= 1 for s in p.semesters)
    assert not p.warnings
    assert all(not s.term.startswith("SU") for s in planner.generate_plan("s1").semesters)
    with pytest.raises(ValueError, match="positive"):
        planner.generate_plan("s1", courses_per_semester=0)


def test_generation_uses_transcript_to_advance_start(catalog):
    catalog.execute("INSERT INTO completed_courses VALUES ('s1', 'CSE 1000', 'F2026', 'B')")
    p = planner.generate_plan("s1")
    assert p.semesters[0].term == "S2027"
    assert "CSE 1000" not in {c["course_id"] for s in p.semesters for c in s.courses}


def test_generation_handles_missing_requirements_schedules_and_cycles(catalog):
    catalog.execute("INSERT INTO prerequisites VALUES ('CSE 1000', 1, 'CSE 3000', 'C')")
    p = planner.generate_plan("s1")
    assert p.warnings
    assert not {"CSE 1000", "CSE 2000", "CSE 3000"} & {
        c["course_id"] for s in p.semesters for c in s.courses}
    catalog.execute("DELETE FROM sections")
    p = planner.generate_plan("s1")
    assert not p.semesters and any("schedule" in w.lower() for w in p.warnings)
    catalog.execute("DELETE FROM requirement_slots WHERE program_id='cs'")
    p = planner.generate_plan("s1")
    assert not p.semesters and any("requirement" in w.lower() for w in p.warnings)


def test_generation_preserves_fixed_enrollments(catalog):
    catalog.execute("INSERT INTO enrollments VALUES ('s1', '4000-F2026')")
    p = planner.generate_plan("s1")
    assert "CSE 4000" in {c["course_id"] for c in p.semesters[0].courses}
    assert p.semesters[0].credits <= 6


def test_generation_can_change_program_without_mutating_student(catalog):
    p = planner.generate_plan("s1", program_id="se")
    assert p.program_id == "se"
    assert p.semesters[0].courses[0]["course_id"] == "CSE 4300"
    assert catalog.query("SELECT program_id FROM students")[0]["program_id"] == "cs"


def test_add_rejects_invalid_courses_and_never_mutates_original(catalog):
    p = plan_with(("F2026", ["CSE 1000"]))
    original = deepcopy(p)
    bad = planner.add_course(p, "CSE 2000", "F2026")
    assert bad.semesters == p.semesters
    assert any("prerequisites_met" in w for w in bad.warnings)
    good = planner.add_course(p, "CSE 2000", "S2027")
    assert len(good.semesters) == 2
    assert not any("[verification]" in w for w in good.warnings)
    assert p == original
    duplicate = planner.add_course(p, "CSE 1000", "F2026")
    assert duplicate.semesters == p.semesters


def test_drop_rechecks_downstream_prerequisites_and_clears_stale_warnings(catalog):
    p = plan_with(("F2026", ["CSE 1000"]), ("S2027", ["CSE 2000"]))
    original = deepcopy(p)
    dropped = planner.drop_course(p, "CSE 1000", "F2026")
    assert any("CSE 2000" in w and "prerequisites_met" in w for w in dropped.warnings)
    restored = planner.add_course(dropped, "CSE 1000", "F2026")
    assert not any("prerequisites_met" in w for w in restored.warnings)
    assert p == original


def test_overlapping_elective_slots_do_not_waste_a_required_course(catalog):
    catalog.execute("UPDATE requirement_slots SET options='[\"CSE 1000\", \"CSE 4100\"]'"
                    " WHERE category='elective'")
    p = planner.generate_plan("s1")
    assert not p.warnings
    assert p.to_dict()["total_credits_planned"] == 15


def test_elective_choice_preserves_a_later_required_prerequisite(catalog):
    catalog.execute("UPDATE students SET max_credits_per_semester=9")
    catalog.execute("DELETE FROM requirement_slots WHERE course_id='CSE 2000'")
    catalog.execute("UPDATE requirement_slots SET options='[\"CSE 2000\", \"CSE 4100\"]'"
                    " WHERE category='elective'")
    p = planner.generate_plan("s1")
    assert not p.warnings
    assert {c["course_id"] for s in p.semesters for c in s.courses} == {
        "CSE 1000", "CSE 2000", "CSE 3000", "CSE 4000"}


def test_unknown_section_times_are_not_certified_conflict_free(catalog):
    catalog.execute("UPDATE sections SET days='', start_time='', end_time='' WHERE course_id='CSE 1000'")
    assert not checks()["no_schedule_conflict"].passed


def test_duplicate_entries_in_same_semester_are_flagged(catalog):
    p = plan_with(("F2026", ["CSE 1000", "CSE 1000"]))
    assert not checks(plan=p)["not_already_passed"].passed


def test_full_multiyear_chain_uses_earlier_terms_for_every_prerequisite(catalog):
    catalog.execute("DELETE FROM requirement_slots")
    catalog.execute("DELETE FROM prerequisites")
    catalog.execute("DELETE FROM sections")
    ids = ["CSE 1000", "CSE 2000", "CSE 3000", "CSE 4000", "CSE 4100", "CSE 4200", "CSE 4300"]
    catalog.execute("UPDATE degree_programs SET total_credits=21")
    terms = ["F2026"] + planner.next_terms("F2026", 7)
    for i, cid in enumerate(ids):
        catalog.execute("INSERT INTO requirement_slots (program_id, category, course_id, credits)"
                        " VALUES ('cs', 'core', :cid, 3)", {"cid": cid})
        if i:
            catalog.execute("INSERT INTO prerequisites VALUES (:cid, 1, :prev, 'C')", {"cid": cid, "prev": ids[i-1]})
        for term in terms:
            catalog.execute("INSERT INTO sections VALUES (:sid, :cid, :term, 'MWF', '09:00', '10:00', '', 40)",
                            {"sid": cid+term, "cid": cid, "term": term})
    p = planner.generate_plan("s1")
    assert len(p.semesters) == 7
    assert p.semesters[-1].term == "F2029"
    assert p.to_dict()["total_credits_planned"] == 21
    assert not p.warnings


def test_concurrent_prereq_is_satisfied_by_same_term_plan_or_enrollment(catalog):
    catalog.execute("INSERT INTO prereq_concurrent VALUES ('CSE 2000', 'CSE 1000')")
    p = plan_with(("F2026", ["CSE 1000"]))
    assert checks("CSE 2000", plan=p)["prerequisites_met"].passed
    catalog.execute("INSERT INTO enrollments VALUES ('s1', '1000-F2026')")
    assert checks("CSE 2000")["prerequisites_met"].passed


def test_non_concurrent_prereq_still_requires_an_earlier_term(catalog):
    p = plan_with(("F2026", ["CSE 1000"]))
    assert not checks("CSE 2000", plan=p)["prerequisites_met"].passed


def test_generation_pulls_a_concurrent_prereq_into_the_same_term(catalog):
    catalog.execute("INSERT INTO prerequisites VALUES ('CSE 1000', 1, 'CSE 4100', 'C')")
    catalog.execute("INSERT INTO prereq_concurrent VALUES ('CSE 1000', 'CSE 4100')")
    p = planner.generate_plan("s1")
    assert {"CSE 1000", "CSE 4100"} <= {c["course_id"] for c in p.semesters[0].courses}
    assert not p.warnings


def test_dropped_course_readded_beside_its_concurrent_prereq(catalog):
    catalog.execute("INSERT INTO prereq_concurrent VALUES ('CSE 2000', 'CSE 1000')")
    p = plan_with(("F2026", ["CSE 1000", "CSE 2000"]))
    dropped = planner.drop_course(p, "CSE 2000", "F2026")
    readded = planner.add_course(dropped, "CSE 2000", "F2026")
    assert not any("[verification]" in w for w in readded.warnings)


def test_generation_projects_offerings_beyond_the_schedule(catalog):
    catalog.execute("DELETE FROM sections WHERE term != 'F2026'")
    p = planner.generate_plan("s1")
    terms = {c["course_id"]: s.term for s in p.semesters for c in s.courses}
    assert terms["CSE 1000"] == "F2026"
    assert planner.term_key(terms["CSE 3000"]) > planner.term_key("S2027")
    assert p.to_dict()["total_credits_planned"] == 15
    assert any("[projection]" in w for w in p.warnings)
    assert all(not s.term.startswith("SU") for s in p.semesters)
    for semester in p.semesters:
        for course in semester.courses:
            assert all(c.passed for c in planner.verify_course("s1", course["course_id"], semester.term, p))


def test_projected_verification_is_flagged_not_certified(catalog):
    catalog.execute("DELETE FROM sections WHERE term != 'F2026'")
    result = checks("CSE 1000", "S2027")
    assert result["no_schedule_conflict"].passed
    assert "Assumed offered" in result["no_schedule_conflict"].detail


def test_upper_level_courses_are_not_assumed_in_summer(catalog):
    catalog.execute("DELETE FROM sections WHERE term != 'F2026'")
    assert not checks("CSE 4000", "SU2027")["no_schedule_conflict"].passed
    assert checks("CSE 2000", "SU2027")["no_schedule_conflict"].passed
