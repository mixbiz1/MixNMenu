"""Additive, re-runnable Financing Contract Phase 1 schema migration."""

from database import engine
from sqlalchemy import text


def migrate():
    with engine.begin() as conn:
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_fin_contract','U') IS NULL
        BEGIN
          CREATE TABLE dbo.tb_fin_contract (
            contract_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_fin_contract PRIMARY KEY,
            comp_code VARCHAR(10) NOT NULL, contract_no VARCHAR(50) NOT NULL,
            contract_type VARCHAR(30) NOT NULL, contract_date DATE NOT NULL,
            contractor_account_id INT NOT NULL, status VARCHAR(20) NOT NULL CONSTRAINT DF_fin_contract_status DEFAULT 'DRAFT',
            customs_date DATE NULL, cost_finalized_date DATE NULL, warehouse_arrival_date DATE NULL, financing_start_date DATE NULL,
            deposit_required BIT NOT NULL CONSTRAINT DF_fin_contract_deposit_required DEFAULT 0,
            deposit_amount NUMERIC(18,0) NOT NULL CONSTRAINT DF_fin_contract_deposit_amount DEFAULT 0,
            deposit_memo NVARCHAR(1000) NULL, memo NVARCHAR(1000) NULL,
            created_by VARCHAR(50) NOT NULL, created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_fin_contract_created DEFAULT SYSDATETIMEOFFSET(),
            updated_by VARCHAR(50) NOT NULL, updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_fin_contract_updated DEFAULT SYSDATETIMEOFFSET(),
            confirmed_by VARCHAR(50) NULL, confirmed_at DATETIMEOFFSET NULL,
            cancelled_by VARCHAR(50) NULL, cancelled_at DATETIMEOFFSET NULL,
            CONSTRAINT UQ_fin_contract_company_no UNIQUE(comp_code,contract_no),
            CONSTRAINT FK_fin_contract_company FOREIGN KEY(comp_code) REFERENCES dbo.tb_company(comp_code),
            CONSTRAINT FK_fin_contract_account FOREIGN KEY(contractor_account_id) REFERENCES dbo.tb_account(account_id),
            CONSTRAINT FK_fin_contract_created FOREIGN KEY(created_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT FK_fin_contract_updated FOREIGN KEY(updated_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT FK_fin_contract_confirmed FOREIGN KEY(confirmed_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT FK_fin_contract_cancelled FOREIGN KEY(cancelled_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT CK_fin_contract_type CHECK(contract_type IN ('IMPORT_AGENCY','BL_TRANSFER','DOMESTIC_PURCHASE')),
            CONSTRAINT CK_fin_contract_status CHECK(status IN ('DRAFT','CONFIRMED','ACTIVE','SETTLED','CANCELLED')),
            CONSTRAINT CK_fin_contract_deposit CHECK(deposit_amount>=0)
          );
          CREATE INDEX IX_fin_contract_lookup ON dbo.tb_fin_contract(comp_code,contract_date,status);
        END
        """))
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_fin_contract_item','U') IS NULL
        BEGIN
          CREATE TABLE dbo.tb_fin_contract_item (
            contract_item_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_fin_contract_item PRIMARY KEY,
            contract_id INT NOT NULL, line_no INT NOT NULL, product_id INT NOT NULL,
            contract_box_qty INT NOT NULL CONSTRAINT DF_fin_contract_item_box DEFAULT 0,
            contract_weight NUMERIC(18,2) NOT NULL CONSTRAINT DF_fin_contract_item_weight DEFAULT 0,
            contract_unit_price NUMERIC(18,0) NULL, memo NVARCHAR(1000) NULL,
            created_by VARCHAR(50) NOT NULL,
            created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_fin_contract_item_created DEFAULT SYSDATETIMEOFFSET(),
            CONSTRAINT UQ_fin_contract_item_line UNIQUE(contract_id,line_no),
            CONSTRAINT FK_fin_contract_item_contract FOREIGN KEY(contract_id) REFERENCES dbo.tb_fin_contract(contract_id),
            CONSTRAINT FK_fin_contract_item_product FOREIGN KEY(product_id) REFERENCES dbo.tb_product(product_id),
            CONSTRAINT FK_fin_contract_item_created FOREIGN KEY(created_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT CK_fin_contract_item_qty CHECK(contract_box_qty>=0 AND contract_weight>=0 AND (contract_box_qty>0 OR contract_weight>0))
          );
          CREATE INDEX IX_fin_contract_item_product ON dbo.tb_fin_contract_item(product_id);
        END
        """))
        conn.execute(text("""
        IF COL_LENGTH('dbo.tb_fin_contract','contract_no') < 50
        BEGIN
          ALTER TABLE dbo.tb_fin_contract DROP CONSTRAINT UQ_fin_contract_company_no;
          ALTER TABLE dbo.tb_fin_contract ALTER COLUMN contract_no VARCHAR(50) NOT NULL;
          ALTER TABLE dbo.tb_fin_contract ADD CONSTRAINT UQ_fin_contract_company_no UNIQUE(comp_code,contract_no);
        END
        """))
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_fin_contract_participant','U') IS NULL
        BEGIN
          CREATE TABLE dbo.tb_fin_contract_participant (
            participant_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_fin_contract_participant PRIMARY KEY,
            contract_id INT NOT NULL, account_id INT NOT NULL, role VARCHAR(30) NOT NULL,
            agreement_status VARCHAR(20) NOT NULL CONSTRAINT DF_fin_participant_agreement DEFAULT 'NOT_REQUIRED',
            agreement_date DATE NULL, effective_date DATE NULL,
            status VARCHAR(20) NOT NULL CONSTRAINT DF_fin_participant_status DEFAULT 'ACTIVE',
            memo NVARCHAR(1000) NULL, created_by VARCHAR(50) NOT NULL,
            created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_fin_participant_created DEFAULT SYSDATETIMEOFFSET(),
            CONSTRAINT UQ_fin_participant_account UNIQUE(contract_id,account_id),
            CONSTRAINT FK_fin_participant_contract FOREIGN KEY(contract_id) REFERENCES dbo.tb_fin_contract(contract_id),
            CONSTRAINT FK_fin_participant_account FOREIGN KEY(account_id) REFERENCES dbo.tb_account(account_id),
            CONSTRAINT FK_fin_participant_created FOREIGN KEY(created_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT CK_fin_participant_role CHECK(role IN ('ORIGINAL_CONTRACTOR','AUTHORIZED_SHIPPER')),
            CONSTRAINT CK_fin_participant_agreement CHECK(agreement_status IN ('NOT_REQUIRED','PENDING','CONFIRMED')),
            CONSTRAINT CK_fin_participant_status CHECK(status IN ('ACTIVE','INACTIVE')),
            CONSTRAINT CK_fin_shipper_agreement CHECK(role<>'AUTHORIZED_SHIPPER' OR agreement_status<>'CONFIRMED' OR agreement_date IS NOT NULL)
          );
          CREATE INDEX IX_fin_participant_account ON dbo.tb_fin_contract_participant(account_id,status);
        END
        """))
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_fin_contract_lot','U') IS NULL
        BEGIN
          CREATE TABLE dbo.tb_fin_contract_lot (
            contract_lot_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_fin_contract_lot PRIMARY KEY,
            contract_id INT NOT NULL, contract_item_id INT NULL, lot_id INT NOT NULL,
            contract_box_qty INT NOT NULL CONSTRAINT DF_fin_contract_lot_box DEFAULT 0,
            contract_weight NUMERIC(18,2) NOT NULL CONSTRAINT DF_fin_contract_lot_weight DEFAULT 0,
            linked_date DATE NOT NULL, status VARCHAR(20) NOT NULL CONSTRAINT DF_fin_contract_lot_status DEFAULT 'ACTIVE',
            conditions_override_json NVARCHAR(MAX) NULL, memo NVARCHAR(1000) NULL,
            created_by VARCHAR(50) NOT NULL,
            created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_fin_contract_lot_created DEFAULT SYSDATETIMEOFFSET(),
            CONSTRAINT UQ_fin_contract_lot UNIQUE(contract_id,lot_id),
            CONSTRAINT FK_fin_contract_lot_contract FOREIGN KEY(contract_id) REFERENCES dbo.tb_fin_contract(contract_id),
            CONSTRAINT FK_fin_contract_lot_lot FOREIGN KEY(lot_id) REFERENCES dbo.tb_lot(lot_id),
            CONSTRAINT FK_fin_contract_lot_created FOREIGN KEY(created_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT CK_fin_contract_lot_qty CHECK(contract_box_qty>=0 AND contract_weight>=0 AND (contract_box_qty>0 OR contract_weight>0)),
            CONSTRAINT CK_fin_contract_lot_status CHECK(status IN ('ACTIVE','CLOSED','CANCELLED'))
          );
          CREATE INDEX IX_fin_contract_lot_lot ON dbo.tb_fin_contract_lot(lot_id,status);
        END
        """))
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_fin_contract_term','U') IS NULL
        BEGIN
          CREATE TABLE dbo.tb_fin_contract_term (
            term_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_fin_contract_term PRIMARY KEY,
            contract_id INT NOT NULL, version INT NOT NULL, effective_from DATE NOT NULL,
            recovery_template VARCHAR(30) NOT NULL CONSTRAINT DF_fin_contract_term_template DEFAULT 'FREE',
            contract_days INT NULL,
            annual_interest_rate NUMERIC(9,6) NOT NULL CONSTRAINT DF_fin_contract_term_interest DEFAULT 0,
            interest_rate_1 NUMERIC(9,6) NULL, interest_period_days_1 INT NULL,
            interest_rate_2 NUMERIC(9,6) NULL, interest_period_days_2 INT NULL,
            brokerage_rate_1 NUMERIC(9,6) NULL, brokerage_rate_2 NUMERIC(9,6) NULL,
            storage_rate_per_kg_day NUMERIC(18,6) NOT NULL CONSTRAINT DF_fin_contract_term_storage DEFAULT 0,
            brokerage_rate NUMERIC(9,6) NOT NULL CONSTRAINT DF_fin_contract_term_brokerage DEFAULT 0,
            inbound_outbound_rate_per_kg NUMERIC(18,6) NOT NULL CONSTRAINT DF_fin_contract_term_inbound DEFAULT 0,
            weighing_rate_per_box NUMERIC(18,6) NOT NULL CONSTRAINT DF_fin_contract_term_weighing DEFAULT 0,
            conditions_json NVARCHAR(MAX) NOT NULL CONSTRAINT DF_fin_contract_term_conditions DEFAULT N'{}',
            change_reason NVARCHAR(1000) NULL, created_by VARCHAR(50) NOT NULL,
            created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_fin_contract_term_created DEFAULT SYSDATETIMEOFFSET(),
            CONSTRAINT UQ_fin_contract_term_version UNIQUE(contract_id,version),
            CONSTRAINT UQ_fin_contract_term_effective UNIQUE(contract_id,effective_from),
            CONSTRAINT FK_fin_contract_term_contract FOREIGN KEY(contract_id) REFERENCES dbo.tb_fin_contract(contract_id),
            CONSTRAINT FK_fin_contract_term_created FOREIGN KEY(created_by) REFERENCES dbo.tb_user(user_id),
            CONSTRAINT CK_fin_contract_term_template CHECK(recovery_template IN ('ALL_IN','EXCLUDE_BROKERAGE','EXCLUDE_BROKERAGE_STORAGE','INTEREST_ONLY','COST_ONLY','FREE')),
            CONSTRAINT CK_fin_contract_term_values CHECK(version>0 AND (contract_days IS NULL OR contract_days>0)
              AND annual_interest_rate>=0 AND storage_rate_per_kg_day>=0 AND brokerage_rate>=0
              AND inbound_outbound_rate_per_kg>=0 AND weighing_rate_per_box>=0)
          );
          CREATE INDEX IX_fin_contract_term_effective ON dbo.tb_fin_contract_term(contract_id,effective_from,version);
        END
        """))
        # Keep ADD COLUMN in its own batch. SQL Server can compile later
        # statements in the same batch before the new column is visible.
        conn.execute(text("""
        IF COL_LENGTH('dbo.tb_fin_contract_lot','contract_item_id') IS NULL
          ALTER TABLE dbo.tb_fin_contract_lot ADD contract_item_id INT NULL;
        """))
        # Check the catalog by table/column relationship so reruns also
        # recognize an equivalent FK or index created under another name.
        conn.execute(text("""
        IF NOT EXISTS (
          SELECT 1 FROM sys.foreign_keys
           WHERE parent_object_id=OBJECT_ID('dbo.tb_fin_contract_lot')
             AND name='FK_fin_contract_lot_item'
        ) AND NOT EXISTS (
          SELECT 1
            FROM sys.foreign_key_columns fkc
            JOIN sys.foreign_keys fk ON fk.object_id=fkc.constraint_object_id
            JOIN sys.columns parent_col ON parent_col.object_id=fkc.parent_object_id
                                      AND parent_col.column_id=fkc.parent_column_id
            JOIN sys.columns ref_col ON ref_col.object_id=fkc.referenced_object_id
                                    AND ref_col.column_id=fkc.referenced_column_id
           WHERE fkc.parent_object_id=OBJECT_ID('dbo.tb_fin_contract_lot')
             AND parent_col.name='contract_item_id'
             AND fkc.referenced_object_id=OBJECT_ID('dbo.tb_fin_contract_item')
             AND ref_col.name='contract_item_id'
        )
          ALTER TABLE dbo.tb_fin_contract_lot ADD CONSTRAINT FK_fin_contract_lot_item
            FOREIGN KEY(contract_item_id) REFERENCES dbo.tb_fin_contract_item(contract_item_id);

        IF NOT EXISTS (
          SELECT 1 FROM sys.indexes
           WHERE object_id=OBJECT_ID('dbo.tb_fin_contract_lot')
             AND name='IX_fin_contract_lot_item'
        ) AND NOT EXISTS (
          SELECT 1
            FROM sys.indexes i
            JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
            JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
           WHERE i.object_id=OBJECT_ID('dbo.tb_fin_contract_lot')
             AND i.is_hypothetical=0 AND ic.key_ordinal=1 AND c.name='contract_item_id'
        )
          CREATE INDEX IX_fin_contract_lot_item ON dbo.tb_fin_contract_lot(contract_item_id);
        """))
        # Backfill missing contract/product items first, including contracts
        # with some pre-existing items. Existing items are never duplicated.
        conn.execute(text("""
        ;WITH legacy AS (
          SELECT l.contract_id, lot.product_id,
                 SUM(l.contract_box_qty) AS contract_box_qty,
                 SUM(l.contract_weight) AS contract_weight,
                 MIN(c.created_by) AS created_by
            FROM dbo.tb_fin_contract_lot l
            JOIN dbo.tb_lot lot ON lot.lot_id=l.lot_id
            JOIN dbo.tb_fin_contract c ON c.contract_id=l.contract_id
           WHERE l.contract_item_id IS NULL
           GROUP BY l.contract_id, lot.product_id
        ), missing AS (
          SELECT legacy.contract_id, legacy.product_id, legacy.contract_box_qty,
                 legacy.contract_weight, legacy.created_by,
                 ROW_NUMBER() OVER(PARTITION BY legacy.contract_id ORDER BY legacy.product_id) AS row_no
            FROM legacy
           WHERE NOT EXISTS (
             SELECT 1 FROM dbo.tb_fin_contract_item i
              WHERE i.contract_id=legacy.contract_id AND i.product_id=legacy.product_id
           )
        ), existing_lines AS (
          SELECT contract_id, MAX(line_no) AS max_line_no
            FROM dbo.tb_fin_contract_item
           GROUP BY contract_id
        )
        INSERT dbo.tb_fin_contract_item
          (contract_id,line_no,product_id,contract_box_qty,contract_weight,created_by)
        SELECT m.contract_id, COALESCE(e.max_line_no,0)+m.row_no, m.product_id,
               m.contract_box_qty, m.contract_weight, m.created_by
          FROM missing m
          LEFT JOIN existing_lines e ON e.contract_id=m.contract_id;
        """))
        # Link every remaining NULL legacy LOT row to the matching product
        # item. TOP(1) keeps this deterministic if an older contract has
        # multiple item rows for the same product.
        conn.execute(text("""
        UPDATE link
           SET contract_item_id=item.contract_item_id
          FROM dbo.tb_fin_contract_lot link
          JOIN dbo.tb_lot lot ON lot.lot_id=link.lot_id
          CROSS APPLY (
            SELECT TOP (1) i.contract_item_id
              FROM dbo.tb_fin_contract_item i
             WHERE i.contract_id=link.contract_id AND i.product_id=lot.product_id
             ORDER BY i.contract_item_id
          ) item
         WHERE link.contract_item_id IS NULL;
        """))
        conn.execute(text("""
        IF COL_LENGTH('dbo.tb_fin_contract_term','interest_rate_1') IS NULL
          ALTER TABLE dbo.tb_fin_contract_term ADD interest_rate_1 NUMERIC(9,6) NULL;
        IF COL_LENGTH('dbo.tb_fin_contract_term','interest_period_days_1') IS NULL
          ALTER TABLE dbo.tb_fin_contract_term ADD interest_period_days_1 INT NULL;
        IF COL_LENGTH('dbo.tb_fin_contract_term','interest_rate_2') IS NULL
          ALTER TABLE dbo.tb_fin_contract_term ADD interest_rate_2 NUMERIC(9,6) NULL;
        IF COL_LENGTH('dbo.tb_fin_contract_term','interest_period_days_2') IS NULL
          ALTER TABLE dbo.tb_fin_contract_term ADD interest_period_days_2 INT NULL;
        IF COL_LENGTH('dbo.tb_fin_contract_term','brokerage_rate_1') IS NULL
          ALTER TABLE dbo.tb_fin_contract_term ADD brokerage_rate_1 NUMERIC(9,6) NULL;
        IF COL_LENGTH('dbo.tb_fin_contract_term','brokerage_rate_2') IS NULL
          ALTER TABLE dbo.tb_fin_contract_term ADD brokerage_rate_2 NUMERIC(9,6) NULL;
        """))
        conn.execute(text("""
        IF OBJECT_ID('dbo.tb_menu_master','U') IS NOT NULL
        BEGIN
          IF EXISTS(SELECT 1 FROM dbo.tb_menu_master WHERE menu_code='FINANCING_CONTRACT')
            UPDATE dbo.tb_menu_master SET menu_name=N'파이낸싱 계약관리',menu_group=N'상품입/출고관리',sort_order=225,use_yn=1 WHERE menu_code='FINANCING_CONTRACT';
          ELSE INSERT dbo.tb_menu_master(menu_code,menu_name,menu_group,sort_order,use_yn)
            VALUES('FINANCING_CONTRACT',N'파이낸싱 계약관리',N'상품입/출고관리',225,1);
          IF OBJECT_ID('dbo.tb_user_menu_permission','U') IS NOT NULL
            INSERT dbo.tb_user_menu_permission(user_id,menu_code,can_read,can_create,can_update,can_delete)
            SELECT user_id,'FINANCING_CONTRACT',1,1,1,1 FROM dbo.tb_user u WHERE u.is_admin=1
              AND NOT EXISTS(SELECT 1 FROM dbo.tb_user_menu_permission p WHERE p.user_id=u.user_id AND p.menu_code='FINANCING_CONTRACT');
        END
        """))


if __name__ == "__main__":
    migrate()
    print("Financing Contract Phase 1 migration completed.")
