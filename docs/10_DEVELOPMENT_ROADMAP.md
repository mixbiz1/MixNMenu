# MXMN DEVELOPMENT ROADMAP

## Phase 0 --- Baseline Freeze

공식 설계문서를 프로젝트 `docs/`에 저장하고 이후 AI 작업의 기준으로
사용한다.

## Phase 1 --- Codebase Gap Analysis / Migration

현재 실행 코드와 목표 Domain/ERD를 비교하여 KEEP / REFACTOR / MOVE / NEW
/ ARCHIVE로 분류한다. 기존 프로그램을 깨뜨리지 않는 Migration 순서를
확정한다.

## Phase 2 --- Vertical Slice #1: Multi-Company

현재 `comp_code="00001"` 고정구조를 제거하고 복수 법인을 지원한다.

완료기준: - `company_id` 기반 내부 식별 - 회사
목록/선택/신규/수정/저장 - 기존 로그인과 메인화면 정상 - 법인 A/B를 각각
저장·조회 가능 - DB Migration 검증 - Git Commit

## Phase 3 --- User / Permission

사용자별 회사 접근 및 메뉴권한을 구현한다.

## Phase 4 --- Common Code / Master

공통코드 → Partner/Customer → Product/Category/Brand/Origin/EST/Tax →
Warehouse → ExpenseCode 순으로 구축한다.

2026-09-17 현재 공통코드·거래처·상품·창고·LOT·초기자료 1차와 계층형
경비코드 Master를 구현하였다. 경비코드는 향후 매입·매출·경비 Detail 및
손익계산서 Report와 연결한다.

## Phase 5 --- LOT / Logistics

Inbound → LOT → Inventory → Outbound를 구현한다. BX/KG, BL번호,
이력번호, 원산지, LOT 개별원가를 추적한다.

## Phase 6 --- General Distribution

Purchase, Sale, Receipt, Payment, Allocation, 미수/미지급을 End-to-End로
구현한다.

## Phase 7 --- Import

Offer → LC → Shipment/BL → 입항 → 보세 → 검역 → 통관 → 수입원가 →
직수입입고/LOT를 구현한다.

## Phase 8 --- Financing

수입대행, BL양수도, 국내매입 계약과 자동 계약번호, 계약조건 이력,
부분출고, 이자/수수료/창고료 등 계산을 구현한다. 기존 Excel 결과와
대조한다.

## Phase 9 --- Reports

거래명세표, LOT 수불원장, 재고, 거래처원장, 수입원가표, 계약 정산서,
세무자료 등을 구현한다.

## Phase 10 --- MeatWatch / External Integration

기간별 신고대상 조회, 일괄전송, 응답/오류/재전송 이력을 구현한다.

## 반복 작업 방식

`GPT 분석/수정 → 사용자 VS Code 실행 → 화면/오류 캡처 → GPT 검증/수정 → 정상 확인 → Git Commit → 다음 기능`

사용자는 코드 자체보다 실제 육류유통 업무 적합성을 검증한다.
