"""일반 매입 Header/Detail Vertical Slice Migration (재실행 안전)."""

from sqlalchemy import text
from database import engine


def _count(conn, name):
    return int(conn.execute(text(f"SELECT COUNT(*) FROM dbo.{name}")).scalar_one())


def migrate():
    protected = ["tb_company", "tb_user", "tb_account", "tb_product", "tb_warehouse",
                 "tb_lot", "tb_inbound", "tb_inbound_item", "tb_expense_code"]
    with engine.begin() as conn:
        before = {name: _count(conn, name) for name in protected}
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_purchase', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.tb_purchase (
            purchase_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_purchase PRIMARY KEY,
            comp_code VARCHAR(10) NOT NULL, purchase_no VARCHAR(30) NOT NULL,
            purchase_date DATE NOT NULL, account_id INT NOT NULL,
            document_status VARCHAR(20) NOT NULL CONSTRAINT DF_purchase_status DEFAULT 'DRAFT',
            total_box_qty INT NOT NULL CONSTRAINT DF_purchase_box DEFAULT 0,
            total_weight NUMERIC(18,2) NOT NULL CONSTRAINT DF_purchase_weight DEFAULT 0,
            total_supply_amount NUMERIC(18,0) NOT NULL CONSTRAINT DF_purchase_supply DEFAULT 0,
            total_tax_amount NUMERIC(18,0) NOT NULL CONSTRAINT DF_purchase_tax DEFAULT 0,
            total_amount NUMERIC(18,0) NOT NULL CONSTRAINT DF_purchase_total DEFAULT 0,
            memo NVARCHAR(1000) NULL,
            created_by VARCHAR(50) NOT NULL, created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_purchase_created DEFAULT SYSDATETIMEOFFSET(),
            updated_by VARCHAR(50) NOT NULL, updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_purchase_updated DEFAULT SYSDATETIMEOFFSET(),
            confirmed_by VARCHAR(50) NULL, confirmed_at DATETIMEOFFSET NULL,
            cancelled_by VARCHAR(50) NULL, cancelled_at DATETIMEOFFSET NULL,
            CONSTRAINT UQ_purchase_company_no UNIQUE(comp_code, purchase_no),
            CONSTRAINT FK_purchase_company FOREIGN KEY(comp_code) REFERENCES dbo.tb_company(comp_code),
            CONSTRAINT FK_purchase_account FOREIGN KEY(account_id) REFERENCES dbo.tb_account(account_id),
            CONSTRAINT FK_purchase_created_user FOREIGN KEY(created_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT FK_purchase_updated_user FOREIGN KEY(updated_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT FK_purchase_confirmed_user FOREIGN KEY(confirmed_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT FK_purchase_cancelled_user FOREIGN KEY(cancelled_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT CK_purchase_status CHECK(document_status IN ('DRAFT','CONFIRMED','CANCELLED')),
            CONSTRAINT CK_purchase_totals CHECK(total_box_qty>=0 AND total_weight>=0 AND total_supply_amount>=0 AND total_tax_amount>=0 AND total_amount=total_supply_amount+total_tax_amount)
          );
          CREATE INDEX IX_purchase_lookup ON dbo.tb_purchase(comp_code,purchase_date,document_status);
        END
        """))
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_purchase_item', 'U') IS NULL
        BEGIN
          CREATE TABLE dbo.tb_purchase_item (
            purchase_item_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_purchase_item PRIMARY KEY,
            purchase_id INT NOT NULL, line_no INT NOT NULL, product_id INT NOT NULL, expense_id INT NOT NULL,
            box_qty INT NOT NULL, weight NUMERIC(18,2) NOT NULL, unit_price NUMERIC(18,0) NOT NULL,
            supply_amount NUMERIC(18,0) NOT NULL, tax_code_snapshot VARCHAR(20) NOT NULL,
            tax_name_snapshot NVARCHAR(100) NOT NULL, tax_rate_snapshot NUMERIC(5,2) NOT NULL,
            tax_amount NUMERIC(18,0) NOT NULL, total_amount NUMERIC(18,0) NOT NULL,
            memo NVARCHAR(500) NULL,
            CONSTRAINT UQ_purchase_item_line UNIQUE(purchase_id,line_no),
            CONSTRAINT FK_purchase_item_header FOREIGN KEY(purchase_id) REFERENCES dbo.tb_purchase(purchase_id),
            CONSTRAINT FK_purchase_item_product FOREIGN KEY(product_id) REFERENCES dbo.tb_product(product_id),
            CONSTRAINT FK_purchase_item_expense FOREIGN KEY(expense_id) REFERENCES dbo.tb_expense_code(expense_id),
            CONSTRAINT CK_purchase_item_values CHECK(line_no>0 AND box_qty>=0 AND weight>0 AND unit_price>=0 AND supply_amount>=0 AND tax_rate_snapshot BETWEEN 0 AND 100 AND tax_amount>=0 AND total_amount=supply_amount+tax_amount)
          );
          CREATE INDEX IX_purchase_item_product ON dbo.tb_purchase_item(product_id);
        END
        """))
        # 1차 매입테이블이 이미 있는 DB를 상품매입+즉시입고 구조로 비파괴 확장한다.
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_purchase_item', 'U') IS NOT NULL
        BEGIN
          IF COL_LENGTH('dbo.tb_purchase_item','warehouse_id') IS NULL
            ALTER TABLE dbo.tb_purchase_item ADD warehouse_id INT NULL;
          IF COL_LENGTH('dbo.tb_purchase_item','history_no') IS NULL
            ALTER TABLE dbo.tb_purchase_item ADD history_no VARCHAR(30) NULL;
          IF COL_LENGTH('dbo.tb_purchase_item','bl_no') IS NULL
            ALTER TABLE dbo.tb_purchase_item ADD bl_no VARCHAR(80) NULL;
          IF COL_LENGTH('dbo.tb_purchase_item','lot_id') IS NULL
            ALTER TABLE dbo.tb_purchase_item ADD lot_id INT NULL;
          IF COL_LENGTH('dbo.tb_purchase_item','inbound_item_id') IS NULL
            ALTER TABLE dbo.tb_purchase_item ADD inbound_item_id INT NULL;

          ALTER TABLE dbo.tb_purchase_item ALTER COLUMN expense_id INT NULL;

          IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE name='FK_purchase_item_warehouse')
            ALTER TABLE dbo.tb_purchase_item ADD CONSTRAINT FK_purchase_item_warehouse FOREIGN KEY(warehouse_id) REFERENCES dbo.tb_warehouse(warehouse_id);
          IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE name='FK_purchase_item_lot')
            ALTER TABLE dbo.tb_purchase_item ADD CONSTRAINT FK_purchase_item_lot FOREIGN KEY(lot_id) REFERENCES dbo.tb_lot(lot_id);
          IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE name='FK_purchase_item_inbound')
            ALTER TABLE dbo.tb_purchase_item ADD CONSTRAINT FK_purchase_item_inbound FOREIGN KEY(inbound_item_id) REFERENCES dbo.tb_inbound_item(inbound_item_id);
          IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE name='IX_purchase_item_history' AND object_id=OBJECT_ID('dbo.tb_purchase_item'))
            CREATE INDEX IX_purchase_item_history ON dbo.tb_purchase_item(history_no);
        END
        """))
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_account_transaction', 'U') IS NOT NULL
        BEGIN
          IF EXISTS(SELECT 1 FROM sys.check_constraints WHERE name='CK_account_tx_type')
            ALTER TABLE dbo.tb_account_transaction DROP CONSTRAINT CK_account_tx_type;
          ALTER TABLE dbo.tb_account_transaction ADD CONSTRAINT CK_account_tx_type
            CHECK(transaction_type IN ('OPENING_RECEIVABLE','OPENING_PAYABLE','PURCHASE_PAYABLE','RECEIPT','PAYMENT'));
        END
        """))
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_menu_master','U') IS NOT NULL
        BEGIN
          IF EXISTS(SELECT 1 FROM dbo.tb_menu_master WHERE menu_code='PURCHASE_GENERAL')
            UPDATE dbo.tb_menu_master SET menu_name=N'상품매입등록',menu_group=N'상품입/출고관리',sort_order=210,use_yn=1 WHERE menu_code='PURCHASE_GENERAL';
          ELSE INSERT dbo.tb_menu_master(menu_code,menu_name,menu_group,sort_order,use_yn) VALUES('PURCHASE_GENERAL',N'상품매입등록',N'상품입/출고관리',210,1);
          IF OBJECT_ID('dbo.tb_user_menu_permission','U') IS NOT NULL
            INSERT dbo.tb_user_menu_permission(user_id,menu_code,can_read,can_create,can_update,can_delete)
            SELECT user_id,'PURCHASE_GENERAL',1,1,1,1 FROM dbo.tb_user u WHERE u.is_admin=1 AND NOT EXISTS(SELECT 1 FROM dbo.tb_user_menu_permission p WHERE p.user_id=u.user_id AND p.menu_code='PURCHASE_GENERAL');
        END
        """))
        after = {name: _count(conn, name) for name in protected}
        if before != after:
            raise RuntimeError("일반 매입 Migration 중 기존 자료 건수가 변경되었습니다.")
        for name in ("tb_purchase", "tb_purchase_item"):
            if not conn.execute(text("SELECT OBJECT_ID(:name,'U')"), {"name": f"dbo.{name}"}).scalar():
                raise RuntimeError(f"{name} 생성 검증에 실패했습니다.")
    print("General purchase migration completed.")


if __name__ == "__main__":
    migrate()
