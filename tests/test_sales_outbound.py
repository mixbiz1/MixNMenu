from datetime import date, datetime, timezone
from decimal import Decimal
from collections import defaultdict
from unittest.mock import patch
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
with patch('sqlalchemy.create_engine', return_value=create_engine('sqlite://')): import main
import models
from audit_service import AuditEvent
from database import Base, get_db
from permissions import issue_token

URL='/api/v1/companies/00001/sales'
@pytest.fixture
def api(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def setup(conn,_): conn.execute('PRAGMA foreign_keys=ON'); conn.create_function('SYSUTCDATETIME',0,lambda:datetime.now(timezone.utc).replace(tzinfo=None).isoformat(' '))
    for table in Base.metadata.tables.values(): table.dialect_options['sqlite']['autoincrement']=True
    Base.metadata.create_all(engine); factory=sessionmaker(bind=engine,autoflush=False)
    with factory() as db:
        db.add_all([models.Company(comp_code='00001',comp_name='T',biz_no='1'),models.User(user_id='tester',user_name='T',password_hash='x',is_admin=True),models.Account(account_id=1,account_code='A1',account_name='거래처'),models.Product(product_id=1,product_code='P1',product_name='상품',tax_type='2'),models.Warehouse(warehouse_id=1,warehouse_code='W1',warehouse_name='창고'),models.TaxCode(tax_code='EXEMPT',tax_name='면세',tax_kind='EXEMPT',tax_rate=0,valid_from=date(2000,1,1)),models.MenuMaster(menu_code='SALES_GENERAL',menu_name='매출',menu_group='거래'),models.MenuMaster(menu_code='PURCHASE_GENERAL',menu_name='매입',menu_group='거래')]); db.commit()
        db.add_all([models.CompanyAccount(comp_code='00001',account_id=1,sales_yn=True,purchase_yn=True),models.CompanyWarehouse(comp_code='00001',warehouse_id=1)]); lot=models.Lot(comp_code='00001',lot_code='L1',source_type='DOMESTIC',product_id=1,warehouse_id=1,individual_cost=1000,status='OPEN',use_yn=True); db.add(lot); db.flush(); inbound=models.Inbound(comp_code='00001',inbound_no='I1',inbound_date=date(2026,10,2),warehouse_id=1,transaction_type='PURCHASE_INBOUND'); db.add(inbound); db.flush(); db.add(models.InboundItem(inbound_id=inbound.inbound_id,line_no=1,product_id=1,lot_id=lot.lot_id,box_qty=10,weight=Decimal('100.00'),individual_cost=1000,amount=100000)); db.commit()
    def dependency():
        with factory() as db: yield db
    main.app.dependency_overrides[get_db]=dependency; monkeypatch.setattr(main,'SessionLocal',factory); counters=defaultdict(int)
    def allocate(db,co,kind,day): counters[kind]+=1; return f'{kind[:2]}-{counters[kind]:03d}'
    monkeypatch.setattr(main,'allocate_document_no',allocate)
    with TestClient(main.app,raise_server_exceptions=False) as client: client.headers['Authorization']='Bearer '+issue_token('tester'); yield client,factory
    main.app.dependency_overrides.clear(); engine.dispose()

def payload(box=2,weight='20.00',lot=1): return {'sale_date':'2026-10-02','account_id':1,'items':[{'line_no':1,'product_id':1,'lot_id':lot,'box_qty':box,'weight':weight,'unit_price':2000}]}
def test_sale_saves_confirmed_outbound_receivable_and_audit(api):
    client,factory=api; r=client.post(URL,json=payload()); assert r.status_code==201,r.text; assert r.json()['document_status']=='CONFIRMED'
    with factory() as db:
        assert db.query(models.Outbound).count()==1 and db.query(models.OutboundItem).count()==1
        assert db.query(models.AccountTransaction).one().transaction_type=='SALES_RECEIVABLE'
        assert main._lot_available(db,'00001',1)==(8,Decimal('80.00'))
        assert [x.action for x in db.scalars(select(AuditEvent).order_by(AuditEvent.audit_event_id))]==['CREATE','CONFIRM']


def test_sale_api_accepts_weight_only_line_in_multi_lot_sale(api):
    client,factory=api
    with factory() as db:
        lot=models.Lot(comp_code='00001',lot_code='L2',source_type='DOMESTIC',product_id=1,
                       warehouse_id=1,individual_cost=1200,status='OPEN',use_yn=True)
        db.add(lot); db.flush()
        inbound=models.Inbound(comp_code='00001',inbound_no='I2',inbound_date=date(2026,10,2),
                               warehouse_id=1,transaction_type='PURCHASE_INBOUND')
        db.add(inbound); db.flush()
        db.add(models.InboundItem(inbound_id=inbound.inbound_id,line_no=1,product_id=1,
                                  lot_id=lot.lot_id,box_qty=5,weight=Decimal('30.00'),
                                  individual_cost=1200,amount=36000))
        db.commit(); lot_id=lot.lot_id
    data=payload(0,'21.00')
    data['items'].append({'line_no':2,'product_id':1,'lot_id':lot_id,
                          'box_qty':1,'weight':'22.00','unit_price':2000})
    response=client.post(URL,json=data)
    assert response.status_code==201,response.text
    assert [item['box_qty'] for item in response.json()['items']]==[0,1]
    with factory() as db:
        assert main._lot_available(db,'00001',1)==(10,Decimal('79.00'))
        assert main._lot_available(db,'00001',lot_id)==(4,Decimal('8.00'))
        assert [item.box_qty for item in db.query(models.OutboundItem).order_by(models.OutboundItem.line_no)]==[0,1]


@pytest.mark.parametrize(('box_qty','weight','expected_box','expected_weight'),[
    (1,'20.00',99,Decimal('2044.00')),
    (0,'15.00',100,Decimal('2049.00')),
])
def test_box_and_weight_stock_are_independent_and_cancel_restores(api,box_qty,weight,expected_box,expected_weight):
    client,factory=api
    with factory() as db:
        inbound=db.query(models.InboundItem).one()
        inbound.box_qty=100; inbound.weight=Decimal('2064.00'); db.commit()
    endpoint=URL+'/lot-availability'
    before=client.get(endpoint).json()[0]
    assert (before['available_box_qty'],Decimal(str(before['available_weight'])))==(100,Decimal('2064.00'))
    response=client.post(URL,json=payload(box_qty,weight))
    assert response.status_code==201,response.text
    sale_id=response.json()['sale_id']
    availability=client.get(endpoint).json()[0]
    assert (availability['available_box_qty'],Decimal(str(availability['available_weight'])))==(expected_box,expected_weight)
    with factory() as db:
        item=db.query(models.OutboundItem).one()
        assert (item.box_qty,item.weight)==(box_qty,Decimal(weight))
        assert main._lot_available(db,'00001',1)==(expected_box,expected_weight)
    canceled=client.post(f'{URL}/{sale_id}/cancel',json={'reason':'재고복원 회귀검증'})
    assert canceled.status_code==200,canceled.text
    restored=client.get(endpoint).json()[0]
    assert (restored['available_box_qty'],Decimal(str(restored['available_weight'])))==(100,Decimal('2064.00'))
    with factory() as db:
        assert db.query(models.OutboundItem).count()==0
        assert db.get(models.Sale,sale_id).document_status=='CANCELLED'
        assert main._lot_available(db,'00001',1)==(100,Decimal('2064.00'))
        assert db.query(models.AccountTransaction).filter(
            models.AccountTransaction.transaction_type=='SALES_RECEIVABLE').count()==0
        actions=[x.action for x in db.query(AuditEvent).filter(
            AuditEvent.entity_type=='SALE',AuditEvent.entity_id==str(sale_id)
        ).order_by(AuditEvent.audit_event_id)]
        assert actions[-1]=='CANCEL'


def test_projection_math_keeps_box_and_kg_independent():
    from sales_inventory import project_lot_stock
    assert project_lot_stock(100,Decimal('2064.00'),1,Decimal('20.00'))==(99,Decimal('2044.00'))
    assert (Decimal('2044.00')/Decimal(99)).quantize(Decimal('0.01'))==Decimal('20.65')
    assert project_lot_stock(100,Decimal('2064.00'),0,Decimal('15.00'))==(100,Decimal('2049.00'))
    assert (Decimal('2049.00')/Decimal(100)).quantize(Decimal('0.01'))==Decimal('20.49')


def test_box_only_outbound_is_valid_but_zero_movement_is_rejected(api):
    client,factory=api
    assert client.post(URL,json=payload(0,'0.00')).status_code==400
    response=client.post(URL,json=payload(1,'0.00'))
    assert response.status_code==201,response.text
    with factory() as db:
        assert main._lot_available(db,'00001',1)==(9,Decimal('100.00'))
        item=db.query(models.OutboundItem).one()
        assert (item.box_qty,item.weight)==(1,Decimal('0.00'))
def test_sale_blocks_box_and_weight_overissue(api):
    client,_=api; assert client.post(URL,json=payload(11,'20.00')).status_code==409; assert client.post(URL,json=payload(2,'100.01')).status_code==409
def test_negative_inventory_exception_reason_allows_box_kg_and_audit(api):
    client,factory=api; data=payload(11,'110.00'); data['inventory_exception_reason']='계근차이 선출고'; r=client.post(URL,json=data); assert r.status_code==201,r.text; assert r.json()['inventory_exception_yn'] and r.json()['inventory_exception_reason']=='계근차이 선출고'
    with factory() as db: assert main._lot_available(db,'00001',1)==(-1,Decimal('-10.00')) and '계근차이 선출고' in db.scalars(select(AuditEvent).order_by(AuditEvent.audit_event_id)).all()[-1].after_json
def test_same_lot_multiple_lines_uses_total_and_receivable_summary(api):
    client,_=api; data=payload(6,'60.00'); data['items'].append({'line_no':2,'product_id':1,'lot_id':1,'box_qty':5,'weight':'40.00','unit_price':2000}); assert client.post(URL,json=data).status_code==409
    data['inventory_exception_reason']='동일 LOT 합산 선출고'; assert client.post(URL,json=data).status_code==201
    value=client.get('/api/v1/companies/00001/sales-receivable-summary',params={'account_id':1,'transaction_date':'2026-10-02'}).json(); assert value['today_sales']==200000 and value['today_receipt']==0 and value['current_receivable']==200000
def test_partial_multiple_lot_outbound_and_cancel_recovery(api):
    client,factory=api; key=client.post(URL,json=payload()).json()['sale_id']; assert client.post(URL,json=payload(3,'30.00')).status_code==201
    assert client.post(f'{URL}/{key}/cancel',json={'reason':'정정'}).status_code==200
    with factory() as db: assert db.query(models.Outbound).count()==1 and db.query(models.AccountTransaction).count()==1 and main._lot_available(db,'00001',1)==(7,Decimal('70.00'))


def test_cancel_sale_restores_all_derived_data_and_hides_daily_list_but_keeps_audit(api):
    client,factory=api
    created=client.post(URL,json=payload(2,'20.00'))
    assert created.status_code==201,created.text
    sale_id=created.json()['sale_id']
    assert len(client.get(URL).json())==1
    canceled=client.post(f'{URL}/{sale_id}/cancel',json={'reason':'거래처 요청 취소'})
    assert canceled.status_code==200,canceled.text
    assert canceled.json()['document_status']=='CANCELLED'
    with factory() as db:
        sale=db.get(models.Sale,sale_id)
        assert sale.document_status=='CANCELLED'
        assert db.query(models.Outbound).count()==0
        assert db.query(models.OutboundItem).count()==0
        assert db.query(models.AccountTransaction).filter(
            models.AccountTransaction.transaction_type=='SALES_RECEIVABLE').count()==0
        assert main._lot_available(db,'00001',1)==(10,Decimal('100.00'))
        cancel_event=db.query(AuditEvent).filter(
            AuditEvent.entity_type=='SALE',AuditEvent.entity_id==str(sale_id),
            AuditEvent.action=='CANCEL').one()
        before=json.loads(cancel_event.before_json)
        after=json.loads(cancel_event.after_json)
        assert len(before['related_transactions']['outbounds'])==1
        assert len(before['related_transactions']['outbound_items'])==1
        assert len(before['related_transactions']['receivables'])==1
        assert after['document_status']=='CANCELLED'
        assert after['related_transactions']=={'outbounds':[],'outbound_items':[],'receivables':[]}
        assert cancel_event.reason=='거래처 요청 취소'
    summary=client.get('/api/v1/companies/00001/sales-receivable-summary',
                       params={'account_id':1,'transaction_date':'2026-10-02'}).json()
    assert summary['today_sales']==0 and summary['current_receivable']==0
    assert client.get(URL).json()==[]
    history=client.get(f'{URL}/{sale_id}/history')
    assert history.status_code==200
    assert [event['action'] for event in history.json()]==['CREATE','CONFIRM','CANCEL']
def test_sale_outbound_blocks_purchase_rematerialization(api):
    client,factory=api; client.post(URL,json=payload())
    with factory() as db:
        lot=db.get(models.Lot,1); purchase=models.Purchase(comp_code='00001',purchase_no='P1',purchase_date=date(2026,10,2),account_id=1,document_status='CONFIRMED',created_by='tester',updated_by='tester'); item=models.PurchaseItem(line_no=1,product_id=1,warehouse_id=1,lot_id=lot.lot_id,box_qty=1,weight=1,unit_price=1,supply_amount=1,tax_code_snapshot='EXEMPT',tax_name_snapshot='면세',tax_rate_snapshot=0,tax_amount=0,discount_amount=0,total_amount=1); purchase.items=[item]; db.add(purchase); db.commit()
        with pytest.raises(Exception) as exc: main._guard_purchase_dematerialization(db,purchase)
        assert getattr(exc.value,'status_code',None)==409


def test_reported_sale_post_with_real_document_type_validation(api,monkeypatch):
    """실제 발번 함수의 prefix 검사를 유지하고 SQL Server sequence SQL만 대체한다."""
    from types import SimpleNamespace
    from trade_common import allocate_document_no as real_allocate
    client,factory=api
    with factory() as db:
        db.get(models.Account,1).account_code='00002'
        db.get(models.Lot,1).lot_code='L20260917-001-01'
        detail=db.query(models.InboundItem).one(); detail.box_qty=100; detail.weight=Decimal('21.55'); db.commit()
    counters=defaultdict(int); kinds=[]
    class SequenceOnlyDb:
        def execute(self,statement,params):
            assert 'UPDLOCK, HOLDLOCK' in str(statement)
            kinds.append(params['document_type']); counters[params['document_type']]+=1
            return SimpleNamespace(scalar_one=lambda:counters[params['document_type']])
    monkeypatch.setattr(main,'allocate_document_no',lambda db,co,kind,day:real_allocate(SequenceOnlyDb(),co,kind,day))
    data=payload(1,'10.00'); data['items'][0]['unit_price']=6000
    response=client.post(URL,json=data)
    assert response.status_code==201,response.text
    assert response.json()['document_status']=='CONFIRMED' and response.json()['total_amount']==60000
    assert kinds==['SALE','OUTBOUND']
    with factory() as db:
        assert main._lot_available(db,'00001',1)==(99,Decimal('11.55'))
        assert db.query(models.Sale).count()==1 and db.query(models.SaleItem).count()==1
        assert db.query(models.Outbound).one().outbound_no=='OU-20261002-0001'
        assert db.query(models.OutboundItem).one().weight==Decimal('10.00')
        assert db.query(models.AccountTransaction).one().original_amount==60000
        assert [x.action for x in db.query(AuditEvent).order_by(AuditEvent.audit_event_id)]==['CREATE','CONFIRM']
    sale_id=response.json()['sale_id']
    assert client.put(f'{URL}/{sale_id}',json=data).status_code==200
    assert client.post(f'{URL}/{sale_id}/cancel',json={'reason':'회귀검증'}).status_code==200


def test_actual_account_master_contact_and_lot_cost_api(api):
    client,factory=api
    with factory() as db:
        account=db.get(models.Account,1); account.phone='02-1234'; account.fax='02-5678'; account.tax_email='sales@example.com'
        db.get(models.Lot,1).individual_cost=Decimal('1200.01'); db.commit()
    contact=client.get('/api/v1/accounts/1').json()
    assert (contact['phone'],contact['fax'],contact['tax_email'])==('02-1234','02-5678','sales@example.com')
    assert client.get(URL+'/lot-availability').json()[0]['individual_cost']==1201


def test_original_unsupported_outbound_kind_reproduces_500_atomically(api,monkeypatch):
    """수정 전 실제 발번 경로의 500과 전체 transaction 회수를 재현한다."""
    from trade_common import allocate_document_no as real_allocate
    client,factory=api
    old_allocator=main.allocate_document_no
    def emulate_original(db,co,kind,day):
        if kind=='OUTBOUND': return real_allocate(db,co,'SALES_OUTBOUND',day)
        return old_allocator(db,co,kind,day)
    monkeypatch.setattr(main,'allocate_document_no',emulate_original)
    assert client.post(URL,json=payload(1,'10.00')).status_code==500
    with factory() as db:
        for model in (models.Sale,models.SaleItem,models.Outbound,models.OutboundItem,models.AccountTransaction,AuditEvent):
            assert db.query(model).count()==0


def test_sales_migration_contains_every_insert_model_column():
    import re
    from pathlib import Path
    ddl=(Path(__file__).resolve().parents[1]/'db_sales_migrate.py').read_text(encoding="utf-8")
    for model in (models.Sale,models.SaleItem,models.Outbound,models.OutboundItem):
        body=ddl.split(f'CREATE TABLE dbo.{model.__tablename__} (',1)[1].split(';',1)[0]
        for column in model.__table__.columns:
            assert re.search(r'\b'+re.escape(column.name)+r'\s+(?:INT|VARCHAR|NVARCHAR|DATE|DATETIMEOFFSET|NUMERIC|BIT)\b',body),f'{model.__tablename__}.{column.name}'
