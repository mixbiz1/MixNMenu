"""Real API/ORM audit cycles on isolated SQLite (SQL Server numbering replaced only)."""
import json
from datetime import date, datetime, timezone
from collections import defaultdict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import production modules without opening an ODBC connection. Every request below
# uses its own isolated test session, never the central database.
from unittest.mock import patch
with patch('sqlalchemy.create_engine', return_value=create_engine('sqlite://')):
    import main
import models
from audit_service import AuditEvent, snapshot_json
from database import Base, get_db
from permissions import issue_token


@pytest.fixture
def api(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    @event.listens_for(engine, 'connect')
    def setup(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
        conn.create_function('SYSUTCDATETIME', 0, lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat(' '))
    # Match SQL Server IDENTITY: do not reuse removed row ids during rematerialization.
    for table in Base.metadata.tables.values():
        table.dialect_options['sqlite']['autoincrement'] = True
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        db.add_all([models.Company(comp_code='00001', comp_name='테스트', biz_no='1'),
                    models.Company(comp_code='00002', comp_name='타회사', biz_no='2'),
                    models.User(user_id='tester', user_name='시험', password_hash='unused', is_admin=True),
                    models.User(user_id='reader', user_name='조회', password_hash='unused'),
                    models.Account(account_id=1, account_code='A1', account_name='매입처'),
                    models.Product(product_id=1, product_code='P1', product_name='상품', tax_type='2'),
                    models.Warehouse(warehouse_id=1, warehouse_code='W1', warehouse_name='창고'),
                    models.TaxCode(tax_code='EXEMPT', tax_name='면세', tax_kind='EXEMPT', tax_rate=0, valid_from=date(2000,1,1)),
                    models.MenuMaster(menu_code='PURCHASE_GENERAL', menu_name='매입', menu_group='거래')])
        db.commit()
        db.add_all([models.CompanyAccount(comp_code='00001', account_id=1, purchase_yn=True),
                    models.CompanyWarehouse(comp_code='00001', warehouse_id=1),
                    models.UserCompanyAccess(user_id='reader', comp_code='00001'),
                    models.UserMenuPermission(user_id='reader', menu_code='PURCHASE_GENERAL', can_read=True)])
        db.commit()
    def dependency():
        with factory() as db: yield db
    main.app.dependency_overrides[get_db] = dependency
    monkeypatch.setattr(main, 'SessionLocal', factory)
    counters = defaultdict(int)
    def allocate(db, company, kind, day):
        counters[(company, kind, day)] += 1
        prefix = 'PU' if kind == 'PURCHASE' else 'PI'
        return f'{prefix}-{day:%Y%m%d}-{counters[(company,kind,day)]:04d}'
    monkeypatch.setattr(main, 'allocate_document_no', allocate)
    with TestClient(main.app, raise_server_exceptions=False) as client:
        client.headers['Authorization'] = 'Bearer ' + issue_token('tester')
        yield client, factory
    main.app.dependency_overrides.clear()
    engine.dispose()


URL = '/api/v1/companies/00001/purchases'

def payload(finalize=False, price=1000, **extra):
    return dict(purchase_date='2026-09-30', account_id=1, finalize=finalize,
                items=[dict(line_no=1, product_id=1, warehouse_id=1, box_qty=2,
                            weight='10.25', unit_price=price, bl_no='BL-한글')], **extra)

def events(factory):
    with factory() as db:
        return [{**{c.key: getattr(row,c.key) for c in AuditEvent.__table__.columns},
                 'before': json.loads(row.before_json) if row.before_json else None,
                 'after': json.loads(row.after_json) if row.after_json else None}
                for row in db.scalars(select(AuditEvent).order_by(AuditEvent.audit_event_id))]


def test_full_confirmed_cycle_snapshots_and_links(api):
    client, factory = api
    response = client.post(URL, json=payload(True)); assert response.status_code == 201, response.text
    key = response.json()['purchase_id']
    response = client.put(f'{URL}/{key}', json=payload(True, 2000, audit_reason='최종 원가'))
    assert response.status_code == 200, response.text
    response = client.post(f'{URL}/{key}/cancel', json={'reason':'  오입력 정정  '})
    assert response.status_code == 200, response.text
    rows = events(factory)
    assert [r['action'] for r in rows] == ['CREATE','CONFIRM','UPDATE','CANCEL']
    assert rows[0]['before'] is None
    assert rows[0]['after']['document_status'] == 'DRAFT'
    assert rows[1]['before'] == rows[0]['after']
    assert rows[1]['after']['document_status'] == 'CONFIRMED'
    assert rows[2]['before']['total_amount'] == '10250'
    assert rows[2]['after']['total_amount'] == '20500'
    assert rows[2]['reason'] == '최종 원가'
    assert rows[3]['reason'] == '오입력 정정'
    assert rows[3]['related_entity_id'] == str(key)
    assert rows[3]['after']['items'][0]['lot_id'] is None
    assert rows[3]['after']['items'][0]['lot_code'] is None
    for name in ('inbounds','inbound_items','lots','payables'):
        assert rows[3]['before']['related_transactions'][name]
        assert rows[3]['after']['related_transactions'][name] == []
    for row in rows:
        assert row['comp_code']=='00001' and row['user_id']=='tester'
        assert row['menu_code']=='PURCHASE_GENERAL' and row['created_at']
        assert '/00001/purchases' in row['source']
    assert client.get(f'{URL}/{key}/history').status_code == 200
    assert client.get(f'/api/v1/companies/00002/purchases/{key}/history').json() == []


@pytest.mark.parametrize('finalize', [False, True])
def test_draft_update_and_confirm_paths(api, finalize):
    client, factory = api
    key = client.post(URL, json=payload()).json()['purchase_id']
    response = client.put(f'{URL}/{key}', json=payload(finalize, 1500)); assert response.status_code == 200, response.text
    if not finalize:
        response=client.post(f'{URL}/{key}/confirm'); assert response.status_code==200, response.text
    rows=events(factory)
    assert [r['action'] for r in rows] == ['CREATE','UPDATE','CONFIRM']
    assert rows[1]['after']['document_status']=='DRAFT'
    assert rows[2]['before']==rows[1]['after']
    assert rows[2]['after']['related_transactions']['payables'][0]['original_amount']=='15375'


def test_draft_delete_retains_history_and_confirmed_delete_blocked(api):
    client, factory = api
    key=client.post(URL,json=payload()).json()['purchase_id']
    assert client.delete(f'{URL}/{key}').status_code==200
    rows=events(factory); assert rows[-1]['action']=='DELETE'
    assert rows[-1]['before']['items'] and rows[-1]['after'] is None
    assert len(client.get(f'{URL}/{key}/history').json())==2
    key=client.post(URL,json=payload(True)).json()['purchase_id']
    count=len(events(factory))
    assert client.delete(f'{URL}/{key}').status_code==409
    assert len(events(factory))==count


@pytest.mark.parametrize('reason', [None, '', '   ', 'x'*1001])
def test_cancel_requires_reason_without_changes(api, reason):
    client, factory=api
    key=client.post(URL,json=payload(True)).json()['purchase_id']
    response=client.post(f'{URL}/{key}/cancel',json={} if reason is None else {'reason':reason})
    assert response.status_code==422
    assert len(events(factory))==2
    assert client.get(URL).json()[0]['document_status']=='CONFIRMED'


@pytest.mark.parametrize('operation', ['create','update','confirm','cancel','delete'])
def test_audit_storage_failure_rolls_back_business_and_events(api, monkeypatch, operation):
    client,factory=api
    if operation != 'create':
        key=client.post(URL,json=payload(operation=='cancel')).json()['purchase_id']
    before=client.get(URL).json(); count=len(events(factory))
    @event.listens_for(AuditEvent,'before_insert')
    def fail(*_): raise RuntimeError('simulated audit insert failure')
    try:
        if operation=='create': response=client.post(URL,json=payload(True))
        elif operation=='update': response=client.put(f'{URL}/{key}',json=payload(True,2500))
        elif operation=='confirm': response=client.post(f'{URL}/{key}/confirm')
        elif operation=='cancel': response=client.post(f'{URL}/{key}/cancel',json={'reason':'시험'})
        else: response=client.delete(f'{URL}/{key}')
        assert response.status_code==500
    finally: event.remove(AuditEvent,'before_insert',fail)
    assert client.get(URL).json()==before
    assert len(events(factory))==count
    with factory() as db:
        assert db.query(models.AccountTransaction).count()==(1 if operation=='cancel' else 0)
        assert db.query(models.Lot).count()==(1 if operation=='cancel' else 0)


def test_permissions_validation_period_and_no_failed_audit(api):
    client,factory=api
    client.headers['Authorization']='Bearer '+issue_token('reader')
    assert client.post(URL,json=payload()).status_code==403
    assert client.get('/api/v1/companies/00002/purchases/1/history').status_code==403
    client.headers['Authorization']='Bearer '+issue_token('tester')
    bad=payload(); bad['items'][0]['product_id']=999
    assert client.post(URL,json=bad).status_code==400
    bad=payload(); bad['items'].append(bad['items'][0].copy())
    assert client.post(URL,json=bad).status_code==400
    with factory() as db:
        db.add(models.AccountingPeriod(comp_code='00001',period_year=2026,period_month=9,
                                      period_status='CLOSED',created_by='tester',updated_by='tester')); db.commit()
    assert client.post(URL,json=payload()).status_code==409
    assert events(factory)==[]


def test_snapshot_json_precision_and_null():
    from decimal import Decimal
    assert snapshot_json(None) is None
    assert json.loads(snapshot_json({'중량':Decimal('256.37'),'일자':date(2026,9,30)}))=={'중량':'256.37','일자':'2026-09-30'}


@pytest.mark.parametrize('operation', ['update', 'cancel'])
def test_downstream_fk_blocks_dematerialization_with_no_audit(api, operation):
    client,factory=api
    key=client.post(URL,json=payload(True)).json()['purchase_id']
    with factory() as db:
        lot=db.query(models.Lot).one()
        # A second transaction referencing the original LOT models downstream use.
        inbound=models.Inbound(comp_code='00001',inbound_no='OTHER',inbound_date=date(2026,9,30),
                               warehouse_id=1,transaction_type='IMPORT_INBOUND')
        db.add(inbound);db.flush()
        db.add(models.InboundItem(inbound_id=inbound.inbound_id,line_no=1,product_id=1,
                                 lot_id=lot.lot_id,box_qty=1,weight=1,individual_cost=1000,amount=1000));db.commit()
    response=(client.put(f'{URL}/{key}',json=payload(True,2000)) if operation=='update'
              else client.post(f'{URL}/{key}/cancel',json={'reason':'연결자료 시험'}))
    assert response.status_code==409,response.text
    assert len(events(factory))==2
    assert client.get(URL).json()[0]['total_amount']==10250
    with factory() as db:
        assert db.query(models.InboundItem).count()==2
        assert db.query(models.AccountTransaction).one().original_amount==10250


def test_audit_model_matches_migration_sqlserver_types_and_indexes():
    from sqlalchemy.dialects import mssql
    table=AuditEvent.__table__
    dialect=mssql.dialect()
    assert table.c.before_json.type.compile(dialect=dialect)=='NVARCHAR(max)'
    assert table.c.after_json.type.compile(dialect=dialect)=='NVARCHAR(max)'
    assert table.c.created_at.type.compile(dialect=dialect)=='DATETIME2'
    assert str(table.c.created_at.server_default.arg)=='SYSUTCDATETIME()'
    assert {i.name for i in table.indexes}=={'IX_tb_audit_event_entity','IX_tb_audit_event_created'}
