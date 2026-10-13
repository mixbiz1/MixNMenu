"""Real API/ledger integration for mixed charges, deposits and final close."""
import copy
import json
from datetime import date
from decimal import Decimal
import pytest
from test_trade_flow_integrity import db_factory
from test_batch1b_distribution_e2e import flow,call,BASE,purchase_data
from test_financing_releases import ready,ship
from test_financing_period_terms import add_version
from test_batch2a_contract_import_cost import contract_data
from audit_service import AuditEvent
import models


def separate(factory,payload,code='STORAGE',kind='TAXABLE',issuer='00001'):
    with factory() as db:
        term=db.get(models.FinancingContract,payload['contract_id']).terms[0];conditions=json.loads(term.conditions_json)
        row=next(x for x in conditions['expense_conditions'] if x['code']==code)
        row.update(billing_mode='SEPARATE',issuer_comp_code=issuer,payer='ACTUAL_SHIPPER',
            tax_treatment=kind,tax_code='VAT10' if kind=='TAXABLE' else 'EXEMPT',
            evidence_type='TAX_INVOICE' if kind=='TAXABLE' else 'INVOICE',name='별도 창고료')
        term.conditions_json=json.dumps(conditions);db.commit()


def receive(client,amount=1000,key='deposit-one',reference='BANK-DP-001',account=1):
    return call(client,'POST','/financing-deposits',201,json={'account_id':account,'received_on':'2026-10-01',
        'amount':amount,'request_key':key,'bank_reference':reference})


def assign(client,deposit,contract,amount=800,key='assign-one'):
    return call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/assign",201,json={'contract_id':contract,
        'assigned_on':'2026-10-02','amount':amount,'request_key':key})


def apply(client,deposit,assignment,release,amount=500,key='apply-one'):
    return call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/apply",201,json={'assignment_id':assignment['assignment_id'],
        'release_id':release['release_id'],'movement_date':'2026-10-05','amount':amount,'request_key':key,'reason':'보증금 계약대금 상계 합의'})


def request_and_confirm(client,payload):
    row=call(client,'POST','/financing-releases',201,json=payload)
    return call(client,'POST',f"/financing-releases/{row['release_id']}/confirm")


def bank_ship(client,row,amount=None):
    amount=int(row['total_amount']) if amount is None else amount
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",json={'reference':'BANK-REL','amount':amount})
    return call(client,'POST',f"/financing-releases/{row['release_id']}/ship")


@pytest.mark.parametrize('kind',['TAXABLE','EXEMPT'])
def test_separate_tax_charge_no_inventory_double_count_fifo_ledger_and_cancel_guard(flow,kind):
    client,factory=flow;payload,_=ready(flow);separate(factory,payload,kind=kind)
    row=ship(client,payload);snapshot=row['snapshot']
    assert 'STORAGE' not in snapshot['lines'][0]['components']
    charge=call(client,'GET',f"/financing-releases/{row['release_id']}/charges")[0]
    assert int(charge['supply_amount'])==27
    assert int(charge['tax_amount'])==(2 if kind=='TAXABLE' else 0)
    assert charge['snapshot']['lines'][0]['evidence_type']==('TAX_INVOICE' if kind=='TAXABLE' else 'INVOICE')
    with factory() as db:
        assert db.query(models.OutboundItem).count()==1
        assert db.query(models.AccountTransaction).filter_by(transaction_type='SALES_RECEIVABLE').count()==2
    ledger=call(client,'GET','/account-ledger',params={'account_id':1,'start_date':'2026-10-01','end_date':'2026-10-05'})
    assert any(x['source_type']=='FINANCING_RELEASE' and x['source_id']==row['release_id'] for x in ledger['transactions'])
    total=int(row['total_amount'])+int(charge['total_amount'])
    receipt=call(client,'POST','/receipts',201,json={'account_id':1,'receipt_date':'2026-10-05','amount':total,'memo':'상품/별도비용 수금'})
    assert receipt['allocated_amount']==total
    summary=call(client,'GET','/sales-receivable-summary',params={'account_id':1,'transaction_date':'2026-10-05'})
    assert summary['current_receivable']==0
    call(client,'POST',f"/financing-releases/{row['release_id']}/cancel",409,json={'reason':'수금배분 Guard'})


