import os
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. .env 환경변수 로드
load_dotenv()

SERVER = os.getenv('DB_SERVER', 'localhost,1433')
DATABASE = os.getenv('DB_NAME', 'mxmn_dev')
USERNAME = os.getenv('DB_USER', 'sa')
PASSWORD = os.getenv('DB_PASSWORD', '')

# 비밀번호 특수문자 안전 인코딩
encoded_password = urllib.parse.quote_plus(PASSWORD) if PASSWORD else ""

# 2. SQLAlchemy 데이터베이스 연결 URL 생성
DATABASE_URL = (
    f"mssql+pyodbc://{USERNAME}:{encoded_password}@{SERVER}/{DATABASE}"
    f"?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
)

# 3. SQLAlchemy 엔진 생성
# fast_executemany=True: SQL Server 대량 INSERT/UPDATE 성능 최화 옵션
engine = create_engine(
    DATABASE_URL,
    echo=False,              # 개발 중 실행되는 SQL 쿼리를 터미널에 출력하려면 True로 변경
    pool_pre_ping=True,      # DB 연결 단절 방지 자동 점검
    fast_executemany=True
)

# 4. DB 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. ORM 모델들이 상속받을 Base 클래스 생성
Base = declarative_base()

# 6. FastAPI 의존성 주입(Dependency Injection)용 DB 세션 생성 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()