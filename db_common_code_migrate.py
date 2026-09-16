from sqlalchemy import text

from database import engine


def table_exists(conn, table_name):
    return conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = :table_name
            """
        ),
        {"table_name": table_name},
    ).scalar() > 0


def column_exists(conn, table_name, column_name):
    return conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = :table_name AND COLUMN_NAME = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar() > 0


with engine.begin() as conn:
    print("=" * 72)
    print("MXMN COMMON CODE MIGRATION")
    print("=" * 72)

    if not table_exists(conn, "tb_code_group"):
        conn.execute(
            text(
                """
                CREATE TABLE tb_code_group (
                    code_group_id INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_tb_code_group PRIMARY KEY,
                    group_code VARCHAR(30) NOT NULL,
                    group_name NVARCHAR(100) NOT NULL,
                    description NVARCHAR(300) NULL,
                    sort_order INT NOT NULL
                        CONSTRAINT DF_tb_code_group_sort_order DEFAULT 0,
                    sort_direction VARCHAR(4) NOT NULL
                        CONSTRAINT DF_tb_code_group_sort_direction DEFAULT 'ASC',
                    system_yn BIT NOT NULL
                        CONSTRAINT DF_tb_code_group_system_yn DEFAULT 0,
                    use_yn BIT NOT NULL
                        CONSTRAINT DF_tb_code_group_use_yn DEFAULT 1,
                    created_at DATETIMEOFFSET NOT NULL
                        CONSTRAINT DF_tb_code_group_created_at DEFAULT SYSDATETIMEOFFSET(),
                    CONSTRAINT UQ_tb_code_group_group_code UNIQUE (group_code)
                )
                """
            )
        )
        print("[ADD] tb_code_group")
    else:
        print("[OK ] tb_code_group")

    # 이미 공통코드 테이블을 만든 사업장에도 안전하게 정렬방식 컬럼만 추가한다.
    if not column_exists(conn, "tb_code_group", "sort_direction"):
        conn.execute(
            text(
                """
                ALTER TABLE tb_code_group
                ADD sort_direction VARCHAR(4) NOT NULL
                    CONSTRAINT DF_tb_code_group_sort_direction DEFAULT 'ASC'
                """
            )
        )
        print("[ADD] tb_code_group.sort_direction")
    else:
        print("[OK ] tb_code_group.sort_direction")

    if not table_exists(conn, "tb_code_value"):
        conn.execute(
            text(
                """
                CREATE TABLE tb_code_value (
                    code_value_id INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_tb_code_value PRIMARY KEY,
                    code_group_id INT NOT NULL,
                    code VARCHAR(30) NOT NULL,
                    code_name NVARCHAR(100) NOT NULL,
                    description NVARCHAR(300) NULL,
                    sort_order INT NOT NULL
                        CONSTRAINT DF_tb_code_value_sort_order DEFAULT 0,
                    extra_value1 NVARCHAR(200) NULL,
                    extra_value2 NVARCHAR(200) NULL,
                    use_yn BIT NOT NULL
                        CONSTRAINT DF_tb_code_value_use_yn DEFAULT 1,
                    created_at DATETIMEOFFSET NOT NULL
                        CONSTRAINT DF_tb_code_value_created_at DEFAULT SYSDATETIMEOFFSET(),
                    CONSTRAINT FK_tb_code_value_group
                        FOREIGN KEY (code_group_id)
                        REFERENCES tb_code_group(code_group_id),
                    CONSTRAINT UQ_tb_code_value_group_code
                        UNIQUE (code_group_id, code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IX_tb_code_value_code_group_id
                ON tb_code_value(code_group_id)
                """
            )
        )
        print("[ADD] tb_code_value")
    else:
        print("[OK ] tb_code_value")

    print("=" * 72)
    print("RESULT: SUCCESS / 기존 데이터 삭제 없음 / 기존 PK·FK 변경 없음")
