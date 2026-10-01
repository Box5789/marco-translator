# Platform Strategy

## Decision status

현재 상태: **P1-F 최소 runtime slice는 Rust shared core로 선택했고, 네 플랫폼 direct runtime gate를 2026-09-28 완료**

최종 제품 플랫폼:
- macOS
- Windows
- Android
- iOS

현재 개발/직접 검증 우선 플랫폼:
- macOS

전체 앱이나 최종 semantic/model runtime 선택은 아니다. 결정 근거와 제한은 `docs/ENGINEERING_BASELINE.md` ADR-007을 따른다.

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
| Screen capture | ScreenCaptureKit picker + one-shot screenshot | platform API | platform API | platform 제약 검증 필요 | macOS P2-A만 ADR-008에서 선택; 나머지 플랫폼은 미결정 |
| OCR | Vision revision 3 (`zh-Hans`) | capability benchmark 필요 | capability benchmark 필요 | capability benchmark 필요 | macOS P2-A만 선택; 나머지 플랫폼/언어는 미결정 |
| Overlay/UI | AppKit `NSWindow` + transient `NSPanel` | native host 검증 | native host 검증 | OS 정책/UX 검증 필요 | macOS P2-A만 host evidence 확보; 나머지 플랫폼은 미결정 |
| Model acceleration | Apple capability 측정 | Windows capability 측정 | Android capability 측정 | Apple capability 측정 | 후속 근거 수집 후 결정; P1-F는 model backend를 선택하지 않음 |
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

P1-F에서 선택한 최소 shared core는 Rust이며, versioned JSON C ABI로 platform host와 연결한다. Python은 conformance reference다. SQLite `user_version=1`과 NFKC UCD 16.0.0 contract를 고정한다. 네 플랫폼 direct target runtime proof와 full regression은 [workflow run 36381612145](https://github.com/Box5789/marco-translator/actions/runs/36381612145)에서 완료했다. 같은 7-case fixture SHA-256은 `b099cfc595104ee80edbf5adc0b247587c9fcf1955a5f04e53a435e5748e845b`다.

P1-F는 MARCO 전체 native 재작성, OCR, screen capture, overlay UI, store 배포를 요구하지 않는다. 다만 semantic engine이 stable boundary 뒤에서 교체 가능하다는 직접 fixture evidence는 필요하다.

P1-F는 macOS direct run, Windows native run, Android emulator smoke, iOS simulator smoke가 모두 성공해 Complete다. compile-only evidence는 runtime smoke를 대체하지 않았다. 상세 measurements, dependency inventory, offline boundary, 회귀 결과 및 residual limits는 `work/current.md` Final closeout에 기록했다.

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

ADR-007 이전 후보 비교 기록은 `work/current.md` Engineering Record에, 최종 결정은 ADR-007에 있다. 이후 model acceleration과 product resource budget은 미결정이다.


## P2-A macOS host vertical slice

P2-A는 macOS를 첫 제품 host로 사용해 다음 user-visible pipeline을 직접 검증한다.

```text
explicit user trigger
→ authorized screen/window/region capture
→ local OCR
→ translation backend adapter
→ transient overlay
```

P2-A는 continuous/background capture를 기본 scope로 삼지 않는다. 최소 vertical slice는 one-shot user-triggered capture이며, 실제 capability/UX evidence가 더 강한 흐름을 요구할 때만 material decision으로 확장한다.

Architecture rule:

- capture, OCR, permission, window/overlay lifecycle은 macOS host adapter 책임이다.
- semantic meaning, TM/User Overlay, unresolved safety는 shared runtime/backend 책임이다.
- host는 domain translation rule을 복제하지 않는다.
- raw capture/OCR text는 기본적으로 ephemeral이며 자동 cloud upload나 persistent logging을 하지 않는다.
- overlay가 다음 capture에 다시 들어가는 self-feedback cycle을 명시적으로 차단한다.

구체 API/프레임워크 선택은 local SDK probe와 macOS 14.0 deployment-target build를 거쳤다. P2-A는 `SCContentSharingPicker`의 단일 창/디스플레이 선택과 `SCScreenshotManager.captureImage`의 one-shot frame, Vision revision 3의 `zh-Hans`, AppKit `NSWindow`/non-activating `NSPanel`을 사용한다. 시스템 picker에는 region mode가 없어 캡처 후 preview에서 사용자가 crop한다. 전체 비교와 근거는 `docs/ENGINEERING_BASELINE.md` ADR-008에 기록한다.

P1-F `marco-runtime.v1` C ABI로 연결한다. Rust 구현은 seven-case fixture resolver이므로 이 macOS slice는 고정된 grounded 문구를 검증한다. full Python/MARCO engine은 앱에 포함하지 않았으며, Python/MARCO actual integration은 reference regression에서 별도로 유지한다. 지원 문구 밖의 입력은 unresolved로 남긴다.
