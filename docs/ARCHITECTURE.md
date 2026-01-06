# Architecture Documentation

This document describes the technical architecture of Moss Nexus, a local RAG-based AI assistant.

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Performance Considerations](#performance-considerations)
- [Security](#security)
- [Scalability](#scalability)

---

## System Overview

Moss Nexus is designed as a fully local AI assistant that runs entirely on Apple Silicon hardware without external API dependencies. The system uses RAG (Retrieval-Augmented Generation) to provide accurate, context-based answers from internal documents.

### Design Principles

1. **Privacy First**: All processing happens locally; no data leaves the machine
2. **Hardware Optimized**: Leverages Apple Silicon's MPS for GPU acceleration
3. **Modular Design**: Components are loosely coupled for easy maintenance
4. **Accuracy Over Speed**: Prioritizes correct answers with source citations

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              User Interfaces                             │
│                                                                         │
│   ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────────┐  │
│   │    Web UI       │  │  Discord Bot    │  │    REST API           │  │
│   │  (Browser)      │  │   (bot.py)      │  │   (api.py)            │  │
│   │                 │  │                 │  │                       │  │
│   │ static/         │  │ !ask, !search   │  │ /api/query            │  │
│   │ index.html      │  │ !status, !ping  │  │ /api/search           │  │
│   └────────┬────────┘  └────────┬────────┘  └───────────┬───────────┘  │
└────────────┼───────────────────┼────────────────────────┼──────────────┘
             │                   │                        │
             └───────────────────┼────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Core RAG Engine                               │
│                           (rag_chain.py)                                 │
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────┐ │
│   │   Query     │    │  Document   │    │      Answer Generation      │ │
│   │  Embedding  │───▶│  Retrieval  │───▶│        (LLM + Prompt)       │ │
│   │             │    │  (Top-K)    │    │                             │ │
│   └─────────────┘    └─────────────┘    └─────────────────────────────┘ │
└─────────┬────────────────────┬──────────────────────────┬───────────────┘
          │                    │                          │
          ▼                    ▼                          ▼
┌─────────────────┐  ┌─────────────────┐       ┌─────────────────────────┐
│   Embedding     │  │    Vector DB    │       │        LLM Server       │
│    Service      │  │                 │       │                         │
│  ┌───────────┐  │  │  ┌───────────┐  │       │  ┌───────────────────┐  │
│  │ HuggingFace│  │  │  │  Qdrant   │  │       │  │      Ollama       │  │
│  │ bge-m3    │  │  │  │ (Docker)  │  │       │  │   llama3.3:70b    │  │
│  │  (MPS)    │  │  │  │           │  │       │  │                   │  │
│  └───────────┘  │  │  └───────────┘  │       │  └───────────────────┘  │
└─────────────────┘  └─────────────────┘       └─────────────────────────┘
          ▲
          │
┌─────────┴─────────────────────────────────────────────────────────────┐
│                        Data Ingestion Pipeline                         │
│                            (ingest.py)                                 │
│                                                                        │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────────┐│
│   │  Load    │───▶│  Split   │───▶│  Embed   │───▶│  Store in Qdrant ││
│   │ Documents│    │ (Chunk)  │    │          │    │                  ││
│   └──────────┘    └──────────┘    └──────────┘    └──────────────────┘│
│        ▲                                                               │
│        │                                                               │
│   ┌────┴────┐                                                          │
│   │  data/  │  PDF, MD, TXT files                                      │
│   └─────────┘                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Configuration Module (`src/config.py`)

Manages application settings using Pydantic Settings.

```python
class Settings(BaseSettings):
    # Discord
    discord_bot_token: str

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.3:70b"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Embedding
    embedding_model: str = "BAAI/bge-m3"

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 100
```

**Key Features:**
- Environment variable loading from `.env`
- Type validation
- Default values for optional settings
- Singleton pattern for global access

### 2. Data Ingestion Pipeline (`src/ingest.py`)

Processes documents and stores them in the vector database.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DocumentIngester Class                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  _load_documents()                                              │
│  ├─ DirectoryLoader (PDF) ──────────────────┐                   │
│  ├─ DirectoryLoader (MD)  ──────────────────┼──▶ List[Document] │
│  └─ DirectoryLoader (TXT) ──────────────────┘                   │
│                                                                 │
│  _split_documents(documents)                                    │
│  └─ RecursiveCharacterTextSplitter ─────────────▶ List[Chunk]   │
│      ├─ chunk_size: 800                                         │
│      ├─ chunk_overlap: 100                                      │
│      └─ separators: ["\n\n", "\n", ".", " "]                    │
│                                                                 │
│  _create_collection()                                           │
│  └─ Qdrant Collection ──────────────────────────▶ moss_knowledge│
│      └─ vectors_config: cosine similarity                       │
│                                                                 │
│  ingest()                                                       │
│  └─ Qdrant.from_documents() ────────────────────▶ Indexed Data  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Chunking Strategy:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| chunk_size | 800 | Optimal for Korean text context |
| chunk_overlap | 100 | Maintains context between chunks |
| separators | `["\n\n", "\n", ".", " "]` | Preserves semantic boundaries |

### 3. RAG Chain (`src/rag_chain.py`)

Core retrieval and generation logic.

```
┌─────────────────────────────────────────────────────────────────┐
│                       RAGChain Class                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Components:                                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ embeddings = HuggingFaceEmbeddings(                         ││
│  │     model_name="BAAI/bge-m3",                               ││
│  │     model_kwargs={'device': 'mps'}  # Apple Silicon GPU     ││
│  │ )                                                           ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ retriever = vectorstore.as_retriever(                       ││
│  │     search_type="similarity",                               ││
│  │     search_kwargs={"k": 4}                                  ││
│  │ )                                                           ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ llm = Ollama(                                               ││
│  │     model="llama3.3:70b",                                   ││
│  │     temperature=0.1,  # Low for consistency                 ││
│  │     num_ctx=8192                                            ││
│  │ )                                                           ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  query(question: str) -> RAGResponse                            │
│  └─ Returns: answer, source_documents, query                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**System Prompt Design:**

```
당신은 모스랜드(Mossland)의 커뮤니티 매니저 'Moss Nexus'입니다.

[Rules]
1. 반드시 [Context]에 있는 내용만 사실로 간주하고 답변하세요.
2. [Context]에 없는 내용은 "죄송하지만..." 라고 답하세요.
3. 답변 끝에는 [Source: 파일명] 형식으로 출처를 남기세요.
4. 한국어로 답변하세요.
```

**Why These Rules:**
1. Prevents hallucination by grounding in context
2. Honest about knowledge limitations
3. Enables fact-checking via source citations
4. Optimized for Korean community

### 4. Web UI & REST API (`src/api.py`)

FastAPI-based web interface and REST API.

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Endpoints:                                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ GET  /           ──▶ Serve Web UI (static/index.html)       ││
│  │ POST /api/query  ──▶ RAG query ──▶ JSON response            ││
│  │ POST /api/search ──▶ Document search ──▶ JSON response      ││
│  │ GET  /api/health ──▶ System status check                    ││
│  │ GET  /docs       ──▶ Swagger API documentation              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  Web UI Features (static/):                                     │
│  ├─ Modern chat interface (index.html)                          │
│  ├─ Responsive CSS design (css/style.css)                       │
│  ├─ Real-time JavaScript logic (js/app.js)                      │
│  ├─ Typing indicator & loading animation                        │
│  ├─ Source document modal                                       │
│  └─ Processing time display                                     │
│                                                                 │
│  API Features:                                                  │
│  ├─ Pydantic request/response models                            │
│  ├─ CORS middleware for cross-origin requests                   │
│  ├─ Async request handling with run_in_executor                 │
│  └─ Lifespan management for RAG chain initialization            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Request/Response Models:**

```python
# Query Request
class QueryRequest(BaseModel):
    question: str  # 1-1000 characters

# Query Response
class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]
    query: str
    processing_time: float
```

### 5. Discord Bot (`src/bot.py`)

User interface layer.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Discord Bot                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Commands:                                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ !ask [question]  ──▶ RAG query ──▶ Embedded response        ││
│  │ !search [query]  ──▶ Document search only                   ││
│  │ !status          ──▶ System health check                    ││
│  │ !ping            ──▶ Latency check                          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  Features:                                                      │
│  ├─ Typing indicator during processing                          │
│  ├─ "Analyzing documents..." placeholder message                │
│  ├─ Long message pagination (>2000 chars)                       │
│  └─ Source document listing                                     │
│                                                                 │
│  Error Handling:                                                │
│  ├─ Graceful timeout handling                                   │
│  ├─ User-friendly error messages                                │
│  └─ Logging for debugging                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Query Processing Flow

```
User Question
      │
      ▼
┌─────────────────┐
│  Discord Bot    │  1. Receive "!ask What is MOC?"
│   receives      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Show typing    │  2. Display "Analyzing documents..."
│  indicator      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Embed query    │  3. Convert question to vector
│  (bge-m3/MPS)   │     [0.023, -0.156, 0.089, ...]
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Search Qdrant  │  4. Find top-4 similar documents
│  (cosine sim)   │     Score: 0.89, 0.85, 0.82, 0.78
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Build prompt   │  5. Inject documents into template
│  with context   │     [Context]: doc1, doc2, doc3, doc4
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate       │  6. Ollama generates response
│  (llama3.3:70b) │     ~10-30 seconds
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Format &       │  7. Create embed with answer
│  respond        │     + source citations
└─────────────────┘
```

### Document Ingestion Flow

```
data/ folder
├── document1.pdf
├── document2.md
└── document3.txt
         │
         ▼
┌─────────────────┐
│  Load documents │  DirectoryLoader per type
│  (parallel)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Extract text   │  PyPDF, UnstructuredMarkdown, TextLoader
│  + metadata     │  metadata: {source, filename}
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Split into     │  RecursiveCharacterTextSplitter
│  chunks         │  800 chars, 100 overlap
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate       │  bge-m3 embeddings (MPS accelerated)
│  embeddings     │  1024-dimensional vectors
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Store in       │  Qdrant collection: moss_knowledge
│  Qdrant         │  Cosine similarity index
└─────────────────┘
```

---

## Technology Stack

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | 3.11+ | Main runtime |
| LLM Framework | LangChain | 0.3.x | RAG orchestration |
| Vector DB | Qdrant | Latest | Document storage & search |
| LLM Server | Ollama | Latest | Local LLM inference |
| Embedding | HuggingFace | - | Text vectorization |
| Bot Framework | discord.py | 2.4+ | Discord integration |
| Config | Pydantic | 2.x | Settings management |

### Model Specifications

**Embedding Model: BAAI/bge-m3**
- Dimension: 1024
- Max tokens: 8192
- Languages: Multilingual (Korean optimized)
- Size: ~2.3GB

**LLM: llama3.3:70b (4-bit quantized)**
- Parameters: 70B (quantized to ~40GB)
- Context window: 128K tokens
- Quantization: Q4_K_M

### Infrastructure

```
┌─────────────────────────────────────────┐
│           Mac mini M4 Pro               │
│  ┌───────────────────────────────────┐  │
│  │  CPU: 14-core (10P + 4E)          │  │
│  │  GPU: 20-core (MPS)               │  │
│  │  RAM: 64GB Unified Memory         │  │
│  │  Storage: 512GB+ SSD              │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐  │
│  │ Python  │ │ Docker  │ │  Ollama   │  │
│  │  venv   │ │(Qdrant) │ │  Server   │  │
│  └─────────┘ └─────────┘ └───────────┘  │
└─────────────────────────────────────────┘
```

---

## Performance Considerations

### Memory Usage

| Component | Estimated RAM |
|-----------|---------------|
| Ollama (llama3.3:70b Q4) | ~40GB |
| Embedding model (bge-m3) | ~3GB |
| Qdrant (10K documents) | ~2GB |
| Python application | ~1GB |
| **Total** | **~46GB** |

### Latency Breakdown

| Operation | Typical Time |
|-----------|--------------|
| Query embedding | 50-100ms |
| Qdrant search | 10-50ms |
| LLM generation | 10-30s |
| **Total** | **~10-30s** |

### Optimization Strategies

1. **MPS Acceleration**
   ```python
   model_kwargs={'device': 'mps'}
   ```

2. **Batch Embedding**
   ```python
   encode_kwargs={'batch_size': 32}
   ```

3. **Connection Pooling**
   - Singleton RAG chain instance
   - Persistent Qdrant connection

4. **Caching** (Future)
   - Query result caching
   - Embedding caching

---

## Security

### Data Privacy

- **Local Processing**: All data stays on the machine
- **No External APIs**: No OpenAI, no cloud services
- **Network Isolation**: Only Discord API calls leave the machine

### Access Control

- **Discord Permissions**: Bot requires specific channel access
- **No Authentication Layer** (v1.0): Suitable for internal use

### Document Security

- **data/ folder**: Should be protected at OS level
- **Sensitive Documents**: Consider encryption at rest
- **Qdrant**: Runs locally, no external exposure

---

## Scalability

### Current Limitations

| Aspect | Limit | Bottleneck |
|--------|-------|------------|
| Concurrent queries | 1 | LLM inference |
| Document count | ~50K chunks | RAM |
| Response time | 30s max | LLM speed |

### Future Scaling Options

1. **Horizontal Scaling**
   - Multiple Ollama instances
   - Load balancer for queries

2. **Vertical Scaling**
   - More RAM for larger models
   - Faster storage (NVMe)

3. **Caching Layer**
   - Redis for frequent queries
   - Embedding cache

4. **Async Processing**
   - Queue-based query handling
   - Background document indexing

---

## Future Architecture

### Planned Enhancements

```
┌─────────────────────────────────────────────────────────────────┐
│                      Future Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐ │
│  │ Discord │  │  Slack  │  │  Web UI │  │    REST API         │ │
│  │   Bot   │  │   Bot   │  │(React)  │  │   (FastAPI)         │ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └──────────┬──────────┘ │
│       └────────────┴────────────┴──────────────────┘            │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    API Gateway (FastAPI)                   │  │
│  │  ┌─────────┐  ┌─────────────┐  ┌────────────────────────┐ │  │
│  │  │  Auth   │  │ Rate Limit  │  │    Request Queue       │ │  │
│  │  └─────────┘  └─────────────┘  └────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    RAG Engine Cluster                      │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                    │  │
│  │  │ Worker 1│  │ Worker 2│  │ Worker 3│  (Auto-scaling)    │  │
│  │  └─────────┘  └─────────┘  └─────────┘                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│              ┌───────────────┼───────────────┐                  │
│              ▼               ▼               ▼                  │
│  ┌─────────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │     Qdrant      │ │   Redis     │ │   Ollama Cluster    │   │
│  │    Cluster      │ │   Cache     │ │                     │   │
│  └─────────────────┘ └─────────────┘ └─────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## References

- [LangChain Documentation](https://python.langchain.com/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Ollama Documentation](https://ollama.ai/docs)
- [BAAI/bge-m3 Model Card](https://huggingface.co/BAAI/bge-m3)
- [discord.py Documentation](https://discordpy.readthedocs.io/)
