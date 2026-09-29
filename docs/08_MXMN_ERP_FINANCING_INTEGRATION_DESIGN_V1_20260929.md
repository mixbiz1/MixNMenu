# MXMN ERP Financing Integration Design v1

**기준일:** 2026-09-29  
**프로젝트:** MXMN ERP / MixNMenu  
**Repository:** `mixbiz1/MixNMenu`  
**문서 성격:** Financing 계약판매 통합 설계 기준서  
**상태:** 사용자 업무규칙 확인 및 실제 FinSales/업무자료 분석을 반영한 v1

---

# 1. 목적

MXMN ERP는 일반 육류 유통과 Financing 계약판매를 하나의 ERP에서 처리한다.

Financing은 별도 재고시스템이 아니라 ERP의 거래처, 상품, 매입, 입고, LOT, 창고, 매출, 출고, 수금 구조 위에 계약/계산/정산 Layer를 추가하는 방식으로 구현한다.

기존 `MXMN_FinSales`는 삭제하거나 계속 독립 확장하지 않고 Reference Implementation 및 회귀검증용으로 보존한다.

본 문서 확정 이후 개발 우선순위는 다음과 같다.

1. 상품매입 현재 구현 재검증 및 마감
2. 일반매출 Vertical Slice
3. Financing Contract Vertical Slice
4. Financing 계산/입금/부분출고/정산
5. PDF 및 실제 자료 회귀검증
6. MXMN ERP 초기버전 통합검증

Financing의 모든 예외를 사전에 구현할 때까지 개발을 미루지 않는다. 다만 향후 구조를 뜯어고치기 어려운 핵심 Domain은 처음부터 확장 가능하게 설계한다.

---

# 2. 최상위 설계 원칙

## 2.1 ERP가 System of Record

ERP의 기존 Master와 Transaction을 원본으로 사용한다.

- Company
- Account / CompanyAccount
- Product
- Warehouse / WarehouseRate / WarehouseCharge
- Purchase / PurchaseItem
- Inbound / InboundItem
- LOT
- User / Permission

Financing이 별도의 상품/거래처/창고/LOT Master를 다시 만들지 않는다.

## 2.2 Financing ≠ Sale

Financing Contract는 계약관계를 관리하고, 실제 매입/매출/출고/입금은 ERP Transaction으로 연결한다.

## 2.3 Partner Single Master / Multiple Business Relationships / Separate Sub-ledgers

동일 사업자를 업무성격 때문에 여러 거래처 Master로 복제하는 방식을 기본으로 사용하지 않는다.

예: 제이케이미트코퍼레이션 하나의 Partner/Account 아래에 다음 업무관계를 구분한다.

- 일반유통 매입/매출
- Financing 계약
- Financing 정산잔액
- 보증금
- BL 양수도

원장 성격은 서로 분리한다.

## 2.4 계약상대방과 실제 거래상대방 분리

Financing Contract의 계약상대방 A와 실제 거래상대방은 다를 수 있다.

- 계약상대방: A
- 실제 매입처: A 또는 C/D 등
- 실제 매출처: A 또는 A가 지정한 B 등
- 실제 출고처: A/B 등
- 실제 입금자: A/B 등

A가 지정한 연관업체의 승인관계와 변경이력을 보존한다.

## 2.5 History / Snapshot 우선

과거 계약조건과 계산결과를 현재 Master 값으로 재계산하여 바꾸지 않는다.

- 계약조건 Version/Term
- 계산 Snapshot
- 관리자 Override 원값/수정값/사유
- 승인자/일시
- 내부 Comment
- 거래처 공개 Comment

을 보존한다.

---

# 3. Business Code 공통원칙

사람이 사용하는 업무코드는 가능하면 분류와 통계에 도움이 되는 논리적 규칙을 가진다.

예: 상품코드는 축종/부위/원산지/세부분류 등의 코드단위를 조합할 수 있다.

계약번호도 작성일자, 계약유형, 거래처 구분, 순번 등을 이용하여 사람이 보고 기본 성격을 파악할 수 있는 자동발번 규칙을 사용한다.

단, 통계와 그룹핑을 코드 문자열 해석에만 의존하지 않는다. 각 분류는 별도 FK/Column으로도 보존한다.

즉:

- Business Code: 사람의 식별/검색/분류 편의
- PK/FK 및 분류 Column: 시스템 무결성/통계/경영정보

내부 PK처럼 사람이 볼 필요가 없는 값에는 억지로 의미를 넣지 않는다.

