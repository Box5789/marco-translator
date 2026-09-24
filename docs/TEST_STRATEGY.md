# Test Strategy

## Purpose

테스트는 내부 코드 실행이 아니라 사용자에게 약속한 semantic safety, persistence, maintenance transaction, rollback을 검증한다.

## Validation layers

| Level | Scope | Required evidence |
|---|---|---|
| Unit | normalization, TM, overlay, session, patch pure logic | strong assertions |
| Component | resolver/realizer/persistence collaboration | boundary fixtures |
| Integration | actual upstream MARCO `.mco`, P1-D package/version store | real boundary execution |
| Regression | zh→ko gaming corpus + general/literal cases | before/after comparable results |
| Security/Failure | malformed patch/archive, path/version/evidence errors | fail-safe state preservation |
| Direct macOS | local offline run, persistence/restart, later model/host checks | actual Mac execution evidence |
| Cross-platform | P1-F fixture parity | same contract fixtures on each target |

## Existing baseline evidence

P1-A/B/C는 baseline source commit의 prior CI에서 검증되었다. 새 P1-D 작업은 기존 regression을 다시 실행해야 하며 prior CI만으로 회귀 없음이 증명되지는 않는다.

## P1-D required cases

### Export
- 정상 package 생성
- low-confidence와 unresolved가 구분되어 포함
- correction evidence 포함
- manifest에 schema/KG version metadata 포함
- 자동 network 전송 없음
- 동일 canonical evidence의 ID 안정성
- duplicate/collision policy
- complete `kg2_` asset snapshot, style/config digests, build provenance, and matching derived `.mco`

### Import and validation
- valid patch
- malformed JSON/schema
- disallowed operation
- unknown evidence ID
- wrong base KG version
- contradictory/conflicting patch
- malicious path/archive entry
- missing required metadata
- all seven v2 operations, closed resource allowlist, stable target identity, and exact expected-old-state
- distinct lexical confidence and semantic routing-weight bounds/behavior

### Dry run
- expected diff 산출
- active Base KG 변경 0
- invalid proposal 적용 0

### Corpus replay
- before/after 동일 corpus
- changed / improved / regressed / unchanged 분류
- gaming `家里 → 본진`이 literal `家里 → 집`을 global하게 파괴하지 않는지 확인
- repeated replay reproducibility
- rebuild the candidate with the actual upstream MARCO compiler and versioned style/axiom inputs

### Approval transaction
- explicit approval 없이는 active version 불변
- successful approval creates one new version
- injected failure leaves prior active version intact
- approval is bound to the freshly replayed candidate version ID
- asset snapshot, derived `.mco`, lineage, and active pointer commit in one SQLite transaction
- proposal/evidence/base/new version lineage 기록

### Rollback
- prior version activation
- canonical identity/content 검증
- TM/User Overlay/Session State 부수 변경 없음
- repeated rollback/idempotency semantics를 설계에 따라 검증

## Offline validation

Runtime과 P1-D local processing은 network unavailable 상태에서 수행 가능한지 확인한다.

외부 LLM 분석 자체는 사용자가 별도 수행하는 maintenance activity이므로 offline runtime acceptance와 구분한다.

## macOS validation

현재 우선 direct validation platform은 macOS다.

P1-D 완료 전 가능한 범위에서:
- package export/import 실제 파일 round-trip
- process restart를 포함한 persistence 확인
- offline execution
- rollback after restart

GUI/overlay 검증은 P1-D 범위 밖이다.

## Performance

P1-D에서 새 성능 목표를 임의로 확정하지 않는다.

P1-E/P1-F에서 같은 Mac workload를 고정한 뒤 다음을 측정한다.
- latency
- peak RAM
- model size
- neural invocation rate

현재 상태: **Measurement Needed**
