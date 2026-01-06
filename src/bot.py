# ===================================================
# Moss Nexus - Discord Bot Module
# Discord 봇 인터페이스
# ===================================================
"""
이 모듈은 Discord 봇을 통해 RAG 시스템에 접근하는
사용자 인터페이스를 제공합니다.

주요 기능:
1. !ask 명령어로 질문 수신
2. RAG 체인을 통한 답변 생성
3. 긴 답변의 페이지네이션 처리
4. 입력 중 표시 (타이핑 인디케이터)
"""

import asyncio
import sys
from typing import Optional
from datetime import datetime

import discord
from discord.ext import commands
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
# Discord 봇 설정
# ─────────────────────────────────────────────────
# 필요한 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True  # 메시지 내용 읽기 권한

# 봇 인스턴스 생성
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    description="Moss Nexus - 모스랜드 AI 거버넌스 어시스턴트"
)

# RAG 체인 인스턴스 (지연 초기화)
rag_chain: Optional[RAGChain] = None


# ─────────────────────────────────────────────────
# Discord 메시지 길이 제한
# ─────────────────────────────────────────────────
MAX_MESSAGE_LENGTH = 2000  # Discord 메시지 최대 길이


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """
    긴 메시지를 Discord 제한에 맞게 분할합니다.

    Args:
        text: 분할할 텍스트
        max_length: 각 부분의 최대 길이

    Returns:
        list[str]: 분할된 메시지 리스트
    """
    if len(text) <= max_length:
        return [text]

    parts = []
    current_part = ""

    # 문단 단위로 분할 시도
    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        # 현재 부분에 추가해도 제한 이내면 추가
        if len(current_part) + len(paragraph) + 2 <= max_length:
            if current_part:
                current_part += "\n\n" + paragraph
            else:
                current_part = paragraph
        else:
            # 현재 부분 저장하고 새로운 부분 시작
            if current_part:
                parts.append(current_part)
            current_part = paragraph

    # 마지막 부분 추가
    if current_part:
        parts.append(current_part)

    return parts


# ─────────────────────────────────────────────────
# 봇 이벤트 핸들러
# ─────────────────────────────────────────────────
@bot.event
async def on_ready():
    """
    봇이 Discord에 연결되었을 때 호출됩니다.
    RAG 체인을 초기화하고 준비 완료 메시지를 출력합니다.
    """
    global rag_chain

    logger.info(f"봇 로그인 완료: {bot.user.name} ({bot.user.id})")
    logger.info(f"연결된 서버 수: {len(bot.guilds)}")

    # RAG 체인 초기화 (백그라운드에서 실행)
    logger.info("RAG 체인 초기화 중...")
    try:
        rag_chain = get_rag_chain()
        logger.info("RAG 체인 초기화 완료!")
    except Exception as e:
        logger.error(f"RAG 체인 초기화 실패: {e}")
        logger.warning("봇은 실행되지만 질문 기능이 작동하지 않을 수 있습니다.")

    # 봇 상태 설정
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!ask 질문"
        )
    )

    print("=" * 50)
    print(f"Moss Nexus 봇이 준비되었습니다!")
    print(f"봇 이름: {bot.user.name}")
    print(f"명령어: !ask [질문]")
    print("=" * 50)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    """
    명령어 오류 발생 시 호출됩니다.

    Args:
        ctx: 명령어 컨텍스트
        error: 발생한 오류
    """
    if isinstance(error, commands.CommandNotFound):
        # 알 수 없는 명령어는 무시
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("질문을 입력해주세요. 사용법: `!ask [질문]`")
        return

    logger.error(f"명령어 오류: {error}")
    await ctx.send(f"오류가 발생했습니다: {str(error)}")


