"""Trace log reading, turn grouping, and Markdown rendering (Person E)."""

import json
import sys
from pathlib import Path

from advisor import tracing

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import render_traces

RECORDS = [
    {"ts": "2026-10-21T15:00:00+00:00", "event": "ui_action", "session": "a", "student_id": "s_sophomore",
     "action": "generate_plan", "source": "live", "program_id": "bs_cs_cyber"},
    {"ts": "2026-10-21T15:00:01+00:00", "event": "user_msg", "session": "a", "student_id": "s_sophomore",
     "message": "Can I take CSE 4344?"},
    {"ts": "2026-10-21T15:00:01.200000+00:00", "event": "intent", "session": "a", "student_id": "s_sophomore",
     "intent": "exact_query"},
    {"ts": "2026-10-21T15:00:01.500000+00:00", "event": "assistant_msg", "session": "a",
     "student_id": "s_sophomore", "intent": "exact_query", "reply": "Yes | all six checks pass."},
    {"ts": "2026-10-21T15:05:00+00:00", "event": "user_msg", "session": "b", "student_id": "s_freshman",
     "message": "Build my plan"},
]


def write_log(tmp_path: Path) -> Path:
    path = tmp_path / "traces.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in RECORDS) + '{"partial', encoding="utf-8")
    return path


def test_read_filters_and_skips_partial_line(tmp_path):
    path = write_log(tmp_path)
    assert len(tracing.read(path)) == 5
    assert len(tracing.read(path, session="a")) == 4
    assert len(tracing.read(path, student_id="s_freshman")) == 1
    assert len(tracing.read(path, since="2026-10-21T15:01")) == 1


def test_group_turns():
    groups = tracing.group_turns(RECORDS)
    assert [g["kind"] for g in groups] == ["action", "turn", "turn"]
    turn = groups[1]
    assert turn["message"] == "Can I take CSE 4344?"
    assert turn["intent"] == "exact_query"
    assert turn["reply"].startswith("Yes")
    assert len(turn["events"]) == 3
    assert tracing.duration_ms(turn) == 500
    assert groups[2]["reply"] is None  # no assistant_msg logged yet


def test_render_markdown(tmp_path):
    path = write_log(tmp_path)
    out = tmp_path / "log.md"
    render_traces.main(["--input", str(path), "--out", str(out), "--session", "a"])
    md = out.read_text()
    assert "### Turn 1: Sam Martinez" in md and "intent `exact_query`" in md
    assert "Yes \\| all six checks pass." not in md  # reply is a quote, not a table cell
    assert "> Yes | all six checks pass." in md
    assert "| generate_plan | live |" in md
    assert "Alex Freshman" not in md  # filtered out by session


def test_trace_tags_session(tmp_path, monkeypatch):
    monkeypatch.setattr(tracing, "TRACE_LOG", tmp_path / "t.jsonl")
    monkeypatch.setattr(tracing, "LOGS_DIR", tmp_path)
    tracing.set_session("demo-1")
    try:
        tracing.trace("ui_action", student_id="s1", action="x")
    finally:
        tracing.set_session(None)
    tracing.trace("ui_action", student_id="s1", action="y")
    rows = [json.loads(line) for line in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert rows[0]["session"] == "demo-1" and "session" not in rows[1]
