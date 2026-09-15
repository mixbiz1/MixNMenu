MXMN Vertical Slice #1 - Multi Company
기준본: 최신MixNMenu_20260915-2_office.zip

교체 파일:
1) main.py
2) models.py
3) views/company_reg.py

DB Schema 변경: 없음
기존 00001 데이터 변경: 없음

주요 변경:
- Company comp_code의 00001 기본값 제거
- GET /api/v1/companies 회사 목록 API
- GET /api/v1/companies/{comp_code} 회사 단건 API
- POST /api/v1/companies 신규 회사 등록
- PUT /api/v1/companies/{comp_code} 기존 회사 수정
- 기존 GET /api/v1/company는 호환용으로 유지
- 업체등록 화면에 회사 선택 / 회사코드 / 신규 / 새로고침 추가
- 레거시 중복 payload(comp_cd, comp_nm 등) 제거

검증:
python -m py_compile main.py models.py views/company_reg.py
통과 완료.

실행 권장:
터미널 1: uvicorn main:app --reload
터미널 2: python app.py

테스트 순서:
1. 기존 로그인 성공
2. 업체등록 화면 진입
3. 00001 (주)믹스비즈 조회 확인
4. [신규] 클릭
5. 회사코드 00002 + 테스트/실제 제2법인 정보 입력
6. 저장
7. 회사 목록에 00001/00002 표시 확인
8. 두 회사를 번갈아 선택하여 각각 정보가 조회되는지 확인

주의:
- 00002 저장은 실제 DB INSERT이므로, 실제 제2법인 정보를 넣어도 되는 시점에 실행하십시오.
- password hash 개선, user-company 권한, tax 구조는 이번 Slice 범위가 아닙니다.
