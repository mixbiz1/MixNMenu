# MXMN 1차 목표 집중 개발 — Financing 출고 연결

## 기준과 판정

시작 GitHub main `0ee33956d66ccdfb87e71d0bc339a71319970b7d`, clean 별도 worktree. 기존 문서 00/04/08/10/11/13~20 및 실제 API/ORM/GUI/테스트를 확인했다. 오래된 Roadmap의 미구현 표기는 현재 코드를 우선하여 판정했다. MXMN_FinSales 신규개발/변경 없음.

**일반유통 기반 및 이번에 명시한 Financing 지원 경로의 자동검증 완료. 전체 Financing을 포함하는 1차 목표는 아직 미완료다.** 미지원 비용·회수·최종마감 기능을 완료로 간주하지 않는다. Work는 Linux이며 MXMN-DEV/SERVER Windows나 운영 DB에 접속/배포한 결과가 아니다.

## 범위별 구현 확인

| 범위 | 현재 판정 / 재사용한 코드·검증 |
| --- | --- |
| 사용자·회사·권한·공통코드 | 기존 구현. main/permissions, permissions/trade_common 회귀 |
| 거래처·상품·창고 Master | 기존 CRUD/검색. 공통 Lookup, 회사격리, API 코드 및 기존 GUI 회귀 |
| 매입 → 입고 → LOT → 매입채무 | 기존 구현. purchase/batch1b/trade_flow_integrity |
| 재고·수불·창고/상품/LOT 집계 | 기존 구현. inventory_projection/inventory_gui |
| 일반매출 → OUTBOUND → 채권 | 기존 구현. sales_outbound/sales_gui |
| 입금·지급/FIFO | 기존 구현. receipts/payments 및 trade_flow_integrity |
| 거래처원장·원전표 이동 | 기존 구현. account_ledger, 안정적인 source_type/source_id 유지 |
| Financing 계약·조건·상품/LOT | 기존 Phase 1 구현 재사용. 원계약 기본정보 수정금지 유지 |
| 계약서 5종·재작성·PDF | 기존 V1 유지. DRAFT 출력/한글/A4/과거 Snapshot 회귀 통과 |
| 실제 수입원가·배부 | 기존 Batch 2A 재사용. CONFIRMED 원가 allocation Snapshot을 출고 원금으로 승계 |
| Financing 출고정산/입금요청 | **신규 구현**, 지원 조건은 아래에 한정 |
| 실제 출고업체 채권·추가약정 | **신규 SALE 연결 및 서명된 추가 약정 등록/철회 경로**, 과거 확정문서 자동 변경 없음 |
| 보증금·최종정산·CLOSED | 미구현. 재고 0만으로 자동 마감하지 않음 |
| 거래처 Web/전송/전자계산서/MeatWatch 전체연동 | 후속 범위. 이번 핵심 흐름과 분리, 완료로 보고하지 않음 |

## 실제 신규 흐름

`확정 계약 + 실제 확정 원가/LOT → 출고정산 DRAFT → 입금요청 CONFIRMED → 은행입금확인 PAID → SALE/OUTBOUND/채권 SHIPPED → 기존 RECEIPT FIFO → 원장/재고/거래명세표`

