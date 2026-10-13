"""Financing partial releases over existing ERP ledgers; frozen quote, bank check,
then one atomic SALE/OUTBOUND. Receipt registration remains a separate FIFO job.
"""
import json
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_CEILING, InvalidOperation
from typing import Literal
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from database import get_db
import models
import financing_contract_routes as contracts
from financing_intake_routes import atomic, locked, dumps, columns, fail, contract_source
from contract_document_templates import term_value
from audit_service import record_audit_event
from trade_common import apply_status_transition

router=APIRouter(prefix='/api/v1/companies/{comp_code}/financing-releases')
def D(value):
    try:
        result=Decimal(str(value))
        if not result.is_finite():raise InvalidOperation
        return result
    except (InvalidOperation,ValueError,TypeError):
        fail('금액/요율에 유효한 숫자를 입력하십시오.',400)

ceil=lambda value:int(D(value).quantize(Decimal(1),rounding=ROUND_CEILING))

class Line(BaseModel):
    model_config=ConfigDict(extra='forbid')
    lot_id:int
    box_qty:int=Field(ge=0)
    weight:Decimal=Field(gt=0,decimal_places=2)
    adjustment:int=0
    adjustment_kind:Literal['PRICE_ADJUSTMENT']|None=None
    adjustment_reason:str|None=Field(default=None,max_length=500)

class Quote(BaseModel):
    model_config=ConfigDict(extra='forbid')
    contract_id:int
    shipper_account_id:int
    release_date:date
    request_key:str=Field(min_length=1,max_length=64)
    # Explicit convention; not an assumed rate or a Warehouse master default.
    interest_year_days:Literal[365,366]
    interest_start_date:date|None=None
    interest_start_reason:str|None=Field(default=None,max_length=1000)
    lines:list[Line]=Field(min_length=1)

class Evidence(BaseModel):
    reference:str=Field(min_length=1,max_length=1000)
    amount:int=Field(ge=0)

class Reason(BaseModel):
    reason:str=Field(min_length=1,max_length=1000)


def locked_release(db,company,identity):
    contract_id=db.query(models.FinancingRelease.contract_id).filter_by(comp_code=company,release_id=identity).scalar()
    if contract_id is None:fail('현재 회사의 출고정산이 없습니다.',404)
    contracts._contract(db,company,contract_id)
    return locked(db,models.FinancingRelease,company,'release_id',identity)


def view(row):
    result=columns(row); result['snapshot']=json.loads(result.pop('snapshot_json')); return result


def audit(db,request,row,action,before=None,reason=None):
    row.updated_by=request.state.user_id; row.updated_at=datetime.now(timezone.utc)
    record_audit_event(db,comp_code=row.comp_code,user_id=request.state.user_id,menu_code='FINANCING_RELEASE',
        action=action,entity_type='FINANCING_RELEASE',entity_id=row.release_id,source=f'{request.method} {request.url.path}',
        before=before,after=view(row),reason=reason,related_entity_type='SALE' if row.sale_id else 'FINANCING_CONTRACT',
        related_entity_id=row.sale_id or row.contract_id)


def eligible(db,company,contract,shipper,day):
    if contract.status not in {'CONFIRMED','ACTIVE'}: fail('확정/진행 계약만 출고할 수 있습니다.')
    contracts._account(db,company,shipper,require_sale=True)
    if shipper!=contract.contractor_account_id:
        participant=next((p for p in contract.participants if p.account_id==shipper and p.role=='AUTHORIZED_SHIPPER'),None)
        if not participant or participant.status!='ACTIVE' or participant.agreement_status!='CONFIRMED' or not participant.agreement_date or participant.agreement_date>day or (participant.effective_date and participant.effective_date>day):
            fail('실제 출고업체의 특별출고약정 및 적용일을 확인하십시오.')