# ─────────────────────────────────────────────────
# 봇 명령어
# ─────────────────────────────────────────────────
@bot.command(name="ask", help="모스랜드에 대해 질문합니다. 예: !ask MOC 토큰이 뭔가요?")
async def ask_question(ctx: commands.Context, *, question: str):
    """
    사용자의 질문을 받아 RAG 시스템으로 답변을 생성합니다.

    사용법: !ask [질문]
    예시: !ask 모스랜드는 어떤 프로젝트인가요?

    Args:
        ctx: 명령어 컨텍스트
        question: 사용자 질문
    """
    global rag_chain

    # RAG 체인이 초기화되지 않은 경우
    if rag_chain is None:
        await ctx.send("시스템이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.")
        return

    # 질문 로깅
    logger.info(f"질문 수신 - 사용자: {ctx.author.name}, 질문: {question}")

    # 임시 메시지 전송 및 타이핑 인디케이터 표시
    processing_msg = await ctx.send("문서를 분석 중입니다...")

    try:
        # 타이핑 인디케이터를 유지하면서 RAG 처리
        async with ctx.typing():
            # RAG 체인 호출 (동기 함수를 비동기로 실행)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                rag_chain.query,
                question
            )

        # 임시 메시지 삭제
        await processing_msg.delete()

        # 답변 전송
        answer = response.answer

        # 긴 메시지 분할 처리
        message_parts = split_message(answer)

        for i, part in enumerate(message_parts):
            if i == 0:
                # 첫 번째 메시지: 임베드로 전송
                embed = discord.Embed(
                    title="Moss Nexus 답변",
                    description=part,
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"질문: {question[:50]}...")
                await ctx.send(embed=embed)
            else:
                # 나머지: 일반 메시지로 전송
                await ctx.send(part)

        # 출처 문서 정보 (선택적)
        if response.source_documents:
            sources = set()
            for doc in response.source_documents:
                filename = doc.metadata.get('filename', '')
                if filename:
                    sources.add(filename)

            if sources:
                source_text = "**참조 문서:** " + ", ".join(sorted(sources))
                await ctx.send(source_text)

    except Exception as e:
        logger.error(f"질문 처리 중 오류: {e}")
        await processing_msg.edit(
            content=f"죄송합니다. 답변 생성 중 오류가 발생했습니다.\n오류: {str(e)}"
        )


@bot.command(name="ping", help="봇의 응답 상태를 확인합니다.")
async def ping(ctx: commands.Context):
    """
    봇의 응답 상태와 지연 시간을 확인합니다.
    """
    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! 지연 시간: {latency}ms")


@bot.command(name="status", help="시스템 상태를 확인합니다.")
async def status(ctx: commands.Context):
    """
    RAG 시스템의 상태를 확인합니다.
    """
    global rag_chain

    embed = discord.Embed(
        title="Moss Nexus 시스템 상태",
        color=discord.Color.blue()
    )

    # RAG 체인 상태
    rag_status = "정상" if rag_chain is not None else "초기화 필요"
    embed.add_field(name="RAG 엔진", value=rag_status, inline=True)

    # 설정 정보
    embed.add_field(name="LLM 모델", value=settings.ollama_model, inline=True)
    embed.add_field(name="임베딩 모델", value=settings.embedding_model, inline=True)
    embed.add_field(name="Qdrant", value=settings.qdrant_url, inline=True)

    await ctx.send(embed=embed)


@bot.command(name="search", help="문서만 검색합니다 (답변 생성 없음). 예: !search MOC 토큰")
async def search_docs(ctx: commands.Context, *, query: str):
    """
    질문과 관련된 문서를 검색합니다 (답변 생성 없이).
    디버깅 및 문서 확인용입니다.

    Args:
        ctx: 명령어 컨텍스트
        query: 검색 쿼리
    """
    global rag_chain

    if rag_chain is None:
        await ctx.send("시스템이 아직 준비되지 않았습니다.")
        return

    async with ctx.typing():
        loop = asyncio.get_event_loop()
        documents = await loop.run_in_executor(
            None,
            rag_chain.search_documents,
            query
        )

    if not documents:
        await ctx.send("관련 문서를 찾을 수 없습니다.")
        return

    embed = discord.Embed(
        title=f"검색 결과: {query}",
        color=discord.Color.orange()
    )

    for i, doc in enumerate(documents, 1):
        filename = doc.metadata.get('filename', 'unknown')
        content = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
        embed.add_field(
            name=f"{i}. {filename}",
            value=content,
            inline=False
        )

    await ctx.send(embed=embed)


# ─────────────────────────────────────────────────
# 봇 실행 함수
# ─────────────────────────────────────────────────
def run_bot():
    """
    Discord 봇을 실행합니다.
    """
    token = settings.discord_bot_token

    if not token or token == "your_discord_bot_token_here":
        logger.error("Discord 봇 토큰이 설정되지 않았습니다!")
        logger.error(".env 파일에 DISCORD_BOT_TOKEN을 설정해주세요.")
        return

    logger.info("Discord 봇 시작 중...")
    bot.run(token)


# ─────────────────────────────────────────────────
# 직접 실행 시 봇 시작
# ─────────────────────────────────────────────────
if __name__ == "__main__":
    run_bot()
