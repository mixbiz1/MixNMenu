"""
MXMN Database Inspector
=======================
목적:
    현재 연결된 MS SQL Server / mxmn_dev 데이터베이스의 실제 구조를
    읽기 전용으로 조사한다.

주의:
    이 프로그램은 DB 구조와 데이터를 변경하지 않는다.
    INSERT / UPDATE / DELETE / ALTER / DROP / CREATE 명령을 사용하지 않는다.

출력:
    1. DB 기본정보
    2. 사용자 테이블 목록
    3. 각 테이블 컬럼
    4. Primary Key
    5. Foreign Key
    6. Unique Constraint
    7. Index
    8. 핵심 테이블 상세정보
"""

from pathlib import Path

from sqlalchemy import inspect, text

from database import engine


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

OUTPUT_FILE = Path(__file__).resolve().parent / "db_inspect_result.txt"

# MXMN에서 우선적으로 살펴볼 가능성이 높은 테이블 이름
# 실제 DB에 존재하지 않아도 오류가 발생하지 않는다.
FOCUS_KEYWORDS = [
    "company",
    "user",
    "employee",
    "partner",
    "customer",
    "item",
    "goods",
    "product",
    "warehouse",
    "stock",
    "inventory",
    "slip",
    "offer",
    "contract",
    "purchase",
    "sale",
    "sales",
    "invoice",
    "payment",
    "receipt",
    "lot",
]


def write_line(file, text_value=""):
    """화면과 결과 파일에 동시에 출력한다."""
    print(text_value)
    file.write(str(text_value) + "\n")


def safe_get_pk(inspector, table_name):
    try:
        return inspector.get_pk_constraint(table_name)
    except Exception as exc:
        return {"error": str(exc)}


def safe_get_fk(inspector, table_name):
    try:
        return inspector.get_foreign_keys(table_name)
    except Exception as exc:
        return [{"error": str(exc)}]


def safe_get_unique(inspector, table_name):
    try:
        return inspector.get_unique_constraints(table_name)
    except Exception as exc:
        return [{"error": str(exc)}]


def safe_get_indexes(inspector, table_name):
    try:
        return inspector.get_indexes(table_name)
    except Exception as exc:
        return [{"error": str(exc)}]


