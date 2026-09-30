# MXMN 商品매입 Audit/History Work 인수인계 — 2026-09-30

## 상태와 작업 기준

코드 및 자동테스트 완료. 중앙 SQL Server Schema 조회, 서버 API 실행, 실제 사용자 GUI Cycle 검증은 미완료이므로 상품매입 최종 마감은 보류한다.

- Source of Truth: `mixbiz1/MixNMenu`, `work/purchase-audit-20260930`
- 작업 시작/종료 HEAD: `168609d4adb0ec6e27b6ea51c6dd7e66efb90811`
- 서버 작업폴더 clean 및 origin 작업브랜치와 동기화: 사용자 확인
- 지정 작업브랜치만 clone/수정. main checkout/merge, commit/push, Git history 변경 없음.
- Work의 변경은 아직 미커밋이며 서버에는 적용되지 않았다. git pull만으로 받을 수 없다.
- 기준: docs/08, 09, 10 및 기존 baseline, 개발원칙, roadmap, current status.

## 기존 구현 확인

공통 AuditEvent/helper 및 Migration은 이미 존재했다. 최신 commit은 `dev_apply_purchase_audit.py`를 추가했으나 main.py에는 호출이 없었다. 기존 deterministic patch를 적용한 뒤 부족한 부분을 보완했다. 모델은 models.py가 아닌 audit_service.py에 있으며 중복 모델을 만들지 않았다. 기존 Purchase Header Audit 필드는 유지했다.

## 변경 파일과 목적

| 파일 | 변경 |
|---|---|
| audit_service.py | 기존 SQL Server Migration과 일치하는 Unicode/NVARCHAR(MAX), DATETIME2/UTC default, 복합 인덱스. SQLite 테스트용 PK 타입 variant. 기존 helper와 동일 Session 방식 유지 |
| main.py | CREATE/UPDATE/CONFIRM/CANCEL/DELETE 연결, 저장값 기반 Snapshot, 파생자료 Snapshot, 실제 API source와 인증 사용자 기록, 오류 rollback, 취소 사유 검증, 수정 사유 선택 입력, 회사별 읽기 전용 history API |
| views/purchase_reg.py | 취소 사유 필수 입력 및 수정 사유 선택 입력만 추가. 기존 저장·수정 Transaction 및 화면 구성 유지 |
| tests/test_purchase_audit.py | 격리 DB에서 실제 API/ORM Cycle와 실패 rollback, 권한·검증·FK 차단, 모델 타입/인덱스 테스트 |
| tests/test_purchase_audit_gui.py | 오프스크린 화면 객체 및 취소 사유의 전달·공백/초과길이/대화상자 취소 차단 테스트 |
| dev_verify_purchase_audit_schema.py | 중앙 DB 읽기 전용 Schema 비교. 테이블·컬럼 타입·NULL·PK·IDENTITY·UTC default·인덱스 검사. DDL/DML/Migration 없음 |
| docs/04_CURRENT_STATUS.md | 최신 상태와 과거 설명의 적용범위 명시 |
| 이 문서 | 변경/검증/제약/중앙 실행 인수인계 |

## Action / Snapshot 규칙

- CREATE: before NULL, after 신규 DRAFT Header/Detail.
- POST finalize=True: CREATE(DRAFT) → CONFIRM(DRAFT → CONFIRMED), 같은 Transaction.
- UPDATE(DRAFT): 수정 직전 → 수정 완료 DRAFT.
- PUT finalize=True 최초 확정: UPDATE(DRAFT → 수정 DRAFT) → CONFIRM(수정 DRAFT → CONFIRMED).
- UPDATE(CONFIRMED): 기존 확정 원문/파생자료 → 재생성된 확정 원문/파생자료. 기존 재생성 방식 유지.
- 명시적 CONFIRM: DRAFT → CONFIRMED.
- CANCEL: CONFIRMED → CANCELLED. 공백 제외 1~1000자 사유 필수. DRAFT/이미 취소된 전표는 거부.
- DELETE: DRAFT만 물리삭제, before 전체 Snapshot, after NULL. Audit에 Purchase FK를 두지 않아 삭제 후에도 이력 보존.

Snapshot에는 Header Audit, 전표번호, Detail, 상품·창고·LOT 식별정보, 입고 Header/Detail, LOT 컬럼값, PURCHASE_PAYABLE 원거래를 포함한다. flush/refresh 및 관계 재조회로 변경 후 이전 LOT 관계가 남는 문제와 저장 전/후 숫자·시간 표현 차이를 줄였다. Decimal은 문자열로 보존한다.

공통 Event는 회사, 인증 사용자, UTC 생성일시, PURCHASE_GENERAL, PURCHASE PK, action, 실제 method/path, reason, before/after를 기록한다. UPDATE/CANCEL의 related_entity는 같은 원 Purchase PK이며, 파생자료의 기존/신규 PK는 Snapshot으로 비교한다. 별도 정정전표/역거래는 이번 범위에서 생성하지 않는다. 향후 후속 출고 도입 뒤 원거래 보존 및 역거래 연결로 확장해야 한다.

## API 변경

