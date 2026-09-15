from sqlalchemy import text
from database import engine

def col_exists(conn, table, col):
    return conn.execute(text("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME=:t AND COLUMN_NAME=:c
    """), {"t":table, "c":col}).scalar() > 0

def add(conn, table, col, ddl):
    if col_exists(conn, table, col):
        print(f"[OK ] {table}.{col}")
    else:
        conn.execute(text(f"ALTER TABLE {table} ADD {col} {ddl}"))
        print(f"[ADD] {table}.{col}")

with engine.begin() as conn:
    print("="*72)
    print("MXMN ACCOUNT V2.1 MIGRATION")
    print("="*72)

    # 회사별 거래처 상태: 회사마다 거래중단 여부가 다를 수 있음
    add(conn, "tb_company_account", "trade_stop_yn",
        "BIT NOT NULL CONSTRAINT DF_tca_trade_stop DEFAULT 0")

    # 이 회사에서 이 거래처에 매출 (세금)계산서를 발행하는 대상인지
    add(conn, "tb_company_account", "invoice_issue_yn",
        "BIT NOT NULL CONSTRAINT DF_tca_invoice_issue DEFAULT 0")

    print("="*72)
    print("RESULT: SUCCESS / 기존 데이터 삭제 없음 / PK·FK 변경 없음")
