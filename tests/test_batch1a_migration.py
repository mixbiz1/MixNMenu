"""Validate emitted SQL, batch ordering and rerun guards without connecting to a DB."""
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateTable
from test_sales_outbound import main
import db_trade_statement_migrate as migration
import models


class Connection:
    def __init__(self, missing=None):
        self.missing = missing
        self.batches = []
        self.references = []

    def execute(self, sql, params=None):
        if params is not None:
            self.references.append(params)
            key = (params['schema_name'], params['table_name'], params['column_name'])
            present = int(key != self.missing)
            class Result:
                def scalar_one(self): return present
            return Result()
        self.batches.append(str(sql))

    def __enter__(self): return self
    def __exit__(self, *args): return False


def install_connection(monkeypatch, conn):
    class Engine:
        def begin(self): return conn
    monkeypatch.setattr(migration, 'engine', Engine())


def test_migration_separate_batches_rerun_guard_and_model_parity(monkeypatch):
    conn = Connection()
    install_connection(monkeypatch, conn)
    migration.migrate(); migration.migrate()
    assert conn.batches[:2] == conn.batches[2:]
    assert len(conn.references) == 2 * len(migration.REFERENCE_KEYS)
    create,index=conn.batches[:2]
    assert "IF OBJECT_ID('dbo.tb_trade_statement','U') IS NULL" in create
    assert 'CREATE INDEX' not in create and 'IF NOT EXISTS' in index
    assert "object_id=OBJECT_ID('dbo.tb_trade_statement')" in index
    assert "name='IX_trade_statement_sale'" in index
    # All constraints are inside the guarded CREATE TABLE, not separately added.
    assert create.index('CONSTRAINT FK_statement_sale') < create.index('END')
    assert all('ALTER TABLE' not in sql and 'INSERT ' not in sql and 'DELETE ' not in sql and 'UPDATE ' not in sql for sql in conn.batches)
    for column in models.TradeStatement.__table__.columns: assert column.name in create
    compiled=str(CreateTable(models.TradeStatement.__table__).compile(dialect=mssql.dialect()))
    assert 'NTEXT' in compiled or 'NVARCHAR' in compiled
    assert 'UQ_trade_statement_version' in compiled and 'UQ_trade_statement_version' in create


def test_sql_server_foreign_keys_match_actual_erp_models_and_sales_migration():
    import re
    from pathlib import Path
    sale = models.Sale.__table__
    assert sale.name == 'tb_sale'
    assert [column.name for column in sale.primary_key] == ['sale_id']
    actual = set(re.findall(r'REFERENCES dbo\.(\w+)\((\w+)\)', migration.CREATE_TABLE))
    expected = {(fk.column.table.name, fk.column.name)
                for fk in models.TradeStatement.__table__.foreign_keys}
    assert actual == expected
    assert set(migration.REFERENCE_KEYS) == {('dbo', table, column) for table, column in expected}
    for fk in models.TradeStatement.__table__.foreign_keys:
        assert fk.column.primary_key
    # Independent evidence from the pre-existing SQL Server migration, not SQLite create_all.
    legacy = (Path(__file__).resolve().parents[1] / 'db_sales_migrate.py').read_text(encoding='utf-8')
    assert f'CREATE TABLE dbo.{sale.name} (' in legacy
    assert re.search(r'sale_id INT IDENTITY\(1,1\) NOT NULL CONSTRAINT PK_sale PRIMARY KEY', legacy)
    assert 'REFERENCES dbo.tb_sale(sale_id)' in legacy
    assert 'REFERENCES dbo.tb_sale_item(sale_item_id)' in legacy
    assert 'i.is_primary_key=1' in migration.CHECK_REFERENCE
    assert 'other_key.key_ordinal>1' in migration.CHECK_REFERENCE


def test_missing_or_incompatible_sales_primary_key_stops_before_ddl(monkeypatch):
    import pytest
    conn = Connection(missing=('dbo', 'tb_sale', 'sale_id'))
    install_connection(monkeypatch, conn)
    with pytest.raises(RuntimeError, match=r'dbo\.tb_sale\(sale_id\).*single-column primary key'):
        migration.migrate()
    assert conn.batches == []


def test_all_existing_erp_prerequisites_are_checked_before_ddl(monkeypatch):
    import pytest
    conn = Connection(missing=('dbo', 'tb_user', 'user_id'))
    install_connection(monkeypatch, conn)
    with pytest.raises(RuntimeError, match=r'dbo\.tb_user\(user_id\)'):
        migration.migrate()
    assert conn.batches == []


def test_sql_server_issue_and_sale_mutation_use_same_serialization_lock():
    from sqlalchemy.orm import Session
    statement=Session().query(models.Sale).with_hint(models.Sale,'WITH (UPDLOCK, HOLDLOCK)',dialect_name='mssql').with_for_update().filter_by(comp_code='00001',sale_id=1).statement
    compiled=str(statement.compile(dialect=mssql.dialect()))
    assert 'WITH (UPDLOCK, HOLDLOCK)' in compiled
    import inspect,trade_statement_routes
    assert 'UPDLOCK, HOLDLOCK' in inspect.getsource(trade_statement_routes._sale)
    assert 'UPDLOCK, HOLDLOCK' in inspect.getsource(main._sale_or_404)