def capacity(db,company,contract,lines,exclude=None):
    import main
    quantities={}
    for line in lines:
        box,kg=quantities.get(line['lot_id'],(0,D(0)))
        quantities[line['lot_id']]=(box+line['box_qty'],kg+D(line['weight']))
    used={}; reserved={}; shipped={}
    for row in db.query(models.FinancingRelease).filter(models.FinancingRelease.comp_code==company,
            models.FinancingRelease.status.in_(['CONFIRMED','PAID','SHIPPED'])).all():
        if row.release_id==exclude: continue
        for line in json.loads(row.snapshot_json)['lines']:
            if row.contract_id==contract.contract_id:
                box,kg=used.get(line['lot_id'],(0,D(0))); used[line['lot_id']]=(box+line['box_qty'],kg+D(line['weight']))
            if row.status=='SHIPPED':
                key=(row.contract_id,line['lot_id']);box,kg=shipped.get(key,(0,D(0)))
                shipped[key]=(box+line['box_qty'],kg+D(line['weight']))
            if row.status!='SHIPPED' and row.contract_id==contract.contract_id:
                box,kg=reserved.get(line['lot_id'],(0,D(0))); reserved[line['lot_id']]=(box+line['box_qty'],kg+D(line['weight']))
    for lot_id,(box,kg) in sorted(quantities.items()):
        link=next((x for x in contract.lots if x.lot_id==lot_id and x.status=='ACTIVE' and x.contract_item_id),None)
        if not link: fail('계약상품에 배정된 ACTIVE LOT만 선택하십시오.')
        if link.conditions_override_json and json.loads(link.conditions_override_json):
            fail('LOT별 조건 override 정산은 아직 지원하지 않습니다. 계약 공통조건으로 임의 대체하지 않습니다.')
        lot=locked(db,models.Lot,company,'lot_id',lot_id)
        if lot.status!='OPEN' or not lot.use_yn: fail('보류/마감 LOT는 출고할 수 없습니다.')
        prev_box,prev_kg=used.get(lot_id,(0,D(0)))
        if box+prev_box>link.contract_box_qty or kg+prev_kg>D(link.contract_weight): fail('누적 출고/예약이 계약 LOT 약정수량을 초과합니다.')
        stock_box,stock_kg=main._lot_available(db,company,lot_id); rbox,rkg=reserved.get(lot_id,(0,D(0)))
        others=db.query(models.FinancingContractLot).join(models.FinancingContract).filter(
            models.FinancingContract.comp_code==company,models.FinancingContract.contract_id!=contract.contract_id,
            models.FinancingContract.status.in_(['DRAFT','CONFIRMED','ACTIVE']),
            models.FinancingContractLot.lot_id==lot_id,models.FinancingContractLot.status=='ACTIVE').all()
        other_box=other_kg=0
        for other in others:
            sold_box,sold_kg=shipped.get((other.contract_id,lot_id),(0,D(0)))
            other_box+=max(0,other.contract_box_qty-sold_box)
            other_kg+=max(D(0),D(other.contract_weight)-sold_kg)
        if box+rbox+other_box>stock_box or kg+rkg+other_kg>stock_kg:
            fail('현재 LOT 재고 및 다른 계약 미출고 배정/확정 예약을 초과합니다.')


def interest(principal,start,end,term,year_days):
    days=(end-start).days+1
    if days<1: fail('이자 기산일이 출고일보다 늦습니다.')
    first=term_value(term,'interest_rate_1' if term.get('interest_rate_1') is not None else 'annual_interest_rate')
    duration=term.get('interest_period_days_1')
    if first is None or not duration: fail('1차 이자율 및 적용기간을 확정하십시오.')
    n1=min(days,duration); n2=max(0,days-duration); second=term.get('interest_rate_2')
    if n2 and (second is None or not term.get('interest_period_days_2') or n2>term['interest_period_days_2']):
        fail('2차 이자율/기간 밖의 연장은 아직 지원하지 않습니다. 계약조건을 확인하십시오.')
    amount=principal*(D(first)*n1+D(second or 0)*n2)/100/year_days
    return amount,{'start':start,'end':end,'days_1':n1,'rate_1':first,'days_2':n2,'rate_2':second,'year_days':year_days}



def term_segments(terms, start, end):
    """Effective-date intervals, inclusive, without silently restarting accrual."""
    ordered=sorted(terms,key=lambda t:(str(t['effective_from']),t['version']))
    applicable=[t for t in ordered if date.fromisoformat(str(t['effective_from'])[:10])<=start]
    if not applicable: fail('비용 기산일에 적용되는 확정 계약조건이 없습니다.')
    current=applicable[-1]; cursor=start; result=[]
    for term in ordered:
        day=date.fromisoformat(str(term['effective_from'])[:10])
        if start<day<=end:
            result.append((cursor,day-timedelta(days=1),current));cursor=day;current=term
    if end<start: fail('비용 기산일이 출고일보다 늦습니다.')
    result.append((cursor,end,current))
    return result


def period_interest(principal,start,end,terms,year_days):
    total=D(0);details=[]
    for first,last,term in term_segments(terms,start,end):
        # Period 1/2 positions stay relative to the original financing start.
        # A new version changes rates, never implicitly grants extra days.
        amount,detail=interest(principal,start,last,term,year_days)
        if first>start:
            previous,_=interest(principal,start,first-timedelta(days=1),term,year_days)
            amount-=previous
        offset=(first-start).days;duration=term.get('interest_period_days_1')
        detail.update(start=first,end=last,days_1=max(0,min((last-start).days+1,duration)-offset),
                      days_2=max(0,(last-first).days+1-max(0,min((last-start).days+1,duration)-offset)),
                      term_id=term['term_id'],term_version=term['version'],amount=amount)
        details.append(detail);total+=amount
    return total,{'start':start,'end':end,'year_days':year_days,'segments':details}


def expense_rate(term,key,codes):
    rows=[x for x in (term.get('conditions') or {}).get('expense_conditions',[]) if x.get('code') in codes]
    if len(rows)>1: fail('동일 비용항목의 복수 조건은 먼저 정리하십시오.')
    if rows:
        row=rows[0]
        if row.get('unit_rate') is None: fail('비용 요율이 미확정입니다.')
        if D(row['unit_rate']) and row.get('billing_mode')!='SEPARATE' and (row.get('tax_treatment')!='EXEMPT' or row.get('payer') not in {'ORIGINAL_CONTRACTOR','ACTUAL_SHIPPER'}):
            fail('과세/별도 청구/다른 부담주체 비용은 자동 합산할 수 없습니다. 별도 정산 지원이 필요합니다.')
        expected='KG_DAY' if key=='storage_rate_per_kg_day' else 'BOX' if key=='weighing_rate_per_box' else 'KG'
        if row.get('basis')!=expected: fail('비용 계산단위가 해당 자동항목과 일치하지 않습니다.')
        return D(row['unit_rate'])
    value=term_value(term,key)
    if value is None: fail('창고료/입출고비/계근비 미입력과 0원을 구분하여 확정하십시오.')
    if D(value): fail('양수 비용에는 세무구분·부담주체가 기록된 비용행이 필요합니다.')
    return D(value)


