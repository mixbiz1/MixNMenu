# MXMN MASTER HANDOFF — 2026-09-23 FINAL

**문서 성격:** Work 재개용 최종 상세 인수인계서  
**작성 기준:** 지난주 Work 중단 시점 이후 2026-09-23까지의 개발·서버화·Git/DB 검증 이력 + 2026-09-23 Chat에서 확정한 Chat/Work/모델 운영 원칙을 통합  
**중요:** 이 문서는 요약본이 아니라, Work가 별도의 긴 대화 이력을 다시 읽지 않아도 현재 상태·과거 경위·미완료 원인·금지사항·향후 협업방식을 충분히 이해하도록 만든 상세 기준서이다.

---

## 0. 이 문서를 읽는 방법과 최신성 원칙

1. 이 문서의 **현재 상태와 최신 결정이 과거 계획보다 우선**한다.
2. 과거에 실제로 수행·검증된 작업 이력은 보존한다. 다만 이후 역할 변경으로 더 이상 현재 계획이 아닌 내용은 **“과거 계획/검증 이력”**으로만 해석한다.
3. 특히 과거 문서에 있던 **“Lenovo IdeaPad 3(81W4, 12GB)를 MXMN-SERVER로 사용”** 계획은 폐기되었다. 최신 서버 대상은 **기존 모바일 PC(i4menu0, Ryzen 5 4500U, 8GB)** 이다.
4. 기존 홈 PC에서 완료한 Windows 11, SQL Server, DB, Python, Git, 백업 검증은 유효한 이력이지만, 새 MXMN-SERVER에 자동으로 적용된 것으로 간주하지 않는다.
5. **MXMN ERP의 상품매입 Migration 미완료 문제와 서버 전환 작업을 섞지 않는다.** 서버화 중 ERP Schema를 임의 수정하지 않는다.
6. Work는 신규 기능부터 시작하지 말고, 중단 지점의 Migration/실DB/코드 정합성 복구를 우선한다.

---

# Part I. 프로젝트 전체 맥락

## 1. MXMN의 목적과 사용자의 개발 방식

MXMN은 수입육류 유통·무역·정산·파이낸싱 업무를 통합하기 위한 Windows 중심 업무 시스템이다. 사용자는 전문 개발자가 아니며 Python, FastAPI, SQLAlchemy, PySide6, SQL Server 등의 세부 구현을 직접 작성하는 방식이 아니라, 실제 육류 수입·도매·파이낸싱 업무 지식과 현재 사용 중인 레거시 프로그램의 화면·프로세스·업무규칙을 AI에 제공하고 AI가 이를 분석·설계·코드화하는 방식으로 개발을 진행한다.

따라서 이 프로젝트에서 가장 중요한 역할 분담은 다음과 같다.

- **사용자:** 실제 업무 목적, 업무규칙, 화면 사용성, 결과 적합성을 판단하는 최종 업무 책임자.
- **일반 Chat:** 업무 요구사항 정리, 설계 검토, 오류 해석, 개발 순서 결정, Work 실행 명세 작성.
- **Work/Codex:** 실제 저장소·파일·코드·DB 관련 구현, 수정, 테스트, 검증.
- **VS Code/로컬 PC:** 사용자가 AI가 제공한 명령을 실행하고 실제 화면과 동작을 확인하는 검증 환경.
- **GitHub:** 검증된 코드와 문서의 공통 기준점.

사용자에게 코드를 이해해야만 다음 단계로 갈 수 있는 부담을 넘기지 않는다. 반대로 사용자의 실제 업무 의도를 AI가 임의로 추정하여 핵심 비즈니스 규칙을 바꾸지도 않는다.

## 2. 기술 스택과 프로젝트 구조

### 2.1 MXMN ERP

- 프로젝트 폴더: `C:\projects\MixNMenu`
- GitHub: `mixbiz1/MixNMenu`
- 기본 브랜치: `main`
- DB: MS SQL Server Express 2025, `mxmn_dev`
- Python 3.11+ 계열 / 현재 검증 이력상 Python 3.12.10
- FastAPI
- SQLAlchemy
- pyodbc
- PySide6
- VS Code
- Git/GitHub

### 2.2 MXMN_FinSales

파이낸싱/계약판매 업무는 ERP 완성 전에 과도하게 결합하지 않기 위해 별도 프로젝트로 분리하였다.

- 프로젝트 폴더: `C:\projects\MXMN_FinSales`
- GitHub: `mixbiz1/MXMN_FinSales`
- 기본 브랜치: `main`
- DB: `mxmn_finsales_db`
- Git 저장소: MixNMenu와 완전히 독립
- Python 실행환경: 현재 별도 venv를 만들지 않고 `C:\projects\MixNMenu\venv\Scripts\python.exe`를 공용 사용한 것이 검증됨
- 목적: 파이낸싱/계약판매 로직을 독립적으로 구현·검증하고, 검증된 비즈니스 로직만 향후 MXMN ERP와 인터페이스 또는 이식

**절대 원칙:** `MixNMenu`와 `MXMN_FinSales`는 Source/Git/DB가 독립이다. 프로젝트 폴더를 바꾸면 Git 저장소도 바뀐다. 두 프로젝트에서 Git 명령을 혼동하지 않는다.

