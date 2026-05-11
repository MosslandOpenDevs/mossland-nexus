<p align="center">
  <h1 align="center">Moss Nexus</h1>
  <p align="center">
    <strong>AI Governance Assistant for Mossland</strong><br>
    Local RAG-based Discord Bot powered by Ollama & Qdrant
  </p>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#usage">Usage</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#한국어">한국어</a>
</p>

---

## Overview

**Moss Nexus** is a fully local AI assistant that answers questions about Mossland by searching internal documents (disclosures, blogs, proposals) using RAG (Retrieval-Augmented Generation). It runs entirely on Apple Silicon without external cloud APIs.

### Why "Nexus"?

*Nexus* means "connection" or "center" — representing the central hub where all Mossland knowledge connects.

### Cloud-hosted sibling

For an externally-hosted RAG surface over Korean crypto / macro narratives (not just Mossland docs), see [Alpha](https://alpha.moss.land?utm_source=github&utm_medium=referral&utm_campaign=nexus-readme) — alpha.moss.land — with a free public 12-tool MCP server at [`/api/mcp`](https://alpha.moss.land/api/mcp) ([repo](https://github.com/MosslandOpenDevs/alpha) · [MCP catalog entry](https://github.com/MosslandOpenDevs/alpha-mcp)).

## Features

- **100% Local Execution**: No OpenAI or external API calls. Everything runs on your Mac.
- **Apple Silicon Optimized**: MPS (Metal Performance Shaders) acceleration for embeddings.
- **RAG Pipeline**: Accurate, fact-based answers with source citations.
- **Multi-format Support**: PDF, Markdown, and TXT document ingestion.
- **Web UI**: Modern chat interface accessible via browser.
- **REST API**: FastAPI-based API for integration with other services.
- **Discord Integration**: Easy-to-use bot interface with `!ask` command.
- **Hallucination Prevention**: Strict prompting to only answer from provided context.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       User Interfaces                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  Web UI     │    │ Discord Bot │    │     REST API        │  │
│  │ (Browser)   │    │  (bot.py)   │    │    (api.py)         │  │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘  │
└─────────┼──────────────────┼─────────────────────┼──────────────┘
          └──────────────────┼─────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         RAG Chain                                │
│                    (rag_chain.py - LangChain)                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   Query     │───▶│  Retriever  │───▶│   LLM Generation    │  │
│  │  Embedding  │    │  (Top-K)    │    │   (Ollama)          │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
└────────┬────────────────────┬───────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│   HuggingFace   │  │     Qdrant      │  │      Ollama         │
│   Embeddings    │  │   Vector DB     │  │   llama3.3:70b      │
│   (BAAI/bge-m3) │  │   (Docker)      │  │   (Local LLM)       │
└─────────────────┘  └─────────────────┘  └─────────────────────┘
         │
         ▼
┌─────────────────┐
│  Data Ingestion │
│   (ingest.py)   │
│  PDF/MD/TXT     │
└─────────────────┘
```

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Chip | Apple Silicon (M1+) | M4 Pro or better |
| RAM | 32GB | 64GB+ |
| Storage | 50GB free | 100GB+ SSD |
| OS | macOS Ventura | macOS Sequoia |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker Desktop
- Ollama installed ([ollama.ai](https://ollama.ai))

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/mossland/mossland-nexus.git
cd mossland-nexus

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment file and configure
cp .env.example .env
# Edit .env and set your DISCORD_BOT_TOKEN

# 5. Start Qdrant (Vector Database)
docker-compose up -d

# 6. Download LLM model via Ollama
ollama pull llama3.3:70b

# 7. Add your documents to data/ folder
# Supported formats: PDF, MD, TXT

# 8. Index your documents
python main.py ingest

# 9. Run the Web UI (or Discord bot)
python main.py api    # Web UI at http://localhost:8000
# or
python main.py bot    # Discord bot
```

## Usage

### Discord Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!ask [question]` | Ask about Mossland | `!ask What is MOC token?` |
| `!search [query]` | Search documents only | `!search tokenomics` |
| `!status` | Check system status | `!status` |
| `!ping` | Check bot latency | `!ping` |

### CLI Commands

```bash
# Run Web UI & API server
python main.py api

# Run Discord bot
python main.py bot

# Index documents in data/ folder
python main.py ingest

# Interactive CLI test mode
python main.py test

# Show current configuration
python main.py config
```

### Web UI

Access the web interface at `http://localhost:8000` after running:

```bash
python main.py api
```

**API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/api/query` | POST | Ask a question |
| `/api/search` | POST | Search documents |
| `/api/health` | GET | Health check |
| `/docs` | GET | Swagger API docs |

## Configuration

All settings are managed via `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Discord bot token | (required) |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | LLM model name | `llama3.3:70b` |
| `QDRANT_HOST` | Qdrant host | `localhost` |
| `QDRANT_PORT` | Qdrant port | `6333` |
| `EMBEDDING_MODEL` | HuggingFace model | `BAAI/bge-m3` |
| `CHUNK_SIZE` | Document chunk size | `800` |
| `CHUNK_OVERLAP` | Chunk overlap | `100` |
| `TOP_K_RESULTS` | Number of retrieved docs | `4` |

## Project Structure

```
mossland-nexus/
├── main.py              # Main entry point
├── requirements.txt     # Python dependencies
├── docker-compose.yml   # Qdrant container config
├── .env.example         # Environment template
├── data/                # Document storage (PDF, MD, TXT)
├── logs/                # Log files
├── docs/                # Documentation
│   └── ARCHITECTURE.md
└── src/
    ├── __init__.py
    ├── config.py        # Settings management (Pydantic)
    ├── ingest.py        # Data ingestion pipeline
    ├── rag_chain.py     # RAG retrieval & generation
    └── bot.py           # Discord bot interface
```

## Troubleshooting

### Common Issues

**1. "MPS device not available"**
```bash
# Check PyTorch MPS support
python -c "import torch; print(torch.backends.mps.is_available())"
```

**2. "Connection refused" for Qdrant**
```bash
# Ensure Qdrant container is running
docker-compose ps
docker-compose up -d
```

**3. "Model not found" for Ollama**
```bash
# List available models
ollama list

# Pull the model if missing
ollama pull llama3.3:70b
```

**4. Empty search results**
```bash
# Re-run document ingestion
python main.py ingest
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

- **Website**: https://moss.land
- **X (Twitter)**: https://x.com/TheMossland
- **Medium**: https://medium.com/mossland-blog
- **GitHub**: https://github.com/mossland

---

<a name="한국어"></a>
# 한국어

## 개요

**Moss Nexus**는 모스랜드의 내부 문서(공시, 블로그, 제안서)를 검색하여 질문에 답변하는 완전 로컬 AI 어시스턴트입니다. RAG(검색 증강 생성) 기술을 사용하며, 외부 클라우드 API 없이 Apple Silicon Mac에서 100% 로컬로 실행됩니다.

### 왜 "Nexus"인가?

*Nexus*는 "연결" 또는 "중심"을 의미합니다 — 모스랜드의 모든 지식이 연결되는 중심 허브를 나타냅니다.

## 주요 기능

- **100% 로컬 실행**: OpenAI 등 외부 API 호출 없음. 모든 것이 Mac에서 실행됩니다.
- **Apple Silicon 최적화**: 임베딩에 MPS(Metal Performance Shaders) 가속 사용.
- **RAG 파이프라인**: 출처 인용이 포함된 정확하고 사실 기반의 답변.
- **다중 형식 지원**: PDF, Markdown, TXT 문서 수집.
- **Web UI**: 브라우저에서 접근 가능한 모던 채팅 인터페이스.
- **REST API**: 다른 서비스와 연동 가능한 FastAPI 기반 API.
- **Discord 연동**: `!ask` 명령어로 쉽게 사용하는 봇 인터페이스.
- **환각 방지**: 제공된 컨텍스트에서만 답변하도록 엄격한 프롬프팅.

## 하드웨어 요구사항

| 구성요소 | 최소 | 권장 |
|----------|------|------|
| 칩 | Apple Silicon (M1+) | M4 Pro 이상 |
| RAM | 32GB | 64GB+ |
| 저장공간 | 50GB 여유 | 100GB+ SSD |
| OS | macOS Ventura | macOS Sequoia |

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- Docker Desktop
- Ollama 설치 ([ollama.ai](https://ollama.ai))

### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/mossland/mossland-nexus.git
cd mossland-nexus

# 2. 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 파일 복사 및 설정
cp .env.example .env
# .env 파일을 편집하여 DISCORD_BOT_TOKEN 설정

# 5. Qdrant 시작 (벡터 데이터베이스)
docker-compose up -d

# 6. Ollama를 통해 LLM 모델 다운로드
ollama pull llama3.3:70b

# 7. data/ 폴더에 문서 추가
# 지원 형식: PDF, MD, TXT

# 8. 문서 인덱싱
python main.py ingest

# 9. Web UI 또는 Discord 봇 실행
python main.py api    # Web UI: http://localhost:8000
# 또는
python main.py bot    # Discord 봇
```

## 사용법

### Web UI

`python main.py api` 실행 후 `http://localhost:8000`에서 접속:

**API 엔드포인트:**

| 엔드포인트 | 메서드 | 설명 |
|------------|--------|------|
| `/` | GET | Web UI |
| `/api/query` | POST | 질문하기 |
| `/api/search` | POST | 문서 검색 |
| `/api/health` | GET | 상태 확인 |
| `/docs` | GET | Swagger API 문서 |

### Discord 명령어

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `!ask [질문]` | 모스랜드에 대해 질문 | `!ask MOC 토큰이 뭔가요?` |
| `!search [검색어]` | 문서만 검색 | `!search 토큰 분배` |
| `!status` | 시스템 상태 확인 | `!status` |
| `!ping` | 봇 지연시간 확인 | `!ping` |

### CLI 명령어

```bash
# Web UI & API 서버 실행
python main.py api

# Discord 봇 실행
python main.py bot

# data/ 폴더의 문서 인덱싱
python main.py ingest

# 대화형 CLI 테스트 모드
python main.py test

# 현재 설정 표시
python main.py config
```

## 설정

모든 설정은 `.env` 파일로 관리됩니다:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DISCORD_BOT_TOKEN` | Discord 봇 토큰 | (필수) |
| `OLLAMA_BASE_URL` | Ollama 서버 URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | LLM 모델명 | `llama3.3:70b` |
| `QDRANT_HOST` | Qdrant 호스트 | `localhost` |
| `QDRANT_PORT` | Qdrant 포트 | `6333` |
| `EMBEDDING_MODEL` | HuggingFace 모델 | `BAAI/bge-m3` |
| `CHUNK_SIZE` | 문서 청크 크기 | `800` |
| `CHUNK_OVERLAP` | 청크 중복 크기 | `100` |
| `TOP_K_RESULTS` | 검색 문서 수 | `4` |

## 문제 해결

### 자주 발생하는 문제

**1. "MPS device not available"**
```bash
# PyTorch MPS 지원 확인
python -c "import torch; print(torch.backends.mps.is_available())"
```

**2. Qdrant "Connection refused"**
```bash
# Qdrant 컨테이너 실행 확인
docker-compose ps
docker-compose up -d
```

**3. Ollama "Model not found"**
```bash
# 사용 가능한 모델 목록 확인
ollama list

# 모델이 없으면 다운로드
ollama pull llama3.3:70b
```

**4. 검색 결과 없음**
```bash
# 문서 인덱싱 다시 실행
python main.py ingest
```

## 기여하기

코드 기여 방법은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요.

## 라이선스

이 프로젝트는 MIT 라이선스로 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 링크

- **웹사이트**: https://moss.land
- **X (트위터)**: https://x.com/TheMossland
- **미디엄**: https://medium.com/mossland-blog
- **깃허브**: https://github.com/mossland
