# MXMN 중앙 서버 구축 인수인계 및 Work 운영 원칙

**기준일:** 2026-09-25\
**프로젝트:** MXMN ERP / MixNMenu\
**GitHub:** `mixbiz1/MixNMenu` / `main`\
**최신 확인 Commit:** `1fe3617c30eb65a134a9d10125933838f7029038`
(`refactor: centralize desktop API base URL`)

------------------------------------------------------------------------

## 1. 이번 작업의 목적

기존 3대 PC에 분산되어 있던 개발/DB 운용 구조에서, **MXMN-SERVER를 중앙
DB + FastAPI 서버로 사용하고 MXMN-DEV/MXMN-WORK가 클라이언트 및 개발
PC로 접속하는 구조**로 전환한다.

최종 목표 구조:

``` text
MXMN-DEV / MXMN-WORK
  PySide6 Desktop Client
        │
        │ Tailscale VPN
        ▼
MXMN-SERVER
  FastAPI :8000
        │
        ▼
SQL Server Express :1433
  └─ mxmn_dev
```

정상 업무 흐름에서는 DEV/WORK의 PySide6가 서버 SQL에 직접 연결하는 것이
아니라 **FastAPI를 통하여 업무 처리**한다. SQL 직접 연결은 인프라/개발
진단용으로만 사용한다.

------------------------------------------------------------------------

# 2. MXMN-SERVER 구축 완료 현황

## 2.1 장비 및 역할

-   서버명: `MXMN-SERVER`
-   Windows: Windows 11 Pro 25H2
-   Python: 3.12.10
-   Git: 2.55.0.windows.5
-   SQL Server: SQL Server 2025 Express
-   프로젝트 경로: `C:\projects\MixNMenu`
-   기존 Windows 사용자 프로필 경로는 변경하지 않음.
-   서버는 중앙 DB + FastAPI 역할을 담당한다.
-   MXMN-DEV와 MXMN-WORK는 계속 개발도 가능하지만 운영 DB/API는 중앙
    서버를 사용한다.

## 2.2 SQL Server

확인/정리 완료:

-   Instance: `MXMN-SERVER\SQLEXPRESS`
-   SQL Server 내부 `@@SERVERNAME`도 `MXMN-SERVER\SQLEXPRESS`로 수정
    완료
-   `mxmn_dev` ONLINE
-   `mxmn_finsales_db` ONLINE
-   Mixed Mode 사용
-   `mxmn_user` SQL Login 정상
-   `mxmn_dev`의 `mxmn_user` SID 재연결 완료
-   DEV에서 실제 `mxmn_user` 로그인 성공
-   `sa`는 SQL 관리용, `mxmn_user`는 MXMN DB/애플리케이션 연결용,
    `admin`은 PySide6 프로그램 관리자 계정이라는 역할 구분 유지

서버 이전 전 보호 백업:

-   `C:\MXMN_Backup\SERVER_PRE_RESTORE\mxmn_dev_SERVER_pre_restore_20260924.bak`
-   `C:\MXMN_Backup\SERVER_PRE_RESTORE\mxmn_finsales_db_SERVER_pre_restore_20260924.bak`

DEV에서 가져온 이전 기준 백업도 VERIFY 후 복원 완료:

-   `C:\MXMN_Backup\mxmn_dev_20260921_pre_server.bak`
-   `C:\MXMN_Backup\mxmn_finsales_db_20260921_pre_server.bak`

**주의:** 서버 구축 과정에서 ERP schema migration은 수행하지 않았다.
`db_purchase_migrate.py` 등 DB 구조 변경 스크립트를 서버 구축 작업과
혼합하지 않는다.

## 2.3 SQL 자동 시작

재부팅 후 확인 결과:

``` text
MSSQL$SQLEXPRESS
State            = Running
StartMode        = Auto
DelayedAutoStart = True
```

즉 SQL Server는 **자동(지연된 시작)** 상태이다. 실제 재부팅 시험에서
Windows 로그인 전에도 MXMN 프로그램 로그인과 DB 접근이 성공했으므로 현재
설정을 변경할 필요가 없다.

