# Team Assignment 2 — The AI Advisor: Project Plan

**Due:** Sunday 10/25/2026 (zip + PPT, 30-min presentation)
**Spec:** `TA2-AI-Advisor-2.pdf` — a LangChain-based Academic AI Advisor that generates
multi-year degree plans and answers exact + semantic advising queries.

## 1. Key decisions

| Decision | Choice | Why |
|---|---|---|
| UI | **Talha's choice** (web/desktop/CLI — all spec-legal) | Talha owns task 5; the scaffold ships a stdlib `cli.py` reference client. The only contract: `orchestrator.handle_message(student_id, message, history) -> str` |
| LLM backend | **Pluggable: Ollama (default) + OpenAI API** | Ollama is installed locally (qwen3:4b, llama3.2:3b, nomic-embed-text) — free, offline. OpenAI via `OPENAI_API_KEY` for better quality when available. LangChain makes both interchangeable behind one interface |
| Framework | **LangChain** (required by spec) + Chroma + SQLite | Spec requires LangChain; Chroma is a local vector DB (no account needed); SQLite is the SQL DBMS |
| Python env | **uv** (single `pyproject.toml`) | Matches existing repo tooling (`RAG/app.py` uses uv) |
| Degree-plan generation | **Deterministic planner component, NOT the LLM** | The spec explicitly hints an LLM can't reliably generate valid plans. A Python "Degree Planner" does the work; the LLM presents it. This is the "component that fills the gap" the professor wants on the architecture diagram |
| Agent architecture | **Intent router → specialized tools/chains** | Small local models are unreliable at free-form tool calling. An LLM intent classifier routes to: SQL chain (exact queries), RAG chain (semantic queries), Degree Planner (plan ops), Advising Dialog (major-change counseling). Each step is narrowly prompted — robust on qwen3:4b and better on OpenAI |

## 2. Architecture (this is also the PPT block diagram)

```
                          ┌──────────────────────────────┐
   Student ──chat──▶      │  UI (Talha's choice)         │
                          └──────────────┬───────────────┘
                                         │
                          ┌──────────────▼───────────────┐
                          │  LangChain Orchestrator      │
                          │  · conversation memory       │
                          │  · intent router (LLM)       │
                          └───┬────────┬────────┬────────┘
              ┌───────────────┘        │        └────────────────┐
              ▼                        ▼                         ▼
   ┌──────────────────┐  ┌───────────────────────┐  ┌─────────────────────────┐
   │ SQL Tool Chain   │  │ RAG Chain             │  │ Degree Planner          │
   │ (exact queries:  │  │ (semantic queries:    │  │ (deterministic engine)  │
   │ prereqs, record, │  │ course content, reqs, │  │ · prereq DAG topo-sort  │
   │ schedule)        │  │ policies)             │  │ · 6-check verifier      │
   └───────┬──────────┘  └───────────┬───────────┘  │ · plan diff/compare     │
           │                       │              └───────────┬─────────────┘
           ▼                       ▼                          │
   ┌──────────────┐      ┌──────────────────┐                 │
   │ SQLite       │      │ Chroma vector DB │◀────────────────┘
   │ courses,     │      │ catalog chunks,  │
   │ prereqs,     │      │ degree-req docs, │
   │ sections,    │      │ policies,        │
   │ students,    │      │ chat history     │
   │ enrollments, │      └──────────────────┘
   │ plans        │
   └──────────────┘
        ▲
   ┌────┴─────────────┐
   │ Trace Logger     │  every intent, tool call, retrieval (ids+scores),
   │ logs/traces.jsonl│  prompt+response → required "log of execution traces"
   └──────────────────┘
```

Components to name on the slide: UI, Orchestrator (memory + intent router),
SQL Tool Chain, RAG Chain, Degree Planner, Verification Engine, SQLite DBMS,
Chroma DBMS, Trace Logger, pluggable LLM adapter (Ollama | OpenAI).

## 3. Requirement → implementation → demo mapping

| Spec req | Implementation | Demo line in presentation |
|---|---|---|
| 1. UI | Talha's chosen front-end over `handle_message` | Show the running app |
| 2. Multi-year degree plan per career interest | Degree Planner: topo-sort prereq DAG, fill semesters ≤ credit cap, optional summer | "I'm a sophomore interested in cybersecurity — build my plan" |
| 3. Exact + semantic queries | Intent router → SQL chain vs RAG chain | "Prereqs for CSE 3310?" (exact) then "Which courses cover machine learning?" (semantic) |
| 4. Six verification checks before recommending | Verification Engine in planner; each recommendation returns check results | "Can I take CSE 4344 next semester?" → per-check pass/fail table |
| 5. Change plan / switch major + comparison | Advising Dialog (multi-turn needs-assessment) → regenerate plan → `compare_plans` diff | "What if I switch to Software Engineering?" → new plan + side-by-side diff |
| 6. Conversation state | Session message list passed to `handle_message` + persisted chat history | "What about only 3 classes next semester instead?" |
| 7. Structural + nonstructural DBs | SQLite (records/courses/schedule/enrollment) + Chroma (catalog, degree reqs, chat history) | Show the two stores in the diagram |
| 8. Multiple DBMS types | SQLite + Chroma (spec names SQL + Chroma/Pinecone explicitly) | One bullet on slide |

## 4. Data plan (biggest hidden work item)

