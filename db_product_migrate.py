from sqlalchemy import text

from database import engine


def table_exists(conn, table_name):
    return conn.execute(
        text("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME=:name"),
        {"name": table_name},
    ).scalar() > 0


def column_exists(conn, table_name, column_name):
    return conn.execute(
        text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME=:table AND COLUMN_NAME=:column"
        ),
        {"table": table_name, "column": column_name},
    ).scalar() > 0


def constraint_exists(conn, constraint_name):
    return conn.execute(
        text("SELECT COUNT(*) FROM sys.foreign_keys WHERE name=:name"),
        {"name": constraint_name},
    ).scalar() > 0


with engine.begin() as conn:
    print("=" * 72)
    print("MXMN PRODUCT MASTER MIGRATION")
    print("=" * 72)

    if not table_exists(conn, "tb_product_category"):
        conn.execute(text("""
            CREATE TABLE tb_product_category (
                category_id INT IDENTITY(1,1) NOT NULL
                    CONSTRAINT PK_tb_product_category PRIMARY KEY,
                category_code VARCHAR(20) NOT NULL,
                category_name NVARCHAR(100) NOT NULL,
                parent_category_id INT NULL,
                category_level INT NOT NULL
                    CONSTRAINT DF_tb_product_category_level DEFAULT 1,
                description NVARCHAR(300) NULL,
                sort_order INT NOT NULL
                    CONSTRAINT DF_tb_product_category_sort DEFAULT 0,
                use_yn BIT NOT NULL
                    CONSTRAINT DF_tb_product_category_use DEFAULT 1,
                created_at DATETIMEOFFSET NOT NULL
                    CONSTRAINT DF_tb_product_category_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT UQ_tb_product_category_code UNIQUE (category_code),
                CONSTRAINT FK_tb_product_category_parent FOREIGN KEY (parent_category_id)
                    REFERENCES tb_product_category(category_id)
            )
        """))
        print("[ADD] tb_product_category")
    else:
        print("[OK ] tb_product_category")

    if not table_exists(conn, "tb_product"):
        conn.execute(text("""
            CREATE TABLE tb_product (
                product_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_tb_product PRIMARY KEY,
                product_code VARCHAR(30) NOT NULL,
                product_name NVARCHAR(100) NOT NULL,
                category_id INT NULL,
                specification NVARCHAR(200) NULL,
                memo NVARCHAR(1000) NULL,
                category NVARCHAR(50) NULL,
                origin NVARCHAR(50) NULL,
                meat_regn_code VARCHAR(10) NULL,
                meat_regn_name NVARCHAR(50) NULL,
                tax_type VARCHAR(1) NOT NULL CONSTRAINT DF_tb_product_tax DEFAULT '2',
                unit_price NUMERIC(12,2) NOT NULL CONSTRAINT DF_tb_product_price DEFAULT 0,
                use_yn BIT NOT NULL CONSTRAINT DF_tb_product_use DEFAULT 1,
                created_at DATETIMEOFFSET NOT NULL
                    CONSTRAINT DF_tb_product_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT UQ_tb_product_code UNIQUE (product_code),
                CONSTRAINT FK_tb_product_category FOREIGN KEY (category_id)
                    REFERENCES tb_product_category(category_id)
            )
        """))
        print("[ADD] tb_product")
    else:
        for column_name, ddl in (
            ("category_id", "category_id INT NULL"),
            ("specification", "specification NVARCHAR(200) NULL"),
            ("memo", "memo NVARCHAR(1000) NULL"),
        ):
            if not column_exists(conn, "tb_product", column_name):
                conn.execute(text(f"ALTER TABLE tb_product ADD {ddl}"))
                print(f"[ADD] tb_product.{column_name}")
            else:
                print(f"[OK ] tb_product.{column_name}")
        if not constraint_exists(conn, "FK_tb_product_category"):
            conn.execute(text("""
                ALTER TABLE tb_product ADD CONSTRAINT FK_tb_product_category
                FOREIGN KEY (category_id) REFERENCES tb_product_category(category_id)
            """))
            print("[ADD] FK_tb_product_category")

    if not table_exists(conn, "tb_product_code_assignment"):
        conn.execute(text("""
            CREATE TABLE tb_product_code_assignment (
                assignment_id INT IDENTITY(1,1) NOT NULL
                    CONSTRAINT PK_tb_product_code_assignment PRIMARY KEY,
                product_id INT NOT NULL,
                code_group_id INT NOT NULL,
                code_value_id INT NOT NULL,
                created_at DATETIMEOFFSET NOT NULL
                    CONSTRAINT DF_tb_product_code_assignment_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT FK_product_assignment_product FOREIGN KEY (product_id)
                    REFERENCES tb_product(product_id),
                CONSTRAINT FK_product_assignment_group FOREIGN KEY (code_group_id)
                    REFERENCES tb_code_group(code_group_id),
                CONSTRAINT FK_product_assignment_value FOREIGN KEY (code_value_id)
                    REFERENCES tb_code_value(code_value_id),
                CONSTRAINT UQ_product_code_assignment_group UNIQUE (product_id, code_group_id)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IX_product_assignment_product "
            "ON tb_product_code_assignment(product_id)"
        ))
        print("[ADD] tb_product_code_assignment")
    else:
        print("[OK ] tb_product_code_assignment")

    print("=" * 72)
    print("RESULT: SUCCESS / 기존 tb_product 및 전표 FK 보존 / 기존 컬럼 삭제 없음")
