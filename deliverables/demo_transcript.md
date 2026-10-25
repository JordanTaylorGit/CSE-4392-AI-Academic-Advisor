# Demo transcript

Student: **Sam Martinez** (`s_sophomore`, bs_cs_cyber). Session `demo-final`, run Oct 24 2026, 19:54.

| # | Demonstrates | Intent | Time |
|---|---|---|---|
| 1 | Req 2: multi-year degree plan | generate_plan | 0.1 s |
| 2 | Req 3: exact query (SQL) | exact_query | 0.0 s |
| 3 | Req 3: semantic query (RAG) | semantic_query | 41.2 s |
| 4 | Req 4: six verification checks | check_eligibility | 0.0 s |
| 5 | Req 6: conversation state | modify_plan | 0.0 s |
| 6 | Req 5: switch major + comparison | switch_major | 0.0 s |

## 1. Req 2: multi-year degree plan

**Student:** I'm a sophomore CS major interested in cybersecurity. Generate my degree plan.

**Advisor:**

> **Degree plan** — `bs_cs_cyber`
>
> - `F2026` (13 hrs): CSE 1325, CSE 2312, CSE 3318, PHYS 1444
> - `S2027` (15 hrs): MATH 2326, CSE 3320, CSE 3310, COMS 2302, CSE 3330
> - `F2027` (15 hrs): CSE 3314, CSE 4344, CSE 3302, CSE 3315, CSE 4316
> - `S2028` (15 hrs): CSE 4317, CSE 4380, CSE 4381, CSE 4382, MATH 3330
> - `F2028` (15 hrs): IE 3301, CSE 3311, CSE 4378, CSE 3340, CSE 4303
> - `S2029` (15 hrs): ECON 2305, ENGL 1375, HIST 1302, POLS 2311, POLS 2312
>
> **Total planned:** 88 hrs
>
> ⚠️ [projection] Terms after SU2027 assume catalog offering patterns (1000/2000-level every term; 3000+ Fall/Spring); meeting times are not published.
>
> ⚠️ [requirements] Unfilled slot 41: no approved courses loaded. Check prerequisites, offerings, and credit caps.
>
> ⚠️ Planning window ends at S2033 (projected past SU2027); requirements remain unfilled.

## 2. Req 3: exact query (SQL)

**Student:** What are the prerequisites for CSE 3310?

**Advisor:**

> **Prerequisites for CSE 3310 — FUNDAMENTALS OF SOFTWARE ENGINEERING:**
>
> - CSE 1320 (min grade C)
> - CSE 1325 (min grade C)
> - CSE 2315 (min grade C)

## 3. Req 3: semantic query (RAG)

**Student:** Which courses cover machine learning or AI topics?

**Advisor:**

> The courses that cover machine learning or AI topics are CSE 4308 (Artificial Intelligence), CSE 4309 (Fundamentals of Machine Learning), and CSE 4311 (Neural Networks and Deep Learning).

## 4. Req 4: six verification checks

**Student:** Can I take CSE 4344 in S2027?

**Advisor:**

> **Eligibility check: CSE 4344 in S2027**
>
> ❌ prerequisites_met — Missing: prereq: CSE 3320 (grade C+)
> ❌ not_already_passed — Already passed or planned in another term.
> ✅ fulfills_degree_requirement — Fills an unfilled degree requirement.
> ❌ no_schedule_conflict — No conflict-free offered section combination in S2027; missing offerings also fail this check.
> ❌ within_semester_credit_cap — 18/15 semester credits.
> ✅ within_degree_credit_cap — 120/123 degree credits (applicable completed + planned/enrolled).

## 5. Req 6: conversation state

**Student:** What about taking only 3 classes next semester instead?

**Advisor:**

> **Degree plan** — `bs_cs_cyber`
>
> - `F2026` (13 hrs): CSE 1325, CSE 2312, CSE 3318, PHYS 1444
> - `S2027` (9 hrs): MATH 2326, CSE 3320, CSE 3310
> - `F2027` (9 hrs): COMS 2302, CSE 3330, CSE 4344
> - `S2028` (9 hrs): CSE 3314, CSE 3302, CSE 3315
> - `F2028` (9 hrs): CSE 4316, CSE 4380, CSE 4381
> - `S2029` (9 hrs): CSE 4317, CSE 4382, MATH 3330
> - `F2029` (9 hrs): IE 3301, CSE 3311, CSE 4378
> - `S2030` (9 hrs): CSE 3313, CSE 3340, ECON 2305
> - `F2030` (9 hrs): ENGL 1375, HIST 1302, POLS 2311
> - `S2031` (3 hrs): POLS 2312
>
> **Total planned:** 88 hrs
>
> ⚠️ [projection] Terms after SU2027 assume catalog offering patterns (1000/2000-level every term; 3000+ Fall/Spring); meeting times are not published.
>
> ⚠️ [requirements] Unfilled slot 41: no approved courses loaded. Check prerequisites, offerings, and credit caps.
>
> ⚠️ Planning window ends at S2033 (projected past SU2027); requirements remain unfilled.

## 6. Req 5: switch major + comparison

**Student:** I'm thinking about switching to Software Engineering.

**Advisor:**

> **Degree plan** — `bs_se_ai`
>
> - `F2026` (13 hrs): CSE 1325, CSE 2312, CSE 3318, PHYS 1444
> - `S2027` (15 hrs): MATH 2326, CSE 3320, CSE 3310, COMS 2302, CSE 3330
> - `F2027` (15 hrs): CSE 3314, CSE 3302, CSE 3311, CSE 3315, CSE 4316
> - `S2028` (15 hrs): CSE 4317, CSE 4321, CSE 4322, CSE 4361, CSE 4380
> - `F2028` (13 hrs): MATH 3330, IE 3301, BIOL 1441, ECON 2305
> - `S2029` (15 hrs): CSE 4308, CSE 4309, CSE 4310, CSE 4311, ENGL 1375
> - `F2029` (9 hrs): HIST 1302, POLS 2311, POLS 2312
>
> **Total planned:** 95 hrs
>
> ⚠️ [projection] Terms after SU2027 assume catalog offering patterns (1000/2000-level every term; 3000+ Fall/Spring); meeting times are not published.
>
> **Compared to your current plan:**
> - Courses added: 8
> - Courses removed: 6
> - Courses moved: 16
> - Credits delta: +7 hrs
> - Semesters added: -3
>
> Program changes from bs_cs_cyber to bs_se_ai. 8 courses added, 6 removed, 16 moved; -3 semesters and +7 planned credits. Last planned term: F2029. The new plan has 1 warnings; review them before using it.
