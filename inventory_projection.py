"""Transaction-derived inventory projections; no inventory balances are stored."""

from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_CEILING

import models


ZERO = Decimal("0.00")


def _amount(weight, unit_cost):
    return int((Decimal(weight or 0) * Decimal(unit_cost or 0)).quantize(
        Decimal("1"), rounding=ROUND_CEILING
    ))


def project_inventory(db, comp_code, start_date: date, end_date: date,
                      warehouse_id=None, product_search="", include_zero=False,
                      group_by="LOT", storage_type=None):
    """Return LOT rows or aggregates using the same transaction-derived rows."""
    query = (db.query(models.Lot, models.Product, models.Warehouse)
             .join(models.Product, models.Product.product_id == models.Lot.product_id)
             .join(models.Warehouse, models.Warehouse.warehouse_id == models.Lot.warehouse_id)
             .filter(models.Lot.comp_code == comp_code))
    if warehouse_id is not None:
        query = query.filter(models.Lot.warehouse_id == warehouse_id)
    if storage_type:
        query = query.filter(models.Warehouse.storage_type == storage_type)
    keyword = (product_search or "").strip()
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter((models.Product.product_name.like(pattern)) |
                             (models.Product.product_code.like(pattern)) |
                             (models.Lot.lot_code.like(pattern)) |
                             (models.Lot.bl_no.like(pattern)) |
                             (models.Lot.container_no.like(pattern)) |
                             (models.Lot.history_no.like(pattern)))

    lots = query.order_by(models.Warehouse.warehouse_name,
                          models.Product.product_name,
                          models.Lot.lot_code).all()
    if not lots:
        return {"rows": [], "summary": _summary([]), "group_by": group_by}

    lot_ids = [lot.lot_id for lot, _, _ in lots]
    inbound_rows = (db.query(models.InboundItem, models.Inbound)
                    .join(models.Inbound, models.Inbound.inbound_id == models.InboundItem.inbound_id)
                    .filter(models.Inbound.comp_code == comp_code,
                            models.InboundItem.lot_id.in_(lot_ids),
                            models.Inbound.inbound_date <= end_date).all())
    outbound_rows = (db.query(models.OutboundItem, models.Outbound)
                     .join(models.Outbound, models.Outbound.outbound_id == models.OutboundItem.outbound_id)
                     .filter(models.Outbound.comp_code == comp_code,
                             models.OutboundItem.lot_id.in_(lot_ids),
                             models.Outbound.outbound_date <= end_date).all())
    in_totals = defaultdict(lambda: [0, ZERO, 0, ZERO, 0, ZERO])
    out_totals = defaultdict(lambda: [0, ZERO, 0, ZERO, 0, ZERO])
    for item, header in inbound_rows:
        values = in_totals[item.lot_id]
        values[4] += int(item.box_qty or 0); values[5] += Decimal(item.weight or 0)
        if header.inbound_date < start_date:
            values[0] += int(item.box_qty or 0); values[1] += Decimal(item.weight or 0)
        else:
            values[2] += int(item.box_qty or 0); values[3] += Decimal(item.weight or 0)
    for item, header in outbound_rows:
        values = out_totals[item.lot_id]
        values[4] += int(item.box_qty or 0); values[5] += Decimal(item.weight or 0)
        if header.outbound_date < start_date:
            values[0] += int(item.box_qty or 0); values[1] += Decimal(item.weight or 0)
        else:
            values[2] += int(item.box_qty or 0); values[3] += Decimal(item.weight or 0)

    inbound_item_ids = [item.inbound_item_id for item, _ in inbound_rows]
    supplier_by_inbound = {}
    if inbound_item_ids:
        purchases = (db.query(models.PurchaseItem.inbound_item_id, models.Account.account_name)
                     .join(models.Purchase, models.Purchase.purchase_id == models.PurchaseItem.purchase_id)
                     .join(models.Account, models.Account.account_id == models.Purchase.account_id)
                     .filter(models.Purchase.comp_code == comp_code,
                             models.PurchaseItem.inbound_item_id.in_(inbound_item_ids)).all())
        supplier_by_inbound = {inbound_id: name for inbound_id, name in purchases}
    supplier_by_lot = {}
    for item, header in inbound_rows:
        if item.lot_id not in supplier_by_lot and supplier_by_inbound.get(item.inbound_item_id):
            supplier_by_lot[item.lot_id] = supplier_by_inbound[item.inbound_item_id]

    rows = []
    for lot, product, warehouse in lots:
        ins, outs = in_totals[lot.lot_id], out_totals[lot.lot_id]
        beginning_box, beginning_kg = ins[0] - outs[0], ins[1] - outs[1]
        in_box, in_kg = ins[2], ins[3]
        out_box, out_kg = outs[2], outs[3]
        stock_box, stock_kg = ins[4] - outs[4], ins[5] - outs[5]
        if not include_zero and stock_box == 0 and stock_kg == 0:
            continue
        cost = Decimal(lot.individual_cost or 0)
        rows.append({
            "comp_code": comp_code, "lot_id": lot.lot_id, "lot_code": lot.lot_code,
            "source_type": lot.source_type, "status": lot.status, "use_yn": bool(lot.use_yn),
            "product_id": product.product_id,
            "product_code": product.product_code, "product_name": product.product_name,
            "category": product.category, "warehouse_id": warehouse.warehouse_id,
            "warehouse_code": warehouse.warehouse_code, "warehouse_name": warehouse.warehouse_name,
            "storage_type": warehouse.storage_type, "production_date": lot.production_date,
            "expiry_date": lot.expiry_date, "beginning_box_qty": beginning_box,
            "beginning_weight": beginning_kg, "inbound_box_qty": in_box,
            "inbound_weight": in_kg, "outbound_box_qty": out_box,
            "outbound_weight": out_kg, "current_box_qty": stock_box,
            "current_weight": stock_kg,
            "average_weight": (stock_kg / Decimal(stock_box)).quantize(Decimal("0.01"))
                              if stock_box else None,
            "individual_cost": int(cost.quantize(Decimal("1"), rounding=ROUND_CEILING)),
            "inventory_amount": _amount(stock_kg, cost),
            "bl_no": lot.bl_no, "container_no": lot.container_no,
            "history_no": lot.history_no, "memo": lot.memo,
            "supplier_name": supplier_by_lot.get(lot.lot_id),
        })

    group_by = (group_by or "LOT").upper()
    if group_by not in {"LOT", "WAREHOUSE", "PRODUCT"}:
        raise ValueError("group_by must be LOT, WAREHOUSE, or PRODUCT")
    if group_by == "LOT":
        result = rows
    else:
        keys = (("warehouse_id", "warehouse_code", "warehouse_name") if group_by == "WAREHOUSE"
                else ("product_id", "product_code", "product_name"))
        grouped = {}
        for row in rows:
            key = tuple(row[k] for k in keys)
            aggregate = grouped.setdefault(key, {k: row[k] for k in keys})
            aggregate.setdefault("source_lot_count", 0); aggregate["source_lot_count"] += 1
            for field in ("beginning_box_qty", "inbound_box_qty", "outbound_box_qty", "current_box_qty", "inventory_amount"):
                aggregate[field] = aggregate.get(field, 0) + row[field]
            for field in ("beginning_weight", "inbound_weight", "outbound_weight", "current_weight"):
                aggregate[field] = aggregate.get(field, ZERO) + row[field]
        result = list(grouped.values())
        for row in result:
            row["average_weight"] = (row["current_weight"] / Decimal(row["current_box_qty"])).quantize(Decimal("0.01")) if row["current_box_qty"] else None
            row["individual_cost"] = None
        result.sort(key=lambda r: tuple(str(r[k] or "") for k in keys))
    return {"rows": result, "summary": _summary(rows), "group_by": group_by}


