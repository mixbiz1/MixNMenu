# MXMN ERP Executive Project Guide — 2026-10-02

**2026-10-02 사용자 업무범위 승인 반영본. DEV/GitHub main 반영 후 공식 기준선으로 확정합니다.**  
상세 근거와 단계별 DB/API/GUI/Test/완료조건은 [Master Baseline](12_MXMN_ERP_MASTER_BASELINE_AND_ROADMAP_20261002.md)을 읽습니다.

## 1. 지금 어디까지 왔는가

MXMN은 육류 수입·도매유통과 Financing 계약판매를 한 ERP에서 관리하는 프로젝트입니다. 회사·거래처·상품·창고·LOT·기초자료·사용자/권한을 만들었고, 상품매입을 저장하면 입고·LOT·미지급 원장이 함께 만들어집니다. 상품매입 상세 변경이력도 GitHub main에 연결됐습니다.

**지금은 상품매입과 Audit를 중앙 서버에서 완전히 검증·마감하기 직전입니다.** 일반매출·출고·수금/지급·Financing 계약/계산/정산은 앞으로 연결할 업무입니다. 메뉴가 보인다고 그 기능이 완성된 것은 아닙니다.

| 영역 | 현재 상태 |
|---|---|
| 회사/거래처/상품/창고/LOT/기초재고·잔액 | 기본 GUI/API/모델 구현 |
| 로그인/회사 접근/menu 권한 | ERP 구현 |
| 상품매입→입고→LOT→미지급 | 구현, 중앙 실제 업무 검증/원가·수정경계 마감 필요 |
| 상품매입 상세 Audit 기록·조회 API | main에 구현, 사용자 DEV 보고 38 passed |
| Audit GUI 이력조회 | 미구현 |
| 중앙 Audit Schema/API/실제 이벤트 최종검증 | 확인 필요; 이번 Work 실접속 없음 |
| 일반매출/출고/수금·지급 | 미구현 |
| ERP Financing 계약/계산/정산 | 최신 설계는 있음, 실제 업무기능 미구현 |

## 2. ERP와 FinSales의 관계

앞으로 실제 신규개발은 **`mixbiz1/MixNMenu` 하나**에서 합니다. ERP가 업무 원본입니다. `mixbiz1/MXMN_FinSales`는 삭제하지 않고 계산방식·화면·PDF·과거 결과 비교에 사용합니다. 독립 신규개발은 중단한 상태입니다.

FinSales의 거래처·상품·창고·LOT를 ERP에 다시 복제하지 않습니다. ERP의 기존 Master와 매입/입고/LOT/매출/출고/수금 위에 계약조건·계산·정산 기능을 추가합니다.

FinSales에서 실제 구현된 것은 날짜별 계산/Simulation/PDF, LOT 조건 저장 API, admin/partner 인증과 중앙 접속입니다. 화면의 “출고조건 저장”과 “담당자 발송”은 안내 메시지이며 실제 출고원장 저장·외부 발송 완료가 아닙니다. 계약연장 이력·불변 계산 Snapshot·최종잔량 보정도 앞으로 ERP에서 만들어야 합니다. 참고 프로그램의 결과도 실제 계약자료와 대조해야 합니다.

## 3. 세 PC와 중앙 서버

| PC | 역할 | 지금 지킬 기준 |
|---|---|---|
| MXMN-SERVER | 중앙 SQL Server, ERP API :8000, FinSales API :8001, VPN/RDP, 자동기동 | 인프라를 다시 구성하지 않음. 실제 배포/DB 대상 확인 |
| MXMN-DEV | 현재 주 개발 PC, VS Code/GUI/테스트 | `C:\projects\MixNMenu`에서 실행 |
| MXMN-WORK | 업무/개발 PC, 현재 접근 어려움 | 접근 가능해지면 공용 환경/연결 확인 |

ERP GUI 업무 경로: **DEV/WORK GUI → SERVER API :8000 → 중앙 `mxmn_dev`**. FinSales는 기존 참고용 API :8001 / `mxmn_finsales_db`를 유지합니다.

현재 공용 Python은 `C:\projects\MixNMenu\venv\Scripts\python.exe`, VS Code 선택 기준은 `.\venv\Scripts\python.exe`입니다. SERVER/DEV는 사용자 현재 확인, WORK는 추후 확인합니다. FinSales 전용 venv를 새로 만들지 않습니다. 옛 문서의 `.venv` 표기는 현재 `venv` 확인과 구분하며 자동기동 설정을 임의 변경하지 않습니다.

## 4. 가장 중요한 DB 사고방지 원칙

GUI가 중앙 API를 쓰더라도 `database.py`를 직접 사용하는 개발 script는 그 PC 설정으로 SQL에 직접 연결합니다. DEV에서 확인된 대상은 `Ideapad-slim-3\SQLEXPRESS / mxmn_dev`였습니다. 중앙과 이름이 같은 **별도 로컬 DB**입니다.

