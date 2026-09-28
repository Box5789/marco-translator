# Current Task — P2-A macOS Capture / OCR / Overlay

Status: Active — capability/requirements evidence phase  
Branch: `p2/macos-capture-ocr-overlay`  
Parent baseline: `p1/cross-platform-runtime-gate@21f7ed967e38fa56ea484c54a3e3e8db1652987a`

P1-F의 전체 Engineering Record는 `work/p1-f-cross-platform-runtime-gate.md`에 보존한다.

## Goal

`software-engineering-discipline`의 full-scope gate를 적용해 실제 macOS 앱에서 **명시적 화면 캡처 → local OCR → translation backend → transient overlay**의 end-to-end vertical slice를 구현하고 직접 검증한다.

정확한 사용자 observable outcome:

> 사용자가 macOS 앱에서 캡처를 명시적으로 시작하면, 권한이 있는 화면/윈도우/영역의 텍스트를 local OCR로 읽고 기존 번역 계약에 전달하며, 번역 결과를 source 앱을 수정하지 않는 transient overlay로 확인하고 닫거나 취소할 수 있다. 기본 동작은 screenshot/OCR text를 디스크나 cloud에 남기지 않는다.

## Current stage

- P1-A~P1-F: Complete
- P2-A: Active — capability/requirements evidence
- Later P2 stages: Not started

## Accepted constraints

- 최종 지원 목표는 macOS / Windows / Android / iOS지만 P2-A 구현/직접 검증은 macOS only다.
- P1-F ADR-007의 Rust shared core, versioned C ABI, SQLite boundary를 유지한다.
- macOS host code는 capture/OCR/overlay/permission/lifecycle adapter를 소유한다.
- macOS host가 semantic/domain translation rule을 재구현하면 안 된다.
- offline-first를 유지한다.
- raw screenshot과 OCR text는 default persistent state가 아니다.
- screen capture는 명시적 user action에서 시작한다.
- P2-A의 최소 flow는 one-shot capture다. continuous/background monitoring은 out of scope다.
- unknown/unresolved input은 fluent guess로 표시하지 않는다.
- Tiny Neural Realizer/backend는 P1-E의 rejected Qwen3 후보를 자동 채택하지 않는다.
- app-store packaging/signing/notarization은 out of scope다.

## Scope

### A1 — Documentation preflight and capability probes

- canonical docs/task-state/Graphify 복원
- P1-F runtime/C ABI와 macOS host example 조사
- 현재 macOS/Xcode/Swift/SDK capability 확인
- capture API/permission behavior 최소 probe
- OCR API/language/coordinate behavior 최소 probe
- overlay/window behavior, focus, own-window exclusion 최소 probe
- native project pattern/build approach 조사

Architecture 선택 전에 실제 SDK/source evidence를 확보한다.

### A2 — Use case/state/privacy contract

다음을 명확히 기록한다.

- actor/user goal과 explicit capture trigger
- capture source와 selection semantics
- permission denied/restricted/granted behavior
- canonical request state
- captured frame lifetime
- OCR result lifetime
- translation request/result ownership
- overlay display state
- cancel/retry/re-entry semantics
- stale asynchronous completion guard
- own-overlay/self-capture feedback guard
- error mapping
- default persistence/logging policy

Async completion이 이전 request 결과를 최신 overlay에 덮어쓰지 못하도록 request identity/generation guard를 정의한다.

### A3 — Architecture ADR

현재 source와 capability probe 후 다음 책임을 evidence로 선택한다.

- macOS app host/UI
- capture adapter
- OCR adapter
- translation backend adapter
- overlay adapter
- request coordinator/state owner

Native platform capability가 confirmed criteria를 충족하면 새 third-party dependency보다 우선한다.

### A4 — Minimal implementation

Acceptance를 증명하는 최소 native macOS app만 구현한다.

Required product flow:

```text
launch
→ explicit capture action
→ capture permission/source handling
→ frame
→ local OCR
→ translation backend
→ transient overlay
→ dismiss/cancel/retry
```

Controlled fixtures에는 현재 번역 regression에서 grounded된 중국어 phrase를 사용해 capture→OCR→translation을 직접 검증한다.

### A5 — Direct-host validation

- permission denied/granted
- real capture
- OCR oracle
- translation result
- unresolved behavior
- overlay
- cycle guard
- cancel/re-entry
- default no-persistence
- offline execution
- latency
- shared runtime/Python regression

CLI/batch success만으로 GUI/capture acceptance를 닫지 않는다.

## Pre-authorized environment boundary

P2-A 범위의 project-local 또는 `/tmp` build/cache/dependency 설치와 공개 source dependency checkout은 사전 승인한다. capability probe와 기존 설치 재사용이 먼저다.

자동 허용:

- project-local/`/tmp` build directories and caches
- Swift/Rust/Python isolated build/test dependencies
- public open-source dependency checkout/download within the existing size boundary
- generated headers/bindings/project files needed for the approved vertical slice
- ephemeral test fixtures and app bundles

별도 승인 필요:

- Homebrew/system package manager 변경
- global language/runtime/package install
- OS security setting 또는 TCC database 직접 변경
- System Settings 자동 조작
- existing Xcode/user SDK settings overwrite
- signing identity/keychain modification
- private/restricted/authenticated asset
- paid API/service
- existing user files overwrite
- single new download >4 GiB or expected total new download >8 GiB

