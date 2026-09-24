# Current Task — P1-D Knowledge Maintenance

Status: Active / Engineering baseline prepared  
Branch: `p1/engineering-baseline-macos`  
Baseline commit before this engineering setup: `06b8954fd0851e361707b5b11d491b90148a887b`

## Goal

`software-engineering-discipline`의 full-scope gate를 적용해 P1-D Knowledge Maintenance를 구현하고 검증한다.

정확한 사용자 observable outcome:

> 사용자가 local translation evidence를 export하고 외부 LLM이 만든 patch proposal을 다시 가져왔을 때, 시스템이 이를 자동 적용하지 않고 검증·dry-run·corpus replay한 뒤 명시적 승인으로만 새 KG version을 원자적으로 만들며, 필요하면 이전 version으로 rollback할 수 있다.

## Current stage

Engineering Baseline: prepared  
P1-D implementation: not started on this branch

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
| AC-D1 | export package가 요구 evidence/manifest/version metadata를 가진다 | package round-trip inspection | Pending |
| AC-D2 | stable Evidence ID가 deterministic하고 reference validation 가능 | repeated fixture export | Pending |
| AC-D3 | invalid patch가 active KG를 바꾸지 않는다 | negative tests + state identity | Pending |
| AC-D4 | dry-run이 diff/impact를 내고 active state mutation 0 | integration test | Pending |
| AC-D5 | replay가 before/after category를 재현한다 | fixed corpus replay | Pending |
| AC-D6 | approval 전 active KG version 불변 | transaction test | Pending |
| AC-D7 | successful approval이 exactly one new version을 원자적으로 활성화 | transaction/version test | Pending |
| AC-D8 | failure injection에서 previous version 유지 | failure test | Pending |
| AC-D9 | rollback이 target version canonical state를 복구 | restart + identity/content test | Pending |
| AC-D10 | P1-A/B/C regression 유지 | full relevant test suite + actual MARCO integration | Pending |
| AC-D11 | local runtime/P1-D path가 network 없이 검증 가능 | offline test | Pending |
| AC-D12 | 가능한 P1-D file/persistence 흐름을 macOS에서 직접 검증 | Mac execution record | Pending/Environment dependent |

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

`graphify-out/graph.json`은 baseline 생성 시 Absent였다. 이후 생기면 orientation에 사용한다.

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

## Material decisions still open

다음 결정이 실제 source/pattern/acceptance evidence를 필요로 하면 그 지점에서 질문한다.

- Base KG version canonical identity 형식
- patch operation별 실제 mutation representation
- replay의 "improved/regressed" oracle가 자동 판정 가능한 범위
- redaction의 P1-D 최소 정책
- schema migration strategy가 현재 contract 변경을 요구하는 경우

독립적으로 진행 가능한 문서/테스트/구현은 이 질문 때문에 선제적으로 멈추지 않는다.

## Stop condition

다음이 모두 충족되면 이 task를 종료한다.

1. P1-D 요구사항/설계/traceability가 구현 결과와 일치
2. P1-D 기능 전체 구현
3. acceptance AC-D1~D11 validated
4. AC-D12는 실제 macOS environment가 제공되면 validated, 아니면 blocker와 impact를 명확히 기록
5. 기존 P1-A/B/C regression 유지
6. security/failure/rollback 검증 완료
7. `docs/P1.md`에서 증거가 있는 P1-D 항목만 완료 표시
8. `work/current.md`에 최종 validation/residual risk/next step 기록
9. 한국어 commit title/body로 branch에 commit/push
10. P1-E는 구현하지 않고 시작 조건만 정리

## Residual risks at baseline

- P1-D canonical versioning과 replay oracle은 아직 구현 근거가 없다.
- actual macOS direct validation은 작업 실행 환경이 Mac을 제공해야 한다.
- cross-platform native runtime 선택은 의도적으로 미결정이다.

## Next step

P1-D implementation 세션이 documentation preflight와 current source inspection을 수행한 뒤, acceptance map과 material decision을 확정하고 구현을 시작한다.
