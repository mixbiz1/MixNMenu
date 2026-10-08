# 계약서 5종 A4 1페이지 및 Qt 폰트 컨텍스트 수정

## 적용 기준

- Source of Truth: mixbiz1/MixNMenu main, bc0e5c4.
- clean bc0e5c4 + `MXMN_BATCH2A_CONTRACT_DOCUMENT_V1_bc0e5c4_20261008.patch` + `MXMN_CONTRACT_DOCUMENT_V1_PAGE_TEST_FIX_INCREMENT_20261008.patch` 적용 직후에서 추가하는 증분이다.
- 최종 증분: `MXMN_CONTRACT_DOCUMENT_A4_SINGLE_PAGE_FINAL_INCREMENT_20261008.patch`.
- 기존 두 patch는 이번 증분에 중복 포함하지 않는다. DEV reset/기존 수정사항 덮어쓰기 없이 git apply --check 성공 후 적용한다.
- 기존 docs/16의 내용이 있는 다중 페이지 허용 정책은 이번 최종 업무규칙으로 대체된다. 정상 5양식은 A4 세로 1페이지, 수용한계 초과 시 안내 및 출력 중단이다.

## 실제 출력 코드 변경

`financing_document.py`에서 QTextDocument.print_의 자동 페이지 분할을 계약서 출력에 사용하지 않는다. QPdfWriter는 그대로 유지한다.

- A4 세로, 사방 12mm 여백. PDF와 실제 프린터가 같은 print_contract 함수를 사용한다.
- QTextDocument를 고정 96 DPI 이미지 측정 장치 및 design metrics로 배치한다. 화면 배율/출력 해상도에 따라 문서의 줄바꿈과 페이지 계산이 바뀌는 경로를 제거했다.
- 기본 본문 9pt. 출력용 문단 간격 3px/셀 패딩 3px/제목 간격을 적용한다. 저장된 HTML/확정 Snapshot을 수정하지 않는다.
- 배치가 근소하게 초과하면 가장 작은 본문이 8.5pt 이상인 범위에서만 균일 축소한다. 과도한 축소, 내용 잘라내기, 조항 삭제, PDF 일부만 그리기는 하지 않는다.
- 가로/세로 크기를 모두 검사한다. 상품이 너무 많거나 특약/주소가 길어 최소 가독성 안에서 수용되지 않으면 `A4 1페이지 수용 한계를 초과했습니다...` 오류를 표시한다. GUI의 기존 오류 안내 경로를 사용한다.
- 실패하면 기존 PDF 파일 및 확정 Snapshot을 보존한다. 임시 PDF는 정리하며 계약 데이터/version/Audit 상태를 변경하지 않는다.
- 출력 장치가 A4를 지원하지 않으면 명확한 오류로 중단한다. 프린터 하드웨어의 용지/배율 선택은 DEV에서 확인해야 한다.
- BL 관세사용 자동 금액 제외, 표/서명란 및 모든 원본 조항은 그대로다. 5종 템플릿 파일/API/Schema/계약번호/LOT 업무 로직 변경 없음.

## 전체 pytest 폰트 오류 분석 및 수정

실제 소스에서 여러 GUI 테스트 모듈이 collection 단계에 `QT_QPA_PLATFORM=offscreen`을 setdefault하고, test_mdi_resize가 모듈 전역 QApplication을 생성하는 경로를 확인했다. 계약서 단독 실행과 전체 collection의 최초 플랫폼이 달라질 수 있다. Windows offscreen backend에서는 설치된 Windows 폰트 registry가 동일하게 노출되지 않는 환경 문제가 기존 Batch1A에서도 확인되었다.

