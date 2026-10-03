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
        "transactions": [{"transaction_date": "2026-10-03", "transaction_no": "RC-1", "type_label": "입금", "memo": "테스트", "box_qty": None, "weight": None, "unit_price": None, "sales_amount": 0, "receipt_amount": 100, "purchase_amount": 0, "payment_amount": 0, "balance": 50, "reference": None}],
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
    assert screen.account.currentData() == 1
    assert screen.transaction_table.rowCount() == 1
    assert screen.transaction_table.item(0, 1).text() == "RC-1"
    assert screen.period_table.rowCount() == 1
    assert "최종잔액: 50원" in screen.balance_summary.text()
    sub.close()
    app.processEvents()
    main_window.open_account_ledger()
    app.processEvents()
    reopened = [window for window in main_window.mdi_area.subWindowList() if type(window.widget()) is AccountLedgerWindow]
    assert len(reopened) == 1
    assert reopened[0].widget().transaction_table.rowCount() == 1
    main_window.close()
