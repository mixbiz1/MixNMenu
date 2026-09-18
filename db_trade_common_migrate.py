"""거래 공통기반 1차 Migration: 발번·회계기간·세금코드 (재실행 안전)."""

from sqlalchemy import text

from database import engine


def _count(conn, table_name: str) -> int:
    return int(conn.execute(text(f"SELECT COUNT(*) FROM dbo.{table_name}")).scalar_one())


def migrate():
    protected = [
        "tb_company", "tb_user", "tb_account", "tb_product", "tb_warehouse",
        "tb_lot", "tb_inbound", "tb_inbound_item", "tb_expense_code",
    ]
    with engine.begin() as conn:
        before = {name: _count(conn, name) for name in protected}

        conn.execute(text("""
            IF OBJECT_ID('dbo.tb_document_sequence', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.tb_document_sequence (
                    document_sequence_id INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_document_sequence PRIMARY KEY,
                    comp_code VARCHAR(10) NOT NULL,
                    document_type VARCHAR(30) NOT NULL,
                    sequence_date DATE NOT NULL,
                    last_number INT NOT NULL CONSTRAINT DF_document_sequence_last DEFAULT 0,
                    updated_at DATETIMEOFFSET NOT NULL
                        CONSTRAINT DF_document_sequence_updated DEFAULT SYSDATETIMEOFFSET(),
                    CONSTRAINT FK_document_sequence_company FOREIGN KEY (comp_code)
                        REFERENCES dbo.tb_company(comp_code),
                    CONSTRAINT UQ_document_sequence_scope
                        UNIQUE (comp_code, document_type, sequence_date),
                    CONSTRAINT CK_document_sequence_last CHECK (last_number >= 0)
                );
            END
        """))
        conn.execute(text("""
            IF OBJECT_ID('dbo.tb_accounting_period', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.tb_accounting_period (
                    accounting_period_id INT IDENTITY(1,1) NOT NULL
                        CONSTRAINT PK_accounting_period PRIMARY KEY,
                    comp_code VARCHAR(10) NOT NULL,
                    period_year INT NOT NULL,
                    period_month INT NOT NULL,
                    period_status VARCHAR(20) NOT NULL
                        CONSTRAINT DF_accounting_period_status DEFAULT 'OPEN',
                    closed_by VARCHAR(50) NULL,
                    closed_at DATETIMEOFFSET NULL,
                    created_by VARCHAR(50) NOT NULL,
                    created_at DATETIMEOFFSET NOT NULL
                        CONSTRAINT DF_accounting_period_created DEFAULT SYSDATETIMEOFFSET(),
                    updated_by VARCHAR(50) NOT NULL,
                    updated_at DATETIMEOFFSET NOT NULL
                        CONSTRAINT DF_accounting_period_updated DEFAULT SYSDATETIMEOFFSET(),
                    CONSTRAINT FK_accounting_period_company FOREIGN KEY (comp_code)
                        REFERENCES dbo.tb_company(comp_code),
                    CONSTRAINT FK_accounting_period_closed_user FOREIGN KEY (closed_by)
                        REFERENCES dbo.tb_user(user_id),
                    CONSTRAINT FK_accounting_period_created_user FOREIGN KEY (created_by)
                        REFERENCES dbo.tb_user(user_id),
                    CONSTRAINT FK_accounting_period_updated_user FOREIGN KEY (updated_by)
                        REFERENCES dbo.tb_user(user_id),
                    CONSTRAINT UQ_accounting_period UNIQUE (comp_code, period_year, period_month),
                    CONSTRAINT CK_accounting_period_month CHECK (period_month BETWEEN 1 AND 12),
                    CONSTRAINT CK_accounting_period_status CHECK (period_status IN ('OPEN','CLOSED')),
                    CONSTRAINT CK_accounting_period_close_audit CHECK (
                        (period_status='OPEN' AND closed_by IS NULL AND closed_at IS NULL)
                        OR (period_status='CLOSED' AND closed_by IS NOT NULL AND closed_at IS NOT NULL)
                    )
                );
                CREATE INDEX IX_accounting_period_lookup
                    ON dbo.tb_accounting_period(comp_code, period_year, period_month, period_status);
            END
        """))
        conn.execute(text("""
            IF OBJECT_ID('dbo.tb_tax_code', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.tb_tax_code (
                    tax_code VARCHAR(20) NOT NULL CONSTRAINT PK_tax_code PRIMARY KEY,
                    tax_name NVARCHAR(100) NOT NULL,
                    tax_kind VARCHAR(20) NOT NULL,
                    tax_rate NUMERIC(5,2) NOT NULL,
                    valid_from DATE NOT NULL,
                    valid_to DATE NULL,
                    sort_order INT NOT NULL CONSTRAINT DF_tax_code_sort DEFAULT 0,
                    use_yn BIT NOT NULL CONSTRAINT DF_tax_code_use DEFAULT 1,
                    created_at DATETIMEOFFSET NOT NULL
                        CONSTRAINT DF_tax_code_created DEFAULT SYSDATETIMEOFFSET(),
                    CONSTRAINT CK_tax_code_kind CHECK (tax_kind IN ('TAXABLE','ZERO','EXEMPT')),
                    CONSTRAINT CK_tax_code_rate CHECK (tax_rate BETWEEN 0 AND 100),
                    CONSTRAINT CK_tax_code_dates CHECK (valid_to IS NULL OR valid_to >= valid_from)
                );
            END
        """))
        conn.execute(text("""
            MERGE dbo.tb_tax_code AS target
            USING (VALUES
                ('VAT10', N'과세 10%', 'TAXABLE', CAST(10.00 AS NUMERIC(5,2)), CAST('2000-01-01' AS DATE), 10),
                ('ZERO', N'영세율', 'ZERO', CAST(0.00 AS NUMERIC(5,2)), CAST('2000-01-01' AS DATE), 20),
                ('EXEMPT', N'면세', 'EXEMPT', CAST(0.00 AS NUMERIC(5,2)), CAST('2000-01-01' AS DATE), 30)
            ) AS source(tax_code, tax_name, tax_kind, tax_rate, valid_from, sort_order)
            ON target.tax_code = source.tax_code
            WHEN NOT MATCHED THEN INSERT
                (tax_code, tax_name, tax_kind, tax_rate, valid_from, sort_order, use_yn)
                VALUES (source.tax_code, source.tax_name, source.tax_kind,
                        source.tax_rate, source.valid_from, source.sort_order, 1);
        """))
        # 사용자·권한 단계가 완료된 DB에 신규 API 권한코드를 함께 등록한다.
        conn.execute(text("""
            IF OBJECT_ID('dbo.tb_menu_master', 'U') IS NOT NULL
            BEGIN
                IF EXISTS (SELECT 1 FROM dbo.tb_menu_master WHERE menu_code='TRADE_COMMON')
                    UPDATE dbo.tb_menu_master
                       SET menu_name=N'거래 공통설정', menu_group=N'거래관리',
                           sort_order=200, use_yn=1
                     WHERE menu_code='TRADE_COMMON';
                ELSE
                    INSERT INTO dbo.tb_menu_master
                        (menu_code, menu_name, menu_group, sort_order, use_yn)
                    VALUES ('TRADE_COMMON', N'거래 공통설정', N'거래관리', 200, 1);

                IF OBJECT_ID('dbo.tb_user_menu_permission', 'U') IS NOT NULL
                    INSERT INTO dbo.tb_user_menu_permission
                        (user_id, menu_code, can_read, can_create, can_update, can_delete)
                    SELECT user_id, 'TRADE_COMMON', 1, 1, 1, 1
                      FROM dbo.tb_user AS u
                     WHERE u.is_admin=1 AND NOT EXISTS (
                         SELECT 1 FROM dbo.tb_user_menu_permission AS p
                          WHERE p.user_id=u.user_id AND p.menu_code='TRADE_COMMON'
                     );
            END
        """))

        after = {name: _count(conn, name) for name in protected}
        if before != after:
            raise RuntimeError("거래 공통기반 Migration 중 기존 Master/원장 건수가 변경되었습니다.")
        seeded = conn.execute(text("""
            SELECT COUNT(*) FROM dbo.tb_tax_code
             WHERE tax_code IN ('VAT10','ZERO','EXEMPT')
        """)).scalar_one()
        if seeded != 3:
            raise RuntimeError("기본 세금코드 검증에 실패했습니다.")
        for table_name in ("tb_document_sequence", "tb_accounting_period", "tb_tax_code"):
            exists = conn.execute(text("SELECT OBJECT_ID(:name, 'U')"), {"name": f"dbo.{table_name}"}).scalar()
            if not exists:
                raise RuntimeError(f"{table_name} 생성 검증에 실패했습니다.")
    print("Trade common foundation migration completed.")


if __name__ == "__main__":
    migrate()
