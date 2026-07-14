# ===================================================
# Moss Nexus - Logging Setup
# 중앙화된 로깅 설정 (모듈별 재설정 금지)
# ===================================================
"""
loguru 설정을 한 곳에서 관리합니다.

- 엔트리포인트(main.py 등)가 setup_logging(level)을 명시적으로 호출하면 그 레벨이 우선합니다.
- 각 모듈은 setup_logging()을 인자 없이 호출해도 이미 설정된 레벨을 덮어쓰지 않습니다.
- 개인정보 보호: 질문 원문/사용자명은 로그에 남기지 않는 것이 규칙입니다.
  요청 ID, 처리 시간, 소스 문서 수만 기록하세요.
"""

import sys

from loguru import logger

from src.config import settings

_configured = False

LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def setup_logging(level: str | None = None) -> None:
    """
    로깅을 설정합니다.

    Args:
        level: 명시적 로그 레벨. None이면 최초 1회만 settings.log_level로 설정하고,
               이미 설정된 경우 아무것도 하지 않습니다 (CLI 플래그가 우선).
    """
    global _configured

    if level is None and _configured:
        return

    logger.remove()
    logger.add(
        sys.stderr,
        level=level or settings.log_level,
        format=LOG_FORMAT,
    )
    _configured = True
