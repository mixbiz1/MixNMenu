# MXMN MIGRATION PLAN v1.0

## M0. 현재본 보존

-   업로드 ZIP을 2026-09-15 기준 코드 Snapshot으로 취급
-   로컬 Git working tree 확인
-   코드 변경 전 Commit/Tag 권장

## M1. 문서 Baseline 반영

이번 `docs/` 문서 세트를 프로젝트에 추가한다. 코드/DB는 아직 변경하지
않는다.

## M2. Multi-Company 설계 확정

기존 `tb_company` 실제 스키마/데이터를 확인한 뒤 Migration SQL을
작성한다. 기존 `comp_code` 데이터를 보존하면서 `company_id` 도입 방법을
결정한다.

## M3. Company API 개선

현재 `/api/v1/company`의 `"00001"` 고정 조회를 제거한다. 목표 API: -
회사 목록 조회 - 회사 단건 조회 - 신규 - 수정 - 활성/비활성 - 필요 시
현재 선택회사

## M4. Company UI 개선

현재 `CompanyRegWidget`을 활용하여 복수 회사 목록/선택/신규/수정이
가능하도록 한다.

## M5. 실행 검증

-   FastAPI 실행
-   DB 연결 확인
-   기존 로그인 성공
-   Main Window 표시
-   Company 화면 표시
-   법인 A/B 저장 및 각각 재조회
-   오류 로그 없음

## M6. Git Commit

Multi-Company Vertical Slice가 정상일 때만 Commit한다.

## M7. 다음 Vertical Slice

User/Permission → Common Code → Partner/Customer → Product/LOT/Tax →
Warehouse 순으로 진행한다.

창고 Master 1차 Migration은 `db_warehouse_migrate.py`로 실행하며
`tb_warehouse`, `tb_company_warehouse`, `tb_warehouse_rate`,
`tb_warehouse_charge`를 비파괴 방식으로 추가한다. 기존 Table/PK/FK/데이터는
변경하거나 삭제하지 않는다. 이미 1차 Migration을 실행한 DB에는 팩스·웹
접속정보 컬럼과 가변 비용항목 테이블만 추가하며 기존 고정요율 중 0이 아닌
값은 대응하는 새 비용항목으로 자동 승계한다.

초기자료등록 1차 Migration은 `db_opening_data_migrate.py`로 실행한다.
`tb_inbound`, `tb_inbound_item`, `tb_account_transaction`,
`tb_account_transaction_allocation`을 기존 테이블·데이터 삭제 없이 추가한다.
Migration 실행 후 최초재고와 거래처 최초잔액 API/화면을 사용한다.
같은 Migration을 재실행하면 `tb_product.expiry_rule`과
`tb_product.shelf_life_days`를 존재 여부 확인 후 추가하며 기존 상품과
초기자료는 변경하거나 삭제하지 않는다.

## 금지사항

-   `models.py`를 목표 ERD 전체로 한 번에 교체하지 않는다.
-   기존 테이블을 확인하지 않고 DROP/RECREATE하지 않는다.
-   운영/개발 데이터의 의미를 확인하지 않고 자동 Migration하지 않는다.
-   사용자가 여러 파일의 일부 코드를 수동 조립하도록 요구하지 않는다.
