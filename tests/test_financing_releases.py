"""One real contract -> cost -> partial quote -> bank check -> ERP -> FIFO E2E."""
import copy
import json
from datetime import date
from decimal import Decimal
import pytest
from test_trade_flow_integrity import db_factory
from test_batch1b_distribution_e2e import flow,call,BASE,state
from test_batch2a_contract_import_cost import ready_case,basic_cost,fill_basic
from test_batch2a_gui_permissions import ui_adapter
from permissions import issue_token,permission_for_request
from audit_service import AuditEvent
from financing_release_routes import interest
import models


def ready(flow, recovery='EXCLUDE_BROKERAGE', kind='IMPORT_AGENCY'):
    client,factory=flow;contract,case,purchase=ready_case(flow,kind)
    cost=fill_basic(client,basic_cost(client,case))
    cost=call(client,'POST',f"/import-costs/{cost['settlement_id']}/confirm",json={'allocation_method':'WEIGHT'})
    with factory() as db:
        row=db.get(models.FinancingContract,contract['contract_id']);row.financing_start_date=date(2026,10,3)
        term=row.terms[0];term.recovery_template=recovery;term.contract_days=90;term.interest_rate_2=Decimal('8.5');term.interest_period_days_2=90
        conditions=json.loads(term.conditions_json)
        conditions['expense_conditions']=[
            {'code':'STORAGE','basis':'KG_DAY','unit_rate':'0.9','tax_treatment':'EXEMPT','payer':'ORIGINAL_CONTRACTOR'},
            {'code':'INBOUND_OUTBOUND','basis':'KG','unit_rate':'0','tax_treatment':'EXEMPT','payer':'ACTUAL_SHIPPER'},
            {'code':'WEIGHING','basis':'BOX','unit_rate':'0','tax_treatment':'EXEMPT','payer':'ACTUAL_SHIPPER'},
            {'code':'BROKERAGE','tax_treatment':'EXEMPT','payer':'ORIGINAL_CONTRACTOR'}]
        term.conditions_json=json.dumps(conditions);db.commit()
    item=cost['snapshot']['allocations'][0]
    payload={'contract_id':contract['contract_id'],'shipper_account_id':1,'release_date':'2026-10-05',
             'interest_year_days':365,'request_key':'release-one','lines':[{'lot_id':item['lot_id'],'box_qty':1,'weight':'10.00'}]}
    return payload,cost


def ship(client,payload):
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json={'reference':'은행실입금 확인','amount':int(row['total_amount'])})
    return call(client,'POST',f"/financing-releases/{row['release_id']}/ship")


