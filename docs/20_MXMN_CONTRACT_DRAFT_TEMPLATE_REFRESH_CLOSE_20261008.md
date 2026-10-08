# 계약서 DRAFT 최신 문구 반영 검증 마감

## 기준

- GitHub mixbiz1/MixNMenu main `eb5df6f` (작업 시작 fetch 결과 동일).
- 별도 clean worktree에서 시작. 이전 patch/작업트리 변경사항 혼합 없음.
- 대상 업무: `FC-00001-261006-00001-IM-0001`, 문서 ID 1 / DRAFT / Version 1.
- 실제 DEV/SERVER DB 및 실행 중인 SERVER에는 접근하지 않았다. 아래 ID 1 검증은 실제 API/ORM/GUI/PDF 경로를 사용한 격리 SQLite 업무 재현이며 운영 문서를 변경한 결과가 아니다.

## 확인된 원인과 경로

`eb5df6f`의 수입대행·BL 기본·국내매입 3종 템플릿에는 다음 승인 문구가 정확히 반영되어 있다.

> “고객사”는 물품 출고 시, “판매사”에게 사전에 출고요청을 신청하고, 예상 판매대금을 “판매사”가 지정하는 계좌로 입금 완료한 후 출고하기로 한다.

BL 세무사용/관세사용 2종은 제3조를 포함하지 않는 별도 제출 양식이며 입금 조항을 임의 추가하지 않는다. 관세사용의 금액 제외 정책도 유지한다.

1. 자동초안 생성: 현재 계약/Master/LOT 정보를 source Snapshot에 저장하고 `render()`로 생성한 HTML을 DB body에 저장.
2. 조회: DB에 저장된 body와 source Snapshot을 반환. 최신 템플릿으로 자동 재계산하지 않는다.
3. GUI 표시: 조회한 body를 QTextEdit에 표시한다.
4. 표준양식 다시 작성: DRAFT에서만 기존 source Snapshot을 사용하여 **서버의 최신 템플릿 파일**을 읽고 body를 다시 생성한다. ID/version/status는 유지하고 UPDATE Audit before/after/reason을 기록한다. 수동 편집 문구는 재작성되므로 버튼 안내에 명시한다.
5. 문구 저장: GUI 편집 HTML을 DB body에 저장한다. 최신 템플릿으로 다시 생성하는 작업과는 별개이다.
6. PDF: 문서를 다시 GET하여 저장된 body를 출력한다. CONFIRMED에서는 snapshot.body를 사용한다. 출력만으로 문서를 업데이트하지 않는다.

따라서 **템플릿 수정·GitHub push·서버 재시작·PDF 다시 저장만으로 기존 DRAFT 본문은 바뀌지 않는다.** 옛 문구가 저장된 DRAFT를 조회/출력하면 옛 문구가 보이는 현상을 실제 코드로 재현했다. 명시적 재작성 후 GUI와 PDF 모두 최신 문구로 바뀌었다.

HTML 템플릿은 재작성할 때 read_text로 읽는다. 올바른 서버 파일이 수정돼 있다면 HTML 템플릿 자체를 읽기 위한 재시작은 필수 조건이 아니다. Python revision/GUI 변경은 실행 중인 API/GUI의 소스 갱신 및 재시작이 필요하다.

**실제 SERVER 동기화/실행 경로는 미검증**이다. 명시적 재작성 후에도 옛 문구가 반환된다면 API가 실행 중인 서버의 파일/경로 또는 호출 대상이 다른지 구분해야 한다. Work에서 이 운영 상태를 확인했다고 주장하지 않는다. DEV 로컬 파일 변경과 원격 API 서버의 실제 템플릿 변경은 서로 다른 사항이다.

## 최소 변경

- `contract_document_templates.py`: 승인 문구 변경을 구분하도록 revision을 `20261008.v1.seller-account`로 갱신. 템플릿 5종의 조항은 추가 변경하지 않음.
- `views/financing_intake.py`: 이전 revision의 DRAFT 조회 시 `표준양식 다시 작성`으로 최신 문구를 적용하라는 안내 및 기존 편집 문구 재작성 안내. 조회 시 자동 수정하지 않음. CONFIRMED에는 이 재작성 안내를 적용하지 않음.
- `tests/test_contract_template_refresh.py`: 신규 9개 회귀 사례.
- `tests/test_batch2a_contract_import_cost.py`: 생성되는 새 revision 검증 기대값 갱신.
- 이 문서.

API 재작성/조회/저장/확정, 출력기, DB 구조, 계약조건/LOT/원가 계산을 재설계하지 않았다. 원본 조건의 미확정값을 추정하거나 채우지 않는다.

## 검증

- 필요 라이브러리를 신규 venv에 requirements.txt 기준 설치. pip check: No broken requirements found.
- clean eb5df6f baseline: **318 passed, 1 warning**.
- 관련 선택: **169 passed, 1 warning**.
- 전체 pytest: **327 passed, 1 warning**.
- warning은 기존 Starlette/httpx deprecation.
- Python compile / UTF-8 / git diff --check: 통과.

신규 회귀의 검증 내용:

- 5양식의 승인 문구/제출양식 고유 정책.
- 해당 계약번호 및 ID 1 / DRAFT / Version 1로 3종 업무를 각각 재현.
- 옛 본문 조회·PDF 저장만으로 DB body/source Snapshot/Audit이 변경되지 않는지 확인.
- GUI의 명시적 재작성 후 최신 본문 표시, 이전 revision 안내 해제.
- 재작성 전 source 값은 그대로이며 revision만 갱신. ID/version/status 유지 및 UPDATE Audit 정확성.
- 실제 GUI PDF 저장 동작에서 GET한 본문 사용 및 승인된 판매사 계좌 문구 추출.
- 문구 저장 후에도 새 문구 유지.
- CONFIRMED 문구 저장/재작성 차단 및 실패 시 Snapshot/Audit 불변.
- 옛 문구로 확정된 과거 문서의 조회/출력은 옛 확정 Snapshot 그대로 유지.

3종 DRAFT PDF를 추가 생성하여 각각 A4 세로 1페이지, 전체 조항/상품표/서명 보존, 판매사 계좌 문구를 텍스트 추출 및 PNG 렌더링으로 확인했다. 기존 5종 A4/최소 8.5pt/수용한계 및 Snapshot 회귀도 전체 suite에서 통과했다. PDF는 QPdfWriter를 유지하며 native QPrinter discovery를 사용하지 않았다.

## 운영 마감 상태

Work 코드·자동검증은 완료. 사용자 지시에 따라 변경사항 commit/push를 진행하며 최종 commit hash와 push 결과는 최종 보고에 기록한다. 실제 서버 배포/DB Migration/운영 ID 1 재작성은 수행하지 않았다.

운영 반영 후 기존 ID 1을 열어 **표준양식 다시 작성 → GUI 본문 확인 → PDF 저장**으로 진행한다. 재작성 직후 상태는 DRAFT / Version 1이어야 한다. 확정본/과거 Snapshot은 자동 교체하지 않는다. 반복 수동 patch 적용은 필요 없으며 Git으로 동기화한다.
