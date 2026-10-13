"""Explicit, idempotent SQL Server Financing phase2 migration. Never imported at startup.
Six new tables and two named CHECK constraints are upgraded without data changes.
FK targets are validated before any DDL; each
CREATE TABLE / CREATE INDEX is executed in its own compilation batch.
"""
from sqlalchemy import text
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateTable, CreateIndex
from database import engine
import models

TABLES = [model.__table__ for model in [models.FinancingCharge,models.FinancingDeposit,
    models.FinancingDepositAssignment,models.FinancingDepositMovement,models.FinancingClosure,models.FinancingBankEvidence]]


LEDGER_TYPES=('OPENING_RECEIVABLE','OPENING_PAYABLE','PURCHASE_PAYABLE','SALES_RECEIVABLE','RECEIPT','PAYMENT',
              'DEPOSIT_RECEIPT','DEPOSIT_RETURN','DEPOSIT_APPLIED')
TYPE_CONSTRAINT_BATCH="""
IF EXISTS (SELECT 1 FROM dbo.tb_account_transaction WHERE transaction_type NOT IN
('OPENING_RECEIVABLE','OPENING_PAYABLE','PURCHASE_PAYABLE','SALES_RECEIVABLE','RECEIPT','PAYMENT','DEPOSIT_RECEIPT','DEPOSIT_RETURN','DEPOSIT_APPLIED'))
    THROW 51000, 'Unsupported existing ledger type; no type constraint changed.', 1;
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE parent_object_id=OBJECT_ID('dbo.tb_account_transaction') AND name='CK_account_tx_type')
    ALTER TABLE dbo.tb_account_transaction DROP CONSTRAINT CK_account_tx_type;
ALTER TABLE dbo.tb_account_transaction WITH CHECK ADD CONSTRAINT CK_account_tx_type CHECK
(transaction_type IN ('OPENING_RECEIVABLE','OPENING_PAYABLE','PURCHASE_PAYABLE','SALES_RECEIVABLE','RECEIPT','PAYMENT','DEPOSIT_RECEIPT','DEPOSIT_RETURN','DEPOSIT_APPLIED'));
"""


CONTRACT_STATUS_BATCH="""
IF EXISTS (SELECT 1 FROM dbo.tb_fin_contract WHERE status NOT IN ('DRAFT','CONFIRMED','ACTIVE','SETTLED','CANCELLED','CLOSED'))
    THROW 51001, 'Unsupported existing financing status; no status constraint changed.', 1;
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE parent_object_id=OBJECT_ID('dbo.tb_fin_contract') AND name='CK_fin_contract_status')
    ALTER TABLE dbo.tb_fin_contract DROP CONSTRAINT CK_fin_contract_status;
ALTER TABLE dbo.tb_fin_contract WITH CHECK ADD CONSTRAINT CK_fin_contract_status CHECK
(status IN ('DRAFT','CONFIRMED','ACTIVE','SETTLED','CANCELLED','CLOSED'));
"""


def statements():
    result = []
    dialect = mssql.dialect()
    preparer = dialect.identifier_preparer
    for table in TABLES:
        sql = str(CreateTable(table).compile(dialect=dialect))
        # All ERP migrations use dbo. Qualify both new tables and their FK targets.
        sql = sql.replace('CREATE TABLE ' + preparer.format_table(table),
                          'CREATE TABLE dbo.' + preparer.format_table(table), 1)
        for fk in table.foreign_keys:
            target = preparer.format_table(fk.column.table)
            sql = sql.replace('REFERENCES ' + target + ' (', 'REFERENCES dbo.' + target + ' (')
        result.append(f"IF OBJECT_ID('dbo.{table.name}','U') IS NULL BEGIN\n{sql}\nEND")
        for index in sorted(table.indexes, key=lambda x: x.name):
            sql = str(CreateIndex(index).compile(dialect=dialect))
            sql = sql.replace(' ON ' + preparer.format_table(table), ' ON dbo.' + preparer.format_table(table), 1)
            result.append(f"IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.{table.name}') AND name='{index.name}')\n{sql}")
    # Existing SQL Server ledger CHECK must explicitly admit the independent deposit types.
    result.append(TYPE_CONSTRAINT_BATCH)
    result.append(CONTRACT_STATUS_BATCH)
    return result


def migrate():
    CHECK_REFERENCE = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=:schema_name AND TABLE_NAME=:table_name AND COLUMN_NAME=:column_name"
    new = {table.name for table in TABLES}
    targets = sorted({(fk.column.table.name, fk.column.name) for table in TABLES
                      for fk in table.foreign_keys if fk.column.table.name not in new})
    targets.append((models.MenuMaster.__tablename__, 'menu_code'))
    targets.append(('tb_account_transaction','transaction_type'))
    targets.append(('tb_fin_contract','status'))
    with engine.begin() as conn:
        for table, column in targets:
            if not conn.execute(text(CHECK_REFERENCE), {'schema_name': 'dbo', 'table_name': table, 'column_name': column}).scalar_one():
                raise RuntimeError(f'Missing ERP prerequisite dbo.{table}({column}); no Financing phase2 DDL executed.')
        for sql in statements(): conn.execute(text(sql))
        # Existing menu/user/company authorization is reused; no blanket permission grants.
        from permissions import MENU_DEFINITIONS
        for code, name, group, order in MENU_DEFINITIONS:
            if code not in {'FINANCING_DEPOSIT','FINANCING_CLOSE'}: continue
            conn.execute(text("""IF NOT EXISTS (SELECT 1 FROM dbo.tb_menu_master WHERE menu_code=:code)
                INSERT INTO dbo.tb_menu_master(menu_code,menu_name,menu_group,sort_order,use_yn)
                VALUES(:code,:name,:group_name,:sort_order,1)"""),
                {'code': code, 'name': name, 'group_name': group, 'sort_order': order})


if __name__ == '__main__': migrate()

