# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Evidence pipeline: source manifests with stable IDs/revisions/hashes,
  Agora/Disclosure adapters, `as_of` time-travel queries, conflict detection,
  exportable evidence packs
- Retrieval: `bge-reranker-v2-m3` reranking stage, Korean golden-set retrieval
  evaluation in CI
- Optional API tokens for proxied deployments; local MCP surface

---

## [2.0.0] - 2026-07-14

Repositioned as **Mossland Local-first Knowledge & Evidence Node** — a
read-only indexer of official, versioned documents that produces answers with
verifiable sources. Public general-purpose Q&A remains with
[Alpha](https://github.com/MosslandOpenDevs/alpha); governance records remain
with [Agora](https://github.com/MosslandOpenDevs/Agora).

### Security (P0)
- API now binds to `127.0.0.1` by default (was `0.0.0.0`)
- Qdrant docker-compose binds to `127.0.0.1` only; unused gRPC port (6334)
  no longer published; image pinned to `qdrant/qdrant:v1.18.2`
- `data/` is git-ignored by default so internal documents cannot be committed
  by accident (samples moved to `fixtures/`)
- CORS restricted to local origins (was `*`)
- Global concurrency limit + queue/query timeouts on all query paths
- Question text and usernames are no longer logged (request ID, latency, and
  source counts only)
- Internal exception strings are no longer returned to users
- Discord: slash commands only (`/ask`, `/search`, `/status`, `/ping`) — the
  privileged `message_content` intent is no longer required; guild/channel
  allowlists and per-user cooldowns added
- Web UI no longer loads Google Fonts (no third-party requests)

### Changed
- **LangChain removed.** The RAG core now uses the official `ollama` client,
  `qdrant-client`, and `FlagEmbedding` directly — fixes the broken clean
  install caused by LangChain v1 module moves
- **Hybrid retrieval**: BGE-M3 dense + sparse vectors fused with Reciprocal
  Rank Fusion; minimum dense-similarity threshold discards weak evidence and
  returns "not found" instead of guessing
- **Atomic reindexing**: ingestion writes to a staging collection, verifies
  point counts, then swaps a Qdrant alias atomically; the previous collection
  is kept for rollback. A failed ingest can no longer destroy the working
  index
- **Fail-closed ingestion**: unreadable files abort the reindex by default
  (`--allow-partial` to override)
- **Backend-assembled citations**: sources come from retrieval metadata
  (filename, page, sha256 content hash, score) instead of asking the LLM to
  emit `[Source: ...]` strings
- Default LLM documentation aligned to `qwen3.5:9b` (6.6GB) with
  `qwen3.5:27b` as the high-quality profile (was `llama3.3:70b` / 64GB-class
  hardware guidance)
- Device auto-selection: CUDA → MPS → CPU (was hard-coded MPS)
- Packaging: `pyproject.toml` + `uv.lock`; `requirements.txt` is now an
  exported pin set; Linux installs CPU PyTorch wheels by default
- Centralized logging setup — `--log-level` is no longer overridden by
  module-level configuration

### Fixed
- Corrected corpus data: the sample document presented the deprecated 2018
  MOC ERC-20 address as current. Samples now record the 2025 ERC-20 address
  (`0x8bbf...0dab`) as current and the 2018 address as deprecated, verified
  against [MossCoin-ERC20-2025](https://github.com/mossland/MossCoin-ERC20-2025);
  unsourced token-distribution/roadmap/partnership claims removed
- Health checks now verify Qdrant, Ollama, model availability, and index
  point counts (previously reported "healthy" whenever the RAG object existed)
- Web UI source modal opened the wrong (or no) sources from the second answer
  onward — sources are now bound directly to each message element
- Discord messages: single paragraphs/lines longer than 2,000 characters are
  now split correctly
- DOCX ingestion implemented (was documented but not implemented)
- RAG errors now propagate as errors instead of being returned as answer
  objects

### Added
- `fixtures/official/moc_token_addresses.md` — verified current/legacy MOC
  contract record with `canonical_url` / `as_of` / `fetched_at` frontmatter
- `fixtures/synthetic/` — clearly-marked demo fixtures (excluded from the
  default index)
- Chunk metadata: sha256 content hash, file hash, ingestion timestamp, page
  numbers (groundwork for the evidence pipeline)
- Unit tests (splitter, loaders, ingest atomicity, RRF, API error handling,
  Discord splitting) and GitHub Actions CI (ruff + pytest)

### Removed
- `langchain`, `langchain-community`, `langchain-huggingface`,
  `sentence-transformers` (superseded by FlagEmbedding), `unstructured`
  dependencies
- Prefix commands (`!ask` 등) — replaced by slash commands

### Upgrade notes
- Run `uv sync` (or `pip install -r requirements.txt` in a fresh venv)
- Re-index once: `python main.py ingest`. The legacy `moss_knowledge`
  collection is replaced by an alias pointing at versioned collections
- Discord: re-invite scope needs `applications.commands`; the
  `MESSAGE CONTENT` privileged intent can be disabled in the developer portal

---

## [1.0.0] - 2025-01-07

### Added
- Initial release of Moss Nexus
- **Core RAG Pipeline**
  - Document ingestion for PDF, Markdown, and TXT files
  - Text chunking with RecursiveCharacterTextSplitter (800 chars, 100 overlap)
  - Vector embeddings using BAAI/bge-m3 with MPS acceleration
  - Qdrant vector database integration
- **Web UI**
  - Modern chat interface with responsive design
  - Real-time typing indicator and loading animation
  - Source document modal for reference checking
  - Processing time display
  - Mobile-friendly layout
- **REST API (FastAPI)**
  - `POST /api/query` - Question answering with sources
  - `POST /api/search` - Document search only
  - `GET /api/health` - System health check
  - Swagger documentation at `/docs`
  - CORS support for cross-origin requests
- **Discord Bot Interface**
  - `!ask` command for Q&A with source citations
  - `!search` command for document search only
  - `!status` command for system health check
  - `!ping` command for latency check
  - Typing indicator during response generation
  - Long message pagination support
- **LLM Integration**
  - Ollama integration with llama3.3:70b model
  - Korean language optimized system prompt
  - Hallucination prevention through strict context adherence
- **Configuration Management**
  - Pydantic-based settings with .env support
  - Configurable chunk size, overlap, and top-k retrieval
- **CLI Interface**
  - `python main.py api` - Run Web UI & API server
  - `python main.py bot` - Run Discord bot
  - `python main.py ingest` - Index documents
  - `python main.py test` - Interactive CLI mode
  - `python main.py config` - Show configuration
- **Documentation**
  - README with English and Korean sections
  - Architecture documentation
  - Contributing guidelines

### Technical Details
- Python 3.11+ support
- Apple Silicon (MPS) optimization
- Docker Compose for Qdrant deployment
- Loguru for structured logging

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| 2.0.0 | 2026-07-14 | Evidence-node repositioning, LangChain removal, hybrid retrieval, atomic reindexing, security hardening, tests + CI |
| 1.0.0 | 2025-01-07 | Initial release with RAG pipeline, Web UI, REST API, Discord bot |

---

## Upgrade Guide

### From 0.x to 1.0.0

This is the initial release. No migration needed.

### Future Upgrades

When upgrading between versions:

1. **Backup your data**
   ```bash
   cp -r data/ data_backup/
   ```

2. **Update dependencies**
   ```bash
   pip install -r requirements.txt --upgrade
   ```

3. **Re-index documents** (if schema changes)
   ```bash
   python main.py ingest
   ```

4. **Check .env.example** for new configuration options

---

## Links

- [GitHub Releases](https://github.com/MosslandOpenDevs/mossland-nexus/releases)
- [Issue Tracker](https://github.com/MosslandOpenDevs/mossland-nexus/issues)
