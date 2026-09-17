"""MXMN LOT Master Migration.

기존 테이블과 데이터를 변경하지 않고 tb_lot을 추가한다.
여러 번 실행해도 안전하다.
"""
from sqlalchemy import text

from database import engine


def table_exists(conn, table_name):
    return conn.execute(
        text("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME=:name"),
        {"name": table_name},
    ).scalar() > 0


with engine.begin() as conn:
    if not table_exists(conn, "tb_lot"):
        conn.execute(text("""
            CREATE TABLE tb_lot (
                lot_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_tb_lot PRIMARY KEY,
                comp_code VARCHAR(10) NOT NULL,
                lot_code VARCHAR(30) NOT NULL,
                business_lot_no NVARCHAR(50) NULL,
                source_type VARCHAR(20) NOT NULL CONSTRAINT DF_lot_source DEFAULT 'IMPORT',
                product_id INT NOT NULL,
                warehouse_id INT NOT NULL,
                bl_no NVARCHAR(80) NULL,
                container_no VARCHAR(30) NULL,
                history_no VARCHAR(30) NULL,
                origin NVARCHAR(50) NULL,
                est_no NVARCHAR(50) NULL,
                production_date DATE NULL,
                expiry_date DATE NULL,
                individual_cost NUMERIC(18,4) NOT NULL CONSTRAINT DF_lot_cost DEFAULT 0,
                status VARCHAR(20) NOT NULL CONSTRAINT DF_lot_status DEFAULT 'OPEN',
                memo NVARCHAR(1000) NULL,
                use_yn BIT NOT NULL CONSTRAINT DF_lot_use DEFAULT 1,
                created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_lot_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT FK_lot_company FOREIGN KEY (comp_code) REFERENCES tb_company(comp_code),
                CONSTRAINT FK_lot_product FOREIGN KEY (product_id) REFERENCES tb_product(product_id),
                CONSTRAINT FK_lot_warehouse FOREIGN KEY (warehouse_id) REFERENCES tb_warehouse(warehouse_id),
                CONSTRAINT UQ_lot_company_code UNIQUE (comp_code, lot_code),
                CONSTRAINT CK_lot_source CHECK (source_type IN ('IMPORT','DOMESTIC')),
                CONSTRAINT CK_lot_status CHECK (status IN ('OPEN','HOLD','CLOSED')),
                CONSTRAINT CK_lot_cost_nonnegative CHECK (individual_cost >= 0),
                CONSTRAINT CK_lot_dates CHECK (
                    expiry_date IS NULL OR production_date IS NULL OR expiry_date >= production_date
                )
            )
        """))
        conn.execute(text(
            "CREATE INDEX IX_lot_lookup ON tb_lot(comp_code, warehouse_id, product_id, status)"
        ))
        conn.execute(text("CREATE INDEX IX_lot_bl_container ON tb_lot(bl_no, container_no)"))
        conn.execute(text("CREATE INDEX IX_lot_history ON tb_lot(history_no)"))
        print("[ADD] tb_lot")
    else:
        print("[OK ] tb_lot")

    print("RESULT: SUCCESS / 기존 테이블·데이터 변경 없음")
