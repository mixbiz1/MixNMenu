from datetime import date, datetime, timezone
from decimal import Decimal
from collections import defaultdict
from unittest.mock import patch
import tempfile
import os

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

with patch("sqlalchemy.create_engine", return_value=create_engine("sqlite://")):
    import models
    import financing_contract_routes as financing
    from database import Base, get_db
from audit_service import AuditEvent
from permissions import permission_for_request


URL = "/api/v1/companies/00001/financing-contracts"
class SyncAsgiClient:
    """Directly exercise route handlers because this runtime stalls on sync ASGI endpoints."""
    def __init__(self, factory): self.factory = factory; self.is_admin = True

    class Result:
        def __init__(self, value=None, status=200, error=None):
            self._value, self.status_code, self.text = value, status, str(error or value)
        def json(self): return self._value
        def raise_for_status(self):
            if self.status_code >= 400: raise AssertionError(self.text)

    def _request(self, method, path, **kwargs):
        parts = path.strip("/").split("/")
        comp_code, tail = parts[3], parts[5:]
        data = kwargs.get("json") or {}
        request = Request({"type": "http", "method": method, "path": path, "headers": [], "query_string": b""})
        request.state.user_id = "tester"; request.state.is_admin = self.is_admin
        with self.factory() as db:
            try:
                if method == "GET" and not tail: value = financing.list_contracts(comp_code, db)
                elif method == "POST" and not tail:
                    value = financing.create_contract(comp_code, financing.ContractCreate.model_validate(data), request, db)
                    return self.Result(value, 201)
                elif tail and tail[0].isdigit():
                    contract_id = int(tail[0]); action = tail[1:] if len(tail) > 1 else []
                    if method == "GET" and not action: value = financing.get_contract(comp_code, contract_id, db)
                    elif method == "GET" and action == ["history"]: value = financing.contract_history(comp_code, contract_id, db)
                    elif method == "PUT" and not action:
                        value = financing.update_contract(comp_code, contract_id, financing.ContractUpdate.model_validate(data), request, db)
                    elif method == "POST" and action == ["confirm"]: value = financing.confirm_contract(comp_code, contract_id, request, db)
                    elif method == "POST" and action == ["cancel"]:
                        value = financing.cancel_contract(comp_code, contract_id, financing.CancelInput.model_validate(data), request, db)
                    elif method == "POST" and action == ["terms"]:
                        value = financing.add_term(comp_code, contract_id, financing.TermInput.model_validate(data), request, db); return self.Result(value, 201)
                    elif method == "POST" and action == ["participants"]:
                        value = financing.add_participant(comp_code, contract_id, financing.ParticipantInput.model_validate(data), request, db); return self.Result(value, 201)
                    elif method == "PUT" and len(action) == 2 and action[0] == "participants":
                        value = financing.update_participant(comp_code, contract_id, int(action[1]), financing.ParticipantUpdate.model_validate(data), request, db)
                    elif method == "POST" and action == ["lots"]:
                        value = financing.add_contract_lot(comp_code, contract_id, financing.ContractLotInput.model_validate(data), request, db); return self.Result(value, 201)
                    elif method == "POST" and action == ["items"]:
                        value = financing.add_contract_item(comp_code, contract_id, financing.ContractItemInput.model_validate(data), request, db); return self.Result(value, 201)
                    else: return self.Result(status=404, error="not found")
                else: return self.Result(status=404, error="not found")
                return self.Result(value)
            except HTTPException as exc:
                return self.Result(status=exc.status_code, error=exc.detail)

    def get(self, path, **kwargs): return self._request("GET", path, **kwargs)
    def post(self, path, **kwargs): return self._request("POST", path, **kwargs)
    def put(self, path, **kwargs): return self._request("PUT", path, **kwargs)


