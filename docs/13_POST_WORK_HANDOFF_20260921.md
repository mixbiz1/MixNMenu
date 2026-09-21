# MXMN Work 중단 이후 변경사항 및 재개 인수인계

-   작성 기준일: 2026-09-21
-   목적: ChatGPT Work 중단 이후 발생한 프로젝트/개발환경/DB/운영방식
    변경사항을 Work 재개 시 정확히 인계
-   성격: 기존 `docs/` 기준문서를 대체하지 않는 보완·인수인계 문서
-   중요 원칙: 본 문서의 내용과 기존 문서 또는 실제 코드/DB가 충돌할
    경우 임의로 판단하지 말고 GitHub `main`, 실제 DB Schema, Migration
    파일을 함께 확인하여 현 상태를 재판정한다.

------------------------------------------------------------------------

## 1. 현재 프로젝트 전체 구조

현재 개발은 하나의 프로젝트가 아니라 다음 두 프로젝트로 분리되어 있다.

### 1.1 MXMN

기존 수입육류 유통·무역 ERP 프로젝트.

-   로컬 경로: `C:\projects\MixNMenu`
-   GitHub: `mixbiz1/MixNMenu`
-   기본 브랜치: `main`
-   DB: `mxmn_dev`
-   주요 기술:
    -   Python
    -   PySide6
    -   FastAPI
    -   SQLAlchemy
    -   pyodbc
    -   MS SQL Server

MXMN은 기존 개발을 계속 이어가는 메인 ERP이다.

### 1.2 MXMN_FinSales

파이낸싱 계약판매 업무를 위한 별도 단독 실행 모듈형 프로젝트.

-   로컬 경로: `C:\projects\MXMN_FinSales`
-   GitHub: `mixbiz1/MXMN_FinSales`
-   기본 브랜치: `main`
-   DB: `mxmn_finsales_db`

MXMN_FinSales는 MXMN 하위 폴더나 동일 Git 저장소가 아니다.

독립적인 프로젝트 폴더, Python 개발환경, 파일구조, Git 저장소, GitHub
Repository, DB를 유지한다.

향후 두 시스템 사이에 업무적 연계가 필요하더라도 프로젝트와 DB를
성급하게 합치지 않는다.

------------------------------------------------------------------------

## 2. SQL Server 현재 구성

홈 PC의 MS SQL Server에는 현재 최소 다음 두 업무 DB가 존재한다.

``` text
SQL Server
├── mxmn_dev
│   └── MixNMenu(MXMN) 전용
│
└── mxmn_finsales_db
    └── MXMN_FinSales 전용
```

두 DB는 각각 독립 프로젝트의 DB이다. DB 이름이나 연결대상을 혼동하지
않는다.

------------------------------------------------------------------------

## 3. 개발/운영 구조 변경

기존에는 여러 PC에 개발환경 및 DB를 두고 Git으로 소스를 동기화하는
방식이 사용되었다.

이 방식에서 점차 Client/Server 구조로 전환한다.

### 목표 구조

``` text
                  MXMN SERVER
                      │
          ┌───────────┴───────────┐
          │                       │
      SQL Server               FastAPI
          │
    ┌─────┴────────┐
    │              │
mxmn_dev     mxmn_finsales_db

          ↑              ↑
          │ Network/API  │
          │              │
    Office Client    Mobile Client
```

홈 노트북을 중앙 서버로 사용하고 사무실/모바일 PC는 Client 역할을
담당하는 방향이다.

중요한 변화는 DB를 각 개발 PC에 복제해서 사용하는 구조에서 벗어나 중앙
SQL Server를 기준으로 사용하는 것이다.

------------------------------------------------------------------------

## 4. 홈 서버 전환 계획

현재 홈 Lenovo 노트북을 MXMN 서버로 전환하는 작업을 진행 중이다.

현재 확인된 주요 사양:

-   Lenovo IdeaPad Slim 3
-   AMD Ryzen 5 4500U
-   RAM 12GB
-   SSD 약 238GB
-   Windows 10 Pro 22H2
-   LG U+ 500Mbps 인터넷

현재 PC 이름은 `ideapad-slim-3`이며, 향후 서버명은 `MXMN-SERVER` 사용을
계획한다.

