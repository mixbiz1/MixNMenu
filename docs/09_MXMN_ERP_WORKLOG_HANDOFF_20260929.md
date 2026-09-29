# MXMN ERP Worklog & Handoff — 2026-09-29

**Project:** MXMN ERP / MixNMenu  
**Repository:** `mixbiz1/MixNMenu`  
**기준일:** 2026-09-29  
**목적:** 2026-09-29 확정 설계, 중앙 DB 정상화, 개발개념 정리 및 다음 작업 시작점 보존

---

## 1. 오늘 확정한 개발 방향

MXMN ERP를 실제 개발의 단일 중심 프로젝트로 사용한다.

- 실제 개발/문서/Git 기준: `C:\projects\MixNMenu`
- GitHub: `mixbiz1/MixNMenu` `main`
- `MXMN_FinSales`는 삭제하지 않는다.
- 다만 독립 신규기능 개발은 중단하고 Reference Implementation / 기존 계산결과 비교 / 회귀검증 용도로 보존한다.
- 특별한 사유가 없는 한 FinSales에 별도 기능추가 및 Git 변경을 계속하지 않는다.

개발 우선순위:

1. Financing Integration Design 보존
2. 상품매입 현재 구현 정상화 및 마감
3. 일반매출 Vertical Slice
4. Financing Contract Vertical Slice
5. Financing 계산/입금/부분출고/정산
6. PDF/실제자료 회귀검증
7. MXMN ERP 초기버전 통합검증

---

## 2. Financing Integration Design v1 저장

오늘 `docs/08_MXMN_ERP_FINANCING_INTEGRATION_DESIGN_V1_20260929.md`를 `MixNMenu/docs`에 저장하였다.

주요 확정내용:

- ERP가 System of Record
- Financing 전용 거래처/상품/창고/LOT Master 중복생성 금지
- Partner Single Master + Multiple Business Relationships + Separate Sub-ledgers
- 한 계약에 복수 LOT 가능
- 계약상대방과 실제 매입처/매출처/출고처/입금자 분리 가능
- 계약업체가 지정한 연관업체와의 입금/실거래 허용 및 관계 History 보존
- 수입대행/BL양수도/국내매입 계약유형
- Contract Term / Interest Segment 방식
- 이자 시작일/종료일 포함 계산
- 수수료/창고료/가변비용의 계약별 유연성
- 평균중량 부분출고 및 최종 잔량마감
- 출고 전 입금 원칙과 Master 예외승인/Audit
- 지속거래 정산차액 상계
- 보증금/담보 독립 Ledger
- Standard Sale / Return Settlement 정산방식
- 일반유통 매입반품/매출반품을 원거래 추적형 Transaction으로 구현
- 자동계산값 Override 시 원값/수정값/사유/사용자/일시 보존
- 의미 있는 Business Code는 분류/통계에 도움이 되는 논리적 자동발번 규칙 적용
- 단, 통계는 코드 문자열만 자르지 않고 별도 FK/분류 Column으로도 관리

Financing 설계는 여기서 계속 확대만 하지 않고 실제 ERP 개발로 전환한다.

---

## 3. 2026-09-29 중앙 DB 오류 발생 및 해결

### 3.1 증상

MXMN-SERVER에서 GUI 메뉴 선택 시 HTTP 500 오류 발생.

1. `2. 코드관리 → 5. 경비코드입력`
2. `4. 상품입/출고관리 → 1. 상품매입등록/수정`

소스 Git 상태 확인 결과:

- branch: `main`
- `origin/main`과 동기화
- working tree clean

따라서 Git 소스 불일치가 아니라 중앙 DB Migration 적용상태를 우선 점검하였다.

### 3.2 경비코드 오류

DB 조회 결과:

`sqlalchemy.exc.NoSuchTableError: dbo.tb_expense_code`

즉 현재 코드에는 경비코드 기능이 존재하지만 중앙 `mxmn_dev`에 실제 테이블이 생성되지 않은 상태였다.

