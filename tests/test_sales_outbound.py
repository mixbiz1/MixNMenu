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
def test_sale_outbound_blocks_purchase_rematerialization(api):
    client,factory=api; client.post(URL,json=payload())
    with factory() as db:
        lot=db.get(models.Lot,1); purchase=models.Purchase(comp_code='00001',purchase_no='P1',purchase_date=date(2026,10,2),account_id=1,document_status='CONFIRMED',created_by='tester',updated_by='tester'); item=models.PurchaseItem(line_no=1,product_id=1,warehouse_id=1,lot_id=lot.lot_id,box_qty=1,weight=1,unit_price=1,supply_amount=1,tax_code_snapshot='EXEMPT',tax_name_snapshot='면세',tax_rate_snapshot=0,tax_amount=0,discount_amount=0,total_amount=1); purchase.items=[item]; db.add(purchase); db.commit()
        with pytest.raises(Exception) as exc: main._guard_purchase_dematerialization(db,purchase)
        assert getattr(exc.value,'status_code',None)==409