------------------------------------------------------------------------

# 3. 네트워크 및 Tailscale

## 3.1 LAN

-   MXMN-SERVER 유선 LAN: `192.168.0.53`
-   Realtek USB GbE, 1Gbps
-   ipTIME DHCP 예약으로 `192.168.0.53` 고정
-   서버는 평상시 유선 LAN 사용
-   Wi-Fi는 평상시 OFF, 필요 시 비상용으로 사용

LAN 품질 시험:

-   Gateway 100회 ping: 손실 0%
-   인터넷 회선 측정: 약 Download 461Mbps / Upload 426Mbps
-   서버 운용에 충분한 상태

## 3.2 Tailscale

-   MXMN-SERVER: `100.72.3.34`
-   MXMN-DEV: `100.125.227.3`
-   DEV를 휴대폰 테더링으로 외부망에 둔 상태에서도 SERVER 연결 성공
-   Tailscale ping은 DERP를 거친 후 direct 연결까지 확인
-   DEV → SERVER TCP 1433 성공
-   DEV → SERVER TCP 8000 성공
-   FastAPI `/docs` HTTP 200 확인

향후 직원용 DEV/WORK 원격 접속은 Tailscale을 사용한다.

**고객 외부 접속은 별도 설계한다.** 고객에게 SQL 1433을 공개하거나
직원용 VPN 구조를 그대로 제공하지 않는다. 향후 고객용 서비스는 HTTPS
기반 Web/API 계층을 별도로 설계한다.

------------------------------------------------------------------------

# 4. 방화벽 최종 상태

## SQL Server

SQL Server는 고정 포트 `1433` 사용.

-   `MXMN SQL Server 1433 - LAN`
    -   TCP 1433
    -   Remote: `192.168.0.0/24`
    -   Private
-   `MXMN SQL Server 1433 - Tailscale`
    -   TCP 1433
    -   Remote: `100.64.0.0/10`
    -   Private

SQL Browser는 필요하지 않아 중지 상태 유지.

## FastAPI

-   `MXMN FastAPI 8000 - Tailscale`
    -   TCP 8000
    -   Tailscale 범위만 허용

Windows가 자동 생성했던 일반 `Python` 인바운드 규칙은 최종적으로 모두
비활성화하였다.

비활성화 후 DEV에서:

``` powershell
(Invoke-WebRequest http://100.72.3.34:8000/docs -UseBasicParsing).StatusCode
```

결과 `200` 확인.

따라서 FastAPI는 일반 Python 공개 허용에 의존하지 않고 **MXMN 전용
Tailscale 방화벽 규칙으로 정상 작동**한다.

------------------------------------------------------------------------

# 5. API 주소 중앙화

## 문제

기존 PySide6 코드 여러 곳에 다음 주소가 직접 하드코딩되어 있었다.

``` text
http://127.0.0.1:8000
```

이 구조에서는 DEV에서 프로그램을 실행할 때 DEV 자신의 localhost
FastAPI를 찾으므로 중앙 SERVER에 접속할 수 없었다.

## 변경

Work를 이용해 API 주소 중앙화 리팩터링 수행.

추가:

-   `api_config.py`

기본 정책:

``` text
API_BASE_URL
기본값 = http://127.0.0.1:8000/api/v1
```

실제 `.env`에서 PC별 API 주소를 결정한다.

MXMN-DEV:

``` text
API_BASE_URL=http://100.72.3.34:8000/api/v1
```

SERVER는 기본 localhost를 사용할 수 있다.

주요 변경 파일:

-   `api_config.py`
-   `app.py`
-   `.env.example`
-   `views/account_reg.py`
-   `views/common_code_reg.py`
-   `views/company_reg.py`
-   `views/expense_code_reg.py`
-   `views/goods_common_code_reg.py`
-   `views/lot_reg.py`
-   `views/mxmn_main_window.py`
-   `views/opening_balance_reg.py`
-   `views/opening_inventory_reg.py`
-   `views/password_change.py`
-   `views/product_reg.py`
-   `views/purchase_reg.py`
-   `views/user_permission_reg.py`
-   `views/user_reg.py`
-   `views/warehouse_reg.py`

