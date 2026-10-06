# MXMN Batch 1A — 검색 공통화 / 일반매출 거래명세표

기준: main `5a187a7`. Financing Phase 1, 기존 Sale/Outbound/LOT/미수/입금/지급 정책 유지.
최종 설치단위: clean `5a187a7` → `MXMN_BATCH1A_FINAL_5a187a7_20261006.patch` 한 번 적용. 이전 본체/폰트 증분 patch를 순차 적용하지 않는다.
이번 patch는 commit/push, 실제 SQL Server Migration, SERVER 배포를 수행하지 않는다.

## 사용 흐름

- 매입: 기존 Enter 검색 그대로. `LookupDialog`를 `views/lookup_dialog.py`로 추출하고 기존 import 호환 유지.
- 매출: 코드/상호/사업자번호로 현재 회사의 매출거래처를 서버 검색, 최대 50건.
- Financing: 계약업체/상품/추가 출고업체 검색 버튼. 상품코드/명칭/규격, 업체코드/명칭/사업자번호 검색. PK를 선택값으로 유지. 기존 계약 선택 시 초기 목록에 없어도 해당 계약업체 PK를 복원.
- 매출 저장 후 `거래명세표 / 재출력`: 현재 매출 미리보기 → 발행 → 같은 창에서 PDF/인쇄. 기존 발행본이 있으면 최신 발행본을 기본 선택. 미발행본의 출력은 비활성화.
- 정정 전표를 발행하면 다음 version. 단순 재출력/중복 클릭은 동일 ID/version.
- `취소 포함 (재출력)`으로 취소 전표의 발행본 조회 가능. 취소 매출 최초/추가 발행은 거부.

## API / 권한

기존 `GET /products`에 선택적 `limit`; 기존 회사 `GET /accounts`에 `search`, `purpose` (`SALE/PURCHASE/CONTRACT`), `limit` 추가. 무인자 호출 결과 유지.
목록 조회에만 `lookup_for=PURCHASE_GENERAL/SALES_GENERAL/FINANCING_CONTRACT`를 지원해 해당 업무 read 권한을 재사용한다. Master 상세/등록/수정 권한은 그대로이며 회사 접근 검사는 선행한다.

`/api/v1/companies/{comp_code}/sales/{sale_id}/statements`:

| Method / suffix | 역할 | 기존 매출 권한 |
|---|---|---|
| GET `/preview` | 현재 확정 SALE에서 미발행 미리보기 | read |
| GET | 발행 version 목록 | read |
| GET `/{statement_id}` | 지정 발행본 재조회 | read |
| POST | 최초/정정 발행, 동일 매출 revision 중복 발행 재사용 | create |

## Snapshot / Version / Audit

`tb_trade_statement`만 추가한다. 회사+SALE+문서종류+version UNIQUE, SALE/Company/User FK, Snapshot JSON (NVARCHAR(MAX)), SHA-256 Sale revision fingerprint, 발행자/UTC 발행일.

- 발행 시 회사/거래처 사업자 표시정보, 상품명/규격, LOT/BL/창고, BOX/KG/단가/공급가액/세액/할인·할증/합계 및 세무 Snapshot을 자동승계한다. 금액 재계산/재입력은 없다.
- Master 값은 **발행 시점 현재 Master**이다. `master_origin`에 이를 명시하며 거래일 당시 Master 복원이라고 주장하지 않는다.
- Master 변경은 발행본 Snapshot 또는 매출 revision fingerprint를 바꾸지 않는다.
- 매출 정정은 `updated_at`과 저장 거래값으로 감지한다. 과거 발행본은 유지하고 API에서 `SUPERSEDED` 표시. 매출 취소는 `CANCELLED` 표시. 이 상태는 현 SALE 상태/revision에서 읽기 시 계산하며 Snapshot을 덮어쓰지 않는다. Sale의 기존 UPDATE/CANCEL Audit이 정정/취소 근거다.
- 발행은 공통 Audit `TRADE_STATEMENT/ISSUE`로 SALE과 연결한다. Snapshot과 Audit은 같은 transaction이다.
- SQL Server의 SALE row `UPDLOCK,HOLDLOCK`을 발행/정정/취소에서 함께 사용한다. version UNIQUE가 최종 방어선이다. 실제 SQL Server 동시 실행 검증은 후속 DEV 검증 항목이다.