---

# 4. Financing Contract와 LOT

한 계약에 여러 LOT를 연결할 수 있다.

- 한 계약에 여러 Container/BL 포함 가능
- 한 BL 안에 여러 품목이 혼적되면 품목별 원가/상품이 달라 여러 LOT 생성 가능
- LOT는 개별상품의 재고관리 단위
- 계약번호/Container/BL 등의 발생근거는 LOT 추적정보로 연결

Financing이 LOT를 새로 소유하지 않고 ERP LOT를 참조한다.

개념:

```text
Contract
 ├─ LOT A
 ├─ LOT B
 └─ LOT C
```

필요한 경우 향후 하나의 LOT가 복수 계약과 관계되는 예외도 수용 가능한 연결구조를 사용한다.

---

# 5. 계약유형

기본 계약유형:

1. 수입대행계약
2. BL양수도계약
3. 국내매입계약

세 유형의 Financing 계산 골격은 동일하지만 선행 업무단계와 원가확정 과정이 다르다.

주요 계약조건은 다음이다.

- 계약기간
- 수수료율
- 이자율
- 창고료 및 비용조건
- 중량산정방식
- 청구방식
- 정산방식
- 보증금/담보조건

계약별 유연성을 우선한다.

---

# 6. 수입원가와 Financing 이자

## 6.1 수입대행

원가확정 전:

`BL 대금지급일 → 최종 원가정산일 전일`

의 Financing 이자를 수입원가에 포함할 수 있다.

원가확정 후:

`최종 원가확정일(매입일) → 각 출고일`

의 계약판매 이자를 적용한다.

## 6.2 BL양수도

BL을 양수하고 BL대금이 지급된 날(통상 계약일)부터 최종 원가정산일 전일까지의 이자를 원가에 포함할 수 있다.

원가확정 후는 수입대행과 동일하다.

## 6.3 국내매입

매입일이 기본 이자 시작일이다.

## 6.4 통관일/매입일

일반적으로 통관일과 매입일은 동일한 값을 Default로 한다. Master 권한 사용자는 실제 업무사유에 따라 수정할 수 있어야 한다.

---

# 7. 이자 계산 Engine

기본 일수 계산:

`이자일수 = 종료일 - 시작일 + 1`

시작일과 종료일을 모두 포함한다.

이율은 고정 1차/2차 Column으로 제한하지 않고 Segment Row 방식으로 관리한다.

예:

```text
1~30일   7.0%
31~60일  7.5%
61~90일  8.0%
91일~    8.5%
```

각 구간의 실제 일수를 해당 약정이율로 계산하여 합산한다.

90일은 일반적인 Default 계약기간이며 계약별 변경 가능하다.

이자원금은 계약상 확정된 kg당 매입원가를 기본으로 한다. 수입의 경우 원물대와 부대비용 및 원가확정 전 Financing 비용 등을 포함하여 산정된 kg당 원가가 될 수 있다.

Financing/유통의 가격은 기본적으로 `원/kg` 단위로 취급한다.

---

# 8. Contract Term / 연장

계약조건을 Contract Header에 덮어쓰지 않고 Term/Version으로 관리한다.

예:

```text
Term 1: 최초 90일 / 수수료 1.2% / 이자 7.5%
Term 2: 연장 90일 / 수수료 1.4% / 이자 8.5%
```

연장 수수료의 기준금액은 연장 시작 시점의 잔존재고에 해당하는 원가금액을 원칙으로 하여 이미 출고된 물량에 수수료가 중복 발생하지 않도록 한다.

연장 이자도 계약기간별 약정이율을 구간별로 적용한다.

---

# 9. 창고료 및 가변비용

기본 비용항목:

- 보관료: KG_DAY
- 입출고비/상하차료: KG
- 계근비: BOX
- 현물검사료: BOX
- 스티커부착비: BOX
- 기타작업비: 건별/정액/기타 계산단위

Warehouse Master의 요율을 Default로 제시하되 계약별로 수정 가능하다.

Master 요율이 나중에 변경되어도 이미 확정된 계약/출고 계산은 변경되지 않도록 계약조건 Snapshot을 사용한다.

비용항목별 회수/청구방식을 구분한다.

- 수입원가 포함
- 출고단가 포함
- 출고시 별도청구
- 월별 별도청구
- 건별 별도청구
- 당사 부담

같은 실제 비용이 수입원가와 계약판매에서 이중 부과되지 않도록 한다.

