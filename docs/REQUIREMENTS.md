# Requirements Record

## Product Change Brief

### Goal
네트워크가 없어도 사용할 수 있고, 의미 결정을 추적·검증할 수 있으며, 사용자 수정과 지식 유지보수를 안전하게 반영하는 범용 번역 엔진을 만든다.

### Users and stakeholders

| Role | Goal / Concern |
|---|---|
| 번역 사용자 | 빠르고 일관된 local translation, 개인 용어 반영 |
| 지식 유지보수 사용자 | 로그를 분석해 KG 개선안을 검토하고 승인/거부/rollback |
| 앱 개발자 | macOS/Windows/Android/iOS에서 동일한 core contract 사용 |
| 유지보수자 | semantic provenance, regression, version compatibility 보존 |

### In scope
- deterministic-first translation runtime
- MARCO semantic selection
- Translation Memory
- User Overlay
- Session State
- maintenance export/import/validation/versioning
- Tiny Neural Realizer 경계
- cross-platform public contract

### Out of scope for current P1-D
- Tiny Realizer 모델 선정/학습
- native cross-platform core 구현
- OCR
- screen capture
- visual overlay UI
- cloud translation runtime

## Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria | Verification |
|---|---|---:|---|---|
| FR-001 | 시스템은 네트워크 없이 runtime translation 경로를 실행할 수 있어야 한다. | H | network-disabled 환경에서 등록된 regression case가 번역된다. | integration/offline test |
| FR-002 | 의미 결정은 MARCO/semantic resolver에서 grounded Semantic Frame으로 고정되어야 한다. | H | realizer가 frame 밖의 semantic decision을 만들 필요가 없다. | contract + regression test |
| FR-003 | exact Translation Memory hit는 semantic resolution 전에 사용할 수 있어야 한다. | H | 동일 source/domain 입력이 저장된 target으로 반환된다. | unit test |
| FR-004 | 사용자의 명시적 번역 수정은 exact TM에 즉시 반영할 수 있어야 한다. | H | 수정 직후 동일 입력이 corrected target을 반환한다. | unit test |
| FR-005 | 사용자별 persistent terminology는 Base KG와 분리된 User Overlay에 저장되어야 한다. | H | restart 후 overlay가 유지되고 Base KG 파일은 변경되지 않는다. | persistence test |
| FR-006 | session-only entity/context는 session 경계를 넘어 누출되지 않아야 한다. | H | 다른 session/clear 이후 동일 binding이 적용되지 않는다. | unit test |
| FR-007 | 사용자는 translation evidence를 maintenance analysis package로 명시적으로 export할 수 있어야 한다. | H | package가 manifest와 필요한 evidence 집합을 포함한다. | P1-D integration test |
| FR-008 | export된 evidence는 patch proposal이 안정적으로 참조할 수 있는 ID를 가져야 한다. | H | 동일 canonical event의 ID가 의미 없이 변하지 않고 중복 정책이 명시된다. | P1-D deterministic test |
| FR-009 | patch import는 schema, operation, evidence, base version, conflict를 적용 전에 검증해야 한다. | H | invalid patch가 Base KG를 바꾸지 않고 명시적 오류로 종료한다. | negative/security tests |
| FR-010 | patch는 실제 적용 전에 dry-run diff와 영향 범위를 제공해야 한다. | H | dry-run 뒤 Base KG version/content가 변경되지 않는다. | P1-D integration test |
| FR-011 | patch 적용 전후 corpus replay로 changed/improved/regressed/unchanged를 비교할 수 있어야 한다. | H | 동일 corpus에 대해 before/after report가 재현된다. | replay test |
| FR-012 | 외부 LLM patch proposal은 사용자 승인 전 자동 적용되지 않아야 한다. | H | import만으로 active KG version이 바뀌지 않는다. | transaction test |
| FR-013 | 승인된 patch 적용은 원자적으로 새 KG version을 만들고 실패 시 기존 version을 유지해야 한다. | H | injected failure 후 active version과 기존 bytes/logical state가 보존된다. | failure-injection test |
| FR-014 | 사용자는 이전 KG version으로 rollback할 수 있어야 한다. | H | rollback 후 지정 version과 동일한 canonical state가 복구된다. | rollback test |
| FR-015 | Tiny Neural Realizer는 Semantic Frame의 의미를 변경할 authority를 가져서는 안 된다. | H | realizer contract가 frame/terminology를 입력으로 받고 KG write path가 없다. | contract review/test |
| FR-016 | 제품 contract는 macOS, Windows, Android, iOS 구현이 공유할 수 있게 플랫폼 UI/API와 분리되어야 한다. | H | public data contract에 특정 UI toolkit 타입이나 Python object identity가 요구되지 않는다. | architecture review |
| FR-017 | runtime 로그/지식은 사용자의 명시적 동작 없이 외부 서비스로 전송되지 않아야 한다. | H | runtime path와 maintenance export path에 automatic network upload가 없다. | code/security review |
| FR-018 | canonical Knowledge Version은 seed, MARCO `.kg`, frame map, `.mco` 빌드에 영향을 주는 style/config 입력, build provenance와 실제 파생 `.mco` digest를 식별해야 한다. | H | 저장·export·재오픈 시 asset digest, compiler provenance, derived `.mco` hash가 일치한다. | version-store and package integrity tests |

