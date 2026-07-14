# ===================================================
# Moss Nexus - Embedding Module
# BGE-M3 dense + sparse 임베딩 (FlagEmbedding)
# ===================================================
"""
BAAI/bge-m3 모델로 dense(의미)와 sparse(어휘) 벡터를 함께 생성합니다.

- dense: 코사인 유사도 기반 의미 검색
- sparse: 토큰 가중치 기반 어휘 검색 (컨트랙트 주소·고유명사 같은
  정확 매칭에 강함) — Qdrant sparse vector로 저장
- 디바이스는 cuda → mps → cpu 순으로 자동 선택
"""

from dataclasses import dataclass

from loguru import logger

from src.config import settings


def detect_device(preference: str = "auto") -> str:
    """사용 가능한 최적 디바이스를 반환합니다."""
    if preference != "auto":
        return preference

    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@dataclass
class EmbeddingBatch:
    """임베딩 결과 배치"""
    dense: list[list[float]]
    sparse: list[dict[int, float]]  # {token_id: weight}


class BGEM3Embedder:
    """
    BGE-M3 임베딩 래퍼

    FlagEmbedding은 임포트가 무겁기 때문에 인스턴스 생성 시점에 지연 로드합니다.
    최초 실행 시 Hugging Face에서 모델(~2.3GB)을 다운로드합니다.
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
    ):
        self.model_name = model_name or settings.embedding_model
        self.device = detect_device(device or settings.embedding_device)
        self.batch_size = batch_size or settings.embedding_batch_size

        logger.info(f"임베딩 모델 로드: {self.model_name} (device={self.device})")

        from FlagEmbedding import BGEM3FlagModel

        self.model = BGEM3FlagModel(
            self.model_name,
            devices=self.device,
            use_fp16=(self.device != "cpu"),
        )
        logger.info("임베딩 모델 로드 완료")

    def encode(self, texts: list[str]) -> EmbeddingBatch:
        """텍스트 리스트를 dense + sparse 벡터로 인코딩합니다."""
        output = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            max_length=8192,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = [vec.tolist() for vec in output["dense_vecs"]]
        sparse = [
            {int(token_id): float(weight) for token_id, weight in weights.items()}
            for weights in output["lexical_weights"]
        ]
        return EmbeddingBatch(dense=dense, sparse=sparse)

    @property
    def dense_dim(self) -> int:
        """dense 벡터 차원 (bge-m3: 1024)"""
        return len(self.encode(["dimension probe"]).dense[0])
