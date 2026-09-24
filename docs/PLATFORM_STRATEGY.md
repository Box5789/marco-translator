# Platform Strategy

## Decision status

현재 상태: **Constraints accepted, implementation technology undecided**

최종 제품 플랫폼:
- macOS
- Windows
- Android
- iOS

현재 개발/직접 검증 우선 플랫폼:
- macOS

이 문서는 Rust/C++/Swift 등 특정 구현 기술을 선택하는 ADR이 아니다.

## 공통 Core 계약으로 유지할 영역

다음 의미는 플랫폼 간 동일해야 한다.

- `TranslationRequest`
- `TranslationResult`
- `SemanticFrame`
- terminology/provenance representation
- Translation Memory semantics
- Base KG / User Overlay / Session State separation
- translation log/evidence schema
- maintenance package/patch contract
- version activation/rollback semantics
- Neural Realizer input/output contract

공통 contract는 JSON/schema 또는 동등하게 portable한 명세로 검증 가능해야 하며 특정 UI toolkit이나 Python object identity를 요구하지 않는다.

## 플랫폼 adapter로 예상하는 영역

| Surface | macOS | Windows | Android | iOS | 현재 결정 |
|---|---|---|---|---|---|
| Screen capture | platform API | platform API | platform API | platform 제약 검증 필요 | P2/P1-F 전 미결정 |
| OCR | capability benchmark 필요 | capability benchmark 필요 | capability benchmark 필요 | capability benchmark 필요 | 미결정 |
| Overlay/UI | native host 검증 | native host 검증 | native host 검증 | OS 정책/UX 검증 필요 | 미결정 |
| Model acceleration | Apple capability 측정 | Windows capability 측정 | Android capability 측정 | Apple capability 측정 | P1-E/P1-F에서 결정 |
| Persistence location | app sandbox 정책 | app data 정책 | app sandbox 정책 | app sandbox 정책 | adapter |
| Permissions/lifecycle | macOS 정책 | Windows 정책 | Android 정책 | iOS 정책 | adapter |

## macOS-first validation

P1/P2 초기 직접 검증은 macOS에서 한다.

### P1에서 Mac으로 직접 확인할 것
- MARCO semantic resolution
- Translation Memory
- User Overlay persistence
- Session State
- correction flow
- routing-weight rollback
- maintenance export/import
- patch dry-run
- corpus replay
- KG version rollback
- offline execution
- P1-E에서 Tiny Realizer latency/RAM 측정

### P2에서 Mac으로 먼저 확인할 것
- screen capture
- OCR
- translation overlay
- 실제 host interaction

GitHub Actions/CLI 성공은 실제 macOS host interaction이 필요한 항목의 대체 증거가 아니다.

## Cross-platform Runtime Gate (P1-F)

P1-F의 목적은 "모바일만 가능한가"가 아니다.

다음을 검증한다.

1. shared contract가 Python implementation detail에 종속되지 않는가.
2. persistent data를 네 플랫폼에서 같은 의미로 읽고 쓸 수 있는가.
3. semantic engine, persistence, model runtime을 stable boundary 뒤에서 교체할 수 있는가.
4. macOS reference fixture를 Windows/Android/iOS에서도 재생할 수 있는가.
5. 각 플랫폼의 resource/permission 차이를 core semantic contract 밖으로 격리할 수 있는가.

## 향후 Architecture ADR의 평가 후보

기술 선택 시 최소 다음을 비교한다.

- Rust shared core
- C/C++ shared core
- platform-native implementations behind stable contracts
- 현재 Python reference를 유지하면서 product runtime만 별도 구현
- source/test evidence가 추가로 정당화하는 대안

비교 기준:
- semantic contract fidelity
- FFI complexity
- build/release complexity
- SQLite/persistence portability
- model runtime integration
- memory/latency
- debugging/tooling
- supply-chain/dependency risk
- macOS/Windows/Android/iOS distribution constraints
- test fixture 재사용 가능성

현재 단계에서 특정 후보를 preferred architecture로 기록하지 않는다.
