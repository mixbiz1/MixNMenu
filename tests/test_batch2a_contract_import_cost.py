"""Batch 2A HTTP E2E over the existing ERP fixture, FK enabled."""
import json
from decimal import Decimal
from unittest.mock import Mock

import pytest
from test_batch1b_distribution_e2e import flow, call, purchase_data, sale_data, state, BASE
from test_trade_flow_integrity import db_factory
import models
from audit_service import AuditEvent
from permissions import issue_token


def contract_data(kind='IMPORT_AGENCY'):
    return {'contract_type':kind,'contract_date':'2026-10-01','contractor_account_id':1,
        'deposit_required':True,'deposit_amount':'30000',
        'items':[{'product_id':1,'contract_box_qty':14,'contract_weight':'140','contract_unit_price':'1000'},
                 {'product_id':2,'contract_box_qty':5,'contract_weight':'50','contract_unit_price':'2000'}],
        'terms':[{'effective_from':'2026-10-01','recovery_template':'ALL_IN','interest_rate_1':'7.5',
            'interest_period_days_1':90,'storage_rate_per_kg_day':'0.9','brokerage_rate_1':'1.5'}]}


def confirmed_contract(client, kind='IMPORT_AGENCY'):
    row = call(client,'POST','/financing-contracts',201,json=contract_data(kind))
    return call(client,'POST',f"/financing-contracts/{row['contract_id']}/confirm")


def make_case(client, contract, linked=True):
    case = call(client,'POST','/import-cases',201,json={'contract_id':contract['contract_id']})
    assert len(case['items']) == 2
    if linked:
        purchase = call(client,'POST','/purchases',201,json=purchase_data())
        mapping = {x['product_id']:x['contract_item_id'] for x in contract['items']}
        entries = [{'contract_item_id':mapping[x['product_id']],'product_id':x['product_id'],
            'lot_id':x['lot_id'],'box_qty':x['box_qty'],'weight':x['weight']} for x in purchase['items']]
        # The ERP fixture uses one BL per purchase row; align them explicitly for
        # this single import case before connecting existing LOTs.
        return case, purchase, entries
    return case, None, None


def ready_case(flow, kind='IMPORT_AGENCY'):
    client, factory = flow
    contract = confirmed_contract(client,kind)
    case, purchase, entries = make_case(client,contract)
    with factory() as db:
        for x in entries: db.get(models.Lot,x['lot_id']).bl_no='BL-COST-1'
        db.commit()
    case = call(client,'PUT',f"/import-cases/{case['import_case_id']}",json={
        'contract_id':contract['contract_id'],'bl_no':'BL-COST-1','currency':'USD',
        'supplier_account_id':2,'customs_date':'2026-10-02','warehouse_receipt_date':'2026-10-03',
        'items':entries,'reason':'실제 BL 및 ERP LOT 연결'})
    call(client,'POST',f"/import-cases/{case['import_case_id']}/start")
    return contract, case, purchase


def basic_cost(client, case):
    return call(client,'POST','/import-costs',201,json={'import_case_id':case['import_case_id']})


def fill_basic(client, settlement):
    amounts = [100,10000,10003,5000,2000]
    result = settlement
    for index, row in enumerate(settlement['rows']):
        result = call(client,'PUT',f"/import-costs/{settlement['settlement_id']}/rows/{row['cost_row_id']}",json={
            'cost_name':row['cost_name'],'occurred_on':f'2026-10-0{index+1}',
            'amount':amounts[index],'currency':'USD' if index==0 else 'KRW',
            'exchange_rate':'1300.50' if index==0 else None,'reason':'실제 비용 입력'})
    return result


