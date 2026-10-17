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
uv sync

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
  tracing.py        execution-trace logger -> logs/traces.jsonl          [Person E]
  seed/
    schema.sql      DB schema (CONTRACT — frozen)                        [Jordan]
    students.json   sample student personas                              [Jordan]
    schedule.json   fabricated sections, next 3 terms                    [Jordan]
    degree_reqs/    narrative degree-requirement docs (-> Chroma + SQL)  [Jordan]
    catalog/        cse_undergrad_courses.pdf + course-desc.jsonl        [have]
cli.py              stdlib reference client (UI contract example)        [Talha owns the real UI]
logs/traces.jsonl   execution trace log (deliverable)
deliverables/       PPT, screenshots, zip staging                        [Person E]
tests/              pytest
```

## Integration contracts (frozen — don't change without telling the team)

- **`seed/schema.sql`** — table names/columns. Jordan owns; everyone else reads only.
- **`tools.py`** — tool function signatures the orchestrator/UI call.
- **Degree-plan JSON shape** — `DegreePlan.to_dict()` in `planner.py`; UI and the
  compare module consume this shape.
- **Trace record shape** — `tracing.py` `trace()` fields; Person E renders the log.
- **UI contract** — `orchestrator.handle_message(student_id, message, history) -> str`.
  Talha picks the UI stack; `cli.py` shows the intended call pattern.

## Status of modules

Implemented now (scaffold): `paths`, `config` (backend switch), `db` (schema init
+ seed loading), `tracing`, `memory` (SQLite-backed chat history), `cli.py`
reference client.

Stubbed with `NotImplementedError` + docstrings (contracts are final, bodies are
TODOs for the owner): `planner`, `compare`, `router`, `chains`, `tools`,
`orchestrator`, `ingest`.

The app runs today — every query answers "not implemented yet" until the owner
fills in their module.
