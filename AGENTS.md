# AGENTS.md

## 적용 규율

이 저장소의 모든 소프트웨어 작업은 `$apply-software-engineering-discipline`의 전체 workflow를 따른다.

기준 저장소:
- https://github.com/Box5789/software-engineering-discipline
- 이 baseline을 만들 때 확인한 기준 commit: `6f69339c7427fd5255bf5a0896413ea5e6c567d3`

스킬이 설치되어 있으면 반드시 먼저 적용한다. 스킬이 없거나 읽을 수 없으면 임의로 대체 규칙을 만들지 말고 그 상태를 명시한다.

기본 흐름:

```text
Requirements
→ Use Case / User Goal
→ Domain Model / SSD / Operation Contract
→ Architecture / Object Design
→ Code
→ Verification / Validation
→ Release Readiness
```

작업이 작아 보여도 단계를 축소하지 않는다. 적용되지 않는 항목은 생략하지 말고 `Not applicable`과 이유를 기록한다.

## 문서 선행

소스 코드, 설계 선택, 파일 수정 전에 다음 순서로 현재 상태를 복원한다.

1. `AGENT_GUIDE.md`
2. `work/current.md` 및 관련 `work/*.md`
3. `README.md`
4. 현재 작업과 관련된 `docs/`
5. 관련 schema / public contract / test
6. 필요하면 source

`graphify-out/graph.json`이 있으면 navigation evidence로 먼저 사용하되 canonical 문서나 직접 source/test evidence를 대체하지 않는다. 없으면 `Absent`, 사용할 수 없으면 `Unverified`로 기록한다. Graphify 설치나 새 의존성 설치가 필요하면 사용자 승인 없이 설치하지 않는다.

변경할 파일은 전체 내용을 먼저 읽는다.

## Source of truth

장기 제품 원칙:
- `AGENT_GUIDE.md`

현재 작업 범위와 stop condition:
- `work/current.md`

기능/품질 요구사항:
- `docs/REQUIREMENTS.md`

현재 분석·설계 기준선:
- `docs/ENGINEERING_BASELINE.md`

플랫폼 전략:
- `docs/PLATFORM_STRATEGY.md`

검증 전략:
- `docs/TEST_STRATEGY.md`

요구사항 추적:
- `docs/TRACEABILITY.md`

구현 세부 원칙:
- `docs/ARCHITECTURE.md`
- `docs/AUTOMATIC_LEARNING.md`
- `docs/MARCO_PROTOCOL.md`

문서가 충돌하면 추측하지 말고 authority와 최신 근거를 확인한 뒤 필요한 결정을 요청한다.

## 작업 범위 규칙

- `work/current.md`에 정의된 현재 scope만 full-scope로 완료한다.
- acceptance criteria를 통과한 뒤 다음 backlog 항목을 자동으로 시작하지 않는다.
- public contract, persistent-data semantics, 보안 경계, 플랫폼 계약을 바꾸는 것은 material pivot이다.
- material pivot에 필요한 근거가 없으면 구현하지 않는다.
- 질문·상태 확인·호환되는 정정은 현재 작업의 steering으로 처리한다.

## 프로젝트 고정 원칙

- Runtime은 offline-first다.
- Base KG는 runtime read-only다.
- User Overlay, Translation Memory, Session State와 Base KG의 책임을 섞지 않는다.
- Tiny Neural Realizer는 의미를 결정하지 않는다.
- 외부 LLM은 maintenance proposal을 만들 뿐 runtime semantic authority가 아니다.
- 로그나 지식은 자동으로 클라우드에 전송하지 않는다.
- invalid/corrupt input은 fail-safe하게 처리한다.
- rollback, data compatibility, trust-boundary validation을 단순화를 이유로 제거하지 않는다.

## 플랫폼

최종 지원 목표:
- macOS
- Windows
- Android
- iOS

현재 직접 검증 우선 플랫폼:
- macOS

macOS 우선 검증은 macOS 전용 core 설계를 의미하지 않는다. 공통 contract는 처음부터 네 플랫폼을 고려한다.

공통 native core 구현 언어, Tiny Realizer runtime, OCR/capture/overlay 구현 방식은 아직 확정되지 않았다. 근거와 acceptance evidence 없이 Rust/C++/Swift 등 특정 기술을 확정하지 않는다.

## 검증 및 전달

- focused test, full regression, actual MARCO integration, direct-host/macOS check를 구분해서 기록한다.
- failed/skipped/timed-out check는 원인과 영향을 분류하기 전 완료 처리하지 않는다.
- GUI/host 작업은 실제 host 검증이 가능하면 batch test로 대체하지 않는다.
- P1 단계에서 Python 구현은 reference implementation이다. 플랫폼 구현이 생겨도 stable contract를 먼저 유지한다.

커밋 전:
- 변경 파일과 diff를 확인한다.
- 가능한 환경에서는 `git diff --check`를 실행한다.
- 필수 validation을 완료한다.
- generated artifact와 canonical source를 구분한다.

커밋 제목과 본문은 한국어로 작성한다. `feat:`, `fix:`, `chore:` 같은 영어 Conventional Commit prefix를 사용하지 않는다.

현재 작업의 진행 상태, validation, residual risk, next step은 `work/current.md`에 갱신한다.
