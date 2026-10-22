# Seed data changes — 2026-10-21 (Jordan)

Seed data now comes from the real UTA 2026-27 catalog instead of fabricated requirements.
Regenerate everything with `uv run python advisor/seed/build_seed_data.py`, then delete
`advisor.db` and run `uv run python -m advisor.db`. Do not hand-edit generated files.

## Contract impact (read this)

| Area | Change |
|---|---|
| Schema | **Existing tables/columns unchanged.** Two new tables added: `professional_courses`, `prereq_concurrent`. |
| Program ids | `bs_cs_cyber`, `bs_se_ai` unchanged. Names changed; **total credits are now 123 and 127** (were 120/120). |
| Program meaning | UTA has no CS/SE "concentrations". `bs_cs_cyber` = BS CS + Cybersecurity *certificate*; `bs_se_ai` = BS SE + AI *certificate*. |
| `courses.credits` | Real hours from the catalog PDF (was hard-coded 3). |
| `prerequisites` | Now populated (132 rows). Same `group_id` = OR; different groups = AND. `min_grade` is `D` when the catalog states none. |
| Concurrent prereqs | `prereq_concurrent(course_id, prereq_id)`: that prerequisite may be taken in the same term. |
| Professional program | `professional_courses`: courses requiring admission to the Engineering Professional Program. |
| `requirement_slots` | Populated (83 rows). Elective/choice slots have `course_id NULL` + `options` JSON; "choose 4" = four identical slots. General-core buckets list *sample* courses only. |
| Current term | **F2026 is the current term**: students' F2026 courses are in `enrollments` (section ids), `completed_courses` ends at S2026/SU2026, planning starts S2027. |
| `students.json` | New `current_enrollments` field. Personas rebuilt so every transcript satisfies the catalog prerequisites. |
| `schedule.json` | Regenerated: 165 sections, F2026/S2027/SU2027, all program courses, clash-free current schedules for personas. |

## Facts in the old seed docs that were wrong

- CSE 1105 is not the required intro course; the plans require **CSE 1106**.
- CSE 4351 / 4352 are **not** the SE capstone: 4351 = Parallel Processing, 4352 = IoT and Networking. The capstone (both degrees) is **CSE 4316 → 4317**.
- CSE 4310 = Computer Vision (Neural Networks & Deep Learning is **CSE 4311**); CSE 4303 = Computer Graphics (not NLP); CSE 4342 = Embedded Systems II.
- MATH 2326 is 3 hours; MATH 3318 is not in either plan; CS needs CSE 3380 **or** MATH 3330, SE the same.
- "C or better in all CSE courses" is not the rule. The real rule: professional-program admission (2.5 GPA) and C or better in prerequisites of professional courses.

## Known gaps / assumptions

- **Unconfirmed:** certificate courses double-count toward degree slots (ask cseugadvising@uta.edu).
- Non-CSE prerequisites are not in the catalog PDF; MATH 2425←1426, MATH 2326←2425, PHYS 1444←1443 are *assumed* from the plan order.
- ALEKS placement, honors equivalents, consent-of-instructor and the UVS certificate gate are not modelled (see `prerequisites.json` → `notes`).
- Sample general-core courses come from UTA's 2025-26 general core list.
- `catalog_sequences.json` holds the catalog's verbatim 4-year plans for the *plain* degrees (test fixtures for the planner; not loaded into SQLite).
