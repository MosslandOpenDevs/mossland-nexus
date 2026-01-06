# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Slack bot integration
- Multi-language document support
- Document update detection (incremental indexing)
- Authentication & rate limiting for API
- Query result caching (Redis)

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

- [GitHub Releases](https://github.com/mossland/mossland-nexus/releases)
- [Issue Tracker](https://github.com/mossland/mossland-nexus/issues)
