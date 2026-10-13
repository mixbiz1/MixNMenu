"""Read-only contract reconciliation and guarded immutable final close."""
import json
from datetime import date,datetime,timezone
from decimal import Decimal
from fastapi import APIRouter,Depends,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.orm import Session
from database import get_db
import models
import financing_contract_routes as contracts
from financing_intake_routes import atomic,columns,dumps,fail
from settlement_service import source_allocated
from trade_common import ensure_period_open
from audit_service import record_audit_event

router=APIRouter(prefix='/api/v1/companies/{comp_code}/financing-closures')

class Close(BaseModel):
    model_config=ConfigDict(extra='forbid')
    closed_on:date
    reason:str=Field(min_length=1,max_length=1000)
    unbilled_costs_reviewed:bool=False
    bank_and_overpayments_reviewed:bool=False
    review_reference:str=Field(min_length=1,max_length=1000)


def reconciliation(db,company,contract):
    import main
    releases=db.query(models.FinancingRelease).filter_by(comp_code=company,contract_id=contract.contract_id).order_by(models.FinancingRelease.release_id).all()
    shipped=[r for r in releases if r.status=='SHIPPED'];issues=[];quantities={};components={};source_rows=[];charge_totals={'supply_amount':0,'tax_amount':0,'total_amount':0}
    for row in shipped:
        snapshot=json.loads(row.snapshot_json)
        for line in snapshot['lines']:
            q=quantities.setdefault(line['lot_id'],{'box_qty':0,'weight':Decimal(0)})
            q['box_qty']+=line['box_qty'];q['weight']+=Decimal(line['weight'])
            if 'COST' not in line['components']:issues.append(f"출고 {row.release_id} 원가회수/반품 검증 필요")
            for key,value in line['components'].items():components[key]=components.get(key,Decimal(0))+Decimal(value)
        sale=db.get(models.Sale,row.sale_id)
        if not sale or sale.document_status!='CONFIRMED':issues.append(f'출고 {row.release_id} 원매출 상태 불일치');continue
        tx=db.query(models.AccountTransaction).filter_by(comp_code=company,transaction_no=sale.sale_no,transaction_type='SALES_RECEIVABLE').first()
        if not tx:issues.append(f'출고 {row.release_id} 원채권 없음')
        else:source_rows.append({'source_type':'SALE','source_id':sale.sale_id,'transaction_id':tx.account_transaction_id,
            'amount':int(tx.original_amount),'settled':int(source_allocated(db,tx.account_transaction_id)),
            'remaining':int(tx.original_amount-source_allocated(db,tx.account_transaction_id))})
        charges=db.query(models.FinancingCharge).filter_by(comp_code=company,release_id=row.release_id,status='CONFIRMED').all()
        if snapshot.get('separate_charges') and len(charges)!=1:issues.append(f'출고 {row.release_id} 별도비용 미청구')
        for charge in charges:
            if int(charge.total_amount)!=snapshot.get('separate_charge_total',0):issues.append(f'출고 {row.release_id} 별도청구 금액 불일치')
            tx=db.get(models.AccountTransaction,charge.transaction_id)
            if not tx:issues.append(f'비용 {charge.charge_id} 원채권 없음');continue
            source_rows.append({'source_type':'FINANCING_CHARGE','source_id':charge.charge_id,'transaction_id':tx.account_transaction_id,
                'amount':int(tx.original_amount),'settled':int(source_allocated(db,tx.account_transaction_id)),
                'remaining':int(tx.original_amount-source_allocated(db,tx.account_transaction_id))})
            for key in charge_totals:charge_totals[key]+=int(getattr(charge,key))
    lots=[];item_assigned={}
    for link in contract.lots:
        if link.status!='ACTIVE':continue
        q=quantities.get(link.lot_id,{'box_qty':0,'weight':Decimal(0)})
        remaining_box=link.contract_box_qty-q['box_qty'];remaining_weight=Decimal(link.contract_weight)-q['weight']
        stock_box,stock_weight=main._lot_available(db,company,link.lot_id)
        lots.append({'lot_id':link.lot_id,'lot_code':link.lot.lot_code,'contract_item_id':link.contract_item_id,
            'assigned_box':link.contract_box_qty,'assigned_weight':link.contract_weight,'shipped_box':q['box_qty'],'shipped_weight':q['weight'],
            'remaining_box':remaining_box,'remaining_weight':remaining_weight,'physical_box':stock_box,'physical_weight':stock_weight})
        if remaining_box!=0 or remaining_weight!=0:issues.append(f'LOT {link.lot.lot_code} 약정 출고 잔량/초과 존재')
        assigned=item_assigned.setdefault(link.contract_item_id,[0,Decimal(0)])
        assigned[0]+=link.contract_box_qty;assigned[1]+=Decimal(link.contract_weight)
    if not lots:issues.append('배정 LOT 없음')
    for item in contract.items:
        assigned=item_assigned.get(item.contract_item_id,[0,Decimal(0)])
        if assigned[0]!=item.contract_box_qty or assigned[1]!=Decimal(item.contract_weight):issues.append(f'계약상품 {item.contract_item_id} 계약/배정수량 불일치')
    if any(r.status not in {'SHIPPED','CANCELLED'} for r in releases):issues.append('미출고 초안/확정/입금확인 요청 존재')
    if any(x['remaining']!=0 for x in source_rows):issues.append('상품/별도비용 미수 또는 초과배분 존재')
    assignments=db.query(models.FinancingDepositAssignment).filter_by(comp_code=company,contract_id=contract.contract_id,status='ACTIVE').all()
    deposit_rows=[]
    for assignment in assignments:
        movements=db.query(models.FinancingDepositMovement).filter_by(comp_code=company,assignment_id=assignment.assignment_id,kind='APPLY',status='CONFIRMED').all()
        applied=sum(int(x.amount) for x in movements)
        remaining=int(assignment.amount)-applied
        deposit_rows.append({'assignment_id':assignment.assignment_id,'deposit_id':assignment.deposit_id,'amount':int(assignment.amount),'applied':applied,'remaining':remaining})
        if remaining!=0:issues.append(f'보증금 배정 {assignment.assignment_id} 담보해제/재배정/반환 필요')
        if any(not m.transaction_id for m in movements):issues.append('출고채권 미연결 보증금 충당 존재')
    cases=db.query(models.ImportCase).filter_by(comp_code=company,contract_id=contract.contract_id).all()
    for case in cases:
        if case.status not in {'COST_CONFIRMED','CLOSED'}:issues.append(f'수입건 {case.import_case_id} 원가정산 미확정')
    # Explicit review is still mandatory: unstructured bank overpayments and outside invoices
    # cannot be conclusively assigned to a contract by this system.
    first_snapshot=json.loads(shipped[0].snapshot_json) if shipped else {}
    return {'company':first_snapshot.get('source',{}).get('company',{'name':db.get(models.Company,company).comp_name}),
        'contractor':first_snapshot.get('source',{}).get('partner',{'name':contract.contractor.account_name}),
        'shippers':sorted({json.loads(x.snapshot_json)['shipper']['name'] for x in shipped}),
        'contract_id':contract.contract_id,'contract_no':contract.contract_no,'status':contract.status,
        'lots':lots,'releases':[{'release_id':x.release_id,'status':x.status,'sale_id':x.sale_id,'amount':int(x.total_amount)} for x in releases],
        'components':components,'separate_charge_totals':charge_totals,'receivables':source_rows,
        'billed_amount':sum(x['amount'] for x in source_rows),'settled_amount':sum(x['settled'] for x in source_rows),
        'remaining_receivable':sum(x['remaining'] for x in source_rows),'deposit_assignments':deposit_rows,
        'issues':list(dict.fromkeys(issues)),'can_close':not issues,'manual_reviews_required':['미청구비용/타법인 증빙','은행입금/초과입금 귀속']}

