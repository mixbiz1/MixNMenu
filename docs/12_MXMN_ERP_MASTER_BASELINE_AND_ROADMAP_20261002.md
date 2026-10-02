# MXMN ERP Master Baseline and Roadmap — 2026-10-02

**상태: 2026-10-02 사용자 업무범위 검토·승인 반영본. DEV/GitHub main 반영 후 공식 Source of Truth로 확정한다.**  
작성 목적: 조일 사용자가 Chat에서 업무규칙을 검토하고 DEV에 반영한 뒤, 다음 Chat/Work가 전체 맥락을 이어받게 한다. 이번 작업은 조사와 문서작성만 수행했다. 기능개발·DB 연결/변경·Migration·Task Scheduler·venv 변경·Git commit/push/merge/branch 변경은 수행하지 않았다.

## 1. 가장 먼저 읽을 결론과 증거의 경계

실제 개발 중심과 업무 원본은 **MXMN ERP / `mixbiz1/MixNMenu` 하나**이다. `MXMN_FinSales`는 삭제하지 않고 계산·화면·PDF·회귀검증 참고용으로 보존한다. 독립 신규개발을 재개하지 않는다. Financing은 ERP Master와 거래에 Contract/Calculation/Settlement 계층을 추가한다.

현재 ERP는 회사/거래처/상품/창고/LOT/기초자료/사용자·권한, 거래 공통기반 및 상품매입의 `Purchase → Inbound → LOT → Purchase Payable`를 구현했다. 상품매입 상세 Audit 기록과 조회 API도 main에 있다. **일반매출·실제 출고·수금/지급·Financing 계약/계산/정산은 아직 구현된 업무 흐름이 아니다.** 화면 메뉴, DB 설계안, 옛 Slip 모델이 존재한다는 이유로 완료로 판정하지 않는다.

Audit는 “구현 없음”도 “전체 마감”도 아니다. 코드/테스트 적용은 완료했고 중앙 SQL Server와 실제 사용자 GUI 검증은 남았다. GUI에는 Audit 이력 조회 화면이 없다. 사용자 보고의 `38 passed`는 DEV의 실행 결과이며 이번 Work가 재실행한 결과가 아니다.

| 증거 구분 | 이번 조사에서 확인한 범위 | 적용 방법 |
|---|---|---|
| 현재 GitHub 코드 | 아래 고정 SHA의 전체 트리, 주요 소스·문서·Migration·테스트 | 구현 유무 판정의 직접 근거 |
| Git history | ERP main 도달 가능 97개, FinSales main 11개, 합계 108개 commit 및 변경파일/patch | 설계→구현→변경의 경위 |
| 과거 문서 | 현재 docs 24개, 문서 변경 125건, 삭제된 초기 FinSales 문서 5개 | 당시 판단과 현재 원칙 구분 |
| 2026-10-02 사용자 지시 | 현재 venv, DEV 테스트, SERVER/DEV SQL 대상 차이, 미커밋 verifier 수정 | 로컬/운영 사실의 사용자 보고 |
| 직접 확인하지 못한 것 | DEV 작업트리, 실제 SERVER 배포 SHA·DB·Task Scheduler·중앙 Audit 이벤트·WORK | 모두 “확인 필요”; 원격 실검증 완료로 쓰지 않음 |

조사 기준:

- ERP: [8cee784821934356dcdbe23f6bcd96612470c89c](https://github.com/mixbiz1/MixNMenu/commit/8cee784821934356dcdbe23f6bcd96612470c89c), main, commit 시각 2026-09-30 09:35:56 UTC.
- FinSales: [2ed3bd33748f01d1ae558d3f33f672956037abc3](https://github.com/mixbiz1/MXMN_FinSales/commit/2ed3bd33748f01d1ae558d3f33f672956037abc3), main, 2026-09-28 08:59:37 UTC.
- “처음부터”는 각 main의 최초 parent 없는 commit부터 현재 SHA까지의 범위이다. 최초 ERP commit은 2026-09-02, FinSales는 2026-09-19이다. 그 이전 실제 업무/Chat 이력, main에 도달하지 않는 모든 별도 branch는 조사 완료라고 주장하지 않는다.
- 현재 비어 있지 않은 소스/문서/설정 91개를 확보했다. ERP 현재 docs 18개, FinSales 6개를 검토했다. ERP의 `ui-당분간 사용안함`은 트리상 보존 자료로 구분했고 모든 Designer 파일을 실행·검증하지 않았다. FinSales 빈 scaffold는 트리로 확인했다.
- 확보한 Python 61개를 import 없이 AST 구문검사했고 오류 0개였다. 실행 검증, Windows GUI 검증 또는 SQL Server 검증을 대신하지 않는다. 본 작업환경에 pytest/PySide6/SQLAlchemy/pyodbc/FastAPI 등 실행 의존성이 갖춰져 있지 않아 업무 테스트를 재실행하지 않았다.

## 2. 현재 Source of Truth와 문서 우선순위

충돌할 때 판단 기준은 “무조건 최신 파일명”이 아니라 **업무의 확정 방향 / 실제 구현 / 운영환경 사실**을 분리하는 것이다.

1. 사용자 2026-10-02 확정 지시: ERP 단일 중심, FinSales 보존, 현재 venv 및 안전한 DB 대상 확인, 이번 Work의 변경 금지.
2. 승인된 최신 업무설계: `08_MXMN_ERP_FINANCING_INTEGRATION_DESIGN_V1_20260929.md`, `10_MXMN_ERP_AUDIT_HISTORY_STANDARD_20260929.md`.
3. 실제 구현: ERP `8cee784`, FinSales `2ed3bd3`의 코드와 테스트. 설계안의 존재는 구현의 증거가 아니다.
4. 운영환경: 9/26 인프라 기록 + 현재 사용자 확인. 운영 상태는 배포 SHA/실제 실행 대상 확인으로 따로 확정한다.
5. 본 Master/Executive Guide: 검토용 통합 후보. 사용자 수정·승인→DEV 반영→GitHub main 반영 후 다음 세션의 첫 진입 문서가 된다.

새 문서 읽기 순서: **본 Master → Executive Guide → ERP 08 Financing → ERP 10 Audit → ERP 07 인프라 → ERP 09 작업기록 → 현재 코드/테스트**. 오래된 04나 11 Gap 문서의 완료표를 단독 기준으로 사용하지 않는다.

기존 `12_MIGRATION_PLAN.md`, `13_POST_WORK_HANDOFF_20260921.md`가 이미 있다. 새 12/13은 전체 파일명이 다르므로 덮어쓰지 않는다. 번호가 중복되는 것은 인덱스 혼선이므로 새 문서의 전체 파일명을 사용한다. 기존 문서 삭제·번호 변경은 이번 작업에 포함하지 않았다.

## 3. 개발 History — 무엇이 언제 바뀌었는가

| 시기 | ERP 실제 변화 | 해석과 현재 영향 |
|---|---|---|
| 9/02~9/12 | 초기 Python/GUI/DB 환경, 회사 화면, 메인/대시보드와 업무 메뉴 | 메뉴 틀을 만들었으며 매출·수금 구현 완료를 뜻하지 않음 |
| 9/15 | `bafc85e` 초기 docs 00~13, 다중회사와 거래처 v2/v2.1, 회사 전환 | 문서의 넓은 목표 범위와 현재 실제 범위를 분리해야 함 |
| 9/16 | 공통코드/상품코드/상품, 검색·화면 개선, 사업자번호 중복 허용 | 기존 복수 거래처코드 허용 이력은 보존. 9/29 이후 중복 생성을 기본으로 삼지 않음 |
| 9/17 | 창고·기간요율·가변비용, LOT, 기초재고/기초잔액, 경비 4계층 | Master/초기 원장 기반. 요율 변경 이력 불변성까지 완료된 것은 아님 |
| 9/18 | 사용자/권한, 공통 발번·기간통제·Header Audit, 상품매입 | 최초 금액전표 → 확정 시 입고/LOT/미지급 생성 → GUI 저장 즉시 확정으로 같은 날 발전 |
| 9/21~9/23 | 서버계획 변경 및 인수인계, SQL 실행 문제 보완 `2309095` | 초기 12GB PC 계획은 9/23 기존 모바일 PC 계획으로 대체. 현재 SERVER 기준 사용 |
| 9/24~9/26 | API 접속설정, 불필요 과거 소스 정리, 중앙 C/S·VPN·RDP·자동기동 | ERP :8000 / FinSales :8001 운영기록. 인프라를 다시 만들 필요 없음 |
| 9/29 | `b637a42` Financing ERP 통합 설계, `6fdb049` 원장/Schema 복구 기록, `590a940` Audit 표준 | 독립 FinSales 확장에서 ERP 통합으로 방향 전환. 이 commit들은 계약 구현이 아님 |
| 9/30 | Audit helper/DDL/개발도구 후 `8cee784` 실제 main API/GUI/테스트 연결 | 옛 Work 인수인계의 “main 미반영” 문장은 현재 Git 기준으로 대체됨 |
| 10/02 | 사용자 DEV 38 passed 및 verifier COLLATE 최소 수정 보고 | central/local DB 구분 재확인. 미커밋 로컬 수정은 이번 원격 코드로 직접 볼 수 없음 |

주요 ERP 구현 commit: 다중회사 `a5fae53`, 회사 전환 `b2b913d`, 거래처 `24ad515`, 상품 `2dada7a`, 창고 `e1b2879`, 가변비용 `bdb0984`, LOT `e210860`/`900fcf4`, 기초자료 `d9fe5b9`, 경비 `2fe4a4c`/`6fb6446`, 사용자 `1c4a8a9`, 권한 `961975e`, 공통거래 `81dd2e0`, 매입 초안 `d715e16`, 물류/미지급 연결 `a265df4`, 즉시확정 `a8313db`, 화면/할인 `16bce19`. 뒤의 commit이 앞의 문서 의미를 바꾸는 지점을 추적했다.

| 시기 | FinSales 실제 변화 | 현재 보존 가치 |
|---|---|---|
| 9/19 `2c54f36` | 계산/Simulation/PDF 중심 GUI 및 초기 문서 | 최초 계산 방식과 UI. “저장/발송 완료” 설명은 코드로 다시 판정해야 함 |
| 9/20 `64e3e59` | C/S 파일 추가, 문서 이름 교체, 빈 모듈 구조 생성 | 이전 5개 문서 삭제 이력은 Git에 보존. 빈 src/api 구조는 업무 구현이 아님 |
| 9/26 `9f784f0`~`fa4b1e1` | API/중앙 DB 접속 및 운영기록 | 샘플 요율 변경→복원과 실제 연결 경위 참고 |
| 9/28 `5c91552`~`2ed3bd3` | admin/partner 인증, LOT 접근제한, 공용 환경/자동기동, TCP DB 기본설정 | 참고 프로그램 실행 환경. ERP 인증/원장으로 다시 통합할 대상은 아님 |
| 9/29 ERP 설계 확정 이후 | FinSales main 신규 계약업무 구현 없음 | 보존 및 회귀검증용. ERP를 실제 개발 대상으로 유지 |

## 4. 문서 전수 분류와 대체 이유

판정은 문서 전체를 폐기한다는 뜻이 아니다. 기술적으로 유효한 부분은 남기고 후속 설계로 대체된 지시만 제외한다.

### 4.1 ERP 현재 docs 18개

| 파일 | 판정 | 지금 사용할 내용 / 적용하면 안 되는 내용 |
|---|---|---|
| `00_PROJECT_BASELINE.md` | 일부 유효 | 다중회사·LOT 개별원가·원장 원칙 유효. `company_id`, Partner/Customer 분리 구조는 목표 모델이며 현재 DB와 다름 |
| `01_PROJECT_SPEC.md` | 목표/참고 | 전체 육류수입·유통 ERP 업무범위. 서비스/수입/매출 등 완료표로 쓰지 않음 |
| `02_DOMAIN_MODEL.md` | 목표/참고 | 도메인 관계 참고. 현재 모델명과 구분 |
| `03_DATABASE_DESIGN.md` | 일부 유효 | 매입/입고/LOT 분리, 원장 설계 및 구현 추가분. 아직 없는 테이블까지 실제 Schema로 읽지 않음 |
| `04_CURRENT_STATUS.md` | 누적 역사/일부 유효 | 9/15~9/30 변화 참고. 상단 v1.26/옛 branch `168609d`, 미커밋/서버 미반영은 main `8cee784`와 구분 |
| `05_FOLDER_STRUCTURE.md` | 목표/일부 유효 | 향후 책임분리 참고. 현재 root 중심 구조를 전면 재배치할 즉시 지시가 아님 |
| `06_MXMN_MASTER_HANDOFF_20260923_FINAL.md` | 역사/일부 유효 | 서버 변경·공용 환경 경위. 독립 FinSales 신규개발 방향은 9/29로 대체 |
| `07_MXMN_SERVER_HANDOFF_20260925.md` | 일부 유효 | 중앙 SQL/API/보안/운영 기록. 당시 작업 branch/commit 지시를 오늘 적용하지 않음 |
| `07_MXMN_SERVER_INFRASTRUCTURE_BASELINE_20260926.md` | 현재 인프라 기록 | 3-PC/VPN/RDP/API 자동기동 기준. 독립 FinSales 향후 개발 문구는 대체 |
| `08_MXMN_ERP_FINANCING_INTEGRATION_DESIGN_V1_20260929.md` | 현재 유효 상위 설계 | ERP SoR, Single Master, 계약/Term/Segment/Snapshot/정산/담보 기준. 구현 상태는 별도 |
| `09_MXMN_ERP_WORKLOG_HANDOFF_20260929.md` | 현재 방향+역사 | Schema 복구 및 통합 방향·공용 venv. 당시 실행 성공을 오늘 DB 검증으로 대신하지 않음 |
| `10_DEVELOPMENT_ROADMAP.md` | 일부 유효/순서 대체 | 전체 목표 참고. 실제 우선순위는 08 및 본 검토안으로 갱신 |
| `10_MXMN_ERP_AUDIT_HISTORY_STANDARD_20260929.md` | 현재 유효 상위 설계 | 공통 append-only 상세 이력 기준 |
| `11_CODEBASE_GAP_ANALYSIS.md` | 역사/잔여 Gap 참고 | 초기 단일회사·평문 ERP 암호·권한 미구현 판정은 이후 코드로 대체. 미구현 업무 일부는 여전히 유효 |
| `11_MXMN_PURCHASE_AUDIT_WORK_HANDOFF_20260930.md` | 현재 기술 참고/시점 대체 | Snapshot/rollback/중앙 검증 미완료 상세 유효. “main 미반영/미커밋”은 현재 main 사실과 다름 |
| `12_MIGRATION_PLAN.md` | 일부 유효 | 백업·테스트·단계적 Migration 원칙. 옛 회사 구조 개편 순서를 자동 실행하지 않음 |
| `13_POST_WORK_HANDOFF_20260921.md` | 역사 | 당시 홈 PC/12GB 서버계획은 후속 서버문서로 대체 |
| `AI_SYSTEM_PROMPT.md` | 일부 유효 | 업무/코딩 운영 참고. 다음 세션 첫 문서는 본 Master와 최신 08/10; 옛 우선순위 단독 적용 금지 |

### 4.2 FinSales 현재 docs 6개 및 초기 문서

| 파일 | 판정 | 이유 |
|---|---|---|
| `00_INTEGRATED_BASELINE_AND_STATUS.md` | Reference/부분 대체 | 9/26 독립 프로그램/C/S 이력. 독립 신규개발 지시는 9/29 ERP 통합으로 대체 |
| `01_MXMN_FINSALES_MODULE_SPEC.md` | Reference/불일치 있음 | 계산·UI 목표 참고. 출고확정 저장/발송/로그는 현재 구현과 다름 |
| `02_BUSINESS_AND_CODING_GUIDELINES.md` | Reference/부분 대체 | 숫자·평균중량·예외 정책 참고. 무조건 올림은 코드 round와 충돌; A/B/C 구분은 현재 3개 계약유형과 다름 |
| `03_WORK_LOG_20260926_FINSALES_CS_SETUP.md` | 역사/운영 참고 | 중앙 C/S 연결·샘플 요율 검증기록. 현재 계약 검증 완료의 증거는 아님 |
| `08_MXMN_FINSALES_SERVER_INFRASTRUCTURE_BASELINE_20260926.md` | Reference 인프라 | 중앙 서버·:8001 보존. 새 기능은 ERP에서 구현 |
| `09_MXMN_FINSALES_AUTH_CS_HANDOFF_20260928.md` | 역사/일부 유효 | 인증/자동기동 경위. `.venv` 표기는 사용자 현재 `venv` 확인으로 대체; 옛 SHA/RDP 대기 상태 구분 |

9/19 초기 `0.Integrated Baseline & Status.md`, `07_MXMN_FINSALES_BASELINE(통합인수인계서)_20260919.md`, `1.current_status.md`, `2.기타 참고 사항 및 정책 가이드.md`, `3. MXMN ERP 프로젝트 마스터플랜 (Master Plan).md`는 9/20 교체/삭제되었다. 최초 commit의 내용을 검토했고 역사적 참고로 분류한다. 초기 문서는 최종금액 절사, 후속 문서는 올림, 실제 코드는 round이므로 규칙을 임의 통일할 수 없다. 복원/삭제 작업은 하지 않았다.

ERP `README.txt`와 `오늘 작업하면서 메모한것.txt`는 초기 실행/작업 참고이고 현재 기준선이 아니다. `db_inspect_result.txt`는 한 시점의 DB 출력 자료로 오늘 중앙 Schema를 증명하지 않는다. FinSales `README.md`/`requirements.txt`와 다수 scaffold는 빈 파일이어서 실행·의존성·업무 구현 근거가 없다. 과거 문서의 자동 생성 citation 표시는 이번 조사에서 출처를 재검증한 표시가 아니다.

## 5. 현재 구조와 3-PC 운영 기준

| 구분 | 확정 방향 또는 사용자 확인 | 이번 Work 직접 검증 여부 |
|---|---|---|
| MXMN-SERVER | Windows 11 Pro, SQL Server Express, 중앙 FastAPI, Tailscale, RDP, SQL/API 자동기동 구성 | 운영 현황은 사용자/9월 문서 기록, 실접속 없음 |
| MXMN-DEV | 주 개발 PC, VS Code, GUI는 중앙 API 사용 | 작업트리/실행환경 직접 열람 없음 |
| MXMN-WORK | 업무/개발 PC, 현재 물리 접근 어려움 | 환경 동일 여부 확인 필요 |
| ERP 프로젝트 | `C:\projects\MixNMenu` | 현재 표준 |
| 공용 Python | `C:\projects\MixNMenu\venv\Scripts\python.exe` | SERVER/DEV는 사용자 현재 확인, WORK 추후 확인 |
| ERP API/DB | :8000 / `mxmn_dev` | 운영 확인 별도 |
| FinSales API/DB | :8001 / `mxmn_finsales_db` | Reference 환경 보존 |

정상 업무 경로는 `DEV/WORK PySide6 GUI → SERVER FastAPI :8000 → 업무로직/SQLAlchemy → 중앙 SQL Server`이다. FinSales는 참고용 GUI→:8001의 기존 구조를 보존한다.

기록상 SQL instance는 `MXMN-SERVER\SQLEXPRESS`, SERVER LAN `192.168.0.53`, Tailscale `100.72.3.34`; DEV `100.125.227.3`, WORK `100.89.96.26`, Android `100.90.119.64`이다. 이것은 설정 참고이며 네트워크 현시점 도달성을 검증한 결과가 아니다. SQL Server Express 2025, RDP 3389 VPN 내 사용과 공용 인터넷 포트포워딩 금지는 기존 운영기준으로 유지한다. SQL 계정 `mxmn_user`, SQL 관리자 `sa`, ERP GUI 관리자 계정은 서로 다른 역할이다. 암호/토큰은 문서에 기록하지 않는다.

**공용 venv 구조는 잘못된 구조가 아니다.** FinSales 전용 환경을 새로 만들지 않는다. 9/28 문서와 `start_finsales_api.cmd`의 `.venv` 표기가 현재 사용자 `venv` 표기와 다르다. 실제 Scheduler 실행명령을 확인하기 전 파일의 옛 표기만 보고 현재 서버가 잘못 실행된다고 단정하거나 Scheduler를 바꾸지 않는다.

### 5.1 GUI의 API 대상과 개발 Script의 DB 대상은 독립이다

ERP `api_config.py`는 API URL 환경값과 기본 `localhost:8000/api/v1`를 사용하고 `api_client.py`는 인증 HTTP 요청을 담당한다. `database.py`는 별도의 `DB_SERVER/DB_NAME/DB_USER/DB_PASSWORD` 및 dotenv 설정을 사용한다. fallback은 `localhost,1433`, `mxmn_dev`, `sa`이며 password는 비어 있는 기본값이다. ODBC Driver 17/SQLAlchemy engine 설정이 있다. GUI API URL을 중앙으로 바꿔도 직접 SQL script의 DB 대상이 중앙으로 바뀌지는 않는다.

사용자 확인 결과 DEV의 직접 SQL 대상은 `Ideapad-slim-3\SQLEXPRESS / mxmn_dev`였다. SERVER와 DEV의 DB 이름이 같으므로 **DB_NAME 하나만 확인하는 것은 안전한 대상 확인이 아니다.** `tb_audit_event missing`가 나온 DEV 로컬 DB에 중앙 Migration을 자동 실행해서는 안 된다.

### 5.2 다음 DB 검증/Migration의 안전한 실행원칙

이번 Work는 아래 명령을 실행하지 않았다. 이후 Chat/DEV에서 한 단계씩 수행한다.

1. 현재 PC, 프로젝트 경로, 실행 Python, `.env` 적용 여부 및 실행 의도를 먼저 확인한다. DB 접속 URL 전체나 암호는 공유하지 않는다.
2. `database.engine`을 쓰는 도구라면 **그 동일 engine 연결**로 아래 읽기 전용 SQL을 실행한다. SSMS의 별도 연결 성공만으로 script 대상을 확정하지 않는다.

```sql
SELECT @@SERVERNAME AS server_name,
       DB_NAME() AS database_name,
       CONVERT(nvarchar(128), SERVERPROPERTY('MachineName')) AS machine_name,
       CONNECTIONPROPERTY('local_net_address') AS local_net_address;
```

3. 결과를 기대 대상 `MXMN-SERVER\SQLEXPRESS / mxmn_dev`와 비교한다. local address는 로컬 연결 방식에 따라 NULL일 수 있으므로 단독 기준으로 쓰지 않는다. instance/machine/db/실행환경을 함께 판단한다. 불일치면 중단하고 설정을 확인한다.
4. 그 다음 기존 verifier를 읽기 전용으로 실행한다. 중앙에서 테이블은 존재했으며 이전 DIFF는 NVARCHAR COLLATE 표현 차이였다는 사용자 보고를 기준으로 한다.
5. DEV 미커밋 COLLATE 수정은 `git diff -- dev_verify_purchase_audit_schema.py`로 확인한다. GitHub main의 현재 verifier는 아직 compiled type 문자열을 직접 비교한다. 길이/Unicode/정밀도/nullable/PK/IDENTITY/default/index는 보존하고 collation 표현만 분리하는 최소 수정을 검토한다. 모든 차이를 무시하는 방식은 금지한다.
6. 실제 중앙 Schema 차이가 확인될 때만 별도 작업으로 Migration 필요성을 결정한다. 사전 백업·복구 경로·대상 guard·검증 SQL·배포 순서를 갖춘다. “missing” 한 줄만 보고 실행하지 않는다.

일부 옛 Migration은 파일 import 시 `engine.begin()` 작업을 실행하므로 Migration 모듈을 진단 목적으로 import하지 않는다. `db_audit_history_migrate.py`는 main guard가 있지만 DB instance guard는 없고 테이블이 없는 경우에만 table/index를 만든다. 기존 부분 Schema/누락 index를 다시 실행만으로 보수하지 않는다. `dev_apply_purchase_audit.py`도 코드를 바꾸는 개발도구이므로 이미 연결된 main에 다시 적용하지 않는다.

## 6. 실제 코드/폴더별 구현 판정

| 영역 | 직접 확인한 소스 | 현재 판정 |
|---|---|---|
| GUI 진입/맥락 | `app.py`, `app_context.py`, `views/mxmn_main_window.py`, `main_dashboard.py`, `main_view.py` | 회사/사용자/메뉴 틀. 메뉴와 실제 업무 완료 구분 |
| API/DB | `main.py`, `api_client.py`, `api_config.py`, `database.py` | root 중심 FastAPI C/S. main.py가 큰 단일 API 파일이며 일부 helper 분리 |
| 모델 | `models.py` 27개 class | `comp_code` 기준. 현재 `company_id` 전면 변경 대상 아님 |
| 회사/거래처 | Company, Account, CompanyAccount, 회사/거래처 GUI/API | 공용 거래처 + 회사별 관계. 별도 Partner/Customer 모델은 없음 |
| 상품/공통코드 | Product/분류/12개 속성코드 관계, TaxCode, 관련 3개 GUI | 상품과 LOT 분리 구현 |
| 창고/요율 | Warehouse/CompanyWarehouse/WarehouseRate/WarehouseCharge, `warehouse_reg.py` | 회사 연결·요율/가변비용 CRUD. 불변 버전/계약 Snapshot 미구현 |
| LOT/기초재고 | LOT, Inbound/InboundItem, `lot_reg.py`, `opening_inventory_reg.py` | 입고 기반 LOT와 기초재고; 일반 출고 원장은 아직 없음 |
| 경비 | ExpenseCode, `expense_code_defaults.py`, `expense_code_reg.py` | 4계층/42 기본코드 및 입력/계산 구분. 독립 경비 거래 완료는 아님 |
| 기초잔액/원장 | AccountTransaction/AccountTransactionAllocation, `opening_balance_reg.py` | 원거래/배분 구조 및 기초잔액. 수금·지급 업무 흐름 아직 없음 |
| 사용자/권한 | User, `permissions.py`, 사용자/권한/암호 GUI | 로그인/회사 접근/menu CRUD 검사 구현 |
| 공통 거래 | `trade_common.py`, 기간/발번 모델 및 Migration | SQL Server 발번 동시성/기간통제/전표상태·Header Audit 기반 |
| 매입 | Purchase/PurchaseItem, `purchase_service.py`, `main.py`, `purchase_reg.py` | 확정 매입의 입고/LOT/미지급 생성·조회·수정·취소 구현, 중앙 마감 대기 |
| 상세 Audit | `audit_service.py`, Migration/verifier, main 호출, 2개 테스트 파일 | 매입 5종 action과 매입 전용 history API 연결. 범용 Entity 조회 API/GUI viewer/전 영역 적용 없음 |
| Sale/Outbound/Receipt/Payment | 모델/API/GUI 전체 검색 | 대응하는 완성 도메인/업무 API 없음. legacy SlipHeader/SlipDetail은 일반매출 완료 증거 아님 |
| Financing/수입/반품/서비스 | 모델/API/GUI/서비스 전체 검색 | ERP 실제 계약/계산/출고/정산·ImportCase·반품·Service 거래 미구현 |

ERP 암호는 PBKDF2-SHA256(260,000회+salt)이며 기존 평문은 로그인 시 변환 경로가 있다. Bearer token은 HMAC 기반 12시간 기본 만료이며 활성사용자/회사접근/menu CRUD를 서버 middleware가 검사한다. 마지막 관리자·자기잠금 방지 경계가 있다. 이는 FinSales의 평문/메모리 인증과 다르다. CompanyAccount의 DB unique 제약과 ORM 선언의 차이도 중앙 Schema 검사에서 확인해야 한다.

향후 책임분리는 기능을 만들 때 해당 API/router/service를 작은 범위로 분리한다. 검토 문서 때문에 현재 flat 구조를 일괄 이동하거나 `comp_code`를 `company_id`로 전면 변경하지 않는다.

### 6.1 Master와 재고에서 먼저 지켜야 할 무결성

- 동일 사업자의 일반유통/Financing/보증금 관계를 별도 Account로 복제하는 것을 기본으로 삼지 않는다. 기존 사업자번호 중복 허용 데이터는 자동 합치지 않고 관계·원장을 조사한 뒤 사용자 확인한다.
- LOT GUI는 수동 신규입력을 제거했으나 LOT 생성 API는 남아 있다. “수동 LOT 생성이 전 경로에서 금지됨”은 사실이 아니다.
- LOT 수정 API가 상품/창고/원가를 바꿀 때 이미 연결된 Inbound와의 의미적 일치를 전부 통제하는지 확인 필요. FK가 존재한다는 것만으로 값 변경이 안전한 것은 아니다.
- 기초재고 수정은 연결 LOT/입고 값을 갱신한다. 향후 출고 후 수정통제는 별도 명시적 규칙/테스트가 필요하다.
- 창고요율은 같은 적용시작일을 수정하면 기존 값을 덮어쓰고 하위 비용행을 재생성한다. 최근 시작일 조회가 조회기준일/종료일 전체를 고려하는 불변 기간요율 엔진은 아니다. Financing 확정계산은 당시 요율 Snapshot을 저장해야 한다.
- 경비코드 GET은 코드가 비었을 때 seed를 만들 수 있다. HTTP GET이라고 무조건 읽기 전용이라고 가정하지 않는다. 이번 조사에서 실제 API를 호출하지 않았다.

## 7. 상품매입의 현재 실제 흐름과 남은 마감

GUI `저장`은 `finalize=True`로 즉시 확정한다. API에는 DRAFT 처리도 있지만 GUI의 일반 저장은 임시저장이 아니다.

1. 서버가 회사/기간/매입처/상품/창고 및 KG/BOX/단가를 검증한다.
2. Purchase/PurchaseItem을 저장하고 확정한다.
3. 창고별 Inbound를 만들고 매입행별 LOT와 InboundItem을 만든다.
4. AccountTransaction에 `PURCHASE_PAYABLE` 원거래를 생성한다.
5. Audit CREATE/CONFIRM을 같은 Session/Transaction 안에 기록한다. 실패 시 전체 rollback한다.

KG는 소수점 둘째 자리, 단가는 정수 원이다. 서버는 공급가 `ceil(KG × 단가)`, 세금 `ceil(공급가 × 세율/100)`을 재계산한다. 상품 과세정보를 Snapshot으로 확정하며 현재 VAT10 또는 EXEMPT 규칙을 사용한다. 할인은 양수일 때 차감, 음수일 때 가산된다. 행 합계와 할인/총금액을 검증한다.

현재 확정자료 수정은 파생 입고/LOT/미지급을 회수하고 재생성하는 방식이다. 이후 거래가 FK로 연결돼 있으면 실패/rollback으로 막는 경우가 있다. Audit는 수정 전후 old/new ID와 실제 값을 보존한다. 그러나 이는 이미 진행된 거래에 대한 반품·정정·역분개 원장을 구현했다는 뜻이 아니다. 매출을 만들기 전에 “사용 후 불변 + 정정 거래” 경계를 정해야 한다.

취소는 상태와 이유를 Purchase에 남기며 미사용 파생원장을 지운다. CANCEL 사유는 trim 후 1~1000자 필수이다. 일반 UPDATE 사유는 현재 필수가 아니다. Draft 삭제는 Audit에 삭제 전 내용을 남기고 Purchase를 물리삭제한다. 확정자료 직접 DELETE는 막는다.

| 남은 확인/정책 | 코드에서 확인한 근거 | 이후 마감 방향 |
|---|---|---|
| 할인과 재고원가 | LOT 원가는 행 단가, Inbound 금액은 행 공급가; Payable은 할인 반영 전표 총액 | 할인 원가배분 여부를 사용자 결정. 현재 합계 차이는 무조건 오류로 단정하지 않음 |
| 0원 확정 | 단가 0/총액 0 경계는 입력상 가능, SQL Migration의 원거래 `original_amount > 0`과 충돌 가능 | 중앙 SQL Server 경계값 테스트. SQLite 테스트만으로 성공 판정 금지 |
| 전표 요약금액 | GUI 전일잔액+현재전표-입력지급 구조; 당일 다른 매입까지 포함한 완전한 거래처 잔액은 아님 | 화면 의미 표시 및 실제 원장/수금지급 완성 후 authoritative 잔액 제공 |
| 조회 성능 | 매입 목록 전체를 받아 GUI가 일자 필터, 동기 HTTP | 누적 데이터에서 중앙 조회/검색/페이지와 GUI 응답성 점검 |
| 사용 후 수정 | 추가 입고/배분 FK는 차단 사례가 있으나 향후 출고/반품 규칙 없음 | 사용 상태를 명시 검사하고 오류 메시지·회수/정정 정책 마련 |
| 수입 매입 | 현재 materialize는 DOMESTIC LOT, BL 입력만으로 수입원가가 완성되지 않음 | 수입원가 확정 최소 Slice 별도 필요 |
| MeatWatch | 환경 URL/token 템플릿을 이용하는 선택적 조회, 미설정 시 503/수동 입력 | 공식 운영 연동/신고 완료와 구분. 외부 장애가 저장 원장을 훼손하지 않게 검증 |
| 추적 정보 | BL/이력번호 등을 LOT에 보존; 일부 생산/컨테이너 정보는 매입입력 부족 | 실물 자료 필수항목과 일반매출까지 추적 연계 확인 |

이 목록은 미래의 수정 지시이며 이번 Work에서는 아무 코드도 바꾸지 않았다.

## 8. Audit / History 정밀 판정

### 8.1 DB와 Service

Audit 모델은 `models.py`가 아니라 **`audit_service.py`의 `AuditEvent`**이다. 중복 모델을 만들지 않는다.

| Column | 현재 SQL Server 정의 | 업무 질문 |
|---|---|---|
| audit_event_id | BIGINT IDENTITY PK | 이벤트 식별/정렬 |
| comp_code / user_id | NVARCHAR(20) / (50), NOT NULL | 어느 회사/누가 |
| menu_code / action | NVARCHAR(50) / (30), NOT NULL | 어느 메뉴/무슨 행동 |
| entity_type / entity_id | NVARCHAR(50) / (100), NOT NULL | 어떤 Entity/Record |
| source | NVARCHAR(200), NOT NULL | 호출 경로 |
| before_json / after_json | NVARCHAR(MAX), nullable | 변경 전/후 |
| reason | NVARCHAR(1000), nullable | 변경 사유 |
| related_entity_type / related_entity_id | NVARCHAR(50) / (100), nullable | 연관 Entity/Record |
| created_at | DATETIME2, NOT NULL, SYSUTCDATETIME() | UTC 언제 |

복합 index는 `(comp_code, entity_type, entity_id, audit_event_id)`와 `(comp_code, created_at, audit_event_id)`다. Purchase FK를 두지 않아 Draft 삭제 후 이력이 남는다. 별도 document_no/module/request correlation column은 없으며 전표번호는 Snapshot 안에 있다. menu/source를 업무문맥으로 사용한다. 향후 여러 원거래/반품/Release 관계를 표준화해야 한다.

Helper는 `db.add()`만 수행하고 자체 commit하지 않는다. 업무 저장과 Audit INSERT가 같은 transaction에 들어간다. Decimal은 문자열, 날짜/시각은 ISO 표현, JSON은 Unicode 보존이다. Snapshot은 flush/refresh/관계 재조회 후 Purchase Header/Detail뿐 아니라 실제 생성 Inbound/InboundItem/LOT/Payable 값까지 담는다.

### 8.2 적용/미적용

| 기준 | 현재 판정 |
|---|---|
| CREATE / UPDATE / DELETE / CONFIRM / CANCEL | main 상품매입 경로에 연결됨 |
| STATUS_CHANGE / OVERRIDE / RETURN | 공통 표준의 목표이며 대응하는 전 ERP 업무 경로는 미구현 |
| 회사/사용자/시간/Entity/전후 값 | 매입 Audit에 저장 |
| 사유 | CANCEL 필수; 일반 UPDATE 선택. 모든 중요행위 사유정책 완성은 아님 |
| 원거래 연결 | 매입 Snapshot 및 관련식별자 있음. 반품/Release의 원거래 연쇄는 아직 없음 |
| 조회 API | `/api/v1/companies/{comp_code}/purchases/{purchase_id}/history`; 회사 및 PURCHASE_GENERAL read 검사, event ID 순서 |
| 삭제 후 조회 | Draft 삭제 후 Audit 조회 가능 |
| GUI History | 전용 viewer 없음. 매입 화면 “이력번호/BL 조회”는 MeatWatch 조회이며 Audit History가 아님 |
| append-only | Audit 수정/삭제 API 없음. 일반 application 경로에서 append-only |
| DB 차원의 보호 | SQL GRANT/권한/trigger 등 일반 사용자 직접 SQL 변경방지 실검증 필요. 앱 API 부재만으로 DB까지 불변이라고 판정하지 않음 |
| 다른 Master/업무 | 공통 helper가 있어도 모두 호출된 것은 아님. 회사/거래처/상품/창고/권한 등 상세 이력 확장 남음 |
| 중앙 Schema | 사용자 보고상 SERVER에 table 존재, COLLATE 표현 DIFF. 이번 Work 직접 Schema 조회 없음 |
| 중앙 실제 이벤트 | 서버 배포 SHA/업무 저장 후 Audit INSERT·조회 실확인 필요 |

현재 조회 API는 Purchase 전용이며 범용 Audit Entity 검색 API는 아직 없다. API의 before_json/after_json은 JSON 문자열이므로 GUI viewer가 파싱·변경 항목 비교·사유·관련전표 탐색을 해야 한다. 단순 원문 표시와 업무 변경 비교의 범위를 구분한다. UTC는 저장 규칙이며 GUI 표시 시간대도 명시해야 한다.

### 8.3 테스트와 한계

ERP tests 5개 파일: `test_permissions.py`, `test_trade_common.py`, `test_purchase.py`, `test_purchase_audit.py`, `test_purchase_audit_gui.py`. 사용자 최신 DEV 보고는 총 38 passed. 최근 Audit 관련 추가 테스트는 22개이며 이전 테스트 16개와 합쳐진 결과다.

Audit API 테스트는 SQLite 별도 engine/FK 및 FastAPI/middleware/실제 ORM·업무코드를 사용하고 SQL Server 발번 부분만 대체한다. CREATE/UPDATE/CONFIRM/CANCEL/DELETE Snapshot, 삭제 후 이력, Audit INSERT 실패 시 rollback, 회사/권한 거절, 기간/입력 경계 및 downstream FK 차단 등을 검증한다. GUI offscreen 테스트는 취소사유 dialog와 API 전송 등 제한된 상호작용이다.

ODBC/SQL Server DDL·IDENTITY·서버 발번 잠금·collation·중앙 권한·실제 서버 배포·Windows 화면 전체·GUI History는 이 테스트의 완료 증거가 아니다. 이번 Work의 구문검사도 이 실행 테스트와 구분한다.

### 8.4 승인 후 첫 실제 개발작업: Audit 완전 검증/마감

1. DEV 작업트리/SHA와 미커밋 verifier diff 확인, 사용자 현재 38 passed 근거 기록.
2. SERVER에서 동일 engine의 identity 확인→중앙 Schema 읽기 전용 검증. COLLATE 수정의 구조 검사 보존 확인.
3. server API 배포 SHA와 코드 연결을 확인. 추가 DDL이 필요한지 여기서 판단한다.
4. 사용자 승인한 테스트회사/자료로 생성→조회→수정→취소, Draft 삭제 및 무권한 거절을 실행하고 중앙 Audit/원장/rollback 확인. 테스트 입력도 DB 쓰기이므로 이번 문서조사에는 포함하지 않았다.
5. 실제 부족한 GUI History viewer와 최소 중앙 검증 결함을 작은 변경으로 보완한다. “검증”과 “새 UI 개발” 작업량을 나눈다.
6. DB 일반사용자 변경통제, 삭제 후 보존, 전후 상세/사유/UTC 표시까지 체크하고 증거를 docs에 남긴다. 중앙 확인 없이 마감하지 않는다.
7. 전 Master 이력을 한꺼번에 만들며 매입 마감을 미루지 않는다. 1차 범위 Master와 중요업무에는 각 다음 Slice에서 동일 표준을 적용한다.

## 9. FinSales → ERP 계승 판정

분류: **① ERP 통합됨 / ② ERP 설계 반영·미구현 / ③ 반드시 계승 / ④ 새 ERP에는 필요 없음 / ⑤ 확인 필요**. 하나의 항목에 설계/Reference/검증 상태가 함께 있을 수 있어 복수 표기한다. ①은 공통 Master 기반에만 해당하며 Financing 계산이 ERP에 이미 이식됐다는 뜻이 아니다.

실행 분석대상은 root `main.py`/`mxmn_finsales_app.py`/`models.py`/`database.py`와 API 설정·auth migration이다. `mxmn_finsales_app_20260919.py`는 이전 GUI 기준, `client.py`는 localhost :8000 `/contracts`를 호출하는 테스트 클라이언트다. 현재 :8001 root API와 일치하는 운영 GUI라고 볼 수 없다. 비어 있는 `api/main_api_fin.py`, `main_finsales.py`, src 파일들은 구현 완료가 아니다.

| 항목 | FinSales 실제 코드 | ERP 상태와 계승 판정 |
|---|---|---|
| 거래처/상품/창고/LOT | 문자열/Float 중심 TB_LOT_MASTER, BL unique | ERP Master 이미 존재 ①. FinSales Master 복제는 ④ |
| 계약구조/복수 LOT | LOT 행에 조건 직접 저장; 완성 Contract/Term 관계 없음 | ②③. ERP Contract↔LOT 연결로 구현 |
| 계약기간 | 기본 날짜/90일 및 1차 기간 입력 | ②③. 계약별 기간, 연장 Term 및 만기 통제 필요 |
| 이자 | 매입일~출고일 양끝 포함, 연365, 고정1/2차 이율 및 기간 | ②③. Segment row로 확장; 날짜 역전 처리 재설계 |
| 수수료 | 원/kg 수수료 round, 별도발행 선택 시 출고단가 포함액 0 | ②③. 계산금액 자체와 청구법인/방식/발행상태를 별도로 보존 |
| 창고료 | 예상중량×KG_DAY×기간+KG 입출고비+BOX 계근비 후 kg당 round | ②③. 기간별 이미 청구한 비용 중복제거 필요 |
| 가변비용 | sticker/inspection/other 저장 컬럼은 있으나 핵심 계산에 전부 반영되지 않음 | ②③⑤. 단위 BOX/KG/FIXED와 실제 포함범위 확정 |
| 일회성 비용 | GUI 비용 표에서 정액을 합산 | ③. Snapshot·DB 저장·세금/청구법인 연결은 별도 |
| 평균중량 | 저장 avg_weight를 사용. 최초 총중량/BOX 비율 전체정밀도를 자동 유지하지 않음 | ②③. 최초 값 고정, 내부 정밀도와 표시 소수점 분리 |
| 부분출고 | BOX 입력과 예상잔량 표시 | ②③. 실제 Outbound 원장/승인/누적 확정재고와 연결 없음 |
| 최종 잔량마감 | 평균×마지막 BOX 방식; 최초중량-누적 확정량 보정 없음 | ②③. ERP 마지막출고에서 잔량 0 맞추기 |
| 입금요청액 | 예상중량×단가합+정액비용 round | ②③⑤. VAT/정책/실제 자료 금액 검증 필요 |
| 출고조건 저장 | `save_custom_changes`는 계산+안내 메시지 | ②③. 출고자료의 실제 DB 저장 완료로 판정 금지 |
| 창고담당자 발송 | `send_shipping_notice_to_manager`는 본문/시간/수신자 구성+안내 메시지 | 자동발송 완료 아님. 외부 실제 발송은 후속 ④(1차 필수 제외); 수동 전달과 기록은 필요 |
| 계약조건 저장/변경 | admin PUT으로 LOT 조건 덮어쓰기 | ②③. “요율 버전 기록” UI 명칭과 달리 immutable Term/history 없음 |
| 연장 | 기존 조건 변경 가능할 뿐 잔존원가/기간별 Term 계산 없음 | ②③. 출고 완료량에 연장수수료 중복 부과 금지 |
| Calculation Snapshot | 확정 계산의 불변 입력/결과/override 저장 없음 | ②③. PDF와 재현 가능한 계산원본으로 필수 |
| PDF | QPrinter/QTextDocument HTML 출력 실제 구현 | ③⑤. 레이아웃 참고, 확정 Snapshot/VAT/정산 출력은 검증 필요 |
| Simulation | 날짜별 12개 열 계산/표시 | ③. 일회성비용 등 단건계산과 일치 여부 회귀 필요 |
| 실제 자료 검증 | 문서에 BUD0106141 등과 검증기록 언급 | ⑤. 원본 계약/Excel expected 값을 이번 Work가 새로 대조하지 않음 |
| 보증금/정산차액/관련업체 | 완성 원장/배분 없음 | ②③. ERP 설계대로 구현 |
| 독립 사용자/권한 | admin/partner login·LOT 접근제한 있음 | Reference 보존; ERP에 중복 auth 이식은 ④ |
| 누적BOX 숫자 | 기존 잔량 표시 기반 | 참고 보존. ERP 재고 원본으로 쓰는 방식은 ④ |
| GUI 내부 계산/고정2구간/Float | 실제 구현 방식 | 결과 비교 참고; ERP Engine 구조로 그대로 복사는 ④ |

### 9.1 놓치면 안 되는 실제 Reference 결함/차이

- Python `round()`는 문서의 무조건 올림/절사와 다르다. Float와 ties-to-even 결과를 돈 정책으로 그대로 승인하지 않는다. Decimal 기반 중앙 policy에서 항목별 반올림/올림/절사 시점을 명시한다.
- 음수 날짜 차이를 최소 1일로 만들 수 있다. 매입 전 출고/입고 전 출고는 정상 1일 이자가 아니라 날짜 오류로 다뤄야 한다.
- 출고 BOX가 잔량을 넘는 것을 원장 수준에서 막는 통제와 final residual compensation이 없다.
- 보관료 항목에 sticker/inspection/other가 저장된다는 이유로 모두 청구됐다고 보면 안 된다. Simulation과 단건 정액비용도 같다고 가정하지 않는다.
- UI의 “VAT 포함” 라벨은 별도의 과세/면세 세액계산 완료 증거가 아니다.
- 한 BL당 unique 행은 혼적 품목별 여러 LOT 요구와 충돌한다. ERP는 BL/Container/상품별 LOT 관계를 사용한다.
- 샘플 `avg_weight=21.43`과 총중량/BOX의 실제 나눗셈 정밀도 차이가 마지막 잔량에 누적될 수 있다. 90일/이율/수수료 샘플은 모든 계약 기본 정답이 아니다.
- FinSales API 시작 시 `init_default_data`가 샘플/company/user를 삽입하고 commit할 수 있다. 읽기 전용 조사용으로 서버를 실행하면 안 된다. 평문 암호/메모리 session·만료 부재도 ERP 구현으로 옮기지 않는다.
- `finsales_contracts`가 과거 중앙 DB 문서에 있어도 현재 root 모델/API가 실사용한다는 근거는 없다. 실제 사용 여부 확인 필요.

FinSales와 새 ERP 결과가 다르면 “동일해야 한다”만으로 판정하지 않는다. **실제 계약/업무자료 → 승인 업무규칙 → 기존 FinSales** 순서로 차이 원인을 정한다. 기존 결함을 고친 의도된 차이는 expected 값과 사유를 기록한다.

## 10. 최신 유효 개발원칙과 대체된 과거 원칙

현재 유효:

- ERP 단일 SoR, Master 공용, 회사별 권한/거래/원장 구분, LOT 개별원가.
- Financing≠Sale. 계약관계와 실제 매입/매출/출고/입금 거래를 연결한다.
- 계약상대방·매입처·매출처·출고처·입금자를 독립 참조하고 승인된 관련업체 관계를 보존한다.
- 거래 원본+배분/정정/반품으로 원장을 보존한다. 재고/채권/채무를 한 숫자 덮어쓰기로 관리하지 않는다.
- Contract Term/Interest Segment/Charge Term/Calculation Snapshot/Override 이력을 저장한다.
- 일반자는 입금 확인 전 Financing 출고확정 금지. Master 예외는 사유/승인자/일시/금액과 Audit 필수.
- 처음 LOT 중량/BOX 고정평균, 마지막 잔량은 누적 확정 출고 차감으로 보정. 실계근 계약은 별도 정책.
- 원가확정 전 이자와 이후 판매이자를 기간경계로 분리, 실제 비용의 수입원가/출고단가/별도청구 중복 금지.
- 수수료 청구법인 및 과세/면세를 분리하고 세무 전표정책은 사용자 확인을 거친다.
- 보증금은 독립 ledger+계약배분. 일반 미수 잔액과 자동 혼합하지 않는다.
- append-only 상세 Audit와 Header 최근행위 필드는 역할이 다르다. 중요 변경의 원값/수정값/사유 보존.
- 작은 Vertical Slice마다 코드→의미 있는 테스트→사용자 실행→문서→Git 정리. 실제 SQL 변경은 DB 대상 확인부터.

대체/폐기된 현재 실행방향:

| 과거 방향 | 현재 방향/변경 이유 |
|---|---|
| ERP/FinSales 독립 신규기능 병행 | 9/29 ERP 통합으로 전환. 중복 Master/원장/계산 정책 방지 |
| 동일 사업자를 업무종류별 거래처로 기본 복제 | Single Master+관계+분리원장. 기존 데이터 강제 합병은 별도 |
| 최초 서버 후보/홈 PC를 현재 SERVER로 간주 | 9/23 이후 서버 이전/9/26 실제 구축 기준 |
| `.venv`가 유일한 최신 경로 | 10/02 사용자 `venv` 확인 우선. 공용 환경 원칙은 유지 |
| Audit Work가 아직 main에 없다고 판단 | 현재 main `8cee784`에 있음. 중앙 배포/검증은 별도 |
| 고정 1/2차 이율·LOT 조건 덮어쓰기 | Segment/Term/Snapshot으로 계약과 과거 결과 보존 |
| 누적BOX/직접수정으로 재고 확정 | ERP 입출고 원장과 반품/정정, 잔량 통제 |
| 모든 금액 일괄 ceil/int/round | 항목별 정책 확정. 기존 매입 ceil 규칙을 임의 변경하지 않음 |
| DB 이름만 같으면 중앙 대상으로 판단 | instance/machine/db 및 실제 engine 대상 확인 |

## 11. 1차 완성본 정의와 확정 범위

2026-10-02 사용자 검토에서 1차 완성본의 범위를 다음과 같이 확정했다.

**1차 완성본의 기준은 화면 수나 일부 Pilot 기능이 아니라, 현재 프로그램에서 실제 Business Process를 시작부터 종료까지 수행할 수 있는 수준이다.**

**일반유통:** 회사/권한/기초재고·잔액 → 매입 → 입고/LOT → 매출 → 출고/잔량 → 미수/미지급 → 수금/지급/배분 → 필요시 원거래 반품 → 원장/이력/출력까지 실제 업무 흐름이 연결되어야 한다.

**Financing:** MXMN의 핵심 목적 중 하나이며 선택적 확장기능이 아니다. 국내매입/수입대행/BL양수도 3개 계약유형의 전체 과정을 1차에 포함한다. 개발은 작은 Vertical Slice로 나누되 기능범위를 2차로 미루어 잘라내지 않는다.

### 11.1 Financing의 확정 Business Process

공통 시작점은 **거래처와의 계약체결 및 계약서 작성/계약조건 확정**이다. 이후 원가확정 전 단계는 계약유형에 따라 분기하고, 원가확정 이후의 일일정산·수금·출고·최종정산·완료 흐름은 공통화한다.

```text
[거래처와 Financing 계약 체결 / 계약서 작성 / 계약조건 확정]
                         ↓
                  [계약유형 분기]
            ┌────────────┼────────────┐
            │            │            │
         수입대행      BL양수도       국내매입
            │            │            │
            ├─ LC 개설 등 필요한 수입절차 ─┤       │
            ├─ 수입 / 보세창고 입고 ───────┤       │
            ├─ 검역 완료 ──────────────────┤       │
            └─ 수입원가 정산/확정 ─────────┘       │
                         │                          │
                         └──────┬───────────────────┘
                                ↓
                     [최종 매입원가 확정]
               (국내매입은 매입원가에서 바로 진입)
                                ↓
                          [일일 정산]
                                ↓
                      [입금요청 / 수금]
                                ↓
                         [출고 승인]
                                ↓
                       [부분출고 반복]
                                ↓
                         [최종 출고]
                                ↓
                 [최종 비용·금액·잔액 정산]
                                ↓
             [보증금/차액/미청구비용 등 종료 확인]
                                ↓
                          [계약 완료]
```

수입대행과 BL양수도는 계약 후 LC 개설 등 필요한 수입절차부터 수입/보세창고 입고·검역·수입원가 정산을 거쳐 원가를 확정한다. 국내매입은 확정된 국내 매입원가에서 공통 Financing 흐름으로 바로 진입한다. 세 유형 모두 원가확정 이후에는 동일한 원칙의 일일정산→수금→출고→최종출고→정산→완료 Cycle을 사용한다.

### 11.2 1차 필수 확정 범위

| 업무 | 1차 필수 범위 | 완성 판단 |
|---|---|---|
| Master/권한/Audit | 현재 Master 보완, 중요 Master변경/사용자·권한 변경 이력, 회사 격리 | 무권한 변경/다른회사 거래 거절, 변경 원본 확인 |
| 매입/재고 | 기존 매입 중앙 마감, 기초재고/입고/LOT 사용 후 수정통제, 재고조회 | 입고-출고-반품 합계와 LOT잔량 일치 |
| 일반매출/출고 | LOT별 Sale/Outbound/Receivable, 취소/정정/부분흐름 | 재고초과 금지, 단일 확정 atomic 처리 |
| 수금/지급 | 실제금액/입금자/지급처/회사/일자, 원거래 Allocation·취소 | 중복/초과배분 거절, 잔액 재현 |
| 계약/계약서 | 3유형 계약등록, 계약서, 복수 LOT/Term/Segment/관련업체, 변경·연장 이력 | 계약조건과 실제 거래가 추적 가능 |
| 수입형 원가확정 | 수입대행/BL양수도의 LC 등 필요한 수입단계, 수입/보세입고·검역·수입원가 정산 및 확정 | 승인된 최종원가가 Financing 원금으로 연결 |
| 국내매입 원가 | 국내매입 확정원가에서 Financing 공통 Cycle로 연결 | 별도 중복 원가원장 없이 계약과 연결 |
| Financing 일일정산 | 이자/수수료/창고료/가변비용/정액비용, Term/Segment, Snapshot/Override | 날짜별 계산과 과거 결과 재현 |
| 입금요청/수금/출고통제 | 요청금액→실제입금 확인→승인→부분출고→최종출고 | 미입금 일반출고 거절, 재고·돈·Audit 일치 |
| 정산/보증금/차액 | 최종중량/금액, 차액 ledger, 보증금 수취/배분/상계/반환, 미청구비용 | 재고0뿐 아니라 모든 금전관계까지 종료 |
| 반품/Return Settlement | 일반 매입·매출반품 및 Financing 원거래 연계, 정산방식 전체 | 삭제/음수수량이 아닌 원거래 연결로 재현 |
| 서비스·법인별 별도청구 | 수수료/창고료 등 별도 청구, 세금 Snapshot/발행상태/수금 연결 | 물품원가와 비용 중복청구 없음 |
| PDF/실제자료 회귀검증 | 계약/입금요청/출고/정산 출력, 실제 자료 expected 비교 | 실제 업무에서 처음부터 끝까지 반복 수행 가능 |
| 통합운영 | SERVER/DEV/WORK, 중앙 Schema/API, 백업/복구, 회사격리, Audit | 일반유통과 Financing 실제사례를 끝까지 수행 |

**Pilot 축소안은 폐기한다.** 국내매입/Standard Sale만 구현하고 1차 완료로 판정하지 않는다. 3개 Financing 계약유형과 전체 Financing Cycle은 모두 1차에 포함한다.

### 11.3 금액·수치 처리 정책

새로운 전사 단일 `round/ceil/truncate` 규칙을 만들지 않는다. **현재 이미 확정·구현된 수치 원칙은 그대로 준행**하고, 신규 Financing 항목은 통상의 상거래 원칙과 실제 계약/업무자료를 기준으로 항목별 정책을 확정한다.

현재 유지할 기준:
- 단가·가격·개별원가: 정수 원. 기존 확정된 올림 정책을 임의 변경하지 않는다.
- 중량: 소수점 둘째 자리 표시/업무 기준.
- BOX: 정수.
- 환율: 소수점 둘째 자리.
- 수수료/VAT 등 기존에 확정된 원단위 처리 규칙은 기존 구현/업무기준을 우선한다.
- 매입 공급가/세금 등 현재 코드에 확정된 계산은 별도 업무결정 없이 변경하지 않는다.
- Financing 이자/수수료/창고료/정액비용/총액/VAT는 FinSales의 Python `round()`를 정답으로 복사하지 않는다. 실제 계약자료와 기존 승인원칙을 대조해 Decimal 기반 항목별 정책으로 고정한다.
- 계산정책을 바꾸는 경우 과거 Snapshot을 재계산하지 않고 policy version/변경사유를 남긴다.

### 11.4 1차 이후 범위의 의미

전자세금계산서 완전자동발행, 외부 창고 자동지시/메일/SMS, MeatWatch 일괄 자동신고, 고급 경영보고, 고객용 독립 Portal, 전면적인 코드폴더 재편 등은 1차 이후 자동화/고도화 후보로 둘 수 있다.

다만 **Financing의 실제 Business Process 자체에 필요한 LC/수입/보세입고/검역/원가확정 정보와 상태는 1차에서 빠질 수 없다.** 외부 시스템과의 완전자동화는 후속일 수 있지만, ERP 안에서 해당 업무단계와 근거를 기록·승인하고 다음 단계로 이어갈 수 있어야 1차 완료로 본다.

## 12. 실행 로드맵 — 각 단계의 완료조건

아래 DB/API 이름은 **미구현 후보 설계**다. 실제 Migration 전 기존 models/AccountTransaction/Allocation과 중복을 검토한다. 새로운 이중 재고원장/이중 미수원장을 만들지 않는다. 각 단계는 앞 단계 승인 후 시작한다.

### 단계 0 — Audit/History 중앙 검증과 마감

- 목적/선행: 본 문서 승인 및 DEV/SERVER 대상 확인 후, 현재 Audit가 중앙에서 동작하도록 완결.
- DB/API: tb_audit_event 구조/보호/read-only 검사; 현재 조회 API와 매입 5종 호출 검증. 추가 DDL은 필요성 확인 후 별도.
- GUI: 매입 상세 이력 viewer 최소 범위, 변경항목/전후값/사유/UTC 표시/삭제이력 탐색.
- 규칙/Audit: 같은 transaction 기록, Audit실패=업무 rollback, 일반사용자 수정·삭제 불가.
- Test: 기존 38 재확인+중앙 Schema/실제 이벤트/권한/rollback 및 GUI. COLLATE 구조비교 회귀.
- 사용자 검증/완료: 중앙 회사·전표의 생성/수정/취소 이력을 사용자가 읽고 이해; DB 대상과 배포 SHA, 결과 docs 기록.
- 작업량/시간: 작은~중간, AI 2~4시간 / 사용자 실행 포함 4~8시간. viewer 범위 확대·SQL 권한 결함은 상한 초과 가능.

### 단계 1 — 상품매입·LOT/재고 마감

- 목적/선행: 단계0; 매입의 물류·미지급·원가가 실제로 일치.
- DB/API: 기존 Purchase/Item/Inbound/LOT/AccountTransaction; 사용 후 수정·취소, LOT API/기초재고 수정 경계, 할인/0원 정책.
- GUI: 매입→LOT/입고/원장 조회, 오류 안내, 최소 재고잔량 조회.
- 규칙/Audit: 확정 atomic, 연결 사용 후 직접 원본변경 통제, 원가/할인/BOX/KG 정책 확정; 중요한 Master/재고수정 Audit.
- Test: 0원/할인/과세·면세/기간/중복/다창고/사용 후 변경거절 및 중앙 SQL 무결성.
- 사용자 검증/완료: 실제 매입 1건을 문서와 대조, 입고량/LOT원가/미지급 재현; 데이터 사용 상태 통제 확인.
- 작업량/시간: 작은~중간, AI 2~4 / 실제 4~8시간.

### 단계 2 — 일반매출 Vertical Slice

- 목적/선행: 단계1; LOT에서 물품 판매→실제출고→미수까지 연결.
- DB/API: Sale/SaleItem/Outbound/OutboundItem 후보, 기존 LOT 및 AccountTransaction 참조; 작성/조회/확정/취소 API.
- GUI: 매출입력/LOT선택/출고량/원가·단가/거래처/잔량/전표탐색.
- 규칙/Audit: BOX/KG 초과출고 방지, 회사·창고·권한/기간, 확정 중복 방지, 동시출고 잠금, 확정 후 정정 원칙; CREATE/CONFIRM/CANCEL.
- Test: 같은 LOT 동시확정/재시도, 품절/부분출고/다LOT/과세·면세, 실패 시 재고·미수 동시 rollback.
- 사용자 검증/완료: 한 매입LOT를 두 번 판매/출고하고 잔량·미수 대조; 조회/취소와 거절 사례 확인.
- 작업량/시간: 큰, AI 6~10 / 실제 10~18시간.

### 단계 3 — 수금/지급·배분/잔액

- 목적/선행: 단계2의 미수와 기존 미지급; 실제 돈을 원거래에 연결. Financing 전 필수.
- DB/API: Receipt/Payment 후보 + 기존 AccountTransactionAllocation 재사용 검토; 입금/지급확정·배분·취소·잔액조회 API.
- GUI: 입금자/거래처/회사/입금일/금액, 여러 전표 선택·부분배분, 미배분잔액/원장탐색.
- 규칙/Audit: 중복·초과배분 금지, 실제 입금확인 권한, 취소 시 배분 회수와 기간, 회사간 돈 자동이동 금지; 확인/배분/취소 이력.
- Test: 부분/다중전표/초과입금/다른입금자/중복재시도/동시배분/기간/rollback.
- 사용자 검증/완료: 일반거래 입금/지급→미수/미지급 감소→취소 복원→원장 재현.
- 작업량/시간: 중간~큰, AI 5~9 / 실제 8~16시간.

### 단계 4 — 수입형 Financing 원가확정 Process와 서비스 청구 기반

- 목적/선행: 단계1/3; 수입대행·BL양수도의 계약 후 LC 등 필요한 수입단계→수입/보세입고→검역→수입원가 정산/확정을 ERP 업무흐름으로 연결하고, Financing 원금과 별도 과세법인 청구를 계산 가능한 거래로 만들기.
- DB/API: 원가확정 Header/비용/배분/Snapshot 후보, 기존 매입LOT/ExpenseCode와 연결; 최소 Service charge 거래 및 원장 연결.
- GUI: 계약/LC 등 수입진행 상태, BL/Container, 수입·보세입고/검역 상태, 상품별 비용·지급일·확정일·kg당원가, 승인/근거, 서비스 청구법인/과세/발행상태.
- 규칙/Audit: 확정 전 이자는 원가확정 전일까지, 이후는 매입일 이후; 비용 중복회수 금지, 사용 후 원가변경은 정정/향후비용; 승인/Override 사유.
- Test: 혼적 다LOT 비용배분/0BOX·0KG/날짜경계/추가비용/별도법인·VAT/중복청구/과거Snapshot.
- 사용자 검증/완료: 수입대행과 BL양수도 실제 사례가 계약 이후 필요한 수입단계→보세입고/검역→수입원가 확정까지 이어지고, 실제 수입원가표 및 별도 수수료가 ERP 확정값/원장과 연결.
- 작업량/시간: 큰 범위. 기존 4~8 / 실제 8~16시간 추정은 '최소 원가확정' 기준이므로 재산정 필요. 1차에는 필요한 수입 Business Process 기록/승인까지 포함하되 외부기관 자동연동은 후속 가능.

### 단계 5 — Financing Contract Vertical Slice

- 목적/선행: Financing 업무의 시작점은 거래처 계약체결/계약서 작성이다. 공통 계약 Skeleton은 수입원가 단계보다 먼저 설계·등록할 수 있으며, 실제 실행/원가확정 연결은 단계2~4의 ERP 거래/LOT와 결합한다.
- DB/API: fin_contract/term/contract_lot, interest_segment/charge_term/authorized_party 후보; 등록/승인/변경·연장/조회.
- GUI: 3유형/계약번호/계약상대방/다LOT/실거래 당사자/기간/조건/관련업체 승인.
- 규칙/Audit: 공용 Master 참조, 다LOT, 고정 최초중량/BOX, 조건 version, 연장잔존원가, 권한 분리; CREATE/CONFIRM/STATUS_CHANGE/Term변경.
- Test: 다른회사LOT/중복연결/기간겹침/권한/계약상대방과입금자다름/연장 원조건 보존.
- 사용자 검증/완료: 국내매입 및 수입형 계약을 ERP LOT와 연결, 새 Master 복제 없이 조건/연장 이력 조회.
- 작업량/시간: 중간, AI 4~7 / 실제 8~12시간.

### 단계 6 — Financing 계산 Engine/Snapshot

- 목적/선행: 단계5와 항목별 돈 정책 승인; GUI와 독립 계산.
- DB/API: release_calc 후보의 입력/자동결과/Override/최종값/policy version Snapshot; 예상계산/확정/Simulation API.
- GUI: 계산 항목/산식/기간·단위/청구법인/포함·별도청구, override 사유, 내부/공개comment.
- 규칙/Audit: inclusive 일수/Segment, 비용청구기간·중복제거, Term별잔존수수료, 고정평균/실계근, 최종중량보정, 음수 날짜거절; OVERRIDE/CONFIRM.
- Test: 1/30/31/60/61/90/91일·연장·윤년의 승인 day basis, 모든비용단위/반올림경계/월별선청구/최종잔량; FinSales와 의도된 차이 표.
- 사용자 검증/완료: 승인자료의 kg원가/이자/비용/요청금액 재현, Master 변경 후 과거Snapshot 불변.
- 작업량/시간: 큰, AI 6~10 / 실제 10~18시간.

### 단계 7 — 입금요청/확인·출고통제/부분출고

- 목적/선행: 단계3/6; 미수 없는 Financing 출고를 실제 재고와 연결.
- DB/API: fin_release/item/payment_request + ReceiptAllocation, 기존 Sale/Outbound; 요청→계산→입금확인→승인→출고확정.
- GUI: 요청/입금대조/부족금액/승인대기/창고전달자료/실출고량·일자/최종계산.
- 규칙/Audit: 일반자 미입금확정 금지, Master예외 사유·승인자·일시·금액, 재고예약/동시확정, actual party 승인, 최종잔량 보정; STATUS_CHANGE/OVERRIDE/CONFIRM.
- Test: 부족입금/다른입금자/중복출고/두요청경합/예외권한/확정실패rollback/예상과실제차이.
- 사용자 검증/완료: 입금 전 거절→입금후 부분출고→최종출고 잔량0, 매출/출고/미수/수금 연결.
- 작업량/시간: 큰, AI 5~9 / 실제 8~16시간.

### 단계 8 — 정산차액·보증금·반품/종료

- 목적/선행: 단계7; 재고 외 돈/담보/별도청구까지 종료.
- DB/API: settlement balance/transaction/allocation, deposit ledger/allocation 후보, purchase/sale return 원거래관계; 상계/반환/재배정/종료 API.
- GUI: 차액발생/상계, 공동담보배분, 원거래반품, Standard Sale/Return Settlement 선택, 종료checklist.
- 규칙/Audit: 원금/경제적수익 분리, 임의세무판정 금지, 보증금 중복배분한도, 반품은 삭제/음수입력이 아님, LOT잔량0만으로계약종료금지; RETURN/OVERRIDE/CANCEL/STATUS_CHANGE.
- Test: 부분반품/누적한도/차기상계/담보공동배분/해제·반환/별도법인청구미완료종료거절/rollback.
- 사용자 검증/완료: 두 정산방식 및 담보수취→배분→해제/반환 사례, 재고/미수/미지급/정산/보증금잔액 재현.
- 작업량/시간: 매우 큰, AI 6~12 / 실제 12~24시간. 세무정책/반품예외 범위가 늘면 추가 산정.

### 단계 9 — PDF/실제 업무자료 회귀검증

- 목적/선행: 단계6~8; 숫자와 외부 전달문서가 같은 확정원본 사용.
- DB/API: Snapshot 조회/출력 metadata, 실제 expected fixtures; 출력/재출력/문서version.
- GUI: 입금요청서/출고/정산 PDF preview/저장, 내부comment 비공개.
- 규칙/Audit: 현재Master재계산 금지, 공개문구/세금/청구법인 명시, 자동발송은 별도 범위; 출력version과확정Snapshot 추적.
- Test: BUD0106141 등 승인 원본↔FinSales↔ERP 항목별 비교, 페이지/단위/음수·0/다LOT·장문, snapshot재출력.
- 사용자 검증/완료: 원본Excel/계약서/PDF와 금액차이 승인표, 실제 사용할 PDF 인쇄확인.
- 작업량/시간: 중간, AI 4~7 / 실제 6~12시간.

### 단계 10 — 초기버전 전체 통합·운영검증

- 목적/선행: 모든 필수 Slice 마감; 반복 일상업무 가능한 상태 확인.
- DB/API/GUI: 배포버전/Schema일치, 중앙운영/클라이언트설정/회사격리/오류회복/백업복구/조회성능.
- 규칙/Audit: 기간마감/중복요청/확정거래 정정/관리자예외/일반사용자 보호. WORK환경은 접근 가능 시 확인.
- Test: 전체 2개 Cycle, 장기간·반복·재시작/통신실패, 중앙 SQL 회귀, 대표 데이터 규모 성능, 테스트DB 복구.
- 사용자 검증/완료: 일반유통·Financing 실제사례 각 최소1회 끝까지 실행, 숫자/출력/Audit 일치와 운영checklist 승인. 현장 미확인/미지원유형 명시.
- 작업량/시간: 큰, AI 4~8 / 실제 8~16시간.

## 13. 예상시간과 작업방식

단위는 집중 작업시간이며 AI 벽시계 사용시간과 사용자 포함 실작업시간은 **더하지 않는다**. 실제 시간에는 AI 작업·사용자 실행/로그 공유/업무판단/반복확인을 포함한다. 낙관은 규칙·자료가 준비되고 중앙 실행이 순조로운 경우의 하한, 일반은 반복검증이 필요한 경우의 범위이다. 지연 대기/사용량제한/세무 자문/출장·접근 대기는 포함하지 않는다.

| 단계 | AI 낙관~일반(시간) | 사용자 포함 낙관~일반(시간) |
|---|---:|---:|
| 0 Audit | 2~4 | 4~8 |
| 1 매입·재고 | 2~4 | 4~8 |
| 2 일반매출 | 6~10 | 10~18 |
| 3 수금·지급 | 5~9 | 8~16 |
| 4 수입형 원가 Process·서비스 | 재산정 | 재산정 |
| 5 계약 | 4~7 | 8~12 |
| 6 계산 | 6~10 | 10~18 |
| 7 입금·출고 | 5~9 | 8~16 |
| 8 정산·반품·담보 | 6~12 | 12~24 |
| 9 PDF/회귀 | 4~7 | 6~12 |
| 10 통합/운영 | 4~8 | 8~16 |
| **기존 최소범위 합계** | **48~88** | **86~164** |
| **확정 1차 범위** | **단계0~1 실측 후 재산정** | **수입형 전체 Process 포함으로 재산정** |

기존 48~88 / 86~164시간은 Work가 '최소 수입원가'를 전제로 산정한 값이므로 더 이상 확정 1차 총시간으로 사용하지 않는다. 사용자 확정에 따라 수입대행·BL양수도의 계약 후 필요한 수입 Business Process까지 1차에 포함한다. 외부기관 자동연동은 후속일 수 있다. 단계0 Audit와 단계1 매입을 실제로 마감한 속도, 그리고 수입 Process의 화면/DB 범위를 확정한 뒤 총시간을 다시 산정한다.

기존 일수 환산도 최소범위 기준이므로 참고치로만 보존한다. 완료일 약속으로 사용하지 않는다. 단계0~1을 끝낸 실제 속도로 추정치를 다시 조정한다. 한 단계가 크면 2~4시간 분량의 작은 Slice로 나누고 중앙 실행 결과를 다음 Slice의 입력으로 삼는다.

## 14. 위험·확인 필요사항과 결정목록

| 우선순위 | 위험/확인 필요 | 다음 행동 |
|---|---|---|
| 최우선 | DEV local DB와 central DB 혼동 | 동일 engine identity부터 확인, Migration 금지 상태 유지 |
| 최우선 | 현재 main ≠ SERVER 실제 배포 ≠ DEV 미커밋 | 세 상태의 SHA/status/diff를 분리 기록 |
| 높음 | Audit가 전체 완료로 오인 | 중앙Schema/API/event/GUI viewer/DB보호 마감 |
| 높음 | 확정 매입/LOT 사용 후 값 변경 | 일반매출 전 불변경계와 정정/반품 정책 확정 |
| 높음 | 수금/지급이 없이 Financing 출고통제 설계만 존재 | 공통 Receipt/Payment/Allocation 먼저 구현 |
| 높음 | 비용/이자/VAT/반올림 중복 또는 원단위 차이 | 항목별 policy 및 실제 expected 자료 승인 |
| 높음 | 수입원가 미확정/BL 혼적/원가 이자 중복 | 최소 원가확정 Slice와 날짜경계, LOT별 배분 |
| 높음 | GUI 저장/발송메시지를 실제 업무원장으로 오인 | FinSales Reference한계 명시, ERP DB 흐름으로 구현 |
| 높음 | 공동담보/차액의 단일잔액 덮어쓰기 | 발생/배분/해제 ledger 및 한도통제 |
| 중간 | 동시출고/중복입금/네트워크 재시도 | SQL Server 동시성·idempotency 검증 |
| 중간 | synchronous 조회 및 누적 데이터 | 페이지/서버검색/GUI 응답성 단계별 보완 |
| 중간 | 오래된 문서의 독립개발/경로/commit지시 | 본 문서 우선순위/문서판정표 이용 |
| 중간 | 실제 백업복구/WORK환경 현황 | 운영 마감 때 테스트DB 복구와 접근 후 확인 |

사용자 리뷰에서 확정/잔여 결정사항:

1. **확정:** 1차는 실제 Business Process를 처음부터 끝까지 수행할 수 있는 수준이며 Financing 3유형과 전체 Cycle을 모두 포함한다. Pilot 축소안은 사용하지 않는다.
2. 매입 할인·운송/창고/추가비용의 LOT 원가 포함/배분 방식은 실제 업무 Slice에서 확정한다.
3. **확정 원칙:** 기존 수치/반올림·올림·절사 정책은 준행하고 신규 항목은 통상의 상거래원칙+실제 계약자료에 따라 항목별로 확정한다. 기존 코드를 일괄 round/ceil 정책으로 바꾸지 않는다.
4. BOX/KG의 내부 계산정밀도·최종마감·실계근 선택, 0 BOX/0원 거래 허용정책.
5. 서비스 청구법인, 별도발행·수금·정산처리 및 Return Settlement 세무전표 규칙.
6. 담보 공동배분/차액허용범위/예외출고권한·사유정책.
7. 실제자료 BUD0106141 등 원본/expected 비교표 준비. 기존 Reference 결과를 무조건 정답으로 삼지 않음.
8. SERVER 배포·Schema와 DEV verifier diff, 실제 Scheduler `venv` 경로, WORK환경.

## 15. Chat / Work / VS Code / GitHub 역할과 비용절약

| 도구/장소 | 맡길 일 | 매번 남길 결과 |
|---|---|---|
| Chat | 전체 업무맥락, 규칙/범위 의사결정, 작은 수정 설계, 한 단계씩 실행 안내, 결과 리뷰 | 결정/다음 한 단계/금지사항 |
| Work | 대규모 두repo 조사, 여러 파일 연계 변경, 복잡한 테스트/회귀/문서작업 | 실제 파일+검증근거+반영/미반영 경계 |
| VS Code/DEV | 정확한 프로젝트/venv에서 실행, GUI/pytest/diff/status, 로그 제공 | command/cwd/interpreter/DB대상/결과 |
| SERVER | 중앙 Schema/API/실제 원장·권한·배포/백업 검증 | 서버identity·배포SHA·테스트결과 |
| GitHub | 승인한 코드/docs의 version 기준 | commit SHA/검증/미해결사항 |
| docs | 세션 간 Source of Truth/업무정책/인수인계 | 현재상태·증거·다음작업을 함께 갱신 |

한 줄 오류, 한 command 실행, 작은 UI 수정, 이미 범위가 명확한 DB read-only 확인 때문에 Work 전체조사를 다시 하지 않는다. Chat에서 로그를 읽고 다음 한 단계만 실행한다. 여러 파일/원장/Audit/권한/동시성까지 바뀌는 Slice만 Work에 맡긴다. 요청에 목표/기준SHA/관련파일/완료조건/금지작업을 넣고 작은 로그/차이만 전달한다.

새 세션 인수인계 최소값: 기준 SHA, DEV clean/dirty 및 관련 diff, SERVER배포SHA, 실제engine identity, 완료단계와 테스트 증거, 사용자 결정, 다음 한 작업, 금지사항. 토큰/암호/DB URL은 전달하지 않는다. 세션마다 인프라·Master를 다시 설계하거나 지난 기준서 전량 재작성하지 않는다.

## 16. 이번 변경파일과 DEV 반영 방법

산출물은 다음 두 신규 문서뿐이다.

- `docs/12_MXMN_ERP_MASTER_BASELINE_AND_ROADMAP_20261002.md`
- `docs/13_MXMN_ERP_EXECUTIVE_PROJECT_GUIDE_20261002.md`

Repo는 인증된 읽기 경로로 조사했고 별도 git checkout/branch 조작 없이 고정 SHA 자료를 확보했다. 기존 원격 소스/문서와 DB는 변경하지 않았다. 조사용 사본은 반영 파일이 아니다. 파일번호12/13의 기존 문서를 덮어쓰지 않는다.

반영 순서:

1. 현재 Chat에 두 Markdown을 첨부하고 업무규칙/범위/검증상태를 리뷰한다.
2. 수정·최종승인 후 DEV의 `C:\projects\MixNMenu\docs`에 전체 파일명 그대로 복사한다. 승인상태 문구를 승인일/기준SHA와 함께 갱신한다.
3. VS Code에서 두 신규파일 전체를 열어 검토하고 `git status --short`로 상태를 확인한다. 신규 미추적 파일은 일반 `git diff`에 내용이 나오지 않으므로 파일 자체를 읽는다.
4. 이미 있던 verifier 수정 등은 `git diff -- dev_verify_purchase_audit_schema.py`로 따로 검토한다. `git add .`로 다른 미승인 변경을 섞지 않는다.
5. 문서만 바뀌면 파일명/내용/링크 확인이 기본 검증이다. 코드 수정도 함께 포함한다면 공용 venv의 pytest와 해당 중앙 검증을 수행한다.
6. 정상 Git 환경에서 사용자가 승인한 파일만 선택하여 commit/push한다. 이번 Work에서는 실행하지 않았다.
7. GitHub main의 반영 SHA를 확인하고 Master를 확정 Source of Truth로 취급한다.
8. 첫 실제 개발은 단계0 Audit 중앙검증/마감, 그 다음 단계1 매입 최종마감이다. 즉시 Financing 신규개발로 넘어가지 않는다.

## 17. 조사 근거 위치

현재 코드 근거는 고정 SHA의 repo 파일 경로다. [ERP 고정 트리](https://github.com/mixbiz1/MixNMenu/tree/8cee784821934356dcdbe23f6bcd96612470c89c), [FinSales 고정 트리](https://github.com/mixbiz1/MXMN_FinSales/tree/2ed3bd33748f01d1ae558d3f33f672956037abc3)에서 아래를 확인한다.

- ERP `models.py`, `main.py`, `purchase_service.py`, `trade_common.py`: 모델/권한/원장/매입 materialize·dematerialize/API.
- `audit_service.py`, `db_audit_history_migrate.py`, `dev_verify_purchase_audit_schema.py`: 모델/JSON/DDL/현재 COLLATE 문자열비교.
- `views/purchase_reg.py`, `lot_reg.py`, `opening_inventory_reg.py`, `warehouse_reg.py`: 실제 GUI 흐름과 이력 viewer 부재.
- `permissions.py`, `api_client.py`, `api_config.py`, `database.py`, 사용자/권한GUI: 인증과 API/직접SQL 대상 분리.
- 각 `db_*_migrate.py`: 현재 코드와 과거 Schema의 차이, import side effect/실행위험. 실행하지 않고 내용으로 조사.
- tests 5개: 실제 assertion/fixture와 SQLite·offscreen 범위.
- FinSales `mxmn_finsales_app.py`의 `calculate_single`, `save_custom_changes`, `send_shipping_notice_to_manager`, Simulation/PDF 및 계약조건 저장: 계산과 실제 저장/발송 경계.
- FinSales `main.py`, `models.py`, `database.py`, auth migration/start cmd, 이전 GUI/test client/빈 scaffold: API/auth/default seed 및 참조환경.

이하는 조회한 commit 전수 인덱스다. 제목은 당시 작성자의 설명이며 그 자체로 업무완료 판정은 아니다. 앞 절들의 판정은 실제 변경파일/현재코드와 대조했다.


### MixNMenu commit 전수 인덱스

| UTC 날짜 | Commit | 변경파일 수 | 제목 |
|---|---|---:|---|
| 2026-09-02T04:52:41Z | [2b01f54](https://github.com/mixbiz1/MixNMenu/commit/2b01f546c6c40909ae0c618f7ddab0043bc82979) | 7 | Chore: Phase 1-B 개발환경 표준화 - .gitignore 적용 및 requirements.txt 고정 |
| 2026-09-02T04:55:19Z | [bbeda35](https://github.com/mixbiz1/MixNMenu/commit/bbeda359701479feedbf089920b91ba8a5f497e9) | 1 | Fix: .gitignore 파일 내용 최종 업데이트 |
| 2026-09-07T09:04:37Z | [b713f24](https://github.com/mixbiz1/MixNMenu/commit/b713f244a4c382be679524e9eb924a5a476a181b) | 17 | 우리회사정보 입력창까지 만듬 |
| 2026-09-09T11:58:44Z | [5fc6091](https://github.com/mixbiz1/MixNMenu/commit/5fc609107332a5a854b67124b63a797d6b9771f0) | 10 | 대쉬보드 사용 |
| 2026-09-09T23:14:39Z | [7a10caa](https://github.com/mixbiz1/MixNMenu/commit/7a10caa56041f475590242f1a29547c4fd7185c7) | 3 | 대시보드에 계약판매추가 |
| 2026-09-10T07:40:50Z | [52e2c44](https://github.com/mixbiz1/MixNMenu/commit/52e2c44d18344917af80deb5a778bdd1f746d8d9) | 6 | company_reg.py 색과 닫기버튼 엔터버튼입력시 반응 수정 |
| 2026-09-10T10:25:14Z | [93cc0d6](https://github.com/mixbiz1/MixNMenu/commit/93cc0d6a44395b7be077e41871511422673aee9c) | 24 | 서버접속-메인창의 대시보드 자동팝업-업체등록창오류수정 |
| 2026-09-10T12:46:33Z | [8b7153b](https://github.com/mixbiz1/MixNMenu/commit/8b7153b85b8e7d004ec63b8ccd59a5b121c9b168) | 29 | 누락된 화일올리기 |
| 2026-09-10T12:49:45Z | [40d9764](https://github.com/mixbiz1/MixNMenu/commit/40d9764121865dc8f3c7ebb6e0f09078acab73a2) | 2 | 불필요한 화일 폴더 정리 |
| 2026-09-12T03:22:07Z | [2432e49](https://github.com/mixbiz1/MixNMenu/commit/2432e4940f6e1d53fbbf6f1a02b6222e813c8713) | 2 | 대쉬보드상의 바로가기 추가/조정 |
| 2026-09-15T01:49:56Z | [bafc85e](https://github.com/mixbiz1/MixNMenu/commit/bafc85e394035fb21225e137d1ab651f96d7116b) | 10 | docs: establish MXMN project baseline |
| 2026-09-15T03:37:03Z | [a5fae53](https://github.com/mixbiz1/MixNMenu/commit/a5fae536a52d996a6c95383e8eab3f619d844774) | 7 | feat: establish multi-company foundation |
| 2026-09-15T06:00:43Z | [b2b913d](https://github.com/mixbiz1/MixNMenu/commit/b2b913d5c6d8c0df71f78f726551354c835fd1ba) | 3 | feat: add runtime company switching |
| 2026-09-15T13:31:45Z | [24ad515](https://github.com/mixbiz1/MixNMenu/commit/24ad515780a7828363c28f6a9c0ccf4fbf9b1123) | 9 | feat: complete account management V2.1 and stabilize DB/API |
| 2026-09-15T13:52:05Z | [56d1ae1](https://github.com/mixbiz1/MixNMenu/commit/56d1ae1ada8a9bcb3686d5a091c620ab2bdc4807) | 1 | current_status.md 생성 |
| 2026-09-16T01:47:41Z | [51d1e84](https://github.com/mixbiz1/MixNMenu/commit/51d1e8456e1e0d38551f6a0f17fcb2d832674fd2) | 2 | fix: improve account checkbox visibility |
| 2026-09-16T02:09:43Z | [11ff323](https://github.com/mixbiz1/MixNMenu/commit/11ff323d5282a5b3e3a3c345b6e5f3bf7e880e53) | 2 | fix: allow duplicate business numbers and set account defaults |
| 2026-09-16T02:29:10Z | [102258f](https://github.com/mixbiz1/MixNMenu/commit/102258f3247d1710ce18b0857cd618b31e517899) | 6 | feat: add common code management vertical slice |
| 2026-09-16T03:01:19Z | [0dcea34](https://github.com/mixbiz1/MixNMenu/commit/0dcea340620d6182bf95293a04f7affa985a8fe8) | 4 | feat: refine common code registration UX |
| 2026-09-16T03:26:54Z | [d9e34bf](https://github.com/mixbiz1/MixNMenu/commit/d9e34bf95c6868a6792a6672792b1a81da9dab22) | 1 | fix: react to common code sorting and add search |
| 2026-09-16T03:37:16Z | [f8390c8](https://github.com/mixbiz1/MixNMenu/commit/f8390c82779d9c3893f10170cf3ca52faa3c1009) | 2 | feat: add product common code management |
| 2026-09-16T04:09:11Z | [001d175](https://github.com/mixbiz1/MixNMenu/commit/001d175feacc96fb5ea701d9b704ee109f5e16db) | 4 | feat: manage product code groups and standardize refresh |
| 2026-09-16T04:26:19Z | [1e282c3](https://github.com/mixbiz1/MixNMenu/commit/1e282c3e978c06b41a3c71554ca8fdd8029140dc) | 1 | fix: keep product code category during search |
| 2026-09-16T04:37:39Z | [b68732d](https://github.com/mixbiz1/MixNMenu/commit/b68732d323c1cd148695d5334feac8979fb569d7) | 3 | fix: unify code search flow and raise active windows |
| 2026-09-16T04:43:43Z | [811cae7](https://github.com/mixbiz1/MixNMenu/commit/811cae7775dbc719f231d2335fe6a72b243856ef) | 1 | docs: update current status for product master handoff |
| 2026-09-16T06:08:46Z | [2dada7a](https://github.com/mixbiz1/MixNMenu/commit/2dada7abb05821582fe388bbb8643e7eaf267fd7) | 5 | feat: add hierarchical product master vertical slice |
| 2026-09-16T06:30:16Z | [19cdf17](https://github.com/mixbiz1/MixNMenu/commit/19cdf173094fc3e96914dc4877f3caf11a508bce) | 2 | fix: move product entry to code management menus |
| 2026-09-16T06:41:19Z | [115ee13](https://github.com/mixbiz1/MixNMenu/commit/115ee13662aaf52de39647bd821958dfc22ca352) | 1 | fix: disambiguate product attribute query joins |
| 2026-09-16T06:52:48Z | [ccf7dfa](https://github.com/mixbiz1/MixNMenu/commit/ccf7dfaea5f8c655393fb7c6dec7cc4d18950d4b) | 1 | fix: migrate legacy product columns idempotently |
| 2026-09-16T08:10:02Z | [419453f](https://github.com/mixbiz1/MixNMenu/commit/419453fa56c4a75b47c07fb24801ed26342e6292) | 1 | feat: align product entry with meat business workflow |
| 2026-09-16T08:40:37Z | [221e060](https://github.com/mixbiz1/MixNMenu/commit/221e060f13e27973742be5883925d7c231787b0c) | 3 | feat: refine product tree workflow and command feedback |
| 2026-09-16T09:06:11Z | [3cd8bac](https://github.com/mixbiz1/MixNMenu/commit/3cd8bacfa06d9bc67b5cbc81a899efe50f214d77) | 1 | fix: show first product and live-compose product names |
| 2026-09-16T09:20:05Z | [2981d12](https://github.com/mixbiz1/MixNMenu/commit/2981d12c921ef266a82862ae2564d07190f09425) | 1 | fix: improve selected-row text contrast |
| 2026-09-16T09:20:26Z | [b17c69f](https://github.com/mixbiz1/MixNMenu/commit/b17c69f59a35d677465b58aca5cb5e615ea75777) | 1 | fix: apply selected-row contrast consistently |
| 2026-09-16T09:20:33Z | [740ff65](https://github.com/mixbiz1/MixNMenu/commit/740ff6584d804b746a857344474e3fcbc2956e7b) | 1 | fix: apply selected-row contrast consistently |
| 2026-09-16T09:38:50Z | [1475be0](https://github.com/mixbiz1/MixNMenu/commit/1475be003c4934f8d9dafb219179aabc6935d98b) | 1 | perf: show data-entry windows before initial loading |
| 2026-09-16T09:38:59Z | [3da4a3c](https://github.com/mixbiz1/MixNMenu/commit/3da4a3c735840e9d381d7a32fcef9927540b85b4) | 1 | perf: reduce initial data-entry window delay |
| 2026-09-16T09:39:09Z | [86144e6](https://github.com/mixbiz1/MixNMenu/commit/86144e6d9af8dfb3dd4b9fe605e04f4d8cbc3292) | 1 | perf: reduce initial data-entry window delay |
| 2026-09-16T09:39:18Z | [5a4280c](https://github.com/mixbiz1/MixNMenu/commit/5a4280c521de652f9039b5f6288ca2f64da7d10f) | 1 | perf: reduce initial data-entry window delay |
| 2026-09-16T09:54:11Z | [a9943c6](https://github.com/mixbiz1/MixNMenu/commit/a9943c6816a95ffe5835f347bc9147af4a19c95e) | 1 | ux: show lookup progress and prevent duplicate requests |
| 2026-09-16T09:54:24Z | [2c85e4c](https://github.com/mixbiz1/MixNMenu/commit/2c85e4c6ba7f7e8ee31233865567ec00710f82a7) | 1 | ux: show lookup progress and prevent duplicate requests |
| 2026-09-16T09:54:36Z | [00fa1ae](https://github.com/mixbiz1/MixNMenu/commit/00fa1aea4f0bee06b1ecc4506c86e46b206f6087) | 1 | ux: show lookup progress and prevent duplicate requests |
| 2026-09-16T09:54:49Z | [38f78a4](https://github.com/mixbiz1/MixNMenu/commit/38f78a48b53a077327740cd41b922f1102ef494a) | 1 | ux: show lookup progress and prevent duplicate requests |
| 2026-09-16T09:55:01Z | [4433032](https://github.com/mixbiz1/MixNMenu/commit/443303206694409baeda32229dabd4292a154b9b) | 1 | docs: record responsive data-loading standard |
| 2026-09-16T09:59:35Z | [caadea8](https://github.com/mixbiz1/MixNMenu/commit/caadea8737f8f3a8d8c70c2d076954cd86610a17) | 1 | perf: batch product attribute loading |
| 2026-09-16T09:59:47Z | [a0e17cb](https://github.com/mixbiz1/MixNMenu/commit/a0e17cb2aafb51b230519b533f892ebf056a914d) | 1 | fix: show saved product part on selection |
| 2026-09-16T10:00:45Z | [087365c](https://github.com/mixbiz1/MixNMenu/commit/087365c3a19af983c726061392b5ad93f8545c2f) | 1 | docs: close product master vertical slice |
| 2026-09-16T10:45:41Z | [bd0cfa2](https://github.com/mixbiz1/MixNMenu/commit/bd0cfa2b250d14b64cd4bf3793bd93a08d13dbbb) | 1 | feat: add human-friendly code selector sorting |
| 2026-09-16T10:52:23Z | [8dffc87](https://github.com/mixbiz1/MixNMenu/commit/8dffc87fe00c6a9b72de0cf049ea0b5b66488f4a) | 1 | docs: finalize product master and hand off warehouse work |
| 2026-09-17T00:33:42Z | [e1b2879](https://github.com/mixbiz1/MixNMenu/commit/e1b2879c2a700d30b7824f257734669617802ba6) | 9 | feat: add warehouse master vertical slice |
| 2026-09-17T01:05:21Z | [bdb0984](https://github.com/mixbiz1/MixNMenu/commit/bdb0984c1d0e4ff30051397f8a63c215b0750614) | 7 | feat: make warehouse charges configurable |
| 2026-09-17T01:40:33Z | [718865a](https://github.com/mixbiz1/MixNMenu/commit/718865af8edba65db414c98bed0f94a8d8979d6f) | 6 | fix: refine warehouse form workflow |
| 2026-09-17T01:56:48Z | [dbec30f](https://github.com/mixbiz1/MixNMenu/commit/dbec30f66e5e2fee862a1e2da89ec790396a90ad) | 3 | fix: set handling charge per box |
| 2026-09-17T02:00:23Z | [6fe06fd](https://github.com/mixbiz1/MixNMenu/commit/6fe06fda4693a06ca5799ce50d1bebe7005c437a) | 2 | fix: label warehouse web user id |
| 2026-09-17T02:34:10Z | [0cefa5e](https://github.com/mixbiz1/MixNMenu/commit/0cefa5ef197041f3b77fa5b447a25353b7c5c03e) | 2 | feat: copy warehouse id when opening site |
| 2026-09-17T02:52:47Z | [e210860](https://github.com/mixbiz1/MixNMenu/commit/e210860d14901c00572e508a9ef2480ad40e071a) | 7 | feat: add lot master vertical slice |
| 2026-09-17T05:02:01Z | [900fcf4](https://github.com/mixbiz1/MixNMenu/commit/900fcf40cb690698b46d18d3fbc4fc504629659a) | 5 | fix: derive lots from inventory transactions |
| 2026-09-17T05:22:12Z | [3f7687f](https://github.com/mixbiz1/MixNMenu/commit/3f7687f0e85e59959a7c6c9db3380f121c769550) | 5 | fix: enforce lot numeric precision rules |
| 2026-09-17T05:23:15Z | [f62b12d](https://github.com/mixbiz1/MixNMenu/commit/f62b12d4217afe228336a07d712b41f14cad5374) | 1 | docs: finalize lot and hand off opening data |
| 2026-09-17T05:40:36Z | [d9fe5b9](https://github.com/mixbiz1/MixNMenu/commit/d9fe5b934e44eb0d17d0fe39e72f83fbcb0a03a6) | 10 | feat: add opening data vertical slice |
| 2026-09-17T06:38:11Z | [d5aa4b6](https://github.com/mixbiz1/MixNMenu/commit/d5aa4b69683400393efbd00dbd873e68589d9ba0) | 9 | fix: refine opening data workflows |
| 2026-09-17T10:46:24Z | [51828ab](https://github.com/mixbiz1/MixNMenu/commit/51828ab3dd2972008ce0bf800d32025927422af8) | 7 | fix: clarify lot numbering and code menus |
| 2026-09-17T11:15:02Z | [7a1c38f](https://github.com/mixbiz1/MixNMenu/commit/7a1c38f2a0d7323f1a3f4b13427b0df458b54326) | 3 | fix: adapt opening inventory column widths |
| 2026-09-17T12:03:17Z | [7defaab](https://github.com/mixbiz1/MixNMenu/commit/7defaabfd562fde839f7eae74e055a4fe06fb557) | 5 | fix: automate lot expiry and enable sorting |
| 2026-09-17T12:13:35Z | [5f8a7eb](https://github.com/mixbiz1/MixNMenu/commit/5f8a7ebb00b0ecc18787da888d5b72463f956d37) | 11 | feat: standardize sorting across lookup lists |
| 2026-09-17T12:18:22Z | [ce16722](https://github.com/mixbiz1/MixNMenu/commit/ce16722d43df83f5ca7bb56c04831353583033aa) | 3 | docs: prioritize integrity over UI convenience |
| 2026-09-17T12:37:06Z | [3a69b23](https://github.com/mixbiz1/MixNMenu/commit/3a69b232eda3f20d32f0676ee1388791fc11fa19) | 5 | fix: backfill lot expiry and simplify code sorting |
| 2026-09-17T13:07:52Z | [b90c476](https://github.com/mixbiz1/MixNMenu/commit/b90c476bbcc1b3d67c42a9ff83d5abc9af46d018) | 6 | feat: add password and postcode system tools |
| 2026-09-17T15:55:12Z | [2fe4a4c](https://github.com/mixbiz1/MixNMenu/commit/2fe4a4c2c879de60b6d97eafe371ae3a0e842d4a) | 16 | feat: add hierarchical expense code master |
| 2026-09-18T01:02:00Z | [6fb6446](https://github.com/mixbiz1/MixNMenu/commit/6fb6446a001c49f43969e1a6a3066cbe3f47802a) | 10 | feat: seed standard profit and loss code tree |
| 2026-09-18T01:16:14Z | [3dbc8b0](https://github.com/mixbiz1/MixNMenu/commit/3dbc8b0aad2eecaf3868277642218ce1e2c5acbc) | 4 | fix: allow detailed expense subitems |
| 2026-09-18T01:36:16Z | [1c4a8a9](https://github.com/mixbiz1/MixNMenu/commit/1c4a8a930562ac00cad0bd41533f5fd96bb4566b) | 7 | feat: add user registration management |
| 2026-09-18T02:10:26Z | [961975e](https://github.com/mixbiz1/MixNMenu/commit/961975e0e8b43379a813593e2c1c56f59d0133b8) | 28 | feat: complete user company and menu permissions |
| 2026-09-18T02:28:39Z | [5b2b680](https://github.com/mixbiz1/MixNMenu/commit/5b2b680da4ffd603d3b42cd779f0ef010cc5383c) | 1 | fix: split SQL Server permission migration batches |
| 2026-09-18T02:29:46Z | [3d9c9e6](https://github.com/mixbiz1/MixNMenu/commit/3d9c9e6f2c502109059e0898751ded0eff45eb7a) | 1 | fix: recover partially applied permission migration |
| 2026-09-18T06:29:11Z | [81dd2e0](https://github.com/mixbiz1/MixNMenu/commit/81dd2e05449d07e8128b5b59c2649e00fb3789ef) | 10 | feat: add trade common foundation |
| 2026-09-18T06:57:06Z | [d715e16](https://github.com/mixbiz1/MixNMenu/commit/d715e1632a26fdcc5cf147e6b442c9e9089428a9) | 12 | feat: add general purchase vertical slice |
| 2026-09-18T07:37:00Z | [a265df4](https://github.com/mixbiz1/MixNMenu/commit/a265df419566502bf9da47479010d06004fbfa2c) | 11 | feat: align product purchase with inbound workflow |
| 2026-09-18T08:27:12Z | [a8313db](https://github.com/mixbiz1/MixNMenu/commit/a8313dbe9b7b93bc5344f11a03d7073f6377a96f) | 5 | feat: simplify product purchase entry workflow |
| 2026-09-18T10:16:41Z | [16bce19](https://github.com/mixbiz1/MixNMenu/commit/16bce19decf5ed8869a9205f2cb27e5dfd0bf710) | 11 | feat: refine product purchase entry layout |
| 2026-09-21T14:55:21Z | [95f6151](https://github.com/mixbiz1/MixNMenu/commit/95f6151c6d02a456b9ea205f5f058a454ed5dff2) | 1 | docs: add post-work handoff for 2026-09-21 |
| 2026-09-23T03:05:03Z | [2309095](https://github.com/mixbiz1/MixNMenu/commit/2309095e24488d4f3267c792413c909346ec03a8) | 1 | fix: split purchase migration schema batches |
| 2026-09-23T03:06:12Z | [44a5509](https://github.com/mixbiz1/MixNMenu/commit/44a5509da5a5dc9c9aa7389214e99989659c52c8) | 1 | docs/06_MXMN_MASTER_HANDOFF_20260923_FINAL.md 업데이트 |
| 2026-09-23T04:14:49Z | [07baabd](https://github.com/mixbiz1/MixNMenu/commit/07baabdc934d544e20085df87f69af6d17f4ac4b) | 1 | Merge origin/main with local handoff document update |
| 2026-09-24T13:44:51Z | [ecadf19](https://github.com/mixbiz1/MixNMenu/commit/ecadf190ce90216f1aaab891a2bb5fd9216a74f7) | 14 | chore: remove obsolete reference files |
| 2026-09-24T14:14:12Z | [1fe3617](https://github.com/mixbiz1/MixNMenu/commit/1fe3617c30eb65a134a9d10125933838f7029038) | 18 | refactor: centralize desktop API base URL |
| 2026-09-24T15:36:19Z | [ba2d01b](https://github.com/mixbiz1/MixNMenu/commit/ba2d01b97c579678dad95e9d270afc60c1cf01c5) | 1 | docs: add MXMN server handoff and Work guidelines |
| 2026-09-25T06:27:31Z | [9940730](https://github.com/mixbiz1/MixNMenu/commit/9940730d7061c71f1464e548b0c3f6f9476a90ad) | 1 | docs: complete MXMN three-PC server handoff |
| 2026-09-26T08:11:30Z | [937464f](https://github.com/mixbiz1/MixNMenu/commit/937464f7ec06e79c67b22212a080dc6427c70a13) | 1 | docs: add final MXMN server infrastructure baseline |
| 2026-09-29T07:44:19Z | [b637a42](https://github.com/mixbiz1/MixNMenu/commit/b637a42f72975f5969e77514c148c762f03260e7) | 1 | docs: add ERP Financing integration design v1 |
| 2026-09-29T10:27:22Z | [6fdb049](https://github.com/mixbiz1/MixNMenu/commit/6fdb0499b627bc69bcac367e26cc8b5eb505e197) | 1 | docs: add 2026-09-29 worklog and purchase handoff |
| 2026-09-29T10:32:12Z | [590a940](https://github.com/mixbiz1/MixNMenu/commit/590a940d30fae11b9dbc32ea9297c25388c7e17f) | 1 | docs: establish ERP-wide audit history standard |
| 2026-09-30T07:15:58Z | [ac3965f](https://github.com/mixbiz1/MixNMenu/commit/ac3965f1029d48bebc3f1d0a8fee649ba41d2f60) | 1 | feat: add common audit history helper foundation |
| 2026-09-30T07:16:20Z | [82c842f](https://github.com/mixbiz1/MixNMenu/commit/82c842f5d1ac0981400c1def7f48149e7a87908c) | 1 | feat: add audit history database migration |
| 2026-09-30T07:18:19Z | [fdaf2f6](https://github.com/mixbiz1/MixNMenu/commit/fdaf2f6ad44f5ffdfc002ba0bd45d69f92827d71) | 1 | feat: make audit event model self-contained |
| 2026-09-30T07:18:46Z | [168609d](https://github.com/mixbiz1/MixNMenu/commit/168609d4adb0ec6e27b6ea51c6dd7e66efb90811) | 1 | dev: add deterministic purchase audit integration patch |
| 2026-09-30T09:35:56Z | [8cee784](https://github.com/mixbiz1/MixNMenu/commit/8cee784821934356dcdbe23f6bcd96612470c89c) | 8 | feat: complete purchase audit history integration and tests |

### MXMN_FinSales commit 전수 인덱스

| UTC 날짜 | Commit | 변경파일 수 | 제목 |
|---|---|---:|---|
| 2026-09-19T06:24:35Z | [2c54f36](https://github.com/mixbiz1/MXMN_FinSales/commit/2c54f36fafb3bc9bbc9e0ef162dfe71544f6c0eb) | 7 | feat: initialize MXMN_FinSales standalone module |
| 2026-09-20T11:22:34Z | [64e3e59](https://github.com/mixbiz1/MXMN_FinSales/commit/64e3e5958e2024187cf6abb942ca37bc083926ad) | 37 | refactor: MXMN_FinSales 3-Tier 아키텍처 구조 전면 개편 및 마스터 설계 문서 최신화 (v1.31) |
| 2026-09-20T13:06:22Z | [0af1386](https://github.com/mixbiz1/MXMN_FinSales/commit/0af1386fd1bab4544f702aea53208a689c4b48a5) | 1 | .gitignore modified |
| 2026-09-26T05:13:39Z | [9f784f0](https://github.com/mixbiz1/MXMN_FinSales/commit/9f784f024f82c50838fa52a70d738155a850768d) | 2 | refactor: centralize FinSales API base URL |
| 2026-09-26T06:49:11Z | [9cb4cae](https://github.com/mixbiz1/MXMN_FinSales/commit/9cb4caed6453f39d2889a77bd2c6a7f7ddecda99) | 2 | docs: finalize FinSales C/S server setup |
| 2026-09-26T06:54:22Z | [817109c](https://github.com/mixbiz1/MXMN_FinSales/commit/817109ca46889cf578400a70047a9fb58af79684) | 1 | docs: add 2026-09-26 FinSales C/S setup handoff |
| 2026-09-26T08:14:08Z | [fa4b1e1](https://github.com/mixbiz1/MXMN_FinSales/commit/fa4b1e10507eb37d9d06fe4c1aae4179eb9c49b2) | 1 | docs: add final FinSales server infrastructure baseline |
| 2026-09-28T08:13:10Z | [5c91552](https://github.com/mixbiz1/MXMN_FinSales/commit/5c91552e9627740bcacb1b2c3e22bf3c551f9d7e) | 4 | feat: add FinSales authentication and user lot access |
| 2026-09-28T08:48:33Z | [fd13596](https://github.com/mixbiz1/MXMN_FinSales/commit/fd135964625395f38e3fd5df7802d70ccbadb5c5) | 1 | fix: use shared .venv for FinSales API startup |
| 2026-09-28T08:55:42Z | [60f89bf](https://github.com/mixbiz1/MXMN_FinSales/commit/60f89bff2020cce37273c9e1a99a0a8690417051) | 1 | docs: add FinSales auth and C/S handoff |
| 2026-09-28T08:59:37Z | [2ed3bd3](https://github.com/mixbiz1/MXMN_FinSales/commit/2ed3bd33748f01d1ae558d3f33f672956037abc3) | 1 | fix: use local SQL TCP endpoint for FinSales server |

### 검토 파일 인덱스

각 파일은 위 고정 SHA에서 확보한 사본이다. 파일번호·내용을 직접 검토할 때 사용한다.

| Repo | 파일 | SHA-256 앞 12자리 |
|---|---|---|
| MixNMenu | `README.txt` | 976ced6019d8 |
| MixNMenu | `api_client.py` | 3afa1d2d6a65 |
| MixNMenu | `api_config.py` | a1b570100aac |
| MixNMenu | `app.py` | ab60c75bc684 |
| MixNMenu | `app_context.py` | a45d518469ce |
| MixNMenu | `audit_service.py` | b8eab36e07fe |
| MixNMenu | `database.py` | 1e0b922d4be1 |
| MixNMenu | `db_account_migrate.py` | 81b3ac138cd6 |
| MixNMenu | `db_account_v21_migrate.py` | 7c2bd3e75f56 |
| MixNMenu | `db_account_v2_migrate.py` | ba2329a60528 |
| MixNMenu | `db_audit_history_migrate.py` | e057f6370500 |
| MixNMenu | `db_common_code_migrate.py` | cabb48565ac7 |
| MixNMenu | `db_company_inspect.py` | 2131206ea09d |
| MixNMenu | `db_expense_code_migrate.py` | 7bc541d85330 |
| MixNMenu | `db_inspect.py` | 4564e5a9f664 |
| MixNMenu | `db_inspect_result.txt` | 647ea10671d6 |
| MixNMenu | `db_lot_migrate.py` | a54007692603 |
| MixNMenu | `db_opening_data_migrate.py` | cd466192d70b |
| MixNMenu | `db_product_migrate.py` | c6c652a0141e |
| MixNMenu | `db_purchase_migrate.py` | 23768afc9af2 |
| MixNMenu | `db_test.py` | 0a26b2166e61 |
| MixNMenu | `db_trade_common_migrate.py` | 67fa4334a0b6 |
| MixNMenu | `db_user_permission_migrate.py` | 4bda75d6f5ff |
| MixNMenu | `db_warehouse_migrate.py` | 29d761241f5a |
| MixNMenu | `dev_apply_purchase_audit.py` | 6bcd6e7b0766 |
| MixNMenu | `dev_verify_purchase_audit_schema.py` | b0977bd93efe |
| MixNMenu | `docs/00_PROJECT_BASELINE.md` | 430d8fc3d8ee |
| MixNMenu | `docs/01_PROJECT_SPEC.md` | 2c07f30c254b |
| MixNMenu | `docs/02_DOMAIN_MODEL.md` | 19564399d374 |
| MixNMenu | `docs/03_DATABASE_DESIGN.md` | 674e70ef3689 |
| MixNMenu | `docs/04_CURRENT_STATUS.md` | 9ef24510f481 |
| MixNMenu | `docs/05_FOLDER_STRUCTURE.md` | 97585cf6d87f |
| MixNMenu | `docs/06_MXMN_MASTER_HANDOFF_20260923_FINAL.md` | 2c6686655c08 |
| MixNMenu | `docs/07_MXMN_SERVER_HANDOFF_20260925.md` | 5515d80e90b4 |
| MixNMenu | `docs/07_MXMN_SERVER_INFRASTRUCTURE_BASELINE_20260926.md` | c6aff7fa0406 |
| MixNMenu | `docs/08_MXMN_ERP_FINANCING_INTEGRATION_DESIGN_V1_20260929.md` | 2c90faa89185 |
| MixNMenu | `docs/09_MXMN_ERP_WORKLOG_HANDOFF_20260929.md` | e9568f03a067 |
| MixNMenu | `docs/10_DEVELOPMENT_ROADMAP.md` | 2af54aa6e91b |
| MixNMenu | `docs/10_MXMN_ERP_AUDIT_HISTORY_STANDARD_20260929.md` | 8b9c445f0d99 |
| MixNMenu | `docs/11_CODEBASE_GAP_ANALYSIS.md` | 45bc1aa4d467 |
| MixNMenu | `docs/11_MXMN_PURCHASE_AUDIT_WORK_HANDOFF_20260930.md` | f017232f157b |
| MixNMenu | `docs/12_MIGRATION_PLAN.md` | 79b49684d641 |
| MixNMenu | `docs/13_POST_WORK_HANDOFF_20260921.md` | c28d201bd7bb |
| MixNMenu | `docs/AI_SYSTEM_PROMPT.md` | f6c1f7511c1b |
| MixNMenu | `expense_code_defaults.py` | 9ec5a34afa69 |
| MixNMenu | `main.py` | 959b9070f833 |
| MixNMenu | `models.py` | 42c48738cef2 |
| MixNMenu | `permissions.py` | b441189a30dc |
| MixNMenu | `purchase_service.py` | ba7d6685401d |
| MixNMenu | `pytest.ini` | 4bd353223330 |
| MixNMenu | `requirements.txt` | cd9b4f591ea9 |
| MixNMenu | `tests/test_permissions.py` | 5d893e0b4390 |
| MixNMenu | `tests/test_purchase.py` | a597e98a6048 |
| MixNMenu | `tests/test_purchase_audit.py` | 8a7a9704f483 |
| MixNMenu | `tests/test_purchase_audit_gui.py` | f745ab8625c3 |
| MixNMenu | `tests/test_trade_common.py` | fb0738a8a03a |
| MixNMenu | `trade_common.py` | 7199280a91fd |
| MixNMenu | `views/account_reg.py` | d989e51c0d39 |
| MixNMenu | `views/common_code_reg.py` | dcea9bef913d |
| MixNMenu | `views/company_reg.py` | 0c3cbdcc4f6b |
| MixNMenu | `views/expense_code_reg.py` | 1e97cbcd009e |
| MixNMenu | `views/goods_common_code_reg.py` | 34e8d84d4f97 |
| MixNMenu | `views/lot_reg.py` | 879e079175df |
| MixNMenu | `views/main_dashboard.py` | b356a1442785 |
| MixNMenu | `views/main_view.py` | d32a0e23cfc3 |
| MixNMenu | `views/mxmn_main_window.py` | 8b8e231172c1 |
| MixNMenu | `views/opening_balance_reg.py` | f57fc1fe50c1 |
| MixNMenu | `views/opening_inventory_reg.py` | 5d3e7d4bcdcf |
| MixNMenu | `views/password_change.py` | d778dd3a319a |
| MixNMenu | `views/product_reg.py` | 1ee11b2fe886 |
| MixNMenu | `views/purchase_reg.py` | b9db28dffe4a |
| MixNMenu | `views/table_utils.py` | dea329fe136c |
| MixNMenu | `views/user_permission_reg.py` | c06313859dc8 |
| MixNMenu | `views/user_reg.py` | 85818800c551 |
| MixNMenu | `views/warehouse_reg.py` | ff4dc3f51150 |
| MixNMenu | `오늘 작업하면서 메모한것.txt` | bf98319795e3 |
| MXMN_FinSales | `api_config.py` | 4a4cd12b366c |
| MXMN_FinSales | `client.py` | 3b8c2ef635ea |
| MXMN_FinSales | `database.py` | 535b97a353c9 |
| MXMN_FinSales | `db_finsales_auth_migrate.py` | 6c9938ced293 |
| MXMN_FinSales | `docs/00_INTEGRATED_BASELINE_AND_STATUS.md` | 1b12b1176862 |
| MXMN_FinSales | `docs/01_MXMN_FINSALES_MODULE_SPEC.md` | a917cfae7d9e |
| MXMN_FinSales | `docs/02_BUSINESS_AND_CODING_GUIDELINES.md` | e452fbea0cae |
| MXMN_FinSales | `docs/03_WORK_LOG_20260926_FINSALES_CS_SETUP.md` | 21f50113b8f7 |
| MXMN_FinSales | `docs/08_MXMN_FINSALES_SERVER_INFRASTRUCTURE_BASELINE_20260926.md` | 89532f285f34 |
| MXMN_FinSales | `docs/09_MXMN_FINSALES_AUTH_CS_HANDOFF_20260928.md` | 139f019ab2d0 |
| MXMN_FinSales | `main.py` | ed46fc66dee3 |
| MXMN_FinSales | `models.py` | 3889bf54ce75 |
| MXMN_FinSales | `mxmn_finsales_app.py` | a4113d4c98f4 |
| MXMN_FinSales | `mxmn_finsales_app_20260919.py` | 832a7061f4ea |
| MXMN_FinSales | `start_finsales_api.cmd` | b6a87c860bac |

문서 변경 이력125건은 commit의 변경파일/patch와 현재문서를 대조했다. 모든 옛 코드 revision을 빌드했다는 뜻은 아니다. 확보 소스는 수정하지 않았으며 마지막 구문검사도 import/DB 접속 없이 수행했다.
