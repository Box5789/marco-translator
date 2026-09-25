# Engineering Baseline

## 1. Baseline identity

Engineering baseline branch:
- `p1/engineering-baseline-macos`

Source baseline:
- `p1/user-overlay`
- commit `06b8954fd0851e361707b5b11d491b90148a887b`

Related stacked PRs at baseline creation:
- PR #1: `p1/marco-semantic-adapter → main`
- PR #2: `p1/user-overlay → p1/marco-semantic-adapter`

두 PR은 이 baseline 작업에서 merge하지 않는다.

Engineering discipline reference verified at:
- `Box5789/software-engineering-discipline@6f69339c7427fd5255bf5a0896413ea5e6c567d3`

## 2. Documentation preflight at baseline creation

| Candidate | Status | Authority / Note |
|---|---|---|
| `AGENTS.md` | Absent → created by baseline | project engineering rules |
| `AGENT_GUIDE.md` | Absent → created by baseline | durable product guidance |
| `AGENT_HANDOFF.md` | Absent | no active handoff |
| `docs/AGENT_HANDOFF.md` | Absent | no active handoff |
| `work/current.md` | Absent → created by baseline | active task state |
| `graphify-out/graph.json` | Absent | Graphify navigation unavailable; no install attempted |
| `README.md` | Read | product overview |
| `docs/ARCHITECTURE.md` | Read | current runtime architecture |
| `docs/AUTOMATIC_LEARNING.md` | Read | mutable knowledge policy |
| `docs/MARCO_PROTOCOL.md` | Read | MARCO integration contract |
| `docs/P1.md` | Read | phase checklist |
| `schemas/kg-patch.schema.json` | Read | current patch schema |
| `schemas/translation-log.schema.json` | Read | current log schema |
| `prompts/kg-maintenance.md` | Read | external maintenance contract |
| `pyproject.toml` | Read | Python reference package definition |

## 3. Confirmed implementation state

### P1-A — complete
- request/result/frame contracts
- conservative normalization
- exact Translation Memory
- deterministic resolver boundary
- Rule Realizer
- Neural Realizer interface
- JSONL logging
- patch proposal validation boundary
- maintenance prompt
- zh→ko gaming regression corpus

### P1-B — complete
- MARCO semantic ontology
- MARCO node → Semantic Frame map
- translator `.mco` source/build
- actual upstream MARCO CI build/integration
- safe unknown handling

### P1-C — complete
- persistent SQLite User Overlay
- explicit correction → TM
- repeated correction → pending proposal
- session-only entity binding
- bounded/reversible routing-weight adaptation

"Complete" here means the prior branch/CI evidence at the baseline commit. 현재 P1-D 이후의 제품 validation까지 포함한다는 뜻은 아니다.

## 4. User-goal use cases

### UC-001 Translate offline text
Primary actor: 번역 사용자

Preconditions:
- 필요한 local knowledge/model assets가 설치되어 있다.

Success guarantee:
- source가 grounded될 수 있으면 target text와 provenance를 반환한다.
- grounded될 수 없으면 의미를 추측하지 않고 unresolved로 남긴다.

Main flow:
1. 사용자가 source text와 language/domain context를 제공한다.
2. 시스템이 normalization/TM/semantic resolution을 수행한다.
3. Semantic Frame을 deterministic rule 또는 constrained realizer로 표현한다.
4. 시스템이 translation result와 log evidence를 만든다.

Extensions:
- TM hit: semantic resolver를 건너뛴다.
- unknown: fluent guess를 만들지 않는다.

### UC-002 Correct translation
Primary actor: 번역 사용자

Success guarantee:
- 명시적 수정은 exact TM에 반영된다.
- 반복 수정이 persistent overlay 후보가 되더라도 자동 승인되지 않는다.

### UC-003 Maintain semantic knowledge
Primary actor: 지식 유지보수 사용자

Success guarantee:
- 사용자가 명시적으로 evidence를 export한다.
- 외부 LLM은 proposal만 만든다.
- local validation과 replay를 통과하고 사용자가 승인한 patch만 새 KG version이 된다.
- rollback 가능하다.

### UC-004 Use temporary session terminology
Primary actor: 번역 사용자

Success guarantee:
- binding은 지정 session에만 적용되고 clear/종료 후 누출되지 않는다.

## 5. Domain Model

