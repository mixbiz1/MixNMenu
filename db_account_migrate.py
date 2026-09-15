"""
MXMN - Account / Company-Account Migration v1

목적
----
1. 기존 tb_account 데이터와 구조를 최대한 보존한다.
2. 거래처 공통 Master에 필요한 기본 컬럼을 보강한다.
3. 회사별 거래처 관계를 관리하는 tb_company_account를 생성한다.
4. 기존 tb_slip_hdr -> tb_account FK를 변경하지 않는다.
5. DELETE / DROP TABLE을 수행하지 않는다.

주의
----
이 스크립트는 DB 구조를 실제로 변경합니다.
반복 실행해도 동일 컬럼/테이블을 중복 생성하지 않도록 작성되었습니다.
"""

from sqlalchemy import text
from database import engine

LINE = "=" * 78


def section(title: str):
    print()
    print(LINE)
    print(title)
    print(LINE)


def table_exists(conn, table_name: str) -> bool:
    sql = text("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = :table_name
    """)
    return conn.execute(sql, {"table_name": table_name}).scalar() > 0


def column_exists(conn, table_name: str, column_name: str) -> bool:
    sql = text("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = :table_name
          AND COLUMN_NAME = :column_name
    """)
    return conn.execute(sql, {
        "table_name": table_name,
        "column_name": column_name,
    }).scalar() > 0


def get_row_count(conn, table_name: str) -> int:
    # table_name은 이 스크립트 내부의 고정된 테이블명만 사용한다.
    return conn.execute(text(f"SELECT COUNT(*) FROM dbo.{table_name}")).scalar()


def add_column_if_missing(conn, table_name: str, column_name: str, definition: str):
    if column_exists(conn, table_name, column_name):
        print(f"[SKIP] {table_name}.{column_name} : already exists")
        return

    conn.execute(text(f"""
        ALTER TABLE dbo.{table_name}
        ADD {column_name} {definition}
    """))
    print(f"[ADD ] {table_name}.{column_name}")


def get_account_fk_count(conn) -> int:
    sql = text("""
        SELECT COUNT(*)
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc
            ON fk.object_id = fkc.constraint_object_id
        INNER JOIN sys.tables parent_table
            ON fkc.parent_object_id = parent_table.object_id
        INNER JOIN sys.columns parent_column
            ON fkc.parent_object_id = parent_column.object_id
           AND fkc.parent_column_id = parent_column.column_id
        INNER JOIN sys.tables referenced_table
            ON fkc.referenced_object_id = referenced_table.object_id
        INNER JOIN sys.columns referenced_column
            ON fkc.referenced_object_id = referenced_column.object_id
           AND fkc.referenced_column_id = referenced_column.column_id
        WHERE parent_table.name = 'tb_slip_hdr'
          AND parent_column.name = 'account_id'
          AND referenced_table.name = 'tb_account'
          AND referenced_column.name = 'account_id'
    """)
    return conn.execute(sql).scalar()


def verify_company_account_constraints(conn):
    sql = text("""
        SELECT
            fk.name AS fk_name,
            OBJECT_NAME(fk.parent_object_id) AS parent_table,
            COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS parent_column,
            OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
            COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc
            ON fk.object_id = fkc.constraint_object_id
        WHERE OBJECT_NAME(fk.parent_object_id) = 'tb_company_account'
        ORDER BY fk.name
    """)
    rows = conn.execute(sql).fetchall()
    print(f"FK count : {len(rows)}")
    for row in rows:
        print(
            f"  {row.parent_table}.{row.parent_column}"
            f" -> {row.referenced_table}.{row.referenced_column}"
            f" [{row.fk_name}]"
        )