def test_partial_release_actual_shipper_sale_receivable_fifo_statement_and_repeat(flow):
    client,factory=flow;payload,cost=ready(flow)
    with factory() as db:
        db.add(models.Account(account_id=3,account_code='SHIP',account_name='실제 출고업체'));db.commit()
        db.add(models.CompanyAccount(comp_code='00001',account_id=3,sales_yn=True));db.commit()
    call(client,'POST','/financing-special-shippers',201,json={'contract_id':payload['contract_id'],'account_id':3,
        'agreement_date':'2026-10-03','effective_date':'2026-10-03','reference':'실제 서명된 특별출고약정서 TEST-3','joint_liability_confirmed':True})
    payload['shipper_account_id']=3
    row=ship(client,payload); snapshot=copy.deepcopy(row['snapshot']); sale=next(x for x in call(client,'GET','/sales') if x['sale_id']==row['sale_id'])
    assert sale['account_id']==3 and Decimal(sale['total_amount'])==Decimal(row['total_amount'])
    assert Decimal(str(sale['items'][0]['weight']))==Decimal('10.00')
    components=snapshot['lines'][0]['components']
    assert Decimal(components['STORAGE'])==Decimal('27')
    allocation=next(x for x in cost['snapshot']['allocations'] if x['lot_id']==payload['lines'][0]['lot_id'])
    principal=Decimal(allocation['allocated_cost'])/Decimal(allocation['actual_weight'])*10
    assert Decimal(components['COST'])==principal
    assert Decimal(components['INTEREST'])==principal*Decimal('7.5')*3/100/365
    with factory() as db:
        recv=db.query(models.AccountTransaction).filter_by(transaction_type='SALES_RECEIVABLE').one()
        assert recv.account_id==3 and recv.original_amount==Decimal(row['total_amount'])
        assert db.query(models.OutboundItem).count()==1
    repeated=call(client,'POST',f"/financing-releases/{row['release_id']}/ship")
    assert repeated['sale_id']==row['sale_id']
    again=call(client,'POST','/financing-releases',201,json=payload); assert again['release_id']==row['release_id']
    statement=call(client,'POST',f"/sales/{row['sale_id']}/statements",json={})
    assert statement['snapshot']['customer']['name']=='실제 출고업체'
    # Existing receipt FIFO remains the only settlement ledger.
    call(client,'POST','/receipts',201,json={'account_id':3,'receipt_date':'2026-10-05','amount':int(row['total_amount']),'memo':'실제 출고대금'})
    summary=call(client,'GET','/sales-receivable-summary',params={'account_id':3,'transaction_date':'2026-10-05'})
    assert summary['current_receivable']==0
    call(client,'POST',f"/financing-releases/{row['release_id']}/cancel",409,json={'reason':'입금 배분 Guard'})
    second={**payload,'request_key':'release-two','release_date':'2026-10-06'}
    second['lines']=[{**payload['lines'][0],'box_qty':0,'weight':'5.00'}]
    next_row=ship(client,second)
    assert next_row['sale_id']!=row['sale_id']
    assert call(client,'GET',f"/financing-releases/{row['release_id']}")['snapshot']==snapshot


def test_bank_check_required_idempotency_and_cancel_restore(flow):
    client,factory=flow;payload,_=ready(flow)
    row=call(client,'POST','/financing-releases',201,json=payload);pk=row['release_id']
    call(client,'POST',f'/financing-releases/{pk}/ship',409)
    call(client,'POST',f'/financing-releases/{pk}/confirm')
    call(client,'POST',f'/financing-releases/{pk}/payment-check',400,json={'reference':'은행','amount':1})
    call(client,'POST',f'/financing-releases/{pk}/ship',409)
    call(client,'POST',f'/financing-releases/{pk}/payment-check',json={'reference':'은행','amount':int(row['total_amount'])})
    shipped=call(client,'POST',f'/financing-releases/{pk}/ship')
    call(client,'POST',f"/sales/{shipped['sale_id']}/cancel",409,json={'reason':'직접 정정 금지'})
    cancelled=call(client,'POST',f'/financing-releases/{pk}/cancel',json={'reason':'출고요청 취소'})
    assert cancelled['snapshot']==row['snapshot']
    assert next(x for x in call(client,'GET','/sales',params={'include_cancelled':True}) if x['sale_id']==shipped['sale_id'])['document_status']=='CANCELLED'
    with factory() as db:
        assert db.query(models.OutboundItem).count()==0
        assert db.query(models.AccountTransaction).filter_by(transaction_type='SALES_RECEIVABLE').count()==0
        audit=db.query(AuditEvent).filter_by(entity_type='FINANCING_RELEASE',action='CANCEL').one()
        assert audit.reason=='출고요청 취소'


def test_duplicate_lot_cumulative_and_reservation_guard(flow):
    client,_=flow;payload,_=ready(flow)
    payload['lines']=[{**payload['lines'][0],'box_qty':9,'weight':'90'}, {**payload['lines'][0],'box_qty':6,'weight':'60'}]
    call(client,'POST','/financing-releases',409,json=payload)
    payload['lines']=[{**payload['lines'][0],'box_qty':10,'weight':'100'}]
    first=call(client,'POST','/financing-releases',201,json=payload)
    draft=call(client,'POST','/financing-releases',201,json={**payload,'request_key':'second'})
    call(client,'POST',f"/financing-releases/{first['release_id']}/confirm")
    call(client,'POST',f"/financing-releases/{draft['release_id']}/confirm",409)
    call(client,'POST','/financing-releases',409,json={**payload,'request_key':'third'})