@pytest.mark.parametrize('kind',['IMPORT_AGENCY','BL_TRANSFER','DOMESTIC_PURCHASE'])
def test_contract_document_template_edit_confirm_snapshot_version_and_master_change(flow,kind):
    client,factory=flow; contract=confirmed_contract(client,kind)
    document=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':kind})
    assert contract['contract_no'] in document['body'] and '140.00' in document['body']
    assert '{{' not in document['body'] and '물품구매-판매계약서' in document['body']
    assert document['snapshot']['body_format']=='HTML' and document['snapshot']['template_revision']=='20261008.v1.seller-account'
    document=call(client,'PUT',f"/contract-documents/{document['document_id']}",json={'body':document['body']+'\n사용자 특별조건','reason':'문구 검토'})
    document=call(client,'POST',f"/contract-documents/{document['document_id']}/confirm")
    assert document['snapshot']['body']==document['body']
    frozen=document['snapshot']
    with factory() as db:
        db.get(models.Product,1).product_name='Master 변경'
        db.get(models.Account,1).account_name='상호 변경'; db.commit()
    assert call(client,'GET',f"/contract-documents/{document['document_id']}")['snapshot']==frozen
    call(client,'PUT',f"/contract-documents/{document['document_id']}",409,json={'body':'덮어쓰기'})
    assert call(client,'POST',f"/contract-documents/{document['document_id']}/confirm")['version']==1
    second=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':kind})
    call(client,'POST',f"/contract-documents/{second['document_id']}/confirm")
    old=call(client,'GET',f"/contract-documents/{document['document_id']}")
    assert old['status']=='SUPERSEDED' and old['snapshot']==frozen and second['version']==2
    call(client,'POST',f"/financing-contracts/{contract['contract_id']}/cancel",409,json={'reason':'후속 계약서 취소 시도'})


def test_contract_document_to_case_carries_confirmed_snapshot_without_assuming_supplier(flow):
    client,factory=flow; contract=confirmed_contract(client)
    doc=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    doc=call(client,'POST',f"/contract-documents/{doc['document_id']}/confirm")
    with factory() as db:
        db.get(models.Account,1).account_name='변경 상호'; db.commit()
    case=call(client,'POST','/import-cases',201,json={'contract_id':contract['contract_id']})
    assert case['source_snapshot']==doc['snapshot']
    assert case['supplier_account_id'] is None
    assert [Decimal(str(x['weight'])) for x in case['items']]==[Decimal('140'),Decimal('50')]
    case=call(client,'PUT',f"/import-cases/{case['import_case_id']}",json={
        'contract_id':contract['contract_id'],'bl_no':'BL-1','reference':'CONT-1','supplier_account_id':2,
        'customs_date':'2026-10-03','warehouse_receipt_date':'2026-10-04'})
    assert case['source_snapshot']==doc['snapshot'] and case['bl_no']=='BL-1'
    call(client,'POST',f"/import-cases/{case['import_case_id']}/start")
    call(client,'POST',f"/import-cases/{case['import_case_id']}/close",409,json={'reason':'조기 마감'})


def test_actual_cost_free_adjustments_period_fx_tax_scope_allocation_snapshot_and_audit(flow):
    client,factory=flow; contract,case,purchase=ready_case(flow)
    cost=basic_cost(client,case)
    assert len(cost['rows'])==5 and all(x['origin']=='AUTO' and x['amount'] is None for x in cost['rows'])
    call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",409,json={})
    cost=fill_basic(client,cost)
    for data in [
        {'cost_name':'검사비','amount':1000,'occurred_on':'2026-10-05','product_id':2},
        {'cost_name':'Claim 할인','amount':-250,'occurred_on':'2026-10-06'},
        {'cost_name':'실제 보관료','cost_kind':'PERIOD','amount':500,'period_start':'2026-10-01',
         'period_end':'2026-10-05','rate':'0.9','basis':'KG_DAY','basis_quantity':'190','memo':'실제 청구액 입력'},
    ]: cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/rows",201,json=data)
    assert Decimal(str(cost['total_cost']))==158303
    before_quantity=[]
    with factory() as db:
        before_quantity=[(x.lot_id,x.box_qty,x.weight) for x in db.query(models.InboundItem).all()]
    cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",json={'reason':'실제 원가 확인'})
    assert cost['status']=='CONFIRMED'
    assert sum(Decimal(str(x['allocated_cost'])) for x in cost['allocations'])==158303
    assert cost['snapshot']['case']['status']=='COST_CONFIRMED'
    assert len(cost['allocations'])==3 and all(x['allocation_id'] for x in cost['allocations'])
    frozen=cost['snapshot']
    with factory() as db:
        assert [(x.lot_id,x.box_qty,x.weight) for x in db.query(models.InboundItem).all()]==before_quantity
        assert db.query(models.FinancingContractLot).filter_by(contract_id=contract['contract_id']).count()==3
        for allocation in cost['allocations']:
            lot=db.get(models.Lot,allocation['lot_id'])
            assert lot.individual_cost==Decimal(str(allocation['unit_cost']))
        assert db.query(AuditEvent).filter_by(action='ALLOCATE_COST').count()==3
        assert db.query(models.AccountTransaction).filter(models.AccountTransaction.transaction_type.in_(['SALE','RECEIPT','PAYMENT'])).count()==0
        db.get(models.Product,1).product_name='변경 상품'; db.commit()
    assert call(client,'GET',f"/import-costs/{cost['settlement_id']}")['snapshot']==frozen
    call(client,'POST',f"/import-costs/{cost['settlement_id']}/rows",409,json={'cost_name':'후속 수정','amount':1})
    call(client,'PUT',f"/import-cases/{case['import_case_id']}",409,json={'contract_id':contract['contract_id']})
    assert call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",json={})['settlement_id']==cost['settlement_id']
    assert call(client,'POST',f"/import-cases/{case['import_case_id']}/close",json={'reason':'수입건 마감'})['status']=='CLOSED'
    call(client,'POST',f"/import-costs/{cost['settlement_id']}/cancel",409,json={'reason':'마감 후 취소'})


