from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_CEILING
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from audit_service import record_audit_event
from database import get_db
from trade_common import allocate_document_no, ensure_period_open


router = APIRouter(prefix="/api/v1/companies/{comp_code}/receipts", tags=["receipts"])


class ReceiptInput(BaseModel):
    receipt_date: date
    account_id: int
    amount: Decimal = Field(gt=0)
    memo: Optional[str] = Field(default=None, max_length=1000)
    audit_reason: Optional[str] = Field(default=None, max_length=1000)


def _ceil_won(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_CEILING)


def _company_or_404(db: Session, comp_code: str):
    row = db.query(models.Company).filter(models.Company.comp_code == comp_code).first()
    if not row:
        raise HTTPException(status_code=404, detail="업무회사가 없습니다.")
    return row


def _sales_account(db: Session, comp_code: str, account_id: int):
    row = (
        db.query(models.CompanyAccount, models.Account)
        .join(models.Account, models.Account.account_id == models.CompanyAccount.account_id)
        .filter(
            models.CompanyAccount.comp_code == comp_code,
            models.CompanyAccount.account_id == account_id,
            models.CompanyAccount.use_yn == True,
            models.CompanyAccount.trade_stop_yn == False,
            models.CompanyAccount.sales_yn == True,
            models.Account.use_yn == True,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=400, detail="현재 회사에서 사용 중인 매출거래처만 선택할 수 있습니다.")
    return row



def _source_allocated(db: Session, source_id: int) -> Decimal:
    value = db.query(func.coalesce(func.sum(models.AccountTransactionAllocation.allocated_amount), 0)).filter(
        models.AccountTransactionAllocation.source_transaction_id == source_id
    ).scalar()
    return Decimal(value or 0)


def _settlement_allocated(db: Session, settlement_id: int) -> Decimal:
    value = db.query(func.coalesce(func.sum(models.AccountTransactionAllocation.allocated_amount), 0)).filter(
        models.AccountTransactionAllocation.settlement_transaction_id == settlement_id
    ).scalar()
    return Decimal(value or 0)


def _clear_receipt_allocations(db: Session, receipt_id: int) -> None:
    db.query(models.AccountTransactionAllocation).filter(
        models.AccountTransactionAllocation.settlement_transaction_id == receipt_id
    ).delete(synchronize_session=False)
    db.flush()


def _allocate_receipt_fifo(db: Session, receipt) -> Decimal:
    """입금일 현재의 기존 미수 원거래에 오래된 순서대로 부분배분한다.

    입금액이 미수보다 크면 초과분은 미배분 선입금으로 남는다. 미래 매출에는
    소급 배분하지 않고 거래처 원장 잔액에서 우선 상계한다.
    """
    _clear_receipt_allocations(db, receipt.account_transaction_id)
    remaining = Decimal(receipt.original_amount)
    sources = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == receipt.comp_code,
        models.AccountTransaction.account_id == receipt.account_id,
        models.AccountTransaction.transaction_type.in_(("OPENING_RECEIVABLE", "SALES_RECEIVABLE")),
        models.AccountTransaction.transaction_date <= receipt.transaction_date,
    ).order_by(
        models.AccountTransaction.transaction_date,
        models.AccountTransaction.account_transaction_id,
    ).all()
    for source in sources:
        if remaining <= 0:
            break
        open_amount = Decimal(source.original_amount) - _source_allocated(db, source.account_transaction_id)
        if open_amount <= 0:
            continue
        amount = min(open_amount, remaining)
        db.add(models.AccountTransactionAllocation(
            source_transaction_id=source.account_transaction_id,
            settlement_transaction_id=receipt.account_transaction_id,
            allocated_amount=amount,
        ))
        remaining -= amount
        db.flush()
    return Decimal(receipt.original_amount) - remaining


def _receipt_snapshot(db: Session, receipt):
    db.flush()
    allocated = _settlement_allocated(db, receipt.account_transaction_id)
    account = db.get(models.Account, receipt.account_id)
    return {
        "account_transaction_id": receipt.account_transaction_id,
        "transaction_no": receipt.transaction_no,
        "receipt_date": receipt.transaction_date,
        "account_id": receipt.account_id,
        "account_code": account.account_code if account else None,
        "account_name": account.account_name if account else None,
        "amount": int(receipt.original_amount),
        "allocated_amount": int(allocated),
        "unallocated_amount": int(Decimal(receipt.original_amount) - allocated),
        "memo": receipt.memo,
    }