def check_start(db,company,contract_id,start,exclude=None,year_days=None):
    for row in db.query(models.FinancingRelease).filter(models.FinancingRelease.comp_code==company,
            models.FinancingRelease.contract_id==contract_id,models.FinancingRelease.status.in_(['CONFIRMED','PAID','SHIPPED'])).all():
        saved=json.loads(row.snapshot_json)
        if row.release_id!=exclude and (saved['accrual_start']!=start.isoformat() or saved['input']['interest_year_days']!=year_days):
            fail('반복 출고는 이전 확정 정산의 이자 기산일과 연기준일수를 승계해야 합니다.')


def domestic_cost(db,company,contract,lot):
    if contract.contract_type!='DOMESTIC_PURCHASE' or lot.source_type!='DOMESTIC':
        fail('현재 계약/LOT의 확정 실제 원가배부가 필요합니다.')
    rows=db.query(models.PurchaseItem).join(models.Purchase).filter(
        models.Purchase.comp_code==company,models.Purchase.document_status=='CONFIRMED',
        models.PurchaseItem.lot_id==lot.lot_id).all()
    if len(rows)!=1:fail('국내매입 LOT의 단일 확정 매입 원가근거가 필요합니다.')
    item=rows[0]
    if item.discount_amount or item.tax_amount or D(item.weight)<=0 or D(item.supply_amount)<=0:
        fail('할인/과세/0원 국내매입의 금융원가 기준은 별도 확인이 필요합니다.')
    purchase=locked(db,models.Purchase,company,'purchase_id',item.purchase_id)
    inbound=db.get(models.InboundItem,item.inbound_item_id) if item.inbound_item_id else None
    if not inbound or inbound.lot_id!=lot.lot_id or inbound.weight!=item.weight or inbound.inbound.comp_code!=company:
        fail('국내매입 LOT의 확정 입고 연결을 확인하십시오.')
    if D(lot.individual_cost)!=D(item.unit_price):fail('국내매입 이후 LOT 원가가 변경되어 원가근거 확인이 필요합니다.')
    return {'kind':'DOMESTIC_PURCHASE','purchase_id':purchase.purchase_id,'purchase_item_id':item.purchase_item_id,
            'purchase_no':purchase.purchase_no,'supply_amount':item.supply_amount,'actual_weight':item.weight,
            'unit_price':item.unit_price,'inbound_item_id':inbound.inbound_item_id,'receipt_date':inbound.inbound.inbound_date}



def brokerage_amount(principal,start,end,segments):
    from contract_document_templates import term_value
    total=D(0);details=[];previous_rate=None
    for index,(first,last,term) in enumerate(segments):
        rate=term_value(term,'brokerage_rate_1' if term.get('brokerage_rate_1') is not None else 'brokerage_rate')
        if rate is None or not term.get('contract_days'):fail('계약수수료율 및 약정기간을 확인하십시오.')
        anchor=start if index==0 else first
        if (last-anchor).days+1>term['contract_days']:fail('연장 적용기간 밖 수수료는 별도 약정이 필요합니다.')
        if term['conditions'].get('brokerage_prebilled'):fail('기청구 수수료가 있어 자동 재청구를 차단합니다.')
        effective_rate=D(rate)
        if index:
            mode=term['conditions'].get('extension_brokerage_mode')
            if mode=='INCREMENTAL_DIFFERENCE':
                if effective_rate<previous_rate:fail('음수 연장수수료는 수정증빙 대사가 필요합니다.')
                effective_rate-=previous_rate
            elif mode!='ADDITIONAL_RATE':fail('연장수수료는 추가율/차액율 약정을 명시하십시오.')
        amount=principal*effective_rate/100;total+=amount
        details.append({'term_id':term['term_id'],'term_version':term['version'],'effective_from':first,
                        'basis_cost':principal,'rate':effective_rate,'amount':amount})
        previous_rate=D(rate)
    return total,details