보관료 기본 일수:

`출고일 - 입고일 + 1`

단 계약에 따라 월말까지 별도발행 후 다음 달 출고 시 당월 1일부터 출고일까지 계산하는 방식 등을 지원해야 한다. 이미 청구된 기간을 중복 부과하지 않아야 한다.

운영자에게 계약별 요율/항목/기간을 조정할 수 있는 유연성을 제공한다.

---

# 10. 수수료와 청구법인

수수료가 판매단가 포함형일 수도 있고 별도발행형일 수도 있다.

별도발행 조건에서는 믹스비즈의 계약판매 입금요청금액에 해당 수수료를 포함하지 않는다.

현재 업무에서는 별도 과세법인(예: 메뉴주식회사)이 수수료를 별도 발행할 수 있다.

따라서 계산결과에는 최소한 다음 개념을 보존한다.

- 수수료 계산금액
- 청구방식
- 청구주체 법인
- 발행/정산상태

세무상 표시와 실제 전표확정은 별도 정책/사용자 확인을 거친다.

---

# 11. 중량 및 부분출고

계약판매의 기본 중량정책:

`최초 LOT 총중량 ÷ 최초 총BOX = 고정평균중량`

중간 부분출고:

`출고 BOX × 고정평균중량 = 적용 출고중량`

최종 잔량출고:

`최초 LOT 중량 - 누적 확정 출고중량 = 최종 출고중량`

으로 LOT를 0으로 마감한다.

계약조건에 따라 실계근중량 방식도 허용한다.

예상 입금요청 단계와 실제 출고 후 확정정산 단계를 분리한다.

---

# 12. 출고/입금 통제

계약판매의 절대적 기본원칙은 미수 없는 출고이다.

정상 Flow:

```text
출고요청
→ 예상금액 계산
→ 입금요청
→ 입금
→ 입금확인
→ 출고승인
→ 실제출고
→ 최종정산
```

일반 사용자는 입금확인 전에 출고를 확정할 수 없다.

최종 Master 권한자는 업무상 필요 시 예외출고를 승인할 수 있으나 다음을 반드시 기록한다.

- 예외사유
- 승인자
- 승인일시
- 계약/Release
- 관련 금액

향후 권한위임에도 동일한 Audit 원칙을 적용한다.

---

# 13. 정산차액과 계속거래

선입금과 실제 확정금액의 차이는 지속거래에서 차기 거래에 상계할 수 있다.

단순 잔액 숫자만 저장하지 않고 다음을 추적한다.

- 발생일
- Contract
- Release
- 발생원인
- 발생금액
- 상계금액
- 잔액
- 어느 차기 Release에 상계되었는지

허용 차액범위는 코드에 고정하지 않고 향후 회사/거래처/계약 정책으로 설정 가능하게 한다.

---

# 14. 보증금 / 담보

보증금은 일반 미수/미지급과 구분된 독립 관리영역이다.

지원 대상:

- 최초 보증금 수취
- 추가 보증금 요청/수취
- 시세하락 등 위험증가에 따른 추가담보
- 반환
- 계약대금과 상계
- 다른 계약으로 재배정
- 하나의 보증금을 복수 계약의 공동담보로 배정
- 담보해제

따라서 `contract.deposit_amount` 같은 단일 Column으로 처리하지 않고 Deposit Ledger와 Contract Allocation 관계를 둔다.

---

# 15. 원가확정 후 추가비용

원가확정 후 추가 수입원가성 비용이 발생한 경우 업무상 영향에 따라 처리방법을 선택할 수 있다.

- 아직 출고가 없고 다른 거래에 영향이 없으면 원가 재정산/매입단가 수정
- 이미 출고가 진행되었거나 과거 원가변경이 부적절하면 향후 출고의 일회성비용 등으로 계약처와 협의하여 처리

자동산출 비용도 Master 사용자가 추가/삭제/수정할 수 있어야 한다.

Override 시 원값, 수정값, 사유, 사용자, 일시를 보존한다.

---

# 16. 계약상대방 / 매입처 / 매출처 / 출고처 / 입금자

Financing에서는 다음 주체를 서로 독립적으로 표현할 수 있어야 한다.

- Contract Partner
- Purchase Party
- Authorized Related Party
- Sales Party
- Release/Ship-to Party
- Payment Party

예:

A와 계약했으나 A가 지정한 B가 입금하고 B에게 실제 판매/출고할 수 있다.

