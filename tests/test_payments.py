from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

with patch("sqlalchemy.create_engine", return_value=create_engine("sqlite://")):
    import main
import models, payment_routes
from audit_service import AuditEvent
from database import Base, get_db
from permissions import issue_token, permission_for_request

URL="/api/v1/companies/00001/payments"

@pytest.fixture
def api(monkeypatch):
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    @event.listens_for(engine,"connect")
    def setup(conn,_): conn.execute("PRAGMA foreign_keys=ON"); conn.create_function("SYSUTCDATETIME",0,lambda:datetime.now(timezone.utc).replace(tzinfo=None).isoformat(" "))
    for table in Base.metadata.tables.values(): table.dialect_options["sqlite"]["autoincrement"]=True
    Base.metadata.create_all(engine); factory=sessionmaker(bind=engine,autoflush=False)
    with factory() as db:
        db.add_all([models.Company(comp_code="00001",comp_name="T",biz_no="1"),models.User(user_id="tester",user_name="T",password_hash="x",is_admin=True),models.Account(account_id=1,account_code="S1",account_name="매입처"),models.MenuMaster(menu_code="PAYMENT_MANAGEMENT",menu_name="지급관리",menu_group="입금/출금관리")]); db.commit()
        db.add(models.CompanyAccount(comp_code="00001",account_id=1,purchase_yn=True)); db.add_all([models.AccountTransaction(comp_code="00001",transaction_no="OP-1",transaction_date=date(2026,10,1),account_id=1,transaction_type="OPENING_PAYABLE",original_amount=100000),models.AccountTransaction(comp_code="00001",transaction_no="PU-1",transaction_date=date(2026,10,2),account_id=1,transaction_type="PURCHASE_PAYABLE",original_amount=50000)]); db.commit()
    def dependency():
        with factory() as db: yield db
    main.app.dependency_overrides[get_db]=dependency; monkeypatch.setattr(main,"SessionLocal",factory); monkeypatch.setattr(payment_routes,"allocate_document_no",lambda db,c,k,d:f"PY-{d:%Y%m%d}-{db.query(models.AccountTransaction).count():04d}")
    with TestClient(main.app,raise_server_exceptions=False) as client:
        client.headers["Authorization"]="Bearer "+issue_token("tester"); yield client,factory
    main.app.dependency_overrides.clear(); engine.dispose()

def body(amount,memo="지급") : return {"payment_date":"2026-10-03","account_id":1,"amount":amount,"memo":memo}

def test_payment_fifo_multiple_update_delete_and_audit(api):
    client,factory=api
    assert permission_for_request("POST",URL).menu_code=="PAYMENT_MANAGEMENT"
    first=client.post(URL,json=body(120000)); second=client.post(URL,json=body(80000)); assert first.status_code==second.status_code==201
    assert first.json()["allocated_amount"]==120000 and second.json()["unallocated_amount"]==50000
    changed=client.put(f"{URL}/{first.json()['account_transaction_id']}",json=body(60000)); assert changed.status_code==200 and changed.json()["allocated_amount"]==60000
    assert client.delete(f"{URL}/{second.json()['account_transaction_id']}").status_code==200
    with factory() as db:
        assert [x.action for x in db.query(AuditEvent).filter_by(entity_type="PAYMENT").order_by(AuditEvent.audit_event_id)]==["CREATE","CREATE","UPDATE","DELETE"]
        assert sum(int(x.allocated_amount) for x in db.query(models.AccountTransactionAllocation))==60000
    summary=client.get("/api/v1/companies/00001/payment-payable-summary",params={"account_id":1,"transaction_date":"2026-10-03"})
    assert summary.status_code==200 and summary.json()=={"previous_payable":150000,"today_purchase":0,"today_payment":60000,"current_payable":90000}

def test_negative_adjustment_requires_reason_and_reverses_advance(api):
    client,factory=api
    assert client.post(URL,json=body(-1," ")).status_code==422
    assert client.post(URL,json=body(200000)).status_code==201
    adjusted=client.post(URL,json=body(-50000,"착오 지급 상계")); assert adjusted.status_code==201 and adjusted.json()["unallocated_amount"]==-50000
    assert client.post(URL,json=body(-200000,"초과조정")).status_code==409