def _receipt_or_404(db: Session, comp_code: str, receipt_id: int):
    row = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.account_transaction_id == receipt_id,
        models.AccountTransaction.comp_code == comp_code,
        models.AccountTransaction.transaction_type == "RECEIPT",
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="입금 원거래가 없습니다.")
    return row


@router.get("")
def get_receipts(comp_code: str, db: Session = Depends(get_db)):
    _company_or_404(db, comp_code)
    rows = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == comp_code,
        models.AccountTransaction.transaction_type == "RECEIPT",
    ).order_by(
        models.AccountTransaction.transaction_date.desc(),
        models.AccountTransaction.account_transaction_id.desc(),
    ).all()
    return [_receipt_snapshot(db, row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_receipt(comp_code: str, data: ReceiptInput, request: Request, db: Session = Depends(get_db)):
    _company_or_404(db, comp_code)
    _sales_account(db, comp_code, data.account_id)
    ensure_period_open(db, comp_code, data.receipt_date)
    amount = _ceil_won(data.amount)
    row = models.AccountTransaction(
        comp_code=comp_code,
        transaction_no=allocate_document_no(db, comp_code, "RECEIPT", data.receipt_date),
        transaction_date=data.receipt_date,
        account_id=data.account_id,
        transaction_type="RECEIPT",
        original_amount=amount,
        memo=data.memo.strip() if data.memo else None,
    )
    try:
        db.add(row)
        db.flush()
        _allocate_receipt_fifo(db, row)
        after = _receipt_snapshot(db, row)
        record_audit_event(
            db,
            comp_code=comp_code,
            user_id=request.state.user_id,
            menu_code="RECEIPT_MANAGEMENT",
            action="CREATE",
            entity_type="RECEIPT",
            entity_id=row.account_transaction_id,
            source=f"{request.method} {request.url.path}",
            after=after,
            reason=data.audit_reason,
        )
        db.commit()
        db.refresh(row)
        return _receipt_snapshot(db, row)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="입금 저장 중 중복 또는 원장 연결 오류가 발생했습니다.") from exc
    except Exception:
        db.rollback()
        raise


@router.put("/{receipt_id}")
def update_receipt(comp_code: str, receipt_id: int, data: ReceiptInput,
                   request: Request, db: Session = Depends(get_db)):
    row = _receipt_or_404(db, comp_code, receipt_id)
    ensure_period_open(db, comp_code, row.transaction_date)
    ensure_period_open(db, comp_code, data.receipt_date)
    _sales_account(db, comp_code, data.account_id)
    before = _receipt_snapshot(db, row)
    try:
        _clear_receipt_allocations(db, row.account_transaction_id)
        if row.transaction_date != data.receipt_date:
            row.transaction_no = allocate_document_no(db, comp_code, "RECEIPT", data.receipt_date)
        row.transaction_date = data.receipt_date
        row.account_id = data.account_id
        row.original_amount = _ceil_won(data.amount)
        row.memo = data.memo.strip() if data.memo else None
        db.flush()
        _allocate_receipt_fifo(db, row)
        after = _receipt_snapshot(db, row)
        record_audit_event(
            db,
            comp_code=comp_code,
            user_id=request.state.user_id,
            menu_code="RECEIPT_MANAGEMENT",
            action="UPDATE",
            entity_type="RECEIPT",
            entity_id=row.account_transaction_id,
            source=f"{request.method} {request.url.path}",
            before=before,
            after=after,
            reason=data.audit_reason,
        )
        db.commit()
        db.refresh(row)
        return _receipt_snapshot(db, row)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="입금 수정 중 원장 배분 오류가 발생했습니다.") from exc
    except Exception:
        db.rollback()
        raise


@router.delete("/{receipt_id}")
def delete_receipt(comp_code: str, receipt_id: int, request: Request,
                   reason: Optional[str] = None, db: Session = Depends(get_db)):
    row = _receipt_or_404(db, comp_code, receipt_id)
    ensure_period_open(db, comp_code, row.transaction_date)
    before = _receipt_snapshot(db, row)
    try:
        _clear_receipt_allocations(db, row.account_transaction_id)
        record_audit_event(
            db,
            comp_code=comp_code,
            user_id=request.state.user_id,
            menu_code="RECEIPT_MANAGEMENT",
            action="DELETE",
            entity_type="RECEIPT",
            entity_id=row.account_transaction_id,
            source=f"{request.method} {request.url.path}",
            before=before,
            reason=reason,
        )
        db.delete(row)
        db.commit()
        return {"message": "입금 원거래와 배분내역이 삭제되었습니다."}
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="입금 삭제 중 원장 연결 오류가 발생했습니다.") from exc
    except Exception:
        db.rollback()
        raise