따라서 `tb_audit_event missing` 한 줄만 보고 Migration을 실행하면 안 됩니다. SERVER에서는 Audit table이 있었고 이전 verifier는 NVARCHAR의 COLLATE 표기 때문에 차이를 보고했습니다. DEV의 COLLATE 최소 수정은 GitHub main에 반영됐는지 확인이 필요합니다.

앞으로의 순서:

1. 현재 PC·프로젝트·Python 확인.
2. script가 사용하는 동일 DB engine으로 서버instance/DB/머신을 읽기 전용 확인.
3. 중앙 `MXMN-SERVER\SQLEXPRESS / mxmn_dev` 대상임을 확인한 뒤 Schema verifier 실행.
4. 실제 구조차이가 확인될 때만 별도 Migration 작업으로 판단.

DB 이름만 같다고 같은 서버라고 보지 않습니다. 암호/토큰/전체 DB URL을 Chat에 붙이지 않습니다. 상세 읽기 전용 SQL과 Migration 안전절차는 Master 5절에 있습니다.

## 5. 현재 Source of Truth

| 무엇을 판단하는가 | 현재 기준 |
|---|---|
| 사용자 방향/환경 | 2026-10-02 지시: ERP 단일 중심, 현재 공용 venv, 이번 조사 변경금지 |
| 실제 ERP 구현 | GitHub main `8cee784821934356dcdbe23f6bcd96612470c89c` |
| FinSales 참고 구현 | main `2ed3bd33748f01d1ae558d3f33f672956037abc3` |
| Financing 업무설계 | ERP docs `08_MXMN_ERP_FINANCING_INTEGRATION_DESIGN_V1_20260929.md` |
| 공통 Audit 설계 | ERP docs `10_MXMN_ERP_AUDIT_HISTORY_STANDARD_20260929.md` |
| 인프라 | ERP 9/26 인프라 기준 + 현재 사용자 확인 |
| 이후 통합 진입문서 | 이번 Master/Guide를 리뷰·승인·main 반영한 뒤 확정 |

옛 04/11 인수인계의 “아직 main 미반영”은 현재 코드와 다릅니다. GitHub 코드 반영과 SERVER 배포·DB 검증은 별도입니다. 기존 12/13 문서가 있으므로 새 문서는 **전체 파일명 그대로** 추가하고 덮어쓰지 않습니다. 기존 문서는 역사로 보존합니다.

## 6. 지금까지의 핵심 History

| 시기 | 주요 변화 |
|---|---|
| 9월 초 | 프로젝트/GUI/회사/업무메뉴 기초 |
| 9/15~17 | 다중회사, 거래처, 상품, 창고/요율/비용, LOT, 기초재고·잔액 |
| 9/18 | 사용자/권한, 공통 거래·발번·기간, 상품매입→물류/미지급 연결 |
| 9/19~28 | FinSales 계산/UI/PDF, 중앙 C/S·인증·공용 실행환경 |
| 9/24~26 | ERP 중앙 서버/API/VPN/RDP/자동기동 구축 |
| 9/29 | Financing을 ERP로 통합하는 방향과 공통 Audit 표준 확정 |
| 9/30~10/02 | 매입 Audit main 적용, 사용자 DEV 38 passed, 중앙/로컬 DB 대상 차이 확인 |

두 repo의 main 전체 108개 commit과 현재 docs 24개/문서 변경125건을 조사했습니다. 현재 확보 Python61개 구문검사 오류0개이며, 이번 Work에서 실행 테스트/중앙 DB 검증을 재현한 것은 아닙니다. 자세한 전수 인덱스는 Master 부록에 있습니다.

## 7. 1차 완성본은 무엇인가

1차 완성본은 화면이 많이 만들어진 상태가 아니라 **현재 프로그램으로 실제 Business Process를 시작부터 종료까지 수행할 수 있는 상태**입니다.

일반유통은 **매입→입고/LOT→매출→출고/재고→미수/미지급→수금/지급→원장/이력**이 연결되어야 합니다.

Financing은 선택기능이 아니라 MXMN의 핵심기능입니다. **국내매입·수입대행·BL양수도 3개 유형의 전체 과정이 모두 1차 범위**입니다.

Financing의 확정 흐름:

**계약체결/계약서 작성 → 계약유형 분기 → (수입대행·BL양수도: LC 등 필요한 수입절차 → 수입/보세창고 입고 → 검역 → 수입원가 정산·확정 / 국내매입: 매입원가 확정) → 일일정산 → 입금요청/수금 → 출고승인 → 부분출고 반복 → 최종출고 → 최종정산 → 보증금·차액·미청구비용 확인 → 계약완료**

개발은 작은 Vertical Slice로 나누지만, 국내매입/Standard Sale만 Pilot하고 나머지를 2차로 미루는 방식은 사용하지 않습니다. 외부 전자세금계산서·창고지시·메일/SMS·기관연동의 완전자동화는 후속일 수 있지만, Financing 업무단계 자체와 근거/승인/원가/정산은 1차에서 ERP 안에 존재해야 합니다.