@pytest.mark.parametrize('change',['shipper','stock','cost','tax'])
def test_shipping_rechecks_and_failure_is_atomic(flow,change):
    client,factory=flow;payload,_=ready(flow)
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json={'reference':'은행','amount':int(row['total_amount'])})
    with factory() as db:
        if change=='shipper':db.query(models.CompanyAccount).filter_by(account_id=1).one().trade_stop_yn=True
        if change=='cost':db.get(models.Lot,payload['lines'][0]['lot_id']).individual_cost+=1
        if change=='stock':db.query(models.InboundItem).filter_by(lot_id=payload['lines'][0]['lot_id']).first().weight=Decimal(1)
        if change=='tax':db.get(models.Product,1).tax_type='1'
        db.commit();before=db.query(AuditEvent).count()
    status=404 if change=='shipper' else 409 if change!='tax' else 409
    call(client,'POST',f"/financing-releases/{row['release_id']}/ship",status)
    with factory() as db:
        assert db.query(models.Sale).count()==0 and db.query(models.OutboundItem).count()==0
        assert db.query(AuditEvent).count()==before
        assert db.get(models.FinancingRelease,row['release_id']).status=='PAID'


def test_unapproved_shipper_and_company_permissions(flow):
    client,factory=flow;payload,_=ready(flow)
    payload['shipper_account_id']=2
    call(client,'POST','/financing-releases',404,json=payload)
    payload['shipper_account_id']=1
    row=call(client,'POST','/financing-releases',201,json=payload)
    assert client.get(BASE.replace('00001','00002')+f"/financing-releases/{row['release_id']}").status_code==404
    assert permission_for_request('POST',BASE+'/financing-releases/1/ship').menu_code=='FINANCING_RELEASE'
    assert permission_for_request('POST',BASE+'/financing-releases/1/ship').action=='update'
    with factory() as db:
        db.add(models.User(user_id='reader',user_name='읽기',password_hash='x',is_admin=False));db.commit()
        db.add(models.UserCompanyAccess(user_id='reader',comp_code='00001'));db.commit()
    client.headers['Authorization']='Bearer '+issue_token('reader')
    assert client.get(BASE+'/financing-releases').status_code==403
    assert client.post(BASE+'/financing-releases/1/ship').status_code==403


def test_interest_segments_and_period_limit():
    term={'interest_rate_1':'7','interest_period_days_1':30,'interest_rate_2':'8','interest_period_days_2':30}
    amount,detail=interest(Decimal(100000),date(2026,1,1),date(2026,2,1),term,365)
    assert amount==Decimal(100000)*(Decimal(7)*30+Decimal(8)*2)/100/365
    assert detail['days_1']==30 and detail['days_2']==2
    from fastapi import HTTPException
    with pytest.raises(HTTPException):interest(Decimal(100000),date(2026,1,1),date(2026,4,1),term,365)


@pytest.mark.parametrize('recovery',['ALL_IN','EXCLUDE_BROKERAGE','EXCLUDE_BROKERAGE_STORAGE','COST_ONLY'])
def test_supported_recovery_components_are_explicit(flow,recovery):
    client,_=flow;payload,_=ready(flow,recovery)
    row=call(client,'POST','/financing-releases',201,json=payload)
    components=row['snapshot']['lines'][0]['components']
    assert ('INTEREST' in components)==(recovery!='COST_ONLY')
    assert ('STORAGE' in components)==(recovery in {'ALL_IN','EXCLUDE_BROKERAGE'})
    assert ('BROKERAGE' in components)==(recovery=='ALL_IN')
    assert {'COST','INOUT','WEIGHING'}<=set(components)


