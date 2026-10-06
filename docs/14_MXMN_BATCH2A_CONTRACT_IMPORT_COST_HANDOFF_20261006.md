# MXMN Batch 2A — 계약서·수입접수·실제 수입원가 인수인계

작성일: 2026-10-06. Repository: `mixbiz1/MixNMenu`, branch: `main`.
공식 Source of Truth: **7d245a0**, `test: close distribution e2e batch 1b`.
이번 변경은 해당 HEAD의 별도 clean worktree에서 작성했다. commit/push, DEV/SERVER 변경, 실제 DB Migration을 수행하지 않았다.

## 1. 완료 범위와 판정

Work 자동검증 기준 Batch 2A Vertical Slice 완료:

계약관리 → 3종 계약서 자동초안/편집/확정 → 수입건 자동승계 → 기존 ERP 입고/LOT 연결 → 실제 발생 원가 및 ± 자유항목 → 원가확정 → 복수 LOT 배부 → Snapshot/Audit.

하나의 연속 HTTP/ORM 시나리오에서 위 연결을 검증했다. 화면은 기존 계약관리와 별도 계약서 작성/조회·수입접수·수입원가정산의 4개로 제한했다. 기존 일반유통·Financing Phase 1을 재설계하지 않았다.

**DEV 실제 SQL Server Migration/Windows GUI 신규 화면 검증은 별도 확인이 필요하다.** Work의 SQLite E2E/SQL Server DDL 정적·가짜 연결 테스트를 실제 SQL Server 실행 성공으로 간주하지 않는다.

## 2. 기존 구현 분석과 재사용

- 문서 11/12/13과 실제 `models.py`, 계약/API/GUI/Migration, Purchase/LOT, Audit, 공통 Lookup 및 원단위 올림 정책을 확인했다.
- 계약 중심: `tb_fin_contract` → `tb_fin_contract_item`/term/participant/`tb_fin_contract_lot`.
- 기존 LOT는 `tb_lot(lot_id)`. 입고수량은 `tb_inbound`/`tb_inbound_item`, 출고는 `tb_outbound`/`tb_outbound_item`. 새로운 재고 누적표나 BL 원장을 만들지 않았다.
- 실제 입고/LOT 생성은 기존 매입 또는 최초재고 API/GUI를 사용한다. 수입접수는 기존 LOT의 PK를 연결하고, 원가확정은 기존 계약 LOT 연결 함수를 재사용한다.
- 거래처·상품·계약·LOT 선택은 기존 LookupDialog. 기존 계약상품/참여·출고업체 검색은 Batch 1A 구현을 그대로 유지했다.
- Audit는 기존 `record_audit_event`/`tb_audit_event`와 같은 업무 트랜잭션을 사용한다.
- 기존 SALE/OUTBOUND, 채권·채무, 입금·지급 FIFO, 거래명세표 제품 PDF 코드는 변경하지 않았다.

## 3. 데이터 연결 및 자동승계

| 단계 | 연결 키 | 자동승계/확정 결과 |
|---|---|---|
| 계약 → 계약서 | contract_id, template_type, version | 계약번호/일자, 당사·계약업체 사업자/주소 정보, 상품·BOX/KG·기준단가, 이자/수수료/창고료/회수유형, 특별조건·참여업체 |
| 계약/확정 계약서 → 수입건 | contract_id, contract_item_id | 확정 계약서가 있으면 그 Snapshot 전체를 source_snapshot으로 복사; 없으면 현재 확정 계약의 참고 Snapshot. 상품/예정수량은 기존 계약상품에서 생성 |
| 수입건 → ERP LOT | import_case_id, case_item_id, product_id, lot_id, bl_no | 예정상품행을 실제 LOT 단위로 분할하고 기존 LOT PK를 검색 연결 |
| 수입건 → 원가정산 | import_case_id, settlement_id, version | 계약 참고조건·상품·BL·연결 LOT. 기본 5행은 AUTO 출처와 참고 Snapshot을 저장 |
| 실제 원가 → 배부 | cost_row_id, case_item_id, lot_id | 실제 발생값의 합계, 정확한 원단위 LOT 배부액, 실제 입고 KG, 기존/새 LOT 개별원가 |
| 원가확정 → 계약 LOT | contract_id, contract_item_id, lot_id | 기존 Phase 1의 상품 일치/수량 한도/다른 계약 약정 Guard를 통과한 실제 입고 BOX/KG 연결 |

