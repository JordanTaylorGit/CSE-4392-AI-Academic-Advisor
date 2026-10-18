# UI ↔ backend contract (Person E)

The Streamlit UI (`app.py`, `ui/`) talks to the backend only through `ui/services.py`.
Until a backend function is implemented, the UI shows a "not built yet" note, or
placeholder data when **More → Use preview data** is on. Nothing in the UI changes
when the real code lands: implement the function and turn preview off.

| UI feature | Backend it calls | Owner | Status |
|---|---|---|---|
| Plan (timeline + year view) | `planner.generate_plan(...).to_dict()` | B | stub |
| Add / drop dialogs | `planner.add_course`, `planner.drop_course` | B | stub |
| Can I take it? (six checks) | `planner.verify_course` → `CheckResult` list | B | stub |
| Switch major comparison | `compare.diff_plans` | B | stub |
| Requirement rings | `requirement_slots` table (read directly in `services._requirements_live`) | A | table empty |
| Chat | `orchestrator.handle_message` | D | router stub |

## Requirement rings (Person A)

No new code needed: seed `requirement_slots` per `schema.sql` (one row per slot,
`category` in `core`, `math_science`, `cse_core`, `concentration`, `elective`;
`course_id` for a fixed course or `options` as a JSON list for an elective slot).
The UI sums `credits` per category and fills each slot with at most one completed
or planned course.

## Chat replies with cards (Person D)

`orchestrator.handle_message(student_id, message, history)` may keep returning a
plain `str`. To show rich cards under the answer, return a dict instead:

```python
{
  "text": "I built a semester-by-semester plan to graduation.",
  "cards": [                      # optional, any number, rendered in order
    {"type": "plan",    "plan": DegreePlan.to_dict()},           # + "Open in Plan" button
    {"type": "checks",  "course_id": "CSE 4344", "term": "S2027",
                        "checks": [asdict(r) for r in verify_course(...)]},
    {"type": "courses", "courses": [{"course_id", "title", "credits", "description"}]},
    {"type": "diff",    "old": plan_dict, "new": plan_dict,
                        "diff": compare.diff_plans(old, new)},
  ],
}
```

Suggested mapping from intents: `GENERATE_PLAN`/`MODIFY_PLAN` → `plan`,
eligibility questions → `checks`, `SEMANTIC_QUERY` hits → `courses`,
`SWITCH_MAJOR` → `diff`. Unknown card types are ignored. `memory.add_message`
should store `text` only.

The placeholder answers in `ui/preview.py::chat_reply` use exactly this shape,
so they double as examples.
