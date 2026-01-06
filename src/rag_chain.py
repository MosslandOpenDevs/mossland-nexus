# ===================================================
# Moss Nexus - RAG Chain Module
# 검색 증강 생성(Retrieval-Augmented Generation) 체인
# ===================================================
"""
이 모듈은 RAG 시스템의 핵심 로직을 구현합니다.

RAG 파이프라인:
1. 사용자 질문을 벡터로 변환
2. Qdrant에서 유사한 문서 검색
3. 검색된 문서를 컨텍스트로 LLM에 전달
4. LLM이 컨텍스트 기반 답변 생성
"""

import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain.schema import Document
from qdrant_client import QdrantClient
from loguru import logger

from src.config import settings


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
# 시스템 프롬프트 템플릿
# ─────────────────────────────────────────────────
SYSTEM_PROMPT_TEMPLATE = """당신은 모스랜드(Mossland)의 커뮤니티 매니저 'Moss Nexus'입니다.
아래의 [Context]를 바탕으로 사용자의 질문에 친절하고 명확하게 답변하세요.

[Rules]
1. 반드시 [Context]에 있는 내용만 사실로 간주하고 답변하세요.
2. [Context]에 없는 내용은 "죄송하지만, 제공된 공식 문서에서 해당 정보를 찾을 수 없습니다."라고 답하세요. 추측하지 마세요.
3. 답변 끝에는 반드시 참조한 문서의 파일명이나 출처를 [Source: 파일명] 형식으로 남기세요.
4. 한국어로 답변하세요.

[Context]
{context}

[Question]
{question}

[Answer]
"""


@dataclass
class RAGResponse:
    """
    RAG 응답 데이터 클래스

    Attributes:
        answer: LLM이 생성한 답변
        source_documents: 검색된 참조 문서 리스트
        query: 원본 사용자 질문
    """
    answer: str
    source_documents: List[Document]
    query: str


