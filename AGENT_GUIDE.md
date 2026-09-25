# AGENT_GUIDE.md

## 제품 정의

Marco Translator는 MARCO 기반의 deterministic semantic reasoning과 작은 local realizer를 결합하는 **offline-first 범용 번역 엔진**이다.

첫 검증 corpus는 중국어 → 한국어 게임 채팅이지만 제품의 의미 구조와 public contract는 특정 게임이나 언어쌍에 종속되지 않아야 한다.

## 최종 플랫폼

제품 지원 목표:
- macOS
- Windows
- Android
- iOS

현재 개발과 직접 검증의 우선 환경은 **macOS**다.

macOS에서 먼저 성공시키되 다음을 macOS에 묶지 않는다.
- Semantic Frame
- Translation Memory contract
- Base KG / User Overlay / Session State semantics
- maintenance package / patch contract
- log/evidence identity
- model realizer interface
- versioning / rollback semantics

플랫폼별로 달라질 가능성이 높은 영역은 adapter로 취급한다.
- screen capture
- OCR
- overlay/window presentation
- model acceleration/runtime
- app lifecycle / permissions
- filesystem integration

## 런타임 책임

기본 경로:

```text
Input
→ Normalizer
→ Translation Memory
→ MARCO Semantic Resolver
→ Semantic Frame
→ Rule Realizer
→ Tiny Neural Realizer (필요할 때만)
→ Output
→ Translation Log
```

의미 결정 authority는 Semantic Resolver까지다.

Tiny Neural Realizer는:
- 이미 결정된 Semantic Frame을 자연스럽게 표현한다.
- source meaning을 재해석하지 않는다.
- KG에 새 지식을 쓰지 않는다.
- 존재하지 않는 concept/sense를 만들지 않는다.
- Semantic Frame과 충돌하는 표현을 선택하지 않는다.

## 지식 계층

### Base KG
- 검증된 공용 semantic knowledge.
- runtime read-only.
- 구조 변경은 maintenance patch + validation + 사용자 승인 후 새 version으로만 가능.

### User Overlay
- 사용자별 용어와 승인된 개인 지식.
- Base KG와 분리.
- reversible.
- 다른 사용자나 global KG에 영향을 주지 않는다.

### Translation Memory
- exact match를 우선 사용.
- 사용자의 명시적 번역 수정은 즉시 TM에 저장 가능.

### Session State
- 현재 session에만 필요한 entity/context.
- 임시 상태이며 폐기 가능.

우선순위와 세부 정책은 `docs/ARCHITECTURE.md`, `docs/AUTOMATIC_LEARNING.md`를 따른다.

## Maintenance Plane

Runtime과 maintenance를 분리한다.

```text
runtime logs
→ 사용자 명시 export
→ 외부 LLM 분석
→ schema-valid patch proposal
→ local validation
→ dry run / corpus replay
→ user approval
→ new KG version
→ rollback 가능
```

외부 LLM provider는 교체 가능해야 한다. runtime에 cloud provider dependency를 넣지 않는다.

자동 외부 업로드는 금지한다.

## 현재 확정하지 않은 결정

다음은 아직 architecture decision이 아니다.

- shared native core 언어
- Rust/C/C++/Swift/Kotlin/C# 등 구체적 구현 조합
- Tiny Realizer의 최종 모델
- model execution backend
- macOS/Windows/Android/iOS UI framework
- OCR engine
- screen capture / overlay 구현 세부

이 결정은 해당 단계에서 현재 source, 플랫폼 capability probe, 성능 측정, 배포/FFI 비용, 실제 acceptance criteria를 근거로 ADR을 작성한 뒤 선택한다.

## 현재 단계

P1-A부터 P1-E까지 구현·검증 기준이 완료됐다. P1-E 후보 결정과 남은 품질 한계는 `docs/ENGINEERING_BASELINE.md` ADR-006과 `work/current.md`에 기록한다.

현재 활성 작업은 `work/current.md`만으로 판단한다. P1-F는 다음 계획 단계지만, 명시적으로 활성 scope가 되기 전에는 시작하지 않는다.

P1의 다음 계획 단계:
- P1-F: Cross-platform Runtime Gate

P1-F는 과거의 "mobile feasibility"가 아니라 macOS / Windows / Android / iOS 공통 runtime contract와 porting feasibility를 검증하는 단계다.

## 문서 경계

- 이 파일은 장기 제품 원칙만 보관한다.
- task 진행률, commit SHA, 임시 가설은 `work/current.md`에 둔다.
- 세부 기능 요구사항은 `docs/REQUIREMENTS.md`에 둔다.
- 이미 승인된 semantic/runtime 상세는 기존 architecture 문서에 둔다.