def inspect_database():
    inspector = inspect(engine)

    with OUTPUT_FILE.open("w", encoding="utf-8-sig") as output:

        write_line(output, "=" * 78)
        write_line(output, "MXMN DATABASE INSPECTION REPORT")
        write_line(output, "=" * 78)

        # -------------------------------------------------
        # 1. DB 기본정보
        # -------------------------------------------------

        write_line(output)
        write_line(output, "[1] DATABASE BASIC INFORMATION")
        write_line(output, "-" * 78)

        with engine.connect() as connection:
            db_info = connection.execute(
                text(
                    """
                    SELECT
                        DB_NAME() AS database_name,
                        @@SERVERNAME AS server_name,
                        @@VERSION AS server_version
                    """
                )
            ).mappings().first()

        write_line(output, f"Database : {db_info['database_name']}")
        write_line(output, f"Server   : {db_info['server_name']}")
        write_line(output, f"Version  : {db_info['server_version']}")

        # -------------------------------------------------
        # 2. 전체 사용자 테이블
        # -------------------------------------------------

        write_line(output)
        write_line(output, "[2] USER TABLE LIST")
        write_line(output, "-" * 78)

        table_names = sorted(inspector.get_table_names())

        write_line(output, f"Total tables: {len(table_names)}")
        write_line(output)

        for number, table_name in enumerate(table_names, start=1):
            write_line(output, f"{number:03d}. {table_name}")

        # -------------------------------------------------
        # 3. 전체 테이블 컬럼
        # -------------------------------------------------

        write_line(output)
        write_line(output, "[3] TABLE / COLUMN STRUCTURE")
        write_line(output, "=" * 78)

        for table_name in table_names:

            write_line(output)
            write_line(output, f"TABLE: {table_name}")
            write_line(output, "-" * 78)

            columns = inspector.get_columns(table_name)

            for column in columns:
                name = column.get("name")
                data_type = column.get("type")
                nullable = column.get("nullable")
                default = column.get("default")

                write_line(
                    output,
                    f"  {name:<30} "
                    f"{str(data_type):<25} "
                    f"NULL={nullable!s:<5} "
                    f"DEFAULT={default}"
                )

        # -------------------------------------------------
        # 4. Primary Key
        # -------------------------------------------------

        write_line(output)
        write_line(output, "[4] PRIMARY KEYS")
        write_line(output, "=" * 78)

        for table_name in table_names:

            pk = safe_get_pk(inspector, table_name)

            write_line(output)
            write_line(output, f"TABLE: {table_name}")

            if "error" in pk:
                write_line(output, f"  ERROR: {pk['error']}")
                continue

            columns = pk.get("constrained_columns") or []
            constraint_name = pk.get("name")

            write_line(output, f"  Constraint : {constraint_name}")
            write_line(output, f"  Columns    : {columns}")

        # -------------------------------------------------
        # 5. Foreign Key
        # -------------------------------------------------

        write_line(output)
        write_line(output, "[5] FOREIGN KEYS")
        write_line(output, "=" * 78)

        for table_name in table_names:

            foreign_keys = safe_get_fk(inspector, table_name)

            if not foreign_keys:
                continue

            write_line(output)
            write_line(output, f"TABLE: {table_name}")

            for fk in foreign_keys:

                if "error" in fk:
                    write_line(output, f"  ERROR: {fk['error']}")
                    continue

                write_line(
                    output,
                    "  "
                    f"{fk.get('name')} : "
                    f"{fk.get('constrained_columns')} "
                    f"-> "
                    f"{fk.get('referred_table')}."
                    f"{fk.get('referred_columns')}"
                )

        # -------------------------------------------------
        # 6. UNIQUE
        # -------------------------------------------------

        write_line(output)
        write_line(output, "[6] UNIQUE CONSTRAINTS")
        write_line(output, "=" * 78)

        for table_name in table_names:

            constraints = safe_get_unique(inspector, table_name)

            if not constraints:
                continue

            write_line(output)
            write_line(output, f"TABLE: {table_name}")

            for constraint in constraints:

                if "error" in constraint:
                    write_line(output, f"  ERROR: {constraint['error']}")
                    continue

                write_line(
                    output,
                    f"  {constraint.get('name')} : "
                    f"{constraint.get('column_names')}"
                )

        # -------------------------------------------------
        # 7. INDEX
        # -------------------------------------------------

        write_line(output)
        write_line(output, "[7] INDEXES")
        write_line(output, "=" * 78)

        for table_name in table_names:

            indexes = safe_get_indexes(inspector, table_name)

            if not indexes:
                continue

            write_line(output)
            write_line(output, f"TABLE: {table_name}")

            for index in indexes:

                if "error" in index:
                    write_line(output, f"  ERROR: {index['error']}")
                    continue

                write_line(
                    output,
                    f"  {index.get('name')} : "
                    f"{index.get('column_names')} "
                    f"UNIQUE={index.get('unique')}"
                )

        # -------------------------------------------------
        # 8. MXMN 핵심 후보 테이블
        # -------------------------------------------------

        write_line(output)
        write_line(output, "[8] MXMN FOCUS TABLES")
        write_line(output, "=" * 78)

        focus_tables = []

        for table_name in table_names:

            lower_name = table_name.lower()

            if any(keyword in lower_name for keyword in FOCUS_KEYWORDS):
                focus_tables.append(table_name)

        if not focus_tables:
            write_line(output, "No focus tables detected.")
        else:
            for table_name in focus_tables:

                write_line(output)
                write_line(output, f">>> {table_name}")

                columns = inspector.get_columns(table_name)

                for column in columns:
                    write_line(
                        output,
                        f"    {column.get('name')} : "
                        f"{column.get('type')} "
                        f"(nullable={column.get('nullable')})"
                    )

                pk = safe_get_pk(inspector, table_name)

                if "error" not in pk:
                    write_line(
                        output,
                        f"    PK : {pk.get('constrained_columns')}"
                    )

                foreign_keys = safe_get_fk(inspector, table_name)

                for fk in foreign_keys:
                    if "error" not in fk:
                        write_line(
                            output,
                            "    FK : "
                            f"{fk.get('constrained_columns')} "
                            f"-> {fk.get('referred_table')}."
                            f"{fk.get('referred_columns')}"
                        )

        # -------------------------------------------------
        # 종료
        # -------------------------------------------------

        write_line(output)
        write_line(output, "=" * 78)
        write_line(output, "INSPECTION COMPLETED")
        write_line(output, f"Result file: {OUTPUT_FILE}")
        write_line(output, "=" * 78)


if __name__ == "__main__":
    try:
        inspect_database()

        print()
        print("✅ DB 구조 조회 완료")
        print(f"✅ 결과 파일 생성: {OUTPUT_FILE.name}")
        print("✅ DB 데이터/구조 변경 없음")

    except Exception as exc:
        print()
        print("❌ DB 구조 조회 중 오류가 발생했습니다.")
        print(f"오류 내용: {exc}")
        raise