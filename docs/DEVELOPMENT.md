# Development Guide

Everything you need to develop and extend Moss Nexus.

## Environment Setup

### Prerequisites

| Tool | Version | Installation |
|------|---------|--------------|
| Python | 3.11+ | `brew install python@3.12` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | latest | [Docker Desktop](https://docker.com/products/docker-desktop) |
| Ollama | latest | `brew install ollama` |

### Setup

```bash
git clone https://github.com/MosslandOpenDevs/mossland-nexus.git
cd mossland-nexus

# Install runtime + dev dependencies from the lockfile
uv sync --all-groups

# Configure
cp .env.example .env

# Start services
docker-compose up -d          # Qdrant (127.0.0.1:6333)
ollama pull qwen3.5:4b        # small model for faster dev iteration

# Verify
uv run python main.py config
```

For development, set a smaller model in `.env`:

```env
OLLAMA_MODEL=qwen3.5:4b
LOG_LEVEL=DEBUG
```

> pip fallback: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
> (`requirements.txt` is exported from `uv.lock` — edit `pyproject.toml`, then
> `uv lock && uv export --no-dev --no-hashes --no-annotate -o requirements.txt`.)

## Project Structure

```
mossland-nexus/
├── main.py                # CLI entry point (logging is configured here)
├── pyproject.toml         # dependencies + ruff/pytest config
├── uv.lock                # pinned resolution (commit this)
├── requirements.txt       # exported pins for pip users
├── docker-compose.yml     # Qdrant v1.18.2, loopback-bound
├── data/                  # your corpus (git-ignored)
├── fixtures/              # sample corpora: official/ & synthetic/
├── static/                # Web UI (self-contained, no CDN assets)
├── tests/                 # pytest suite (no model downloads needed)
├── .github/workflows/     # CI: ruff + pytest
└── src/
    ├── config.py          # Pydantic settings
    ├── logging_setup.py   # central logging
    ├── loaders.py         # PDF/MD/TXT/DOCX loaders
    ├── splitter.py        # text chunking
    ├── embeddings.py      # BGE-M3 (lazy import of FlagEmbedding)
    ├── ingest.py          # staging → verify → alias swap
    ├── rag_chain.py       # hybrid retrieval + generation + health
    ├── api.py             # FastAPI server
    └── bot.py             # Discord slash commands
```

## Running Locally

```bash
uv run python main.py test                    # interactive CLI Q&A
uv run python main.py api --log-level DEBUG   # Web UI at 127.0.0.1:8000
uv run python main.py bot                     # Discord bot
uv run python main.py ingest                  # index data/ (fail-closed)
uv run python main.py ingest --allow-partial  # tolerate broken files
```

## Testing

```bash
uv run pytest            # full suite (fast — heavy models are mocked/injected)
uv run pytest -v tests/test_ingest.py
uv run ruff check .      # lint (CI-enforced)
```

Design notes for testability:

- `DocumentIngester` and `RAGChain` accept injected `embedder`, `client`, and
  `llm` instances — tests pass fakes/mocks, so **no test downloads a model or
  needs a running Qdrant/Ollama**.
- `FlagEmbedding`/`torch` are imported lazily inside `BGEM3Embedder`, keeping
  test imports light.
- The FastAPI `TestClient` is used without the lifespan context, so tests
  control the `rag_chain` global directly.

Example — testing with a fake embedder:

```python
class FakeEmbedder:
    def encode(self, texts):
        from src.embeddings import EmbeddingBatch
        return EmbeddingBatch(
            dense=[[0.1, 0.2, 0.3] for _ in texts],
            sparse=[{1: 0.5} for _ in texts],
        )

ingester = DocumentIngester(embedder=FakeEmbedder(), client=mock_qdrant)
```

## Debugging

### Qdrant inspection

```bash
curl http://127.0.0.1:6333/collections                    # list collections
curl http://127.0.0.1:6333/aliases                        # alias → collection
curl http://127.0.0.1:6333/collections/moss_knowledge     # via alias
```

### Ollama

```bash
ollama list
curl http://localhost:11434/api/version
```

### Health endpoint

```bash
curl http://127.0.0.1:8000/api/health | python3 -m json.tool
# reports qdrant / ollama / model_available / collection_points individually
```

## Common Tasks

### Adding a new document format

Add a loader function in `src/loaders.py` and register it:

```python
def _load_csv(path: Path) -> list[tuple[str, int | None]]:
    ...
    return [(text, None)]

_LOADERS[".csv"] = _load_csv
SUPPORTED_EXTENSIONS = (*SUPPORTED_EXTENSIONS, ".csv")
```

Loader failures are collected per file — never swallow exceptions inside a
loader; let `load_documents` record them so fail-closed ingestion works.

### Adding a slash command

```python
# src/bot.py
@client.tree.command(name="mycmd", description="설명")
async def my_command(interaction: discord.Interaction):
    await interaction.response.send_message("...")
```

Commands sync automatically on startup (guild-scoped if
`DISCORD_GUILD_IDS` is set — instant; global otherwise — up to 1h).

### Adding an API endpoint

Follow the existing pattern in `src/api.py`: use `_run_limited()` for
anything that touches the RAG core, log with a request ID (never the question
text), and return generic error strings.

### Changing retrieval behavior

Tuning knobs in `.env`: `TOP_K_RESULTS`, `RETRIEVAL_CANDIDATES`,
`MIN_DENSE_SCORE`, `CHUNK_SIZE`, `CHUNK_OVERLAP`. The RRF fusion and
threshold logic live in `src/rag_chain.py::RAGChain.search`.

## Troubleshooting

**`ModuleNotFoundError: No module named 'src'`** — run from the project root
(or `uv run python main.py ...`, which handles it).

**MPS not available** — `uv run python -c "import torch; print(torch.backends.mps.is_available())"`;
fall back with `EMBEDDING_DEVICE=cpu`.

**Qdrant connection refused** — `docker-compose ps`, then `docker-compose up -d`;
note it listens on `127.0.0.1` only.

**Slash commands not appearing** — with `DISCORD_GUILD_IDS` set they appear
instantly in those guilds; global registration can take up to an hour. The
bot invite needs the `applications.commands` scope.

**Slow embedding on CPU** — lower `EMBEDDING_BATCH_SIZE`, or use a CUDA/MPS
machine for large corpora.

## Resources

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [FlagEmbedding (BGE-M3)](https://github.com/FlagOpen/FlagEmbedding)
- [Ollama API Reference](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [uv Documentation](https://docs.astral.sh/uv/)
