# ===================================================
# Moss Nexus - FastAPI REST API & Web UI
# 웹 인터페이스 및 REST API 서버
# ===================================================
"""
로컬 전용 REST API와 Web UI.

보안 기본값:
- 기본 바인드는 127.0.0.1 (외부 공개는 reverse proxy/TLS/Tailscale 뒤에서만)
- 전역 동시성 제한 + 큐 대기/질의 타임아웃
- 내부 예외 문자열을 사용자에게 노출하지 않음
- 질문 원문을 로그에 남기지 않음 (요청 ID·처리 시간·근거 수만 기록)
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, Field

from src.config import settings
from src.logging_setup import setup_logging
from src.rag_chain import RAGChain, RetrievedChunk, get_rag_chain

setup_logging()

GENERIC_QUERY_ERROR = "질문 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
GENERIC_SEARCH_ERROR = "검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
BUSY_ERROR = "서버가 혼잡합니다. 잠시 후 다시 시도해주세요."
NOT_READY_ERROR = "RAG 시스템이 초기화되지 않았습니다. 잠시 후 다시 시도해주세요."


# ─────────────────────────────────────────────────
# Pydantic 모델 (Request/Response)
# ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    """질문 요청 모델"""
    question: str = Field(..., min_length=1, max_length=1000, description="질문 내용")


class SourceDocument(BaseModel):
    """출처 문서 모델 (백엔드가 검색 메타데이터에서 조립 — 검증 가능한 인용)"""
    filename: str
    content: str
    chunk_index: int | None = None
    page: int | None = None
    score: float | None = None
    content_hash: str | None = None   # 청크 본문의 sha256
    ingested_at: str | None = None    # 색인 시각 (ISO 8601, UTC)


class QueryResponse(BaseModel):
    """질문 응답 모델"""
    answer: str
    sources: list[SourceDocument]
    query: str
    processing_time: float


class SearchRequest(BaseModel):
    """검색 요청 모델"""
    query: str = Field(..., min_length=1, max_length=500, description="검색어")
    top_k: int | None = Field(default=4, ge=1, le=10, description="검색 결과 수")


class SearchResponse(BaseModel):
    """검색 응답 모델"""
    results: list[SourceDocument]
    query: str
    total_results: int


class HealthResponse(BaseModel):
    """헬스체크 응답 모델"""
    status: str
    qdrant: bool
    ollama: bool
    model_available: bool
    collection_points: int | None
    ollama_model: str
    embedding_model: str
    timestamp: str


# ─────────────────────────────────────────────────
# 전역 상태
# ─────────────────────────────────────────────────
rag_chain: RAGChain | None = None
query_semaphore = asyncio.Semaphore(settings.max_concurrent_queries)


def _to_source_documents(chunks: list[RetrievedChunk]) -> list[SourceDocument]:
    """검색 청크를 응답용 출처 문서로 변환합니다 (본문은 500자로 절단)."""
    sources = []
    for chunk in chunks:
        content = chunk.content
        if len(content) > 500:
            content = content[:500] + "..."
        sources.append(SourceDocument(
            filename=chunk.filename,
            content=content,
            chunk_index=chunk.chunk_index,
            page=chunk.page,
            score=round(chunk.score, 4),
            content_hash=chunk.content_hash,
            ingested_at=chunk.ingested_at,
        ))
    return sources


async def _run_limited(func, *args, timeout: float):
    """
    동시성 제한 + 타임아웃 하에 동기 함수를 실행합니다.

    실행 중인 스레드는 취소할 수 없으므로, 세마포어 슬롯은 타임아웃 시점이
    아니라 스레드가 실제로 끝나는 시점에 반환합니다 — 그래야 LLM이 느려져도
    MAX_CONCURRENT_QUERIES가 실제 동시 작업 수를 계속 제한합니다.
    """
    try:
        await asyncio.wait_for(
            query_semaphore.acquire(), timeout=settings.queue_timeout_seconds
        )
    except TimeoutError:
        raise HTTPException(status_code=429, detail=BUSY_ERROR) from None

    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, func, *args)

    def _release(finished):
        if not finished.cancelled():
            finished.exception()  # 미회수 예외 경고 방지
        query_semaphore.release()

    future.add_done_callback(_release)
    return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)


# ─────────────────────────────────────────────────
# FastAPI 앱 생성
# ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 라이프사이클 관리자"""
    global rag_chain

    logger.info("FastAPI 서버 시작 중...")
    try:
        rag_chain = get_rag_chain()
        logger.info("RAG Chain 초기화 완료")
    except Exception as e:
        logger.error(f"RAG Chain 초기화 실패: {type(e).__name__}: {e}")
        logger.warning("API 서버는 실행되지만 질문 기능이 작동하지 않습니다.")

    yield

    logger.info("FastAPI 서버 종료 중...")