---

# Part II. Work 중단 전후 개발 이력

## 3. 2026-09-16~09-18 집중 개발 구간

이 기간에는 MXMN 기반 기능이 빠르게 확장되었다. 화면이 보이거나 일부 기능이 동작한다고 해서 모든 기능이 완전히 마감된 것은 아니며, 이후 Migration 선행관계와 실DB 정합성 문제가 드러났다.

### 3.1 사용자·권한

완료/검증된 핵심 내용:

- 관리자 전체회사·전체메뉴 권한 유지
- 관리자 자신의 계정/마지막 관리자 잠금 방지
- 사용자별 회사 접근권한
- 메뉴별 조회/등록/수정/삭제(CRUD) 권한
- 권한 저장 후 재변경 가능
- 재로그인 후 권한 반영
- 공통 권한검사와 API 우회 방지 방향 적용
- `db_user_permission_migrate.py` 수행 과정에서 `tb_user.is_admin` 관련 오류가 있었고 이후 복구하여 Migration 완료

### 3.2 거래 공통기반

`db_trade_common_migrate.py`가 정상 완료되었고 다음 기반을 구성했다.

- 회사·전표·업무일자 기준 자동발번
- 전표 상태: `DRAFT → CONFIRMED → CANCELLED`
- 확정/취소 후 변경 제한
- 회계기간 `OPEN/CLOSED`
- 작성·수정·확정·취소 Audit
- 세금코드 `VAT10 / ZERO / EXEMPT` 스냅샷
- INPUT 경비코드 검증
- 당시 `pytest` 9개가 모두 통과한 이력이 있음

### 3.3 수치·표시 원칙

현재까지 확정된 공통 원칙:

- 단가/가격/개별원가: 정수 원, 소수점 발생 시 올림
- 중량: 소수점 둘째 자리까지
- 박스: 정수
- 환율: 소수점 둘째 자리까지
- 금액: 3자리 콤마
- 수수료 VAT: 원단위 절하

### 3.4 LOT와 초기자료

LOT는 독립적으로 남발하는 Master가 아니라 **매입/매출/이동 등 업무 결과로 생성되는 식별단위**라는 원칙을 확정했다.

초기자료 등록에서는 연속사업자의 시스템 전환을 위해 다음을 다룬다.

- 최초재고: 기준일·창고·상품·LOT·BOX·KG·개별원가
- 저장 시 LOT + 최초입고를 원자적으로 생성
- 생산일 입력 및 소비기한 자동계산(냉동 2년 - 1일 기준)
- 최초 생성 후 연결 데이터가 없는 범위에서 수정/삭제 가능하도록 검토·구현
- LOT 리스트: 날짜-전표-품목 연결
- 거래처 최초잔액: 미수/미지급 원거래를 만들고 이후 부분수금/지급 연결

### 3.5 코드·상품·창고·거래처

- 공통코드 / 상품공통코드 / 상품입력 화면
- 조회·새로고침·정렬(코드/가나다/ABC) 통일
- 엔터 검색·이동 UX
- 상품입력 좌측 계층 트리와 우측 브랜드·등급·부위·원산지·공장번호·포장·기타 조합
- 상품명 실시간 미리보기 및 평균중량 자동화
- 창고 Master: 보세 기본, 일반창고 선택, kg당/박스당/추가비용 on/off
- 창고 웹주소와 ID 관리, 사이트 이동 시 ID 복사 편의기능 요구
- 거래처 신규 기본값: 거래상태=거래처, 업무유형=일반, 매입/매출/계산서 발행대상
- 동일 사업자번호 복수코드 허용

### 3.6 경비코드 요구

향후 손익계산서·경비통계 등 경영자료로 확장할 수 있도록 계층형 코드로 설계한다.

최상위 예시:

- 매출
- 매입
- 매출총이익
- 판매관리비
- 영업이익
- 영업외수익
- 영업외비용
- 법인세비용
- 당기순이익

하위 항목은 직접 추가 가능하며, 신규·미사용 데이터는 삭제 가능하도록 한다.

### 3.7 상품매입등록/수정 — 현재 가장 중요한 미완료 지점

요구사항으로는 다음이 정리되어 있었다.

- 화면 명칭: `상품매입등록/수정`
- 매입처/상품 키워드 선택
- 과세 체크박스, 기본 면세
- 상단 `이력번호조회` → BL# 자동 채움
- 저장 시 LOT 자동 생성
- 합계 옆 할인 입력
- 기존 거래공통·권한·세금·LOT 원칙과 연결

그러나 `db_purchase_migrate.py` 실행 과정에서 문제가 발생했다. 한 차례 `total_discount_amount` 컬럼 오류가 수정된 이력이 있으나, 이후 재점검 과정에서 **실제 DB에 `tb_purchase`가 없거나 Migration이 `dbo.tb_expense_code`에 의존하는 선행관계 문제**가 확인되어 완결 상태로 볼 수 없게 되었다.