실행:

```powershell
python db_expense_code_migrate.py
```

결과:

```text
[ADD] tb_expense_code
[SEED] standard profit/loss tree
```

GUI 재검증 결과 경비코드 화면 정상 작동.

### 3.3 상품매입 오류 1차

중앙 DB 테이블 확인 결과:

```text
tb_inbound
tb_inbound_item
tb_lot
```

은 존재했으나 다음이 없었다.

```text
tb_purchase
tb_purchase_item
```

실행:

```powershell
python db_purchase_migrate.py
```

결과:

```text
General purchase migration completed.
```

이후 상품매입 화면의 연속 2개 오류 중 1개가 해소됨.

### 3.4 상품매입 오류 2차

남은 오류 API:

```text
/api/v1/companies/00001/purchase-options?transaction_date=2026-09-29
```

`get_purchase_options()`를 추적한 결과 마지막에 `get_trade_input_options()`를 호출하며 다음 Master를 조회함.

- `TaxCode`
- `ExpenseCode`

ExpenseCode는 앞 단계에서 정상화되었으나 중앙 DB에는 `tb_tax_code`가 없었다.

검색 결과 `tb_tax_code` 생성은 `db_trade_common_migrate.py`에 포함되어 있음을 확인.

실행:

```powershell
python db_trade_common_migrate.py
```

결과:

```text
Trade common foundation migration completed.
```

GUI 재검증 결과:

- 경비코드입력 정상
- 상품매입등록/수정 정상
- 기존 HTTP 500 팝업 모두 제거됨

### 3.5 결론

오늘 오류는 새 소스코드의 로직 오류가 아니라 **현재 GitHub main이 기대하는 DB Schema와 MXMN-SERVER 중앙 `mxmn_dev`의 실제 Schema 사이에 Migration 적용 누락이 있었던 것**이다.

오늘 적용한 Migration:

```text
db_expense_code_migrate.py
db_purchase_migrate.py
db_trade_common_migrate.py
```

소스코드 수정은 하지 않았다.

---

## 4. Server Process 확인사항

점검 중 ERP `:8000` 관련 프로세스가 다음과 같이 관찰되었다.

- 부모 PID는 `C:\projects\MixNMenu\venv\Scripts\python.exe`
- 실제 8000 Listen 자식 PID의 ExecutablePath는 `C:\Python312\python.exe`

부모/자식 관계가 확인되었으므로 단순히 두 개의 독립 Uvicorn 충돌이라고 판단하지 않는다.

오늘의 GUI 500 오류 원인은 DB Migration 누락으로 해결되었으므로 이 프로세스 구조는 당일 추가 변경하지 않았다.

향후 자동기동/가상환경 점검 시 필요하면 별도로 원인을 확인한다. 현재 정상 서비스를 임의 종료하지 않는다.

---

## 5. 오늘 정리한 Migration 개념

MXMN의 기본 실행구조:

```text
사용자
  ↓
PySide6 GUI Client
  ↓ HTTP
FastAPI Server
  ↓
업무 Logic / SQLAlchemy
  ↓ pyodbc
MS SQL Server / mxmn_dev
```

### 5.1 migrate.py의 역할

`migrate.py`는 GUI와 FastAPI 기능 자체를 구현하는 파일이 아니라, **현재 프로그램 기능이 요구하는 실제 DB 구조를 중앙 DB에 생성/변경하여 코드와 DB Schema를 맞추는 Python DB Migration Script**이다.

개념적으로:

```text
models.py / 업무설계
    ↓
"이 기능에는 이런 DB 구조가 필요하다"
    ↓
migrate.py
    ↓
실제 MS SQL DB에 Table / Column / Constraint / FK / Seed 등을 생성·변경
```

예: 상품매입 기능이라면 단순 저장공간 하나가 아니라 다음과 같은 구조를 실제 DB에 구현한다.