검증:

-   Python 문법/Import 정상
-   기존 테스트 16개 통과
-   실제 사용 소스의 API 하드코딩 제거
-   localhost 기본값 정상
-   SERVER Tailscale 주소 적용 정상
-   DEV 실제 로그인 정상
-   거래처 조회 정상
-   창고 조회 정상
-   공통코드 입력/조회/삭제 정상

GitHub 반영 Commit:

`1fe3617c30eb65a134a9d10125933838f7029038`

------------------------------------------------------------------------

# 6. FastAPI 자동 실행

## 실행 명령 검증

VS Code나 venv 수동 활성화 없이 다음 방식으로 실행 가능함을 확인했다.

``` powershell
& "C:\projects\MixNMenu\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir "C:\projects\MixNMenu"
```

## Windows 작업 스케줄러

작업명:

`MXMN FastAPI Server`

주요 설정:

-   트리거: 시스템 시작 시
-   사용자의 로그온 여부에 관계없이 실행
-   가장 높은 수준의 권한으로 실행
-   프로그램: `C:\projects\MixNMenu\venv\Scripts\python.exe`
-   인수: `-m uvicorn main:app --host 0.0.0.0 --port 8000`
-   시작 위치: `C:\projects\MixNMenu`
-   요청 시 실행 허용
-   놓친 경우 가능한 빨리 실행
-   실패 시 1분 간격 / 3회 재시도
-   장시간 실행 시 강제 종료 옵션 해제
-   이미 실행 중이면 새 인스턴스 실행 안 함

수동 실행 후 DEV `/docs` = HTTP 200 확인.

SERVER 재부팅 후 **Windows 로그인하지 않은 상태**에서도 DEV `/docs` =
200 확인.

그 상태에서 DEV PySide6 `admin` 로그인까지 성공.

따라서:

``` text
Windows 부팅
 → SQL Server 자동 기동
 → Tailscale 자동 연결
 → FastAPI 자동 기동
 → DEV 원격 접속
 → 프로그램 로그인/DB 사용
```

전체 무인 부팅 경로가 실제 검증되었다.

------------------------------------------------------------------------

# 7. 서버 전원 운영 설정

현재 활성 전원 구성표:

`고성능`

AC 전원 사용 시:

-   자동 절전: 사용 안 함
-   덮개 닫기: 아무 작업 안 함
-   화면 꺼짐은 허용 가능하며 서버 동작과 무관

따라서 화면이 꺼져도 서버는 계속 동작한다.

------------------------------------------------------------------------

# 8. Git 정리

오래된 폴더:

`참고용-수정되거나 사용안하는 화일모음`

은 사용자 판단에 따라 삭제했다.

처음에는 Git 비추적 폴더로 오판했으나, 삭제 후 `git status`에서 tracked
파일임이 확인되었다. Git의 한글 경로 quoting/escape 때문에 최초 검색
결과를 잘못 해석한 것이 원인이었다.

삭제는 사용자가 원래 원했던 내용이므로 그대로 유지하고 GitHub에 반영
완료.

관련 commit:

`ecadf19` --- obsolete reference files 제거

API 중앙화 이후 최신:

`1fe3617` --- API base URL 중앙화

SERVER도 `git pull` 후:

``` text
1fe3617 (HEAD -> main, origin/main, origin/HEAD)
```

확인 완료.

------------------------------------------------------------------------

# 9. Work 사용 과정에서 확인된 문제

이번 API 중앙화 자체는 Work가 정상적으로 수행했다.

그러나 작업 완료 후 GitHub push 단계에서 **GitHub 인증 정보 문제로
push가 거절**되었고, Work가 우회방법을 탐색하고 해결하는 데 약 **5분
42초**를 사용했다.

이 문제는 이번만의 문제가 아니며, 이전 Work 사용에서도 Git/GitHub 인증
문제 해결에 불필요한 시간과 사용량을 소비한 사례가 있었다.

Work의 주간 사용량은 한정되어 있으므로 이런 작업은 비용 대비 가치가
낮다.

