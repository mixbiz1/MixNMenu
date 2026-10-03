"""입금·지급 공통 FIFO/조정 배분 규칙.

배분 금액은 양수(정상 반제) 또는 음수(기존 반제의 역조정)로만 저장한다.
음수 원거래는 먼저 미배분 선입금·선지급을 줄이고, 부족한 경우에만 가장 최근
원거래 배분을 되돌린다. 그러므로 미수·미지급 원거래의 배분잔액은 음수가 되지 않는다.
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func

import models


_NET_SIGNS = {
    "OPENING_RECEIVABLE": 1,
    "SALES_RECEIVABLE": 1,
    "PAYMENT": 1,
    "RECEIPT": -1,
    "OPENING_PAYABLE": -1,
    "PURCHASE_PAYABLE": -1,
}


def transaction_net_delta(transaction):
    """미수 관점 순잔액(+)에 반영되는 거래별 금액."""
    return Decimal(transaction.original_amount or 0) * _NET_SIGNS.get(transaction.transaction_type, 0)


def account_net_balance(db, comp_code, account_id, transaction_date):
    """기준일까지 회사·거래처 원거래의 순잔액을 공통 규칙으로 계산한다."""
    rows = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == comp_code,
        models.AccountTransaction.account_id == account_id,
        models.AccountTransaction.transaction_date <= transaction_date,
    ).all()
    return sum((transaction_net_delta(row) for row in rows), Decimal(0))


def source_allocated(db, source_id):
    value = db.query(func.coalesce(func.sum(models.AccountTransactionAllocation.allocated_amount), 0)).filter(
        models.AccountTransactionAllocation.source_transaction_id == source_id
    ).scalar()
    return Decimal(value or 0)


def settlement_allocated(db, settlement_id):
    value = db.query(func.coalesce(func.sum(models.AccountTransactionAllocation.allocated_amount), 0)).filter(
        models.AccountTransactionAllocation.settlement_transaction_id == settlement_id
    ).scalar()
    return Decimal(value or 0)


def clear_settlement_allocations(db, settlement_id):
    db.query(models.AccountTransactionAllocation).filter(
        models.AccountTransactionAllocation.settlement_transaction_id == settlement_id
    ).delete(synchronize_session=False)
    db.flush()


def _net_advance_before(db, settlement, settlement_type):
    rows = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == settlement.comp_code,
        models.AccountTransaction.account_id == settlement.account_id,
        models.AccountTransaction.transaction_type == settlement_type,
        models.AccountTransaction.transaction_date <= settlement.transaction_date,
        models.AccountTransaction.account_transaction_id != settlement.account_transaction_id,
    ).all()
    return sum((Decimal(row.original_amount) - settlement_allocated(db, row.account_transaction_id) for row in rows), Decimal(0))


def allocate_settlement_fifo(db, settlement, *, source_types, settlement_type):
    """양수는 FIFO, 음수 조정은 선지급/선입금 우선 후 LIFO 역배분한다."""
    clear_settlement_allocations(db, settlement.account_transaction_id)
    amount = Decimal(settlement.original_amount)
    if amount == 0:
        raise HTTPException(status_code=422, detail="입금·지급 금액은 0원이 될 수 없습니다.")
    sources = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == settlement.comp_code,
        models.AccountTransaction.account_id == settlement.account_id,
        models.AccountTransaction.transaction_type.in_(tuple(source_types)),
        models.AccountTransaction.transaction_date <= settlement.transaction_date,
    ).order_by(models.AccountTransaction.transaction_date, models.AccountTransaction.account_transaction_id).all()
    if amount > 0:
        remaining = amount
        for source in sources:
            if remaining <= 0: break
            open_amount = Decimal(source.original_amount) - source_allocated(db, source.account_transaction_id)
            if open_amount <= 0: continue
            allocated = min(open_amount, remaining)
            db.add(models.AccountTransactionAllocation(source_transaction_id=source.account_transaction_id,
                settlement_transaction_id=settlement.account_transaction_id, allocated_amount=allocated))
            remaining -= allocated; db.flush()
        return amount - remaining

    # 음수: 이전의 미배분 선입금/선지급부터 상계한다. 남은 부분만 이미 반제된
    # 원거래를 최근 순서로 되돌린다. 총 기존 반제를 초과하는 조정은 금지한다.
    remaining = -amount
    advance = max(_net_advance_before(db, settlement, settlement_type), Decimal(0))
    remaining -= min(advance, remaining)
    for source in reversed(sources):
        if remaining <= 0: break
        reversible = source_allocated(db, source.account_transaction_id)
        if reversible <= 0: continue
        reversed_amount = min(reversible, remaining)
        db.add(models.AccountTransactionAllocation(source_transaction_id=source.account_transaction_id,
            settlement_transaction_id=settlement.account_transaction_id, allocated_amount=-reversed_amount))
        remaining -= reversed_amount; db.flush()
    if remaining > 0:
        raise HTTPException(status_code=409, detail="음수 조정액이 기존 입금·지급 및 배분잔액을 초과합니다.")
    return amount + remaining  # 음수 배분 합계(선입금 상계분은 0)
