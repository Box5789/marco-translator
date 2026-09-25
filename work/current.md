# Current Task — P1-E Tiny Realizer Benchmark

- Status: Complete — benchmark, required regressions, documentation, and delivery ready
- Branch: `p1/tiny-realizer-benchmark`
- Parent baseline: `p1/engineering-baseline-macos@72a8e98fc39bbe33e13910005188020050ace302`

P1-D의 전체 Engineering Record는 `work/p1-d-knowledge-maintenance.md`에 보존한다.

## Goal

`software-engineering-discipline`의 full-scope gate를 적용해 Tiny Neural Realizer가 Marco Translator의 semantic authority를 침범하지 않으면서 실제 macOS local runtime에서 사용할 가치가 있는지 정량·정성 evidence로 검증한다.

정확한 사용자 observable outcome:

> 동일한 grounded Semantic Frame workload에 대해 rule-only baseline과 local neural realizer 후보를 비교하고, semantic preservation·terminology compliance·fluency·latency·peak RAM·model size·neural invocation rate를 재현 가능하게 측정한다. 결과를 근거로 다음 단계에서 사용할 후보 또는 "현재 후보 없음 / dedicated small realizer가 필요함"을 결정할 수 있어야 한다.

## Current stage

- P1-A: Complete
- P1-B: Complete
- P1-C: Complete
- P1-D: Complete
- P1-E: Complete
- P1-F: Not started

## Accepted decisions

- 최종 플랫폼: macOS / Windows / Android / iOS.
- P1-E의 첫 직접 benchmark/validation 플랫폼: macOS.
- macOS-first는 macOS-only runtime 결정을 의미하지 않는다.
- Base KG / User Overlay / TM / Session State의 기존 경계를 바꾸지 않는다.
- Tiny Neural Realizer는 meaning resolver가 아니다.
- frame/terminology와 충돌하는 출력을 semantic success로 간주하지 않는다.
- runtime cloud API dependency를 도입하지 않는다.
- 최종 model, inference runtime, quantization format은 benchmark evidence 전에 확정하지 않는다.
- shared native core 기술 선택은 P1-F 범위이며 P1-E에서 확정하지 않는다.
- 성능 목표 수치는 실측 전에 임의로 고정하지 않는다.
- Qwen3-0.6B Q4_K_M was measured but not selected: strengthened semantic oracle 0/5; current grounded pipeline neural invocation 0/5.
- 100–300M dedicated training is not justified by the current five-frame workload, 10 seed entries, and absent training corpus.

## Scope

### In scope

1. Documentation preflight와 현재 realizer contract/source/test 복원
2. macOS capability probe
   - 현재 hardware/OS/runtime
   - 이미 설치된 local inference capability
   - 새 dependency/model download 필요 여부
3. Benchmark contract
   - frozen Semantic Frame workload
   - terminology constraints
   - deterministic oracle
   - measurement procedure/version identity
4. Rule-only baseline
5. 최소 1개 sub-1B off-the-shelf local model 후보 조사 및 실제 macOS benchmark
6. 100–300M dedicated/distilled/fine-tuned 후보의 필요성·데이터 적합성 판단
   - 충분한 근거가 있으면 별도 benchmark candidate로 진행
   - 근거가 부족하면 "not justified yet"을 evidence와 함께 기록하고 임의 학습하지 않음
7. Semantic preservation 측정
8. Terminology compliance 측정
9. Fluency 측정
10. Performance/resource 측정
    - cold/warm latency
    - 반복 실행 분포
    - peak RAM
    - model-on-disk size
11. Neural invocation rate 측정 또는 동일 기준의 reproducible estimate
12. local assets 준비 후 offline inference 검증
13. 기존 P1-A~P1-D regression 유지
14. benchmark 결과와 architecture implications를 Engineering/Decision Record에 반영

### Pre-authorized benchmark environment boundary

사용자가 P1-E 범위에 한해 다음 작업을 사전 승인했다. 이 승인은 `AGENTS.md`의 설치 승인 요구를 아래 범위에서 충족한 것으로 기록한다.

자동 허용:
- project-local `.venv` 또는 `/tmp`의 disposable isolated environment 생성
- 해당 isolated environment 내부의 필요한 Python package 설치
- 공개 benchmark model/runtime asset 다운로드
- project-local 또는 명시된 benchmark cache/temp 경로 사용
- benchmark가 요구하는 local-only model conversion/quantization artifact 생성

