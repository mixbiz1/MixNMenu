# MXMN ERP 1차 목표 — 1·2차 통합 개발 인수인계

## 0. 최종 판정: 부분완료 / 작업 종료

기준: `mixbiz1/MixNMenu` main `c9734431c61857c44fdc1b559b2462c84187d3d2`.
1차 patch 7개 파일/380개 테스트 상태를 포함한 후속 구현이다. **이번 통합 patch는 1차 patch를 포함한다. 두 patch를 중복 적용하지 않는다.**
Work에서 실제 코드·격리 API/SQLite FK·Qt GUI 어댑터·PDF·SQL Server DDL 소스 검증을 수행했다. 최종 **411 passed, 1 warning**. 2차 신규 회귀 **31개**, 최초 clean 기준 누적 45개 증가. compile 및 diff 검사 통과.
Git commit/push, 중앙 SQL Server 접속/Migration, 운영 SERVER 변경, 사용자 PC 조작은 하지 않았다. Windows GUI·실제 SQL Server Migration/잠금경합은 미검증이다.
전체 Financing 1차 목표 완료 선언은 하지 않는다. 아래 지원 경로는 구현·자동검증 완료이며, 원가반품·타법인 청구·월별 기청구 등은 Guard로 남겼다.

## 1. 구현 범위

| 항목 | 실제 지원 | 남은 제한 |
| --- | --- | --- |
| 기존 일반유통 | 사용자/권한, Master, 매입·LOT·입고, 매출·출고, FIFO, 원장/재고/Drill-down 유지 | Windows 운영 회귀 별도 |
| 1차 후속 기능 | 적용일별 이자/창고료, 국내 면세매입 원가, 입금요청 PDF 포함 | 국내 할인·과세매입 등 원가기준 미지원 |
| 혼합 과세·면세 | 면세 상품 SALE와 과세/면세 **별도 비용채권** 분리, 공급/세액/합계·증빙대상 Snapshot | 타 법인 발행, 다른 부담업체는 미확정 경로 Guard |
| 6종 출고가 | 기존 4종 + 명시적 FREE 선택 = 5종의 지원 경로 | INTEREST_ONLY 원가반품 미구현; FREE 원가 미회수는 Guard |
| 추가·할인 | 계약조건의 명시적 KG/BOX 추가비용, 면세 포함 할인, 기존 근거 필수 가격조정 유지 | 음수 별도증빙/고정비·월별 기청구 미지원 |
| 연장수수료 | Term 구간 + 명시적 추가율/차액율, 해당 부분출고 원가 기준 계산 | 잔존전체 일괄 선청구·월별 기청구·세무/청구주체 변경 Guard |
| 보증금 | 실수취, 계약 분산배정/해제/재배정, 지정 요청 충당, 잔액, 실제 반환, 취소 복원, 독립 원장/Audit | 제3자 상계·실제 반환의 단순 취소는 Guard |
| 최종정산/CLOSED | 계약/LOT/출고/채권/보증금/미청구 대사, 마감 Guard, 고정 Snapshot, 마감 이후 반제·출고 변경 차단 | 외부 증빙/초과입금 귀속은 근거 있는 권한자 확인 필수; reopen 없음 |
| GUI/PDF | 보증금·최종마감 메뉴, 원장 Drill-down, 혼합세무/충당/보증금/최종정산 A4 한글·다중페이지 | 실제 Windows/프린터, 전자계산서 자동발행 미검증/미구현 |

## 2. 혼합세무·별도청구

기존 상품 SALE/OUTBOUND는 그대로다. 과세비용을 면세 상품에 합산하지 않는다. 별도비용은 `tb_fin_charge`에 고정 청구내역을 저장하고, 동일 회사/실제 출고업체의 `SALES_RECEIVABLE` 원거래로 **한 번** 전개한다. 서비스비용으로 재고 입출고를 만들지 않는다.

