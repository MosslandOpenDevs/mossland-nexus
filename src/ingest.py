# ===================================================
# Moss Nexus - Data Ingestion Pipeline
# 문서 로드, 청킹, 임베딩 및 벡터 DB 저장
# ===================================================
"""
이 모듈은 RAG(검색 증강 생성) 시스템의 핵심인 데이터 수집 파이프라인을 구현합니다.

주요 기능:
1. 다양한 형식의 문서 로드 (PDF, MD, TXT, DOCX)
2. 문서를 적절한 크기로 청킹(분할)
3. 텍스트를 벡터로 임베딩 (MPS 가속 사용)
4. Qdrant 벡터 DB에 저장
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain.schema import Document
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from tqdm import tqdm
from loguru import logger

# 설정 모듈 임포트
from src.config import settings


# ─────────────────────────────────────────────────
# 로깅 설정
# ─────────────────────────────────────────────────
logger.remove()  # 기본 핸들러 제거
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)


class DocumentIngester:
    """
    문서 수집 및 벡터화 파이프라인 클래스

    이 클래스는 다음 단계를 처리합니다:
    1. 문서 로드 (PDF, MD, TXT)
    2. 텍스트 청킹 (분할)
    3. 임베딩 생성 (MPS 가속)
    4. Qdrant에 저장
    """

    def __init__(self):
        """
        DocumentIngester 초기화
        임베딩 모델과 Qdrant 클라이언트를 설정합니다.
        """
        logger.info("DocumentIngester 초기화 중...")

        # ─────────────────────────────────────────────────
        # 임베딩 모델 초기화 (MPS 가속 사용)
        # ─────────────────────────────────────────────────
        # Apple Silicon의 Metal Performance Shaders(MPS)를 활용하여
        # GPU 가속으로 임베딩을 생성합니다.
        logger.info(f"임베딩 모델 로드 중: {settings.embedding_model}")

        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={
                'device': 'mps',  # Apple Silicon GPU 가속
                'trust_remote_code': True
            },
            encode_kwargs={
                'normalize_embeddings': True,  # 정규화하여 코사인 유사도 최적화
                'batch_size': 32  # 배치 크기 설정
            }
        )
        logger.info("임베딩 모델 로드 완료!")

        # ─────────────────────────────────────────────────
        # 텍스트 분할기 초기화
        # ─────────────────────────────────────────────────
        # RecursiveCharacterTextSplitter는 의미 단위를 유지하면서
        # 문서를 적절한 크기로 분할합니다.
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,      # 청크 크기 (기본 800자)
            chunk_overlap=settings.chunk_overlap, # 중복 크기 (기본 100자)
            length_function=len,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],  # 분할 우선순위
            is_separator_regex=False
        )

        # ─────────────────────────────────────────────────
        # Qdrant 클라이언트 초기화
        # ─────────────────────────────────────────────────
        self.qdrant_client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port
        )
        logger.info(f"Qdrant 연결 완료: {settings.qdrant_url}")

    def _load_documents(self) -> List[Document]:
        """
        data/ 디렉토리에서 모든 문서를 로드합니다.

        지원 형식:
        - PDF (.pdf)
        - Markdown (.md)
        - Text (.txt)

        Returns:
            List[Document]: 로드된 문서 리스트
        """
        documents = []
        data_path = settings.data_path

        if not data_path.exists():
            logger.warning(f"데이터 디렉토리가 존재하지 않습니다: {data_path}")
            data_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"데이터 디렉토리 생성됨: {data_path}")
            return documents

        logger.info(f"문서 로드 시작: {data_path}")

        # ─────────────────────────────────────────────────
        # PDF 파일 로드
        # ─────────────────────────────────────────────────
        pdf_loader = DirectoryLoader(
            str(data_path),
            glob="**/*.pdf",
            loader_cls=PyPDFLoader,
            show_progress=True,
            use_multithreading=True  # 멀티스레딩으로 성능 향상
        )
        try:
            pdf_docs = pdf_loader.load()
            documents.extend(pdf_docs)
            logger.info(f"PDF 문서 {len(pdf_docs)}개 로드됨")
        except Exception as e:
            logger.warning(f"PDF 로드 중 오류: {e}")

        # ─────────────────────────────────────────────────
        # Markdown 파일 로드
        # ─────────────────────────────────────────────────
        md_loader = DirectoryLoader(
            str(data_path),
            glob="**/*.md",
            loader_cls=UnstructuredMarkdownLoader,
            show_progress=True
        )
        try:
            md_docs = md_loader.load()
            documents.extend(md_docs)
            logger.info(f"Markdown 문서 {len(md_docs)}개 로드됨")
        except Exception as e:
            logger.warning(f"Markdown 로드 중 오류: {e}")

        # ─────────────────────────────────────────────────
        # Text 파일 로드
        # ─────────────────────────────────────────────────
        txt_loader = DirectoryLoader(
            str(data_path),
            glob="**/*.txt",
            loader_cls=TextLoader,
            show_progress=True,
            loader_kwargs={'encoding': 'utf-8'}
        )
        try:
            txt_docs = txt_loader.load()
            documents.extend(txt_docs)
            logger.info(f"Text 문서 {len(txt_docs)}개 로드됨")
        except Exception as e:
            logger.warning(f"Text 로드 중 오류: {e}")

        logger.info(f"총 {len(documents)}개 문서 로드 완료")
        return documents

    def _split_documents(self, documents: List[Document]) -> List[Document]:
        """
        문서를 청크(chunk)로 분할합니다.

        청킹은 RAG 시스템의 핵심으로, 적절한 크기의 텍스트 조각을
        만들어 검색 정확도를 높입니다.

        Args:
            documents: 원본 문서 리스트

        Returns:
            List[Document]: 분할된 청크 리스트
        """
        logger.info("문서 청킹(분할) 시작...")

        chunks = self.text_splitter.split_documents(documents)

        # 각 청크에 메타데이터 추가 (출처 추적용)
        for i, chunk in enumerate(chunks):
            # 원본 파일명 추출
            source = chunk.metadata.get('source', 'unknown')
            filename = Path(source).name if source else 'unknown'
            chunk.metadata['filename'] = filename
            chunk.metadata['chunk_id'] = i

        logger.info(f"총 {len(chunks)}개 청크 생성 완료")
        return chunks

    def _create_collection(self):
        """
        Qdrant에 벡터 컬렉션을 생성합니다.
        이미 존재하는 경우 기존 컬렉션을 삭제하고 새로 생성합니다.
        """
        collection_name = settings.qdrant_collection_name

        # 기존 컬렉션 삭제 (있는 경우)
        try:
            self.qdrant_client.delete_collection(collection_name)
            logger.info(f"기존 컬렉션 삭제: {collection_name}")
        except Exception:
            pass  # 컬렉션이 없으면 무시

        # 임베딩 차원 확인을 위한 테스트
        test_embedding = self.embeddings.embed_query("test")
        embedding_dim = len(test_embedding)
        logger.info(f"임베딩 차원: {embedding_dim}")

        # 새 컬렉션 생성
        self.qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=embedding_dim,
                distance=qdrant_models.Distance.COSINE  # 코사인 유사도 사용
            )
        )
        logger.info(f"새 컬렉션 생성 완료: {collection_name}")

    def ingest(self, recreate_collection: bool = True) -> int:
        """
        전체 데이터 수집 파이프라인을 실행합니다.

        파이프라인 순서:
        1. 문서 로드
        2. 문서 청킹
        3. (선택적) 컬렉션 재생성
        4. 벡터 DB에 저장

        Args:
            recreate_collection: True면 컬렉션을 새로 생성 (기존 데이터 삭제)

        Returns:
            int: 저장된 청크 수
        """
        logger.info("=" * 50)
        logger.info("Moss Nexus 데이터 수집 파이프라인 시작")
        logger.info("=" * 50)

        # Step 1: 문서 로드
        documents = self._load_documents()
        if not documents:
            logger.warning("로드된 문서가 없습니다. data/ 폴더에 문서를 추가해주세요.")
            return 0

        # Step 2: 문서 청킹
        chunks = self._split_documents(documents)
        if not chunks:
            logger.warning("생성된 청크가 없습니다.")
            return 0

        # Step 3: 컬렉션 생성 (필요시)
        if recreate_collection:
            self._create_collection()

        # Step 4: Qdrant에 저장
        logger.info("벡터 DB에 데이터 저장 중...")

        # LangChain의 Qdrant 래퍼를 사용하여 저장
        vectorstore = Qdrant.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
            force_recreate=False  # 이미 위에서 생성했으므로 False
        )

        logger.info("=" * 50)
        logger.info(f"데이터 수집 완료! 총 {len(chunks)}개 청크 저장됨")
        logger.info("=" * 50)

        return len(chunks)


def run_ingestion():
    """
    데이터 수집 파이프라인을 실행하는 진입점 함수
    """
    try:
        ingester = DocumentIngester()
        num_chunks = ingester.ingest(recreate_collection=True)

        if num_chunks > 0:
            print(f"\n성공적으로 {num_chunks}개의 청크가 벡터 DB에 저장되었습니다.")
            print("이제 봇을 실행하여 질문할 수 있습니다!")
        else:
            print("\n저장된 데이터가 없습니다.")
            print(f"'{settings.data_dir}' 폴더에 PDF, MD, TXT 파일을 추가해주세요.")

    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}")
        raise


# ─────────────────────────────────────────────────
# 직접 실행 시 데이터 수집 파이프라인 실행
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    run_ingestion()
