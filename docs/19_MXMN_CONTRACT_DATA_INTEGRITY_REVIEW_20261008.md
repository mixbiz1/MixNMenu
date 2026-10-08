# MXMN 계약서 V1 — 계약내용·데이터 정합성 검토 및 수정

## 기준 및 검증 범위

- Repository: `mixbiz1/MixNMenu`, main `b961b3c` (`fix: allow draft contract PDF preview and printing`). 작업 시작 GitHub fetch 결과 최신 main과 일치.
- 해당 HEAD의 clean 별도 작업공간에서 시작했다. 기존 patch/다른 작업트리 수정사항을 혼합하지 않았다.
- docs/15~18, 실제 ORM/DTO/API/GUI/5종 출력 매핑, 사용자가 저장한 `계약서_1_v1.pdf` 및 스캔 수입대행 표준 원본을 확인했다.
- 실제 검증 대상: `FC-00001-261006-00001-IM-0001`, 문서 ID 1 / DRAFT / Version 1. **DEV/SERVER DB에 접속하여 해당 행을 조회하거나 변경한 것은 아니다.** PDF만으로 raw DB 값과 저장 당시 GUI 입력 의도를 확정할 수 없다. 아래 DB 분석은 공식 소스의 ORM·Migration·DTO·저장 경로에 대한 확인이다.
- 자동검증은 FK 활성 SQLite + 실제 FastAPI/ORM 및 Linux Qt offscreen/Nanum 폰트로 수행했다. 실제 SQL Server 실행 및 Windows 프린터 출력은 수행하지 않았다.

## 실제 수정 완료

### 1. 미입력과 명시적 0원

공식 `tb_fin_contract_term`의 창고료·입출고비·계근비는 ORM와 SQL Server Migration 모두 `NOT NULL / DEFAULT 0`이다. TermInput도 생략값을 Decimal(0)으로 만들며 기존 GUI는 공란을 0으로 보냈다. 따라서 과거 숫자 컬럼의 0만으로 미입력/명시적 0을 구분할 수 없다. 저장된 Decimal이 JSON 문자열 `"0.000000"`으로 전달되면 기존 int/Decimal 0 제외 비교도 통과하여 입출고비/계근비 0.00이 출력되었다.

변경된 **출력 판정**:

| 저장 출처 | 출력 |
| --- | --- |
| NULL/미입력 | 미확정 또는 기존 빈칸 |
| expense_conditions에 명시된 unit_rate=0 | 0.00원 |
| 새 조건의 document_rate_inputs=true + 숫자 0 | 0.00원 |
| 과거 표준 숫자 컬럼 0, 입력 여부 기록 없음 | 미확정 — 과거 0원 합의 여부 확인 필요 |
| 기존 양수 요율 | 해당 요율 유지 |

- 기존 `conditions_json`에 `document_rate_inputs`를 기록한다. 창고료·입출고비·계근비·최초 이자/수수료의 입력 여부만 보존하며 숫자 컬럼 및 계산은 변경하지 않는다.
- API는 요청에서 실제 지정한 필드를 기록하고, GUI는 공란/0 여부를 별도로 전달한다. 잘못된 입력 여부 타입 또는 미입력 표시와 양수 요율의 모순은 저장 전에 거부한다.
- GUI 재조회에서 명시적 0 요율/상품단가가 빈칸으로 소실되는 truthiness 비교도 수정했다. flat 비용 조건을 재조회할 때 저장값을 보여주되 세무/부담주체를 임의 지정하지 않는다.
- 이 처리로 과거 0의 입력 의도를 복원했다고 주장하지 않는다. 과거 term/Audit/확정문서를 자동 수정하지 않는다.

### 2. 출고약정기간

`contract_days`는 기존 ORM/TermInput/템플릿에 있으나 GUI 조건 입력/전송이 없었다. 기존 필드를 입력하는 `출고약정 / 계약기간 (일)`을 추가했다. 1차 이자 적용기간과 별개로 저장하며 90일 이자 기간을 출고약정기간으로 대체하지 않는다. 새 약정일수는 기존 조건 버전 추가 경로를 사용한다.

