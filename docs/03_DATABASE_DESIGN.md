# MXMN DATABASE DESIGN v1.0 Candidate

> 이 문서는 목표 ERD의 테이블 그룹과 핵심 PK/FK 방향을 정의한다. 아직
> 실제 `mxmn_dev`에 일괄 적용하지 않는다. 기존 DB와 Migration Plan을
> 확인한 후 단계적으로 적용한다.

## 공통 수치 Type 기준

-   가격·단가·개별원가: 원 단위 정수 표현, 계산 소수점은 올림
-   중량: `NUMERIC(..., 2)` KG
-   BOX: `INT`
-   환율: `NUMERIC(..., 2)`
-   금액 및 환율 계산: Python `Decimal`과 SQL `NUMERIC` 사용

기존 호환 컬럼의 Scale이 더 크더라도 API 저장과 화면 표시에서 이 업무
정밀도 원칙을 적용하며, 기존 테이블을 불필요하게 변경하지 않는다.

## 1. SYSTEM

-   `tb_company`: `company_id` PK, `company_code` UNIQUE
-   `tb_user`: 내부 PK + 로그인 ID UNIQUE
-   `tb_role`
-   `tb_user_role`
-   `tb_permission`
-   필요 시 사용자-회사 접근관계 테이블

## 2. MASTER

-   `tb_partner`: 실제 사업자
-   `tb_customer`: `company_id` FK + `partner_id` FK, 회사별 업무
    거래처코드
-   `tb_product_category`
-   `tb_product`
-   `tb_service`
-   `tb_warehouse`
-   `tb_company_warehouse`: 회사별 창고 사용관계
-   `tb_warehouse_rate`: 회사별 입출고료·보관료·계근료 적용기간 이력
-   `tb_warehouse_charge`: 요율기간별 가변 비용항목과 계산기준
-   `tb_establishment`
-   `tb_tax_code`
-   `tb_code_group`
-   `tb_code_value`

### Tax

Company 자체를 과세/면세로 고정하지 않는다. Product/Service는 기본 Tax
Code를 가지며 Purchase/Sale Detail에는 실제 거래 당시 Tax Code/Rate를
Snapshot으로 저장한다.

## 3. TRADE / IMPORT

-   `tb_import_case`
-   `tb_import_offer`
-   `tb_import_offer_item`
-   `tb_lc`
-   `tb_shipment`
-   `tb_bl`
-   `tb_container`
-   `tb_import_lot_link`
-   `tb_import_document`
-   `tb_import_cost_type`
-   `tb_import_cost_template`
-   `tb_import_cost_template_item`
-   `tb_import_cost`

## 4. LOGISTICS

-   `tb_lot`
-   `tb_inbound`
-   `tb_inbound_item`
-   `tb_outbound`
-   `tb_outbound_item`

재고의 핵심 차원은
`company_id + warehouse_id + product_id + lot_id`이다. 현재고는 입출고
Transaction으로 산출하는 것을 기본으로 한다.

창고는 실제 창고의 명칭·주소·보관유형을 `tb_warehouse`에 한 번 저장하고,
업무회사별 사용 여부는 `tb_company_warehouse`로 분리한다. 창고요율은 현재
값으로 덮어쓰지 않고 `tb_warehouse_rate`의 적용 시작일/종료일 구간으로
보존한다. 실제 비용은 `tb_warehouse_charge`에 항목별로 저장하며 계산기준은
KG당, BOX당, KG·일당, 건당 정액을 지원한다. 창고마다 필요한 비용항목을
추가하거나 제외할 수 있다.

LOT에는 개별원가를 유지한다. 평균원가를 사용하지 않는다.

### LOT Master 1차 상세 (2026-09-17)

`tb_lot`은 수량 장부가 아니라 상품의 실제 입고분을 식별하고 추적하는
Master이다.

-   내부 PK: `lot_id`
-   업무 표시번호: 일반 LOT는 회사별 `LYYYYMMDD-001`, 최초재고 LOT는
    `LYYYYMMDD-HHH-DD`(기준일-최초입고 Header 순번-Detail 생성순번) 형식으로
    자동발번한다.
-   발생구분: 수입(`IMPORT`) / 국내매입(`DOMESTIC`)
-   연결: `comp_code + product_id + warehouse_id`(최초 입고 예정창고)
-   추적: 공급자 LOT번호(공급자 포장·라벨에 표시된 외부 LOT), BL번호,
    컨테이너번호, 축산물이력번호
-   속성 Snapshot: 원산지, EST NO, 생산일, 소비기한
-   평가: `individual_cost` 원/KG, LOT별 개별원가(정수 원, 소수점 올림)
-   상태: 사용중(`OPEN`) / 보류(`HOLD`) / 마감(`CLOSED`)
-   사용중지는 물리삭제하지 않고 `use_yn = 0`으로 처리

입고 BOX·KG를 `tb_lot`에 원본 수량으로 중복 저장하지 않는다. 다음
Vertical Slice에서 `tb_inbound_item`이 LOT별 입고수량을 발생시키고,
`tb_outbound_item`이 LOT별 출고수량을 차감한다. 현재고는 두 Transaction의
합계로 산출한다. 같은 BL에 여러 컨테이너가 있거나 같은 컨테이너에 여러
상품·이력번호가 있으면 LOT를 각각 분리한다.
`tb_lot.warehouse_id`는 최초 입고 예정창고이며, 창고이동 후 실제 현재고
위치는 입출고 Transaction으로 산출한다.

LOT는 독립 기초코드로 수동 생성하지 않는다. 정상 운영에서는 다음 원인
Transaction의 Detail을 저장할 때 필요한 LOT를 같은 DB Transaction 안에서
생성한다.

