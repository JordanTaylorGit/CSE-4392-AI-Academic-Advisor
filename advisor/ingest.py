"""Load course/degree documents and upsert their embeddings into Chroma.

  The document IDs are stable, so re-running
``python -m advisor.ingest`` updates existing records rather than duplicating
those documents. Embeddings come from advisor.config (Ollama or OpenAI).
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from .paths import CATALOG_PDF, COURSE_DESC_JSONL, DEGREE_REQS_DIR

# A real entry begins "CSE 1325. OBJECT-ORIENTED PROGRAMMING. 3 Hours."
# Mere prerequisite mentions ("CSE 1325.") are not new course entries.
ENTRY_RE = re.compile(r"^CSE (\d{4})\.\s*\S.*?\b\d+ Hours?\.", re.S)


def load_course_chunks(pdf_path: Path = CATALOG_PDF) -> list[dict]:
    """Return [{'id': 'CSE 1325', 'text': 'full course entry'}] from PDF."""
    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    chunks: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for part in re.split(r"(?=\bCSE \d{4}\.)", text):
        part = re.sub(r"\s+", " ", part).strip()
        if not part:
            continue
        match = ENTRY_RE.match(part)
        if match:
            key = (match.group(1), part)
            if key not in seen:
                seen.add(key)
                chunks.append({"id": f"CSE {match.group(1)}", "text": part})
        elif chunks:
            # This is a continuation/prerequisite mention within the prior entry.
            chunks[-1]["text"] += " " + part
    return chunks


def load_degree_req_docs(dir_path: Path = DEGREE_REQS_DIR) -> list[dict]:
    """Load the team-authored program documents for semantic search."""
    return [
        {"id": f"degree_req:{path.stem}", "text": path.read_text(encoding="utf-8")}
        for path in sorted(dir_path.glob("*.md"))
    ]


def build_documents() -> list[dict]:
    """Prepare Chroma records without calling an embedding API.

    Each item has a stable ``id``, searchable ``text``, and ``metadata``.
    Separate catalog and description records make both prerequisite clauses
    and keyword/topic queries easy to retrieve.
    """
    records: list[dict] = []
    for chunk in load_course_chunks():
        course_id = chunk["id"]
        records.append({
            "id": f"catalog:{course_id.replace(' ', '-')}",
            "text": chunk["text"],
            "metadata": {
                "document_id": f"catalog:{course_id.replace(' ', '-')}",
                "source": "catalog_pdf",
                "source_file": CATALOG_PDF.name,
                "course_id": course_id,
            },
        })

    with COURSE_DESC_JSONL.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            number = str(raw["id"]).strip()
            course_id = f"CSE {number}"
            title = str(raw["title"]).strip()
            description = str(raw["description"]).strip()
            doc_id = f"description:CSE-{number}"
            records.append({
                "id": doc_id,
                "text": f"{course_id}: {title}\nDescription: {description}",
                "metadata": {
                    "document_id": doc_id,
                    "source": "course_description",
                    "source_file": COURSE_DESC_JSONL.name,
                    "course_id": course_id,
                    "title": title,
                },
            })

    for doc in load_degree_req_docs():
        records.append({
            "id": doc["id"],
            "text": doc["text"],
            "metadata": {
                "document_id": doc["id"],
                "source": "degree_requirements",
                "source_file": f"{doc['id'].split(':', 1)[1]}.md",
            },
        })

    if not records:
        raise ValueError("No course catalog, descriptions, or degree requirements found")
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate document IDs detected in input corpus")
    return records


def ingest(batch_size: int = 20) -> int:
    """Upsert all documents into Chroma using the configured embeddings.

    Returns the number of indexed records. Ollama users must start Ollama and
    download the embedding model before running this function.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    # Late import keeps document preparation / --dry-run independent of Ollama.
    from .chains import get_vectorstore
    from .tracing import trace

    records = build_documents()
    store = get_vectorstore()

    # Renamed or removed degree .md files otherwise linger in persistent Chroma.
    # Prune *only* degree requirement entries; leave course and other data alone.
    valid_degree_ids = {
        record["id"] for record in records
        if record["metadata"]["source"] == "degree_requirements"
    }
    existing_degree_ids = set(store.get(
        where={"source": "degree_requirements"}, include=[]
    )["ids"])
    stale_degree_ids = sorted(existing_degree_ids - valid_degree_ids)
    if stale_degree_ids:
        store.delete(ids=stale_degree_ids)
        print(f"Removed {len(stale_degree_ids)} outdated degree documents from Chroma")

    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        # LangChain Chroma's add_texts uses an upsert for existing IDs.
        store.add_texts(
            texts=[doc["text"] for doc in batch],
            metadatas=[doc["metadata"] for doc in batch],
            ids=[doc["id"] for doc in batch],
        )
        print(f"Indexed {min(start + len(batch), len(records))}/{len(records)} documents")
    trace("ingestion", documents=len(records), sources=dict(Counter(
        record["metadata"]["source"] for record in records
    )))
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the AI Advisor Chroma RAG index")
    parser.add_argument("--dry-run", action="store_true", help="inspect records, don't call embeddings")
    parser.add_argument("--batch-size", type=int, default=20, help="embedding batch size (default 20)")
    args = parser.parse_args()
    if args.dry_run:
        records = build_documents()
        print(f"Prepared {len(records)} documents (no embeddings called):")
        for source, count in sorted(Counter(r["metadata"]["source"] for r in records).items()):
            print(f"  {source}: {count}")
    else:
        print(f"Finished indexing {ingest(args.batch_size)} documents into Chroma.")


if __name__ == "__main__":
    main()
