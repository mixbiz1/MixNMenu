"""초기자료등록용 원장을 기존 데이터를 보존하면서 추가한다."""

from sqlalchemy import text

from database import engine


def migrate():
    statements = [
        """
        IF OBJECT_ID('tb_inbound', 'U') IS NULL
        BEGIN
            CREATE TABLE tb_inbound (
                inbound_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_inbound PRIMARY KEY,
                comp_code VARCHAR(10) NOT NULL,
                inbound_no VARCHAR(30) NOT NULL,
                inbound_date DATE NOT NULL,
                warehouse_id INT NOT NULL,
                transaction_type VARCHAR(30) NOT NULL,
                memo VARCHAR(1000) NULL,
                created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_inbound_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT FK_inbound_company FOREIGN KEY (comp_code) REFERENCES tb_company(comp_code),
                CONSTRAINT FK_inbound_warehouse FOREIGN KEY (warehouse_id) REFERENCES tb_warehouse(warehouse_id),
                CONSTRAINT UQ_inbound_company_no UNIQUE (comp_code, inbound_no),
                CONSTRAINT CK_inbound_type CHECK (transaction_type IN ('OPENING_INVENTORY','PURCHASE_INBOUND','IMPORT_INBOUND'))
            );
            CREATE INDEX IX_inbound_lookup ON tb_inbound(comp_code, inbound_date, warehouse_id);
        END
        """,
        """
        IF OBJECT_ID('tb_inbound_item', 'U') IS NULL
        BEGIN
            CREATE TABLE tb_inbound_item (
                inbound_item_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_inbound_item PRIMARY KEY,
                inbound_id INT NOT NULL,
                line_no INT NOT NULL,
                product_id INT NOT NULL,
                lot_id INT NOT NULL,
                box_qty INT NOT NULL,
                weight NUMERIC(18,2) NOT NULL,
                individual_cost NUMERIC(18,4) NOT NULL,
                amount NUMERIC(18,0) NOT NULL,
                CONSTRAINT FK_inbound_item_header FOREIGN KEY (inbound_id) REFERENCES tb_inbound(inbound_id),
                CONSTRAINT FK_inbound_item_product FOREIGN KEY (product_id) REFERENCES tb_product(product_id),
                CONSTRAINT FK_inbound_item_lot FOREIGN KEY (lot_id) REFERENCES tb_lot(lot_id),
                CONSTRAINT UQ_inbound_item_line UNIQUE (inbound_id, line_no),
                CONSTRAINT CK_inbound_item_box CHECK (box_qty >= 0),
                CONSTRAINT CK_inbound_item_weight CHECK (weight > 0),
                CONSTRAINT CK_inbound_item_cost CHECK (individual_cost >= 0),
                CONSTRAINT CK_inbound_item_amount CHECK (amount >= 0)
            );
            CREATE INDEX IX_inbound_item_stock ON tb_inbound_item(product_id, lot_id);
        END
        """,
        """
        IF OBJECT_ID('tb_account_transaction', 'U') IS NULL
        BEGIN
            CREATE TABLE tb_account_transaction (
                account_transaction_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_account_tx PRIMARY KEY,
                comp_code VARCHAR(10) NOT NULL,
                transaction_no VARCHAR(30) NOT NULL,
                transaction_date DATE NOT NULL,
                account_id INT NOT NULL,
                transaction_type VARCHAR(30) NOT NULL,
                original_amount NUMERIC(18,0) NOT NULL,
                memo VARCHAR(1000) NULL,
                created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_account_tx_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT FK_account_tx_company FOREIGN KEY (comp_code) REFERENCES tb_company(comp_code),
                CONSTRAINT FK_account_tx_account FOREIGN KEY (account_id) REFERENCES tb_account(account_id),
                CONSTRAINT UQ_account_tx_company_no UNIQUE (comp_code, transaction_no),
                CONSTRAINT CK_account_tx_type CHECK (transaction_type IN ('OPENING_RECEIVABLE','OPENING_PAYABLE','RECEIPT','PAYMENT')),
                CONSTRAINT CK_account_tx_amount CHECK (original_amount > 0)
            );
            CREATE INDEX IX_account_tx_ledger ON tb_account_transaction(comp_code, account_id, transaction_date);
        END
        """,
        """
        IF OBJECT_ID('tb_account_transaction_allocation', 'U') IS NULL
        BEGIN
            CREATE TABLE tb_account_transaction_allocation (
                allocation_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_account_tx_allocation PRIMARY KEY,
                source_transaction_id INT NOT NULL,
                settlement_transaction_id INT NOT NULL,
                allocated_amount NUMERIC(18,0) NOT NULL,
                created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_account_tx_alloc_created DEFAULT SYSDATETIMEOFFSET(),
                CONSTRAINT FK_account_tx_alloc_source FOREIGN KEY (source_transaction_id) REFERENCES tb_account_transaction(account_transaction_id),
                CONSTRAINT FK_account_tx_alloc_settlement FOREIGN KEY (settlement_transaction_id) REFERENCES tb_account_transaction(account_transaction_id),
                CONSTRAINT UQ_account_tx_alloc_pair UNIQUE (source_transaction_id, settlement_transaction_id),
                CONSTRAINT CK_account_tx_alloc_amount CHECK (allocated_amount > 0),
                CONSTRAINT CK_account_tx_alloc_distinct CHECK (source_transaction_id <> settlement_transaction_id)
            );
        END
        """,
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.execute(text("""
            IF COL_LENGTH('tb_product', 'expiry_rule') IS NULL
                ALTER TABLE tb_product ADD expiry_rule VARCHAR(20) NOT NULL
                    CONSTRAINT DF_product_expiry_rule DEFAULT 'AUTO' WITH VALUES;
            IF COL_LENGTH('tb_product', 'shelf_life_days') IS NULL
                ALTER TABLE tb_product ADD shelf_life_days INT NULL;
        """))
        conn.execute(text("""
            UPDATE lot
               SET expiry_date =
                   CASE
                       WHEN UPPER(ISNULL(product.expiry_rule, 'AUTO')) = 'DAYS'
                           THEN DATEADD(DAY, product.shelf_life_days - 1, lot.production_date)
                       ELSE DATEADD(DAY, -1, DATEADD(YEAR, 2, lot.production_date))
                   END
              FROM tb_lot AS lot
              JOIN tb_product AS product ON product.product_id = lot.product_id
             WHERE lot.production_date IS NOT NULL
               AND lot.expiry_date IS NULL
               AND (
                   UPPER(ISNULL(product.expiry_rule, 'AUTO')) = 'FROZEN_2Y'
                   OR (
                       UPPER(ISNULL(product.expiry_rule, 'AUTO')) = 'DAYS'
                       AND product.shelf_life_days IS NOT NULL
                   )
                   OR (
                       UPPER(ISNULL(product.expiry_rule, 'AUTO')) = 'AUTO'
                       AND NOT EXISTS (
                           SELECT 1
                             FROM tb_product_code_assignment AS assignment
                             JOIN tb_code_group AS code_group
                               ON code_group.code_group_id = assignment.code_group_id
                             JOIN tb_code_value AS code_value
                               ON code_value.code_value_id = assignment.code_value_id
                            WHERE assignment.product_id = product.product_id
                              AND code_group.group_code = 'PC004'
                              AND code_value.code_name LIKE N'%냉장%'
                       )
                   )
               );
        """))
    print("[OK] 초기자료등록 원장 Migration 완료")


if __name__ == "__main__":
    migrate()
