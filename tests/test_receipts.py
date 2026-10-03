from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

with patch("sqlalchemy.create_engine", return_value=create_engine("sqlite://")):
    import main

import models
import receipt_routes
from audit_service import AuditEvent
from database import Base, get_db
from permissions import issue_token, permission_for_request


URL = "/api/v1/companies/00001/receipts"


@pytest.fixture
def api(monkeypatch):
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
            models.Company(comp_code="00001", comp_name="T", biz_no="1"),
            models.User(user_id="tester", user_name="T", password_hash="x", is_admin=True),
            models.Account(account_id=1, account_code="A1", account_name="매출처"),
            models.MenuMaster(menu_code="RECEIPT_MANAGEMENT", menu_name="입금관리", menu_group="입금/출금관리"),
            models.MenuMaster(menu_code="SALES_GENERAL", menu_name="매출", menu_group="거래"),
        ])
        db.commit()
        db.add(models.CompanyAccount(comp_code="00001", account_id=1, sales_yn=True, purchase_yn=False))
        db.add_all([
            models.AccountTransaction(
                comp_code="00001", transaction_no="OR20261001-001", transaction_date=date(2026, 10, 1),
                account_id=1, transaction_type="OPENING_RECEIVABLE", original_amount=100000, memo="기초미수"
            ),
            models.AccountTransaction(
                comp_code="00001", transaction_no="SA-001", transaction_date=date(2026, 10, 2),
                account_id=1, transaction_type="SALES_RECEIVABLE", original_amount=50000, memo="매출"
            ),
        ])
        db.commit()

    def dependency():
        with factory() as db:
            yield db

    main.app.dependency_overrides[get_db] = dependency
    monkeypatch.setattr(main, "SessionLocal", factory)
    counters = {"RECEIPT": 0}
    def allocate(db, comp_code, kind, day):
        counters[kind] = counters.get(kind, 0) + 1
        return f"RC-{day:%Y%m%d}-{counters[kind]:04d}"
    monkeypatch.setattr(receipt_routes, "allocate_document_no", allocate)
    with TestClient(main.app, raise_server_exceptions=False) as client:
        client.headers["Authorization"] = "Bearer " + issue_token("tester")
        yield client, factory
    main.app.dependency_overrides.clear()
    engine.dispose()


def payload(amount=120000, day="2026-10-03"):
    return {"receipt_date": day, "account_id": 1, "amount": amount, "memo": "통장입금"}


def test_receipt_permission_is_separate_menu():
    rule = permission_for_request("POST", "/api/v1/companies/00001/receipts")
    assert (rule.menu_code, rule.action) == ("RECEIPT_MANAGEMENT", "create")


def test_receipt_fifo_allocates_oldest_receivable_first(api):
    client, factory = api
    response = client.post(URL, json=payload())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["amount"] == 120000
    assert body["allocated_amount"] == 120000
    assert body["unallocated_amount"] == 0
    with factory() as db:
        receipt = db.query(models.AccountTransaction).filter_by(transaction_type="RECEIPT").one()
        allocations = db.query(models.AccountTransactionAllocation).order_by(models.AccountTransactionAllocation.allocation_id).all()
        assert [int(x.allocated_amount) for x in allocations] == [100000, 20000]
        assert all(x.settlement_transaction_id == receipt.account_transaction_id for x in allocations)
        assert db.query(AuditEvent).filter_by(entity_type="RECEIPT", action="CREATE").count() == 1
    summary = client.get(
        "/api/v1/companies/00001/sales-receivable-summary",
        params={"account_id": 1, "transaction_date": "2026-10-03"},
    ).json()
    assert summary["previous_receivable"] == 150000
    assert summary["today_receipt"] == 120000
    assert summary["current_receivable"] == 30000


def test_over_receipt_keeps_unallocated_advance(api):
    client, factory = api
    response = client.post(URL, json=payload(200000))
    assert response.status_code == 201, response.text
    assert response.json()["allocated_amount"] == 150000
    assert response.json()["unallocated_amount"] == 50000
    with factory() as db:
        assert sum(Decimal(x.allocated_amount) for x in db.query(models.AccountTransactionAllocation).all()) == Decimal("150000")
    summary = client.get(
        "/api/v1/companies/00001/sales-receivable-summary",
        params={"account_id": 1, "transaction_date": "2026-10-03"},
    ).json()
    assert summary["current_receivable"] == -50000


def test_receipt_update_rebuilds_allocations_and_delete_restores_sources(api):
    client, factory = api
    created = client.post(URL, json=payload(120000))
    receipt_id = created.json()["account_transaction_id"]
    updated = client.put(f"{URL}/{receipt_id}", json=payload(60000))
    assert updated.status_code == 200, updated.text
    assert updated.json()["allocated_amount"] == 60000
    with factory() as db:
        allocations = db.query(models.AccountTransactionAllocation).all()
        assert len(allocations) == 1
        assert int(allocations[0].allocated_amount) == 60000
        actions = [x.action for x in db.query(AuditEvent).filter_by(entity_type="RECEIPT").order_by(AuditEvent.audit_event_id)]
        assert actions == ["CREATE", "UPDATE"]
    deleted = client.delete(f"{URL}/{receipt_id}")
    assert deleted.status_code == 200, deleted.text
    with factory() as db:
        assert db.query(models.AccountTransaction).filter_by(transaction_type="RECEIPT").count() == 0
        assert db.query(models.AccountTransactionAllocation).count() == 0
        actions = [x.action for x in db.query(AuditEvent).filter_by(entity_type="RECEIPT").order_by(AuditEvent.audit_event_id)]
        assert actions == ["CREATE", "UPDATE", "DELETE"]