------------------------------------------------------------------------

# 10. MXMN 개발 도구별 역할 --- 앞으로의 고정 원칙

## Chat

담당:

-   사용자와 요구사항 정리
-   설계/업무 규칙 확정
-   단계별 검증 지시
-   서버/네트워크/SQL/Git 문제 해결
-   Work 작업 지시문 작성
-   Work 결과 검토
-   개발 진행 순서 관리
-   인수인계 문서화

특징:

-   짧고 반복적인 확인
-   사용자 PC에서 한 단계씩 실행
-   위험 작업 전 상태 확인
-   Git 인증/동기화 문제는 우선 Chat에서 처리

## Work

담당:

-   여러 파일을 실제로 수정하는 개발 작업
-   코드베이스 분석
-   구현
-   테스트
-   필요한 문서 업데이트
-   commit 생성

Work가 **하지 말아야 할 기본 업무**:

-   GitHub 인증 오류 장시간 해결
-   push 실패 후 여러 우회방법 반복 탐색
-   서버/Windows 설정 시행착오
-   이미 Chat에서 할 수 있는 단순 Git 명령
-   단순 `git pull/status/log`
-   긴 환경 진단
-   사용자가 직접 1\~2개 명령으로 확인할 수 있는 작업

## VS Code

-   프로젝트 소스 확인/편집
-   프로젝트 터미널
-   `git pull`
-   `git status`
-   Python 실행/테스트
-   DEV 개발환경의 기본 작업공간

MXMN 개발 세션은 편의상:

``` text
VS Code
 → C:\projects\MixNMenu
 → venv 활성화
 → Git/Python 작업
```

순서로 통일한다.

Git 자체는 venv와 무관하지만 이후 Python 작업을 위해 개발 세션 시작 시
venv를 활성화한다.

## Windows PowerShell

SERVER의 Windows 관리에 사용:

-   네트워크
-   Tailscale
-   방화벽
-   SQL Server 서비스
-   전원/절전
-   작업 스케줄러 진단
-   Windows 시스템 상태

------------------------------------------------------------------------

# 11. Work 자원 절약을 위한 필수 운영 규칙

## 원칙 1 --- Work에는 "완결된 개발 단위"만 맡긴다

좋은 예:

> API 주소를 공통 설정으로 중앙화하고 관련 실제 사용 파일을 수정한 뒤
> 테스트하고 commit까지 수행.

나쁜 예:

> GitHub가 왜 안 되는지 조사하고 어떻게든 push까지 해줘.

Work의 고가 자원은 **코드를 이해하고 수정하고 검증하는 일**에 집중한다.

## 원칙 2 --- 기본 종료점은 `commit`

앞으로 Work의 기본 완료 기준:

``` text
분석
→ 코드 수정
→ 테스트
→ 변경사항 보고
→ git commit
→ STOP
```

`push`는 기본 업무에서 제외한다.

## 원칙 3 --- Push는 로컬에서 수행

기본:

``` text
Work: commit hash 전달
        ↓
Chat/사용자 로컬 환경
        ↓
git status
git log -1 --oneline
git push
```

GitHub 인증이 이미 정상인 환경에서 단 한 번의 push로 성공할 것이 확실한
경우만 Work push를 허용할 수 있다.

## 원칙 4 --- Git 인증 오류 1회 발생 시 즉시 중단

Work에서 push를 허용한 경우에도:

``` text
git push 성공
 → 종료

git push 인증 오류
 → 즉시 STOP
 → 오류 내용과 commit hash만 보고
```

**Work가 인증 우회방법을 탐색하지 않는다.**

Chat에서 해결한다.

## 원칙 5 --- 동일 문제 반복 탐색 금지

어떤 명령/접근이 실패하면:

1.  실패 원인 한 번 분석
2.  코드 작업과 무관하면 중단
3.  사용자에게 결과 보고
4.  Chat으로 넘김

"될 때까지 여러 방법 시도"를 Work의 기본 행동으로 두지 않는다.

## 원칙 6 --- 작업 범위를 명시적으로 잠근다

