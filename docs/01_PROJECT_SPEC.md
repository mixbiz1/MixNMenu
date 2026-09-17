# MXMN PROJECT SPEC v1.0 Candidate

## 1. SYSTEM

회사등록, 사용자등록, 로그인, 역할/권한, 메뉴접근권한을 관리한다. 하나의
시스템에서 복수 법인을 지원한다.

## 2. MASTER

핵심 Master는 Partner, Customer, Product, ProductCategory, Service,
Warehouse, Establishment(EST), TaxCode, CodeGroup/CodeValue,
ExpenseCode이다.

-   Partner: 실제 법적 사업자
-   Customer: MXMN 업무용 거래처코드
-   Product: 재고를 가지는 상품
-   Service: 재고를 가지지 않는 용역
-   LOT: Product의 실제 입고/재고 추적 단위
-   ExpenseCode: 매출·매입·판매관리비·영업외손익을 최대 4단계로 분류하는
    손익·경비통계용 계층형 코드

## 3. 일반 유통

`매입 → 입고 → LOT → 재고 → 매출 → 출고 → 수금`을 기본 흐름으로 한다.
동시에 `매입 → 미지급 → 지급`, `매출 → 미수 → 수금`을 관리한다.

매입/매출과 입고/출고는 연결하되 동일 Entity로 합치지 않는다. 분할
입고·분할 출고·반품·창고이동 등에 대응한다.

## 4. 수입

ImportCase를 중심으로 Offer, LC, Shipment, BL, Container, 수입문서,
수입원가, LOT를 연결한다.

BL 발행 이후에는 BL번호를 중심으로 입항 및 후속 진행을 추적할 수 있어야
한다.

## 5. BL / Container / LOT

기본적으로 하나의 BL에 여러 Container, 하나의 Container에 여러
상품/LOT가 존재할 수 있다. 국내 LOT도 존재하므로 LOT 자체에 수입 FK를
강제하지 않고 Import-Lot Link로 연결하는 방향을 기본으로 한다.

## 6. LOT/재고

LOT에는 상품, 원산지, EST, 생산/소비기한(해당 시), 축산물이력번호,
개별원가 등 실제 재고추적 정보를 연결한다. 재고 수량은 BX와 KG를 함께
관리한다.

## 7. 수입원가

수입원가 항목은 Row 방식으로 관리한다. 상품원금, BL원금결제, LC
관련비용, 해외수수료, 관세, 검역, 통관, 운송, 창고 등 필수·가변 비용을
실제 발생 여부에 따라 추가/제외한다. 발생일, 외화금액, 환율, 원화금액,
VAT, 원가포함여부, 설명/비고 등을 가질 수 있다.

## 8. 상품/서비스와 Tax

한 거래 Header에 Product와 Service Detail이 함께 존재할 수 있다. 각
Detail에는 거래 당시 Tax Code와 Tax Rate Snapshot을 보존한다. 따라서 한
거래에서 면세상품과 과세서비스를 함께 처리할 수 있다.

## 9. 수금/지급

Receipt/Payment와 Sale/Purchase를 Allocation으로 연결하여 부분수금, 다수
전표 일괄수금, 부분지급 등을 처리한다.

## 10. Financing

Financing은 일반 유통 LOT 위의 계약·계산 Layer이다. Contract → Contract
Term → Contract LOT → Release Request → Release Calculation →
Outbound/Sale로 연결한다. 부분출고를 반복하여 0 BOX/0 KG가 될 때까지
관리한다.

## 11. MeatWatch

입고 시 등록된 축산물이력번호는 출고까지 승계한다. 기간을 지정해
매입/매출 신고대상을 조회하고 일괄전송하며 성공/실패/재전송 이력을
보존한다.

## 12. 문서

Offer, BL, Commercial Invoice, Packing List, 검역증, 원산지증명서,
수입확인/신고서류, 계약서 등을 업무 Entity에 연결한다. 중복정보를
문서마다 다시 입력하지 않는다.

## 13. Report

거래명세표에는 법적·실무적으로 필요한 원산지, 축산물이력번호 및 BL번호가
LOT에서 자동 연결되어야 한다. 동일 데이터에서 거래처용, 세무기장업체용,
내부관리용, 파이낸싱 정산용 등 목적별 출력물을 만든다.
