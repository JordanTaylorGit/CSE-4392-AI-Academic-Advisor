"""Scaffold smoke tests — the pieces that must work before owners fill in."""

from advisor import db, planner


def test_schema_and_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "advisor.db")
    monkeypatch.setattr(db, "_engine", None)
    db.init_db()
    assert db.query("SELECT COUNT(*) AS n FROM courses")[0]["n"] > 0
    assert db.query("SELECT COUNT(*) AS n FROM students")[0]["n"] == 4
    assert db.query("SELECT COUNT(*) AS n FROM sections")[0]["n"] > 0


def test_term_ordering():
    assert planner.term_key("F2026") < planner.term_key("S2027")
    assert planner.term_key("S2027") < planner.term_key("SU2027")
    nxt = planner.next_terms("F2026", 4, include_summer=True)
    assert nxt == ["S2027", "SU2027", "F2027", "S2028"]


def test_plan_dict_contract():
    p = planner.DegreePlan(student_id="s1", program_id="bs_cs_cyber")
    p.semesters.append(planner.PlanSemester(term="F2026", courses=[
        {"course_id": "CSE 1310", "title": "Intro", "credits": 3}]))
    d = p.to_dict()
    assert d["total_credits_planned"] == 3
    assert d["semesters"][0]["term"] == "F2026"


def test_ingest_loader_finds_courses():
    from advisor import ingest
    chunks = ingest.load_course_chunks()
    assert len(chunks) > 50
    assert all(c["id"].startswith("CSE ") for c in chunks)