Work 지시문에 항상 포함:

``` text
이번 작업 범위는 ○○만입니다.
DB migration 금지.
관련 없는 리팩터링 금지.
환경/인프라 변경 금지.
Git 인증 문제 해결 금지.
테스트 후 commit까지만 수행.
```

범위 밖 문제는 발견만 보고하고 수정하지 않는다.

## 원칙 7 --- DB Migration은 별도 승인

서버 구축, UI 수정, API 설정 변경 중에는 migration을 실행하지 않는다.

Migration이 필요한 개발은:

``` text
왜 필요한지
→ 영향 테이블
→ 백업 여부
→ 실행 스크립트
→ 롤백 방법
```

을 먼저 확인하고 별도 단계로 수행한다.

## 원칙 8 --- Work에게 긴 수동 검증을 맡기지 않는다

GUI 실행 후 사람이 눈으로 확인해야 하는 사항은 사용자가 DEV에서
검증한다.

Work는:

-   syntax
-   import
-   pytest
-   정적 검색
-   자동화 가능한 검증

까지 담당한다.

실제:

-   로그인 화면
-   메뉴 열림
-   조회 결과
-   저장/삭제 UX

등은 DEV에서 사용자가 확인한다.

## 원칙 9 --- GitHub는 중앙 전달 지점, 자동 동기화가 아니다

``` text
DEV push → GitHub 변경
```

이 되어도 SERVER/WORK가 자동 변경되는 것은 아니다.

각 PC에서 필요할 때:

``` text
git pull
```

을 명시적으로 수행한다.

이 원칙은 서버 안정성을 위해 유지한다.

## 원칙 10 --- 서버는 검증된 commit만 pull

SERVER에서 직접 개발하지 않는다.

기본 흐름:

``` text
Work/DEV에서 개발
→ 테스트
→ commit
→ GitHub push
→ DEV 실제 프로그램 검증
→ SERVER git pull
→ FastAPI 재시작/자동실행 검증
```

SERVER는 운영 역할이므로 실험적 코드의 첫 실행 장소로 사용하지 않는다.

------------------------------------------------------------------------

# 12. 표준 MXMN 개발 프로세스

## A. 작업 시작

1.  Chat에서 요구사항 정리
2.  범위/DB 영향/검증방법 확정
3.  필요한 경우 Work용 작업지시문 생성

## B. Work

1.  최신 `main` 확인
2.  지정 범위만 분석
3.  코드 수정
4.  자동 테스트
5.  변경내용 보고
6.  commit
7.  commit hash 보고
8.  STOP

## C. Git 전달

로컬 인증 정상 환경에서:

``` powershell
git push
```

문제 발생 시 Work를 다시 사용하지 않고 Chat에서 해결.

## D. DEV 검증

``` powershell
git pull
```

이후:

-   프로그램 실행
-   로그인
-   조회
-   필요한 최소 CRUD
-   회귀 여부 확인

## E. SERVER 반영

DEV 검증 성공 후:

``` powershell
git pull
```

FastAPI 재기동 또는 서비스 재시작 후 HTTP/API 확인.

## F. 문서화

기능 완료 시:

-   `04_CURRENT_STATUS.md`
-   관련 기준 문서
-   필요 시 인수인계 문서

업데이트.

------------------------------------------------------------------------

# 13. Work에 사용할 표준 지시문 템플릿

``` text
MXMN 개발을 GitHub mixbiz1/MixNMenu의 main 최신 소스를 기준으로 진행합니다.

[이번 작업]
- 목표:
- 수정 대상:
- 유지해야 할 기존 기능:
- 금지 사항:

[필수 원칙]
1. 이번 요청 범위 밖의 기능은 수정하지 마세요.
2. DB schema/migration은 명시적으로 요청하지 않는 한 실행하지 마세요.
3. .env 및 비밀번호/인증정보를 Git에 포함하지 마세요.
4. 관련 없는 리팩터링, 패키지 변경, 환경 변경을 하지 마세요.
5. 자동화 가능한 문법/import/test 검증을 수행하세요.
6. 실제 GUI 업무 검증은 제가 DEV에서 수행합니다.
7. 변경 완료 후 git commit까지만 수행하세요.
8. GitHub push는 수행하지 마세요.
9. commit hash, 변경 파일, 테스트 결과, DEV에서 확인할 항목만 보고하고 종료하세요.
10. Git/GitHub 인증 문제를 해결하거나 우회방법을 탐색하지 마세요.

완료 기준:
코드 수정 → 자동검증 → commit → 결과 보고 → STOP
```

