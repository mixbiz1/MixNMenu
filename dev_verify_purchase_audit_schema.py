"""Read-only model/schema check. Never creates tables or runs migration."""
from sqlalchemy import inspect, text
from database import engine
from audit_service import AuditEvent


def check_schema(connection):
    inspector = inspect(connection)
    problems = []
    if not inspector.has_table('tb_audit_event', schema='dbo'):
        return ['dbo.tb_audit_event is missing']
    actual = {column['name']: column for column in inspector.get_columns('tb_audit_event', schema='dbo')}
    for column in AuditEvent.__table__.columns:
        found = actual.get(column.name)
        if found is None:
            problems.append(f'{column.name}: missing'); continue
        expected_type = column.type.compile(dialect=connection.dialect).upper()
        actual_type = found['type'].compile(dialect=connection.dialect).upper()
        if expected_type != actual_type:
            problems.append(f'{column.name}: model={expected_type}, DB={actual_type}')
        if column.nullable != found['nullable']:
            problems.append(f'{column.name}: nullable differs')
    if inspector.get_pk_constraint('tb_audit_event', schema='dbo')['constrained_columns'] != ['audit_event_id']:
        problems.append('audit_event_id primary key differs')
    if not actual.get('audit_event_id', {}).get('identity'):
        problems.append('audit_event_id IDENTITY is missing')
    default = str(actual.get('created_at', {}).get('default') or '').upper()
    if 'SYSUTCDATETIME' not in default:
        problems.append('created_at UTC default differs')
    indexes = {value['name']: value['column_names'] for value in inspector.get_indexes('tb_audit_event', schema='dbo')}
    for index in AuditEvent.__table__.indexes:
        if indexes.get(index.name) != [column.name for column in index.columns]:
            problems.append(f'{index.name}: index differs')
    return problems


if __name__ == '__main__':
    with engine.connect() as connection:
        name = connection.execute(text('SELECT DB_NAME()')).scalar_one()
        print(f'Database: {name}')
        if name != 'mxmn_dev':
            raise SystemExit('Expected mxmn_dev; no schema check performed.')
        problems = check_schema(connection)
    for problem in problems:
        print(f'[DIFF] {problem}')
    if problems:
        raise SystemExit(1)
    print('Audit schema matches model. Read-only check; no migration executed.')
