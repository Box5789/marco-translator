# Current Task — P1-F Cross-platform Runtime Gate

Status: Complete — P1-F portable runtime gate와 요구 회귀 검증을 2026-09-28 완료
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
- P1-F: Complete

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
| AC-F1 | Python-only coupling과 portable/public/persistent boundary가 완전하게 inventory된다 | reconciled scope table + source references | Validated |
| AC-F2 | request/result/frame/term/error와 필요한 persistence semantics가 versioned portable contract/fixture로 고정된다 | schema/fixture hashes + Python reference conformance | Validated |
| AC-F3 | architecture 후보가 실제 source/capability evidence로 비교되고 ADR이 결정된다 | decision record + probes | Validated |
| AC-F4 | 선택된 product-runtime vertical slice가 실행 시 Python interpreter/MARCO internal Python module 없이 동작한다 | dependency/runtime inspection + smoke | Validated |
| AC-F5 | resolver/realizer가 stable boundary 뒤에서 교체되고 unresolved safety가 유지된다 | fixture resolver/null realizer tests | Validated |
| AC-F6 | in-scope runtime persistence/interchange가 Python reference와 의미 parity를 가진다 | cross-runtime round-trip/reopen test | Validated |
| AC-F7 | macOS direct native conformance가 통과한다 | local Mac runtime report | Validated |
| AC-F8 | Windows native runtime conformance가 통과한다 | Windows runner report | Validated |
| AC-F9 | Android emulator/actual runtime smoke가 통과한다 | Android runtime report | Validated |
| AC-F10 | iOS simulator/actual runtime smoke가 통과한다 | iOS runtime report | Validated |
| AC-F11 | portable slice가 offline/cloud-independent하게 실행된다 | target/offline checks | Validated |
| AC-F12 | target build/resource evidence가 실제 측정값으로 기록된다 | binary/startup/latency/memory 가능한 subset | Validated |
| AC-F13 | P1-A~P1-E regression과 actual MARCO integration이 유지된다 | full Python suite + integration | Validated |
| AC-F14 | OCR/capture/UI 등 platform host concern이 semantic core contract 밖에 유지된다 | architecture/host smoke review | Validated |
| AC-F15 | P1-F 결론과 P2 시작 조건이 evidence로 정리된다 | final ADR + Engineering Record | Validated |

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

- semantic engine의 eventual native implementation strategy
- per-platform model acceleration backend
- final product latency/RAM/binary-size budgets

P1-F 범위의 shared runtime, FFI, SQLite direct-file boundary는 source/toolchain/interoperability evidence 후 ADR-007에서 결정했다. 위 미결정 항목은 이번 slice가 확정하지 않는다.

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

## Initial residual risks (before P1-F probes)

- product runtime strategy는 아직 evidence 없이 선택되지 않았다.
- iOS/Android runtime smoke를 수행할 local/CI toolchain availability는 아직 probe 전이다.
- 현재 Python persistence 구현은 SQLite 중심이며 cross-runtime direct-file compatibility가 최선인지 아직 결정되지 않았다.
- MARCO 자체는 Python reference engine이므로 eventual native semantic engine은 P1-F에서 interface feasibility만 증명하고 full rewrite는 하지 않을 수 있다.
- P1-E에서는 neural invocation rate가 0이었으므로 P1-F model-runtime backend는 선택 근거가 약하다.

## Completion and handoff

P1-F는 AC-F1~AC-F15 검증, 네 target runtime smoke, Python reference/actual MARCO 회귀, 문서·ADR 갱신, 한국어 커밋 및 원격 반영을 마쳐 종료했다. 최종 증거와 남은 제한은 아래 Final closeout에 기록한다. P2 OCR/capture/overlay 구현은 시작하지 않았다. 새 P2 범위는 제품 요구·플랫폼 권한·개인정보 경계·성능 예산의 근거를 정한 뒤 별도 작업으로 승인되어야 한다.

## Engineering Record — P1-F recovery and evidence work (2026-09-28)

### Goal, authority, scope, and stop condition

