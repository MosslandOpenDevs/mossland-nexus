"""RRF 융합 단위 테스트"""

from dataclasses import dataclass

from src.rag_chain import rrf_merge


@dataclass
class FakeHit:
    id: str


def test_rrf_empty():
    assert rrf_merge([[], []]) == []


def test_rrf_both_lists_boost_shared_items():
    dense = [FakeHit("a"), FakeHit("b"), FakeHit("c")]
    sparse = [FakeHit("b"), FakeHit("d")]

    merged = rrf_merge([dense, sparse])
    ids = [item.id for item, _ in merged]

    # 양쪽에 모두 등장한 b가 1위
    assert ids[0] == "b"
    assert set(ids) == {"a", "b", "c", "d"}


def test_rrf_scores_descending():
    dense = [FakeHit("a"), FakeHit("b")]
    sparse = [FakeHit("c")]
    merged = rrf_merge([dense, sparse])
    scores = [score for _, score in merged]
    assert scores == sorted(scores, reverse=True)


def test_rrf_single_list_preserves_order():
    dense = [FakeHit("x"), FakeHit("y"), FakeHit("z")]
    merged = rrf_merge([dense])
    assert [item.id for item, _ in merged] == ["x", "y", "z"]
