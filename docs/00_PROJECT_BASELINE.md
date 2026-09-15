# MXMN PROJECT BASELINE

**Version:** 1.0 Candidate\
**Baseline date:** 2026-09-15\
**Project:** MXMN

## 1. 프로젝트 정의

MXMN은 육류 수입·도매유통, 정산, 파이낸싱 계약판매를 통합 관리하는
Windows ERP이다. 현행 MeatSoft/KIMS 업무와 실제 수입·유통·파이낸싱
실무를 벤치마킹하되 레거시 구조를 그대로 복제하지 않고, 중복 입력을
줄이며 확장 가능한 구조로 재설계한다.

## 2. 최상위 설계 원칙

-   복수 법인을 처음부터 지원하며 주요 Transaction은 `company_id`로 소속
    법인을 구분한다.
-   법인을 면세/과세로 고정하지 않는다. 상품·서비스 Master에는 기본
    Tax를 두고 실제 거래 Detail에는 당시 Tax Code/Rate를 Snapshot으로
    보존한다.
-   법적 사업자(Partner)와 ERP 거래처코드(Customer)를 분리하여 동일
    사업자번호에 복수 거래처코드를 허용한다.
-   Product와 LOT를 분리한다. 동일 Product라도 입고·BL·이력번호·원가가
    다르면 별도 LOT이다.
-   재고평가는 평균원가가 아닌 **LOT별 개별원가**를 사용한다.
-   재고는 `Company + Warehouse + Product + LOT` 차원에서 입출고
    Transaction으로 산출한다.
-   `Purchase ≠ Inbound`, `Sale ≠ Outbound`, `Financing ≠ Sale`을
    원칙으로 한다.
-   BL번호와 축산물이력번호는 LOT에서 출고·거래명세표까지 자동 승계한다.
-   동일 사실은 한 번만 저장한다(One Fact → One Data).
-   수입원가 비용항목은 Column이 아니라 Row로 관리하여 가변 항목을
    추가/제외할 수 있게 한다.
-   파이낸싱은 별도 재고체계가 아니라 일반 유통·LOT 위에 계약/계산
    Layer로 구성한다.
-   계약조건 변경과 계산 결과는 이력 및 Snapshot으로 보존한다.
-   MeatWatch 신고는 ERP 입출고 원천 Transaction과 분리하여 기간별
    일괄전송/오류/재전송을 관리한다.
-   PDF 등 일반문서는 DB Binary로 저장하지 않고 외부 저장공간을 사용하며
    DB에는 연결정보와 Metadata를 저장한다.
-   동일 원천데이터에서 거래처용·세무사용·내부관리용 등 여러 Report를
    생성한다(One Data → Multiple Reports).

## 3. 기술 스택

-   Python 3.11+
-   PySide6 Pure Python UI
-   FastAPI
-   SQLAlchemy / pyodbc / Pydantic
-   MS SQL Server 2025 (`mxmn_dev`)
-   VS Code / Git / GitHub
-   향후 PyInstaller 배포

## 4. 기본 Architecture

`PySide6 Client → Client Service → HTTP → FastAPI → Business Service → SQLAlchemy → MS SQL Server`

외부 연동(MeatWatch, 문서저장, 전자세금계산서 등)은 ERP Core와 분리한다.

## 5. 수입 재고 상태

`CONTRACTED → SHIPPED → ARRIVED → BONDED_IN → QUARANTINE_DONE → CUSTOMS_CLEARED`

업무 의미: - 계약완료/선적 전 = 수입예정재고 - BL 발행/선적 = 운송중 -
국내 입항 - 보세창고 입고 - 검역완료 = 미통관재고 - 통관완료 =
판매가능재고

생산예정일·선적예정일은 필수 관리항목으로 강제하지 않는다.

## 6. Financing 계약 유형

-   `IMPORT_AGENCY` 수입대행
-   `BL_TRANSFER` BL양수도
-   `DOMESTIC_PURCHASE` 국내매입

수수료율·이자율·창고료·입출고료·계근료 등은 하드코딩하지 않고
Parameter/Contract Term으로 관리한다.

## 7. UI/개발 원칙

신규 UI는 Qt Designer `.ui` 파일이 아니라 Pure Python PySide6를 기본으로
한다. 화면 캡처 분석 → Python 구현 → 실행 → 캡처 검증 → 수정의 순서로
개발한다.

사용자가 코드를 직접 검증해야 하는 방식으로 개발하지 않는다. AI는 수정
전 관련 파일과 호출관계, 영향범위를 확인하고 수정 후에는 수정
파일/이유/영향/실행방법/정상결과를 설명한다.

## 8. 개발 방식

Vertical Slice 방식으로 하나의 기능을 DB Model → Schema → Service → API
→ Client Service → View → 저장/조회/수정 → 실행검증까지 완성한 후 다음
기능으로 이동한다.

대규모 일괄 리팩터링을 피하고
`작은 변경 → 실행검증 → Git Commit → 다음 변경`을 반복한다.

## 9. 2026년 9월 목표

전체 ERP의 완성을 의미하지 않는다. 실제 업무에 사용할 수 있는 초기버전을
목표로 Framework → Master → 일반유통 → 수입 → Financing → Report →
Integration 순으로 실행 가능한 기능을 축적한다.