def main():
    section("MXMN ACCOUNT / COMPANY-ACCOUNT MIGRATION v1")

    try:
        with engine.begin() as conn:
            section("[1] DATABASE CHECK")
            database_name = conn.execute(text("SELECT DB_NAME()" )).scalar()
            print(f"Database : {database_name}")

            if not database_name:
                raise RuntimeError("현재 데이터베이스명을 확인할 수 없습니다.")
            if database_name.lower() != "mxmn_dev":
                raise RuntimeError(
                    f"예상 DB는 MXMN_DEV인데 현재 DB는 {database_name} 입니다. Migration을 중단합니다."
                )

            section("[2] PRE-MIGRATION SAFETY CHECK")
            required_tables = ["tb_account", "tb_company", "tb_slip_hdr"]
            for table_name in required_tables:
                exists = table_exists(conn, table_name)
                print(f"{table_name:<25} : {'OK' if exists else 'NOT FOUND'}")
                if not exists:
                    raise RuntimeError(f"필수 테이블 {table_name}이 없습니다.")

            account_count_before = get_row_count(conn, "tb_account")
            slip_count_before = get_row_count(conn, "tb_slip_hdr")
            account_fk_before = get_account_fk_count(conn)

            print()
            print(f"tb_account rows          : {account_count_before}")
            print(f"tb_slip_hdr rows         : {slip_count_before}")
            print(f"slip -> account FK count : {account_fk_before}")

            if account_fk_before < 1:
                raise RuntimeError(
                    "기존 tb_slip_hdr.account_id -> tb_account.account_id FK를 찾지 못했습니다."
                )

            section("[3] TB_ACCOUNT MASTER EXTENSION")
            # 거래처 자체의 공통 신원/연락 정보만 둔다.
            # 회사별 거래조건은 tb_company_account에서 관리한다.
            columns = [
                ("account_name_contract", "NVARCHAR(100) NULL"),
                ("corp_no", "VARCHAR(20) NULL"),
                ("zip_code", "VARCHAR(10) NULL"),
                ("address", "NVARCHAR(250) NULL"),
                ("address_detail", "NVARCHAR(250) NULL"),
                ("uptae", "NVARCHAR(100) NULL"),
                ("upjong", "NVARCHAR(100) NULL"),
                ("fax", "VARCHAR(30) NULL"),
                ("mobile", "VARCHAR(30) NULL"),
                ("email", "VARCHAR(150) NULL"),
                ("contact_name", "NVARCHAR(50) NULL"),
                ("contact_mobile", "VARCHAR(30) NULL"),
                ("contact_email", "VARCHAR(150) NULL"),
                ("meatwatch_cust_no", "VARCHAR(50) NULL"),
                ("memo", "NVARCHAR(1000) NULL"),
            ]
            for column_name, definition in columns:
                add_column_if_missing(conn, "tb_account", column_name, definition)

            section("[4] TB_COMPANY_ACCOUNT")
            if not table_exists(conn, "tb_company_account"):
                conn.execute(text("""
                    CREATE TABLE dbo.tb_company_account
                    (
                        company_account_id INT IDENTITY(1,1) NOT NULL,
                        comp_code VARCHAR(10) NOT NULL,
                        account_id INT NOT NULL,

                        purchase_yn BIT NOT NULL
                            CONSTRAINT DF_tb_company_account_purchase_yn DEFAULT (0),
                        sales_yn BIT NOT NULL
                            CONSTRAINT DF_tb_company_account_sales_yn DEFAULT (0),
                        use_yn BIT NOT NULL
                            CONSTRAINT DF_tb_company_account_use_yn DEFAULT (1),
                        tax_invoice_yn BIT NOT NULL
                            CONSTRAINT DF_tb_company_account_tax_invoice_yn DEFAULT (1),

                        credit_limit DECIMAL(18,2) NULL,
                        payment_terms NVARCHAR(100) NULL,
                        bank_info NVARCHAR(250) NULL,
                        manager_name NVARCHAR(50) NULL,
                        manager_mobile VARCHAR(30) NULL,
                        manager_email VARCHAR(150) NULL,
                        memo NVARCHAR(1000) NULL,

                        created_at DATETIME2 NOT NULL
                            CONSTRAINT DF_tb_company_account_created_at DEFAULT (SYSUTCDATETIME()),
                        updated_at DATETIME2 NULL,

                        CONSTRAINT PK_tb_company_account
                            PRIMARY KEY (company_account_id),
                        CONSTRAINT FK_tb_company_account_company
                            FOREIGN KEY (comp_code) REFERENCES dbo.tb_company(comp_code),
                        CONSTRAINT FK_tb_company_account_account
                            FOREIGN KEY (account_id) REFERENCES dbo.tb_account(account_id),
                        CONSTRAINT UQ_tb_company_account_company_account
                            UNIQUE (comp_code, account_id)
                    )
                """))
                print("[CREATE] tb_company_account")
            else:
                print("[SKIP] tb_company_account : already exists")

            section("[5] INDEX CHECK")
            conn.execute(text("""
                IF NOT EXISTS (
                    SELECT 1
                    FROM sys.indexes
                    WHERE name = 'IX_tb_company_account_comp_code'
                      AND object_id = OBJECT_ID('dbo.tb_company_account')
                )
                CREATE INDEX IX_tb_company_account_comp_code
                    ON dbo.tb_company_account(comp_code)
            """))
            print("[OK] IX_tb_company_account_comp_code")

            conn.execute(text("""
                IF NOT EXISTS (
                    SELECT 1
                    FROM sys.indexes
                    WHERE name = 'IX_tb_company_account_account_id'
                      AND object_id = OBJECT_ID('dbo.tb_company_account')
                )
                CREATE INDEX IX_tb_company_account_account_id
                    ON dbo.tb_company_account(account_id)
            """))
            print("[OK] IX_tb_company_account_account_id")

            section("[6] POST-MIGRATION VERIFICATION")
            account_count_after = get_row_count(conn, "tb_account")
            slip_count_after = get_row_count(conn, "tb_slip_hdr")
            account_fk_after = get_account_fk_count(conn)
            company_account_exists = table_exists(conn, "tb_company_account")

            print(f"tb_account rows BEFORE   : {account_count_before}")
            print(f"tb_account rows AFTER    : {account_count_after}")
            print(f"tb_slip_hdr rows BEFORE  : {slip_count_before}")
            print(f"tb_slip_hdr rows AFTER   : {slip_count_after}")
            print(f"slip -> account FK BEFORE: {account_fk_before}")
            print(f"slip -> account FK AFTER : {account_fk_after}")
            print(f"tb_company_account       : {'OK' if company_account_exists else 'FAILED'}")

            if account_count_before != account_count_after:
                raise RuntimeError("tb_account 기존 데이터 건수가 변경되었습니다.")
            if slip_count_before != slip_count_after:
                raise RuntimeError("tb_slip_hdr 기존 데이터 건수가 변경되었습니다.")
            if account_fk_after < 1:
                raise RuntimeError("기존 전표-거래처 FK가 유지되지 않았습니다.")
            if not company_account_exists:
                raise RuntimeError("tb_company_account 생성 확인에 실패했습니다.")

            print()
            verify_company_account_constraints(conn)

            section("[7] MIGRATION RESULT")
            print("RESULT              : SUCCESS")
            print("Existing DELETE     : NONE")
            print("Existing TABLE DROP : NONE")
            print("Existing PK change  : NONE")
            print("Existing FK removal : NONE")
            print()
            print("MXMN 거래처 공통 Master + 회사별 거래처 관계 구조 생성 완료")

    except Exception as exc:
        section("MIGRATION FAILED")
        print(f"ERROR : {exc}")
        print()
        print("engine.begin() Transaction이므로 실패한 Migration 작업은 Rollback됩니다.")
        raise


if __name__ == "__main__":
    main()
