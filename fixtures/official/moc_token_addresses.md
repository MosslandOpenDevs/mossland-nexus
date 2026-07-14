---
source_id: "mossland:moc-erc20-2025:readme"
authority: "official_record"
canonical_url: "https://github.com/mossland/MossCoin-ERC20-2025"
published_at: "2025-08-04"
fetched_at: "2026-07-14"
as_of: "2026-07-14"
---

# Moss Coin (MOC) 컨트랙트 주소 — 현행/레거시 공식 레코드

이 문서는 [mossland/MossCoin-ERC20-2025](https://github.com/mossland/MossCoin-ERC20-2025)
공식 저장소의 내용을 요약한 레코드입니다. 최신 상태는 반드시 원본(canonical_url)에서 확인하세요.

## 현행 토큰 (사용해야 하는 주소)

| 항목 | 값 |
|------|-----|
| 토큰명 / 심볼 | Moss Coin (MOC) |
| 네트워크 | Ethereum Mainnet (ChainId 1) |
| **컨트랙트 주소 (2025 ERC-20)** | [`0x8bbfe65e31b348cd823c62e02ad8c19a84dd0dab`](https://etherscan.io/token/0x8bbfe65e31b348cd823c62e02ad8c19a84dd0dab) |
| Decimals | 18 |
| 총 발행량 | 500,000,000 MOC (고정, premint) |
| 배포일 | 2025-08-04 |
| 관리 모델 | Ownerless (관리자 키 없음) |
| 기능 | Burnable, Permit (EIP-2612), Votes (ERC20Votes / EIP-712) |
| 감사 | CertiK |

## 레거시 토큰 (사용 금지)

> 아래 컨트랙트는 기록 추적용으로만 남아 있습니다.
> **입금·스왑·연동에 사용하지 마세요.**

| 토큰 | 네트워크 | 컨트랙트 | 상태 |
|------|----------|----------|------|
| Legacy ERC-20 (2018) | Ethereum Mainnet | `0x865ec58b06bF6305B886793AA20A2da31D034E68` | **Deprecated** — 2025 마이그레이션 경로에 포함되지 않음 |
| Luniverse MOC | Luniverse (기업용 체인) | `0x878120A5C9828759A250156c66D629219F07C5c6` | 현행 마이그레이션의 **출발점** (Luniverse → ERC-20 2025 경로만 지원) |
| WMOC (ERC-20) | Ethereum Mainnet | `0xbee20b9df360b8442534ed8059f3e5baeeb74eaf` | 스왑 **중단(inactive)** |

## 마이그레이션 경로

- ✅ 지원: **Luniverse → ERC-20 (2025)**
- ❌ 미지원: Legacy ERC-20 (2018) → ERC-20 (2025), WMOC 경유 경로 일체

## 피싱 주의

공식 채널의 링크만 사용하고, 항상 위의 **현행 Mainnet 주소**를 확인하세요.
현재 활성화된 스왑 포털은 없습니다.
