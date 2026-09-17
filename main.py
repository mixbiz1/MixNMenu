from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db, engine, Base
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

    if user.password_hash != req.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="암호가 일치하지 않습니다.",
        )

    return LoginResponse(
        status="success",
        message="로그인 성공",
        user_name=user.user_name,
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
    db: Session = Depends(get_db),
):
    """등록된 모든 회사를 회사코드 순으로 조회한다."""

    return (
        db.query(models.Company)
        .order_by(models.Company.comp_code)
        .all()
    )


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