- 별도비용은 상품 `FinancingRelease.total_amount` 및 상품 출고 전 입금확인액에서 제외된다.
- 출고 시 상품 SALE 및 별도 비용채권을 같은 atomic transaction에 생성한다. 늦은 오류도 전체 rollback.
- 기존 RECEIPT FIFO가 상품채권과 별도비용채권을 순서대로 반제한다. 미수 요약/거래처원장은 기존 AccountTransaction을 사용한다.
- 원장에서 비용을 더블클릭하면 `FINANCING_RELEASE` source ID로 해당 출고정산을 연다.
- 출고 취소 시 비용채권도 함께 취소한다. 수금 Allocation이 있으면 차단한다. 별도 비용에 대한 독립 금액 수정은 제공하지 않는다.
- 세금코드는 실제 출고일의 유효 코드이며 견적 이후 코드명/세율/세무구분이 변경되면 출고를 차단한다.
- 비용 공급가액은 기존 원단위 올림. **서비스 비용 VAT는 기존 Financing 수수료 정책의 항목별 원단위 절하**다. 상품 SALE의 기존 VAT/단가 계산을 변경하지 않았다.
- 증빙대상 INVOICE/TAX_INVOICE는 계산서/세금계산서 **발행 대상** 분류다. 홈택스 전송이나 법적 증빙 발행 완료를 뜻하지 않는다.

계약 Term의 기존 `conditions.expense_conditions`에 실제 약정 근거로 다음을 명시한다. 아래는 테스트 예시이며 운영 요율/법인을 확정하는 값이 아니다.

```json
{
  "expense_conditions": [
    {
      "code": "STORAGE",
      "name": "별도 창고료",
      "basis": "KG_DAY",
      "unit_rate": "0.9",
      "billing_mode": "SEPARATE",
      "issuer_comp_code": "00001",
      "payer": "ACTUAL_SHIPPER",
      "tax_treatment": "TAXABLE",
      "tax_code": "VAT10",
      "evidence_type": "TAX_INVOICE"
    }
  ]
}
```

현재 `issuer_comp_code`는 해당 API의 업무회사와 같아야 한다. 타 법인의 증빙/채권을 다른 회사 사용자 권한으로 자동 생성하지 않는다. 면세 별도비용은 실제 EXEMPT 코드 + INVOICE를 지정한다. 포함 비용은 EXEMPT와 부담주체를 유지한다. 기간 중 세무/청구방식/부담주체 변경은 기존 비용을 새 증빙으로 소급 분류하지 않고 Guard한다.

## 3. 자유형·연장·추가 비용

### FREE

`recovery_template=FREE`에서 `conditions.recovery_components`로 허용항목을 명시한다. 현재 허용: COST, INTEREST, STORAGE, INOUT, WEIGHING, BROKERAGE. 중복/미지원 항목을 거부하며 **COST 포함**이 필수다. 원가 미회수/반품을 임의 일반 SALE로 처리하지 않는다.

```json
{"recovery_components": ["COST", "INTEREST", "INOUT", "WEIGHING"]}
```

별도청구로 명시된 비용은 상품 포함항목에서 빠져도 별도비용으로 계산한다. 계약의 명시적 KG/BOX 추가비용은 INCLUDED/SEPARATE와 세무·부담주체를 지정한다. 면세 포함 음수 요율은 합의된 할인으로 보존한다. 고정비를 부분출고마다 중복 청구하거나 음수 별도증빙을 새 채권으로 만들지 않는다.

### 연장수수료

이자/창고료의 1차 구간 계산을 재사용한다. 이자 1/2차 위치는 원래 금융기산일에서의 누적 위치이며 새 Term에서 자동 재시작하지 않는다. 각 Term의 입력 기간 밖은 계속 차단한다.

수수료가 있는 새 Term은 `conditions.extension_brokerage_mode`를 실제 약정에 맞게 명시해야 한다.

- `ADDITIONAL_RATE`: 새 Term 요율 전체를 추가 수수료율로 사용.
- `INCREMENTAL_DIFFERENCE`: 이전 Term 대비 요율 증가분만 추가. 음수 차액은 수정증빙 검토가 필요하여 차단.

각 출고행의 실제 회수원가를 기준으로 최초율 + 적용된 연장율을 계산한다. 이미 출고된 수량에 다시 수수료를 부과하지 않는다. 구간별 기준원가/적용율/금액을 고정 Snapshot에 저장한다. `brokerage_prebilled=true`이면 자동 재청구를 차단한다.

이 지원은 실제 부분출고 때 각 물량의 수수료를 회수하는 경로다. 연장일에 잔존전체 원가를 일괄 선청구하는 경로, 월말 기청구/다음 달 잔여기간 청구, 2구간 밖 임의 연장, LOT override는 완료하지 않았다.

## 4. 독립 보증금 원장

새 메뉴 `9 → 7.보증금 관리`, 권한 `FINANCING_DEPOSIT`.

