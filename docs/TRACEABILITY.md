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