자동 허용 작업도 먼저 capability probe를 수행하고, 이미 설치된 충분한 도구가 있으면 재사용한다. 설치/다운로드한 package·model의 이름, version/revision, license, source, 저장 위치, 실제 disk size를 Engineering Record에 남긴다. benchmark asset과 cache는 source artifact로 commit하지 않는다.

별도 승인이 필요한 항목:
- Homebrew 등 system package manager 변경
- global Python, `--user`, `--break-system-packages` 설치
- OS 설정, driver, system runtime 변경
- 인증 token/login이 필요한 model 또는 private/restricted asset
- 유료 API/서비스 사용
- 기존 사용자 파일이나 persistent environment 덮어쓰기
- 단일 다운로드가 4 GiB를 초과하거나, 예상 총 신규 다운로드가 8 GiB를 초과하는 작업

별도 승인 대상에 도달해도 독립적으로 가능한 corpus 설계, source inspection, benchmark harness, rule baseline, 문서/분석 작업은 계속한다.

### Explicitly out of scope

- P1-F native/core port
- Rust/C++/Swift 등 shared core 언어 확정
- Windows/Android/iOS 실기 benchmark
- OCR
- screen capture
- overlay UI
- cloud inference service
- Base KG patch semantics 재설계
- P1-D version/rollback 계약 변경
- PR #1/#2 merge
- release/tag

## Acceptance criteria

| ID | Criterion | Direct evidence | Status |
|---|---|---|---|
| AC-E1 | benchmark workload와 fixture identity가 고정되고 재현 가능하다 | versioned workload SHA-256 `4014f59dd1b31bd61a4b4b71ce51252cd5160213f1df5b8b733a71cef088f24e`; both reports match workload, prompt and runner hashes and all repeated outputs | Validated |
| AC-E2 | rule-only baseline이 동일 workload로 측정된다 | two reports: 50 calls/run, semantic 5/5, median 0.000333–0.000375 ms | Validated |
| AC-E3 | 최소 1개 sub-1B local candidate가 실제 Mac에서 실행된다 | Qwen3 0.6B, Q4_K_M, local Ollama on Apple M5 | Validated |
| AC-E4 | semantic preservation이 독립 metric/oracle로 측정된다 | slot/contradiction/relation/unsupported-claim oracle: rule 5/5, candidate 0/5 | Validated; candidate fails hard constraint |
| AC-E5 | terminology compliance가 독립적으로 측정된다 | exact `TermDecision.target` oracle: rule and candidate 4/5 | Validated; final frame has documented term/slot conflict |
| AC-E6 | fluency가 semantic correctness와 분리된 rubric으로 기록된다 | 1–5 separate single-reviewer scores: rule mean 4.6, candidate mean 2.6 | Validated |
| AC-E7 | 동일 workload에서 latency/RAM/model size가 측정된다 | two cold/warm reports; sampled process-tree RSS and exact model bytes | Validated |
| AC-E8 | neural invocation rate가 실제 pipeline 또는 재현 가능한 기준으로 계산된다 | actual MARCO pipeline: 0/5 grounded, 0/6 including unknown | Validated |
| AC-E9 | local assets 준비 후 inference가 network-disabled 상태에서 실행된다 | two direct inference runs under loopback-only macOS sandbox; Ollama cloud disabled | Validated |
| AC-E10 | P1-A~P1-D regression이 유지된다 | full suite normal and network-disabled, each 62 passed/0 skipped; actual MARCO `.mco` included | Validated |
| AC-E11 | 100–300M candidate의 수행/보류가 데이터·compute·품질 evidence로 정당화된다 | five frames, ten seed entries, no training corpus and zero invocation rate | Not justified; no training performed |
| AC-E12 | 최종 benchmark conclusion이 특정 후보 채택/보류/전용 realizer 필요 중 하나로 evidence와 함께 정리된다 | ADR-006 and two immutable reports | Validated; candidate held, rule path retained, runtime remains undecided |
| AC-E13 | P1-F/native-core 기술 선택을 선행하지 않는다 | diff/decision review; no core/runtime or cross-platform choice | Validated |

## Benchmark design constraints