- 실수취: 실제 금액·입금일·소유업체·은행 고유근거·요청키를 기록한다. 계약 약정 deposit_amount를 실수취로 간주하지 않는다.
- 실수취 `DEPOSIT_RECEIPT`, 실제 반환 `DEPOSIT_RETURN`은 일반 미수/미지급 순잔액과 RECEIPT FIFO에서 제외된다. 독립 원장에서 조회한다.
- 하나의 실제 보증금을 여러 계약에 분산배정할 수 있다. 미사용 배정 해제 후 다른 계약에 재배정할 수 있다. 배정 해제가 충당된 금액까지 복원하지 않는다.
- 배정은 계약업체 또는 유효한 특별약정 출고업체의 담보만 지원한다. 적용일/확인일을 검사한다.
- 충당은 **CONFIRMED 출고정산, 입금확인 전**, 배정 계약/동일 실제 채무자에게만 가능하다. 다른 소유자의 보증금으로 제3자 채권을 자동 상계하지 않는다.
- 충당일은 배정일 이후의 출고정산일이다. 배정 잔액/요청액을 초과할 수 없다.
- 입금확인 필요액 = 상품 요청액 − 보증금 충당액. 전액 충당도 금액 0원과 명시적 상계 근거 확인 후에만 출고한다.
- 출고 시 `DEPOSIT_APPLIED` 원거래 및 기존 Allocation을 **지정 상품채권**에 한 번 생성한다. 일반 RECEIPT 실수취를 추가 생성하지 않는다.
- 일반 수금 FIFO는 충당 후 남은 미수만 반제한다. 일반 음수 RECEIPT로 보증금 충당을 되돌릴 수 없다.
- 출고취소는 일반 수금 Guard 통과 시 자신의 보증금 충당을 함께 복원한다. 실패하면 전체 rollback되므로 보증금만 풀리는 상태가 생기지 않는다.
- 실제 반환은 담보해제된 미배정 잔액만 가능하다. 실제 은행반환을 단순 취소해 잔액을 되살리는 기능은 차단한다. 다시 실제 수취한 경우 새 은행근거로 재수취 등록한다.
- 보증금 수취 정정취소는 활성 배정/충당/반환이 없어야 한다. 은행근거와 Audit는 삭제하지 않는다.
- 원장의 보증금 수취/반환/충당을 더블클릭하면 보증금 화면으로 이동한다. `/financing-deposits/{id}/history`로 Audit 확인 가능.

### 은행 중복근거

`tb_fin_bank_evidence`에 업무회사 + 정규화 은행근거를 UNIQUE로 보존하여 같은 근거를 보증금/일반입금/반환에 재사용하지 못한다. 일반 입금 GUI에 은행근거 입력을 추가했다.

**실수취 보증금이 있는 거래처의 신규 양수 RECEIPT는 은행근거가 필수다.** 보증금이 없는 거래처의 기존 입금은 호환성을 위해 선택 입력을 유지한다. 은행 연동/계좌조회는 없다. 실제 은행근거는 권한자가 확인하며, 서로 다른 문자열이 같은 은행거래인지 자동 추론하지 않는다.

## 5. 최종정산 / CLOSED

새 메뉴 `9 → 8.최종정산/계약마감`, 권한 `FINANCING_CLOSE`.

대사: 계약상품 수량 ↔ ACTIVE LOT 배정 ↔ SHIPPED 출고수량, 약정 잔량 및 실제 LOT 재고, 회수 원가/비용, 상품·별도비용 청구, 원채권별 Allocation 반제/잔액, 보증금 배정/충당/잔액, 수입원가 상태 및 미출고 요청.

다음은 마감 차단이다.

- 계약/배정/출고 수량 불일치, 약정 잔량 또는 초과수량.
- 미출고 DRAFT/CONFIRMED/PAID 요청.
- 원매출/채권 부재, 별도비용 미청구, 미수 또는 초과배분.
- 미사용 보증금 배정, 채권 미연결 충당.
- 관련 수입원가 미확정.
- 최종 출고일 또는 반제일보다 과거 마감일.

전산 차단사항이 없어도 **미청구/타법인 증빙 확인**, **은행입금/초과입금 귀속 확인**, 검토근거 및 사유가 모두 필요하다. 이 확인은 외부/비구조화 비용이 없다고 시스템이 추측하는 기능이 아니다. 확인한 권한자의 근거를 Audit/Snapshot에 남긴다.