이 템플릿을 앞으로 Work 작업의 기본 머리말로 사용한다.

------------------------------------------------------------------------

# 14. 다음 작업

오늘은 MXMN-WORK 설정을 진행하지 않는다.

다음 작업 시작점:

1.  MXMN-WORK 부팅
2.  GitHub 최신 `main` 확인/pull
3.  Tailscale 설치/로그인 및 SERVER 연결
4.  WORK `.env`의 `API_BASE_URL` 설정
5.  FastAPI 8000 연결 확인
6.  PySide6 로그인/조회 확인
7.  필요 시 SQL 직접 연결은 진단 목적으로만 확인
8.  SERVER/DEV/WORK 3대 최종 역할 및 운영절차 문서 확정

그 후 중앙 서버 구축 1차 완료 선언 및 기존 분산 DB 운용 정리 여부를
판단한다.

------------------------------------------------------------------------

# 15. 현재 기준 결론

2026-09-25 현재 MXMN-SERVER는 **중앙 SQL Server + FastAPI 서버로서 실제
운용 가능한 1차 상태**에 도달했다.

특히 다음이 실제 검증되었다.

-   서버 재부팅
-   Windows 사용자 미로그인
-   SQL Server 자동 기동
-   Tailscale 자동 연결
-   FastAPI 자동 실행
-   외부 DEV에서 HTTP 200
-   PySide6 admin 로그인
-   서버 DB 조회
-   서버 DB 등록/삭제

따라서 다음 작업의 중심은 서버 자체 구축이 아니라 **MXMN-WORK를 동일
중앙 구조에 연결하고, 운영/개발 절차를 정착시키는 것**이다.

또한 Work는 앞으로 "무엇이든 끝까지 해결하는 에이전트"로 사용하지 않고,
**코드 분석·수정·자동검증·commit이라는 고부가가치 개발 작업에
집중**시킨다. GitHub 인증, 단순 push/pull, Windows 설정, 반복적인 수동
진단은 Chat + 로컬 환경에서 처리하여 주간 사용량과 시간을 보호한다.

------------------------------------------------------------------------

# 16. 2026-09-25 추가 검증 --- DEV 외부망 및 WORK 중앙 서버 연결

## 16.1 MXMN-DEV 장비명 및 외부망 실사용

모바일 개발 노트북의 Windows PC 이름을 `Ideapad-slim-3`에서 `MXMN-DEV`로
변경하고 재부팅 후 `hostname`으로 적용을 확인했다.

실제 외부 Wi-Fi 환경에서 다음 경로를 검증했다.

``` text
외부 Wi-Fi → MXMN-DEV → Tailscale → MXMN-SERVER(100.72.3.34)
→ FastAPI :8000 → SQL Server → mxmn_dev
```

DEV에서 다음 요청 결과가 `200`이었다.

``` powershell
(Invoke-WebRequest http://100.72.3.34:8000/docs -UseBasicParsing).StatusCode
```

이후 `python app.py` 실행 후 `admin` 로그인도 정상 작동했다. 따라서 중앙
서버는 집 내부 LAN뿐 아니라 실제 외부 인터넷 환경에서도 Tailscale을 통해
정상 사용 가능함을 확인했다.

## 16.2 MXMN-WORK Git 최신화

WORK의 기존 최신 commit은 다음이었다.

``` text
95f6151 docs: add post-work handoff for 2026-09-21
```

`git pull origin main`으로 GitHub 최신 `main`을 받아 다음 범위로
Fast-forward 되었다.

``` text
95f6151..ba2d01b
```

