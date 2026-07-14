# ===================================================
# Moss Nexus - Data Ingestion Pipeline
# 문서 로드, 청킹, 임베딩 및 벡터 DB 저장
# ===================================================
"""
데이터 수집 파이프라인.

안전한 재색인을 위해 다음 순서로 동작합니다:

1. 문서 로드 (파일 단위 실패 추적 — 기본은 fail-closed)
2. 청킹 + 메타데이터(해시, 시각) 부여
3. staging 컬렉션 생성 후 전체 색인
4. 포인트 수 검증
5. Qdrant alias를 staging 컬렉션으로 **원자적 전환**
6. 직전 컬렉션 1개는 롤백용으로 보존, 그 이전 것은 삭제

기존 인덱스는 새 인덱스가 완전히 준비되어 검증을 통과하기 전까지
절대 삭제되지 않습니다.
"""

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client import models as qdrant_models
from tqdm import tqdm

from src.config import settings
from src.loaders import LoadError, load_documents
from src.logging_setup import setup_logging
from src.splitter import split_text

setup_logging()

UPSERT_BATCH_SIZE = 64
EMBED_GROUP_SIZE = 256


class IngestError(Exception):
    """색인 파이프라인 실패 (기존 인덱스는 보존됨)"""


@dataclass
class IngestReport:
    """색인 결과 리포트"""
    num_files: int = 0
    num_chunks: int = 0
    new_collection: str = ""
    previous_collection: str | None = None
    deleted_collections: list[str] = field(default_factory=list)
    load_errors: list[LoadError] = field(default_factory=list)


def _chunk_point_id(source: str, page: int | None, index: int, content_hash: str) -> str:
    """(파일, 페이지, 청크 순번, 내용 해시)로부터 결정적 포인트 ID를 만듭니다."""
    key = f"moss-nexus:{source}:{page}:{index}:{content_hash}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