@pytest.mark.parametrize('problem',['issuer','evidence','tax','payer','included_tax'])
def test_unclear_service_metadata_cannot_become_exempt_product(flow,problem):
    client,factory=flow;payload,_=ready(flow);separate(factory,payload)
    with factory() as db:
        term=db.get(models.FinancingContract,payload['contract_id']).terms[0];conditions=json.loads(term.conditions_json);row=conditions['expense_conditions'][0]
        if problem=='issuer':row['issuer_comp_code']='00002'
        if problem=='evidence':row['evidence_type']='INVOICE'
        if problem=='tax':row['tax_code']='EXEMPT'
        if problem=='payer':row['payer']='ORIGINAL_CONTRACTOR'
        if problem=='included_tax':row['billing_mode']='INCLUDED'
        term.conditions_json=json.dumps(conditions);db.commit()
    call(client,'POST','/financing-releases',409,json=payload)


def test_free_explicit_components_and_signed_extra_discount(flow):
    client,factory=flow;payload,_=ready(flow,'FREE')
    with factory() as db:
        term=db.get(models.FinancingContract,payload['contract_id']).terms[0];conditions=json.loads(term.conditions_json)
        conditions['recovery_components']=['COST','INOUT'];conditions['expense_conditions'].append({'code':'DISCOUNT','basis':'KG','unit_rate':'-2',
            'billing_mode':'INCLUDED','tax_treatment':'EXEMPT','payer':'ACTUAL_SHIPPER','name':'약정 할인'})
        term.conditions_json=json.dumps(conditions);db.commit()
    row=ship(client,payload);line=row['snapshot']['lines'][0]
    assert set(line['components'])=={'COST','INOUT','DISCOUNT'} and Decimal(line['components']['DISCOUNT'])==-20
    assert row['sale_id']


def test_free_without_principal_recovery_stays_guarded(flow):
    client,factory=flow;payload,_=ready(flow,'FREE')
    with factory() as db:
        term=db.get(models.FinancingContract,payload['contract_id']).terms[0];conditions=json.loads(term.conditions_json);conditions['recovery_components']=['INTEREST']
        term.conditions_json=json.dumps(conditions);db.commit()
    call(client,'POST','/financing-releases',409,json=payload)


@pytest.mark.parametrize('mode,expected',[('ADDITIONAL_RATE','4.5'),('INCREMENTAL_DIFFERENCE','3.0')])
def test_explicit_extension_brokerage_remaining_partial_quantity_snapshot(flow,mode,expected):
    client,factory=flow;payload,_=ready(flow,'ALL_IN')
    first=ship(client,payload);frozen=copy.deepcopy(first['snapshot'])
    add_version(factory,payload)
    with factory() as db:
        term=max(db.get(models.FinancingContract,payload['contract_id']).terms,key=lambda t:t.version);term.brokerage_rate_1=Decimal(3)
        conditions=json.loads(term.conditions_json);conditions['extension_brokerage_mode']=mode
        term.conditions_json=json.dumps(conditions);db.commit()
    payload['request_key']='extension-partial';payload['release_date']='2026-10-06';payload['lines'][0]['weight']='5';payload['lines'][0]['box_qty']=0
    later=ship(client,payload);line=later['snapshot']['lines'][0]
    assert Decimal(line['components']['BROKERAGE'])==Decimal(line['components']['COST'])*Decimal(expected)/100
    assert len(line['brokerage_segments'])==2
    assert call(client,'GET',f"/financing-releases/{first['release_id']}")['snapshot']==frozen


def test_separate_charge_cancel_restores_inventory_without_orphan_receivable(flow):
    client,factory=flow;payload,_=ready(flow);separate(factory,payload)
    row=ship(client,payload)
    call(client,'POST',f"/financing-releases/{row['release_id']}/cancel",json={'reason':'청구/상품 동시 취소'})
    with factory() as db:
        assert db.query(models.OutboundItem).count()==0
        assert db.query(models.AccountTransaction).filter_by(transaction_type='SALES_RECEIVABLE').count()==0
        assert db.query(models.FinancingCharge).one().status=='CANCELLED'