def calculate(db,company,data):
    import main
    contract=contracts._contract(db,company,data.contract_id)
    main.ensure_period_open(db,company,data.release_date)
    eligible(db,company,contract,data.shipper_account_id,data.release_date)
    capacity(db,company,contract,[x.model_dump() for x in data.lines])
    source=contract_source(db,contract)
    # A later effective version cannot be retroactively treated as applicable
    # over a whole accrual interval; that engine is a later supported case.
    start=data.interest_start_date or contract.financing_start_date
    if start is None: fail('계약에 기산일이 없으면 출고정산에서 실제 이자 기산일과 근거를 입력하십시오.')
    if data.interest_start_date and data.interest_start_date!=contract.financing_start_date and not (data.interest_start_reason or '').strip():
        fail('실제 이자 기산일의 근거가 필요합니다. 확정 계약 Header는 변경하지 않습니다.',400)
    check_start(db,company,contract.contract_id,start,year_days=data.interest_year_days)
    terms=[t for t in source['contract']['terms'] if date.fromisoformat(str(t['effective_from'])[:10])<=start]
    term=max(terms,key=lambda t:(str(t['effective_from']),t['version'])) if terms else {}
    if not term or date.fromisoformat(str(term['effective_from'])[:10])>start: fail('기산일 이후 조건 변경의 구간별 정산은 아직 지원하지 않습니다.')
    segments=term_segments(source['contract']['terms'],start,data.release_date)
    if any(t['recovery_template']!=term['recovery_template'] for _,_,t in segments):
        fail('기간 중 회수유형 변경은 원가/비용 중복 회수 검토가 필요합니다.')
    if len(segments)>1 and term['recovery_template']=='ALL_IN' and not all(t['conditions'].get('extension_brokerage_mode') in {'ADDITIONAL_RATE','INCREMENTAL_DIFFERENCE'} for _,_,t in segments[1:]):
        fail('기간 중 수수료 조건변경은 잔존원가 및 기청구 대사가 필요합니다.')
    term=segments[-1][2]
    expense_rows=(term.get('conditions') or {}).get('expense_conditions',[])
    if not isinstance(expense_rows,list) or any(not isinstance(row,dict) for row in expense_rows):fail('계약 비용행 구조를 확인하십시오.',400)
    recovery=term['recovery_template']
    if recovery not in {'ALL_IN','EXCLUDE_BROKERAGE','EXCLUDE_BROKERAGE_STORAGE','COST_ONLY','FREE'}:
        fail('이자형 원가반품 및 자유형 회수는 아직 지원하지 않습니다.')
    selected={'COST','INOUT','WEIGHING'}
    if recovery!='COST_ONLY': selected.add('INTEREST')
    if recovery in {'ALL_IN','EXCLUDE_BROKERAGE'}: selected.add('STORAGE')
    if recovery=='ALL_IN': selected.add('BROKERAGE')
    if recovery=='FREE':
        chosen=term['conditions'].get('recovery_components')
        if not isinstance(chosen,list) or not chosen or any(not isinstance(x,str) for x in chosen) or len(chosen)!=len(set(chosen)) or set(chosen)-{'COST','INTEREST','STORAGE','INOUT','WEIGHING','BROKERAGE'} or 'COST' not in chosen:
            fail('자유형은 명시적 허용항목과 원가회수 포함조건이 필요합니다. 원가반품/미회수는 별도 승인 경로를 사용하십시오.')
        selected=set(chosen)
    from financing_charge_service import condition,is_separate,separate_line
    base_selected=set(selected)
    selected|={code for code in ['INTEREST','STORAGE','INOUT','WEIGHING','BROKERAGE'] if is_separate(term,code)}
    def billing_signature(active,code):
        row=condition(active,code)
        return (row.get('billing_mode','INCLUDED'),row.get('tax_treatment','EXEMPT'),
                row.get('issuer_comp_code',company),row.get('payer','ORIGINAL_CONTRACTOR'),row.get('tax_code'),row.get('evidence_type'))
    for code in selected & {'INTEREST','STORAGE','BROKERAGE'}:
        if any(billing_signature(active,code)!=billing_signature(term,code) for _,_,active in segments):
            fail('기간 중 세무/청구/부담주체 변경은 과거 비용구간별 증빙 대사가 필요합니다.')
    result=[]; inputs=[];separate_charges=[]
    for number,line in enumerate(data.lines,1):
        lot=locked(db,models.Lot,company,'lot_id',line.lot_id)
        if str(lot.product.tax_type) not in {'2','EXEMPT'}: fail('혼합 과세/가공상품 Financing은 별도 세무정산 지원이 필요합니다.')
        allocation=db.query(models.ImportCostAllocation,models.ImportCostSettlement,models.ImportCase).join(models.ImportCostSettlement,
            models.ImportCostAllocation.settlement_id==models.ImportCostSettlement.settlement_id).join(models.ImportCase,
            models.ImportCostSettlement.import_case_id==models.ImportCase.import_case_id).filter(models.ImportCostAllocation.lot_id==lot.lot_id,
            models.ImportCostSettlement.comp_code==company,models.ImportCostSettlement.status=='CONFIRMED',
            models.ImportCase.contract_id==contract.contract_id).first()
        origin=None
        if not allocation:
            other_cost=db.query(models.ImportCostAllocation).join(models.ImportCostSettlement).filter(
                models.ImportCostAllocation.lot_id==lot.lot_id,models.ImportCostSettlement.comp_code==company,
                models.ImportCostSettlement.status=='CONFIRMED').first()
            if other_cost:fail('다른 계약의 확정 원가배부 LOT를 국내매입 원가로 대체할 수 없습니다.')
            origin=domestic_cost(db,company,contract,lot)
            part=settlement=case=None;frozen_rows=[]
            frozen={'allocated_cost':origin['supply_amount'],'actual_weight':origin['actual_weight']}
        else:
            part,settlement,case=allocation
            frozen_rows=json.loads(settlement.snapshot_json)['rows']
            frozen=next(x for x in json.loads(settlement.snapshot_json)['allocations'] if x['allocation_id']==part.allocation_id)
        if selected & {'INTEREST','STORAGE'} and any(x['cost_kind']=='PERIOD' and D(x['krw_amount'] or 0)!=0 for x in frozen_rows):
            fail('이미 원가에 포함된 기간비용이 있어 자동 재청구를 차단합니다. 청구구간 분리가 필요합니다.')
        cost=D(frozen['allocated_cost'])/D(frozen['actual_weight']); principal=cost*line.weight
        components={'COST':principal}; detail={};storage_detail=[]
        if 'INTEREST' in selected: components['INTEREST'],detail=period_interest(principal,start,data.release_date,source['contract']['terms'],data.interest_year_days) if len(segments)>1 else interest(principal,start,data.release_date,term,data.interest_year_days)
        if 'STORAGE' in selected:
            receipt_date=case.warehouse_receipt_date if case else origin['receipt_date']
            if not receipt_date or receipt_date>data.release_date: fail('실제 입고일을 확인하십시오.')
            storage_segments=term_segments(source['contract']['terms'],receipt_date,data.release_date)
            if any(billing_signature(t,'STORAGE')!=billing_signature(term,'STORAGE') for _,_,t in storage_segments):
                fail('입고 이후 창고료 청구/세무 변경은 기간별 증빙 대사가 필요합니다.')
            if any(t['recovery_template']!=recovery for _,_,t in storage_segments):
                fail('보관기간 중 회수유형 변경은 기간비용 대사가 필요합니다.')
            for first,last,t in storage_segments:
                rate=expense_rate(t,'storage_rate_per_kg_day',{'STORAGE'})
                storage_detail.append({'start':first,'end':last,'days':(last-first).days+1,'rate':rate,
                    'term_id':t['term_id'],'term_version':t['version'],'amount':line.weight*rate*((last-first).days+1)})
            components['STORAGE']=sum((x['amount'] for x in storage_detail),D(0))
        if 'INOUT' in selected:components['INOUT']=line.weight*expense_rate(term,'inbound_outbound_rate_per_kg',{'INOUT','INBOUND_OUTBOUND'})
        if 'WEIGHING' in selected:components['WEIGHING']=line.box_qty*expense_rate(term,'weighing_rate_per_box',{'WEIGHING'})
        brokerage_detail=[]
        if 'BROKERAGE' in selected:
            components['BROKERAGE'],brokerage_detail=brokerage_amount(principal,start,data.release_date,segments)
            row=condition(term,'BROKERAGE')
            if D(components['BROKERAGE']) and not is_separate(term,'BROKERAGE') and (row.get('tax_treatment')!='EXEMPT' or row.get('payer') not in {'ORIGINAL_CONTRACTOR','ACTUAL_SHIPPER'}):
                fail('과세 수수료는 명시적 별도청구 조건이 필요합니다.')
        # Support explicit supplementary contract charges; do not silently discard them.
        for row in expense_rows:
            code=row.get('code')
            if code in {'STORAGE','INOUT','INBOUND_OUTBOUND','WEIGHING','BROKERAGE','INTEREST'}:continue
            if not isinstance(code,str) or not code.strip():fail('추가비용 코드를 입력하십시오.')
            if row.get('unit_rate') is None:fail('추가비용 단가가 미확정입니다.')
            if not D(row['unit_rate']):continue
            if row.get('basis') not in {'KG','BOX'}:fail('추가비용은 부분출고 KG/BOX 비례 근거가 필요합니다. 고정/기간 기청구는 별도 대사가 필요합니다.')
            if not (row.get('billing_mode') in {'INCLUDED','SEPARATE'}):fail('추가비용의 포함/별도청구를 명시하십시오.')
            if code in components:fail('추가비용 코드가 중복됩니다.')
            components[code]=D(row['unit_rate'])*(line.weight if row['basis']=='KG' else line.box_qty)
        for code in list(components):
            if code=='COST':continue
            row=condition(term,code)
            if row.get('billing_mode')=='SEPARATE':
                charge=separate_line(db,company,data.release_date,term,code,components.pop(code),lot.lot_id)
                if charge['total_amount']:separate_charges.append(charge)
            elif code=='INTEREST' and row and (row.get('tax_treatment')!='EXEMPT' or row.get('payer') not in {'ACTUAL_SHIPPER','ORIGINAL_CONTRACTOR'}):
                fail('상품가격 포함 이자는 면세/부담주체 조건이 필요합니다.')
            elif code not in {'INTEREST','STORAGE','INOUT','WEIGHING','BROKERAGE'}:
                if row.get('tax_treatment')!='EXEMPT' or row.get('payer') not in {'ACTUAL_SHIPPER','ORIGINAL_CONTRACTOR'}:
                    fail('상품가격 포함 추가비용은 면세/부담주체 조건이 필요합니다.')
        # Historical nonzero supplementary conditions cannot vanish on a term change.
        for _,_,active in segments[:-1]:
            old_rows=active['conditions'].get('expense_conditions',[])
            if any(x.get('code') not in {'STORAGE','INOUT','INBOUND_OUTBOUND','WEIGHING','BROKERAGE','INTEREST'} and D(x.get('unit_rate') or 0) for x in old_rows):
                fail('기간 중 추가비용 변경은 기청구 대사가 필요합니다.')
        if line.adjustment and (not (line.adjustment_reason or '').strip() or line.adjustment_kind!='PRICE_ADJUSTMENT'):
            fail('면세상품 가격조정의 종류와 근거가 필요합니다. 과세/부대비용은 별도 정산하십시오.',400)
        raw=sum(components.values())+line.adjustment
        if raw<0: fail('정산금액은 음수일 수 없습니다.',400)
        price=ceil(raw/line.weight)
        inputs.append(main.SaleItemInput(line_no=number,product_id=lot.product_id,lot_id=lot.lot_id,
            box_qty=line.box_qty,weight=line.weight,unit_price=price,memo=f'Financing 계약 {contract.contract_no}'))
        result.append({'lot_id':lot.lot_id,'lot_code':lot.lot_code,'product_name':lot.product.product_name,
            'box_qty':line.box_qty,'weight':line.weight,'unit_price':price,'components':components,'interest':detail,'storage_segments':storage_detail,'brokerage_segments':brokerage_detail,
            'adjustment':line.adjustment,'adjustment_kind':line.adjustment_kind,'adjustment_reason':line.adjustment_reason,'raw_amount':raw,
            'rounding_difference':D(ceil(line.weight*price))-raw,'allocation_id':part.allocation_id if part else None,'cost_source':origin,
            'settlement_id':settlement.settlement_id if settlement else None,'lot_cost_at_quote':lot.individual_cost})
    prepared,_,_=main._prepare_sale_lines(db,company,data.release_date,inputs)
    totals=main.summarize_purchase(prepared)
    return {'input':data.model_dump(mode='json'),'source':source,'lines':result,'sale_items':[x.model_dump(mode='json') for x in inputs],
            'totals':totals,'accrual_start':start,'prepared_lines':prepared,'recovery_template':recovery,'bank_account':source['company'].get('bank1'),
            'shipper':{'account_id':data.shipper_account_id,'name':db.get(models.Account,data.shipper_account_id).account_name},
            'term_id':term['term_id'],'term_version':term['version'],
            'separate_charges':separate_charges,'separate_charge_total':sum(x['total_amount'] for x in separate_charges),
            'term_segments':[{'start':first,'end':last,'term_id':t['term_id'],'term_version':t['version']} for first,last,t in segments]}


