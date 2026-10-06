"""Explicit, idempotent SQL Server Batch 2A migration. Never imported at startup.
Only new tables are created. FK targets are validated before any DDL; each
CREATE TABLE / CREATE INDEX is executed in its own compilation batch.
"""
from sqlalchemy import text
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateTable, CreateIndex
from database import engine
import models

TABLES = [models.ContractDocument.__table__, models.ImportCase.__table__,
          models.ImportCaseItem.__table__, models.ImportCostSettlement.__table__,
          models.ImportCostRow.__table__, models.ImportCostAllocation.__table__]


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
    return result


def migrate():
    from db_trade_statement_migrate import CHECK_REFERENCE
    new = {table.name for table in TABLES}
    targets = sorted({(fk.column.table.name, fk.column.name) for table in TABLES
                      for fk in table.foreign_keys if fk.column.table.name not in new})
    targets.append((models.MenuMaster.__tablename__, 'menu_code'))
    with engine.begin() as conn:
        for table, column in targets:
            if not conn.execute(text(CHECK_REFERENCE), {'schema_name': 'dbo', 'table_name': table, 'column_name': column}).scalar_one():
                raise RuntimeError(f'Missing ERP prerequisite dbo.{table}({column}); no Batch 2A DDL executed.')
        for sql in statements(): conn.execute(text(sql))
        # Existing menu/user/company authorization is reused; no blanket permission grants.
        from permissions import MENU_DEFINITIONS
        for code, name, group, order in MENU_DEFINITIONS:
            if code not in {'FINANCING_DOCUMENT','IMPORT_INTAKE','IMPORT_COST'}: continue
            conn.execute(text("""IF NOT EXISTS (SELECT 1 FROM dbo.tb_menu_master WHERE menu_code=:code)
                INSERT INTO dbo.tb_menu_master(menu_code,menu_name,menu_group,sort_order,use_yn)
                VALUES(:code,:name,:group_name,:sort_order,1)"""),
                {'code': code, 'name': name, 'group_name': group, 'sort_order': order})


if __name__ == '__main__': migrate()