- Goal and exact observable outcome: this record preserves the P1-F goal and acceptance map above. Python reference and the selected portable runtime must read the same versioned contract/fixture identities, preserve semantic/unknown/persistence behavior, and execute the minimum slice without Python on macOS, Windows, Android, and iOS.
- Authority: the user explicitly authorized full-scope P1-F on `p1/cross-platform-runtime-gate`, including required validation and Korean commit/push. The isolated public toolchain/dependency boundary in this file is pre-authorized. No approval is inferred for system package-manager changes, global installs, private or paid services, overwriting user state, or downloads above the recorded size limits.
- Scope: AC-F1–AC-F15 and phases F1–F6 above. Non-goals remain OCR, capture, overlay/UI, full app/release, full MARCO rewrite absent gate evidence, new realizer selection, P1-D contract redesign, PR merge, and release/tag.
- Stop: meet every applicable acceptance criterion with direct evidence, complete the four target runtime checks and P1-A–P1-E regression/integration, update canonical records, then commit/push this branch and verify both refs. Do not start P2.

### Baseline and recovered state

- Repository: `Box5789/marco-translator`; branch `p1/cross-platform-runtime-gate` tracks `origin/p1/cross-platform-runtime-gate`.
- Baseline: `cd7856c1d9ee2bb2c9de3ca6a05e00a3c84284bc`; local and remote matched. The tracked worktree and index were clean.
- Preserved pre-existing state: untracked `graphify-out/` from P1-E. Do not commit, regenerate, or overwrite it without checking the recorded baseline.
- Parent P1-E baseline: `b0a2e2eedff9a1e139e3ba76676472af1e93325e`.

### Documentation preflight

| Candidate | Status | Relevance |
|---|---|---|
| `AGENTS.md`, `AGENT_GUIDE.md`, `work/current.md` | Read | authority, product invariants, active scope |
| `AGENT_HANDOFF.md`, `docs/AGENT_HANDOFF.md` | Absent | no handoff in target tree |
| `work/p1-e-tiny-realizer-benchmark.md` | Read | carry-forward semantic and realizer evidence |
| `work/p1-d-knowledge-maintenance.md` | Not applicable | P1-D behavior is excluded; ADR-005 is the active canonical boundary |
| `README.md` | Read | runtime, Python-reference, and MARCO overview |
| `docs/REQUIREMENTS.md`, `docs/ENGINEERING_BASELINE.md` | Read | FR/QA, operation contracts, ADR-003–006 |
| `docs/PLATFORM_STRATEGY.md`, `docs/TEST_STRATEGY.md`, `docs/TRACEABILITY.md`, `docs/P1.md` | Read | P1-F gate, validation, requirement mapping, phase closure |
| `docs/ARCHITECTURE.md`, `docs/MARCO_PROTOCOL.md`, `docs/AUTOMATIC_LEARNING.md` | Read | semantic authority, resolver seam, state ownership |
| `schemas/translation-log.schema.json`, `schemas/kg-patch.schema.json`, `prompts/kg-maintenance.md` | Read | log/persistent contract inventory; P1-D proposal boundary |
| `pyproject.toml`, `pytest.ini`, `.github/workflows/p1-marco-integration.yml` | Read | runtime/test dependencies and current integration CI |
| Runtime sources and `test_pipeline.py`, `test_marco_adapter.py`, `test_user_overlay.py`, `test_marco_integration.py` | Read | request-to-result and persistence/interchange paths |
| `$apply-software-engineering-discipline` and all nine references | Read | complete workflow, including conditional OOP and delivery checks |
| `caveman`, `ponytail` | Read | concise Korean and minimum sufficient changes |
| `references/object-oriented-design.md` | Read; applicable | service seams and state-owning persistence objects are in scope |
| External standards certification | Not applicable | no certification or standards-compliance claim is planned |
| Skill maintenance validation | Not applicable | the skill itself is not being changed |

### Graphify and direct navigation evidence

- Existing graph: `graphify-out/graph.json`, generated from P1-E and potentially stale for this branch; 677 nodes and 1,381 links. Read-only inline BFS ran with the already-installed `/Users/pck2790/.local/share/uv/tools/graphifyy/bin/python`; `graphify` and `networkx` imports succeeded. No lessons file or `wiki/index.md` exists.
- The graph navigated to `models.py` (`TranslationRequest`, `TermDecision`, `SemanticFrame`, `TranslationResult`), `pipeline.py` (`Translator.translate`), `marco_adapter.py` (`MarcoResolver`), `tm.py`, and `user_state.py`. Canonical docs and direct source/tests below supersede graph suggestions.

### Requirements, use case, and operation contract

