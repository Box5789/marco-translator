# Traceability Matrix

## Current implementation

| Requirement / Use Case | Analysis / Design | Current code/artifact | Test / Evidence |
|---|---|---|---|
| FR-001, UC-001 | Runtime plane | `src/marco_translator/pipeline.py` | existing pipeline + MARCO integration tests |
| FR-002, FR-015 | Semantic ownership, ADR-003 | resolver / `marco_adapter.py` / realizer boundary | resolver/adapter regression tests |
| FR-003 | Translation Memory | `tm.py` | pipeline TM tests |
| FR-004, UC-002 | correction contract | `pipeline.py`, `tm.py` | user overlay correction tests |
| FR-005 | ADR-002 | `user_state.py` | persistence tests |
| FR-006, UC-004 | Session Binding | `user_state.py` | session isolation tests |
| FR-017 | ADR-001 | runtime architecture | architecture/security review; P1-D must retain |
| FR-018 | ADR-005, Knowledge Version v2 | `knowledge_version.KnowledgeVersionStore`, `marco_pack.compile_marco_pack` | `test_mac_version_bootstrap_reopens_and_materializes_verified_model`; package digest checks |

## P1-D traceability

| Requirement / Use Case | Analysis / Design element | Current implementation surface | Required test evidence |
|---|---|---|---|
| FR-007, UC-003 | Full Analysis Package | `maintenance.export_analysis_package`, `KnowledgeVersionStore.snapshot` | `test_analysis_package_carries_full_version_assets_mco_and_evidence_subsets`; atomic replacement and privacy tests |
| FR-008 | Evidence identity contract | `maintenance.stable_evidence_id`, package reader | deterministic identity, duplicate/conflicting source ID, and package tamper tests |
| FR-009 | `kg-patch-v2` trust boundary | `maintenance.load_analysis_package`, `load_patch_proposal`, `patches.validate_patch_document`, `apply_patch_operations` | `test_valid_patch_requires_v2_resource_identity_states_and_evidence`; all seven operations; stale state, unknown evidence, conflict, schema and unsafe archive tests |
| FR-010 | Dry Run | `KnowledgeVersionStore.preview_patch` | `test_dry_run_replays_actual_marco_without_persisting_or_activating` |
| FR-011 | Corpus Replay | actual MARCO rebuild + fixed regression and literal/domain corpus | deterministic eight-case before/after report; regression gate test |
| FR-012 | Approval gate | `KnowledgeVersionStore.approve_patch` requires matching fresh candidate version ID | `test_explicit_approval_is_atomic_and_rollback_survives_restart_without_touching_user_state`; mismatched approval rejection |
| FR-013 | Atomic version transaction | `versions`, `assets`, active pointer, activation history in one SQLite transaction | injected activation-log failure preserves active snapshot and version count |
| FR-014 | Rollback | `KnowledgeVersionStore.rollback` | reopen store, restore exact assets and `.mco`, verify activation history |
| QA-001 | Offline | runtime/maintenance local paths | network-disabled regression |
| QA-002 | Determinism | replay + versioned inputs | repeatability test |
| QA-003 | Fail safety | import/apply boundaries | corrupted input tests |
| QA-004 | Atomicity | transaction | failure-injection test |
| QA-005 | Rollback | version store | canonical identity/content check |
| QA-006 | Traceability | stable Evidence ID | dangling reference=0 |
| QA-007 | Privacy | explicit export boundary | no automatic upload review/test |
| QA-010 | Compatibility | versioned schema | version/migration/rejection tests |

이 matrix는 구현 중 실제 파일/테스트 이름으로 갱신한다. 계획된 surface를 source inspection 전에 고정된 class/API로 해석하지 않는다.

## P1-E traceability

| Requirement / Use Case | Analysis / Design element | Current implementation / artifact | Test / Evidence |
|---|---|---|---|
| FR-002, FR-015, UC-001 | ADR-003 and ADR-006; semantic authority remains in the grounded frame | `pipeline.py` unresolved-frame gate; target-only prompt in `scripts/benchmark_tiny_realizer.py` | `test_neural_realizer_does_not_guess_unresolved_frame`; actual MARCO unknown-input integration case |
| QA-001 Offline | Offline-first runtime; loopback-only benchmark sandbox | P1-E runner launches local Ollama with cloud disabled and no proxies | two sandboxed direct macOS reports in `benchmarks/p1-e/results/` |
| QA-002 Determinism | Frozen workload, model digest, prompt hashes, pinned MARCO revision | `benchmarks/p1-e/workload.v1.json` and versioned run reports | `test_rule_baseline_matches_every_frozen_case`; repeated outputs identical within and across reports |
| QA-009 Performance | Comparable rule and local candidate measurements without setting a product threshold | P1-E runner records cold/warm latency, sampled process-tree RSS, and model bytes | two 50-call reports; exact environment, runner, workload, and prompt identities in ADR-006 |

## P1-F traceability