```text
tb_purchase
  └─ tb_purchase_item
       ├─ Product와 관계
       ├─ Inbound와 관계
       ├─ LOT와 관계
       └─ 거래/미지급 원장과 관계
```

즉 Migration은 단순한 데이터 저장공간 생성이 아니라 특정 업무기능에 필요한 **DB 설계의 실제 실현**이다.

### 5.2 Table / Column / PK / FK / Mapping

DB 설계에서는 다음을 정의한다.

- Table: 어떤 업무정보를 보관하는가
- Column: 어떤 항목을 보관하는가
- Data Type: 정수/문자/날짜/Decimal 등
- PK: 각 Record의 고유 식별자
- FK: 다른 Table Record와의 관계
- Constraint: 중복/NULL/잘못된 값 등을 방지하는 규칙
- Mapping: 거래처→매입→입고→LOT→재고→매출→출고 등 업무관계를 연결

따라서 관계형 DB의 핵심은 데이터를 각각 저장하는 것뿐 아니라 **데이터가 왜 생겼고 무엇과 연결되는지를 영속적으로 보존하는 것**이다.

### 5.3 GUI는 DB에 직접 접근하지 않는다

사용자는 GUI Form을 통해 입력/조회하지만 MXMN에서는 GUI가 DB에 직접 SQL을 실행하지 않는다.

```text
GUI
 ↓
FastAPI
 ↓
업무규칙/권한/검증
 ↓
SQLAlchemy
 ↓
MS SQL DB
```

예를 들어 사용자가 상품매입을 저장하면 겉으로는 하나의 Form 저장이지만 내부에서는 업무규칙에 따라 Purchase, PurchaseItem, Inbound, LOT, 재고, 미지급 및 Audit 관계가 생성될 수 있다.

### 5.4 전통적 DB 프로그램 개념과 MXMN 대응

| 전통적 DB 개념 | MXMN 구현 |
|---|---|
| Table | MS SQL Server Table |
| Form | PySide6 GUI |
| Query | SQLAlchemy Query / FastAPI |
| Function / Module | Python 업무 Logic / Service |
| Macro / 자동처리 | Python API / Service / Transaction |
| Report | GUI 조회 / Excel / PDF / 경영정보 |
| PK / FK | 관계형 데이터 무결성 |
| Relationship / Mapping | SQL Server + SQLAlchemy Models |
| DB 구조 변경 | Migration Script |

DB 관계와 분류가 잘 설계되어 있으면 이후 새로운 경영정보/통계/Report는 기존 영속 데이터의 관계를 Query하여 만들 수 있다.

예를 들어 상품에 축종/부위/원산지 등의 분류 FK가 정확히 존재하면 향후 기간별·축종별·원산지별·부위별·거래처별 매출/수익성 분석을 원자료 재입력 없이 구현할 수 있다.

---

## 6. 개발 시 중요한 원칙 재확인

1. GUI 오류가 발생했다고 즉시 GUI 코드를 수정하지 않는다.
2. HTTP 500이면 API 서버 로그/DB Schema/API 의존성을 먼저 확인한다.
3. Git main이 최신이어도 DB Migration이 적용되지 않으면 코드와 DB가 불일치할 수 있다.
4. Migration은 어떤 중앙 DB를 대상으로 실행하는지 먼저 확인한다.
5. 기존 데이터를 가진 DB에서는 Migration을 추측하여 무작정 실행하지 않는다.
6. 기능별 Model/API/DB/GUI가 하나의 Vertical Slice로 연결되어야 한다.
7. 업무관계는 가능한 PK/FK와 명확한 Transaction 관계로 영속화한다.
8. 경영정보에 도움이 되는 Business Code와 별도 분류 FK를 함께 사용한다.
9. Financing 때문에 일반유통 Master/Transaction을 중복 생성하지 않는다.
10. 실제 기능검증 후 Git을 정리한다.

---

## 7. 다음 작업 — 상품매입 마감