- Primary actor: translation user; conformance evaluator supplies frozen requests and persistence fixtures.
- Preconditions: contract/fixture version and hashes are pinned; resolver and realizer implementations satisfy declared boundaries; runtime is local and offline.
- Success: the same valid request yields equal semantic fields and deterministic output across the Python reference and portable slice; exact TM and approved user state survive close/reopen; session bindings remain ephemeral.
- Failure: malformed or unsupported boundary input returns a stable error/status; an unresolved frame stays unresolved and never reaches an unconstrained neural realizer; Base KG remains unchanged.
- Operations: normalize then check session exact match, check exact TM, resolve a `SemanticFrame`, try deterministic realization, call neural realization only for a grounded rule miss, otherwise return unresolved. Explicit correction writes exact TM and may create a pending User Overlay proposal; approval is explicit.
- Canonical/persisted/display state: Base KG is read-only; TM and User Overlay are user-scoped SQLite state; Session State is memory-only; JSONL logging is append-only output. Runtime core must not merge these ownership boundaries.

### Confirmed source findings and coupling inventory

- `models.py` uses Python dataclasses and `asdict`; `TranslationResult.path` and `metadata` are open-ended. These are Python representations, not yet a versioned portable contract.
- `normalizer.py` uses Python `unicodedata.normalize("NFKC")` plus Unicode whitespace collapse. Cross-runtime normalization needs fixture-level parity.
- `pipeline.py` owns orchestration. Current precedence is session exact match, TM exact match, resolver, rule realizer, grounded-only neural fallback, unresolved. `MarcoResolver` uses dependency injection in tests and imports `mco` only in its file-loading constructor.
- `tm.py` and `user_state.py` use standard-library `sqlite3`; empty string represents a null domain. TM, overlay terminology, correction/proposal, and reversible route-weight event tables are created lazily without an explicit schema-version marker. `SessionStateStore` is in-memory.
- `logger.py` appends JSONL with UUID and timestamp; translation and correction records currently use different schema-version strings. The existing log schema is permissive and is not by itself a strict request/result contract.
- Runtime sources otherwise use Python standard-library facilities. `mco`, NumPy, and Pillow belong to optional MARCO build/integration paths; `maintenance.py`, `patches.py`, and `knowledge_version.py` remain in the separate P1-D maintenance plane.
- OOP record: `TranslationRequest`, `TermDecision`, `SemanticFrame`, and `TranslationResult` are immutable/mutable value-like records as currently implemented; `Translator` is the orchestration service; resolver/realizer are composition seams; TM, Overlay, and Session stores own distinct state/lifecycles. A portable design must preserve these boundaries without adding inheritance by default.

### Initial capability probe (macOS 26.6.2, arm64, 32 GiB)

- Present: Apple Clang 21.0.1, CMake 4.4.3, Swift 6.3.3, .NET SDK 10.0.301, SQLite 3.51.0, Java 26. Android SDK/ADB/NDK, Gradle, and Xcode `simctl` are absent. An isolated Rust 1.98.1 toolchain was subsequently installed under `/tmp/marco-translator-p1f-rustup-20260928`; no global or system package state was changed.
- `xcodebuild -version` cannot run because only Command Line Tools are active; `xcrun --sdk iphoneos --show-sdk-path` reports the iPhoneOS SDK is absent. iOS simulator availability remains unverified locally.
- Native C++ can compile/link/run against host SQLite (`sqlite3_open(":memory:")` returned 0). This is host-only evidence, not four-platform capability.
- Python 3.14.7 system runtime has no `pytest` or `mco`; the existing disposable P1-E `/tmp` venv has pytest 9.1.1, `mco` 0.1.0, NumPy 2.5.3, Pillow 12.3.0, and the editable translator package. The guessed `/tmp` P1-E upstream checkout location was absent; the exact prior checkout path is unknown. Actual MARCO integration setup still needs locating or recreating within the authorized isolated boundary.

### Candidate probes and evidence-backed selection

