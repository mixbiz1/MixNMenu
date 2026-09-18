from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
import hashlib
import hmac
import os
import secrets
from typing import Optional

import httpx as external_httpx

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db, engine, Base, SessionLocal
from expense_code_defaults import STANDARD_EXPENSE_TREE
from permissions import (
    MENU_CODES, company_code_from_path, issue_token, permission_for_request, verify_token,
)
from purchase_service import (
    calculate_purchase_line, summarize_purchase, validate_box_qty, validate_client_amounts,
)
from trade_common import (
    allocate_document_no, apply_status_transition, ensure_draft, ensure_period_open,
    tax_snapshot, validate_leaf_input_expense,
)
import models


# =============================================================================
# Database / FastAPI
# =============================================================================

# 데이터베이스 테이블 자동 생성
# 기존 테이블은 변경하지 않음
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MXMN ERP API",
    version="1.1.0",
)


# =============================================================================
# Login Schema
# =============================================================================

class LoginRequest(BaseModel):
    user_id: str
    password: str


class LoginResponse(BaseModel):
    status: str
    message: str
    user_name: str
    access_token: str
    is_admin: bool
    permissions: dict


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=4, max_length=100)


class UserCreateRequest(BaseModel):
    user_id: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    user_name: str = Field(min_length=1, max_length=50)
    initial_password: str = Field(min_length=4, max_length=100)
    use_yn: bool = True


class UserUpdateRequest(BaseModel):
    user_name: str = Field(min_length=1, max_length=50)
    new_password: Optional[str] = Field(default=None, min_length=4, max_length=100)


class UserPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=4, max_length=100)


class UserStatusRequest(BaseModel):
    use_yn: bool
    actor_user_id: Optional[str] = None  # 구버전 Client 호환용, 보안판단에는 사용하지 않음


class MenuPermissionRequest(BaseModel):
    menu_code: str
    can_read: bool = False
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False


class UserAccessRequest(BaseModel):
    company_codes: list[str]
    menu_permissions: list[MenuPermissionRequest]


PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260000


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), PASSWORD_ITERATIONS
    ).hex()
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    """신규 Hash와 기존 평문 비밀번호를 함께 검증하여 무중단 전환한다."""
    if not stored.startswith(f"{PASSWORD_SCHEME}$"):
        return hmac.compare_digest(stored, password)
    try:
        _, iterations, salt, expected = stored.split("$", 3)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations)
        ).hex()
        return hmac.compare_digest(expected, actual)
    except (TypeError, ValueError):
        return False


def _user_response(user):
    """비밀번호를 제외한 사용자 관리용 응답만 반환한다."""
    return {
        "user_id": user.user_id,
        "user_name": user.user_name,
        "use_yn": bool(user.use_yn),
        "is_admin": bool(user.is_admin),
        "created_at": user.created_at,
    }


def _permission_dict(db: Session, user_id: str):
    rows = db.query(models.UserMenuPermission).filter(
        models.UserMenuPermission.user_id == user_id
    ).all()
    return {
        row.menu_code: {
            "can_read": bool(row.can_read), "can_create": bool(row.can_create),
            "can_update": bool(row.can_update), "can_delete": bool(row.can_delete),
        }
        for row in rows
    }


@app.middleware("http")
async def enforce_api_permissions(request: Request, call_next):
    """모든 v1 API에 인증·회사·메뉴 CRUD 권한을 공통 적용한다."""
    path = request.url.path
    if not path.startswith("/api/v1/") or path == "/api/v1/auth/login":
        return await call_next(request)
    authorization = request.headers.get("Authorization", "")
    token = authorization[7:] if authorization.startswith("Bearer ") else ""
    user_id = verify_token(token)
    if not user_id:
        return JSONResponse(status_code=401, content={"detail": "로그인이 만료되었거나 인증정보가 없습니다."})

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.user_id == user_id).first()
        if not user or not user.use_yn:
            return JSONResponse(status_code=403, content={"detail": "사용할 수 없는 계정입니다."})
        request.state.user_id = user.user_id
        request.state.is_admin = bool(user.is_admin)

        comp_code = company_code_from_path(path)
        if comp_code and not user.is_admin:
            allowed = db.query(models.UserCompanyAccess).filter(
                models.UserCompanyAccess.user_id == user.user_id,
                models.UserCompanyAccess.comp_code == comp_code,
            ).first()
            if not allowed:
                return JSONResponse(status_code=403, content={"detail": "해당 업무회사에 접근할 권한이 없습니다."})

        rule = permission_for_request(request.method, path)
        # 회사 목록은 로그인 사용자의 선택목록이므로 별도 메뉴권한 없이 허용한다.
        if rule and not (request.method == "GET" and path == "/api/v1/companies") and not user.is_admin:
            permission = db.query(models.UserMenuPermission).filter(
                models.UserMenuPermission.user_id == user.user_id,
                models.UserMenuPermission.menu_code == rule.menu_code,
            ).first()
            if not permission or not bool(getattr(permission, f"can_{rule.action}")):
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"{rule.menu_code} 메뉴의 {rule.action} 권한이 없습니다."},
                )
    finally:
        db.close()
    return await call_next(request)


@app.get("/api/v1/users")
def get_users(
    include_inactive: bool = True,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.User)
    if not include_inactive:
        query = query.filter(models.User.use_yn == True)
    keyword = (search or "").strip()
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            (models.User.user_id.like(pattern)) | (models.User.user_name.like(pattern))
        )
    return [_user_response(row) for row in query.order_by(models.User.user_id).all()]


@app.post("/api/v1/users", status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreateRequest, db: Session = Depends(get_db)):
    user_id = data.user_id.strip()
    user_name = data.user_name.strip()
    if not user_name:
        raise HTTPException(status_code=400, detail="사용자명을 입력하세요.")
    if db.query(models.User).filter(models.User.user_id == user_id).first():
        raise HTTPException(status_code=409, detail="이미 등록된 사용자 ID입니다.")
    obj = models.User(
        user_id=user_id,
        user_name=user_name,
        password_hash=_hash_password(data.initial_password),
        use_yn=data.use_yn,
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="이미 등록된 사용자 ID입니다.")
    db.refresh(obj)
    return _user_response(obj)


@app.put("/api/v1/users/{user_id}")
def update_user(user_id: str, data: UserUpdateRequest, db: Session = Depends(get_db)):
    obj = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="등록되지 않은 사용자입니다.")
    name = data.user_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="사용자명을 입력하세요.")
    obj.user_name = name
    if data.new_password:
        obj.password_hash = _hash_password(data.new_password)
    db.commit()
    db.refresh(obj)
    return _user_response(obj)


@app.put("/api/v1/users/{user_id}/reset-password")
def reset_user_password(
    user_id: str, data: UserPasswordResetRequest, db: Session = Depends(get_db)
):
    obj = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="등록되지 않은 사용자입니다.")
    obj.password_hash = _hash_password(data.new_password)
    db.commit()
    return {"message": "사용자 비밀번호가 초기화되었습니다."}


@app.put("/api/v1/users/{user_id}/status")
def update_user_status(
    user_id: str, data: UserStatusRequest, request: Request, db: Session = Depends(get_db)
):
    obj = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="등록되지 않은 사용자입니다.")
    if not data.use_yn and user_id == request.state.user_id:
        raise HTTPException(status_code=400, detail="현재 로그인 사용자는 자기 계정을 사용중지할 수 없습니다.")
    if not data.use_yn and obj.is_admin:
        active_admins = db.query(models.User).filter(
            models.User.is_admin == True, models.User.use_yn == True
        ).count()
        if active_admins <= 1:
            raise HTTPException(status_code=400, detail="마지막 관리자는 사용중지할 수 없습니다.")
    obj.use_yn = data.use_yn
    db.commit()
    db.refresh(obj)
    return _user_response(obj)


@app.put("/api/v1/users/{user_id}/password")
def change_password(user_id: str, data: PasswordChangeRequest, request: Request, db: Session = Depends(get_db)):
    if user_id != request.state.user_id:
        raise HTTPException(status_code=403, detail="자기 계정의 비밀번호만 변경할 수 있습니다.")
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user or not user.use_yn:
        raise HTTPException(status_code=404, detail="사용 가능한 사용자 계정이 없습니다.")
    if not _verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 일치하지 않습니다.")
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="새 비밀번호는 현재 비밀번호와 다르게 입력해 주세요.")
    user.password_hash = _hash_password(data.new_password)
    db.commit()
    return {"message": "비밀번호가 변경되었습니다."}


@app.get("/api/v1/users/{user_id}/access")
def get_user_access(user_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="등록되지 않은 사용자입니다.")
    companies = db.query(models.Company).order_by(models.Company.comp_code).all()
    allowed = {row.comp_code for row in db.query(models.UserCompanyAccess).filter(
        models.UserCompanyAccess.user_id == user_id
    ).all()}
    menus = db.query(models.MenuMaster).filter(models.MenuMaster.use_yn == True).order_by(
        models.MenuMaster.sort_order, models.MenuMaster.menu_code
    ).all()
    assigned = _permission_dict(db, user_id)
    return {
        "user_id": user.user_id,
        "user_name": user.user_name,
        "is_admin": bool(user.is_admin),
        "companies": [
            {"comp_code": row.comp_code, "comp_name": row.comp_name,
             "allowed": bool(user.is_admin or row.comp_code in allowed)}
            for row in companies
        ],
        "menus": [
            {"menu_code": row.menu_code, "menu_name": row.menu_name,
             "menu_group": row.menu_group,
             **({"can_read": True, "can_create": True, "can_update": True, "can_delete": True}
                if user.is_admin else assigned.get(row.menu_code, {
                    "can_read": False, "can_create": False, "can_update": False, "can_delete": False
                }))}
            for row in menus
        ],
    }


@app.put("/api/v1/users/{user_id}/access")
def replace_user_access(user_id: str, data: UserAccessRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="등록되지 않은 사용자입니다.")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="관리자는 전체 회사·메뉴 권한이 고정되어 변경할 수 없습니다.")

    company_codes = list(dict.fromkeys(data.company_codes))
    menu_codes = [row.menu_code for row in data.menu_permissions]
    if len(menu_codes) != len(set(menu_codes)):
        raise HTTPException(status_code=400, detail="중복된 메뉴 권한이 있습니다.")
    valid_companies = {row[0] for row in db.query(models.Company.comp_code).filter(
        models.Company.comp_code.in_(company_codes)
    ).all()} if company_codes else set()
    if valid_companies != set(company_codes):
        raise HTTPException(status_code=400, detail="등록되지 않은 회사코드가 포함되어 있습니다.")
    if not set(menu_codes).issubset(MENU_CODES):
        raise HTTPException(status_code=400, detail="등록되지 않은 메뉴코드가 포함되어 있습니다.")
    if user.use_yn and not company_codes:
        raise HTTPException(status_code=400, detail="사용 중인 일반 사용자는 업무회사를 한 곳 이상 지정해야 합니다.")

    try:
        db.query(models.UserCompanyAccess).filter(
            models.UserCompanyAccess.user_id == user_id
        ).delete(synchronize_session=False)
        db.query(models.UserMenuPermission).filter(
            models.UserMenuPermission.user_id == user_id
        ).delete(synchronize_session=False)
        db.add_all([models.UserCompanyAccess(user_id=user_id, comp_code=code) for code in company_codes])
        db.add_all([
            models.UserMenuPermission(user_id=user_id, menu_code=row.menu_code,
                can_read=row.can_read, can_create=row.can_create,
                can_update=row.can_update, can_delete=row.can_delete)
            for row in data.menu_permissions
        ])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="회사 또는 메뉴 권한의 PK/FK·중복 조건을 확인하세요.")
    return get_user_access(user_id, db)


# =============================================================================
# Company Schema
# =============================================================================

class CompanySchema(BaseModel):
    """tb_company와 1:1로 사용하는 회사 정보 Schema."""

    model_config = ConfigDict(from_attributes=True)

    comp_code: str
    comp_name: str
    comp_name_en: Optional[str] = None
    biz_no: str
    meatwatch_bplc_no: Optional[str] = None
    ceo_name: Optional[str] = None
    zip_code: Optional[str] = None
    address: Optional[str] = None
    uptae: Optional[str] = None
    upjong: Optional[str] = None
    lic_no: Optional[str] = None
    bank1: Optional[str] = None
    bank2: Optional[str] = None
    tel: Optional[str] = None
    fax: Optional[str] = None
    pcs: Optional[str] = None
    email: Optional[str] = None
    consult: Optional[str] = None


# =============================================================================
# Root / DB Check
# =============================================================================

@app.get("/")
def read_root():
    return {
        "message": "Welcome to MXMN ERP API Server!"
    }


@app.get("/api/db-check")
def check_db_status(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT @@VERSION")).scalar()

        return {
            "status": "success",
            "db_response": "Connected to MS SQL Server",
            "version": (
                str(result)[:60] + "..."
                if result
                else "Unknown"
            ),
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


# =============================================================================
# Authentication API
# =============================================================================

@app.post(
    "/api/v1/auth/login",
    response_model=LoginResponse,
)
def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(models.User)
        .filter(models.User.user_id == req.user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자 ID입니다.",
        )

    if not user.use_yn:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )

    if not _verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="암호가 일치하지 않습니다.",
        )

    # 기존 평문 저장 계정은 정상 로그인 시 안전한 Hash로 자동 전환한다.
    if not user.password_hash.startswith(f"{PASSWORD_SCHEME}$"):
        user.password_hash = _hash_password(req.password)
        db.commit()

    return LoginResponse(
        status="success",
        message="로그인 성공",
        user_name=user.user_name,
        access_token=issue_token(user.user_id),
        is_admin=bool(user.is_admin),
        permissions=_permission_dict(db, user.user_id),
    )


# =============================================================================
# Company API
# Multi Company Vertical Slice
# =============================================================================

@app.get(
    "/api/v1/companies",
    response_model=list[CompanySchema],
)
def get_companies(
    request: Request,
    db: Session = Depends(get_db),
):
    """등록된 모든 회사를 회사코드 순으로 조회한다."""

    query = db.query(models.Company)
    if not request.state.is_admin:
        query = query.join(
            models.UserCompanyAccess,
            models.UserCompanyAccess.comp_code == models.Company.comp_code,
        ).filter(models.UserCompanyAccess.user_id == request.state.user_id)
    return query.order_by(models.Company.comp_code).all()


@app.get(
    "/api/v1/companies/{comp_code}",
    response_model=CompanySchema,
)
def get_company_by_code(
    comp_code: str,
    db: Session = Depends(get_db),
):
    """회사코드로 회사 한 곳을 조회한다."""

    company = (
        db.query(models.Company)
        .filter(models.Company.comp_code == comp_code)
        .first()
    )

    if not company:
        raise HTTPException(
            status_code=404,
            detail="등록되지 않은 회사코드입니다.",
        )

    return company