| Concept | Attributes | Associations | Meaning |
|---|---|---|---|
| Translation Request | source text, language pair, domain, style, session | produces Translation Result | 한 번의 번역 요구 |
| Translation Result | target text, path, confidence, warnings | may reference Semantic Frame | 번역 결과 |
| Semantic Frame | intent, terms, slots, unresolved, confidence | resolved from Base KG/Overlay context | 의미 결정 결과 |
| Translation Memory Entry | language pair, domain, source, target, origin | selected before semantic resolution | exact supervision memory |
| Base KG Version | version identity, semantic content | parent/patch lineage | 검증된 공용 지식 snapshot |
| User Overlay Entry | scope, source, target/concept, status | belongs to user profile | 개인 persistent preference |
| Session Binding | session id, source, target/concept | belongs to one session | 임시 context |
| Translation Evidence | stable id, request/result/provenance | exported in Analysis Package | maintenance 근거 |
| Analysis Package | manifest, evidence subsets, KG metadata | input to external analysis | 사용자 명시 export artifact |
| Patch Proposal | base version, operations, evidence refs | proposed against Base KG Version | 외부 LLM의 변경 제안 |
| Patch Validation Report | schema/conflict/evidence/replay results | evaluates Patch Proposal | 적용 전 검증 결과 |
| KG Version Transaction | base version, patch, target version, state | activates a new Base KG Version | 승인된 원자적 변경 |

도메인 모델에는 UI widget이나 DB table을 넣지 않는다.

## 6. System Sequence Diagrams

### SSD — UC-001 Translate offline text

| Step | Actor/System Event | Parameters | System response |
|---|---|---|---|
| 1 | `translate` | source, languages, domain, style, session | target/provenance 또는 unresolved |
| 2 | `correct` (optional) | source, corrected target | TM update + optional pending overlay proposal |

### SSD — UC-003 Maintain semantic knowledge

| Step | Actor/System Event | Parameters | System response |
|---|---|---|---|
| 1 | `exportAnalysisPackage` | selected logs/version | local package path + manifest |
| 2 | 외부 LLM 분석 | user-controlled external action | patch proposal file |
| 3 | `importPatchProposal` | proposal | validation result; active KG unchanged |
| 4 | `dryRunPatch` | valid proposal | diff + replay impact |
| 5 | `approvePatch` | proposal id | new KG version activated atomically |
| 6 | `rollbackKgVersion` | version id | selected version activated |

## 7. Key Operation Contracts

### translate(request)

Preconditions:
- request contract is valid.

Postconditions:
- result path is one of the declared runtime paths.
- grounded output has provenance appropriate to its path.
- unresolved input is not silently promoted by an unconstrained realizer.
- Base KG is unchanged.

### correct(request, correctedText)

Preconditions:
- corrected target is non-empty.

Postconditions:
- exact TM entry reflects explicit user correction.
- correction evidence is logged when logging is configured.
- repeated correction may create a pending User Overlay proposal.
- Base KG is unchanged.

### exportAnalysisPackage(selection)

Preconditions:
- user explicitly initiates export.

Postconditions:
- package is created locally.
- manifest identifies schema/version inputs.
- included evidence has stable IDs.
- no automatic external transfer occurs.

### importPatchProposal(proposal)

Preconditions:
- file is locally supplied by user.

Postconditions:
- schema/operation/evidence/base-version/conflict validation result is returned.
- active Base KG is unchanged.

### approvePatch(proposal)

Preconditions:
- proposal is valid.
- required replay/impact checks satisfy active policy.
- user explicitly approves.

Postconditions:
- either one complete new KG version becomes active or no active state changes.
- previous version remains recoverable.
- transaction provenance records proposal/evidence/base/new version.

### rollbackKgVersion(version)

Preconditions:
- target version exists and is compatible.

Postconditions:
- requested version becomes active atomically.
- TM/User Overlay/Session State are not rewritten as a side effect.

## 8. Architecture decisions

### ADR-001 — Runtime / Maintenance plane separation
Status: Accepted

Decision:
- runtime translation은 cloud dependency 없이 local로 동작한다.
- 외부 LLM은 user-controlled maintenance proposal 단계에만 참여한다.

### ADR-002 — Base KG and adaptive state separation
Status: Accepted

Decision:
- Base KG, User Overlay, TM, Session State는 별도 책임을 가진다.
- runtime self-learning이 Base KG topology를 직접 바꾸지 않는다.

### ADR-003 — Neural Realizer semantic authority
Status: Accepted

Decision:
- Tiny Neural Realizer는 realization만 담당한다.
- semantic decision은 upstream frame을 따른다.

### ADR-004 — Cross-platform core implementation technology
Status: Proposed / Undecided

Decision:
- 아직 선택하지 않는다.

Evidence required before decision:
- P1 contract inventory
- macOS benchmark
- platform capability constraints
- FFI/build/distribution analysis
- model runtime requirements

Candidate set은 `docs/PLATFORM_STRATEGY.md`를 따른다.