- Rust isolated probe: `serde_json 1.0.151`, `unicode-normalization 0.1.24`, and a strict versioned JSON record passed host tests and `cargo check` for `aarch64-apple-ios`, `aarch64-apple-ios-sim`, `aarch64-linux-android`, and `x86_64-pc-windows-msvc`. The normalization crate uses UCD 16.0.0, matching Python 3.14.7. Rust's whitespace set plus U+001C–U+001F was compared against Python `re` `\\s` over every Unicode scalar: 29 values on each side, zero mismatches.
- Rust SQLite probe: `rusqlite 0.40.2` with bundled SQLite 3.53.2 read Python-created `tm` and `terminology` tables, wrote a TM entry, set `PRAGMA user_version=1`, then the Python stores reopened the same file and read both original and Rust-written data. Host evidence passed.
- Full `rusqlite` bundled-SQLite cross-check could not run locally for iOS, Android, or Windows: `libsqlite3-sys` required the absent Xcode iOS SDK, Android NDK compiler, or Windows MSVC toolchain. This is an environment limitation, not a target runtime result. GitHub-hosted macOS/Windows and an Android emulator runner are the planned direct validation path.
- Native C++20 JSON/NFKC probe passed on macOS with existing `nlohmann-json 3.12.0` and ICU4C 78.3. ICU reports Unicode 17.0.0, while the Python reference reports Unicode 16.0.0. Matching the reference would require selecting/building a different ICU data version and provisioning that dependency for every target. No C++ cross-target build was run.
- Python-only runtime is excluded by AC-F4. Platform-native semantic implementations would duplicate the same normalizer, orchestration, unresolved gate, and persistence decisions. Direct Python/Rust DB interoperability and stable SQLite file format support the existing-file boundary over an additional export/import format.
- Decision recorded in `docs/ENGINEERING_BASELINE.md` ADR-007: select a Rust shared core; use strict versioned JSON over a C ABI; pin NFKC to UCD 16.0.0 and cap FFI input at 1 MiB; return library-owned NUL-terminated JSON strings through an explicit Rust release function; retain SQLite with `user_version=1`, recognizing validated schema v0 and rejecting unknown/incompatible versions. The resolver uses fixtures and the neural seam is null; no semantic engine or model runtime is selected.
- This is an architecture selection only. Direct SQLite bundled cross-builds and AC-F7–F10 runtime evidence remain required before acceptance.

### Acceptance map at architecture-selection checkpoint (historical)

At this checkpoint AC-F1–AC-F15 were **Pending**. ADR-007 recorded the evidence-backed architecture and persistence decisions; the portable contract, Rust slice, Python conformance, schema migration guard, and four target smoke paths were not yet implemented. The completion state is recorded below in the final Engineering Record.

### Validation and residual risk at architecture-selection checkpoint (historical)

- Repository baseline/status, Graphify graph/interpreter, source inventories, macOS tool availability, and the host SQLite probe were checked read-only; no product test suite has run yet.
- Local iOS simulator and Android runtime are unavailable in the present host environment. CI/simulator route is not yet proven; this blocks the corresponding criteria until direct target smoke succeeds.
- The Python request has no byte/length ceiling; the new versioned FFI contract sets a 1 MiB input limit. Python source compatibility remains unlimited; the reference conformance path uses Python 3.14.7 / UCD 16.0.0.

## Final closeout — P1-F (2026-09-28)

### Delivered outcome

- AC-F1~AC-F15를 모두 `Validated`로 닫았다. P1-F의 portable contract, Rust shared runtime slice, C ABI, SQLite v1 boundary, Python conformance 및 host adapters는 ADR-007과 traceability에 반영했다.
- Architecture decision은 evidence 기반 Rust 1.98.1 shared runtime slice다. 이것은 semantic engine 전체나 최종 model/runtime backend 선택이 아니다. Resolver는 deterministic fixture, neural seam은 null 구현으로 두었고 Base KG/TM/User Overlay/Session State 경계를 보존했다.
- Contract `marco-runtime.v1`의 7개 fixture가 모든 target report에서 SHA-256 `b099cfc595104ee80edbf5adc0b247587c9fcf1955a5f04e53a435e5748e845b`로 일치했다.
- Python runtime 경로는 reference 유지, portable runtime은 Python·MARCO `mco`·모델·네트워크 실행 의존성 없이 동작했다. iOS/Android host는 lifecycle/FFI glue만 가진다.

### Verification evidence