@router.get('')
def listing(comp_code:str,contract_id:int|None=None,db:Session=Depends(get_db)):
    q=db.query(models.FinancingRelease).filter_by(comp_code=comp_code)
    if contract_id is not None:q=q.filter_by(contract_id=contract_id)
    return [view(x) for x in q.order_by(models.FinancingRelease.release_id.desc()).all()]

@router.get('/{release_id}/funding')
def funding(comp_code:str,release_id:int,db:Session=Depends(get_db)):
    from financing_deposit_routes import applied_to_release
    row=locked_release(db,comp_code,release_id)
    deposit=applied_to_release(db,row)
    return {'release_id':release_id,'request_amount':int(row.total_amount),'deposit_applied':deposit,
            'cash_required':int(row.total_amount)-deposit,'movements':[columns(x) for x in db.query(models.FinancingDepositMovement).filter_by(comp_code=comp_code,release_id=release_id).all()]}

@router.get('/{release_id}/charges')
def charges(comp_code:str,release_id:int,db:Session=Depends(get_db)):
    from financing_charge_service import view as charge_view
    locked_release(db,comp_code,release_id)
    return [charge_view(x) for x in db.query(models.FinancingCharge).filter_by(comp_code=comp_code,release_id=release_id).all()]

@router.get('/{release_id}')
def get(comp_code:str,release_id:int,db:Session=Depends(get_db)):
    row=locked_release(db,comp_code,release_id)
    result=view(row);result['funding']=funding(comp_code,release_id,db)
    return result

