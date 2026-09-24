# Current Task — P1-D Knowledge Maintenance

Status: Implementation and validation complete; commit/push pending
Branch: `p1/engineering-baseline-macos`  
Baseline commit before this engineering setup: `06b8954fd0851e361707b5b11d491b90148a887b`

## Goal

`software-engineering-discipline`의 full-scope gate를 적용해 P1-D Knowledge Maintenance를 구현하고 검증한다.

정확한 사용자 observable outcome:

> 사용자가 local translation evidence를 export하고 외부 LLM이 만든 patch proposal을 다시 가져왔을 때, 시스템이 이를 자동 적용하지 않고 검증·dry-run·corpus replay한 뒤 명시적 승인으로만 새 KG version을 원자적으로 만들며, 필요하면 이전 version으로 rollback할 수 있다.

## Current stage

Engineering Baseline: prepared  
P1-D implementation: complete; all AC-D1–AC-D12 and full offline regression validated on macOS

## Accepted decisions

- 최종 플랫폼: macOS / Windows / Android / iOS.
- 현재 직접 검증 우선 플랫폼: macOS.
- macOS-first는 macOS-only architecture를 의미하지 않는다.
- Base KG는 runtime read-only.
- TM / User Overlay / Session State / Base KG는 별도 책임.
- 외부 LLM은 provider-independent patch proposal 생성기.
- automatic cloud upload 없음.
- Tiny Neural Realizer는 semantic authority 없음.
- Python은 현재 reference implementation.
- shared native core 기술은 P1-F 근거 확보 전 미결정.
- ADR-005 승인: Knowledge Version은 seed, MARCO source `.kg`, frame map, MCO model style/axiom inputs, build provenance, 실제 `.mco` 출력 digest를 묶는다. `.mco` bytes는 검증된 derived runtime artifact다.
- `kg-patch-v2`가 기존 일곱 operation을 유지한다. 각 patch는 제한된 `resource`, stable `target`, `expected_old_state`, `proposed_new_state`, evidence IDs를 요구한다.
- `ADJUST_WEIGHT`는 seed lexical `confidence`와 frame-map semantic `routing_weight`를 분리한다. Semantic weight는 기존 MARCO adapter의 mapped-node trace-rescue margin에만 적용한다.
- `.kg` operation 위치: `ADD_PATTERN`은 `[개념]` examples, `ADD_NEGATIVE_CONSTRAINT`는 `[무관]` examples, `ADD_RELATION`은 선언된 type의 `[논증]` edge다.

## Scope

### In scope

1. Analysis Package export
   - manifest
   - translation logs
   - low-confidence subset
   - unresolved subset
   - corrections
   - unknown/candidate evidence where supported by current data
   - KG snapshot/version metadata
   - maintenance instructions

2. Stable Evidence ID
   - canonical identity input 정의
   - duplicate/collision policy
   - replay/export 간 불필요한 identity churn 방지

3. Patch validation
   - schema
   - allowed operation
   - evidence refs
   - base KG version
   - conflict
   - trust-boundary/path validation as applicable

4. Patch dry-run
   - mutation preview
   - no active Base KG modification

5. Corpus replay
   - before/after
   - changed / improved / regressed / unchanged
   - literal/domain sense regression 포함

6. User approval transaction
   - import ≠ apply
   - explicit approval
   - failure atomicity

7. Versioned rollback
   - prior version retention
   - version activation
   - rollback after restart
   - TM/User Overlay/Session State side-effect 금지

8. Privacy/security
   - explicit export only
   - automatic external transfer 금지
   - sensitive-data policy/extension point
   - malformed/corrupt/malicious input fail-safe

### Explicitly out of scope

- P1-E Tiny Realizer benchmark 구현
- Tiny Realizer 학습/증류
- P1-F native/core port
- Rust/C++/Swift 등 core 기술 선택
- OCR
- screen capture
- overlay UI
- Windows/Android/iOS host 구현
- PR #1/#2 merge
- release/tag

## Acceptance criteria

