from sqlalchemy import text

from database import engine


def table_exists(conn, table_name):
    return conn.execute(
        text("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME=:name"),
        {"name": table_name},
    ).scalar() > 0


def migrate():
    """기존 자료를 변경하지 않고 계층형 경비코드 Master를 추가한다."""
    with engine.begin() as conn:
        if table_exists(conn, "tb_expense_code"):
            print("[OK ] tb_expense_code")
            return
        conn.execute(text("""
            CREATE TABLE tb_expense_code (
                expense_id INT IDENTITY(1,1) NOT NULL
                    CONSTRAINT PK_tb_expense_code PRIMARY KEY,
                expense_code VARCHAR(20) NOT NULL,
                expense_name NVARCHAR(100) NOT NULL,
                parent_expense_id INT NULL,
                expense_level INT NOT NULL
                    CONSTRAINT DF_tb_expense_code_level DEFAULT 1,
                statement_section VARCHAR(30) NOT NULL,
                description NVARCHAR(300) NULL,
                sort_order INT NOT NULL
                    CONSTRAINT DF_tb_expense_code_sort DEFAULT 0,
                use_yn BIT NOT NULL
                    CONSTRAINT DF_tb_expense_code_use DEFAULT 1,
                created_at DATETIMEOFFSET NOT NULL
                    CONSTRAINT DF_tb_expense_code_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT UQ_tb_expense_code_code UNIQUE (expense_code),
                CONSTRAINT CK_tb_expense_code_level CHECK (expense_level BETWEEN 1 AND 4),
                CONSTRAINT FK_tb_expense_code_parent FOREIGN KEY (parent_expense_id)
                    REFERENCES tb_expense_code(expense_id)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IX_tb_expense_code_parent ON tb_expense_code(parent_expense_id)"
        ))
        print("[ADD] tb_expense_code")


if __name__ == "__main__":
    migrate()