서버화 과정에서는 다음을 순차 적용한다.

-   Windows 11 전환
-   UEFI/GPT 전환
-   내부 IP 고정
-   Gigabit 유선 LAN 권장
-   SQL Server 중앙화
-   FastAPI 서버 운영
-   외부 접속 시 보안 네트워크/VPN 고려
-   절전/덮개닫기/자동시작 설정

------------------------------------------------------------------------

## 5. Windows/서버 전환 현재 확인사항

Windows 11 호환성 점검 과정에서 다음이 확인되었다.

-   CPU: Windows 11 사용 가능 계열
-   TPM: TPM 2.0 정상
-   현재 BIOS Mode: Legacy
-   Secure Boot: Legacy Mode 때문에 현재 사용 불가
-   시스템 디스크: MBR 상태
-   `mbr2gpt /validate /allowFullOS` 실행 결과:
    `Validation completed successfully`

따라서 향후 다음 전환을 계획한다.

``` text
MBR
 ↓
GPT
 ↓
Legacy BIOS → UEFI
 ↓
Secure Boot
 ↓
Windows 11
```

아직 실제 `mbr2gpt /convert` 작업은 진행하지 않은 상태이다.

------------------------------------------------------------------------

## 6. 서버 전환 전 백업 상태

2026-09-21 기준 다음 DB 백업을 생성했다.

``` text
C:\MXMN_Backup\
├── mxmn_dev_20260921.bak
└── mxmn_finsales_db_20260921.bak
```

두 파일 모두 SQL Server에서 `RESTORE VERIFYONLY` 검증을 수행했고
정상적인 백업 세트임을 확인했다.

주의: `mxmn_dev_20260921.bak`은 아래 설명하는 일부 Migration 누락 상태가
발견되기 전/복구 중 생성된 백업이다.

따라서 현재 상태 보존용 백업으로는 의미가 있지만, "모든 최신 Migration이
적용된 완성 DB"라고 간주해서는 안 된다.

Migration 정합성 복구 후 최종 DB 백업을 다시 생성할 필요가 있다.

------------------------------------------------------------------------

## 7. Work 중단 당시 MXMN 상태 관련 중요사항

Work 사용한도가 소진되면서 MXMN 개발이 완전히 마감·검증되지 않은
상태에서 작업이 중단되었을 가능성이 있다.

특히 마지막 주요 개발 영역은 `상품매입등록/수정`이었다.

따라서 Work 재개 시 "상품매입 기능이 완료됐다"고 문서만 보고 가정하지
말고 실제 코드, Migration, DB Schema, 테스트 결과를 다시 확인해야 한다.

------------------------------------------------------------------------

## 8. 2026-09-21 Chat에서 확인된 MXMN DB 불일치

서버 전환 전에 MXMN을 실행하여 정상 여부를 확인하는 과정에서 DB Schema와
현재 소스코드가 일치하지 않는 문제가 발견되었다.

### 8.1 로그인 오류

FastAPI 로그인 시 `tb_user.is_admin` 컬럼이 DB에 없어 HTTP 500 오류
발생.

기존 프로젝트에 존재하는 `db_user_permission_migrate.py`를 2026-09-21
Chat 진행 중 실행했다.

그 후 로그인은 정상화되었다.

즉 `mxmn_dev`는 당시 최신 사용자/권한 Migration이 적용되지 않은
상태였다.

------------------------------------------------------------------------

## 9. 상품매입 오류

로그인 정상화 후 `상품매입등록/수정` 화면을 실행했으나 다음 API에서 HTTP
500 발생.

-   `/api/v1/companies/00001/purchase-options`
-   `/api/v1/companies/00001/purchases`

SQL Server 오류 확인 결과 `dbo.tb_purchase` 테이블이 존재하지 않았다.

현재 Python 소스에서는 `models.Purchase` 및 `tb_purchase`를 사용하고
있으나 실제 `mxmn_dev` DB에는 해당 테이블이 없는 상태였다.

------------------------------------------------------------------------

## 10. db_purchase_migrate.py 실행 결과

기존 프로젝트의 `db_purchase_migrate.py`를 실행하여 문제를 해결하려
했으나 Migration 시작 단계에서 다음 오류가 발생했다.

