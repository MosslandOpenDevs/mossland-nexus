# ===================================================
# Moss Nexus - RAG Module
# 하이브리드 검색(dense+sparse RRF) + 로컬 LLM 생성
# ===================================================
"""
RAG 파이프라인 (LangChain 미사용):

1. 질문을 BGE-M3로 dense + sparse 임베딩
2. Qdrant에서 dense(의미) / sparse(어휘) 병렬 검색
3. RRF(Reciprocal Rank Fusion)로 융합, 상위 K개 선택
   - dense 검색에는 최소 유사도 임계값 적용
   - 근거가 없으면 LLM을 호출하지 않고 "찾을 수 없음" 응답
4. Ollama LLM이 컨텍스트 기반 답변 생성
5. 출처는 LLM이 아니라 백엔드가 검색 메타데이터에서 조립
"""

from dataclasses import dataclass

import ollama
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client import models as qdrant_models

from src.config import settings
from src.logging_setup import setup_logging

setup_logging()


# ─────────────────────────────────────────────────
# 시스템 프롬프트
# ─────────────────────────────────────────────────
SYSTEM_PROMPT = """당신은 모스랜드(Mossland) 문서를 검색해 답변하는 어시스턴트 'Moss Nexus'입니다.

[Rules]
1. 반드시 [Context]에 있는 내용만 사실로 간주하고 답변하세요.
2. 근거가 없으면 "죄송하지만, 색인된 문서에서 해당 정보를 찾을 수 없습니다."라고 답하세요.
3. 추측하거나 일반 지식으로 보완하지 마세요.
4. 답변 문장의 근거가 된 문서 번호를 [1], [2] 형식으로 표기하세요.
5. 한국어로 답변하세요."""

NO_RESULT_ANSWER = "죄송하지만, 색인된 문서에서 관련 정보를 찾을 수 없습니다."


@dataclass
class RetrievedChunk:
    """검색된 문서 청크 (출처 메타데이터 포함)"""
    filename: str
    source: str
    content: str
    chunk_index: int | None = None
    page: int | None = None
    score: float = 0.0          # RRF 융합 점수
    dense_score: float | None = None  # 코사인 유사도 (dense 결과에만 존재)
    content_hash: str | None = None
    ingested_at: str | None = None


@dataclass
class RAGResponse:
    """
    RAG 응답

    Attributes:
        answer: LLM이 생성한 답변
        sources: 검색된 근거 청크 리스트 (백엔드가 조립한 출처)
        query: 원본 사용자 질문
    """
    answer: str
    sources: list[RetrievedChunk]
    query: str


def rrf_merge(result_lists: list[list], k: int = 60) -> list[tuple]:
    """
    Reciprocal Rank Fusion.

    Args:
        result_lists: 랭킹 리스트들 (각 원소는 .id 속성을 가진 객체)
        k: RRF 상수 (기본 60)

    Returns:
        (item, fused_score) 리스트 — 융합 점수 내림차순
    """
    scores: dict = {}
    items: dict = {}
    for results in result_lists:
        for rank, item in enumerate(results):
            scores[item.id] = scores.get(item.id, 0.0) + 1.0 / (k + rank + 1)
            items.setdefault(item.id, item)

    ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return [(items[item_id], score) for item_id, score in ranked]