금액처리는 현재 확정된 기존 원칙을 유지합니다. 단가·가격·개별원가는 정수 원, 중량은 소수점 둘째 자리, BOX는 정수, 환율은 소수점 둘째 자리 등 기존 기준을 임의 변경하지 않습니다. 신규 Financing 금액항목은 통상의 상거래원칙과 실제 계약자료를 기준으로 항목별 반올림/올림/절사 정책을 확정하며 FinSales의 Python `round()`를 일괄 정답으로 복사하지 않습니다.

## 8. 남은 순서와 예상시간

개발의 큰 순서는 유지하되 Financing 업무의 시작점이 계약이라는 점을 명확히 합니다.

| 순서 | 작업 | 비고 |
|---|---|---|
| 0 | Audit 중앙 검증·이력 GUI 마감 | 다음 실제 작업 |
| 1 | 상품매입·LOT/재고 최종 마감 | 일반 거래 기반 확정 |
| 2 | 일반매출/출고/미수 | 공통 Sale/Outbound 기반 |
| 3 | 수금/지급·배분/잔액 | Financing 수금통제에도 재사용 |
| 4 | Financing 계약/계약서 공통기반 + 수입형 원가 Process | 계약이 시작점. 수입대행/BL양수도는 필요한 수입단계·보세입고·검역·원가확정, 국내매입은 매입원가에서 연결 |
| 5 | Financing 일일정산 Engine/Snapshot | 이자·비용·Term/Segment |
| 6 | 입금요청·확인/출고통제·부분출고 | 실제 수금과 재고 연결 |
| 7 | 최종정산·보증금·차액·반품/종료 | 계약완료 조건까지 |
| 8 | PDF/실제 업무자료 회귀검증 | FinSales/실제 원본과 비교 |
| 9 | 전체 통합/운영 검증 | 일반유통+Financing 실제 Cycle |

Work가 제시한 **AI 48~88시간 / 사용자 포함 86~164시간은 '최소 수입원가' 범위를 전제로 한 기존 참고치**입니다. 이제 수입대행·BL양수도의 필요한 수입 Business Process 전체가 1차로 확정되었으므로 총시간은 그대로 확정하지 않습니다. Audit와 매입 마감의 실제 속도를 측정하고 수입 Process의 DB/화면 범위를 구체화한 뒤 다시 산정합니다.

## 9. 지금 바로 할 일과 파일 반영

이번 결과를 받자마자 다음 기능을 개발하지 않습니다.

1. 2026-10-02 사용자 확정사항(1차 Business Process 완주, Financing 3유형 전체 포함, 계약부터 시작하는 흐름, 기존 금액정책 준행)을 반영한 두 문서를 DEV에 반영합니다.
2. 잔여 세부정책은 각 Vertical Slice에서 실제 계약/업무자료와 함께 확정하되, 이미 확정된 1차 범위를 다시 Pilot으로 축소하지 않습니다.
3. DEV `C:\projects\MixNMenu\docs`에 두 파일을 전체 이름 그대로 복사하고 Git 반영 SHA를 확정합니다.
4. VS Code에서 파일내용을 확인하고 터미널에서 `git status --short`를 확인합니다. 기존 verifier 변경은 `git diff -- dev_verify_purchase_audit_schema.py`로 따로 확인합니다.
5. 다른 미승인 변경을 섞지 않고 두 문서만 선택해 검토합니다. 문서만 바뀌면 내용/링크 확인, 코드 변경도 넣으면 해당 테스트가 필요합니다.
6. 정상 DEV Git 환경에서 사용자 승인 후 commit/push하고 main 반영 SHA를 확인합니다.
7. 다음 실제작업은 Audit 전체 중앙 검증/마감입니다. 이어 매입 최종마감→일반매출→Financing으로 진행합니다.

이번 Work는 코드·DB·Scheduler·venv·기존 문서를 변경하지 않았고 **Git commit/push/merge/branch 변경도 하지 않았습니다.** 사용자가 반영할 신규파일은 이 Guide와 Master 두 개입니다.

## 10. 개발 중 반복해서 볼 원칙

- 새 Master/원장을 FinSales에 만들지 않고 ERP 것을 참조합니다.
- 계약상대방과 실제 매입처/매출처/출고처/입금자는 다를 수 있습니다.
- 미입금 출고는 일반사용자에게 금지하고 관리자 예외는 이유·승인자를 기록합니다.
- 계약조건 변경/계산 Override는 과거 값을 덮어쓰지 않고 이력/Snapshot을 남깁니다.
- LOT 잔량0만으로 계약종료하지 않고 돈/보증금/미청구비용을 확인합니다.
- 확정거래 반품·정정은 원거래를 연결하며 삭제/음수수량 입력으로 대신하지 않습니다.
- DB 검사부터 실제 SQL 서버를 확인합니다. 오류 하나로 Migration을 실행하지 않습니다.
- 사용자 보고, 코드상 구현, 실제 중앙검증을 서로 구분합니다.

Chat은 업무결정·한 단계씩 실행/로그 확인에, Work는 여러 파일이 얽힌 조사·변경·검증에 사용합니다. 단순 오류 한 줄이나 한 command 실행 때문에 전체 Work 조사를 다시 하지 않습니다. VS Code는 실제 실행, GitHub는 승인 version, docs는 다음 세션의 기억입니다.
