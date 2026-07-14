# ===================================================
# Moss Nexus - Discord Bot Module
# Discord slash command 인터페이스
# ===================================================
"""
Discord 봇 (slash commands 기반).

보안/프라이버시 기본값:
- privileged intent(message_content) 불필요 — slash command만 사용
- guild/channel allowlist (설정 시 해당 서버·채널에서만 동작)
- 사용자별 쿨다운 + 전역 동시성 제한
- 질문 원문·사용자명을 로그에 남기지 않음
- 내부 예외 문자열을 사용자에게 노출하지 않음
"""

import asyncio
from datetime import UTC, datetime

import discord
from discord import app_commands
from loguru import logger

from src.config import settings
from src.logging_setup import setup_logging
from src.rag_chain import RetrievedChunk, get_rag_chain

setup_logging()

GENERIC_ERROR = "죄송합니다. 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
NOT_READY = "시스템이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요."
MAX_MESSAGE_LENGTH = 2000  # Discord 메시지 최대 길이


# ─────────────────────────────────────────────────
# 메시지 분할
# ─────────────────────────────────────────────────
def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """
    긴 메시지를 Discord 제한에 맞게 분할합니다.

    문단 → 줄 → 강제 절단 순으로 시도하므로 max_length를 넘는
    단일 문단/줄도 안전하게 분할됩니다.
    """
    if len(text) <= max_length:
        return [text]

    units: list[str] = []
    for paragraph in text.split("\n\n"):
        if len(paragraph) <= max_length:
            units.append(paragraph)
            continue
        for line in paragraph.split("\n"):
            if len(line) <= max_length:
                units.append(line)
            else:
                units.extend(
                    line[i:i + max_length]
                    for i in range(0, len(line), max_length)
                )

    parts: list[str] = []
    current = ""
    for unit in units:
        if not unit.strip():
            continue
        if current and len(current) + len(unit) + 2 > max_length:
            parts.append(current)
            current = unit
        else:
            current = f"{current}\n\n{unit}" if current else unit
    if current:
        parts.append(current)

    return parts if parts else [text[:max_length]]


def format_sources(sources: list[RetrievedChunk]) -> str:
    """검색 메타데이터에서 출처 문자열을 조립합니다 (LLM 생성이 아님)."""
    seen: dict[str, None] = {}
    for chunk in sources:
        label = chunk.filename
        if chunk.page:
            label += f" (p.{chunk.page})"
        seen.setdefault(label, None)
    if not seen:
        return ""
    return "**참조 문서:** " + ", ".join(seen.keys())


# ─────────────────────────────────────────────────
# 클라이언트 (allowlist 검사 포함)
# ─────────────────────────────────────────────────
class GuardedCommandTree(app_commands.CommandTree):
    """guild/channel allowlist를 강제하는 커맨드 트리"""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        allowed_guilds = settings.discord_guild_id_list
        if allowed_guilds and interaction.guild_id not in allowed_guilds:
            await interaction.response.send_message(
                "이 서버에서는 사용할 수 없는 봇입니다.", ephemeral=True
            )
            return False

        allowed_channels = settings.discord_channel_id_list
        if allowed_channels and interaction.channel_id not in allowed_channels:
            await interaction.response.send_message(
                "이 채널에서는 사용할 수 없습니다.", ephemeral=True
            )
            return False

        return True


class MossNexusClient(discord.Client):
    """Moss Nexus Discord 클라이언트 (slash command 전용)"""

    def __init__(self):
        # message_content 등 privileged intent 불필요
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = GuardedCommandTree(self)
        self.rag_chain = None
        self.query_semaphore = asyncio.Semaphore(settings.max_concurrent_queries)
        self._init_lock = asyncio.Lock()

    async def setup_hook(self):
        guild_ids = settings.discord_guild_id_list
        if guild_ids:
            # allowlist가 있으면 해당 guild에만 커맨드 등록 (전역 미등록)
            for gid in guild_ids:
                guild = discord.Object(id=gid)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            logger.info(f"slash command를 {len(guild_ids)}개 guild에 등록했습니다")
        else:
            await self.tree.sync()
            logger.info("slash command를 전역 등록했습니다 (반영까지 최대 1시간)")

    async def on_ready(self):
        logger.info(f"봇 로그인 완료 (연결된 서버 수: {len(self.guilds)})")

        # on_ready는 재연결 시 여러 번 호출될 수 있으므로 1회만 초기화
        async with self._init_lock:
            if self.rag_chain is None:
                try:
                    loop = asyncio.get_event_loop()
                    self.rag_chain = await loop.run_in_executor(None, get_rag_chain)
                    logger.info("RAG 체인 초기화 완료")
                except Exception as e:
                    logger.error(f"RAG 체인 초기화 실패: {type(e).__name__}: {e}")
                    logger.warning("봇은 실행되지만 질문 기능이 작동하지 않습니다.")

        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="/ask 질문",
            ),
        )


client = MossNexusClient()


async def _run_rag(func, *args):
    """
    동시성 제한 + 타임아웃 하에 동기 RAG 함수를 실행합니다.

    실행 중인 스레드는 취소할 수 없으므로, 세마포어 슬롯은 타임아웃 시점이
    아니라 스레드가 실제로 끝나는 시점에 반환합니다.
    """
    await client.query_semaphore.acquire()
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, func, *args)

    def _release(finished):
        if not finished.cancelled():
            finished.exception()  # 미회수 예외 경고 방지
        client.query_semaphore.release()

    future.add_done_callback(_release)
    return await asyncio.wait_for(
        asyncio.shield(future), timeout=settings.query_timeout_seconds
    )


