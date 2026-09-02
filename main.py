from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db, engine, Base
import models

# 데이터베이스 테이블 자동 생성 (이미 수동 생성된 DB여도 없는 테이블만 추가 생성)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MixNMenu ERP API", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "Welcome to MixNMenu ERP API Server!"}

@app.get("/api/db-check")
def check_db_status(db: Session = Depends(get_db)):
    """
    FastAPI -> DB 연결 상태를 확인하는 엔드포인트
    """
    try:
        result = db.execute(text("SELECT @@VERSION")).scalar()
        return {
            "status": "success",
            "db_response": "Connected to MS SQL Server",
            "version": result[:60] + "..."
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}