import pytest

from advisor import tools


def invoke(name, **kwargs):
    return getattr(tools, name).invoke({"student_id": "s1", **kwargs})


def test_tool_generates_saves_modifies_and_verifies_current_plan(catalog):
    initial = invoke("generate_degree_plan")
    assert initial["total_credits_planned"] == 15
    assert catalog.query("SELECT COUNT(*) AS n FROM plans")[0]["n"] == 1
    modified = invoke("modify_plan", drop=["CSE 1000"], term="F2026")
    assert modified["total_credits_planned"] == 12
    checks = invoke("verify_course_eligibility", course_id="CSE 2000", term="S2027")
    assert not checks[0]["passed"]
    restored = invoke("modify_plan", add=["CSE 1000"], term="F2026")
    assert restored["total_credits_planned"] == 15
    assert invoke("verify_course_eligibility", course_id="CSE 2000", term="S2027")[0]["passed"]


def test_tool_regenerates_for_course_load_and_switches_major(catalog):
    invoke("generate_degree_plan", include_summer=True)
    lighter = invoke("modify_plan", courses_per_semester=1)
    assert all(len(s["courses"]) <= 1 for s in lighter["semesters"])
    switched = invoke("switch_major", new_program_id="se")
    assert switched["new_plan"]["program_id"] == "se"
    assert switched["diff"]["added"] == [{"term": "F2026", "course_id": "CSE 4300"}]
    assert catalog.query("SELECT program_id FROM students")[0]["program_id"] == "se"
    assert all(c["passed"] for c in invoke("verify_course_eligibility", course_id="CSE 4300", term="F2026"))


def test_invalid_program_does_not_change_student_or_saved_plan(catalog):
    invoke("generate_degree_plan")
    with pytest.raises(ValueError, match="program"):
        invoke("switch_major", new_program_id="does_not_exist")
    assert catalog.query("SELECT program_id FROM students")[0]["program_id"] == "cs"
    assert catalog.query("SELECT COUNT(*) AS n FROM plans")[0]["n"] == 1


def test_modify_requires_an_unambiguous_term_for_course_changes(catalog):
    with pytest.raises(ValueError, match="term"):
        invoke("modify_plan", add=["CSE 1000"])