- 신규 tests/conftest.py가 collection 전 pytest_configure에서 QApplication을 생성한다.
- Windows는 먼저 `QT_QPA_PLATFORM=windows`를 설정하고, Linux Work는 offscreen을 사용한다. 기존 모듈의 setdefault가 Windows 플랫폼을 덮어쓰지 못한다.
- 세션/모듈에서 QApplication strong reference를 보관하고, 마지막 창 닫힘으로 종료되지 않게 한다. 함수별 fixture 종료 때 애플리케이션을 삭제하지 않는다.
- trade_statement_document.korean_font_family에 올바른 QGuiApplication 컨텍스트 여부만 검사하는 guard를 추가했다. 컨텍스트가 없으면 설치 안내 대신 QApplication 초기화 안내로 실패한다.
- 기존 설치 목록 우선순위, Malgun Gothic/맑은 고딕/Noto 등의 선택, script/glyph probing 미사용, 실제 폰트 부재 오류는 변경하지 않는다. fake 폰트를 캐시하거나 registry 실패를 무조건 성공 처리하지 않는다.
- 신규 회귀에서 app 수명, 실제 registry 조회, 빈 registry monkeypatch 종료 후 원래 목록 복구, 앱 부재 시 native 조회 전 중단을 검증한다. 기존 거래명세표 별도 프로세스 100행 한글 PDF 테스트는 그대로 유지한다.
- Linux Work에서 Windows backend를 직접 실행하지 않았다. 보고된 9건의 Windows 실패는 위 초기화 경로가 유력한 원인이며, Windows DEV 전체 재실행으로 최종 확인해야 한다. Windows 폰트 재설치는 요구하지 않는다.

## 자동검증 및 샘플

- 5종 정상 1상품/복수상품 계약: A4 1페이지, 전체 HTML 본문 블록/표 셀/조항/서명 보존, 한글 텍스트 추출, 세무사용 금액 및 관세사용 금액 제외 통과.
- 5종 샘플 PDF: 모두 1페이지. PDF를 JPEG 렌더링하여 표/한글/서명란의 겹침/잘림이 없는지 시각 확인했다.
- 세무사용 샘플 금액: 49,512,128원. 국내매입 샘플 단가 2,250원/Kg, 금액 49,512,128원. 수입 USD 오퍼단가/금액은 현재 저장 데이터가 없어 빈칸 유지한다.
- 확정 Snapshot 기반 출력/재출력 일치, QTextEdit로 편집 저장한 HTML 출력, 근소한 초과 시 8.5–9pt 축소 범위 통과.
- 100상품/비정상적으로 긴 특약은 수용한계 안내로 중단하며 Snapshot과 기존 PDF 보존 통과.
- 동일 함수를 96/300/600 DPI 장치에 출력하여 1페이지/본문 동일성과 텍스트 bounding rectangle의 2pt 이내 일치를 검증했다. 이것을 실제 Windows 종이 인쇄 검증으로 간주하지 않는다.
- 계약서 + Qt 컨텍스트 + 거래명세표 + Batch2A + Financing 선택: **102 passed, 1 warning**.
- 전체 pytest: **260 passed, 1 warning**. warning은 기존 Starlette/httpx deprecation이다.
- Python compile / UTF-8 / git diff --check / 정확한 두 patch 적용 기준 git apply --check 통과.
- Work 필요 패키지(PySide6, SQLAlchemy, pytest 등)와 Poppler가 설치된 환경에서 실제 테스트했다. Work PDF 폰트는 설치된 Nanum을 사용한다.

## 변경 파일

- financing_document.py
- trade_statement_document.py
- tests/conftest.py
- tests/test_contract_document_v1.py
- tests/test_qt_application_context.py
- docs/17_MXMN_CONTRACT_A4_SINGLE_PAGE_FINAL_20261008.md

## DEV 최소 확인

1. 기존 두 patch 적용 상태에서 최종 증분 git apply --check 후 git apply. 실패하면 reset/강제 적용하지 않는다.
2. 계약서 V1 테스트 및 전체 pytest를 실행한다. Windows QApplication.platformName은 windows여야 하며 설치 폰트가 그대로 보여야 한다.
3. 실제 계약서 5종 PDF 저장/재출력: A4 세로 1페이지, 한글/금액/표/서명란 확인.
4. 실제 프린터 A4 세로/실제 크기(100%)로 인쇄해 PDF와 배치를 비교한다. 드라이버의 추가 축소/확대는 끈다.
5. 긴 특약/많은 상품에서 안내가 나오고 원본 문서/PDF가 훼손되지 않는지 확인한다. 사용자 내용은 자동 삭제하지 않는다.

DB Schema/Migration, 계약번호, Financing/LOT 업무 로직, 기존 확정 Snapshot 변경 없음. 실제 DB Migration, commit/push, SERVER 반영 없음.