| ID | Criterion | Direct evidence | Status |
|---|---|---|---|
| AC-D1 | export package가 요구 evidence/manifest/version metadata를 가진다 | full pytest package ZIP round-trip and atomic-write checks | Validated |
| AC-D2 | stable Evidence ID가 deterministic하고 reference validation 가능 | canonical identity, exact known-evidence reference checks, duplicate/conflict tests | Validated |
| AC-D3 | invalid patch가 active KG를 바꾸지 않는다 | invalid/stale/conflicting patch rejection and unchanged active-version assertions | Validated |
| AC-D4 | dry-run이 diff/impact를 내고 active state mutation 0 | `test_dry_run_replays_actual_marco_without_persisting_or_activating` | Validated |
| AC-D5 | replay가 before/after category를 재현한다 | deterministic actual-MARCO replay; eight fixed cases include literal/domain regression | Validated |
| AC-D6 | approval 전 active KG version 불변 | preview and mismatched-approval transaction assertions | Validated |
| AC-D7 | successful approval이 exactly one new version을 원자적으로 활성화 | `test_explicit_approval_is_atomic_and_rollback_survives_restart_without_touching_user_state` | Validated |
| AC-D8 | failure injection에서 previous version 유지 | `test_activation_failure_and_mismatched_approval_leave_active_snapshot_unchanged` | Validated |
| AC-D9 | rollback이 target version canonical state를 복구 | restart, exact asset/`.mco` comparison, and activation history | Validated |
| AC-D10 | P1-A/B/C regression 유지 | full pytest suite with the current upstream MARCO pack | Validated: 49 passed, 0 skipped |
| AC-D11 | local runtime/P1-D path가 network 없이 검증 가능 | full suite with socket connection, connection-ex, create-connection, and DNS lookup blocked | Validated: 49 passed |
| AC-D12 | P1-D file/persistence 흐름을 macOS에서 직접 검증 | native macOS full-suite run; version bootstrap, reopen, materialization, approval and rollback tests | Validated |

## Required preflight before source changes

새 작업 세션은 반드시:

1. `AGENTS.md`
2. `AGENT_GUIDE.md`
3. 이 파일
4. `README.md`
5. `docs/REQUIREMENTS.md`
6. `docs/ENGINEERING_BASELINE.md`
7. `docs/PLATFORM_STRATEGY.md`
8. `docs/TEST_STRATEGY.md`
9. `docs/TRACEABILITY.md`
10. 기존 architecture/learning/MARCO docs
11. relevant schemas/tests/source

순으로 evidence를 복원한다.

`graphify-out/graph.json`은 baseline 시점에 Absent였다. 최종 `graphify update .` 결과는 596 nodes / 1211 edges, 33 communities다. JSON asset 3개는 source node가 없어 경고가 있었고, graph는 navigation evidence로만 사용한다. `graphify-out/` 생성 파일은 untracked이며 사용자 지침에 따라 보존하고 구현 commit에는 넣지 않는다.

## Validation set

- P1-A regression
- P1-B actual upstream MARCO integration
- P1-C User Overlay tests
- P1-D unit tests
- P1-D integration tests
- corrupted/malformed inputs
- wrong base version
- unknown evidence ID
- conflict
- transaction failure
- rollback/restart
- offline execution
- macOS direct file/persistence validation where available

failed/skipped/timed-out result는 분류와 impact statement 없이 완료로 처리하지 않는다.

## Material decision checkpoint (Superseded 2026-09-24)

아래는 이전 checkpoint에서 열려 있던 결정이다. 사용자가 2026-09-24에 full-scope 계약을 승인했고, `docs/ENGINEERING_BASELINE.md`의 ADR-005가 현재 정본이다.

- 승인·rollback이 관리할 Base KG artifact 경계: runtime seed만 포함할지, MARCO source graph와 frame map까지 포함할지
- `kg-patch-v1` 일곱 operation의 실제 mutation 필드와 규칙

이전 질문/중단 상태는 해소됐다. 과거 기록은 작업 이력으로만 남긴다.

## Stop condition

다음이 모두 충족되면 이 task를 종료한다.

1. P1-D 요구사항/설계/traceability가 구현 결과와 일치
2. P1-D 기능 전체 구현
3. acceptance AC-D1~AC-D12 validated
4. AC-D12는 실제 macOS environment에서 file/persistence 흐름을 직접 검증
5. 기존 P1-A/B/C regression 유지
6. security/failure/rollback 검증 완료
7. `docs/P1.md`에서 증거가 있는 P1-D 항목만 완료 표시
8. `work/current.md`에 최종 validation/residual risk/next step 기록
9. 한국어 commit title/body로 branch에 commit/push
10. P1-E는 구현하지 않고 시작 조건만 정리