- 입력 semantic authority는 `SemanticFrame`과 constrained terminology에 있다.
- raw source text를 후보 모델에 제공할 경우에도 semantic conflict 시 frame이 우선한다는 것을 test로 증명해야 한다.
- model이 KG/TM/User Overlay를 직접 수정하는 경로를 만들지 않는다.
- benchmark prompt/template은 후보별로 임의 최적화해 공정성을 깨뜨리지 않는다. 후보별 필수 adapter 차이는 기록한다.
- rule-only와 neural 후보는 가능한 한 동일한 logical workload를 사용한다.
- warmup, repetition count, measurement start/end, hardware state를 기록한다.
- 실패/timeout/OOM/unsupported operation은 누락하지 않고 결과로 분류한다.
- semantic failure를 fluency 점수로 상쇄하지 않는다.

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
10. `docs/ARCHITECTURE.md`
11. `docs/MARCO_PROTOCOL.md`
12. realizer/pipeline 관련 source와 tests
13. 필요 시 `work/p1-d-knowledge-maintenance.md`

순으로 현재 상태를 복원한다.

`graphify-out/graph.json`이 있으면 navigation evidence로 사용하되 canonical docs/source/test를 대체하지 않는다.

## Validation set

- benchmark harness unit/component tests
- frozen corpus reproducibility
- semantic preservation
- terminology compliance
- fluency rubric integrity
- repeated macOS performance measurement
- memory measurement
- model asset size
- neural invocation rate
- offline inference
- P1-A~P1-D regression
- actual upstream MARCO integration
- failure/timeout/OOM/invalid-output handling where applicable

failed/skipped/timed-out result는 reproducible classification과 impact statement 없이 완료로 처리하지 않는다.

## Material decisions still open

다음은 benchmark evidence가 나오기 전에는 결정하지 않는다.

- 어떤 off-the-shelf model이 최종 후보인지
- 어떤 inference runtime이 product runtime에 적합한지
- quantization 형식
- 100–300M 전용 모델 학습 필요 여부
- 최종 latency/RAM budget
- Apple-specific acceleration을 공통 architecture contract로 승격할지 여부

## Stop condition

다음이 모두 충족되면 P1-E를 종료한다.

1. AC-E1~AC-E13이 validated 또는 명시적으로 evidence-based Not applicable/Not justified로 분류됨
2. 동일 frozen workload 기반 rule-only/sub-1B 비교 완료
3. semantic/terminology/fluency/resource 결과가 분리되어 기록됨
4. macOS direct benchmark 완료
5. local inference offline 검증 완료
6. 기존 P1-A~P1-D regression 유지
7. relevant requirements/test/traceability/ADR 문서가 실제 결과와 일치
8. `docs/P1.md`는 증거가 있는 P1-E 항목만 완료 처리
9. `work/current.md`에 final Engineering Record, residual risk, P1-F start condition 기록
10. 한국어 commit title/body로 해당 branch에 commit/push하고 remote ref 확인
11. P1-F 구현은 시작하지 않음

## Residual risks at task start

- The hard semantic oracle covers the five frozen frames only; it cannot prove broad translation quality.
- Fluency was scored by one reviewer, not an independent native-speaker panel.
- The exact terminology target for `FEED_ENEMY` conflicts with its semantic slot; both baselines record that failure explicitly.
- Sampled process-tree RSS can miss brief peaks and can count shared resident pages more than once.
- No product latency/RAM target, final model, or product inference runtime was selected; those remain outside P1-E.

## Next step

P1-E is complete. Do not start P1-F until it is recorded as the active scope in `work/current.md`; carry forward the semantic-authority boundary, five-frame oracle limitation, and unresolved term/slot conflict.

## Engineering Record — P1-E continuation 2026-09-25

### Goal, authority, and stop condition

- Goal: P1-E benchmark scope를 끝내고 evidence로 후보의 사용 가치 또는 보류를 결정한다.
- Exact observable outcome: 같은 grounded Semantic Frame 입력에서 rule-only와 local sub-1B candidate 출력을 비교하고 semantic/terminology hard constraints, fluency, latency, peak RAM, model size, invocation rate를 재현 가능한 기록으로 남긴다. Unknown frame은 neural guess로 승격되지 않는다.
- Authority: 사용자가 이 P1-E 전체 scope 및 여기 기재한 격리 환경/package/public asset 한도를 승인했다. 지정 branch commit/push도 승인됐다.
- Non-goals: P1-F, native-core/runtime 선택, Windows/Android/iOS host benchmark, OCR/capture/overlay, cloud inference, P1-D contract 변경, PR merge, release/tag, unsupported fine-tuning.
- Stop: AC-E1–E13 및 required regression/offline/macOS evidence 완료, 문서·record 갱신, Korean commit/push와 remote-ref 비교 뒤 종료한다.