계약업체와 실제 공급업체는 다른 역할이다. 공급업체를 계약업체로 임의 자동 지정하지 않고 회사에 등록된 거래처를 별도로 검색한다. 일반 수입건은 contract_id 없이 상품을 검색 추가할 수 있다.

계약상 기준일과 실제 발생일을 구분한다. 기존 계약 화면은 “계약상 조건 적용 기준일”로 표시하고, 실제 통관/입고일과 원가행 발생일은 별도로 확인 입력한다. 기본 원가행의 금액/날짜는 미입력 상태이며 계약상 예상값을 실제 발생금액으로 간주하지 않는다.

## 4. 신규 테이블

| 테이블 | PK | 목적/주요 필드 |
|---|---|---|
| tb_fin_contract_document | document_id | 회사, 계약, template_type, version, 상태, 편집 body, snapshot_json, 사용자/일시 |
| tb_import_case | import_case_id | 회사, nullable 계약, 회사별 고유 수입번호, supplier_account_id, BL/reference/통화, 실제 통관/입고일, 상태, 참고 source_snapshot_json |
| tb_import_case_item | case_item_id | 수입건, 행번호, nullable 계약상품, 상품, nullable 기존 LOT, BOX/KG, 비고 |
| tb_import_cost_settlement | settlement_id | 회사, 수입건, version, 상태, 최종 total_cost, 확정 snapshot_json |
| tb_import_cost_row | cost_row_id | EVENT/PERIOD, 발생일/기간·Rate·Basis·수량, signed 실제 금액, 통화/환율/원화액, 세무속성/실제 세액/원가포함 여부, 부담주체, AUTO/MANUAL 출처·참고 JSON, 상품/LOT 범위 |
| tb_import_cost_allocation | allocation_id | 정산, 수입상품, LOT, 실제 입고 KG, 정확한 배부액, 올림 단가, 이전 단가, 배부 방식 |

계약별 계약서 version, 수입건별 원가 version, 수입건별 상품 행번호, 원가정산별 원가 행번호/LOT 배부에 UNIQUE 제약이 있다. 상태 및 원가행 종류에 CHECK 제약이 있다. FK는 실제 기존 Company/User/Account/Product/FinancingContract/ContractItem/LOT 모델과 일치한다.

기존 테이블 컬럼 변경은 없다. 기존 모델과 거래 연결은 보존한다.

## 5. API

아래 모든 경로는 `/api/v1/companies/{comp_code}` 하위다.

| 경로 | 메서드/용도 |
|---|---|
| /contract-documents | GET 목록(contract_id 필터), POST 확정 계약에서 자동초안 생성 |
| /contract-documents/{document_id} | GET 재조회, PUT 초안 body 편집 |
| /contract-documents/{document_id}/confirm | POST 확정; 같은 확정본 재요청은 동일 결과 |
| /contract-documents/{document_id}/cancel | POST 사유와 취소, Snapshot 유지 |
| /import-cases | GET 검색/목록, POST 계약 자동승계 또는 일반 수입건 생성 |
| /import-cases/{import_case_id} | GET 상세, PUT LOT·실제 접수정보 수정 |
| /import-cases/{import_case_id}/start, /close | POST 접수 진행 / 원가확정 후 수입건 마감 |
| /import-costs | GET 목록(import_case_id 필터), POST 기본 5행 또는 빈 정산 생성 |
| /import-costs/{settlement_id} | GET 원가행/배부/확정 Snapshot 재조회 |
| /import-costs/{settlement_id}/rows | POST ± 자유항목 |
| /import-costs/{settlement_id}/rows/{cost_row_id} | PUT 실제 값 편집, DELETE 미발생 행 삭제 |
| /import-costs/{settlement_id}/confirm | POST WEIGHT 또는 DIRECT 확정/LOT 반영; 중복 확정은 동일 결과 |
| /import-costs/{settlement_id}/cancel | POST 사유와 취소/안전한 기존 단가 복원 |