## Migration / 출력

`db_trade_statement_migrate.py`: 테이블 생성과 인덱스 생성을 별도 execute batch로 분리. 존재 여부 guard, 기존 데이터 변경/복사/삭제 없음. 실제 DB에 실행하지 않았다. 자동검증은 emitted SQL의 batch/guard/model 일치 및 SQL Server dialect compile을 대상으로 한다. 실제 SQL Server 최초/재실행 검증을 대신하지 않는다.

새 런타임 dependency 없음. 기존 PySide6 QTextDocument 사용. PDF는 QPdfWriter, 실제 프린터 인쇄는 QPrinter 사용. PDF 생성은 native printer discovery를 사용하지 않는다. A4 가로, 다중 행/페이지, 한글/BOX/KG/단가/금액/합계. 한글 글꼴(Windows 맑은 고딕 또는 나눔고딕 등) 필요; 전체 설치 family 목록에서 Malgun Gothic/맑은 고딕, NanumGothic/나눔고딕, Noto Sans CJK KR, Noto Sans KR, Apple SD Gothic Neo, AppleGothic, Gulim/굴림, Dotum/돋움 순으로 선택한다. Korean script classification과 QRawFont glyph 사전검사를 필수 Guard로 쓰지 않는다. 알려진 후보가 없으면 정상 UTF-8 오류를 표시한다.

PDF는 문서 ID의 저장 Snapshot으로 재생성하며 발행일/발행자/version은 저장값 사용. 사용자 선택 경로에 임시 파일로 출력 후 atomic replace; DB에는 PC 경로를 저장하지 않는다. 출력 직전 상태 재조회로 취소/정정 표시. 인쇄/PDF 실패가 이미 발행된 문서/SALE을 취소하지 않는다. 서버 PDF binary 보관·웹 출력·전송·범용 Template 편집은 후속 범위다.

## DEV 실제 검증 항목

1. 수십/수백 상품·거래처에서 일부 코드/규격/사업자번호 검색과 Enter/더블클릭 PK 선택.
2. 매입 저장, 매출 저장, Financing 기존 계약 열기/계약상품/계약업체/출고업체 선택.
3. 확정 매출의 복수 행, BOX 0/KG 출고, 과세/면세, 할인/할증, 합계 대조.
4. 발행 후 Master 변경 → 이전 발행본 불변; 매출 정정 → v2, v1 재출력.
5. 취소 포함 조회 → 과거 발행본 취소 표시, 신규 발행 차단.
6. 실제 Windows 프린터/PDF에서 한글, 긴 업체/상품/규격/주소, 다중 페이지 열 폭·페이지 경계 확인.
7. 제한 사용자 read/create 및 타회사 조회/발행 차단.
8. 승인된 별도 DB 작업에서 Migration 최초/재실행 및 동시 발행 검증.

## Work 자동검증 결과

- 선택: Batch 1A 25개 + Financing Phase 1/Migration 9개 = **34 passed**, 1 warning.
- 전체: **174 passed**, 1 warning (환경의 Starlette/httpx deprecation).
- 기존 기준의 149개 회귀테스트를 포함한다. 새 런타임 package 추가 없음.
- GUI는 HTTP를 격리한 offscreen 테스트. 한글/100행 PDF 생성·텍스트 추출·첫 페이지 렌더링 검토 완료. 테스트 환경에는 나눔고딕을 설치했다.
- 실제 MXMN-DEV PC/Windows 프린터/SQL Server/SERVER 검증은 수행하지 않았다.
