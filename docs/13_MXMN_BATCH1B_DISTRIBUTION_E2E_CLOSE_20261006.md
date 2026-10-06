# MXMN Batch 1B — 일반유통 E2E 검증 마감

작성일: 2026-10-06

## 기준과 작업 범위

- Repository: `mixbiz1/MixNMenu`, branch: `main`.
- 공식 Source of Truth: `4789d73806a646107c2afe42cf351353be21c40b`.
- Commit: `4789d73 feat: add trade statement and shared lookup batch 1a`.
- origin/main fetch 후 위 commit의 별도 clean worktree에서 시작했다. 이전 Batch 1A 변경 작업공간을 기준으로 삼지 않았다.
- 실행 환경: Work Linux / Python 3.12 / PySide6 offscreen / 격리 SQLite. MXMN-DEV나 SERVER에서 실행한 결과라고 주장하지 않는다.
- 필요한 Python 런타임 라이브러리는 설치된 venv에서 import 및 baseline 실행으로 확인했다. 한글 PDF 테스트용 Work 나눔고딕 환경을 재사용했다.
- 실제 DB Migration, commit, push, SERVER 변경은 수행하지 않았다.
- 제품 기능·Schema·PDF 폰트 정책 변경 없음. 테스트와 이 문서만 추가했다.

## 판정

**Work의 일반유통 자동 E2E 검증 범위는 완료했다. DEV 실데이터·GUI 종합검증을 포함한 운영 마감은 미완료다.**

완료 근거는 전체 pytest 통과만이 아니라, 아래 연속 HTTP 시나리오에서 실제 ORM 저장값, FIFO allocation, 원장, LOT 수불, 세 종류 재고집계, SALE 및 발행 Snapshot을 수량과 금액으로 대조하여 설명되지 않는 차이가 없음을 확인한 것이다.

사용자 제공 DEV 검증은 Batch 1A 거래명세표 미리보기와 실제 PDF 저장에 대한 증거로 이어받았다. 일반유통 전체 흐름의 DEV 실사용 검증으로 확대 해석하지 않는다.

## 실제 데이터 연결

| 단계 | 기존 모델/API와 연결 |
|---|---|
| 거래처/상품 | Account / CompanyAccount / Product / CompanyWarehouse. 테스트에서 사용 가능한 Master와 회사 연결을 준비한다. |
| 매입 | POST `/companies/{comp_code}/purchases`, Purchase(`tb_purchase.purchase_id`) + PurchaseItem. 상품 Master의 세무구분으로 거래 세금 Snapshot을 만든다. |
| 입고/LOT | `_materialize_purchase`가 창고별 Inbound와 행별 Lot/InboundItem을 생성. PurchaseItem의 `lot_id`, `inbound_item_id`로 연결한다. |
| 매입채무 | AccountTransaction의 `PURCHASE_PAYABLE`. `comp_code + purchase_no(transaction_no)`로 해당 매입전표와 연결하고 원금은 매입 총액이다. |
| 지급 | POST/PUT/DELETE `/payments`. AccountTransaction의 PAYMENT, AccountTransactionAllocation의 source/settlement PK를 이용해 기존 FIFO 반제를 수행한다. |
| 매출/출고 | POST `/sales`가 Sale(`tb_sale.sale_id`)를 CONFIRMED로 저장. SaleItem의 기존 LOT를 OutboundItem이 `sale_item_id`로 참조한다. 창고별 Outbound를 생성한다. |
| 매출채권 | AccountTransaction의 `SALES_RECEIVABLE`. `comp_code + sale_no(transaction_no)`로 SALE과 연결한다. |
| 입금 | POST/PUT/DELETE `/receipts`. RECEIPT 원거래와 PK 기반 FIFO allocation을 저장한다. |
| 원장 | `/account-ledger`. AccountTransaction에서 순잔액을 계산하며 원전표의 source_type/source_id를 제공한다. 매입/매출은 전표 PK, 입금/지급은 원거래 PK이다. |
| 재고/수불 | `/inventory`의 LOT/PRODUCT/WAREHOUSE 집계와 `/inventory/lots/{lot_id}/transactions`. 동일한 InboundItem/OutboundItem 합계를 사용한다. |
| 거래명세표 | `/sales/{sale_id}/statements`. TradeStatement의 Sale FK와 발행 Snapshot. 원 SALE 값 자동승계, 과거 version 보존. |
| Audit | 동일 업무 transaction에서 CREATE/CONFIRM/UPDATE/CANCEL/DELETE/ISSUE를 저장. 수정·취소 사유와 before/after를 검증한다. |