신규 메뉴 FINANCING_DOCUMENT / IMPORT_INTAKE / IMPORT_COST의 기존 CRUD 권한을 사용한다. 확정·취소·시작·마감은 update, 원가행 추가는 부모 정산 편집인 update 권한이다. 상품/거래처/계약/수입건/LOT의 좁은 조회 경로만 lookup_for로 해당 업무 read 권한을 재사용한다. lookup_for가 수정 권한이나 다른 회사 접근을 허용하지 않는다. Migration은 메뉴만 추가하며 일반 사용자에게 자동 권한을 부여하지 않는다.

## 6. GUI

`9.파이낸싱/계약판매` 메뉴:

1. 기존 파이낸싱 계약관리: 기존 공통 검색 유지, 계약 기준일 표시만 명확화.
2. 계약서 작성/조회: 확정 계약 검색 → 유형 자동선택 → 초안 생성 → 본문 편집/저장 → 확정 → 재조회/PDF/인쇄. 확정 본문은 읽기 전용, 새 version은 기존 본문을 덮어쓰지 않는다.
3. 수입접수: 계약 검색 시 상품 PK/예정수량 자동승계. 실제 공급업체, BL/reference/통화/실제 날짜 입력. 상품행 분할·삭제·LOT 검색 연결. 저장/접수 진행/원가확정 후 마감.
4. 수입원가정산: 수입건/BL 검색, 상단 참고 계약조건, 실제 원가행 Grid와 EVENT/PERIOD 입력, ± 자유항목/삭제, 하단 원가합계 및 WEIGHT/DIRECT 배부. 상품/LOT 비용 범위도 PK 검색 선택이다.

확정 전 배부 표의 KG는 수입접수의 참고 수량이며, 확정 후에는 실제 입고원장 KG다. 서버가 확정 시 실제 입고 중량을 다시 읽는다. 이 구분을 “참고/확정 KG”로 표시한다.

계약서 출력은 Snapshot 본문을 HTML escape 후 출력한다. PDF는 QPdfWriter와 원자적 임시파일 교체를 사용하며 QPrinter discovery를 호출하지 않는다. 실제 프린터 선택은 사용자가 인쇄 버튼을 누를 때만 실행한다. PDF 생성 실패는 계약/확정 Snapshot을 변경하지 않는다. 실제 법률문구는 승인 전 Sample Template이며, 전자서명/범용 Word Designer를 만들지 않았다.

## 7. 상태전이·수정 Guard

- 계약서: DRAFT → CONFIRMED → SUPERSEDED 또는 CANCELLED. 새 초안 version을 확정하면 이전 확정본을 SUPERSEDED로 표시하고 내용은 유지한다. 초안 중복 생성은 차단한다.
- 수입건: DRAFT → IN_PROGRESS → COSTING → COST_CONFIRMED → CLOSED. 계약 연결은 생성 후 변경 불가. 원가정산을 하나라도 시작한 뒤에는 기본정보/상품행을 수정하지 않는다.
- 원가: DRAFT → CONFIRMED → CANCELLED. 취소 후 수입건은 COSTING으로 돌아가 새 원가 version을 생성할 수 있다. 과거 원가행/배부/Snapshot은 유지한다. 확정된 원가행의 직접 수정/삭제는 차단한다.
- 수입건 CLOSED는 수입접수의 마감이며 **Financing 계약 최종마감이 아니다**.
- 실제 입고 중량, 활성 OPEN LOT, 회사/상품/BL 일치, 계약상품 및 약정 한도를 검사한다. 한 수입건의 같은 LOT 중복과 다른 확정 정산의 LOT 중복 배부를 차단한다.
- 출고 또는 SALE ITEM 이력이 있으면 원가확정/복원을 차단한다. 취소된 매출의 과거 사용 이력도 보호한다.
- 취소 시 LOT 현재 단가가 확정 단가와 다르면 자동 복원하지 않는다. CLOSED 수입건의 원가취소도 차단한다.
- 연결된 수입건 LOT의 기존 매입 수정/취소, 최초재고 수정/삭제, LOT 마스터의 상품·창고·BL·원가 변경을 차단하여 입고/원가 기준을 보호한다. COSTING 전에는 수입접수에서 LOT 연결을 해제한 뒤 원거래를 정정할 수 있다.
- 확정 계약서나 수입건이 연결된 원계약 취소를 차단한다. 기존 Phase 1 정책을 완화하지 않았다.

## 8. 수치·세무·배부 정책

