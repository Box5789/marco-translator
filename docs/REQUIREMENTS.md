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

### Out of scope for current P2-A
- continuous/background real-time capture loop
- Windows/Android/iOS product UI implementation
- full native MARCO semantic-engine rewrite
- new Tiny Realizer selection/training
- cloud translation runtime
- account/sync/telemetry backend
- production signing/notarization/store release
- automatic persistence of raw screenshots or OCR text

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
| FR-019 | runtime의 public data contract는 Python object identity 없이 직렬화·검증 가능해야 한다. | H | request/result/frame/term/error fixtures를 비-Python 구현이 같은 의미로 읽고 쓴다. | schema + conformance tests |
| FR-020 | Python reference와 product runtime 후보는 같은 frozen conformance fixtures에 대해 동일한 deterministic 의미 결과를 내야 한다. | H | 필수 fixture parity 100%; unknown/unresolved safety parity 유지. | cross-runtime conformance suite |
| FR-021 | product runtime 후보는 실행 시 Python interpreter 또는 MARCO 내부 Python module을 필수로 요구해서는 안 된다. | H | selected portable vertical slice가 Python 없이 macOS/Windows/Android/iOS target에서 build/link되며 required smoke path가 실행된다. | target build/runtime smoke |
| FR-022 | semantic resolver와 neural realizer는 stable boundary 뒤에서 교체 가능해야 한다. | H | fixture resolver와 null/fixture realizer가 core orchestration을 변경하지 않고 대체된다. | component/contract tests |
| FR-023 | runtime persistent semantics는 플랫폼 간 보존되어야 한다. | H | TM/User Overlay/Session 또는 승인된 interchange representation이 Python reference fixture와 round-trip 의미 parity를 가진다. | persistence interop tests |
| FR-024 | platform-specific capture/OCR/UI/permission/lifecycle 코드는 semantic core에 직접 결합되지 않아야 한다. | H | platform smoke host가 thin adapter로 core를 호출하고 core contract에 host UI 타입이 없다. | architecture + host smoke review |
| FR-025 | macOS/Windows/Android/iOS에서 동일한 core conformance version과 fixture identity를 검증할 수 있어야 한다. | H | 네 플랫폼 evidence가 동일 contract/fixture hash를 보고한다. | CI/direct target reports |
| FR-026 | macOS 사용자는 명시적 동작으로 화면/윈도우/영역 캡처를 시작할 수 있어야 한다. | H | user-triggered capture가 선택된 source의 frame을 반환하고 취소가 가능하다. | direct-host acceptance |
| FR-027 | macOS capture flow는 필요한 screen-recording 권한 상태를 감지하고 denied/restricted/granted를 안전하게 처리해야 한다. | H | 권한 미허용에서 crash/무한 재시도 없이 안내하고, 허용 후 capture가 정상 동작한다. | permission-path host test |
| FR-028 | OCR은 캡처된 frame을 local-only로 처리하고 source text 및 bounding information을 translation stage에 전달해야 한다. | H | controlled Chinese fixtures에서 normalized OCR text와 geometry가 oracle에 맞고 network access가 없다. | OCR fixture + offline host test |
| FR-029 | macOS host는 OCR text를 기존 translation backend contract로 전달하고 semantic rule을 UI/capture layer에서 재구현하지 않아야 한다. | H | supported fixture가 canonical translation result를 반환하고 host code에 별도 domain translation rule이 없다. | end-to-end + architecture review |
| FR-030 | 번역 결과는 source app을 수정하지 않는 transient overlay로 표시되고 사용자가 즉시 닫을 수 있어야 한다. | H | overlay가 실제 화면에 표시되고 dismiss/cancel 후 잔존 state가 없다. | direct-host UI test |
| FR-031 | overlay와 app-owned UI는 capture→OCR 입력으로 재유입되어 feedback loop를 만들지 않아야 한다. | H | repeated capture에서 own overlay text가 OCR/translation input으로 재수집되지 않는다. | cycle-guard acceptance test |
| FR-032 | raw screenshot과 OCR source text는 기본 설정에서 디스크에 영구 저장되지 않아야 한다. | H | normal flow 후 app data/temp inventory에 capture artifact가 남지 않는다. | privacy/file-system test |
| FR-033 | capture/OCR/translation/overlay pipeline은 network 없이 동작해야 한다. | H | outbound network denied 상태에서 controlled end-to-end flow가 완료된다. | direct offline host test |
| FR-034 | capture request는 취소 가능하고 새 요청이 이전 요청의 stale OCR/translation 결과를 overlay에 표시하지 않아야 한다. | H | cancel/restart/re-entry 테스트에서 latest-request state만 commit된다. | state/temporal host test |
| FR-035 | P2-A는 capture→OCR→translation→overlay 단계별 latency를 같은 controlled workload로 측정해야 한다. | M | stage timing과 end-to-end p50/p90이 기록된다. | performance report |
| FR-036 | macOS app boundary는 P1-F Rust runtime/portable contract와 호환되고 platform code가 core contract에 UI 타입을 추가하지 않아야 한다. | H | host adapter가 versioned C ABI/portable contract를 사용하고 P1-F conformance regression이 유지된다. | integration + P1-F regression |

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
| QA-008 | Portability | 같은 translation contract를 다른 플랫폼에서 구현 | 플랫폼 adapter 없이 core schema를 해석 가능 | schema/fixture parity; P1-F는 자원 기준선을 측정하고 제품 budget은 정하지 않음 |
| QA-009 | Performance | macOS에서 reference workload 실행 | P1-E/P1-F에서 동일 workload 기준 측정 | latency/RAM/model size 목표는 현재 Measurement Needed |
| QA-010 | Compatibility | persistent schema/version 변화 | 기존 지원 version을 읽거나 명시적 migration/rejection | silent corruption 0 |
| QA-011 | Runtime portability | 동일 frozen runtime contract를 네 target에서 build/run | 플랫폼별 adapter 차이와 무관하게 core fixture 의미 유지 | required conformance mismatch 0 |
| QA-012 | FFI/API safety | host가 invalid payload/error를 전달 | crash/UB 대신 versioned error contract로 실패 | unhandled boundary crash 0 in conformance suite |
| QA-013 | Runtime independence | product runtime process 시작 | Python/MARCO internal module 없이 portable slice 실행 | Python runtime dependency 0 for selected slice |
| QA-014 | Resource observability | target smoke workload 실행 | binary/startup/latency/memory 또는 측정 가능한 subset 기록 | 임의 product threshold 없이 platform별 measured evidence 기록 |
| QA-015 | Capture privacy | 사용자가 화면 번역을 실행 | capture frame/OCR text는 처리 중 memory에만 유지되고 명시적 export 없이는 persisted/logged되지 않음 | default persistent raw capture artifact 0 |
| QA-016 | Permission resilience | screen-recording permission 미허용/변경 | app이 안전한 상태로 남고 복구 경로 제공 | crash 0, stale overlay 0 |
| QA-017 | Interaction safety | overlay 표시 중 사용자가 원래 앱과 상호작용 | overlay lifecycle이 source content를 변경하지 않고 닫기/취소 가능 | trapped input/focus loop 0 in acceptance flow |
| QA-018 | Pipeline observability | controlled capture workload 반복 | stage/end-to-end latency를 같은 조건으로 기록 | measured p50/p90; product threshold는 P2-A evidence 전 미정 |

