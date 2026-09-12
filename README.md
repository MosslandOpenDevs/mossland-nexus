<p align="center">
  <h1 align="center">Moss Nexus</h1>
  <p align="center">
    <strong>Mossland Local-first Knowledge & Evidence Node</strong><br>
    Read-only indexing of official, versioned Mossland documents — answers with sources, hashes, and timestamps, generated locally
  </p>
</p>

<!-- opendevs-badges:start -->
[![CI](https://github.com/MosslandOpenDevs/mossland-nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/MosslandOpenDevs/mossland-nexus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-64748b?style=flat)](LICENSE)
<!-- opendevs-badges:end -->

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#usage">Usage</a> •
  <a href="#security-defaults">Security</a> •
  <a href="#한국어">한국어</a>
</p>

---

## Overview

**Moss Nexus** is a local-first RAG node that indexes official Mossland documents (disclosures, proposals, records) **read-only** and answers questions with **verifiable citations** — every answer is grounded in retrieved chunks that carry the source file, content hash, and ingestion timestamp.

Nexus is an **indexer, not a publisher**: canonical facts live in their official repositories (e.g. [MossCoin-ERC20-2025](https://github.com/mossland/MossCoin-ERC20-2025), [Agora](https://github.com/MosslandOpenDevs/Agora)); Nexus builds a disposable, derived search index over them.

### How local is it?

Documents, embeddings, vector search, and LLM inference all run on your machine. Be aware of the network touchpoints that remain:

- **First run** downloads the embedding model from Hugging Face (~2.3GB) and the LLM via Ollama.
- **Discord adapter** (optional) talks to the Discord API; Discord's network policies apply to anything sent through it.
- The Web UI loads no external fonts or scripts.
- API and Qdrant bind to `127.0.0.1` by default — nothing is exposed to your LAN unless you change that.

### Where Nexus fits in the Mossland ecosystem

| Service | Role | Relationship to Nexus |
|---------|------|----------------------|
| [Agora](https://github.com/MosslandOpenDevs/Agora) | Binding proposals & voting records, AI governance briefs | System of record — a data *source* for Nexus |
| [Alpha](https://github.com/MosslandOpenDevs/alpha) | Public crypto/macro media RAG + free 12-tool MCP server at [alpha.moss.land](https://alpha.moss.land?utm_source=github&utm_medium=referral&utm_campaign=nexus-readme) | Public general-purpose Q&A lives there, not here |
| Passport | Wallet auth, credentials, participation records | Potential read-only source (privacy scope TBD) |
| Disclosure | Official disclosures & supply announcements | Publisher — Nexus only indexes |
| **Nexus** | **Local audit/evidence node over official records** | This repository |

## Features

- **Local inference**: embeddings (BGE-M3) and LLM (Ollama) run on your machine — Apple Silicon (MPS), NVIDIA (CUDA), or CPU, selected automatically.
- **Hybrid retrieval**: dense (semantic) + sparse (lexical) BGE-M3 vectors fused with Reciprocal Rank Fusion — exact strings like contract addresses are matched lexically, not just semantically.
- **Backend-assembled citations**: sources come from retrieval metadata — filename, page, sha256 content hash, ingestion timestamp, score (exposed via the REST API and Web UI) — the LLM cannot fabricate a citation.
- **Relevance gating**: below-threshold matches are discarded; with no evidence, Nexus says "not found" instead of guessing.
- **Atomic reindexing**: ingestion builds a staging collection, verifies it, then swaps a Qdrant alias — a failed ingest can never destroy the working index. The previous index is kept for rollback.
- **Fail-closed ingestion**: a file that fails to parse aborts the reindex by default (`--allow-partial` to override).
- **Multi-format**: PDF, Markdown, TXT, DOCX.
- **Interfaces**: Web UI, REST API, Discord slash commands (`/ask`, `/search`, `/status`, `/ping`).
- **Safe defaults**: loopback binds, no privileged Discord intents, guild/channel allowlists, per-user cooldowns, concurrency limits, no question text in logs, no internal errors leaked to users.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       User Interfaces                            │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────────┐  │
│  │  Web UI     │    │ Discord Bot  │    │     REST API       │  │
│  │ (Browser)   │    │ /ask /search │    │    (api.py)        │  │
│  └──────┬──────┘    └──────┬───────┘    └─────────┬──────────┘  │
└─────────┼──────────────────┼──────────────────────┼─────────────┘
          └──────────────────┼──────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RAG Core (rag_chain.py)                       │
│  ┌──────────────┐   ┌──────────────────┐   ┌─────────────────┐  │
│  │ BGE-M3 query │──▶│ dense + sparse   │──▶│  Ollama LLM     │  │
│  │ dense+sparse │   │ search → RRF     │   │  (qwen3.5)      │  │
│  └──────────────┘   │ + score gate     │   └─────────────────┘  │
│                     └──────────────────┘   sources assembled    │
│                                            from metadata        │
└────────┬────────────────────┬───────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌──────────────────────┐  ┌────────────────┐
│   BGE-M3        │  │  Qdrant (Docker)     │  │    Ollama      │
│  (FlagEmbedding)│  │  alias ──▶ collection│  │  (local LLM)   │
│  MPS/CUDA/CPU   │  │  (atomic swap)       │  │                │
└─────────────────┘  └──────────▲───────────┘  └────────────────┘
                                │ staging → verify → swap
┌───────────────────────────────┴─────────────────────────────────┐
│              Ingestion (ingest.py) — fail-closed                 │
│   data/ (PDF·MD·TXT·DOCX) → chunks + sha256 + timestamps         │
└──────────────────────────────────────────────────────────────────┘
```

The Qdrant index is always a **derived, disposable artifact** — the source of truth stays in the original documents.

## Hardware Requirements

Runs on Apple Silicon (MPS), Linux/NVIDIA (CUDA), or plain CPU. Requirements depend on the LLM you pick:

| Profile | Ollama model | Download | Suggested RAM |
|---------|-------------|----------|---------------|
| Default | `qwen3.5:9b` | 6.6GB | 16GB+ |
| Higher quality | `qwen3.5:27b` | 17GB | 32GB+ |
| Low-resource dev | `qwen3.5:4b` | 3.4GB | 8GB+ |

Plus a ~2.3GB download for the BGE-M3 embedding model, and headroom for Qdrant (small corpora: a few hundred MB).

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) — or pip
- Docker (for Qdrant)
- [Ollama](https://ollama.com)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/MosslandOpenDevs/mossland-nexus.git
cd mossland-nexus

# 2. Install dependencies (locked versions)
uv sync
#    …or with pip:  python3 -m venv venv && source venv/bin/activate
#                   pip install -r requirements.txt

# 3. Copy environment file and configure
cp .env.example .env
# For Discord, set DISCORD_BOT_TOKEN and DISCORD_GUILD_IDS

# 4. Start Qdrant (binds to 127.0.0.1 only)
docker-compose up -d

# 5. Download the LLM
ollama pull qwen3.5:9b

# 6. Add documents to data/  (git-ignored by design)
#    Try the corrected sample record:
cp fixtures/official/moc_token_addresses.md data/

# 7. Index documents (staging → verify → atomic alias swap)
uv run python main.py ingest

# 8. Run the Web UI (or the Discord bot)
uv run python main.py api    # Web UI at http://127.0.0.1:8000
uv run python main.py bot    # Discord bot (slash commands)
```

> Linux note: the lockfile installs CPU-only PyTorch wheels on Linux to avoid multi-GB CUDA downloads. For NVIDIA GPUs, remove the `pytorch-cpu` source block in `pyproject.toml` and re-run `uv lock`.

## Usage

### Discord Slash Commands

No privileged intents (message content) are required.

| Command | Description |
|---------|-------------|
| `/ask question:` | Ask about indexed Mossland documents |
| `/search query:` | Retrieval only, no LLM generation |
| `/status` | Real health check (Qdrant · Ollama · model · index) |
| `/ping` | Latency check |

Restrict the bot with `DISCORD_GUILD_IDS` / `DISCORD_CHANNEL_IDS`; per-user cooldown via `DISCORD_COOLDOWN_SECONDS`.

### CLI Commands

```bash
uv run python main.py api                     # Web UI & REST API
uv run python main.py bot                     # Discord bot
uv run python main.py ingest                  # index data/ (fail-closed)
uv run python main.py ingest --allow-partial  # tolerate unreadable files
uv run python main.py test                    # interactive CLI Q&A
uv run python main.py config                  # show configuration
```

### REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/api/query` | POST | Ask a question (`{"question": "..."}`) |
| `/api/search` | POST | Retrieval only (`{"query": "...", "top_k": 4}`) |
| `/api/health` | GET | Dependency-level health (Qdrant/Ollama/model/index) |
| `/docs` | GET | Swagger API docs |

## Configuration

All settings via `.env` (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Discord bot token | (required for bot) |
| `DISCORD_GUILD_IDS` | Comma-separated guild allowlist | (empty = all) |
| `DISCORD_CHANNEL_IDS` | Comma-separated channel allowlist | (empty = all) |
| `DISCORD_COOLDOWN_SECONDS` | Per-user cooldown for `/ask` and `/search` | `30` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | LLM model name | `qwen3.5:9b` |
| `QDRANT_HOST` / `QDRANT_PORT` | Qdrant address | `localhost` / `6333` |
| `QDRANT_COLLECTION_NAME` | Collection **alias** (atomic swap target) | `moss_knowledge` |
| `EMBEDDING_MODEL` | HuggingFace embedding model | `BAAI/bge-m3` |
| `EMBEDDING_DEVICE` | `auto` / `cuda` / `mps` / `cpu` | `auto` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Chunking parameters | `800` / `100` |
| `TOP_K_RESULTS` | Evidence chunks per answer | `4` |
| `MIN_DENSE_SCORE` | Minimum cosine similarity for evidence | `0.35` |
| `API_HOST` / `API_PORT` | API bind address | `127.0.0.1` / `8000` |
| `MAX_CONCURRENT_QUERIES` | Global query concurrency | `2` |
| `QUERY_TIMEOUT_SECONDS` | Per-query timeout | `180` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Security Defaults

- **Loopback only**: FastAPI and Qdrant bind to `127.0.0.1`. To share the service, put it behind a reverse proxy with TLS + auth, or a private overlay network (e.g. Tailscale). Do not just flip the bind address.
- **`data/` is git-ignored** so internal documents cannot be committed by accident. Sample documents live in `fixtures/` instead.
- **No question logging**: logs carry request IDs, latency, and source counts — not question text or usernames.
- **No error leakage**: users get generic error messages; details stay in server logs.
- **Discord**: slash commands only (no message-content intent), guild/channel allowlists, cooldowns.
- **Throttling**: global concurrency limit + queue and query timeouts protect the local LLM.

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Data Policy

- `data/` — your indexed corpus. Local only, never committed.
- `fixtures/official/` — records verified against canonical sources, with `canonical_url`, `as_of`, `fetched_at` frontmatter (e.g. current vs **deprecated** MOC contract addresses).
- `fixtures/synthetic/` — clearly-marked demo fixtures. Never treat as fact.

> ⚠️ MOC token addresses: the 2018 ERC-20 contract is **deprecated**. The current 2025 ERC-20 address and migration paths are recorded in [`fixtures/official/moc_token_addresses.md`](fixtures/official/moc_token_addresses.md) and verified against [mossland/MossCoin-ERC20-2025](https://github.com/mossland/MossCoin-ERC20-2025).

## Project Structure

```
mossland-nexus/
├── main.py               # CLI entry point
├── pyproject.toml        # dependencies (uv.lock = pinned resolution)
├── requirements.txt      # exported pins for pip users
├── docker-compose.yml    # Qdrant v1.18.2, loopback-bound
├── .env.example          # environment template
├── data/                 # your documents (git-ignored)
├── fixtures/             # sample corpora (official / synthetic)
├── static/               # Web UI (no external assets)
├── tests/                # unit tests (pytest)
├── .github/workflows/    # CI (ruff + pytest)
└── src/
    ├── config.py         # Pydantic settings
    ├── logging_setup.py  # central logging (privacy rules)
    ├── loaders.py        # PDF/MD/TXT/DOCX loading, per-file error tracking
    ├── splitter.py       # recursive text chunking
    ├── embeddings.py     # BGE-M3 dense+sparse, device auto-select
    ├── ingest.py         # staging → verify → atomic alias swap
    ├── rag_chain.py      # hybrid retrieval (RRF) + generation + health
    ├── api.py            # FastAPI (hardened defaults)
    └── bot.py            # Discord slash commands
```

## Roadmap

- **Evidence pipeline**: source manifests with stable IDs, revisions, and hashes; adapters for Agora/Disclosure machine-readable exports; `as_of` time-travel queries; conflict/staleness detection; exportable evidence packs for exchange due-diligence.
- **Retrieval quality**: `bge-reranker-v2-m3` reranking stage; Korean golden-set retrieval evaluation in CI.
- **Access**: optional API tokens for proxied deployments; local MCP surface.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Troubleshooting

**1. Qdrant "Connection refused"**
```bash
docker-compose ps && docker-compose up -d
```

**2. Ollama "model not found"**
```bash
ollama list
ollama pull qwen3.5:9b
```

**3. Ingest aborts with load errors**
The pipeline is fail-closed. Fix or remove the reported files, or run:
```bash
uv run python main.py ingest --allow-partial
```

**4. Empty answers ("찾을 수 없습니다")**
Evidence below `MIN_DENSE_SCORE` is discarded by design. Check `/api/search` output; re-ingest after adding relevant documents.

**5. Device check (Apple Silicon)**
```bash
uv run python -c "import torch; print(torch.backends.mps.is_available())"
```

## License

MIT — see [LICENSE](LICENSE).

## Links

- **Website**: https://moss.land
- **X (Twitter)**: https://x.com/TheMossland
- **Medium**: https://medium.com/mossland-blog
- **GitHub**: https://github.com/mossland

---

<a name="한국어"></a>
# 한국어

## 개요

**Moss Nexus**는 모스랜드의 공식 문서(공시, 제안서, 기록)를 **읽기 전용으로 색인**하고, 출처·해시·시점이 포함된 **검증 가능한 답변**을 만드는 로컬 우선(local-first) RAG 노드입니다. 모든 답변은 검색된 청크에 근거하며, 각 청크는 원본 파일명·내용 해시·색인 시각을 함께 가집니다.

Nexus는 **발행자가 아니라 색인자**입니다. 사실의 원본은 각 공식 저장소([MossCoin-ERC20-2025](https://github.com/mossland/MossCoin-ERC20-2025), [Agora](https://github.com/MosslandOpenDevs/Agora) 등)에 있으며, Nexus의 인덱스는 언제든 다시 만들 수 있는 파생 산출물입니다.

### 어디까지 로컬인가?

문서·임베딩·벡터 검색·LLM 추론은 모두 로컬에서 처리됩니다. 다만 다음 네트워크 접점은 알아두세요:

- **최초 실행 시** Hugging Face에서 임베딩 모델(~2.3GB), Ollama에서 LLM을 다운로드합니다.
- **Discord 어댑터**(선택)는 Discord API를 사용하며, 전송된 내용에는 Discord의 정책이 적용됩니다.
- Web UI는 외부 폰트/스크립트를 호출하지 않습니다.
- API와 Qdrant는 기본적으로 `127.0.0.1`에만 바인드됩니다.

### 모스랜드 생태계에서의 위치

| 서비스 | 역할 | Nexus와의 관계 |
|--------|------|----------------|
| [Agora](https://github.com/MosslandOpenDevs/Agora) | 구속력 있는 제안·투표 기록, AI 거버넌스 브리프 | 원천 데이터를 제공하는 System of Record |
| [Alpha](https://github.com/MosslandOpenDevs/alpha) | 공개 크립토 미디어 RAG + 무료 12-tool MCP ([alpha.moss.land](https://alpha.moss.land)) | 공개 범용 Q&A는 Alpha 담당 |
| Passport | 지갑 인증·자격·참여 기록 | 향후 읽기 전용 소스 후보 (개인정보 범위 확정 후) |
| Disclosure | 공시·유통량 발표 주체 | Nexus는 색인만 수행 |
| **Nexus** | **공식 기록의 로컬 감사·증거 노드** | 이 저장소 |

## 주요 기능

- **로컬 추론**: BGE-M3 임베딩과 Ollama LLM이 내 컴퓨터에서 실행 (Apple Silicon MPS / NVIDIA CUDA / CPU 자동 선택)
- **하이브리드 검색**: dense(의미) + sparse(어휘) 벡터를 RRF로 융합 — 컨트랙트 주소 같은 정확한 문자열도 놓치지 않음
- **백엔드 출처 조립**: 출처는 LLM이 아니라 검색 메타데이터(파일명·페이지·sha256 해시·색인 시각·점수)에서 조립되어 REST API와 Web UI로 노출 — 출처 조작 불가
- **관련도 게이트**: 임계값 미달 결과는 폐기, 근거가 없으면 추측 대신 "찾을 수 없음" 응답
- **원자적 재색인**: staging 컬렉션 → 검증 → Qdrant alias 전환. 실패한 색인이 기존 인덱스를 파괴할 수 없으며, 직전 인덱스는 롤백용으로 보존
- **Fail-closed 색인**: 파싱 실패 파일이 있으면 기본적으로 중단 (`--allow-partial`로 재정의 가능)
- **다중 형식**: PDF, Markdown, TXT, DOCX
- **인터페이스**: Web UI, REST API, Discord slash command (`/ask`, `/search`, `/status`, `/ping`)
- **안전 기본값**: 루프백 바인드, privileged intent 불필요, guild/채널 allowlist, 쿨다운, 동시성 제한, 질문 원문 비로깅, 내부 오류 비노출

## 하드웨어 요구사항

| 프로필 | Ollama 모델 | 다운로드 | 권장 RAM |
|--------|------------|----------|----------|
| 기본 | `qwen3.5:9b` | 6.6GB | 16GB+ |
| 고품질 | `qwen3.5:27b` | 17GB | 32GB+ |
| 저사양 개발용 | `qwen3.5:4b` | 3.4GB | 8GB+ |

임베딩 모델(BGE-M3, 다운로드 ~2.3GB)과 Qdrant용 여유 공간이 추가로 필요합니다.

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (권장) 또는 pip
- Docker (Qdrant용)
- [Ollama](https://ollama.com)

### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/MosslandOpenDevs/mossland-nexus.git
cd mossland-nexus

# 2. 의존성 설치 (버전 고정)
uv sync
#    pip 사용 시: python3 -m venv venv && source venv/bin/activate
#                 pip install -r requirements.txt

# 3. 환경 파일 복사 및 설정
cp .env.example .env
# Discord를 쓸 경우 DISCORD_BOT_TOKEN, DISCORD_GUILD_IDS 설정

# 4. Qdrant 시작 (127.0.0.1에만 바인드)
docker-compose up -d

# 5. LLM 다운로드
ollama pull qwen3.5:9b

# 6. data/ 폴더에 문서 추가 (git에서 무시됨)
#    교정된 샘플 레코드로 시작해볼 수 있습니다:
cp fixtures/official/moc_token_addresses.md data/

# 7. 문서 인덱싱 (staging → 검증 → alias 원자 전환)
uv run python main.py ingest

# 8. Web UI 또는 Discord 봇 실행
uv run python main.py api    # Web UI: http://127.0.0.1:8000
uv run python main.py bot    # Discord 봇 (slash commands)
```

> Linux 참고: 수 GB의 CUDA 다운로드를 피하기 위해 Linux에서는 CPU 전용 PyTorch 휠이 설치됩니다. NVIDIA GPU를 쓰려면 `pyproject.toml`의 `pytorch-cpu` 소스 블록을 제거하고 `uv lock`을 다시 실행하세요.

## 사용법

### Discord Slash Commands

privileged intent(메시지 내용 읽기) 없이 동작합니다.

| 명령어 | 설명 |
|--------|------|
| `/ask question:` | 색인된 모스랜드 문서에 대해 질문 |
| `/search query:` | 검색만 수행 (답변 생성 없음) |
| `/status` | 실제 상태 확인 (Qdrant · Ollama · 모델 · 인덱스) |
| `/ping` | 지연시간 확인 |

`DISCORD_GUILD_IDS` / `DISCORD_CHANNEL_IDS`로 사용 범위를 제한하고, `DISCORD_COOLDOWN_SECONDS`로 사용자별 쿨다운(`/ask`·`/search` 공통)을 설정하세요.

### CLI 명령어

```bash
uv run python main.py api                     # Web UI & REST API
uv run python main.py bot                     # Discord 봇
uv run python main.py ingest                  # data/ 색인 (fail-closed)
uv run python main.py ingest --allow-partial  # 읽기 실패 파일 허용
uv run python main.py test                    # 대화형 CLI 테스트
uv run python main.py config                  # 설정 확인
```

### REST API

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/` | GET | Web UI |
| `/api/query` | POST | 질문 (`{"question": "..."}`) |
| `/api/search` | POST | 검색만 (`{"query": "...", "top_k": 4}`) |
| `/api/health` | GET | 의존성 단위 상태 확인 |
| `/docs` | GET | Swagger API 문서 |

## 보안 기본값

- **루프백 전용**: FastAPI와 Qdrant는 `127.0.0.1`에 바인드됩니다. 외부 공유가 필요하면 바인드 주소만 바꾸지 말고, TLS+인증이 있는 reverse proxy나 Tailscale 같은 사설 네트워크 뒤에 두세요.
- **`data/`는 git에서 무시** — 내부 문서가 실수로 커밋되지 않습니다. 샘플은 `fixtures/`에서 관리합니다.
- **질문 비로깅**: 로그에는 요청 ID·처리 시간·근거 수만 남고, 질문 원문·사용자명은 남지 않습니다.
- **오류 비노출**: 사용자에게는 일반화된 메시지만, 상세 내용은 서버 로그에만.
- **Discord**: slash command 전용(privileged intent 불필요), allowlist, 쿨다운.
- **부하 제한**: 전역 동시성 제한 + 큐/질의 타임아웃으로 로컬 LLM 보호.

## 데이터 정책

- `data/` — 색인 대상 코퍼스. 로컬 전용, 커밋 금지.
- `fixtures/official/` — 공식 소스로 검증된 레코드 (`canonical_url`, `as_of`, `fetched_at` frontmatter 포함).
- `fixtures/synthetic/` — 명확히 표시된 데모용 합성 샘플. 사실로 취급 금지.

> ⚠️ **MOC 토큰 주소 주의**: 2018년 ERC-20 컨트랙트는 **폐기(deprecated)** 되었습니다. 현행 2025 ERC-20 주소와 마이그레이션 경로는 [`fixtures/official/moc_token_addresses.md`](fixtures/official/moc_token_addresses.md)에 기록되어 있으며 [mossland/MossCoin-ERC20-2025](https://github.com/mossland/MossCoin-ERC20-2025)에서 검증되었습니다.

## 로드맵

- **증거 파이프라인**: 안정적 ID·리비전·해시를 가진 source manifest, Agora/Disclosure 어댑터, `as_of` 시점 질의, 상충/노후 사실 탐지, 거래소 실사용 evidence pack 내보내기
- **검색 품질**: `bge-reranker-v2-m3` 재랭킹, 한국어 golden set 기반 검색 평가 CI
- **접근 제어**: 프록시 배포용 API 토큰, 로컬 MCP 서버

## 문제 해결

**1. Qdrant "Connection refused"**
```bash
docker-compose ps && docker-compose up -d
```

**2. Ollama "model not found"**
```bash
ollama list
ollama pull qwen3.5:9b
```

**3. 색인이 로드 오류로 중단됨**
파이프라인은 fail-closed입니다. 보고된 파일을 수정/제거하거나 다음을 실행하세요:
```bash
uv run python main.py ingest --allow-partial
```

**4. "찾을 수 없습니다" 답변**
`MIN_DENSE_SCORE` 미달 근거는 의도적으로 폐기됩니다. `/api/search`로 검색 결과를 확인하고, 관련 문서를 추가한 뒤 재색인하세요.

## 기여하기

코드 기여 방법은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요.

## 라이선스

이 프로젝트는 MIT 라이선스로 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 링크

- **웹사이트**: https://moss.land
- **X (트위터)**: https://x.com/TheMossland
- **미디엄**: https://medium.com/mossland-blog
- **깃허브**: https://github.com/mossland
