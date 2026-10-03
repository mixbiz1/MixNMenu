"""거래처 원시 거래를 합성해 반환하는 파생 거래처원장 서비스."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

import models
from settlement_service import transaction_net_delta

_TYPE_LABELS = {
    "OPENING_RECEIVABLE": "기초미수",
    "OPENING_PAYABLE": "기초미지급",
    "SALES_RECEIVABLE": "매출",
    "PURCHASE_PAYABLE": "매입",
    "RECEIPT": "입금",
    "PAYMENT": "지급",
}


def net_balance(transactions):
    return sum((transaction_net_delta(row) for row in transactions), Decimal(0))


def _detail_for_transaction(db, comp_code, transaction):
    """매입·매출 전표에 이미 저장된 수량/이력정보만 합산한다."""
    if transaction.transaction_type == "PURCHASE_PAYABLE":
        header = db.query(models.Purchase).filter(
            models.Purchase.comp_code == comp_code,
            models.Purchase.purchase_no == transaction.transaction_no,
            models.Purchase.account_id == transaction.account_id,
        ).first()
        items = header.items if header else []
        refs = [value for item in items for value in (item.history_no, item.bl_no) if value]
    elif transaction.transaction_type == "SALES_RECEIVABLE":
        header = db.query(models.Sale).filter(
            models.Sale.comp_code == comp_code,
            models.Sale.sale_no == transaction.transaction_no,
            models.Sale.account_id == transaction.account_id,
        ).first()
        items = header.items if header else []
        refs = [item.lot.history_no for item in items if item.lot and item.lot.history_no]
    else:
        return {"box_qty": None, "weight": None, "unit_price": None, "reference": None}

    prices = {int(item.unit_price) for item in items if item.unit_price is not None}
    weight = sum((Decimal(item.weight or 0) for item in items), Decimal(0))
    references = ", ".join(sorted(set(refs))) or None
    return {
        "box_qty": sum(int(item.box_qty or 0) for item in items),
        "weight": float(weight.quantize(Decimal("0.01"))),
        "unit_price": next(iter(prices)) if len(prices) == 1 else None,
        "reference": references,
    }


def _empty_total():
    return {
        "box_qty": 0,
        "weight": Decimal(0),
        "sales_amount": 0,
        "receipt_amount": 0,
        "purchase_amount": 0,
        "payment_amount": 0,
        "net_change": 0,
    }


def _add_total(total, row):
    if row["box_qty"] is not None:
        total["box_qty"] += row["box_qty"]
    if row["weight"] is not None:
        total["weight"] += Decimal(str(row["weight"]))
    total["sales_amount"] += row["sales_amount"]
    total["receipt_amount"] += row["receipt_amount"]
    total["purchase_amount"] += row["purchase_amount"]
    total["payment_amount"] += row["payment_amount"]
    total["net_change"] += row["net_change"]


def _serialize_total(total):
    return {
        **{key: value for key, value in total.items() if key != "weight"},
        "weight": float(total["weight"].quantize(Decimal("0.01"))),
    }


def build_account_ledger(db, comp_code: str, account_id: int, start_date: date, end_date: date):
    """전잔액부터 기간 말 잔액까지를 결정적 순서로 반환한다.

    원장은 AccountTransaction에서 매 요청 합성하며 별도 원장 테이블을 쓰지 않는다.
    같은 날짜는 account_transaction_id 오름차순으로 고정한다.
    """
    transactions = db.query(models.AccountTransaction).filter(
        models.AccountTransaction.comp_code == comp_code,
        models.AccountTransaction.account_id == account_id,
        models.AccountTransaction.transaction_date <= end_date,
    ).order_by(
        models.AccountTransaction.transaction_date,
        models.AccountTransaction.account_transaction_id,
    ).all()
    opening = sum((transaction_net_delta(row) for row in transactions if row.transaction_date < start_date), Decimal(0))
    period_rows = []
    daily = defaultdict(_empty_total)
    monthly = defaultdict(_empty_total)
    period_total = _empty_total()
    balance = opening

    for transaction in transactions:
        if transaction.transaction_date < start_date:
            continue
        amount = Decimal(transaction.original_amount or 0)
        kind = transaction.transaction_type
        net_change = transaction_net_delta(transaction)
        detail = _detail_for_transaction(db, comp_code, transaction)
        row = {
            "account_transaction_id": transaction.account_transaction_id,
            "transaction_date": transaction.transaction_date.isoformat(),
            "transaction_no": transaction.transaction_no,
            "transaction_type": kind,
            "type_label": _TYPE_LABELS.get(kind, kind),
            "memo": transaction.memo or "",
            **detail,
            "transaction_amount": int(amount),
            "sales_amount": int(amount) if kind == "SALES_RECEIVABLE" else 0,
            "receipt_amount": int(amount) if kind == "RECEIPT" else 0,
            "purchase_amount": int(amount) if kind == "PURCHASE_PAYABLE" else 0,
            "payment_amount": int(amount) if kind == "PAYMENT" else 0,
            "net_change": int(net_change),
        }
        balance += net_change
        row["balance"] = int(balance)
        period_rows.append(row)
        _add_total(daily[transaction.transaction_date.isoformat()], row)
        _add_total(monthly[transaction.transaction_date.strftime("%Y-%m")], row)
        _add_total(period_total, row)

    return {
        "comp_code": comp_code,
        "account_id": account_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "opening_balance": int(opening),
        "ending_balance": int(balance),
        "transactions": period_rows,
        "daily_totals": {key: _serialize_total(value) for key, value in sorted(daily.items())},
        "monthly_totals": {key: _serialize_total(value) for key, value in sorted(monthly.items())},
        "period_total": _serialize_total(period_total),
    }