### ADR-005 — Canonical Knowledge Version and patch mutation semantics
Status: Accepted — 사용자 결정, 2026-09-24

Context and evidence:
- `KnowledgeStore.from_json` consumes `knowledge/seed.zh-ko.json`; `MarcoResolver` separately consumes `knowledge/marco-frame-map.zh-ko.json`.
- `scripts/build_marco_pack.py` compiles the selected source graph from `marco/` through `mco.compile`.
- Upstream MARCO `DoTaeIn/Marco@59d19de74443b5f3768e27032ef83e1c592b0d47` documents deterministic `.mco` output. Its compiler packages selected `.kg` files and `kgpack.model_files()`, which includes `styles/*.json` and `axioms/*.json`. The current translator source contains the semantic graph and `marco/styles/translator.json`.
- MARCO graph authoring defines `[개념]` examples as routeable node examples, `[무관]` examples as unrelated/distractor input, and `[논증]` as typed graph relations. `부정관계` is a rebuttal relation, not a classifier negative example. The `.kg` contract has no per-edge numeric weight field.
- `SQLiteUserOverlay` bounds user route bias; `MarcoResolver` uses it only for the trace-rescue margin of an already mapped node. Seed `confidence` is lexical confidence.

Alternatives considered:
| Option | Result | Reason |
|---|---|---|
| Version only the runtime seed | Rejected | Cannot identify the MARCO graph, frame mapping, or compiled routing behavior. |
| Treat `.mco` as the sole authoritative artifact | Rejected | Loses editable source and reproducible build inputs. |
| Version editable sources, compiler inputs/provenance, and the verified derived output | Accepted | Supports complete dry-run, replay, restart, activation, and rollback. |

Decision:
- A canonical Knowledge Version contains the exact `knowledge/seed.zh-ko.json`, `marco/graphs/graph_zh_ko_gaming_semantics.kg`, `knowledge/marco-frame-map.zh-ko.json`, and every MARCO model asset consumed from `marco/styles/*.json` and `marco/axioms/*.json`.
- Its build provenance records the upstream MARCO repository/revision, `mco` and NumPy versions, Python implementation/version, platform/architecture/zlib, build recipe and script/module SHA-256, canonical compiler-input digests, and the actual deterministic `.mco` output SHA-256/size. The version identity hashes the canonical asset digests and provenance, including the derived-output digest. The `.mco` bytes are stored as a verified derived runtime artifact, not as an editable canonical source.
- Patch schema `kg-patch-v2` keeps all seven operation names. Every operation requires `resource`, a resource-scoped stable `target`, `expected_old_state`, `proposed_new_state`, and evidence IDs. Add operations require an absent old state; adjustments require the exact current old value. Resources are a closed allowlist; no patch supplies a filesystem path or changes code.
- `ADD_ALIAS`, `ADD_SENSE`, and `ADD_DOMAIN_SENSE` add entries to the seed. `ADD_ALIAS` must reuse an existing concept; `ADD_SENSE` is global; `ADD_DOMAIN_SENSE` requires a domain.
- `ADD_PATTERN` adds an example to an existing node in the MARCO graph's `[개념]` section. `ADD_NEGATIVE_CONSTRAINT` adds a distractor example to `[무관]`. `ADD_RELATION` adds one typed edge to `[논증]`, using a relation declared by that graph.
- `ADJUST_WEIGHT` targets either seed `confidence` (lexical confidence in 0..1) or frame-map `routing_weight` (semantic route margin bias in -0.10..0.10, default 0). The latter follows the existing mapped-node trace-rescue hook; it does not change MARCO's selected node. When combined with user-scoped route bias, the total applied bias remains bounded to ±0.10. `부정관계` and MARCO global thresholds are not treated as per-target weights.
- Active state changes only after schema, evidence, base identity, target identity, expected-state/conflict, build, replay, and explicit user approval pass. Complete immutable version snapshots, derived `.mco` bytes, lineage, and the active-version pointer are committed in one standard-library SQLite transaction. Runtime files are a verified materialized cache; the database snapshot is canonical. User Overlay, TM, and Session State remain outside the version transaction.

Consequences:
- Seed-only `kg1_` identities and the underspecified `kg-patch-v1` are rejected for the new transaction path; there is no silent migration or auto-apply.
- The frame-map contract gains an optional bounded `routing_weight` field with default 0. MARCO source syntax remains unchanged.
- The Python version store is a P1 reference implementation. P1-E/F and platform-native persistence remain out of scope.

## 9. Responsibility assignment

