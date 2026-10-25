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
- [x] Commit + push branch `talha/ui-deliverables` (e6b9489 after rebase onto main). PR to main: later, when the team is ready
- [x] Look at light mode on screen (screenshots are light mode; reads well)
- [x] Year view · requirement rings · rich cards in chat answers — built on preview data;
      backend handoff documented in `ui/README.md`
- [ ] Merge with real backend: Person A seeds `requirement_slots` (rings go live, no UI change);
      Person D returns `{"text", "cards"}` from `handle_message` (cards go live)
      - [x] Jordan's `Data` merged: rings live, current F2026 enrollments count as in progress,
            "Concentration" -> "Certificate", preview totals 123 / 127
      - [x] Transcript download (.csv) in More
      - [x] Chat hardening: backend errors become a reply, leaked qwen3 reasoning hidden
      - [x] `.python-version` 3.13 (onnxruntime has no 3.15 wheels)

## Step 2 — Logging / execution traces (deliverable)
- [x] Log every UI action via `tracing.trace("ui_action", ...)`; passive redraws not logged
- [x] Session id on every record (`tracing.set_session`) so one demo run can be pulled out
- [x] **Traces** section (More → Show execution traces): turns step by step, filters, search, download
- [x] `scripts/render_traces.py` -> readable `deliverables/execution_trace_log.md`
- [ ] Final log: render the demo session only, after Step 3
      (`uv run python scripts/render_traces.py --session <demo session id>`)

## Step 3 — Demo script
- [x] `scripts/run_demo.py` replays the 7 prompts from `PLAN.md` §9, captures traces
      (tested 10/23 on all branches merged: 7/7 run; step 7 hits Kyle's term bug)
- [x] Presenter guide: `deliverables/DEMO_GUIDE.md` (walk-through, warm-up, fallbacks)
- [x] Final run on merged main (10/24, session `demo-final`): `demo_transcript.md` + `execution_trace_log.md`
      (chat add/drop step removed: orchestrator fails with "explicit term is required")

## Step 4 — Screenshots
- [x] `scripts/take_screenshots.py`: headless Chrome walks DEMO_GUIDE, 11 PNGs
      (draft set taken 10/23 on all branches merged)
- [x] Final set on merged main -> `deliverables/screenshots/` (10/24)

## Step 5 — PPT (30 min incl. Q&A)
- [x] `scripts/build_slides.py` -> `deliverables/AI_Advisor_Presentation.pptx` (23 slides, speaker notes)
- [x] Architecture block diagram + component functions + I/O
- [x] Design decisions considered and why we chose ours
- [x] Code segments per component (what it does + why needed)
- [x] Demo screenshots (what is the input, what the output means)
- [x] Rebuilt from final screenshots, following the professor's TA2 template outline (30 slides)
- [ ] Full names for Miguel and Kyle on the title slide; teammates review their code slides

## Step 6 — Zip packaging
- [x] `scripts/package_submission.py` -> `dist/CSE4392_TA2_AI_Advisor.zip` (HEAD + traces + SUBMISSION.md)
- [x] Fresh-unzip test (10/23, all branches merged): uv sync, seed, ingest, 89 tests pass, app starts

## Final run (after every PR is merged into main)

```bash
git switch main && git pull
rm -f advisor.db && uv run python -m advisor.db && uv run python -m advisor.ingest
uv run streamlit run app.py                                   # terminal 1, keep running
uv run --with playwright python scripts/take_screenshots.py   # terminal 2 -> deliverables/screenshots/
uv run python scripts/run_demo.py --session demo-final        # transcript + execution_trace_log.md
uv run --with python-pptx python scripts/build_slides.py      # deck from the final screenshots
git add deliverables && git commit -m "Final demo outputs, screenshots, deck" && git push
uv run python scripts/package_submission.py                   # dist/CSE4392_TA2_AI_Advisor.zip
```

Screenshots run before the demo script: the demo's "switching to Software
Engineering" step changes Sam's major in advisor.db (backend bug). Reseed
(`rm -f advisor.db && uv run python -m advisor.db`, restart the app) before presenting.
