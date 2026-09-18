from sqlalchemy import text

from database import engine
from expense_code_defaults import STANDARD_EXPENSE_TREE


def table_exists(conn, table_name):
    return conn.execute(
        text("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME=:name"),
        {"name": table_name},
    ).scalar() > 0


def column_exists(conn, table_name, column_name):
    return conn.execute(text("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME=:table AND COLUMN_NAME=:column
    """), {"table": table_name, "column": column_name}).scalar() > 0


def seed_standard_tree(conn):
    ids = {}
    for index, row in enumerate(STANDARD_EXPENSE_TREE, start=1):
        key, parent_key, name, section, node_type, formula, order, description = row
        parent_id = ids.get(parent_key)
        level = 1 if parent_id is None else conn.execute(text(
            "SELECT expense_level + 1 FROM tb_expense_code WHERE expense_id=:id"
        ), {"id": parent_id}).scalar()
        result = conn.execute(text("""
            INSERT INTO tb_expense_code (
                expense_code, expense_name, parent_expense_id, expense_level,
                statement_section, node_type, formula_code, system_yn,
                description, sort_order, use_yn
            ) OUTPUT INSERTED.expense_id VALUES (
                :code, :name, :parent, :level, :section, :node_type, :formula,
                :system_yn, :description, :sort_order, 1
            )
        """), {
            "code": f"E{index:05d}", "name": name, "parent": parent_id,
            "level": level, "section": section, "node_type": node_type,
            "formula": formula, "system_yn": 1 if level == 1 else 0,
            "description": description, "sort_order": order,
        })
        ids[key] = result.scalar()


def migrate():
    """계층형 경비코드 스키마와 표준 손익구조를 생성한다."""
    with engine.begin() as conn:
        if not table_exists(conn, "tb_expense_code"):
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
                node_type VARCHAR(20) NOT NULL CONSTRAINT DF_tb_expense_code_node DEFAULT 'INPUT',
                formula_code VARCHAR(40) NULL,
                system_yn BIT NOT NULL CONSTRAINT DF_tb_expense_code_system DEFAULT 0,
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
        additions = (
            ("node_type", "VARCHAR(20) NOT NULL CONSTRAINT DF_tb_expense_code_node DEFAULT 'INPUT' WITH VALUES"),
            ("formula_code", "VARCHAR(40) NULL"),
            ("system_yn", "BIT NOT NULL CONSTRAINT DF_tb_expense_code_system DEFAULT 0 WITH VALUES"),
        )
        for column, ddl in additions:
            if not column_exists(conn, "tb_expense_code", column):
                conn.execute(text(f"ALTER TABLE tb_expense_code ADD {column} {ddl}"))
                print(f"[ADD] tb_expense_code.{column}")

        # 1차 경비코드 화면에서 만든 시험자료만 존재하는 버전을 표준구조로 1회 전환한다.
        system_count = conn.execute(text(
            "SELECT COUNT(*) FROM tb_expense_code WHERE system_yn=1"
        )).scalar()
        if system_count == 0:
            while conn.execute(text("SELECT COUNT(*) FROM tb_expense_code")).scalar():
                deleted = conn.execute(text("""
                    DELETE FROM tb_expense_code
                    WHERE expense_id NOT IN (
                        SELECT DISTINCT parent_expense_id FROM tb_expense_code
                        WHERE parent_expense_id IS NOT NULL
                    )
                """))
                if deleted.rowcount == 0:
                    raise RuntimeError("기존 경비코드를 표준구조로 전환할 수 없습니다.")
            seed_standard_tree(conn)
            print("[SEED] standard profit/loss tree")
        else:
            print("[OK ] standard profit/loss tree")


if __name__ == "__main__":
    migrate()
