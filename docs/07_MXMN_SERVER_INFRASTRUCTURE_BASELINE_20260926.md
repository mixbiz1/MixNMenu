# MXMN ERP — 중앙 서버 / C/S / 원격관리 인프라 최종 기준서

**기준일:** 2026-09-26  
**프로젝트:** MXMN ERP / MixNMenu  
**Repository:** `mixbiz1/MixNMenu`  
**문서 성격:** 개발 전 중앙 인프라 구축 완료 기준서  
**상태:** 구축 및 실제 검증 완료

---

# 1. 문서 목적

본 문서는 MXMN ERP의 중앙 서버, 데이터베이스, FastAPI, 클라이언트, Tailscale 및 원격관리 구조에 대한 최종 기준을 기록한다.

향후 ChatGPT, ChatGPT Work, 기타 AI Agent 또는 개발자가 MXMN ERP 개발을 이어갈 때 중앙 인프라 구조를 다시 추측하거나 불필요하게 변경하지 않도록 하기 위한 기준문서이다.

2026-09-26 기준으로 다음 개발 전 인프라 구축 절차를 모두 완료하였다.

1. MXMN ERP C/S 구축
2. MXMN_FinSales C/S 구축
3. MXMN-SERVER 원격관리 환경 구축

따라서 이후 MXMN ERP 개발에서는 특별한 장애 또는 명시적인 구조변경 요구가 없는 한 서버 인프라를 재설계하거나 임의 변경하지 않는다.

---

# 2. 전체 시스템 역할

## MXMN-SERVER

중앙 서버 역할을 담당한다.

주요 역할:

- MS SQL Server Express 중앙 DB 운영
- MXMN ERP FastAPI 서버 운영
- MXMN_FinSales FastAPI 서버 운영
- 중앙 데이터 보관
- DEV / WORK 클라이언트의 API 및 DB 연결 대상
- Tailscale 네트워크 참여
- Windows RDP를 통한 원격 서버관리

PC명:

`MXMN-SERVER`

운영체제:

`Windows 11 Pro`

LAN IP:

`192.168.0.53`

Tailscale IP:

`100.72.3.34`

---

## MXMN-DEV

주 개발용 PC이다.

주요 역할:

- MXMN ERP 개발
- MXMN_FinSales 개발
- VS Code 및 개발도구 실행
- Git / GitHub 작업
- 중앙 SERVER API/DB 접속
- 필요 시 MXMN-SERVER RDP 원격관리

Tailscale IP:

`100.125.227.3`

---

## MXMN-WORK

사무실 업무 및 보조 개발용 PC이다.

주요 역할:

- 실제 업무 클라이언트
- 개발 및 검증
- Git / GitHub 작업
- 중앙 SERVER API/DB 접속
- 필요 시 MXMN-SERVER RDP 원격관리

Tailscale IP:

`100.89.96.26`

---

## Android Smartphone

외부에서 서버 상태를 확인하거나 필요한 최소 서버관리 작업을 수행하기 위한 보조 관리 단말이다.

검증 당시 장치:

`il-a36`

Tailscale IP:

`100.90.119.64`

스마트폰은 주 개발장비가 아니다.

용도는 다음과 같다.

- MXMN-SERVER Windows 화면 원격접속
- 서버 상태 확인
- FastAPI 상태 확인
- 필요한 경우 프로그램 재실행
- Windows 작업 스케줄러 확인
- 긴급한 기본 서버관리

---

# 3. 네트워크 기본 구조

MXMN 시스템의 원격 네트워크는 Tailscale을 기본으로 한다.

구조:

`MXMN-DEV / MXMN-WORK / Smartphone`

↓

`Tailscale`

↓

`MXMN-SERVER (100.72.3.34)`

↓

`SQL Server / ERP API / FinSales API / Windows RDP`

중요:

**인터넷 공유기에서 RDP TCP 3389를 외부 인터넷에 직접 포트포워딩하지 않는다.**

원격 RDP 역시 Tailscale 내부 네트워크를 통해 접속한다.

---

# 4. MXMN ERP 중앙 C/S 구조

MXMN ERP는 중앙 SERVER 기반 C/S 구조로 운영한다.

기본 구조:

`PySide6 Desktop Client`

↓

`FastAPI`

↓

`SQL Server`

중앙 SERVER:

`MXMN-SERVER`

ERP API:

`100.72.3.34:8000`

SQL Server:

`100.72.3.34:1433`

