# MXMN FOLDER STRUCTURE v1.0 Target

``` text
MixNMenu/
├─ app.py
├─ main.py
├─ core/
│  ├─ config.py
│  ├─ database.py
│  └─ security.py
├─ models/
│  ├─ system.py
│  ├─ master.py
│  ├─ trade.py
│  ├─ logistics.py
│  ├─ sales.py
│  ├─ financing.py
│  └─ compliance.py
├─ schemas/
├─ api/
├─ services/
├─ views/
│  ├─ main/
│  ├─ system/
│  ├─ master/
│  ├─ trade/
│  ├─ logistics/
│  ├─ financing/
│  └─ reports/
├─ integrations/
│  ├─ meatwatch/
│  ├─ document_storage/
│  └─ tax_invoice/
├─ reports/
├─ resources/
├─ docs/
├─ tools/
├─ requirements.txt
├─ .env
├─ .env.example
└─ .gitignore
```

## 현재 → 목표 Migration 원칙

-   `app.py`: 유지, Desktop Client Entry로 발전
-   `main.py`: 유지하되 API Router를 단계적으로 분리
-   `database.py`: 유지 후 `core/database.py`로 이동
-   `models.py`: 현재 실행을 유지하면서 Domain별 model 파일로 단계적
    분리
-   `db_test.py`: `tools/`로 이동
-   `views/company_reg.py`: 유지, 첫 표준 Vertical Slice로 발전
-   `views/warehouse_reg.py`: 창고 Master와 회사별 사용·기본요율 입력
-   `views/mxmn_main_window.py`: 유지, Main Shell로 발전
-   `db_warehouse_migrate.py`: 창고 관련 3개 테이블 비파괴 Migration
-   `db_opening_data_migrate.py`: 최초재고·거래처 최초잔액 원장 비파괴 Migration
-   `views/opening_inventory_reg.py`: 최초재고 Header/Detail 입력
-   `views/opening_balance_reg.py`: 거래처 미수·미지급 최초 원거래 입력
-   `views/table_utils.py`: 조회목록 정렬·실제값 비교·가변 열 너비 공통 유틸
-   `views/main_dashboard.py`: QUiLoader 의존 제거 후 Pure Python화
-   `views/password_change.py`: 현재 로그인 사용자 비밀번호 변경 대화상자
-   `views/main_view.py`: Legacy/Archive 후보
-   `ui-당분간 사용안함`: 신규 개발에 사용하지 않고 Archive 성격으로
    유지
-   과거 버전 모음 폴더: Git 이력으로 대체할 수 있도록 점진 정리

**주의:** 목표 폴더 구조로 한 번에 이동하지 않는다. 각 변경 후
실행검증과 Git Commit을 수행한다.