Screen Recording 권한이 필요한 경우 정상 macOS permission flow를 trigger할 수 있지만, 실제 grant/revoke는 사용자/OS가 수행한다. 권한 검증 때문에 TCC database를 직접 수정하지 않는다.

## Explicitly out of scope

- continuous/background real-time capture
- OCR/history persistence
- automatic screenshot logging
- cloud OCR/translation
- Windows/Android/iOS product UI
- full native MARCO rewrite
- new Tiny Realizer training/selection
- product updater/account/sync/telemetry
- code signing/notarization/App Store release
- P1-D/P1-F contract redesign unless a P2-A acceptance criterion proves a blocking incompatibility

## Acceptance criteria

| ID | Criterion | Direct evidence | Status |
|---|---|---|---|
| AC-A1 | capture/OCR/overlay/runtime capability와 relevant SDK behavior가 direct probe로 확인되고 ADR에 반영된다 | capability record | Pending |
| AC-A2 | permission/state/cancel/re-entry/privacy contract가 구현 전 명확히 기록된다 | operation/state contract | Pending |
| AC-A3 | native macOS app이 실제로 launch되고 capture action을 제공한다 | direct host launch/input | Pending |
| AC-A4 | denied/restricted permission에서 crash 없이 복구 안내/상태를 제공한다 | direct permission path | Pending |
| AC-A5 | granted permission에서 actual on-screen controlled fixture를 capture한다 | captured-frame identity/visual check | Pending |
| AC-A6 | local OCR이 frozen Chinese fixture의 normalized text와 geometry oracle을 만족한다 | OCR fixture report | Pending |
| AC-A7 | OCR text가 existing translation backend contract를 통해 canonical supported translation으로 처리된다 | controlled end-to-end result | Pending |
| AC-A8 | unsupported/unresolved input이 guessed translation으로 표시되지 않는다 | unknown end-to-end case | Pending |
| AC-A9 | translation result가 transient overlay에 표시되고 dismiss/cancel 후 사라진다 | direct host overlay test | Pending |
| AC-A10 | app/overlay가 다음 capture→OCR input으로 재유입되지 않는다 | repeated capture cycle-guard test | Pending |
| AC-A11 | cancelled/older async request의 stale result가 최신 overlay state를 덮지 않는다 | delayed completion/re-entry test | Pending |
| AC-A12 | normal flow 후 raw capture/OCR artifact가 disk에 남지 않고 outbound network 없이 E2E가 동작한다 | filesystem inventory + network-denied run | Pending |
| AC-A13 | frozen workload의 capture/OCR/translation/overlay stage timing과 E2E p50/p90이 기록된다 | direct Mac performance report | Pending |
| AC-A14 | P1-F portable conformance와 applicable Python/MARCO regression이 유지된다 | regression workflows/tests | Pending |
| AC-A15 | P2-A architecture, limitations, residual risks와 다음 P2 start condition이 Engineering Record에 정리된다 | final record | Pending |

## Material decisions still open

- exact capture API and source-selection UX
- exact local OCR engine/configuration
- AppKit / SwiftUI / hybrid host/window structure
- overlay placement and interaction details beyond transient/dismissible behavior
- development translation-backend bridge to the current semantic engine
- hotkey/input mechanism
- product latency/CPU/RAM budgets

이 항목들은 capability/source evidence 전에 선결정하지 않는다. 여러 대안이 acceptance를 충족하면서 user-facing UX trade-off가 남으면 dependent implementation 전에 사용자 정렬을 요청한다.

## Validation set

- unit/component tests for request state and adapters
- controlled OCR fixtures
- translation backend integration
- permission/error paths
- overlay direct-host behavior
- self-capture cycle guard
- cancellation/stale completion
- no-persistence privacy check
- outbound-network-denied E2E
- stage/E2E latency measurement
- P1-F runtime conformance regression
- applicable P1 Python/MARCO regression
- build/project/document checks

failed/skipped/timed-out/direct-host-unavailable result는 reproducible classification과 impact 없이 완료 처리하지 않는다.

## Stop condition

P2-A를 종료하려면:

1. AC-A1~AC-A15가 Validated 또는 criterion 자체가 evidence-based Not applicable로 정당화
2. 실제 macOS host에서 capture/OCR/translation/overlay user flow 검증
3. privacy/offline/cancel/cycle-guard failure paths 검증
4. P1 regression 유지
5. canonical requirements/platform/test/traceability/ADR 문서 갱신
6. `docs/P2.md`에서 evidence가 있는 항목만 완료 표시
7. final Engineering Record/residual risk/next scope 기록
8. 한국어 commit title/body로 branch commit/push 및 remote ref 확인
9. continuous capture나 다른 플랫폼 host를 자동으로 시작하지 않음

## Residual risks at task start

- exact macOS capture/OCR/overlay APIs와 permission semantics는 아직 capability probe 전이다.
- current Rust portable core는 full native MARCO semantic engine을 포함하지 않는다; P2-A의 development translation-backend bridge를 evidence로 결정해야 한다.
- overlay self-exclusion/focus behavior는 direct host probe가 필요하다.
- actual OCR accuracy와 end-to-end latency budget은 아직 측정되지 않았다.

## Next step

documentation preflight/Graphify orientation 후 현재 macOS toolchain과 P1-F host boundary를 조사한다. 그 다음 native capture/OCR/overlay capability probes와 request-state/privacy contract를 먼저 완성하고, evidence 후 ADR과 최소 app implementation으로 진행한다.
