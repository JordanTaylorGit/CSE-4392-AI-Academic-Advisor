# Demo guide (presenters)

About 8 minutes of the 30-minute slot. One student, **Sam Martinez** (`s_sophomore`):
BS Computer Science + Cybersecurity certificate, 32 credits done, 4 classes in
progress this fall (F2026 is the current term).

## Before you present (10 minutes ahead)

```bash
uv sync
rm -f advisor.db && uv run python -m advisor.db     # fresh seed
uv run python -m advisor.ingest                      # Chroma index (needs Ollama)
uv run streamlit run app.py                          # http://localhost:8501
```

1. Check Ollama is running: `ollama list` shows `qwen3:4b`, `qwen3:0.6b`, `nomic-embed-text`.
2. **Warm the model**: ask one throwaway question in Ask (the first answer loads the
   model and takes about a minute; after that, 20 to 40 seconds). Ollama unloads it
   after 5 idle minutes, so do this right before you start.
3. More → **Use preview data** must be **off**. Turn on **Show execution traces**.
4. More → **Clear the conversation**, so Ask starts fresh.

## The walk-through

Each step names the spec requirement it shows. Say the input, then what the output means.

| # | Where | Do | What it shows (requirement) |
|---|---|---|---|
| 1 | Top bar | Pick Sam Martinez | Web UI; the student is already signed in (req 1) |
| 2 | Hero + Plan | Point at credit progress and the requirement rings | Structured data from SQLite: completed (green) and in-progress (blue) credits per area |
| 3 | Plan | **Build plan**, then switch Timeline / Years | Semester-by-semester degree plan for his career interest (req 2) |
| 4 | Plan | **Add** a course: the dialog runs the six checks before the button enables. Then **Drop**, then **Undo** | Dialog boxes (req 1) and changing a plan (req 5a) |
| 5 | Check a course | CSE 4344, Spring 2027, **Run checks** | The six verification checks (a)-(f) with reasons (req 4) |
| 6 | Ask | "What are the prerequisites for CSE 3310?" | Exact query, answered from SQL (req 3) |
| 7 | Ask | "Which courses cover machine learning or AI topics?" | Semantic query, answered by RAG over Chroma (req 3, 7, 8) |
| 8 | Ask | "Generate my degree plan", then "What about taking only 3 classes next semester instead?" | Conversation state: the follow-up uses the earlier turn (req 6) |
| 9 | Switch major | Pick Software Engineering + AI | New plan side by side with the old one, and what changes (req 5c) |
| 10 | Traces | Open the latest chat turn | Execution trace: question, routed intent, retrieval hits, LLM answer, timing (deliverable) |
| 11 | More | **Download transcript** | Small extra: the record as a CSV |

## Expected output (from `scripts/run_demo.py`)

`deliverables/demo_transcript.md` holds the exact answers from the last scripted run.
Highlights for Sam:

- Prerequisites for CSE 3310: CSE 1320, CSE 1325, CSE 2315 (min grade C).
- Machine learning / AI courses: CSE 4308, CSE 4309, CSE 4311.
- Cybersecurity certificate: CSE 4344 (or 4352), CSE 4380, CSE 4381, CSE 4382 (12 credits).

## If something goes wrong

- **An answer takes long**: the spinner is the local model working. Keep talking
  through what the step shows; don't click again.
- **"I couldn't answer that: …"**: the backend rejected that phrasing. Move to the next
  step; the same feature is on the Plan / Check a course screens.
- **"This part of the advisor isn't built yet"**: preview is off and that backend piece
  is missing on this checkout. Pull the latest `main`.
- **Ollama errors**: `brew services restart ollama`, then warm the model again.
- Worst case, show `deliverables/demo_transcript.md` and the screenshots.

## Re-running the scripted demo

```bash
uv run python scripts/run_demo.py --session demo-final
```

Writes `deliverables/demo_transcript.md` and `deliverables/execution_trace_log.md`
(the rendered trace log for the zip) for that session only.