**현재 판단:** 상품매입 화면이 일부 표시되거나 코드가 존재하는 것과 Migration/실DB/Model/API/UI가 완전히 정합한 것은 별개다. 이 기능은 Work가 재개될 때 다시 종합 검증해야 하는 **미완료 Vertical Slice**다.

**금지:** 서버화 과정에서 `tb_purchase` 또는 `tb_expense_code`를 임의 `CREATE`하여 문제를 덮지 않는다.

---

## 4. Work 사용량 소진과 개발 중단의 의미

9/18~9/19 무렵 Work/Codex의 5시간 및 주간 공유 사용량이 소진되면서 Work 중심 개발이 중단되었다. 이 중단은 단순한 서비스 사용 제한이었지만, 결과적으로 다음 문제를 점검하는 계기가 되었다.

기존 방식은 사용자가 목적 메뉴를 제시하면 Work가 다음을 한 번에 수행하는 구조였다.

1. 레거시 DB와 기존 코드 분석
2. 사용자가 공유한 현재 화면/캡처 분석
3. 업무 요구사항 추론
4. 구현 가능한 UI/DB/API 설계
5. `.py` 및 Migration 작성
6. 테스트 가능한 형태 제공
7. 사용자가 VS Code에서 실행
8. 오류/UX 피드백
9. Work가 재분석·수정
10. 몇 차례 반복
11. 1차 통과 후 문서화
12. 중간 또는 최종 Git commit/push

이 방식은 비개발자인 사용자가 AI를 실질적인 개발자로 활용하기에는 매우 자연스럽고 효과적이었으나, Work가 **업무분석가 + 시스템설계자 + 개발자 + 테스터 + Git 관리자 + 문서작성자** 역할을 매 반복마다 모두 수행하여 주간 사용량이 빠르게 소진되는 문제가 있었다.

따라서 2026-09-23부터 개발 품질은 유지하되 Work가 꼭 필요한 작업에 집중하도록 협업 프로세스를 조정한다. 자세한 원칙은 Part VI에 기록한다.

---

# Part III. Git, DB, 백업 및 서버화 이력

## 5. Git/GitHub의 현재 운영 개념

Git 개념은 다음과 같이 이해하고 운영한다.

- `main`: 현재 로컬 PC에서 체크아웃한 브랜치
- `origin/main`: 마지막 `fetch/pull` 시점에 로컬 Git이 알고 있는 원격 `main`의 상태
- 실제 GitHub 원격은 다른 PC의 push로 바뀔 수 있으므로 작업 전 `fetch`로 원격 정보를 갱신하는 습관이 중요

기본 작업 전:

```powershell
git fetch
git status
git pull
```

기능 검증 후:

```powershell
git status
git add .
git commit -m "작업 내용"
git push
```

GitHub `main`은 검증된 공통 소스 기준점이다. 그러나 `git pull`을 무조건 실행하기보다 현재 폴더가 어느 프로젝트인지, working tree가 clean한지, 원격과 어떤 차이가 있는지 먼저 확인한다.

## 6. 2026-09-21~09-22 서버 준비를 위해 수행한 기존 홈 PC 작업

당시에는 기존 홈 12GB Lenovo IdeaPad 3(81W4)를 중앙 서버로 전환하려는 계획이었다. 이 계획 자체는 이후 변경되었지만, 그 PC에서 실제 완료한 검증 결과는 안전망 및 이전 소스로서 유효하다.

완료 이력:

- 로컬 및 USB 백업
- DB `.bak` 백업과 `RESTORE VERIFYONLY` 성공
- MBR → GPT 변환
- UEFI 전환
- Secure Boot 활성화
- TPM 2.0 확인
- Windows RE Enabled
- Windows 11 Pro 25H2 업그레이드
- Windows Update 최신 상태 확인
- SQL Server Authentication으로 `127.0.0.1,1433` 접속 확인
- `mxmn_dev` 존재/접속 확인
- `mxmn_finsales_db` 존재/접속 확인
- MixNMenu venv 정상
- Python 3.12.10 / pip 25.0.1 검증 이력
- MixNMenu Git: `main` clean, `origin/main`과 일치, 당시 commit `95f6151`
- MXMN_FinSales Git: `main` clean, `origin/main`과 일치, 당시 commit `0af1386`
- FinSales가 MixNMenu venv Python을 공용 사용하는 구조 확인

이 검증 결과는 **기존 홈 PC에 대한 완료 이력**이다. 새 서버 PC의 상태를 대신 증명하지 않는다.

---

# Part IV. 2026-09-23 최종 3대 PC 역할 재배치

## 7. 최신 역할 — 과거 HOME/OFFICE/MOBILE 명칭보다 우선

| 기존 구분 | CPU | RAM | 기존 장치명 | 최신 역할/장치명 |
|---|---|---:|---|---|
| 기존 모바일 | Ryzen 5 4500U | 8GB / 2667MT/s | `i4menu0` | **MXMN-SERVER** |
| 기존 홈 | Ryzen 5 4500U | 12GB | `Ideapad-slim-3` | **MXMN-DEV** |
| 기존 사무실 | Ryzen 5 7520U | 8GB / 5500MT/s | `MIXBIZ1` | **MXMN-WORK** |

