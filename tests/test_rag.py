"""Offline tests for Miguel's RAG ingestion and semantic-answering modules.

No Ollama server or OpenAI API key is required: external services are mocked.
"""

from collections import Counter
from types import SimpleNamespace

from advisor import chains, ingest, tracing


def test_build_documents_has_all_sources_and_stable_ids():
    docs = ingest.build_documents()
    assert len(docs) == 154
    assert len({doc["id"] for doc in docs}) == len(docs)
    assert Counter(d["metadata"]["source"] for d in docs) == {
        "catalog_pdf": 77,
        "course_description": 75,
        "degree_requirements": 2,
    }
    assert any("CSE 4308" in d["text"] for d in docs)
    assert any(d["id"] == "degree_req:bs_cs_cybersecurity" for d in docs)


def test_ingest_batches_and_reuses_ids(monkeypatch):
    stored = {}
    calls = []

    class FakeChroma:
        def add_texts(self, texts, metadatas, ids):
            calls.append(len(ids))
            for identifier, item, metadata in zip(ids, texts, metadatas):
                stored[identifier] = (item, metadata)

    monkeypatch.setattr(chains, "get_vectorstore", lambda: FakeChroma())
    monkeypatch.setattr(tracing, "trace", lambda *args, **kwargs: None)
    assert ingest.ingest(batch_size=30) == 154
    assert calls == [30, 30, 30, 30, 30, 4]
    assert len(stored) == 154
    ingest.ingest(batch_size=60)
    assert len(stored) == 154  # repeated runs don't create new IDs


def test_search_documents_returns_grounded_hits(monkeypatch):
    events = []
    monkeypatch.setattr(tracing, "trace", lambda *args, **kwargs: events.append((args, kwargs)))

    class FakeChroma:
        def similarity_search_with_score(self, query, k):
            assert query == "machine learning"
            assert k == 2
            return [(SimpleNamespace(
                page_content="CSE 4309 covers machine learning",
                metadata={"document_id": "catalog:CSE-4309", "source": "catalog_pdf",
                          "course_id": "CSE 4309", "source_file": "cse_undergrad_courses.pdf"},
            ), 0.45)]

    monkeypatch.setattr(chains, "get_vectorstore", lambda: FakeChroma())
    matches = chains.search_documents("machine learning", k=2)
    assert len(matches) == 1
    assert matches[0]["id"] == "catalog:CSE-4309"
    assert matches[0]["score"] == 0.45
    assert events[0][0] == ("retrieval",)


def test_answer_semantic_uses_sources_and_cites(monkeypatch):
    from advisor import config

    prompts = []

    class FakeModel:
        def invoke(self, messages):
            prompts.extend(messages)
            return SimpleNamespace(content="CSE 4309 covers machine learning [Source 1].")

    monkeypatch.setattr(config, "get_chat_model", lambda **kwargs: FakeModel())
    monkeypatch.setattr(chains, "search_documents", lambda query, k: [{
        "id": "catalog:CSE-4309", "text": "CSE 4309 covers machine learning",
        "source": "catalog_pdf", "course_id": "CSE 4309", "score": 0.1,
    }])
    monkeypatch.setattr(tracing, "trace", lambda *args, **kwargs: None)
    result = chains.answer_semantic("Which courses cover machine learning?", "s1")
    assert "CSE 4309 covers machine learning" in result
    assert "Retrieved sources: CSE 4309" in result
    assert prompts[0][0] == "system"
    assert "Use ONLY" in prompts[0][1]
    assert "catalog:CSE-4309" in prompts[1][1]


def test_answer_semantic_without_hits(monkeypatch):
    monkeypatch.setattr(chains, "search_documents", lambda query, k: [])
    result = chains.answer_semantic("Any question")
    assert "python -m advisor.ingest" in result
