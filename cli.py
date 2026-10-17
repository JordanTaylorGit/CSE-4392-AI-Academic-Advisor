"""Minimal CLI client — reference implementation of the UI contract.

Run:  uv run python cli.py

This exists so the rest of the team always has a working front-end while
Talha builds the real UI (spec req 1 allows web, desktop, or CLI). The ONLY
function a UI needs is:

    orchestrator.handle_message(student_id, message, history) -> str

`history` is the displayed transcript as [{'role', 'content'}] — pass the
session's messages so follow-ups ("what about 3 classes instead?") resolve.
"""

import sys

from advisor import db, orchestrator


def pick_student() -> str:
    students = db.query(
        "SELECT student_id, name, program_id FROM students ORDER BY student_id"
    )
    if not students:
        sys.exit("No students seeded — run: uv run python -m advisor.db")
    print("Students:")
    for i, s in enumerate(students, 1):
        print(f"  {i}. {s['name']}  ({s['student_id']}, {s['program_id']})")
    while True:
        try:
            return students[int(input("Select [1]: ") or "1") - 1]["student_id"]
        except (ValueError, IndexError):
            print("Invalid choice.")


def main() -> None:
    db.init_db()
    student_id = pick_student()
    history: list[dict] = []
    print("\nAI Advisor ready. 'quit' to exit.\n")
    while True:
        try:
            msg = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not msg or msg.lower() in {"quit", "exit", "q"}:
            break
        reply = orchestrator.handle_message(student_id, msg, history)
        history += [{"role": "user", "content": msg},
                    {"role": "assistant", "content": reply}]
        print(f"\n{reply}\n")


if __name__ == "__main__":
    main()