DEV와 WORK는 각 PC에 별도의 운영 DB를 유지하는 방식이 아니라 중앙 SERVER의 DB/API를 사용하는 구조를 기준으로 한다.

---

# 5. MXMN_FinSales와의 관계

MXMN ERP와 MXMN_FinSales는 서로 독립된 프로젝트 및 Git 저장소이다.

그러나 물리적인 중앙 SERVER는 함께 사용한다.

MXMN ERP:

- API Port: `8000`

MXMN_FinSales:

- API Port: `8001`
- 중앙 DB: `mxmn_finsales_db`

두 프로젝트의 소스코드, Git 저장소 및 업무기능 개발은 독립적으로 관리한다.

한 프로젝트의 기능개발 과정에서 다른 프로젝트 소스를 임의로 수정하지 않는다.

---

# 6. Windows RDP 구축 기록

2026-09-26 MXMN-SERVER의 원격관리 환경을 구축하였다.

초기 상태:

- Windows RDP 비활성
- `fDenyTSConnections = 1`
- `TermService = Stopped`
- TCP `3389` LISTEN 없음
- Windows 기본 RDP 방화벽 규칙 비활성

설정 후:

- `fDenyTSConnections = 0`
- `TermService` 실행
- Windows 기본 원격 데스크톱 방화벽 규칙 활성화

활성화된 Windows 기본 규칙:

- 원격 데스크톱 - 사용자 모드(TCP-In)
- 원격 데스크톱 - 사용자 모드(UDP-In)
- 원격 데스크톱 - 섀도(TCP-In)

공유기 RDP 포트포워딩은 설정하지 않았다.

---

# 7. RDP Listener 문제 및 해결 기록

RDP 활성화 직후 다음 설정은 정상이었다.

- `PortNumber = 3389`
- `fEnableWinStation = 1`
- `SecurityLayer = 2`
- `UserAuthentication = 1`
- `TermService = Running`

그러나 최초에는:

- `qwinsta`에 `rdp-tcp` Listener 없음
- TCP 3389 LISTEN 없음

상태가 발생하였다.

실행 중인 Windows 세션에서 `Restart-Service TermService -Force`를 시도했으나 TermService를 중지할 수 없었다.

강제 서비스 종료 또는 추가적인 위험한 설정 변경을 하지 않고 MXMN-SERVER를 정상 재부팅하였다.

재부팅 후:

`qwinsta`

에서

`rdp-tcp 65536 수신 대기`

상태가 정상적으로 생성되었다.

또한:

- `:: :3389` LISTEN
- `0.0.0.0:3389` LISTEN
- `TermService = Running`

상태를 확인하였다.

따라서 추가적인 서비스 시작유형 변경 등은 수행하지 않았다.

---

# 8. RDP 로그인 기준

MXMN-SERVER Windows 계정:

`MXMN-SERVER\i4menu0`

RDP 로그인 시 Windows PIN이 아니라 실제 Windows 계정 암호가 필요할 수 있다.

암호 자체는 본 문서 및 Git Repository에 기록하지 않는다.

---

# 9. MXMN-DEV 원격접속 검증

MXMN-DEV에서 Windows 기본 Remote Desktop Connection(`mstsc`)을 이용하여 다음 주소로 접속하였다.

`100.72.3.34`

사용자:

`MXMN-SERVER\i4menu0`

실제 MXMN-SERVER Windows Desktop 표시 및 원격조작에 성공하였다.

검증 완료 경로:

`MXMN-DEV → Tailscale → MXMN-SERVER → RDP`

---

# 10. MXMN-WORK 원격접속 검증

MXMN-WORK Tailscale:

`100.89.96.26`

MXMN-SERVER:

`100.72.3.34`

WORK에서 다음 테스트를 수행하였다.

`Test-NetConnection 100.72.3.34 -Port 3389`

결과:

`TcpTestSucceeded : True`

이후 Windows Remote Desktop Connection을 이용하여 실제 MXMN-SERVER Windows Desktop 접속 및 조작에 성공하였다.

검증 완료 경로:

`MXMN-WORK → Tailscale → MXMN-SERVER → RDP`

---

# 11. Android 스마트폰 원격관리 검증

Android Galaxy 스마트폰에 Tailscale을 설치하였다.

동일 Tailnet에서 MXMN-SERVER를 확인하였다.

스마트폰:

`il-a36`

Tailscale IP:

`100.90.119.64`

Microsoft Windows App을 설치하고 PC Connection을 생성하였다.

