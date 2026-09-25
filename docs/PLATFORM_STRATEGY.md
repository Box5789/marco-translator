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

P1-F의 목적은 "모바일만 가능한가"가 아니다. **Python reference의 의미 계약을 product runtime으로 옮길 수 있는지 네 플랫폼에서 직접 검증하는 gate**다.

검증 순서:

1. Python-only coupling과 public/persistent contract를 inventory한다.
2. request/result/frame/term/error와 필요한 persistence semantics를 portable schema/fixture로 freeze한다.
3. Rust shared core, C/C++ shared core, platform-native implementations, Python reference + independent product runtime 등 현재 근거가 있는 후보를 capability probe와 source evidence로 비교한다.
4. 명확한 근거가 있을 때만 ADR로 product runtime 전략을 선택한다. 동률의 material trade-off가 남으면 구현 전에 사용자 정렬을 요청한다.
5. 선택된 전략으로 **최소 vertical slice**를 구현한다. 목표는 full product port가 아니라 contract feasibility 증명이다.
6. 최소 slice는 serialization, normalization, deterministic rule realization, unresolved safety gate, resolver/realizer 교체 seam, runtime persistence/interchange parity를 검증한다.
7. macOS에서 직접 실행하고, Windows/Android/iOS에서 같은 contract/fixture identity를 사용해 build/link/runtime smoke를 수행한다.
8. target별 결과를 direct execution / simulator-emulator / compile-link only로 분리한다. compile 성공을 runtime 성공으로 보고하지 않는다.
9. offline behavior와 Python-runtime independence를 확인한다.
10. P1-A~P1-E Python reference regression을 유지한다.

P1-F는 MARCO 전체 native 재작성, OCR, screen capture, overlay UI, store 배포를 요구하지 않는다. 다만 semantic engine이 stable boundary 뒤에서 교체 가능하다는 직접 fixture evidence는 필요하다.

P1-F를 Complete로 선언하려면 macOS direct run, Windows native run, Android emulator/runtime smoke, iOS simulator/runtime smoke가 모두 요구된다. 환경 제약으로 하나라도 실행하지 못하면 그 항목은 blocked로 남기고 compile-only evidence로 대체하지 않는다.

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
