-- AI Advisor SQLite schema (CONTRACT — Jordan owns; others read only)
--
-- Structural data: courses, prerequisites, sections (schedule), students,
-- completed/enrolled courses, degree programs + requirement slots, saved plans,
-- chat history.
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- COURSES + PREREQUISITES
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS courses (
    course_id   TEXT PRIMARY KEY,        -- e.g. 'CSE 1310'
    dept        TEXT NOT NULL,           -- 'CSE', 'MATH', ...
    number      TEXT NOT NULL,           -- '1310'
    title       TEXT NOT NULL,
    credits     INTEGER NOT NULL,        -- credit hours
    level       INTEGER,                     -- 1..6 (first digit of number)
    requires_professional  INTEGER NOT NULL DEFAULT 0,  -- prereq text says "admitted into an Engineering Professional Program"
    typically_offered      TEXT,                        -- e.g. 'F,S,Su' (catalog: 1000/2000-level every term incl. summer; 3000+ at least twice a year)
    description TEXT NOT NULL DEFAULT ''
);
-- Updated

-- Prerequisites. Rows sharing (course_id, group_id) form an OR-set:
-- the prereq is satisfied if ANY course in that group is completed.
-- Most courses have one group with several rows meaning "all required" only
-- when group_id is distinct per row; see load logic in planner.py.
CREATE TABLE IF NOT EXISTS prerequisites (
    course_id  TEXT NOT NULL REFERENCES courses(course_id),
    kind       TEXT NOT NULL DEFAULT 'prereq' CHECK (kind IN ('prereq','coreq')),
    group_id   INTEGER NOT NULL,          -- same group_id = OR alternatives
    prereq_id  TEXT NOT NULL REFERENCES courses(course_id),
    min_grade  TEXT NOT NULL DEFAULT 'C',
    PRIMARY KEY (course_id, kind, group_id, prereq_id)
);
-- Updated

-- ---------------------------------------------------------------------------
-- SCHEDULE (fabricated sections, next 3 terms)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sections (
    section_id  TEXT PRIMARY KEY,         -- e.g. 'CSE 3310-001-F2026'
    course_id   TEXT NOT NULL REFERENCES courses(course_id),
    term        TEXT NOT NULL,            -- 'F2026', 'S2027', 'SU2027'
    section_no  TEXT NOT NULL,
    days        TEXT NOT NULL,            -- 'MWF', 'TR', 'M', ...
    start_time  TEXT NOT NULL,            -- '09:00' 24h
    end_time    TEXT NOT NULL,            -- '09:50'
    room        TEXT,
    instructor  TEXT NOT NULL DEFAULT '',
    capacity    INTEGER NOT NULL DEFAULT 40
    modality    TEXT DEFAULT 'in_person'
);
CREATE INDEX IF NOT EXISTS idx_sections_course_term ON sections(course_id, term);
-- Updated

-- ---------------------------------------------------------------------------
-- PROGRAMS (degrees AND certificates) + RULES
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS degree_programs (
    program_id  TEXT PRIMARY KEY,         -- 'bs_cs_cyber', 'bs_se_ai'
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('degree','certificate')),
    catalog_year  TEXT NOT NULL,           -- '2026-2027'
    total_hours INTEGER NOT NULL        -- degree total (e.g. 120)
    -- certificates only. 1 = a course may count toward the certificate AND a degree slot.
    double_counts_with_degree  INTEGER NOT NULL DEFAULT 0,
    source_url                 TEXT,
    summary                    TEXT
);
-- Updated

-- Scalar rules the verifier needs (GPA floors, attempt limits, ...).
CREATE TABLE IF NOT EXISTS program_rules (
    program_id   TEXT NOT NULL REFERENCES programs(program_id),
    rule_key     TEXT NOT NULL,                         -- 'professional_min_gpa', ...
    value_num    REAL,
    description  TEXT,
    PRIMARY KEY (program_id, rule_key)
);
-- Updated

-- ---------------------------------------------------------------------------
-- REQUIREMENT SLOTS  (what a degree/certificate needs)
--   fixed     exactly one course (slot_courses has 1 row)
--   one_of    pick one of the alternates in slot_courses (CSE 3380 OR MATH 3330)
--   choose_n  pick `courses_needed` distinct courses from slot_courses
--   category  fill `hours` from a general-core bucket; slot_courses holds only
--             sample courses when open_list = 1 (full list lives in the catalog)
--   free      any course (open elective)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS requirement_slots (
    slot_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL REFERENCES degree_programs(program_id),
    slot_key   TEXT NOT NULL,             -- 'cse3318' (same key across programs = same requirement)
    category   TEXT NOT NULL,             -- 'core', 'math_science', 'cse_core', 'concentration', 'elective'
    label      TEXT NOT NULL,
    slot_type  TEXT NOT NULL CHECK (slot_type IN ('fixed','one_of','choose_n','category','free')),
    hours      INTEGER NOT NULL,                   -- total credit hours this slot contributes
    courses_needed  INTEGER,                            -- choose_n only
    professional    INTEGER NOT NULL DEFAULT 0,         -- 1 = needs admission to the professional program
    open_list       INTEGER NOT NULL DEFAULT 0,         -- 1 = slot_courses is only a sample
    notes           TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (program_id, slot_key)
);
CREATE INDEX IF NOT EXISTS idx_slots_program ON requirement_slots(program_id);
-- Updated