# ─────────────────────────────────────────────────
# Slash Commands
# ─────────────────────────────────────────────────
@client.tree.command(name="ask", description="모스랜드 문서에 대해 질문합니다")
@app_commands.describe(question="질문 내용")
@app_commands.checks.cooldown(1, settings.discord_cooldown_seconds)
async def ask_command(interaction: discord.Interaction, question: str):
    if client.rag_chain is None:
        await interaction.response.send_message(NOT_READY, ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    logger.info(f"[{interaction.id}] /ask 수신 (질문 길이: {len(question)}자)")
    started = asyncio.get_event_loop().time()

    try:
        response = await _run_rag(client.rag_chain.query, question)
    except TimeoutError:
        logger.error(f"[{interaction.id}] 질의 타임아웃")
        await interaction.followup.send(GENERIC_ERROR)
        return
    except Exception as e:
        logger.error(f"[{interaction.id}] 질문 처리 중 오류: {type(e).__name__}: {e}")
        await interaction.followup.send(GENERIC_ERROR)
        return

    elapsed = asyncio.get_event_loop().time() - started
    logger.info(
        f"[{interaction.id}] 답변 완료 "
        f"(처리 시간: {elapsed:.1f}s, 근거: {len(response.sources)}개)"
    )

    parts = split_message(response.answer)
    embed = discord.Embed(
        title="Moss Nexus 답변",
        description=parts[0],
        color=discord.Color.green(),
        timestamp=datetime.now(UTC),
    )
    embed.set_footer(
        text=f"{settings.ollama_model} · 근거 {len(response.sources)}개 · {elapsed:.1f}s"
    )
    await interaction.followup.send(embed=embed)

    for part in parts[1:]:
        await interaction.followup.send(part)

    source_text = format_sources(response.sources)
    if source_text:
        for part in split_message(source_text):
            await interaction.followup.send(part)


@client.tree.command(name="search", description="문서만 검색합니다 (답변 생성 없음)")
@app_commands.describe(query="검색어")
@app_commands.checks.cooldown(1, settings.discord_cooldown_seconds)
async def search_command(interaction: discord.Interaction, query: str):
    if client.rag_chain is None:
        await interaction.response.send_message(NOT_READY, ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    try:
        chunks = await _run_rag(client.rag_chain.search, query)
    except TimeoutError:
        await interaction.followup.send(GENERIC_ERROR)
        return
    except Exception as e:
        logger.error(f"[{interaction.id}] 검색 중 오류: {type(e).__name__}: {e}")
        await interaction.followup.send(GENERIC_ERROR)
        return

    if not chunks:
        await interaction.followup.send("관련 문서를 찾을 수 없습니다.")
        return

    embed = discord.Embed(title="검색 결과", color=discord.Color.orange())
    for i, chunk in enumerate(chunks, start=1):
        label = chunk.filename
        if chunk.page:
            label += f" (p.{chunk.page})"
        content = chunk.content
        if len(content) > 200:
            content = content[:200] + "..."
        # Discord embed field name 제한: 256자
        embed.add_field(name=f"{i}. {label}"[:256], value=content, inline=False)

    await interaction.followup.send(embed=embed)


@client.tree.command(name="status", description="시스템 상태를 확인합니다")
async def status_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)

    embed = discord.Embed(
        title="Moss Nexus 시스템 상태",
        color=discord.Color.blue(),
    )

    if client.rag_chain is None:
        embed.add_field(name="RAG 엔진", value="초기화되지 않음", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    try:
        loop = asyncio.get_event_loop()
        checks = await loop.run_in_executor(None, client.rag_chain.health)
    except Exception as e:
        logger.error(f"상태 확인 실패: {type(e).__name__}: {e}")
        await interaction.followup.send(GENERIC_ERROR, ephemeral=True)
        return

    def mark(ok: bool) -> str:
        return "✅ 정상" if ok else "❌ 접근 불가"

    embed.add_field(name="전체", value=mark(checks["healthy"]), inline=True)
    embed.add_field(name="Qdrant", value=mark(checks["qdrant"]), inline=True)
    embed.add_field(name="Ollama", value=mark(checks["ollama"]), inline=True)
    embed.add_field(
        name="LLM 모델",
        value=f"{settings.ollama_model} ({'설치됨' if checks['model_available'] else '미설치'})",
        inline=True,
    )
    points = checks["collection_points"]
    embed.add_field(
        name="색인",
        value=f"{points}개 청크" if points is not None else "없음",
        inline=True,
    )

    await interaction.followup.send(embed=embed, ephemeral=True)


@client.tree.command(name="ping", description="봇의 응답 상태를 확인합니다")
async def ping_command(interaction: discord.Interaction):
    latency = round(client.latency * 1000)
    await interaction.response.send_message(
        f"Pong! 지연 시간: {latency}ms", ephemeral=True
    )


# ─────────────────────────────────────────────────
# 오류 처리
# ─────────────────────────────────────────────────
@client.tree.error
async def on_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CommandOnCooldown):
        message = f"잠시 후 다시 시도해주세요 ({error.retry_after:.0f}초 후 가능)."
    elif isinstance(error, app_commands.CheckFailure):
        return  # interaction_check에서 이미 응답함
    else:
        logger.error(f"[{interaction.id}] 명령어 오류: {type(error).__name__}: {error}")
        message = GENERIC_ERROR

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


# ─────────────────────────────────────────────────
# 봇 실행 함수
# ─────────────────────────────────────────────────
def run_bot():
    """Discord 봇을 실행합니다."""
    token = settings.discord_bot_token

    if not token or token == "your_discord_bot_token_here":
        logger.error("Discord 봇 토큰이 설정되지 않았습니다!")
        logger.error(".env 파일에 DISCORD_BOT_TOKEN을 설정해주세요.")
        return

    logger.info("Discord 봇 시작 중...")
    client.run(token)


if __name__ == "__main__":
    run_bot()