@pytest.fixture
def api(monkeypatch):
    db_file = tempfile.NamedTemporaryFile(prefix="mxmn_financing_", suffix=".sqlite", delete=False)
    db_file.close()
    engine = create_engine(f"sqlite:///{db_file.name}", connect_args={"check_same_thread": False})

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
            models.Company(comp_code="00001", comp_name="T1", biz_no="1"),
            models.Company(comp_code="00002", comp_name="T2", biz_no="2"),
            models.User(user_id="tester", user_name="T", password_hash="x", is_admin=True),
            models.User(user_id="system", user_name="System", password_hash="x", is_admin=True),
            models.Account(account_id=1, account_code="A1", account_name="최초 계약업체"),
            models.Account(account_id=2, account_code="B1", account_name="추가 출고업체"),
            models.Account(account_id=3, account_code="C1", account_name="타 회사 업체"),
            models.Product(product_id=1, product_code="P1", product_name="상품", tax_type="2"),
            models.Product(product_id=2, product_code="P2", product_name="상품2", tax_type="2"),
            models.Warehouse(warehouse_id=1, warehouse_code="W1", warehouse_name="창고"),
            models.MenuMaster(menu_code="FINANCING_CONTRACT", menu_name="파이낸싱", menu_group="거래"),
        ])
        db.flush()
        db.add_all([
            models.CompanyAccount(comp_code="00001", account_id=1, purchase_yn=True, sales_yn=True),
            models.CompanyAccount(comp_code="00001", account_id=2, purchase_yn=True, sales_yn=True),
            models.CompanyAccount(comp_code="00002", account_id=3, purchase_yn=True, sales_yn=True),
        ])
        lot = models.Lot(comp_code="00001", lot_code="L1", source_type="DOMESTIC", product_id=1,
            warehouse_id=1, individual_cost=1000, status="OPEN", use_yn=True)
        other = models.Lot(comp_code="00002", lot_code="L2", source_type="DOMESTIC", product_id=1,
            warehouse_id=1, individual_cost=1000, status="OPEN", use_yn=True)
        db.add_all([lot, other]); db.flush()
        inbound = models.Inbound(comp_code="00001", inbound_no="I1", inbound_date=date(2026, 10, 2),
            warehouse_id=1, transaction_type="PURCHASE_INBOUND")
        db.add(inbound); db.flush()
        db.add(models.InboundItem(inbound_id=inbound.inbound_id, line_no=1, product_id=1, lot_id=lot.lot_id,
            box_qty=20, weight=Decimal("200.00"), individual_cost=1000, amount=200000))
        db.commit()
        other_lot_id = other.lot_id

    def dependency():
        with factory() as db:
            yield db
    client = SyncAsgiClient(factory)
    yield client, factory, other_lot_id
    engine.dispose()
    os.unlink(db_file.name)


def payload(number="FC-001", *, agreement="CONFIRMED", lot_id=1):
    return {
        "contract_no": number, "contract_type": "DOMESTIC_PURCHASE", "contract_date": "2026-10-02",
        "contractor_account_id": 1, "deposit_required": True, "deposit_amount": "30000",
        "deposit_memo": "계약 별도 담보", "participants": [{"account_id": 2,
            "agreement_status": agreement, "agreement_date": "2026-10-02" if agreement == "CONFIRMED" else None}],
        "lots": [{"lot_id": lot_id, "contract_box_qty": 5, "contract_weight": "50.00"}],
        "terms": [{"effective_from": "2026-10-02", "recovery_template": "ALL_IN",
            "annual_interest_rate": "7.5", "interest_rate_1": "7.5", "interest_period_days_1": 90,
            "interest_rate_2": "8.0", "interest_period_days_2": 90,
            "storage_rate_per_kg_day": "0.12", "brokerage_rate": "1.0",
            "brokerage_rate_1": "1.0", "brokerage_rate_2": "1.2", "inbound_outbound_rate_per_kg": "15.5",
            "weighing_rate_per_box": "200", "conditions": {"currency": "KRW", "vat": "10%",
                "expense_conditions": [{"code": "WORK", "basis": "BOX", "unit_rate": "50",
                    "tax_treatment": "EXEMPT", "payer": "CONTRACTUAL_PARTY"}]}}],
    }