def test_direct_allocation_exact_total_cancel_restores_cost_and_keeps_snapshot(flow):
    client,factory=flow; contract,case,_=ready_case(flow)
    cost=call(client,'POST','/import-costs',201,json={'import_case_id':case['import_case_id'],'basic_rows':False})
    cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/rows",201,json={'cost_name':'전체원가','occurred_on':'2026-10-05','amount':300003})
    entries=[{'case_item_id':x['case_item_id'],'amount':value} for x,value in zip(case['items'],[100001,100001,100001])]
    wrong=[{**x,'amount':0} for x in entries]
    call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",409,json={'allocation_method':'DIRECT','allocations':wrong})
    cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",json={'allocation_method':'DIRECT','allocations':entries})
    snapshot=cost['snapshot']
    canceled=call(client,'POST',f"/import-costs/{cost['settlement_id']}/cancel",json={'reason':'실제 환율 정정'})
    assert canceled['snapshot']==snapshot and canceled['status']=='CANCELLED'
    with factory() as db:
        for x in canceled['allocations']: assert db.get(models.Lot,x['lot_id']).individual_cost==Decimal(str(x['previous_unit_cost']))
        assert db.query(AuditEvent).filter_by(action='RESTORE_COST').count()==3
    next_cost=basic_cost(client,case)
    assert next_cost['version']==2


@pytest.mark.parametrize('bad',[
    {'cost_kind':'UNKNOWN'}, {'currency':'USD','exchange_rate':None},
    {'period_start':'2026-10-10','period_end':'2026-10-01'}, {'lot_id':999},
    {'product_id':999}, {'tax_kind':'WRONG'}, {'payer':'WRONG'}, {'currency':'KRW','exchange_rate':'2'},
])
def test_invalid_cost_data_is_rejected_without_partial_rows(flow,bad):
    client,factory=flow; _,case,_=ready_case(flow); cost=basic_cost(client,case)
    before=call(client,'GET',f"/import-costs/{cost['settlement_id']}")
    call(client,'POST',f"/import-costs/{cost['settlement_id']}/rows",400,json={'cost_name':'오류 원가','amount':1,**bad})
    assert call(client,'GET',f"/import-costs/{cost['settlement_id']}")==before


def test_sold_lot_cost_confirmation_is_blocked_atomically(flow):
    client,factory=flow; _,case,purchase=ready_case(flow)
    cost=fill_basic(client,basic_cost(client,case))
    sale=call(client,'POST','/sales',201,json=sale_data(purchase))
    with factory() as db: original=[x.individual_cost for x in db.query(models.Lot).order_by(models.Lot.lot_id)]
    call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",409,json={})
    assert call(client,'GET',f"/import-costs/{cost['settlement_id']}")['status']=='DRAFT'
    with factory() as db:
        assert [x.individual_cost for x in db.query(models.Lot).order_by(models.Lot.lot_id)]==original
        assert db.query(models.ImportCostAllocation).count()==0
    call(client,'POST',f"/sales/{sale['sale_id']}/cancel",json={'reason':'출고 취소'})
    call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",409,json={})