@app.post(
    "/api/v1/companies",
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    data: CompanySchema,
    db: Session = Depends(get_db),
):
    """
    새 회사를 등록한다.
    이미 존재하는 회사코드는 신규등록할 수 없다.
    """

    existing = (
        db.query(models.Company)
        .filter(models.Company.comp_code == data.comp_code)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="이미 등록된 회사코드입니다.",
        )

    company = models.Company(
        **data.model_dump()
    )

    db.add(company)

    try:
        db.commit()
        db.refresh(company)

    except Exception:
        db.rollback()
        raise

    return {
        "status": "success",
        "message": "회사 정보가 등록되었습니다.",
    }


@app.put(
    "/api/v1/companies/{comp_code}",
)
def update_company(
    comp_code: str,
    data: CompanySchema,
    db: Session = Depends(get_db),
):
    """
    기존 회사 정보를 수정한다.
    PK인 회사코드는 화면에서 변경하지 않는다.
    """

    company = (
        db.query(models.Company)
        .filter(models.Company.comp_code == comp_code)
        .first()
    )

    if not company:
        raise HTTPException(
            status_code=404,
            detail="등록되지 않은 회사코드입니다.",
        )

    if data.comp_code != comp_code:
        raise HTTPException(
            status_code=400,
            detail="회사코드는 수정할 수 없습니다.",
        )

    for key, value in data.model_dump(
        exclude={"comp_code"}
    ).items():
        setattr(company, key, value)

    try:
        db.commit()
        db.refresh(company)

    except Exception:
        db.rollback()
        raise

    return {
        "status": "success",
        "message": "회사 정보가 수정되었습니다.",
    }


# 기존 호출 호환용
# 신규 UI는 /api/v1/companies API 사용
@app.get(
    "/api/v1/company",
    response_model=CompanySchema,
)
def get_legacy_company(
    db: Session = Depends(get_db),
):
    company = (
        db.query(models.Company)
        .order_by(models.Company.comp_code)
        .first()
    )

    if not company:
        raise HTTPException(
            status_code=404,
            detail="등록된 회사가 없습니다.",
        )

    return company


# =============================================================================
# Common Code API
# =============================================================================

class CodeGroupSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    group_code: str
    group_name: str
    description: Optional[str] = None
    sort_order: int = 0
    sort_direction: str = "ASC"
    system_yn: bool = False
    use_yn: bool = True


class CodeGroupResponse(CodeGroupSchema):
    code_group_id: int


class CodeValueSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    code_name: str
    description: Optional[str] = None
    sort_order: int = 0
    extra_value1: Optional[str] = None
    extra_value2: Optional[str] = None
    use_yn: bool = True


class CodeValueResponse(CodeValueSchema):
    code_value_id: int
    code_group_id: int


def _get_code_group_or_404(group_code: str, db: Session):
    group = (
        db.query(models.CodeGroup)
        .filter(models.CodeGroup.group_code == group_code)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="등록되지 않은 코드그룹입니다.")
    return group


def _next_group_code(db: Session, prefix: str = "CG") -> str:
    prefix = (prefix or "CG").strip().upper()
    if not prefix.isalpha() or len(prefix) > 5:
        raise HTTPException(status_code=400, detail="코드 접두사는 영문 1~5자리여야 합니다.")
    numbers = []
    for (code,) in db.query(models.CodeGroup.group_code).all():
        suffix = code[len(prefix):] if code and code.upper().startswith(prefix) else ""
        if suffix.isdigit():
            numbers.append(int(suffix))
    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def _next_value_code(group_id: int, db: Session) -> str:
    numbers = []
    rows = db.query(models.CodeValue.code).filter(
        models.CodeValue.code_group_id == group_id
    ).all()
    for (code,) in rows:
        if code and code.isdigit():
            numbers.append(int(code))
    return f"{max(numbers, default=0) + 1:03d}"


def _sort_direction(value: str) -> str:
    direction = (value or "ASC").strip().upper()
    if direction not in {"ASC", "DESC"}:
        raise HTTPException(status_code=400, detail="정렬방식은 오름차순 또는 내림차순이어야 합니다.")
    return direction


@app.get("/api/v1/code-groups", response_model=list[CodeGroupResponse])
def get_code_groups(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.CodeGroup)
    if not include_inactive:
        query = query.filter(models.CodeGroup.use_yn == True)
    return query.order_by(models.CodeGroup.sort_order, models.CodeGroup.group_code).all()


@app.get("/api/v1/code-groups/next-code")
def get_next_code_group_code(prefix: str = "CG", db: Session = Depends(get_db)):
    return {"group_code": _next_group_code(db, prefix)}