## Residual risks at previous checkpoint (historical)

- Base KG boundary와 patch operation semantics가 정해지지 않아 P1-D validation/apply/version/rollback 경로는 구현하지 않았다.
- Replay의 improved/regressed 판정 oracle은 선택된 mutation contract와 함께 정해야 한다.
- actual macOS persistence validation은 version store가 결정·구현된 뒤 수행해야 한다.
- Cross-platform native runtime 선택은 P1-F 근거 확보 전 미결정이다.

## Next step at previous checkpoint (superseded)

ADR-005 계약을 반영해 patch schema, dry-run/replay, approval/version/rollback을 구현하고 나머지 acceptance를 검증한다.

## Engineering Record — continuation checkpoint (2026-09-24)

### Goal, authority, and stop condition

- 목표: 이 파일의 P1-D scope를 구현하고 AC-D1~AC-D11을 검증한다. 가능한 macOS file/persistence 검증도 수행한 뒤 이 branch에 한국어 commit/push한다.
- 정확한 사용자 결과: 사용자가 local translation evidence를 명시적으로 export하고, 외부에서 만든 patch를 가져와 검증·dry-run·corpus replay한 뒤 승인할 때만 완전한 새 Base KG version이 활성화된다. 실패 시 기존 version이 유지되고, 재시작 뒤에도 rollback할 수 있다.
- 비목표: P1-E, P1-F, OCR/capture/overlay, native core 선택, PR merge, release/tag.
- 승인: 구현과 지정 branch push는 사용자 요청으로 승인됐다. 이 범위 밖의 계약·데이터 경계 변경은 수행하지 않는다.
- 종료: acceptance, 필수 회귀·보안·실패·rollback 검증, 문서 갱신, Korean commit/push, local/remote ref 일치 확인을 마친다. AC-D12의 macOS host 검증이 불가능하면 blocker와 영향을 기록한다.

### Baseline and recovered state

- Repository: `Box5789/marco-translator`.
- Branch: `p1/engineering-baseline-macos`, tracks `origin/p1/engineering-baseline-macos`.
- Baseline commit: `a56a52c731a54098d2bb089a74d776e753ec8f8e` (parent `f4be0e11ff8f5af144d1b6af333b408084269e7d`).
- Baseline working tree/index: clean; no user edits were present.
- Historical source baseline recorded in §1: `06b8954fd0851e361707b5b11d491b90148a887b`.
- Initial checkout was an empty Git directory without remote; it contained no user files. The verified GitHub branch was fetched and checked out before project docs or source were restored.
- Graphify baseline: `graphify-out/graph.json` Absent; final authorized update contains 596 nodes / 1211 edges across 33 communities. Three JSON asset files produced no nodes. Generated `graphify-out/` files are untracked and preserved outside the implementation commit.

### Documentation preflight

| Candidate | Status | Authority / use |
|---|---|---|
| `AGENTS.md` | Read | full workflow, boundaries, delivery |
| `AGENT_GUIDE.md` | Read | durable product/architecture rules |
| `AGENT_HANDOFF.md` | Absent | no root handoff |
| `docs/AGENT_HANDOFF.md` | Absent | no docs handoff |
| `work/current.md` | Read | current scope and stop condition |
| Other `work/*.md` | Absent | inventory contains only this task note |
| `README.md` | Read | product/runtime overview |
| `docs/REQUIREMENTS.md` | Read | FR/quality constraints |
| `docs/ENGINEERING_BASELINE.md` | Read | UC-003, domain model, SSD, contracts, baseline state |
| `docs/PLATFORM_STRATEGY.md` | Read | four-platform contract and macOS validation |
| `docs/TEST_STRATEGY.md` | Read | required P1-D/security/restart cases |
| `docs/TRACEABILITY.md` | Read | requirement-to-code/test map |
| `docs/ARCHITECTURE.md` | Read | runtime/maintenance separation and validation order |
| `docs/AUTOMATIC_LEARNING.md` | Read | Base KG versus adaptive-state boundary |
| `docs/MARCO_PROTOCOL.md` | Read | `.kg`, frame-map, `.mco` integration boundary |
| `docs/P1.md` | Read | P1-D stop boundary; P1-E/F excluded |
| `schemas/kg-patch.schema.json` | Read | current seven operation names and incomplete operation-specific schema |
| `schemas/translation-log.schema.json` | Read | current translation-log fields |
| `prompts/kg-maintenance.md` | Read | external proposal rules |
| `pyproject.toml`, `pytest.ini` | Read | package and test requirements |
| `.github/workflows/p1-marco-integration.yml` | Read | actual upstream MARCO regression procedure |
| `scripts/build_marco_pack.py` | Read | translator `.mco` build inputs |
| Existing relevant source/tests/assets | Read | `maintenance.py`, logger, runtime stores, resolvers, relevant tests, seed, frame map, MARCO graph |
| OOP reference | Read / Applicable | version transaction has persistent state and lifecycle |
| Other full engineering references | Read | diagnosis, implementation, change control, delivery, artifacts, standard map, handoff, maintenance validation |