@pytest.mark.parametrize('problem',['missing','taxable','version','unsupported','adjustment'])
def test_unknown_and_unsupported_conditions_never_become_default_prices(flow,problem):
    client,factory=flow;payload,_=ready(flow)
    with factory() as db:
        term=db.get(models.FinancingContract,payload['contract_id']).terms[0];conditions=json.loads(term.conditions_json)
        if problem=='missing':conditions['expense_conditions']=[x for x in conditions['expense_conditions'] if x['code']!='STORAGE'];term.storage_rate_per_kg_day=0;conditions.pop('document_rate_inputs',None)
        if problem=='taxable':conditions['expense_conditions'][0]['tax_treatment']='TAXABLE'
        if problem=='version':term.effective_from=date(2026,10,4)
        if problem=='unsupported':term.recovery_template='FREE'
        term.conditions_json=json.dumps(conditions);db.commit()
    if problem=='adjustment':payload['lines'][0]['adjustment']=-100
    call(client,'POST','/financing-releases',400 if problem=='adjustment' else 409,json=payload)
    with factory() as db:
        assert db.query(models.FinancingRelease).count()==0 and db.query(models.Sale).count()==0


def test_special_shipper_agreement_revocation_is_rechecked(flow):
    client,factory=flow;payload,_=ready(flow)
    with factory() as db:
        db.query(models.CompanyAccount).filter_by(account_id=2).one().sales_yn=True;db.commit()
    payload['shipper_account_id']=2
    call(client,'POST','/financing-releases',409,json=payload)
    with factory() as db:
        db.add(models.FinancingContractParticipant(contract_id=payload['contract_id'],account_id=2,role='AUTHORIZED_SHIPPER',
            agreement_status='CONFIRMED',agreement_date=date(2026,10,3),effective_date=date(2026,10,3),status='ACTIVE',created_by='tester'));db.commit()
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json={'reference':'은행','amount':int(row['total_amount'])})
    with factory() as db:
        db.query(models.FinancingContractParticipant).filter_by(account_id=2).one().agreement_status='PENDING';db.commit()
    call(client,'POST',f"/financing-releases/{row['release_id']}/ship",409)
    with factory() as db:assert db.query(models.Sale).count()==0


def test_gui_quote_bank_check_ship_uses_saved_data_without_reentry(flow,ui_adapter,monkeypatch):
    client,factory=flow;ui,_=ui_adapter;payload,_=ready(flow)
    from views.financing_release import FinancingReleaseWindow
    window=FinancingReleaseWindow()
    contract=call(client,'GET',f"/financing-contracts/{payload['contract_id']}")
    monkeypatch.setattr(window,'choose',lambda *a,**kw:contract)
    window.pick_contract()
    assert window.goods.rowCount()==len(contract['lots'])
    for index in reversed(range(window.goods.rowCount())):
        if window.goods.item(index,0).data(ui.Qt.UserRole)!=payload['lines'][0]['lot_id']:window.goods.removeRow(index)
    window.goods.item(0,1).setText('1');window.goods.item(0,2).setText('10.00')
    window.day.setText('2026-10-05');window.year_days.setText('365')
    window.create();assert window.current['status']=='DRAFT' and '입금요청' in window.result.toPlainText()
    window.confirm();window.evidence.setText('은행 GUI 확인');window.received.setText(str(window.current['total_amount']))
    window.check_payment();window.ship()
    assert window.current['status']=='SHIPPED' and window.current['sale_id']
    assert window.shipper.property('pk')==1
    window.close()


