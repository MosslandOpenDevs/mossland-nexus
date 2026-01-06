# ===================================================
# Moss Nexus - Configuration Module
# 환경 변수 및 설정 관리
# ===================================================
"""
Pydantic Settings를 사용한 타입 안전한 설정 관리
.env 파일에서 설정을 로드하고 검증합니다.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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

    # ─────────────────────────────────────────────────
    # Ollama 설정
    # ─────────────────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama 서버 URL"
    )
    ollama_model: str = Field(
        default="llama3.3:70b",
        description="사용할 Ollama 모델명"
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
        description="Qdrant 컬렉션 이름"
    )

    # ─────────────────────────────────────────────────
    # Embedding 모델 설정
    # ─────────────────────────────────────────────────
    embedding_model: str = Field(
        default="BAAI/bge-m3",
        description="HuggingFace 임베딩 모델명"
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
        description="검색 결과 상위 K개"
    )

    # ─────────────────────────────────────────────────
    # FastAPI 설정
    # ─────────────────────────────────────────────────
    api_host: str = Field(
        default="0.0.0.0",
        description="API 서버 호스트"
    )
    api_port: int = Field(
        default=8000,
        description="API 서버 포트"
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
    print(f"Collection: {settings.qdrant_collection_name}")
    print(f"Embedding Model: {settings.embedding_model}")
    print(f"Data Directory: {settings.data_path}")
    print(f"Chunk Size: {settings.chunk_size}")
    print(f"Top K Results: {settings.top_k_results}")
    print("=" * 50)


if __name__ == "__main__":
    print_settings()