- 새 메뉴 `9 → 5.출고정산/입금요청`, 권한 `FINANCING_RELEASE`.
- `9 → 6.특별출고약정`은 기존 FINANCING_CONTRACT 권한 사용.
- 계약·업체·상품·LOT·원가/조건은 앞 단계에서 승계한다. 출고 수량은 해당 거래의 실제 Box/Kg를 입력한다.
- 원금은 **allocation Snapshot.allocated_cost / actual_weight × 출고 KG**다. 반올림된 LOT 단가를 정확한 배부총액으로 오인하지 않는다.
- 이자 시작일은 계약 값 또는 근거가 기록된 실제 기산일. 확정 계약 Header를 강제로 수정하지 않는다. 연 기준 365/366은 운영자가 약정을 확인하여 입력한다. 기산일·연 기준은 반복 출고에서 자동 승계하고 임의 변경을 차단한다.
- 이자일수는 시작/종료 포함. 1·2차 약정율과 각 적용일수로 분할하며 지원 기간 밖은 차단한다.
- 보관료는 실제 수입접수 입고일~출고일을 포함하여 계산한다. 계약 비용행의 단위·세무·부담주체를 검증한다. NULL/default 0을 합의된 0원으로 대체하지 않는다.
- 회수유형은 ALL_IN / EXCLUDE_BROKERAGE / EXCLUDE_BROKERAGE_STORAGE / COST_ONLY. 모두 같은 ERP SALE 경로를 사용한다.
- 비영(非零) 자동 비용은 면세·계약업체/실제 출고업체 부담인 지원 항목만 합산한다. 과세/별도청구/다른 부담주체/미지원 추가비용은 묵살하지 않고 차단한다.
- ± 수동 항목은 근거가 있는 **면세상품 가격조정**만 지원한다. 과세 서비스 비용을 면세 상품에 몰래 합산하지 않는다.
- 최종 원/Kg 단가 및 공급가액은 기존 ERP 원단위 올림. 정확한 항목합계와 단가 올림 차이는 Snapshot/GUI에 표시한다.
- DRAFT를 저장한 뒤 수정하는 API는 만들지 않았다. 오류 정정은 취소 → 새 요청키로 생성하며 과거 Snapshot은 보존한다.

## 무결성 / 기존 정책 보호

- 계약 LOT 누적 출고 및 확정 예약, 다른 계약의 미출고 배정량, 실제 LOT 잔량을 검사한다. 같은 전표의 동일 LOT 여러 행을 합산한다.
- 계약/LOT/정산/매출에 SQL Server UPDLOCK/HOLDLOCK을 사용한다. 일반 SALE도 같은 LOT 잠금에 참여하도록 보강했다. 실제 SQL Server 경합/교착 부하 검증은 별도다.
- 생성 요청키는 회사별 UNIQUE. 동일 입력 재요청/재출고는 기존 결과이며 다른 입력으로 같은 키를 재사용하면 차단한다.
- 입금확인은 실제 은행 근거+요청 전액이며 **RECEIPT 전산등록을 Hard Guard로 삼지 않는다**. 자동 RECEIPT를 중복 생성하지 않는다. 같은 입금확인 재시도는 Audit 중복 없이 같은 결과다.
- 출고 시 업체 상태, 특별약정/적용일, 원가 취소/단가 변경, 재고, 회계기간, 세무금액 및 세무속성을 다시 검사한다.
- 기존 `_save_sale`을 공용 내부 함수로 사용하고 Financing 트랜잭션 내부에서는 commit하지 않는다. 뒤 단계 오류라도 SALE/OUTBOUND/채권/Audit/계약 ACTIVE 전환이 모두 rollback된다.
- 최초 출고 시 계약을 ACTIVE로 진행시키고 Audit 기록. 취소해도 이력을 삭제하거나 자동 CLOSED 처리하지 않는다.
- 실제 출고업체가 SALE.account_id / SALES_RECEIVABLE.account_id / RECEIPT / 거래명세표 고객이다. 최초 계약업체의 책임을 실제 출고자 ID로 바꾸지 않는다.
- 연결 SALE은 일반 화면에서 직접 수정/취소하지 못한다. Financing 취소 경로에서 기존 수금 allocation Guard 및 재고/채권 복원을 재사용한다. 이미 입금 배분이 있으면 취소를 차단한다.
- 일반매출의 마이너스 재고/예외사유 정책은 유지한다. 이번 Financing에는 마이너스 재고 예외출고를 추가하지 않았다.
- 확정 계약서, 원가 및 출고 Snapshot은 Master/템플릿 변경으로 재계산하지 않는다.