API 주소 중앙화, 최신 views, 서버 인수인계 문서, 오래된 참고용 파일 제거
등 기존 `main` 변경사항이 WORK에도 반영되었다.

## 16.3 MXMN-WORK Tailscale 설치 및 중앙 API 연결

WORK에는 Tailscale이 설치되어 있지 않았으므로 Windows용 Tailscale을
설치하고 SERVER/DEV와 동일한 `mixbiz1` tailnet에 로그인했다.

WORK Tailscale IP:

``` text
100.89.96.26
```

WORK에서 SERVER FastAPI 포트를 확인했다.

``` powershell
Test-NetConnection 100.72.3.34 -Port 8000
```

결과:

``` text
InterfaceAlias   : Tailscale
SourceAddress    : 100.89.96.26
TcpTestSucceeded : True
```

WORK의 `.env`에는 `API_BASE_URL`이 없었으므로 다음 항목만 추가했다.

``` text
API_BASE_URL=http://100.72.3.34:8000/api/v1
```

DB 관련 `.env` 값은 변경하지 않았다.

이후 WORK에서 `python app.py`를 실행하고 `admin` 로그인이 정상 작동함을
확인했다.

## 16.4 MXMN-WORK 장비명 변경 및 재부팅 검증

기존 Windows PC 이름 `MIXBIZ1`을 다음과 같이 변경했다.

``` text
MIXBIZ1 → MXMN-WORK
```

재부팅 후 `hostname` 결과:

``` text
MXMN-WORK
```

재부팅 직후 Tailscale은 잠시 `Tailscale is starting / NoState`를
표시했으나 설정 변경 없이 잠시 기다린 뒤 정상 연결되었다.

최종 Tailscale 상태:

``` text
100.89.96.26   mxmn-work    mixbiz1@  windows  -
100.125.227.3  mxmn-dev     mixbiz1@  windows  offline
100.72.3.34    mxmn-server  mixbiz1@  windows  -
```

당시 `mxmn-dev`의 offline 표시는 DEV 전원이 꺼져 있었기 때문이며
정상이다.

WORK 재부팅 후 다시 SERVER FastAPI를 확인했고 HTTP `200`을 확인했다.
따라서 WORK도 재부팅 후 Tailscale 자동 연결 및 중앙 서버 접근이
정상이다.

------------------------------------------------------------------------

# 17. 3대 PC 중앙 서버 구성 --- 최종 확정

  -----------------------------------------------------------------------
  장비              역할              Tailscale IP      검증 상태
  ----------------- ----------------- ----------------- -----------------
  `MXMN-SERVER`     중앙 SQL Server + `100.72.3.34`     무인
                    FastAPI                             부팅/자동실행
                                                        검증 완료

  `MXMN-DEV`        모바일 주 개발 PC `100.125.227.3`   외부망 실사용
                                                        검증 완료

  `MXMN-WORK`       업무 + 개발 PC    `100.89.96.26`    중앙 API
                                                        연결/재부팅 검증
                                                        완료
  -----------------------------------------------------------------------

정상 애플리케이션 경로는 다음으로 확정한다.

``` text
MXMN-DEV / MXMN-WORK
 → PySide6 Desktop Client
 → API_BASE_URL
 → Tailscale
 → MXMN-SERVER FastAPI :8000
 → SQL Server
 → mxmn_dev
```

DEV/WORK의 SQL Server 1433 직접 접속은 정상 업무 경로가 아니라 인프라 및
장애 진단용으로만 사용한다.

------------------------------------------------------------------------

# 18. 중앙 서버 3-PC 구성 1차 완료 판정

다음 항목이 실제 환경에서 검증되었다.