원장과 LOT 수불의 GUI 원거래 이동은 기존 `open_account_ledger_source(source_type, source_id)` 및 각 화면의 `open_source_id`를 재사용한다. 전표번호 문자열 재검색을 도입하지 않았다. 새 HTTP E2E에서 생성된 전표의 실제 PK를 API source_id와 대조했고, 기존 GUI 회귀에서 네 가지 원거래 dispatch 및 LOT 수불 더블클릭을 확인했다.

## 연속 Scenario A — 실제 저장값 대조

Master 준비: 매입처 account_id=2, 매출처 account_id=1, 상품 2종, 창고 2곳. 정상 시나리오는 매입처와 매출처를 분리하여 개별 채무/채권 등식을 직접 검증한다.

### 매입과 입고

한 매입전표에 3개 행을 등록하며, API가 3개 LOT와 창고별 입고전표 2개를 생성한다. 테스트에서 매입 파생자료를 직접 만들어 우회하지 않는다.

| 행 | 상품/창고 | BOX | KG | 단가 | 공급가액 | 세액 | 합계 |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 상품1 / 창고1, 면세 | 10 | 100.00 | 1,000 | 100,000 | 0 | 100,000 |
| 2 | 상품1 / 창고2, 면세 | 4 | 40.00 | 1,000 | 40,000 | 0 | 40,000 |
| 3 | 상품2 / 창고1, 과세 | 5 | 50.00 | 2,000 | 100,000 | 10,000 | 110,000 |
| 합계 | 3 LOT / 2 창고 | 19 | 190.00 | | 240,000 | 10,000 | 250,000 |

- 매입전표 총액 = PURCHASE_PAYABLE 원금 = 250,000원.
- PurchaseItem의 LOT 및 입고행 PK, 상품, BOX/KG가 실제 InboundItem과 일치한다.
- 지급 70,000원은 해당 채무 원거래에 배분되고 미지급은 180,000원이다.
- 지급 allocation이 있는 매입의 수정/취소는 차단된다. 실패 전후 전체 업무행과 Audit이 동일함을 확인한다.

### 매출과 출고

위 매입이 생성한 세 LOT를 그대로 사용한다. 한 SALE에 BOX+KG 2개 행과 BOX=0 중량전용 1개 행을 포함한다.

| 행 | 원 매입 LOT | BOX | KG | 단가 | 공급가액 | 세액 | 합계 |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | LOT1 | 2 | 20.00 | 1,500 | 30,000 | 0 | 30,000 |
| 2 | LOT2, 중량전용 | 0 | 5.50 | 1,500 | 8,250 | 0 | 8,250 |
| 3 | LOT3 | 1 | 10.00 | 2,500 | 25,000 | 2,500 | 27,500 |
| 합계 | | 3 | 35.50 | | 63,250 | 2,500 | 65,750 |

- SALE 총액 = SALES_RECEIVABLE 원금 = 65,750원.
- OutboundItem의 sale_item_id, lot_id, BOX/KG가 해당 SaleItem과 일치한다. 창고별 출고 Header는 2개이다.
- 입금 20,000원을 해당 매출채권에 배분하며 미수는 45,750원이다.
- 입금 배분 후 SALE 수정/취소는 차단되고 부분 변경이나 추가 Audit이 남지 않는다.

### 정산 수정/삭제와 최종 반제

- 부분 지급을 70,000 → 80,000원으로, 부분 입금을 20,000 → 25,000원으로 수정하여 allocation 합계를 확인한다.
- 두 정산을 삭제하면 관련 allocation이 없어지고 미지급 250,000원, 미수 65,750원으로 복구된다.
- 지급 70,000 + 180,000원, 입금 20,000 + 45,750원을 다시 등록한다.
- 각 원거래에서 `original_amount - SUM(allocated_amount) = 0`이다.
- 미수/미지급 요약 API와 해당 거래처원장 최종 잔액 모두 0이다.
- 원장 매입·매출 복수 상세행의 source_id는 동일 원전표 PK이다. 입금·지급 source_id는 각 정산 원거래 PK이다.
- UPDATE Audit의 before/after와 사유, DELETE Audit의 before와 삭제사유를 확인한다.

