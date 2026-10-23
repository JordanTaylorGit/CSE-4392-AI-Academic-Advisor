"""Execution-trace logger -> logs/traces.jsonl (required deliverable).

Every significant event — user message, routed intent, tool call, retrieval
hits, LLM prompt/response — is appended as one JSON line. Talha owns the
rendering of this log for the final zip (app Traces section and
scripts/render_traces.py both read it through read() / group_turns()).

Record shape (contract): {"ts", "event", **fields}. When a session is set
with set_session(), records also carry "session" so one app session or demo
run can be pulled out of the shared log.
"""

import json
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import LOGS_DIR, TRACE_LOG

_session: ContextVar[str | None] = ContextVar("trace_session", default=None)


def set_session(session_id: str | None) -> None:
    """Tag the following trace records (in this thread/context) with a session id."""
    _session.set(session_id)


def trace(event: str, **fields: Any) -> None:
    """Append one trace record. `event` names the kind: 'user_msg',
    'intent', 'tool_call', 'retrieval', 'llm_response', 'error', ..."""
    LOGS_DIR.mkdir(exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **({"session": s} if (s := _session.get()) else {}),
        **fields,
    }
    with TRACE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read(path: Path = TRACE_LOG, since: str | None = None, session: str | None = None,
         student_id: str | None = None) -> list[dict]:
    """Load trace records, oldest first, optionally filtered. `since` is an ISO
    timestamp prefix compared as a string (e.g. '2026-10-21' or '2026-10-21T15:00')."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue  # a partially written last line
        if since and r.get("ts", "") < since:
            continue
        if session and r.get("session") != session:
            continue
        if student_id and r.get("student_id") != student_id:
            continue
        out.append(r)
    return out


def group_turns(records: list[dict]) -> list[dict]:
    """Group records into chat turns (a user_msg up to its assistant_msg, per
    student) and standalone UI actions, oldest first.

    Records without a student_id join the open turn, if any.

    Turn:   {"kind": "turn", "student_id", "session", "start", "end",
             "message", "intent", "reply", "events": [...]}
    Action: {"kind": "action", "student_id", "session", "start", "end", "events": [record]}
    """
    groups: list[dict] = []
    open_turns: dict[str, dict] = {}  # student_id -> turn awaiting its reply
    for r in records:
        sid = r.get("student_id", "")
        turn = open_turns.get(sid)
        if not sid and turn is None and open_turns:
            # Router/chain/retrieval records often carry no student_id; they belong
            # to the turn in progress (the most recently opened one).
            turn = list(open_turns.values())[-1]
        if r["event"] == "user_msg":
            turn = {"kind": "turn", "student_id": sid, "session": r.get("session"),
                    "start": r["ts"], "end": r["ts"], "message": r.get("message", ""),
                    "intent": None, "reply": None, "events": [r]}
            open_turns[sid] = turn
            groups.append(turn)
        elif turn is not None:
            turn["events"].append(r)
            turn["end"] = r["ts"]
            if r["event"] == "intent":
                turn["intent"] = r.get("intent")
            elif r["event"] == "assistant_msg":
                turn["intent"] = turn["intent"] or r.get("intent")
                turn["reply"] = r.get("reply", "")
                open_turns.pop(sid, None)
        else:
            groups.append({"kind": "action", "student_id": sid, "session": r.get("session"),
                           "start": r["ts"], "end": r["ts"], "events": [r]})
    return groups


def duration_ms(group: dict) -> int:
    start = datetime.fromisoformat(group["start"])
    end = datetime.fromisoformat(group["end"])
    return int((end - start).total_seconds() * 1000)