`dbo.tb_expense_code` 테이블이 존재하지 않음.

즉 상품매입 Migration 하나만 누락된 것이 아니라, 그보다 앞선 DB
Migration 또는 Master Schema 적용이 누락되어 있을 가능성이 높다.

`db_purchase_migrate.py`는 필요한 기존 테이블의 데이터 보호 검사를
수행하는 과정에서 중단되었으므로 상품매입 Migration 자체는 정상 완료되지
않았다.

------------------------------------------------------------------------

## 11. 현재까지 Chat에서 DB에 가한 변경

2026-09-21 Chat에서 MXMN DB와 관련하여 실제 완료된 주요 변경은
`db_user_permission_migrate.py` 실행이다.

이 Migration 실행 후 로그인 정상 동작을 확인했다.

반면 `db_purchase_migrate.py`는 `dbo.tb_expense_code` 부재 오류로
중단됐다.

Chat에서는 다음 작업을 하지 않았다.

-   `tb_purchase` 수동 생성하지 않음
-   `tb_expense_code` 수동 생성하지 않음
-   Migration 코드를 임의 수정하지 않음
-   DB Schema를 추측해서 수동 보완하지 않음

이는 Work가 재개 후 정확한 Migration 상태를 판단할 수 있도록 의도적으로
보존한 것이다.

------------------------------------------------------------------------

## 12. Work 재개 시 최우선 작업

Work가 다시 사용 가능해지면 신규 기능 개발보다 먼저 MXMN의 실제 상태를
재판정한다.

### STEP 1. Git 상태 확인

`C:\projects\MixNMenu`에서 다음을 확인한다.

-   `git status`
-   `git fetch`
-   `origin/main`
-   HEAD
-   최신 commit

2026-09-21 Chat 확인 당시에는 working tree가 clean이고 local `main`과
`origin/main`이 일치했다.

### STEP 2. 기준문서 확인

특히 다음을 확인한다.

-   `docs/04_CURRENT_STATUS.md`
-   `docs/10_DEVELOPMENT_ROADMAP.md`
-   관련 DB/Migration 문서
-   본 인수인계 문서

단, 문서보다 실제 코드/DB 상태를 우선 검증한다.

### STEP 3. Migration 파일 전수 확인

저장소의 `db_*migrate.py` 파일들을 확인하고 각각의 다음 사항을 분석한다.

-   목적
-   생성 테이블
-   ALTER 대상
-   선행 의존성
-   실행 순서
-   재실행 안전성
-   기존 데이터 보호 로직

### STEP 4. 실제 mxmn_dev Schema 비교

현재 SQL Server의 `mxmn_dev`와 다음을 비교한다.

-   `models.py`
-   Migration 파일
-   FastAPI API
-   현재 문서

### STEP 5. 누락 Migration 판정

특히 다음 상태를 확인한다.

-   `tb_user.is_admin`
-   `tb_expense_code`
-   `tb_purchase`
-   상품매입 관련 Detail/LOT/거래공통 테이블

### STEP 6. 올바른 순서로 Migration 적용

임의 `CREATE TABLE` 방식이 아니라 기존 Migration 체계를 우선 사용한다.

Migration 자체가 불완전하다면 먼저 코드의 의도와 기존 작업 기록을 확인한
후 수정한다.

### STEP 7. 자동 테스트

Migration 완료 후:

``` powershell
python -m pytest -q
```

실행.

### STEP 8. 실제 UI 검증

최소 다음 기능까지 실제 실행 검증한다.

-   로그인
-   사용자 권한
-   업무회사
-   상품/코드
-   창고
-   LOT/초기자료
-   상품매입등록/수정

------------------------------------------------------------------------

## 13. 두 프로젝트의 Git 원칙

현재 두 프로젝트는 각각 독립 Git Repository를 유지한다.

### MXMN

``` text
C:\projects\MixNMenu
↓
GitHub: mixbiz1/MixNMenu
```

### MXMN_FinSales

``` text
C:\projects\MXMN_FinSales
↓
GitHub: mixbiz1/MXMN_FinSales
```

각 프로젝트 폴더에서 별도로 다음 명령을 수행한다.

-   `git status`
-   `git fetch`
-   `git pull`
-   `git add`
-   `git commit`
-   `git push`

