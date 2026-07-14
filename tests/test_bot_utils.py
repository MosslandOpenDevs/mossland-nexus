"""Discord 봇 유틸리티 테스트 — 메시지 분할 및 출처 조립"""

from src.bot import format_sources, split_message
from src.rag_chain import RetrievedChunk


def test_short_message_unchanged():
    assert split_message("짧은 메시지") == ["짧은 메시지"]


def test_paragraphs_packed_under_limit():
    text = "\n\n".join(f"문단 {i}: " + "내용 " * 50 for i in range(20))
    parts = split_message(text, max_length=2000)
    assert all(len(p) <= 2000 for p in parts)
    assert len(parts) > 1


def test_single_long_paragraph_hard_split():
    # 기존 버그: 2000자 초과 단일 문단을 분할하지 못했음
    text = "가" * 5000
    parts = split_message(text, max_length=2000)
    assert all(len(p) <= 2000 for p in parts)
    assert sum(len(p) for p in parts) >= 5000


def test_long_lines_within_paragraph():
    text = ("x" * 3000) + "\n" + ("y" * 100)
    parts = split_message(text, max_length=2000)
    assert all(len(p) <= 2000 for p in parts)


def test_format_sources_dedup_and_pages():
    chunks = [
        RetrievedChunk(filename="a.pdf", source="a.pdf", content="", page=3),
        RetrievedChunk(filename="a.pdf", source="a.pdf", content="", page=3),
        RetrievedChunk(filename="b.md", source="b.md", content=""),
    ]
    text = format_sources(chunks)
    assert text.count("a.pdf (p.3)") == 1
    assert "b.md" in text


def test_format_sources_empty():
    assert format_sources([]) == ""