접속 대상:

`100.72.3.34`

사용자:

`MXMN-SERVER\i4menu0`

Friendly Name:

`MXMN-SERVER`

Gateway:

`No gateway`

실제 스마트폰 화면에서 MXMN-SERVER Windows Desktop 표시 및 원격조작에 성공하였다.

검증 완료 경로:

`Galaxy → Tailscale → MXMN-SERVER → RDP`

---

# 12. SERVER 재부팅 후 최종 서비스 검증

RDP 설정 후 MXMN-SERVER를 정상 재부팅하였다.

재부팅 이후 RDP Listener 자동 복구를 확인하였다.

또한 MXMN-WORK에서 다음 중앙서비스를 검증하였다.

## SQL Server

대상:

`100.72.3.34:1433`

결과:

`TcpTestSucceeded : True`

## MXMN ERP FastAPI

대상:

`http://100.72.3.34:8000`

결과:

`HTTP 200`

## MXMN_FinSales FastAPI

대상:

`http://100.72.3.34:8001`

결과:

`HTTP 200`

따라서 재부팅 이후에도 다음 핵심 인프라가 정상 운영됨을 확인하였다.

- Windows RDP
- SQL Server
- MXMN ERP FastAPI
- MXMN_FinSales FastAPI
- Tailscale

---

# 13. 최종 시스템 구조

```text
                     ┌─────────────────────┐
                     │     MXMN-SERVER     │
                     │   Windows 11 Pro    │
                     │  100.72.3.34        │
                     └──────────┬──────────┘
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
        SQL Server          ERP FastAPI       FinSales API
          :1433                :8000              :8001
             │                  │                  │
             └──────────────────┼──────────────────┘
                                │
                            Tailscale
                                │
                ┌───────────────┼───────────────┐
                │               │               │
           MXMN-DEV        MXMN-WORK        Galaxy
        100.125.227.3     100.89.96.26    100.90.119.64
                │               │               │
                └────── RDP / Client / 관리 ───┘
```

---

# 14. 운영 및 개발 원칙

향후 AI Agent 또는 개발자는 다음 원칙을 따른다.

1. MXMN-SERVER를 중앙 DB/API 서버 기준으로 유지한다.
2. 특별한 장애가 없는 한 중앙 서버 인프라를 임의 변경하지 않는다.
3. 공유기에서 TCP 3389를 인터넷에 직접 포트포워딩하지 않는다.
4. 원격관리는 Tailscale + RDP 구조를 기본으로 한다.
5. 정상 작동 중인 SQL Server/API 자동기동 설정을 이유 없이 변경하지 않는다.
6. DEV와 WORK는 개발 및 업무 클라이언트 역할을 담당한다.
7. 스마트폰은 긴급/보조 서버관리 용도로 사용한다.
8. 암호, API Secret 등 보안정보를 Git 문서에 기록하지 않는다.
9. MXMN ERP와 MXMN_FinSales 소스 및 Git 저장소는 독립적으로 관리한다.
10. 인프라 변경이 필요한 경우 먼저 현재 상태를 확인하고 최소 변경 후 실제 검증한다.

---

# 15. 개발 재개 기준

2026-09-26을 기준으로 개발 전 인프라 구축은 완료되었다.

완료 순서:

`ERP C/S 구축`

→

`FinSales C/S 구축`

→

`MXMN-SERVER 원격관리 구축`

→

**완료**

다음 MXMN ERP 작업부터는 중앙서버 구축을 반복하지 않는다.

대상 프로젝트의 GitHub `main` 최신 상태를 확인하고 기존 업무기능 개발 중단 지점에서 개발을 재개한다.

권장 시작 절차:

1. `git status`
2. `git fetch`
3. 로컬과 `origin/main` 상태 확인
4. 필요 시 `git pull --ff-only origin main`
5. `docs/04_CURRENT_STATUS.md` 및 관련 기준문서 확인
6. 마지막 개발 중단 지점 확인
7. 다음 Vertical Slice 결정
8. 코드 수정
9. 실제 실행/사용자 검증
10. 문서 업데이트
11. Git commit / push

---

# 16. 최종 상태 선언

**2026-09-26 MXMN ERP 중앙 C/S 및 MXMN-SERVER 원격관리 인프라 구축 완료.**

이 문서는 향후 MXMN ERP 개발에서 중앙 서버 및 네트워크 구조를 판단하기 위한 기준문서로 사용한다.