def test_deposit_assignment_apply_ship_net_fifo_cancel_and_return(flow):
    client,factory=flow;payload,_=ready(flow);deposit=receive(client);assignment=assign(client,deposit,payload['contract_id'])
    row=request_and_confirm(client,payload);move=apply(client,deposit,assignment,row)
    funding=call(client,'GET',f"/financing-releases/{row['release_id']}/funding")
    assert funding['cash_required']==int(row['total_amount'])-500
    call(client,'POST',f"/financing-releases/{row['release_id']}/payment-check",400,json={'reference':'銀行','amount':int(row['total_amount'])})
    shipped=bank_ship(client,row,funding['cash_required'])
    with factory() as db:
        assert db.query(models.AccountTransaction).filter_by(transaction_type='RECEIPT').count()==0
        assert db.query(models.AccountTransaction).filter_by(transaction_type='DEPOSIT_APPLIED').one().original_amount==500
        assert db.query(models.AccountTransactionAllocation).one().allocated_amount==500
    summary=call(client,'GET','/sales-receivable-summary',params={'account_id':1,'transaction_date':'2026-10-05'})
    assert summary['current_receivable']==int(row['total_amount'])-500
    # Ordinary FIFO settles only the remaining debt, never the actual deposit bank transfer again.
    receipt=call(client,'POST','/receipts',201,json={'account_id':1,'receipt_date':'2026-10-05','amount':funding['cash_required'],'bank_reference':'BANK-CASH'})
    assert receipt['allocated_amount']==funding['cash_required']
    call(client,'POST',f"/financing-releases/{row['release_id']}/cancel",409,json={'reason':'일반수금 존재'})
    unchanged=call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}");assert unchanged['applied_amount']==500
    call(client,'DELETE',f"/receipts/{receipt['account_transaction_id']}")
    call(client,'POST',f"/financing-releases/{row['release_id']}/cancel",json={'reason':'출고복원'})
    restored=call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}");assert restored['balance']==1000 and restored['applied_amount']==0
    call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/assignments/{assignment['assignment_id']}/cancel",json={'reason':'담보해제'})
    returned=call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/return",201,json={'movement_date':'2026-10-06','amount':1000,'request_key':'return','reason':'실반환','bank_reference':'BANK-RETURN'})
    assert call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}")['balance']==0
    call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/movements/{returned['movement_id']}/cancel",409,json={'reason':'실송금취소 금지'})


def test_deposit_idempotency_and_shared_bank_reference_no_duplicate_cash(flow):
    client,factory=flow;deposit=receive(client);same=receive(client);assert same['deposit_id']==deposit['deposit_id']
    call(client,'POST','/financing-deposits',409,json={'account_id':1,'received_on':'2026-10-01','amount':1000,'request_key':'second','bank_reference':'BANK-DP-001'})
    call(client,'POST','/receipts',409,json={'account_id':1,'receipt_date':'2026-10-05','amount':1000,'bank_reference':'BANK-DP-001'})
    with factory() as db:
        assert db.query(models.FinancingDeposit).count()==1
        assert db.query(models.AccountTransaction).filter_by(transaction_type='RECEIPT').count()==0
    receipt=call(client,'POST','/receipts',201,json={'account_id':1,'receipt_date':'2026-10-05','amount':1000,'bank_reference':'BANK-RC-1'})
    call(client,'POST','/financing-deposits',409,json={'account_id':1,'received_on':'2026-10-01','amount':1000,'request_key':'from-rc','bank_reference':'BANK-RC-1'})


def test_deposit_guards_and_cross_company(flow):
    client,factory=flow;payload,_=ready(flow);deposit=receive(client);assignment=assign(client,deposit,payload['contract_id'])
    call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/assign",409,json={'contract_id':payload['contract_id'],'assigned_on':'2026-10-02','amount':300,'request_key':'over'})
    call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/return",409,json={'movement_date':'2026-10-05','amount':300,'request_key':'reserved','reason':'담보유지','bank_reference':'BANK-X'})
    call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/cancel",409,json={'reason':'배정존재'})
    assert client.get(BASE.replace('00001','00002')+f"/financing-deposits/{deposit['deposit_id']}").status_code==404
    row=request_and_confirm(client,payload);apply(client,deposit,assignment,row)
    call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/apply",409,json={'assignment_id':assignment['assignment_id'],'release_id':row['release_id'],
        'movement_date':'2026-10-05','amount':400,'request_key':'over-use','reason':'과다'})


def complete_contract(flow):
    client,factory=flow
    purchase_payload=purchase_data();purchase_payload['items']=purchase_payload['items'][:1]
    purchase=call(client,'POST','/purchases',201,json=purchase_payload)
    data=contract_data('DOMESTIC_PURCHASE');data['financing_start_date']='2026-10-01';data['items']=data['items'][:1]
    data['items'][0].update(contract_box_qty=10,contract_weight='100')
    data['terms'][0].update(recovery_template='COST_ONLY',inbound_outbound_rate_per_kg='0',weighing_rate_per_box='0')
    contract=call(client,'POST','/financing-contracts',201,json=data)
    call(client,'POST',f"/financing-contracts/{contract['contract_id']}/lots",201,json={'lot_id':purchase['items'][0]['lot_id'],
        'contract_item_id':contract['items'][0]['contract_item_id'],'contract_box_qty':10,'contract_weight':'100'})
    call(client,'POST',f"/financing-contracts/{contract['contract_id']}/confirm")
    payload={'contract_id':contract['contract_id'],'shipper_account_id':1,'release_date':'2026-10-05','interest_year_days':365,
        'request_key':'complete','lines':[{'lot_id':purchase['items'][0]['lot_id'],'box_qty':10,'weight':'100'}]}
    return payload