def test_cost_audit_failure_rolls_back_allocations_lot_cost_contract_links_and_case(flow,monkeypatch):
    client,factory=flow; _,case,_=ready_case(flow); cost=fill_basic(client,basic_cost(client,case))
    import financing_intake_routes as routes
    original=routes.record_audit_event
    def fail(*args,**kwargs):
        original(*args,**kwargs)
        if kwargs['action']=='CONFIRM': raise RuntimeError('post-write audit failure')
    monkeypatch.setattr(routes,'record_audit_event',fail)
    with factory() as db:
        original_costs=[x.individual_cost for x in db.query(models.Lot).order_by(models.Lot.lot_id)]
        events=db.query(AuditEvent).count()
    call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",500,json={})
    with factory() as db:
        assert [x.individual_cost for x in db.query(models.Lot).order_by(models.Lot.lot_id)]==original_costs
        assert db.query(models.ImportCostAllocation).count()==0
        assert db.query(models.FinancingContractLot).count()==0
        assert db.query(AuditEvent).count()==events
        assert db.get(models.ImportCase,case['import_case_id']).status=='COSTING'


@pytest.mark.parametrize('resource',['contract-documents','import-cases','import-costs'])
def test_company_isolation_on_lists_and_creation(flow,resource):
    client,_=flow; contract,case,_=ready_case(flow)
    if resource=='contract-documents': payload={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'}
    elif resource=='import-cases': payload={'contract_id':contract['contract_id']}
    else: payload={'import_case_id':case['import_case_id']}
    response=client.post(BASE.replace('00001','00002')+'/'+resource,json=payload)
    assert response.status_code==404
    assert client.get(BASE.replace('00001','00002')+'/'+resource).json()==[]


def test_general_import_case_without_contract_and_cost_row_deletion_audit(flow):
    client,factory=flow
    case=call(client,'POST','/import-cases',201,json={'bl_no':'GENERAL-BL','supplier_account_id':2,
        'items':[{'product_id':1,'box_qty':1,'weight':10}]})
    assert case['contract_id'] is None and case['source_snapshot']=={}
    call(client,'POST',f"/import-cases/{case['import_case_id']}/start")
    cost=basic_cost(client,case); key=cost['rows'][0]['cost_row_id']
    cost=call(client,'DELETE',f"/import-costs/{cost['settlement_id']}/rows/{key}",params={'reason':'미발생 비용 삭제'})
    assert len(cost['rows'])==4
    with factory() as db: assert db.query(AuditEvent).filter_by(action='DELETE_ROW').one().reason=='미발생 비용 삭제'


def test_one_connected_contract_document_import_actual_cost_and_lot_handoff(flow):
    client,factory=flow
    contract=confirmed_contract(client)
    document=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    document=call(client,'PUT',f"/contract-documents/{document['document_id']}",json={'body':document['body']+'\n수입건 추가 약정','reason':'확정 전 검토'})
    document=call(client,'POST',f"/contract-documents/{document['document_id']}/confirm")
    case,_,_=make_case(client,contract,linked=False)
    assert case['source_snapshot']==document['snapshot']
    purchase_input=purchase_data()
    for entry in purchase_input['items']: entry['bl_no']='BL-CONNECTED'
    purchase=call(client,'POST','/purchases',201,json=purchase_input)
    mapping={x['product_id']:x['contract_item_id'] for x in contract['items']}
    case=call(client,'PUT',f"/import-cases/{case['import_case_id']}",json={
        'contract_id':contract['contract_id'],'supplier_account_id':2,'bl_no':'BL-CONNECTED',
        'customs_date':'2026-10-02','warehouse_receipt_date':'2026-10-03',
        'items':[{'contract_item_id':mapping[x['product_id']],'product_id':x['product_id'],
            'lot_id':x['lot_id'],'box_qty':x['box_qty'],'weight':x['weight']} for x in purchase['items']]})
    call(client,'POST',f"/import-cases/{case['import_case_id']}/start")
    cost=fill_basic(client,basic_cost(client,case))
    for amount in [1000,-250]:
        cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/rows",201,json={
            'cost_name':'추가비용' if amount>0 else 'Claim 할인','amount':amount,'occurred_on':'2026-10-04'})
    cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",json={'reason':'계약부터 LOT까지 연결 검증'})
    assert cost['snapshot']['case']['source_snapshot']==document['snapshot']
    assert Decimal(cost['snapshot']['total_cost'])==157803
    assert sum(Decimal(x['allocated_cost']) for x in cost['snapshot']['allocations'])==157803
    with factory() as db:
        links=db.query(models.FinancingContractLot).filter_by(contract_id=contract['contract_id']).all()
        assert {x.lot_id for x in links}=={x['lot_id'] for x in purchase['items']}
        assert sum(x.contract_weight for x in links)==190
        assert db.query(models.OutboundItem).count()==0 and db.query(models.Sale).count()==0
        assert db.query(AuditEvent).filter_by(entity_type='IMPORTCOSTSETTLEMENT',action='CONFIRM').count()==1
    document_snapshot=document['snapshot']; cost_snapshot=cost['snapshot']
    with factory() as db:
        db.get(models.Account,1).account_name='나중에 변경된 업체'; db.get(models.Product,1).product_name='나중에 변경된 상품'; db.commit()
    assert call(client,'GET',f"/contract-documents/{document['document_id']}")['snapshot']==document_snapshot
    assert call(client,'GET',f"/import-costs/{cost['settlement_id']}")['snapshot']==cost_snapshot