def test_ship_late_failure_rolls_back_sale_outbound_receivable_and_audit(flow,monkeypatch):
    client,factory=flow;payload,_=ready(flow)
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json={'reference':'은행','amount':int(row['total_amount'])})
    import financing_release_routes as release
    original=release.audit
    def fail_ship(db,request,row,action,*args,**kwargs):
        if action=='SHIP':raise RuntimeError('late safe fault injection')
        return original(db,request,row,action,*args,**kwargs)
    monkeypatch.setattr(release,'audit',fail_ship)
    with factory() as db:before=db.query(AuditEvent).count()
    call(client,'POST',f"/financing-releases/{row['release_id']}/ship",500)
    with factory() as db:
        assert db.query(models.Sale).count()==0 and db.query(models.OutboundItem).count()==0
        assert db.query(models.AccountTransaction).filter_by(transaction_type='SALES_RECEIVABLE').count()==0
        assert db.query(AuditEvent).count()==before
        saved=db.get(models.FinancingRelease,row['release_id']);assert saved.status=='PAID' and saved.sale_id is None


def test_original_contract_cost_master_changes_do_not_recompute_confirmed_request(flow):
    client,factory=flow;payload,_=ready(flow)
    row=call(client,'POST','/financing-releases',201,json=payload)
    frozen=copy.deepcopy(row['snapshot'])
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    with factory() as db:
        db.get(models.FinancingContract,payload['contract_id']).terms[0].storage_rate_per_kg_day=Decimal(999)
        db.get(models.Account,1).account_name='후속 Master';db.commit()
    reread=call(client,'GET',f"/financing-releases/{row['release_id']}")
    assert reread['snapshot']==frozen
    assert reread['snapshot']['shipper']['name']!='후속 Master'


def test_period_cost_already_capitalized_is_not_charged_again(flow):
    client,factory=flow;payload,cost=ready(flow)
    with factory() as db:
        row=db.get(models.ImportCostSettlement,cost['settlement_id']);frozen=json.loads(row.snapshot_json)
        frozen['rows'][0]['cost_kind']='PERIOD';frozen['rows'][0]['krw_amount']='100'
        row.snapshot_json=json.dumps(frozen);db.commit()
    call(client,'POST','/financing-releases',409,json=payload)


def test_payment_check_retry_is_idempotent_and_conflicting_reference_rejected(flow):
    client,factory=flow;payload,_=ready(flow)
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    evidence={'reference':'은행','amount':int(row['total_amount'])}
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json=evidence)
    with factory() as db:before=db.query(AuditEvent).count()
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json=evidence)
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",409,json={**evidence,'reference':'다른 은행'})
    with factory() as db:assert db.query(AuditEvent).count()==before


def test_tax_attribute_change_with_same_amount_also_rolls_back(flow):
    client,factory=flow;payload,_=ready(flow)
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json={'reference':'은행','amount':int(row['total_amount'])})
    with factory() as db:
        db.get(models.Product,1).tax_type='1';db.get(models.TaxCode,'VAT10').tax_rate=0;db.commit()
    call(client,'POST',f"/financing-releases/{row['release_id']}/ship",409)
    with factory() as db:assert db.query(models.Sale).count()==0


def test_actual_start_can_be_recorded_without_editing_confirmed_contract(flow,ui_adapter):
    client,factory=flow;ui,_=ui_adapter;payload,_=ready(flow)
    with factory() as db:
        db.get(models.FinancingContract,payload['contract_id']).financing_start_date=None;db.commit()
    call(client,'POST','/financing-releases',409,json=payload)
    payload.update(interest_start_date='2026-10-03')
    call(client,'POST','/financing-releases',400,json=payload)
    payload['interest_start_reason']='실제 원가확정 후 Financing 기산 근거'
    row=call(client,'POST','/financing-releases',201,json=payload)
    assert row['snapshot']['accrual_start']=='2026-10-03'
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    with factory() as db:assert db.get(models.FinancingContract,payload['contract_id']).financing_start_date is None
    call(client,'POST','/financing-releases',409,json={**payload,'request_key':'changed-start','interest_start_date':'2026-10-04'})


