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

## P1-D planned traceability

| Requirement / Use Case | Analysis / Design element | Planned implementation surface | Required test evidence |
|---|---|---|---|
| FR-007, UC-003 | Analysis Package | maintenance/export boundary | export round-trip |
| FR-008 | Evidence identity contract | logger/evidence/export schema | deterministic ID/collision tests |
| FR-009 | Patch trust boundary | validator/import boundary | malformed/disallowed/evidence/version/conflict tests |
| FR-010 | Dry Run | patch preview service | no-mutation diff test |
| FR-011 | Corpus Replay | replay/report boundary | before/after classification regression |
| FR-012 | Approval gate | transaction/controller | no-approval no-change test |
| FR-013 | Atomic version transaction | version store/transaction | injected failure atomicity |
| FR-014 | Rollback | version store | rollback/restart integrity |
| QA-001 | Offline | runtime/maintenance local paths | network-disabled regression |
| QA-002 | Determinism | replay + versioned inputs | repeatability test |
| QA-003 | Fail safety | import/apply boundaries | corrupted input tests |
| QA-004 | Atomicity | transaction | failure-injection test |
| QA-005 | Rollback | version store | canonical identity/content check |
| QA-006 | Traceability | stable Evidence ID | dangling reference=0 |
| QA-007 | Privacy | explicit export boundary | no automatic upload review/test |
| QA-010 | Compatibility | versioned schema | version/migration/rejection tests |

이 matrix는 구현 중 실제 파일/테스트 이름으로 갱신한다. 계획된 surface를 source inspection 전에 고정된 class/API로 해석하지 않는다.
