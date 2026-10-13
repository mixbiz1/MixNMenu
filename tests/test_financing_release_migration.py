"""SQL Server source/FK/index/batch verification without touching operational DB."""
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateIndex
from test_batch2a_migration import Connection,install
import db_financing_release_migrate as migration
import models


def test_fk_matches_actual_models_and_nullable_sale_unique_is_filtered():
    batches=migration.statements()
    create=next(x for x in batches if 'CREATE TABLE' in x)
    assert 'CREATE TABLE dbo.tb_fin_release' in create
    for fk in models.FinancingRelease.__table__.foreign_keys:
        assert f'REFERENCES dbo.{fk.column.table.name} ({fk.column.name})' in create
    assert 'NVARCHAR(max)' in create or 'NVARCHAR(MAX)' in create
    unique=next(x for x in batches if 'UQ_fin_release_sale' in x)
    assert 'CREATE UNIQUE INDEX' in unique and 'WHERE sale_id IS NOT NULL' in unique
    assert 'IF NOT EXISTS' in unique
    assert 'UNIQUE (sale_id)' not in create
    assert all(not ('CREATE TABLE' in sql and 'CREATE INDEX' in sql) for sql in batches)
    assert all('ALTER TABLE' not in sql for sql in batches)


def test_migration_repeated_guarded_batches_and_no_permission_grants(monkeypatch):
    connection=Connection();install(monkeypatch,connection)
    # install() patches the Batch2A module; explicitly patch this migration too.
    class Engine:
        def begin(self):return connection
    monkeypatch.setattr(migration,'engine',Engine())
    migration.migrate();first=list(connection.batches)
    migration.migrate();assert connection.batches==first+first
    assert not any('tb_user_menu_permission' in sql for sql,_ in first)
    assert any(params and params.get('code')=='FINANCING_RELEASE' for _,params in first)