-   시스템 도입 시 `OPENING_INVENTORY` 최초재고 등록
-   `PURCHASE_INBOUND` 매입입고
-   `IMPORT_INBOUND` 수입입고
-   기존 LOT의 창고이동은 새 LOT 생성이 아니라 이동 Transaction으로 처리

LOT 조회·보정 화면은 이미 생성된 LOT의 추적정보 확인과 제한적 보정에만
사용한다. 연결자료가 전혀 없는 오입력 LOT만 물리삭제할 수 있고, 외래키로
연결된 LOT는 삭제하지 못하도록 DB와 API에서 차단한다.

### 시스템 도입 초기자료

다른 시스템에서 MXMN으로 전환할 때의 기준시점 자료는 일반 거래와 구분된
Opening Transaction으로 등록한다.

-   최초재고: 회사·기준일·창고 Header + 상품·LOT 추적정보·BOX·KG·개별원가 Detail
-   거래처잔액: 거래처별 미수금·미지급금과 기준일
-   금융잔액: 통장/현금 계정별 잔액과 기준일

최초재고 저장 시 `LOT + 입고 Transaction`을 원자적으로 함께 생성한다.
초기자료도 등록 이후에는 일반 입고·출고·이동·수금·지급과 동일한 원장에
포함되며, 잔액이나 현재고를 사용자가 직접 덮어쓰지 않는다.

### 초기자료등록 1차 구현 구조 (2026-09-17)

- `tb_inbound`: 회사·기준일·창고·거래유형을 가진 입고 Header
- `tb_inbound_item`: 상품·LOT·BOX·KG·개별원가·평가금액을 가진 Detail
- `tb_account_transaction`: 거래처 미수·미지급 및 향후 수금·지급 원거래
- `tb_account_transaction_allocation`: 원거래와 부분수금·부분지급의 배분 연결

최초재고는 `OPENING_INVENTORY`, 최초 미수금은 `OPENING_RECEIVABLE`, 최초
미지급금은 `OPENING_PAYABLE`로 일반 거래와 명확히 구분한다. 최초재고 저장은
입고 Header → LOT → 입고 Detail 전체를 한 DB Transaction에서 처리하여 한
단계라도 실패하면 모두 Rollback한다.

거래처 최초잔액은 단순 누적 잔액 컬럼이 아니라 각각 독립된 원거래로
생성한다. 향후 `RECEIPT`·`PAYMENT` 거래를 만들고 Allocation에 배분 금액을
저장하면 한 최초잔액에 여러 번 부분수금·부분지급하거나 한 수금·지급을 여러
원거래에 나누어 연결할 수 있다. 미결잔액은 `원거래금액 - 배분합계`로
산출한다.

### 소비기한 자동계산

상품 Master에 `expiry_rule`과 `shelf_life_days`를 둔다.

- `AUTO`: `PC004 냉장구분`이 냉장이면 상품별 예외규칙을 사용하고, 별도
  냉장정보가 없는 일반 수입육은 냉동 기본값인 생산일 + 2년 - 1일
- `FROZEN_2Y`: 냉장구분과 관계없이 생산일 + 2년 - 1일
- `DAYS`: 생산일 + 상품별 지정일수 - 1일
- `NONE`: 자동계산하지 않음

냉장 우육·돈육 또는 특정 브랜드처럼 별도 규칙이 있는 상품은 상품 Master의
`DAYS`와 지정일수로 관리한다. 최초재고 화면에서는 생산일만 입력하고,
소비기한과 상품의 원산지·EST는 저장 시 상품 Master에서 자동 적용한다.

## 5. MONEY

-   `tb_purchase`
-   `tb_purchase_item`
-   `tb_sale`
-   `tb_sale_item`
-   `tb_receipt`
-   `tb_receipt_allocation`
-   `tb_payment`
-   `tb_payment_allocation`
-   `tb_tax_document`

Purchase/Sale와 Inbound/Outbound는 분리한다.

## 6. FINANCING

-   `tb_fin_contract`
-   `tb_fin_contract_term`
-   `tb_fin_contract_lot`
-   `tb_fin_release`
-   `tb_fin_release_item`
-   `tb_fin_release_calc`

계약번호는 시스템 내부 PK와 분리된 UNIQUE 업무번호로 자동 생성한다.
계약조건 변경은 과거 조건을 덮어쓰지 않고 유효기간별 Segment/Term으로
관리한다.

## 7. COMPLIANCE

-   `tb_meatwatch_batch`
-   `tb_meatwatch_tx`

ERP 입출고가 원천이며 외부 API 전송 상태는 별도 관리한다.

## 8. REPORT / SYSTEM SUPPORT

-   `tb_report_template`
-   `tb_report_template_item`
-   `tb_number_sequence`

## 9. 기존 models.py와의 주요 차이

현재 모델의 `Company.comp_code` PK는 목표 구조에서 내부 `company_id`
PK + 업무용 `company_code` UNIQUE로 전환한다.

현재 `Account`는 장기적으로 `Partner + Customer` 구조로 분리한다.

현재 `Product.category`, `origin`, `tax_type` 문자열 직접저장은
Master/FK 중심으로 정규화한다.

현재 `SlipHeader/SlipDetail` 하나로 매입·입고·매출·출고·파이낸싱을
통합한 구조는 목표 구조에서 Purchase/Inbound/Sale/Outbound/Financing으로
역할을 분리한다.

현재 `SlipHeader.tax_type`처럼 Header 전체를 하나의 Tax로 고정하지
않는다.
