"""MXMN 창고 Master Migration.

기존 테이블/데이터를 삭제하지 않고 창고 공통 Master, 회사별 사용관계,
회사별 요율 적용기간 테이블을 생성한다. 여러 번 실행해도 안전하다.
"""
from sqlalchemy import text

from database import engine


def table_exists(conn, table_name):
    return conn.execute(text(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME=:name"
    ), {"name": table_name}).scalar() > 0


with engine.begin() as conn:
    if not table_exists(conn, "tb_warehouse"):
        conn.execute(text("""
            CREATE TABLE tb_warehouse (
                warehouse_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_tb_warehouse PRIMARY KEY,
                warehouse_code VARCHAR(20) NOT NULL,
                warehouse_name NVARCHAR(100) NOT NULL,
                warehouse_type VARCHAR(20) NOT NULL CONSTRAINT DF_warehouse_type DEFAULT 'GENERAL',
                storage_type VARCHAR(20) NOT NULL CONSTRAINT DF_warehouse_storage DEFAULT 'FROZEN',
                biz_no VARCHAR(20) NULL,
                zip_code VARCHAR(10) NULL,
                address NVARCHAR(300) NULL,
                phone VARCHAR(30) NULL,
                contact_name NVARCHAR(50) NULL,
                meatwatch_bplc_no VARCHAR(30) NULL,
                memo NVARCHAR(1000) NULL,
                use_yn BIT NOT NULL CONSTRAINT DF_warehouse_use DEFAULT 1,
                created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_warehouse_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT UQ_tb_warehouse_code UNIQUE (warehouse_code)
            )
        """))
        print("[ADD] tb_warehouse")
    else:
        print("[OK ] tb_warehouse")

    if not table_exists(conn, "tb_company_warehouse"):
        conn.execute(text("""
            CREATE TABLE tb_company_warehouse (
                company_warehouse_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_tb_company_warehouse PRIMARY KEY,
                comp_code VARCHAR(10) NOT NULL,
                warehouse_id INT NOT NULL,
                use_yn BIT NOT NULL CONSTRAINT DF_company_warehouse_use DEFAULT 1,
                created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_company_warehouse_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT FK_company_warehouse_company FOREIGN KEY (comp_code) REFERENCES tb_company(comp_code),
                CONSTRAINT FK_company_warehouse_warehouse FOREIGN KEY (warehouse_id) REFERENCES tb_warehouse(warehouse_id),
                CONSTRAINT UQ_company_warehouse UNIQUE (comp_code, warehouse_id)
            )
        """))
        conn.execute(text("CREATE INDEX IX_company_warehouse_company ON tb_company_warehouse(comp_code)"))
        print("[ADD] tb_company_warehouse")
    else:
        print("[OK ] tb_company_warehouse")

    if not table_exists(conn, "tb_warehouse_rate"):
        conn.execute(text("""
            CREATE TABLE tb_warehouse_rate (
                warehouse_rate_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_tb_warehouse_rate PRIMARY KEY,
                comp_code VARCHAR(10) NOT NULL,
                warehouse_id INT NOT NULL,
                valid_from DATE NOT NULL,
                valid_to DATE NULL,
                inbound_rate NUMERIC(12,2) NOT NULL CONSTRAINT DF_warehouse_rate_in DEFAULT 0,
                outbound_rate NUMERIC(12,2) NOT NULL CONSTRAINT DF_warehouse_rate_out DEFAULT 0,
                storage_rate NUMERIC(12,4) NOT NULL CONSTRAINT DF_warehouse_rate_storage DEFAULT 0,
                weighing_rate NUMERIC(12,2) NOT NULL CONSTRAINT DF_warehouse_rate_weighing DEFAULT 0,
                vat_yn BIT NOT NULL CONSTRAINT DF_warehouse_rate_vat DEFAULT 1,
                created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_warehouse_rate_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT FK_warehouse_rate_company FOREIGN KEY (comp_code) REFERENCES tb_company(comp_code),
                CONSTRAINT FK_warehouse_rate_warehouse FOREIGN KEY (warehouse_id) REFERENCES tb_warehouse(warehouse_id),
                CONSTRAINT UQ_warehouse_rate_period UNIQUE (comp_code, warehouse_id, valid_from),
                CONSTRAINT CK_warehouse_rate_period CHECK (valid_to IS NULL OR valid_to >= valid_from),
                CONSTRAINT CK_warehouse_rate_nonnegative CHECK (
                    inbound_rate >= 0 AND outbound_rate >= 0 AND storage_rate >= 0 AND weighing_rate >= 0
                )
            )
        """))
        conn.execute(text("CREATE INDEX IX_warehouse_rate_lookup ON tb_warehouse_rate(comp_code, warehouse_id, valid_from)"))
        print("[ADD] tb_warehouse_rate")
    else:
        print("[OK ] tb_warehouse_rate")

    print("RESULT: SUCCESS / 기존 테이블·데이터 변경 없음")
