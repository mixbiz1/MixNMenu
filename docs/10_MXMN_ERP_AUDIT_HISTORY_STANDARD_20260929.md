# MXMN ERP Audit / History Standard

**기준일:** 2026-09-29  
**Project:** MXMN ERP / MixNMenu  
**Status:** 전 메뉴 공통 필수 설계원칙  
**적용범위:** Master / Transaction / Financing / 권한 / 설정 / 코드 / 정산 / 취소·반품 등 전체

---

## 1. 목적

MXMN ERP는 상용 ERP 수준의 추적가능성(Traceability)을 기본기능으로 가진다.

사용자가 자료를 등록·수정·삭제·취소·확정·상태변경·Override할 때 현재 값만 남기지 않고, 추후 다음 질문에 답할 수 있어야 한다.

- 누가 변경했는가?
- 언제 변경했는가?
- 어떤 회사/메뉴/업무자료에서 변경했는가?
- 무엇을 변경했는가?
- 변경 전 값은 무엇인가?
- 변경 후 값은 무엇인가?
- 왜 변경했는가?
- 어떤 원거래/원문서와 연결된 변경인가?

이 원칙은 특정 Financing 기능에만 적용하지 않고 MXMN ERP 전체 공통기반으로 적용한다.

---

## 2. 핵심 원칙

### 2.1 수정/삭제 History는 선택기능이 아니다

모든 업무상 중요한 Master와 Transaction의 수정/삭제/취소/확정/상태변경은 History 대상이다.

### 2.2 물리삭제 최소화

업무자료는 가능한 물리적 DELETE보다 비활성화, 취소, 역거래, 반품 등 업무상태로 보존한다.

물리삭제가 허용되는 초기/미사용 Master 등에서도 삭제 전 Snapshot을 Audit History에 남긴다.

### 2.3 확정거래는 원문불변 우선

매입·매출·입고·출고·수금·지급·Financing 정산 등 확정된 Transaction은 원문을 직접 덮어쓰는 것보다 취소/반품/역거래/정정전표 방식으로 수정 이력을 보존한다.

### 2.4 Before / After Snapshot

단순히 `updated_at`만 기록하지 않는다. 중요한 변경은 최소한 변경 전 값과 변경 후 값을 비교할 수 있어야 한다.

### 2.5 사용자와 사유

Audit에는 로그인 사용자, 일시, 작업종류를 자동기록한다. Master Override, 확정자료 취소, 예외출고, 자동계산값 수정 등 중요한 예외작업에는 사유 입력을 필수화한다.

### 2.6 History 자체는 일반 사용자가 수정/삭제할 수 없다

Audit Log는 원거래와 분리된 append-only 성격으로 관리한다. 일반 CRUD 권한으로 Audit 원문을 변경할 수 없도록 한다.

---

## 3. 공통 Audit 데이터 모델 방향

전 ERP에서 재사용하는 공통 Audit Event 구조를 둔다.

예시 필드:

- audit_id: PK
- event_time: 발생일시
- user_id: 실행 사용자
- comp_code: 업무회사
- menu_code / module_code: 발생 메뉴/모듈
- entity_type: ACCOUNT / PRODUCT / PURCHASE / SALE / LOT / FIN_CONTRACT 등
- entity_id: 대상 PK
- document_no / business_key: 사람이 식별할 업무번호
- action: CREATE / UPDATE / DELETE / CONFIRM / CANCEL / STATUS_CHANGE / OVERRIDE / RETURN 등
- before_data: 변경 전 Snapshot(JSON 등)
- after_data: 변경 후 Snapshot
- reason: 변경/예외 사유
- parent_entity_type / parent_entity_id: 원거래 연결
- request/correlation 식별정보: 하나의 업무처리에서 여러 테이블 변경을 묶어 추적하기 위한 값

세부 DB 명칭과 타입은 실제 구현 전에 현재 models/API 구조와 충돌 여부를 확인하여 확정한다.

---

## 4. Header Audit 필드와 상세 History의 구분

기존 Transaction Header의 다음 필드는 계속 유용하다.

- created_by / created_at
- updated_by / updated_at
- confirmed_by / confirmed_at
- cancelled_by / cancelled_at

그러나 이것만으로는 과거 값이 무엇이었는지 알 수 없다.