2026-09-29 종료 시점에 상품매입 메뉴를 열 때 발생하던 DB/API 오류는 정상화되었다.

다음 세션에서는 인프라나 Migration을 다시 구축하지 않는다.

첫 작업은 **지난 개발에서 마지막으로 구현했으나 현재 제대로 작동하지 않는 상품매입 기능을 사용자와 함께 재현하여 원인을 수정하는 것**이다.

그 다음 상품매입 전체 Cycle을 점검한다.

```text
상품매입 입력
→ 저장/확정
→ Inbound
→ LOT
→ 재고
→ PURCHASE_PAYABLE
→ 조회/수정/취소
→ 데이터 무결성
```

특히 후속 일반매출/출고가 연결된 이후에는 확정 매입의 파생자료를 단순 회수/삭제하지 않고 매입반품 등 원거래 추적형 역거래로 발전시킬 수 있는 구조를 유지한다.

상품매입 마감 후 즉시 **일반매출 Vertical Slice**로 이동하고, 그 다음 Financing을 ERP Transaction 위에 연결한다.

---

## 8. 다음 세션 시작용 프롬프트

```text
MXMN ERP 개발을 이어서 진행합니다.

기준 Repository는 GitHub mixbiz1/MixNMenu의 main이며 실제 개발폴더는
C:\projects\MixNMenu 입니다.

2026-09-29에 Financing Integration Design v1을
`docs/08_MXMN_ERP_FINANCING_INTEGRATION_DESIGN_V1_20260929.md`로 저장했습니다.
MXMN_FinSales는 독립 신규개발을 중단하고 Reference Implementation 및
회귀검증용으로 보존합니다.

같은 날 MXMN-SERVER 중앙 mxmn_dev에서 GUI 500 오류를 점검하여 다음
Migration 누락을 정상화했습니다.

- db_expense_code_migrate.py
- db_purchase_migrate.py
- db_trade_common_migrate.py

현재 `2.코드관리 → 5.경비코드입력`과
`4.상품입/출고관리 → 1.상품매입등록/수정` 메뉴는 정상적으로 열립니다.
소스코드 수정 없이 중앙 DB Schema만 현재 main 코드와 맞췄습니다.

이제 인프라나 Financing 설계를 다시 시작하지 말고 상품매입 마감부터 진행합니다.

첫 작업은 지난번 상품매입에서 마지막으로 구현했으나 현재 제대로 작동하지
않는 기능을 실제 GUI에서 재현하고, 최신 main의 관련 GUI/API/Model/Migration을
추적하여 원인을 찾는 것입니다.

바로 코드를 추측하여 수정하지 말고:
1. 사용자에게 현재 잘못 작동하는 기능을 재현받기
2. 실제 코드/DB/API 흐름 확인
3. 최소 수정
4. 사용자 실행검증
5. 상품매입 전체 Cycle 검증
6. Git commit/push 및 docs/current status 업데이트
순으로 마감해 주세요.

상품매입 전체 Cycle은
상품매입 → Inbound → LOT → 재고 → PURCHASE_PAYABLE → 조회/수정/취소
입니다.

상품매입이 마감되면 일반매출 Vertical Slice로 이동하고,
그 다음 ERP LOT/매입/매출/출고 기반 위에 Financing을 연결합니다.

추가 원칙:
- Business Code는 가능한 분류/통계에 도움이 되는 논리적 자동발번 규칙을 사용
- 통계는 코드문자열에만 의존하지 않고 별도 FK/분류 Column도 유지
- Migration은 DB 설계의 실제 구현이며 대상 DB 확인 후 안전하게 적용
- GUI는 DB에 직접 접근하지 않고 PySide6 → FastAPI → 업무Logic/SQLAlchemy → MS SQL 구조 유지
- 기존 정상기능과 실제 데이터를 훼손하지 않는 작은 Vertical Slice 방식으로 진행
```

---

**End of handoff — 2026-09-29**
