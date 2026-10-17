"""Repo-relative filesystem paths. Shared by all modules."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = Path(__file__).resolve().parent / "seed"
CATALOG_PDF = SEED_DIR / "catalog" / "cse_undergrad_courses.pdf"
COURSE_DESC_JSONL = SEED_DIR / "catalog" / "course-desc.jsonl"
DEGREE_REQS_DIR = SEED_DIR / "degree_reqs"
STUDENTS_JSON = SEED_DIR / "students.json"
SCHEDULE_JSON = SEED_DIR / "schedule.json"
SCHEMA_SQL = SEED_DIR / "schema.sql"

DB_PATH = REPO_ROOT / "advisor.db"
CHROMA_DIR = REPO_ROOT / ".chroma"
LOGS_DIR = REPO_ROOT / "logs"
TRACE_LOG = LOGS_DIR / "traces.jsonl"
