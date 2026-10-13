"""Independent actual deposit ledger, explicit assignment and targeted application.
No bank receipt is auto-created a second time. All writes are one transaction.
"""
import json
from uuid import uuid4
from datetime import date
from decimal import Decimal
from fastapi import APIRouter,Depends,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy.orm import Session
import models
import financing_contract_routes as contracts
from database import get_db
from financing_intake_routes import atomic,locked,fail,dumps,columns
from trade_common import ensure_period_open
from audit_service import record_audit_event
from settlement_service import source_allocated

router=APIRouter(prefix='/api/v1/companies/{comp_code}/financing-deposits')

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Receive(Input):
    account_id:int
    received_on:date
    amount:int=Field(gt=0)
    bank_reference:str=Field(min_length=1,max_length=200)
    request_key:str=Field(min_length=1,max_length=64)

class Assign(Input):
    contract_id:int
    assigned_on:date
    amount:int=Field(gt=0)
    request_key:str=Field(min_length=1,max_length=64)

class Move(Input):
    movement_date:date
    amount:int=Field(gt=0)
    request_key:str=Field(min_length=1,max_length=64)
    reason:str=Field(min_length=1,max_length=1000)

class Apply(Move):
    assignment_id:int
    release_id:int

class Return(Move):
    bank_reference:str=Field(min_length=1,max_length=200)

class Reason(Input):
    reason:str=Field(min_length=1,max_length=1000)


def audit(db,request,row,action,before=None,reason=None):
    primary=next(c.name for c in row.__table__.columns if c.primary_key)
    record_audit_event(db,comp_code=row.comp_code,user_id=request.state.user_id,menu_code='FINANCING_DEPOSIT',
        action=action,entity_type={'FinancingDeposit':'FINANCING_DEPOSIT','FinancingDepositAssignment':'FINANCING_DEPOSIT_ASSIGNMENT','FinancingDepositMovement':'FINANCING_DEPOSIT_MOVEMENT'}[type(row).__name__],entity_id=getattr(row,primary),
        source=f'{request.method} {request.url.path}',before=before,after=columns(row),reason=reason,
        related_entity_type='FINANCING_CONTRACT' if getattr(row,'contract_id',None) else 'FINANCING_DEPOSIT',
        related_entity_id=getattr(row,'contract_id',None) or getattr(row,'deposit_id',None))


def claim_bank(db,company,reference,kind,identity):
    reference=reference.strip().upper()
    if not reference:fail('실제 은행 거래 식별근거를 입력하십시오.',400)
    existing=db.query(models.FinancingBankEvidence).filter_by(comp_code=company,reference=reference).first()
    if existing:
        if (existing.source_type,existing.source_id)==(kind,identity):return
        fail('동일 은행 거래근거가 이미 입금/보증금/반환에 연결되어 있습니다.')
    db.add(models.FinancingBankEvidence(comp_code=company,reference=reference,source_type=kind,source_id=identity));db.flush()


def active_contract(db,company,identity):
    row=contracts._contract(db,company,identity)
    if row.status not in {'CONFIRMED','ACTIVE'}:fail('확정/진행 계약만 보증금을 배정/충당할 수 있습니다.')
    return row


def amounts(db,row):
    assignments=db.query(models.FinancingDepositAssignment).filter_by(comp_code=row.comp_code,deposit_id=row.deposit_id,status='ACTIVE').all()
    movements=db.query(models.FinancingDepositMovement).filter_by(comp_code=row.comp_code,deposit_id=row.deposit_id,status='CONFIRMED').all()
    applied=sum(int(x.amount) for x in movements if x.kind=='APPLY')
    returned=sum(int(x.amount) for x in movements if x.kind=='RETURN')
    # An assignment's original amount remains consumed after its applied share is cancelled/reassigned.
    cancelled_used=0
    inactive=db.query(models.FinancingDepositAssignment).filter_by(comp_code=row.comp_code,deposit_id=row.deposit_id,status='CANCELLED').all()
    inactive_ids={x.assignment_id for x in inactive}
    cancelled_used=sum(int(x.amount) for x in movements if x.kind=='APPLY' and x.assignment_id in inactive_ids)
    reserved=sum(int(x.amount) for x in assignments)+cancelled_used
    return {'received_amount':int(row.amount) if row.status=='CONFIRMED' else 0,'applied_amount':applied,
            'returned_amount':returned,'balance':int(row.amount)-applied-returned if row.status=='CONFIRMED' else 0,
            'unassigned_amount':int(row.amount)-returned-reserved if row.status=='CONFIRMED' else 0}