### 3. 계약 당사자

Account Master에는 `account_name` 한 개만 있고 별도 legal_name/관리용 별칭 필드가 없다. CompanyAccount에도 법적 상호 필드가 없다. 연락담당자와 대표자는 별도 값이며 상호를 복구할 출처로 사용하지 않는다.

- 보고된 `(계약)` 접두어가 있는 이름은 법적 상호로 자동 인증하지 않고 빈칸 + 확인 안내로 처리한다.
- 접두어/접미어를 제거하여 상호를 추정하지 않는다. 특히 `_` 또는 괄호를 포함한 정상 상호를 자르지 않는다.
- 사업자번호·대표자·주소/상세주소는 원본 Master에서 승계한 Snapshot 그대로 유지한다.
- Master 및 과거 본문은 변경하지 않는다. 기존 ID 1은 명시적인 초안 재작성/문구 저장을 하기 전까지 기존 내용을 유지한다.

### 4. 확정 전 확인 안내

문서 API 응답에 read-only `validation`을 추가하고 계약서 GUI에 필수 확인 / 선택·추가조건 확인을 표시한다. 5양식에 공통 당사자·상품 검증을 적용하며 해당 양식에 없는 금액/조건을 요구하지 않는다.

이 안내는 **자동승계 원본에 대한 누락 안내**이다. 수동 편집한 본문을 분석하여 원계약 조건이 확정되었다고 간주하지 않는다. 기존 확정 API의 상태전이·확정 권한 및 Audit 규칙은 그대로이며 별도 강제 차단/승인 Workflow를 추가하지 않았다. 서명 전 업무 담당자의 실제 문구 검토가 필요하다.

## 항목별 실제 데이터 매핑

계약서 생성은 `contract_source()` → `_snapshot()`/party/LOT metadata → `ContractDocument.snapshot_json` → `render()` → 저장된 body 순서다. DRAFT 출력은 저장 body, CONFIRMED 출력은 확정 snapshot.body를 사용하며 출력 시 현재 Master로 재계산하지 않는다.

| 항목 | DB / DTO / Snapshot 출처 | PDF 연결 및 판정 |
| --- | --- | --- |
| 계약번호·일자 | tb_fin_contract.contract_no / contract_date → ContractCreate/Update → contract | contract_no / contract_date_ko |
| 상품·Box·Kg | tb_fin_contract_item.product_id / contract_box_qty / contract_weight → ContractItemInput → items | goods_rows, total_box, total_kg |
| 원화 기준단가 | tb_fin_contract_item.contract_unit_price → ContractItemInput → items | 국내매입 단가/금액, BL 세무사용 양도금액. 행별 원단위 올림 합계 유지 |
| USD 오퍼단가·USD 물품총액 | 현재 계약상품 DTO/DB에 없음. ImportCase.currency는 통화 코드만 있고 ImportCaseItem에도 오퍼 단가 없음 | 수입대행/BL 기본의 USD 칸은 빈칸. KRW 기준단가, 실제 원가, 환율, Product 기본단가로 대체하지 않음 |
| 보증금 비율 | 비율 컬럼 없음. tb_fin_contract.deposit_required / deposit_amount / deposit_memo만 있음 | 원본 비율칸 빈칸. 약정액은 기존 조건에 표시. 비율 역산하지 않음 |
| 출고약정/계약기간 | tb_fin_contract_term.contract_days → TermInput → 유효 term | contract_days. interest_period_days_1과 별개 |
| 계약수수료·연장율 | brokerage_rate_1 / brokerage_rate_2, legacy brokerage_rate → TermInput → term | brokerage_1 / brokerage_2. 연장 가산율은 2차−1차 |
| 이자·연장율 | interest_rate_1 / interest_rate_2, legacy annual_interest_rate; interest_period_days_1/2 | interest_1/2, interest_increment; 적용기간 extras. 조건의 실 적용 계산은 변경 없음 |
| 수수료 세무·부담 | conditions_json.expense_conditions BROKERAGE.tax_treatment / payer | 과세·면세 표기와 부담주체. 미입력 시 빈칸 및 안내 |
| 창고료 | storage_rate_per_kg_day 또는 expense_conditions.STORAGE.unit_rate/basis/tax_treatment/payer | 명시적 비용행 우선; default zero는 위 입력출처 판정 |
| 입출고비·계근비 | inbound_outbound_rate_per_kg / weighing_rate_per_box 또는 INOUT/INBOUND_OUTBOUND/WEIGHING 비용행 | 명시적 비용행 우선; 단위·세무·부담 표시 유지 |
| 판매대금 계좌 | tb_company.bank1 → CompanySchema → company.bank1 | bank_account. bank2 또는 고객사 은행계좌로 자동 대체하지 않음 |
| 당사 | tb_company.comp_name / biz_no / ceo_name / address → CompanySchema → company | 당사자·서명란 |
| 계약업체 | tb_account.account_name / biz_no / ceo_name / address / address_detail → AccountSchema → partner | 법적 상호 출처 검토, 관리 접두어가 있으면 빈칸 및 안내 |
| BL·Container·창고·원산지 | ACTIVE 계약 LOT와 실제 ERP Lot/Warehouse. 원산지 미연결 시 Product.origin | document_goods → 상품표/BL 양식. 미연결은 빈칸 |

