"""splitter 단위 테스트"""

import pytest

from src.splitter import split_text


def test_empty_text_returns_no_chunks():
    assert split_text("") == []
    assert split_text("   \n\n  ") == []


def test_short_text_single_chunk():
    text = "모스랜드는 블록체인 기반 메타버스 프로젝트입니다."
    assert split_text(text, chunk_size=800) == [text]


def test_chunks_respect_max_size():
    text = "가나다라마바사아자차카타파하 " * 500
    chunks = split_text(text, chunk_size=200, chunk_overlap=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 200


def test_paragraph_boundaries_preferred():
    paragraphs = [f"문단 {i}번의 내용입니다." for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = split_text(text, chunk_size=60, chunk_overlap=10)
    # 모든 문단 내용이 어딘가에는 포함되어야 함
    joined = " ".join(chunks)
    for i in range(10):
        assert f"문단 {i}번" in joined


def test_overlap_between_chunks():
    text = ("한국어 문장입니다. " * 100).strip()
    overlap = 30
    chunks = split_text(text, chunk_size=150, chunk_overlap=overlap)
    assert len(chunks) > 1
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        # 다음 청크의 시작 부분이 이전 청크의 끝과 겹쳐야 함
        assert nxt[:10].strip() in prev or prev[-overlap:].strip()[:10] in nxt


def test_oversized_single_token_hard_split():
    # 구분자가 전혀 없는 긴 문자열도 강제 분할되어야 함
    text = "a" * 5000
    chunks = split_text(text, chunk_size=800, chunk_overlap=100)
    assert all(len(c) <= 800 for c in chunks)
    assert sum(len(c) for c in chunks) >= 5000 - 800  # 내용 손실 없음(중복 제외)


def test_invalid_params():
    with pytest.raises(ValueError):
        split_text("abc", chunk_size=0)
    with pytest.raises(ValueError):
        split_text("abc", chunk_size=100, chunk_overlap=100)
