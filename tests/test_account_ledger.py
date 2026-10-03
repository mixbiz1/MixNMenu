from datetime import date, datetime, timezone
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
from permissions import issue_token, permission_for_request


@pytest.fixture
def db_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def setup(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.create_function("SYSUTCDATETIME", 0, lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat(" "))

    for table in Base.metadata.tables.values():
        table.dialect_options["sqlite"]["autoincrement"] = True
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        db.add_all([
            models.Company(comp_code="00001", comp_name="A", biz_no="1"),
            models.Company(comp_code="00002", comp_name="B", biz_no="2"),
            models.User(user_id="ledger-admin", user_name="T", password_hash="x", is_admin=True),
            models.Account(account_id=1, account_code="A1", account_name="거래처"),
        ])
        db.commit()
        db.add_all([
            models.CompanyAccount(comp_code="00001", account_id=1, sales_yn=True, purchase_yn=True),
            models.CompanyAccount(comp_code="00002", account_id=1, sales_yn=True, purchase_yn=True),
        ])
        # 전기 전잔액은 +60. 기간 거래는 양·음 전환을 모두 거쳐 기말 +25로 끝난다.
        txs = [
            ("OPENING_RECEIVABLE", "OR-1", "2026-09-30", 100),
            ("OPENING_PAYABLE", "OP-1", "2026-09-30", 40),
            ("SALES_RECEIVABLE", "SA-1", "2026-10-01", 80),
            ("PURCHASE_PAYABLE", "PU-1", "2026-10-01", 70),
            ("RECEIPT", "RC-1", "2026-10-02", 100),
            ("PAYMENT", "PY-1", "2026-10-02", 50),
            ("RECEIPT", "RC-2", "2026-10-03", -10),
            ("PAYMENT", "PY-2", "2026-10-03", -5),
        ]
        db.add_all(models.AccountTransaction(
            comp_code="00001", account_id=1, transaction_type=kind,
            transaction_no=no, transaction_date=date.fromisoformat(day), original_amount=amount,
            memo={"RC-1": "거래처 송금", "PY-1": "매입대금 지급"}.get(no),
        ) for kind, no, day, amount in txs)
        db.add(models.AccountTransaction(
            comp_code="00002", account_id=1, transaction_type="OPENING_RECEIVABLE",
            transaction_no="OR-B", transaction_date=date(2026, 9, 30), original_amount=999,
        ))
        db.commit()

    yield factory
    engine.dispose()


def get_ledger(factory, comp="00001", account_id=1, start="2026-10-01", end="2026-10-03"):
    with factory() as db:
        return main.get_account_ledger(comp, account_id, date.fromisoformat(start), date.fromisoformat(end), db)


def test_ledger_opening_period_rows_and_all_six_transaction_types(db_factory):
    data = get_ledger(db_factory)
    assert data["opening_balance"] == 60
    assert [row["type_label"] for row in data["transactions"]] == ["매출", "매입", "입금", "지급", "입금", "지급"]
    assert [row["balance"] for row in data["transactions"]] == [140, 70, -30, 20, 30, 25]
    assert data["ending_balance"] == 25
    assert data["period_total"]["sales_amount"] == 80
    assert data["period_total"]["purchase_amount"] == 70
    assert data["period_total"]["receipt_amount"] == 90
    assert data["period_total"]["payment_amount"] == 45
    receipt, payment = data["transactions"][2:4]
    assert receipt["memo"] == "[입금] 거래처 송금"
    assert payment["memo"] == "[지급] 매입대금 지급"
    assert receipt["source_type"] == "RECEIPT" and receipt["source_id"] == receipt["account_transaction_id"]
    assert payment["source_type"] == "PAYMENT" and payment["source_id"] == payment["account_transaction_id"]


def test_ledger_date_range_determinism_daily_monthly_totals_and_settlement_match(db_factory):
    first = get_ledger(db_factory, start="2026-10-01", end="2026-10-03")
    second = get_ledger(db_factory, start="2026-10-01", end="2026-10-03")
    assert [r["account_transaction_id"] for r in first["transactions"]] == [r["account_transaction_id"] for r in second["transactions"]]
    assert [r["balance"] for r in first["transactions"]] == [r["balance"] for r in second["transactions"]]
    assert first["daily_totals"]["2026-10-02"]["net_change"] == -50
    assert first["monthly_totals"]["2026-10"]["net_change"] == -35
    assert first["period_total"]["net_change"] == -35
    with db_factory() as db:
        sales_summary = main.get_sales_receivable_summary("00001", 1, date(2026, 10, 3), db)
        payment_summary = main.get_payment_payable_summary("00001", 1, date(2026, 10, 3), db)
        purchase_summary = main.get_purchase_payable_summary("00001", 1, date(2026, 10, 3), db)
    assert first["ending_balance"] == sales_summary["current_receivable"] == 25
    assert first["ending_balance"] == -payment_summary["current_payable"]
    assert first["ending_balance"] == -purchase_summary["current_payable"]


def test_ledger_filters_company_and_hides_preperiod_transactions_in_detail(db_factory):
    data = get_ledger(db_factory, start="2026-10-01", end="2026-10-01")
    assert data["opening_balance"] == 60
    assert [row["transaction_no"] for row in data["transactions"]] == ["SA-1", "PU-1"]
    other = get_ledger(db_factory, comp="00002", start="2026-10-01", end="2026-10-03")
    assert other["opening_balance"] == 999
    assert other["transactions"] == []
    assert other["ending_balance"] == 999


def test_multiline_purchase_and_sale_details_show_source_item_values_without_repeating_ledger_amount(db_factory):
    with db_factory() as db:
        warehouse = models.Warehouse(warehouse_code="LEDGER-WH", warehouse_name="테스트 창고")
        products = [
            models.Product(product_code="LEDGER-P1", product_name="우삼겹 미국"),
            models.Product(product_code="LEDGER-P2", product_name="삼겹살 칠레"),
        ]
        db.add_all([warehouse, *products])
        db.flush()
        purchase = models.Purchase(
            comp_code="00001", purchase_no="PU-MULTI", purchase_date=date(2026, 10, 2),
            account_id=1, document_status="CONFIRMED", total_box_qty=3, total_weight=30,
            total_supply_amount=5000, total_tax_amount=0, total_discount_amount=0,
            total_amount=5000, memo="냉동 원료 입고", created_by="ledger-admin", updated_by="ledger-admin",
            items=[
                models.PurchaseItem(line_no=1, product=products[0], box_qty=1, weight=10, unit_price=100,
                    supply_amount=1000, tax_code_snapshot="ZERO", tax_name_snapshot="면세",
                    tax_rate_snapshot=0, tax_amount=0, discount_amount=0, total_amount=1000,
                    history_no="H-P-001", bl_no="BL-P-01", memo="앞다리"),
                models.PurchaseItem(line_no=2, product=products[1], box_qty=2, weight=20, unit_price=200,
                    supply_amount=4000, tax_code_snapshot="ZERO", tax_name_snapshot="면세",
                    tax_rate_snapshot=0, tax_amount=0, discount_amount=0, total_amount=4000,
                    history_no="H-P-002", bl_no="BL-P-02", memo="냉동삼겹"),
            ],
        )
        lot1 = models.Lot(comp_code="00001", lot_code="LOT-S-01", product_id=products[0].product_id,
            warehouse_id=warehouse.warehouse_id, source_type="DOMESTIC", history_no="H-S-001", bl_no="BL-S-01")
        lot2 = models.Lot(comp_code="00001", lot_code="LOT-S-02", product_id=products[1].product_id,
            warehouse_id=warehouse.warehouse_id, source_type="DOMESTIC", history_no="H-S-002", bl_no="BL-S-02")
        db.add_all([purchase, lot1, lot2])
        db.flush()
        sale = models.Sale(
            comp_code="00001", sale_no="SA-MULTI", sale_date=date(2026, 10, 2), account_id=1,
            document_status="CONFIRMED", total_box_qty=7, total_weight=7, total_supply_amount=450,
            total_tax_amount=0, total_discount_amount=0, total_amount=450, memo="거래처 정기 출고",
            inventory_exception_yn=False, created_by="ledger-admin", updated_by="ledger-admin",
            items=[
                models.SaleItem(line_no=1, product=products[0], lot=lot1, box_qty=3, weight=3,
                    unit_price=50, supply_amount=150, tax_code_snapshot="ZERO", tax_name_snapshot="면세",
                    tax_rate_snapshot=0, tax_amount=0, discount_amount=0, total_amount=150, memo="냉장"),
                models.SaleItem(line_no=2, product=products[1], lot=lot2, box_qty=4, weight=4,
                    unit_price=75, supply_amount=300, tax_code_snapshot="ZERO", tax_name_snapshot="면세",
                    tax_rate_snapshot=0, tax_amount=0, discount_amount=0, total_amount=300),
            ],
        )
        db.add(sale)
        db.add_all([
            models.AccountTransaction(comp_code="00001", account_id=1, transaction_type="PURCHASE_PAYABLE",
                transaction_no="PU-MULTI", transaction_date=date(2026, 10, 2), original_amount=5000, memo="상품매입 PU-MULTI"),
            models.AccountTransaction(comp_code="00001", account_id=1, transaction_type="SALES_RECEIVABLE",
                transaction_no="SA-MULTI", transaction_date=date(2026, 10, 2), original_amount=450, memo="일반매출 SA-MULTI"),
        ])
        db.commit()

    ledger = get_ledger(db_factory)
    purchase = next(row for row in ledger["transactions"] if row["transaction_no"] == "PU-MULTI")
    sale = next(row for row in ledger["transactions"] if row["transaction_no"] == "SA-MULTI")
    assert purchase["source_type"] == "PURCHASE" and purchase["source_id"] is not None
    assert sale["source_type"] == "SALE" and sale["source_id"] is not None
    assert (purchase["box_qty"], purchase["weight"], purchase["line_amount"]) == (3, 30.0, 5000)
    assert (sale["box_qty"], sale["weight"], sale["line_amount"]) == (7, 7.0, 450)
    assert {item["source_id"] for item in purchase["details"]} == {purchase["source_id"]}
    assert {item["source_id"] for item in sale["details"]} == {sale["source_id"]}
    assert [(item["product_name"], item["box_qty"], item["weight"], item["unit_price"], item["line_amount"])
            for item in purchase["details"]] == [
                ("우삼겹 미국", 1, 10.0, 100, 1000), ("삼겹살 칠레", 2, 20.0, 200, 4000)]
    assert [item["reference"] for item in purchase["details"]] == [
        "이력 H-P-001 · BL BL-P-01", "이력 H-P-002 · BL BL-P-02"]
    assert all(item["product_name"] in item["memo"] and "PU-MULTI" not in item["memo"] for item in purchase["details"])
    assert [(item["product_name"], item["box_qty"], item["weight"], item["unit_price"], item["line_amount"])
            for item in sale["details"]] == [
                ("우삼겹 미국", 3, 3.0, 50, 150), ("삼겹살 칠레", 4, 4.0, 75, 300)]
    assert [item["reference"] for item in sale["details"]] == [
        "LOT LOT-S-01 · 이력 H-S-001 · BL BL-S-01",
        "LOT LOT-S-02 · 이력 H-S-002 · BL BL-S-02"]
    assert all(item["product_name"] in item["memo"] and "SA-MULTI" not in item["memo"] for item in sale["details"])
    from views.account_ledger import AccountLedgerWindow
    displayed = AccountLedgerWindow._expand_transactions(ledger["transactions"])
    purchase_lines = [row for row in displayed if row["transaction_no"] == "PU-MULTI"]
    sale_lines = [row for row in displayed if row["transaction_no"] == "SA-MULTI"]
    assert [row["line_amount"] for row in purchase_lines] == [1000, 4000]
    assert [row["purchase_amount"] for row in purchase_lines] == [5000, None]
    assert [row["line_amount"] for row in sale_lines] == [150, 300]
    assert [row["sales_amount"] for row in sale_lines] == [450, None]
    assert ledger["period_total"]["purchase_amount"] == 5070
    assert ledger["period_total"]["sales_amount"] == 530
    assert sum(row["purchase_amount"] for row in purchase_lines if row["purchase_amount"] is not None) == 5000
    assert sum(row["sales_amount"] for row in sale_lines if row["sales_amount"] is not None) == 450
    assert ledger["ending_balance"] == 25 - 5000 + 450 == -4525
    with db_factory() as db:
        assert ledger["ending_balance"] == int(main.account_net_balance(db, "00001", 1, date(2026, 10, 3)))
        purchase_record = db.query(models.Purchase).filter_by(purchase_no="PU-MULTI").one()
        purchase_record.items[1].product.product_name = "수정 상품명"
        purchase_record.items[1].box_qty = 5
        purchase_record.items[1].weight = 50
        purchase_record.items[1].unit_price = 250
        purchase_record.items[1].total_amount = 12500
        purchase_record.total_box_qty = 6
        purchase_record.total_weight = 60
        purchase_record.total_amount = 13500
        tx = db.query(models.AccountTransaction).filter_by(transaction_no="PU-MULTI").one()
        tx.original_amount = 13500
        db.commit()
    refreshed = get_ledger(db_factory)
    refreshed_purchase = next(row for row in refreshed["transactions"] if row["transaction_no"] == "PU-MULTI")
    assert refreshed_purchase["details"][1]["product_name"] == "수정 상품명"
    assert (refreshed_purchase["details"][1]["box_qty"], refreshed_purchase["details"][1]["weight"],
            refreshed_purchase["details"][1]["unit_price"], refreshed_purchase["details"][1]["line_amount"]) == (5, 50.0, 250, 12500)
    assert refreshed["ending_balance"] == 25 - 13500 + 450 == -13025
    with db_factory() as db:
        purchase_record = db.query(models.Purchase).filter_by(purchase_no="PU-MULTI").one()
        tx = db.query(models.AccountTransaction).filter_by(transaction_no="PU-MULTI").one()
        db.delete(tx)
        db.delete(purchase_record)
        db.commit()
    after_delete = get_ledger(db_factory)
    assert not any(row["transaction_no"] == "PU-MULTI" for row in after_delete["transactions"])
    assert after_delete["ending_balance"] == 25 + 450 == 475


def test_ledger_drilldown_dispatches_stable_source_ids_and_reuses_mdi_windows(monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget
    from app_context import app_context
    import views.mxmn_main_window as main_window_module
    from views.mxmn_main_window import MixNMainWindow

    app = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")

    def fake_window(name):
        class SourceWindow(QWidget):
            def __init__(self):
                super().__init__()
                self.opened_ids = []

            def open_source_id(self, source_id):
                self.opened_ids.append(source_id)
        SourceWindow.__name__ = name
        return SourceWindow

    source_classes = {
        "PURCHASE": fake_window("PurchaseRegWindow"),
        "SALE": fake_window("SaleRegWindow"),
        "RECEIPT": fake_window("ReceiptRegWindow"),
        "PAYMENT": fake_window("PaymentRegWindow"),
    }
    for source_type, class_name in ((key, f"{key.title()}RegWindow") for key in source_classes):
        monkeypatch.setattr(main_window_module, class_name, source_classes[source_type])
    main_window = MixNMainWindow()
    try:
        for source_type, source_id in (("PURCHASE", 11), ("SALE", 22), ("RECEIPT", 33), ("PAYMENT", 44), ("PURCHASE", 11)):
            main_window.open_account_ledger_source(source_type, source_id)
            app.processEvents()
        source_subwindows = [sub for sub in main_window.mdi_area.subWindowList()
                             if type(sub.widget()) in source_classes.values()]
        assert len(source_subwindows) == 4
        opened = {
            type(sub.widget()).__name__: sub.widget().opened_ids
            for sub in source_subwindows
        }
        assert opened == {
            "PurchaseRegWindow": [11, 11], "SaleRegWindow": [22],
            "ReceiptRegWindow": [33], "PaymentRegWindow": [44],
        }
    finally:
        main_window.close()
        app.processEvents()


def test_each_ledger_drilldown_target_selects_the_exact_source_primary_key():
    import os
    from types import SimpleNamespace
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtWidgets import QApplication, QDateEdit, QTableWidget, QTableWidgetItem
    from views.purchase_reg import PurchaseRegWindow
    from views.sale_reg import SaleRegWindow
    from views.receipt_reg import ReceiptRegWindow
    from views.payment_reg import PaymentRegWindow

    app = QApplication.instance() or QApplication([])

    def document_target(source_class, source_id, key, date_field, control_field):
        table = QTableWidget(1, 1)
        cell = QTableWidgetItem("source")
        cell.setData(Qt.UserRole, source_id)
        table.setItem(0, 0, cell)
        date = QDateEdit()
        target = SimpleNamespace(
            saved=[{key: source_id, date_field: "2026-10-02"}],
            load_all=lambda: None,
            query_sales=lambda: None,
            load_data=lambda: None,
            today_table=table,
            **{control_field: date},
        )
        assert source_class.open_source_id(target, source_id) is True
        assert table.currentRow() == 0
        assert date.date() == QDate(2026, 10, 2)

    document_target(PurchaseRegWindow, 101, "purchase_id", "purchase_date", "purchase_date")
    document_target(SaleRegWindow, 202, "sale_id", "sale_date", "date")

    def settlement_target(source_class, source_id):
        table = QTableWidget(1, 1)
        cell = QTableWidgetItem("settlement")
        cell.setData(Qt.UserRole, source_id)
        table.setItem(0, 0, cell)
        target = SimpleNamespace(
            rows=[{"account_transaction_id": source_id}],
            load_data=lambda: None,
            table=table,
            current_id=None,
        )
        target._select_id = lambda transaction_id: ReceiptRegWindow._select_id(target, transaction_id)
        table.itemSelectionChanged.connect(lambda: setattr(target, "current_id", source_id))
        assert source_class.open_source_id(target, source_id) is True
        assert target.current_id == source_id and table.currentRow() == 0

    settlement_target(ReceiptRegWindow, 303)
    settlement_target(PaymentRegWindow, 404)
    app.processEvents()


def test_ledger_rejects_reversed_dates_and_unknown_company_relation(db_factory):
    with pytest.raises(HTTPException) as reversed_dates:
        get_ledger(db_factory, start="2026-10-04", end="2026-10-03")
    assert reversed_dates.value.status_code == 422
    with pytest.raises(HTTPException) as invalid_account:
        get_ledger(db_factory, account_id=999)
    assert invalid_account.value.status_code == 404
    assert permission_for_request("GET", "/api/v1/companies/00001/account-ledger").menu_code == "ACCOUNT_LEDGER"


def test_ledger_menu_selection_query_and_mdi_close_reopen(monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app_context import app_context
    from views.account_ledger import AccountLedgerWindow
    from views.mxmn_main_window import MixNMainWindow

    app = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")

    class Response:
        status_code = 200
        def __init__(self, body): self.body = body
        def raise_for_status(self): return None
        def json(self): return self.body

    ledger = {
        "transactions": [{"transaction_date": "2026-10-03", "transaction_no": "RC-1", "type_label": "입금", "memo": "[입금] 테스트", "source_type": "RECEIPT", "source_id": 77, "box_qty": None, "weight": None, "unit_price": None, "sales_amount": 0, "receipt_amount": 100, "purchase_amount": 0, "payment_amount": 0, "balance": 50, "reference": None}],
        "daily_totals": {"2026-10-03": {"box_qty": 0, "weight": 0, "sales_amount": 0, "receipt_amount": 100, "purchase_amount": 0, "payment_amount": 0, "net_change": -100}},
        "monthly_totals": {"2026-10": {"box_qty": 0, "weight": 0, "sales_amount": 0, "receipt_amount": 100, "purchase_amount": 0, "payment_amount": 0, "net_change": -100}},
        "period_total": {"net_change": -100}, "opening_balance": 150, "ending_balance": 50,
    }
    def fake_get(url, **kwargs):
        if url.endswith("/accounts"):
            return Response([{"account_id": 1, "account_name": "거래처", "use_yn": True, "trade_stop_yn": False}])
        if url.endswith("/account-ledger"):
            assert kwargs["params"] == {"account_id": 1, "start_date": kwargs["params"]["start_date"], "end_date": kwargs["params"]["end_date"]}
            return Response(ledger)
        raise AssertionError(url)

    monkeypatch.setattr("views.account_ledger.httpx.get", fake_get)
    main_window = MixNMainWindow()
    assert main_window.action_account_ledger.text() == "1.거래처원장"
    main_window.open_account_ledger()
    app.processEvents()
    sub = next(window for window in main_window.mdi_area.subWindowList() if type(window.widget()) is AccountLedgerWindow)
    screen = sub.widget()
    drilldown = []
    main_window.open_account_ledger_source = lambda source_type, source_id: drilldown.append((source_type, source_id))
    assert screen.account.currentData() == 1
    assert screen.transaction_table.rowCount() == 1
    assert screen.transaction_table.item(0, 1).text() == "RC-1"
    assert screen.period_table.rowCount() == 1
    assert "최종잔액: 50원" in screen.balance_summary.text()
    screen.transaction_table.itemDoubleClicked.emit(screen.transaction_table.item(0, 0))
    assert drilldown == [("RECEIPT", 77)]
    sub.close()
    app.processEvents()
    main_window.open_account_ledger()
    app.processEvents()
    reopened = [window for window in main_window.mdi_area.subWindowList() if type(window.widget()) is AccountLedgerWindow]
    assert len(reopened) == 1
    assert reopened[0].widget().transaction_table.rowCount() == 1
    main_window.close()
