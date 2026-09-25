# Current Task — P1-F Cross-platform Runtime Gate

Status: Active — contract inventory and architecture evidence phase  
Branch: `p1/cross-platform-runtime-gate`  
Parent baseline: `p1/tiny-realizer-benchmark@b0a2e2eedff9a1e139e3ba76676472af1e93325e`

P1-E의 전체 Engineering Record는 `work/p1-e-tiny-realizer-benchmark.md`에 보존한다.

## Goal

`software-engineering-discipline`의 full-scope gate를 적용해 Python reference implementation의 핵심 runtime 의미 계약을 macOS / Windows / Android / iOS에서 동일하게 구현할 수 있는지 직접 검증한다.

정확한 사용자 observable outcome:

> 같은 versioned request/frame/result/persistence fixtures를 Python reference와 product-runtime 후보가 해석하고, semantic meaning·unknown safety·deterministic realization·runtime state semantics를 동일하게 보존한다. 선택된 최소 portable runtime slice는 Python interpreter 없이 macOS, Windows, Android, iOS의 target runtime에서 실제 smoke path를 실행할 수 있어야 한다.

P1-F는 완성 앱을 만드는 단계가 아니라 **cross-platform product runtime architecture를 증거로 선택하고, 그 선택이 실제 네 플랫폼에서 성립하는지 최소 vertical slice로 검증하는 gate**다.

## Current stage

- P1-A: Complete
- P1-B: Complete
- P1-C: Complete
- P1-D: Complete
- P1-E: Complete
- P1-F: Active

## Accepted decisions carried forward

- 최종 제품 플랫폼: macOS / Windows / Android / iOS.
- 현재 로컬 직접 개발/검증 기준 머신은 macOS.
- macOS-first는 macOS-only architecture를 의미하지 않는다.
- Runtime은 offline-first.
- Base KG는 runtime read-only.
- TM / User Overlay / Session State / Base KG의 책임을 섞지 않는다.
- Tiny Neural Realizer는 semantic authority가 아니다.
- unknown/unresolved frame은 neural guess로 승격하지 않는다.
- P1-E의 Qwen3 후보는 product 선택이 아니다. P1-F는 해당 model/runtime을 상속하지 않는다.
- P1-D의 Knowledge Version / kg-patch-v2 / rollback contract를 재설계하지 않는다.
- Python은 reference implementation이며 product runtime의 필수 dependency로 고정하지 않는다.
- OCR / screen capture / overlay / UI는 platform adapter 영역이며 P1-F 구현 범위 밖이다.

## Scope

### Phase F1 — Documentation preflight and coupling inventory

- canonical docs/task-state/Graphify 상태 복원
- runtime source 전체 흐름 추적
- Python-specific dependency inventory
- public contract / persistent contract / generated artifact / platform adapter 경계 분류
- 현재 SQLite/file/schema 계약이 portable semantic contract인지 Python implementation detail인지 구분

### Phase F2 — Portable contract and conformance fixtures

최소 다음 의미를 versioned portable form으로 고정한다.

- TranslationRequest
- TermDecision / terminology provenance
- SemanticFrame
- TranslationResult
- boundary error/status
- deterministic rule realization inputs/outputs
- unresolved/unknown safety behavior
- in-scope runtime persistence/interchange semantics

Python object identity, dataclass repr, implementation-specific exception string에 contract를 의존시키지 않는다.

Python reference에서 frozen conformance fixtures/report를 만들고 hash/version identity를 기록한다.

### Phase F3 — Architecture evidence and ADR

최소 비교 후보:

1. Rust shared core
2. C/C++ shared core
3. platform-native implementations behind one stable contract
4. Python reference를 검증 oracle로만 유지하고 별도 product runtime을 독립 구현
5. source/capability evidence가 정당화하는 다른 후보

비교 기준:

- semantic contract fidelity
- macOS/Windows/Android/iOS target support
- FFI/host integration complexity
- memory/error ownership safety
- SQLite/persistence portability
- offline operation
- build/release complexity
- model-runtime integration flexibility
- debugging/tooling
- dependency/supply-chain risk
- binary/resource overhead
- conformance fixture reuse
- long-term maintenance cost

구체 architecture를 선택하기 전에 현재 source/pattern과 실제 toolchain/platform capability를 probe한다.

**Decision authority:** architecture selection은 이번 P1-F의 명시적 deliverable로 승인되어 있다. required evidence 후 한 후보가 acceptance criteria를 명확히 충족하고 다른 후보보다 material하게 우세하면 ADR을 기록하고 다음 phase로 진행한다. 둘 이상의 후보가 기준을 충족하면서 장기적인 material trade-off가 남으면 dependent implementation 전에 사용자 정렬을 요청한다.

### Phase F4 — Minimal portable runtime vertical slice

선택된 ADR에 따라 acceptance를 증명하는 가장 작은 slice만 구현한다. full port를 목표로 하지 않는다.

최소 검증 대상:

