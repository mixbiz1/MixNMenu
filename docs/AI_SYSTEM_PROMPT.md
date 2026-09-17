# MXMN AI DEVELOPMENT RULES

MXMN 코드를 작성·수정하는 AI는 다음 규칙을 우선 적용한다.

## 1. 작업 전

1.  `docs/00_PROJECT_BASELINE.md`를 먼저 읽는다.
2.  관련 Domain의 Spec/Domain/DB 문서를 확인한다.
3.  수정 대상 파일만 보지 말고 호출하는 파일과 호출되는 파일을 함께
    확인한다.
4.  현재 실행되는 기능을 불필요하게 깨뜨리지 않는다.
5.  Legacy MeatSoft/KIMS는 업무 벤치마크이며 복제 대상이 아니다.

## 2. 사용자 특성에 따른 개발 방식

사용자는 프로그램 언어를 직접 검증하지 않는다. 따라서 부분 코드 조각만
던지고 사용자가 알아서 합치게 하지 않는다. 가능하면 수정 완료된 전체
파일 또는 명확한 자동 적용 단위로 제공한다.

수정 후 반드시 설명한다: - 수정한 파일 - 무엇을 수정했는지 - 왜
수정했는지 - 기존 기능에 미치는 영향 - VS Code에서 실행할 명령 - 정상일
때 보이는 결과 - 오류 발생 시 사용자가 캡처할 화면/터미널

## 3. DB 원칙

-   Multi-Company
-   Partner와 Customer 분리
-   Product와 LOT 분리
-   LOT별 개별원가
-   Purchase ≠ Inbound
-   Sale ≠ Outbound
-   Financing은 일반유통 위 Layer
-   Transaction Tax Snapshot
-   BL + 축산물이력번호 자동승계
-   One Fact → One Data
-   ExpenseCode는 ProductCategory·CodeValue와 분리된 계층형 Master
-   사용된 Master 코드는 물리삭제하지 않고 사용중지
-   가변 비용/조건은 Row/Parameter화
-   법적/회계적/계약적 계산결과는 Snapshot 보존

## 4. UI 원칙

신규 화면은 Pure Python PySide6를 기본으로 한다. 신규 Qt Designer `.ui`
의존을 만들지 않는다. Enter 중심 업무입력, F-key 단축키 등 현업 ERP
생산성을 고려한다.

UI 편의기능의 우선순위는 `데이터 무결성·오류방지 → 안정성·반응속도 →
사용 편의성`이다. 정렬 후에는 화면 행번호가 아니라 PK/고유 ID로 원본을
찾아야 하며, 입력순서가 업무자료인 표에는 자동정렬을 적용하지 않는다.
편의기능이 PK/FK, 중복방지, 저장대상 식별 또는 성능에 위험을 만들면 그
기능을 제외한다.

## 5. 안전한 변경

대규모 일괄 리팩터링을 피한다. `작은 변경 → 실행 → 검증 → Commit` 순서를
지킨다. DB 스키마 변경 전 기존 데이터와 Migration 영향을 확인한다.

Python 실행검증 전에는 `PySide6`, `sqlalchemy`, `pyodbc`, `fastapi`,
`pydantic`, `httpx`, `python-dotenv` 등 해당 코드에 필요한 패키지를 먼저
설치하거나 설치 여부를 확인한다. 가능한 경우 문법검사에 그치지 않고 실제
모듈 import와 화면/객체 생성까지 실행검증한다. OS 런타임이나 외부 DB가
없어 실행하지 못한 범위는 통과한 것으로 표현하지 않고 명확히 기록한다.

## 6. 외부연동

MeatWatch 등 외부 API 오류가 ERP 원천 거래 저장을 막지 않도록
Integration을 분리한다. 외부 문서 Binary는 원칙적으로 SQL Server에 직접
저장하지 않는다.

## 7. 명칭

프로젝트 공식 명칭은 **MXMN**으로 사용한다. 기존 폴더명 `MixNMenu`는
현재 로컬 경로 호환을 위해 당분간 유지할 수 있다.