| Requirement / Use Case | Analysis / Design element | Current implementation / artifact | Required test evidence |
|---|---|---|---|
| FR-019, FR-020, FR-025 | P1-F JSON v1 contract and shared Rust core; ADR-007 | `schemas/marco-runtime-v1.schema.json`, `runtime/fixtures/conformance-v1.json`, `runtime/src/lib.rs`, `src/marco_translator/portable_contract.py` | frozen fixture SHA-256; `tests/test_p1f_conformance.py`; four target reports carry the same contract and fixture hash |
| FR-021, FR-022 | C ABI and replaceable resolver/realizer seams; ADR-007 | `runtime/include/marco_runtime.h`, fixture resolver and null realizer in `runtime/src/lib.rs`, thin C and iOS hosts | isolated runtime has no Python/MARCO/network/model dependency; native C host and iOS simulator app execute fixture/orchestration checks |
| FR-023, FR-003–FR-006 | shared SQLite v1 file contract; Session State remains ephemeral | `src/marco_translator/persistence_schema.py`, Python TM/Overlay stores, Rust runtime persistence | `tests/test_p1f_persistence.py`, C host close/reopen checks, Python↔Rust TM/Overlay file round-trip |
| FR-024, QA-001, QA-011 | platform lifecycle stays outside semantic core; offline local operation | `runtime/hosts/c_smoke.c`, `runtime/hosts/ios/MarcoRuntimeSmokeApp.swift`, `.github/workflows/p1f-runtime-gate.yml` | macOS/Windows native process, Android emulator and iOS simulator smoke reports; linked dependency inventory and no runtime network API/dependency |
| QA-008, QA-009 | portability/resource baseline only; no product budget selected | ADR-007 target rationale and per-platform report artifact | library bytes, startup/smoke CPU time where the host reports it, toolchain/runtime dependency inventory |
| QA-010, QA-012 | store and FFI fail-closed contracts | Rust schema/status/input/output validation; Python store migration/rejection | incompatible/unknown SQLite version, invalid UTF-8/JSON/version/fields, input/output caps, invalid status, close/reopen cases |

P1-F closeout (2026-09-28): all rows above have direct implementation/test evidence. Workflow run `36381612145` completed all five jobs successfully. macOS, Windows, Android API 35 emulator, and iOS Simulator 26.4.1 each reported `marco-runtime.v1`, seven fixtures, and SHA-256 `b099cfc595104ee80edbf5adc0b247587c9fcf1955a5f04e53a435e5748e845b`. Detailed target reports and limits: `work/current.md` Final closeout.


## P2-A macOS host traceability

| Requirement / Use Case | Analysis / Design element | Implementation surface | Evidence / remaining direct-host status |
|---|---|---|---|
| FR-026, FR-027 | Explicit source selection, one-shot permission guard, post-capture region crop | `macos/Sources/MarcoCaptureApp.swift`, `macos/Sources/RegionCropView.swift`, ADR-008 | App launch/action and denied guidance observed on Mac; granted capture remains pending manual Screen Recording permission. |
| FR-028, QA-015 | Local simplified Chinese OCR and normalized line geometry | `macos/Sources/CaptureCore.swift`, `macos/Tests/HostChecks.swift` | Exact bitmap oracle and crop OCR pass; actual on-screen fixture awaits permission. |
| FR-029, FR-036 | Existing versioned translation boundary; no host semantic rule | `PortableRuntime` in `macos/Sources/CaptureCore.swift`, `runtime/include/marco_runtime.h` | App uses the P1-F seven-case fixture; component checks pass and Python/MARCO regression is separate. Direct GUI E2E awaits Screen Recording access. |
| FR-030, QA-017 | Dismissible, non-activating transient result surface | `TranslationOverlay` in `macos/Sources/MarcoCaptureApp.swift` | Build and AppKit capability checks pass; actual display/dismiss awaits granted capture. |
| FR-031 | Exclude host from picker and screen-sharing output | `installPickerConfiguration`, `window.sharingType`, `TranslationOverlay.panel.sharingType` | Configuration/build checks pass; repeated real capture cycle awaits granted capture. |
| FR-032, FR-033 | Ephemeral frame/text/timing; offline host | `AppDelegate` request lifecycle and `PortableRuntime(databasePath: ":memory:")` | Source/runtime audit passes; app-specific inventory and network-denied successful E2E await granted capture. |
| FR-034 | Generation guard for cancellation and re-entry | `RequestGeneration` in `macos/Sources/CaptureCore.swift` | Delayed stale-completion assertion passes; direct capture UI re-entry remains pending. |
| FR-035, QA-018 | In-memory stage samples and nearest-rank p50/p90 | `recordTiming`, `updateTimingLabel`, `percentile` in `macos/Sources/MarcoCaptureApp.swift` | Instrumentation builds; real controlled workload report awaits granted capture. |

P2-A remains active until the direct-host evidence above is complete. Component checks and Python/MARCO regression are not substitutes for those permission-dependent rows.
