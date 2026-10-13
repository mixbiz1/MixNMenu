"""Explicit tax/billing metadata. Separate charges use ordinary receivable FIFO."""
import json
from decimal import Decimal,ROUND_FLOOR
import models
from financing_intake_routes import fail,dumps,columns
from trade_common import tax_snapshot
from audit_service import record_audit_event
from settlement_service import source_allocated


def audit(db,request,row,action,before=None,reason=None,menu='FINANCING_RELEASE'):
    record_audit_event(db,comp_code=row.comp_code,user_id=request.state.user_id,menu_code=menu,
        action=action,entity_type='FINANCING_CHARGE',entity_id=row.charge_id,source=f'{request.method} {request.url.path}',
        before=before,after=view(row),reason=reason,related_entity_type='FINANCING_CONTRACT',related_entity_id=row.contract_id)


def view(row):
    result=columns(row);result['snapshot']=json.loads(result.pop('snapshot_json'));return result


def condition(term,code):
    aliases={'INOUT':{'INOUT','INBOUND_OUTBOUND'}}
    rows=[r for r in (term.get('conditions') or {}).get('expense_conditions',[]) if r.get('code') in aliases.get(code,{code})]
    if len(rows)>1:fail('동일 비용항목의 중복 청구조건을 정리하십시오.')
    return rows[0] if rows else {}


def is_separate(term,code):return condition(term,code).get('billing_mode')=='SEPARATE'


def separate_line(db,company,day,term,code,amount,lot_id):
    from financing_release_routes import D,ceil
    row=condition(term,code)
    if row.get('billing_mode')!='SEPARATE' or row.get('issuer_comp_code')!=company:
        fail('별도청구는 명시된 현재 청구법인에서만 전표화합니다. 타 법인 발행은 별도 승인 경로가 필요합니다.')
    if row.get('payer')!='ACTUAL_SHIPPER':fail('별도청구의 부담주체는 실제 출고업체로 명확히 지정하십시오.')
    tax=db.get(models.TaxCode,row.get('tax_code')) if row.get('tax_code') else None
    if not tax:fail('별도비용의 유효 세금코드가 필요합니다.')
    snapshot=tax_snapshot(tax,day)
    treatment=row.get('tax_treatment')
    if treatment not in {'EXEMPT','TAXABLE'} or tax.tax_kind!=treatment or (treatment=='EXEMPT' and D(tax.tax_rate)!=0):
        fail('비용 세무구분과 세금코드가 일치하지 않습니다.')
    expected='TAX_INVOICE' if treatment=='TAXABLE' else 'INVOICE'
    if row.get('evidence_type')!=expected:fail('비용 세무구분에 맞는 계산서/세금계산서 대상이 필요합니다.')
    if D(amount)<0:fail('음수 별도비용은 원청구 연결 수정증빙 경로가 필요합니다.')
    supply=ceil(amount)
    # Existing financing agreement policy: VAT for service fees is truncated per item.
    vat=int((D(supply)*D(tax.tax_rate)/100).quantize(Decimal(1),rounding=ROUND_FLOOR))
    return {'code':code,'lot_id':lot_id,'name':row.get('name') or code,'raw_amount':D(amount),
            'supply_amount':supply,'tax_amount':vat,'total_amount':supply+vat,**snapshot,
            'tax_treatment':treatment,'evidence_type':expected,'issuer_comp_code':company,
            'payer':'ACTUAL_SHIPPER','term_id':term['term_id'],'term_version':term['version']}


def materialize(db,company,release,request):
    lines=json.loads(release.snapshot_json).get('separate_charges',[])
    if not lines:return None
    old=db.query(models.FinancingCharge).filter_by(comp_code=company,release_id=release.release_id).first()
    if old:fail('별도청구가 이미 존재합니다. 중복 채권 생성은 허용하지 않습니다.')
    for line in lines:
        tax=db.get(models.TaxCode,line['tax_code_snapshot'])
        now=tax_snapshot(tax,release.release_date) if tax else None
        if not now or tax.tax_kind!=line['tax_treatment'] or any(str(now[k])!=str(line[k]) for k in ('tax_code_snapshot','tax_name_snapshot')) or Decimal(now['tax_rate_snapshot'])!=Decimal(line['tax_rate_snapshot']):
            fail('별도청구 세금코드가 견적 이후 변경되었습니다.')
    supply=sum(x['supply_amount'] for x in lines);tax=sum(x['tax_amount'] for x in lines)
    row=models.FinancingCharge(comp_code=company,contract_id=release.contract_id,release_id=release.release_id,
        account_id=release.shipper_account_id,charge_date=release.release_date,supply_amount=supply,tax_amount=tax,
        total_amount=supply+tax,status='CONFIRMED',created_by=request.state.user_id,
        snapshot_json=dumps({'release_id':release.release_id,'source':json.loads(release.snapshot_json)['source'],
            'shipper':json.loads(release.snapshot_json)['shipper'],'lines':lines,'supply_amount':supply,'tax_amount':tax,'total_amount':supply+tax}))
    db.add(row);db.flush()
    tx=models.AccountTransaction(comp_code=company,account_id=row.account_id,transaction_date=row.charge_date,
        transaction_no=f'FCH-{row.charge_id}',transaction_type='SALES_RECEIVABLE',original_amount=row.total_amount,
        memo=f'Financing 별도비용 / 출고정산 {release.release_id}')
    db.add(tx);db.flush();row.transaction_id=tx.account_transaction_id;audit(db,request,row,'CONFIRM')
    return row


def cancel(db,release,request,reason):
    row=db.query(models.FinancingCharge).filter_by(comp_code=release.comp_code,release_id=release.release_id,status='CONFIRMED').first()
    if not row:return
    if db.query(models.AccountTransactionAllocation).filter_by(source_transaction_id=row.transaction_id).first():fail('수금/충당된 별도청구는 출고를 취소하기 전에 반제를 취소하십시오.')
    before=view(row);tx=db.get(models.AccountTransaction,row.transaction_id)
    row.transaction_id=None;row.status='CANCELLED';db.flush();db.delete(tx);audit(db,request,row,'CANCEL',before,reason)