## Quality Attributes

| ID | Attribute | Stimulus / Environment | Required Response | Response Measure |
|---|---|---|---|---|
| QA-001 | Offline capability | 정상 runtime에서 network unavailable | 번역 가능한 local knowledge는 계속 처리 | required regression corpus가 network 없이 통과 |
| QA-002 | Determinism | 동일 input + 동일 TM/overlay/KG/rule version | deterministic 경로는 동일 semantic/result와 provenance 제공 | replay 결과가 동일하게 재생 |
| QA-003 | Fail safety | malformed/corrupt patch/archive | 적용 중단, 기존 active KG 보존 | partial mutation 0 |
| QA-004 | Atomicity | patch transaction 중 failure | 새 version 활성화 금지, 기존 version 유지 | active version change 0 |
| QA-005 | Rollback | 사용자가 과거 version 지정 | 해당 canonical version 복구 | version identity와 canonical content가 기대값과 일치 |
| QA-006 | Traceability | 외부 LLM이 evidence를 참조 | exact source event를 역추적 가능 | dangling evidence reference 0 |
| QA-007 | Privacy | 사용자가 maintenance를 사용하지 않음 | 자동 외부 전송 없음 | background cloud upload 0 |
| QA-008 | Portability | 같은 translation contract를 다른 플랫폼에서 구현 | 플랫폼 adapter 없이 core schema를 해석 가능 | schema/fixture parity; 구체 성능 한계는 P1-F에서 측정 |
| QA-009 | Performance | macOS에서 reference workload 실행 | P1-E/P1-F에서 동일 workload 기준 측정 | latency/RAM/model size 목표는 현재 Measurement Needed |
| QA-010 | Compatibility | persistent schema/version 변화 | 기존 지원 version을 읽거나 명시적 migration/rejection | silent corruption 0 |

## Constraints

- 최종 목표 플랫폼: macOS / Windows / Android / iOS.
- 현재 직접 검증 우선 환경: macOS.
- runtime은 offline-first.
- Base KG runtime self-modification 금지.
- 외부 LLM은 provider-independent maintenance proposal 역할만 한다.
- cloud API는 runtime 필수 dependency가 될 수 없다.
- Python 구현은 현재 reference implementation이다.
- native core 언어는 아직 결정하지 않는다.
- 새 dependency 설치는 capability probe 후 필요 시 사용자 승인 절차를 따른다.

## Assumptions

- MARCO의 public `mco` API가 reference integration boundary로 유지된다.
- P1-D는 사용자 승인에 따라 `kg-patch-v2`를 사용하고, seed-only `kg1_` version과 `kg-patch-v1`을 명시적으로 거부한다. 자동 migration은 없다.
- 성능 수치는 Mac 실측 전 확정하지 않는다.

## Glossary

| Term | Meaning |
|---|---|
| Semantic Frame | source meaning이 결정된 뒤 realizer에 전달되는 구조화된 표현 |
| Base KG | 검증된 공용 지식. runtime read-only |
| User Overlay | 사용자별 persistent preference/limited adaptive knowledge |
| Translation Memory | exact source→target 기억 |
| Session State | session 수명에 한정된 임시 context |
| Maintenance Plane | 로그 export, 외부 분석, patch validation/approval/versioning 경로 |
| Tiny Neural Realizer | Semantic Frame을 target-language sentence로 표현하는 local model |
| Evidence ID | maintenance proposal이 원본 evidence를 안정적으로 가리키는 식별자 |
| Knowledge Version | seed, MARCO source graph, frame map, compiler assets/provenance, verified derived-model digest를 묶는 immutable canonical snapshot |
