# MXMN ERP 후속 집중개발 인수인계 — 2026-10-13

## 판정: 부분완료

기준 HEAD: `c9734431c61857c44fdc1b559b2462c84187d3d2` (`mixbiz1/MixNMenu`, main).
clean 기준을 별도 checkout으로 확보했다. Git commit/push, 중앙 DB 접속/변경, 운영 서버 변경은 수행하지 않았다.
전체 1차 목표를 완료한 것은 아니다. 아래 구현 경로는 Linux 격리 SQLite API/Qt 자동검증 완료이며 Windows GUI와 실제 SQL Server 동시성/운영 시나리오는 미검증이다.

## 1. 실제 구현

### P0: 적용일별 계약조건 계산

- 계약 Term effective_from을 기준으로 시작/종료 포함 구간을 분리한다. 변경일은 새 조건에 한 번만 포함된다.
- 이자는 원래 계약 이자기산일과 연기준 365/366을 유지한다. 새로운 Term을 추가했다는 이유로 1차 이자기간을 자동 재시작하지 않는다. 각 Term의 1/2차 기간은 원기산일에서의 누적 위치에 적용된다. 명시한 적용기간 밖은 계속 차단한다.
- 창고료는 실제 입고일부터 출고일까지 각 날짜에 적용되는 Term의 KG_DAY 요율로 계산한다.
- 각 구간의 날짜·적용일수·요율·term_id/version·금액을 Snapshot에 저장한다. 과거 저장 정산을 새 조건으로 재계산하지 않는다.
- 입출고비/계근비는 일회성 출고비용으로 출고일 유효 Term을 적용한다.
- 지원 회수유형은 기존 4종을 유지한다. 기간 중 회수유형 변경, ALL_IN의 수수료 조건변경은 잔존원가/기청구 대사가 필요하므로 차단한다.
- 이자형 반품/자유형, LOT override, 원가에 이미 포함된 PERIOD 비용 중복방지 Guard는 유지한다. 자동 기간 연장이나 연장 수수료 회수는 새로 승인하지 않았다.

### P0: 국내매입 LOT 직접 원가 연결

- DOMESTIC_PURCHASE 계약 + DOMESTIC LOT + 현재 회사의 단일 CONFIRMED 매입상품행 + 실제 입고 연결이 있는 경우, 수입원가 allocation 없이 기존 출고 흐름에 진입한다.
- 정확한 원가 = 확정 매입상품행 공급가액 / 실제 매입중량 × 출고중량. LOT 원가를 임의 입력하거나 수입원가배부를 가짜로 생성하지 않는다.
- 매입전표/상품행/입고행 ID, 매입전표번호, 공급가액, 중량, 단가, 입고일을 Snapshot에 보존한다.
- LOT 개별원가와 확정 매입단가가 다르면 차단한다. 할인/과세/0원/복수근거/미확정/입고연결 누락은 임의 산정하지 않는다.
- 다른 계약의 CONFIRMED 수입원가배부가 있는 LOT는 국내매입 원가로 대체하지 않는다.
- 확정/출고 직전 원가근거와 LOT 원가를 다시 검사한다. 원가 변경 시 SALE/OUTBOUND/채권을 생성하지 않는다.
- 기존 계약 LOT 배정, 누적 부분출고, 특별약정, 입금확인, Audit, FIFO 연결을 재사용한다.

### P1: 입금요청서 PDF

- 출고정산 화면에 `입금요청서 PDF` 버튼을 추가했다. 저장된 정산을 GET하여 출력하며 전표/입금/채권을 생성하거나 변경하지 않는다.
- A4 세로, 한글 폰트, 복수페이지 출력. 계약번호, 실제 출고업체, 계약업체, LOT/상품/BOX/KG, 공급가액/세액/요청총액, 정산항목/조정근거/올림차이, 고정 입금계좌를 표시한다.
- DRAFT/취소/입금확인/출고완료 상태를 표시한다. PAID/SHIPPED는 원요청 재출력이며 잔여미수 요청으로 오해하지 않도록 표시한다.
- 확정용 PDF에 저장된 계좌가 없으면 차단한다. 현재 회사 Master 계좌로 과거 Snapshot을 바꾸지 않는다. 필요한 경우 기존 초안 취소 후 계좌 확인하여 새 정산을 작성한다.
- Qt QPdfWriter와 기존 한글 폰트 선택 및 원자적 파일교체 방식을 사용한다. 추가 Python 운영 의존성/테이블은 없다.
- 첨부 PDF는 테스트 fixture의 가상 업체/계좌/거래 자료다. 실업무 요청서가 아니다.

