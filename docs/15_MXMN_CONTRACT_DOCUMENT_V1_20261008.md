# Batch 2A 계약서 자동생성 V1 — 2026-10-08

## 기준 및 범위

- Repository: mixbiz1/MixNMenu, main / bc0e5c4 (`fix: align financing contract SQL Server bit filters`). 작업 시작 fetch 결과 origin/main도 동일했다.
- 기존 계약서 API, 회사/메뉴 권한, 문서 PK, 계약 PK, 전역 version, 상태, Audit 및 QPdfWriter를 재사용한다.
- 모델/DB Schema/Migration 변경 없음. 실제 DB Migration, commit/push, SERVER 변경 없음.
- 기존 계약/조건 계산, 매입/매출, 입금/지급, LOT 재고, 원장, 실제 원가/배부 계산은 변경하지 않는다.

## 표준 원본과 양식

사용자가 제공한 스캔 PDF 다섯 파일의 실제 페이지를 확인해 조항, 상품 표, 당사자 및 서명란을 HTML 템플릿으로 전사했다. 국내매입 PDF의 두 페이지는 동일 양식의 반복이다. 예시 거래처/금액/날짜/은행계좌/실제 날인은 신규 계약에 복제하지 않는다.

| 계약유형 | 출력양식 / template_type | 원본 |
| --- | --- | --- |
| IMPORT_AGENCY | 수입대행 / IMPORT_AGENCY | 수입개별계약서(수입대행)(BUD0106141) |
| BL_TRANSFER | 기본 / BL_TRANSFER | (신)건별수입계약서_루돌프 장족(BL#2605-0944-VM) |
| BL_TRANSFER | 세무사 / BL_TRANSFER_TAX | (신)BL양수도계약서(세무사용)_루돌프 장족 |
| BL_TRANSFER | 관세사 / BL_TRANSFER_CUSTOMS | (신)BL양수도계약서(관세사용)_루돌프 장족 |
| DOMESTIC_PURCHASE | 국내매입 / DOMESTIC_PURCHASE | 0.개별계약서(국내매입)(BL#BUD0106145) |

- BL 세무사 양식은 `금액(원)`을 포함하고 관세사 양식은 금액 행, 이자/수수료/특약 금액을 자동 출력하지 않는다.
- BL 양도자는 계약업체, 양수자는 당사이다. 동일 계약 PK에서 3종 문서를 각각 생성한다.
- 원본 국내매입 이자율 표의 두 번째 항목명 `연장시 수수료율(vat별도)`는 원본 표기를 유지하되 값은 계약의 2차 이자율이다. 세무표시는 입력 조건을 반영한다. 문구를 임의로 법률 교정하지 않았다.
- 원본 출고 조항의 `고객사 지정계좌`도 그대로 유지했다. 입금계좌 줄은 당사 Master의 bank1을 사용한다. 원본 조항 변경은 별도 업무 검토 사항이다.

## 자동승계 및 미입력 정책

`contract_document_templates.py`는 데이터 매핑을 담당하고 `templates/contracts/*.html`은 문구와 표 구조를 담당한다. 계약일에 유효한 최신 조건을 선택한다. 미래 조건을 현재 계약에 자동 적용하지 않는다.

자동반영: 계약번호/일자, 당사·계약업체 상호/사업자번호/주소/대표, 계약상품명/Box/Kg, 원화 기준단가와 상품행별 원단위 올림 금액, 1·2차 이자/중개수수료율 및 적용기간, 기간 연장 가산율 차이, 창고료/추가비용의 요율·단위·세무·부담주체·비고, 계약/상품 특약, 보증금 약정액, 추가 출고업체, 당사 계좌. 연결된 ACTIVE 계약 LOT에서 원산지/BL/Container/창고를 승계하고 원산지 미연결 시 상품 Master를 사용한다.

- 단가/금액은 해당 원본에 그 항목이 있는 경우만 표시한다.
- 기존 contract_unit_price는 GUI의 원/Kg 기준단가다. 수입 두 양식의 USD 오퍼단가/물품총액으로 잘못 표시하거나 임의 환산하지 않는다. 현재 저장 구조에 USD 오퍼/인보이스 참조가 없어 해당 칸은 빈칸이다. 보증금 비율도 저장값이 없으므로 빈칸이며 약정액은 조건에 표시한다.
- 미입력/미연결 값은 `________`로 표시한다. 초안 표의 빈칸을 사용자가 검토·수정할 수 있다. 이 문서 편집은 원계약 조건/계산을 변경하지 않는다.
- 본문에는 JSON, 내부 필드명, 객체 표현, Sample Template 경고가 자동 노출되지 않는다.
- 특약은 사용자가 입력한 실제 텍스트를 사용하며 법률문구를 새로 생성하지 않는다.

## API / Snapshot / Version / Audit

- 기존 `ContractDocument.body`에 HTML을 저장하고 기존 snapshot_json에 body_format=HTML 및 template_revision=20261008.v1을 기록한다. 별도 컬럼 불필요.
- 생성 시 Master/계약/LOT 정보가 Snapshot으로 고정된다. 확정 시 편집한 본문도 고정되며 출력은 확정 Snapshot을 사용한다. Master/템플릿 변경으로 과거 확정본을 재계산하지 않는다.
- 초안 중복 제한과 확정본 SUPERSEDED 처리는 같은 template_type 단위다. 다른 BL 출력양식을 덮어쓰지 않는다. version은 기존 계약 전체 순번 및 UNIQUE(contract_id, version)를 유지한다.
- 수입접수 자동승계는 해당 계약의 기본 확정 양식을 선택한다. 세무사/관세사 제출 문서를 업무 기본 계약으로 잘못 선택하지 않는다. 원가/배부 계산은 그대로다.
- 새 POST `/contract-documents/{document_id}/regenerate`: DRAFT만 저장된 source Snapshot으로 표준양식을 재작성한다. ID/version 유지, 기존 UPDATE 권한, Audit before/after/reason 기록. 확정본/취소본/대체본 재작성 거부.
- 기존 확정 plain text/Sample 문서는 자동 교체하지 않는다. 새로운 version으로 작성한다.
- 문구 저장은 HTML과 기존 plain text를 모두 지원한다. 외부 이미지/파일/링크/script 리소스는 허용하지 않는다.
- PDF 실패 시 SALE/계약/문서 Snapshot을 변경하지 않고 임시 PDF를 정리한다. 기존 대상 파일은 성공 시에만 교체한다.

## GUI 및 출력

기존 `2.계약서 작성/조회`에서 계약을 선택하면 해당 유형의 양식만 표시한다. 표준 HTML을 QTextEdit에 문구/표로 표시한다. 초안은 직접 문구 및 셀 편집, 확정본은 읽기 전용이다. 외부 rich-text 붙여넣기는 막고 plain text로 처리한다. 확정 버튼은 미저장 편집을 먼저 저장한다.

`표준양식 다시 작성`은 기존 JSON 예시 초안을 전환하거나 초안 편집을 취소하고 source Snapshot으로 되돌릴 때 사용한다. 저장되지 않은 문구도 초기화되므로 필요시 먼저 별도로 보존한다. 확정본은 새 version을 생성한다. 목록에는 출력양식을 표시한다.

PDF 저장은 QPdfWriter, 실제 종이 인쇄만 기존 QPrinter/QPrintDialog를 사용한다. PDF 저장에서 native printer discovery를 하지 않는다. 거래명세표 폰트 코드 및 기존 Batch 1A 환경성 테스트는 수정하지 않았다.

## 검증

- clean bc0e5c4 baseline: 223 passed, 1 warning.
- 신규 계약서 V1: 23개 테스트. 5양식 조항/표, 금액 숨김, 미입력, 미래조건, 원단위 금액, BL 3종/같은 유형 supersede, 기존 초안 재작성/Audit, HTML 저장/확정, Snapshot 불변, 리소스 차단, GUI 선택/자동저장, 5종 한글 PDF, 기존 plain 확정본, 실제 GUI 비용조건, 100상품 다중 페이지, 실제 ERP LOT 메타데이터를 검증한다.
- Financing/Batch2A 포함 선택: 71 passed, 1 warning.
- 전체 pytest: 246 passed, 1 warning. warning은 기존 Starlette/httpx deprecation이다.
- Work Qt offscreen 테스트는 설치한 실제 Nanum 폰트와 별도 FONTCONFIG_FILE을 사용한다. 제품의 한글 글꼴 판정 정책 변경 없음.
- 5종 PDF를 생성·렌더링해 표/한글/서명란을 시각 확인했다. 일반 1상품 예시 5종 모두 A4 1페이지, 100상품은 다중 페이지이며 마지막 상품/서명 추출도 검증했다. 입력 길이/폰트 차이에 따라 실제 페이지 수는 달라질 수 있다.
- Python compile, UTF-8 검사, git diff --check 통과. clean bc0e5c4 별도 작업공간에서 patch git apply --check 통과.
- API 자동검증은 SQLite FK 활성화 및 실제 FastAPI/ORM을 사용한다. 실제 SQL Server DB 실행, Windows 프린터 인쇄는 수행하지 않았다.

## DEV 실제 GUI 검증

1. clean bc0e5c4에 제공 patch 하나를 적용한다. Migration 없이 API와 GUI를 갱신 실행한다.
2. 계약 FC-00001-261006-00001-IM-0001을 선택한다. 기존 문서가 DRAFT이면 문서를 열고 `표준양식 다시 작성`; 확정본이면 새 자동초안을 만든다.
3. 문구/표/당사자/수량/이자·비용 조건을 원본 PDF와 비교하고 USD/인보이스/보증금 비율 등 미입력 칸을 검토한다. 표 셀 및 특약을 수정·저장하거나 바로 확정한다.
4. 확정 후 PDF 저장/재저장 및 인쇄한다. Windows Malgun Gothic에서 표, 서명란, 긴 주소 및 여러 상품의 페이지 분할을 확인한다.
5. BL 계약 한 건에서 기본/세무사용/관세사용을 각각 생성·확정한다. 세무사용만 금액이 있고 세 양식이 함께 조회되는지 확인한다. 관세사용 문구 편집 시 금액을 수동 추가하지 않는다.
6. 같은 양식 새 version 확정 후 해당 양식의 이전 문서만 대체되며 다른 양식은 유지되는지, Master 변경 후 과거 PDF가 바뀌지 않는지 확인한다.

## 남은 제한사항

- V1은 원본 표/조항에 충실한 Qt HTML 출력으로, 스캔 문서와 픽셀 단위 동일성 및 실제 도장 이미지를 구현하지 않는다.
- USD 오퍼/인보이스 참조/보증금 비율의 구조화 자동승계는 현재 DB에 값이 없어 불가능하다. 초안에서 수동 확인하는 방식이며 신규 금융조건/통화 계산 또는 Schema를 추가하지 않았다.
- 자유 문구 편집은 업무 담당자가 검토해야 한다. 관세사용 자동생성은 금액을 제외하지만 사용자가 직접 금액 문구를 추가하는 행위까지 의미 분석으로 차단하지 않는다.
- 최초 생성/새 version에는 현재 Master를 사용한다. 이것을 과거 당시 Master로 간주하지 않는다. 기존 초안 재작성에는 당시 저장 source를 사용한다.
- Work 자동검증 완료, 사용자 DEV GUI/PDF/프린터 검증 및 배포는 남아 있다.