마감 완료는 `tb_fin_closure`에 고정 Snapshot을 만들고 계약을 CLOSED 처리한다. 동일 입력 재시도는 동일 마감 결과다. 과거 Master 변경으로 최종정산을 재계산하지 않는다. 마감 후 새 출고/취소/조건변경/배정 및 연결된 RECEIPT 수정·삭제·음수 역배분을 차단한다. reopen/마감취소는 제공하지 않는다.

계약과 직접 관련 없는 미배정 보증금은 타 계약 담보용으로 남길 수 있다. 잔액 0을 이유로 보증금을 강제 반환하지 않는다. 원가반품·타법인 전표 등이 미지원인 계약에는 이 지원 경로로 형식적 마감을 하지 않는다.

## 6. Migration — 중앙 SERVER 한 곳에서만, 사용자 수행

**신규 `db_financing_phase2_migrate.py` 필요. Work에서 실행하지 않았다.**

새 테이블 6개:

1. `tb_fin_charge`
2. `tb_fin_deposit`
3. `tb_fin_deposit_assignment`
4. `tb_fin_deposit_movement`
5. `tb_fin_closure`
6. `tb_fin_bank_evidence`

기존 테이블 DROP/RECREATE/데이터 UPDATE/DELETE/backfill 없음. 아래 **기존 named CHECK 2개를 같은 transaction에서 안전하게 확장**한다.

- `CK_account_tx_type`: 기존 6종 + DEPOSIT_RECEIPT/DEPOSIT_RETURN/DEPOSIT_APPLIED.
- `CK_fin_contract_status`: 기존 DRAFT/CONFIRMED/ACTIVE/**SETTLED 유지**/CANCELLED + CLOSED.

기존 미지원 값이 있으면 THROW로 중단한다. 외부 FK/메뉴/기존 컬럼을 먼저 검사하며 각 CREATE TABLE/INDEX는 별도 compilation batch다. nullable transaction_id UNIQUE는 SQL Server filtered index를 사용한다. 사용자 권한 일괄 부여나 API startup 자동 Migration은 없다.

SQLite 검증은 ORM FK/Check 및 격리 API 검증이다. SQL Server 검증은 DDL 컴파일·FK 순서·누락 선행조건 차단·가드 SQL·반복 batch 검증이다. **실제 SQL Server 실행·롤백·동시성/교착 부하검증을 한 것은 아니다.**

신규 코드에서 원장 조회/RECEIPT/출고/계약취소도 새 테이블을 참조한다. **Migration 완료 전에 새 중앙 API를 운영하지 않는다.** 기존 매입/매출 Migration은 거래유형 CHECK를 옛 목록으로 되돌릴 수 있으므로 무작정 재실행하지 않는다. 재실행이 필요한 경우 phase2 Migration을 마지막에 다시 적용하여 CHECK를 확인해야 한다.

## 7. 검증 결과

- 1차 patch 기준: 380 passed, 1 warning.
- 이번 신규 31개: 혼합세무/별도비용/FIFO/재고/취소, FREE/할인, 명시 연장수수료/과거 Snapshot, 보증금 분산/전액·부분충당/복원/반환/중복 은행근거/음수수금 분리, 최종 CLOSED/과거 마감 차단/마감 후 반제 Guard, 늦은 Audit 오류 rollback, 메뉴 권한, GUI API 어댑터, A4 한글·다중페이지 모든 LOT 행 보존/불변 출력, SQL Server Migration 검증.
- **최종 전체 411 passed, 1 warning** (54.29초).
- `python -m compileall -q .` 및 `git diff --check` 통과.
- PDF 3종 페이지 PNG 시각검사 완료. 샘플은 모두 가상 fixture의 업체/계좌/거래다. 실입금요청/실계약 자료가 아니다.
- warning은 기존 FastAPI/Starlette TestClient httpx deprecation이며 실패가 아니다.
- clean c973443 별도 checkout에서 통합 patch `git apply --check` 및 실제 적용, diff 검사 수행. 최종 진행기록에 patch 해시/크기를 남긴다.

## 8. 변경 파일

최초 c973443 대비 **25개 파일**, 1차 변경 포함. 신규 테스트는 phase2 2개 파일(31개 case), 1차 테스트 2개 파일 유지.