## 2. 1차 완료범위 재점검

| 범위 | 판정 | 확인/제한 |
| --- | --- | --- |
| 사용자·회사·권한·공통코드 | 완료(기존 코드/자동검증) | 실제 권한별 Windows 검증 별도 |
| 거래처·상품·창고 Master | 완료(기존 코드/자동검증) | 기존 CRUD/Lookup 재사용 |
| 일반매입·LOT·입고 | 완료(기존 코드/자동검증) | 매입/입고/채무/Audit 회귀 유지 |
| 일반매출·출고·재고 | 완료(기존 코드/자동검증) | 마이너스재고 승인 정책 유지 |
| 입금·지급 FIFO | 완료(기존 코드/자동검증) | 별도 보증금으로 혼합하지 않음 |
| 미수·미지급·거래처원장 | 완료(기존 코드/자동검증) | 원거래/원장 연결 유지 |
| LOT/창고/상품 재고·기간수불 | 완료(기존 코드/자동검증) | 기존 기간정의/집계 유지 |
| Drill-down·Audit | 완료(기존 코드/자동검증) | 원전표 식별자/수정취소 Guard 유지 |
| Financing 계약·계약서·수입원가 | 완료(기존 지원 경로/자동검증) | 추가 계약유형 세무 및 실환경 검증 별도 |
| Financing 정산·입금요청·부분출고 | 부분완료 / 실제 환경 검증 필요 | 지원 4종 + 명시된 기간변경 + 국내 면세매입 연결 |
| 보증금·최종정산·CLOSED | 미구현 | 약정 deposit_amount를 실수취금으로 사용하지 않음 |
| 업무용 출력물·PDF | 부분완료 | 계약서/거래명세표/입금요청 PDF 지원; 혼합세무 별도증빙 미지원 |

## 3. 테스트와 검증

- 초기 한글폰트 부재: clean 기준과 변경본 모두 동일한 출력 실패 51개 발생. 운영 코드를 우회하지 않고 Work 환경에 Nanum 한글폰트를 설치했다.
- 한글폰트 보완 후 clean `c973443`: **366 passed, 1 warning**.
- 신규 회귀: 기간조건 5 + 국내매입/PDF/GUI 9 = **14개**.
- 최종 전체: **380 passed, 1 warning** (44.48초).
- warning: 기존 FastAPI/Starlette TestClient의 httpx deprecation.
- 변경 Python compile, `git diff --check` 통과.
- PDF 한글 추출, A4 치수, 1페이지/복수페이지, Snapshot 불변, 계좌변경 후 재출력, HTML escaping, 출력 실패 시 기존 파일 보존 및 GUI GET-only를 검증했다. PDF 페이지 PNG 시각검사 완료.
- SQL Server에 실제 접속하지 않았다. SQLite FK enabled 격리 fixture 사용. 기존 SQL Server UPDLOCK/HOLDLOCK 경로를 재사용하며 잠금 경합/교착/다중 PC 동시출고는 실제 SQL Server에서 별도 검증해야 한다.
- Work에서 요구사항의 모든 PC와 운영 메뉴를 조작한 것이 아니다.

## 4. 변경 파일

7개 파일(신규 4, 기존 3):