class RAGChain:
    """
    RAG(검색 증강 생성) 체인 클래스

    이 클래스는 다음 기능을 제공합니다:
    1. Qdrant 벡터 DB에서 관련 문서 검색
    2. Ollama LLM을 사용한 답변 생성
    3. 출처 정보와 함께 응답 반환
    """

    def __init__(self):
        """
        RAGChain 초기화
        임베딩 모델, 벡터 스토어, LLM을 설정합니다.
        """
        logger.info("RAGChain 초기화 중...")

        # ─────────────────────────────────────────────────
        # 임베딩 모델 초기화 (MPS 가속)
        # ─────────────────────────────────────────────────
        logger.info(f"임베딩 모델 로드: {settings.embedding_model}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={
                'device': 'mps',  # Apple Silicon GPU 가속
                'trust_remote_code': True
            },
            encode_kwargs={
                'normalize_embeddings': True
            }
        )

        # ─────────────────────────────────────────────────
        # Qdrant 벡터 스토어 연결
        # ─────────────────────────────────────────────────
        logger.info(f"Qdrant 연결: {settings.qdrant_url}")
        self.qdrant_client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port
        )

        # 컬렉션 존재 확인
        try:
            collection_info = self.qdrant_client.get_collection(
                settings.qdrant_collection_name
            )
            logger.info(f"컬렉션 '{settings.qdrant_collection_name}' 연결됨 "
                       f"(포인트 수: {collection_info.points_count})")
        except Exception as e:
            logger.warning(f"컬렉션이 존재하지 않습니다. ingest.py를 먼저 실행해주세요: {e}")

        # LangChain Qdrant 래퍼 초기화
        self.vectorstore = Qdrant(
            client=self.qdrant_client,
            collection_name=settings.qdrant_collection_name,
            embeddings=self.embeddings
        )

        # ─────────────────────────────────────────────────
        # Retriever 설정
        # ─────────────────────────────────────────────────
        # 유사도 상위 K개 문서를 검색하는 Retriever
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": settings.top_k_results  # 기본 4개
            }
        )

        # ─────────────────────────────────────────────────
        # Ollama LLM 초기화
        # ─────────────────────────────────────────────────
        logger.info(f"Ollama LLM 초기화: {settings.ollama_model}")
        self.llm = Ollama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.1,  # 낮은 temperature로 일관된 답변 생성
            num_ctx=8192,     # 컨텍스트 윈도우 크기
            num_predict=2048,  # 최대 생성 토큰 수
        )

        # ─────────────────────────────────────────────────
        # 프롬프트 템플릿 설정
        # ─────────────────────────────────────────────────
        self.prompt = PromptTemplate(
            template=SYSTEM_PROMPT_TEMPLATE,
            input_variables=["context", "question"]
        )

        # ─────────────────────────────────────────────────
        # RetrievalQA 체인 구성
        # ─────────────────────────────────────────────────
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",  # 모든 문서를 하나의 프롬프트에 넣기
            retriever=self.retriever,
            return_source_documents=True,  # 출처 문서 반환
            chain_type_kwargs={
                "prompt": self.prompt
            }
        )

        logger.info("RAGChain 초기화 완료!")

    def _format_sources(self, documents: List[Document]) -> str:
        """
        검색된 문서들의 출처 정보를 포맷팅합니다.

        Args:
            documents: 검색된 문서 리스트

        Returns:
            str: 포맷팅된 출처 문자열
        """
        if not documents:
            return ""

        sources = set()
        for doc in documents:
            filename = doc.metadata.get('filename', '')
            if filename:
                sources.add(filename)

        if sources:
            return "\n\n[참조 문서: " + ", ".join(sorted(sources)) + "]"
        return ""

    async def aquery(self, question: str) -> RAGResponse:
        """
        비동기 질문 처리 메서드

        Discord 봇에서 비동기로 호출하기 위한 래퍼 메서드입니다.

        Args:
            question: 사용자 질문

        Returns:
            RAGResponse: 답변, 출처 문서, 원본 질문을 포함한 응답
        """
        return self.query(question)

    def query(self, question: str) -> RAGResponse:
        """
        질문에 대한 답변을 생성합니다.

        RAG 파이프라인:
        1. 질문을 벡터로 변환
        2. Qdrant에서 유사 문서 검색
        3. 검색된 문서를 컨텍스트로 LLM에 전달
        4. LLM이 답변 생성

        Args:
            question: 사용자 질문

        Returns:
            RAGResponse: 답변, 출처 문서, 원본 질문을 포함한 응답
        """
        logger.info(f"질문 수신: {question[:50]}...")

        try:
            # RetrievalQA 체인 실행
            result = self.qa_chain.invoke({"query": question})

            answer = result.get("result", "답변을 생성할 수 없습니다.")
            source_documents = result.get("source_documents", [])

            # 로그에 검색된 문서 정보 출력
            logger.info(f"검색된 문서 수: {len(source_documents)}")
            for i, doc in enumerate(source_documents):
                filename = doc.metadata.get('filename', 'unknown')
                logger.debug(f"  [{i+1}] {filename}")

            return RAGResponse(
                answer=answer,
                source_documents=source_documents,
                query=question
            )

        except Exception as e:
            logger.error(f"질문 처리 중 오류: {e}")
            return RAGResponse(
                answer=f"죄송합니다. 질문 처리 중 오류가 발생했습니다: {str(e)}",
                source_documents=[],
                query=question
            )

    def search_documents(self, query: str, k: int = None) -> List[Document]:
        """
        질문과 관련된 문서를 검색합니다 (답변 생성 없이).

        디버깅이나 문서 검색 확인용으로 사용합니다.

        Args:
            query: 검색 쿼리
            k: 반환할 문서 수 (기본값: settings.top_k_results)

        Returns:
            List[Document]: 검색된 문서 리스트
        """
        if k is None:
            k = settings.top_k_results

        documents = self.vectorstore.similarity_search(query, k=k)
        return documents


# ─────────────────────────────────────────────────
# 싱글톤 인스턴스 (지연 초기화)
# ─────────────────────────────────────────────────
_rag_chain_instance: Optional[RAGChain] = None


def get_rag_chain() -> RAGChain:
    """
    RAGChain 싱글톤 인스턴스를 반환합니다.

    최초 호출 시 인스턴스를 생성하고, 이후 호출에서는
    기존 인스턴스를 재사용합니다.

    Returns:
        RAGChain: RAG 체인 인스턴스
    """
    global _rag_chain_instance

    if _rag_chain_instance is None:
        _rag_chain_instance = RAGChain()

    return _rag_chain_instance


# ─────────────────────────────────────────────────
# 테스트용 메인 함수
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    # RAG 체인 초기화
    rag = get_rag_chain()

    # 테스트 질문
    test_questions = [
        "모스랜드는 어떤 프로젝트인가요?",
        "MOC 토큰의 총 발행량은 얼마인가요?",
    ]

    for question in test_questions:
        print(f"\n{'='*50}")
        print(f"질문: {question}")
        print("="*50)

        response = rag.query(question)
        print(f"\n답변:\n{response.answer}")

        if response.source_documents:
            print(f"\n참조 문서:")
            for doc in response.source_documents:
                print(f"  - {doc.metadata.get('filename', 'unknown')}")
