# MXMN DATABASE DESIGN v1.0 Candidate

> 이 문서는 목표 ERD의 테이블 그룹과 핵심 PK/FK 방향을 정의한다. 아직
> 실제 `mxmn_dev`에 일괄 적용하지 않는다. 기존 DB와 Migration Plan을
> 확인한 후 단계적으로 적용한다.

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
-   업무 표시번호: 회사별 `lot_code` (`LYYYYMMDD-001` 형식 자동발번)
-   발생구분: 수입(`IMPORT`) / 국내매입(`DOMESTIC`)
-   연결: `comp_code + product_id + warehouse_id`(최초 입고 예정창고)
-   추적: 공급자 LOT번호, BL번호, 컨테이너번호, 축산물이력번호
-   속성 Snapshot: 원산지, EST NO, 생산일, 소비기한
-   평가: `individual_cost` 원/KG, LOT별 개별원가
-   상태: 사용중(`OPEN`) / 보류(`HOLD`) / 마감(`CLOSED`)
-   사용중지는 물리삭제하지 않고 `use_yn = 0`으로 처리

입고 BOX·KG를 `tb_lot`에 원본 수량으로 중복 저장하지 않는다. 다음
Vertical Slice에서 `tb_inbound_item`이 LOT별 입고수량을 발생시키고,
`tb_outbound_item`이 LOT별 출고수량을 차감한다. 현재고는 두 Transaction의
합계로 산출한다. 같은 BL에 여러 컨테이너가 있거나 같은 컨테이너에 여러
상품·이력번호가 있으면 LOT를 각각 분리한다.
`tb_lot.warehouse_id`는 최초 입고 예정창고이며, 창고이동 후 실제 현재고
위치는 입출고 Transaction으로 산출한다.

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
