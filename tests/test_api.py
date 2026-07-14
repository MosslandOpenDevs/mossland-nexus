"""API 테스트 — 오류 비노출, readiness, 출처 조립, 동시성 제한 검증"""

import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app
from src.rag_chain import RAGResponse, RetrievedChunk


@pytest.fixture
def client():
    # lifespan을 실행하지 않음 → rag_chain은 테스트가 직접 주입
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_rag_chain(monkeypatch):
    monkeypatch.setattr(api_module, "rag_chain", None)


class FakeRAG:
    def __init__(self, answer="테스트 답변", fail=False):
        self.answer = answer
        self.fail = fail

    def query(self, question):
        if self.fail:
            raise RuntimeError("internal secret: db password leaked")
        return RAGResponse(
            answer=self.answer,
            sources=[RetrievedChunk(
                filename="doc.md", source="doc.md",
                content="근거 " * 300,  # 500자 초과 → 절단 확인
                chunk_index=0, score=0.03,
                content_hash="a" * 64,
                ingested_at="2026-07-14T00:00:00+00:00",
            )],
            query=question,
        )

    def search(self, query, k=None):
        if self.fail:
            raise RuntimeError("internal secret")
        return [RetrievedChunk(filename="doc.md", source="doc.md", content="본문")]

    def health(self):
        return {
            "qdrant": True, "ollama": True,
            "model_available": True, "collection_points": 10,
            "healthy": True,
        }


def test_query_returns_503_when_not_ready(client):
    response = client.post("/api/query", json={"question": "질문"})
    assert response.status_code == 503


def test_health_down_when_not_ready(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "down"


def test_query_success_and_source_truncation(client, monkeypatch):
    monkeypatch.setattr(api_module, "rag_chain", FakeRAG())

    response = client.post("/api/query", json={"question": "MOC 토큰이 뭔가요?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "테스트 답변"
    assert len(body["sources"]) == 1
    assert len(body["sources"][0]["content"]) <= 503  # 500자 + "..."


def test_sources_expose_hash_and_timestamp(client, monkeypatch):
    """검증 가능한 인용: sha256 해시와 색인 시각이 API로 노출되어야 함"""
    monkeypatch.setattr(api_module, "rag_chain", FakeRAG())

    response = client.post("/api/query", json={"question": "질문"})

    source = response.json()["sources"][0]
    assert source["content_hash"] == "a" * 64
    assert source["ingested_at"] == "2026-07-14T00:00:00+00:00"


async def test_semaphore_released_only_after_thread_finishes(monkeypatch):
    """타임아웃 시 세마포어 슬롯은 스레드가 실제로 끝난 뒤에 반환되어야 함
    (그렇지 않으면 MAX_CONCURRENT_QUERIES가 실제 동시 작업 수를 제한하지 못함)"""
    sem = asyncio.Semaphore(1)
    monkeypatch.setattr(api_module, "query_semaphore", sem)

    started = threading.Event()

    def slow():
        started.set()
        time.sleep(0.4)
        return "done"

    with pytest.raises(TimeoutError):
        await api_module._run_limited(slow, timeout=0.05)

    assert started.is_set()
    # 스레드가 아직 실행 중 — 슬롯은 반환되지 않아야 함
    assert sem.locked()

    # 스레드 종료 후 슬롯 반환
    await asyncio.sleep(0.6)
    assert not sem.locked()


async def test_semaphore_released_on_success(monkeypatch):
    sem = asyncio.Semaphore(1)
    monkeypatch.setattr(api_module, "query_semaphore", sem)

    result = await api_module._run_limited(lambda: "ok", timeout=5)

    assert result == "ok"
    await asyncio.sleep(0.05)
    assert not sem.locked()


def test_query_error_does_not_leak_exception(client, monkeypatch):
    monkeypatch.setattr(api_module, "rag_chain", FakeRAG(fail=True))

    response = client.post("/api/query", json={"question": "질문"})

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "secret" not in detail
    assert "RuntimeError" not in detail


def test_search_error_does_not_leak_exception(client, monkeypatch):
    monkeypatch.setattr(api_module, "rag_chain", FakeRAG(fail=True))

    response = client.post("/api/search", json={"query": "검색어"})

    assert response.status_code == 500
    assert "secret" not in response.json()["detail"]


def test_health_reports_real_checks(client, monkeypatch):
    monkeypatch.setattr(api_module, "rag_chain", FakeRAG())

    response = client.get("/api/health")

    body = response.json()
    assert body["status"] == "healthy"
    assert body["qdrant"] is True
    assert body["collection_points"] == 10


def test_question_length_validation(client, monkeypatch):
    monkeypatch.setattr(api_module, "rag_chain", FakeRAG())

    response = client.post("/api/query", json={"question": "x" * 2000})
    assert response.status_code == 422
