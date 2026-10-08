# 계약서 DRAFT PDF / 인쇄 수정

- 기준: GitHub main `f89e7e7` (작업 시작 시 최신 HEAD 일치 확인).
- 범위: 계약서 출력 정책만 변경. DB Schema/Migration, 계약조건, LOT 업무 로직 변경 없음.

## 출력 정책

DRAFT는 PDF 저장 및 인쇄가 가능하며 출력물에만 `초안 / 검토용`을 표시한다. CONFIRMED에는 자동 초안 표시를 넣지 않는다. 기존 CANCELLED 출력은 취소 표시를 포함하여 허용하는 정책이므로 그대로 유지한다. SUPERSEDED 표시도 유지한다.

원문 및 확정 Snapshot에 표시를 저장하지 않는다. 문서 ID, status, version, body, snapshot, Audit은 출력 전후 동일하다. 기존 CONFIRMED 수정금지 규칙은 유지한다. GUI의 미저장 수정은 자동 저장하지 않으므로 수정 내용을 출력하려면 먼저 문구 저장을 실행해야 한다.

서버에는 별도 PDF/인쇄 API가 없다. 기존 문서 GET의 메뉴 조회권한 및 회사격리를 재사용한다. GUI PDF/인쇄는 저장된 문서를 GET으로 조회하며 상태 변경 API를 호출하지 않는다.

## 구현

- `financing_document.py`: DRAFT 출력 제한 해제, 출력 HTML에만 초안 표시. Qt 편집기의 속성이 있는 body 태그도 지원.
- `views/financing_intake.py`: DRAFT 인쇄 제한 해제.
- `tests/test_contract_draft_output.py`: 23개 회귀 사례 추가.

5종 양식에 동일 정책을 적용하며 QPdfWriter, A4 세로 단면, 최소 8.5pt, 내용 보존 및 수용 한계 오류 정책은 변경하지 않는다. native printer discovery는 PDF 저장에서 사용하지 않는다.

## 검증 결과

- 관련 선택 테스트: 125 passed, 1 warning.
- 전체 pytest: 283 passed, 1 warning (기존 Starlette/httpx deprecation).
- Python compile 및 git diff --check: 통과.
- clean f89e7e7 기준 patch git apply --check: 통과.
- 5종 실제 DRAFT PDF: 각각 A4 세로 1페이지, 초안 표시, 한글 본문/조항/품목표/서명란 추출 및 렌더링 확인.
- BL 세무사용 금액 표시 및 관세사용 금액 미표시 유지.
- PDF와 공유 인쇄 renderer의 텍스트 일치 확인. 출력 전후 DB 및 Snapshot/Audit 불변 확인.
- 과도한 내용의 DRAFT 출력 실패 시 DB와 기존 PDF 보존 확인.

Work 검증은 Linux offscreen Qt 및 설치된 Nanum 폰트로 수행했다. 실제 Windows 물리 프린터 인쇄는 DEV 확인이 필요하다.

## DEV 최소 확인

1. 기존 ID 1 / Version 1 / DRAFT를 열어 PDF 저장과 인쇄를 실행한다.
2. 초안 표시와 모든 내용이 1페이지에 보이며 출력 후에도 DRAFT / Version 1인지 확인한다.
3. CONFIRMED 문서는 초안 표시 없이 출력되고 편집 제한이 유지되는지 확인한다.

실제 DB Migration, commit/push, SERVER 변경은 수행하지 않았다.