국내매입에서도 A와 계약했지만 실제 상품은 C에서 매입할 수 있다.

각 주체는 동일 Partner Master를 참조하며 계약과의 승인관계 및 이력을 남긴다.

---

# 17. 정산방식

최소 두 가지 정산방식을 고려한다.

## 17.1 Standard Sale

일반적인 계약판매 방식으로 상품 원가와 계약조건을 반영한 판매단가로 실제 상품매출을 발생시킨다.

## 17.2 Return Settlement

계약상 협의된 경우 매입원금 전체를 다시 매출로 발생시키지 않고 원매입에 대한 반품거래를 이용하여 원금을 정리하고, 계약에서 발생한 경제적 수익/비용을 별도로 거래화할 수 있다.

개념:

```text
원상품 매입
→ Financing 진행
→ 원금 상당 매입반품
→ 면세법인: 약정 이자성격 금액 등 필요한 매출
→ 과세법인: 중개수수료/창고료 등 별도발행
```

세무처리를 시스템이 임의로 결정하지 않는다. 계약별 정산방식 선택, 원거래 연결, 금액산출 후 사용자 확인을 거쳐 실제 ERP 거래를 확정한다.

---

# 18. 일반유통 반품

반품은 Financing 전용 기능이 아니라 ERP 일반유통의 기본 Transaction이다.

지원해야 할 기본형:

- 매입반품
- 매출반품

반품은 원거래를 추적할 수 있어야 하며 단순 삭제나 임의 음수수량 입력으로 대체하지 않는다.

원거래, 반품수량/중량, 사유, 처리일, LOT, 재고 및 채권/채무 역전관계를 추적한다.

Financing의 Return Settlement도 이 일반 반품기능을 재사용한다.

---

# 19. 자동계산 / Override / Comment

계산엔진은 UI와 분리한다.

개념:

```text
GUI
→ Financing API
→ Financing Service
→ Calculation Engine
→ ERP Master / Transaction
```

자동계산 결과를 Master가 수정할 수 있으나 원값을 덮어쓰지 않는다.

보존항목:

- 자동계산값
- 수정값
- 수정사유
- 수정자
- 수정일시

Comment는 최소 다음 두 종류를 지원한다.

- internal_comment: 내부 직원용
- partner_comment: 거래처에게 공개 가능한 내용

---

# 20. 숫자/반올림 정책

현재는 기존 MXMN ERP 기준원칙을 준용한다.

- 가격/단가/개별원가: 원 단위 기준 기존 정책
- 중량: 소수점 둘째 자리
- BOX: 정수
- 환율: 소수점 둘째 자리
- 수수료 VAT 등: 기존 MXMN 정책 준용

향후 일반 상거래관행을 기준으로 항목별 반올림/올림/절사/절상 정책을 다시 확정한다.

계산코드 곳곳에 `round`, `ceil`, `int` 등을 흩어놓지 않고 중앙 Numeric/Money Policy를 통해 변경 가능하게 설계한다.

---

# 21. 계약/LOT 종료

LOT 잔량이 0이 되었다고 즉시 모든 계약업무를 CLOSED 처리하지 않는다.

종료 후보가 되면 다음을 점검한다.

- LOT 재고잔량
- 계약판매 미수
- 초과입금/정산잔액
- 보증금/담보
- 미청구 수수료
- 미청구 창고료
- 기타 미정산비용

사용자에게 완료확인 Checklist/팝업을 제공한다.

복수 LOT 계약에서는 개별 LOT 완료와 전체 Contract 완료를 구분한다.

---

# 22. 예상/확정 계산과 Snapshot

Release는 최소 다음 단계를 구분한다.

```text
Release Request
→ Pre-calculation
→ Payment Request
→ Receipt / Allocation
→ Release Approval
→ Outbound
→ Final Calculation
→ Settlement
```

과거 Release의 계산결과는 당시의 계약조건/요율/중량/Override를 Snapshot으로 보존하여 이후 Master나 Contract Term 변경에도 바뀌지 않도록 한다.

---

# 23. Financing 후보 Domain / DB

기존 ERP 설계의 다음 테이블 개념을 중심으로 확장한다.

- `tb_fin_contract`
- `tb_fin_contract_term`
- `tb_fin_contract_lot`
- `tb_fin_release`
- `tb_fin_release_item`
- `tb_fin_release_calc`

추가 후보:

- interest segment
- fee term
- charge term
- authorized contract party
- payment request
- receipt allocation
- settlement balance
- deposit
- deposit transaction
- deposit allocation
- BL transfer
- override/audit