def test_actual_tax_capitalization_and_signed_fx_rounding_are_explicit(flow):
    client,_=flow; _,case,_=ready_case(flow)
    cost=call(client,'POST','/import-costs',201,json={'import_case_id':case['import_case_id'],'basic_rows':False})
    for data in [
        {'cost_name':'과세비용','amount':100,'tax_kind':'TAXABLE','tax_amount_krw':10,'capitalize_tax':True},
        {'cost_name':'불공제 원가 제외','amount':100,'tax_kind':'TAXABLE','tax_amount_krw':10,'capitalize_tax':False},
        {'cost_name':'외화할인','amount':'-0.01','currency':'USD','exchange_rate':'1300.50'},
    ]:
        cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/rows",201,json={**data,'occurred_on':'2026-10-04'})
    assert [Decimal(str(x['krw_amount'])) for x in cost['rows']]==[110,100,-13]
    cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",json={})
    assert Decimal(str(cost['total_cost']))==197
    assert sum(Decimal(str(x['allocated_cost'])) for x in cost['allocations'])==197


def test_existing_purchase_opening_and_lot_master_cannot_rewrite_import_cost_basis(flow):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from test_trade_flow_integrity import main
    client,factory=flow; _,case,purchase=ready_case(flow)
    lot_id=purchase['items'][0]['lot_id']
    cost=fill_basic(client,basic_cost(client,case))
    cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",json={})
    with factory() as db:
        lot=db.get(models.Lot,lot_id)
        before=lot.individual_cost
        payload={'lot_code':lot.lot_code,'product_id':lot.product_id,'warehouse_id':lot.warehouse_id,
            'bl_no':lot.bl_no,'individual_cost':str(before+1),'source_type':lot.source_type}
        header=SimpleNamespace(comp_code='00001',items=db.query(models.InboundItem).filter_by(lot_id=lot_id).all())
        with pytest.raises(HTTPException,match='409'):
            main._guard_opening_inventory_changes(db,header)
    call(client,'PUT',f'/lots/{lot_id}',409,json=payload)
    call(client,'POST',f"/purchases/{purchase['purchase_id']}/cancel",409,json={'reason':'연결 원가 보호'})
    with factory() as db:
        assert db.get(models.Lot,lot_id).individual_cost==before
        assert db.get(models.Purchase,purchase['purchase_id']).document_status=='CONFIRMED'
        assert db.get(models.ImportCostSettlement,cost['settlement_id']).status=='CONFIRMED'


def test_cross_company_detail_ids_are_not_visible_or_mutable(flow):
    client,_=flow; contract,case,_=ready_case(flow); cost=basic_cost(client,case)
    doc=call(client,'POST','/contract-documents',201,json={'contract_id':contract['contract_id'],'template_type':'IMPORT_AGENCY'})
    for resource,key in [('contract-documents',doc['document_id']),('import-cases',case['import_case_id']),('import-costs',cost['settlement_id'])]:
        foreign=BASE.replace('00001','00002')+f'/{resource}/{key}'
        assert client.get(foreign).status_code==404
    assert client.post(BASE.replace('00001','00002')+f"/import-costs/{cost['settlement_id']}/confirm",json={}).status_code==404
