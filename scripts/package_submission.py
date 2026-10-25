"""Build the submission zip (Person E, deliverable).

    uv run python scripts/package_submission.py
    uv run python scripts/package_submission.py --out ~/Desktop/CSE4392_TA2_AI_Advisor.zip

Contents (spec section 4):
  - source code: every file committed at HEAD (git archive, so nothing local
    or generated slips in: no .venv, advisor.db, .chroma, .env)
  - documents used to generate the embedding vectors: advisor/seed/catalog/,
    advisor/seed/degree_reqs/ (committed, so already in the source)
  - log of execution traces: logs/traces.jsonl (not committed; added here) plus
    deliverables/execution_trace_log.md and demo_transcript.md
  - the presentation: deliverables/AI_Advisor_Presentation.pptx + screenshots
  - SUBMISSION.md at the top: what is where and how to run it

Commit first: uncommitted changes are not packaged (the script warns).
"""

import argparse
import io
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOP = "CSE4392_TA2_AI_Advisor"

REQUIRED = [
    "deliverables/AI_Advisor_Presentation.pptx",
    "deliverables/execution_trace_log.md",
    "advisor/seed/catalog/cse_undergrad_courses.pdf",
    "advisor/seed/degree_reqs",
]

GUIDE = """# CSE 4392 Team Assignment 2: Academic AI Advisor

| What the assignment asks for | Where it is |
|---|---|
| PPT (architecture, code segments, demo screenshots) | `deliverables/AI_Advisor_Presentation.pptx` |
| Demo screenshots | `deliverables/screenshots/` |
| Source code | everything else (`app.py`, `ui/`, `advisor/`, `scripts/`, `tests/`) |
| Log of execution traces | `logs/traces.jsonl` (raw, one JSON object per step) and `deliverables/execution_trace_log.md` (readable, demo session) |
| Documents used to generate the embedding vectors | `advisor/seed/catalog/` (UTA CSE course catalog PDF, course descriptions) and `advisor/seed/degree_reqs/` (degree requirement documents) |

## Run it

Needs [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com) (macOS: `brew install uv ollama`).

```bash
ollama pull qwen3:4b && ollama pull qwen3:0.6b && ollama pull nomic-embed-text
uv sync                               # installs Python 3.13 + dependencies
uv run python -m advisor.db           # builds advisor.db (SQLite) from advisor/seed/
uv run python -m advisor.ingest       # embeds the documents into .chroma/ (Chroma)
uv run streamlit run app.py           # opens http://localhost:8501
```

Pick a student at the top (the demo uses Sam Martinez). `deliverables/DEMO_GUIDE.md`
walks through every feature; `uv run pytest` runs the tests. To use OpenAI instead of
Ollama, copy `.env.example` to `.env` and set `ADVISOR_LLM=openai` and `OPENAI_API_KEY`.
"""


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True,
                          capture_output=True, text=True).stdout


def build(out: Path, trace_log: Path) -> Path:
    if git("status", "--porcelain").strip():
        print("warning: uncommitted changes are NOT included (packaging HEAD)", file=sys.stderr)
    tracked = set(git("ls-files").splitlines())
    missing = [p for p in REQUIRED if not any(t == p or t.startswith(p + "/") for t in tracked)]
    if missing:
        sys.exit(f"missing from HEAD: {', '.join(missing)} (run the demo / slides scripts and commit)")
    if not trace_log.exists():
        sys.exit(f"no trace log at {trace_log}; run scripts/run_demo.py first")

    archive = subprocess.run(["git", "archive", "--format=zip", f"--prefix={TOP}/", "HEAD"],
                             cwd=REPO_ROOT, check=True, capture_output=True).stdout
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as src, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item))
        dst.write(trace_log, f"{TOP}/logs/traces.jsonl")
        dst.writestr(f"{TOP}/SUBMISSION.md", GUIDE)
    commit = git("rev-parse", "--short", "HEAD").strip()
    size = out.stat().st_size / 1e6
    print(f"Wrote {out} ({size:.1f} MB) from commit {commit}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "dist" / f"{TOP}.zip")
    ap.add_argument("--trace-log", type=Path, default=REPO_ROOT / "logs" / "traces.jsonl")
    args = ap.parse_args(argv)
    build(args.out.expanduser(), args.trace_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