| Check | Result | Evidence and limits |
|---|---|---|
| Rust host/unit/build | Pass | Rust 1.98.1; 8 tests passed; release build and `cargo fmt --all -- --check` passed. Local target capability checks covered iOS/Android/Windows compile targets; CI below supplies direct target execution. |
| Python reference and actual MARCO | Pass | Local full suite with the actual pinned `.mco`, network denied: 66 passed. CI run `36381612145` checked out `DoTaeIn/Marco@ffedc8b8552505e515b8f5ea2ae7f9934d7ef58e`, built the pack, and completed `pytest -q tests` successfully. Linux skipped the macOS-only `libproc` RSS sampler; the local macOS suite ran it. |
| macOS native runtime | Pass | Direct C host; same contract/hash and 7 fixtures; open 2,465 µs, smoke 45,613 µs; dylib 2,877,152 bytes. Rust↔Python SQLite interop passed on Python 3.14.7 / SQLite 3.50.4. CI applied `sandbox-exec` network denial; linked runtime dependency was `libSystem`. |
| Windows native runtime | Pass | Native C host and 8 Rust tests; same contract/hash and 7 fixtures; open 4,000 µs, smoke 96,000 µs; DLL 2,513,920 bytes. Dependency inventory contains Windows system/runtime libraries only. |
| Android emulator | Pass | Android API 35 emulator, Rust library build and C host execution; same contract/hash and 7 fixtures; open 2,637 µs, smoke 236,010 µs; shared library 3,242,560 bytes. Dynamic dependencies were `libdl`, `libm`, and `libc`. |
| iOS simulator | Pass | iOS Simulator 26.4.1, SDK 26.5; direct Swift host reported fixture, FFI error, Overlay, Session, TM, and reopen checks; same contract/hash and 7 fixtures; startup 27.01 ms, runtime 12.13 ms; app 159,744 bytes and static runtime library 22,015,848 bytes. Linked dependencies were Apple system frameworks/libraries and Swift runtime. |
| Offline/dependency boundary | Pass | All four runtime reports say `network_dependency=none`; macOS execution additionally ran inside a network-denied sandbox. Host dependency inventories were collected for macOS, Windows, Android, and iOS. Resource values are measurements, not product budgets; memory was not measured. |
| Local boundary/tool checks | Pass | After the Android NDK macro fix, strict Clang C smoke compile and network-denied runtime smoke passed. `git diff --check`, workflow YAML parsing, plist/Xcode project lint, Swift parse, and Bash syntax checks passed. |

CI evidence bundle is attached to [workflow run 36381612145](https://github.com/Box5789/marco-translator/actions/runs/36381612145). All five jobs succeeded: Python/reference+MARCO, macOS, Windows, Android emulator, and iOS simulator. Target measurements are baseline evidence only; startup/memory/binary-size product budgets remain undecided.

### Failed-check classification and correction

| Run | Observed failure | Classification and correction |
|---|---|---|
| `36380005430` | Android shell rejected `pipefail`; iOS Swift host used an unavailable `Data` API | Host/workflow integration defects. Android execution moved to a Bash helper; iOS file handling was changed to supported APIs. |
| `36380358383` | Windows fixture hash differed under CRLF; Android cross compiler environment was lost in a subshell; iOS linker could not find the Rust library | Cross-platform build/integration defects. Fixture JSON/sidecar line endings were pinned to LF; Android compiler environment and build were kept in one helper shell; iOS library search path was added. |
| `36380717936` | iOS simulator device list was parsed as an array although the SDK returns a dictionary; Android runner evaluated multiline shell script lines in separate shells | Runner/API-shape defects. iOS selection now iterates `devices.values`; Android workflow calls a checked-in Bash helper. |
| `36381048661` | Android NDK's `linux/limits.h` redefined `MAX_INPUT`, which strict C warnings treated as an error | C host name collision. Renamed it to `P1F_MAX_INPUT_BYTES`; strict local compile passed and the final Android emulator CI job passed. The other four jobs had passed in that run. |

The final successful implementation commits were `05e2e85`, `ae42197`, `52ca2fd`, `6eb7b4e`, and `3b5b5a5`, all pushed to `p1/cross-platform-runtime-gate`. The documentation closeout is committed and pushed separately after this evidence record.

### Graphify, residual risk, and stop condition

- Graphify `update .` ran after the last source change. It reported 7 source files with zero nodes and a partial parse warning for `runtime/include/marco_runtime.h` at line 36; its watch reported no topology change. Clang strict compile and native smoke are the direct C-header/runtime evidence. Pre-existing untracked `graphify-out/` was preserved and excluded from commits.
- CI emitted informational Node.js 20 deprecation annotations for GitHub Actions currently forced onto Node.js 24; all affected jobs succeeded. Action version maintenance is separate from the runtime contract.
- Local Mac did not have iOS/Android SDKs, so those platforms were directly executed in GitHub-hosted simulator/emulator CI. No local simulator/emulator claim is made.
- P2 OCR, capture, overlay/UI, app packaging, full native MARCO semantic implementation, model backend, and final product resource targets were not started or selected. They require separate scope and evidence.
- Stop condition is met: all applicable acceptance criteria have direct evidence; all four platform runtimes, offline/persistence/error checks, regression/integration, canonical docs, and remote branch delivery are complete. No follow-on phase was started.
