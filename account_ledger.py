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


def _item_detail(item, kind, header_memo):
    product_name = item.product.product_name if item.product else "상품명 없음"
    lot = getattr(item, "lot", None)
    history_no = getattr(item, "history_no", None) or (lot.history_no if lot else None)
    bl_no = getattr(item, "bl_no", None) or (lot.bl_no if lot else None)
    references = []
    if lot and lot.lot_code:
        references.append(f"LOT {lot.lot_code}")
    if history_no:
        references.append(f"이력 {history_no}")
    if bl_no:
        references.append(f"BL {bl_no}")
    memo_parts = [f"[{'매입' if kind == 'PURCHASE_PAYABLE' else '매출'}] {product_name}"]
    for value in (header_memo, item.memo):
        value = (value or "").strip()
        if value and value not in memo_parts:
            memo_parts.append(value)
    return {
        "line_no": item.line_no,
        "product_name": product_name,
        "memo": " · ".join(memo_parts),
        "box_qty": int(item.box_qty or 0),
        "weight": float(Decimal(item.weight or 0).quantize(Decimal("0.01"))),
        "unit_price": int(item.unit_price or 0),
        "line_amount": int(item.total_amount or 0),
        "lot_code": lot.lot_code if lot else None,
        "reference": " · ".join(references) or None,
    }


def _details_for_transaction(db, comp_code, transaction):
    """전표의 원래 품목행을 표시용으로 반환하고, 거래금액은 전표 단위로 유지한다."""
    if transaction.transaction_type == "PURCHASE_PAYABLE":
        header = db.query(models.Purchase).filter(
            models.Purchase.comp_code == comp_code,
            models.Purchase.purchase_no == transaction.transaction_no,
            models.Purchase.account_id == transaction.account_id,
        ).first()
        items = header.items if header else []
        source_type, source_id = "PURCHASE", header.purchase_id if header else None
    elif transaction.transaction_type == "SALES_RECEIVABLE":
        header = db.query(models.Sale).filter(
            models.Sale.comp_code == comp_code,
            models.Sale.sale_no == transaction.transaction_no,
            models.Sale.account_id == transaction.account_id,
        ).first()
        items = header.items if header else []
        source_type, source_id = "SALE", header.sale_id if header else None
    else:
        label = _TYPE_LABELS.get(transaction.transaction_type, transaction.transaction_type)
        memo = f"[{label}]"
        if transaction.memo and transaction.memo.strip():
            memo += f" {transaction.memo.strip()}"
        source_type = {"RECEIPT": "RECEIPT", "PAYMENT": "PAYMENT"}.get(transaction.transaction_type, "OPENING_BALANCE")
        return [{"memo": memo, "box_qty": None, "weight": None, "unit_price": None,
                 "line_amount": None, "product_name": None, "line_no": None,
                 "lot_code": None, "reference": None,
                 "source_type": source_type, "source_id": transaction.account_transaction_id}]

    items = sorted(items, key=lambda item: (item.line_no, item.purchase_item_id if hasattr(item, "purchase_item_id") else item.sale_item_id))
    if not items:
        return [{"memo": f"[{_TYPE_LABELS[transaction.transaction_type]}]", "box_qty": 0,
                 "weight": 0.0, "unit_price": None, "line_amount": None,
                 "product_name": None, "line_no": None, "lot_code": None, "reference": None,
                 "source_type": source_type, "source_id": source_id}]
    return [{**_item_detail(item, transaction.transaction_type, header.memo if header else None),
             "source_type": source_type, "source_id": source_id} for item in items]


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
        details = _details_for_transaction(db, comp_code, transaction)
        first_detail = details[0]
        if kind in {"PURCHASE_PAYABLE", "SALES_RECEIVABLE"}:
            box_qty = sum((item["box_qty"] or 0) for item in details)
            weight = sum((Decimal(str(item["weight"] or 0)) for item in details), Decimal(0))
            prices = {item["unit_price"] for item in details if item["unit_price"] is not None}
            line_amount = sum((item["line_amount"] or 0) for item in details)
            lot_codes = sorted({item["lot_code"] for item in details if item["lot_code"]})
            references = sorted({item["reference"] for item in details if item["reference"]})
        else:
            box_qty, weight, prices, line_amount = first_detail["box_qty"], first_detail["weight"], set(), None
            lot_codes, references = [], []
        row = {
            "account_transaction_id": transaction.account_transaction_id,
            "transaction_date": transaction.transaction_date.isoformat(),
            "transaction_no": transaction.transaction_no,
            "transaction_type": kind,
            "type_label": _TYPE_LABELS.get(kind, kind),
            "memo": first_detail["memo"],
            "details": details,
            "source_type": first_detail["source_type"],
            "source_id": first_detail["source_id"],
            "box_qty": box_qty,
            "weight": float(Decimal(str(weight)).quantize(Decimal("0.01"))) if weight is not None else None,
            "unit_price": next(iter(prices)) if len(prices) == 1 else None,
            "line_amount": line_amount,
            "product_name": ", ".join(dict.fromkeys(item["product_name"] for item in details if item["product_name"])) or None,
            "lot_code": ", ".join(lot_codes) or None,
            "reference": " · ".join(references) or None,
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