def test_contract_create_list_update_auto_number_and_audit(api):
    client, factory, _ = api
    created = client.post(URL, json=payload())
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["status"] == "DRAFT"
    assert result["contract_no"].startswith("FC-00001-261002-A1-DP-")
    assert result["participants"][0]["role"] == "ORIGINAL_CONTRACTOR"
    assert result["participants"][1]["account_name"] == "추가 출고업체"
    assert result["lots"][0]["lot_id"] == 1
    assert result["terms"][0]["conditions"]["currency"] == "KRW"
    assert result["terms"][0]["conditions"]["expense_conditions"][0]["code"] == "WORK"
    assert Decimal(result["terms"][0]["interest_rate_2"]) == Decimal("8.0")
    assert result["terms"][0]["interest_period_days_1"] == 90
    assert Decimal(result["terms"][0]["brokerage_rate_2"]) == Decimal("1.2")
    assert result["deposit_amount"] == 30000
    item = client.post(f"{URL}/{result['contract_id']}/items", json={
        "product_id": 2, "contract_box_qty": 2, "contract_weight": "20.00", "memo": "추가 계약상품"})
    assert item.status_code == 201, item.text
    assert client.get(URL).json()[0]["contract_id"] == result["contract_id"]
    update = client.put(f"{URL}/{result['contract_id']}", json={
        "contract_type": "DOMESTIC_PURCHASE", "contract_date": "2026-10-03", "contractor_account_id": 1,
        "deposit_required": True, "deposit_amount": "30000", "memo": "수정"})
    assert update.status_code == 200, update.text
    assert update.json()["memo"] == "수정"
    second = client.post(URL, json=payload()).json()
    assert second["contract_no"] != result["contract_no"]
    with factory() as db:
        events = db.query(AuditEvent).filter(AuditEvent.entity_type == "FINANCING_CONTRACT").all()
        assert [row.action for row in events] == ["CREATE", "UPDATE", "CREATE"]
        assert db.query(models.AccountTransaction).count() == 0
        assert db.query(models.Outbound).count() == 0


def test_company_bound_accounts_lots_and_special_agreement_confirmation_guard(api):
    client, factory, other_lot_id = api
    data = payload("FC-002", agreement="PENDING")
    response = client.post(URL, json=data)
    assert response.status_code == 201, response.text
    contract_id = response.json()["contract_id"]
    assert client.post(f"{URL}/{contract_id}/confirm").status_code == 409
    participant = response.json()["participants"][1]
    updated = client.put(f"{URL}/{contract_id}/participants/{participant['participant_id']}", json={
        "agreement_status": "CONFIRMED", "agreement_date": "2026-10-03", "effective_date": "2026-10-03",
        "status": "ACTIVE", "memo": "약정서 수취"})
    assert updated.status_code == 200, updated.text

    data = payload("FC-003", lot_id=other_lot_id)
    assert client.post(URL, json=data).status_code == 404
    cross_company = payload("FC-004")
    cross_company["contractor_account_id"] = 3
    assert client.post(URL, json=cross_company).status_code == 404
    with factory() as db:
        assert db.query(models.FinancingContract).count() == 1


