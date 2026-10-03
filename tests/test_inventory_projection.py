from datetime import date, datetime, timezone
from decimal import Decimal
import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

with patch("sqlalchemy.create_engine", return_value=create_engine("sqlite://")):
    import main
import models
from database import Base


@pytest.fixture
def inventory_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def setup(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.create_function("SYSUTCDATETIME", 0,
                             lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat(" "))

    for table in Base.metadata.tables.values():
        table.dialect_options["sqlite"]["autoincrement"] = True
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        db.add_all([
            models.Company(comp_code="00001", comp_name="테스트", biz_no="1"),
            models.Company(comp_code="00002", comp_name="타회사", biz_no="2"),
            models.User(user_id="tester", user_name="T", password_hash="x", is_admin=True),
            models.Account(account_id=1, account_code="A1", account_name="매입처"),
            models.Product(product_id=1, product_code="P1", product_name="상품", tax_type="2"),
            models.Warehouse(warehouse_id=1, warehouse_code="W1", warehouse_name="창고", storage_type="FROZEN"),
            models.Warehouse(warehouse_id=2, warehouse_code="W2", warehouse_name="다른 창고"),
            models.TaxCode(tax_code="EXEMPT", tax_name="면세", tax_kind="EXEMPT", tax_rate=0,
                           valid_from=date(2000, 1, 1)),
        ])
        db.commit()
        db.add_all([
            models.CompanyAccount(comp_code="00001", account_id=1, sales_yn=True, purchase_yn=True),
            models.CompanyWarehouse(comp_code="00001", warehouse_id=1),
            models.CompanyWarehouse(comp_code="00001", warehouse_id=2),
            models.CompanyWarehouse(comp_code="00002", warehouse_id=1),
        ])
        lot = models.Lot(comp_code="00001", lot_code="L1", source_type="DOMESTIC",
                         product_id=1, warehouse_id=1, individual_cost=1000, status="OPEN", use_yn=True,
                         bl_no="BL-1", history_no="H-1", production_date=date(2026, 9, 1),
                         expiry_date=date(2028, 8, 31))
        db.add(lot); db.flush()
        inbound = models.Inbound(comp_code="00001", inbound_no="I1", inbound_date=date(2026, 10, 2),
                                 warehouse_id=1, transaction_type="PURCHASE_INBOUND")
        db.add(inbound); db.flush()
        inbound_item = models.InboundItem(inbound_id=inbound.inbound_id, line_no=1, product_id=1,
                                          lot_id=lot.lot_id, box_qty=10, weight=Decimal("100.00"),
                                          individual_cost=1000, amount=100000)
        db.add(inbound_item)
        db.commit()
    yield factory
    engine.dispose()


def make_sale_outbound(db, lot_id=1, box=2, weight="20.00", sale_no="SA-1"):
    sale = models.Sale(comp_code="00001", sale_no=sale_no, sale_date=date(2026, 10, 2),
                       account_id=1, document_status="CONFIRMED", created_by="tester", updated_by="tester")
    db.add(sale); db.flush()
    sale_item = models.SaleItem(sale_id=sale.sale_id, line_no=1, product_id=1, lot_id=lot_id,
                                box_qty=box, weight=Decimal(weight), unit_price=2000, supply_amount=40000,
                                tax_code_snapshot="EXEMPT", tax_name_snapshot="면세", tax_rate_snapshot=0,
                                tax_amount=0, discount_amount=0, total_amount=40000)
    db.add(sale_item); db.flush()
    outbound = models.Outbound(comp_code="00001", outbound_no="OU-1", outbound_date=sale.sale_date,
                               warehouse_id=1, transaction_type="SALES_OUTBOUND")
    db.add(outbound); db.flush()
    db.add(models.OutboundItem(outbound_id=outbound.outbound_id, sale_item_id=sale_item.sale_item_id,
                               line_no=1, product_id=1, lot_id=lot_id, box_qty=box,
                               weight=Decimal(weight), amount=40000))
    db.flush()
    return sale


def test_period_projection_inclusive_dates_and_box_kg_equation(inventory_db):
    with inventory_db() as db:
        purchase = models.Purchase(comp_code="00001", purchase_no="PU-1", purchase_date=date(2026, 10, 2),
                                   account_id=1, document_status="CONFIRMED", created_by="tester", updated_by="tester")
        db.add(purchase); db.flush()
        inbound_item = db.query(models.InboundItem).one()
        db.add(models.PurchaseItem(purchase_id=purchase.purchase_id, line_no=1, product_id=1,
                                   warehouse_id=1, lot_id=1, inbound_item_id=inbound_item.inbound_item_id,
                                   box_qty=10, weight=100, unit_price=1000, supply_amount=100000,
                                   tax_code_snapshot="EXEMPT", tax_name_snapshot="면세", tax_rate_snapshot=0,
                                   tax_amount=0, discount_amount=0, total_amount=100000))
        make_sale_outbound(db)
        db.commit()
        result = main.get_inventory_projection("00001", date(2026, 10, 2), date(2026, 10, 2),
                                               None, "", True, "LOT", db)
        row = next(item for item in result["rows"] if item["lot_code"] == "L1")
        assert (row["beginning_box_qty"], Decimal(str(row["beginning_weight"]))) == (0, Decimal("0.00"))
        assert (row["inbound_box_qty"], Decimal(str(row["inbound_weight"]))) == (10, Decimal("100.00"))
        assert (row["outbound_box_qty"], Decimal(str(row["outbound_weight"]))) == (2, Decimal("20.00"))
        assert (row["current_box_qty"], Decimal(str(row["current_weight"]))) == (8, Decimal("80.00"))
        assert row["individual_cost"] == 1000 and row["inventory_amount"] == 80000
        assert row["supplier_name"] == "매입처"
        summary = result["summary"]
        assert summary["beginning_box_qty"] + summary["inbound_box_qty"] - summary["outbound_box_qty"] == summary["current_box_qty"]
        assert Decimal(str(summary["beginning_weight"])) + Decimal(str(summary["inbound_weight"])) - Decimal(str(summary["outbound_weight"])) == Decimal(str(summary["current_weight"]))
        next_day = main.get_inventory_projection("00001", date(2026, 10, 3), date(2026, 10, 3),
                                                 None, "", False, "LOT", db)
        next_row = next(item for item in next_day["rows"] if item["lot_code"] == "L1")
        assert (next_row["beginning_box_qty"], next_row["current_box_qty"]) == (8, 8)
        assert next_row["inbound_box_qty"] == next_row["outbound_box_qty"] == 0


def test_warehouse_and_product_groupings_reconcile_to_lot_projection(inventory_db):
    with inventory_db() as db:
        lot = models.Lot(comp_code="00001", lot_code="L2", source_type="DOMESTIC", product_id=1,
                         warehouse_id=1, individual_cost=1200, status="OPEN", use_yn=True)
        db.add(lot); db.flush()
        header = models.Inbound(comp_code="00001", inbound_no="I2", inbound_date=date(2026, 10, 2),
                                warehouse_id=1, transaction_type="PURCHASE_INBOUND")
        db.add(header); db.flush()
        db.add(models.InboundItem(inbound_id=header.inbound_id, line_no=1, product_id=1,
                                  lot_id=lot.lot_id, box_qty=5, weight=Decimal("25.00"),
                                  individual_cost=1200, amount=30000))
        db.flush()
        params = (date(2026, 10, 1), date(2026, 10, 3), None, "", False)
        detail = main.get_inventory_projection("00001", *params, "LOT", db)
        warehouse = main.get_inventory_projection("00001", *params, "WAREHOUSE", db)
        product = main.get_inventory_projection("00001", *params, "PRODUCT", db)
        assert warehouse["rows"][0]["source_lot_count"] == 2
        assert product["rows"][0]["source_lot_count"] == 2
        for key in ("beginning_box_qty", "inbound_box_qty", "outbound_box_qty", "current_box_qty",
                    "beginning_weight", "inbound_weight", "outbound_weight", "current_weight", "inventory_amount"):
            assert warehouse["summary"][key] == detail["summary"][key] == product["summary"][key]
            assert warehouse["rows"][0][key] == product["rows"][0][key]


def test_current_average_weight_uses_remaining_box_and_weight_independently(inventory_db):
    with inventory_db() as db:
        db.query(models.InboundItem).one().box_qty = 100
        db.query(models.InboundItem).one().weight = Decimal("2064.00")
        make_sale_outbound(db, box=1, weight="20.00")
        db.commit()
        result = main.get_inventory_projection("00001", date(2026, 10, 2), date(2026, 10, 2),
                                               None, "", False, "LOT", db)
        row = result["rows"][0]
        assert row["current_box_qty"] == 99
        assert Decimal(str(row["current_weight"])) == Decimal("2044.00")
        assert Decimal(str(row["average_weight"])) == Decimal("20.65")


def test_zero_lot_filter_and_company_separation(inventory_db):
    with inventory_db() as db:
        db.add(models.Lot(comp_code="00001", lot_code="ZERO", source_type="DOMESTIC", product_id=1,
                          warehouse_id=1, individual_cost=1000, status="CLOSED", use_yn=False))
        other_lot = models.Lot(comp_code="00002", lot_code="OTHER-LOT", source_type="DOMESTIC",
                               product_id=1, warehouse_id=1, individual_cost=999, status="OPEN", use_yn=True)
        db.add(other_lot); db.flush()
        header = models.Inbound(comp_code="00002", inbound_no="OTHER-IN", inbound_date=date(2026, 10, 2),
                                warehouse_id=1, transaction_type="OPENING_INVENTORY")
        db.add(header); db.flush()
        db.add(models.InboundItem(inbound_id=header.inbound_id, line_no=1, product_id=1,
                                  lot_id=other_lot.lot_id, box_qty=7, weight=70,
                                  individual_cost=999, amount=69930))
        db.commit()
        args = (date(2026, 10, 1), date(2026, 10, 3), None, "")
        default = main.get_inventory_projection("00001", *args, False, "LOT", db)
        all_lots = main.get_inventory_projection("00001", *args, True, "LOT", db)
        other = main.get_inventory_projection("00002", *args, False, "LOT", db)
        assert all(row["lot_code"] != "ZERO" for row in default["rows"])
        assert any(row["lot_code"] == "ZERO" for row in all_lots["rows"])
        assert all(row["lot_code"] != "OTHER-LOT" for row in all_lots["rows"])
        assert [row["lot_code"] for row in other["rows"]] == ["OTHER-LOT"]


def test_lot_history_has_source_ids_and_running_balances(inventory_db):
    with inventory_db() as db:
        sale = make_sale_outbound(db); db.commit()
        history = main.get_inventory_lot_transactions("00001", 1, date(2026, 10, 2), db)
        outbound = next(row for row in history["rows"] if row["direction"] == "OUTBOUND")
        assert (outbound["source_type"], outbound["source_id"], outbound["source_no"]) == ("SALE", sale.sale_id, sale.sale_no)
        assert (outbound["balance_box_qty"], Decimal(str(outbound["balance_weight"]))) == (8, Decimal("80.00"))
        with pytest.raises(HTTPException) as missing:
            main.get_inventory_lot_transactions("00001", 999, None, db)
        assert missing.value.status_code == 404


def test_opening_lot_cannot_be_changed_after_outbound(inventory_db):
    with inventory_db() as db:
        opening = models.Inbound(comp_code="00001", inbound_no="OI-1", inbound_date=date(2026, 10, 1),
                                 warehouse_id=1, transaction_type="OPENING_INVENTORY")
        db.add(opening); db.flush()
        lot = models.Lot(comp_code="00001", lot_code="OPEN-LOT", source_type="DOMESTIC", product_id=1,
                         warehouse_id=1, individual_cost=1000, status="OPEN", use_yn=True)
        db.add(lot); db.flush()
        item = models.InboundItem(inbound_id=opening.inbound_id, line_no=1, product_id=1, lot_id=lot.lot_id,
                                  box_qty=3, weight=30, individual_cost=1000, amount=30000)
        db.add(item); db.flush(); make_sale_outbound(db, lot_id=lot.lot_id, box=1, weight="10.00"); db.commit()
        with pytest.raises(HTTPException) as blocked:
            main._guard_opening_inventory_changes(db, opening)
        assert blocked.value.status_code == 409
        row = main.get_inventory_projection("00001", date(2026, 10, 1), date(2026, 10, 3),
                                            None, "", True, "LOT", db)["rows"]
        stock = next(value for value in row if value["lot_id"] == lot.lot_id)
        assert (stock["current_box_qty"], Decimal(str(stock["current_weight"]))) == (2, Decimal("20.00"))


def test_opening_inventory_create_update_delete_have_audit_history(inventory_db):
    scope = {"type": "http", "method": "POST", "path": "/api/v1/companies/00001/opening-inventories",
             "headers": [], "query_string": b"", "server": ("test", 80),
             "client": ("test", 1), "scheme": "http"}
    request = main.Request(scope); request.state.user_id = "tester"
    with inventory_db() as db:
        data = main.OpeningInventorySchema(
            base_date=date(2026, 10, 1), warehouse_id=1,
            items=[main.OpeningInventoryItemSchema(product_id=1, source_type="DOMESTIC",
                                                   box_qty=2, weight=Decimal("20.00"),
                                                   individual_cost=1000)],
        )
        created = main.create_opening_inventory("00001", data, request, db)
        inbound_id = created["inbound_id"]
        detail = created["items"][0]
        update_request = main.Request({**scope, "method": "PUT",
                                       "path": f"/api/v1/companies/00001/opening-inventories/{inbound_id}"})
        update_request.state.user_id = "tester"
        update = main.OpeningInventorySchema(
            base_date=date(2026, 10, 1), warehouse_id=1,
            items=[main.OpeningInventoryItemSchema(
                inbound_item_id=detail["inbound_item_id"], lot_id=detail["lot_id"],
                product_id=1, source_type="DOMESTIC", box_qty=2, weight=Decimal("21.00"),
                individual_cost=1000,
            )],
        )
        main.update_opening_inventory("00001", inbound_id, update, update_request, db)
        delete_request = main.Request({**scope, "method": "DELETE",
                                       "path": f"/api/v1/companies/00001/opening-inventories/{inbound_id}"})
        delete_request.state.user_id = "tester"
        main.delete_opening_inventory("00001", inbound_id, delete_request, db)
        history = main.get_opening_inventory_history("00001", inbound_id, db)
        assert [event["action"] for event in history] == ["CREATE", "UPDATE", "DELETE"]
        assert history[1]["before_json"] and history[1]["after_json"]
        assert json.loads(history[1]["after_json"])["items"][0]["weight"] == "21.00"
        assert history[2]["before_json"] and history[2]["after_json"] is None


def test_held_lot_cannot_be_sold_or_moved_between_warehouses(inventory_db):
    with inventory_db() as db:
        lot = db.get(models.Lot, 1); lot.status = "HOLD"; db.flush()
        request = main.SaleItemInput(line_no=1, product_id=1, lot_id=1, box_qty=1,
                                     weight=Decimal("10.00"), unit_price=2000)
        with pytest.raises(HTTPException) as blocked:
            main._prepare_sale_lines(db, "00001", date(2026, 10, 2), [request])
        assert blocked.value.status_code == 409
        data = main.LotSchema(lot_code="L1", source_type="DOMESTIC", product_id=1, warehouse_id=2,
                              bl_no="BL-1", history_no="H-1", individual_cost=1000, status="HOLD", use_yn=True)
        with pytest.raises(HTTPException) as move_blocked:
            main.update_lot("00001", 1, data, db)
        assert move_blocked.value.status_code == 409
        assert lot.warehouse_id == 1 and lot.status == "HOLD"


def test_inventory_rejects_reversed_period_and_unknown_group(inventory_db):
    with inventory_db() as db:
        with pytest.raises(HTTPException) as reversed_period:
            main.get_inventory_projection("00001", date(2026, 10, 3), date(2026, 10, 2),
                                          None, "", False, "LOT", db)
        assert reversed_period.value.status_code == 400
        with pytest.raises(HTTPException) as bad_group:
            main.get_inventory_projection("00001", date(2026, 10, 1), date(2026, 10, 3),
                                          None, "", False, "BL", db)
        assert bad_group.value.status_code == 400
        frozen = main.get_inventory_projection("00001", date(2026, 10, 1), date(2026, 10, 3),
                                               None, "", False, "LOT", db, "FROZEN")
        chilled = main.get_inventory_projection("00001", date(2026, 10, 1), date(2026, 10, 3),
                                                None, "", False, "LOT", db, "CHILLED")
        assert [row["lot_code"] for row in frozen["rows"]] == ["L1"]
        assert chilled["rows"] == []