한 프로젝트의 Git 명령을 다른 프로젝트 폴더에서 실행하지 않는다.

------------------------------------------------------------------------

## 14. Git 개념 기준

향후 사용자가 혼동하지 않도록 다음 개념을 기준으로 설명한다.

``` text
main
= 현재 Local Repository의 Branch

origin/main
= Local Git이 마지막 fetch 시점에 기억하고 있는
  Remote main의 상태

GitHub main
= 실제 GitHub Remote Repository의 현재 상태
```

따라서 원격 상태를 최신으로 확인하려면 `git fetch`가 먼저 필요하다.

그 후 `git status` 등을 통해 local과 remote tracking branch 관계를
확인한다.

------------------------------------------------------------------------

## 15. 개발 방식 원칙

MXMN의 기본 개발방식은 계속 다음 원칙을 유지한다.

### Pure Python UI

-   Qt Designer `.ui` 의존 배제
-   PySide6 Python 코드로 UI 작성

### Layout 기반 UI

-   `setGeometry()` 중심 고정좌표 사용 금지
-   `QVBoxLayout`
-   `QHBoxLayout`
-   `QGridLayout`
-   기타 Qt Layout Manager 사용

### 화면 독립성

View별로 가능한 경우 단독 실행 및 검증 가능하도록 유지한다.

### Layer 분리

``` text
View
 ↓
Service / Business Logic
 ↓
API / Model
 ↓
Database
```

책임을 분리한다.

------------------------------------------------------------------------

## 16. 작은 Vertical Slice 원칙

MXMN 개발은 전체 ERP를 한 번에 변경하지 않는다.

``` text
작은 요구사항
 ↓
DB/Model
 ↓
API
 ↓
UI
 ↓
Test
 ↓
실행 검증
 ↓
Git Commit
```

단위로 진행한다.

기능 하나를 완결한 후 다음 기능으로 넘어간다.

------------------------------------------------------------------------

## 17. DB 변경 원칙

DB Schema 변경은 다음을 원칙으로 한다.

-   임의 수동 ALTER 최소화
-   Migration Script로 명시
-   재실행 안전성 고려
-   기존 데이터 보호
-   PK/FK/Unique 제약 검토
-   Migration 후 Test
-   문서 업데이트

개발 PC마다 DB를 별도로 수동 수정하여 서로 다른 Schema가 만들어지는
방식은 피한다.

중앙 서버 전환 이후에는 하나의 기준 DB Schema를 유지한다.

------------------------------------------------------------------------

## 18. 수치 표시 원칙

기존에 확정된 업무 표시 기준은 유지한다.

-   단가/가격/개별원가: 정수 원, 소수점 발생 시 올림
-   중량: 소수점 둘째 자리
-   박스: 정수
-   환율: 소수점 둘째 자리
-   금액: 3자리 콤마
-   수수료 VAT: 원단위 절하

해당 원칙을 임의 변경하지 않는다.

------------------------------------------------------------------------

## 19. LOT 기본 원칙

LOT는 원칙적으로 독립적인 수동 Master 생성 대상이 아니라 다음 거래의
결과로 생성한다.

-   최초재고
-   매입
-   수입
-   이동
-   기타 재고발생 거래

LOT와 재고수불의 정합성을 우선한다.

------------------------------------------------------------------------

## 20. 거래 공통기반 원칙

기존에 구축한 다음 개념을 유지한다.

-   회사/전표/업무일자 기반 자동발번
-   `DRAFT → CONFIRMED → CANCELLED`
-   확정/취소 후 변경 제한
-   회계기간 OPEN/CLOSED
-   Audit
-   세금코드 Snapshot
-   권한 검사
-   API 우회 방지

신규 업무모듈은 가능하면 이 공통기반 위에 구현한다.

------------------------------------------------------------------------

## 21. 사용자·권한 원칙

기존 사용자/권한 구현 방향을 유지한다.

-   관리자 전체회사/전체메뉴
-   사용자별 회사 접근권한
-   메뉴별 CRUD 권한
-   API 공통 권한검사
-   자기 계정 잠금 방지
-   마지막 관리자 보호

단, 현재 DB Migration 정합성을 먼저 확인한다.

