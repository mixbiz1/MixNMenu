# 계약서 V1 Windows 페이지 검증

## 정확한 적용 기준

이번 결과는 clean `bc0e5c4` + `MXMN_BATCH2A_CONTRACT_DOCUMENT_V1_bc0e5c4_20261008.patch` 적용 직후 상태에서 추가하는 증분이다. 이전 V1 전체 patch를 다시 적용하거나 DEV 파일을 reset/복원하지 않는다.

검증에 사용한 V1 patch SHA-256:
`a99ffd43fb20ae119b862c6ea67e6b42283569ade90e162fe951f9061e6281c8`

변경은 `tests/test_contract_document_v1.py`와 이 문서뿐이다. 계약서 제품 코드, 5종 템플릿/조항/표/서명란, 글꼴 선택, PDF 여백/글자 크기, Snapshot/Audit, QPdfWriter 및 DB Schema 변경 없음. 기존 Batch1A 테스트도 변경하지 않았다.

## 원인 및 확인 한계

기존 테스트의 `reader.pageCount()==1`은 Work의 NanumGothic 출력 결과를 Windows에서도 동일해야 한다고 가정한 조건이다. 같은 A4/9pt라도 폰트의 글자폭/행높이 및 Qt 출력환경에 따라 줄바꿈과 페이지 수가 달라진다. 현재 양식은 추가 상품/특약/긴 주소를 허용하며 1페이지 자체가 업무 무결성 요건은 아니다.

- 원본 V1 소스를 별도 작업공간에 재현했다. Work에 있는 Nanum 계열 6종으로 수입대행/BL 기본의 동일 짧은 예시는 모두 1페이지이며 본문/서명이 보존되었다.
- 실제 특약이 긴 예시를 두 양식으로 출력해 2페이지를 재현했다. 두 번째 페이지에는 양쪽 사업자정보, 주소, 대표 및 서명란이 있었다. JPEG 렌더링으로 확인했고 빈 페이지가 아니었다.
- 사용자가 보고한 Windows PDF 파일 자체는 이번 작업에 제공되지 않았다. 그 파일의 2페이지가 빈 페이지인지, 서명/조항이 있는지 확정하지 못했다. Windows에서 실제 실행/재현했다고 주장하지 않는다.
- 확인되지 않은 원인을 근거로 조항 삭제, 글자 크기 축소, 출력기 교체 또는 Master/Snapshot 변경을 하지 않았다.

## 테스트 수정

5종 PDF 검사에서 1페이지 고정을 제거하고 아래를 검증한다.

1. PDF가 한 페이지 이상 있으며 각 페이지에 페이지 번호 이외의 실제 내용이 있다. 빈 페이지/페이지 번호만 있는 페이지는 계속 실패 처리한다.
2. Snapshot HTML을 QTextDocument로 해석한 모든 비어 있지 않은 본문 블록이 PDF 전체 텍스트에 존재한다. 표 셀, 전체 조항, 당사자 정보 및 서명란 포함이다.
3. 비교 시 공백/줄바꿈 및 Qt가 추가하는 각 페이지의 마지막 페이지 번호만 제외한다. 페이지를 넘어 이어지는 조항/특약에 페이지 번호가 섞여 오판정하지 않는다.
4. 한글, 금액 표시/관세사용 숨김, Snapshot 기반 출력, QPdfWriter, QPrinter native discovery 미사용을 유지한다.
5. 긴 특약으로 수입대행/BL 기본을 다중 페이지 생성하고 재출력한다. 모든 본문 보존 및 동일 환경의 재출력 페이지 수 일치, 원본 Snapshot 불변을 검증한다.
6. 페이지 번호만 있는 두 번째 페이지를 테스트 helper가 반드시 거부하는 음성 회귀테스트를 추가했다.

Windows에서 새 검사가 빈 페이지 또는 본문 누락으로 실패한다면 기존 `expected 1, actual 2`와 달리 해당 페이지/본문 블록이 명확히 표시된다. 이는 남아 있는 출력 결함의 증거이며 별도 조사 대상이다. 검사를 skip하거나 빈 페이지를 허용하지 않는다.

## Work 검증 결과

Python/PySide6/SQLAlchemy/pytest 및 Poppler 설치 환경에서 검증했다. Qt offscreen + 실제 설치한 Nanum 폰트를 FONTCONFIG_FILE로 제공했다. Windows 글꼴 설치 상황을 Work에서 확인했다고 간주하지 않는다.

- 계약서 V1 신규 및 기존: 26 passed (선택 묶음에 포함).
- 계약서 V1 + Batch1A 거래명세표 + Batch2A + Financing 선택: **91 passed, 1 warning**.
- 전체 pytest: **249 passed, 1 warning**.
- 전체 실행에서 QFontDatabase 선택/부재/mock 회귀 및 기존 별도 프로세스 100행 한글 거래명세표 PDF 검사가 통과했다. 기존 process isolation을 그대로 사용하며 관련 제품 코드를 변경하지 않았다.
- 5종 PDF 한글/금액/표/서명란 렌더링과 전체 본문 보존 통과. 짧은 Work 예시는 모두 1페이지, 긴 수입 예시는 내용이 있는 2페이지. 100상품 다중 페이지 테스트 유지/통과.
- Python compile / UTF-8 / 증분 diff --check 통과.
- 별도 clean bc0e5c4에 V1 patch 적용 후 증분 `git apply --check` 통과.
- warning은 기존 Starlette/httpx deprecation이다.
- 실제 DB Migration, commit/push, SERVER 변경 없음.

## DEV 적용 및 최소 확인

프로젝트에서 증분 파일에 대해 아래 두 명령만 실행한다. 기존 수정사항과 충돌하면 check가 실패하므로 강제 적용/reset하지 않는다.

```powershell
git apply --check "C:\path\MXMN_CONTRACT_DOCUMENT_V1_PAGE_TEST_FIX_INCREMENT_20261008.patch"
git apply "C:\path\MXMN_CONTRACT_DOCUMENT_V1_PAGE_TEST_FIX_INCREMENT_20261008.patch"
```

적용 후 계약서 V1 단독 및 전체 pytest를 실행한다. 수입대행/BL 기본 PDF의 실제 마지막 페이지에서 조항 또는 서명란을 확인한다. 내용이 있는 2페이지는 정상이며, 페이지 번호만 있는 빈 페이지는 정상으로 판정하지 않는다. Windows 실제 전체 결과는 DEV 확인 후 기록한다.
