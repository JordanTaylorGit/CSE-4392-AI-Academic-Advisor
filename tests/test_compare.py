from advisor.compare import diff_plans
from advisor.planner import DegreePlan, PlanSemester


def make_plan(program, *entries):
    return DegreePlan("s1", program, [PlanSemester(term, [
        {"course_id": cid, "title": cid, "credits": 3} for cid in ids
    ]) for term, ids in entries])


def test_comparison_separates_moves_from_additions_and_removals():
    old = make_plan("cs", ("F2026", ["CSE 1000", "CSE 2000"]), ("S2027", ["CSE 3000"]))
    new = make_plan("se", ("F2026", ["CSE 1000", "CSE 4000"]), ("S2027", ["CSE 2000"]),
                    ("F2027", ["CSE 4100"]))
    result = diff_plans(old, new)
    assert result["added"] == [{"term": "F2026", "course_id": "CSE 4000"},
                               {"term": "F2027", "course_id": "CSE 4100"}]
    assert result["removed"] == [{"term": "S2027", "course_id": "CSE 3000"}]
    assert result["moved"] == [{"course_id": "CSE 2000", "from": "F2026", "to": "S2027"}]
    assert result["semesters_added"] == 1
    assert result["credits_delta"] == 3
    assert "cs" in result["summary"] and "se" in result["summary"]
    assert "F2027" in result["summary"]


def test_identical_and_empty_plan_comparisons():
    empty = make_plan("cs")
    result = diff_plans(empty, empty)
    assert result["added"] == result["removed"] == result["moved"] == []
    assert result["credits_delta"] == result["semesters_added"] == 0
    full = make_plan("cs", ("F2026", ["CSE 1000"]))
    assert diff_plans(full, empty)["credits_delta"] == -3


def test_comparison_rejects_different_students():
    import pytest

    old, new = make_plan("cs"), make_plan("cs")
    new.student_id = "s2"
    with pytest.raises(ValueError, match="student"):
        diff_plans(old, new)
