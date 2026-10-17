"""Chroma ingest pipeline (Person C).

Embeds the nonstructural data into .chroma/:
  - course catalog chunks   <- seed/catalog/cse_undergrad_courses.pdf
  - course descriptions     <- seed/catalog/course-desc.jsonl
  - degree requirement docs <- seed/degree_reqs/*.md

Run:  uv run python -m advisor.ingest

The catalog chunker below is ported from the course RAG prototype
(RAG/app.py — same ENTRY_RE splitting strategy).
"""

import re
from pathlib import Path

from pypdf import PdfReader

from .chains import COLLECTION, get_vectorstore
from .paths import CATALOG_PDF, COURSE_DESC_JSONL, DEGREE_REQS_DIR

# A real catalog entry looks like: "CSE 1325. OBJECT-ORIENTED PROGRAMMING. 3 Hours."
# Bare "CSE NNNN." fragments are prerequisite mentions, not new entries.
ENTRY_RE = re.compile(r"^CSE (\d{4})\.\s*\S.*?\b\d+ Hours?\.", re.S)


def load_course_chunks(pdf_path: Path = CATALOG_PDF) -> list[dict]:
    """Split the catalog PDF into one chunk per course entry.
    Returns [{'id': 'CSE 1325', 'text': '...'}]."""
    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    chunks, seen = [], set()
    for part in re.split(r"(?=\bCSE \d{4}\.)", text):
        part = re.sub(r"\s+", " ", part).strip()
        if not part:
            continue
        m = ENTRY_RE.match(part)
        if m:
            key = (m.group(1), part)
            if key not in seen:
                seen.add(key)
                chunks.append({"id": f"CSE {m.group(1)}", "text": part})
        elif chunks:
            chunks[-1]["text"] += " " + part
    return chunks


def load_degree_req_docs(dir_path: Path = DEGREE_REQS_DIR) -> list[dict]:
    """One document per degree-requirements .md file (section-split if large)."""
    docs = []
    for p in sorted(dir_path.glob("*.md")):
        docs.append({"id": f"degree_req:{p.stem}", "text": p.read_text(encoding="utf-8")})
    return docs


def ingest() -> None:
    """Embed everything into the Chroma collection.

    TODO (Person C): upsert all chunks + docs into get_vectorstore()
    (ids=doc['id'], documents=doc['text'], metadatas={'source': ...}).
    Also embed course-desc.jsonl rows, and (optionally, spec req 7) upsert
    summarized advising/chat history.
    """
    raise NotImplementedError("TODO Person C: implement ingest")


if __name__ == "__main__":
    ingest()