CREATE TABLE IF NOT EXISTS slot_courses (
    slot_id    TEXT NOT NULL REFERENCES requirement_slots(slot_id),
    course_id  TEXT NOT NULL REFERENCES courses(course_id),
    PRIMARY KEY (slot_id, course_id)
);
CREATE INDEX IF NOT EXISTS idx_slot_courses_course ON slot_courses(course_id);
-- Updated

-- Catalog's recommended 4-year plan = ground truth for testing the planner.
-- One row per line of the printed plan; a slot may appear several times
-- (e.g. 'us_history' is 3 hrs in year 1 and 3 hrs in year 2).
CREATE TABLE IF NOT EXISTS program_sequence (
    program_id  TEXT NOT NULL REFERENCES programs(program_id),
    year        INTEGER NOT NULL,                       -- 1..4
    term        TEXT NOT NULL CHECK (term IN ('Fall','Spring')),
    position    INTEGER NOT NULL,
    slot_id     TEXT NOT NULL REFERENCES requirement_slots(slot_id),
    hours       INTEGER NOT NULL,
    PRIMARY KEY (program_id, year, term, position)
);
-- Updated

-- ---------------------------------------------------------------------------
-- STUDENTS + RECORDS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    student_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    program_id   TEXT NOT NULL REFERENCES degree_programs(program_id),
    start_term   TEXT NOT NULL,           -- e.g. 'F2024'
    max_credits_per_semester INTEGER NOT NULL DEFAULT 18
    professional_admitted  INTEGER NOT NULL DEFAULT 0,
    interests              TEXT,          -- free text: 'cybersecurity, networks'
    notes                  TEXT
);
-- Updated

-- Certificates a student is pursuing (alongside their degree).
CREATE TABLE IF NOT EXISTS student_certificates (
    student_id  TEXT NOT NULL REFERENCES students(student_id),
    program_id  TEXT NOT NULL REFERENCES programs(program_id),
    PRIMARY KEY (student_id, program_id)
);
-- Updated

CREATE TABLE IF NOT EXISTS completed_courses (
    student_id TEXT NOT NULL REFERENCES students(student_id),
    course_id  TEXT NOT NULL REFERENCES courses(course_id),
    term       TEXT NOT NULL,
    grade      TEXT NOT NULL,
    PRIMARY KEY (student_id, course_id)
);
-- Left from scaffolding

CREATE TABLE IF NOT EXISTS enrollments (          -- current-term enrollment
    enrollment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    section_id TEXT NOT NULL REFERENCES sections(section_id),
    term       TEXT NOT NULL,                       -- 'Fall 2026'
    status     TEXT NOT NULL CHECK (status IN ('completed','in_progress','planned')),
    grade      TEXT, 
    UNIQUE (student_id, section_id, term)
);
CREATE INDEX IF NOT EXISTS idx_enroll_student ON enrollments(student_id);
-- Updated

-- ---------------------------------------------------------------------------
-- SAVED PLANS  (DegreePlan.to_dict() JSON from planner.py)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plans (
    plan_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    program_id TEXT NOT NULL REFERENCES degree_programs(program_id),
    name       TEXT,
    parent_plan_id  INTEGER REFERENCES plans(plan_id),  -- set when a plan is derived from another (for compare_plans)
    label      TEXT NOT NULL DEFAULT 'draft', -- check purpose and if need or to remove, leaving in for now
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
    plan_json  TEXT NOT NULL
);
-- Updated

CREATE TABLE IF NOT EXISTS plan_semesters (
    plan_id   INTEGER NOT NULL REFERENCES plans(plan_id),
    term      TEXT NOT NULL,              -- 'F2026', 'S2027', 'SU2027', ...
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    PRIMARY KEY (plan_id, term, course_id)
);
-- Left from scaffold, need to verify is not reused in any of the updated tables above

-- Persisted advising/chat history (also embedded into Chroma).
CREATE TABLE IF NOT EXISTS chat_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    role       TEXT NOT NULL,             -- 'user' | 'assistant'
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