## 서명된 특별출고약정

기존 참여업체의 확정 후 일반 편집 금지는 그대로다. 별도 `financing-special-shippers` 경로로 **확정/진행 계약에 실제 서명된 추가 약정**을 등록한다. 근거·확인일·적용일·연대책임 수취 확인이 필수다. 역할은 AUTHORIZED_SHIPPER로 고정하며 최초 계약업체는 대체하지 않는다.

기존 tb_fin_contract_participant를 재사용하고 CREATE Audit에 근거 memo를 보존한다. 철회는 ACTIVE→INACTIVE 및 REVOKE before/after/reason이며 서명 근거와 과거 계약서 Snapshot은 덮어쓰지 않는다. 철회 후 미출고 요청은 출고 시 차단한다. 철회된 업체의 재승인/다중 약정 Version이나 법률문구 자동작성은 이번 범위가 아니다. 실제 서명문서 확인은 권한자가 수행하며 시스템은 그 확인 근거를 기록한다.

## DB / Migration

새 테이블 **tb_fin_release 1개**: 회사/계약/실제업체/출고일/요청키/상태/고정 Snapshot/총액/SALE FK/입금확인 근거·사용자·일시/Audit용 사용자·일시. 기존 ERP 테이블에 새 컬럼을 추가하지 않는다.

`db_financing_release_migrate.py`는 기존 Batch 2A SQL Server 패턴을 사용한다. 실제 ORM FK 대상 및 컬럼을 먼저 검사하며, CREATE TABLE/각 INDEX/메뉴 등록을 개별 guarded batch로 실행한다. NULL sale_id는 다수 초안이 저장되도록 **WHERE sale_id IS NOT NULL인 UNIQUE filtered index**를 사용한다. 전체 UNIQUE(sale_id)로 SQL Server에서 두 번째 초안이 실패하는 구조를 피했다. 사용자 권한을 일괄 부여하지 않는다.

Migration 자동검증은 DDL/FK/조건별 index/별도 batch/재실행 SQL 및 SQLite FK 상태 검증이다. **실제 SQL Server Migration 실행·운영 데이터 변경은 하지 않았다.**

## 검증 결과

- 시작 baseline: 327 passed, 1 warning.
- 신규 출고/약정/마이그레이션 회귀: 39개.
- 관련 선택: 117 passed, 1 warning.
- 전체 pytest: 366 passed, 1 warning.
- warning은 기존 Starlette/httpx deprecation.
- pip check / Python compile / UTF-8 / git diff --check 통과.
- 3 계약유형, 복수 LOT/창고, Box=0 중량전용, 반복 부분출고, 실제 업체 채권, FIFO 및 거래명세표 수치 일치 확인.
- GUI 어댑터가 실제 API로 초안/확정/입금확인/출고/추가약정/철회를 실행했다. 실제 Windows GUI/프린터 및 중앙 DB 검증과 구분한다.
- 실패 사례: 늦은 Audit 오류까지 포함한 전체 rollback, 가격은 같아도 세무속성 변경 시 차단, 미확정·과세·기간 밖·타 계약 배정·미확인/철회 약정·LOT override 차단 등.

## 미완료 우선순위

**P0/P1 — 전체 1차 마감을 위해 남은 핵심 지원**:

1. 과세 서비스/혼합 세무 및 별도 청구법인의 비용·수수료 거래 연결. 현재 면세 상품 SALE에 임의 합산하지 않는다.
2. 기간 중 조건변경, 2구간 이후 이자, 연장 수수료의 잔존원가 회수, LOT override, 이미 원가에 포함된 PERIOD 비용의 중복 없는 구간별 계산 및 월별 기청구 관리.
3. 자유형 및 이자형 원가반품/경영승인 이후 실거래 연결.
4. 원가확정 배부 없이 기존 국내매입 LOT만 사용하는 Financing 원가기준. 이번 지원은 3유형 모두 **CONFIRMED 실제 원가 allocation이 있는 경우**다.
5. 보증금 Ledger/분산배정/반환·재배정 및 최종정산/CLOSED. deposit_amount는 조건이며 실수취금이나 자동 차감으로 간주하지 않는다. 재고 0이나 이번 입금확인만으로 계약 마감을 선언하지 않는다.
6. 고정 평균중량/최종 잔량 자동입력, 입금요청 정식 PDF, 계약별 수금 배분·기청구 정산 고도화. 현재 실제 Box/Kg 입력, GUI 입금요청과 기존 SALE 거래명세표를 사용한다.