| Dataset | Source | Status |
|---|---|---|
| Course catalog text | `Notes/cse_undergrad_courses.pdf` — existing parser in `RAG/app.py` (`load_courses`) | Have it; reuse chunker |
| Course descriptions | `Notes/course-desc.jsonl` (75 CSE courses) | Have it |
| Prerequisites | Parse prereq clauses from catalog entry text; regex for common patterns + hand-curated table for the ~75 CSE courses | **Must build** |
| Degree requirements | **Author 2 program docs**: BS CS w/ Cybersecurity concentration, BS SE w/ AI concentration (~120 hrs: core curriculum, math/science, CSE core, concentration electives). Store structured slots in SQLite AND narrative text in Chroma | **Must create** — largest single data task |
| Class schedule | Fabricate sections for next 3 terms (Fall/Spring/Summer) with days/times so conflict-checking is real | Must create |
| Student records | 3–4 personas: new freshman, mid-degree CS student, SE student eyeing a switch, near-grad senior | Must create |
| Advising/chat history | Written by the app itself into SQLite + Chroma | Automatic |

## 5. Repo layout

```
Assignments/Team Assignment 2/advisor/
  pyproject.toml            # uv project: langchain, langchain-ollama, langchain-openai,
                            # langchain-chroma, chromadb, pypdf, sqlalchemy
                            # (UI deps added by Talha when he picks a stack)
  advisor/
    config.py               # LLM backend switch: ollama | openai (env or sidebar)
    db.py                   # SQLite access (SQLAlchemy)
    planner.py              # Degree Planner + Verification Engine
    compare.py              # plan diff
    router.py               # intent classifier
    chains.py               # RAG chain, SQL tool chain
    tools.py                # LangChain tools (planner, record lookup, schedule, eligibility)
    memory.py               # conversation state + persisted chat history
    ingest.py               # Chroma ingest (reuses RAG/app.py loader)
    tracing.py              # execution-trace logger → logs/traces.jsonl
    seed/                   # schema.sql, degree_reqs/*.md, schedule.json, students.json
  cli.py                    # stdlib reference client; Talha adds the real UI
                            # on top of orchestrator.handle_message()
  logs/traces.jsonl
  deliverables/             # PPT, screenshots, zip staging
```

## 6. Work split — 5 people

| Person | Workstream | Delivers |
|---|---|---|
| **A — Data (Jordan)** | SQLite schema + seed; prereq parser; author 2 degree-req docs; fabricate schedule + students | `schema.sql`, `seed/`, parser script |
| **B — Planner (Loc)** | Degree Planner: prereq DAG topo-sort, semester packing, 6-check verifier, plan diff | `planner.py`, `compare.py`, unit tests |
| **C — RAG (Miguel)** | Chroma ingest (catalog + degree docs + policies), retriever chain, embedding config for both backends | `ingest.py`, RAG chain |
| **D — Agent (Kyle)** | LangChain orchestrator: intent router, tools, memory, advising dialog, LLM backend abstraction | `router.py`, `tools.py`, `chains.py`, `config.py` |
| **E — UI/Deliverables (Talha)** | UI (his choice of stack) over `handle_message`, trace logger, demo script, screenshots, PPT, zip packaging | UI files, `tracing.py`, `deliverables/` |

Integration contract (freeze early, everyone codes against it): the data schema,
the tool signatures in `tools.py`, and the JSON shape of a degree plan.

## 7. Timeline (8 days)

| Day | Milestone |
|---|---|
| Sat 10/17–Sun 10/18 | Kickoff: agree on this plan + schema + tool signatures. Scaffold is pushed to `main`. A starts schema/seed, C ports `RAG/app.py` ingest to Chroma, D stubs orchestrator, Talha picks the UI stack |
| Mon 10/19–Tue 10/20 | **Core loop works**: exact query → SQL answer; semantic query → RAG answer; "generate my plan" → valid multi-year plan in UI |
| Wed 10/21 | Plan modification, add/drop, major-switch dialog + plan comparison; all 6 verification checks firing |
| Thu 10/22 | Demo script end-to-end, memory follow-ups working, trace logging verified; **feature freeze** |
| Fri 10/23 | Bugfix only. E: screenshots, PPT draft, execution-trace log collected |
| Sat 10/24 | Rehearse 30-min presentation, finalize PPT, build + verify zip |
| Sun 10/25 | Buffer / submit |

## 8. Deliverables checklist (from spec §4)

- [ ] Zip containing everything below
- [ ] PPT: architecture block diagram (§2), important code segments (what each does + why), demo screenshots
- [ ] Source code
- [ ] Log of execution traces (`logs/traces.jsonl`)
- [ ] Documents used to generate embeddings (`seed/degree_reqs/`, catalog chunks)

## 9. Demo script (drives screenshots + presentation)

1. "I'm a sophomore CS major interested in cybersecurity — generate my degree plan."
2. "What are the prerequisites for CSE 3310?" → exact SQL path
3. "Which courses cover machine learning or AI topics?" → semantic RAG path
4. "Can I take CSE 4344 next semester?" → 6-check verification table
5. "What about taking only 3 classes next semester instead?" → memory follow-up
6. "I'm thinking about switching to Software Engineering." → advising dialog → new plan → side-by-side comparison with pros/cons
7. "Drop CSE 3310 from next semester and add CSE 3302." → modify plan

## 10. Risks

| Risk | Mitigation |
|---|---|
| Small local models are unreliable tool-callers | Router architecture (narrow prompts per step); OpenAI fallback via env var for the demo if needed |
| Degree-requirement data doesn't exist | Jordan authors it day 1 — it's a fabricated-but-realistic dataset; the spec only requires the system to work, not real UTA audits |
| Prereq parsing from PDF prose is messy | Parse the common "Prerequisite: X, Y" patterns; hand-curate stragglers in a table — 75 courses is small enough |
| Scope creep | Fixed scope: 2 degree programs, ~4 students, next-3-terms schedule only |
| Integration pain late in the week | Freeze schema + tool signatures on day 1; core loop must work by Tue |