-   MXMN-SERVER 중앙 SQL Server 및 FastAPI
-   SQL Server `mxmn_user` 인증
-   SERVER/DEV/WORK Tailscale 연결
-   FastAPI TCP 8000
-   API 주소 중앙화
-   DEV 로그인/조회/등록/삭제
-   DEV 실제 외부 인터넷 환경 로그인
-   WORK Git 최신화
-   WORK Tailscale 신규 설치
-   WORK `.env` 중앙 API 설정
-   WORK 실제 `admin` 로그인
-   WORK PC 이름 `MXMN-WORK` 적용
-   WORK 재부팅 후 Tailscale 자동 재연결
-   WORK 재부팅 후 SERVER FastAPI HTTP 200
-   SERVER 재부팅 후 Windows 미로그인 상태에서 FastAPI 및 DB 로그인
-   SERVER FastAPI 작업 스케줄러 자동실행
-   SERVER 전원/절전 설정
-   MXMN 전용 방화벽 규칙 검증

따라서 **MXMN 중앙 서버 3-PC 구성의 1차 구축은 완료**로 판정한다.

------------------------------------------------------------------------

# 19. 이후 개발/배포 운영 기준

기본 프로세스:

``` text
Chat
 → 요구사항·범위 확정

Work
 → 코드 분석
 → 지정 범위 수정
 → 자동 테스트
 → git commit
 → commit hash 보고
 → STOP

사용자 로컬 DEV/WORK
 → git push

MXMN-DEV
 → git pull
 → 실제 GUI/업무 검증

MXMN-SERVER
 → DEV 검증 완료된 commit만 git pull
 → 필요 시 FastAPI 재기동
 → HTTP/API 확인
```

## GitHub push 원칙

Work의 기본 책임에서 `git push`를 제외한다.

API 중앙화 작업에서도 코드 변경 자체는 정상 완료했으나 GitHub 인증 문제
해결에 약 5분 42초가 추가 소요되었다. 이전 Work에서도 Git/GitHub 인증
문제가 반복적으로 자원을 소비했다.

따라서:

``` text
Work = commit까지
Push = 사용자 로컬 인증 환경
```

으로 고정한다.

예외적으로 Work에서 push를 시도하도록 명시했더라도 인증 오류가 한 번
발생하면 즉시 중단하고 우회 인증 방법을 반복 탐색하지 않는다.

## SERVER 반영 원칙

GitHub `main`이 변경되어도 SERVER가 자동 pull하지 않는다.

``` text
개발 완료 → GitHub push → DEV 검증 → SERVER pull
```

순서를 유지한다. 문서만 변경된 commit은 SERVER 서비스 재시작 없이 pull할
수 있다.

## `.env` 원칙

`.env`는 Git 추적 대상이 아니다. 실제 비밀번호나 인증정보는 GitHub
문서에 기록하지 않는다.

현재 DEV/WORK 중앙 API 기준:

``` text
API_BASE_URL=http://100.72.3.34:8000/api/v1
```

SERVER는 localhost 기본값을 사용할 수 있다.

------------------------------------------------------------------------

# 20. 향후 선택 과제

중앙 서버 1차 구축 이후 별도 과제로 다음을 검토한다.

1.  스마트폰에 Tailscale 설치 후 SERVER 상태 확인
2.  Windows 11 Pro RDP를 Tailscale 내부에서만 사용하도록 구성
3.  외부에서 스마트폰으로 SERVER 원격관리 시험
4.  서버 장애/백업/복구 운영 절차 문서화
5.  MXMN 기능 개발 재개
6.  필요 시 MXMN_FinSales의 중앙 서버 운영 구조 별도 검토

스마트폰 원격관리는 중앙 서버 핵심 구축과 분리하여 진행한다.

------------------------------------------------------------------------

# 21. 최종 결론

2026-09-25 현재 MXMN은 PC별 로컬 DB 복제 중심 구조에서 다음 중앙 구조로
전환되었다.

``` text
MXMN-SERVER
  중앙 SQL Server + 중앙 FastAPI
        ↑
     Tailscale
      ↗     ↖
MXMN-DEV   MXMN-WORK
```

SERVER/DEV/WORK의 이름과 역할이 명확히 확정되었고, 집 LAN뿐 아니라 실제
외부 인터넷 환경, SERVER 무인 부팅, WORK 재부팅 이후 자동 연결까지
검증되었다.

따라서 이후 MXMN 개발은 **중앙 서버를 기준으로 기능 개발과 검증을
계속하는 단계**로 넘어간다.