class RAGChain:
    """
    하이브리드 검색 + 생성 파이프라인

    Args:
        embedder: 주입 가능한 임베더 (테스트용)
        client: 주입 가능한 Qdrant 클라이언트 (테스트용)
        llm: 주입 가능한 ollama.Client (테스트용)
    """

    def __init__(self, embedder=None, client: QdrantClient | None = None, llm=None):
        logger.info("RAGChain 초기화 중...")

        if embedder is None:
            from src.embeddings import BGEM3Embedder
            embedder = BGEM3Embedder()
        self.embedder = embedder

        self.client = client or QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        # timeout: Ollama가 응답 불능일 때 워커 스레드가 무한 대기하지 않도록 제한
        self.llm = llm or ollama.Client(
            host=settings.ollama_base_url,
            timeout=settings.query_timeout_seconds,
        )

        # 컬렉션(alias) 존재 확인 — 없으면 경고만 (ingest 안내)
        try:
            count = self.client.count(
                collection_name=settings.qdrant_collection_name, exact=True
            ).count
            logger.info(
                f"컬렉션 '{settings.qdrant_collection_name}' 연결됨 (포인트 수: {count})"
            )
        except Exception:
            logger.warning(
                f"컬렉션 '{settings.qdrant_collection_name}'이 없습니다. "
                f"'python main.py ingest'를 먼저 실행해주세요."
            )

        logger.info("RAGChain 초기화 완료")

    # ─────────────────────────────────────────────────
    # 검색
    # ─────────────────────────────────────────────────
    def search(self, query: str, k: int | None = None) -> list[RetrievedChunk]:
        """
        하이브리드 검색: dense(임계값 적용) + sparse → RRF 융합 → 상위 K개
        """
        if k is None:
            k = settings.top_k_results
        collection = settings.qdrant_collection_name
        candidates = settings.retrieval_candidates

        encoded = self.embedder.encode([query])
        dense_vec = encoded.dense[0]
        sparse_vec = encoded.sparse[0]

        dense_hits = self.client.query_points(
            collection_name=collection,
            query=dense_vec,
            using="dense",
            limit=candidates,
            score_threshold=settings.min_dense_score,
            with_payload=True,
        ).points

        sparse_hits = []
        if sparse_vec:
            sparse_hits = self.client.query_points(
                collection_name=collection,
                query=qdrant_models.SparseVector(
                    indices=list(sparse_vec.keys()),
                    values=list(sparse_vec.values()),
                ),
                using="sparse",
                limit=candidates,
                with_payload=True,
            ).points

        dense_scores = {hit.id: hit.score for hit in dense_hits}
        merged = rrf_merge([dense_hits, sparse_hits])

        chunks = []
        for point, fused_score in merged[:k]:
            payload = point.payload or {}
            chunks.append(RetrievedChunk(
                filename=payload.get("filename", "unknown"),
                source=payload.get("source", "unknown"),
                content=payload.get("text", ""),
                chunk_index=payload.get("chunk_index"),
                page=payload.get("page"),
                score=fused_score,
                dense_score=dense_scores.get(point.id),
                content_hash=payload.get("content_hash"),
                ingested_at=payload.get("ingested_at"),
            ))
        return chunks

    # ─────────────────────────────────────────────────
    # 생성
    # ─────────────────────────────────────────────────
    def _build_context(self, chunks: list[RetrievedChunk]) -> str:
        """검색 결과를 번호가 매겨진 컨텍스트 블록으로 조립합니다."""
        blocks = []
        for i, chunk in enumerate(chunks, start=1):
            locator = chunk.filename
            if chunk.page:
                locator += f", p.{chunk.page}"
            blocks.append(f"[{i}] ({locator})\n{chunk.content}")
        return "\n\n".join(blocks)

    def query(self, question: str) -> RAGResponse:
        """
        질문에 대한 답변을 생성합니다.

        근거 문서가 없으면 LLM을 호출하지 않고 즉시 "찾을 수 없음"을 반환합니다.
        LLM/DB 오류는 예외로 전파됩니다 — 호출자(API/봇)가 사용자에게
        일반화된 오류 메시지를 보여줄 책임을 가집니다.
        """
        chunks = self.search(question)
        logger.info(f"검색된 근거 청크: {len(chunks)}개")

        if not chunks:
            return RAGResponse(answer=NO_RESULT_ANSWER, sources=[], query=question)

        context = self._build_context(chunks)
        user_prompt = f"[Context]\n{context}\n\n[Question]\n{question}"

        response = self.llm.chat(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={
                "temperature": settings.ollama_temperature,
                "num_ctx": settings.ollama_num_ctx,
                "num_predict": settings.ollama_num_predict,
            },
        )
        answer = response["message"]["content"].strip()

        return RAGResponse(answer=answer, sources=chunks, query=question)

    # ─────────────────────────────────────────────────
    # 상태 확인
    # ─────────────────────────────────────────────────
    def health(self) -> dict:
        """
        실제 의존성(Qdrant, Ollama, 컬렉션, 모델)의 상태를 확인합니다.
        """
        status: dict = {
            "qdrant": False,
            "collection_points": None,
            "ollama": False,
            "model_available": False,
        }

        try:
            self.client.get_collections()
            status["qdrant"] = True
            status["collection_points"] = self.client.count(
                collection_name=settings.qdrant_collection_name, exact=True
            ).count
        except Exception as e:
            logger.warning(f"Qdrant 상태 확인 실패: {type(e).__name__}")

        try:
            listed = self.llm.list()
            status["ollama"] = True
            model_names = [m.model for m in listed.models]
            status["model_available"] = any(
                name == settings.ollama_model
                or name.split(":")[0] == settings.ollama_model
                for name in model_names
            )
        except Exception as e:
            logger.warning(f"Ollama 상태 확인 실패: {type(e).__name__}")

        status["healthy"] = bool(
            status["qdrant"]
            and status["ollama"]
            and status["collection_points"] is not None
        )
        return status


# ─────────────────────────────────────────────────
# 싱글톤 인스턴스 (지연 초기화)
# ─────────────────────────────────────────────────
_rag_chain_instance: RAGChain | None = None


def get_rag_chain() -> RAGChain:
    """
    RAGChain 싱글톤 인스턴스를 반환합니다.

    최초 호출 시 인스턴스를 생성하고, 이후 호출에서는
    기존 인스턴스를 재사용합니다.
    """
    global _rag_chain_instance

    if _rag_chain_instance is None:
        _rag_chain_instance = RAGChain()

    return _rag_chain_instance