class DocumentIngester:
    """
    문서 수집 및 벡터화 파이프라인

    Args:
        embedder: 주입 가능한 임베더 (테스트용). 없으면 BGE-M3를 로드합니다.
        client: 주입 가능한 Qdrant 클라이언트 (테스트용).
    """

    def __init__(self, embedder=None, client: QdrantClient | None = None):
        if embedder is None:
            from src.embeddings import BGEM3Embedder
            embedder = BGEM3Embedder()
        self.embedder = embedder

        self.client = client or QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        logger.info(f"Qdrant 연결: {settings.qdrant_url}")

    # ─────────────────────────────────────────────────
    # 청킹
    # ─────────────────────────────────────────────────
    def _build_chunks(self, documents) -> list[dict]:
        """문서를 청크 payload 리스트로 변환합니다."""
        ingested_at = datetime.now(UTC).isoformat()
        chunks: list[dict] = []

        for doc in documents:
            pieces = split_text(
                doc.text,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            for i, piece in enumerate(pieces):
                content_hash = hashlib.sha256(piece.encode("utf-8")).hexdigest()
                chunks.append({
                    "id": _chunk_point_id(doc.source, doc.page, i, content_hash),
                    "text": piece,
                    "filename": doc.filename,
                    "source": doc.source,
                    "page": doc.page,
                    "chunk_index": i,
                    "content_hash": content_hash,
                    "file_hash": doc.file_hash,
                    "ingested_at": ingested_at,
                })

        logger.info(f"총 {len(chunks)}개 청크 생성")
        return chunks

    # ─────────────────────────────────────────────────
    # staging 컬렉션 색인
    # ─────────────────────────────────────────────────
    def _index_to_staging(self, chunks: list[dict]) -> str:
        """staging 컬렉션을 만들고 전체 청크를 색인한 뒤 검증합니다."""
        alias = settings.qdrant_collection_name
        staging = f"{alias}__{time.strftime('%Y%m%d%H%M%S')}"

        # 임베딩 (dense + sparse)
        logger.info("임베딩 생성 중...")
        dense_all: list[list[float]] = []
        sparse_all: list[dict[int, float]] = []
        texts = [c["text"] for c in chunks]
        for start in tqdm(range(0, len(texts), EMBED_GROUP_SIZE), desc="embedding"):
            batch = self.embedder.encode(texts[start:start + EMBED_GROUP_SIZE])
            dense_all.extend(batch.dense)
            sparse_all.extend(batch.sparse)

        dim = len(dense_all[0])
        logger.info(f"임베딩 차원: {dim}, staging 컬렉션: {staging}")

        self.client.create_collection(
            collection_name=staging,
            vectors_config={
                "dense": qdrant_models.VectorParams(
                    size=dim,
                    distance=qdrant_models.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "sparse": qdrant_models.SparseVectorParams(),
            },
        )

        try:
            for start in tqdm(range(0, len(chunks), UPSERT_BATCH_SIZE), desc="upsert"):
                batch = chunks[start:start + UPSERT_BATCH_SIZE]
                points = []
                for offset, chunk in enumerate(batch):
                    idx = start + offset
                    sparse = sparse_all[idx]
                    payload = {k: v for k, v in chunk.items() if k != "id"}
                    points.append(qdrant_models.PointStruct(
                        id=chunk["id"],
                        vector={
                            "dense": dense_all[idx],
                            "sparse": qdrant_models.SparseVector(
                                indices=list(sparse.keys()),
                                values=list(sparse.values()),
                            ),
                        },
                        payload=payload,
                    ))
                self.client.upsert(collection_name=staging, points=points, wait=True)

            # 검증: 저장된 포인트 수가 청크 수와 일치해야 함
            stored = self.client.count(collection_name=staging, exact=True).count
            if stored != len(chunks):
                raise IngestError(
                    f"검증 실패: 청크 {len(chunks)}개 중 {stored}개만 저장됨"
                )
        except Exception:
            logger.error(f"staging 색인 실패 — {staging} 삭제 후 중단 (기존 인덱스는 무손상)")
            self.client.delete_collection(staging)
            raise

        logger.info(f"staging 색인 및 검증 완료: {stored}개 포인트")
        return staging

    # ─────────────────────────────────────────────────
    # alias 원자적 전환
    # ─────────────────────────────────────────────────
    def _swap_alias(self, staging: str) -> tuple[str | None, list[str]]:
        """alias를 staging 컬렉션으로 전환하고 오래된 컬렉션을 정리합니다."""
        alias = settings.qdrant_collection_name

        existing = {c.name for c in self.client.get_collections().collections}
        alias_targets = [
            a.collection_name
            for a in self.client.get_aliases().aliases
            if a.alias_name == alias
        ]
        previous = alias_targets[0] if alias_targets else None

        # v1.x 레이아웃 마이그레이션: alias와 같은 이름의 실제 컬렉션이 있으면
        # alias를 만들 수 없으므로 제거 (staging 검증 통과 후에만 도달)
        if alias in existing:
            logger.warning(f"구버전 레이아웃 감지 — 실제 컬렉션 '{alias}'을 삭제하고 alias로 대체")
            self.client.delete_collection(alias)
            existing.discard(alias)

        operations: list = []
        if previous:
            operations.append(qdrant_models.DeleteAliasOperation(
                delete_alias=qdrant_models.DeleteAlias(alias_name=alias)
            ))
        operations.append(qdrant_models.CreateAliasOperation(
            create_alias=qdrant_models.CreateAlias(
                collection_name=staging,
                alias_name=alias,
            )
        ))
        self.client.update_collection_aliases(change_aliases_operations=operations)
        logger.info(f"alias '{alias}' → '{staging}' 전환 완료")

        # 롤백용으로 직전 컬렉션 1개만 남기고 그 이전 staging 컬렉션 삭제
        deleted = []
        for name in existing:
            if name.startswith(f"{alias}__") and name not in (staging, previous):
                self.client.delete_collection(name)
                deleted.append(name)
                logger.info(f"오래된 컬렉션 삭제: {name}")

        return previous, deleted

    # ─────────────────────────────────────────────────
    # 전체 파이프라인
    # ─────────────────────────────────────────────────
    def ingest(self, allow_partial: bool = False) -> IngestReport:
        """
        전체 색인 파이프라인을 실행합니다.

        Args:
            allow_partial: True면 일부 파일 로드 실패를 허용하고 진행합니다.
                           기본값(False)은 fail-closed — 실패 파일이 있으면
                           기존 인덱스를 건드리지 않고 중단합니다.
        """
        logger.info("=" * 50)
        logger.info("Moss Nexus 데이터 수집 파이프라인 시작")
        logger.info("=" * 50)

        documents, errors = load_documents(settings.data_path)

        if errors:
            for err in errors:
                logger.error(f"  로드 실패: {err.source} — {err.error}")
            if not allow_partial:
                raise IngestError(
                    f"{len(errors)}개 파일 로드 실패. 파일을 수정하거나 "
                    f"--allow-partial 옵션으로 부분 색인을 허용하세요. "
                    f"기존 인덱스는 변경되지 않았습니다."
                )
            logger.warning(f"{len(errors)}개 파일을 제외하고 부분 색인을 진행합니다")

        if not documents:
            logger.warning("로드된 문서가 없습니다. 기존 인덱스는 변경되지 않았습니다.")
            return IngestReport(load_errors=errors)

        chunks = self._build_chunks(documents)
        if not chunks:
            logger.warning("생성된 청크가 없습니다. 기존 인덱스는 변경되지 않았습니다.")
            return IngestReport(load_errors=errors)

        staging = self._index_to_staging(chunks)
        previous, deleted = self._swap_alias(staging)

        num_files = len({doc.source for doc in documents})
        logger.info("=" * 50)
        logger.info(f"색인 완료: 파일 {num_files}개, 청크 {len(chunks)}개 → '{staging}'")
        if previous:
            logger.info(f"롤백용 이전 컬렉션 보존: {previous}")
        logger.info("=" * 50)

        return IngestReport(
            num_files=num_files,
            num_chunks=len(chunks),
            new_collection=staging,
            previous_collection=previous,
            deleted_collections=deleted,
            load_errors=errors,
        )


def run_ingestion(allow_partial: bool = False):
    """데이터 수집 파이프라인 진입점"""
    try:
        ingester = DocumentIngester()
        report = ingester.ingest(allow_partial=allow_partial)

        if report.num_chunks > 0:
            print(f"\n성공: {report.num_chunks}개 청크가 "
                  f"'{report.new_collection}'에 색인되었습니다.")
            if report.previous_collection:
                print(f"이전 컬렉션은 롤백용으로 보존됩니다: {report.previous_collection}")
        else:
            print("\n색인된 데이터가 없습니다.")
            print(f"'{settings.data_dir}' 폴더에 PDF, MD, TXT, DOCX 파일을 추가해주세요.")

    except IngestError as e:
        logger.error(f"색인 중단: {e}")
        raise SystemExit(1) from None
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    run_ingestion()