def test_confirm_term_version_immutability_cancel_and_history(api):
    client, factory, _ = api
    created = client.post(URL, json=payload("FC-005"))
    assert created.status_code == 201, created.text
    contract_id = created.json()["contract_id"]
    confirmed = client.post(f"{URL}/{contract_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "CONFIRMED"
    update = client.put(f"{URL}/{contract_id}", json={
        "contract_type": "DOMESTIC_PURCHASE", "contract_date": "2026-10-02", "contractor_account_id": 1})
    assert update.status_code == 409
    term = client.post(f"{URL}/{contract_id}/terms", json={
        "effective_from": "2026-11-01", "recovery_template": "FREE",
        "annual_interest_rate": "8.0", "conditions": {"agreement": "amended"}, "change_reason": "조건 변경 합의"})
    assert term.status_code == 201, term.text
    assert term.json()["version"] == 2
    assert client.post(f"{URL}/{contract_id}/terms", json={"effective_from": "2026-09-01"}).status_code == 409
    detail = client.get(f"{URL}/{contract_id}").json()
    assert [(row["version"], Decimal(row["annual_interest_rate"])) for row in detail["terms"]] == [
        (1, Decimal("7.5")), (2, Decimal("8.0"))]
    child_history = client.get(f"{URL}/{contract_id}/history").json()
    assert {row["entity_type"] for row in child_history} >= {
        "FINANCING_CONTRACT", "FINANCING_CONTRACT_PARTICIPANT", "FINANCING_CONTRACT_ITEM", "FINANCING_CONTRACT_LOT",
        "FINANCING_CONTRACT_TERM"}
    canceled = client.post(f"{URL}/{contract_id}/cancel", json={"reason": "계약 협의 종료"})
    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "CANCELLED"
    assert client.get(f"{URL}/{contract_id}/history").json()[-1]["action"] == "CANCEL"
    assert client.put(f"{URL}/{contract_id}/participants/2", json={"agreement_status": "PENDING"}).status_code == 409
    with factory() as db:
        row = db.get(models.FinancingContract, contract_id)
        assert row.status == "CANCELLED"
        assert [term.version for term in row.terms] == [1, 2]


def test_contract_qty_cannot_overcommit_lot_source_projection(api):
    client, _, _ = api
    data = payload("FC-006")
    data["lots"][0]["contract_box_qty"] = 21
    assert client.post(URL, json=data).status_code == 409


def test_contract_can_be_created_and_confirmed_before_lot_then_assign_multiple_lots(api):
    client, factory, _ = api
    data = payload("ignored-client-number")
    data["lots"] = []
    data["items"] = [{"product_id": 1, "contract_box_qty": 10, "contract_weight": "100.00"},
        {"product_id": 2, "contract_box_qty": 2, "contract_weight": "20.00", "memo": "별도 품목"}]
    created = client.post(URL, json=data)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["contract_no"] != "ignored-client-number"
    assert body["lots"] == []
    assert [item["product_id"] for item in body["items"]] == [1, 2]
    contract_id = body["contract_id"]
    assert client.post(f"{URL}/{contract_id}/confirm").status_code == 200
    # Different lots of the same product can be linked as later receipts arrive.
    with factory() as db:
        second_lot = models.Lot(comp_code="00001", lot_code="L1-2", source_type="DOMESTIC",
            product_id=1, warehouse_id=1, individual_cost=1000, status="OPEN", use_yn=True)
        db.add(second_lot); db.flush()
        inbound = models.Inbound(comp_code="00001", inbound_no="I2", inbound_date=date(2026, 10, 3),
            warehouse_id=1, transaction_type="PURCHASE_INBOUND")
        db.add(inbound); db.flush()
        db.add(models.InboundItem(inbound_id=inbound.inbound_id, line_no=1, product_id=1,
            lot_id=second_lot.lot_id, box_qty=10, weight=Decimal("100.00"), individual_cost=1000, amount=100000))
        second_id = second_lot.lot_id
        db.commit()
    item_id = body["items"][0]["contract_item_id"]
    one = client.post(f"{URL}/{contract_id}/lots", json={"contract_item_id": item_id, "lot_id": 1,
        "contract_box_qty": 5, "contract_weight": "50.00", "linked_date": "2026-10-03"})
    two = client.post(f"{URL}/{contract_id}/lots", json={"contract_item_id": item_id, "lot_id": second_id,
        "contract_box_qty": 5, "contract_weight": "50.00", "linked_date": "2026-10-04"})
    assert one.status_code == two.status_code == 201, (one.text, two.text)
    detail = client.get(f"{URL}/{contract_id}").json()
    assert len(detail["lots"]) == 2
    assert detail["items"][0]["allocated_box_qty"] == 10
    over = client.post(f"{URL}/{contract_id}/lots", json={"contract_item_id": item_id, "lot_id": 1,
        "contract_box_qty": 1, "contract_weight": "1.00"})
    assert over.status_code == 409


def test_interest_only_requires_domestic_purchase_and_recorded_approval(api):
    client, factory, _ = api
    data = payload("FC-007")
    data["terms"][0]["recovery_template"] = "INTEREST_ONLY"
    assert client.post(URL, json=data).status_code == 409
    data["contract_type"] = "IMPORT_AGENCY"
    data["terms"][0]["conditions"] = {"cost_return_management_approved": True,
        "counterparty_agreement_confirmed": True, "management_approval_memo": "승인·합의"}
    assert client.post(URL, json=data).status_code == 409
    data["contract_type"] = "DOMESTIC_PURCHASE"
    client.is_admin = False
    assert client.post(URL, json=data).status_code == 403
    with factory() as db:
        db.add(models.UserMenuPermission(user_id="tester", menu_code="FINANCING_CONTRACT",
            can_read=True, can_create=True, can_update=True, can_delete=False))
        db.commit()
    assert client.post(URL, json=data).status_code == 201


def test_financing_api_uses_its_menu_permission_mapping():
    rule = permission_for_request("POST", URL)
    assert (rule.menu_code, rule.action) == ("FINANCING_CONTRACT", "create")
    confirm = permission_for_request("POST", f"{URL}/1/confirm")
    assert (confirm.menu_code, confirm.action) == ("FINANCING_CONTRACT", "update")


def test_financing_gui_builds_contract_from_existing_account_lot_and_term(monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app_context import app_context
    from views.financing_contract_reg import FinancingContractWindow
    import views.financing_contract_reg as financing_ui

    class Response:
        def __init__(self, value): self.value = value
        def json(self): return self.value
        def raise_for_status(self): return None

    app = QApplication.instance() or QApplication([])
    app_context.set_company("00001", "테스트회사")
    monkeypatch.setattr(FinancingContractWindow, "_get", lambda self, path, **params: (
        [{"account_id": 1, "account_name": "계약업체", "account_code": "A1"}] if path == "accounts" else
        [{"lot_id": 1, "lot_code": "L1", "product_name": "상품", "warehouse_name": "창고", "product_id": 1}]))
    list_rows = []
    monkeypatch.setattr(financing_ui.httpx, "get", lambda url, *args, **kwargs: Response(
        [{"product_id": 1, "product_code": "P1", "product_name": "상품"}] if str(url).endswith("/products") else list_rows))
    captured = {}

    def post(url, json=None, timeout=20):
        captured.update(json)
        list_rows[:] = [{"contract_id": 1, "contract_no": "FC-00001-261002-A1-DP-0001",
            "contract_date": json["contract_date"], "contract_type": json["contract_type"],
            "contractor_account_id": json["contractor_account_id"], "contractor_name": "계약업체",
            "status": "DRAFT", "items": [{"contract_item_id": 1, "product_id": 1, "product_code": "P1",
                "product_name": "상품", "contract_box_qty": 5, "contract_weight": "50.00", "allocated_box_qty": 0,
                "allocated_weight": 0}], "lots": [], "terms": json["terms"], "participants": []}]
        return Response(list_rows[0])
    monkeypatch.setattr(financing_ui.httpx, "post", post)

    window = FinancingContractWindow()
    window.show(); app.processEvents()
    window.item_box.setText("5"); window.item_kg.setText("50.00"); window.add_item_row()
    window.create_contract()
    assert "contract_no" not in captured
    assert captured["items"][0]["product_id"] == 1
    assert captured["items"][0]["contract_box_qty"] == 5
    assert captured["lots"] == []
    assert captured["terms"][0]["recovery_template"] == "ALL_IN"
    assert window.contract_date.calendarPopup()
    assert window.interest_days_1.placeholderText()
    window.interest_1.setText("5.5"); window.interest_1.setFocus(); app.processEvents()
    assert window.interest_1.selectedText() == "5.5"
    assert window.table.rowCount() == 1
    window.close()