P2: 고급 디자인/통계/전송센터/거래처 Web/자동 외부신고. 이번에 추가하지 않았다.

## DEV/SERVER 적용 순서 — 운영 변경은 사용자가 수행

1. 운영 DB 백업 및 API 유지보수 중지. DEV와 SERVER에서 `git pull --ff-only origin main` (변경 작업트리는 강제로 reset하지 않는다).
2. **SERVER의 올바른 mxmn_dev 설정/venv**에서 `python db_financing_release_migrate.py` 실행. 중앙 DB 한 곳에 적용하며 DEV에서 별도 운영 DB를 중복 변경하지 않는다. 필요하면 같은 명령 재실행으로 멱등성을 확인한다. 사전 FK 검사 실패 시 중단하고 다른 테이블명을 추측하여 치환하지 않는다.
3. SERVER API 재시작, DEV GUI 재시작. 일반 사용자에게 필요한 FINANCING_RELEASE 권한을 기존 권한관리로 부여한다. 관리자는 기존 관리자 정책을 사용한다.
4. 기존 일반매출 생성/수정/취소도 새 연결 Guard를 읽으므로 **Migration 성공 전 새 API를 운영하지 않는다**.
5. 먼저 테스트 거래로 아래 최소 GUI 사례를 확인하고 실제 계약으로 확장한다. 기존 실계약을 테스트용으로 취소하거나 데이터 값을 덮어쓰지 않는다.

최소 GUI 확인:

- 원가확정/계약 LOT가 있는 테스트 계약, 명시적 요율·세무·부담주체·은행계좌를 준비한다. 계약서 문구 수정만으로 계약조건 숫자가 변경되지는 않는다.
- 확정 후 B업체를 추가하려면 특별출고약정 화면에서 서명 근거/날짜/연대책임 수취 확인을 등록한다.
- 출고정산에서 계약/실제 업체/실제 수량·날짜·기산 근거·연 기준일수를 입력, 계산 항목/올림 차이를 검토한다.
- 은행입금 확인 전 출고 차단 → 실제 은행 근거/금액 확인 → SALE 생성 → 연결 매출 열기. B업체 채권·LOT 감소·거래명세표 고객과 금액을 확인한다.
- 기존 입금관리에서 실제 수금 등록 후 FIFO/거래처원장을 확인한다. 선입금/기존 미수와 함께 쓰는 경우 기존 FIFO 및 순잔액 정책을 따른다.
- 반복 부분출고에서 기산일/연 기준 승계 및 잔량을 확인한다. 후속 수금이 없는 테스트 출고 취소는 재고/채권 복원, 수금 배분된 출고는 Guard 차단을 확인한다.
- 새 미지원 조건 오류는 임의로 우회하지 않는다. 실제 SQL Server/Windows 운영 GUI 결과를 추가 기록한 뒤 전체 1차 완료를 판정한다.

변경 파일: models.py, main.py, permissions.py, financing_contract_routes.py, financing_release_routes.py, db_financing_release_migrate.py, views/financing_release.py, views/mxmn_main_window.py, 신규 테스트 2개, docs/04 및 이 문서. 검증 후 commit/GitHub main 반영; 최종 SHA는 최종 보고에서 확인한다. 실제 SERVER 배포/DB Migration/개별 실계약 조작은 수행하지 않았다.
