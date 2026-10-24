# CSE 4392 — Academic AI Advisor

Team Assignment 2: an Academic AI Advisor built on **LangChain**, with a SQL
database (SQLite) for structural data, a vector database (Chroma) for
unstructured data, and a deterministic **Degree Planner** engine that
generates and verifies multi-year degree plans.

**UI is Talha's choice** (web, desktop, or CLI — all allowed by the spec). The
only contract a UI must satisfy is:

```python
orchestrator.handle_message(student_id: str, message: str,
                            history: list[dict]) -> str
```

`cli.py` is a stdlib reference client that exercises that contract today.

See `PLAN.md` for the full architecture, work split, and timeline.

## Quick start

```bash
# 1. Install deps (uses uv; https://docs.astral.sh/uv/)
uv sync --python 3.13

# 2. Pick an LLM backend (default: local Ollama)
cp .env.example .env          # edit if needed
ollama pull qwen3:4b          # local chat model
ollama pull nomic-embed-text  # local embedding model
# ...or set ADVISOR_LLM=openai and OPENAI_API_KEY in .env

# 3. Build the databases
uv run python -m advisor.db        # creates + seeds advisor.db (SQLite)
uv run python -m advisor.ingest    # embeds catalog + degree docs into .chroma/

# 4. Run the reference CLI
uv run python cli.py
```

## Repo layout

```
advisor/            the package
  config.py         LLM/embeddings backend switch (ollama | openai)      [Kyle]
  paths.py          repo-relative paths                                  [shared]
  db.py             SQLite engine, schema init, seed loaders             [Jordan]
  planner.py        Degree Planner + 6-check Verification Engine         [Loc]
  compare.py        plan diff (old plan vs new plan)                     [Loc]
  router.py         LLM intent classifier                                [Kyle]
  chains.py         RAG chain + SQL tool chain                           [Miguel/Kyle]
  tools.py          LangChain tool signatures (CONTRACT — frozen)        [Kyle]
  memory.py         conversation state + persisted chat history          [Kyle]
  orchestrator.py   handle_message(): router -> handlers, tracing        [Kyle]
  ingest.py         Chroma ingest pipeline (catalog, degree docs)        [Miguel]
  tracing.py        execution-trace logger -> logs/traces.jsonl          [Talha]
  seed/
    schema.sql      DB schema (CONTRACT — frozen)                        [Jordan]
    students.json   sample student personas                              [Jordan]
    schedule.json   fabricated sections, next 3 terms                    [Jordan]
    degree_reqs/    narrative degree-requirement docs (-> Chroma + SQL)  [Jordan]
    catalog/        cse_undergrad_courses.pdf + course-desc.jsonl        [have]
cli.py              stdlib reference client (UI contract example)        [Talha owns the real UI]
logs/traces.jsonl   execution trace log (deliverable)
deliverables/       PPT, screenshots, zip staging                        [Talha]
tests/              pytest
```

## Integration contracts (frozen — don't change without telling the team)

- **`seed/schema.sql`** — table names/columns. Jordan owns; everyone else reads only.
- **`tools.py`** — tool function signatures the orchestrator/UI call.
- **Degree-plan JSON shape** — `DegreePlan.to_dict()` in `planner.py`; UI and the
  compare module consume this shape.
- **Trace record shape** — `tracing.py` `trace()` fields; Talha renders the log.
- **UI contract** — `orchestrator.handle_message(student_id, message, history) -> str`.
  Talha picks the UI stack; `cli.py` shows the intended call pattern.

## Status of modules

Implemented now (scaffold): `paths`, `config` (backend switch), `db` (schema init
+ seed loading), `tracing`, `memory` (SQLite-backed chat history), `cli.py`
reference client.

## Deterministic planner (Loc)

Run the tests without Ollama, OpenAI credentials, or an embedding database:

```bash
uv sync --python 3.13
uv run pytest -q
```

Python 3.13 is the tested runtime; the locked ONNX dependency does not currently have a Python 3.15 wheel.
Tests use temporary SQLite databases, including a small complete catalog.

The planner supports these operations:

- `generate_plan(student_id, program_id=None, include_summer=False, courses_per_semester=None)` orders courses by prerequisite readiness, packs semesters, and returns a `DegreePlan`.
- `verify_course(student_id, course_id, term, plan=None)` always returns the six named checks in contract order, including detailed failure reasons.
- `add_course` and `drop_course` return independent plans and recheck the remaining courses.
  Invalid additions are rejected; dropping a prerequisite leaves its dependent courses visible with warnings.
- `diff_plans(old, new)` separates additions, removals, and moves and reports semester/credit changes.
- The LangChain tools generate and save plans, modify the latest saved plan, verify against it, and atomically save a new plan with a major change.
  Batch additions are checked together so mutual corequisites can be added in one request.
  Course additions/removals require an explicit term.

### Planning rules and assumptions

- Prerequisite groups are ANDed; alternatives within a group are ORed.
  Recorded minimum grades are enforced.
  Earlier planned prerequisites are conditional on passing them; they are not recorded as completed courses.
- Prerequisites listed in `prereq_concurrent` may share a term.
- A course fills at most one degree requirement.
  Fixed slots and elective options lists are supported; a course must be explicitly listed to count.
- Completed CSE courses need C or better to count toward the degree; other courses need D or better.
  Unknown grades, pass/fail codes, and incompletes do not establish a letter-grade threshold.
- Semester credit totals use catalog values and include current enrollments once.
  Degree caps include applicable completed credits and all planned/enrolled courses, without double-counting the same course.
- Section selection searches alternative combinations and keeps enrolled sections fixed.
  Missing sections, unknown meeting times, and conflicting meetings fail verification.
- Planning starts at the first available term at or after the student's start term and after the latest completed transcript term.
  Summer is optional, and an explicit course-count limit also respects the credit cap.
- Generation is deterministic. Past the published schedule it assumes catalog offering
  patterns — 1000/2000-level every term, 3000+ at least Fall/Spring — and flags those
  terms as projections rather than certifying meeting times.
  Missing data, prerequisite cycles, unmet admission conditions, or infeasible loads produce partial plans with warnings.
  It does not promise a globally optimal graduation date.
- Saved plans keep course assignments in `plan_semesters`; warnings are recalculated on load.

### Integration status

Main's seed loader currently creates zero requirement slots or prerequisite rows.
It also provides only three terms of sections.
Jordan's complete degree requirements, prerequisite data, and schedules are needed before the seeded personas can produce useful verified degree plans.
The planner reports missing requirements explicitly instead of manufacturing degree rules.
The original schema and Jordan's data files are unchanged by this work.

Verification includes a seven-semester prerequisite chain, all six checks, alternative sections, caps, overlapping electives, corequisite bundles, admission restrictions, passing retakes, add/drop, comparison, persistence, and major changes.
