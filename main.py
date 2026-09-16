from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
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

