# ===================================================
# Moss Nexus - Configuration Module
# 환경 변수 및 설정 관리
# ===================================================
"""
Pydantic Settings를 사용한 타입 안전한 설정 관리
.env 파일에서 설정을 로드하고 검증합니다.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스
    환경 변수 또는 .env 파일에서 설정을 로드합니다.
    """

    # ─────────────────────────────────────────────────
    # Discord 설정
    # ─────────────────────────────────────────────────
    discord_bot_token: str = Field(
        default="",
        description="Discord 봇 토큰"
    )
    discord_guild_ids: str = Field(
        default="",
        description="봇을 허용할 Discord 서버(guild) ID 목록 (쉼표 구분). 비우면 모든 서버 허용"
    )
    discord_channel_ids: str = Field(
        default="",
        description="봇을 허용할 채널 ID 목록 (쉼표 구분). 비우면 모든 채널 허용"
    )
    discord_cooldown_seconds: int = Field(
        default=30,
        description="사용자별 질의 쿨다운 (초) — /ask, /search 공통"
    )

    # ─────────────────────────────────────────────────
    # Ollama 설정
    # ─────────────────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama 서버 URL"
    )
    ollama_model: str = Field(
        default="qwen3.5:9b",
        description="사용할 Ollama 모델명"
    )
    ollama_num_ctx: int = Field(
        default=8192,
        description="LLM 컨텍스트 윈도우 크기 (토큰)"
    )
    ollama_num_predict: int = Field(
        default=2048,
        description="LLM 최대 생성 토큰 수"
    )
    ollama_temperature: float = Field(
        default=0.1,
        description="LLM temperature (낮을수록 일관된 답변)"
    )

    # ─────────────────────────────────────────────────
    # Qdrant 설정
    # ─────────────────────────────────────────────────
    qdrant_host: str = Field(
        default="localhost",
        description="Qdrant 서버 호스트"
    )
    qdrant_port: int = Field(
        default=6333,
        description="Qdrant 서버 포트"
    )
    qdrant_collection_name: str = Field(
        default="moss_knowledge",
        description="Qdrant 컬렉션 alias 이름 (실제 컬렉션은 alias 뒤에서 원자적으로 교체됨)"
    )

    # ─────────────────────────────────────────────────
    # Embedding 모델 설정
    # ─────────────────────────────────────────────────
    embedding_model: str = Field(
        default="BAAI/bge-m3",
        description="HuggingFace 임베딩 모델명 (dense+sparse 지원)"
    )
    embedding_device: str = Field(
        default="auto",
        description="임베딩 디바이스: auto | cuda | mps | cpu"
    )
    embedding_batch_size: int = Field(
        default=32,
        description="임베딩 배치 크기"
    )

    # ─────────────────────────────────────────────────
    # 데이터 디렉토리 설정
    # ─────────────────────────────────────────────────
    data_dir: str = Field(
        default="./data",
        description="문서 파일이 저장된 디렉토리 경로"
    )

    # ─────────────────────────────────────────────────
    # 청킹(Chunking) 설정
    # ─────────────────────────────────────────────────
    chunk_size: int = Field(
        default=800,
        description="문서 청크 크기 (문자 수)"
    )
    chunk_overlap: int = Field(
        default=100,
        description="청크 간 중복 크기 (문자 수)"
    )

    # ─────────────────────────────────────────────────
    # 검색 설정
    # ─────────────────────────────────────────────────
    top_k_results: int = Field(
        default=4,
        description="답변 근거로 사용할 최종 문서 수"
    )
    retrieval_candidates: int = Field(
        default=12,
        description="dense/sparse 각각에서 가져올 후보 수 (RRF 융합 전)"
    )
    min_dense_score: float = Field(
        default=0.35,
        description="dense 검색 최소 코사인 유사도 (이 값 미만은 근거로 사용하지 않음)"
    )

    # ─────────────────────────────────────────────────
    # FastAPI 설정
    # ─────────────────────────────────────────────────
    api_host: str = Field(
        default="127.0.0.1",
        description="API 서버 바인드 주소 (외부 공개는 reverse proxy/TLS/Tailscale 뒤에서만)"
    )
    api_port: int = Field(
        default=8000,
        description="API 서버 포트"
    )
    max_concurrent_queries: int = Field(
        default=2,
        description="동시에 처리할 최대 질의 수 (로컬 LLM 보호)"
    )
    queue_timeout_seconds: int = Field(
        default=10,
        description="질의 슬롯 대기 제한 시간 (초). 초과 시 429 응답"
    )
    query_timeout_seconds: int = Field(
        default=180,
        description="질의 1건의 최대 처리 시간 (초)"
    )

    # ─────────────────────────────────────────────────
    # 로깅 설정
    # ─────────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="로그 레벨"
    )

    # ─────────────────────────────────────────────────
    # Pydantic Settings 설정
    # ─────────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def data_path(self) -> Path:
        """데이터 디렉토리의 Path 객체를 반환합니다."""
        return Path(self.data_dir).resolve()

    @property
    def qdrant_url(self) -> str:
        """Qdrant 연결 URL을 반환합니다."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def discord_guild_id_list(self) -> list[int]:
        """허용된 guild ID 목록을 반환합니다 (빈 목록 = 제한 없음)."""
        return _parse_id_list(self.discord_guild_ids)

    @property
    def discord_channel_id_list(self) -> list[int]:
        """허용된 채널 ID 목록을 반환합니다 (빈 목록 = 제한 없음)."""
        return _parse_id_list(self.discord_channel_ids)


def _parse_id_list(raw: str) -> list[int]:
    """쉼표로 구분된 ID 문자열을 int 리스트로 변환합니다."""
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


# 전역 설정 인스턴스 (싱글톤 패턴)
settings = Settings()


# ─────────────────────────────────────────────────
# 설정 확인용 함수
# ─────────────────────────────────────────────────
def print_settings():
    """현재 설정을 출력합니다 (디버깅용)."""
    print("=" * 50)
    print("Moss Nexus Configuration")
    print("=" * 50)
    print(f"Ollama URL: {settings.ollama_base_url}")
    print(f"Ollama Model: {settings.ollama_model}")
    print(f"Qdrant URL: {settings.qdrant_url}")
    print(f"Collection (alias): {settings.qdrant_collection_name}")
    print(f"Embedding Model: {settings.embedding_model}")
    print(f"Embedding Device: {settings.embedding_device}")
    print(f"Data Directory: {settings.data_path}")
    print(f"Chunk Size: {settings.chunk_size}")
    print(f"Top K Results: {settings.top_k_results}")
    print(f"Min Dense Score: {settings.min_dense_score}")
    print(f"API Bind: {settings.api_host}:{settings.api_port}")
    print("=" * 50)


if __name__ == "__main__":
    print_settings()
