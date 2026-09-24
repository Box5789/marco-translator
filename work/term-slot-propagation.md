# 사용자 용어의 문장 슬롯 반영 — 제한 수정

## 현재 작업과 권한

- 브랜치: `fix/term-slot-propagation-20260924`
- 기준: `a56a52c731a54098d2bb089a74d776e753ec8f8e`
- 사용자 승인: 알려진 문장의 사용자 용어 반영/해제 경로를 먼저 구현한다.
- 이 분기에서는 본 문서의 제한 수정만 수행한다. 기존 `work/current.md`의 P1-D는 별도 개발 브랜치의 작업으로 보존하며 재개하지 않는다.
- main/기존 브랜치/전역 스킬/운영 DB는 변경하지 않는다. 병합·전역 설치는 승인 범위에 포함하지 않는다.

## 근거와 결정

기존 지식 저장소는 범위와 우선순위에 맞는 TermDecision을 반환하지만,
두 resolver는 authored slots를 그대로 반환하고 RuleRealizer는 slots만
렌더링한다. 실제 SQLite Overlay부터 Translator까지 연결한 신규 16개
시험을 원본에 실행해 10 FAIL / 6 PASS, pytest exit 1로 재현했다.

수정은 source expression과 slot의 명시적 연결로 제한했다.
`docs/TERM_SLOT_BINDING.md`가 이 분기의 추가 계약 설명이다.
유효한 결과를 사용자에게 전달할 책임은 기존 resolver/realizer 분리를
유지한다. 새 언어 런타임/프레임워크/DB/불필요한 문자열 후처리를 만들지 않는다.

## 변경과 보존

- 공통 `bind_term_slots`를 기존 knowledge 모듈에 추가.
- Pattern과 MARCO frame map의 optional `slot_terms`를 두 resolver에 연결.
- 최초 등록: `西边有狙`의 `entity <- 狙`만. 기존 기본 문장 유지.
- SemanticFrame, TranslationResult, TM/Overlay/Session DB, 우선순위, 실현기,
  neural 경계, MARCO 상태/가중치 정책, Base KG 그래프는 변경하지 않는다.
- 기존 CI에 새 분기와 신규 unit/component 파일을 연결하고 실제 MARCO
  integration 파일에는 용어 설정/해제/TM 보존 사례 하나만 추가.

## 실행한 검증

ChatGPT 작업 컨테이너에서 connector로 가져온 파일을 Git blob SHA로 확인한
격리 소스 사본을 사용했다. 전체 git clone은 DNS 오류로 불가능했고,
실행에 필요한 runtime·data·관련 test만 복사했다. 운영 파일은 공유하지 않았다.
패키지 설치나 사용자 Mac/앱/DB 접근은 하지 않았다.

- 최초 사용자 흐름: 원본 10 FAIL / 6 PASS; 수정 후 동일 16/16 PASS.
- 최종: 기존 pipeline/adapter/overlay 19개 + 신규 25개 = 44 PASS.
- 실제 MARCO 7개: 로컬 `mco`/model 없음으로 SKIP. 성공으로 계산하지 않음.
- 최종 명령:
  `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_pipeline.py tests/test_marco_adapter.py tests/test_user_overlay.py tests/test_term_propagation.py tests/test_marco_integration.py`
- 기존 maintenance 시험은 로컬 소스 사본에 포함하지 않아 실행하지 않았다.
  변경하지 않은 기존 CI 명령에는 계속 포함돼 있다.
- 실제 MARCO/macos 결과는 위 로컬 결과에 포함하지 않는다. 새 commit의
  Actions 결과를 별도로 확인해야 한다. 함수 시험은 엔진 의미 정확도 평가가 아니다.

## 인계와 종료 조건

남은 확인은 이 commit의 기존 CI(실제 MARCO) 및 필요한 macOS Python
회귀다. CI 실패 시 upstream/model 식별자와 실패 원인을 먼저 분리한다.
같은 조건에서 통과한 검사만 이유 없이 반복하지 않고, 검사 의미를 약화해
통과시키지 않는다. 준비된 runtime이 없으면 설치/배포를 확대하지 말고
구체적인 미실행 조건만 남긴다.

이 수정의 검증/최소 보완 뒤 종료한다. P1-D·neural realizer·스킬/R2·MARCO
범용 기억 시스템은 별도 지시 전 진행하지 않는다.