따라서:

1. Header Audit Column = 현재 자료의 주요 상태와 마지막 행위자를 빠르게 확인
2. 공통 Audit History = 변경 전/후와 전체 변경과정을 추적

두 방식을 함께 사용한다.

---

## 5. 적용대상

### Master

- 회사
- 사용자/권한
- 거래처 및 회사별 거래관계
- 상품/상품분류/공통코드
- 창고/창고요율
- 경비코드/세금코드
- 기타 향후 Master

### Transaction

- 상품매입/경비매입
- 입고/LOT/재고조정
- 일반매출/출고
- 수금/지급/Allocation
- 매입반품/매출반품
- 취소/정정

### Financing

- 계약
- 계약조건 Version/Term
- 수수료/이자/창고료/가변비용 계산
- 입금요청
- 입금확인
- 부분출고
- 정산
- 보증금/담보
- Master Override 및 예외출고

---

## 6. 사용자 화면 원칙

각 업무화면에 무조건 복잡한 History Grid를 노출하지는 않는다.

공통적으로 선택된 자료에 대해 `변경이력/히스토리`를 조회할 수 있는 공통기능을 제공하는 방향으로 한다.

조회 예:

```text
2026-09-29 14:32  조일  UPDATE
매입단가: 6,800 → 6,849
사유: 최종 원가정산 반영
```

권한에 따라 History 조회범위를 제한할 수 있으나 Master 관리자는 전체 이력을 확인할 수 있어야 한다.

---

## 7. 구현 전략

기능별 화면마다 제각각 History 코드를 작성하지 않는다.

공통 Audit Service/Helper + 공통 Audit Table/API를 먼저 만들고, 이후 각 Vertical Slice의 CREATE/UPDATE/DELETE/CONFIRM/CANCEL/OVERRIDE 경로에서 호출한다.

적용순서:

1. 기존 Audit 관련 구현 조사
2. 공통 Audit Domain/DB Migration/API 설계
3. 상품매입에 첫 실제 적용
4. 사용자 검증
5. 이후 신규 일반매출/Financing에는 처음부터 적용
6. 기존 Master 메뉴는 순차적으로 공통 Audit에 연결
7. History 조회 공통 UI 추가

이렇게 하여 초기버전 개발속도를 과도하게 늦추지 않으면서도 앞으로 추가되는 모든 기능이 Audit 누락 없이 만들어지도록 한다.

---

## 8. 삭제/수정 정책

### 미사용/초기자료

업무연결이 전혀 없는 자료는 권한에 따라 삭제를 허용할 수 있다. 단 삭제 Snapshot은 History에 남긴다.

### 업무연결 자료

후속 Transaction이 존재하면 단순 DELETE를 거부한다.

### 확정 Transaction

직접 UPDATE/DELETE보다 취소/정정/반품/역거래를 사용하고 원거래 FK를 보존한다.

### 예외 Override

Master 권한자만 허용하며 원값/수정값/사유/사용자/일시를 반드시 보존한다.

---

## 9. 개발 완료 기준 추가

앞으로 MXMN의 기능은 화면이 정상 작동하고 데이터가 저장되는 것만으로 완료로 보지 않는다.

업무상 중요한 기능은 최소한 다음을 확인한다.

```text
권한
+ 입력검증
+ Transaction 무결성
+ PK/FK 관계
+ Audit/History
+ 오류처리
+ 사용자 실행검증
```

수정/삭제/취소/Override가 있는 기능은 History 검증까지 통과해야 해당 Vertical Slice를 마감한다.

---

## 10. 다음 작업에 대한 즉시 적용

다음 세션의 `상품매입 마감`에서 이 원칙을 첫 적용대상으로 삼는다.

상품매입의 현재 수정/취소 흐름을 검토하면서:

- 누가 수정/취소했는지
- 변경 전/후 값
- 수정/취소 사유가 필요한 지점
- Purchase → Inbound → LOT → PURCHASE_PAYABLE 파생자료 변경관계
- 후속 거래 존재 시 수정/취소 차단

을 함께 검증한다.

그 후 일반매출 Vertical Slice부터는 공통 Audit 기반을 기본 구성요소로 포함한다.

---

**이 문서는 MXMN ERP 전체 개발에 적용되는 공통 필수 원칙이다.**
