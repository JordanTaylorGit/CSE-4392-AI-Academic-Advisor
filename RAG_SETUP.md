# RAG Setup

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/download) (default backend)

Run the commands below from the repository's root folder.

## Install dependencies

```bash
uv sync
```

## Start Ollama

Start Ollama if it isn't already running:

```bash
ollama serve
```

Keep that terminal open, and use a second terminal for the remaining commands. If Ollama is already running, there's no need to start another server.

Download the models if needed:

```bash
ollama pull qwen3:4b
ollama pull nomic-embed-text
```

## Index the documents

Check what will be loaded without generating embeddings:

```bash
uv run python -m advisor.ingest --dry-run
```

Index the documents in Chroma:

```bash
uv run python -m advisor.ingest
```

The index includes the course catalog, course descriptions, and degree requirement Markdown files. Chroma data is stored in `.chroma/` locally and should not be committed to GitHub.

## Run tests

```bash
uv run pytest -q
```

## Test a RAG query

```bash
uv run python -c "from advisor.chains import answer_semantic; print(answer_semantic('Which courses cover machine learning?'))"
```

The answer should include relevant course information and retrieved sources.

## Update degree requirements

All `.md` files directly inside `advisor/seed/degree_reqs/` are detected automatically. If these files are added, changed, renamed, or removed, rerun:

```bash
uv run python -m advisor.ingest
```

This updates the degree documents in Chroma and removes entries for degree files that no longer exist.

## Notes

- Default chat model: `qwen3:4b`
- Default embedding model: `nomic-embed-text`
- Ollama must be available for indexing and answering queries; `--dry-run` does not require it.
- Changing to an embedding model with a different vector dimension may require rebuilding `.chroma/`.