### Confirmed findings at original checkpoint (historical; decision superseded)

- `KnowledgeStore.from_json` reads `entries` from `knowledge/seed.zh-ko.json` only.
- `MarcoResolver` reads `knowledge/marco-frame-map.zh-ko.json` separately. `scripts/build_marco_pack.py` compiles `marco/graphs/graph_zh_ko_gaming_semantics.kg` into `.mco`; these artifacts do not share an existing version owner.
- `kg-patch-v1` lists seven operation types, but requires only `type` and `evidence_ids`; operation-specific fields and mutation behavior are unspecified. At the recovered baseline, maintenance tests covered only a valid sample and rejection of automatic apply.
- The supported Base KG artifact set and patch mutation semantics control approval, snapshot identity, dry-run, and rollback. A user decision is pending; edits to those dependent paths remain paused. Independent evidence export and stable identity work may proceed.
- Baseline tool probe found Python 3.14.7 and bundled Python but no `pytest`, `jsonschema`, or installed `mco`. The declared `pytest>=7` extra is now installed only in isolated `/tmp` virtual environments; `jsonschema` and translator/global Python environments were not changed. A fresh upstream MARCO checkout supplies the source used to build the test pack; MARCO environment variables were set only for test processes. `.github` workflow confirms integration requires checkout/build setup.

### Use case, operation contract, and object boundary

- Primary actor: 지식 유지보수 사용자.
- Preconditions: user explicitly selects local evidence for export; patch proposal is user-supplied; proposal references exported evidence and the current compatible Base KG version.
- Success guarantee: import and dry-run do not mutate active state; explicit approval activates exactly one complete version; rollback after restart restores the selected canonical version; TM, User Overlay, and Session State stay unchanged.
- Failure guarantee: malformed, incompatible, conflicting, rejected, or interrupted work leaves the prior active version intact and records no partial activation.
- Operations: export package, derive/validate evidence identity, validate/import proposal, dry-run/replay, approve version transaction, rollback version.
- OOP: Applicable. Candidate roles are Evidence/Version value objects and a version-store service, but exact persistent snapshot responsibility is deferred until the Base KG boundary and operation semantics are aligned. Prefer composition; no inheritance need is evidenced.
- No external ISO/security-standard compliance claim is made; internal product constraints and direct tests govern this reference implementation.

### Acceptance map at original checkpoint

| Criterion | Direct evidence | Status |
|---|---|---|
| AC-D1 export contents/round-trip | full pytest package ZIP manifest, snapshot, prompt, evidence subset, and atomic-write checks | Validated |
| AC-D2 stable Evidence ID/reference | full pytest canonical key-order, stable-ID, exact known-evidence reference, duplicate, and conflicting-source-ID checks | Validated |
| AC-D3 invalid patch preserves active KG | negative tests plus version identity | Pending / depends on scope decision |
| AC-D4 dry-run reports impact with zero mutation | integration test | Pending / depends on scope decision |
| AC-D5 replay categories and literal/domain regression | fixed corpus replay comparison | Pending / replay policy to be evidenced |
| AC-D6 approval gate | transaction test | Pending / depends on scope decision |
| AC-D7 one atomic new version | transaction/version test | Pending / depends on scope decision |
| AC-D8 failure injection preserves prior version | failure test | Pending / depends on scope decision |
| AC-D9 rollback after restart | reopen store and compare canonical state | Pending / depends on scope decision |
| AC-D10 P1-A/B/C regression | complete tests with a pack built from current upstream MARCO | Validated: 47 passed, 0 skipped |
| AC-D11 offline local path | full suite with socket connection, connection-ex, create-connection, and DNS lookup blocked | Validated: 47 passed |
| AC-D12 macOS file/persistence path | native macOS export/reopen/rollback execution | Partially validated: export ran on macOS; persistent version store pending |

