from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_CEILING
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from audit_service import record_audit_event
from database import get_db
from settlement_service import allocate_settlement_fifo, clear_settlement_allocations, settlement_allocated
from trade_common import allocate_document_no, ensure_period_open

router = APIRouter(prefix="/api/v1/companies/{comp_code}/payments", tags=["payments"])


class PaymentInput(BaseModel):
    payment_date: date
    account_id: int
    amount: Decimal
    memo: Optional[str] = Field(default=None, max_length=1000)
    audit_reason: Optional[str] = Field(default=None, max_length=1000)


def _won(value): return Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_CEILING)


def _company(db, comp_code):
    if not db.query(models.Company).filter_by(comp_code=comp_code).first():
        raise HTTPException(status_code=404, detail="업무회사가 없습니다.")


def _purchase_account(db, comp_code, account_id):
    row = db.query(models.CompanyAccount, models.Account).join(models.Account).filter(
        models.CompanyAccount.comp_code == comp_code, models.CompanyAccount.account_id == account_id,
        models.CompanyAccount.use_yn == True, models.CompanyAccount.trade_stop_yn == False,
        models.CompanyAccount.purchase_yn == True, models.Account.use_yn == True).first()
    if not row: raise HTTPException(status_code=400, detail="현재 회사에서 사용 중인 매입거래처만 선택할 수 있습니다.")
    return row


def _snapshot(db, row):
    db.flush(); allocated = settlement_allocated(db, row.account_transaction_id); account = db.get(models.Account, row.account_id)
    return {"account_transaction_id": row.account_transaction_id, "transaction_no": row.transaction_no,
        "payment_date": row.transaction_date, "account_id": row.account_id,
        "account_code": account.account_code if account else None, "account_name": account.account_name if account else None,
        "amount": int(row.original_amount), "allocated_amount": int(allocated),
        "unallocated_amount": int(Decimal(row.original_amount) - allocated), "memo": row.memo}


def _row(db, comp_code, payment_id):
    result = db.query(models.AccountTransaction).filter_by(account_transaction_id=payment_id, comp_code=comp_code, transaction_type="PAYMENT").first()
    if not result: raise HTTPException(status_code=404, detail="지급 원거래가 없습니다.")
    return result


def _validate_adjustment(data):
    amount = _won(data.amount)
    if amount == 0: raise HTTPException(status_code=422, detail="지급액은 0원이 될 수 없습니다.")
    if amount < 0 and not ((data.memo or "").strip() or (data.audit_reason or "").strip()):
        raise HTTPException(status_code=422, detail="음수 지급 조정은 적요 또는 조정사유를 입력하세요.")
    return amount


def _allocate(db, row):
    return allocate_settlement_fifo(db, row, source_types=("OPENING_PAYABLE", "PURCHASE_PAYABLE"), settlement_type="PAYMENT")


@router.get("")
def get_payments(comp_code: str, db: Session = Depends(get_db)):
    _company(db, comp_code)
    rows = db.query(models.AccountTransaction).filter_by(comp_code=comp_code, transaction_type="PAYMENT").order_by(models.AccountTransaction.transaction_date.desc(), models.AccountTransaction.account_transaction_id.desc()).all()
    return [_snapshot(db, row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_payment(comp_code: str, data: PaymentInput, request: Request, db: Session = Depends(get_db)):
    _company(db, comp_code); _purchase_account(db, comp_code, data.account_id); ensure_period_open(db, comp_code, data.payment_date)
    amount = _validate_adjustment(data)
    row = models.AccountTransaction(comp_code=comp_code, transaction_no=allocate_document_no(db, comp_code, "PAYMENT", data.payment_date), transaction_date=data.payment_date, account_id=data.account_id, transaction_type="PAYMENT", original_amount=amount, memo=data.memo.strip() if data.memo else None)
    try:
        db.add(row); db.flush(); _allocate(db, row); after = _snapshot(db, row)
        record_audit_event(db, comp_code=comp_code, user_id=request.state.user_id, menu_code="PAYMENT_MANAGEMENT", action="CREATE", entity_type="PAYMENT", entity_id=row.account_transaction_id, source=f"{request.method} {request.url.path}", after=after, reason=data.audit_reason)
        db.commit(); db.refresh(row); return _snapshot(db, row)
    except HTTPException: db.rollback(); raise
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="지급 저장 중 원장 연결 오류가 발생했습니다.") from exc
    except Exception: db.rollback(); raise


@router.put("/{payment_id}")
def update_payment(comp_code: str, payment_id: int, data: PaymentInput, request: Request, db: Session = Depends(get_db)):
    row = _row(db, comp_code, payment_id); ensure_period_open(db, comp_code, row.transaction_date); ensure_period_open(db, comp_code, data.payment_date); _purchase_account(db, comp_code, data.account_id); amount = _validate_adjustment(data); before = _snapshot(db, row)
    try:
        clear_settlement_allocations(db, row.account_transaction_id)
        if row.transaction_date != data.payment_date: row.transaction_no = allocate_document_no(db, comp_code, "PAYMENT", data.payment_date)
        row.transaction_date = data.payment_date; row.account_id = data.account_id; row.original_amount = amount; row.memo = data.memo.strip() if data.memo else None; db.flush(); _allocate(db, row); after = _snapshot(db, row)
        record_audit_event(db, comp_code=comp_code, user_id=request.state.user_id, menu_code="PAYMENT_MANAGEMENT", action="UPDATE", entity_type="PAYMENT", entity_id=row.account_transaction_id, source=f"{request.method} {request.url.path}", before=before, after=after, reason=data.audit_reason)
        db.commit(); db.refresh(row); return _snapshot(db, row)
    except HTTPException: db.rollback(); raise
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="지급 수정 중 원장 연결 오류가 발생했습니다.") from exc
    except Exception: db.rollback(); raise


@router.delete("/{payment_id}")
def delete_payment(comp_code: str, payment_id: int, request: Request, reason: Optional[str] = None, db: Session = Depends(get_db)):
    row = _row(db, comp_code, payment_id); ensure_period_open(db, comp_code, row.transaction_date); before = _snapshot(db, row)
    try:
        clear_settlement_allocations(db, row.account_transaction_id)
        record_audit_event(db, comp_code=comp_code, user_id=request.state.user_id, menu_code="PAYMENT_MANAGEMENT", action="DELETE", entity_type="PAYMENT", entity_id=row.account_transaction_id, source=f"{request.method} {request.url.path}", before=before, reason=reason)
        db.delete(row); db.commit(); return {"message": "지급 원거래와 배분내역이 삭제되었습니다."}
    except HTTPException: db.rollback(); raise
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="지급 삭제 중 원장 연결 오류가 발생했습니다.") from exc
    except Exception: db.rollback(); raise