실제 Migration 전에는 기존 ERP의 AccountTransaction, 향후 Sale/Outbound/Receipt 구조와 중복 여부를 다시 검토하여 불필요한 이중원장을 만들지 않는다.

---

# 24. 기존 MXMN_FinSales 처리방향

## 재사용/참조 가치가 높은 부분

- 날짜별 출고단가 Simulation
- 이자/수수료 계산 개념
- 평균중량 계산 개념
- 부분출고 UI 개념
- 창고비 계산 아이디어
- PDF 출력/Layout
- 실제 검증자료

## ERP로 그대로 가져오지 않는 부분

- `TB_LOT_MASTER`
- FinSales 독립 User/Auth
- buyer/item/warehouse 문자열 Master
- 고정 1차/2차 이율 Column
- LOT 조건 직접 덮어쓰기
- 미완성 부분출고 저장방식
- `accumulated_out_boxes`만을 이용한 재고관리
- GUI 내부에 직접 결합된 계산식

독립 `MXMN_FinSales`는 삭제하지 않고 Reference Implementation 및 회귀검증용으로 보존한다.

---

# 25. 회귀검증

실제 업무자료와 기존 FinSales를 검증기준으로 사용한다.

예: BUD0106141 등 실제 계약/원가자료를 이용하여

```text
실제 Excel/계약자료
       ↕
기존 MXMN_FinSales
       ↕
신규 ERP Financing
```

결과를 비교한다.

비교대상:

- kg당 확정원가
- 이자일수/이자
- 수수료
- 창고료/부대비용
- 예상 출고단가
- 입금요청금액
- 부분출고 후 잔량
- 최종 잔량마감

---

# 26. 개발 우선순위

본 설계 v1 이후 Financing 분석만 계속 확장하지 않는다.

## Phase 1 — 상품매입 마감

현재 `Purchase → Inbound → LOT → Payable` 구현을 최신 main 기준으로 재검증하고 실제 빠진 부분만 보완한다.

반품기능을 즉시 전부 구현하지 않더라도 향후 매입반품이 원거래를 정상적으로 참조할 수 있는 구조를 훼손하지 않는다.

## Phase 2 — 일반매출 Vertical Slice

`LOT 선택 → Sale → Outbound → 재고차감 → Receivable`을 구현한다.

향후 매출반품을 원거래 기준으로 연결할 수 있게 설계한다.

## Phase 3 — Financing Contract Vertical Slice

- Contract 생성
- Partner 연결
- 복수 LOT 연결
- Term
- 이자/수수료/창고조건

## Phase 4 — Financing Release

- 출고가 계산
- 입금요청
- 입금확인
- 출고통제
- 부분출고
- Snapshot

## Phase 5 — 정산/보증금/PDF/종료

- 정산차액 상계
- Deposit Ledger
- 최종 잔량마감
- 종료 Checklist
- PDF
- 실제 자료 회귀검증

---

# 27. 초기버전 완료 기준

MXMN ERP 초기버전은 모든 예외기능이 완벽한 상태를 의미하지 않는다.

다음 실제 업무 Cycle이 처음부터 끝까지 연결되면 초기버전의 핵심 목표를 달성한 것으로 본다.

```text
Master
→ 상품매입
→ 입고
→ LOT/재고
→ 일반매출/출고/미수
+
Financing Contract
→ 계약 LOT
→ 계약조건
→ 출고가 계산
→ 입금요청
→ 입금확인
→ 부분출고
→ 잔량관리
→ 최종출고
→ 계약종료
```

향후 세금계산서 완전자동화, 외부 창고 자동출고지시, 고급 경영보고서, 모든 예외 자동화 등은 초기버전 이후 단계적으로 확장한다.

---

# 28. 다음 작업

본 문서 저장 후 다음 작업은 Financing 추가개발이 아니라 **상품매입 마감**이다.

최신 GitHub `main`을 기준으로 상품매입의 실제 구현을 다시 확인하여:

1. 입력
2. 저장
3. 확정
4. Inbound 생성
5. LOT 생성
6. 재고 반영
7. Purchase Payable 생성
8. 조회/수정/취소 및 데이터 무결성

을 점검하고, 현재 구현에서 실제 빠진 부분만 작은 Vertical Slice 방식으로 보완한다.

각 Slice는 `코드 수정 → 검증 → 사용자 확인 → Git 정리` 순서로 마감한다.
