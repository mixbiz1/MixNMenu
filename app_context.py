class AppContext:
    """
    MXMN 프로그램 전체에서 공유하는 현재 실행 Context.

    관리 대상
    ----------
    1. 현재 로그인 사용자
    2. 현재 업무 회사

    향후 확장 가능 항목
    ----------
    - 사용자 권한
    - 사업장
    - 부서
    - 세션 정보
    """

    def __init__(self):
        self._user_id = None
        self._user_name = None
        self._access_token = None
        self._is_admin = False
        self._permissions = {}

        self._company_code = None
        self._company_name = None

    # ========================================================
    # 사용자 Context
    # ========================================================

    def set_user(self, user_id: str, user_name: str, access_token=None,
                 is_admin=False, permissions=None):
        """현재 로그인 사용자를 설정한다."""
        self._user_id = user_id
        self._user_name = user_name
        self._access_token = access_token
        self._is_admin = bool(is_admin)
        self._permissions = permissions or {}

    def clear_user(self):
        """현재 로그인 사용자 정보를 초기화한다."""
        self._user_id = None
        self._user_name = None
        self._access_token = None
        self._is_admin = False
        self._permissions = {}

    @property
    def user_id(self):
        return self._user_id

    @property
    def user_name(self):
        return self._user_name

    @property
    def has_user(self):
        return self._user_id is not None

    @property
    def access_token(self):
        return self._access_token

    @property
    def is_admin(self):
        return self._is_admin

    def can(self, menu_code: str, action: str = "read") -> bool:
        if self._is_admin:
            return True
        return bool(self._permissions.get(menu_code, {}).get(f"can_{action}", False))

    # ========================================================
    # 회사 Context
    # ========================================================

    def set_company(self, company_code: str, company_name: str):
        """현재 업무 회사를 설정한다."""
        self._company_code = company_code
        self._company_name = company_name

    def clear_company(self):
        """현재 업무 회사 정보를 초기화한다."""
        self._company_code = None
        self._company_name = None

    @property
    def company_code(self):
        return self._company_code

    @property
    def company_name(self):
        return self._company_name

    @property
    def has_company(self):
        return self._company_code is not None

    # ========================================================
    # 전체 Context 초기화
    # ========================================================

    def clear(self):
        """사용자와 회사 Context를 모두 초기화한다."""
        self.clear_user()
        self.clear_company()

    # ========================================================
    # 화면 표시용 문자열
    # ========================================================

    @property
    def company_display(self):
        if not self.has_company:
            return "회사: 미선택"

        return (
            f"회사: {self.company_code} "
            f"{self.company_name}"
        )

    @property
    def user_display(self):
        if not self.has_user:
            return "사용자: 미로그인"

        return f"사용자: {self.user_name}"

    @property
    def session_display(self):
        return (
            f"{self.company_display}"
            f"   |   "
            f"{self.user_display}"
        )


# ============================================================
# MXMN 프로그램 전체에서 공유하는 단일 Context 객체
# ============================================================

app_context = AppContext()