def _summary(rows):
    def total(key):
        return sum((Decimal(row.get(key) or 0) for row in rows), Decimal(0))
    return {
        "beginning_box_qty": int(total("beginning_box_qty")),
        "beginning_weight": total("beginning_weight"),
        "inbound_box_qty": int(total("inbound_box_qty")),
        "inbound_weight": total("inbound_weight"),
        "outbound_box_qty": int(total("outbound_box_qty")),
        "outbound_weight": total("outbound_weight"),
        "current_box_qty": int(total("current_box_qty")),
        "current_weight": total("current_weight"),
        "inventory_amount": int(total("inventory_amount")),
    }


def lot_transactions(db, comp_code, lot_id, end_date=None):
    """Movement detail with stable references back to purchase/sale or inbound/outbound."""
    lot = db.query(models.Lot).filter(models.Lot.comp_code == comp_code,
                                      models.Lot.lot_id == lot_id).first()
    if lot is None:
        return None
    inbound = (db.query(models.InboundItem, models.Inbound)
               .join(models.Inbound, models.Inbound.inbound_id == models.InboundItem.inbound_id)
               .filter(models.Inbound.comp_code == comp_code,
                       models.InboundItem.lot_id == lot_id).all())
    outbound = (db.query(models.OutboundItem, models.Outbound)
                .join(models.Outbound, models.Outbound.outbound_id == models.OutboundItem.outbound_id)
                .filter(models.Outbound.comp_code == comp_code,
                        models.OutboundItem.lot_id == lot_id).all())
    purchase_links = {}
    inbound_ids = [item.inbound_item_id for item, _ in inbound]
    if inbound_ids:
        for purchase_id, purchase_no, inbound_item_id in db.query(
                models.Purchase.purchase_id, models.Purchase.purchase_no,
                models.PurchaseItem.inbound_item_id).join(
                models.PurchaseItem, models.PurchaseItem.purchase_id == models.Purchase.purchase_id
        ).filter(models.Purchase.comp_code == comp_code,
                 models.PurchaseItem.inbound_item_id.in_(inbound_ids)).all():
            purchase_links[inbound_item_id] = (purchase_id, purchase_no)
    sale_links = {}
    sale_item_ids = [item.sale_item_id for item, _ in outbound]
    if sale_item_ids:
        for sale_id, sale_no, sale_item_id in db.query(
                models.Sale.sale_id, models.Sale.sale_no, models.SaleItem.sale_item_id
        ).join(models.SaleItem, models.SaleItem.sale_id == models.Sale.sale_id).filter(
                models.Sale.comp_code == comp_code,
                models.SaleItem.sale_item_id.in_(sale_item_ids)).all():
            sale_links[sale_item_id] = (sale_id, sale_no)
    movements = []
    for item, header in inbound:
        purchase = purchase_links.get(item.inbound_item_id)
        source_type, source_id, source_no = (("PURCHASE", purchase[0], purchase[1]) if purchase else
                                              ("OPENING_INVENTORY" if header.transaction_type == "OPENING_INVENTORY" else "INBOUND",
                                               header.inbound_id, header.inbound_no))
        movements.append({"date": header.inbound_date, "direction": "INBOUND",
                          "transaction_type": header.transaction_type,
                          "transaction_no": header.inbound_no, "source_type": source_type,
                          "source_id": source_id, "source_no": source_no,
                          "inbound_item_id": item.inbound_item_id, "outbound_item_id": None,
                          "box_delta": int(item.box_qty), "weight_delta": Decimal(item.weight),
                          "warehouse_id": header.warehouse_id})
    for item, header in outbound:
        sale = sale_links.get(item.sale_item_id)
        source_type, source_id, source_no = (("SALE", sale[0], sale[1]) if sale else
                                             ("OUTBOUND", header.outbound_id, header.outbound_no))
        movements.append({"date": header.outbound_date, "direction": "OUTBOUND",
                          "transaction_type": header.transaction_type,
                          "transaction_no": header.outbound_no, "source_type": source_type,
                          "source_id": source_id, "source_no": source_no,
                          "inbound_item_id": None, "outbound_item_id": item.outbound_item_id,
                          "box_delta": -int(item.box_qty), "weight_delta": -Decimal(item.weight),
                          "warehouse_id": header.warehouse_id})
    if end_date:
        movements = [row for row in movements if row["date"] <= end_date]
    movements.sort(key=lambda r: (r["date"], r["direction"], r["transaction_no"],
                                 r["inbound_item_id"] or r["outbound_item_id"]))
    balance_box, balance_kg = 0, ZERO
    for row in movements:
        balance_box += row["box_delta"]; balance_kg += row["weight_delta"]
        row["balance_box_qty"] = balance_box; row["balance_weight"] = balance_kg
    return {"lot_id": lot_id, "lot_code": lot.lot_code,
            "product_id": lot.product_id, "product_name": lot.product.product_name,
            "rows": movements, "current_box_qty": balance_box,
            "current_weight": balance_kg}