### Scope coverage at original checkpoint

| In-scope surface | Checkpoint status |
|---|---|
| Analysis package export | Implemented and full-suite validated: `src/marco_translator/maintenance.py`, `tests/test_maintenance.py` |
| Stable Evidence ID | Implemented and full-suite validated with exact evidence-reference checks |
| Patch schema/evidence/version/conflict/path validation | Partially implemented: strict local JSON import/envelope, operation allowlist, evidence/base-version checks, unique patch IDs; operation-specific mutation and graph-conflict checks pending scope decision |
| Dry-run | Unverified pending scope decision |
| Corpus replay | Unverified pending mutation semantics/oracle |
| Explicit approval and atomic activation | Unverified pending scope decision |
| Versioned rollback/restart | Unverified pending snapshot boundary |
| Privacy/security/failure behavior | Export and local patch-load paths reject malformed/non-finite/duplicate-key JSON and preserve inputs; apply-side semantics await the contract decision |
| P1-E/P1-F and listed product exclusions | Explicitly excluded |

Next step: apply the user's Base KG boundary and operation-semantics decision, then implement dependent P1-D paths.

### Independent export/evidence design

- Reuse the existing standard-library JSONL/ZIP path in `maintenance.py`; no new runtime dependency or network path.
- Compute `ev1_<sha256>` from UTF-8 canonical JSON of each complete logged event (`sort_keys`, compact separators, `ensure_ascii=False`, non-finite numbers rejected). This preserves event identity across repeated exports while retaining separately logged repeated events.
- Exact duplicate event records with the same source event ID collapse to one evidence record. Reuse of one source event ID for different content and any digest collision fail the export; no ambiguous reference is emitted.
- Preserve source records and add `evidence_id` only in the package. Create explicit low-confidence, unresolved, and correction subsets; record threshold and subset counts in the manifest. Current logger has no unaccepted MARCO-candidate field, so candidate subset is empty unless that field is present in a future/current log record.
- Provide an optional caller-supplied redaction callback; default export is exact local evidence after explicit invocation. Manifest records the applied policy. Package creation performs no network operation and writes via a temporary file followed by replace so a failed export cannot leave a partial package or truncate its input.
- Acceptance: repeated fixed-log export yields identical evidence IDs/references; category membership is checked from package contents; duplicate/collision, malformed JSON, redaction, output/input path collision, and injected write failure preserve source and prior output.

These export/evidence choices remain active. Version identity and patch mutation are now governed by ADR-005.

### Implementation and validation checkpoint before ADR-005

- Changed: `src/marco_translator/maintenance.py`, `tests/test_maintenance.py`, `prompts/kg-maintenance.md`.
- Added canonical `ev1_` SHA-256 event identity; package event categories, caller-provided redaction, snapshot metadata, fixed archive member names, input/output collision guard, and temporary-file replacement. `load_patch_proposal` reads only a selected regular local file, rejects duplicate JSON keys, and validates before returning without applying. Validation requires the exact known-evidence set and active Base KG version, then checks object/schema shape, allowed operations, field types, unique IDs, references, version match, and automatic-apply prohibition. The prompt binds the proposal to the exported Base KG version.
- Direct macOS Python `py_compile` passed. Export checks cover repeated evidence IDs, confidence/unresolved/correction/candidate subsets, caller redaction, offline socket guard, malformed/non-finite JSON rejection, source-ID conflict, output/input collision, and preservation of prior output after an injected ZIP failure.
- Installed declared `pytest>=7` in isolated `/tmp` virtual environments. Full suite on bundled Python 3.12 with `MCO_MARCO_ROOT` and `MARCO_TRANSLATOR_MCO` set to the fresh current-upstream checkout and built pack: **47 passed, 0 skipped**. Repeated the full suite with `socket.connect`, `connect_ex`, `create_connection`, and DNS lookup blocked: **47 passed**. An initial run without a pack skipped six integration cases; final runs exercised all six. During development, a Python 3.12 collection failure from an unavailable `collections.abc.AbstractSet` import and one overly narrow error-message assertion were both corrected; final runs pass.
- Fresh upstream MARCO checkout `326ae6109b1dc92696d88dc9e4209717a26e3f3f` matched remote `main`. Pack `/tmp/marco-translator-zh-ko-gaming-20260924.mco` SHA-256: `3f38aa5f1237170dbb5cf5a9cdbe19ab3d309c973b2d581bdc6f28463adeb627`. The older local clone remained untouched.
- `docs/P1.md` marks only export subsets and stable IDs complete. `docs/TRACEABILITY.md` maps FR-007/FR-008 to current export code and tests.
- Commit/push: not attempted; dependent implementation and validation remain incomplete.
- Next: implement under ADR-005, rerun full P1-D validation, update Graphify after source changes, then commit/push and compare local/remote SHA.

