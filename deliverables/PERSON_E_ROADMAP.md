# Person E Roadmap — UI, Logging, Demo, PPT, Zip

Owner: Talha (branch `talha/ui-deliverables`). Work top to bottom; check off as done.
Due: Sun 10/25/2026. See `PLAN.md` §6–§9 for the team plan.

## Step 1 — Web UI (Streamlit) — spec req 1, 3 (dialog boxes), 4, 5c, 6
- [x] Layout: frosted top bar (segmented nav, student picker, More menu) + hero with credit progress
- [x] **Ask** — iMessage-style chat, suggested questions, typed replies, conversation state (req 6)
- [x] **Plan** — program / courses per semester / summer -> degree route timeline (req 2)
- [x] **Check a course** — course + semester -> six checks (a)-(f) (req 4)
- [x] **Add / Drop** dialog boxes (`st.dialog`) with confirmation + undo (req 3)
- [x] **Switch major** — new plan side by side + what changes (req 5c)
- [x] Graceful "not built yet" states + preview-data switch while teammates' modules are stubs
- [x] Apple/Stripe-style redesign, light + dark, Apple-style motion (reduced-motion safe)
- [x] Design review vs Apple HIG, contrast fixes -> `deliverables/design_review.md`
- [x] Commit + push branch `talha/ui-deliverables` (295d9ef). PR to main: later, when the team is ready
- [ ] Look at light mode on screen (only dark mode seen so far)
- [x] Year view · requirement rings · rich cards in chat answers — built on preview data;
      backend handoff documented in `ui/README.md`
- [ ] Merge with real backend: Person A seeds `requirement_slots` (rings go live, no UI change);
      Person D returns `{"text", "cards"}` from `handle_message` (cards go live)

## Step 2 — Logging / execution traces (deliverable)
- [x] Log every UI action via `tracing.trace("ui_action", ...)`; passive redraws not logged
- [x] Session id on every record (`tracing.set_session`) so one demo run can be pulled out
- [x] **Traces** section (More → Show execution traces): turns step by step, filters, search, download
- [x] `scripts/render_traces.py` -> readable `deliverables/execution_trace_log.md`
- [ ] Final log: render the demo session only, after Step 3
      (`uv run python scripts/render_traces.py --session <demo session id>`)

## Step 3 — Demo script
- [ ] `scripts/run_demo.py` replays the 7 prompts from `PLAN.md` §9, captures traces
- [ ] Demo personas + expected outputs written down for the presenters

## Step 4 — Screenshots
- [ ] One screenshot per demo step (input + output visible) -> `deliverables/screenshots/`

## Step 5 — PPT (30 min incl. Q&A)
- [ ] Architecture block diagram + component functions + I/O
- [ ] Design decisions considered and why we chose ours
- [ ] Code segments per component (what it does + why needed)
- [ ] Demo screenshots (what is the input, what the output means)

## Step 6 — Zip packaging
- [ ] Source code, `logs/traces.jsonl` + rendered log, embedding source docs, PPT
- [ ] Fresh-clone test: unzip -> run README quick start -> app works