def close_data():return {'closed_on':'2026-10-06','reason':'최종업무 대사 완료','unbilled_costs_reviewed':True,
    'bank_and_overpayments_reviewed':True,'review_reference':'검토내역 FINAL-1'}


def test_close_requires_full_reconciliation_paid_ar_and_freezes_receipt_and_contract(flow):
    client,factory=flow;payload=complete_contract(flow)
    call(client,'POST',f"/financing-closures/contracts/{payload['contract_id']}/close",409,json=close_data())
    row=ship(client,payload)
    pending=call(client,'GET',f"/financing-closures/contracts/{payload['contract_id']}");assert not pending['can_close'] and pending['remaining_receivable']>0
    receipt=call(client,'POST','/receipts',201,json={'account_id':1,'receipt_date':'2026-10-05','amount':int(row['total_amount'])})
    clean=call(client,'GET',f"/financing-closures/contracts/{payload['contract_id']}");assert clean['can_close']
    denied={**close_data(),'unbilled_costs_reviewed':False}
    call(client,'POST',f"/financing-closures/contracts/{payload['contract_id']}/close",400,json=denied)
    closed=call(client,'POST',f"/financing-closures/contracts/{payload['contract_id']}/close",201,json=close_data())
    assert closed['snapshot']['remaining_receivable']==0
    again=call(client,'POST',f"/financing-closures/contracts/{payload['contract_id']}/close",201,json=close_data());assert again['closure_id']==closed['closure_id']
    call(client,'DELETE',f"/receipts/{receipt['account_transaction_id']}",409)
    call(client,'PUT',f"/receipts/{receipt['account_transaction_id']}",409,json={'account_id':1,'receipt_date':'2026-10-05','amount':1})
    call(client,'POST','/receipts',409,json={'account_id':1,'receipt_date':'2026-10-06','amount':-1,'memo':'마감반제 취소금지'})
    call(client,'POST',f"/financing-releases/{row['release_id']}/cancel",409,json={'reason':'마감 이후'})
    call(client,'POST','/financing-releases',409,json={**payload,'request_key':'closed-new'})
    with factory() as db:
        assert db.get(models.FinancingContract,payload['contract_id']).status=='CLOSED'
        assert db.query(AuditEvent).filter_by(entity_type='FINANCING_CONTRACT',action='CLOSE').count()==1


def test_close_unused_deposit_assignment_blocks_until_released(flow):
    client,_=flow;payload=complete_contract(flow);row=ship(client,payload)
    call(client,'POST','/receipts',201,json={'account_id':1,'receipt_date':'2026-10-05','amount':int(row['total_amount'])})
    deposit=receive(client);assignment=assign(client,deposit,payload['contract_id'])
    recon=call(client,'GET',f"/financing-closures/contracts/{payload['contract_id']}");assert not recon['can_close']
    call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/assignments/{assignment['assignment_id']}/cancel",json={'reason':'공동담보해제 후 다른 계약용 유지'})
    call(client,'POST',f"/financing-closures/contracts/{payload['contract_id']}/close",201,json=close_data())
    assert call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}")['balance']==1000


def test_full_deposit_application_requires_explicit_zero_cash_confirmation(flow):
    client,factory=flow;payload,_=ready(flow);release=request_and_confirm(client,payload)
    deposit=receive(client,int(release['total_amount']));assignment=assign(client,deposit,payload['contract_id'],int(release['total_amount']))
    apply(client,deposit,assignment,release,int(release['total_amount']))
    call(client,'POST',f"/financing-releases/{release['release_id']}/ship",409)
    call(client,'POST',f"/financing-releases/{release['release_id']}/payment-check",json={'reference':'보증금 전액충당 합의 / 실제 현금 0원','amount':0})
    call(client,'POST',f"/financing-releases/{release['release_id']}/ship")
    summary=call(client,'GET','/sales-receivable-summary',params={'account_id':1,'transaction_date':'2026-10-05'})
    assert summary['current_receivable']==0
    with factory() as db:assert db.query(models.AccountTransaction).filter_by(transaction_type='RECEIPT').count()==0


