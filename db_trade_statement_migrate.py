"""Batch 1A SQL Server migration. Explicit invocation only; never runs on API startup."""
from sqlalchemy import text
from database import engine
import models

# These are the existing ERP keys, not a second sale/document identity.
# The dbo schema is also used by db_sales_migrate.py.
REFERENCE_KEYS = tuple(sorted(
    (fk.column.table.schema or 'dbo', fk.column.table.name, fk.column.name)
    for fk in models.TradeStatement.__table__.foreign_keys
))
CHECK_REFERENCE = """
SELECT COUNT(*) FROM sys.schemas s
JOIN sys.tables t ON t.schema_id=s.schema_id
JOIN sys.columns c ON c.object_id=t.object_id
JOIN sys.index_columns ic ON ic.object_id=c.object_id AND ic.column_id=c.column_id
JOIN sys.indexes i ON i.object_id=ic.object_id AND i.index_id=ic.index_id
WHERE s.name=:schema_name AND t.name=:table_name AND c.name=:column_name
 AND i.is_primary_key=1 AND ic.key_ordinal=1
 AND NOT EXISTS (SELECT 1 FROM sys.index_columns other_key
     WHERE other_key.object_id=i.object_id AND other_key.index_id=i.index_id
       AND other_key.key_ordinal>1)
"""

CREATE_TABLE = """
IF OBJECT_ID('dbo.tb_trade_statement','U') IS NULL
BEGIN
 CREATE TABLE dbo.tb_trade_statement (
 statement_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_trade_statement PRIMARY KEY,
 comp_code VARCHAR(10) NOT NULL, sale_id INT NOT NULL,
 document_kind VARCHAR(30) NOT NULL, version INT NOT NULL,
 sale_fingerprint VARCHAR(64) NOT NULL, snapshot_json NVARCHAR(MAX) NOT NULL,
 issued_by VARCHAR(50) NOT NULL, issued_at DATETIMEOFFSET NOT NULL,
 CONSTRAINT FK_statement_company FOREIGN KEY(comp_code) REFERENCES dbo.tb_company(comp_code),
 CONSTRAINT FK_statement_sale FOREIGN KEY(sale_id) REFERENCES dbo.tb_sale(sale_id),
 CONSTRAINT FK_statement_user FOREIGN KEY(issued_by) REFERENCES dbo.tb_user(user_id),
 CONSTRAINT CK_statement_version CHECK(version > 0),
 CONSTRAINT CK_statement_kind CHECK(document_kind='TRADE_STATEMENT'),
 CONSTRAINT UQ_trade_statement_version UNIQUE(comp_code,sale_id,document_kind,version)
 );
END
"""
CREATE_INDEX = """
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.tb_trade_statement') AND name='IX_trade_statement_sale')
 CREATE INDEX IX_trade_statement_sale ON dbo.tb_trade_statement(comp_code,sale_id,version);
"""


def migrate():
    with engine.begin() as conn:
        # Validate all prerequisites before emitting any DDL. A missing tb_sale
        # means the existing sales schema is absent in this database; do not
        # silently create it or point documents at an unrelated ledger table.
        for schema, table, column in REFERENCE_KEYS:
            exists = conn.execute(text(CHECK_REFERENCE), {
                'schema_name': schema, 'table_name': table, 'column_name': column,
            }).scalar_one()
            if not exists:
                raise RuntimeError(
                    f'Missing ERP prerequisite: {schema}.{table}({column}) '
                    'must exist as a single-column primary key. '
                    'No trade-statement DDL has been executed. '
                    'Verify the configured database and existing ERP migrations '
                    '(dbo.tb_sale is created by db_sales_migrate.py).'
                )
        # Separate batches: the second batch is compiled after the table exists.
        conn.execute(text(CREATE_TABLE))
        conn.execute(text(CREATE_INDEX))


if __name__ == '__main__':
    migrate()
