"""SQL Server 매출 저장 관련 모델/실제 컬럼 대조. SELECT만 수행한다."""
from sqlalchemy import inspect, text
from database import engine
import models
from audit_service import AuditEvent


def verify():
    failures = []
    with engine.connect() as conn:
        target = conn.execute(text('SELECT @@SERVERNAME AS server_name, DB_NAME() AS database_name')).mappings().one()
        print(f"Target: {target['server_name']} / {target['database_name']}")
        inspector = inspect(conn)
        for model in (models.Sale, models.SaleItem, models.Outbound, models.OutboundItem,
                      models.AccountTransaction, AuditEvent, models.Lot, models.Account, models.DocumentSequence):
            table = model.__table__
            if not inspector.has_table(table.name, schema='dbo'):
                failures.append(f'{table.name}: 테이블 없음'); continue
            actual = {x['name']:x for x in inspector.get_columns(table.name, schema='dbo')}
            issues = []
            for column in table.columns:
                db_column = actual.get(column.name)
                if db_column is None:
                    issues.append(f'{column.name}: 컬럼 없음'); continue
                if column.nullable and not db_column['nullable']:
                    issues.append(f'{column.name}: DB NOT NULL / Model NULL 허용')
                if column.primary_key and column.autoincrement is True and not db_column.get('identity'):
                    issues.append(f'{column.name}: IDENTITY 없음')
                try:
                    if column.type.python_type != db_column['type'].python_type:
                        issues.append(f'{column.name}: 타입 Model={column.type}, DB={db_column["type"]}')
                except (NotImplementedError, AttributeError):
                    pass
                for prop in ('length', 'precision', 'scale'):
                    expected = getattr(column.type, prop, None); found = getattr(db_column['type'], prop, None)
                    if expected is not None and found is not None and found < expected:
                        issues.append(f'{column.name}: {prop} Model={expected}, DB={found}')
            for name, column in actual.items():
                if name not in table.columns and not column['nullable'] and column.get('default') is None and not column.get('identity') and not column.get('computed'):
                    issues.append(f'{name}: Model에 없는 DB 필수 컬럼')
            print(f"{table.name}: {'; '.join(issues) if issues else '컬럼 대조 OK'}")
            failures.extend(f'{table.name}: {x}' for x in issues)
        rows = conn.execute(text("""
            SELECT OBJECT_NAME(parent_object_id) AS table_name, name, definition
            FROM sys.check_constraints
            WHERE parent_object_id IN (OBJECT_ID('dbo.tb_sale'), OBJECT_ID('dbo.tb_sale_item'),
                OBJECT_ID('dbo.tb_outbound'), OBJECT_ID('dbo.tb_outbound_item'),
                OBJECT_ID('dbo.tb_account_transaction'), OBJECT_ID('dbo.tb_document_sequence'))
        """)).mappings().all()
        for row in rows: print(f"CHECK {row['table_name']}.{row['name']}: {row['definition']}")
        print(f"컬럼 대조 결과: {len(failures)}건 불일치. DB 변경 없음.")
    return not failures


if __name__ == '__main__':
    raise SystemExit(0 if verify() else 1)