1. `financing_release_routes.py`: 기간 계산/국내매입 원가 및 재검사.
2. `financing_release_document.py` (신규): Snapshot 입금요청 PDF.
3. `views/financing_release.py`: PDF 저장 버튼.
4. `tests/test_financing_period_terms.py` (신규): 경계/금액/과거 Snapshot/출고/차단 회귀.
5. `tests/test_financing_domestic_output.py` (신규): 국내원가/반복출고/원가변경/한글 PDF/GUI 회귀.
6. `docs/04_CURRENT_STATUS.md`: 이번 미배포 변경 요약.
7. `docs/22_MXMN_PHASE1_REMAINING_FEATURES_HANDOFF_20261013.md` (신규): 이 인수인계.

별도 `MXMN_WORK_PROGRESS_20261013.md`와 테스트 PDF는 patch 밖의 다운로드 산출물이다.

## 5. Migration

**이번 patch에 추가 Migration 없음.** 기존 사용자 적용 완료 `db_financing_release_migrate.py`/tb_fin_release를 재사용한다. 테이블 DROP/RECREATE/자동 Migration/운영 backfill 없음. 새 내용은 기존 Snapshot JSON에 추가된다. 기존 Snapshot은 cost_source/구간 필드가 없어도 기존 재검사/출력 경로가 동작한다.

## 6. DEV 적용 순서

patch를 `C:\projects\MixNMenu`에 다운로드하고 VS Code 터미널에서 해당 경로 및 기존 venv를 사용한다.

첫 확인 명령(아직 적용하지 않음):

```powershell
git apply --check .\MXMN_PHASE1_REMAINING_FEATURES_c973443_20261013.patch
```

이 명령 성공 후 아래를 순서대로 진행한다.

```powershell
git rev-parse HEAD
git status --short
```

HEAD가 정확히 `c9734431c61857c44fdc1b559b2462c84187d3d2`이고 업무 소스의 미커밋 변경이 없는지 확인한다. 다운로드 patch 등 산출물은 소스 변경과 구분한다. 기준이 다르거나 기존 소스 변경이 있으면 reset/덮어쓰기를 하지 않는다.

```powershell
git apply .\MXMN_PHASE1_REMAINING_FEATURES_c973443_20261013.patch
python -m pytest -q
python -m compileall -q financing_release_routes.py financing_release_document.py views\financing_release.py tests\test_financing_period_terms.py tests\test_financing_domestic_output.py
git diff --check
```

기대: 380 passed, 기존 warning 1개. .env/비밀번호를 출력하거나 Git에 추가하지 않는다. DEV/WORK 로컬 SQL Server를 사용하지 않는다. 이 단계의 pytest는 기존 격리 fixture이며 중앙 DB Migration은 실행하지 않는다.

주의: DEV에 patch만 적용하면 중앙 FastAPI는 여전히 기존 코드다. 새 API 계산의 실제 GUI 검증은 아래 SERVER API 코드 반영 이후 가능하다. DEV에 로컬 운영 API/DB를 만들어 우회하지 않는다.

## 7. SERVER 적용 순서 — 사용자의 별도 운영 작업

1. DEV 자동검증 성공 및 변경 검토 후 사용자가 GitHub 반영 여부를 결정한다. 이번 Work에는 commit/push 권한이 없으며 수행하지 않았다.
2. 사용자 결정으로 GitHub에 반영한 경우 SERVER에서 작업트리/설정 확인 → `git pull --ff-only origin main` → 기존 방식의 중앙 API 재시작. 별도 새 Migration은 실행하지 않는다.
3. DEV/WORK GUI를 재시작한다. 기존 중앙 API 주소 `http://100.72.3.34:8000/api/v1`를 유지한다.
4. 아래 테스트용 GUI 시나리오를 중앙 서버에 실행하고 실제 SQL Server 결과를 기록한다. 실계약을 파괴하거나 기존 운영자료를 테스트용으로 수정하지 않는다.
5. 기대와 다르면 운영 거래를 확대하지 않고 결과를 공유한다. 임의 원가/세무구분/입금확인으로 Guard를 우회하지 않는다.

## 8. GUI 검증 시나리오

### 국내 면세매입

