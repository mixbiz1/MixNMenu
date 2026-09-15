# MXMN CODEBASE GAP ANALYSIS --- 2026-09-15

## 기준 코드

업로드된 `최신MixNMenu_20260915-1.zip`을 현재 코드 기준본으로
분석하였다.

## 현재 Architecture

`PySide6 app.py → HTTP → FastAPI main.py → SQLAlchemy models.py/database.py → MS SQL Server`

현재 로그인과 Company 등록은 실제 API/ORM 연결이 존재하여 단순 UI
Mock보다 진전된 **ERP Framework + 첫 Vertical Slice 시험구현 단계**이다.

## 파일 판정

  --------------------------------------------------------------------------------------------------------
  현재 파일                     현재 역할                           판정              방향
  ----------------------------- ----------------------------------- ----------------- --------------------
  `app.py`                      로그인/Client Entry                 KEEP + REFACTOR   API Client/보안 분리

  `database.py`                 SQLAlchemy Engine/Session           KEEP              추후
                                                                                      `core/database.py`

  `db_test.py`                  DB 연결검증                         KEEP(dev)         `tools/` 이동

  `main.py`                     FastAPI + Login + Company API       REFACTOR          Router/Schema 분리

  `models.py`                   Company/User/Account/Product/Slip   REFACTOR          Domain별 모델 분리

  `views/company_reg.py`        회사등록 Pure Python UI             KEEP              Vertical Slice #1

  `views/mxmn_main_window.py`   MDI Main Window                     KEEP              Main Shell

  `views/main_dashboard.py`     Dashboard                           REFACTOR          QUiLoader 제거

  `views/main_view.py`          과거 UI Loader                      ARCHIVE 후보      신규 구조에서 제거

  `services/`                   Service Layer                       BUILD             Client/API Service
                                                                                      계층 구축

  `ui-당분간 사용안함/`         Qt Designer 자산                    ARCHIVE           신규개발 금지

  과거 수정본 모음              수동 버전보관                       ARCHIVE           Git 이력으로 대체
  --------------------------------------------------------------------------------------------------------

## 구조적 Gap

### Company

현재 `Company.comp_code`가 PK이고 Company API는 `"00001"`을 고정
조회한다. 실제 동작은 Single-Company이다. 목표는 내부 `company_id` PK +
업무용 `company_code` UNIQUE 구조이다.

### Account

현재 `Account` 하나에 법적 사업자와 업무 거래처 개념이 혼재한다. 목표는
`Partner + Customer` 분리이다.

### Product

현재 category/origin/tax_type 등이 문자열로 직접 저장된다. 목표는
Master/FK 중심이며 LOT를 별도 관리한다.

### Slip

현재 `SlipHeader/SlipDetail`에서 매입·입고·매출·출고·파이낸싱을
`slip_type`으로 통합한다. 실제 업무에서는
Purchase/Inbound/Sale/Outbound/Financing의 생명주기가 다르므로 장기 목표
구조에서는 분리한다.

### Tax

현재 Header의 `tax_type`으로 거래 전체를 과세/면세 처리한다. 목표는
Product/Service 기본 Tax + 거래 Detail Tax Snapshot이다.

### Security

현재 `password_hash` 필드는 이름과 달리 로그인에서 문자열 직접 비교한다.
운영 단계 전에 실제 Password Hash 검증으로 전환한다.

### UI

`company_reg.py`, `mxmn_main_window.py`는 Pure Python 방향이지만 일부
Dashboard/Main View에는 QUiLoader 잔재가 있다.

## Migration 핵심 원칙

현재 코드를 버리고 재작성하지 않는다. 실행되는 기능을 유지하면서 Company
Vertical Slice부터 목표 구조로 전환한다.