def view(db,row):
    result=columns(row);result['snapshot']=json.loads(result.pop('snapshot_json'));result.update(amounts(db,row))
    result['account_name']=result['snapshot'].get('account_name') or db.get(models.Account,row.account_id).account_name
    result['assignments']=[columns(x) for x in db.query(models.FinancingDepositAssignment).filter_by(comp_code=row.comp_code,deposit_id=row.deposit_id).all()]
    result['movements']=[columns(x) for x in db.query(models.FinancingDepositMovement).filter_by(comp_code=row.comp_code,deposit_id=row.deposit_id).all()]
    return result


def applied_to_release(db,row):
    return sum(int(x.amount) for x in db.query(models.FinancingDepositMovement).filter_by(comp_code=row.comp_code,release_id=row.release_id,kind='APPLY',status='CONFIRMED').all())


def idempotent(db,model,company,key,payload):
    row=db.query(model).filter_by(comp_code=company,request_key=key).first()
    if row and hasattr(row,'snapshot_json') and json.loads(row.snapshot_json).get('input')!=payload:
        fail('동일 요청키의 보증금 내용이 다릅니다.')
    return row

@router.get('')
def listing(comp_code:str,db:Session=Depends(get_db)):
    return [view(db,x) for x in db.query(models.FinancingDeposit).filter_by(comp_code=comp_code).order_by(models.FinancingDeposit.deposit_id.desc()).all()]

@router.get('/{deposit_id}/history')
def history(comp_code:str,deposit_id:int,db:Session=Depends(get_db)):
    from audit_service import AuditEvent
    locked(db,models.FinancingDeposit,comp_code,'deposit_id',deposit_id)
    assignment_ids=[x.assignment_id for x in db.query(models.FinancingDepositAssignment).filter_by(comp_code=comp_code,deposit_id=deposit_id).all()]
    movement_ids=[x.movement_id for x in db.query(models.FinancingDepositMovement).filter_by(comp_code=comp_code,deposit_id=deposit_id).all()]
    identities={'FINANCING_DEPOSIT':{str(deposit_id)},'FINANCING_DEPOSIT_ASSIGNMENT':{str(x) for x in assignment_ids},'FINANCING_DEPOSIT_MOVEMENT':{str(x) for x in movement_ids}}
    return [columns(x) for x in db.query(AuditEvent).filter(AuditEvent.comp_code==comp_code,AuditEvent.entity_type.in_(identities)).order_by(AuditEvent.audit_event_id).all() if x.entity_id in identities[x.entity_type]]

@router.get('/{deposit_id}')
def get(comp_code:str,deposit_id:int,db:Session=Depends(get_db)):
    return view(db,locked(db,models.FinancingDeposit,comp_code,'deposit_id',deposit_id))

