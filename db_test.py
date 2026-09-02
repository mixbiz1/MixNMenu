import os
import urllib.parse
import pyodbc
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 1. .env 파일의 환경변수 로드
load_dotenv()

SERVER = os.getenv('DB_SERVER')
DATABASE = os.getenv('DB_NAME')
USERNAME = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')

# 2. pyodbc 직접 연결 테스트
print("=== [1] pyodbc 직접 연결 테스트 ===")
connection_string = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    f"TrustServerCertificate=yes;"
)

try:
    conn = pyodbc.connect(connection_string, timeout=5)
    cursor = conn.cursor()
    cursor.execute("SELECT @@VERSION;")
    row = cursor.fetchone()
    print("✅ pyodbc 연결 성공!")
    print(f"SQL Server 버전: {row[0][:50]}...\n")
    conn.close()
except Exception as e:
    print(f"❌ pyodbc 연결 실패: {e}\n")

# 3. SQLAlchemy ORM 엔진 연결 테스트
print("=== [2] SQLAlchemy 엔진 연결 테스트 ===")
# 비밀번호 특수문자 방어 처리
encoded_password = urllib.parse.quote_plus(PASSWORD) if PASSWORD else ""
db_url = f"mssql+pyodbc://{USERNAME}:{encoded_password}@{SERVER}/{DATABASE}?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"

try:
    engine = create_engine(db_url, echo=False)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("✅ SQLAlchemy 엔진 연결 성공!")
        print(f"테스트 쿼리 결과: {result.scalar()}\n")
except Exception as e:
    print(f"❌ SQLAlchemy 연결 실패: {e}\n")