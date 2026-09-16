from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
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
    code_order = (
        models.CodeValue.code.desc()
        if group.sort_direction == "DESC"
        else models.CodeValue.code.asc()
    )
    return query.order_by(code_order).all()


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
    unit_price: float = 0
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


def _product_result(obj, db: Session):
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
        "unit_price": float(obj.unit_price or 0),
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
    return [_product_result(obj, db) for obj in query.order_by(models.Product.product_code).all()]


@app.get("/api/v1/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.Product).filter(models.Product.product_id == product_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="상품이 없습니다.")
    return _product_result(obj, db)


@app.post("/api/v1/products", status_code=status.HTTP_201_CREATED)
def create_product(data: ProductSchema, db: Session = Depends(get_db)):
    code = data.product_code.strip().upper() or _next_product_code(db)
    if db.query(models.Product).filter(models.Product.product_code == code).first():
        raise HTTPException(status_code=409, detail="이미 등록된 상품코드입니다.")
    values = data.model_dump(exclude={"product_code", "code_value_ids"})
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
    for key, value in data.model_dump(exclude={"product_code", "code_value_ids"}).items():
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
