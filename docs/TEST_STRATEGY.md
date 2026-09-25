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

P1-E에서 고정 workload로 아래 항목을 측정했다. Product latency/RAM budget은 아직 확정하지 않았다.
- latency
- peak RAM
- model size
- neural invocation rate

P1-E 직접 측정은 아래 결과를 따른다. 후속 제품 budget 측정은 **Measurement Needed** 상태다.


## P1-E benchmark validation

P1-E는 macOS에서 Tiny Neural Realizer 후보를 **동일한 frozen workload**로 비교한다. 모델이나 runtime을 먼저 정하고 테스트를 맞추지 않는다.

Required evidence:

- benchmark corpus/version identity와 재현 가능한 input fixture
- deterministic rule-only baseline
- 최소 1개 sub-1B off-the-shelf local realizer 후보의 실제 macOS 실행
- 100–300M distilled/fine-tuned 후보는 데이터·compute·품질 근거가 충분할 때만 수행
- semantic preservation과 terminology compliance를 hard constraint로 별도 기록
- fluency는 semantic correctness와 분리된 rubric으로 기록
- 동일 workload에서 cold/warm latency, 반복 latency 분포, peak RAM, model-on-disk size
- 실제 pipeline에서 neural invocation rate 또는 동일 기준의 재현 가능한 계산
- local assets가 준비된 뒤 network-disabled inference
- P1-A~P1-D 전체 regression 유지

새 model/runtime dependency나 model asset이 필요하면 먼저 기존 capability를 probe한다. P1-E에서는 project-local 또는 temporary isolated environment의 package 설치와 공개 benchmark model/runtime asset 다운로드가 사전 승인되어 있다. system package manager/global Python/OS 설정 변경, 인증·비용이 필요한 asset, 기존 persistent 환경 덮어쓰기, 단일 4 GiB 초과 또는 총 신규 8 GiB 초과 다운로드는 별도 승인을 요구한다. 모든 외부 asset의 source/version/license/size를 기록한다.

구체적인 product latency/RAM threshold는 실측 전 임의로 확정하지 않는다. benchmark 결과와 플랫폼 요구를 근거로 후속 ADR에서 결정한다.

### P1-E completed measurement

- Frozen workload: five actual MARCO-derived grounded gaming frames; one unknown-input pipeline invocation case. Workload SHA-256: `4014f59dd1b31bd61a4b4b71ce51252cd5160213f1df5b8b733a71cef088f24e`.
- Candidate: `qwen3:0.6b-q4_K_M`, Ollama 0.34.0, manifest SHA-256 `7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435`, 751.63M parameters, Q4_K_M, 522,653,767 bytes. Model metadata reports Apache-2.0; see `docs/ENGINEERING_BASELINE.md` ADR-006 for official source links.
- Host: macOS 26.6.2, Apple M5, arm64, 32 GiB, AC power, no thermal/performance warning.
- Procedure: verify the existing isolated model cache and exact digest; never pull from the runner. Two warmup rounds, then 10 repetitions × five cases, repeated as two runs. Cold latency is the first case after explicit unload. Rule latency measures `RuleRealizer.realize` on the identical verified in-memory frames; candidate latency includes local HTTP/API and inference. RSS is sampled every 100 ms from the Ollama server and its `llama-server` descendants using macOS `libproc`.
- Offline boundary: each server and benchmark client run under `sandbox-exec`, which denies all inbound/outbound networking except loopback. The server receives `OLLAMA_NO_CLOUD=1`; proxies are removed. Both final runs completed under this boundary.
- Immutable raw reports: `benchmarks/p1-e/results/run-1.json` and `benchmarks/p1-e/results/run-2.json`. Runner SHA-256 is `8a901525441334a3aebfa905598977c154bc2e534d722186c2b56946900133a7`; both runs have the same workload, prompts, runner, and all repeated outputs.

| Measure | Rule baseline | Qwen3 candidate |
|---|---:|---:|
| Semantic oracle | 5/5 | 0/5 |
| Exact terminology oracle | 4/5 | 4/5 |
| Warm realization median | 0.000333–0.000375 ms | 93.58–95.69 ms |
| Warm latency p90 | 0.000416–0.000500 ms | 144.33–146.18 ms |
| Warm observed maximum | 0.000625–0.000708 ms | 151.87–184.58 ms |
| Cold first call | No model load | 712.2–715.7 ms total; model load 577.4–578.3 ms |
| Peak process-tree RSS | Not applicable | 953.2–955.2 MiB |
| Model artifact | None | 522,653,767 bytes |
| Actual neural invocation rate | 0/5 grounded inputs | Product path: 0/5 grounded, 0/6 including unknown |

The semantic oracle requires every declared slot and rejects explicit contradictions, relation reversals, and unsupported-claim fragments. A regression proves that slot-complete outputs still fail when they invert or invent a claim. The terminology oracle checks exact `TermDecision.target` separately from slot semantics. On the final frame, the target `킬 헌납` conflicts with the frame slot and canonical rule output `죽어주면`; therefore both rule and candidate score 4/5. That pre-existing contract conflict remains visible in the report.

Fluency rubric (1–5): 1 unusable; 2 serious phrasing issues; 3 understandable but noticeably awkward; 4 natural with minor awkwardness; 5 concise and idiomatic gaming chat. One Codex review scored fluency separately from semantic/term correctness; this is a single-rater estimate, not a native-speaker panel.

| Case | Rule output (score) | Candidate output (score) |
|---|---|---|
| west sniper | `서쪽에 저격수 있음` (5) | `저격수 서쪽에 위치하며, 게임을 진행할 수 있는 공간입니다.` (3) |
| base enemy | `본진에 적 있음` (5) | `본진이 적을 방어하고 있다.` (4) |
| church materials | `교회에 건축 자재가 필요함` (4) | `"건축 자재를 활용한 교회 건축 작업을 진행 중입니다."` (3) |
| group push | `뭉쳐서 한 번에 밀자` (5) | `"망치던 게임을 한 번에 밀자"` (2) |
| stop feeding | `한 명씩 가서 죽어주면 답이 없어` (4) | `코스닥 쇼트를 했을 때, 한 명씩 가서 헌납할 수 없다.` (1) |

Mean fluency: rule 4.6/5; candidate 2.6/5. Candidate outputs were stable within and across runs, but it failed semantic hard constraints on all five cases and was not selected. Fine-tuning/distillation at 100–300M was not justified: the repository has no dedicated training corpus, only five evaluated frames, ten seed entries, and no current neural invocation.