- BOX는 정수, KG는 소수 2자리. 실제 금액/Rate/Basis 수량은 소수 4자리, 환율은 2자리, 원화 비용/배부액은 원단위다.
- 원화 비용 = 실제 signed 금액 × 실제 환율, 기존 정책과 같은 ROUND_CEILING 원단위 올림. KRW 환율은 1 또는 생략. 외화 금액 입력 시 실제 환율이 필수다. 예: -0.01 USD × 1300.50 → -13원.
- 세무속성(EXEMPT/TAXABLE/ZERO/OUT_OF_SCOPE) 및 실제 세액 KRW를 보존한다. 세액은 자동 세금계산이 아니며, capitalize_tax=true인 행만 실제 세액을 원가에 더한다.
- 부담주체(MXMN/CONTRACTOR/SUPPLIER/SHIPPER)는 추적 속성이다. 이번 Batch에서 주체별 채권·채무/회수액을 생성하지 않는다. 입력된 원가행은 주체와 무관하게 정산 총원가에 포함된다.
- EVENT는 확정 시 실제 발생일/금액이 필수. PERIOD는 시작·종료일/Rate/Basis/수량과 실제 결과금액이 필수. 자동 이자·기간정산 엔진은 아니다.
- 기본 5행은 사용자가 금액/발생일을 채우거나 삭제해야 한다. null은 실제 미입력, 0은 확인된 0원이다. ± 추가행을 포함한 모든 행의 원화액 합계가 확정 총원가이며 합계 직접 덮어쓰기는 없다.
- WEIGHT는 기존 입고원장 SUM(weight)의 비례배부. 각 원가행을 BL 전체/지정 상품/지정 LOT 범위에 배부한다. 절대액 비례 계산의 원단위 미만을 버리고 그 행의 마지막 LOT에 잔액 보정, 음수행은 부호를 복원한다. **모든 LOT 배부액 합계 = 확정 총원가**.
- DIRECT는 모든 연결 LOT의 금액을 명시하고 합계가 확정 총원가와 정확히 같아야 한다. 상품/LOT 지정 원가행이 있으면 DIRECT를 허용하지 않고 WEIGHT를 사용한다.
- 확정 총원가는 양수, LOT별 최종 배부액은 0 이상이다. LOT 개별원가 = 해당 정확한 배부액 ÷ 실제 입고 KG를 원단위 올림. 변경 전/후를 Audit 및 allocation에 저장한다.
- **올림 단가 × KG가 정확한 배부액과 다를 수 있다.** 기존 ERP 원단위 단가 정책을 유지한 차이이며, Batch 2B Financing 계산은 allocated_cost/실제 weight Snapshot을 사용하고 단가×중량으로 정확한 총원가를 역산하지 않는다.
- 배부는 재고 수량, 기존 매입전표/채무/입고액을 재작성하지 않는다. 실제 비용은 원가정산에 별도로 보존한다. 비용 지급·세액 회계전표·재평가 분개 자동생성은 이번 범위 밖이다.

## 9. Snapshot·Audit·원자성

- 계약서 확정: 당사/거래처/계약/상품/조건 참고값 + 사용자가 수정한 최종 본문, 유형/version/sample 여부.
- 수입건: 생성 당시 계약서 또는 확정 계약의 참고 Snapshot. 실제 공급업체·통관/입고일은 별도의 실제 데이터다.
- 원가확정: 수입건의 계약 참고 Snapshot, 실제 상품/LOT 및 업체 표시정보, 모든 실제 원가행, 정확한 배부액/입고 KG/이전·새 단가, 확정자/일시/version.
- 이후 상품·거래처 Master 변경은 기존 확정 Snapshot JSON을 바꾸지 않는다. 재조회·출력은 확정 계약서 본문을 그대로 사용한다.
- CREATE/UPDATE/CONFIRM/CANCEL/SUPERSEDE, 수입건 START/COSTING/COST_CONFIRMED/CLOSE, ADD_ROW/UPDATE_ROW/DELETE_ROW, LOT ALLOCATE_COST/RESTORE_COST 이력을 기존 Audit에 기록한다.
- 확정 전체는 같은 DB 트랜잭션이다. LOT 비용 반영/기존 계약 LOT 연결/Audit 중 실패 시 모든 변경을 롤백한다. SQL Server UPDLOCK/HOLDLOCK으로 업무 부모/LOT를 직렬화하고 version UNIQUE로 중복을 방어한다. 실제 SQL Server 동시성/교착 스트레스 검증은 DEV 확인 항목이다.
- 취소는 배부 Snapshot과 계약 LOT/BL 연결을 삭제하지 않는다. 실제 LOT 식별·입고 연결은 계속 유효하며 원가만 안전하게 이전 단가로 복원한다.

