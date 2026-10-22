-- AI Advisor SQLite schema (CONTRACT — Jordan owns; others read only)
--
-- Structural data: courses, prerequisites, sections (schedule), students,
-- completed/enrolled courses, degree programs + requirement slots, saved plans,
-- chat history.

CREATE TABLE IF NOT EXISTS courses (
    course_id   TEXT PRIMARY KEY,        -- e.g. 'CSE 1310'
    dept        TEXT NOT NULL,           -- 'CSE', 'MATH', ...
    number      TEXT NOT NULL,           -- '1310'
    title       TEXT NOT NULL,
    credits     INTEGER NOT NULL,        -- credit hours
    description TEXT NOT NULL DEFAULT ''
);

-- Prerequisites. Rows sharing (course_id, group_id) form an OR-set:
-- the prereq is satisfied if ANY course in that group is completed.
-- Most courses have one group with several rows meaning "all required" only
-- when group_id is distinct per row; see load logic in planner.py.
CREATE TABLE IF NOT EXISTS prerequisites (
    course_id  TEXT NOT NULL REFERENCES courses(course_id),
    group_id   INTEGER NOT NULL,          -- same group_id = OR alternatives
    prereq_id  TEXT NOT NULL REFERENCES courses(course_id),
    min_grade  TEXT NOT NULL DEFAULT 'C',
    PRIMARY KEY (course_id, group_id, prereq_id)
);

-- Class schedule sections (next 3 terms; fabricated data).
CREATE TABLE IF NOT EXISTS sections (
    section_id  TEXT PRIMARY KEY,         -- e.g. 'CSE 3310-001-F2026'
    course_id   TEXT NOT NULL REFERENCES courses(course_id),
    term        TEXT NOT NULL,            -- 'F2026', 'S2027', 'SU2027'
    days        TEXT NOT NULL,            -- 'MWF', 'TR', 'M', ...
    start_time  TEXT NOT NULL,            -- '09:00' 24h
    end_time    TEXT NOT NULL,            -- '09:50'
    instructor  TEXT NOT NULL DEFAULT '',
    capacity    INTEGER NOT NULL DEFAULT 40
);

CREATE TABLE IF NOT EXISTS degree_programs (
    program_id  TEXT PRIMARY KEY,         -- 'bs_cs_cyber', 'bs_se_ai'
    name        TEXT NOT NULL,
    total_credits INTEGER NOT NULL        -- degree total (e.g. 120)
);

-- Requirement slots: a program is a set of slots. For fixed slots course_id
-- names the exact course; for elective slots course_id IS NULL and `options`
-- lists allowed course_ids (JSON array) or a category tag.
CREATE TABLE IF NOT EXISTS requirement_slots (
    slot_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL REFERENCES degree_programs(program_id),
    category   TEXT NOT NULL,             -- 'core', 'math_science', 'cse_core',
                                          -- 'concentration', 'elective'
    course_id  TEXT REFERENCES courses(course_id),   -- NULL => elective slot
    options    TEXT NOT NULL DEFAULT '[]',           -- JSON array of course_ids
    credits    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    student_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    program_id   TEXT NOT NULL REFERENCES degree_programs(program_id),
    start_term   TEXT NOT NULL,           -- e.g. 'F2024'
    max_credits_per_semester INTEGER NOT NULL DEFAULT 18
);

CREATE TABLE IF NOT EXISTS completed_courses (
    student_id TEXT NOT NULL REFERENCES students(student_id),
    course_id  TEXT NOT NULL REFERENCES courses(course_id),
    term       TEXT NOT NULL,
    grade      TEXT NOT NULL,
    PRIMARY KEY (student_id, course_id)
);

CREATE TABLE IF NOT EXISTS enrollments (          -- current-term enrollment
    student_id TEXT NOT NULL REFERENCES students(student_id),
    section_id TEXT NOT NULL REFERENCES sections(section_id),
    PRIMARY KEY (student_id, section_id)
);

-- Saved/generated degree plans.
CREATE TABLE IF NOT EXISTS plans (
    plan_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    program_id TEXT NOT NULL REFERENCES degree_programs(program_id),
    label      TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plan_semesters (
    plan_id   INTEGER NOT NULL REFERENCES plans(plan_id),
    term      TEXT NOT NULL,              -- 'F2026', 'S2027', 'SU2027', ...
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    PRIMARY KEY (plan_id, term, course_id)
);

-- Persisted advising/chat history (also embedded into Chroma).
CREATE TABLE IF NOT EXISTS chat_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    role       TEXT NOT NULL,             -- 'user' | 'assistant'
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================================
-- ADDITIVE tables (added 2026-10-21, Jordan). Nothing above was changed, so existing
-- code and an existing advisor.db keep working; these are created by IF NOT EXISTS.
-- ============================================================================

-- Courses whose prerequisite text requires "Admitted into an Engineering Professional Program".
-- A student must be admitted before taking these (catalog: 2.5 GPA overall / in required
-- science-math-engineering courses / in required CSE courses; <= 4 unsuccessful engineering attempts).
CREATE TABLE IF NOT EXISTS professional_courses (
    course_id TEXT PRIMARY KEY REFERENCES courses(course_id)
);

-- (course_id, prereq_id) pairs from `prerequisites` that may be taken in the SAME term
-- ("or concurrent enrollment" / co-requisite). Verifier rule: a prereq row is satisfied by a
-- completed course with grade >= min_grade, OR -- if listed here -- by a course planned in the same term.
CREATE TABLE IF NOT EXISTS prereq_concurrent (
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    prereq_id TEXT NOT NULL REFERENCES courses(course_id),
    PRIMARY KEY (course_id, prereq_id)
);