@app.post(
    "/api/v1/code-groups",
    response_model=CodeGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_code_group(data: CodeGroupSchema, db: Session = Depends(get_db)):
    group_code = data.group_code.strip().upper() or _next_group_code(db)
    if db.query(models.CodeGroup).filter(models.CodeGroup.group_code == group_code).first():
        raise HTTPException(status_code=409, detail="이미 등록된 코드그룹입니다.")
    values = data.model_dump(exclude={"group_code", "sort_direction"})
    obj = models.CodeGroup(
        **values,
        group_code=group_code,
        sort_direction=_sort_direction(data.sort_direction),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@app.put("/api/v1/code-groups/{group_code}", response_model=CodeGroupResponse)
def update_code_group(
    group_code: str,
    data: CodeGroupSchema,
    db: Session = Depends(get_db),
):
    obj = _get_code_group_or_404(group_code, db)
    if data.group_code.strip().upper() != obj.group_code:
        raise HTTPException(status_code=400, detail="저장된 코드그룹 코드는 변경할 수 없습니다.")
    values = data.model_dump(exclude={"group_code", "sort_direction"})
    values["sort_direction"] = _sort_direction(data.sort_direction)
    for key, value in values.items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@app.delete("/api/v1/code-groups/{group_code}")
def deactivate_code_group(group_code: str, db: Session = Depends(get_db)):
    """참조 데이터 보호를 위해 물리삭제 대신 그룹과 상세코드를 사용중지한다."""
    obj = _get_code_group_or_404(group_code, db)
    obj.use_yn = False
    db.query(models.CodeValue).filter(
        models.CodeValue.code_group_id == obj.code_group_id
    ).update({models.CodeValue.use_yn: False}, synchronize_session=False)
    db.commit()
    return {"message": "코드그룹과 소속 상세코드가 사용중지되었습니다."}


@app.get(
    "/api/v1/code-groups/{group_code}/values/next-code",
)
def get_next_code_value_code(group_code: str, db: Session = Depends(get_db)):
    group = _get_code_group_or_404(group_code, db)
    return {"code": _next_value_code(group.code_group_id, db)}


@app.get(
    "/api/v1/code-groups/{group_code}/values",
    response_model=list[CodeValueResponse],
)
def get_code_values(
    group_code: str,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    group = _get_code_group_or_404(group_code, db)
    query = db.query(models.CodeValue).filter(
        models.CodeValue.code_group_id == group.code_group_id
    )
    if not include_inactive:
        query = query.filter(models.CodeValue.use_yn == True)
    return query.order_by(models.CodeValue.code.asc()).all()


@app.post(
    "/api/v1/code-groups/{group_code}/values",
    response_model=CodeValueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_code_value(
    group_code: str,
    data: CodeValueSchema,
    db: Session = Depends(get_db),
):
    group = _get_code_group_or_404(group_code, db)
    code = data.code.strip().upper() or _next_value_code(group.code_group_id, db)
    duplicate = (
        db.query(models.CodeValue)
        .filter(
            models.CodeValue.code_group_id == group.code_group_id,
            models.CodeValue.code == code,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="이 그룹에 동일한 코드가 이미 있습니다.")
    obj = models.CodeValue(
        **data.model_dump(exclude={"code"}),
        code_group_id=group.code_group_id,
        code=code,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@app.put(
    "/api/v1/code-groups/{group_code}/values/{code_value_id}",
    response_model=CodeValueResponse,
)
def update_code_value(
    group_code: str,
    code_value_id: int,
    data: CodeValueSchema,
    db: Session = Depends(get_db),
):
    group = _get_code_group_or_404(group_code, db)
    obj = (
        db.query(models.CodeValue)
        .filter(
            models.CodeValue.code_value_id == code_value_id,
            models.CodeValue.code_group_id == group.code_group_id,
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="등록되지 않은 공통코드입니다.")

    code = data.code.strip().upper()
    duplicate = (
        db.query(models.CodeValue)
        .filter(
            models.CodeValue.code_group_id == group.code_group_id,
            models.CodeValue.code == code,
            models.CodeValue.code_value_id != code_value_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="이 그룹에 동일한 코드가 이미 있습니다.")

    for key, value in data.model_dump(exclude={"code"}).items():
        setattr(obj, key, value)
    obj.code = code
    db.commit()
    db.refresh(obj)
    return obj


@app.delete("/api/v1/code-groups/{group_code}/values/{code_value_id}")
def deactivate_code_value(
    group_code: str,
    code_value_id: int,
    db: Session = Depends(get_db),
):
    """향후 상품 참조를 보존할 수 있도록 상세코드를 물리삭제하지 않는다."""
    group = _get_code_group_or_404(group_code, db)
    obj = db.query(models.CodeValue).filter(
        models.CodeValue.code_value_id == code_value_id,
        models.CodeValue.code_group_id == group.code_group_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="등록되지 않은 공통코드입니다.")
    obj.use_yn = False
    db.commit()
    return {"message": "상세코드가 사용중지되었습니다."}


# =============================================================================
# Expense Code Master API
# =============================================================================

EXPENSE_STATEMENT_SECTIONS = {
    "SALES",
    "COST_OF_SALES",
    "SGA",
    "NON_OPERATING_INCOME",
    "NON_OPERATING_EXPENSE",
    "GROSS_PROFIT",
    "OPERATING_PROFIT",
    "PRETAX_PROFIT",
    "INCOME_TAX",
    "NET_PROFIT",
}
EXPENSE_NODE_TYPES = {"GROUP", "INPUT"}


class ExpenseCodeSchema(BaseModel):
    expense_code: str
    expense_name: str
    parent_expense_id: Optional[int] = None
    statement_section: str
    node_type: str = "INPUT"
    description: Optional[str] = None
    sort_order: int = 0
    use_yn: bool = True


def _next_expense_code(db: Session) -> str:
    numbers = []
    for (code,) in db.query(models.ExpenseCode.expense_code).all():
        if code and code.startswith("E") and code[1:].isdigit():
            numbers.append(int(code[1:]))
    return f"E{max(numbers, default=0) + 1:05d}"


def _expense_parent_values(parent_id: Optional[int], section: str, db: Session):
    normalized = (section or "").strip().upper()
    if parent_id is None:
        raise HTTPException(status_code=400, detail="최상위 손익구조는 시스템이 관리합니다.")
    parent = db.query(models.ExpenseCode).filter(
        models.ExpenseCode.expense_id == parent_id
    ).first()
    if not parent:
        raise HTTPException(status_code=400, detail="상위 경비코드가 없습니다.")
    if not parent.use_yn:
        raise HTTPException(status_code=400, detail="사용중지된 경비코드 아래에는 추가할 수 없습니다.")
    if parent.node_type == "CALCULATED":
        raise HTTPException(status_code=400, detail="자동계산 항목 아래에는 하위항목을 추가할 수 없습니다.")
    if parent.expense_level >= 4:
        raise HTTPException(status_code=400, detail="경비코드는 4단계까지만 생성할 수 있습니다.")
    return parent.expense_level + 1, parent.statement_section


def _seed_standard_expense_codes(db: Session, replace=False):
    existing = db.query(models.ExpenseCode).count()
    if existing and not replace:
        return False
    if existing:
        rows = db.query(models.ExpenseCode).order_by(
            models.ExpenseCode.expense_level.desc()
        ).all()
        for row in rows:
            db.delete(row)
        db.flush()
    ids = {}
    for index, row in enumerate(STANDARD_EXPENSE_TREE, start=1):
        key, parent_key, name, section, node_type, formula, order, description = row
        parent_id = ids.get(parent_key)
        level = 1
        if parent_id:
            parent = db.query(models.ExpenseCode).filter(
                models.ExpenseCode.expense_id == parent_id
            ).one()
            level = parent.expense_level + 1
        obj = models.ExpenseCode(
            expense_code=f"E{index:05d}", expense_name=name,
            parent_expense_id=parent_id, expense_level=level,
            statement_section=section, node_type=node_type,
            formula_code=formula, system_yn=(level == 1),
            description=description, sort_order=order, use_yn=True,
        )
        db.add(obj)
        db.flush()
        ids[key] = obj.expense_id
    db.commit()
    return True


@app.post("/api/v1/expense-codes/initialize-standard")
def initialize_standard_expense_codes(replace: bool = False, db: Session = Depends(get_db)):
    try:
        changed = _seed_standard_expense_codes(db, replace=replace)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="거래에 연결된 코드가 있어 표준구조로 재구성할 수 없습니다.")
    return {"changed": changed, "message": "표준 손익구조가 생성되었습니다." if changed else "기존 구조를 유지했습니다."}


@app.get("/api/v1/expense-codes/next-code")
def get_next_expense_code(db: Session = Depends(get_db)):
    return {"expense_code": _next_expense_code(db)}


@app.get("/api/v1/expense-codes")
def get_expense_codes(include_inactive: bool = False, db: Session = Depends(get_db)):
    if db.query(models.ExpenseCode).count() == 0:
        _seed_standard_expense_codes(db)
    query = db.query(models.ExpenseCode)
    if not include_inactive:
        query = query.filter(models.ExpenseCode.use_yn == True)
    return query.order_by(
        models.ExpenseCode.expense_level,
        models.ExpenseCode.sort_order,
        models.ExpenseCode.expense_code,
    ).all()


@app.post("/api/v1/expense-codes", status_code=status.HTTP_201_CREATED)
def create_expense_code(data: ExpenseCodeSchema, db: Session = Depends(get_db)):
    code = data.expense_code.strip().upper() or _next_expense_code(db)
    if db.query(models.ExpenseCode).filter(
        models.ExpenseCode.expense_code == code
    ).first():
        raise HTTPException(status_code=409, detail="이미 등록된 경비코드입니다.")
    level, section = _expense_parent_values(
        data.parent_expense_id, data.statement_section, db
    )
    node_type = data.node_type.strip().upper()
    if node_type not in EXPENSE_NODE_TYPES:
        raise HTTPException(status_code=400, detail="항목성격은 그룹 또는 실제입력만 선택할 수 있습니다.")
    obj = models.ExpenseCode(
        **data.model_dump(exclude={"expense_code", "statement_section", "node_type"}),
        expense_code=code,
        expense_level=level,
        statement_section=section,
        node_type=node_type,
        system_yn=False,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@app.put("/api/v1/expense-codes/{expense_id}")
def update_expense_code(
    expense_id: int, data: ExpenseCodeSchema, db: Session = Depends(get_db)
):
    obj = db.query(models.ExpenseCode).filter(
        models.ExpenseCode.expense_id == expense_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="등록되지 않은 경비코드입니다.")
    if obj.system_yn:
        raise HTTPException(status_code=400, detail="시스템 표준항목은 수정할 수 없습니다.")
    if data.expense_code.strip().upper() != obj.expense_code:
        raise HTTPException(status_code=400, detail="저장된 경비코드는 변경할 수 없습니다.")
    if data.parent_expense_id == expense_id:
        raise HTTPException(status_code=400, detail="자기 자신을 상위코드로 지정할 수 없습니다.")
    if data.parent_expense_id != obj.parent_expense_id:
        has_children = db.query(models.ExpenseCode).filter(
            models.ExpenseCode.parent_expense_id == expense_id
        ).first()
        if has_children:
            raise HTTPException(
                status_code=400,
                detail="하위코드가 있는 경비코드는 상위코드를 변경할 수 없습니다.",
            )
    level, section = _expense_parent_values(
        data.parent_expense_id, data.statement_section, db
    )
    node_type = data.node_type.strip().upper()
    if node_type not in EXPENSE_NODE_TYPES:
        raise HTTPException(status_code=400, detail="항목성격은 그룹 또는 실제입력만 선택할 수 있습니다.")
    section_changed = obj.statement_section != section
    values = data.model_dump(exclude={"expense_code", "statement_section", "node_type"})
    values["expense_level"] = level
    values["statement_section"] = section
    values["node_type"] = node_type
    for key, value in values.items():
        setattr(obj, key, value)
    if section_changed:
        pending = [expense_id]
        descendants = []
        while pending:
            current = pending.pop()
            children = db.query(models.ExpenseCode.expense_id).filter(
                models.ExpenseCode.parent_expense_id == current
            ).all()
            child_ids = [row[0] for row in children if row[0] not in descendants]
            descendants.extend(child_ids)
            pending.extend(child_ids)
        if descendants:
            db.query(models.ExpenseCode).filter(
                models.ExpenseCode.expense_id.in_(descendants)
            ).update(
                {models.ExpenseCode.statement_section: section},
                synchronize_session=False,
            )
    db.commit()
    db.refresh(obj)
    return obj


@app.delete("/api/v1/expense-codes/{expense_id}")
def delete_expense_code(expense_id: int, db: Session = Depends(get_db)):
    target = db.query(models.ExpenseCode).filter(
        models.ExpenseCode.expense_id == expense_id
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="등록되지 않은 경비코드입니다.")
    pending = [expense_id]
    affected = []
    while pending:
        current = pending.pop()
        affected.append(current)
        children = db.query(models.ExpenseCode.expense_id).filter(
            models.ExpenseCode.parent_expense_id == current
        ).all()
        pending.extend(row[0] for row in children if row[0] not in affected)
    protected = db.query(models.ExpenseCode).filter(
        models.ExpenseCode.expense_id.in_(affected), models.ExpenseCode.system_yn == True
    ).first()
    if protected:
        raise HTTPException(status_code=400, detail="시스템 표준항목은 삭제할 수 없습니다.")
    try:
        for row in db.query(models.ExpenseCode).filter(
            models.ExpenseCode.expense_id.in_(affected)
        ).order_by(models.ExpenseCode.expense_level.desc()).all():
            db.delete(row)
        db.commit()
        return {"mode": "deleted", "message": "사용 이력이 없는 항목을 삭제했습니다."}
    except IntegrityError:
        db.rollback()
        db.query(models.ExpenseCode).filter(
            models.ExpenseCode.expense_id.in_(affected)
        ).update({models.ExpenseCode.use_yn: False}, synchronize_session=False)
        db.commit()
        return {"mode": "deactivated", "message": "연결 자료가 있어 삭제하지 않고 사용중지했습니다."}


# =============================================================================
# Product Category / Product Master API
# =============================================================================

class ProductCategorySchema(BaseModel):
    category_code: str
    category_name: str
    parent_category_id: Optional[int] = None
    description: Optional[str] = None
    sort_order: int = 0
    use_yn: bool = True


class ProductSchema(BaseModel):
    product_code: str
    product_name: str
    category_id: Optional[int] = None
    specification: Optional[str] = None
    meat_regn_code: Optional[str] = None
    meat_regn_name: Optional[str] = None
    tax_type: str = "2"
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    expiry_rule: str = "AUTO"
    shelf_life_days: Optional[int] = Field(default=None, ge=1)
    memo: Optional[str] = None
    use_yn: bool = True
    code_value_ids: list[int] = Field(default_factory=list)


def _next_category_code(db: Session):
    numbers = []
    for (code,) in db.query(models.ProductCategory.category_code).all():
        if code and code.startswith("CAT") and code[3:].isdigit():
            numbers.append(int(code[3:]))
    return f"CAT{max(numbers, default=0) + 1:05d}"


def _next_product_code(db: Session):
    numbers = []
    for (code,) in db.query(models.Product.product_code).all():
        if code and code.startswith("P") and code[1:].isdigit():
            numbers.append(int(code[1:]))
    return f"P{max(numbers, default=0) + 1:05d}"


def _category_level(parent_id: Optional[int], db: Session):
    if parent_id is None:
        return 1
    parent = db.query(models.ProductCategory).filter(
        models.ProductCategory.category_id == parent_id
    ).first()
    if not parent:
        raise HTTPException(status_code=400, detail="상위 상품분류가 없습니다.")
    if parent.category_level >= 3:
        raise HTTPException(status_code=400, detail="상품분류는 대·중·소 3단계까지만 가능합니다.")
    return parent.category_level + 1


def _product_result(obj, db: Session, assignments=None):
    if assignments is None:
        assignments = db.query(
            models.ProductCodeAssignment, models.CodeGroup, models.CodeValue
        ).select_from(models.ProductCodeAssignment).join(
            models.CodeGroup,
            models.ProductCodeAssignment.code_group_id == models.CodeGroup.code_group_id,
        ).join(
            models.CodeValue,
            models.ProductCodeAssignment.code_value_id == models.CodeValue.code_value_id,
        ).filter(models.ProductCodeAssignment.product_id == obj.product_id).all()
    return {
        "product_id": obj.product_id,
        "product_code": obj.product_code,
        "product_name": obj.product_name,
        "category_id": obj.category_id,
        "specification": obj.specification,
        "meat_regn_code": obj.meat_regn_code,
        "meat_regn_name": obj.meat_regn_name,
        "tax_type": obj.tax_type,
        "unit_price": int(_ceil_won(obj.unit_price)),
        "expiry_rule": obj.expiry_rule or "AUTO",
        "shelf_life_days": obj.shelf_life_days,
        "memo": obj.memo,
        "use_yn": obj.use_yn,
        "code_value_ids": [value.code_value_id for _, _, value in assignments],
        "attributes": [
            {
                "group_code": group.group_code,
                "group_name": group.group_name,
                "code_value_id": value.code_value_id,
                "code": value.code,
                "code_name": value.code_name,
            }
            for _, group, value in assignments
        ],
    }


def _product_results(objects, db: Session):
    """상품목록의 공통코드 조합을 한 번에 조회하여 N+1 쿼리를 방지한다."""
    if not objects:
        return []
    product_ids = [obj.product_id for obj in objects]
    rows = db.query(
        models.ProductCodeAssignment, models.CodeGroup, models.CodeValue
    ).select_from(models.ProductCodeAssignment).join(
        models.CodeGroup,
        models.ProductCodeAssignment.code_group_id == models.CodeGroup.code_group_id,
    ).join(
        models.CodeValue,
        models.ProductCodeAssignment.code_value_id == models.CodeValue.code_value_id,
    ).filter(models.ProductCodeAssignment.product_id.in_(product_ids)).all()
    assignments_by_product = {product_id: [] for product_id in product_ids}
    for assignment, group, value in rows:
        assignments_by_product.setdefault(assignment.product_id, []).append(
            (assignment, group, value)
        )
    return [
        _product_result(obj, db, assignments_by_product.get(obj.product_id, []))
        for obj in objects
    ]


def _save_product_assignments(product_id: int, code_value_ids: list[int], db: Session):
    ids = list(dict.fromkeys(code_value_ids))
    values = db.query(models.CodeValue).filter(models.CodeValue.code_value_id.in_(ids)).all() if ids else []
    if len(values) != len(ids):
        raise HTTPException(status_code=400, detail="선택한 상품공통코드 중 등록되지 않은 값이 있습니다.")
    group_ids = [value.code_group_id for value in values]
    if len(group_ids) != len(set(group_ids)):
        raise HTTPException(status_code=400, detail="동일 상품분류에서는 하나의 코드만 선택할 수 있습니다.")
    db.query(models.ProductCodeAssignment).filter(
        models.ProductCodeAssignment.product_id == product_id
    ).delete(synchronize_session=False)
    for value in values:
        db.add(models.ProductCodeAssignment(
            product_id=product_id,
            code_group_id=value.code_group_id,
            code_value_id=value.code_value_id,
        ))


@app.get("/api/v1/product-categories/next-code")
def get_next_product_category_code(db: Session = Depends(get_db)):
    return {"category_code": _next_category_code(db)}


@app.get("/api/v1/product-categories")
def get_product_categories(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.ProductCategory)
    if not include_inactive:
        query = query.filter(models.ProductCategory.use_yn == True)
    return query.order_by(
        models.ProductCategory.category_level,
        models.ProductCategory.sort_order,
        models.ProductCategory.category_code,
    ).all()


@app.post("/api/v1/product-categories", status_code=status.HTTP_201_CREATED)
def create_product_category(data: ProductCategorySchema, db: Session = Depends(get_db)):
    code = data.category_code.strip().upper() or _next_category_code(db)
    if db.query(models.ProductCategory).filter(models.ProductCategory.category_code == code).first():
        raise HTTPException(status_code=409, detail="이미 등록된 상품분류 코드입니다.")
    obj = models.ProductCategory(
        **data.model_dump(exclude={"category_code"}),
        category_code=code,
        category_level=_category_level(data.parent_category_id, db),
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@app.put("/api/v1/product-categories/{category_id}")
def update_product_category(category_id: int, data: ProductCategorySchema, db: Session = Depends(get_db)):
    obj = db.query(models.ProductCategory).filter(models.ProductCategory.category_id == category_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="상품분류가 없습니다.")
    if data.category_code.strip().upper() != obj.category_code:
        raise HTTPException(status_code=400, detail="저장된 상품분류 코드는 변경할 수 없습니다.")
    if data.parent_category_id == category_id:
        raise HTTPException(status_code=400, detail="자기 자신을 상위분류로 지정할 수 없습니다.")
    if data.parent_category_id != obj.parent_category_id:
        has_children = db.query(models.ProductCategory).filter(
            models.ProductCategory.parent_category_id == category_id
        ).first()
        if has_children:
            raise HTTPException(
                status_code=400,
                detail="하위분류가 있는 분류는 상위분류를 변경할 수 없습니다.",
            )
    values = data.model_dump(exclude={"category_code"})
    values["category_level"] = _category_level(data.parent_category_id, db)
    for key, value in values.items(): setattr(obj, key, value)
    db.commit(); db.refresh(obj)
    return obj


@app.delete("/api/v1/product-categories/{category_id}")
def deactivate_product_category(category_id: int, db: Session = Depends(get_db)):
    pending = [category_id]
    affected = []
    while pending:
        current = pending.pop()
        affected.append(current)
        children = db.query(models.ProductCategory.category_id).filter(
            models.ProductCategory.parent_category_id == current
        ).all()
        pending.extend(row[0] for row in children)
    db.query(models.ProductCategory).filter(
        models.ProductCategory.category_id.in_(affected)
    ).update({models.ProductCategory.use_yn: False}, synchronize_session=False)
    db.commit()
    return {"message": "선택 분류와 하위분류가 사용중지되었습니다."}


@app.get("/api/v1/products/next-code")
def get_next_product_code(db: Session = Depends(get_db)):
    return {"product_code": _next_product_code(db)}


@app.get("/api/v1/products")
def get_products(search: str = "", category_id: Optional[int] = None,
                 include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.Product)
    if not include_inactive:
        query = query.filter(models.Product.use_yn == True)
    if category_id is not None:
        # 상위분류를 선택하면 모든 하위부위 상품을 함께 조회한다.
        category_ids = [category_id]
        pending = [category_id]
        while pending:
            current = pending.pop()
            children = db.query(models.ProductCategory.category_id).filter(
                models.ProductCategory.parent_category_id == current
            ).all()
            child_ids = [row[0] for row in children if row[0] not in category_ids]
            category_ids.extend(child_ids)
            pending.extend(child_ids)
        query = query.filter(models.Product.category_id.in_(category_ids))
    if search.strip():
        keyword = f"%{search.strip()}%"
        query = query.filter(
            (models.Product.product_code.like(keyword)) |
            (models.Product.product_name.like(keyword)) |
            (models.Product.specification.like(keyword))
        )
    objects = query.order_by(models.Product.product_code).all()
    return _product_results(objects, db)


@app.get("/api/v1/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.Product).filter(models.Product.product_id == product_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="상품이 없습니다.")
    return _product_result(obj, db)


@app.post("/api/v1/products", status_code=status.HTTP_201_CREATED)
def create_product(data: ProductSchema, db: Session = Depends(get_db)):
    if data.expiry_rule not in {"AUTO", "FROZEN_2Y", "DAYS", "NONE"}:
        raise HTTPException(status_code=400, detail="소비기한 계산규칙이 올바르지 않습니다.")
    if data.expiry_rule == "DAYS" and not data.shelf_life_days:
        raise HTTPException(status_code=400, detail="지정일수 계산은 소비기한 일수가 필요합니다.")
    code = data.product_code.strip().upper() or _next_product_code(db)
    if db.query(models.Product).filter(models.Product.product_code == code).first():
        raise HTTPException(status_code=409, detail="이미 등록된 상품코드입니다.")
    values = data.model_dump(exclude={"product_code", "code_value_ids"})
    values["unit_price"] = _ceil_won(data.unit_price)
    obj = models.Product(**values, product_code=code)
    db.add(obj); db.flush()
    _save_product_assignments(obj.product_id, data.code_value_ids, db)
    db.commit(); db.refresh(obj)
    return _product_result(obj, db)


@app.put("/api/v1/products/{product_id}")
def update_product(product_id: int, data: ProductSchema, db: Session = Depends(get_db)):
    obj = db.query(models.Product).filter(models.Product.product_id == product_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="상품이 없습니다.")
    if data.product_code.strip().upper() != obj.product_code:
        raise HTTPException(status_code=400, detail="저장된 상품코드는 변경할 수 없습니다.")
    if data.expiry_rule not in {"AUTO", "FROZEN_2Y", "DAYS", "NONE"}:
        raise HTTPException(status_code=400, detail="소비기한 계산규칙이 올바르지 않습니다.")
    if data.expiry_rule == "DAYS" and not data.shelf_life_days:
        raise HTTPException(status_code=400, detail="지정일수 계산은 소비기한 일수가 필요합니다.")
    values = data.model_dump(exclude={"product_code", "code_value_ids"})
    values["unit_price"] = _ceil_won(data.unit_price)
    for key, value in values.items():
        setattr(obj, key, value)
    _save_product_assignments(obj.product_id, data.code_value_ids, db)
    db.commit(); db.refresh(obj)
    return _product_result(obj, db)


@app.delete("/api/v1/products/{product_id}")
def deactivate_product(product_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.Product).filter(models.Product.product_id == product_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="상품이 없습니다.")
    obj.use_yn = False
    db.commit()
    return {"message": "상품이 사용중지되었습니다."}


# =============================================================================
# Warehouse Master API
#
# tb_warehouse          = 회사 간 공유하는 실제 창고
# tb_company_warehouse  = 업무회사별 사용관계
# tb_warehouse_rate     = 회사별 기본요율 적용기간 이력
# =============================================================================

class WarehouseChargeSchema(BaseModel):
    charge_name: str
    calc_unit: str
    unit_rate: float = Field(default=0, ge=0)
    sort_order: int = 0
    use_yn: bool = True


class WarehouseSchema(BaseModel):
    warehouse_code: str = ""
    warehouse_name: str
    warehouse_type: str = "BONDED"
    storage_type: str = "MIXED"
    biz_no: Optional[str] = None
    zip_code: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    web_url: Optional[str] = None
    web_user_id: Optional[str] = None
    contact_name: Optional[str] = None
    meatwatch_bplc_no: Optional[str] = None
    memo: Optional[str] = None
    use_yn: bool = True
    company_use_yn: bool = True
    valid_from: date
    valid_to: Optional[date] = None
    inbound_rate: float = Field(default=0, ge=0)
    outbound_rate: float = Field(default=0, ge=0)
    storage_rate: float = Field(default=0, ge=0)
    weighing_rate: float = Field(default=0, ge=0)
    vat_yn: bool = True
    charges: list[WarehouseChargeSchema] = Field(default_factory=list)


def _next_warehouse_code(db: Session):
    numbers = []
    for (code,) in db.query(models.Warehouse.warehouse_code).all():
        if code and code.startswith("W") and code[1:].isdigit():
            numbers.append(int(code[1:]))
    return f"W{max(numbers, default=0) + 1:04d}"


def _validate_warehouse_data(data: WarehouseSchema):
    if not data.warehouse_name.strip():
        raise HTTPException(status_code=400, detail="창고명은 필수입니다.")
    if data.warehouse_type not in {"GENERAL", "BONDED"}:
        raise HTTPException(status_code=400, detail="창고구분 값이 올바르지 않습니다.")
    if data.storage_type not in {"FROZEN", "CHILLED", "AMBIENT", "MIXED"}:
        raise HTTPException(status_code=400, detail="보관유형 값이 올바르지 않습니다.")
    if data.valid_to and data.valid_to < data.valid_from:
        raise HTTPException(status_code=400, detail="적용 종료일은 시작일보다 빠를 수 없습니다.")
    names = []
    for charge in data.charges:
        name = charge.charge_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="비용항목명을 입력해 주세요.")
        if charge.calc_unit not in {"KG", "BOX", "KG_DAY", "FIXED"}:
            raise HTTPException(status_code=400, detail=f"{name}: 계산기준이 올바르지 않습니다.")
        names.append(name.casefold())
    if len(names) != len(set(names)):
        raise HTTPException(status_code=400, detail="같은 비용항목명을 중복 등록할 수 없습니다.")


def _warehouse_result(obj, comp_code: str, db: Session):
    relation = db.query(models.CompanyWarehouse).filter(
        models.CompanyWarehouse.comp_code == comp_code,
        models.CompanyWarehouse.warehouse_id == obj.warehouse_id,
    ).first()
    rate = db.query(models.WarehouseRate).filter(
        models.WarehouseRate.comp_code == comp_code,
        models.WarehouseRate.warehouse_id == obj.warehouse_id,
    ).order_by(models.WarehouseRate.valid_from.desc()).first()
    return {
        "warehouse_id": obj.warehouse_id,
        "warehouse_code": obj.warehouse_code,
        "warehouse_name": obj.warehouse_name,
        "warehouse_type": obj.warehouse_type,
        "storage_type": obj.storage_type,
        "biz_no": obj.biz_no,
        "zip_code": obj.zip_code,
        "address": obj.address,
        "phone": obj.phone,
        "fax": obj.fax,
        "web_url": obj.web_url,
        "web_user_id": obj.web_user_id,
        "contact_name": obj.contact_name,
        "meatwatch_bplc_no": obj.meatwatch_bplc_no,
        "memo": obj.memo,
        "use_yn": bool(obj.use_yn),
        "company_use_yn": bool(relation.use_yn) if relation else False,
        "valid_from": rate.valid_from if rate else None,
        "valid_to": rate.valid_to if rate else None,
        "inbound_rate": float(rate.inbound_rate or 0) if rate else 0,
        "outbound_rate": float(rate.outbound_rate or 0) if rate else 0,
        "storage_rate": float(rate.storage_rate or 0) if rate else 0,
        "weighing_rate": float(rate.weighing_rate or 0) if rate else 0,
        "vat_yn": bool(rate.vat_yn) if rate else True,
        "charges": [
            {
                "warehouse_charge_id": charge.warehouse_charge_id,
                "charge_name": charge.charge_name,
                "calc_unit": charge.calc_unit,
                "unit_rate": float(charge.unit_rate or 0),
                "sort_order": charge.sort_order,
                "use_yn": bool(charge.use_yn),
            }
            for charge in sorted(rate.charges, key=lambda row: (row.sort_order, row.warehouse_charge_id))
        ] if rate else [],
    }


def _save_company_warehouse(obj, comp_code: str, data: WarehouseSchema, db: Session):
    company = db.query(models.Company).filter(models.Company.comp_code == comp_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="업무회사가 없습니다.")
    relation = db.query(models.CompanyWarehouse).filter(
        models.CompanyWarehouse.comp_code == comp_code,
        models.CompanyWarehouse.warehouse_id == obj.warehouse_id,
    ).first()
    if relation:
        relation.use_yn = data.company_use_yn
    else:
        db.add(models.CompanyWarehouse(
            comp_code=comp_code, warehouse_id=obj.warehouse_id, use_yn=data.company_use_yn
        ))
    rate = db.query(models.WarehouseRate).filter(
        models.WarehouseRate.comp_code == comp_code,
        models.WarehouseRate.warehouse_id == obj.warehouse_id,
        models.WarehouseRate.valid_from == data.valid_from,
    ).first()
    values = {
        "valid_to": data.valid_to,
        "inbound_rate": data.inbound_rate,
        "outbound_rate": data.outbound_rate,
        "storage_rate": data.storage_rate,
        "weighing_rate": data.weighing_rate,
        "vat_yn": data.vat_yn,
    }
    if rate:
        for key, value in values.items():
            setattr(rate, key, value)
    else:
        rate = models.WarehouseRate(
            comp_code=comp_code, warehouse_id=obj.warehouse_id,
            valid_from=data.valid_from, **values,
        )
        db.add(rate)
    db.flush()
    db.query(models.WarehouseCharge).filter(
        models.WarehouseCharge.warehouse_rate_id == rate.warehouse_rate_id
    ).delete(synchronize_session=False)
    for index, charge in enumerate(data.charges):
        db.add(models.WarehouseCharge(
            warehouse_rate_id=rate.warehouse_rate_id,
            charge_name=charge.charge_name.strip(),
            calc_unit=charge.calc_unit,
            unit_rate=charge.unit_rate,
            sort_order=charge.sort_order if charge.sort_order else index + 1,
            use_yn=charge.use_yn,
        ))


@app.get("/api/v1/warehouses/next-code")
def get_next_warehouse_code(db: Session = Depends(get_db)):
    return {"warehouse_code": _next_warehouse_code(db)}


@app.get("/api/v1/companies/{comp_code}/warehouses")
def get_warehouses(comp_code: str, search: str = "", include_inactive: bool = False,
                   db: Session = Depends(get_db)):
    query = db.query(models.Warehouse).outerjoin(
        models.CompanyWarehouse,
        (models.CompanyWarehouse.warehouse_id == models.Warehouse.warehouse_id) &
        (models.CompanyWarehouse.comp_code == comp_code),
    )
    if not include_inactive:
        query = query.filter(
            models.Warehouse.use_yn == True,
            models.CompanyWarehouse.use_yn == True,
        )
    if search.strip():
        keyword = f"%{search.strip()}%"
        query = query.filter(
            (models.Warehouse.warehouse_name.like(keyword)) |
            (models.Warehouse.warehouse_code.like(keyword)) |
            (models.Warehouse.address.like(keyword))
        )
    objects = query.order_by(models.Warehouse.warehouse_name, models.Warehouse.warehouse_code).all()
    return [_warehouse_result(obj, comp_code, db) for obj in objects]


@app.post("/api/v1/companies/{comp_code}/warehouses", status_code=status.HTTP_201_CREATED)
def create_warehouse(comp_code: str, data: WarehouseSchema, db: Session = Depends(get_db)):
    _validate_warehouse_data(data)
    code = data.warehouse_code.strip().upper() or _next_warehouse_code(db)
    if db.query(models.Warehouse).filter(models.Warehouse.warehouse_code == code).first():
        raise HTTPException(status_code=409, detail="이미 등록된 창고코드입니다.")
    values = data.model_dump(exclude={
        "warehouse_code", "company_use_yn", "valid_from", "valid_to",
        "inbound_rate", "outbound_rate", "storage_rate", "weighing_rate", "vat_yn", "charges",
    })
    obj = models.Warehouse(**values, warehouse_code=code)
    db.add(obj); db.flush()
    _save_company_warehouse(obj, comp_code, data, db)
    db.commit(); db.refresh(obj)
    return _warehouse_result(obj, comp_code, db)


@app.put("/api/v1/companies/{comp_code}/warehouses/{warehouse_id}")
def update_warehouse(comp_code: str, warehouse_id: int, data: WarehouseSchema,
                     db: Session = Depends(get_db)):
    _validate_warehouse_data(data)
    obj = db.query(models.Warehouse).filter(models.Warehouse.warehouse_id == warehouse_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="창고가 없습니다.")
    if data.warehouse_code.strip().upper() != obj.warehouse_code:
        raise HTTPException(status_code=400, detail="저장된 창고코드는 변경할 수 없습니다.")
    values = data.model_dump(exclude={
        "warehouse_code", "company_use_yn", "valid_from", "valid_to",
        "inbound_rate", "outbound_rate", "storage_rate", "weighing_rate", "vat_yn", "charges",
    })
    for key, value in values.items():
        setattr(obj, key, value)
    _save_company_warehouse(obj, comp_code, data, db)
    db.commit(); db.refresh(obj)
    return _warehouse_result(obj, comp_code, db)


@app.delete("/api/v1/companies/{comp_code}/warehouses/{warehouse_id}")
def deactivate_warehouse(comp_code: str, warehouse_id: int, db: Session = Depends(get_db)):
    relation = db.query(models.CompanyWarehouse).filter(
        models.CompanyWarehouse.comp_code == comp_code,
        models.CompanyWarehouse.warehouse_id == warehouse_id,
    ).first()
    if not relation:
        raise HTTPException(status_code=404, detail="현재 회사에 등록된 창고가 없습니다.")
    relation.use_yn = False
    db.commit()
    return {"message": "현재 업무회사에서 창고 사용이 중지되었습니다."}


# =============================================================================
# LOT Master API
#
# LOT는 상품의 식별·추적·개별원가를 보존한다. 박스/중량 재고는 LOT에
# 누적 저장하지 않고 후속 입고·출고 Transaction 합계로 계산한다.
# =============================================================================

class LotSchema(BaseModel):
    lot_code: str = ""
    business_lot_no: Optional[str] = None
    source_type: str = "IMPORT"
    product_id: int
    warehouse_id: int
    bl_no: Optional[str] = None
    container_no: Optional[str] = None
    history_no: Optional[str] = None
    origin: Optional[str] = None
    est_no: Optional[str] = None
    production_date: Optional[date] = None
    expiry_date: Optional[date] = None
    individual_cost: Decimal = Field(default=Decimal("0"), ge=0)
    status: str = "OPEN"
    memo: Optional[str] = None
    use_yn: bool = True


def _next_lot_code(comp_code: str, db: Session):
    prefix = f"L{date.today():%Y%m%d}-"
    numbers = []
    rows = db.query(models.Lot.lot_code).filter(
        models.Lot.comp_code == comp_code,
        models.Lot.lot_code.like(f"{prefix}%"),
    ).all()
    for (code,) in rows:
        suffix = (code or "")[len(prefix):]
        if suffix.isdigit():
            numbers.append(int(suffix))
    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def _ceil_won(value) -> Decimal:
    """가격·개별원가는 원 단위 정수로 올림한다."""
    return Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_CEILING)


def _validate_lot_data(comp_code: str, data: LotSchema, db: Session, require_active: bool = True):
    if data.source_type not in {"IMPORT", "DOMESTIC"}:
        raise HTTPException(status_code=400, detail="LOT 구분 값이 올바르지 않습니다.")
    if data.status not in {"OPEN", "HOLD", "CLOSED"}:
        raise HTTPException(status_code=400, detail="LOT 상태 값이 올바르지 않습니다.")
    if data.expiry_date and data.production_date and data.expiry_date < data.production_date:
        raise HTTPException(status_code=400, detail="소비기한은 생산일보다 빠를 수 없습니다.")
    product_query = db.query(models.Product).filter(models.Product.product_id == data.product_id)
    if require_active:
        product_query = product_query.filter(models.Product.use_yn == True)
    product = product_query.first()
    if not product:
        raise HTTPException(status_code=400, detail="사용 가능한 상품을 선택해 주세요.")
    warehouse_query = db.query(models.Warehouse).join(
        models.CompanyWarehouse,
        models.CompanyWarehouse.warehouse_id == models.Warehouse.warehouse_id,
    ).filter(
        models.Warehouse.warehouse_id == data.warehouse_id,
        models.CompanyWarehouse.comp_code == comp_code,
    )
    if require_active:
        warehouse_query = warehouse_query.filter(
            models.Warehouse.use_yn == True,
            models.CompanyWarehouse.use_yn == True,
        )
    warehouse = warehouse_query.first()
    if not warehouse:
        raise HTTPException(status_code=400, detail="현재 회사에서 사용하는 창고를 선택해 주세요.")
    return product


def _lot_result(obj):
    return {
        "lot_id": obj.lot_id,
        "comp_code": obj.comp_code,
        "lot_code": obj.lot_code,
        "business_lot_no": obj.business_lot_no,
        "source_type": obj.source_type,
        "product_id": obj.product_id,
        "product_code": obj.product.product_code,
        "product_name": obj.product.product_name,
        "warehouse_id": obj.warehouse_id,
        "warehouse_code": obj.warehouse.warehouse_code,
        "warehouse_name": obj.warehouse.warehouse_name,
        "bl_no": obj.bl_no,
        "container_no": obj.container_no,
        "history_no": obj.history_no,
        "origin": obj.origin,
        "est_no": obj.est_no,
        "production_date": obj.production_date,
        "expiry_date": obj.expiry_date,
        "individual_cost": int(_ceil_won(obj.individual_cost)),
        "status": obj.status,
        "memo": obj.memo,
        "use_yn": bool(obj.use_yn),
    }


@app.get("/api/v1/companies/{comp_code}/lots/next-code")
def get_next_lot_code(comp_code: str, db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db)
    return {"lot_code": _next_lot_code(comp_code, db)}


@app.get("/api/v1/companies/{comp_code}/lots")
def get_lots(comp_code: str, search: str = "", include_inactive: bool = False,
             db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db)
    query = db.query(models.Lot).filter(models.Lot.comp_code == comp_code)
    if not include_inactive:
        query = query.filter(models.Lot.use_yn == True)
    if search.strip():
        keyword = f"%{search.strip()}%"
        query = query.join(models.Product, models.Product.product_id == models.Lot.product_id).filter(
            (models.Lot.lot_code.like(keyword)) |
            (models.Lot.business_lot_no.like(keyword)) |
            (models.Lot.bl_no.like(keyword)) |
            (models.Lot.container_no.like(keyword)) |
            (models.Lot.history_no.like(keyword)) |
            (models.Product.product_name.like(keyword))
        )
    objects = query.order_by(models.Lot.created_at.desc(), models.Lot.lot_id.desc()).all()
    return [_lot_result(obj) for obj in objects]


@app.get("/api/v1/companies/{comp_code}/lots/{lot_id}")
def get_lot(comp_code: str, lot_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.Lot).filter(
        models.Lot.comp_code == comp_code, models.Lot.lot_id == lot_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="LOT가 없습니다.")
    return _lot_result(obj)


@app.post("/api/v1/companies/{comp_code}/lots", status_code=status.HTTP_201_CREATED)
def create_lot(comp_code: str, data: LotSchema, db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db)
    product = _validate_lot_data(comp_code, data, db)
    code = data.lot_code.strip().upper() or _next_lot_code(comp_code, db)
    if db.query(models.Lot).filter(
        models.Lot.comp_code == comp_code, models.Lot.lot_code == code
    ).first():
        raise HTTPException(status_code=409, detail="현재 회사에 이미 등록된 LOT번호입니다.")
    values = data.model_dump(exclude={"lot_code"})
    if values["production_date"] and values["expiry_date"] is None:
        values["expiry_date"] = _calculate_expiry_date(product, values["production_date"], db)
    values["individual_cost"] = _ceil_won(values["individual_cost"])
    for key in ("business_lot_no", "bl_no", "container_no", "history_no", "origin", "est_no", "memo"):
        values[key] = values[key].strip() if values[key] else None
    obj = models.Lot(comp_code=comp_code, lot_code=code, **values)
    db.add(obj); db.commit(); db.refresh(obj)
    return _lot_result(obj)


@app.put("/api/v1/companies/{comp_code}/lots/{lot_id}")
def update_lot(comp_code: str, lot_id: int, data: LotSchema,
               db: Session = Depends(get_db)):
    obj = db.query(models.Lot).filter(
        models.Lot.comp_code == comp_code, models.Lot.lot_id == lot_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="LOT가 없습니다.")
    if data.lot_code.strip().upper() != obj.lot_code:
        raise HTTPException(status_code=400, detail="저장된 LOT번호는 변경할 수 없습니다.")
    product = _validate_lot_data(comp_code, data, db, require_active=False)
    values = data.model_dump(exclude={"lot_code"})
    if values["production_date"] and values["expiry_date"] is None:
        values["expiry_date"] = _calculate_expiry_date(product, values["production_date"], db)
    values["individual_cost"] = _ceil_won(values["individual_cost"])
    for key in ("business_lot_no", "bl_no", "container_no", "history_no", "origin", "est_no", "memo"):
        values[key] = values[key].strip() if values[key] else None
    for key, value in values.items():
        setattr(obj, key, value)
    db.commit(); db.refresh(obj)
    return _lot_result(obj)


@app.delete("/api/v1/companies/{comp_code}/lots/{lot_id}")
def deactivate_lot(comp_code: str, lot_id: int, permanent: bool = False,
                   db: Session = Depends(get_db)):
    obj = db.query(models.Lot).filter(
        models.Lot.comp_code == comp_code, models.Lot.lot_id == lot_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="LOT가 없습니다.")
    if permanent:
        db.delete(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="입고·출고·재고 등 연결자료가 있는 LOT는 삭제할 수 없습니다. 사용중지 또는 마감 처리해 주세요.",
            )
        return {"message": "연결자료가 없는 LOT가 삭제되었습니다."}
    obj.use_yn = False
    db.commit()
    return {"message": "LOT가 사용중지되었습니다."}


# =============================================================================
# Opening Data API
# =============================================================================

class OpeningInventoryItemSchema(BaseModel):
    inbound_item_id: Optional[int] = None
    lot_id: Optional[int] = None
    product_id: int
    business_lot_no: Optional[str] = None
    source_type: str = "IMPORT"
    bl_no: Optional[str] = None
    container_no: Optional[str] = None
    history_no: Optional[str] = None
    production_date: Optional[date] = None
    box_qty: int = Field(ge=0)
    weight: Decimal = Field(gt=0)
    individual_cost: Decimal = Field(ge=0)
    memo: Optional[str] = None


class OpeningInventorySchema(BaseModel):
    base_date: date
    warehouse_id: int
    memo: Optional[str] = None
    items: list[OpeningInventoryItemSchema] = Field(min_length=1)


class OpeningBalanceSchema(BaseModel):
    base_date: date
    account_id: int
    balance_type: str
    amount: Decimal = Field(gt=0)
    memo: Optional[str] = None


def _next_daily_number(model, number_column, comp_code: str, prefix: str,
                       base_date: date, db: Session) -> str:
    head = f"{prefix}{base_date:%Y%m%d}-"
    numbers = []
    rows = db.query(number_column).filter(
        model.comp_code == comp_code, number_column.like(f"{head}%")
    ).all()
    for (number,) in rows:
        suffix = (number or "")[len(head):]
        if suffix.isdigit():
            numbers.append(int(suffix))
    return f"{head}{max(numbers, default=0) + 1:03d}"


def _opening_lot_code(inbound_no: str, detail_sequence: int) -> str:
    """최초재고 LOT를 기준일-입고전표순번-상세순번으로 식별한다."""
    header_part = inbound_no[2:] if inbound_no.startswith("OI") else inbound_no
    return f"L{header_part}-{detail_sequence:02d}"


def _next_opening_detail_sequence(header) -> int:
    sequences = []
    prefix = f"L{header.inbound_no[2:] if header.inbound_no.startswith('OI') else header.inbound_no}-"
    for detail in header.items:
        code = detail.lot.lot_code or ""
        suffix = code[len(prefix):] if code.startswith(prefix) else ""
        if suffix.isdigit():
            sequences.append(int(suffix))
    return max(sequences, default=len(header.items)) + 1


def _quantize_weight(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _product_attribute(product, group_code: str, db: Session) -> Optional[str]:
    row = db.query(models.CodeValue.code_name).join(
        models.ProductCodeAssignment,
        models.ProductCodeAssignment.code_value_id == models.CodeValue.code_value_id,
    ).join(
        models.CodeGroup,
        models.ProductCodeAssignment.code_group_id == models.CodeGroup.code_group_id,
    ).filter(
        models.ProductCodeAssignment.product_id == product.product_id,
        models.CodeGroup.group_code == group_code,
    ).first()
    return row[0] if row else None


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, month=2, day=28)


def _calculate_expiry_date(product, production_date: Optional[date], db: Session):
    if production_date is None:
        return None
    rule = (product.expiry_rule or "AUTO").upper()
    if rule == "NONE":
        return None
    if rule == "DAYS":
        if not product.shelf_life_days:
            raise HTTPException(status_code=400, detail=f"{product.product_name}의 소비기한 일수를 설정해 주세요.")
        return production_date + timedelta(days=product.shelf_life_days - 1)
    if rule == "FROZEN_2Y":
        return _add_years(production_date, 2) - timedelta(days=1)
    storage_name = _product_attribute(product, "PC004", db) or ""
    if "냉장" in storage_name:
        return None
    # 수입육 업무에서는 별도 냉장정보가 없는 AUTO 상품을 냉동 기본값으로 본다.
    # 냉장육·특정 브랜드는 상품 Master에서 DAYS 또는 NONE 규칙으로 명시한다.
    return _add_years(production_date, 2) - timedelta(days=1)


def _opening_inventory_result(header):
    return {
        "inbound_id": header.inbound_id,
        "inbound_no": header.inbound_no,
        "base_date": header.inbound_date,
        "warehouse_id": header.warehouse_id,
        "warehouse_name": header.warehouse.warehouse_name,
        "memo": header.memo,
        "items": [{
            "inbound_item_id": item.inbound_item_id,
            "line_no": item.line_no,
            "product_id": item.product_id,
            "product_code": item.product.product_code,
            "product_name": item.product.product_name,
            "lot_id": item.lot_id,
            "lot_code": item.lot.lot_code,
            "business_lot_no": item.lot.business_lot_no,
            "source_type": item.lot.source_type,
            "bl_no": item.lot.bl_no,
            "container_no": item.lot.container_no,
            "history_no": item.lot.history_no,
            "origin": item.lot.origin,
            "est_no": item.lot.est_no,
            "production_date": item.lot.production_date,
            "expiry_date": item.lot.expiry_date,
            "memo": item.lot.memo,
            "box_qty": item.box_qty,
            "weight": item.weight,
            "individual_cost": int(_ceil_won(item.individual_cost)),
            "amount": int(item.amount),
        } for item in header.items],
    }


@app.get("/api/v1/companies/{comp_code}/opening-inventories")
def get_opening_inventories(comp_code: str, db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db)
    rows = db.query(models.Inbound).filter(
        models.Inbound.comp_code == comp_code,
        models.Inbound.transaction_type == "OPENING_INVENTORY",
    ).order_by(models.Inbound.inbound_date.desc(), models.Inbound.inbound_id.desc()).all()
    return [_opening_inventory_result(row) for row in rows]


@app.post("/api/v1/companies/{comp_code}/opening-inventories", status_code=status.HTTP_201_CREATED)
def create_opening_inventory(comp_code: str, data: OpeningInventorySchema,
                             db: Session = Depends(get_db)):
    """LOT와 최초입고 Header/Detail을 단일 DB Transaction으로 생성한다."""
    _get_company_or_404(comp_code, db)
    warehouse = db.query(models.Warehouse).join(models.CompanyWarehouse).filter(
        models.Warehouse.warehouse_id == data.warehouse_id,
        models.Warehouse.use_yn == True,
        models.CompanyWarehouse.comp_code == comp_code,
        models.CompanyWarehouse.use_yn == True,
    ).first()
    if not warehouse:
        raise HTTPException(status_code=400, detail="현재 회사에서 사용하는 창고를 선택해 주세요.")

    product_ids = {item.product_id for item in data.items}
    products = {
        row.product_id: row for row in db.query(models.Product).filter(
            models.Product.product_id.in_(product_ids), models.Product.use_yn == True
        ).all()
    }
    if set(products) != product_ids:
        raise HTTPException(status_code=400, detail="사용할 수 없는 상품이 포함되어 있습니다.")
    for item in data.items:
        if item.source_type not in {"IMPORT", "DOMESTIC"}:
            raise HTTPException(status_code=400, detail="LOT 구분 값이 올바르지 않습니다.")

    try:
        inbound = models.Inbound(
            comp_code=comp_code,
            inbound_no=_next_daily_number(
                models.Inbound, models.Inbound.inbound_no, comp_code, "OI", data.base_date, db
            ),
            inbound_date=data.base_date,
            warehouse_id=data.warehouse_id,
            transaction_type="OPENING_INVENTORY",
            memo=data.memo.strip() if data.memo else None,
        )
        db.add(inbound)
        db.flush()
        for line_no, item in enumerate(data.items, 1):
            product = products[item.product_id]
            origin = _product_attribute(product, "PC003", db)
            est_no = _product_attribute(product, "PC008", db)
            expiry_date = _calculate_expiry_date(product, item.production_date, db)
            lot = models.Lot(
                comp_code=comp_code,
                lot_code=_opening_lot_code(inbound.inbound_no, line_no),
                business_lot_no=item.business_lot_no.strip() if item.business_lot_no else None,
                source_type=item.source_type,
                product_id=item.product_id,
                warehouse_id=data.warehouse_id,
                bl_no=item.bl_no.strip() if item.bl_no else None,
                container_no=item.container_no.strip() if item.container_no else None,
                history_no=item.history_no.strip() if item.history_no else None,
                origin=origin,
                est_no=est_no,
                production_date=item.production_date,
                expiry_date=expiry_date,
                individual_cost=_ceil_won(item.individual_cost),
                status="OPEN",
                memo=item.memo.strip() if item.memo else None,
                use_yn=True,
            )
            db.add(lot)
            db.flush()
            weight = _quantize_weight(item.weight)
            cost = _ceil_won(item.individual_cost)
            db.add(models.InboundItem(
                inbound_id=inbound.inbound_id,
                line_no=line_no,
                product_id=item.product_id,
                lot_id=lot.lot_id,
                box_qty=item.box_qty,
                weight=weight,
                individual_cost=cost,
                amount=_ceil_won(weight * cost),
            ))
        db.commit()
        db.refresh(inbound)
        return _opening_inventory_result(inbound)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="최초재고 저장 중 중복 또는 연결 오류가 발생했습니다.") from exc
    except Exception:
        db.rollback()
        raise


@app.put("/api/v1/companies/{comp_code}/opening-inventories/{inbound_id}")
def update_opening_inventory(comp_code: str, inbound_id: int,
                             data: OpeningInventorySchema,
                             db: Session = Depends(get_db)):
    header = db.query(models.Inbound).filter(
        models.Inbound.inbound_id == inbound_id,
        models.Inbound.comp_code == comp_code,
        models.Inbound.transaction_type == "OPENING_INVENTORY",
    ).first()
    if not header:
        raise HTTPException(status_code=404, detail="최초재고 전표가 없습니다.")
    warehouse = db.query(models.Warehouse).join(models.CompanyWarehouse).filter(
        models.Warehouse.warehouse_id == data.warehouse_id,
        models.CompanyWarehouse.comp_code == comp_code,
        models.CompanyWarehouse.use_yn == True,
    ).first()
    if not warehouse:
        raise HTTPException(status_code=400, detail="현재 회사에서 사용하는 창고를 선택해 주세요.")
    product_ids = {item.product_id for item in data.items}
    products = {row.product_id: row for row in db.query(models.Product).filter(
        models.Product.product_id.in_(product_ids), models.Product.use_yn == True
    ).all()}
    if set(products) != product_ids:
        raise HTTPException(status_code=400, detail="사용할 수 없는 상품이 포함되어 있습니다.")
    existing = {item.inbound_item_id: item for item in header.items}
    requested_ids = {item.inbound_item_id for item in data.items if item.inbound_item_id}
    if not requested_ids.issubset(existing):
        raise HTTPException(status_code=400, detail="현재 전표에 속하지 않은 상세행입니다.")
    try:
        next_detail_sequence = _next_opening_detail_sequence(header)
        header.inbound_date = data.base_date
        header.warehouse_id = data.warehouse_id
        header.memo = data.memo.strip() if data.memo else None
        # 기존 행의 순서를 바꾸어도 (inbound_id, line_no) UNIQUE가 충돌하지 않게
        # 임시 순번으로 먼저 이동한 뒤 최종 순번을 적용한다.
        for old_item in existing.values(): old_item.line_no += 100000
        db.flush()
        for removed_id in set(existing) - requested_ids:
            old_item = existing[removed_id]
            old_lot = old_item.lot
            db.delete(old_item); db.flush(); db.delete(old_lot)
        db.flush()
        for line_no, item in enumerate(data.items, 1):
            if item.source_type not in {"IMPORT", "DOMESTIC"}:
                raise HTTPException(status_code=400, detail="LOT 구분 값이 올바르지 않습니다.")
            product = products[item.product_id]
            origin = _product_attribute(product, "PC003", db)
            est_no = _product_attribute(product, "PC008", db)
            expiry_date = _calculate_expiry_date(product, item.production_date, db)
            if item.inbound_item_id:
                detail = existing[item.inbound_item_id]
                lot = detail.lot
            else:
                lot = models.Lot(
                    comp_code=comp_code,
                    lot_code=_opening_lot_code(header.inbound_no, next_detail_sequence),
                    product_id=item.product_id,
                    warehouse_id=data.warehouse_id,
                )
                next_detail_sequence += 1
                db.add(lot); db.flush()
                detail = models.InboundItem(inbound_id=header.inbound_id, lot_id=lot.lot_id)
                db.add(detail)
            lot.business_lot_no = item.business_lot_no.strip() if item.business_lot_no else None
            lot.source_type = item.source_type
            lot.product_id = item.product_id
            lot.warehouse_id = data.warehouse_id
            lot.bl_no = item.bl_no.strip() if item.bl_no else None
            lot.container_no = item.container_no.strip() if item.container_no else None
            lot.history_no = item.history_no.strip() if item.history_no else None
            lot.origin = origin; lot.est_no = est_no
            lot.production_date = item.production_date; lot.expiry_date = expiry_date
            lot.individual_cost = _ceil_won(item.individual_cost)
            lot.status = "OPEN"; lot.memo = item.memo.strip() if item.memo else None; lot.use_yn = True
            weight = _quantize_weight(item.weight); cost = _ceil_won(item.individual_cost)
            detail.line_no = line_no; detail.product_id = item.product_id
            detail.box_qty = item.box_qty; detail.weight = weight
            detail.individual_cost = cost; detail.amount = _ceil_won(weight * cost)
        db.commit(); db.refresh(header)
        return _opening_inventory_result(header)
    except HTTPException:
        db.rollback(); raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="후속 입출고에 연결된 LOT가 포함되어 수정할 수 없습니다.",
        ) from exc
    except Exception:
        db.rollback(); raise


@app.delete("/api/v1/companies/{comp_code}/opening-inventories/{inbound_id}")
def delete_opening_inventory(comp_code: str, inbound_id: int,
                             db: Session = Depends(get_db)):
    header = db.query(models.Inbound).filter(
        models.Inbound.inbound_id == inbound_id,
        models.Inbound.comp_code == comp_code,
        models.Inbound.transaction_type == "OPENING_INVENTORY",
    ).first()
    if not header:
        raise HTTPException(status_code=404, detail="최초재고 전표가 없습니다.")
    try:
        lots = [item.lot for item in header.items]
        db.delete(header); db.flush()
        for lot in lots: db.delete(lot)
        db.commit()
        return {"message": "최초재고 전표와 연결 LOT가 삭제되었습니다."}
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="후속 입출고에 연결된 LOT가 포함되어 삭제할 수 없습니다.",
        ) from exc


def _opening_balance_result(obj, allocated=Decimal("0")):
    return {
        "account_transaction_id": obj.account_transaction_id,
        "transaction_no": obj.transaction_no,
        "base_date": obj.transaction_date,
        "account_id": obj.account_id,
        "account_code": obj.account.account_code,
        "account_name": obj.account.account_name,
        "balance_type": obj.transaction_type.replace("OPENING_", ""),
        "amount": int(obj.original_amount),
        "allocated_amount": int(allocated),
        "remaining_amount": int(Decimal(obj.original_amount) - allocated),
        "memo": obj.memo,
    }


@app.get("/api/v1/companies/{comp_code}/opening-balances")
def get_opening_balances(comp_code: str, db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db)
    rows = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == comp_code,
        models.AccountTransaction.transaction_type.in_(("OPENING_RECEIVABLE", "OPENING_PAYABLE")),
    ).order_by(
        models.AccountTransaction.transaction_date.desc(),
        models.AccountTransaction.account_transaction_id.desc(),
    ).all()
    results = []
    for row in rows:
        allocated = sum((Decimal(x.allocated_amount) for x in db.query(
            models.AccountTransactionAllocation
        ).filter(
            models.AccountTransactionAllocation.source_transaction_id == row.account_transaction_id
        ).all()), Decimal("0"))
        results.append(_opening_balance_result(row, allocated))
    return results


@app.post("/api/v1/companies/{comp_code}/opening-balances", status_code=status.HTTP_201_CREATED)
def create_opening_balance(comp_code: str, data: OpeningBalanceSchema,
                           db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db)
    balance_type = data.balance_type.strip().upper()
    if balance_type not in {"RECEIVABLE", "PAYABLE"}:
        raise HTTPException(status_code=400, detail="잔액구분은 미수금 또는 미지급금이어야 합니다.")
    relation = db.query(models.CompanyAccount).filter(
        models.CompanyAccount.comp_code == comp_code,
        models.CompanyAccount.account_id == data.account_id,
        models.CompanyAccount.use_yn == True,
        models.CompanyAccount.trade_stop_yn == False,
    ).first()
    if not relation:
        raise HTTPException(status_code=400, detail="현재 회사에서 거래 가능한 거래처를 선택해 주세요.")
    if balance_type == "RECEIVABLE" and not relation.sales_yn:
        raise HTTPException(status_code=400, detail="미수금은 매출거래 거래처에만 등록할 수 있습니다.")
    if balance_type == "PAYABLE" and not relation.purchase_yn:
        raise HTTPException(status_code=400, detail="미지급금은 매입거래 거래처에만 등록할 수 있습니다.")
    prefix = "OR" if balance_type == "RECEIVABLE" else "OP"
    amount = _ceil_won(data.amount)
    obj = models.AccountTransaction(
        comp_code=comp_code,
        transaction_no=_next_daily_number(
            models.AccountTransaction, models.AccountTransaction.transaction_no,
            comp_code, prefix, data.base_date, db
        ),
        transaction_date=data.base_date,
        account_id=data.account_id,
        transaction_type=f"OPENING_{balance_type}",
        original_amount=amount,
        memo=data.memo.strip() if data.memo else None,
    )
    try:
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return _opening_balance_result(obj)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="최초잔액 저장 중 중복 또는 연결 오류가 발생했습니다.") from exc


@app.put("/api/v1/companies/{comp_code}/opening-balances/{transaction_id}")
def update_opening_balance(comp_code: str, transaction_id: int,
                           data: OpeningBalanceSchema, db: Session = Depends(get_db)):
    obj = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.account_transaction_id == transaction_id,
        models.AccountTransaction.comp_code == comp_code,
        models.AccountTransaction.transaction_type.in_(("OPENING_RECEIVABLE", "OPENING_PAYABLE")),
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="거래처 최초잔액 원거래가 없습니다.")
    allocated = db.query(models.AccountTransactionAllocation).filter(
        models.AccountTransactionAllocation.source_transaction_id == transaction_id
    ).first()
    if allocated:
        raise HTTPException(status_code=409, detail="수금·지급이 배분된 원거래는 수정할 수 없습니다.")
    balance_type = data.balance_type.strip().upper()
    if balance_type not in {"RECEIVABLE", "PAYABLE"}:
        raise HTTPException(status_code=400, detail="잔액구분은 미수금 또는 미지급금이어야 합니다.")
    relation = db.query(models.CompanyAccount).filter(
        models.CompanyAccount.comp_code == comp_code,
        models.CompanyAccount.account_id == data.account_id,
        models.CompanyAccount.use_yn == True,
        models.CompanyAccount.trade_stop_yn == False,
    ).first()
    if not relation:
        raise HTTPException(status_code=400, detail="현재 회사에서 거래 가능한 거래처를 선택해 주세요.")
    if balance_type == "RECEIVABLE" and not relation.sales_yn:
        raise HTTPException(status_code=400, detail="미수금은 매출거래 거래처에만 등록할 수 있습니다.")
    if balance_type == "PAYABLE" and not relation.purchase_yn:
        raise HTTPException(status_code=400, detail="미지급금은 매입거래 거래처에만 등록할 수 있습니다.")
    obj.transaction_date = data.base_date; obj.account_id = data.account_id
    obj.transaction_type = f"OPENING_{balance_type}"; obj.original_amount = _ceil_won(data.amount)
    obj.memo = data.memo.strip() if data.memo else None
    db.commit(); db.refresh(obj)
    return _opening_balance_result(obj)


@app.delete("/api/v1/companies/{comp_code}/opening-balances/{transaction_id}")
def delete_opening_balance(comp_code: str, transaction_id: int,
                           db: Session = Depends(get_db)):
    obj = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.account_transaction_id == transaction_id,
        models.AccountTransaction.comp_code == comp_code,
        models.AccountTransaction.transaction_type.in_(("OPENING_RECEIVABLE", "OPENING_PAYABLE")),
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="거래처 최초잔액 원거래가 없습니다.")
    if db.query(models.AccountTransactionAllocation).filter(
        models.AccountTransactionAllocation.source_transaction_id == transaction_id
    ).first():
        raise HTTPException(status_code=409, detail="수금·지급이 배분된 원거래는 삭제할 수 없습니다.")
    db.delete(obj); db.commit()
    return {"message": "거래처 최초잔액 원거래가 삭제되었습니다."}


# =============================================================================
# Account API
#
# 설계 원칙
#
# tb_account
#   = 회사 간 공유 가능한 거래처 공통 Master
#
# tb_company_account
#   = 각 회사별 거래처 사용관계 및 거래조건
#
# 매입/매출/미수/미지급/재고/LOT 등 실제 업무 데이터는
# 반드시 comp_code 기준으로 회사별 독립 관리
# =============================================================================


class AccountSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    account_code: str
    account_name: str
    biz_no: Optional[str] = None
    corp_no: Optional[str] = None
    ceo_name: Optional[str] = None
    zip_code: Optional[str] = None
    address: Optional[str] = None
    address_detail: Optional[str] = None
    uptae: Optional[str] = None
    upjong: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    contact_name: Optional[str] = None
    contact_mobile: Optional[str] = None
    tax_email: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_account_holder: Optional[str] = None
    meatwatch_cust_no: Optional[str] = None
    memo: Optional[str] = None
    use_yn: bool = True

class AccountResponse(AccountSchema):
    account_id: int

class CompanyAccountSchema(BaseModel):
    trade_status: str = "TRADE"
    trade_type: str = "GENERAL"
    purchase_yn: bool = False
    sales_yn: bool = False
    tax_doc_type: str = "NONE"
    sales_tax_auto_yn: bool = False
    purchase_tax_manage_yn: bool = False
    trade_stop_yn: bool = False
    invoice_issue_yn: bool = False
    use_yn: bool = True
    memo: Optional[str] = None

class CompanyAccountResponse(CompanyAccountSchema):
    model_config = ConfigDict(from_attributes=True)
    company_account_id: int
    comp_code: str
    account_id: int
    account_code: str
    account_name: str
    biz_no: Optional[str] = None
    ceo_name: Optional[str] = None
    tax_email: Optional[str] = None

def _get_company_or_404(comp_code: str, db: Session):
    company = db.query(models.Company).filter(models.Company.comp_code == comp_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="등록되지 않은 회사코드입니다.")
    return company

def _get_account_or_404(account_id: int, db: Session):
    account = db.query(models.Account).filter(models.Account.account_id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="등록되지 않은 거래처입니다.")
    return account

@app.get("/api/v1/accounts/next-code")
def get_next_account_code(db: Session = Depends(get_db)):
    rows = db.query(models.Account.account_code).filter(models.Account.account_code.isnot(None)).all()
    max_no = 0
    for (code,) in rows:
        code = str(code).strip()
        if code.isdigit():
            max_no = max(max_no, int(code))
    return {"account_code": f"{max_no + 1:05d}"}

@app.get("/api/v1/accounts", response_model=list[AccountResponse])
def get_accounts(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.Account)
    if not include_inactive:
        q = q.filter(models.Account.use_yn == True)
    return q.order_by(models.Account.account_name, models.Account.account_code).all()

@app.get("/api/v1/accounts/{account_id}", response_model=AccountResponse)
def get_account(account_id: int, db: Session = Depends(get_db)):
    return _get_account_or_404(account_id, db)

@app.post("/api/v1/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(data: AccountSchema, db: Session = Depends(get_db)):
    if db.query(models.Account).filter(models.Account.account_code == data.account_code).first():
        raise HTTPException(status_code=409, detail="이미 등록된 거래처코드입니다.")
    # 동일 사업자번호라도 업무 역할별로 복수의 거래처코드를 등록할 수 있다.
    # 거래처코드(account_code)만 고유하게 관리한다.
    obj=models.Account(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.put("/api/v1/accounts/{account_id}", response_model=AccountResponse)
def update_account(account_id: int, data: AccountSchema, db: Session = Depends(get_db)):
    obj=_get_account_or_404(account_id,db)
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    db.commit(); db.refresh(obj)
    return obj

def _company_account_response(ca, a):
    return CompanyAccountResponse(
        company_account_id=ca.company_account_id, comp_code=ca.comp_code,
        account_id=a.account_id, account_code=a.account_code, account_name=a.account_name,
        biz_no=a.biz_no, ceo_name=a.ceo_name, tax_email=a.tax_email,
        trade_status=ca.trade_status, trade_type=ca.trade_type,
        purchase_yn=ca.purchase_yn, sales_yn=ca.sales_yn,
        tax_doc_type=ca.tax_doc_type, sales_tax_auto_yn=ca.sales_tax_auto_yn,
        purchase_tax_manage_yn=ca.purchase_tax_manage_yn,
        trade_stop_yn=ca.trade_stop_yn, invoice_issue_yn=ca.invoice_issue_yn,
        use_yn=ca.use_yn, memo=ca.memo)

@app.get("/api/v1/companies/{comp_code}/accounts", response_model=list[CompanyAccountResponse])
def get_company_accounts(
    comp_code: str,
    include_inactive: bool=False,
    include_stopped: bool=False,
    db: Session=Depends(get_db)
):
    _get_company_or_404(comp_code,db)
    q=(db.query(models.CompanyAccount,models.Account)
       .join(models.Account,models.CompanyAccount.account_id==models.Account.account_id)
       .filter(models.CompanyAccount.comp_code==comp_code))
    if not include_inactive:
        q=q.filter(models.CompanyAccount.use_yn==True,models.Account.use_yn==True)
    if not include_stopped:
        q=q.filter(models.CompanyAccount.trade_stop_yn==False)
    return [_company_account_response(c,a) for c,a in q.order_by(models.Account.account_name).all()]

@app.get("/api/v1/companies/{comp_code}/accounts/{account_id}", response_model=CompanyAccountResponse)
def get_company_account(comp_code: str, account_id:int, db:Session=Depends(get_db)):
    a=_get_account_or_404(account_id,db)
    ca=(db.query(models.CompanyAccount).filter(models.CompanyAccount.comp_code==comp_code,
                                               models.CompanyAccount.account_id==account_id).first())
    if not ca: raise HTTPException(status_code=404,detail="현재 업무회사에 연결되지 않은 거래처입니다.")
    return _company_account_response(ca,a)

@app.post("/api/v1/companies/{comp_code}/accounts/{account_id}", response_model=CompanyAccountResponse)
def link_account_to_company(comp_code:str,account_id:int,data:CompanyAccountSchema,db:Session=Depends(get_db)):
    _get_company_or_404(comp_code,db); a=_get_account_or_404(account_id,db)
    ca=(db.query(models.CompanyAccount).filter(models.CompanyAccount.comp_code==comp_code,
                                               models.CompanyAccount.account_id==account_id).first())
    if ca:
        for k,v in data.model_dump().items(): setattr(ca,k,v)
    else:
        ca=models.CompanyAccount(comp_code=comp_code,account_id=account_id,**data.model_dump())
        db.add(ca)
    db.commit(); db.refresh(ca)
    return _company_account_response(ca,a)

@app.put("/api/v1/companies/{comp_code}/accounts/{account_id}", response_model=CompanyAccountResponse)
def update_company_account(comp_code:str,account_id:int,data:CompanyAccountSchema,db:Session=Depends(get_db)):
    return link_account_to_company(comp_code,account_id,data,db)


# =============================================================================
# Trade common foundation API
# =============================================================================

class AccountingPeriodUpdate(BaseModel):
    period_status: str = Field(pattern=r"^(OPEN|CLOSED)$")


def _period_response(row):
    return {
        "accounting_period_id": row.accounting_period_id,
        "comp_code": row.comp_code,
        "period_year": row.period_year,
        "period_month": row.period_month,
        "period_status": row.period_status,
        "closed_by": row.closed_by,
        "closed_at": row.closed_at,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at,
    }


@app.get("/api/v1/tax-codes")
def get_tax_codes(
    transaction_date: Optional[date] = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    target_date = transaction_date or date.today()
    query = db.query(models.TaxCode)
    if not include_inactive:
        query = query.filter(
            models.TaxCode.use_yn == True,
            models.TaxCode.valid_from <= target_date,
            (models.TaxCode.valid_to == None) | (models.TaxCode.valid_to >= target_date),
        )
    return query.order_by(models.TaxCode.sort_order, models.TaxCode.tax_code).all()


@app.get("/api/v1/companies/{comp_code}/accounting-periods")
def get_accounting_periods(comp_code: str, db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db)
    rows = db.query(models.AccountingPeriod).filter(
        models.AccountingPeriod.comp_code == comp_code
    ).order_by(
        models.AccountingPeriod.period_year.desc(),
        models.AccountingPeriod.period_month.desc(),
    ).all()
    return [_period_response(row) for row in rows]


@app.put("/api/v1/companies/{comp_code}/accounting-periods/{period_year}/{period_month}")
def set_accounting_period(
    comp_code: str,
    period_year: int,
    period_month: int,
    data: AccountingPeriodUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    _get_company_or_404(comp_code, db)
    if period_year < 2000 or period_year > 2100 or period_month < 1 or period_month > 12:
        raise HTTPException(status_code=400, detail="올바른 회계연월을 입력하세요.")
    row = db.query(models.AccountingPeriod).filter(
        models.AccountingPeriod.comp_code == comp_code,
        models.AccountingPeriod.period_year == period_year,
        models.AccountingPeriod.period_month == period_month,
    ).first()
    now = datetime.now(timezone.utc)
    if not row:
        row = models.AccountingPeriod(
            comp_code=comp_code,
            period_year=period_year,
            period_month=period_month,
            period_status="OPEN",
            created_by=request.state.user_id,
            updated_by=request.state.user_id,
        )
        db.add(row)
    row.period_status = data.period_status
    row.updated_by = request.state.user_id
    row.updated_at = now
    if data.period_status == "CLOSED":
        row.closed_by = request.state.user_id
        row.closed_at = now
    else:
        row.closed_by = None
        row.closed_at = None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="회계기간 중복 또는 사용자·회사 연결을 확인하세요.")
    db.refresh(row)
    return _period_response(row)


@app.get("/api/v1/companies/{comp_code}/trade-input-options")
def get_trade_input_options(comp_code: str, transaction_date: date, db: Session = Depends(get_db)):
    """거래 Detail에서 허용되는 세금코드와 최하위 INPUT 경비코드만 반환한다."""
    _get_company_or_404(comp_code, db)
    taxes = db.query(models.TaxCode).filter(
        models.TaxCode.use_yn == True,
        models.TaxCode.valid_from <= transaction_date,
        (models.TaxCode.valid_to == None) | (models.TaxCode.valid_to >= transaction_date),
    ).order_by(models.TaxCode.sort_order).all()
    # Self alias 없이도 안정적으로 동작하도록 활성 부모 ID 집합을 먼저 구한다.
    parent_ids = {row[0] for row in db.query(models.ExpenseCode.parent_expense_id).filter(
        models.ExpenseCode.parent_expense_id.isnot(None),
        models.ExpenseCode.use_yn == True,
    ).distinct().all()}
    expenses = db.query(models.ExpenseCode).filter(
        models.ExpenseCode.node_type == "INPUT",
        models.ExpenseCode.use_yn == True,
    ).order_by(models.ExpenseCode.expense_code).all()
    return {
        "tax_codes": taxes,
        "expense_codes": [
            {"expense_id": row.expense_id, "expense_code": row.expense_code,
             "expense_name": row.expense_name, "statement_section": row.statement_section}
            for row in expenses if row.expense_id not in parent_ids
        ],
    }


# =============================================================================
# General purchase Vertical Slice
# =============================================================================

class PurchaseItemInput(BaseModel):
    line_no: int = Field(ge=1)
    product_id: int
    expense_id: Optional[int] = None  # 구버전 Client 호환. 상품매입에서는 사용하지 않는다.
    warehouse_id: int
    box_qty: int = Field(ge=0)
    weight: Decimal = Field(gt=0, decimal_places=2)
    unit_price: int = Field(ge=0)
    taxable_yn: bool = False
    tax_code: Optional[str] = Field(default=None, max_length=20)
    history_no: Optional[str] = Field(default=None, max_length=30)
    bl_no: Optional[str] = Field(default=None, max_length=80)
    supply_amount: Optional[int] = Field(default=None, ge=0)
    tax_amount: Optional[int] = Field(default=None, ge=0)
    discount_amount: int = 0
    total_amount: Optional[int] = Field(default=None, ge=0)
    memo: Optional[str] = Field(default=None, max_length=500)


class PurchaseInput(BaseModel):
    purchase_date: date
    account_id: int
    memo: Optional[str] = Field(default=None, max_length=1000)
    finalize: bool = False
    items: list[PurchaseItemInput] = Field(min_length=1)


def _purchase_supplier(db: Session, comp_code: str, account_id: int):
    row = (db.query(models.CompanyAccount, models.Account)
           .join(models.Account, models.Account.account_id == models.CompanyAccount.account_id)
           .filter(models.CompanyAccount.comp_code == comp_code,
                   models.CompanyAccount.account_id == account_id,
                   models.CompanyAccount.use_yn == True,
                   models.CompanyAccount.trade_stop_yn == False,
                   models.CompanyAccount.purchase_yn == True,
                   models.Account.use_yn == True).first())
    if not row:
        raise HTTPException(status_code=400, detail="현재 회사에서 사용 중인 매입거래처만 선택할 수 있습니다.")
    return row


def _prepare_purchase_lines(db: Session, comp_code: str, purchase_date: date, items):
    line_numbers = [item.line_no for item in items]
    if len(set(line_numbers)) != len(line_numbers):
        raise HTTPException(status_code=400, detail="전표 내 Detail 순번은 중복될 수 없습니다.")
    prepared = []
    for item in items:
        product = db.query(models.Product).filter(
            models.Product.product_id == item.product_id, models.Product.use_yn == True
        ).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"{item.line_no}행 상품은 사용 중인 상품이 아닙니다.")
        warehouse = db.query(models.Warehouse).join(models.CompanyWarehouse).filter(
            models.Warehouse.warehouse_id == item.warehouse_id,
            models.Warehouse.use_yn == True,
            models.CompanyWarehouse.comp_code == comp_code,
            models.CompanyWarehouse.use_yn == True,
        ).first()
        if not warehouse:
            raise HTTPException(status_code=400, detail=f"{item.line_no}행 창고는 현재 회사에서 사용하는 창고가 아닙니다.")
        # 세무구분은 화면 선택값이 아니라 상품 Master를 단일 기준으로 사용한다.
        tax_code = "VAT10" if str(product.tax_type) in {"1", "VAT10"} else "EXEMPT"
        tax = db.query(models.TaxCode).filter(models.TaxCode.tax_code == tax_code).first()
        if not tax:
            raise HTTPException(status_code=400, detail=f"{item.line_no}행 세금코드가 없습니다.")
        snapshot = tax_snapshot(tax, purchase_date)
        calculated = calculate_purchase_line(
            item.weight, item.unit_price, snapshot["tax_rate_snapshot"], item.discount_amount
        )
        validate_client_amounts(calculated, item.model_dump())
        prepared.append({
            "line_no": item.line_no, "product_id": item.product_id,
            "expense_id": None, "warehouse_id": item.warehouse_id,
            "history_no": item.history_no.strip() if item.history_no else None,
            "bl_no": item.bl_no.strip() if item.bl_no else None,
            "box_qty": validate_box_qty(item.box_qty),
            "weight": Decimal(item.weight), "unit_price": item.unit_price,
            **snapshot, **calculated, "memo": item.memo,
        })
    return prepared


def _purchase_result(row):
    return {
        "purchase_id": row.purchase_id, "comp_code": row.comp_code,
        "purchase_no": row.purchase_no, "purchase_date": row.purchase_date,
        "account_id": row.account_id,
        "account_code": row.account.account_code if row.account else None,
        "account_name": row.account.account_name if row.account else None,
        "document_status": row.document_status,
        "total_box_qty": row.total_box_qty, "total_weight": row.total_weight,
        "total_supply_amount": row.total_supply_amount,
        "total_tax_amount": row.total_tax_amount,
        "total_discount_amount": row.total_discount_amount,
        "total_amount": row.total_amount,
        "memo": row.memo, "created_by": row.created_by, "created_at": row.created_at,
        "updated_by": row.updated_by, "updated_at": row.updated_at,
        "confirmed_by": row.confirmed_by, "confirmed_at": row.confirmed_at,
        "cancelled_by": row.cancelled_by, "cancelled_at": row.cancelled_at,
        "items": [{
            "purchase_item_id": item.purchase_item_id, "line_no": item.line_no,
            "product_id": item.product_id,
            "product_code": item.product.product_code if item.product else None,
            "product_name": item.product.product_name if item.product else None,
            "expense_id": item.expense_id,
            "expense_code": item.expense.expense_code if item.expense else None,
            "expense_name": item.expense.expense_name if item.expense else None,
            "warehouse_id": item.warehouse_id,
            "warehouse_name": item.warehouse.warehouse_name if item.warehouse else None,
            "history_no": item.history_no, "bl_no": item.bl_no,
            "average_weight": (Decimal(item.weight) / item.box_qty).quantize(Decimal("0.01")) if item.box_qty else Decimal("0.00"),
            "lot_id": item.lot_id, "lot_code": item.lot.lot_code if item.lot else None,
            "inbound_item_id": item.inbound_item_id,
            "box_qty": item.box_qty, "weight": item.weight, "unit_price": item.unit_price,
            "supply_amount": item.supply_amount,
            "tax_code_snapshot": item.tax_code_snapshot,
            "tax_name_snapshot": item.tax_name_snapshot,
            "tax_rate_snapshot": item.tax_rate_snapshot,
            "tax_amount": item.tax_amount, "discount_amount": item.discount_amount,
            "total_amount": item.total_amount,
            "memo": item.memo,
        } for item in sorted(row.items, key=lambda value: value.line_no)],
    }


def _purchase_or_404(db: Session, comp_code: str, purchase_id: int):
    row = db.query(models.Purchase).filter(
        models.Purchase.purchase_id == purchase_id,
        models.Purchase.comp_code == comp_code,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="일반 매입전표가 없습니다.")
    return row


def _materialize_purchase(db: Session, row):
    """상품매입 원문을 실제 입고·LOT·미지급 원장으로 한 번에 전개한다."""
    inbound_by_warehouse = {}
    for item in sorted(row.items, key=lambda value: value.line_no):
        if not item.warehouse_id:
            raise HTTPException(status_code=400, detail=f"{item.line_no}행 입고창고를 선택하세요.")
        inbound = inbound_by_warehouse.get(item.warehouse_id)
        if inbound is None:
            inbound = models.Inbound(
                comp_code=row.comp_code,
                inbound_no=allocate_document_no(db, row.comp_code, "PURCHASE_INBOUND", row.purchase_date),
                inbound_date=row.purchase_date,
                warehouse_id=item.warehouse_id,
                transaction_type="PURCHASE_INBOUND",
                memo=f"상품매입 {row.purchase_no}",
            )
            db.add(inbound); db.flush(); inbound_by_warehouse[item.warehouse_id] = inbound
        lot = models.Lot(
            comp_code=row.comp_code,
            lot_code=f"L{row.purchase_no[3:]}-{item.line_no:02d}",
            business_lot_no=None,
            source_type="DOMESTIC",
            product_id=item.product_id,
            warehouse_id=item.warehouse_id,
            bl_no=item.bl_no,
            history_no=item.history_no,
            origin=_product_attribute(item.product, "PC003", db),
            est_no=_product_attribute(item.product, "PC008", db),
            individual_cost=item.unit_price,
            status="OPEN", use_yn=True,
            memo=f"상품매입 {row.purchase_no} {item.line_no}행",
        )
        db.add(lot); db.flush()
        inbound_item = models.InboundItem(
            inbound_id=inbound.inbound_id, line_no=item.line_no,
            product_id=item.product_id, lot_id=lot.lot_id,
            box_qty=item.box_qty, weight=item.weight,
            individual_cost=item.unit_price, amount=item.supply_amount,
        )
        db.add(inbound_item); db.flush()
        item.lot_id = lot.lot_id
        item.inbound_item_id = inbound_item.inbound_item_id
    db.add(models.AccountTransaction(
        comp_code=row.comp_code, transaction_no=row.purchase_no,
        transaction_date=row.purchase_date, account_id=row.account_id,
        transaction_type="PURCHASE_PAYABLE", original_amount=row.total_amount,
        memo=f"상품매입 {row.purchase_no}",
    ))


def _dematerialize_purchase(db: Session, row, transaction_no: Optional[str] = None):
    """수정·취소 전에 이 매입이 만든 파생자료만 회수한다."""
    inbound_ids = {item.inbound_item.inbound_id for item in row.items if item.inbound_item}
    lots = [item.lot for item in row.items if item.lot]
    for item in row.items:
        item.inbound_item_id = None
        item.lot_id = None
    db.flush()
    if inbound_ids:
        db.query(models.InboundItem).filter(
            models.InboundItem.inbound_id.in_(inbound_ids)
        ).delete(synchronize_session=False)
        db.query(models.Inbound).filter(
            models.Inbound.inbound_id.in_(inbound_ids)
        ).delete(synchronize_session=False)
    for lot in lots:
        db.delete(lot)
    db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == row.comp_code,
        models.AccountTransaction.transaction_no == (transaction_no or row.purchase_no),
        models.AccountTransaction.transaction_type == "PURCHASE_PAYABLE",
    ).delete(synchronize_session=False)


@app.get("/api/v1/companies/{comp_code}/purchase-options")
def get_purchase_options(comp_code: str, transaction_date: date,
                         supplier_query: str = "", product_query: str = "",
                         db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db)
    suppliers_query = (db.query(models.CompanyAccount, models.Account)
                 .join(models.Account, models.Account.account_id == models.CompanyAccount.account_id)
                 .filter(models.CompanyAccount.comp_code == comp_code,
                         models.CompanyAccount.use_yn == True,
                         models.CompanyAccount.trade_stop_yn == False,
                         models.CompanyAccount.purchase_yn == True,
                         models.Account.use_yn == True))
    supplier_keyword = supplier_query.strip()
    if supplier_keyword:
        pattern = f"%{supplier_keyword}%"
        suppliers_query = suppliers_query.filter(
            (models.Account.account_name.like(pattern)) |
            (models.Account.account_code.like(pattern)) |
            (models.Account.biz_no.like(pattern))
        )
    else:
        suppliers_query = suppliers_query.filter(models.Account.account_id == -1)
    suppliers = suppliers_query.order_by(models.Account.account_name).limit(50).all()

    products_query = db.query(models.Product).filter(models.Product.use_yn == True)
    product_keyword = product_query.strip()
    if product_keyword:
        pattern = f"%{product_keyword}%"
        products_query = products_query.filter(
            (models.Product.product_name.like(pattern)) |
            (models.Product.product_code.like(pattern)) |
            (models.Product.specification.like(pattern))
        )
    else:
        products_query = products_query.filter(models.Product.product_id == -1)
    products = products_query.order_by(models.Product.product_name, models.Product.product_code).limit(50).all()
    warehouses = (db.query(models.Warehouse).join(models.CompanyWarehouse)
                  .filter(models.CompanyWarehouse.comp_code == comp_code,
                          models.CompanyWarehouse.use_yn == True,
                          models.Warehouse.use_yn == True)
                  .order_by(models.Warehouse.warehouse_name).all())
    trade = get_trade_input_options(comp_code, transaction_date, db)
    return {
        "suppliers": [{"account_id": a.account_id, "account_code": a.account_code,
                       "account_name": a.account_name} for _, a in suppliers],
        "products": [{"product_id": p.product_id, "product_code": p.product_code,
                      "product_name": p.product_name, "tax_type": p.tax_type} for p in products],
        "warehouses": [{"warehouse_id": w.warehouse_id, "warehouse_code": w.warehouse_code,
                         "warehouse_name": w.warehouse_name} for w in warehouses],
        **trade,
    }


@app.get("/api/v1/companies/{comp_code}/purchases")
def get_purchases(comp_code: str, db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db)
    rows = db.query(models.Purchase).filter(models.Purchase.comp_code == comp_code).order_by(
        models.Purchase.purchase_date.desc(), models.Purchase.purchase_id.desc()).all()
    return [_purchase_result(row) for row in rows]


@app.post("/api/v1/companies/{comp_code}/purchases", status_code=status.HTTP_201_CREATED)
def create_purchase(comp_code: str, data: PurchaseInput, request: Request,
                    db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db); _purchase_supplier(db, comp_code, data.account_id)
    ensure_period_open(db, comp_code, data.purchase_date)
    prepared = _prepare_purchase_lines(db, comp_code, data.purchase_date, data.items)
    totals = summarize_purchase(prepared)
    row = models.Purchase(
        comp_code=comp_code, purchase_no=allocate_document_no(db, comp_code, "PURCHASE", data.purchase_date),
        purchase_date=data.purchase_date, account_id=data.account_id, memo=data.memo,
        document_status="DRAFT", created_by=request.state.user_id,
        updated_by=request.state.user_id, **totals,
    )
    row.items = [models.PurchaseItem(**item) for item in prepared]
    db.add(row)
    try:
        db.flush()
        if data.finalize:
            _materialize_purchase(db, row)
            apply_status_transition(row, "CONFIRMED", request.state.user_id)
        db.commit()
    except HTTPException:
        db.rollback(); raise
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="전표번호·Detail 순번 또는 참조자료 중복/연결을 확인하세요.")
    db.refresh(row); return _purchase_result(row)


@app.put("/api/v1/companies/{comp_code}/purchases/{purchase_id}")
def update_purchase(comp_code: str, purchase_id: int, data: PurchaseInput,
                    request: Request, db: Session = Depends(get_db)):
    row = _purchase_or_404(db, comp_code, purchase_id)
    if row.document_status == "CANCELLED":
        raise HTTPException(status_code=400, detail="취소된 상품매입전표는 수정할 수 없습니다.")
    ensure_period_open(db, comp_code, row.purchase_date)
    ensure_period_open(db, comp_code, data.purchase_date)
    _purchase_supplier(db, comp_code, data.account_id)
    prepared = _prepare_purchase_lines(db, comp_code, data.purchase_date, data.items)
    totals = summarize_purchase(prepared)
    was_confirmed = row.document_status == "CONFIRMED"
    old_purchase_no = row.purchase_no
    try:
        if was_confirmed:
            _dematerialize_purchase(db, row, old_purchase_no)
        if row.purchase_date != data.purchase_date:
            row.purchase_no = allocate_document_no(db, comp_code, "PURCHASE", data.purchase_date)
        row.purchase_date = data.purchase_date; row.account_id = data.account_id; row.memo = data.memo
        row.updated_by = request.state.user_id; row.updated_at = datetime.now(timezone.utc)
        for key, value in totals.items(): setattr(row, key, value)
        row.items.clear(); db.flush()
        row.items.extend(models.PurchaseItem(**item) for item in prepared)
        db.flush()
        if data.finalize or was_confirmed:
            _materialize_purchase(db, row)
            if not was_confirmed:
                apply_status_transition(row, "CONFIRMED", request.state.user_id)
        db.commit()
    except HTTPException:
        db.rollback(); raise
    except IntegrityError:
        db.rollback()
        detail = ("후속 입출고에 연결된 매입은 수정할 수 없습니다."
                  if was_confirmed else "Detail 순번 또는 참조자료 연결을 확인하세요.")
        raise HTTPException(status_code=409, detail=detail)
    db.refresh(row); return _purchase_result(row)


@app.delete("/api/v1/companies/{comp_code}/purchases/{purchase_id}")
def delete_purchase(comp_code: str, purchase_id: int, db: Session = Depends(get_db)):
    row = _purchase_or_404(db, comp_code, purchase_id); ensure_draft(row)
    ensure_period_open(db, comp_code, row.purchase_date)
    db.delete(row); db.commit(); return {"message": "작성 중인 일반 매입전표가 삭제되었습니다."}


@app.post("/api/v1/companies/{comp_code}/purchases/{purchase_id}/confirm")
def confirm_purchase(comp_code: str, purchase_id: int, request: Request,
                     db: Session = Depends(get_db)):
    row = _purchase_or_404(db, comp_code, purchase_id); ensure_period_open(db, comp_code, row.purchase_date)
    ensure_draft(row)
    try:
        _materialize_purchase(db, row)
        apply_status_transition(row, "CONFIRMED", request.state.user_id)
        db.commit()
    except HTTPException:
        db.rollback(); raise
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="이미 확정되었거나 LOT·입고·미지급 원장 연결이 중복되었습니다.")
    db.refresh(row); return _purchase_result(row)