def test_gui_inherits_confirmed_release_start_when_contract_header_is_blank(flow,ui_adapter,monkeypatch):
    client,factory=flow;ui,_=ui_adapter;payload,_=ready(flow)
    with factory() as db:db.get(models.FinancingContract,payload['contract_id']).financing_start_date=None;db.commit()
    payload.update(interest_start_date='2026-10-03',interest_start_reason='실제 원가확정 근거')
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    from views.financing_release import FinancingReleaseWindow
    window=FinancingReleaseWindow()
    monkeypatch.setattr(window,'choose',lambda *a,**kw:call(client,'GET',f"/financing-contracts/{payload['contract_id']}"))
    window.pick_contract()
    assert window.start.text()=='2026-10-03' and window.start_reason.text()=='실제 원가확정 근거'
    window.close()


@pytest.mark.parametrize('kind',['IMPORT_AGENCY','BL_TRANSFER','DOMESTIC_PURCHASE'])
def test_three_contract_types_use_one_existing_sale_pipeline_when_cost_is_confirmed(flow,kind):
    client,factory=flow;payload,_=ready(flow,kind=kind)
    row=ship(client,payload)
    assert row['snapshot']['source']['contract']['contract_type']==kind
    with factory() as db:
        assert db.get(models.Sale,row['sale_id']).account_id==1
        assert db.query(models.Outbound).count()==1


def test_multiple_lots_two_warehouses_and_weight_only_flow(flow):
    client,factory=flow;payload,cost=ready(flow)
    lots=[x['lot_id'] for x in cost['snapshot']['allocations'] if x['product_id']==1]
    assert len(lots)==2
    payload['lines']=[{'lot_id':lots[0],'box_qty':1,'weight':'10.00'},
                      {'lot_id':lots[1],'box_qty':0,'weight':'5.00'}]
    row=ship(client,payload)
    assert len(row['snapshot']['lines'])==2
    with factory() as db:
        sale=db.get(models.Sale,row['sale_id'])
        assert len(sale.items)==2 and sale.total_box_qty==1 and sale.total_weight==Decimal(15)
        assert db.query(models.Outbound).count()==2 and db.query(models.OutboundItem).count()==2
    statement=call(client,'POST',f"/sales/{row['sale_id']}/statements")
    assert len(statement['snapshot']['items'])==2 and Decimal(statement['snapshot']['total_weight'])==Decimal(15)
    assert Decimal(statement['snapshot']['total_amount'])==Decimal(row['total_amount'])


def test_invalid_saved_json_rate_reports_validation_error_not_default_or_partial_data(flow):
    client,factory=flow;payload,_=ready(flow)
    with factory() as db:
        term=db.get(models.FinancingContract,payload['contract_id']).terms[0]
        conditions=json.loads(term.conditions_json);conditions['expense_conditions'][0]['unit_rate']='미입력'
        term.conditions_json=json.dumps(conditions);db.commit()
    call(client,'POST','/financing-releases',400,json=payload)
    with factory() as db:assert db.query(models.FinancingRelease).count()==0


def test_lot_specific_overrides_are_not_silently_ignored(flow):
    client,factory=flow;payload,_=ready(flow)
    with factory() as db:
        link=db.query(models.FinancingContractLot).filter_by(contract_id=payload['contract_id'],lot_id=payload['lines'][0]['lot_id']).one()
        link.conditions_override_json=json.dumps({'annual_interest_rate':'99'});db.commit()
    call(client,'POST','/financing-releases',409,json=payload)


def test_repeat_year_basis_must_match_confirmed_request(flow):
    client,_=flow;payload,_=ready(flow)
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    call(client,'POST','/financing-releases',409,json={**payload,'request_key':'changed-year','interest_year_days':366})


