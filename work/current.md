# Current Task — P2-A macOS Capture / OCR / Overlay

Status: Blocked — normal Screen Recording app addition did not register the host; the likely signing-identity issue is unconfirmed; AC-A2 closeout-baseline adjustment also awaits the user's decision
Branch: `p2/macos-capture-ocr-overlay`  
Parent baseline: `p1/cross-platform-runtime-gate@21f7ed967e38fa56ea484c54a3e3e8db1652987a`

P1-F의 전체 Engineering Record는 `work/p1-f-cross-platform-runtime-gate.md`에 보존한다.

## Goal

`software-engineering-discipline`의 full-scope gate를 적용해 실제 macOS 앱에서 **명시적 화면 캡처 → local OCR → translation backend → transient overlay**의 end-to-end vertical slice를 구현하고 직접 검증한다.

정확한 사용자 observable outcome:

> 사용자가 macOS 앱에서 캡처를 명시적으로 시작하면, 권한이 있는 화면/윈도우/영역의 텍스트를 local OCR로 읽고 기존 번역 계약에 전달하며, 번역 결과를 source 앱을 수정하지 않는 transient overlay로 확인하고 닫거나 취소할 수 있다. 기본 동작은 screenshot/OCR text를 디스크나 cloud에 남기지 않는다.

## Current stage

- P1-A~P1-F: Complete
- P2-A: Blocked — direct macOS host validation awaits a usable Screen Recording grant path and the AC-A2 decision
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

## Use case and operation contract

Actor: local macOS user translating one visible Chinese message. The user initiates every capture from the app; no hotkey, background observer, or continuous stream is active.

Successful path:

    Idle → PermissionCheck → SourceSelection → Capturing → Captured → OCR → Translation → Overlay → Idle

- Source selection is one window or one display in the ScreenCaptureKit picker. The user then drags a region over the in-memory preview; the crop is converted from top-left normalized view coordinates to source pixels. Crops smaller than 2×2 pixels are rejected.
- Permission check calls CGPreflightScreenCaptureAccess; the normal OS request is attempted only after the explicit capture action. A false request/preflight result returns to Idle with recovery guidance. A capture error rechecks access and maps no access to the same guidance; an MDM-restricted state is not distinguishable from denied through this Boolean API.
- The request owner is AppDelegate. RequestGeneration.begin() runs for each start and cancel() invalidates the active generation. Picker, capture, and OCR completions must match the generation before updating visible state. Picker cancel, user cancel, and re-entry invalidate older work; stale completion is ignored.
- The frame remains in memory from capture through the user's crop and OCR handoff. OCR text is sent as a marco-runtime.v1 request with zh → ko, gaming, neutral, and no session ID. The runtime opens :memory:. After translation, the frame, region, and OCR document are released; the transient overlay owns only the display string until dismissal.
- Error mapping: denied/restricted access → permission guidance; picker cancellation → canceled status; screenshot failure with permission → capture error; OCR failure/empty text → user-facing error; unavailable or malformed runtime → runtime error; unresolved translation → explicit no-confirmed-translation message, never a guess; stale callback → ignored.
- The app and overlay windows set sharingType = .none; the picker excludes the app bundle. The overlay is a separate non-activating NSPanel at the main display's visible-frame corner. No source-app input or content is modified.
- Screenshot bytes, OCR text, translation requests, and timing samples are not persisted or logged. The runtime database is in-memory. The app has no network client; successful network-denied GUI flow and post-flow inventory still require the granted-permission run.

## Acceptance criteria