## Engineering Record — accepted decision and resumed implementation (2026-09-24)

### Decision and direct evidence

- User approved the full canonical-version boundary and all existing seven patch operation names, with resource-scoped stable target identity and explicit expected/proposed state.
- ADR-005 is recorded in `docs/ENGINEERING_BASELINE.md`; it supersedes the earlier unresolved checkpoint.
- Local contract evidence: `KnowledgeStore.from_json` reads seed entries; `MarcoResolver` consumes the frame map and already accepts bounded overlay route bias for an existing mapped-node trace-rescue margin; `scripts/build_marco_pack.py` compiles the translator MARCO source tree.
- Upstream evidence: the current official `DoTaeIn/Marco` main commit was pinned read-only at `59d19de74443b5f3768e27032ef83e1c592b0d47`. Its `mco.compile` implementation states deterministic output and calls `kgpack.model_files()`, which packages style JSON and axiom JSON along with the selected graph. The old local MARCO clone at `e35587fc497e451ff4c7affa50464e21361b492f` was left untouched.
- MARCO graph contract distinguishes `[무관]` rejection examples from `부정관계` rebuttal edges. It declares no per-edge numeric weights. Patch resource mapping follows these roles; semantic route weight is stored separately in frame metadata and only biases the existing trace-rescue margin.

### Updated use case, state, and stop condition

- Preconditions: the active Knowledge Version and its exported evidence are identified; every patch cites known evidence and an exact base version.
- Dry-run/import do not change the active pointer or immutable versions. Explicit approval follows replay and builds exactly one complete candidate version. Activation atomically replaces one local pointer; rollback selects an existing verified version after restart.
- User Overlay, Translation Memory, and Session State remain outside the canonical Base KG transaction.
- Stop condition remains the existing AC-D1–AC-D12 map, P1-A/B/C regression, offline/security/failure/restart checks, macOS direct persistence check, documentation and Graphify refresh, then Korean commit/push with remote SHA verification. P1-E/F stay excluded.

### Accepted operation/resource map

| Operation | Canonical resource and mutation |
|---|---|
| `ADD_ALIAS` | Seed entry for an existing concept |
| `ADD_SENSE` | Global seed entry |
| `ADD_DOMAIN_SENSE` | Domain-scoped seed entry |
| `ADD_PATTERN` | Existing node examples in MARCO graph `[개념]` |
| `ADD_NEGATIVE_CONSTRAINT` | Rejection examples in MARCO graph `[무관]` |
| `ADD_RELATION` | Declared relation edge in MARCO graph `[논증]` |
| `ADJUST_WEIGHT` | Seed lexical `confidence`, or frame-map semantic `routing_weight` |

All operations require resource, stable target ID, exact expected old state, proposed new state, unique patch ID, known evidence IDs, and the active base version. Additions use an absent old state. Weight changes compare the actual old numeric value; missing frame-map route weight has effective value 0. The new public proposal/package formats are `kg-patch-v2` and `analysis-package-v2`; v1 proposals are rejected rather than silently migrated.

### Current baseline and stage

- Branch/HEAD at resume: `p1/engineering-baseline-macos` / `a56a52c731a54098d2bb089a74d776e753ec8f8e`, tracking `origin/p1/engineering-baseline-macos`.
- Preserved earlier task changes: `docs/P1.md`, `docs/TRACEABILITY.md`, `prompts/kg-maintenance.md`, `src/marco_translator/maintenance.py`, `tests/test_maintenance.py`, and this note. Generated untracked `graphify-out/` is preserved and excluded from source delivery.
- Decision files updated: `docs/ENGINEERING_BASELINE.md` and this note.
- Validation at resume: export/evidence checkpoint previously passed 47 full-suite cases and 47 offline cases against an earlier upstream pack; those results do not validate the accepted version/patch paths. Current upstream revision was fetched into a separate temporary checkout; fresh end-to-end validation remains required.
- Current stage: implementing `kg-patch-v2`, canonical asset/build provenance identity, dry-run/replay, explicit approval, atomic version activation and restart rollback.
- Residual risk: compatibility with v1 is intentionally rejection-only; no migration has been specified. Native cross-platform storage is P1-F and remains out of scope.

