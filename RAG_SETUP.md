# Miguel's RAG module — setup, demonstration, and handoff

This work implements three shared integration points **without modifying frozen signatures**:

- `advisor/ingest.py`: split the catalog PDF into course entries, load 75 course descriptions and two degree-requirement Markdown files, and upsert them into persistent Chroma.
- `advisor/chains.py`: Chroma nearest-neighbor retrieval (`search_documents`), then LangChain chat-model answering grounded in retrieved text (`answer_semantic`). The `answer_exact` SQL stub is **Kyle's responsibility** and was deliberately left unchanged.
- `advisor/tools.py`: connect the existing `search_advising_docs(query, k)` tool to the retriever without changing its signature.
- `tests/test_rag.py`: offline unit tests using fake vector stores/models.

## Prepare your branch

From your local clone (not the ZIP download):

```bash
git switch main
git pull origin main
git switch -c feature/rag
```

Copy these modified files into the clone, preserving directories, then:

```bash
git add advisor/ingest.py advisor/chains.py advisor/tools.py tests/test_rag.py RAG_SETUP.md
git commit -m "Implement Chroma ingestion and semantic RAG queries"
git push -u origin feature/rag
```

Open a GitHub pull request from `feature/rag` into `main`. **Coordinate with Kyle before merging `chains.py` and `tools.py`, as these files are shared**, to avoid overwriting any work on his branch.

## Install and run

The project needs Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

Choose exactly one inference and embeddings backend.

**Option A: local Ollama** (default). Have Ollama installed and running, then:

```bash
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

The default `ADVISOR_LLM=ollama` in `.env.example` uses these models. The repo's `config.py` reads environment variables, **but does not load `.env` automatically**. For Ollama you can use defaults without creating `.env`.

**Option B: OpenAI**. Set environment variables in your shell, such as PowerShell:

```powershell
$env:ADVISOR_LLM="openai"
$env:OPENAI_API_KEY="YOUR_KEY_HERE"
```

Do not commit your key or `.env` to GitHub. Models may incur API charges.

Then run:

```bash
uv run python -m advisor.ingest --dry-run
uv run python -m advisor.ingest
uv run pytest -q
```

`--dry-run` reads the local documents and reports the counts without invoking a server. The actual indexing requires Ollama or OpenAI embeddings. Persistent embeddings are placed in `.chroma/` (Git-ignored). **Rebuild `.chroma/` when changing to an embedding model with a different vector dimension.** Repeated indexing with the same backend updates existing IDs.

## Try the RAG component independently

The full CLI invokes `orchestrator.handle_message`, and the team's router remains a placeholder in the provided `main` branch. While Kyle implements routing, run the semantic chain directly:

```bash
uv run python -c "from advisor.chains import answer_semantic; print(answer_semantic('Which courses cover machine learning?'))"
```

Another demo question:

```bash
uv run python -c "from advisor.chains import answer_semantic; print(answer_semantic('What does the example BS CS cybersecurity concentration require?'))"
```

You should see a grounded response and a list of retrieved course/document sources. Retrieval events are also appended to `logs/traces.jsonl` for the assignment deliverable.

## Architecture explanation for your presentation

```text
Course catalog PDF ──> load_course_chunks ──┐
Course descriptions ──> JSONL loader ───────┼──> Embeddings (Ollama/OpenAI)
Degree requirements ──> Markdown loader ───┘           │
                                                       ▼
                                                Chroma vector DB
                                                       │
Student question ──> query embedding ──> top-k retrieval
                                              │
                                     context + question
                                              │
                                         LangChain LLM
                                              │
                                 grounded answer + sources
```

### Presentation sample

"I implemented the Retrieval-Augmented Generation component. It stores embeddings from the course catalog, course descriptions, and degree requirement documents in Chroma. When a student asks a semantic question, the retriever returns the most relevant records, which are supplied as source context to the language model. We log the retrieved IDs and distance scores and include source references to reduce unsupported answers. Eligibility checks must still run through the deterministic course validator, which is a separate component."

**Important limitation:** The two degree requirement Markdown files in the team repository are team-authored example program documents, not verified official UTA degree audits. Also, this RAG module does not validate class schedules, prerequisite completion, or registration eligibility; those are separate team workstreams.