### 7.1 변경 판단

- 기존 모바일과 기존 홈은 CPU가 동일한 Ryzen 5 4500U다.
- 전용 서버는 SQL Server Express + FastAPI 중심이며 소규모 사용 환경에서 CPU를 지속적으로 크게 소비하지 않는다.
- 서버는 일반 업무를 최소화하므로 8GB 모델을 전용 서버로 두는 것이 합리적이다.
- 개발/업무 PC는 브라우저, ChatGPT, VS Code, Python, PySide6, pytest, SSMS, Excel/PDF 등을 동시에 사용하므로 12GB RAM의 체감 가치가 더 크다.
- 사무실 PC는 RAM 8GB지만 Ryzen 5 7520U와 빠른 메모리를 사용하므로 업무와 필요 시 개발을 담당하는 WORK로 유지한다.

### 7.2 역할명의 의미

- **MXMN-SERVER:** 두 회사 공통 중앙 서버. `mxmn_dev`, `mxmn_finsales_db` 및 향후 공통 서비스를 호스팅할 수 있음.
- **MXMN-DEV:** 사용자가 주로 휴대하며 개발하는 PC. 일반 업무도 가능.
- **MXMN-WORK:** 사무실 업무 중심 PC. 필요 시 개발 가능.

WORK와 DEV는 설치 가능한 소프트웨어나 권한을 제한하는 이름이 아니다. 두 PC 모두 Git/Python/VS Code/SSMS 등 개발도구를 유지할 수 있다.

### 7.3 Windows 사용자 프로필

장치 이름만 변경하고 기존 Windows 사용자 계정과 `C:\Users\...` 프로필은 유지한다.

- `i4menu0` PC → 장치명 `MXMN-SERVER`
- `Ideapad-slim-3` → 장치명 `MXMN-DEV`
- `MIXBIZ1` → 장치명 `MXMN-WORK`

`C:\Users` 폴더를 server/dev/work에 맞추어 수동 Rename하지 않는다. Python venv, VS Code, Git credential, 환경변수 등 경로 의존 설정을 불필요하게 손상시킬 수 있다.

Hostname을 직접 참조하는 SQL Server/FastAPI/네트워크 설정은 이름 변경 후 별도 검증한다.

---

## 8. 최신 서버화 작업 순서

현재 서버화의 재개점은 **기존 모바일 PC(i4menu0)를 MXMN-SERVER로 전환하는 단계**다.

순서는 다음과 같다.

1. 기존 모바일 PC를 집에 두고 상시 전원·인터넷 연결이 가능한지 확인.
2. Windows 장치 이름을 `MXMN-SERVER`로 변경하고 재부팅. 사용자 계정/프로필은 변경하지 않음.
3. 재부팅 후 해당 PC 자체의 Windows 버전, SQL Server 구성요소, Python, Git 등 실제 설치 상태를 확인. 기존 홈 PC 검증 결과를 전제하지 않음.
4. 기존 홈 PC에 보관된 검증된 `mxmn_dev`, `mxmn_finsales_db` 백업을 새 서버로 안전하게 이전·복원. 원본과 백업 유지.
5. 새 서버에서 SQL Server Service, SQL Authentication, 두 DB 존재/접속, SQL Server 내부 Server Name 검증.
6. USB-LAN 유선 연결 우선. 고정 IP 또는 공유기 DHCP Reservation 구성.
7. SQL Server TCP/IP, Port 1433, Windows Firewall, SQL Server Browser 필요 여부 점검.
8. FastAPI를 새 서버에서 수동 실행하고 MXMN-DEV / MXMN-WORK에서 접근 시험.
9. 검증 후 FastAPI 및 필요한 서비스 자동 시작 방식 결정.
10. 전원 연결 시 Sleep 금지, 덮개 동작, Windows Update/자동 재부팅 등 24시간 운용 설정.
11. MXMN-DEV와 MXMN-WORK에서 GitHub 소스 + 중앙 API/DB 연결 검증.
12. 두 Client PC에서 정상 업무/개발이 확인된 뒤 각 PC의 로컬 DB 중복 운영을 단계적으로 종료. 백업은 유지.

### 서버화 중 절대 금지

- `db_purchase_migrate.py`를 서버화 목적에서 실행하지 않는다.
- `tb_purchase`, `tb_expense_code`를 임의 생성하지 않는다.
- 서버 전환과 상품매입 Migration 복구를 한 작업 세션에서 섞지 않는다.
- 새 서버 검증 전 기존 홈 PC의 DB나 백업을 삭제/덮어쓰지 않는다.

---

# Part V. MXMN ERP Work 재개 시 최우선 과제

## 9. 상품매입 Migration/Schema 정합성 복구

Work가 ERP 개발을 다시 시작할 때 신규 메뉴 구현보다 먼저 아래를 수행한다.

1. GitHub `mixbiz1/MixNMenu`의 `main` 최신 상태 확인.
2. 최소한 다음 문서를 먼저 읽는다.
   - `docs/04_CURRENT_STATUS.md`
   - `docs/10_DEVELOPMENT_ROADMAP.md`
   - `docs/13_POST_WORK_HANDOFF_20260921.md` (존재 시)
   - 본 최종 인수인계서
   - 관련 DB/도메인 설계문서