def test_deposit_split_between_contracts_release_and_reassign_without_double_amount(flow):
    client,_=flow;first=complete_contract(flow)
    # A second independent contract has no overlapping LOT assignment.
    data=contract_data('DOMESTIC_PURCHASE');data['contract_no']='SECOND-COLLATERAL';data['items']=data['items'][:1]
    second=call(client,'POST','/financing-contracts',201,json=data)
    call(client,'POST',f"/financing-contracts/{second['contract_id']}/confirm")
    deposit=receive(client,1000)
    one=assign(client,deposit,first['contract_id'],400,'split-one')
    assign(client,deposit,second['contract_id'],600,'split-two')
    assert call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}")['unassigned_amount']==0
    call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/assignments/{one['assignment_id']}/cancel",json={'reason':'공동담보 재배정'})
    assign(client,deposit,second['contract_id'],400,'reassign')
    assert call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}")['unassigned_amount']==0
    assert len(call(client,'GET',f"/financing-deposits/{deposit['deposit_id']}/history"))==5


def test_service_tax_master_change_after_confirmation_rolls_back_entire_release(flow):
    client,factory=flow;payload,_=ready(flow);separate(factory,payload)
    release=request_and_confirm(client,payload)
    call(client,'POST',f"/financing-releases/{release['release_id']}/payment-check",json={'reference':'은행','amount':int(release['total_amount'])})
    with factory() as db:db.get(models.TaxCode,'VAT10').tax_rate=Decimal(9);db.commit()
    call(client,'POST',f"/financing-releases/{release['release_id']}/ship",409)
    with factory() as db:
        assert db.query(models.Sale).count()==0 and db.query(models.OutboundItem).count()==0
        assert db.query(models.FinancingCharge).count()==0
        assert db.get(models.FinancingRelease,release['release_id']).status=='PAID'


def test_zero_separate_cost_never_creates_zero_receivable(flow):
    client,factory=flow;payload,_=ready(flow);separate(factory,payload)
    with factory() as db:
        term=db.get(models.FinancingContract,payload['contract_id']).terms[0];conditions=json.loads(term.conditions_json);conditions['expense_conditions'][0]['unit_rate']='0';term.conditions_json=json.dumps(conditions);db.commit()
    release=ship(client,payload)
    assert release['snapshot']['separate_charges']==[]
    with factory() as db:
        assert db.query(models.FinancingCharge).count()==0
        assert db.query(models.AccountTransaction).filter_by(transaction_type='SALES_RECEIVABLE').count()==1


def test_active_deposit_or_release_prevents_parent_contract_cancel(flow):
    client,_=flow;payload=complete_contract(flow);deposit=receive(client);assignment=assign(client,deposit,payload['contract_id'])
    call(client,'POST',f"/financing-contracts/{payload['contract_id']}/cancel",409,json={'reason':'배정이 남아 있음'})
    call(client,'POST',f"/financing-deposits/{deposit['deposit_id']}/assignments/{assignment['assignment_id']}/cancel",json={'reason':'배정해제'})
    request_and_confirm(client,payload)
    call(client,'POST',f"/financing-contracts/{payload['contract_id']}/cancel",409,json={'reason':'요청이 남아 있음'})


def test_cash_receipt_for_deposit_customer_requires_structured_bank_evidence(flow):
    client,_=flow;receive(client)
    call(client,'POST','/receipts',400,json={'account_id':1,'receipt_date':'2026-10-05','amount':1000})
    call(client,'POST','/receipts',409,json={'account_id':1,'receipt_date':'2026-10-05','amount':1000,'bank_reference':'bank-dp-001'})
    call(client,'POST','/receipts',201,json={'account_id':1,'receipt_date':'2026-10-05','amount':1000,'bank_reference':'REAL-SECOND-CASH'})


def test_future_receipt_cannot_make_earlier_close_appear_paid(flow):
    client,_=flow;payload=complete_contract(flow);row=ship(client,payload)
    call(client,'POST','/receipts',201,json={'account_id':1,'receipt_date':'2026-10-07','amount':int(row['total_amount'])})
    call(client,'POST',f"/financing-closures/contracts/{payload['contract_id']}/close",409,json=close_data())
    call(client,'POST',f"/financing-closures/contracts/{payload['contract_id']}/close",201,json={**close_data(),'closed_on':'2026-10-07'})