- PurchaseInput.audit_reason: 선택, 최대 1000자. 수정 GUI에서 선택 입력.
- 취소 요청: `POST /api/v1/companies/{comp_code}/purchases/{purchase_id}/cancel`, JSON `{"reason":"취소 사유"}`. 구버전 사유 없는 호출은 422. 클라이언트/API 함께 반영 필요.
- 이력 조회: `GET /api/v1/companies/{comp_code}/purchases/{purchase_id}/history`.
- 기존 회사 접근 및 PURCHASE_GENERAL read 권한 적용. 삭제된 DRAFT 이력도 조회 가능. Audit 수정/삭제 API는 없음.
- 반환 before_json/after_json은 JSON 문자열이며 event 순서대로 반환. 공통 History GUI는 후속 과제.

## DB / Migration

Work에서 중앙 DB 접근/변경 및 Migration 실행 없음. db_audit_history_migrate.py 변경 없음. 사용자 보고상 Migration은 중앙 DB에 이미 적용되어 있다. 모델을 기존 Migration에 맞췄으므로 추가 DDL이 필요하다고 판단할 근거는 없다. 실제 Schema 확인 전 일치 완료로 보고하지 않는다.

`dev_verify_purchase_audit_schema.py`는 DB_NAME이 mxmn_dev인지 확인하고 Schema만 조회한다. 불일치가 나오면 결과를 먼저 검토한다. Migration을 추측해 재실행하지 않는다.

## 자동검증 결과

- 기존 테스트 16개 + 신규 22개 = **38 passed, 1 warning in 2.10s**.
- 경고: 테스트 런타임 Starlette TestClient/httpx 사용의 deprecation. 기능 실패 아님.
- Python compile 및 git diff --check 통과.
- GUI 오프스크린 실제 PurchaseRegWindow 객체 생성 성공. HTTP/대화상자는 mock 처리.
- API는 실제 FastAPI middleware/endpoint, SQLAlchemy 모델, 격리 SQLite DB 사용. FK 활성화 및 ID 재사용 방지. 인증·회사·메뉴권한 경로 실행.
- 중앙 ODBC DB 대신 테스트 엔진만 대체하며 SQL Server 발번 함수만 테스트 대체. 업무 입력검증, materialize/dematerialize, 상태변경, Audit INSERT/commit/rollback은 실제 코드 실행.
- Audit INSERT 실패를 CREATE/UPDATE/CONFIRM/CANCEL/DELETE 각각 주입해 업무자료와 Audit 모두 rollback되는지 검증.
- 후속 다른 입고가 원 LOT를 참조하면 확정 UPDATE/CANCEL이 409로 거부되고 원 거래·미지급·이력이 유지됨.
- DB 저장된 Event 조회에서 사용자/회사/menu/source/time/reason/전후 Snapshot 확인. 중앙 DB 실제 기록 확인과 구별해야 한다.
- 런타임: Python 3.12, SQLAlchemy 2.1.1, FastAPI 0.142.1, Pydantic 2.13.5, httpx 0.28.1, PySide6 6.11.2. 서버 requirements의 일부 버전과 다르므로 서버 pytest 재확인 필요.

## Chat에서 이어갈 중앙 검증

사용자에게 명령은 한 단계씩 안내한다. 아래는 순서이며 한 번에 실행 요청하지 않는다.

1. 변경 diff를 최종 검토하고 지정 브랜치의 서버 파일에 반영하는 방법을 확정. Work는 commit/push를 하지 않으므로 서버 소스는 아직 이전 상태이다.
2. 반영 후 브랜치/변경 파일 확인, 전체 pytest 실행. 예상 38 passed.
3. 읽기 전용 Schema 검증 스크립트 실행. 일치 결과 확인 뒤 추가 Migration 필요 여부 판단.
4. 기존 운영 방식으로 API/GUI 변경 반영. 구버전 GUI는 취소 사유를 전송하지 않으므로 함께 갱신.
5. 테스트 자료로 신규 저장/확정 → 조회 → 수정(단가 등) → 취소 사유 입력 → 취소 Cycle. 기존 실제 purchase_id=1은 사용자 승인 없이 검증용으로 변경하지 않는다.
6. 동일 전표 이력에서 CREATE/CONFIRM/UPDATE/CANCEL, before/after 금액·LOT/입고/미지급 연결과 취소 후 빈 파생자료 확인.
7. DRAFT API Cycle로 수정/명시 확정/삭제 및 삭제 후 history 확인. GUI 저장은 즉시 확정하므로 DRAFT는 API 검증 대상.
8. 중앙 DB의 tb_audit_event 실제 기록 확인 및 권한/오류 결과 확인.
9. 사용자 확인까지 완료된 후 상품매입 마감. 다음 개발은 일반매출 Vertical Slice이며 Financing 설계 추가 확대 없음.

## 발견 문제 / 잔여 항목

이번에 해결: API Audit 미연결, finalize CONFIRM before 누락, 상태변경 전후 구분, 취소 사유 미지원, Snapshot 저장값/이전 관계 보정, 모델/Migration 타입·인덱스 차이, Audit 실패 rollback 검증 누락.

잔여: 중앙 Schema·SQL Server 고유 발번/잠금·실제 API/GUI·중앙 Event 기록 검증. 확정 원거래의 역거래 전환, 공통 History GUI, 다른 Master/Transaction Audit 연결은 후속 단계. append-only는 애플리케이션 경로 기준이며 DB 관리자 직접 SQL 방지용 trigger/DB 권한 재설계는 이번에 수행하지 않았다.

최종 마감이나 사용자 검증 완료로 표현하지 않는다. Git commit/push/main merge는 수행하지 않았다.
