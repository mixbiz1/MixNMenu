"""
MXMN Company/User Pre-Migration Inspector
읽기 전용 - DB 변경 없음
"""

from sqlalchemy import text
from database import engine


def print_section(title):
    print("\n" + "=" * 75)
    print(title)
    print("=" * 75)


def main():

    print_section("MXMN COMPANY / USER PRE-MIGRATION INSPECTION")

    with engine.connect() as conn:

        # -------------------------------------------------
        # 1. 현재 DB
        # -------------------------------------------------
        print_section("[1] DATABASE")

        row = conn.execute(
            text("SELECT DB_NAME() AS db_name")
        ).mappings().first()

        print(f"Database : {row['db_name']}")

        # -------------------------------------------------
        # 2. Company 전체 레코드
        # -------------------------------------------------
        print_section("[2] TB_COMPANY")

        rows = conn.execute(
            text("""
                SELECT *
                FROM tb_company
                ORDER BY comp_code
            """)
        ).mappings().all()

        print(f"Company count : {len(rows)}")

        for i, row in enumerate(rows, 1):

            print(f"\n--- COMPANY #{i} ---")

            for key, value in row.items():

                # 너무 긴 값은 화면에서 잘라서 표시
                display_value = value

                if isinstance(value, str) and len(value) > 100:
                    display_value = value[:100] + "..."

                print(f"{key:<25} : {display_value}")

        # -------------------------------------------------
        # 3. User
        # 비밀번호 값 자체는 출력하지 않는다.
        # -------------------------------------------------
        print_section("[3] TB_USER")

        user_columns = conn.execute(
            text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'tb_user'
                ORDER BY ORDINAL_POSITION
            """)
        ).scalars().all()

        safe_columns = [
            col for col in user_columns
            if "password" not in col.lower()
            and "passwd" not in col.lower()
            and col.lower() not in {"pw"}
        ]

        if safe_columns:

            column_sql = ", ".join(
                f"[{col}]" for col in safe_columns
            )

            user_rows = conn.execute(
                text(f"""
                    SELECT {column_sql}
                    FROM tb_user
                """)
            ).mappings().all()

            print(f"User count : {len(user_rows)}")

            for i, row in enumerate(user_rows, 1):

                print(f"\n--- USER #{i} ---")

                for key, value in row.items():
                    print(f"{key:<25} : {value}")

        else:
            print("No safe user columns detected.")

        # -------------------------------------------------
        # 4. Company 관련 FK
        # -------------------------------------------------
        print_section("[4] FOREIGN KEYS REFERENCING TB_COMPANY")

        fk_rows = conn.execute(
            text("""
                SELECT
                    OBJECT_NAME(fkc.parent_object_id) AS child_table,
                    COL_NAME(
                        fkc.parent_object_id,
                        fkc.parent_column_id
                    ) AS child_column,
                    OBJECT_NAME(
                        fkc.referenced_object_id
                    ) AS parent_table,
                    COL_NAME(
                        fkc.referenced_object_id,
                        fkc.referenced_column_id
                    ) AS parent_column,
                    fk.name AS fk_name
                FROM sys.foreign_key_columns fkc
                INNER JOIN sys.foreign_keys fk
                    ON fkc.constraint_object_id = fk.object_id
                WHERE OBJECT_NAME(
                    fkc.referenced_object_id
                ) = 'tb_company'
                ORDER BY child_table, child_column
            """)
        ).mappings().all()

        print(f"FK count : {len(fk_rows)}")

        for row in fk_rows:
            print(
                f"{row['child_table']}.{row['child_column']}"
                f" -> "
                f"{row['parent_table']}.{row['parent_column']}"
                f"   [{row['fk_name']}]"
            )

        # -------------------------------------------------
        # 5. comp_code 사용 테이블
        # -------------------------------------------------
        print_section("[5] TABLES CONTAINING COMP_CODE")

        comp_rows = conn.execute(
            text("""
                SELECT
                    TABLE_NAME,
                    COLUMN_NAME,
                    DATA_TYPE,
                    CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE COLUMN_NAME = 'comp_code'
                ORDER BY TABLE_NAME
            """)
        ).mappings().all()

        for row in comp_rows:

            print(
                f"{row['TABLE_NAME']:<30}"
                f"{row['COLUMN_NAME']:<15}"
                f"{row['DATA_TYPE']:<15}"
                f"length={row['CHARACTER_MAXIMUM_LENGTH']}"
            )

        # -------------------------------------------------
        # 6. 종료
        # -------------------------------------------------
        print_section("INSPECTION COMPLETED")

        print("DB modification : NONE")
        print("INSERT          : NONE")
        print("UPDATE          : NONE")
        print("DELETE          : NONE")
        print("ALTER           : NONE")


if __name__ == "__main__":

    try:
        main()

    except Exception as exc:

        print("\nERROR")
        print(exc)

        raise