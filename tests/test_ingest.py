"""ingest 파이프라인 테스트 — 원자적 재색인(fail-closed, staging→alias) 검증"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.config import settings
from src.ingest import DocumentIngester, IngestError


class FakeEmbedder:
    """결정적 더미 임베더 (모델 다운로드 없음)"""

    def encode(self, texts):
        from src.embeddings import EmbeddingBatch
        return EmbeddingBatch(
            dense=[[0.1, 0.2, 0.3] for _ in texts],
            sparse=[{1: 0.5, 7: 0.2} for _ in texts],
        )


def make_client(existing_collections=(), aliases=()):
    """upsert된 포인트를 추적하는 Qdrant 클라이언트 목"""
    client = MagicMock()
    upserted = []

    def upsert(collection_name, points, wait=True):
        upserted.extend(points)

    client.upsert.side_effect = upsert
    client.count.side_effect = lambda **kw: SimpleNamespace(count=len(upserted))
    client.get_collections.return_value = SimpleNamespace(
        collections=[SimpleNamespace(name=n) for n in existing_collections]
    )
    client.get_aliases.return_value = SimpleNamespace(
        aliases=[
            SimpleNamespace(alias_name=a, collection_name=c) for a, c in aliases
        ]
    )
    client.upserted = upserted
    return client


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    return tmp_path


def test_fail_closed_on_load_error(data_dir):
    (data_dir / "good.md").write_text("정상 문서입니다.", encoding="utf-8")
    (data_dir / "broken.pdf").write_bytes(b"not a pdf")

    client = make_client()
    ingester = DocumentIngester(embedder=FakeEmbedder(), client=client)

    with pytest.raises(IngestError):
        ingester.ingest(allow_partial=False)

    # 기존 인덱스를 절대 건드리지 않아야 함
    client.create_collection.assert_not_called()
    client.delete_collection.assert_not_called()
    client.update_collection_aliases.assert_not_called()


def test_allow_partial_proceeds(data_dir):
    (data_dir / "good.md").write_text("정상 문서입니다.", encoding="utf-8")
    (data_dir / "broken.pdf").write_bytes(b"not a pdf")

    client = make_client()
    ingester = DocumentIngester(embedder=FakeEmbedder(), client=client)

    report = ingester.ingest(allow_partial=True)

    assert report.num_chunks > 0
    assert len(report.load_errors) == 1
    client.create_collection.assert_called_once()


def test_staging_then_alias_swap(data_dir):
    (data_dir / "doc.md").write_text("모스랜드 문서입니다.", encoding="utf-8")

    alias = settings.qdrant_collection_name
    client = make_client()
    ingester = DocumentIngester(embedder=FakeEmbedder(), client=client)

    report = ingester.ingest()

    # staging 컬렉션 이름은 alias__timestamp 형식
    created = client.create_collection.call_args.kwargs["collection_name"]
    assert created.startswith(f"{alias}__")
    assert report.new_collection == created

    # alias 전환이 한 번의 원자적 호출로 이뤄져야 함
    client.update_collection_aliases.assert_called_once()
    ops = client.update_collection_aliases.call_args.kwargs["change_aliases_operations"]
    assert ops[-1].create_alias.alias_name == alias
    assert ops[-1].create_alias.collection_name == created

    # 이전 alias가 없었으므로 delete 작업 없음
    assert len(ops) == 1
    client.delete_collection.assert_not_called()


def test_previous_collection_kept_for_rollback(data_dir):
    (data_dir / "doc.md").write_text("모스랜드 문서입니다.", encoding="utf-8")

    alias = settings.qdrant_collection_name
    previous = f"{alias}__20250101000000"
    ancient = f"{alias}__20240101000000"
    client = make_client(
        existing_collections=[previous, ancient],
        aliases=[(alias, previous)],
    )
    ingester = DocumentIngester(embedder=FakeEmbedder(), client=client)

    report = ingester.ingest()

    # 직전 컬렉션은 롤백용 보존, 그 이전 것은 삭제
    assert report.previous_collection == previous
    deleted = [c.args[0] for c in client.delete_collection.call_args_list]
    assert ancient in deleted
    assert previous not in deleted


def test_legacy_plain_collection_migrated(data_dir):
    (data_dir / "doc.md").write_text("모스랜드 문서입니다.", encoding="utf-8")

    alias = settings.qdrant_collection_name
    # v1.x 레이아웃: alias 이름의 실제 컬렉션이 존재
    client = make_client(existing_collections=[alias])
    ingester = DocumentIngester(embedder=FakeEmbedder(), client=client)

    ingester.ingest()

    deleted = [c.args[0] for c in client.delete_collection.call_args_list]
    assert alias in deleted
    client.update_collection_aliases.assert_called_once()


def test_empty_data_dir_leaves_index_untouched(data_dir):
    client = make_client()
    ingester = DocumentIngester(embedder=FakeEmbedder(), client=client)

    report = ingester.ingest()

    assert report.num_chunks == 0
    client.create_collection.assert_not_called()
    client.update_collection_aliases.assert_not_called()
