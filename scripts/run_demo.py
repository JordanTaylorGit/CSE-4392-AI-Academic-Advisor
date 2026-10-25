"""Run the presentation demo end to end and capture its traces (Person E, deliverable).

    uv run python scripts/run_demo.py                # Sam Martinez, the 7 PLAN.md §9 prompts
    uv run python scripts/run_demo.py --student s_switcher --session demo-final

Each prompt goes through ui/services.ask, the same path as the app's Ask screen,
with the conversation carried forward so follow-ups ("only 3 classes instead?")
resolve. Every record is tagged with one session id, then this writes:

    deliverables/demo_transcript.md        question, answer, intent, time per step
    deliverables/execution_trace_log.md    the rendered trace log for the zip

Needs the databases built (advisor.db, .chroma/) and, for the LLM steps, Ollama
running with the models in .env (see README quick start).
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import render_traces

from advisor import tracing
from advisor.paths import REPO_ROOT, TRACE_LOG
from ui import services as svc

# PLAN.md §9, one prompt per spec requirement it demonstrates.
STEPS = [
    ("Req 2: multi-year degree plan",
     "I'm a sophomore CS major interested in cybersecurity. Generate my degree plan."),
    ("Req 3: exact query (SQL)", "What are the prerequisites for CSE 3310?"),
    ("Req 3: semantic query (RAG)", "Which courses cover machine learning or AI topics?"),
    # Term as a code: the orchestrator reads "next semester" as the current term (F2026).
    ("Req 4: six verification checks", "Can I take CSE 4344 in S2027?"),
    ("Req 6: conversation state", "What about taking only 3 classes next semester instead?"),
    ("Req 5: switch major + comparison", "I'm thinking about switching to Software Engineering."),
    # Add / drop by chat fails ("An explicit term is required"); the demo shows it on
    # the Plan screen's dialogs instead. Restore once orchestrator passes the term.
]


def run(student_id: str, session: str) -> list[dict]:
    tracing.set_session(session)
    messages: list[dict] = []
    results = []
    for n, (label, prompt) in enumerate(STEPS, 1):
        print(f"[{n}/{len(STEPS)}] {prompt}", flush=True)
        messages.append({"role": "user", "content": prompt})
        start = time.perf_counter()
        try:
            reply, _ = svc.ask(student_id, prompt, messages, None, use_preview=False)
            text = reply["text"]
        except svc.NotReady as e:
            text = f"(not built yet: {e})"
        seconds = time.perf_counter() - start
        messages.append({"role": "assistant", "content": text})
        results.append({"label": label, "prompt": prompt, "reply": text, "seconds": seconds})
        print(f"      {seconds:.1f}s  {text.splitlines()[0][:90] if text else ''}", flush=True)
    tracing.set_session(None)
    return results


def intents(session: str) -> list[str | None]:
    """The routed intent of each turn, from the trace log."""
    turns = [g for g in tracing.group_turns(tracing.read(session=session)) if g["kind"] == "turn"]
    return [t["intent"] for t in turns]


def write_transcript(path: Path, student: dict, session: str, results: list[dict]) -> None:
    routed = intents(session)
    out = ["# Demo transcript", "",
           f"Student: **{student['name']}** (`{student['student_id']}`, {student['program_id']}). "
           f"Session `{session}`, run {datetime.now().astimezone():%b %d %Y, %H:%M}.", "",
           "| # | Demonstrates | Intent | Time |", "|---|---|---|---|"]
    out += [f"| {n} | {r['label']} | {routed[n - 1] if n <= len(routed) else ''} | {r['seconds']:.1f} s |"
            for n, r in enumerate(results, 1)]
    for n, r in enumerate(results, 1):
        out += ["", f"## {n}. {r['label']}", "", f"**Student:** {r['prompt']}", "",
                "**Advisor:**", ""] + [f"> {line}" if line else ">" for line in r["reply"].splitlines()]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--student", default="s_sophomore", help="student_id (default: Sam Martinez)")
    ap.add_argument("--session", default=f"demo-{datetime.now():%m%d-%H%M}",
                    help="session id stamped on every trace record")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "deliverables")
    args = ap.parse_args(argv)

    students = svc.students()
    if args.student not in students:
        ap.error(f"unknown student {args.student!r}; one of {', '.join(students)}")
    results = run(args.student, args.session)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_transcript(args.out_dir / "demo_transcript.md", students[args.student], args.session, results)
    render_traces.main(["--session", args.session, "--out", str(args.out_dir / "execution_trace_log.md")])
    (args.out_dir / "demo_session.json").write_text(
        json.dumps({"session": args.session, "student_id": args.student,
                    "trace_log": str(TRACE_LOG.relative_to(REPO_ROOT))}, indent=2) + "\n")
    print(f"Done. Session {args.session}: {args.out_dir / 'demo_transcript.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
