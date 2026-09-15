from sqlalchemy import text
from database import engine

def col_exists(conn, table, col):
    return conn.execute(text("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME=:t AND COLUMN_NAME=:c
    """), {"t":table,"c":col}).scalar() > 0

def add(conn, table, col, ddl):
    if col_exists(conn, table, col):
        print(f"[OK ] {table}.{col}")
    else:
        conn.execute(text(f"ALTER TABLE {table} ADD {col} {ddl}"))
        print(f"[ADD] {table}.{col}")

with engine.begin() as conn:
    print("="*72)
    print("MXMN ACCOUNT V2 MIGRATION")
    print("="*72)

    # 공통 사업자/거래처 Master
    add(conn,"tb_account","corp_no","NVARCHAR(20) NULL")
    add(conn,"tb_account","zip_code","NVARCHAR(10) NULL")
    add(conn,"tb_account","address","NVARCHAR(200) NULL")
    add(conn,"tb_account","address_detail","NVARCHAR(200) NULL")
    add(conn,"tb_account","uptae","NVARCHAR(100) NULL")
    add(conn,"tb_account","upjong","NVARCHAR(100) NULL")
    add(conn,"tb_account","fax","NVARCHAR(30) NULL")
    add(conn,"tb_account","contact_name","NVARCHAR(50) NULL")
    add(conn,"tb_account","contact_mobile","NVARCHAR(30) NULL")
    add(conn,"tb_account","tax_email","NVARCHAR(150) NULL")
    add(conn,"tb_account","bank_name","NVARCHAR(50) NULL")
    add(conn,"tb_account","bank_account_no","NVARCHAR(80) NULL")
    add(conn,"tb_account","bank_account_holder","NVARCHAR(100) NULL")
    add(conn,"tb_account","memo","NVARCHAR(1000) NULL")

    # 회사별 거래 관계/자동 계산서 설정
    add(conn,"tb_company_account","trade_status","NVARCHAR(20) NOT NULL CONSTRAINT DF_tca_trade_status DEFAULT N'TRADE'")
    add(conn,"tb_company_account","trade_type","NVARCHAR(30) NOT NULL CONSTRAINT DF_tca_trade_type DEFAULT N'GENERAL'")
    add(conn,"tb_company_account","purchase_yn","BIT NOT NULL CONSTRAINT DF_tca_purchase DEFAULT 0")
    add(conn,"tb_company_account","sales_yn","BIT NOT NULL CONSTRAINT DF_tca_sales DEFAULT 0")
    add(conn,"tb_company_account","tax_doc_type","NVARCHAR(20) NOT NULL CONSTRAINT DF_tca_tax_doc_type DEFAULT N'NONE'")
    add(conn,"tb_company_account","sales_tax_auto_yn","BIT NOT NULL CONSTRAINT DF_tca_sales_tax_auto DEFAULT 0")
    add(conn,"tb_company_account","purchase_tax_manage_yn","BIT NOT NULL CONSTRAINT DF_tca_purchase_tax_manage DEFAULT 0")
    add(conn,"tb_company_account","memo","NVARCHAR(1000) NULL")

    print("="*72)
    print("RESULT: SUCCESS / 기존 데이터 삭제 없음 / PK·FK 변경 없음")