### Baseline and recovered state

- Repository: `Box5789/marco-translator`.
- Branch: `p1/tiny-realizer-benchmark`, tracks `origin/p1/tiny-realizer-benchmark`.
- Baseline: `174b05f4e3a132e682068fbfeafcb0d56520be67` (`P1-E 격리 설치와 공개 모델 다운로드 사전 승인 기록`); remote matched at recovery.
- Working tree/index: clean; sole untracked `graphify-out/` came from the preceding P1-D session. Preserve and exclude from commit.
- Parent/task transition: branch starts from P1-D completion at `72a8e98fc39bbe33e13910005188020050ace302`.
- Graphify: existing untracked generated graph is from P1-D and may be stale for this branch. Read-only inline traversal used resolved interpreter `/Users/pck2790/.local/share/uv/tools/graphifyy/bin/python`; `neural`, `realizer`, `frame`, `semantic`, `benchmark`, `terminology`, `runtime`, `translation` mapped to `docs/ENGINEERING_BASELINE.md`, `src/marco_translator/realizer.py`, `models.py`, and pipeline/test nodes. No lessons or wiki index found. Graph is navigation evidence only.

### Documentation preflight

| Candidate | Status | Use |
|---|---|---|
| `AGENTS.md`, `AGENT_GUIDE.md` | Read | workflow, product boundary, active stage |
| `AGENT_HANDOFF.md`, `docs/AGENT_HANDOFF.md` | Absent | no handoff |
| `work/current.md` | Read | P1-E scope, acceptance, approvals |
| `work/p1-d-knowledge-maintenance.md` | Not applicable | P1-D unchanged and excluded; its active boundary is carried by canonical docs |
| `README.md` | Read | product pipeline and reference runtime |
| `docs/REQUIREMENTS.md` | Read | FR-002/015, QA-001/002/009/010 |
| `docs/ENGINEERING_BASELINE.md` | Read | UC-001, ADR-003/004/005 and realizer boundary |
| `docs/PLATFORM_STRATEGY.md` | Read | macOS evidence; no P1-F decision |
| `docs/TEST_STRATEGY.md` | Read | P1-E benchmark and regression set |
| `docs/TRACEABILITY.md` | Read | requirement mapping to update |
| `docs/ARCHITECTURE.md`, `docs/MARCO_PROTOCOL.md` | Read | frame authority, unknown contract, fallback order |
| `docs/AUTOMATIC_LEARNING.md` | Read | no Base KG or adaptive-state mutation |
| `docs/P1.md` | Read | completion checklist; mark only evidenced items |
| `pyproject.toml`, `pytest.ini`, MARCO CI workflow | Read | declared packages, test runner and integration steps |
| `scripts/build_marco_pack.py`, `src/marco_translator/marco_pack.py` | Read | actual upstream pack build/provenance |
| `realizer.py`, `models.py`, `pipeline.py`, `resolver.py`, `marco_adapter.py`, `knowledge.py` | Read | full grounded frame to output flow |
| `test_pipeline.py`, `test_marco_integration.py` | Read | current fallback, semantic regression fixtures |
| maintenance schemas/prompts | Not applicable | no maintenance or persistence contract change |
| OOP design | Not applicable | no new domain object, mutable state owner, or public polymorphic contract planned |
| external standards | Not applicable | no standards-compliance claim or standards-dependent design |
| Engineering reference set | Read | diagnosis, implementation, change control, delivery, artifacts, OOP, standard map, handoff, maintenance validation |

### Requirements, use case, and operation contract

