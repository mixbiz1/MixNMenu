from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db, engine, Base
import models

# 데이터베이스 테이블 자동 생성 (기존 테이블은 변경하지 않음)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MXMN ERP API", version="1.1.0")


class LoginRequest(BaseModel):
    user_id: str
    password: str


class LoginResponse(BaseModel):
    status: str
    message: str
    user_name: str


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


@app.get("/")
def read_root():
    return {"message": "Welcome to MXMN ERP API Server!"}


@app.get("/api/db-check")
def check_db_status(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT @@VERSION")).scalar()
        return {
            "status": "success",
            "db_response": "Connected to MS SQL Server",
            "version": str(result)[:60] + "..." if result else "Unknown",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/v1/auth/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_id == req.user_id).first()
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


# -----------------------------------------------------------------------------
# Company API - Multi Company Vertical Slice #1
# -----------------------------------------------------------------------------

@app.get("/api/v1/companies", response_model=list[CompanySchema])
def get_companies(db: Session = Depends(get_db)):
    """등록된 모든 회사를 회사코드 순으로 조회한다."""
    return db.query(models.Company).order_by(models.Company.comp_code).all()


@app.get("/api/v1/companies/{comp_code}", response_model=CompanySchema)
def get_company_by_code(comp_code: str, db: Session = Depends(get_db)):
    """회사코드로 회사 한 곳을 조회한다."""
    company = (
        db.query(models.Company)
        .filter(models.Company.comp_code == comp_code)
        .first()
    )
    if not company:
        raise HTTPException(status_code=404, detail="등록되지 않은 회사코드입니다.")
    return company


@app.post("/api/v1/companies", status_code=status.HTTP_201_CREATED)
def create_company(data: CompanySchema, db: Session = Depends(get_db)):
    """새 회사를 등록한다. 이미 존재하는 회사코드는 신규등록할 수 없다."""
    existing = (
        db.query(models.Company)
        .filter(models.Company.comp_code == data.comp_code)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="이미 등록된 회사코드입니다.")

    company = models.Company(**data.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return {"status": "success", "message": "회사 정보가 등록되었습니다."}


@app.put("/api/v1/companies/{comp_code}")
def update_company(
    comp_code: str,
    data: CompanySchema,
    db: Session = Depends(get_db),
):
    """기존 회사 정보를 수정한다. PK인 회사코드는 화면에서 변경하지 않는다."""
    company = (
        db.query(models.Company)
        .filter(models.Company.comp_code == comp_code)
        .first()
    )
    if not company:
        raise HTTPException(status_code=404, detail="등록되지 않은 회사코드입니다.")

    if data.comp_code != comp_code:
        raise HTTPException(status_code=400, detail="회사코드는 수정할 수 없습니다.")

    for key, value in data.model_dump(exclude={"comp_code"}).items():
        setattr(company, key, value)

    db.commit()
    return {"status": "success", "message": "회사 정보가 수정되었습니다."}


# 기존 호출 호환용: 첫 회사 1건 조회. 신규 UI는 위 /companies API를 사용한다.
@app.get("/api/v1/company", response_model=CompanySchema)
def get_legacy_company(db: Session = Depends(get_db)):
    company = db.query(models.Company).order_by(models.Company.comp_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="등록된 회사가 없습니다.")
    return company
