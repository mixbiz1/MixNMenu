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

LOT에는 개별원가를 유지한다. 평균원가를 사용하지 않는다.

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