------------------------------------------------------------------------

## 22. MXMN_FinSales 관련 원칙

MXMN_FinSales는 파이낸싱 계약판매를 위한 독립 실행형 모듈이다.

현재 단계에서 MXMN과 물리적으로 합치지 않는다.

향후 업무적으로 공유할 수 있는 거래처, 상품, 계약, 출고, 정산 등이
발생하더라도 먼저 인터페이스/API/동기화 전략을 설계한 후 연결한다.

두 DB를 임의 JOIN하거나 직접 상대 프로젝트 DB 테이블을 수정하는 방식은
지양한다.

------------------------------------------------------------------------

## 23. 서버 전환 후 개발 원칙

향후 홈 서버가 중앙 서버가 되면 다음 구조를 기본으로 한다.

### Server

-   SQL Server
-   FastAPI
-   중앙 DB
-   필요 개발환경

### Client

-   PySide6 Client
-   API 접속
-   필요 개발환경

장기적으로 Client가 SQL Server에 직접 의존하는 부분은 줄이고 API Layer를
통한 접근을 확대한다.

------------------------------------------------------------------------

## 24. 현재 Work에게 요구되는 판단

Work 재개 시 다음을 먼저 판단해야 한다.

1.  Work 중단 당시 실제 마지막 완료 Commit은 무엇인가?
2.  상품매입 기능은 코드 기준으로 어디까지 완료됐는가?
3.  상품매입 개발 중 Work 한도 소진으로 미완성 상태가 Commit/Push됐는가?
4.  아니면 코드는 완성됐지만 홈 PC DB에 필요한 Migration만 실행되지
    않았는가?
5.  `tb_expense_code` 누락은 어떤 선행 Migration이 적용되지 않았기
    때문인가?
6.  현재 `mxmn_dev`를 최신 GitHub `main` 코드와 일치시키기 위한 정확한
    Migration 순서는 무엇인가?
7.  기존 데이터 손실 없이 이를 적용할 수 있는가?

이 판단이 끝나기 전에는 신규 MXMN 기능 개발을 시작하지 않는다.

------------------------------------------------------------------------

## 25. Work 재개 후 완료 기준

MXMN 복구/동기화 작업은 단순히 "Migration 실행 성공"으로 완료하지
않는다.

최소 다음 조건을 충족해야 한다.

-   DB Schema와 Models 일치
-   Migration 정상 완료
-   Migration 재실행 안전성 검토
-   pytest 통과
-   로그인 정상
-   사용자/권한 정상
-   주요 Master 정상
-   상품매입등록/수정 화면 정상
-   조회/신규/저장/수정 등 구현 범위 정상
-   API HTTP 500 없음
-   Git working tree clean
-   GitHub `main` Push 완료
-   `04_CURRENT_STATUS.md` 업데이트
-   필요한 Roadmap/DB 문서 업데이트

------------------------------------------------------------------------

# Work 재개용 핵심 지시

Work는 본 문서를 읽은 후 바로 신규 기능을 구현하지 말고 다음 순서로
진행한다.

1.  GitHub `mixbiz1/MixNMenu`의 `main` 최신 상태를 확인한다.
2.  기존 `docs/` 기준문서와 본 문서를 함께 읽는다.
3.  모든 Migration 파일과 현재 `mxmn_dev` Schema를 비교한다.
4.  Work 중단 시점에 상품매입 기능이 실제로 어디까지 완료됐는지
    판정한다.
5.  2026-09-21 Chat에서 실행된 `db_user_permission_migrate.py` 변경을
    고려한다.
6.  실패한 `db_purchase_migrate.py`와 누락된 `tb_expense_code`의 원인을
    추적한다.
7.  임의 테이블 생성 없이 올바른 Migration 체인을 복구한다.
8.  pytest 및 실제 UI/API 검증을 수행한다.
9.  정상화 후 문서를 최신 상태로 갱신한다.
10. 그 이후에 기존 Roadmap의 다음 개발단계로 진행한다.

본 문서는 기존 프로젝트 기준문서를 대체하지 않는다.

목적은 **Work 중단 이후 발생한 변경사항과 현재 실제 상태를 Work가
오해하지 않도록 연결하는 것**이다.