- Primary actor: translation user; evaluator/researcher supplies a frozen grounded frame workload.
- Preconditions: workload identity and Semantic Frames are frozen; model/runtime/license identity and prompt are recorded; candidate receives target frame fields and constrained target terminology, never raw source text.
- Success: same workload yields a deterministic rule baseline and actual local model outputs with separate semantic, terminology, fluency, resource and invocation results.
- Failure: timeout/OOM/unsupported/error remains classified; ungrounded frame returns unresolved with no neural invocation; no KG/TM/Overlay/Session mutation or network inference occurs.
- Operation: `benchmark(workload, candidate, repetitions)` is read-only over product state and emits a versioned evidence report; candidate artifacts remain in the authorized temporary model cache.
- State/timing: corpus and oracle are canonical checked-in inputs; measurement result is an immutable run artifact; no automatic correction, state feedback, or event cycle applies.

### Confirmed findings and decisions

- `Translator.translate` runs exact session/TM, resolves a `SemanticFrame`, tries `RuleRealizer`, then invokes `NeuralRealizer` on any rule miss. Direct actual-MARCO reproduction passed an unresolved unknown frame to a fake realizer, which returned `추측 번역`; result path became `neural-realizer`. This violates FR-015 and the unresolved contract. Narrow shared-root fix: gate neural fallback on `not frame.unresolved`; preserve neural use for grounded rule misses.
- Current actual MARCO pack resolves five registered frames; each has a deterministic template. Seed has 10 entries. No separate training/fine-tuning corpus file exists in repository inventory. Dedicated 100–300M training is `Not justified yet`; do not train on five benchmark examples.
- Capability probe: macOS 26.6.2, Apple M5, arm64; Python 3.14.7 system runtime has no MLX/llama.cpp/PyTorch/pytest modules. Existing Ollama CLI 0.34.0 is reusable; no daemon was running. Existing user Ollama store contains only 9.6GB and 19GB models, so it is untouched.
- Authorized isolated setup: fresh `/tmp/marco-translator-p1e-venv-20260925` using bundled Python 3.12.14; `marco-translator` editable, `mco` editable from clean upstream MARCO `ffedc8b8552505e515b8f5ea2ae7f9934d7ef58e`, NumPy 2.5.3, Pillow 12.3.0, pytest 9.1.1. No global/system packages changed.
- Trial candidate (not product selection): public `qwen3:0.6b-q4_K_M`, Ollama manifest short ID `7df6b6e09427`, downloaded size 522MB into `/tmp/marco-translator-p1e-ollama-models-20260925`. Official Qwen card identifies Apache-2.0. Ollama runs on isolated loopback port 11435 with cloud features disabled. No existing model asset was overwritten.
- Actual MARCO build succeeded on the fresh pinned upstream checkout; `.mco` SHA-256 `3f38aa5f1237170dbb5cf5a9cdbe19ab3d309c973b2d581bdc6f28463adeb627`, 3,220 bytes. Baseline full suite against it: 49 passed, 0 skipped.
- Alternative comparison: reuse installed Ollama + temporary model cache was smaller and sufficient than installing MLX/another runtime; no runtime architecture claim follows. Keep candidate prompt based on target language, domain, intent/style, target `TermDecision`s and slots; omit source text and source-side lexical fields.
- Frozen benchmark oracle: every declared slot must appear, explicit contradiction markers must be absent, and exact `TermDecision.target` values are scored separately. Fluency uses an independent 1–5 rubric. The existing exact-term/slot conflict is reported without changing source semantics.

### Scope and acceptance map

| Item | Status at recovery | Direct evidence / planned validation |
|---|---|---|
| AC-E1 frozen workload and identity | Validated | actual MARCO-derived frames, pinned input/source hashes, two reports with identical workload/prompt/runner hashes and outputs |
| AC-E2 deterministic rule baseline | Validated | 50 repeated `RuleRealizer` calls/run; semantic 5/5 and medians 0.000333–0.000375 ms |
| AC-E3 sub-1B candidate on Mac | Validated | local Qwen3-0.6B Q4_K_M, exact manifest digest, Apple M5 execution |
| AC-E4 semantic preservation | Validated; candidate fails constraint | slot/contradiction/relation/unsupported-claim hard checks: rule 5/5, candidate 0/5 |
| AC-E5 terminology | Validated; fixture conflict retained | exact target check: rule and candidate 4/5; `FEED_ENEMY` target/slot mismatch recorded |
| AC-E6 fluency | Validated | independent 1–5 review, rule mean 4.6 and candidate mean 2.6 |
| AC-E7 performance/resources | Validated | two cold/warm reports, sampled process-tree RSS, exact artifact size |
| AC-E8 invocation rate | Validated | actual MARCO pipeline 0/5 grounded and 0/6 including unknown |
| AC-E9 offline inference | Validated | two runs under macOS network sandbox allowing loopback only; cloud disabled |
| AC-E10 P1-A–D regression | Validated | 62 passed/0 skipped normally and with all outbound networking denied; actual MARCO integration included |
| AC-E11 100–300M dedicated candidate | Not justified | five evaluated frames, ten seed entries, no training corpus, zero neural invocation |
| AC-E12 final candidate conclusion | Validated | ADR-006: Qwen3 held; rule path retained; no dedicated model justified |
| AC-E13 no P1-F/native choice | Validated | scope and final diff review; no runtime/core selection |