## 10. Migration

`db_financing_intake_migrate.py`: 신규 6개 테이블과 기존 메뉴에 3개 메뉴를 추가한다. 애플리케이션 시작 시 실행하지 않는다.

1. 기존 모델 FK 대상의 dbo 테이블/단일 PK 및 메뉴 PK를 SQL Server sys catalog로 먼저 검사. 불일치 시 DDL 전에 명확한 오류.
2. 실제 ORM의 MSSQL CreateTable에서 dbo와 FK 대상을 명시. 각 테이블은 OBJECT_ID 가드, FK/UNIQUE/CHECK는 해당 guarded CREATE TABLE 내부.
3. 각 index는 sys.indexes 존재 가드로 별도 컴파일 batch. 메뉴 insert도 IF NOT EXISTS. 권한 자동 grant 없음.
4. 기존 테이블 ALTER가 없으므로 신규 컬럼 추가/즉시 참조 batch error 207 패턴이 없다. 삭제/기존 데이터 갱신 없음.

자동테스트는 실제 MSSQL dialect로 CREATE TABLE/FK/PK/Unicode/CHECK/UNIQUE를 검증하고, 테이블 생성 순서·index 가드·동일 재실행 SQL·선행 PK 부재 시 DDL 미실행을 검증한다. **실제 Migration 실행은 수행하지 않았다.**

## 11. 자동검증 결과

- 기준 7d245a0 전체 baseline: **184 passed, 1 warning**.
- 신규 Batch 2A 테스트: **34건**. API 연속 E2E/부정·격리·Guard, 실제 HTTP와 연결한 GUI 데이터승계, 계약서 PDF·안전한 실패 주입, Migration 검증.
- Batch 2A + Financing + Batch 1A/1B + 일반 매입/매출/정산 무결성 관련 선택: **102 passed, 1 warning**.
- 전체 pytest: **218 passed, 1 warning**. 경고는 기존 Starlette/httpx deprecation.
- Python compile, UTF-8 읽기/깨짐 검사, `git diff --check`: 통과.
- clean **7d245a0**에서 최종 통합 patch `git apply --check`: 통과.
- 기존 거래명세표 100행 한글/multi-page/Snapshot PDF 테스트도 Work에서 통과. Windows subprocess는 offscreen/시험 폰트 디렉터리 강제를 제거하고 네이티브 Qt font registry를 사용하도록 **harness만** 짧게 변경했다. Windows 분기는 Work에서 실행하지 않았으며 실제 제품 폰트 로직은 변경하지 않았다.

연속 예: 실제 입고 3 LOT, 19 BOX/190 KG → 기본 원가 157,053원 + 추가 1,000원 - Claim 250원 = **157,803원** → 3 LOT 정확한 배부합계 157,803원. 별도 시나리오에서는 PERIOD 실제 보관료 500원까지 포함한 **158,303원**, 상품 범위 원가, 외화 환율, 세액 원가포함/제외, 직접배부/취소 복원, 판매 LOT 차단, Audit 실패 전체 롤백을 검증했다. Batch 2A는 SALE/Receipt/Deposit/출고를 생성하지 않았다.

## 12. DEV 최소 실제 확인

