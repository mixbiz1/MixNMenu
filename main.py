from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, engine, Base
import models

# 데이터베이스 테이블 자동 생성
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MixNMenu ERP API", version="1.0.0")

class LoginRequest(BaseModel):
    user_id: str
    password: str

class LoginResponse(BaseModel):
    status: str
    message: str
    user_name: str

@app.get("/")
def read_root():
    return {"message": "Welcome to MixNMenu ERP API Server!"}

@app.get("/api/db-check")
def check_db_status(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT @@VERSION")).scalar()
        return {
            "status": "success",
            "db_response": "Connected to MS SQL Server",
            "version": str(result)[:60] + "..." if result else "Unknown"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/v1/auth/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_id == req.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자 ID입니다."
        )
    if not user.use_yn:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다."
        )
    if user.password_hash != req.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="암호가 일치하지 않습니다."
        )

    return LoginResponse(
        status="success",
        message="로그인 성공",
        user_name=user.user_name
    )

from pydantic import BaseModel
from typing import Optional

class CompanySchema(BaseModel):
    comp_code: Optional[str] = "00001"
    comp_name: str
    comp_name_en: Optional[str] = None
    biz_no: str
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

@app.get("/api/v1/company", response_model=CompanySchema)
def get_company(db: Session = Depends(get_db)):
    company = db.query(models.Company).filter(models.Company.comp_code == "00001").first()
    if not company:
        return CompanySchema(comp_code="00001", comp_name="", biz_no="")
    return company

@app.post("/api/v1/company")
def save_company(data: CompanySchema, db: Session = Depends(get_db)):
    company = db.query(models.Company).filter(models.Company.comp_code == data.comp_code).first()
    if company:
        for key, value in data.dict().items():
            setattr(company, key, value)
    else:
        company = models.Company(**data.dict())
        db.add(company)
    db.commit()
    return {"status": "success", "message": "사업장 정보가 저장되었습니다."}