Interim next step superseded by the P1-E final closeout below.

### Final evidence — 2026-09-25

#### Frozen workload and candidate

- Workload: `benchmarks/p1-e/workload.v1.json`, five actual-MARCO grounded frames plus one unknown pipeline input. SHA-256 `4014f59dd1b31bd61a4b4b71ce51252cd5160213f1df5b8b733a71cef088f24e`.
- Provenance: Marco `ffedc8b8552505e515b8f5ea2ae7f9934d7ef58e`; `.mco` SHA-256 `3f38aa5f1237170dbb5cf5a9cdbe19ab3d309c973b2d581bdc6f28463adeb627`; frame map `573cf813df6d513a0536fba9819ae86284619ad24f1b4632d8887483c86699fa`; seed `3e21404f1cbbafeaba3fa515fbd51e8d2ca2fe272e221a14733a66140b5fff8a`.
- Candidate: `qwen3:0.6b-q4_K_M`, Ollama 0.34.0, exact manifest SHA-256 `7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435`, 751.63M parameters, Q4_K_M, 522,653,767 bytes, Apache-2.0. It ran from the isolated `/tmp/marco-translator-p1e-ollama-models-20260925` cache; the pre-existing user model store was not used or overwritten.
- Host: macOS 26.6.2, Apple M5, arm64, 34,359,738,368 bytes physical RAM, AC power, no thermal/performance warning.
- Setup: disposable `/tmp/marco-translator-p1e-venv-20260925`, bundled Python 3.12.14, local editable translator and pinned upstream MARCO, NumPy 2.5.3, Pillow 12.3.0, pytest 9.1.1. System/global packages unchanged.
- Prompt exposes only target language, domain, intent, style, preferred target terms and Semantic Frame slots. Source text, source terms and concept IDs are omitted. Per-case hashes are in both run reports.

#### Results

| Measure | Rule baseline | Qwen3 candidate |
|---|---:|---:|
| Semantic hard checks | 5/5 | 0/5 |
| Exact terminology | 4/5 | 4/5 |
| Warm median, 50 calls/run | 0.000333–0.000375 ms | 93.58–95.69 ms |
| Warm p90 | 0.000416–0.000500 ms | 144.33–146.18 ms |
| Warm observed maximum | 0.000625–0.000708 ms | 151.87–184.58 ms |
| Cold first call | No model load | 712.2–715.7 ms; load 577.4–578.3 ms |
| Sampled Ollama process-tree RSS peak | Not applicable | 953.2–955.2 MiB |
| Model artifact size | None | 522,653,767 bytes |
| Actual production neural invocation rate | 0/5 grounded | neural candidate path is not reached; actual pipeline 0/5 grounded and 0/6 including unknown |

- Both final reports used the same workload SHA, five prompt hashes, and runner SHA `8a901525441334a3aebfa905598977c154bc2e534d722186c2b56946900133a7`. Candidate and rule outputs were identical across both runs and all 10 measured repetitions per case.
- Raw report `benchmarks/p1-e/results/run-1.json`: SHA-256 `71be925e7fa75e967733dae5498e92fe1a6ca0f6f8ecc189c0f55769bdbb0ba5`.
- Raw report `benchmarks/p1-e/results/run-2.json`: SHA-256 `38800321ba29ef61a451f628d0d767ab355f6b087d1a35191be72eade08edfdd`.
- Fluency rubric: 1 unusable, 2 serious phrase issues, 3 understandable but awkward, 4 natural with minor awkwardness, 5 concise idiomatic gaming chat. Single-reviewer scores: rule `[5,5,4,5,4]`, mean 4.6; candidate `[3,4,3,2,1]`, mean 2.6. The scores do not compensate for semantic failures.
- The fifth frame's exact term target `킬 헌납` conflicts with its slot/canonical output `죽어주면`; this is why the rule baseline and candidate both score 4/5 on the separate exact-term check. No source knowledge was changed.
- Decision: do not select the candidate. The deterministic path covers all five grounded inputs, the candidate fails semantic hard constraints on all five cases and is materially slower/larger, and current neural invocation rate is zero. A 100–300M training run is not justified without a representative licensed corpus and a grounded neural fallback workload.

