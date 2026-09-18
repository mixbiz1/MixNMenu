"""사용자 회사 접근 및 메뉴 CRUD 권한 Migration (재실행 안전)."""

from sqlalchemy import text

from database import engine
from permissions import MENU_DEFINITIONS


def migrate():
    with engine.begin() as conn:
        first_install = conn.execute(
            text("SELECT CASE WHEN COL_LENGTH('tb_user', 'is_admin') IS NULL THEN 1 ELSE 0 END")
        ).scalar() == 1
        if first_install:
            # SQL Server는 같은 Batch의 ALTER 뒤에 새 Column을 참조하면 전체
            # Batch 컴파일 시점에 207 오류를 낼 수 있으므로 반드시 분리한다.
            conn.execute(text("""
                ALTER TABLE tb_user ADD is_admin BIT NOT NULL
                    CONSTRAINT DF_tb_user_is_admin DEFAULT 0
            """))
            conn.execute(text("""
                UPDATE tb_user SET is_admin = 1
                WHERE user_id = (
                    SELECT TOP 1 user_id FROM tb_user WHERE use_yn = 1
                    ORDER BY CASE WHEN LOWER(user_id) IN ('admin', 'administrator') THEN 0 ELSE 1 END,
                             created_at, user_id
                )
            """))
        conn.execute(text("""
            IF OBJECT_ID('tb_menu_master', 'U') IS NULL
            CREATE TABLE tb_menu_master (
                menu_code VARCHAR(50) NOT NULL CONSTRAINT PK_menu_master PRIMARY KEY,
                menu_name NVARCHAR(100) NOT NULL,
                menu_group NVARCHAR(50) NOT NULL,
                sort_order INT NOT NULL CONSTRAINT DF_menu_master_sort DEFAULT 0,
                use_yn BIT NOT NULL CONSTRAINT DF_menu_master_use DEFAULT 1
            )
        """))
        conn.execute(text("""
            IF OBJECT_ID('tb_user_company_access', 'U') IS NULL
            CREATE TABLE tb_user_company_access (
                user_id VARCHAR(50) NOT NULL,
                comp_code VARCHAR(10) NOT NULL,
                CONSTRAINT PK_user_company_access PRIMARY KEY (user_id, comp_code),
                CONSTRAINT FK_uca_user FOREIGN KEY (user_id) REFERENCES tb_user(user_id),
                CONSTRAINT FK_uca_company FOREIGN KEY (comp_code) REFERENCES tb_company(comp_code)
            )
        """))
        conn.execute(text("""
            IF OBJECT_ID('tb_user_menu_permission', 'U') IS NULL
            CREATE TABLE tb_user_menu_permission (
                user_id VARCHAR(50) NOT NULL,
                menu_code VARCHAR(50) NOT NULL,
                can_read BIT NOT NULL CONSTRAINT DF_ump_read DEFAULT 0,
                can_create BIT NOT NULL CONSTRAINT DF_ump_create DEFAULT 0,
                can_update BIT NOT NULL CONSTRAINT DF_ump_update DEFAULT 0,
                can_delete BIT NOT NULL CONSTRAINT DF_ump_delete DEFAULT 0,
                CONSTRAINT PK_user_menu_permission PRIMARY KEY (user_id, menu_code),
                CONSTRAINT FK_ump_user FOREIGN KEY (user_id) REFERENCES tb_user(user_id),
                CONSTRAINT FK_ump_menu FOREIGN KEY (menu_code) REFERENCES tb_menu_master(menu_code)
            )
        """))
        for code, name, group, order in MENU_DEFINITIONS:
            conn.execute(text("""
                IF EXISTS (SELECT 1 FROM tb_menu_master WHERE menu_code = :code)
                    UPDATE tb_menu_master SET menu_name=:name, menu_group=:grp,
                        sort_order=:sort_order, use_yn=1 WHERE menu_code=:code;
                ELSE
                    INSERT INTO tb_menu_master(menu_code, menu_name, menu_group, sort_order, use_yn)
                    VALUES (:code, :name, :grp, :sort_order, 1);
            """), {"code": code, "name": name, "grp": group, "sort_order": order})
        # 최초 설치 때만 기존 활성계정 전체를 보존한다. 재실행 때 신규 일반계정에
        # 전체권한이 생기지 않도록 이후에는 관리자 명시자료만 보충한다.
        user_filter = "u.use_yn=1" if first_install else "u.is_admin=1"
        conn.execute(text(f"""
            INSERT INTO tb_user_company_access(user_id, comp_code)
            SELECT u.user_id, c.comp_code FROM tb_user u CROSS JOIN tb_company c
            WHERE {user_filter} AND NOT EXISTS (
                SELECT 1 FROM tb_user_company_access x
                WHERE x.user_id=u.user_id AND x.comp_code=c.comp_code)
        """))
        conn.execute(text(f"""
            INSERT INTO tb_user_menu_permission(user_id, menu_code, can_read, can_create, can_update, can_delete)
            SELECT u.user_id, m.menu_code, 1, 1, 1, 1
            FROM tb_user u CROSS JOIN tb_menu_master m
            WHERE {user_filter} AND NOT EXISTS (
                SELECT 1 FROM tb_user_menu_permission x
                WHERE x.user_id=u.user_id AND x.menu_code=m.menu_code)
        """))
    print("User/company/menu permission migration completed.")


if __name__ == "__main__":
    migrate()