@app.post("/api/v1/companies/{comp_code}/purchases/{purchase_id}/cancel")
def cancel_purchase(comp_code: str, purchase_id: int, request: Request,
                    db: Session = Depends(get_db)):
    row = _purchase_or_404(db, comp_code, purchase_id); ensure_period_open(db, comp_code, row.purchase_date)
    # 현재 출고 Vertical Slice 전이므로 매입확정이 만든 입고/LOT만 원자적으로 회수한다.
    # 후속 출고 연결 뒤에는 취소출고 원장을 생성하는 방식으로 교체한다.
    try:
        _dematerialize_purchase(db, row)
        apply_status_transition(row, "CANCELLED", request.state.user_id)
        db.commit()
    except HTTPException:
        db.rollback(); raise
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="후속 입출고에 연결된 매입은 취소할 수 없습니다.")
    db.refresh(row); return _purchase_result(row)


@app.get("/api/v1/companies/{comp_code}/purchase-payable-summary")
def get_purchase_payable_summary(comp_code: str, account_id: int, transaction_date: date,
                                 db: Session = Depends(get_db)):
    _get_company_or_404(comp_code, db); _purchase_supplier(db, comp_code, account_id)
    previous_rows = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == comp_code,
        models.AccountTransaction.account_id == account_id,
        models.AccountTransaction.transaction_date < transaction_date,
    ).all()
    previous = sum((Decimal(row.original_amount) if row.transaction_type in {
        "OPENING_PAYABLE", "PURCHASE_PAYABLE"
    } else -Decimal(row.original_amount) if row.transaction_type == "PAYMENT" else Decimal(0)
                    for row in previous_rows), Decimal(0))
    today_payment = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == comp_code,
        models.AccountTransaction.account_id == account_id,
        models.AccountTransaction.transaction_date == transaction_date,
        models.AccountTransaction.transaction_type == "PAYMENT",
    ).all()
    return {"previous_payable": int(previous),
            "today_payment": int(sum((Decimal(row.original_amount) for row in today_payment), Decimal(0)))}


@app.get("/api/v1/companies/{comp_code}/meatwatch/bl-lookup")
def lookup_meatwatch_bl(comp_code: str, history_no: str, db: Session = Depends(get_db)):
    """미트와치 연동 URL이 설정된 경우 이력번호로 BL번호를 조회한다."""
    _get_company_or_404(comp_code, db)
    template = os.getenv("MEATWATCH_BL_LOOKUP_URL", "").strip()
    if not template:
        raise HTTPException(status_code=503, detail="미트와치 BL 조회 연동정보가 설정되지 않았습니다. BL번호를 수기로 입력해 주세요.")
    token = os.getenv("MEATWATCH_API_TOKEN", "").strip()
    try:
        response = external_httpx.get(template.format(history_no=history_no.strip()),
                                      headers={"Authorization": f"Bearer {token}"} if token else {}, timeout=15)
        response.raise_for_status(); payload = response.json()
        bl_no = payload.get("bl_no") or payload.get("blNo") or payload.get("BL_NO")
        if not bl_no: raise HTTPException(status_code=404, detail="해당 이력번호의 BL번호를 찾지 못했습니다.")
        return {"history_no": history_no, "bl_no": str(bl_no)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"미트와치 BL 조회에 실패했습니다: {exc}")