@router.get('')
def listing(comp_code:str,db:Session=Depends(get_db)):
    return [{**columns(x),'snapshot':json.loads(x.snapshot_json)} for x in db.query(models.FinancingClosure).filter_by(comp_code=comp_code).order_by(models.FinancingClosure.closure_id.desc()).all()]

@router.get('/contracts/{contract_id}')
def reconcile(comp_code:str,contract_id:int,db:Session=Depends(get_db)):
    return reconciliation(db,comp_code,contracts._contract(db,comp_code,contract_id))

@router.get('/{closure_id}')
def get(comp_code:str,closure_id:int,db:Session=Depends(get_db)):
    from financing_intake_routes import locked
    row=locked(db,models.FinancingClosure,comp_code,'closure_id',closure_id)
    return {**columns(row),'snapshot':json.loads(row.snapshot_json)}

@router.post('/contracts/{contract_id}/close',status_code=201)
def close(comp_code:str,contract_id:int,data:Close,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        contract=contracts._contract(db,comp_code,contract_id)
        old=db.query(models.FinancingClosure).filter_by(comp_code=comp_code,contract_id=contract_id).first()
        if old:
            if json.loads(old.snapshot_json)['review']!=data.model_dump(mode='json'):fail('이미 마감된 계약의 검토근거를 변경할 수 없습니다.')
            return {**columns(old),'snapshot':json.loads(old.snapshot_json)}
        if contract.status not in {'CONFIRMED','ACTIVE'}:fail('확정/진행 계약만 최종 마감하십시오.')
        ensure_period_open(db,comp_code,data.closed_on)
        if not data.reason.strip() or not data.review_reference.strip() or not data.unbilled_costs_reviewed or not data.bank_and_overpayments_reviewed:
            fail('미청구 비용 및 은행/초과입금 대사 확인과 검토 근거가 필요합니다.',400)
        snapshot=reconciliation(db,comp_code,contract)
        if snapshot['issues']:fail('계약마감 차단: '+' / '.join(snapshot['issues']))
        if any(date.fromisoformat(json.loads(r.snapshot_json)['input']['release_date'])>data.closed_on for r in db.query(models.FinancingRelease).filter_by(comp_code=comp_code,contract_id=contract_id,status='SHIPPED').all()):fail('최종 출고일보다 이전에 계약을 마감할 수 없습니다.')
        for source in snapshot['receivables']:
            allocations=db.query(models.AccountTransactionAllocation).filter_by(source_transaction_id=source['transaction_id']).all()
            if any(db.get(models.AccountTransaction,a.settlement_transaction_id).transaction_date>data.closed_on for a in allocations):
                fail('마감일 이후 입금/충당으로 반제된 채권은 해당 마감일에 완료로 처리할 수 없습니다.')
        snapshot['review']=data.model_dump(mode='json')
        row=models.FinancingClosure(comp_code=comp_code,contract_id=contract_id,closed_on=data.closed_on,snapshot_json=dumps(snapshot),created_by=request.state.user_id)
        db.add(row);db.flush();before={'status':contract.status};contract.status='CLOSED';contract.updated_by=request.state.user_id;contract.updated_at=datetime.now(timezone.utc)
        record_audit_event(db,comp_code=comp_code,user_id=request.state.user_id,menu_code='FINANCING_CLOSE',action='CLOSE',
            entity_type='FINANCING_CONTRACT',entity_id=contract_id,source=f'{request.method} {request.url.path}',
            before=before,after={'status':'CLOSED','closure_id':row.closure_id,'reconciliation':snapshot},reason=data.reason)
        return {**columns(row),'snapshot':json.loads(row.snapshot_json)}


def ensure_source_mutable(db,source_id):
    tx=db.get(models.AccountTransaction,source_id)
    if not tx or tx.transaction_type!='SALES_RECEIVABLE':return
    release=db.query(models.FinancingRelease).join(models.Sale,models.FinancingRelease.sale_id==models.Sale.sale_id).filter(
        models.FinancingRelease.comp_code==tx.comp_code,models.Sale.sale_no==tx.transaction_no).first()
    if not release:
        charge=db.query(models.FinancingCharge).filter_by(comp_code=tx.comp_code,transaction_id=source_id).first()
        if charge:release=db.get(models.FinancingRelease,charge.release_id)
    if release:
        contract=contracts._contract(db,tx.comp_code,release.contract_id)
        if contract.status=='CLOSED':fail('마감된 계약의 채권 반제를 변경할 수 없습니다.')
