import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


class _Connection:
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))


class _Engine:
    def __init__(self):
        self.connection = _Connection()

    def begin(self):
        engine = self

        class _Transaction:
            def __enter__(self):
                return engine.connection

            def __exit__(self, exc_type, exc_value, traceback):
                return False

        return _Transaction()


def test_contract_item_migration_uses_separate_sql_server_batches(monkeypatch):
    engine = _Engine()
    monkeypatch.setitem(sys.modules, "database", SimpleNamespace(engine=engine))
    monkeypatch.setitem(sys.modules, "sqlalchemy", SimpleNamespace(text=lambda value: value))
    path = Path(__file__).resolve().parents[1] / "db_financing_contract_migrate.py"
    spec = importlib.util.spec_from_file_location("_financing_migration_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.migrate()
    batches = engine.connection.statements
    add_column = next(i for i, sql in enumerate(batches)
                      if "ALTER TABLE dbo.tb_fin_contract_lot ADD contract_item_id" in sql)
    add_fk_index = next(i for i, sql in enumerate(batches)
                        if "sys.foreign_key_columns" in sql and "sys.indexes" in sql)
    create_missing_items = next(i for i, sql in enumerate(batches)
                                if "INSERT dbo.tb_fin_contract_item" in sql)
    link_legacy_rows = next(i for i, sql in enumerate(batches)
                            if "UPDATE link" in sql and "contract_item_id=item.contract_item_id" in sql)

    assert add_column < add_fk_index < create_missing_items < link_legacy_rows
    assert batches[add_column].count("contract_item_id") == 2
    assert "FOREIGN KEY" not in batches[add_column]
    assert "CREATE INDEX" not in batches[add_column]
    assert "UPDATE" not in batches[add_column]
    assert "COL_LENGTH('dbo.tb_fin_contract_lot','contract_item_id') IS NULL" in batches[add_column]
    assert "NOT EXISTS" in batches[add_fk_index]
    assert "sys.foreign_key_columns" in batches[add_fk_index]
    assert "sys.indexes" in batches[add_fk_index]
    assert "i.contract_id=legacy.contract_id AND i.product_id=legacy.product_id" in batches[create_missing_items]
    assert "WHERE link.contract_item_id IS NULL" in batches[link_legacy_rows]
