"""Sale follow-up documents: immutable issuance snapshots, no inventory side effects."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
import models
from audit_service import record_audit_event

router = APIRouter(prefix="/api/v1/companies/{comp_code}/sales/{sale_id}/statements")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=lambda v: str(v) if isinstance(v, Decimal) else v.isoformat())


def _sale(db, company, sale_id):
    # Lock the same Sale row as the update/cancel handlers. Serializes issue/version allocation.
    row = (db.query(models.Sale).with_hint(models.Sale, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
           .with_for_update().filter_by(comp_code=company, sale_id=sale_id).first())
    if not row: raise HTTPException(404, "매출전표가 없습니다.")
    return row


def fingerprint(sale):
    fields = ("sale_no", "sale_date", "account_id", "memo", "updated_at", "total_box_qty", "total_weight",
              "total_supply_amount", "total_tax_amount", "total_discount_amount", "total_amount")
    data = {key: getattr(sale, key) for key in fields}
    data["items"] = [{c.name: getattr(item, c.name) for c in models.SaleItem.__table__.columns
                      if c.name not in {"sale_item_id", "sale_id"}} for item in sorted(sale.items, key=lambda x: x.line_no)]
    return hashlib.sha256(_json(data).encode("utf-8")).hexdigest()


def build_snapshot(db, sale):
    company = db.get(models.Company, sale.comp_code)
    def party(row, name):
        return {"name": getattr(row, name), **{key: getattr(row, key, None) for key in
                ("biz_no", "ceo_name", "address", "address_detail", "uptae", "upjong", "phone", "tel", "fax", "email", "tax_email")}}
    result = {"schema_version": 1, "master_origin": "CURRENT_MASTER_AT_ISSUANCE_NOT_HISTORICAL",
              "company": party(company, "comp_name"), "customer": party(sale.account, "account_name"),
              "customer_code": sale.account.account_code, "sale_id": sale.sale_id, "sale_no": sale.sale_no,
              "sale_date": sale.sale_date.isoformat(), "memo": sale.memo, "items": []}
    for key in ("total_box_qty", "total_weight", "total_supply_amount", "total_tax_amount", "total_discount_amount", "total_amount"):
        result[key] = str(getattr(sale, key))
    for item in sorted(sale.items, key=lambda x: x.line_no):
        values = {c.name: getattr(item, c.name) for c in models.SaleItem.__table__.columns if c.name not in {"sale_item_id", "sale_id"}}
        values.update(product_code=item.product.product_code, product_name=item.product.product_name,
                      specification=item.product.specification, lot_code=item.lot.lot_code,
                      bl_no=getattr(item.lot, "bl_no", None), warehouse_name=item.lot.warehouse.warehouse_name)
        result["items"].append(values)
    return json.loads(_json(result))


def _result(row, sale):
    status = "CANCELLED" if sale.document_status == "CANCELLED" else (
        "ISSUED" if row.sale_fingerprint == fingerprint(sale) else "SUPERSEDED")
    return {"statement_id": row.statement_id, "comp_code": row.comp_code, "sale_id": row.sale_id,
            "document_kind": row.document_kind, "version": row.version, "status": status,
            "issued_by": row.issued_by, "issued_at": row.issued_at, "snapshot": json.loads(row.snapshot_json)}


@router.get("/preview")
def preview_statement(comp_code: str, sale_id: int, db: Session = Depends(get_db)):
    sale = _sale(db, comp_code, sale_id)
    if sale.document_status != "CONFIRMED": raise HTTPException(409, "확정된 매출만 최초 발행할 수 있습니다.")
    return {"version": None, "statement_id": None, "status": "PREVIEW", "snapshot": build_snapshot(db, sale)}


@router.get("")
def list_statements(comp_code: str, sale_id: int, db: Session = Depends(get_db)):
    sale = _sale(db, comp_code, sale_id)
    rows = db.query(models.TradeStatement).filter_by(comp_code=comp_code, sale_id=sale_id).order_by(models.TradeStatement.version.desc()).all()
    return [_result(row, sale) for row in rows]


@router.get("/{statement_id}")
def get_statement(comp_code: str, sale_id: int, statement_id: int, db: Session = Depends(get_db)):
    sale = _sale(db, comp_code, sale_id)
    row = db.query(models.TradeStatement).filter_by(comp_code=comp_code, sale_id=sale_id, statement_id=statement_id).first()
    if not row: raise HTTPException(404, "거래명세표가 없습니다.")
    return _result(row, sale)


@router.post("")
def issue_statement(comp_code: str, sale_id: int, request: Request, db: Session = Depends(get_db)):
    sale = _sale(db, comp_code, sale_id)
    if sale.document_status != "CONFIRMED": raise HTTPException(409, "확정된 매출만 발행할 수 있습니다.")
    digest = fingerprint(sale)
    last = db.query(models.TradeStatement).filter_by(comp_code=comp_code, sale_id=sale_id).order_by(models.TradeStatement.version.desc()).first()
    if last and last.sale_fingerprint == digest: return _result(last, sale)
    snapshot = build_snapshot(db, sale)
    row = models.TradeStatement(comp_code=comp_code, sale_id=sale_id, document_kind="TRADE_STATEMENT",
        version=(last.version + 1 if last else 1), sale_fingerprint=digest, snapshot_json=_json(snapshot),
        issued_by=request.state.user_id, issued_at=datetime.now(timezone.utc))
    db.add(row); db.flush()
    record_audit_event(db, comp_code=comp_code, user_id=request.state.user_id, menu_code="SALES_GENERAL",
        action="ISSUE", entity_type="TRADE_STATEMENT", entity_id=row.statement_id,
        source=f"{request.method} {request.url.path}", after={"version": row.version, "snapshot": snapshot},
        related_entity_type="SALE", related_entity_id=sale_id)
    db.commit(); db.refresh(row)
    return _result(row, sale)
