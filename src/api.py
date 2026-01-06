# ===================================================
# Moss Nexus - FastAPI REST API & Web UI
# 웹 인터페이스 및 REST API 서버
# ===================================================
"""
이 모듈은 웹 브라우저에서 RAG 시스템에 접근할 수 있는
REST API와 Web UI를 제공합니다.

주요 기능:
1. POST /api/query - 질문에 대한 답변 생성
2. POST /api/search - 문서 검색만 수행
3. GET /api/health - 시스템 상태 확인
4. GET / - 웹 UI 제공
"""

import sys
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger

from src.config import settings
from src.rag_chain import get_rag_chain, RAGChain


# ─────────────────────────────────────────────────
# 로깅 설정
# ─────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


# ─────────────────────────────────────────────────
# Pydantic 모델 (Request/Response)
# ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    """질문 요청 모델"""
    question: str = Field(..., min_length=1, max_length=1000, description="질문 내용")


class SourceDocument(BaseModel):
    """출처 문서 모델"""
    filename: str
    content: str
    chunk_id: Optional[int] = None


class QueryResponse(BaseModel):
    """질문 응답 모델"""
    answer: str
    sources: List[SourceDocument]
    query: str
    processing_time: float


class SearchRequest(BaseModel):
    """검색 요청 모델"""
    query: str = Field(..., min_length=1, max_length=500, description="검색어")
    top_k: Optional[int] = Field(default=4, ge=1, le=10, description="검색 결과 수")


class SearchResponse(BaseModel):
    """검색 응답 모델"""
    results: List[SourceDocument]
    query: str
    total_results: int


class HealthResponse(BaseModel):
    """헬스체크 응답 모델"""
    status: str
    rag_chain: str
    ollama_model: str
    embedding_model: str
    qdrant_url: str
    timestamp: str


# ─────────────────────────────────────────────────
# RAG Chain 인스턴스 (전역)
# ─────────────────────────────────────────────────
rag_chain: Optional[RAGChain] = None


# ─────────────────────────────────────────────────
# FastAPI 앱 생성
# ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱 시작/종료 시 실행되는 라이프사이클 관리자
    """
    global rag_chain

    # 시작 시: RAG Chain 초기화
    logger.info("FastAPI 서버 시작 중...")
    logger.info("RAG Chain 초기화 중...")

    try:
        rag_chain = get_rag_chain()
        logger.info("RAG Chain 초기화 완료!")
    except Exception as e:
        logger.error(f"RAG Chain 초기화 실패: {e}")
        logger.warning("API 서버는 실행되지만 질문 기능이 작동하지 않을 수 있습니다.")

    yield

    # 종료 시: 정리 작업
    logger.info("FastAPI 서버 종료 중...")


app = FastAPI(
    title="Moss Nexus API",
    description="모스랜드 AI 거버넌스 어시스턴트 REST API",
    version="1.0.0",
    lifespan=lifespan
)


# ─────────────────────────────────────────────────
# CORS 설정 (개발용)
# ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    """
    메인 웹 UI 페이지를 제공합니다.
    """
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        return HTMLResponse(
            content="<h1>Moss Nexus</h1><p>Web UI not found. Please check static/index.html</p>",
            status_code=200
        )


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    시스템 상태를 확인합니다.

    Returns:
        HealthResponse: 시스템 상태 정보
    """
    global rag_chain

    return HealthResponse(
        status="healthy" if rag_chain is not None else "degraded",
        rag_chain="initialized" if rag_chain is not None else "not initialized",
        ollama_model=settings.ollama_model,
        embedding_model=settings.embedding_model,
        qdrant_url=settings.qdrant_url,
        timestamp=datetime.now().isoformat()
    )


@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    질문에 대한 답변을 생성합니다.

    Args:
        request: 질문 요청

    Returns:
        QueryResponse: 답변, 출처, 처리 시간
    """
    global rag_chain

    if rag_chain is None:
        raise HTTPException(
            status_code=503,
            detail="RAG 시스템이 초기화되지 않았습니다. 잠시 후 다시 시도해주세요."
        )

    logger.info(f"질문 수신: {request.question[:50]}...")
    start_time = asyncio.get_event_loop().time()

    try:
        # RAG 체인 호출 (동기 함수를 비동기로 실행)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            rag_chain.query,
            request.question
        )

        # 출처 문서 변환
        sources = []
        for doc in response.source_documents:
            sources.append(SourceDocument(
                filename=doc.metadata.get('filename', 'unknown'),
                content=doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content,
                chunk_id=doc.metadata.get('chunk_id')
            ))

        end_time = asyncio.get_event_loop().time()
        processing_time = round(end_time - start_time, 2)

        logger.info(f"답변 생성 완료 (처리 시간: {processing_time}s)")

        return QueryResponse(
            answer=response.answer,
            sources=sources,
            query=request.question,
            processing_time=processing_time
        )

    except Exception as e:
        logger.error(f"질문 처리 중 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"질문 처리 중 오류가 발생했습니다: {str(e)}"
        )


@app.post("/api/search", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    """
    문서를 검색합니다 (답변 생성 없이).

    Args:
        request: 검색 요청

    Returns:
        SearchResponse: 검색된 문서 리스트
    """
    global rag_chain

    if rag_chain is None:
        raise HTTPException(
            status_code=503,
            detail="RAG 시스템이 초기화되지 않았습니다."
        )

    logger.info(f"검색 요청: {request.query}")

    try:
        loop = asyncio.get_event_loop()
        documents = await loop.run_in_executor(
            None,
            lambda: rag_chain.search_documents(request.query, request.top_k)
        )

        results = []
        for doc in documents:
            results.append(SourceDocument(
                filename=doc.metadata.get('filename', 'unknown'),
                content=doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content,
                chunk_id=doc.metadata.get('chunk_id')
            ))

        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results)
        )

    except Exception as e:
        logger.error(f"검색 중 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"검색 중 오류가 발생했습니다: {str(e)}"
        )


# ─────────────────────────────────────────────────
# 서버 실행 함수
# ─────────────────────────────────────────────────
def run_api():
    """
    FastAPI 서버를 실행합니다.
    """
    import uvicorn

    print("=" * 60)
    print("       Moss Nexus - Web API Server")
    print("       모스랜드 AI 거버넌스 어시스턴트")
    print("=" * 60)
    print()
    print(f"  Web UI: http://{settings.api_host}:{settings.api_port}")
    print(f"  API Docs: http://{settings.api_host}:{settings.api_port}/docs")
    print()
    print(f"  LLM Model: {settings.ollama_model}")
    print(f"  Embedding: {settings.embedding_model}")
    print()
    print("=" * 60)
    print()

    uvicorn.run(
        "src.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    run_api()
