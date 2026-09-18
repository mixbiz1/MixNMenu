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

2026-09-18 사용자등록과 사용자별 업무회사 접근, 프로그램 메뉴별 CRUD 권한,
서명 Token 및 FastAPI 공통 권한검사를 구현하였다. 최초 Migration은 기존
활성계정의 전체 접근을 유지하고 관리자 1명을 지정한다. 후속 거래 화면은 같은 메뉴코드와
HTTP Method 권한검사를 사용하고 작성자·수정자 Audit을 추가한다.

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

## 현재 기준 권장 잔여 구현 순서 (2026-09-18)

1.  **사용자·권한 마감 (완료)**
    - 사용자별 업무회사 접근, 메뉴 CRUD 및 API 공통검사 완료
    - 거래 저장 시 작성자·수정자 Audit은 거래 공통기반에서 적용
2.  **거래 공통기반 및 누락 Master**
    - 전표번호·상태·확정/취소·회계기간 기준
    - 세금코드/세율 Snapshot, 용역코드, 금융계좌/결제수단
    - 거래에서 경비코드 최하위 `INPUT`만 선택
    - 2026-09-18 1차 완료: 동시성 안전 발번, 회계기간 마감, 전표 상태/Audit
      공통규칙, 세금코드·세율 Snapshot 기반, 최하위 INPUT 조회/검증
    - 후속 분리: 용역코드는 용역매출 단계, 금융계좌·결제수단은
      수금·지급 Allocation 단계에서 실제 화면과 함께 구현
3.  **일반 매입 → 입고 → LOT → 재고조회**
    - 매입과 실제 입고를 분리하고 부분입고 지원
    - 최초재고 원장과 합산되는 회사·창고·상품·LOT 재고검증
4.  **일반 매출 → 출고 → 재고차감**
    - 부분출고·반품·창고이동
    - LOT의 BL·이력번호·원산지를 거래명세표까지 승계
5.  **미수/미지급 → 수금/지급 Allocation**
    - 매입·매출 확정 시 원거래 채권/채무 자동 생성
    - 부분수금·부분지급·다수전표 일괄배분
    - 임의 미수/미지급 입력은 초기잔액·조정전표로 제한
6.  **일반 수입관리**
    - Offer → LC → Shipment/BL/Container → 통관 → 수입원가
    - 통관 완료 후 일반 입고·LOT·재고 흐름에 연결
7.  **파이낸싱/계약판매**
    - 수입대행·BL양수도·국내매입 계약
    - 조건 이력, 반복 부분출고, 이자·수수료·창고료 계산 Snapshot
8.  **전자(세금)계산서 및 출력**
    - 매입·매출 원거래 기준 발행대상·공급가액·세액 연계
    - 전자계산서 사용자/인증·전송 이력은 Core 거래와 분리
9.  **조회·보고서·외부연동 확장**
    - 각 Vertical Slice마다 검증용 조회화면은 함께 구현
    - 최종 통합조회, 손익, LOT 수불, 거래처원장, 수입원가, 계약정산
    - MeatWatch 신고/재전송 및 문서연결
10. **환경설정·프린터·배포 마감**
    - 회사별 기본값, 번호정책, 출력양식, 프린터 설정
    - 백업/복구·로그·성능·권한·PyInstaller 배포 점검

조회화면은 마지막에 한꺼번에 만드는 것이 아니라 각 거래 단계의 저장결과를
검증할 최소 조회를 함께 만들고, 9단계에서 여러 업무를 합친 경영보고서로
확장한다. 프린터설정과 환경설정은 현재 보류하며 출력·배포 단계에서 진행한다.