- portable contract serialization/deserialization
- normalization
- deterministic rule realization
- unresolved safety gate
- resolver replacement seam
- neural realizer replacement seam/null implementation
- orchestration needed for frozen conformance path
- runtime persistence/interchange parity required by FR-023
- stable host/FFI/API boundary and error semantics

MARCO 전체 native reimplementation은 기본적으로 out of scope다. 대신 fixture/deterministic resolver를 통해 semantic engine이 stable boundary 뒤에서 교체 가능함을 증명한다.

### Phase F5 — Four-platform proof

같은 contract/fixture identity로 다음을 수행한다.

- macOS: 현재 Mac에서 direct native conformance run
- Windows: native CI/runtime conformance run
- Android: emulator 또는 실제 Android runtime smoke
- iOS: simulator 또는 실제 iOS runtime smoke

각 evidence를 다음으로 분리한다.

- compile
- link
- runtime execution
- persistence/interchange
- offline execution
- resource measurement

compile/link 성공만으로 runtime 성공을 주장하지 않는다. Android/iOS runtime smoke가 환경상 불가능하면 P1-F는 해당 criterion을 Blocked로 남기며 Complete로 종료하지 않는다.

### Phase F6 — Regression and architecture closeout

- P1-A~P1-E Python reference full regression
- actual upstream MARCO integration
- portable conformance regression
- platform smoke reports
- architecture ADR와 traceability 갱신
- P1 완료 여부와 P2 start conditions 기록

## Pre-authorized P1-F environment boundary

사용자가 P1-F 범위 내 개발·검증에 필요한 **격리된 공개 toolchain/dependency 사용**을 사전 승인한 것으로 처리한다.

자동 허용:

- project-local 또는 `/tmp` disposable virtual/build environment
- 해당 격리 환경의 package/dependency 설치
- public/open-source compiler/toolchain/SDK component 다운로드를 격리 경로에 설치
- public source dependency checkout
- ephemeral CI에서 공식/검증된 setup action 또는 package 설치
- target build cache, emulator/simulator test artifact, generated binding/header
- P1-F proof에 필요한 공개 fixture/tool artifact

자동 허용 전에도 capability probe와 기존 설치 재사용을 우선한다. 외부 artifact는 source/version/revision/license/location/size를 Engineering Record에 기록한다. cache/toolchain/generated artifact는 명시적 canonical source가 아니면 commit하지 않는다.

별도 승인이 필요한 항목:

- Homebrew 등 사용자 머신의 system package manager 변경
- global Python/Node/Ruby/Java 등 전역 환경 변경
- `--user`, `--break-system-packages` 설치
- OS 설정, security setting, driver, kernel/system runtime 변경
- 기존 Xcode/Android Studio/SDK/toolchain의 사용자 설정이나 persistent state 덮어쓰기
- 인증 token/login/private/restricted asset
- 유료 API/서비스
- 기존 사용자 파일 덮어쓰기
- 단일 신규 다운로드 4 GiB 초과 또는 예상 총 신규 다운로드 8 GiB 초과

가능하면 `RUSTUP_HOME`, `CARGO_HOME`, SDK/cache root 등을 project-local 또는 `/tmp`로 격리한다.

별도 승인 대상에 도달해도 독립적으로 가능한 source inspection, contract extraction, fixtures, ADR evidence, CI design은 계속한다.

## Explicitly out of scope

- OCR
- screen capture
- translation overlay UI
- full desktop/mobile app UI
- app-store packaging/signing/notarization/release
- full native MARCO engine rewrite unless direct gate evidence proves the minimal slice cannot validate without it
- new Tiny Realizer selection/training
- P1-D patch/version semantics redesign
- production telemetry/cloud backend
- PR #1/#2 merge
- release/tag

## Acceptance criteria

| ID | Criterion | Direct evidence | Status |
|---|---|---|---|
| AC-F1 | Python-only coupling과 portable/public/persistent boundary가 완전하게 inventory된다 | reconciled scope table + source references | Pending |
| AC-F2 | request/result/frame/term/error와 필요한 persistence semantics가 versioned portable contract/fixture로 고정된다 | schema/fixture hashes + Python reference conformance | Pending |
| AC-F3 | architecture 후보가 실제 source/capability evidence로 비교되고 ADR이 결정된다 | decision record + probes | Pending |
| AC-F4 | 선택된 product-runtime vertical slice가 실행 시 Python interpreter/MARCO internal Python module 없이 동작한다 | dependency/runtime inspection + smoke | Pending |
| AC-F5 | resolver/realizer가 stable boundary 뒤에서 교체되고 unresolved safety가 유지된다 | fixture resolver/null realizer tests | Pending |
| AC-F6 | in-scope runtime persistence/interchange가 Python reference와 의미 parity를 가진다 | cross-runtime round-trip/reopen test | Pending |
| AC-F7 | macOS direct native conformance가 통과한다 | local Mac runtime report | Pending |
| AC-F8 | Windows native runtime conformance가 통과한다 | Windows runner report | Pending |
| AC-F9 | Android emulator/actual runtime smoke가 통과한다 | Android runtime report | Pending |
| AC-F10 | iOS simulator/actual runtime smoke가 통과한다 | iOS runtime report | Pending |
| AC-F11 | portable slice가 offline/cloud-independent하게 실행된다 | target/offline checks | Pending |
| AC-F12 | target build/resource evidence가 실제 측정값으로 기록된다 | binary/startup/latency/memory 가능한 subset | Pending |
| AC-F13 | P1-A~P1-E regression과 actual MARCO integration이 유지된다 | full Python suite + integration | Pending |
| AC-F14 | OCR/capture/UI 등 platform host concern이 semantic core contract 밖에 유지된다 | architecture/host smoke review | Pending |
| AC-F15 | P1-F 결론과 P2 시작 조건이 evidence로 정리된다 | final ADR + Engineering Record | Pending |