## Engineering Record — P1-D completion and delivery preparation (2026-09-24)

### Implementation outcome

- Analysis Package v2 exports stable evidence records/subsets, the complete canonical source snapshot, build provenance, and the verified derived `.mco`. Export remains an explicit local action with no network transfer.
- Knowledge Version v2 identifies the seed, MARCO `.kg`, frame map, compiler-consumed style/axiom JSON, build recipe and environment provenance, and the actual `.mco` output digest. SQLite retains immutable source bytes, derived model bytes, lineage, activation history, and the active pointer.
- `kg-patch-v2` keeps all seven operation names. Every operation identifies its resource and stable target and supplies expected old and proposed new state. Patch application rejects stale values, existing seed targets/examples/edges, undeclared relations, and forward/rebuttal conflicts.
- Mutation locations follow ADR-005: seed additions for alias/sense operations, MARCO `[개념]` for patterns, `[무관]` `_잡담` for negative examples, `[논증]` for declared typed relations, and either seed lexical confidence or frame-map semantic routing weight for `ADJUST_WEIGHT`.
- Dry-run rebuilds the candidate with actual upstream `mco.compile` and replays eight fixed translation/literal/domain cases twice. Approval is bound to the freshly replayed candidate ID and commits the snapshot plus active pointer in one SQLite transaction. Rollback after reopening restores the versioned assets/model without changing TM or User Overlay.
- Runtime handoff materializes and verifies the active `.mco`, seed, and frame map before constructing `MarcoResolver`.

### Verification evidence

- Host: macOS 26.6.2, arm64; bundled Python 3.12.14; NumPy 2.3.5. Upstream MARCO checkout was clean at `59d19de74443b5f3768e27032ef83e1c592b0d47`.
- Actual `scripts/build_marco_pack.py` build passed. Derived `.mco`: 3,220 bytes, SHA-256 `3f38aa5f1237170dbb5cf5a9cdbe19ab3d309c973b2d581bdc6f28463adeb627`. Build provenance includes script/module digests, selected graph and style input digests, compiler identity, platform/runtime versions, and output digest.
- Disposable macOS SQLite bootstrap/replay produced canonical version `kg2_5d3b7cc701d0b9e667d83b5973159ccb86c181cd045f8d54a8acfcaa61f5e890` with the same verified `.mco` digest.
- Full repository test suite passed twice on the final implementation: **49 passed, 0 skipped**. The final run took 1.38s and used the freshly rebuilt actual MARCO pack. Its offline run replaced `socket.connect`, `connect_ex`, `create_connection`, and `getaddrinfo` with failures before pytest collection.
- macOS persistence cases exercised bootstrap, store reopen, verified materialization, approval, active resolver translation, rollback after restart, exact source/model restoration, and unchanged user TM/Overlay state.
- `json.tool` parsed `schemas/kg-patch.schema.json`; `compileall` passed for `src`, `tests`, and `scripts`; `git diff --check` passed. The optional `jsonschema` package is absent from the isolated runtime, so no third-party Draft 2020-12 meta-validator was run; behavioral validation of all seven operations and all old/new state rules passed in the source tests.
- Final `graphify update .` completed: 596 nodes, 1211 edges, 33 communities. It reported three JSON source assets with zero graph nodes; generated `graphify-out/` files remain preserved and excluded from implementation delivery.

### Completion and residual risk

- AC-D1 through AC-D12 are validated; `docs/P1.md`, `docs/TRACEABILITY.md`, requirements, architecture, MARCO protocol, test strategy, maintenance prompt, and this record reflect the implemented contract.
- Deliberate compatibility boundary: `kg-patch-v1` and `kg1_` identities are rejected; no migration was specified. Native Windows/Android/iOS storage, P1-E, and P1-F remain outside this task's approved scope.
- Current delivery state: Korean commit and push to `p1/engineering-baseline-macos` are pending; verify the remote branch equals local HEAD before marking delivery complete.