1. 검토 후 DEV SQL Server에서 Migration 최초/재실행, 기존 테이블/PK 선행검사, 한글 NVARCHAR, 신규 메뉴/사용자 권한을 확인한다. 본 Work에서는 실행하지 않았다.
2. 3종 확정 계약 선택, 자동초안/편집/확정/새 version/재조회, Master 변경 후 이전 본문, 실제 Windows PDF 저장/프린터 출력을 확인한다. 법률문구는 업무 승인본으로 교체 검토한다.
3. 계약상품 자동승계, 공급업체 별도 선택, BL/실제 날짜, 복수 LOT 분할/PK 검색 연결을 확인한다. 기존 ERP 매입/입고 화면에서 LOT 생성한 뒤 연결한다.
4. 실제 원가 기본행 수정/삭제, ± 자유항목, 통화/환율/세액/부담주체, EVENT/PERIOD 실제 결과를 입력하고 참고값과 실제값을 혼동하지 않는지 확인한다.
5. 복수 LOT WEIGHT/직접배부 합계, 실제 입고 KG, 원단위 올림 단가, Audit, 확정 후 차단·취소 복원·판매 LOT Guard를 확인한다. 수입건 CLOSED와 계약 최종마감은 구분한다.
6. 신규 메뉴 read-only 사용자/다른 회사 ID 접근 차단, 기존 매입·매출·정산·거래명세표 흐름을 간단 재확인한다. Windows 기존 한글 100행 PDF harness를 실행하고 환경 문제는 제품 PDF 장애와 분리한다.

## 13. 보증금 및 Batch 2B 연결점

기존 deposit_required/deposit_amount/deposit_memo를 계약 조건 및 계약서/수입건 참고 Snapshot에 유지했다. 보증금을 원가 차감, SALE 대금, RECEIPT로 변환하지 않았다. 단일 계약 숫자를 최종 보증금 Ledger로 간주하지 않는다.

후속 Deposit Ledger는 회사/거래처별 수취 event_id와 allocation_id를 별도 식별하고 contract_id/import_case_id(=BL 묶음)에 배정/해제/재배정/반환 이벤트를 연결해야 한다. 계약간 이동 정책·수취잔액/배정액 검증·불변 History/Audit는 2B 이후 업무확정 사항이며 이번 신규 테이블/실거래로 만들지 않았다.

Batch 2B가 이어받을 안정적인 PK: contract_id / contract_item_id / document_id+version / import_case_id / case_item_id / settlement_id+version / allocation_id / lot_id. 원가 입력은 **CONFIRMED settlement의 Snapshot**을 사용하고 CANCELLED 과거 version은 유효 원가로 사용하지 않는다.

부분출고는 기존 계약 LOT 한도·실제 LOT 재고를 확인하고 allocation.allocated_cost / actual_weight를 정확한 원가 기준으로 사용해야 한다. 계약 term/회수유형/참여·출고업체 및 향후 기간비용 발생 구간을 명시적으로 선택한다. 일일입금요청 → 입금확인 → 기존 SALE/OUTBOUND → 반복 부분출고 → 최종정산/보증금/계약 CLOSED는 이번 Batch에서 구현하지 않았다.

## 14. 남은 제한사항

- Sample 계약서로 법률 승인/전자서명/범용 Template Designer를 대체하지 않는다.
- Offer/LC/선적/검역 전체 workflow, 실제 지급·세무 회계분개, 기간 자동 계산엔진, 출고정산, 보증금 원장, 외부전송/Web은 다음 Batch다.
- 원가확정 후 접수정보/LOT 대체는 지원하지 않는다. 정정은 안전한 원가취소와 새 version으로 수행하며 과거 이력은 삭제하지 않는다. 취소한 수입건의 기본정보 재편집 기능은 이번 범위에 추가하지 않았다.
- 원가취소 후 새 version은 기본행부터 작성하므로 확정 전 실제 비용을 충분히 검토한다. 과거 원가행 자동복제/비교 편집기는 후속 UX 사항이다.
- 동일 실제 LOT를 여러 수입건의 확정 원가에 분할배부하는 정책은 지원하지 않는다. 실제 입고 양수 KG가 필요하다.
- 신설 메뉴는 기존 API의 조회 결과를 공통 검색 대화상자에서 검색한다. 대규모 서버 페이징/검색 최적화는 별도 UX 작업이다.
- Work에서는 실제 SQL Server Migration/동시성 및 Windows 프린터/신규 전체 GUI를 실행하지 않았다. 자동검증 완료와 DEV 실사용 확인을 구분한다.

## 15. 설치 단위

산출물은 하나: **MXMN_BATCH2A_CONTRACT_IMPORT_COST_7d245a0_20261006.patch**.
적용 기준은 clean 7d245a0이며 기존 Batch 1A/1B patch를 별도로 순차 적용하지 않는다. 이번 Work에서는 Migration 실행/commit/push/SERVER 변경을 하지 않았다.