app = FastAPI(
    title="Moss Nexus API",
    description="Mossland local-first knowledge & evidence node — REST API",
    version="2.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────
# CORS 설정 — Web UI는 same-origin이므로 로컬 origin만 허용
# ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.api_port}",
        f"http://127.0.0.1:{settings.api_port}",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ─────────────────────────────────────────────────
# Static 파일 서빙
# ─────────────────────────────────────────────────
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# ─────────────────────────────────────────────────
# API 엔드포인트
# ─────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """메인 웹 UI 페이지를 제공합니다."""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse(
        content="<h1>Moss Nexus</h1><p>Web UI not found. Please check static/index.html</p>",
        status_code=200,
    )


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    시스템 상태를 확인합니다.

    RAG 객체 존재 여부가 아니라 Qdrant·Ollama·컬렉션·모델의
    실제 접근 가능 여부를 검사합니다.
    """
    if rag_chain is None:
        return HealthResponse(
            status="down",
            qdrant=False,
            ollama=False,
            model_available=False,
            collection_points=None,
            ollama_model=settings.ollama_model,
            embedding_model=settings.embedding_model,
            timestamp=datetime.now(UTC).isoformat(),
        )

    loop = asyncio.get_event_loop()
    checks = await loop.run_in_executor(None, rag_chain.health)

    return HealthResponse(
        status="healthy" if checks["healthy"] else "degraded",
        qdrant=checks["qdrant"],
        ollama=checks["ollama"],
        model_available=checks["model_available"],
        collection_points=checks["collection_points"],
        ollama_model=settings.ollama_model,
        embedding_model=settings.embedding_model,
        timestamp=datetime.now(UTC).isoformat(),
    )


@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """질문에 대한 답변을 생성합니다."""
    if rag_chain is None:
        raise HTTPException(status_code=503, detail=NOT_READY_ERROR)

    request_id = uuid.uuid4().hex[:8]
    logger.info(f"[{request_id}] 질문 수신 (길이: {len(request.question)}자)")
    loop = asyncio.get_event_loop()
    start_time = loop.time()

    try:
        response = await _run_limited(
            rag_chain.query,
            request.question,
            timeout=settings.query_timeout_seconds,
        )
    except HTTPException:
        raise
    except TimeoutError:
        logger.error(f"[{request_id}] 질의 타임아웃 ({settings.query_timeout_seconds}s)")
        raise HTTPException(status_code=504, detail=BUSY_ERROR) from None
    except Exception as e:
        logger.error(f"[{request_id}] 질문 처리 중 오류: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=GENERIC_QUERY_ERROR) from None

    processing_time = round(loop.time() - start_time, 2)
    logger.info(
        f"[{request_id}] 답변 생성 완료 "
        f"(처리 시간: {processing_time}s, 근거: {len(response.sources)}개)"
    )

    return QueryResponse(
        answer=response.answer,
        sources=_to_source_documents(response.sources),
        query=request.question,
        processing_time=processing_time,
    )


@app.post("/api/search", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    """문서를 검색합니다 (답변 생성 없이)."""
    if rag_chain is None:
        raise HTTPException(status_code=503, detail=NOT_READY_ERROR)

    request_id = uuid.uuid4().hex[:8]
    logger.info(f"[{request_id}] 검색 요청 (길이: {len(request.query)}자)")

    try:
        chunks = await _run_limited(
            rag_chain.search,
            request.query,
            request.top_k,
            timeout=settings.query_timeout_seconds,
        )
    except HTTPException:
        raise
    except TimeoutError:
        raise HTTPException(status_code=504, detail=BUSY_ERROR) from None
    except Exception as e:
        logger.error(f"[{request_id}] 검색 중 오류: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=GENERIC_SEARCH_ERROR) from None

    results = _to_source_documents(chunks)
    return SearchResponse(
        results=results,
        query=request.query,
        total_results=len(results),
    )


# ─────────────────────────────────────────────────
# 서버 실행 함수
# ─────────────────────────────────────────────────
def run_api():
    """FastAPI 서버를 실행합니다."""
    import uvicorn

    print("=" * 60)
    print("       Moss Nexus - Web API Server")
    print("       Mossland Local-first Knowledge & Evidence Node")
    print("=" * 60)
    print()
    print(f"  Web UI: http://{settings.api_host}:{settings.api_port}")
    print(f"  API Docs: http://{settings.api_host}:{settings.api_port}/docs")
    print()
    print(f"  LLM Model: {settings.ollama_model}")
    print(f"  Embedding: {settings.embedding_model}")
    print()
    if settings.api_host not in ("127.0.0.1", "localhost"):
        print("  ⚠️  주의: 루프백이 아닌 주소에 바인드되어 있습니다.")
        print("      외부 공개는 reverse proxy/TLS/인증 뒤에서만 하세요.")
        print()
    print("=" * 60)
    print()

    uvicorn.run(
        "src.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run_api()