### 재고와 수불 등식

| LOT | 입고 BOX/KG | 출고 BOX/KG | 현재 BOX/KG |
|---|---|---|---|
| LOT1 | 10 / 100.00 | 2 / 20.00 | 8 / 80.00 |
| LOT2 | 4 / 40.00 | 0 / 5.50 | 4 / 34.50 |
| LOT3 | 5 / 50.00 | 1 / 10.00 | 4 / 40.00 |
| 합계 | 19 / 190.00 | 3 / 35.50 | 16 / 154.50 |

- 시작일 10/02 조회에서는 10/01 입고를 기초재고로 반영한다.
- BOX/KG 각각 `기초 + 기간입고 - 기간출고 = 현재재고`이다.
- LOT 전체 수불 delta 합계와 최종 수불잔액이 현재 LOT 재고 및 매출 가용재고 산식과 일치한다.
- PRODUCT/WAREHOUSE의 기초·입고·출고·현재수량 및 재고금액은 해당 LOT 행들의 합과 일치한다. 동일 상품이 두 창고/LOT에 존재하여 단일행 집계만 검증하지 않는다.

### 거래명세표

- 확정 SALE에서 3개 행의 상품/LOT/BOX/KG/단가/공급가액/세액/합계를 재입력 없이 발행한다.
- 각 Snapshot 행과 Header 합계가 SALE 저장값과 일치한다.
- 상품명·거래처명·회사명 변경 뒤에도 기존 Snapshot JSON 바이트와 재조회값은 동일하다.
- 중복 발행은 기존 문서 ID를 반환한다. 다른 회사 조회/발행은 차단된다.
- 발행 및 재조회가 재고·채권 반제를 다시 만들지 않는다.

## 추가 수정/취소/실패 검증

새 E2E 7건은 정상 연속 시나리오 외 다음을 포함한다.

1. 후속 거래 없는 매입의 중량 정정: LOT/입고/채무를 중복 없이 재생성. 취소 후 LOT·입고·채무 제거 및 Audit 보존.
2. 실제 출고된 LOT의 매입 수정/취소 Guard, 수금된 SALE Guard: 409 전후 전체 업무행 불변.
3. 미수금 배분 없는 SALE의 20 → 21KG 정정: 재고와 채권 67,250원으로 재전개, 거래명세표 v2 생성, v1 Snapshot 불변/SUPERSEDED 표시.
4. SALE 취소: 출고·매출채권 제거와 재고 복구. v1/v2 문서는 남고 CANCELLED 표시, 추가 발행 차단.
5. 동일 전표/동일 LOT 두 행 누적 출고(11 BOX / 105KG): 사유 없으면 차단. 예외사유를 입력하면 -1 BOX / -5KG 허용 및 Audit 기록, 취소 후 복구.
6. 매입 확정, 매출 확정, 명세표 발행의 Audit 저장 직후 의도적인 예외를 주입한다. 입출고·LOT·채권채무·문서·Audit을 포함한 전체 업무행이 실패 전 상태로 복구됨을 확인한다.

매출 취소는 SALE ITEM을 삭제하는 기능이 아니다. 취소된 SALE ITEM의 LOT FK와 이력은 남으므로, 한 번 사용된 매입 LOT 자체를 삭제하는 매입 취소는 여전히 차단된다. 이를 새 오류로 간주하거나 Guard를 약화하지 않았다. **후속 참조 없는 매입의 취소**와 **사용 이력이 남은 매입의 보호**를 별도 테스트한다.

## 발견 결함과 수정 내용

- 위 검증 범위에서 실제 제품 데이터 무결성 또는 업무 흐름 차단 결함은 발견하지 않았다. 제품 소스를 테스트에 맞춰 바꾸지 않았다.
- 기존 테스트는 개별 기능 또는 더 짧은 교차 흐름을 검증했으며, 복수 상품·창고·LOT → 정산 CRUD → 모든 재고집계 → 거래명세표까지 연결된 HTTP 검증이 부족했다. 이 검증 공백을 `tests/test_batch1b_distribution_e2e.py`로 보완했다.
- 기존 Windows PDF 성공 사례를 제품 기능의 DEV 검증으로 인정한다. QPdfWriter/PDF 폰트 코드와 기존 PDF 테스트를 변경하거나 skip하지 않았다.
- 일반유통을 막는 별도 UX 결함은 이번 검증에서 확인하지 않았다. 대규모 화면 변경을 추가하지 않았다.