- 거래/원장: `models.py`, `main.py`, `permissions.py`, `account_ledger.py`, `receipt_routes.py`, `settlement_service.py`, `financing_contract_routes.py`, `financing_release_routes.py`.
- 신규 서비스/API: `financing_charge_service.py`, `financing_deposit_routes.py`, `financing_close_routes.py`.
- Migration: `db_financing_phase2_migrate.py`.
- 출력: `financing_release_document.py`, `financing_settlement_document.py`.
- GUI: `views/financing_release.py`, `views/financing_settlement.py`, `views/mxmn_main_window.py`, `views/receipt_reg.py`.
- 테스트: `tests/test_financing_domestic_output.py`, `tests/test_financing_period_terms.py`, `tests/test_financing_phase2.py`, `tests/test_financing_phase2_output_migration.py`.
- 문서: `docs/04_CURRENT_STATUS.md`, 기존 1차 인수인계 `docs/22_...md`, 신규 `docs/23_MXMN_PHASE1_FULL_INTEGRATED_HANDOFF_20261013.md`.

## 9. DEV 적용 — 중복 patch 금지

통합 patch를 `C:\projects\MixNMenu`에 저장하고 VS Code에서 프로젝트/기존 venv를 사용한다.

첫 명령은 적용 전 검사다.

```powershell
git apply --check .\MXMN_PHASE1_FULL_INTEGRATED_c973443_20261013.patch
```

그 다음 HEAD/작업트리를 확인한다.

```powershell
git rev-parse HEAD
git status --short
```

### 아직 1차 patch를 적용하지 않은 clean c973443

소스의 미커밋 변경이 없는지 확인한 뒤 통합 patch **하나만** 적용한다.

```powershell
git apply .\MXMN_PHASE1_FULL_INTEGRATED_c973443_20261013.patch
python -m pytest -q
python -m compileall -q .
git diff --check
```

기대 411 passed, 기존 warning 1개. .env/비밀번호를 Git에 포함하지 않는다. DEV/WORK의 로컬 SQL Server/로컬 운영 API를 사용하지 않는다. 자동테스트는 기존 격리 fixture다.

### DEV에 이미 1차 patch만 적용했고 이후 소스 수정은 없는 경우

통합 patch 검사가 실패하는 것이 정상일 수 있다. **1차 위에 통합 patch를 다시 적용하지 않는다.** 기존 7개 파일 외 임의 수정이 없는지 확인하고, 원래 1차 patch를 사용하여 되돌릴 수 있는지 먼저 검사한다.

```powershell
git apply --reverse --check .\MXMN_PHASE1_REMAINING_FEATURES_c973443_20261013.patch
```

이 검사 성공 및 기존 1차 이후 다른 소스 변경 없음 확인 후에만 다음을 실행한다.

```powershell
git apply --reverse .\MXMN_PHASE1_REMAINING_FEATURES_c973443_20261013.patch
git apply --check .\MXMN_PHASE1_FULL_INTEGRATED_c973443_20261013.patch
git apply .\MXMN_PHASE1_FULL_INTEGRATED_c973443_20261013.patch
python -m pytest -q
git diff --check
```

그 외 상태에서는 강제 reset/덮어쓰기/patch 중복 적용을 하지 않는다. 소스를 보존하고 별도 clean c973443 checkout에서 검증해야 한다. 신규 파일과 기존 변경사항이 모두 통합 patch에 포함된다.

## 10. SERVER 적용 — GitHub 반영 결정 후 사용자 작업

1. DEV 자동검증/검토 후 사용자가 commit/push 여부를 결정한다. Work는 수행하지 않았다.
2. 운영 DB 백업/VERIFYONLY, API 정지 등 기존 운영 절차 수행.
3. 사용자 승인으로 GitHub 반영했다면 SERVER에서 clean 작업트리 확인 후 `git pull --ff-only origin main`.
4. **SERVER의 기존 중앙 mxmn_dev 설정/venv**에서:

```powershell
python db_financing_phase2_migrate.py
```

5. Migration 성공/새 테이블/CHECK/메뉴 확인 후 기존 방식으로 중앙 FastAPI 재시작. DEV/WORK GUI 재시작.
6. 비관리자에게 필요한 FINANCING_DEPOSIT/FINANCING_CLOSE 권한을 기존 권한관리에서 부여. 일괄 권한 부여하지 않는다.
7. 아래 테스트용 GUI 시나리오 후 실제 계약으로 확대한다. 실제 자료를 테스트용으로 수정하지 않는다.