3. `db_*migrate.py` 전체와 실제 `mxmn_dev` Schema를 대조한다.
4. `tb_user.is_admin` 복구 이후 현재 권한 Schema 상태를 확인한다.
5. `tb_purchase` 부재 및 `db_purchase_migrate.py`의 `dbo.tb_expense_code` 의존 문제를 **임의 CREATE 없이 원래 설계와 Migration 순서에 맞게 해결**한다.
6. `models.py`, `main.py`, 관련 service/API/view 코드를 함께 대조한다.
7. 상품매입등록/수정 Vertical Slice의 Model/API/Service/UI/권한/LOT/세금/할인 로직을 실제 코드 기준으로 검증한다.
8. Migration → pytest → API → UI 순으로 검증한다.
9. 사용자가 로컬에서 실행할 명령과 확인 포인트를 순서대로 제공한다.
10. 실제 검증 후 `04_CURRENT_STATUS.md`, Roadmap 및 관련 문서를 갱신한다.
11. 정상 확인 후 의미 있는 단위로 GitHub `main`에 정리한다.

**완료 판정:** 화면이 뜨는 것만으로 완료가 아니다. DB Migration, 실제 Schema, Model, API, UI, 권한, LOT/재고 영향, 테스트, 문서가 서로 일치해야 완료다.

---

# Part VI. 2026-09-23 확정 AI 개발 운영 원칙

## 10. 왜 프로세스를 조정하는가

사용자는 개발자가 아니므로 Work의 완결적 구현 능력이 프로젝트의 핵심이다. 따라서 Work를 단순 코드 조각 생성기로 축소하지 않는다. 다만 Work가 매 반복마다 프로젝트 전체 분석·설계·구현·테스트·Git·문서화를 모두 수행하면 주간 사용량이 빠르게 소진되어 며칠간 개발이 중단될 수 있다.

목표는 **Work를 덜 쓰기 위해 사용자가 개발자가 되는 것**이 아니다. 목표는 **Chat과 사용자가 Work 전후의 판단·검증을 분담하여 Work가 실제 구현이 필요한 순간에 집중하도록 하는 것**이다.

## 11. 도구별 역할

| 주체/도구 | 주 역할 | 원칙 |
|---|---|---|
| **일반 Chat** | 업무 요구사항 정리, 화면/프로세스 설계, DB/도메인 원칙 검토, 오류 로그 해석, Work 지시문 작성, 인수인계/문서 구조화 | Work 실행 전에 가능한 한 요구와 완료조건을 확정한다. |
| **Work** | Git/문서/코드/DB를 종합 분석하여 합의된 기능 구현, 실제 파일 수정, 테스트, 필요한 문서 갱신 | 불명확한 핵심 업무규칙을 임의로 결정하지 않는다. 관련 범위부터 조사한다. |
| **Codex** | 코드 중심 구현·수정·디버깅·테스트 | Work와 공유 사용량이라는 점을 고려한다. |
| **사용자/VS Code** | 명령 실행, 화면 확인, 업무 적합성 판단, Traceback 제공, Git 동기화 확인 | 코드를 직접 이해/작성해야만 진행 가능한 구조로 만들지 않는다. |
| **GitHub main** | 검증된 소스와 문서의 공통 기준점 | 프로젝트 혼동, 확인 없는 덮어쓰기 금지. |

## 12. 표준 개발 사이클

### 12.1 Chat에서 요구사항·설계 확정

새 기능을 시작할 때 사용자는 업무 목적, 현재 화면, 레거시 동작, 원하는 결과를 설명한다. 화면 UX 문제는 캡처를 적극 활용한다.

Chat에서 먼저 다음을 정리한다.

- 업무 목적과 처리 흐름
- 입력/조회/수정/삭제 조건
- DB 및 데이터 관계
- API/UI 동작
- LOT·재고·거래·회계 영향
- 권한과 무결성
- 테스트/완료 조건
- 유지해야 할 기존 기능

### 12.2 Chat에서 Work 실행 명세 작성

Work에게 “전체 프로젝트를 다시 분석해서 알아서 설계하고 구현”시키는 방식은 꼭 필요할 때만 사용한다. 보통은 Chat에서 확정한 내용을 다음 형태로 넘긴다.

- 작업 목적
- 확정 업무규칙
- 확인할 관련 문서/파일
- 구현 범위
- 금지/비변경 사항
- Migration/API/UI/권한/테스트 범위
- 완료 조건
- 문서/Git 처리 범위

### 12.3 Work에서 실제 구현

Work는 관련 문서와 관련 코드를 우선 확인하고 필요할 때만 범위를 넓힌다. 기존 정상 기능을 최대한 보존하고 작은 Vertical Slice 단위로 구현한다.

### 12.4 사용자가 로컬 실행

대표 흐름:

```powershell
git fetch
git status
git pull
python <migration_script>.py
python -m pytest -q
python app.py
```

사용자는 화면과 실제 업무 동작을 확인한다.