- 테스트용 DOMESTIC_PURCHASE 계약/상품, 확정 면세매입 LOT 및 실제 입고를 준비하고 기존 계약 LOT 화면에서 해당 상품행에 배정한다.
- 계약조건에 기산일, 이자율/1·2차 기간, 명시적 비용요율/면세/부담주체/단위, 입금계좌를 확인한다. 수입원가 allocation은 생성하지 않는다.
- 출고정산에서 1 Box/10kg 등 실제 수량을 입력한다. 원가가 확정 매입 공급가액/입고중량 비례값인지 확인한다.
- 요청확정 → 은행 실제 확인(전산 테스트용이면 실제 검증 근거로 명확히 표시) → SALE/OUTBOUND → 실제 업체 채권/재고/원장 확인. 기존 수금 FIFO는 기존 화면에서 별도 등록한다.
- 반복 부분출고, 중량전용, 입금확인 전 출고 차단 및 기존 취소 Guard를 확인한다.

### 조건변경

- 기존 지원유형 EXCLUDE_BROKERAGE 등에서 적법한 Term 변경을 입력한다. 예시: 10/3~10/5 이자 7.5%→10/4부터 10%, 동일 기간 창고료 0.9→1.8원/kg·일. 수치 예시는 운영계약 요율이 아니다.
- 변경일 중복 없이 1일/2일 계산되는지 확인한다. 이자 1·2차 위치는 원기산일에서의 누적 일수다. 새 Term 기산일부터 1차 기간 재시작을 의미하는 계약이라면 이 경로를 사용하지 말고 별도 결정/설계가 필요하다.
- 과거 저장/확정 요청의 금액·계좌·Snapshot 불변을 확인한다.
- ALL_IN 기간변경/회수유형 변경/기간초과가 기존 방침대로 차단되는지 확인한다.

### PDF

- 저장된 정산을 선택하고 `입금요청서 PDF` 버튼을 누른다.
- 한글, 계약/실제 출고업체, LOT/수량, 공급가액/세액/요청금액, 근거/올림차이 및 저장 계좌 확인.
- 확정 후 Master 계좌 변경으로 재출력본이 바뀌지 않아야 한다. DRAFT는 검토용 표시, 취소는 취소 표시, 입금확인/출고완료는 원요청 재출력 표시다.
- 여러 LOT와 긴 상품명으로 페이지 잘림이 없는지 실제 Windows 폰트/프린터 환경을 확인한다.

## 9. 미완료 / 사용자 결정 필요

- 과세·면세 혼합, 과세 서비스 별도청구, 청구법인/사업자별 전표·증빙 연결: 미구현. 상품 SALE에 과세비용을 임의 면세 합산하지 않았다. 발행법인·과세표준/세액 처리·포함/별도청구 분개 기준이 필요하다.
- 자유형 항목선택/개별 과세 ±비용, 이자형 원가반품: 미구현. 기존 승인요건과 차단 유지. 반품 대상 원거래 및 회수/채권 관계를 명시해야 한다.
- 기간 연장 수수료/잔존원가/기청구 관리/LOT override: 미구현. 새 Term의 1차 기간 재시작 정책이 필요한 계약은 별도 결정 필요.
- 국내매입 할인·과세·추가 경비·복수매입 원가: 미지원. 해당 원가/세액/경비 귀속 기준을 확인해야 한다.
- 보증금 수취·배정·충당·반환/취소·잔액: 미구현. 독립 Ledger 방향은 기존 설계에 있으나 FIFO/채권과의 정확한 전표/취소/공동담보 연결은 이번에 임의 확정하지 않았다.
- 최종 대사/CLOSED/마감수정 통제: 미구현. 재고 0만으로 마감하지 않는다. 보증금/미청구비용/채권 정리 경로 이후 구현해야 한다.
- PDF는 면세 지원 경로의 정식 요청 출력이다. 혼합세무/별도청구/보증금충당 요청은 그 기능 구현 후 확장해야 한다.

## 10. Patch 검증

신규 파일을 포함한 `git diff --binary` patch를 작성하고 별도 clean `c973443` checkout에서 `git apply --check` 및 실제 적용/`git diff --check`로 검증한다. 최종 파일 크기/해시는 별도 진행기록에 남긴다. Git commit/push는 하지 않는다.
