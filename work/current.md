# Current Task — P1-E Tiny Realizer Benchmark

Status: Active — benchmark planning and capability verification  
Branch: `p1/tiny-realizer-benchmark`  
Parent baseline: `p1/engineering-baseline-macos@72a8e98fc39bbe33e13910005188020050ace302`

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
- P1-E: Active
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
| AC-E1 | benchmark workload와 fixture identity가 고정되고 재현 가능하다 | versioned corpus/manifest + repeat run | Pending |
| AC-E2 | rule-only baseline이 동일 workload로 측정된다 | benchmark report | Pending |
| AC-E3 | 최소 1개 sub-1B local candidate가 실제 Mac에서 실행된다 | direct macOS inference record | Pending |
| AC-E4 | semantic preservation이 독립 metric/oracle로 측정된다 | hard-constraint evaluation | Pending |
| AC-E5 | terminology compliance가 독립적으로 측정된다 | required-term assertions/report | Pending |
| AC-E6 | fluency가 semantic correctness와 분리된 rubric으로 기록된다 | scored sample/report | Pending |
| AC-E7 | 동일 workload에서 latency/RAM/model size가 측정된다 | reproducible benchmark output | Pending |
| AC-E8 | neural invocation rate가 실제 pipeline 또는 재현 가능한 기준으로 계산된다 | invocation report | Pending |
| AC-E9 | local assets 준비 후 inference가 network-disabled 상태에서 실행된다 | offline run | Pending |
| AC-E10 | P1-A~P1-D regression이 유지된다 | full regression + actual MARCO integration | Pending |
| AC-E11 | 100–300M candidate의 수행/보류가 데이터·compute·품질 evidence로 정당화된다 | decision record | Pending |
| AC-E12 | 최종 benchmark conclusion이 특정 후보 채택/보류/전용 realizer 필요 중 하나로 evidence와 함께 정리된다 | ADR/Engineering Record | Pending |
| AC-E13 | P1-F/native-core 기술 선택을 선행하지 않는다 | scope/review | Pending |

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

- 현재 Mac의 실제 inference capability와 설치된 runtime은 아직 재-probe하지 않았다.
- model 후보와 라이선스/배포 조건은 아직 검증되지 않았다. 공개 benchmark asset 다운로드는 위 한도 내 사전 승인되었지만 license/source 기록은 필수다.
- semantic-preservation 자동 oracle이 어느 범위까지 충분한지 아직 확정되지 않았다.
- 100–300M 전용 모델을 학습할 만큼 corpus가 충분한지 아직 검증되지 않았다.

## Next step

documentation preflight 후 현재 `NeuralRealizer` contract와 Mac capability를 조사한다. 필요한 project-local isolated package와 공개 benchmark model/runtime asset은 위 사전 승인 범위에서 설치·다운로드하고, 별도 승인 경계에 해당하는 작업만 사용자에게 질문한다.
