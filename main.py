#!/usr/bin/env python3
# ===================================================
# Moss Nexus - Main Entry Point
# 메인 실행 파일
# ===================================================
"""
Moss Nexus 애플리케이션의 메인 진입점입니다.

사용법:
    # Discord 봇 실행
    python main.py bot

    # Web UI & API 서버 실행
    python main.py api

    # 데이터 수집 (문서 인덱싱)
    python main.py ingest [--allow-partial]

    # 설정 확인
    python main.py config

    # RAG 테스트 (CLI 모드)
    python main.py test
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_bot():
    """Discord 봇을 실행합니다."""
    from src.bot import run_bot as start_discord_bot
    from src.config import settings

    print("=" * 60)
    print("       Moss Nexus - Discord Bot")
    print("       Mossland Local-first Knowledge & Evidence Node")
    print("=" * 60)
    print()
    print(f"  LLM Model: {settings.ollama_model}")
    print(f"  Embedding: {settings.embedding_model}")
    print(f"  Qdrant: {settings.qdrant_url}")
    print("  Commands: /ask /search /status /ping")
    print()
    print("=" * 60)
    print()

    start_discord_bot()


def run_api():
    """FastAPI 웹 서버를 실행합니다. Web UI와 REST API를 제공합니다."""
    from src.api import run_api as start_api_server
    start_api_server()


def run_ingest(allow_partial: bool = False):
    """데이터 수집 파이프라인을 실행합니다."""
    from src.config import settings
    from src.ingest import run_ingestion

    print("=" * 60)
    print("       Moss Nexus - Data Ingestion")
    print("       문서 인덱싱 파이프라인 (staging → 검증 → alias 전환)")
    print("=" * 60)
    print()
    print(f"  Data Directory: {settings.data_path}")
    print(f"  Embedding Model: {settings.embedding_model}")
    print(f"  Chunk Size: {settings.chunk_size}")
    print(f"  Collection (alias): {settings.qdrant_collection_name}")
    print()
    print("=" * 60)
    print()

    run_ingestion(allow_partial=allow_partial)


def show_config():
    """현재 설정을 출력합니다."""
    from src.config import print_settings
    print_settings()


def run_test():
    """RAG 시스템을 CLI 모드로 테스트합니다."""
    from src.rag_chain import get_rag_chain

    print("=" * 60)
    print("       Moss Nexus - Interactive Test Mode")
    print("       RAG 시스템 테스트")
    print("=" * 60)
    print()
    print("질문을 입력하세요 (종료: 'quit' 또는 'exit')")
    print()

    print("RAG 체인 초기화 중...")
    rag = get_rag_chain()
    print("초기화 완료!")
    print()

    while True:
        try:
            question = input("질문 > ").strip()

            if not question:
                continue

            if question.lower() in ['quit', 'exit', 'q']:
                print("테스트를 종료합니다.")
                break

            print("\n답변 생성 중...")
            response = rag.query(question)

            print()
            print("-" * 40)
            print("답변:")
            print("-" * 40)
            print(response.answer)

            if response.sources:
                print()
                print("참조 문서:")
                for chunk in response.sources:
                    label = chunk.filename
                    if chunk.page:
                        label += f" (p.{chunk.page})"
                    print(f"  - {label}")

            print()

        except KeyboardInterrupt:
            print("\n\n테스트를 종료합니다.")
            break
        except Exception as e:
            print(f"오류 발생: {type(e).__name__}: {e}")
            continue


def main():
    """메인 함수: 커맨드라인 인자를 파싱하고 해당 기능을 실행합니다."""
    parser = argparse.ArgumentParser(
        description="Moss Nexus - Mossland Local-first Knowledge & Evidence Node",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python main.py bot       # Discord 봇 실행 (/ask, /search, /status, /ping)
  python main.py api       # Web UI & API 서버 실행 (기본: 127.0.0.1:8000)
  python main.py ingest    # 문서 인덱싱 (data/ 폴더, 원자적 재색인)
  python main.py config    # 설정 확인
  python main.py test      # CLI 테스트 모드

시작하기:
  1. .env.example을 .env로 복사하고 설정 편집
  2. docker-compose up -d  (Qdrant 시작)
  3. data/ 폴더에 문서 추가 (PDF, MD, TXT, DOCX)
  4. python main.py ingest  (문서 인덱싱)
  5. python main.py api     (Web UI 시작) 또는
     python main.py bot     (Discord 봇 시작)
        """
    )

    parser.add_argument(
        "command",
        choices=["bot", "api", "ingest", "config", "test"],
        help="실행할 명령 (bot: Discord봇, api: Web서버, ingest: 문서인덱싱, "
             "config: 설정확인, test: CLI테스트)"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="로그 레벨 (기본: .env의 LOG_LEVEL 또는 INFO)"
    )

    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="(ingest 전용) 일부 파일 로드 실패를 허용하고 부분 색인 진행"
    )

    args = parser.parse_args()

    # 로깅 설정 — 여기서 설정한 레벨을 각 모듈이 덮어쓰지 않음
    from src.logging_setup import setup_logging
    setup_logging(args.log_level)

    if args.command == "ingest":
        run_ingest(allow_partial=args.allow_partial)
        return

    commands = {
        "bot": run_bot,
        "api": run_api,
        "config": show_config,
        "test": run_test,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