## Validation rules

- 모든 target은 동일한 contract/fixture version과 hash를 보고해야 한다.
- semantic mismatch는 성능이나 build 성공으로 상쇄할 수 없다.
- unknown/unresolved safety mismatch는 blocking failure다.
- compile-only는 runtime acceptance의 대체 증거가 아니다.
- emulator/simulator check가 필요한데 실행되지 않으면 skipped가 아니라 Blocked로 분류한다.
- FFI malformed input, invalid enum/status, oversized/invalid string or JSON, error propagation 등 trust-boundary failure cases를 포함한다.
- platform-specific host code가 core semantic rule을 재구현하지 않도록 검토한다.
- resource 수치는 product budget이 아니라 baseline measurement로 기록한다.
- failed/skipped/timed-out check는 reproducible classification과 impact 없이 완료 처리하지 않는다.

## Required documentation preflight before source/design changes

1. `AGENTS.md`
2. `AGENT_GUIDE.md`
3. 이 파일
4. `README.md`
5. `docs/REQUIREMENTS.md`
6. `docs/ENGINEERING_BASELINE.md`
7. `docs/PLATFORM_STRATEGY.md`
8. `docs/TEST_STRATEGY.md`
9. `docs/TRACEABILITY.md`
10. `docs/ARCHITECTURE.md`
11. `docs/MARCO_PROTOCOL.md`
12. `docs/AUTOMATIC_LEARNING.md`
13. P1-E 결과가 필요하면 `work/p1-e-tiny-realizer-benchmark.md`
14. relevant schemas/source/tests/build workflows

`graphify-out/graph.json`이 있으면 source inspection 전 navigation evidence로 사용하되 canonical docs/direct source/test evidence를 대체하지 않는다.

## Material decisions still open

- selected product runtime strategy / shared core language
- FFI surface shape
- cross-platform persistence interchange versus direct SQLite-file compatibility boundary
- semantic engine의 eventual native implementation strategy
- per-platform model acceleration backend
- final product latency/RAM/binary-size budgets

P1-F에서 직접 evidence가 필요한 항목만 결정한다. P2/P1-E 범위의 결정을 끌어오지 않는다.

## Stop condition

다음이 모두 충족되면 P1-F를 종료한다.

1. AC-F1~AC-F15 모두 Validated 또는 해당 criterion 자체가 evidence-based Not applicable로 정당화됨
2. required four-platform runtime evidence가 모두 존재
3. selected architecture와 portable contract가 canonical docs에 반영
4. Python reference와 portable implementation conformance parity 유지
5. P1-A~P1-E regression 유지
6. offline/error/persistence/FFI validation 완료
7. `docs/P1.md`는 evidence가 있는 P1-F 항목만 완료 표시
8. `work/current.md`에 final Engineering Record, residual risks, P2 start conditions 기록
9. 한국어 commit title/body로 해당 branch에 commit/push하고 remote ref 확인
10. P2 OCR/capture/overlay 구현은 시작하지 않음

## Residual risks at task start

- product runtime strategy는 아직 evidence 없이 선택되지 않았다.
- iOS/Android runtime smoke를 수행할 local/CI toolchain availability는 아직 probe 전이다.
- 현재 Python persistence 구현은 SQLite 중심이며 cross-runtime direct-file compatibility가 최선인지 아직 결정되지 않았다.
- MARCO 자체는 Python reference engine이므로 eventual native semantic engine은 P1-F에서 interface feasibility만 증명하고 full rewrite는 하지 않을 수 있다.
- P1-E에서는 neural invocation rate가 0이었으므로 P1-F model-runtime backend는 선택 근거가 약하다.

## Next step

documentation preflight와 Graphify orientation 후 runtime source/persistence/build dependency를 end-to-end로 조사한다. 그 다음 F1/F2 contract inventory와 conformance fixtures를 먼저 고정하고, architecture 후보 capability probe와 ADR evidence를 수집한다. evidence 전에는 Rust/C++/platform-native 중 어느 것도 선결정하지 않는다.