DEV에 patch만 적용하면 중앙 API는 여전히 이전 코드다. 새 메뉴와 계산을 확인하려고 DEV 로컬 DB로 우회하지 않는다. 새 API의 실제 GUI 검증은 중앙 API 코드 및 Migration 반영 이후 가능하다.

## 11. 최소 Windows/SQL Server 검증 시나리오

1. **기존 일반거래**: 매입→LOT→일반매출→입금 FIFO→거래처원장/재고 및 원전표 Drill-down을 테스트 거래로 재확인.
2. **별도 과세비용**: 실제 확인한 Term의 STORAGE 등 SEPARATE/현재 청구법인/ACTUAL_SHIPPER/유효 세금코드/증빙대상 입력. 상품요청액 제외·별도 공급/세액 확인 → 은행확인 → 출고. 상품채권+비용채권 2개, OUTBOUND 1번인지 확인. 수금 후 미수 0, 수금 배분 후 취소 Guard 확인.
3. **FREE/연장**: 허용 COST 포함 항목을 명시하고 필요 비용행 설정. 적법한 새 Term의 추가율/차액율 선택 후 반복 부분출고. 과거 Snapshot/요율/계좌 불변 확인. 미지원 기간·회수유형·세무변경 Guard 확인.
4. **보증금**: 실제 은행근거의 실수취 → 2개 계약 분산배정 → 한 요청 충당. 실제 현금확인액이 상품요청액−충당인지 확인. 출고 후 지정 채권 반제, 일반 FIFO 잔액만 수금. 보증금 근거를 일반 입금에 재사용 시 차단. 수금이 없는 테스트 출고취소는 재고·채권·충당 원자 복원.
5. **반환/재배정**: 미사용 배정 해제 → 다른 계약 재배정 또는 실은행 반환. 충당분까지 미배정으로 풀리지 않는지 확인. 실제 반환 단순 취소 Guard 확인.
6. **최종마감**: 약정 전량 출고, 상품/비용 미수 0, 불필요 담보 해제, 수입원가 확정, 미출고 요청 없음 확인. 미청구/은행/초과입금 대사 근거 입력 후 CLOSED. 마감 후 수금수정/삭제·음수수금·출고취소·신규출고 차단 확인. 미래 입금으로 과거 마감할 수 없어야 한다.
7. **PDF/GUI**: 한글/긴 상품명/복수 LOT/여러 페이지, 실제 업체/금액/계좌/보증금/별도비용 구분 확인. 원장 원전표 더블클릭, 새 메뉴 닫았다 재열기 및 권한별 읽기/쓰기 확인.
8. **SQL Server 동시성**: 같은 계약/LOT 및 보증금을 2대 PC에서 동시에 확정/충당/출고해 초과배정/이중반제/중복채권이 생기지 않는지 별도 확인. Work SQLite 통과를 이 부하검증 완료로 간주하지 않는다.

## 12. 남은 개발·결정사항

- **INTEREST_ONLY 원가반품**: 기존 원매입/반품 상대/LOT 소유권·재고·세무·채권의 연결을 확정해야 한다. 기존 경영자 승인/상대 합의 필드는 유지하지만, 이것만으로 실제 반품전표를 자동 만들지 않았다.
- **타 법인 별도발행**: issuer 회사 권한, 발행회사 원채권/수금, A 계약 ↔ B 증빙 연결 및 취소/마감 정책이 필요하다. 현재 회사 아닌 issuer는 Guard.
- **제3자 보증금 상계**: 소유업체와 실제 채무자가 다를 때의 명시적 상계 합의/권한/책임/증빙 기준 필요. 공동 담보 배정은 지원하지만 타인 채권 상계는 차단.
- **월별 기청구·선청구**: 원가 포함 PERIOD, 월말 창고료/수수료 기청구를 날짜·LOT·채권별로 중복 제거하는 확장 필요. 현재 구조는 각 실제 출고 물량의 기간비용 경로.
- **이자기간 새 Term 재시작**, **고정비/음수 별도 청구**, **국내 할인/과세/경비 원가**, **LOT override**, **마감 reopen**: 미지원/별도 정책 검토.
- 실제 홈택스/전자계산서 발행·메일/외부 전송 자동화는 이번 결과에 포함하지 않는다.

이 남은 경로를 완료로 포장하지 않는다. 현재 지원 조건의 코드는 구현·자동검증했으며 실제 운영 검증 후 범위를 확대해야 한다.