| ID | Criterion | Evidence | Status |
|---|---|---|---|
| AC-A1 | Capture/OCR/overlay/runtime capability and SDK behavior probed and recorded | SDK/API probes; ADR-008; macOS 14 build | Verified |
| AC-A2 | Permission/state/cancel/re-entry/privacy contract recorded before implementation | Contract recorded and code checked against it; it was not persisted before the first vertical-slice source edit, so the timing criterion is a process deviation | Partial |
| AC-A3 | Native macOS app launches and provides capture action | Direct app launch, AX capture/cancel/settings controls, and app-provided link to the Screen & System Audio Recording pane | Verified |
| AC-A4 | Denied/restricted permission fails safely with recovery guidance | On 2026-10-01, explicit capture action returned permission guidance without crash; Cancel reported that the request was canceled and a subsequent selection safely returned to the permission guidance. MDM restriction is unavailable on this host. | Partially verified |
| AC-A5 | Granted permission captures an actual controlled on-screen fixture | User requested adding the exact running app through System Settings. Two normal app-picker selections returned to the pane without adding an entry; the list stayed at 8 apps and the app still reports no access. | Blocked |
| AC-A6 | Local OCR matches frozen text and geometry oracle | Direct Vision fixture 西边有狙; top-left pixel bbox 99.8,95.1,324.4,81.8; region crop 648×230 | Component verified; capture pending |
| AC-A7 | OCR text reaches the existing translation contract and returns canonical supported output | P1-F C ABI known phrase check passes; bridge selected from FR-021/P1-F constraints; UI E2E awaits grant | Pending |
| AC-A8 | Unknown input is not displayed as guessed translation | C ABI unknown case returns unresolved and empty text; on-screen unknown fixture prepared | Component verified; capture pending |
| AC-A9 | Translation is shown in transient overlay and dismiss/cancel clears it | AppKit panel compiles; actual display depends on granted capture | Pending |
| AC-A10 | App/overlay is excluded from the next capture | Picker bundle exclusion and sharingType = .none compile; repeated real capture awaits grant | Pending |
| AC-A11 | Cancelled/older completion cannot overwrite a newer request | Delayed completion/re-entry assertion passes in macos/test-host.sh | Verified |
| AC-A12 | Normal flow leaves no raw capture/OCR artifact and succeeds with outbound networking denied | Python/MARCO and P1-F C host pass network-denied; app-specific post-flow inventory/successful GUI E2E awaits grant | Pending |
| AC-A13 | Frozen workload stage timings and E2E p50/p90 recorded | In-app nearest-rank instrumentation builds; actual values await granted capture | Pending |
| AC-A14 | P1-F portable conformance and applicable Python/MARCO regression stay green | Rust: 8 tests; network-denied C host: 7 fixtures, same hash; pinned Python/MARCO regression: 66 passed, 0 skipped | Verified |
| AC-A15 | Architecture, limits, risks, and next start condition recorded | ADR-008 and this task record document choices, limits, risks, and the next start condition | Verified |

Additional validation: Xcode 27.0 / macOS SDK 27.0, Swift 6.4, Rust 1.98.1, macOS 26.6.2 arm64 / 32 GiB. cargo fmt --all -- --check, locked offline Rust tests/build, macos/test-host.sh, .app build/code-sign verification, plist lint, and git diff --check passed. Pinned Python/MARCO checkout was ffedc8b8552505e515b8f5ea2ae7f9934d7ef58e; pack SHA-256 was 3f38aa5f1237170dbb5cf5a9cdbe19ab3d309c973b2d581bdc6f28463adeb627.

2026-09-30 repeat validation: `cargo +1.98.1 fmt --check`, locked offline Rust tests (8 passed), release build, `macos/test-host.sh` under `sandbox-exec` network denial, and strict C-host run (7 fixtures; SHA-256 `b099cfc595104ee80edbf5adc0b247587c9fcf1955a5f04e53a435e5748e845b`) passed. Pinned Python/MARCO suite passed all 66 tests with 0 skips under network denial. An initial run without `MCO_MARCO_ROOT` and `MARCO_TRANSLATOR_MCO` skipped 14 MARCO-dependent tests; that run is not acceptance evidence and was replaced by the complete pinned run. The first Xcode 27 `swiftc` invocation lacked `SDKROOT` and reported `unable to load standard library`; setting the already-installed Xcode 27 SDK path fixed the host configuration, and the same host checks and app build passed. Final app executable SHA-256: `258f4e471cc7dc2812b7876a3e619717f9de06a580ec5989163781c72c071549`.

2026-10-01 direct UI refresh: CUA access succeeded with the Mac unlocked. The running P2 app exposes capture/cancel/settings controls and, after explicit capture action, shows `화면 기록 권한이 필요합니다. 권한을 허용한 뒤 앱에서 다시 시도하세요.` The source calls `CGPreflightScreenCaptureAccess` then `CGRequestScreenCaptureAccess`; this run still returned to the denial guidance. Cancel reported `현재 요청을 취소했습니다. 원본 화면은 변경되지 않았습니다.` A new selection returned safely to permission guidance. Both controlled fixture windows expose the exact AX text `西边有狙` and `完全未知的新句子`. The app-provided settings button opened macOS's Screen & System Audio Recording pane. At the user's request, the exact running app bundle was selected twice through the normal Add/Open UI after the user authenticated Settings; each picker closed, but the allowed-app list remained at 8 entries and still omitted Marco Translator P2. The app continues to report no access. No TCC database was modified and no permission grant took effect.

## Engineering Record — P2-A

### Authority and baseline

- Authority: the user authorized full-scope P2-A implementation and direct macOS validation on `p2/macos-capture-ocr-overlay`. After the grant path failed, the user explicitly directed a checkpoint commit/push of the current blocked implementation. This authorizes branch publication without waiving AC-A2 or the P2-A stop condition. The project-local/`/tmp` validation boundary is pre-authorized. The user also explicitly authorized adding this app through normal System Settings UI; the app picker did not change the effective permission list. Direct TCC database mutation remains excluded.
- Continuation baseline: repository `Box5789/marco-translator`; local branch and `origin/p2/macos-capture-ocr-overlay` both pointed to `4d6a37754d5638787377053c60c35199dff67f1b`. At recovery, the 16 intended implementation/document files were already staged. Generated `graphify-out/` was untracked and preserved unstaged.
- Exact outcome and stop condition: use the Goal, Use case and operation contract, AC-A1–AC-A15, and Stop condition above. No later P2 phase is authorized.