## Migration 확인

기존 Purchase/Sale/Opening Data/Trade Statement Migration의 테이블·FK 구조와 실제 ORM 참조를 확인했다. 매출 원장은 dbo.tb_sale(sale_id), 출고 상세는 tb_sale_item(sale_item_id), 명세표도 tb_sale(sale_id)를 참조한다. 명세표 Migration은 ERP 선행 PK 검사와 테이블/인덱스 별도 batch 및 재실행 guard를 사용한다.

이번 변경에 DB 구조 변경이나 신규 Migration은 없다. 기존 Migration 검증은 SQL Server dialect SQL/guard/모델 일치 확인이며, SQLite create_all 또는 mock 테스트를 SQL Server 실제 Migration 성공이라고 보고하지 않는다.

## 자동검증 결과

- clean baseline 전체: **177 passed, 1 warning**.
- 신규 Batch 1B E2E: **7 passed, 1 warning**.
- 관련 선택(Purchase/Audit/Sale/GUI/Receipt/Payment/Ledger/Inventory/Batch 1A/Financing): **159 passed, 1 warning**.
- 최종 전체 pytest: **184 passed, 1 warning**.
- Python compile: 통과.
- git diff --check: 통과.
- clean `4789d73` 별도 작업공간에서 최종 patch `git apply --check`: 통과. 실제 적용 후 작성 소스와 바이트 일치를 확인했다.
- warning: 기존 Starlette/httpx deprecation. 기능 실패가 아니다.

선택 및 전체 테스트에서 기존 GUI Drill-down, Financing Phase 1/Migration, 입출금 FIFO/음수 조정/선수선급 및 거래명세표 회귀를 포함한다. 한글 100행 다중페이지 PDF 기존 테스트도 통과했으며, 제품 렌더러는 변경하지 않았다.

## 남은 제한사항 / DEV 최소 확인

자동 E2E는 SQLite의 FK를 켠 격리 DB에서 실제 API/ORM/transaction을 사용한다. SQL Server 전용 발번은 기존 fixture의 대체 발번을 사용하므로 실제 SQL Server 잠금·동시 발번·동시 FIFO 배분 검증은 아니다. 실제 DB와 SERVER에는 연결/변경하지 않았다. 거래처 Master 준비는 fixture로 수행했으며 Master 등록 GUI 자체의 실사용 승인을 대신하지 않는다.

겸업 거래처의 요약 API/원장은 기존 **순잔액 정책**을 따른다. 같은 거래처에 매입과 매출이 함께 있거나 선수/선급이 있으면 전체 순잔액은 개별 매출채권/매입채무 allocation 잔액과 다를 수 있다. 별도 거래처의 정상 시나리오에서 위 등식을 직접 검증하고, 기존 교차 흐름 회귀에서 겸업·선수/선급 정책을 유지했다.

DEV에서 운영 마감을 위해 추가 확인할 최소 항목:

1. 승인된 테스트자료로 복수 상품/LOT 매입 → 두 창고 재고 → BOX=0 포함 매출 → 부분/최종 지급·입금을 연결하고 미수·미지급 및 세 종류 재고조회 값을 대조한다.
2. 거래처원장 및 LOT 수불 더블클릭으로 원 매입/매출/입금/지급이 정확히 열리는지 확인한다.
3. 후속 참조 없는 테스트 전표의 수정/취소, 후속 거래 Guard, 명세표 정정 version/과거본 재출력/취소 표시를 확인한다. Windows 한글 PDF 기본 저장 성공은 이미 확인된 사실로 취급한다.

이 세 항목의 실제 결과가 확인되기 전에는 DEV 운영 마감 완료나 SERVER 배포 완료로 표기하지 않는다.

최종 설치단위: clean `4789d73` → `MXMN_BATCH1B_DISTRIBUTION_E2E_CLOSE_4789d73_20261006.patch`. 이 패치는 테스트와 본 문서를 추가한다.