### 12.5 오류/개선사항은 Chat에서 먼저 판별

오류가 나면 즉시 Work를 다시 부르기보다 먼저 Chat에 다음을 제공한다.

- Traceback 전체
- 문제가 발생한 화면 캡처
- 실제 입력값/결과와 기대 결과
- 필요 시 관련 코드 부분

Chat이 원인을 좁히고 코드 수정이 필요하다고 판단하면 Work에 구체적인 수정 명세를 전달한다.

### 12.6 완결 단위에서 Git/문서 정리

Work가 매 작은 시도마다 Git 작업까지 전적으로 맡을 필요는 없다. 사용자가 단순 Git 명령을 실행할 수 있다. 다만 의미 있는 체크포인트는 commit으로 남긴다.

예:

- DB/API 기반 완료
- 화면 CRUD 완료
- LOT/재고 연동 완료
- 테스트 및 문서화 완료

복잡한 conflict, branch 복구, history 정리가 필요할 때 Work의 도움을 받는다.

---

## 13. 모델 선택 원칙

모든 작업에 가장 높은 추론 수준/모델을 고정 사용하지 않는다. **정확성이 중요한 복잡한 영역에는 충분한 모델을 쓰되, 명세가 명확한 단순 작업은 더 가벼운 모델을 시험**한다.

### 13.1 일반 Chat

- **Instant:** 기본. 요구사항 논의, 화면 검토, Git 설명, 오류 해석, 다음 작업 결정, Work 지시문 작성.
- **Medium:** 여러 설계 선택지 비교, 데이터 구조와 업무 로직을 좀 더 깊게 검토할 때.
- **High:** LOT/재고/원가, 회계·파이낸싱, 권한·무결성, 대규모 구조 변경처럼 설계 오류의 영향이 큰 문제.

일반 Chat의 사용량은 Work/Codex 공유 사용량과 별도로 관리되는 영역으로 이해하되, Chat의 고추론 옵션에도 별도 사용 제한이 있을 수 있으므로 필요할 때만 올린다.

### 13.2 Work/Codex

사용 가능한 모델 구성이 UI에서 허용될 경우 다음을 기본 실험 원칙으로 한다.

- **Luna 계열:** 문구/버튼/아주 작은 UI 수정 등 매우 단순하고 명확한 변경.
- **Terra 계열:** 명세가 확정된 일반 CRUD, PySide6 화면, API, 테스트 등 일반 구현의 우선 후보.
- **Sol 계열:** 복잡한 DB/Migration, LOT/재고/원가, 거래 공통기반, 권한, 파이낸싱 계산, 여러 모듈에 걸친 설계, 원인 불명의 복잡한 버그.

**주의:** 모델별 실제 주간 한도 차감률을 고정 비율로 가정하지 않는다. 작업 복잡도, 컨텍스트, 실행시간, 도구 사용 등에 따라 달라질 수 있으므로 실측한다.

## 14. Work 주간 사용량 실측 관리

주간 한도가 100%로 갱신된 이후 일정 기간 다음을 기록한다.

| 작업명 | 사용 모델 | 시작 잔량 | 종료 잔량 | 작업 범위/비고 |
|---|---|---:|---:|---|
| 예: 상품매입 CRUD | Terra | 100% | 94% | DB/API/UI/테스트 |
| 예: 체크박스 수정 | Luna/Terra | 94% | 93% | 소형 UI |
| 예: LOT 구조 변경 | Sol | 93% | 82% | 복잡한 다중 모듈 |

예시 수치는 실제 값이 아니다. 1~2주 실측하여 MXMN의 소형/중형/대형 작업별 평균 소비량을 파악하고, Plus 유지/크레딧/플랜 변경 여부를 데이터로 판단한다.

**운영 목표:** 5시간 단기 한도보다 주간 누적 한도를 더 적극적으로 관리하여 매일 지속적으로 Work를 사용할 수 있도록 한다.

---

## 15. 캡처, 코드, 오류자료를 제공하는 기준

### 화면/UX

캡처 우선. 체크박스, 컬럼, 버튼 위치, 정렬, 포커스, 색상, 창 크기 등은 이미지가 코드보다 효율적이다.

### 실행 오류

Traceback 텍스트 우선. 가능하면 처음부터 마지막 줄까지 제공한다.

### 특정 로직

관련 함수/클래스/코드 부분 우선. 매우 긴 `.py` 전체를 반복해서 Chat에 붙이지 않는다. 전체 파일이 필요하면 Work가 저장소에서 직접 읽도록 한다.

### 프로젝트 전체 구조

`docs` 기준문서와 실제 저장소를 Work가 확인한다. 매번 프로젝트 전체 코드를 Chat에 복사하지 않는다.

---

# Part VII. 기준문서와 Work 행동규칙

## 16. MXMN 기준문서

Work는 프로젝트를 매번 처음부터 재해석하지 않도록 다음 문서를 장기 기준으로 활용한다.