### Documentation and evidence preflight

| Candidate | Status | Relevance |
|---|---|---|
| `AGENTS.md`, `AGENT_GUIDE.md`, `work/current.md` | Read | workflow authority, durable product rules, active scope |
| `AGENT_HANDOFF.md`, `docs/AGENT_HANDOFF.md` | Absent | no handoff exists in this checkout |
| `work/p1-f-cross-platform-runtime-gate.md` | Read | carry-forward Rust C ABI contract and P1-F evidence |
| `work/p1-d-knowledge-maintenance.md`, `work/p1-e-tiny-realizer-benchmark.md` | Not applicable | completed phases; no P1-D/E behavior changes |
| `README.md`, `docs/REQUIREMENTS.md`, `docs/ENGINEERING_BASELINE.md`, `docs/PLATFORM_STRATEGY.md`, `docs/TEST_STRATEGY.md`, `docs/TRACEABILITY.md`, `docs/P2.md` | Read | product scope, FR/QA, ADR, platform and validation authority |
| `docs/ARCHITECTURE.md`, `docs/AUTOMATIC_LEARNING.md`, `docs/MARCO_PROTOCOL.md` | Read | semantic authority, state ownership, MARCO boundary |
| `docs/P1.md` | Not applicable | P1 is closed; this change updates P2 records only |
| `runtime/include/marco_runtime.h`, `schemas/marco-runtime-v1.schema.json`, `runtime/fixtures/conformance-v1.json`, P1-F conformance/persistence tests | Read | existing public contract and regression evidence |
| P2-A Swift sources, host checks, build/test scripts, plist | Read | every staged implementation file was inspected in full |
| `graphify-out/graph.json` | Read, inline BFS | 47 navigation nodes; canonical docs and source/tests remain authoritative |
| `graphify-out/wiki/index.md`, `graphify-out/reflections/LESSONS.md` | Absent | no generated wiki index or lessons file |
| External standards certification | Not applicable | no certification claim is made |
| Skill-maintenance validation | Not applicable | the engineering skill itself is unchanged |

### Design and object responsibilities

- ADR-008 records capability probes and alternatives. Native `SCContentSharingPicker`/`SCScreenshotManager`, Vision `zh-Hans`, and AppKit were selected after local SDK/build probes. The host reuses P1-F Rust C ABI because FR-021 excludes Python/MARCO runtime dependency and P2-A excludes a full native MARCO rewrite. No dependency was added.
- `AppDelegate` is the request coordinator/service: it owns the current generation and transient frame/selection/UI state; only matching callbacks may update the UI. `RequestGeneration` is a stateful guard whose contract is that only the newest generation is accepted; `HostChecks` exercises cancel and stale completion.
- `PortableRuntime` is a composition adapter that owns the opaque C ABI handle, serializes `marco-runtime.v1`, validates the response envelope, and closes the handle. Its database defaults to `:memory:`; fixture tests cover known and unresolved input.
- `RegionCropView` owns only transient selection geometry and maps view coordinates to a normalized crop. Its crop/OCR bounds are component-tested. `TranslationOverlay` owns only a transient display string and close callback; direct display/dismissal remains unverified while the host is locked.
- No new interface or inheritance hierarchy was added. Framework protocol inheritance is required by AppKit/ScreenCaptureKit; composition connects the adapters. UML is not needed for this small host boundary.

### Scope coverage

| Surface | Status | Evidence or limit |
|---|---|---|
| Requirements, platform, test, traceability, P2, ADR/task records | Changed | staged canonical updates; AC map retained above |
| macOS capture/OCR/translation/overlay host and local build | Changed | build/sign and component checks pass; granted GUI flow pending |
| P1-F Rust runtime contract and fixtures | Already compliant; reused | no shared runtime source change; 8 Rust tests and 7-case C ABI smoke pass |
| Python/MARCO reference | Already compliant; regression rerun | pinned checkout/pack; 66 pass, 0 skip, network denied |
| Other platform UI, continuous capture, production distribution | Explicitly excluded | outside P2-A scope |
| Granted capture, on-screen fixture, overlay lifecycle/cycle, app inventory, GUI offline flow, latency | Blocked | app remains absent after normal Settings Add/Open; ad hoc signature and no installed signing identity are recorded below |
| `graphify-out/` | Generated navigation artifact; preserved | untracked and excluded from staged paths |

### Validation and release state