## 기존 기능으로 정상 확인

- DRAFT PDF/인쇄 허용 및 출력에만 `초안 / 검토용` 표시.
- CONFIRMED 초안 표시 없음, 본문 수정/재작성 금지, Snapshot 출력.
- CANCELLED는 기존 취소 표시 출력 허용 정책 유지. SUPERSEDED/Version도 기존 정책 유지.
- 문서 GET·PDF·인쇄·검증 안내는 DB 상태/version/body/snapshot/Audit을 변경하지 않는다.
- A4 세로 1페이지, 최소 8.5pt, 수용한계 초과 감지·기존 PDF 보존, QPdfWriter 및 PDF의 QPrinter discovery 미사용 유지.
- BL 세무사용만 원화 금액 표시, 관세사용은 금액·이자·수수료·특약의 자동 출력 제외.
- templates/contracts/*.html의 법적 조항은 **수정하지 않았다**. 출력기/폰트 선택 코드도 변경하지 않았다.
- 회수유형, 계약번호, LOT/재고/원가/배부/일반매입·매출 계산과 기존 확정 상태전이는 변경 없음.

## 사용자 업무결정 필요

1. **제3조 입금계좌 문구**: 제공된 원본 스캔 수입대행 계약서도 “예상금액을 ‘고객사’ 지정계좌로 입금완료한 후”라고 적혀 있다. 같은 원본의 보증금 조항은 판매사 지정계좌, 입금계좌 줄은 판매사 계좌다. 현재 템플릿은 원문에 충실하지만 문구 안의 계좌 지정 주체와 당사 bank1 출력 사이에 업무상 확인이 필요하다. 사용자 승인 전 교정하지 않았다.
2. **법적 상호**: 현재 Master의 account_name을 사업자 원본 상호로 관리할지, 관리용 별칭/법적 상호를 별도로 저장할지 결정 필요. 기존 문자열을 잘라 `주식회사...`로 추정하지 않았다. 당장 기존 초안의 서명용 상호는 확인된 사업자 원본을 보고 문구에서 보완할 수 있다.
3. **USD 오퍼/인보이스 및 보증금 비율**: 구조화 저장·참조할 업무 데이터 출처 결정 필요. 현재 V1에는 값이 없어 자동입력 불가하며 초안에서 검토·수동 보완 가능. 샘플 요율·금액·계좌를 가져오지 않는다.
4. **과거 0의 의미**: 저장 출처가 없으면 합의된 0원인지 미입력인지 복원 불가. 원계약/Audit 근거 확인 후 기존 조건 버전 및 초안 편집 경로로 명시한다. 과거 확정 Snapshot을 재계산하지 않는다.
5. **확정 안내의 강제 차단 여부**: 이번 수정은 누락 안내이며 강제 서명조건/승인 절차를 정의하지 않는다. 본문 수동 보완과 구조화 원계약 조건의 확정 기준을 별도 업무정책으로 정할 수 있다.

## DB Migration 필요 여부

이번 patch는 **Migration 불필요**. 기존 조건 JSON에 입력 여부를 기록하며 숫자 컬럼의 nullable/default 및 모든 테이블/제약조건을 유지한다. 과거 데이터 backfill도 없다. 법적 상호 별도 컬럼 또는 USD 오퍼/보증금 비율의 구조화 저장을 선택하면 후속 설계·Migration 영향 검토가 필요하다.

## 테스트 및 PDF 검증

- clean b961b3c baseline: 283 passed, 1 warning.
- 신규 정합성 회귀: 35개. NULL/문자열 0/default 0/명시적 0, 비용행 NULL/0, API 입력출처·원자적 오류, SQL Server ORM DDL, GUI 0 재조회·약정기간 별도 승계, 상호 추정 금지, 누락 안내, 5종 PDF 및 과거 ID 1 보호 포함.
- 관련 선택: **160 passed, 1 warning**.
- 전체 pytest: **318 passed, 1 warning**.
- warning: 기존 Starlette/httpx deprecation.
- Python compile / UTF-8 / git diff --check: 통과.
- clean b961b3c 별도 작업공간 git apply --check: 통과.

| 출력양식 | 실제 생성 PDF 페이지 | 확인 |
| --- | --- | --- |
| 수입대행 | A4 세로 1 | 한글·USD 빈칸·미확정 비용·조항·서명 |
| BL 기본 | A4 세로 1 | 한글·USD 빈칸·미확정 비용·조항·서명 |
| BL 세무사용 | A4 세로 1 | 49,512,128원·당사자·상품·BL·서명 |
| BL 관세사용 | A4 세로 1 | 금액 없음·당사자·상품·BL·서명 |
| 국내매입 | A4 세로 1 | 원화 단가/금액·미확정 비용·조항·서명 |

5종 PDF를 실제 생성하고 QTextDocument 전체 본문 블록과 PDF 추출문을 대조했다. PNG 렌더링으로 잘림/겹침 없이 표와 서명란이 유지되는지 확인했다. CONFIRMED 및 재출력 회귀, 내용 초과 오류, 기존 거래명세표·Financing 회귀도 선택/전체 suite에 포함했다. Windows DEV 실제 PDF/인쇄 검증은 별도이다.

## 변경 파일 / 적용

- contract_document_templates.py
- financing_contract_routes.py
- financing_intake_routes.py
- views/financing_contract_reg.py
- views/financing_intake.py
- tests/test_contract_document_integrity.py
- tests/test_batch2a_contract_import_cost.py (새 매핑 revision 식별자 검증)
- docs/19_MXMN_CONTRACT_DATA_INTEGRITY_REVIEW_20261008.md

최종 patch: `MXMN_CONTRACT_DATA_INTEGRITY_FIX_b961b3c_20261008.patch`. clean b961b3c에 단독 적용한다. 기존 patch들을 추가 적용하지 않는다.

기존 ID 1은 적용만으로 변경되지 않는다. DRAFT의 `표준양식 다시 작성`은 기존 source Snapshot을 사용하고 ID/version을 유지하는 기존 Audit 작업이다. 이때 새 미확정 표시와 상호 안내가 적용된다. Master를 수정해도 과거 source는 자동 갱신되지 않는다. 확정본은 그대로 보존하고 필요한 경우 새 version을 작성한다.

실제 DB Migration, commit/push, SERVER 반영은 수행하지 않았다. **자동 표시·검증 코드 마감 완료 / 위 업무결정 및 실제 문서 필수값 보완은 미완료**로 구분한다.