| Responsibility | Current module/boundary | Rationale |
|---|---|---|
| orchestration | Translator pipeline | Controller: 요청 흐름 조정 |
| semantic selection | Resolver / MARCO adapter | Protected Variation around semantic engine |
| exact memory | Translation Memory | Information Expert for exact translation entries |
| personal persistent state | User Overlay | Pure Fabrication separating user persistence from KG |
| session state | Session State | lifecycle owner of ephemeral context |
| realization | Rule/Neural Realizer boundary | semantic/linguistic responsibility separation |
| maintenance validation | Maintenance boundary | trust-boundary validation separated from runtime |

OOP applies because persistent mutable state, service boundaries, and interchangeable resolver/realizer collaborators exist. Inheritance is not required by the baseline; composition/interfaces are preferred only where a current variation point exists.

## 10. Gap at baseline creation

At baseline creation, P1-D remained the active gap. Its approved scope and final evidence are recorded in `work/current.md`.

## 11. ADR-006 — P1-E tiny realizer benchmark decision

Status: Benchmark complete; off-the-shelf candidate not selected. Product runtime remains undecided.

Context and evidence:
- The frozen workload contains five grounded gaming frames and one unknown-input invocation case. Workload SHA-256 is `4014f59dd1b31bd61a4b4b71ce51252cd5160213f1df5b8b733a71cef088f24e`; the frames were re-derived from actual MARCO `ffedc8b8552505e515b8f5ea2ae7f9934d7ef58e` and the versioned `.mco`.
- The same target-only prompts and Qwen3-0.6B Q4_K_M candidate ran twice on macOS 26.6.2 / Apple M5 / 32 GiB. Both runs produced identical outputs for all five cases and every repetition.
- Candidate semantic hard checks passed 0/5 cases after the oracle explicitly rejected slot-present relation reversals and unsupported claims; exact terminology passed 4/5. Rule baseline semantic checks passed 5/5; terminology also passed 4/5 because `FEED_ENEMY` targets `킬 헌납` while its grounded slot and expected output use `죽어주면`.
- Candidate warm API latency medians were 93.58–95.69 ms (p90 144.33–146.18 ms, observed max 151.87–184.58 ms). Cold first-call wall time was 712.2–715.7 ms, including 577.4–578.3 ms model load. Sampled Ollama process-tree RSS peak was 953.2–955.2 MiB. Model artifact size was 522,653,767 bytes; Ollama reported 751.63M parameters and Q4_K_M. Rule-boundary medians were 0.000333–0.000375 ms (p90 0.000416–0.000500 ms).
- The production pipeline made 0 neural-realizer calls across five grounded cases; the unknown case remained unresolved. Current seed has 10 entries and no dedicated training corpus is present.
- The two raw reports are `benchmarks/p1-e/results/run-1.json` (SHA-256 `71be925e7fa75e967733dae5498e92fe1a6ca0f6f8ecc189c0f55769bdbb0ba5`) and `benchmarks/p1-e/results/run-2.json` (SHA-256 `38800321ba29ef61a451f628d0d767ab355f6b087d1a35191be72eade08edfdd`). Runner SHA-256: `8a901525441334a3aebfa905598977c154bc2e534d722186c2b56946900133a7`.

Alternatives considered:
| Option | Result | Reason |
|---|---|---|
| Select Qwen3-0.6B Q4_K_M for product realization | Rejected | It violates semantic hard constraints on all five grounded cases and adds latency and RAM while the rule path already resolves the workload. |
| Train/distill a 100–300M model now | Not justified | Five benchmark frames, 10 seed entries, zero current neural invocations, and no training corpus do not support a training-quality claim. |
| Keep the deterministic path and retain the neural boundary without selecting a model/runtime | Accepted | It preserves semantic authority and leaves later runtime decisions evidence-driven. |

Decision:
- Do not select this candidate for product use. Keep neural realization subordinate to a grounded frame and the rule-first pipeline.
- Do not start 100–300M training or fine-tuning in P1-E. Revisit only when a representative, licensed training/evaluation corpus and a grounded neural-fallback workload exist.
- Do not choose a product runtime, quantization policy, shared-core language, or P1-F architecture from this benchmark. No latency/RAM product threshold is set here.
- Preserve the final frame's exact term/slot conflict in the benchmark record; do not silently rewrite the knowledge contract to improve a score.

Candidate asset provenance: `qwen3:0.6b-q4_K_M`, Ollama 0.34.0, manifest digest `sha256:7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435`, Apache-2.0. Public references checked 2026-09-25: https://huggingface.co/Qwen/Qwen3-0.6B/tree/main and https://ollama.com/library/qwen3/tags.

Consequences:
- P1-E is complete with the candidate held. Existing rule-only outputs remain the selected realization behavior for this workload.
- A future candidate evaluation must preserve the frozen SemanticFrame authority and report semantic, terminology, fluency, resource, and invocation evidence independently.