- `00_PROJECT_BASELINE.md`
- `01_PROJECT_SPEC.md`
- `02_DOMAIN_MODEL.md`
- `03_DATABASE_DESIGN.md`
- `04_CURRENT_STATUS.md`
- `05_FOLDER_STRUCTURE.md`
- `10_DEVELOPMENT_ROADMAP.md`
- `11_CODEBASE_GAP_ANALYSIS.md`
- `12_MIGRATION_PLAN.md`
- `AI_SYSTEM_PROMPT.md`
- `13_POST_WORK_HANDOFF_20260921.md` (존재 시)
- 본 `MXMN_MASTER_HANDOFF_20260923_FINAL`

특히 `04_CURRENT_STATUS.md`는 **현재 구현 완료 상태, 미완료 상태, 다음 작업**을 정확히 유지해야 한다.

## 17. Work가 반드시 따라야 할 작업 원칙

1. 작업 시작 시 `04_CURRENT_STATUS.md`, 본 인수인계서, 해당 작업 관련 문서를 먼저 확인한다.
2. 사용자와 Chat에서 이미 확정한 요구사항을 불필요하게 다시 설계하지 않는다.
3. 불명확한 핵심 업무규칙은 임의 결정하지 말고 Chat/사용자에게 확인한다.
4. 기존 정상 기능을 최대한 유지하고 필요한 범위만 변경한다.
5. 가능한 한 작은 Vertical Slice로 구현한다.
6. DB 변경은 Migration, 실제 Schema, 기존 데이터 영향, Model/API 의존성을 함께 검토한다.
7. API/UI뿐 아니라 권한·무결성·LOT·재고·세금·거래공통기반 영향도 확인한다.
8. 구현 후 가능한 자동 테스트와 실행 검증을 수행하고 결과를 명확히 보고한다.
9. 사용자가 로컬에서 실행해야 할 명령을 순서대로 제공한다.
10. 단순 Git 명령은 사용자가 직접 수행할 수 있도록 안내하고, 복잡한 Git 작업에 Work를 집중한다.
11. 기능 검증 후 `04_CURRENT_STATUS.md` 등 필요한 문서를 갱신한다.
12. 매 작업마다 전체 프로젝트를 처음부터 광범위하게 재분석하지 않는다. 관련 범위부터 확인하고 필요할 때 확장한다.
13. Work/Codex 사용량을 고려하되 **DB 무결성·재고·회계·권한·파이낸싱 등 핵심 정확성은 사용량 절약보다 우선**한다.
14. “동작해 보임”과 “완료”를 구분한다. 완료는 코드·DB·Migration·API·UI·테스트·문서가 정합한 상태다.
15. 서버 인프라 변경과 ERP Schema 복구를 같은 작업 흐름에서 섞지 않는다.
16. `MixNMenu`와 `MXMN_FinSales`의 폴더/Git/DB를 혼동하지 않는다.

---

# Part VIII. 현재 상태와 다음 행동

## 18. 현재 상태 표

| 영역 | 현재 상태 | 다음 행동 |
|---|---|---|
| MXMN ERP | 기반 기능 다수 구현. 상품매입 Migration/Schema 정합성 미완료 | Work 재개 시 Migration/실DB/코드 정합성 복구 최우선 |
| MXMN_FinSales | 독립 Repo/DB로 분리, 투트랙 개발 | 독립 개발·검증, 향후 검증 로직만 MXMN에 연결 |
| Git | 두 프로젝트 독립 `main` 운영 | 각 PC 작업 전후 fetch/status/pull/push 습관화 |
| Python | MixNMenu venv 검증, FinSales 공용 사용 이력 | 현재 구조 유지, 새 서버에서는 실제 상태 재검증 |
| DB | 기존 홈 PC에서 두 DB 접속 및 백업 검증 완료 | 새 MXMN-SERVER로 안전 이전·복원 후 재검증 |
| 백업 | 로컬+USB, VERIFYONLY 성공 이력 | 새 서버 전환 완료까지 안전망 유지 |
| 서버 | 대상이 기존 모바일 PC로 최종 변경 | 장치명 MXMN-SERVER 변경부터 단계별 진행 |
| AI 운영 | 과거 Work 완결형 반복으로 주간 한도 소진 경험 | Chat 설계/오류판단 + Work 구현/검증 분담, 모델/사용량 실측 |

## 19. 지금부터의 우선순위

서버화 작업을 진행하는 세션이라면:

1. 기존 모바일 PC → `MXMN-SERVER` 장치명 변경
2. 해당 PC 자체 환경 재검증
3. DB 안전 이전/복원
4. SQL Server 네트워크화
5. FastAPI 외부 Client 접근 검증
6. MXMN-DEV / MXMN-WORK 중앙 연결 검증
7. 안정화 후 로컬 DB 중복 운영 축소

ERP 개발을 재개하는 세션이라면:

1. GitHub main + docs 최신 상태 확인
2. Migration 전체와 실DB Schema 대조
3. `tb_purchase` / `tb_expense_code` 선행관계 문제 복구
4. 상품매입 Vertical Slice 종합 검증
5. 테스트/사용자 실행 검증
6. 문서/Git 정리
7. 그 다음 신규 기능

**두 흐름은 서로 섞지 않는다.**

---

# Part IX. Work 재개용 직접 지시문

## 20. MXMN ERP Work 재개 지시

