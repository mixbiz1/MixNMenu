"""Cross-flow regression checks against isolated SQLite ORM state.

These tests call the same route functions directly so their business transactions,
allocations, audit writes, and ledger projections can be verified without HTTP.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

with patch("sqlalchemy.create_engine", return_value=create_engine("sqlite://")):
    import main
import models
import payment_routes
import receipt_routes
from account_ledger import build_account_ledger
from audit_service import AuditEvent
from database import Base
from settlement_service import account_net_balance


@pytest.fixture
def db_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _sqlite_setup(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.create_function(
            "SYSUTCDATETIME", 0,
            lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat(" "),
        )

    for table in Base.metadata.tables.values():
        table.dialect_options["sqlite"]["autoincrement"] = True
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        db.add_all([
            models.Company(comp_code="00001", comp_name="흐름검증", biz_no="1"),
            models.User(user_id="tester", user_name="검증자", password_hash="x", is_admin=True),
            models.Account(account_id=1, account_code="A1", account_name="겸업 거래처"),
            models.Account(account_id=2, account_code="A2", account_name="매입처"),
            models.Product(product_id=1, product_code="P1", product_name="테스트육", tax_type="2"),
            models.Warehouse(warehouse_id=1, warehouse_code="W1", warehouse_name="테스트창고"),
            models.TaxCode(tax_code="EXEMPT", tax_name="면세", tax_kind="EXEMPT",
                           tax_rate=0, valid_from=date(2000, 1, 1)),
        ])
        db.commit()
        db.add_all([
            models.CompanyAccount(comp_code="00001", account_id=1, purchase_yn=True, sales_yn=True),
            models.CompanyAccount(comp_code="00001", account_id=2, purchase_yn=True, sales_yn=False),
            models.CompanyWarehouse(comp_code="00001", warehouse_id=1),
        ])
        db.commit()

    counters = {"PURCHASE": 0, "PURCHASE_INBOUND": 0, "SALE": 0, "OUTBOUND": 0,
                "PAYMENT": 0, "RECEIPT": 0}

    def allocate(_db, _company, kind, day):
        counters[kind] += 1
        return f"{kind[:2]}-{day:%Y%m%d}-{counters[kind]:04d}"

    monkeypatch.setattr(main, "allocate_document_no", allocate)
    monkeypatch.setattr(payment_routes, "allocate_document_no", allocate)
    monkeypatch.setattr(receipt_routes, "allocate_document_no", allocate)
    yield factory
    engine.dispose()


def request(method, path):
    return SimpleNamespace(
        method=method, url=SimpleNamespace(path=path), state=SimpleNamespace(user_id="tester")
    )


def purchase_input(amount=1000, day=date(2026, 10, 1), account_id=1):
    weight = Decimal(amount) / Decimal(100)
    return main.PurchaseInput(
        purchase_date=day, account_id=account_id, finalize=True,
        items=[main.PurchaseItemInput(
            line_no=1, product_id=1, warehouse_id=1, box_qty=1,
            weight=weight, unit_price=100,
        )],
    )


def create_purchase(db, amount=1000, day=date(2026, 10, 1), account_id=1):
    return main.create_purchase(
        "00001", purchase_input(amount, day, account_id), request("POST", "/purchases"), db
    )


def sale_input(lot_id, amount=800, day=date(2026, 10, 2)):
    weight = Decimal(amount) / Decimal(100)
    return main.SaleInput(
        sale_date=day, account_id=1,
        items=[main.SaleItemInput(
            line_no=1, product_id=1, lot_id=lot_id, box_qty=1,
            weight=weight, unit_price=100,
        )],
    )


def create_sale(db, lot_id, amount=800, day=date(2026, 10, 2)):
    return main.create_sale("00001", sale_input(lot_id, amount, day), request("POST", "/sales"), db)


def test_real_purchase_sale_settlement_and_ledger_share_one_net_balance(db_factory):
    with db_factory() as db:
        purchase = create_purchase(db)
        payable = db.query(models.AccountTransaction).filter_by(
            transaction_type="PURCHASE_PAYABLE").one()
        assert int(payable.original_amount) == purchase["total_amount"] == 1000
        assert purchase["document_status"] == "CONFIRMED"
        assert db.query(models.Lot).count() == 1

        sale = create_sale(db, purchase["items"][0]["lot_id"])
        receivable = db.query(models.AccountTransaction).filter_by(
            transaction_type="SALES_RECEIVABLE").one()
        assert int(receivable.original_amount) == sale["total_amount"] == 800
        assert db.query(models.OutboundItem).count() == 1

        # A sold LOT protects its source purchase from changes and cancellation.
        with pytest.raises(HTTPException) as lot_update_blocked:
            main.update_purchase("00001", purchase["purchase_id"], purchase_input(),
                                 request("PUT", "/purchases"), db)
        assert lot_update_blocked.value.status_code == 409
        db.rollback()
        with pytest.raises(HTTPException) as lot_cancel_blocked:
            main.cancel_purchase(
                "00001", purchase["purchase_id"], main.PurchaseCancelInput(reason="검증"),
                request("POST", "/purchases/cancel"), db,
            )
        assert lot_cancel_blocked.value.status_code == 409
        db.rollback()

        # A separate purchase isolates the payable Allocation Guard from LOT links.
        guarded_purchase = create_purchase(db, amount=500, account_id=2)
        guarded_payment = payment_routes.create_payment(
            "00001", payment_routes.PaymentInput(payment_date=date(2026, 10, 3), account_id=2,
                                                    amount=100, memo="부분지급"),
            request("POST", "/payments"), db,
        )
        assert guarded_payment["allocated_amount"] == 100
        with pytest.raises(HTTPException) as allocation_update_blocked:
            main.update_purchase("00001", guarded_purchase["purchase_id"],
                                 purchase_input(amount=500, account_id=2),
                                 request("PUT", "/purchases"), db)
        assert allocation_update_blocked.value.status_code == 409
        db.rollback()
        with pytest.raises(HTTPException) as allocation_cancel_blocked:
            main.cancel_purchase(
                "00001", guarded_purchase["purchase_id"], main.PurchaseCancelInput(reason="검증"),
                request("POST", "/purchases/cancel"), db,
            )
        assert allocation_cancel_blocked.value.status_code == 409
        db.rollback()

        payment = payment_routes.create_payment(
            "00001", payment_routes.PaymentInput(payment_date=date(2026, 10, 3), account_id=1,
                                                    amount=400, memo="부분지급"),
            request("POST", "/payments"), db,
        )
        assert payment["allocated_amount"] == 400

        receipt = receipt_routes.create_receipt(
            "00001", receipt_routes.ReceiptInput(receipt_date=date(2026, 10, 3), account_id=1,
                                                    amount=300, memo="부분입금"),
            request("POST", "/receipts"), db,
        )
        assert payment["allocated_amount"] == 400
        assert receipt["allocated_amount"] == 300
        balance = account_net_balance(db, "00001", 1, date(2026, 10, 3))
        ledger = build_account_ledger(db, "00001", 1, date(2026, 10, 1), date(2026, 10, 3))
        assert balance == Decimal(-100)
        assert ledger["ending_balance"] == -100
        assert main.get_sales_receivable_summary(
            "00001", 1, date(2026, 10, 3), db
        )["current_receivable"] == -100
        assert main.get_purchase_payable_summary(
            "00001", 1, date(2026, 10, 3), db
        )["current_payable"] == 100

        # Receipt allocation symmetrically protects a confirmed sale from change/cancellation.
        with pytest.raises(HTTPException) as sale_update_blocked:
            main.update_sale(
                "00001", sale["sale_id"], sale_input(sale["items"][0]["lot_id"]),
                request("PUT", "/sales"), db,
            )
        assert sale_update_blocked.value.status_code == 409
        db.rollback()
        with pytest.raises(HTTPException) as sale_blocked:
            main.cancel_sale(
                "00001", sale["sale_id"], main.SaleCancelInput(reason="검증"),
                request("POST", "/sales/cancel"), db,
            )
        assert sale_blocked.value.status_code == 409
        db.rollback()
        db.refresh(db.get(models.Sale, sale["sale_id"]))
        assert db.query(models.AccountTransaction).filter_by(
            transaction_type="SALES_RECEIVABLE").count() == 1
        assert db.query(models.OutboundItem).count() == 1
        purchase_actions = [row.action for row in db.query(AuditEvent).filter_by(
            entity_type="PURCHASE").order_by(AuditEvent.audit_event_id)]
        sale_actions = [row.action for row in db.query(AuditEvent).filter_by(
            entity_type="SALE").order_by(AuditEvent.audit_event_id)]
        assert purchase_actions == ["CREATE", "CONFIRM", "CREATE", "CONFIRM"]
        assert sale_actions == ["CREATE", "CONFIRM"]


@pytest.mark.parametrize(
    ("settlement_type", "source_type", "input_type", "route_module", "date_field", "url"),
    [
        ("PAYMENT", "PURCHASE_PAYABLE", payment_routes.PaymentInput, payment_routes,
         "payment_date", "/payments"),
        ("RECEIPT", "SALES_RECEIVABLE", receipt_routes.ReceiptInput, receipt_routes,
         "receipt_date", "/receipts"),
    ],
)
def test_settlement_edit_delete_rebuilds_allocations_and_restores_source(
        db_factory, settlement_type, source_type, input_type, route_module, date_field, url):
    with db_factory() as db:
        source = models.AccountTransaction(
            comp_code="00001", account_id=1, transaction_no=f"{source_type}-1",
            transaction_date=date(2026, 10, 1), transaction_type=source_type, original_amount=1000,
        )
        db.add(source)
        db.commit()
        data = input_type(**{date_field: date(2026, 10, 2), "account_id": 1,
                             "amount": 400, "memo": "부분 정산"})
        if settlement_type == "PAYMENT":
            created = route_module.create_payment("00001", data, request("POST", url), db)
            update = route_module.update_payment
            delete = route_module.delete_payment
        else:
            created = route_module.create_receipt("00001", data, request("POST", url), db)
            update = route_module.update_receipt
            delete = route_module.delete_receipt
        assert created["allocated_amount"] == 400
        settlement_id = created["account_transaction_id"]
        updated_data = input_type(**{date_field: date(2026, 10, 2), "account_id": 1,
                                     "amount": 600, "memo": "수정 정산"})
        updated = update("00001", settlement_id, updated_data, request("PUT", url), db)
        assert updated["allocated_amount"] == 600
        assert int(db.query(models.AccountTransactionAllocation).filter_by(
            source_transaction_id=source.account_transaction_id).with_entities(
                models.AccountTransactionAllocation.allocated_amount).scalar()) == 600
        assert Decimal(source.original_amount) - Decimal(600) == 400

        delete("00001", settlement_id, request("DELETE", url), db=db)
        db.refresh(source)
        assert db.query(models.AccountTransactionAllocation).count() == 0
        assert Decimal(source.original_amount) == 1000
        assert db.query(models.AccountTransaction).filter_by(
            account_transaction_id=settlement_id).count() == 0
        actions = [row.action for row in db.query(AuditEvent).filter_by(
            entity_type=settlement_type).order_by(AuditEvent.audit_event_id)]
        assert actions == ["CREATE", "UPDATE", "DELETE"]


@pytest.mark.parametrize(
    ("route_module", "input_type", "date_field", "settlement_type", "source_type", "summary_name", "url"),
    [
        (payment_routes, payment_routes.PaymentInput, "payment_date", "PAYMENT", "PURCHASE_PAYABLE",
         "get_purchase_payable_summary", "/payments"),
        (receipt_routes, receipt_routes.ReceiptInput, "receipt_date", "RECEIPT", "SALES_RECEIVABLE",
         "get_sales_receivable_summary", "/receipts"),
    ],
)
def test_advances_offset_later_documents_and_negative_adjustments_are_bounded(
        db_factory, route_module, input_type, date_field, settlement_type, source_type, summary_name, url):
    with db_factory() as db:
        # An advance remains unallocated to a future source document; the common
        # account balance offsets that document immediately in both directions.
        create = route_module.create_payment if settlement_type == "PAYMENT" else route_module.create_receipt
        send = lambda day, amount, memo: create(
            "00001", input_type(**{date_field: date(2026, 10, day), "account_id": 1,
                                   "amount": amount, "memo": memo}),
            request("POST", url), db,
        )
        advance = send(1, 500, "선정산")
        source = models.AccountTransaction(
            comp_code="00001", account_id=1, transaction_no=f"{source_type}-LATER",
            transaction_date=date(2026, 10, 2), transaction_type=source_type, original_amount=300,
        )
        db.add(source)
        db.commit()
        assert advance["unallocated_amount"] == 500
        summary = getattr(main, summary_name)("00001", 1, date(2026, 10, 2), db)
        balance_key = "current_payable" if settlement_type == "PAYMENT" else "current_receivable"
        assert summary[balance_key] == -200
        assert db.query(models.AccountTransactionAllocation).count() == 0

        adjusted = send(3, -200, "선정산 조정")
        assert adjusted["unallocated_amount"] == -200
        balance = account_net_balance(db, "00001", 1, date(2026, 10, 3))
        assert balance == Decimal(0)
        with pytest.raises(HTTPException) as too_large:
            send(4, -1000, "초과 조정")
        assert too_large.value.status_code == 409
        db.rollback()
        assert db.query(AuditEvent).filter_by(entity_type=settlement_type, action="CREATE").count() == 2


@pytest.mark.parametrize(
    ("route_module", "input_type", "date_field", "settlement_type", "url"),
    [
        (payment_routes, payment_routes.PaymentInput, "payment_date", "PAYMENT", "/payments"),
        (receipt_routes, receipt_routes.ReceiptInput, "receipt_date", "RECEIPT", "/receipts"),
    ],
)
def test_negative_settlement_adjustment_reason_advance_reversal_and_audit(
        db_factory, route_module, input_type, date_field, settlement_type, url):
    with db_factory() as db:
        create = route_module.create_payment if settlement_type == "PAYMENT" else route_module.create_receipt
        def send(amount, memo=None, audit_reason=None, day=3):
            data = input_type(**{date_field: date(2026, 10, day), "account_id": 1,
                                 "amount": amount, "memo": memo, "audit_reason": audit_reason})
            return create("00001", data, request("POST", url), db)

        with pytest.raises(HTTPException) as no_reason:
            send(-1, memo=" ")
        assert no_reason.value.status_code == 422
        db.rollback()
        original = send(500, memo="선정산")
        adjusted = send(-200, memo="선정산 취소", day=4)
        assert original["unallocated_amount"] == 500
        assert adjusted["unallocated_amount"] == -200
        with pytest.raises(HTTPException) as too_large:
            send(-400, memo="범위 초과", day=5)
        assert too_large.value.status_code == 409
        db.rollback()
        actions = [row.action for row in db.query(AuditEvent).filter_by(
            entity_type=settlement_type).order_by(AuditEvent.audit_event_id)]
        assert actions == ["CREATE", "CREATE"]


def test_mixed_opening_purchase_sale_receipt_payment_netting_matches_ledger(db_factory):
    with db_factory() as db:
        rows = [
            ("OB-R", "OPENING_RECEIVABLE", 150),
            ("OB-P", "OPENING_PAYABLE", 100),
            ("SA", "SALES_RECEIVABLE", 1000),
            ("PU", "PURCHASE_PAYABLE", 700),
            ("RC", "RECEIPT", 200),
            ("PY", "PAYMENT", 100),
        ]
        db.add_all(models.AccountTransaction(
            comp_code="00001", account_id=1, transaction_no=no,
            transaction_date=date(2026, 10, 1), transaction_type=kind, original_amount=amount,
        ) for no, kind, amount in rows)
        db.commit()
        # 150 - 100 + 1,000 - 700 - 200 + 100 = 250.
        ledger = build_account_ledger(db, "00001", 1, date(2026, 10, 1), date(2026, 10, 1))
        assert account_net_balance(db, "00001", 1, date(2026, 10, 1)) == Decimal(250)
        assert ledger["ending_balance"] == 250
        assert main.get_sales_receivable_summary(
            "00001", 1, date(2026, 10, 1), db
        )["current_receivable"] == 250
        assert main.get_purchase_payable_summary(
            "00001", 1, date(2026, 10, 1), db
        )["current_payable"] == -250