def test_other_contract_remaining_commitment_is_protected_after_general_sale(flow):
    client,factory=flow;payload,_=ready(flow)
    lot_id=payload['lines'][0]['lot_id']
    with factory() as db:
        own=db.query(models.FinancingContractLot).filter_by(contract_id=payload['contract_id'],lot_id=lot_id).one()
        own.contract_box_qty=5;own.contract_weight=Decimal(50);db.commit()
    from test_batch2a_contract_import_cost import contract_data
    data=contract_data();data['items']=data['items'][:1];data['items'][0].update(contract_box_qty=5,contract_weight='50')
    other=call(client,'POST','/financing-contracts',201,json=data)
    call(client,'POST',f"/financing-contracts/{other['contract_id']}/confirm")
    call(client,'POST',f"/financing-contracts/{other['contract_id']}/lots",201,json={
        'lot_id':lot_id,'contract_item_id':other['items'][0]['contract_item_id'],'contract_box_qty':5,'contract_weight':'50'})
    call(client,'POST','/sales',201,json={'sale_date':'2026-10-04','account_id':1,'items':[
        {'line_no':1,'product_id':1,'lot_id':lot_id,'box_qty':5,'weight':'50','unit_price':1000}]})
    call(client,'POST','/financing-releases',409,json=payload)


def test_manual_adjustment_is_explicit_goods_price_not_an_untyped_taxable_fee(flow):
    client,_=flow;payload,_=ready(flow)
    payload['lines'][0].update(adjustment=-100,adjustment_reason='합의한 면세상품 가격차감')
    call(client,'POST','/financing-releases',400,json=payload)
    payload['lines'][0]['adjustment_kind']='PRICE_ADJUSTMENT'
    row=call(client,'POST','/financing-releases',201,json=payload)
    assert row['snapshot']['lines'][0]['adjustment_kind']=='PRICE_ADJUSTMENT'


def test_signed_supplement_and_revocation_preserve_primary_header_and_confirmed_document(flow,ui_adapter,monkeypatch):
    client,factory=flow;ui,_=ui_adapter;payload,_=ready(flow)
    document=call(client,'POST','/contract-documents',201,json={'contract_id':payload['contract_id'],'template_type':'IMPORT_AGENCY'})
    frozen=call(client,'POST',f"/contract-documents/{document['document_id']}/confirm")['snapshot']
    with factory() as db:db.query(models.CompanyAccount).filter_by(account_id=2).one().sales_yn=True;db.commit()
    data={'contract_id':payload['contract_id'],'account_id':2,'agreement_date':'2026-10-03','effective_date':'2026-10-03',
          'reference':'서명약정 S-001','joint_liability_confirmed':False}
    call(client,'POST','/financing-special-shippers',400,json=data)
    call(client,'POST',f"/financing-contracts/{payload['contract_id']}/participants",409,json={'account_id':2})
    from views.financing_release import SpecialShipperWindow
    window=SpecialShipperWindow();window.contract.setProperty('pk',payload['contract_id']);window.account.setProperty('pk',2)
    window.signed.setText('2026-10-03');window.effective.setText('2026-10-03');window.reference.setText('서명약정 S-001');window.joint.setChecked(True)
    window.create(); participant=window.current
    assert participant['agreement_status']=='CONFIRMED' and '서명약정 S-001' in participant['memo']
    original=call(client,'GET',f"/financing-contracts/{payload['contract_id']}")
    assert original['contractor_account_id']==1 and original['status']=='CONFIRMED'
    assert call(client,'GET',f"/contract-documents/{document['document_id']}")['snapshot']==frozen
    payload['shipper_account_id']=2
    row=call(client,'POST','/financing-releases',201,json=payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json={'reference':'은행','amount':int(row['total_amount'])})
    window.reason.setText('추가업체 출고권한 철회');window.revoke()
    assert window.current['status']=='INACTIVE'
    call(client,'POST',f"/financing-releases/{row['release_id']}/ship",409)
    with factory() as db:
        assert db.query(models.Sale).count()==0
        revoke=db.query(AuditEvent).filter_by(entity_type='FINANCING_CONTRACT_PARTICIPANT',action='REVOKE').one()
        assert revoke.reason=='추가업체 출고권한 철회'
    window.close()