```text
MXMN_MASTER_HANDOFF_20260923_FINAL 문서를 최우선 인수인계 기준으로 읽고 작업을 재개해 주세요.

1. GitHub mixbiz1/MixNMenu main 최신 상태를 기준으로 시작합니다.
2. docs/04_CURRENT_STATUS.md, docs/10_DEVELOPMENT_ROADMAP.md,
   docs/13_POST_WORK_HANDOFF_20260921.md(존재 시), 관련 설계문서와 본 인수인계서를 먼저 읽습니다.
3. 신규 기능부터 시작하지 말고 Work 중단 지점의 Migration/실DB/코드 정합성을 복구합니다.
4. db_*migrate.py 전체와 실제 mxmn_dev schema를 대조합니다.
5. tb_user.is_admin 복구 이후 현재 상태를 확인합니다.
6. tb_purchase 부재 및 db_purchase_migrate.py의 dbo.tb_expense_code 의존 문제를
   임의 CREATE 없이 원래 설계/Migration 순서에 맞게 해결합니다.
7. 상품매입등록/수정 Vertical Slice의 Model/API/Service/UI/권한/LOT/세금/할인 로직을
   실제 코드 기준으로 검증합니다.
8. pytest + API + UI 실행 검증을 완료합니다.
9. 사용자가 로컬에서 실행할 명령과 확인 포인트를 순서대로 알려줍니다.
10. 실제 검증 완료 후 CURRENT_STATUS/Roadmap/관련 문서를 갱신합니다.
11. Git은 의미 있는 검증 단위로 정리하며, 단순 명령은 사용자가 직접 실행할 수 있도록 안내합니다.
12. 핵심 업무규칙이 불명확하면 임의 추정하지 말고 먼저 Chat/사용자와 확정합니다.
13. 서버화 작업과 ERP Schema 복구를 섞지 않습니다.
```

## 21. 서버화 재개 지시

```text
현재 서버 대상은 과거의 12GB 홈 노트북이 아니라 기존 모바일 PC입니다.

최신 역할:
- 기존 모바일 Ryzen 5 4500U / 8GB / i4menu0 → MXMN-SERVER
- 기존 홈 Ryzen 5 4500U / 12GB / Ideapad-slim-3 → MXMN-DEV
- 기존 사무실 Ryzen 5 7520U / 8GB / MIXBIZ1 → MXMN-WORK

Windows 사용자 계정과 C:\Users 프로필은 변경하지 않고 장치 이름만 변경합니다.
기존 홈 PC에서 완료한 Windows 11 Pro 25H2, SQL Server/DB, Python, Git, 백업 검증은 유효한 과거 완료 이력이지만 새 서버에 자동 적용된 것으로 보지 않습니다.

현재 서버화 재개점은 i4menu0 PC의 Windows 장치 이름을 MXMN-SERVER로 변경하는 단계입니다.
위험하거나 재부팅/네트워크/DB에 영향을 주는 작업은 한 단계씩 안내하고 사용자의 실행 결과를 확인한 뒤 다음 단계로 진행합니다.
MXMN ERP 상품매입 Migration 문제는 이 서버화 세션에서 수정하지 않습니다.
```

---

# Part X. 절대 잊지 말아야 할 최종 원칙

1. **MXMN은 업무 시스템이다.** 기술적으로 편한 방향보다 실제 업무 규칙과 데이터 무결성이 우선한다.
2. **사용자는 개발자가 아니다.** 사용자가 업무판단과 실행검증에 집중할 수 있도록 AI가 기술 구현을 책임 있게 지원한다.
3. **Chat은 생각하고 결정하는 곳, Work/Codex는 실제 프로젝트를 구현하는 곳, VS Code는 사용자가 실행·검증하는 곳, GitHub는 검증된 MXMN을 기록하는 곳**으로 운영한다.
4. Work 사용량을 줄이기 위해 정확성을 희생하지 않는다. 대신 불필요한 전체 재분석, 반복 Git 작업, 명세 없는 시행착오를 줄인다.
5. 화면이 뜨거나 일부 동작한다고 완료가 아니다. DB Migration·실Schema·Model·API·UI·권한·테스트·문서가 맞아야 완료다.
6. GitHub `main`은 공통 기준점이지만 작업 전 현재 폴더와 Git 상태를 확인한다.
7. MXMN ERP와 MXMN_FinSales는 독립 Source/Git/DB다.
8. 중앙 서버화의 목적은 DB와 API를 한 곳에 두는 것이며, WORK/DEV에서의 개발을 금지하는 것이 아니다.
9. 새 기능보다 현재 중단 지점의 정합성 복구가 먼저다.
10. 서버 인프라 작업과 ERP Schema 수정은 분리한다.
11. 핵심 업무규칙은 AI가 임의 추정하지 않는다. 불명확하면 Chat에서 사용자와 확정한 후 Work가 구현한다.
12. 중요한 변경은 작은 Vertical Slice와 검증 가능한 체크포인트로 진행한다.

---

**이 문서가 2026-09-23 현재 MXMN 프로젝트의 최종 Master Handoff 및 AI 개발 운영 기준이다.**