- Component/build: Rust formatting/tests/release build, Swift host OCR/crop/known/unknown/stale-generation check, strict 7-fixture C ABI host, app code-sign verification, plist lint, and `git diff --check` passed. Component OCR oracle: `西边有狙`, top-left pixel bounds `99.8,95.1,324.4,81.8`, crop `648×230`.
- Regression/offline: Pinned actual MARCO checkout `ffedc8b8552505e515b8f5ea2ae7f9934d7ef58e`, pack SHA-256 `3f38aa5f1237170dbb5cf5a9cdbe19ab3d309c973b2d581bdc6f28463adeb627`; 66 Python tests passed with 0 skips under network denial. C host reported `marco-runtime.v1`, 7 fixtures, SHA-256 `b099cfc595104ee80edbf5adc0b247587c9fcf1955a5f04e53a435e5748e845b`, and `network_dependency=none`.
- Direct host: the Mac was unlocked on 2026-10-01. CUA confirmed denied-permission guidance, cancel and safe re-entry, both controlled fixture windows, and the app-provided link to the Screen & System Audio Recording pane. After user authorization and authentication, two normal Add/Open attempts on the exact running app bundle left the pane's allowed-app list at 8 entries without Marco Translator P2. The app still reports no Screen Recording access. `codesign -dvvv` reports `Signature=adhoc`, no TeamIdentifier, and no internal requirements; `security find-identity -p codesigning -v` reports 0 valid identities. `spctl -a -vv` rejects this development bundle. These facts make unstable ad hoc code identity a plausible explanation, consistent with Apple's ScreenCaptureKit guidance, but do not prove why Settings declined to retain the selected bundle. App Store/developer distribution signing remains out of P2-A scope. Granted capture and its privacy, overlay cycle, offline GUI, and timing checks remain unverified.
- Process deviation: AC-A2 explicitly requires the contract to precede the first source edit. It was recorded afterward. This historical condition cannot be retroactively validated; AC-A2 remains `Partial` unless the user approves the requested closeout-criterion adjustment. No source rewrite can erase that chronology.
- Release: a checkpoint commit/push is now explicitly authorized while the task remains blocked. Publication does not waive the direct-host acceptance or AC-A2 gate and is not P2-A closeout. The staged files passed `git diff --cached --check`; generated `graphify-out/` remains unstaged.

Graphify AST update completed: 1,294 nodes / 2,523 edges. It reports seven input/data files with zero nodes and a partial parse warning in runtime/include/marco_runtime.h; this is navigation-only evidence. Existing untracked graphify-out/ was preserved and remains unstaged.

## Material decisions still open

- **Screen Recording grant path:** the user authorized normal System Settings app addition and authenticated the pane. Two Add/Open attempts on the running bundle returned without an app-list entry (count stayed 8); the app still reports no access. The app is ad hoc signed, and this Mac has 0 valid code-signing identities. Apple DTS states that ScreenCaptureKit permission identity is tied to code signing ([Apple Developer Forums](https://developer.apple.com/forums/thread/819406)); ad hoc signing is a plausible blocker, not a proven diagnosis. Stable local development signing was explicitly outside the approved P2-A scope; do not create or install a signing identity without user approval.
- **AC-A2 closeout criterion:** user decision requested. The original temporal criterion remains `Partial`; do not alter the stop condition or claim completion until the user responds.
- **Product latency/CPU/RAM budgets:** measure the controlled flow first; no threshold is selected in P2-A.
- **MDM-restricted permission path:** no managed/restricted host policy is available here; current permission APIs collapse this to a no-access result.

Capture, OCR, host/window selection, source-selection interaction, and overlay placement are recorded in ADR-008 from capability evidence. The above remaining decisions are explicitly distinguished from those completed selections.

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

## Residual risks and next step

- No granted Screen Recording run has yet demonstrated captured-frame identity, overlay dismissal, or repeated-cycle exclusion.
- The app remains absent from Screen & System Audio Recording after two user-authorized normal Add/Open attempts. It is ad hoc signed and this Mac has no valid signing identity; the permission grant path is unresolved and stable signing remains outside scope.
- App-specific no-persistence inventory and successful app execution under a network-denied sandbox remain pending with the granted flow.
- Latency values from a real capture have not been recorded; product budgets remain open.
- The current native translation bridge is intentionally limited to the Rust seven-case fixture resolver and is not the Python/MARCO semantic engine.

Next: obtain the user's decision on AC-A2 and on whether to expand scope for a local development-signing path or provide a stable identity on this Mac. Then run the final `.app` through controlled known/unknown fixtures, repeated selection/cancel/re-entry, overlay dismissal, app-specific file inventory, network-denied execution, and latency sampling; finish canonical documentation and deliver the Korean commit to `origin/p2/macos-capture-ocr-overlay` only if the authorized stop condition is met.
