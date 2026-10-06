"""SQL Server batch/FK/rerun verification, without connecting to a real DB."""
import re
import pytest
from test_sales_outbound import main
import models
import db_financing_intake_migrate as migration


class Connection:
    def __init__(self, missing=None):
        self.missing = missing; self.batches = []; self.references = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, statement, params=None):
        if params and 'schema_name' in params:
            self.references.append(params)
            present = (params['table_name'], params['column_name']) != self.missing
            class Result:
                def scalar_one(self): return present
            return Result()
        self.batches.append((str(statement), params))


def install(monkeypatch, connection):
    class Engine:
        def begin(self): return connection
    monkeypatch.setattr(migration, 'engine', Engine())


def test_mssql_tables_fk_unicode_constraints_and_separate_guarded_batches():
    batches = migration.statements()
    creates = [sql for sql in batches if 'CREATE TABLE' in sql]
    assert len(creates) == len(migration.TABLES) == 6
    new = set()
    for table, sql in zip(migration.TABLES, creates):
        assert f"IF OBJECT_ID('dbo.{table.name}','U') IS NULL" in sql
        assert 'CREATE INDEX' not in sql and 'ALTER TABLE' not in sql
        assert 'IDENTITY' in sql
        assert all(column.name in sql for column in table.columns)
        actual = set(re.findall(r'REFERENCES dbo\.(\w+) \((\w+)\)', sql))
        expected = {(fk.column.table.name, fk.column.name) for fk in table.foreign_keys}
        assert actual == expected
        assert all(fk.column.primary_key for fk in table.foreign_keys)
        for fk in table.foreign_keys:
            assert fk.column.table not in migration.TABLES or fk.column.table.name in new
        new.add(table.name)
    assert 'NVARCHAR(max)' in creates[0] and 'NVARCHAR(max)' in creates[-3]
    assert any('UNIQUE' in sql for sql in creates)
    assert any('CHECK' in sql for sql in creates)
    for sql in batches:
        if 'CREATE INDEX' in sql:
            assert 'IF NOT EXISTS' in sql and 'sys.indexes' in sql and 'object_id=OBJECT_ID' in sql


def test_rerun_emits_identical_catalog_guarded_sql_and_checks_all_prerequisites(monkeypatch):
    connection = Connection(); install(monkeypatch, connection)
    migration.migrate(); first = list(connection.batches); migration.migrate()
    assert connection.batches == first * 2
    assert len(first) == len(migration.statements()) + 3
    for sql, params in first[-3:]:
        assert 'IF NOT EXISTS' in sql and 'INSERT INTO dbo.tb_menu_master' in sql
        assert params['code'] in {'FINANCING_DOCUMENT', 'IMPORT_INTAKE', 'IMPORT_COST'}
    existing = {table.name for table in models.Base.metadata.tables.values()} - {t.name for t in migration.TABLES}
    assert all(x['table_name'] in existing for x in connection.references)
    assert any(x['table_name'] == models.Lot.__tablename__ and x['column_name'] == 'lot_id' for x in connection.references)
    assert any(x['table_name'] == models.FinancingContract.__tablename__ for x in connection.references)
    assert not any('DELETE ' in sql or 'UPDATE ' in sql or 'GRANT ' in sql for sql, _ in first)


@pytest.mark.parametrize('missing', [('tb_lot','lot_id'), ('tb_fin_contract','contract_id'), ('tb_menu_master','menu_code')])
def test_missing_prerequisite_stops_before_any_ddl(monkeypatch, missing):
    connection = Connection(missing); install(monkeypatch, connection)
    with pytest.raises(RuntimeError, match='no Batch 2A DDL executed'):
        migration.migrate()
    assert connection.batches == []