@router.post('',status_code=201)
def create(comp_code:str,data:Quote,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        contracts._contract(db,comp_code,data.contract_id) # serialization/idempotency
        old=db.query(models.FinancingRelease).filter_by(comp_code=comp_code,request_key=data.request_key).first()
        if old:
            if json.loads(old.snapshot_json)['input']!=data.model_dump(mode='json'):fail('동일 요청키에 다른 출고내용을 사용할 수 없습니다.')
            return view(old)
        snapshot=calculate(db,comp_code,data)
        row=models.FinancingRelease(comp_code=comp_code,contract_id=data.contract_id,shipper_account_id=data.shipper_account_id,
            release_date=data.release_date,request_key=data.request_key,status='DRAFT',snapshot_json=dumps(snapshot),
            total_amount=snapshot['totals']['total_amount'],created_by=request.state.user_id,updated_by=request.state.user_id)
        db.add(row);db.flush();audit(db,request,row,'CREATE'); return view(row)


def recheck(db,company,row):
    import main
    main.ensure_period_open(db,company,row.release_date)
    contract=contracts._contract(db,company,row.contract_id); eligible(db,company,contract,row.shipper_account_id,row.release_date)
    snapshot=json.loads(row.snapshot_json); check_start(db,company,contract.contract_id,date.fromisoformat(snapshot['accrual_start']),row.release_id,snapshot['input']['interest_year_days'])
    capacity(db,company,contract,snapshot['lines'],row.release_id)
    for line in snapshot['lines']:
        lot=locked(db,models.Lot,company,'lot_id',line['lot_id'])
        if line.get('cost_source'):
            current=domestic_cost(db,company,contract,lot)
            if json.loads(dumps(current))!=line['cost_source']:fail('견적 이후 국내매입 원가근거가 변경되었습니다. 새 정산을 작성하십시오.')
        else:
            settlement=locked(db,models.ImportCostSettlement,company,'settlement_id',line['settlement_id'])
            if settlement.status!='CONFIRMED':fail('견적 이후 실제 원가가 변경되었습니다. 새 출고정산을 작성하십시오.')
        if D(lot.individual_cost)!=D(line['lot_cost_at_quote']):fail('견적 이후 실제 원가가 변경되었습니다. 새 출고정산을 작성하십시오.')
    return snapshot

@router.post('/{release_id}/confirm')
def confirm(comp_code:str,release_id:int,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        row=locked_release(db,comp_code,release_id)
        if row.status in {'CONFIRMED','PAID','SHIPPED'}:return view(row)
        if row.status!='DRAFT':fail('초안만 입금요청을 확정할 수 있습니다.')
        before=view(row);recheck(db,comp_code,row)
        row.status='CONFIRMED';audit(db,request,row,'CONFIRM',before);return view(row)

@router.post('/{release_id}/payment-check')
def payment_check(comp_code:str,release_id:int,data:Evidence,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        row=locked_release(db,comp_code,release_id)
        from financing_deposit_routes import applied_to_release
        required=int(row.total_amount)-applied_to_release(db,row)
        if row.status in {'PAID','SHIPPED'} and row.payment_evidence==data.reference.strip() and data.amount==required:return view(row)
        if row.status!='CONFIRMED':fail('확정 입금요청만 입금확인할 수 있습니다.')
        if not data.reference.strip() or data.amount!=required:fail('실제 은행입금 근거와 입금요청 전액을 확인하십시오.',400)
        before=view(row);row.status='PAID';row.payment_evidence=data.reference.strip()
        row.payment_confirmed_by=request.state.user_id;row.payment_confirmed_at=datetime.now(timezone.utc)
        audit(db,request,row,'PAYMENT_CHECK',before,data.reference);return view(row)

@router.post('/{release_id}/ship')
def ship(comp_code:str,release_id:int,request:Request,db:Session=Depends(get_db)):
    import main
    with atomic(db):
        row=locked_release(db,comp_code,release_id)
        if row.status=='SHIPPED':return view(row)
        if row.status!='PAID':fail('실제 은행입금 확인 후 출고하십시오. RECEIPT 등록은 별도입니다.')
        before=view(row);snapshot=recheck(db,comp_code,row)
        data=main.SaleInput(sale_date=row.release_date,account_id=row.shipper_account_id,items=snapshot['sale_items'],
            memo=f"Financing 출고정산 {row.release_id}",audit_reason='입금확인 출고')
        sale=main._save_sale(comp_code,data,request,db,commit=False)
        if any(D(sale[key])!=D(snapshot['totals'][key]) for key in ('total_supply_amount','total_tax_amount','total_discount_amount','total_amount')):
            fail('정산 Snapshot과 현재 ERP 세무금액이 달라 새 정산이 필요합니다.')
        materialized=db.get(models.Sale,sale['sale_id'])
        for expected,actual in zip(snapshot['prepared_lines'],sorted(materialized.items,key=lambda item:item.line_no)):
            if any(str(expected[key])!=str(getattr(actual,key)) for key in ('tax_code_snapshot','tax_name_snapshot')) or D(expected['tax_rate_snapshot'])!=D(actual.tax_rate_snapshot):
                fail('정산 이후 세무속성이 변경되었습니다. 새 정산을 작성하십시오.')
        from financing_charge_service import materialize
        materialize(db,comp_code,row,request)
        row.sale_id=sale['sale_id'];row.status='SHIPPED'
        from financing_deposit_routes import materialize_applications
        materialize_applications(db,row,request)
        contract=db.get(models.FinancingContract,row.contract_id)
        if contract.status=='CONFIRMED':
            contract.status='ACTIVE';contract.updated_by=request.state.user_id;contract.updated_at=datetime.now(timezone.utc)
            record_audit_event(db,comp_code=comp_code,user_id=request.state.user_id,menu_code='FINANCING_RELEASE',
                action='ACTIVATE',entity_type='FINANCING_CONTRACT',entity_id=contract.contract_id,
                source=f'{request.method} {request.url.path}',before={'status':'CONFIRMED'},after={'status':'ACTIVE'},
                related_entity_type='SALE',related_entity_id=row.sale_id)
        audit(db,request,row,'SHIP',before);return view(row)

@router.post('/{release_id}/cancel')
def cancel(comp_code:str,release_id:int,data:Reason,request:Request,db:Session=Depends(get_db)):
    import main
    with atomic(db):
        row=locked_release(db,comp_code,release_id)
        if row.status=='CANCELLED':return view(row)
        if not data.reason.strip():fail('취소 사유가 필요합니다.',400)
        contract=contracts._contract(db,comp_code,row.contract_id)
        if contract.status=='CLOSED':fail('마감된 계약의 출고정산은 취소할 수 없습니다.')
        before=view(row)
        from financing_deposit_routes import cancel_release_applications
        cancel_release_applications(db,row,request,data.reason)
        if row.status=='SHIPPED':
            from financing_charge_service import cancel as cancel_charge
            cancel_charge(db,row,request,data.reason)
            sale=main._sale_or_404(db,comp_code,row.sale_id); main.ensure_period_open(db,comp_code,sale.sale_date)
            sale_before=main._sale_snapshot(db,sale)
            main._dematerialize_sale(db,sale,financing_release_id=row.release_id)
            apply_status_transition(sale,'CANCELLED',request.state.user_id);db.flush()
            record_audit_event(db,comp_code=comp_code,user_id=request.state.user_id,menu_code='SALES_GENERAL',
                action='CANCEL',entity_type='SALE',entity_id=sale.sale_id,source=f'{request.method} {request.url.path}',
                before=sale_before,after=main._sale_snapshot(db,sale),reason=data.reason)
        row.status='CANCELLED';audit(db,request,row,'CANCEL',before,data.reason);return view(row)


# A signed supplementary agreement is additive. The original contract header,
# existing document snapshots and ordinary participant-edit guards stay intact.
agreement_router=APIRouter(prefix='/api/v1/companies/{comp_code}/financing-special-shippers')

class SignedSupplement(BaseModel):
    model_config=ConfigDict(extra='forbid')
    contract_id:int
    account_id:int
    agreement_date:date
    effective_date:date
    reference:str=Field(min_length=1,max_length=300)
    joint_liability_confirmed:bool
    memo:str|None=Field(default=None,max_length=400)


def participant_view(row):
    return {**columns(row),'comp_code':row.contract.comp_code,'contract_no':row.contract.contract_no,
            'account_name':row.account.account_name}


def special_row(db,company,participant_id):
    identity=db.query(models.FinancingContractParticipant.contract_id).join(models.FinancingContract).filter(
        models.FinancingContract.comp_code==company,models.FinancingContractParticipant.participant_id==participant_id).first()
    if not identity:fail('현재 회사의 특별출고약정이 없습니다.',404)
    contracts._contract(db,company,identity[0])
    row=db.query(models.FinancingContractParticipant).with_hint(models.FinancingContractParticipant,
        'WITH (UPDLOCK, HOLDLOCK)',dialect_name='mssql').with_for_update().filter_by(participant_id=participant_id,contract_id=identity[0]).first()
    if row.role!='AUTHORIZED_SHIPPER':fail('최초 계약책임자는 특별약정 철회로 변경할 수 없습니다.')
    return row

@agreement_router.get('')
def special_list(comp_code:str,db:Session=Depends(get_db)):
    rows=db.query(models.FinancingContractParticipant).join(models.FinancingContract).filter(
        models.FinancingContract.comp_code==comp_code,models.FinancingContractParticipant.role=='AUTHORIZED_SHIPPER').all()
    return [participant_view(row) for row in rows]

@agreement_router.get('/{participant_id}')
def special_get(comp_code:str,participant_id:int,db:Session=Depends(get_db)):
    return participant_view(special_row(db,comp_code,participant_id))

@agreement_router.post('',status_code=201)
def special_create(comp_code:str,data:SignedSupplement,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        contract=contracts._contract(db,comp_code,data.contract_id)
        if contract.status not in {'CONFIRMED','ACTIVE'}:fail('확정 계약의 별도 서명된 추가 약정을 등록하십시오.')
        if not data.reference.strip() or not data.joint_liability_confirmed:fail('서명된 특별약정 근거 및 최초 계약업체와 추가 업체의 연대책임을 확인하십시오.',400)
        if data.effective_date<data.agreement_date:fail('약정 확인일보다 이전부터 출고할 수 없습니다.',400)
        if db.query(models.FinancingContractParticipant).filter_by(contract_id=contract.contract_id,account_id=data.account_id).first():
            fail('이미 등록된 참여업체입니다. 기존 약정 이력을 덮어쓰지 않습니다.')
        memo='서명된 특별출고약정: '+data.reference.strip()+' / 계약업체·추가업체 연대책임 확인'
        if data.memo:memo+=' / '+data.memo
        row=contracts._add_participant(db,contract,contracts.ParticipantInput(account_id=data.account_id,
            agreement_status='CONFIRMED',agreement_date=data.agreement_date,effective_date=data.effective_date,memo=memo),
            request.state.user_id,signed_supplement=True)
        return participant_view(row)

@agreement_router.post('/{participant_id}/revoke')
def special_revoke(comp_code:str,participant_id:int,data:Reason,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        row=special_row(db,comp_code,participant_id)
        if row.contract.status not in {'CONFIRMED','ACTIVE'}:fail('현재 계약 상태에서 특별출고약정을 철회할 수 없습니다.')
        if not data.reason.strip():fail('철회 사유를 입력하십시오.',400)
        if row.status=='INACTIVE':return participant_view(row)
        before=participant_view(row);row.status='INACTIVE'
        record_audit_event(db,comp_code=comp_code,user_id=request.state.user_id,menu_code='FINANCING_CONTRACT',
            action='REVOKE',entity_type='FINANCING_CONTRACT_PARTICIPANT',entity_id=row.participant_id,
            source=f'{request.method} {request.url.path}',before=before,after=participant_view(row),reason=data.reason,
            related_entity_type='FINANCING_CONTRACT',related_entity_id=row.contract_id)
        return participant_view(row)