#### Offline and regression verification

- Benchmark runner SHA above. It verifies the existing model digest and never pulls assets, disables proxies, sets `OLLAMA_NO_CLOUD=1`, and self-relaunches under macOS `sandbox-exec`: all non-loopback inbound/outbound traffic is denied while localhost is permitted for the API and Ollama's internal runner.
- Final direct macOS inference: 2 runs × 50 warm requests plus 2 warmup rounds, both completed inside the network sandbox. Warm output stable across repetitions and runs.
- Focused regressions: 23 passed, covering unknown-frame no-guess behavior, grounded neural fallback, actual MARCO cases, prompt/source-field separation, strengthened semantic/term oracle, rule baseline and RSS sampling.
- Full suite with actual MARCO `.mco`: 62 passed, 0 skipped. Repeated under sandbox denying all outbound network: 62 passed, 0 skipped.
- `compileall` passed for `src`, `scripts`, and `tests`. JSON parser accepted the frozen workload and both reports.
- Direct fallback regression reproduced before the fix: unresolved actual-MARCO frame reached a fake neural realizer and returned `추측 번역`. Shared pipeline gate now blocks unresolved frames and retains neural fallback for grounded rule misses.

#### Failed-attempt classification

- Initial model identity comparison failed because Ollama's tags endpoint omits the `sha256:` display prefix; the runner now normalizes only that prefix and verifies the same full digest. No candidate inference was counted in that attempt.
- First sandboxed inference runner exited because Ollama's internal `llama-server` uses dynamic loopback ports. Sandbox validation showed `localhost:*` permits local runner communication while external IPs remain denied; both final offline runs passed.
- An early resource run reported zero RSS because sandbox policy rejected the setuid `ps` executable. That report is invalid and excluded. The runner now uses macOS `libproc`; child-count semantics and the real `ollama serve` / `llama-server` tree were directly verified. Both final runs sampled two-process peaks near 1 GiB.
- The first slot-only semantic oracle allowed some outputs with all slot strings but an inverted relation or unsupported claim. The workload now rejects explicit per-case examples of those errors, a parametrized regression covers them, and both final reports were freshly generated under the strengthened oracle. Final candidate semantic pass is 0/5; earlier 3/5 reports were superseded.
- No final acceptance validation failed, was skipped, timed out, or hit OOM.

#### Final scope and delivery state

- Canonical docs updated: `AGENT_GUIDE.md`, `docs/ENGINEERING_BASELINE.md` ADR-006, `docs/TEST_STRATEGY.md`, `docs/TRACEABILITY.md`, `docs/P1.md`, this Engineering Record.
- Product change is limited to the unresolved-frame neural gate plus direct regression tests. Benchmark fixture, runner, and two raw evidence reports are included. P1-D schemas/assets/contracts and P1-F architecture remain untouched.
- Graphify inline traversal was used before source changes. `graphify update .` succeeded after the final code update (677 nodes, 1,381 edges, 36 communities). It warned that six data-only JSON inputs, including the benchmark workload/results and KG source files, produced no graph nodes; direct source/hash checks cover them. Generated `graphify-out/` remains untracked and excluded from delivery.
- Remaining limitation: five-frame semantic oracle and single-rater fluency scores do not prove broad quality; RSS is sampled at 100 ms and may count shared pages more than once. The exact term/slot conflict is documented.
- Next scope: P1-F may start only after it becomes the explicit active scope in this file. Preserve offline-first behavior, grounded semantic authority, unknown-input safety and portable contracts; do not inherit Qwen3 or runtime selection as a P1-E decision.
