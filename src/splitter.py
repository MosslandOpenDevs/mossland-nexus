# ===================================================
# Moss Nexus - Text Splitter
# 의미 단위를 보존하는 재귀적 텍스트 분할기
# ===================================================
"""
LangChain 의존성 없이 구현한 경량 재귀 분할기입니다.

문단 → 줄 → 문장 → 단어 순으로 분할을 시도하여 chunk_size 이하의
조각을 만들고, 검색 문맥 유지를 위해 청크 사이에 overlap을 둡니다.
"""

DEFAULT_SEPARATORS = ("\n\n", "\n", ". ", " ")


def _split_units(text: str, chunk_size: int, separators: tuple[str, ...]) -> list[str]:
    """chunk_size 이하의 조각(unit) 리스트로 재귀 분할합니다."""
    if len(text) <= chunk_size:
        return [text]

    if not separators:
        # 더 이상 나눌 구분자가 없으면 문자 단위로 강제 분할
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep, rest = separators[0], separators[1:]
    parts = text.split(sep)
    if len(parts) == 1:
        return _split_units(text, chunk_size, rest)

    units: list[str] = []
    for i, part in enumerate(parts):
        piece = part + sep if i < len(parts) - 1 else part
        if not piece:
            continue
        if len(piece) <= chunk_size:
            units.append(piece)
        else:
            units.extend(_split_units(piece, chunk_size, rest))
    return units


def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    separators: tuple[str, ...] = DEFAULT_SEPARATORS,
) -> list[str]:
    """
    텍스트를 chunk_size 이하의 청크로 분할합니다.

    Args:
        text: 분할할 텍스트
        chunk_size: 청크 최대 길이 (문자 수)
        chunk_overlap: 인접 청크 간 중복 길이 (문자 수)
        separators: 분할 우선순위 구분자

    Returns:
        list[str]: 공백을 정리한 청크 리스트 (빈 청크 제외)
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size는 1 이상이어야 합니다")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap은 chunk_size보다 작아야 합니다")

    text = text.strip()
    if not text:
        return []

    units = _split_units(text, chunk_size, separators)

    chunks: list[str] = []
    current = ""
    for unit in units:
        if current and len(current) + len(unit) > chunk_size:
            stripped = current.strip()
            if stripped:
                chunks.append(stripped)
            # 이전 청크 끝부분을 overlap으로 이어붙여 문맥 유지
            tail = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = tail + unit if len(tail) + len(unit) <= chunk_size else unit
        else:
            current += unit

    stripped = current.strip()
    if stripped:
        chunks.append(stripped)

    return chunks
