"""Render logs/traces.jsonl as a readable Markdown log (Person E, deliverable).

    uv run python scripts/render_traces.py                       # whole log
    uv run python scripts/render_traces.py --session demo-1021   # one demo run
    uv run python scripts/render_traces.py --since 2026-10-21 --out deliverables/execution_trace_log.md

Chat turns are shown step by step (question, intent, tool calls, answer);
UI actions (plan built, checks run, course added, ...) follow in a table.
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from advisor import tracing
from advisor.paths import REPO_ROOT, STUDENTS_JSON, TRACE_LOG

HIDDEN = {"ts", "event", "session", "student_id"}


def cell(value, limit: int = 300) -> str:
    """One Markdown table cell: single line, pipes escaped, long values cut."""
    text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= limit else text[:limit] + "…"


def details(r: dict) -> str:
    return "; ".join(f"{k.replace('_', ' ')}: {cell(v, 200)}" for k, v in r.items()
                     if k not in HIDDEN and v not in (None, "", []))


def local(ts: str) -> str:
    return datetime.fromisoformat(ts).astimezone().strftime("%b %d %Y, %H:%M:%S")


def render(records: list[dict], filters: str, source: Path) -> str:
    names = {s["student_id"]: s["name"] for s in json.loads(STUDENTS_JSON.read_text())}
    groups = tracing.group_turns(records)
    turns = [g for g in groups if g["kind"] == "turn"]
    actions = [g for g in groups if g["kind"] == "action"]
    try:
        shown_source = source.resolve().relative_to(REPO_ROOT)
    except ValueError:
        shown_source = source
    out = ["# Execution trace log", "",
           f"Generated {datetime.now().astimezone():%b %d %Y, %H:%M} from `{shown_source}`."
           f" Filters: {filters or 'none'}.", ""]
    if not records:
        return "\n".join([*out, "No trace records matched.", ""])

    out += ["## Summary", "",
            f"- **Time range:** {local(records[0]['ts'])} to {local(records[-1]['ts'])}",
            f"- **Chat turns:** {len(turns)}, **UI actions:** {len(actions)}, "
            f"**events:** {len(records)}",
            f"- **Students:** {', '.join(sorted({names.get(r['student_id'], r['student_id']) for r in records if r.get('student_id')}))}",
            "", "| Event | Count |", "|---|---|"]
    out += [f"| {e} | {n} |" for e, n in Counter(r["event"] for r in records).most_common()]
    out.append("")

    if turns:
        out += ["## Chat turns", ""]
        for i, g in enumerate(turns, 1):
            who = names.get(g["student_id"], g["student_id"])
            intent = f", intent `{g['intent']}`" if g["intent"] else ""
            out += [f"### Turn {i}: {who}, {local(g['start'])}{intent}, "
                    f"{tracing.duration_ms(g)} ms", "",
                    f"**Student:** {g['message']}", "",
                    "| Step | Event | Details |", "|---|---|---|"]
            out += [f"| {n} | {r['event']} | {cell(details(r))} |"
                    for n, r in enumerate(g["events"], 1)]
            reply = g["reply"] if g["reply"] is not None else "_(no reply logged)_"
            out += ["", "**Advisor:**", ""] + [f"> {line}" if line else ">"
                                               for line in reply.splitlines()] + [""]

    if actions:
        out += ["## UI actions", "", "| Time | Student | Action | Source | Details |",
                "|---|---|---|---|---|"]
        for g in actions:
            r = g["events"][0]
            extra = {k: v for k, v in r.items() if k not in ("action", "source")}
            out.append(f"| {local(r['ts'])} | {names.get(r.get('student_id'), r.get('student_id', ''))} "
                       f"| {r.get('action', r['event'])} | {r.get('source', '')} | {cell(details(extra))} |")
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", type=Path, default=TRACE_LOG)
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "deliverables" / "execution_trace_log.md")
    ap.add_argument("--since", help="ISO timestamp prefix, e.g. 2026-10-21 or 2026-10-21T15:00")
    ap.add_argument("--session", help="only records from this session id (see the app's Traces section)")
    ap.add_argument("--student", help="only records for this student_id")
    args = ap.parse_args(argv)

    records = tracing.read(args.input, since=args.since, session=args.session,
                           student_id=args.student)
    filters = ", ".join(f"{k} = {v}" for k, v in
                        (("since", args.since), ("session", args.session), ("student", args.student)) if v)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(records, filters, args.input), encoding="utf-8")
    print(f"Wrote {args.out} ({len(records)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