@router.post('',status_code=201)
def receive(comp_code:str,data:Receive,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        company=locked(db,models.Company,comp_code,'comp_code',comp_code)
        old=idempotent(db,models.FinancingDeposit,comp_code,data.request_key,data.model_dump(mode='json'))
        if old:return view(db,old)
        contracts._account(db,comp_code,data.account_id)
        ensure_period_open(db,comp_code,data.received_on)
        tx=models.AccountTransaction(comp_code=comp_code,account_id=data.account_id,transaction_date=data.received_on,
            transaction_no='DP-TEMP-'+uuid4().hex[:12],transaction_type='DEPOSIT_RECEIPT',original_amount=data.amount,memo='보증금 수취 (일반 FIFO 제외)')
        # Use the generated ledger ID for the final stable, unique number.
        db.add(tx);db.flush();tx.transaction_no=f'DP-{tx.account_transaction_id}'
        row=models.FinancingDeposit(comp_code=comp_code,account_id=data.account_id,received_on=data.received_on,
            amount=data.amount,request_key=data.request_key,bank_reference=data.bank_reference.strip(),transaction_id=tx.account_transaction_id,
            status='CONFIRMED',created_by=request.state.user_id,snapshot_json=dumps({'input':data.model_dump(mode='json'),'account_name':db.get(models.Account,data.account_id).account_name}))
        db.add(row);db.flush();claim_bank(db,comp_code,data.bank_reference,'DEPOSIT',row.deposit_id)
        audit(db,request,row,'RECEIVE');return view(db,row)

@router.post('/{deposit_id}/assign',status_code=201)
def assign(comp_code:str,deposit_id:int,data:Assign,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        contract=active_contract(db,comp_code,data.contract_id)
        row=locked(db,models.FinancingDeposit,comp_code,'deposit_id',deposit_id)
        old=db.query(models.FinancingDepositAssignment).filter_by(comp_code=comp_code,request_key=data.request_key).first()
        if old:
            if (old.deposit_id,old.contract_id,old.assigned_on,int(old.amount))!=(deposit_id,data.contract_id,data.assigned_on,data.amount):fail('동일 배정 요청키에 다른 내용을 사용할 수 없습니다.')
            return columns(old)
        if row.status!='CONFIRMED' or data.assigned_on<row.received_on:fail('실수취 보증금 및 배정일을 확인하십시오.')
        eligible={contract.contractor_account_id}|{p.account_id for p in contract.participants if p.role=='AUTHORIZED_SHIPPER' and p.status=='ACTIVE' and p.agreement_status=='CONFIRMED' and p.agreement_date and p.agreement_date<=data.assigned_on and (not p.effective_date or p.effective_date<=data.assigned_on)}
        if row.account_id not in eligible:fail('계약 책임/출고업체 보증금만 배정하십시오. 제3자 담보는 별도 약정이 필요합니다.')
        ensure_period_open(db,comp_code,data.assigned_on)
        if data.amount>amounts(db,row)['unassigned_amount']:fail('미배정 보증금 잔액을 초과합니다.')
        assignment=models.FinancingDepositAssignment(comp_code=comp_code,deposit_id=deposit_id,contract_id=data.contract_id,
            assigned_on=data.assigned_on,amount=data.amount,request_key=data.request_key,status='ACTIVE',created_by=request.state.user_id)
        db.add(assignment);db.flush();audit(db,request,assignment,'ASSIGN');return columns(assignment)

@router.post('/{deposit_id}/assignments/{assignment_id}/cancel')
def unassign(comp_code:str,deposit_id:int,assignment_id:int,data:Reason,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        identity=db.query(models.FinancingDepositAssignment).filter_by(comp_code=comp_code,assignment_id=assignment_id,deposit_id=deposit_id).first()
        if not identity:fail('보증금 배정이 없습니다.',404)
        active_contract(db,comp_code,identity.contract_id)
        locked(db,models.FinancingDeposit,comp_code,'deposit_id',deposit_id)
        assignment=locked(db,models.FinancingDepositAssignment,comp_code,'assignment_id',assignment_id)
        if assignment.status=='CANCELLED':return columns(assignment)
        if not data.reason.strip():fail('배정해제 사유가 필요합니다.',400)
        ensure_period_open(db,comp_code,assignment.assigned_on)
        before=columns(assignment);assignment.status='CANCELLED';audit(db,request,assignment,'UNASSIGN',before,data.reason)
        return columns(assignment)

@router.post('/{deposit_id}/apply',status_code=201)
def apply(comp_code:str,deposit_id:int,data:Apply,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        from financing_release_routes import locked_release
        release=locked_release(db,comp_code,data.release_id)
        active_contract(db,comp_code,release.contract_id)
        row=locked(db,models.FinancingDeposit,comp_code,'deposit_id',deposit_id)
        assignment=locked(db,models.FinancingDepositAssignment,comp_code,'assignment_id',data.assignment_id)
        old=idempotent(db,models.FinancingDepositMovement,comp_code,data.request_key,data.model_dump(mode='json'))
        if old:
            if old.deposit_id!=deposit_id:fail('동일 요청키에 다른 보증금을 사용할 수 없습니다.')
            return columns(old)
        if release.status!='CONFIRMED':fail('입금확인 전 확정 요청에만 보증금을 충당하십시오.')
        if assignment.deposit_id!=deposit_id or assignment.contract_id!=release.contract_id or assignment.status!='ACTIVE' or row.status!='CONFIRMED':fail('현재 계약의 유효한 보증금 배정이 필요합니다.')
        if row.account_id!=release.shipper_account_id:fail('보증금 소유업체와 실제 채무자가 다릅니다. 제3자 상계는 별도 승인 경로가 필요합니다.')
        if data.movement_date!=release.release_date or data.movement_date<assignment.assigned_on:fail('충당일은 배정일 이후 출고정산일과 일치해야 합니다.')
        if not data.reason.strip():fail('보증금 충당 근거가 필요합니다.',400)
        ensure_period_open(db,comp_code,data.movement_date)
        used=sum(int(x.amount) for x in db.query(models.FinancingDepositMovement).filter_by(comp_code=comp_code,assignment_id=assignment.assignment_id,status='CONFIRMED',kind='APPLY').all())
        if data.amount>int(assignment.amount)-used or data.amount>int(release.total_amount)-applied_to_release(db,release):fail('배정 잔액 또는 출고정산 요청액을 초과합니다.')
        movement=models.FinancingDepositMovement(comp_code=comp_code,deposit_id=deposit_id,assignment_id=assignment.assignment_id,
            release_id=release.release_id,movement_date=data.movement_date,amount=data.amount,kind='APPLY',status='CONFIRMED',
            request_key=data.request_key,snapshot_json=dumps({'input':data.model_dump(mode='json'),'contract_id':release.contract_id,'shipper_account_id':release.shipper_account_id}),created_by=request.state.user_id)
        db.add(movement);db.flush();audit(db,request,movement,'APPLY_RESERVE',reason=data.reason);return columns(movement)


def materialize_applications(db,release,request):
    # Lock contract -> deposits -> source transactions under the release's atomic transaction.
    movements=db.query(models.FinancingDepositMovement).filter_by(comp_code=release.comp_code,release_id=release.release_id,kind='APPLY',status='CONFIRMED').order_by(models.FinancingDepositMovement.deposit_id,models.FinancingDepositMovement.movement_id).all()
    sale=db.get(models.Sale,release.sale_id)
    source=db.query(models.AccountTransaction).filter_by(comp_code=release.comp_code,transaction_no=sale.sale_no,transaction_type='SALES_RECEIVABLE').one()
    for movement in movements:
        locked(db,models.FinancingDeposit,release.comp_code,'deposit_id',movement.deposit_id)
        if movement.transaction_id:fail('보증금 충당이 이미 채권에 연결되어 있습니다.')
        if source.account_id!=release.shipper_account_id or source_allocated(db,source.account_transaction_id)+movement.amount>source.original_amount:fail('충당할 원채권 잔액을 초과합니다.')
        tx=models.AccountTransaction(comp_code=release.comp_code,account_id=release.shipper_account_id,transaction_date=release.release_date,
            transaction_no=f'DPA-{movement.movement_id}',transaction_type='DEPOSIT_APPLIED',original_amount=movement.amount,memo=f'보증금 충당 / 출고정산 {release.release_id}')
        db.add(tx);db.flush();movement.transaction_id=tx.account_transaction_id
        db.add(models.AccountTransactionAllocation(source_transaction_id=source.account_transaction_id,
            settlement_transaction_id=tx.account_transaction_id,allocated_amount=movement.amount));db.flush()
        audit(db,request,movement,'APPLY_POST')

@router.post('/{deposit_id}/return',status_code=201)
def give_back(comp_code:str,deposit_id:int,data:Return,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        row=locked(db,models.FinancingDeposit,comp_code,'deposit_id',deposit_id)
        old=idempotent(db,models.FinancingDepositMovement,comp_code,data.request_key,data.model_dump(mode='json'))
        if old:
            if old.deposit_id!=deposit_id:fail('동일 요청키에 다른 보증금을 사용할 수 없습니다.')
            return columns(old)
        ensure_period_open(db,comp_code,data.movement_date)
        if row.status!='CONFIRMED' or data.movement_date<row.received_on or data.amount>amounts(db,row)['unassigned_amount']:fail('담보해제된 미배정 보증금만 실제 반환할 수 있습니다.')
        if not data.reason.strip():fail('반환 근거가 필요합니다.',400)
        tx=models.AccountTransaction(comp_code=comp_code,account_id=row.account_id,transaction_date=data.movement_date,
            transaction_no='DPR-TEMP-'+uuid4().hex[:12],transaction_type='DEPOSIT_RETURN',original_amount=data.amount,memo='보증금 실제 반환 (미수/미지급 제외)')
        db.add(tx);db.flush();tx.transaction_no=f'DPR-{tx.account_transaction_id}'
        movement=models.FinancingDepositMovement(comp_code=comp_code,deposit_id=deposit_id,movement_date=data.movement_date,
            amount=data.amount,kind='RETURN',status='CONFIRMED',request_key=data.request_key,bank_reference=data.bank_reference.strip(),
            transaction_id=tx.account_transaction_id,snapshot_json=dumps({'input':data.model_dump(mode='json')}),created_by=request.state.user_id)
        db.add(movement);db.flush();claim_bank(db,comp_code,data.bank_reference,'DEPOSIT_RETURN',movement.movement_id)
        audit(db,request,movement,'RETURN',reason=data.reason);return columns(movement)

@router.post('/{deposit_id}/movements/{movement_id}/cancel')
def cancel_move(comp_code:str,deposit_id:int,movement_id:int,data:Reason,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        identity=db.query(models.FinancingDepositMovement).filter_by(comp_code=comp_code,movement_id=movement_id,deposit_id=deposit_id).first()
        if not identity:fail('보증금 이동이 없습니다.',404)
        if identity.release_id:
            from financing_release_routes import locked_release
            release=locked_release(db,comp_code,identity.release_id)
            active_contract(db,comp_code,release.contract_id)
            if release.status in {'PAID','SHIPPED'}:fail('입금확인/출고된 충당은 요청 취소 경로에서 복원하십시오.')
        locked(db,models.FinancingDeposit,comp_code,'deposit_id',deposit_id)
        row=locked(db,models.FinancingDepositMovement,comp_code,'movement_id',movement_id)
        if row.status=='CANCELLED':return columns(row)
        ensure_period_open(db,comp_code,row.movement_date)
        if not data.reason.strip():fail('취소 사유가 필요합니다.',400)
        if row.kind=='RETURN':fail('실제 은행반환은 단순 취소로 복원하지 않습니다. 재수취 은행근거로 새 보증금을 등록하십시오.')
        before=columns(row);row.status='CANCELLED';audit(db,request,row,'CANCEL',before,data.reason);return columns(row)


def cancel_release_applications(db,release,request,reason):
    movements=db.query(models.FinancingDepositMovement).filter_by(comp_code=release.comp_code,release_id=release.release_id,kind='APPLY',status='CONFIRMED').all()
    for movement in movements:
        locked(db,models.FinancingDeposit,release.comp_code,'deposit_id',movement.deposit_id)
        ensure_period_open(db,release.comp_code,movement.movement_date)
        before=columns(movement)
        if movement.transaction_id:
            db.query(models.AccountTransactionAllocation).filter_by(settlement_transaction_id=movement.transaction_id).delete(synchronize_session=False)
            tx=db.get(models.AccountTransaction,movement.transaction_id);movement.transaction_id=None;db.flush();db.delete(tx)
        movement.status='CANCELLED';audit(db,request,movement,'CANCEL_RELEASE',before,reason)

@router.post('/{deposit_id}/cancel')
def cancel_deposit(comp_code:str,deposit_id:int,data:Reason,request:Request,db:Session=Depends(get_db)):
    with atomic(db):
        row=locked(db,models.FinancingDeposit,comp_code,'deposit_id',deposit_id)
        if row.status=='CANCELLED':return view(db,row)
        if not data.reason.strip():fail('수취 정정 사유가 필요합니다.',400)
        ensure_period_open(db,comp_code,row.received_on)
        if db.query(models.FinancingDepositAssignment).filter_by(comp_code=comp_code,deposit_id=deposit_id,status='ACTIVE').first() or db.query(models.FinancingDepositMovement).filter_by(comp_code=comp_code,deposit_id=deposit_id,status='CONFIRMED').first():fail('배정/충당/반환이 있는 보증금 수취는 취소할 수 없습니다.')
        before=columns(row);row.status='CANCELLED'
        # Keep the original bank/deposit evidence; a cancelled root has no available balance.
        audit(db,request,row,'CANCEL',before,data.reason);return view(db,row)
