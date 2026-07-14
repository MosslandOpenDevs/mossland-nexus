# Fixtures

색인 대상 디렉토리(`data/`)와 분리된 샘플·레퍼런스 문서 모음입니다.
`python main.py ingest`는 `data/`만 색인하므로, 이 디렉토리의 문서는 **기본적으로 색인되지 않습니다.**

| 디렉토리 | authority | 설명 |
|----------|-----------|------|
| `official/` | `official_record` | 공식 저장소·공시에서 검증해 요약한 레코드. 각 문서 상단 frontmatter에 `canonical_url`, `as_of`, `fetched_at`이 명시됩니다. |
| `synthetic/` | `synthetic_sample` | 데모·테스트용 합성 샘플. 사실 검증에 사용하지 마세요. |

## 사용 방법

데모를 위해 색인해 보고 싶다면 원하는 파일을 `data/`로 복사한 뒤 재색인하세요:

```bash
cp fixtures/official/moc_token_addresses.md data/
python main.py ingest
```

> `data/`는 git에서 무시됩니다(`.gitignore`). 내부 문서를 실수로 커밋하는 사고를 막기 위한 기본값이므로 해제하지 마세요.
