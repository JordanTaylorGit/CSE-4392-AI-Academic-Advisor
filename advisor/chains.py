"""RAG chain + SQL tool chain (Persons C/D).

- answer_semantic: retrieval over Chroma (catalog chunks, degree-req docs,
  policies) grounded answer generation.
- answer_exact: structured lookups against SQLite (prereqs, schedule, student
  record). Prefer deterministic SQL helpers here over letting the LLM write
  SQL — exact queries have known shapes.
"""

from .paths import CHROMA_DIR

COLLECTION = "advisor"


def get_vectorstore():
    """Return the Chroma vectorstore for the configured embeddings backend."""
    from langchain_chroma import Chroma

    from .config import get_embeddings

    return Chroma(
        collection_name=COLLECTION,
        persist_directory=str(CHROMA_DIR),
        embedding_function=get_embeddings(),
    )


def answer_semantic(query: str, student_id: str | None = None, k: int = 5) -> str:
    """Answer a semantic/unstructured query via RAG.

    Retrieve top-k chunks from Chroma (trace the hits via tracing.trace
    'retrieval' with doc ids + scores), then answer with the chat model using
    ONLY retrieved context; say "I don't know" when context is insufficient.

    TODO (Person C): implement. Reuse the retrieval pattern from the course's
    RAG prototype (same embeddings, same chunk format).
    """
    raise NotImplementedError("TODO Person C: implement answer_semantic")


def answer_exact(query: str, student_id: str | None = None) -> str:
    """Answer a conventional/exact-matching query against SQLite.

    Known query shapes: prerequisites for a course, a student's record/GPA-ish
    summary, section times for a course/term, remaining requirements.
    Extract the course id / term with a tiny LLM call or regex, hit db.query,
    format the answer. Log 'tool_call' traces.

    TODO (Person D): implement.
    """
    raise NotImplementedError("TODO Person D: implement answer_exact")