## Constraints

- 최종 목표 플랫폼: macOS / Windows / Android / iOS.
- 현재 직접 검증 우선 환경: macOS.
- runtime은 offline-first.
- Base KG runtime self-modification 금지.
- 외부 LLM은 provider-independent maintenance proposal 역할만 한다.
- cloud API는 runtime 필수 dependency가 될 수 없다.
- Python 구현은 현재 reference implementation이다.
- portable runtime 언어/구현 전략은 P1-F ADR-007의 Rust shared core 결정을 따른다. 최종 MARCO semantic engine과 neural realizer는 별도 evidence 전까지 미결정이다.
- P1-F에서는 architecture 후보를 실제 source/pattern/capability evidence로 비교한 뒤, 명확한 단일 결론이면 task 권한 안에서 ADR을 확정할 수 있다. 여러 후보가 기준을 충족하면서 장기 trade-off가 남으면 구현 전 사용자 정렬을 요청한다.
- dependency/toolchain은 capability probe가 선행되며, `work/current.md`의 현재 작업 사전 승인 경계를 따른다.

## P2-A implementation interpretation

- FR-026의 region 선택은 macOS system picker가 제공하는 single-window/single-display 선택 뒤 앱 preview에서 사용자가 drag-crop하는 흐름이다. 캡처 전 선택은 항상 명시적이며 한 번의 frame만 처리한다.
- FR-028은 Vision revision 3의 accurate `zh-Hans` OCR로 구현한다. 언어 범위는 현재 controlled fixture와 capability evidence가 확인한 간체 중국어다.
- FR-029/FR-036은 UI가 의미 규칙을 복제하지 않도록 P1-F `marco-runtime.v1` C ABI를 호출한다. Rust resolver는 frozen fixture set만 다루며 full Python/MARCO semantic engine과 동등하다고 간주하지 않는다.
- FR-030의 결과는 별도 AppKit floating panel로 표시하고 사용자가 닫거나 요청을 취소할 수 있다. Panel과 host window는 캡처 대상에서 제외하도록 설정한다.
- FR-032/FR-033에서 frame, OCR 문자열, 처리 시간은 요청 중 메모리에서만 유지한다. 앱 로그, screenshot history, cloud request는 생성하지 않는다. 실제 direct-host inventory/offline 결과는 `work/current.md`에 기록한다.

## Assumptions

- MARCO의 public `mco` API가 reference integration boundary로 유지된다.
- P1-D는 사용자 승인에 따라 `kg-patch-v2`를 사용하고, seed-only `kg1_` version과 `kg-patch-v1`을 명시적으로 거부한다. 자동 migration은 없다.
- P2-A의 제품 latency/resource 목표는 실제 host 측정 후 정한다.

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
